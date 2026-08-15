"""Reverse athlete merges that kept the wrong profile.

The Admin identity review's similar-names "Keep" buttons were wired backwards
(each kept the *other* athlete), so merges made before the fix kept the wrong
spelling — and in every affected merge here the empty-ID side's spelling won,
with the other side's GNZ ID promoted onto it.  This script restores the
pre-merge state: a post-merge athlete is split back into two or more separate
profiles, each owning its original rows, by rewriting rows per event.

Because slugs are content-addressed, every restored profile regains its
original pre-merge URL, and post-merge slug redirects are pruned automatically
by ``rebuild_athletes``.  Same-name splits (the two sides share a normalized
name, e.g. a case/punctuation variant) get a unique ``identity_override`` on
all but one side so the rebuild keeps them apart; re-merging later clears the
override.

Spec format (``--spec-file`` / ``--spec``)::

    {"cases": [
        {"athlete_id": 4450, "splits": [
            {"name": "Isabella Matheson", "gnz_id": "523803", "event_ids": [149, 159]},
            {"name": "Isabella Matherson", "gnz_id": "", "event_ids": [94]}
        ]}
    ]}

Every row of the athlete must fall into exactly one split (the union of the
splits' ``event_ids`` must equal the athlete's event set).

Alternatively derive the spec automatically from a pre-merge backup DB
(``--from-backup``): the backup's athletes that no longer exist and whose name
is similar to the live athlete are treated as the merged-away profiles, and
rows in events absent from the backup are absorbed by the numeric-ID split.

Usage::

    python -m app.reverse_merges --spec-file spec.json                  # dry run
    python -m app.reverse_merges --spec-file spec.json --apply          # write
    python -m app.reverse_merges --from-backup backup.db --for 4450,4451 --apply
    python -m app.reverse_merges --from-backup backup.db --all --apply
    python -m app.reverse_merges --db path/to/results.db --spec-file spec.json --apply

``--all`` over-derives (it picks up non-merge re-keys too, producing single-split
noise), so target the specific survivors with ``--for``.  In production the
pre-merge snapshot lives inside the backend container (``/app/data/...``), e.g.
to reverse a set of buggy-button merges made after the snapshot::

    docker exec nz-gymnastics-results-backend-1 python -m app.reverse_merges \\
        --from-backup /app/data/results.pre-identity-fix.db --for 5166,5167,... --apply
"""

import argparse
import difflib
import json
import secrets
import sqlite3
import sys

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import _names_similar, _signature_hash, _slug_from_hash, rebuild_athletes
from app.cache import invalidate
from app.database import get_session
from app.models import Athlete, LongScore, WellingtonIntent

_NAME_SIMILARITY_THRESHOLD = 0.85


def _fresh_override_token() -> str:
    return secrets.token_hex(16)


def _expected_slug(name: str, gnz_id: str) -> str:
    return _slug_from_hash(_signature_hash(name.strip().lower(), gnz_id))


def _find_athlete(session, name: str, gnz_id: str) -> Athlete | None:
    """Locate an athlete by canonical (name, gnz_id) — empty id is stored as NULL."""
    if gnz_id:
        return (
            session.query(Athlete)
            .filter(Athlete.canonical_name == name, Athlete.gnz_id == gnz_id)
            .first()
        )
    return (
        session.query(Athlete)
        .filter(
            Athlete.canonical_name == name,
            (Athlete.gnz_id.is_(None)) | (Athlete.gnz_id == ""),
        )
        .first()
    )


