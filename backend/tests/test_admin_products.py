import json
from unittest.mock import patch

from sqlalchemy import select

from app.core.auth import create_session
from app.core.passwords import hash_password
from app.db.models import AdminAuditEvent, BoosterPack, BoosterPoolEntry, User, UserBooster
from test_economy import HubTestCase


class AdminProductTests(HubTestCase):
    password = 'Product-owner-test-123!'

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        super().setUp()
        self.tokens = {}
        with self.sessions() as db:
            for index, role in enumerate(['super_admin', 'admin', 'support_admin', 'user'], 2):
                user = User(id=index, username=f'role-{index}', display_name=role,
                            role=role, twitch_id=str(index), password_hash=self.password_hash)
                db.add(user)
                db.flush()
                self.tokens[role] = {'Authorization': 'Bearer ' + create_session(db, user)}
            db.commit()

    def change(self, key='product-settings-1', role='super_admin', **values):
        return self.client.post('/api/admin/products/1', headers={**self.tokens[role], 'Idempotency-Key': key}, json={
            'price_override': 25, 'draw_count_override': 5,
            'expected_price_override': None, 'expected_draw_count_override': None,
            'password': self.password, 'reason': 'Produktregeln im Test anpassen', **values,
        })

    def test_only_owner_can_view_and_write(self):
        for role in ['admin', 'support_admin', 'user']:
            self.assertEqual(self.client.get('/api/admin/products', headers=self.tokens[role]).status_code, 403)
            self.assertEqual(self.change(role=role).status_code, 403)
        self.assertEqual(self.client.get('/api/admin/products').status_code, 401)
        self.assertEqual(self.change(password='wrong').status_code, 403)

    def test_price_and_exact_five_cards_apply_to_all_public_endpoints(self):
        response = self.change()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['product']['cards_per_pack'], 5)
        self.assertEqual(self.client.get('/api/boosters', headers=self.headers).json()[0]['cost'], 25)
        self.assertEqual(self.client.get('/api/boosters/1', headers=self.headers).json()['cards_per_pack'], 5)
        purchase = self.buy().json()
        self.assertEqual((purchase['cost'], purchase['total_cost'], purchase['credits_remaining']), (25, 25, 75))
        result = self.client.post('/api/boosters/1/open', headers=self.headers)
        self.assertEqual(len(result.json()['cards']), 5)
        with self.sessions() as db:
            event = db.scalar(select(AdminAuditEvent))
            details = json.loads(event.details_json)
            self.assertEqual(details['before']['cost'], 100)
            self.assertEqual(details['after']['cost'], 25)
            self.assertNotIn(self.password, event.details_json)

    def test_replay_and_stale_updates_cannot_overwrite_new_settings(self):
        first = self.change()
        self.assertEqual(self.change().json(), first.json())
        self.assertEqual(self.change(key='product-stale-2', price_override=70).status_code, 409)
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(AdminAuditEvent)).all()), 1)

    def test_reset_uses_defaults_and_free_price_is_supported(self):
        self.assertEqual(self.change(price_override=0, draw_count_override=1).status_code, 200)
        self.assertEqual(self.buy().json()['total_cost'], 0)
        result = self.change(key='product-reset-2', price_override=None, draw_count_override=None,
                             expected_price_override=0, expected_draw_count_override=1)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual((result.json()['product']['cost'], result.json()['product']['cards_per_pack']), (100, 9))

    def test_invalid_input_and_structure_draw_changes_are_rejected(self):
        for values in [{'price_override': -1}, {'draw_count_override': 0}, {'draw_count_override': 101},
                       {'price_override': True}, {'draw_count_override': 1.5}]:
            self.assertEqual(self.change(**values).status_code, 422)
        with self.sessions() as db:
            db.get(BoosterPack, 1).product_type = 'structure_deck'
            db.commit()
        self.assertEqual(self.change().status_code, 409)
        result = self.change(draw_count_override=None)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['product']['cost'], 25)

    def test_rare_guarantee_survives_custom_count_and_missing_pool_is_blocked(self):
        self.assertEqual(self.change(draw_count_override=12).status_code, 200)
        with self.sessions() as db:
            db.scalar(select(BoosterPoolEntry)).rarity = 'common'
            db.add(UserBooster(user_id=1, booster_id=1, quantity=1))
            db.commit()
        self.assertEqual(self.buy().status_code, 409)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 409)
        detail = self.client.get('/api/boosters/1', headers=self.headers).json()
        self.assertTrue(detail['rare_guaranteed'])
        self.assertEqual(detail['cards_per_pack'], 0)

    def test_additive_migration_preserves_existing_products_and_is_repeatable(self):
        from app.db.session import migrate_local_schema
        with self.engine.begin() as connection:
            connection.exec_driver_sql('ALTER TABLE booster_packs DROP COLUMN price_override')
            connection.exec_driver_sql('ALTER TABLE booster_packs DROP COLUMN draw_count_override')
        with patch('app.db.session.engine', self.engine):
            migrate_local_schema()
            migrate_local_schema()
        with self.sessions() as db:
            pack = db.get(BoosterPack, 1)
            self.assertEqual(pack.name, 'Test')
            self.assertIsNone(pack.price_override)
            self.assertIsNone(pack.draw_count_override)
