from sqlalchemy import select
from app.db.models import CardDetails, InventoryItem, Card, User
from scripts.sync_german import sync_german
from scripts.sync_image_sources import fill_missing_names
from test_economy import HubTestCase


class CollectionTests(HubTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            db.add(InventoryItem(user_id=1, card_id=1, quantity=3))
            db.add(CardDetails(card_id=1, name_de="Prüfdrache", description_de="Ein deutscher Text.", race="Dragon", level=8, atk=3000, defense=2500, ban_status="Unlimited", konami_id=4007))
            db.commit()

    def test_german_metadata_and_filters(self):
        result = self.client.get('/api/collection', params={'search': 'Prüf', 'race': 'Dragon', 'level': 8, 'atk': 3000, 'duplicates': True}, headers=self.headers).json()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['total_quantity'], 3)
        self.assertEqual(result['items'][0]['card']['name'], 'Prüfdrache')
        self.assertEqual(result['items'][0]['card']['image_url'], '/api/cards/1/art/de')
        self.assertEqual(self.client.get('/api/collection', params={'atk': 0}, headers=self.headers).json()['total'], 0)
        facets = self.client.get('/api/collection/filters', headers=self.headers).json()
        self.assertEqual(facets['level'], [8])
        self.assertEqual(facets['race'], ['Dragon'])
        self.assertEqual(self.client.get('/api/cards', params={'search': 'Prüf'}).json()['total'], 1)

    def test_missing_translation_keeps_original_name_and_german_image_candidate(self):
        with self.sessions() as db:
            db.get(CardDetails, 1).name_de = None
            original_name = db.get(Card, 1).name
            db.commit()
        card = self.client.get('/api/cards/1').json()
        self.assertEqual(card['name'], original_name)
        self.assertFalse(card['localized'])
        self.assertTrue(card['image_available'])
        self.assertEqual(card['image_url'], '/api/cards/1/art/de')

    def test_empty_and_placeholder_translations_fall_back_to_english(self):
        for invalid in [None, '', '  ', 'Karte 123', 'Karte [123]', 'karte 123']:
            with self.sessions() as db:
                details = db.get(CardDetails, 1)
                details.name_de = invalid
                details.description_de = invalid
                details.description_en = 'Original English effect text.'
                original_name = db.get(Card, 1).name
                db.commit()
            result = self.client.get('/api/cards/1').json()
            self.assertEqual(result['name'], original_name)
            self.assertEqual(result['description'], 'Original English effect text.')
            self.assertEqual(result['description_language'], 'en')
            self.assertFalse(result['localized'])
        self.assertEqual(self.client.get('/api/collection', params={'search': 'English effect'}, headers=self.headers).json()['total'], 1)

    def test_german_text_is_preferred_when_english_is_available(self):
        with self.sessions() as db:
            db.get(CardDetails, 1).description_en = 'English text'
            db.commit()
        result = self.client.get('/api/cards/1').json()
        self.assertEqual(result['description'], 'Ein deutscher Text.')
        self.assertEqual(result['description_language'], 'de')

    def test_supplemental_names_preserve_existing_translations_and_wallet(self):
        self.assertEqual(fill_missing_names({'Anderer Name': [4007]}, self.sessions), 0)
        with self.sessions() as db:
            db.get(CardDetails, 1).name_de = None
            db.commit()
        self.assertEqual(fill_missing_names({'Ergänzter Name': [4007]}, self.sessions), 1)
        with self.sessions() as db:
            self.assertEqual(db.get(CardDetails, 1).name_de, 'Ergänzter Name')
            self.assertEqual(db.get(User, 1).credits, 100)
            self.assertEqual(db.scalar(select(InventoryItem)).quantity, 3)

    def test_paging_totals_and_user_isolation(self):
        with self.sessions() as db:
            stranger = User(username='stranger', display_name='Fremd', credits=0)
            db.add(stranger); db.flush()
            db.add(InventoryItem(user_id=stranger.id, card_id=1, quantity=50)); db.commit()
        response = self.client.get('/api/collection', params={'page': 2, 'page_size': 1}, headers=self.headers)
        self.assertEqual(response.json()['items'], [])
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['total_quantity'], 3)
        self.assertEqual(self.client.get('/api/collection').status_code, 401)

    def test_zero_values_remain_filterable(self):
        with self.sessions() as db:
            db.get(CardDetails, 1).atk = 0
            db.get(CardDetails, 1).scale = 0
            db.commit()
        self.assertEqual(self.client.get('/api/collection', params={'atk': 0, 'scale': 0}, headers=self.headers).json()['total'], 1)
        self.assertEqual(self.client.get('/api/collection/filters', headers=self.headers).json()['scale'], [0])

    def test_translation_import_preserves_identity_and_owned_data(self):
        raw = {'id': 'test', 'name': 'English name', 'type': 'Monster', 'race': 'Dragon', 'level': 8, 'atk': 3000}
        sync_german([raw], [{**raw, 'name': 'Deutscher Name', 'desc': 'Deutscher Text'}], self.sessions)
        with self.sessions() as db:
            self.assertEqual(db.get(Card, 1).details.name_de, 'Deutscher Name')
            self.assertEqual(db.scalar(select(InventoryItem)).quantity, 3)
            self.assertEqual(db.get(User, 1).credits, 100)
