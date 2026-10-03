"""Local first-owner provisioning; the caller controls commit/rollback."""
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import AdminAuditEvent, User


def bootstrap_owner(database: Session, twitch_id: str) -> User:
    if database.get_bind().dialect.name != "sqlite":
        raise ValueError("Die lokale Ersteinrichtung unterstützt ausschließlich SQLite.")
    if not twitch_id.isascii() or not twitch_id.isdigit():
        raise ValueError("Eine numerische Twitch-ID ist erforderlich, kein Benutzername.")
    # Serialize competing setup commands before inspecting roles and the one-time receipt.
    database.execute(text("BEGIN IMMEDIATE"))
    if database.scalar(select(AdminAuditEvent.id).where(AdminAuditEvent.event_key == "first-owner")) or database.scalar(
            select(User.id).where(User.role == "super_admin")):
        raise ValueError("Ein Hauptadministrator wurde bereits eingerichtet. Keine Änderung vorgenommen.")
    user = database.scalar(select(User).where(User.twitch_id == twitch_id))
    if not user or not user.is_active or not user.password_hash or user.username == "jaden-demo":
        raise ValueError("Die Twitch-ID muss zu einem aktiven, fertig registrierten Konto gehören.")
    previous = user.role
    user.role = "super_admin"
    database.add(AdminAuditEvent(event_key="first-owner", action="owner_bootstrap", target_id=user.id,
        actor_id=None, source="local_cli", details_json=json.dumps({"previous_role": previous, "role": user.role})))
    database.flush()
    return user
