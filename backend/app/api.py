import random
import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, case, and_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.auth import get_current_user
from app.core.permissions import admin_reader as admin_user
from app.db.models import BattlePassProgress, BoosterOpening, BoosterOpeningCard, BoosterPack, BoosterPoolEntry, Card, CardDetails, CardPrinting, CardSet, DiamondTransaction, InventoryItem, TradeListing, User, UserBooster, ProductPurchaseCounter, StructureDeckDefinition, StructureDeckItem, StructureDeckBonusSlot, StructureDeckBonusChoice, SpecialCard
from app.db.session import get_db
from app.modules.card_data.service import catalog_service
from app.modules.economy import lock_wallet, book_diamonds, replay, finish
from app.modules.inventory import migrate_user, variant, change_stock
from app.core.config import settings
from app.core.pricing import product_price, purchase_limit
from app.core.structure_decks import deck_entries, product_rules, deck_size, deck_candidates, draw_deck
from app.core.booster_rules import drawable_entries, effective_pack_size, pool_size, MAX_WEIGHT

router = APIRouter(prefix="/api")
Database = Annotated[Session, Depends(get_db)]


def current_user(database: Database, authorization: Annotated[str | None, Header()] = None) -> User:
    return get_current_user(authorization, database)


def translated_text(value):
    if not value or not value.strip() or re.fullmatch(r"Karte\s*(?:\[\s*)?\d+\s*\]?", value.strip(), re.IGNORECASE):
        return None
    return value.strip()


def card_payload(card: Card) -> dict:
    details = card.details
    name_de = translated_text(details.name_de) if details else None
    description_de = translated_text(details.description_de) if details else None
    german = bool(details and details.konami_id)
    original = (f"/api/community/cards/{card.id}/image" if card.external_provider == "sdoycc-community" else f"/api/cards/{card.id}/art/original") if card.image_url else None
    return {"id": card.id, "external_id": card.external_id,
            "name": name_de or card.name,
            "description": description_de or (details.description_en if details else None),
            "description_language": "de" if description_de else "en",
            "localized": bool(name_de),
            "image_available": german or bool(original),
            "image_language": "de" if german or card.external_provider == "sdoycc-community" else "original",
            "fallback_image_url": original if german else None,
            "set": card.card_set, "set_code": card.set_code, "rarity": card.rarity,
            "type": card.card_type, "attribute": card.attribute,
            "image_url": f"/api/cards/{card.id}/art/de" if german else original,
            "race": details.race if details else None, "archetype": details.archetype if details else None,
            "level": details.level if details else None, "atk": details.atk if details else None,
            "defense": details.defense if details else None, "scale": details.scale if details else None,
            "link_value": details.link_value if details else None,
            "link_markers": json.loads(details.link_markers or "[]") if details else [],
            "ban_status": details.ban_status if details else None}


@router.get("/auth/demo")
def demo_auth() -> dict:
    if not settings.demo_enabled:
        raise HTTPException(404, "Demo-Zugang deaktiviert")
    return {"token": "demo-token", "user": {"username": "jaden-demo", "display_name": "Jaden D."}}


@router.get("/users/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role, "credits": user.credits, "diamonds": user.credits, "twitch_id": user.twitch_id}


@router.get("/wallet/me/history")
def wallet_history(database: Database, user: User = Depends(current_user)) -> list[dict]:
    entries = database.scalars(select(DiamondTransaction).where(DiamondTransaction.user_id == user.id).order_by(DiamondTransaction.id.desc()).limit(100)).all()
    return [{"id": entry.id, "amount": entry.amount, "balance_after": entry.balance_after, "reason": entry.reason, "created_at": entry.created_at.isoformat() + "Z"} for entry in entries]


@router.get("/users/me/summary")
def user_summary(database: Database, user: User = Depends(current_user)) -> dict:
    quantity, unique = database.execute(select(func.coalesce(func.sum(InventoryItem.quantity), 0), func.count()).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0)).one()
    return {"total_cards": quantity, "unique_cards": unique,
            "packs_opened": database.scalar(select(func.count()).select_from(BoosterOpening).where(BoosterOpening.user_id == user.id)),
            "owned_packs": database.scalar(select(func.coalesce(func.sum(UserBooster.quantity), 0)).where(UserBooster.user_id == user.id))}


