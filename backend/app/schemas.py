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
    slug: str = ""
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
    slug: str = ""
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
    slug: str = ""
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
    slug: str = ""
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
    slug: str = ""
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
    slug: str = ""
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
    slug: str = ""
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
    gnz_id: str | None = None
    athlete_id: int | None = None
    slug: str | None = None
    year: int
    submitted: bool


class GymnastEditRequest(BaseModel):
    event_id: int
    current_name: str
    slug: str | None = None
    new_name: str | None = None
    new_gnz_id: str | None = None
    new_club: str | None = None
    new_division: str | None = None
    new_round_type: str | None = None
    current_division: str | None = None
    current_round_type: str | None = None


class GymnastEditResponse(BaseModel):
    updated: int


class AthleteReviewInfo(BaseModel):
    athlete_id: int
    slug: str
    name: str
    gnz_id: str | None = None
    clubs: list[str] = []
    events: int = 0
    event_ids: list[int] = []
    years: list[int] = []
    disciplines: list[str] = []
    rows: int = 0
    intent_years: list[int] = []


class SimilarAthletes(BaseModel):
    name_a: str
    name_b: str
    score: float
    athlete_a: AthleteReviewInfo
    athlete_b: AthleteReviewInfo


class NameConflict(BaseModel):
    name: str
    athletes: list[AthleteReviewInfo]


class IdConflict(BaseModel):
    gnz_id: str
    athletes: list[AthleteReviewInfo]


class MultiIdAthlete(BaseModel):
    athlete_id: int
    slug: str
    name: str
    gnz_ids: dict[str, int]
    clubs: list[str] = []
    events: int = 0
    event_ids: list[int] = []
    years: list[int] = []
    disciplines: list[str] = []
    rows: int = 0


class IdentityReviewResponse(BaseModel):
    similar_names: list[SimilarAthletes] = []
    name_conflicts: list[NameConflict] = []
    id_conflicts: list[IdConflict] = []
    multi_id_athletes: list[MultiIdAthlete] = []


class MergeAthletesRequest(BaseModel):
    athlete_id: int
    merge_id: int


class MergePreviewRequest(BaseModel):
    athlete_id: int
    merge_ids: list[int]


class MergeChangeRow(BaseModel):
    event_id: int
    event_name: str
    rows: int
    old_name: str
    old_gnz_id: str
    new_name: str
    new_gnz_id: str


class MergePairPreview(BaseModel):
    survivor: AthleteReviewInfo
    merged: AthleteReviewInfo
    target_name: str
    target_gnz_id: str
    changes: list[MergeChangeRow]
    intent_moves: list[int]
    survivor_slug: str
    merged_slug: str


class MergePreviewResponse(BaseModel):
    pairs: list[MergePairPreview]


class SplitAthleteRequest(BaseModel):
    athlete_id: int
    split_by: str
    value: str
    new_gnz_id: str | None = None


class MergeAthletesResponse(BaseModel):
    merged_rows: int
    survivor_id: int
    survivor_slug: str


class SplitAthleteResponse(BaseModel):
    split_rows: int
    original_id: int
    original_slug: str
    created_id: int
    created_slug: str


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


class TrafficPoint(BaseModel):
    date: str
    page_views: int = 0
    api_requests: int = 0
    errors: int = 0


class HourPoint(BaseModel):
    hour: int
    page_views: int = 0
    api_requests: int = 0


class TopPath(BaseModel):
    path: str
    count: int = 0
    errors: int = 0


class TopUser(BaseModel):
    username: str
    role: str
    page_views: int = 0
    api_requests: int = 0


class ActivityTotals(BaseModel):
    page_views: int
    api_requests: int
    errors: int
    avg_duration_ms: float | None
    active_days: int
    anon_page_views: int
    auth_page_views: int
    anon_api_requests: int
    auth_api_requests: int


class ActivitySummaryResponse(BaseModel):
    range_days: int
    totals: ActivityTotals
    daily_series: list[TrafficPoint]
    auth_daily_series: list[TrafficPoint]
    hourly_series: list[HourPoint]
    top_pages: list[TopPath]
    top_api: list[TopPath]
    top_users: list[TopUser]


class CloudflareDay(BaseModel):
    date: str
    requests: int = 0
    bytes: int = 0
    threats: int = 0
    cached_requests: int = 0
    unique_visitors: int = 0


class CloudflareTopCountry(BaseModel):
    country: str
    requests: int = 0


class CloudflareStatusCode(BaseModel):
    code: int | None
    requests: int = 0


class CloudflareNamedCount(BaseModel):
    name: str
    count: int = 0


class CloudflareHourPoint(BaseModel):
    hour: int
    requests: int = 0


class CloudflareTotals(BaseModel):
    requests: int
    bytes: int
    unique_visitors: int
    threats: int
    cache_hit_ratio: float | None


class CloudflareSummaryResponse(BaseModel):
    configured: bool
    days: int
    error: str | None = None
    totals: CloudflareTotals | None = None
    daily: list[CloudflareDay] = []
    top_countries: list[CloudflareTopCountry] = []
    status_codes: list[CloudflareStatusCode] = []
    top_paths: list[CloudflareNamedCount] = []
    cache_status: list[CloudflareNamedCount] = []
    device_type: list[CloudflareNamedCount] = []
    hourly: list[CloudflareHourPoint] = []
