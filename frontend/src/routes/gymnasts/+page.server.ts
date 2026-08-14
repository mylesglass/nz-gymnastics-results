import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export interface GymnastData {
  slug?: string;
  gnz_id: string;
  name: string;
  club: string | null;
  alt_ids: string[];
  alt_clubs: string[];
}

export const load: PageServerLoad = async () => {
  let gymnasts: GymnastData[] = [];
  try {
    gymnasts = await backendFetch<GymnastData[]>("/api/gymnasts");
  } catch {
    gymnasts = [];
  }
  return { gymnasts };
};
