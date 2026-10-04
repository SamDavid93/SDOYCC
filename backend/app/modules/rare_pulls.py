"""Transactional chat outbox. No network or Twitch call occurs during a pack opening."""
from datetime import datetime, timedelta
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import RarePullAnnouncement
from app.db.session import get_db
from app.modules.streamerbot import bridge_auth

HIGH_RARITIES = {
    "ultra_rare": "Ultraselten", "secret_rare": "Geheim selten",
    "ultimate_rare": "Ultimativ selten", "ghost_rare": "Geisterselten",
    "starlight_rare": "Sternenlicht-selten", "collector's_rare": "Sammlerselten",
    "collectors_rare": "Sammlerselten", "collector_rare": "Sammlerselten",
    "quarter_century_secret_rare": "Jubiläums-Geheimselten",
    "platinum_secret_rare": "Platin-Geheimselten", "prismatic_secret_rare": "Prisma-Geheimselten",
    "gold_rare": "Goldselten", "gold_secret_rare": "Gold-Geheimselten",
    "premium_gold_rare": "Premium-Goldselten", "platinum_rare": "Platinselten",
}


def compact(value, limit):
    clean = " ".join(str(value).split())
    encoded = clean.encode("utf-8")
    return clean if len(encoded) <= limit else encoded[:limit - 3].decode("utf-8", errors="ignore") + "..."


def enqueue_rare_pulls(database, opening, user, booster, cards):
    if not user.twitch_id or not user.is_active:
        return
    grouped = {}
    for card in cards:
        rarity = card["rarity"].lower().replace(" ", "_")
        if rarity not in HIGH_RARITIES:
            continue
        key = (card["id"], rarity)
        if key not in grouped:
            grouped[key] = [card["name"], 0]
        grouped[key][1] += 1
    timestamp = datetime.utcnow()
    for (card_id, rarity), (name, quantity) in grouped.items():
        message = (f"Glückwunsch @{compact(user.username, 25)}! "
                   f"{quantity} × {compact(name, 150)} [{HIGH_RARITIES[rarity]}] "
                   f"aus {compact(booster.name, 150)} gezogen!")
        database.add(RarePullAnnouncement(opening_id=opening.id, card_id=card_id, rarity=rarity,
            message=message, expires_at=timestamp + timedelta(minutes=10)))


router = APIRouter(prefix="/api/integrations/streamerbot/announcements", dependencies=[Depends(bridge_auth)])
Database = Annotated[Session, Depends(get_db)]


class Channel(BaseModel):
    broadcaster_login: str = Field(min_length=1, max_length=25, pattern=r"^[A-Za-z0-9_]+$")


class Acknowledgement(Channel):
    claim_token: str = Field(min_length=32, max_length=80)


def check_channel(payload):
    if payload.broadcaster_login.lower() != settings.twitch_broadcaster_login.lower():
        raise HTTPException(403, "Falscher Twitch-Kanal")


@router.post("/claim")
def claim(payload: Channel, database: Database):
    check_channel(payload)
    timestamp = datetime.utcnow()
    available = (RarePullAnnouncement.sent_at.is_(None), RarePullAnnouncement.expires_at > timestamp,
                 or_(RarePullAnnouncement.claimed_until.is_(None), RarePullAnnouncement.claimed_until <= timestamp))
    # The conditional UPDATE arbitrates concurrent pollers on SQLite as well as
    # PostgreSQL. A claim response lost in transit becomes available again.
    candidate = database.scalar(select(RarePullAnnouncement.id).where(*available).order_by(RarePullAnnouncement.id).limit(1))
    if candidate is None:
        return {"announcement": None}
    token = secrets.token_hex(24)
    changed = database.execute(update(RarePullAnnouncement).where(RarePullAnnouncement.id == candidate, *available)
        .values(claim_token=token, claimed_until=timestamp + timedelta(seconds=60)))
    if not changed.rowcount:
        database.rollback()
        return {"announcement": None}
    record = database.get(RarePullAnnouncement, candidate)
    result = {"announcement": {"id": record.id, "message": record.message, "claim_token": token}}
    database.commit()
    return result


@router.post("/{announcement_id}/ack")
def acknowledge(announcement_id: int, payload: Acknowledgement, database: Database):
    check_channel(payload)
    record = database.get(RarePullAnnouncement, announcement_id)
    if record is None or not record.claim_token or not secrets.compare_digest(record.claim_token, payload.claim_token):
        raise HTTPException(409, "Meldung ist nicht mehr für diese Ausführung reserviert")
    if record.sent_at:
        return {"acknowledged": True}
    # Token comparison in the UPDATE also protects against a concurrent reclaim.
    changed = database.execute(update(RarePullAnnouncement).where(RarePullAnnouncement.id == announcement_id,
        RarePullAnnouncement.claim_token == payload.claim_token, RarePullAnnouncement.sent_at.is_(None))
        .values(sent_at=datetime.utcnow()))
    if not changed.rowcount:
        database.rollback()
        raise HTTPException(409, "Reservierung hat sich geändert")
    database.commit()
    return {"acknowledged": True}
