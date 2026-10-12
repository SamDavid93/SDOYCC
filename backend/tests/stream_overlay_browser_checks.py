"""Exercise the actual overlay with synthetic draws; no account or Twitch writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / 'backend/app/modules/rare-pulls-overlay.html').read_text(encoding='utf8')


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        errors, acknowledgements = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        notice = {'id': 1, 'claim_token': 'synthetic-token-' * 3, 'username': 'TestZuschauer',
                  'quantity': 2, 'rarity': 'Ultraselten', 'booster_name': 'Testpack',
                  'card': {'name': 'Testkarte', 'image_url': '/image.jpg', 'fallback_image_url': '/fallback.jpg'}}

        def route(request):
            path = request.request.url.split('127.0.0.1:8002')[-1].split('?')[0]
            if path == '/api/stream-overlay/rare-pulls':
                request.fulfill(content_type='text/html', body=HTML)
            elif path == '/api/stream-overlay/channel':
                request.fulfill(json={'broadcaster_login': 'test'})
            elif path == '/api/stream-overlay/claim':
                request.fulfill(json={'announcement': notice if len(acknowledgements) < 2 else None})
            elif path.endswith('/ack'):
                acknowledgements.append(request.request.post_data_json)
                request.fulfill(status=503 if len(acknowledgements) == 1 else 200,
                                json={'acknowledged': True})
            elif path == '/image.jpg':
                request.fulfill(status=404)
            elif path == '/fallback.jpg':
                request.fulfill(content_type='image/jpeg', body=(ROOT / 'frontend/src/assets/card-back.jpg').read_bytes())
            else:
                request.fulfill(status=404)

        page.route('**/*', route)
        page.goto('http://127.0.0.1:8002/api/stream-overlay/rare-pulls')
        page.wait_for_function("document.querySelector('#alert').classList.contains('visible')")
        expect(page.locator('#viewer')).to_contain_text('@TestZuschauer')
        expect(page.locator('#name')).to_have_text('2 × Testkarte')
        assert page.locator('#card').evaluate('(e)=>e.complete && e.naturalWidth > 0')
        assert page.locator('#card').get_attribute('src') == '/fallback.jpg'
        assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgba(0, 0, 0, 0)'
        page.wait_for_timeout(450)
        box = page.locator('#alert').bounding_box()
        assert box and abs(box['x'] - 32) < 1 and abs(box['y'] + box['height'] - 1048) < 1
        page.screenshot(path=str(ROOT / 'artifacts/stream-overlay-desktop.png'), omit_background=True)
        page.wait_for_function("JSON.parse(localStorage.getItem('sdoycc-overlay-seen')||'[]').includes(1)", timeout=15000)
        page.wait_for_timeout(6500)
        assert len(acknowledgements) == 2
        assert all(item['claim_token'] == notice['claim_token'] for item in acknowledgements)
        assert not page.locator('#alert').evaluate("(e)=>e.classList.contains('visible')")
        acknowledgements.clear()
        page.reload()
        page.wait_for_timeout(500)
        assert not page.locator('#alert').evaluate("(e)=>e.classList.contains('visible')")
        assert len(acknowledgements) == 1
        assert not errors, errors
        browser.close()
    print(json.dumps({'passed': True, 'checks': ['transparent', 'bottom-left', 'card-fallback', 'quantity', 'ack-retry', 'deduplication', 'reload']}))


if __name__ == '__main__':
    run()
