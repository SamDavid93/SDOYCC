"""Match progression and sideboarding from the originally reserved multiset."""
from collections import Counter
import copy
import json

from fastapi import HTTPException
from app.db.models import DuelMatchProgress, DuelWorkerRun
from app.modules.workflow import mutex

SECTIONS = ('main', 'extra', 'side')
EXTRA_TYPES = 0x40 | 0x2000 | 0x800000 | 0x4000000


def initial(snapshot):
    decks = [copy.deepcopy(player['sections']) for player in snapshot['players']]
    return {'version': 1, 'game': 1, 'phase': 'playing', 'score': [0, 0], 'results': [],
        'original': copy.deepcopy(decks), 'decks': decks, 'ready': [False, False],
        'starter': 0, 'chooser': None, 'next_starter': None}


def sideboard(progress, seat, sections, catalog):
    if set(sections) != set(SECTIONS): raise ValueError('All three sections required')
    original = progress['original'][seat]
    if any(len(sections[key]) != len(original[key]) for key in SECTIONS):
        raise ValueError('Initial section sizes must be preserved')
    if Counter(code for key in SECTIONS for code in sections[key]) != Counter(code for key in SECTIONS for code in original[key]):
        raise ValueError('Only the originally reserved card multiset may be used')
    for key in ('main', 'extra'):
        for code in sections[key]:
            if type(code) is not int or code not in catalog: raise ValueError('Unknown card')
            if bool(catalog[code]['type'] & EXTRA_TYPES) != (key == 'extra'):
                raise ValueError('Invalid main/extra card type')
    # Limits are unchanged because the immutable whole-deck multiset is unchanged.
    return copy.deepcopy(sections)


def record_game(progress, winner):
    value = copy.deepcopy(progress)
    if value['phase'] != 'playing': raise ValueError('Game already recorded')
    value['results'].append({'game': value['game'], 'winner': winner})
    if winner is not None: value['score'][winner] += 1
    value['version'] += 1
    value['phase'] = 'finished' if max(value['score']) >= 2 else 'sideboarding'
    value['ready'] = [False, False]
    value['chooser'] = 1 - winner if winner is not None else value['starter']
    value['next_starter'] = None
    return value


def save(db, run_id, owner, progress):
    mutex(db)
    run = db.get(DuelWorkerRun, run_id, populate_existing=True)
    if not run or run.owner_instance != owner or run.state not in ('starting', 'running'):
        raise HTTPException(409, 'Match-Zuordnung nicht mehr gueltig.')
    row = db.get(DuelMatchProgress, run_id)
    if row: row.progress_json = json.dumps(progress)
    else: db.add(DuelMatchProgress(run_id=run_id, progress_json=json.dumps(progress)))
    db.commit()


def public(progress, seat, catalog=None):
    if not progress: return None
    value = {key: copy.deepcopy(progress[key]) for key in
        ('version', 'game', 'phase', 'score', 'results', 'ready', 'starter', 'chooser', 'next_starter')}
    if progress['phase'] == 'sideboarding':
        value['decks'] = copy.deepcopy(progress['decks'][seat])
        value['cards'] = {code: {'code': code, 'name': catalog.get(code, {}).get('name', str(code)),
            'type': catalog.get(code, {}).get('type', 0)}
            for cards in progress['original'][seat].values() for code in cards} if catalog else {}
    return value
