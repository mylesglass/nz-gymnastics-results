import { error, redirect } from "@sveltejs/kit";
import type { PageServerLoad } from "./$types";
import { backendFetch } from "$lib/backend";
import { kebabName } from "$lib/seo";

interface GymnastIdentity {
  slug: string;
  gnz_id: string;
  name: string;
  club: string | null;
}

export const load: PageServerLoad = async ({ params, url }) => {
  const raw = params.slug;
  const match = raw.match(/^(a[0-9a-f]{10})(?:-(.*))?$/i);
  const identity = match ? `slug=${match[1]}` : `gnz_id=${encodeURIComponent(raw)}`;

  let g: GymnastIdentity | null = null;
  try {
    g = await backendFetch<GymnastIdentity | null>(`/api/gymnast?${identity}`);
  } catch {
    g = null;
  }

  if (!g || !g.name) {
    throw error(404, "Gymnast not found");
  }

  const name = g.name;
  const slug = g.slug || (match ? match[1] : g.gnz_id);
  const suffix = kebabName(name);
  const readablePath = suffix ? `/gymnast/${slug}-${suffix}` : `/gymnast/${slug}`;

  if (g.slug && url.pathname !== readablePath) {
    throw redirect(301, readablePath);
  }

  return { name, slug: g.slug || "" };
};
