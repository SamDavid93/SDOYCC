"""D0-only, fail-closed browser projection of the pinned EDOPro 11 protocol.

This is deliberately NOT a complete Yu-Gi-Oh client. The laboratory uses a
closed normal-monster / normal damage-spell fixture. Unknown prompts abort.
Wire layout reference: edo9300/edopro gframe/duelclient.cpp (AGPL-3.0-or-later).
Never send raw engine frames, response buffers or private card codes to clients.
"""
import base64
import struct
import importlib.util
from pathlib import Path

_declarations_spec = importlib.util.spec_from_file_location('sdoycc_declarations', Path(__file__).with_name('declarations.py'))
_declarations = importlib.util.module_from_spec(_declarations_spec)
_declarations_spec.loader.exec_module(_declarations)


class UnsupportedMessage(ValueError):
    pass


class Reader:
    def __init__(self, data): self.data, self.offset = data, 0
    def read(self, fmt):
        size = struct.calcsize('<' + fmt)
        if self.offset + size > len(self.data): raise ValueError('Truncated engine frame')
        values = struct.unpack_from('<' + fmt, self.data, self.offset)
        self.offset += size
        return values[0] if len(values) == 1 else values
    def loc(self):
        owner, zone, sequence, position = self.read('BBII')
        return {'owner': owner, 'zone': zone, 'sequence': sequence, 'position': position}


