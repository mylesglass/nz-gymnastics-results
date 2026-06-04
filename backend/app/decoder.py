"""Decode opaque Scoreholder publicOutputs keys into human-readable field names."""

_OUTPUT_NAMES_TO_COLUMNS = {
    "Score": "pass_final_score",
    "Difficulty": "d_score",
    "Execution": "e_score",
    "Neutral Deductions": "neutral_deductions",
    "Execution Deductions": "_execution_deductions",
}

_STANDARD_FIELDS = {"pass_final_score", "d_score", "e_score", "neutral_deductions"}


def build_output_map(performance_rules: list[dict]) -> dict[str, dict[str, str]]:
    """Build a mapping from unitScoreId -> {opaque_output_id -> human_readable_name}.

    Each rule set contains a scores[].nodeTree.interface.outputs[] array where
    each entry has an opaque `id` and a human-readable `name`.
    """
    output_map: dict[str, dict[str, str]] = {}

    for rule in performance_rules:
        scores = rule.get("scores", [])
        for score_def in scores:
            score_id = score_def.get("id")
            if not score_id:
                continue

            interface = score_def.get("nodeTree", {}).get("interface", {})
            outputs = interface.get("outputs", [])

            id_to_name: dict[str, str] = {}
            for output in outputs:
                oid = output.get("id")
                name = output.get("name")
                if oid and name:
                    id_to_name[oid] = name

            if id_to_name:
                output_map[score_id] = id_to_name

    return output_map


def decode_public_outputs(
    public_outputs: dict,
    output_map: dict[str, str],
) -> dict[str, float | str | None]:
    """Translate opaque publicOutputs keys into standard score columns.

    Args:
        public_outputs: The raw publicOutputs dict from a performanceScore.
        output_map: The id -> human_name mapping for the relevant score definition.

    Returns:
        Dict with keys: pass_final_score, d_score, e_score, neutral_deductions.
        Unrecognised or missing values are set to None.
    """
    result: dict[str, float | str | None] = {
        "pass_final_score": None,
        "d_score": None,
        "e_score": None,
        "neutral_deductions": None,
    }

    for opaque_id, raw_value in public_outputs.items():
        human_name = output_map.get(opaque_id)
        if human_name is None:
            continue

        column = _OUTPUT_NAMES_TO_COLUMNS.get(human_name)
        if column is None:
            continue

        if column == "_execution_deductions":
            continue

        if isinstance(raw_value, (int, float)):
            result[column] = float(raw_value)
        elif isinstance(raw_value, str) and raw_value.lower() in ("dns", "dnf", "zero"):
            result[column] = raw_value.lower()

    return result


def has_dns(public_outputs: dict, output_map: dict[str, str]) -> bool:
    """Check if a score represents 'Did Not Start'."""
    for opaque_id, raw_value in public_outputs.items():
        human_name = output_map.get(opaque_id)
        if human_name == "Did Not Start" and raw_value is True:
            return True
        if isinstance(raw_value, str) and raw_value.lower() == "dns":
            return True
    return False