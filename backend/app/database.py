from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.clubdata import DATA_DIR, ensure_seed as ensure_club_data_seed
from app.models import Base

SQLITE_PATH = str(DATA_DIR / "results.db")
engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, class_=Session)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=30000;")
    cursor.execute("PRAGMA cache_size=-64000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA temp_store=MEMORY;")
    cursor.close()


_INDEX_DEFINITIONS = [
    ("idx_long_scores_event_id", "CREATE INDEX IF NOT EXISTS idx_long_scores_event_id ON long_scores(event_id)"),
    ("idx_long_scores_gnz_id", "CREATE INDEX IF NOT EXISTS idx_long_scores_gnz_id ON long_scores(gnz_id)"),
    ("idx_long_scores_gymnast_name", "CREATE INDEX IF NOT EXISTS idx_long_scores_gymnast_name ON long_scores(gymnast_name)"),
    ("idx_long_scores_club_name", "CREATE INDEX IF NOT EXISTS idx_long_scores_club_name ON long_scores(club_name)"),
    ("idx_long_scores_event_gymnast", "CREATE INDEX IF NOT EXISTS idx_long_scores_event_gymnast ON long_scores(event_id, gymnast_name)"),
    ("idx_long_scores_rankings", "CREATE INDEX IF NOT EXISTS idx_long_scores_rankings ON long_scores(discipline, level_category, pass_final_score)"),
    ("idx_long_scores_athlete_id", "CREATE INDEX IF NOT EXISTS idx_long_scores_athlete_id ON long_scores(athlete_id)"),
    ("idx_events_year", "CREATE INDEX IF NOT EXISTS idx_events_year ON events(year)"),
    ("idx_athletes_slug", "CREATE UNIQUE INDEX IF NOT EXISTS idx_athletes_slug ON athletes(slug)"),
    ("idx_athletes_gnz_id", "CREATE INDEX IF NOT EXISTS idx_athletes_gnz_id ON athletes(gnz_id)"),
]


def _ensure_indexes(conn):
    for table in ("long_scores", "events", "athletes"):
        existing = {
            row[1]
            for row in conn.execute(text(f"PRAGMA index_list('{table}')")).fetchall()
        }
        for name, sql in _INDEX_DEFINITIONS:
            if name.startswith(f"idx_{table}") and name not in existing:
                conn.execute(text(sql))


def init_db():
    Base.metadata.create_all(engine)
    # Ensure the persistent club-data copy exists (seeded from the image).
    ensure_club_data_seed()
    with engine.connect() as conn:
        existing_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(events)")).fetchall()
        }
        if "is_national" not in existing_cols:
            conn.execute(
                text("ALTER TABLE events ADD COLUMN is_national BOOLEAN DEFAULT 0")
            )
        if "host_club" not in existing_cols:
            conn.execute(
                text("ALTER TABLE events ADD COLUMN host_club VARCHAR")
            )
        if "host_province" in existing_cols:
            try:
                conn.execute(
                    text("ALTER TABLE events DROP COLUMN host_province")
                )
            except Exception:
                # Older SQLite without DROP COLUMN — leave the empty column in place
                pass
        score_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(long_scores)")).fetchall()
        }
        if "athlete_id" not in score_cols:
            conn.execute(
                text("ALTER TABLE long_scores ADD COLUMN athlete_id INTEGER REFERENCES athletes(id)")
            )
        _ensure_indexes(conn)
        conn.commit()

    # Seed athlete identities BEFORE the intents migration so existing
    # wellington_intents rows can map their gnz_id to an athlete_id.
    from app.athlete_identity import rebuild_athletes
    seed_session = SessionLocal()
    try:
        rebuild_athletes(seed_session)
    finally:
        seed_session.close()

    with engine.connect() as conn:
        # wellington_intents: re-key from gnz_id to athlete_id (SQLite can't alter
        # a unique constraint, so rebuild the table; existing rows are mapped to
        # the athlete whose canonical gnz_id matches).
        wintent_tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='wellington_intents'")).fetchall()
        }
        if wintent_tables:
            wintent_cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(wellington_intents)")).fetchall()
            }
            if "athlete_id" not in wintent_cols:
                conn.execute(text("DROP TABLE IF EXISTS wellington_intents_new"))
                conn.execute(text("""
                    CREATE TABLE wellington_intents_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        gnz_id VARCHAR,
                        athlete_id INTEGER,
                        year INTEGER NOT NULL,
                        submitted_at DATETIME,
                        CONSTRAINT uix_athlete_year UNIQUE (athlete_id, year)
                    )
                """))
                conn.execute(text("""
                    INSERT INTO wellington_intents_new (id, gnz_id, athlete_id, year, submitted_at)
                    SELECT w.id, w.gnz_id, a.athlete_id, w.year, w.submitted_at
                    FROM wellington_intents w
                    LEFT JOIN (
                        SELECT gnz_id, MIN(id) AS athlete_id FROM athletes GROUP BY gnz_id
                    ) a ON a.gnz_id = w.gnz_id
                """))
                conn.execute(text("DROP TABLE wellington_intents"))
                conn.execute(text("ALTER TABLE wellington_intents_new RENAME TO wellington_intents"))
        user_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        if "permissions" not in user_cols:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN permissions VARCHAR DEFAULT ''")
            )
        _ensure_indexes(conn)
        conn.commit()
        # Flush any large WAL accumulated since the last start so reads don't
        # stall on WAL pages; passive never blocks active readers/writers. This
        # must run outside an open transaction, so the migrations above are
        # committed first — and it is best-effort (a busy lock must not stop
        # startup).
        try:
            conn.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
        except Exception:
            pass
        conn.commit()


def get_session() -> Session:
    return SessionLocal()