"""Closed D0 lab, independent of production accounts, database and economics.

Start only through run_lab.py or the isolated browser test. This module is NOT
registered on the production app. Two capability-authenticated laboratory seats
exercise a restricted, explicitly announced fixture pool against the real core.
"""
import asyncio
import base64
from collections import Counter
from contextlib import asynccontextmanager
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from protocol import Projection
from engine_process import EngineProcess
from provision import DEFAULT_ROOT, verify

HERE = Path(__file__).resolve().parent
FLAGS = 0x30002e800  # API 11 MR5 flags + TCG SEGOC; D0 profile, not tournament approval


def fixture(root):
    with sqlite3.connect((Path(root) / 'cards/cards.cdb').as_uri() + '?mode=ro', uri=True) as db:
        columns = 'd.id,t.name,t.desc,d.atk,d.def'
        rows = db.execute(f'SELECT {columns} FROM datas d JOIN texts t ON t.id=d.id '
                          'WHERE type=17 AND (level & 255)<=4 AND atk>1000 AND alias=0 AND (ot & 2)!=0 ORDER BY d.id LIMIT 14').fetchall()
        spell = db.execute(f'SELECT {columns} FROM datas d JOIN texts t ON t.id=d.id WHERE d.id=19523799').fetchone()
    catalog = {code: {'name': name, 'description': desc, 'atk': atk, 'defense': defense} for code, name, desc, atk, defense in [*rows, spell]}
    deck = ([r[0] for r in rows] * 3)[:37] + [spell[0]] * 3
    return catalog, deck


def validate_fixture(deck, stock, catalog):
    if type(deck) is not list or len(deck) != 40 or any(type(code) is not int for code in deck):
        raise ValueError('Das Labordeck muss genau 40 Karten enthalten.')
    for code, count in Counter(deck).items():
        if code not in catalog or count > 3 or count > stock.get(code, 0):
            raise ValueError('Karte im Labor nicht verfügbar oder Kopienlimit überschritten.')


class Login(BaseModel):
    code: str = Field(min_length=20, max_length=100)


def create_app(root=DEFAULT_ROOT, origins=('http://127.0.0.1:8014',), codes=None):
    root = Path(root).resolve()
    verify(root)
    catalog, deck = fixture(root)
    stock = Counter(deck)
    validate_fixture(deck, stock, catalog)
    projection = Projection(catalog)
    engine = EngineProcess(root)
    seats = {}
    sessions = {}
    codes = codes or (secrets.token_urlsafe(24), secrets.token_urlsafe(24))
    lock = asyncio.Lock()
    started = False
    failure = None

    @asynccontextmanager
    async def lifespan(app):
        try: yield
        finally: await engine.close()

    app = FastAPI(title='SDOYCC DuelZone – isoliertes Techniklabor', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.codes = codes
    app.state.projection = projection
    app.state.engine = engine
    app.state.fixture_deck = deck

    @app.middleware('http')
    async def private(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.get('/')
    async def index(): return FileResponse(HERE / 'web/index.html')

    @app.get('/health')
    async def health(): return {'status': 'ok', 'scope': 'isolated-lab', 'core_api': [11, 0]}

    @app.post('/session')
    async def login(body: Login, request: Request):
        if request.headers.get('origin') not in origins: raise HTTPException(403, 'Falscher Ursprung')
        owner = next((seat for seat, code in enumerate(codes) if secrets.compare_digest(code, body.code)), None)
        if owner is None: raise HTTPException(401, 'Ungültiger Laborzugang')
        if len(sessions) >= 20: raise HTTPException(429, 'Zu viele Laborsitzungen')
        token = secrets.token_urlsafe(32); sessions[token] = owner
        response = JSONResponse({'seat': owner})
        response.set_cookie('duel_lab', token, httponly=True, secure=request.url.scheme == 'https', samesite='strict', max_age=3600)
        return response

    async def broadcast():
        for owner, socket in list(seats.items()):
            try:
                if failure:
                    await socket.send_json({'type': 'failure', 'message': failure})
                elif started:
                    await socket.send_json({'type': 'state', **projection.view(owner)})
                else:
                    await socket.send_json({'type': 'waiting', 'message': 'Warte auf den zweiten Labor-Spieler.'})
            except (WebSocketDisconnect, RuntimeError, OSError):
                if seats.get(owner) is socket: seats.pop(owner, None)

    @app.websocket('/duel')
    async def duel(socket: WebSocket):
        nonlocal started, failure
        if socket.headers.get('origin') not in origins:
            await socket.close(code=4403); return
        owner = sessions.get(socket.cookies.get('duel_lab'))
        if owner is None:
            await socket.close(code=4401); return
        await socket.accept()
        async with lock:
            if owner in seats:
                await socket.close(code=4409); return
            seats[owner] = socket
            if len(seats) == 2 and not started and not failure:
                try:
                    result = await engine.command({'op': 'start', 'decks': [deck, deck], 'flags': FLAGS})
                    projection.consume(result); started = True
                except Exception:
                    failure = 'Engine-Prüfung unterbrochen. Das Laborprotokoll muss geprüft werden.'
                    await engine.close()
            await broadcast()
        try:
            while True:
                raw = await socket.receive_text()
                if len(raw) > 4096:
                    await socket.close(code=4400); break
                async with lock:
                    if seats.get(owner) is not socket: break
                    if not started or failure or projection.ended:
                        await socket.send_json({'type': 'error', 'message': 'Keine aktive Entscheidung.'}); continue
                    try:
                        message = json.loads(raw)
                        if not isinstance(message, dict) or message.get('type') not in ('answer', 'surrender'): raise ValueError('Unbekannte Aktion')
                        surrender = message['type'] == 'surrender'
                        if not surrender:
                            response = projection.respond(owner, message.get('prompt'), message.get('selected'))
                    except (ValueError, TypeError):
                        await socket.send_json({'type': 'error', 'message': 'Ungültige, fremde oder veraltete Entscheidung.'}); continue
                    try:
                        if surrender:
                            # The authenticated seat concedes, never a client-supplied player ID.
                            # Stop the worker before publishing the terminal result.
                            await engine.close()
                            projection.surrender(owner)
                        else:
                            packet = await engine.command({'op': 'respond', 'response': base64.b64encode(response).decode()})
                            projection.consume(packet)
                            if projection.ended: await engine.close()
                    except Exception:
                        failure = 'Dieser Engine-Ablauf wird im Techniklabor noch nicht unterstützt.'
                        await engine.close()
                    await broadcast()
        except WebSocketDisconnect:
            pass
        finally:
            async with lock:
                if seats.get(owner) is socket: seats.pop(owner, None)

    app.mount('/assets', StaticFiles(directory=HERE / 'web'), name='assets')
    return app
