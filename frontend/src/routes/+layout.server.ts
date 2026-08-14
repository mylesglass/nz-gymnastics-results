import { env } from "$env/dynamic/private";

export function load(): { verification: string | null } {
  return { verification: env.SEO_VERIFICATION_META || null };
}
