from typing import Annotated

from fastapi import APIRouter, Path
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from .auth import Admin, CurrentUser, DB, hash_password, revoke_sessions
from .common import Limit, Offset, QueryText, audit, paginate, reject, workspace
from .domain import COMPLETED, Role
from .models import AuditEvent, Ticket, User
from .schemas import AuditRead, Page, SlaSettings, UserCreate, UserPatch, UserRead, UserRef, WorkspaceRead

router = APIRouter(prefix="/api")
UserID = Annotated[int, Path(gt=0, le=2_147_483_647)]


@router.get("/users", response_model=Page[UserRead], tags=["Administration"])
def list_users(db: DB, user: Admin, search: QueryText = "", role: Role | None = None,
               limit: Limit = 20, offset: Offset = 0):
    statement = select(User)
    if term := search.strip().lower():
        statement = statement.where(or_(*(
            func.lower(field).contains(term, autoescape=True) for field in (User.name, User.email)
        )))
    if role is not None:
        statement = statement.where(User.role == role)
    rows, total = paginate(db, statement.order_by(User.name, User.id), limit, offset)
    return Page[UserRead](items=rows, total=total, limit=limit, offset=offset)


@router.get("/users/choices", response_model=Page[UserRef], tags=["Administration"])
def user_choices(db: DB, user: Admin, role: Role | None = None,
                 limit: Limit = 100, offset: Offset = 0):
    statement = select(User).where(User.active.is_(True))
    if role is not None:
        statement = statement.where(User.role == role)
    rows, count = paginate(db, statement.order_by(User.name, User.id), limit, offset)
    return Page[UserRef](items=rows, total=count, limit=limit, offset=offset)


@router.post("/users", status_code=201, response_model=UserRead, tags=["Administration"])
def create_user(data: UserCreate, db: DB, user: Admin):
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        reject(409, "This email is already registered.")
    record = User(name=data.name, email=data.email, role=data.role,
                  password_hash=hash_password(data.password.get_secret_value()))
    db.add(record)
    db.flush()
    audit(db, user, "user.created", "user", record.id, f"Created {record.role.value} account.")
    db.commit()
    return record


@router.patch("/users/{user_id}", response_model=UserRead, tags=["Administration"])
def update_user(user_id: UserID, data: UserPatch, db: DB, user: Admin):
    record = db.get(User, user_id)
    if record is None:
        reject(404, "User not found.")
    changes = data.model_dump(exclude_unset=True)
    changes = {key: value for key, value in changes.items()
               if key == "password" or getattr(record, key) != value}
    security_fields = {"role", "active", "password"} & changes.keys()
    if user.id == record.id and security_fields:
        reject(409, "Use Settings to change your password. Another administrator manages your role or status.")
    if record.role == Role.TECHNICIAN and (changes.get("active") is False or
                                          changes.get("role", record.role) != Role.TECHNICIAN):
        assigned = db.scalar(select(Ticket.id).where(
            Ticket.assignee_id == record.id, Ticket.status.not_in(COMPLETED),
        ).limit(1))
        if assigned is not None:
            reject(409, "Reassign this technician's active tickets first.")
    if changes:
        for key, value in changes.items():
            if key == "password":
                record.password_hash = hash_password(value.get_secret_value())
            else:
                setattr(record, key, value)
        if security_fields:
            revoke_sessions(db, record.id)
        fields = sorted("sign-in credential" if item == "password" else item for item in changes)
        audit(db, user, "user.updated", "user", record.id, "Updated " + ", ".join(fields) + ".")
        db.commit()
    return record


@router.get("/audit-logs", response_model=Page[AuditRead], tags=["Administration"])
def audit_logs(db: DB, user: Admin, entity: QueryText = "", limit: Limit = 30, offset: Offset = 0):
    statement = select(AuditEvent).options(joinedload(AuditEvent.actor))
    if entity:
        statement = statement.where(AuditEvent.entity == entity)
    rows, count = paginate(db, statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()), limit, offset)
    return Page[AuditRead](items=rows, total=count, limit=limit, offset=offset)


@router.get("/settings", response_model=WorkspaceRead, tags=["Settings"])
def read_settings(db: DB, user: CurrentUser):
    return workspace(db)


@router.put("/settings/sla", response_model=WorkspaceRead, tags=["Settings"])
def save_sla(data: SlaSettings, db: DB, user: Admin):
    config = workspace(db)
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    audit(db, user, "settings.sla_updated", "workspace", config.id, "SLA targets updated.")
    db.commit()
    return config
