from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Card


class LocalProvider:
    name = "local-demo"

    def __init__(self, database: Session):
        self.database = database

    def search_cards(self, query: str = "") -> list[dict]:
        statement = select(Card)
        if query:
            statement = statement.where(Card.name.ilike(f"%{query}%"))
        return list(self.database.scalars(statement).all())

    def get_card(self, external_id: str) -> Card | None:
        return self.database.scalar(select(Card).where(Card.external_id == external_id))

    def get_latest_updates(self) -> list[Card]:
        return list(self.database.scalars(select(Card).order_by(Card.updated_at.desc()).limit(50)).all())
