"""Back up local SQLite before applying the additive hub schema migration."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db import models  # Register all tables before create_all.
from app.db.session import engine, migrate_local_schema


def migrate() -> None:
    backup_path = None
    if engine.dialect.name == "sqlite" and engine.url.database and engine.url.database != ":memory:":
        path = Path(engine.url.database).resolve()
        if path.exists():
            directory = Path("artifacts/db-backups")
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = directory / f"{path.stem}-{stamp}.db"
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(backup_path) as backup:
                source.backup(backup)
    migrate_local_schema()
    print(json.dumps({"migration": "complete", "backup": str(backup_path) if backup_path else None}))


if __name__ == "__main__":
    migrate()
