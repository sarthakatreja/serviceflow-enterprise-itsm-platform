from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from serviceflow import tickets
from serviceflow.domain import TicketStatus, utcnow
from serviceflow.main import create_app
from serviceflow.models import Ticket, TicketResolution

from conftest import create_ticket, sign_in


def test_reopening_requires_fresh_notes_and_preserves_both_resolution_records(client):
    technician = sign_in(client, "technician").json()
    sign_in(client, "employee")
    ticket = create_ticket(client).json()
    path = f"/api/tickets/{ticket['id']}"
    sign_in(client)
    assert client.patch(path, json={"assignee_id": technician["id"]}).status_code == 200
    sign_in(client, "technician")
    assert client.patch(path, json={"status": "in_progress"}).status_code == 200

    first_notes = "Replaced the keyboard and verified the input device."
    first = client.patch(path, json={"status": "resolved", "resolution_notes": first_notes}).json()
    first_entry = first["resolution_history"][0]
    assert first_entry["notes"] == first_notes
    assert first_entry["resolver"]["id"] == technician["id"]

    reopened = client.patch(path, json={"status": "in_progress", "resolution_notes": first_notes}).json()
    assert reopened["status"] == "in_progress"
    assert reopened["resolved_at"] is None
    assert reopened["resolution_notes"] == ""
    assert reopened["resolution_history"] == [first_entry]
    assert reopened["sla_deadline"] == first["sla_deadline"]

    rejected = client.patch(path, json={"status": "resolved"})
    assert rejected.status_code == 422
    assert "new resolution notes" in rejected.json()["detail"]
    assert client.patch(path, json={"status": "resolved", "resolution_notes": "   "}).status_code == 422
    current = client.get(path).json()
    assert current["version"] == reopened["version"]
    assert current["resolution_history"] == [first_entry]

    final_notes = "Replaced the loose internal connector and ran an extended hardware test."
    result = client.patch(path, json={"status": "resolved", "resolution_notes": final_notes})
    assert result.status_code == 200
    final = result.json()
    assert final["resolution_history"][0]["notes"] == final_notes
    assert final["resolution_history"][0]["resolved_at"] == final["resolved_at"]
    assert final["resolution_history"][0]["id"] != first_entry["id"]
    assert final["resolution_history"][1] == first_entry
    assert datetime.fromisoformat(final["resolved_at"]) > datetime.fromisoformat(first["resolved_at"])

    sign_in(client, "employee")
    assert client.get(path).json()["resolution_history"] == final["resolution_history"]


def test_saved_resolution_draft_still_works_for_first_resolution(client):
    sign_in(client)
    listing = client.get("/api/tickets?status=in_progress&limit=1").json()
    path = f"/api/tickets/{listing['items'][0]['id']}"
    draft = "Diagnosed and repaired the connectivity issue."
    assert client.patch(path, json={"resolution_notes": draft}).status_code == 200
    result = client.patch(path, json={"status": "resolved"})
    assert result.status_code == 200
    assert result.json()["resolution_history"][0]["notes"] == draft


def test_upgrade_imports_legacy_note_and_clears_stale_reopened_draft(client, settings):
    engine = client.app.state.engine
    with Session(engine) as db, db.begin():
        ticket = db.scalar(select(Ticket).where(Ticket.status == TicketStatus.RESOLVED).limit(1))
        old_id = ticket.id
        old_note = ticket.resolution_notes
        old_time = ticket.resolved_at
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.resolved_at = None
        ticket.updated_at = reopened_at = utcnow()
    TicketResolution.__table__.drop(engine)

    for _ in range(2):
        with TestClient(create_app(settings)) as restarted:
            sign_in(restarted)
            detail = restarted.get(f"/api/tickets/{old_id}").json()
            assert detail["status"] == "in_progress"
            assert detail["resolution_notes"] == ""
            assert datetime.fromisoformat(detail["updated_at"]) == reopened_at
            assert len(detail["resolution_history"]) == 1
            entry = detail["resolution_history"][0]
            assert entry["notes"] == old_note
            assert datetime.fromisoformat(entry["resolved_at"]) == old_time


def test_sla_endpoint_refreshes_clock_and_keeps_ticket_scope(client, monkeypatch):
    sign_in(client, "employee")
    ticket = create_ticket(client, priority="critical").json()
    path = f"/api/tickets/{ticket['id']}/sla"
    deadline = datetime.fromisoformat(ticket["sla_deadline"])
    monkeypatch.setattr(tickets, "utcnow", lambda: deadline - timedelta(seconds=20))
    due = client.get(path).json()
    assert due == {"version": ticket["version"], "sla_state": "due_soon", "remaining_seconds": 20}
    monkeypatch.setattr(tickets, "utcnow", lambda: deadline + timedelta(seconds=15))
    assert client.get(path).json() == {"version": ticket["version"], "sla_state": "overdue", "remaining_seconds": -15}
    sign_in(client, "alex")
    assert client.get(path).status_code == 404
    client.post("/api/auth/logout")
    assert client.get(path).status_code == 401