class Projection:
    def __init__(self, catalog, strings=None):
        self.catalog = catalog
        self.strings = strings or {}
        self.selection_hints = {}
        self.lp = [8000, 8000]
        self.hands = [[], []]
        self.field = [{}, {}]
        self.grave = [[], []]
        self.deck_count = [40, 40]
        self.turn, self.phase, self.turn_number = 0, 0, 0
        self.prompt = None
        self.revision = 0
        self.events = []
        self.event_sequence = 0
        self.winner = None
        self.ended = False
        self.end_reason = None
        self.match_kill = False
        self.seen = set()
        self.query_boards = None
        self.disabled = 0
        self.chain_cards = {}
        self.attack_cards = []

    def card(self, code):
        return {'code': code, **{key: value for key, value in self.catalog[code].items() if key != 'options'}}

    def public_events(self, owner):
        return [{**{key: value for key, value in event.items() if not key.startswith('_')},
                 **({'affected_cards': event['_cards_by_seat'][owner]} if '_cards_by_seat' in event else {})}
            for event in self.events[-100:] if '_audience' not in event or owner in event['_audience']]

    @staticmethod
    def location_visible(location, seat):
        zone = location['zone']
        return (location['owner'] == seat and zone in (2, 4, 8, 16, 32, 64)) or (zone in (4, 8, 16, 32, 64) and bool(location.get('position', 0) & 5))

    def named_card(self, role, code, locations):
        return [(role, code, {seat for seat in (0, 1) if any(self.location_visible(location, seat) for location in locations)})]

    def named_location(self, role, location):
        owner, zone, sequence = location['owner'], location['zone'], location['sequence']
        entry = self.field[owner].get((zone, sequence)) if zone in (4, 8) else None
        if entry is None and self.query_boards:
            entries = self.query_boards[owner]['zones'].get(str(zone), [])
            entry = entries[sequence] if sequence < len(entries) else None
        if entry:
            seats = {seat for seat in (0, 1) if not entry.get('hidden') and (entry.get('public') or self.location_visible({**location, 'position': entry.get('position', 0)}, seat))}
            return [(role, entry.get('code', 0), seats)]
        return [(role, 0, set())]

    def event(self, kind, **data):
        affected = data.pop('_affected', None)
        if affected is not None:
            # Snapshot names now: later flips, shuffles and moves must not rewrite history.
            data['_cards_by_seat'] = {seat: [{'role': role, 'name': self.catalog[code]['name'] if seat in visible and code in self.catalog else 'Verdeckte Karte'}
                for role, code, visible in affected] for seat in (0, 1)}
        self.event_sequence += 1
        self.events.append({'id': self.event_sequence, 'kind': kind, **data})
        if len(self.events) > 3000: del self.events[:-3000]

    def consume(self, packet):
        if 'error' in packet: raise RuntimeError(packet['error'])
        self.prompt = None
        for encoded in packet['messages']:
            r = Reader(base64.b64decode(encoded, validate=True))
            msg = r.read('B'); self.seen.add(msg)
            if msg == 2:
                kind, recipient, value = r.read('BBQ')
                if kind == 3: self.selection_hints[recipient] = self.description(value)
                elif kind in (1, 2, 4, 5, 6, 7, 8, 9, 10):
                    text = self.description(value) if kind in (1, 2, 4) else self.catalog.get(value, {}).get('name', str(value))
                    self.event('hint', text=text, _audience=[recipient])
            elif msg in (10, 11):
                owner = r.read('B'); choices = []
                groups = range(6) if msg == 11 else range(2)
                labels = ['Beschwören', 'Spezialbeschwören', 'Position ändern', 'Monster setzen', 'Zauber/Falle setzen', 'Aktivieren'] if msg == 11 else ['Aktivieren', 'Angreifen']
                for group in groups:
                    for index in range(r.read('I')):
                        code, controller, zone = r.read('IBB')
                        small = (msg == 11 and group == 2) or (msg == 10 and group == 1)
                        sequence = r.read('B' if small else 'I')
                        if (msg == 11 and group == 5) or (msg == 10 and group == 0): r.read('QB')
                        elif msg == 10 and group == 1: r.read('B')
                        choices.append(self.choice(f'{labels[group]}: {self.catalog[code]["name"]}',
                                                   struct.pack('<i', (index << 16) + group), code))
                        choices[-1].update(action=(['summon', 'special_summon', 'position', 'set_monster', 'set_spell', 'activate'] if msg == 11 else ['activate', 'attack'])[group],
                            location={'owner': controller, 'zone': zone, 'sequence': sequence})
                phase_choices = [(6, 'Kampfphase'), (7, 'Zug beenden')] if msg == 11 else [(2, 'Hauptphase 2'), (3, 'Zug beenden')]
                for number, text in phase_choices:
                    if r.read('B'): choices.append(self.choice(text, struct.pack('<i', number)))
                if msg == 11: r.read('B')  # optional hand shuffle is not a game decision
                self.new_prompt(owner, 'Aktion wählen', choices)
            elif msg in (18, 24):
                owner, count, blocked = r.read('BBI')
                if count > 32: raise ValueError('Invalid zone count')
                choices = []
                for bit in range(32):
                    if blocked & (1 << bit): continue
                    controller = owner if bit < 16 else 1 - owner
                    zone, sequence = (4 if bit % 16 < 8 else 8), bit % 8
                    choices.append(self.choice(f'{"Eigene" if controller == owner else "Gegnerische"} Zone {sequence + 1}', bytes([controller, zone, sequence])))
                    choices[-1]['location'] = {'owner': controller, 'zone': zone, 'sequence': sequence}
                self.new_prompt(owner, 'Zone wählen', choices)
                self.prompt['kind'] = 'zones'
                self.prompt['placement'] = msg == 18
                if count > 1:
                    self.prompt.update(select=True, minimum=count, maximum=count, _response_kind='zones')
            elif msg == 19:
                owner, code, positions = r.read('BIB')
                choices = [self.choice(text, struct.pack('<i', position), code) for position, text in
                           [(1, 'Offener Angriff'), (2, 'Verdeckter Angriff'), (4, 'Offene Verteidigung'), (8, 'Verdeckte Verteidigung')] if positions & position]
                self.new_prompt(owner, 'Position wählen', choices)
            elif msg == 15:
                owner, cancel = r.read('BB'); minimum, maximum, count = r.read('III')
                choices = []
                for index in range(count):
                    code = r.read('I'); location = r.loc()
                    choices.append(self.choice(self.catalog[code]['name'] if code else 'Verdeckte Karte', b'', code or None))
                    choices[-1]['location'] = location
                self.new_prompt(owner, 'Karten auswählen', choices, allow_empty=minimum == 0 or bool(cancel))
                self.prompt.update(minimum=minimum, maximum=maximum, select=True, cancel=bool(cancel))
            elif msg == 12:
                owner, code = r.read('BI'); location = r.loc(); description = r.read('Q')
                self.new_prompt(owner, 'Effekt von ' + self.catalog[code]['name'] + ' aktivieren?',
                    [self.choice('Ja', struct.pack('<i', 1), code), self.choice('Nein', struct.pack('<i', 0), code)])
                self.prompt['effect_card'] = self.card(code)
                self.prompt['effect_location'] = location
            elif msg in (14, 143):
                owner, count = r.read('BB')
                choices = []
                for index in range(count):
                    value = r.read('Q')
                    label = str(value & 0xffffffff) if msg == 143 else self.description(value, index)
                    choices.append(self.choice(label, struct.pack('<i', index)))
                self.new_prompt(owner, 'Zahl ansagen' if msg == 143 else 'Effektoption wählen', choices)
            elif msg == 26:
                owner, finishable, cancelable = r.read('BBB'); minimum, maximum = r.read('II')
                choices, selected_count = [], 0
                for removing in (False, True):
                    count = r.read('I')
                    if removing: selected_count = count
                    for _ in range(count):
                        code = r.read('I'); info = r.loc()
                        label = self.catalog[code]['name'] if code else 'Verdeckte Karte'
                        index = len(choices)
                        choices.append(self.choice(('Abwählen: ' if removing else 'Auswählen: ') + label,
                            struct.pack('<II', 1, index), code or None))
                        choices[-1]['location'] = info
                self.new_prompt(owner, 'Auswahl ändern', choices, allow_empty=bool(finishable or cancelable))
                self.prompt.update(cancel=bool(finishable or cancelable), selection_progress={
                    'minimum': minimum, 'maximum': maximum, 'selected': selected_count, 'can_finish': bool(finishable)})
            elif msg in (20, 21, 25):
                owner = r.read('B')
                cancel = r.read('B') if msg == 20 else True
                minimum, maximum, count = r.read('III') if msg == 20 else (0, 0, r.read('I'))
                choices, weights = [], []
                for _ in range(count):
                    code, controller = r.read('IB')
                    zone, sequence = r.read('BI') if msg == 20 else r.read('II')
                    weight = r.read('B') if msg == 20 else 0
                    weights.append(weight)
                    name = self.catalog[code]['name'] if code else 'Verdeckte Karte'
                    choices.append(self.choice(name + (f' · Tributwert {weight}' if msg == 20 else ''), b'', code or None))
                    choices[-1]['location'] = {'owner': controller, 'zone': zone, 'sequence': sequence}
                self.new_prompt(owner, 'Tribute wählen' if msg == 20 else 'Reihenfolge wählen', choices)
                self.prompt.update(select=True, minimum=0 if msg == 20 else count,
                    maximum=maximum if msg == 20 else count, cancel=bool(cancel),
                    ordered=msg != 20, _response_kind='tribute' if msg == 20 else 'sort',
                    _weights=weights, _tribute_minimum=minimum)
            elif msg == 22:
                owner, counter_type, total, count = r.read('BHHI')
                choices, limits = [], []
                for _ in range(count):
                    code, controller, zone, sequence, available = r.read('IBBBH')
                    limits.append(available)
                    choices.append(self.choice(self.catalog[code]['name'] if code else 'Verdeckte Karte', b'', code or None))
                    choices[-1]['location'] = {'owner': controller, 'zone': zone, 'sequence': sequence}
                self.new_prompt(owner, 'Zählmarken entfernen', choices)
                self.prompt.update(counter=True, counter_limits=limits, counter_total=total, _response_kind='counter')
            elif msg == 23:
                owner, mode, target, minimum, maximum, required = r.read('BBIIII')
                mandatory = []
                for _ in range(required):
                    r.read('I'); r.loc(); mandatory.append(r.read('I'))
                choices, weights = [], []
                for _ in range(r.read('I')):
                    code = r.read('I'); location = r.loc(); value = r.read('I')
                    weights.append(value)
                    values = [value & 65535] + ([value >> 16] if value >> 16 else [])
                    name = self.catalog[code]['name'] if code else 'Verdeckte Karte'
                    choices.append(self.choice(name + ' · Wert ' + '/'.join(map(str, values)), b'', code or None))
                    choices[-1]['location'] = location
                self.new_prompt(owner, 'Materialien für Summe ' + str(target) + ' wählen', choices)
                self.prompt.update(select=True, minimum=minimum if mode == 0 else 0, maximum=maximum if mode == 0 else len(choices),
                    _response_kind='sum', _weights=weights, _mandatory=mandatory, _sum_mode=mode, _sum_target=target)
            elif msg in (140, 141):
                owner, count = r.read('BB'); allowed = r.read('Q' if msg == 140 else 'I')
                names = ['Erde', 'Wasser', 'Feuer', 'Wind', 'Licht', 'Finsternis', 'Göttlich'] if msg == 141 else [
                    'Krieger', 'Hexer', 'Fee', 'Unterweltler', 'Zombie', 'Maschine', 'Aqua', 'Pyro', 'Fels',
                    'Geflügeltes Ungeheuer', 'Pflanze', 'Insekt', 'Donner', 'Drache', 'Ungeheuer',
                    'Ungeheuer-Krieger', 'Dinosaurier', 'Fisch', 'Seeschlange', 'Reptil', 'Psi',
                    'Göttliches Ungeheuer', 'Schöpfergott', 'Wyrm', 'Cyberse', 'Illusion']
                values = [1 << bit for bit in range(64 if msg == 140 else 32) if allowed & (1 << bit)]
                choices = [self.choice(names[value.bit_length()-1] if value.bit_length()-1 < len(names) else 'Typ ' + str(value.bit_length()), b'') for value in values]
                self.new_prompt(owner, 'Typ ansagen' if msg == 140 else 'Eigenschaft ansagen', choices)
                self.prompt.update(select=True, minimum=count, maximum=count, _response_kind='mask', _values=values, _mask_format='Q' if msg == 140 else 'I')
            elif msg == 132:
                owner = r.read('B')
                self.new_prompt(owner, 'Schere, Stein, Papier', [self.choice(label, struct.pack('<i', i)) for i, label in [(1, 'Schere'), (2, 'Stein'), (3, 'Papier')]])
            elif msg == 142:
                owner, count = r.read('BB')
                program = [r.read('Q') for _ in range(count)]
                choices = [self.choice(card['name'], struct.pack('<i', code), code)
                    for code, card in self.catalog.items() if _declarations.declarable(code, card, program)]
                self.new_prompt(owner, 'Karte ansagen', choices)
            elif msg == 16:
                owner, special, forced = r.read('BBB'); r.read('II'); count = r.read('I')
                choices = []
                for index in range(count):
                    code = r.read('I'); location = r.loc(); r.read('QB')
                    choices.append(self.choice('Effekt: ' + self.catalog[code]['name'], struct.pack('<i', index), code))
                    choices[-1]['location'] = location
                if not forced: choices.append(self.choice('Nicht anketten', struct.pack('<i', -1)))
                self.new_prompt(owner, 'Auf die Kette reagieren', choices)
                if not forced and count == 0:
                    self.prompt['_empty_chain'] = True
            elif msg == 13:
                owner = r.read('B'); description = r.read('Q')
                self.new_prompt(owner, self.description(description), [self.choice('Ja', struct.pack('<i', 1)), self.choice('Nein', struct.pack('<i', 0))])
            elif msg == 90:
                owner, count = r.read('BI')
                drawn = []
                for _ in range(count):
                    code, position = r.read('II'); self.hands[owner].append(code)
                    drawn.append(('Karte', code, {owner}))
                self.deck_count[owner] -= count
                self.event('draw', player=owner, count=count, _affected=drawn)
            elif msg == 50:
                code = r.read('I'); before, after = r.loc(), r.loc(); reason = r.read('I')
                owner = before['owner']; zone = before['zone']; seq = before['sequence']
                if zone == 2 and 'query_boards' not in packet: self.hands[owner].pop(seq)
                elif zone in (4, 8): self.field[owner].pop((zone, seq), None)
                elif zone == 16 and 'query_boards' not in packet: self.grave[owner].pop(seq)
                owner, zone, seq = after['owner'], after['zone'], after['sequence']
                if zone == 2: self.hands[owner].insert(seq, code)
                elif zone in (4, 8): self.field[owner][(zone, seq)] = {'code': code, 'position': after['position']}
                elif zone == 16: self.grave[owner].append(code)
                elif zone not in (0, 1) and 'query_boards' not in packet: raise UnsupportedMessage('Zone outside laboratory pool')
                kind = 'destroy' if reason & 1 and zone == 16 else 'banish' if zone == 32 else 'control' if before['owner'] != owner and zone in (4, 8) else 'material' if before['zone'] & 128 or zone & 128 else 'token' if before['zone'] == 0 and self.catalog.get(code, {}).get('type', 0) & 0x4000 else 'move'
                self.event(kind, player=owner, zone=zone, before=before, after=after, _affected=self.named_card('Karte', code, [before, after]))
            elif msg == 53:
                code, owner, zone, seq, old, new = r.read('IBBBBB')
                self.field[owner][(zone, seq)] = {'code': code, 'position': new}
                self.event('position', player=owner, _affected=self.named_card('Karte', code, [{'owner': owner, 'zone': zone, 'position': old}, {'owner': owner, 'zone': zone, 'position': new}]))
            elif msg == 40:
                if self.turn_number:
                    self.event('turn_end', player=self.turn, number=self.turn_number)
                self.turn = r.read('B'); self.turn_number += 1
                self.event('turn', player=self.turn, number=self.turn_number)
            elif msg == 41:
                self.phase = r.read('H'); self.event('phase', phase=self.phase, player=self.turn, number=self.turn_number)
            elif msg in (91, 92, 94, 100):
                owner, value = r.read('BI')
                previous = self.lp[owner]
                self.lp[owner] = value if msg == 94 else max(0, self.lp[owner] + (value if msg == 92 else -value))
                self.event('lp', player=owner, value=self.lp[owner], delta=self.lp[owner] - previous)
            elif msg == 5:
                winner, reason = r.read('BB')
                if winner not in (0, 1, 2): raise ValueError('Invalid native winner')
                self.winner = winner if winner in (0, 1) else None
                self.ended = True
                self.prompt = None
                self.end_reason = 'engine'
                self.event('win', winner=self.winner, reason=reason)
            elif msg in (60, 62, 64):
                code = r.read('I'); info = r.loc()
                bits = self.catalog.get(code, {}).get('type', 0)
                method = 'covered' if not info['position'] & 5 else 'flip' if msg == 64 else 'normal' if msg == 60 else 'fusion' if bits & 0x40 else 'synchro' if bits & 0x2000 else 'xyz' if bits & 0x800000 else 'link' if bits & 0x4000000 else 'ritual' if bits & 0x80 else 'pendulum' if bits & 0x1000000 else 'special'
                self.event('summon', player=info['owner'], location=info, method=method, _affected=self.named_card('Karte', code, [info]))
            elif msg == 70:
                code = r.read('I'); source = r.loc(); player, zone, sequence, description, number = r.read('BBIQI')
                options = self.catalog.get(code, {}).get('options', [])
                effect = self.strings.get(description) or (options[description & 15] if description >> 4 == code and description & 15 < len(options) else None)
                # An activated card is public to both seats; other hidden cards stay private.
                self.event('chain', source=source, number=number, card=self.card(code), effect=effect)
                self.chain_cards[number] = code
            elif msg in (71, 72, 73, 74, 75, 76):
                number = r.read('B') if msg != 74 else 0
                codes = [self.chain_cards[number]] if number in self.chain_cards else list(self.chain_cards.values()) if msg == 74 else []
                self.event('chain_step', step=msg, number=number, _affected=[('Effektkarte', code, {0, 1}) for code in codes])
                if msg == 74: self.chain_cards.clear()
            elif msg == 110:
                attacker, defender = r.loc(), r.loc()
                affected = self.named_location('Angreifer', attacker)
                if defender['zone']: affected += self.named_location('Ziel', defender)
                self.attack_cards = affected
                self.event('attack', attacker=attacker, defender=defender, direct=not defender['zone'], _affected=affected)
            elif msg == 56:
                self.disabled = r.read('I'); self.event('zones', disabled=self.disabled)
            elif msg == 170:
                r.read('I'); self.match_kill = True
            elif msg in (93, 96, 97):
                source, target = r.loc(), r.loc()
                self.event('equip' if msg == 93 else 'target' if msg == 96 else 'untarget', source=source, target=target,
                           _affected=self.named_location('Karte', source) + self.named_location('Ziel', target))
            elif msg == 95:
                source = r.loc(); self.event('unequip', source=source, _affected=self.named_location('Karte', source))
            elif msg in (101, 102):
                counter, player, zone, sequence, count = r.read('HBBBH')
                self.event('counter', player=player, zone=zone, sequence=sequence, counter=counter, count=count, added=msg == 101,
                           _affected=self.named_location('Karte', {'owner': player, 'zone': zone, 'sequence': sequence}))
            elif msg in (30, 31, 42):
                recipient, count = r.read('BI')
                cards = []
                if count > 200: raise ValueError('Reveal card limit')
                for _ in range(count):
                    code, controller, zone, sequence = r.read('IBBI')
                    if code: cards.append(self.card(code))
                self.event('reveal', cards=cards, _audience=[recipient])
            elif msg in (32, 33, 36, 39) and 'query_boards' in packet:
                self.event('shuffle', player=r.read('B'))
            elif msg in (130, 131):
                player, count = r.read('BB')
                values = [r.read('B') for _ in range(count)]
                self.event('coin' if msg == 130 else 'dice', player=player, values=values)
            elif msg == 112: self.event('negate', _affected=self.attack_cards)
            elif msg in (30, 31, 34, 35, 37, 38, 42, 55, 56, 81, 93, 95, 96, 97, 101, 102, 120, 121, 122, 123, 133, 170, 190) and 'query_boards' in packet:
                # Full authoritative queries apply movement/stat/zone changes.
                # Raw private informational packets are never forwarded.
                self.event('information', message=msg)
            elif msg in (2, 3, 54, 61, 63, 65, 80, 83, 111, 112, 113, 114, 160, 165):
                pass  # D0 informational only; no raw messages leave the server
            else:
                raise UnsupportedMessage('Engine message not yet implemented: ' + str(msg))
        self.revision += 1
        if 'query_boards' in packet:
            self.query_boards = packet['query_boards']
            self.field = [{(zone, sequence): dict(entry) for zone in (4, 8)
                for sequence, entry in enumerate(board['zones'][str(zone)]) if entry}
                for board in self.query_boards]
        if self.prompt: self.prompt['id'] = self.revision
        if packet['status'] == 1 and not self.prompt:
            raise UnsupportedMessage('Waiting without supported prompt')

    @staticmethod
    def choice(label, response, code=None):
        return {'label': label, '_response': response, 'code': code}

    def description(self, value, index=0):
        if value in self.strings: return self.strings[value]
        code, number = value >> 4, value & 15
        options = self.catalog.get(code, {}).get('options', [])
        return options[number] if number < len(options) and options[number] else f'Option {index + 1} · Effektkennung {value}'

    def surrender(self, owner):
        if type(owner) is not int or owner not in (0, 1) or self.ended:
            raise ValueError('Keine gültige Aufgabe möglich')
        self.ended = True
        self.winner = 1 - owner
        self.end_reason = 'surrender'
        self.prompt = None
        self.revision += 1
        self.event('win', winner=self.winner, reason='surrender')

    def new_prompt(self, owner, title, choices, allow_empty=False):
        if owner not in (0, 1) or (not choices and not allow_empty): raise ValueError('Invalid engine prompt')
        self.prompt = {'owner': owner, 'title': title, 'choices': choices}
        if owner in self.selection_hints: self.prompt['hint'] = self.selection_hints.pop(owner)

    def respond(self, owner, prompt_id, selected, cancel=False):
        p = self.prompt
        if type(owner) is not int or type(prompt_id) is not int or not p or p['owner'] != owner or p['id'] != prompt_id:
            raise ValueError('Veraltete oder fremde Entscheidung')
        if type(cancel) is not bool: raise ValueError('Ungültiger Abbruch')
        if cancel:
            if not p.get('cancel') or selected != []: raise ValueError('Diese Auswahl darf nicht abgebrochen werden')
            return struct.pack('<i', -1)
        if not isinstance(selected, list) or any(type(i) is not int for i in selected) or (not p.get('counter') and len(set(selected)) != len(selected)):
            raise ValueError('Ungültige Auswahl')
        if p.get('counter'):
            if len(selected) != len(p['choices']) or any(not 0 <= value <= limit for value, limit in zip(selected, p['counter_limits'])) or sum(selected) != p['counter_total']:
                raise ValueError('Ungültige Zählmarkenanzahl')
            return struct.pack('<' + 'H' * len(selected), *selected)
        if any(i < 0 or i >= len(p['choices']) for i in selected): raise ValueError('Ungültige Auswahl')
        if p.get('select'):
            if not p['minimum'] <= len(selected) <= p['maximum']: raise ValueError('Ungültige Kartenanzahl')
            kind = p.get('_response_kind')
            if kind == 'zones': return b''.join(p['choices'][index]['_response'] for index in selected)
            if kind == 'sort':
                ranks = [selected.index(index) for index in range(len(p['choices']))]
                return bytes(ranks)
            if kind == 'mask':
                mask = 0
                for index in selected: mask |= p['_values'][index]
                return struct.pack('<' + p['_mask_format'], mask)
            if kind == 'tribute' and sum(p['_weights'][index] for index in selected) < p['_tribute_minimum']:
                raise ValueError('Nicht genügend Tribute')
            if kind == 'sum':
                weights = p['_mandatory'] + [p['_weights'][index] for index in selected]
                if p['_sum_mode'] == 0:
                    totals = {0}
                    for value in weights:
                        options = {value & 65535} | ({value >> 16} if value >> 16 else set())
                        totals = {total + option for total in totals for option in options if total + option <= p['_sum_target']}
                        if len(totals) > 100000: raise ValueError('Summenauswahl zu komplex')
                    valid = p['_sum_target'] in totals
                else:
                    lows = [min(value & 65535, value >> 16) if value >> 16 else value & 65535 for value in weights]
                    highs = [max(value & 65535, value >> 16) for value in weights]
                    valid = bool(weights) and (sum(lows) >= p['_sum_target'] or sum(highs) >= p['_sum_target'] > sum(highs) - min(highs))
                if not valid: raise ValueError('Ungültige Materialsumme')
            return struct.pack('<' + 'I' * (2 + len(selected)), 0, len(selected), *selected)
        if len(selected) != 1: raise ValueError('Genau eine Aktion wählen')
        if p['title'] == 'Aktion wählen' and p['choices'][selected[0]]['label'] == 'Zug beenden' and not p.get('_announced_end'):
            self.event('phase_request', player=owner, phase=512, number=self.turn_number)
            p['_announced_end'] = True
        return p['choices'][selected[0]]['_response']

    def public_choice(self, choice):
        return {'label': choice['label'], 'card': self.card(choice['code']) if choice['code'] else None,
                **{key: choice[key] for key in ('action', 'location') if key in choice}}

    def view(self, owner):
        if self.query_boards is not None:
            return self.query_view(owner)
        boards = []
        for player in (0, 1):
            field = []
            for (zone, sequence), entry in self.field[player].items():
                visible = player == owner or entry['position'] & 5
                field.append({'zone': zone, 'sequence': sequence, 'position': entry['position'],
                              'card': self.card(entry['code']) if visible else None})
            boards.append({'lp': self.lp[player], 'deck': self.deck_count[player],
                           'hand': [self.card(code) if player == owner else None for code in self.hands[player]],
                           'field': field, 'grave': [self.card(code) for code in self.grave[player]]})
        prompt = None
        if self.prompt and self.prompt['owner'] == owner:
            prompt = {key: value for key, value in self.prompt.items() if key != 'choices' and not key.startswith('_')}
            prompt['choices'] = [self.public_choice(c) for c in self.prompt['choices']]
        return {'revision': self.revision, 'seat': owner, 'boards': boards, 'turn': self.turn,
                'phase': self.phase, 'turn_number': self.turn_number, 'prompt': prompt,
                'events': self.public_events(owner), 'winner': self.winner, 'ended': self.ended,
                'end_reason': self.end_reason}

    def query_view(self, owner):
        def visible(entry, player, zone):
            return bool(entry and not entry.get('hidden') and (entry.get('public') or
                (player == owner and zone in (2, 4, 8, 16, 32, 64)) or (zone in (4, 8, 16, 32, 64) and entry.get('position', 0) & 5)))
        def card(entry):
            return {**self.card(entry['code']), **{key: entry[key] for key in ('atk', 'defense', 'level', 'rank', 'lscale', 'rscale', 'link', 'link_marker') if key in entry}}
        boards = []
        for player, board in enumerate(self.query_boards):
            zones = board['zones']
            field = []
            for zone in (4, 8):
                for sequence, entry in enumerate(zones[str(zone)]):
                    if not entry: continue
                    shown = visible(entry, player, zone)
                    field.append({'zone': zone, 'sequence': sequence, 'position': entry.get('position', 0),
                        'disabled': bool(self.disabled & (1 << (player * 16 + (8 if zone == 8 else 0) + sequence))),
                        'card': card(entry) if shown else None, 'materials': [self.card(code) for code in entry.get('overlay', [])] if shown else [],
                        'counters': entry.get('counters', []) if shown else [],
                        'equip': entry.get('equip') if shown else None, 'targets': entry.get('targets', []) if shown else []})
            boards.append({'lp': self.lp[player], 'deck': board['deck'], 'field': field,
                'hand': [card(entry) if visible(entry, player, 2) else None for entry in zones['2']],
                'grave': [card(entry) if visible(entry, player, 16) else None for entry in zones['16']],
                'removed': [card(entry) if visible(entry, player, 32) else None for entry in zones['32']],
                'extra': [card(entry) if visible(entry, player, 64) else None for entry in zones['64']]})
        prompt = None
        if self.prompt and self.prompt['owner'] == owner:
            prompt = {key: value for key, value in self.prompt.items() if key != 'choices' and not key.startswith('_')}
            prompt['choices'] = [self.public_choice(choice) for choice in self.prompt['choices']]
        return {'revision': self.revision, 'seat': owner, 'boards': boards, 'turn': self.turn,
            'phase': self.phase, 'turn_number': self.turn_number, 'prompt': prompt,
            'events': self.public_events(owner), 'winner': self.winner, 'ended': self.ended, 'end_reason': self.end_reason}
