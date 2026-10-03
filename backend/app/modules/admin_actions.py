"""Audited account actions. No game assets are deleted or overwritten."""
import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, aliased

from app.core.auth import get_current_user
from app.core.passwords import verify_password
from app.core.permissions import admin_reader
from app.core.rate_limit import throttle
from app.db.models import AdminAuditEvent, AdminMutationLock, AuthSession, RegistrationChallenge, RegistrationInvite, User
from app.db.session import get_db
from app.modules.admin import paged, Page, PageSize
from app.modules.economy import finish, replay

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_reader)])
Database = Annotated[Session, Depends(get_db)]
Action = Literal["reset_login", "revoke_sessions", "block", "unblock", "change_role"]
Role = Literal["user", "support_admin", "admin", "super_admin"]


class AccountAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Action
    reason: str = Field(min_length=5, max_length=500)
    confirmation: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)
    role: Role | None = None

    @field_validator("reason", "confirmation", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


def state(database: Session, user: User) -> dict:
    return {"role": user.role, "is_active": user.is_active, "registered": bool(user.password_hash),
            "active_sessions": database.scalar(select(func.count(AuthSession.token_hash)).where(
                AuthSession.user_id == user.id, AuthSession.expires_at > datetime.utcnow()))}


@router.post("/users/{user_id}/actions")
def account_action(user_id: int, payload: AccountAction, database: Database,
                   actor: User = Depends(admin_reader),
                   authorization: Annotated[str | None, Header()] = None,
                   idempotency_key: Annotated[str | None, Header()] = None) -> dict:
    if actor.role not in {"admin", "super_admin"}:
        raise HTTPException(403, "Der Support-Zugang erlaubt ausschließlich lesenden Zugriff.")
    if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
        raise HTTPException(400, "Eine gültige Aktionskennung ist erforderlich.")
    if (payload.action == "change_role") != (payload.role is not None):
        raise HTTPException(400, "Eine Zielrolle ist ausschließlich bei einer Rollenänderung erforderlich.")
    throttle(database, [(f"admin-password:{actor.id}", 15)])
    database.refresh(actor)
    checked_hash = actor.password_hash
    if not verify_password(payload.password.get_secret_value(), checked_hash):
        # 403 keeps the authenticated session, but declines this fresh confirmation.
        raise HTTPException(403, "Dein Administrator-Passwort ist nicht korrekt.")
    identity = {"user_id": user_id, **payload.model_dump(exclude={"password"})}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    action_key = "admin:" + digest
    # Global admin lock serializes role/last-owner checks across different target accounts.
    insert = sqlite_insert if database.get_bind().dialect.name == "sqlite" else pg_insert
    database.execute(insert(AdminMutationLock).values(id=1, revision=0).on_conflict_do_nothing(index_elements=["id"]))
    database.execute(update(AdminMutationLock).where(AdminMutationLock.id == 1).values(revision=AdminMutationLock.revision + 1))
    # Lock account rows in a stable order, including inactive targets (unblock).
    for account_id in sorted({actor.id, user_id}):
        database.execute(update(User).where(User.id == account_id).values(credits=User.credits).execution_options(synchronize_session=False))
    database.expire_all()
    actor = get_current_user(authorization, database)
    if actor.role not in {"admin", "super_admin"} or actor.password_hash != checked_hash:
        raise HTTPException(403, "Deine Berechtigung oder Anmeldung wurde geändert. Bitte neu beginnen.")
    previous = replay(database, actor, idempotency_key, action_key)
    if previous is not None:
        return previous
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Konto nicht gefunden.")
    if payload.confirmation != user.username:
        raise HTTPException(400, "Bitte den Benutzernamen des Zielkontos exakt bestätigen.")
    if actor.role != "super_admin" and (user.role != "user" or payload.action == "change_role"):
        raise HTTPException(403, "Nur Hauptadministratoren dürfen Verwaltungsrollen bearbeiten.")
    if user.username == "jaden-demo" or not user.twitch_id:
        raise HTTPException(400, "Diese Aktionen sind ausschließlich für Twitch-Konten verfügbar.")
    if user.id == actor.id and payload.action != "revoke_sessions":
        raise HTTPException(403, "Das eigene Verwaltungskonto darf hier nur abgemeldet werden.")
    removes_owner = payload.action in {"block", "reset_login"} or (payload.action == "change_role" and payload.role != "super_admin")
    if user.role == "super_admin" and user.is_active and user.password_hash and removes_owner:
        owners = database.scalar(select(func.count(User.id)).where(User.role == "super_admin", User.is_active.is_(True), User.password_hash.is_not(None)))
        if owners <= 1:
            raise HTTPException(409, "Der letzte angemeldete Hauptadministrator muss erhalten bleiben.")
    if payload.action == "change_role" and payload.role != "user" and (not user.is_active or not user.password_hash):
        raise HTTPException(400, "Verwaltungsrechte erfordern ein aktives, registriertes Konto.")
    before = state(database, user)
    if payload.action == "reset_login":
        user.password_hash = None
    elif payload.action == "block":
        user.is_active = False
    elif payload.action == "unblock":
        user.is_active = True
    elif payload.action == "change_role":
        user.role = payload.role
    if payload.action != "unblock":
        database.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    if payload.action in {"reset_login", "block", "change_role"}:
        database.execute(delete(RegistrationChallenge).where(RegistrationChallenge.user_id == user.id))
        database.execute(delete(RegistrationInvite).where(RegistrationInvite.user_id == user.id))
    database.flush()
    if payload.action == "block":
        from app.modules.trading import cleanup
        cleanup(database)
    event = AdminAuditEvent(action=payload.action, actor_id=actor.id, target_id=user.id, source="admin_panel",
        details_json=json.dumps({"reason": payload.reason, "before": before, "after": state(database, user)}, ensure_ascii=False))
    database.add(event)
    database.flush()
    response = {"audit_id": event.id, "action": payload.action, "user_id": user.id, "username": user.username,
                "state": state(database, user), "sessions_revoked": before["active_sessions"] if payload.action != "unblock" else 0}
    return finish(database, actor, idempotency_key, action_key, response)


@router.get("/audit")
def audit(database: Database, actor: User = Depends(admin_reader), user_id: int | None = Query(None, ge=1),
          action: str = Query("", max_length=80), page: Page = 1, page_size: PageSize = 25) -> dict:
    if actor.role not in {"admin", "super_admin"}:
        raise HTTPException(403, "Das Änderungsprotokoll ist Administratoren vorbehalten.")
    acting, affected = aliased(User), aliased(User)
    statement = select(AdminAuditEvent, acting.username, affected.username).outerjoin(
        acting, acting.id == AdminAuditEvent.actor_id).join(affected, affected.id == AdminAuditEvent.target_id)
    if user_id is not None:
        statement = statement.where(AdminAuditEvent.target_id == user_id)
    if action:
        statement = statement.where(AdminAuditEvent.action == action)
    return paged(database, statement.order_by(AdminAuditEvent.id.desc()), page, page_size, lambda row: {
        "id": row[0].id, "action": row[0].action, "actor": row[1], "target": row[2], "target_id": row[0].target_id,
        "source": row[0].source, "created_at": row[0].created_at.isoformat() + "Z", "details": json.loads(row[0].details_json)})
