"""Tests for ingest-time GNZ ID backfill safety (_ingest_event).

Covers the guard that stops a missing ``gnz_id`` from being auto-filled when
the name is ambiguous in the existing database:

* a name mapped to 2+ distinct numeric IDs must stay blank (never guess);
* a name mapped to exactly one numeric ID is backfilled;
* non-numeric / club-code existing IDs are never used for backfill.
"""

import os
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import _ingest_event, app
from app.models import Base, Event, LongScore

client = TestClient(app)

BASE_SCORE = {"discipline": "WAG", "pass_number": 1, "apparatus": "VT"}


def _event_participants(name: str) -> list[dict]:
    return [{"_id": "p1", "name": name, "organizationId": "org1"}]


def _minimal_event(name: str = "Alice Smith") -> dict:
    """A structurally valid Scoreholder export for one gymnast, one vault."""
    return {
        "eventOrganizations": [{"_id": "org1", "name": "OMNI Gymnastic Centre"}],
        "eventParticipants": _event_participants(name),
        "performanceIndividuals": [{"_id": "ind1", "participantId": "p1", "unitId": "u1"}],
        "units": [{"_id": "u1", "name": "WAG STEP 5"}],
        "events": [{"name": "Test Event", "startDate": "2025-01-01", "endDate": "2025-01-02"}],
        "performanceRules": [
            {
                "_id": "pr1",
                "unitId": "u1",
                "scores": [
                    {
                        "id": "sd1",
                        "nodeTree": {
                            "interface": {
                                "outputs": [
                                    {"id": "score_val", "name": "Score"},
                                    {"id": "d_val", "name": "Difficulty"},
                                    {"id": "e_val", "name": "Execution"},
                                    {"id": "n_val", "name": "Neutral Deductions"},
                                ],
                            },
                        },
                    },
                ],
                "competition": {
                    "nodeTree": {
                        "nodes": [
                            {"id": "node1", "name": "Vault", "resultSets": [{"id": "rs1"}]},
                        ],
                    },
                },
            },
        ],
        "performanceScores": [
            {
                "_id": "s1",
                "unitScoreId": "sd1",
                "unitEventId": "ue1",
                "unitPassId": "up1",
                "entityId": "ind1",
                "publicOutputs": {"score_val": 12.0, "d_val": 5.0, "e_val": 7.0, "n_val": 0.0},
            },
        ],
        "performanceResultTables": [
            {
                "unitId": "u1",
                "resultTableId": "rt1",
                "resultSets": [
                    {
                        "id": "rs1",
                        "primaryRanking": [
                            {
                                "entityId": "ind1",
                                "rank": 1,
                                "value": 12.0,
                                "sourceItems": [{"itemId": "s1", "itemType": "score"}],
                            },
                        ],
                    },
                ],
            },
        ],
    }


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


def _seed_existing(session, name: str, ids: list[str]):
    for i, gid in enumerate(ids):
        eid = i + 1
        session.add(Event(
            id=eid, name=f"E{eid}",
            start_date=f"2024-01-0{eid}", end_date=f"2024-01-0{eid}",
            discipline="WAG", year=2024,
        ))
        session.add(LongScore(
            event_id=eid, event_name=f"E{eid}", gymnast_name=name, gnz_id=gid,
            club_name="OMNI Gymnastic Centre", **BASE_SCORE,
        ))
    session.commit()


def _ingest_new_event(name: str):
    """Ingest a new competition whose gymnast has no GNZ ID in the export."""
    data = _minimal_event(name)
    return _ingest_event(data, None)


