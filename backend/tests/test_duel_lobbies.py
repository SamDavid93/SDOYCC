from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.auth import create_session
from app.db.models import AuthSession, DuelDeckConfirmation, DuelLobby, DuelLobbySeat, DuelRuleProfile, User, VariantInventory
from app.modules.inventory import change_stock, variant
from app.modules.duel_lobbies import cleanup_lobbies
from app.modules.workflow import mutex
from test_decks import DeckTestCase


class LobbyTests(DeckTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            host, guest = db.get(User, 1), db.get(User, 2)
            for user in (host, guest): user.twitch_id = str(100000 + user.id); user.password_hash = 'isolated-fixture'
            self.headers = {'Authorization': 'Bearer ' + create_session(db, host)}
            outsider = User(username='third', display_name='Dritter Spieler', twitch_id='100003', password_hash='isolated-fixture', credits=0)
            db.add(outsider); db.flush()
            self.third = {'Authorization': 'Bearer ' + create_session(db, outsider)}
            db.commit()
        self.host_deck = self.client.post('/api/decks', json={**self.body, 'name': 'Geheime Strategie'}, headers=self.headers).json()
        self.guest_deck = self.client.post('/api/decks', json={**self.body, 'name': 'Gaststrategie'}, headers=self.other_headers).json()

    def post(self, path, body, headers=None, key=None):
        return self.client.post('/api/duel-zone' + path, json=body, headers={**(headers or self.headers), 'Idempotency-Key': key or str(uuid4())})

    def create_room(self):
        response = self.post('/lobbies', {'deck_id': self.host_deck['id']})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def join(self, room, headers=None):
        return self.post('/join', {'code': room['code']}, headers or self.other_headers)

    def mine(self, headers=None):
        return self.client.get('/api/duel-zone/me', headers=headers or self.headers).json()

    def clean(self):
        with self.sessions() as db: mutex(db); cleanup_lobbies(db); db.commit()

    def test_private_membership_approval_and_deck_names(self):
        room = self.create_room()
        guest = self.join(room)
        self.assertEqual(guest.status_code, 200, guest.text)
        self.assertNotIn('Geheime Strategie', guest.text)
        self.assertNotIn('entries', guest.text)
        self.assertIsNone(guest.json()['own_deck'])
        self.assertIsNone(self.mine(self.third))
        room = self.mine()
        forbidden = self.post(f'/lobbies/{room["id"]}/guest', {'version': room['version'], 'accept': True}, self.other_headers)
        self.assertEqual(forbidden.status_code, 403)
        choice = {'version': room['version'], 'deck_id': self.guest_deck['id']}
        self.assertEqual(self.post(f'/lobbies/{room["id"]}/deck', choice, self.other_headers).status_code, 409)
        approved = self.post(f'/lobbies/{room["id"]}/guest', {'version': room['version'], 'accept': True})
        self.assertEqual(approved.status_code, 200)
        selected = self.post(f'/lobbies/{room["id"]}/deck', {**choice, 'version': approved.json()['version']}, self.other_headers)
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual(selected.json()['own_deck']['name'], 'Gaststrategie')
        self.assertNotIn('Gaststrategie', json.dumps(self.mine()))

    def test_create_retry_and_one_active_seat(self):
        payload = {'deck_id': self.host_deck['id']}
        first = self.post('/lobbies', payload, key='lobby-create-once')
        self.assertEqual(self.post('/lobbies', payload, key='lobby-create-once').json(), first.json())
        self.assertEqual(self.post('/lobbies', payload).status_code, 409)
        self.assertEqual(self.post('/join', {'code': first.json()['code']}).status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(DuelLobby.id))), 1)
            self.assertEqual(db.scalar(select(func.count(DuelLobbySeat.user_id))), 1)

    def test_two_guests_race_for_one_seat(self):
        room = self.create_room()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda headers: self.join(room, headers), [self.other_headers, self.third]))
        self.assertEqual(sorted(r.status_code for r in results), [200, 404])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(DuelLobbySeat.user_id))), 2)

    def test_outsider_and_wrong_code_cannot_mutate_room(self):
        room = self.create_room()
        for path, body in [('guest', {'accept': False}), ('deck', {'deck_id': self.host_deck['id']}), ('ready', {}), ('leave', {})]:
            response = self.post(f'/lobbies/{room["id"]}/{path}', {'version': room['version'], **body}, self.third)
            self.assertEqual(response.status_code, 404, response.text)
        for code in ('SDO-AAAA-AAAA', '........'):
            self.assertEqual(self.post('/join', {'code': code}, self.third).status_code, 404)
        self.assertEqual(self.client.get('/api/duel-zone/me').status_code, 401)

    def test_stale_version_and_guest_removal(self):
        room = self.create_room(); self.join(room)
        path = f'/lobbies/{room["id"]}/guest'
        self.assertEqual(self.post(path, {'version': room['version'], 'accept': False}).status_code, 409)
        current = self.mine()
        self.assertEqual(self.post(path, {'version': current['version'], 'accept': False}).status_code, 200)
        self.assertIsNone(self.mine(self.other_headers))
        self.assertEqual(self.mine()['state'], 'open')

    def test_leave_close_and_expiry_release_membership_once(self):
        room = self.create_room(); self.join(room)
        current = self.mine()
        left = self.post(f'/lobbies/{room["id"]}/leave', {'version': current['version']}, self.other_headers)
        self.assertEqual(left.status_code, 200)
        self.assertIsNone(self.mine(self.other_headers))
        with self.sessions() as db:
            db.get(DuelLobby, room['id']).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        self.assertEqual(self.mine()['state'], 'expired')
        self.clean(); self.clean()
        self.assertIsNone(self.mine())
        next_room = self.create_room()
        self.assertNotEqual(next_room['id'], room['id'])
        self.join(next_room)
        self.assertEqual(self.post(f'/lobbies/{next_room["id"]}/leave', {'version': self.mine()['version']}).status_code, 200)
        self.assertIsNone(self.mine(self.other_headers))

    def test_revoked_host_session_and_blocked_guest_cleanup(self):
        room = self.create_room(); self.join(room)
        with self.sessions() as db:
            db.get(User, 2).is_active = False; db.commit()
        self.clean()
        self.assertEqual(len(self.mine()['members']), 1)
        with self.sessions() as db:
            db.execute(delete(AuthSession).where(AuthSession.user_id == 1)); db.commit()
        self.clean()
        with self.sessions() as db:
            self.assertEqual(db.get(DuelLobby, room['id']).state, 'expired')
            self.assertEqual(db.scalar(select(func.count(DuelLobbySeat.user_id))), 0)

    def test_deck_version_changes_detected_and_selected_deck_not_deletable(self):
        room = self.create_room()
        response = self.client.put('/api/decks/' + self.host_deck['id'], json={**self.body, 'name': 'Edited', 'version': 1}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(self.mine()['own_deck_changed'])
        self.assertEqual(self.client.post('/api/decks/' + self.host_deck['id'] + '/delete', json={'version': 2}, headers=self.headers).status_code, 409)
        selected = self.post(f'/lobbies/{room["id"]}/deck', {'version': room['version'], 'deck_id': self.host_deck['id']})
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertFalse(selected.json()['own_deck_changed'])

    def test_start_always_blocked_without_reservations_or_inventory_changes(self):
        room = self.create_room()
        with self.sessions() as db:
            profile = db.get(DuelRuleProfile, self.profile)
            profile.engine_approved = True; profile.region_approved = True; db.commit()
        response = self.post(f'/lobbies/{room["id"]}/ready', {'version': room['version']})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.mine()['can_start'])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.reserved))), 0)
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.quantity))), 69)
            self.assertEqual(db.get(User, 1).credits, 100)

    def test_non_registered_account_rejected(self):
        with self.sessions() as db:
            db.get(User, 1).password_hash = None; db.commit()
        response = self.post('/lobbies', {'deck_id': self.host_deck['id']})
        self.assertEqual(response.status_code, 403)

    def selectable_room(self):
        with self.sessions() as db:
            for cid in range(1, 24):
                change_stock(db, 2, variant(db, cid, 'rare'), 3, 'test', f'confirmation:{cid}')
            db.commit()
        room = self.create_room(); self.join(room)
        room = self.mine()
        room = self.post(f'/lobbies/{room["id"]}/guest', {'version': room['version'], 'accept': True}).json()
        room = self.post(f'/lobbies/{room["id"]}/deck', {'version': room['version'], 'deck_id': self.guest_deck['id']}, self.other_headers).json()
        return room

    def confirm(self, room, headers=None, value=True):
        return self.post(f'/lobbies/{room["id"]}/confirm-deck', {'version': room['version'], 'confirmed': value}, headers)

    def test_two_deck_confirmations_are_private_and_do_not_start_or_reserve(self):
        room = self.selectable_room()
        room = self.confirm(room).json()
        self.assertTrue(room['members'][0]['deck_confirmed'])
        self.assertFalse(room['both_decks_confirmed'])
        response = self.confirm(room, self.other_headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('Geheime Strategie', response.text)
        self.assertNotIn('context_hash', response.text)
        self.assertTrue(response.json()['both_decks_confirmed'])
        self.assertFalse(response.json()['can_start'])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.reserved))), 0)
        room = self.confirm(response.json(), self.other_headers, False).json()
        self.assertFalse(any(member['deck_confirmed'] for member in room['members']))

    def test_deck_edit_and_reselection_invalidate_both_confirmations(self):
        room = self.selectable_room()
        room = self.confirm(room).json(); room = self.confirm(room, self.other_headers).json()
        edited = self.client.put('/api/decks/' + self.host_deck['id'], json={**self.body, 'name': 'Neue Fassung', 'version': 1}, headers=self.headers)
        self.assertEqual(edited.status_code, 200, edited.text)
        current = self.mine()
        self.assertFalse(any(m['deck_confirmed'] for m in current['members']))
        self.assertFalse(current['can_confirm_deck'])
        self.assertEqual(self.confirm(current).status_code, 409)
        selected = self.post(f'/lobbies/{room["id"]}/deck', {'version': current['version'], 'deck_id': self.host_deck['id']}).json()
        self.assertTrue(selected['can_confirm_deck'])
        with self.sessions() as db: self.assertEqual(db.scalar(select(func.count(DuelDeckConfirmation.user_id))), 0)

    def test_confirm_requires_current_owner_session_and_both_selections(self):
        room = self.create_room()
        self.assertEqual(self.confirm(room).status_code, 409)
        self.assertEqual(self.confirm(room, self.third).status_code, 404)
        self.post(f'/lobbies/{room["id"]}/leave', {'version': room['version']})
        room = self.selectable_room()
        with self.sessions() as db:
            other_session = {'Authorization': 'Bearer ' + create_session(db, db.get(User, 1))}; db.commit()
        self.assertEqual(self.confirm(room, other_session).status_code, 403)
        self.assertEqual(self.confirm(room).status_code, 200)

    def test_missing_stock_prevents_confirmation_without_revealing_card_names(self):
        room = self.selectable_room()
        with self.sessions() as db:
            change_stock(db, 2, variant(db, 1, 'rare'), -3, 'test', 'remove-before-confirm'); db.commit()
        response = self.confirm(room, self.other_headers)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('Prüfkarte', response.text)
        self.assertFalse(self.mine()['both_decks_confirmed'])

    def test_confirmation_expiry_and_guest_rejoin_do_not_reuse_consent(self):
        room = self.selectable_room(); room = self.confirm(room).json()
        room = self.confirm(room, self.other_headers).json()
        with self.sessions() as db:
            db.get(DuelDeckConfirmation, 1).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        self.assertFalse(self.mine()['members'][0]['deck_confirmed'])
        self.post(f'/lobbies/{room["id"]}/leave', {'version': room['version']}, self.other_headers)
        self.join(self.mine())
        self.assertFalse(any(m['deck_confirmed'] for m in self.mine()['members']))
        with self.sessions() as db: self.assertEqual(db.scalar(select(func.count(DuelDeckConfirmation.user_id))), 0)

    def test_simultaneous_confirmation_requires_refresh_then_keeps_both(self):
        room = self.selectable_room()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda headers: self.confirm(room, headers), [self.headers, self.other_headers]))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        retry_headers = self.headers if results[0].status_code == 409 else self.other_headers
        room = self.confirm(self.mine(), retry_headers).json()
        self.assertTrue(room['both_decks_confirmed'])
