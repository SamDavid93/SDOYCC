"""Private deck drafts. No inventory mutation/reservation and no duel startup here."""
from collections import Counter, defaultdict
from datetime import datetime
import json
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.api import card_payload, current_user
from app.db.models import Card, CardDetails, DuelCardRule, DuelRuleProfile, InventoryItem, PlayerDeck, SpecialCard
from app.db.session import get_db
from app.modules.duel_rules import EXTRA_CARD_TYPES, MAIN_CARD_TYPES, digest, parse_ydk, profile_payload, rule_payload, stock_for, stock_query, validate_deck
from app.modules.economy import finish, lock_wallet, replay

router = APIRouter(prefix='/api/decks', tags=['Decks'])
Database = Annotated[Session, Depends(get_db)]
Key = Annotated[str | None, Header(alias='Idempotency-Key')]


class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    card_id: int = Field(gt=0, strict=True)
    section: Literal['main', 'extra', 'side']
    quantity: int = Field(ge=1, le=200, strict=True)


class DeckData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    notes: str = Field(default='', max_length=1000)
    profile_id: str | None = Field(default=None, min_length=64, max_length=64)
    entries: list[Entry] = Field(default_factory=list, max_length=200)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value): raise ValueError('Deckname fehlt oder enthält Steuerzeichen.')
        return value.strip()


class SaveDeck(DeckData):
    version: int = Field(ge=1, strict=True)


class Version(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, strict=True)


class Archive(Version):
    archived: bool = Field(strict=True)


class YdkRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(max_length=100_000)
    profile_id: str = Field(min_length=64, max_length=64)


def get_profile(db, profile_id):
    profile = db.get(DuelRuleProfile, profile_id) if profile_id else None
    if profile_id and profile is None: raise HTTPException(400, 'Der gewählte Regelstand existiert nicht.')
    return profile


def own_deck(db, user_id, deck_id, version=None):
    deck = db.scalar(select(PlayerDeck).where(PlayerDeck.id == deck_id, PlayerDeck.user_id == user_id).execution_options(populate_existing=True))
    if deck is None: raise HTTPException(404, 'Deck nicht gefunden.')
    if version is not None and deck.version != version:
        raise HTTPException(409, 'Dieses Deck wurde inzwischen verändert. Lade den aktuellen Stand; dein Entwurf wurde nicht überschrieben.')
    return deck


def normalize(db, entries):
    counts = Counter()
    for entry in entries: counts[(entry.section, entry.card_id)] += entry.quantity
    if sum(counts.values()) > 200: raise HTTPException(400, 'Ein Entwurf darf höchstens 200 Karten enthalten.')
    ids = {card_id for _, card_id in counts}
    allowed = set(db.scalars(select(Card.id).where(Card.id.in_(ids), ~Card.id.in_(select(SpecialCard.card_id).where(SpecialCard.state == 'draft'))))) if ids else set()
    if allowed != ids: raise HTTPException(400, 'Der Entwurf enthält unbekannte oder nicht veröffentlichte Karten.')
    return [{'section': section, 'card_id': card_id, 'quantity': quantity} for (section, card_id), quantity in sorted(counts.items())]


def check_capacity(db, user_id, total=True):
    active = db.scalar(select(func.count()).select_from(PlayerDeck).where(PlayerDeck.user_id == user_id, PlayerDeck.archived.is_(False)))
    if active >= 30: raise HTTPException(409, 'Höchstens 30 aktive Decks. Archiviere zuerst ein Deck.')
    if total and db.scalar(select(func.count()).select_from(PlayerDeck).where(PlayerDeck.user_id == user_id)) >= 200:
        raise HTTPException(409, 'Höchstens 200 Decks einschließlich Archiv. Lösche zuerst einen alten Entwurf.')


def summary(deck):
    entries = json.loads(deck.entries_json)
    return {'id': deck.id, 'name': deck.name, 'notes': deck.notes, 'profile_id': deck.profile_id,
            'version': deck.version, 'archived': deck.archived, 'created_at': deck.created_at.isoformat() + 'Z',
            'updated_at': deck.updated_at.isoformat() + 'Z',
            'counts': {s: sum(e['quantity'] for e in entries if e['section'] == s) for s in ('main', 'extra', 'side')}}


def detail(db, deck):
    entries = json.loads(deck.entries_json)
    ids = {e['card_id'] for e in entries}
    cards = {card.id: card_payload(card) for card in db.scalars(select(Card).where(Card.id.in_(ids)))} if ids else {}
    profile = get_profile(db, deck.profile_id)
    return {**summary(deck), 'entries': entries, 'cards': cards, 'profile': profile_payload(profile),
            'validation': validate_deck(db, deck.user_id, entries, profile)}


@router.get('/profiles')
def profiles(db: Database, user=Depends(current_user)):
    return [profile_payload(p) for p in db.scalars(select(DuelRuleProfile).order_by(DuelRuleProfile.created_at.desc(), DuelRuleProfile.id))]


