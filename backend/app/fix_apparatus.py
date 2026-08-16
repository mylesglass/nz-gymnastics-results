"""One-time cleanup of un-resolvable apparatus labels in ``long_scores``.

Some Scoreholder exports publish the all-around day's per-apparatus passes
inside multi-set result tables whose result sets are all named "All-around"
(or ``All-Around | Under``/``Over``). When a pass's ``_unitEventId`` isn't
covered by any single-set per-apparatus table, the parser stores the generic
result-set name in ``LongScore.apparatus`` (e.g. ``All-around``). Those passes
are real scores (they still count toward the all-around total), but the
apparatus is genuinely unknowable, so the label is misleading.

This script normalises every row whose ``apparatus`` is outside
``STANDARD_APPARATUS`` to ``""`` (the parser's existing convention for an
unknown apparatus) and clears the meaningless ``apparatus_rank``. The rankings,
specialist, medal and wide-pivot consumers already ignore non-standard
apparatus, so this is purely data hygiene for the raw table.

Usage::

    python -m app.fix_apparatus               # dry run
    python -m app.fix_apparatus --apply       # write changes

Idempotent: re-running with --apply reports 0 rows.
"""

import argparse
import sys

from app.database import get_session
from app.models import LongScore
from app.transformer import STANDARD_APPARATUS


def _fix_rows(session, apply: bool) -> dict:
    """Relabel non-standard apparatus rows; returns stats.

    Commits the changes when ``apply`` is True, otherwise rolls back so the
    dry run leaves no trace.
    """
    stats = {"rows": 0, "details": []}
    query = session.query(LongScore).filter(
        LongScore.apparatus.isnot(None),
        LongScore.apparatus != "",
        LongScore.apparatus.notin_(STANDARD_APPARATUS),
    )
    for r in query.all():
        old = r.apparatus
        r.apparatus = ""
        if r.apparatus_rank is not None:
            r.apparatus_rank = None
        stats["rows"] += 1
        if len(stats["details"]) < 8:
            stats["details"].append(
                f"{r.gymnast_name} [{r.event_name}] ({r.level_category}): {old!r} -> ''"
            )
    if apply:
        session.commit()
    else:
        session.rollback()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--db", default=None, help="override the SQLite DB path (default: data/results.db)")
    args = parser.parse_args()

    if args.db:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker

        import app.database as db_mod
        db_mod.SQLITE_PATH = args.db
        db_mod.engine = create_engine(
            f"sqlite:///{args.db}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        db_mod.SessionLocal = sessionmaker(bind=db_mod.engine, class_=Session)

    session = get_session()
    try:
        stats = _fix_rows(session, args.apply)
        if args.apply:
            from app.cache import invalidate

            invalidate()

        print(f"rows relabelled: {stats['rows']}")
        print(f"mode: {'APPLIED' if args.apply else 'DRY RUN'}")
        for detail in stats["details"]:
            print(f"    {detail}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
