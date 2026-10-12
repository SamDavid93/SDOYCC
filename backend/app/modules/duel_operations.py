"""Audited operator controls; never release inventory without a process proof."""
from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from pydantic import Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.permissions import admin_reader
from app.db.models import DuelWorkerRun, DuelWorkerLease, DuelRuntimePolicy
from app.modules.admin import Database
from app.modules.duel_worker import service
from app.modules.workflow import AdminCommand, Auth, Key, administrator, audit, action
from app.modules.economy import replay, finish
from app.modules.duel_admission import status

router = APIRouter(prefix='/api/admin/duels', dependencies=[Depends(admin_reader)])


class PolicyCommand(AdminCommand):
    accepting_new: bool = Field(strict=True)
    version: int = Field(ge=1, strict=True)


@router.post('/policy')
def policy(body: PolicyCommand, database: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = administrator(database, authorization, idempotency_key, body)
    operation = action('duel_admission_policy', body)
    previous = replay(database, actor, idempotency_key, operation)
    if previous is not None: return previous
    current = status(database)
    if body.version != current['version']: raise HTTPException(409, 'Duellbetriebsstand ist veraltet. Bitte aktualisieren.')
    row = database.get(DuelRuntimePolicy, 1)
    if row is None:
        row = DuelRuntimePolicy(id=1, accepting_new=True, version=1); database.add(row)
    row.accepting_new = body.accepting_new; row.version += 1
    audit(database, actor, actor.id, 'duel_admission_policy',
        {'accepting_new': row.accepting_new, 'version': row.version, 'reason': body.reason})
    database.flush()
    return finish(database, actor, idempotency_key, operation, status(database))


@router.get('/operations')
def operations(request: Request, database: Database):
    runtime = getattr(request.app.state, 'duel_worker', None)
    runs = database.execute(select(DuelWorkerRun, DuelWorkerLease).outerjoin(
        DuelWorkerLease, DuelWorkerLease.run_id == DuelWorkerRun.id).where(
            DuelWorkerRun.state.in_(('starting', 'running'))).order_by(DuelWorkerRun.created_at)).all()
    return {'enabled': settings.duel_worker_enabled and runtime is not None,
        'admission': status(database),
        'runs': [{'id': run.id, 'state': run.state,
            'age_seconds': max(0, int((datetime.utcnow() - run.created_at).total_seconds())),
            'local': bool(runtime and run.owner_instance == runtime.instance and run.id in runtime.runs),
            'process_evidence': lease is not None} for run, lease in runs]}


def approve(db, authorization, key, body, run_id, name):
    actor = administrator(db, authorization, key, body)
    run = db.get(DuelWorkerRun, run_id)
    if not run: raise HTTPException(404, 'Duell nicht gefunden.')
    audit(db, actor, json.loads(run.participants_json)[0]['user_id'], name, {'run_id': run_id, 'reason': body.reason})
    proof = (actor.id, actor.password_hash)
    db.commit()
    return proof


def recheck(db, authorization, proof):
    actor = get_current_user(authorization, db)
    if (actor.id, actor.password_hash) != proof or actor.role != 'super_admin':
        raise HTTPException(403, 'Verwaltungsberechtigung wurde geändert.')


@router.post('/runs/{run_id}/abort')
async def abort(run_id: str, body: AdminCommand, request: Request, authorization: Auth = None, idempotency_key: Key = None):
    runtime = service(request)
    proof = await runtime.database(approve, authorization, idempotency_key, body, run_id, 'duel_abort_requested')
    live = runtime.runs.get(run_id)
    if live is None: raise HTTPException(409, 'Fremder oder verwaister Worker benötigt die Wiederanlaufprüfung.')
    async with live.lock:
        await runtime.database(recheck, authorization, proof)
        if not live.terminal: await runtime.stop(run_id, live, 'admin_abort')
    return {'id': run_id, 'stopped': True}


@router.post('/runs/{run_id}/recover')
async def recover(run_id: str, body: AdminCommand, request: Request, authorization: Auth = None, idempotency_key: Key = None):
    runtime = service(request)
    proof = await runtime.database(approve, authorization, idempotency_key, body, run_id, 'duel_recovery_requested')
    await runtime.database(recheck, authorization, proof)
    results = await runtime.recover_orphans(only=run_id)
    if not any(result['id'] == run_id and result['recovered'] for result in results):
        # Repeated successful requests are harmless; no manual override exists.
        def ended(db): return db.get(DuelWorkerRun, run_id).state not in ('starting', 'running')
        if not await runtime.database(ended):
            raise HTTPException(409, 'Prozessstopp nicht nachweisbar. Reservierungen bleiben bestehen.')
    return {'id': run_id, 'stopped': True}