@router.get('/catalog')
def catalog(db: Database, user=Depends(current_user), profile_id: str | None = None,
            search: str = Query('', max_length=150), scope: Literal['available', 'owned', 'all'] = 'available',
            group: Literal['all', 'monster', 'spell', 'trap', 'extra', 'unknown'] = 'all',
            attribute: str = '', race: str = '', archetype: str = '', level: int | None = None,
            atk: int | None = None, defense: int | None = None, scale: int | None = None, link_value: int | None = None,
            copy_limit: int | None = Query(None, ge=0, le=3),
            page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=60)):
    get_profile(db, profile_id)
    stocks = stock_query(user.id)
    verified = stocks.c.quantity == InventoryItem.quantity
    available = case((verified, func.coalesce(stocks.c.available, 0)), else_=0)
    query = select(Card.id).outerjoin(CardDetails, CardDetails.card_id == Card.id).outerjoin(
        InventoryItem, and_(InventoryItem.card_id == Card.id, InventoryItem.user_id == user.id)).outerjoin(
        stocks, stocks.c.card_id == Card.id).outerjoin(DuelCardRule, and_(DuelCardRule.card_id == Card.id, DuelCardRule.profile_id == profile_id)).where(
        ~Card.id.in_(select(SpecialCard.card_id).where(SpecialCard.state == 'draft')))
    if scope == 'available': query = query.where(available > 0)
    elif scope == 'owned': query = query.where(InventoryItem.quantity > 0)
    if search:
        term = '%' + search + '%'
        query = query.where(or_(Card.name.ilike(term), CardDetails.name_de.ilike(term), CardDetails.description_de.ilike(term), CardDetails.description_en.ilike(term), Card.external_id == search))
    if group in ('monster', 'spell', 'trap'):
        catalog_types = (MAIN_CARD_TYPES | EXTRA_CARD_TYPES) - {'Spell Card', 'Trap Card'} if group == 'monster' else {'Spell Card' if group == 'spell' else 'Trap Card'}
        query = query.where(or_(DuelCardRule.type_bits.op('&')({'monster': 1, 'spell': 2, 'trap': 4}[group]) != 0, Card.card_type.in_(catalog_types)))
    elif group == 'extra': query = query.where(or_(DuelCardRule.section == 'extra', Card.card_type.in_(EXTRA_CARD_TYPES)))
    elif group == 'unknown': query = query.where(or_(DuelCardRule.status.is_(None), DuelCardRule.status != 'mapped'))
    for column, value in [(Card.attribute, attribute), (CardDetails.race, race), (CardDetails.archetype, archetype),
                          (CardDetails.level, level), (CardDetails.atk, atk), (CardDetails.defense, defense),
                          (CardDetails.scale, scale), (CardDetails.link_value, link_value), (DuelCardRule.copy_limit, copy_limit)]:
        if value is not None and value != '': query = query.where(column == value)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    ids = list(db.scalars(query.order_by(func.coalesce(CardDetails.name_de, Card.name), Card.id).offset((page-1)*page_size).limit(page_size)))
    cards = {card.id: card for card in db.scalars(select(Card).where(Card.id.in_(ids)))} if ids else {}
    rules = {r.card_id: r for r in db.scalars(select(DuelCardRule).where(DuelCardRule.profile_id == profile_id, DuelCardRule.card_id.in_(ids)))} if ids else {}
    stock = stock_for(db, user.id, ids)
    return {'total': total, 'page': page, 'page_size': page_size,
            'items': [{'card': card_payload(cards[c]), 'rule': rule_payload(cards[c], rules.get(c)),
                       **stock.get(c, {'owned': 0, 'available': 0, 'stock_verified': True})} for c in ids]}


@router.post('/validate')
def validate(body: DeckData, db: Database, user=Depends(current_user)):
    entries = normalize(db, body.entries)
    return validate_deck(db, user.id, entries, get_profile(db, body.profile_id))


@router.post('/ydk/parse')
def import_ydk(body: YdkRequest, db: Database, user=Depends(current_user)):
    get_profile(db, body.profile_id)
    try: source = parse_ydk(body.text)
    except ValueError as error: raise HTTPException(400, str(error)) from error
    codes = {e['passcode'] for e in source}
    matches = defaultdict(list)
    for rule, card in db.execute(select(DuelCardRule, Card).join(Card, Card.id == DuelCardRule.card_id).where(
            DuelCardRule.profile_id == body.profile_id, DuelCardRule.passcode.in_(codes))):
        if rule_payload(card, rule)['status'] == 'mapped': matches[rule.passcode].append(card.id)
    missing = sorted(code for code in codes if len(matches[code]) != 1)
    if missing:
        raise HTTPException(400, 'Keine eindeutige freigegebene Katalogzuordnung für Passcodes: ' + ', '.join(map(str, missing)))
    entries = normalize(db, [Entry(card_id=matches[e['passcode']][0], section=e['section'], quantity=1) for e in source])
    ids = {e['card_id'] for e in entries}
    cards = {card.id: card_payload(card) for card in db.scalars(select(Card).where(Card.id.in_(ids)))} if ids else {}
    return {'entries': entries, 'cards': cards, 'validation': validate_deck(db, user.id, entries, get_profile(db, body.profile_id))}


