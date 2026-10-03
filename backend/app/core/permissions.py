"""Server-side permissions; demo sessions never grant administrative access."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.models import User
from app.db.session import get_db

ADMIN_READ_ROLES = frozenset({"support_admin", "admin", "super_admin"})


def admin_reader(database: Annotated[Session, Depends(get_db)],
                 authorization: Annotated[str | None, Header()] = None) -> User:
    user = get_current_user(authorization, database)
    if authorization == "Bearer demo-token" or user.role not in ADMIN_READ_ROLES:
        raise HTTPException(403, "Für diesen Bereich fehlen dir die Verwaltungsrechte.")
    return user
