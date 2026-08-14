import type { RequestHandler } from "./$types";

export const GET: RequestHandler = ({ url }) => {
  const origin = url.origin;
  const body = `User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin
Disallow: /upload
Disallow: /login
Disallow: /rankings
Disallow: /wellington-ranking

Sitemap: ${origin}/sitemap.xml
`;
  return new Response(body, {
    headers: { "Content-Type": "text/plain" },
  });
};
