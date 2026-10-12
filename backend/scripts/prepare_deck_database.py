"""Add deck/rule tables and a verified candidate; preserve all account/stock data.

SQLite preparation uses a consistent backup and a write transaction. It neither
enables duels nor grants cards. Run on a disposable copy before the real database.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.config import settings
from app.db.models import Card, DuelCardRule, DuelRuleProfile
from app.db.session import Base
from app.modules.duel_rules import import_profile
from app.modules.duel_region import official_limits
from import_duel_rules import load_source, DEFAULT_ROOT

PROTECTED = ('users', 'inventory_items', 'variant_inventory', 'inventory_transactions',
             'diamond_transactions', 'user_boosters', 'booster_openings', 'booster_opening_cards',
             'inventory_reservations', 'action_receipts')


def protected(db, tables):
    result = {}
    for name in PROTECTED:
        if name not in tables: continue
        rows = sorted(json.dumps(list(row), default=str, ensure_ascii=True) for row in db.execute(text('SELECT * FROM ' + name)))
        result[name] = {'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', default=None)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--official-list', type=Path, default=ROOT / 'artifacts/duel-reference/official-banlist.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/deck-database-report.json')
    args = parser.parse_args()
    engine = create_engine(args.database_url or settings.database_url)
    if engine.dialect.name != 'sqlite': raise ValueError('This backed-up preparation supports SQLite only.')
    names = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        mismatch = connection.execute(text('''SELECT COUNT(*) FROM inventory_items i LEFT JOIN
            (SELECT s.user_id,v.card_id,SUM(s.quantity) quantity FROM variant_inventory s JOIN card_variants v ON v.id=s.variant_id
             GROUP BY s.user_id,v.card_id) s ON s.user_id=i.user_id AND s.card_id=i.card_id
            WHERE i.quantity != COALESCE(s.quantity,0)''')).scalar()
    if mismatch: raise ValueError('Stock reconciliation required before preparation; no quantities were changed.')
    if not args.apply:
        print(json.dumps({'mode': 'preview', 'stock_mismatches': mismatch, 'deck_tables_present': 'player_decks' in names})); return
    database_file = Path(engine.url.database).resolve()
    backups = ROOT / 'artifacts/database-backups'; backups.mkdir(parents=True, exist_ok=True)
    backup = backups / (database_file.stem + '-decks-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.db')
    with sqlite3.connect(database_file.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    cards, limits, scripts, name, sources = load_source(DEFAULT_ROOT)
    raw = args.official_list.read_bytes()
    effective, limits, unresolved = official_limits(json.loads(raw), cards)
    if unresolved: raise ValueError('Unresolved official-list identities; import refused.')
    sources.update(regional_effective=effective, regional_list_sha256=hashlib.sha256(raw).hexdigest(),
                   approval='candidate-only; requires documented engine and regional review')
    tables = [table for table in Base.metadata.sorted_tables if table.name.startswith('duel_') or table.name in ('player_decks', 'deck_templates')]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        before = protected(db, names)
        profile, counts = import_profile(db, db.scalars(select(Card)).all(), cards, limits, scripts, 'TCG-EU ' + effective, sources)
        db.flush()
        owned = db.execute(text('''SELECT r.status,COUNT(DISTINCT i.card_id) FROM inventory_items i
            JOIN duel_card_rules r ON r.card_id=i.card_id AND r.profile_id=:profile WHERE i.quantity>0 GROUP BY r.status'''), {'profile': profile.id}).all()
        if protected(db, names) != before: raise ValueError('Protected account/stock data changed; transaction rolled back.')
        report = {'status': 'prepared', 'backup': str(backup), 'profile_id': profile.id, 'list_effective': effective,
                  'mapping': dict(counts), 'owned_card_mapping': dict(owned), 'stock_mismatches': mismatch,
                  'protected_data_unchanged': True, 'duels_enabled': False,
                  'engine_approved': profile.engine_approved, 'region_approved': profile.region_approved,
                  'protected_tables': before}
        db.commit()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({key: value for key, value in report.items() if key != 'protected_tables'}, indent=2))
    engine.dispose()


if __name__ == '__main__': main()
