"""Parse Scoreholder JSON into long-format rows for SQLite storage."""

import difflib
import json
import re
import unicodedata

from app.clubdata import active_path, ensure_seed
from app.decoder import build_output_map, decode_public_outputs
from app.resolver import (
    fix_gnz_id,
    resolve_clubs,
    resolve_individuals,
    resolve_participants,
    resolve_level,
    resolve_units,
)

# Load club name normalisation data (persistent copy seeded from the image).
_CLUB_DATA_PATH = active_path()
_NAME_TO_CANONICAL: dict[str, str] = {}
_NAME_TO_REGION: dict[str, str] = {}
try:
    with open(ensure_seed()) as _f:
        _club_data = json.load(_f)
    _NAME_TO_CANONICAL = {k: v["name"] for k, v in _club_data["lookup"].items()}
    _NAME_TO_REGION = {k: v["region"] for k, v in _club_data["lookup"].items()}
except (FileNotFoundError, json.JSONDecodeError):
    pass

_NAME_LEVEL_SUFFIX = re.compile(r"\s+\([^)]*\)")


def reload_club_maps() -> None:
    with open(_CLUB_DATA_PATH) as f:
        data = json.load(f)
    _NAME_TO_CANONICAL.clear()
    _NAME_TO_CANONICAL.update({k: v["name"] for k, v in data["lookup"].items()})
    _NAME_TO_REGION.clear()
    _NAME_TO_REGION.update({k: v["region"] for k, v in data["lookup"].items()})


def find_unknown_clubs(data: dict) -> list[str]:
    orgs = {org["_id"]: org["name"] for org in data.get("eventOrganizations", []) if "name" in org and org.get("_id")}

    non_gfa_units = {
        u["_id"] for u in data.get("units", [])
        if "gfa" not in (u.get("name") or "").lower()
    }

    if not non_gfa_units:
        return []

    part_to_org = {
        ep["_id"]: ep.get("organizationId")
        for ep in data.get("eventParticipants", [])
        if ep.get("_id") and ep.get("organizationId")
    }

    competitive_orgs = set()
    for pi in data.get("performanceIndividuals", []):
        pid, uid = pi.get("participantId"), pi.get("unitId")
        if pid and uid and uid in non_gfa_units:
            oid = part_to_org.get(pid)
            if oid and oid in orgs:
                competitive_orgs.add(oid)

    club_names = {orgs[oid] for oid in competitive_orgs}
    return sorted(c for c in club_names if c.lower().strip() not in _NAME_TO_CANONICAL)


def _normalise_for_match(name: str) -> str:
    """Lowercase, strip diacritics (macrons), and collapse whitespace."""
    folded = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", folded).strip().lower()


def suggest_club_mapping(unknown_clubs: list[str], threshold: float = 0.9) -> dict[str, str]:
    """Suggest a canonical club for each unknown club name.

    Exact normalized matches against known aliases always win; otherwise a
    fuzzy ratio above the threshold is required so genuinely new clubs aren't
    mis-mapped.
    """
    known_keys = list(_NAME_TO_CANONICAL)
    known_canonicals = sorted(set(_NAME_TO_CANONICAL.values()))

    suggestions: dict[str, str] = {}
    for unknown in unknown_clubs:
        folded = _normalise_for_match(unknown)
        canonical = _NAME_TO_CANONICAL.get(folded)
        if canonical:
            if canonical != unknown:
                suggestions[unknown] = canonical
            continue
        best, best_score = None, 0.0
        for candidate in known_keys + known_canonicals:
            score = difflib.SequenceMatcher(None, folded, _normalise_for_match(candidate)).ratio()
            if score > best_score:
                best, best_score = candidate, score
        if best_score >= threshold:
            suggestions[unknown] = _NAME_TO_CANONICAL.get(best.lower(), best)
    return suggestions


