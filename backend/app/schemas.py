from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    discipline: str
    year: int | None = None
    gymnast_count: int
    score_count: int
    club_count: int
    created_at: datetime | None = None


class EventListItem(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    discipline: str
    year: int | None = None
    gymnast_count: int


class ResultsResponse(BaseModel):
    event: EventListItem
    columns: list[str]
    rows: list[dict]


class EventUpdate(BaseModel):
    name: str


class StatsResponse(BaseModel):
    total_events: int
    total_gymnasts: int
    total_scores: int
    total_clubs: int


class ClubItem(BaseModel):
    name: str
    gymnast_count: int
    region: str | None


class GymnastItem(BaseModel):
    gnz_id: str
    name: str
    club: str | None