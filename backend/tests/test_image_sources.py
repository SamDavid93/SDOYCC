import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.modules import image_sources


class ImageSourceTests(unittest.TestCase):
    def test_uses_explicit_german_index_not_best_english_image(self):
        manifest = {'cards': {'4007': {'1': {'bestArt': '//artworks-en-n.ygoresources.com/en.png', 'idx': {'de': [{'path': '//artworks-de-db.ygoresources.com/de.png'}], 'en': [{'path': '//artworks-en-n.ygoresources.com/en.png'}]}}}}}
        with tempfile.TemporaryDirectory() as temp, patch.object(image_sources, 'INDEX', Path(temp) / 'index.json'), patch.object(image_sources, '_index', None):
            image_sources.refresh_index(manifest)
            self.assertEqual(image_sources.german_sources(4007), ['https://artworks-de-db.ygoresources.com/de.png'])
            self.assertEqual(image_sources.german_sources(999), [])

    def test_image_hosts_are_restricted(self):
        for path in ['https://evil.test/x.png', 'http://127.0.0.1/x', '//artworks.ygoresources.com.evil.test/x', 'https://artworks-de-db.ygoresources.com:8080/x']:
            self.assertIsNone(image_sources.trusted_artwork_url(path))
