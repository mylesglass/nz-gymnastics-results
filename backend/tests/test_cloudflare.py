"""Tests for the Cloudflare analytics fetch + admin summary endpoint."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import seed_admin_user
from app.cloudflare import (
    _parse_breakdown,
    build_breakdown_query,
    build_daily_query,
    is_configured,
    parse_zone_response,
)
from app.database import init_db
from app.main import app
from app.models import Base

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


class TestCloudflareConfig:
    def test_not_configured_by_default(self):
        os.environ.pop("CLOUDFLARE_ZONE_ID", None)
        os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        assert is_configured() is False

    def test_configured_when_both_env_vars_set(self):
        os.environ["CLOUDFLARE_ZONE_ID"] = "abc123"
        os.environ["CLOUDFLARE_API_TOKEN"] = "tok"
        try:
            assert is_configured() is True
        finally:
            os.environ.pop("CLOUDFLARE_ZONE_ID", None)
            os.environ.pop("CLOUDFLARE_API_TOKEN", None)

    def test_configured_requires_both(self):
        os.environ["CLOUDFLARE_ZONE_ID"] = "abc123"
        os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        try:
            assert is_configured() is False
        finally:
            os.environ.pop("CLOUDFLARE_ZONE_ID", None)


class TestCloudflareQueries:
    def test_daily_query_uses_zone_and_range(self):
        q = build_daily_query("zone123", 7)
        assert 'zoneTag: "zone123"' in q
        assert "httpRequests1dGroups" in q
        assert "date_geq" in q
        assert "uniques" in q

    def test_breakdown_query_groups_by_country_and_status(self):
        q = build_breakdown_query("zone123", 7)
        assert "httpRequestsAdaptiveGroups" in q
        assert "clientCountryName" in q
        assert "edgeResponseStatus" in q
        assert "topPaths" in q
        assert "clientRequestPath" in q
        assert "cacheStatus" in q
        assert "deviceType" in q
        assert "clientDeviceType" in q
        assert "hourly" in q
        assert "datetimeHour" in q


class TestCloudflareParse:
    def test_parse_zone_response(self):
        data = {
            "data": {
                "viewer": {
                    "zones": [{
                        "httpRequests1dGroups": [
                            {
                                "dimensions": {"date": "2026-08-13"},
                                "sum": {"requests": 100, "bytes": 50000,
                                        "cachedRequests": 80, "cachedBytes": 40000,
                                        "threats": 2},
                                "uniq": {"uniques": 30},
                            },
                            {
                                "dimensions": {"date": "2026-08-14"},
                                "sum": {"requests": 200, "bytes": 100000,
                                        "cachedRequests": 160, "cachedBytes": 80000,
                                        "threats": 0},
                                "uniq": {"uniques": 45},
                            },
                        ],
                    }]
                }
            }
        }
        summary = parse_zone_response(data, 7)
        assert summary["configured"] is True
        assert summary["days"] == 7
        assert summary["totals"]["requests"] == 300
        assert summary["totals"]["bytes"] == 150000
        assert summary["totals"]["unique_visitors"] == 75
        assert summary["totals"]["threats"] == 2
        # 120 of 150 KB were served from cache.
        assert summary["totals"]["cache_hit_ratio"] == pytest.approx(0.8)
        assert len(summary["daily"]) == 2
        assert summary["daily"][0]["date"] == "2026-08-13"

    def test_parse_breakdown(self):
        view = {
            "topCountries": [
                {"count": 250, "dimensions": {"clientCountryName": "NZ"}},
                {"count": 50, "dimensions": {"clientCountryName": "AU"}},
            ],
            "statusCodes": [
                {"count": 270, "dimensions": {"edgeResponseStatus": 200}},
                {"count": 30, "dimensions": {"edgeResponseStatus": 404}},
            ],
            "topPaths": [
                {"count": 180, "dimensions": {"clientRequestPath": "/results"}},
                {"count": 120, "dimensions": {"clientRequestPath": "/rankings"}},
            ],
            "cacheStatus": [
                {"count": 200, "dimensions": {"cacheStatus": "HIT"}},
                {"count": 100, "dimensions": {"cacheStatus": "DYNAMIC"}},
            ],
            "deviceType": [
                {"count": 210, "dimensions": {"clientDeviceType": "mobile"}},
                {"count": 90, "dimensions": {"clientDeviceType": "desktop"}},
            ],
            "hourly": [
                {"count": 60, "dimensions": {"datetimeHour": "2026-08-14T09:00:00Z"}},
                {"count": 40, "dimensions": {"datetimeHour": "2026-08-14T09:00:00Z"}},
                {"count": 10, "dimensions": {"datetimeHour": "2026-08-14T14:00:00Z"}},
            ],
        }
        b = _parse_breakdown(view)
        assert b["top_countries"][0] == {"country": "NZ", "requests": 250}
        assert b["status_codes"][0] == {"code": 200, "requests": 270}
        assert b["top_paths"][0] == {"name": "/results", "count": 180}
        assert b["cache_status"][0] == {"name": "HIT", "count": 200}
        assert b["device_type"][0] == {"name": "mobile", "count": 210}
        assert len(b["hourly"]) == 24
        assert b["hourly"][9]["requests"] == 100
        assert b["hourly"][14]["requests"] == 10


class TestCloudflareAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        _enable_auth()
        self.db_path, self.engine, TestSession, self.old_engine, self.old_session = _setup_db()
        init_db()
        seed_admin_user()
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)
        _disable_auth()
        os.environ.pop("CLOUDFLARE_ZONE_ID", None)
        os.environ.pop("CLOUDFLARE_API_TOKEN", None)

    def test_summary_returns_not_configured(self):
        token = _admin_token()
        resp = client.get("/api/admin/cloudflare/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["days"] == 30
        assert data["totals"] is None
        assert data["daily"] == [] and data["top_countries"] == [] and data["status_codes"] == []
        assert data["top_paths"] == [] and data["cache_status"] == [] and data["device_type"] == []
        assert data["hourly"] == []

    def test_summary_requires_admin(self):
        token = _member_token()
        resp = client.get("/api/admin/cloudflare/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_summary_no_token(self):
        resp = client.get("/api/admin/cloudflare/summary")
        assert resp.status_code == 401

    def test_summary_clamps_days(self):
        token = _admin_token()
        resp = client.get(
            "/api/admin/cloudflare/summary",
            params={"days": 12345},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["days"] == 30
