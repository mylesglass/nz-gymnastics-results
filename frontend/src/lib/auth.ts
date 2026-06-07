import { writable } from "svelte/store";

export const isLoggedIn = writable(false);
export const authConfigured = writable(false);

let _password: string | null = null;

export function login(password: string): void {
  _password = password;
  isLoggedIn.set(true);
}

export function logout(): void {
  _password = null;
  isLoggedIn.set(false);
}

export function getPassword(): string | null {
  return _password;
}
