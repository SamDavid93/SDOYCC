"""Private lobbies with accepted participants and immediately saved deck selections."""
from datetime import datetime, timedelta
import json
import re
import secrets
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import current_user
from app.core.auth import get_current_user
from app.core.rate_limit import throttle
from app.db.models import AuthSession, DuelDeckConfirmation, DuelLobby, DuelLobbySeat, DuelRuleProfile, DuelWorkerRun, PlayerDeck, User
from app.core.config import settings
from app.db.models import DuelLobbyOptions
from app.db.session import get_db
from app.modules.decks import own_deck, summary
from app.modules.duel_rules import profile_payload, validate_deck
from app.modules.duel_confirmation import clear_confirmations, confirmation_context, confirmed_players, worker_consent_players
from app.modules.duel_confirmation import selection_ready, record_selection, discard_selection
from app.modules.economy import finish, replay
from app.modules.duel_admission import restricted, require_player
from app.modules.workflow import Auth, Command, Key, action, lock_users, writer

router = APIRouter(prefix='/api/duel-zone', tags=['DuelZone'])
Database = Annotated[Session, Depends(get_db)]
ACTIVE = ('open', 'full')


class CreateLobby(Command):
    deck_id: str = Field(min_length=36, max_length=36)
    mode: Literal['single', 'match'] = 'single'
    ready: bool = Field(default=False, strict=True)


class JoinLobby(Command):
    code: str = Field(min_length=8, max_length=13)


class LobbyVersion(Command):
    version: int = Field(ge=1, strict=True)


class ChooseDeck(LobbyVersion):
    deck_id: str | None = Field(min_length=36, max_length=36)
    ready: bool = Field(default=False, strict=True)


class GuestDecision(LobbyVersion):
    accept: bool = Field(strict=True)


class DeckConfirmation(LobbyVersion):
    confirmed: bool = Field(strict=True)


def eligible(db, seat, now):
    user = db.get(User, seat.user_id)
    if not user or not user.is_active or not user.password_hash or not user.twitch_id or restricted(db, user.id, now): return False
    if seat.session_hash:
        session = db.get(AuthSession, seat.session_hash, populate_existing=True)
        if session is None or session.expires_at <= now: return False
    return True


def close_lobby(db, lobby, state='closed'):
    # D3a only: running matches are deliberately outside this cleanup path.
    if lobby.state not in ACTIVE: return
    clear_confirmations(db, lobby)
    for seat in db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby.id)):
        db.delete(seat)
    lobby.state = state; lobby.version += 1
    db.flush()


def cleanup_lobbies(db):
    """Call under workflow.mutex. Never frees a future running-match reservation."""
    now = datetime.utcnow()
    lobbies = db.scalars(select(DuelLobby).where(DuelLobby.state.in_(ACTIVE))).all()
    all_seats = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id.in_([room.id for room in lobbies]))).all()
    lock_users(db, [seat.user_id for seat in all_seats])
    for lobby in lobbies:
        seats = [seat for seat in all_seats if seat.lobby_id == lobby.id]
        host = next((seat for seat in seats if seat.seat == 0), None)
        if lobby.expires_at <= now or not host or not eligible(db, host, now):
            close_lobby(db, lobby, 'expired'); continue
        for seat in seats:
            if seat.seat == 1 and not eligible(db, seat, now):
                clear_confirmations(db, lobby, preserve_selections=True)
                discard_selection(db, seat.user_id)
                db.delete(seat); lobby.state = 'open'; lobby.version += 1
    db.flush()


