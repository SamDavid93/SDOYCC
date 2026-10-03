"""Whole-package trades with explicit reservations and immutable settlement receipts."""
import json
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select, func, or_, delete, exists
from app.api import current_user, card_payload
from app.core.permissions import admin_reader
from app.core.config import settings
from app.db.models import (User, Card, CardVariant, VariantInventory, InventoryReservation, MarketListing,
    MarketProposal, TradeSettlement, TradeReport, TradeBlock, TradeRestriction, CardPrinting, CardSet, SpecialCard, MarketCardIndex, MarketRevision, CardDetails)
from app.modules.admin import Database, Page, PageSize
from app.modules.workflow import entity_page as paged
from app.modules.inventory import change_stock, migrate_user
from app.modules.economy import replay, finish
from app.modules.workflow import Command, AdminCommand, Auth, Key, writer, administrator, action, lock_users, notice, audit, mutex

router = APIRouter(prefix="/api/trade")

@router.get("/config")
def trading_config():
    return {"proposal_hours": settings.trade_proposal_hours, "max_listings": settings.trade_max_listings, "max_proposals": settings.trade_max_proposals}

class Item(Command):
    variant_id: int = Field(ge=1, strict=True)
    quantity: int = Field(ge=1, le=100, strict=True)

class Wanted(Command):
    card_id: int = Field(ge=1, strict=True)
    quantity: int = Field(ge=1, le=100, strict=True)

class ListingDraft(Command):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1000)
    items: list[Item] = Field(min_length=1, max_length=100)
    wanted: list[Wanted] = Field(default_factory=list, max_length=100)
    days: int = Field(default=7, ge=1, le=30, strict=True)
    complete_set_id: int | None = Field(None, ge=1, strict=True)

class Version(Command):
    version: int = Field(ge=1, strict=True)

class ProposalDraft(Version):
    items: list[Item] = Field(min_length=1, max_length=100)

class Counter(Version):
    wanted: list[Wanted] = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)

def eligible(db, uid):
    user = db.get(User, uid)
    restriction = db.get(TradeRestriction, uid)
    if not user or not user.is_active or not user.twitch_id or not user.password_hash:
        raise HTTPException(403, "Handel benötigt ein aktives, registriertes Twitch-Konto.")
    if restriction and restriction.until > datetime.utcnow():
        raise HTTPException(403, f"Dieses Konto ist bis {restriction.until.strftime('%d.%m.%Y %H:%M')} UTC für den Handel gesperrt.")
    return user

def pair_allowed(db, a, b):
    eligible(db, a); eligible(db, b)
    if a == b: raise HTTPException(400, "Ein Tausch mit dir selbst ist nicht möglich.")
    if db.scalar(select(TradeBlock.id).where(or_((TradeBlock.user_id == a) & (TradeBlock.blocked_id == b), (TradeBlock.user_id == b) & (TradeBlock.blocked_id == a)))):
        raise HTTPException(403, "Zwischen diesen Konten ist kein Handel möglich.")

def package(db, uid, items):
    migrate_user(db, uid)
    if len({i.variant_id for i in items}) != len(items): raise HTTPException(400, "Varianten bitte zu einer Menge zusammenfassen.")
    result = []
    for i in items:
        kind = db.get(CardVariant, i.variant_id)
        stock = db.scalar(select(VariantInventory).where(VariantInventory.user_id == uid, VariantInventory.variant_id == i.variant_id, VariantInventory.bound.is_(False)))
        if not kind or kind.legacy: raise HTTPException(400, "Ungeklärter Altbestand ist nicht handelbar.")
        special = db.scalar(select(SpecialCard).where(SpecialCard.card_id == kind.card_id))
        if special and not special.tradable: raise HTTPException(400, "Diese Sonderkarte ist nicht handelbar.")
        if not stock or stock.quantity - stock.reserved < i.quantity: raise HTTPException(409, "Nicht genug ungebundene, frei verfügbare Karten.")
        result.append({"variant_id": kind.id, "quantity": i.quantity, "card_id": kind.card_id,
            "card": {**card_payload(db.get(Card, kind.card_id)), "rarity": kind.rarity}, "booster_id": kind.booster_id})
    return result

