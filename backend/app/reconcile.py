from collections import defaultdict

from sqlalchemy import func

from app.database import get_session
from app.models import LongScore


def _score_id(gnz_id: str, freq: int) -> int:
    score = freq
    if gnz_id.isdigit():
        score += 100
    return score


def reconcile_athletes() -> dict:
    session = get_session()
    try:
        rows = (
            session.query(
                func.trim(func.lower(LongScore.gymnast_name)).label("clean_name"),
                LongScore.gnz_id,
                func.count(LongScore.id).label("cnt"),
            )
            .filter(
                LongScore.gymnast_name.isnot(None),
                LongScore.gymnast_name != "",
            )
            .group_by(
                func.trim(func.lower(LongScore.gymnast_name)),
                LongScore.gnz_id,
            )
            .all()
        )

        name_groups: dict[str, dict[str | None, int]] = {}
        original_names: dict[str, str] = {}
        for clean_name, gnz_id, cnt in rows:
            name_groups.setdefault(clean_name, {})
            name_groups[clean_name][gnz_id] = cnt
            original_names[clean_name] = clean_name

        total_athletes = len(name_groups)
        ids_corrected = 0
        names_unified = 0
        conflicts: list[dict] = []

        for clean_name, id_freqs in name_groups.items():
            non_empty = {k: v for k, v in id_freqs.items() if k}
            if len(non_empty) <= 1:
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
