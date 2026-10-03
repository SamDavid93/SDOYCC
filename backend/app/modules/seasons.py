"""Immutable free seasons; UTC opening events, periodic quests and shared reward grants."""
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select, func
from app.api import current_user
from app.core.permissions import admin_reader
from app.db.models import Season, SeasonProgress, SeasonXpEvent, SeasonClaim, BoosterOpening, User
from app.modules.admin import Database, Page, PageSize
from app.modules.workflow import entity_page as paged
from app.modules.economy import lock_wallet, replay, finish
from app.modules.grants import Position, Draft, preview, apply_grant, digest
from app.modules.workflow import Command, AdminCommand, Auth, Key, administrator, writer, action, audit

router = APIRouter(prefix="/api/seasons")
admin_router = APIRouter(prefix="/api/admin/seasons", dependencies=[Depends(admin_reader)])

class Level(Command):
    xp: int = Field(ge=1, le=10000000, strict=True)
    items: list[Position] = Field(min_length=1, max_length=20)

class Quest(Command):
    period: Literal["daily", "weekly"]
    openings: int = Field(ge=1, le=100, strict=True)
    xp: int = Field(ge=1, le=100000, strict=True)

class SeasonDraft(AdminCommand):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    starts_at: datetime
    ends_at: datetime
    claim_until: datetime
    opening_xp: int = Field(ge=1, le=10000, strict=True)
    levels: list[Level] = Field(min_length=1, max_length=100)
    quests: list[Quest] = Field(default_factory=list, max_length=2)

    @field_validator("starts_at", "ends_at", "claim_until")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None: raise ValueError("Zeitpunkt benötigt eine Zeitzone.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @model_validator(mode="after")
    def ordered(self):
        if not self.starts_at < self.ends_at <= self.claim_until or self.claim_until - self.starts_at > timedelta(days=400):
            raise ValueError("Start, Ende und Abholfrist müssen geordnet sein; maximal 400 Tage.")
        if [x.xp for x in self.levels] != sorted({x.xp for x in self.levels}): raise ValueError("XP-Schwellen müssen streng steigen.")
        if len({q.period for q in self.quests}) != len(self.quests): raise ValueError("Nur eine Aufgabe je Periode.")
        return self

def status(season, now=None):
    now = now or datetime.utcnow()
    if season.state != "published": return season.state
    if now < season.starts_at: return "scheduled"
    if now < season.ends_at: return "active"
    if now < season.claim_until: return "ended"
    return "archived"

def season_json(row):
    return {"id": row.id, "name": row.name, "description": row.description, "state": status(row), "version": row.version,
        "starts_at": row.starts_at.isoformat()+"Z", "ends_at": row.ends_at.isoformat()+"Z", "claim_until": row.claim_until.isoformat()+"Z", **json.loads(row.rules_json)}

def budget(payload):
    totals = {k: sum(i.quantity for level in payload.levels for i in level.items if i.kind == k) for k in ["points", "card", "special", "pack"]}
    example = []
    for per_day in [1, 2, 5]:
        days = max(1, (payload.ends_at-payload.starts_at).days)
        xp = days * per_day * payload.opening_xp
        xp += sum((days if q.period == "daily" else days//7) * q.xp for q in payload.quests if per_day * (1 if q.period == "daily" else 7) >= q.openings)
        example.append({"openings_per_day": per_day, "xp": xp, "level": sum(xp >= l.xp for l in payload.levels)})
    return {"per_user": totals, "examples": example, "note": "Beispiele rechnen mit Standardboostern zu 100 Punkten. Aufgabenperioden richten sich nach UTC; angebrochene Perioden können abweichen."}

def validate_rewards(db, actor, payload):
    # Validate products without applying the administrator's current inventory-dependent deck limit.
    for level in payload.levels:
        for i in level.items:
            if i.kind == "pack":
                from app.modules.grants import valid_pack
                pack, _ = valid_pack(db, i.booster_id)
                if pack.product_type == "structure_deck": raise HTTPException(400, "Saisonbelohnungen verwenden Standardbooster, damit das persönliche Structure-Deck-Limit keine Abholung verhindert.")
            if i.kind == "special":
                from app.db.models import SpecialCard
                special = db.scalar(select(SpecialCard).where(SpecialCard.card_id == i.card_id))
                if special and special.supply_limit is not None: raise HTTPException(400, "Begrenzt aufgelegte Sonderkarten sind für allgemein zugesagte Saisonbelohnungen ungeeignet.")
        preview(db, None, Draft(user_id=actor.id, reason="Saison-Belohnung prüfen", items=level.items), system=True)

@admin_router.post("/preview")
def preview_season(payload: SeasonDraft, database: Database, actor=Depends(admin_reader)):
    if actor.role != "super_admin": raise HTTPException(403, "Saisons verwaltet der Hauptadministrator.")
    validate_rewards(database, actor, payload)
    return budget(payload)

@admin_router.post("")
def create_season(payload: SeasonDraft, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action("season-create", payload); previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    validate_rewards(database, actor, payload)
    rules = {"opening_xp": payload.opening_xp, "levels": [l.model_dump() for l in payload.levels], "quests": [q.model_dump() for q in payload.quests], "budget": budget(payload)}
    row = Season(name=payload.name, description=payload.description, starts_at=payload.starts_at, ends_at=payload.ends_at,
        claim_until=payload.claim_until, rules_json=json.dumps(rules))
    database.add(row); database.flush()
    audit(database, actor, actor.id, "season_create", {"season_id": row.id, "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, season_json(row))

@admin_router.get("")
def admin_seasons(database: Database, page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(Season).order_by(Season.id.desc()), page, page_size, season_json)

@admin_router.post("/{season_id}/publish")
def publish(season_id: int, payload: AdminCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action(f"season-publish:{season_id}", payload); previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(Season, season_id)
    if not row or row.state != "draft": raise HTTPException(409, "Nur Entwürfe können veröffentlicht werden.")
    if row.starts_at < datetime.utcnow()-timedelta(minutes=2): raise HTTPException(400, "Saisonbeginn liegt in der Vergangenheit. Neuen Entwurf mit zukünftigem Beginn anlegen.")
    overlap = database.scalar(select(Season.id).where(Season.state == "published", Season.starts_at < row.ends_at, Season.ends_at > row.starts_at))
    if overlap: raise HTTPException(409, "Der Zeitraum überschneidet sich mit einer veröffentlichten Saison.")
    rules = json.loads(row.rules_json)
    draft = SeasonDraft(name=row.name, description=row.description, starts_at=row.starts_at.replace(tzinfo=timezone.utc),
        ends_at=row.ends_at.replace(tzinfo=timezone.utc), claim_until=row.claim_until.replace(tzinfo=timezone.utc),
        opening_xp=rules["opening_xp"], levels=rules["levels"], quests=rules["quests"], reason=payload.reason, password=payload.password)
    validate_rewards(database, actor, draft)
    row.state = "published"
    audit(database, actor, actor.id, "season_publish", {"season_id": row.id, "version": row.version, "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, season_json(row))

class Extension(AdminCommand):
    claim_until: datetime
    version: int

@admin_router.post("/{season_id}/extend-claims")
def extend(season_id: int, payload: Extension, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, payload)
    code = action(f"season-extend:{season_id}", payload); previous = replay(database, actor, idempotency_key, code)
    if previous is not None: return previous
    row = database.get(Season, season_id)
    if not row or row.state != "published" or row.version != payload.version: raise HTTPException(409, "Saisonversion geändert.")
    if not payload.claim_until.tzinfo: raise HTTPException(400, "Zeitzone fehlt.")
    until = payload.claim_until.astimezone(timezone.utc).replace(tzinfo=None)
    if not row.claim_until < until <= row.claim_until + timedelta(days=90): raise HTTPException(400, "Die Abholfrist kann um höchstens 90 Tage verlängert werden.")
    before = row.claim_until.isoformat()+"Z"; row.claim_until = until; row.version += 1
    audit(database, actor, actor.id, "season_extend", {"season_id": row.id, "before": before, "after": until.isoformat()+"Z", "reason": payload.reason})
    return finish(database, actor, idempotency_key, code, season_json(row))

def period_start(time, period):
    start = time.replace(hour=0, minute=0, second=0, microsecond=0)
    return start if period == "daily" else start - timedelta(days=start.weekday())

def award_xp(db, season, uid, ref, amount):
    if db.scalar(select(SeasonXpEvent.id).where(SeasonXpEvent.season_id == season.id, SeasonXpEvent.user_id == uid, SeasonXpEvent.reference == ref)): return
    progress = db.scalar(select(SeasonProgress).where(SeasonProgress.season_id == season.id, SeasonProgress.user_id == uid))
    if not progress:
        progress = SeasonProgress(season_id=season.id, user_id=uid, xp=0); db.add(progress)
    progress.xp += amount
    db.add(SeasonXpEvent(season_id=season.id, user_id=uid, reference=ref, xp=amount)); db.flush()

def process_opening(db, opening):
    user = db.get(User, opening.user_id)
    if not user.twitch_id: return
    season = db.scalar(select(Season).where(Season.state == "published", Season.starts_at <= opening.created_at, Season.ends_at > opening.created_at))
    if not season: return
    rules = json.loads(season.rules_json)
    award_xp(db, season, user.id, f"opening:{opening.id}", rules["opening_xp"])
    for quest in rules["quests"]:
        start = period_start(opening.created_at, quest["period"]); end = start + timedelta(days=1 if quest["period"] == "daily" else 7)
        count = db.scalar(select(func.count(BoosterOpening.id)).where(BoosterOpening.user_id == user.id,
            BoosterOpening.created_at >= max(start, season.starts_at), BoosterOpening.created_at < min(end, season.ends_at)))
        if count >= quest["openings"]: award_xp(db, season, user.id, f"quest:{quest['period']}:{start.isoformat()}", quest["xp"])

def sync(db, uid, season):
    processed = select(SeasonXpEvent.reference).where(SeasonXpEvent.user_id == uid, SeasonXpEvent.season_id == season.id)
    from sqlalchemy import cast, String, literal
    openings = db.scalars(select(BoosterOpening).where(BoosterOpening.user_id == uid, BoosterOpening.created_at >= season.starts_at,
        BoosterOpening.created_at < season.ends_at, (literal("opening:") + cast(BoosterOpening.id, String)).not_in(processed)).order_by(BoosterOpening.id))
    for opening in openings: process_opening(db, opening)

def progress_payload(db, user, season):
    sync(db, user.id, season)
    xp = db.scalar(select(SeasonProgress.xp).where(SeasonProgress.user_id == user.id, SeasonProgress.season_id == season.id)) or 0
    claims = {c.level: c.grant_id for c in db.scalars(select(SeasonClaim).where(SeasonClaim.user_id == user.id, SeasonClaim.season_id == season.id))}
    result = season_json(season); rules = json.loads(season.rules_json); now = datetime.utcnow()
    result.update(xp=xp, level=sum(xp >= level["xp"] for level in rules["levels"]), claims=claims,
        can_claim=now < season.claim_until and now >= season.starts_at)
    result["quest_progress"] = []
    for q in rules["quests"]:
        start = period_start(min(now, season.ends_at-timedelta(microseconds=1)), q["period"])
        end = start+timedelta(days=1 if q["period"] == "daily" else 7)
        count = db.scalar(select(func.count(BoosterOpening.id)).where(BoosterOpening.user_id == user.id,
            BoosterOpening.created_at >= max(start, season.starts_at), BoosterOpening.created_at < min(end, season.ends_at)))
        result["quest_progress"].append({**q, "count": count, "resets_at": min(end, season.ends_at).isoformat()+"Z"})
    return result

@router.get("/current")
def current(database: Database, user=Depends(current_user)):
    now = datetime.utcnow()
    row = database.scalar(select(Season).where(Season.state == "published", Season.starts_at <= now, Season.claim_until > now).order_by(Season.starts_at.desc()))
    if not row: return {"season": None}
    lock_wallet(database, user)
    result = progress_payload(database, user, row); database.commit()
    return {"season": result}

@router.get("/me/history")
def history(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 20):
    return paged(database, select(Season).where(Season.state == "published").order_by(Season.starts_at.desc()), page, page_size, season_json)

@router.get("/{season_id}/me")
def season_me(season_id: int, database: Database, user=Depends(current_user)):
    row = database.get(Season, season_id)
    if not row or row.state != "published": raise HTTPException(404, "Saison nicht verfügbar.")
    lock_wallet(database, user); result = progress_payload(database, user, row); database.commit()
    return result

@router.post("/{season_id}/rewards/{level}/claim")
def claim(season_id: int, level: int, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    user = writer(database, authorization, idempotency_key); code = f"season-claim:{season_id}:{level}"
    previous = replay(database, user, idempotency_key, code)
    if previous is not None: return previous
    existing = database.scalar(select(SeasonClaim).where(SeasonClaim.user_id == user.id, SeasonClaim.season_id == season_id, SeasonClaim.level == level))
    if existing:
        from app.db.models import Grant
        return json.loads(database.get(Grant, existing.grant_id).result_json)
    row = database.get(Season, season_id); now = datetime.utcnow()
    if not row or row.state != "published" or not row.starts_at <= now < row.claim_until: raise HTTPException(409, "Die Abholfrist ist nicht offen.")
    progress = progress_payload(database, user, row)
    if level < 1 or level > len(progress["levels"]) or progress["xp"] < progress["levels"][level-1]["xp"]:
        raise HTTPException(409, "Diese Belohnung ist noch nicht freigeschaltet.")
    draft = Draft(user_id=user.id, reason=f"{row.name} · Stufe {level}", items=progress["levels"][level-1]["items"])
    snap = preview(database, None, draft, system=True)
    result = apply_grant(database, user, None, draft, snap, digest({"season": row.id, "level": level, "user": user.id}), source="season")
    database.add(SeasonClaim(season_id=row.id, user_id=user.id, level=level, grant_id=result["grant_id"]))
    return finish(database, user, idempotency_key, code, result)
