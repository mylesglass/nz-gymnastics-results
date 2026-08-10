"""Remove duplicate event rows from the database.

Groups events by ``(name, start_date, discipline)`` and keeps the copy with the
most ``long_scores`` (tie-break: lowest id), deleting the rest. Duplicates are
usually caused by the same Scoreholder export being imported more than once;
each copy carries its own orphaned-looking result rows, so the whole pile shows
up on the timeline/events page.

Usage:
    python -m app.dedupe_events          # dry-run (default)
    python -m app.dedupe_events --apply  # delete the duplicate rows
"""

import argparse

from sqlalchemy import func

from app.cache import invalidate
from app.database import get_session
from app.models import Event, LongScore


def dedupe_events(apply: bool = False) -> dict:
    session = get_session()
    try:
        groups = (
            session.query(Event.name, Event.start_date, Event.discipline, func.count(Event.id))
            .group_by(Event.name, Event.start_date, Event.discipline)
            .having(func.count(Event.id) > 1)
            .order_by(Event.name, Event.start_date, Event.discipline)
            .all()
        )

        kept = 0
        removed = 0
        for name, start_date, discipline, count in groups:
            copies = (
                session.query(Event, func.count(LongScore.id))
                .outerjoin(LongScore, LongScore.event_id == Event.id)
                .filter(
                    Event.name == name,
                    Event.start_date == start_date,
                    Event.discipline == discipline,
                )
                .group_by(Event.id)
                .order_by(func.count(LongScore.id).desc(), Event.id.asc())
                .all()
            )
            keeper = copies[0][0]
            print(
                f"  {name} | {start_date} | {discipline} — {count} copies, "
                f"keeping #{keeper.id} ({copies[0][1]} scores)"
            )
            for event, score_count in copies[1:]:
                print(f"    delete #{event.id} ({score_count} scores)")
                removed += 1
                if apply:
                    session.delete(event)
            kept += 1

        if apply:
            session.commit()
            invalidate()

        return {"groups": len(groups), "kept": kept, "removed": removed}
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete the duplicate rows (default is a dry run)",
    )
    args = parser.parse_args()

    report = dedupe_events(apply=args.apply)
    verb = "Deleted" if args.apply else "Would delete"
    print()
    print(f"Duplicate groups: {report['groups']}")
    print(f"Groups kept: {report['kept']}")
    print(f"{verb}: {report['removed']} duplicate events")
