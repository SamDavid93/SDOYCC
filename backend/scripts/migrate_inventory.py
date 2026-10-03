"""Run with the backend stopped and after migrate_database.py made a backup."""
import argparse
import json

from app.db.session import SessionLocal
from app.modules.inventory import migrate_inventory


def main():
    parser = argparse.ArgumentParser(description="Variantenbestand prüfen und übernehmen")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as database:
        result = migrate_inventory(database)
        if args.apply:
            database.commit()
        else:
            database.rollback()
        print(json.dumps({"applied": args.apply, **result}))


if __name__ == "__main__":
    main()
