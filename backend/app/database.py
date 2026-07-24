import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(DATA_DIR, exist_ok=True)

SQLITE_PATH = str(DATA_DIR / "results.db")
engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, class_=Session)


def init_db():
    Base.metadata.create_all(engine)
    # Migrate existing tables — add columns that may not exist yet
    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(events)")).fetchall()
        }
        if "is_national" not in existing:
            conn.execute(
                text("ALTER TABLE events ADD COLUMN is_national BOOLEAN DEFAULT 0")
            )
        conn.commit()


def get_session() -> Session:
    return SessionLocal()