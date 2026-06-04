import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(DATA_DIR, exist_ok=True)

SQLITE_PATH = str(DATA_DIR / "results.db")
engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, class_=Session)


def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()