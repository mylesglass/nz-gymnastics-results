"""Evidence-based athlete ID reconciliation.

Merges rows that share a normalized name *only* when the data supports them
being the same person.  Two signals override a shared name and force a
conflict instead of a merge:

* **same-event collision** — the name carries 2+ distinct IDs within a single
  event (a person cannot be two people at one competition);
* **discipline conflict** — the name's IDs span 2+ disciplines (an athlete
  competes in exactly one of WAG/MAG).

Spelling variants of one person (which share a numeric ID) are untouched here
— unifying display names is handled elsewhere.
"""

from collections import defaultdict

from sqlalchemy import func

from app.database import get_session
from app.models import LongScore


def _score_id(gnz_id: str, freq: int) -> int:
    score = freq
    if gnz_id.isdigit():
        score += 100
    return score


def _same_event_collision(
    event_ids_by_id: dict[str, set[int]],
) -> bool:
    """True if any event contains 2+ distinct non-empty IDs for a name."""
    events: dict[int, set[str]] = defaultdict(set)
    for gid, eids in event_ids_by_id.items():
        for eid in eids:
            events[eid].add(gid)
    return any(len(ids) > 1 for ids in events.values())


def _disciplines_conflict(disciplines_by_id: dict[str, set[str]]) -> bool:
    """True if the name's IDs span more than one discipline."""
    union: set[str] = set()
    for discs in disciplines_by_id.values():
        union.update(discs)
    return len(union) > 1


def reconcile_athletes() -> dict:
    session = get_session()
    try:
        rows = (
            session.query(
                func.trim(func.lower(LongScore.gymnast_name)).label("clean_name"),
                LongScore.gnz_id,
                LongScore.event_id,
                LongScore.discipline,
                func.count(LongScore.id).label("cnt"),
            )
            .filter(
                LongScore.gymnast_name.isnot(None),
                LongScore.gymnast_name != "",
            )
            .group_by(
                func.trim(func.lower(LongScore.gymnast_name)),
                LongScore.gnz_id,
                LongScore.event_id,
                LongScore.discipline,
            )
            .all()
        )

        name_groups: dict[str, dict[str, int]] = {}
        event_ids_by_gid: dict[str, dict[str, set[int]]] = {}
        disciplines_by_gid: dict[str, dict[str, set[str]]] = {}
        for clean_name, gnz_id, event_id, discipline, cnt in rows:
            name_groups.setdefault(clean_name, {})
            name_groups[clean_name][gnz_id or ""] = (
                name_groups[clean_name].get(gnz_id or "", 0) + cnt
            )
            event_ids_by_gid.setdefault(clean_name, {}).setdefault(gnz_id or "", set()).add(event_id)
            if discipline:
                disciplines_by_gid.setdefault(clean_name, {}).setdefault(gnz_id or "", set()).add(discipline)

        total_athletes = len(name_groups)
        ids_corrected = 0
        names_unified = 0
        conflicts: list[dict] = []

        for clean_name, id_freqs in name_groups.items():
            non_empty = {k: v for k, v in id_freqs.items() if k}
            if len(non_empty) <= 1:
                continue

            event_ids = event_ids_by_gid.get(clean_name, {})
            disciplines = disciplines_by_gid.get(clean_name, {})

            if _same_event_collision(event_ids):
                conflicts.append(
                    {
                        "name": clean_name,
                        "previous_ids": sorted(non_empty.keys()),
                        "chosen_id": None,
                        "rows_updated": 0,
                        "reason": "same name with 2+ different IDs in one event — distinct people",
                    }
                )
                continue

            if _disciplines_conflict(disciplines):
                conflicts.append(
                    {
                        "name": clean_name,
                        "previous_ids": sorted(non_empty.keys()),
                        "chosen_id": None,
                        "rows_updated": 0,
                        "reason": "name spans 2+ disciplines — distinct people",
                    }
                )
                continue

            candidates = sorted(
                non_empty.keys(),
                key=lambda x: _score_id(x, non_empty[x]),
                reverse=True,
            )
            best = candidates[0]
            runner_up = candidates[1] if len(candidates) > 1 else None

            if runner_up and _score_id(best, non_empty[best]) == _score_id(
                runner_up, non_empty[runner_up]
            ):
                conflicts.append(
                    {
                        "name": clean_name,
                        "previous_ids": sorted(non_empty.keys()),
                        "chosen_id": None,
                        "rows_updated": 0,
                        "reason": "tie between equally frequent IDs — manual review",
                    }
                )
                continue

            previous_ids = sorted(k for k in non_empty if k != best)
            updated = (
                session.query(LongScore)
                .filter(
                    func.trim(func.lower(LongScore.gymnast_name)) == clean_name,
                    LongScore.gnz_id.in_(previous_ids),
                )
                .update({"gnz_id": best}, synchronize_session=False)
            )
            ids_corrected += updated
            names_unified += 1

        session.commit()

        report = {
            "total_athletes": total_athletes,
            "ids_corrected": ids_corrected,
            "names_unified": names_unified,
            "conflicts": conflicts,
        }
        return report
    finally:
        session.close()
