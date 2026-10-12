"""Isolated start-boundary tests; approvals here belong to artificial test rules."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.auth import create_session
from app.db.models import (CardVariant, DuelDeckConfirmation, DuelLobby, DuelPreparation, DuelRuleProfile, DuelStockReservation,
                           PlayerDeck, User, VariantInventory)
from app.modules.admin_extended import operations
from app.modules.duel_preparation import cleanup_preparations, prepare_pair, release_preparation
from app.modules.inventory import change_stock, variant
from app.modules.trading import reserve, release
from app.modules.workflow import mutex
from test_decks import DeckTestCase


class PreparationFixture(DeckTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            for uid in (1, 2):
                user = db.get(User, uid)
                user.twitch_id = str(200000 + uid); user.password_hash = 'test-fixture'
                token = create_session(db, user)
                if uid == 1: self.headers = {'Authorization': 'Bearer ' + token}
                else: self.other_headers = {'Authorization': 'Bearer ' + token}
            for cid in range(1, 24):
                change_stock(db, 2, variant(db, cid, 'rare'), 3, 'test', f'guest:{cid}', bound=(cid == 1))
            # Only this temporary database has artificial approvals, never the imported real profile.
            profile = db.get(DuelRuleProfile, self.profile)
            profile.engine_approved = profile.region_approved = True
            db.commit()
        body = {**self.body, 'entries': [*self.body['entries'],
                {'card_id': 22, 'section': 'extra', 'quantity': 1},
                {'card_id': 15, 'section': 'side', 'quantity': 2}]}
        self.decks = [self.client.post('/api/decks', json=body, headers=h).json()
                      for h in (self.headers, self.other_headers)]
        def post(path, payload, headers):
            response = self.client.post('/api/duel-zone' + path, json=payload,
                headers={**headers, 'Idempotency-Key': str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()
        room = post('/lobbies', {'deck_id': self.decks[0]['id']}, self.headers)
        room = post('/join', {'code': room['code']}, self.other_headers)
        room = post(f'/lobbies/{room["id"]}/guest', {'version': room['version'], 'accept': True}, self.headers)
        room = post(f'/lobbies/{room["id"]}/deck', {'version': room['version'], 'deck_id': self.decks[1]['id']}, self.other_headers)
        for headers in (self.headers, self.other_headers):
            room = post(f'/lobbies/{room["id"]}/confirm-deck', {'version': room['version'], 'confirmed': True}, headers)
        self.room = room

    def prepare(self):
        with self.sessions() as db:
            mutex(db)
            row = prepare_pair(db, self.room['id'], self.room['version'])
            receipt = row.id
            db.commit()
            return receipt

    def free(self, receipt, reason='start_failed'):
        with self.sessions() as db:
            mutex(db); release_preparation(db, receipt, reason); db.commit()

    def total(self):
        with self.sessions() as db:
            return db.scalar(select(func.sum(VariantInventory.reserved)))


class PreparationTests(PreparationFixture):
    def test_pair_snapshot_all_sections_and_idempotent_release(self):
        receipt = self.prepare()
        self.assertEqual(self.prepare(), receipt)
        self.assertEqual(self.total(), 86)
        with self.sessions() as db:
            row = db.get(DuelPreparation, receipt)
            self.assertEqual(sha256(row.snapshot_json.encode()).hexdigest(), row.snapshot_hash)
            snapshot = json.loads(row.snapshot_json)
            self.assertEqual(snapshot['profile_id'], self.profile)
            for p in snapshot['players']:
                self.assertEqual({k: len(v) for k, v in p['sections'].items()}, {'main': 40, 'extra': 1, 'side': 2})
            status = operations(db)
            self.assertTrue(status['inventory_consistent']); self.assertTrue(status['journal_consistent'])
            self.assertTrue(status['reservations_consistent']); self.assertEqual(status['reserved_cards'], 86)
            # Frozen receipt survives later private editor changes.
            deck = db.get(PlayerDeck, self.decks[0]['id']); deck.entries_json = '[]'; deck.version += 1
            original = row.snapshot_json; db.commit()
        with self.assertRaises(HTTPException): self.prepare()
        self.free(receipt); self.free(receipt, 'cancelled')
        self.assertEqual(self.total(), 0)
        with self.sessions() as db:
            row = db.get(DuelPreparation, receipt)
            self.assertEqual(row.snapshot_json, original); self.assertEqual(row.release_reason, 'start_failed')
        with self.assertRaises(HTTPException): self.prepare()

    def test_bound_copies_preferred_and_inventory_removal_blocked(self):
        with self.sessions() as db:
            change_stock(db, 1, variant(db, 1, 'rare'), 3, 'test', 'unbound-alternative'); db.commit()
        receipt = self.prepare()
        with self.sessions() as db:
            rows = db.scalars(select(VariantInventory).join(CardVariant).where(
                VariantInventory.user_id == 1, CardVariant.card_id == 1)).all()
            self.assertEqual({row.bound: row.reserved for row in rows}, {True: 3, False: 0})
            with self.assertRaises(HTTPException):
                change_stock(db, 1, variant(db, 1, 'rare'), -1, 'test', 'cannot-remove-bound', bound=True)
            db.rollback()
        self.free(receipt)
        with self.sessions() as db:
            change_stock(db, 1, variant(db, 1, 'rare'), -1, 'test', 'can-remove-bound', bound=True); db.commit()

    def test_other_players_shortage_never_leaves_half_pair(self):
        with self.sessions() as db:
            change_stock(db, 2, variant(db, 2, 'rare'), -1, 'test', 'shortage'); db.commit()
        with self.sessions() as db:
            mutex(db)
            with self.assertRaises(HTTPException): prepare_pair(db, self.room['id'], self.room['version'])
            # Explicit commit after a caught error must still not leave partial reservations.
            db.commit()
            self.assertEqual(db.scalar(select(func.count(DuelPreparation.id))), 0)
        self.assertEqual(self.total(), 0)

    def test_same_variant_trade_and_duel_release_independently(self):
        with self.sessions() as db:
            mutex(db); kind = variant(db, 14, 'rare')
            reserve(db, 1, [{'variant_id': kind.id, 'quantity': 1}], 'listing:test'); db.commit()
        receipt = self.prepare()
        self.assertEqual(self.total(), 87)
        self.free(receipt)
        self.assertEqual(self.total(), 1)
        with self.sessions() as db:
            self.assertTrue(operations(db)['reservations_consistent'])
            mutex(db); release(db, 'listing:test'); db.commit()
        self.assertEqual(self.total(), 0)

    def test_trade_and_duel_race_one_wins_without_overreservation(self):
        def trade():
            with self.sessions() as db:
                mutex(db)
                try:
                    reserve(db, 1, [{'variant_id': variant(db, 2, 'rare').id, 'quantity': 1}], 'listing:race')
                    db.commit(); return 'trade'
                except HTTPException: db.rollback(); return 'blocked'
        def duel():
            try: self.prepare(); return 'duel'
            except HTTPException: return 'blocked'
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(trade), pool.submit(duel)]
            results = [future.result() for future in futures]
        self.assertEqual(results.count('blocked'), 1)
        self.assertIn(self.total(), (1, 86))
        with self.sessions() as db: self.assertTrue(operations(db)['reservations_consistent'])

    def test_concurrent_preparation_retries_reserve_once(self):
        with ThreadPoolExecutor(2) as pool: ids = list(pool.map(lambda _: self.prepare(), range(2)))
        self.assertEqual(ids[0], ids[1]); self.assertEqual(self.total(), 86)

    def test_engine_and_region_gates_and_stale_deck(self):
        for attribute in ('engine_approved', 'region_approved'):
            with self.sessions() as db: setattr(db.get(DuelRuleProfile, self.profile), attribute, False); db.commit()
            with self.assertRaises(HTTPException): self.prepare()
            with self.sessions() as db: setattr(db.get(DuelRuleProfile, self.profile), attribute, True); db.commit()
        with self.sessions() as db: db.get(PlayerDeck, self.decks[1]['id']).version += 1; db.commit()
        with self.assertRaises(HTTPException): self.prepare()
        self.assertEqual(self.total(), 0)

    def test_restart_cleanup_expiry_idempotent(self):
        receipt = self.prepare()
        with self.sessions() as db:
            db.get(DuelPreparation, receipt).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        for _ in range(2):
            with self.sessions() as db: mutex(db); cleanup_preparations(db); db.commit()
        self.assertEqual(self.total(), 0)

    def test_account_revocation_and_changed_lobby_cleanup(self):
        receipt = self.prepare()
        with self.sessions() as db: db.get(User, 2).is_active = False; db.commit()
        with self.assertRaises(HTTPException): self.prepare()
        with self.sessions() as db:
            mutex(db); cleanup_preparations(db); db.commit()
            self.assertEqual(db.get(DuelPreparation, receipt).release_reason, 'session_ended')
        self.assertEqual(self.total(), 0)

    def test_running_matches_never_released_by_preparation_cleanup(self):
        receipt = self.prepare()
        with self.sessions() as db:
            row = db.get(DuelPreparation, receipt); row.state = 'running'
            row.expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        with self.assertRaises(HTTPException): self.free(receipt)
        with self.sessions() as db: mutex(db); cleanup_preparations(db); db.commit()
        self.assertEqual(self.total(), 86)

    def test_counter_corruption_release_fails_without_partial_changes(self):
        receipt = self.prepare()
        with self.sessions() as db:
            row = db.scalar(select(VariantInventory).where(VariantInventory.reserved > 0).order_by(VariantInventory.id.desc()))
            row.reserved = 0; db.commit()
            before = {r.id: r.reserved for r in db.scalars(select(VariantInventory))}
        with self.sessions() as db:
            mutex(db)
            with self.assertRaises(HTTPException): release_preparation(db, receipt, 'start_failed')
            db.commit()
            self.assertEqual({r.id: r.reserved for r in db.scalars(select(VariantInventory))}, before)
            self.assertEqual(db.get(DuelPreparation, receipt).state, 'prepared')
            self.assertFalse(operations(db)['reservations_consistent'])

    def test_incomplete_receipt_is_not_silently_retried_or_released(self):
        receipt = self.prepare()
        with self.sessions() as db:
            reservation = db.scalar(select(DuelStockReservation).where(DuelStockReservation.preparation_id == receipt))
            reservation.active = False; db.commit()
        before = self.total()
        with self.assertRaises(HTTPException): self.prepare()
        with self.assertRaises(HTTPException): self.free(receipt)
        self.assertEqual(self.total(), before)

    def test_lobby_mutation_invalidates_preparation_on_cleanup(self):
        receipt = self.prepare()
        with self.sessions() as db: db.get(DuelLobby, self.room['id']).version += 1; db.commit()
        with self.assertRaises(HTTPException): self.prepare()
        with self.sessions() as db:
            mutex(db); cleanup_preparations(db); db.commit()
            self.assertEqual(db.get(DuelPreparation, receipt).release_reason, 'lobby_changed')
        self.assertEqual(self.total(), 0)

    def test_preparation_requires_two_unexpired_explicit_confirmations(self):
        with self.sessions() as db:
            db.get(DuelDeckConfirmation, 2).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        with self.assertRaises(HTTPException): self.prepare()
        self.assertEqual(self.total(), 0)

    def test_withdrawing_confirmation_releases_pair_immediately(self):
        receipt = self.prepare()
        response = self.client.post(f'/api/duel-zone/lobbies/{self.room["id"]}/confirm-deck',
            json={'version': self.room['version'], 'confirmed': False},
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.total(), 0)
        self.assertFalse(response.json()['both_decks_confirmed'])
        with self.sessions() as db: self.assertEqual(db.get(DuelPreparation, receipt).state, 'released')

    def test_deck_edit_cleans_up_prestart_reservations(self):
        receipt = self.prepare()
        with self.sessions() as db: db.get(PlayerDeck, self.decks[1]['id']).version += 1; db.commit()
        with self.sessions() as db: mutex(db); cleanup_preparations(db); db.commit()
        self.assertEqual(self.total(), 0)
