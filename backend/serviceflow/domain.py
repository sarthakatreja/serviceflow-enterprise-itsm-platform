from datetime import datetime, timezone
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    TECHNICIAN = "technician"
    EMPLOYEE = "employee"


class TicketStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(StrEnum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    NETWORK = "network"
    ACCOUNT_ACCESS = "account_access"
    EMAIL = "email"
    SECURITY = "security"
    GENERAL = "general"


class AssetType(StrEnum):
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    SERVER = "server"
    NETWORK_DEVICE = "network_device"
    PRINTER = "printer"
    MOBILE = "mobile"


class AssetStatus(StrEnum):
    IN_USE = "in_use"
    IN_STOCK = "in_stock"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class SlaState(StrEnum):
    ON_TRACK = "on_track"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    MET = "met"
    BREACHED = "breached"


COMPLETED = (TicketStatus.RESOLVED, TicketStatus.CLOSED)
TRANSITIONS = {
    TicketStatus.OPEN: (TicketStatus.ASSIGNED,),
    TicketStatus.ASSIGNED: (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING),
    TicketStatus.IN_PROGRESS: (TicketStatus.PENDING, TicketStatus.RESOLVED),
    TicketStatus.PENDING: (TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED),
    TicketStatus.RESOLVED: (TicketStatus.IN_PROGRESS, TicketStatus.CLOSED),
    TicketStatus.CLOSED: (),
}
DEFAULT_SLA_HOURS = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 8,
    Priority.MEDIUM: 24,
    Priority.LOW: 72,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
