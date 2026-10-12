"""Global admission limits; mutations serialize with the workflow DB mutex."""
from fastapi import HTTPException
from sqlalchemy import func, select
from datetime import datetime
from app.core.config import settings
from app.db.models import DuelRuntimePolicy, DuelWorkerRun, DuelRestriction


def restricted(db, user_id, now=None):
    row = db.get(DuelRestriction, user_id, populate_existing=True)
    return bool(row and row.until > (now or datetime.utcnow()))


def require_player(db, user_id):
    if restricted(db, user_id): raise HTTPException(403, 'Für dieses Konto besteht eine befristete Duellsperre. Andere Hub-Funktionen bleiben verfügbar.')


def status(db):
    policy = db.get(DuelRuntimePolicy, 1)
    active = db.scalar(select(func.count(DuelWorkerRun.id)).where(DuelWorkerRun.state.in_(('starting', 'running'))))
    return {'accepting_new': policy.accepting_new if policy else True,
        'version': policy.version if policy else 1,
        'active_matches': active, 'max_active_matches': settings.duel_max_active_matches,
        'available_slots': max(0, settings.duel_max_active_matches - active)}


def require_slot(db):
    policy = status(db)
    if not policy['accepting_new']:
        raise HTTPException(503, 'Duellbetrieb in Wartung. Laufende Matches können zu Ende gespielt werden.')
    if not policy['available_slots']:
        raise HTTPException(429, 'Alle Duellplätze sind belegt. Versuche es nach Abschluss eines Matches erneut.',
            headers={'Retry-After': '30'})
