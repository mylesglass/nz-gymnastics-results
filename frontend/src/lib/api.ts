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
}

export interface WideResponse {
  event: { id: number; name: string; discipline: string };
  wag: { columns: string[]; rows: Record<string, unknown>[] };
  mag: { columns: string[]; rows: Record<string, unknown>[] };
}

export async function checkAuthStatus(): Promise<{ configured: boolean }> {
  const res = await fetch(`${API_BASE}/api/auth/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function authLogin(username: string, password: string): Promise<{ access_token: string; role: string }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadFile(file: File, allowUnknown = false): Promise<EventSummary> {
  const form = new FormData();
  form.append("file", file);
  let url = `${API_BASE}/api/upload`;
  if (allowUnknown) url += "?allow_unknown=1";
  const res = await fetch(url, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  if (res.status === 409) {
    const body = await res.json();
    const detail = body.detail || body;
    const err = new Error(detail.message || "Unknown clubs") as Error & Record<string, unknown>;
    err._clubConflict = true;
    err.unknown_clubs = detail.unknown_clubs;
    err.known_clubs = detail.known_clubs;
    throw err;
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  const res = await fetch(`${API_BASE}/api/events`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  data: { name?: string; is_national?: boolean }
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
  { name: string; gymnast_count: number; region: string | null }[]
> {
  const res = await fetch(`${API_BASE}/api/clubs`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listYears(): Promise<{ years: number[] }> {
  const res = await fetch(`${API_BASE}/api/years`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listGymnasts(): Promise<
  { gnz_id: string; name: string; club: string | null }[]
> {
  const res = await fetch(`${API_BASE}/api/gymnasts`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function reconcileAthletes(): Promise<{
  total_athletes: number;
  ids_corrected: number;
  names_unified: number;
  conflicts: Array<{ name: string; previous_ids: string[]; chosen_id: string | null; rows_updated: number }>;
}> {
  const res = await fetch(`${API_BASE}/api/admin/reconcile-athletes`, {
    method: "POST",
    headers: authHeaders(),
  });
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
}

export interface RankingsResponse {
  year: number;
  step: string;
  discipline: string;
  rankings: RankingRow[];
}

export async function getRankings(
  year: number,
  step: string,
  discipline: string,
  quota?: boolean,
  qualifier?: boolean
): Promise<RankingsResponse> {
  const params = new URLSearchParams({ year: String(year), step, discipline });
  if (quota) params.set("quota", "true");
  if (qualifier) params.set("qualifier", "true");
  const res = await fetch(`${API_BASE}/api/rankings?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
