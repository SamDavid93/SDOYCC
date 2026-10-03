import math
from types import SimpleNamespace
from sqlalchemy import select, delete
from app.core.booster_rules import drawable_entries
from app.db.models import Card, BoosterPack, BoosterPoolEntry, UserBooster, User, InventoryItem, DiamondTransaction
from test_economy import HubTestCase


class BoosterLimitTests(HubTestCase):
    def configure(self, count, configured=5):
        with self.sessions() as db:
            db.execute(delete(BoosterPoolEntry))
            for number in range(1, count + 1):
                if db.get(Card, number) is None:
                    db.add(Card(id=number, external_id=str(number), name=f'Karte im Test {number}', card_set='Test', set_code='T', rarity='rare', card_type='Monster', attribute='LIGHT', image_url=''))
                    db.flush()
                db.add(BoosterPoolEntry(booster_id=1, card_id=number, rarity='rare', weight=1))
            db.get(BoosterPack, 1).cards_per_pack = configured
            stock = db.scalar(select(UserBooster))
            if stock is None:
                db.add(UserBooster(user_id=1, booster_id=1, quantity=1))
            else:
                stock.quantity = 1
            db.commit()

    def test_display_and_opening_agree_for_small_and_large_pools(self):
        for available, expected in [(0, 0), (1, 1), (3, 3), (5, 5), (6, 5)]:
            with self.subTest(available=available):
                self.configure(available)
                detail = self.client.get('/api/boosters/1', headers=self.headers).json()
                listing = self.client.get('/api/boosters', headers=self.headers).json()[0]
                self.assertEqual(detail['cards_per_pack'], expected)
                self.assertEqual(listing['cards_per_pack'], expected)
                self.assertEqual(listing['pool_size'], available)
                result = self.client.post('/api/boosters/1/open', headers=self.headers)
                self.assertEqual(result.status_code, 200 if expected else 409)
                if expected:
                    self.assertEqual(len(result.json()['cards']), expected)
                with self.sessions() as db:
                    self.assertEqual(db.scalar(select(UserBooster)).quantity, 0 if expected else 1)
                    self.assertEqual(db.get(User, 1).credits, 100)

    def test_rarity_variants_and_zero_weights_do_not_inflate_limit(self):
        self.configure(2)
        with self.sessions() as db:
            db.scalar(select(BoosterPoolEntry).where(BoosterPoolEntry.card_id == 2)).weight = 0
            db.add(BoosterPoolEntry(booster_id=1, card_id=1, rarity='ultra_rare', weight=1))
            db.commit()
        detail = self.client.get('/api/boosters/1', headers=self.headers).json()
        self.assertEqual(detail['cards_per_pack'], 1)
        self.assertEqual(detail['pool_size'], 1)
        self.assertEqual(len(detail['pool']), 2)
        self.assertEqual(self.client.get('/api/boosters', headers=self.headers).json()[0]['cards_per_pack'], 1)

    def test_invalid_pools_cannot_be_bought_or_opened(self):
        for weight in [-1, 0, math.inf]:
            with self.subTest(weight=weight):
                self.configure(1)
                with self.sessions() as db:
                    db.scalar(select(BoosterPoolEntry)).weight = weight
                    db.commit()
                self.assertEqual(self.buy().status_code, 409)
                self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 409)
                self.assertEqual(self.client.get('/api/boosters', headers=self.headers).json()[0]['cards_per_pack'], 0)
                with self.sessions() as db:
                    self.assertEqual(db.get(User, 1).credits, 100)
                    self.assertEqual(db.scalar(select(UserBooster)).quantity, 1)
                    self.assertIsNone(db.scalar(select(DiamondTransaction)))
        self.assertEqual(drawable_entries([SimpleNamespace(weight=math.nan, card_id=1)]), [])

    def test_configured_zero_is_rejected_and_existing_cards_aggregate(self):
        self.configure(1, configured=0)
        self.assertEqual(self.buy().status_code, 409)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 409)
        self.configure(1)
        with self.sessions() as db:
            db.add(InventoryItem(user_id=1, card_id=1, quantity=2))
            db.commit()
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(InventoryItem)).quantity, 3)
