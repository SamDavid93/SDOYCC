from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def migrate_local_schema() -> None:
    """Apply small additive migrations for the local development database."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    deck_columns = {column["name"] for column in inspector.get_columns("structure_deck_definitions")}
    if "notes" not in deck_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE structure_deck_definitions ADD COLUMN notes TEXT"))
    detail_columns = {column["name"] for column in inspector.get_columns("card_details")}
    if "description_en" not in detail_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE card_details ADD COLUMN description_en TEXT"))
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(512)"))
    if "twitch_id" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN twitch_id VARCHAR(40)"))
            connection.execute(text("CREATE UNIQUE INDEX uq_users_twitch_id ON users(twitch_id)"))
    opening_columns = {column["name"] for column in inspector.get_columns("booster_openings")}
    if "credits_spent" not in opening_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE booster_openings ADD COLUMN credits_spent INTEGER NOT NULL DEFAULT 0"))
    booster_columns = {column["name"] for column in inspector.get_columns("booster_packs")}
    if "set_id" not in booster_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE booster_packs ADD COLUMN set_id INTEGER REFERENCES card_sets(id)"))
    if "image_url" not in booster_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE booster_packs ADD COLUMN image_url TEXT"))
    if "product_type" not in booster_columns:
        from app.core.pricing import product_type_for_name, product_price
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE booster_packs ADD COLUMN product_type VARCHAR(30) NOT NULL DEFAULT 'booster'"))
            for pack_id, name in connection.execute(text("SELECT id, name FROM booster_packs")).all():
                kind = product_type_for_name(name)
                connection.execute(text("UPDATE booster_packs SET product_type = :kind, cost = :cost WHERE id = :id"),
                                   {"kind": kind, "cost": product_price(kind), "id": pack_id})
    # Establish a conservative lifetime baseline once per existing user/product.
    # Opening a pack or a restart must never reset its purchase allowance.
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO product_purchase_counters (user_id, booster_id, quantity)
            SELECT prior.user_id, prior.booster_id, SUM(prior.quantity)
            FROM (
                SELECT user_id, booster_id, quantity FROM user_boosters
                UNION ALL
                SELECT user_id, booster_id, COUNT(*) AS quantity FROM booster_openings GROUP BY user_id, booster_id
            ) AS prior
            WHERE NOT EXISTS (SELECT 1 FROM product_purchase_counters pc WHERE pc.user_id = prior.user_id AND pc.booster_id = prior.booster_id)
            GROUP BY prior.user_id, prior.booster_id"""))
    # Product rename only: preserve the pack ID, pool and every user's stock.
    with engine.begin() as connection:
        connection.execute(text("UPDATE booster_packs SET name = :new WHERE key = :key AND name = :old"),
                           {"new": "SDOYCC Origins", "key": "standard-booster", "old": "CardCluster Origins"})
    # Retain existing balances and establish a journal baseline, without replaying old openings.
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO diamond_transactions (user_id, amount, balance_after, reason, reference, created_at)
            SELECT id, credits, credits, 'opening_balance', 'opening-balance:' || CAST(id AS VARCHAR), CURRENT_TIMESTAMP
            FROM users WHERE NOT EXISTS (SELECT 1 FROM diamond_transactions WHERE user_id = users.id)"""))

    with engine.begin() as connection:
        for name, table, columns in [
            ('ix_printings_card_set', 'card_printings', 'card_id, set_id'),
            ('ix_printings_set_card', 'card_printings', 'set_id, card_id'),
            ('ix_openings_user', 'booster_openings', 'user_id'),
            ('ix_opening_cards_opening', 'booster_opening_cards', 'opening_id'),
            ('ix_pool_card_booster', 'booster_pool_entries', 'card_id, booster_id')]:
            connection.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})'))
