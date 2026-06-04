from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    discipline = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    scores = relationship("LongScore", back_populates="event", cascade="all, delete-orphan")


class LongScore(Base):
    __tablename__ = "long_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    event_name = Column(String, nullable=False)
    gymnast_name = Column(String, nullable=False)
    gnz_id = Column(String, nullable=True)
    club_name = Column(String, nullable=True)
    discipline = Column(String, nullable=False)
    level_category = Column(String, nullable=True)
    division = Column(String, nullable=True)
    apparatus = Column(String, nullable=False)
    pass_number = Column(Integer, default=1)
    d_score = Column(Float, nullable=True)
    e_score = Column(Float, nullable=True)
    neutral_deductions = Column(Float, nullable=True)
    pass_final_score = Column(Float, nullable=True)
    apparatus_rank = Column(Integer, nullable=True)
    aa_score = Column(Float, nullable=True)
    aa_rank = Column(Integer, nullable=True)
    round_type = Column(String, nullable=True)
    date_created = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    event = relationship("Event", back_populates="scores")