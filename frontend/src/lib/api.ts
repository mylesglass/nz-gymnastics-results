import { getToken } from "./auth";

const API_BASE = "";

function authHeaders(): Record<string, string> {
  const t = getToken();
  if (t) return { Authorization: `Bearer ${t}` };
  return {};
}

export interface EventSummary {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  year: number | null;
  gymnast_count: number;
  score_count: number;
  club_count?: number;
  is_national?: boolean;
  host_club?: string | null;
  ids_corrected?: number;
  names_unified?: number;
  conflicts?: Array<{ name: string; previous_ids: string[]; chosen_id: string | null; rows_updated: number }>;
  warnings?: Array<{ type: string; name?: string; gnz_id?: string; gnz_ids?: string[]; names?: string[] }>;
}

export interface WideResponse {
  event: { id: number; name: string; discipline: string };
  wag: { columns: string[]; rows: Record<string, unknown>[] };
  mag: { columns: string[]; rows: Record<string, unknown>[] };
}

export interface CurrentUserInfo {
  username: string;
  role: string;
  permissions: string[];
}

export async function checkAuthStatus(): Promise<{ configured: boolean }> {
  const res = await fetch(`${API_BASE}/api/auth/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function authLogin(username: string, password: string): Promise<{
  access_token: string;
  role: string;
  permissions: string[];
}> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function me(): Promise<CurrentUserInfo> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = new Error(await res.text()) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function updateUserPermissions(
  userId: number,
  permissions: string[]
): Promise<{ ok: boolean; permissions: string[] }> {
  const res = await fetch(`${API_BASE}/api/auth/users/${userId}/permissions`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ permissions }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadFile(file: File, allowUnknown = false, hostClub?: string): Promise<EventSummary> {
  const form = new FormData();
  form.append("file", file);
  let url = `${API_BASE}/api/upload`;
  if (allowUnknown) url += "?allow_unknown=1";
  if (hostClub) url += `${allowUnknown ? "&" : "?"}host_club=${encodeURIComponent(hostClub)}`;
  const res = await fetch(url, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  await throwIfUploadError(res);
  return res.json();
}

export async function importFromUrl(url: string, allowUnknown = false, hostClub?: string): Promise<EventSummary> {
  const res = await fetch(`${API_BASE}/api/import-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ url, allow_unknown: allowUnknown, host_club: hostClub || null }),
  });
  await throwIfUploadError(res);
  return res.json();
}

async function throwIfUploadError(res: Response): Promise<void> {
  if (res.status === 409) {
    const body = await res.json();
    const detail = body.detail || body;
    const err = new Error(detail.message || "Unknown clubs") as Error & Record<string, unknown>;
    err._clubConflict = true;
    err.unknown_clubs = detail.unknown_clubs;
    err.known_clubs = detail.known_clubs;
    err.suggestions = detail.suggestions || {};
    throw err;
  }
  if (!res.ok) throw new Error(await res.text());
}