def _normalise_club(club_name: str, is_nationals: bool) -> str:
    """Resolve a club name to its canonical form, or to region for Nationals."""
    lower = club_name.lower().strip()
    canonical = _NAME_TO_CANONICAL.get(lower)
    if canonical is None:
        return club_name
    if is_nationals:
        region = _NAME_TO_REGION.get(lower)
        return region if region else club_name
    return canonical


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
    """Normalise apparatus name to standard short form.

    Strips division/group/final suffixes before matching:
      "Balance Beam | Over"      -> "Balance Beam" -> "BB"
      "Vault - Final"            -> "Vault"        -> "VT"
      "Floor | Group 3"          -> "Floor"        -> "FX"
      "Uneven Bars | DIVISION A" -> "Uneven Bars"  -> "UB"
    """
    clean = name.strip().lower()
    # Strip everything after " |", " -", trailing " final", " qualification", " finale"
    for sep in [" |", " -", " final", " qualification", " finale"]:
        if sep in clean:
            clean = clean.split(sep)[0].strip()
    mapping = {
        "floor": "FX", "vault": "VT", "beam": "BB",
        "balance beam": "BB", "uneven bars": "UB", "u-bars": "UB",
        "pommel": "PH", "pommel horse": "PH",
        "rings": "SR", "still rings": "SR",
        "p-bars": "PB", "parallel bars": "PB",
        "h-bar": "HB", "horizontal bar": "HB",
    }
    return mapping.get(clean, name)


MAG_APPARATUS = {"Pommel Horse", "Still Rings", "Parallel Bars", "Horizontal Bar"}
WAG_APPARATUS = {"Uneven Bars", "Balance Beam"}


def _normalise_base_apparatus(raw: str) -> str:
    clean = raw.strip()
    for sep in [" |", " -", " final", " qualification", " finale"]:
        if sep in clean.lower():
            clean = clean[:clean.lower().index(sep)].strip()
    return clean


def _infer_discipline_from_nodes(nodes: list[dict]) -> str | None:
    names: set[str] = set()
    for n in nodes:
        raw = n.get("name", "")
        if not raw:
            continue
        base = _normalise_base_apparatus(raw.split(" >")[0].strip())
        names.add(base)
    has_mag = bool(MAG_APPARATUS & names)
    has_wag = bool(WAG_APPARATUS & names)
    if has_mag:
        return "MAG"
    if has_wag:
        return "WAG"
    return None


def _build_unit_discipline_map(data: dict) -> dict[str, str]:
    rule_disc: dict[int, str] = {}
    for i, rule in enumerate(data.get("performanceRules", [])):
        nodes = rule.get("competition", {}).get("nodeTree", {}).get("nodes", [])
        d = _infer_discipline_from_nodes(nodes)
        if d:
            rule_disc[i] = d

    rs_to_rule: dict[str, int] = {}
    for i, rule in enumerate(data.get("performanceRules", [])):
        for node in rule.get("competition", {}).get("nodeTree", {}).get("nodes", []):
            for rs in node.get("resultSets", []):
                rs_id = rs.get("id")
                if rs_id:
                    rs_to_rule[rs_id] = i

    unit_rs: dict[str, set[str]] = {}
    for prt in data.get("performanceResultTables", []):
        uid = prt.get("unitId")
        if not uid:
            continue
        if uid not in unit_rs:
            unit_rs[uid] = set()
        for rs in prt.get("resultSets", []):
            rs_id = rs.get("id")
            if rs_id:
                unit_rs[uid].add(rs_id)

    result: dict[str, str] = {}
    for uid, rs_ids in unit_rs.items():
        discs: set[str] = set()
        for rs_id in rs_ids:
            ri = rs_to_rule.get(rs_id)
            if ri is not None:
                d = rule_disc.get(ri)
                if d:
                    discs.add(d)
        if len(discs) == 1:
            result[uid] = list(discs)[0]
        elif len(discs) > 1:
            result[uid] = "WAG+MAG"
    return result


