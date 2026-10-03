"""Atomic, previewed grants; explicit input and saved receipts, never partial delivery."""
import hashlib
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.api import translated_text
from app.core.auth import get_current_user
from app.core.booster_rules import drawable_entries, effective_pack_size, pool_size
from app.core.config import settings
from app.core.passwords import verify_password
from app.core.permissions import admin_reader
from app.core.pricing import purchase_limit
from app.core.rate_limit import throttle
from app.core.structure_decks import deck_candidates, deck_size
from app.db.models import (AdminAuditEvent, AdminMutationLock, BoosterPack, BoosterPoolEntry, Card, CardDetails,
    CardVariant, Grant, GrantItem, Notification, ProductPurchaseCounter, StructureDeckItem,
    StructureDeckBonusChoice, StructureDeckBonusSlot, User, UserBooster, VariantInventory, SpecialCard)
from app.modules.admin import Database, Page, PageSize, paged
from app.modules.economy import book_diamonds, finish, replay
from app.modules.inventory import change_stock, migrate_user, rarity_key, variant

router = APIRouter(prefix="/api/admin/grants", dependencies=[Depends(admin_reader)])


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["points", "card", "pack", "special"]
    quantity: int = Field(ge=1, le=1000000, strict=True)
    card_id: int | None = Field(None, ge=1, strict=True)
    booster_id: int | None = Field(None, ge=1, strict=True)
    rarity: str | None = Field(None, max_length=80)
    bound: bool = Field(False, strict=True)

    @model_validator(mode="after")
    def check_fields(self):
        if self.kind == "special" and (not self.card_id or self.booster_id or self.rarity):
            raise ValueError("Sonderkarte benötigt nur Karten-ID, Menge und Bindung.")
        if self.kind == "points" and (self.card_id or self.booster_id or self.rarity or self.bound):
            raise ValueError("Punkteposition enthält fremde Felder.")
        if self.kind == "pack" and (not self.booster_id or self.card_id or self.rarity or self.bound):
            raise ValueError("Packposition benötigt ausschließlich Produkt und Menge.")
        if self.kind == "card" and (not self.card_id or not self.booster_id or not self.rarity):
            raise ValueError("Kartenposition benötigt Karte, Herkunftspack und Seltenheit.")
        if self.rarity:
            self.rarity = rarity_key(self.rarity)
        if self.kind == "card" and not self.rarity:
            raise ValueError("Eine konkrete Seltenheit ist erforderlich.")
        return self


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=5, max_length=500)
    items: list[Position] = Field(min_length=1, max_length=20)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class ExecuteGrant(Draft):
    password: SecretStr = Field(min_length=1, max_length=128)
    confirmation: str = Field(min_length=1, max_length=64)
    preview_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def require_granter(actor):
    if actor.role not in {"admin", "super_admin"}:
        raise HTTPException(403, "Vergaben erfordern Administratorrechte.")


def limits(actor):
    return {"points": 1000000, "card": 1000, "pack": 100} if actor.role == "super_admin" else {
        "points": settings.admin_grant_points_limit, "card": settings.admin_grant_cards_limit, "pack": settings.admin_grant_packs_limit}


def valid_pack(database, booster_id):
    pack = database.get(BoosterPack, booster_id)
    if not pack or not pack.active:
        raise HTTPException(400, "Das gewählte Produkt ist nicht aktiv.")
    entries = deck_candidates(pack) if pack.product_type == "structure_deck" else drawable_entries(pack.entries)
    count = deck_size(pack) if pack.product_type == "structure_deck" else effective_pack_size(pack.cards_per_pack, pool_size(entries))
    if not count:
        raise HTTPException(400, "Das gewählte Produkt hat keinen gültigen Karteninhalt.")
    return pack, entries


