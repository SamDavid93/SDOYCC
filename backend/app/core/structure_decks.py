"""Fixed quantities are independent of random booster weights."""


def deck_entries(pack):
    deck = pack.deck
    if not deck or not deck.source or not deck.content_hash or not deck.items:
        return []
    if any(item.quantity < 1 or item.quantity > 100 for item in deck.items):
        return []
    if any(not slot.name or not 1 <= len(slot.choices) <= 30 or
           len({(choice.card_id, choice.rarity) for choice in slot.choices}) != len(slot.choices)
           for slot in deck.bonus_slots):
        return []
    if not 1 <= deck.card_count <= 100 or sum(item.quantity for item in deck.items) + len(deck.bonus_slots) != deck.card_count:
        return []
    return deck.items


def deck_size(pack):
    return pack.deck.card_count if deck_entries(pack) else 0


def deck_candidates(pack):
    entries = deck_entries(pack)
    if not entries:
        return []
    return [*entries, *(choice for slot in pack.deck.bonus_slots for choice in slot.choices)]


def draw_deck(pack):
    import random
    entries = deck_entries(pack)
    if not entries:
        raise ValueError('Ungültige Deckliste')
    result = [entry for entry in entries for _ in range(entry.quantity)]
    # Only bonus slots draw randomly; every fixed copy is always granted.
    for slot in pack.deck.bonus_slots:
        result.append(random.SystemRandom().choice(slot.choices))
    return result


def product_rules(pack, purchased=0):
    from app.core.pricing import purchase_limit
    limit = purchase_limit(pack.product_type)
    is_deck = pack.product_type == 'structure_deck'
    entries = deck_entries(pack) if is_deck else []
    return {"product_type": pack.product_type, "purchase_limit": limit,
            "fixed_cards": sum(item.quantity for item in entries),
            "bonus_cards": len(pack.deck.bonus_slots) if entries else 0,
            "content_notes": pack.deck.notes if is_deck and pack.deck else None,
            "purchased_total": purchased,
            "purchases_remaining": max(0, limit - purchased) if limit is not None else None}
