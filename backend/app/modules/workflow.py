"""Shared transaction boundary for multi-account workflows; no commits in helpers."""
import json
from typing import Annotated
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.auth import get_current_user
from app.core.passwords import verify_password
from app.core.rate_limit import throttle
from app.db.models import AdminMutationLock, AdminAuditEvent, User, HubNotice
from app.modules.grants import digest

Auth = Annotated[str | None, Header()]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]

class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class AdminCommand(Command):
    password: SecretStr = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=5, max_length=500)

def key_required(key):
    if not key or not 8 <= len(key) <= 100:
        raise HTTPException(400, "Eine gültige Aktionskennung ist erforderlich.")

def mutex(db):
    insert = sqlite_insert if db.get_bind().dialect.name == "sqlite" else pg_insert
    db.execute(insert(AdminMutationLock).values(id=1, revision=0).on_conflict_do_nothing(index_elements=["id"]))
    db.execute(update(AdminMutationLock).where(AdminMutationLock.id == 1).values(revision=AdminMutationLock.revision + 1))
    db.expire_all()

def lock_users(db, ids):
    for account_id in sorted(set(ids)):
        db.execute(update(User).where(User.id == account_id).values(credits=User.credits).execution_options(synchronize_session=False))
    db.expire_all()

def writer(db, authorization, key, ids=()):
    key_required(key)
    mutex(db)
    user = get_current_user(authorization, db)
    if not user.twitch_id or not user.password_hash:
        raise HTTPException(403, "Ein registriertes Twitch-Konto ist erforderlich.")
    lock_users(db, [user.id, *ids])
    return get_current_user(authorization, db)

def administrator(db, authorization, key, payload, ids=(), super_only=True):
    actor = get_current_user(authorization, db)
    if actor.role not in ({"super_admin"} if super_only else {"super_admin", "admin"}):
        raise HTTPException(403, "Für diese Aktion fehlen dir Verwaltungsrechte.")
    throttle(db, [(f"admin-password:{actor.id}", 15)])
    db.refresh(actor)
    checked_hash = actor.password_hash
    if not verify_password(payload.password.get_secret_value(), checked_hash):
        raise HTTPException(403, "Dein Administrator-Passwort ist nicht korrekt.")
    actor = writer(db, authorization, key, ids)
    if actor.password_hash != checked_hash or actor.role not in ({"super_admin"} if super_only else {"super_admin", "admin"}):
        raise HTTPException(403, "Deine Anmeldung oder Berechtigung wurde geändert.")
    return actor

def action(name, payload):
    return name + ":" + digest(payload.model_dump(mode="json", exclude={"password"}))

def audit(db, actor, target_id, name, data):
    row = AdminAuditEvent(actor_id=actor.id if actor else None, target_id=target_id,
        action=name, source="workflow", details_json=json.dumps(data, ensure_ascii=False))
    db.add(row); db.flush()
    return row.id

def notice(db, user_id, title, message, link):
    db.add(HubNotice(user_id=user_id, title=title, message=message, link=link))

def entity_page(db, statement, page, page_size, serialize):
    from app.modules.admin import paged
    return paged(db, statement, page, page_size, lambda row: serialize(row[0] if len(row) == 1 else row))
