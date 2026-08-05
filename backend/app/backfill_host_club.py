"""Guess ``host_club`` for existing events that don't have one yet.

Uses the name-based ``_guess_host_club`` helper as a starting point; National
events default to ``Gymnastics NZ``. Review the dry-run output and correct any
wrong guesses on the events page (admin edit dialog) — no re-upload of event
files is needed.

Usage:
    python -m app.backfill_host_club          # dry-run (default)
    python -m app.backfill_host_club --apply  # write guesses
"""

import argparse

from sqlalchemy import func

from app.cache import invalidate
from app.database import get_session
from app.models import Event
from app.transformer import _guess_host_club


def _resolve(name: str, is_national: bool) -> str:
    if is_national:
        return "Gymnastics NZ"
    guess = _guess_host_club(name)
    if guess:
        return guess
    if "national" in name.lower():
        return "Gymnastics NZ"
    return ""


def backfill_host_club(apply: bool = False) -> dict:
    session = get_session()
    try:
        rows = (
            session.query(Event)
            .filter(
                Event.host_club.is_(None),
                func.trim(func.coalesce(Event.host_club, "")) == "",
            )
            .order_by(Event.year, Event.name)
            .all()
        )
        proposed = 0
        unmatched = 0
        for event in rows:
            guess = _resolve(event.name, bool(event.is_national))
            if not guess:
                unmatched += 1
                print(f"  (no match)   {event.year} | {event.name}")
                continue
            proposed += 1
            print(f"  {guess:40s}  {event.year} | {event.name}")
            if apply:
                event.host_club = guess

        if apply:
            session.commit()
            invalidate()

        return {"events_without": len(rows), "proposed": proposed, "unmatched": unmatched}
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the guesses to the database (default is a dry run)",
    )
    args = parser.parse_args()

    report = backfill_host_club(apply=args.apply)
    verb = "Applied" if args.apply else "Would propose"
    print()
    print(f"Events without host_club: {report['events_without']}")
    print(f"{verb} a guess for: {report['proposed']}")
    print(f"Unmatched (left blank): {report['unmatched']}")
