import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image
from app.modules import cardcluster_images as scans, german_images


class CardclusterImageTests(unittest.TestCase):
    def setUp(self):
        scans._failures.clear()
        buffer = io.BytesIO()
        Image.new('RGB', (500, 731)).save(buffer, format='WEBP')
        self.content = buffer.getvalue()

    def response(self, content):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_bytes.return_value = [content]
        return response

    def test_preferred_scan_upgrades_old_cache_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(scans, 'CACHE', Path(temp) / 'preferred'), patch.object(german_images, 'CACHE', Path(temp) / 'old'), patch.object(scans.httpx, 'stream', return_value=self.response(self.content)) as stream:
            german_images.CACHE.mkdir()
            (german_images.CACHE / '4007.img').write_bytes(b'old scan')
            result = german_images.german_image(4007)
            self.assertEqual(result.read_bytes(), self.content)
            self.assertEqual(german_images.image_response(result).media_type, 'image/webp')
            self.assertEqual(german_images.german_image(4007), result)
            self.assertEqual(stream.call_count, 1)
            self.assertFalse(stream.call_args.kwargs['follow_redirects'])

    def test_failed_download_keeps_old_german_scan_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(scans, 'CACHE', Path(temp) / 'preferred'), patch.object(german_images, 'CACHE', Path(temp) / 'old'), patch.object(scans.httpx, 'stream', return_value=self.response(b'<html>blocked</html>')) as stream:
            german_images.CACHE.mkdir()
            old = german_images.CACHE / '4007.img'
            old.write_bytes(b'old scan')
            self.assertEqual(german_images.german_image(4007), old)
            self.assertEqual(german_images.german_image(4007), old)
            self.assertEqual(stream.call_count, 1)

    def test_unverified_or_english_sources_are_never_requested(self):
        with patch.object(scans, 'SOURCES', {1: 'SET/SET-EN001-1234567890-500.webp', 2: '../outside'}), patch.object(scans.httpx, 'stream') as stream:
            for code in (1, 2, 3):
                self.assertIsNone(scans.preferred_image(code))
            stream.assert_not_called()

    def test_low_resolution_scan_is_rejected(self):
        buffer = io.BytesIO()
        Image.new('RGB', (100, 146)).save(buffer, format='WEBP')
        with tempfile.TemporaryDirectory() as temp, patch.object(scans, 'CACHE', Path(temp)), patch.object(scans.httpx, 'stream', return_value=self.response(buffer.getvalue())):
            self.assertIsNone(scans.preferred_image(4007))
            self.assertEqual(list(Path(temp).iterdir()), [])
