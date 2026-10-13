"""Render real duel components with synthetic frames; never writes account data."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from playwright.sync_api import sync_playwright, expect
from browser_smoke import ROOT, free_port, wait_ready


def run():
    port = free_port()
    url = f'http://127.0.0.1:{port}'
    frontend = ROOT / 'frontend'
    with tempfile.TemporaryDirectory(prefix='.duel-presentation-', dir=frontend) as directory:
        folder = Path(directory)
        assert folder.resolve().is_relative_to(frontend.resolve())
        (folder / 'index.html').write_text('<div id="root"></div><script type="module" src="./check.tsx"></script>', encoding='utf8')
        (folder / 'check.tsx').write_text('''
import React from 'react'
import { createRoot } from 'react-dom/client'
import { DuelWorkerTable } from '../src/pages/DuelWorkerTable'
import '../src/styles.css'
import '../src/pages/decks.css'
sessionStorage.setItem('hub-session', 'synthetic-presentation-token')
const card = {code:1,name:'Testkarte',description:'Deutscher Kartentext',image_url:'/test-card.svg',atk:1000,defense:1000}
const side = {lp:8000,deck:30,hand:[],grave:[],field:[]}
const frame = {id:'presentation',state:'running',seat:0,board:{revision:1,seat:0,turn:0,turn_number:1,phase:4,ended:false,events:[],
boards:[{...side,field:[{zone:4,sequence:0,position:8,card},{zone:8,sequence:0,position:8,card},{zone:8,sequence:1,position:8,card}]},
{...side,field:[{zone:4,sequence:0,position:8,card:null},{zone:8,sequence:0,position:8,card:null}]}],
prompt:{id:7,title:'Auf die Kette reagieren',choices:[{label:'Effekt: Testkarte',card},{label:'Nicht anketten',card:null}]}}}
window.__answers=[]
class Socket {
static OPEN=1;readyState=1
constructor(){window.__socket=this;setTimeout(()=>this.onopen?.(),0)}
send(text){const message=JSON.parse(text);if(message.type==='answer'){window.__answers.push(message);frame.board.prompt=null;frame.board.revision++}if(message.type!=='ping')queueMicrotask(()=>this.onmessage?.({data:JSON.stringify({type:'state',result:frame})}))}
close(){this.readyState=3}
}
window.WebSocket=Socket
window.__showChain=()=>{frame.board.prompt={id:8,title:'Auf die Kette reagieren',choices:[{label:'Effekt: Testkarte',card},{label:'Nicht anketten',card:null}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__showPhase=(turn=0,phase=4)=>{frame.board.turn=turn;frame.board.phase=phase;frame.board.prompt={id:20+frame.board.revision,title:'Aktion wählen',choices:[{label:'Aktivieren: Testkarte',card,action:'activate',location:{owner:0,zone:4,sequence:0}}, {label:phase===4?'Kampfphase':'Hauptphase 2',card:null},{label:'Zug beenden',card:null}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__battle=()=>{frame.board.turn=0;frame.board.phase=16;frame.board.boards[0].field=[{zone:4,sequence:0,position:1,card},{zone:4,sequence:1,position:1,card}];frame.board.boards[1].field=[{zone:4,sequence:0,position:8,card:null},{zone:4,sequence:1,position:1,card}];frame.board.prompt={id:100,title:'Aktion wählen',choices:[{label:'Angreifen: Testkarte',card,action:'attack',location:{owner:0,zone:4,sequence:0}},{label:'Aktivieren: Testkarte',card,action:'activate',location:{owner:0,zone:4,sequence:0}},{label:'Angreifen: Testkarte',card,action:'attack',location:{owner:0,zone:4,sequence:1}},{label:'Zug beenden',card:null}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__targets=()=>{frame.board.prompt={id:101,title:'Karten auswählen',select:true,minimum:1,maximum:1,choices:[{label:'Verdeckte Karte',card:null,location:{owner:1,zone:4,sequence:0}},{label:'Testkarte',card,location:{owner:1,zone:4,sequence:1}}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__log=()=>{frame.board.events.push({id:3,kind:'attack',affected_cards:[{role:'Angreifer',name:'Testkarte'},{role:'Ziel',name:'Verdeckte Karte'}]},{id:4,kind:'chain_step',step:73,number:1,affected_cards:[{role:'Effektkarte',name:'Testkarte'}]});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__effect=(seat)=>{frame.seat=seat;frame.board.seat=seat;frame.board.prompt=null;frame.board.events.push({id:frame.board.events.length+1,kind:'chain',card,source:{owner:0,zone:4,sequence:0},number:1,effect:'Ein bestätigter Testeffekt'});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__feedback=(chain=false)=>{frame.seat=0;frame.board.seat=0;frame.board.turn=0;frame.board.boards[0]={...side,hand:[card],grave:[card],extra:[card],removed:[card],field:[{zone:4,sequence:0,position:1,card},{zone:8,sequence:0,position:8,card}]};frame.board.prompt={id:300,title:chain?'Auf die Kette reagieren':'Aktion wählen',choices:[2,4,8,16,32,64,1].map(zone=>({label:'Aktivieren: Testkarte '+zone,card,...(chain?{}:{action:'activate'}),location:{owner:0,zone,sequence:0}}))};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__announce=(kind,phase,player=1)=>{frame.board.events.push({id:Math.max(0,...frame.board.events.map(e=>e.id))+1,kind,phase,player,number:2});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
createRoot(document.getElementById('root')).render(<DuelWorkerTable runId="presentation" onExit={()=>{}} />)
''', encoding='utf8')
        env = {**os.environ, 'VITE_BASE_PATH': '/'}
        node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe')
        with (ROOT / 'artifacts/duel-presentation-vite.log').open('w') as log:
            process = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=frontend, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                wait_ready(url, process)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width':1440,'height':1000})
                    page.add_init_script("""window.__soundStarts=0; const OriginalAudioContext=window.AudioContext; window.AudioContext=class extends OriginalAudioContext { createBufferSource(){const node=super.createBufferSource();const start=node.start.bind(node);node.start=(...args)=>{window.__soundStarts++;return start(...args)};return node} };""")
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/test-card.svg', lambda route: route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="80" height="120"><rect width="80" height="120" fill="teal"/></svg>'))
                    page.goto(url + '/' + folder.name + '/index.html')
                    expect(page.locator('.duel-chain-overlay')).to_be_visible()
                    for owner in (0,1):
                        monster = page.locator(f'.arena-slot[data-duel-owner="{owner}"][data-duel-zone="4"][data-duel-sequence="0"] .duel-playing-card')
                        assert abs(monster.evaluate('(e)=>new DOMMatrix(getComputedStyle(e).transform).m12')) > .99
                        spell = page.locator(f'.arena-slot[data-duel-owner="{owner}"][data-duel-zone="8"][data-duel-sequence="0"] .duel-playing-card')
                        assert spell.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
                    expect(page.locator('.duel-chain-card')).to_have_count(1)
                    expect(page.get_by_role('button',name='Effekt: Testkarte',exact=True)).to_be_focused()
                    page.screenshot(path=str(ROOT / 'artifacts/duel-chain-desktop.png'))
                    page.get_by_role('button',name='Effekt: Testkarte',exact=True).click()
                    expect(page.locator('.duel-chain-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers') == [{'type':'answer','prompt':7,'selected':[0]}]
                    page.evaluate('window.__showChain()')
                    page.set_viewport_size({'width':390,'height':844})
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    box = page.locator('.duel-chain-overlay').bounding_box()
                    assert box and box['x'] >= 0 and box['y'] >= 0 and box['x']+box['width'] <= 390 and box['y']+box['height'] <= 844
                    page.screenshot(path=str(ROOT / 'artifacts/duel-chain-mobile.png'))
                    page.get_by_role('button',name='Nicht anketten',exact=True).click()
                    expect(page.locator('.duel-chain-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers[1]') == {'type':'answer','prompt':8,'selected':[1]}
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__showPhase()')
                    orb = page.locator('.arena-phase-orb')
                    expect(orb).to_be_enabled()
                    expect(orb).to_contain_text('Hauptphase 1')
                    zone = page.get_by_label('Gegnerische Extra-Monsterzone 2', exact=True).bounding_box()
                    dial = orb.bounding_box()
                    assert zone and dial and dial['x'] > zone['x'] + zone['width']
                    orb.click()
                    expect(page.get_by_role('group',name='Erlaubte Phasenwechsel')).to_be_visible()
                    page.screenshot(path=str(ROOT / 'artifacts/duel-phase-desktop.png'))
                    page.get_by_role('group',name='Erlaubte Phasenwechsel').get_by_role('button',name='Kampfphase',exact=True).click()
                    assert page.evaluate('window.__answers[2].selected') == [1]
                    expect(page.locator('.arena-phase-options')).to_have_count(0)
                    page.evaluate('window.__showPhase(0,16)')
                    expect(orb).to_contain_text('Kampfphase')
                    orb.click()
                    page.get_by_role('group',name='Erlaubte Phasenwechsel').get_by_role('button',name='Hauptphase 2',exact=True).click()
                    assert page.evaluate('window.__answers[3].selected') == [1]
                    page.evaluate('window.__showPhase(1,512)')
                    expect(orb).to_be_disabled()
                    expect(orb).to_contain_text('Endphase')
                    page.evaluate('window.__showPhase(0,4)')
                    page.set_viewport_size({'width':390,'height':844})
                    orb.click()
                    dial = orb.bounding_box()
                    assert dial and abs(dial['width'] - dial['height']) < 1
                    menu = page.locator('.arena-phase-options').bounding_box()
                    assert menu and menu['x'] >= 0 and menu['x'] + menu['width'] <= 390
                    page.screenshot(path=str(ROOT / 'artifacts/duel-phase-mobile.png'))
                    page.keyboard.press('Escape')
                    expect(page.locator('.arena-phase-options')).to_have_count(0)
                    expect(orb).to_be_focused()
                    orb.click()
                    page.get_by_role('group',name='Erlaubte Phasenwechsel').get_by_role('button',name='Endphase · Zug beenden',exact=True).click()
                    assert page.evaluate('window.__answers[4].selected') == [2]
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__battle()')
                    expect(page.locator('.attack-ready')).to_have_count(2)
                    assert orb.evaluate('(e)=>getComputedStyle(e).borderTopColor') == 'rgb(66, 143, 239)'
                    assert page.locator('.duel-worker-table > .duel-decisions').count() == 0
                    page.get_by_role('button',name='Monsterzone 1 Aktionen',exact=True).click()
                    page.locator('.arena-card-actions').get_by_role('button',name='Angreifen: Testkarte',exact=True).click()
                    expect(page.get_by_role('dialog',name='Angriff vorbereiten')).to_be_visible()
                    page.get_by_role('dialog',name='Angriff vorbereiten').get_by_role('button',name='Abbrechen',exact=True).click()
                    assert len(page.evaluate('window.__answers')) == 5
                    page.get_by_role('button',name='Monsterzone 2 Aktionen',exact=True).click()
                    page.get_by_role('button',name='Angriff starten',exact=True).click()
                    assert page.evaluate('window.__answers[5].selected') == [2]
                    page.evaluate('window.__targets()')
                    page.get_by_role('button',name='Monsterzone 1 auswählen',exact=True).click()
                    expect(page.get_by_role('button',name='Angriff bestätigen',exact=True)).to_be_enabled()
                    page.screenshot(path=str(ROOT / 'artifacts/duel-field-attack.png'))
                    page.get_by_role('button',name='Angriff bestätigen',exact=True).click()
                    assert page.evaluate('window.__answers[6].selected') == [0]
                    for seat in (0,1):
                        page.evaluate('(seat)=>window.__effect(seat)',seat)
                        expect(page.get_by_role('status',name='Aktivierter Karteneffekt')).to_be_visible()
                        expect(page.locator('.duel-effect-reveal')).to_contain_text('Dein Effekt' if seat==0 else 'Gegner aktiviert')
                        if seat==1:
                            assert orb.evaluate('(e)=>getComputedStyle(e).borderTopColor') == 'rgb(225, 72, 105)'
                            page.screenshot(path=str(ROOT / 'artifacts/duel-field-effect.png'))
                        expect(page.locator('.duel-inspector-effect')).to_contain_text('Ein bestätigter Testeffekt',timeout=5000)
                        expect(page.locator('.duel-card-description')).to_have_text('Deutscher Kartentext')
                        page.wait_for_timeout(2200)
                    page.evaluate('window.__log()')
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.get_by_text('Bestätigtes Duellprotokoll',exact=True).click()
                    expect(page.locator('.duel-event-log')).to_contain_text('Angreifer: Testkarte')
                    expect(page.locator('.duel-event-log')).to_contain_text('Ziel: Verdeckte Karte')
                    expect(page.locator('.duel-event-log')).to_contain_text('Effekt aufgelöst · 1 · Effektkarte: Testkarte')
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.evaluate('window.__feedback()')
                    for zone in (4,8):
                        expect(page.locator(f'.arena-own .arena-slot[data-duel-zone="{zone}"].effect-available')).to_have_count(1)
                    for zone in (16,32,64,1):
                        pile=page.locator(f'.arena-own .arena-pile[data-duel-zone="{zone}"]')
                        expect(pile).to_have_class(__import__('re').compile('effect-available'))
                        assert pile.evaluate('(e)=>getComputedStyle(e).animationName')=='duel-effect-pulse'
                    expect(page.locator('.arena-own .arena-hand .duel-playing-card.effect-available')).to_have_count(1)
                    page.screenshot(path=str(ROOT/'artifacts/duel-effects-gold.png'))
                    page.locator('.arena-own .arena-pile[data-duel-zone="16"] summary').click()
                    page.locator('.arena-own .arena-pile[data-duel-zone="16"] .duel-playing-card').click()
                    page.get_by_role('button',name='Aktivieren: Testkarte 16',exact=True).click()
                    assert page.evaluate('window.__answers.at(-1).selected') == [3]
                    expect(page.locator('.effect-available')).to_have_count(0)
                    page.evaluate('window.__feedback(true)')
                    expect(page.locator('.arena-own .arena-pile[data-duel-zone="32"].effect-available')).to_have_count(1)
                    # Finish the synthetic decision so phase-only frames cannot glow.
                    page.evaluate('window.__socket.send(JSON.stringify({type:"answer",selected:[0]}))')
                    for kind,phase,title in [('phase_request',512,'Beendet Zug'),('phase',512,'Endphase'),('turn_end',None,'Zug beendet'),('turn',None,'Dein Zug'),('phase',1,'Ziehphase'),('phase',2,'Standby-Phase'),('phase',4,'Hauptphase 1')]:
                        page.evaluate('([kind,phase,player])=>window.__announce(kind,phase,player)',[kind,phase,0 if kind in ('turn','phase') and phase!=512 else 1])
                        banner=page.get_by_role('status',name='Phasenwechsel',exact=True)
                        expect(banner).to_contain_text(title,timeout=10000)
                        assert banner.evaluate('(e)=>getComputedStyle(e).pointerEvents')=='none'
                        if kind=='phase_request':
                            expect(banner).to_contain_text('Reaktionen sind noch möglich')
                            assert page.locator('.arena-phase-announcement.is-opponent-turn').count()==1
                        if phase==2:
                            page.wait_for_timeout(300)
                            page.screenshot(path=str(ROOT/'artifacts/duel-phase-announcement.png'))
                        expect(banner).to_have_count(0,timeout=5000)
                    page.get_by_label('Duellmenü',exact=True).click()
                    expect(page.get_by_role('button',name='Ton an',exact=True)).to_have_attribute('aria-pressed','true')
                    page.get_by_role('button',name='Ton an',exact=True).click()
                    assert page.evaluate('localStorage.getItem("duel-sound")')=='off'
                    assert page.evaluate('window.__soundStarts') > 0
                    before=page.evaluate('window.__soundStarts')
                    page.evaluate('window.__announce("phase",256,0)')
                    expect(page.get_by_role('status',name='Phasenwechsel',exact=True)).to_contain_text('Hauptphase 2')
                    assert page.evaluate('window.__soundStarts')==before
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.set_viewport_size({'width':390,'height':844})
                    page.emulate_media(reduced_motion='reduce')
                    page.evaluate('window.__feedback()')
                    assert page.locator('.arena-own .arena-pile[data-duel-zone="32"]').evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                    page.evaluate('window.__announce("phase",2,0)')
                    expect(page.get_by_role('status',name='Phasenwechsel',exact=True)).to_contain_text('Standby-Phase',timeout=5000)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(ROOT/'artifacts/duel-feedback-mobile.png'),full_page=True)
                    assert not errors, errors
                    browser.close()
                print(json.dumps({'browser':'passed','checks':['card orientation','chain image and keyboard focus','original answer indexes preserved','chain overlay on mobile','phase dial right of extra zone 2','battle/main 2/end transitions','opponent turn disabled','circular mobile dial and menu fit','Escape restores focus','sapphire own turn and ruby opponent turn','legal attacker highlight','cancel before attack sends no answer','field target and adjacent confirmation','effect reveal and viewer for both seats','named cards and chain resolution in duel log','gold effect glow on all locations','grave activation keeps original answer index','large ordered phase banners and pending turn end','real sound buffer playback and persistent mute','mobile feedback and reduced motion'],'console_errors':errors}))
            finally:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    run()
