"""Versioned deck-construction data; not a replacement for the EDOPro rule core.

Bit identifiers follow the pinned upstream ocgapi_constants.h (see D1 docs).
No guessed mappings: trusted provider + exact passcode + matching original name.
"""
from collections import Counter, defaultdict
import hashlib
import json
import re
import unicodedata

from sqlalchemy import select, func

from app.db.models import Card, CardVariant, DuelCardRule, DuelRuleProfile, InventoryItem, VariantInventory

EXTRA_TYPES = 0x40 | 0x2000 | 0x800000 | 0x4000000
TOKEN = 0x4000
STATUS_TEXT = {
    "mapped": "Kartenzuordnung geprüft",
    "unknown_provider": "Für diese Kartenquelle fehlt eine geprüfte Zuordnung.",
    "unknown_passcode": "Passcode nicht in den Engine-Daten gefunden.",
    "name_mismatch": "Kartenname und Engine-Passcode passen nicht zusammen.",
    "alias_invalid": "Regelidentität dieser Karte ist noch nicht eindeutig.",
    "unsupported_type": "Dieser Kartentyp gehört nicht in ein TCG-Deck.",
    "not_tcg": "Diese Karte ist im Datenpaket nicht als TCG-Karte freigegeben.",
    "missing": "Kartenzuordnung für diesen Regelstand fehlt.",
    "stale": "Katalogdaten haben sich geändert; neue Zuordnung erforderlich.",
}


def canonical(value):
    return unicodedata.normalize("NFKC", value).replace("’", "'").strip().casefold()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def fingerprint(card):
    return digest([card.external_provider, card.external_id, canonical(card.name)])


def parse_banlist(text):
    """One ordinary list only; reject whitelist directives or unknown syntax."""
    name, limits = None, {}
    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('!'):
            if name is not None: raise ValueError('Mehrere Bannlisten in einer Datei.')
            name = line[1:].strip()
            if not name: raise ValueError('Bannlistenname fehlt.')
            continue
        match = re.fullmatch(r'(\d{1,10})\s+([0-3])(?:\s+--.*)?', line)
        if not match or name is None:
            raise ValueError(f'Unbekanntes Bannlistenformat in Zeile {number}.')
        code, limit = map(int, match.groups())
        if code <= 0 or code > 2147483647 or (code in limits and limits[code] != limit):
            raise ValueError('Ungültiger oder widersprüchlicher Bannlisteneintrag.')
        limits[code] = limit
    if not name: raise ValueError('Keine benannte Bannliste gefunden.')
    return name, limits


def resolve_identity(code, engine_cards):
    visited = set()
    while code in engine_cards and code not in visited:
        visited.add(code)
        alias = engine_cards[code]['alias']
        if not alias: return code
        code = alias
    return None


def mapped_rules(cards, engine_cards, limits, script_codes):
    identities = {code: resolve_identity(code, engine_cards) for code in engine_cards}
    family_limits = {}
    for code, limit in limits.items():
        identity = identities.get(code)
        if identity: family_limits[identity] = min(family_limits.get(identity, 3), limit)
    rows = []
    for card in cards:
        row = dict(card_id=card.id, catalog_fingerprint=fingerprint(card), passcode=None, identity=None,
                   type_bits=0, section=None, copy_limit=3, status='unknown_provider', script_available=False)
        # local-demo is intentional and still must match both code and original name.
        if card.external_provider not in ('ygoprodeck', 'local-demo'):
            rows.append(row); continue
        code = int(card.external_id) if re.fullmatch(r'[0-9]{1,10}', card.external_id) else 0
        source = engine_cards.get(code)
        if not source:
            row['status'] = 'unknown_passcode'; rows.append(row); continue
        if canonical(card.name) != canonical(source['name']):
            row['status'] = 'name_mismatch'; rows.append(row); continue
        identity = identities[code]
        bits = source['type']
        section = 'extra' if bits & EXTRA_TYPES else 'main'
        status = 'mapped'
        if identity is None: status = 'alias_invalid'
        elif bits & TOKEN or not bits & 7 or bits & 0x8000: status = 'unsupported_type'
        elif source['ot'] not in (2, 3): status = 'not_tcg'  # exclude anime/custom/pre-release flags
        row.update(passcode=code, identity=identity, type_bits=bits, section=section,
                   copy_limit=family_limits.get(identity, 3), status=status,
                   script_available=code in script_codes or (identity in script_codes) or bool(bits & 0x10 and not bits & (0x20 | 0x1000000)))
        rows.append(row)
    return rows