@router.get("/cards")
def list_cards(database: Database, search: str | None = Query(default=None), rarity: str | None = Query(default=None), card_type: str | None = Query(default=None), attribute: str | None = Query(default=None), set_id: int | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=24, ge=1, le=100)) -> dict:
    # Sort/page lightweight IDs first; never sort the full text/image metadata
    # of the entire catalog just to display one page.
    query = select(Card.id).outerjoin(CardDetails, CardDetails.card_id == Card.id).order_by(CardDetails.name_de.is_(None), func.coalesce(CardDetails.name_de, Card.name), Card.id)
    query = query.where(~Card.id.in_(select(SpecialCard.card_id).where(SpecialCard.state == "draft")))
    if search:
        query = query.where(Card.name.ilike(f"%{search}%") | Card.details.has(CardDetails.name_de.ilike(f"%{search}%")) | Card.card_set.ilike(f"%{search}%") | Card.set_code.ilike(f"%{search}%") | Card.rarity.ilike(f"%{search}%"))
    if rarity:
        query = query.where(Card.rarity == rarity)
    if card_type:
        query = query.where(Card.card_type == card_type)
    if attribute:
        query = query.where(Card.attribute == attribute)
    if set_id:
        query = query.where(Card.id.in_(select(CardPrinting.card_id).where(CardPrinting.set_id == set_id)))
    total = database.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    start = (page - 1) * page_size
    ids = list(database.scalars(query.offset(start).limit(page_size)))
    records = {card.id: card for card in database.scalars(select(Card).where(Card.id.in_(ids)))}
    cards = [records[card_id] for card_id in ids]
    return {"items": [card_payload(card) for card in cards], "total": total, "page": page, "page_size": page_size}


@router.get("/cards/{card_id}")
def get_card(card_id: int, database: Database) -> dict:
    card = database.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Karte nicht gefunden")
    return card_payload(card)


@router.get("/cards/{card_id}/image")
def card_image(card_id: int, database: Database) -> dict:
    card = database.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Karte nicht gefunden")
    payload = card_payload(card)
    return {key: payload[key] for key in ("external_id", "image_url", "fallback_image_url", "image_language")}


@router.get("/cards/{card_id}/printings")
def card_printings(card_id: int, database: Database) -> list[dict]:
    card = database.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Karte nicht gefunden")
    printings = database.scalars(select(CardPrinting).where(CardPrinting.card_id == card_id).order_by(CardPrinting.set_code)).all()
    return [{"id": item.id, "set_id": item.set_id, "external_printing_id": item.external_printing_id, "set_code": item.set_code, "rarity": item.rarity, "provider_rarity_name": item.provider_rarity_name, "image_url": item.image_url} for item in printings]


@router.get("/cards/{card_id}/boosters")
def boosters_for_card(card_id: int, database: Database, user: User = Depends(current_user)) -> list[dict]:
    if database.get(Card, card_id) is None:
        raise HTTPException(404, "Karte nicht gefunden")
    return boosters(database, user, set_id=None, card_id=card_id)


@router.get("/card-sets")
def list_card_sets(database: Database, search: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100)) -> dict:
    query = select(CardSet).order_by(CardSet.name)
    if search:
        query = query.where(CardSet.name.ilike(f"%{search}%") | CardSet.code.ilike(f"%{search}%"))
    total = database.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    start = (page - 1) * page_size
    sets = database.scalars(query.offset(start).limit(page_size)).all()
    return {"items": [{"id": item.id, "external_id": item.external_id, "name": item.name, "code": item.code, "release_date": item.release_date, "card_count": item.card_count, "cover_image_url": item.cover_image_url} for item in sets], "total": total, "page": page, "page_size": page_size}


@router.get("/packs")
def list_packs(database: Database, search: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100)) -> dict:
    """Pack catalog backed by the synchronized official cardsets feed."""
    return list_card_sets(database, search=search, page=page, page_size=page_size)


