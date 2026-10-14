"""Import original EU product-gallery images; never modify catalogue or economy data."""
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from sync_booster_covers import BASE, ROOT, download, identity

CATEGORIES = ('booster-packs-de', 'structure-decks-de', 'starter-decks-de',
              'tins-de', 'andere', 'ots-tournament-packs-de', 'speed-duel-de')


class Tags(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


def trusted_page(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == 'www.yugioh-card.com' and parsed.path.startswith('/eu/')


def fetch(url):
    for _ in range(4):
        if not trusted_page(url):
            raise ValueError('Untrusted product page')
        response = httpx.get(url, timeout=30, follow_redirects=False)
        if not response.is_redirect:
            response.raise_for_status()
            return response.text
        url = urljoin(url, response.headers['location'])
    raise ValueError('Too many redirects')


def clean(value):
    return html.unescape(re.sub('<[^>]+>', '', value)).strip()


def index_products(markup, page):
    for block in re.findall(r'<article\b[^>]*class="[^"]*product-tile[^"]*"[^>]*>(.*?)</article>', markup, re.S):
        heading = re.search(r'<h2\b[^>]*>(.*?)</h2>', block, re.S)
        tags = Tags(block).tags
        links = [attrs.get('href', '') for tag, attrs in tags if tag == 'a' and 'product-tile__link' in attrs.get('class', '')]
        images = [attrs.get('src', '') for tag, attrs in tags if tag == 'img']
        if heading and links and images:
            source = urljoin(page, links[0])
            if trusted_page(source) and '/product/' in urlparse(source).path:
                yield {'name': clean(heading[1]), 'source': source, 'index': page,
                       'image_source': urljoin(page, images[0])}


def next_page(markup, page):
    for tag, attrs in Tags(markup).tags:
        if tag == 'a' and {'next', 'page-numbers'} <= set(attrs.get('class', '').split()):
            url = urljoin(page, attrs.get('href', ''))
            if trusted_page(url) and urlparse(url).path.startswith(urlparse(page).path.split('/page/')[0]):
                return url
    return None


def gallery(markup, source):
    match = re.search(r'const\s+lg_elements\s*=\s*(\[.*?\]);', markup, re.S)
    if not match:
        return []
    return [urljoin(source, item['src']) for item in json.loads(match[1]) if item.get('src')]


def image_priority(url):
    filename = urlparse(url).path.rsplit('/', 1)[-1].lower()
    german = bool(re.search(r'[-_]de(?:[-_.]|$)', filename))
    single = 'single' in filename
    display = 'display' in filename or 'stack' in filename
    return (not german, not single, display, filename)


def resolve(item):
    try:
        markup = fetch(item['source'])
        tags = Tags(markup).tags
        names = [item['name']]
        english = next((urljoin(item['source'], attrs['href']) for tag, attrs in tags
                        if tag == 'link' and attrs.get('hreflang') == 'en' and attrs.get('href')), None)
        if english and trusted_page(english):
            english_markup = fetch(english)
            names.extend(attrs['content'] for tag, attrs in Tags(english_markup).tags
                         if tag == 'meta' and attrs.get('property') == 'og:title' and attrs.get('content'))
        images = sorted(set(gallery(markup, item['source'])), key=image_priority)
        images.append(item['image_source'])
        rejected = []
        for image in dict.fromkeys(images):
            result = download({**item, 'image_source': image, 'aliases': list(dict.fromkeys(names)), 'region': 'eu'})
            if 'file' in result:
                filename = urlparse(image).path.rsplit('/', 1)[-1]
                result['image_language'] = 'de' if re.search(r'[-_]DE(?:[-_.]|$)', filename, re.I) else 'unspecified'
                return result
            rejected.append(result['rejected'])
        return {**item, 'rejected': rejected}
    except (httpx.HTTPError, ValueError, KeyError) as error:
        return {**item, 'rejected': str(error)}


def main():
    items, failures = {}, []
    for category in CATEGORIES:
        page = f'{BASE}/eu/de/product-category/{category}/'
        visited = set()
        while page and page not in visited and len(visited) < 30:
            visited.add(page)
            try:
                markup = fetch(page)
                found = list(index_products(markup, page))
                for item in found:
                    items.setdefault(item['source'], item)
                print(f'{category}: page {len(visited)}, {len(found)} products', flush=True)
                page = next_page(markup, page)
            except (httpx.HTTPError, ValueError) as error:
                failures.append({'page': page, 'error': str(error)})
                break
    if not items:
        raise ValueError('No EU products found; keeping existing covers')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(resolve, items.values()))
    target = ROOT / 'frontend/src/data/officialBoosterCovers.json'
    covers = json.loads(target.read_text(encoding='utf-8'))
    accepted = [item for item in results if 'file' in item]
    for item in accepted:
        for name in item['aliases']:
            key = identity(name)
            if key:
                covers[key] = item
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(covers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
    report = {'products': len(items), 'accepted': len(accepted), 'manifest_keys': len(covers),
              'german_images': sum(item['image_language'] == 'de' for item in accepted),
              'index_failures': failures, 'rejected': [item for item in results if 'rejected' in item]}
    (ROOT / 'artifacts/official-eu-product-covers.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('rejected', 'index_failures')}), flush=True)


if __name__ == '__main__':
    main()
