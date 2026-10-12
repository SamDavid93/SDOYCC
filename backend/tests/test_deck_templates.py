from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import select

from app.db.models import DeckTemplate, PlayerDeck
from test_decks import DeckTestCase


class TemplateTests(DeckTestCase):
    def setUp(self):
        super().setUp()
        self.deck = self.client.post('/api/decks', json={**self.body, 'notes': 'PRIVATE NOTES'}, headers=self.headers).json()

    def share(self, headers=None, version=None):
        return self.client.post('/api/deck-templates/decks/' + self.deck['id'],
            json={'version': version or self.deck['version']},
            headers={**(headers or self.headers), 'Idempotency-Key': str(uuid4())})

    def test_immutable_shared_revision_has_no_notes_owner_or_stock(self):
        shared = self.share().json()
        with self.sessions() as db:
            row = db.get(PlayerDeck, self.deck['id']); row.entries_json = '[]'; row.version += 1; db.commit()
        response = self.client.get('/api/deck-templates/' + shared['id'])
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['entries'], self.deck['entries'])
        for private in ('notes', 'user_id', 'validation', 'stock', 'session_hash', 'deck_id'):
            self.assertNotIn(private, payload)

    def test_copy_validates_own_stock_and_never_grants_cards(self):
        shared = self.share().json()
        response = self.client.post('/api/deck-templates/' + shared['id'] + '/copy',
            headers={**self.other_headers, 'Idempotency-Key': str(uuid4())})
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.client.get('/api/decks', headers=self.other_headers).json(), [])
        self.assertEqual(self.client.get('/api/decks/' + self.deck['id'], headers=self.other_headers).status_code, 404)

    def test_share_ownership_version_revoke_and_expiry(self):
        self.assertEqual(self.share(self.other_headers).status_code, 404)
        self.assertEqual(self.share(version=2).status_code, 409)
        shared = self.share().json(); path = '/api/deck-templates/' + shared['id']
        self.assertEqual(self.client.post(path + '/revoke', headers=self.other_headers).status_code, 404)
        self.assertEqual(self.client.post(path + '/revoke', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(path).status_code, 404)
        shared = self.share().json()
        with self.sessions() as db:
            db.get(DeckTemplate, shared['id']).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        self.assertEqual(self.client.get('/api/deck-templates/' + shared['id']).status_code, 404)

    def test_share_cap_and_idempotency(self):
        path = '/api/deck-templates/decks/' + self.deck['id']
        headers = {**self.headers, 'Idempotency-Key': str(uuid4())}
        body = {'version': self.deck['version']}
        first = self.client.post(path, json=body, headers=headers).json()
        self.assertEqual(self.client.post(path, json=body, headers=headers).json()['id'], first['id'])
        for _ in range(9): self.assertEqual(self.share().status_code, 200)
        self.assertEqual(self.share().status_code, 409)