def _build_apparatus_and_division_maps(performance_rules: list[dict]) -> tuple[dict[str, str], dict[str, str | None], dict[str, str]]:
    """Build maps from result_set_id -> base_apparatus, division, and raw_node_name."""
    apparatus_map: dict[str, str] = {}
    division_map: dict[str, str | None] = {}
    node_name_map: dict[str, str] = {}
    for rule in performance_rules:
        nodes = rule.get("competition", {}).get("nodeTree", {}).get("nodes", [])
        for node in nodes:
            raw_name = node.get("name")
            if not raw_name:
                continue
            base_name = raw_name.split(" >")[0].strip()
            division = _extract_division(raw_name)
            for rs in node.get("resultSets", []):
                rs_id = rs.get("id")
                if rs_id:
                    apparatus_map[rs_id] = base_name
                    division_map[rs_id] = division
                    node_name_map[rs_id] = raw_name
    return apparatus_map, division_map, node_name_map


def _extract_division(node_name: str, discipline: str = "WAG") -> str | None:
    lower = node_name.lower()

    for tag in ["international", " int"]:
        if tag in lower:
            return "INTERNATIONAL"
    for tag in ["over", "overs", "division b"]:
        if tag in lower:
            return "OVER"
    for tag in ["under", "unders", "division a"]:
        if tag in lower:
            return "UNDER"

    if " > u" in lower:
        return "UNDER"
    if " > o" in lower:
        return "OVER"

    import re
    if re.search(r"\bA\b", node_name):
        return "UNDER"
    if re.search(r"\bB\b", node_name):
        return "OVER"

    return None


def _is_competitive_level(level: str) -> bool:
    lower = level.lower()
    if not lower or lower == "none":
        return False
    if "step" in lower and any(c.isdigit() for c in lower):
        return True
    if "level" in lower and any(c.isdigit() for c in lower):
        return True
    if "international" in lower:
        return True
    if "senior open" in lower:
        return True
    if "senior" in lower and "open" not in lower:
        return True
    if "junior" in lower and "international" not in lower:
        return True
    if "youth" in lower:
        return True
    if lower in ("u16", "u18") or "under 16" in lower or "under 18" in lower:
        return True
    return False


def _infer_round_type(unit_name: str, node_name: str) -> str:
    """Determine round type from unit name and competition node name.
    
    Checks node name for qualification/final markers, then unit name
    for multi-day patterns like "Day Two Apparatus" and "App Medals".
    """
    import re
    lower_node = node_name.lower()
    if "qualification" in lower_node:
        return "All Around"
    if "final" in lower_node:
        if "all-around" in lower_node or "all around" in lower_node:
            return "All Around - Final"
        return "Apparatus Finals"

    # Multi-day meets can encode the day in the node name (e.g. "All-around - Day 2",
    # "Balance Beam - Day 2") while the unit name stays generic.
    if "day 2" in lower_node or "day two" in lower_node:
        if "all-around" in lower_node or "all around" in lower_node:
            return "All Around - Day 2"
        if "apparatus" in lower_node or "apps" in lower_node or "final" in lower_node:
            return "Apparatus Finals"
        return "Day 2"

    # Determine base round from unit name
    lower = unit_name.lower()
    if "apparatus finals" in lower:
        return "Apparatus Finals"
    if "apparatus" in lower and "all around" not in lower and "aa" not in lower and "team" not in lower:
        return "Apparatus Finals"
    if "app medals" in lower:
        return "Apparatus Finals"
    if "day 2" in lower:
        if "all around" in lower:
            return "All Around - Day 2"
        if "apparatus" in lower or "apps" in lower or "final" in lower:
            return "Apparatus Finals"
        return "Day 2"
    if "day two" in lower or "apps day two" in lower:
        return "Apparatus Finals"
    if "aa" in lower and "team" in lower:
        return "All Around, Teams"
    if "aa" in lower or "all around" in lower or "apps" in lower:
        return "All Around"
    if "team" in lower:
        return "Team"
    return "All Around"


