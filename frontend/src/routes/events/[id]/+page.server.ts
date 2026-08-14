import { error } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export interface EventDetailData {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  year: number | null;
  gymnast_count: number;
  is_national: boolean;
  host_club: string | null;
}

export const load: PageServerLoad = async ({ params }) => {
  const id = Number(params.id);
  let events: EventDetailData[] = [];
  try {
    events = await backendFetch<EventDetailData[]>("/api/events");
  } catch {
    // fall through to 404 below
  }
  const event = events.find((e) => e.id === id);
  if (!event) {
    throw error(404, "Event not found");
  }
  return { event };
};
