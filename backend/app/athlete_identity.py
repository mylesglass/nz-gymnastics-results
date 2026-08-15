"""Athlete identity clustering and assignment.

An ``Athlete`` is a stable identity derived from the (messy) ``gnz_id`` /
``gymnast_name`` columns on ``long_scores``.  Rows that belong to the same
person share an ``athlete_id`` and a canonical display name, decoupling the
public-facing identity from the source data's inconsistent identifiers and
giving each person one stable ``slug`` for gymnast-page URLs.

Clustering runs a union-find over ``(normalized name, gnz_id)`` signatures:

* **Within a name** — signatures merge into one athlete unless the data proves
  they are different people:
    * same-event collision — two IDs appear in the same event (a person cannot
      be two people at one competition);
    * discipline conflict — IDs span WAG + MAG;
    * disjoint clubs — IDs with no club in common.  An athlete may change clubs
      but keeps their ID, so disjoint club sets across *different* IDs is
      evidence of two people (e.g. the two Madison Lynches, OMNI vs Onslow).
  Rows with an empty ``gnz_id`` join their name's dominant non-empty ID's
  athlete, or form their own athlete when the name has no IDs.
* **Across names** — two athletes sharing a numeric ``gnz_id`` merge only when
  their normalized names are close (difflib ``SequenceMatcher.ratio >= 0.85``),
  so spelling variants of one person (``Eva Mcewan`` / ``Eva McEwan``) collapse
  while genuinely different people sharing a bad ID stay separate.
* **Admin override** — a non-empty ``identity_override`` token on a row is a
  hard force-split boundary (set by the admin Split action): each distinct
  token is its own athlete and unmarked rows cluster among themselves with the
  normal rules.  Merge clears the token so the two halves join back up.

``rebuild_athletes`` is idempotent and **signature-stable**: each cluster is
keyed by a hash of its canonical ``(normalized name, gnz_id)`` pair, so an
existing ``Athlete`` row is reused (keeping its ``id``/``slug``) across rebuilds
unless the cluster's dominant identity actually changes.  After re-clustering,
every ``long_scores`` row is **back-written** to its cluster's canonical
spelling, so the raw ``gymnast_name`` column stops carrying variant spellings.

When a cluster's identity changes (admin merge/split, or a rebuild that
re-keys it), the old ``Athlete`` row is deleted — but a ``SlugRedirect`` is
recorded from its old ``slug`` to the athlete that absorbed its rows, so
bookmarked/shared gymnast URLs resolve to the survivor instead of 404ing.
"""

import difflib
import hashlib
from collections import Counter, defaultdict

from sqlalchemy import func

from app.models import Athlete, LongScore, SlugRedirect

_NAME_SIMILARITY_THRESHOLD = 0.85


class _UnionFind:
    """Path-compressed union-find keyed on arbitrary hashable items."""

    def __init__(self) -> None:
        self.parent: dict = {}

    def _root(self, x):
        self.parent.setdefault(x, x)
        parent = self.parent[x]
        while parent != self.parent[parent]:
            parent = self.parent[parent]
        self.parent[x] = parent
        return parent

    def union(self, a, b) -> None:
        ra, rb = self._root(a), self._root(b)
        if ra != rb:
            self.parent[rb] = ra

    def components(self) -> dict:
        groups: dict = defaultdict(set)
        for key in self.parent:
            groups[self._root(key)].add(key)
        return groups


def _same_event_collision(events_by_id: dict[str, set[int]]) -> bool:
    """True if any event contains 2+ distinct non-empty IDs."""
    events: dict[int, set[str]] = defaultdict(set)
    for gid, eids in events_by_id.items():
        for eid in eids:
            events[eid].add(gid)
    return any(len(ids) > 1 for ids in events.values())


def _disciplines_conflict(disciplines_by_id: dict[str, set[str]]) -> bool:
    """True if the IDs' disciplines span more than one value."""
    union: set[str] = set()
    for discs in disciplines_by_id.values():
        union.update(discs)
    return len(union) > 1


def _numeric_count(id_counts: Counter) -> int:
    return sum(cnt for gid, cnt in id_counts.items() if gid and gid.isdigit())