def wanted_items(db, items):
    if len({i.card_id for i in items}) != len(items): raise HTTPException(400, "Gesuchte Karten bitte zusammenfassen.")
    result = []
    for i in items:
        card = db.get(Card, i.card_id)
        if not card: raise HTTPException(400, "Gesuchte Karte fehlt.")
        result.append({**i.model_dump(), "name": card_payload(card)["name"]})
    return result

def reserve(db, uid, items, reference):
    for i in items:
        stock = db.scalar(select(VariantInventory).where(VariantInventory.user_id == uid, VariantInventory.variant_id == i["variant_id"], VariantInventory.bound.is_(False)))
        if not stock or stock.quantity - stock.reserved < i["quantity"]: raise HTTPException(409, "Karten inzwischen reserviert.")
        stock.reserved += i["quantity"]
        db.add(InventoryReservation(user_id=uid, variant_id=i["variant_id"], quantity=i["quantity"], reference=reference))
    db.flush()

def release(db, reference):
    for r in db.scalars(select(InventoryReservation).where(InventoryReservation.reference == reference, InventoryReservation.active.is_(True))):
        stock = db.scalar(select(VariantInventory).where(VariantInventory.user_id == r.user_id, VariantInventory.variant_id == r.variant_id, VariantInventory.bound.is_(False)))
        if not stock or stock.reserved < r.quantity: raise HTTPException(409, "Reservierungsbestand inkonsistent. Verwaltung verständigen.")
        stock.reserved -= r.quantity; r.active = False
    db.flush()

def close_proposal(db, p, state):
    if p.state != "pending": return
    release(db, f"proposal:{p.id}"); p.state = state
    notice(db, p.user_id, "Tauschangebot aktualisiert", "Dein Angebot wurde beendet; die Reservierung ist aufgehoben.", "/trade")

def close_listing(db, listing, state):
    if listing.state not in {"open", "draft"}: return
    release(db, f"listing:{listing.id}"); listing.state = state
    for p in db.scalars(select(MarketProposal).where(MarketProposal.listing_id == listing.id, MarketProposal.state == "pending")):
        close_proposal(db, p, "invalidated")
    notice(db, listing.owner_id, "Handelsanzeige beendet", listing.title + " · Reservierungen aufgehoben.", "/trade")

def cleanup(db):
    """Caller owns mutex. Stable account locks also serialize against pack openings."""
    listings = db.scalars(select(MarketListing).where(MarketListing.state == "open")).all()
    proposals = db.scalars(select(MarketProposal).where(MarketProposal.state == "pending")).all()
    lock_users(db, [x.owner_id for x in listings] + [x.user_id for x in proposals])
    now = datetime.utcnow()
    for listing in listings:
        try: eligible(db, listing.owner_id)
        except HTTPException: close_listing(db, listing, "moderated"); continue
        if listing.expires_at <= now: close_listing(db, listing, "expired")
    for p in proposals:
        if p.state != "pending": continue
        try: eligible(db, p.user_id)
        except HTTPException: close_proposal(db, p, "invalidated"); continue
        if p.expires_at <= now: close_proposal(db, p, "expired")
    db.flush()

def start(db, auth, key):
    user = writer(db, auth, key)
    cleanup(db)
    eligible(db, user.id)
    return user

def listing_json(db, row):
    return {"id": row.id, "owner_id": row.owner_id, "owner": db.get(User, row.owner_id).display_name, "title": row.title,
        "description": row.description, "items": json.loads(row.offered_json), "wanted": json.loads(row.wanted_json),
        "state": "expired" if row.state == "open" and row.expires_at <= datetime.utcnow() else row.state,
        "version": row.version, "expires_at": row.expires_at.isoformat() + "Z", "complete_set": json.loads(row.set_snapshot_json)}

