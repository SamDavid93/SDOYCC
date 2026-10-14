"""Nine-card standard boosters; preserve explicitly configured special packs.

Legacy standard size 5 is interpreted as 9 without rewriting owned packs or
historical openings. Fixed structure deck contents use their separate rules.
"""
import math
import sys
import random

MAX_WEIGHT = sys.float_info.max


def drawable_entries(entries):
    entries = list(entries)
    if any(not math.isfinite(entry.weight) or entry.weight < 0 for entry in entries):
        return []
    return [entry for entry in entries if entry.weight > 0]


def effective_pack_size(configured: int, pool_size: int) -> int:
    if configured in (5, 9):
        return 9 if pool_size else 0
    return max(0, min(configured, pool_size))


RARE_RARITIES = frozenset({
    'rare', 'super_rare', 'ultra_rare', 'secret_rare', 'ultimate_rare',
    'ghost_rare', 'platinum_secret_rare', 'starlight_rare',
    'quarter_century_secret_rare', 'prismatic_secret_rare', 'gold_rare',
    'gold_secret_rare', 'premium_gold_rare', 'platinum_rare',
    "collector's_rare", 'collectors_rare', 'collector_rare',
})


def is_rare(rarity):
    return rarity.strip().lower().replace(' ', '_') in RARE_RARITIES


def booster_size(configured, entries, override=None):
    entries = drawable_entries(entries)
    return available_pack_size(configured, pool_size(entries), any(is_rare(entry.rarity) for entry in entries), override)


def available_pack_size(configured, size, has_rare, override=None):
    if (configured in (5, 9) or override is not None) and not has_rare:
        return 0
    if override is not None:
        return override if size else 0
    return effective_pack_size(configured, size)


def draw_booster(configured, entries, override=None):
    entries = drawable_entries(entries)
    count = booster_size(configured, entries, override)
    if not count:
        raise ValueError('Kein gültiger Kartenpool mit erforderlicher Seltenheit')
    rng = random.SystemRandom()

    def choose(pool, amount):
        maximum = max(entry.weight for entry in pool)
        return rng.choices(pool, weights=[entry.weight / maximum for entry in pool], k=amount)

    if configured in (5, 9) or override is not None:
        return choose(entries, count - 1) + choose([entry for entry in entries if is_rare(entry.rarity)], 1)
    return choose(entries, count)


def pool_size(entries) -> int:
    return len({entry.card_id for entry in entries})
