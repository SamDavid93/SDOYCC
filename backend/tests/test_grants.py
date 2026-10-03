from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy import func, select

from app.core.auth import create_session
from app.core.passwords import hash_password, verify_password
from app.db.models import (AdminAuditEvent, BoosterPack, DiamondTransaction, Grant, GrantItem, InventoryItem,
    InventoryTransaction, Notification, ProductPurchaseCounter, StructureDeckDefinition, StructureDeckItem,
    User, UserBooster, VariantInventory, Card)
from app.modules.inventory import migrate_inventory
from test_economy import HubTestCase


class GrantTests(HubTestCase):
    password = 'Grant-Test-Passwort-123!'

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        super().setUp()
        self.tokens = {}
        with self.sessions() as db:
            for account_id, role in [(2, 'super_admin'), (3, 'user'), (4, 'admin'), (5, 'support_admin')]:
                user = User(id=account_id, username=f'user{account_id}', display_name=f'User {account_id}', role=role,
                    twitch_id=str(account_id * 100), password_hash=self.password_hash, credits=700)
                db.add(user); db.flush()
                self.tokens[account_id] = {'Authorization': 'Bearer ' + create_session(db, user)}
            db.add_all([InventoryItem(user_id=3, card_id=1, quantity=4), UserBooster(user_id=3, booster_id=1, quantity=2)])
            db.flush(); migrate_inventory(db); db.commit()
        self.draft = {'user_id': 3, 'reason': 'Belohnung für das Community-Event', 'items': [
            {'kind': 'points', 'quantity': 100}, {'kind': 'card', 'card_id': 1, 'booster_id': 1, 'rarity': 'rare', 'quantity': 2},
            {'kind': 'pack', 'booster_id': 1, 'quantity': 1}]}

    def preview(self, draft=None, actor=2):
        return self.client.post('/api/admin/grants/preview', json=draft or self.draft, headers=self.tokens[actor])

    def body(self, draft=None, actor=2):
        draft = draft or self.draft
        result = self.preview(draft, actor)
        self.assertEqual(result.status_code, 200, result.text)
        return {**draft, 'password': self.password, 'confirmation': result.json()['username'], 'preview_hash': result.json()['preview_hash']}

    def grant(self, body, actor=2, key='grant-key-0001'):
        return self.client.post('/api/admin/grants', json=body, headers={**self.tokens[actor], 'Idempotency-Key': key})

    def test_mixed_grant_once_with_journals_receipt_and_notification(self):
        body = self.body()
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(Grant.id))), 0)
            self.assertEqual(db.get(User, 3).credits, 700)
        response = self.grant(body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.grant(body).json(), response.json())
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 800)
            self.assertEqual(db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id == 3)), 6)
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.quantity)).where(VariantInventory.user_id == 3)), 6)
            self.assertEqual(db.scalar(select(UserBooster.quantity).where(UserBooster.user_id == 3)), 3)
            self.assertEqual(db.scalar(select(func.count(GrantItem.id))), 3)
            self.assertEqual(db.scalar(select(func.count(Grant.id))), 1)
            self.assertEqual(db.scalar(select(func.count(Notification.id))), 1)
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id))), 1)
            self.assertEqual(db.scalar(select(DiamondTransaction.reason)), 'admin_grant')
        receipt = self.client.get('/api/admin/grants/' + str(response.json()['grant_id']), headers=self.tokens[2])
        self.assertEqual(receipt.json(), response.json())
        self.assertNotIn(self.password, receipt.text)

    def test_role_limits_target_and_password(self):
        for actor in (3, 5):
            self.assertEqual(self.preview(actor=actor).status_code, 403)
        body = self.body()
        self.assertEqual(self.grant({**body, 'password': 'wrong'}).status_code, 403)
        self.assertEqual(self.grant({**body, 'confirmation': 'other'}).status_code, 400)
        self.assertEqual(self.grant(body, key='short').status_code, 400)
        self.assertEqual(self.preview({**self.draft, 'user_id': 2}, actor=4).status_code, 403)
        self.assertEqual(self.preview({**self.draft, 'user_id': 1}).status_code, 400)
        self.assertEqual(self.preview({**self.draft, 'items': [{'kind': 'points', 'quantity': 10001}]}, actor=4).status_code, 400)
        self.assertEqual(self.preview({**self.draft, 'items': [{'kind': 'points', 'quantity': True}]}).status_code, 422)
        self.assertEqual(self.preview({**self.draft, 'items': [self.draft['items'][0]] * 2}).status_code, 400)
        self.assertEqual(self.preview({**self.draft, 'items': [{'kind': 'card', 'quantity': 1, 'card_id': 1, 'booster_id': 1, 'rarity': 'secret_rare'}]}).status_code, 400)
        self.assertEqual(self.preview({**self.draft, 'items': [{'kind': 'card', 'quantity': 1, 'card_id': 1, 'booster_id': 1, 'rarity': '   '}]}).status_code, 422)
        self.assertEqual(self.grant(body, actor=4).status_code, 409)  # Different actor limits invalidate the preview.
        self.assertEqual(self.grant(self.body(actor=4), actor=4).status_code, 200)

    def test_preview_change_and_reused_key_conflict(self):
        body = self.body()
        with self.sessions() as db:
            db.get(User, 3).credits += 100; db.commit()
        self.assertEqual(self.grant(body).status_code, 409)
        fresh = self.body()
        self.assertEqual(self.grant(fresh).status_code, 200)
        self.assertEqual(self.grant({**fresh, 'reason': 'Abweichende Begründung'}).status_code, 409)

    def test_parallel_duplicate_grants_deliver_once(self):
        body = self.body()
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: self.grant(body), range(2)))
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(responses[0].json(), responses[1].json())
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 800)
            self.assertEqual(db.scalar(select(func.count(Grant.id))), 1)

    def test_failure_during_delivery_rolls_back_every_position(self):
        body = self.body()
        with patch('app.modules.grants.change_stock', side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):
                self.grant(body)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 700)
            self.assertEqual(db.scalar(select(UserBooster.quantity).where(UserBooster.user_id == 3)), 2)
            for model in (Grant, GrantItem, Notification, AdminAuditEvent, DiamondTransaction):
                self.assertEqual(db.scalar(select(func.count()).select_from(model)), 0)

    def test_invalidated_pack_and_blocked_recipient_abort(self):
        body = self.body()
        with self.sessions() as db:
            db.get(BoosterPack, 1).active = False; db.commit()
        self.assertEqual(self.grant(body).status_code, 400)
        with self.sessions() as db:
            db.get(BoosterPack, 1).active = True; db.get(User, 3).is_active = False; db.commit()
        self.assertEqual(self.grant(body).status_code, 400)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 700)

    def test_structure_deck_gifts_share_lifetime_cap_with_purchase(self):
        with self.sessions() as db:
            db.add(BoosterPack(id=2, key='gift-deck', name='Structure Deck Test', product_type='structure_deck', cost=600))
            db.flush()
            db.add(StructureDeckDefinition(booster_id=2, source='fixture', content_hash='fixture', card_count=3))
            db.flush()
            db.add(StructureDeckItem(booster_id=2, card_id=1, rarity='rare', quantity=3)); db.commit()
        draft = {**self.draft, 'items': [{'kind': 'pack', 'booster_id': 2, 'quantity': 3}]}
        self.assertEqual(self.grant(self.body(draft)).status_code, 200)
        self.assertEqual(self.preview(draft).status_code, 400)
        buy = self.client.post('/api/boosters/2/purchase', headers=self.tokens[3], json={'quantity': 1})
        self.assertEqual(buy.status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 700)
            self.assertEqual(db.scalar(select(ProductPurchaseCounter.quantity).where(ProductPurchaseCounter.user_id == 3, ProductPurchaseCounter.booster_id == 2)), 3)

    def test_notifications_owned_only_and_read_idempotent(self):
        self.grant(self.body())
        result = self.client.get('/api/notifications', headers=self.tokens[3]).json()
        self.assertEqual((result['unread'], result['total']), (1, 1))
        notice = result['items'][0]['id']
        self.assertEqual(self.client.get('/api/notifications', headers=self.tokens[2]).json()['total'], 0)
        self.assertEqual(self.client.post(f'/api/notifications/{notice}/read', headers=self.tokens[2]).status_code, 404)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/notifications/{notice}/read', headers=self.tokens[3]).status_code, 200)
        self.assertEqual(self.client.get('/api/notifications', headers=self.tokens[3]).json()['unread'], 0)

    def test_grant_and_purchase_serialize_without_lost_balance(self):
        body = self.body({**self.draft, 'items': [{'kind': 'points', 'quantity': 100}]})
        with ThreadPoolExecutor(2) as pool:
            grant = pool.submit(self.grant, body)
            purchase = pool.submit(self.client.post, '/api/boosters/1/purchase', headers=self.tokens[3], json={'quantity': 1})
            grant_result, buy_result = grant.result(), purchase.result()
        self.assertEqual(buy_result.status_code, 200)
        self.assertIn(grant_result.status_code, (200, 409))
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 700 if grant_result.status_code == 200 else 600)

    def test_bound_variant_and_unregistered_recipient(self):
        with self.sessions() as db:
            db.get(User, 3).password_hash = None; db.commit()
        draft = {**self.draft, 'items': [{**self.draft['items'][1], 'bound': True}]}
        self.assertEqual(self.grant(self.body(draft)).status_code, 200)
        with self.sessions() as db:
            self.assertIsNone(db.get(User, 3).password_hash)
            self.assertEqual(db.scalar(select(VariantInventory.quantity).where(VariantInventory.user_id == 3, VariantInventory.bound.is_(True))), 2)

    def test_catalog_and_card_options_offer_real_sources(self):
        options = self.client.get('/api/admin/grants/card-options/1', headers=self.tokens[2])
        self.assertEqual(options.json(), [{'booster_id': 1, 'name': 'Test', 'rarity': 'rare'}])
        for kind in ('card', 'pack'):
            result = self.client.get(f'/api/admin/grants/catalog?kind={kind}&search=Test', headers=self.tokens[2])
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['total'], 1)

    def test_permission_is_rechecked_after_password_validation(self):
        body = self.body(actor=4)
        def verify_then_demote(password, stored):
            valid = verify_password(password, stored)
            with self.sessions() as db:
                db.get(User, 4).role = 'user'; db.commit()
            return valid
        with patch('app.modules.grants.verify_password', side_effect=verify_then_demote):
            self.assertEqual(self.grant(body, actor=4).status_code, 403)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).credits, 700)
            self.assertEqual(db.scalar(select(func.count(Grant.id))), 0)

    def test_missing_image_does_not_block_valid_card(self):
        with self.sessions() as db:
            db.get(Card, 1).image_url = ''; db.commit()
        draft = {**self.draft, 'items': [self.draft['items'][1]]}
        self.assertEqual(self.grant(self.body(draft)).status_code, 200)
