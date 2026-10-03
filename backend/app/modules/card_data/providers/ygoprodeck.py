from typing import Any

import httpx


class YgoProDeckProvider:
    """Development fallback provider; stores metadata only and never downloads images."""

    name = "ygoprodeck"
    card_feed_url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    set_feed_url = "https://db.ygoprodeck.com/api/v7/cardsets.php"

    def fetch_cards(self) -> list[dict[str, Any]]:
        response = httpx.get(self.card_feed_url, timeout=60)
        response.raise_for_status()
        return response.json().get("data", [])

    def fetch_sets(self) -> list[dict[str, Any]]:
        response = httpx.get(self.set_feed_url, timeout=60)
        response.raise_for_status()
        return response.json()

    def fetch_packs(self) -> list[dict[str, Any]]:
        """The official cardsets feed is the supported pack/set catalog source."""
        return self.fetch_sets()

    def fetch_database_version(self) -> dict[str, Any]:
        response = httpx.get("https://db.ygoprodeck.com/api/v7/checkDBVer.php", timeout=20)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def image_url(external_id: str) -> str:
        return f"https://images.ygoprodeck.com/images/cards/{external_id}.jpg"
