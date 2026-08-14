import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

interface ClubItem {
  name: string;
  gymnast_count: number;
  region: string | null;
  is_region: boolean;
}

export const load: PageServerLoad = async ({ params }) => {
  const raw = params.club;
  let clubs: ClubItem[] = [];
  try {
    clubs = await backendFetch<ClubItem[]>("/api/clubs");
  } catch {
    clubs = [];
  }
  const club =
    clubs.find((c) => c.name === raw) ??
    clubs.find((c) => c.name.toLowerCase() === raw.toLowerCase());
  if (!club) {
    throw error(404, "Club not found");
  }
  return { name: club.name, region: club.region, gymnastCount: club.gymnast_count };
};