def import_profile(db, cards, engine_cards, limits, script_codes, list_name, sources):
    rows = mapped_rules(cards, engine_cards, limits, script_codes)
    rows.sort(key=lambda row: row['card_id'])
    key = digest({'schema': 1, 'region': 'TCG-EU', 'list': list_name, 'sources': sources, 'rules': rows})
    existing = db.get(DuelRuleProfile, key)
    if existing: return existing, Counter(row['status'] for row in rows)
    profile = DuelRuleProfile(id=key, name=f'TCG-Vorprüfung · {list_name}', list_name=list_name,
                             sources_json=json.dumps(sources, sort_keys=True), engine_approved=False, region_approved=False)
    db.add(profile); db.flush()
    db.add_all(DuelCardRule(profile_id=key, **row) for row in rows)
    db.flush()
    return profile, Counter(row['status'] for row in rows)


def profile_payload(profile):
    if profile is None: return None
    return {'id': profile.id, 'name': profile.name, 'region': profile.region, 'list_name': profile.list_name,
            'engine_approved': profile.engine_approved, 'region_approved': profile.region_approved,
            'created_at': profile.created_at.isoformat() + 'Z'}


def stock_query(user_id):
    return select(CardVariant.card_id.label('card_id'), func.sum(VariantInventory.quantity).label('quantity'),
                  func.sum(VariantInventory.quantity - VariantInventory.reserved).label('available')).join(
        VariantInventory, VariantInventory.variant_id == CardVariant.id).where(
        VariantInventory.user_id == user_id).group_by(CardVariant.card_id).subquery()


def stock_for(db, user_id, card_ids):
    if not card_ids: return {}
    variants = stock_query(user_id)
    rows = db.execute(select(InventoryItem.card_id, InventoryItem.quantity, variants.c.quantity, variants.c.available).outerjoin(
        variants, variants.c.card_id == InventoryItem.card_id).where(InventoryItem.user_id == user_id, InventoryItem.card_id.in_(card_ids)))
    return {card_id: {'owned': owned, 'available': int(available or 0) if owned == total else 0,
                     'stock_verified': owned == total or (owned == 0 and total is None)} for card_id, owned, total, available in rows}


def rule_payload(card, rule):
    status = rule.status if rule else 'missing'
    if rule and rule.catalog_fingerprint != fingerprint(card): status = 'stale'
    return {'status': status, 'message': STATUS_TEXT[status],
            'passcode': rule.passcode if rule and status not in ('stale', 'missing') else None,
            'identity': rule.identity if rule else None, 'section': rule.section if rule else None,
            'copy_limit': rule.copy_limit if rule else None, 'type_bits': rule.type_bits if rule else 0,
            'script_available': bool(rule and rule.script_available)}