def _cluster_name_signatures(signatures: list[dict]) -> list[set[str]]:
    """Cluster one name's signatures into athlete groups (union-find).

    ``signatures`` are dicts with ``key`` (the ``(norm_name, gnz_id)`` tuple),
    ``id``, ``events``, ``disciplines``, ``clubs``, ``count`` and ``override``.
    Returns a list of signature-key sets — one per distinct person the name
    represents.  Empty-ID signatures attach to the group containing the most
    frequent non-empty ID (or form their own group when the name has no IDs).

    Rows carrying a non-empty ``identity_override`` (an admin force-split) are
    a hard boundary: each distinct token is its own person, and unmarked rows
    cluster among themselves with the normal rules.
    """
    marked = [s for s in signatures if s.get("override")]
    if marked:
        groups: list[set[str]] = []
        unmarked = [s for s in signatures if not s.get("override")]
        if unmarked:
            groups.extend(_cluster_name_signatures(unmarked))
        by_token: dict[str, set[str]] = defaultdict(set)
        for s in marked:
            by_token[s["override"]].add(s["key"])
        groups.extend(set(g) for g in by_token.values())
        return groups

    non_empty = sorted({s["id"] for s in signatures if s["id"]})
    keys_by_id: dict[str, list[str]] = defaultdict(list)
    for s in signatures:
        keys_by_id[s["id"]].append(s["key"])
    count_by_id = {s["id"]: s["count"] for s in signatures}

    def _attach_empty(groups: list[set[str]]) -> list[set[str]]:
        empty_keys = keys_by_id.get("", [])
        if not empty_keys:
            return groups
        if not groups:
            return [{k for k in empty_keys}]
        best_group = max(
            groups,
            key=lambda g: sum(count_by_id.get(key[1], 0) for key in g),
        )
        best_group.update(empty_keys)
        return groups

    if len(non_empty) <= 1:
        return [{s["key"] for s in signatures}]

    events_by_id = {s["id"]: s["events"] for s in signatures}
    discs_by_id = {s["id"]: s["disciplines"] for s in signatures}
    clubs_by_id = {s["id"]: s["clubs"] for s in signatures}

    if _same_event_collision(events_by_id):
        # Distinct people sharing a name — each ID stays its own athlete.
        groups = [{k for k in keys_by_id[gid]} for gid in non_empty]
        return _attach_empty(groups)

    if _disciplines_conflict(discs_by_id):
        # Split by discipline, union IDs within the same discipline.
        by_disc: dict[str, set[str]] = defaultdict(set)
        for s in signatures:
            for disc in s["disciplines"]:
                by_disc[disc].add(s["id"])
        groups = []
        for disc_ids in by_disc.values():
            members: set[str] = set()
            for gid in disc_ids:
                members.update(keys_by_id[gid])
            groups.append(members)
        return _attach_empty(groups)

    # No collision / discipline conflict: merge IDs that share a club.  IDs
    # with disjoint club sets are likely different people (a person keeps their
    # ID when they change clubs), so they stay separate.
    uf = _UnionFind()
    for s in signatures:
        uf.union(s["key"], s["key"])
    club_to_ids: dict[str, set[str]] = defaultdict(set)
    for s in signatures:
        for club in s["clubs"]:
            club_to_ids[club].add(s["id"])
    if any(club_to_ids.values()):
        for club_ids in club_to_ids.values():
            sorted_ids = sorted(club_ids)
            for i in range(1, len(sorted_ids)):
                uf.union(keys_by_id[sorted_ids[0]][0], keys_by_id[sorted_ids[i]][0])
        # IDs with no club rows attach to the most frequent club-linked ID.
        club_linked = {gid for gids in club_to_ids.values() for gid in gids}
        unlinked = [gid for gid in non_empty if gid not in club_linked]
        if unlinked:
            best_id = max(
                (gid for gid in non_empty if gid in club_linked),
                key=lambda gid: count_by_id[gid],
            )
            for gid in unlinked:
                uf.union(keys_by_id[best_id][0], keys_by_id[gid][0])
    else:
        all_non_empty = [k for gid in non_empty for k in keys_by_id[gid]]
        for i in range(1, len(all_non_empty)):
            uf.union(all_non_empty[0], all_non_empty[i])

    # Empty-ID signature joins the dominant (most frequent non-empty) ID.
    empty_keys = keys_by_id.get("", [])
    if empty_keys:
        best_id = max(non_empty, key=lambda gid: count_by_id[gid])
        for k in empty_keys:
            uf.union(keys_by_id[best_id][0], k)

    return [set(g) for g in uf.components().values()]


