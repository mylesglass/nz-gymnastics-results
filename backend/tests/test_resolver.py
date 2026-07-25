import pytest

from app.resolver import (
    fix_gnz_id,
    resolve_clubs,
    resolve_individuals,
    resolve_level,
    resolve_participants,
    resolve_units,
)


class TestResolveClubs:
    def test_basic_mapping(self):
        orgs = [
            {"_id": "org1", "name": "CSG"},
            {"_id": "org2", "name": "HVG"},
        ]
        assert resolve_clubs(orgs) == {"org1": "CSG", "org2": "HVG"}

    def test_empty_list(self):
        assert resolve_clubs([]) == {}

    def test_skips_entries_without_id(self):
        orgs = [{"name": "NoID"}, {"_id": "x", "name": "Valid"}]
        result = resolve_clubs(orgs)
        assert result == {"x": "Valid"}


class TestResolveParticipants:
    def test_basic(self):
        parts = [
            {"_id": "p1", "name": "Alice", "identifier": "GNZ001", "organizationId": "org1"},
        ]
        result = resolve_participants(parts)
        assert result == {
            "p1": {"name": "Alice", "gnz_id": "GNZ001", "org_id": "org1"},
        }

    def test_empty(self):
        assert resolve_participants([]) == {}

    def test_missing_optional_fields(self):
        parts = [{"_id": "p1", "name": "Bob"}]
        result = resolve_participants(parts)
        assert result["p1"]["gnz_id"] == ""
        assert result["p1"]["org_id"] == ""


class TestResolveIndividuals:
    def test_basic(self):
        inds = [
            {"_id": "e1", "participantId": "p1", "unitId": "u1"},
        ]
        result = resolve_individuals(inds)
        assert result == {
            "e1": {"participant_id": "p1", "unit_id": "u1"},
        }

    def test_maps_multiple_individuals_for_same_participant(self):
        inds = [
            {"_id": "e1", "participantId": "p1", "unitId": "u1"},
            {"_id": "e2", "participantId": "p1", "unitId": "u2"},
        ]
        result = resolve_individuals(inds)
        assert result["e1"]["unit_id"] == "u1"
        assert result["e2"]["unit_id"] == "u2"

    def test_empty(self):
        assert resolve_individuals([]) == {}


class TestResolveUnits:
    def test_wag_unit(self):
        units = [{"_id": "u1", "name": "WAG STEP 5 Green AA"}]
        result = resolve_units(units)
        assert result["u1"]["discipline"] == "WAG"
        assert result["u1"]["name"] == "WAG STEP 5 Green AA"

    def test_mag_unit(self):
        units = [{"_id": "u2", "name": "MAG Level 4"}]
        result = resolve_units(units)
        assert result["u2"]["discipline"] == "MAG"

    def test_inferred_via_step_keyword(self):
        units = [{"_id": "u1", "name": "STEP 1 Green"}]
        result = resolve_units(units)
        assert result["u1"]["discipline"] == "WAG"

    def test_inferred_via_level_keyword(self):
        units = [{"_id": "u2", "name": "Level 2"}]
        result = resolve_units(units)
        assert result["u2"]["discipline"] == "MAG"

    def test_unknown(self):
        units = [{"_id": "u3", "name": "Something Else"}]
        result = resolve_units(units)
        assert result["u3"]["discipline"] == "UNKNOWN"


class TestResolveLevel:
    def test_wag_step(self):
        assert resolve_level("WAG STEP 5 Green AA") == "STEP 5"

    def test_wag_step_no_extra(self):
        assert resolve_level("STEP 1") == "STEP 1"

    def test_mag_level(self):
        assert resolve_level("MAG Level 4") == "Level 4"

    def test_default_fallback(self):
        assert resolve_level("UNKNOWN") == "UNKNOWN"

    def test_junior_international_node(self):
        assert resolve_level("All-Around | Junior International") == "Junior International"

    def test_senior_international_node(self):
        assert resolve_level("All-Around | Senior International") == "Senior International"

    def test_international_with_qualifier(self):
        assert resolve_level("Vault | Junior International Qualification") == "Junior International"

    def test_si_abbreviation(self):
        assert resolve_level("WAG DIVISION A | SI") == "Senior International"

    def test_ji_abbreviation(self):
        assert resolve_level("WAG DIVISION A | JI") == "Junior International"

    def test_composite_unit_falls_to_step(self):
        assert resolve_level("WAG DIVISION A | STEP 10, JI, SI") == "STEP 10"


class TestFixGnzId:
    def test_strips_gs_prefix(self):
        assert fix_gnz_id("GS12345") == "12345"

    def test_no_prefix(self):
        assert fix_gnz_id("12345") == "12345"

    def test_empty(self):
        assert fix_gnz_id("") == ""

    def test_club_code_returns_empty(self):
        assert fix_gnz_id("ARG") == ""
        assert fix_gnz_id("NHG") == ""

    def test_strips_gnz_prefix(self):
        assert fix_gnz_id("GNZ699917") == "699917"

    def test_strips_ggs_prefix(self):
        assert fix_gnz_id("GGS200576") == "200576"