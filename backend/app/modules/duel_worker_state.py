"""Database boundaries for the opt-in local worker. No subprocess I/O under locks."""
from datetime import datetime, timedelta
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.auth import get_current_user
from app.db.models import AuthSession, DuelLobby, DuelLobbySeat, DuelPreparation, DuelRuleProfile, DuelWorkerRun, DuelWorkerLease, DuelWorkerParticipant, DuelWorkerReplay, DuelWorkerConsent, User, PlayerDeck
from app.modules.duel_lobbies import close_lobby
from app.modules.duel_preparation import prepare_pair, receipt_rows, release_preparation
from app.modules.workflow import lock_users, mutex, writer
from app.modules.duel_confirmation import confirmation_context, worker_consent_players, confirmed_players, clear_confirmations
from app.modules.duel_rules import validate_deck

ACTIVE = ('starting', 'running')


def consent(db, lobby_id, version, value, authorization, key):
    from app.modules.duel_lobbies import mutation, room_payload
    from types import SimpleNamespace
    user, lobby, seat = mutation(db, authorization, key, lobby_id, SimpleNamespace(version=version))
    if getattr(user, '_authenticated_session', None) != seat.session_hash:
        raise HTTPException(403, 'Verwende die ursprüngliche Lobby-Anmeldung.')
    if not value:
        clear_confirmations(db, lobby)
    else:
        context = confirmation_context(db, lobby)
        if not context or len(confirmed_players(db, lobby, context)) != 2:
            raise HTTPException(409, 'Zuerst müssen beide Decks bestätigt sein.')
        deck = db.get(PlayerDeck, seat.deck_id)
        if not validate_deck(db, user.id, json.loads(deck.entries_json), db.get(DuelRuleProfile, lobby.profile_id))['ready']:
            raise HTTPException(409, 'Deck oder Regelstand ist noch nicht für den geschlossenen Worker-Test freigegeben.')
        old = db.get(DuelWorkerConsent, user.id)
        if old: db.delete(old); db.flush()
        db.add(DuelWorkerConsent(user_id=user.id, lobby_id=lobby.id, context_hash=context,
                                expires_at=min(lobby.expires_at, datetime.utcnow() + timedelta(minutes=2))))
    lobby.version += 1; db.flush()
    result = room_payload(db, lobby, user.id); db.commit()
    return result


def participants_valid(db, run):
    from app.modules.duel_admission import restricted
    for participant in json.loads(run.participants_json):
        user = db.get(User, participant['user_id'], populate_existing=True)
        session = db.get(AuthSession, participant['session_hash'], populate_existing=True)
        if (not user or not user.is_active or not user.password_hash or restricted(db, user.id) or not session
                or session.user_id != user.id or session.expires_at <= datetime.utcnow()): return False
    profile = db.get(DuelRuleProfile, db.get(DuelPreparation, run.preparation_id).profile_id, populate_existing=True)
    return bool(profile and profile.engine_approved and profile.region_approved)


def authorize_run(db, run_id, authorization):
    user = get_current_user(authorization, db)
    run = db.get(DuelWorkerRun, run_id, populate_existing=True)
    participant = next((p for p in json.loads(run.participants_json) if p['user_id'] == user.id), None) if run else None
    if not participant: raise HTTPException(404, 'Duell nicht gefunden.')
    if not participant['session_hash'] or participant['session_hash'] != getattr(user, '_authenticated_session', None):
        raise HTTPException(403, 'Dieses Duell gehört zur ursprünglichen Anmeldung. Andere Sitzungen dürfen es nicht übernehmen.')
    return run, participant['seat']


