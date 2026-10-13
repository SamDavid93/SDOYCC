from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.modules.duel_worker import LiveRun


class DuelClockTests(TestCase):
    def live(self):
        projection = SimpleNamespace(turn_number=1, turn=0, ended=False, prompt={'owner': 0})
        live = LiveRun(None, projection, clock_started=100)
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        return live

    def test_initial_budget_is_360_and_only_deciding_player_pays(self):
        live = self.live()
        self.assertEqual(live.clock_remaining, [360, 360])
        with patch('app.modules.duel_worker.time.monotonic', return_value=120): live.tick_clock()
        self.assertEqual(live.clock_remaining, [340, 360])
        self.assertEqual(live.clock_recovered, [0, 0])

    def test_opponent_recovers_half_of_actual_decision_time_once(self):
        live = self.live(); live.clock_remaining[1] = 200
        with patch('app.modules.duel_worker.time.monotonic', return_value=120): live.tick_clock(); live.tick_clock()
        self.assertEqual(live.clock_remaining, [340, 210])
        self.assertEqual(live.clock_recovered, [0, 10])

    def test_recovery_caps_at_360_and_overrun_cannot_create_extra_credit(self):
        live = self.live(); live.clock_remaining = [4, 359]
        with patch('app.modules.duel_worker.time.monotonic', return_value=200): live.tick_clock()
        self.assertEqual(live.clock_remaining, [0, 360])
        self.assertEqual(live.clock_recovered, [0, 1])

    def test_turn_changes_do_not_reset_remaining_time(self):
        live = self.live(); live.clock_remaining = [120, 150]
        live.projection.turn_number = 2; live.projection.turn = 1; live.projection.prompt = {'owner': 1}
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        self.assertEqual(live.clock_remaining, [120, 150])
        self.assertEqual(live.clock_owner, 1)

    def test_engine_processing_does_not_charge_or_restore_time(self):
        live = self.live()
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.pause_clock()
        live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=160): live.tick_clock()
        self.assertEqual(live.clock_remaining, [350, 100])

    def test_reactions_use_decision_owner_and_remapped_match_seats(self):
        live = self.live(); live.engine_seats = [1, 0]; live.clock_owner = None
        live.clock_remaining = [200, 300]
        live.projection.turn = 1; live.projection.prompt = {'owner': 0}
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        self.assertEqual(live.clock_owner, 1)
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.tick_clock()
        self.assertEqual(live.clock_remaining, [205, 290])
