import pytest

from app.decoder import build_output_map, decode_public_outputs, has_dns


def _make_rule(unit_id: str, outputs: list[dict]) -> dict:
    return {
        "_id": f"rule_{unit_id}",
        "unitId": unit_id,
        "scores": [
            {
                "id": f"score_def_{unit_id}",
                "nodeTree": {
                    "interface": {
                        "outputs": outputs,
                    },
                },
            },
        ],
    }


class TestBuildOutputMap:
    def test_builds_mapping_from_outputs(self):
        rules = [
            _make_rule("u1", [
                {"id": "abc123", "name": "Score"},
                {"id": "def456", "name": "Difficulty"},
                {"id": "ghi789", "name": "Execution"},
                {"id": "jkl012", "name": "Neutral Deductions"},
            ]),
        ]
        result = build_output_map(rules)
        assert result == {
            "score_def_u1": {
                "abc123": "Score",
                "def456": "Difficulty",
                "ghi789": "Execution",
                "jkl012": "Neutral Deductions",
            },
        }

    def test_empty_rules(self):
        assert build_output_map([]) == {}

    def test_skips_score_def_without_id(self):
        rules = [
            {
                "scores": [
                    {"nodeTree": {"interface": {"outputs": [{"id": "x", "name": "Score"}]}}},
                ],
            },
        ]
        assert build_output_map(rules) == {}

    def test_multiple_rules(self):
        rules = [
            _make_rule("wag", [{"id": "o1", "name": "Score"}]),
            _make_rule("mag", [{"id": "o2", "name": "Difficulty"}]),
        ]
        result = build_output_map(rules)
        assert "score_def_wag" in result
        assert "score_def_mag" in result


class TestDecodePublicOutputs:
    def test_decode_normal_score(self):
        output_map = {
            "abc123": "Score",
            "def456": "Difficulty",
            "ghi789": "Execution",
            "jkl012": "Neutral Deductions",
            "xyz999": "Execution Deductions",
        }
        public = {
            "abc123": 13.5,
            "def456": 5.0,
            "ghi789": 8.5,
            "jkl012": 0,
            "xyz999": 0.5,
        }
        result = decode_public_outputs(public, output_map)
        assert result["pass_final_score"] == 13.5
        assert result["d_score"] == 5.0
        assert result["e_score"] == 8.5
        assert result["neutral_deductions"] == 0.0

    def test_decode_dns_string(self):
        output_map = {
            "dns_key": "Did Not Start",
            "score_key": "Score",
            "diff_key": "Difficulty",
            "exec_key": "Execution",
        }
        public = {
            "dns_key": "dns",
            "score_key": "dns",
            "diff_key": 10.0,
            "exec_key": "dns",
        }
        result = decode_public_outputs(public, output_map)
        assert result["pass_final_score"] == "dns"

    def test_decode_empty_outputs(self):
        result = decode_public_outputs({}, {"a": "Score"})
        assert result["pass_final_score"] is None

    def test_unrecognised_keys_ignored(self):
        output_map = {"known": "Score"}
        public = {"known": 12.0, "unknown": 99.0}
        result = decode_public_outputs(public, output_map)
        assert result["pass_final_score"] == 12.0

    def test_execution_deductions_excluded(self):
        output_map = {
            "score": "Score",
            "ded": "Execution Deductions",
        }
        public = {"score": 12.0, "ded": 0.8}
        result = decode_public_outputs(public, output_map)
        assert "pass_final_score" in result
        assert result["pass_final_score"] == 12.0

    def test_start_value_decoded(self):
        output_map = {"sv": "Start Value"}
        public = {"sv": 10.0}
        result = decode_public_outputs(public, output_map)
        assert result["start_value"] == 10.0


class TestHasDns:
    def test_dns_true_when_dns_string_present(self):
        output_map = {"k1": "Did Not Start"}
        assert has_dns({"k1": "dns"}, output_map) is True

    def test_dns_true_when_dns_boolean(self):
        output_map = {"k1": "Did Not Start"}
        assert has_dns({"k1": True}, output_map) is True

    def test_dns_false_when_no_dns(self):
        output_map = {"k1": "Score"}
        assert has_dns({"k1": 12.0}, output_map) is False

    def test_dns_false_on_empty(self):
        assert has_dns({}, {"k1": "Did Not Start"}) is False