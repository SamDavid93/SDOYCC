"""Published community cards, compensating corrections and resumable grant batches."""
import base64
import csv
import io
import json
from uuid import uuid4
from typing import Literal
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from sqlalchemy import select, func
from app.api import card_payload
from app.core.permissions import admin_reader
from app.db.models import (Card, CardDetails, SpecialCard, User, GrantBatch, GrantBatchRow,
    CardVariant, VariantInventory, UserBooster, InventoryTransaction, DiamondTransaction, GrantItem, Grant,
    AdminAuditEvent, InventoryReservation, MarketListing, MarketProposal)
from app.modules.admin import Database, Page, PageSize
from app.modules.workflow import entity_page as paged
from app.modules.economy import book_diamonds, finish, replay
from app.modules.inventory import change_stock
from app.modules.grants import Draft, Position, preview, apply_grant, digest
from app.modules.workflow import AdminCommand, Auth, Key, administrator, action, audit, notice, writer

router = APIRouter(prefix="/api/admin/advanced", dependencies=[Depends(admin_reader)])
art_router = APIRouter()

class SpecialDraft(AdminCommand):
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=1, max_length=3000)
    edition: str = Field(min_length=1, max_length=120)
    rarity: Literal["common", "rare", "super_rare", "ultra_rare", "secret_rare"]
    tradable: bool = True
    supply_limit: int | None = Field(None, ge=1, le=1000000, strict=True)
    image: str = Field(min_length=1, max_length=5600000)

def image_data(value):
    try:
        raw = base64.b64decode(value.split(",", 1)[-1], validate=True)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in {"PNG", "JPEG", "WEBP"} or not (100 <= im.width <= 3000 and 100 <= im.height <= 4200) or getattr(im, "n_frames", 1) != 1:
                raise ValueError()
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            clean = io.BytesIO(); im.convert("RGB").save(clean, format="JPEG", quality=90)
        return base64.b64encode(clean.getvalue()).decode()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(400, "Bitte ein gültiges PNG-, JPEG- oder WebP-Bild bis 4 MB und 100–3000 × 100–4200 Pixel verwenden.") from None

@router.get("/special-cards")
def specials(database: Database, page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(SpecialCard, Card).join(Card).order_by(SpecialCard.id.desc()), page, page_size,
        lambda r: {"id": r[0].id, "card_id": r[1].id, "name": r[1].name, "state": r[0].state, "edition": r[0].edition,
            "tradable": r[0].tradable, "issued": r[0].issued, "supply_limit": r[0].supply_limit, "card": card_payload(r[1])})

