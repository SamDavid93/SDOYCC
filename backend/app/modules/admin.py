"""Read-only account management. Explicit payloads never serialize auth material."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import admin_reader
from app.db.models import BoosterPack, Card, CardDetails, DiamondTransaction, InventoryItem, User, UserBooster
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_reader)])
Database = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1, le=100000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def account(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name,
            "twitch_id": user.twitch_id, "role": user.role, "is_active": user.is_active,
            "registered": bool(user.password_hash), "points": user.credits,
            "created_at": user.created_at.isoformat() + "Z"}


def target(database: Session, user_id: int) -> User:
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Konto nicht gefunden.")
    return user


def paged(database: Session, statement, page: int, page_size: int, serialize) -> dict:
    total = database.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = database.execute(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/overview")
def overview(database: Database) -> dict:
    def count(*conditions):
        return database.scalar(select(func.count(User.id)).where(*conditions))
    return {"users": count(), "registered": count(User.password_hash.is_not(None)),
            "pending": count(User.password_hash.is_(None), User.twitch_id.is_not(None)),
            "inactive": count(User.is_active.is_(False)),
            "points": database.scalar(select(func.coalesce(func.sum(User.credits), 0))),
            "cards": database.scalar(select(func.coalesce(func.sum(InventoryItem.quantity), 0))),
            "packs": database.scalar(select(func.coalesce(func.sum(UserBooster.quantity), 0)))}


@router.get("/users")
def users(database: Database, search: str = Query("", max_length=100),
          state: Literal["all", "registered", "pending", "inactive"] = "all",
          role: Literal["all", "user", "support_admin", "admin", "super_admin"] = "all",
          page: Page = 1, page_size: PageSize = 25) -> dict:
    statement = select(User)
    if search.strip():
        term = search.strip()
        statement = statement.where(or_(User.username.icontains(term, autoescape=True),
                                       User.display_name.icontains(term, autoescape=True), User.twitch_id == term))
    if state == "registered":
        statement = statement.where(User.password_hash.is_not(None))
    elif state == "pending":
        statement = statement.where(User.password_hash.is_(None), User.twitch_id.is_not(None))
    elif state == "inactive":
        statement = statement.where(User.is_active.is_(False))
    if role != "all":
        statement = statement.where(User.role == role)
    return paged(database, statement.order_by(User.id), page, page_size, lambda row: account(row[0]))


@router.get("/users/{user_id}")
def user_detail(user_id: int, database: Database) -> dict:
    user = target(database, user_id)
    quantity, unique = database.execute(select(func.coalesce(func.sum(InventoryItem.quantity), 0), func.count())
        .where(InventoryItem.user_id == user_id, InventoryItem.quantity > 0)).one()
    packs = database.scalar(select(func.coalesce(func.sum(UserBooster.quantity), 0)).where(UserBooster.user_id == user_id))
    return {**account(user), "cards": quantity, "unique_cards": unique, "packs": packs}


@router.get("/users/{user_id}/wallet")
def wallet(user_id: int, database: Database, page: Page = 1, page_size: PageSize = 25) -> dict:
    target(database, user_id)
    statement = select(DiamondTransaction).where(DiamondTransaction.user_id == user_id).order_by(DiamondTransaction.id.desc())
    def serialize(row):
        entry = row[0]
        return {"id": entry.id, "amount": entry.amount, "balance_after": entry.balance_after,
                "reason": entry.reason, "created_at": entry.created_at.isoformat() + "Z"}
    return paged(database, statement, page, page_size, serialize)


@router.get("/users/{user_id}/inventory")
def inventory(user_id: int, database: Database, page: Page = 1, page_size: PageSize = 25) -> dict:
    target(database, user_id)
    # Project only the list fields; don't load large card texts or artwork metadata.
    statement = select(Card.id, Card.name, CardDetails.name_de, InventoryItem.quantity).join(
        InventoryItem, InventoryItem.card_id == Card.id).outerjoin(CardDetails, CardDetails.card_id == Card.id).where(
        InventoryItem.user_id == user_id, InventoryItem.quantity > 0).order_by(Card.id)
    from app.api import translated_text
    result = paged(database, statement, page, page_size,
                   lambda row: {"id": row[0], "name": translated_text(row[2]) or row[1], "quantity": row[3]})
    from app.modules.inventory import owned_variants
    variants = owned_variants(database, user_id, [item["id"] for item in result["items"]])
    for item in result["items"]:
        item["variants"] = variants.get(item["id"], [])
    return result


@router.get("/users/{user_id}/packs")
def packs(user_id: int, database: Database, page: Page = 1, page_size: PageSize = 25) -> dict:
    target(database, user_id)
    statement = select(BoosterPack.id, BoosterPack.name, UserBooster.quantity).join(
        UserBooster, UserBooster.booster_id == BoosterPack.id).where(
        UserBooster.user_id == user_id, UserBooster.quantity > 0).order_by(BoosterPack.id)
    return paged(database, statement, page, page_size,
                 lambda row: {"id": row[0], "name": row[1], "quantity": row[2]})
