"""Tests for app.fix_apparatus (normalising un-resolvable apparatus labels)."""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_session
from app.fix_apparatus import _fix_rows
from app.models import Base, Event, LongScore


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


def _add_score(session, apparatus: str, rank: int | None = None) -> None:
    ev = Event(name="Meet", start_date="2025-03-01", end_date="2025-03-01", discipline="WAG", year=2025)
    session.add(ev)
    session.flush()
    session.add(LongScore(
        event_id=ev.id,
        event_name="Meet",
        gymnast_name="Ana",
        gnz_id="G-1",
        club_name="Capital Gymnastics",
        discipline="WAG",
        level_category="STEP 8",
        apparatus=apparatus,
        pass_number=1,
        pass_final_score=11.0,
        apparatus_rank=rank,
        round_type="All Around",
    ))
    session.commit()


class TestFixApparatus:
    def test_dry_run_relabels_and_reverts(self):
        session = get_session()
        try:
            _add_score(session, "All-around", rank=1)
            _add_score(session, "VT", rank=2)
        finally:
            session.close()

        stats = _fix_rows(get_session(), apply=False)
        assert stats["rows"] == 1

        session = get_session()
        try:
            rows = session.query(LongScore).all()
            assert {r.apparatus for r in rows} == {"All-around", "VT"}
        finally:
            session.close()

    def test_apply_normalises_and_clears_rank(self):
        session = get_session()
        try:
            _add_score(session, "All-around", rank=1)
            _add_score(session, "All-Around | Under", rank=3)
            _add_score(session, "VT", rank=2)
        finally:
            session.close()

        stats = _fix_rows(get_session(), apply=True)
        assert stats["rows"] == 2

        session = get_session()
        try:
            rows = session.query(LongScore).all()
            relabelled = [r for r in rows if r.apparatus == ""]
            assert len(relabelled) == 2
            assert all(r.apparatus_rank is None for r in relabelled)
            vt = next(r for r in rows if r.apparatus == "VT")
            assert vt.apparatus_rank == 2
        finally:
            session.close()

    def test_idempotent(self):
        session = get_session()
        try:
            _add_score(session, "All-around", rank=1)
        finally:
            session.close()

        _fix_rows(get_session(), apply=True)
        stats = _fix_rows(get_session(), apply=True)
        assert stats["rows"] == 0
