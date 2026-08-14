import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";

export interface EventSummaryData {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  discipline: string;
  year: number | null;
  gymnast_count: number;
  is_national?: boolean;
  host_club?: string | null;
}

export const load: PageServerLoad = async () => {
  let events: EventSummaryData[] = [];
  try {
    events = await backendFetch<EventSummaryData[]>("/api/events");
  } catch {
    events = [];
  }
  return { events };
};
