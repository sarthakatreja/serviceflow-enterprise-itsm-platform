from datetime import datetime, timedelta
from math import floor

from .domain import Priority, SlaState
from .models import Ticket, Workspace


def deadline(start: datetime, priority: Priority, config: Workspace) -> datetime:
    return start + timedelta(hours=getattr(config, f"{priority.value}_hours"))


def sla_state(ticket: Ticket, now: datetime, warning_hours: int) -> SlaState:
    if ticket.resolved_at is not None:
        return SlaState.MET if ticket.resolved_at <= ticket.sla_deadline else SlaState.BREACHED
    if now > ticket.sla_deadline:
        return SlaState.OVERDUE
    if ticket.sla_deadline - now <= timedelta(hours=warning_hours):
        return SlaState.DUE_SOON
    return SlaState.ON_TRACK


def remaining_seconds(ticket: Ticket, now: datetime) -> int | None:
    if ticket.resolved_at is not None:
        return None
    return floor((ticket.sla_deadline - now).total_seconds())
