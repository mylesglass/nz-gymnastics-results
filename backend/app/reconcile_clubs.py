"""Normalise existing club names in the database to their canonical forms.

Run after updating clubs_and_regions.json to merge variants that were
stored before the aliases existed.

Usage:
    python -m app.reconcile_clubs
"""

from sqlalchemy import func

from app.database import get_session
from app.models import LongScore
from app.parser import _NAME_TO_CANONICAL


def reconcile_clubs() -> dict:
    session = get_session()
    try:
        rows = (
            session.query(LongScore.club_name)
            .filter(LongScore.club_name.isnot(None), LongScore.club_name != "")
            .distinct()
            .all()
        )
        distinct_names = sorted({r[0] for r in rows if r[0]})

        updates = 0
        resolved: dict[str, str] = {}

        for name in distinct_names:
            lower = name.lower().strip()
            canonical = _NAME_TO_CANONICAL.get(lower)
            if canonical and canonical != name:
                resolved[name] = canonical

        for old_name, new_name in resolved.items():
            updated = (
                session.query(LongScore)
                .filter(
                    func.lower(func.trim(LongScore.club_name)) == old_name.lower().strip(),
                    LongScore.club_name != new_name,
                )
                .update({"club_name": new_name}, synchronize_session=False)
            )
            updates += updated

        session.commit()

        return {
            "distinct_names": len(distinct_names),
            "names_resolved": len(resolved),
            "rows_updated": updates,
        }
    finally:
        session.close()


if __name__ == "__main__":
    report = reconcile_clubs()
    print(f"Distinct club names: {report['distinct_names']}")
    print(f"Names resolved to canonical: {report['names_resolved']}")
    print(f"Rows updated: {report['rows_updated']}")