@router.post("/special-cards")
def special_create(payload: SpecialDraft, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action("special-create", payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    clean = image_data(payload.image)
    card = Card(external_provider="sdoycc-community", external_id="community:" + str(uuid4()), name=payload.name,
        card_set=payload.edition, set_code="SDOYCC", rarity=payload.rarity, card_type="Community", attribute="", image_url="community")
    database.add(card); database.flush()
    database.add(CardDetails(card_id=card.id, name_de=payload.name, description_de=payload.description))
    row = SpecialCard(card_id=card.id, description=payload.description, edition=payload.edition, tradable=payload.tradable,
        supply_limit=payload.supply_limit, image_data=clean, image_type="image/jpeg")
    database.add(row); database.flush()
    audit(database, actor, actor.id, "special_create", {"card_id": card.id, "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, {"id": row.id, "card_id": card.id, "state": row.state})

class SpecialState(AdminCommand):
    state: Literal["active", "archived"]

@router.post("/special-cards/{special_id}/state")
def special_state(special_id: int, payload: SpecialState, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action(f"special-state:{special_id}", payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(SpecialCard, special_id)
    if not row: raise HTTPException(404, "Sonderkarte nicht gefunden.")
    before = row.state; row.state = payload.state
    audit(database, actor, actor.id, "special_state", {"card_id": row.card_id, "before": before, "after": row.state, "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, {"id": row.id, "state": row.state})

@art_router.get("/api/community/cards/{card_id}/image")
def special_image(card_id: int, database: Database):
    row = database.scalar(select(SpecialCard).where(SpecialCard.card_id == card_id))
    if not row: raise HTTPException(404, "Bild nicht gefunden.")
    return Response(base64.b64decode(row.image_data), media_type=row.image_type,
        headers={"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"})

class Correction(AdminCommand):
    user_id: int = Field(ge=1)
    confirmation: str
    kind: Literal["points", "card", "pack"]
    reference_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=1000000, strict=True)

def correction_preview(db, p):
    user = db.get(User, p.user_id)
    if not user or not user.twitch_id: raise HTTPException(400, "Twitch-Zielkonto fehlt.")
    if user.username != p.confirmation: raise HTTPException(400, "Zielbenutzernamen exakt bestätigen.")
    if p.kind == "points":
        original = db.get(DiamondTransaction, p.reference_id)
        if not original or original.user_id != user.id or original.amount <= 0: raise HTTPException(400, "Positive Originalbuchung fehlt.")
        corrected = -(db.scalar(select(func.sum(DiamondTransaction.amount)).where(DiamondTransaction.reference.like(f"correction:points:{original.id}:%"))) or 0)
        before = user.credits; maximum = original.amount - corrected
        item = None
    elif p.kind == "card":
        original = db.get(InventoryTransaction, p.reference_id)
        if not original or original.user_id != user.id or original.amount <= 0: raise HTTPException(400, "Positive Originalbewegung fehlt.")
        if db.scalar(select(InventoryTransaction.id).where(InventoryTransaction.user_id == user.id,
            InventoryTransaction.variant_id == original.variant_id, InventoryTransaction.id > original.id,
            InventoryTransaction.reason == "trade_out")):
            raise HTTPException(409, "Seit der Originalbuchung wurden Exemplare dieser Variante weitergetauscht. Eine automatische Rücknahme ist nicht eindeutig; gesondert klären.")
        corrected = -(db.scalar(select(func.sum(InventoryTransaction.amount)).where(InventoryTransaction.reference.like(f"correction:card:{original.id}:%"))) or 0)
        item = db.scalar(select(VariantInventory).where(VariantInventory.user_id == user.id, VariantInventory.variant_id == original.variant_id, VariantInventory.bound == original.bound))
        before = item.quantity if item else 0; maximum = min(original.amount - corrected, before - (item.reserved if item else 0))
    else:
        original = db.get(GrantItem, p.reference_id)
        grant = db.get(Grant, original.grant_id) if original else None
        if not original or original.kind != "pack" or grant.user_id != user.id: raise HTTPException(400, "Original-Packvergabe fehlt.")
        prior = db.scalars(select(AdminAuditEvent).where(AdminAuditEvent.action == "correction", AdminAuditEvent.target_id == user.id)).all()
        corrected = sum(d.get("quantity", 0) for e in prior if (d := json.loads(e.details_json)).get("kind") == "pack" and d.get("reference_id") == original.id)
        item = db.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == original.booster_id))
        before = item.quantity if item else 0; maximum = original.quantity - corrected
    if p.quantity > min(maximum, before): raise HTTPException(409, "Originalmenge oder frei verfügbarer Bestand reicht für diese Korrektur nicht aus.")
    return user, original, item, {"user_id": user.id, "username": user.username, "kind": p.kind, "reference_id": p.reference_id,
        "quantity": p.quantity, "before": before, "after": before - p.quantity, "reason": p.reason}

@router.get("/correction-sources/{user_id}")
def correction_sources(user_id: int, database: Database, actor=Depends(admin_reader), kind: Literal["points", "card", "pack"] = "points", page: Page = 1, page_size: PageSize = 20):
    if actor.role != "super_admin": raise HTTPException(403, "Korrekturen nur durch Hauptadministratoren.")
    if kind == "points":
        return paged(database, select(DiamondTransaction).where(DiamondTransaction.user_id == user_id, DiamondTransaction.amount > 0).order_by(DiamondTransaction.id.desc()),
            page, page_size, lambda r: {"id": r.id, "amount": r.amount, "reason": r.reason, "created_at": r.created_at.isoformat()+"Z"})
    if kind == "card":
        return paged(database, select(InventoryTransaction, Card.name).join(CardVariant, CardVariant.id == InventoryTransaction.variant_id).join(Card, Card.id == CardVariant.card_id).where(
            InventoryTransaction.user_id == user_id, InventoryTransaction.amount > 0).order_by(InventoryTransaction.id.desc()),
            page, page_size, lambda r: {"id": r[0].id, "amount": r[0].amount, "name": r[1], "created_at": r[0].created_at.isoformat()+"Z"})
    from app.db.models import BoosterPack
    return paged(database, select(GrantItem, BoosterPack.name).join(Grant, Grant.id == GrantItem.grant_id).join(BoosterPack, BoosterPack.id == GrantItem.booster_id).where(
        Grant.user_id == user_id, GrantItem.kind == "pack").order_by(GrantItem.id.desc()), page, page_size,
        lambda r: {"id": r[0].id, "quantity": r[0].quantity, "name": r[1]})

@router.post("/corrections/preview")
def preview_correction(payload: Correction, database: Database, actor=Depends(admin_reader)):
    if actor.role != "super_admin": raise HTTPException(403, "Nur Hauptadministratoren dürfen korrigieren.")
    result = correction_preview(database, payload)[3]
    return {**result, "preview_hash": digest(result)}

class ExecuteCorrection(Correction):
    preview_hash: str

@router.post("/corrections")
def correct(payload: ExecuteCorrection, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, [payload.user_id])
    code = action("correction", payload)
    previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    user, original, stock, result = correction_preview(database, payload)
    if digest(result) != payload.preview_hash: raise HTTPException(409, "Bestand geändert. Vorschau erneuern.")
    aid = audit(database, actor, user.id, "correction", result)
    ref = f"correction:{payload.kind}:{original.id}:{aid}"
    if payload.kind == "points": book_diamonds(database, user, -payload.quantity, "admin_correction", ref)
    elif payload.kind == "card": change_stock(database, user.id, database.get(CardVariant, original.variant_id), -payload.quantity, "admin_correction", ref, original.bound)
    else: stock.quantity -= payload.quantity
    notice(database, user.id, "Bestandskorrektur", f"{payload.reason} · {payload.quantity} zurückgenommen. Beleg #{aid}.", "/account")
    return finish(database, actor, idempotency_key, code, {**result, "audit_id": aid})

class BatchDraft(AdminCommand):
    user_ids: list[int] = Field(min_length=1, max_length=100)
    items: list[Position] = Field(min_length=1, max_length=20)

def batch_preview(db, actor, p):
    rows = []
    for uid in sorted(set(p.user_ids)):
        try:
            snap = preview(db, actor, Draft(user_id=uid, reason=p.reason, items=p.items))
            rows.append({"user_id": uid, "username": snap["username"], "state": "ready", "preview": snap})
        except HTTPException as error:
            rows.append({"user_id": uid, "state": "rejected", "error": error.detail})
    return {"rows": rows, "preview_hash": digest(rows)}

@router.post("/batches/preview")
def batch_preview_api(payload: BatchDraft, database: Database, actor=Depends(admin_reader)):
    if actor.role not in {"admin", "super_admin"}: raise HTTPException(403, "Keine Vergabeberechtigung.")
    return batch_preview(database, actor, payload)

class BatchCreate(BatchDraft):
    preview_hash: str

@router.post("/batches")
def create_batch(payload: BatchCreate, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, payload.user_ids, super_only=False)
    code = action("batch-create", payload); previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    snap = batch_preview(database, actor, payload)
    if snap["preview_hash"] != payload.preview_hash: raise HTTPException(409, "Empfängerliste geändert. Vorschau erneuern.")
    if any(r["state"] != "ready" for r in snap["rows"]): raise HTTPException(400, "Abgelehnte Empfänger zuerst aus der Liste entfernen.")
    batch = GrantBatch(actor_id=actor.id, reason=payload.reason, items_json=json.dumps([i.model_dump() for i in payload.items]))
    database.add(batch); database.flush()
    for row in snap["rows"]: database.add(GrantBatchRow(batch_id=batch.id, user_id=row["user_id"]))
    audit(database, actor, actor.id, "batch_create", {"batch_id": batch.id, "user_ids": sorted(set(payload.user_ids)), "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, {"id": batch.id})

@router.get("/batches")
def batches(database: Database, page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(GrantBatch).order_by(GrantBatch.id.desc()), page, page_size,
        lambda b: {"id": b.id, "reason": b.reason, "created_at": b.created_at.isoformat() + "Z"})

@router.get("/batches/{batch_id}")
def batch_detail(batch_id: int, database: Database):
    batch = database.get(GrantBatch, batch_id)
    if not batch: raise HTTPException(404, "Sammelvergabe fehlt.")
    return {"id": batch.id, "reason": batch.reason, "items": json.loads(batch.items_json), "rows": [
        {"id": row.id, "user_id": row.user_id, "username": name, "state": row.state, "result": json.loads(row.result_json)}
        for row, name in database.execute(select(GrantBatchRow, User.username).join(User).where(GrantBatchRow.batch_id == batch_id).order_by(GrantBatchRow.id))]}

@router.post("/batches/{batch_id}/rows/{row_id}")
def run_row(batch_id: int, row_id: int, payload: AdminCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, super_only=False)
    row = database.get(GrantBatchRow, row_id); batch = database.get(GrantBatch, batch_id)
    if not row or not batch or row.batch_id != batch_id: raise HTTPException(404, "Empfängerzeile fehlt.")
    if actor.role != "super_admin" and actor.id != batch.actor_id: raise HTTPException(403, "Fremde Sammelvergabe.")
    if row.state == "done": return json.loads(row.result_json)
    from app.modules.workflow import lock_users
    lock_users(database, [actor.id, row.user_id])
    draft = Draft(user_id=row.user_id, reason=batch.reason, items=json.loads(batch.items_json))
    try:
        with database.begin_nested():
            snap = preview(database, actor, draft)
            result = apply_grant(database, database.get(User, row.user_id), actor, draft, snap, digest(draft.model_dump()), source="batch")
        row.state = "done"; row.result_json = json.dumps(result)
    except HTTPException as error:
        row.state = "rejected"; result = {"error": error.detail}; row.result_json = json.dumps(result)
    database.commit()
    return result

@router.post("/batches/{batch_id}/run")
def run_batch(batch_id: int, payload: AdminCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload, super_only=False)
    checked_hash, actor_id = actor.password_hash, actor.id
    batch = database.get(GrantBatch, batch_id)
    if not batch or (actor.role != "super_admin" and batch.actor_id != actor.id): raise HTTPException(403, "Sammelvergabe nicht zugänglich.")
    ids = list(database.scalars(select(GrantBatchRow.id).where(GrantBatchRow.batch_id == batch_id).order_by(GrantBatchRow.id)))
    database.commit()
    for row_id in ids:
        actor = writer(database, authorization, idempotency_key)
        if actor.id != actor_id or actor.password_hash != checked_hash or actor.role not in {"admin", "super_admin"}:
            raise HTTPException(403, "Berechtigung geändert. Verbleibende Empfänger wurden nicht ausgeführt.")
        batch = database.get(GrantBatch, batch_id)
        if actor.role != "super_admin" and batch.actor_id != actor.id: raise HTTPException(403, "Berechtigung geändert.")
        row = database.get(GrantBatchRow, row_id)
        if row.state == "done": database.commit(); continue
        from app.modules.workflow import lock_users
        lock_users(database, [actor.id, row.user_id])
        draft = Draft(user_id=row.user_id, reason=batch.reason, items=json.loads(batch.items_json))
        try:
            with database.begin_nested():
                snap = preview(database, actor, draft)
                result = apply_grant(database, database.get(User, row.user_id), actor, draft, snap, digest(draft.model_dump()), source="batch")
            row.state = "done"; row.result_json = json.dumps(result)
        except HTTPException as error:
            row.state = "rejected"; row.result_json = json.dumps({"error": error.detail})
        database.commit()
    return batch_detail(batch_id, database)

@router.get("/operations")
def operations(database: Database):
    from app.db.models import InventoryItem, SeasonXpEvent, SeasonProgress, Season, BoosterOpening
    from sqlalchemy import exists, literal, cast, String
    totals = {(u,c): q for u,c,q in database.execute(select(InventoryItem.user_id, InventoryItem.card_id, InventoryItem.quantity)) if q}
    variants = {(u,c): q for u,c,q in database.execute(select(VariantInventory.user_id, CardVariant.card_id, func.sum(VariantInventory.quantity)).join(CardVariant).group_by(VariantInventory.user_id, CardVariant.card_id)) if q}
    reservations = {(u,v): q for u,v,q in database.execute(select(InventoryReservation.user_id, InventoryReservation.variant_id, func.sum(InventoryReservation.quantity)).where(InventoryReservation.active.is_(True)).group_by(InventoryReservation.user_id, InventoryReservation.variant_id)) if q}
    reserved = {(u,v): q for u,v,q in database.execute(select(VariantInventory.user_id, VariantInventory.variant_id, VariantInventory.reserved).where(VariantInventory.bound.is_(False))) if q}
    stock = {(u,v,b): q for u,v,b,q in database.execute(select(VariantInventory.user_id, VariantInventory.variant_id, VariantInventory.bound, VariantInventory.quantity)) if q}
    journal = {(u,v,b): q for u,v,b,q in database.execute(select(InventoryTransaction.user_id, InventoryTransaction.variant_id, InventoryTransaction.bound, func.sum(InventoryTransaction.amount)).group_by(InventoryTransaction.user_id, InventoryTransaction.variant_id, InventoryTransaction.bound)) if q}
    xp = {(u,s): q for u,s,q in database.execute(select(SeasonProgress.user_id, SeasonProgress.season_id, SeasonProgress.xp)) if q}
    xp_journal = {(u,s): q for u,s,q in database.execute(select(SeasonXpEvent.user_id, SeasonXpEvent.season_id, func.sum(SeasonXpEvent.xp)).group_by(SeasonXpEvent.user_id, SeasonXpEvent.season_id)) if q}
    processed = exists(select(SeasonXpEvent.id).where(SeasonXpEvent.user_id == BoosterOpening.user_id,
        SeasonXpEvent.season_id == Season.id, SeasonXpEvent.reference == literal("opening:") + cast(BoosterOpening.id, String))).correlate(BoosterOpening, Season)
    missing = database.scalar(select(func.count()).select_from(BoosterOpening).join(User).join(Season,
        (Season.starts_at <= BoosterOpening.created_at) & (Season.ends_at > BoosterOpening.created_at)).where(Season.state == "published", User.twitch_id.is_not(None), ~processed))
    return {"inventory_consistent": totals == variants, "journal_consistent": stock == journal,
        "reservations_consistent": reservations == reserved, "reserved_cards": sum(reserved.values()),
        "xp_consistent": xp == xp_journal, "pending_xp_events": missing,
        "pending_batches": database.scalar(select(func.count(GrantBatchRow.id)).where(GrantBatchRow.state != "done")),
        "open_listings": database.scalar(select(func.count(MarketListing.id)).where(MarketListing.state == "open"))}

@router.get("/users.csv")
def users_export(database: Database, actor=Depends(admin_reader), search: str = Query("", max_length=100)):
    if actor.role != "super_admin": raise HTTPException(403, "Export nur für Hauptadministratoren.")
    if database.scalar(select(func.count(User.id)).where(User.username.icontains(search, autoescape=True))) > 10000:
        raise HTTPException(400, "Mehr als 10.000 Konten. Bitte den Export durch eine Namenssuche eingrenzen.")
    out = io.StringIO(); writer = csv.writer(out, delimiter=";")
    writer.writerow(["ID", "Twitch-Name", "Rolle", "Aktiv", "Sammelpunkte"])
    for u in database.scalars(select(User).where(User.username.icontains(search, autoescape=True)).order_by(User.id).limit(10000)):
        writer.writerow([u.id, "'" + u.username, u.role, u.is_active, u.credits])
    return Response("\ufeff" + out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="sdoycc-konten.csv"'})
