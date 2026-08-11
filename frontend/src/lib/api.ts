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
  if (!res.ok) throw new Error(await res.text());
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
  club?: string;
}): Promise<MedalsResponse> {
  const qp = new URLSearchParams();
  if (params?.year !== undefined) qp.set("year", String(params.year));
  if (params?.gnz_id) qp.set("gnz_id", params.gnz_id);
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
  { gnz_id: string; name: string; club: string | null }[]
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
  return data.gnz_ids;
}

export async function toggleIntent(gnzId: string, year: number, submitted: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/api/wellington/intent`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ gnz_id: gnzId, year, submitted }),
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
}): Promise<{ items: ActivityLogItem[]; total: number }> {
  const qp = new URLSearchParams();
  if (params?.user) qp.set("user", params.user);
  if (params?.type) qp.set("type", params.type);
  if (params?.limit !== undefined) qp.set("limit", String(params.limit));
  if (params?.offset !== undefined) qp.set("offset", String(params.offset));
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