export async function saveAliases(aliases: Record<string, string>): Promise<void> {
  const res = await fetch(`${API_BASE}/api/clubs/aliases`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ aliases }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function listEvents(): Promise<EventSummary[]> {
  const res = await fetch(`${API_BASE}/api/events`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function refreshCache(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/refresh-cache`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getStats(): Promise<{
  total_events: number;
  total_gymnasts: number;
  total_scores: number;
  total_clubs: number;
}> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface MedalCounts {
  g: number;
  s: number;
  b: number;
  total: number;
}

export interface GymnastMedals {
  slug?: string;
  gnz_id: string;
  name: string;
  club: string | null;
  medals: MedalCounts;
}

export interface ClubMedals {
  name: string;
  medals: MedalCounts;
}

export interface MedalsResponse {
  year: number | null;
  gymnasts: GymnastMedals[];
  clubs: ClubMedals[];
}

export async function getMedals(params?: {
  year?: number;
  gnz_id?: string;
  athlete_id?: number;
  slug?: string;
  club?: string;
}): Promise<MedalsResponse> {
  const qp = new URLSearchParams();
  if (params?.year !== undefined) qp.set("year", String(params.year));
  if (params?.gnz_id) qp.set("gnz_id", params.gnz_id);
  if (params?.athlete_id !== undefined) qp.set("athlete_id", String(params.athlete_id));
  if (params?.slug) qp.set("slug", params.slug);
  if (params?.club) qp.set("club", params.club);
  const qs = qp.toString();
  const res = await fetch(`${API_BASE}/api/medals${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getWideResults(eventId: number): Promise<WideResponse> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}/results/wide`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAllWideResults(params?: {
  gnz_id?: string;
  athlete_id?: number;
  slug?: string;
  club?: string;
  year?: number;
}): Promise<{
  name?: string;
  wag?: { columns: string[]; rows: Record<string, unknown>[] };
  mag?: { columns: string[]; rows: Record<string, unknown>[] };
}> {
  let url = `${API_BASE}/api/results/wide-all`;
  const qp = new URLSearchParams();
  if (params?.gnz_id) qp.set("gnz_id", params.gnz_id);
  if (params?.athlete_id !== undefined) qp.set("athlete_id", String(params.athlete_id));
  if (params?.slug) qp.set("slug", params.slug);
  if (params?.club) qp.set("club", params.club);
  if (params?.year) qp.set("year", String(params.year));
  const qs = qp.toString();
  if (qs) url += `?${qs}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteEvent(eventId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function renameEvent(
  eventId: number,
  name: string
): Promise<EventSummary> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateEvent(
  eventId: number,
  data: { name?: string; is_national?: boolean; host_club?: string | null }
): Promise<EventSummary> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listClubs(): Promise<
  { name: string; gymnast_count: number; region: string | null; is_region: boolean }[]
> {
  const res = await fetch(`${API_BASE}/api/clubs`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface KnownClub {
  name: string;
  region: string;
}

export async function listKnownClubs(): Promise<KnownClub[]> {
  const res = await fetch(`${API_BASE}/api/clubs/known`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listYears(): Promise<{ years: number[] }> {
  const res = await fetch(`${API_BASE}/api/years`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listGymnasts(params?: { year?: number }): Promise<
  { slug?: string; gnz_id: string; name: string; club: string | null }[]
> {
  const qp = new URLSearchParams();
  if (params?.year !== undefined) qp.set("year", String(params.year));
  const qs = qp.toString();
  const res = await fetch(`${API_BASE}/api/gymnasts${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface RankingRow {
  rank: string;
  name: string;
  slug?: string;
  gnz_id: string;
  club: string | null;
  region: string;
  scores: number[];
  competitions: string[];
  total: number;
  reached_mark?: boolean;
}

export interface RankingsResponse {
  year: number;
  step: string;
  discipline: string;
  rankings: RankingRow[];
  apparatus_specialists?: ApparatusSpecialistRow[];
  apparatus_qualifying_score?: number | null;
  apparatus_qualifying_count?: number;
}

export async function getRankings(
  year: number,
  step: string,
  discipline: string,
  quota?: boolean,
  qualifier?: boolean,
  division?: string
): Promise<RankingsResponse> {
  const params = new URLSearchParams({ year: String(year), step, discipline });
  if (quota) params.set("quota", "true");
  if (qualifier) params.set("qualifier", "true");
  if (division) params.set("division", division);
  const res = await fetch(`${API_BASE}/api/rankings?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface ApparatusRankingRow {
  rank: string;
  name: string;
  slug?: string;
  gnz_id: string;
  club: string | null;
  region: string;
  best: number;
  d: number | null;
  event: string;
  count: number;
}

export interface ApparatusLeaderboard {
  app: string;
  rankings: ApparatusRankingRow[];
}

export interface ApparatusRankingsResponse {
  year: number;
  step: string;
  discipline: string;
  apparatus: ApparatusLeaderboard[];
}

export async function getApparatusRankings(
  year: number,
  step: string,
  discipline: string,
  division?: string
): Promise<ApparatusRankingsResponse> {
  const params = new URLSearchParams({ year: String(year), step, discipline });
  if (division) params.set("division", division);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(`${API_BASE}/api/rankings/apparatus?${params}`, {
      headers: authHeaders(),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

export interface ApparatusPass {
  app: string;
  pass_number: number;
  d: number | null;
  e: number | null;
  n: number | null;
  total: number | null;
  bonus: number | null;
  rank: number | null;
  start_value: number | null;
}

export interface WellingtonRankingRow {
  rank: string;
  name: string;
  slug?: string;
  gnz_id: string;
  club: string | null;
  region: string;
  scores: number[];
  competitions: string[];
  categories: string[];
  apparatus: ApparatusPass[][];
  total: number;
  average: number;
  warnings: string[];
  intent_submitted: boolean;
}

export interface ApparatusQualifyingApp {
  app: string;
  best: number;
  event: string;
  count: number;
  competitions: string[];
}

export interface ApparatusSpecialistRow {
  name: string;
  slug?: string;
  gnz_id: string;
  club: string | null;
  region: string;
  apparatus: ApparatusQualifyingApp[];
  count: number;
  qualified: boolean;
}

export interface CheckItem {
  label: string;
  met: boolean;
  detail: string;
}

export interface WellingtonNotRankedRow {
  name: string;
  slug?: string;
  gnz_id: string;
  club: string | null;
  region: string;
  scores: (number | null)[];
  competition_names: string[];
  categories: string[];
  apparatus: ApparatusPass[][];
  competitions: number;
  regional_count: number;
  club_count: number;
  away_count: number;
  why: string;
  checks: CheckItem[];
  intent_submitted: boolean;
}

export interface WellingtonRankingResponse {
  year: number;
  step: string;
  discipline: string;
  rankings: WellingtonRankingRow[];
  not_ranked: WellingtonNotRankedRow[];
  config_key: string;
  qualifying_score: number | null;
  wellington_qualifying_score: number | null;
  apparatus_specialists: ApparatusSpecialistRow[];
  apparatus_qualifying_score: number | null;
  apparatus_qualifying_count: number;
}

export async function getWellingtonRankings(
  year: number,
  step: string,
  discipline: string,
  gnzQualifier?: boolean,
  wellingtonQualifier?: boolean,
  intentFilter?: boolean,
): Promise<WellingtonRankingResponse> {
  const params = new URLSearchParams({ year: String(year), step, discipline });
  if (gnzQualifier !== undefined) params.set("gnz_qualifier", gnzQualifier ? "true" : "false");
  if (wellingtonQualifier !== undefined) params.set("wellington_qualifier", wellingtonQualifier ? "true" : "false");
  if (intentFilter !== undefined) params.set("intent_filter", intentFilter ? "true" : "false");
  const res = await fetch(`${API_BASE}/api/rankings/wellington?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getIntents(year: number): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/wellington/intents?year=${year}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.slugs ?? data.gnz_ids ?? [];
}

export async function toggleIntent(identity: string, year: number, submitted: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/api/wellington/intent`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ slug: identity, year, submitted }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getRankingSteps(
  year: number,
  discipline: string
): Promise<{ steps: string[] }> {
  const params = new URLSearchParams({ year: String(year), discipline });
  const res = await fetch(`${API_BASE}/api/rankings/steps?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface DuplicateInstance {
  club: string;
  level_category: string;
  id_counts: Record<string, number>;
  total_rows: number;
}

export interface DuplicateGroup {
  name: string;
  instances: DuplicateInstance[];
  total_rows: number;
}

export async function checkDuplicates(): Promise<DuplicateGroup[]> {
  const res = await fetch(`${API_BASE}/api/admin/duplicates`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fixDuplicates(): Promise<{
  fixed: number;
  low_confidence: DuplicateGroup[];
}> {
  const res = await fetch(`${API_BASE}/api/admin/duplicates/fix`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function applyFixes(
  fixes: Array<{ name: string; club: string; level_category: string; chosen_id: string }>
): Promise<{ applied: number }> {
  const res = await fetch(`${API_BASE}/api/admin/duplicates/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(fixes),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface SuggestedMerge {
  name_a: string;
  name_b: string;
  score: number;
  gnz_ids_a: string[];
  gnz_ids_b: string[];
  rows_a: number;
  rows_b: number;
}

export async function getSuggestedMerges(): Promise<SuggestedMerge[]> {
  const res = await fetch(`${API_BASE}/api/admin/suggested-merges`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function mergeNames(
  from_name: string,
  to_name: string
): Promise<{ merged: number; names_unified: number; ids_corrected: number; conflicts: unknown[] }> {
  const res = await fetch(`${API_BASE}/api/admin/merge-names`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ from_name, to_name }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateGymnast(data: {
  event_id: number;
  current_name: string;
  new_name?: string;
  new_gnz_id?: string;
  new_club?: string;
}): Promise<{ updated: number }> {
  const res = await fetch(`${API_BASE}/api/admin/scores/gymnast`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface AthleteReviewInfo {
  athlete_id: number;
  slug: string;
  name: string;
  gnz_id: string | null;
  clubs: string[];
  events: number;
  event_ids: number[];
  years: number[];
  disciplines: string[];
  rows: number;
  intent_years: number[];
}

export interface SimilarAthletes {
  name_a: string;
  name_b: string;
  score: number;
  athlete_a: AthleteReviewInfo;
  athlete_b: AthleteReviewInfo;
}

export interface NameConflict {
  name: string;
  athletes: AthleteReviewInfo[];
}

export interface IdConflict {
  gnz_id: string;
  athletes: AthleteReviewInfo[];
}

export interface MultiIdAthlete {
  athlete_id: number;
  slug: string;
  name: string;
  gnz_ids: Record<string, number>;
  clubs: string[];
  events: number;
  event_ids: number[];
  years: number[];
  disciplines: string[];
  rows: number;
}

export interface IdentityReview {
  similar_names: SimilarAthletes[];
  name_conflicts: NameConflict[];
  id_conflicts: IdConflict[];
  multi_id_athletes: MultiIdAthlete[];
}

export async function getIdentityReview(): Promise<IdentityReview> {
  const res = await fetch(`${API_BASE}/api/admin/identity-review`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function mergeAthletes(
  athlete_id: number,
  merge_id: number
): Promise<{ merged_rows: number; survivor_id: number; survivor_slug: string }> {
  const res = await fetch(`${API_BASE}/api/admin/athletes/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ athlete_id, merge_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function splitAthlete(data: {
  athlete_id: number;
  split_by: string;
  value: string;
  new_gnz_id?: string;
}): Promise<{
  split_rows: number;
  original_id: number;
  original_slug: string;
  created_id: number;
  created_slug: string;
}> {
  const res = await fetch(`${API_BASE}/api/admin/athletes/split`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function trackPage(path: string): Promise<void> {
  await fetch(`${API_BASE}/api/track/page`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ path }),
  });
}

export interface ActivityLogItem {
  id: number;
  username: string;
  role: string;
  type: string;
  method: string | null;
  path: string;
  query: string | null;
  status_code: number | null;
  duration_ms: number | null;
  created_at: string;
}

export async function getActivityLogs(params?: {
  user?: string;
  type?: string;
  limit?: number;
  offset?: number;
  days?: number;
}): Promise<{ items: ActivityLogItem[]; total: number }> {
  const qp = new URLSearchParams();
  if (params?.user) qp.set("user", params.user);
  if (params?.type) qp.set("type", params.type);
  if (params?.limit !== undefined) qp.set("limit", String(params.limit));
  if (params?.offset !== undefined) qp.set("offset", String(params.offset));
  if (params?.days !== undefined) qp.set("days", String(params.days));
  const qs = qp.toString();
  const res = await fetch(`${API_BASE}/api/admin/activity?${qs}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clearActivityLogs(user?: string): Promise<{ deleted: number }> {
  const qs = user ? `?user=${encodeURIComponent(user)}` : "";
  const res = await fetch(`${API_BASE}/api/admin/activity${qs}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface TrafficPoint {
  date: string;
  page_views: number;
  api_requests: number;
  errors: number;
}

export interface HourPoint {
  hour: number;
  page_views: number;
  api_requests: number;
}

export interface TopPath {
  path: string;
  count: number;
  errors: number;
}

export interface TopUser {
  username: string;
  role: string;
  page_views: number;
  api_requests: number;
}

export interface ActivityTotals {
  page_views: number;
  api_requests: number;
  errors: number;
  avg_duration_ms: number | null;
  active_days: number;
  anon_page_views: number;
  auth_page_views: number;
  anon_api_requests: number;
  auth_api_requests: number;
}

export interface ActivitySummary {
  range_days: number;
  totals: ActivityTotals;
  daily_series: TrafficPoint[];
  auth_daily_series: TrafficPoint[];
  hourly_series: HourPoint[];
  top_pages: TopPath[];
  top_api: TopPath[];
  top_users: TopUser[];
}

export async function getActivitySummary(days: number): Promise<ActivitySummary> {
  const res = await fetch(`${API_BASE}/api/admin/activity/summary?days=${days}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
