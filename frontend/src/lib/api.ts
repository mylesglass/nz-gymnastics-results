import { dev } from "$app/environment";

const API_BASE = dev ? "" : "http://backend:8000";

export interface EventSummary {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  gymnast_count: number;
  score_count: number;
}

export interface ResultsResponse {
  event: { id: number; name: string; gymnast_count: number };
  columns: string[];
  rows: Record<string, unknown>[];
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

export async function getResults(eventId: number): Promise<ResultsResponse> {
  const res = await fetch(`${API_BASE}/api/events/${eventId}/results`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getExportUrl(eventId: number, format: "csv" | "xlsx"): string {
  return `${API_BASE}/api/events/${eventId}/export/${format}`;
}