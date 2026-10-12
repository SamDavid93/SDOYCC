"""Explicitly verified German Cardcluster scans; no scraping or guessed URLs."""
import hashlib
import io
import re
import threading
import time
from pathlib import Path

import httpx
from PIL import Image

# Konami database IDs, not internal inventory IDs or artwork/passcode variants.
SOURCES = {
    4007: 'SDWD/SDWD-DE003-ALT7-861a06c56c-500.webp',
    4041: 'RA05/RA05-DE083-UR-ALT11-3c0d19babf-500.webp',
    12950: 'LAVD/LAVD-DES08-ecea876b07-500.webp',
    4088: 'MP24/MP24-DE054-ALT7-620228bf53-500.webp',
    15032: 'LAVD/LAVD-DEO34-ALT2-04da9248ee-500.webp',
    4844: 'YGLD/YGLD-DEB26-41f77c257a-500.webp',
    13631: 'LAVD/LAVD-DES21-8c78b08cb5-500.webp',
    13619: 'LAVD/LAVD-DES17-a5617aaeff-500.webp',
    4842: 'L5DD/L5DD-DEA15-0455795588-500.webp',
    4343: 'L26D/L26D-DES05-a89f84087a-500.webp',
    4861: 'RA02/RA02-DE075-SCR-e35e1bbb48-500.webp',
    14741: 'LAVD/LAVD-DES10-bb0c810c95-500.webp',
}
CACHE = Path(__file__).resolve().parents[3] / 'cache/cards-cardcluster-de'
_locks = {}
_failures = {}
_parallel = threading.BoundedSemaphore(3)


def preferred_image(konami_id: int) -> Path | None:
    source = SOURCES.get(konami_id, '')
    if not re.fullmatch(r'[A-Z0-9]+/[A-Z0-9]+-DE[A-Z0-9]+(?:-[A-Z0-9]+)*-[a-f0-9]{10}-500\.webp', source):
        return None
    target = CACHE / f'{konami_id}-{hashlib.sha256(source.encode()).hexdigest()[:12]}.webp'
    with _locks.setdefault(konami_id, threading.Lock()), _parallel:
        if target.exists():
            return target
        if _failures.get(konami_id, 0) > time.monotonic():
            return None
        try:
            # Bound the body before decoding. Never follow redirects to another host.
            with httpx.stream('GET', 'https://cardcluster.de/storage/cards/' + source,
                              timeout=5, follow_redirects=False) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 4_000_000:
                        raise ValueError('Oversized image')
            with Image.open(io.BytesIO(content)) as image:
                if image.format != 'WEBP' or image.width != 500 or not 700 <= image.height <= 760:
                    raise ValueError('Unexpected card scan')
                image.verify()
            CACHE.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp')
            temporary.write_bytes(content)
            temporary.replace(target)
            _failures.pop(konami_id, None)
            return target
        except (httpx.HTTPError, ValueError, OSError):
            _failures[konami_id] = time.monotonic() + 3600
            return None