@router.get("/card-sets/{set_id}/cards")
def cards_in_set(set_id: int, database: Database) -> list[dict]:
    card_set = database.get(CardSet, set_id)
    if card_set is None:
        raise HTTPException(status_code=404, detail="Kartenset nicht gefunden")
    cards_for_set = database.scalars(select(Card).join(CardPrinting, CardPrinting.card_id == Card.id).where(CardPrinting.set_id == set_id).distinct().order_by(Card.name)).all()
    return [card_payload(card) for card in cards_for_set]


@router.get("/card-sets/{set_id}/boosters")
def boosters_for_set(set_id: int, database: Database, user: User = Depends(current_user)) -> list[dict]:
    if database.get(CardSet, set_id) is None:
        raise HTTPException(status_code=404, detail="Kartenset nicht gefunden")
    return boosters(database, user, set_id=set_id)


@router.get("/packs/{pack_id}/cards")
def cards_in_pack(pack_id: int, database: Database) -> list[dict]:
    return cards_in_set(pack_id, database)


@router.get("/admin/card-data/status")
def card_data_status(user: User = Depends(admin_user)) -> dict:
    return catalog_service.status()


@router.post("/admin/card-data/sync/recent")
def sync_recent_cards(user: User = Depends(admin_user)) -> dict:
    raise HTTPException(501, "Katalog-Sync über backend/scripts/sync_catalog.py ausführen")


@router.get("/inventory/me")
def inventory(database: Database, user: User = Depends(current_user)) -> dict:
    items = database.scalars(select(InventoryItem).options(joinedload(InventoryItem.card)).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0).order_by(InventoryItem.id.desc())).all()
    return {"items": [{"quantity": item.quantity, "card": card_payload(item.card)} for item in items], "total_quantity": sum(item.quantity for item in items), "unique_cards": len(items)}


@router.get("/boosters")
def boosters(database: Database, user: User = Depends(current_user), set_id: int | None = None, card_id: int | None = None) -> list[dict]:
    query = select(BoosterPack).options(selectinload(BoosterPack.deck).selectinload(StructureDeckDefinition.items), selectinload(BoosterPack.deck).selectinload(StructureDeckDefinition.bonus_slots).selectinload(StructureDeckBonusSlot.choices)).where(BoosterPack.active.is_(True)).order_by(BoosterPack.id)
    if set_id:
        query = query.where(BoosterPack.set_id == set_id)
    if card_id:
        query = query.where(((BoosterPack.product_type == "structure_deck") & BoosterPack.deck.has(StructureDeckDefinition.items.any(StructureDeckItem.card_id == card_id) | StructureDeckDefinition.bonus_slots.any(StructureDeckBonusSlot.choices.any(StructureDeckBonusChoice.card_id == card_id)))) | ((BoosterPack.product_type != "structure_deck") & BoosterPack.entries.any(BoosterPoolEntry.card_id == card_id)))
    packs = database.scalars(query).all()
    stock = {item.booster_id: item.quantity for item in database.scalars(select(UserBooster).where(UserBooster.user_id == user.id)).all()}
    valid_weight = and_(BoosterPoolEntry.weight >= 0, BoosterPoolEntry.weight <= MAX_WEIGHT)
    sizes = database.execute(select(
        BoosterPoolEntry.booster_id,
        func.count(func.distinct(case((and_(valid_weight, BoosterPoolEntry.weight > 0), BoosterPoolEntry.card_id)))),
        func.sum(case((valid_weight, 0), else_=1)),
        func.count(func.distinct(case((and_(valid_weight, BoosterPoolEntry.weight > 0, InventoryItem.quantity > 0), BoosterPoolEntry.card_id)))),
    ).outerjoin(InventoryItem, and_(InventoryItem.card_id == BoosterPoolEntry.card_id, InventoryItem.user_id == user.id))
        .group_by(BoosterPoolEntry.booster_id)).all()
    pool_sizes = {pack_id: count if invalid == 0 else 0 for pack_id, count, invalid, collected in sizes}
    collected_counts = {pack_id: collected if invalid == 0 else 0 for pack_id, count, invalid, collected in sizes}
    purchased = dict(database.execute(select(ProductPurchaseCounter.booster_id, ProductPurchaseCounter.quantity).where(ProductPurchaseCounter.user_id == user.id)).all())
    sets = {item.id: item for item in database.scalars(select(CardSet))}
    deck_sizes = {pack.id: deck_size(pack) for pack in packs if pack.product_type == "structure_deck"}
    owned_cards = set(database.scalars(select(InventoryItem.card_id).where(InventoryItem.user_id == user.id, InventoryItem.quantity > 0))) if deck_sizes else set()
    for pack in packs:
        if pack.product_type == "structure_deck":
            candidates = {item.card_id for item in deck_candidates(pack)}
            pool_sizes[pack.id] = len(candidates)
            collected_counts[pack.id] = len(candidates & owned_cards)
    return [{"id": pack.id, "key": pack.key, "name": pack.name, "set_id": pack.set_id,
             "set_name": sets[pack.set_id].name if pack.set_id in sets else None,
             "set_code": sets[pack.set_id].code if pack.set_id in sets else None,
             "image_url": pack.image_url, "cards_per_pack": deck_sizes[pack.id] if pack.id in deck_sizes else effective_pack_size(pack.cards_per_pack, pool_sizes.get(pack.id, 0)), "cost": product_price(pack.product_type),
             **product_rules(pack, purchased.get(pack.id, 0)),
             "owned": stock.get(pack.id, 0), "pool_size": pool_sizes.get(pack.id, 0),
             "collection_progress": collection_progress(collected_counts.get(pack.id, 0), pool_sizes.get(pack.id, 0))} for pack in packs]


