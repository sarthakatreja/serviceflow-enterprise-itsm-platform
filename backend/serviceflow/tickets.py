from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from .auth import Admin, CurrentUser, DB
from .common import Limit, Offset, QueryText, audit, paginate, reject, workspace
from .domain import COMPLETED, TRANSITIONS, Category, Priority, Role, SlaState, TicketStatus, utcnow
from .models import Asset, Ticket, TicketActivity, TicketComment, TicketResolution, User, Workspace
from .policy import deadline, remaining_seconds, sla_state
from .schemas import (
    ActivityRead, CommentCreate, CommentRead, Page, ResolutionRead, SortOrder, TicketCreate, TicketDetail,
    TicketPatch, TicketRead, TicketSlaRead,
)

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])
TicketID = Annotated[int, Path(gt=0, le=2_147_483_647)]
EMPLOYEE_FIELDS = {"title", "description", "category", "asset_id"}
TECHNICIAN_FIELDS = {"status", "resolution_notes"}


def ticket_scope(user: User, own: bool = False, archived: bool = False):
    record_state = Ticket.archived_at.is_not(None) if archived else Ticket.archived_at.is_(None)
    if user.role == Role.TECHNICIAN:
        return record_state & (Ticket.assignee_id == user.id)
    if user.role == Role.EMPLOYEE or own:
        return record_state & (Ticket.creator_id == user.id)
    return record_state


def with_details(statement):
    return statement.options(joinedload(Ticket.creator), joinedload(Ticket.assignee), joinedload(Ticket.asset))


def get_ticket(db: Session, actor: User, ticket_id: int, include_archived: bool = False) -> Ticket:
    scope = True if include_archived and actor.role == Role.ADMIN else ticket_scope(actor)
    ticket = db.scalar(with_details(select(Ticket).where(Ticket.id == ticket_id, scope)))
    if ticket is None:
        reject(404, "Ticket not found.")
    return ticket


def present(ticket: Ticket, now: datetime, warning_hours: int) -> TicketRead:
    return TicketRead(
        id=ticket.id, number=ticket.number, version=ticket.version,
        title=ticket.title, description=ticket.description, category=ticket.category,
        priority=ticket.priority, status=ticket.status, creator=ticket.creator,
        assignee=ticket.assignee, asset=ticket.asset, created_at=ticket.created_at,
        updated_at=ticket.updated_at, sla_deadline=ticket.sla_deadline,
        resolved_at=ticket.resolved_at, archived_at=ticket.archived_at, resolution_notes=ticket.resolution_notes,
        sla_state=sla_state(ticket, now, warning_hours),
        remaining_seconds=remaining_seconds(ticket, now),
    )


def transitions(ticket: Ticket, actor: User) -> list[TicketStatus]:
    if actor.role == Role.EMPLOYEE:
        return []
    options = TRANSITIONS[ticket.status]
    if actor.role == Role.TECHNICIAN:
        return [state for state in options if state not in (TicketStatus.OPEN, TicketStatus.CLOSED)]
    return list(options)


def detail_view(db: Session, ticket: Ticket, actor: User, config: Workspace) -> TicketDetail:
    comments = db.scalars(select(TicketComment).where(TicketComment.ticket_id == ticket.id)
                          .options(joinedload(TicketComment.author))
                          .order_by(TicketComment.created_at, TicketComment.id)).all()
    activity = db.scalars(select(TicketActivity).where(TicketActivity.ticket_id == ticket.id)
                          .options(joinedload(TicketActivity.actor))
                          .order_by(TicketActivity.created_at.desc(), TicketActivity.id.desc())).all()
    history = db.scalars(select(TicketResolution).where(TicketResolution.ticket_id == ticket.id)
                         .options(joinedload(TicketResolution.resolver))
                         .order_by(TicketResolution.resolved_at.desc(), TicketResolution.id.desc())).all()
    return TicketDetail(
        **present(ticket, utcnow(), config.warning_hours).model_dump(),
        comments=[CommentRead.model_validate(entry) for entry in comments],
        activity=[ActivityRead.model_validate(entry) for entry in activity],
        resolution_history=[ResolutionRead.model_validate(entry) for entry in history],
        allowed_transitions=transitions(ticket, actor),
    )


