import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export const load: PageServerLoad = async () => {
  let stats: {
    total_events: number;
    total_gymnasts: number;
    total_scores: number;
    total_clubs: number;
  } | null = null;
  try {
    stats = await backendFetch(
      "/api/stats",
    );
  } catch {
    stats = null;
  }
  return { stats };
};