def _signature_hash(canonical_norm: str, canonical_id: str) -> str:
    digest = hashlib.sha1(f"{canonical_norm}\x00{canonical_id}".encode("utf-8")).hexdigest()
    return digest


def _slug_from_hash(digest: str) -> str:
    return f"a{digest[:10]}"


def _redirect_target(
    session, target_id: int, orphan_slugs: dict[int, str]
) -> int | None:
    """Resolve a redirect's target to a live athlete, following merge chains.

    ``orphan_slugs`` maps athlete ids deleted this rebuild to their slugs, so
    a target merged away in this same rebuild (A->B then B->C) can be followed
    through its newly-recorded redirect.  Returns ``None`` when no live athlete
    exists at the end of the chain.
    """
    seen: set[int] = set()
    while target_id is not None and target_id not in seen:
        seen.add(target_id)
        if target_id in orphan_slugs:
            old_slug = orphan_slugs[target_id]
        elif session.get(Athlete, target_id) is not None:
            return target_id
        else:
            old_slug = orphan_slugs.get(target_id)
        if old_slug is None:
            return None
        hop = (
            session.query(SlugRedirect)
            .filter(SlugRedirect.old_slug == old_slug)
            .first()
        )
        if hop is None:
            return None
        target_id = hop.athlete_id
    return None


