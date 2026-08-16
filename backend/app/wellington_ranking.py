"""Wellington regional ranking computation for team selection.

Classifies competitions by name patterns, applies step/discipline-specific
selection rules, and ranks Wellington-attached gymnasts.
"""

from collections import defaultdict

from app.database import get_session
from app.models import Athlete, Event, LongScore
from app.transformer import STANDARD_APPARATUS, _find_region, _use_vault_average

# ── Event name patterns ──────────────────────────────────────────────
# Matched case-insensitively against raw event_name in the DB.

_REGIONAL_PATTERNS = ["wellington champ", "central"]
_CLUB_PATTERNS = ["capital", "rimutaka"]


def _classify_event(event_name: str) -> str:
    """Classify an event as ``"regional"``, ``"club"``, or ``"away"``."""
    lower = event_name.lower()
    if any(p in lower for p in _REGIONAL_PATTERNS):
        return "regional"
    if any(p in lower for p in _CLUB_PATTERNS):
        return "club"
    return "away"


# ── Step-range configs ───────────────────────────────────────────────

_STEP_CONFIGS: list[dict] = [
    {
        "key": "wag_step_5_6",
        "label": "WAG STEP 5–6",
        "steps": {"STEP 5", "STEP 6"},
        "disciplines": {"WAG"},
        "gnz_qualifying_score": 50.0,
        "gnz_requires_two": True,
        "gnz_requires_away": True,
        "wellington_qualifying_score": 53.0,
        "selection": "wag_step_5_6",
        "club_events": True,
        "away_required": True,
    },
    {
        "key": "wag_step_7_10",
        "label": "WAG STEP 7–10",
        "steps": {"STEP 7", "STEP 8", "STEP 9", "STEP 10"},
        "disciplines": {"WAG"},
        "gnz_qualifying_score": 43.0,
        "gnz_requires_two": True,
        "gnz_requires_away": False,
        "wellington_qualifying_score": None,
        "selection": "wag_step_7_10",
        "club_events": False,
        "away_required": False,
        "specialist_steps": {"STEP 8", "STEP 9", "STEP 10"},
        "apparatus_qualifying_score": 11.0,
        "apparatus_qualifying_count": 2,
    },
    {
        "key": "mag_level_4_6",
        "label": "MAG Level 4–6",
        "steps": {"Level 4", "Level 5", "Level 6"},
        "disciplines": {"MAG"},
        "gnz_qualifying_score": None,
        "gnz_requires_two": False,
        "gnz_requires_away": False,
        "wellington_qualifying_score": 58.0,
        "selection": "mag_level_4_6",
        "club_events": True,
        "away_required": True,
    },
    {
        "key": "mag_level_7_plus",
        "label": "MAG Level 7+",
        "steps": {"Level 7", "Level 8", "Level 9", "Senior Open", "U18"},
        "disciplines": {"MAG"},
        "gnz_qualifying_score": None,
        "gnz_requires_two": False,
        "gnz_requires_away": False,
        "wellington_qualifying_score": 63.0,
        "selection": "mag_level_7_plus",
        "club_events": False,
        "away_required": False,
        "specialist_steps": {"Level 7", "Level 8", "Level 9", "Senior Open", "U18"},
        "apparatus_qualifying_score": 11.5,
        "apparatus_qualifying_count": 1,
    },
    {
        "key": "wag_youth_international",
        "label": "WAG Youth International",
        "steps": {"Youth International"},
        "disciplines": {"WAG"},
        "gnz_qualifying_score": 42.5,
        "gnz_requires_two": False,
        "gnz_requires_away": False,
        "wellington_qualifying_score": None,
        "selection": "international",
        "club_events": False,
        "away_required": False,
        "marks_required": 1,
    },
    {
        "key": "wag_junior_international",
        "label": "WAG Junior International",
        "steps": {"Junior International"},
        "disciplines": {"WAG"},
        "gnz_qualifying_score": 43.0,
        "gnz_requires_two": False,
        "gnz_requires_away": False,
        "wellington_qualifying_score": None,
        "selection": "international",
        "club_events": False,
        "away_required": False,
        "marks_required": 1,
        "specialist_steps": {"Junior International"},
        "apparatus_qualifying_scores": {"VT": 12.2, "UB": 10.4, "BB": 10.5, "FX": 11.4},
        "apparatus_qualifying_count": 1,
    },
    {
        "key": "wag_senior_international",
        "label": "WAG Senior International",
        "steps": {"Senior International"},
        "disciplines": {"WAG"},
        "gnz_qualifying_score": 45.0,
        "gnz_requires_two": False,
        "gnz_requires_away": False,
        "wellington_qualifying_score": None,
        "selection": "international",
        "club_events": False,
        "away_required": False,
        "marks_required": 1,
        "specialist_steps": {"Senior International"},
        "apparatus_qualifying_scores": {"VT": 12.5, "UB": 11.3, "BB": 11.2, "FX": 11.4},
        "apparatus_qualifying_count": 1,
    },
]


