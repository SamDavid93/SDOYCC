"""Strict independent EU list mapping. Konami database IDs are not passcodes."""
from collections import defaultdict
from datetime import datetime, date
import html

from app.modules.duel_rules import canonical, resolve_identity


def official_limits(data, cards, today=None):
    effective = datetime.strptime(data['from'], '%d/%m/%Y').date()
    if effective > (today or date.today()): raise ValueError('Official list is not effective yet')
    names = defaultdict(set)
    for code, card in cards.items():
        identity = resolve_identity(code, cards)
        if identity and card['ot'] in (2, 3): names[canonical(card['name'])].add(identity)
    limits, missing = {}, []
    for limit in (0, 1, 2):
        if not isinstance(data.get(str(limit)), list): raise ValueError('Incomplete official list')
        for row in data[str(limit)]:
            name = html.unescape(row['nameeng'])
            identities = names.get(canonical(name), set())
            if len(identities) != 1:
                missing.append({'name': name, 'reason': 'missing' if not identities else 'ambiguous'})
                continue
            identity = next(iter(identities))
            if identity in limits and limits[identity] != limit: raise ValueError('Conflicting official limits')
            limits[identity] = limit
    if not limits: raise ValueError('Empty official list')
    return effective.isoformat(), limits, missing


def compare_limits(cards, pinned, official):
    family = {}
    for code, limit in pinned.items():
        identity = resolve_identity(code, cards)
        if not identity: raise ValueError('Pinned list has unresolved card identity')
        family[identity] = min(family.get(identity, 3), limit)
    return [{'passcode': code, 'name': cards[code]['name'], 'pinned': family.get(code, 3),
        'official': official.get(code, 3)} for code in sorted(set(family) | set(official))
        if family.get(code, 3) != official.get(code, 3)]
