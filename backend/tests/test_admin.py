import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.admin_setup import bootstrap_owner
from app.core.auth import create_session
from app.db.models import AdminAuditEvent, InventoryItem, User, UserBooster
from test_economy import HubTestCase


class AdminTests(HubTestCase):
    def setUp(self):
        super().setUp()
        with self.sessions() as db:
            owner = User(username="owner", display_name="Owner", role="super_admin", twitch_id="1234",
                         password_hash="never-return-this-hash", credits=800)
            pending = User(username="pending", display_name="Pending", twitch_id="9876", credits=100)
            db.add_all([owner, pending])
            db.flush()
            self.owner_id = owner.id
            self.admin_headers = {"Authorization": "Bearer " + create_session(db, owner)}
            db.add_all([InventoryItem(user_id=owner.id, card_id=1, quantity=3),
                        UserBooster(user_id=owner.id, booster_id=1, quantity=2)])
            db.commit()

    def test_all_admin_routes_require_real_session_and_current_role(self):
        routes = ["overview", "users", "users/2", "users/2/wallet", "users/2/inventory", "users/2/packs", "card-data/status"]
        for route in routes:
            self.assertEqual(self.client.get("/api/admin/" + route).status_code, 401)
            self.assertEqual(self.client.get("/api/admin/" + route, headers=self.headers).status_code, 403)
        with self.sessions() as db:
            db.get(User, 1).role = "super_admin"
            db.commit()
        self.assertEqual(self.client.get("/api/admin/users", headers=self.headers).status_code, 403)
        for role in ("support_admin", "admin", "super_admin", "user", "made_up"):
            with self.sessions() as db:
                db.get(User, self.owner_id).role = role
                db.commit()
            for route in routes:
                self.assertEqual(self.client.get("/api/admin/" + route, headers=self.admin_headers).status_code,
                                 200 if role in {"support_admin", "admin", "super_admin"} else 403, (role, route))
        with self.sessions() as db:
            user = db.get(User, self.owner_id)
            user.role, user.is_active = "super_admin", False
            db.commit()
        self.assertEqual(self.client.get("/api/admin/users", headers=self.admin_headers).status_code, 401)

    def test_filtered_pagination_and_explicit_safe_payloads(self):
        def read(query):
            response = self.client.get("/api/admin/users" + query, headers=self.admin_headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("password_hash", response.text)
            self.assertNotIn("never-return", response.text)
            self.assertNotIn("token", response.text)
            return response.json()
        self.assertEqual(read("?page_size=1&page=2")["items"][0]["id"], self.owner_id)
        self.assertEqual(read("?search=1234")["total"], 1)
        self.assertEqual(read("?search=OWNER")["total"], 1)
        self.assertEqual(read("?state=pending")["items"][0]["username"], "pending")
        self.assertEqual(read("?role=super_admin")["total"], 1)
        self.assertEqual(read("?search=%25")["total"], 0)
        self.assertEqual(read("?page=9")["items"], [])
        for query in ("?page=0", "?page_size=101", "?role=invalid", "?state=invalid"):
            self.assertEqual(self.client.get("/api/admin/users" + query, headers=self.admin_headers).status_code, 422)

    def test_account_totals_match_owned_records_and_missing_is_404(self):
        detail = self.client.get("/api/admin/users/2", headers=self.admin_headers).json()
        self.assertEqual((detail["points"], detail["cards"], detail["unique_cards"], detail["packs"]), (800, 3, 1, 2))
        self.assertEqual(self.client.get("/api/admin/users/2/inventory", headers=self.admin_headers).json()["items"],
                         [{"id": 1, "name": "Test", "quantity": 3, "variants": []}])
        self.assertEqual(self.client.get("/api/admin/users/2/packs", headers=self.admin_headers).json()["items"][0]["quantity"], 2)
        self.assertEqual(self.client.get("/api/admin/users/1/inventory", headers=self.admin_headers).json()["total"], 0)
        overview = self.client.get("/api/admin/overview", headers=self.admin_headers).json()
        self.assertEqual(overview, {"users": 3, "registered": 1, "pending": 1, "inactive": 0, "points": 1000, "cards": 3, "packs": 2})
        for suffix in ("", "/wallet", "/inventory", "/packs"):
            self.assertEqual(self.client.get("/api/admin/users/999" + suffix, headers=self.admin_headers).status_code, 404)

    def reset_owner(self):
        with self.sessions() as db:
            db.get(User, self.owner_id).role = "user"
            db.commit()

    def test_bootstrap_requires_registered_active_twitch_identity(self):
        self.reset_owner()
        for twitch_id in ("owner", "no-id", "000", "9876"):
            with self.sessions() as db, self.assertRaises(ValueError):
                bootstrap_owner(db, twitch_id)
        with self.sessions() as db:
            db.get(User, self.owner_id).is_active = False
            db.commit()
        with self.sessions() as db, self.assertRaises(ValueError):
            bootstrap_owner(db, "1234")

    def test_bootstrap_preview_rollback_and_audited_single_use(self):
        self.reset_owner()
        with self.sessions() as db:
            bootstrap_owner(db, "1234")
            db.rollback()
        with self.sessions() as db:
            self.assertEqual(db.get(User, self.owner_id).role, "user")
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id))), 0)
        with self.sessions() as db:
            bootstrap_owner(db, "1234")
            db.commit()
        with self.sessions() as db:
            event = db.scalar(select(AdminAuditEvent))
            self.assertEqual((event.actor_id, event.target_id, event.source), (None, self.owner_id, "local_cli"))
            self.assertEqual(json.loads(event.details_json), {"previous_role": "user", "role": "super_admin"})
            self.assertEqual(db.get(User, self.owner_id).credits, 800)
        with self.sessions() as db, self.assertRaises(ValueError):
            bootstrap_owner(db, "1234")

    def test_concurrent_bootstrap_creates_exactly_one_owner_receipt(self):
        self.reset_owner()
        def provision(_):
            with self.sessions() as db:
                try:
                    bootstrap_owner(db, "1234")
                    db.commit()
                    return True
                except ValueError:
                    return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(provision, range(2))), [False, True])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(AdminAuditEvent.id))), 1)
