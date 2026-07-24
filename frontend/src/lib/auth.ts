import { writable } from "svelte/store";

const TOKEN_KEY = "nzgr_token";

function parseToken(token: string): { username: string; role: string } | null {
  try {
    const payload = token.split(".")[1];
    const decoded = JSON.parse(atob(payload));
    return { username: decoded.sub, role: decoded.role };
  } catch {
    return null;
  }
}

function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function saveToken(token: string | null) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // localStorage unavailable (SSR, privacy mode, etc.)
  }
}

let _token: string | null = loadToken();

export const currentUser = writable<{ username: string; role: string } | null>(
  _token ? parseToken(_token) : null
);
export const authConfigured = writable(false);

export function getToken(): string | null {
  return _token;
}

export function setToken(token: string): void {
  _token = token;
  saveToken(token);
  currentUser.set(parseToken(token));
}

export function logout(): void {
  _token = null;
  saveToken(null);
  currentUser.set(null);
}
