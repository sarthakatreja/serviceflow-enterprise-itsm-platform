from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from serviceflow.demo_accounts import DEMO_PASSWORD
from serviceflow.main import create_app
from serviceflow.models import User
from serviceflow.seed import reset_demo, seed_demo

from conftest import sign_in


asset = {
    "name": "Warehouse support laptop", "tag": "BRI-QA-018", "type": "laptop", "manufacturer": "Dell",
    "model": "Latitude 5450", "location": "Brisbane warehouse", "status": "in_stock",
    "serial_number": "FICTIONAL-0001", "purchase_date": "2026-04-15", "notes": "Ready for onboarding.",
}


def test_inventory_create_edit_search_filter_and_restart_persistence(client, settings):
    technician = sign_in(client, "technician").json()
    sign_in(client)
    assert client.get("/api/assets").json()["total"] == 16
    result = client.post("/api/assets", json=asset)
    assert result.status_code == 201
    record = result.json()
    asset_path = f"/api/assets/{record['id']}"
    updated = client.patch(asset_path, json={"assigned_user_id": technician["id"], "status": "in_use"})
    assert updated.status_code == 200 and updated.json()["assigned_user"]["id"] == technician["id"]
    listed = client.get("/api/assets?search=warehouse&type=laptop&status=in_use").json()
    assert listed["total"] == 1 and listed["items"][0]["tag"] == asset["tag"]
    with TestClient(create_app(settings)) as restarted:
        sign_in(restarted)
        stored = restarted.get(asset_path).json()
        assert stored["assigned_user"]["id"] == technician["id"] and stored["status"] == "in_use"
        assert stored["purchase_date"] == asset["purchase_date"]
    logs = client.get("/api/audit-logs?entity=asset").json()["items"]
    assert [row["action"] for row in logs[:2]] == ["asset.updated", "asset.created"]


def test_case_normalized_asset_tags_are_unique_and_rejected_on_update(client):
    sign_in(client)
    assert client.post("/api/assets", json=asset).status_code == 201
    assert client.post("/api/assets", json={**asset, "tag": asset["tag"].lower()}).status_code == 409
    other = client.post("/api/assets", json={**asset, "tag": "BRI-QA-019"}).json()
    assert client.patch(f"/api/assets/{other['id']}", json={"tag": asset["tag"].lower()}).status_code == 409
    assert client.post("/api/assets", json={**asset, "type": "unknown"}).status_code == 422


@pytest.mark.parametrize("role", ["employee", "technician"])
def test_non_admin_apis_refuse_privileged_operations(client, role):
    sign_in(client, role)
    for path in ("/api/reports", "/api/reports/export", "/api/users", "/api/users/choices", "/api/audit-logs"):
        assert client.get(path).status_code == 403
    assert client.post("/api/assets", json=asset).status_code == 403
    assert client.get("/api/assets").status_code == (403 if role == "employee" else 200)
    settings = client.get("/api/settings").json()
    assert settings["low_hours"] == 72
    settings.pop("demo")
    assert client.put("/api/settings/sla", json=settings).status_code == 403


def test_user_lifecycle_and_audit_exclude_credentials(client):
    signed_in = sign_in(client).json()
    credentials = {
        "name": "Casey Wright", "email": "casey@serviceflow.test", "role": "employee",
        "password": "Casey test password 23",
    }
    created = client.post("/api/users", json=credentials)
    assert created.status_code == 201
    assert "password" not in created.text
    path = f"/api/users/{created.json()['id']}"
    duplicate = client.post("/api/users", json={**credentials, "email": credentials["email"].upper()})
    assert duplicate.status_code == 409
    assert client.get("/api/users?search=casey&role=employee").json()["total"] == 1
    assert client.patch(f"/api/users/{signed_in['id']}", json={"role": "employee"}).status_code == 409
    reset = "Replacement test password 25"
    assert client.patch(path, json={"password": reset, "role": "technician"}).status_code == 200
    assert sign_in(client, "casey", credentials["password"]).status_code == 401
    assert sign_in(client, "casey", reset).json()["role"] == "technician"
    sign_in(client)
    assert client.patch(path, json={"active": False}).json()["active"] is False
    log = client.get("/api/audit-logs?entity=user").text
    assert "user.created" in log and "user.updated" in log
    assert reset not in log and credentials["password"] not in log
    assert sign_in(client, "casey", reset).status_code == 401


def test_active_technician_cannot_be_disabled_while_assigned_to_open_work(client):
    technician = sign_in(client, "technician").json()
    sign_in(client)
    result = client.patch(f"/api/users/{technician['id']}", json={"active": False})
    assert result.status_code == 409
    assert client.patch(f"/api/users/{technician['id']}", json={"role": "employee"}).status_code == 409


def test_demo_seeding_is_repeatable_and_reset_is_explicit(client):
    sign_in(client)
    record = client.post("/api/assets", json=asset).json()
    with Session(client.app.state.engine) as db, db.begin():
        assert seed_demo(db) is False
    assert client.get(f"/api/assets/{record['id']}").status_code == 200
    with Session(client.app.state.engine) as db, db.begin():
        reset_demo(db)
        assert len(db.scalars(select(User)).all()) == 8
    assert client.get("/api/auth/me").status_code == 401
    assert sign_in(client, "admin", DEMO_PASSWORD).status_code == 200
    assert client.get("/api/assets").json()["total"] == 16


def test_demo_reset_refuses_non_demo_database(settings):
    with TestClient(create_app(settings)) as client, Session(client.app.state.engine) as db:
        with pytest.raises(ValueError, match="only available"):
            reset_demo(db)
        assert client.get("/api/auth/context").json() == {"demo": False}
