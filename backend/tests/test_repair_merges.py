"""Tests for the wrong-merge repair script (app/repair_merges.py)."""

import os
import tempfile

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import rebuild_athletes
from app.models import Athlete, Base, Event, LongScore, SlugRedirect, WellingtonIntent
from app.repair_merges import repair, set_corrections

BASE = {"discipline": "WAG", "pass_number": 1, "apparatus": "VT", "event_name": "E"}


def _make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)
    return db_path, TestSession


def _event(session, name="Meet 2026") -> int:
    ev = Event(name=name, start_date="2026-03-01", end_date="2026-03-02", discipline="WAG", year=2026)
    session.add(ev)
    session.flush()
    return ev.id


class TestRepairMerges:
    def test_dry_run_reports_without_writing(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1 = _event(s)
            ev2 = _event(s, name="Other Meet")
            s.add(LongScore(**{**BASE, "event_id": ev1, "gymnast_name": "Mathew Arck-weeber", "gnz_id": "1023", "club_name": "New Zealand"}))
            s.add(LongScore(**{**BASE, "event_id": ev2, "gymnast_name": "Mathew Arck-weeber", "gnz_id": "1023", "club_name": "Counties - Manukau"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id

            set_corrections({aid: ("Matthew Arck-weeber", "568463")})
            report = repair(s, apply=False)
            assert report["items"][0]["rows"] == 2
            assert report["items"][0]["changed"] is True

            # Nothing written.
            rows = s.query(LongScore.gnz_id).all()
            assert rows == [("1023",), ("1023",)]
            s.rollback()
        finally:
            s.close()
            os.unlink(db_path)

    def test_apply_rewrites_reroutes_and_moves_intent(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1 = _event(s)
            s.add(LongScore(**{**BASE, "event_id": ev1, "gymnast_name": "Mathew Arck-weeber", "gnz_id": "1023", "club_name": "New Zealand"}))
            s.add(LongScore(**{**BASE, "event_id": ev1, "gymnast_name": "Mathew Arck-weeber", "gnz_id": "1023", "club_name": "Counties - Manukau"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id
            old_slug = s.query(Athlete).filter(Athlete.id == aid).first().slug
            s.add(WellingtonIntent(athlete_id=aid, gnz_id="1023", year=2026))
            s.commit()

            set_corrections({aid: ("Matthew Arck-weeber", "568463")})
            report = repair(s, apply=True)
            assert report["items"][0]["changed"] is True

            # Rows carry the corrected identity under a single athlete.
            rows = s.query(LongScore).all()
            assert len(rows) == 2
            assert {r.gnz_id for r in rows} == {"568463"}
            assert {r.gymnast_name for r in rows} == {"Matthew Arck-weeber"}
            assert len({r.athlete_id for r in rows}) == 1
            new = s.get(Athlete, next(iter({r.athlete_id for r in rows})))
            assert new.canonical_name == "Matthew Arck-weeber"
            assert new.gnz_id == "568463"

            # Old URL redirects to the corrected athlete.
            redirect = s.query(SlugRedirect).filter(SlugRedirect.old_slug == old_slug).first()
            assert redirect is not None
            assert redirect.athlete_id == new.id

            # Wellington intent moved to the corrected athlete.
            intent = s.query(WellingtonIntent).one()
            assert intent.athlete_id == new.id
            assert intent.gnz_id == "568463"
        finally:
            s.close()
            os.unlink(db_path)

    def test_reapply_is_idempotent(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1 = _event(s)
            s.add(LongScore(**{**BASE, "event_id": ev1, "gymnast_name": "Mathew Arck-weeber", "gnz_id": "1023", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id

            set_corrections({aid: ("Matthew Arck-weeber", "568463")})
            repair(s, apply=True)
            second = repair(s, apply=True)
            assert second["items"][0]["changed"] is False
        finally:
            s.close()
            os.unlink(db_path)
