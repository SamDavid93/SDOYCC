"""Trusted Streamer.bot bridge. No Twitch developer application is required."""
import secrets
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import token_hash
from app.core.config import settings
from app.core.rate_limit import throttle
from app.db.models import RegistrationChallenge, TwitchRedemption, User
from app.db.session import get_db
from app.modules.economy import book_diamonds, lock_wallet


def bridge_auth(x_streamerbot_key: Annotated[str | None, Header()] = None) -> None:
    if len(settings.streamerbot_api_key) < 32:
        raise HTTPException(503, "Streamer.bot-Verbindung ist noch nicht eingerichtet")
    if not x_streamerbot_key or not secrets.compare_digest(x_streamerbot_key.encode(), settings.streamerbot_api_key.encode()):
        raise HTTPException(401, "Invalid bridge key")


router = APIRouter(prefix="/api/integrations/streamerbot", dependencies=[Depends(bridge_auth)])
Database = Annotated[Session, Depends(get_db)]


class TwitchIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=40, pattern=r"^[0-9]+$")
    username: str = Field(min_length=1, max_length=25, pattern=r"^[A-Za-z0-9_]+$")
    display_name: str = Field(default="", max_length=100)
    broadcaster_login: str = Field(min_length=1, max_length=25, pattern=r"^[A-Za-z0-9_]+$")

    @field_validator("username", "broadcaster_login")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.lower()


class Redemption(TwitchIdentity):
    redemption_id: str = Field(min_length=1, max_length=100)
    reward_id: str = Field(min_length=1, max_length=100)
    reward_cost: int = Field(gt=0, strict=True)
    status: Literal["fulfilled", "unfulfilled", "canceled"]


class Confirmation(TwitchIdentity):
    code: str = Field(min_length=10, max_length=10, pattern=r"^[a-fA-F0-9]{10}$")


def resolve_user(database: Session, identity: TwitchIdentity) -> User:
    if identity.broadcaster_login != settings.twitch_broadcaster_login.lower():
        raise HTTPException(403, "Wrong Twitch channel")
    user = database.scalar(select(User).where(User.twitch_id == identity.user_id))
    if user is None:
        try:
            with database.begin_nested():
                user = User(twitch_id=identity.user_id, username=identity.username,
                            display_name=identity.display_name or identity.username, credits=0)
                database.add(user)
                database.flush()
        except IntegrityError:
            user = database.scalar(select(User).where(User.twitch_id == identity.user_id))
            if user is None:
                raise HTTPException(409, "Benutzername ist bereits einer anderen Twitch-ID zugeordnet") from None
    lock_wallet(database, user)
    if user.username != identity.username:
        other = database.scalar(select(User).where(User.username == identity.username, User.id != user.id))
        if other:
            raise HTTPException(409, "Benutzername ist bereits einer anderen Twitch-ID zugeordnet")
        user.username = identity.username
    user.display_name = identity.display_name or identity.username
    database.flush()
    return user


def registration_link(database: Session, user: User) -> dict:
    frontend = settings.frontend_url.split("#")[0]
    if user.password_hash:
        return {"registered": True, "username": user.username, "login_url": frontend + "#/", "registration_url": None}
    # Public address only. Password activation requires a separate browser challenge.
    return {"registered": False, "username": user.username,
            "registration_url": frontend + "#/register/" + quote(user.username, safe="")}


@router.get("/status")
def status() -> dict:
    return {"status": "ok", "channel": settings.twitch_broadcaster_login, "reward_configured": bool(settings.twitch_reward_id),
            "reward_cost": settings.twitch_reward_cost, "reward_points": settings.twitch_reward_diamonds}


@router.post("/register")
def register_command(payload: TwitchIdentity, database: Database) -> dict:
    user = resolve_user(database, payload)
    response = registration_link(database, user)
    database.commit()
    return response


@router.post("/confirm")
def confirm_registration(payload: Confirmation, database: Database) -> dict:
    if payload.broadcaster_login != settings.twitch_broadcaster_login.lower():
        raise HTTPException(403, "Wrong Twitch channel")
    throttle(database, [(f"confirm-user:{payload.user_id}", 15)])
    challenge = database.scalar(select(RegistrationChallenge).where(RegistrationChallenge.code_hash == token_hash(payload.code.upper())))
    if challenge is None or challenge.expires_at <= datetime.utcnow():
        raise HTTPException(400, "Code ist ungültig oder abgelaufen. Bitte im eigenen Browser neu beginnen.")
    user = database.get(User, challenge.user_id)
    if user is None or user.twitch_id != payload.user_id or challenge.username != payload.username:
        raise HTTPException(403, "Code gehört zu einem anderen Twitch-Konto.")
    challenge_token, user_id = challenge.token_hash, user.id
    lock_wallet(database, user)
    database.expire_all()
    challenge = database.get(RegistrationChallenge, challenge_token)
    user = database.get(User, user_id)
    if (challenge is None or challenge.expires_at <= datetime.utcnow()
            or not user.is_active or user.password_hash is not None or user.username != challenge.username):
        raise HTTPException(400, "Diese Registrierung ist nicht mehr gültig. Bitte anmelden oder neu beginnen.")
    challenge.approved = True
    # Only the browser explicitly confirmed by this Twitch account may finish signup.
    database.execute(delete(RegistrationChallenge).where(RegistrationChallenge.user_id == user.id,
                                                        RegistrationChallenge.token_hash != challenge.token_hash))
    database.commit()
    return {"confirmed": True, "username": user.username}


@router.post("/redemptions")
def reward_redemption(payload: Redemption, database: Database) -> dict:
    if payload.broadcaster_login != settings.twitch_broadcaster_login.lower():
        raise HTTPException(403, "Wrong Twitch channel")
    if not settings.twitch_reward_id:
        raise HTTPException(503, "Reward-ID ist noch nicht eingerichtet")
    if payload.reward_id != settings.twitch_reward_id or payload.reward_cost != settings.twitch_reward_cost:
        raise HTTPException(403, "Wrong reward or channel-point cost")
    user = resolve_user(database, payload)
    existing = database.get(TwitchRedemption, payload.redemption_id)
    credited = False
    if existing and existing.user_id != user.id:
        raise HTTPException(409, "Einlösung gehört zu einem anderen Konto")
    if existing is None:
        # The initial redemption already spent the viewer's channel points.
        # Keep canceled IDs with amount 0 so a delayed initial event cannot credit them.
        amount = 0 if payload.status == "canceled" else settings.twitch_reward_diamonds
        database.add(TwitchRedemption(redemption_id=payload.redemption_id, user_id=user.id,
                                     reward_id=payload.reward_id, diamonds=amount))
        if amount:
            book_diamonds(database, user, amount, "twitch_redemption", "twitch:" + payload.redemption_id)
            credited = True
    receipt_amount = existing.diamonds if existing else amount
    response = {"credited": credited, "duplicate": existing is not None, "diamonds": user.credits,
                "status": payload.status, "registration_url": None,
                "fulfill_required": payload.status == "unfulfilled" and receipt_amount > 0,
                "canceled_after_credit": payload.status == "canceled" and receipt_amount > 0}
    if payload.status != "canceled" and existing is None:
        response.update(registration_link(database, user))
    database.commit()
    return response
