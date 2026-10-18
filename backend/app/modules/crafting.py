"""Printing-based crafting. Own database, shared stock locks and one transaction.

VariantInventory is the canonical, reservation-aware stock with a direct printing
FK; CardVariant preserves provenance. InventoryItem is a checked, derived total for
the collection/deck readers. Unknown legacy stock never receives invented rarity.
"""
import json
import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import aliased

from app.api import current_user, translated_text
from app.core.permissions import admin_reader
from app.db.models import (BoosterPack, Card, CardDetails, CardPrinting, CardSet, CardVariant,
    CraftingControl, CraftingCurrency, CraftingRarityRule, CraftingTransaction, HubEvent,
    SpecialCard, UserCardPreference, UserCraftingBalance, UserCraftingSettings, VariantInventory)
from app.modules.admin import Database, Page, PageSize, paged, target
from app.modules.economy import finish, replay
from app.modules.inventory import change_stock, ensure_printing, rarity_key, reservation_totals
from app.modules.workflow import AdminCommand, Auth, Command, Key, action, administrator, audit, writer

router = APIRouter(prefix="/api/crafting")
admin_router = APIRouter(prefix="/api/admin/crafting", dependencies=[Depends(admin_reader)])


def seed_crafting(db):
    """Add only rarities actually present; never overwrite administrator balancing."""
    keys = set(db.scalars(select(CardPrinting.rarity).distinct())) | set(db.scalars(select(Card.rarity).distinct()))
    existing = set(db.scalars(select(CraftingRarityRule.rarity_key)))
    for order, key in enumerate(sorted(k for k in keys if k)):
        key = rarity_key(key)
        if key in existing: continue
        currency = key + "_cp"
        title = key.replace("_", " ").title()
        if not db.get(CraftingCurrency, currency):
            db.add(CraftingCurrency(key=currency, display_name=title + " CP")); db.flush()
        db.add(CraftingRarityRule(rarity_key=key, currency_key=currency, display_name=title,
            dismantle_value=10, craft_cost=30, crafting_enabled=key != "other",
            dismantling_enabled=key != "other", sort_order=order))
        existing.add(key)
    if not db.get(CraftingControl, 1): db.add(CraftingControl(id=1))
    db.flush()


def control(db):
    row = db.get(CraftingControl, 1)
    return {"crafting_enabled": row.crafting_enabled if row else True,
        "dismantling_enabled": row.dismantling_enabled if row else True,
        "bulk_enabled": row.bulk_enabled if row else True,
        "max_quantity": row.max_quantity if row else 1000, "version": row.version if row else 1}


def rule_json(row):
    return {key: getattr(row, key) for key in ("id", "rarity_key", "currency_key", "display_name",
        "dismantle_value", "craft_cost", "crafting_enabled", "dismantling_enabled", "sort_order", "version")}


def printing_rule(db, printing):
    # Explicit provider-name assignments take precedence over the normalized bucket.
    for key in dict.fromkeys([rarity_key(printing.provider_rarity_name), rarity_key(printing.rarity)]):
        if key:
            row = db.scalar(select(CraftingRarityRule).where(CraftingRarityRule.rarity_key == key))
            if row: return row


def eligible(db, printing):
    return bool(printing.rarity and not db.scalar(select(SpecialCard.id).where(SpecialCard.card_id == printing.card_id)))


def wallet(db, uid):
    balances = dict(db.execute(select(UserCraftingBalance.currency_key, UserCraftingBalance.balance).where(UserCraftingBalance.user_id == uid)).all())
    return [{"currency_key": c.key, "display_name": c.display_name, "balance": balances.get(c.key, 0)}
        for c in db.scalars(select(CraftingCurrency).order_by(CraftingCurrency.key))]


