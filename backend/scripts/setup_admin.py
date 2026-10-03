"""Preview by default. Run after the backed-up schema migration."""
import argparse
import json

from app.core.admin_setup import bootstrap_owner
from app.db.session import SessionLocal


def main():
    parser = argparse.ArgumentParser(description="Ersten SDOYCC-Hauptadministrator lokal einrichten")
    parser.add_argument("--twitch-id", required=True)
    parser.add_argument("--apply", action="store_true", help="Rolle und Prüfprotokoll dauerhaft speichern")
    args = parser.parse_args()
    with SessionLocal() as database:
        try:
            user = bootstrap_owner(database, args.twitch_id)
            result = {"user_id": user.id, "username": user.username, "role": user.role,
                      "applied": args.apply}
            if args.apply:
                database.commit()
            else:
                database.rollback()
            print(json.dumps(result))
        except ValueError as error:
            database.rollback()
            parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
