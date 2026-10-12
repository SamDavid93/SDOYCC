"""Internal D3b transaction boundary. No endpoint and no engine launch yet.

Caller holds workflow.mutex and commits/rolls back the outer transaction. Each
operation uses a savepoint so even a caught failure cannot commit half a pair.
Nothing here grants/removes cards, credits or XP. Snapshots never enter lobby DTOs.
"""
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import (CardVariant, DuelLobby, DuelLobbySeat, DuelPreparation,
                           DuelDeckConfirmation, DuelRuleProfile, DuelStockReservation, PlayerDeck, VariantInventory)
from app.modules.duel_lobbies import eligible
from app.modules.duel_rules import validate_deck
from app.modules.inventory import reservation_totals
from app.modules.workflow import lock_users
from app.modules.duel_confirmation import confirmed_players


def receipt_rows(db, receipt):
    """Reject missing/altered rows and shared-counter drift before retry/release."""
    if sha256(receipt.snapshot_json.encode()).hexdigest() != receipt.snapshot_hash:
        raise HTTPException(409, 'Duell-Snapshot inkonsistent. Verwaltung verständigen.')
    expected_cards = Counter()
    for player in json.loads(receipt.snapshot_json)['players']:
        for entry in player['entries']:
            expected_cards[(player['user_id'], entry['card_id'])] += entry['quantity']
    rows = db.execute(select(DuelStockReservation, VariantInventory, CardVariant.card_id).join(
        VariantInventory, VariantInventory.id == DuelStockReservation.stock_id).join(
        CardVariant, CardVariant.id == VariantInventory.variant_id).where(
        DuelStockReservation.preparation_id == receipt.id, DuelStockReservation.active.is_(True))).all()
    actual_cards = Counter()
    counters = reservation_totals(db)
    for reservation, stock, card_id in rows:
        actual_cards[(stock.user_id, card_id)] += reservation.quantity
        if (stock.reserved < reservation.quantity or
                stock.reserved != counters.get((stock.user_id, stock.variant_id, stock.bound), 0)):
            raise HTTPException(409, 'Reservierungsbestand inkonsistent. Verwaltung verständigen.')
    if actual_cards != expected_cards:
        raise HTTPException(409, 'Duellreservierung unvollständig. Verwaltung verständigen.')
    return [(reservation, stock) for reservation, stock, _ in rows]


