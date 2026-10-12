"""Authenticated surrender and terminal-state invariants; no native runtime or Hub DB."""
import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab
from protocol import Projection


class SurrenderTests(unittest.TestCase):
    def test_terminal_state_cannot_be_changed_or_answered(self):
        p = Projection({})
        p.new_prompt(0, 'Test', [p.choice('Test', b'answer')])
        p.prompt['id'] = 1
        for invalid in (True, -1, 2, '0'):
            with self.assertRaises(ValueError): p.surrender(invalid)
        p.surrender(1)
        self.assertEqual(p.winner, 0)
        self.assertIsNone(p.prompt)
        with self.assertRaises(ValueError): p.respond(0, 1, [0])
        with self.assertRaises(ValueError): p.surrender(0)
        self.assertEqual(p.winner, 0)

    def test_gateway_uses_authenticated_seat_and_stops_worker(self):
        deck = (list(range(14)) * 3)[:40]
        for loser in (0, 1):
            with self.subTest(loser=loser), patch.object(lab, 'verify'), patch.object(lab, 'fixture', return_value=(dict.fromkeys(range(14)), deck)), patch.object(lab, 'EngineProcess') as engine_type:
                engine = engine_type.return_value
                engine.command = AsyncMock(return_value={'status': 0, 'messages': [base64.b64encode(bytes([40, 0])).decode()]})
                engine.close = AsyncMock()
                app = lab.create_app()
                origin = {'origin': 'http://127.0.0.1:8014'}
                with TestClient(app) as client:
                    cookies = []
                    for code in app.state.codes:
                        response = client.post('/session', json={'code': code}, headers=origin)
                        self.assertEqual(response.status_code, 200)
                        cookies.append('duel_lab=' + response.cookies['duel_lab'])
                    with client.websocket_connect('/duel', headers={**origin, 'cookie': cookies[0]}) as first:
                        self.assertEqual(first.receive_json()['type'], 'waiting')
                        first.send_json({'type': 'surrender'})
                        self.assertEqual(first.receive_json()['type'], 'error')
                        engine.close.assert_not_awaited()
                        with client.websocket_connect('/duel', headers={**origin, 'cookie': cookies[1]}) as second:
                            first.receive_json(); second.receive_json()
                            sockets = [first, second]
                            sockets[loser].send_json({'type': 'surrender', 'owner': 1-loser, 'winner': loser})
                            results = [socket.receive_json() for socket in sockets]
                            for result in results:
                                self.assertTrue(result['ended'])
                                self.assertEqual(result['winner'], 1-loser)
                                self.assertEqual(result['end_reason'], 'surrender')
                                self.assertIsNone(result['prompt'])
                            engine.close.assert_awaited_once()
                            for socket in sockets:
                                socket.send_json({'type': 'surrender'})
                                self.assertEqual(socket.receive_json()['type'], 'error')
                            self.assertEqual(app.state.projection.winner, 1-loser)
                            engine.command.assert_awaited_once()


if __name__ == '__main__': unittest.main()
