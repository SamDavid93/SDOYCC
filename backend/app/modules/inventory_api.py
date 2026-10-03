from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from app.api import current_user, translated_text
from app.core.permissions import admin_reader
from app.db.models import BoosterPack, Card, CardDetails, CardVariant, InventoryTransaction, SpecialCard
from app.modules.admin import Database, Page, PageSize, paged, target

router = APIRouter(prefix="/api")


def journal(database, user_id, page, page_size):
    statement = select(InventoryTransaction, CardVariant, Card.name, CardDetails.name_de, func.coalesce(BoosterPack.name, SpecialCard.edition)).join(
        CardVariant, CardVariant.id == InventoryTransaction.variant_id).join(Card, Card.id == CardVariant.card_id).outerjoin(
        CardDetails, CardDetails.card_id == Card.id).outerjoin(BoosterPack, BoosterPack.id == CardVariant.booster_id).outerjoin(SpecialCard, SpecialCard.card_id == CardVariant.card_id).where(
        InventoryTransaction.user_id == user_id).order_by(InventoryTransaction.id.desc())
    return paged(database, statement, page, page_size, lambda row: {"id": row[0].id,
        "card_id": row[1].card_id, "name": translated_text(row[3]) or row[2], "variant_id": row[1].id,
        "rarity": row[1].rarity, "legacy": row[1].legacy, "source": row[4], "bound": row[0].bound,
        "amount": row[0].amount, "balance_after": row[0].balance_after, "reason": row[0].reason,
        "created_at": row[0].created_at.isoformat() + "Z"})


@router.get("/inventory/me/journal")
def my_journal(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 25):
    return journal(database, user.id, page, page_size)


@router.get("/admin/users/{user_id}/inventory-journal", dependencies=[Depends(admin_reader)])
def user_journal(user_id: int, database: Database, page: Page = 1, page_size: PageSize = 25):
    target(database, user_id)
    return journal(database, user_id, page, page_size)
