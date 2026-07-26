import re
import unicodedata


def _clean_name(raw: str) -> str:
    name = (raw or "").replace("\ufffd", "").replace("\u00a0", " ")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"\s+", " ", name).strip()
    return " ".join(w.capitalize() for w in name.split())


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
            "name": _clean_name(p.get("name", "")),
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


def resolve_units(units: list[dict], event_discipline_hint: str | None = None) -> dict[str, dict]:
    """Map unit_id -> {name, discipline}.

    When a unit name doesn't clearly indicate WAG or MAG, the
    event_discipline_hint is used as a fallback.
    """
    mapping: dict[str, dict] = {}
    for unit in units:
        uid = unit.get("_id")
        if not uid:
            continue
        name = unit.get("name", "")
        mapping[uid] = {
            "name": name,
            "discipline": _infer_discipline(name, event_discipline_hint),
        }
    return mapping


def _infer_discipline(unit_name: str, event_hint: str | None = None) -> str:
    lower = unit_name.lower()
    if "wag" in lower or "step" in lower:
        return "WAG"
    if "mag" in lower or "level" in lower:
        return "MAG"
    if event_hint:
        return event_hint
    return "UNKNOWN"


def resolve_level(unit_name: str) -> str:
    """Extract the level/category string from a unit name."""
    lower = unit_name.lower()

    # Check full international phrases first (before step/level to handle node names)
    if "junior international" in lower:
        return "Junior International"
    if "senior international" in lower:
        return "Senior International"
    if "youth international" in lower:
        return "Youth International"

    m = re.search(r"step\s*(\d+)", lower)
    if m:
        return f"STEP {m.group(1)}"
    m = re.search(r"level\s*(\d+)", lower)
    if m:
        return f"Level {m.group(1)}"

    # Known level keywords (check long matches first)
    if "senior open" in lower:
        return "Senior Open"
    if "youth" in lower:
        return "Youth International"
    if "under 16" in lower or "u16" in lower:
        return "U16"
    if "under 18" in lower or "u18" in lower:
        return "U18"
    if "senior" in lower and "open" not in lower:
        return "Senior"
    if "junior" in lower and "international" not in lower:
        return "Junior"

    # Abbreviation checks (word-boundary)
    if re.search(r"\bsi\b", lower):
        return "Senior International"
    if re.search(r"\bji\b", lower):
        return "Junior International"

    return unit_name


def fix_gnz_id(identifier: str) -> str:
    """Normalise GNZ IDs (strip leading prefixes, reject non-numeric)."""
    raw = (identifier or "").strip()
    for prefix in ("GS", "GNZ", "GGS"):
        if raw.startswith(prefix):
            raw = raw.removeprefix(prefix)
    if raw.isdigit():
        return raw
    return ""