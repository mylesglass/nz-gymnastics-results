"""Tests for national rankings: distinct-competition marks and GNZ qualifier."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Base, Event, LongScore
from app.transformer import _guess_host_club

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


def _add_event(session, name: str, host_club: str | None = None, year: int = 2025, discipline: str = "WAG") -> int:
    event = Event(
        name=name,
        start_date="2025-03-01",
        end_date="2025-03-02",
        discipline=discipline,
        year=year,
        is_national=False,
        host_club=host_club,
    )
    session.add(event)
    session.flush()
    return event.id


def _add_score(
    session, event_id: int, event_name: str, name: str, gnz_id: str, club: str,
    score: float, level_category: str = "STEP 5", discipline: str = "WAG",
    aa_score: float | None = None, round_type: str = "All Around",
    division: str | None = None,
) -> None:
    session.add(LongScore(
        event_id=event_id,
        event_name=event_name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline=discipline,
        level_category=level_category,
        division=division,
        apparatus="FX",
        pass_number=1,
        pass_final_score=score,
        aa_score=score if aa_score is None else aa_score,
        round_type=round_type,
    ))


def _rank(year: int, step: str, discipline: str, qualifier: bool = False, division: str | None = None) -> dict:
    resp = client.get(
        "/api/rankings",
        params={
            "year": str(year),
            "step": step,
            "discipline": discipline,
            "qualifier": "true" if qualifier else "false",
            "division": division or "",
        },
    )
    assert resp.status_code == 200
    return resp.json()


class TestDistinctCompetitions:
    def test_two_day_event_counts_once(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev_a = _add_event(session, "Wellington Champs", "Capital Gymnastics")
            ev_b = _add_event(session, "Canterbury Champs", "Christchurch School of Gymnastics")
            # Two round_types (AA day + Apparatus Finals day) of the same event
            _add_score(session, ev_a, "Wellington Champs", "TwoDay", "A-001", "Capital Gymnastics", 60.0, aa_score=60.0, round_type="All Around")
            _add_score(session, ev_a, "Wellington Champs", "TwoDay", "A-001", "Capital Gymnastics", 59.0, aa_score=59.0, round_type="Apparatus Finals")
            _add_score(session, ev_b, "Canterbury Champs", "TwoDay", "A-001", "Capital Gymnastics", 55.0, aa_score=55.0)
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "TwoDay")
        # Only the best mark per event; the two events must be distinct
        assert row["scores"] == [60.0, 55.0]
        assert row["competitions"] == ["Wellington Champs", "Canterbury Champs"]
        assert row["total"] == 115.0


class TestStep56Qualifier:
    def _seed(self, session) -> None:
        home = _add_event(session, "Wellington Champs", "Capital Gymnastics")
        home2 = _add_event(session, "Wellington Open", "Capital Gymnastics")
        away = _add_event(session, "Canterbury Champs", "Christchurch School of Gymnastics")
        # 2 marks, one away → qualifies
        _add_score(session, home, "Wellington Champs", "Away Ok", "B-001", "Capital Gymnastics", 51.0)
        _add_score(session, away, "Canterbury Champs", "Away Ok", "B-001", "Capital Gymnastics", 50.5)
        # 2 marks, both at home → fails the away requirement
        _add_score(session, home, "Wellington Champs", "Away Missing", "C-001", "Capital Gymnastics", 51.0)
        _add_score(session, home2, "Wellington Open", "Away Missing", "C-001", "Capital Gymnastics", 50.5)
        # Only one mark → needs 2
        _add_score(session, away, "Canterbury Champs", "One Mark", "D-001", "Capital Gymnastics", 51.0)
        # 2 marks below 50.0
        _add_score(session, home, "Wellington Champs", "Below Mark", "E-001", "Capital Gymnastics", 49.0)
        _add_score(session, home2, "Wellington Open", "Below Mark", "E-001", "Capital Gymnastics", 48.5)
        session.commit()

    def test_qualifier_requires_two_marks_and_one_away(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", qualifier=True)
        names = {r["name"] for r in body["rankings"]}
        assert "Away Ok" in names
        assert names == {"Away Ok"}

    def test_without_qualifier_everyone_ranked(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", qualifier=False)
        names = {r["name"] for r in body["rankings"]}
        assert {"Away Ok", "Away Missing", "One Mark", "Below Mark"} <= names

    def test_blank_host_club_is_conservative(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            home = _add_event(session, "Wellington Champs", None)  # unknown host
            away = _add_event(session, "Canterbury Champs", None)
            _add_score(session, home, "Wellington Champs", "Unknown Host", "F-001", "Capital Gymnastics", 51.0)
            _add_score(session, away, "Canterbury Champs", "Unknown Host", "F-001", "Capital Gymnastics", 50.5)
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", qualifier=True)
        assert all(r["name"] != "Unknown Host" for r in body["rankings"])


class TestStep7to10Qualifier:
    def test_needs_two_marks_from_different_competitions(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev_a = _add_event(session, "Wellington Champs", "Capital Gymnastics")
            ev_b = _add_event(session, "Canterbury Champs", "Christchurch School of Gymnastics")
            # Two distinct events, both ≥43 → qualifies
            _add_score(session, ev_a, "Wellington Champs", "Two Comps", "G-001", "Capital Gymnastics", 44.0, level_category="STEP 7")
            _add_score(session, ev_b, "Canterbury Champs", "Two Comps", "G-001", "Capital Gymnastics", 43.5, level_category="STEP 7")
            # Two round_types of the SAME event both ≥43 → still only one mark
            _add_score(session, ev_a, "Wellington Champs", "Same Comp", "H-001", "Capital Gymnastics", 44.0, level_category="STEP 7", aa_score=44.0, round_type="All Around")
            _add_score(session, ev_a, "Wellington Champs", "Same Comp", "H-001", "Capital Gymnastics", 43.5, level_category="STEP 7", aa_score=43.5, round_type="Apparatus Finals")
            # Only one mark
            _add_score(session, ev_a, "Wellington Champs", "One Mark", "I-001", "Capital Gymnastics", 44.0, level_category="STEP 7")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 7", "WAG", qualifier=True)
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Two Comps"}


class TestStep56TopThreeAverage:
    def test_uses_three_marks(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            ev3 = _add_event(session, "Comp Three", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "Triple", "N-001", "Capital Gymnastics", 52.0)
            _add_score(session, ev2, "Comp Two", "Triple", "N-001", "Capital Gymnastics", 51.0)
            _add_score(session, ev3, "Comp Three", "Triple", "N-001", "Capital Gymnastics", 50.0)
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "Triple")
        assert row["scores"] == [52.0, 51.0, 50.0]
        assert row["total"] == 153.0

    def test_sorts_by_average_not_sum(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            ev3 = _add_event(session, "Comp Three", "Capital Gymnastics")
            ev4 = _add_event(session, "Comp Four", "Capital Gymnastics")
            # Two marks averaging 57.5 (higher average, lower sum)
            _add_score(session, ev1, "Comp One", "TwoMark", "O-001", "Capital Gymnastics", 58.0)
            _add_score(session, ev2, "Comp Two", "TwoMark", "O-001", "Capital Gymnastics", 57.0)
            # Three marks averaging 56.667 (lower average, higher sum)
            _add_score(session, ev1, "Comp One", "ThreeMark", "P-001", "Capital Gymnastics", 58.0)
            _add_score(session, ev2, "Comp Two", "ThreeMark", "P-001", "Capital Gymnastics", 57.0)
            _add_score(session, ev3, "Comp Three", "ThreeMark", "P-001", "Capital Gymnastics", 55.0)
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG")
        ordered = [r["name"] for r in body["rankings"]]
        assert ordered.index("TwoMark") < ordered.index("ThreeMark")

    def test_other_steps_still_use_two_marks(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            ev3 = _add_event(session, "Comp Three", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "Double", "Q-001", "Capital Gymnastics", 44.0, level_category="STEP 7")
            _add_score(session, ev2, "Comp Two", "Double", "Q-001", "Capital Gymnastics", 43.5, level_category="STEP 7")
            _add_score(session, ev3, "Comp Three", "Double", "Q-001", "Capital Gymnastics", 42.0, level_category="STEP 7")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 7", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "Double")
        assert row["scores"] == [44.0, 43.5]
        assert row["total"] == 87.5


class TestStep14MarkIndicator:
    def test_check_when_two_distinct_marks_reached(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "Qualified", "R-001", "Capital Gymnastics", 53.0, level_category="STEP 1")
            _add_score(session, ev2, "Comp Two", "Qualified", "R-001", "Capital Gymnastics", 52.5, level_category="STEP 1")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 1", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "Qualified")
        assert row["reached_mark"] is True

    def test_dash_when_only_one_mark_reached(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "One Mark", "S-001", "Capital Gymnastics", 53.0, level_category="STEP 1")
            _add_score(session, ev2, "Comp Two", "One Mark", "S-001", "Capital Gymnastics", 40.0, level_category="STEP 1")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 1", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "One Mark")
        assert row["reached_mark"] is False

    def test_two_marks_in_same_competition_count_once(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "Same Comp", "T-001", "Capital Gymnastics", 53.0, level_category="STEP 1", aa_score=53.0, round_type="All Around")
            _add_score(session, ev1, "Comp One", "Same Comp", "T-001", "Capital Gymnastics", 52.5, level_category="STEP 1", aa_score=52.5, round_type="Apparatus Finals")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 1", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "Same Comp")
        assert row["reached_mark"] is False

    def test_other_steps_not_flagged(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev1 = _add_event(session, "Comp One", "Capital Gymnastics")
            ev2 = _add_event(session, "Comp Two", "Capital Gymnastics")
            _add_score(session, ev1, "Comp One", "Step Five", "U-001", "Capital Gymnastics", 53.0, level_category="STEP 5")
            _add_score(session, ev2, "Comp Two", "Step Five", "U-001", "Capital Gymnastics", 52.5, level_category="STEP 5")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG")
        row = next(r for r in body["rankings"] if r["name"] == "Step Five")
        assert row["reached_mark"] is False


class TestFigAndMagQualifier:
    @pytest.mark.parametrize(
        "step, mark, pass_score, fail_score",
        [
            ("Youth International", 42.5, 42.6, 42.4),
            ("Junior International", 43.0, 43.1, 42.9),
            ("Senior International", 45.0, 45.1, 44.9),
        ],
    )
    def test_fig_single_mark(self, step, mark, pass_score, fail_score):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs", "Capital Gymnastics")
            _add_score(session, ev, "Wellington Champs", "Passer", "J-001", "Capital Gymnastics", pass_score, level_category=step)
            _add_score(session, ev, "Wellington Champs", "Fails", "K-001", "Capital Gymnastics", fail_score, level_category=step)
            session.commit()
        finally:
            session.close()

        body = _rank(2025, step, "WAG", qualifier=True)
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Passer"}

    @pytest.mark.parametrize("step", ["Level 7", "Level 8", "Level 9", "U18", "Senior Open"])
    def test_mag_single_mark_at_63(self, step):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Canterbury Champs", "Christchurch School of Gymnastics", discipline="MAG")
            _add_score(session, ev, "Canterbury Champs", "Passer", "L-001", "Capital Gymnastics", 63.5, level_category=step, discipline="MAG")
            _add_score(session, ev, "Canterbury Champs", "Fails", "M-001", "Capital Gymnastics", 62.9, level_category=step, discipline="MAG")
            session.commit()
        finally:
            session.close()

        body = _rank(2025, step, "MAG", qualifier=True)
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Passer"}


class TestGuessHostClub:
    def test_club_name_in_event_name(self):
        assert _guess_host_club("Capital Juniors 2025") == "Capital Gymnastics"

    def test_longest_match_wins(self):
        assert _guess_host_club("Gymnastics Waitara - Junior Opens 2025") == "Gymnastics Waitara"

    def test_no_match_returns_empty(self):
        assert _guess_host_club("Ribbon Day 2025") == ""


class TestDivisionFilter:
    def _seed(self, session) -> None:
        ev_over = _add_event(session, "Over Champs", "Capital Gymnastics")
        ev_under = _add_event(session, "Under Champs", "Capital Gymnastics")
        # Two marks each in a single division
        _add_score(session, ev_over, "Over Champs", "Over Athlete", "A-001", "Capital Gymnastics", 51.0, division="OVER")
        _add_score(session, ev_under, "Under Champs", "Under Athlete", "B-001", "Capital Gymnastics", 50.5, division="UNDER")
        # Mixed athlete: one mark in each division
        _add_score(session, ev_over, "Over Champs", "Mixed Athlete", "C-001", "Capital Gymnastics", 52.0, division="OVER")
        _add_score(session, ev_under, "Under Champs", "Mixed Athlete", "C-001", "Capital Gymnastics", 51.5, division="UNDER")
        # No division set (None)
        _add_score(session, ev_over, "Over Champs", "No Division", "D-001", "Capital Gymnastics", 49.0, division=None)
        session.commit()

    def test_all_divisions_by_default(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG")
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Over Athlete", "Under Athlete", "Mixed Athlete", "No Division"}

    def test_over_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", division="OVER")
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Over Athlete", "Mixed Athlete"}
        row = next(r for r in body["rankings"] if r["name"] == "Mixed Athlete")
        assert row["scores"] == [52.0]

    def test_under_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", division="UNDER")
        names = {r["name"] for r in body["rankings"]}
        assert names == {"Under Athlete", "Mixed Athlete"}
        row = next(r for r in body["rankings"] if r["name"] == "Mixed Athlete")
        assert row["scores"] == [51.5]

    def test_unknown_division_returns_empty(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            self._seed(session)
        finally:
            session.close()

        body = _rank(2025, "STEP 5", "WAG", division="INTERNATIONAL")
        assert body["rankings"] == []
