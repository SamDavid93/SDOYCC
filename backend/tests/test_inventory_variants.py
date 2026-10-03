from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import func, select

from app.db.models import BoosterOpening, BoosterOpeningCard, CardVariant, InventoryItem, InventoryTransaction, UserBooster, VariantInventory
from app.modules.inventory import change_stock, migrate_inventory, migrate_user, variant
from test_economy import HubTestCase


class VariantTests(HubTestCase):
    def seed_history(self, quantity, rarities):
        with self.sessions() as db:
            db.add(InventoryItem(user_id=1, card_id=1, quantity=quantity))
            opening = BoosterOpening(user_id=1, booster_id=1)
            db.add(opening); db.flush()
            for rarity in rarities:
                db.add(BoosterOpeningCard(opening_id=opening.id, card_id=1, rarity=rarity))
            db.commit()

    def test_exact_history_reconstructs_counts_once(self):
        self.seed_history(3, ['Common', 'common', 'ultra_rare'])
        with self.sessions() as db:
            self.assertEqual(migrate_inventory(db), {'reconstructed': 3, 'legacy': 0})
            db.commit()
        with self.sessions() as db:
            self.assertEqual(migrate_inventory(db), {'reconstructed': 0, 'legacy': 0})
            counts = dict(db.execute(select(CardVariant.rarity, VariantInventory.quantity).join(VariantInventory)).all())
            self.assertEqual(counts, {'common': 2, 'ultra_rare': 1})
            self.assertEqual(db.scalar(select(func.count(InventoryTransaction.id))), 2)
            self.assertEqual(db.scalar(select(InventoryItem.quantity)), 3)

    def test_mismatched_history_stays_unknown_never_highest_rarity(self):
        for quantity, history in [(3, ['ultra_rare']), (1, ['common', 'ultra_rare'])]:
            with self.subTest(quantity=quantity):
                with self.sessions() as db:
                    db.query(InventoryTransaction).delete(); db.query(VariantInventory).delete(); db.query(CardVariant).delete()
                    db.query(InventoryItem).delete(); db.query(BoosterOpeningCard).delete(); db.query(BoosterOpening).delete(); db.commit()
                self.seed_history(quantity, history)
                with self.sessions() as db:
                    self.assertEqual(migrate_inventory(db), {'reconstructed': 0, 'legacy': quantity})
                    db.commit()
                result = self.client.get('/api/collection', headers=self.headers).json()['items'][0]
                self.assertEqual(result['card']['rarity'], 'unknown')
                self.assertEqual(result['card']['owned_variants'][0]['quantity'], quantity)
                self.assertEqual(self.client.get('/api/collection?rarity=ultra_rare', headers=self.headers).json()['total'], 0)
                self.assertEqual(self.client.get('/api/collection?rarity=unknown', headers=self.headers).json()['total'], 1)

    def test_opening_adds_only_real_variant_and_journal_once(self):
        self.seed_history(3, [])
        self.assertEqual(self.buy().status_code, 200)
        headers = {**self.headers, 'Idempotency-Key': 'variant-opening-1'}
        result = self.client.post('/api/boosters/1/open', headers=headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=headers).json(), result.json())
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(InventoryItem.quantity)), 4)
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.quantity))), 4)
            self.assertEqual(db.scalar(select(func.count(InventoryTransaction.id))), 2)
        collection = self.client.get('/api/collection', headers=self.headers).json()['items'][0]['card']
        self.assertEqual(set(collection['collected_rarities']), {'unknown', 'rare'})
        self.assertEqual(sorted(item['quantity'] for item in collection['owned_variants']), [1, 3])
        journal = self.client.get('/api/inventory/me/journal?page_size=1', headers=self.headers).json()
        self.assertEqual(journal['total'], 2)
        self.assertEqual(journal['items'][0]['reason'], 'booster_opening')
        self.assertEqual(journal['items'][0]['balance_after'], 1)
        self.assertEqual(self.client.get('/api/inventory/me/journal').status_code, 401)
        self.assertEqual(self.client.get('/api/admin/users/1/inventory-journal', headers=self.headers).status_code, 403)

    def test_reserved_stock_cannot_be_removed_and_reference_conflict(self):
        with self.sessions() as db:
            kind = variant(db, 1, 'Rare', 1)
            change_stock(db, 1, kind, 3, 'test_grant', 'grant-reference')
            change_stock(db, 1, kind, 3, 'test_grant', 'grant-reference')
            stock = db.scalar(select(VariantInventory)); stock.reserved = 2; db.flush()
            with self.assertRaises(HTTPException):
                change_stock(db, 1, kind, -2, 'test_correction', 'correction-ref')
            with self.assertRaises(HTTPException) as error:
                change_stock(db, 1, kind, 4, 'test_grant', 'grant-reference')
            self.assertEqual(error.exception.status_code, 409)
            change_stock(db, 1, kind, -1, 'test_correction', 'valid-correction')
            self.assertEqual(stock.quantity, 2)
            self.assertEqual(db.scalar(select(InventoryItem.quantity)), 2)
            self.assertEqual(db.scalar(select(func.count(InventoryTransaction.id))), 2)

    def test_drift_is_detected_instead_of_silently_reclassifying(self):
        self.seed_history(3, [])
        with self.sessions() as db:
            migrate_user(db, 1)
            db.scalar(select(InventoryItem)).quantity = 4
            db.flush()
            with self.assertRaises(ValueError):
                migrate_user(db, 1)

    def test_opening_failure_rolls_back_both_inventories_and_migration(self):
        self.seed_history(3, [])
        self.buy()
        with patch('app.api.finish', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/boosters/1/open', headers=self.headers)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(InventoryItem.quantity)), 3)
            self.assertEqual(db.scalar(select(UserBooster.quantity)), 1)
            self.assertEqual(db.scalar(select(func.count(VariantInventory.id))), 0)
            self.assertEqual(db.scalar(select(func.count(InventoryTransaction.id))), 0)
