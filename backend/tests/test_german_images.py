import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from app.modules import german_images


class GermanImageTests(unittest.TestCase):
    def setUp(self):
        self.sources = patch.object(german_images, 'german_sources', return_value=[])
        self.sources.start()
        self.addCleanup(self.sources.stop)

    def test_cdn_is_preferred_without_fetching_card_html(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(german_images, 'CACHE', Path(temp)), patch.object(german_images, 'german_sources', return_value=['https://artworks-de-db.ygoresources.com/card.png']), patch.object(german_images.httpx, 'get') as get, patch.object(german_images.httpx, 'Client') as html_client:
            get.return_value.content = b'\x89PNG\r\n\x1a\noriginal-cdn-bytes'
            german_images._failures.clear()
            self.assertEqual(german_images.german_image(4007).read_bytes(), get.return_value.content)
            german_images.german_image(4007)
            self.assertEqual(get.call_count, 1)
            html_client.assert_not_called()

    def test_original_image_is_cached_and_rejects_arbitrary_urls(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(german_images, 'CACHE', Path(temp) / 'de'), patch.object(german_images.httpx, 'get') as get:
            get.return_value.content = b'\xff\xd8original-jpeg'
            url = 'https://images.ygoprodeck.com/images/cards/123.jpg'
            self.assertEqual(german_images.original_image(url).read_bytes(), get.return_value.content)
            german_images.original_image(url)
            self.assertEqual(get.call_count, 1)
            for invalid in ['http://127.0.0.1/test', 'https://images.ygoprodeck.com.evil.test/images/cards/123.jpg']:
                with self.assertRaises(HTTPException):
                    german_images.original_image(invalid)
            self.assertEqual(get.call_count, 1)

    def test_png_preview_is_cached_without_changing_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(german_images, 'CACHE', Path(temp)), patch.object(german_images.httpx, 'Client') as factory:
            client = factory.return_value.__enter__.return_value
            page = MagicMock()
            page.text = '<meta property="og:image" content="https://www.db.yugioh-card.com/yugiohdb/get_image.action?cid=4007&amp;request_locale=de">'
            image = MagicMock()
            image.content = b'\x89PNG\r\n\x1a\nsource-preview'
            client.get.side_effect = [page, image]
            german_images._failures.clear()
            path = german_images.german_image(4007)
            self.assertEqual(path.read_bytes(), image.content)
            self.assertEqual(german_images.german_image(4007), path)
            self.assertEqual(client.get.call_count, 2)

    def test_untrusted_or_non_german_source_is_not_downloaded(self):
        for url in ['https://example.com/image?cid=4007&request_locale=de', 'https://www.db.yugioh-card.com/yugiohdb/get_image.action?cid=4007&request_locale=en']:
            with tempfile.TemporaryDirectory() as temp, patch.object(german_images, 'CACHE', Path(temp)), patch.object(german_images.httpx, 'Client') as factory:
                client = factory.return_value.__enter__.return_value
                page = MagicMock(); page.text = f'<meta property="og:image" content="{url}">'
                client.get.return_value = page
                german_images._failures.clear()
                with self.assertRaises(HTTPException):
                    german_images.german_image(4007)
                self.assertEqual(client.get.call_count, 1)
        german_images._failures.clear()
