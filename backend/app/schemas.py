from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "member"


class UserUpdate(BaseModel):
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


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
    is_region: bool = False


class GymnastItem(BaseModel):
    gnz_id: str
    name: str
    club: str | None


class UploadValidationResponse(BaseModel):
    message: str
    unknown_clubs: list[str]
    known_clubs: list[str]


class ConflictItem(BaseModel):
    name: str
    previous_ids: list[str]
    chosen_id: str | None
    rows_updated: int


class ReconcileReport(BaseModel):
    total_athletes: int
    ids_corrected: int
    names_unified: int
    conflicts: list[ConflictItem]