from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from declarations import BASE, declarable

def op(number): return BASE + (number << 32)


class DeclarationTests(unittest.TestCase):
    def test_arithmetic_logic_and_signed_division(self):
        self.assertTrue(declarable(1, {}, [8, 2, op(3), 4, op(1), op(7)]))
        self.assertFalse(declarable(1, {}, [8, 0, op(3)]))
        self.assertFalse(declarable(1, {}, [op(0)]))
        self.assertFalse(declarable(1, {}, [1, 64, op(0x12)]))
        self.assertTrue(declarable(1, {}, [3, op(6), 2, op(3), 1, op(0), op(7)]))

    def test_type_race_attribute_setcode_alias_and_token_rules(self):
        card = {'type': 0x21, 'race': 0x2000, 'attribute': 16, 'setcode': 0x1234}
        for program in ([1, op(0x102)], [0x2000, op(0x103)], [16, op(0x104)], [0x1234, op(0x101)]):
            self.assertTrue(declarable(123, card, program))
        self.assertFalse(declarable(123, card, [0x2234, op(0x101)]))
        self.assertFalse(declarable(123, {**card, 'alias': 12}, [1]))
        self.assertTrue(declarable(123, {**card, 'alias': 12}, [1, op(0x14)]))
        self.assertFalse(declarable(123, {**card, 'type': 0x4011}, [1]))
        self.assertTrue(declarable(123, {**card, 'type': 0x4011}, [1, op(0x15)]))
