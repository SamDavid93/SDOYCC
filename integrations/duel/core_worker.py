"""Isolated EDOPro API 11 worker. Internal JSON-lines IPC; never expose publicly.

ABI reference: edo9300/ygopro-core ocgapi.h / ocgapi_types.h, commit
38d04c9feb1a26617407091380634c87262fe3f8 (AGPL-3.0-or-later).
The DLL and trusted card scripts run only in this disposable child process.
"""
import base64
import ctypes as C
import json
import os
import random
from pathlib import Path
import sqlite3
import struct
import sys


class CardData(C.Structure):
    _fields_ = [('code', C.c_uint32), ('alias', C.c_uint32), ('setcodes', C.POINTER(C.c_uint16)),
                ('type', C.c_uint32), ('level', C.c_uint32), ('attribute', C.c_uint32),
                ('race', C.c_uint64), ('attack', C.c_int32), ('defense', C.c_int32),
                ('lscale', C.c_uint32), ('rscale', C.c_uint32), ('link_marker', C.c_uint32)]


class Player(C.Structure):
    _fields_ = [('lp', C.c_uint32), ('hand', C.c_uint32), ('draw', C.c_uint32)]


ReadCard = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.POINTER(CardData))
ReadScript = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_char_p)
Log = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p, C.c_int)
ReadDone = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(CardData))


class Options(C.Structure):
    _fields_ = [('seed', C.c_uint64 * 4), ('flags', C.c_uint64), ('p0', Player), ('p1', Player),
                ('reader', ReadCard), ('payload1', C.c_void_p), ('scripts', ReadScript),
                ('payload2', C.c_void_p), ('log', Log), ('payload3', C.c_void_p),
                ('done', ReadDone), ('payload4', C.c_void_p), ('unsafe', C.c_uint8)]


class NewCard(C.Structure):
    _fields_ = [('team', C.c_uint8), ('duelist', C.c_uint8), ('code', C.c_uint32),
                ('controller', C.c_uint8), ('location', C.c_uint32), ('sequence', C.c_uint32),
                ('position', C.c_uint32)]


class QueryInfo(C.Structure):
    _fields_ = [('flags', C.c_uint32), ('controller', C.c_uint8), ('location', C.c_uint32),
                ('sequence', C.c_uint32), ('overlay_sequence', C.c_uint32)]


def decode_queries(raw):
    """Full non-cache API 11 query stream; never sent directly to a browser."""
    if len(raw) < 4 or struct.unpack_from('<I', raw)[0] != len(raw) - 4:
        raise ValueError('Invalid query stream length')
    offset, result = 4, []
    scalar = {1: ('code', 'I'), 2: ('position', 'I'), 0x10: ('level', 'I'), 0x20: ('rank', 'I'),
        0x100: ('atk', 'i'), 0x200: ('defense', 'i'), 0x100000: ('public', 'B'),
        0x200000: ('lscale', 'I'), 0x400000: ('rscale', 'I'), 0x1000000: ('hidden', 'B')}
    while offset < len(raw):
        card = {}
        for _ in range(64):
            if offset + 2 > len(raw): raise ValueError('Truncated query')
            size = struct.unpack_from('<H', raw, offset)[0]; offset += 2
            if size == 0: card = None; break
            if size < 4 or offset + size > len(raw): raise ValueError('Invalid query field')
            flag = struct.unpack_from('<I', raw, offset)[0]
            payload = raw[offset+4:offset+size]; offset += size
            if flag == 0x80000000:
                if payload: raise ValueError('Invalid query terminator')
                break
            if flag in scalar:
                key, fmt = scalar[flag]
                if len(payload) != struct.calcsize('<' + fmt): raise ValueError('Invalid query scalar')
                card[key] = struct.unpack('<' + fmt, payload)[0]
            elif flag in (0x10000, 0x20000):
                if len(payload) < 4: raise ValueError('Invalid query vector')
                count = struct.unpack_from('<I', payload)[0]
                if count > 200 or len(payload) != 4 + 4 * count: raise ValueError('Invalid query vector count')
                card['overlay' if flag == 0x10000 else 'counters'] = list(struct.unpack('<' + 'I' * count, payload[4:]))
            elif flag == 0x800000:
                if len(payload) != 8: raise ValueError('Invalid Link query')
                card['link'], card['link_marker'] = struct.unpack('<II', payload)
            elif flag == 0x4000:
                if len(payload) != 10: raise ValueError('Invalid equip query')
                owner, zone, sequence, position = struct.unpack('<BBII', payload)
                card['equip'] = {'owner': owner, 'zone': zone, 'sequence': sequence, 'position': position}
            elif flag == 0x8000:
                if len(payload) < 4: raise ValueError('Invalid target query')
                count = struct.unpack_from('<I', payload)[0]
                if count > 200 or len(payload) != 4 + 10 * count: raise ValueError('Invalid target query count')
                card['targets'] = [dict(zip(('owner', 'zone', 'sequence', 'position'), struct.unpack_from('<BBII', payload, 4 + 10 * i))) for i in range(count)]
        else: raise ValueError('Query field limit')
        result.append(card)
        if len(result) > 200: raise ValueError('Query card limit')
    return result


