import copy
import base64
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core_worker import decode_queries
from protocol import Projection


def query_field(flag, payload): return struct.pack('<HI', len(payload) + 4, flag) + payload
def stream(*cards):
    payload = b''.join(cards)
    return struct.pack('<I', len(payload)) + payload


class QueryTests(unittest.TestCase):
    def test_temporary_reveal_is_private_to_engine_recipient(self):
        projection = Projection({101: {'name': 'Secret'}})
        message = struct.pack('<BBIIBBI', 31, 1, 1, 101, 0, 2, 0)
        projection.consume({'status': 0, 'messages': [base64.b64encode(message).decode()]})
        self.assertNotIn('Secret', str(projection.view(0)))
        self.assertEqual(projection.view(1)['events'][0]['cards'][0]['name'], 'Secret')
        self.assertNotIn('_audience', str(projection.view(1)))

    def test_equip_and_target_queries_validate_location_vectors(self):
        loc = struct.pack('<BBII', 1, 4, 3, 1)
        card = query_field(0x4000, loc) + query_field(0x8000, struct.pack('<I', 1) + loc) + query_field(0x80000000, b'')
        result = decode_queries(stream(card))[0]
        self.assertEqual(result['equip']['sequence'], 3)
        self.assertEqual(result['targets'][0]['owner'], 1)
        with self.assertRaises(ValueError): decode_queries(stream(query_field(0x8000, struct.pack('<I', 2) + loc)))

    def test_event_ids_remain_monotonic_after_history_is_bounded(self):
        projection = Projection({})
        for _ in range(3010): projection.event('chain')
        self.assertEqual(len(projection.events), 3000)
        self.assertEqual(projection.events[-1]['id'], 3010)
        self.assertEqual(projection.events[0]['id'], 11)

    def test_native_query_format_preserves_empty_zones_and_dynamic_stats(self):
        card = query_field(1, struct.pack('<I', 101)) + query_field(0x100, struct.pack('<i', -1)) + query_field(0x80000000, b'')
        self.assertEqual(decode_queries(stream(card, b'\0\0')), [{'code': 101, 'atk': -1}, None])
        for invalid in (b'', b'\0\0\0\0x', stream(b'\x01\x00'), stream(query_field(1, b'\0'))):
            with self.assertRaises(ValueError): decode_queries(invalid)

    def test_query_vectors_enforce_lengths(self):
        card = query_field(0x10000, struct.pack('<III', 2, 101, 102)) + query_field(0x80000000, b'')
        self.assertEqual(decode_queries(stream(card))[0]['overlay'], [101, 102])
        with self.assertRaises(ValueError): decode_queries(stream(query_field(0x10000, struct.pack('<II', 2, 101))))

    def test_private_query_projection_hides_every_opponent_zone_and_stats(self):
        projection = Projection({101: {'name': 'Private A'}, 102: {'name': 'Private B'}})
        board = {'deck': 35, 'zones': {str(zone): [] for zone in (2, 4, 8, 16, 32, 64)}}
        private = {'code': 102, 'position': 8, 'atk': 9999, 'overlay': [101], 'counters': [0x20001]}
        board['zones']['2'] = [private]
        board['zones']['4'] = [private]
        board['zones']['32'] = [private]
        board['zones']['64'] = [private]
        projection.query_boards = [copy.deepcopy(board), copy.deepcopy(board)]
        view = projection.view(0)
        for zone in ('hand', 'removed', 'extra'): self.assertEqual(view['boards'][1][zone], [None])
        field = view['boards'][1]['field'][0]
        self.assertIsNone(field['card']); self.assertEqual(field['materials'], []); self.assertEqual(field['counters'], [])
        self.assertEqual(view['boards'][0]['field'][0]['card']['atk'], 9999)
        projection.query_boards[0]['zones']['32'][0]['hidden'] = 1
        self.assertEqual(projection.view(0)['boards'][0]['removed'], [None])

    def test_public_hand_card_and_faceup_extra_are_visible_without_other_cards(self):
        projection = Projection({101: {'name': 'Public card'}})
        board = {'deck': 35, 'zones': {str(zone): [] for zone in (2, 4, 8, 16, 32, 64)}}
        board['zones']['2'] = [{'code': 101, 'position': 8, 'public': 1}, {'code': 101, 'position': 8}]
        board['zones']['64'] = [{'code': 101, 'position': 1}]
        projection.query_boards = [copy.deepcopy(board), copy.deepcopy(board)]
        opponent = projection.view(0)['boards'][1]
        self.assertEqual(opponent['hand'][0]['name'], 'Public card')
        self.assertIsNone(opponent['hand'][1]); self.assertEqual(opponent['extra'][0]['name'], 'Public card')
