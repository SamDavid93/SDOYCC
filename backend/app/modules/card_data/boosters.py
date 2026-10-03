from collections import defaultdict

from app.core.pricing import BOOSTER_PRICE, product_type_for_name, product_price

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BoosterPack, BoosterPoolEntry, CardPrinting, CardSet


def sync_set_boosters(database: Session) -> None:
    """Update generated products without deleting their IDs or owned stock."""
    printings_by_set = defaultdict(dict)
    for printing in database.scalars(select(CardPrinting).where(CardPrinting.set_id.is_not(None)).order_by(CardPrinting.id)):
        printings_by_set[printing.set_id].setdefault(printing.card_id, printing)
    packs = database.scalars(select(BoosterPack)).all()
    by_key = {pack.key: pack for pack in packs}
    linked_sets = {pack.set_id for pack in packs}
    entries_by_pack = defaultdict(dict)
    for entry in database.scalars(select(BoosterPoolEntry)):
        entries_by_pack[entry.booster_id][entry.card_id] = entry
    for card_set in database.scalars(select(CardSet)):
        printings = printings_by_set.get(card_set.id)
        if not printings:
            continue
        key = f"set-booster-{card_set.id}"
        pack = by_key.get(key)
        if pack is None:
            if card_set.id in linked_sets:
                continue  # Preserve deliberately configured custom products.
            pack = BoosterPack(key=key, set_id=card_set.id, name=f"{card_set.name} Booster", cost=BOOSTER_PRICE, cards_per_pack=5)
            database.add(pack)
            database.flush()
        pack.product_type = product_type_for_name(card_set.name)
        pack.cost = product_price(pack.product_type)
        pack.name = card_set.name if pack.product_type == 'structure_deck' else f"{card_set.name} Booster"
        pack.image_url = card_set.cover_image_url
        for card_id, printing in printings.items():
            rarity = printing.rarity or "other"
            entry = entries_by_pack[pack.id].get(card_id)
            if entry is None:
                entry = BoosterPoolEntry(booster_id=pack.id, card_id=card_id)
                database.add(entry)
            entry.rarity = rarity
            entry.weight = 1 if rarity in {"common", "rare"} else 0.35
