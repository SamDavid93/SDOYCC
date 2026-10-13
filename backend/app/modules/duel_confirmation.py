"""Deck-selection consent, separate from engine approval and actual match start."""
from datetime import datetime
from hashlib import sha256
import json

from sqlalchemy import select

from app.db.models import DuelDeckConfirmation, DuelLobbySeat, DuelPreparation, DuelWorkerConsent, PlayerDeck


def confirmation_context(db, lobby):
    from app.modules.duel_lobbies import eligible
    now = datetime.utcnow()
    seats = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby.id).order_by(DuelLobbySeat.seat)).all()
    if lobby.state != 'full' or lobby.expires_at <= now or len(seats) != 2: return None
    selection = []
    for seat in seats:
        deck = db.get(PlayerDeck, seat.deck_id) if seat.deck_id else None
        if (not seat.accepted or not eligible(db, seat, now) or not deck or deck.user_id != seat.user_id
                or deck.archived or deck.version != seat.deck_version or deck.profile_id != lobby.profile_id):
            return None
        selection.append([seat.user_id, seat.seat, seat.session_hash, deck.id, deck.version])
    # Lobby.version changes for confirmations too; hashing it would invalidate the first
    # player's consent when the second confirms. Membership mutations clear both rows.
    return sha256(json.dumps([lobby.id, lobby.profile_id, selection], separators=(',', ':')).encode()).hexdigest()


def confirmed_players(db, lobby, context=None):
    context = context or confirmation_context(db, lobby)
    if not context: return set()
    now = datetime.utcnow()
    return authorized_players(db, lobby, DuelDeckConfirmation, context, now)


def selection_context(lobby, seat):
    """Own explicit deck choice; joining, accepting or changing the other deck preserves it."""
    return sha256(json.dumps(['deck-selection-v1', lobby.id, lobby.profile_id, seat.user_id,
        seat.seat, seat.session_hash, seat.deck_id, seat.deck_version], separators=(',', ':')).encode()).hexdigest()


def selection_ready(db, lobby, seat):
    deck = db.get(PlayerDeck, seat.deck_id) if seat.deck_id else None
    row = db.get(DuelDeckConfirmation, seat.user_id)
    consent = db.get(DuelWorkerConsent, seat.user_id)
    return bool(seat.accepted and deck and not deck.archived and deck.version == seat.deck_version
        and deck.profile_id == lobby.profile_id and deck.user_id == seat.user_id
        and row and consent and row.lobby_id == consent.lobby_id == lobby.id
        and row.context_hash == consent.context_hash == selection_context(lobby, seat)
        and min(row.expires_at, consent.expires_at) > datetime.utcnow())


def authorized_players(db, lobby, model, context, now):
    seats = {seat.user_id: seat for seat in db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby.id))}
    return {row.user_id for row in db.scalars(select(model).where(model.lobby_id == lobby.id, model.expires_at > now))
        if row.user_id in seats and row.context_hash in (context, selection_context(lobby, seats[row.user_id]))}


def discard_selection(db, user_id):
    for model in (DuelDeckConfirmation, DuelWorkerConsent):
        row = db.get(model, user_id)
        if row: db.delete(row)
    db.flush()


def record_selection(db, lobby, seat):
    discard_selection(db, seat.user_id)
    context = selection_context(lobby, seat)
    for model in (DuelDeckConfirmation, DuelWorkerConsent):
        db.add(model(user_id=seat.user_id, lobby_id=lobby.id, context_hash=context, expires_at=lobby.expires_at))
    db.flush()


def clear_confirmations(db, lobby, *, preserve_selections=False):
    """Under workflow.mutex; changing a selection also cancels any pre-start hold."""
    receipt = db.scalar(select(DuelPreparation).where(DuelPreparation.lobby_id == lobby.id))
    if receipt and receipt.state == 'prepared':
        from app.modules.duel_preparation import release_preparation
        release_preparation(db, receipt.id, 'cancelled')
    for model in (DuelDeckConfirmation, DuelWorkerConsent):
        for row in db.scalars(select(model).where(model.lobby_id == lobby.id)).all():
            seat = db.get(DuelLobbySeat, row.user_id)
            if preserve_selections and seat and seat.lobby_id == lobby.id and row.context_hash == selection_context(lobby, seat): continue
            db.delete(row)
    db.flush()


def worker_consent_players(db, lobby, context=None):
    context = context or confirmation_context(db, lobby)
    if not context or len(confirmed_players(db, lobby, context)) != 2: return set()
    return authorized_players(db, lobby, DuelWorkerConsent, context, datetime.utcnow())
