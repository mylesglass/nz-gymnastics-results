"""Tests for the materialized data stores (STEP 30).

Exercises the store lifecycle against a temp source DB (same isolation pattern
as other test files: patch ``app.database.engine``/``SessionLocal``) and an
automatically-derived materialized store next to it. ``materialize.reset()``
clears the cached engine between tests.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app import database as db_mod
from app import materialize
from app.main import _build_event_marks
from app.models import Athlete, Base, Event, LongScore
from app.transformer import _compute_pivot


@pytest.fixture()
def db_env():
    """Patch the source DB to a temp file and reset the materialized store."""
    materialize.reset()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)
    old_engine, old_session = db_mod.engine, db_mod.SessionLocal
    db_mod.engine = engine
    db_mod.SessionLocal = TestSession
    yield engine, TestSession
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session
    materialize.reset()
    for suffix in ("", "-wal", "-shm"):
        p = Path(db_path).with_name(Path(db_path).stem + ".materialized.db" + suffix)
        if p.exists():
            os.unlink(p)
    os.unlink(db_path)


def _score(session, event: Event, name: str, gnz_id: str, club: str, step: str,
           discipline: str, division: str, apparatus: str, total: float | None,
           d_score: float | None = None, aa_score: float | None = None,
           round_type: str = "All Around", athlete_id: int | None = None) -> None:
    session.add(LongScore(
        event_id=event.id,
        athlete_id=athlete_id,
        event_name=event.name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline=discipline,
        level_category=step,
        division=division,
        apparatus=apparatus,
        pass_number=1,
        d_score=d_score,
        e_score=None,
        neutral_deductions=None,
        pass_final_score=total,
        apparatus_rank=None,
        aa_score=aa_score,
        aa_rank=None,
        round_type=round_type,
    ))


def _seed(db_env) -> dict:
    """Two non-national events (WAG + MAG) with a couple of gymnasts each."""
    _, TestSession = db_env
    session = TestSession()
    ev1 = Event(name="Tauranga Comp", start_date="2025-03-01", end_date="2025-03-01",
                discipline="WAG", year=2025, is_national=False, host_club="Tauranga")
    ev2 = Event(name="Auckland Champs", start_date="2025-04-01", end_date="2025-04-01",
                discipline="MAG", year=2025, is_national=False, host_club="Auckland")
    session.add_all([ev1, ev2])
    session.flush()

    # All three gymnasts are clustered (rebuild_athletes back-fills athlete_id
    # for every row in production, so a mixed None/int column never occurs).
    eva = Athlete(slug="a-eva", signature_hash="h1", canonical_name="Eva McEwan", gnz_id="1001")
    amelia = Athlete(slug="a-amelia", signature_hash="h2", canonical_name="Amelia Smith", gnz_id="1002")
    jack = Athlete(slug="a-jack", signature_hash="h3", canonical_name="Jack Moore", gnz_id="2001")
    session.add_all([eva, amelia, jack])
    session.flush()

    # WAG STEP 2 — full AA for Eva, partial for Amelia.
    for app in ("VT", "UB", "BB", "FX"):
        _score(session, ev1, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               app, 11.0 + {"VT": 0.5, "UB": 0.4, "BB": 0.3, "FX": 0.2}[app],
               d_score=5.0, aa_score=45.5, athlete_id=eva.id)
    _score(session, ev1, "Amelia Smith", "1002", "Tauranga", "STEP 2", "WAG", "OVER",
           "VT", 10.0, d_score=4.5, aa_score=None, athlete_id=amelia.id)
    _score(session, ev1, "Amelia Smith", "1002", "Tauranga", "STEP 2", "WAG", "OVER",
           "UB", 9.5, d_score=4.0, aa_score=None, athlete_id=amelia.id)

    # MAG Level 4 — one gymnast.
    for app in ("FX", "PH", "SR", "VT", "PB", "HB"):
        _score(session, ev2, "Jack Moore", "2001", "Auckland", "Level 4", "MAG", "",
               app, 12.0, d_score=5.5, aa_score=60.0, athlete_id=jack.id)
    session.commit()
    ids = {"ev1": ev1.id, "ev2": ev2.id, "eva_id": eva.id, "eva_slug": eva.slug}
    session.close()
    return ids


class TestStoreLifecycle:
    def test_store_created_next_to_source(self, db_env):
        engine, _ = db_env
        mat = materialize.init_materialized()
        assert mat is not None
        assert Path(mat.url.database).name == Path(engine.url.database).stem + ".materialized.db"

    def test_epoch_bumps_on_mark(self, db_env):
        materialize.init_materialized()
        e0 = materialize._meta_get("epoch")
        materialize.mark_needs_rebuild()
        assert materialize._meta_get("epoch") != e0
        assert materialize.needs_rebuild()

    def test_ready_and_needs_rebuild_after_rebuild(self, db_env):
        _seed(db_env)
        materialize.init_materialized()
        assert not materialize.is_ready()
        assert materialize.needs_rebuild()  # empty store always needs a build
        materialize.rebuild_all()
        st = materialize.status()
        assert st["ready"]
        assert not st["needs_rebuild"]
        assert not st["building"]
        assert st["last_rebuild_ms"] > 0


class TestRebuildEquivalence:
    def test_wide_rows_match_compute_pivot(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        session = db_env[1]()
        for eid in (ids["ev1"], ids["ev2"]):
            data = _compute_pivot(eid, session)
            stored = materialize.get_wide_rows(event_id=eid)
            assert set(stored) == set(data)  # same discipline sections
            for dk in data:
                fresh = {json.dumps(r, sort_keys=True) for r in data[dk]["rows"]}
                got = {json.dumps(r, sort_keys=True) for r in stored[dk]["rows"]}
                assert fresh == got
                assert stored[dk]["columns"] == data[dk]["columns"]

    def test_ranking_marks_match_build_event_marks(self, db_env):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        key = (2025, "WAG", "STEP 2", "")
        marks = materialize.get_ranking_marks(*key)
        assert marks is not None
        session = db_env[1]()
        rows = materialize._ranking_rows(session, 2025, "WAG", "STEP 2", "")
        athletes = {a.id: a for a in session.query(Athlete).all()}
        per_event, apparatus_events, meta_by_key = _build_event_marks(rows, "STEP 2", athletes)
        for a_key, meta in meta_by_key.items():
            if isinstance(a_key, int) and a_key in athletes:
                meta["slug"] = athletes[a_key].slug
        assert marks["per_event"] == per_event
        assert marks["apparatus_events"] == apparatus_events
        assert marks["meta_by_key"] == meta_by_key

    def test_ranking_marks_division_keys(self, db_env):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        # "" (unfiltered) and "OVER" both exist for WAG STEP 2.
        assert materialize.get_ranking_marks(2025, "WAG", "STEP 2", "") is not None
        assert materialize.get_ranking_marks(2025, "WAG", "STEP 2", "OVER") is not None
        assert materialize.get_ranking_marks(2025, "MAG", "Level 4", "") is not None
        assert materialize.get_ranking_marks(2024, "WAG", "STEP 2", "") is None

    def test_wide_rows_column_shapes(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        single = materialize.get_wide_rows(event_id=ids["ev1"])
        assert "event_name" not in single["wag"]["columns"]
        assert "event_name" not in single["wag"]["rows"][0]
        wide = materialize.get_wide_rows(event_id=ids["ev1"], include_event=True)
        assert wide["wag"]["columns"][0] == "event_name"
        assert all("event_name" in r for r in wide["wag"]["rows"])

    def test_wide_rows_filters(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        by_club = materialize.get_wide_rows(club="Auckland")
        assert set(by_club) == {"mag"}
        by_year = materialize.get_wide_rows(year=2025)
        assert set(by_year) == {"wag", "mag"}
        by_missing = materialize.get_wide_rows(year=2024)
        assert by_missing == {}


class TestRebuildLifecycle:
    def test_rebuild_idempotent(self, db_env):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        before = materialize.get_ranking_marks(2025, "WAG", "STEP 2", "")
        mat = materialize.init_materialized()
        with mat.connect() as conn:
            count = conn.execute(text("SELECT count(*) FROM wide_rows")).scalar()
        materialize.rebuild_all()
        after = materialize.get_ranking_marks(2025, "WAG", "STEP 2", "")
        assert after == before
        assert not materialize.needs_rebuild()
        with mat.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM wide_rows")).scalar() == count

    def test_failure_keeps_prior_version(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        prior = materialize.get_ranking_marks(2025, "WAG", "STEP 2", "")

        def boom(session):
            raise RuntimeError("mid-rebuild failure")

        monkeypatch.setattr(materialize, "_compute_marks_all", boom)
        # A pending mutation (the realistic trigger) leaves epoch > built_epoch.
        materialize.mark_needs_rebuild()
        with pytest.raises(RuntimeError):
            materialize.rebuild_all()
        # Prior version still served, needs_rebuild stays true, building cleared.
        assert materialize.get_ranking_marks(2025, "WAG", "STEP 2", "") == prior
        assert materialize.needs_rebuild()
        assert not materialize.status()["building"]

    def test_out_of_process_mutation_detected(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        assert not materialize.needs_rebuild()

        # Simulate a CLI mutation: write through a second connection, then mark
        # the store dirty (what cache.invalidate() does for every mutation path).
        engine = db_env[0]
        with engine.begin() as conn:
            conn.execute(text("UPDATE events SET name = 'Renamed Comp' WHERE id = :e"),
                         {"e": ids["ev1"]})
        materialize.mark_needs_rebuild()
        assert materialize.needs_rebuild()

        materialize.rebuild_all()
        assert not materialize.needs_rebuild()
        wide = materialize.get_wide_rows(event_id=ids["ev1"], include_event=True)
        assert wide["wag"]["rows"][0]["event_name"] == "Renamed Comp"

    def test_rebuild_event_inserts_sync(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        # Add a brand-new event that the full rebuild doesn't know about.
        session = db_env[1]()
        ev3 = Event(name="New Event", start_date="2025-05-01", end_date="2025-05-01",
                    discipline="WAG", year=2025, is_national=False, host_club="Tauranga")
        session.add(ev3)
        session.flush()
        _score(session, ev3, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               "VT", 12.0, d_score=5.0, aa_score=None)
        _score(session, ev3, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               "UB", 11.5, d_score=4.5, aa_score=None)
        _score(session, ev3, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               "BB", 11.0, d_score=4.0, aa_score=None)
        session.commit()

        materialize.rebuild_event(ev3.id)
        stored = materialize.get_wide_rows(event_id=ev3.id)
        assert "wag" in stored
        names = {r["name"] for r in stored["wag"]["rows"]}
        assert names == {"Eva McEwan"}

    def test_rebuild_event_skips_when_full_rebuild_running(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        # Hold the rebuild lock, then rebuild_event must no-op (return False)
        # rather than block — the caller falls back to live compute.
        acquired = materialize._rebuild_lock.acquire(blocking=False)
        try:
            assert materialize.rebuild_event(99999) is False  # returns without raising
        finally:
            if acquired:
                materialize._rebuild_lock.release()
        # When the lock is free the refresh succeeds and returns True.
        assert materialize.rebuild_event(99999) is False  # unknown event
        assert materialize.rebuild_event(1) is True


class TestStoreBackedEndpoints:
    """Store-backed endpoints must return output identical to live compute."""

    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def _live(self, monkeypatch, fn):
        monkeypatch.setenv("MATERIALIZED_READS", "0")
        try:
            return fn()
        finally:
            monkeypatch.delenv("MATERIALIZED_READS", raising=False)

    def test_rankings_store_equals_live(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        params = {"year": 2025, "step": "STEP 2", "discipline": "WAG"}
        store = client.get("/api/rankings", params=params).json()
        live = self._live(monkeypatch, lambda: client.get("/api/rankings", params=params).json())
        assert store == live

    def test_rankings_toggles_store_equals_live(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        for extra in ({"quota": "true"}, {"qualifier": "true"}, {"division": "OVER"}):
            params = {"year": 2025, "step": "STEP 2", "discipline": "WAG", **extra}
            store = client.get("/api/rankings", params=params).json()
            live = self._live(monkeypatch, lambda: client.get("/api/rankings", params=params).json())
            assert store == live, extra

    def test_apparatus_store_equals_live(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        params = {"year": 2025, "step": "Level 4", "discipline": "MAG"}
        store = client.get("/api/rankings/apparatus", params=params).json()
        live = self._live(monkeypatch, lambda: client.get("/api/rankings/apparatus", params=params).json())
        assert store == live

    def test_event_wide_store_equals_live(self, db_env, monkeypatch):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        store = client.get(f"/api/events/{ids['ev1']}/results/wide").json()
        live = self._live(monkeypatch, lambda: client.get(f"/api/events/{ids['ev1']}/results/wide").json())
        # Metadata + columns must match exactly; row order can differ (the store
        # sorts by event, the live pivot by SQL scan order) — the frontend sorts.
        assert store["event"] == live["event"]
        for key in set(store) & set(live) - {"event"}:
            assert store[key]["columns"] == live[key]["columns"]
            assert {json.dumps(r, sort_keys=True) for r in store[key]["rows"]} == \
                   {json.dumps(r, sort_keys=True) for r in live[key]["rows"]}
        assert set(store) == set(live)

    def test_wide_all_store_equals_live(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        store = client.get("/api/results/wide-all", params={"year": 2025}).json()
        live = self._live(monkeypatch, lambda: client.get("/api/results/wide-all", params={"year": 2025}).json())
        # Row order within/across events is deterministic in both paths, but
        # compare rows canonically to be robust to ordering ties.
        for key in ("wag", "mag"):
            if key in store or key in live:
                assert [json.dumps(r, sort_keys=True) for r in sorted(store[key]["rows"], key=lambda r: json.dumps(r, sort_keys=True))] == \
                       [json.dumps(r, sort_keys=True) for r in sorted(live[key]["rows"], key=lambda r: json.dumps(r, sort_keys=True))]
                assert store[key]["columns"] == live[key]["columns"]
        assert set(store) == set(live)

    def test_wide_all_by_slug_from_store(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        resp = client.get("/api/results/wide-all", params={"slug": ids["eva_slug"]})
        assert resp.status_code == 200
        body = resp.json()
        wag = body.get("wag", {})
        assert wag, body  # must NOT hit the name-only fallback
        assert {r["name"] for r in wag["rows"]} == {"Eva McEwan"}

    def test_wellington_store_equals_live(self, db_env, monkeypatch):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        params = {"year": 2025, "step": "Level 4", "discipline": "MAG"}
        store = client.get("/api/rankings/wellington", params=params).json()
        live = self._live(monkeypatch, lambda: client.get("/api/rankings/wellington", params=params).json())
        assert store == live

    def test_rebuild_status_endpoint(self, db_env):
        _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        client = self._client()
        resp = client.get("/api/admin/rebuild/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["needs_rebuild"] is False
        assert body["building"] is False
        assert body["last_rebuild_ms"] > 0
