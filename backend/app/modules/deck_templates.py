"""Capability links disclose only the deliberately shared revision of a deck."""
from datetime import datetime, timedelta
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api import card_payload, current_user
from app.db.models import Card, DeckTemplate, User
from app.modules.decks import Database, DeckData, Key, Version, create, own_deck
from app.modules.duel_rules import profile_payload
from app.modules.decks import get_profile
from app.modules.economy import finish, lock_wallet, replay

router = APIRouter(prefix='/api/deck-templates', tags=['Shared deck templates'])


def summary(row):
    return {'id': row.id, 'name': row.name, 'deck_version': row.deck_version,
            'expires_at': row.expires_at.isoformat() + 'Z', 'revoked': row.revoked}


def available(db, template_id, lock=False):
    query = select(DeckTemplate).where(DeckTemplate.id == template_id).execution_options(populate_existing=True)
    if lock: query = query.with_for_update()
    row = db.scalar(query)
    owner = db.get(User, row.user_id) if row else None
    if not row or row.revoked or row.expires_at <= datetime.utcnow() or not owner or not owner.is_active:
        raise HTTPException(404, 'Diese Deckvorlage ist nicht mehr verfügbar.')
    return row


@router.get('/mine/{deck_id}')
def mine(deck_id: str, db: Database, user=Depends(current_user)):
    own_deck(db, user.id, deck_id)
    return [summary(row) for row in db.scalars(select(DeckTemplate).where(
        DeckTemplate.user_id == user.id, DeckTemplate.deck_id == deck_id,
        DeckTemplate.revoked.is_(False), DeckTemplate.expires_at > datetime.utcnow()))]


@router.post('/decks/{deck_id}')
def share(deck_id: str, body: Version, db: Database, user=Depends(current_user), idempotency_key: Key = None):
    lock_wallet(db, user)
    action = f'deck:share:{deck_id}:{body.version}'
    previous = replay(db, user, idempotency_key, action)
    if previous: return previous
    deck = own_deck(db, user.id, deck_id, body.version)
    if deck.archived: raise HTTPException(409, 'Archiviertes Deck zuerst wiederherstellen.')
    count = db.scalar(select(func.count(DeckTemplate.id)).where(DeckTemplate.user_id == user.id,
        DeckTemplate.revoked.is_(False), DeckTemplate.expires_at > datetime.utcnow()))
    if count >= 10: raise HTTPException(409, 'Höchstens zehn aktive Vorlagen. Widerrufe zuerst einen alten Link.')
    row = DeckTemplate(id=str(uuid4()), user_id=user.id, deck_id=deck.id, deck_version=deck.version,
        name=deck.name, profile_id=deck.profile_id, entries_json=deck.entries_json,
        expires_at=datetime.utcnow() + timedelta(days=30))
    db.add(row); db.flush()
    return finish(db, user, idempotency_key, action, summary(row))


@router.post('/{template_id}/revoke')
def revoke(template_id: str, db: Database, user=Depends(current_user), idempotency_key: Key = None):
    lock_wallet(db, user)
    action = 'deck:revoke:' + template_id
    previous = replay(db, user, idempotency_key, action)
    if previous: return previous
    row = db.get(DeckTemplate, template_id)
    if not row or row.user_id != user.id: raise HTTPException(404, 'Eigene Deckvorlage nicht gefunden.')
    row.revoked = True
    return finish(db, user, idempotency_key, action, summary(row))


@router.get('/{template_id}')
def view(template_id: str, db: Database):
    row = available(db, template_id)
    entries = json.loads(row.entries_json)
    ids = {entry['card_id'] for entry in entries}
    cards = {card.id: card_payload(card) for card in db.scalars(select(Card).where(Card.id.in_(ids)))}
    return {**summary(row), 'entries': entries, 'cards': cards,
        'profile_id': row.profile_id, 'profile': profile_payload(get_profile(db, row.profile_id))}


@router.post('/{template_id}/copy')
def copy(template_id: str, db: Database, user=Depends(current_user), idempotency_key: Key = None):
    # Lock before checking revocation, so copy and revoke have a defined order.
    lock_wallet(db, user)
    row = available(db, template_id, lock=True)
    body = DeckData(name=row.name, notes='', profile_id=row.profile_id, entries=json.loads(row.entries_json))
    return create(body, db, user, idempotency_key)
