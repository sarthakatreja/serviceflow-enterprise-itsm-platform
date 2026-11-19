from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth import hash_password
from .common import workspace
from .demo_accounts import DEMO_PASSWORD, DEMO_SIGN_INS
from .domain import COMPLETED, AssetStatus, AssetType, Category, Priority, Role, TicketStatus, utcnow
from .models import Asset, AuditEvent, LoginSession, Ticket, TicketActivity, TicketComment, TicketResolution, User
from .policy import deadline

DEMO_USERS = [
    ("Maya Chen", DEMO_SIGN_INS[Role.ADMIN], Role.ADMIN),
    ("Nadia Patel", DEMO_SIGN_INS[Role.TECHNICIAN], Role.TECHNICIAN),
    ("Kai Nguyen", "kai@serviceflow.test", Role.TECHNICIAN),
    ("Jordan Ellis", "jordan@serviceflow.test", Role.TECHNICIAN),
    ("Olivia Brooks", DEMO_SIGN_INS[Role.EMPLOYEE], Role.EMPLOYEE),
    ("Alex Rivera", "alex@serviceflow.test", Role.EMPLOYEE),
    ("Priya Shah", "priya@serviceflow.test", Role.EMPLOYEE),
    ("Ethan Morris", "ethan@serviceflow.test", Role.EMPLOYEE),
]

ASSETS = [
    ("FIN-LT-014", "Finance operations laptop", "laptop", "Lenovo", "ThinkPad T14", 4, "Sydney · Finance", "in_use"),
    ("DES-LT-007", "Design work laptop", "laptop", "Dell", "Latitude 7450", 5, "Sydney · Design", "in_use"),
    ("OPS-DS-009", "Operations workstation", "desktop", "HP", "EliteDesk 800", 6, "Melbourne · Operations", "in_use"),
    ("PPL-MB-003", "People operations phone", "mobile", "Apple", "iPhone 15", 7, "Brisbane · People", "in_use"),
    ("SYD-NET-01", "Sydney core switch", "network_device", "Cisco", "Catalyst 9200", None, "Sydney · Network room", "in_use"),
    ("MEL-NET-02", "Melbourne wireless access point", "network_device", "Aruba", "AP-515", None, "Melbourne · Level 2", "maintenance"),
    ("SYD-SVR-02", "Identity services host", "server", "Dell", "PowerEdge R450", None, "Sydney · Data room", "in_use"),
    ("SYD-PR-04", "Level 4 shared printer", "printer", "Canon", "imageRUNNER C3326", None, "Sydney · Level 4", "in_use"),
    ("BRI-PR-01", "Reception label printer", "printer", "Zebra", "ZD421", None, "Brisbane · Reception", "maintenance"),
    ("STK-LT-012", "Spare service desk laptop", "laptop", "Lenovo", "ThinkPad T14", None, "Sydney · Stores", "in_stock"),
    ("OPS-LT-015", "Depot support laptop", "laptop", "Dell", "Latitude 5540", 7, "Brisbane · Depot", "in_use"),
    ("SEC-LT-005", "Security analyst laptop", "laptop", "Lenovo", "ThinkPad T14", 2, "Sydney · Service desk", "in_use"),
    ("MEL-DS-001", "Legacy reception desktop", "desktop", "HP", "ProDesk 600", None, "Melbourne · Stores", "retired"),
    ("SYD-MB-008", "Loan mobile phone", "mobile", "Samsung", "Galaxy A55", None, "Sydney · Stores", "in_stock"),
    ("MEL-LT-043", "Procurement laptop", "laptop", "HP", "EliteBook 840", 6, "Melbourne · Procurement", "in_use"),
    ("SYD-SVR-11", "Reporting file host", "server", "HPE", "ProLiant DL360", None, "Sydney · Data room", "in_use"),
]