def preview(database, actor, payload: Draft, system=False):
    if not system:
        require_granter(actor)
    user = database.get(User, payload.user_id)
    if not user:
        raise HTTPException(404, "Zielkonto nicht gefunden.")
    if not user.is_active or not user.twitch_id or user.username == "jaden-demo":
        raise HTTPException(400, "Vergaben benötigen ein aktives Twitch-Konto.")
    if not system and actor.role != "super_admin" and (user.role != "user" or user.id == actor.id):
        raise HTTPException(403, "Administratoren dürfen nur an normale Nutzer vergeben.")
    budget = {"points": 1000000, "card": 1000, "pack": 100} if system else limits(actor)
    totals = {kind: sum(item.quantity for item in payload.items if item.kind == kind or (kind == "card" and item.kind == "special")) for kind in budget}
    if any(totals[kind] > maximum for kind, maximum in budget.items()):
        raise HTTPException(400, "Die Vergabe überschreitet dein Mengenlimit pro Vorgang.")
    seen, rows = set(), []
    for item in payload.items:
        identity = (item.kind, item.card_id, item.booster_id, item.rarity, item.bound)
        if identity in seen:
            raise HTTPException(400, "Gleiche Positionen bitte zu einer Menge zusammenfassen.")
        seen.add(identity)
        row = item.model_dump()
        if item.kind == "points":
            row.update(name="Sammelpunkte", before=user.credits, after=user.credits + item.quantity)
        elif item.kind == "special":
            special = database.scalar(select(SpecialCard).where(SpecialCard.card_id == item.card_id))
            if not special or special.state != "active":
                raise HTTPException(400, "Die Sonderkarte ist nicht veröffentlicht.")
            if not special.tradable and not item.bound:
                raise HTTPException(400, "Diese Sonderkarte muss kontogebunden vergeben werden.")
            if special.supply_limit is not None and special.issued + sum(x.quantity for x in payload.items if x.kind == "special" and x.card_id == item.card_id) > special.supply_limit:
                raise HTTPException(409, "Die Auflage der Sonderkarte ist ausgeschöpft.")
            card = database.get(Card, item.card_id)
            existing = database.scalar(select(CardVariant).where(CardVariant.card_id == card.id, CardVariant.booster_id.is_(None), CardVariant.legacy.is_(False)))
            before = (database.scalar(select(VariantInventory.quantity).where(VariantInventory.user_id == user.id, VariantInventory.variant_id == existing.id, VariantInventory.bound == item.bound)) or 0) if existing else 0
            row.update(name=card.name, rarity=card.rarity, source=special.edition, issued=special.issued, limit=special.supply_limit, before=before, after=before + item.quantity)
        else:
            pack, entries = valid_pack(database, item.booster_id)
            row["source"] = pack.name
            if item.kind == "pack":
                before = database.scalar(select(UserBooster.quantity).where(UserBooster.user_id == user.id, UserBooster.booster_id == pack.id)) or 0
                counter = database.scalar(select(ProductPurchaseCounter.quantity).where(ProductPurchaseCounter.user_id == user.id, ProductPurchaseCounter.booster_id == pack.id)) or 0
                maximum = purchase_limit(pack.product_type)
                if maximum is not None and counter + item.quantity > maximum:
                    raise HTTPException(400, "Dieses Structure Deck ist pro Konto auf insgesamt drei Bezüge begrenzt, einschließlich Vergaben.")
                row.update(name=pack.name, before=before, after=before + item.quantity, limit=maximum, acquired=counter)
            else:
                if not any(entry.card_id == item.card_id and rarity_key(entry.rarity) == item.rarity for entry in entries):
                    raise HTTPException(400, "Diese Karte/Seltenheit gehört nicht zum gewählten Produkt.")
                card = database.get(Card, item.card_id)
                existing = database.scalar(select(CardVariant).where(CardVariant.card_id == item.card_id,
                    CardVariant.booster_id == item.booster_id, CardVariant.rarity == item.rarity, CardVariant.legacy.is_(False)))
                before = (database.scalar(select(VariantInventory.quantity).where(VariantInventory.user_id == user.id,
                    VariantInventory.variant_id == existing.id, VariantInventory.bound == item.bound)) or 0) if existing else 0
                row.update(name=translated_text(card.details.name_de) if card.details else None, before=before, after=before + item.quantity)
                row["name"] = row["name"] or card.name
        rows.append(row)
    result = {"user_id": user.id, "username": user.username, "reason": payload.reason, "items": rows,
              "limits": budget, "points_after": user.credits + totals["points"]}
    return {**result, "preview_hash": digest(result)}


