"""Server-owned product prices and lifetime purchase limits."""

BOOSTER_PRICE = 100
STRUCTURE_DECK_PRICE = BOOSTER_PRICE * 6
STRUCTURE_DECK_LIMIT = 3


def product_type_for_name(name: str) -> str:
    name = name.casefold()
    # Companion promotional sets are not complete Structure Decks.
    if 'structure deck' in name and not any(part in name for part in ('special edition', 'special set', 'deluxe edition')):
        return 'structure_deck'
    return 'booster'


def product_price(product_type: str) -> int:
    return STRUCTURE_DECK_PRICE if product_type == 'structure_deck' else BOOSTER_PRICE


def purchase_limit(product_type: str) -> int | None:
    return STRUCTURE_DECK_LIMIT if product_type == 'structure_deck' else None
