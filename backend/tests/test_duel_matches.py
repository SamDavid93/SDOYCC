import copy
import json
import unittest
from uuid import uuid4
from unittest.mock import patch

from app.db.models import DuelLobbyOptions, DuelMatchProgress
from app.modules.duel_matches import initial, record_game, sideboard, public
from test_duel_worker import WorkerTests, packet
import struct
import time


class MatchRulesTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {1: {'type': 17}, 2: {'type': 17}, 3: {'type': 0x4000001}}
        self.progress = initial({'players': [{'sections': {'main': [1, 1], 'extra': [3], 'side': [2]}}] * 2})

    def test_second_win_not_second_game_finishes_and_draw_does_not_score(self):
        progress = self.progress
        for winner in (None, 0, 1, None, 0):
            progress = record_game(progress, winner)
            if max(progress['score']) < 2:
                self.assertEqual(progress['phase'], 'sideboarding')
                progress['phase'] = 'playing'; progress['game'] += 1
        self.assertEqual(progress['score'], [2, 1]); self.assertEqual(progress['phase'], 'finished')
        self.assertEqual(len(progress['results']), 5)
        with self.assertRaises(ValueError): record_game(progress, 0)

    def test_sideboard_preserves_sizes_multiset_and_types(self):
        accepted = {'main': [1, 2], 'extra': [3], 'side': [1]}
        self.assertEqual(sideboard(self.progress, 0, accepted, self.catalog), accepted)
        for invalid in ({'main': [1], 'extra': [3], 'side': [1, 2]},
                        {'main': [1, 99], 'extra': [3], 'side': [1]},
                        {'main': [1, 3], 'extra': [2], 'side': [1]}):
            with self.assertRaises(ValueError): sideboard(self.progress, 0, invalid, self.catalog)

    def test_public_progress_does_not_reveal_opponent_or_original_deck(self):
        self.progress['phase'] = 'sideboarding'
        self.progress['decks'][1]['side'] = [999]
        view = public(self.progress, 0, self.catalog)
        self.assertNotIn('999', json.dumps(view)); self.assertNotIn('original', view)
        self.progress['phase'] = 'playing'
        self.assertNotIn('decks', public(self.progress, 0, self.catalog))


class MatchWorkerTests(WorkerTests):
    def setUp(self):
        super().setUp()
        self.adapter.catalog = {code: dict(row) for code, row in self.data.items()}
        with self.sessions() as db:
            db.get(DuelLobbyOptions, self.room['id']).mode = 'match'; db.commit()

    # Inherited single-duel tests intentionally stay in their original test class.
    def test_clock_exhaustion_scores_game_and_side_timeout_aborts_without_releasing_early(self):
        result = self.start_worker().json(); run_id = result['id']; live = self.runtime.runs[run_id]
        live.clock_remaining[0] = .01; live.clock_started = time.monotonic() - 1
        result = self.get_run(run_id).json()
        self.assertEqual(result['match']['score'], [0, 1]); self.assertEqual(result['match']['phase'], 'sideboarding')
        self.assertEqual(self.total(), 86)
        self.assertEqual(result['match']['results'][0]['reason'], 'decision_timeout')
        live.side_started = time.monotonic() - 181
        result = self.get_run(run_id).json()
        self.assertEqual(result['reason'], 'sideboard_timeout'); self.assertEqual(result['state'], 'aborted')
        self.assertEqual(self.total(), 0)

    def test_sideboarding_forfeit_is_distinct_from_neutral_timeout(self):
        result = self.start_worker().json(); run_id = result['id']; live = self.runtime.runs[run_id]
        live.clock_remaining[0] = .01; live.clock_started = time.monotonic() - 1
        self.get_run(run_id)
        live.match['ready'] = [True, False]; live.side_started = time.monotonic() - 181
        result = self.get_run(run_id).json()
        self.assertEqual(result['reason'], 'sideboard_forfeit'); self.assertEqual(result['winner_seat'], 0)
        self.assertEqual(self.total(), 0)

    def test_match_sideboarding_revisions_privacy_and_starter_mapping(self):
        result = self.start_worker().json(); run_id = result['id']
        self.assertEqual(result['match']['score'], [0, 0])
        engine = self.adapter.engines[0]
        async def win(command):
            engine.commands.append(command)
            return packet(struct.pack('<BBB', 5, 0, 1), status=0)
        with patch.object(engine, 'command', win):
            result = self.client.post('/api/duel-zone/worker/runs/' + run_id + '/answer',
                json={'prompt': result['board']['prompt']['id'], 'selected': [0]}, headers=self.headers).json()
        self.assertEqual(result['match']['phase'], 'sideboarding'); self.assertEqual(self.total(), 86)
        self.assertEqual(result['state'], 'running')
        guest = self.get_run(run_id, self.other_headers).json()
        self.assertNotIn('original', guest['match'])
        url = '/api/duel-zone/worker/runs/' + run_id + '/sideboard'
        body = {'version': result['match']['version'], 'sections': result['match']['decks'], 'ready': True}
        self.assertEqual(self.client.post(url, json={**body, 'starter': 1}, headers=self.headers).status_code, 403)
        result = self.client.post(url, json=body, headers=self.headers).json()
        self.assertEqual(self.client.post(url, json=body, headers=self.headers).status_code, 409)
        guest = self.get_run(run_id, self.other_headers).json()
        bad = copy.deepcopy(guest['match']['decks']); bad['main'][0] = 999
        self.assertEqual(self.client.post(url, json={'version': guest['match']['version'], 'sections': bad, 'ready': True, 'starter': 1}, headers=self.other_headers).status_code, 409)
        result = self.client.post(url, json={'version': guest['match']['version'], 'sections': guest['match']['decks'], 'ready': True, 'starter': 1}, headers=self.other_headers).json()
        self.assertEqual(result['match']['game'], 2); self.assertEqual(result['match']['phase'], 'playing')
        self.assertEqual(result['board']['seat'], 0); self.assertEqual(result['seat'], 1)
        self.assertEqual(self.total(), 86)
        self.assertIsNone(self.get_run(run_id).json()['board']['prompt'])
        with self.sessions() as db:
            progress = json.loads(db.get(DuelMatchProgress, run_id).progress_json)
            self.assertEqual(progress['score'], [1, 0]); self.assertEqual(progress['starter'], 1)
        result = self.client.post('/api/duel-zone/worker/runs/' + run_id + '/surrender', json={}, headers=self.other_headers).json()
        self.assertEqual(result['winner_seat'], 0); self.assertEqual(self.total(), 0)


# Prevent unittest from inheriting unrelated single-duel tests in this fixture.
for name in list(WorkerTests.__dict__):
    if name.startswith('test_'): setattr(MatchWorkerTests, name, None)

del WorkerTests
