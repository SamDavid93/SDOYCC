"""OBS browser source available only directly on the backend computer."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.core.config import settings
from app.modules.rare_pulls import Database, Acknowledgement, acknowledge, claim_next


def local_overlay(request: Request):
    # Cloudflare reaches uvicorn over loopback too: reject forwarding headers
    # as well as public Host names. Never expose the queue through the tunnel.
    if (not request.client or request.client.host not in {'127.0.0.1', '::1'}
            or request.url.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or any(name in request.headers for name in (
                'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'cf-connecting-ip'))
            or request.headers.get('origin', str(request.base_url).rstrip('/')) != str(request.base_url).rstrip('/')
            or request.headers.get('sec-fetch-site', 'same-origin') not in {'same-origin', 'none'}):
        raise HTTPException(403, 'Overlay nur direkt auf dem Server-PC verfügbar')


router = APIRouter(prefix='/api/stream-overlay', dependencies=[Depends(local_overlay)])


@router.get('/rare-pulls')
def page():
    return FileResponse(Path(__file__).with_name('rare-pulls-overlay.html'), media_type='text/html')


@router.post('/claim')
def claim(database: Database):
    if settings.rare_pull_delivery != 'overlay':
        return {'announcement': None}
    return claim_next(database, overlay=True)


@router.post('/{announcement_id}/ack')
def ack(announcement_id: int, payload: Acknowledgement, database: Database):
    return acknowledge(announcement_id, payload, database)


@router.get('/channel')
def channel():
    return {'broadcaster_login': settings.twitch_broadcaster_login}
