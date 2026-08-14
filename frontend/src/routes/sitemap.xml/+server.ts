import type { RequestHandler } from "./$types";
import { backendFetch } from "$lib/backend";
import { kebabName } from "$lib/seo";

interface EventListItem {
  id: number;
  name: string;
  discipline: string;
}

interface GymnastItem {
  slug?: string;
  gnz_id: string;
  name: string;
}

interface ClubItem {
  name: string;
}

function escXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export const GET: RequestHandler = async ({ url }) => {
  const origin = url.origin;
  const locs: string[] = ["/", "/events", "/results", "/gymnasts", "/clubs"];

  try {
    const events = await backendFetch<EventListItem[]>("/api/events");
    for (const e of events) locs.push(`/events/${e.id}`);
  } catch {
    // events unavailable — sitemap still valid with static pages
  }
  try {
    const gymnasts = await backendFetch<GymnastItem[]>("/api/gymnasts");
    for (const g of gymnasts) {
      if (g.slug) {
        locs.push(`/gymnast/${g.slug}-${kebabName(g.name)}`);
      } else if (g.gnz_id) {
        locs.push(`/gymnast/${encodeURIComponent(g.gnz_id)}`);
      }
    }
  } catch {
    // gymnasts unavailable
  }
  try {
    const clubs = await backendFetch<ClubItem[]>("/api/clubs");
    for (const c of clubs) {
      locs.push(`/club/${encodeURIComponent(c.name)}`);
    }
  } catch {
    // clubs unavailable
  }

  const urls = locs
    .map(
      (loc) =>
        `<url><loc>${escXml(`${origin}${loc}`)}</loc></url>`
    )
    .join("\n  ");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  ${urls}
</urlset>
`;

  return new Response(body, {
    headers: { "Content-Type": "application/xml" },
  });
};
