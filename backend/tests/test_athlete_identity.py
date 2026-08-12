"""Tests for athlete identity clustering (athlete_identity.py)."""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import rebuild_athletes, resolve_identity
from app.models import Athlete, Base, LongScore


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
    return db_path, TestSession, old_engine, old_session


def _teardown_db(db_path, old_engine, old_session):
    import app.database as db_mod
    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


class TestAthleteIdentity:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.db_path, self.TestSession, self.old_engine, self.old_session = _setup_db()
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)

    BASE = {"discipline": "WAG", "pass_number": 1, "apparatus": "VT", "event_name": "E"}

    def _seed(self, rows: list[dict]):
        sess = self.TestSession()
        for r in rows:
            sess.add(LongScore(**{**self.BASE, **r}))
        sess.commit()
        sess.close()

    def _athletes(self):
        sess = self.TestSession()
        try:
            return {
                a.canonical_name: {"gnz_id": a.gnz_id, "slug": a.slug}
                for a in sess.query(Athlete).all()
            }
        finally:
            sess.close()

    def _row_athlete(self, name: str, gid: str) -> set[int]:
        sess = self.TestSession()
        try:
            return {
                r.athlete_id
                for r in sess.query(LongScore).filter(
                    LongScore.gymnast_name == name,
                    (LongScore.gnz_id == gid) if gid else LongScore.gnz_id.is_(None),
                ).all()
            }
        finally:
            sess.close()

    def test_single_id_one_athlete(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "club_name": "C1"},
            {"event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "club_name": "C1"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 1
        assert self._row_athlete("Alice Smith", "123") == {1}

    def test_two_ids_same_club_merge(self):
        # Same name, two IDs, same club, different events → one person
        self._seed([
            {"event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "club_name": "C1"},
            {"event_id": 2, "gymnast_name": "Alice Smith", "gnz_id": "456", "club_name": "C1"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 1
        assert self._row_athlete("Alice Smith", "123") == self._row_athlete("Alice Smith", "456")

    def test_same_event_two_ids_split(self):
        # Two people sharing a name at the same event (Madison Lynch case)
        self._seed([
            {"event_id": 1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
            {"event_id": 1, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 2
        assert self._row_athlete("Madison Lynch", "249317") != self._row_athlete("Madison Lynch", "716561")

    def test_disjoint_clubs_split(self):
        # Same name, different IDs, never the same event but disjoint clubs
        self._seed([
            {"event_id": 1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
            {"event_id": 2, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 2

    def test_discipline_conflict_split(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Blake Taylor", "gnz_id": "122484", "discipline": "MAG", "club_name": "Hamilton City"},
            {"event_id": 2, "gymnast_name": "Blake Taylor", "gnz_id": "649936", "discipline": "WAG", "club_name": "TGC"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 2

    def test_shared_id_similar_names_merge(self):
        # Spelling variants sharing an ID collapse into one athlete
        self._seed([
            {"event_id": 1, "gymnast_name": "Eva Mcewan", "gnz_id": "999", "club_name": "OMNI"},
            {"event_id": 2, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 1
        athletes = self._athletes()
        assert "Eva McEwan" in athletes

    def test_shared_id_dissimilar_names_stay_separate(self):
        # Genuinely different people sharing a bad ID stay separate
        self._seed([
            {"event_id": 1, "gymnast_name": "John Smith", "gnz_id": "888", "club_name": "C2"},
            {"event_id": 2, "gymnast_name": "Jane Porter", "gnz_id": "888", "club_name": "C3"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 2
        assert self._row_athlete("John Smith", "888") != self._row_athlete("Jane Porter", "888")

    def test_empty_id_joins_dominant(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Bob Jones", "gnz_id": None, "club_name": "C4"},
            {"event_id": 2, "gymnast_name": "Bob Jones", "gnz_id": "777", "club_name": "C4"},
            {"event_id": 3, "gymnast_name": "Bob Jones", "gnz_id": "777", "club_name": "C4"},
        ])
        sess = self.TestSession()
        try:
            n = rebuild_athletes(sess)
        finally:
            sess.close()
        assert n == 1
        assert self._row_athlete("Bob Jones", None) == self._row_athlete("Bob Jones", "777")

    def test_canonical_name_most_frequent_spelling(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "eva mcewan", "gnz_id": "999", "club_name": "OMNI"},
            {"event_id": 2, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
            {"event_id": 3, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            rebuild_athletes(sess)
        finally:
            sess.close()
        athletes = self._athletes()
        assert "Eva McEwan" in athletes

    def test_idempotent_and_slug_stable(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
            {"event_id": 2, "gymnast_name": "Eva Mcewan", "gnz_id": "999", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            rebuild_athletes(sess)
            before = {(a.canonical_name, a.gnz_id, a.slug, a.id) for a in sess.query(Athlete).all()}
            rebuild_athletes(sess)
            after = {(a.canonical_name, a.gnz_id, a.slug, a.id) for a in sess.query(Athlete).all()}
        finally:
            sess.close()
        assert before == after
        assert len(before) == 1

    def test_resolve_identity_slug_and_gnz_id(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
            {"event_id": 2, "gymnast_name": "Eva Mcewan", "gnz_id": "999", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            rebuild_athletes(sess)
            athlete = sess.query(Athlete).first()
            assert resolve_identity(sess, slug=athlete.slug) == athlete.id
            assert resolve_identity(sess, gnz_id="999") == athlete.id
            assert resolve_identity(sess, slug="nope") is None
            assert resolve_identity(sess, gnz_id="missing") is None
        finally:
            sess.close()

    def test_no_rows_deletes_athletes(self):
        self._seed([
            {"event_id": 1, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
        ])
        sess = self.TestSession()
        try:
            rebuild_athletes(sess)
            assert sess.query(Athlete).count() == 1
            sess.query(LongScore).delete()
            sess.commit()
            n = rebuild_athletes(sess)
            assert n == 0
            assert sess.query(Athlete).count() == 0
        finally:
            sess.close()
