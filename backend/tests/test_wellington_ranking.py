"""Tests for Wellington ranking computation, including in-progress athletes."""

import os
import tempfile
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Event, LongScore
from app.wellington_ranking import _get_config, _selection_checks, compute_wellington_rankings


def _check(row: dict, label: str) -> dict:
    """Return a row's checklist item matching ``label``."""
    return next(c for c in row["checks"] if c["label"] == label)


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


def _add_event(session, name: str) -> int:
    event = Event(
        name=name,
        start_date="2025-03-01",
        end_date="2025-03-02",
        discipline="MAG",
        year=2025,
        is_national=False,
    )
    session.add(event)
    session.flush()
    return event.id


def _add_score(
    session, event_id: int, event_name: str,
    name: str, gnz_id: str, club: str, score: float,
) -> None:
    session.add(LongScore(
        event_id=event_id,
        event_name=event_name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline="MAG",
        level_category="Level 7",
        apparatus="FX",
        pass_number=1,
        pass_final_score=score,
    ))


def _seed(session) -> dict[str, int]:
    """Seed Level 7 MAG events for 2025.

    ``event_ids`` maps short names to event ids so tests can reference them.
    """
    event_ids = {
        "reg1": _add_event(session, "MAG Wellington Champs"),
        "reg2": _add_event(session, "Central Championships"),
        "reg3": _add_event(session, "Wellington Champs Day 2"),
        "away1": _add_event(session, "Auckland Champs"),
        "away2": _add_event(session, "Christchurch Champs"),
    }
    # 2 comps (1 regional, 1 away) → in progress
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "Nico Geldenhuys", "A-001", "Capital Gymnastics", 60.0)
    _add_score(session, event_ids["away1"], "Auckland Champs", "Nico Geldenhuys", "A-001", "Capital Gymnastics", 58.0)
    # 3 regional-only comps → in progress (missing away mix)
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "Local Only", "B-001", "Capital Gymnastics", 62.0)
    _add_score(session, event_ids["reg2"], "Central Championships", "Local Only", "B-001", "Capital Gymnastics", 61.0)
    _add_score(session, event_ids["reg3"], "Wellington Champs Day 2", "Local Only", "B-001", "Capital Gymnastics", 60.0)
    # Full selection (1 regional + 2 away) → ranked
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "Full Qualifier", "C-001", "Capital Gymnastics", 70.0)
    _add_score(session, event_ids["away1"], "Auckland Champs", "Full Qualifier", "C-001", "Capital Gymnastics", 68.0)
    _add_score(session, event_ids["away2"], "Christchurch Champs", "Full Qualifier", "C-001", "Capital Gymnastics", 67.0)
    # Selection-capable but no intent → not_ranked when intent filter on
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "No Intent", "E-001", "Capital Gymnastics", 66.0)
    _add_score(session, event_ids["away1"], "Auckland Champs", "No Intent", "E-001", "Capital Gymnastics", 65.0)
    _add_score(session, event_ids["away2"], "Christchurch Champs", "No Intent", "E-001", "Capital Gymnastics", 64.0)
    # Selection-capable but below the 63.000 Wellington mark → not_ranked when qualifier on
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "Low Qualifier", "F-001", "Capital Gymnastics", 60.0)
    _add_score(session, event_ids["away1"], "Auckland Champs", "Low Qualifier", "F-001", "Capital Gymnastics", 58.0)
    _add_score(session, event_ids["away2"], "Christchurch Champs", "Low Qualifier", "F-001", "Capital Gymnastics", 57.0)
    # 2 comps but not a Wellington club → excluded
    _add_score(session, event_ids["reg1"], "MAG Wellington Champs", "Not WGTN", "D-001", "Aorangi South Canterbury Gymsports", 55.0)
    _add_score(session, event_ids["away1"], "Auckland Champs", "Not WGTN", "D-001", "Aorangi South Canterbury Gymsports", 54.0)
    session.commit()
    return event_ids


