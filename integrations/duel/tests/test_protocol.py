"""No native runtime required; security properties of the laboratory boundary."""
from collections import Counter
from pathlib import Path
import struct
import sys
import unittest
import base64

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import validate_fixture
from protocol import Projection, Reader, UnsupportedMessage

CATALOG = {101: {'name': 'Testkarte', 'description': 'Privater Text', 'atk': 1000, 'defense': 1000}}


class BoundaryTests(unittest.TestCase):
    def test_public_activation_carries_card_for_both_seats_without_revealing_hand(self):
        message = bytes([70]) + struct.pack('<I', 101) + struct.pack('<BBII', 0, 8, 1, 1)
        message += struct.pack('<BBIQI', 0, 8, 1, 101 << 4, 1)
        self.p.consume({'status':0, 'messages':[base64.b64encode(message).decode()]})
        for seat in (0, 1):
            event = self.p.view(seat)['events'][-1]
            self.assertEqual(event['card']['code'], 101)
            self.assertEqual(event['card']['description'], 'Privater Text')
            self.assertIsNone(self.p.view(seat)['boards'][1-seat]['hand'][0])

    def test_selection_location_is_exposed_without_hidden_card_identity(self):
        message = bytes([15,0,1]) + struct.pack('<III',1,1,1) + struct.pack('<I',0) + struct.pack('<BBII',1,4,3,8)
        self.p.consume({'status':1, 'messages':[base64.b64encode(message).decode()]})
        choice = self.p.view(0)['prompt']['choices'][0]
        self.assertIsNone(choice['card'])
        self.assertEqual(choice['location']['sequence'],3)
        self.assertIsNone(self.p.view(1)['prompt'])

    def test_identical_hand_cards_keep_distinct_action_instances(self):
        message = bytes([11, 0]) + struct.pack('<I', 2)
        message += b''.join(struct.pack('<IBBI', 101, 0, 2, sequence) for sequence in (0, 1))
        message += struct.pack('<5I3B', 0, 0, 0, 0, 0, 0, 0, 0)
        self.p.consume({'status': 1, 'messages': [base64.b64encode(message).decode()]})
        choices = self.p.view(0)['prompt']['choices']
        self.assertEqual([choice['location']['sequence'] for choice in choices], [0, 1])
        self.assertEqual([choice['action'] for choice in choices], ['summon', 'summon'])
        self.assertEqual(self.p.respond(0, self.p.prompt['id'], [1]), struct.pack('<i', 1 << 16))
        self.assertIsNone(self.p.view(1)['prompt'])
        self.assertTrue(all('_response' not in choice for choice in choices))

    def test_zone_choices_distinguish_monster_and_spell_rows_for_second_seat(self):
        blocked = 0xffffffff ^ ((1 << 2) | (1 << 10))
        message = struct.pack('<BBBI', 18, 1, 1, blocked)
        self.p.consume({'status': 1, 'messages': [base64.b64encode(message).decode()]})
        prompt = self.p.view(1)['prompt']
        self.assertEqual(prompt['kind'], 'zones'); self.assertTrue(prompt['placement'])
        self.assertEqual([choice['location'] for choice in prompt['choices']],
            [{'owner': 1, 'zone': 4, 'sequence': 2}, {'owner': 1, 'zone': 8, 'sequence': 2}])
        self.assertEqual(self.p.respond(1, prompt['id'], [1]), bytes([1, 8, 2]))

    def test_native_draw_has_no_winner_and_clears_decision(self):
        self.p.consume({'status': 0, 'messages': [base64.b64encode(bytes([5, 2, 0])).decode()]})
        self.assertTrue(self.p.ended)
        self.assertIsNone(self.p.winner)
        self.assertIsNone(self.p.prompt)
        self.assertIsNone(self.p.view(0)['winner'])
        with self.assertRaises(ValueError):
            Projection(CATALOG).consume({'status': 0, 'messages': [base64.b64encode(bytes([5, 255, 0])).decode()]})

    def setUp(self):
        self.p = Projection(CATALOG)
        self.p.hands = [[101], [101]]
        self.p.field[1][(4, 0)] = {'code': 101, 'position': 8}
        self.p.new_prompt(0, 'Wählen', [self.p.choice('Test', b'answer', 101)])
        self.p.prompt['id'] = 7

    def test_hidden_hands_fields_and_prompt(self):
        view = self.p.view(0)
        self.assertIsNone(view['boards'][1]['hand'][0])
        self.assertIsNone(view['boards'][1]['field'][0]['card'])
        self.assertEqual(view['boards'][0]['hand'][0]['code'], 101)
        self.assertNotIn('_response', view['prompt']['choices'][0])
        self.assertIsNone(self.p.view(1)['prompt'])

    def test_visible_card_and_owner_can_inspect_set_card(self):
        self.assertEqual(self.p.view(1)['boards'][1]['field'][0]['card']['code'], 101)
        self.p.field[1][(4, 0)]['position'] = 1
        self.assertEqual(self.p.view(0)['boards'][1]['field'][0]['card']['code'], 101)

    def test_foreign_stale_and_malformed_answers(self):
        for owner, prompt, choices in [(1, 7, [0]), (0, 6, [0]), (0, 7.0, [0]), (False, 7, [0]), (0, 7, [-1]), (0, 7, [True]), (0, 7, [0, 0]), (0, 7, [100]), (0, 7, [])]:
            with self.subTest(owner=owner, prompt=prompt, choices=choices):
                with self.assertRaises(ValueError): self.p.respond(owner, prompt, choices)
        self.assertEqual(self.p.respond(0, 7, [0]), b'answer')

    def test_selection_counts(self):
        self.p.prompt.update(select=True, minimum=1, maximum=1)
        self.assertEqual(self.p.respond(0, 7, [0]), struct.pack('<III', 0, 1, 0))
        with self.assertRaises(ValueError): self.p.respond(0, 7, [])

    def test_unsupported_message_fails_closed(self):
        import base64
        with self.assertRaises(UnsupportedMessage):
            self.p.consume({'status': 1, 'messages': [base64.b64encode(bytes([255])).decode()]})

    def test_reader_rejects_truncated_frame(self):
        with self.assertRaises(ValueError): Reader(b'\x00').read('I')

    def test_fixture_requires_owned_legal_quantities(self):
        deck = (list(range(14)) * 3)[:40]
        catalog = dict.fromkeys(range(14))
        stock = Counter(deck)
        validate_fixture(deck, stock, catalog)
        for invalid, inventory in [(deck[:-1], stock), ([0] * 40, stock), (deck, {}), ([999] + deck[1:], stock)]:
            with self.assertRaises(ValueError): validate_fixture(invalid, inventory, catalog)


if __name__ == '__main__': unittest.main()
