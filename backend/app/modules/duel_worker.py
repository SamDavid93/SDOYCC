"""Opt-in development bridge with private WebSockets and immutable deck snapshots."""
import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from app.core.config import settings
from app.modules import duel_worker_state as state
from app.modules.workflow import Auth, Command, Key

ROOT = Path(__file__).resolve().parents[3]
INTEGRATION = ROOT / 'integrations/duel'
router = APIRouter(prefix='/api/duel-zone/worker', tags=['Local duel worker'])
CLOCK_DELIVERY_GRACE = 30.0


def load_module(name):
    spec = importlib.util.spec_from_file_location('sdoycc_worker_' + name, INTEGRATION / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class NativeAdapter:
    def __init__(self, root=None):
        self.root = Path(root) if root else ROOT / 'artifacts/duel-probe'
        load_module('provision').verify(self.root)
        self.process_type = load_module('engine_process').EngineProcess
        self.sandbox = load_module('windows_sandbox').Sandbox(self.root, INTEGRATION / 'core_worker.py')
        self.projection_type = load_module('protocol').Projection
        strings_lock = json.loads((INTEGRATION / 'strings.lock.json').read_text(encoding='utf8'))
        strings = self.root / 'config/strings.conf'
        if hashlib.sha256(strings.read_bytes()).hexdigest() != strings_lock['sha256']: raise ValueError('Unverified system strings')
        self.strings = {}
        for line in strings.read_text(encoding='utf8').splitlines():
            parts = line.split(maxsplit=2)
            if len(parts) == 3 and parts[0] == '!system' and parts[1].isdigit(): self.strings[int(parts[1])] = parts[2]
        self.sources = {'package': json.loads((INTEGRATION / 'sources.lock.json').read_text(encoding='utf8')),
            'strings_sha256': strings_lock['sha256'],
            'cdb_sha256': hashlib.sha256((self.root / 'cards/cards.cdb').read_bytes()).hexdigest(),
            'banlist_sha256': hashlib.sha256((self.root / 'lists/0TCG.lflist.conf').read_bytes()).hexdigest()}
        with sqlite3.connect((self.root / 'cards/cards.cdb').as_uri() + '?mode=ro', uri=True) as db:
            rows = db.execute('SELECT d.id,t.name,t.desc,d.atk,d.def,d.type,d.race,d.attribute,d.setcode,d.alias,' +
                ','.join('t.str' + str(i) for i in range(1, 17)) + ',d.level FROM datas d JOIN texts t ON d.id=t.id '
                '').fetchall()
        self.catalog = {row[0]: dict(zip(('name', 'description', 'atk', 'defense', 'type', 'race', 'attribute', 'setcode', 'alias'), row[1:10]), options=list(row[10:26]), level=row[26] & 255) for row in rows}

    def check(self, snapshot):
        if any(snapshot['sources'].get(key) != value for key, value in self.sources.items()):
            raise HTTPException(409, 'Regelprofil und installierter Worker-Datenstand stimmen nicht überein.')
        for player in snapshot['players']:
            sections = player['sections']
            if (not 40 <= len(sections['main']) <= 60 or len(sections['extra']) > 15 or len(sections['side']) > 15
                    or any(code not in self.catalog for cards in sections.values() for code in cards)):
                raise HTTPException(409, 'Deckbereiche stimmen nicht mit dem geprueften Engine-Datensatz ueberein.')

    def create(self): return self.process_type(self.sandbox.root, self.sandbox), self.projection_type(self.catalog, self.strings)

    def manifest(self):
        return load_module('process_identity').manifest(self.sandbox.root, self.sandbox.script)

    def recover(self, manifest, run_id, instance):
        return load_module('process_identity').recover(manifest, run_id, instance, self.manifest())


@dataclass
class LiveRun:
    engine: object
    projection: object
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seen: dict = field(default_factory=lambda: {0: time.monotonic(), 1: time.monotonic()})
    created: float = field(default_factory=time.monotonic)
    terminal: bool = False
    pending_outcome: tuple | None = None
    history: dict = field(default_factory=lambda: {'0': [], '1': []})
    history_bytes: int = 0
    history_truncated: bool = False
    match: dict | None = None
    engine_seats: list = field(default_factory=lambda: [0, 1])
    clock_remaining: list = field(default_factory=lambda: [360.0, 360.0])
    clock_recovered: list = field(default_factory=lambda: [0.0, 0.0])
    clock_owner: int | None = None
    clock_started: float = field(default_factory=time.monotonic)
    clock_turn: int = 0
    side_started: float | None = None
    practice: bool = False
    bot_task: object | None = None
    clock_decision: tuple | None = None
    clock_ready: bool = False
    clock_grace: float = CLOCK_DELIVERY_GRACE
    clock_waiting_since: float | None = None
    clock_segments: list = field(default_factory=list)
    clock_exhausted_at: float | None = None

    def pause_clock(self, now=None):
        now = max(self.clock_started, time.monotonic() if now is None else now)
        if self.clock_owner is not None:
            owner, other = self.clock_owner, 1 - self.clock_owner
            elapsed = min(self.clock_remaining[owner], max(0, now - self.clock_started))
            self.clock_remaining[owner] = max(0, self.clock_remaining[owner] - elapsed)
            if self.clock_remaining[owner] <= 0 and self.clock_exhausted_at is None:
                self.clock_exhausted_at = self.clock_started + elapsed
            recovered = min(360.0 - self.clock_remaining[other], elapsed * .5)
            self.clock_remaining[other] += recovered
            self.clock_recovered[other] += recovered
            if elapsed:
                self.clock_segments.append((self.clock_started, self.clock_started + elapsed, owner, recovered))
                charged_until = self.clock_started + elapsed
                self.clock_segments = [segment for segment in self.clock_segments if segment[1] > charged_until - CLOCK_DELIVERY_GRACE]
        self.clock_started = now; self.clock_owner = None

    def clear_decision(self, now=None):
        self.pause_clock(now)
        self.clock_decision = None
        self.clock_ready = False
        self.clock_waiting_since = None
        self.clock_segments = []
        self.clock_exhausted_at = None

    def tick_clock(self, now=None):
        now = time.monotonic() if now is None else now
        self.pause_clock(now)
        if self.projection.turn_number != self.clock_turn:
            self.clock_turn = self.projection.turn_number
        prompt = self.projection.prompt
        actionable = (not self.terminal and not self.projection.ended and prompt
            and not prompt.get('_empty_chain') and (not self.match or self.match['phase'] == 'playing'))
        decision = (self.engine_seats[prompt['owner']], prompt['id'], self.projection.revision) if actionable else None
        if decision != self.clock_decision:
            self.clock_decision = decision
            self.clock_ready = bool(decision and self.practice and decision[0] == 1)
            self.clock_grace = CLOCK_DELIVERY_GRACE
            self.clock_waiting_since = now if decision and not self.clock_ready else None
            self.clock_segments = []
            self.clock_exhausted_at = None
        if decision and self.clock_ready: self.clock_owner = decision[0]

    def decision_ready(self, seat, prompt, revision):
        self.tick_clock()
        if self.clock_decision != (seat, prompt, revision):
            raise ValueError('Decision is stale or belongs to another player')
        if not self.clock_ready:
            now = time.monotonic()
            self.clock_grace = max(0, self.clock_grace - max(0, now - self.clock_waiting_since))
            if self.clock_grace <= 0: raise ValueError('Decision delivery timed out')
            self.clock_waiting_since = None
            self.clock_ready = True
            self.clock_started = now
            self.clock_owner = seat
            self.clock_segments = []

    def disconnect_decision(self, seat, confirmed_at=None):
        self.tick_clock()
        if self.clock_decision and self.clock_decision[0] == seat and self.clock_ready:
            if confirmed_at is not None:
                # Socket liveness is observed, not instantaneous. Refund only
                # server-measured unconfirmed time, using the same finite grace
                # as delivery/reconnects. Remove the exact recovery it produced.
                refunded, credited = 0.0, 0.0
                for start, end, owner, recovered in reversed(self.clock_segments):
                    if owner != seat: continue
                    duration = min(max(0, end - max(start, confirmed_at)), max(0, self.clock_grace - refunded))
                    refunded += duration
                    credited += max(0, recovered - max(0, end - start - duration) * .5)
                self.clock_remaining[seat] = min(360, self.clock_remaining[seat] + refunded)
                self.clock_remaining[1 - seat] = max(0, self.clock_remaining[1 - seat] - credited)
                self.clock_recovered[1 - seat] = max(0, self.clock_recovered[1 - seat] - credited)
                self.clock_grace = max(0, self.clock_grace - refunded)
                if self.clock_remaining[seat] > 0: self.clock_exhausted_at = None
            self.clock_ready = False
            self.clock_waiting_since = time.monotonic()
            self.clock_owner = None
            self.clock_segments = []

    def delivery_remaining(self):
        if self.clock_waiting_since is None: return None
        return max(0, self.clock_grace - max(0, time.monotonic() - self.clock_waiting_since))

    def clock(self):
        return {'remaining': [round(value, 1) for value in self.clock_remaining], 'active': self.clock_owner,
            'readiness_required': True,
            'waiting_for': self.clock_decision[0] if self.clock_decision and not self.clock_ready else None,
            'ready_timeout': round(self.delivery_remaining(), 1) if self.clock_waiting_since is not None else None,
            'profile': '360s budget; 50% of opponent decision time recovered, capped at 360s',
            'limit': 360, 'refill_ratio': .5, 'recovered': [round(value, 1) for value in self.clock_recovered],
            'side_remaining': max(0, round(180 - (time.monotonic() - self.side_started), 1)) if self.side_started is not None else None}

    def view(self, seat):
        return self.projection.view(self.engine_seats.index(seat))

    def capture(self):
        if self.history_truncated: return
        frames = {str(seat): copy.deepcopy(self.view(seat)) for seat in (0, 1)}
        if self.match:
            for frame in frames.values(): frame['game'] = self.match['game']
        size = len(json.dumps(frames, ensure_ascii=False).encode('utf8'))
        if self.history_bytes + size > 8 * 1024 * 1024 or len(self.history['0']) >= 1200:
            self.history_truncated = True; return
        self.history_bytes += size
        for seat, frame in frames.items(): self.history[seat].append(frame)


class WorkerService:
    def __init__(self, sessions, adapter):
        self.sessions, self.adapter = sessions, adapter
        self.instance = str(uuid4()); self.runs = {}; self.creation_lock = asyncio.Lock()
        self.sockets = {}
        self.refresh_artwork()

    def refresh_artwork(self):
        if isinstance(self.adapter, NativeAdapter):
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            from app.db.models import Card
            from app.api import translated_text
            from app.modules.duel_rules import canonical
            with self.sessions() as db:
                for card in db.scalars(select(Card).options(joinedload(Card.details)).where(Card.external_provider.in_(['ygoprodeck', 'local-demo']))):
                    code = int(card.external_id) if card.external_id.isdecimal() else None
                    entry = self.adapter.catalog.get(code)
                    if entry and card.image_url and canonical(card.name) == canonical(entry.get('name_en', entry['name'])):
                        entry['image_url'] = '/api/cards/' + str(card.id) + '/art/original'
                        details = card.details
                        entry['fallback_image_url'] = '/api/cards/' + str(card.id) + '/art/de' if details and details.konami_id else None
                        entry.setdefault('name_en', entry['name'])
                        entry.setdefault('description_en', entry.get('description', ''))
                        entry['name'] = (translated_text(details.name_de) if details else None) or entry['name_en']
                        entry['description'] = (translated_text(details.description_de) if details else None) or entry['description_en']

    async def consume_packet(self, live, packet):
        # Only an optional chain with zero legal effects is deterministic.
        # Drain it before resuming either player's decision clock.
        for _ in range(64):
            live.projection.consume(packet)
            prompt = live.projection.prompt
            if live.projection.ended or not prompt or not prompt.get('_empty_chain'):
                return
            response = live.projection.respond(prompt['owner'], prompt['id'], [0])
            packet = await live.engine.command({'op': 'respond', 'response': base64.b64encode(response).decode()})
        raise RuntimeError('Too many consecutive empty chain windows')

    async def database(self, operation, *args):
        def call():
            with self.sessions() as db: return operation(db, *args)
        return await asyncio.to_thread(call)

    async def stop(self, run_id, live, reason, winner=None):
        # No inventory is released unless process termination is confirmed. On a DB
        # error keep this object so watchdog can retry settlement with the stopped core.
        if live.pending_outcome is None: live.pending_outcome = (reason, winner)
        live.clear_decision()
        await live.engine.close()
        replay = {**live.history, 'truncated': live.history_truncated} if live.history['0'] else None
        await self.database(state.finish_stopped, run_id, self.instance, *live.pending_outcome, replay)
        live.terminal = True
        if live.bot_task and live.bot_task is not asyncio.current_task(): live.bot_task.cancel()
        if live.match:
            live.match['phase'] = 'finished' if live.pending_outcome[0] in {'engine', 'surrender', 'decision_timeout', 'sideboard_forfeit'} else 'aborted'
            live.match['winner'] = live.pending_outcome[1]

    async def start(self, lobby_id, version, authorization, key, *, practice=False):
        async with self.creation_lock:
            await asyncio.to_thread(self.refresh_artwork)
            engine, projection = self.adapter.create()  # Constructors never spawn a process.
            manifest = self.adapter.manifest() if hasattr(self.adapter, 'manifest') else None
            # The commit must complete even if the HTTP start request disappears.
            from app.modules.duel_practice import begin as practice_begin
            begin = asyncio.create_task(self.database(practice_begin if practice else state.begin, lobby_id, version, authorization, key, self.instance, self.adapter.check, manifest))
            cancelled = False
            try: run_id, snapshot = await asyncio.shield(begin)
            except asyncio.CancelledError:
                run_id, snapshot = await begin
                cancelled = True
            if snapshot is not None:
                if hasattr(engine, 'bind'): engine.bind(run_id, self.instance)
                live = LiveRun(engine, projection); self.runs[run_id] = live
                live.practice = bool(snapshot.get('practice'))
                if snapshot.get('mode') == 'match':
                    from app.modules.duel_matches import initial
                    live.match = initial(snapshot)
                async with live.lock:
                    try:
                        if cancelled: raise asyncio.CancelledError
                        if live.match: await self.persist_match(run_id, live, live.match)
                        decks = [p['sections'] if p['sections']['extra'] else p['sections']['main'] for p in snapshot['players']]
                        packet = await engine.command({'op': 'start', 'decks': decks, 'flags': 0x30002e800})
                        await self.consume_packet(live, packet)
                        live.tick_clock()
                        live.capture()
                        await self.database(state.activate, run_id, self.instance)
                    except BaseException as error:
                        await asyncio.shield(self.stop(run_id, live, 'worker_failure'))
                        if isinstance(error, asyncio.CancelledError): raise
                        raise HTTPException(503, 'Der Testworker konnte nicht starten. Reservierungen wurden nach dem Prozessstopp freigegeben.')
                if live.practice: live.bot_task = asyncio.create_task(self.bot_loop(run_id,live))
            elif cancelled: raise asyncio.CancelledError
            return await self.view(run_id, authorization)

    async def bot_loop(self, run_id, live):
        from app.modules.duel_practice import answer
        turn, acted, decisions = None, set(), 0
        try:
            while not live.terminal:
                await asyncio.sleep(.55)
                async with live.lock:
                    if live.terminal: return
                    live.seen[1] = time.monotonic()
                    if live.projection.turn_number != turn:
                        turn=live.projection.turn_number;acted.clear();decisions=0
                    prompt=live.projection.prompt
                    if not prompt or live.engine_seats[prompt['owner']] != 1: continue
                    def valid(db):
                        from app.db.models import DuelWorkerRun
                        return state.participants_valid(db,db.get(DuelWorkerRun,run_id))
                    if not await self.database(valid):
                        await self.stop(run_id,live,'session_ended');return
                    await self.check_clock(run_id,live)
                    if live.terminal: return
                    decisions+=1
                    if decisions>200: raise ValueError('Test bot decision limit exceeded')
                    response=answer(live.projection,acted)
                    live.clear_decision()
                    packet=await live.engine.command({'op':'respond','response':base64.b64encode(response).decode()})
                    await self.consume_packet(live,packet)
                    live.tick_clock();live.capture()
                    if live.projection.ended:
                        winner=live.engine_seats[live.projection.winner] if live.projection.winner in (0,1) else None
                        await self.stop(run_id,live,'engine',winner)
        except asyncio.CancelledError:
            raise
        except Exception:
            import logging
            logging.getLogger(__name__).exception('KI-Testduell %s konnte eine Entscheidung nicht ausführen.',run_id)
            async with live.lock:
                if not live.terminal: await self.stop(run_id,live,'worker_failure')

    async def recover_orphans(self, only=None):
        from sqlalchemy import select
        from app.db.models import DuelWorkerRun, DuelWorkerLease
        def candidates(db):
            return [(run.id, run.owner_instance, lease.manifest_json if lease else None)
                for run, lease in db.execute(select(DuelWorkerRun, DuelWorkerLease).outerjoin(
                    DuelWorkerLease, DuelWorkerLease.run_id == DuelWorkerRun.id).where(DuelWorkerRun.state.in_(state.ACTIVE)))]
        outcomes = []
        for run_id, owner, manifest in await self.database(candidates):
            if only is not None and run_id != only: continue
            if owner == self.instance: continue
            try:
                if manifest is None or not hasattr(self.adapter, 'recover'):
                    raise ValueError('Kein nachweisbarer Prozessbeleg vorhanden.')
                stopped = await asyncio.to_thread(self.adapter.recover, json.loads(manifest), run_id, owner)
                if stopped is not True: raise ValueError('Prozessstopp nicht nachgewiesen.')
                await self.database(state.finish_stopped, run_id, owner, 'server_restart')
                outcomes.append({'id': run_id, 'recovered': True})
            except Exception:
                outcomes.append({'id': run_id, 'recovered': False})
        return outcomes

    async def inspect(self, run_id, authorization):
        def read(db):
            row, seat = state.authorize_run(db, run_id, authorization)
            from app.db.models import DuelMatchProgress
            from app.modules.duel_matches import public
            progress = db.get(DuelMatchProgress, run_id)
            receipt = state.public_receipt(row)
            if progress:
                summary = json.loads(progress.progress_json)
                summary['phase'] = 'finished' if row.state == 'finished' else 'aborted' if row.state == 'aborted' else 'playing'
                receipt['match'] = public(summary, seat)
            return receipt, seat, state.participants_valid(db, row), row.owner_instance
        return await self.database(read)

    async def view(self, run_id, authorization, touch=True):
        received = time.monotonic()
        receipt, seat, valid, owner = await self.inspect(run_id, authorization)
        live = self.runs.get(run_id)
        if not live:
            if receipt['state'] in state.ACTIVE:
                return {**receipt, 'state': 'recovery_required', 'seat': seat, 'board': None}
            return {**receipt, 'seat': seat, 'board': None}
        async with live.lock:
            receipt, seat, valid, owner = await self.inspect(run_id, authorization)
            previous_state = receipt['state']
            if touch: live.seen[seat] = max(live.seen[seat], received)
            if valid and not live.terminal: await self.check_clock(run_id, live)
            if live.pending_outcome and not live.terminal:
                await self.stop(run_id, live, *live.pending_outcome)
                receipt, seat, valid, owner = await self.inspect(run_id, authorization)
            if not valid and not live.terminal:
                await self.stop(run_id, live, 'session_ended')
                receipt, seat, _, _ = await self.inspect(run_id, authorization)
            from app.modules.duel_matches import public
            if previous_state in state.ACTIVE and live.terminal:
                receipt, seat, valid, owner = await self.inspect(run_id, authorization)
            return {**receipt, 'seat': seat, 'clock': live.clock(), 'board': live.view(seat) if receipt['state'] != 'aborted' else None,
                'match': public(live.match, seat, self.adapter.catalog) if live.match and hasattr(self.adapter, 'catalog') else public(live.match, seat) if live.match else None}

    async def decision_ready(self, run_id, authorization, prompt, revision, socket):
        received = time.monotonic()
        live = self.runs.get(run_id)
        if not live: raise HTTPException(409, 'Duellworker ist nicht verfuegbar.')
        async with live.lock:
            _, seat, valid, _ = await self.inspect(run_id, authorization)
            if self.sockets.get((run_id, seat)) is not socket: raise HTTPException(409, 'Diese Duellverbindung ist nicht mehr aktuell.')
            live.seen[seat] = max(live.seen[seat], received)
            if not valid and not live.terminal: await self.stop(run_id, live, 'session_ended')
            if not live.terminal: await self.check_clock(run_id, live)
            if not live.terminal:
                try: live.decision_ready(seat, prompt, revision)
                except (ValueError, TypeError): raise HTTPException(409, 'Die Entscheidung ist veraltet oder gehoert zum anderen Spieler.')
                live.seen[seat] = time.monotonic()
        return await self.view(run_id, authorization, touch=False)

    async def disconnect(self, run_id, seat, socket, confirmed_at=None):
        live = self.runs.get(run_id)
        if not live: return
        async with live.lock:
            if self.sockets.get((run_id, seat)) is socket and not live.terminal:
                live.disconnect_decision(seat, confirmed_at)

    async def act(self, run_id, authorization, prompt=None, selected=None, surrender=False, cancel=False):
        received = time.monotonic()
        live = self.runs.get(run_id)
        if not live: raise HTTPException(409, 'Worker nicht verfügbar. Keine neue Aktion möglich.')
        async with live.lock:
            # Recheck AFTER waiting for a preceding command or an administrator reset.
            receipt, seat, valid, owner = await self.inspect(run_id, authorization)
            live.seen[seat] = max(live.seen[seat], received)
            if valid and not live.terminal: await self.check_clock(run_id, live, now=received)
            if live.pending_outcome and not live.terminal: await self.stop(run_id, live, *live.pending_outcome)
            elif not valid and not live.terminal: await self.stop(run_id, live, 'session_ended')
            elif not live.terminal:
                live.seen[seat] = time.monotonic()
                if surrender:
                    live.clear_decision(now=received)
                    await live.engine.close()
                    live.projection.surrender(live.engine_seats.index(seat))
                    live.capture()
                    await self.stop(run_id, live, 'surrender', 1 - seat)
                else:
                    if live.match and live.match['phase'] != 'playing': raise HTTPException(409, 'Zwischen den Spielen ist keine Engine-Antwort moeglich.')
                    try: response = live.projection.respond(live.engine_seats.index(seat), prompt, selected, cancel)
                    except (ValueError, TypeError): raise HTTPException(409, 'Ungültige, fremde oder veraltete Entscheidung.')
                    try:
                        # Debit only until the command reached the server. Database,
                        # engine and delivery work are never player thinking time.
                        live.clear_decision(now=received)
                        packet = await live.engine.command({'op': 'respond', 'response': base64.b64encode(response).decode()})
                        await self.consume_packet(live, packet)
                        live.tick_clock()
                        live.capture()
                        if live.projection.ended:
                            winner = live.engine_seats[live.projection.winner] if live.projection.winner in (0, 1) else None
                            if live.match: await self.game_ended(run_id, live, winner)
                            else: await self.stop(run_id, live, 'engine', winner)
                    except BaseException as error:
                        await asyncio.shield(self.stop(run_id, live, 'worker_failure'))
                        if isinstance(error, asyncio.CancelledError): raise
            # Terminal commands never change an already recorded result.
        return await self.view(run_id, authorization)

    async def sweep(self):
        failures = []
        for run_id, live in list(self.runs.items()):
            if live.terminal:
                if time.monotonic() - max(live.seen.values()) > 120: self.runs.pop(run_id, None)
                continue
            try:
                async with live.lock:
                    def valid(db):
                        from app.db.models import DuelWorkerRun
                        return state.participants_valid(db, db.get(DuelWorkerRun, run_id))
                    if live.pending_outcome: await self.stop(run_id, live, *live.pending_outcome)
                    elif not await self.database(valid): await self.stop(run_id, live, 'session_ended')
                    elif time.monotonic() - min(live.seen.values()) > 60 or time.monotonic() - live.created > 3600:
                        await self.stop(run_id, live, 'timeout')
                    else: await self.check_clock(run_id, live)
            except Exception as error:
                failures.append(error)
        if failures: raise failures[0]

    async def game_ended(self, run_id, live, winner, reason='engine'):
        from app.modules.duel_matches import record_game
        await live.engine.close()
        live.clear_decision()
        progress = record_game(live.match, winner)
        progress['results'][-1]['reason'] = reason
        if getattr(live.projection, 'match_kill', False) and winner is not None:
            progress['phase'] = 'finished'; progress['match_kill'] = True
        await self.persist_match(run_id, live, progress)
        live.side_started = time.monotonic() if progress['phase'] == 'sideboarding' else None
        if progress['phase'] == 'finished': await self.stop(run_id, live, reason, winner)

    async def check_clock(self, run_id, live, now=None):
        live.tick_clock(now)
        exhausted = live.clock_owner
        # A half-open connection can cross zero before its loss is detected.
        # Require server-observed client activity after that crossing before
        # scoring a loss; otherwise disconnect settlement can refund the gap.
        # Even an invalid frame proves liveness, so it cannot stall this check.
        confirmed = (exhausted is not None and ((live.practice and exhausted == 1)
            or live.seen[exhausted] >= (live.clock_exhausted_at if live.clock_exhausted_at is not None else time.monotonic())))
        if exhausted is not None and live.clock_remaining[exhausted] <= 0 and confirmed:
            loser = live.clock_owner
            await live.engine.close(); live.projection.surrender(live.engine_seats.index(loser)); live.capture()
            if live.match: await self.game_ended(run_id, live, 1 - loser, 'decision_timeout')
            else: await self.stop(run_id, live, 'decision_timeout', 1 - loser)
        elif live.clock_waiting_since is not None and live.delivery_remaining() <= 0:
            # A missing UI/delivery acknowledgement is a transport failure, not
            # thinking time. Reconnects share the prompt's remaining grace.
            await self.stop(run_id, live, 'timeout')
        elif live.side_started is not None and time.monotonic() - live.side_started >= 180:
            ready = live.match['ready']
            winner = ready.index(True) if ready.count(True) == 1 else None
            await self.stop(run_id, live, 'sideboard_forfeit' if winner is not None else 'sideboard_timeout', winner)

    async def sideboard(self, run_id, authorization, body):
        from app.modules.duel_matches import sideboard
        _, seat, _, _ = await self.inspect(run_id, authorization)
        live = self.runs.get(run_id)
        if not live: raise HTTPException(409, 'Match nicht verfuegbar.')
        async with live.lock:
            _, seat, valid, _ = await self.inspect(run_id, authorization)
            if valid and not live.terminal: await self.check_clock(run_id, live)
            if not valid:
                await self.stop(run_id, live, 'session_ended')
                raise HTTPException(409, 'Match-Anmeldung beendet.')
            if live.terminal or not live.match or live.match['phase'] != 'sideboarding' or live.match['version'] != body.version:
                raise HTTPException(409, 'Side-Deck-Stand ist veraltet oder das Spiel laeuft bereits.')
            progress = copy.deepcopy(live.match)
            try: progress['decks'][seat] = sideboard(progress, seat, body.sections, self.adapter.catalog)
            except (ValueError, KeyError, TypeError): raise HTTPException(409, 'Nur die reservierte Kartenmenge und die urspruenglichen Bereichsgroessen sind erlaubt.')
            if body.starter is not None:
                if seat != progress['chooser']: raise HTTPException(403, 'Nur der berechtigte Spieler waehlt den naechsten Startspieler.')
                progress['next_starter'] = body.starter
            if body.ready and seat == progress['chooser'] and progress['next_starter'] is None:
                raise HTTPException(409, 'Waehle zuerst, wer das naechste Spiel beginnt.')
            progress['ready'][seat] = body.ready
            progress['version'] += 1
            await self.persist_match(run_id, live, progress)
            live.seen[seat] = time.monotonic()
            if all(progress['ready']) and progress['next_starter'] is not None:
                try:
                    starter = progress['next_starter']
                    live.engine_seats = [starter, 1 - starter]
                    old_revision, old_sequence = live.projection.revision, live.projection.event_sequence
                    _, live.projection = self.adapter.create()
                    live.projection.revision = old_revision; live.projection.event_sequence = old_sequence
                    progress['game'] += 1; progress['phase'] = 'playing'; progress['starter'] = starter
                    live.side_started = None
                    live.clock_remaining = [360.0, 360.0]; live.clock_recovered = [0.0, 0.0]; live.clock_turn = 0
                    packet = await live.engine.command({'op': 'start', 'decks': [progress['decks'][player] for player in live.engine_seats], 'flags': 0x30002e800})
                    await self.consume_packet(live, packet)
                    live.tick_clock()
                    await self.persist_match(run_id, live, progress)
                    live.capture()
                except BaseException as error:
                    await asyncio.shield(self.stop(run_id, live, 'worker_failure'))
                    if isinstance(error, asyncio.CancelledError): raise
        return await self.view(run_id, authorization)

    async def persist_match(self, run_id, live, progress):
        from app.modules.duel_matches import save
        pending = asyncio.create_task(self.database(save, run_id, self.instance, progress))
        try: await asyncio.shield(pending)
        except asyncio.CancelledError:
            await pending
            live.match = progress
            await asyncio.shield(self.stop(run_id, live, 'worker_failure'))
            raise
        live.match = progress

    async def watchdog(self):
        import logging
        while True:
            await asyncio.sleep(5)
            try: await self.sweep()
            except Exception: logging.getLogger(__name__).error('Duellworker-Bereinigung fehlgeschlagen; Reservierungen bleiben geschützt.')

    async def close(self):
        failures = []
        for run_id, live in list(self.runs.items()):
            try:
                async with live.lock:
                    if not live.terminal: await self.stop(run_id, live, 'shutdown')
            except Exception as error:
                failures.append(error)
        if failures: raise failures[0]


def service(request):
    runtime = getattr(request.app.state, 'duel_worker', None)
    if not settings.duel_worker_enabled or runtime is None: raise HTTPException(404, 'Duellworker ist nicht aktiviert.')
    return runtime


class Start(Command):
    lobby_id: str = Field(min_length=36, max_length=36)
    version: int = Field(ge=1, strict=True)


class PracticeStart(Command):
    deck_id: str = Field(min_length=36,max_length=36)


class Answer(Command):
    prompt: int = Field(ge=1, strict=True)
    selected: list[Annotated[int, Field(strict=True, ge=0)]] = Field(max_length=100)
    cancel: bool = Field(default=False, strict=True)


class DecisionReady(Command):
    prompt: int = Field(ge=1, strict=True)
    revision: int = Field(ge=1, strict=True)


class Consent(Start):
    consent: bool = Field(strict=True)


class Surrender(Command):
    pass


class Sideboard(Command):
    version: int = Field(ge=1, strict=True)
    sections: dict[str, Annotated[list[Annotated[int, Field(strict=True, ge=1, le=0xffffffff)]], Field(max_length=60)]] = Field(max_length=3)
    ready: bool = Field(strict=True)
    starter: Annotated[int, Field(strict=True, ge=0, le=1)] | None = None


@router.post('/runs/{run_id}/sideboard')
async def submit_sideboard(run_id: str, body: Sideboard, request: Request, authorization: Auth = None):
    return await service(request).sideboard(run_id, authorization, body)


@router.post('/start')
async def start(body: Start, request: Request, authorization: Auth = None, idempotency_key: Key = None):
    return await service(request).start(body.lobby_id, body.version, authorization, idempotency_key)


@router.post('/practice')
async def practice(body: PracticeStart, request: Request, authorization: Auth = None, idempotency_key: Key = None):
    return await service(request).start(body.deck_id,1,authorization,idempotency_key,practice=True)


@router.post('/consent')
async def consent(body: Consent, request: Request, authorization: Auth = None, idempotency_key: Key = None):
    return await service(request).database(state.consent, body.lobby_id, body.version, body.consent, authorization, idempotency_key)


@router.get('/runs/{run_id}')
async def view(run_id: str, request: Request, authorization: Auth = None):
    return await service(request).view(run_id, authorization)


@router.post('/runs/{run_id}/answer')
async def answer(run_id: str, body: Answer, request: Request, authorization: Auth = None):
    return await service(request).act(run_id, authorization, body.prompt, body.selected, cancel=body.cancel)


@router.post('/runs/{run_id}/surrender')
async def surrender(run_id: str, body: Surrender, request: Request, authorization: Auth = None):
    return await service(request).act(run_id, authorization, surrender=True)
