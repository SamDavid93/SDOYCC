"""Real native AI test, isolated accounts/database, no production writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.sync_api import sync_playwright,expect
from browser_smoke import ROOT,free_port,wait_ready
from duel_worker_browser_checks import seed_worker_database


def run():
    api_port,ui_port=free_port(),free_port()
    api_url,ui_url=f'http://127.0.0.1:{api_port}',f'http://127.0.0.1:{ui_port}'
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
        database=Path(temporary)/'practice.db'
        env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database),'APP_ENV':'development','ENABLE_DEMO_AUTH':'true',
            'ENABLE_DUEL_WORKER_LAB':'true','CORS_ORIGINS':ui_url,'VITE_API_BASE_URL':api_url+'/api','VITE_BASE_PATH':'/','FRONTEND_URL':ui_url+'/'}
        with (ROOT/'artifacts/duel-practice-servers.log').open('w',encoding='utf-8') as log:
            flags=subprocess.CREATE_NO_WINDOW
            backend=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--app-dir','backend','--port',str(api_port)],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=flags)
            frontend=subprocess.Popen(['C:/Program Files/nodejs/node.exe',str(ROOT/'node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(ui_port)],cwd=ROOT/'frontend',env=env,stdout=log,stderr=log,creationflags=flags)
            run_id=None;engine=None
            try:
                wait_ready(api_url+'/api/health',backend,timeout=180);wait_ready(ui_url,frontend)
                token,guest_token,deck,_guest_deck,baseline=seed_worker_database(database)
                from sqlalchemy import create_engine,select,func
                from sqlalchemy.orm import Session
                from app.db.models import User,PlayerDeck,VariantInventory,InventoryTransaction,DuelWorkerRun
                engine=create_engine('sqlite:///'+str(database))
                with Session(engine) as db:
                    db.get(User,db.get(PlayerDeck,deck).user_id).role='admin';db.commit()
                with httpx.Client(base_url=api_url,headers={'Authorization':'Bearer '+token},timeout=60) as client,sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    context=browser.new_context(viewport={'width':1440,'height':1000})
                    context.add_init_script('sessionStorage.setItem("hub-session",'+json.dumps(token)+')')
                    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(ui_url+'/#/duel-zone')
                    page.get_by_label('Dein Deck',exact=True).select_option(deck)
                    page.get_by_label('Gegner',exact=True).select_option('bot')
                    expect(page.get_by_role('heading',name='KI-Testduell',exact=True)).to_be_visible()
                    page.screenshot(path=str(ROOT/'artifacts/duel-practice-selection.png'),full_page=True)
                    page.get_by_role('button',name='KI-Testduell starten',exact=True).click()
                    expect(page.locator('.duel-worker-table.is-playing')).to_be_visible(timeout=30000)
                    run_id=client.get('/api/duel-zone/me').json()['worker_run_id']
                    endpoint='/api/duel-zone/worker/runs/'+run_id
                    assert client.get(endpoint,headers={'Authorization':'Bearer '+guest_token}).status_code==404
                    assert client.post('/api/duel-zone/worker/practice',json={'deck_id':deck},headers={'Authorization':'Bearer '+guest_token,'Idempotency-Key':'guest-practice-rejected'}).status_code==403
                    page.locator('.arena-phase-orb').click()
                    page.get_by_role('button',name='Endphase · Zug beenden',exact=True).click()
                    deadline=time.monotonic()+35
                    events=[];state=None
                    while time.monotonic()<deadline:
                        reply=client.get(endpoint);reply.raise_for_status();state=reply.json()
                        assert state['state']=='running',state
                        board=state['board'];events=board['events']
                        assert all(card is None for card in board['boards'][1]['hand'])
                        if board['turn_number']>=3 and board['prompt'] and board['boards'][0]['lp']<8000:break
                        if board['turn_number']>=3 and board['prompt']:
                            own_prompt=board['prompt']
                            end=next((i for i,c in enumerate(own_prompt['choices']) if c['label']=='Zug beenden'),None)
                            if end is not None:
                                response=client.post(endpoint+'/answer',json={'prompt':own_prompt['id'],'selected':[end]})
                                response.raise_for_status()
                        page.wait_for_timeout(200)
                    else:raise AssertionError('AI failed to summon, attack and return control: '+json.dumps(state))
                    assert any(event['kind']=='summon' for event in events),events
                    assert any(event['kind']=='attack' for event in events),events
                    page.reload()
                    expect(page.locator('.duel-worker-table.is-playing')).to_be_visible(timeout=10000)
                    page.screenshot(path=str(ROOT/'artifacts/duel-practice-playing.png'),full_page=True)
                    result=client.post(endpoint+'/surrender',json={});result.raise_for_status()
                    assert result.json()['state']=='finished'
                    with Session(engine) as db:
                        assert db.scalar(select(func.sum(VariantInventory.reserved)))==0
                        assert baseline==(db.scalar(select(func.sum(VariantInventory.quantity))),db.scalar(select(func.count(InventoryTransaction.id))))
                        assert db.get(DuelWorkerRun,run_id).state=='finished'
                    assert not errors,errors
                    browser.close()
                    print(json.dumps({'status':'passed','native_core':True,'checks':['admin selection','non-admin rejected','private hand','autonomous summon attack and turn end','LP damage','reload','surrender','inventory unchanged'],'console_errors':errors}))
                engine.dispose()
            finally:
                if run_id:
                    try:httpx.post(api_url+'/api/duel-zone/worker/runs/'+run_id+'/surrender',json={},headers={'Authorization':'Bearer '+token},timeout=10)
                    except Exception:pass
                if engine is not None:engine.dispose()
                for process in (frontend,backend):
                    if process.poll() is None:
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:process.kill()


if __name__=='__main__':run()
