"""German previews from the public official card page; cache once on local disk.

This endpoint never substitutes an English scan or removes source watermarks.
Only database-owned numeric Konami IDs can reach this downloader.
"""
import html
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.db.models import Card
from app.db.session import SessionLocal
from app.modules.image_sources import german_sources

router = APIRouter()
CACHE = Path(__file__).resolve().parents[3] / "cache" / "cards-de"
_schedule_lock = threading.Lock()
_parallel = threading.BoundedSemaphore(3)
_card_locks: dict[int | str, threading.Lock] = {}
_failures: dict[int | str, float] = {}
_last_request = 0.0


def write_image(content: bytes, target: Path):
    if not content.startswith((b"\xff\xd8", b"\x89PNG\r\n\x1a\n")) or len(content) > 4_000_000:
        raise ValueError("Kein gültiges Kartenbild")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)


def original_image(url: str) -> Path:
    # Only the stored provider card image can be fetched, never a client-supplied URL.
    match = re.fullmatch(r"https://images\.ygoprodeck\.com/images/cards/(\d+)\.jpg", url or "")
    if not match:
        raise HTTPException(404, "Kein Originalbild hinterlegt")
    target = CACHE.parent / "cards-original" / (match[1] + ".img")
    with _card_locks.setdefault("original-" + match[1], threading.Lock()), _parallel:
        if target.exists():
            return target
        if _failures.get(url, 0) > time.monotonic():
            raise HTTPException(404, "Originalbild derzeit nicht verfügbar")
        try:
            response = httpx.get(url, timeout=10, follow_redirects=False)
            response.raise_for_status()
            write_image(response.content, target)
            return target
        except (httpx.HTTPError, ValueError, OSError):
            _failures[url] = time.monotonic() + 3600
            raise HTTPException(404, "Originalbild derzeit nicht verfügbar") from None


def german_image(konami_id: int) -> Path:
    global _last_request
    target = CACHE / f"{konami_id}.img"
    if target.exists():
        return target
    if _failures.get(konami_id, 0) > time.monotonic():
        raise HTTPException(404, "Deutsches Kartenbild derzeit nicht verfügbar")
    # Deduplicate each card, limit concurrency and pace the source requests.
    with _card_locks.setdefault(konami_id, threading.Lock()), _parallel:
        if target.exists():
            return target
        if _failures.get(konami_id, 0) > time.monotonic():
            raise HTTPException(404, "Deutsches Kartenbild derzeit nicht verfügbar")
        # Static language-specific CDN files avoid the fragile per-card HTML lookup.
        for url in german_sources(konami_id):
            try:
                response = httpx.get(url, timeout=5, follow_redirects=False)
                response.raise_for_status()
                write_image(response.content, target)
                return target
            except (httpx.HTTPError, ValueError, OSError):
                continue
        with _schedule_lock:
            time.sleep(max(0, .4 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
        try:
            with httpx.Client(timeout=5, follow_redirects=False) as client:
                page = client.get("https://www.db.yugioh-card.com/yugiohdb/card_search.action", params={"ope": 2, "cid": konami_id, "request_locale": "de"})
                page.raise_for_status()
                match = re.search(r"property=['\"]og:image['\"]\s+content=['\"]([^'\"]+)", page.text)
                if not match:
                    raise ValueError("Kein deutsches Vorschaubild")
                url = html.unescape(match[1])
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if parsed.scheme != "https" or parsed.netloc != "www.db.yugioh-card.com" or parsed.path != "/yugiohdb/get_image.action" or params.get("request_locale") != ["de"] or params.get("cid") != [str(konami_id)]:
                    raise ValueError("Unerwartete Bildquelle")
                response = client.get(url)
                response.raise_for_status()
                write_image(response.content, target)
                _failures.pop(konami_id, None)
                return target
        except (httpx.HTTPError, ValueError, OSError):
            _failures[konami_id] = time.monotonic() + 3600
            raise HTTPException(404, "Deutsches Kartenbild derzeit nicht verfügbar") from None


@router.get("/api/cards/{card_id}/art/de")
def card_art_de(card_id: int):
    with SessionLocal() as db:
        card = db.get(Card, card_id)
        if card is None or not card.details or not card.details.konami_id:
            raise HTTPException(404, "Keine deutsche Kartenabbildung hinterlegt")
        konami_id = card.details.konami_id
    target = german_image(konami_id)
    return image_response(target)


def image_response(target):
    with target.open("rb") as source:
        media_type = "image/png" if source.read(8) == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return FileResponse(target, media_type=media_type, headers={"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"})


@router.get("/api/cards/{card_id}/art/original")
def card_art_original(card_id: int):
    with SessionLocal() as db:
        card = db.get(Card, card_id)
        if card is None:
            raise HTTPException(404, "Karte nicht gefunden")
        url = card.image_url
    return image_response(original_image(url))