def log_activity(db: Session, ticket: Ticket, actor: User, action: str, detail: str) -> None:
    db.add(TicketActivity(ticket_id=ticket.id, actor_id=actor.id, action=action, detail=detail))
    audit(db, actor, action, "ticket", ticket.id, detail)


def validate_asset(db: Session, actor: User, asset_id: int | None) -> None:
    if asset_id is None:
        return
    asset = db.get(Asset, asset_id)
    if asset is None or (actor.role == Role.EMPLOYEE and asset.assigned_user_id != actor.id):
        reject(404, "Asset not found.")


def filter_sla(statement, kind: SlaState, now: datetime, warning_hours: int):
    cutoff = now + timedelta(hours=warning_hours)
    predicates = {
        SlaState.ON_TRACK: (Ticket.resolved_at.is_(None), Ticket.sla_deadline > cutoff),
        SlaState.DUE_SOON: (Ticket.resolved_at.is_(None), Ticket.sla_deadline >= now, Ticket.sla_deadline <= cutoff),
        SlaState.OVERDUE: (Ticket.resolved_at.is_(None), Ticket.sla_deadline < now),
        SlaState.MET: (Ticket.resolved_at.is_not(None), Ticket.resolved_at <= Ticket.sla_deadline),
        SlaState.BREACHED: (Ticket.resolved_at.is_not(None), Ticket.resolved_at > Ticket.sla_deadline),
    }
    return statement.where(*predicates[kind])


@router.get("", response_model=Page[TicketRead])
def list_tickets(
    db: DB, user: CurrentUser, search: QueryText = "", status: TicketStatus | None = None,
    priority: Priority | None = None, category: Category | None = None, sla: SlaState | None = None,
    scope: Literal["visible", "mine"] = "visible", sort: SortOrder = "updated",
    limit: Limit = 20, offset: Offset = 0, archived: bool = False,
):
    if archived and user.role != Role.ADMIN:
        reject(403, "Only administrators can view archived tickets.")
    now = utcnow()
    config = workspace(db)
    statement = select(Ticket).where(ticket_scope(user, own=scope == "mine", archived=archived))
    if term := search.strip().lower():
        search_fields = [func.lower(field).contains(term, autoescape=True)
                         for field in (Ticket.title, Ticket.description)]
        identifier = term.removeprefix("sf-")
        if identifier.isascii() and identifier.isdecimal() and len(identifier) <= 10:
            search_fields.append(Ticket.id == int(identifier))
        statement = statement.where(or_(*search_fields))
    if status is not None:
        statement = statement.where(Ticket.status == status)
    if priority is not None:
        statement = statement.where(Ticket.priority == priority)
    if category is not None:
        statement = statement.where(Ticket.category == category)
    if sla is not None:
        statement = filter_sla(statement, sla, now, config.warning_hours)

    ordering = {
        "updated": Ticket.updated_at.desc(),
        "newest": Ticket.created_at.desc(),
        "oldest": Ticket.created_at.asc(),
        "priority": case({value.value: rank for rank, value in enumerate(Priority)}, value=Ticket.priority),
        "deadline": Ticket.sla_deadline.asc(),
    }
    items, total = paginate(db, with_details(statement.order_by(ordering[sort], Ticket.id.desc())), limit, offset)
    return Page[TicketRead](
        items=[present(item, now, config.warning_hours) for item in items],
        total=total, limit=limit, offset=offset,
    )


