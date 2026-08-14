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
DATA_DIR_2025 = HERE.parent.parent / "data-collection" / "2025"

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
        assert data["gymnast_count"] == 269
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

    def test_upload_surfaces_collision_warnings(self):
        # manawatu-wag_2025.json contains two Madison Lynches (different GNZ
        # IDs) at the same event plus a reused ID across two names. The upload
        # response must surface these as warnings.
        path = DATA_DIR_2025 / "manawatu-wag_2025.json"
        if not path.exists():
            pytest.skip("manawatu-wag_2025.json not found")

        with open(path, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("manawatu-wag_2025.json", f, "application/json")})
        assert resp.status_code == 200
        data = resp.json()
        warnings = data.get("warnings", [])

        same_name = [w for w in warnings if w["type"] == "same_name_multiple_ids"]
        assert any(w["name"] == "Madison Lynch" and set(w["gnz_ids"]) == {"249317", "716561"}
                   for w in same_name)

        same_id = [w for w in warnings if w["type"] == "same_id_multiple_names"]
        assert any(w["gnz_id"] == "779330" and {"Avery Monaghan", "Mackenzie Hutton-Reardon"}.issubset(set(w["names"]))
                   for w in same_id)

    def test_upload_replaces_all_duplicate_copies(self):
        path = DATA_DIR / "hve-2026.json"
        if not path.exists():
            pytest.skip("hve-2026.json not found")

        # Simulate an event that was imported multiple times (stale duplicates
        # already in the DB). Re-uploading the same competition must clear them
        # all, not just the first match.
        import app.database as db_mod

        from app.models import Event

        session = db_mod.SessionLocal()
        try:
            for _ in range(3):
                session.add(
                    Event(
                        name="HVG Elementary Competition 2026",
                        start_date="2026-05-23",
                        end_date="2026-05-23",
                        discipline="WAG+MAG",
                        year=2026,
                    )
                )
            session.commit()
        finally:
            session.close()

        with open(path, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("hve-2026.json", f, "application/json")})
        assert resp.status_code == 200

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
        assert body["gymnast_count"] == 269
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

    def test_known_clubs(self):
        resp = client.get("/api/clubs/known")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert all({"name", "region"} <= set(item) for item in data)
        names = {item["name"] for item in data}
        assert "Capital Gymnastics" in names

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
        assert data[0]["gymnast_count"] == 269


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
        assert data["event"]["gymnast_count"] == 269
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
        from app.database import SessionLocal
        from app.models import LongScore

        session = SessionLocal()
        try:
            # Athletes who reached the mark at least once on some apparatus.
            # The endpoint must surface these as qualified specialists (≥ 2
            # competitions on the same apparatus) or greyed "ghost" rows (1).
            rows = (
                session.query(LongScore.gnz_id)
                .filter(
                    LongScore.level_category == step,
                    LongScore.discipline == "WAG",
                    LongScore.gnz_id.isnot(None),
                    LongScore.gnz_id != "",
                    LongScore.pass_final_score.isnot(None),
                )
                .group_by(LongScore.gnz_id, LongScore.apparatus, LongScore.event_id)
                .having(func.max(LongScore.pass_final_score) >= 11.0)
                .all()
            )
            return sorted({g for (g,) in rows})
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
        for s in body["apparatus_specialists"]:
            assert "qualified" in s
            assert s["apparatus"], f"{s['name']} has no apparatus badges"
            for a in s["apparatus"]:
                assert a["app"]
                assert a["best"] >= 11.0
                assert a["count"] >= 1
                assert isinstance(a["competitions"], list)


