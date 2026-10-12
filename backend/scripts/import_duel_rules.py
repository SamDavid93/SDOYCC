"""Import a candidate rule snapshot from the pinned lab package; never enables duels.

Default is a read-only report. --apply explicitly writes only the three new
deck/rule tables. Use --database-url for isolated tests; no inventory mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'integrations/duel'))
from provision import DEFAULT_ROOT, verify
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import Card, DuelCardRule, DuelRuleProfile, PlayerDeck
from app.modules.duel_rules import import_profile, mapped_rules, parse_banlist


def load_source(root):
    root = Path(root).resolve()
    verify(root)
    cdb = root / 'cards/cards.cdb'
    banlist = root / 'lists/0TCG.lflist.conf'
    with sqlite3.connect(cdb.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        cards = {row['id']: dict(row) for row in db.execute('SELECT d.id,d.alias,d.type,d.ot,t.name FROM datas d JOIN texts t ON d.id=t.id')}
    name, limits = parse_banlist(banlist.read_text(encoding='utf8'))
    scripts = {int(path.stem[1:]) for path in (root / 'scripts').rglob('c*.lua') if path.stem[1:].isdigit()}
    lock = json.loads((ROOT / 'integrations/duel/sources.lock.json').read_text(encoding='utf8'))
    strings = json.loads((ROOT / 'integrations/duel/strings.lock.json').read_text(encoding='utf8'))
    if hashlib.sha256((root / 'config/strings.conf').read_bytes()).hexdigest() != strings['sha256']:
        raise ValueError('Unverified system string source')
    sources = {'package': lock, 'cdb_sha256': hashlib.sha256(cdb.read_bytes()).hexdigest(),
               'strings_sha256': strings['sha256'],
               'banlist_sha256': hashlib.sha256(banlist.read_bytes()).hexdigest(),
               'regional_reference': 'https://www.yugioh-card.com/eu/play/forbidden-and-limited-list/',
               'approval': 'candidate-only; regional release and full browser engine coverage pending'}
    return cards, limits, scripts, name, sources


def main():
    parser = argparse.ArgumentParser(description='Versionierte TCG-Vorprüfung vorbereiten; Duelle bleiben gesperrt.')
    parser.add_argument('--runtime', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--database-url', default=None)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--official-list', type=Path, help='Saved official EU list; exact-name/alias mapping required')
    args = parser.parse_args()
    engine_cards, limits, scripts, name, sources = load_source(args.runtime)
    if args.official_list:
        from app.modules.duel_region import official_limits
        raw = args.official_list.read_bytes()
        effective, limits, unresolved = official_limits(json.loads(raw), engine_cards)
        if unresolved: raise ValueError('Official EU list has unresolved or ambiguous card names; import refused')
        name = 'TCG-EU ' + effective
        sources['regional_list_sha256'] = hashlib.sha256(raw).hexdigest()
        sources['regional_effective'] = effective
        sources['approval'] = 'official EU limits mapped; engine/license/public release pending'
    engine = create_engine(args.database_url or settings.database_url)
    try:
        with Session(engine) as db:
            cards = db.scalars(select(Card)).all()
            from collections import Counter
            counts = Counter(row['status'] for row in mapped_rules(cards, engine_cards, limits, scripts))
            result = {'mode': 'applied' if args.apply else 'preview', 'list': name, 'mapping': dict(counts), 'duels_enabled': False}
        if args.apply:
            # No production startup/migrations, grants, account writes or engine launch.
            for table in (DuelRuleProfile.__table__, DuelCardRule.__table__, PlayerDeck.__table__): table.create(engine, checkfirst=True)
            with Session(engine) as db:
                profile, _ = import_profile(db, db.scalars(select(Card)).all(), engine_cards, limits, scripts, name, sources)
                db.commit(); result['profile_id'] = profile.id
        print(json.dumps(result, ensure_ascii=True, indent=2))
    finally: engine.dispose()


if __name__ == '__main__': main()