def _validate_case(session, case: dict) -> dict:
    """Check a spec case covers the athlete's rows exactly once.  Returns info."""
    aid = case["athlete_id"]
    splits = case.get("splits", [])
    athlete = session.get(Athlete, aid)
    if athlete is None:
        missing = [s for s in splits if _find_athlete(session, s["name"], s["gnz_id"]) is None]
        if not missing:
            return {"athlete_id": aid, "status": "already reversed"}
        return {"athlete_id": aid, "status": "athlete not found"}

    event_rows = dict(
        session.query(LongScore.event_id, func.count(LongScore.id))
        .filter(LongScore.athlete_id == aid)
        .group_by(LongScore.event_id)
        .all()
    )
    live_events = set(event_rows)

    seen: set[int] = set()
    split_events: list[tuple[str, str, set[int]]] = []
    for s in splits:
        es = set(s.get("event_ids", []))
        if not es:
            return {"athlete_id": aid, "status": "error", "error": f"split {s['name']!r} has no events"}
        if es & seen:
            return {"athlete_id": aid, "status": "error", "error": "splits overlap on events"}
        if not es <= live_events:
            extra = sorted(es - live_events)
            return {
                "athlete_id": aid,
                "status": "error",
                "error": f"split {s['name']!r} lists events {extra} the athlete has no rows in",
            }
        seen |= es
        split_events.append((s["name"], s.get("gnz_id", "") or "", es))

    uncovered = live_events - seen
    if uncovered:
        return {
            "athlete_id": aid,
            "status": "error",
            "error": f"events {sorted(uncovered)} are not covered by any split",
        }

    rows_total = sum(event_rows.values())
    info = {
        "athlete_id": aid,
        "status": "ok",
        "name": athlete.canonical_name,
        "rows": rows_total,
        "splits": [
            {
                "name": name,
                "gnz_id": gid,
                "rows": sum(event_rows[e] for e in es),
                "events": len(es),
                "slug": _expected_slug(name, gid),
            }
            for name, gid, es in split_events
        ],
    }
    norms = [s["name"].strip().lower() for s in splits]
    info["override"] = len(set(norms)) < len(norms)
    return info


def reverse(
    session,
    spec: dict,
    apply: bool = False,
) -> dict:
    """Reverse the merges described by ``spec``.

    Returns a report.  When ``apply`` is False nothing is written.
    """
    report: dict[str, list[dict]] = {"cases": []}
    for case in spec.get("cases", []):
        report["cases"].append(_process_case(session, case, apply))
    return report


def _process_case(session, case: dict, apply: bool) -> dict:
    aid = case["athlete_id"]
    splits = case.get("splits", [])
    info = _validate_case(session, case)
    if info["status"] != "ok":
        return info
    if not apply:
        return info

    athlete = session.get(Athlete, aid)
    norm_collision = info["override"]

    # Pick the canonical split (numeric id) — the others get an override when
    # two splits share a name, so the rebuild keeps them as separate athletes.
    canonical_idx = next(
        (i for i, s in enumerate(splits) if (s.get("gnz_id") or "").isdigit()),
        0,
    )
    for i, s in enumerate(splits):
        es = set(s["event_ids"])
        updates = {
            LongScore.gymnast_name: s["name"],
            LongScore.gnz_id: s.get("gnz_id") or None,
        }
        if norm_collision and i != canonical_idx:
            updates[LongScore.identity_override] = _fresh_override_token()
        session.query(LongScore).filter(
            LongScore.athlete_id == aid,
            LongScore.event_id.in_(es),
        ).update(updates, synchronize_session=False)

    rebuild_athletes(session)

    # Re-point Wellington intents to the canonical split's resulting athlete.
    canonical = splits[canonical_idx]
    new_athlete = _find_athlete(session, canonical["name"], canonical.get("gnz_id") or "")
    if new_athlete is not None and new_athlete.id != aid:
        for intent in (
            session.query(WellingtonIntent)
            .filter(WellingtonIntent.athlete_id == aid)
            .all()
        ):
            intent.athlete_id = new_athlete.id
            intent.gnz_id = canonical.get("gnz_id") or None
        session.commit()
    invalidate()

    return {**info, "status": "reversed"}


# --- Spec derivation from a pre-merge backup -----------------------------


