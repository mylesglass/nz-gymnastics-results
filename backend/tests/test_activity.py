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
from app.models import ActivityLog, Base, TrafficDaily
from app.traffic import is_bot, normalize_path

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

    def _traffic(self) -> list[TrafficDaily]:
        sess = self.TestSession()
        try:
            return sess.query(TrafficDaily).all()
        finally:
            sess.close()

    def _traffic_for(self, path_group: str) -> TrafficDaily | None:
        sess = self.TestSession()
        try:
            return (
                sess.query(TrafficDaily)
                .filter(TrafficDaily.path_group == path_group)
                .first()
            )
        finally:
            sess.close()

    def test_track_page_anonymous_aggregated(self):
        resp = client.post("/api/track/page", json={"path": "/rankings?year=2024"})
        assert resp.status_code == 200
        assert self._rows() == []
        row = self._traffic_for("/rankings")
        assert row is not None
        assert row.kind == "page"
        assert row.anonymous is True
        assert row.count == 1

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
        traffic = self._traffic_for("/rankings")
        assert traffic is not None
        assert traffic.anonymous is False

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
        traffic = self._traffic_for("/api/rankings/steps")
        assert traffic is not None
        assert traffic.anonymous is False
        assert traffic.count == 1

    def test_middleware_aggregates_anonymous(self):
        client.get("/api/events")
        assert self._rows() == []
        traffic = self._traffic_for("/api/events")
        assert traffic is not None
        assert traffic.kind == "api"
        assert traffic.anonymous is True
        assert traffic.count == 1

    def test_middleware_skips_bots(self):
        client.get("/api/events", headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"})
        assert self._rows() == []
        assert self._traffic() == []

    def test_middleware_skips_health(self):
        client.get("/api/health")
        assert self._traffic() == []

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
        # created_at is serialized as UTC (Z suffix) so the browser renders the
        # viewer's local time, not a naive local-time misread.
        assert item["created_at"].endswith("Z")

    def test_activity_list_days_filter(self):
        token = _admin_token()
        client.post(
            "/api/track/page",
            json={"path": "/results"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.get(
            "/api/admin/activity",
            params={"days": 7},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert any(item["path"] == "/results" for item in resp.json()["items"])

    def test_activity_list_errors_filter(self):
        token = _admin_token()
        client.get("/api/events", headers={"Authorization": f"Bearer {token}"})
        client.get("/api/nonexistent-route", headers={"Authorization": f"Bearer {token}"})
        resp = client.get(
            "/api/admin/activity",
            params={"errors": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"], "expected at least one error row"
        assert all(item["status_code"] >= 400 for item in data["items"])
        assert any(item["path"] == "/api/nonexistent-route" for item in data["items"])
        # Without the flag, the same endpoint returns all rows (incl. 2xx).
        resp2 = client.get("/api/admin/activity", headers={"Authorization": f"Bearer {token}"})
        assert resp2.json()["total"] > data["total"]
        assert any(item["status_code"] < 400 for item in resp2.json()["items"])

    def test_activity_summary_requires_admin(self):
        token = _member_token()
        resp = client.get("/api/admin/activity/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_activity_summary_no_token(self):
        resp = client.get("/api/admin/activity/summary")
        assert resp.status_code == 401

    def test_activity_summary_shape_and_totals(self):
        token = _admin_token()
        member = _member_token()
        client.post(
            "/api/track/page",
            json={"path": "/results"},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.get("/api/events")
        client.get("/api/events", headers={"Authorization": f"Bearer {member}"})
        resp = client.get(
            "/api/admin/activity/summary",
            params={"days": 7},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["range_days"] == 7
        totals = data["totals"]
        assert totals["page_views"] >= 1
        assert totals["api_requests"] >= 1
        assert totals["auth_page_views"] >= 1
        assert totals["anon_api_requests"] >= 1
        assert totals["active_days"] >= 1
        assert data["daily_series"], "expected at least one daily point"
        assert 1 <= len(data["hourly_series"]) <= 24
        assert all(0 <= h["hour"] <= 23 for h in data["hourly_series"])
        assert any(p["path"] == "/results" for p in data["top_pages"])
        # The built-in admin account is excluded from the top-users chart so it
        # can't dominate; other users still appear.
        assert all(u["username"] != "admin" for u in data["top_users"])
        assert any(u["username"] == "alice" for u in data["top_users"])
        # Errors are computed but zero in this happy path.
        assert totals["errors"] >= 0

    def test_activity_summary_error_counting(self):
        token = _admin_token()
        client.get("/api/nonexistent-route")
        resp = client.get(
            "/api/admin/activity/summary",
            params={"days": 7},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        # The 404 itself was counted as an anonymous request, plus the summary
        # call is admin-authenticated and excluded; error count must include the 404.
        assert data["totals"]["errors"] >= 1

    def test_activity_summary_clamps_days(self):
        token = _admin_token()
        resp = client.get(
            "/api/admin/activity/summary",
            params={"days": 12345},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["range_days"] == 30


class TestTrafficNormalization:
    def test_normalize_numeric(self):
        assert normalize_path("/api/events/123/results/wide") == "/api/events/[id]/results/wide"
        assert normalize_path("/events/123") == "/events/[id]"

    def test_normalize_slug(self):
        assert normalize_path("/api/results/wide-all?slug=a1b2c3d4e5") == "/api/results/wide-all"

    def test_normalize_strips_query(self):
        assert normalize_path("/api/rankings?year=2024&step=STEP%201") == "/api/rankings"

    def test_normalize_keeps_club_paths(self):
        assert normalize_path("/club/Christchurch%20Gym%20Sports") == "/club/Christchurch%20Gym%20Sports"

    def test_normalize_hex_slug(self):
        assert normalize_path("/gymnast/a1b2c3d4e5") == "/gymnast/[slug]"

    def test_normalize_empty(self):
        assert normalize_path("") == "/"

    def test_is_bot(self):
        assert is_bot("Mozilla/5.0 (compatible; Googlebot/2.1)")
        assert is_bot("python-requests/2.31")
        assert is_bot("curl/8.0")
        assert not is_bot("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        assert not is_bot(None)
