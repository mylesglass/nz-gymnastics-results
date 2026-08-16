"""Tests for national per-apparatus rankings (GET /api/rankings/apparatus)."""

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

    from app.cache import cache

    cache.clear()

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


def _add_pass(
    session, event_id: int, event_name: str, name: str, gnz_id: str, club: str,
    apparatus: str, score: float, level_category: str = "STEP 8", discipline: str = "WAG",
    d_score: float | None = None, round_type: str = "All Around",
    division: str | None = None, pass_number: int = 1, aa_score: float | None = None,
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
        apparatus=apparatus,
        pass_number=pass_number,
        pass_final_score=score,
        d_score=d_score,
        aa_score=aa_score,
        round_type=round_type,
    ))


def _leaderboard(year: int, step: str, discipline: str, division: str | None = None) -> dict:
    resp = client.get(
        "/api/rankings/apparatus",
        params={
            "year": str(year),
            "step": step,
            "discipline": discipline,
            "division": division or "",
        },
    )
    assert resp.status_code == 200
    return resp.json()


def _app_rows(body: dict, app: str) -> list[dict]:
    lb = next(a for a in body["apparatus"] if a["app"] == app)
    return lb["rankings"]


class TestBestMarkPerSeason:
    def test_picks_highest_mark_across_events(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev_a = _add_event(session, "Wellington Champs")
            ev_b = _add_event(session, "Canterbury Champs")
            _add_pass(session, ev_a, "Wellington Champs", "Pead", "A-001", "Capital Gymnastics", "VT", 12.0, d_score=5.4)
            _add_pass(session, ev_b, "Canterbury Champs", "Pead", "A-001", "Capital Gymnastics", "VT", 13.5, d_score=5.8)
            _add_pass(session, ev_b, "Canterbury Champs", "Pead", "A-001", "Capital Gymnastics", "UB", 11.2, d_score=5.0)
            _add_pass(session, ev_b, "Canterbury Champs", "Other", "B-001", "Capital Gymnastics", "VT", 12.4)
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG")
        rows = _app_rows(body, "VT")
        assert rows[0]["name"] == "Pead"
        assert rows[0]["best"] == 13.5
        assert rows[0]["event"] == "Canterbury Champs"
        assert rows[0]["d"] == 5.8
        assert rows[0]["count"] == 2
        assert [r["name"] for r in rows] == ["Pead", "Other"]
        assert _app_rows(body, "UB")[0]["name"] == "Pead"

    def test_round_types_of_same_event_merge(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "TwoDay", "C-001", "Capital Gymnastics", "FX", 11.0, round_type="All Around")
            _add_pass(session, ev, "Wellington Champs", "TwoDay", "C-001", "Capital Gymnastics", "FX", 12.5, round_type="Apparatus Finals")
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG")
        rows = _app_rows(body, "FX")
        assert rows[0]["best"] == 12.5
        assert rows[0]["count"] == 1

    def test_apparatus_order_and_absent_apparatus(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "Pead", "A-001", "Capital Gymnastics", "BB", 10.9)
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG")
        apps = [a["app"] for a in body["apparatus"]]
        assert apps == ["BB"]

    def test_empty_event_set(self):
        body = _leaderboard(1999, "STEP 8", "WAG")
        assert body["apparatus"] == []

    def test_division_filter(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Over Champs")
            _add_pass(session, ev, "Over Champs", "Over Athlete", "D-001", "Capital Gymnastics", "FX", 12.0, division="OVER")
            _add_pass(session, ev, "Over Champs", "Under Athlete", "E-001", "Capital Gymnastics", "FX", 11.5, division="UNDER")
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG", division="OVER")
        rows = _app_rows(body, "FX")
        assert [r["name"] for r in rows] == ["Over Athlete"]


class TestVaultAggregation:
    def test_step6_averages_two_vaults(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "F-001", "Capital Gymnastics", "VT", 11.0, d_score=4.4, pass_number=1, level_category="STEP 6")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "F-001", "Capital Gymnastics", "VT", 13.0, d_score=5.6, pass_number=2, level_category="STEP 6")
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 6", "WAG")
        rows = _app_rows(body, "VT")
        assert rows[0]["best"] == 12.0
        assert rows[0]["d"] == 5.0

    def test_step8_takes_best_vault_on_aa_day(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "G-001", "Capital Gymnastics", "VT", 11.0, d_score=4.4, pass_number=1, level_category="STEP 8")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "G-001", "Capital Gymnastics", "VT", 13.0, d_score=5.6, pass_number=2, level_category="STEP 8")
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG")
        rows = _app_rows(body, "VT")
        assert rows[0]["best"] == 13.0
        assert rows[0]["d"] == 5.6

    def test_step10_averages_on_finals_day(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "H-001", "Capital Gymnastics", "VT", 11.0, d_score=4.4, pass_number=1, level_category="STEP 10", round_type="Apparatus Finals")
            _add_pass(session, ev, "Wellington Champs", "Vaulter", "H-001", "Capital Gymnastics", "VT", 13.0, d_score=5.6, pass_number=2, level_category="STEP 10", round_type="Apparatus Finals")
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 10", "WAG")
        rows = _app_rows(body, "VT")
        assert rows[0]["best"] == 12.0