# ── Qualification checks ────────────────────────────────────────────

def _is_gnz_qualified(all_events: list[dict], config: dict) -> bool:
    """Check GNZ qualification across all events, not just selected marks."""
    threshold = config.get("gnz_qualifying_score")
    if threshold is None:
        return True
    qualifying = [e for e in all_events if e["score"] >= threshold]
    if config.get("gnz_requires_two", False):
        if len(qualifying) < 2:
            return False
        if config.get("gnz_requires_away", False):
            if not any(_classify_event(e["event_name"]) == "away" for e in qualifying):
                return False
        return True
    return len(qualifying) >= 1


def _is_wellington_qualified(all_events: list[dict], config: dict) -> bool:
    """Check Wellington qualification score across all events."""
    threshold = config.get("wellington_qualifying_score")
    if threshold is None:
        return True
    return any(e["score"] >= threshold for e in all_events)


def _gnz_failure_reason(config: dict, all_events: list[dict]) -> str:
    """Human-readable reason for GNZ qualifier failure."""
    threshold = config.get("gnz_qualifying_score")
    if threshold is None:
        return ""
    qualifying = [e for e in all_events if e["score"] >= threshold]
    count = len(qualifying)
    needs_two = config.get("gnz_requires_two", False)
    needs_away = config.get("gnz_requires_away", False)

    if needs_two:
        if count < 2:
            msg = f"Has achieved Gymnastics NZ qualifying mark {threshold:.3f} {count} time(s) — needs 2"
            if needs_away:
                msg += " (one must be outside Wellington)"
            return msg
        if needs_away and not any(_classify_event(e["event_name"]) == "away" for e in qualifying):
            return f"Has achieved Gymnastics NZ qualifying mark {threshold:.3f} {count} times but none outside Wellington — needs at least one away"
    return f"Has not achieved Gymnastics NZ qualifying mark {threshold:.3f}"


def _wgtn_failure_reason(config: dict) -> str:
    """Human-readable reason for Wellington qualifier failure."""
    threshold = config.get("wellington_qualifying_score")
    if threshold is None:
        return ""
    return f"Has not achieved Wellington qualifying mark {threshold:.3f}"


def _selection_checks(
    config: dict, n_regional: int, n_club: int, n_away: int, n_total: int,
) -> list[dict]:
    """Return the competition-mix requirements checklist for a config.

    Each item is ``{label, met, detail}`` where ``detail`` shows the current
    count out of the requirement (``"x of y"``).
    """
    key = config["selection"]

    if config.get("marks_required", 3) == 1:
        return []

    if key == "wag_step_5_6":
        named = n_regional + n_club
        return [
            {"label": "Regional event", "met": n_regional >= 1, "detail": f"{n_regional} of 1"},
            {"label": "2nd named event (regional/Capital/Rimutaka)", "met": named >= 2, "detail": f"{named} of 2"},
            {"label": "Away competition", "met": n_away >= 1, "detail": f"{n_away} of 1"},
        ]
    if key == "wag_step_7_10":
        return [
            {"label": "Regional event", "met": n_regional >= 1, "detail": f"{n_regional} of 1"},
            {"label": "3 competitions", "met": n_total >= 3, "detail": f"{n_total} of 3"},
            {"label": "Away competition", "met": n_away >= 1, "detail": f"{n_away} of 1"},
        ]
    if key == "mag_level_4_6":
        named = n_regional + n_club
        return [
            {"label": "2 Wellington events (regional or Capital)", "met": named >= 2, "detail": f"{named} of 2"},
            {"label": "Away competition", "met": n_away >= 1, "detail": f"{n_away} of 1"},
        ]
    # mag_level_7_plus
    return [
        {"label": "Regional event", "met": n_regional >= 1, "detail": f"{n_regional} of 1"},
        {"label": "2 away competitions", "met": n_away >= 2, "detail": f"{n_away} of 2"},
    ]


