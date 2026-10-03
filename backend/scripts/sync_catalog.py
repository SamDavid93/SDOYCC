from sqlalchemy import select

from app.db.models import Card, CardDetails, CardPrinting, CardSet
from app.db.session import SessionLocal, migrate_local_schema
from app.modules.card_data.boosters import sync_set_boosters
from app.modules.card_data.providers.ygoprodeck import YgoProDeckProvider


def normalize_rarity(value: str | None) -> str:
    normalized = (value or "other").lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "common": "common",
        "rare": "rare",
        "super_rare": "super_rare",
        "ultra_rare": "ultra_rare",
        "secret_rare": "secret_rare",
        "ultimate_rare": "ultimate_rare",
        "ghost_rare": "ghost_rare",
        "starlight_rare": "starlight_rare",
        "quarter_century_secret_rare": "quarter_century_secret_rare",
        "platinum_secret_rare": "platinum_secret_rare",
    }
    return aliases.get(normalized, "other")


def first_set(card_data: dict) -> dict:
    sets = card_data.get("card_sets") or []
    return sets[0] if sets else {}


def sync_catalog(provider=None, session_factory=SessionLocal) -> tuple[int, int, int]:
    provider = provider or YgoProDeckProvider()
    remote_sets = provider.fetch_sets()
    remote_cards = provider.fetch_cards()
    if not remote_sets or not remote_cards:
        raise ValueError("Refusing an empty catalog import")
    with session_factory() as database:
        existing_sets = {item.external_id: item for item in database.scalars(select(CardSet))}
        existing_sets_by_name = {item.name: item for item in existing_sets.values()}
        for remote in remote_sets:
            set_name = remote.get("set_name") or "Unknown set"
            set_code = remote.get("set_code") or "no-code"
            external_id = f"{set_code}:{set_name}"
            item = existing_sets.get(external_id)
            if item is None:
                item = CardSet(external_provider=provider.name, external_id=external_id, name=set_name)
                database.add(item)
                existing_sets[external_id] = item
            existing_sets_by_name[set_name] = item
            item.name = set_name
            item.code = remote.get("set_code")
            item.release_date = remote.get("tcg_date")
            item.card_count = remote.get("num_of_cards")
            item.cover_image_url = remote.get("set_image")
        database.flush()

        existing_cards = {item.external_id: item for item in database.scalars(select(Card)).all()}
        existing_printings = {item.external_printing_id: item for item in database.scalars(select(CardPrinting)).all()}
        printing_count = 0
        for remote in remote_cards:
            external_id = str(remote["id"])
            remote_set = first_set(remote)
            card = existing_cards.get(external_id)
            if card is None:
                card = Card(external_provider=provider.name, external_id=external_id, name=remote.get("name") or "Unknown card", card_set=remote_set.get("set_name") or "Unknown set", set_code=remote_set.get("set_code") or "", rarity=normalize_rarity(remote_set.get("set_rarity")), card_type=remote.get("type") or "", attribute=remote.get("attribute") or "", image_url=provider.image_url(external_id))
                database.add(card)
                existing_cards[external_id] = card
            else:
                card.name = remote.get("name") or card.name
                card.card_set = remote_set.get("set_name") or card.card_set
                card.set_code = remote_set.get("set_code") or card.set_code
                card.rarity = normalize_rarity(remote_set.get("set_rarity"))
                card.card_type = remote.get("type") or card.card_type
                card.attribute = remote.get("attribute") or card.attribute
                card.image_url = provider.image_url(external_id)
            database.flush()
            if remote.get("desc"):
                details = card.details or CardDetails(card_id=card.id)
                details.description_en = remote["desc"]
                database.add(details)
            for printing in remote.get("card_sets") or []:
                printing_id = f"{external_id}:{printing.get('set_code', printing.get('set_name', 'unknown'))}"
                set_id = str(printing.get("set_code") or printing.get("set_name"))
                linked_set = existing_sets_by_name.get(printing.get("set_name")) or existing_sets.get(set_id)
                record = existing_printings.get(printing_id)
                if record is None:
                    record = CardPrinting(card_id=card.id, set_id=linked_set.id if linked_set else None, external_provider=provider.name, external_printing_id=printing_id)
                    database.add(record)
                    existing_printings[printing_id] = record
                record.card_id = card.id
                record.set_id = linked_set.id if linked_set else None
                record.set_code = printing.get("set_code")
                record.rarity = normalize_rarity(printing.get("set_rarity"))
                record.provider_rarity_name = printing.get("set_rarity")
                record.image_url = provider.image_url(external_id)
                printing_count += 1
        database.flush()
        sync_set_boosters(database)
        database.commit()
        return len(remote_cards), len(remote_sets), printing_count


if __name__ == "__main__":
    migrate_local_schema()
    cards, sets, printings = sync_catalog()
    print(f"Synced {cards} cards, {sets} sets, and {printings} printings. Images remain external URLs derived from card numbers.")
