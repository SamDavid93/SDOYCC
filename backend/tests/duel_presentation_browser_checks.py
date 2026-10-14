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
import { bossSummon } from '../src/pages/DuelSummonCutin'
import { bossSoundFor, DuelSoundPlayer } from '../src/pages/duelSounds'
import '../src/styles.css'
import '../src/pages/decks.css'
import '../src/master-duel-theme.css'
import '../src/master-duel-content.css'
import '../src/master-duel-game.css'
sessionStorage.setItem('hub-session', 'synthetic-presentation-token')
const card = {code:1,name:'Testkarte',description:'Deutscher Kartentext',image_url:'/test-card.svg',atk:1000,defense:1000}
const side = {lp:8000,deck:30,hand:[],grave:[],field:[]}
const frame = {id:'presentation',state:'running',seat:0,clock:{remaining:[360,360],active:null,side_remaining:null,readiness_required:true,waiting_for:0,ready_timeout:30},board:{revision:1,seat:0,turn:0,turn_number:1,phase:4,ended:false,events:[],
boards:[{...side,field:[{zone:4,sequence:0,position:8,card},{zone:8,sequence:0,position:8,card},{zone:8,sequence:1,position:8,card}]},
{...side,field:[{zone:4,sequence:0,position:8,card:null},{zone:8,sequence:0,position:8,card:null}]}],
prompt:{id:7,title:'Auf die Kette reagieren',choices:[{label:'Effekt: Testkarte',card},{label:'Nicht anketten',card:null}]}}}
window.__answers=[]
window.__readyFrames=[]
window.__bossSounds=[]
const originalBossSound=DuelSoundPlayer.prototype.playBossSummon
DuelSoundPlayer.prototype.playBossSummon=function(event,seconds){window.__bossSounds.push(bossSoundFor(event));return originalBossSound.call(this,event,seconds)}
window.__bossEligible=(event,seat)=>bossSummon(event,seat)
class Socket {
static OPEN=1;readyState=1
constructor(){window.__socket=this;setTimeout(()=>this.onopen?.(),0)}
send(text){const message=JSON.parse(text);if(message.type==='decision_ready')window.__readyFrames.push(message);if(message.type==='answer'){const stale=JSON.stringify(frame);if(window.__delayReply){window.__delayReply=false;queueMicrotask(()=>this.onmessage?.({data:JSON.stringify({type:'state',result:JSON.parse(stale)})}));window.__replyLater=true}window.__answers.push(message);const progress=frame.board.prompt?.selection_progress;if(progress&&!message.cancel){frame.board.prompt={...frame.board.prompt,id:frame.board.prompt.id+1,selection_progress:{...progress,selected:progress.selected+1,can_finish:progress.selected+1>=progress.minimum},cancel:progress.selected+1>=progress.minimum}}else frame.board.prompt=null;frame.board.revision++}if(message.type!=='ping'){const emit=()=>this.onmessage?.({data:JSON.stringify({type:'state',result:frame,ack:message.type==='answer'})});if(window.__replyLater){window.__replyLater=false;setTimeout(emit,350)}else queueMicrotask(emit)}}
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
window.__pick=(minimum,maximum=minimum,ordered=false,zone=1)=>{frame.board.prompt={id:500+frame.board.revision,title:'Karten auswählen',hint:'Wähle Karten, die deiner Hand hinzugefügt werden.',select:true,minimum,maximum,ordered,choices:[0,1,2].map(i=>({label:'Auswahl '+(i+1),card,location:{owner:0,zone,sequence:i}}))};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__pickStep=()=>{window.__pick(2);frame.board.prompt={...frame.board.prompt,title:'Auswahl ändern',select:false,cancel:false,selection_progress:{minimum:2,maximum:2,selected:0,can_finish:false}};window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__scene=(event)=>{frame.board.seat=frame.seat=0;frame.board.turn=0;frame.board.phase=4;frame.board.prompt=null;
const visible={...card,image_url:'/scene-card.jpg',atk:3000,defense:2500};
frame.board.boards=[{...side,lp:8000,hand:Array(6).fill(visible),grave:[visible],extra:[null,null],removed:[],field:[{zone:4,sequence:0,position:1,card:visible},{zone:4,sequence:2,position:4,card:visible},{zone:8,sequence:1,position:8,card:visible}]},{...side,lp:event?.kind==='lp'?7000:8000,hand:Array(4).fill(null),grave:[],extra:[null],removed:[],field:[{zone:4,sequence:0,position:8,card:null},{zone:4,sequence:2,position:1,card:visible},{zone:8,sequence:1,position:8,card:null}]}];
if(event)frame.board.events.push({...event,id:Math.max(0,...frame.board.events.map(e=>e.id))+1});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__extra=(owners,seat,offer=false)=>{frame.board.seat=frame.seat=seat;frame.board.prompt=offer?{id:900+frame.board.revision,kind:'zones',minimum:1,maximum:1,choices:[{label:'Right',location:{owner:seat,zone:4,sequence:6}},{label:'Left',location:{owner:seat,zone:4,sequence:5}}]}:null;frame.board.boards.forEach(s=>s.field=s.field.filter(e=>e.zone!==4||e.sequence<5));owners.forEach((owner,i)=>{if(owner!==null)frame.board.boards[owner].field.push({zone:4,sequence:owner===seat?5+i:6-i,position:1,card})});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__pileFlow=()=>{window.__scene();const extra={...card,name:'Synchro-Test',type:0x2001};frame.board.boards[0].extra=[{...card,name:'Nicht beschwoerbar'},extra,{...card,name:'Fusion-Test'}];frame.board.prompt={id:1100+frame.board.revision,title:'Aktion wählen',choices:[{label:'Zug beenden',card:null},{label:'Spezialbeschwören: Synchro-Test',card:extra,action:'special_summon',location:{owner:0,zone:64,sequence:1}},{label:'Aktivieren: Synchro-Test',card:extra,action:'activate',location:{owner:0,zone:64,sequence:1}},{label:'Spezialbeschwören: Fusion-Test',card:{...card,name:'Fusion-Test'},action:'special_summon',location:{owner:0,zone:64,sequence:2}}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__pileStep=(stage)=>{frame.board.prompt={id:1200+frame.board.revision,title:stage==='materials'?'Materialien wählen':stage==='zones'?'Zone wählen':'Aktion wählen',...(stage==='materials'?{select:true,minimum:2,maximum:2}:stage==='zones'?{kind:'zones',placement:true}:{}),choices:stage==='materials'?[0,1].map(sequence=>({label:'Material '+sequence,card,location:{owner:0,zone:4,sequence}})):stage==='zones'?[6,2].map(sequence=>({label:'Zone '+sequence,card:null,location:{owner:0,zone:4,sequence}})):[{label:'Zug beenden',card:null}]};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__clock=(active=null,seat=0)=>{frame.seat=seat;frame.clock={remaining:[180,300],active,side_remaining:null,readiness_required:true,waiting_for:null,ready_timeout:null};frame.board.prompt=null;frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__currentDecision=()=>({prompt:frame.board.prompt?.id,revision:frame.board.revision})
window.__clockTick=()=>window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})
window.__nextGame=()=>{frame.seat=0;frame.match={version:1,game:2,phase:'playing',score:[1,0],ready:[false,false],chooser:null,next_starter:null};frame.board.revision=1;frame.board.seat=0;frame.board.turn=0;frame.board.events=[{id:1,kind:'phase',phase:4,player:0,number:1}];frame.board.boards.forEach(s=>s.lp=8000);frame.clock={remaining:[360,360],active:null,side_remaining:null,readiness_required:true,waiting_for:0,ready_timeout:30};frame.board.prompt={id:1,title:'Aktion w\u00e4hlen',choices:[{label:'Zug beenden',card:null}]};window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__finish=()=>{const id=Math.max(0,...frame.board.events.map(e=>e.id));frame.state='finished';frame.winner_seat=1;frame.board.ended=true;frame.board.prompt=null;frame.board.boards[0].lp=0;frame.board.events.push({id:id+1,kind:'attack',attacker:{owner:1,zone:4,sequence:2},direct:true},{id:id+2,kind:'lp',player:0,value:0,delta:-8000},{id:id+3,kind:'win',winner:1});frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__actions=()=>{window.__scene();frame.board.prompt={id:1500+frame.board.revision,title:'Aktion w\u00e4hlen',choices:['activate','set_spell','summon','special_summon'].map(action=>({label:action,action,card,location:{owner:0,zone:2,sequence:0}}))};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__badImage=()=>{window.__scene();frame.board.boards[1].field[1].card={...card,name:'Visible opponent monster',image_url:'/missing-card-image.png'};frame.board.revision++;window.__socket.onmessage({data:JSON.stringify({type:'state',result:frame})})}
window.__boss=(overrides={})=>window.__scene({kind:'summon',method:'synchro',player:1,location:{owner:1,zone:4,sequence:2,position:1},card:{...card,name:'Blue-Eyes White Dragon',image_url:'/scene-card.jpg',level:8,type:0x2001,attribute:16,atk:3000,defense:2500},...overrides})
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
                    key_warnings = []
                    page.on('console', lambda message: key_warnings.append(message.text) if 'same key' in message.text else None)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/test-card.svg', lambda route: route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="80" height="120"><rect width="80" height="120" fill="teal"/></svg>'))
                    artwork=ROOT/'cache/cards-original/89631139.img'
                    page.route('**/scene-card.jpg', lambda route: route.fulfill(content_type='image/jpeg', body=artwork.read_bytes()) if artwork.exists() else route.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="80" height="120"><rect width="80" height="120" fill="teal"/></svg>'))
                    page.goto(url + '/' + folder.name + '/index.html')
                    expect(page.locator('.duel-chain-overlay')).to_be_visible()
                    for owner in (0,1):
                        monster = page.locator(f'.arena-slot[data-duel-owner="{owner}"][data-duel-zone="4"][data-duel-sequence="0"] .duel-playing-card')
                        assert abs(monster.evaluate('(e)=>new DOMMatrix(getComputedStyle(e).transform).m12')) > .99
                        if owner==1:
                            assert monster.evaluate('(e)=>getComputedStyle(e).opacity')=='1'
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
                        if seat==0:
                            expect(page.get_by_role('status',name='Aktivierter Karteneffekt')).to_have_count(0)
                            expect(page.locator('.duel-inspector-effect')).to_contain_text('Ein bestätigter Testeffekt',timeout=500)
                        if seat==1:
                            expect(page.get_by_role('status',name='Aktivierter Karteneffekt')).to_be_visible()
                            expect(page.locator('.duel-effect-reveal')).to_contain_text('Gegner aktiviert')
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
                    page.locator('.arena-own .arena-pile[data-duel-zone="16"]').get_by_role('button',name='Effekt aktivieren',exact=False).click()
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
                    # Event animations use exact locations and never expose a hidden card face.
                    expect(page.locator('.arena-phase-announcement')).to_have_count(0,timeout=5000)
                    page.emulate_media(reduced_motion='no-preference')
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__scene()')
                    page.evaluate('window.scrollTo(0,0)')
                    page.screenshot(path=str(ROOT/'artifacts/duel-premium-arena.png'),full_page=True)
                    for method in ('normal','fusion','synchro','xyz','link','ritual','pendulum','covered'):
                        page.evaluate('(method)=>window.__scene({kind:"summon",method,player:0,location:{owner:0,zone:4,sequence:0}})',method)
                        scene=page.locator(f'.duel-scene-motion[data-summon-method="{method}"]')
                        expect(scene.locator('.duel-summon-portal')).to_have_count(1)
                        assert scene.evaluate('(e)=>getComputedStyle(e).pointerEvents')=='none'
                        assert scene.locator('image').count()==0
                        if method=='synchro':
                            page.wait_for_timeout(300)
                            page.screenshot(path=str(ROOT/'artifacts/duel-premium-summon.png'))
                        expect(scene).to_have_count(0,timeout=5000)
                    page.evaluate('window.__scene({kind:"attack",attacker:{owner:0,zone:4,sequence:0},defender:{owner:1,zone:4,sequence:0}})')
                    expect(page.locator('.duel-attack-ray')).to_have_count(1)
                    page.wait_for_timeout(350)
                    page.screenshot(path=str(ROOT/'artifacts/duel-premium-attack.png'))
                    expect(page.locator('.duel-attack-ray')).to_have_count(0,timeout=5000)
                    page.evaluate('window.__scene({kind:"attack",attacker:{owner:0,zone:4,sequence:0},direct:true})')
                    expect(page.locator('.duel-attack-ray')).to_have_count(1)
                    expect(page.locator('.duel-attack-ray')).to_have_count(0,timeout=5000)
                    page.evaluate('window.__scene({kind:"lp",player:1,value:7000,delta:-1000})')
                    expect(page.locator('.duel-lp-delta')).to_contain_text('1.000')
                    expect(page.locator('[data-duel-hud="1"] .duel-life')).to_contain_text('7.000')
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(ROOT/'artifacts/duel-premium-damage.png'))
                    expect(page.locator('.duel-lp-delta')).to_have_count(0,timeout=5000)
                    page.evaluate('window.__scene({kind:"draw",player:1,count:1})')
                    moving=page.locator('.duel-travel-card image')
                    expect(moving).to_have_count(1)
                    assert 'card-back' in moving.get_attribute('href')
                    expect(moving).to_have_count(0,timeout=5000)
                    # Selecting animation reduction also suppresses SVG travel without OS settings.
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.get_by_label('Animationen',exact=True).select_option('reduced')
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.evaluate('window.__scene({kind:"draw",player:1,count:1})')
                    expect(page.locator('.duel-scene-motion[data-event-kind="draw"]')).to_have_count(1)
                    assert page.locator('.duel-travel-card').count()==0
                    page.evaluate('window.__scene({kind:"summon",method:"link",player:0,location:{owner:0,zone:4,sequence:0}})')
                    portal=page.locator('.duel-summon-portal')
                    expect(portal).to_have_count(1)
                    assert portal.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                    expect(portal).to_have_count(0,timeout=5000)
                    for width,height in ((1280,720),(1920,1080),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        page.evaluate('window.__scene()')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        arena=page.locator('.duel-arena').bounding_box()
                        assert arena and (width<=760 or arena['y']+arena['height']<=height),arena
                        page.screenshot(path=str(ROOT/f'artifacts/duel-premium-{width}.png'),full_page=True)
                        if width>760:
                            page.evaluate('document.documentElement.style.setProperty("--site-footer-height","60px")')
                            arena=page.locator('.duel-arena').bounding_box()
                            assert arena and arena['y']+arena['height'] <= height-60,arena
                            page.evaluate('document.documentElement.style.removeProperty("--site-footer-height")')
                    page.set_viewport_size({'width':1440,'height':1000})
                    for winner,title in ((0,'Sieg'),(1,'Niederlage'),(None,'Unentschieden')):
                        page.evaluate('(winner)=>window.__scene({kind:"win",winner})',winner)
                        expect(page.get_by_role('status',name='Duellergebnis')).to_contain_text(title)
                        expect(page.get_by_role('status',name='Duellergebnis')).to_have_count(0,timeout=5000)
                    page.evaluate('window.__scene({kind:"chain_step",step:75,number:1})')
                    expect(page.get_by_role('status',name='Negierter Effekt')).to_contain_text('Aktivierung negiert')
                    before=len(page.evaluate('window.__answers'))
                    page.evaluate('window.__pick(1)')
                    progress=page.get_by_role('status',name='Auswahlfortschritt')
                    expect(progress).to_contain_text('Wähle genau 1 Karte')
                    page.evaluate('window.__delayReply=true')
                    page.get_by_role('button',name='Auswahl 2',exact=True).dblclick()
                    expect(page.get_by_role('button',name='Auswahl 2',exact=True)).to_be_disabled()
                    page.wait_for_timeout(80)
                    expect(page.get_by_role('button',name='Auswahl 2',exact=True)).to_be_disabled()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[1]
                    assert len(page.evaluate('window.__answers'))==before+1
                    page.evaluate('window.__pick(2)')
                    page.get_by_role('button',name='Auswahl 1',exact=True).dblclick()
                    expect(progress).to_contain_text('Noch 1 Karte erforderlich')
                    assert len(page.evaluate('window.__answers'))==before+1
                    page.get_by_role('button',name='Auswahl 3',exact=True).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[0,2]
                    page.evaluate('window.__pick(2)')
                    page.get_by_role('button',name='Auswahl 1',exact=True).click()
                    page.get_by_role('button',name='Auswahl 2',exact=True).click()
                    total=len(page.evaluate('window.__answers'))
                    page.get_by_role('button',name='Auswahl 3',exact=True).dblclick()
                    expect(progress).to_contain_text('2 / 2 ausgewählt')
                    assert len(page.evaluate('window.__answers'))==total
                    page.get_by_role('button',name='Auswahl 1',exact=True).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[0,1]
                    page.evaluate('window.__pick(3,3,true)')
                    for name in ('Auswahl 3','Auswahl 1','Auswahl 2'):
                        page.get_by_role('button',name=name,exact=True).click()
                    page.get_by_role('button',name='1. Auswahl 3',exact=True).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[2,0,1]
                    page.evaluate('window.__pickStep()')
                    total=len(page.evaluate('window.__answers'))
                    page.get_by_role('button',name='Auswahl 1',exact=True).dblclick()
                    expect(progress).to_contain_text('1 / 2 ausgewählt')
                    assert len(page.evaluate('window.__answers'))==total+1
                    page.get_by_role('button',name='Auswahl 2',exact=True).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    answers=page.evaluate('window.__answers.slice(-2)')
                    assert answers[0]['selected']==[1]
                    assert answers[1]['selected']==[] and answers[1]['cancel'] is True
                    assert answers[1]['prompt']>answers[0]['prompt']
                    page.evaluate('window.__scene();window.__pick(2,2,false,2)')
                    hand_popup=page.get_by_role('dialog',name='Handkarten für einen Effekt auswählen')
                    expect(hand_popup).to_be_visible()
                    expect(hand_popup.get_by_role('heading')).to_be_focused()
                    expect(hand_popup.locator('.duel-choice-list>button')).to_have_count(3)
                    expect(hand_popup.locator('.duel-choice-origin').first).to_have_text('Hand')
                    hand_popup.get_by_role('button',name='Auswahl 1',exact=True).click()
                    expect(hand_popup.get_by_role('button',name='Auswahl 1',exact=True)).to_have_attribute('aria-pressed','true')
                    hand_popup.get_by_role('button',name='Auswahl 1',exact=True).click()
                    expect(progress).to_contain_text('Wähle genau 2 Karten')
                    own=page.locator('.arena-own .arena-hand-card>.duel-playing-card')
                    own.nth(0).dblclick()
                    expect(progress).to_contain_text('Noch 1 Karte erforderlich')
                    own.nth(1).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[0,1]
                    page.evaluate('window.__scene()')
                    assert own.first.bounding_box()['width']>=100
                    page.set_viewport_size({'width':390,'height':844})
                    assert own.first.bounding_box()['width']>=66
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.evaluate('window.__pick(2)')
                    expect(progress).to_contain_text('Wähle genau 2 Karten')
                    page.screenshot(path=str(ROOT/'artifacts/duel-selection-mobile.png'),full_page=True)
                    page.get_by_role('button',name='Auswahl 1',exact=True).click()
                    page.get_by_role('button',name='Auswahl 2',exact=True).dblclick()
                    expect(page.locator('.arena-decision-overlay')).to_have_count(0)
                    page.evaluate('window.__scene();window.__pick(1,1,false,2)')
                    expect(hand_popup).to_be_visible()
                    page.screenshot(path=str(ROOT/'artifacts/duel-hand-effect-popup-mobile.png'),full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    hand_popup.get_by_role('button',name='Auswahl 1',exact=True).click()
                    confirm=hand_popup.get_by_role('button',name='Auswahl bestätigen',exact=True)
                    expect(confirm).to_be_enabled()
                    popup_bounds=hand_popup.bounding_box();confirm_bounds=confirm.bounding_box()
                    assert confirm_bounds['y']+confirm_bounds['height']<=popup_bounds['y']+popup_bounds['height']
                    hand_popup.get_by_role('button',name='Auswahl 2',exact=True).dblclick()
                    expect(hand_popup).to_have_count(0)
                    assert page.evaluate('window.__answers.at(-1).selected')==[1]
                    # Physical shared zones keep their DOM identity when controllers change.
                    page.evaluate('window.__physicalExtraNodes=Array.from(document.querySelectorAll(".arena-extra-row > .arena-slot"))')
                    for viewport in ({'width':1440,'height':1000}, {'width':390,'height':844}):
                        page.set_viewport_size(viewport)
                        for seat in (0,1):
                            for owners in ([None,None],[seat,None],[None,seat],[1-seat,seat],[seat,1-seat],[None,None],[1-seat,None],[None,1-seat],[None,None]):
                                for offer in (False,True):
                                    page.evaluate('(args)=>window.__extra(...args)', [owners,seat,offer])
                                    expect(page.locator('.arena-extra-row > .arena-slot')).to_have_count(2)
                                    expect(page.locator('.arena-slot')).to_have_count(24)
                                    assert page.evaluate('window.__physicalExtraNodes.every((node,i)=>node===document.querySelectorAll(".arena-extra-row > .arena-slot")[i])')
                                    for index, owner in enumerate(owners):
                                        if owner is not None:
                                            zone=page.locator('.arena-extra-row > .arena-slot').nth(index)
                                            expect(zone).to_have_attribute('data-duel-owner',str(owner))
                                            expect(zone.locator('.duel-playing-card')).to_have_count(1)
                            page.evaluate('(seat)=>window.__extra([null,null],seat,true)',seat)
                            page.locator('.arena-extra-row > .arena-slot').nth(0).locator('.arena-zone-choice').click()
                            assert page.evaluate('window.__answers.at(-1).selected') == [1]
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__pileFlow()')
                    extra=page.locator('.arena-own .arena-pile[data-duel-zone="64"]')
                    extra.locator('summary').click()
                    expect(extra.get_by_role('heading',name='Mögliche Spezialbeschwörungen')).to_be_visible()
                    expect(extra.locator('.arena-pile-options>button')).to_have_count(2)
                    expect(extra.get_by_role('button',name='Effekt aktivieren',exact=False)).to_contain_text('(1)')
                    expect(extra.locator('.arena-pile-options')).not_to_contain_text('Nicht beschwoerbar')
                    extra.get_by_role('button',name='Extra-Deck ansehen',exact=False).click()
                    expect(extra.locator('.arena-pile-cards .duel-playing-card')).to_have_count(3)
                    extra.get_by_role('button',name='Mögliche Aktionen',exact=False).click()
                    extra.get_by_role('button',name='Spezialbeschwören: Synchro-Test',exact=True).click()
                    assert page.evaluate('window.__answers.at(-1).selected') == [1]
                    page.evaluate('window.__pileStep("materials")')
                    guide=page.get_by_role('status',name='Deine laufende Kartenaktion')
                    expect(guide).to_contain_text('Synchrobeschwörung')
                    expect(guide).to_contain_text('Synchro-Test')
                    expect(guide).to_contain_text('Materialien wählen')
                    page.evaluate('window.__pileStep("zones")')
                    expect(guide).to_contain_text('Zielfeld wählen')
                    guide_bounds=guide.bounding_box()
                    selection_bounds=page.locator('.arena-field-selection-guide').bounding_box()
                    assert guide_bounds['y']+guide_bounds['height']<=selection_bounds['y']
                    page.screenshot(path=str(ROOT/'artifacts/duel-summon-guidance.png'))
                    page.locator('.arena-slot[data-duel-owner="0"][data-duel-zone="4"][data-duel-sequence="6"] .arena-zone-choice').click()
                    assert page.evaluate('window.__answers.at(-1).selected') == [0]
                    page.evaluate('window.__pileStep("idle")')
                    expect(guide).to_have_count(0)
                    page.evaluate('window.__feedback()')
                    removed=page.locator('.arena-own .arena-pile[data-duel-zone="32"]')
                    removed.locator('summary').click()
                    removed.get_by_role('button',name='Effekt aktivieren',exact=False).click()
                    expect(removed.locator('.arena-pile-options>button')).to_have_count(1)
                    page.screenshot(path=str(ROOT/'artifacts/duel-pile-effects.png'))
                    removed.get_by_role('button',name='Aktivieren: Testkarte 32',exact=True).click()
                    assert page.evaluate('window.__answers.at(-1).selected') == [4]
                    for width,height in ((1440,1000),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        page.evaluate('window.__pileFlow()')
                        extra.locator('summary').click()
                        bounds=extra.locator('.arena-pile-browser').bounding_box()
                        assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=width+1,bounds
                        page.keyboard.press('Escape')
                        expect(extra).not_to_have_attribute('open','')
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.get_by_label('Animationen',exact=True).select_option('full')
                    page.get_by_label('Boss-Cut-ins',exact=True).check()
                    sound_button=page.get_by_role('button',name='Ton aus',exact=True)
                    if sound_button.count():sound_button.click()
                    page.get_by_label('Duellmenü',exact=True).click()
                    assert not page.evaluate('window.__bossEligible({kind:"summon",player:0,card:{level:12,atk:4000}},0)')
                    assert not page.evaluate('window.__bossEligible({kind:"summon",player:1,method:"covered",card:{level:12,atk:4000}},0)')
                    assert not page.evaluate('window.__bossEligible({kind:"summon",player:1,card:{level:4,atk:1900}},0)')
                    assert page.evaluate('window.__bossEligible({kind:"summon",player:1,card:{level:3,type:0x4000000,atk:2000}},0)')
                    page.evaluate('window.__boss()')
                    cutin=page.get_by_role('status',name='Gegnerisches Bossmonster beschworen')
                    expect(cutin).to_be_visible()
                    expect(cutin).to_contain_text('Blue-Eyes White Dragon')
                    expect(cutin).to_contain_text('ATK 3000')
                    assert cutin.evaluate('(e)=>getComputedStyle(e).pointerEvents')=='none'
                    page.wait_for_timeout(350)
                    page.screenshot(path=str(ROOT/'artifacts/duel-boss-cutin-desktop.png'))
                    assert page.evaluate('window.__bossSounds.at(-1)')=='boss-light'
                    page.evaluate('window.__showChain()')
                    expect(cutin).to_have_class(__import__('re').compile('is-compact'))
                    expect(page.locator('.duel-chain-overlay')).to_be_visible()
                    page.get_by_role('button',name='Nicht anketten',exact=True).click()
                    assert page.evaluate('window.__answers.at(-1).selected')==[1]
                    expect(cutin).to_have_count(0,timeout=3000)
                    page.evaluate('window.__boss({player:0})')
                    page.wait_for_timeout(500)
                    expect(cutin).to_have_count(0)
                    page.wait_for_timeout(300)
                    page.set_viewport_size({'width':390,'height':844})
                    page.evaluate('window.__boss({method:"xyz"})')
                    expect(cutin).to_be_visible()
                    page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(ROOT/'artifacts/duel-boss-cutin-mobile.png'),full_page=True)
                    expect(cutin).to_have_count(0,timeout=3000)
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.get_by_label('Animationen',exact=True).select_option('reduced')
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.evaluate('window.__boss()')
                    expect(cutin).to_have_class(__import__('re').compile('cutin-reduced'))
                    assert cutin.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                    expect(cutin).to_have_count(0,timeout=2000)
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.get_by_label('Boss-Cut-ins',exact=True).uncheck()
                    page.get_by_label('Duellmenü',exact=True).click()
                    page.evaluate('window.__boss()')
                    page.wait_for_timeout(400)
                    expect(cutin).to_have_count(0)
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__actions()')
                    page.locator('.arena-own .arena-hand-card').first.locator('.duel-playing-card').click()
                    actions=page.locator('.arena-own .arena-hand-card').first.locator('.arena-hand-actions')
                    expect(actions.locator('[data-duel-action="activate"]')).to_be_visible()
                    styles=actions.locator('[data-duel-action]').evaluate_all('(buttons)=>buttons.map(b=>({background:getComputedStyle(b).backgroundColor,border:getComputedStyle(b).borderStyle,icon:!!b.querySelector("svg"),detail:!!b.querySelector("small")}))')
                    assert len({item['background'] for item in styles})==4,styles
                    assert styles[-1]['border']=='dashed' and all(item['icon'] and item['detail'] for item in styles),styles
                    page.screenshot(path=str(ROOT/'artifacts/duel-distinct-actions.png'))
                    page.route('**/missing-card-image.png',lambda route:route.abort())
                    page.evaluate('window.__badImage()')
                    monster=page.locator('.arena-slot[data-duel-owner="1"][data-duel-zone="4"][data-duel-sequence="2"] .duel-playing-card')
                    expect(monster.locator('strong')).to_be_visible()
                    expect(monster.locator('strong')).to_have_text('Visible opponent monster')
                    expect(monster.locator('img')).to_be_hidden()
                    expect(page.locator('.arena-slot .duel-playing-card')).to_have_count(6)
                    page.get_by_label('Duellmen\u00fc',exact=True).click()
                    page.get_by_label('Animationen',exact=True).select_option('full')
                    page.get_by_role('button',name='Animationen \u00fcberspringen',exact=True).click(force=True) if page.get_by_role('button',name='Animationen \u00fcberspringen',exact=True).is_enabled() else None
                    page.get_by_label('Duellmen\u00fc',exact=True).click()
                    page.wait_for_timeout(100)
                    page.evaluate('window.__clock(null,1)')
                    timer=page.locator('.arena-timer-control')
                    expect(timer.locator('.arena-timer-value')).to_have_text('05:00')
                    expect(timer.locator('.arena-timer-opponent b')).to_have_text('03:00')
                    expect(timer).to_have_attribute('data-clock-active','paused')
                    page.wait_for_timeout(1100)
                    expect(timer.locator('.arena-timer-value')).to_have_text('05:00')
                    page.evaluate('window.__clock(1,1)')
                    expect(timer).to_have_attribute('data-clock-active','own')
                    expect(timer.locator('.arena-timer-value')).to_have_text('04:59',timeout=2500)
                    page.evaluate('window.__clock(0,1)')
                    expect(timer).to_have_attribute('data-clock-active','opponent')
                    expect(timer.locator('.arena-timer-value')).to_have_text('05:00')
                    expect(timer.locator('.arena-timer-opponent b')).to_have_text('02:59',timeout=2500)
                    for width,height in ((1920,1080),(1280,720),(390,844)):
                        page.set_viewport_size({'width':width,'height':height})
                        dial=timer.locator('.arena-timer-dial').bounding_box()
                        zones=page.locator('.arena-extra-row>.arena-slot')
                        phase=page.locator('.arena-phase-orb').bounding_box()
                        assert dial and phase and dial['x']>=0 and dial['x']+dial['width']<zones.first.bounding_box()['x'],(dial,phase)
                        assert abs(dial['y']+dial['height']/2-(phase['y']+phase['height']/2))<20,(dial,phase)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        page.screenshot(path=str(ROOT/f'artifacts/duel-timer-{width}.png'))
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.evaluate('window.__actions()')
                    page.wait_for_timeout(150)
                    ready_count=page.evaluate('window.__readyFrames.length')
                    assert ready_count>0
                    for _ in range(3):page.evaluate('window.__clockTick()')
                    page.wait_for_timeout(150)
                    assert page.evaluate('window.__readyFrames.length')==ready_count
                    assert page.evaluate('({prompt:window.__readyFrames.at(-1).prompt,revision:window.__readyFrames.at(-1).revision})')==page.evaluate('window.__currentDecision()')
                    page.evaluate('window.__clock(null,0)')
                    page.evaluate('window.__nextGame()')
                    expect(timer.locator('.arena-timer-value')).to_have_text('06:00')
                    expect(page.locator('.duel-turn-line')).to_contain_text('Spiel 2')
                    page.wait_for_timeout(150)
                    assert page.evaluate('({prompt:window.__readyFrames.at(-1).prompt,revision:window.__readyFrames.at(-1).revision})')=={'prompt':1,'revision':1}
                    page.evaluate('window.__finish()')
                    expect(page.locator('.duel-event-stage.event-attack')).to_be_visible()
                    expect(page.locator('[data-duel-hud="0"] .duel-life')).to_contain_text('8.000')
                    expect(page.locator('.duel-worker-result')).to_have_count(0)
                    expect(page.locator('.duel-worker-table')).to_have_class(__import__('re').compile('is-playing'))
                    expect(page.locator('.duel-event-stage.event-lp')).to_be_visible()
                    expect(page.locator('[data-duel-hud="0"] .duel-life')).to_contain_text('0 LP')
                    expect(page.locator('.duel-worker-result')).to_have_count(0)
                    expect(page.get_by_role('status',name='Duellergebnis')).to_be_visible()
                    expect(page.locator('.duel-worker-result')).to_have_count(0)
                    expect(page.locator('.duel-worker-result')).to_be_visible(timeout=4000)
                    expect(page.locator('.duel-worker-result')).to_contain_text('Du hast verloren')
                    page.evaluate('window.__finish()')
                    expect(page.locator('.duel-event-stage.event-attack')).to_be_visible()
                    page.get_by_label('Duellmen\u00fc',exact=True).click()
                    page.get_by_role('button',name='Animationen \u00fcberspringen',exact=True).click()
                    expect(page.locator('.duel-worker-result')).to_be_visible(timeout=1000)
                    page.get_by_label('Duellmen\u00fc',exact=True).click()
                    page.evaluate('window.__finish()')
                    expect(page.locator('.duel-event-stage.event-attack')).to_be_visible()
                    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
                    expect(page.locator('.duel-worker-result')).to_be_visible(timeout=1000)
                    assert not key_warnings, key_warnings
                    assert not errors, errors
                    browser.close()
                print(json.dumps({'browser':'passed','checks':['card orientation','chain image and keyboard focus','original answer indexes preserved','chain overlay on mobile','phase dial right of extra zone 2','battle/main 2/end transitions','opponent turn disabled','circular mobile dial and menu fit','Escape restores focus','sapphire own turn and ruby opponent turn','legal attacker highlight','cancel before attack sends no answer','field target and adjacent confirmation','own effect updates viewer immediately without center animation; opponent effect remains visible','named cards and chain resolution in duel log','gold effect glow on all locations','grave activation keeps original answer index','large ordered phase banners and pending turn end','real sound buffer playback and persistent mute','mobile feedback and reduced motion','eight summon portals without hidden card faces','location-accurate attack and direct attack','player LP delta and authoritative final LP','card travel uses original back','user-selected reduction disables SVG travel','larger arena fits 720p and 1080p including footer allowance','premium mobile has no horizontal overflow','victory defeat and draw use engine winner','negated activation announcement','one-card double-click submits exactly once','incomplete multi-selection stays open','maximum selection cannot be exceeded','double-click preserves original selection order','step selection auto-finishes only after engine confirms completion','double-click selects own hand cards','larger own hand fits mobile','required-card count remains visible on mobile','periodic clock state cannot acknowledge a pending action','two shared extra zones retain physical identity across controller and prompt changes for both seats and viewports','occupied shared zones stay visible and placement preserves original indexes','extra deck lists only legal summons and separates browsing','grave and banished action lists preserve original engine indexes','summon guidance keeps card method and material or zone step visible','pile menus fit mobile and close with Escape','opponent boss summon cut-ins with attribute-matched original sound','own weak and covered monsters never trigger a cut-in','decisions compact the cut-in without blocking chain answers','desktop mobile reduced-motion and cut-in disable controls','hand effect choices automatically open a focused popup with shared selection','mobile hand popup retains visible confirmation and supports double-click'],'decision_ready_deduplicated':'passed','left_middle_timer_and_paused_clock':'passed','terminal_attack_damage_result_order':'passed','failed_opponent_image_keeps_occupied_zone_visible':'passed','console_errors':errors}))
            finally:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    run()