def _qualifier_checks(config: dict, gnz_ok: bool, wgtn_ok: bool) -> list[dict]:
    """Return intent/qualifier checklist items for a config, if applicable."""
    checks: list[dict] = []
    gnz = config.get("gnz_qualifying_score")
    if gnz is not None:
        checks.append({
            "label": f"Gymnastics NZ qualifying mark ({gnz:.3f})",
            "met": gnz_ok,
            "detail": "",
        })
    wgtn = config.get("wellington_qualifying_score")
    if wgtn is not None:
        checks.append({
            "label": f"Wellington qualifying mark ({wgtn:.3f})",
            "met": wgtn_ok,
            "detail": "",
        })
    return checks


def _dropped_reasons(
    intent_filter: bool, intent_submitted: bool, warnings: list[str],
) -> list[str]:
    """Reasons a selection-capable athlete isn't on the ranking."""
    reasons: list[str] = []
    if intent_filter and not intent_submitted:
        reasons.append("Hasn't submitted intent yet")
    reasons.extend(warnings)
    if not reasons:
        reasons.append("Doesn't meet the current selection criteria")
    return reasons


def _unranked_row(
    name: str, slug: str, gnz_id: str, club: str, region: str,
    scores: list[float | None], competition_names: list[str],
    categories: list[str], apparatus: list[list[dict]],
    competitions: int, n_regional: int, n_club: int, n_away: int,
    why: str, checks: list[dict], intent_submitted: bool,
) -> dict:
    """Build a unified ``not_ranked`` row shared by all non-ranked athletes."""
    return {
        "name": name,
        "slug": slug,
        "gnz_id": gnz_id,
        "club": club,
        "region": region,
        "scores": scores,
        "competition_names": competition_names,
        "categories": categories,
        "apparatus": apparatus,
        "competitions": competitions,
        "regional_count": n_regional,
        "club_count": n_club,
        "away_count": n_away,
        "why": why,
        "checks": checks,
        "intent_submitted": intent_submitted,
    }


def _get_config(discipline: str, step: str) -> dict | None:
    for cfg in _STEP_CONFIGS:
        if discipline in cfg["disciplines"] and step in cfg["steps"]:
            return cfg
    return None


# ── Per-competition score computation ────────────────────────────────

def _compute_competition_score(
    scores: list, step: str,
) -> float:
    """Produce a single competition score from one event+round_type group.

    Same logic as the national ranking endpoint: prefer max AA, otherwise
    sum apparatus scores with vault averaging rules.
    """
    aa_values = [s.aa_score for s in scores if s.aa_score is not None]
    if aa_values:
        return float(max(aa_values))

    app_scores: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        if s.pass_final_score is not None:
            app_scores.setdefault(s.apparatus or "", []).append(
                float(s.pass_final_score)
            )

    total = 0.0
    for app, vals in app_scores.items():
        if app == "VT" and len(vals) > 1:
            if _use_vault_average(step, scores[0].round_type or ""):
                total += sum(vals) / len(vals)
            else:
                total += max(vals)
        else:
            total += sum(vals)
    return total


# ── Selection rules per step range ───────────────────────────────────

def _pick_distinct(
    pool: list[dict], used_ids: set[int],
) -> dict | None:
    """Return the first event from *pool* whose ``event_id`` is not in *used_ids*, or ``None``."""
    for e in pool:
        if e["event_id"] not in used_ids:
            return e
    return None


def _select_wag_step_5_6(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict | None]:
    """Best regional → next best from remaining 3 named events → best away.

    Returns a length-3 list with ``None`` for slots that couldn't be filled.
    """
    score1 = regional[0] if regional else None
    used = {score1["event_id"]} if score1 else set()
    named = sorted(regional + club, key=lambda x: -x["score"])

    score2 = _pick_distinct(named, used)
    if score2:
        used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    return [score1, score2, score3]


def _select_wag_step_7_10(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict | None]:
    """Best regional → best two endorsed competitions (1 must be away).

    Returns a length-3 list with ``None`` for slots that couldn't be filled.
    """
    score1 = regional[0] if regional else None
    used = {score1["event_id"]} if score1 else set()
    endorsed = [e for e in all_events if e["event_id"] not in used]
    endorsed_away = [e for e in endorsed if e["event_id"] in {a["event_id"] for a in away}]

    score2 = _pick_distinct(endorsed, used)
    if score2:
        used.add(score2["event_id"])

    # At least one of the two endorsed marks must be away
    if score2 and score2["event_id"] not in {a["event_id"] for a in away}:
        score3 = _pick_distinct(endorsed_away, used)
    else:
        score3 = _pick_distinct(endorsed, used)
    return [score1, score2, score3]


