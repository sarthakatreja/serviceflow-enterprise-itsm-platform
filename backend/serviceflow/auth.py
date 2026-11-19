from datetime import timedelta
from hashlib import sha256
import secrets
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .common import audit, reject, workspace
from .db import get_db
from .demo_accounts import DEMO_PASSWORD, DEMO_SIGN_INS
from .domain import Role, utcnow
from .models import LoginSession, User
from .schemas import AuthContext, DemoLoginBody, LoginBody, PasswordChange, UserRead

SESSION_COOKIE = "serviceflow_session"
cookie_scheme = APIKeyCookie(name=SESSION_COOKIE, auto_error=False, scheme_name="SessionCookie")
hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))

DB = Annotated[Session, Depends(get_db)]
Cookie = Annotated[str | None, Depends(cookie_scheme)]
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def session_from(db: Session, token: str | None) -> LoginSession | None:
    if token is None or len(token) != 43 or not token.isascii():
        return None
    row = db.get(LoginSession, digest(token))
    if row is None or row.expires_at <= utcnow() or not row.user.active:
        return None
    return row


def current_user(db: DB, token: Cookie) -> User:
    row = session_from(db, token)
    if row is None:
        reject(401, "Sign in to continue.")
    return row.user


CurrentUser = Annotated[User, Depends(current_user)]


def admin_user(user: CurrentUser) -> User:
    if user.role != Role.ADMIN:
        reject(403, "Administrator access is required.")
    return user


Admin = Annotated[User, Depends(admin_user)]


def revoke_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))


def clear_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, samesite="strict",
        secure=request.app.state.settings.cookie_secure,
    )


@router.get("/context", response_model=AuthContext)
def login_context(db: DB):
    return AuthContext(demo=workspace(db).demo)


def start_session(user: User | None, password: str, request: Request, response: Response,
                  db: Session, token: str | None) -> User:
    matches = verify_password(user.password_hash if user is not None else dummy_hash, password)
    if user is None or not user.active or not matches:
        audit(db, None, "auth.login_failed", "session", None, "Credentials were rejected.")
        db.commit()
        reject(401, "Email or password is incorrect.")

    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    old_session = session_from(db, token)
    if old_session is not None:
        db.delete(old_session)
    key = secrets.token_urlsafe(32)
    now = utcnow()
    duration = timedelta(hours=request.app.state.settings.session_hours)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    db.add(LoginSession(token_hash=digest(key), user_id=user.id, expires_at=now + duration))
    audit(db, user, "auth.login", "user", user.id, "Signed in.")
    db.commit()
    response.set_cookie(
        SESSION_COOKIE, key, max_age=int(duration.total_seconds()), httponly=True,
        secure=request.app.state.settings.cookie_secure, samesite="strict", path="/",
    )
    return user


@router.post("/login", response_model=UserRead)
def login(data: LoginBody, request: Request, response: Response, db: DB, token: Cookie):
    user = db.scalar(select(User).where(User.email == data.email))
    return start_session(user, data.password.get_secret_value(), request, response, db, token)


@router.post("/demo", response_model=UserRead)
def demo_login(data: DemoLoginBody, request: Request, response: Response, db: DB, token: Cookie):
    if not workspace(db).demo:
        reject(404, "The demo workspace is unavailable.")
    user = db.scalar(select(User).where(User.email == DEMO_SIGN_INS[data.role], User.role == data.role))
    return start_session(user, DEMO_PASSWORD, request, response, db, token)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB, token: Cookie):
    entry = session_from(db, token)
    if entry is not None:
        audit(db, entry.user, "auth.logout", "user", entry.user_id, "Signed out.")
        db.delete(entry)
        db.commit()
    clear_cookie(request, response)


@router.post("/password", status_code=204)
def change_password(data: PasswordChange, request: Request, response: Response, db: DB, user: CurrentUser):
    if not verify_password(user.password_hash, data.current_password.get_secret_value()):
        reject(400, "Current password is incorrect.")
    user.password_hash = hash_password(data.new_password.get_secret_value())
    revoke_sessions(db, user.id)
    audit(db, user, "auth.password_changed", "user", user.id, "Password changed. Sessions revoked.")
    db.commit()
    clear_cookie(request, response)
