"""Run with the pinned 32-bit Python. Disposable native fixtures, no Hub database.

Fixtures intentionally place cards in starting zones to exercise real scripts;
they are protocol/mechanics checks, not legal tournament opening positions.
"""
import base64
import ctypes as C
import itertools
import json
from pathlib import Path
import sqlite3
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core_worker import Core, Options, Player, NewCard
from protocol import Projection


def catalog(root):
    with sqlite3.connect(str(root / 'cards/cards.cdb')) as db:
        return {row[0]: dict(zip(('name', 'description', 'atk', 'defense', 'type', 'race', 'attribute', 'setcode', 'alias'), row[1:]))
            for row in db.execute('SELECT d.id,t.name,t.desc,d.atk,d.def,d.type,d.race,d.attribute,d.setcode,d.alias FROM datas d JOIN texts t ON t.id=d.id')}


def fixture(core, hands, fields, extras, spells=None, decks=None, draw=0):
    options = Options((C.c_uint64 * 4)(1, 2, 3, 4), 0x30002e800, Player(8000, 0, draw), Player(8000, 0, draw),
        core.reader, None, core.scripts, None, core.logger, None, core.done, None, 0)
    if core.lib.OCG_CreateDuel(C.byref(core.duel), C.byref(options)): raise RuntimeError('Fixture creation failed')
    for script in (b'constant.lua', b'utility.lua'):
        if not core.read_script(None, core.duel, script): raise RuntimeError('Bootstrap missing')
    for owner in (0, 1):
        groups = [(1, decks[owner] if decks is not None else [89631139] * 40, 8), (2, hands[owner], 8), (4, fields[owner], 1), (64, extras[owner], 8), (8, (spells or [[], []])[owner], 8)]
        for zone, codes, position in groups:
            for sequence, code in enumerate(codes):
                seq, pos = sequence, position
                if isinstance(code, tuple): seq, code, pos = code
                core.lib.OCG_DuelNewCard(core.duel, C.byref(NewCard(owner, 0, code, owner, zone, seq, pos)))
    core.lib.OCG_StartDuel(core.duel)
    return core.process()


def answer(projection, target):
    prompt = projection.prompt
    choices = prompt['choices']
    if prompt.get('counter'):
        left = prompt['counter_total']; values = []
        for limit in prompt['counter_limits']:
            take = min(limit, left); values.append(take); left -= take
        return projection.respond(prompt['owner'], prompt['id'], values)
    if prompt.get('select'):
        for count in range(prompt['minimum'], min(prompt['maximum'], len(choices)) + 1):
            for indices in itertools.combinations(range(len(choices)), count):
                try: return projection.respond(prompt['owner'], prompt['id'], list(indices))
                except ValueError: pass
    else:
        candidates = list(range(len(choices)))
        if prompt['title'] == 'Aktion wählen':
            desired = [i for i, choice in enumerate(choices) if choice.get('code') == target and
                (choice['label'].startswith('Spezial') or choice['label'].startswith('Beschw') or choice['label'].startswith('Aktivieren'))]
            desired.sort(key=lambda i: 0 if choices[i]['label'].startswith('Spezial') else 1 if choices[i]['label'].startswith('Aktivieren') else 2)
            candidates = desired + [i for i in candidates if i not in desired]
        for index in candidates:
            try: return projection.respond(prompt['owner'], prompt['id'], [index])
            except ValueError: pass
    if prompt.get('cancel'): return projection.respond(prompt['owner'], prompt['id'], [], True)
    raise ValueError('No legal fixture response')


