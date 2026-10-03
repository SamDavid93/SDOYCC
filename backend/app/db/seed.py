import json
from pathlib import Path
from app.core.pricing import BOOSTER_PRICE, product_type_for_name, product_price
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BattlePassProgress, BoosterPack, BoosterPoolEntry, Card, CardDetails, CardPrinting, CardSet, DiamondTransaction, InventoryItem, TradeListing, User, UserBooster

CARD_SEED = [
    ("89631139", "Blue-Eyes White Dragon", "Legend of Blue Eyes", "LOB-001", "Ultra Rare", "Normal Monster", "LIGHT"),
    ("46986414", "Dark Magician", "Starter Deck Yugi", "SDY-006", "Rare", "Normal Monster", "DARK"),
    ("14558127", "Ash Blossom & Joyous Spring", "Maximum Crisis", "MACR-EN036", "Secret Rare", "Effect Monster", "FIRE"),
    ("74677422", "Red-Eyes Black Dragon", "Legend of Blue Eyes", "LOB-070", "Ultra Rare", "Normal Monster", "DARK"),
    ("86066372", "Accesscode Talker", "Eternity Code", "ETCO-EN046", "Secret Rare", "Link Monster", "DARK"),
    ("55144522", "Pot of Greed", "Metal Raiders", "MRD-040", "Common", "Normal Spell", "SPELL"),
]


def seed_database(database: Session) -> None:
    user = database.scalar(select(User).where(User.username == "jaden-demo"))
    if user is None:
        user = User(username="jaden-demo", display_name="Jaden D.", role="user", credits=2450)
        database.add(user)
        database.flush()

    if database.scalar(select(DiamondTransaction).where(DiamondTransaction.user_id == user.id)) is None:
        database.add(DiamondTransaction(user_id=user.id, amount=user.credits, balance_after=user.credits,
                                        reason="opening_balance", reference=f"opening-balance:{user.id}"))

    cards: list[Card] = []
    for external_id, name, card_set, set_code, rarity, card_type, attribute in CARD_SEED:
        card = database.scalar(select(Card).where(Card.external_id == external_id))
        if card is None:
            card = Card(external_provider="local-demo", external_id=external_id, name=name, card_set=card_set, set_code=set_code, rarity=rarity, card_type=card_type, attribute=attribute, image_url=f"https://images.ygoprodeck.com/images/cards/{external_id}.jpg")
            database.add(card)
            database.flush()
        cards.append(card)

    for card, quantity in zip(cards, [3, 2, 1, 4, 1, 6]):
        item = database.scalar(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.card_id == card.id))
        if item is None:
            database.add(InventoryItem(user_id=user.id, card_id=card.id, quantity=quantity))

    booster = database.scalar(select(BoosterPack).where(BoosterPack.key == "standard-booster"))
    linked_set = database.scalar(select(CardSet).where(CardSet.name == "Legend of Blue Eyes White Dragon"))
    if booster is None:
        booster = BoosterPack(key="standard-booster", set_id=linked_set.id if linked_set else None, image_url=linked_set.cover_image_url if linked_set else None, name="SDOYCC Origins", cards_per_pack=5, cost=BOOSTER_PRICE)
        database.add(booster)
        database.flush()
        for card in cards:
            database.add(BoosterPoolEntry(booster_id=booster.id, card_id=card.id, rarity=card.rarity, weight=1 if card.rarity != "Common" else 4))
    elif linked_set and booster.set_id is None:
        booster.set_id = linked_set.id
        booster.image_url = linked_set.cover_image_url
        set_cards = database.scalars(select(Card).join(CardPrinting, CardPrinting.card_id == Card.id).where(CardPrinting.set_id == linked_set.id).distinct()).all()
        if set_cards:
            for entry in list(booster.entries):
                database.delete(entry)
            database.flush()
            for card in set_cards:
                database.add(BoosterPoolEntry(booster_id=booster.id, card_id=card.id, rarity=card.rarity, weight=1 if card.rarity in {"common", "rare"} else 0.35))

    # Every synchronized set gets a purchasable set booster when no product exists yet.
    existing_set_ids = {pack.set_id for pack in database.scalars(select(BoosterPack).where(BoosterPack.set_id.is_not(None))).all()}
    for card_set in database.scalars(select(CardSet).order_by(CardSet.id)).all():
        if card_set.id in existing_set_ids:
            continue
        set_cards = database.scalars(select(Card).join(CardPrinting, CardPrinting.card_id == Card.id).where(CardPrinting.set_id == card_set.id).distinct()).all()
        if not set_cards:
            continue
        kind = product_type_for_name(card_set.name)
        set_booster = BoosterPack(key=f"set-booster-{card_set.id}", set_id=card_set.id, image_url=card_set.cover_image_url, name=card_set.name if kind == 'structure_deck' else f"{card_set.name} Booster", product_type=kind, cards_per_pack=5, cost=product_price(kind))
        database.add(set_booster)
        database.flush()
        for card in set_cards:
            rarity = card.rarity or "other"
            database.add(BoosterPoolEntry(booster_id=set_booster.id, card_id=card.id, rarity=rarity, weight=1 if rarity in {"common", "rare"} else 0.35))

    for pack in database.scalars(select(BoosterPack).where(BoosterPack.set_id.is_not(None))).all():
        if pack.card_set and pack.card_set.cover_image_url:
            pack.image_url = pack.card_set.cover_image_url

    stock = database.scalar(select(UserBooster).where(UserBooster.user_id == user.id, UserBooster.booster_id == booster.id))
    if stock is None:
        database.add(UserBooster(user_id=user.id, booster_id=booster.id, quantity=4))

    listing = database.scalar(select(TradeListing).where(TradeListing.title == "Looking for Blue-Eyes"))
    if listing is None:
        database.add(TradeListing(creator_id=user.id, title="Looking for Blue-Eyes", description="Demo listing", card_id=cards[3].id, quantity=1))

    progress = database.scalar(select(BattlePassProgress).where(BattlePassProgress.user_id == user.id, BattlePassProgress.season_key == "season-1"))
    if progress is None:
        database.add(BattlePassProgress(user_id=user.id, season_key="season-1", xp=2460, level=18))
    database.commit()

    # Verified German metadata for starter cards, including isolated offline databases.
    translations = json.loads(Path(__file__).with_name('demo_de.json').read_text(encoding='utf-8'))
    for card in database.scalars(select(Card).where(Card.external_id.in_(translations))):
        if database.get(CardDetails, card.id) is None:
            database.add(CardDetails(card_id=card.id, **translations[card.external_id]))
    database.commit()
