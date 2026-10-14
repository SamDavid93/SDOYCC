from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.modules.duel_worker import CLOCK_DELIVERY_GRACE, LiveRun


class DuelClockTests(TestCase):
    def live(self, ready=True):
        projection = SimpleNamespace(turn_number=1, turn=0, ended=False, revision=1, prompt={'owner': 0, 'id': 1})
        live = LiveRun(None, projection, clock_started=100)
        with patch('app.modules.duel_worker.time.monotonic', return_value=100):
            live.tick_clock()
            if ready: live.decision_ready(0, 1, 1)
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
        live.projection.turn_number = 2; live.projection.turn = 1
        live.projection.prompt = {'owner': 1, 'id': 2}; live.projection.revision = 2
        with patch('app.modules.duel_worker.time.monotonic', return_value=100):
            live.tick_clock()
            self.assertIsNone(live.clock_owner)
            live.decision_ready(1, 2, 2)
        self.assertEqual(live.clock_remaining, [120, 150])
        self.assertEqual(live.clock_owner, 1)

    def test_standby_supplements_fast_opponent_credit_to_sixty_only_once(self):
        live = self.live(); live.clock_owner = None
        live.clock_remaining = [150, 200]; live.clock_recovered = [1, 0]
        live.projection.events = [{'kind': 'phase', 'phase': 2, 'player': 0, 'number': 3}]
        with patch('app.modules.duel_worker.time.monotonic', return_value=100):
            live.tick_clock(); live.tick_clock()
        self.assertEqual(live.clock_remaining, [209, 200])
        self.assertEqual(live.clock_recovered, [60, 0])

    def test_standby_keeps_higher_half_credit_and_caps_refill(self):
        live = self.live(); live.clock_owner = None
        live.clock_remaining = [200, 350]; live.clock_recovered = [80, 0]
        live.projection.events = [{'kind': 'phase', 'phase': 2, 'player': 0, 'number': 3}, {'kind': 'phase', 'phase': 2, 'player': 1, 'number': 4}]
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        self.assertEqual(live.clock_remaining, [200, 360])
        self.assertEqual(live.clock_recovered, [80, 10])
        live.clock_remaining[0] = 100
        live.projection.events.append({'kind': 'phase', 'phase': 2, 'player': 0, 'number': 5})
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        self.assertEqual(live.clock_remaining[0], 160)

    def test_standby_refill_maps_match_seats_even_when_main_phase_already_arrived(self):
        live = self.live(); live.clock_owner = None; live.engine_seats = [1, 0]
        live.clock_remaining = [100, 200]
        live.projection.phase = 4
        live.projection.events = [{'kind': 'phase', 'phase': 2, 'player': 0, 'number': 2}]
        with patch('app.modules.duel_worker.time.monotonic', return_value=100): live.tick_clock()
        self.assertEqual(live.clock_remaining, [100, 260])

    def test_engine_processing_does_not_charge_or_restore_time(self):
        live = self.live()
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.clear_decision()
        live.clock_remaining[1] = 100
        live.projection.prompt = {'owner': 1, 'id': 2}; live.projection.revision = 2
        with patch('app.modules.duel_worker.time.monotonic', return_value=160): live.tick_clock()
        self.assertEqual(live.clock_remaining, [350, 100])
        self.assertIsNone(live.clock_owner)

    def test_reactions_use_decision_owner_and_remapped_match_seats(self):
        live = self.live(); live.engine_seats = [1, 0]; live.clock_owner = None
        live.clock_remaining = [200, 300]
        live.projection.turn = 1; live.projection.prompt = {'owner': 0, 'id': 2}; live.projection.revision = 2
        with patch('app.modules.duel_worker.time.monotonic', return_value=100):
            live.tick_clock()
            live.decision_ready(1, 2, 2)
        self.assertEqual(live.clock_owner, 1)
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.tick_clock()
        self.assertEqual(live.clock_remaining, [205, 290])

    def test_delivery_and_render_wait_never_charge_budget_or_refill_opponent(self):
        live = self.live(ready=False); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=120):
            live.tick_clock()
            self.assertEqual(live.clock_remaining, [360, 100])
            self.assertEqual(live.clock_recovered, [0, 0])
            self.assertEqual(live.clock()['waiting_for'], 0)
            self.assertEqual(live.clock()['ready_timeout'], 10)
            self.assertTrue(live.clock()['readiness_required'])
            live.decision_ready(0, 1, 1)
        with patch('app.modules.duel_worker.time.monotonic', return_value=125): live.tick_clock()
        self.assertEqual(live.clock_remaining, [355, 102.5])

    def test_duplicate_ready_does_not_pause_reset_or_double_refill(self):
        live = self.live(); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=110):
            live.decision_ready(0, 1, 1); live.decision_ready(0, 1, 1)
        self.assertEqual(live.clock_remaining, [350, 105])
        self.assertEqual(live.clock_recovered, [0, 5])
        with patch('app.modules.duel_worker.time.monotonic', return_value=120): live.tick_clock()
        self.assertEqual(live.clock_remaining, [340, 110])

    def test_foreign_stale_and_wrong_revision_ready_cannot_start_a_clock(self):
        live = self.live(ready=False)
        with patch('app.modules.duel_worker.time.monotonic', return_value=105):
            for values in ((1, 1, 1), (0, 2, 1), (0, 1, 2)):
                with self.assertRaises(ValueError): live.decision_ready(*values)
        self.assertIsNone(live.clock_owner)
        self.assertEqual(live.clock_remaining, [360, 360])
        self.assertEqual(live.clock_waiting_since, 100)

    def test_disconnect_pauses_and_reconnect_uses_only_leftover_grace(self):
        live = self.live(ready=False); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=105): live.decision_ready(0, 1, 1)
        with patch('app.modules.duel_worker.time.monotonic', return_value=115): live.disconnect_decision(0)
        with patch('app.modules.duel_worker.time.monotonic', return_value=120):
            live.tick_clock(); self.assertEqual(live.delivery_remaining(), 20)
            live.decision_ready(0, 1, 1)
        self.assertEqual(live.clock_remaining, [350, 105])
        self.assertEqual(live.clock_grace, 20)
        with patch('app.modules.duel_worker.time.monotonic', return_value=125):
            live.disconnect_decision(0); live.disconnect_decision(0)
        with patch('app.modules.duel_worker.time.monotonic', return_value=145):
            self.assertEqual(live.delivery_remaining(), 0)
            with self.assertRaises(ValueError): live.decision_ready(0, 1, 1)
        self.assertEqual(live.clock_remaining, [345, 107.5])
        self.assertIsNone(live.clock_owner)

    def test_opponent_disconnect_does_not_pause_current_decision(self):
        live = self.live()
        with patch('app.modules.duel_worker.time.monotonic', return_value=105): live.disconnect_decision(1)
        self.assertEqual(live.clock_owner, 0)
        self.assertIsNone(live.clock_waiting_since)

    def test_bot_starts_automatically_but_human_practice_prompt_waits(self):
        live = self.live(ready=False); live.practice = True
        live.projection.prompt = {'owner': 1, 'id': 2}; live.projection.revision = 2
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.tick_clock()
        self.assertEqual(live.clock_owner, 1)
        with patch('app.modules.duel_worker.time.monotonic', return_value=115): live.clear_decision()
        live.projection.prompt = {'owner': 0, 'id': 3}; live.projection.revision = 3
        with patch('app.modules.duel_worker.time.monotonic', return_value=120): live.tick_clock()
        self.assertEqual(live.clock_remaining, [360, 355])
        self.assertIsNone(live.clock_owner)

    def test_empty_chain_terminal_and_sideboard_never_wait_for_ui_or_charge(self):
        for mode in ('_empty_chain', 'ended', 'terminal', 'sideboard', 'no_prompt'):
            live = self.live(ready=False)
            if mode == '_empty_chain': live.projection.prompt['_empty_chain'] = True
            if mode == 'ended': live.projection.ended = True
            if mode == 'terminal': live.terminal = True
            if mode == 'sideboard': live.match = {'phase': 'sideboarding'}
            if mode == 'no_prompt': live.projection.prompt = None
            with patch('app.modules.duel_worker.time.monotonic', return_value=130): live.tick_clock()
            self.assertIsNone(live.clock_owner, mode)
            self.assertIsNone(live.clock_waiting_since, mode)
            self.assertEqual(live.clock_remaining, [360, 360], mode)

    def test_receipt_cutoff_excludes_server_processing(self):
        live = self.live(); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=125):
            live.tick_clock(now=110)
            live.clear_decision(now=110)
        self.assertEqual(live.clock_remaining, [350, 105])
        self.assertEqual(live.clock_recovered, [0, 5])
        self.assertIsNone(live.clock_owner)

    def test_delivery_grace_is_thirty_seconds(self):
        self.assertEqual(CLOCK_DELIVERY_GRACE, 30)

    def test_offline_detection_refunds_unconfirmed_interval_and_its_exact_recovery(self):
        live = self.live(); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.tick_clock()
        with patch('app.modules.duel_worker.time.monotonic', return_value=120):
            live.disconnect_decision(0, confirmed_at=105)
        self.assertEqual(live.clock_remaining, [355, 102.5])
        self.assertEqual(live.clock_recovered, [0, 2.5])
        self.assertEqual(live.clock_grace, 15)
        with patch('app.modules.duel_worker.time.monotonic', return_value=125): live.decision_ready(0, 1, 1)
        self.assertEqual(live.clock_grace, 10)
        with patch('app.modules.duel_worker.time.monotonic', return_value=145):
            live.disconnect_decision(0, confirmed_at=125)
        self.assertEqual(live.clock_remaining, [345, 107.5])
        self.assertEqual(live.clock_grace, 0)
        with patch('app.modules.duel_worker.time.monotonic', return_value=145):
            with self.assertRaises(ValueError): live.decision_ready(0, 1, 1)

    def test_partial_disconnect_refund_preserves_credit_earned_before_cap(self):
        live = self.live(); live.clock_remaining[1] = 355; live.clock_grace = 10
        with patch('app.modules.duel_worker.time.monotonic', return_value=120):
            live.disconnect_decision(0, confirmed_at=100)
        self.assertEqual(live.clock_remaining, [350, 360])
        self.assertEqual(live.clock_recovered, [0, 5])
        self.assertEqual(live.clock_grace, 0)

    def test_disconnect_refund_cannot_touch_an_earlier_prompt(self):
        live = self.live(); live.clock_remaining[1] = 100
        with patch('app.modules.duel_worker.time.monotonic', return_value=110): live.clear_decision()
        live.projection.prompt = {'owner': 0, 'id': 2}; live.projection.revision = 2
        with patch('app.modules.duel_worker.time.monotonic', return_value=120):
            live.tick_clock(); live.decision_ready(0, 2, 2)
        with patch('app.modules.duel_worker.time.monotonic', return_value=130):
            live.disconnect_decision(0, confirmed_at=100)
        self.assertEqual(live.clock_remaining, [350, 105])
        self.assertEqual(live.clock_recovered, [0, 5])