def rebuild_athletes(session) -> int:
    """Recompute athlete identities and assign ``long_scores.athlete_id``.

    Idempotent and signature-stable: existing ``Athlete`` rows are reused when
    their cluster's canonical ``(normalized name, gnz_id)`` is unchanged, and
    athletes with no remaining rows are deleted.  Returns the number of
    athletes after the rebuild.
    """
    rows = (
        session.query(
            func.trim(func.lower(LongScore.gymnast_name)).label("norm"),
            LongScore.gymnast_name,
            LongScore.gnz_id,
            LongScore.event_id,
            LongScore.discipline,
            LongScore.club_name,
            LongScore.identity_override,
            func.count(LongScore.id).label("cnt"),
        )
        .filter(
            LongScore.gymnast_name.isnot(None),
            LongScore.gymnast_name != "",
        )
        .group_by(
            func.trim(func.lower(LongScore.gymnast_name)),
            LongScore.gymnast_name,
            LongScore.gnz_id,
            LongScore.event_id,
            LongScore.discipline,
            LongScore.club_name,
            LongScore.identity_override,
        )
        .all()
    )

    sig_data: dict[tuple[str, str], dict] = {}
    for norm, spelling, gid, eid, disc, club, override, cnt in rows:
        key = (norm, gid or "")
        if key not in sig_data:
            sig_data[key] = {
                "key": key,
                "norm": norm,
                "id": gid or "",
                "count": 0,
                "events": set(),
                "disciplines": set(),
                "clubs": set(),
                "spellings": Counter(),
                "override": override or "",
            }
        d = sig_data[key]
        d["count"] += cnt
        if eid is not None:
            d["events"].add(eid)
        if disc:
            d["disciplines"].add(disc)
        if club:
            d["clubs"].add(club)
        d["spellings"][spelling.strip()] += cnt
        if override:
            d["override"] = override

    if not sig_data:
        existing = session.query(Athlete).all()
        for athlete in existing:
            session.delete(athlete)
        session.commit()
        return 0

    # --- Within-name clustering -----------------------------------------
    by_name: dict[str, list[dict]] = defaultdict(list)
    for d in sig_data.values():
        by_name[d["norm"]].append(d)

    uf = _UnionFind()
    for d in sig_data.values():
        uf.union(d["key"], d["key"])
    for sigs in by_name.values():
        for group in _cluster_name_signatures(sigs):
            anchor = min(group)
            for key in group:
                uf.union(key, anchor)

    # --- Cross-name clustering (shared numeric ID + similar name) ------
    id_to_sigs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, d in sig_data.items():
        if d["id"].isdigit():
            id_to_sigs[d["id"]].append(key)
    for gid, keys in id_to_sigs.items():
        if len(keys) < 2:
            continue
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if a == b:
                    continue
                name_a = sig_data[a]["norm"]
                name_b = sig_data[b]["norm"]
                if name_a == name_b:
                    continue
                if _names_similar(name_a, name_b):
                    uf.union(a, b)

    components = uf.components()

    # --- Aggregate per component ----------------------------------------
    component_data: dict = {}
    for root, keys in components.items():
        norm_counter: Counter = Counter()
        id_counter: Counter = Counter()
        spelling_counter: Counter = Counter()
        count = 0
        for key in keys:
            d = sig_data[key]
            count += d["count"]
            spelling_counter.update(d["spellings"])
            if d["id"]:
                id_counter[d["id"]] += d["count"]
            norm_counter[d["norm"]] += d["count"]
        canonical_norm = max(norm_counter, key=lambda n: (norm_counter[n], -len(n), n.lower()))
        numeric = [gid for gid in id_counter if gid.isdigit()]
        if numeric:
            canonical_id = max(numeric, key=lambda gid: (id_counter[gid], gid))
        elif id_counter:
            canonical_id = max(id_counter, key=lambda gid: (id_counter[gid], gid))
        else:
            canonical_id = ""
        canonical_name = max(
            spelling_counter,
            key=lambda n: (spelling_counter[n], -len(n), n.lower()),
        )
        component_data[root] = {
            "canonical_name": canonical_name,
            "canonical_norm": canonical_norm,
            "gnz_id": canonical_id or None,
            "count": count,
        }

    # --- Signature-stable upsert of athletes ----------------------------
    existing = {a.signature_hash: a for a in session.query(Athlete).all()}
    sig_to_athlete: dict[tuple[str, str], int] = {}
    athlete_names: dict[int, str] = {}
    hashes_in_use: set[str] = set()
    for root, meta in component_data.items():
        digest = _signature_hash(meta["canonical_norm"], meta["gnz_id"] or "")
        slug = _slug_from_hash(digest)
        hashes_in_use.add(digest)
        athlete = existing.get(digest)
        if athlete is None:
            athlete = Athlete(
                signature_hash=digest,
                slug=slug,
                canonical_name=meta["canonical_name"],
                gnz_id=meta["gnz_id"],
            )
            session.add(athlete)
            session.flush()
            existing[digest] = athlete
        else:
            athlete.canonical_name = meta["canonical_name"]
            athlete.slug = slug
            athlete.gnz_id = meta["gnz_id"]
        for key in components[root]:
            sig_to_athlete[key] = athlete.id
            athlete_names[athlete.id] = meta["canonical_name"]

    # --- Capture signature keys of soon-to-be-orphaned athletes --------
    # Rows still point at the old athlete here, so their (norm, gnz_id)
    # signatures reveal which new athlete will absorb them.  Used to build
    # slug redirects so old gymnast URLs keep resolving after a merge/split.
    orphan_keys: dict[str, list[tuple[tuple[str, str], int]]] = {}
    for digest, athlete in existing.items():
        if digest in hashes_in_use:
            continue
        rows = (
            session.query(
                func.trim(func.lower(LongScore.gymnast_name)).label("norm"),
                LongScore.gnz_id,
                func.count(LongScore.id),
            )
            .filter(LongScore.athlete_id == athlete.id)
            .group_by(
                func.trim(func.lower(LongScore.gymnast_name)),
                LongScore.gnz_id,
            )
            .all()
        )
        if rows:
            orphan_keys[athlete.slug] = [((norm, gid or ""), cnt) for norm, gid, cnt in rows]

    # --- Assign athlete_id to long_scores -------------------------------
    for key, athlete_id in sig_to_athlete.items():
        norm, gid = key
        if gid:
            session.query(LongScore).filter(
                func.trim(func.lower(LongScore.gymnast_name)) == norm,
                LongScore.gnz_id == gid,
            ).update({LongScore.athlete_id: athlete_id}, synchronize_session=False)
        else:
            session.query(LongScore).filter(
                func.trim(func.lower(LongScore.gymnast_name)) == norm,
                (LongScore.gnz_id.is_(None)) | (LongScore.gnz_id == ""),
            ).update({LongScore.athlete_id: athlete_id}, synchronize_session=False)

    # Orphans are deleted only after re-pointing, so no ``long_scores`` row
    # still references an athlete whose signature changed this rebuild.
    orphan_slugs: dict[int, str] = {}
    for digest, athlete in list(existing.items()):
        if digest not in hashes_in_use:
            orphan_slugs[athlete.id] = athlete.slug

    # --- Slug redirects for the deleted athletes -----------------------
    # An orphan's rows were re-pointed to their new owner above; record
    # ``old_slug -> new owner`` so the old gymnast URL 301s there instead of
    # 404ing.  When several keys split the rows across owners, keep the key
    # with the most rows (one redirect per old slug).
    for slug, entries in orphan_keys.items():
        best_key = max(entries, key=lambda e: e[1])[0]
        new_owner = sig_to_athlete.get(best_key)
        if new_owner is not None:
            session.add(SlugRedirect(old_slug=slug, athlete_id=new_owner))

    # Re-point existing redirects whose target is deleted this rebuild (a
    # chain: A->B then B->C).  Must happen BEFORE the orphans are deleted —
    # ``slug_redirects.athlete_id`` is a foreign key to ``athletes``.
    for redirect in list(session.query(SlugRedirect).all()):
        if redirect.athlete_id not in orphan_slugs:
            continue
        target = _redirect_target(session, redirect.athlete_id, orphan_slugs)
        if target is None:
            session.delete(redirect)
        elif target != redirect.athlete_id:
            redirect.athlete_id = target

    # Persist the redirect inserts/re-points first, then drop the orphans
    # (no redirect references them any more, so the FK delete succeeds).
    session.flush()
    for digest, athlete in list(existing.items()):
        if digest not in hashes_in_use:
            session.delete(athlete)
    session.flush()

    # --- Prune redirects ------------------------------------------------
    # An identity that came back (same signature re-ingested) makes the old
    # slug live again — drop the stale redirect, the URL works on its own.
    live_slugs = {
        r[0]
        for r in session.query(Athlete.slug)
        .filter(Athlete.slug.isnot(None))
        .all()
    }
    for redirect in list(session.query(SlugRedirect).all()):
        if redirect.old_slug in live_slugs:
            session.delete(redirect)
            continue
        target = _redirect_target(session, redirect.athlete_id, orphan_slugs)
        if target is None:
            session.delete(redirect)
        elif target != redirect.athlete_id:
            redirect.athlete_id = target

    # --- Back-write: unify raw spelling to the canonical name -----------
    # Every row of an athlete now carries the cluster's most-common spelling,
    # so name-keyed queries, stats counts and per-event groupings stop seeing
    # variant spellings as separate people/marks.  Idempotent: once the raw
    # column matches ``canonical_name`` the UPDATE matches zero rows.
    for athlete_id, canonical_name in athlete_names.items():
        session.query(LongScore).filter(
            LongScore.athlete_id == athlete_id,
            LongScore.gymnast_name != canonical_name,
        ).update(
            {LongScore.gymnast_name: canonical_name},
            synchronize_session=False,
        )

    session.commit()
    return len(component_data)


