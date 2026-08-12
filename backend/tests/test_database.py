"""Tests for the database init/migration path."""

import os
import sqlite3
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db


def _build_old_schema(path: str) -> None:
    """Create the pre-identity migration schema and seed one row per table."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            start_date VARCHAR NOT NULL,
            end_date VARCHAR NOT NULL,
            discipline VARCHAR NOT NULL,
            year INTEGER,
            created_at DATETIME
        );
        CREATE TABLE long_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            event_name VARCHAR NOT NULL,
            gymnast_name VARCHAR NOT NULL,
            gnz_id VARCHAR,
            club_name VARCHAR,
            discipline VARCHAR NOT NULL,
            level_category VARCHAR,
            division VARCHAR,
            apparatus VARCHAR NOT NULL,
            pass_number INTEGER DEFAULT 1,
            d_score FLOAT,
            e_score FLOAT,
            neutral_deductions FLOAT,
            pass_final_score FLOAT,
            bonus FLOAT,
            start_value FLOAT,
            apparatus_rank INTEGER,
            aa_score FLOAT,
            aa_rank INTEGER,
            round_type VARCHAR,
            date_created DATETIME
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR NOT NULL,
            hashed_password VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            created_at DATETIME
        );
        CREATE TABLE wellington_intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gnz_id VARCHAR,
            year INTEGER NOT NULL,
            submitted_at DATETIME
        );
        INSERT INTO events (id, name, start_date, end_date, discipline, year)
            VALUES (1, 'Old Meet', '2026-03-01', '2026-03-02', 'WAG', 2026);
        INSERT INTO long_scores (
            id, event_id, event_name, gymnast_name, gnz_id, club_name,
            discipline, level_category, apparatus, pass_number, pass_final_score, round_type
        ) VALUES (1, 1, 'Old Meet', 'Eva McEwan', '999', 'OMNI',
                  'WAG', 'STEP 5', 'VT', 1, 10.5, 'All Around');
        INSERT INTO users (id, username, hashed_password, role)
            VALUES (1, 'admin', 'hash', 'admin');
        INSERT INTO wellington_intents (id, gnz_id, year)
            VALUES (1, '999', 2026);
    """)
    conn.commit()
    conn.close()


class TestInitDbMigration:
    def test_migrates_existing_schema_and_preserves_rows(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()
        _build_old_schema(db_path)

        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        TestSession = sessionmaker(bind=engine, class_=Session)

        import app.database as db_mod

        old_engine = db_mod.engine
        old_session = db_mod.SessionLocal
        db_mod.engine = engine
        db_mod.SessionLocal = TestSession
        try:
            init_db()

            with engine.connect() as conn:
                long_score_cols = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(long_scores)")).fetchall()
                }
                assert "athlete_id" in long_score_cols
                assert "identity_override" in long_score_cols

                event_cols = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(events)")).fetchall()
                }
                assert "is_national" in event_cols
                assert "host_club" in event_cols

                user_cols = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
                }
                assert "permissions" in user_cols

                intent_cols = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(wellington_intents)")).fetchall()
                }
                assert "athlete_id" in intent_cols

            # Seeded data survived, and the identity rebuild assigned athlete_id.
            sess = TestSession()
            try:
                row = sess.execute(text(
                    "SELECT gymnast_name, gnz_id, athlete_id FROM long_scores WHERE id = 1"
                )).first()
                assert row is not None
                assert row.gymnast_name == "Eva McEwan"
                assert row.gnz_id == "999"
                assert row.athlete_id is not None

                intent = sess.execute(text(
                    "SELECT athlete_id FROM wellington_intents WHERE id = 1"
                )).first()
                assert intent is not None
                assert intent.athlete_id == row.athlete_id

                athlete_count = sess.execute(text("SELECT count(*) FROM athletes")).scalar()
                assert athlete_count == 1

                event = sess.execute(text(
                    "SELECT name, host_club FROM events WHERE id = 1"
                )).first()
                assert event is not None
                assert event.name == "Old Meet"
            finally:
                sess.close()
        finally:
            db_mod.engine = old_engine
            db_mod.SessionLocal = old_session
            os.unlink(db_path)
