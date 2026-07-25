import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(DATA_DIR, exist_ok=True)

SQLITE_PATH = str(DATA_DIR / "results.db")
engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, class_=Session)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
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
    ("idx_events_year", "CREATE INDEX IF NOT EXISTS idx_events_year ON events(year)"),
]


def _ensure_indexes(conn):
    for table in ("long_scores", "events"):
        existing = {
            row[1]
            for row in conn.execute(text(f"PRAGMA index_list('{table}')")).fetchall()
        }
        for name, sql in _INDEX_DEFINITIONS:
            if name.startswith(f"idx_{table}") and name not in existing:
                conn.execute(text(sql))


def init_db():
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        existing_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(events)")).fetchall()
        }
        if "is_national" not in existing_cols:
            conn.execute(
                text("ALTER TABLE events ADD COLUMN is_national BOOLEAN DEFAULT 0")
            )
        _ensure_indexes(conn)
        conn.commit()


def get_session() -> Session:
    return SessionLocal()