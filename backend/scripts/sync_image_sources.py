"""Refresh German artwork lookup and fill missing names without altering ownership."""
import argparse
import json
from pathlib import Path
import httpx
from sqlalchemy import select
from app.db.models import CardDetails
from app.db.session import SessionLocal
from app.modules.image_sources import refresh_index


def fill_missing_names(names, session_factory=SessionLocal):
    by_id = {int(cid): name for name, ids in names.items() for cid in ids if name.strip()}
    count = 0
    with session_factory() as db:
        for details in db.scalars(select(CardDetails).where(CardDetails.name_de.is_(None) | (CardDetails.name_de == ""))):
            if details.konami_id in by_id:
                details.name_de = by_id[details.konami_id]
                count += 1
        db.commit()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deutsche Bildquellen und fehlende Namen ergänzen")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    folder = Path("artifacts")
    folder.mkdir(exist_ok=True)
    for filename, url in [
        ("artworks-manifest.json", "https://artworks.ygoresources.com/manifest.json"),
        ("ygoresources-names-de.json", "https://db.ygoresources.com/data/idx/card/name/de"),
    ]:
        target = folder / filename
        if args.refresh or not target.exists():
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            response.json()  # Validate before replacing the last working cache.
            target.write_bytes(response.content)
            if response.headers.get("X-Cache-Revision"):
                target.with_suffix(".revision").write_text(response.headers["X-Cache-Revision"])
    index = refresh_index(json.loads((folder / "artworks-manifest.json").read_bytes()))
    names = fill_missing_names(json.loads((folder / "ygoresources-names-de.json").read_bytes()))
    print(f"Deutsche Bildquellen für {len(index)} Konami-Karten erfasst; {names} fehlende deutsche Namen ergänzt.")
