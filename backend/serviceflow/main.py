from contextlib import asynccontextmanager
from pathlib import PurePosixPath

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import admin, analytics, assets, auth, tickets
from .auth import DB
from .config import Settings
from .db import Base, make_engine
from .models import Workspace
from .resolutions import import_legacy_resolutions


def initialize(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        if db.get(Workspace, 1) is None:
            db.add(Workspace(id=1))
        import_legacy_resolutions(db)


def fail(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            target = PurePosixPath(path.replace("\\", "/"))
            if error.status_code != 404 or target.parts[:1] == ("api",) or target.suffix:
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = make_engine(config.database_url)
        application.state.engine = engine
        try:
            initialize(engine)
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="ServiceFlow API", version="1.1.0", lifespan=lifespan,
        description="Ticket workflows, asset inventory, SLA reporting and administration.",
    )
    application.state.settings = config
    origins = set(config.origins)

    @application.middleware("http")
    async def protect_request(request: Request, call_next):
        origin = request.headers.get("origin")
        if (request.url.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and origin is not None and origin not in origins):
            response = fail(403, "This request origin is not allowed.")
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.add_middleware(
        CORSMiddleware, allow_origins=config.origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError):
        safe_errors = [{"loc": issue["loc"], "msg": issue["msg"]} for issue in error.errors()]
        return JSONResponse({"detail": safe_errors}, status_code=422)

    @application.exception_handler(IntegrityError)
    async def constraint_error(_request: Request, _error: IntegrityError):
        return fail(409, "A record with this identifier already exists or its reference changed.")

    @application.exception_handler(StaleDataError)
    async def concurrent_update(_request: Request, _error: StaleDataError):
        return fail(409, "The record changed. Refresh and try again.")

    @application.exception_handler(OperationalError)
    async def database_unavailable(_request: Request, _error: OperationalError):
        return fail(503, "The database is temporarily unavailable.")

    @application.get("/health", tags=["System"])
    def health(db: DB):
        db.scalar(select(1))
        return {"status": "ok"}

    for routes in (auth.router, tickets.router, assets.router, analytics.router, admin.router):
        application.include_router(routes)

    if config.frontend_dir is not None:
        application.mount("/", FrontendFiles(directory=config.frontend_dir, html=True), name="frontend")

    return application


app = create_app()