class TestNotRankedUnqualified:
    def test_not_ranked_lists_unqualified_wellington_athletes(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "MAG", "Level 7", intents={"A-001"})
        not_ranked = {r["name"]: r for r in result["not_ranked"]}

        assert {"Nico Geldenhuys", "Local Only"} <= set(not_ranked)

        nico = not_ranked["Nico Geldenhuys"]
        assert nico["competitions"] == 2
        assert nico["scores"] == [60.0, 58.0, None]
        assert nico["competition_names"] == ["MAG Wellington Champs", "Auckland Champs", ""]
        assert nico["categories"] == ["regional", "away", ""]
        assert nico["why"] == "Needs 3 eligible competitions — currently has 2"
        assert nico["regional_count"] == 1
        assert nico["club_count"] == 0
        assert nico["away_count"] == 1
        assert _check(nico, "Regional event") == {"label": "Regional event", "met": True, "detail": "1 of 1"}
        assert _check(nico, "2 away competitions") == {"label": "2 away competitions", "met": False, "detail": "1 of 2"}
        assert _check(nico, "Intent submitted")["met"] is True
        assert _check(nico, "Wellington qualifying mark (63.000)")["met"] is False
        assert nico["intent_submitted"] is True

        local = not_ranked["Local Only"]
        assert local["competitions"] == 3
        assert local["scores"] == [62.0, None, None]
        assert local["competition_names"] == ["MAG Wellington Champs", "", ""]
        assert local["categories"] == ["regional", "", ""]
        assert local["why"] == "Can't form the required 3-mark selection — missing the regional/away event mix"
        assert local["regional_count"] == 3
        assert local["club_count"] == 0
        assert local["away_count"] == 0
        assert _check(local, "Regional event")["met"] is True
        assert _check(local, "2 away competitions") == {"label": "2 away competitions", "met": False, "detail": "0 of 2"}
        assert _check(local, "Intent submitted")["met"] is False
        assert local["intent_submitted"] is False

    def test_qualified_athletes_excluded_from_not_ranked(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "MAG", "Level 7", intents=None)
        not_ranked_names = {r["name"] for r in result["not_ranked"]}
        ranked_names = {r["name"] for r in result["rankings"]}

        assert "Full Qualifier" not in not_ranked_names
        assert "Full Qualifier" in ranked_names
        assert "Not WGTN" not in not_ranked_names

    def test_not_ranked_sorted_alphabetically(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "MAG", "Level 7", intents=None)
        names = [r["name"] for r in result["not_ranked"]]
        assert names == sorted(names, key=str.lower)


class TestSelectionChecks:
    @pytest.mark.parametrize(
        "discipline, step, n_regional, n_club, n_away, n_total, expected",
        [
            # MAG Level 7+ — needs regional + 2 away
            ("MAG", "Level 7", 1, 0, 1, 2, [
                {"label": "Regional event", "met": True, "detail": "1 of 1"},
                {"label": "2 away competitions", "met": False, "detail": "1 of 2"},
            ]),
            ("MAG", "Level 7", 0, 1, 2, 3, [
                {"label": "Regional event", "met": False, "detail": "0 of 1"},
                {"label": "2 away competitions", "met": True, "detail": "2 of 2"},
            ]),
            # WAG STEP 5–6 — needs regional + 2nd named + away
            ("WAG", "STEP 5", 1, 0, 0, 1, [
                {"label": "Regional event", "met": True, "detail": "1 of 1"},
                {"label": "2nd named event (regional/Capital/Rimutaka)", "met": False, "detail": "1 of 2"},
                {"label": "Away competition", "met": False, "detail": "0 of 1"},
            ]),
            # WAG STEP 7–10 — needs regional + 3 total + 1 away
            ("WAG", "STEP 8", 1, 1, 0, 2, [
                {"label": "Regional event", "met": True, "detail": "1 of 1"},
                {"label": "3 competitions", "met": False, "detail": "2 of 3"},
                {"label": "Away competition", "met": False, "detail": "0 of 1"},
            ]),
            # MAG Level 4–6 — needs 2 Wellington + away
            ("MAG", "Level 5", 2, 0, 1, 3, [
                {"label": "2 Wellington events (regional or Capital)", "met": True, "detail": "2 of 2"},
                {"label": "Away competition", "met": True, "detail": "1 of 1"},
            ]),
        ],
    )
    def test_selection_checks(
        self, discipline, step, n_regional, n_club, n_away, n_total, expected,
    ):
        config = _get_config(discipline, step)
        assert config is not None
        assert _selection_checks(config, n_regional, n_club, n_away, n_total) == expected


