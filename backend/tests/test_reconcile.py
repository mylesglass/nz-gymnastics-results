import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.models import Base, LongScore
from app.reconcile import reconcile_athletes
from app.main import app

client = TestClient(app)


def _setup_db():
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
    return db_path, engine, TestSession, old_engine, old_session


def _teardown_db(db_path, old_engine, old_session):
    import app.database as db_mod
    os.unlink(db_path)
    db_mod.engine = old_engine
    db_mod.SessionLocal = old_session


def _seed(session, rows: list[dict]):
    for r in rows:
        session.add(LongScore(**r))
    session.commit()


class TestReconcile:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.db_path, _, TestSession, self.old_engine, self.old_session = _setup_db()
        import app.database as db_mod
        init_db()
        self.TestSession = TestSession
        yield
        _teardown_db(self.db_path, self.old_engine, self.old_session)

    BASE = {"discipline": "WAG", "pass_number": 1}

    def test_single_id_no_change(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "apparatus": "UB", "event_name": "E1"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 0
        assert report["names_unified"] == 0
        assert report["conflicts"] == []

    def test_unifies_two_ids_favoring_numeric(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "123", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "Alice Smith", "gnz_id": "X456", "apparatus": "UB", "event_name": "E2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 1
        assert report["names_unified"] == 1
        sess2 = self.TestSession()
        remaining = sess2.query(LongScore).all()
        for r in remaining:
            assert r.gnz_id == "123"
        sess2.close()

    def test_numeric_preferred(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Frankie R", "gnz_id": "766580", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "Frankie R", "gnz_id": "G66580", "apparatus": "UB", "event_name": "E2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 1
        assert report["names_unified"] == 1
        sess2 = self.TestSession()
        remaining = sess2.query(LongScore).all()
        for r in remaining:
            assert r.gnz_id == "766580"
        sess2.close()

    def test_most_frequent_wins(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Bob Jones", "gnz_id": "111", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "Bob Jones", "gnz_id": "111", "apparatus": "UB", "event_name": "E1"},
            {**self.BASE, "event_id": 3, "gymnast_name": "Bob Jones", "gnz_id": "111", "apparatus": "BB", "event_name": "E2"},
            {**self.BASE, "event_id": 4, "gymnast_name": "Bob Jones", "gnz_id": "222", "apparatus": "FX", "event_name": "E3"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 1
        sess2 = self.TestSession()
        remaining = sess2.query(LongScore).all()
        for r in remaining:
            assert r.gnz_id == "111"
        sess2.close()

    def test_tie_reported_as_conflict(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Tie Girl", "gnz_id": "555", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "Tie Girl", "gnz_id": "666", "apparatus": "UB", "event_name": "E2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert len(report["conflicts"]) == 1
        assert report["ids_corrected"] == 0
        sess2 = self.TestSession()
        remaining = sess2.query(LongScore).all()
        ids = set(r.gnz_id for r in remaining)
        assert ids == {"555", "666"}
        sess2.close()

    def test_empty_ids_ignored(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "No ID", "gnz_id": None, "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "No ID", "gnz_id": "", "apparatus": "UB", "event_name": "E2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 0
        assert report["names_unified"] == 0

    def test_case_insensitive_matching(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Alice Smith", "gnz_id": "100", "apparatus": "VT", "event_name": "E1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "alice smith", "gnz_id": "X200", "apparatus": "UB", "event_name": "E2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["names_unified"] == 1
        assert report["ids_corrected"] == 1

    def test_non_numeric_id_loses(self):
        sess = self.TestSession()
        _seed(sess, [
            {**self.BASE, "event_id": 1, "gymnast_name": "Monique F", "gnz_id": "662330", "apparatus": "VT", "event_name": "E1", "club_name": "C1"},
            {**self.BASE, "event_id": 2, "gymnast_name": "Monique F", "gnz_id": "AGA", "apparatus": "UB", "event_name": "E2", "club_name": "C2"},
        ])
        sess.close()
        report = reconcile_athletes()
        assert report["ids_corrected"] == 1
        sess2 = self.TestSession()
        remaining = sess2.query(LongScore).all()
        for r in remaining:
            assert r.gnz_id == "662330"
        sess2.close()

    def test_api_endpoint_requires_admin(self):
        os.environ["ADMIN_PASSWORD"] = "test"
        os.environ["JWT_SECRET"] = "test-secret-reconcile"
        from app.auth import seed_admin_user
        init_db()
        seed_admin_user()
        try:
            # No auth token → 401
            resp = client.post("/api/admin/reconcile-athletes")
            assert resp.status_code == 401
            # Login as admin
            login = client.post("/api/auth/login", json={"username": "admin", "password": "test"})
            token = login.json()["access_token"]
            resp2 = client.post("/api/admin/reconcile-athletes", headers={"Authorization": f"Bearer {token}"})
            assert resp2.status_code == 200
        finally:
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("JWT_SECRET", None)
