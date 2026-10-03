from datetime import datetime, timezone

from app.core.config import settings


class CardCatalogService:
    def __init__(self) -> None:
        self.provider_name = settings.primary_card_provider
        self.last_sync_at: datetime | None = None
        self.last_sync_status = "seeded"

    def status(self) -> dict:
        return {"provider": self.provider_name, "cache": "database", "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None, "status": self.last_sync_status}

    def mark_sync(self, status: str = "completed") -> dict:
        self.last_sync_at = datetime.now(timezone.utc)
        self.last_sync_status = status
        return self.status()


catalog_service = CardCatalogService()
