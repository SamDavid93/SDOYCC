from unittest.mock import patch

from sqlalchemy import select

from app.db.models import BoosterPack, BoosterPoolEntry, Card, CardPrinting, CardSet, UserBooster
from scripts.sync_catalog import sync_catalog
from test_economy import HubTestCase


class Provider:
    name = "ygoprodeck"

    def fetch_sets(self):
        return [{"set_name": "Set Alpha", "set_code": "ALP", "num_of_cards": 1}]

    def fetch_cards(self):
        return [{"id": 123, "name": "Alpha card", "type": "Monster", "card_sets": [
            {"set_name": "Set Alpha", "set_code": "ALP-001", "set_rarity": "Ultra Rare"}]}]

    def image_url(self, external_id):
        return f"https://example.com/{external_id}.jpg"


class CatalogTests(HubTestCase):
    def test_card_boosters_use_actual_active_pool_not_set_printings(self):
        sync_catalog(Provider(), self.sessions)
        with self.sessions() as db:
            card = db.scalar(select(Card).where(Card.external_id == "123"))
            card_id = card.id
            card_set = db.scalar(select(CardSet))
            pack = db.scalar(select(BoosterPack).where(BoosterPack.set_id == card_set.id))
            pack.image_url = "https://example.com/alpha-cover.jpg"
            pack_id = pack.id
            # Same set but no matching pool: must not appear as a source.
            empty = BoosterPack(key="empty", name="Empty", set_id=card_set.id, cost=100)
            inactive = BoosterPack(key="inactive", name="Inactive", active=False, cost=100)
            db.add_all([empty, inactive])
            db.flush()
            db.add(BoosterPoolEntry(booster_id=inactive.id, card_id=card_id, rarity="rare", weight=1))
            db.commit()
        response = self.client.get(f"/api/cards/{card_id}/boosters", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [pack_id])
        self.assertEqual(response.json()[0]["image_url"], "https://example.com/alpha-cover.jpg")
        self.assertEqual(response.json()[0]["set_code"], "ALP")
        pool = self.client.get(f"/api/boosters/{pack_id}", headers=self.headers).json()["pool"]
        self.assertEqual(pool[0]["card"]["set"], "Set Alpha")
        self.assertEqual(pool[0]["card"]["set_code"], "ALP-001")
        self.assertEqual(self.client.get(f"/api/cards/{card_id}/printings").json()[0]["set_id"], card_set.id)
        self.assertEqual(self.client.get("/api/cards/99999/boosters", headers=self.headers).status_code, 404)

    def test_uniform_price_overrides_old_product_price_in_display_and_charge(self):
        with self.sessions() as db:
            db.get(BoosterPack, 1).cost = 500
            db.commit()
        self.assertEqual(self.client.get("/api/boosters", headers=self.headers).json()[0]["cost"], 100)
        self.assertEqual(self.client.get("/api/boosters/1", headers=self.headers).json()["cost"], 100)
        response = self.buy()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["credits_remaining"], 0)

    def test_repeated_import_preserves_set_pack_printing_and_stock(self):
        provider = Provider()
        sync_catalog(provider, self.sessions)
        with self.sessions() as db:
            card_set = db.scalar(select(CardSet))
            pack = db.scalar(select(BoosterPack).where(BoosterPack.set_id == card_set.id))
            printing = db.scalar(select(CardPrinting))
            original_ids = (card_set.id, pack.id, printing.id)
            db.add(UserBooster(user_id=1, booster_id=pack.id, quantity=3))
            db.commit()
        sync_catalog(provider, self.sessions)
        with self.sessions() as db:
            card_set = db.scalar(select(CardSet))
            pack = db.scalar(select(BoosterPack).where(BoosterPack.set_id == card_set.id))
            printing = db.scalar(select(CardPrinting))
            self.assertEqual((card_set.id, pack.id, printing.id), original_ids)
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 3)
            self.assertEqual(db.scalar(select(BoosterPoolEntry).where(BoosterPoolEntry.booster_id == pack.id)).rarity, "ultra_rare")

    def test_failed_import_rolls_back_entire_catalog(self):
        provider = Provider()
        with patch.object(provider, "fetch_cards", return_value=provider.fetch_cards() + [{"name": "broken"}]):
            with self.assertRaises(KeyError):
                sync_catalog(provider, self.sessions)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(CardSet)))
            self.assertEqual(len(db.scalars(select(Card)).all()), 1)

    def test_card_search_and_pagination(self):
        sync_catalog(Provider(), self.sessions)
        response = self.client.get("/api/cards", params={"search": "ALP-001", "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["name"], "Alpha card")
        self.assertEqual(self.client.get("/api/cards", params={"page": 2, "page_size": 1}).json()["total"], 2)
