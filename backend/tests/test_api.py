import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.main import app

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent.parent / "data-collection" / "2026"

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Use a temporary SQLite database for each test."""
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

    yield

    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


class TestHealth:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestUpload:
    def test_upload_rejects_non_json(self):
        resp = client.post("/api/upload", files={"file": ("test.txt", b"hello", "text/plain")})
        assert resp.status_code == 400

    def test_upload_rejects_invalid_json(self):
        resp = client.post("/api/upload", files={"file": ("test.json", b"not json", "application/json")})
        assert resp.status_code == 400

    def test_upload_rejects_missing_top_level_key(self):
        data = json.dumps({"events": [{"name": "Test"}]})
        resp = client.post("/api/upload", files={"file": ("test.json", data.encode(), "application/json")})
        assert resp.status_code == 422
        body = resp.json()
        assert "errors" in body["detail"]

    def test_upload_hve_success(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")

        with open(path, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "HVG Elementary Competition 2026"
        assert data["discipline"] == "WAG+MAG"
        assert data["gymnast_count"] == 271
        assert data["score_count"] >= 1000
        assert data["id"] > 0

    def test_upload_replaces_existing(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")

        with open(path, "rb") as f:
            resp1 = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})
        assert resp1.status_code == 200

        with open(path, "rb") as f:
            resp2 = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})
        assert resp2.status_code == 200

        # Only 1 event in the DB after re-upload
        resp = client.get("/api/events")
        assert len(resp.json()) == 1


class TestImportUrl:
    def _load_hve(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")
        with open(path, "rb") as f:
            return json.loads(f.read())

    def test_empty_url_rejected(self, monkeypatch):
        monkeypatch.setattr("app.main.fetch_event_json", lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")))
        resp = client.post("/api/import-url", json={"url": "   "})
        assert resp.status_code == 400

    def test_invalid_url_rejected(self, monkeypatch):
        def fake(url):
            from app.scoreholder import ScoreholderFetchError

            raise ScoreholderFetchError("Could not find a Scoreholder event ID in the URL")

        monkeypatch.setattr("app.main.fetch_event_json", fake)
        resp = client.post("/api/import-url", json={"url": "https://example.com/foo"})
        assert resp.status_code == 502
        assert "event ID" in resp.json()["detail"]

    def test_fetch_error_surfaces(self, monkeypatch):
        from app.scoreholder import ScoreholderFetchError

        monkeypatch.setattr("app.main.fetch_event_json", lambda url: (_ for _ in ()).throw(ScoreholderFetchError("Scoreholder event not found (404)")))
        resp = client.post("/api/import-url", json={"url": "https://scoreholder.com/en/events/000000000000000000000000"})
        assert resp.status_code == 502
        assert resp.json()["detail"] == "Scoreholder event not found (404)"

    def test_import_url_success(self, monkeypatch):
        data = self._load_hve()
        monkeypatch.setattr("app.main.fetch_event_json", lambda url: data)

        resp = client.post("/api/import-url", json={"url": "https://scoreholder.com/en/events/66c6ae8a8026be8951720d23"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "HVG Elementary Competition 2026"
        assert body["discipline"] == "WAG+MAG"
        assert body["gymnast_count"] == 271
        assert body["id"] > 0

    def _unknown_club_payload(self, org_name="Totally Unknown Club XYZ"):
        return {
            "events": [{"name": "Test Event", "startDate": "2026-01-01"}],
            "eventOrganizations": [{"_id": "1", "name": org_name}],
            "eventParticipants": [{"_id": "p1", "organizationId": "1"}],
            "performanceIndividuals": [{"participantId": "p1", "unitId": "u1"}],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [{"_id": "u1", "name": "WAG Level 1", "type": "performance"}],
        }

    def test_import_url_unknown_clubs_409(self, monkeypatch):
        monkeypatch.setattr("app.main.fetch_event_json", lambda url: self._unknown_club_payload())

        resp = client.post("/api/import-url", json={"url": "https://scoreholder.com/en/events/66c6ae8a8026be8951720d23"})
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "Totally Unknown Club XYZ" in detail["unknown_clubs"]
        assert detail["suggestions"] == {}

    def test_import_url_409_includes_suggestion(self, monkeypatch):
        monkeypatch.setattr("app.main.fetch_event_json", lambda url: self._unknown_club_payload("Te Awamutu Gymsport"))

        resp = client.post("/api/import-url", json={"url": "https://scoreholder.com/en/events/66c6ae8a8026be8951720d23"})
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["suggestions"] == {"Te Awamutu Gymsport": "Te Awamutu Gymsports"}

    def test_import_url_allow_unknown_skips_409(self, monkeypatch):
        monkeypatch.setattr("app.main.fetch_event_json", lambda url: self._unknown_club_payload())

        resp = client.post("/api/import-url", json={"url": "https://scoreholder.com/en/events/66c6ae8a8026be8951720d23", "allow_unknown": True})
        assert resp.status_code == 200


class TestListEvents:
    def test_empty(self):
        resp = client.get("/api/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_after_upload(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")

        with open(path, "rb") as f:
            client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})

        resp = client.get("/api/events")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "HVG Elementary Competition 2026"
        assert data[0]["gymnast_count"] == 271


class TestGetResults:
    def test_404_for_missing(self):
        resp = client.get("/api/events/999/results")
        assert resp.status_code == 404

    def test_returns_long_format(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")

        with open(path, "rb") as f:
            upload_resp = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})
        event_id = upload_resp.json()["id"]

        resp = client.get(f"/api/events/{event_id}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert "columns" in data
        assert "rows" in data
        assert "event" in data
        assert data["event"]["gymnast_count"] == 271
        assert len(data["rows"]) >= 1000
        # Verify columns
        for col in ["gymnast_name", "apparatus", "pass_final_score"]:
            assert col in data["columns"]


class TestExport:
    def _upload(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")
        with open(path, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})
        return resp.json()["id"]

    def test_export_csv(self):
        event_id = self._upload()
        resp = client.get(f"/api/events/{event_id}/export/csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert resp.text.startswith("gnz-id")

    def test_export_xlsx(self):
        event_id = self._upload()
        resp = client.get(f"/api/events/{event_id}/export/xlsx")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_export_404(self):
        resp = client.get("/api/events/999/export/csv")
        assert resp.status_code == 404


class TestWellingtonRankings:
    _DATA = HERE.parent.parent / "data-collection" / "2025" / "wellington-wag_2025.json"

    def _upload(self):
        if not self._DATA.exists():
            pytest.skip("wellington-wag_2025.json not found")
        with open(self._DATA, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("wellington-wag_2025.json", f, "application/json")})
        assert resp.status_code == 200

    def _specialist_candidates(self, step: str = "STEP 8") -> list[str]:
        from collections import defaultdict

        from app.database import SessionLocal
        from app.models import LongScore

        session = SessionLocal()
        try:
            rows = (
                session.query(LongScore.gnz_id, LongScore.apparatus, func.max(LongScore.pass_final_score))
                .filter(
                    LongScore.level_category == step,
                    LongScore.discipline == "WAG",
                    LongScore.gnz_id.isnot(None),
                    LongScore.gnz_id != "",
                    LongScore.pass_final_score.isnot(None),
                )
                .group_by(LongScore.gnz_id, LongScore.apparatus)
                .having(func.max(LongScore.pass_final_score) >= 11.0)
                .all()
            )
            per_gymnast: dict[str, set[str]] = defaultdict(set)
            for gnz_id, apparatus, _score in rows:
                per_gymnast[gnz_id].add(apparatus)
            return [g for g, apps in per_gymnast.items() if len(apps) >= 2]
        finally:
            session.close()

    def test_not_ranked_returned(self):
        self._upload()
        resp = client.get("/api/rankings/wellington?year=2025&step=STEP 8&discipline=WAG")
        assert resp.status_code == 200
        body = resp.json()
        assert "not_ranked" in body
        for row in body["not_ranked"]:
            assert row["region"] == "Wellington"
            assert row["competitions"] >= 1
            assert len(row["scores"]) == 3
            assert len(row["competition_names"]) == 3
            assert "intent_submitted" in row
            assert "regional_count" in row
            assert "club_count" in row
            assert "away_count" in row
            assert row["regional_count"] + row["club_count"] + row["away_count"] == row["competitions"]
            assert row["why"]
            assert len(row["checks"]) >= 1
            for check in row["checks"]:
                assert "label" in check
                assert "met" in check

    def test_apparatus_specialists_returned(self):
        self._upload()
        candidates = self._specialist_candidates()
        assert len(candidates) >= 1, "no STEP 8 apparatus-specialist candidates in test data"

        from app.database import SessionLocal
        from app.models import WellingtonIntent

        session = SessionLocal()
        try:
            for gnz_id in candidates:
                session.add(WellingtonIntent(gnz_id=gnz_id, year=2025))
            session.commit()
        finally:
            session.close()

        resp = client.get("/api/rankings/wellington?year=2025&step=STEP 8&discipline=WAG")
        assert resp.status_code == 200
        body = resp.json()
        assert "apparatus_specialists" in body
        specialist_ids = [s["gnz_id"] for s in body["apparatus_specialists"]]
        assert any(g in specialist_ids for g in candidates)