def _names_similar(a: str, b: str) -> bool:
    """Whether two normalized names are close enough to be the same person."""
    matcher = difflib.SequenceMatcher(None, a, b)
    if matcher.quick_ratio() < _NAME_SIMILARITY_THRESHOLD:
        return False
    return matcher.ratio() >= _NAME_SIMILARITY_THRESHOLD


def athlete_lookup(session) -> dict[str, Athlete]:
    """Return ``{id: Athlete}`` for all athletes (slug/name/gnz_id lookups)."""
    return {a.id: a for a in session.query(Athlete).all()}


def resolve_identity(session, slug: str | None = None, gnz_id: str | None = None) -> int | None:
    """Resolve a slug (``a...``) or legacy gnz_id to a single athlete id.

    A slug that no longer exists (e.g. merged away) is followed through its
    ``SlugRedirect`` to the athlete that absorbed it.  Returns ``None`` when
    nothing matches, or when a gnz_id maps to multiple athletes (callers fall
    back to the raw gnz_id match).
    """
    if slug:
        athlete = (
            session.query(Athlete)
            .filter(Athlete.slug == slug)
            .first()
        )
        if athlete:
            return athlete.id
        redirect = (
            session.query(SlugRedirect)
            .filter(SlugRedirect.old_slug == slug)
            .first()
        )
        if redirect is not None and session.get(Athlete, redirect.athlete_id) is not None:
            return redirect.athlete_id
        return None
    if gnz_id:
        matches = (
            session.query(Athlete)
            .filter(Athlete.gnz_id == gnz_id)
            .all()
        )
        if len(matches) == 1:
            return matches[0].id
    return None


if __name__ == "__main__":
    from app.database import get_session

    session = get_session()
    try:
        count = rebuild_athletes(session)
        print(f"Rebuilt {count} athletes")
    finally:
        session.close()