def book_currency(db, uid, currency, amount, source, kind, printing=None, quantity=0, rarity=None):
    if not db.get(CraftingCurrency, currency): raise HTTPException(400, "Unbekannte Crafting-Währung.")
    old = db.scalar(select(CraftingTransaction).where(CraftingTransaction.source_ref == source))
    if old:
        if (old.user_id, old.currency_key, old.currency_amount, old.type) != (uid, currency, amount, kind):
            raise HTTPException(409, "Diese CP-Buchung wurde bereits anders ausgeführt.")
        return old
    row = db.scalar(select(UserCraftingBalance).where(UserCraftingBalance.user_id == uid, UserCraftingBalance.currency_key == currency))
    if not row:
        row = UserCraftingBalance(user_id=uid, currency_key=currency, balance=0); db.add(row)
    before = row.balance
    if before + amount < 0: raise HTTPException(409, "Nicht genügend Craft Points dieser Rarität.")
    row.balance += amount
    tx = CraftingTransaction(user_id=uid, type=kind, card_printing_id=printing, rarity_key=rarity,
        currency_key=currency, card_quantity=quantity, currency_amount=amount,
        balance_before=before, balance_after=row.balance, source_ref=source)
    db.add(tx); db.flush()
    if kind != "admin_adjustment":
        emit(db, uid, "crafting_currency_earned" if amount > 0 else "crafting_currency_spent", source,
            {"currency_key": currency, "currency_amount": abs(amount), "rarity": rarity, "source_ref": source})
    return tx


def emit(db, uid, event_type, ref, payload):
    db.add(HubEvent(user_id=uid, event_type=event_type, source_ref=ref, payload_json=json.dumps(payload)))
    db.flush()


def holdings(db, uid, printing_id, ledger=None):
    rows = db.execute(select(VariantInventory, CardVariant).join(CardVariant, CardVariant.id == VariantInventory.variant_id).where(
        VariantInventory.user_id == uid, CardVariant.printing_id == printing_id)).all()
    pref = db.scalar(select(UserCardPreference).where(UserCardPreference.user_id == uid, UserCardPreference.card_printing_id == printing_id))
    settings = db.get(UserCraftingSettings, uid)
    keep = settings.keep_one if settings else True
    ledger = reservation_totals(db) if ledger is None else ledger
    owned = sum(stock.quantity for stock, _ in rows)
    unbound = sum(stock.quantity for stock, _ in rows if not stock.bound)
    reserved = sum(max(stock.reserved, ledger.get((uid, kind.id, stock.bound), 0)) for stock, kind in rows if not stock.bound)
    protected = max(pref.protected_quantity if pref else 0, int(keep and unbound > 0))
    return {"quantity": owned, "unbound_quantity": unbound, "bound_quantity": owned - unbound,
        "reserved": reserved, "protected_quantity": pref.protected_quantity if pref else 0,
        "effective_protected": protected, "favorite": pref.favorite if pref else False,
        "keep_one": keep, "dismantle_available_quantity": max(0, unbound - reserved - protected)}, rows


def card_json(db, uid, printing, card=None, details=None, card_set=None, ledger=None):
    card = card or db.get(Card, printing.card_id)
    details = details or db.get(CardDetails, printing.card_id)
    card_set = card_set or (db.get(CardSet, printing.set_id) if printing.set_id else None)
    stock, _ = holdings(db, uid, printing.id, ledger)
    rule = printing_rule(db, printing)
    funds = db.scalar(select(UserCraftingBalance.balance).where(UserCraftingBalance.user_id == uid,
        UserCraftingBalance.currency_key == rule.currency_key)) or 0 if rule else 0
    switches = control(db)
    allowed = eligible(db, printing)
    return {"card_printing_id": printing.id, "card_id": card.id,
        "name": translated_text(details.name_de) if details and translated_text(details.name_de) else card.name,
        "image_url": f"/api/cards/{card.id}/art/original", "set_id": printing.set_id,
        "set_name": card_set.name if card_set else "Übernommener Produktbestand",
        "set_code": printing.set_code, "provider": printing.external_provider,
        "provider_rarity_name": printing.provider_rarity_name, "rarity": printing.rarity,
        "card_type": card.card_type, "archetype": details.archetype if details else None,
        "rule": rule_json(rule) if rule else None, "currency_balance": funds, **stock,
        "crafting_enabled": bool(allowed and rule and rule.crafting_enabled and switches["crafting_enabled"]),
        "dismantling_enabled": bool(allowed and rule and rule.dismantling_enabled and switches["dismantling_enabled"])}


class CardAction(Command):
    card_printing_id: int = Field(ge=1, strict=True)
    quantity: int = Field(default=1, ge=1, le=1000, strict=True)
    quote_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Preview(CardAction):
    type: str = Field(pattern=r"^(craft|dismantle)$")