class TestBackfillGuard:
    def test_ambiguous_name_stays_blank(self):
        # Two Madison-Lynch-style people share a name, so the DB maps it to two
        # distinct IDs. A new event's blank-ID rows must NOT be filled with either.
        db_path, _, TestSession, old_engine, old_session = _setup_db()
        try:
            sess = TestSession()
            _seed_existing(sess, "Alice Smith", ["100", "101"])
            sess.close()

            resp = _ingest_new_event("Alice Smith")
            sess = TestSession()
            rows = sess.query(LongScore).filter(LongScore.event_id == resp.id).all()
            assert len(rows) == 1
            assert rows[0].gnz_id in (None, "")  # stayed blank, no guess
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)

    def test_unambiguous_name_filled(self):
        # A name mapped to exactly one numeric ID can be safely backfilled.
        db_path, _, TestSession, old_engine, old_session = _setup_db()
        try:
            sess = TestSession()
            _seed_existing(sess, "Bob Jones", ["300"])
            sess.close()

            resp = _ingest_new_event("Bob Jones")
            sess = TestSession()
            rows = sess.query(LongScore).filter(LongScore.event_id == resp.id).all()
            assert len(rows) == 1
            assert rows[0].gnz_id == "300"
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)

    def test_non_numeric_id_never_backfilled(self):
        # A club-code ID (e.g. TRI) is not a GNZ ID and must never be assigned.
        db_path, _, TestSession, old_engine, old_session = _setup_db()
        try:
            sess = TestSession()
            _seed_existing(sess, "Carol Smith", ["TRI"])
            sess.close()

            resp = _ingest_new_event("Carol Smith")
            sess = TestSession()
            rows = sess.query(LongScore).filter(LongScore.event_id == resp.id).all()
            assert len(rows) == 1
            assert rows[0].gnz_id in (None, "")
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)

    def test_numeric_wins_over_non_numeric(self):
        # A name mapped to one numeric + one club-code ID is still unambiguous
        # (only the numeric ID counts), so backfill proceeds.
        db_path, _, TestSession, old_engine, old_session = _setup_db()
        try:
            sess = TestSession()
            _seed_existing(sess, "Dave Green", ["400", "TRI"])
            sess.close()

            resp = _ingest_new_event("Dave Green")
            sess = TestSession()
            rows = sess.query(LongScore).filter(LongScore.event_id == resp.id).all()
            assert len(rows) == 1
            assert rows[0].gnz_id == "400"
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)


class TestUploadWarnings:
    def test_synthetic_collision_surfaces_warnings(self):
        # A same-name-two-IDs collision in the upload must be reported, and the
        # two distinct people must NOT be merged by the post-ingest reconcile.
        db_path, _, TestSession, old_engine, old_session = _setup_db()
        try:
            data = _minimal_event()
            data["eventParticipants"] = [
                {"_id": "p1", "name": "Madison Lynch", "identifier": "249317", "organizationId": "org1"},
                {"_id": "p2", "name": "Madison Lynch", "identifier": "716561", "organizationId": "org1"},
            ]
            data["performanceIndividuals"] = [
                {"_id": "ind1", "participantId": "p1", "unitId": "u1"},
                {"_id": "ind2", "participantId": "p2", "unitId": "u1"},
            ]
            data["performanceScores"] = [
                {
                    "_id": "s1", "unitScoreId": "sd1", "unitEventId": "ue1", "unitPassId": "up1",
                    "entityId": "ind1", "publicOutputs": {"score_val": 12.0, "d_val": 5.0, "e_val": 7.0, "n_val": 0.0},
                },
                {
                    "_id": "s2", "unitScoreId": "sd1", "unitEventId": "ue1", "unitPassId": "up1",
                    "entityId": "ind2", "publicOutputs": {"score_val": 11.0, "d_val": 5.0, "e_val": 6.0, "n_val": 0.0},
                },
            ]
            data["performanceResultTables"] = [
                {
                    "unitId": "u1", "resultTableId": "rt1",
                    "resultSets": [
                        {
                            "id": "rs1",
                            "primaryRanking": [
                                {
                                    "entityId": "ind1", "rank": 1, "value": 12.0,
                                    "sourceItems": [{"itemId": "s1", "itemType": "score"}],
                                },
                                {
                                    "entityId": "ind2", "rank": 2, "value": 11.0,
                                    "sourceItems": [{"itemId": "s2", "itemType": "score"}],
                                },
                            ],
                        },
                    ],
                },
            ]

            resp = _ingest_event(data, None)
            assert any(
                w["type"] == "same_name_multiple_ids" and w["gnz_ids"] == ["249317", "716561"]
                for w in resp.warnings
            )

            sess = TestSession()
            rows = sess.query(LongScore).filter(LongScore.event_id == resp.id).all()
            ids = {r.gnz_id for r in rows}
            assert ids == {"249317", "716561"}  # distinct people kept separate
            sess.close()
        finally:
            _teardown_db(db_path, old_engine, old_session)
