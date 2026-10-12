"""Read-only official/pinned EU comparison. Never enables or writes a profile."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_duel_rules import load_source
from app.modules.duel_region import official_limits, compare_limits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-list', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / 'artifacts/duel-probe')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    cards, pinned, _, name, _ = load_source(args.runtime)
    effective, official, unresolved = official_limits(json.loads(args.official_list.read_text(encoding='utf8')), cards)
    differences = compare_limits(cards, pinned, official)
    result = {'status': 'matched' if not differences and not unresolved else 'mismatch',
        'pinned_list': name, 'official_effective': effective, 'differences': differences,
        'unresolved': unresolved, 'production_modified': False, 'duels_enabled': False}
    encoded = json.dumps(result, ensure_ascii=True, indent=2)
    if args.output: args.output.write_text(encoded, encoding='utf8')
    print(encoded)
    return 0 if result['status'] == 'matched' else 1


if __name__ == '__main__': raise SystemExit(main())
