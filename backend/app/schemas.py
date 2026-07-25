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


class ConflictItem(BaseModel):
    name: str
    previous_ids: list[str]
    chosen_id: str | None
    rows_updated: int


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
    ids_corrected: int = 0
    names_unified: int = 0
    conflicts: list[ConflictItem] = []


class EventListItem(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    discipline: str
    year: int | None = None
    gymnast_count: int
    is_national: bool = False


class ResultsResponse(BaseModel):
    event: EventListItem
    columns: list[str]
    rows: list[dict]


class EventUpdate(BaseModel):
    name: str | None = None
    is_national: bool | None = None


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
    alt_ids: list[str] = []
    alt_clubs: list[str] = []


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


class RankingRow(BaseModel):
    rank: str
    name: str
    gnz_id: str
    club: str | None
    region: str = ""
    scores: list[float]
    competitions: list[str]
    total: float


class RankingsResponse(BaseModel):
    year: int
    step: str
    discipline: str
    rankings: list[RankingRow]


class StepsResponse(BaseModel):
    steps: list[str]


class DuplicateInstance(BaseModel):
    club: str
    level_category: str
    id_counts: dict[str, int]
    total_rows: int


class DuplicateGroup(BaseModel):
    name: str
    instances: list[DuplicateInstance]
    total_rows: int


class FixDuplicatesResponse(BaseModel):
    fixed: int = 0
    low_confidence: list[DuplicateGroup] = []


class ApplyFixItem(BaseModel):
    name: str
    club: str
    level_category: str
    chosen_id: str


class SuggestedMerge(BaseModel):
    name_a: str
    name_b: str
    score: float
    gnz_ids_a: list[str]
    gnz_ids_b: list[str]
    rows_a: int = 0
    rows_b: int = 0


class MergeNamesRequest(BaseModel):
    from_name: str
    to_name: str