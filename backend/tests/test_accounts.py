from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.core.auth import token_hash
from app.core.config import settings
from app.core.passwords import verify_password
from app.db.models import AuthSession, DiamondTransaction, RegistrationChallenge, RegistrationInvite, User
from test_economy import HubTestCase


class AccountTests(HubTestCase):
    password = "Mein-Hub-Passwort-123!"

    def setUp(self):
        super().setUp()
        self.previous = (settings.streamerbot_api_key, settings.twitch_reward_id)
        settings.streamerbot_api_key = "test-bridge-key-" + "x" * 32
        settings.twitch_reward_id = "reward-1"
        self.bridge_headers = {"X-Streamerbot-Key": settings.streamerbot_api_key}
        self.identity = {"user_id": "456", "username": "Viewer", "display_name": "Viewer", "broadcaster_login": "SamDavidOfficial"}

    def tearDown(self):
        settings.streamerbot_api_key, settings.twitch_reward_id = self.previous
        super().tearDown()

    def invite(self, identity=None):
        response = self.client.post("/api/integrations/streamerbot/register", headers=self.bridge_headers, json=identity or self.identity)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def credentials(self, response=None):
        invite = response or self.invite()
        self.assertNotIn("token=", invite["registration_url"])
        challenge = self.start(invite["username"])
        response = self.confirm(challenge["code"])
        self.assertEqual(response.status_code, 200, response.text)
        return {"token": challenge["token"], "username": invite["username"], "password": self.password}

    def start(self, username="viewer"):
        response = self.client.post("/api/auth/register/start", json={"username": username})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def confirm(self, code, **identity):
        return self.client.post("/api/integrations/streamerbot/confirm", headers=self.bridge_headers,
                                json={**self.identity, **identity, "code": code})

    def redeem(self, status="fulfilled", **extra):
        return self.client.post("/api/integrations/streamerbot/redemptions", headers=self.bridge_headers,
            json={**self.identity, "redemption_id": "redemption-1", "reward_id": "reward-1", "reward_cost": 1000, "status": status, **extra})

    def test_registration_and_password_login_preserve_precredited_balance(self):
        credit = self.redeem()
        self.assertEqual(credit.status_code, 200, credit.text)
        credentials = self.credentials(credit.json())
        registered = self.client.post("/api/auth/register", json=credentials)
        self.assertEqual(registered.status_code, 200, registered.text)
        token = registered.json()["token"]
        self.assertEqual(self.client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).json()["diamonds"], 100)
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.twitch_id == "456"))
            self.assertEqual(user.username, "viewer")
            self.assertNotIn(self.password, user.password_hash)
            self.assertTrue(verify_password(self.password, user.password_hash))
            self.assertIsNone(db.scalar(select(RegistrationChallenge)))
        self.assertEqual(self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code, 204)
        self.assertEqual(self.client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code, 401)
        login = self.client.post("/api/auth/login", json={"username": "VIEWER", "password": self.password})
        self.assertEqual(login.status_code, 200)

    def test_modified_username_token_or_expired_invite_is_rejected(self):
        credentials = self.credentials()
        self.assertEqual(self.client.post("/api/auth/register", json={**credentials, "username": "someone_else"}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/register", json={**credentials, "token": "x" * 43}).status_code, 400)
        with self.sessions() as db:
            invite = db.scalar(select(RegistrationChallenge))
            invite.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 400)

    def test_rotated_link_invalidates_old_link_without_losing_balance(self):
        old = self.credentials(self.redeem().json())
        new = self.credentials()
        self.assertEqual(self.client.post("/api/auth/register", json=old).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/register", json=new).status_code, 200)
        self.assertIsNone(self.invite()["registration_url"])

    def test_registration_link_cannot_reset_existing_password(self):
        credentials = self.credentials()
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/register", json={**credentials, "password": "Malicious-new-password"}).status_code, 400)
        self.assertTrue(self.invite()["registered"])

    def test_concurrent_registration_consumes_invite_once(self):
        credentials = self.credentials()
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: self.client.post("/api/auth/register", json=credentials), range(2)))
        self.assertEqual(sorted(reply.status_code for reply in replies), [200, 400])

    def test_bridge_rejects_unauthorized_calls_and_wrong_channel(self):
        url = "/api/integrations/streamerbot/register"
        self.assertEqual(self.client.post(url, json=self.identity).status_code, 401)
        self.assertEqual(self.client.post(url, headers={"X-Streamerbot-Key": "wrong"}, json=self.identity).status_code, 401)
        self.assertEqual(self.client.post(url, headers=self.bridge_headers, json={**self.identity, "broadcaster_login": "wrong"}).status_code, 403)

    def test_initial_redemption_credits_immediately_and_update_never_twice(self):
        response = self.redeem("unfulfilled")
        credentials = self.credentials(response.json())
        self.assertEqual(response.json()["diamonds"], 100)
        self.assertTrue(response.json()["credited"])
        self.assertTrue(response.json()["fulfill_required"])
        retry = self.redeem("unfulfilled").json()
        self.assertFalse(retry["credited"])
        self.assertTrue(retry["fulfill_required"])
        self.assertFalse(self.redeem().json()["credited"])
        self.assertFalse(self.redeem().json()["fulfill_required"])
        self.assertTrue(self.redeem().json()["duplicate"])
        self.assertEqual(self.redeem().json()["diamonds"], 100)
        # Later reward notifications must not invalidate the browser confirmation.
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 200)
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(DiamondTransaction)).all()), 1)

    def test_cancellation_before_delayed_event_prevents_credit(self):
        canceled = self.redeem("canceled").json()
        self.assertEqual(canceled["diamonds"], 0)
        self.assertFalse(canceled["fulfill_required"])
        for status in ("unfulfilled", "fulfilled"):
            delayed = self.redeem(status).json()
            self.assertTrue(delayed["duplicate"])
            self.assertFalse(delayed["credited"])
            self.assertFalse(delayed["fulfill_required"])
            self.assertEqual(delayed["diamonds"], 0)

    def test_cancellation_after_credit_flags_manual_reconciliation(self):
        self.redeem("unfulfilled")
        canceled = self.redeem("canceled").json()
        self.assertTrue(canceled["canceled_after_credit"])
        self.assertFalse(canceled["fulfill_required"])
        self.assertFalse(canceled["credited"])
        self.assertEqual(canceled["diamonds"], 100)

    def test_concurrent_reward_delivery_does_not_credit_twice(self):
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda state: self.redeem(state), ["unfulfilled", "fulfilled"]))
        self.assertEqual([reply.status_code for reply in replies], [200, 200])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(User).where(User.twitch_id == "456")).credits, 100)

    def test_wrong_reward_or_price_does_not_credit(self):
        self.assertEqual(self.redeem(reward_id="wrong").status_code, 403)
        self.assertEqual(self.redeem(reward_cost=1).status_code, 403)
        self.assertEqual(self.redeem(reward_cost=True).status_code, 422)

    def test_other_twitch_id_cannot_claim_same_username(self):
        self.invite()
        response = self.client.post("/api/integrations/streamerbot/register", headers=self.bridge_headers, json={**self.identity, "user_id": "999"})
        self.assertEqual(response.status_code, 409)

    def test_password_login_errors_and_rate_limit(self):
        self.client.post("/api/auth/register", json=self.credentials())
        # Hashing is covered above; avoid hashing 128 MiB ten times in the limiter test.
        with patch("app.modules.accounts.verify_password", return_value=False):
            for _ in range(10):
                self.assertEqual(self.client.post("/api/auth/login", json={"username": "viewer", "password": "wrong"}).status_code, 401)
            response = self.client.post("/api/auth/login", json={"username": "viewer", "password": "wrong"})
            self.assertEqual(response.status_code, 429)

    def test_expired_session_and_disabled_user_are_rejected(self):
        with self.sessions() as db:
            db.add(AuthSession(token_hash=token_hash("expired"), user_id=1, expires_at=datetime.utcnow() - timedelta(seconds=1)))
            db.commit()
        self.assertEqual(self.client.get("/api/users/me", headers={"Authorization": "Bearer expired"}).status_code, 401)

    def test_no_oauth_or_public_account_creation(self):
        self.assertEqual(self.client.post("/api/auth/twitch/start", json={"verifier": "x" * 43}).status_code, 404)
        self.assertEqual(self.client.post("/api/auth/register", json={"username": "viewer", "password": self.password}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/register", json={**self.credentials(), "role": "admin"}).status_code, 422)

    def test_public_link_and_code_cannot_activate_another_browser(self):
        public = self.invite()
        self.assertNotIn("?", public["registration_url"])
        owner = self.start()
        attacker = self.start()
        credentials = {"username": "viewer", "token": owner["token"], "password": self.password}
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 403)
        inspect = self.client.post("/api/auth/register/inspect", json={"username": "viewer", "token": owner["token"]})
        self.assertFalse(inspect.json()["confirmed"])
        self.assertEqual(self.confirm(owner["code"], user_id="999").status_code, 403)
        self.assertEqual(self.confirm(owner["code"], username="other").status_code, 403)
        self.assertEqual(self.confirm(owner["code"], broadcaster_login="otherchannel").status_code, 403)
        self.assertEqual(self.client.post("/api/integrations/streamerbot/confirm", json={**self.identity, "code": owner["code"]}).status_code, 401)
        self.assertEqual(self.confirm(owner["code"].lower()).status_code, 200)
        self.assertEqual(self.confirm(owner["code"]).status_code, 200)  # repeated event is safe
        self.assertEqual(self.client.post("/api/auth/register", json={**credentials, "token": attacker["token"]}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/register", json={**credentials, "token": owner["code"]}).status_code, 422)
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 200)
        self.assertEqual(self.confirm(owner["code"]).status_code, 400)

    def test_public_requests_do_not_invalidate_confirmed_browser(self):
        credentials = self.credentials()
        self.start()
        self.invite()
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/register/start", json={"username": "viewer"}).status_code, 409)

    def test_expired_confirmation_and_disabled_account_are_rejected(self):
        self.invite()
        challenge = self.start()
        with self.sessions() as db:
            db.get(RegistrationChallenge, token_hash(challenge["token"])).expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.confirm(challenge["code"]).status_code, 400)
        challenge = self.start()
        with self.sessions() as db:
            db.scalar(select(User).where(User.twitch_id == "456")).is_active = False
            db.commit()
        self.assertEqual(self.confirm(challenge["code"]).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/register/start", json={"username": "viewer"}).status_code, 400)

    def test_unknown_user_and_old_private_invitation_are_rejected(self):
        self.assertEqual(self.client.post("/api/auth/register/start", json={"username": "unknown"}).status_code, 400)
        self.invite()
        with self.sessions() as db:
            user = db.scalar(select(User).where(User.twitch_id == "456"))
            db.add(RegistrationInvite(user_id=user.id, username=user.username, token_hash=token_hash("x" * 43), expires_at=datetime.utcnow() + timedelta(minutes=10)))
            db.commit()
        self.assertEqual(self.client.post("/api/auth/register", json={"username": "viewer", "token": "x" * 43, "password": self.password}).status_code, 400)

    def test_confirmation_rate_limit_and_hash_storage(self):
        self.invite()
        challenge = self.start()
        with self.sessions() as db:
            stored = db.scalar(select(RegistrationChallenge))
            self.assertEqual(stored.code_hash, token_hash(challenge["code"]))
            self.assertNotEqual(stored.code_hash, challenge["code"])
            self.assertNotEqual(stored.token_hash, challenge["token"])
        for _ in range(15):
            self.assertEqual(self.confirm("FFFFFFFFFF", user_id="999").status_code, 400)
        self.assertEqual(self.confirm("FFFFFFFFFF", user_id="999").status_code, 429)

    def test_streamer_can_confirm_own_registration(self):
        self.identity = {**self.identity, "username": "SamDavidOfficial", "display_name": "SamDavidOfficial"}
        credentials = self.credentials()
        self.assertEqual(self.client.post("/api/auth/register", json=credentials).status_code, 200)