def collection_progress(owned: int, total: int) -> dict:
    return {"owned": owned, "total": total, "percent": round(100 * owned / total, 1) if total else 0}


def booster_payload(pack: BoosterPack, owned: int = 0, purchased: int = 0) -> dict:
    rarity_counts: dict[str, int] = {}
    entries = deck_entries(pack) if pack.product_type == "structure_deck" else drawable_entries(pack.entries)
    size = pool_size(deck_candidates(pack) if pack.product_type == "structure_deck" else entries)
    for entry in entries:
        rarity_counts[entry.rarity] = rarity_counts.get(entry.rarity, 0) + (entry.quantity if pack.product_type == "structure_deck" else 1)
    return {"id": pack.id, "key": pack.key, "name": pack.name, "set_id": pack.set_id, "image_url": pack.image_url, "cards_per_pack": deck_size(pack) if pack.product_type == "structure_deck" else effective_pack_size(pack.cards_per_pack, size), "cost": product_price(pack.product_type), **product_rules(pack, purchased), "owned": owned, "pool_size": size, "rarities": [{"rarity": rarity, "cards": count} for rarity, count in sorted(rarity_counts.items())]}


@router.get("/boosters/{booster_id:int}")
def booster_detail(booster_id: int, database: Database, user: User = Depends(current_user)) -> dict:
    pack = database.scalar(select(BoosterPack).options(joinedload(BoosterPack.entries).joinedload(BoosterPoolEntry.card), selectinload(BoosterPack.deck).selectinload(StructureDeckDefinition.items).joinedload(StructureDeckItem.card), selectinload(BoosterPack.deck).selectinload(StructureDeckDefinition.bonus_slots).selectinload(StructureDeckBonusSlot.choices).joinedload(StructureDeckBonusChoice.card)).where(BoosterPack.id == booster_id))
    if pack is None or not pack.active:
        raise HTTPException(status_code=404, detail="Booster nicht gefunden")
    stock = database.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == booster_id))
    counter = database.scalar(select(ProductPurchaseCounter).where(ProductPurchaseCounter.user_id == user.id, ProductPurchaseCounter.booster_id == pack.id))
    payload = booster_payload(pack, stock.quantity if stock else 0, counter.quantity if counter else 0)
    candidates = {entry.card_id for entry in (deck_candidates(pack) if pack.product_type == "structure_deck" else drawable_entries(pack.entries))}
    collected = database.scalar(select(func.count()).select_from(InventoryItem).where(
        InventoryItem.user_id == user.id, InventoryItem.quantity > 0, InventoryItem.card_id.in_(candidates)))
    payload["collection_progress"] = collection_progress(collected, len(candidates))
    card_set = database.get(CardSet, pack.set_id) if pack.set_id else None
    printings = {}
    if card_set:
        for printing in database.scalars(select(CardPrinting).where(CardPrinting.set_id == card_set.id).order_by(CardPrinting.id)):
            printings.setdefault((printing.card_id, printing.rarity), printing)
    payload["set_name"] = card_set.name if card_set else None
    payload["set_code"] = card_set.code if card_set else None
    payload["pool"] = []
    for entry in (deck_entries(pack) if pack.product_type == "structure_deck" else drawable_entries(pack.entries)):
        printing = printings.get((entry.card_id, entry.rarity))
        card = {**card_payload(entry.card), "rarity": entry.rarity,
                "set": card_set.name if card_set else pack.name,
                "set_code": printing.set_code if printing else ""}
        payload["pool"].append({"card": card, "rarity": entry.rarity, "weight": 0 if pack.product_type == "structure_deck" else entry.weight, "quantity": entry.quantity if pack.product_type == "structure_deck" else None})
    payload["bonus_slots"] = []
    if pack.product_type == "structure_deck" and deck_entries(pack):
        for slot in pack.deck.bonus_slots:
            choices = []
            for choice in slot.choices:
                printing = printings.get((choice.card_id, choice.rarity))
                choices.append({"card": {**card_payload(choice.card), "rarity": choice.rarity,
                    "set": card_set.name if card_set else pack.name,
                    "set_code": printing.set_code if printing else ""},
                    "rarity": choice.rarity, "probability": 1 / len(slot.choices)})
            payload["bonus_slots"].append({"name": slot.name, "quantity": 1, "choices": choices})
    return payload


