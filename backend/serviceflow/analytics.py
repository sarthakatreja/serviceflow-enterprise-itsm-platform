from collections import Counter, defaultdict
import csv
from datetime import datetime, time, timedelta, timezone
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from .assets import asset_scope
from .auth import Admin, CurrentUser, DB
from .common import workspace
from .domain import COMPLETED, AssetStatus, AssetType, Category, Priority, SlaState, TicketStatus, utcnow
from .models import Asset, Ticket
from .policy import sla_state
from .schemas import Dashboard, DayCount, Metrics, ReportFilters, Workload
from .tickets import present, ticket_scope, with_details

router = APIRouter(prefix="/api", tags=["Analytics"])
Filters = Annotated[ReportFilters, Query()]


def report_statement(filters: ReportFilters):
    statement = select(Ticket).where(Ticket.archived_at.is_(None))
    if filters.start is not None:
        statement = statement.where(Ticket.created_at >= datetime.combine(filters.start, time.min, timezone.utc))
    if filters.end is not None:
        statement = statement.where(
            Ticket.created_at < datetime.combine(filters.end + timedelta(days=1), time.min, timezone.utc),
        )
    if filters.priority is not None:
        statement = statement.where(Ticket.priority == filters.priority)
    if filters.status is not None:
        statement = statement.where(Ticket.status == filters.status)
    return with_details(statement.order_by(Ticket.created_at.desc(), Ticket.id.desc()))


def count_by(rows, field, enum):
    counts = Counter(getattr(row, field) for row in rows)
    return {key: counts[key] for key in enum}


def build_metrics(tickets: list[Ticket], assets: list[Asset], now: datetime, warning_hours: int) -> Metrics:
    statuses = count_by(tickets, "status", TicketStatus)
    priorities = count_by(tickets, "priority", Priority)
    sla_counts = Counter(sla_state(ticket, now, warning_hours) for ticket in tickets)
    resolved = [ticket for ticket in tickets if ticket.resolved_at is not None]
    completed = len(resolved)
    assigned = defaultdict(list)
    names = {None: "Unassigned"}
    for ticket in tickets:
        assigned[ticket.assignee_id].append(ticket)
        if ticket.assignee is not None:
            names[ticket.assignee_id] = ticket.assignee.name

    workload = [
        Workload(
            id=user_id, name=names[user_id],
            active=sum(ticket.status not in COMPLETED for ticket in group),
            resolved=sum(ticket.status in COMPLETED for ticket in group),
        ) for user_id, group in assigned.items()
    ]
    workload.sort(key=lambda row: (-row.active, row.name))
    start = now.date() - timedelta(days=13)
    created_dates = Counter(ticket.created_at.date() for ticket in tickets)
    resolved_dates = Counter(ticket.resolved_at.date() for ticket in resolved)
    activity = [DayCount(date=day, created=created_dates[day], resolved=resolved_dates[day])
                for day in (start + timedelta(days=index) for index in range(14))]

    return Metrics(
        total=len(tickets), open=statuses[TicketStatus.OPEN], in_progress=statuses[TicketStatus.IN_PROGRESS],
        resolved=completed,
        critical=sum(ticket.priority == Priority.CRITICAL and ticket.status not in COMPLETED for ticket in tickets),
        due_soon=sla_counts[SlaState.DUE_SOON], overdue=sla_counts[SlaState.OVERDUE],
        assets=len(assets), sla_met=sla_counts[SlaState.MET], sla_late=sla_counts[SlaState.BREACHED],
        sla_breaches=sla_counts[SlaState.BREACHED] + sla_counts[SlaState.OVERDUE],
        compliance=round(sla_counts[SlaState.MET] * 100 / completed, 1) if completed else None,
        average_resolution_hours=round(
            sum((ticket.resolved_at - ticket.created_at).total_seconds() for ticket in resolved)
            / completed / 3600, 1,
        ) if completed else None,
        by_status=statuses, by_priority=priorities, by_category=count_by(tickets, "category", Category),
        assets_by_type=count_by(assets, "type", AssetType),
        assets_by_status=count_by(assets, "status", AssetStatus),
        workload=workload, activity=activity,
    )


@router.get("/dashboard/summary", response_model=Dashboard)
def dashboard(db: DB, user: CurrentUser):
    config = workspace(db)
    now = utcnow()
    tickets = list(db.scalars(with_details(
        select(Ticket).where(ticket_scope(user)).order_by(Ticket.updated_at.desc(), Ticket.id.desc()),
    )))
    assets = list(db.scalars(select(Asset).where(asset_scope(user))))
    return Dashboard(
        **build_metrics(tickets, assets, now, config.warning_hours).model_dump(),
        recent=[present(ticket, now, config.warning_hours) for ticket in tickets[:6]],
    )


@router.get("/reports", response_model=Metrics)
def reports(db: DB, user: Admin, filters: Filters):
    tickets = list(db.scalars(report_statement(filters)))
    assets = list(db.scalars(select(Asset)))
    return build_metrics(tickets, assets, utcnow(), workspace(db).warning_hours)


def csv_cell(text: str) -> str:
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠")):
        return "'" + text
    return text


@router.get("/reports/export", response_class=Response, responses={
    200: {"content": {"text/csv": {"schema": {"type": "string"}}}},
})
def export_report(db: DB, user: Admin, filters: Filters):
    ticket_rows = db.scalars(report_statement(filters))
    now = utcnow()
    warning_hours = workspace(db).warning_hours
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow([
        "Ticket", "Title", "Category", "Priority", "Status", "Requester", "Assigned technician",
        "Asset", "Created (UTC)", "Updated (UTC)", "SLA deadline (UTC)", "SLA outcome", "Resolved (UTC)",
    ])
    for ticket in ticket_rows:
        writer.writerow([
            ticket.number, csv_cell(ticket.title), ticket.category.value, ticket.priority.value, ticket.status.value,
            csv_cell(ticket.creator.name), csv_cell(ticket.assignee.name) if ticket.assignee is not None else "",
            csv_cell(ticket.asset.tag) if ticket.asset is not None else "", ticket.created_at.isoformat(),
            ticket.updated_at.isoformat(), ticket.sla_deadline.isoformat(),
            sla_state(ticket, now, warning_hours).value,
            ticket.resolved_at.isoformat() if ticket.resolved_at is not None else "",
        ])
    return Response(
        buffer.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="serviceflow-ticket-report.csv"'},
    )