def validate_deck(db, user_id, entries, profile):
    from app.api import translated_text
    ids = {item['card_id'] for item in entries}
    cards = {card.id: card for card in db.scalars(select(Card).where(Card.id.in_(ids)))} if ids else {}
    rules = {row.card_id: row for row in db.scalars(select(DuelCardRule).where(DuelCardRule.profile_id == profile.id,
             DuelCardRule.card_id.in_(ids)))} if profile and ids else {}
    stock = stock_for(db, user_id, ids)
    totals, counts, families = Counter(), Counter(), defaultdict(list)
    issues = []
    def issue(kind, code, message, card_id=None):
        issues.append({'kind': kind, 'code': code, 'message': message, 'card_id': card_id})
    if not profile: issue('rules', 'profile_missing', 'Noch kein versionierter Regelstand gewählt.')
    for entry in entries:
        totals[entry['section']] += entry['quantity']; counts[entry['card_id']] += entry['quantity']
    for section, minimum, maximum, title in [('main', 40, 60, 'Hauptdeck'), ('extra', 0, 15, 'Extra-Deck'), ('side', 0, 15, 'Side-Deck')]:
        if not minimum <= totals[section] <= maximum:
            issue('rules', 'size_' + section, f'{title}: {totals[section]} Karten, erlaubt {minimum}–{maximum}.')
    for card_id, quantity in counts.items():
        card = cards.get(card_id)
        if card is None:
            issue('rules', 'unknown_card', 'Diese Katalogkarte existiert nicht mehr.', card_id); continue
        name = (translated_text(card.details.name_de) if card.details else None) or card.name
        rule = rule_payload(card, rules.get(card_id))
        if rule['status'] != 'mapped': issue('rules', rule['status'], f'{name}: {rule["message"]}', card_id)
        else:
            families[rule['identity']].append((card_id, quantity, rule['copy_limit'], name))
            for entry in entries:
                if entry['card_id'] == card_id and entry['section'] != 'side' and entry['section'] != rule['section']:
                    issue('rules', 'wrong_section', f'{name}: gehört ins {"Extra-Deck" if rule["section"] == "extra" else "Hauptdeck"}.', card_id)
            if not rule['script_available']: issue('engine', 'script_missing', f'{name}: Kartenskript fehlt.', card_id)
        if not rule['identity'] and quantity > 3:
            issue('rules', 'copy_limit', f'{name}: {quantity} Exemplare, höchstens 3 erlaubt.', card_id)
        own = stock.get(card_id, {'owned': 0, 'available': 0, 'stock_verified': True})
        if not own['stock_verified']: issue('stock', 'stock_unverified', f'{name}: Bestandszuordnung muss geprüft werden.', card_id)
        if quantity > own['available']:
            issue('stock', 'missing_stock', f'{name}: {quantity} benötigt, {own["available"]} frei, {own["owned"]} im Besitz.', card_id)
    for family in families.values():
        quantity, limit = sum(row[1] for row in family), min(row[2] for row in family)
        if quantity > limit:
            issue('rules', 'copy_limit', f'{family[0][3]}: insgesamt {quantity}, erlaubt {limit} (alle Bereiche und Illustrationen zusammen).', family[0][0])
    if not profile or not profile.engine_approved:
        issue('engine', 'engine_pending', 'Das Browser-Regelpaket ist noch nicht für vollständige Duelle freigegeben.')
    if not profile or not profile.region_approved:
        issue('engine', 'region_pending', 'Die europäische Karten-/Formatfreigabe ist noch nicht abgeschlossen.')
    rules_ok = not any(i['kind'] == 'rules' for i in issues)
    stock_ok = not any(i['kind'] == 'stock' for i in issues)
    engine_ok = not any(i['kind'] == 'engine' for i in issues)
    return {'counts': {s: totals[s] for s in ('main', 'extra', 'side')}, 'issues': issues,
            'rules_ok': rules_ok, 'stock_ok': stock_ok, 'engine_ok': engine_ok,
            'ready': rules_ok and stock_ok and engine_ok, 'stock': stock,
            'rules': {card_id: rule_payload(card, rules.get(card_id)) for card_id, card in cards.items()}}


def parse_ydk(text):
    if len(text.encode('utf8')) > 100_000: raise ValueError('YDK-Datei ist größer als 100 KB.')
    section, seen, result = None, [], []
    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if not line: continue
        if line in ('#main', '#extra', '!side'):
            section = {'#main': 'main', '#extra': 'extra', '!side': 'side'}[line]
            if section in seen or ['main', 'extra', 'side'][len(seen)] != section:
                raise ValueError(f'YDK-Bereiche in falscher Reihenfolge (Zeile {number}).')
            seen.append(section); continue
        if line.startswith('#') and not line.startswith(('#main', '#extra')): continue
        if not section or not re.fullmatch(r'[0-9]{1,10}', line) or not 0 < int(line) <= 2147483647:
            raise ValueError(f'Ungültiger Passcode oder Bereich in Zeile {number}.')
        result.append({'section': section, 'passcode': int(line)})
        if len(result) > 200: raise ValueError('YDK enthält mehr als 200 Karten.')
    if seen != ['main', 'extra', 'side']: raise ValueError('YDK benötigt #main, #extra und !side.')
    return result
