"""Restart-safe expiry cleanup and catch-up of committed opening events."""
import asyncio
import logging
from sqlalchemy import select, exists, literal, cast, String
from app.db.session import SessionLocal
from app.db.models import User, Season, SeasonXpEvent, BoosterOpening
from app.modules.workflow import mutex, lock_users
from app.modules.trading import cleanup
from app.modules.seasons import sync

def maintain():
    with SessionLocal() as db:
        mutex(db)
        cleanup(db)
        # Events normally book synchronously. Replay only missing committed openings after downtime.
        seasons = db.scalars(select(Season).where(Season.state == "published")).all()
        for season in seasons:
            processed = exists(select(SeasonXpEvent.id).where(SeasonXpEvent.user_id == BoosterOpening.user_id,
                SeasonXpEvent.season_id == season.id, SeasonXpEvent.reference == literal("opening:") + cast(BoosterOpening.id, String)))
            pending_users = select(BoosterOpening.user_id).where(BoosterOpening.created_at >= season.starts_at,
                BoosterOpening.created_at < season.ends_at, ~processed)
            for uid in db.scalars(select(User.id).where(User.twitch_id.is_not(None), User.id.in_(pending_users)).order_by(User.id)):
                lock_users(db, [uid])
                sync(db, uid, season)
        db.commit()

async def maintenance_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(maintain)
        except Exception:
            logging.getLogger(__name__).error("Bestandsbereinigung fehlgeschlagen; erneuter Versuch in einer Minute.")
