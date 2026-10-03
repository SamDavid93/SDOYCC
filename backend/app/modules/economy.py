"""All wallet and inventory mutations serialize on the owner's database row."""
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import ActionReceipt, DiamondTransaction, User
from app.core.auth import recheck_session


def lock_wallet(database: Session, user: User) -> None:
    # UPDATE also acquires a write lock on SQLite, where FOR UPDATE has no effect.
    database.execute(update(User).where(User.id == user.id).values(credits=User.credits).execution_options(synchronize_session=False))
    database.refresh(user)
    recheck_session(database, user)
    if not user.is_active:
        raise HTTPException(403, "Dieses Konto ist gesperrt")


def book_diamonds(database: Session, user: User, amount: int, reason: str, reference: str | None = None) -> None:
    if user.credits + amount < 0:
        raise HTTPException(400, "Nicht genug Sammelpunkte")
    user.credits += amount
    database.add(DiamondTransaction(user_id=user.id, amount=amount, balance_after=user.credits,
                                    reason=reason, reference=reference or str(uuid4())))
    database.flush()


def replay(database: Session, user: User, key: str | None, action: str) -> dict | None:
    if key is None:
        return None
    if not 8 <= len(key) <= 100:
        raise HTTPException(400, "Ungültige Aktionskennung")
    receipt = database.scalar(select(ActionReceipt).where(ActionReceipt.user_id == user.id, ActionReceipt.request_key == key))
    if receipt:
        if receipt.action != action:
            raise HTTPException(409, "Diese Aktionskennung wurde bereits für eine andere Aktion verwendet")
        return json.loads(receipt.response_json)
    return None


def finish(database: Session, user: User, key: str | None, action: str, response: dict) -> dict:
    if key:
        database.add(ActionReceipt(user_id=user.id, request_key=key, action=action, response_json=json.dumps(response)))
    database.commit()
    return response
