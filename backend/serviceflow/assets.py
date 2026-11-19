from typing import Annotated

from fastapi import APIRouter, Path
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from .auth import Admin, CurrentUser, DB
from .common import Limit, Offset, QueryText, audit, paginate, reject
from .domain import AssetStatus, AssetType, Role
from .models import Asset, Ticket, User
from .schemas import AssetCreate, AssetPatch, AssetRead, AssetRef, Page

router = APIRouter(prefix="/api/assets", tags=["Assets"])
AssetID = Annotated[int, Path(gt=0, le=2_147_483_647)]


def asset_scope(actor: User):
    if actor.role == Role.EMPLOYEE:
        return Asset.assigned_user_id == actor.id
    if actor.role == Role.TECHNICIAN:
        return Asset.id.in_(select(Ticket.asset_id).where(Ticket.assignee_id == actor.id, Ticket.archived_at.is_(None)))
    return True


def require_inventory_access(actor: User) -> None:
    if actor.role == Role.EMPLOYEE:
        reject(403, "Asset inventory is available to service desk staff.")


def find_asset(db, actor: User, asset_id: int) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, asset_scope(actor))
                      .options(joinedload(Asset.assigned_user)))
    if asset is None:
        reject(404, "Asset not found.")
    return asset


def validate_owner(db, owner_id: int | None) -> None:
    if owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is None or not owner.active:
            reject(422, "Choose an active staff member.")


def validate_tag(db, tag: str, asset_id: int | None = None) -> None:
    existing = db.scalar(select(Asset.id).where(Asset.tag == tag))
    if existing is not None and existing != asset_id:
        reject(409, "An asset with this tag already exists.")


@router.get("", response_model=Page[AssetRead])
def list_assets(
    db: DB, user: CurrentUser, search: QueryText = "", type: AssetType | None = None,
    status: AssetStatus | None = None, limit: Limit = 20, offset: Offset = 0,
):
    require_inventory_access(user)
    statement = select(Asset).where(asset_scope(user)).options(joinedload(Asset.assigned_user))
    if term := search.strip().lower():
        fields = (Asset.tag, Asset.name, Asset.serial_number, Asset.location)
        statement = statement.where(or_(*(func.lower(field).contains(term, autoescape=True) for field in fields)))
    if type is not None:
        statement = statement.where(Asset.type == type)
    if status is not None:
        statement = statement.where(Asset.status == status)
    items, total = paginate(db, statement.order_by(Asset.tag), limit, offset)
    return Page[AssetRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/choices", response_model=Page[AssetRef])
def asset_choices(db: DB, user: CurrentUser, limit: Limit = 100, offset: Offset = 0):
    rows, count = paginate(db, select(Asset).where(asset_scope(user)).order_by(Asset.tag), limit, offset)
    return Page[AssetRef](items=rows, total=count, limit=limit, offset=offset)


@router.post("", status_code=201, response_model=AssetRead)
def create_asset(data: AssetCreate, db: DB, user: Admin):
    validate_tag(db, data.tag)
    validate_owner(db, data.assigned_user_id)
    asset = Asset(**data.model_dump())
    db.add(asset)
    db.flush()
    audit(db, user, "asset.created", "asset", asset.id, "Inventory record created.")
    db.commit()
    return asset


@router.get("/{asset_id}", response_model=AssetRead)
def read_asset(asset_id: AssetID, db: DB, user: CurrentUser):
    require_inventory_access(user)
    return find_asset(db, user, asset_id)


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: AssetID, data: AssetPatch, db: DB, user: Admin):
    asset = find_asset(db, user, asset_id)
    changes = {key: value for key, value in data.model_dump(exclude_unset=True).items()
               if getattr(asset, key) != value}
    if "tag" in changes:
        validate_tag(db, changes["tag"], asset.id)
    if "assigned_user_id" in changes:
        validate_owner(db, changes["assigned_user_id"])
    if changes:
        for key, value in changes.items():
            setattr(asset, key, value)
        audit(db, user, "asset.updated", "asset", asset.id, "Updated " + ", ".join(sorted(changes)) + ".")
        db.commit()
        db.expire(asset, ["assigned_user"])
    return asset
