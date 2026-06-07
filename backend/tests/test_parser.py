import json
from pathlib import Path

import pytest

from app.parser import _infer_event_discipline, _normalise_apparatus, parse_json, validate_upload_structure

HERE = Path(__file__).resolve().parent
DATA_DIR_2025 = HERE.parent.parent / "data-collection" / "2025" / "json"
DATA_DIR_2026 = HERE.parent.parent / "data-collection" / "2026"


def load(name):
    if (DATA_DIR_2026 / name).exists():
        path = DATA_DIR_2026 / name
    else:
        path = DATA_DIR_2025 / name
    if not path.exists():
        pytest.skip(f"{name} not found")
    with open(path) as f:
        return json.load(f)


# --- Known files and basic stats ---
ALL_FILES = {
    # 2026
    "hve-2026.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG+MAG"},
    "mgi-wag-2026.json": {"min_rows": 2000, "min_gyms": 400, "discipline": "WAG"},
    # 2025 - major
    "csg-classic_2025.json": {"min_rows": 3000, "min_gyms": 500, "discipline": "WAG+MAG"},
    "nationals-2025.json": {"min_rows": 2000, "min_gyms": 400, "discipline": "WAG+MAG"},
    "affinity_2025.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG+MAG"},
    # 2025 - diverse events
    "manawatu-wag_2025.json": {"min_rows": 2000, "min_gyms": 400, "discipline": "WAG"},
    "manawatu-mag_2025.json": {"min_rows": 500, "min_gyms": 100, "discipline": "MAG"},
    "southern-champs.json": {"min_rows": 700, "min_gyms": 150, "discipline": "WAG+MAG"},
    "kings-birthday_2025.json": {"min_rows": 1000, "min_gyms": 250, "discipline": "WAG+MAG"},
    "rimutaka-juniors_2025.json": {"min_rows": 500, "min_gyms": 100, "discipline": "WAG"},
    "wellington-wag_2025.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG"},
    "wellington-mag_2025.json": {"min_rows": 200, "min_gyms": 40, "discipline": "MAG"},
    "hbpb-seniors.json": {"min_rows": 400, "min_gyms": 50, "discipline": "WAG"},
    "levin.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG+MAG"},
    "northland-champs.json": {"min_rows": 500, "min_gyms": 100, "discipline": "WAG+MAG"},
    "tristar-elementary_2025.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG+MAG"},
    "tristar-senior_2025.json": {"min_rows": 1000, "min_gyms": 200, "discipline": "WAG+MAG"},
    "midlands-junior-senior.json": {"min_rows": 700, "min_gyms": 100, "discipline": "WAG+MAG"},
}

# Full scan of every JSON in the 2025 dir
ALL_2025_FILES = sorted(p.name for p in DATA_DIR_2025.glob("*.json"))


class TestNormaliseApparatus:
    def test_wag(self):
        assert _normalise_apparatus("Floor") == "FX"
        assert _normalise_apparatus("Vault") == "VT"
        assert _normalise_apparatus("Beam") == "BB"
        assert _normalise_apparatus("Balance Beam") == "BB"
        assert _normalise_apparatus("Uneven Bars") == "UB"
        assert _normalise_apparatus("U-Bars") == "UB"

    def test_mag(self):
        assert _normalise_apparatus("Pommel") == "PH"
        assert _normalise_apparatus("Pommel Horse") == "PH"
        assert _normalise_apparatus("Rings") == "SR"
        assert _normalise_apparatus("Still Rings") == "SR"
        assert _normalise_apparatus("P-Bars") == "PB"
        assert _normalise_apparatus("Parallel Bars") == "PB"
        assert _normalise_apparatus("H-Bar") == "HB"
        assert _normalise_apparatus("Horizontal Bar") == "HB"
        assert _normalise_apparatus("Vault") == "VT"

    def test_unknown_passthrough(self):
        assert _normalise_apparatus("Something") == "Something"


