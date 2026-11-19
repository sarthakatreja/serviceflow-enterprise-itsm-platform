from datetime import date, datetime
from typing import Annotated, ClassVar, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator

from .domain import AssetStatus, AssetType, Category, Priority, Role, SlaState, TicketStatus


Email = Annotated[str, StringConstraints(
    strip_whitespace=True, to_lower=True, max_length=254,
    pattern=r"(?i)^[a-z0-9.!#$%&'*+/=?^_+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+$",
)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=160)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=8000)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
AssetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
AssetTag = Annotated[str, StringConstraints(
    strip_whitespace=True, to_upper=True, pattern=r"(?i)^[a-z0-9][a-z0-9_-]{1,39}$",
)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Ref = Annotated[int, Field(gt=0, le=2_147_483_647)]
Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]

T = TypeVar("T")


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatchBody(Body):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def check_changes(self):
        for name in self.model_fields_set - self.nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to update.")
        return self


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class LoginBody(Body):
    email: Email
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class DemoLoginBody(Body):
    role: Role


class UserRef(ReadModel):
    id: int
    name: str


class UserRead(UserRef):
    email: str
    role: Role
    active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(Body):
    name: Name
    email: Email
    role: Role
    password: Password


class UserPatch(PatchBody):
    name: Name | None = None
    role: Role | None = None
    active: bool | None = None
    password: Password | None = None


class PasswordChange(Body):
    current_password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    new_password: Password


class AssetCreate(Body):
    tag: AssetTag
    name: AssetName
    type: AssetType
    manufacturer: Name
    model: AssetName
    serial_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    assigned_user_id: Ref | None = None
    location: ShortText = ""
    status: AssetStatus = AssetStatus.IN_STOCK
    purchase_date: date | None = None
    notes: Notes = ""


class AssetPatch(PatchBody):
    nullable_fields = frozenset({"assigned_user_id", "purchase_date"})

    tag: AssetTag | None = None
    name: AssetName | None = None
    type: AssetType | None = None
    manufacturer: Name | None = None
    model: AssetName | None = None
    serial_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    assigned_user_id: Ref | None = None
    location: ShortText | None = None
    status: AssetStatus | None = None
    purchase_date: date | None = None
    notes: Notes | None = None


class AssetRef(ReadModel):
    id: int
    tag: str
    name: str


class AssetRead(AssetRef):
    type: AssetType
    manufacturer: str
    model: str
    serial_number: str
    assigned_user: UserRef | None
    location: str
    status: AssetStatus
    purchase_date: date | None
    notes: str
    created_at: datetime
    updated_at: datetime


class TicketCreate(Body):
    title: Title
    description: Description
    category: Category
    priority: Priority = Priority.MEDIUM
    asset_id: Ref | None = None


class TicketPatch(PatchBody):
    nullable_fields = frozenset({"asset_id", "assignee_id"})

    version: Ref | None = None
    title: Title | None = None
    description: Description | None = None
    category: Category | None = None
    priority: Priority | None = None
    status: TicketStatus | None = None
    asset_id: Ref | None = None
    assignee_id: Ref | None = None
    resolution_notes: Notes | None = None


class TicketRead(ReadModel):
    id: int
    number: str
    version: int
    title: str
    description: str
    category: Category
    priority: Priority
    status: TicketStatus
    creator: UserRef
    assignee: UserRef | None
    asset: AssetRef | None
    created_at: datetime
    updated_at: datetime
    sla_deadline: datetime
    resolved_at: datetime | None
    archived_at: datetime | None
    resolution_notes: str
    sla_state: SlaState
    remaining_seconds: int | None


class CommentCreate(Body):
    body: CommentBody


class CommentRead(ReadModel):
    id: int
    author: UserRef
    body: str
    created_at: datetime


class ActivityRead(ReadModel):
    id: int
    actor: UserRef
    action: str
    detail: str
    created_at: datetime


class ResolutionRead(ReadModel):
    id: int
    resolver: UserRef | None
    notes: str
    resolved_at: datetime


class TicketDetail(TicketRead):
    comments: list[CommentRead]
    activity: list[ActivityRead]
    allowed_transitions: list[TicketStatus]
    resolution_history: list[ResolutionRead]


class TicketSlaRead(BaseModel):
    version: int
    sla_state: SlaState
    remaining_seconds: int | None


class AuditRead(ReadModel):
    id: int
    actor: UserRef | None
    entity: str
    entity_id: int | None
    action: str
    detail: str
    created_at: datetime


Hours = Annotated[int, Field(strict=True, ge=1, le=720)]


class SlaSettings(Body):
    critical_hours: Hours
    high_hours: Hours
    medium_hours: Hours
    low_hours: Hours
    warning_hours: Hours

    @model_validator(mode="after")
    def check_targets(self):
        if not self.critical_hours <= self.high_hours <= self.medium_hours <= self.low_hours:
            raise ValueError("Targets must increase from Critical to Low priority.")
        if self.warning_hours > self.critical_hours:
            raise ValueError("The warning window cannot exceed the Critical target.")
        return self


class WorkspaceRead(SlaSettings):
    model_config = ConfigDict(from_attributes=True)
    demo: bool


class AuthContext(BaseModel):
    demo: bool


class DayCount(BaseModel):
    date: date
    created: int
    resolved: int


class Workload(BaseModel):
    id: int | None
    name: str
    active: int
    resolved: int


class Metrics(BaseModel):
    total: int
    open: int
    in_progress: int
    resolved: int
    critical: int
    due_soon: int
    overdue: int
    assets: int
    sla_met: int
    sla_late: int
    sla_breaches: int
    compliance: float | None
    average_resolution_hours: float | None
    by_status: dict[TicketStatus, int]
    by_priority: dict[Priority, int]
    by_category: dict[Category, int]
    assets_by_type: dict[AssetType, int]
    assets_by_status: dict[AssetStatus, int]
    workload: list[Workload]
    activity: list[DayCount]


class Dashboard(Metrics):
    recent: list[TicketRead]


SortOrder = Literal["updated", "newest", "oldest", "priority", "deadline"]


class ReportFilters(BaseModel):
    start: date | None = None
    end: date | None = None
    priority: Priority | None = None
    status: TicketStatus | None = None

    @model_validator(mode="after")
    def check_date_range(self):
        if self.start and self.end and self.end < self.start:
            raise ValueError("End date must be on or after the start date.")
        if self.end == date.max:
            raise ValueError("End date is out of range.")
        return self
