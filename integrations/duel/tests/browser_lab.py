"""Real Windows EDOPro core + two independent Edge browser sessions, local only."""
import json
from pathlib import Path
import socket
import sys
import threading
import time

import httpx
from playwright.sync_api import sync_playwright, expect
import uvicorn

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from lab import create_app


def run(surrender=False):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    app = create_app(origins=(url,))
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error', access_log=False, ws_max_size=4096))
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    artifacts = BASE.parents[1] / 'artifacts/duel-lab'
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.1)
        assert server.started, 'Laboratory failed to start'
        assert httpx.post(url + '/session', json={'code': 'x' * 24}, headers={'Origin': url}).status_code == 401
        assert httpx.post(url + '/session', json={'code': app.state.codes[0]}, headers={'Origin': 'https://other.invalid'}).status_code == 403
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            contexts = [browser.new_context(viewport={'width': 1440, 'height': 1100}) for _ in range(2)]
            pages = [context.new_page() for context in contexts]
            messages, errors = [[], []], []
            for seat, page in enumerate(pages):
                page.on('pageerror', lambda error: errors.append(str(error)))
                def bind(ws, seat=seat):
                    ws.on('framereceived', lambda raw: messages[seat].append(json.loads(raw)))
                page.on('websocket', bind)
                page.goto(url)
                page.get_by_label('Persönlicher Laborzugang').fill(app.state.codes[seat])
                page.get_by_role('button', name='Verbinden', exact=True).click()
            expect(pages[0].locator('#table')).to_be_visible()
            expect(pages[1].locator('#table')).to_be_visible()
            states = lambda seat: [m for m in messages[seat] if m['type'] == 'state']
            for seat in (0, 1):
                snapshot = states(seat)[-1]
                assert all(card is None for card in snapshot['boards'][1-seat]['hand'])
                assert all(card and 'code' in card for card in snapshot['boards'][seat]['hand'])
                assert '_response' not in json.dumps(snapshot)
                expect(pages[seat].locator('#opponent-hand button')).to_have_count(0)
            pages[0].locator('#own-hand button').first.click()
            expect(pages[0].get_by_role('dialog')).to_be_visible()
            expect(pages[0].locator('#card-text')).not_to_be_empty()
            pages[0].keyboard.press('Escape')
            expect(pages[0].get_by_role('dialog')).not_to_be_visible()
            pages[0].screenshot(path=str(artifacts / 'browser-desktop.png'), full_page=True)
            pages[1].set_viewport_size({'width': 390, 'height': 844})
            assert pages[1].evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow'
            pages[1].screenshot(path=str(artifacts / 'browser-mobile.png'), full_page=True)
            pages[1].set_viewport_size({'width': 1440, 'height': 1100})

            # Attempt an opponent's prompt and a stale prompt through a second socket.
            # Duplicate seat must be rejected before it can send gameplay commands.
            duplicate = pages[0].evaluate("""() => new Promise(resolve => {
              const ws = new WebSocket(`ws://${location.host}/duel`);
              ws.onclose = e => resolve(e.code);
              setTimeout(() => { ws.close(); resolve(-1) }, 3000);
            })""")
            assert duplicate == 4409
            if surrender:
                # Player 2 may concede during player 1's turn. Cancel must do nothing.
                worker = app.state.engine.process
                pages[1].once('dialog', lambda dialog: dialog.dismiss())
                pages[1].get_by_role('button', name='Duell aufgeben', exact=True).click()
                expect(pages[1].get_by_role('button', name='Duell aufgeben', exact=True)).to_be_enabled()
                assert not app.state.projection.ended
                pages[1].once('dialog', lambda dialog: dialog.accept())
                pages[1].get_by_role('button', name='Duell aufgeben', exact=True).click()
                expect(pages[0].locator('#result-reason')).to_have_text('Dein Gegner hat aufgegeben.')
                expect(pages[1].locator('#result-reason')).to_have_text('Du hast aufgegeben.')
                expect(pages[0].locator('#decision-title')).to_have_text('Du hast gewonnen.')
                for page in pages:
                    expect(page.locator('#surrender')).to_be_disabled()
                    expect(page.locator('#actions button')).to_have_count(0)
                assert worker.returncode is not None and app.state.engine.process is None
                assert not errors, errors
                report = {'status': 'passed', 'scenario': 'surrender', 'cancel_preserves_duel': True,
                          'winner': 0, 'worker_stopped': True, 'console_errors': errors,
                          'network': 'local loopback', 'production_accounts_modified': False}
                (artifacts / 'surrender-report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
                print(json.dumps(report))
                browser.close()
                return
            priorities = ['Aktivieren:', 'Beschwören:', 'Angreifen:', 'Kampfphase', 'Nicht anketten', 'Zug beenden']
            seen_animations = set()
            for step in range(1200):
                snapshots = [states(seat)[-1] for seat in (0, 1)]
                if snapshots[0]['ended']: break
                seat = next(i for i, snapshot in enumerate(snapshots) if snapshot['prompt'])
                snapshot, page = snapshots[seat], pages[seat]
                prompt = snapshot['prompt']
                seen_animations.update(e['kind'] for e in snapshot['events'])
                if prompt.get('select'):
                    for index in range(prompt['minimum']): page.locator(f'[data-choice="{index}"]').click()
                    page.get_by_role('button', name='Auswahl bestätigen').click()
                else:
                    index = min(range(len(prompt['choices'])), key=lambda i: next((rank for rank, name in enumerate(priorities) if prompt['choices'][i]['label'].startswith(name)), 99))
                    page.locator(f'[data-choice="{index}"]').click()
                for other in pages:
                    # Wait for the latest projection to be rendered in each browser.
                    other.wait_for_function('(revision) => document.querySelector("#table").dataset.revision > revision', arg=snapshot['revision'])
                if any(m['type'] == 'failure' for group in messages for m in group):
                    raise AssertionError('Unsupported engine path in browser test')
            else:
                raise AssertionError('Engine did not finish within the safety limit')
            final = states(0)[-1]
            assert final['winner'] in (0, 1, 2)
            assert final['ended'] and states(1)[-1]['ended']
            assert {'draw', 'summon', 'attack', 'lp'} <= seen_animations
            assert not errors, errors
            pages[0].screenshot(path=str(artifacts / 'result-desktop.png'), full_page=True)
            report = {'status': 'passed', 'engine': 'EDOPro native API 11.0', 'steps': step,
                      'turns': final['turn_number'], 'winner': final['winner'],
                      'observed_messages': sorted(app.state.projection.seen),
                      'observed_animation_events': sorted(seen_animations),
                      'separate_browser_sessions': 2, 'network': 'local loopback; external network not tested',
                      'console_errors': errors, 'production_accounts_modified': False}
            (artifacts / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print(json.dumps(report))
            browser.close()
    finally:
        server.should_exit = True; thread.join(timeout=15)
        assert not thread.is_alive(), 'Laboratory did not stop cleanly'


if __name__ == '__main__': run(surrender='--surrender' in sys.argv)
