"""Tests for activity tracking (middleware, page beacon, admin review)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import seed_admin_user
from app.database import init_db
from app.main import app
from app.models import ActivityLog, Base

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


def _admin_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _member_token():
    token = _admin_token()
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alice-pw", "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    resp2 = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pw"})
    return resp2.json()["access_token"]


class TestActivityAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        _enable_auth()
        self.db_path, self.engine, TestSession, self.old_engine, self.old_session = _setup_db()
        init_db()
        seed_admin_user()
        self.TestSession = TestSession
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)
        _disable_auth()

    def _rows(self) -> list[ActivityLog]:
        sess = self.TestSession()
        try:
            return sess.query(ActivityLog).all()
        finally:
            sess.close()

    def test_track_page_requires_auth(self):
        resp = client.post("/api/track/page", json={"path": "/rankings"})
        assert resp.status_code == 401
        assert self._rows() == []

    def test_track_page_logs_row(self):
        token = _admin_token()
        resp = client.post(
            "/api/track/page",
            json={"path": "/rankings?year=2024"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        rows = self._rows()
        assert len(rows) == 1
        row = rows[0]
        assert row.type == "page"
        assert row.username == "admin"
        assert row.path == "/rankings?year=2024"
        assert row.method == "GET"

    def test_track_page_not_double_logged(self):
        token = _admin_token()
        client.post("/api/track/page", json={"path": "/"}, headers={"Authorization": f"Bearer {token}"})
        rows = self._rows()
        assert len(rows) == 1
        assert rows[0].type == "page"

    def test_middleware_logs_authenticated_api_request(self):
        token = _member_token()
        resp = client.get(
            "/api/rankings/steps",
            params={"year": 2024, "discipline": "WAG"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        rows = [r for r in self._rows() if r.path == "/api/rankings/steps"]
        assert len(rows) == 1
        row = rows[0]
        assert row.type == "api"
        assert row.username == "alice"
        assert row.method == "GET"
        assert row.query is not None and "year=2024" in row.query
        assert row.status_code == 200
        assert row.duration_ms is not None

    def test_middleware_skips_anonymous(self):
        client.get("/api/events")
        assert self._rows() == []

    def test_activity_list_requires_admin(self):
        token = _member_token()
        resp = client.get("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_activity_list_no_token(self):
        resp = client.get("/api/admin/activity")
        assert resp.status_code == 401

    def test_activity_list_and_filter(self):
        token = _admin_token()
        client.post(
            "/api/track/page",
            json={"path": "/results"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(item["type"] == "page" and item["path"] == "/results" for item in data["items"])

        resp2 = client.get(
            "/api/admin/activity",
            params={"type": "api"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert all(item["type"] == "api" for item in resp2.json()["items"])
        assert not any(item["path"] == "/results" for item in resp2.json()["items"])

        resp3 = client.get(
            "/api/admin/activity",
            params={"user": "admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert all(item["username"] == "admin" for item in resp3.json()["items"])

    def test_activity_clear(self):
        token = _admin_token()
        client.post(
            "/api/track/page",
            json={"path": "/results"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.delete("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1
        assert self._rows() == []

    def test_activity_clear_requires_admin(self):
        token = _member_token()
        resp = client.delete("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_activity_items_have_no_personal_fields(self):
        token = _admin_token()
        client.post(
            "/api/track/page",
            json={"path": "/"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        item = resp.json()["items"][0]
        for field in ("client_ip", "user_agent"):
            assert field not in item
