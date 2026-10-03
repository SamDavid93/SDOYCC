"""Shared effective pack size; rarity variants do not multiply card identities."""
import math
import sys

MAX_WEIGHT = sys.float_info.max


def drawable_entries(entries):
    entries = list(entries)
    if any(not math.isfinite(entry.weight) or entry.weight < 0 for entry in entries):
        return []
    return [entry for entry in entries if entry.weight > 0]


def effective_pack_size(configured: int, pool_size: int) -> int:
    return max(0, min(configured, pool_size))


def pool_size(entries) -> int:
    return len({entry.card_id for entry in entries})
