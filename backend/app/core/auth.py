import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuthSession, User


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(database: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    database.add(AuthSession(token_hash=token_hash(token), user_id=user.id,
                             expires_at=datetime.utcnow() + timedelta(hours=settings.session_hours)))
    return token


def get_current_user(authorization: str | None, database: Session) -> User:
    user = None
    if authorization == "Bearer demo-token" and settings.demo_enabled:
        user = database.scalar(select(User).where(User.username == "jaden-demo"))
    elif authorization and authorization.startswith("Bearer "):
        session = database.get(AuthSession, token_hash(authorization[7:]), populate_existing=True)
        if session and session.expires_at > datetime.utcnow():
            user = database.get(User, session.user_id)
            if user is not None:
                user._authenticated_session = session.token_hash
    if user is None or not user.is_active:
        raise HTTPException(401, "Bitte mit Benutzername und Passwort anmelden")
    return user


def recheck_session(database: Session, user: User) -> None:
    """Called after the account write lock: a reset may have revoked a waiting request."""
    key = getattr(user, "_authenticated_session", None)
    if key:
        session = database.get(AuthSession, key, populate_existing=True)
        if session is None or session.expires_at <= datetime.utcnow():
            raise HTTPException(401, "Die Sitzung wurde beendet. Bitte erneut anmelden.")
