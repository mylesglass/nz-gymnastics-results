import { writable } from "svelte/store";

export const selectedYear = writable<string | null>(null);
export const yearOptions = writable<string[]>([]);