class TestUnresolvableApparatus:
    """Passes labelled with the generic "All-around" result-set name (the
    parser's fallback for multi-set aggregate tables) must never count as a
    real apparatus: no leaderboard, no specialist badge — but their scores
    still count toward the all-around total."""

    def _seed(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            def _event(i: int, name: str) -> int:
                ev = Event(
                    name=name, start_date="2025-03-01", end_date="2025-03-02",
                    discipline="WAG", year=2025,
                )
                session.add(ev)
                session.flush()
                return ev.id

            def _score(eid, ename, name, gnz, app, total, pn=1, aa=None, rt="All Around"):
                session.add(LongScore(
                    event_id=eid, event_name=ename, gymnast_name=name, gnz_id=gnz,
                    club_name="Capital Gymnastics", discipline="WAG",
                    level_category="STEP 8", apparatus=app, pass_number=pn,
                    pass_final_score=total, round_type=rt, aa_score=aa,
                ))

            e1 = _event(1, "Meet One")
            e2 = _event(2, "Meet Two")
            # "AllRounder" only has unresolvable "All-around" passes. Each event's
            # three passes sum to 33 (< STEP 8's 43.0 AA qualifier) so she is not
            # AA-qualified; but individual passes are >= 11.0, which WOULD make her
            # a specialist if "All-around" were treated as a real apparatus.
            _score(e1, "Meet One", "AllRounder", "G-001", "All-around", 11.0)
            _score(e1, "Meet One", "AllRounder", "G-001", "All-around", 11.2)
            _score(e1, "Meet One", "AllRounder", "G-001", "All-around", 10.8)
            _score(e2, "Meet Two", "AllRounder", "G-001", "All-around", 11.4)
            _score(e2, "Meet Two", "AllRounder", "G-001", "All-around", 11.1)
            _score(e2, "Meet Two", "AllRounder", "G-001", "All-around", 10.5)
            # "RealDeal" hits the UB mark on 2 distinct competitions -> specialist.
            _score(e1, "Meet One", "RealDeal", "G-002", "UB", 11.2)
            _score(e2, "Meet Two", "RealDeal", "G-002", "UB", 11.6)
            session.commit()
        finally:
            session.close()

    def test_no_all_around_leaderboard(self):
        self._seed()
        body = _leaderboard(2025, "STEP 8", "WAG")
        apps = [a["app"] for a in body["apparatus"]]
        assert apps == ["UB"]
        assert "All-around" not in apps and "All-Around" not in apps

    def test_all_around_not_a_specialist(self):
        self._seed()
        resp = client.get("/api/rankings", params={
            "year": "2025", "step": "STEP 8", "discipline": "WAG", "qualifier": "true",
        })
        assert resp.status_code == 200
        body = resp.json()
        by_name = {s["name"]: s for s in body["apparatus_specialists"]}
        assert "RealDeal" in by_name
        assert all(a["app"] in ("VT", "UB", "BB", "FX") for a in by_name["RealDeal"]["apparatus"])
        assert "AllRounder" not in by_name, "unresolvable All-around passes must not qualify as a specialist"

    def test_all_around_scores_still_count_toward_aa_total(self):
        self._seed()
        resp = client.get("/api/rankings", params={
            "year": "2025", "step": "STEP 8", "discipline": "WAG",
        })
        assert resp.status_code == 200
        body = resp.json()
        allrounder = next(r for r in body["rankings"] if r["name"] == "AllRounder")
        # 33.0 per competition, summed over the top 2 -> total 66.0
        assert allrounder["total"] == 66.0


class TestRankingAndTies:
    def test_sorted_desc_with_t_ties(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            ev = _add_event(session, "Wellington Champs")
            _add_pass(session, ev, "Wellington Champs", "Tied One", "I-001", "Capital Gymnastics", "FX", 13.0)
            _add_pass(session, ev, "Wellington Champs", "Tied Two", "J-001", "Capital Gymnastics", "FX", 13.0)
            _add_pass(session, ev, "Wellington Champs", "Leader", "K-001", "Capital Gymnastics", "FX", 13.5)
            _add_pass(session, ev, "Wellington Champs", "Trailer", "L-001", "Capital Gymnastics", "FX", 12.0)
            session.commit()
        finally:
            session.close()

        body = _leaderboard(2025, "STEP 8", "WAG")
        rows = _app_rows(body, "FX")
        assert [r["name"] for r in rows] == ["Leader", "Tied One", "Tied Two", "Trailer"]
        assert rows[0]["rank"] == "1"
        assert rows[1]["rank"] == "T2"
        assert rows[2]["rank"] == "T2"
        assert rows[3]["rank"] == "4"