class TestNotRanked:
    def test_intent_filtered_athletes_in_not_ranked(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "MAG", "Level 7", intents={"C-001"})
        ranked = {r["name"] for r in result["rankings"]}
        not_ranked = {r["name"] for r in result["not_ranked"]}

        assert "Full Qualifier" in ranked
        assert "No Intent" in not_ranked
        assert "Low Qualifier" in not_ranked
        assert "Full Qualifier" not in not_ranked
        # Athletes who can't form a selection are also in the combined list
        assert "Nico Geldenhuys" in not_ranked

    def test_not_ranked_cleared_when_intent_filter_off(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "MAG", "Level 7", intents={"C-001"}, intent_filter=False,
        )
        ranked = {r["name"] for r in result["rankings"]}
        not_ranked = {r["name"] for r in result["not_ranked"]}

        assert "No Intent" in ranked
        assert "No Intent" not in not_ranked
        # Low Qualifier still fails the Wellington qualifier (toggle on by default)
        assert "Low Qualifier" in not_ranked
        qual_row = next(r for r in result["not_ranked"] if r["name"] == "Low Qualifier")
        assert qual_row["why"] == "Has not achieved Wellington qualifying mark 63.000"

    def test_selection_capable_absent_when_all_toggles_off(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "MAG", "Level 7", intents=None,
            gnz_qualifier=False, wellington_qualifier=False, intent_filter=False,
        )
        not_ranked_names = {r["name"] for r in result["not_ranked"]}
        assert {"Full Qualifier", "No Intent", "Low Qualifier"} <= {
            r["name"] for r in result["rankings"]
        }
        assert "Full Qualifier" not in not_ranked_names
        assert "No Intent" not in not_ranked_names
        assert "Low Qualifier" not in not_ranked_names
        # Athletes who can't form a selection remain in the list
        assert {"Nico Geldenhuys", "Local Only"} <= not_ranked_names

    def test_not_ranked_row_shape(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "MAG", "Level 7", intents={"C-001"})
        row = next(r for r in result["not_ranked"] if r["name"] == "No Intent")
        assert row["scores"] == [66.0, 65.0, 64.0]
        assert row["competitions"] == 3
        assert row["region"] == "Wellington"
        assert row["why"] == "Hasn't submitted intent yet"
        assert _check(row, "Intent submitted") == {"label": "Intent submitted", "met": False, "detail": ""}
        assert _check(row, "Regional event")["met"] is True
        assert _check(row, "2 away competitions")["met"] is True
        assert _check(row, "Wellington qualifying mark (63.000)")["met"] is True
        assert row["intent_submitted"] is False

    def test_adding_intent_moves_athlete_to_rankings(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _seed(session)
        finally:
            session.close()

        before = compute_wellington_rankings(2025, "MAG", "Level 7", intents={"C-001"})
        assert "No Intent" in {r["name"] for r in before["not_ranked"]}
        assert "No Intent" not in {r["name"] for r in before["rankings"]}

        # Toggling intent on for E-001 (as the UI does) must move them up
        after = compute_wellington_rankings(
            2025, "MAG", "Level 7", intents={"C-001", "E-001"},
        )
        assert "No Intent" in {r["name"] for r in after["rankings"]}
        assert "No Intent" not in {r["name"] for r in after["not_ranked"]}


def _add_wag5(session, event_name: str, name: str, gnz_id: str, club: str, score: float) -> int:
    """Add a WAG STEP 5 event score for 2025."""
    event = Event(
        name=event_name,
        start_date="2025-03-01",
        end_date="2025-03-02",
        discipline="WAG",
        year=2025,
        is_national=False,
    )
    session.add(event)
    session.flush()
    session.add(LongScore(
        event_id=event.id,
        event_name=event_name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline="WAG",
        level_category="STEP 5",
        apparatus="FX",
        pass_number=1,
        pass_final_score=score,
    ))
    return event.id


def _add_intl_score(
    session, event_name: str, step: str, name: str, gnz_id: str,
    club: str, apparatus: str, score: float, pass_number: int = 1,
    aa_score: float | None = None,
) -> None:
    """Add a WAG International division score for 2025."""
    event = Event(
        name=event_name,
        start_date="2025-03-01",
        end_date="2025-03-02",
        discipline="WAG",
        year=2025,
        is_national=False,
    )
    session.add(event)
    session.flush()
    session.add(LongScore(
        event_id=event.id,
        event_name=event_name,
        gymnast_name=name,
        gnz_id=gnz_id,
        club_name=club,
        discipline="WAG",
        level_category=step,
        apparatus=apparatus,
        pass_number=pass_number,
        pass_final_score=score,
        aa_score=aa_score,
    ))


class TestSlotAlignment:
    def test_events_placed_in_correct_category_slots(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_wag5(session, "Rimutaka Juniors 2025", "Club Only", "G-001", "Capital Gymnastics", 44.0)
            _add_wag5(session, "WAG Wellington Champs", "Regional And Away", "G-002", "Capital Gymnastics", 52.0)
            _add_wag5(session, "Manawatu WAG Opens", "Regional And Away", "G-002", "Capital Gymnastics", 50.0)
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(2025, "WAG", "STEP 5", intents=None)
        rows = {r["name"]: r for r in result["not_ranked"]}

        # A club event must land in the "Next Best" (named) slot, not Regional Best.
        club_only = rows["Club Only"]
        assert club_only["scores"] == [None, 44.0, None]
        assert club_only["competition_names"] == ["", "Rimutaka Juniors 2025", ""]
        assert club_only["categories"] == ["", "club", ""]

        # A regional event fills slot 1, an away event slot 3; slot 2 stays empty.
        reg_away = rows["Regional And Away"]
        assert reg_away["scores"] == [52.0, None, 50.0]
        assert reg_away["competition_names"] == ["WAG Wellington Champs", "", "Manawatu WAG Opens"]
        assert reg_away["categories"] == ["regional", "", "away"]


class TestStep8ApparatusSpecialists:
    def test_two_comps_same_apparatus_qualifies(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "WAG Wellington Champs", "STEP 8",
                "Twice Vault", "S-001", "Capital Gymnastics",
                "VT", 11.2, aa_score=None,
            )
            _add_intl_score(
                session, "Manawatu WAG Opens", "STEP 8",
                "Twice Vault", "S-001", "Capital Gymnastics",
                "VT", 11.5, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "STEP 8", intents={"S-001"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        assert "Twice Vault" in specialists
        row = specialists["Twice Vault"]
        assert row["qualified"] is True
        assert row["count"] == 1
        assert len(row["apparatus"]) == 1
        app = row["apparatus"][0]
        assert app["app"] == "VT"
        assert app["best"] == 11.5
        assert app["count"] == 2
        assert set(app["competitions"]) == {"WAG Wellington Champs", "Manawatu WAG Opens"}

    def test_one_comp_ghost_badge(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "WAG Wellington Champs", "STEP 8",
                "Once Vault", "S-002", "Capital Gymnastics",
                "VT", 11.1, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "STEP 8", intents={"S-002"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        assert "Once Vault" in specialists
        row = specialists["Once Vault"]
        assert row["qualified"] is False
        assert len(row["apparatus"]) == 1
        app = row["apparatus"][0]
        assert app["app"] == "VT"
        assert app["count"] == 1
        assert app["competitions"] == ["WAG Wellington Champs"]

    def test_two_apparatus_one_comp_each_is_ghost_not_qualified(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "WAG Wellington Champs", "STEP 8",
                "Mixed", "S-003", "Capital Gymnastics",
                "VT", 11.2, aa_score=None,
            )
            _add_intl_score(
                session, "Manawatu WAG Opens", "STEP 8",
                "Mixed", "S-003", "Capital Gymnastics",
                "UB", 11.1, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "STEP 8", intents={"S-003"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        row = specialists["Mixed"]
        assert row["qualified"] is False
        assert {a["app"] for a in row["apparatus"]} == {"VT", "UB"}
        assert all(a["count"] == 1 for a in row["apparatus"])

    def test_mixed_qualified_and_ghost_badges(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "WAG Wellington Champs", "STEP 8",
                "Mixed Row", "S-005", "Capital Gymnastics",
                "FX", 11.4, aa_score=None,
            )
            _add_intl_score(
                session, "Manawatu WAG Opens", "STEP 8",
                "Mixed Row", "S-005", "Capital Gymnastics",
                "FX", 11.6, aa_score=None,
            )
            _add_intl_score(
                session, "CSG Classic", "STEP 8",
                "Mixed Row", "S-005", "Capital Gymnastics",
                "VT", 11.2, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "STEP 8", intents={"S-005"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        row = specialists["Mixed Row"]
        assert row["qualified"] is True
        by_app = {a["app"]: a for a in row["apparatus"]}
        assert set(by_app) == {"FX", "VT"}
        assert by_app["FX"]["count"] == 2
        assert by_app["FX"]["best"] == 11.6
        assert by_app["VT"]["count"] == 1
        assert by_app["VT"]["best"] == 11.2

    def test_below_mark_not_listed(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "WAG Wellington Champs", "STEP 8",
                "Below Mark", "S-004", "Capital Gymnastics",
                "VT", 10.9, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "STEP 8", intents={"S-004"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        assert "Below Mark" not in specialists


class TestInternational:
    def test_configs_resolve(self):
        assert _get_config("WAG", "Youth International")["key"] == "wag_youth_international"
        assert _get_config("WAG", "Junior International")["key"] == "wag_junior_international"
        assert _get_config("WAG", "Senior International")["key"] == "wag_senior_international"
        assert _get_config("MAG", "U18")["key"] == "mag_level_7_plus"
        assert _get_config("MAG", "Senior Open")["key"] == "mag_level_7_plus"

    def test_selection_checks_empty_for_single_mark(self):
        config = _get_config("WAG", "Junior International")
        assert config is not None
        assert _selection_checks(config, 0, 0, 0, 1) == []

    def test_mag_7_plus_has_specialists(self):
        config = _get_config("MAG", "Level 8")
        assert config is not None
        assert config["specialist_steps"] == {"Level 7", "Level 8", "Level 9", "Senior Open", "U18"}
        assert config["apparatus_qualifying_score"] == 11.5
        assert config["apparatus_qualifying_count"] == 1

    def test_single_mark_ranking_and_qualifier(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            _add_intl_score(
                session, "Junior International Selection", "Junior International",
                "Intl Qualifier", "J-001", "Capital Gymnastics",
                "AA", 43.5, aa_score=43.5,
            )
            _add_intl_score(
                session, "Junior International Selection", "Junior International",
                "Intl Low", "J-002", "Capital Gymnastics",
                "AA", 40.0, aa_score=40.0,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "Junior International", intents=None,
        )
        ranked = {r["name"]: r for r in result["rankings"]}

        assert "Intl Qualifier" in ranked
        assert "Intl Low" not in ranked
        entry = ranked["Intl Qualifier"]
        # Single-mark selection: one slot only, total == that mark.
        assert entry["scores"] == [43.5]
        assert entry["competitions"] == ["Junior International Selection"]
        assert entry["total"] == 43.5
        assert entry["average"] == 43.5

    def test_intl_apparatus_specialist(self):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            # Qualifies via UB specialist mark (10.4 for Junior International).
            _add_intl_score(
                session, "Junior International Selection", "Junior International",
                "UB Specialist", "J-003", "Capital Gymnastics",
                "UB", 10.6, aa_score=None,
            )
            # Reaches a mark on only one apparatus below its threshold → not a specialist.
            _add_intl_score(
                session, "Junior International Selection", "Junior International",
                "Too Low", "J-004", "Capital Gymnastics",
                "UB", 10.0, aa_score=None,
            )
            session.commit()
        finally:
            session.close()

        result = compute_wellington_rankings(
            2025, "WAG", "Junior International", intents={"J-003", "J-004"},
        )
        specialists = {s["name"]: s for s in result["apparatus_specialists"]}
        assert "UB Specialist" in specialists
        assert specialists["UB Specialist"]["apparatus"][0]["app"] == "UB"
        assert specialists["UB Specialist"]["apparatus"][0]["best"] == 10.6
        assert "Too Low" not in specialists


class TestApparatusSumFallback:
    """Multi-pass non-vault apparatus must use the best pass, not the sum,
    when the competition has no official AA (matches the national-ranking rule)."""

    def _score(self, app, total, aa=None):
        return SimpleNamespace(
            apparatus=app, pass_final_score=total, aa_score=aa,
            round_type="All Around",
        )

    def test_multi_pass_uses_best_per_apparatus(self):
        from app.wellington_ranking import _compute_competition_score

        scores = [
            self._score("HB", 12.15), self._score("HB", 12.033),
            self._score("PB", 11.2), self._score("PB", 12.3),
            self._score("PH", 10.866), self._score("PH", 9.366),
            self._score("SR", 10.65), self._score("SR", 10.633),
        ]
        # 12.15 + 12.3 + 10.866 + 10.65 = 45.966, not the summed 89.198.
        assert round(_compute_competition_score(scores, "Level 7"), 3) == 45.966

    def test_official_aa_wins(self):
        from app.wellington_ranking import _compute_competition_score

        scores = [
            self._score("HB", 8.4, aa=65.931),
            self._score("HB", 9.8, aa=65.931),
            self._score("VT", 11.1, aa=65.931),
        ]
        assert _compute_competition_score(scores, "Level 7") == 65.931

    def test_single_pass_unchanged(self):
        from app.wellington_ranking import _compute_competition_score

        scores = [self._score("FX", 12.0), self._score("HB", 10.0)]
        assert _compute_competition_score(scores, "Level 7") == 22.0
