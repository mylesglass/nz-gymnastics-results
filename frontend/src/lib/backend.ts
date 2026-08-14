import { dev } from "$app/environment";

export const BACKEND_URL =
  process.env.PROXY_TARGET || (dev ? "http://localhost:8000" : "http://backend:8000");

export async function backendFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`);
  if (!res.ok) throw new Error(`backend ${path}: HTTP ${res.status}`);
  return res.json();
}