class TestNationalRankingsApparatus:
    """Apparatus-qualifier section on the national /api/rankings endpoint."""

    _DATA = HERE.parent.parent / "data-collection" / "2025" / "wellington-wag_2025.json"

    def _upload(self):
        if not self._DATA.exists():
            pytest.skip("wellington-wag_2025.json not found")
        with open(self._DATA, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("wellington-wag_2025.json", f, "application/json")})
        assert resp.status_code == 200

    def test_apparatus_specialists_returned(self):
        self._upload()
        resp = client.get("/api/rankings?year=2025&step=STEP 8&discipline=WAG&qualifier=true")
        assert resp.status_code == 200
        body = resp.json()
        assert "apparatus_specialists" in body
        assert body["apparatus_qualifying_score"] == 11.0
        assert body["apparatus_qualifying_count"] == 2
        specialists = body["apparatus_specialists"]
        assert len(specialists) >= 1, "no STEP 8 apparatus specialists in test data"
        ranked_ids = {r["gnz_id"] for r in body["rankings"]}
        for s in specialists:
            assert s["gnz_id"] not in ranked_ids, f"{s['name']} is both ranked and a specialist"
            assert s["apparatus"], f"{s['name']} has no apparatus badges"
            for a in s["apparatus"]:
                assert a["app"]
                assert a["best"] >= 11.0
                assert a["count"] >= 1
                assert isinstance(a["competitions"], list)

    def test_specialists_empty_without_qualifier(self):
        # The specialist section is tied to the qualifier view: with the
        # qualifier filter off it stays empty.
        self._upload()
        resp = client.get("/api/rankings?year=2025&step=STEP 8&discipline=WAG")
        assert resp.status_code == 200
        assert resp.json()["apparatus_specialists"] == []

    def test_no_specialist_config_for_low_step(self):
        self._upload()
        resp = client.get("/api/rankings?year=2025&step=STEP 5&discipline=WAG&qualifier=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["apparatus_specialists"] == []
        assert body["apparatus_qualifying_score"] is None

    def test_threshold_count_round_merge_and_vault(self):
        # Deterministic: STEP 8 = 11.000 on 2 DISTINCT competitions, vault best
        # of the day, two round types of one competition merge to a single mark.
        from app.database import SessionLocal
        from app.models import Event, LongScore

        session = SessionLocal()
        try:
            def _event(i: int) -> int:
                ev = Event(
                    name=f"Meet {i}", start_date="2025-03-01", end_date="2025-03-02",
                    discipline="WAG", year=2025,
                )
                session.add(ev)
                session.flush()
                return ev.id

            def _score(eid, name, gnz, app, total, rt="All Around", pn=1, aa=None):
                session.add(LongScore(
                    event_id=eid, event_name=f"Meet {eid}", gymnast_name=name, gnz_id=gnz,
                    club_name="Clubs R Us", discipline="WAG", level_category="STEP 8",
                    apparatus=app, pass_number=pn, pass_final_score=total,
                    round_type=rt, aa_score=aa,
                ))

            e1, e2, e3 = _event(1), _event(2), _event(3)

            # "Dual" reaches 11.2/11.3 UB at two events -> qualified specialist.
            _score(e1, "Dual", "G100", "UB", 11.2)
            _score(e2, "Dual", "G100", "UB", 11.3)
            # "Once" reaches 11.1 UB at one event only -> greyed ghost.
            _score(e1, "Once", "G200", "UB", 11.1)
            # "SameDay": two round types of the same event merge to one mark.
            _score(e1, "SameDay", "G300", "UB", 11.0, rt="All Around")
            _score(e1, "SameDay", "G300", "UB", 11.6, rt="Apparatus Finals")
            # "VaultGirl": two passes a day; STEP 8 takes the best mark, and the
            # mark is reached at two distinct events -> qualified.
            _score(e1, "VaultGirl", "G500", "VT", 11.0, pn=1)
            _score(e1, "VaultGirl", "G500", "VT", 11.4, pn=2)
            _score(e2, "VaultGirl", "G500", "VT", 11.2, pn=1)
            _score(e2, "VaultGirl", "G500", "VT", 11.1, pn=2)
            # "AAQual" qualifies for the AA table AND reaches the mark -> with
            # the qualifier filter on, AA-qualified gymnasts are excluded from
            # the specialist section.
            _score(e1, "AAQual", "G400", "UB", 11.5, aa=43.0)
            _score(e2, "AAQual", "G400", "UB", 11.4, aa=43.5)
            session.commit()
        finally:
            session.close()

        resp = client.get("/api/rankings?year=2025&step=STEP 8&discipline=WAG&qualifier=true")
        assert resp.status_code == 200
        by_name = {s["name"]: s for s in resp.json()["apparatus_specialists"]}

        dual = by_name.get("Dual")
        assert dual is not None and dual["qualified"] is True
        assert next(a for a in dual["apparatus"] if a["app"] == "UB")["count"] == 2
        assert next(a for a in dual["apparatus"] if a["app"] == "UB")["best"] == 11.3

        once = by_name.get("Once")
        assert once is not None and once["qualified"] is False
        assert next(a for a in once["apparatus"] if a["app"] == "UB")["count"] == 1

        same = by_name.get("SameDay")
        assert same is not None
        same_ub = next(a for a in same["apparatus"] if a["app"] == "UB")
        assert same_ub["count"] == 1
        assert same_ub["best"] == 11.6

        vault = by_name.get("VaultGirl")
        assert vault is not None and vault["qualified"] is True
        vt = next(a for a in vault["apparatus"] if a["app"] == "VT")
        assert vt["count"] == 2
        assert vt["best"] == 11.4

        assert "AAQual" not in by_name


class TestGymnasts:
    def _seed(self, session) -> None:
        from app.models import Event, LongScore

        ev25 = Event(name="Meet 2025", start_date="2025-03-01", end_date="2025-03-02", discipline="WAG", year=2025)
        ev26 = Event(name="Meet 2026", start_date="2026-03-01", end_date="2026-03-02", discipline="WAG", year=2026)
        session.add_all([ev25, ev26])
        session.flush()
        session.add_all([
            LongScore(event_id=ev25.id, event_name="Meet 2025", gymnast_name="Alice", gnz_id="A-001", club_name="Affinity Gymnastics Academy", discipline="WAG", level_category="STEP 5", apparatus="VT", pass_number=1, pass_final_score=10.0, round_type="All Around"),
            LongScore(event_id=ev25.id, event_name="Meet 2025", gymnast_name="Bob", gnz_id="B-001", club_name="Levin Gymnastics Club", discipline="WAG", level_category="STEP 5", apparatus="FX", pass_number=1, pass_final_score=9.5, round_type="All Around"),
            LongScore(event_id=ev26.id, event_name="Meet 2026", gymnast_name="Alice", gnz_id="A-001", club_name="Affinity Gymnastics Academy", discipline="WAG", level_category="STEP 5", apparatus="UB", pass_number=1, pass_final_score=11.0, round_type="All Around"),
        ])
        session.commit()

    def test_year_filter(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        all_resp = client.get("/api/gymnasts")
        assert all_resp.status_code == 200
        assert {g["name"] for g in all_resp.json()} == {"Alice", "Bob"}

        resp25 = client.get("/api/gymnasts", params={"year": 2025})
        assert resp25.status_code == 200
        assert {g["name"] for g in resp25.json()} == {"Alice", "Bob"}

        resp26 = client.get("/api/gymnasts", params={"year": 2026})
        assert resp26.status_code == 200
        assert {g["name"] for g in resp26.json()} == {"Alice"}


class TestAthleteSlugEndpoints:
    def _seed(self, session) -> None:
        from app.athlete_identity import rebuild_athletes
        from app.models import Event, LongScore

        ev = Event(name="Meet 2026", start_date="2026-03-01", end_date="2026-03-02", discipline="WAG", year=2026)
        session.add(ev)
        session.flush()
        session.add_all([
            LongScore(event_id=ev.id, event_name="Meet 2026", gymnast_name="Eva Mcewan", gnz_id="999", club_name="OMNI", discipline="WAG", level_category="STEP 5", apparatus="VT", pass_number=1, pass_final_score=10.0, round_type="All Around"),
            LongScore(event_id=ev.id, event_name="Meet 2026", gymnast_name="Eva McEwan", gnz_id="999", club_name="OMNI", discipline="WAG", level_category="STEP 5", apparatus="UB", pass_number=1, pass_final_score=11.0, round_type="All Around"),
        ])
        session.commit()
        rebuild_athletes(session)

    def test_gymnasts_collapse_variants_and_expose_slug(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        resp = client.get("/api/gymnasts", params={"year": 2026})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Eva McEwan"
        assert items[0]["slug"]
        assert items[0]["slug"].startswith("a")

    def test_wide_all_by_slug_and_gnz_id_back_compat(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
            from app.models import Athlete
            slug = session.query(Athlete).first().slug
        finally:
            session.close()

        by_slug = client.get("/api/results/wide-all", params={"slug": slug}).json()
        rows = (by_slug.get("wag") or {}).get("rows", [])
        assert len(rows) == 1
        assert rows[0]["name"] == "Eva McEwan"
        assert rows[0]["slug"] == slug

        by_gnz = client.get("/api/results/wide-all", params={"gnz_id": "999"}).json()
        assert len((by_gnz.get("wag") or {}).get("rows", [])) == 1

    def test_medals_by_slug(self):
        from app.athlete_identity import rebuild_athletes
        from app.cache import cache
        from app.database import SessionLocal
        from app.models import Athlete, LongScore

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
            # Give the athlete an apparatus gold so medals return a row
            session.query(LongScore).update({"apparatus_rank": 1}, synchronize_session=False)
            session.commit()
            rebuild_athletes(session)
            slug = session.query(Athlete).first().slug
        finally:
            session.close()

        resp = client.get("/api/medals", params={"slug": slug})
        assert resp.status_code == 200
        gymnasts = resp.json()["gymnasts"]
        assert len(gymnasts) == 1
        assert gymnasts[0]["slug"] == slug
        assert gymnasts[0]["medals"]["g"] == 2

    def test_wide_all_fallback_name_uses_canonical(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
            from app.models import Athlete
            slug = session.query(Athlete).first().slug
        finally:
            session.close()

        # Year 1999 has no rows: the "gymnast not found" fallback name must
        # come from the athlete's canonical spelling, not a raw variant row.
        resp = client.get("/api/results/wide-all", params={"slug": slug, "year": 1999})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Eva McEwan"


class TestGymnastIdentity:
    def _seed(self, session) -> None:
        from app.athlete_identity import rebuild_athletes
        from app.models import Event, LongScore

        ev = Event(name="Meet 2026", start_date="2026-03-01", end_date="2026-03-02", discipline="WAG", year=2026)
        session.add(ev)
        session.flush()
        session.add_all([
            LongScore(event_id=ev.id, event_name="Meet 2026", gymnast_name="Eva Mcewan", gnz_id="999", club_name="OMNI", discipline="WAG", level_category="STEP 5", apparatus="VT", pass_number=1, pass_final_score=10.0, round_type="All Around"),
            LongScore(event_id=ev.id, event_name="Meet 2026", gymnast_name="Eva McEwan", gnz_id="999", club_name="OMNI", discipline="WAG", level_category="STEP 5", apparatus="UB", pass_number=1, pass_final_score=11.0, round_type="All Around"),
        ])
        session.commit()
        rebuild_athletes(session)

    def test_by_slug(self):
        from app.cache import cache
        from app.database import SessionLocal
        from app.models import Athlete

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
            slug = session.query(Athlete).first().slug
        finally:
            session.close()

        resp = client.get("/api/gymnast", params={"slug": slug})
        assert resp.status_code == 200
        g = resp.json()
        assert g["name"] == "Eva McEwan"
        assert g["slug"] == slug
        assert g["gnz_id"] == "999"
        assert g["club"] == "OMNI"

    def test_by_gnz_id(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        resp = client.get("/api/gymnast", params={"gnz_id": "999"})
        assert resp.status_code == 200
        g = resp.json()
        assert g["name"] == "Eva McEwan"
        assert g["slug"].startswith("a")

    def test_unknown_returns_null(self):
        from app.cache import cache
        from app.database import SessionLocal

        cache.clear()
        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        resp = client.get("/api/gymnast", params={"slug": "a0000000000"})
        assert resp.status_code == 200
        assert resp.json() is None

        resp = client.get("/api/gymnast")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_gnz_id_fallback_without_athlete_cluster(self):
        from app.cache import cache
        from app.database import SessionLocal
        from app.models import Event, LongScore

        cache.clear()
        session = SessionLocal()
        try:
            ev = Event(name="Meet 2026", start_date="2026-03-01", end_date="2026-03-02", discipline="WAG", year=2026)
            session.add(ev)
            session.flush()
            session.add(LongScore(event_id=ev.id, event_name="Meet 2026", gymnast_name="Una Clustered", gnz_id="777", club_name="Team X", discipline="WAG", level_category="STEP 5", apparatus="VT", pass_number=1, pass_final_score=10.0, round_type="All Around"))
            session.commit()
        finally:
            session.close()

        resp = client.get("/api/gymnast", params={"gnz_id": "777"})
        assert resp.status_code == 200
        g = resp.json()
        assert g["name"] == "Una Clustered"
        assert g["slug"] == ""
        assert g["club"] == "Team X"