def index_listing(db, row):
    db.add(MarketRevision(listing_id=row.id, version=row.version, snapshot_json=json.dumps(listing_json(db, row))))
    db.execute(delete(MarketCardIndex).where(MarketCardIndex.listing_id == row.id))
    for side, items in [("offered", json.loads(row.offered_json)), ("wanted", json.loads(row.wanted_json))]:
        for item in items:
            db.add(MarketCardIndex(listing_id=row.id, side=side, card_id=item["card_id"],
                variant_key=item.get("variant_id", item["card_id"]), quantity=item["quantity"],
                rarity=item.get("card", {}).get("rarity")))
    db.flush()

@router.get("/stock")
def available(database: Database, user=Depends(current_user), search: str = Query("", max_length=100), page: Page = 1, page_size: PageSize = 30):
    statement = select(VariantInventory, CardVariant, Card).join(CardVariant, CardVariant.id == VariantInventory.variant_id).join(Card, Card.id == CardVariant.card_id).where(
        VariantInventory.user_id == user.id, VariantInventory.bound.is_(False), VariantInventory.quantity > 0, CardVariant.legacy.is_(False),
        or_(Card.name.icontains(search, autoescape=True), Card.details.has(CardDetails.name_de.icontains(search, autoescape=True))),
        ~exists(select(SpecialCard.id).where(SpecialCard.card_id == Card.id, SpecialCard.tradable.is_(False)))).order_by(VariantInventory.id)
    return paged(database, statement, page, page_size, lambda r: {"variant_id": r[1].id, "card": {**card_payload(r[2]), "rarity": r[1].rarity},
        "quantity": r[0].quantity, "reserved": r[0].reserved, "available": r[0].quantity - r[0].reserved})

@router.get("/sets/{set_id}/preview")
def set_package(set_id: int, database: Database, user=Depends(current_user)):
    card_ids = database.scalars(select(CardPrinting.card_id).where(CardPrinting.set_id == set_id).distinct().order_by(CardPrinting.card_id)).all()
    if not card_ids or len(card_ids) > 100: raise HTTPException(400, "Sets müssen zwischen 1 und 100 Kartenidentitäten enthalten; größere Sets bitte in Pakete teilen.")
    items, missing = [], []
    for cid in card_ids:
        stock = database.scalar(select(VariantInventory).join(CardVariant).where(VariantInventory.user_id == user.id,
            VariantInventory.bound.is_(False), VariantInventory.quantity > VariantInventory.reserved, CardVariant.card_id == cid, CardVariant.legacy.is_(False)).order_by(CardVariant.id))
        if stock: items.append({"variant_id": stock.variant_id, "quantity": 1, "card": {**card_payload(database.get(Card, cid)), "rarity": database.get(CardVariant, stock.variant_id).rarity}})
        else: missing.append(card_payload(database.get(Card, cid))["name"])
    return {"items": items, "missing": missing, "complete": not missing, "definition": "Je eine Kartenidentität; unterschiedliche nachgewiesene Ausgaben erlaubt."}

