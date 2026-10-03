"""Variant stock and append-only movements, kept in sync with legacy card totals.

Call writers under lock_wallet; migration runs offline or during startup.
"""
import hashlib
import re
from collections import Counter, defaultdict

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import BoosterOpening, BoosterOpeningCard, CardVariant, InventoryItem, InventoryTransaction, VariantInventory


def rarity_key(value: str | None) -> str | None:
    return re.sub(r"\s+", "_", value.strip().lower()) if value and value.strip() else None


def variant(database: Session, card_id: int, rarity: str | None = None, booster_id: int | None = None, legacy=False) -> CardVariant:
    rarity = None if legacy else rarity_key(rarity)
    key = f"legacy:{card_id}" if legacy else f"draw:{card_id}:{booster_id}:{hashlib.sha256((rarity or '').encode()).hexdigest()}"
    row = database.scalar(select(CardVariant).where(CardVariant.key == key))
    if row is None:
        # Independent users may discover the same variant at the same time.
        insert = sqlite_insert if database.get_bind().dialect.name == "sqlite" else pg_insert
        database.execute(insert(CardVariant).values(key=key, card_id=card_id, rarity=rarity,
            booster_id=booster_id, legacy=legacy).on_conflict_do_nothing(index_elements=["key"]))
        row = database.scalar(select(CardVariant).where(CardVariant.key == key))
    return row


def migrate_user(database: Session, user_id: int) -> dict:
    totals = dict(database.execute(select(InventoryItem.card_id, InventoryItem.quantity).where(InventoryItem.user_id == user_id)).all())
    existing = dict(database.execute(select(CardVariant.card_id, func.sum(VariantInventory.quantity)).join(
        VariantInventory, VariantInventory.variant_id == CardVariant.id).where(VariantInventory.user_id == user_id).group_by(CardVariant.card_id)).all())
    for card_id, quantity in existing.items():
        if quantity != totals.get(card_id, 0):
            raise ValueError(f"Variantenbestand weicht vom Gesamtbestand ab: Konto {user_id}, Karte {card_id}.")
    pending = {card_id: quantity for card_id, quantity in totals.items() if card_id not in existing and quantity != 0}
    history = defaultdict(Counter)
    if pending:
        for card_id, booster_id, rarity, quantity in database.execute(select(BoosterOpeningCard.card_id, BoosterOpening.booster_id,
            BoosterOpeningCard.rarity, func.count()).join(BoosterOpening).where(
            BoosterOpening.user_id == user_id, BoosterOpeningCard.card_id.in_(pending)).group_by(
            BoosterOpeningCard.card_id, BoosterOpening.booster_id, BoosterOpeningCard.rarity)):
            history[card_id][(booster_id, rarity_key(rarity))] += quantity
    result = {"reconstructed": 0, "legacy": 0}
    for card_id, quantity in pending.items():
        if quantity < 0:
            raise ValueError("Negativer Altbestand; Migration abgebrochen.")
        proven = history[card_id]
        # No arbitrary subset selection: any mismatch leaves the entire old stock unknown.
        exact = sum(proven.values()) == quantity and all(rarity for _, rarity in proven)
        allocations = proven if exact else {(None, None): quantity}
        reason = "opening_reconstruction" if exact else "legacy_migration"
        for (booster_id, rarity), amount in allocations.items():
            kind = variant(database, card_id, rarity, booster_id, legacy=not exact)
            database.add(VariantInventory(user_id=user_id, variant_id=kind.id, quantity=amount, reserved=0, bound=False))
            database.add(InventoryTransaction(user_id=user_id, variant_id=kind.id, bound=False, amount=amount,
                balance_after=amount, reason=reason, reference=f"baseline:{user_id}:{kind.id}"))
        result["reconstructed" if exact else "legacy"] += quantity
    database.flush()
    return result


def migrate_inventory(database: Session) -> dict:
    result = {"reconstructed": 0, "legacy": 0}
    owners = select(InventoryItem.user_id).union(select(VariantInventory.user_id)).subquery()
    for user_id in database.scalars(select(owners.c.user_id).order_by(owners.c.user_id)):
        counts = migrate_user(database, user_id)
        for key in result:
            result[key] += counts[key]
    return result


def change_stock(database: Session, user_id: int, kind: CardVariant, amount: int, reason: str, reference: str, bound=False) -> None:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount == 0:
        raise ValueError("Kartenbewegung muss eine ganze Menge ungleich null sein.")
    previous = database.scalar(select(InventoryTransaction).where(InventoryTransaction.reference == reference))
    if previous:
        if (previous.user_id, previous.variant_id, previous.amount, previous.reason, previous.bound) != (user_id, kind.id, amount, reason, bound):
            raise HTTPException(409, "Diese Kartenbewegung wurde bereits anders gebucht.")
        return
    stock = database.scalar(select(VariantInventory).where(VariantInventory.user_id == user_id,
        VariantInventory.variant_id == kind.id, VariantInventory.bound == bound))
    if stock is None:
        stock = VariantInventory(user_id=user_id, variant_id=kind.id, quantity=0, reserved=0, bound=bound)
        database.add(stock)
    if stock.quantity + amount < stock.reserved:
        raise HTTPException(409, "Nicht genügend frei verfügbare Exemplare dieser Variante.")
    total = database.scalar(select(InventoryItem).where(InventoryItem.user_id == user_id, InventoryItem.card_id == kind.card_id))
    if total is None:
        total = InventoryItem(user_id=user_id, card_id=kind.card_id, quantity=0)
        database.add(total)
    variant_total = database.scalar(select(func.coalesce(func.sum(VariantInventory.quantity), 0)).join(
        CardVariant, CardVariant.id == VariantInventory.variant_id).where(
        VariantInventory.user_id == user_id, CardVariant.card_id == kind.card_id))
    if variant_total != total.quantity:
        raise HTTPException(409, "Variantenbestand und Kartenbestand weichen ab. Bitte die Bestandsprüfung ausführen.")
    if total.quantity + amount < 0:
        raise HTTPException(409, "Kartenbestand reicht nicht aus.")
    stock.quantity += amount
    total.quantity += amount
    database.add(InventoryTransaction(user_id=user_id, variant_id=kind.id, bound=bound, amount=amount,
        balance_after=stock.quantity, reason=reason, reference=reference))
    database.flush()


def owned_variants(database: Session, user_id: int, card_ids: list[int]) -> dict:
    from app.db.models import BoosterPack, SpecialCard
    result = defaultdict(list)
    if not card_ids:
        return result
    for kind, stock, name in database.execute(select(CardVariant, VariantInventory, func.coalesce(BoosterPack.name, SpecialCard.edition)).join(
        VariantInventory, VariantInventory.variant_id == CardVariant.id).outerjoin(BoosterPack, BoosterPack.id == CardVariant.booster_id).outerjoin(SpecialCard, SpecialCard.card_id == CardVariant.card_id).where(
        VariantInventory.user_id == user_id, VariantInventory.quantity > 0, CardVariant.card_id.in_(card_ids)).order_by(CardVariant.id)):
        result[kind.card_id].append({"id": kind.id, "rarity": kind.rarity, "legacy": kind.legacy,
            "source": name, "printing_id": kind.printing_id, "quantity": stock.quantity,
            "reserved": stock.reserved, "available": stock.quantity - stock.reserved, "bound": stock.bound})
    return result
