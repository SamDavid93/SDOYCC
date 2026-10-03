import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import create_session, token_hash
from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.core.rate_limit import throttle
from app.db.models import AuthSession, RegistrationChallenge, User
from app.db.session import get_db
from app.modules.economy import lock_wallet

router = APIRouter(prefix="/api/auth")
Database = Annotated[Session, Depends(get_db)]


@router.get("/config")
def auth_config() -> dict:
    return {"auth_mode": "password", "registration_mode": "chat_confirmation", "demo_enabled": settings.demo_enabled,
            "streamerbot_enabled": len(settings.streamerbot_api_key) >= 32,
            "channel": settings.twitch_broadcaster_login, "reward_cost": settings.twitch_reward_cost,
            "reward_points": settings.twitch_reward_diamonds, "currency": "Tradingpoints"}


class RegistrationName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=25, pattern=r"^[A-Za-z0-9_]+$")


class InviteIdentity(RegistrationName):
    token: str = Field(min_length=40, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class Register(InviteIdentity):
    password: str = Field(min_length=12, max_length=128)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def invite_user(database: Session, payload: InviteIdentity, require_approved: bool = True) -> tuple[RegistrationChallenge, User]:
    invite = database.get(RegistrationChallenge, token_hash(payload.token))
    if invite is None or invite.expires_at <= datetime.utcnow() or invite.username != payload.username.lower():
        raise HTTPException(400, "Registrierung ist ungültig oder abgelaufen. Bitte einen neuen Bestätigungscode anfordern.")
    user = database.get(User, invite.user_id)
    if user is None or not user.is_active or user.password_hash is not None or user.username != invite.username:
        raise HTTPException(400, "Diese Registrierung ist nicht mehr gültig. Bitte anmelden oder neu beginnen.")
    if require_approved and not invite.approved:
        raise HTTPException(403, "Bitte zuerst den angezeigten !confirm-Befehl mit deinem Twitch-Konto im Chat senden.")
    return invite, user


@router.post("/register/start")
def start_registration(payload: RegistrationName, database: Database, request: Request) -> dict:
    throttle(database, [(f"register-start:{request.client.host if request.client else 'unknown'}", 20)])
    user = database.scalar(select(User).where(User.username == payload.username.lower()))
    if user is None or not user.is_active or not user.twitch_id:
        raise HTTPException(400, "Bitte zuerst !register im Twitch-Chat eingeben und den Link aus dem Chat öffnen.")
    if user.password_hash is not None:
        raise HTTPException(409, "Dein Konto ist bereits registriert. Bitte mit deinem Passwort anmelden.")
    database.execute(delete(RegistrationChallenge).where(RegistrationChallenge.expires_at <= datetime.utcnow()))
    token, code = secrets.token_urlsafe(32), secrets.token_hex(5).upper()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.registration_minutes)
    database.add(RegistrationChallenge(token_hash=token_hash(token), code_hash=token_hash(code),
                                      user_id=user.id, username=user.username, expires_at=expires_at))
    database.commit()
    # The browser secret never appears in the public link or the chat command.
    return {"token": token, "code": code, "username": user.username, "channel": settings.twitch_broadcaster_login,
            "expires_at": expires_at.isoformat() + "Z", "expires_in_minutes": settings.registration_minutes}


@router.post("/register/inspect")
def inspect_invite(payload: InviteIdentity, database: Database, request: Request) -> dict:
    throttle(database, [(f"inspect-token:{token_hash(payload.token)}", 120),
                        (f"inspect-ip:{request.client.host if request.client else 'unknown'}", 600)])
    invite, user = invite_user(database, payload, require_approved=False)
    return {"username": user.username, "display_name": user.display_name, "confirmed": invite.approved}


@router.post("/register")
def register(payload: Register, database: Database, request: Request) -> dict:
    throttle(database, [(f"register:{request.client.host if request.client else 'unknown'}", 15)])
    _, user = invite_user(database, payload)
    # Hash before locking the wallet so other users can keep purchasing on SQLite.
    password_hash = hash_password(payload.password)
    lock_wallet(database, user)
    # Reload after locking: another request may already have consumed/rotated this invitation.
    database.expire_all()
    invite, user = invite_user(database, payload)
    user.password_hash = password_hash
    database.execute(delete(RegistrationChallenge).where(RegistrationChallenge.user_id == user.id))
    token = create_session(database, user)
    database.commit()
    return {"token": token, "username": user.username}


@router.post("/login")
def login(payload: Login, database: Database, request: Request) -> dict:
    username = payload.username.strip().lower()
    throttle(database, [(f"login-user:{username}", 10), (f"login-ip:{request.client.host if request.client else 'unknown'}", 40)])
    user = database.scalar(select(User).where(User.username == username))
    valid = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        raise HTTPException(401, "Benutzername oder Passwort ist falsch")
    checked_hash = user.password_hash
    lock_wallet(database, user)
    if user.password_hash != checked_hash:
        raise HTTPException(401, "Die Anmeldung wurde zwischenzeitlich zurückgesetzt. Bitte erneut beginnen.")
    database.execute(delete(AuthSession).where(AuthSession.expires_at < datetime.utcnow()))
    token = create_session(database, user)
    database.commit()
    return {"token": token, "username": user.username}


@router.post("/logout")
def logout(database: Database, authorization: Annotated[str | None, Header()] = None) -> Response:
    if authorization and authorization.startswith("Bearer "):
        database.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(authorization[7:])))
        database.commit()
    return Response(status_code=204)