def prepare_pair(db, lobby_id, expected_version):
    """Requires approved rules AND a fresh accepted two-seat lobby, under mutex.

    A stable preparation per lobby provides retry safety. Released preparations
    are terminal: a fresh lobby is required. Full worker launch is a later step.
    """
    with db.begin_nested():
        lobby = db.get(DuelLobby, lobby_id, populate_existing=True)
        if not lobby: raise HTTPException(404, 'Lobby nicht gefunden.')
        old = db.scalar(select(DuelPreparation).where(DuelPreparation.lobby_id == lobby_id))
        if old:
            if old.state != 'prepared' or old.expires_at <= datetime.utcnow():
                raise HTTPException(409, 'Startvorbereitung beendet. Bitte eine neue Lobby öffnen.')
            receipt_rows(db, old)
            snapshot = json.loads(old.snapshot_json)
            if snapshot['lobby_version'] != expected_version:
                raise HTTPException(409, 'Die Lobby wurde mit einem anderen Stand vorbereitet.')
            # A retry must not bypass session, version or profile revocation checks.
        seats = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == lobby_id).order_by(DuelLobbySeat.seat)).all()
        lock_users(db, [seat.user_id for seat in seats])
        now = datetime.utcnow()
        if (lobby.state != 'full' or lobby.expires_at <= now or lobby.version != expected_version
                or len(seats) != 2 or [s.seat for s in seats] != [0, 1]
                or any(not s.accepted or not eligible(db, s, now) for s in seats)):
            raise HTTPException(409, 'Beide bestätigten Spieler und ein aktueller Lobby-Stand sind erforderlich.')
        if confirmed_players(db, lobby) != {seat.user_id for seat in seats}:
            raise HTTPException(409, 'Beide Spieler müssen ihre aktuelle Deckauswahl ausdrücklich bestätigen.')
        confirmations = db.scalars(select(DuelDeckConfirmation).where(DuelDeckConfirmation.lobby_id == lobby.id)).all()
        profile = db.get(DuelRuleProfile, lobby.profile_id)
        if not profile or not profile.engine_approved or not profile.region_approved:
            raise HTTPException(409, 'Der Regelstand ist noch nicht für Browserduelle freigegeben.')
        players, allocation = [], []
        for seat in seats:
            deck = db.get(PlayerDeck, seat.deck_id) if seat.deck_id else None
            if (not deck or deck.user_id != seat.user_id or deck.archived or deck.version != seat.deck_version
                    or deck.profile_id != lobby.profile_id):
                raise HTTPException(409, 'Ein ausgewähltes Deck wurde geändert. Bitte erneut auswählen.')
            if old:
                saved = next(p for p in snapshot['players'] if p['user_id'] == seat.user_id)
                if saved['deck_id'] != deck.id or saved['deck_version'] != deck.version:
                    raise HTTPException(409, 'Die Deckauswahl stimmt nicht mehr mit der Vorbereitung überein.')
                check = validate_deck(db, seat.user_id, json.loads(deck.entries_json), profile)
                if not check['rules_ok'] or not check['engine_ok'] or any(i['code'] == 'stock_unverified' for i in check['issues']):
                    raise HTTPException(409, 'Regeln oder Bestandszuordnung müssen erneut geprüft werden.')
                continue
            entries = json.loads(deck.entries_json)
            check = validate_deck(db, seat.user_id, entries, profile)
            if not check['ready']:
                # No opponent card names, counts or private validation details in this error.
                raise HTTPException(409, 'Mindestens ein Deck erfüllt Regeln oder Kartenverfügbarkeit nicht mehr.')
            demand = Counter()
            for entry in entries: demand[entry['card_id']] += entry['quantity']
            stock = db.execute(select(VariantInventory, CardVariant.card_id).join(CardVariant).where(
                VariantInventory.user_id == seat.user_id, CardVariant.card_id.in_(demand),
                VariantInventory.quantity > VariantInventory.reserved).order_by(
                VariantInventory.bound.desc(), VariantInventory.id)).all()
            # Prefer bound copies so the user's tradable collection remains available.
            for row, card_id in stock:
                take = min(demand[card_id], row.quantity - row.reserved)
                if take: allocation.append((row, take)); demand[card_id] -= take
            if any(demand.values()): raise HTTPException(409, 'Kartenbestand wurde zwischenzeitlich verändert.')
            players.append({'user_id': seat.user_id, 'seat': seat.seat, 'deck_id': deck.id,
                            'deck_version': deck.version, 'sections': {
                section: [check['rules'][entry['card_id']]['passcode'] for entry in entries
                          if entry['section'] == section for _ in range(entry['quantity'])]
                for section in ('main', 'extra', 'side')}, 'entries': entries})
        expected = reservation_totals(db)
        if any(row.reserved != expected.get((row.user_id, row.variant_id, row.bound), 0) for row, _ in allocation):
            raise HTTPException(409, 'Reservierungsbestand inkonsistent. Verwaltung verständigen.')
        if old: return old
        from app.db.models import DuelLobbyOptions
        options = db.get(DuelLobbyOptions, lobby.id)
        snapshot_json = json.dumps({'schema': 1, 'mode': options.mode if options else 'single', 'lobby_version': expected_version, 'profile_id': profile.id,
                                    'sources': json.loads(profile.sources_json), 'players': players,
                                    'confirmations': [{'user_id': c.user_id, 'context_hash': c.context_hash,
                                                      'confirmed_at': c.created_at.isoformat() + 'Z'} for c in confirmations]},
                                   sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        receipt = DuelPreparation(id=str(uuid4()), lobby_id=lobby_id, profile_id=profile.id, state='prepared',
            snapshot_json=snapshot_json, snapshot_hash=sha256(snapshot_json.encode()).hexdigest(),
            expires_at=min(lobby.expires_at, now + timedelta(minutes=2), *(c.expires_at for c in confirmations)))
        db.add(receipt); db.flush()
        for row, quantity in allocation:
            row.reserved += quantity
            db.add(DuelStockReservation(preparation_id=receipt.id, stock_id=row.id, quantity=quantity, active=True))
        db.flush()
        return receipt


def release_preparation(db, preparation_id, reason, *, worker_stopped=False):
    """Ordinary callers can only release pre-start holds. The internal worker may
    pass worker_stopped only AFTER awaiting confirmed process termination.
    """
    if reason not in {'cancelled', 'start_failed', 'expired', 'session_ended', 'lobby_changed', 'worker_stopped'}:
        raise ValueError('Unknown preparation release reason')
    with db.begin_nested():
        receipt = db.get(DuelPreparation, preparation_id, populate_existing=True)
        if not receipt: raise HTTPException(404, 'Startvorbereitung nicht gefunden.')
        if receipt.state == 'released': return receipt
        allowed = {'prepared', 'starting', 'running'} if worker_stopped else {'prepared'}
        if receipt.state not in allowed: raise HTTPException(409, 'Ein gestartetes Duell darf hier nicht freigegeben werden.')
        rows = receipt_rows(db, receipt)
        lock_users(db, [stock.user_id for _, stock in rows])
        # Validate every row before touching one: fail closed on corrupted counters.
        for reservation, stock in rows:
            stock.reserved -= reservation.quantity; reservation.active = False
        receipt.state = 'released'; receipt.release_reason = reason; receipt.released_at = datetime.utcnow()
        db.flush()
        return receipt


def cleanup_preparations(db):
    """Restart-safe pre-start cleanup, under workflow.mutex; no running matches."""
    now = datetime.utcnow()
    for receipt in db.scalars(select(DuelPreparation).where(DuelPreparation.state == 'prepared')).all():
        lobby = db.get(DuelLobby, receipt.lobby_id)
        seats = db.scalars(select(DuelLobbySeat).where(DuelLobbySeat.lobby_id == receipt.lobby_id)).all()
        if receipt.expires_at <= now or not lobby or lobby.expires_at <= now:
            release_preparation(db, receipt.id, 'expired')
        elif lobby.state != 'full' or len(seats) != 2 or lobby.version != json.loads(receipt.snapshot_json)['lobby_version']:
            release_preparation(db, receipt.id, 'lobby_changed')
        elif any(not eligible(db, seat, now) for seat in seats):
            release_preparation(db, receipt.id, 'session_ended')
        elif confirmed_players(db, lobby) != {seat.user_id for seat in seats}:
            release_preparation(db, receipt.id, 'lobby_changed')
