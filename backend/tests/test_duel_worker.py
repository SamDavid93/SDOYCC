import asyncio
import base64
import json
import struct
import time
from contextlib import asynccontextmanager
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import delete, func, select

from app.core.auth import create_session
from app.core.config import settings
from app.db.models import AuthSession, DuelWorkerConsent, DuelWorkerRun, DuelWorkerLease, User, VariantInventory
from app.main import app
from app.modules import duel_worker_state
from app.modules.duel_worker import LiveRun, NativeAdapter, WorkerService, load_module
from test_duel_preparation import PreparationFixture


def packet(*messages, status=1):
    return {'version': [11, 0], 'status': status, 'messages': [base64.b64encode(m).decode() for m in messages]}


def prompt(owner):
    return struct.pack('<BB6IBBB', 11, owner, 0, 0, 0, 0, 0, 0, 0, 1, 0)


class FakeEngine:
    def __init__(self): self.commands = []; self.closed = False; self.fail_start = False; self.fail_answer = False; self.fail_close = False
    async def command(self, command):
        self.commands.append(command)
        if command['op'] == 'start':
            if self.fail_start: raise RuntimeError('isolated start failure')
            return packet(struct.pack('<BBIII', 90, 0, 1, 10001, 1), struct.pack('<BBIII', 90, 1, 1, 10002, 1), prompt(0))
        if self.fail_answer: raise RuntimeError('isolated response failure')
        return packet(prompt(1))
    async def close(self):
        if self.fail_close: raise RuntimeError('isolated process stop failure')
        self.closed = True


class FakeAdapter:
    def __init__(self): self.engines = []; self.reject = False; self.fail_start = False
    def check(self, snapshot):
        if self.reject: raise HTTPException(409, 'Unsupported test pool')
    def create(self):
        engine = FakeEngine(); engine.fail_start = self.fail_start; self.engines.append(engine)
        return engine, load_module('protocol').Projection({10001: {'name': 'Private first card'}, 10002: {'name': 'Private second card'}})


