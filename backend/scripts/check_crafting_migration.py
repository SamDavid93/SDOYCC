"""Apply crafting migration to an online SQLite backup, never to the live DB."""
import hashlib
import json
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import models, session as database
from app.modules.crafting import seed_crafting
from app.modules.inventory import migrate_inventory


def run():
    root = Path(__file__).resolve().parents[2]
    source = Path(database.engine.url.database).resolve()
    copy = root / 'artifacts/crafting-migration-dry-run.db'
    assert source != copy.resolve()
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(copy) as dest:
        src.backup(dest)
        names = {row[0] for row in dest.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        tables = ['inventory_items', 'variant_inventory', 'inventory_reservations', 'duel_stock_reservations', 'users', 'user_boosters']
        tables += [t for t in ['user_crafting_balances', 'crafting_transactions'] if t in names]
        columns = {t: [row[1] for row in dest.execute(f'PRAGMA table_info({t})')] for t in tables}

    def signature():
        with sqlite3.connect(copy.as_uri()+'?mode=ro', uri=True) as db:
            return {t: hashlib.sha256(json.dumps(db.execute(
                'SELECT '+','.join('"'+c+'"' for c in fields)+' FROM '+t+' ORDER BY 1').fetchall(), default=str).encode()).hexdigest()
                for t, fields in columns.items()}

    before = signature()
    database.engine = create_engine('sqlite:///'+str(copy).replace('\\','/'))
    database.migrate_local_schema()
    with Session(database.engine) as db:
        counts = migrate_inventory(db); seed_crafting(db); db.commit()
    with sqlite3.connect(copy) as db:
        printings = db.execute('SELECT COUNT(*) FROM card_printings').fetchone()[0]
        rules = db.execute('SELECT rarity_key,dismantle_value,craft_cost,crafting_enabled FROM crafting_rarity_rules ORDER BY rarity_key').fetchall()
        balances = db.execute('SELECT COUNT(*) FROM user_crafting_balances').fetchone()[0]
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('SELECT COUNT(*) FROM variant_inventory v JOIN card_variants c ON c.id=v.variant_id WHERE v.card_printing_id IS NULL OR v.card_printing_id<>c.printing_id').fetchone()[0] == 0
    with Session(database.engine) as db:
        migrate_inventory(db); seed_crafting(db); db.commit()
    with sqlite3.connect(copy) as db:
        assert db.execute('SELECT COUNT(*) FROM card_printings').fetchone()[0] == printings
    assert signature() == before, 'Existing owned data changed'
    result = {'owned_data_unchanged': True, 'migration_idempotent': True, 'printing_links_complete': True,
        'foreign_keys_valid': True, 'rules': rules, 'wallet_rows': balances, 'inventory_migration': counts}
    (root/'artifacts/crafting-migration-audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    database.engine.dispose()


if __name__ == '__main__': run()