class TestInferEventDiscipline:
    def test_wag_only(self):
        data = {"units": [{"name": "WAG STEP 5"}, {"name": "STEP 3 Green"}]}
        assert _infer_event_discipline(data) == "WAG"

    def test_mag_only(self):
        data = {"units": [{"name": "MAG Level 4"}, {"name": "Level 2"}]}
        assert _infer_event_discipline(data) == "MAG"

    def test_both(self):
        data = {"units": [{"name": "WAG STEP 5"}, {"name": "MAG Level 4"}]}
        assert _infer_event_discipline(data) == "WAG+MAG"


class TestParseAllFiles:
    @pytest.mark.parametrize("fname", list(ALL_FILES.keys()))
    def test_parses_with_minimum_rows(self, fname):
        data = load(fname)
        stats = ALL_FILES[fname]
        event_info, rows = parse_json(data)

        assert event_info["discipline"] == stats["discipline"], (
            f"{fname}: expected discipline={stats['discipline']}, got {event_info['discipline']}"
        )
        assert len(rows) >= stats["min_rows"], (
            f"{fname}: expected >= {stats['min_rows']} rows, got {len(rows)}"
        )

        gymnasts = set(r["gymnast_name"] for r in rows)
        assert len(gymnasts) >= stats["min_gyms"], (
            f"{fname}: expected >= {stats['min_gyms']} gymnasts, got {len(gymnasts)}"
        )

    @pytest.mark.parametrize("fname", list(ALL_FILES.keys()))
    def test_rows_have_required_fields(self, fname):
        data = load(fname)
        _, rows = parse_json(data)
        for row in rows[:50]:
            assert row["gymnast_name"], f"Missing gymnast_name in {fname}"
            assert row["apparatus"], f"Missing apparatus in {fname}"
            assert "pass_final_score" in row, f"Missing pass_final_score in {fname}"
            assert "division" in row
            assert "round_type" in row

    @pytest.mark.parametrize("fname", list(ALL_FILES.keys()))
    def test_gnz_ids_cleaned(self, fname):
        data = load(fname)
        _, rows = parse_json(data)
        for row in rows[:30]:
            gnz = row["gnz_id"]
            assert gnz is None or not gnz.startswith("GS"), (
                f"GNZ ID still has GS prefix: {gnz} in {fname}"
            )

    @pytest.mark.parametrize("fname", list(ALL_FILES.keys()))
    def test_apparatus_ranks_present(self, fname):
        data = load(fname)
        _, rows = parse_json(data)
        ranked = [r for r in rows if r["apparatus_rank"] is not None]
        assert len(ranked) > 0, f"No apparatus ranks in {fname}"

    @pytest.mark.parametrize("fname", list(ALL_FILES.keys()))
    def test_aa_scores_present(self, fname):
        data = load(fname)
        _, rows = parse_json(data)
        with_aa = [r for r in rows if r["aa_score"] is not None]
        assert len(with_aa) > 0, f"No AA scores in {fname}"


class TestBulkScan2025:
    """Ensure every 2025 JSON file parses without errors."""

    @pytest.mark.parametrize("fname", ALL_2025_FILES)
    def test_parses_cleanly(self, fname):
        path = DATA_DIR_2025 / fname
        if not path.exists():
            pytest.skip(f"{fname} not found")
        with open(path) as f:
            data = json.load(f)
        event_info, rows = parse_json(data)
        assert len(event_info["name"]) > 0
        assert len(rows) > 0


