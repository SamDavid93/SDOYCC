import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("configure_public", Path(__file__).resolve().parents[1] / "scripts" / "configure_public.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class PublicConfigTests(unittest.TestCase):
    def test_project_pages_origin_has_no_repository_path(self):
        values = config.public_values("https://samdavidofficial.github.io/sdoycc", "https://api.sdoycc.de/api/")
        self.assertEqual(values["FRONTEND_URL"], "https://samdavidofficial.github.io/sdoycc/")
        self.assertEqual(values["CORS_ORIGINS"], "https://samdavidofficial.github.io")
        self.assertEqual(values["VITE_BASE_PATH"], "/sdoycc/")
        self.assertEqual(values["VITE_API_BASE_URL"], "https://api.sdoycc.de/api")
        self.assertEqual(values["APP_ENV"], "production")
        self.assertEqual(values["ENABLE_DEMO_AUTH"], "false")

    def test_root_site_and_backend_origin(self):
        values = config.public_values("https://samdavidofficial.github.io/", "https://api.sdoycc.de")
        self.assertEqual(values["VITE_BASE_PATH"], "/")
        self.assertEqual(values["VITE_API_BASE_URL"], "https://api.sdoycc.de/api")

    def test_rejects_local_insecure_credentials_query_and_wrong_api_path(self):
        invalid = ["http://api.sdoycc.de", "https://localhost", "https://127.0.0.1", "https://10.0.0.1",
                   "https://[::1]", "https://secret@api.sdoycc.de", "https://api.sdoycc.de?token=private",
                   "https://api.sdoycc.de/#secret", "https://YOUR_BACKEND_HOST", "https://api.sdoycc.de/v2",
                   "https://api.sdoycc.de:8002", "https://api.sdoycc.de:broken"]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                config.public_values("https://samdavidofficial.github.io/sdoycc/", url)

    def test_secrets_database_and_comments_survive_duplicate_replacement(self):
        original = '# Kommentar\r\nSTREAMERBOT_API_KEY="local-secret=keep"\r\nDATABASE_URL=sqlite:///./live.db\r\nAPP_ENV=development\r\nexport APP_ENV=development\r\nTWITCH_REWARD_ID=keep-reward'
        rendered = config.render_env(original, {"APP_ENV": "production", "ENABLE_DEMO_AUTH": "false"})
        self.assertIn('STREAMERBOT_API_KEY="local-secret=keep"\r\nDATABASE_URL=sqlite:///./live.db\r\n', rendered)
        self.assertTrue(rendered.startswith('# Kommentar\r\n'))
        self.assertIn('TWITCH_REWARD_ID=keep-reward\n', rendered)
        self.assertEqual(rendered.count('APP_ENV='), 1)
        self.assertIn('APP_ENV=production\n', rendered)

    def test_backup_is_exact_and_repeat_has_no_extra_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = root / ".env"
            original = b'\xef\xbb\xbfSTREAMERBOT_API_KEY="local-only"\r\nAPP_ENV=development\r\n'
            env.write_bytes(original)
            backup = config.apply_config(env, {"APP_ENV": "production"}, root / "backups")
            self.assertEqual(backup.read_bytes(), original)
            self.assertIn('STREAMERBOT_API_KEY="local-only"', env.read_text())
            self.assertIsNone(config.apply_config(env, {"APP_ENV": "production"}, root / "backups"))
            self.assertEqual(len(list((root / "backups").iterdir())), 1)

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = root / ".env"
            original = b'APP_ENV=development\n'
            env.write_bytes(original)
            with patch.object(config.os, "replace", side_effect=OSError("locked")), self.assertRaises(OSError):
                config.apply_config(env, {"APP_ENV": "production"}, root / "backups")
            self.assertEqual(env.read_bytes(), original)
            self.assertEqual(list(root.glob('.env.public-*')), [])


if __name__ == "__main__":
    unittest.main()