@router.get("/limits")
def grant_limits(actor=Depends(admin_reader)):
    require_granter(actor)
    return limits(actor)


@router.post("/preview")
def preview_grant(payload: Draft, database: Database, actor=Depends(admin_reader)):
    return preview(database, actor, payload)


def apply_grant(database, user, actor, draft, snapshot, fingerprint, source="admin"):
    """Shared delivery engine. Caller owns authentication, locks, receipt and commit."""
    migrate_user(database, user.id)
    grant = Grant(user_id=user.id, actor_id=actor.id if actor else None, source=source, reason=draft.reason, payload_hash=fingerprint)
    database.add(grant); database.flush()
    for index, item in enumerate(draft.items):
        reference = f"grant:{grant.id}:{index}"
        line = GrantItem(grant_id=grant.id, kind=item.kind, quantity=item.quantity, bound=item.bound)
        if item.kind == "points":
            book_diamonds(database, user, item.quantity, "season_reward" if source == "season" else "admin_grant", reference)
        elif item.kind in {"card", "special"}:
            if item.kind == "special":
                special = database.scalar(select(SpecialCard).where(SpecialCard.card_id == item.card_id))
                special.issued += item.quantity
                rarity = database.get(Card, item.card_id).rarity
            else:
                rarity = item.rarity
            kind = variant(database, item.card_id, rarity, item.booster_id)
            change_stock(database, user.id, kind, item.quantity, "season_reward" if source == "season" else "admin_grant", reference, item.bound)
            line.variant_id = kind.id
        else:
            stock = database.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == item.booster_id))
            if stock is None:
                stock = UserBooster(user_id=user.id, booster_id=item.booster_id, quantity=0)
                database.add(stock)
            stock.quantity += item.quantity
            pack = database.get(BoosterPack, item.booster_id)
            if purchase_limit(pack.product_type) is not None:
                counter = database.scalar(select(ProductPurchaseCounter).where(ProductPurchaseCounter.user_id == user.id, ProductPurchaseCounter.booster_id == pack.id))
                if counter is None:
                    counter = ProductPurchaseCounter(user_id=user.id, booster_id=pack.id, quantity=0)
                    database.add(counter)
                counter.quantity += item.quantity
            line.booster_id = item.booster_id
        database.add(line); database.flush()
    event = AdminAuditEvent(action="grant", actor_id=actor.id if actor else None, target_id=user.id, source=source,
        details_json=json.dumps({"grant_id": grant.id, "reason": draft.reason, "items": snapshot["items"]}, ensure_ascii=False))
    database.add(event); database.flush()
    result = {**snapshot, "grant_id": grant.id, "audit_id": event.id, "created_at": grant.created_at.isoformat() + "Z"}
    grant.result_json = json.dumps(result, ensure_ascii=False)
    database.add(Notification(user_id=user.id, grant_id=grant.id))
    return result