class TestParseRealData:
    def test_hve_parses(self):
        data = load("hve-2026.json")
        event_info, rows = parse_json(data)
        assert event_info["name"] == "HVG Elementary Competition 2026"
        assert event_info["discipline"] == "WAG+MAG"
        assert len(rows) >= 1000

    def test_mgi_parses(self):
        data = load("mgi-wag-2026.json")
        event_info, rows = parse_json(data)
        assert event_info["name"] == "Manawatu WAG Opens 2026"
        assert event_info["discipline"] == "WAG"
        assert len(rows) >= 2000

    def test_nationals_has_qualification_and_finals(self):
        data = load("nationals-2025.json")
        _, rows = parse_json(data)
        round_types = set(r["round_type"] for r in rows)
        assert "All Around - Qualification" in round_types
        assert any("Final" in (rt or "") for rt in round_types)

    def test_csg_classic_large_event(self):
        data = load("csg-classic_2025.json")
        _, rows = parse_json(data)
        assert len(rows) >= 3000
        gymnasts = set(r["gymnast_name"] for r in rows)
        assert len(gymnasts) >= 500

    def test_csg_classic_international_levels(self):
        data = load("csg-classic_2025.json")
        _, rows = parse_json(data)
        levels = {r["gymnast_name"]: r["level_category"] for r in rows}
        assert levels.get("Alisa Wada") == "Senior International"
        assert levels.get("Sarah Kennard") == "Junior International"

    def test_csg_classic_apparatus_finals_no_aa(self):
        data = load("csg-classic_2025.json")
        _, rows = parse_json(data)
        finals = [r for r in rows if r["round_type"] == "Apparatus Finals"]
        assert len(finals) > 0, "expected some apparatus finals rows"
        for row in finals:
            assert row["aa_score"] is None, (
                f"{row['gymnast_name']} finals {row['apparatus']} has aa_score={row['aa_score']}"
            )
            assert row["aa_rank"] is None, (
                f"{row['gymnast_name']} finals {row['apparatus']} has aa_rank={row['aa_rank']}"
            )
        # Qualification rows should still have AA
        quals = [r for r in rows if r["round_type"] == "All Around - Qualification"]
        assert len(quals) > 0
        assert any(r["aa_score"] is not None for r in quals), "no qualification rows have an aa_score"

    def test_affinity_large_wag(self):
        data = load("affinity_2025.json")
        _, rows = parse_json(data)
        assert len(rows) >= 1000
        wags = set(r["gymnast_name"] for r in rows if r["discipline"] == "WAG")
        assert len(wags) > 0


class TestValidateUploadStructure:
    def test_valid_structure(self):
        data = {
            "eventOrganizations": [],
            "eventParticipants": [],
            "performanceIndividuals": [],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [],
            "events": [{"name": "Test Event"}],
        }
        assert validate_upload_structure(data) == []

    def test_missing_key(self):
        data = {"events": [{"name": "Test"}]}
        errors = validate_upload_structure(data)
        assert len(errors) > 0
        assert any("eventOrganizations" in e for e in errors)

    def test_missing_events(self):
        data = {
            "eventOrganizations": [],
            "eventParticipants": [],
            "performanceIndividuals": [],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [],
        }
        errors = validate_upload_structure(data)
        assert any("events" in e for e in errors)

    def test_empty_events(self):
        data = {
            "eventOrganizations": [],
            "eventParticipants": [],
            "performanceIndividuals": [],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [],
            "events": [],
        }
        errors = validate_upload_structure(data)
        assert any("non-empty" in e for e in errors)

    def test_event_missing_name(self):
        data = {
            "eventOrganizations": [],
            "eventParticipants": [],
            "performanceIndividuals": [],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [],
            "events": [{}],
        }
        errors = validate_upload_structure(data)
        assert any("name" in e for e in errors)

    def test_wrong_type(self):
        data = {
            "eventOrganizations": "not a list",
            "eventParticipants": [],
            "performanceIndividuals": [],
            "performanceRules": [],
            "performanceScores": [],
            "performanceResultTables": [],
            "units": [],
            "events": [{"name": "Test"}],
        }
        errors = validate_upload_structure(data)
        assert any("list" in e for e in errors)


