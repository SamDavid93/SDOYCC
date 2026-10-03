"""Enrich existing IDs without changing accounts, owned cards or booster pools."""
import json
from pathlib import Path
import httpx
from sqlalchemy import select
from app.db.models import Card, CardDetails
from app.db.session import SessionLocal, migrate_local_schema


def sync_german(english, german, session_factory=SessionLocal):
    by_id = {str(item["id"]): item for item in english}
    de_by_id = {str(item["id"]): item for item in german}
    en_by_name = {item.get("name"): item for item in english}
    en_by_konami = {meta["konami_id"]: item for item in english for meta in item.get("misc_info", []) if meta.get("konami_id")}
    for source, mapping in [(english, by_id), (german, de_by_id)]:
        for item in source:
            for artwork in item.get("card_images", []):
                mapping.setdefault(str(artwork["id"]), item)
    if not by_id or not de_by_id:
        raise ValueError("Leere Übersetzungsquelle wird nicht importiert")
    count = 0
    with session_factory() as db:
        for card in db.scalars(select(Card)):
            raw = by_id.get(card.external_id) or de_by_id.get(card.external_id)
            if not raw:
                continue
            translated = de_by_id.get(card.external_id, {})
            details = card.details or CardDetails(card_id=card.id)
            details.name_de = translated.get("name") or details.name_de
            details.description_de = translated.get("desc") or details.description_de
            details.race = raw.get("race")
            details.archetype = raw.get("archetype")
            details.level = raw.get("level")
            details.atk = raw.get("atk")
            details.defense = raw.get("def")
            details.scale = raw.get("scale")
            details.link_value = raw.get("linkval")
            details.link_markers = json.dumps(raw.get("linkmarkers", []))
            details.ban_status = raw.get("banlist_info", {}).get("ban_tcg", "Unlimited")
            details.konami_id = next((item.get("konami_id") for item in raw.get("misc_info", []) if item.get("konami_id")), None)
            original = by_id.get(card.external_id) or en_by_konami.get(details.konami_id) or en_by_name.get(card.name)
            if original and original.get("desc"):
                details.description_en = original["desc"]
            db.add(details)
            count += bool(details.name_de)
        db.commit()
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deutsche Kartendaten ergänzen")
    parser.add_argument("--refresh", action="store_true", help="Quelldaten neu herunterladen")
    args = parser.parse_args()
    migrate_local_schema()
    cache = Path("artifacts")
    cache.mkdir(exist_ok=True)
    sources = []
    for language in ["en", "de"]:
        target = cache / f"catalog-{language}.json"
        if args.refresh or not target.exists():
            params = {"misc": "yes"}
            if language == "de":
                params["language"] = "de"
            response = httpx.get("https://db.ygoprodeck.com/api/v7/cardinfo.php", params=params, timeout=90)
            response.raise_for_status()
            target.write_bytes(response.content)
        sources.append(json.loads(target.read_bytes())["data"])
    print(f"Kartentexte aktualisiert; {sync_german(*sources)} bestehende Karten haben einen deutschen Namen.")
