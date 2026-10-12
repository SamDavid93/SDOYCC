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
    return set(db.scalars(select(DuelDeckConfirmation.user_id).where(
        DuelDeckConfirmation.lobby_id == lobby.id, DuelDeckConfirmation.context_hash == context,
        DuelDeckConfirmation.expires_at > now)))


def clear_confirmations(db, lobby):
    """Under workflow.mutex; changing a selection also cancels any pre-start hold."""
    receipt = db.scalar(select(DuelPreparation).where(DuelPreparation.lobby_id == lobby.id))
    if receipt and receipt.state == 'prepared':
        from app.modules.duel_preparation import release_preparation
        release_preparation(db, receipt.id, 'cancelled')
    for row in db.scalars(select(DuelDeckConfirmation).where(DuelDeckConfirmation.lobby_id == lobby.id)).all():
        db.delete(row)
    for row in db.scalars(select(DuelWorkerConsent).where(DuelWorkerConsent.lobby_id == lobby.id)).all():
        db.delete(row)
    db.flush()


def worker_consent_players(db, lobby, context=None):
    context = context or confirmation_context(db, lobby)
    if not context or len(confirmed_players(db, lobby, context)) != 2: return set()
    return set(db.scalars(select(DuelWorkerConsent.user_id).where(
        DuelWorkerConsent.lobby_id == lobby.id, DuelWorkerConsent.context_hash == context,
        DuelWorkerConsent.expires_at > datetime.utcnow())))
