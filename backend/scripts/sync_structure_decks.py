"""Check bundled deck definitions; --apply installs them without changing ownership."""
import argparse
import json
from app.db.session import SessionLocal
from app.modules.card_data.structure_decks import import_structure_decks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as database:
        report = import_structure_decks(database)
        if args.apply:
            database.commit()
        else:
            database.rollback()
        print(json.dumps({'applied': args.apply, **report}, ensure_ascii=True, indent=2))