def run():
    root = Path(sys.argv[1]).resolve(); cards = catalog(root)
    def code(name):
        matches = [key for key, value in cards.items() if value['name'] == name and not value['alias']]
        if len(matches) != 1: raise ValueError('Fixture card name is not unique: ' + name)
        return matches[0]
    scapegoat = code('Scapegoat')
    scenarios = [
        ('tribute', [[89631139], []], [[43096270, 69247929], []], [[], []], 89631139),
        ('synchro', [[], []], [[21615956, 6368038], []], [[44508094], []], 44508094),
        ('xyz', [[], []], [[43096270, 69247929], []], [[84013237], []], 84013237),
        ('link', [[], []], [[43096270, 69247929], []], [[2857636], []], 2857636),
        ('fusion', [[24094653, 46986414, 38033121], []], [[], []], [[50237654], []], 24094653),
        ('ritual', [[55761792, 5405694, 89631139], []], [[], []], [[], []], 55761792),
        ('pendulum', [[15146890, 51531505, 43096270], []], [[], []], [[], []], 15146890),
        ('chain-negation', [[12580477], [89631139]], [[], [43096270]], [[], []], 12580477),
        ('counter', [[71413901], []], [[], []], [[], []], 71413901),
        ('token', [[scapegoat], []], [[], []], [[], []], scapegoat),
    ]
    results = []
    for name, hands, fields, extras, target in scenarios:
        core = Core(root); projection = Projection(cards)
        try:
            spells = [[], [(0, 77414722, 8)]] if name == 'chain-negation' else None
            projection.consume(fixture(core, hands, fields, extras, spells))
            invoked = False
            for step in range(35):
                if projection.ended: break
                action_target = target
                if name == 'pendulum':
                    placed = {entry.get('code') for entry in projection.query_boards[0]['zones']['8'] if entry}
                    action_target = 15146890 if 15146890 not in placed else 51531505 if 51531505 not in placed else 15146890
                response = answer(projection, action_target)
                projection.consume(core.respond(base64.b64encode(response).decode()))
                if name == 'tribute': expected = target
                elif extras[0]: expected = extras[0][0]
                elif name == 'pendulum': expected = 43096270
                elif name == 'counter': expected = target
                else: expected = 5405694
                present = any(entry and entry.get('code') == expected for entry in projection.query_boards[0]['zones']['4'])
                if name == 'chain-negation': present = 75 in projection.seen and 74 in projection.seen
                if name == 'counter': present = 101 in projection.seen
                if name == 'token':
                    present = sum(bool(entry and cards.get(entry.get('code'), {}).get('type', 0) & 0x4000)
                        for entry in projection.query_boards[0]['zones']['4']) == 4
                if name == 'pendulum': present = present and 62 in projection.seen
                if present:
                    invoked = True; break
            if not invoked: raise AssertionError('Expected native summon did not finish')
            results.append({'scenario': name, 'status': 'passed', 'prompts_and_messages': sorted(projection.seen), 'responses': step + 1})
        except Exception as error:
            results.append({'scenario': name, 'status': 'failed', 'error': str(error), 'seen': sorted(projection.seen), 'prompt': {k: v for k, v in projection.prompt.items() if k != 'choices'} if projection.prompt else None})
        finally: core.close()
    exodia = [code(name) for name in ('Exodia the Forbidden One', 'Left Arm of the Forbidden One',
        'Right Arm of the Forbidden One', 'Left Leg of the Forbidden One', 'Right Leg of the Forbidden One')]
    for name, hands, decks, draw, expected_winner in (
            ('alternative-victory', [exodia[:-1], []], [[exodia[-1]], [89631139] * 40], 1, 0),
            ('simultaneous-alternative-draw', [exodia, exodia], [[89631139], [89631139]], 1, None),
            ('empty-draw-deck', [[], []], [[], []], 1, 0)):
        core = Core(root); projection = Projection(cards); responses = 0
        try:
            projection.consume(fixture(core, hands, [[], []], [[], []], decks=decks, draw=draw))
            for _ in range(20):
                if projection.ended: break
                choices = projection.prompt['choices']
                end = next((index for index, choice in enumerate(choices) if choice['label'].startswith('Zug beenden')), None)
                response = projection.respond(projection.prompt['owner'], projection.prompt['id'], [end]) if end is not None else answer(projection, 0)
                projection.consume(core.respond(base64.b64encode(response).decode()))
                responses += 1
            assert projection.ended and projection.winner == expected_winner, 'Native result did not match fixture outcome'
            results.append({'scenario': name, 'status': 'passed', 'prompts_and_messages': sorted(projection.seen), 'responses': responses})
        except Exception as error:
            results.append({'scenario': name, 'status': 'failed', 'error': str(error), 'seen': sorted(projection.seen)})
        finally: core.close()
    print(json.dumps({'native_core': True, 'production_modified': False, 'scenarios': results}, ensure_ascii=True))
    return 0 if all(row['status'] == 'passed' for row in results) else 1


if __name__ == '__main__': raise SystemExit(run())
