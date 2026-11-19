from typing import Annotated

from fastapi import HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AuditEvent, User, Workspace

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]
QueryText = Annotated[str, Query(max_length=120)]


def reject(status: int, detail: str) -> None:
    raise HTTPException(status_code=status, detail=detail)


def workspace(db: Session) -> Workspace:
    return db.get(Workspace, 1)


def paginate(db: Session, statement, limit: int, offset: int):
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.offset(offset).limit(limit)).all()
    return rows, count


def audit(
    db: Session, actor: User | None, action: str, entity: str, entity_id: int | None, detail: str,
) -> None:
    db.add(AuditEvent(
        actor_id=actor.id if actor is not None else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        detail=detail,
    ))
