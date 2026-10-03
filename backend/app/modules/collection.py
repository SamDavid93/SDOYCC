from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_, and_, String
from sqlalchemy.orm import Session
from app.db.models import Card, CardDetails, CardPrinting, CardSet, InventoryItem, CardVariant, VariantInventory, BoosterPack
from app.modules.inventory import owned_variants
from app.db.session import get_db
from app.api import current_user, card_payload

router = APIRouter(prefix="/api/collection")
Database = Annotated[Session, Depends(get_db)]


def owned_rarities(db, user_id):
    rows = db.execute(select(CardVariant.card_id, CardVariant.rarity).join(VariantInventory).where(VariantInventory.user_id == user_id, VariantInventory.quantity > 0).distinct()).all()
    result = {}
    for card_id, rarity in rows:
        result.setdefault(card_id, []).append(rarity or "unknown")
    return result


@router.get("/filters")
def filters(db: Database, user=Depends(current_user)):
    owned = select(InventoryItem.card_id).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0)
    def values(column):
        query = select(column).distinct().where(column.is_not(None))
        if isinstance(column.type, String):
            query = query.where(column != "")
        query = query.where(Card.id.in_(owned)) if column.class_ is Card else query.where(CardDetails.card_id.in_(owned))
        return list(db.scalars(query.order_by(column)))
    result = {key: values(column) for key, column in {
        "type": Card.card_type, "attribute": Card.attribute, "race": CardDetails.race,
        "archetype": CardDetails.archetype, "level": CardDetails.level, "atk": CardDetails.atk,
        "defense": CardDetails.defense, "scale": CardDetails.scale, "link_value": CardDetails.link_value,
        "ban_status": CardDetails.ban_status}.items()}
    rare = owned_rarities(db, user.id)
    result["rarity"] = sorted({value for card_id in db.scalars(owned) for value in rare.get(card_id, ["unknown"])})
    result["set_id"] = [{"value": item.id, "label": item.name} for item in db.scalars(select(CardSet).where(CardSet.id.in_(select(CardPrinting.set_id).where(CardPrinting.card_id.in_(owned)))).order_by(CardSet.name))]
    result["link_markers"] = sorted({marker for card in db.scalars(select(Card).where(Card.id.in_(owned))) for marker in card_payload(card)["link_markers"]})
    return result


@router.get("")
def collection(db: Database, user=Depends(current_user), search: str = "", rarity: str = "", card_type: str = "",
               attribute: str = "", race: str = "", archetype: str = "", level: int | None = None,
               atk: int | None = None, defense: int | None = None, scale: int | None = None,
               link_value: int | None = None, link_marker: str = "", ban_status: str = "",
               set_id: int | None = None, duplicates: bool = False,
               sort: str = Query("name", pattern="^(name|quantity|atk|level|recent)$"),
               page: int = Query(1, ge=1), page_size: int = Query(36, ge=1, le=72)):
    query = select(InventoryItem, Card).join(Card, Card.id == InventoryItem.card_id).outerjoin(CardDetails, CardDetails.card_id == Card.id).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0)
    if search:
        term = f"%{search}%"
        query = query.where(or_(Card.name.ilike(term), CardDetails.name_de.ilike(term), CardDetails.description_de.ilike(term), CardDetails.description_en.ilike(term), Card.set_code.ilike(term), Card.external_id == search))
    for column, value in [(Card.card_type, card_type), (Card.attribute, attribute), (CardDetails.race, race),
                          (CardDetails.archetype, archetype), (CardDetails.level, level), (CardDetails.atk, atk),
                          (CardDetails.defense, defense), (CardDetails.scale, scale), (CardDetails.link_value, link_value), (CardDetails.ban_status, ban_status)]:
        if value is not None and value != "":
            query = query.where(column == value)
    if link_marker:
        query = query.where(CardDetails.link_markers.contains('"' + link_marker + '"'))
    if set_id:
        query = query.where(Card.id.in_(select(CardPrinting.card_id).where(CardPrinting.set_id == set_id)))
    if duplicates:
        query = query.where(InventoryItem.quantity > 1)
    rarities = owned_rarities(db, user.id)
    if rarity:
        matching = [card_id for card_id, values in rarities.items() if rarity in values]
        query = query.where(or_(Card.id.in_(matching), Card.id.not_in(list(rarities)) if rarity == "unknown" else False))
    filtered = query.order_by(None).subquery()
    total = db.scalar(select(func.count()).select_from(filtered))
    orders = {"name": func.coalesce(CardDetails.name_de, Card.name), "quantity": InventoryItem.quantity.desc(), "atk": CardDetails.atk.desc(), "level": CardDetails.level.desc(), "recent": InventoryItem.id.desc()}
    rows = db.execute(query.order_by(orders[sort], Card.id).offset((page - 1) * page_size).limit(page_size)).unique().all()
    quantity, unique = db.execute(select(func.coalesce(func.sum(InventoryItem.quantity), 0), func.count()).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0)).one()
    ranking = ["common", "rare", "super_rare", "ultra_rare", "secret_rare", "ultimate_rare", "ghost_rare", "platinum_secret_rare", "starlight_rare", "quarter_century_secret_rare"]
    items = []
    variants = owned_variants(db, user.id, [card.id for _, card in rows])
    for stock, card in rows:
        payload = card_payload(card)
        owned = rarities.get(card.id, ["unknown"])
        payload["rarity"] = max(owned, key=lambda value: ranking.index(value) if value in ranking else -1)
        payload["collected_rarities"] = owned
        payload["owned_variants"] = variants.get(card.id, [{"id": None, "rarity": None, "legacy": True,
            "source": None, "printing_id": None, "quantity": stock.quantity, "reserved": 0, "available": stock.quantity, "bound": False}])
        items.append({"card": payload, "quantity": stock.quantity})
    return {"items": items, "total": total, "total_quantity": quantity, "unique_cards": unique, "page": page, "page_size": page_size}
