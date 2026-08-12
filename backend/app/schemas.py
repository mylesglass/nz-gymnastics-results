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
    permissions: list[str] = []


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "member"
    permissions: list[str] = []


class UserUpdate(BaseModel):
    password: str


class UserPermissionsUpdate(BaseModel):
    permissions: list[str]


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    permissions: list[str] = []
    created_at: datetime


class ConflictItem(BaseModel):
    name: str
    previous_ids: list[str]
    chosen_id: str | None
    rows_updated: int
    reason: str | None = None


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
    host_club: str | None = None
    warnings: list[dict] = []


class EventListItem(BaseModel):
    id: int
    name: str
    start_date: str
    end_date: str
    discipline: str
    year: int | None = None
    gymnast_count: int
    is_national: bool = False
    host_club: str | None = None


class ResultsResponse(BaseModel):
    event: EventListItem
    columns: list[str]
    rows: list[dict]


class EventUpdate(BaseModel):
    name: str | None = None
    is_national: bool | None = None
    host_club: str | None = None


class StatsResponse(BaseModel):
    total_events: int
    total_gymnasts: int
    total_scores: int
    total_clubs: int


class MedalCounts(BaseModel):
    g: int = 0
    s: int = 0
    b: int = 0
    total: int = 0


class GymnastMedals(BaseModel):
    gnz_id: str
    name: str
    club: str | None = None
    medals: MedalCounts = MedalCounts()


class ClubMedals(BaseModel):
    name: str
    medals: MedalCounts = MedalCounts()


class MedalsResponse(BaseModel):
    year: int | None = None
    gymnasts: list[GymnastMedals]
    clubs: list[ClubMedals]


class ClubItem(BaseModel):
    name: str
    gymnast_count: int
    region: str | None
    is_region: bool = False


class KnownClubItem(BaseModel):
    name: str
    region: str


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


class ImportUrlRequest(BaseModel):
    url: str
    allow_unknown: bool = False
    host_club: str | None = None


class ConflictItem(BaseModel):
    name: str
    previous_ids: list[str]
    chosen_id: str | None
    rows_updated: int
    reason: str | None = None


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
    reached_mark: bool = False


class RankingsResponse(BaseModel):
    year: int
    step: str
    discipline: str
    rankings: list[RankingRow]
    apparatus_specialists: list["ApparatusSpecialistRow"] = []
    apparatus_qualifying_score: float | None = None
    apparatus_qualifying_count: int = 2


class StepsResponse(BaseModel):
    steps: list[str]


class ApparatusRankingRow(BaseModel):
    rank: str
    name: str
    gnz_id: str
    club: str | None
    region: str = ""
    best: float
    d: float | None = None
    event: str = ""
    count: int = 0


class ApparatusLeaderboard(BaseModel):
    app: str
    rankings: list[ApparatusRankingRow]


class ApparatusRankingsResponse(BaseModel):
    year: int
    step: str
    discipline: str
    apparatus: list[ApparatusLeaderboard]


class ApparatusRow(BaseModel):
    app: str
    pass_number: int
    d: float | None = None
    e: float | None = None
    n: float | None = None
    total: float | None = None
    bonus: float | None = None
    rank: int | None = None
    start_value: float | None = None


class WellingtonRankingRow(BaseModel):
    rank: str
    name: str
    gnz_id: str
    club: str | None
    region: str = ""
    scores: list[float]
    competitions: list[str]
    categories: list[str]
    apparatus: list[list[ApparatusRow]] = []
    total: float
    average: float
    warnings: list[str] = []
    intent_submitted: bool = True


class CheckItem(BaseModel):
    label: str
    met: bool
    detail: str = ""


class WellingtonNotRankedRow(BaseModel):
    name: str
    gnz_id: str
    club: str | None
    region: str = ""
    scores: list[float | None]
    competition_names: list[str]
    categories: list[str]
    apparatus: list[list[ApparatusRow]] = []
    competitions: int
    regional_count: int = 0
    club_count: int = 0
    away_count: int = 0
    why: str = ""
    checks: list[CheckItem] = []
    intent_submitted: bool = True


class WellingtonRankingResponse(BaseModel):
    year: int
    step: str
    discipline: str
    rankings: list[WellingtonRankingRow]
    not_ranked: list[WellingtonNotRankedRow] = []
    config_key: str = ""
    qualifying_score: float | None = None
    wellington_qualifying_score: float | None = None
    apparatus_specialists: list["ApparatusSpecialistRow"] = []
    apparatus_qualifying_score: float | None = None
    apparatus_qualifying_count: int = 2


class ApparatusQualifyingApp(BaseModel):
    app: str
    best: float
    event: str = ""
    count: int = 0
    competitions: list[str] = []


class ApparatusSpecialistRow(BaseModel):
    name: str
    gnz_id: str
    club: str | None
    region: str = ""
    apparatus: list[ApparatusQualifyingApp] = []
    count: int = 0
    qualified: bool = True


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


class IntentToggle(BaseModel):
    gnz_id: str
    year: int
    submitted: bool


class GymnastEditRequest(BaseModel):
    event_id: int
    current_name: str
    new_name: str | None = None
    new_gnz_id: str | None = None
    new_club: str | None = None


class GymnastEditResponse(BaseModel):
    updated: int


class TrackPageRequest(BaseModel):
    path: str


class ActivityLogItem(BaseModel):
    id: int
    username: str
    role: str
    type: str
    method: str | None = None
    path: str
    query: str | None = None
    status_code: int | None = None
    duration_ms: float | None = None
    created_at: datetime


class ActivityLogResponse(BaseModel):
    items: list[ActivityLogItem]
    total: int