@router.get('')
def list_decks(db: Database, user=Depends(current_user), archived: bool = False):
    return [summary(deck) for deck in db.scalars(select(PlayerDeck).where(PlayerDeck.user_id == user.id,
            PlayerDeck.archived == archived).order_by(PlayerDeck.updated_at.desc(), PlayerDeck.id))]


@router.post('')
def create(body: DeckData, db: Database, user=Depends(current_user), idempotency_key: Key = None):
    lock_wallet(db, user)
    action = 'deck:create:' + digest(body.model_dump())
    previous = replay(db, user, idempotency_key, action)
    if previous: return previous
    check_capacity(db, user.id); get_profile(db, body.profile_id)
    entries = normalize(db, body.entries)
    deck = PlayerDeck(id=str(uuid4()), user_id=user.id, name=body.name, notes=body.notes, profile_id=body.profile_id,
                      entries_json=json.dumps(entries), version=1, archived=False)
    db.add(deck); db.flush()
    return finish(db, user, idempotency_key, action, detail(db, deck))


@router.get('/{deck_id}')
def get_deck(deck_id: str, db: Database, user=Depends(current_user)):
    return detail(db, own_deck(db, user.id, deck_id))


@router.put('/{deck_id}')
def save(deck_id: str, body: SaveDeck, db: Database, user=Depends(current_user)):
    lock_wallet(db, user)
    deck = own_deck(db, user.id, deck_id, body.version)
    if deck.archived: raise HTTPException(409, 'Archiviertes Deck zuerst wiederherstellen.')
    get_profile(db, body.profile_id)
    entries = normalize(db, body.entries)
    deck.name, deck.notes, deck.profile_id = body.name, body.notes, body.profile_id
    deck.entries_json = json.dumps(entries); deck.version += 1; deck.updated_at = datetime.utcnow()
    db.flush(); result = detail(db, deck); db.commit()
    return result


@router.post('/{deck_id}/duplicate')
def duplicate(deck_id: str, body: Version, db: Database, user=Depends(current_user), idempotency_key: Key = None):
    lock_wallet(db, user)
    action = f'deck:duplicate:{deck_id}:{body.version}'
    previous = replay(db, user, idempotency_key, action)
    if previous: return previous
    original = own_deck(db, user.id, deck_id, body.version)
    check_capacity(db, user.id)
    deck = PlayerDeck(id=str(uuid4()), user_id=user.id, name=original.name[:72] + ' (Kopie)', notes=original.notes,
                      profile_id=original.profile_id, entries_json=original.entries_json, version=1, archived=False)
    db.add(deck); db.flush()
    return finish(db, user, idempotency_key, action, detail(db, deck))


@router.post('/{deck_id}/archive')
def archive(deck_id: str, body: Archive, db: Database, user=Depends(current_user)):
    lock_wallet(db, user)
    deck = own_deck(db, user.id, deck_id, body.version)
    if deck.archived and not body.archived: check_capacity(db, user.id, total=False)
    deck.archived = body.archived; deck.version += 1; deck.updated_at = datetime.utcnow()
    db.flush(); result = summary(deck); db.commit()
    return result


@router.post('/{deck_id}/delete')
def delete(deck_id: str, body: Version, db: Database, user=Depends(current_user)):
    lock_wallet(db, user)
    deck = own_deck(db, user.id, deck_id, body.version)
    from app.db.models import DuelLobbySeat
    if db.scalar(select(DuelLobbySeat.user_id).where(DuelLobbySeat.deck_id == deck.id)):
        raise HTTPException(409, 'Dieses Deck ist in einer Lobby ausgewählt. Verlasse die Lobby vor dem Löschen.')
    db.delete(deck); db.commit()
    return {'deleted': True}


@router.get('/{deck_id}/ydk', response_class=PlainTextResponse)
def export_ydk(deck_id: str, db: Database, user=Depends(current_user)):
    deck = own_deck(db, user.id, deck_id)
    entries = json.loads(deck.entries_json)
    check = validate_deck(db, user.id, entries, get_profile(db, deck.profile_id))
    if any(rule['status'] != 'mapped' for rule in check['rules'].values()) or len(check['rules']) != len({e['card_id'] for e in entries}):
        raise HTTPException(400, 'Export erst nach eindeutiger Kartenzuordnung möglich.')
    lines = ['#created by SDOYCC']
    for section, marker in [('main', '#main'), ('extra', '#extra'), ('side', '!side')]:
        lines.append(marker)
        for e in entries:
            if e['section'] == section: lines.extend([str(check['rules'][e['card_id']]['passcode'])] * e['quantity'])
    return PlainTextResponse('\n'.join(lines) + '\n', headers={'Content-Disposition': 'attachment; filename="sdoycc-deck.ydk"'})
