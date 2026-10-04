from sqlalchemy import select
from app.db.models import (BoosterPack, BoosterPoolEntry, Card, InventoryItem, User,
    StructureDeckDefinition, StructureDeckItem, StructureDeckBonusSlot, StructureDeckBonusChoice)
from test_economy import HubTestCase


class BoosterProgressTests(HubTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            db.add_all([Card(id=i, external_id=str(i), name=f'Test {i}', card_set='Test', set_code='T',
                rarity='common', card_type='Monster', attribute='LIGHT', image_url='') for i in (2, 3)])
            db.flush()
            db.add(BoosterPoolEntry(booster_id=1, card_id=2, rarity='ultra_rare', weight=1))
            db.add(BoosterPoolEntry(booster_id=1, card_id=1, rarity='ultra_rare', weight=1))
            db.add(BoosterPoolEntry(booster_id=1, card_id=3, rarity='rare', weight=0))
            db.add(InventoryItem(user_id=1, card_id=1, quantity=5))
            db.add(InventoryItem(user_id=1, card_id=2, quantity=0))
            db.add(User(id=2, username='other', display_name='Other', credits=0))
            db.flush()
            db.add(InventoryItem(user_id=2, card_id=2, quantity=20))
            db.commit()

    def progress(self):
        listing = self.client.get('/api/boosters', headers=self.headers).json()[0]['collection_progress']
        detail = self.client.get('/api/boosters/1', headers=self.headers).json()['collection_progress']
        self.assertEqual(listing, detail)
        return detail

    def test_unique_owned_cards_exclude_duplicates_zero_stock_and_other_users(self):
        self.assertEqual(self.progress(), {'owned': 1, 'total': 2, 'percent': 50.0})
        with self.sessions() as db:
            db.scalar(select(InventoryItem).where(InventoryItem.user_id == 1, InventoryItem.card_id == 2)).quantity = 1
            db.commit()
        self.assertEqual(self.progress(), {'owned': 2, 'total': 2, 'percent': 100.0})

    def test_invalid_pool_and_empty_pool_have_zero_progress(self):
        with self.sessions() as db:
            for entry in db.scalars(select(BoosterPoolEntry)): entry.weight = 0
            db.commit()
        self.assertEqual(self.progress(), {'owned': 0, 'total': 0, 'percent': 0})
        with self.sessions() as db:
            db.scalar(select(BoosterPoolEntry).limit(1)).weight = -1
            db.commit()
        self.assertEqual(self.progress(), {'owned': 0, 'total': 0, 'percent': 0})

    def test_structure_deck_counts_bonus_choices_and_fixed_duplicates_once(self):
        with self.sessions() as db:
            db.get(BoosterPack, 1).product_type = 'structure_deck'
            db.add(StructureDeckDefinition(booster_id=1, source='fixture', content_hash='test', card_count=4,
                items=[StructureDeckItem(card_id=1, rarity='rare', quantity=3)],
                bonus_slots=[StructureDeckBonusSlot(name='Bonus', choices=[
                    StructureDeckBonusChoice(card_id=1, rarity='secret_rare'),
                    StructureDeckBonusChoice(card_id=2, rarity='secret_rare'),
                    StructureDeckBonusChoice(card_id=3, rarity='secret_rare')])]))
            db.commit()
        self.assertEqual(self.progress(), {'owned': 1, 'total': 3, 'percent': 33.3})

    def test_opening_refreshes_progress_and_retry_does_not_inflate_it(self):
        with self.sessions() as db:
            for item in db.scalars(select(InventoryItem).where(InventoryItem.user_id == 1)): item.quantity = 0
            for entry in db.scalars(select(BoosterPoolEntry)): entry.weight = 1 if entry.card_id == 2 else 0
            db.commit()
        self.assertEqual(self.progress()['owned'], 0)
        self.assertEqual(self.buy().status_code, 200)
        headers = {**self.headers, 'Idempotency-Key': 'progress-open'}
        first = self.client.post('/api/boosters/1/open', headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.progress(), {'owned': 1, 'total': 1, 'percent': 100.0})
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=headers).json(), first.json())
        self.assertEqual(self.progress()['owned'], 1)
