import base64
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import Projection

CATALOG = {101: {'name': 'Material A', 'options': ['Effekt A']}, 102: {'name': 'Material B'}, 103: {'name': 'Material C'}}
def frame(fmt, *values): return struct.pack('<' + fmt, *values)
def location(): return frame('BBII', 0, 4, 0, 1)


class DecisionTests(unittest.TestCase):
    def parse(self, message):
        projection = Projection(CATALOG)
        projection.consume({'status': 1, 'messages': [base64.b64encode(message).decode()]})
        return projection

    def test_effect_confirmation_options_and_number(self):
        p = self.parse(frame('BBI', 12, 0, 101) + location() + frame('Q', 1616))
        self.assertEqual(p.respond(0, 1, [1]), frame('i', 0))
        p = self.parse(frame('BBBQQ', 14, 0, 2, 1616, 1617))
        self.assertEqual(p.view(0)['prompt']['choices'][0]['label'], 'Effekt A')
        self.assertEqual(p.respond(0, 1, [1]), frame('i', 1))
        p = self.parse(frame('BBBQQ', 143, 0, 2, 100, 500))
        self.assertEqual(p.respond(0, 1, [1]), frame('i', 1))

    def test_multiple_zones_require_exact_distinct_count(self):
        p = self.parse(frame('BBBI', 24, 0, 2, 0xfffffff8))
        self.assertEqual(p.respond(0, 1, [0, 2]), bytes([0, 4, 0, 0, 4, 2]))
        for selected in ([0], [0, 0], [0, 1, 2]):
            with self.assertRaises(ValueError): p.respond(0, 1, selected)

    def test_cancel_and_incremental_selection_use_native_response_layout(self):
        p = self.parse(frame('BBBBIII', 26, 0, 1, 0, 1, 2, 1) + frame('I', 101) + location() + frame('I', 0))
        self.assertEqual(p.respond(0, 1, [0]), frame('II', 1, 0))
        self.assertEqual(p.respond(0, 1, [], cancel=True), frame('i', -1))
        with self.assertRaises(ValueError): p.respond(0, 1, [0], cancel=True)
        empty = self.parse(frame('BBBBIIII', 26, 0, 1, 0, 0, 0, 0, 0))
        self.assertEqual(empty.respond(0, 1, [], cancel=True), frame('i', -1))

    def test_tribute_values_and_sort_permutation(self):
        p = self.parse(frame('BBBIII', 20, 0, 1, 2, 2, 2) + frame('IBBIB', 101, 0, 4, 0, 2) + frame('IBBIB', 102, 0, 4, 1, 1))
        self.assertEqual(p.respond(0, 1, [0]), frame('III', 0, 1, 0))
        with self.assertRaises(ValueError): p.respond(0, 1, [1])
        p = self.parse(frame('BBI', 25, 0, 3) + b''.join(frame('IBII', code, 0, 4, i) for i, code in enumerate((101, 102, 103))))
        self.assertEqual(p.respond(0, 1, [2, 0, 1]), bytes([1, 2, 0]))
        with self.assertRaises(ValueError): p.respond(0, 1, [0, 1])

    def test_counter_allocations_allow_repeated_counts_but_enforce_total(self):
        p = self.parse(frame('BBHHI', 22, 0, 1, 2, 2) + frame('IBBBH', 101, 0, 4, 0, 2) + frame('IBBBH', 102, 0, 4, 1, 3))
        self.assertEqual(p.respond(0, 1, [1, 1]), frame('HH', 1, 1))
        for selected in ([2, 2], [0, 4], [2], [True, 1], [-1, 3]):
            with self.assertRaises(ValueError): p.respond(0, 1, selected)

    def test_exact_sum_respects_required_and_dual_values(self):
        p = self.parse(frame('BBBIIII', 23, 0, 0, 8, 1, 2, 1) + frame('I', 103) + location() + frame('I', 2)
            + frame('I', 2) + frame('I', 101) + location() + frame('I', (6 << 16) | 3) + frame('I', 102) + location() + frame('I', 4))
        self.assertEqual(p.respond(0, 1, [0]), frame('III', 0, 1, 0))
        for selected in ([1], [0, 1], []):
            with self.assertRaises(ValueError): p.respond(0, 1, selected)
        self.assertNotIn('_weights', p.view(0)['prompt'])
        self.assertIsNone(p.view(1)['prompt'])

    def test_attributes_and_64bit_races_only_use_offered_bits(self):
        p = self.parse(frame('BBBI', 141, 0, 2, 0x21))
        self.assertEqual(p.respond(0, 1, [0, 1]), frame('I', 0x21))
        with self.assertRaises(ValueError): p.respond(0, 1, [0])
        p = self.parse(frame('BBBQ', 140, 0, 1, 1 << 62))
        self.assertEqual(p.respond(0, 1, [0]), frame('Q', 1 << 62))

    def test_at_least_sum_ignores_native_zero_count_limits(self):
        p = self.parse(frame('BBBIIII', 23, 0, 1, 8, 0, 0, 0) + frame('I', 1) + frame('I', 101) + location() + frame('I', 8))
        self.assertEqual(p.prompt['maximum'], 1)
        self.assertEqual(p.respond(0, 1, [0]), frame('III', 0, 1, 0))
        with self.assertRaises(ValueError): p.respond(0, 1, [])

    def test_rock_paper_scissors_and_non_cancelable_choice(self):
        p = self.parse(frame('BB', 132, 0))
        self.assertEqual(p.respond(0, 1, [2]), frame('i', 3))
        with self.assertRaises(ValueError): p.respond(0, 1, [], cancel=True)

    def test_card_declaration_returns_passcode_and_rejects_not_offered_choice(self):
        p = self.parse(frame('BBBQQ', 142, 0, 2, 102, 0x4000010000000000))
        self.assertEqual(len(p.prompt['choices']), 1)
        self.assertEqual(p.respond(0, 1, [0]), frame('i', 102))
        with self.assertRaises(ValueError): p.respond(0, 1, [1])
