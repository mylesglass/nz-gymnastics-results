"""Tests for the merge-reversal script (app/reverse_merges.py)."""

import os
import tempfile

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import _signature_hash, _slug_from_hash, rebuild_athletes
from app.models import Athlete, Base, Event, LongScore, SlugRedirect, WellingtonIntent
from app.reverse_merges import derive_spec, reverse

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


def _slug(norm: str, gid: str) -> str:
    return _slug_from_hash(_signature_hash(norm, gid))


class TestReverseMerges:
    def test_reverse_splits_by_event(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1, ev2, ev3 = _event(s), _event(s, "B"), _event(s, "C")
            for eid in (ev1, ev2, ev3):
                s.add(LongScore(**{**BASE, "event_id": eid, "gymnast_name": "Isabella Matherson", "gnz_id": "523803", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id
            merged_slug = s.query(Athlete).filter(Athlete.id == aid).first().slug

            spec = {"cases": [{"athlete_id": aid, "splits": [
                {"name": "Isabella Matheson", "gnz_id": "523803", "event_ids": [ev1, ev2]},
                {"name": "Isabella Matherson", "gnz_id": "", "event_ids": [ev3]},
            ]}]}
            rep = reverse(s, spec, apply=True)
            assert rep["cases"][0]["status"] == "reversed"

            by_name = {a.canonical_name: a for a in s.query(Athlete).all()}
            assert set(by_name) == {"Isabella Matheson", "Isabella Matherson"}
            matheson = by_name["Isabella Matheson"]
            matherson = by_name["Isabella Matherson"]
            assert matheson.gnz_id == "523803"
            assert matherson.gnz_id is None
            # Original pre-merge slugs are live again.
            assert matheson.slug == _slug("isabella matheson", "523803")
            assert matherson.slug == _slug("isabella matherson", "")
            # The merged slug redirects to the larger split.
            redirect = s.query(SlugRedirect).filter(SlugRedirect.old_slug == merged_slug).first()
            assert redirect is not None
            assert redirect.athlete_id == matheson.id
            # Rows split correctly.
            assert s.query(LongScore).filter(LongScore.athlete_id == matheson.id).count() == 2
            assert s.query(LongScore).filter(LongScore.athlete_id == matherson.id).count() == 1
        finally:
            s.close()
            os.unlink(db_path)

    def test_reverse_same_name_sets_override(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1, ev2 = _event(s), _event(s, "B")
            for eid in (ev1, ev2):
                s.add(LongScore(**{**BASE, "event_id": eid, "gymnast_name": "Bianca Mendes Mattos", "gnz_id": "539540", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id

            spec = {"cases": [{"athlete_id": aid, "splits": [
                {"name": "Bianca Mendes Mattos", "gnz_id": "539540", "event_ids": [ev1]},
                {"name": "Bianca Mendes Mattos", "gnz_id": "", "event_ids": [ev2]},
            ]}]}
            reverse(s, spec, apply=True)

            athletes = s.query(Athlete).all()
            assert len(athletes) == 2
            assert {a.canonical_name for a in athletes} == {"Bianca Mendes Mattos"}
            by_id = {a.gnz_id: a for a in athletes}
            id_side = by_id["539540"]
            empty_side = by_id[None]
            assert s.query(LongScore).filter(LongScore.athlete_id == empty_side.id, LongScore.identity_override.isnot(None)).count() == 1
            assert s.query(LongScore).filter(LongScore.athlete_id == id_side.id, LongScore.identity_override.isnot(None)).count() == 0
        finally:
            s.close()
            os.unlink(db_path)

    def test_reverse_requires_full_coverage(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1, ev2, ev3 = _event(s), _event(s, "B"), _event(s, "C")
            for eid in (ev1, ev2, ev3):
                s.add(LongScore(**{**BASE, "event_id": eid, "gymnast_name": "Isabella Matherson", "gnz_id": "523803", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id

            spec = {"cases": [{"athlete_id": aid, "splits": [
                {"name": "Isabella Matheson", "gnz_id": "523803", "event_ids": [ev1, ev2]},
            ]}]}
            rep = reverse(s, spec, apply=False)
            assert rep["cases"][0]["status"] == "error"
            assert "not covered" in rep["cases"][0]["error"]

            # Overlapping events also rejected.
            spec2 = {"cases": [{"athlete_id": aid, "splits": [
                {"name": "A", "gnz_id": "1", "event_ids": [ev1, ev2]},
                {"name": "B", "gnz_id": "2", "event_ids": [ev2, ev3]},
            ]}]}
            rep2 = reverse(s, spec2, apply=False)
            assert rep2["cases"][0]["status"] == "error"
            assert "overlap" in rep2["cases"][0]["error"]
        finally:
            s.close()
            os.unlink(db_path)

    def test_reverse_repoints_intent_and_is_idempotent(self):
        db_path, TestSession = _make_db()
        s = TestSession()
        try:
            ev1, ev2, ev3 = _event(s), _event(s, "B"), _event(s, "C")
            for eid in (ev1, ev2, ev3):
                s.add(LongScore(**{**BASE, "event_id": eid, "gymnast_name": "Isabella Matherson", "gnz_id": "523803", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            aid = s.query(Athlete).first().id
            s.add(WellingtonIntent(athlete_id=aid, gnz_id="523803", year=2026))
            s.commit()

            spec = {"cases": [{"athlete_id": aid, "splits": [
                {"name": "Isabella Matheson", "gnz_id": "523803", "event_ids": [ev1, ev2]},
                {"name": "Isabella Matherson", "gnz_id": "", "event_ids": [ev3]},
            ]}]}
            reverse(s, spec, apply=True)

            matheson = s.query(Athlete).filter(Athlete.canonical_name == "Isabella Matheson").first()
            intent = s.query(WellingtonIntent).one()
            assert intent.athlete_id == matheson.id
            assert intent.gnz_id == "523803"

            # Re-running is a no-op.
            second = reverse(s, spec, apply=True)
            assert second["cases"][0]["status"] == "already reversed"
            assert s.query(Athlete).count() == 2
        finally:
            s.close()
            os.unlink(db_path)

    def test_derive_spec_from_backup(self):
        import shutil

        # The backup is a snapshot of the live DB *before* the merge (same id
        # space), so derivation can tell merged-away athletes from survivors.
        live_path, LiveSession = _make_db()
        s = LiveSession()
        try:
            e1, e2, e3 = _event(s), _event(s, "B"), _event(s, "C")
            s.add(LongScore(**{**BASE, "event_id": e1, "gymnast_name": "Isabella Matheson", "gnz_id": "523803", "club_name": "C1"}))
            s.add(LongScore(**{**BASE, "event_id": e2, "gymnast_name": "Isabella Matheson", "gnz_id": "523803", "club_name": "C1"}))
            s.add(LongScore(**{**BASE, "event_id": e3, "gymnast_name": "Isabella Matherson", "gnz_id": "", "club_name": "C1"}))
            s.commit()
            rebuild_athletes(s)
            s.close()

            bak_path = live_path + ".bak"
            shutil.copy(live_path, bak_path)
            try:
                s = LiveSession()
                # Simulate the merge: everything collapses onto one identity.
                s.query(LongScore).update(
                    {"gymnast_name": "Isabella Matherson", "gnz_id": "523803"},
                    synchronize_session=False,
                )
                s.commit()
                rebuild_athletes(s)
                aid = s.query(Athlete).first().id

                spec = derive_spec(s, bak_path, athlete_ids=[aid])
                assert len(spec["cases"]) == 1
                splits = spec["cases"][0]["splits"]
                by_name = {sp["name"]: sp for sp in splits}
                assert set(by_name) == {"Isabella Matheson", "Isabella Matherson"}
                assert by_name["Isabella Matheson"]["gnz_id"] == "523803"
                assert set(by_name["Isabella Matheson"]["event_ids"]) == {e1, e2}
                assert by_name["Isabella Matherson"]["gnz_id"] == ""
                assert set(by_name["Isabella Matherson"]["event_ids"]) == {e3}
            finally:
                os.unlink(bak_path)
        finally:
            os.unlink(live_path)