def begin(db, lobby_id, version, authorization, key, instance, check_snapshot, manifest=None):
    user = writer(db, authorization, key)
    lobby = db.get(DuelLobby, lobby_id)
    if not lobby or lobby.host_id != user.id: raise HTTPException(404, 'Eigene Lobby nicht gefunden.')
    old = db.scalar(select(DuelWorkerRun).where(DuelWorkerRun.lobby_id == lobby_id))
    if old:
        authorize_run(db, old.id, authorization)
        return old.id, None
    from app.modules.duel_admission import require_slot
    require_slot(db)  # Same global transaction as the reservation/start receipt.
    if len(worker_consent_players(db, lobby)) != 2:
        raise HTTPException(409, 'Beide Spieler müssen zuerst ein aktuelles Deck auswählen.')
    receipt = prepare_pair(db, lobby_id, version)
    snapshot = json.loads(receipt.snapshot_json)
    check_snapshot(snapshot)  # Exact pinned sources and supported pool, never caller-supplied decks.
    seats = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby_id).order_by(DuelLobbySeat.seat)).all()
    if any(not s.session_hash for s in seats): raise HTTPException(403, 'Der Worker benötigt zwei echte Hub-Anmeldungen.')
    run = DuelWorkerRun(id=str(uuid4()), preparation_id=receipt.id, lobby_id=lobby_id, owner_instance=instance,
        state='starting', participants_json=json.dumps([{'user_id': s.user_id, 'seat': s.seat, 'session_hash': s.session_hash,
            'consent_expires_at': db.get(DuelWorkerConsent, s.user_id).expires_at.isoformat()} for s in seats]))
    db.add(run); receipt.state = 'starting'; lobby.state = 'starting'; lobby.version += 1
    db.flush()
    for seat in seats:
        db.add(DuelWorkerParticipant(run_id=run.id, user_id=seat.user_id, seat=seat.seat))
    if manifest is not None:
        db.flush()
        db.add(DuelWorkerLease(run_id=run.id, manifest_json=json.dumps(manifest)))
    db.commit()
    return run.id, snapshot


def activate(db, run_id, instance):
    mutex(db)
    run = db.get(DuelWorkerRun, run_id)
    if run.owner_instance != instance or run.state != 'starting': raise HTTPException(409, 'Worker-Zuordnung verändert.')
    lock_users(db, [p['user_id'] for p in json.loads(run.participants_json)])
    receipt = db.get(DuelPreparation, run.preparation_id)
    if (receipt.expires_at <= datetime.utcnow() or not participants_valid(db, run) or
            any(datetime.fromisoformat(p['consent_expires_at']) <= datetime.utcnow() for p in json.loads(run.participants_json))):
        raise HTTPException(409, 'Startberechtigung ist inzwischen abgelaufen.')
    receipt_rows(db, receipt)
    run.state = 'running'; receipt.state = 'running'
    db.get(DuelLobby, run.lobby_id).state = 'running'
    db.commit()


def finish_stopped(db, run_id, instance, reason, winner=None, replay=None):
    """Only the owner service calls this AFTER awaiting successful process termination."""
    scored = {'engine', 'surrender', 'decision_timeout', 'sideboard_forfeit'}
    if reason not in scored | {'worker_failure', 'session_ended', 'timeout', 'shutdown', 'server_restart', 'admin_abort', 'sideboard_timeout'}:
        raise ValueError('Unknown worker outcome')
    mutex(db)
    run = db.get(DuelWorkerRun, run_id)
    if run.owner_instance != instance: raise HTTPException(409, 'Fremder Worker darf nicht freigegeben werden.')
    if run.state not in ACTIVE: return
    release_preparation(db, run.preparation_id, 'worker_stopped', worker_stopped=True)
    run.state = 'finished' if reason in scored else 'aborted'
    run.reason = reason; run.winner_seat = winner if reason in scored and type(winner) is int and winner in (0, 1) else None
    run.ended_at = datetime.utcnow()
    from app.db.models import DuelMatchProgress
    progress = db.get(DuelMatchProgress, run_id)
    if progress:
        value = json.loads(progress.progress_json)
        value.update(phase=run.state, winner=run.winner_seat, reason=reason)
        progress.progress_json = json.dumps(value)
    if replay is not None:
        db.add(DuelWorkerReplay(run_id=run.id, views_json=json.dumps(replay, ensure_ascii=False),
            expires_at=datetime.utcnow() + timedelta(days=30)))
    lobby = db.get(DuelLobby, run.lobby_id)
    lobby.state = 'full'  # Transition through the existing idempotent membership cleanup.
    close_lobby(db, lobby)
    db.commit()


def public_receipt(run):
    return {'id': run.id, 'state': run.state, 'reason': run.reason, 'winner_seat': run.winner_seat,
            'ended_at': run.ended_at.isoformat() + 'Z' if run.ended_at else None}
