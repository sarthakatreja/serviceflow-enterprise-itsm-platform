from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UtcTimestamp
from .domain import AssetStatus, AssetType, Category, Priority, Role, TicketStatus, utcnow


def choices(enum):
    return Enum(
        enum, native_enum=False, create_constraint=True, validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    critical_hours: Mapped[int] = mapped_column(default=4)
    high_hours: Mapped[int] = mapped_column(default=8)
    medium_hours: Mapped[int] = mapped_column(default=24)
    low_hours: Mapped[int] = mapped_column(default=72)
    warning_hours: Mapped[int] = mapped_column(default=2)
    updated_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, onupdate=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[Role] = mapped_column(choices(Role), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, onupdate=utcnow)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcTimestamp(), index=True)
    user: Mapped[User] = relationship()


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[AssetType] = mapped_column(choices(AssetType), index=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[str] = mapped_column(String(100), default="")
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    location: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[AssetStatus] = mapped_column(choices(AssetStatus), index=True)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, onupdate=utcnow)
    assigned_user: Mapped[User | None] = relationship()


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_status_deadline", "status", "sla_deadline"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(choices(Category), index=True)
    priority: Mapped[Priority] = mapped_column(choices(Priority), index=True)
    status: Mapped[TicketStatus] = mapped_column(choices(TicketStatus), default=TicketStatus.OPEN)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, onupdate=utcnow)
    sla_deadline: Mapped[datetime] = mapped_column(UtcTimestamp())
    resolved_at: Mapped[datetime | None] = mapped_column(UtcTimestamp())
    archived_at: Mapped[datetime | None] = mapped_column(UtcTimestamp(), index=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    creator: Mapped[User] = relationship(foreign_keys=[creator_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    asset: Mapped[Asset | None] = relationship()

    __mapper_args__ = {"version_id_col": version}

    @property
    def number(self) -> str:
        return f"SF-{self.id:05d}"


class TicketResolution(Base):
    __tablename__ = "ticket_resolutions"
    __table_args__ = (UniqueConstraint("ticket_id", "resolved_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    resolver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime] = mapped_column(UtcTimestamp())
    resolver: Mapped[User | None] = relationship()


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow)
    author: Mapped[User] = relationship()


class TicketActivity(Base):
    __tablename__ = "ticket_activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(String(350))
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow)
    actor: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    entity: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[int | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(48), index=True)
    detail: Mapped[str] = mapped_column(String(350))
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp(), default=utcnow, index=True)
    actor: Mapped[User | None] = relationship()
