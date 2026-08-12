from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship

ACTIVITY_TYPE_API = "api"
ACTIVITY_TYPE_PAGE = "page"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    permissions = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Athlete(Base):
    __tablename__ = "athletes"

    __table_args__ = (
        Index("idx_athletes_slug", "slug", unique=True),
        Index("idx_athletes_gnz_id", "gnz_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, nullable=False)
    signature_hash = Column(String, nullable=False, unique=True)
    canonical_name = Column(String, nullable=False)
    gnz_id = Column(String, nullable=True)
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
    host_club = Column(String, nullable=True)
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
        Index("idx_long_scores_athlete_id", "athlete_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    identity_override = Column(String, nullable=True)

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


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    __table_args__ = (
        Index("idx_activity_logs_created_at", "created_at"),
        Index("idx_activity_logs_username", "username"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    type = Column(String, nullable=False)
    method = Column(String, nullable=True)
    path = Column(String, nullable=False)
    query = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class WellingtonIntent(Base):
    __tablename__ = "wellington_intents"

    __table_args__ = (
        UniqueConstraint("athlete_id", "year", name="uix_athlete_year"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    gnz_id = Column(String, nullable=True)
    athlete_id = Column(Integer, nullable=True)
    year = Column(Integer, nullable=False)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))