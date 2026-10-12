"""Verify real pack UI releases alerts after flips, never on opening or closing."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from playwright.sync_api import sync_playwright, expect
from browser_smoke import ROOT, free_port, wait_ready


def run():
    frontend = ROOT / 'frontend'
    port = free_port()
    url = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='.pack-reveal-', dir=frontend) as directory:
        folder = Path(directory)
        (folder / 'index.html').write_text('<div id="root"></div><script type="module" src="./check.tsx"></script>', encoding='utf8')
        (folder / 'check.tsx').write_text('''
import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { PackOpeningProvider, usePackOpening } from '../src/components/PackOpening'
import '../src/styles.css'
import '../src/experience.css'
sessionStorage.setItem('hub-session','synthetic-reveal-token')
function App(){const {openPack}=usePackOpening();return <button onClick={()=>openPack({id:1,name:'Testpack',set_code:'TEST',owned:3} as any)}>Testpack öffnen</button>}
createRoot(document.getElementById('root')).render(<BrowserRouter><PackOpeningProvider><App/></PackOpeningProvider></BrowserRouter>)
''', encoding='utf8')
        env = {**os.environ, 'VITE_BASE_PATH': '/'}
        node = os.environ.get('NODE_EXE', 'C:/Program Files/nodejs/node.exe')
        with (ROOT / 'artifacts/pack-reveal-vite.log').open('w') as log:
            process = subprocess.Popen([node, str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(port), '--strictPort'],
                cwd=frontend, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                wait_ready(url, process)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page()
                    errors, releases = [], []
                    opening = [0]
                    page.on('pageerror', lambda error: errors.append(str(error)))

                    def api(route):
                        if route.request.resource_type not in {'fetch', 'xhr'}:
                            route.continue_()
                            return
                        path = route.request.url.split('/api/')[-1]
                        if path == 'boosters/1/open':
                            opening[0] += 1
                            cards = [{'id':i+1,'name':f'Karte {i+1}','rarity':'ultra_rare','type':'Monster','image_url':'', 'set':'Test','set_code':'TEST'} for i in range(3)]
                            route.fulfill(json={'opening_id':opening[0], 'booster_id':1,'remaining':3-opening[0],'credits_remaining':0,'cards':cards})
                        elif path.endswith('/reveal'):
                            releases.append({'path':path, 'indices':route.request.post_data_json['indices']})
                            route.fulfill(json={'confirmed':True})
                        else:
                            route.fulfill(status=404)

                    page.route('**/api/**', api)
                    page.goto(url + '/' + folder.name + '/index.html')
                    page.wait_for_timeout(1000)
                    assert not errors, errors
                    page.get_by_role('button',name='Testpack öffnen',exact=True).click()
                    button = page.get_by_role('button',name='Karte 1 aufdecken',exact=True)
                    expect(button).to_be_visible(timeout=10000)
                    assert not releases
                    button.click()
                    page.wait_for_timeout(500)
                    assert not releases, 'Alert released during flip'
                    page.wait_for_timeout(650)
                    assert releases == [{'path':'booster-openings/1/reveal','indices':[0]}]
                    page.get_by_role('button',name='Alle aufdecken',exact=True).click()
                    expect(page.get_by_role('button',name='Nächstes Pack öffnen',exact=True)).to_be_visible()
                    page.wait_for_timeout(150)
                    assert releases[-1]['indices'] == [0,1,2]
                    count = len(releases)
                    page.get_by_role('button',name='Nächstes Pack öffnen',exact=True).click()
                    expect(page.get_by_role('button',name='Karte 1 aufdecken',exact=True)).to_be_visible(timeout=10000)
                    page.wait_for_timeout(1000)
                    assert len(releases) == count, 'Previous reveals leaked into next opening'
                    page.get_by_role('button',name='Öffnung schließen',exact=True).click()
                    page.wait_for_timeout(1000)
                    assert len(releases) == count, 'Closing revealed covered cards'
                    assert not errors, errors
                    browser.close()
            finally:
                process.terminate()
                process.wait(timeout=15)
    print(json.dumps({'passed':True, 'checks':['no-spoiler-before-flip','after-flip','reveal-all','next-pack','close-covered']}))


if __name__ == '__main__':
    run()
