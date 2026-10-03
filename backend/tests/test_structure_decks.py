from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from sqlalchemy import select

from app.db.models import (BoosterPack, Card, User, InventoryItem, UserBooster,
                           ProductPurchaseCounter, StructureDeckDefinition, StructureDeckItem)
from test_economy import HubTestCase


class StructureDeckTests(HubTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            db.get(User, 1).credits = 5000
            db.get(BoosterPack, 1).product_type = 'structure_deck'
            db.add(Card(id=2, external_id='second', name='Second', card_set='Test', set_code='T', rarity='common', card_type='Monster', attribute='LIGHT', image_url=''))
            db.add(StructureDeckDefinition(booster_id=1, source='test fixture', content_hash='test', card_count=42,
                items=[StructureDeckItem(card_id=1, rarity='rare', quantity=3), StructureDeckItem(card_id=2, rarity='common', quantity=39)]))
            db.commit()

    def test_full_content_preserves_duplicates_and_history_without_random_draw(self):
        bought = self.buy().json()
        self.assertEqual((bought['total_cost'], bought['credits_remaining'], bought['purchases_remaining']), (600, 4400, 2))
        for url in ['/api/boosters', '/api/boosters/1']:
            data = self.client.get(url, headers=self.headers).json()
            data = data[0] if isinstance(data, list) else data
            self.assertEqual((data['cost'], data['cards_per_pack'], data['pool_size'], data['purchases_remaining']), (600, 42, 2, 2))
        with patch('app.api.random.SystemRandom', side_effect=AssertionError('Deck must not draw')):
            opened = self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'open-deck-1'}).json()
        self.assertEqual(len(opened['cards']), 42)
        self.assertEqual(sum(c['id'] == 1 for c in opened['cards']), 3)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'open-deck-1'}).json(), opened)
        with self.sessions() as db:
            self.assertEqual(dict(db.execute(select(InventoryItem.card_id, InventoryItem.quantity)).all()), {1: 3, 2: 39})
        history = self.client.get('/api/boosters/me/history', headers=self.headers).json()
        self.assertEqual(len(history[0]['cards']), 42)

    def test_lifetime_limit_survives_opening_and_allows_idempotent_retry(self):
        self.assertEqual(self.client.post('/api/boosters/1/purchase', headers=self.headers, json={'quantity': 2}).status_code, 200)
        third = self.buy('third-buy-1')
        self.assertEqual(third.json()['purchases_remaining'], 0)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 200)
        self.assertEqual(self.buy('fourth-buy-1').status_code, 409)
        self.assertEqual(self.buy('third-buy-1').json(), third.json())
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 3200)
            self.assertEqual(db.scalar(select(ProductPurchaseCounter)).quantity, 3)
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 2)

    def test_concurrent_last_purchase_cannot_exceed_three(self):
        self.client.post('/api/boosters/1/purchase', headers=self.headers, json={'quantity': 2})
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(self.buy, ['last-buy-a', 'last-buy-b']))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(ProductPurchaseCounter)).quantity, 3)
            self.assertEqual(db.get(User, 1).credits, 3200)

    def test_failed_purchase_and_missing_definition_do_not_consume_allowance(self):
        with self.sessions() as db:
            db.get(User, 1).credits = 599
            db.commit()
        self.assertEqual(self.buy().status_code, 400)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(ProductPurchaseCounter)))
            db.get(User, 1).credits = 5000
            db.get(StructureDeckDefinition, 1).card_count = 43
            db.add(UserBooster(user_id=1, booster_id=1, quantity=1))
            db.commit()
        self.assertEqual(self.buy().status_code, 409)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get('/api/boosters/1', headers=self.headers).json()['cards_per_pack'], 0)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 5000)
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 1)

    def test_limit_is_per_product_and_bulk_over_limit_is_atomic(self):
        self.assertEqual(self.client.post('/api/boosters/1/purchase', headers=self.headers, json={'quantity': 4}).status_code, 409)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(ProductPurchaseCounter)))
            pack = BoosterPack(key='other', name='Other', product_type='structure_deck', deck=StructureDeckDefinition(source='test', content_hash='test', card_count=1, items=[StructureDeckItem(card_id=1, rarity='rare', quantity=1)]))
            db.add(pack)
            db.commit()
        self.client.post('/api/boosters/1/purchase', headers=self.headers, json={'quantity': 3})
        other = self.client.post('/api/boosters/2/purchase', headers=self.headers, json={'quantity': 1})
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.json()['purchases_remaining'], 2)

    def test_manifest_import_is_idempotent_and_never_silently_changes_contents(self):
        from app.modules.card_data.structure_decks import import_structure_decks
        definition = {'set_name': 'Imported deck', 'sources': ['test source'], 'card_count': 3,
                      'items': [{'external_id': 'test', 'rarity': 'rare', 'quantity': 3, 'set_code': 'T'}]}
        manifest = {'definitions': [definition]}
        with self.sessions() as db:
            db.add(BoosterPack(key='imported', name='Imported deck', product_type='structure_deck'))
            db.commit()
            self.assertEqual(import_structure_decks(db, manifest)['installed'], ['Imported deck'])
            db.commit()
            self.assertEqual(import_structure_decks(db, manifest)['unchanged'], ['Imported deck'])
            definition['card_count'] = 2
            definition['items'][0]['quantity'] = 2
            self.assertEqual(import_structure_decks(db, manifest)['conflicts'], ['Imported deck'])
            self.assertEqual(db.get(BoosterPack, 2).deck.items[0].quantity, 3)

    def test_bundled_manifest_has_complete_counts_and_real_duplicate_examples(self):
        import json
        from app.modules.card_data.structure_decks import MANIFEST
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        decks = {d['set_name']: d for d in manifest['definitions']}
        for d in decks.values():
            self.assertEqual(sum(i['quantity'] for i in d['items']) + len(d.get('bonus_slots', [])), d['card_count'])
            self.assertTrue(d['sources'])
        self.assertEqual(decks['Structure Deck: Albaz Strike']['card_count'], 51)
        traptrix = decks['Structure Deck: Beware of Traptrix']
        self.assertEqual(traptrix['card_count'], 48)
        self.assertEqual(sum(i['quantity'] == 2 for i in traptrix['items']), 2)
        self.assertEqual(len(decks), 59)
        blue = decks['Structure Deck: Blue-Eyes White Destiny']
        self.assertEqual((blue['card_count'], len(blue['bonus_slots'][0]['choices'])), (51, 3))
        self.assertEqual(next(i['quantity'] for i in blue['items'] if i['external_id'] == '89631139'), 3)
        spirit = decks['Structure Deck: Spirit Charmers']
        self.assertEqual((spirit['card_count'], len(spirit['bonus_slots'][0]['choices'])), (43, 4))

    def add_bonus(self):
        from app.db.models import StructureDeckBonusSlot, StructureDeckBonusChoice
        with self.sessions() as db:
            db.add(Card(id=3, external_id='bonus-only', name='Bonus only', card_set='Test', set_code='T', rarity='secret_rare', card_type='Monster', attribute='LIGHT', image_url=''))
            deck = db.get(StructureDeckDefinition, 1)
            deck.card_count = 43
            deck.bonus_slots.append(StructureDeckBonusSlot(name='Eine Bonuskarte', choices=[
                StructureDeckBonusChoice(card_id=1, rarity='secret_rare'),
                StructureDeckBonusChoice(card_id=3, rarity='secret_rare')]))
            db.commit()

    def test_bonus_is_additional_drawn_once_and_not_rerolled_on_retry(self):
        self.add_bonus()
        self.assertEqual(self.buy().status_code, 200)
        with patch('random.SystemRandom.choice', side_effect=lambda choices: choices[-1]) as choose:
            first = self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'bonus-open-1'})
            self.assertEqual(first.status_code, 200, first.text)
            again = self.client.post('/api/boosters/1/open', headers={**self.headers, 'Idempotency-Key': 'bonus-open-1'})
            self.assertEqual(first.json(), again.json())
            self.assertEqual(choose.call_count, 1)
        cards = first.json()['cards']
        self.assertEqual(len(cards), 43)
        self.assertEqual(sum(c['id'] == 1 for c in cards), 3)
        self.assertEqual(sum(c['id'] == 2 for c in cards), 39)
        self.assertEqual(sum(c['id'] == 3 and c['rarity'] == 'secret_rare' for c in cards), 1)
        history = self.client.get('/api/boosters/me/history', headers=self.headers).json()[0]
        self.assertEqual(len(history['cards']), 43)
        self.assertEqual(sum(c['rarity'] == 'secret_rare' for c in history['cards']), 1)

    def test_bonus_display_and_card_discovery_are_consistent(self):
        self.add_bonus()
        detail = self.client.get('/api/boosters/1', headers=self.headers).json()
        listed = self.client.get('/api/cards/3/boosters', headers=self.headers).json()[0]
        for result in [detail, listed]:
            self.assertEqual((result['cards_per_pack'], result['fixed_cards'], result['bonus_cards'], result['pool_size']), (43, 42, 1, 3))
        self.assertEqual(len(detail['pool']), 2)
        self.assertEqual([c['probability'] for c in detail['bonus_slots'][0]['choices']], [.5, .5])

    def test_empty_bonus_slot_blocks_purchase_and_open_without_losing_stock(self):
        self.add_bonus()
        self.buy()
        with self.sessions() as db:
            definition = db.get(StructureDeckDefinition, 1)
            definition.bonus_slots[0].choices.clear()
            db.commit()
        self.assertEqual(self.buy('invalid-bonus').status_code, 409)
        self.assertEqual(self.client.post('/api/boosters/1/open', headers=self.headers).status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 4400)
            self.assertEqual(db.scalar(select(UserBooster)).quantity, 1)

    def test_bonus_manifest_import_checks_all_choices_before_installing(self):
        from app.modules.card_data.structure_decks import import_structure_decks
        definition = {'set_name': 'Bonus import', 'sources': ['test source'], 'card_count': 2,
            'items': [{'external_id': 'test', 'rarity': 'rare', 'quantity': 1, 'set_code': 'T'}],
            'bonus_slots': [{'name': 'Bonus', 'choices': [{'external_id': 'missing', 'rarity': 'secret_rare', 'set_code': 'T'}]}]}
        with self.sessions() as db:
            db.add(BoosterPack(id=2, key='bonus-import', name='Bonus import', product_type='structure_deck'))
            db.commit()
            self.assertIn('Bonus import', import_structure_decks(db, {'definitions': [definition]})['pending'])
            self.assertIsNone(db.get(BoosterPack, 2).deck)
            definition['bonus_slots'][0]['choices'][0]['external_id'] = 'test'
            self.assertEqual(import_structure_decks(db, {'definitions': [definition]})['installed'], ['Bonus import'])
            db.commit()
            result = self.client.get('/api/boosters/2', headers=self.headers).json()
            self.assertEqual((result['fixed_cards'], result['bonus_cards'], result['cards_per_pack']), (1, 1, 2))
