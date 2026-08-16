"""Tests for the inline gymnast edit endpoint (PATCH /api/admin/scores/gymnast).

Covers the field updates (name / GNZ ID / club / division / round-type), the
case-insensitive name fallback, slug scoping (so same-name athletes in one event
edit independently), round-type/division scoping by the current displayed value,
and synchronous refresh of the materialized wide_rows store.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app import database as db_mod
from app import materialize
from app.athlete_identity import rebuild_athletes
from app.main import edit_gymnast_scores
from app.models import Athlete, Base, Event, LongScore
from app.schemas import GymnastEditRequest


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
        d_score=5.0,
        e_score=None,
        neutral_deductions=None,
        pass_final_score=total,
        apparatus_rank=None,
        aa_score=None,
        aa_rank=None,
        round_type=round_type,
    ))


def _seed(db_env) -> dict:
    """One WAG event with Eva (2 round types), Amelia, and two Simone Biles.

    Rows are seeded without athletes and ``rebuild_athletes`` builds the identity
    table with real content-addressed slugs (the endpoint re-runs it on every
    edit, so pre-seeding bogus Athlete rows would be destroyed).
    """
    _, TestSession = db_env
    session = TestSession()
    ev1 = Event(name="Tauranga Comp", start_date="2025-03-01", end_date="2025-03-01",
                discipline="WAG", year=2025, is_national=False, host_club="Tauranga")
    session.add(ev1)
    session.flush()

    # Eva: full AA + a finals pass (two round groups).
    for app in ("VT", "UB", "BB", "FX"):
        _score(session, ev1, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               app, 11.0, round_type="All Around")
    _score(session, ev1, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
           "FX", 10.0, round_type="Apparatus Finals")
    _score(session, ev1, "Amelia Smith", "1002", "Tauranga", "STEP 2", "WAG", "OVER",
           "VT", 10.0, round_type="All Around")
    # Two distinct people sharing a name in the same event.
    _score(session, ev1, "Simone Biles", "3001", "Tauranga", "STEP 2", "WAG", "",
           "VT", 12.0, round_type="All Around")
    _score(session, ev1, "Simone Biles", "3002", "Tauranga", "STEP 2", "WAG", "",
           "VT", 11.5, round_type="All Around")
    session.flush()
    rebuild_athletes(session)
    simone_a = session.query(Athlete).filter(Athlete.gnz_id == "3001").first()
    simone_b = session.query(Athlete).filter(Athlete.gnz_id == "3002").first()
    session.commit()
    ids = {"ev1": ev1.id,
           "simone_a_slug": simone_a.slug if simone_a else None,
           "simone_b_slug": simone_b.slug if simone_b else None}
    session.close()
    return ids


def _patch(ids: dict, **kw) -> dict:
    """Call the endpoint directly with a built GymnastEditRequest."""
    payload = {"event_id": ids["ev1"], "current_name": kw.pop("current_name", "Eva McEwan")}
    payload.update(kw)
    return edit_gymnast_scores(GymnastEditRequest(**payload), _auth="admin")


class TestInlineEdit:
    def test_update_name_and_club_case_insensitive(self, db_env):
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        result = _patch(ids, current_name="EVA MCEWAN", new_name="Eva McEwan-Smith", new_club="Other Club")
        assert result.updated == 5  # Eva's 5 passes
        rows = session.query(LongScore).filter(
            LongScore.event_id == ids["ev1"],
            LongScore.gymnast_name == "Eva McEwan-Smith",
        ).all()
        assert len(rows) == 5
        assert {r.club_name for r in rows} == {"Other Club"}
        session.close()

    def test_update_gnz_id(self, db_env):
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        result = _patch(ids, new_gnz_id="9999")
        assert result.updated == 5
        rows = session.query(LongScore).filter(
            LongScore.event_id == ids["ev1"],
            LongScore.gnz_id == "9999",
        ).all()
        assert len(rows) == 5
        session.close()

    def test_update_division_scoped_by_current(self, db_env):
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        result = _patch(ids, new_division="UNDER", current_division="OVER")
        assert result.updated == 5  # both of Eva's round groups carry OVER
        rows = session.query(LongScore).filter(
            LongScore.event_id == ids["ev1"],
            LongScore.gymnast_name == "Eva McEwan",
        ).all()
        assert len(rows) == 5
        assert {r.division for r in rows} == {"UNDER"}
        session.close()

    def test_update_round_type_scoped_by_current(self, db_env):
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        result = _patch(ids, new_round_type="All Around - Day 2", current_round_type="All Around")
        assert result.updated == 4  # only the AA group, not the finals pass
        rows = session.query(LongScore).filter(
            LongScore.event_id == ids["ev1"],
            LongScore.gymnast_name == "Eva McEwan",
        ).all()
        round_types = [r.round_type for r in rows]
        assert round_types.count("All Around - Day 2") == 4
        assert "Apparatus Finals" in round_types  # untouched
        session.close()

    def test_slug_scoping_edits_only_that_athlete(self, db_env):
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        result = _patch(ids, slug=ids["simone_a_slug"], current_name="Simone Biles", new_club="Puma")
        assert result.updated == 1  # only one of the two Simone Biles rows
        rows = session.query(LongScore).filter(
            LongScore.gnz_id.in_(["3001", "3002"]),
        ).all()
        by_id = {r.gnz_id: r.club_name for r in rows}
        assert by_id["3001"] == "Puma"
        assert by_id["3002"] == "Tauranga"
        session.close()

    def test_no_match_returns_zero(self, db_env):
        ids = _seed(db_env)
        result = _patch(ids, current_name="Nobody Here", new_club="X")
        assert result.updated == 0

    def test_name_edit_propagates_across_events(self, db_env):
        """A name edit must rename every row of the athlete (all events), or
        rebuild_athletes would see the old spelling still dominating elsewhere
        and silently revert it."""
        ids = _seed(db_env)
        _, TestSession = db_env
        session = TestSession()
        ev2 = Event(name="Second Comp", start_date="2025-05-01", end_date="2025-05-01",
                    discipline="WAG", year=2025, is_national=False, host_club="Tauranga")
        session.add(ev2)
        session.flush()
        _score(session, ev2, "Eva McEwan", "1001", "Tauranga", "STEP 2", "WAG", "OVER",
               "VT", 11.0, round_type="All Around")
        session.flush()
        rebuild_athletes(session)
        eva_slug = session.query(Athlete).filter(Athlete.gnz_id == "1001").first().slug
        session.commit()
        session.close()

        result = _patch(ids, slug=eva_slug, current_name="Eva McEwan", new_name="Eva McEwan Smith")
        assert result.updated == 6  # 5 rows in ev1 + 1 row in ev2

        session = TestSession()
        names = session.query(LongScore.gymnast_name).filter(LongScore.gnz_id == "1001").all()
        assert {n[0] for n in names} == {"Eva McEwan Smith"}
        session.close()

    def test_no_fields_raises_400(self, db_env):
        ids = _seed(db_env)
        with pytest.raises(HTTPException) as exc:
            _patch(ids)
        assert exc.value.status_code == 400

    def test_unknown_slug_raises_404(self, db_env):
        ids = _seed(db_env)
        with pytest.raises(HTTPException) as exc:
            _patch(ids, slug="a-nope", new_club="X")
        assert exc.value.status_code == 404

    def test_materialized_store_reflects_edit(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        _patch(ids, new_division="UNDER", current_division="OVER")
        data = materialize.get_wide_rows(event_id=ids["ev1"])
        assert data and "wag" in data
        eva_rows = [r for r in data["wag"]["rows"] if r.get("name") == "Eva McEwan"]
        assert eva_rows, "Eva's wide rows must exist in the store"
        assert {r.get("division") for r in eva_rows} == {"UNDER"}

    def test_store_row_names_follow_rename(self, db_env):
        ids = _seed(db_env)
        materialize.init_materialized()
        _patch(ids, new_name="Eva McEwan-Smith")
        data = materialize.get_wide_rows(event_id=ids["ev1"])
        assert data and "wag" in data
        names = {r.get("name") for r in data["wag"]["rows"]}
        assert "Eva McEwan-Smith" in names
        assert "Eva McEwan" not in names


class TestEditDuringInFlightRebuild:
    """An edit that lands while a full rebuild holds the rebuild lock used to
    leave the prebuilt store stale until the next background rebuild finished —
    so the table kept showing the old value. The event is flagged dirty and the
    read endpoints refresh it on demand (or live-pivot) instead."""

    def _store_divisions(self, ids, name="Eva McEwan"):
        data = materialize.get_wide_rows(event_id=ids["ev1"])
        return {
            r.get("division")
            for r in data["wag"]["rows"]
            if r.get("name") == name
        }

    def test_edit_during_inflight_rebuild_served_fresh(self, db_env):
        from fastapi import Response
        from app.main import get_results_wide

        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        assert self._store_divisions(ids) == {"OVER"}

        acquired = materialize._rebuild_lock.acquire(blocking=False)
        try:
            result = _patch(ids, new_division="UNDER", current_division="OVER")
            assert result.updated == 5
            # rebuild_event skipped (lock held) — event flagged dirty, store stale.
            assert ids["ev1"] in materialize.dirty_events()
            assert self._store_divisions(ids) == {"OVER"}
        finally:
            materialize._rebuild_lock.release()

        resp = get_results_wide(ids["ev1"], Response())
        assert self._store_divisions(ids) == {"UNDER"}
        assert ids["ev1"] not in materialize.dirty_events()

    def test_read_during_inflight_rebuild_live_pivots(self, db_env):
        """Reading while the lock is still held live-pivots rather than serving
        the stale store."""
        from fastapi import Response
        from app.main import get_results_wide

        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()

        acquired = materialize._rebuild_lock.acquire(blocking=False)
        try:
            _patch(ids, new_division="UNDER", current_division="OVER")
            resp = get_results_wide(ids["ev1"], Response())  # lock still held
            divs = {
                r.get("division")
                for r in resp["wag"]["rows"]
                if r.get("name") == "Eva McEwan"
            }
            assert divs == {"UNDER"}
        finally:
            materialize._rebuild_lock.release()

    def test_wide_all_during_inflight_rebuild_served_fresh(self, db_env):
        from fastapi import Response
        from app.main import get_all_results_wide

        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()

        acquired = materialize._rebuild_lock.acquire(blocking=False)
        try:
            _patch(ids, new_division="UNDER", current_division="OVER")
            assert ids["ev1"] in materialize.dirty_events()
        finally:
            materialize._rebuild_lock.release()

        resp = get_all_results_wide(Response(), year=2025)
        divs = {
            r.get("division")
            for r in resp["wag"]["rows"]
            if r.get("name") == "Eva McEwan"
        }
        assert divs == {"UNDER"}
        assert ids["ev1"] not in materialize.dirty_events()

    def test_full_rebuild_clears_dirty(self, db_env):
        """A completed fresh rebuild clears the dirty set — reads go back to the
        fast store path."""
        ids = _seed(db_env)
        materialize.init_materialized()
        materialize.rebuild_all()
        materialize.mark_event_dirty(ids["ev1"])
        materialize.rebuild_all()
        assert ids["ev1"] not in materialize.dirty_events()