def room_payload(db, lobby, user_id):
    members = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby.id).order_by(DuelLobbySeat.seat)).all()
    if not any(member.user_id == user_id for member in members): raise HTTPException(404, 'Lobby nicht gefunden.')
    now = datetime.utcnow()
    active = ((lobby.state in ACTIVE and lobby.expires_at > now) or lobby.state in ('starting', 'running')) and all(eligible(db, seat, now) for seat in members)
    own = next(seat for seat in members if seat.user_id == user_id)
    own_list = db.get(PlayerDeck, own.deck_id) if own.deck_id else None
    profile = db.get(DuelRuleProfile, lobby.profile_id)
    context = confirmation_context(db, lobby)
    confirmed = confirmed_players(db, lobby, context) if context else set()
    worker_consents = worker_consent_players(db, lobby, context) if context else set()
    run_id = db.scalar(select(DuelWorkerRun.id).where(DuelWorkerRun.lobby_id == lobby.id))
    options = db.get(DuelLobbyOptions, lobby.id)
    from app.modules.duel_admission import status
    admission = status(db)
    if not active or lobby.state not in ACTIVE: blocker = 'Die Lobby ist nicht mehr für einen neuen Duellstart geöffnet.'
    elif not settings.duel_worker_enabled: blocker = 'Der Duellbetrieb ist auf diesem Server ausgeschaltet.'
    elif not admission['accepting_new']: blocker = 'Wartung: Neue Duelle sind vorübergehend pausiert.'
    elif not admission['available_slots']: blocker = 'Alle Duellplätze sind belegt. Warte auf einen freien Platz.'
    elif not profile or not profile.engine_approved or not profile.region_approved: blocker = 'Der gewählte Regelstand benötigt die Engine- und Regionsfreigabe.'
    elif not context: blocker = 'Der Gast muss angenommen sein und beide Spieler müssen ein aktuelles Deck auswählen.'
    elif len(confirmed) != 2 or len(worker_consents) != 2: blocker = 'Beide Spieler müssen ein aktuelles Deck auswählen.'
    else: blocker = ''
    return {'id': lobby.id, 'code': 'SDO-' + lobby.code[:4] + '-' + lobby.code[4:], 'host_id': lobby.host_id,
            'version': lobby.version, 'state': lobby.state if active else 'expired',
            'expires_at': lobby.expires_at.isoformat() + 'Z', 'server_time': now.isoformat() + 'Z',
            'profile': profile_payload(profile), 'own_deck': summary(own_list) if own_list else None,
            'mode': options.mode if options else 'single',
            'worker_run_id': run_id, 'worker_test_available': settings.duel_worker_enabled,
            'worker_alpha': settings.app_env == 'production' and settings.enable_duel_alpha,
            'worker_both_consented': len(worker_consents) == 2,
            'can_confirm_deck': bool(context), 'both_decks_confirmed': len(confirmed) == 2,
            'own_deck_changed': bool(own_list and (own_list.version != own.deck_version or own_list.archived or own_list.profile_id != lobby.profile_id)),
            'members': [{'user_id': s.user_id, 'name': db.get(User, s.user_id).display_name, 'seat': s.seat,
                         'accepted': s.accepted, 'deck_selected': bool(s.deck_id),
                         'deck_ready': selection_ready(db, lobby, s),
                         'deck_confirmed': s.user_id in confirmed, 'worker_consented': s.user_id in worker_consents} for s in members],
            'can_start': not blocker, 'start_blocker': blocker, 'admission': admission}


def mutation(db, auth, key, lobby_id, payload):
    user = writer(db, auth, key)
    lobby = db.get(DuelLobby, lobby_id)
    seat = db.get(DuelLobbySeat, user.id)
    if not lobby or not seat or seat.lobby_id != lobby_id: raise HTTPException(404, 'Lobby nicht gefunden.')
    members = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby_id)).all()
    lock_users(db, [s.user_id for s in members])
    now = datetime.utcnow()
    if lobby.state not in ACTIVE or lobby.expires_at <= now or not all(eligible(db, s, now) for s in members):
        raise HTTPException(409, 'Lobby ist abgelaufen oder eine Anmeldung wurde beendet. Verlasse die Lobby und öffne eine neue.')
    if lobby.version != payload.version: raise HTTPException(409, 'Die Lobby wurde verändert. Bitte mit dem aktuellen Stand erneut versuchen.')
    return user, lobby, seat


def chosen_deck(db, user_id, deck_id, profile_id=None):
    deck = own_deck(db, user_id, deck_id)
    if deck.archived or not deck.profile_id: raise HTTPException(409, 'Wähle ein aktives Deck mit versioniertem Regelstand.')
    if profile_id and deck.profile_id != profile_id: raise HTTPException(409, 'Dein Deck benötigt genau den Regelstand dieser Lobby.')
    return deck


def check_selected_deck(db, user_id, deck):
    check = validate_deck(db, user_id, json.loads(deck.entries_json), db.get(DuelRuleProfile, deck.profile_id))
    if not check['rules_ok'] or not check['stock_ok']:
        raise HTTPException(409, 'Dein Deck erfüllt die Deckregeln oder Kartenverfügbarkeit noch nicht. Prüfe es unter Meine Decks.')


