import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import BoosterPack, BoosterPoolEntry, Card, DiamondTransaction, InventoryItem, User, UserBooster
from app.db.session import Base, get_db
from app.main import app


class HubTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 15})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, autoflush=False, expire_on_commit=False)
        self.previous_demo = settings.enable_demo_auth
        settings.enable_demo_auth = True
        with self.sessions() as db:
            user = User(username="jaden-demo", display_name="Demo", credits=100)
            card = Card(external_id="test", name="Test", card_set="Test", set_code="T", rarity="rare", card_type="Monster", attribute="LIGHT", image_url="https://example.com/card.jpg")
            pack = BoosterPack(key="test", name="Test", cost=100, cards_per_pack=5)
            db.add_all([user, card, pack])
            db.flush()
            db.add(BoosterPoolEntry(booster_id=pack.id, card_id=card.id, rarity="rare", weight=1))
            db.commit()
        def database():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer demo-token"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        settings.enable_demo_auth = self.previous_demo
        self.engine.dispose()
        self.temp.cleanup()

    def buy(self, key="purchase-1"):
        return self.client.post("/api/boosters/1/purchase", headers={**self.headers, "Idempotency-Key": key}, json={"quantity": 1})


class EconomyTests(HubTestCase):
    def test_booster_detail_reports_actual_pool(self):
        response = self.client.get("/api/boosters/1", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["pool_size"], 1)
        self.assertEqual(response.json()["pool"][0]["weight"], 1)

    def test_purchase_and_open_charge_once_and_cap_small_pool(self):
        self.assertEqual(self.buy().json()["diamonds_remaining"], 0)
        result = self.client.post("/api/boosters/1/open", headers={**self.headers, "Idempotency-Key": "opening-1"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(result.json()["cards"]), 1)
        self.assertEqual(result.json()["diamonds_remaining"], 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(InventoryItem)).quantity, 1)
            self.assertEqual(len(db.scalars(select(DiamondTransaction)).all()), 1)
        replayed = self.client.post("/api/boosters/1/open", headers={**self.headers, "Idempotency-Key": "opening-1"})
        self.assertEqual(replayed.json(), result.json())
        self.assertEqual(self.client.get("/api/inventory/me", headers=self.headers).json()["total_quantity"], 1)

    def test_retry_purchase_does_not_charge_twice(self):
        first = self.buy()
        self.assertEqual(self.buy().json(), first.json())
        self.assertEqual(self.client.get("/api/boosters/me", headers=self.headers).json()[0]["quantity"], 1)

    def test_conflicting_idempotency_key(self):
        self.buy()
        response = self.client.post("/api/boosters/1/open", headers={**self.headers, "Idempotency-Key": "purchase-1"})
        self.assertEqual(response.status_code, 409)

    def test_concurrent_purchases_cannot_overspend(self):
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(self.buy, ["purchase-a", "purchase-b"]))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 400])
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 0)
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 1)

    def test_concurrent_openings_cannot_spend_same_pack(self):
        self.buy()
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda key: self.client.post("/api/boosters/1/open", headers={**self.headers, "Idempotency-Key": key}), ["opening-a", "opening-b"]))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 400])

    def test_insufficient_balance_leaves_inventory_unchanged(self):
        response = self.client.post("/api/boosters/1/purchase", headers=self.headers, json={"quantity": 2})
        self.assertEqual(response.status_code, 400)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 100)
            self.assertIsNone(db.scalar(select(UserBooster)))

    def test_production_rejects_demo(self):
        previous = settings.app_env
        settings.app_env = "production"
        try:
            self.assertEqual(self.client.get("/api/users/me", headers=self.headers).status_code, 401)
            self.assertEqual(self.client.get("/api/auth/demo").status_code, 404)
        finally:
            settings.app_env = previous


if __name__ == "__main__":
    unittest.main()