@router.get("/listings")
def listings(database: Database, user=Depends(current_user), search: str = Query("", max_length=100), mine: bool = False,
        card_id: int | None = None, set_id: int | None = None, rarity: str = Query("", max_length=80),
        side: Literal["offered", "wanted"] = "offered", fulfillable: bool = False, page: Page = 1, page_size: PageSize = 20):
    statement = select(MarketListing).order_by(MarketListing.id.desc())
    if mine: statement = statement.where(MarketListing.owner_id == user.id)
    else: statement = statement.where(MarketListing.state == "open", MarketListing.expires_at > datetime.utcnow())
    if search: statement = statement.where(or_(MarketListing.title.icontains(search, autoescape=True), MarketListing.description.icontains(search, autoescape=True)))
    if not mine:
        statement = statement.where(MarketListing.owner_id.in_(select(User.id).where(User.is_active.is_(True))),
            ~MarketListing.owner_id.in_(select(TradeRestriction.user_id).where(TradeRestriction.until > datetime.utcnow())))
    if card_id or set_id or rarity:
        matched = select(MarketCardIndex.listing_id).where(MarketCardIndex.side == side)
        if card_id: matched = matched.where(MarketCardIndex.card_id == card_id)
        if set_id: matched = matched.where(MarketCardIndex.card_id.in_(select(CardPrinting.card_id).where(CardPrinting.set_id == set_id)))
        if rarity: matched = matched.where(MarketCardIndex.rarity == rarity)
        statement = statement.where(MarketListing.id.in_(matched))
    if fulfillable:
        amounts = select(CardVariant.card_id.label("card_id"), func.sum(VariantInventory.quantity - VariantInventory.reserved).label("available")).join(VariantInventory).where(
            VariantInventory.user_id == user.id, VariantInventory.bound.is_(False), CardVariant.legacy.is_(False),
            ~exists(select(SpecialCard.id).where(SpecialCard.card_id == CardVariant.card_id, SpecialCard.tradable.is_(False)))).group_by(CardVariant.card_id).subquery()
        insufficient = select(MarketCardIndex.listing_id).outerjoin(amounts, amounts.c.card_id == MarketCardIndex.card_id).where(
            MarketCardIndex.side == "wanted", func.coalesce(amounts.c.available, 0) < MarketCardIndex.quantity)
        statement = statement.where(~MarketListing.id.in_(insufficient))
    return paged(database, statement, page, page_size, lambda row: listing_json(database, row))