class Core:
    def __init__(self, root):
        # The supervisor resolves and verifies this absolute path before spawn.
        # AppContainer intentionally denies the volume queries used by resolve().
        self.root = Path(root)
        if not self.root.is_absolute() or '..' in self.root.parts:
            raise ValueError('Worker runtime path must be absolute')
        self.lib = C.CDLL(str(self.root / 'ocgcore.dll'))
        signatures = {
            'OCG_GetVersion': ([C.POINTER(C.c_int), C.POINTER(C.c_int)], None),
            'OCG_CreateDuel': ([C.POINTER(C.c_void_p), C.POINTER(Options)], C.c_int),
            'OCG_DestroyDuel': ([C.c_void_p], None),
            'OCG_LoadScript': ([C.c_void_p, C.c_char_p, C.c_uint32, C.c_char_p], C.c_int),
            'OCG_DuelNewCard': ([C.c_void_p, C.POINTER(NewCard)], None),
            'OCG_StartDuel': ([C.c_void_p], None),
            'OCG_DuelProcess': ([C.c_void_p], C.c_int),
            'OCG_DuelGetMessage': ([C.c_void_p, C.POINTER(C.c_uint32)], C.c_void_p),
            'OCG_DuelSetResponse': ([C.c_void_p, C.c_char_p, C.c_uint32], None),
            'OCG_DuelQueryCount': ([C.c_void_p, C.c_uint8, C.c_uint32], C.c_uint32),
            'OCG_DuelQueryLocation': ([C.c_void_p, C.POINTER(C.c_uint32), C.POINTER(QueryInfo)], C.c_void_p),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, name); fn.argtypes = args; fn.restype = result
        major, minor = C.c_int(), C.c_int()
        self.lib.OCG_GetVersion(C.byref(major), C.byref(minor))
        self.version = (major.value, minor.value)
        if self.version != (11, 0):
            raise ValueError('Unsupported core ABI')
        self.db = sqlite3.connect((self.root / 'cards/cards.cdb').as_uri() + '?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.setcodes = {}
        self.script_paths = {p.name: p for p in (self.root / 'scripts').rglob('*.lua')}
        self.errors = []
        self.duel = C.c_void_p()
        self.reader = ReadCard(self.read_card)
        self.scripts = ReadScript(self.read_script)
        self.logger = Log(self.log)
        self.done = ReadDone(lambda payload, data: None)

    def read_card(self, payload, code, data):
        try:
            row = self.db.execute('SELECT * FROM datas WHERE id=?', (code,)).fetchone()
            if row is None:
                raise ValueError('Unknown engine card')
            packed = row['setcode'] & ((1 << 64) - 1)
            values = [(packed >> offset) & 65535 for offset in range(0, 64, 16)]
            self.setcodes.setdefault(code, (C.c_uint16 * 5)(*values, 0))
            data[0] = CardData(code, row['alias'], self.setcodes[code], row['type'], row['level'] & 255,
                               row['attribute'], row['race'], row['atk'], row['def'],
                               (row['level'] >> 24) & 255, (row['level'] >> 16) & 255,
                               row['def'] if row['type'] & 0x4000000 else 0)
        except Exception as error:
            self.errors.append(type(error).__name__ + ': card data unavailable')

    def read_script(self, payload, duel, name):
        try:
            path = self.script_paths.get(name.decode('utf8'))
            if path is None:
                return 0
            script = path.read_bytes()
            return self.lib.OCG_LoadScript(duel, script, len(script), name)
        except Exception:
            self.errors.append('Script could not be loaded')
            return 0

    def log(self, payload, message, kind):
        if kind == 0:
            self.errors.append(message.decode('utf8', errors='replace')[:500])

    def start(self, decks, flags):
        if self.duel.value:
            raise ValueError('Duel already running')
        if len(decks) != 2:
            raise ValueError('Invalid decks')
        decks = [deck if isinstance(deck, dict) else {'main': deck, 'extra': []} for deck in decks]
        if any(not isinstance(deck.get('main'), list) or not isinstance(deck.get('extra'), list)
               or not 40 <= len(deck['main']) <= 60 or len(deck['extra']) > 15
               or any(type(code) is not int or not 0 < code < 2147483648 for code in deck['main'] + deck['extra']) for deck in decks):
            raise ValueError('Invalid engine deck sections')
        options = Options((C.c_uint64 * 4)(*struct.unpack('<4Q', os.urandom(32))), flags,
                          Player(8000, 5, 1), Player(8000, 5, 1), self.reader, None,
                          self.scripts, None, self.logger, None, self.done, None, 0)
        status = self.lib.OCG_CreateDuel(C.byref(self.duel), C.byref(options))
        if status != 0:
            raise RuntimeError('Core creation failed: ' + str(status))
        for name in [b'constant.lua', b'utility.lua']:
            if not self.read_script(None, self.duel, name):
                raise RuntimeError('Missing bootstrap scripts')
        for owner, deck in enumerate(decks):
            shuffled = list(deck['main'])
            random.SystemRandom().shuffle(shuffled)
            for code in shuffled:
                self.lib.OCG_DuelNewCard(self.duel, C.byref(NewCard(owner, 0, code, owner, 1, 0, 8)))
            for code in deck['extra']:
                self.lib.OCG_DuelNewCard(self.duel, C.byref(NewCard(owner, 0, code, owner, 64, 0, 8)))
        self.lib.OCG_StartDuel(self.duel)
        return self.process()

    def process(self):
        messages = []
        for _ in range(1000):
            status = self.lib.OCG_DuelProcess(self.duel)
            size = C.c_uint32()
            pointer = self.lib.OCG_DuelGetMessage(self.duel, C.byref(size))
            if size.value > 8 * 1024 * 1024:
                raise RuntimeError('Engine message limit')
            raw = C.string_at(pointer, size.value)
            offset = 0
            while offset < len(raw):
                length = struct.unpack_from('<I', raw, offset)[0]; offset += 4
                if not 1 <= length <= len(raw) - offset:
                    raise RuntimeError('Invalid frame')
                messages.append(base64.b64encode(raw[offset:offset + length]).decode('ascii'))
                offset += length
            if self.errors:
                raise RuntimeError('; '.join(self.errors))
            if status != 2:
                return {'version': self.version, 'status': status, 'messages': messages, 'query_boards': self.query_boards()}
        raise RuntimeError('Engine processing limit')

    def query_boards(self):
        boards = []
        flags = 1 | 2 | 0x10 | 0x20 | 0x100 | 0x200 | 0x4000 | 0x8000 | 0x10000 | 0x20000 | 0x100000 | 0x200000 | 0x400000 | 0x800000 | 0x1000000
        for owner in (0, 1):
            board = {'deck': self.lib.OCG_DuelQueryCount(self.duel, owner, 1), 'zones': {}}
            for zone in (2, 4, 8, 16, 32, 64):
                size = C.c_uint32()
                info = QueryInfo(flags, owner, zone, 0, 0)
                pointer = self.lib.OCG_DuelQueryLocation(self.duel, C.byref(size), C.byref(info))
                if not pointer or size.value > 1024 * 1024: raise ValueError('Invalid board query')
                board['zones'][str(zone)] = decode_queries(C.string_at(pointer, size.value))
            boards.append(board)
        return boards

    def respond(self, value):
        if not self.duel.value:
            raise ValueError('No active duel')
        response = base64.b64decode(value, validate=True)
        if not 1 <= len(response) <= 1024:
            raise ValueError('Invalid response size')
        self.lib.OCG_DuelSetResponse(self.duel, response, len(response))
        return self.process()

    def close(self):
        if self.duel.value:
            self.lib.OCG_DestroyDuel(self.duel)
            self.duel = C.c_void_p()
        self.db.close()


def main():
    core = Core(sys.argv[1])
    try:
        for line in sys.stdin:
            try:
                if len(line) > 65536:
                    raise ValueError('Command too large')
                command = json.loads(line)
                if command['op'] == 'start':
                    result = core.start(command['decks'], command['flags'])
                elif command['op'] == 'respond':
                    result = core.respond(command['response'])
                elif command['op'] == 'version':
                    result = {'version': core.version}
                else:
                    raise ValueError('Unknown operation')
                print(json.dumps(result), flush=True)
            except Exception as error:
                print(json.dumps({'error': str(error)}), flush=True)
                break  # fail closed; a damaged worker is never reused
    finally:
        core.close()


if __name__ == '__main__':
    main()
