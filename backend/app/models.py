from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        Index("idx_events_year", "year"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    discipline = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    is_national = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    scores = relationship("LongScore", back_populates="event", cascade="all, delete-orphan")


class LongScore(Base):
    __tablename__ = "long_scores"

    __table_args__ = (
        Index("idx_long_scores_event_id", "event_id"),
        Index("idx_long_scores_gnz_id", "gnz_id"),
        Index("idx_long_scores_gymnast_name", "gymnast_name"),
        Index("idx_long_scores_club_name", "club_name"),
        Index("idx_long_scores_event_gymnast", "event_id", "gymnast_name"),
        Index("idx_long_scores_rankings", "discipline", "level_category", "pass_final_score"),
    )

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
    bonus = Column(Float, nullable=True)
    start_value = Column(Float, nullable=True)
    apparatus_rank = Column(Integer, nullable=True)
    aa_score = Column(Float, nullable=True)
    aa_rank = Column(Integer, nullable=True)
    round_type = Column(String, nullable=True)
    date_created = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    event = relationship("Event", back_populates="scores")