import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.auth import create_session, get_current_user, token_hash
from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.db.models import AdminAuditEvent, AuthSession, DiamondTransaction, InventoryItem, ProductPurchaseCounter, RegistrationChallenge, User, UserBooster
from app.modules.economy import lock_wallet
from test_economy import HubTestCase


class AdminActionTests(HubTestCase):
    password = "Admin-Pruefung-12345!"

    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        super().setUp()
        self.tokens = {}
        self.previous_key = settings.streamerbot_api_key
        settings.streamerbot_api_key = "isolated-admin-bridge-" + "x" * 32
        with self.sessions() as db:
            for index, (name, role) in enumerate([("owner", "super_admin"), ("viewer", "user"), ("admin", "admin"), ("support", "support_admin")], 2):
                user = User(id=index, username=name, display_name=name, twitch_id=str(index * 100),
                            password_hash=self.password_hash, role=role, credits=700)
                db.add(user)
                db.flush()
                self.tokens[index] = {"Authorization": "Bearer " + create_session(db, user)}
            db.add_all([InventoryItem(user_id=3, card_id=1, quantity=4), UserBooster(user_id=3, booster_id=1, quantity=2),
                ProductPurchaseCounter(user_id=3, booster_id=1, quantity=3),
                DiamondTransaction(user_id=3, amount=700, balance_after=700, reason="opening_balance", reference="fixture")])
            db.add(RegistrationChallenge(token_hash=token_hash("old-token" * 6), code_hash=token_hash("ABCDEF1234"),
                user_id=3, username="viewer", approved=True, expires_at=datetime.utcnow() + timedelta(hours=1)))
            db.commit()

    def tearDown(self):
        settings.streamerbot_api_key = self.previous_key
        super().tearDown()

    def action(self, action="reset_login", target=3, actor=2, key="action-0001", **extra):
        with self.sessions() as db:
            username = db.get(User, target).username if db.get(User, target) else "missing"
        body = {"action": action, "reason": "Vom Nutzer angeforderte Wiederherstellung", "confirmation": username, "password": self.password, **extra}
        return self.client.post(f"/api/admin/users/{target}/actions", headers={**self.tokens[actor], "Idempotency-Key": key}, json=body)

    def test_reset_preserves_assets_and_requires_new_twitch_confirmation(self):
        response = self.action()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["sessions_revoked"], 1)
        self.assertEqual(self.client.get("/api/users/me", headers=self.tokens[3]).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "viewer", "password": self.password}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json={"username": "viewer", "token": "old-token" * 6, "password": self.password}).status_code, 400)
        with self.sessions() as db:
            user = db.get(User, 3)
            self.assertEqual((user.twitch_id, user.credits, user.role), ("300", 700, "user"))
            self.assertIsNone(user.password_hash)
            self.assertIsNone(db.scalar(select(RegistrationChallenge).where(RegistrationChallenge.user_id == 3)))
            self.assertEqual(db.scalar(select(InventoryItem.quantity).where(InventoryItem.user_id == 3)), 4)
            self.assertEqual(db.scalar(select(UserBooster.quantity).where(UserBooster.user_id == 3)), 2)
            self.assertEqual(db.scalar(select(ProductPurchaseCounter.quantity).where(ProductPurchaseCounter.user_id == 3)), 3)
            self.assertEqual(db.scalar(select(func.count(DiamondTransaction.id))), 1)
        challenge = self.client.post("/api/auth/register/start", json={"username": "viewer"}).json()
        registration = {"username": "viewer", "token": challenge["token"], "password": "Neues-Passwort-123456"}
        self.assertEqual(self.client.post("/api/auth/register", json=registration).status_code, 403)
        confirmation = {"user_id": "300", "username": "viewer", "display_name": "Viewer", "broadcaster_login": settings.twitch_broadcaster_login, "code": challenge["code"]}
        bridge = {"X-Streamerbot-Key": settings.streamerbot_api_key}
        self.assertEqual(self.client.post("/api/integrations/streamerbot/confirm", json={**confirmation, "user_id": "999"}, headers=bridge).status_code, 403)
        self.assertEqual(self.client.post("/api/integrations/streamerbot/confirm", json=confirmation, headers=bridge).status_code, 200)
        registered = self.client.post("/api/auth/register", json=registration)
        self.assertEqual(registered.status_code, 200, registered.text)
        self.assertEqual(self.client.get("/api/users/me", headers={"Authorization": "Bearer " + registered.json()["token"]}).json()["diamonds"], 700)
        # A delayed retry of the original reset must not delete the new password.
        self.assertEqual(self.action().json(), response.json())
        with self.sessions() as db:
            self.assertTrue(verify_password(registration["password"], db.get(User, 3).password_hash))

    def test_permissions_password_confirmation_and_demo_are_enforced(self):
        for actor in (3, 5):
            self.assertEqual(self.action(actor=actor).status_code, 403)
        self.assertEqual(self.action(actor=4, target=2).status_code, 403)
        self.assertEqual(self.action(actor=4, action="change_role", role="admin").status_code, 403)
        self.assertEqual(self.action(password="wrong").status_code, 403)
        self.assertEqual(self.action(confirmation="other").status_code, 400)
        self.assertEqual(self.action(target=1).status_code, 400)
        self.assertEqual(self.action(target=999).status_code, 404)
        self.assertEqual(self.action(key="").status_code, 400)
        self.assertEqual(self.action(reason="  ").status_code, 422)
        self.assertEqual(self.action(actor=4).status_code, 200)

    def test_repeat_conflict_and_atomic_audit(self):
        first = self.action()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.action().json(), first.json())
        self.assertEqual(self.action(reason="Anderer Grund").status_code, 409)
        with self.sessions() as db:
            events = db.scalars(select(AdminAuditEvent)).all()
            self.assertEqual(len(events), 1)
            self.assertNotIn(self.password, events[0].details_json)
            self.assertNotIn("scrypt", events[0].details_json)
        self.assertEqual(self.client.get("/api/admin/audit", headers=self.tokens[5]).status_code, 403)
        result = self.client.get("/api/admin/audit?user_id=3&action=reset_login", headers=self.tokens[2])
        self.assertEqual(result.json()["total"], 1)
        self.assertEqual(result.json()["items"][0]["details"]["after"]["registered"], False)

    def test_block_unblock_and_session_revocation(self):
        self.assertEqual(self.action(action="block").status_code, 200)
        self.assertEqual(self.client.get("/api/users/me", headers=self.tokens[3]).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "viewer", "password": self.password}).status_code, 401)
        self.assertEqual(self.action(action="unblock", key="unblock-1").status_code, 200)
        self.assertEqual(self.client.get("/api/users/me", headers=self.tokens[3]).status_code, 401)
        login = self.client.post("/api/auth/login", json={"username": "viewer", "password": self.password})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.action(action="revoke_sessions", key="revoke-1").status_code, 200)
        self.assertEqual(self.client.get("/api/users/me", headers={"Authorization": "Bearer " + login.json()["token"]}).status_code, 401)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).password_hash, self.password_hash)

    def test_roles_last_owner_and_self_escalation(self):
        for action, extra in [("block", {}), ("reset_login", {}), ("change_role", {"role": "user"})]:
            self.assertEqual(self.action(target=2, action=action, **extra).status_code, 403)
        self.assertEqual(self.action(actor=4, target=4, action="change_role", role="super_admin").status_code, 403)
        self.assertEqual(self.action(action="change_role", role="support_admin").status_code, 200)
        self.assertEqual(self.client.get("/api/users/me", headers=self.tokens[3]).status_code, 401)
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).role, "support_admin")
            self.assertEqual(db.get(User, 2).role, "super_admin")

    def test_parallel_owners_cannot_disable_each_other(self):
        with self.sessions() as db:
            db.get(User, 4).role = "super_admin"
            db.commit()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda pair: self.action(action="block", actor=pair[0], target=pair[1]), [(2, 4), (4, 2)]))
        self.assertEqual(sorted(response.status_code for response in results), [200, 401])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(User.id)).where(User.role == "super_admin", User.is_active.is_(True))), 1)

    def test_action_failure_rolls_back_account_and_audit(self):
        with patch("app.modules.admin_actions.finish", side_effect=RuntimeError("simulated commit failure")):
            with self.assertRaises(RuntimeError):
                self.action()
        with self.sessions() as db:
            self.assertEqual(db.get(User, 3).password_hash, self.password_hash)
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id))), 0)
        self.assertEqual(self.client.get("/api/users/me", headers=self.tokens[3]).status_code, 200)

    def test_parallel_reset_with_same_key_writes_one_receipt(self):
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.action(), range(2)))
        self.assertTrue(all(response.status_code == 200 for response in results))
        self.assertEqual(results[0].json(), results[1].json())
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id))), 1)

    def test_login_cannot_recreate_session_after_racing_reset(self):
        def verify_then_reset(password, stored):
            result = verify_password(password, stored)
            self.assertEqual(self.action().status_code, 200)
            return result
        with patch("app.modules.accounts.verify_password", side_effect=verify_then_reset):
            response = self.client.post("/api/auth/login", json={"username": "viewer", "password": self.password})
        self.assertEqual(response.status_code, 401, response.text)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AuthSession.token_hash)).where(AuthSession.user_id == 3)), 0)

    def test_authenticated_waiting_purchase_rechecks_revoked_session(self):
        with self.sessions() as db:
            user = get_current_user(self.tokens[3]["Authorization"], db)
            self.assertEqual(self.action().status_code, 200)
            with self.assertRaises(HTTPException) as caught:
                lock_wallet(db, user)
            self.assertEqual(caught.exception.status_code, 401)
