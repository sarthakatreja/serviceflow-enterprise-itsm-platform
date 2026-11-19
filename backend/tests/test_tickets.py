from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from serviceflow.main import create_app

from conftest import create_ticket, sign_in


def test_employee_creates_updates_and_comments_on_own_ticket(client):
    employee = sign_in(client, "employee").json()
    result = create_ticket(client)
    assert result.status_code == 201
    ticket = result.json()
    assert ticket["status"] == "open"
    assert ticket["creator"]["id"] == employee["id"]
    start = datetime.fromisoformat(ticket["created_at"])
    due = datetime.fromisoformat(ticket["sla_deadline"])
    assert start.tzinfo is not None and due - start == timedelta(hours=24)
    path = f"/api/tickets/{ticket['id']}"
    assert client.patch(path, json={"title": "Replacement input device"}).status_code == 200
    assert client.patch(path, json={"priority": "critical"}).status_code == 403
    assert client.post(path + "/comments", json={"body": "Available for a diagnostic call."}).status_code == 201
    detail = client.get(path).json()
    assert detail["title"] == "Replacement input device"
    assert detail["comments"][0]["author"]["id"] == employee["id"]
    assert {row["action"] for row in detail["activity"]} == {
        "ticket.created", "ticket.updated", "ticket.comment_added",
    }


def test_employee_cannot_view_comment_or_modify_another_request(client):
    sign_in(client, "alex")
    result = create_ticket(client)
    assert result.status_code == 201
    path = f"/api/tickets/{result.json()['id']}"
    employee = sign_in(client, "employee").json()
    assert client.get(path).status_code == 404
    assert client.patch(path, json={"title": "Updated title"}).status_code == 404
    assert client.post(path + "/comments", json={"body": "Please follow up."}).status_code == 404
    listing = client.get("/api/tickets?scope=visible&limit=100").json()
    assert all(row["creator"]["id"] == employee["id"] for row in listing["items"])
    assert all(row["creator"]["id"] == employee["id"] for row in client.get("/api/dashboard/summary").json()["recent"])


def test_asset_choices_and_association_respect_employee_ownership(client):
    sign_in(client)
    assets = client.get("/api/assets?limit=100").json()["items"]
    sign_in(client, "employee")
    visible = client.get("/api/assets/choices").json()["items"]
    assert visible
    owned = {row["id"] for row in visible}
    outside = next(row["id"] for row in assets if row["id"] not in owned)
    denied = create_ticket(client, asset_id=outside)
    assert denied.status_code == 404
    accepted = create_ticket(client, asset_id=visible[0]["id"])
    assert accepted.status_code == 201
    assert accepted.json()["asset"]["id"] == visible[0]["id"]


def test_admin_assigns_technician_and_technician_resolves_with_notes(client):
    technician = sign_in(client, "technician").json()
    sign_in(client)
    ticket = create_ticket(client, priority="high").json()
    path = f"/api/tickets/{ticket['id']}"
    assigned = client.patch(path, json={"assignee_id": technician["id"], "version": ticket["version"]})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["assignee"]["id"] == technician["id"]

    sign_in(client, "technician")
    assert create_ticket(client).status_code == 403
    assert client.patch(path, json={"priority": "critical"}).status_code == 403
    assert client.patch(path, json={"status": "in_progress"}).status_code == 200
    assert client.patch(path, json={"status": "resolved"}).status_code == 422
    done = client.patch(path, json={"status": "resolved", "resolution_notes": "Device replaced and validated."})
    assert done.status_code == 200
    assert done.json()["sla_state"] == "met"
    assert done.json()["resolved_at"] is not None
    assert done.json()["remaining_seconds"] is None
    assert client.patch(path, json={"resolution_notes": ""}).status_code == 422
    assert client.patch(path, json={"status": "closed"}).status_code == 409

    sign_in(client)
    closed = client.patch(path, json={"status": "closed"})
    assert closed.status_code == 200
    assert closed.json()["resolved_at"] == done.json()["resolved_at"]
    assert client.patch(path, json={"title": "Closed ticket edit"}).status_code == 409
    assert client.post(path + "/comments", json={"body": "Late comment."}).status_code == 409
    entries = client.get("/api/audit-logs?entity=ticket&limit=100").json()["items"]
    assert {"ticket.assigned", "ticket.status_changed"} <= {
        item["action"] for item in entries if item["entity_id"] == ticket["id"]
    }


