from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    twitch_id: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    inventory: Mapped[list["InventoryItem"]] = relationship(back_populates="user")


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_provider: Mapped[str] = mapped_column(String(40), default="local")
    external_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    card_set: Mapped[str] = mapped_column(String(160))
    set_code: Mapped[str] = mapped_column(String(40))
    rarity: Mapped[str] = mapped_column(String(50))
    card_type: Mapped[str] = mapped_column(String(80))
    attribute: Mapped[str] = mapped_column(String(30))
    image_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    details: Mapped["CardDetails | None"] = relationship(lazy="joined", uselist=False)


class CardDetails(Base):
    __tablename__ = "card_details"
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    name_de: Mapped[str | None] = mapped_column(String(200), index=True)
    description_de: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    race: Mapped[str | None] = mapped_column(String(80), index=True)
    archetype: Mapped[str | None] = mapped_column(String(100), index=True)
    level: Mapped[int | None] = mapped_column(Integer)
    atk: Mapped[int | None] = mapped_column(Integer)
    defense: Mapped[int | None] = mapped_column(Integer)
    scale: Mapped[int | None] = mapped_column(Integer)
    link_value: Mapped[int | None] = mapped_column(Integer)
    link_markers: Mapped[str | None] = mapped_column(Text)
    ban_status: Mapped[str | None] = mapped_column(String(40))
    konami_id: Mapped[int | None] = mapped_column(Integer, index=True)


