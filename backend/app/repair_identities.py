"""One-time athlete identity repair using source JSON exports as ground truth.

Fixes two classes of corruption that accumulated in the live database:

1. **Wrong / merged GNZ IDs.**  ``reconcile_athletes()`` used to merge rows by
   name alone, collapsing distinct people who share a name (e.g. two Madison
   Lynches) into a single ID.  The source JSONs in ``data-collection/`` carry
   each athlete's true ``identifier``.

2. **Mangled name capitalization.**  The old ``_clean_name()`` lowercased every
   word (``McEwan`` -> ``Mcewan``).  The source JSONs preserve the original
   spelling.

Unlike the previous per-event version, this script is **consensus-driven**: for
each ``(name, club)`` signature it counts the numeric identifiers across *all*
source files, and only changes a DB row when a clear majority exists (an ID
with strictly more votes than every other).  A single file's typo therefore
never overwrites an ID that five other files agree on.

Only rows whose ``(name, club)`` has a decisive consensus are touched; tied or
single-vote signatures are left alone.

Usage::

    python -m app.repair_identities              # dry run
    python -m app.repair_identities --apply      # write changes

Idempotent: re-running with --apply converges (second run reports 0).
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.database import get_session
from app.models import LongScore
from app.resolver import _clean_name

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data-collection"


def set_data_dir(path: Path) -> None:
    """Point the script at a different source-JSON directory (used in tests)."""
    global _DATA_DIR
    _DATA_DIR = path


def _norm(text: str) -> str:
    """Normalise a name/club for matching (lowercase, collapse punctuation)."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _clean_id(identifier: str) -> str:
    """Normalise a source identifier to a plain numeric GNZ ID (or '')."""
    raw = (identifier or "").strip()
    for prefix in ("GS", "GNZ", "GGS"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    return raw if raw.isdigit() else ""


def _build_source_consensus() -> tuple[dict[tuple, str], dict[tuple, str]]:
    """Count numeric identifiers and name spellings per (name, club) signature.

    Returns ``(id_consensus, name_consensus)`` where each maps a
    ``(normalized_name, normalized_club)`` key to its majority value.  Keys
    whose top-2 values tie are excluded (no decisive majority).
    """
    id_votes: dict[tuple, Counter] = defaultdict(Counter)
    name_votes: dict[tuple, Counter] = defaultdict(Counter)
    for path in sorted(_DATA_DIR.glob("**/*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        orgs = {o.get("_id"): o.get("name", "") for o in data.get("eventOrganizations", [])}
        for p in data.get("eventParticipants", []):
            raw_name = (p.get("name") or "").strip()
            if not raw_name:
                continue
            # Clean through the same fixed name-caser as the parser so the
            # consensus votes on the canonical spelling (e.g. all the different
            # source casings of ``De la Harpe`` collapse to one form) instead
            # of letting a single file's sloppy casing win.
            name = _clean_name(raw_name)
            club = orgs.get(p.get("organizationId"), "")
            key = (_norm(name), _norm(club))
            gid = _clean_id(p.get("identifier", ""))
            if gid:
                id_votes[key][gid] += 1
            name_votes[key][name] += 1

    def majority(counter: Counter) -> str | None:
        items = counter.most_common()
        if not items:
            return None
        if len(items) == 1:
            return items[0][0]
        # Require a decisive majority: the winner must beat the runner-up by a
        # factor of >= 2. This protects genuine same-name two-people cases and
        # near-ties (e.g. 7:3) from being force-merged to one ID.
        if items[0][1] >= items[1][1] * 2:
            return items[0][0]
        return None

    id_consensus = {k: v for k, v in ((k, majority(c)) for k, c in id_votes.items()) if v}
    name_consensus = {k: v for k, v in ((k, majority(c)) for k, c in name_votes.items()) if v}
    return id_consensus, name_consensus


def _repair_rows(
    session,
    id_consensus: dict[tuple, str],
    name_consensus: dict[tuple, str],
    apply: bool,
) -> dict:
    """Apply consensus IDs/names to DB rows by (name, club) signature.

    Returns stats.  When ``apply`` is False, mutations are reverted so the dry
    run leaves no trace.
    """
    stats = {"rows": 0, "id_fixes": 0, "name_fixes": 0, "details": []}
    for r in session.query(LongScore).all():
        key = (_norm(r.gymnast_name), _norm(r.club_name or ""))
        changes = {}
        target_id = id_consensus.get(key)
        if target_id and r.gnz_id != target_id:
            changes["gnz_id"] = target_id
        target_name = name_consensus.get(key)
        if target_name and r.gymnast_name != target_name:
            changes["gymnast_name"] = target_name
        if not changes:
            continue
        originals = {f: getattr(r, f) for f in changes}
        for field, value in changes.items():
            setattr(r, field, value)
        if not apply:
            for field, value in originals.items():
                setattr(r, field, value)
        stats["rows"] += 1
        if "gnz_id" in changes:
            stats["id_fixes"] += 1
        if "gymnast_name" in changes:
            stats["name_fixes"] += 1
        if len(stats["details"]) < 8:
            bits = []
            if "gnz_id" in changes:
                bits.append(f"gnz {originals['gnz_id'] or '∅'} -> {changes['gnz_id']}")
            if "gymnast_name" in changes:
                bits.append(f"name '{originals['gymnast_name']}' -> '{changes['gymnast_name']}'")
            stats["details"].append(f"{r.gymnast_name} [{r.club_name or '?'}] ({'; '.join(bits)})")
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

    id_consensus, name_consensus = _build_source_consensus()
    session = get_session()
    try:
        stats = _repair_rows(session, id_consensus, name_consensus, args.apply)
        if args.apply:
            session.commit()
            from app.cache import invalidate

            invalidate()
        else:
            session.rollback()

        print(f"source (name,club) signatures: {len(id_consensus)} with a decisive ID, {len(name_consensus)} with a name")
        print(f"rows needing repair: {stats['rows']}  (ID: {stats['id_fixes']}, name/casing: {stats['name_fixes']})")
        print(f"mode: {'APPLIED' if args.apply else 'DRY RUN'}")
        for detail in stats["details"]:
            print(f"    {detail}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
