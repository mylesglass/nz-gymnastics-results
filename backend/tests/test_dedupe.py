import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_session
from app.dedupe_events import dedupe_events
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


def make_event(session, name="Comp", scores=0) -> int:
    ev = Event(
        name=name,
        start_date="2025-03-01",
        end_date="2025-03-01",
        discipline="MAG",
        year=2025,
    )
    session.add(ev)
    session.flush()
    for i in range(scores):
        session.add(
            LongScore(
                event_id=ev.id,
                event_name=name,
                gymnast_name=f"G{i}",
                discipline="MAG",
                apparatus="FX",
            )
        )
    session.commit()
    return ev.id


class TestDedupeEvents:
    def test_no_duplicates_noop(self):
        session = get_session()
        try:
            make_event(session, scores=2)
        finally:
            session.close()

        report = dedupe_events(apply=False)
        assert report == {"groups": 0, "kept": 0, "removed": 0}

        session = get_session()
        try:
            assert session.query(Event).count() == 1
        finally:
            session.close()

    def test_dry_run_leaves_rows(self):
        session = get_session()
        try:
            make_event(session, scores=2)
            make_event(session, scores=2)
        finally:
            session.close()

        report = dedupe_events(apply=False)
        assert report["groups"] == 1
        assert report["removed"] == 1

        session = get_session()
        try:
            assert session.query(Event).count() == 2
        finally:
            session.close()

    def test_apply_keeps_richest_copy(self):
        session = get_session()
        try:
            poor_id = make_event(session, scores=1)
            rich_id = make_event(session, scores=5)
        finally:
            session.close()

        report = dedupe_events(apply=True)
        assert report["groups"] == 1
        assert report["removed"] == 1

        session = get_session()
        try:
            remaining = session.query(Event).all()
            assert [e.id for e in remaining] == [rich_id]
            assert poor_id not in [e.id for e in remaining]
            # the deleted copy's scores are gone too (cascade)
            assert session.query(LongScore).count() == 5
        finally:
            session.close()

    def test_apply_tie_break_keeps_lowest_id(self):
        session = get_session()
        try:
            low_id = make_event(session, scores=3)
            high_id = make_event(session, scores=3)
        finally:
            session.close()

        assert low_id < high_id
        report = dedupe_events(apply=True)
        assert report["removed"] == 1

        session = get_session()
        try:
            assert [e.id for e in session.query(Event).all()] == [low_id]
        finally:
            session.close()

    def test_independent_groups(self):
        session = get_session()
        try:
            make_event(session, name="Alpha", scores=1)
            make_event(session, name="Alpha", scores=1)
            make_event(session, name="Beta", scores=1)
            make_event(session, name="Beta", scores=1)
        finally:
            session.close()

        report = dedupe_events(apply=True)
        assert report["groups"] == 2
        assert report["removed"] == 2

        session = get_session()
        try:
            assert session.query(Event).count() == 2
        finally:
            session.close()
