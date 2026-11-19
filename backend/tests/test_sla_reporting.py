import csv
from datetime import datetime, timedelta, timezone
from io import StringIO

import pytest

from serviceflow.domain import Priority, SlaState
from serviceflow.models import Ticket, Workspace
from serviceflow.policy import deadline, remaining_seconds, sla_state

from conftest import create_ticket, sign_in


@pytest.mark.parametrize(("delta", "resolution", "expected"), [
    (3, None, SlaState.ON_TRACK),
    (2, None, SlaState.DUE_SOON),
    (0, None, SlaState.DUE_SOON),
    (-1, None, SlaState.OVERDUE),
    (-1, 0, SlaState.MET),
    (-2, -1, SlaState.BREACHED),
])
def test_sla_state_boundaries(delta, resolution, expected):
    now = datetime(2026, 11, 19, 1, tzinfo=timezone.utc)
    due = now + timedelta(hours=delta)
    completed = due - timedelta(hours=resolution) if resolution is not None else None
    ticket = Ticket(sla_deadline=due, resolved_at=completed)
    assert sla_state(ticket, now, 2) == expected
    assert remaining_seconds(ticket, now) == (None if completed else delta * 3600)


def test_configurable_sla_keeps_existing_deadline_until_reprioritised(client):
    sign_in(client)
    previous = create_ticket(client, priority="medium").json()
    initial = client.get("/api/settings").json()
    assert (initial["critical_hours"], initial["high_hours"], initial["medium_hours"], initial["low_hours"]) == (4, 8, 24, 72)
    payload = {"critical_hours": 2, "high_hours": 6, "medium_hours": 18, "low_hours": 48, "warning_hours": 1}
    assert client.put("/api/settings/sla", json={**payload, "low_hours": 2}).status_code == 422
    assert client.put("/api/settings/sla", json={**payload, "warning_hours": 3}).status_code == 422
    put = client.put("/api/settings/sla", json=payload)
    assert put.status_code == 200 and put.json()["medium_hours"] == 18
    path = f"/api/tickets/{previous['id']}"
    assert client.get(path).json()["sla_deadline"] == previous["sla_deadline"]
    new = create_ticket(client, priority="critical").json()
    assert datetime.fromisoformat(new["sla_deadline"]) == deadline(
        datetime.fromisoformat(new["created_at"]), Priority.CRITICAL, Workspace(**payload),
    )
    adjusted = client.patch(path, json={"priority": "high"}).json()
    assert datetime.fromisoformat(adjusted["sla_deadline"]) - datetime.fromisoformat(previous["created_at"]) == timedelta(hours=6)
    log = client.get("/api/audit-logs?entity=workspace").json()["items"]
    assert log[0]["action"] == "settings.sla_updated"


def test_database_backed_dashboard_matches_ticket_and_sla_queues(client):
    sign_in(client)
    summary = client.get("/api/dashboard/summary").json()
    tickets = client.get("/api/tickets?limit=100").json()["items"]
    assert summary["total"] == len(tickets) == 38
    assert summary["assets"] == 16
    assert summary["open"] == sum(row["status"] == "open" for row in tickets)
    assert summary["critical"] == sum(row["priority"] == "critical" and row["resolved_at"] is None for row in tickets)
    assert summary["resolved"] == sum(row["resolved_at"] is not None for row in tickets)
    assert summary["overdue"] == client.get("/api/tickets?sla=overdue").json()["total"]
    assert summary["due_soon"] == client.get("/api/tickets?sla=due_soon").json()["total"]
    assert summary["sla_breaches"] == summary["overdue"] + summary["sla_late"]
    assert summary["compliance"] == round(summary["sla_met"] * 100 / summary["resolved"], 1)
    assert len(summary["activity"]) == 14
    create_ticket(client, priority="critical")
    updated = client.get("/api/dashboard/summary").json()
    assert updated["total"] == summary["total"] + 1
    assert updated["critical"] == summary["critical"] + 1
    assert updated["recent"][0]["title"] == "Replacement keyboard request"


def test_report_filters_match_export_and_protect_spreadsheet_cells(client):
    sign_in(client)
    formula_like = "=2026+11"
    created = create_ticket(client, title=formula_like, priority="critical").json()
    today = created["created_at"][:10]
    filters = {"priority": "critical", "status": "open", "start": today, "end": today}
    report = client.get("/api/reports", params=filters).json()
    exported = client.get("/api/reports/export", params=filters)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == report["total"] >= 1
    match = next(row for row in rows if row["Ticket"] == created["number"])
    assert match["Title"] == "'" + formula_like and match["Priority"] == "critical"
    assert report["by_status"]["open"] == report["total"]
    assert report["assets"] == 16
    assert report["compliance"] is None and report["average_resolution_hours"] is None
    assert client.get("/api/reports?start=2026-11-19&end=2026-11-18").status_code == 422
    assert client.get("/api/reports/export?end=9999-12-31").status_code == 422


def test_report_resolution_time_uses_stored_timestamps(client):
    sign_in(client)
    report = client.get("/api/reports?status=resolved").json()
    rows = client.get("/api/tickets?status=resolved&limit=100").json()["items"]
    elapsed = [(datetime.fromisoformat(row["resolved_at"]) - datetime.fromisoformat(row["created_at"])).total_seconds()
               for row in rows]
    assert report["total"] == report["resolved"] == len(rows) > 0
    assert report["average_resolution_hours"] == round(sum(elapsed) / len(elapsed) / 3600, 1)
    assert sum(report["by_category"].values()) == len(rows)
    assert sum(row["resolved"] for row in report["workload"]) == len(rows)