@router.post("", status_code=201, response_model=TicketDetail)
def create_ticket(data: TicketCreate, db: DB, user: CurrentUser):
    if user.role == Role.TECHNICIAN:
        reject(403, "Technicians work tickets assigned to their queue.")
    validate_asset(db, user, data.asset_id)
    config = workspace(db)
    now = utcnow()
    ticket = Ticket(
        **data.model_dump(), creator_id=user.id, status=TicketStatus.OPEN, created_at=now,
        updated_at=now, sla_deadline=deadline(now, data.priority, config),
    )
    db.add(ticket)
    db.flush()
    log_activity(db, ticket, user, "ticket.created", "Ticket opened.")
    db.commit()
    return detail_view(db, ticket, user, config)


@router.get("/{ticket_id}", response_model=TicketDetail)
def read_ticket(ticket_id: TicketID, db: DB, user: CurrentUser):
    return detail_view(db, get_ticket(db, user, ticket_id, include_archived=True), user, workspace(db))


@router.get("/{ticket_id}/sla", response_model=TicketSlaRead)
def read_ticket_sla(ticket_id: TicketID, db: DB, user: CurrentUser):
    ticket = get_ticket(db, user, ticket_id, include_archived=True)
    now = utcnow()
    return TicketSlaRead(version=ticket.version, sla_state=sla_state(ticket, now, workspace(db).warning_hours),
                         remaining_seconds=remaining_seconds(ticket, now))


@router.delete("/{ticket_id}", status_code=204)
def archive_ticket(ticket_id: TicketID, db: DB, user: Admin):
    """Soft-delete a closed ticket while retaining its activity and audit records."""
    ticket = get_ticket(db, user, ticket_id, include_archived=True)
    if ticket.status != TicketStatus.CLOSED:
        reject(409, "Close the ticket before archiving it.")
    if ticket.archived_at is None:
        ticket.archived_at = utcnow()
        log_activity(db, ticket, user, "ticket.archived", "Closed ticket archived.")
        db.commit()


@router.post("/{ticket_id}/restore", response_model=TicketDetail)
def restore_ticket(ticket_id: TicketID, db: DB, user: Admin):
    ticket = get_ticket(db, user, ticket_id, include_archived=True)
    if ticket.archived_at is not None:
        ticket.archived_at = None
        log_activity(db, ticket, user, "ticket.restored", "Ticket restored to the closed queue.")
        db.commit()
    return detail_view(db, ticket, user, workspace(db))


def get_changes(ticket: Ticket, data: TicketPatch, user: User) -> dict:
    changes = data.model_dump(exclude_unset=True)
    version = changes.pop("version", None)
    if not changes:
        reject(422, "Supply at least one ticket field to update.")
    if version is not None and version != ticket.version:
        reject(409, "This ticket changed. Refresh it before editing.")
    if ticket.status == TicketStatus.CLOSED:
        reject(409, "Closed tickets cannot be edited.")
    if user.role == Role.EMPLOYEE:
        if not changes.keys() <= EMPLOYEE_FIELDS or ticket.status != TicketStatus.OPEN:
            reject(403, "Employees can edit the details of their own open tickets.")
    if user.role == Role.TECHNICIAN and not changes.keys() <= TECHNICIAN_FIELDS:
        reject(403, "Technicians can update status and resolution notes.")
    return {name: value for name, value in changes.items() if value != getattr(ticket, name)}


def apply_assignment(db: Session, ticket: Ticket, changes: dict) -> int | None:
    if "assignee_id" not in changes:
        return ticket.assignee_id
    if ticket.status in COMPLETED:
        reject(409, "Reopen the ticket before changing its assignment.")
    assignee = changes["assignee_id"]
    if assignee is not None:
        technician = db.get(User, assignee)
        if technician is None or technician.role != Role.TECHNICIAN or not technician.active:
            reject(422, "Choose an active technician.")
        if ticket.status == TicketStatus.OPEN:
            changes.setdefault("status", TicketStatus.ASSIGNED)
    elif ticket.status == TicketStatus.ASSIGNED:
        changes.setdefault("status", TicketStatus.OPEN)
    else:
        reject(409, "Assign a replacement technician for a ticket already being worked.")
    return assignee