def _select_mag_level_4_6(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict | None]:
    """Best two Wellington scores → best away.

    Returns a length-3 list with ``None`` for slots that couldn't be filled.
    """
    wellington = sorted(regional + club, key=lambda x: -x["score"])

    score1 = _pick_distinct(wellington, set())
    used = {score1["event_id"]} if score1 else set()

    score2 = _pick_distinct(wellington, used)
    if score2:
        used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    return [score1, score2, score3]


def _select_mag_level_7_plus(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict | None]:
    """Best regional → best two away.

    Returns a length-3 list with ``None`` for slots that couldn't be filled.
    """
    score1 = regional[0] if regional else None
    used = {score1["event_id"]} if score1 else set()

    score2 = _pick_distinct(away, used)
    if score2:
        used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    return [score1, score2, score3]


def _select_international(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict | None]:
    """Single highest AA mark — no competition-mix selection.

    Returns a length-3 list with the best score first and ``None`` slots
    after, so a single-mark config fills exactly one slot.
    """
    best = max(all_events, key=lambda x: x["score"]) if all_events else None
    return [best, None, None]


_SELECTORS = {
    "wag_step_5_6": _select_wag_step_5_6,
    "wag_step_7_10": _select_wag_step_7_10,
    "mag_level_4_6": _select_mag_level_4_6,
    "mag_level_7_plus": _select_mag_level_7_plus,
    "international": _select_international,
}


# ── Main entry point ─────────────────────────────────────────────────

