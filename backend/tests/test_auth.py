from hashlib import sha256

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from serviceflow.auth import SESSION_COOKIE, verify_password
from serviceflow.demo_accounts import DEMO_PASSWORD
from serviceflow.domain import utcnow
from serviceflow.main import create_app
from serviceflow.models import AuditEvent, LoginSession, User

from conftest import sign_in


def test_health_and_empty_workspace(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/auth/context").json() == {"demo": False}
        assert client.post("/api/auth/demo", json={"role": "admin"}).status_code == 404
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("path", [
    "/api/tickets", "/api/assets", "/api/dashboard/summary", "/api/reports",
    "/api/reports/export", "/api/users", "/api/audit-logs", "/api/settings",
])
def test_api_routes_require_an_authenticated_session(client, path):
    assert client.get(path).status_code == 401


def test_seeded_login_stores_only_password_and_session_hashes(client):
    response = sign_in(client)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert "password_hash" not in response.json()
    assert client.get("/api/auth/me").json()["email"] == "admin@serviceflow.test"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies[SESSION_COOKIE]
    with Session(client.app.state.engine) as db:
        user = db.scalar(select(User).where(User.email == "admin@serviceflow.test"))
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password(user.password_hash, DEMO_PASSWORD)
        assert user.password_hash != DEMO_PASSWORD
        session = db.get(LoginSession, sha256(token.encode()).hexdigest())
        assert session.user_id == user.id and session.expires_at > utcnow()
        assert session.token_hash != token
        assert db.get(LoginSession, token) is None


@pytest.mark.parametrize("account", ["admin", "unknown"])
def test_invalid_login_is_generic_and_audited(client, account):
    submitted = "Invalid test credential 42"
    response = sign_in(client, account, submitted)
    assert response.status_code == 401
    assert response.json() == {"detail": "Email or password is incorrect."}
    assert SESSION_COOKIE not in client.cookies
    with Session(client.app.state.engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.login_failed"))
        assert event is not None and event.actor_id is None
        assert submitted not in event.detail


def test_logout_revokes_database_session(client):
    sign_in(client)
    token = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={token}"}).status_code == 401


def test_password_change_revokes_sessions_and_persists_new_password(client):
    sign_in(client, "employee")
    change = {"current_password": "Incorrect password", "new_password": "Replacement test pass 42"}
    assert client.post("/api/auth/password", json=change).status_code == 400
    change["current_password"] = DEMO_PASSWORD
    assert client.post("/api/auth/password", json=change).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert sign_in(client, "employee").status_code == 401
    assert client.post("/api/auth/demo", json={"role": "employee"}).status_code == 401
    assert sign_in(client, "employee", change["new_password"]).status_code == 200


@pytest.mark.parametrize("role", ["admin", "technician", "employee"])
def test_demo_button_opens_only_the_matching_seeded_role(client, role):
    result = client.post("/api/auth/demo", json={"role": role})
    assert result.status_code == 200
    assert client.get("/api/auth/me").json()["role"] == role


def test_browser_origin_allowlist_applies_to_writes_and_cors(client):
    data = {"email": "admin@serviceflow.test", "password": DEMO_PASSWORD}
    rejected = client.post("/api/auth/login", json=data, headers={"Origin": "https://other.example"})
    assert rejected.status_code == 403
    assert "access-control-allow-origin" not in rejected.headers
    accepted = client.post("/api/auth/login", json=data, headers={"Origin": "http://127.0.0.1:5173"})
    assert accepted.status_code == 200
    assert accepted.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert accepted.headers["x-content-type-options"] == "nosniff"


def test_invalid_login_shape_omits_values_from_validation_response(client):
    response = client.post("/api/auth/login", json={"email": "invalid", "password": "a" * 129})
    assert response.status_code == 422
    assert "a" * 129 not in response.text
    assert set(response.json()["detail"][0]) == {"loc", "msg"}


def test_built_frontend_deep_links_and_api_not_found(settings, tmp_path):
    frontend = tmp_path / "web"
    frontend.mkdir()
    (frontend / "index.html").write_text("<title>ServiceFlow frontend</title>")
    (frontend / "assets").mkdir()
    (frontend / "assets" / "fixture.js").write_text("console.log('fixture');")
    with TestClient(create_app(settings.model_copy(update={"frontend_dir": frontend}))) as client:
        assert "ServiceFlow frontend" in client.get("/tickets/12").text
        assert "ServiceFlow frontend" in client.get("/assets/12").text
        assert "console.log" in client.get("/assets/fixture.js").text
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/unknown").status_code == 404