@router.get("/boosters/me")
def my_boosters(database: Database, user: User = Depends(current_user)) -> list[dict]:
    stocks = database.scalars(select(UserBooster).where(UserBooster.user_id == user.id)).all()
    return [{"booster_id": stock.booster_id, "quantity": stock.quantity} for stock in stocks]


class BoosterPurchase(BaseModel):
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/boosters/{booster_id}/purchase")
def purchase_booster(booster_id: int, payload: BoosterPurchase, database: Database, user: User = Depends(current_user), idempotency_key: Annotated[str | None, Header()] = None) -> dict:
    lock_wallet(database, user)
    action = f"purchase:{booster_id}:{payload.quantity}"
    previous = replay(database, user, idempotency_key, action)
    if previous is not None:
        return previous
    booster = database.get(BoosterPack, booster_id)
    if booster is None or not booster.active:
        raise HTTPException(status_code=404, detail="Booster nicht gefunden")
    total_cost = product_price(booster.product_type) * payload.quantity
    is_deck = booster.product_type == "structure_deck"
    if is_deck and not deck_entries(booster):
        raise HTTPException(409, "Die vollständige Deckliste wird noch geprüft; Kauf derzeit nicht verfügbar")
    if not is_deck and not effective_pack_size(booster.cards_per_pack, pool_size(drawable_entries(booster.entries))):
        raise HTTPException(409, "Dieser Booster hat keinen gültigen Kartenpool")
    counter = database.scalar(select(ProductPurchaseCounter).where(ProductPurchaseCounter.user_id == user.id, ProductPurchaseCounter.booster_id == booster_id).with_for_update())
    purchased = counter.quantity if counter else 0
    limit = purchase_limit(booster.product_type)
    if limit is not None and purchased + payload.quantity > limit:
        raise HTTPException(409, "Dieses Structure Deck kann pro Konto insgesamt nur dreimal gekauft werden")
    book_diamonds(database, user, -total_cost, "booster_purchase")
    if counter is None:
        counter = ProductPurchaseCounter(user_id=user.id, booster_id=booster_id, quantity=0)
        database.add(counter)
    counter.quantity += payload.quantity
    stock = database.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == booster_id).with_for_update())
    if stock is None:
        stock = UserBooster(user_id=user.id, booster_id=booster_id, quantity=0)
        database.add(stock)
    stock.quantity += payload.quantity
    return finish(database, user, idempotency_key, action, {"booster_id": booster_id, "purchased": payload.quantity, "owned": stock.quantity, "credits_remaining": user.credits, "diamonds_remaining": user.credits, "image_url": booster.image_url, "cost": product_price(booster.product_type), "total_cost": total_cost, **product_rules(booster, counter.quantity)})


