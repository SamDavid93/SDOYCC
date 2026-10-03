import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

from app.db.session import migrate_local_schema


class MigrationTests(unittest.TestCase):
    def test_lifetime_baseline_counts_owned_and_opened_once(self):
        from sqlalchemy.orm import Session
        from app.db.models import User, BoosterPack, UserBooster, BoosterOpening, ProductPurchaseCounter
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'counts.db'}")
            with patch('app.db.session.engine', engine):
                migrate_local_schema()
                with Session(engine) as db:
                    db.add_all([User(id=1, username='owner', display_name='Owner', credits=100),
                                BoosterPack(id=1, key='deck', name='Structure Deck: Test', product_type='structure_deck')])
                    db.flush()
                    db.add_all([UserBooster(user_id=1, booster_id=1, quantity=2), BoosterOpening(user_id=1, booster_id=1)])
                    db.commit()
                migrate_local_schema()
                with Session(engine) as db:
                    self.assertEqual(db.query(ProductPurchaseCounter).one().quantity, 3)
                    db.query(UserBooster).one().quantity = 1
                    db.add(BoosterOpening(user_id=1, booster_id=1))
                    db.commit()
                migrate_local_schema()
                with Session(engine) as db:
                    self.assertEqual(db.query(ProductPurchaseCounter).one().quantity, 3)
            engine.dispose()

    def test_brand_migration_preserves_booster_identity_and_stock(self):
        from sqlalchemy.orm import Session
        from app.db.models import User, BoosterPack, UserBooster
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'rename.db'}")
            with patch('app.db.session.engine', engine):
                migrate_local_schema()
                with Session(engine) as db:
                    user = User(username='owner', display_name='Owner', credits=100)
                    pack = BoosterPack(key='standard-booster', name='CardCluster Origins', cost=100)
                    db.add_all([user, pack]); db.flush()
                    user_id, pack_id = user.id, pack.id
                    db.add(UserBooster(user_id=user_id, booster_id=pack_id, quantity=7))
                    db.commit()
                migrate_local_schema()
                migrate_local_schema()
                with Session(engine) as db:
                    self.assertEqual(db.get(BoosterPack, pack_id).name, 'SDOYCC Origins')
                    self.assertEqual(db.get(User, user_id).credits, 100)
                    self.assertEqual(db.query(UserBooster).one().quantity, 7)
            engine.dispose()

    def test_existing_balance_survives_idempotent_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64), display_name VARCHAR(100), role VARCHAR(30), is_active BOOLEAN, credits INTEGER, created_at DATETIME)"))
                connection.execute(text("INSERT INTO users VALUES (1, 'legacy', 'Legacy', 'user', 1, 1450, CURRENT_TIMESTAMP)"))
            with patch("app.db.session.engine", engine):
                migrate_local_schema()
                migrate_local_schema()
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT credits FROM users WHERE id=1")).scalar(), 1450)
                self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM diamond_transactions")).scalar(), 1)
                self.assertEqual(connection.execute(text("SELECT amount FROM diamond_transactions")).scalar(), 1450)
                self.assertIn("twitch_id", {column["name"] for column in inspect(engine).get_columns("users")})
                self.assertIn("password_hash", {column["name"] for column in inspect(engine).get_columns("users")})
            engine.dispose()
