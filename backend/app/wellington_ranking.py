"""Wellington regional ranking computation for team selection.

Classifies competitions by name patterns, applies step/discipline-specific
selection rules, and ranks Wellington-attached gymnasts.
"""

from collections import defaultdict

from app.database import get_session
from app.models import Event, LongScore
from app.transformer import _find_region, _use_vault_average

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
) -> list[dict] | None:
    """Best regional → next best from remaining 3 named events → best away."""
    score1 = regional[0] if regional else None
    if score1 is None:
        return None

    used = {score1["event_id"]}
    named = sorted(regional + club, key=lambda x: -x["score"])

    score2 = _pick_distinct(named, used)
    if score2 is None:
        return None
    used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    if score3 is None:
        return None

    return [score1, score2, score3]


def _select_wag_step_7_10(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict] | None:
    """Best regional → best two endorsed competitions (1 must be away)."""
    score1 = regional[0] if regional else None
    if score1 is None:
        return None

    used = {score1["event_id"]}
    endorsed = [e for e in all_events if e["event_id"] not in used]
    endorsed_away = [e for e in endorsed if e["event_id"] in {a["event_id"] for a in away}]

    score2 = _pick_distinct(endorsed, used)
    if score2 is None:
        return None
    used.add(score2["event_id"])

    # At least one of the two endorsed marks must be away
    if score2["event_id"] not in {a["event_id"] for a in away}:
        score3 = _pick_distinct(endorsed_away, used)
    else:
        score3 = _pick_distinct(endorsed, used)
    if score3 is None:
        return None

    return [score1, score2, score3]


def _select_mag_level_4_6(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict] | None:
    """Best two Wellington scores → best away."""
    wellington = sorted(regional + club, key=lambda x: -x["score"])

    score1 = _pick_distinct(wellington, set())
    if score1 is None:
        return None
    used = {score1["event_id"]}

    score2 = _pick_distinct(wellington, used)
    if score2 is None:
        return None
    used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    if score3 is None:
        return None

    return [score1, score2, score3]


def _select_mag_level_7_plus(
    regional: list[dict], club: list[dict], away: list[dict],
    all_events: list[dict],
) -> list[dict] | None:
    """Best regional → best two away."""
    score1 = regional[0] if regional else None
    if score1 is None:
        return None

    used = {score1["event_id"]}

    score2 = _pick_distinct(away, used)
    if score2 is None:
        return None
    used.add(score2["event_id"])

    score3 = _pick_distinct(away, used)
    if score3 is None:
        return None

    return [score1, score2, score3]


_SELECTORS = {
    "wag_step_5_6": _select_wag_step_5_6,
    "wag_step_7_10": _select_wag_step_7_10,
    "mag_level_4_6": _select_mag_level_4_6,
    "mag_level_7_plus": _select_mag_level_7_plus,
}


# ── Main entry point ─────────────────────────────────────────────────

def compute_wellington_rankings(
    year: int, discipline: str, step: str,
    gnz_qualifier: bool = True, wellington_qualifier: bool = True,
) -> dict:
    """Return ranking dict with keys ``rankings``, ``year``, ``step``, ``discipline``.

    Each ranking entry contains:
      name, gnz_id, club, region, scores[3], competitions[3],
      categories[3], total, average
    """
    config = _get_config(discipline, step)
    if config is None:
        return {"rankings": [], "year": year, "step": step, "discipline": discipline}

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
                "year": year,
                "step": step,
                "discipline": discipline,
            }

        rows = (
            session.query(
                LongScore.gymnast_name,
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

        # 1. Group by (gymnast, event, round_type) → competition scores
        raw_groups: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (
                r.gymnast_name, r.gnz_id, r.club_name,
                r.event_id, r.event_name, r.round_type,
            )
            raw_groups[key].append(r)

        # 2. Per gymnast: collect best score per event
        #    (across round_types — "best day of two-day competition")
        gymnast_events: dict[str, dict[int, list[dict]]] = defaultdict(
            lambda: defaultdict(list),
        )
        for key, scores in raw_groups.items():
            name = key[0]
            event_id = key[3]
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
            ]

            gymnast_events[name][event_id].append({
                "score": comp_score,
                "event_name": key[4],
                "event_id": event_id,
                "gnz_id": key[1] or "",
                "club": key[2] or "",
                "apparatus": apparatus,
            })

        # 3. Per gymnast: take best score per event, classify, select top 3
        rankings = []
        for name, event_map in gymnast_events.items():
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

            scores = [s["score"] for s in selected]
            competitions = [s["event_name"] for s in selected]
            categories = [s["category"] for s in selected]
            total = sum(scores)
            avg = total / len(scores)

            # GNZ qualifier check (against ALL events)
            if gnz_qualifier and not _is_gnz_qualified(all_events_list, config):
                continue

            # Wellington qualifier check (against ALL events)
            if wellington_qualifier and not _is_wellington_qualified(all_events_list, config):
                continue

            best_gnz_id = next(
                (s["gnz_id"] for s in all_events_list if s["gnz_id"]), "",
            )
            best_club = next(
                (s["club"] for s in all_events_list if s["club"]), "",
            )

            rankings.append({
                "name": name,
                "gnz_id": best_gnz_id,
                "club": best_club,
                "region": _find_region(best_club),
                "scores": [round(s, 3) for s in scores],
                "competitions": competitions,
                "categories": categories,
                "apparatus": [s.get("apparatus", []) for s in selected],
                "total": round(total, 3),
                "average": round(avg, 3),
            })

        # 4. Filter to Wellington region only
        rankings = [r for r in rankings if r["region"] == "Wellington"]

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

        return {
            "rankings": rankings,
            "year": year,
            "step": step,
            "discipline": discipline,
            "config_key": config["key"],
            "gnz_qualifying_score": config.get("gnz_qualifying_score"),
            "wellington_qualifying_score": config.get("wellington_qualifying_score"),
        }
    finally:
        session.close()