def compute_wellington_rankings(
    year: int, discipline: str, step: str,
    gnz_qualifier: bool = True, wellington_qualifier: bool = True,
    intents: set[str] | None = None, intent_filter: bool = True,
) -> dict:
    """Return ranking dict with keys ``rankings``, ``not_ranked``, ``year``,
    ``step``, ``discipline``.

    Each ranking entry contains:
      name, gnz_id, club, region, scores[3], competitions[3],
      categories[3], total, average

    ``not_ranked`` lists Wellington athletes who aren't on the ranking and
    why: either they can't yet form the required 3-mark selection (too few
    competitions / missing event mix) or they were dropped by the active
    toggles (intent / GNZ / Wellington qualifier). ``why`` is the headline
    reason and ``checks`` is a ✓/✗ requirements checklist (competition mix,
    intent, and qualifiers) for getting onto the ranking.
    """
    config = _get_config(discipline, step)
    if config is None:
        return {
            "rankings": [],
            "not_ranked": [],
            "apparatus_specialists": [],
            "year": year,
            "step": step,
            "discipline": discipline,
        }

    session = get_session()
    try:
        event_ids = [
            e.id
            for e in session.query(Event).filter(
                Event.year == year,
                Event.is_national == False,  # noqa: E712
            ).all()
        ]
        if not event_ids:
            return {
                "rankings": [],
                "not_ranked": [],
                "apparatus_specialists": [],
                "year": year,
                "step": step,
                "discipline": discipline,
            }

        rows = (
            session.query(
                LongScore.gymnast_name,
                LongScore.athlete_id,
                LongScore.gnz_id,
                LongScore.club_name,
                LongScore.event_id,
                LongScore.event_name,
                LongScore.apparatus,
                LongScore.pass_number,
                LongScore.pass_final_score,
                LongScore.aa_score,
                LongScore.round_type,
                LongScore.d_score,
                LongScore.e_score,
                LongScore.neutral_deductions,
                LongScore.bonus,
                LongScore.start_value,
                LongScore.apparatus_rank,
            )
            .filter(
                LongScore.event_id.in_(event_ids),
                LongScore.level_category == step,
                LongScore.discipline == discipline,
                LongScore.pass_final_score.isnot(None),
            )
            .all()
        )

        athletes = {a.id: a for a in session.query(Athlete).all()}

        # 1. Group by (gymnast, event, round_type) → competition scores
        raw_groups: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (
                r.athlete_id or r.gymnast_name, r.gymnast_name, r.gnz_id, r.club_name,
                r.event_id, r.event_name, r.round_type,
            )
            raw_groups[key].append(r)

        # 2. Per gymnast: collect best score per event
        #    (across round_types — "best day of two-day competition")
        gymnast_events: dict[str, dict[int, list[dict]]] = defaultdict(
            lambda: defaultdict(list),
        )
        # Per (gymnast, apparatus, event): best apparatus score for that
        # competition. Multiple round types of a two-day competition merge to
        # the best score for the event. Used for specialist qualification.
        apparatus_events: dict[str, dict[str, dict[int, dict]]] = defaultdict(
            lambda: defaultdict(dict),
        )
        gymnast_meta: dict[str, dict[str, str]] = {}
        for key, scores in raw_groups.items():
            a_key = key[0]
            name = key[1]
            event_id = key[4]
            comp_score = _compute_competition_score(scores, step)

            apparatus = [
                {
                    "app": s.apparatus or "",
                    "pass_number": s.pass_number,
                    "d": s.d_score,
                    "e": s.e_score,
                    "n": s.neutral_deductions,
                    "total": float(s.pass_final_score) if s.pass_final_score else None,
                    "bonus": float(s.bonus) if s.bonus else None,
                    "rank": s.apparatus_rank,
                    "start_value": float(s.start_value) if s.start_value else None,
                }
                for s in scores
                if s.apparatus in STANDARD_APPARATUS
            ]

            # Event-level apparatus score for specialist tracking. Vault
            # aggregates multiple passes per the AA rules (average or best).
            # Unresolvable "All-around" apparatus is skipped so it can never
            # qualify as a specialist.
            event_app_scores: dict[str, float] = {}
            vt_totals: list[float] = []
            for p in apparatus:
                if p["total"] is None:
                    continue
                if p["app"] == "VT":
                    vt_totals.append(p["total"])
                else:
                    prev = event_app_scores.get(p["app"])
                    if prev is None or p["total"] > prev:
                        event_app_scores[p["app"]] = p["total"]
            if vt_totals:
                if _use_vault_average(step, key[6]):
                    event_app_scores["VT"] = sum(vt_totals) / len(vt_totals)
                else:
                    event_app_scores["VT"] = max(vt_totals)
            for app, score in event_app_scores.items():
                prev = apparatus_events[a_key][app].get(event_id)
                if prev is None or score > prev["score"]:
                    apparatus_events[a_key][app][event_id] = {
                        "score": score,
                        "event_name": key[5],
                    }

            if a_key not in gymnast_meta:
                gymnast_meta[a_key] = {"name": name, "gnz_id": key[2] or "", "club": key[3] or ""}
            else:
                if not gymnast_meta[a_key]["gnz_id"] and key[2]:
                    gymnast_meta[a_key]["gnz_id"] = key[2]
                if not gymnast_meta[a_key]["club"] and key[3]:
                    gymnast_meta[a_key]["club"] = key[3]

            gymnast_events[a_key][event_id].append({
                "score": comp_score,
                "event_name": key[5],
                "event_id": event_id,
                "gnz_id": key[2] or "",
                "club": key[3] or "",
                "apparatus": apparatus,
            })

        # Canonical display names for athlete-keyed gymnasts.
        for a_key, meta in gymnast_meta.items():
            if isinstance(a_key, int) and a_key in athletes:
                meta["name"] = athletes[a_key].canonical_name or meta["name"]

        # 3. Per gymnast: take best score per event, classify, select top 3
        rankings = []
        not_ranked = []
        for a_key, event_map in gymnast_events.items():
            meta = gymnast_meta.get(a_key, {"name": str(a_key), "gnz_id": "", "club": ""})
            name = meta["name"]
            slug = athletes[a_key].slug if isinstance(a_key, int) and a_key in athletes else ""
            all_events_list = []
            for eid, scores_list in event_map.items():
                best = max(scores_list, key=lambda x: x["score"])
                best["category"] = _classify_event(best["event_name"])
                all_events_list.append(best)

            all_events_list.sort(key=lambda x: -x["score"])
            regionals = [e for e in all_events_list if e["category"] == "regional"]
            clubs = [e for e in all_events_list if e["category"] == "club"]
            aways = [e for e in all_events_list if e["category"] == "away"]

            selector = _SELECTORS.get(config["selection"])
            if selector is None:
                continue
            selected = selector(regionals, clubs, aways, all_events_list)
            if selected is None:
                continue
            marks_required = config.get("marks_required", 3)
            best_gnz_id = next(
                (s["gnz_id"] for s in all_events_list if s["gnz_id"]), "",
            )
            intent_submitted = (
                intents is None
                or a_key in intents
                or (best_gnz_id and best_gnz_id in intents)
            )
            if None in selected[:marks_required]:
                gnz_id = meta["gnz_id"]
                club = meta["club"]
                region = _find_region(club)
                if region != "Wellington":
                    continue
                count = len(all_events_list)
                n_regional = len(regionals)
                n_club = len(clubs)
                n_away = len(aways)
                slot_scores = [round(s["score"], 3) if s else None for s in selected]
                slot_names = [s["event_name"] if s else "" for s in selected]
                slot_cats = [s["category"] if s else "" for s in selected]
                slot_apps = [s.get("apparatus", []) if s else [] for s in selected]
                if count < marks_required:
                    why = f"Needs {marks_required} eligible competition{'s' if marks_required != 1 else ''} — currently has {count}"
                elif marks_required == 1:
                    why = "No eligible competitions"
                else:
                    why = "Can't form the required 3-mark selection — missing the regional/away event mix"
                checks = _selection_checks(config, n_regional, n_club, n_away, count)
                checks.append({"label": "Intent submitted", "met": intent_submitted, "detail": ""})
                checks.extend(_qualifier_checks(
                    config,
                    _is_gnz_qualified(all_events_list, config),
                    _is_wellington_qualified(all_events_list, config),
                ))
                not_ranked.append(_unranked_row(
                    name, slug, gnz_id, club, region,
                    slot_scores, slot_names, slot_cats, slot_apps,
                    count, n_regional, n_club, n_away,
                    why, checks, intent_submitted,
                ))
                continue

            scores = [s["score"] for s in selected if s is not None]
            competitions = [s["event_name"] for s in selected if s is not None]
            categories = [s["category"] for s in selected if s is not None]
            total = sum(scores)
            avg = total / len(scores)

            # Always compute qualifier warnings regardless of toggle state
            gnz_ok = _is_gnz_qualified(all_events_list, config)
            wgtn_ok = _is_wellington_qualified(all_events_list, config)

            warnings: list[str] = []
            if not gnz_ok:
                warnings.append(_gnz_failure_reason(config, all_events_list))
            if not wgtn_ok:
                warnings.append(_wgtn_failure_reason(config))

            best_club = next(
                (s["club"] for s in all_events_list if s["club"]), "",
            )

            entry = {
                "name": name,
                "slug": slug,
                "gnz_id": best_gnz_id,
                "club": best_club,
                "region": _find_region(best_club),
                "scores": [round(s, 3) for s in scores],
                "competitions": competitions,
                "categories": categories,
                "apparatus": [s.get("apparatus", []) for s in selected if s is not None],
                "total": round(total, 3),
                "average": round(avg, 3),
                "warnings": warnings,
                "intent_submitted": intent_submitted,
            }

            # Filter when the corresponding toggle is ON; athletes dropped by a
            # toggle still appear in ``not_ranked`` so selectors can see them.
            if (
                (gnz_qualifier and not gnz_ok)
                or (wellington_qualifier and not wgtn_ok)
                or (intent_filter and not intent_submitted)
            ):
                reasons = _dropped_reasons(intent_filter, intent_submitted, warnings)
                checks = _selection_checks(
                    config, len(regionals), len(clubs), len(aways),
                    len(all_events_list),
                )
                checks.append({
                    "label": "Intent submitted",
                    "met": entry["intent_submitted"],
                    "detail": "",
                })
                checks.extend(_qualifier_checks(config, gnz_ok, wgtn_ok))
                not_ranked.append(_unranked_row(
                    entry["name"], entry["slug"], entry["gnz_id"], entry["club"], entry["region"],
                    entry["scores"], entry["competitions"], entry["categories"],
                    entry["apparatus"],
                    len(all_events_list), len(regionals), len(clubs), len(aways),
                    reasons[0], checks, entry["intent_submitted"],
                ))
                continue

            rankings.append(entry)

        # 4. Filter to Wellington region only
        rankings = [r for r in rankings if r["region"] == "Wellington"]
        not_ranked = [r for r in not_ranked if r["region"] == "Wellington"]

        # Sort not-ranked alphabetically by name.
        not_ranked.sort(key=lambda x: x["name"].lower())

        # 5. Sort by total descending and assign ranks
        rankings.sort(key=lambda x: -x["total"])

        rank = 1
        prev_total = None
        for i, entry in enumerate(rankings):
            if prev_total is not None and entry["total"] < prev_total:
                rank = i + 1
            entry["rank"] = rank
            prev_total = entry["total"]

        for i, entry in enumerate(rankings):
            if i > 0 and entry["total"] == rankings[i - 1]["total"]:
                entry["rank_text"] = f"T{entry['rank']}"
            elif i < len(rankings) - 1 and entry["total"] == rankings[i + 1]["total"]:
                entry["rank_text"] = f"T{entry['rank']}"
            else:
                entry["rank_text"] = str(entry["rank"])

        # 6. Apparatus specialists: athletes with intent who did not qualify
        #    via the All Around path but reached the apparatus score threshold.
        #    Thresholds are either a single float across apparatus or a
        #    per-apparatus dict. The mark must be reached in
        #    ``apparatus_qualifying_count`` DISTINCT COMPETITIONS on the same
        #    apparatus. Athletes who reached it once but not enough times are
        #    returned as ``qualified: False`` rows so the UI can render
        #    greyed-out "ghost" badges.
        apparatus_specialists = []
        specialist_steps = config.get("specialist_steps")
        if specialist_steps and step in specialist_steps:
            app_threshold = config.get("apparatus_qualifying_score")
            app_scores_by_app = config.get("apparatus_qualifying_scores")
            app_count = config.get("apparatus_qualifying_count", 2)
            aa_keys = {r["name"] for r in rankings}
            for a_key, app_events in apparatus_events.items():
                meta = gymnast_meta.get(a_key, {"name": str(a_key), "gnz_id": "", "club": ""})
                name = meta["name"]
                if name in aa_keys:
                    continue
                gnz_id = meta["gnz_id"]
                club = meta["club"]
                if intents is not None and a_key not in intents and gnz_id not in intents:
                    continue
                region = _find_region(club)
                if region != "Wellington":
                    continue
                slug = athletes[a_key].slug if isinstance(a_key, int) and a_key in athletes else ""

                qualifying = []
                partial = []
                for app, events in app_events.items():
                    threshold = (
                        app_scores_by_app.get(app, float("inf"))
                        if app_scores_by_app is not None
                        else app_threshold
                    )
                    hits = sorted(
                        (e for e in events.values() if e["score"] >= threshold),
                        key=lambda x: -x["score"],
                    )
                    if not hits:
                        continue
                    best = hits[0]
                    entry = {
                        "app": app,
                        "best": round(best["score"], 3),
                        "event": best["event_name"],
                        "count": len(hits),
                        "competitions": sorted({h["event_name"] for h in hits}),
                    }
                    if len(hits) >= app_count:
                        qualifying.append(entry)
                    else:
                        partial.append(entry)

                if qualifying:
                    qualifying.sort(key=lambda x: (-x["best"], x["app"]))
                    partial.sort(key=lambda x: (-x["best"], x["app"]))
                    apparatus_specialists.append({
                        "name": name,
                        "slug": slug,
                        "gnz_id": gnz_id,
                        "club": club,
                        "region": region,
                        "apparatus": qualifying + partial,
                        "count": len(qualifying) + len(partial),
                        "qualified": True,
                    })
                elif partial:
                    partial.sort(key=lambda x: (-x["best"], x["app"]))
                    apparatus_specialists.append({
                        "name": name,
                        "slug": slug,
                        "gnz_id": gnz_id,
                        "club": club,
                        "region": region,
                        "apparatus": partial,
                        "count": len(partial),
                        "qualified": False,
                    })

            apparatus_specialists.sort(
                key=lambda x: (-x["qualified"], -x["count"], x["name"]),
            )

        return {
            "rankings": rankings,
            "not_ranked": not_ranked,
            "apparatus_specialists": apparatus_specialists,
            "year": year,
            "step": step,
            "discipline": discipline,
            "config_key": config["key"],
            "gnz_qualifying_score": config.get("gnz_qualifying_score"),
            "wellington_qualifying_score": config.get("wellington_qualifying_score"),
            "apparatus_qualifying_score": config.get("apparatus_qualifying_score"),
            "apparatus_qualifying_count": config.get("apparatus_qualifying_count", 2),
        }
    finally:
        session.close()
