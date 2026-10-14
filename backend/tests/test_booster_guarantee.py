import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.booster_rules import booster_size, draw_booster, is_rare


class BoosterGuaranteeTests(unittest.TestCase):
    def entry(self, rarity, weight=1):
        return SimpleNamespace(card_id=rarity, rarity=rarity, weight=weight)

    def test_guaranteed_slot_cannot_draw_common_even_when_random_slots_do(self):
        common, rare = self.entry('common', 1e308), self.entry('Ultra Rare', 1e-300)
        with patch('app.core.booster_rules.random.SystemRandom') as rng:
            rng.return_value.choices.side_effect = lambda pool, weights, k: [pool[0]] * k
            cards = draw_booster(9, [common, rare])
        self.assertEqual(cards, [common] * 8 + [rare])
        self.assertEqual(rng.return_value.choices.call_count, 2)

    def test_single_card_pool_still_delivers_nine(self):
        rare = self.entry('rare')
        self.assertEqual(draw_booster(5, [rare]), [rare] * 9)

    def test_unknown_and_unavailable_rarities_do_not_satisfy_guarantee(self):
        for entries in [[self.entry('common')], [self.entry('other')],
                        [self.entry('rare', 0), self.entry('common')]]:
            self.assertEqual(booster_size(9, entries), 0)
            with self.assertRaises(ValueError):
                draw_booster(9, entries)
        self.assertFalse(is_rare('unknown'))

    def test_custom_special_pack_keeps_its_rules(self):
        entries = [self.entry('common'), self.entry('other'), self.entry('unknown')]
        self.assertEqual(len(draw_booster(3, entries)), 3)
        self.assertEqual(booster_size(0, entries), 0)

    def test_large_weights_remain_finite(self):
        self.assertEqual(len(draw_booster(9, [self.entry('rare', 1e308), self.entry('super_rare', 1e308)])), 9)
