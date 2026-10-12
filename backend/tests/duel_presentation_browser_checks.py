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
                    assert not errors, errors
                    browser.close()
                print(json.dumps({'browser':'passed','checks':['both seats: set monsters sideways, set spells/traps upright','chain image and keyboard focus','effect/pass preserve original prompt indexes','overlay visible on scrolled mobile viewport','overlay disappears after response'],'console_errors':errors}))
            finally:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    run()
