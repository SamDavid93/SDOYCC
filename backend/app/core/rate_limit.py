from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.auth import token_hash
from app.db.models import AuthRateLimit


def throttle(database: Session, keys: list[tuple[str, int]], seconds: int = 300) -> None:
    """Shared across workers; failed authentication must not roll back counters."""
    now = datetime.utcnow()
    database.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at < now))
    insert = sqlite_insert if database.get_bind().dialect.name == "sqlite" else pg_insert
    limited = False
    for key, limit in keys:
        statement = insert(AuthRateLimit).values(key=token_hash(key), attempts=1, expires_at=now + timedelta(seconds=seconds))
        statement = statement.on_conflict_do_update(index_elements=[AuthRateLimit.key], set_={
            "attempts": case((AuthRateLimit.expires_at <= now, 1), else_=AuthRateLimit.attempts + 1),
            "expires_at": case((AuthRateLimit.expires_at <= now, now + timedelta(seconds=seconds)), else_=AuthRateLimit.expires_at),
        }).returning(AuthRateLimit.attempts)
        limited = database.execute(statement).scalar_one() > limit or limited
    database.commit()
    if limited:
        raise HTTPException(429, "Zu viele Versuche. Bitte in fünf Minuten erneut versuchen.", headers={"Retry-After": str(seconds)})
