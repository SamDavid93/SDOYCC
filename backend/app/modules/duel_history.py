"""Account-private terminal receipts and thirty-day own-view playback."""
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api import current_user
from app.db.models import DuelWorkerParticipant, DuelWorkerReplay, DuelWorkerRun, DuelMatchProgress
from app.modules.decks import Database
from app.modules.duel_worker_state import public_receipt

router = APIRouter(prefix='/api/duel-zone/history', tags=['Private duel history'])


@router.get('')
def history(db: Database, user=Depends(current_user), page: int = Query(1, ge=1)):
    query = select(DuelWorkerRun, DuelWorkerParticipant).join(DuelWorkerParticipant,
        DuelWorkerParticipant.run_id == DuelWorkerRun.id).where(DuelWorkerParticipant.user_id == user.id,
        DuelWorkerRun.state.in_(('finished', 'aborted')))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(DuelWorkerRun.ended_at.desc(), DuelWorkerRun.id).offset((page-1)*20).limit(20)).all()
    replay_ids = set(db.scalars(select(DuelWorkerReplay.run_id).where(
        DuelWorkerReplay.run_id.in_([row.id for row, _ in rows]), DuelWorkerReplay.expires_at > datetime.utcnow())))
    matches = {row.run_id: json.loads(row.progress_json) for row in db.scalars(select(DuelMatchProgress).where(
        DuelMatchProgress.run_id.in_([run.id for run, _ in rows])))}
    return {'total': total, 'page': page, 'items': [{**public_receipt(row), 'seat': participant.seat,
        'match': {key: matches[row.id][key] for key in ('score', 'game', 'results')} if row.id in matches else None,
        'replay_available': row.id in replay_ids} for row, participant in rows]}


@router.get('/{run_id}/replay')
def replay(run_id: str, db: Database, user=Depends(current_user)):
    participant = db.get(DuelWorkerParticipant, (run_id, user.id))
    run = db.get(DuelWorkerRun, run_id) if participant else None
    if not run or run.state not in ('finished', 'aborted'): raise HTTPException(404, 'Abgeschlossenes eigenes Duell nicht gefunden.')
    row = db.get(DuelWorkerReplay, run_id)
    if not row or row.expires_at <= datetime.utcnow(): raise HTTPException(404, 'Dieser Spielverlauf ist nicht mehr verfügbar.')
    data = json.loads(row.views_json)
    return {**public_receipt(run), 'seat': participant.seat, 'format': 'sdoycc-own-view-v1',
        'frames': data[str(participant.seat)], 'truncated': data['truncated'],
        'expires_at': row.expires_at.isoformat() + 'Z'}