ACTIVE = [
    ("VPN sign-in fails for finance team", "network", "critical", "in_progress", 3, 4, 1, 0),
    ("Intermittent Wi-Fi on Melbourne level 2", "network", "high", "assigned", 11, 6, 2, 5),
    ("MFA reset for payroll approval", "account_access", "high", "open", 7, 4, None, 0),
    ("Add a shared project mailbox", "email", "medium", "pending", 12, 5, 1, 1),
    ("Laptop fan runs continuously", "hardware", "medium", "open", 2, 5, None, 1),
    ("New starter needs design tools", "software", "medium", "open", 1.2, 7, None, 10),
    ("Endpoint protection reports an outdated client", "security", "critical", "in_progress", 6, 6, 3, 2),
    ("Replace damaged docking station", "hardware", "low", "pending", 77, 4, 1, 0),
    ("Provide read access to procurement drive", "account_access", "low", "assigned", 15, 6, 2, 14),
    ("Check identity sync warnings", "security", "high", "in_progress", 3.8, 6, 3, 6),
    ("Shared printer drops jobs from managed laptops", "hardware", "medium", "in_progress", 26, 5, 2, 7),
    ("Move meeting room laptop to new VLAN", "network", "low", "assigned", 48, 7, 2, 10),
    ("Install approved screen recording tool", "software", "low", "pending", 37, 5, 3, 1),
    ("Unable to send from group mailbox", "email", "medium", "open", 4, 4, None, 0),
    ("Review laptop replacement options", "general", "low", "open", 29, 6, None, 14),
    ("Incident notice banner missing", "software", "medium", "assigned", 20, 7, 1, None),
    ("Desktop shortcuts reset after sign-in", "software", "medium", "in_progress", 8, 6, 3, 2),
]
COMPLETED_TITLES = [
    ("Recover access to shared calendar", "email"),
    ("Restore reporting drive permissions", "account_access"),
    ("Replace failed laptop charger", "hardware"),
    ("Resolve branch DNS lookup errors", "network"),
    ("Roll out endpoint client update", "security"),
    ("Prepare two onboarding accounts", "account_access"),
    ("Repair spreadsheet add-in", "software"),
    ("Reconnect reception label printer", "hardware"),
    ("Reset managed phone enrolment", "general"),
    ("Verify suspicious mailbox rule", "security"),
    ("Recover archived email folder", "email"),
    ("Restore an offline network port", "network"),
    ("Reissue single sign-on registration", "account_access"),
    ("Update approved PDF editor", "software"),
    ("Replace cracked laptop screen", "hardware"),
    ("Stop duplicate meeting invitations", "email"),
    ("Reconcile lost-device inventory", "security"),
    ("Provision access to the training portal", "general"),
    ("Renew desktop certificate", "security"),
    ("Enable guest Wi-Fi for workshop", "network"),
    ("Remove crashed VPN profile", "network"),
]
COMPLETED_AGES = (10, 18, 25, 27, 30, 48, 50, 72, 78, 100, 104, 125, 142, 168, 190, 198, 223, 244, 273, 296, 319)
DESCRIPTIONS = {
    "VPN sign-in fails for finance team": (
        "Finance staff can reach the VPN sign-in page, but the connection disconnects after MFA approval. "
        "The issue affects three managed laptops and is blocking the month-end reconciliation. "
        "Please verify the VPN profile and identity sign-in logs."
    ),
    "Intermittent Wi-Fi on Melbourne level 2": (
        "Staff can join the corporate wireless network, but their devices lose connectivity "
        "during video calls. Desk connections on the same floor remain stable."
    ),
    "MFA reset for payroll approval": (
        "A replaced work phone is no longer registered for multifactor authentication. "
        "Payroll approval is due this afternoon. Please follow the approved identity verification process."
    ),
}


@dataclass(frozen=True)
class DemoTicket:
    title: str
    category: str
    priority: str
    status: str
    age: float
    requester: int
    technician: int | None
    asset: int | None
    resolution_hours: float = 0


def demo_records() -> list[DemoTicket]:
    records = [DemoTicket(*row) for row in ACTIVE]
    priorities = ("high", "medium", "low", "critical", "medium")
    for index, (title, category) in enumerate(COMPLETED_TITLES):
        priority = priorities[index % len(priorities)]
        resolved_after = (9 if priority in {"high", "critical"} else 28) if index in {0, 7, 13, 19} else 2.5
        records.append(DemoTicket(
            title, category, priority, "closed" if index % 3 == 2 else "resolved",
            COMPLETED_AGES[index], 4 + index % 4, 1 + index % 3, index % len(ASSETS),
            resolved_after,
        ))
    return records