@router.post("/listings")
def create_listing(payload: ListingDraft, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action("listing-create", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    if database.scalar(select(func.count(MarketListing.id)).where(MarketListing.owner_id == user.id, MarketListing.state.in_(["open", "draft"]))) >= settings.trade_max_listings:
        raise HTTPException(400, f"Höchstens {settings.trade_max_listings} offene Anzeigen oder Entwürfe sind erlaubt.")
    items = package(database, user.id, payload.items); wanted = wanted_items(database, payload.wanted)
    complete_set = None
    if payload.complete_set_id:
        card_set = database.get(CardSet, payload.complete_set_id)
        card_ids = set(database.scalars(select(CardPrinting.card_id).where(CardPrinting.set_id == payload.complete_set_id)))
        if not card_set or not card_ids or not card_ids <= {i["card_id"] for i in items}:
            raise HTTPException(400, "Das Paket enthält nicht jede Kartenidentität des angegebenen Sets.")
        complete_set = {"id": card_set.id, "name": card_set.name, "card_ids": sorted(card_ids), "definition": "Je eine Kartenidentität; nachgewiesene alternative Ausgaben erlaubt."}
    row = MarketListing(owner_id=user.id, title=payload.title, description=payload.description, offered_json=json.dumps(items),
        wanted_json=json.dumps(wanted), set_snapshot_json=json.dumps(complete_set), expires_at=datetime.utcnow() + timedelta(days=payload.days))
    database.add(row); database.flush()
    index_listing(database, row)
    return finish(database, user, idempotency_key, code, listing_json(database, row))

@router.get("/listings/{listing_id}")
def detail(listing_id: int, database: Database, user=Depends(current_user)):
    row = database.get(MarketListing, listing_id)
    if not row or (row.state == "draft" and row.owner_id != user.id): raise HTTPException(404, "Anzeige nicht gefunden.")
    result = listing_json(database, row)
    result["versions"] = [{"version": r.version, "created_at": r.created_at.isoformat()+"Z", "snapshot": json.loads(r.snapshot_json)}
        for r in database.scalars(select(MarketRevision).where(MarketRevision.listing_id == row.id).order_by(MarketRevision.version.desc()).limit(100))]
    proposals = select(MarketProposal).where(MarketProposal.listing_id == row.id)
    if row.owner_id != user.id: proposals = proposals.where(MarketProposal.user_id == user.id)
    result["proposals"] = [{"id": p.id, "user_id": p.user_id, "user": database.get(User, p.user_id).display_name,
        "items": json.loads(p.items_json), "state": p.state, "version": p.version, "expires_at": p.expires_at.isoformat()+"Z"} for p in database.scalars(proposals.order_by(MarketProposal.id.desc()).limit(100))]
    return result

@router.post("/listings/{listing_id}/{operation}")
def listing_action(listing_id: int, operation: Literal["publish", "cancel"], payload: Version, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"listing-{operation}:{listing_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(MarketListing, listing_id)
    if not row or row.owner_id != user.id: raise HTTPException(403, "Nur eigene Anzeigen können geändert werden.")
    if row.version != payload.version: raise HTTPException(409, "Anzeigenversion veraltet.")
    if operation == "publish":
        if row.state != "draft" or row.expires_at <= datetime.utcnow(): raise HTTPException(409, "Dieser Entwurf kann nicht veröffentlicht werden.")
        items = package(database, user.id, [Item(variant_id=i["variant_id"], quantity=i["quantity"]) for i in json.loads(row.offered_json)])
        reserve(database, user.id, items, f"listing:{row.id}"); row.state = "open"
    else: close_listing(database, row, "cancelled")
    return finish(database, user, idempotency_key, code, listing_json(database, row))

# Fixed routes must precede a generic operation route in Starlette. This route uses a separate namespace.
@router.post("/proposals/to/{listing_id}")
def propose(listing_id: int, payload: ProposalDraft, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"proposal:{listing_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(MarketListing, listing_id)
    if not row or row.state != "open" or row.version != payload.version or row.expires_at <= datetime.utcnow(): raise HTTPException(409, "Anzeige nicht mehr offen oder Version veraltet.")
    pair_allowed(database, user.id, row.owner_id)
    if database.scalar(select(func.count(MarketProposal.id)).where(MarketProposal.user_id == user.id, MarketProposal.state == "pending")) >= settings.trade_max_proposals:
        raise HTTPException(400, f"Höchstens {settings.trade_max_proposals} verbindliche Vorschläge gleichzeitig.")
    if database.scalar(select(MarketProposal.id).where(MarketProposal.user_id == user.id, MarketProposal.listing_id == row.id, MarketProposal.state == "pending")):
        raise HTTPException(409, "Du hast bereits ein offenes Angebot für diese Anzeige.")
    items = package(database, user.id, payload.items)
    for wanted in json.loads(row.wanted_json):
        if sum(i["quantity"] for i in items if i["card_id"] == wanted["card_id"]) < wanted["quantity"]:
            raise HTTPException(400, "Das Paket erfüllt nicht alle gesuchten Kartenmengen.")
    p = MarketProposal(listing_id=row.id, user_id=user.id, version=row.version, items_json=json.dumps(items), expires_at=min(row.expires_at, datetime.utcnow()+timedelta(hours=settings.trade_proposal_hours)))
    database.add(p); database.flush(); reserve(database, user.id, items, f"proposal:{p.id}")
    notice(database, row.owner_id, "Neues Tauschangebot", user.display_name + " bietet dir ein Kartenpaket an.", f"/trade/{row.id}")
    return finish(database, user, idempotency_key, code, {"id": p.id, "state": p.state})

@router.post("/counter/{listing_id}")
def counter(listing_id: int, payload: Counter, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"counter:{listing_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(MarketListing, listing_id)
    if not row or row.owner_id != user.id: raise HTTPException(403, "Fremde Anzeige.")
    if row.state != "open" or row.version != payload.version: raise HTTPException(409, "Anzeige geändert.")
    row.wanted_json = json.dumps(wanted_items(database, payload.wanted)); row.description = payload.description; row.version += 1
    index_listing(database, row)
    for p in database.scalars(select(MarketProposal).where(MarketProposal.listing_id == row.id, MarketProposal.state == "pending")):
        close_proposal(database, p, "invalidated")
    return finish(database, user, idempotency_key, code, listing_json(database, row))

@router.post("/proposals/{proposal_id}/{operation}")
def proposal_action(proposal_id: int, operation: Literal["accept", "reject", "withdraw"], payload: Version, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"proposal-{operation}:{proposal_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    p = database.get(MarketProposal, proposal_id); row = database.get(MarketListing, p.listing_id) if p else None
    if not p or user.id != (p.user_id if operation == "withdraw" else row.owner_id): raise HTTPException(403, "Für dieses Angebot fehlen dir die Rechte.")
    if p.state != "pending" or row.state != "open" or p.version != payload.version or row.version != payload.version:
        raise HTTPException(409, "Das Angebot ist nicht mehr in dieser Version offen.")
    if operation != "accept":
        close_proposal(database, p, "withdrawn" if operation == "withdraw" else "rejected")
        return finish(database, user, idempotency_key, code, {"id": p.id, "state": p.state})
    pair_allowed(database, row.owner_id, p.user_id)
    if min(p.expires_at, row.expires_at) <= datetime.utcnow(): raise HTTPException(409, "Angebot abgelaufen.")
    give, receive = json.loads(row.offered_json), json.loads(p.items_json)
    receipt = TradeSettlement(listing_id=row.id, proposal_id=p.id, owner_id=row.owner_id, partner_id=p.user_id, result_json="{}")
    database.add(receipt); database.flush()
    for uid, items, ref in [(row.owner_id, give, f"listing:{row.id}"), (p.user_id, receive, f"proposal:{p.id}")]:
        reserved = {r.variant_id: r.quantity for r in database.scalars(select(InventoryReservation).where(InventoryReservation.reference == ref, InventoryReservation.active.is_(True)))}
        if reserved != {i["variant_id"]: i["quantity"] for i in items}: raise HTTPException(409, "Reservierung stimmt nicht mit dem Paket überein.")
        release(database, ref)
    for source, target, items in [(row.owner_id, p.user_id, give), (p.user_id, row.owner_id, receive)]:
        for i in items:
            kind = database.get(CardVariant, i["variant_id"])
            reference = f"trade:{receipt.id}:{source}:{kind.id}"
            change_stock(database, source, kind, -i["quantity"], "trade_out", reference+":out")
            change_stock(database, target, kind, i["quantity"], "trade_in", reference+":in")
    p.state = "accepted"; close_listing(database, row, "completed")
    result = {"id": receipt.id, "listing_id": row.id, "owner_id": row.owner_id, "partner_id": p.user_id,
        "owner": database.get(User, row.owner_id).display_name, "partner": database.get(User, p.user_id).display_name,
        "given": give, "received": receive, "created_at": receipt.created_at.isoformat()+"Z"}
    receipt.result_json = json.dumps(result)
    audit(database, user, p.user_id, "trade_settlement", {"settlement_id": receipt.id, "listing_id": row.id})
    for uid in [row.owner_id, p.user_id]: notice(database, uid, "Kartentausch abgeschlossen", f"Beide Kartenpakete wurden übertragen. Beleg #{receipt.id}.", "/trade")
    return finish(database, user, idempotency_key, code, result)

@router.get("/me/history")
def history(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(TradeSettlement).where(or_(TradeSettlement.owner_id == user.id, TradeSettlement.partner_id == user.id)).order_by(TradeSettlement.id.desc()),
        page, page_size, lambda row: json.loads(row.result_json))

@router.get("/me/proposals")
def my_proposals(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(MarketProposal).where(MarketProposal.user_id == user.id).order_by(MarketProposal.id.desc()), page, page_size,
        lambda p: {"id": p.id, "listing_id": p.listing_id, "state": p.state, "version": p.version, "items": json.loads(p.items_json)})

class Report(Command):
    reason: str = Field(min_length=5, max_length=500)

@router.post("/reports/{listing_id}")
def report(listing_id: int, payload: Report, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"report:{listing_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    if not database.get(MarketListing, listing_id): raise HTTPException(404, "Anzeige fehlt.")
    row = database.scalar(select(TradeReport).where(TradeReport.listing_id == listing_id, TradeReport.user_id == user.id))
    if not row:
        row = TradeReport(listing_id=listing_id, user_id=user.id, reason=payload.reason); database.add(row); database.flush()
    return finish(database, user, idempotency_key, code, {"id": row.id, "state": row.state})

class Blocking(Command):
    blocked: bool

@router.post("/blocks/{user_id}")
def blocking(user_id: int, payload: Blocking, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = start(database, authorization, idempotency_key); code = action(f"trade-block:{user_id}", payload)
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    if user.id == user_id or not database.get(User, user_id): raise HTTPException(400, "Ungültiges Zielkonto.")
    row = database.scalar(select(TradeBlock).where(TradeBlock.user_id == user.id, TradeBlock.blocked_id == user_id))
    if payload.blocked and not row: database.add(TradeBlock(user_id=user.id, blocked_id=user_id))
    if not payload.blocked and row: database.delete(row)
    if payload.blocked:
        for p, listing in database.execute(select(MarketProposal, MarketListing).join(MarketListing).where(MarketProposal.state == "pending")):
            if {p.user_id, listing.owner_id} == {user.id, user_id}: close_proposal(database, p, "invalidated")
    return finish(database, user, idempotency_key, code, {"blocked": payload.blocked})

@router.get("/moderation")
def reports(database: Database, actor=Depends(admin_reader), page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(TradeReport).order_by(TradeReport.id.desc()), page, page_size,
        lambda r: {"id": r.id, "listing_id": r.listing_id, "user_id": r.user_id, "reason": r.reason, "state": r.state})

class Moderate(AdminCommand):
    close_listing: bool = False
    restrict_days: int = Field(default=0, ge=0, le=365)

@router.post("/moderation/{report_id}")
def moderate(report_id: int, payload: Moderate, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, super_only=False)
    code = action(f"moderate:{report_id}", payload); previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    cleanup(database)
    report = database.get(TradeReport, report_id); row = database.get(MarketListing, report.listing_id) if report else None
    if not row: raise HTTPException(404, "Meldung fehlt.")
    target = database.get(User, row.owner_id)
    if actor.role != "super_admin" and target.role != "user": raise HTTPException(403, "Nur Hauptadministratoren dürfen Verwaltungskonten moderieren.")
    if target.id == actor.id: raise HTTPException(403, "Eigene Anzeigen nicht selbst moderieren.")
    if payload.restrict_days:
        restriction = database.get(TradeRestriction, target.id)
        if not restriction: restriction = TradeRestriction(user_id=target.id); database.add(restriction)
        restriction.until = datetime.utcnow()+timedelta(days=payload.restrict_days); restriction.reason = payload.reason
        for listing in database.scalars(select(MarketListing).where(MarketListing.owner_id == target.id, MarketListing.state.in_(["open", "draft"]))): close_listing(database, listing, "moderated")
        for p in database.scalars(select(MarketProposal).where(MarketProposal.user_id == target.id, MarketProposal.state == "pending")): close_proposal(database, p, "invalidated")
    if payload.close_listing: close_listing(database, row, "moderated")
    report.state = "resolved"
    audit(database, actor, target.id, "trade_moderation", {"report_id": report.id, "reason": payload.reason, "days": payload.restrict_days})
    notice(database, report.user_id, "Handelsmeldung geprüft", payload.reason, "/trade")
    return finish(database, actor, idempotency_key, code, {"id": report.id, "state": report.state})
