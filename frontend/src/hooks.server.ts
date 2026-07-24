import type { Handle } from "@sveltejs/kit";

const backend = process.env.PROXY_TARGET || "http://backend:8000";

export const handle: Handle = async ({ event, resolve }) => {
  const url = event.url;
  if (url.pathname.startsWith("/api")) {
    const target = new URL(url.pathname + url.search, backend);
    const headers = new Headers(event.request.headers);
    headers.delete("host");
    const body =
      event.request.method === "GET" || event.request.method === "HEAD"
        ? undefined
        : await event.request.text();
    const proxy = await fetch(target, {
      method: event.request.method,
      headers,
      body,
    });
    return new Response(proxy.body, {
      status: proxy.status,
      statusText: proxy.statusText,
      headers: proxy.headers,
    });
  }
  return resolve(event);
};
