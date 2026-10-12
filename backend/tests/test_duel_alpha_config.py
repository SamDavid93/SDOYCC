from unittest import TestCase
from app.core.config import Settings


class AlphaConfigTests(TestCase):
    def config(self, **values):
        return Settings(_env_file=None, **values)

    def test_production_requires_explicit_alpha_flag(self):
        self.assertFalse(self.config(app_env='production', enable_duel_worker_lab=True).duel_worker_enabled)
        config = self.config(app_env='production', enable_duel_alpha=True, enable_demo_auth=True)
        self.assertTrue(config.duel_worker_enabled)
        self.assertFalse(config.demo_enabled)
        self.assertFalse(config.duel_worker_lab_enabled)

    def test_alpha_does_not_enable_development_or_unknown_environment(self):
        for env in ('development', 'staging', 'prod'):
            self.assertFalse(self.config(app_env=env, enable_duel_alpha=True).duel_worker_enabled)
        self.assertTrue(self.config(app_env='development', enable_duel_worker_lab=True).duel_worker_enabled)

    def test_default_is_disabled(self):
        self.assertFalse(self.config().duel_worker_enabled)