class TestEqualDiscardedFiltering:
    def test_equal_discarded_rankings_skipped(self):
        """Rankings with equal-discarded status should be filtered out."""
        data = {
            "eventOrganizations": [{"_id": "org1", "name": "Club A"}],
            "eventParticipants": [{"_id": "p1", "name": "Gymnast A", "gnzId": "12345", "orgId": "org1"}],
            "performanceIndividuals": [{"_id": "ind1", "participantId": "p1", "unitId": "u1"}],
            "units": [{"_id": "u1", "name": "WAG STEP 5"}],
            "events": [{"name": "Test Event", "startDate": "2025-01-01", "endDate": "2025-01-02"}],
            "performanceRules": [
                {
                    "_id": "pr1",
                    "unitId": "u1",
                    "scores": [
                        {
                            "id": "sd1",
                            "nodeTree": {
                                "interface": {
                                    "outputs": [
                                        {"id": "score_val", "name": "Score"},
                                        {"id": "d_val", "name": "Difficulty"},
                                        {"id": "e_val", "name": "Execution"},
                                        {"id": "n_val", "name": "Neutral Deductions"},
                                    ],
                                },
                            },
                        },
                    ],
                    "competition": {
                        "nodeTree": {
                            "nodes": [
                                {
                                    "id": "node1",
                                    "name": "Vault",
                                    "resultSets": [{"id": "rs1"}],
                                },
                            ],
                        },
                    },
                },
            ],
            "performanceScores": [
                {
                    "_id": "s1",
                    "unitScoreId": "sd1",
                    "unitEventId": "ue1",
                    "unitPassId": "up1",
                    "entityId": "ind1",
                    "publicOutputs": {
                        "score_val": 12.0,
                        "d_val": 5.0,
                        "e_val": 7.0,
                        "n_val": 0.0,
                    },
                },
            ],
            "performanceResultTables": [
                {
                    "unitId": "u1",
                    "resultTableId": "rt1",
                    "resultSets": [
                        {
                            "id": "rs1",
                            "primaryRanking": [
                                {
                                    "entityId": "ind1",
                                    "rank": 1,
                                    "value": 12.0,
                                    "sourceItems": [
                                        {"itemId": "s1", "itemType": "score", "status": "equal-discarded"},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        event_info, rows = parse_json(data)
        # The equal-discarded ranking should be filtered, so no rows emitted
        assert len(rows) == 0, f"Expected 0 rows for equal-discarded, got {len(rows)}"

    def test_normal_ranking_still_emitted(self):
        """Same structure but with normal (non-discarded) status should produce rows."""
        data = {
            "eventOrganizations": [{"_id": "org1", "name": "Club A"}],
            "eventParticipants": [{"_id": "p1", "name": "Gymnast A", "gnzId": "12345", "orgId": "org1"}],
            "performanceIndividuals": [{"_id": "ind1", "participantId": "p1", "unitId": "u1"}],
            "units": [{"_id": "u1", "name": "WAG STEP 5"}],
            "events": [{"name": "Test Event", "startDate": "2025-01-01", "endDate": "2025-01-02"}],
            "performanceRules": [
                {
                    "_id": "pr1",
                    "unitId": "u1",
                    "scores": [
                        {
                            "id": "sd1",
                            "nodeTree": {
                                "interface": {
                                    "outputs": [
                                        {"id": "score_val", "name": "Score"},
                                        {"id": "d_val", "name": "Difficulty"},
                                        {"id": "e_val", "name": "Execution"},
                                        {"id": "n_val", "name": "Neutral Deductions"},
                                    ],
                                },
                            },
                        },
                    ],
                    "competition": {
                        "nodeTree": {
                            "nodes": [
                                {
                                    "id": "node1",
                                    "name": "Vault",
                                    "resultSets": [{"id": "rs1"}],
                                },
                            ],
                        },
                    },
                },
            ],
            "performanceScores": [
                {
                    "_id": "s1",
                    "unitScoreId": "sd1",
                    "unitEventId": "ue1",
                    "unitPassId": "up1",
                    "entityId": "ind1",
                    "publicOutputs": {
                        "score_val": 12.0,
                        "d_val": 5.0,
                        "e_val": 7.0,
                        "n_val": 0.0,
                    },
                },
            ],
            "performanceResultTables": [
                {
                    "unitId": "u1",
                    "resultTableId": "rt1",
                    "resultSets": [
                        {
                            "id": "rs1",
                            "primaryRanking": [
                                {
                                    "entityId": "ind1",
                                    "rank": 1,
                                    "value": 12.0,
                                    "sourceItems": [
                                        {"itemId": "s1", "itemType": "score"},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        event_info, rows = parse_json(data)
        assert len(rows) == 1, f"Expected 1 row for normal ranking, got {len(rows)}"