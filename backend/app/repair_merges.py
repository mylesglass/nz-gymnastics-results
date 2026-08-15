"""Repair athlete merges that kept the wrong profile.

The Admin identity review's similar-names "Keep" buttons were wired backwards
(each kept the *other* athlete), so merges made before the fix kept the wrong
spelling and — when both sides had a GNZ ID — the wrong ID.  This script
rewrites the confirmed athletes' rows to their canonical name + GNZ ID and lets
``rebuild_athletes`` re-key everything (slug redirects keep old URLs working;
Wellington intents are re-pointed to the resulting athlete).

Confirmed corrections (``athlete_id -> (canonical_name, gnz_id)``)::

    * 2950  Mathew Arck-weeber  -> Matthew Arck-weeber / 568463
    * 335   Annabelle Crochrane -> Annabelle Cochrane / 833663
    * 4452  Sophie Chishom      -> Sophie Chisholm   / 617735

Usage::

    python -m app.repair_merges            # dry run
    python -m app.repair_merges --apply    # write changes
    python -m app.repair_merges --db path/to/results.db --apply

Idempotent: re-running with --apply reports 0 rows to fix.
"""

import argparse
import sys

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import _signature_hash, _slug_from_hash, rebuild_athletes
from app.cache import invalidate
from app.database import get_session
from app.models import Athlete, LongScore, WellingtonIntent

CORRECTIONS: dict[int, tuple[str, str]] = {
    2950: ("Matthew Arck-weeber", "568463"),
    335: ("Annabelle Cochrane", "833663"),
    4452: ("Sophie Chisholm", "617735"),
}


def set_corrections(corrections: dict[int, tuple[str, str]]) -> None:
    """Override the correction list (used in tests)."""
    global CORRECTIONS
    CORRECTIONS = corrections


def _expected_slug(name: str, gnz_id: str) -> str:
    return _slug_from_hash(_signature_hash(name.strip().lower(), gnz_id))


def repair(
    session,
    corrections: dict[int, tuple[str, str]] | None = None,
    apply: bool = False,
) -> dict:
    """Rewrite corrected athletes' rows to their canonical name + GNZ ID.

    Returns a report dict.  When ``apply`` is False nothing is written.
    """
    corrections = corrections if corrections is not None else CORRECTIONS
    report: dict[str, list[dict]] = {"items": []}
    if not corrections:
        return report

    for aid, (target_name, target_gid) in corrections.items():
        athlete = session.get(Athlete, aid)
        if athlete is None:
            # A previous --apply re-keyed the athlete (new signature = new id).
            # If the corrected identity now exists, there is nothing to fix.
            existing = (
                session.query(Athlete)
                .filter(
                    Athlete.canonical_name == target_name,
                    Athlete.gnz_id == target_gid,
                )
                .first()
            )
            if existing is None:
                report["items"].append({"athlete_id": aid, "error": "athlete not found"})
                continue
            existing_rows = (
                session.query(func.count(LongScore.id))
                .filter(LongScore.athlete_id == existing.id)
                .scalar()
                or 0
            )
            report["items"].append({
                "athlete_id": aid,
                "old_name": target_name,
                "old_gnz_id": target_gid,
                "new_name": target_name,
                "new_gnz_id": target_gid,
                "rows": existing_rows,
                "intents": [],
                "old_slug": existing.slug,
                "new_slug": existing.slug,
                "changed": False,
            })
            continue

        row_count = (
            session.query(func.count(LongScore.id))
            .filter(LongScore.athlete_id == aid)
            .scalar()
            or 0
        )
        intents = [
            year
            for (year,) in session.query(WellingtonIntent.year)
            .filter(WellingtonIntent.athlete_id == aid)
            .all()
        ]
        expected = _expected_slug(target_name, target_gid)
        changed = (
            (athlete.canonical_name != target_name)
            or (athlete.gnz_id or "") != target_gid
        )
        entry = {
            "athlete_id": aid,
            "old_name": athlete.canonical_name,
            "old_gnz_id": athlete.gnz_id or "",
            "new_name": target_name,
            "new_gnz_id": target_gid,
            "rows": row_count,
            "intents": sorted(intents),
            "old_slug": athlete.slug,
            "new_slug": expected,
            "changed": changed,
        }
        if apply and changed and row_count:
            session.query(LongScore).filter(LongScore.athlete_id == aid).update(
                {
                    LongScore.gymnast_name: target_name,
                    LongScore.gnz_id: target_gid,
                },
                synchronize_session=False,
            )
        report["items"].append(entry)

    if apply:
        rebuild_athletes(session)
        # Re-point Wellington intents: the corrected athlete's row is deleted
        # and replaced by the (name, gnz_id) identity it was rewritten to.
        for aid, (target_name, target_gid) in corrections.items():
            new_athlete = (
                session.query(Athlete)
                .filter(
                    Athlete.canonical_name == target_name,
                    Athlete.gnz_id == target_gid,
                )
                .first()
            )
            if new_athlete is None or new_athlete.id == aid:
                continue
            existing_years = {
                year
                for (year,) in session.query(WellingtonIntent.year)
                .filter(WellingtonIntent.athlete_id == new_athlete.id)
                .all()
            }
            for intent in (
                session.query(WellingtonIntent)
                .filter(WellingtonIntent.athlete_id == aid)
                .all()
            ):
                if intent.year in existing_years:
                    session.delete(intent)
                else:
                    intent.athlete_id = new_athlete.id
                    intent.gnz_id = target_gid
                    existing_years.add(intent.year)
        session.commit()
        invalidate()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--db", default=None, help="override the SQLite DB path (default: data/results.db)")
    args = parser.parse_args()

    if args.db:
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
        report = repair(session, apply=args.apply)
    finally:
        session.close()

    print(f"mode: {'APPLIED' if args.apply else 'DRY RUN'}")
    for item in report["items"]:
        if "error" in item:
            print(f"    athlete {item['athlete_id']}: {item['error']}")
            continue
        status = "OK" if item["changed"] else "already correct"
        print(
            f"    {item['athlete_id']} {item['old_name']!r} [{item['old_gnz_id']!r}]"
            f" -> {item['new_name']!r} [{item['new_gnz_id']!r}]"
            f" ({item['rows']} rows, intents {item['intents']}) [{status}]"
        )
        print(
            f"        slug {item['old_slug']} -> {item['new_slug']}"
            + ("" if item["new_slug"] == item["old_slug"] else "  (URL redirects)")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