@router.post("")
def execute_grant(payload: ExecuteGrant, database: Database, actor=Depends(admin_reader),
                  authorization: Annotated[str | None, Header()] = None,
                  idempotency_key: Annotated[str | None, Header()] = None):
    require_granter(actor)
    if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
        raise HTTPException(400, "Eine gültige Aktionskennung ist erforderlich.")
    throttle(database, [(f"admin-password:{actor.id}", 15)])
    database.refresh(actor)
    checked_hash = actor.password_hash
    if not verify_password(payload.password.get_secret_value(), checked_hash):
        raise HTTPException(403, "Dein Administrator-Passwort ist nicht korrekt.")
    fingerprint = digest(payload.model_dump(exclude={"password"}))
    insert = sqlite_insert if database.get_bind().dialect.name == "sqlite" else pg_insert
    database.execute(insert(AdminMutationLock).values(id=1, revision=0).on_conflict_do_nothing(index_elements=["id"]))
    database.execute(update(AdminMutationLock).where(AdminMutationLock.id == 1).values(revision=AdminMutationLock.revision + 1))
    for account_id in sorted({actor.id, payload.user_id}):
        database.execute(update(User).where(User.id == account_id).values(credits=User.credits).execution_options(synchronize_session=False))
    database.expire_all()
    actor = get_current_user(authorization, database)
    require_granter(actor)
    if actor.password_hash != checked_hash:
        raise HTTPException(403, "Die Anmeldung wurde geändert. Bitte neu beginnen.")
    previous = replay(database, actor, idempotency_key, "grant:" + fingerprint)
    if previous is not None:
        return previous
    snapshot = preview(database, actor, payload)
    if snapshot["username"] != payload.confirmation:
        raise HTTPException(400, "Der bestätigte Zielbenutzername stimmt nicht überein.")
    if snapshot["preview_hash"] != payload.preview_hash:
        raise HTTPException(409, "Bestand oder Vergaberegeln haben sich geändert. Bitte die Vorschau erneut laden.")
    result = apply_grant(database, database.get(User, payload.user_id), actor, payload, snapshot, fingerprint)
    return finish(database, actor, idempotency_key, "grant:" + fingerprint, result)


@router.get("/catalog")
def catalog(database: Database, actor=Depends(admin_reader), kind: Literal["card", "pack"] = "card",
            search: str = Query("", max_length=100), page: Page = 1, page_size: PageSize = 20):
    require_granter(actor)
    if kind == "pack":
        statement = select(BoosterPack.id, BoosterPack.name).where(BoosterPack.active.is_(True), BoosterPack.name.icontains(search, autoescape=True)).order_by(BoosterPack.id)
        return paged(database, statement, page, page_size, lambda row: {"id": row[0], "name": row[1]})
    statement = select(Card.id, Card.name, CardDetails.name_de).outerjoin(CardDetails, CardDetails.card_id == Card.id).where(
        or_(Card.name.icontains(search, autoescape=True), CardDetails.name_de.icontains(search, autoescape=True), Card.external_id == search)).order_by(Card.id)
    return paged(database, statement, page, page_size, lambda row: {"id": row[0], "name": translated_text(row[2]) or row[1]})


@router.get("/card-options/{card_id}")
def card_options(card_id: int, database: Database, actor=Depends(admin_reader)):
    require_granter(actor)
    candidates = select(BoosterPoolEntry.booster_id).where(BoosterPoolEntry.card_id == card_id).union(
        select(StructureDeckItem.booster_id).where(StructureDeckItem.card_id == card_id),
        select(StructureDeckBonusSlot.booster_id).join(StructureDeckBonusChoice).where(StructureDeckBonusChoice.card_id == card_id))
    options = []
    for pack_id in database.scalars(select(BoosterPack.id).where(BoosterPack.active.is_(True), BoosterPack.id.in_(candidates)).order_by(BoosterPack.id)):
        try:
            pack, entries = valid_pack(database, pack_id)
        except HTTPException:
            continue
        for rarity in sorted({rarity_key(entry.rarity) for entry in entries if entry.card_id == card_id and rarity_key(entry.rarity)}):
            options.append({"booster_id": pack.id, "name": pack.name, "rarity": rarity})
    return options


@router.get("/{grant_id}")
def receipt(grant_id: int, database: Database, actor=Depends(admin_reader)):
    require_granter(actor)
    grant = database.get(Grant, grant_id)
    if not grant:
        raise HTTPException(404, "Vergabe nicht gefunden.")
    return json.loads(grant.result_json)
