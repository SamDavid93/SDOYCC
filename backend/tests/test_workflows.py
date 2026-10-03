import base64
import io
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4
from PIL import Image
from sqlalchemy import select, func
from app.core.auth import create_session
from app.core.passwords import hash_password
from app.db.models import (User, Card, CardVariant, VariantInventory, InventoryItem, InventoryTransaction,
    UserBooster, SpecialCard, Grant, GrantBatchRow, MarketListing, MarketProposal, InventoryReservation,
    TradeSettlement, Season, SeasonProgress, SeasonXpEvent, SeasonClaim, BoosterOpening, DiamondTransaction,
    CardPrinting, CardSet, AuthSession, HubNotice)
from app.modules.inventory import variant, change_stock
from app.modules.trading import cleanup
from app.modules.workflow import mutex
from app.modules.seasons import process_opening, period_start
from test_economy import HubTestCase


class WorkflowTests(HubTestCase):
    password = 'Workflow-Test-Passwort-123!'
    @classmethod
    def setUpClass(cls): cls.pwhash = hash_password(cls.password)

    def setUp(self):
        super().setUp(); self.tokens = {}
        with self.sessions() as db:
            for uid, role in [(2,'super_admin'),(3,'user'),(4,'user'),(5,'support_admin'),(6,'admin')]:
                u=User(id=uid,username=f'user{uid}',display_name=f'Nutzer {uid}',twitch_id=str(uid*100),password_hash=self.pwhash,role=role,credits=500)
                db.add(u); db.flush(); self.tokens[uid]={'Authorization':'Bearer '+create_session(db,u)}
            for uid in [3,4,6]:
                kind=variant(db,1,'rare',1); change_stock(db,uid,kind,10,'fixture',f'fixture:{uid}')
                db.add(UserBooster(user_id=uid,booster_id=1,quantity=10))
            self.variant_id=kind.id; db.commit()

    def post(self,path,body=None,uid=2,key=None):
        return self.client.post(path,json=body or {},headers={**self.tokens[uid],'Idempotency-Key':key or str(uuid4())})

    def get(self,path,uid=2): return self.client.get(path,headers=self.tokens[uid])
    def ok(self,response):
        self.assertEqual(response.status_code,200,response.text); return response.json()
    def admin(self,**kw): return {'password':self.password,'reason':'Nachvollziehbare Testaktion',**kw}
    def packet(self,quantity=2): return [{'variant_id':self.variant_id,'quantity':quantity}]

    def listing(self,uid=3,quantity=2,wanted=None):
        row=self.ok(self.post('/api/trade/listings',{'title':'Kartenpaket zum Tausch','description':'Testangebot','items':self.packet(quantity),'wanted':wanted or [],'days':7},uid))
        return self.ok(self.post(f"/api/trade/listings/{row['id']}/publish",{'version':1},uid))
    def proposal(self,listing,uid=4,quantity=3):
        return self.ok(self.post(f"/api/trade/proposals/to/{listing['id']}",{'version':listing['version'],'items':self.packet(quantity)},uid))
    def assert_inventory(self):
        with self.sessions() as db:
            for stock in db.scalars(select(VariantInventory)):
                reserved=db.scalar(select(func.coalesce(func.sum(InventoryReservation.quantity),0)).where(InventoryReservation.user_id==stock.user_id,InventoryReservation.variant_id==stock.variant_id,InventoryReservation.active.is_(True)))
                self.assertEqual(stock.reserved,reserved)
                journal=db.scalar(select(func.sum(InventoryTransaction.amount)).where(InventoryTransaction.user_id==stock.user_id,InventoryTransaction.variant_id==stock.variant_id,InventoryTransaction.bound==stock.bound))
                self.assertEqual(stock.quantity,journal)
            for item in db.scalars(select(InventoryItem)):
                self.assertEqual(item.quantity,db.scalar(select(func.sum(VariantInventory.quantity)).join(CardVariant).where(VariantInventory.user_id==item.user_id,CardVariant.card_id==item.card_id)))

    def test_trade_reserves_and_settles_once(self):
        listing=self.listing(); proposal=self.proposal(listing)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(VariantInventory.reserved).where(VariantInventory.user_id==3)),2)
        path=f"/api/trade/proposals/{proposal['id']}/accept"
        first=self.ok(self.post(path,{'version':1},3,key='accept-once-key'))
        self.assertEqual(first,self.ok(self.post(path,{'version':1},3,key='accept-once-key')))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id==3)),11)
            self.assertEqual(db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id==4)),9)
            self.assertEqual(db.scalar(select(func.count(TradeSettlement.id))),1)
        self.assert_inventory()
        self.assertEqual(len(self.ok(self.get('/api/trade/me/history',3))['items']),1)
        self.assertEqual(len(self.ok(self.get('/api/trade/me/history',6))['items']),0)

    def test_parallel_publication_cannot_reserve_twice(self):
        def create(n):
            return self.post('/api/trade/listings',{'title':f'Paket {n}','items':self.packet(8)},3).json()['id']
        ids=[create(1),create(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda i:self.post(f'/api/trade/listings/{i}/publish',{'version':1},3),ids))
        self.assertEqual(sorted(r.status_code for r in results),[200,409]); self.assert_inventory()

    def test_two_simultaneous_acceptances_settle_only_once(self):
        listing=self.listing(); a=self.proposal(listing); b=self.proposal(listing,6)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda p:self.post(f"/api/trade/proposals/{p['id']}/accept",{'version':1},3),[a,b]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409]); self.assert_inventory()

    def test_trade_midway_failure_rolls_back_both_sides(self):
        listing=self.listing(); proposal=self.proposal(listing)
        from app.modules.inventory import change_stock as real
        def fail(db,uid,kind,amount,*args,**kw):
            if amount>0: raise RuntimeError('simulated failure')
            return real(db,uid,kind,amount,*args,**kw)
        with patch('app.modules.trading.change_stock',side_effect=fail):
            with self.assertRaises(RuntimeError): self.post(f"/api/trade/proposals/{proposal['id']}/accept",{'version':1},3)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(TradeSettlement.id))),0)
            self.assertEqual(db.get(MarketListing,listing['id']).state,'open')
        self.assert_inventory()

    def test_counter_invalidates_old_proposals_and_version(self):
        listing=self.listing(); p=self.proposal(listing)
        self.ok(self.post(f"/api/trade/counter/{listing['id']}",{'version':1,'wanted':[{'card_id':1,'quantity':2}],'description':'Neue Konditionen'},3))
        self.assertEqual(self.post(f"/api/trade/proposals/{p['id']}/accept",{'version':1},3).status_code,409)
        self.assertEqual(self.post(f"/api/trade/proposals/to/{listing['id']}",{'version':1,'items':self.packet()},4).status_code,409)
        self.assert_inventory()

    def test_expiry_cleanup_restart_releases_once(self):
        listing=self.listing(); self.proposal(listing)
        with self.sessions() as db:
            db.get(MarketListing,listing['id']).expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
        for _ in range(2):
            with self.sessions() as db: mutex(db);cleanup(db);db.commit()
        with self.sessions() as db: self.assertEqual(db.get(MarketListing,listing['id']).state,'expired')
        self.assert_inventory()

    def test_self_foreign_bound_legacy_and_blocked_rejected(self):
        listing=self.listing()
        self.assertEqual(self.post(f"/api/trade/proposals/to/{listing['id']}",{'version':1,'items':self.packet()},3).status_code,400)
        self.assertEqual(self.post(f"/api/trade/listings/{listing['id']}/cancel",{'version':1},4).status_code,403)
        self.ok(self.post('/api/trade/blocks/4',{'blocked':True},3))
        self.assertEqual(self.post(f"/api/trade/proposals/to/{listing['id']}",{'version':1,'items':self.packet()},4).status_code,403)
        with self.sessions() as db:
            kind=variant(db,1,legacy=True);change_stock(db,4,kind,5,'fixture','legacy-test'); legacy_id=kind.id;db.commit()
        self.assertEqual(self.post('/api/trade/listings',{'title':'Altbestand','items':[{'variant_id':legacy_id,'quantity':1}]},4).status_code,400)

    def test_moderation_and_trade_restriction(self):
        listing=self.listing();self.proposal(listing)
        report=self.ok(self.post(f"/api/trade/reports/{listing['id']}",{'reason':'Unpassende Handelsanzeige'},4))
        self.assertEqual(self.post(f"/api/trade/moderation/{report['id']}",self.admin(close_listing=True,restrict_days=2),5).status_code,403)
        self.ok(self.post(f"/api/trade/moderation/{report['id']}",self.admin(close_listing=True,restrict_days=2)))
        self.assertEqual(self.post('/api/trade/listings',{'title':'Gesperrter Handel','items':self.packet()},3).status_code,403)
        self.assert_inventory()

    def test_set_assistant_and_snapshot_survive_catalog_change(self):
        with self.sessions() as db:
            s=CardSet(name='Ein Kartenset',external_id='set-test');db.add(s);db.flush()
            db.add(CardPrinting(card_id=1,set_id=s.id,external_provider='test',external_printing_id='set-print',rarity='rare'));sid=s.id;db.commit()
        result=self.ok(self.get(f'/api/trade/sets/{sid}/preview',3));self.assertTrue(result['complete'])
        listing=self.listing()
        with self.sessions() as db: db.get(Card,1).name='Geänderter Katalogname';db.commit()
        self.assertEqual(self.ok(self.get(f"/api/trade/listings/{listing['id']}",4))['items'][0]['card']['name'],'Test')

    def special(self,limit=2):
        b=io.BytesIO();Image.new('RGB',(200,290),'red').save(b,format='PNG')
        body=self.admin(name='Community Testkarte',description='Sonderkarte der Community',edition='Testedition',rarity='ultra_rare',tradable=True,supply_limit=limit,image=base64.b64encode(b.getvalue()).decode())
        row=self.ok(self.post('/api/admin/advanced/special-cards',body))
        self.ok(self.post(f"/api/admin/advanced/special-cards/{row['id']}/state",self.admin(state='active')))
        return row

    def grant_special(self,card_id,uid=3,quantity=1):
        body={'user_id':uid,'reason':'Besondere Community-Belohnung','items':[{'kind':'special','card_id':card_id,'quantity':quantity}]}
        response=self.post('/api/admin/grants/preview',body)
        if response.status_code!=200:return response
        return self.post('/api/admin/grants',{**body,'password':self.password,'confirmation':f'user{uid}','preview_hash':response.json()['preview_hash']})

    def test_special_card_publish_supply_and_archive(self):
        row=self.special();self.ok(self.grant_special(row['card_id'],quantity=2))
        self.assertEqual(self.grant_special(row['card_id'],4).status_code,409)
        image=self.client.get(f"/api/community/cards/{row['card_id']}/image")
        self.assertEqual(image.headers['content-type'],'image/jpeg')
        self.ok(self.post(f"/api/admin/advanced/special-cards/{row['id']}/state",self.admin(state='archived')))
        self.assertEqual(self.grant_special(row['card_id']).status_code,400)
        self.assert_inventory()

    def test_invalid_special_image_and_permission(self):
        body=self.admin(name='Testkarte',description='Test',edition='Test',rarity='rare',image='PHN2Zz48L3N2Zz4=')
        self.assertEqual(self.post('/api/admin/advanced/special-cards',body).status_code,400)
        self.assertEqual(self.post('/api/admin/advanced/special-cards',body,6).status_code,403)

    def batch(self):
        body=self.admin(user_ids=[3,4,3],items=[{'kind':'points','quantity':100}])
        snap=self.ok(self.post('/api/admin/advanced/batches/preview',body))
        return self.ok(self.post('/api/admin/advanced/batches',{**body,'preview_hash':snap['preview_hash']}))

    def test_batch_frozen_recipients_partial_resume_and_once(self):
        batch=self.batch()
        with self.sessions() as db:db.get(User,4).is_active=False;db.commit()
        result=self.ok(self.post(f"/api/admin/advanced/batches/{batch['id']}/run",self.admin()))
        self.assertEqual([r['state'] for r in result['rows']],['done','rejected'])
        with self.sessions() as db:db.get(User,4).is_active=True;db.commit()
        for _ in range(2):self.ok(self.post(f"/api/admin/advanced/batches/{batch['id']}/run",self.admin()))
        with self.sessions() as db:
            self.assertEqual(db.get(User,3).credits,600);self.assertEqual(db.get(User,4).credits,600)
            self.assertEqual(db.scalar(select(func.count(Grant.id))),2)

    def correction(self,kind,reference,qty=1):
        body=self.admin(user_id=3,confirmation='user3',kind=kind,reference_id=reference,quantity=qty)
        snap=self.post('/api/admin/advanced/corrections/preview',body)
        if snap.status_code!=200:return snap
        return self.post('/api/admin/advanced/corrections',{**body,'preview_hash':snap.json()['preview_hash']})

    def test_correction_original_limit_and_reserved_protection(self):
        with self.sessions() as db:ref=db.scalar(select(InventoryTransaction.id).where(InventoryTransaction.user_id==3))
        self.listing(quantity=9)
        self.assertEqual(self.correction('card',ref,2).status_code,409)
        self.ok(self.correction('card',ref,1));self.assertEqual(self.correction('card',ref,1).status_code,409)
        self.assert_inventory()

    def test_points_correction_does_not_erase_original(self):
        with self.sessions() as db:
            t=DiamondTransaction(user_id=3,amount=50,balance_after=500,reason='fixture',reference='test-credit');db.add(t);db.flush();ref=t.id;db.commit()
        self.ok(self.correction('points',ref,40));self.assertEqual(self.correction('points',ref,11).status_code,409)
        with self.sessions() as db:self.assertEqual(db.get(DiamondTransaction,ref).amount,50);self.assertEqual(db.get(User,3).credits,460)

    def season(self,**overrides):
        now=datetime.now(timezone.utc)
        body=self.admin(name='Testsaison',description='Kostenlose Testsaison',starts_at=(now-timedelta(seconds=1)).isoformat(),ends_at=(now+timedelta(days=7)).isoformat(),claim_until=(now+timedelta(days=9)).isoformat(),opening_xp=10,
            levels=[{'xp':10,'items':[{'kind':'points','quantity':100}]},{'xp':30,'items':[{'kind':'pack','booster_id':1,'quantity':1}]}],quests=[{'period':'daily','openings':2,'xp':20}],**overrides)
        row=self.ok(self.post('/api/admin/seasons',body));self.ok(self.post(f"/api/admin/seasons/{row['id']}/publish",self.admin()));return row

    def opening(self,uid=3,key=None): return self.ok(self.post('/api/boosters/1/open',uid=uid,key=key))

    def test_season_openings_quests_and_claim_once(self):
        row=self.season();self.opening(key='season-opening-once');self.opening(key='season-opening-once')
        current=self.ok(self.get('/api/seasons/current',3))['season'];self.assertEqual(current['xp'],10)
        self.opening();current=self.ok(self.get('/api/seasons/current',3))['season'];self.assertEqual(current['xp'],40)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.post(f"/api/seasons/{row['id']}/rewards/1/claim",uid=3),range(2)))
        self.assertTrue(all(r.status_code==200 for r in results),[r.text for r in results])
        with self.sessions() as db:
            self.assertEqual(db.get(User,3).credits,600);self.assertEqual(db.scalar(select(func.count(SeasonClaim.id))),1)
        self.assert_inventory()

    def test_season_claim_locked_expired_and_blocked(self):
        row=self.season();path=f"/api/seasons/{row['id']}/rewards/1/claim"
        self.assertEqual(self.post(path,uid=3).status_code,409);self.opening()
        with self.sessions() as db:db.get(Season,row['id']).claim_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
        self.assertEqual(self.post(path,uid=3).status_code,409)
        with self.sessions() as db:db.get(User,3).is_active=False;db.commit()
        self.assertEqual(self.post(path,uid=3).status_code,401)

    def test_season_boundary_and_missing_event_catchup(self):
        row=self.season()
        with self.sessions() as db:
            season=db.get(Season,row['id']);season.ends_at=datetime.utcnow()-timedelta(seconds=1)
            db.add(BoosterOpening(user_id=3,booster_id=1,created_at=season.ends_at-timedelta(microseconds=1)))
            db.add(BoosterOpening(user_id=3,booster_id=1,created_at=season.ends_at));db.commit()
        self.assertEqual(self.ok(self.get('/api/seasons/current',3))['season']['xp'],10)
        self.assertEqual(self.ok(self.get('/api/seasons/current',3))['season']['xp'],10)

    def test_season_claim_failure_rolls_back(self):
        row=self.season();self.opening()
        with patch('app.modules.grants.book_diamonds',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):self.post(f"/api/seasons/{row['id']}/rewards/1/claim",uid=3)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(SeasonClaim.id))),0);self.assertEqual(db.scalar(select(func.count(Grant.id))),0);self.assertEqual(db.get(User,3).credits,500)

    def test_season_publish_overlap_and_rule_immutability(self):
        row=self.season()
        self.assertEqual(self.post(f"/api/admin/seasons/{row['id']}/publish",self.admin()).status_code,409)
        body=self.admin(name='Überlappung',starts_at=datetime.now(timezone.utc).isoformat(),ends_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),claim_until=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),opening_xp=1,levels=[{'xp':1,'items':[{'kind':'points','quantity':1}]}])
        draft=self.ok(self.post('/api/admin/seasons',body));self.assertEqual(self.post(f"/api/admin/seasons/{draft['id']}/publish",self.admin()).status_code,409)
        self.assertEqual(self.post('/api/admin/seasons',body,6).status_code,403)
        self.assertEqual(period_start(datetime(2026,10,25,2,30),'daily'),datetime(2026,10,25))

    def test_notifications_ownership_and_operations_views(self):
        listing=self.listing();self.proposal(listing)
        notices=self.ok(self.get('/api/notifications',3));nid=next(i['id'] for i in notices['items'] if i['id']<0)
        self.assertEqual(self.post(f'/api/notifications/{nid}/read',uid=4).status_code,404)
        self.ok(self.post(f'/api/notifications/{nid}/read',uid=3))
        for path in ['/api/admin/advanced/operations','/api/admin/advanced/special-cards','/api/admin/advanced/batches','/api/admin/seasons','/api/trade/moderation','/api/seasons/me/history','/api/trade/stock','/api/trade/listings','/api/trade/me/proposals','/api/admin/advanced/correction-sources/3?kind=card']:
            self.ok(self.get(path))
        self.assertEqual(self.get('/api/admin/advanced/users.csv',3).status_code,403)
        self.assertEqual(self.get('/api/admin/advanced/users.csv').status_code,200)

    def test_accept_races_cancel_without_losing_cards(self):
        listing=self.listing();p=self.proposal(listing)
        actions=[(f"/api/trade/proposals/{p['id']}/accept",{'version':1}), (f"/api/trade/listings/{listing['id']}/cancel",{'version':1})]
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda a:self.post(a[0],a[1],3),actions))
        self.assertTrue(all(r.status_code in [200,409] for r in results))
        with self.sessions() as db:
            self.assertIn(db.get(MarketListing,listing['id']).state,['completed','cancelled'])
            self.assertEqual(db.scalar(select(func.sum(InventoryItem.quantity))),30)
        self.assert_inventory()

    def test_block_immediately_releases_all_market_reservations(self):
        listing=self.listing();self.proposal(listing)
        result=self.post('/api/admin/users/3/actions',self.admin(action='block',confirmation='user3'))
        self.ok(result)
        with self.sessions() as db:self.assertEqual(db.get(MarketListing,listing['id']).state,'moderated')
        self.assert_inventory()

    def test_season_opening_failure_is_atomic(self):
        self.season()
        with patch('app.modules.seasons.award_xp',side_effect=RuntimeError('XP failure')):
            with self.assertRaises(RuntimeError): self.post('/api/boosters/1/open',uid=3)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(BoosterOpening.id))),0)
            self.assertEqual(db.scalar(select(UserBooster.quantity).where(UserBooster.user_id==3)),10)
            self.assertEqual(db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id==3)),10)
        self.assert_inventory()

    def test_trade_filters_and_personal_pending_packages(self):
        listing=self.listing(wanted=[{'card_id':1,'quantity':4}]);self.proposal(listing,quantity=4)
        for query in ['card_id=1','side=wanted&card_id=1','rarity=rare','fulfillable=true']:
            self.assertEqual(self.ok(self.get('/api/trade/listings?'+query,4))['total'],1)
        self.assertEqual(self.ok(self.get('/api/trade/listings?card_id=99999',4))['total'],0)
        self.assertEqual(self.ok(self.get('/api/trade/me/proposals',4))['total'],1)
        self.assertEqual(len(self.ok(self.get(f"/api/trade/listings/{listing['id']}",6))['proposals']),0)

    def test_claim_extension_version_and_preserved_progress(self):
        row=self.season();self.opening()
        self.ok(self.post(f"/api/admin/seasons/{row['id']}/extend-claims",self.admin(version=1,claim_until=(datetime.now(timezone.utc)+timedelta(days=15)).isoformat())))
        self.assertEqual(self.post(f"/api/admin/seasons/{row['id']}/extend-claims",self.admin(version=1,claim_until=(datetime.now(timezone.utc)+timedelta(days=16)).isoformat())).status_code,409)
        self.assertEqual(self.ok(self.get('/api/seasons/current',3))['season']['xp'],10)

    def test_trade_invalid_idempotency_payload_and_reservation_limit(self):
        body={'title':'Tauschen','items':self.packet(2)}
        self.ok(self.post('/api/trade/listings',body,3,key='listing-conflict-key'))
        self.assertEqual(self.post('/api/trade/listings',{**body,'items':self.packet(3)},3,key='listing-conflict-key').status_code,409)
        self.assertEqual(self.post('/api/trade/listings',{**body,'items':self.packet(11)},3).status_code,409)
        self.assertEqual(self.client.post('/api/trade/listings',json=body,headers=self.headers).status_code,400)

    def test_special_supply_concurrent_and_inventory_kept(self):
        row=self.special(limit=1)
        def grant(uid):return self.grant_special(row['card_id'],uid)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(grant,[3,4]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        with self.sessions() as db:self.assertEqual(db.get(SpecialCard,row['id']).issued,1)
        self.assert_inventory()

    def test_admin_batch_scope_and_correction_after_trade_rejected(self):
        body=self.admin(user_ids=[2,3],items=[{'kind':'points','quantity':1}])
        result=self.ok(self.post('/api/admin/advanced/batches/preview',body,6))
        self.assertEqual(result['rows'][0]['state'],'rejected')
        with self.sessions() as db:ref=db.scalar(select(InventoryTransaction.id).where(InventoryTransaction.user_id==3))
        listing=self.listing();p=self.proposal(listing);self.ok(self.post(f"/api/trade/proposals/{p['id']}/accept",{'version':1},3))
        self.assertEqual(self.correction('card',ref,1).status_code,409)

    def test_eight_parallel_publications_keep_stock_and_reservations(self):
        ids=[self.ok(self.post('/api/trade/listings',{'title':f'Paket Nummer {i}','items':self.packet(3)},3))['id'] for i in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda i:self.post(f'/api/trade/listings/{i}/publish',{'version':1},3),ids))
        self.assertEqual(sum(r.status_code==200 for r in results),3)
        self.assertTrue(all(r.status_code in [200,409] for r in results))
        self.assert_inventory()

    def test_complete_set_validation_and_frozen_conditions(self):
        with self.sessions() as db:
            s=CardSet(name='Vollständiges Testset',external_id='complete-test');db.add(s);db.flush()
            c=Card(name='Fehlende Karte',external_id='missing-test',card_set='Test',set_code='T2',rarity='rare',card_type='Monster',attribute='LIGHT',image_url='')
            db.add(c);db.flush()
            for card_id in [1,c.id]:db.add(CardPrinting(card_id=card_id,set_id=s.id,external_provider='test',external_printing_id=f'complete:{card_id}'))
            sid=s.id;db.commit()
        self.assertFalse(self.ok(self.get(f'/api/trade/sets/{sid}/preview',3))['complete'])
        self.assertEqual(self.post('/api/trade/listings',{'title':'Komplettes Testset','items':self.packet(),'complete_set_id':sid},3).status_code,400)
        listing=self.listing();self.ok(self.post(f"/api/trade/counter/{listing['id']}",{'version':1,'wanted':[{'card_id':1,'quantity':1}],'description':'Neue Bedingungen'},3))
        versions=self.ok(self.get(f"/api/trade/listings/{listing['id']}",4))['versions']
        self.assertEqual([v['version'] for v in versions],[2,1]);self.assertEqual(versions[1]['snapshot']['wanted'],[])

    def test_operational_check_detects_variant_and_xp_mismatch(self):
        result=self.ok(self.get('/api/admin/advanced/operations'))
        self.assertTrue(result['inventory_consistent'] and result['journal_consistent'] and result['reservations_consistent'] and result['xp_consistent'])
        with self.sessions() as db:
            db.scalar(select(VariantInventory).where(VariantInventory.user_id==3)).quantity+=1;db.commit()
        result=self.ok(self.get('/api/admin/advanced/operations'))
        self.assertFalse(result['inventory_consistent']);self.assertFalse(result['journal_consistent'])
