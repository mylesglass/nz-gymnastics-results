import json
from pathlib import Path

import pytest

from app.parser import _infer_event_discipline, _normalise_apparatus, parse_json

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent.parent / "data-collection" / "2026"


@pytest.fixture
def hve_data():
    path = DATA_DIR / "hve-2026.json"
    if not path.exists():
        pytest.skip("hve-2026.json not found")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mgi_data():
    path = DATA_DIR / "mgi-wag-2026.json"
    if not path.exists():
        pytest.skip("mgi-wag-2026.json not found")
    with open(path) as f:
        return json.load(f)


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


class TestParseRealData:
    def test_hve_parses(self, hve_data):
        event_info, rows = parse_json(hve_data)
        assert event_info["name"] == "HVG Elementary Competition 2026"
        assert event_info["discipline"] == "WAG+MAG"
        assert len(rows) > 0
        # Should have at least 1146 score entries
        assert len(rows) >= 1000

    def test_hve_rows_have_required_fields(self, hve_data):
        _, rows = parse_json(hve_data)
        for row in rows[:50]:
            assert row["gymnast_name"]
            assert row["apparatus"]
            assert row["discipline"] in ("WAG", "MAG")
            assert row["pass_number"] >= 1
            # Every row should have a final score (might be None if DNS)
            assert "pass_final_score" in row

    def test_hve_gnz_ids_cleaned(self, hve_data):
        _, rows = parse_json(hve_data)
        for row in rows[:20]:
            gnz = row["gnz_id"]
            assert gnz is None or not gnz.startswith("GS")

    def test_mgi_parses(self, mgi_data):
        event_info, rows = parse_json(mgi_data)
        assert event_info["name"] == "Manawatu WAG Opens 2026"
        assert event_info["discipline"] == "WAG"
        assert len(rows) > 0
        assert len(rows) >= 2000

    def test_mgi_rows_have_required_fields(self, mgi_data):
        _, rows = parse_json(mgi_data)
        found_apps = set()
        for row in rows[:100]:
            found_apps.add(row["apparatus"])
            assert row["gymnast_name"]
        # Should see at least VT, UB, BB, FX
        assert "VT" in found_apps
        assert "UB" in found_apps
        assert "BB" in found_apps
        assert "FX" in found_apps

    def test_hve_apparatus_ranks_present(self, hve_data):
        _, rows = parse_json(hve_data)
        ranked = [r for r in rows if r["apparatus_rank"] is not None]
        assert len(ranked) > 0

    def test_hve_aa_scores_present(self, hve_data):
        _, rows = parse_json(hve_data)
        with_aa = [r for r in rows if r["aa_score"] is not None]
        # At least some gymnasts should have AA scores
        assert len(with_aa) > 0