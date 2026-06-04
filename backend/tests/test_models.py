import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Event, LongScore


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, class_=Session)
    session = TestSession()
    yield session
    session.close()


class TestEvent:
    def test_create_event(self, db_session: Session):
        event = Event(name="Test Competition", start_date="2025-01-01", end_date="2025-01-02", discipline="WAG")
        db_session.add(event)
        db_session.commit()

        saved = db_session.query(Event).first()
        assert saved.name == "Test Competition"
        assert saved.start_date == "2025-01-01"
        assert saved.end_date == "2025-01-02"
        assert saved.discipline == "WAG"
        assert saved.id is not None

    def test_delete_cascades_scores(self, db_session: Session):
        event = Event(name="Test", start_date="2025-01-01", end_date="2025-01-01", discipline="WAG")
        db_session.add(event)
        db_session.flush()

        score = LongScore(
            event_id=event.id,
            event_name="Test",
            gymnast_name="Alice",
            discipline="WAG",
            apparatus="VT",
            pass_final_score=13.5,
        )
        db_session.add(score)
        db_session.commit()

        assert db_session.query(LongScore).count() == 1

        db_session.delete(event)
        db_session.commit()

        assert db_session.query(LongScore).count() == 0
        assert db_session.query(Event).count() == 0


class TestLongScore:
    def test_create_long_score(self, db_session: Session):
        event = Event(name="Comp", start_date="2025-01-01", end_date="2025-01-01", discipline="WAG")
        db_session.add(event)
        db_session.flush()

        score = LongScore(
            event_id=event.id,
            event_name="Comp",
            gymnast_name="Alice",
            gnz_id="GNZ001",
            club_name="CSG",
            discipline="WAG",
            level_category="STEP 5",
            division="OPEN",
            apparatus="VT",
            pass_number=1,
            d_score=5.0,
            e_score=8.5,
            neutral_deductions=0.0,
            pass_final_score=13.5,
            apparatus_rank=2,
            aa_score=52.0,
            aa_rank=3,
            round_type="AA",
        )
        db_session.add(score)
        db_session.commit()

        saved = db_session.query(LongScore).first()
        assert saved.gymnast_name == "Alice"
        assert saved.gnz_id == "GNZ001"
        assert saved.apparatus == "VT"
        assert saved.pass_final_score == 13.5
        assert saved.d_score == 5.0
        assert saved.e_score == 8.5

    def test_long_score_belongs_to_event(self, db_session: Session):
        event = Event(name="Comp", start_date="2025-01-01", end_date="2025-01-01", discipline="WAG")
        db_session.add(event)
        db_session.flush()

        score = LongScore(
            event_id=event.id,
            event_name="Comp",
            gymnast_name="Bob",
            discipline="MAG",
            apparatus="FX",
        )
        db_session.add(score)
        db_session.commit()

        assert score.event.name == "Comp"
        assert len(event.scores) == 1
        assert event.scores[0].gymnast_name == "Bob"