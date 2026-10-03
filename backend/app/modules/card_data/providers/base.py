from typing import Protocol


class CardDataProvider(Protocol):
    name: str

    def search_cards(self, query: str = "") -> list[dict]: ...

    def get_card(self, external_id: str) -> dict | None: ...

    def get_latest_updates(self) -> list[dict]: ...
