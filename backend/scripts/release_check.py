"""Read-only readiness report. Never prints tokens, password hashes or the database URL."""
import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from app.core.config import settings
from app.db.session import engine

def public_https(value):
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and bool(host) and host not in {"localhost", "127.0.0.1", "::1"} and not any(x in value.upper() for x in ["YOUR_", "REPLACE_", "EXAMPLE."])

def check(public=False):
    checks = {}
    if engine.dialect.name == "sqlite" and engine.url.database and engine.url.database != ":memory:":
        path = Path(engine.url.database).resolve()
        checks['database_exists'] = path.exists()
        if path.exists():
            db = sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)
            try:
                checks['database_integrity'] = db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                checks['foreign_keys'] = not db.execute('PRAGMA foreign_key_check').fetchall()
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                checks['complete_schema'] = {'special_cards','grant_batches','market_listings','market_card_index','inventory_reservations','trade_settlements','seasons','season_claims'} <= tables
                checks['active_owner'] = bool(db.execute("SELECT 1 FROM users WHERE role='super_admin' AND is_active=1 AND password_hash IS NOT NULL AND twitch_id IS NOT NULL LIMIT 1").fetchone())
                if {'variant_inventory','card_variants','inventory_items'} <= tables:
                    total = {(u,c):q for u,c,q in db.execute('SELECT user_id,card_id,quantity FROM inventory_items') if q}
                    variants = {(u,c):q for u,c,q in db.execute('SELECT v.user_id,c.card_id,SUM(v.quantity) FROM variant_inventory v JOIN card_variants c ON c.id=v.variant_id GROUP BY v.user_id,c.card_id') if q}
                    checks['inventory_totals'] = total == variants
            finally: db.close()
    else:
        checks['database_engine_supported'] = engine.dialect.name == 'postgresql'
    checks['bridge_key_configured'] = len(settings.streamerbot_api_key) >= 32 and 'REPLACE_' not in settings.streamerbot_api_key
    checks['reward_configured'] = bool(settings.twitch_reward_id) and 'REPLACE_' not in settings.twitch_reward_id
    if public:
        checks['production_mode'] = settings.app_env == 'production' and not settings.demo_enabled
        checks['public_frontend'] = public_https(settings.frontend_url)
        checks['public_cors'] = bool(settings.cors_origin_list) and all(public_https(x) and urlparse(x).path in ('','/') for x in settings.cors_origin_list)
        checks['frontend_origin_allowed'] = f'{urlparse(settings.frontend_url).scheme}://{urlparse(settings.frontend_url).netloc}' in settings.cors_origin_list
    return {'mode':'public' if public else 'local', 'ready':all(checks.values()), 'checks':checks,
        'external_acceptance':'Twitch-Chat, echte Einlösung und Zugriff von einem anderen Gerät separat prüfen.'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--public',action='store_true');args=parser.parse_args()
    report=check(args.public);print(json.dumps(report,ensure_ascii=True,indent=2));raise SystemExit(0 if report['ready'] else 1)
