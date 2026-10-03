import httpx


class CardClusterProvider:
    name = "cardcluster"

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url

    def _configured(self) -> None:
        if not self.base_url:
            raise RuntimeError("CardCluster provider URL is not configured")

    def search_cards(self, query: str = "") -> list[dict]:
        self._configured()
        response = httpx.get(f"{self.base_url}/cards", params={"search": query}, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_card(self, external_id: str) -> dict | None:
        self._configured()
        response = httpx.get(f"{self.base_url}/cards/{external_id}", timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_latest_updates(self) -> list[dict]:
        self._configured()
        response = httpx.get(f"{self.base_url}/cards/latest", timeout=10)
        response.raise_for_status()
        return response.json()