def quote(db, uid, printing_id, quantity, kind):
    p = db.get(CardPrinting, printing_id)
    if not p: raise HTTPException(404, "Kartenausgabe nicht gefunden.")
    row = card_json(db, uid, p)
    if quantity > control(db)["max_quantity"]: raise HTTPException(400, "Menge überschreitet das Aktionslimit.")
    if not row[kind + "ing_enabled" if kind == "craft" else "dismantling_enabled"]:
        raise HTTPException(409, "Diese Ausgabe ist für diese Aktion gesperrt oder ihre Rarität ist noch nicht zugeordnet.")
    rule = row["rule"]
    amount = quantity * rule["craft_cost" if kind == "craft" else "dismantle_value"]
    if kind == "craft" and row["currency_balance"] < amount: raise HTTPException(409, "Nicht genügend CP dieser Rarität.")
    if kind == "dismantle" and row["dismantle_available_quantity"] < quantity:
        raise HTTPException(409, "Nicht genügend freie, ungeschützte Exemplare. Handel, Duelle und Kartenschutz werden berücksichtigt.")
    result = {"type": kind, "card_printing_id": printing_id, "card_id": p.card_id, "name": row["name"],
        "rarity": rule["rarity_key"], "currency_key": rule["currency_key"], "quantity": quantity,
        "currency_amount": amount, "balance_before": row["currency_balance"],
        "new_balance": row["currency_balance"] + (amount if kind == "dismantle" else -amount),
        "quantity_before": row["quantity"], "new_quantity": row["quantity"] + (quantity if kind == "craft" else -quantity),
        "available_quantity": row["dismantle_available_quantity"], "rule_version": rule["version"]}
    from app.modules.grants import digest
    return {**result, "quote_hash": digest(result)}


def execute_card(db, user, payload, kind, source=None):
    result = quote(db, user.id, payload.card_printing_id, payload.quantity, kind)
    if payload.quote_hash and payload.quote_hash != result["quote_hash"]:
        raise HTTPException(409, "Bestand, CP oder Regeln haben sich geändert. Bitte Vorschau neu laden.")
    p = db.get(CardPrinting, payload.card_printing_id)
    source = source or f"{kind}_tx_{uuid4()}"
    amount = result["currency_amount"] * (1 if kind == "dismantle" else -1)
    tx = book_currency(db, user.id, result["currency_key"], amount, source, kind, p.id, payload.quantity, result["rarity"])
    if kind == "craft":
        key = f"printing:{p.id}"
        variant = db.scalar(select(CardVariant).where(CardVariant.key == key))
        if not variant:
            variant = CardVariant(key=key, card_id=p.card_id, printing_id=p.id, rarity=p.rarity, legacy=False)
            db.add(variant); db.flush()
        change_stock(db, user.id, variant, payload.quantity, "craft", source)
    else:
        _, stocks = holdings(db, user.id, p.id)
        ledger = reservation_totals(db)
        remaining = payload.quantity
        for stock, variant in sorted(stocks, key=lambda row: row[0].id):
            if stock.bound: continue
            free = max(0, stock.quantity - max(stock.reserved, ledger.get((user.id, variant.id, False), 0)))
            take = min(remaining, free)
            if take:
                change_stock(db, user.id, variant, -take, "dismantle", f"{source}:stock:{stock.id}")
                remaining -= take
            if remaining == 0: break
        if remaining: raise HTTPException(409, "Der freie Variantenbestand hat sich geändert.")
    event = "card_crafted" if kind == "craft" else "card_dismantled"
    emit(db, user.id, event, source, {"card_printing_id": p.id, "card_id": p.card_id,
        "rarity": result["rarity"], "quantity": payload.quantity, "currency_key": result["currency_key"],
        "currency_amount": abs(amount), "source_ref": source})
    return {**result, "success": True, "transaction_id": tx.id, "source_ref": source,
        "quantity_crafted" if kind == "craft" else "quantity_dismantled": payload.quantity,
        "currency_spent" if kind == "craft" else "currency_earned": abs(amount)}


@router.get("/balances")
def balances(database: Database, user=Depends(current_user)):
    return wallet(database, user.id)


@router.get("/rules")
def rules(database: Database, user=Depends(current_user)):
    return [rule_json(r) for r in database.scalars(select(CraftingRarityRule).order_by(CraftingRarityRule.sort_order, CraftingRarityRule.id))]


@router.get("/filters")
def filters(database: Database, user=Depends(current_user)):
    return {"sets": [{"id": row.id, "name": row.name} for row in database.scalars(select(CardSet).where(CardSet.id.in_(select(CardPrinting.set_id))).order_by(CardSet.name))],
        "types": [v for v in database.scalars(select(Card.card_type).distinct().order_by(Card.card_type)) if v],
        "archetypes": [v for v in database.scalars(select(CardDetails.archetype).distinct().order_by(CardDetails.archetype)) if v]}