def _sanitise_float(value: object) -> float | None:
    """Convert a value to float, or None if it's a DNS/DNF string."""
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in ("dns", "dnf", "zero"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _sanitise_rank(value: object) -> int | None:
    """Convert a rank to int, or None if it's a DNS/DNF string."""
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in ("dns", "dnf"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_json(data: dict) -> tuple[dict, list[dict]]:
    clubs = resolve_clubs(data.get("eventOrganizations", []))
    participants = resolve_participants(data.get("eventParticipants", []))

    # Compute event discipline early so it can be used as hint for units
    event_discipline_hint = _infer_event_discipline(data)

    individuals = resolve_individuals(data.get("performanceIndividuals", []))
    units = resolve_units(data.get("units", []), event_discipline_hint)
    unit_discipline_map = _build_unit_discipline_map(data)
    for uid in units:
        inferred = unit_discipline_map.get(uid)
        if inferred:
            units[uid]["discipline"] = inferred
    output_map = build_output_map(data.get("performanceRules", []))
    apparatus_map, division_map, node_name_map = _build_apparatus_and_division_maps(data.get("performanceRules", []))

    # Build unitEventId → apparatus from single-table PRTs with specific node names.
    # Used to give correct apparatus names to rows from multi-set aggregate PRTs
    # (e.g. All-around node result sets) where rs_name is generic.
    unit_event_apparatus: dict[str, str] = {}
    for _prt in data.get("performanceResultTables", []):
        if len(_prt.get("resultSets", [])) != 1:
            continue
        for _rs in _prt.get("resultSets", []):
            _rs_id = _rs.get("id")
            _app_name = apparatus_map.get(_rs_id, "")
            if not _app_name or _app_name.lower() in ("all-around", "team", ""):
                continue
            for _ue in _rs.get("usedEvents", []):
                _eid = _ue.get("eventId")
                if _eid:
                    unit_event_apparatus[_eid] = _app_name

    # -- Build entity_id -> division from resultTableConfigs --
    # Division is encoded in competition node names referenced by resultTableConfigs
    # First map: competition node id -> division
    node_division: dict[str, str | None] = {}
    node_level: dict[str, str | None] = {}
    for rule in data.get("performanceRules", []):
        for node in rule.get("competition", {}).get("nodeTree", {}).get("nodes", []):
            nid = node.get("id")
            if nid:
                node_division[nid] = _extract_division(node.get("name", ""))
                lv = resolve_level(node.get("name", ""))
                node_level[nid] = lv if lv != node.get("name", "") else None

    # Second map: entity_id -> division from performanceIndividuals
    entity_division: dict[str, str | None] = {}
    entity_level: dict[str, str | None] = {}
    # Result-table ids that actually carry a published result for each entity.
    # The resultTableConfigs registration list can include tables the gymnast
    # never scored in (e.g. a STEP 10 gymnast registered against Senior
    # International tables first), so the level/division must come from a table
    # the gymnast actually competed in.
    entity_result_tables: dict[str, set[str]] = {}
    for _prt in data.get("performanceResultTables", []):
        _rtid = _prt.get("resultTableId")
        if not _rtid:
            continue
        for _rs in _prt.get("resultSets", []):
            for _rank in _rs.get("primaryRanking", []):
                _eid = _rank.get("entityId")
                if _eid:
                    entity_result_tables.setdefault(_eid, set()).add(_rtid)
    for ind in data.get("performanceIndividuals", []):
        eid = ind.get("_id")
        if not eid:
            continue
        configs = ind.get("resultTableConfigs", [])
        present = entity_result_tables.get(eid, set())
        # Level: prefer the first config backed by an actual result that names a
        # level; otherwise fall back to the first config naming a level at all.
        level_cfg = None
        for config in configs:
            rtid = config.get("resultTableId")
            if rtid and rtid in node_level and node_level[rtid]:
                if level_cfg is None:
                    level_cfg = rtid
                if rtid in present:
                    level_cfg = rtid
                    break
        lv = node_level.get(level_cfg) if level_cfg else None
        # Division comes from the same node that determined the level so a stale
        # registration config never leaks its division onto the wrong gymnast;
        # without a level config, keep the first-config-with-division fallback.
        div = None
        if level_cfg:
            div = node_division.get(level_cfg)
        else:
            for config in configs:
                rtid = config.get("resultTableId")
                if rtid and rtid in node_division and node_division[rtid]:
                    div = node_division[rtid]
                    break
            # Also try from the old-style resultId via the division map
            if div is None:
                for config in configs:
                    rid = config.get("resultId")
                    if rid and rid in division_map and division_map[rid]:
                        div = division_map[rid]
                        break
        entity_division[eid] = div
        entity_level[eid] = lv

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

    # -- Propagate bonus across passes in the same (entityId, unitEventId) group --
    # Bonus is an apparatus-level modifier that applies to all passes for that
    # gymnast on that apparatus (e.g. both vaults), even if only one score
    # definition carries the Bonus output field.
    entity_unit_bonus: dict[tuple[str, str], float] = {}
    for sdata in scores_by_id.values():
        bonus = sdata.get("bonus")
        if bonus is not None:
            try:
                bv = float(bonus)
            except (ValueError, TypeError):
                continue
            key = (sdata["_entityId"], sdata["_unitEventId"])
            entity_unit_bonus[key] = bv
    for sdata in scores_by_id.values():
        key = (sdata["_entityId"], sdata["_unitEventId"])
        bonus = entity_unit_bonus.get(key)
        if bonus is not None:
            sdata["bonus"] = bonus
            raw = sdata.get("pass_final_score")
            if raw is not None:
                try:
                    sdata["pass_final_score"] = float(raw) + bonus
                except (ValueError, TypeError):
                    pass

    # -- Track per-entity per-event pass IDs for correct pass numbering --
    entity_event_passes: dict[str, dict[str, set[str]]] = {}
    for sdata in scores_by_id.values():
        eid = sdata["_entityId"]
        ueid = sdata["_unitEventId"]
        entity_event_passes.setdefault(eid, {}).setdefault(ueid, set()).add(sdata["_unitPassId"])

    # -- Event metadata --
    event_raw = data.get("events", [{}])[0]
    event_name = event_raw.get("name", "")
    is_nationals = "national" in event_name.lower()
    event_info = {
        "name": event_name,
        "start_date": event_raw.get("startDate", ""),
        "end_date": event_raw.get("endDate", ""),
        "discipline": _infer_event_discipline(data),
        "year": _extract_year(event_raw.get("startDate", "")),
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
    #   Deduplicate by score _id (same physical score may appear in multiple result sets)
    aa_scores: dict[tuple[str, str], dict] = {}
    rows: list[dict] = []
    emitted_score_ids: set[str] = set()

    for prt in data.get("performanceResultTables", []):
        result_sets = prt.get("resultSets", [])

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

                # Determine item_type from the first source item
                si_first = source_items[0]
                item_type = si_first.get("itemType")
                status = si_first.get("status", "")

                if status == "equal-discarded":
                    continue

                # --- Aggregate (AA / Team) results ---
                if item_type == "result-set":
                    if is_aa:
                        aa_unit_info = units.get(prt.get("unitId", ""), {})
                        aa_round_type = _infer_round_type(
                            aa_unit_info.get("name", ""),
                            node_name_map.get(rs_id, rs_name),
                        )
                        aa_scores[(entity_id, aa_round_type)] = {
                            "aa_score": score_value,
                            "aa_rank": rank_value,
                        }
                    continue

                if item_type != "score":
                    continue

                # Process every retained score source item for this ranking
                for si in source_items:
                    if si.get("status", "") == "equal-discarded":
                        continue
                    if si.get("itemType") != "score":
                        continue

                    item_id = si.get("itemId", "")
                    score_data = scores_by_id.get(item_id)
                    if score_data is None:
                        continue
                    if not isinstance(score_data.get("pass_final_score"), (int, float)):
                        continue
                    if item_id in emitted_score_ids:
                        continue
                    emitted_score_ids.add(item_id)

                    # Resolve gymnast
                    ind_info = individuals.get(entity_id, {})
                    participant_id = ind_info.get("participant_id", "")
                    unit_id = ind_info.get("unit_id", "")
                    part_info = participants.get(participant_id, {})
                    unit_info = units.get(unit_id, {})
                    gnz_id = fix_gnz_id(part_info.get("gnz_id", ""))
                    gymnast_name = _NAME_LEVEL_SUFFIX.sub("", part_info.get("name", "")).strip()
                    club_name = _normalise_club(
                        clubs.get(part_info.get("org_id", ""), ""),
                        is_nationals,
                    )
                    discipline = unit_info.get("discipline", "UNKNOWN")
                    level_category = entity_level.get(entity_id) or resolve_level(unit_info.get("name", ""))

                    # Filter out GFA (Gym For All) results: check raw unit name for markers
                    unit_name_lower = unit_info.get("name", "").lower()
                    if "gfa" in unit_name_lower or ("novice" in unit_name_lower and discipline == "WAG"):
                        continue

                    if not _is_competitive_level(level_category):
                        continue

                    # Pass number
                    pass_number = 1
                    eid = score_data["_entityId"]
                    ueid = score_data["_unitEventId"]
                    event_pass_set = entity_event_passes.get(eid, {}).get(ueid, set())
                    sorted_passes = sorted(event_pass_set)
                    if len(sorted_passes) > 1:
                        pass_number = sorted_passes.index(score_data["_unitPassId"]) + 1

                    division = division_map.get(rs_id) or entity_division.get(entity_id)
                    if division is None:
                        unit_name = unit_info.get("name", "")
                        if "step" in unit_name.lower() or "level" in unit_name.lower():
                            division = _extract_division(unit_name)
                    if level_category and "International" in level_category:
                        division = None
                    round_type = _infer_round_type(unit_info.get("name", ""), node_name_map.get(rs_id, rs_name))
                    aa = aa_scores.get((entity_id, round_type), {})

                    row = {
                        "event_name": event_info["name"],
                        "gymnast_name": gymnast_name,
                        "gnz_id": gnz_id,
                        "club_name": club_name,
                        "discipline": discipline,
                        "level_category": level_category,
                        "division": division,
                        "apparatus": _normalise_apparatus(unit_event_apparatus.get(score_data["_unitEventId"], rs_name)),
                        "pass_number": pass_number,
                        "d_score": _sanitise_float(score_data.get("d_score")),
                        "e_score": _sanitise_float(score_data.get("e_score")),
                        "neutral_deductions": _sanitise_float(score_data.get("neutral_deductions")),
                        "pass_final_score": _sanitise_float(score_data.get("pass_final_score")),
                        "start_value": _sanitise_float(score_data.get("start_value")),
                        "apparatus_rank": _sanitise_rank(rank_value),
                        "aa_score": None if "Apparatus Finals" in round_type or "Day 2" in round_type else _sanitise_float(aa.get("aa_score")),
                        "aa_rank": None if "Apparatus Finals" in round_type or "Day 2" in round_type else _sanitise_rank(aa.get("aa_rank")),
                        "round_type": round_type,
                        "bonus": _sanitise_float(score_data.get("bonus")),
                    }
                    rows.append(row)

    rows.sort(key=lambda r: (r["gymnast_name"], r["apparatus"], r["pass_number"]))

    # Backfill AA scores for rows emitted before their AA result set was processed
    # (AA result set may appear after apparatus result sets in the same table)
    entity_to_name: dict[str, str] = {}
    for eid, ind_info in individuals.items():
        pid = ind_info.get("participant_id", "")
        part_info = participants.get(pid, {})
        name = part_info.get("name", "")
        if name:
            entity_to_name[eid] = name
    for (eid, rt), aa_data in aa_scores.items():
        name = entity_to_name.get(eid)
        if not name:
            continue
        aa_score = aa_data.get("aa_score")
        aa_rank = aa_data.get("aa_rank")
        if aa_score is None:
            continue
        for row in rows:
            if row["gymnast_name"] == name and row["aa_score"] is None and row["round_type"] == rt:
                row["aa_score"] = _sanitise_float(aa_score)
                row["aa_rank"] = _sanitise_rank(aa_rank)

    return event_info, rows


def detect_participant_collisions(data: dict) -> list[dict]:
    """Detect identity collisions inside a single event export.

    Returns a list of warnings for two failure signatures:

    * **same name, 2+ distinct IDs** — two different people share a name (e.g.
      two Madison Lynches at the same meet).  These must NOT be auto-merged.
    * **same ID, 2+ distinct names** — a numeric identifier was reused for
      different people (source data-entry error).

    Club-code identifiers (``TRI``/``ARG``/``HOW``…) are ignored — they are
    not athlete IDs.
    """
    participants = list(resolve_participants(data.get("eventParticipants", [])).values())
    name_to_ids: dict[str, set[str]] = {}
    id_to_names: dict[str, set[str]] = {}
    for p in participants:
        name = p.get("name", "")
        if not name:
            continue
        gid = fix_gnz_id(p.get("gnz_id", ""))
        if not gid:
            continue
        name_to_ids.setdefault(name.lower(), set()).add(gid)
        id_to_names.setdefault(gid, set()).add(name)

    warnings: list[dict] = []
    for name_lower, ids in name_to_ids.items():
        if len(ids) > 1:
            names = sorted({p["name"] for p in participants if p["name"].lower() == name_lower})
            warnings.append({
                "type": "same_name_multiple_ids",
                "name": names[0],
                "gnz_ids": sorted(ids),
            })
    for gid, names in id_to_names.items():
        if len(names) > 1:
            warnings.append({
                "type": "same_id_multiple_names",
                "gnz_id": gid,
                "names": sorted(names),
            })
    return warnings


class ParseError(Exception):
    """Raised when uploaded JSON is structurally invalid for parsing."""


_REQUIRED_TOP_KEYS = [
    "eventOrganizations",
    "eventParticipants",
    "performanceIndividuals",
    "performanceRules",
    "performanceScores",
    "performanceResultTables",
    "units",
]

_REQUIRED_EVENT_KEYS = [
    "events",
]


def validate_upload_structure(data: dict) -> list[str]:
    """Check uploaded data has all required top-level keys.

    Returns a list of error messages (empty means valid).
    """
    errors: list[str] = []

    for key in _REQUIRED_TOP_KEYS:
        if key not in data:
            errors.append(f"Missing required top-level key: {key!r}")
        elif not isinstance(data[key], list):
            errors.append(f"Key {key!r} must be a list, got {type(data[key]).__name__}")

    for key in _REQUIRED_EVENT_KEYS:
        if key not in data:
            errors.append(f"Missing required top-level key: {key!r}")
        elif not isinstance(data[key], list) or len(data[key]) == 0:
            errors.append(f"Key {key!r} must be a non-empty list")

    if "events" in data and isinstance(data.get("events"), list) and len(data["events"]) > 0:
        event = data["events"][0]
        if not isinstance(event, dict):
            errors.append("First element of 'events' must be an object")
        else:
            if "name" not in event or not event["name"]:
                errors.append("Event must have a non-empty 'name' field")

    return errors


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


def _extract_year(start_date: str) -> int | None:
    if len(start_date) >= 4 and start_date[:4].isdigit():
        return int(start_date[:4])
    return None