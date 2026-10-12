import unittest
from datetime import date
from app.modules.duel_region import official_limits, compare_limits


class RegionTests(unittest.TestCase):
    def test_exact_name_alias_family_mapping_and_cid_never_used_as_passcode(self):
        cards = {100: {'name': 'A & B', 'alias': 0, 'ot': 3}, 101: {'name': 'A & B', 'alias': 100, 'ot': 3}}
        data = {'from': '18/05/2026', '0': [], '1': [{'nameeng': 'A &amp; B', 'cid': '999'}], '2': []}
        effective, limits, unresolved = official_limits(data, cards, date(2026, 10, 6))
        self.assertEqual(limits, {100: 1}); self.assertFalse(unresolved)
        self.assertEqual(compare_limits(cards, {101: 1}, limits), [])
        self.assertEqual(compare_limits(cards, {}, limits)[0]['official'], 1)

    def test_ambiguous_missing_future_and_incomplete_are_not_approved(self):
        cards = {100: {'name': 'Same', 'alias': 0, 'ot': 3}, 101: {'name': 'Same', 'alias': 0, 'ot': 3}, 102: {'name': 'Known', 'alias': 0, 'ot': 3}}
        data = {'from': '18/05/2026', '0': [{'nameeng': 'Same'}, {'nameeng': 'Missing'}], '1': [{'nameeng': 'Known'}], '2': []}
        _, _, missing = official_limits(data, cards, date(2026, 10, 6))
        self.assertEqual([entry['reason'] for entry in missing], ['ambiguous', 'missing'])
        with self.assertRaises(ValueError): official_limits(data, cards, date(2026, 1, 1))
        del data['2']
        with self.assertRaises(ValueError): official_limits(data, cards, date(2026, 10, 6))