@router.get("/cards")
def cards(database: Database, user=Depends(current_user), search: str = Query("", max_length=100),
          rarity: str = "", set_id: int | None = None, card_id: int | None = None, card_type: str = "", archetype: str = "",
          only_craftable: bool = False, only_affordable: bool = False, owned_only: bool = False,
          duplicates_only: bool = False, page: Page = 1, page_size: PageSize = 36):
    normal, provider = aliased(CraftingRarityRule), aliased(CraftingRarityRule)
    normalized_provider = func.lower(func.replace(CardPrinting.provider_rarity_name, " ", "_"))
    stmt = select(CardPrinting, Card, CardDetails, CardSet).join(Card, Card.id == CardPrinting.card_id).outerjoin(
        CardDetails, CardDetails.card_id == Card.id).outerjoin(CardSet, CardSet.id == CardPrinting.set_id).outerjoin(
        normal, normal.rarity_key == CardPrinting.rarity).outerjoin(provider, provider.rarity_key == normalized_provider).outerjoin(
        UserCraftingBalance, (UserCraftingBalance.user_id == user.id) & (UserCraftingBalance.currency_key == func.coalesce(provider.currency_key, normal.currency_key)))
    if search: stmt = stmt.where(or_(Card.name.icontains(search, autoescape=True), CardDetails.name_de.icontains(search, autoescape=True), CardPrinting.set_code.icontains(search, autoescape=True)))
    if rarity: stmt = stmt.where(func.coalesce(provider.rarity_key, normal.rarity_key, CardPrinting.rarity) == rarity)
    if set_id: stmt = stmt.where(CardPrinting.set_id == set_id)
    if card_id: stmt = stmt.where(Card.id == card_id)
    if card_type: stmt = stmt.where(Card.card_type.icontains(card_type, autoescape=True))
    if archetype: stmt = stmt.where(CardDetails.archetype.icontains(archetype, autoescape=True))
    if owned_only or duplicates_only:
        owned = select(CardVariant.printing_id).join(VariantInventory, VariantInventory.variant_id == CardVariant.id).where(
            VariantInventory.user_id == user.id).group_by(CardVariant.printing_id).having(func.sum(VariantInventory.quantity) > (1 if duplicates_only else 0))
        stmt = stmt.where(CardPrinting.id.in_(owned))
    if only_craftable or only_affordable:
        stmt = stmt.where(CardPrinting.rarity.is_not(None), func.coalesce(provider.crafting_enabled, normal.crafting_enabled).is_(True),
            ~select(SpecialCard.id).where(SpecialCard.card_id == Card.id).exists())
        if not control(database)["crafting_enabled"]: stmt = stmt.where(False)
    if only_affordable: stmt = stmt.where(func.coalesce(UserCraftingBalance.balance, 0) >= func.coalesce(provider.craft_cost, normal.craft_cost))
    ledger = reservation_totals(database)
    return paged(database, stmt.order_by(func.coalesce(CardDetails.name_de, Card.name), CardPrinting.id), page, page_size,
        lambda row: card_json(database, user.id, *row, ledger=ledger))


@router.get("/cards/{card_printing_id}")
def card_detail(card_printing_id: int, database: Database, user=Depends(current_user)):
    p = database.get(CardPrinting, card_printing_id)
    if not p: raise HTTPException(404, "Kartenausgabe nicht gefunden.")
    return card_json(database, user.id, p)


@router.post("/preview")
def preview_action(payload: Preview, database: Database, user=Depends(current_user)):
    return quote(database, user.id, payload.card_printing_id, payload.quantity, payload.type)


