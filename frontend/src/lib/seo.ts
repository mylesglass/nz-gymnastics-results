export const SITE_NAME = "NZ Gymnastics Results";

export const SITE_DESCRIPTION =
  "Search, browse, and share New Zealand Artistic Gymnastics competition results — events, gymnasts, clubs, medals, and scores for WAG and MAG.";

export function pageTitle(title: string): string {
  return title.includes(SITE_NAME) ? title : `${title} — ${SITE_NAME}`;
}

export function kebabName(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function gymnastPath(
  slug: string | undefined | null,
  gnzId: string,
  name: string
): string {
  if (slug && name) {
    const suffix = kebabName(name);
    return suffix ? `/gymnast/${slug}-${suffix}` : `/gymnast/${slug}`;
  }
  return `/gymnast/${encodeURIComponent(slug || gnzId)}`;
}
