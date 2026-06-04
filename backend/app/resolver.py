import re


def resolve_clubs(event_organizations: list[dict]) -> dict[str, str]:
    """Map org_id -> club_name."""
    return {org["_id"]: org["name"] for org in event_organizations if "_id" in org and "name" in org}


def resolve_participants(event_participants: list[dict]) -> dict[str, dict]:
    """Map participant_id -> {name, gnz_id, org_id}."""
    mapping: dict[str, dict] = {}
    for p in event_participants:
        pid = p.get("_id")
        if not pid:
            continue
        mapping[pid] = {
            "name": p.get("name", ""),
            "gnz_id": p.get("identifier", ""),
            "org_id": p.get("organizationId", ""),
        }
    return mapping


def resolve_individuals(performance_individuals: list[dict]) -> dict[str, dict]:
    """Map entity_id (_id of performanceIndividual) -> participant_id and unit_id."""
    mapping: dict[str, dict] = {}
    for ind in performance_individuals:
        eid = ind.get("_id")
        if not eid:
            continue
        mapping[eid] = {
            "participant_id": ind.get("participantId", ""),
            "unit_id": ind.get("unitId", ""),
        }
    return mapping


def resolve_units(units: list[dict]) -> dict[str, dict]:
    """Map unit_id -> {name, discipline}."""
    mapping: dict[str, dict] = {}
    for unit in units:
        uid = unit.get("_id")
        if not uid:
            continue
        name = unit.get("name", "")
        mapping[uid] = {
            "name": name,
            "discipline": _infer_discipline(name),
        }
    return mapping


def _infer_discipline(unit_name: str) -> str:
    lower = unit_name.lower()
    if "wag" in lower or "step" in lower:
        return "WAG"
    if "mag" in lower or "level" in lower:
        return "MAG"
    # Non-standard names: try to infer from event context
    international_terms = ["international", "junior international", "senior international",
                           "youth", "junior", "senior", "u16", "u18", "u 16", "u 18",
                           "senior open", "under 16", "under 18"]
    for term in international_terms:
        if term in lower:
            return "UNKNOWN"
    return "UNKNOWN"


def resolve_level(unit_name: str) -> str:
    """Extract the level/category string from a unit name."""
    lower = unit_name.lower()
    m = re.search(r"step\s+(\d+)", lower)
    if m:
        return f"STEP {m.group(1)}"
    m = re.search(r"level\s+(\d+)", lower)
    if m:
        return f"Level {m.group(1)}"

    # Known level keywords
    if "junior international" in lower:
        return "Junior International"
    if "senior international" in lower:
        return "Senior International"
    if "youth" in lower and "international" in lower:
        return "Youth International"
    if "senior open" in lower:
        return "Senior Open"
    if "under 16" in lower or "u16" in lower:
        return "U16"
    if "under 18" in lower or "u18" in lower:
        return "U18"
    if "senior" in lower and "open" not in lower:
        return "Senior"
    if "junior" in lower and "international" not in lower:
        return "Junior"

    return unit_name


def fix_gnz_id(identifier: str) -> str:
    """Normalise GNZ IDs (strip leading 'GS' prefix)."""
    if identifier.startswith("GS"):
        return identifier[2:]
    return identifier