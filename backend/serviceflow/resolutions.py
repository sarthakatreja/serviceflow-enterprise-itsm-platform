from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .models import Ticket, TicketActivity, TicketResolution


def import_legacy_resolutions(db: Session) -> None:
    """Import the latest stored note when the earlier schema predates resolution history."""
    resolved_events = select(TicketActivity).where(
        TicketActivity.ticket_id == Ticket.id,
        TicketActivity.action == "ticket.status_changed",
        TicketActivity.detail.endswith(" to resolved."),
    )
    history_exists = select(TicketResolution.id).where(TicketResolution.ticket_id == Ticket.id).exists()
    missing = db.scalars(select(Ticket).where(
        ~history_exists, Ticket.resolution_notes != "",
        Ticket.resolved_at.is_not(None) | resolved_events.exists(),
    )).all()
    for ticket in missing:
        event = db.scalar(select(TicketActivity).where(
            TicketActivity.ticket_id == ticket.id,
            TicketActivity.action == "ticket.status_changed",
            TicketActivity.detail.endswith(" to resolved."),
        ).order_by(TicketActivity.created_at.desc(), TicketActivity.id.desc()).limit(1))
        if ticket.resolved_at is None and event is None:
            continue
        db.add(TicketResolution(
            ticket_id=ticket.id, notes=ticket.resolution_notes,
            resolver_id=event.actor_id if event is not None else None,
            resolved_at=ticket.resolved_at if ticket.resolved_at is not None else event.created_at,
        ))
        if ticket.resolved_at is None:
            ticket.resolution_notes = ""
            flag_modified(ticket, "updated_at")
