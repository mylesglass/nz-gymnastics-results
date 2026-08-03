import json
import os
import tempfile

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import (
    _get_jwt_secret,
    create_token,
    decode_token,
    hash_password,
    seed_admin_user,
    verify_password,
)
from app.database import init_db
from app.models import Base, User
from app.main import app

client = TestClient(app)

TEST_PASSWORD = "test-admin-pw"
TEST_SECRET = "test-secret-for-tests-32chars-long!!!"


def _enable_auth():
    os.environ["ADMIN_PASSWORD"] = TEST_PASSWORD
    os.environ["JWT_SECRET"] = TEST_SECRET


def _disable_auth():
    os.environ.pop("ADMIN_PASSWORD", None)
    os.environ.pop("JWT_SECRET", None)


def _setup_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)
    import app.database as db_mod
    old_engine = db_mod.engine
    old_session = db_mod.SessionLocal
    db_mod.engine = engine
    db_mod.SessionLocal = TestSession
    return db_path, engine, TestSession, old_engine, old_session


def _teardown_db(db_path, old_engine, old_session):
    import app.database as db_mod
    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestHashVerify:
    def test_round_trip(self):
        h = hash_password("hello123")
        assert verify_password("hello123", h)

    def test_wrong_password(self):
        h = hash_password("correct")
        assert not verify_password("wrong", h)

    def test_different_hashes_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestToken:
    def test_create_and_decode(self):
        token = create_token("alice", "admin")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "alice"
        assert payload["role"] == "admin"

    def test_expired_token(self):
        import datetime as dt
        secret = _get_jwt_secret()
        payload = {
            "sub": "alice",
            "role": "member",
            "iat": dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10),
            "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3),
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        assert decode_token(token) is None

    def test_bad_signature(self):
        token = jwt.encode({"sub": "alice", "role": "admin"}, "wrong-secret", algorithm="HS256")
        assert decode_token(token) is None


class TestSeedAdmin:
    def test_creates_admin(self):
        _enable_auth()
        db_path, engine, TestSession, old_engine, old_session = _setup_db()
        try:
            init_db()
            result = seed_admin_user()
            assert result == "admin"
            sess = TestSession()
            user = sess.query(User).filter(User.username == "admin").first()
            assert user is not None
            assert user.role == "admin"
            assert verify_password(TEST_PASSWORD, user.hashed_password)
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)
            _disable_auth()

    def test_idempotent(self):
        _enable_auth()
        db_path, engine, TestSession, old_engine, old_session = _setup_db()
        try:
            init_db()
            seed_admin_user()
            seed_admin_user()
            sess = TestSession()
            count = sess.query(User).filter(User.username == "admin").count()
            assert count == 1
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)
            _disable_auth()

    def test_custom_username(self):
        _enable_auth()
        os.environ["ADMIN_USERNAME"] = "superadmin"
        db_path, engine, TestSession, old_engine, old_session = _setup_db()
        try:
            init_db()
            seed_admin_user()
            sess = TestSession()
            user = sess.query(User).filter(User.username == "superadmin").first()
            assert user is not None
            assert user.role == "admin"
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)
            os.environ.pop("ADMIN_USERNAME", None)
            _disable_auth()

    def test_skips_when_disabled(self):
        _disable_auth()
        db_path, engine, _, old_engine, old_session = _setup_db()
        try:
            init_db()
            result = seed_admin_user()
            assert result is None
        finally:
            _teardown_db(db_path, old_engine, old_session)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


class TestAuthAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        _enable_auth()
        self.db_path, self.engine, TestSession, self.old_engine, self.old_session = _setup_db()
        import app.database as db_mod
        init_db()
        seed_admin_user()
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)
        _disable_auth()

    def test_auth_status_configured(self):
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert "user" not in data

    def test_auth_status_with_token(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = resp.json()["access_token"]
        resp2 = client.get("/api/auth/status", headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_login_success(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        # Token should be valid
        assert decode_token(data["access_token"]) is not None

    def test_login_wrong_password(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 401

    def test_login_when_disabled(self):
        _disable_auth()
        try:
            resp = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
            assert resp.status_code == 400
        finally:
            _enable_auth()

    def test_register_user(self):
        # Login as admin
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        # Register a member
        resp = client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "bob-pw", "role": "member"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "bob"
        assert data["role"] == "member"
        assert "id" in data

    def test_register_duplicate(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        resp = client.post(
            "/api/auth/register",
            json={"username": "admin", "password": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_register_requires_admin(self):
        # Register a member user first
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        admin_token = login.json()["access_token"]
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "alice-pw", "role": "member"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Login as member
        login2 = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pw"})
        member_token = login2.json()["access_token"]
        # Try to register another user (should fail)
        resp = client.post(
            "/api/auth/register",
            json={"username": "charlie", "password": "x"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403

    def test_register_no_token(self):
        resp = client.post(
            "/api/auth/register",
            json={"username": "charlie", "password": "x"},
        )
        assert resp.status_code == 401

    def test_list_users(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        resp = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["username"] == "admin"

    def test_list_users_forbidden_for_member(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        admin_token = login.json()["access_token"]
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "alice-pw", "role": "member"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        login2 = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pw"})
        member_token = login2.json()["access_token"]
        resp = client.get("/api/auth/users", headers={"Authorization": f"Bearer {member_token}"})
        assert resp.status_code == 403

    def test_reset_password(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        # Create a user
        reg = client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "bob-pw", "role": "member"},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = reg.json()["id"]
        # Reset password
        resp = client.post(
            f"/api/auth/users/{user_id}/reset-password",
            json={"password": "new-pw"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Login with new password
        resp2 = client.post("/api/auth/login", json={"username": "bob", "password": "new-pw"})
        assert resp2.status_code == 200

    def test_delete_user(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        reg = client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "bob-pw", "role": "member"},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = reg.json()["id"]
        resp = client.delete(
            f"/api/auth/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Verify removed
        users = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
        assert all(u["id"] != user_id for u in users)

    def test_cannot_delete_self(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        data = login.json()
        token = data["access_token"]
        users = client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"}).json()
        admin_id = users[0]["id"]
        resp = client.delete(
            f"/api/auth/users/{admin_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestRankingsEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self):
        _enable_auth()
        self.db_path, self.engine, TestSession, self.old_engine, self.old_session = _setup_db()
        import app.database as db_mod
        init_db()
        seed_admin_user()
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)
        _disable_auth()

    def test_admin_can_access(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        token = login.json()["access_token"]
        resp = client.get("/api/rankings?year=2026&step=STEP+10&discipline=WAG", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_member_can_access(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        admin_token = login.json()["access_token"]
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "alice-pw", "role": "member"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        login2 = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pw"})
        member_token = login2.json()["access_token"]
        resp = client.get("/api/rankings?year=2026&step=STEP+10&discipline=WAG", headers={"Authorization": f"Bearer {member_token}"})
        assert resp.status_code == 200

    def test_unauthenticated_cannot_access(self):
        resp = client.get("/api/rankings")
        assert resp.status_code == 401


class TestPermissions:
    @pytest.fixture(autouse=True)
    def setup(self):
        _enable_auth()
        self.db_path, self.engine, TestSession, self.old_engine, self.old_session = _setup_db()
        import app.database as db_mod
        init_db()
        seed_admin_user()
        self.admin_token = client.post(
            "/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
        ).json()["access_token"]
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)
        _disable_auth()

    def _register_member(self, username: str = "alice", permissions: list[str] | None = None):
        body: dict = {"username": username, "password": "alice-pw", "role": "member"}
        if permissions is not None:
            body["permissions"] = permissions
        resp = client.post(
            "/api/auth/register",
            json=body,
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def _member_token(self, username: str = "alice"):
        login = client.post("/api/auth/login", json={"username": username, "password": "alice-pw"})
        assert login.status_code == 200
        return login.json()

    def test_member_default_permissions(self):
        data = self._register_member()
        assert data["permissions"] == ["rankings.national"]

    def test_admin_permissions(self):
        login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        data = login.json()
        assert data["permissions"] == ["rankings.national", "rankings.wellington"]

    def test_register_with_custom_permissions(self):
        data = self._register_member(permissions=["rankings.wellington"])
        assert data["permissions"] == ["rankings.wellington"]

    def test_register_filters_unknown_permissions(self):
        data = self._register_member(permissions=["rankings.wellington", "bogus"])
        assert data["permissions"] == ["rankings.wellington"]

    def test_national_access_with_default_member(self):
        self._register_member()
        token = self._member_token()["access_token"]
        resp = client.get(
            "/api/rankings?year=2026&step=STEP+10&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_wellington_denied_without_permission(self):
        self._register_member()
        token = self._member_token()["access_token"]
        resp = client.get(
            "/api/rankings/wellington?year=2026&step=STEP+10&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_wellington_allowed_with_permission(self):
        self._register_member(permissions=["rankings.wellington"])
        token = self._member_token()["access_token"]
        resp = client.get(
            "/api/rankings/wellington?year=2026&step=STEP+10&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_steps_allowed_with_either_permission(self):
        self._register_member(permissions=["rankings.wellington"])
        token = self._member_token()["access_token"]
        resp = client.get(
            "/api/rankings/steps?year=2026&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_intents_denied_without_wellington(self):
        self._register_member()
        token = self._member_token()["access_token"]
        resp = client.get(
            "/api/wellington/intents?year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_bypasses_permission_checks(self):
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
        ).json()["access_token"]
        resp = client.get(
            "/api/rankings/wellington?year=2026&step=STEP+10&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_update_permissions_endpoint(self):
        self._register_member()
        users = client.get(
            "/api/auth/users", headers={"Authorization": f"Bearer {self.admin_token}"}
        ).json()
        alice = next(u for u in users if u["username"] == "alice")
        resp = client.patch(
            f"/api/auth/users/{alice['id']}/permissions",
            json={"permissions": ["rankings.wellington"]},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["permissions"] == ["rankings.wellington"]
        token = self._member_token()["access_token"]
        wellington = client.get(
            "/api/rankings/wellington?year=2026&step=STEP+10&discipline=WAG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert wellington.status_code == 200

    def test_me_returns_permissions(self):
        self._register_member()
        data = self._member_token()["access_token"]
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data}"})
        assert resp.status_code == 200
        assert resp.json()["permissions"] == ["rankings.national"]
