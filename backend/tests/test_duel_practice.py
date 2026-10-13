import asyncio
import json
import struct
from contextlib import asynccontextmanager
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select
from app.core.config import settings
from app.db.models import DuelWorkerRun, DuelStockReservation, User, VariantInventory
from app.main import app
from app.modules.duel_worker import WorkerService, load_module
from test_duel_preparation import PreparationFixture
from test_duel_worker import FakeAdapter, FakeEngine, packet, prompt


class PracticeEngine(FakeEngine):
    async def command(self, command):
        self.commands.append(command)
        if command['op']=='start': return packet(prompt(0))
        owner=1 if len(self.commands)%2==0 else 0
        return packet(prompt(owner))


class PracticeAdapter(FakeAdapter):
    def create(self):
        engine=PracticeEngine();self.engines.append(engine)
        return engine,load_module('protocol').Projection({10001:{'name':'Test'}})


class PracticeTests(PreparationFixture):
    def setUp(self):
        super().setUp()
        self.client.post(f'/api/duel-zone/lobbies/{self.room["id"]}/leave',
            json={'version':self.room['version']},headers={**self.headers,'Idempotency-Key':str(uuid4())})
        with self.sessions() as db:
            db.get(User,1).role='admin';db.commit()
        self.adapter=PracticeAdapter();self.runtime=WorkerService(self.sessions,self.adapter)
        self.old_runtime=getattr(app.state,'duel_worker',None)
        self.old_flag=settings.enable_duel_worker_lab
        settings.enable_duel_worker_lab=True;app.state.duel_worker=self.runtime
        @asynccontextmanager
        async def lifespan(_): yield
        self.lifespan=patch.object(app.router,'lifespan_context',lifespan)
        self.lifespan.start();self.client.__enter__()

    def tearDown(self):
        self.client.portal.call(self.runtime.close)
        self.client.__exit__(None,None,None);self.lifespan.stop()
        app.state.duel_worker=self.old_runtime;settings.enable_duel_worker_lab=self.old_flag
        super().tearDown()

    def start(self,headers=None,deck=None,key=None):
        return self.client.post('/api/duel-zone/worker/practice',json={'deck_id':deck or self.decks[0]['id']},
            headers={**(headers or self.headers),'Idempotency-Key':key or str(uuid4())})

    def test_admin_start_is_private_inventory_neutral_and_idempotent(self):
        with self.sessions() as db:
            before=[(s.id,s.quantity,s.reserved) for s in db.scalars(select(VariantInventory).order_by(VariantInventory.id))]
        key=str(uuid4());result=self.start(key=key)
        self.assertEqual(result.status_code,200,result.text)
        data=result.json();self.assertTrue(data['practice']);self.assertEqual(data['seat'],0)
        self.assertEqual(self.start(key=key).json()['id'],data['id'])
        self.assertEqual(sum(command['op']=='start' for engine in self.adapter.engines for command in engine.commands),1)
        self.assertEqual(self.client.get('/api/duel-zone/worker/runs/'+data['id'],headers=self.other_headers).status_code,404)
        with self.sessions() as db:
            self.assertEqual(before,[(s.id,s.quantity,s.reserved) for s in db.scalars(select(VariantInventory).order_by(VariantInventory.id))])
            self.assertEqual(list(db.scalars(select(DuelStockReservation))),[])
        surrender=self.client.post('/api/duel-zone/worker/runs/'+data['id']+'/surrender',json={},headers=self.headers)
        self.assertEqual(surrender.json()['state'],'finished')
        self.assertTrue(self.adapter.engines[0].closed)

    def test_non_admin_and_foreign_deck_rejected(self):
        self.assertEqual(self.start(headers=self.other_headers).status_code,403)
        self.assertEqual(self.start(deck=self.decks[1]['id']).status_code,404)
        with self.sessions() as db:
            db.get(User,1).role='support_admin';db.commit()
        self.assertEqual(self.start().status_code,403)

    def test_bot_moves_without_client_answer_and_role_revocation_stops_run(self):
        data=self.start().json();run_id=data['id']
        result=self.client.post(f'/api/duel-zone/worker/runs/{run_id}/answer',json={
            'prompt':data['board']['prompt']['id'],'selected':[0]},headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.client.portal.call(asyncio.sleep,1.3)
        latest=self.client.get(f'/api/duel-zone/worker/runs/{run_id}',headers=self.headers).json()
        self.assertIsNotNone(latest['board']['prompt'])
        self.assertEqual(len(self.adapter.engines[0].commands),3)
        with self.sessions() as db:
            db.get(User,1).role='user';db.commit()
        latest=self.client.get(f'/api/duel-zone/worker/runs/{run_id}',headers=self.headers).json()
        self.assertEqual(latest['state'],'aborted')
        self.assertEqual(latest['reason'],'session_ended')

    def test_second_start_and_unapproved_rules_rejected(self):
        data=self.start().json()
        self.assertEqual(self.start().status_code,409)
        self.client.post(f'/api/duel-zone/worker/runs/{data["id"]}/surrender',json={},headers=self.headers)
        from app.db.models import DuelRuleProfile
        with self.sessions() as db:
            db.get(DuelRuleProfile,self.profile).engine_approved=False;db.commit()
        self.assertEqual(self.start().status_code,409)
