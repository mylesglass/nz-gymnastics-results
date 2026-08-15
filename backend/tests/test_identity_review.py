"""Tests for the admin identity review + merge/split endpoints."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.athlete_identity import rebuild_athletes
from app.main import app
from app.models import Athlete, Base, Event, LongScore, SlugRedirect, WellingtonIntent

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)

    import app.database as db_mod

    old_engine = db_mod.engine
    old_session = db_mod.SessionLocal
    db_mod.engine = engine
    db_mod.SessionLocal = TestSession

    yield TestSession

    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


class TestIdentityReview:
    BASE = {"discipline": "WAG", "pass_number": 1, "apparatus": "VT", "event_name": "E"}

    def _event(self, session, year=2026, name="Meet 2026") -> int:
        ev = Event(name=name, start_date=f"{year}-03-01", end_date=f"{year}-03-02", discipline="WAG", year=year)
        session.add(ev)
        session.flush()
        return ev.id

    def _seed(self, session, rows: list[dict]) -> None:
        for r in rows:
            session.add(LongScore(**{**self.BASE, **r}))
        session.commit()

    def _athletes(self, session) -> dict[str, list[Athlete]]:
        by_name: dict[str, list[Athlete]] = {}
        for a in session.query(Athlete).all():
            by_name.setdefault(a.canonical_name, []).append(a)
        return by_name

    def _review(self) -> dict:
        resp = client.get("/api/admin/identity-review")
        assert resp.status_code == 200
        return resp.json()

    def test_review_reports_name_conflicts(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            data = self._review()
            groups = [g for g in data["name_conflicts"] if g["name"] == "Madison Lynch"]
            assert len(groups) == 1
            assert len(groups[0]["athletes"]) == 2
            assert {a["gnz_id"] for a in groups[0]["athletes"]} == {"249317", "716561"}
        finally:
            session.close()

    def test_review_reports_id_conflicts(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Alex Sims", "gnz_id": "102232", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Alexander Sims", "gnz_id": "102232", "club_name": "C2"},
            ])
            rebuild_athletes(session)
            data = self._review()
            groups = [g for g in data["id_conflicts"] if g["gnz_id"] == "102232"]
            assert len(groups) == 1
            assert len(groups[0]["athletes"]) == 2
            assert {a["name"] for a in groups[0]["athletes"]} == {"Alex Sims", "Alexander Sims"}
        finally:
            session.close()

    def test_review_reports_multi_id_athlete(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Adam Lim", "gnz_id": "184417", "club_name": "OMNI"},
                {"event_id": ev2, "gymnast_name": "Adam Lim", "gnz_id": "273749", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            data = self._review()
            names = [m["name"] for m in data["multi_id_athletes"]]
            assert "Adam Lim" in names
            multi = next(m for m in data["multi_id_athletes"] if m["name"] == "Adam Lim")
            assert set(multi["gnz_ids"]) == {"184417", "273749"}
        finally:
            session.close()

    def test_review_reports_similar_names(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Mathew Jones", "gnz_id": "1001", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Matthew Jones", "gnz_id": "1002", "club_name": "C2"},
            ])
            rebuild_athletes(session)
            data = self._review()
            pairs = [
                m for m in data["similar_names"]
                if {m["name_a"], m["name_b"]} == {"Mathew Jones", "Matthew Jones"}
            ]
            assert len(pairs) == 1
        finally:
            session.close()

    def test_merge_same_name_athletes(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            groups = self._athletes(session)["Madison Lynch"]
            assert len(groups) == 2
            survivor = next(a for a in groups if a.gnz_id == "249317")
            merged = next(a for a in groups if a.gnz_id == "716561")

            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200
            body = resp.json()
            assert body["survivor_id"] == survivor.id
            assert body["survivor_slug"] == survivor.slug

            remaining = self._athletes(session).get("Madison Lynch", [])
            assert len(remaining) == 1
            rows = session.query(LongScore).all()
            assert len({r.athlete_id for r in rows}) == 1
            assert all(r.gnz_id == "249317" for r in rows)
        finally:
            session.close()

    def test_merge_variant_names_shared_id(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Alex Sims", "gnz_id": "102232", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Alexander Sims", "gnz_id": "102232", "club_name": "C2"},
            ])
            rebuild_athletes(session)
            groups = self._athletes(session)
            survivor = groups["Alexander Sims"][0]
            merged = groups["Alex Sims"][0]

            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200

            all_names = {a.canonical_name for a in session.query(Athlete).all()}
            assert all_names == {"Alexander Sims"}
            assert len(session.query(Athlete).all()) == 1
        finally:
            session.close()

    def test_merge_moves_wellington_intent(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            groups = self._athletes(session)["Madison Lynch"]
            survivor = next(a for a in groups if a.gnz_id == "249317")
            merged = next(a for a in groups if a.gnz_id == "716561")
            session.add(WellingtonIntent(athlete_id=merged.id, gnz_id="716561", year=2026))
            session.commit()

            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200

            intents = session.query(WellingtonIntent).all()
            assert len(intents) == 1
            assert intents[0].athlete_id == survivor.id
        finally:
            session.close()

    def test_merge_self_rejected(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Eva McEwan", "gnz_id": "999", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            aid = session.query(Athlete).first().id
            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": aid,
                "merge_id": aid,
            })
            assert resp.status_code == 400
        finally:
            session.close()

    def test_split_by_gnz_id(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Adam Lim", "gnz_id": "184417", "club_name": "OMNI"},
                {"event_id": ev2, "gymnast_name": "Adam Lim", "gnz_id": "273749", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            athletes = session.query(Athlete).all()
            assert len(athletes) == 1
            aid = athletes[0].id

            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid,
                "split_by": "gnz_id",
                "value": "273749",
            })
            assert resp.status_code == 200
            body = resp.json()
            assert body["split_rows"] == 1
            assert body["created_slug"] != body["original_slug"]

            by_name = self._athletes(session)["Adam Lim"]
            assert len(by_name) == 2
            created = next(a for a in by_name if a.id == body["created_id"])
            assert created.gnz_id.startswith("S")
            original = next(a for a in by_name if a.id == body["original_id"])
            assert original.gnz_id == "184417"

            data = self._review()
            assert not any(m["name"] == "Adam Lim" for m in data["multi_id_athletes"])
        finally:
            session.close()

    def test_split_by_event(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Bob Smith", "gnz_id": "555", "club_name": "C1"},
                {"event_id": ev1, "gymnast_name": "Bob Smith", "gnz_id": "555", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Bob Smith", "gnz_id": "555", "club_name": "C1"},
            ])
            rebuild_athletes(session)
            assert len(session.query(Athlete).all()) == 1

            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": session.query(Athlete).first().id,
                "split_by": "event_id",
                "value": str(ev2),
            })
            assert resp.status_code == 200
            assert resp.json()["split_rows"] == 1
            assert len(session.query(Athlete).all()) == 2
        finally:
            session.close()

    def test_split_custom_gnz_id(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Adam Lim", "gnz_id": "184417", "club_name": "OMNI"},
                {"event_id": ev2, "gymnast_name": "Adam Lim", "gnz_id": "273749", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            aid = session.query(Athlete).first().id

            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid,
                "split_by": "gnz_id",
                "value": "273749",
                "new_gnz_id": "910203",
            })
            assert resp.status_code == 200
            created = session.get(Athlete, resp.json()["created_id"])
            assert created.gnz_id == "910203"
        finally:
            session.close()

    def test_split_persists_across_rebuilds_and_merge_undoes_it(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Adam Lim", "gnz_id": "184417", "club_name": "OMNI"},
                {"event_id": ev2, "gymnast_name": "Adam Lim", "gnz_id": "273749", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            aid = session.query(Athlete).first().id

            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid,
                "split_by": "gnz_id",
                "value": "273749",
            })
            assert resp.status_code == 200
            body = resp.json()
            assert len(session.query(Athlete).all()) == 2

            # The force-split survives an untouched rebuild.
            rebuild_athletes(session)
            assert len(session.query(Athlete).all()) == 2

            # Merging the halves back collapses them into one athlete.
            resp2 = client.post("/api/admin/athletes/merge", json={
                "athlete_id": body["original_id"],
                "merge_id": body["created_id"],
            })
            assert resp2.status_code == 200
            assert len(session.query(Athlete).all()) == 1
            assert len(session.query(LongScore).all()) == 2
            assert all(r.athlete_id == session.query(Athlete).first().id for r in session.query(LongScore).all())
        finally:
            session.close()

    def test_split_guards(self, setup_db):
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Bob Smith", "gnz_id": "555", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Bob Smith", "gnz_id": "555", "club_name": "C1"},
            ])
            rebuild_athletes(session)
            aid = session.query(Athlete).first().id

            # Unknown split_by
            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid, "split_by": "bad", "value": "x",
            })
            assert resp.status_code == 400

            # No rows match the value
            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid, "split_by": "gnz_id", "value": "000000",
            })
            assert resp.status_code == 400

            # Splitting off every row
            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid, "split_by": "club_name", "value": "C1",
            })
            assert resp.status_code == 400

            # Missing athlete
            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": 99999, "split_by": "gnz_id", "value": "555",
            })
            assert resp.status_code == 404
        finally:
            session.close()

    def test_merge_redirects_old_slug_to_survivor(self, setup_db):
        from app.athlete_identity import resolve_identity
        from app.cache import invalidate as clear_cache
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": ev2, "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            groups = self._athletes(session)["Madison Lynch"]
            assert len(groups) == 2
            survivor = next(a for a in groups if a.gnz_id == "249317")
            merged = next(a for a in groups if a.gnz_id == "716561")

            clear_cache()
            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200

            # The merged-away slug now resolves to the survivor via a redirect.
            clear_cache()
            g = client.get("/api/gymnast", params={"slug": merged.slug}).json()
            assert g is not None
            assert g["slug"] == survivor.slug
            assert g["name"] == "Madison Lynch"
            assert resolve_identity(session, slug=merged.slug) == survivor.id
            assert resolve_identity(session, slug=survivor.slug) == survivor.id
        finally:
            session.close()

    def test_merge_empty_id_survivor_redirects_both_old_slugs(self, setup_db):
        from app.athlete_identity import resolve_identity
        from app.cache import invalidate as clear_cache
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Alex Sims", "gnz_id": "102232", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Alexander Sims", "gnz_id": "", "club_name": "C2"},
            ])
            rebuild_athletes(session)
            by_name = self._athletes(session)
            survivor = by_name["Alexander Sims"][0]
            merged = by_name["Alex Sims"][0]
            old_slugs = {survivor.slug, merged.slug}

            clear_cache()
            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200

            # Both previously-open URLs resolve to the one new survivor slug.
            clear_cache()
            resolved = set()
            for slug in old_slugs:
                g = client.get("/api/gymnast", params={"slug": slug}).json()
                assert g is not None, slug
                resolved.add(g["slug"])
            assert len(resolved) == 1
            new_slug = next(iter(resolved))
            assert new_slug not in old_slugs

            target = resolve_identity(session, slug=next(iter(old_slugs)))
            assert target is not None
            for slug in old_slugs:
                assert resolve_identity(session, slug=slug) == target
        finally:
            session.close()

    def test_redirect_pruned_when_identity_resurrected(self, setup_db):
        from app.cache import invalidate as clear_cache
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Alex Sims", "gnz_id": "102232", "club_name": "C1"},
                {"event_id": ev2, "gymnast_name": "Alexander Sims", "gnz_id": "", "club_name": "C2"},
            ])
            rebuild_athletes(session)
            by_name = self._athletes(session)
            survivor = by_name["Alexander Sims"][0]
            merged = by_name["Alex Sims"][0]
            merged_slug = merged.slug

            clear_cache()
            resp = client.post("/api/admin/athletes/merge", json={
                "athlete_id": survivor.id,
                "merge_id": merged.id,
            })
            assert resp.status_code == 200

            # Re-ingesting the merged-away signature brings the slug back live.
            ev3 = self._event(session, name="Reingest Meet")
            self._seed(session, [
                {"event_id": ev3, "gymnast_name": "Alex Sims", "gnz_id": "102232", "club_name": "C1"},
            ])
            rebuild_athletes(session)

            clear_cache()
            g = client.get("/api/gymnast", params={"slug": merged_slug}).json()
            assert g is not None
            assert g["slug"] == merged_slug
            assert (
                session.query(SlugRedirect)
                .filter(SlugRedirect.old_slug == merged_slug)
                .first()
                is None
            )
        finally:
            session.close()

    def test_split_does_not_leave_self_redirect(self, setup_db):
        from app.athlete_identity import resolve_identity
        from app.cache import invalidate as clear_cache
        session = setup_db()
        try:
            ev1 = self._event(session)
            ev2 = self._event(session, name="Other Meet")
            self._seed(session, [
                {"event_id": ev1, "gymnast_name": "Adam Lim", "gnz_id": "184417", "club_name": "OMNI"},
                {"event_id": ev2, "gymnast_name": "Adam Lim", "gnz_id": "273749", "club_name": "OMNI"},
            ])
            rebuild_athletes(session)
            aid = session.query(Athlete).first().id

            clear_cache()
            resp = client.post("/api/admin/athletes/split", json={
                "athlete_id": aid,
                "split_by": "gnz_id",
                "value": "273749",
            })
            assert resp.status_code == 200
            body = resp.json()

            assert resolve_identity(session, slug=body["original_slug"]) == body["original_id"]
            assert resolve_identity(session, slug=body["created_slug"]) == body["created_id"]
            assert (
                session.query(SlugRedirect)
                .filter(SlugRedirect.old_slug == body["original_slug"])
                .first()
                is None
            )
        finally:
            session.close()

    def test_merge_chain_repoints_redirects(self, setup_db):
        from app.athlete_identity import resolve_identity
        from app.cache import invalidate as clear_cache
        session = setup_db()
        try:
            evs = [self._event(session, name=f"Meet {i}") for i in range(3)]
            self._seed(session, [
                {"event_id": evs[0], "gymnast_name": "Madison Lynch", "gnz_id": "249317", "club_name": "Onslow"},
                {"event_id": evs[1], "gymnast_name": "Madison Lynch", "gnz_id": "716561", "club_name": "OMNI"},
                {"event_id": evs[2], "gymnast_name": "Madison Lynch", "gnz_id": "999999", "club_name": "CSG"},
            ])
            rebuild_athletes(session)
            groups = self._athletes(session)["Madison Lynch"]
            assert len(groups) == 3
            by_id = {a.gnz_id: a for a in groups}
            slugs = {gid: a.slug for gid, a in by_id.items()}

            # A (249317) merged into B (716561)...
            clear_cache()
            r = client.post("/api/admin/athletes/merge", json={
                "athlete_id": by_id["716561"].id,
                "merge_id": by_id["249317"].id,
            })
            assert r.status_code == 200
            b_id = r.json()["survivor_id"]

            # ...then B merged into C (999999). A's redirect must re-point to C.
            clear_cache()
            r2 = client.post("/api/admin/athletes/merge", json={
                "athlete_id": by_id["999999"].id,
                "merge_id": b_id,
            })
            assert r2.status_code == 200
            c_id = r2.json()["survivor_id"]

            for slug in (slugs["249317"], slugs["716561"], slugs["999999"]):
                assert resolve_identity(session, slug=slug) == c_id
        finally:
            session.close()


class TestIdentityReviewAuth:
    def test_review_requires_admin(self):
        os.environ["ADMIN_PASSWORD"] = "test"
        os.environ["JWT_SECRET"] = "test-secret-identity-review"
        from app.auth import seed_admin_user
        from app.database import init_db
        init_db()
        seed_admin_user()
        try:
            resp = client.get("/api/admin/identity-review")
            assert resp.status_code == 401
            login = client.post("/api/auth/login", json={"username": "admin", "password": "test"})
            token = login.json()["access_token"]
            resp2 = client.get("/api/admin/identity-review", headers={"Authorization": f"Bearer {token}"})
            assert resp2.status_code == 200
        finally:
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("JWT_SECRET", None)