def test_technicians_only_see_assigned_work_and_assets(client):
    sign_in(client)
    ticket = create_ticket(client).json()
    assets = client.get("/api/assets?limit=100").json()["items"]
    tech = sign_in(client, "technician").json()
    assigned = client.get("/api/tickets?limit=100").json()["items"]
    assert assigned and all(row["assignee"]["id"] == tech["id"] for row in assigned)
    assert client.get(f"/api/tickets/{ticket['id']}").status_code == 404
    results = client.get("/api/assets?limit=100").json()["items"]
    assert {asset["id"] for asset in results} == {row["asset"]["id"] for row in assigned if row["asset"]}
    outside = next(row["id"] for row in assets if row["id"] not in {asset["id"] for asset in results})
    assert client.get(f"/api/assets/{outside}").status_code == 404


def test_invalid_workflow_changes_rollback_without_activity(client):
    admin = sign_in(client).json()
    ticket = create_ticket(client).json()
    path = f"/api/tickets/{ticket['id']}"
    assert client.patch(path, json={"status": "resolved", "resolution_notes": "A note."}).status_code == 409
    assert client.patch(path, json={"status": "assigned"}).status_code == 409
    assert client.patch(path, json={"assignee_id": admin["id"]}).status_code == 422
    after = client.get(path).json()
    assert after["version"] == ticket["version"]
    assert after["status"] == "open" and after["assignee"] is None
    assert after["activity"] == ticket["activity"]


def test_stale_ticket_update_returns_conflict_and_preserves_current_state(client):
    sign_in(client)
    ticket = create_ticket(client).json()
    path = f"/api/tickets/{ticket['id']}"
    version = ticket["version"]
    assert client.patch(path, json={"version": version, "priority": "critical"}).status_code == 200
    assert client.patch(path, json={"version": version, "priority": "low"}).status_code == 409
    updated = client.get(path).json()
    assert updated["priority"] == "critical"
    assert datetime.fromisoformat(updated["sla_deadline"]) - datetime.fromisoformat(ticket["created_at"]) == timedelta(hours=4)


def test_ticket_filters_pagination_sorting_and_ticket_number_search(client):
    sign_in(client)
    filters = {"search": "", "priority": "high", "sort": "oldest", "limit": 2}
    first = client.get("/api/tickets", params=filters).json()
    second = client.get("/api/tickets", params={**filters, "offset": 2}).json()
    ids = [row["id"] for row in first["items"] + second["items"]]
    assert first["total"] == second["total"] >= 4
    assert len(set(ids)) == 4 and ids == sorted(ids)
    assert all(row["priority"] == "high" for row in first["items"] + second["items"])
    number = first["items"][0]["number"]
    found = client.get("/api/tickets", params={"search": number}).json()
    assert found["total"] == 1 and found["items"][0]["number"] == number
    assert client.get("/api/tickets?status=unknown").status_code == 422


def test_ticket_and_comment_survive_reopening_the_same_database(client, settings):
    sign_in(client)
    ticket = create_ticket(client).json()
    path = f"/api/tickets/{ticket['id']}"
    client.post(path + "/comments", json={"body": "Persistence check."})
    with TestClient(create_app(settings)) as reopened:
        sign_in(reopened)
        detail = reopened.get(path).json()
        assert detail["title"] == ticket["title"]
        assert detail["comments"][0]["body"] == "Persistence check."


def test_invalid_ticket_input_has_no_side_effect(client):
    sign_in(client)
    before = client.get("/api/dashboard/summary").json()["total"]
    assert create_ticket(client, title="  ", priority="urgent").status_code == 422
    assert create_ticket(client, creator_id=999).status_code == 422
    assert client.get("/api/dashboard/summary").json()["total"] == before


def test_admin_archives_only_closed_tickets_and_can_restore_history(client):
    sign_in(client)
    count = client.get("/api/dashboard/summary").json()["total"]
    ticket = client.get("/api/tickets?status=closed&limit=1").json()["items"][0]
    path = f"/api/tickets/{ticket['id']}"
    open_ticket = create_ticket(client).json()
    assert client.delete(f"/api/tickets/{open_ticket['id']}").status_code == 409
    assert client.delete(path).status_code == 204
    assert client.get(path).json()["archived_at"] is not None
    assert client.get("/api/dashboard/summary").json()["total"] == count
    assert client.get("/api/reports").json()["total"] == count
    assert client.get("/api/tickets", params={"search": ticket["number"]}).json()["total"] == 0
    archives = client.get("/api/tickets?archived=true").json()
    assert archives["total"] == 1 and archives["items"][0]["id"] == ticket["id"]
    sign_in(client, "employee")
    assert client.get("/api/tickets?archived=true").status_code == 403
    assert client.get(path).status_code == 404
    assert client.post(path + "/restore").status_code == 403
    sign_in(client)
    restored = client.post(path + "/restore").json()
    assert restored["archived_at"] is None and restored["status"] == "closed"
    assert [row["action"] for row in restored["activity"][:2]] == ["ticket.restored", "ticket.archived"]
    assert client.get("/api/dashboard/summary").json()["total"] == count + 1