@router.get("/boosters/me/history")
def booster_history(database: Database, user: User = Depends(current_user), limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    openings = database.execute(select(BoosterOpening).options(joinedload(BoosterOpening.cards).joinedload(BoosterOpeningCard.card), joinedload(BoosterOpening.booster)).where(BoosterOpening.user_id == user.id, BoosterOpening.cards.any()).order_by(BoosterOpening.created_at.desc()).limit(limit)).unique().scalars().all()
    return [{"id": opening.id, "booster_id": opening.booster_id, "booster_name": opening.booster.name, "credits_spent": opening.credits_spent, "created_at": opening.created_at.isoformat(), "cards": [{"rarity": result.rarity, "is_new": result.is_new, "card": card_payload(result.card)} for result in opening.cards]} for opening in openings]


@router.post("/boosters/{booster_id}/open")
def open_booster(booster_id: int, database: Database, user: User = Depends(current_user), idempotency_key: Annotated[str | None, Header()] = None) -> dict:
    lock_wallet(database, user)
    action = f"open:{booster_id}"
    previous = replay(database, user, idempotency_key, action)
    if previous is not None:
        return previous
    booster = database.get(BoosterPack, booster_id)
    stock = database.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == booster_id).with_for_update())
    if booster is None or not booster.active or stock is None or stock.quantity < 1:
        raise HTTPException(status_code=400, detail="Kein ungeöffneter Booster verfügbar")
    is_deck = booster.product_type == "structure_deck"
    entries = deck_entries(booster) if is_deck else drawable_entries(booster.entries)
    count = deck_size(booster) if is_deck else effective_pack_size(booster.cards_per_pack, pool_size(entries))
    if not count:
        raise HTTPException(status_code=409, detail="Dieser Booster hat keinen gültigen Kartenpool")
    stock.quantity -= 1
    migrate_user(database, user.id)
    results: list[dict] = []
    opening = BoosterOpening(user_id=user.id, booster_id=booster_id, credits_spent=0)
    database.add(opening)
    database.flush()
    # Scale weights to keep even large finite values safe for random.choices.
    if is_deck:
        drawn = draw_deck(booster)
    else:
        max_weight = max(entry.weight for entry in entries)
        weights = [entry.weight / max_weight for entry in entries]
        drawn = random.SystemRandom().choices(entries, weights=weights, k=count)
    for draw_index, entry in enumerate(drawn):
        item = database.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.card_id == entry.card_id))
        is_new = item is None or item.quantity == 0
        kind = variant(database, entry.card_id, entry.rarity, booster_id)
        change_stock(database, user.id, kind, 1, "booster_opening", f"opening:{opening.id}:{draw_index}")
        results.append({**card_payload(entry.card), "rarity": entry.rarity})
        database.add(BoosterOpeningCard(opening_id=opening.id, card_id=entry.card_id, rarity=entry.rarity, is_new=is_new))
    database.flush()
    from app.modules.seasons import process_opening
    process_opening(database, opening)
    from app.modules.rare_pulls import enqueue_rare_pulls
    enqueue_rare_pulls(database, opening, user, booster, results)
    return finish(database, user, idempotency_key, action, {"opening_id": opening.id, "booster_id": booster_id, "cards": results, "remaining": stock.quantity, "credits_remaining": user.credits, "diamonds_remaining": user.credits})


# Legacy prototypes intentionally have no writable routes. The versioned market and
# real season modules own /trade and /seasons.
