from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4
from types import SimpleNamespace
import unittest

from sqlalchemy import func, select

from app.core.auth import create_session
from app.db.models import Card, CardDetails, DuelCardRule, DuelRuleProfile, InventoryItem, PlayerDeck, User, VariantInventory
from app.modules.duel_rules import import_profile, mapped_rules, parse_banlist, parse_ydk
from app.modules.inventory import change_stock, variant
from test_economy import HubTestCase


class RuleParserTests(unittest.TestCase):
    def test_strict_banlist(self):
        self.assertEqual(parse_banlist('#heading\n!Test TCG\n123 0 --Card\n456 2'), ('Test TCG', {123: 0, 456: 2}))
        for text in ('123 0', '!TCG\n$whitelist', '!TCG\n123 4', '!TCG\n!Other', '!TCG\n123 0\n123 1'):
            with self.subTest(text=text), self.assertRaises(ValueError): parse_banlist(text)

    def test_mapping_never_guesses_and_alias_limits_apply_to_family(self):
        def card(code, name='Name', provider='ygoprodeck'):
            return SimpleNamespace(id=code, external_id=str(code), external_provider=provider, name=name)
        data = {1: {'alias': 0, 'type': 17, 'ot': 3, 'name': 'Name'},
                2: {'alias': 1, 'type': 17, 'ot': 3, 'name': 'Name'},
                3: {'alias': 4, 'type': 17, 'ot': 3, 'name': 'Name'},
                4: {'alias': 3, 'type': 17, 'ot': 3, 'name': 'Name'}}
        rows = mapped_rules([card(1), card(2), card(3), card(4, 'Wrong'), card(5), card(6, provider='sdoycc-community')], data, {2: 1}, set())
        self.assertEqual([r['status'] for r in rows], ['mapped', 'mapped', 'alias_invalid', 'name_mismatch', 'unknown_passcode', 'unknown_provider'])
        self.assertEqual(rows[0]['copy_limit'], 1)
        self.assertEqual(rows[1]['identity'], 1)

    def test_hybrid_types_and_non_tcg_cards(self):
        types = [17, 0x81, 0x1000000 | 0x40 | 1, 0x2000 | 1, 0x800000 | 1, 0x4000000 | 1, 0x4001, 17, 0x8001]
        cards = [SimpleNamespace(id=i, name='Name', external_id=str(i), external_provider='ygoprodeck') for i in range(1, 10)]
        data = {i: {'name': 'Name', 'alias': 0, 'type': t, 'ot': 1 if i == 8 else 3} for i, t in enumerate(types, 1)}
        rules = mapped_rules(cards, data, {}, set())
        self.assertEqual([r['section'] for r in rules[:6]], ['main', 'main', 'extra', 'extra', 'extra', 'extra'])
        self.assertEqual([r['status'] for r in rules[6:]], ['unsupported_type', 'not_tcg', 'unsupported_type'])

    def test_ydk_boundaries(self):
        self.assertEqual(parse_ydk('\ufeff#created by test\n#main\n000123\n#extra\n!side\n123')[0]['passcode'], 123)
        for text in ('#main\n123', '#main\n#extra\n!side\n#main', '#main\nnope\n#extra\n!side', '#main\n' + '1\n' * 201 + '#extra\n!side', 'X' * 100001):
            with self.subTest(text=text[:40]), self.assertRaises(ValueError): parse_ydk(text)


