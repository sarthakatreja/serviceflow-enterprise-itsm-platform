"""Serve the built UI with a fresh, disposable database for Playwright."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session
import uvicorn

from serviceflow.config import Settings
from serviceflow.db import make_engine
from serviceflow.main import create_app, initialize
from serviceflow.seed import seed_demo


def main():
    port = int(os.environ.get("SERVICEFLOW_E2E_PORT", "18011"))
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    with TemporaryDirectory(prefix="serviceflow-e2e-") as directory:
        database = (Path(directory) / "e2e.db").as_posix()
        settings = Settings(
            _env_file=None, database_url=f"sqlite:///{database}", frontend_dir=frontend,
            allowed_origins=f"http://127.0.0.1:{port}", cookie_secure=False,
        )
        engine = make_engine(settings.database_url)
        try:
            initialize(engine)
            with Session(engine) as db, db.begin():
                seed_demo(db)
        finally:
            engine.dispose()
        uvicorn.run(create_app(settings), host="127.0.0.1", port=port, access_log=False)


if __name__ == "__main__":
    main()