def perform(payload, database, authorization, idempotency_key, kind):
    user = writer(database, authorization, idempotency_key)
    code = action("crafting:" + kind, payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    return finish(database, user, idempotency_key, code, execute_card(database, user, payload, kind))


@router.post("/craft")
def craft(payload: CardAction, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    return perform(payload, database, authorization, idempotency_key, "craft")


@router.post("/dismantle")
def dismantle(payload: CardAction, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    return perform(payload, database, authorization, idempotency_key, "dismantle")


class Preference(Command):
    protected_quantity: int = Field(ge=0, le=1000000, strict=True)
    favorite: bool = Field(default=False, strict=True)


@router.post("/cards/{printing_id}/preference")
def preference(printing_id: int, payload: Preference, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = writer(database, authorization, idempotency_key)
    code = action(f"crafting:protect:{printing_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    if not database.get(CardPrinting, printing_id): raise HTTPException(404, "Ausgabe nicht gefunden.")
    stock, _ = holdings(database, user.id, printing_id)
    if payload.protected_quantity > stock["unbound_quantity"]: raise HTTPException(400, "Schutzmenge übersteigt deinen ungebundenen Bestand.")
    row = database.scalar(select(UserCardPreference).where(UserCardPreference.user_id == user.id, UserCardPreference.card_printing_id == printing_id))
    if not row: row = UserCardPreference(user_id=user.id, card_printing_id=printing_id); database.add(row)
    row.protected_quantity = payload.protected_quantity; row.favorite = payload.favorite
    return finish(database, user, idempotency_key, code, payload.model_dump())


class PlayerSettings(Command):
    keep_one: bool = Field(strict=True)


@router.get("/settings")
def get_settings(database: Database, user=Depends(current_user)):
    row = database.get(UserCraftingSettings, user.id)
    return {"keep_one": row.keep_one if row else True, "control": control(database)}


@router.post("/settings")
def save_settings(payload: PlayerSettings, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = writer(database, authorization, idempotency_key); code = action("crafting:settings", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(UserCraftingSettings, user.id)
    if not row: row = UserCraftingSettings(user_id=user.id); database.add(row)
    row.keep_one = payload.keep_one
    return finish(database, user, idempotency_key, code, payload.model_dump())


class Bulk(Command):
    keep_quantity: int = Field(default=3, ge=0, le=1000, strict=True)
    quote_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def bulk_quote(db, uid, keep):
    if not control(db)["bulk_enabled"]: raise HTTPException(409, "Sammelzerlegung ist derzeit deaktiviert.")
    ids = db.scalars(select(CardVariant.printing_id).join(VariantInventory).where(VariantInventory.user_id == uid,
        VariantInventory.bound.is_(False), VariantInventory.quantity > 0, CardVariant.printing_id.is_not(None)).distinct()).all()
    items, totals = [], {}
    for pid in ids:
        p = db.get(CardPrinting, pid); data = card_json(db, uid, p)
        if not data["dismantling_enabled"]: continue
        count = min(data["dismantle_available_quantity"], max(0, data["unbound_quantity"] - data["reserved"] - max(keep, data["effective_protected"])))
        if count > control(db)["max_quantity"]: raise HTTPException(409, "Ein Bestand überschreitet das Sammellimit. Bitte diesen zuerst einzeln zerlegen.")
        if count:
            line = quote(db, uid, pid, count, "dismantle"); items.append(line)
            totals[line["currency_key"]] = totals.get(line["currency_key"], 0) + line["currency_amount"]
    if len(items) > 2000: raise HTTPException(409, "Zu viele Ausgaben für eine Sammelzerlegung.")
    from app.modules.grants import digest
    result = {"items": items, "totals": totals, "card_quantity": sum(i["quantity"] for i in items), "keep_quantity": keep}
    return {**result, "quote_hash": digest(result)}


@router.post("/duplicates/preview")
def duplicates_preview(payload: Bulk, database: Database, user=Depends(current_user)):
    return bulk_quote(database, user.id, payload.keep_quantity)


@router.post("/duplicates/dismantle")
def duplicates(payload: Bulk, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = writer(database, authorization, idempotency_key); code = action("crafting:duplicates", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    result = bulk_quote(database, user.id, payload.keep_quantity)
    if not payload.quote_hash or payload.quote_hash != result["quote_hash"]:
        raise HTTPException(409, "Sammelvorschau fehlt oder ist veraltet. Bitte neu prüfen.")
    if not result["items"]: raise HTTPException(409, "Keine ungeschützten Duplikate verfügbar.")
    # Balances change between lines of the same currency. The enclosing quote
    # validated every line before any mutation; do not re-use stale balance hashes.
    for line in result["items"]:
        execute_card(database, user, CardAction(card_printing_id=line["card_printing_id"], quantity=line["quantity"]), "dismantle")
    return finish(database, user, idempotency_key, code, {**result, "success": True, "balances": wallet(database, user.id)})


def tx_json(row):
    return {**{key: getattr(row, key) for key in ("id", "user_id", "type", "card_printing_id", "rarity_key", "currency_key", "card_quantity", "currency_amount", "balance_before", "balance_after", "source_ref")}, "created_at": row.created_at.isoformat() + "Z"}


@router.get("/history")
def history(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 25):
    return paged(database, select(CraftingTransaction).where(CraftingTransaction.user_id == user.id).order_by(CraftingTransaction.id.desc()), page, page_size, lambda row: tx_json(row[0]))


@admin_router.get("/rules")
def admin_rules(database: Database):
    mapped = [rule_json(r) for r in database.scalars(select(CraftingRarityRule).order_by(CraftingRarityRule.sort_order, CraftingRarityRule.id))]
    known = {r["rarity_key"] for r in mapped}
    available = set(database.scalars(select(CardPrinting.rarity).distinct())) | set(database.scalars(select(CardPrinting.provider_rarity_name).distinct()))
    return {"rules": mapped, "currencies": [{"key": c.key, "display_name": c.display_name} for c in database.scalars(select(CraftingCurrency))],
        "unmapped": sorted({rarity_key(k) for k in available if k} - known)}


class RuleCommand(AdminCommand):
    rarity_key: str = Field(min_length=1, max_length=120)
    currency_key: str = Field(pattern=r"^[a-z0-9_]{1,95}_cp$")
    display_name: str = Field(min_length=1, max_length=120)
    dismantle_value: int = Field(default=10, ge=0, le=100000, strict=True)
    craft_cost: int = Field(default=30, ge=1, le=1000000, strict=True)
    crafting_enabled: bool = Field(default=True, strict=True)
    dismantling_enabled: bool = Field(default=True, strict=True)
    sort_order: int = Field(default=0, ge=0, le=10000, strict=True)
    version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def no_profit(self):
        if self.craft_cost <= self.dismantle_value: raise ValueError("Crafting muss mehr CP kosten als Zerlegen einbringt.")
        self.rarity_key = rarity_key(self.rarity_key)
        return self


def save_rule(rule_id, payload, database, authorization, key):
    actor = administrator(database, authorization, key, payload)
    code = action(f"crafting:rule:{rule_id}", payload)
    previous = replay(database, actor, key, code)
    if previous is not None: return previous
    observed = {rarity_key(k) for k in database.scalars(select(CardPrinting.rarity).distinct()) if k}
    observed |= {rarity_key(k) for k in database.scalars(select(CardPrinting.provider_rarity_name).distinct()) if k}
    observed |= {rarity_key(k) for k in database.scalars(select(Card.rarity).distinct()) if k}
    if payload.rarity_key not in observed: raise HTTPException(400, "Diese Rarität ist im vorhandenen Katalog nicht belegt.")
    row = database.get(CraftingRarityRule, rule_id) if rule_id else None
    if rule_id and not row: raise HTTPException(404, "Regel nicht gefunden.")
    if row and (payload.rarity_key != row.rarity_key or payload.version != row.version): raise HTTPException(409, "Regel wurde geändert; bitte neu laden.")
    if not row and database.scalar(select(CraftingRarityRule.id).where(CraftingRarityRule.rarity_key == payload.rarity_key)):
        raise HTTPException(409, "Diese Rarität hat bereits eine Regel.")
    if not database.get(CraftingCurrency, payload.currency_key):
        expected = re.sub(r"[^a-z0-9_]", "", payload.rarity_key) + "_cp"
        if payload.currency_key != expected: raise HTTPException(400, "Neue Währungen müssen zur belegten Rarität gehören.")
        database.add(CraftingCurrency(key=payload.currency_key, display_name=payload.display_name + " CP")); database.flush()
    before = rule_json(row) if row else None
    if row is None: row = CraftingRarityRule(rarity_key=payload.rarity_key); database.add(row)
    for field, value in payload.model_dump(exclude={"password", "reason", "version", "rarity_key"}).items(): setattr(row, field, value)
    row.version = (row.version or 0) + 1; database.flush()
    audit(database, actor, actor.id, "crafting_rule", {"reason": payload.reason, "before": before, "after": rule_json(row)})
    return finish(database, actor, key, code, rule_json(row))


@admin_router.post("/rules")
def create_rule(payload: RuleCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    return save_rule(None, payload, database, authorization, idempotency_key)


@admin_router.put("/rules/{rule_id}")
@admin_router.post("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    return save_rule(rule_id, payload, database, authorization, idempotency_key)


@admin_router.get("/transactions")
def transactions(database: Database, user_id: int | None = None, page: Page = 1, page_size: PageSize = 25):
    stmt = select(CraftingTransaction)
    if user_id: stmt = stmt.where(CraftingTransaction.user_id == user_id)
    return paged(database, stmt.order_by(CraftingTransaction.id.desc()), page, page_size, lambda row: tx_json(row[0]))


@admin_router.get("/users/{user_id}/balances")
def admin_balances(user_id: int, database: Database):
    target(database, user_id)
    return wallet(database, user_id)


class Adjustment(AdminCommand):
    currency_key: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=-1000000, le=1000000, strict=True)


@admin_router.post("/users/{user_id}/adjust")
def adjust(user_id: int, payload: Adjustment, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, ids=[user_id])
    code = action(f"crafting:adjust:{user_id}", payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    target(database, user_id)
    if not payload.amount: raise HTTPException(400, "Die Korrektur darf nicht null sein.")
    tx = book_currency(database, user_id, payload.currency_key, payload.amount, f"craft_admin_{uuid4()}", "admin_adjustment")
    audit(database, actor, user_id, "crafting_adjustment", {"reason": payload.reason, **tx_json(tx)})
    return finish(database, actor, idempotency_key, code, tx_json(tx))


class ControlCommand(AdminCommand):
    crafting_enabled: bool = Field(strict=True)
    dismantling_enabled: bool = Field(strict=True)
    bulk_enabled: bool = Field(strict=True)
    max_quantity: int = Field(ge=1, le=1000, strict=True)
    version: int = Field(ge=1, strict=True)


@admin_router.get("/settings")
def admin_settings(database: Database): return control(database)


@admin_router.post("/settings")
def save_control(payload: ControlCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action("crafting:control", payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(CraftingControl, 1)
    if not row or row.version != payload.version: raise HTTPException(409, "Einstellungen wurden geändert; bitte neu laden.")
    before = control(database)
    for field in ("crafting_enabled", "dismantling_enabled", "bulk_enabled", "max_quantity"): setattr(row, field, getattr(payload, field))
    row.version += 1
    audit(database, actor, actor.id, "crafting_settings", {"reason": payload.reason, "before": before, "after": control(database)})
    return finish(database, actor, idempotency_key, code, control(database))


@admin_router.get("/stats")
def stats(database: Database):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    totals = database.execute(select(CraftingTransaction.type, func.sum(CraftingTransaction.card_quantity)).where(CraftingTransaction.created_at >= today).group_by(CraftingTransaction.type)).all()
    currencies = database.execute(select(CraftingTransaction.currency_key, func.sum(CraftingTransaction.currency_amount)).where(CraftingTransaction.created_at >= today).group_by(CraftingTransaction.currency_key)).all()
    gross = database.execute(select(CraftingTransaction.currency_key,
        func.sum(case((CraftingTransaction.currency_amount > 0, CraftingTransaction.currency_amount), else_=0)),
        func.sum(case((CraftingTransaction.currency_amount < 0, -CraftingTransaction.currency_amount), else_=0))).where(
        CraftingTransaction.created_at >= today).group_by(CraftingTransaction.currency_key)).all()
    top = {}
    for kind in ("craft", "dismantle"):
        row = database.execute(select(CraftingTransaction.card_printing_id, Card.name, func.sum(CraftingTransaction.card_quantity).label("quantity")).join(CardPrinting, CardPrinting.id == CraftingTransaction.card_printing_id).join(Card, Card.id == CardPrinting.card_id).where(CraftingTransaction.type == kind).group_by(CraftingTransaction.card_printing_id, Card.name).order_by(func.sum(CraftingTransaction.card_quantity).desc()).limit(1)).first()
        top[kind] = {"card_printing_id": row[0], "name": row[1], "quantity": row[2]} if row else None
    average = database.scalar(select(func.sum(-CraftingTransaction.currency_amount) * 1.0 / func.nullif(func.sum(CraftingTransaction.card_quantity), 0)).where(CraftingTransaction.type == "craft"))
    return {"day_start_utc": today.isoformat()+"Z", "today": dict(totals), "currency_net_today": dict(currencies),
        "currency_today": [{"currency_key": row[0], "earned": row[1], "spent": row[2]} for row in gross], "top": top, "average_craft_cost": average}
