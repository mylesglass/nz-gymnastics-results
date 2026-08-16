"""Tests for medal tallies: dedup, ties, year filter, club attribution."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Base, Event, LongScore

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    from app.cache import cache

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

    cache.clear()

    yield

    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


def _add_event(session, name: str, year: int = 2025, is_national: bool = False) -> int:
    event = Event(
        name=name,
        start_date="2025-03-01",
        end_date="2025-03-02",
        discipline="WAG",
        year=year,
        is_national=is_national,
    )
    session.add(event)
    session.flush()
    return event.id


def _add_score(
    session,
    event_id: int,
    event_name: str,
    name: str,
    gnz_id: str,
    club: str,
    apparatus: str,
    app_rank: int | None = None,
    aa_rank: int | None = None,
    round_type: str = "All Around",
    pass_number: int = 1,
) -> None:
    session.add(LongScore(
        event_id=event_id,
        event_name=event_name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline="WAG",
        level_category="STEP 5",
        apparatus=apparatus,
        pass_number=pass_number,
        pass_final_score=10.0,
        apparatus_rank=app_rank,
        aa_rank=aa_rank,
        round_type=round_type,
    ))


def _medals(**params) -> dict:
    resp = client.get("/api/medals", params=params)
    assert resp.status_code == 200
    return resp.json()


def _gymnast(body: dict, name: str) -> dict:
    return next(g for g in body["gymnasts"] if g["name"] == name)


class TestGymnastTallies:
    def test_aa_and_apparatus_medals(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            # AA gold duplicated on every apparatus row must count once
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=3, aa_rank=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "UB", app_rank=2, aa_rank=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "BB", app_rank=None, aa_rank=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "FX", app_rank=None, aa_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals()
        g = _gymnast(body, "Ana")
        assert g["medals"]["g"] == 1
        assert g["medals"]["s"] == 1
        assert g["medals"]["b"] == 1
        assert g["medals"]["total"] == 3
        assert g["gnz_id"] == "G-1"
        assert g["club"] == "Affinity Gymnastics Academy"

    def test_vault_multi_pass_counts_once(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=3, pass_number=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=3, pass_number=2)
            session.commit()
        finally:
            session.close()

        g = _gymnast(_medals(), "Ana")
        assert g["medals"]["b"] == 1
        assert g["medals"]["total"] == 1

    def test_aa_and_apparatus_final_are_distinct_medals(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            # AA gold in qualification + vault gold in the final = 2 distinct awards
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=2, aa_rank=1, round_type="All Around")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1, round_type="Apparatus Finals")
            session.commit()
        finally:
            session.close()

        g = _gymnast(_medals(), "Ana")
        assert g["medals"]["g"] == 2
        assert g["medals"]["s"] == 1

    def test_apparatus_finals_aa_rank_not_counted(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            # An "Apparatus Finals" round carries no real AA award
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=2, aa_rank=1, round_type="Apparatus Finals")
            session.commit()
        finally:
            session.close()

        g = _gymnast(_medals(), "Ana")
        assert g["medals"]["s"] == 1
        assert g["medals"]["g"] == 0

    def test_unresolvable_apparatus_rank_awards_no_medal(self):
        # Passes whose apparatus is a generic "All-around" label (parser
        # fallback for multi-set result tables) must never award an apparatus
        # medal, even with a 1-3 rank stored.
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "All-around", app_rank=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "All-Around | Over", app_rank=2)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=3)
            session.commit()
        finally:
            session.close()

        body = _medals()
        g = _gymnast(body, "Ana")
        assert g["medals"]["g"] == 0
        assert g["medals"]["s"] == 0
        assert g["medals"]["b"] == 1
        assert g["medals"]["total"] == 1


class TestTies:
    def test_shared_rank_both_medal(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, ev, "Meet", "Bella", "G-2", "Affinity Gymnastics Academy", "VT", app_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals()
        assert _gymnast(body, "Ana")["medals"]["g"] == 1
        assert _gymnast(body, "Bella")["medals"]["g"] == 1


class TestYearFilter:
    def test_year_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev25 = _add_event(session, "Meet 2025", year=2025)
            ev26 = _add_event(session, "Meet 2026", year=2026)
            _add_score(session, ev25, "Meet 2025", "Old", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, ev26, "Meet 2026", "New", "G-2", "Affinity Gymnastics Academy", "VT", app_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals(year=2026)
        names = {g["name"] for g in body["gymnasts"]}
        assert names == {"New"}
        assert body["year"] == 2026

    def test_nationals_count_like_any_competition(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            national = _add_event(session, "Nationals", is_national=True)
            _add_score(session, national, "Nationals", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, national, "Nationals", "Ana", "G-1", "Affinity Gymnastics Academy", "UB", app_rank=2, aa_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals()
        g = _gymnast(body, "Ana")
        assert g["medals"]["g"] == 2
        assert g["medals"]["s"] == 1
        assert g["medals"]["total"] == 3
        assert "nationals" not in g
        club = next(c for c in body["clubs"] if c["name"] == "Affinity Gymnastics Academy")
        assert club["medals"]["g"] == 2


class TestAttribution:
    def test_club_attribution(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "UB", app_rank=2)
            session.commit()
        finally:
            session.close()

        body = _medals()
        club = next(c for c in body["clubs"] if c["name"] == "Affinity Gymnastics Academy")
        assert club["medals"]["g"] == 1
        assert club["medals"]["s"] == 1
        assert set(club.keys()) == {"name", "medals"}

    def test_regional_team_counts_as_plain_club(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Counties - Manukau", "VT", app_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals()
        club = next(c for c in body["clubs"] if c["name"] == "Counties - Manukau")
        assert club["medals"]["g"] == 1
        assert set(club.keys()) == {"name", "medals"}
        assert "regions" not in body

    def test_missing_gnz_id_still_counts_for_club(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "", "Affinity Gymnastics Academy", "VT", app_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals()
        g = _gymnast(body, "Ana")
        assert g["gnz_id"] == ""
        assert g["medals"]["g"] == 1
        club = next(c for c in body["clubs"] if c["name"] == "Affinity Gymnastics Academy")
        assert club["medals"]["g"] == 1

    def test_gnz_id_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, ev, "Meet", "Bella", "G-2", "Affinity Gymnastics Academy", "VT", app_rank=3)
            session.commit()
        finally:
            session.close()

        body = _medals(gnz_id="G-1")
        assert [g["name"] for g in body["gymnasts"]] == ["Ana"]
        assert len(body["clubs"]) == 1

    def test_club_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Meet")
            _add_score(session, ev, "Meet", "Ana", "G-1", "Affinity Gymnastics Academy", "VT", app_rank=1)
            _add_score(session, ev, "Meet", "Bella", "G-2", "Levin Gymnastics Club", "VT", app_rank=1)
            session.commit()
        finally:
            session.close()

        body = _medals(club="Levin Gymnastics Club")
        assert [c["name"] for c in body["clubs"]] == ["Levin Gymnastics Club"]
        assert len(body["gymnasts"]) == 1
        assert body["gymnasts"][0]["club"] == "Levin Gymnastics Club"
