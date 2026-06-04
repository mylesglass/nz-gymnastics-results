from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

SQLITE_PATH = "data/results.db"
engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine, class_=Session)


def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()