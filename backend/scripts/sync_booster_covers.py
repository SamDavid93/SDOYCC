"""Cache verified, sufficiently large official booster images without changing the database."""
import hashlib
import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://www.yugioh-card.com'
PAGES = ['/en/products/booster-pack/', '/en/products/past_products/booster-pack-archive/']


def identity(name):
    name = re.sub(r'\s+Booster$', '', name, flags=re.I)
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())


def products(markup, page):
    for block in re.findall(r'<section class="detail clear">(.*?)</li>', markup, re.S):
        image = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"', block)
        heading = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.S)
        link = re.search(r'<a class="btn" href="([^"]+)"', block)
        if not image or not heading or not link:
            continue
        name = html.unescape(re.sub('<[^>]+>', '', heading[1])).strip()
        if not identity(name) or identity(name) != identity(html.unescape(image[2])):
            continue
        url = urljoin(BASE, html.unescape(image[1]))
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'www.yugioh-card.com' or not parsed.path.startswith('/en/wp-content/uploads/'):
            continue
        yield {'name': name, 'image_source': url, 'source': urljoin(BASE, link[1]), 'index': page}


def download(item):
    try:
        url = item['image_source']
        for _ in range(4):
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.netloc not in ('www.yugioh-card.com', 'img.yugioh-card.com') or not parsed.path.startswith(('/en/wp-content/uploads/', '/eu/wp-content/uploads/')):
                raise ValueError('untrusted image redirect')
            response = httpx.get(url, timeout=30, follow_redirects=False)
            if not response.is_redirect:
                break
            url = urljoin(url, response.headers['location'])
        response.raise_for_status()
        if len(response.content) > 6 * 1024 * 1024:
            raise ValueError('image too large')
        focus = None
        with Image.open(BytesIO(response.content)) as image:
            width, height = image.size
            extension = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}.get(image.format)
            if not extension or width < 240 or height < 400 or not .8 <= height / width <= 2.4:
                raise ValueError(f'unsuitable pack image: {width}x{height}')
            image.verify()
        if item.get('region') == 'eu':
            # Measure the product against the white studio canvas. Only the
            # viewport changes; the downloaded original remains untouched.
            with Image.open(BytesIO(response.content)) as image:
                rgb = image.convert('RGB')
                difference = ImageChops.difference(rgb, Image.new('RGB', rgb.size, 'white')).convert('L')
                bounds = difference.point(lambda value: 255 if value > 65 else 0).getbbox()
                if bounds:
                    padding = round(min(width, height) * .035)
                    left, top, right, bottom = bounds
                    left, top = max(0, left-padding), max(0, top-padding)
                    right, bottom = min(width, right+padding), min(height, bottom+padding)
                    focus = [left, top, right-left, bottom-top]
        digest = hashlib.sha256(response.content).hexdigest()
        filename = digest[:20] + '.' + extension
        folder = ROOT / 'frontend/public/booster-covers'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(response.content)
        return {**item, 'file': 'booster-covers/' + filename, 'width': width, 'height': height, 'sha256': digest,
                **({'focus': focus} if focus else {})}
    except (httpx.HTTPError, OSError, ValueError) as error:
        return {**item, 'rejected': str(error)}


def main():
    items = {}
    for path in PAGES:
        page = BASE + path
        response = httpx.get(page, timeout=30)
        response.raise_for_status()
        for item in products(response.text, page):
            items.setdefault(identity(item['name']), item)
    if not items:
        raise ValueError('Official product index is empty; keeping existing cover manifest.')
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(download, items.values()))
    accepted = {identity(item['name']): item for item in results if 'file' in item}
    target = ROOT / 'frontend/src/data/officialBoosterCovers.json'
    previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    # Keep verified European gallery images preferred when the US archive is refreshed.
    european = {key: item for key, item in previous.items()
                if item.get('region') == 'eu' and (ROOT / 'frontend/public' / item['file']).is_file()}
    accepted = {**previous, **accepted, **european}  # Source outages never remove working covers.
    if not accepted:
        raise ValueError('No suitable official covers; keeping existing manifest.')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(accepted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    report = {'products': len(items), 'covers': len(accepted), 'rejected': [item for item in results if 'rejected' in item]}
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / 'artifacts/official-booster-covers.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'products': len(items), 'covers': len(accepted), 'rejected': len(report['rejected'])}))


if __name__ == '__main__':
    main()
