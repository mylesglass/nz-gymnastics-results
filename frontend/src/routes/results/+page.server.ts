import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export const load: PageServerLoad = async () => {
  let totalScores: number | null = null;
  try {
    const stats = await backendFetch<{ total_scores: number }>("/api/stats");
    totalScores = stats.total_scores;
  } catch {
    totalScores = null;
  }
  return { totalScores };
};