def apply_transition(db: Session, ticket: Ticket, user: User, changes: dict,
                     assignee: int | None, now: datetime) -> None:
    next_status = changes.get("status", ticket.status)
    if next_status == TicketStatus.OPEN and assignee is not None:
        reject(409, "Clear the assignment to return a ticket to Open.")
    if next_status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.PENDING) and assignee is None:
        reject(409, "Assign a technician before moving to this status.")
    if "status" in changes and next_status not in transitions(ticket, user):
        reject(409, f"Cannot move from {ticket.status.value} to {next_status.value}.")
    if changes.get("status") == TicketStatus.RESOLVED:
        notes = changes.get("resolution_notes", ticket.resolution_notes)
        if not notes.strip():
            reject(422, "Add new resolution notes for this resolution.")
        db.add(TicketResolution(ticket_id=ticket.id, resolver_id=user.id, notes=notes, resolved_at=now))
        ticket.resolved_at = now
    elif next_status in COMPLETED:
        if not changes.get("resolution_notes", ticket.resolution_notes):
            reject(422, "Resolution notes are required on completed tickets.")
        if "resolution_notes" in changes:
            entry = db.scalar(select(TicketResolution).where(
                TicketResolution.ticket_id == ticket.id, TicketResolution.resolved_at == ticket.resolved_at,
            ))
            if entry is not None:
                entry.notes = changes["resolution_notes"]
    elif ticket.status in COMPLETED:
        ticket.resolved_at = None
        if changes.get("resolution_notes", ticket.resolution_notes):
            changes["resolution_notes"] = ""


@router.patch("/{ticket_id}", response_model=TicketDetail)
def update_ticket(ticket_id: TicketID, data: TicketPatch, db: DB, user: CurrentUser):
    ticket = get_ticket(db, user, ticket_id)
    config = workspace(db)
    changes = get_changes(ticket, data, user)
    if not changes:
        return detail_view(db, ticket, user, config)

    if "asset_id" in changes:
        validate_asset(db, user, changes["asset_id"])
    if "priority" in changes and ticket.status in COMPLETED:
        reject(409, "Reopen the ticket before changing its priority.")

    assignee = apply_assignment(db, ticket, changes)
    now = utcnow()
    apply_transition(db, ticket, user, changes, assignee, now)

    if "status" in changes:
        log_activity(db, ticket, user, "ticket.status_changed",
                     f"Status changed from {ticket.status.value} to {changes['status'].value}.")
    if "assignee_id" in changes:
        description = f"Assigned to technician #{assignee}." if assignee is not None else "Assignment removed."
        log_activity(db, ticket, user, "ticket.assigned", description)
    if "priority" in changes:
        log_activity(db, ticket, user, "ticket.priority_changed",
                     f"Priority changed from {ticket.priority.value} to {changes['priority'].value}.")
        ticket.sla_deadline = deadline(ticket.created_at, changes["priority"], config)
    if fields := changes.keys() - {"status", "assignee_id", "priority"}:
        log_activity(db, ticket, user, "ticket.updated", "Updated " + ", ".join(sorted(fields)) + ".")
    for key, value in changes.items():
        setattr(ticket, key, value)
    ticket.updated_at = now
    db.commit()
    db.expire(ticket, ["assignee", "asset"])
    return detail_view(db, ticket, user, config)


@router.post("/{ticket_id}/comments", status_code=201, response_model=CommentRead)
def add_comment(ticket_id: TicketID, data: CommentCreate, db: DB, user: CurrentUser):
    ticket = get_ticket(db, user, ticket_id)
    if ticket.status == TicketStatus.CLOSED:
        reject(409, "Closed tickets cannot receive comments.")
    comment = TicketComment(ticket_id=ticket.id, author=user, body=data.body)
    db.add(comment)
    ticket.updated_at = utcnow()
    log_activity(db, ticket, user, "ticket.comment_added", "Comment added.")
    db.commit()
    return comment