@router.get('/me')
def my_lobby(db: Database, user=Depends(current_user)):
    seat = db.get(DuelLobbySeat, user.id)
    return room_payload(db, db.get(DuelLobby, seat.lobby_id), user.id) if seat else None


@router.post('/lobbies')
def create_lobby(body: CreateLobby, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = get_current_user(authorization, db)
    throttle(db, [(f'lobby-create:{actor.id}', 5)], seconds=600)
    user = writer(db, authorization, idempotency_key)
    require_player(db, user.id)
    fingerprint = action('lobby:create', body)
    old = replay(db, user, idempotency_key, fingerprint)
    if old is not None: return old
    cleanup_lobbies(db)
    if db.get(DuelLobbySeat, user.id): raise HTTPException(409, 'Du bist bereits in einer Lobby. Verlasse sie zuerst.')
    deck = chosen_deck(db, user.id, body.deck_id)
    if body.ready: check_selected_deck(db, user.id, deck)
    for _ in range(10):
        code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
        if not db.scalar(select(DuelLobby.id).where(DuelLobby.code == code)): break
    else: raise HTTPException(503, 'Lobby-Code konnte nicht erzeugt werden. Bitte erneut versuchen.')
    lobby = DuelLobby(id=str(uuid4()), code=code, host_id=user.id, profile_id=deck.profile_id,
                      expires_at=datetime.utcnow() + timedelta(minutes=15), state='open', version=1)
    db.add(lobby); db.flush()
    db.add(DuelLobbyOptions(lobby_id=lobby.id, mode=body.mode))
    db.add(DuelLobbySeat(user_id=user.id, lobby_id=lobby.id, seat=0, accepted=True, deck_id=deck.id,
                         deck_version=deck.version, session_hash=getattr(user, '_authenticated_session', None)))
    db.flush()
    if body.ready: record_selection(db, lobby, db.get(DuelLobbySeat, user.id))
    return finish(db, user, idempotency_key, fingerprint, room_payload(db, lobby, user.id))


@router.post('/join')
def join_lobby(body: JoinLobby, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    actor = get_current_user(authorization, db)
    throttle(db, [(f'lobby-join:{actor.id}', 10)])
    user = writer(db, authorization, idempotency_key)
    require_player(db, user.id)
    fingerprint = action('lobby:join', body)
    old = replay(db, user, idempotency_key, fingerprint)
    if old is not None: return old
    cleanup_lobbies(db)
    if db.get(DuelLobbySeat, user.id): raise HTTPException(409, 'Du bist bereits in einer Lobby. Verlasse sie zuerst.')
    code = body.code.upper()
    if re.fullmatch(r'SDO-[A-Z2-9]{4}-[A-Z2-9]{4}', code): code = code[4:8] + code[9:13]
    elif not re.fullmatch(r'[A-Z2-9]{8}', code): raise HTTPException(404, 'Keine freie Lobby mit diesem Code gefunden.')
    lobby = db.scalar(select(DuelLobby).where(DuelLobby.code == code, DuelLobby.state == 'open'))
    if not lobby: raise HTTPException(404, 'Keine freie Lobby mit diesem Code gefunden.')
    lock_users(db, [lobby.host_id, user.id])
    clear_confirmations(db, lobby, preserve_selections=True)
    db.add(DuelLobbySeat(user_id=user.id, lobby_id=lobby.id, seat=1, accepted=False,
                         session_hash=getattr(user, '_authenticated_session', None)))
    lobby.state = 'full'; lobby.version += 1; lobby.expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.flush()
    return finish(db, user, idempotency_key, fingerprint, room_payload(db, lobby, user.id))


@router.post('/lobbies/{lobby_id}/guest')
def guest_decision(lobby_id: str, body: GuestDecision, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    user, lobby, seat = mutation(db, authorization, idempotency_key, lobby_id, body)
    if seat.seat != 0: raise HTTPException(403, 'Nur der Gastgeber darf einen Gast bestätigen oder entfernen.')
    guest = db.scalar(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby.id, DuelLobbySeat.seat == 1))
    if not guest: raise HTTPException(409, 'Es wartet kein Gast in dieser Lobby.')
    clear_confirmations(db, lobby, preserve_selections=True)
    if body.accept: guest.accepted = True
    else:
        discard_selection(db, guest.user_id)
        db.delete(guest); lobby.state = 'open'
    lobby.version += 1; lobby.expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.flush(); result = room_payload(db, lobby, user.id); db.commit()
    return result


@router.post('/lobbies/{lobby_id}/deck')
def select_deck(lobby_id: str, body: ChooseDeck, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    user, lobby, seat = mutation(db, authorization, idempotency_key, lobby_id, body)
    if not seat.accepted: raise HTTPException(409, 'Warte zunächst auf die Bestätigung des Gastgebers.')
    if getattr(user, '_authenticated_session', None) != seat.session_hash:
        raise HTTPException(403, 'Verwende die ursprüngliche Lobby-Anmeldung.')
    deck = chosen_deck(db, user.id, body.deck_id, lobby.profile_id) if body.deck_id else None
    if body.ready and deck: check_selected_deck(db, user.id, deck)
    clear_confirmations(db, lobby, preserve_selections=True)
    discard_selection(db, user.id)
    seat.deck_id = deck.id if deck else None; seat.deck_version = deck.version if deck else None
    lobby.version += 1; lobby.expires_at = datetime.utcnow() + timedelta(minutes=15)
    if body.ready and deck: record_selection(db, lobby, seat)
    db.flush(); result = room_payload(db, lobby, user.id); db.commit()
    return result


@router.post('/lobbies/{lobby_id}/leave')
def leave_lobby(lobby_id: str, body: LobbyVersion, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    # Leaving must also work when expired or the other participant was blocked.
    user = writer(db, authorization, idempotency_key)
    lobby = db.get(DuelLobby, lobby_id); seat = db.get(DuelLobbySeat, user.id)
    if not lobby or not seat or seat.lobby_id != lobby_id: raise HTTPException(404, 'Lobby nicht gefunden.')
    if lobby.state not in ACTIVE: raise HTTPException(409, 'Diese Lobby kann nicht mehr verlassen werden.')
    if lobby.version != body.version: raise HTTPException(409, 'Lobby verändert. Bitte erneut versuchen.')
    if seat.seat == 0: close_lobby(db, lobby)
    else:
        clear_confirmations(db, lobby, preserve_selections=True)
        discard_selection(db, user.id)
        db.delete(seat); lobby.state = 'open'; lobby.version += 1
    db.commit()
    return {'left': True}


@router.post('/lobbies/{lobby_id}/ready')
def ready(lobby_id: str, body: LobbyVersion, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    mutation(db, authorization, idempotency_key, lobby_id, body)
    # Deliberately fail closed even if somebody manually changes profile flags.
    raise HTTPException(409, 'Noch nicht verfügbar: Der vollständige Duellstart mit atomarer Kartenreservierung wird erst nach der Engine-Abnahme aktiviert.')


@router.post('/lobbies/{lobby_id}/confirm-deck')
def confirm_deck(lobby_id: str, body: DeckConfirmation, db: Database, authorization: Auth = None, idempotency_key: Key = None):
    user, lobby, seat = mutation(db, authorization, idempotency_key, lobby_id, body)
    if getattr(user, '_authenticated_session', None) != seat.session_hash:
        raise HTTPException(403, 'Bestätige das Deck in der Anmeldung, mit der du der Lobby beigetreten bist.')
    if not body.confirmed:
        clear_confirmations(db, lobby)
    else:
        context = confirmation_context(db, lobby)
        if not context:
            raise HTTPException(409, 'Beide Spieler müssen bestätigt sein und ein aktuelles Deck ausgewählt haben.')
        deck = chosen_deck(db, user.id, seat.deck_id, lobby.profile_id)
        check = validate_deck(db, user.id, json.loads(deck.entries_json), db.get(DuelRuleProfile, lobby.profile_id))
        if not check['rules_ok'] or not check['stock_ok']:
            raise HTTPException(409, 'Dein Deck erfüllt die Deckregeln oder Kartenverfügbarkeit noch nicht. Prüfe es unter Meine Decks.')
        # Engine approval is deliberately separate: confirming an owned draft starts no game.
        row = db.get(DuelDeckConfirmation, user.id)
        if row: db.delete(row); db.flush()
        db.add(DuelDeckConfirmation(user_id=user.id, lobby_id=lobby.id, context_hash=context,
            expires_at=min(lobby.expires_at, datetime.utcnow() + timedelta(minutes=5))))
    lobby.version += 1
    db.flush(); result = room_payload(db, lobby, user.id); db.commit()
    return result
