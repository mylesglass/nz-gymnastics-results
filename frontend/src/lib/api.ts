import { dev } from "$app/environment";

const API_BASE = dev ? "" : "http://backend:8000";

export interface EventSummary {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  year: number | null;
  gymnast_count: number;
  score_count: number;
}

export interface WideResponse {
  event: { id: number; name: string; discipline: string };
  wag: { columns: string[]; rows: Record<string, unknown>[] };
  mag: { columns: string[]; rows: Record<string, unknown>[] };
}

export async function uploadFile(file: File): Promise<EventSummary> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listEvents(): Promise<EventSummary[]> {
  const res = await fetch(`${API_BASE}/api/events`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getWideResults(eventId: number): Promise<WideResponse> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}/results/wide`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getExportUrl(eventId: number, format: "csv" | "xlsx"): string {
  return `${API_BASE}/api/events/${eventId}/export/${format}`;
}

export async function getAllWideResults(params?: {
  gnz_id?: string;
  club?: string;
}): Promise<{
  wag?: { columns: string[]; rows: Record<string, unknown>[] };
  mag?: { columns: string[]; rows: Record<string, unknown>[] };
}> {
  let url = `${API_BASE}/api/results/wide-all`;
  const qp = new URLSearchParams();
  if (params?.gnz_id) qp.set("gnz_id", params.gnz_id);
  if (params?.club) qp.set("club", params.club);
  const qs = qp.toString();
  if (qs) url += `?${qs}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}