def _backup_connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def derive_spec(
    session,
    backup_path: str,
    athlete_ids: list[int] | None = None,
    all_: bool = False,
) -> dict:
    """Derive reverse specs by diffing ``backup_path`` against the live DB.

    A live athlete is a merge survivor when the backup contains athlete(s)
    that (1) no longer exist, (2) have a name similar to the survivor's, and
    (3) only ever appeared in events the survivor now owns.  ``athlete_ids``
    restricts the scan; ``all_`` scans every live athlete.
    """
    con = _backup_connect(backup_path)
    try:
        bak_athletes = {
            bid: (bname, bgid or "")
            for bid, bname, bgid in con.execute(
                "select id, canonical_name, gnz_id from athletes"
            ).fetchall()
        }
        bak_events: dict[int, set[int]] = {}
        for bid, eid in con.execute(
            "select distinct athlete_id, event_id from long_scores"
        ).fetchall():
            bak_events.setdefault(bid, set()).add(eid)
    finally:
        con.close()

    cur_ids = {r[0] for r in session.query(Athlete.id).all()}
    deleted = {
        bid: (bname, bgid, bak_events.get(bid, set()))
        for bid, (bname, bgid) in bak_athletes.items()
        if bid not in cur_ids and bak_events.get(bid)
    }
    if not deleted:
        return {"cases": []}

    # Bucket deleted names by first letter to bound the similarity scan.
    by_letter: dict[str, list[tuple[int, str, str, set[int]]]] = {}
    for bid, (bname, bgid, bevents) in deleted.items():
        by_letter.setdefault(bname[:1].lower(), []).append((bid, bname, bgid, bevents))

    def _scan(aid: int) -> dict | None:
        survivor = session.get(Athlete, aid)
        if survivor is None or not survivor.canonical_name:
            return None
        live_events = {
            eid
            for (eid,) in session.query(LongScore.event_id)
            .filter(LongScore.athlete_id == aid)
            .distinct()
            .all()
        }
        cand: list[tuple[str, str, set[int]]] = []
        for _, bname, bgid, bevents in by_letter.get(survivor.canonical_name[:1].lower(), []):
            if not bevents <= live_events:
                continue
            if not _names_similar(bname, survivor.canonical_name):
                continue
            cand.append((bname, bgid, bevents))
        if not cand:
            return None
        splits = [
            {"name": name, "gnz_id": gid, "event_ids": sorted(es)}
            for name, gid, es in cand
        ]
        covered = set().union(*(es for _, _, es in cand))
        gaps = live_events - covered
        if gaps:
            id_split = next((s for s in splits if s["gnz_id"].isdigit()), None)
            if id_split is None:
                return None
            id_split["event_ids"] = sorted(set(id_split["event_ids"]) | gaps)
        return {"athlete_id": aid, "splits": splits}

    ids = athlete_ids if athlete_ids is not None else [r[0] for r in session.query(Athlete.id).all()]
    cases = []
    for aid in ids:
        case = _scan(aid)
        if case is not None:
            cases.append(case)
    return {"cases": cases}


# --- CLI ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-file", default=None, help="JSON spec file")
    parser.add_argument("--spec", default=None, help="inline JSON spec")
    parser.add_argument("--from-backup", default=None, help="derive specs by diffing a pre-merge backup DB")
    parser.add_argument("--for", dest="for_ids", default=None, help="comma-separated athlete ids (with --from-backup)")
    parser.add_argument("--all", action="store_true", help="derive specs for every merge survivor (with --from-backup)")
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
        if args.from_backup:
            ids = None
            if args.for_ids:
                ids = [int(x) for x in args.for_ids.split(",") if x.strip()]
            elif not args.all:
                parser.error("--from-backup requires --for <ids> or --all")
            spec = derive_spec(session, args.from_backup, athlete_ids=ids, all_=args.all)
            print(f"derived {len(spec['cases'])} case(s) from {args.from_backup}")
        elif args.spec_file:
            with open(args.spec_file) as f:
                spec = json.load(f)
        elif args.spec:
            spec = json.loads(args.spec)
        else:
            parser.error("provide --spec-file, --spec or --from-backup")

        report = reverse(session, spec, apply=args.apply)
        print(f"mode: {'APPLIED' if args.apply else 'DRY RUN'}")
        for info in report["cases"]:
            print(f"    athlete {info['athlete_id']}: {info['status']}")
            if info.get("error"):
                print(f"        error: {info['error']}")
            for s in info.get("splits", []):
                print(
                    f"        {s['name']!r} [{s.get('gnz_id') or ''}] "
                    f"({s['rows']} rows, {s['events']} events) -> /gymnast/{s['slug']}"
                )
            if info.get("override"):
                print("        same-name split: identity_override applied")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