class DeckTestCase(HubTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            first = db.get(Card, 1)
            first.external_provider = 'ygoprodeck'; first.external_id = '10001'; first.name = 'Card 1'
            for i in range(2, 24):
                db.add(Card(id=i, external_provider='ygoprodeck', external_id=str(10000+i), name=f'Card {i}',
                            card_set='Test', set_code='T', rarity='rare', card_type='Monster', attribute='LIGHT', image_url=''))
            db.flush()
            for i in range(1, 24):
                db.add(CardDetails(card_id=i, level=4, atk=1500, defense=1000, race='Dragon', name_de=f'Prüfkarte {i}'))
                kind = variant(db, i, 'rare')
                change_stock(db, 1, kind, 3, 'test', f'test:{i}', bound=(i == 1))
            self.data = {10000+i: {'name': f'Card {i}', 'alias': 0, 'type': 17 if i <= 21 else 0x4000001, 'ot': 3} for i in range(1, 24)}
            profile, _ = import_profile(db, db.scalars(select(Card)).all(), self.data, {}, {10022, 10023}, 'TEST', {'test': True})
            self.profile = profile.id
            other = User(username='other', display_name='Other', credits=0)
            db.add(other); db.flush(); token = create_session(db, other); db.commit()
            self.other_headers = {'Authorization': 'Bearer ' + token}
        self.body = {'name': 'Mein Testdeck', 'profile_id': self.profile, 'notes': '', 'entries':
                     [{'card_id': i, 'section': 'main', 'quantity': 3 if i < 14 else 1} for i in range(1, 15)]}


class DeckTests(DeckTestCase):
    def create(self, body=None, key='deck-create-test'):
        return self.client.post('/api/decks', json=body or self.body, headers={**self.headers, 'Idempotency-Key': key})

    def validate(self, body=None):
        r = self.client.post('/api/decks/validate', json=body or self.body, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_creation_private_idempotent_no_stock_or_credits_change(self):
        response = self.create(); self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.create().json(), response.json())
        check = response.json()['validation']
        self.assertTrue(check['rules_ok']); self.assertTrue(check['stock_ok']); self.assertFalse(check['ready'])
        self.assertFalse(check['engine_ok'])
        id = response.json()['id']
        self.assertEqual(self.client.get('/api/decks/' + id, headers=self.other_headers).status_code, 404)
        self.assertEqual(self.client.get('/api/decks', headers=self.other_headers).json(), [])
        self.assertEqual(self.client.get('/api/decks').status_code, 401)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 1).credits, 100)
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.quantity))), 69)
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.reserved))), 0)
            self.assertEqual(db.scalar(select(func.count(PlayerDeck.id))), 1)

    def test_sizes_and_sections(self):
        for size, valid in [(39, False), (40, True), (60, True), (61, False)]:
            entries = [{'card_id': i+1, 'section': 'main', 'quantity': min(3, size-i*3)} for i in range((size+2)//3)]
            result = self.validate({**self.body, 'entries': entries})
            self.assertEqual(result['rules_ok'], valid, result)
        for section in ('extra', 'side'):
            result = self.validate({**self.body, 'entries': self.body['entries'] + [{'card_id': 22, 'section': section, 'quantity': 16}]})
            self.assertIn('size_' + section, {i['code'] for i in result['issues']})
        result = self.validate({**self.body, 'entries': self.body['entries'] + [{'card_id': 22, 'section': 'main', 'quantity': 1}]})
        self.assertIn('wrong_section', {i['code'] for i in result['issues']})

    def test_aliases_bans_and_same_card_across_sections(self):
        with self.sessions() as db:
            db.get(DuelCardRule, (self.profile, 2)).identity = 10001
            db.get(DuelCardRule, (self.profile, 3)).copy_limit = 0
            db.get(DuelCardRule, (self.profile, 4)).copy_limit = 1
            db.get(DuelCardRule, (self.profile, 5)).copy_limit = 2
            db.commit()
        result = self.validate()
        limited = {i['card_id'] for i in result['issues'] if i['code'] == 'copy_limit'}
        self.assertEqual(limited, {1, 3, 4, 5})
        result = self.validate({**self.body, 'entries': self.body['entries'] + [{'card_id': 6, 'section': 'side', 'quantity': 1}]})
        self.assertIn(6, {i['card_id'] for i in result['issues'] if i['code'] == 'copy_limit'})

    def test_stock_bound_reserved_and_drift(self):
        with self.sessions() as db:
            db.scalar(select(VariantInventory).where(VariantInventory.user_id == 1, VariantInventory.bound.is_(True))).reserved = 1
            db.get(InventoryItem, 2).quantity = 10
            db.commit()
        check = self.validate()
        self.assertEqual(check['stock']['1']['available'], 2)
        self.assertEqual(check['stock']['2']['available'], 0)
        self.assertFalse(check['stock_ok'])
        catalog = self.client.get('/api/decks/catalog', params={'profile_id': self.profile}, headers=self.headers).json()
        self.assertNotIn(2, [i['card']['id'] for i in catalog['items']])

    def test_stale_mapping_and_missing_profile_block_readiness(self):
        with self.sessions() as db:
            db.get(Card, 1).name = 'Different identity'; db.commit()
        self.assertIn('stale', {i['code'] for i in self.validate()['issues']})
        check = self.validate({**self.body, 'profile_id': None})
        self.assertFalse(check['rules_ok']); self.assertFalse(check['ready'])

    def test_concurrent_edits_reject_lost_update(self):
        deck = self.create().json()
        def edit(name):
            return self.client.put('/api/decks/' + deck['id'], headers=self.headers, json={**self.body, 'version': 1, 'name': name})
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(edit, ['First', 'Second']))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        self.assertEqual(self.client.get('/api/decks/' + deck['id'], headers=self.headers).json()['version'], 2)

    def test_duplicate_archive_delete_permissions_and_versions(self):
        deck = self.create().json(); path = '/api/decks/' + deck['id']
        for action in ('duplicate', 'delete', 'archive'):
            body = {'version': 1, **({'archived': True} if action == 'archive' else {})}
            self.assertEqual(self.client.post(path + '/' + action, json=body, headers=self.other_headers).status_code, 404)
        copy = self.client.post(path + '/duplicate', json={'version': 1}, headers=self.headers)
        self.assertEqual(copy.status_code, 200, copy.text)
        self.assertEqual(copy.json()['entries'], deck['entries'])
        archived = self.client.post(path + '/archive', json={'version': 1, 'archived': True}, headers=self.headers)
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(self.client.put(path, json={**self.body, 'version': 2}, headers=self.headers).status_code, 409)
        self.assertEqual(len(self.client.get('/api/decks?archived=true', headers=self.headers).json()), 1)
        self.assertEqual(self.client.post(path + '/delete', json={'version': 1}, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.post(path + '/delete', json={'version': 2}, headers=self.headers).status_code, 200)

    def test_ydk_roundtrip_unknown_passcode_and_no_grants(self):
        deck = self.create().json()
        response = self.client.get('/api/decks/' + deck['id'] + '/ydk', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        imported = self.client.post('/api/decks/ydk/parse', json={'profile_id': self.profile, 'text': response.text}, headers=self.headers)
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()['entries'], deck['entries'])
        invalid = response.text.replace('10001', '999999999')
        self.assertEqual(self.client.post('/api/decks/ydk/parse', json={'profile_id': self.profile, 'text': invalid}, headers=self.headers).status_code, 400)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.sum(VariantInventory.quantity))), 69)

    def test_catalog_filters_page_and_private_stock(self):
        response = self.client.get('/api/decks/catalog', params={'profile_id': self.profile, 'group': 'extra', 'page_size': 1}, headers=self.headers).json()
        self.assertEqual(response['total'], 2)
        self.assertEqual(len(response['items']), 1)
        self.assertEqual(response['items'][0]['rule']['section'], 'extra')
        self.assertEqual(self.client.get('/api/decks/catalog', headers=self.other_headers).json()['total'], 0)
        result = self.client.get('/api/decks/catalog', params={'scope': 'all', 'search': 'Prüfkarte 1'}, headers=self.other_headers).json()
        self.assertGreater(result['total'], 0)
        self.assertTrue(all(i['owned'] == 0 for i in result['items']))

    def test_malformed_drafts_and_creation_key_conflict(self):
        for entry in [{'card_id': True, 'section': 'main', 'quantity': 1}, {'card_id': 1, 'section': 'side', 'quantity': -1}, {'card_id': 1, 'section': 'bad', 'quantity': 1}]:
            self.assertEqual(self.create({**self.body, 'entries': [entry]}).status_code, 422)
        self.assertEqual(self.create({**self.body, 'entries': [{'card_id': 999, 'section': 'main', 'quantity': 1}]}).status_code, 400)
        self.assertEqual(self.create({**self.body, 'name': '   '}).status_code, 422)
        self.create()
        self.assertEqual(self.create({**self.body, 'name': 'Different'}).status_code, 409)

    def test_rule_import_repeat_and_new_version_leave_old_snapshot_intact(self):
        with self.sessions() as db:
            same, _ = import_profile(db, db.scalars(select(Card)).all(), self.data, {}, {10022, 10023}, 'TEST', {'test': True})
            self.assertEqual(same.id, self.profile)
            new, _ = import_profile(db, db.scalars(select(Card)).all(), self.data, {10001: 0}, {10022, 10023}, 'TEST 2', {'test': True})
            self.assertNotEqual(new.id, same.id)
            self.assertEqual(db.get(DuelCardRule, (self.profile, 1)).copy_limit, 3)
            self.assertEqual(db.get(DuelCardRule, (new.id, 1)).copy_limit, 0)
            self.assertFalse(new.engine_approved)
            db.commit()

    def test_active_deck_cap_is_atomic(self):
        with self.sessions() as db:
            db.add_all(PlayerDeck(id=str(uuid4()), user_id=1, name=f'Deck {i}', entries_json='[]', archived=False) for i in range(29))
            db.commit()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda key: self.create(key=key), ['deck-cap-one', 'deck-cap-two']))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        self.assertEqual(len(self.client.get('/api/decks', headers=self.headers).json()), 30)

    def test_ambiguous_ydk_mapping_cannot_choose_arbitrary_card(self):
        with self.sessions() as db:
            db.get(DuelCardRule, (self.profile, 2)).passcode = 10001
            db.commit()
        response = self.client.post('/api/decks/ydk/parse', json={'profile_id': self.profile, 'text': '#main\n10001\n#extra\n!side'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn('10001', response.json()['detail'])


if __name__ == '__main__': unittest.main()
