import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import func, select

from app.core.auth import create_session
from app.core.passwords import hash_password
from app.db.models import (AdminAuditEvent, Card, CardDetails, CardPrinting, CardVariant, CraftingCurrency,
    CraftingRarityRule, CraftingTransaction, HubEvent, InventoryItem, InventoryReservation,
    Season, SeasonProgress, User, UserCardPreference, UserCraftingBalance, VariantInventory)
from app.modules.crafting import book_currency, seed_crafting
from app.modules.inventory import change_stock, migrate_inventory, variant
from test_economy import HubTestCase


class CraftingTests(HubTestCase):
    password = "Crafting-Test-Password-123!"

    @classmethod
    def setUpClass(cls): cls.password_hash = hash_password(cls.password)

    def setUp(self):
        super().setUp()
        self.tokens = {}
        with self.sessions() as db:
            for uid, role in ((2, "super_admin"), (3, "user"), (4, "user"), (5, "support_admin")):
                user = User(id=uid, username=f"craft{uid}", display_name=f"Craft {uid}", role=role,
                    twitch_id=str(9000+uid), password_hash=self.password_hash, credits=500)
                db.add(user); db.flush()
                self.tokens[uid] = {"Authorization": "Bearer " + create_session(db, user)}
            db.add(Card(id=2, external_id="craft-target", name="Zielkarte", card_set="Test", set_code="T2", rarity="ultra_rare", card_type="Monster", attribute="LIGHT", image_url="https://example.com/card.jpg"))
            db.flush()
            db.add(CardDetails(card_id=1, name_de="Test", description_de="Deutscher Kartentext", archetype="Testgruppe"))
            for pid, card, rarity in ((1,1,"rare"),(2,2,"rare"),(3,2,"ultra_rare"),(4,1,None)):
                db.add(CardPrinting(id=pid, card_id=card, external_provider="test", external_printing_id=str(pid), rarity=rarity, set_code=f"TEST-{pid}"))
            db.flush()
            kind = variant(db, 1, "rare", 1); kind.printing_id = 1; db.flush()
            self.vid = kind.id
            change_stock(db, 3, kind, 10, "fixture", "stock3")
            change_stock(db, 4, kind, 3, "fixture", "stock4")
            seed_crafting(db)
            book_currency(db, 3, "rare_cp", 60, "funds-rare", "reward")
            book_currency(db, 3, "ultra_rare_cp", 60, "funds-ultra", "reward")
            db.commit()

    def post(self, path, body, user=3, key="craft-test-key-001"):
        return self.client.post(path, json=body, headers={**self.tokens[user], "Idempotency-Key": key})

    def get(self, path, user=3): return self.client.get(path, headers=self.tokens[user])

    def detail(self, pid=1):
        response = self.get(f"/api/crafting/cards/{pid}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_wallet_uses_only_existing_rarities_and_no_shop_currency(self):
        response = self.get('/api/crafting/balances')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({r['currency_key'] for r in response.json()}, {'rare_cp','ultra_rare_cp'})
        self.assertEqual(self.detail()['quantity'], 10)
        self.assertEqual(self.detail()['dismantle_available_quantity'], 9)
        with self.sessions() as db: self.assertEqual(db.get(User, 3).credits, 500)

    def test_dismantle_craft_exact_printing_ledgers_and_replay(self):
        body = {'card_printing_id':1,'quantity':3}
        quote = self.post('/api/crafting/preview', {**body,'type':'dismantle'}).json()
        response = self.post('/api/crafting/dismantle', {**body,'quote_hash':quote['quote_hash']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['new_balance'],90)
        self.assertEqual(self.post('/api/crafting/dismantle',{**body,'quote_hash':quote['quote_hash']}).json(),response.json())
        made=self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':1},key='craft-target-key')
        self.assertEqual(made.status_code,200,made.text)
        self.assertEqual(made.json()['new_balance'],60)
        self.assertEqual(self.detail(2)['quantity'],1)
        self.assertEqual(self.detail(3)['quantity'],0)
        self.assertEqual(self.detail()['quantity'],7)
        with self.sessions() as db:
            self.assertEqual(db.get(User,3).credits,500)
            self.assertEqual(db.scalar(select(func.sum(InventoryItem.quantity)).where(InventoryItem.user_id==3)),8)
            self.assertEqual(db.scalar(select(func.count(CraftingTransaction.id)).where(CraftingTransaction.type.in_(['craft','dismantle']))),2)
            types=set(db.scalars(select(HubEvent.event_type)))
            self.assertTrue({'card_dismantled','card_crafted','crafting_currency_earned','crafting_currency_spent'}<=types)

    def test_trade_reservations_and_protection_reduce_available_stock(self):
        with self.sessions() as db:
            stock=db.scalar(select(VariantInventory).where(VariantInventory.user_id==3));stock.reserved=2
            db.add(InventoryReservation(user_id=3,variant_id=self.vid,quantity=2,reference='trade-test',active=True))
            db.add(UserCardPreference(user_id=3,card_printing_id=1,protected_quantity=3,favorite=True));db.commit()
        self.assertEqual(self.detail()['dismantle_available_quantity'],5)
        self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':6}).status_code,409)
        self.assertEqual(self.detail()['quantity'],10)
        self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':5},key='free-five-cards').status_code,200)
        self.assertEqual(self.detail()['quantity'],5)
        self.assertEqual(self.detail()['reserved'],2)

    def test_bound_unknown_and_insufficient_cp_cannot_be_consumed(self):
        with self.sessions() as db:
            kind=db.get(CardVariant,self.vid)
            change_stock(db,3,kind,2,'bound_fixture','bound-fixture',bound=True);db.commit()
        self.assertEqual(self.detail()['bound_quantity'],2)
        self.assertEqual(self.detail()['dismantle_available_quantity'],9)
        self.assertEqual(self.post('/api/crafting/craft',{'card_printing_id':4,'quantity':1}).status_code,409)
        self.assertEqual(self.post('/api/crafting/craft',{'card_printing_id':3,'quantity':3}).status_code,409)
        self.assertEqual(self.detail(3)['quantity'],0)

    def test_invalid_and_other_users_requests_do_not_touch_inventory(self):
        for quantity in (0,-1,True,1.5,1001):
            self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':quantity}).status_code,422)
        self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':4},user=4).status_code,409)
        self.assertEqual(self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':1,'currency_amount':0}).status_code,422)
        self.assertEqual(self.get('/api/admin/crafting/transactions').status_code,403)
        self.assertEqual(self.get('/api/crafting/history',4).json()['total'],0)
        self.assertEqual(self.detail()['quantity'],10)

    def test_stale_quote_rejected_without_any_partial_booking(self):
        body={'card_printing_id':2,'quantity':1}
        quote=self.post('/api/crafting/preview',{**body,'type':'craft'}).json()
        with self.sessions() as db:
            rule=db.scalar(select(CraftingRarityRule).where(CraftingRarityRule.rarity_key=='rare'));rule.craft_cost=40;rule.version+=1;db.commit()
        response=self.post('/api/crafting/craft',{**body,'quote_hash':quote['quote_hash']})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.detail(2)['quantity'],0)
        self.assertEqual(self.detail()['currency_balance'],60)

    def test_same_idempotency_key_cannot_change_action(self):
        self.assertEqual(self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':1}).status_code,200)
        self.assertEqual(self.post('/api/crafting/craft',{'card_printing_id':3,'quantity':1}).status_code,409)

    def test_duplicate_preview_is_confirmed_once_and_stale_preview_fails(self):
        preview=self.post('/api/crafting/duplicates/preview',{'keep_quantity':3}).json()
        self.assertEqual(preview['card_quantity'],7)
        self.assertEqual(preview['totals'],{'rare_cp':70})
        body={'keep_quantity':3,'quote_hash':preview['quote_hash']}
        response=self.post('/api/crafting/duplicates/dismantle',body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.detail()['quantity'],3)
        self.assertEqual(self.post('/api/crafting/duplicates/dismantle',body).json(),response.json())
        self.assertEqual(self.post('/api/crafting/duplicates/dismantle',body,key='stale-bulk-preview').status_code,409)

    def test_concurrent_craft_cannot_overspend_cp(self):
        def run(i): return self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':2},key=f'parallel-craft-{i}').status_code
        with ThreadPoolExecutor(max_workers=2) as pool: codes=list(pool.map(run,[1,2]))
        self.assertEqual(sorted(codes),[200,409])
        self.assertEqual(self.detail(2)['quantity'],2)
        self.assertEqual(self.detail()['currency_balance'],0)

    def test_admin_adjustments_require_password_permissions_and_audit(self):
        body={'currency_key':'rare_cp','amount':20,'password':self.password,'reason':'Testkorrektur CP'}
        self.assertEqual(self.post('/api/admin/crafting/users/3/adjust',body,user=3).status_code,403)
        self.assertEqual(self.post('/api/admin/crafting/users/3/adjust',{**body,'password':'wrong'},user=2).status_code,403)
        response=self.post('/api/admin/crafting/users/3/adjust',body,user=2)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['balance_after'],80)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id)).where(AdminAuditEvent.action=='crafting_adjustment')),1)
            self.assertEqual(db.scalar(select(func.count(HubEvent.id)).where(HubEvent.user_id==3,HubEvent.event_type=='crafting_currency_earned')),2)

    def test_rules_only_allow_catalog_rarities_no_profitable_loop(self):
        rule=self.get('/api/admin/crafting/rules',2).json()['rules'][0]
        body={**{k:v for k,v in rule.items() if k!='id'},'password':self.password,'reason':'Regeltest Crafting'}
        self.assertEqual(self.post('/api/admin/crafting/rules',{**body,'rarity_key':'invented_rare'},user=2).status_code,400)
        self.assertEqual(self.post(f"/api/admin/crafting/rules/{rule['id']}",{**body,'craft_cost':5},user=2).status_code,422)
        response=self.post(f"/api/admin/crafting/rules/{rule['id']}",{**body,'craft_cost':40},user=2)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['version'],2)

    def test_catalog_filter_printings_and_affordability(self):
        response=self.get('/api/crafting/cards?card_id=2&rarity=rare&only_affordable=true')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([r['card_printing_id'] for r in response.json()['items']],[2])
        response=self.get('/api/crafting/cards?owned_only=true')
        self.assertEqual(response.json()['total'],1)
        response=self.get('/api/crafting/filters')
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('Monster',response.json()['types'])
        self.assertIn('Testgruppe',response.json()['archetypes'])
        response=self.get('/api/crafting/cards?card_type=Monster&archetype=Testgruppe&owned_only=true')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['total'],1)

    def test_migration_preserves_stock_ids_reservations_and_unknown_rarity(self):
        with self.sessions() as db:
            stock=db.scalar(select(VariantInventory).where(VariantInventory.user_id==3));before=(stock.id,stock.quantity,stock.reserved)
            unknown=variant(db,2,legacy=True);change_stock(db,3,unknown,1,'legacy_fixture','legacy-proof')
            migrate_inventory(db);db.commit();db.refresh(stock)
            self.assertEqual((stock.id,stock.quantity,stock.reserved),before)
            self.assertIsNone(db.get(CardPrinting,unknown.printing_id).rarity)
            self.assertEqual(db.get(CardVariant,self.vid).printing_id,1)

    def test_shared_reward_delivery_supports_cp_and_does_not_award_xp(self):
        from app.modules.grants import Draft, preview, apply_grant, digest
        with self.sessions() as db:
            user=db.get(User,3)
            draft=Draft(user_id=3,reason='Saisonbelohnung Craft Points',items=[{'kind':'crafting_currency','currency_key':'rare_cp','quantity':10}])
            snap=preview(db,None,draft,system=True)
            apply_grant(db,user,None,draft,snap,digest(snap),source='season');db.commit()
        self.assertEqual(self.detail()['currency_balance'],70)
        with self.sessions() as db: self.assertEqual(db.scalar(select(func.count(SeasonProgress.id))),0)

    def test_crafting_missions_track_events_without_automatic_xp(self):
        from app.modules.seasons import progress_payload
        with self.sessions() as db:
            now=datetime.utcnow()
            season=Season(name='Crafting Test',description='',state='published',starts_at=now-timedelta(seconds=1),ends_at=now+timedelta(days=1),claim_until=now+timedelta(days=2),rules_json=json.dumps({'opening_xp':10,'levels':[],'quests':[{'period':'daily','mission_type':'dismantle_card','target':2,'xp':0}]}))
            db.add(season);db.commit();sid=season.id
        self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':2}).status_code,200)
        with self.sessions() as db:
            result=progress_payload(db,db.get(User,3),db.get(Season,sid))
            self.assertEqual(result['quest_progress'][0]['count'],2)
            self.assertEqual(result['xp'],0)

    def test_failure_after_cp_booking_rolls_back_stock_currency_events_and_journal(self):
        with self.sessions() as db:
            before_tx=db.scalar(select(func.count(CraftingTransaction.id)))
            before_events=db.scalar(select(func.count(HubEvent.id)))
        with patch('app.modules.crafting.change_stock',side_effect=RuntimeError('forced stock failure')):
            with self.assertRaises(RuntimeError):
                self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':1})
        self.assertEqual(self.detail()['currency_balance'],60)
        self.assertEqual(self.detail(2)['quantity'],0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(CraftingTransaction.id))),before_tx)
            self.assertEqual(db.scalar(select(func.count(HubEvent.id))),before_events)

    def test_currencies_cannot_be_converted_or_chosen_by_the_player(self):
        response=self.post('/api/crafting/craft',{'card_printing_id':3,'quantity':1})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.detail(3)['currency_balance'],30)
        self.assertEqual(self.detail()['currency_balance'],60)
        response=self.post('/api/crafting/craft',{'card_printing_id':3,'quantity':1,'currency_key':'rare_cp'},key='forbidden-conversion')
        self.assertEqual(response.status_code,422)

    def test_catalog_provider_rarity_can_be_explicitly_assigned_without_fake_currency(self):
        with self.sessions() as db:
            db.get(CardPrinting,2).provider_rarity_name='Test Provider Rare';db.commit()
        body={'rarity_key':'test_provider_rare','currency_key':'rare_cp','display_name':'Test Provider Rare',
            'password':self.password,'reason':'Belegte Provider-Zuordnung'}
        response=self.post('/api/admin/crafting/rules',body,user=2)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.detail(2)['rule']['rarity_key'],'test_provider_rare')
        response=self.get('/api/crafting/cards?rarity=test_provider_rare&only_affordable=true')
        self.assertEqual([r['card_printing_id'] for r in response.json()['items']],[2])

    def test_admin_stats_are_read_only_and_report_gross_cp_movements(self):
        self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':2})
        self.post('/api/crafting/craft',{'card_printing_id':2,'quantity':1},key='stats-craft-card')
        response=self.get('/api/admin/crafting/stats',2)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['today']['dismantle'],2)
        self.assertEqual(response.json()['today']['craft'],1)
        rare=next(row for row in response.json()['currency_today'] if row['currency_key']=='rare_cp')
        self.assertEqual(rare['earned'],80)
        self.assertEqual(rare['spent'],30)

    def test_crafting_quest_xp_farming_is_rejected(self):
        from pydantic import ValidationError
        from app.modules.seasons import Quest
        with self.assertRaises(ValidationError): Quest(period='daily',mission_type='craft_card',target=1,xp=20)
        with self.assertRaises(ValidationError): Quest(period='daily',mission_type='craft_rarity',target=1,xp=0)

    def test_duel_reservation_keeps_exact_printing_locked(self):
        from app.db.models import DuelLobby, DuelPreparation, DuelRuleProfile, DuelStockReservation
        with self.sessions() as db:
            db.add(DuelRuleProfile(id='craft-profile',name='Testprofil',list_name='Test',sources_json='[]'))
            db.flush()
            db.add(DuelLobby(id='craft-lobby',code='CRAFT123',host_id=3,profile_id='craft-profile',expires_at=datetime.utcnow()+timedelta(minutes=5)))
            db.flush()
            db.add(DuelPreparation(id='craft-preparation',lobby_id='craft-lobby',profile_id='craft-profile',snapshot_json='{}',snapshot_hash='a'*64,expires_at=datetime.utcnow()+timedelta(minutes=5)))
            db.flush()
            stock=db.scalar(select(VariantInventory).where(VariantInventory.user_id==3));stock.reserved=4
            db.add(DuelStockReservation(preparation_id='craft-preparation',stock_id=stock.id,quantity=4,active=True));db.commit()
        self.assertEqual(self.detail()['dismantle_available_quantity'],5)
        self.assertEqual(self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':6}).status_code,409)
        response=self.post('/api/crafting/dismantle',{'card_printing_id':1,'quantity':5},key='duel-free-stock-only')
        self.assertEqual(response.status_code,200,response.text)
        with self.sessions() as db:
            stock=db.scalar(select(VariantInventory).where(VariantInventory.user_id==3))
            self.assertEqual(stock.quantity,5);self.assertEqual(stock.reserved,4)
            self.assertEqual(stock.card_printing_id,1)