class WorkerTests(PreparationFixture):
    def setUp(self):
        super().setUp()
        self.adapter = FakeAdapter(); self.runtime = WorkerService(self.sessions, self.adapter)
        self.previous_flag = settings.enable_duel_worker_lab
        self.previous_alpha = settings.enable_duel_alpha
        settings.enable_duel_alpha = False
        self.previous_runtime = getattr(app.state, 'duel_worker', None)
        settings.enable_duel_worker_lab = True; app.state.duel_worker = self.runtime
        for headers in (self.headers, self.other_headers):
            response = self.client.post('/api/duel-zone/worker/consent', json={'lobby_id': self.room['id'], 'version': self.room['version'], 'consent': True},
                headers={**headers, 'Idempotency-Key': str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text); self.room = response.json()
        # A real ASGI server uses one loop. Keep both test WebSockets on one
        # portal as well; separate TestClient portals cannot share asyncio locks.
        @asynccontextmanager
        async def fixture_lifespan(_app): yield
        self.lifespan_patch = patch.object(app.router, 'lifespan_context', fixture_lifespan)
        self.lifespan_patch.start(); self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None); self.lifespan_patch.stop()
        for engine in self.adapter.engines: engine.fail_close = False
        asyncio.run(self.runtime.close())
        app.state.duel_worker = self.previous_runtime; settings.enable_duel_worker_lab = self.previous_flag
        settings.enable_duel_alpha = self.previous_alpha
        super().tearDown()

    def start_worker(self):
        return self.client.post('/api/duel-zone/worker/start', json={'lobby_id': self.room['id'], 'version': self.room['version']},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())})

    def select_ready_decks(self):
        for deck, headers in zip(self.decks, (self.headers, self.other_headers)):
            response = self.client.post(f'/api/duel-zone/lobbies/{self.room["id"]}/deck',
                json={'version': self.room['version'], 'deck_id': deck['id'], 'ready': True},
                headers={**headers, 'Idempotency-Key': str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            self.room = response.json()

    def test_deck_selection_starts_directly_without_separate_confirmation_calls(self):
        self.select_ready_decks()
        self.assertTrue(self.room['can_start'])
        self.assertTrue(all(member['deck_ready'] for member in self.room['members']))
        self.assertEqual(self.total(), 0)
        response = self.start_worker()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['state'], 'running')
        self.assertEqual(self.total(), 86)

    def test_deselecting_deck_blocks_start_and_preserves_other_players_choice(self):
        self.select_ready_decks()
        response = self.client.post(f'/api/duel-zone/lobbies/{self.room["id"]}/deck',
            json={'version': self.room['version'], 'deck_id': None, 'ready': False},
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.room = response.json()
        self.assertFalse(self.room['can_start'])
        self.assertTrue(self.room['members'][0]['deck_ready'])
        self.assertFalse(self.room['members'][1]['deck_ready'])
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)
        self.select_ready_decks()
        self.assertEqual(self.start_worker().status_code, 200)

    def test_ready_selection_requires_original_session_and_current_deck_version(self):
        self.select_ready_decks()
        with self.sessions() as db:
            other_session = {'Authorization': 'Bearer ' + create_session(db, db.get(User, 2))}
            from app.db.models import PlayerDeck
            db.get(PlayerDeck, self.decks[1]['id']).version += 1
            db.commit()
        response = self.client.post(f'/api/duel-zone/lobbies/{self.room["id"]}/deck',
            json={'version': self.room['version'], 'deck_id': self.decks[1]['id'], 'ready': True},
            headers={**other_session, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)

    def test_ready_selection_does_not_bypass_changed_stock_or_profile_approval(self):
        self.select_ready_decks()
        with self.sessions() as db:
            from app.db.models import DuelRuleProfile
            db.get(DuelRuleProfile, self.profile).region_approved = False
            db.commit()
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)
        with self.sessions() as db:
            db.get(DuelRuleProfile, self.profile).region_approved = True
            stock = db.scalar(select(VariantInventory).where(VariantInventory.user_id == 2, VariantInventory.quantity > 0))
            stock.quantity = 0
            db.commit()
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)

    def get_run(self, run_id, headers=None):
        return self.client.get('/api/duel-zone/worker/runs/' + run_id, headers=headers or self.headers)

    def test_start_uses_snapshot_and_only_original_two_sessions_get_private_views(self):
        response = self.start_worker(); self.assertEqual(response.status_code, 200, response.text)
        result = response.json(); self.assertEqual(result['state'], 'running')
        self.assertEqual(self.total(), 86)
        self.assertEqual({key: len(cards) for key, cards in self.adapter.engines[0].commands[0]['decks'][0].items()}, {'main': 40, 'extra': 1, 'side': 2})
        self.assertEqual(result['board']['boards'][1]['hand'], [None])
        guest = self.get_run(result['id'], self.other_headers)
        self.assertNotIn('Private first card', guest.text)
        self.assertIsNone(guest.json()['board']['prompt'])
        self.assertNotIn('session_hash', response.text)
        self.assertNotIn('_response', response.text)
        with self.sessions() as db:
            token = create_session(db, db.get(User, 1))
            outsider = User(username='outsider', display_name='Outsider', credits=0)
            db.add(outsider); db.flush(); stranger = create_session(db, outsider); db.commit()
        self.assertEqual(self.get_run(result['id'], {'Authorization': 'Bearer ' + token}).status_code, 403)
        self.assertEqual(self.get_run(result['id'], {'Authorization': 'Bearer ' + stranger}).status_code, 404)
        self.assertEqual(self.client.get('/api/duel-zone/worker/runs/' + result['id']).status_code, 401)
        self.assertEqual(self.start_worker().json()['id'], result['id'])
        self.assertEqual(sum(bool(e.commands) for e in self.adapter.engines), 1)

    def test_failed_start_and_unsupported_pool_leave_no_reservations(self):
        self.adapter.reject = True
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)
        with self.sessions() as db: self.assertEqual(db.scalar(select(func.count(DuelWorkerRun.id))), 0)
        self.adapter.reject = False; self.adapter.fail_start = True
        self.assertEqual(self.start_worker().status_code, 503)
        self.assertTrue(self.adapter.engines[-1].closed); self.assertEqual(self.total(), 0)
        with self.sessions() as db: self.assertEqual(db.scalar(select(DuelWorkerRun)).state, 'aborted')

    def test_foreign_and_duplicate_answers_cannot_advance_engine_twice(self):
        result = self.start_worker().json(); run_id = result['id']; prompt_id = result['board']['prompt']['id']
        path = f'/api/duel-zone/worker/runs/{run_id}/answer'
        body = {'prompt': prompt_id, 'selected': [0]}
        self.assertEqual(self.client.post(path, json=body, headers=self.other_headers).status_code, 409)
        self.assertEqual(self.client.post(path, json={'prompt': prompt_id, 'selected': [True]}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post(path, json=body, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post(path, json=body, headers=self.headers).status_code, 409)
        self.assertEqual(len(self.adapter.engines[0].commands), 2)

    def test_surrender_uses_authenticated_seat_and_settles_once_after_stop(self):
        run_id = self.start_worker().json()['id']; path = f'/api/duel-zone/worker/runs/{run_id}/surrender'
        self.assertEqual(self.client.post(path, json={'winner': 1}, headers=self.other_headers).status_code, 422)
        result = self.client.post(path, json={}, headers=self.other_headers).json()
        self.assertEqual(result['state'], 'finished'); self.assertEqual(result['winner_seat'], 0)
        self.assertEqual(result['reason'], 'surrender'); self.assertTrue(self.adapter.engines[0].closed)
        self.assertEqual(self.total(), 0)
        again = self.client.post(path, json={}, headers=self.headers).json()
        self.assertEqual(again['winner_seat'], 0)
        self.assertIsNone(self.client.get('/api/duel-zone/me', headers=self.headers).json())
        with self.sessions() as db: self.assertEqual(db.get(User, 1).credits, 100)

    def test_revoked_participant_causes_neutral_abort_and_releases_stock(self):
        run_id = self.start_worker().json()['id']
        with self.sessions() as db: db.execute(delete(AuthSession).where(AuthSession.user_id == 2)); db.commit()
        self.assertEqual(self.get_run(run_id, self.other_headers).status_code, 401)
        result = self.get_run(run_id).json()
        self.assertEqual(result['state'], 'aborted'); self.assertIsNone(result['winner_seat'])
        self.assertEqual(result['reason'], 'session_ended'); self.assertEqual(self.total(), 0)

    def test_unknown_core_response_aborts_neutrally(self):
        result = self.start_worker().json(); self.adapter.engines[0].fail_answer = True
        response = self.client.post(f'/api/duel-zone/worker/runs/{result["id"]}/answer',
            json={'prompt': result['board']['prompt']['id'], 'selected': [0]}, headers=self.headers).json()
        self.assertEqual(response['state'], 'aborted'); self.assertEqual(response['reason'], 'worker_failure')
        self.assertEqual(self.total(), 0)

    def test_disconnect_timeout_releases_only_after_process_stop(self):
        run_id = self.start_worker().json()['id']; live = self.runtime.runs[run_id]
        live.seen[1] = time.monotonic() - 61
        self.adapter.engines[0].fail_close = True
        with self.assertRaises(RuntimeError): asyncio.run(self.runtime.sweep())
        self.assertEqual(self.total(), 86)
        self.adapter.engines[0].fail_close = False
        asyncio.run(self.runtime.sweep())
        self.assertEqual(self.total(), 0)
        self.assertEqual(self.get_run(run_id).json()['reason'], 'timeout')

    def test_database_settlement_retry_preserves_original_outcome(self):
        run_id = self.start_worker().json()['id']; live = self.runtime.runs[run_id]
        with patch('app.modules.duel_worker_state.finish_stopped', side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError): asyncio.run(self.runtime.stop(run_id, live, 'surrender', 1))
        self.assertTrue(self.adapter.engines[0].closed); self.assertEqual(self.total(), 86)
        asyncio.run(self.runtime.sweep())
        result = self.get_run(run_id).json()
        self.assertEqual(result['reason'], 'surrender'); self.assertEqual(result['winner_seat'], 1)
        self.assertEqual(self.total(), 0)

    def test_server_restart_never_blindly_releases_orphan_run(self):
        run_id = self.start_worker().json()['id']
        replacement = WorkerService(self.sessions, self.adapter)
        result = asyncio.run(replacement.view(run_id, self.headers['Authorization']))
        self.assertEqual(result['state'], 'recovery_required')
        self.assertEqual(self.total(), 86)

    def test_proven_orphan_recovery_is_neutral_and_idempotent(self):
        run_id = self.start_worker().json()['id']
        with self.sessions() as db:
            db.add(DuelWorkerLease(run_id=run_id, manifest_json='{"test": true}')); db.commit()
        replacement = WorkerService(self.sessions, self.adapter)
        # Simulates a kernel-confirmed stop, never a player-provided assertion.
        self.adapter.recover = lambda manifest, rid, owner: True
        results = asyncio.run(replacement.recover_orphans())
        self.assertEqual(results, [{'id': run_id, 'recovered': True}])
        self.assertEqual(self.total(), 0)
        self.assertEqual(asyncio.run(replacement.recover_orphans()), [])
        with self.sessions() as db:
            row = db.get(DuelWorkerRun, run_id)
            self.assertEqual(row.state, 'aborted')
            self.assertEqual(row.reason, 'server_restart')
            self.assertIsNone(row.winner_seat)

    def test_unproven_orphan_recovery_preserves_reservations(self):
        run_id = self.start_worker().json()['id']
        with self.sessions() as db:
            db.add(DuelWorkerLease(run_id=run_id, manifest_json='{}')); db.commit()
        replacement = WorkerService(self.sessions, self.adapter)
        self.adapter.recover = lambda *args: False
        self.assertEqual(asyncio.run(replacement.recover_orphans()), [{'id': run_id, 'recovered': False}])
        self.assertEqual(self.total(), 86)

    def test_admin_abort_requires_owner_password_and_audits_neutral_result(self):
        from app.core.passwords import hash_password
        from app.db.models import AdminAuditEvent
        run_id = self.start_worker().json()['id']
        path = '/api/admin/duels/runs/' + run_id + '/abort'
        body = {'password': 'Worker-test-password', 'reason': 'Kontrollierter Testabbruch'}
        headers = {**self.headers, 'Idempotency-Key': str(uuid4())}
        self.assertEqual(self.client.post(path, json=body, headers=headers).status_code, 403)
        with self.sessions() as db:
            user = db.get(User, 1); user.role = 'super_admin'; user.password_hash = hash_password(body['password']); db.commit()
        self.assertEqual(self.client.post(path, json={**body, 'password': 'wrong'}, headers=headers).status_code, 403)
        self.assertEqual(self.total(), 86)
        status = self.client.get('/api/admin/duels/operations', headers=self.headers).json()
        self.assertTrue(status['runs'][0]['local'])
        self.assertNotIn('session_hash', json.dumps(status))
        response = self.client.post(path, json=body, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.total(), 0)
        self.assertEqual(self.get_run(run_id).json()['reason'], 'admin_abort')
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id)).where(AdminAuditEvent.action == 'duel_abort_requested')), 1)

    def test_maintenance_is_audited_idempotent_and_blocks_only_new_starts(self):
        from app.core.passwords import hash_password
        from app.db.models import AdminAuditEvent
        body = {'password': 'Worker-test-password', 'reason': 'Geplante Wartung des Duellbetriebs', 'version': 1, 'accepting_new': False}
        headers = {**self.headers, 'Idempotency-Key': str(uuid4())}
        path = '/api/admin/duels/policy'
        self.assertEqual(self.client.post(path, json=body, headers=headers).status_code, 403)
        with self.sessions() as db:
            user = db.get(User, 1); user.role = 'super_admin'; user.password_hash = hash_password(body['password']); db.commit()
        self.assertEqual(self.client.post(path, json={**body, 'password': 'wrong'}, headers=headers).status_code, 403)
        response = self.client.post(path, json=body, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['version'], 2)
        self.assertEqual(self.client.post(path, json=body, headers=headers).json(), response.json())
        self.assertEqual(self.start_worker().status_code, 503)
        self.assertEqual(self.total(), 0)
        self.assertFalse(any(engine.commands for engine in self.adapter.engines))
        self.assertEqual(self.client.post(path, json={**body, 'accepting_new': True},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())}).status_code, 409)
        response = self.client.post(path, json={**body, 'version': 2, 'accepting_new': True},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        run = self.start_worker().json()
        response = self.client.post(path, json={**body, 'version': 3},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.start_worker().json()['id'], run['id'])
        answer = self.client.post(f'/api/duel-zone/worker/runs/{run["id"]}/answer',
            json={'prompt': run['board']['prompt']['id'], 'selected': [0]}, headers=self.headers)
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json()['state'], 'running')
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id)).where(AdminAuditEvent.action == 'duel_admission_policy')), 3)

    def control_owner(self):
        from app.core.passwords import hash_password
        with self.sessions() as db:
            user = db.get(User, 1); user.role = 'super_admin'; user.password_hash = hash_password('Worker-test-password'); db.commit()
        return {'password': 'Worker-test-password', 'reason': 'Kontrollierte Betriebsprüfung'}

    def test_rule_review_requires_evidence_source_match_and_version(self):
        from app.db.models import DuelRuleProfile, AdminAuditEvent
        body = {**self.control_owner(), 'version': 1, 'engine_approved': True, 'region_approved': True,
                'evidence': 'Nur künstliche Nachweise in dieser temporären Testdatenbank.'}
        path = '/api/admin/duels/rule-profiles/' + self.profile
        headers = {**self.headers, 'Idempotency-Key': str(uuid4())}
        with self.sessions() as db:
            profile = db.get(DuelRuleProfile, self.profile)
            profile.engine_approved = profile.region_approved = False; db.commit()
        self.assertEqual(self.client.post(path, json=body, headers=headers).status_code, 409)
        with self.sessions() as db:
            profile = db.get(DuelRuleProfile, self.profile); sources = json.loads(profile.sources_json)
            sources.update(regional_effective='2020-01-01', regional_list_sha256='a'*64)
            profile.sources_json = json.dumps(sources); db.commit()
        self.adapter.reject = True
        self.assertEqual(self.client.post(path, json=body, headers=headers).status_code, 409)
        self.adapter.reject = False
        self.assertEqual(self.client.post(path, json={**body, 'password': 'wrong'}, headers=headers).status_code, 403)
        response = self.client.post(path, json=body, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['version'], 2)
        self.assertEqual(self.client.post(path, json=body, headers=headers).json(), response.json())
        self.assertEqual(self.client.post(path, json=body,
            headers={**self.headers, 'Idempotency-Key': str(uuid4())}).status_code, 409)
        run = self.start_worker().json()
        response = self.client.post(path, json={**body, 'version': 2, 'engine_approved': False},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        result = self.get_run(run['id']).json()
        self.assertEqual(result['state'], 'aborted'); self.assertIsNone(result['winner_seat'])
        self.assertEqual(self.total(), 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id)).where(AdminAuditEvent.action == 'duel_profile_review')), 2)

    def test_duel_restriction_preserves_hub_access_and_releases_stopped_run(self):
        body = {**self.control_owner(), 'version': 1, 'hours': 24}
        path = '/api/admin/duels/restrictions/2'
        headers = {**self.headers, 'Idempotency-Key': str(uuid4())}
        run = self.start_worker().json()
        self.assertEqual(self.client.post(path, json=body, headers={**self.other_headers, 'Idempotency-Key': str(uuid4())}).status_code, 403)
        response = self.client.post(path, json=body, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['active']); self.assertEqual(response.json()['version'], 2)
        self.assertEqual(self.client.post(path, json=body, headers=headers).json(), response.json())
        self.assertEqual(self.client.get('/api/users/me', headers=self.other_headers).status_code, 200)
        self.assertEqual(self.client.get('/api/inventory/me', headers=self.other_headers).status_code, 200)
        result = self.get_run(run['id']).json()
        self.assertEqual(result['state'], 'aborted'); self.assertIsNone(result['winner_seat'])
        self.assertEqual(self.total(), 0)
        self.assertEqual(self.client.post('/api/duel-zone/lobbies', json={'deck_id': self.decks[1]['id']},
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())}).status_code, 403)
        self.assertEqual(self.client.post(path, json={**body, 'hours': 0},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())}).status_code, 409)
        response = self.client.post(path, json={**body, 'version': 2, 'hours': 0},
            headers={**self.headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['active']); self.assertEqual(response.json()['version'], 3)
        response = self.client.post('/api/duel-zone/lobbies', json={'deck_id': self.decks[1]['id']},
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)

    def test_capacity_counts_durable_runs_and_retry_keeps_original_match(self):
        from app.modules.duel_admission import require_slot, status
        with patch.object(settings, 'duel_max_active_matches', 1):
            run = self.start_worker().json()
            with self.sessions() as db:
                self.assertEqual(status(db)['available_slots'], 0)
                with self.assertRaises(HTTPException) as error: require_slot(db)
                self.assertEqual(error.exception.status_code, 429)
            self.assertEqual(self.start_worker().json()['id'], run['id'])
            self.assertEqual(self.total(), 86)
            self.client.post(f'/api/duel-zone/worker/runs/{run["id"]}/surrender', json={}, headers=self.headers)
            with self.sessions() as db: self.assertEqual(status(db)['available_slots'], 1)

    def test_history_replay_is_terminal_account_private_and_expires(self):
        from datetime import datetime, timedelta
        from app.db.models import DuelWorkerReplay
        run_id = self.start_worker().json()['id']; path = '/api/duel-zone/history/' + run_id + '/replay'
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 404)
        self.client.post('/api/duel-zone/worker/runs/' + run_id + '/surrender', json={}, headers=self.headers)
        history = self.client.get('/api/duel-zone/history', headers=self.headers).json()
        self.assertEqual(history['total'], 1); self.assertTrue(history['items'][0]['replay_available'])
        host = self.client.get(path, headers=self.headers).json()
        guest = self.client.get(path, headers=self.other_headers).json()
        self.assertNotIn('Private second card', json.dumps(host))
        self.assertNotIn('Private first card', json.dumps(guest))
        self.assertEqual(host['frames'][-1]['end_reason'], 'surrender')
        with self.sessions() as db:
            token = create_session(db, db.get(User, 1)); db.commit()
        self.assertEqual(self.client.get(path, headers={'Authorization': 'Bearer ' + token}).status_code, 200)
        self.assertEqual(self.get_run(run_id, {'Authorization': 'Bearer ' + token}).status_code, 403)
        with self.sessions() as db:
            db.get(DuelWorkerReplay, run_id).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 404)

    def test_production_gate_ignores_enabled_test_flag(self):
        with patch.object(settings, 'app_env', 'production'):
            self.assertEqual(self.start_worker().status_code, 404)
        self.assertEqual(self.total(), 0)

    def test_native_adapter_checks_sources_all_section_sizes_and_known_cards(self):
        adapter = object.__new__(NativeAdapter); adapter.sources = {'package': 'test'}; adapter.catalog = {123: {}}
        snapshot = {'sources': {'package': 'wrong'}, 'players': [{'sections': {'main': [123]*40, 'extra': [], 'side': []}}]}
        with self.assertRaises(HTTPException): adapter.check(snapshot)
        snapshot['sources']['package'] = 'test'; adapter.check(snapshot)
        for sections in ({'main': [123]*39, 'extra': [], 'side': []}, {'main': [999]*40, 'extra': [], 'side': []},
                         {'main': [123]*61, 'extra': [], 'side': []}, {'main': [123]*40, 'extra': [123]*16, 'side': []},
                         {'main': [123]*40, 'extra': [], 'side': [123]*16}, {'main': [123]*40, 'extra': [], 'side': [999]}):
            snapshot['players'][0]['sections'] = sections
            with self.assertRaises(HTTPException): adapter.check(snapshot)
        snapshot['players'][0]['sections'] = {'main': [123]*60, 'extra': [123]*15, 'side': [123]*15}
        adapter.check(snapshot)

    def test_deck_confirmation_alone_never_authorizes_worker_start(self):
        with self.sessions() as db: db.delete(db.get(DuelWorkerConsent, 2)); db.commit()
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)
        self.assertFalse(any(engine.commands for engine in self.adapter.engines))

    def test_expired_worker_consent_rejected_and_only_host_starts(self):
        from datetime import datetime, timedelta
        response = self.client.post('/api/duel-zone/worker/start', json={'lobby_id': self.room['id'], 'version': self.room['version']},
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 404)
        with self.sessions() as db:
            db.get(DuelWorkerConsent, 1).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        self.assertEqual(self.start_worker().status_code, 409)
        self.assertEqual(self.total(), 0)

    def test_simultaneous_start_requests_spawn_one_process(self):
        async def both():
            return await asyncio.gather(*(self.runtime.start(self.room['id'], self.room['version'],
                self.headers['Authorization'], str(uuid4())) for _ in range(2)))
        results = asyncio.run(both())
        self.assertEqual(results[0]['id'], results[1]['id'])
        self.assertEqual(sum(bool(e.commands) for e in self.adapter.engines), 1)
        self.assertEqual(self.total(), 86)

    def test_cancelled_start_stops_process_releases_stock_and_propagates(self):
        with patch.object(FakeEngine, 'command', new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(self.runtime.start(self.room['id'], self.room['version'],
                    self.headers['Authorization'], str(uuid4())))
        self.assertTrue(self.adapter.engines[0].closed)
        self.assertEqual(self.total(), 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(DuelWorkerRun)).reason, 'worker_failure')

    def test_cancelled_start_during_database_commit_never_leaves_unowned_stock(self):
        async def scenario():
            committed = asyncio.Event()
            original = self.runtime.database
            async def delayed(operation, *args):
                result = await original(operation, *args)
                if operation is duel_worker_state.begin:
                    committed.set()
                    await asyncio.sleep(0.03)
                return result
            with patch.object(self.runtime, 'database', side_effect=delayed):
                task = asyncio.create_task(self.runtime.start(self.room['id'], self.room['version'],
                    self.headers['Authorization'], str(uuid4())))
                await committed.wait(); task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task
        asyncio.run(scenario())
        self.assertEqual(self.total(), 0)
        self.assertFalse(any(engine.commands for engine in self.adapter.engines))

    def test_cancelled_answer_stops_process_releases_stock_and_propagates(self):
        result = self.start_worker().json()
        with patch.object(self.adapter.engines[0], 'command', new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(self.runtime.act(result['id'], self.headers['Authorization'],
                    result['board']['prompt']['id'], [0]))
        self.assertTrue(self.adapter.engines[0].closed)
        self.assertEqual(self.total(), 0)
        self.assertEqual(self.get_run(result['id']).json()['reason'], 'worker_failure')

    def socket_for(self, run_id, origin=None):
        return self.client.websocket_connect('/api/duel-zone/worker/runs/' + run_id + '/socket',
            headers={'Origin': origin or settings.cors_origin_list[0]})

    def test_websocket_authentication_private_state_answer_and_result(self):
        run_id = self.start_worker().json()['id']
        with self.socket_for(run_id) as host, self.socket_for(run_id) as guest:
            host.send_json({'type': 'authenticate', 'token': self.headers['Authorization'][7:]})
            guest.send_json({'type': 'authenticate', 'token': self.other_headers['Authorization'][7:]})
            first = host.receive_json()['result']; other = guest.receive_json()['result']
            self.assertEqual(first['board']['boards'][1]['hand'], [None])
            self.assertEqual(other['board']['boards'][0]['hand'], [None])
            def acknowledged(socket):
                for _ in range(30):
                    message = socket.receive_json()
                    if message.get('ack'): return message['result']
                self.fail('Command acknowledgement did not arrive')
            host.send_json({'type': 'answer', 'prompt': first['board']['prompt']['id'], 'selected': [0]})
            response = acknowledged(host)
            self.assertGreater(response['board']['revision'], first['board']['revision'])
            host.send_json({'type': 'surrender'})
            result = acknowledged(host)
            self.assertEqual(result['winner_seat'], 1)
            self.assertEqual(result['reason'], 'surrender')
            self.assertEqual(self.total(), 0)

    def test_websocket_rejects_foreign_origin_session_and_duplicate_seat(self):
        run_id = self.start_worker().json()['id']
        with self.assertRaises(WebSocketDisconnect):
            with self.socket_for(run_id, 'https://untrusted.invalid'): pass
        with self.sessions() as db:
            token = create_session(db, db.get(User, 1)); db.commit()
        with self.socket_for(run_id) as socket:
            socket.send_json({'type': 'authenticate', 'token': token})
            with self.assertRaises(WebSocketDisconnect) as error: socket.receive_json()
            self.assertEqual(error.exception.code, 4403)
        with self.socket_for(run_id) as first:
            first.send_json({'type': 'authenticate', 'token': self.headers['Authorization'][7:]})
            first.receive_json()
            with self.socket_for(run_id) as second:
                second.send_json({'type': 'authenticate', 'token': self.headers['Authorization'][7:]})
                with self.assertRaises(WebSocketDisconnect) as error: second.receive_json()
                self.assertEqual(error.exception.code, 4409)
        self.assertEqual(self.total(), 86)

    def test_websocket_invalid_and_stale_decisions_do_not_advance_core(self):
        run_id = self.start_worker().json()['id']
        with self.socket_for(run_id) as socket:
            socket.send_json({'type': 'authenticate', 'token': self.headers['Authorization'][7:]})
            first = socket.receive_json()['result']; pid = first['board']['prompt']['id']
            def receive_control(expected):
                # Periodic authoritative clock states can precede a command
                # response. They must preserve the same unanswered decision.
                for _ in range(20):
                    frame = socket.receive_json()
                    if frame['type'] == 'state':
                        self.assertEqual(frame['result']['board']['revision'], first['board']['revision'])
                        self.assertEqual(frame['result']['board']['prompt']['id'], pid)
                        continue
                    self.assertEqual(frame['type'], expected)
                    return
                self.fail('No websocket command response within 20 frames')
            for message in ({'type': 'answer', 'prompt': pid, 'selected': [True]},
                            {'type': 'surrender', 'winner': 0},
                            {'type': 'answer', 'prompt': pid + 1, 'selected': [0]}):
                socket.send_json(message)
                receive_control('error')
            socket.send_json({'type': 'ping'})
            receive_control('pong')
        self.assertEqual(len(self.adapter.engines[0].commands), 1)

    def test_websocket_rejects_missing_credentials_and_production_mode(self):
        run_id = self.start_worker().json()['id']
        with self.socket_for(run_id) as socket:
            socket.send_json({'type': 'ping'})
            with self.assertRaises(WebSocketDisconnect) as error: socket.receive_json()
            self.assertEqual(error.exception.code, 4401)
        with patch.object(settings, 'app_env', 'production'):
            with self.assertRaises(WebSocketDisconnect):
                with self.socket_for(run_id): pass


class WorkerCleanupTests(IsolatedAsyncioTestCase):
    async def test_empty_optional_chain_is_passed_before_next_player_prompt(self):
        projection = load_module('protocol').Projection({})
        engine = FakeEngine(); live = LiveRun(engine, projection)
        service = WorkerService(None, None)
        empty = struct.pack('<BBBBIII', 16, 0, 0, 0, 0, 0, 0)
        await service.consume_packet(live, packet(empty))
        self.assertEqual(len(engine.commands), 1)
        self.assertEqual(base64.b64decode(engine.commands[0]['response']), struct.pack('<i', -1))
        self.assertEqual(projection.prompt['owner'], 1)
        self.assertNotIn('_empty_chain', projection.prompt)

    async def test_real_chain_choice_is_never_automatically_passed(self):
        for forced in (0, 1):
            projection = load_module('protocol').Projection({10001: {'name': 'Available effect'}})
            engine = FakeEngine(); live = LiveRun(engine, projection)
            choice = struct.pack('<BBBBIII', 16, 0, 0, forced, 0, 0, 1) + struct.pack('<IBBIIQB', 10001, 0, 4, 0, 1, 0, 0)
            await WorkerService(None, None).consume_packet(live, packet(choice))
            self.assertEqual(engine.commands, [])
            self.assertEqual(len(projection.prompt['choices']), 2 if not forced else 1)

    async def test_shutdown_attempts_remaining_processes_after_one_stop_fails(self):
        runtime = WorkerService(None, None)
        first, second = LiveRun(FakeEngine(), None), LiveRun(FakeEngine(), None)
        first.engine.fail_close = True
        runtime.runs = {'first': first, 'second': second}
        runtime.database = AsyncMock()
        with self.assertRaises(RuntimeError): await runtime.close()
        self.assertFalse(first.terminal)
        self.assertTrue(second.engine.closed)
        self.assertTrue(second.terminal)
        runtime.database.assert_awaited_once_with(
            duel_worker_state.finish_stopped,
            'second', runtime.instance, 'shutdown', None, None)

    async def test_sweep_retries_other_pending_outcomes_after_one_stop_fails(self):
        runtime = WorkerService(None, None)
        first, second = LiveRun(FakeEngine(), None), LiveRun(FakeEngine(), None)
        first.engine.fail_close = True
        first.pending_outcome = ('timeout', None)
        second.pending_outcome = ('surrender', 1)
        runtime.runs = {'first': first, 'second': second}
        runtime.database = AsyncMock()
        with self.assertRaises(RuntimeError): await runtime.sweep()
        self.assertFalse(first.terminal)
        self.assertTrue(second.terminal)
        self.assertEqual(second.pending_outcome, ('surrender', 1))
        first.engine.fail_close = False
        await runtime.sweep()
        self.assertTrue(first.terminal)
        self.assertEqual(runtime.database.await_count, 2)
