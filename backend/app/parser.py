"""Parse Scoreholder JSON into long-format rows for SQLite storage."""

from app.decoder import build_output_map, decode_public_outputs
from app.resolver import (
    fix_gnz_id,
    resolve_clubs,
    resolve_individuals,
    resolve_participants,
    resolve_level,
    resolve_units,
)


def _build_apparatus_map(performance_rules: list[dict]) -> dict[str, str]:
    """Map result_set_id -> apparatus name from competition node tree."""
    mapping: dict[str, str] = {}
    for rule in performance_rules:
        nodes = rule.get("competition", {}).get("nodeTree", {}).get("nodes", [])
        for node in nodes:
            raw_name = node.get("name")
            if not raw_name:
                continue
            node_name = raw_name.split(" >")[0].strip()
            for rs in node.get("resultSets", []):
                rs_id = rs.get("id")
                if rs_id:
                    mapping[rs_id] = node_name
    return mapping


def _normalise_apparatus(name: str) -> str:
    mapping = {
        "floor": "FX", "vault": "VT", "beam": "BB",
        "balance beam": "BB", "uneven bars": "UB", "u-bars": "UB",
        "pommel": "PH", "pommel horse": "PH",
        "rings": "SR", "still rings": "SR",
        "p-bars": "PB", "parallel bars": "PB",
        "h-bar": "HB", "horizontal bar": "HB",
    }
    return mapping.get(name.strip().lower(), name)


def parse_json(data: dict) -> tuple[dict, list[dict]]:
    clubs = resolve_clubs(data.get("eventOrganizations", []))
    participants = resolve_participants(data.get("eventParticipants", []))
    individuals = resolve_individuals(data.get("performanceIndividuals", []))
    units = resolve_units(data.get("units", []))
    output_map = build_output_map(data.get("performanceRules", []))
    apparatus_map = _build_apparatus_map(data.get("performanceRules", []))

    # -- Index performanceScores by _id --
    scores_by_id: dict[str, dict] = {}
    for score in data.get("performanceScores", []):
        sid = score.get("_id")
        if not sid:
            continue
        uid = score.get("unitScoreId", "")
        id_map = output_map.get(uid, {})
        decoded = decode_public_outputs(score.get("publicOutputs", {}), id_map)
        decoded["_unitEventId"] = score.get("unitEventId", "")
        decoded["_unitPassId"] = score.get("unitPassId", "")
        decoded["_entityId"] = score.get("entityId", "")
        scores_by_id[sid] = decoded

    # -- Track per-entity per-event pass IDs for correct pass numbering --
    entity_event_passes: dict[str, dict[str, set[str]]] = {}
    for sdata in scores_by_id.values():
        eid = sdata["_entityId"]
        ueid = sdata["_unitEventId"]
        entity_event_passes.setdefault(eid, {}).setdefault(ueid, set()).add(sdata["_unitPassId"])

    # -- Event metadata --
    event_raw = data.get("events", [{}])[0]
    event_info = {
        "name": event_raw.get("name", ""),
        "start_date": event_raw.get("startDate", ""),
        "end_date": event_raw.get("endDate", ""),
        "discipline": _infer_event_discipline(data),
    }

    # -- Build a lookup from result-set id -> (unitId, result table) --
    rs_to_table: dict[str, dict] = {}
    for prt in data.get("performanceResultTables", []):
        for rs in prt.get("resultSets", []):
            rs_id = rs.get("id")
            if rs_id:
                rs_to_table[rs_id] = {
                    "unitId": prt.get("unitId"),
                    "resultSets": prt.get("resultSets", []),
                    "resultTableId": prt.get("resultTableId"),
                }

    # -- Process result tables --
    # Strategy:
    #   1-set tables -> individual apparatus rankings (emit rows with score + rank)
    #   Multi-set tables -> capture AA aggregate scores only
    aa_scores: dict[str, dict] = {}
    rows: list[dict] = []

    for prt in data.get("performanceResultTables", []):
        result_sets = prt.get("resultSets", [])
        is_single_table = len(result_sets) == 1

        for rs in result_sets:
            rs_id = rs.get("id")
            rs_name = apparatus_map.get(rs_id, "")
            is_aa = rs_name.lower().startswith("all-around") or rs_name.lower() == "team"

            for ranking in rs.get("primaryRanking", []):
                entity_id = ranking.get("entityId")
                source_items = ranking.get("sourceItems", [])
                rank_value = ranking.get("rank")
                score_value = ranking.get("value")

                if not entity_id or not source_items:
                    continue

                si = source_items[0]
                item_type = si.get("itemType")
                status = si.get("status", "")
                if status == "discarded":
                    continue

                # --- Aggregate (AA / Team) results ---
                if item_type == "result-set":
                    if is_aa:
                        aa_scores[entity_id] = {
                            "aa_score": score_value,
                            "aa_rank": rank_value,
                        }
                    continue

                # --- Single-table apparatus rankings ---
                if not is_single_table:
                    continue

                if item_type != "score":
                    continue

                item_id = si.get("itemId", "")
                score_data = scores_by_id.get(item_id)
                if score_data is None:
                    continue

                # Resolve gymnast
                ind_info = individuals.get(entity_id, {})
                participant_id = ind_info.get("participant_id", "")
                unit_id = ind_info.get("unit_id", "")
                part_info = participants.get(participant_id, {})
                unit_info = units.get(unit_id, {})
                gnz_id = fix_gnz_id(part_info.get("gnz_id", ""))
                gymnast_name = part_info.get("name", "")
                club_name = clubs.get(part_info.get("org_id", ""), "")
                discipline = unit_info.get("discipline", "UNKNOWN")
                level_category = resolve_level(unit_info.get("name", ""))

                # Pass number
                pass_number = 1
                eid = score_data["_entityId"]
                ueid = score_data["_unitEventId"]
                event_pass_set = entity_event_passes.get(eid, {}).get(ueid, set())
                sorted_passes = sorted(event_pass_set)
                if len(sorted_passes) > 1:
                    pass_number = sorted_passes.index(score_data["_unitPassId"]) + 1

                aa = aa_scores.get(entity_id, {})

                row = {
                    "event_name": event_info["name"],
                    "gymnast_name": gymnast_name,
                    "gnz_id": gnz_id,
                    "club_name": club_name,
                    "discipline": discipline,
                    "level_category": level_category,
                    "division": None,
                    "apparatus": _normalise_apparatus(rs_name),
                    "pass_number": pass_number,
                    "d_score": score_data.get("d_score"),
                    "e_score": score_data.get("e_score"),
                    "neutral_deductions": score_data.get("neutral_deductions"),
                    "pass_final_score": score_data.get("pass_final_score"),
                    "apparatus_rank": rank_value,
                    "aa_score": aa.get("aa_score"),
                    "aa_rank": aa.get("aa_rank"),
                    "round_type": None,
                }
                rows.append(row)

    rows.sort(key=lambda r: (r["gymnast_name"], r["apparatus"], r["pass_number"]))
    return event_info, rows


def _infer_event_discipline(data: dict) -> str:
    disciplines = set()
    for unit in data.get("units", []):
        name = unit.get("name", "").lower()
        if "wag" in name or "step" in name:
            disciplines.add("WAG")
        if "mag" in name or "level" in name:
            disciplines.add("MAG")
    if len(disciplines) == 1:
        return disciplines.pop()
    if "WAG" in disciplines and "MAG" in disciplines:
        return "WAG+MAG"
    return "UNKNOWN"