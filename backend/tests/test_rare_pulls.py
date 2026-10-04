from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from sqlalchemy import select

from app.core.config import settings
from app.core.auth import create_session
from app.db.models import User, BoosterPoolEntry, BoosterOpening, RarePullAnnouncement, InventoryItem, UserBooster, Card
from test_economy import HubTestCase


class RarePullTests(HubTestCase):
    def setUp(self):
        super().setUp()
        self.old_key = settings.streamerbot_api_key
        settings.streamerbot_api_key = 'rare-pull-test-key-' * 3
        self.bridge = {'X-Streamerbot-Key': settings.streamerbot_api_key}
        self.channel = {'broadcaster_login': settings.twitch_broadcaster_login}
        with self.sessions() as db:
            user = db.get(User, 1)
            user.twitch_id = '12345'
            user.password_hash = 'registered-fixture'
            self.headers = {'Authorization': 'Bearer ' + create_session(db, user)}
            db.scalar(select(BoosterPoolEntry)).rarity = 'ultra_rare'
            db.commit()

    def tearDown(self):
        settings.streamerbot_api_key = self.old_key
        super().tearDown()

    def open_pack(self):
        self.assertEqual(self.buy().status_code, 200)
        result = self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'rare-open'})
        self.assertEqual(result.status_code, 200, result.text)
        return result

    def claim(self):
        return self.client.post('/api/integrations/streamerbot/announcements/claim', headers=self.bridge, json=self.channel)

    def ack(self, item, token=None):
        return self.client.post(f'/api/integrations/streamerbot/announcements/{item["id"]}/ack', headers=self.bridge,
            json={**self.channel, 'claim_token': token or item['claim_token']})

    def test_opening_enqueues_once_and_ack_is_idempotent(self):
        first = self.open_pack()
        self.assertEqual(self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'rare-open'}).json(), first.json())
        with self.sessions() as db:
            rows = db.scalars(select(RarePullAnnouncement)).all()
            self.assertEqual(len(rows), 1)
            self.assertIn('@jaden-demo', rows[0].message)
            self.assertIn('Ultraselten', rows[0].message)
            self.assertIn('aus Test gezogen', rows[0].message)
        item = self.claim().json()['announcement']
        self.assertIsNone(self.claim().json()['announcement'])
        self.assertEqual(self.ack(item).status_code, 200)
        self.assertEqual(self.ack(item).status_code, 200)
        self.assertIsNone(self.claim().json()['announcement'])

    def test_secret_bridge_and_correct_channel_required(self):
        path = '/api/integrations/streamerbot/announcements/claim'
        self.assertEqual(self.client.post(path, json=self.channel).status_code, 401)
        self.assertEqual(self.client.post(path, headers=self.headers, json=self.channel).status_code, 401)
        self.assertEqual(self.client.post(path, headers=self.bridge, json={'broadcaster_login':'other_channel'}).status_code, 403)

    def test_expired_lease_retries_but_old_token_cannot_ack(self):
        self.open_pack()
        first = self.claim().json()['announcement']
        self.assertEqual(self.ack(first, 'wrong-token-' * 4).status_code, 409)
        with self.sessions() as db:
            db.get(RarePullAnnouncement, first['id']).claimed_until = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        second = self.claim().json()['announcement']
        self.assertEqual(second['id'], first['id'])
        self.assertNotEqual(second['claim_token'], first['claim_token'])
        self.assertEqual(self.ack(first).status_code, 409)
        self.assertEqual(self.ack(second).status_code, 200)

    def test_old_announcements_expire_and_parallel_pollers_claim_once(self):
        self.open_pack()
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: self.claim(), range(4)))
        self.assertTrue(all(r.status_code == 200 for r in results))
        self.assertEqual(sum(r.json()['announcement'] is not None for r in results), 1)
        with self.sessions() as db:
            row = db.scalar(select(RarePullAnnouncement))
            row.claimed_until = datetime.utcnow() - timedelta(seconds=1)
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertIsNone(self.claim().json()['announcement'])

    def test_lower_rarity_is_not_announced(self):
        with self.sessions() as db:
            db.scalar(select(BoosterPoolEntry)).rarity = 'super_rare'
            db.commit()
        self.open_pack()
        self.assertIsNone(self.claim().json()['announcement'])

    def test_queue_failure_rolls_back_opening_and_inventory(self):
        self.assertEqual(self.buy().status_code, 200)
        with patch('app.modules.rare_pulls.enqueue_rare_pulls', side_effect=RuntimeError('fixture rollback')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/boosters/1/open', headers=self.headers)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(BoosterOpening)))
            self.assertIsNone(db.scalar(select(RarePullAnnouncement)))
            self.assertIsNone(db.scalar(select(InventoryItem)))
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 1)

    def test_repeated_high_card_is_grouped_and_message_is_one_bounded_line(self):
        with self.sessions() as db:
            db.add(Card(id=2, external_id='second', name='Second', card_set='Test', set_code='T', rarity='common', card_type='Monster', attribute='LIGHT', image_url=''))
            db.flush()
            db.add(BoosterPoolEntry(booster_id=1, card_id=2, rarity='common', weight=1))
            db.get(Card, 1).name = '龍\n' * 120
            db.commit()
        self.assertEqual(self.buy().status_code, 200)
        with patch('app.api.random.SystemRandom') as random:
            random.return_value.choices.side_effect = lambda entries, **kwargs: [next(e for e in entries if e.card_id == 1)] * 2
            self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 200)
        item = self.claim().json()['announcement']
        self.assertIn('2 ×', item['message'])
        self.assertNotIn('\n', item['message'])
        self.assertLessEqual(len(item['message'].encode('utf-8')), 450)
        self.assertIsNone(self.claim().json()['announcement'])