class CardSet(Base):
    __tablename__ = "card_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_provider: Mapped[str] = mapped_column(String(40), default="local")
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    card_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class CardPrinting(Base):
    __tablename__ = "card_printings"
    __table_args__ = (UniqueConstraint("external_provider", "external_printing_id", name="uq_card_printing_provider_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    set_id: Mapped[int | None] = mapped_column(ForeignKey("card_sets.id"), nullable=True)
    external_provider: Mapped[str] = mapped_column(String(40), default="local")
    external_printing_id: Mapped[str] = mapped_column(String(150))
    set_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rarity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_rarity_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("user_id", "card_id", name="uq_inventory_user_card"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    user: Mapped[User] = relationship(back_populates="inventory")
    card: Mapped[Card] = relationship()


class BoosterPack(Base):
    __tablename__ = "booster_packs"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    set_id: Mapped[int | None] = mapped_column(ForeignKey("card_sets.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cards_per_pack: Mapped[int] = mapped_column(Integer, default=5)
    product_type: Mapped[str] = mapped_column(String(30), default="booster", server_default="booster")
    cost: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    entries: Mapped[list["BoosterPoolEntry"]] = relationship(back_populates="booster", cascade="all, delete-orphan")
    card_set: Mapped["CardSet | None"] = relationship()
    deck: Mapped["StructureDeckDefinition | None"] = relationship(cascade="all, delete-orphan")


class StructureDeckDefinition(Base):
    __tablename__ = "structure_deck_definitions"
    booster_id: Mapped[int] = mapped_column(ForeignKey("booster_packs.id"), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    card_count: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    items: Mapped[list["StructureDeckItem"]] = relationship(cascade="all, delete-orphan", order_by="StructureDeckItem.id")
    bonus_slots: Mapped[list["StructureDeckBonusSlot"]] = relationship(cascade="all, delete-orphan", order_by="StructureDeckBonusSlot.id")


class StructureDeckBonusSlot(Base):
    __tablename__ = "structure_deck_bonus_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    booster_id: Mapped[int] = mapped_column(ForeignKey("structure_deck_definitions.booster_id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    choices: Mapped[list["StructureDeckBonusChoice"]] = relationship(cascade="all, delete-orphan", order_by="StructureDeckBonusChoice.id")


class StructureDeckBonusChoice(Base):
    __tablename__ = "structure_deck_bonus_choices"
    __table_args__ = (UniqueConstraint("slot_id", "card_id", "rarity", name="uq_structure_bonus_choice"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("structure_deck_bonus_slots.id"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    rarity: Mapped[str] = mapped_column(String(50))
    card: Mapped[Card] = relationship()


class CardVariant(Base):
    __tablename__ = "card_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    rarity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    booster_id: Mapped[int | None] = mapped_column(ForeignKey("booster_packs.id"), nullable=True)
    printing_id: Mapped[int | None] = mapped_column(ForeignKey("card_printings.id"), nullable=True)
    legacy: Mapped[bool] = mapped_column(Boolean, default=False)


class VariantInventory(Base):
    __tablename__ = "variant_inventory"
    __table_args__ = (UniqueConstraint("user_id", "variant_id", "bound", name="uq_variant_owner_bound"),
                     CheckConstraint("quantity >= 0 AND reserved >= 0 AND reserved <= quantity", name="ck_variant_stock"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("card_variants.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    bound: Mapped[bool] = mapped_column(Boolean, default=False)


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("card_variants.id"))
    bound: Mapped[bool] = mapped_column(Boolean, default=False)
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str] = mapped_column(String(180), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StructureDeckItem(Base):
    __tablename__ = "structure_deck_items"
    __table_args__ = (UniqueConstraint("booster_id", "card_id", "rarity", name="uq_structure_card_rarity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    booster_id: Mapped[int] = mapped_column(ForeignKey("structure_deck_definitions.booster_id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    rarity: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer)
    card: Mapped[Card] = relationship()


class BoosterPoolEntry(Base):
    __tablename__ = "booster_pool_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    booster_id: Mapped[int] = mapped_column(ForeignKey("booster_packs.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    rarity: Mapped[str] = mapped_column(String(50))
    weight: Mapped[float] = mapped_column(Float, default=1)
    booster: Mapped[BoosterPack] = relationship(back_populates="entries")
    card: Mapped[Card] = relationship()


class UserBooster(Base):
    __tablename__ = "user_boosters"
    __table_args__ = (UniqueConstraint("user_id", "booster_id", name="uq_user_booster"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    booster_id: Mapped[int] = mapped_column(ForeignKey("booster_packs.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)


class ProductPurchaseCounter(Base):
    __tablename__ = "product_purchase_counters"
    __table_args__ = (UniqueConstraint("user_id", "booster_id", name="uq_purchase_counter_user_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    booster_id: Mapped[int] = mapped_column(ForeignKey("booster_packs.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)


class BoosterOpening(Base):
    __tablename__ = "booster_openings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    booster_id: Mapped[int] = mapped_column(ForeignKey("booster_packs.id"))
    credits_spent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    cards: Mapped[list["BoosterOpeningCard"]] = relationship(back_populates="opening", cascade="all, delete-orphan")
    booster: Mapped["BoosterPack"] = relationship()


class BoosterOpeningCard(Base):
    __tablename__ = "booster_opening_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    opening_id: Mapped[int] = mapped_column(ForeignKey("booster_openings.id"))
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    rarity: Mapped[str] = mapped_column(String(50))
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    opening: Mapped[BoosterOpening] = relationship(back_populates="cards")
    card: Mapped[Card] = relationship()


class TradeListing(Base):
    __tablename__ = "trade_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    card: Mapped[Card] = relationship()


class BattlePassProgress(Base):
    __tablename__ = "battle_pass_progress"
    __table_args__ = (UniqueConstraint("user_id", "season_key", name="uq_battle_pass_user_season"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    season_key: Mapped[str] = mapped_column(String(80))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)


class DiamondTransaction(Base):
    __tablename__ = "diamond_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ActionReceipt(Base):
    __tablename__ = "action_receipts"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_action_user_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(150))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    details_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AdminMutationLock(Base):
    __tablename__ = "admin_mutation_lock"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)


class Grant(Base):
    __tablename__ = "grants"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))
    payload_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class GrantItem(Base):
    __tablename__ = "grant_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey("grants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("card_variants.id"), nullable=True)
    booster_id: Mapped[int | None] = mapped_column(ForeignKey("booster_packs.id"), nullable=True)
    bound: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey("grants.id"), unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    username: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class RegistrationChallenge(Base):
    __tablename__ = "registration_challenges"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    username: Mapped[str] = mapped_column(String(64))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class TwitchRedemption(Base):
    __tablename__ = "twitch_redemptions"
    redemption_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reward_id: Mapped[str] = mapped_column(String(100))
    diamonds: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class HubNotice(Base):
    __tablename__ = "hub_notices"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SpecialCard(Base):
    __tablename__ = "special_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="draft")
    description: Mapped[str] = mapped_column(Text)
    edition: Mapped[str] = mapped_column(String(120))
    tradable: Mapped[bool] = mapped_column(Boolean, default=True)
    supply_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued: Mapped[int] = mapped_column(Integer, default=0)
    image_data: Mapped[str] = mapped_column(Text)
    image_type: Mapped[str] = mapped_column(String(30))


class GrantBatch(Base):
    __tablename__ = "grant_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    items_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class GrantBatchRow(Base):
    __tablename__ = "grant_batch_rows"
    __table_args__ = (UniqueConstraint("batch_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("grant_batches.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    result_json: Mapped[str] = mapped_column(Text, default="{}")


class MarketListing(Base):
    __tablename__ = "market_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(1000))
    offered_json: Mapped[str] = mapped_column(Text)
    wanted_json: Mapped[str] = mapped_column(Text)
    set_snapshot_json: Mapped[str] = mapped_column(Text, default="null")
    state: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MarketProposal(Base):
    __tablename__ = "market_proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    items_json: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MarketCardIndex(Base):
    __tablename__ = "market_card_index"
    __table_args__ = (UniqueConstraint("listing_id", "side", "variant_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    side: Mapped[str] = mapped_column(String(10))
    variant_key: Mapped[int] = mapped_column(Integer)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    rarity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)


class MarketRevision(Base):
    __tablename__ = "market_revisions"
    __table_args__ = (UniqueConstraint("listing_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (UniqueConstraint("reference", "variant_id"), CheckConstraint("quantity > 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("card_variants.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(80), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TradeSettlement(Base):
    __tablename__ = "trade_settlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"), unique=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("market_proposals.id"), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TradeReport(Base):
    __tablename__ = "trade_reports"
    __table_args__ = (UniqueConstraint("listing_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(20), default="open")


class TradeBlock(Base):
    __tablename__ = "trade_blocks"
    __table_args__ = (UniqueConstraint("user_id", "blocked_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TradeRestriction(Base):
    __tablename__ = "trade_restrictions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    until: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(500))


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(1000))
    state: Mapped[str] = mapped_column(String(20), default="draft")
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    claim_until: Mapped[datetime] = mapped_column(DateTime)
    rules_json: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class SeasonProgress(Base):
    __tablename__ = "season_progress"
    __table_args__ = (UniqueConstraint("season_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    xp: Mapped[int] = mapped_column(Integer, default=0)


class SeasonXpEvent(Base):
    __tablename__ = "season_xp_events"
    __table_args__ = (UniqueConstraint("season_id", "user_id", "reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reference: Mapped[str] = mapped_column(String(100))
    xp: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SeasonClaim(Base):
    __tablename__ = "season_claims"
    __table_args__ = (UniqueConstraint("season_id", "user_id", "level"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    level: Mapped[int] = mapped_column(Integer)
    grant_id: Mapped[int] = mapped_column(ForeignKey("grants.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
