"""Language-specific artwork index. Fetch once, cache locally, never guess paths."""
import json
import threading
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

INDEX = Path(__file__).resolve().parents[3] / "cache" / "artworks-de-index.json"
_index = None
_lock = threading.Lock()


def trusted_artwork_url(path):
    if not isinstance(path, str) or not path:
        return None
    url = urljoin("https://artworks.ygoresources.com/", path)
    parsed = urlparse(url)
    try:
        valid_port = parsed.port in (None, 443)
    except ValueError:
        return None
    if parsed.scheme != "https" or not valid_port or parsed.username or parsed.password:
        return None
    host = parsed.hostname or ""
    if host != "artworks.ygoresources.com" and not (host.startswith("artworks-") and host.endswith(".ygoresources.com")):
        return None
    return url


def refresh_index(manifest=None):
    global _index
    if manifest is None:
        response = httpx.get("https://artworks.ygoresources.com/manifest.json", timeout=30)
        response.raise_for_status()
        manifest = response.json()
    if not isinstance(manifest.get("cards"), dict) or not manifest["cards"]:
        raise ValueError("Leerer Bildindex")
    result = {}
    for cid, artworks in manifest["cards"].items():
        urls = []
        # Prefer the first artwork, then use another German artwork of the same card.
        for artwork in sorted(artworks, key=lambda value: (value != "1", value)):
            for entry in artworks[artwork].get("idx", {}).get("de", []):
                url = trusted_artwork_url(entry.get("path", ""))
                if url and url not in urls:
                    urls.append(url)
        if urls:
            result[str(cid)] = urls[:2]
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    temporary = INDEX.with_suffix(".tmp")
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(INDEX)
    _index = result
    return result


def german_sources(konami_id):
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                try:
                    _index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else refresh_index()
                except (httpx.HTTPError, OSError, ValueError):
                    # The existing official source remains available if this index fails.
                    _index = {}
    return [url for path in _index.get(str(konami_id), []) if (url := trusted_artwork_url(path))]
