"""Private websocket transport. Credentials travel only in the first TLS frame."""
import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import settings
from app.modules.duel_worker import Answer, DecisionReady, Surrender, Sideboard, service

router = APIRouter()
TERMINAL = {'finished', 'aborted', 'recovery_required'}


async def read_frame(socket, timeout=10):
    raw = await asyncio.wait_for(socket.receive_text(), timeout)
    if len(raw.encode('utf8')) > 4096:
        raise ValueError('Frame too large')
    result = json.loads(raw)
    if not isinstance(result, dict): raise ValueError('Object required')
    return result


@router.websocket('/api/duel-zone/worker/runs/{run_id}/socket')
async def worker_socket(socket: WebSocket, run_id: str):
    # CORS middleware does not authorize websocket Origins.
    if socket.headers.get('origin') not in settings.cors_origin_list or len(run_id) != 36:
        await socket.close(code=4403); return
    try: runtime = service(socket)
    except HTTPException:
        await socket.close(code=4404); return
    await socket.accept()
    seat = None
    key = None
    last_received = None
    try:
        message = await read_frame(socket)
        if set(message) != {'type', 'token'} or message['type'] != 'authenticate' or not isinstance(message['token'], str) or not 20 <= len(message['token']) <= 256:
            await socket.close(code=4401); return
        authorization = 'Bearer ' + message['token']
        del message
        _, seat, _, _ = await runtime.inspect(run_id, authorization)
        key = (run_id, seat)
        # No awaits between testing and occupying the seat.
        if key in runtime.sockets:
            await socket.close(code=4409); return
        runtime.sockets[key] = socket
        live = runtime.runs.get(run_id)
        if live is not None: live.seen[seat] = time.monotonic()
        last_sent = None
        window, count = time.monotonic(), 0
        last_received = time.monotonic()
        while True:
            result = await runtime.view(run_id, authorization, touch=False)
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
            if encoded != last_sent:
                await asyncio.wait_for(socket.send_json({'type': 'state', 'result': result}), 5)
                last_sent = encoded
            if result['state'] in TERMINAL:
                await socket.close(code=1000); break
            try: message = await read_frame(socket, timeout=0.5)
            except asyncio.TimeoutError:
                if time.monotonic() - last_received > 20:
                    await socket.close(code=4408); break
                continue
            last_received = time.monotonic()
            live = runtime.runs.get(run_id)
            if live is not None and runtime.sockets.get(key) is socket:
                live.seen[seat] = max(live.seen[seat], last_received)
            if time.monotonic() - window >= 10: window, count = time.monotonic(), 0
            count += 1
            if count > 80:
                await socket.close(code=4429); break
            try:
                kind = message.pop('type', None)
                if kind == 'ping' and not message:
                    live = runtime.runs.get(run_id)
                    if live is not None: live.seen[seat] = time.monotonic()
                    await socket.send_json({'type': 'pong'}); continue
                if kind == 'decision_ready':
                    body = DecisionReady.model_validate(message)
                    result = await runtime.decision_ready(run_id, authorization, body.prompt, body.revision, socket)
                    # Readiness is not an action acknowledgement: it must never
                    # unlock a still-pending engine answer in the browser.
                    await socket.send_json({'type': 'state', 'result': result, 'ready_ack': True})
                    last_sent = json.dumps(result, ensure_ascii=False, sort_keys=True)
                    continue
                if kind == 'answer':
                    body = Answer.model_validate(message)
                    result = await runtime.act(run_id, authorization, body.prompt, body.selected, cancel=body.cancel)
                elif kind == 'surrender':
                    Surrender.model_validate(message)
                    result = await runtime.act(run_id, authorization, surrender=True)
                elif kind == 'sideboard':
                    result = await runtime.sideboard(run_id, authorization, Sideboard.model_validate(message))
                else: raise ValueError('Unknown command')
                # An explicit acknowledgement also unblocks the UI when an answer
                # produces the same public state. It never repeats an engine action.
                await socket.send_json({'type': 'state', 'result': result, 'ack': True})
                last_sent = json.dumps(result, ensure_ascii=False, sort_keys=True)
            except (ValidationError, ValueError, TypeError):
                await socket.send_json({'type': 'error', 'message': 'Ungültige Spielentscheidung.'})
            except HTTPException as error:
                if error.status_code in (401, 403, 404): raise
                await socket.send_json({'type': 'error', 'message': error.detail})
    except HTTPException as error:
        await socket.close(code={401: 4401, 403: 4403, 404: 4404}.get(error.status_code, 1011))
    except (ValueError, TypeError, asyncio.TimeoutError):
        await socket.close(code=4400)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        if key is not None and runtime.sockets.get(key) is socket:
            try: await runtime.disconnect(run_id, seat, socket, last_received)
            finally:
                if runtime.sockets.get(key) is socket: runtime.sockets.pop(key, None)
