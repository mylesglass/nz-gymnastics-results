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