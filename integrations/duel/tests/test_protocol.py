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
    def test_german_display_marks_sources_and_does_not_publish_english_originals(self):
        self.p = Projection({101: {'name': 'Testkarte', 'description': 'Deutscher Kartentext',
            'description_language': 'de', 'description_en': 'English source text',
            'options': ['Ziehe 1 Karte.'], 'options_en': ['Draw 1 card.']}}, display_language='de')
        self.consume_message(bytes([14, 0, 1]) + struct.pack('<Q', 101 << 4))
        prompt = self.p.view(0)['prompt']
        self.assertEqual(prompt['effect_language'], 'de')
        choice = prompt['choices'][0]
        self.assertEqual(choice['effect_language'], 'de')
        self.assertEqual(choice['card']['description_language'], 'de')
        self.assertNotIn('description_en', choice['card'])
        self.assertNotIn('options_en', choice['card'])
        self.assertNotIn('effect_original', choice)

    def test_mode_selected_inside_resolution_updates_only_that_chain_link(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Draw a card', 'Destroy a card']}}
        self.p.chain_effects = {1: {'effect_card': self.p.card(101), 'effect_text': 'Choose an effect', 'effect_stage': 'resolution'},
            2: {'effect_card': self.p.card(101), 'effect_text': 'Other link', 'effect_stage': 'resolution'}}
        self.p.resolving_chain = 1
        self.consume_message(bytes([14, 0, 2]) + struct.pack('<QQ', 101 << 4, (101 << 4) | 1))
        self.p.respond(0, self.p.prompt['id'], [1])
        self.p.new_prompt(0, 'Ziel wählen', [self.p.choice('Ziel', b'target', 101)])
        self.assertEqual(self.p.prompt['effect_text'], 'Destroy a card')
        self.assertEqual(self.p.chain_effects[2]['effect_text'], 'Other link')

    def test_offer_and_confirmed_costs_do_not_borrow_another_resolving_effect(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Old effect']}, 102: {'name': 'Other card', 'description': 'Other text', 'options': ['Offered effect']}}
        self.p.chain_effects[1] = {'effect_card': self.p.card(101), 'effect_text': 'Old effect', 'effect_stage': 'resolution'}
        self.p.resolving_chain = 1
        self.consume_message(bytes([12]) + struct.pack('<BIBBIIQ', 0, 102, 0, 16, 0, 1, 102 << 4))
        self.assertEqual(self.p.prompt['effect_card']['code'], 102)
        self.assertEqual(self.p.prompt['effect_text'], 'Offered effect')
        self.assertEqual(self.p.prompt['effect_stage'], 'offer')
        self.p.respond(0, self.p.prompt['id'], [0])
        self.p.new_prompt(0, 'Kosten wählen', [self.p.choice('Kosten', b'cost', 101)])
        self.assertEqual(self.p.prompt['effect_card']['code'], 102)
        self.assertEqual(self.p.prompt['effect_text'], 'Offered effect')
        self.assertEqual(self.p.prompt['effect_stage'], 'activation_cost')

    def test_resolution_context_uses_exact_chain_link_and_clears_when_completed(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Draw one card.', 'Destroy one card.'], 'options_en': ['private source strings']}}
        for number, effect in ((1, 0), (2, 1)):
            self.consume_message(bytes([70]) + struct.pack('<IBBIIBBIQI', 101, 0, 16, 0, 1, 0, 16, 0, (101 << 4) | effect, number))
        for number, text in ((2, 'Destroy one card.'), (1, 'Draw one card.')):
            self.consume_message(bytes([72, number]))
            self.p.new_prompt(0, 'Karten auswählen', [self.p.choice('Ziel', b'target', 101)])
            self.assertEqual(self.p.prompt['effect_text'], text)
            self.assertEqual(self.p.prompt['effect_stage'], 'resolution')
            self.assertEqual(self.p.prompt['effect_location']['zone'], 16)
            self.assertNotIn('options_en', self.p.prompt['effect_card'])
            self.assertIsNone(self.p.view(1)['prompt'])
            self.consume_message(bytes([73, number]))
        self.p.new_prompt(0, 'Karten auswählen', [self.p.choice('Ziel', b'target', 101)])
        self.assertNotIn('effect_card', self.p.prompt)

    def test_only_confirmed_activation_supplies_cost_context(self):
        self.p.new_prompt(0, 'Aktion wählen', [self.p.choice('Aktivieren', b'activate', 101)])
        self.p.prompt['id'] = 20
        self.p.prompt['choices'][0].update(action='activate', effect_text='Confirmed effect', location={'owner': 0, 'zone': 16, 'sequence': 0})
        self.assertNotIn('effect_card', self.p.prompt)
        with self.assertRaises(ValueError): self.p.respond(1, 20, [0])
        self.assertIsNone(self.p.pending_effect)
        self.p.respond(0, 20, [0])
        self.p.new_prompt(0, 'Kosten wählen', [self.p.choice('Kosten', b'cost', 101)])
        self.assertEqual(self.p.prompt['effect_text'], 'Confirmed effect')
        self.assertEqual(self.p.prompt['effect_stage'], 'activation_cost')
        self.p.new_prompt(0, 'Auf die Kette reagieren', [self.p.choice('Angebot', b'other', 101)])
        self.assertNotIn('effect_card', self.p.prompt)
        self.p.new_prompt(0, 'Aktion wählen', [self.p.choice('Aktion', b'next')])
        self.assertIsNone(self.p.pending_effect)

    def test_zone_selection_uses_exact_card_hint_and_is_private(self):
        self.consume_message(bytes([2, 3, 0]) + struct.pack('<Q', 101))
        self.consume_message(bytes([18, 0, 1]) + struct.pack('<I', 0xfffffffe))
        prompt = self.p.view(0)['prompt']
        self.assertEqual(prompt['placement_card']['code'], 101)
        self.assertIn('Testkarte', prompt['hint'])
        self.assertIsNone(self.p.view(1)['prompt'])
        self.consume_message(bytes([18, 0, 1]) + struct.pack('<I', 0xfffffffe))
        self.assertNotIn('placement_card', self.p.view(0)['prompt'])

    def test_activation_options_keep_descriptions_and_original_engine_indices(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Draw one card.', 'Destroy one card.']}}
        packet = bytes([11, 0]) + struct.pack('<6I', 0, 0, 0, 0, 0, 2)
        for option in (0, 1):
            packet += struct.pack('<IBBIQB', 101, 0, 4, 0, (101 << 4) | option, 0)
        self.consume_message(packet + bytes([0, 0, 0]))
        choices = self.p.view(0)['prompt']['choices']
        self.assertEqual([choice['effect_text'] for choice in choices], ['Draw one card.', 'Destroy one card.'])
        self.assertEqual(choices[0]['location'], choices[1]['location'])
        self.assertIsNone(self.p.view(1)['prompt'])
        self.assertEqual(self.p.respond(0, self.p.prompt['id'], [1]), struct.pack('<i', (1 << 16) | 5))

    def test_native_effect_options_are_explicit_and_preserve_response(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Draw one card.', 'Destroy one card.']}}
        self.consume_message(bytes([14, 0, 2]) + struct.pack('<QQ', 101 << 4, (101 << 4) | 1))
        prompt = self.p.view(0)['prompt']
        self.assertEqual(prompt['kind'], 'effect_options')
        self.assertEqual([choice['effect_text'] for choice in prompt['choices']], ['Draw one card.', 'Destroy one card.'])
        self.assertEqual(prompt['choices'][1]['card']['code'], 101)
        self.assertEqual(self.p.respond(0, prompt['id'], [1]), struct.pack('<i', 1))

    def test_chain_effect_descriptions_do_not_merge_different_locations(self):
        self.p.catalog = {101: {**CATALOG[101], 'options': ['Draw one card.', 'Destroy one card.']}}
        packet = bytes([16, 0, 0, 0]) + struct.pack('<III', 0, 0, 2)
        for option, zone in ((0, 2), (1, 16)):
            packet += struct.pack('<IBBIIQB', 101, 0, zone, 0, 1, (101 << 4) | option, 0)
        self.consume_message(packet)
        prompt = self.p.view(0)['prompt']
        self.assertEqual([choice['location']['zone'] for choice in prompt['choices'][:2]], [2, 16])
        self.assertEqual(prompt['choices'][1]['effect_text'], 'Destroy one card.')
        self.assertEqual(self.p.respond(0, prompt['id'], [1]), struct.pack('<i', 1))

    def test_sparse_field_snapshot_keeps_summons_in_same_slots_for_both_seats(self):
        def board():
            return {'deck': 30, 'zones': {str(zone): [] for zone in (2, 4, 8, 16, 32, 64)}}
        boards = [board(), board()]
        boards[1]['zones']['4'] = [None, None, {'code': 101, 'position': 1}, None, None, None, {'code': 101, 'position': 1}]
        boards[1]['zones']['8'] = [None, {'code': 101, 'position': 8}]
        self.p.consume({'status': 0, 'messages': [], 'query_boards': boards})
        for seat in (0, 1):
            field = self.p.view(seat)['boards'][1]['field']
            self.assertEqual([(entry['zone'], entry['sequence']) for entry in field], [(4, 2), (4, 6), (8, 1)])
            self.assertEqual([entry['card']['code'] for entry in field[:2]], [101, 101])
            self.assertEqual(field[2]['card'] is None, seat == 0)
        boards[1]['zones']['4'][2] = None
        self.p.consume({'status': 0, 'messages': [], 'query_boards': boards})
        for seat in (0, 1):
            self.assertEqual([(entry['zone'], entry['sequence']) for entry in self.p.view(seat)['boards'][1]['field']], [(4, 6), (8, 1)])

    def test_step_selection_exposes_required_and_selected_counts_only_to_deciding_player(self):
        message = struct.pack('<BBBBII', 26, 0, 0, 1, 2, 2)
        message += struct.pack('<IIBBII', 1, 101, 0, 1, 0, 0)
        message += struct.pack('<IIBBII', 1, 101, 0, 1, 1, 0)
        self.p.consume({'status': 1, 'messages': [base64.b64encode(message).decode()]})
        self.assertEqual(self.p.prompt['selection_progress'], {'minimum': 2, 'maximum': 2, 'selected': 1, 'can_finish': False})
        self.assertEqual(self.p.view(0)['prompt']['selection_progress']['selected'], 1)
        self.assertIsNone(self.p.view(1)['prompt'])
        self.assertEqual(self.p.respond(0, self.p.prompt['id'], [0]), struct.pack('<II', 1, 0))

    def test_turn_end_request_is_public_but_not_a_completed_turn(self):
        self.p.turn_number = 1
        self.p.new_prompt(0, 'Aktion wählen', [self.p.choice('Zug beenden', struct.pack('<i', 7))])
        self.p.prompt['id'] = 9
        for selected in ([9], []):
            with self.assertRaises(ValueError): self.p.respond(0, 9, selected)
        self.assertEqual(self.p.events, [])
        self.assertEqual(self.p.respond(0, 9, [0]), struct.pack('<i', 7))
        self.p.respond(0, 9, [0])
        for seat in (0, 1):
            self.assertEqual([event['kind'] for event in self.p.public_events(seat)], ['phase_request'])
        # A chain can intervene before the native core actually advances the turn.
        self.consume_message(bytes([41]) + struct.pack('<H', 512))
        self.assertNotIn('turn_end', [event['kind'] for event in self.p.events])
        self.consume_message(bytes([40, 1]))
        self.assertEqual([event['kind'] for event in self.p.events][-2:], ['turn_end', 'turn'])
        self.assertEqual(self.p.events[-2]['player'], 0)
        self.assertEqual(self.p.events[-1]['player'], 1)

    def test_phase_event_records_owner_and_turn_number(self):
        self.p.turn = 1; self.p.turn_number = 3
        self.consume_message(bytes([41]) + struct.pack('<H', 2))
        event = self.p.public_events(0)[-1]
        self.assertEqual((event['phase'], event['player'], event['number']), (2, 1, 3))

    def test_effect_yes_no_exposes_location_only_to_deciding_seat(self):
        self.consume_message(bytes([12]) + struct.pack('<BIBBIIQ', 0, 101, 0, 16, 2, 1, 101 << 4))
        prompt = self.p.view(0)['prompt']
        self.assertEqual(prompt['effect_location']['zone'], 16)
        self.assertEqual(prompt['effect_location']['sequence'], 2)
        self.assertIsNone(self.p.view(1)['prompt'])

    def consume_message(self, message):
        self.p.consume({'status': 0, 'messages': [base64.b64encode(message).decode()]})

    def test_draw_log_names_are_private_and_do_not_change_after_reveal(self):
        self.consume_message(bytes([90, 0]) + struct.pack('<III', 1, 101, 1))
        self.assertEqual(self.p.public_events(0)[-1]['affected_cards'][0]['name'], 'Testkarte')
        hidden = self.p.public_events(1)[-1]
        self.assertEqual(hidden['affected_cards'][0]['name'], 'Verdeckte Karte')
        self.assertNotIn('101', str(hidden))
        self.consume_message(bytes([60]) + struct.pack('<IBBII', 101, 0, 4, 0, 1))
        self.assertEqual(self.p.public_events(1)[0], hidden)
        self.assertEqual(self.p.public_events(1)[-1]['affected_cards'][0]['name'], 'Testkarte')

    def test_covered_summon_names_only_for_owner(self):
        self.consume_message(bytes([62]) + struct.pack('<IBBII', 101, 0, 4, 0, 8))
        self.assertEqual(self.p.public_events(0)[-1]['affected_cards'][0]['name'], 'Testkarte')
        self.assertEqual(self.p.public_events(1)[-1]['affected_cards'][0]['name'], 'Verdeckte Karte')
        for seat in (0,1): self.assertIsNone(self.p.public_events(seat)[-1]['card'])

    def test_face_up_summon_snapshot_has_public_visual_metadata(self):
        self.p.catalog[101]={**CATALOG[101],'level':8,'type':0x2001,'attribute':16,'image_url':'/api/cards/1/art/original'}
        self.consume_message(bytes([62])+struct.pack('<IBBII',101,1,4,5,1))
        for seat in (0,1):
            event=self.p.public_events(seat)[-1]
            self.assertEqual(event['method'],'synchro')
            self.assertEqual(event['card']['level'],8)
            self.assertEqual(event['card']['attribute'],16)
            self.assertEqual(event['card']['name'],'Testkarte')
        # Later catalog changes cannot change the name or metadata in the recorded event.
        self.p.catalog[101]['level']=1
        self.assertEqual(self.p.public_events(0)[-1]['card']['level'],8)

    def test_attack_log_names_attacker_and_hides_set_target(self):
        self.p.field[0][(4, 0)] = {'code': 101, 'position': 1}
        self.consume_message(bytes([110]) + struct.pack('<BBIIBBII', 0, 4, 0, 1, 1, 4, 0, 8))
        own = self.p.public_events(0)[-1]['affected_cards']
        self.assertEqual(own, [{'role': 'Angreifer', 'name': 'Testkarte'}, {'role': 'Ziel', 'name': 'Verdeckte Karte'}])
        self.assertEqual(self.p.public_events(1)[-1]['affected_cards'][1]['name'], 'Testkarte')

    def test_chain_resolution_retains_activated_card_name(self):
        self.consume_message(bytes([70]) + struct.pack('<IBBIIBBIQI', 101, 0, 8, 0, 1, 0, 8, 0, 101 << 4, 1))
        self.consume_message(bytes([72, 1]))
        self.consume_message(bytes([74]))
        for seat in (0, 1):
            self.assertEqual(self.p.public_events(seat)[-1]['affected_cards'][0]['name'], 'Testkarte')
            self.assertEqual(self.p.public_events(seat)[-2]['affected_cards'][0]['name'], 'Testkarte')

    def test_destroy_log_names_card_revealed_in_graveyard(self):
        self.consume_message(bytes([50]) + struct.pack('<IBBIIBBIII', 101, 1, 4, 0, 8, 1, 16, 0, 1, 1))
        for seat in (0, 1):
            self.assertEqual(self.p.public_events(seat)[-1]['affected_cards'][0]['name'], 'Testkarte')

    def test_attack_log_uses_latest_query_visibility(self):
        self.p.field[0][(4, 0)] = {'code': 101, 'position': 1}
        boards = [{'zones': {'4': [{'code': 101, 'position': 8}], '8': []}}, {'zones': {'4': [], '8': []}}]
        self.p.consume({'status': 0, 'messages': [], 'query_boards': boards})
        self.consume_message(bytes([110]) + struct.pack('<BBIIBBII', 0, 4, 0, 8, 1, 0, 0, 0))
        self.assertEqual(self.p.public_events(0)[-1]['affected_cards'][0]['name'], 'Testkarte')
        self.assertEqual(self.p.public_events(1)[-1]['affected_cards'][0]['name'], 'Verdeckte Karte')
        self.assertTrue(self.p.public_events(0)[-1]['direct'])

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
