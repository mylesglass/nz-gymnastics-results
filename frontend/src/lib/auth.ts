import { writable } from "svelte/store";

const TOKEN_KEY = "nzgr_token";
const PERMISSIONS_KEY = "nzgr_permissions";

export const PERMISSIONS = {
  national: "rankings.national",
  wellington: "rankings.wellington",
} as const;

export interface CurrentUser {
  username: string;
  role: string;
  permissions: string[];
}

function parseToken(token: string): { username: string; role: string } | null {
  try {
    const payload = token.split(".")[1];
    const decoded = JSON.parse(atob(payload));
    if (decoded.exp && Date.now() / 1000 > decoded.exp) return null;
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

function loadPermissions(): string[] {
  try {
    const raw = localStorage.getItem(PERMISSIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function savePermissions(permissions: string[]) {
  try {
    if (permissions.length > 0) {
      localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(permissions));
    } else {
      localStorage.removeItem(PERMISSIONS_KEY);
    }
  } catch {
    // localStorage unavailable
  }
}

let _token: string | null = loadToken();
let _permissions: string[] = loadPermissions();

function toUser(
  token: { username: string; role: string } | null,
  permissions: string[]
): CurrentUser | null {
  return token ? { ...token, permissions } : null;
}

export const currentUser = writable<CurrentUser | null>(
  toUser(_token ? parseToken(_token) : null, _permissions)
);
export const authConfigured = writable(false);

export function getToken(): string | null {
  return _token;
}

export function setToken(token: string, permissions?: string[]): void {
  _token = token;
  saveToken(token);
  if (permissions) {
    _permissions = permissions;
    savePermissions(permissions);
  }
  currentUser.set(toUser(parseToken(token), _permissions));
}

export function setPermissions(permissions: string[]): void {
  _permissions = permissions;
  savePermissions(permissions);
  const parsed = _token ? parseToken(_token) : null;
  currentUser.set(toUser(parsed, permissions));
}

export function logout(): void {
  _token = null;
  _permissions = [];
  saveToken(null);
  savePermissions([]);
  currentUser.set(null);
}

export function hasPermission(
  user: CurrentUser | null,
  permission: string
): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  return user.permissions.includes(permission);
}
