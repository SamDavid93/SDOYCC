import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update, literal

from app.api import current_user
from app.db.models import Grant, Notification, HubNotice
from app.modules.admin import Database, Page, PageSize, paged
from app.modules.economy import lock_wallet

router = APIRouter(prefix="/api/notifications")


@router.get("")
def notifications(database: Database, user=Depends(current_user), page: Page = 1, page_size: PageSize = 10):
    rows = select(Notification.id.label("id"), Notification.created_at.label("time")).where(Notification.user_id == user.id).union_all(
        select(-HubNotice.id, HubNotice.created_at).where(HubNotice.user_id == user.id)).subquery()
    ids = database.scalars(select(rows.c.id).order_by(rows.c.time.desc(), rows.c.id).offset((page-1)*page_size).limit(page_size))
    items = []
    for nid in ids:
        if nid < 0:
            row = database.get(HubNotice, -nid)
            items.append({"id": nid, "read": row.read_at is not None, "grant_id": None, "title": row.title, "reason": row.message,
                "link": row.link, "created_at": row.created_at.isoformat()+"Z", "items": []})
        else:
            row = database.get(Notification, nid); grant = database.get(Grant, row.grant_id)
            items.append({"id": nid, "read": row.read_at is not None, "grant_id": grant.id, "reason": grant.reason,
                "created_at": row.created_at.isoformat()+"Z", "items": json.loads(grant.result_json)["items"]})
    unread = sum(database.scalar(select(func.count(model.id)).where(model.user_id == user.id, model.read_at.is_(None))) for model in [Notification, HubNotice])
    return {"items": items, "total": database.scalar(select(func.count()).select_from(rows)), "page": page, "page_size": page_size, "unread": unread}



@router.post("/{notification_id}/read")
def read(notification_id: int, database: Database, user=Depends(current_user)):
    lock_wallet(database, user)
    model = HubNotice if notification_id < 0 else Notification
    result = database.execute(update(model).where(model.id == abs(notification_id), model.user_id == user.id).values(
        read_at=func.coalesce(model.read_at, datetime.utcnow())))
    if result.rowcount != 1:
        raise HTTPException(404, "Mitteilung nicht gefunden.")
    database.commit()
    return {"read": True}
