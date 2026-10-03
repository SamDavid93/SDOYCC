"""Import the reviewed, bundled deck manifest without downloading at startup.

Definitions are immutable once installed: a changed manifest needs an explicit
review/migration so purchased packs cannot silently change their contents.
"""
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from app.core.pricing import STRUCTURE_DECK_PRICE
from app.db.models import BoosterPack, Card, CardDetails, CardPrinting, StructureDeckDefinition, StructureDeckItem, StructureDeckBonusSlot, StructureDeckBonusChoice

MANIFEST = Path(__file__).resolve().parents[3] / 'data' / 'structure-decks.json'


def import_structure_decks(database, manifest=None):
    manifest = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding='utf-8'))
    definitions = {item['set_name']: item for item in manifest['definitions']}
    cards = {item.external_id: item for item in database.scalars(select(Card))}
    tokens = manifest.get('additional_tokens', {})
    report = {'installed': [], 'unchanged': [], 'pending': [], 'conflicts': []}
    packs = database.scalars(select(BoosterPack).where(BoosterPack.product_type == 'structure_deck')).all()
    for pack in packs:
        name = pack.card_set.name if pack.card_set else pack.name.removesuffix(' Booster')
        pack.name = name
        pack.cost = STRUCTURE_DECK_PRICE
        definition = definitions.get(name)
        if not definition:
            report['pending'].append(name)
            continue
        items = definition['items']
        slots = definition.get('bonus_slots', [])
        if any(not slot.get('name') or not 1 <= len(slot['choices']) <= 30 or
               len({(i['external_id'], i['rarity']) for i in slot['choices']}) != len(slot['choices']) for slot in slots):
            raise ValueError(f'Ungültige Bonusauswahl: {name}')
        candidates = items + [choice for slot in slots for choice in slot['choices']]
        if (not items or any(type(item['quantity']) is not int or not 1 <= item['quantity'] <= 100 for item in items)
                or sum(item['quantity'] for item in items) + len(slots) != definition['card_count']
                or not 1 <= definition['card_count'] <= 100
                or len({(i['external_id'], i['rarity']) for i in items}) != len(items)
                or not definition['sources']):
            raise ValueError(f'Ungültige Deckdefinition: {name}')
        digest = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        if pack.deck:
            report['unchanged' if pack.deck.content_hash == digest else 'conflicts'].append(name)
            continue
        if any(i['external_id'] not in cards and i['external_id'] not in tokens for i in candidates):
            report['pending'].append(name)
            continue
        # Only add tokens actually needed by a complete definition.
        for item in candidates:
            ext = item['external_id']
            if ext not in cards:
                token = tokens[ext]
                card = Card(external_id=ext, name=token['name'], card_set=name,
                            set_code=item['set_code'], rarity=item['rarity'], card_type='Token', attribute='', image_url='')
                database.add(card)
                database.flush()
                database.add(CardDetails(card_id=card.id, name_de=token.get('name_de'),
                    description_de=token.get('description_de'), description_en=token.get('description_en'), konami_id=token.get('konami_id')))
                cards[ext] = card
            card = cards[ext]
            if pack.set_id and not database.scalar(select(CardPrinting.id).where(CardPrinting.set_id == pack.set_id, CardPrinting.card_id == card.id, CardPrinting.rarity == item['rarity'])):
                database.add(CardPrinting(card_id=card.id, set_id=pack.set_id, external_provider='structure-manifest',
                    external_printing_id=f'{pack.key}:{ext}:{item["rarity"]}', set_code=item['set_code'], rarity=item['rarity'], language='en'))
                database.flush()
        pack.deck = StructureDeckDefinition(source='\n'.join(definition['sources']), content_hash=digest,
            card_count=definition['card_count'], notes=definition.get('notes'),
            bonus_slots=[StructureDeckBonusSlot(name=slot['name'], choices=[StructureDeckBonusChoice(card_id=cards[i['external_id']].id, rarity=i['rarity']) for i in slot['choices']]) for slot in slots], items=[StructureDeckItem(card_id=cards[i['external_id']].id, rarity=i['rarity'], quantity=i['quantity']) for i in items])
        report['installed'].append(name)
    database.flush()
    return report
