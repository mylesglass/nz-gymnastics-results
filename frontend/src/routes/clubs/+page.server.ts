import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export interface ClubData {
  name: string;
  gymnast_count: number;
  region: string | null;
  is_region: boolean;
}

export const load: PageServerLoad = async () => {
  let clubs: ClubData[] = [];
  try {
    clubs = await backendFetch<ClubData[]>("/api/clubs");
  } catch {
    clubs = [];
  }
  return { clubs };
};
