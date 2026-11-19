from collections.abc import Iterator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from serviceflow.config import Settings
from serviceflow.demo_accounts import DEMO_PASSWORD
from serviceflow.main import create_app
from serviceflow.seed import seed_demo


@pytest.fixture
def settings(tmp_path):
    database = (tmp_path / "serviceflow-test.db").as_posix()
    return Settings(database_url=f"sqlite:///{database}", _env_file=None)


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as connection:
        with Session(connection.app.state.engine) as db, db.begin():
            seed_demo(db)
        yield connection


def sign_in(client: TestClient, account: str = "admin", password: str = DEMO_PASSWORD):
    return client.post("/api/auth/login", json={
        "email": f"{account}@serviceflow.test", "password": password,
    })


def create_ticket(client: TestClient, **overrides):
    fields = {
        "title": "Replacement keyboard request",
        "description": "The keyboard intermittently stops responding on the finance laptop.",
        "category": "hardware",
        "priority": "medium",
    }
    return client.post("/api/tickets", json={**fields, **overrides})