def record_activity(db: Session, ticket: Ticket, actor: User, action: str, detail: str, when: datetime):
    db.add_all([
        TicketActivity(ticket_id=ticket.id, actor_id=actor.id, action=action, detail=detail, created_at=when),
        AuditEvent(actor_id=actor.id, entity="ticket", entity_id=ticket.id, action=action, detail=detail, created_at=when),
    ])


def seed_demo(db: Session) -> bool:
    config = workspace(db)
    if db.scalar(select(User.id).limit(1)) is not None:
        if config.demo:
            return False
        raise ValueError("This database already contains user accounts.")
    config.demo = True
    now = utcnow()
    onboarded = now - timedelta(days=60)
    users = [User(name=name, email=email, role=role, password_hash=hash_password(DEMO_PASSWORD),
                  created_at=onboarded, updated_at=onboarded) for name, email, role in DEMO_USERS]
    db.add_all(users)
    db.flush()
    inventory = [
        Asset(
            tag=tag, name=name, type=AssetType(kind), manufacturer=manufacturer, model=model,
            serial_number=f"DEMO-{index + 101:04d}", assigned_user=users[owner] if owner is not None else None,
            location=location, status=AssetStatus(status), purchase_date=(now - timedelta(days=250 + index * 11)).date(),
            notes="Fictional demonstration inventory record.", created_at=onboarded, updated_at=onboarded,
        )
        for index, (tag, name, kind, manufacturer, model, owner, location, status) in enumerate(ASSETS)
    ]
    db.add_all(inventory)
    db.flush()

    ordered = sorted(demo_records(), key=lambda row: -row.age)
    for row in ordered:
        priority, status = Priority(row.priority), TicketStatus(row.status)
        created = now - timedelta(hours=row.age)
        resolved = created + timedelta(hours=row.resolution_hours) if status in COMPLETED else None
        changed = resolved or (created + timedelta(minutes=20) if row.technician is not None else created)
        owner = users[row.requester]
        technician = users[row.technician] if row.technician is not None else None
        ticket = Ticket(
            title=row.title,
            description=DESCRIPTIONS.get(row.title, f"Support request to {row.title[0].lower() + row.title[1:]}. "
                                         "The requester has asked the service desk to confirm next steps."),
            category=Category(row.category), priority=priority, status=status, creator=owner,
            assignee=technician, asset=inventory[row.asset] if row.asset is not None else None,
            created_at=created, updated_at=changed, sla_deadline=deadline(created, priority, config),
            resolved_at=resolved,
            resolution_notes="Confirmed the corrective action with the requester and verified normal operation." if resolved else "",
        )
        db.add(ticket)
        db.flush()
        if resolved is not None:
            db.add(TicketResolution(ticket_id=ticket.id, resolver_id=technician.id if technician else None,
                                    notes=ticket.resolution_notes, resolved_at=resolved))
        record_activity(db, ticket, owner, "ticket.created", "Ticket opened.", created)
        if technician is not None:
            record_activity(db, ticket, users[0], "ticket.assigned",
                            f"Assigned to technician #{technician.id}.", created + timedelta(minutes=10))
            if status != TicketStatus.ASSIGNED:
                record_activity(db, ticket, technician, "ticket.status_changed",
                                f"Status updated to {status.value}.", changed)
            if status in (TicketStatus.IN_PROGRESS, TicketStatus.PENDING):
                db.add(TicketComment(
                    ticket_id=ticket.id, author=technician,
                    body="Initial checks are complete. I have contacted the requester for the next verification step.",
                    created_at=changed,
                ))
    db.flush()
    return True


def reset_demo(db: Session) -> None:
    config = workspace(db)
    if not config.demo:
        raise ValueError("Reset is only available for a database initialised with seed-demo.")
    for table in (AuditEvent, TicketActivity, TicketComment, TicketResolution, LoginSession, Ticket, Asset, User):
        db.execute(delete(table))
    config.critical_hours, config.high_hours, config.medium_hours, config.low_hours = 4, 8, 24, 72
    config.warning_hours = 2
    db.flush()
    seed_demo(db)
