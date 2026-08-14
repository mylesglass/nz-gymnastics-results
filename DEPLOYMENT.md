# Deployment & TLS Runbook — `https://results.coach.tools`

Runbook for diagnosing and fixing the "Your Connection Isn't Private" /
`NET::ERR_CERT_AUTHORITY_INVALID` errors users see when opening the site.

## Quick summary

- Public entry is **Cloudflare** → **Nginx Proxy Manager (NPM)** on the origin VPS → the
  `frontend:3000` / `backend:8000` containers (see `docker-compose.prod.yml`).
- A browser only validates the certificate of the server it **actually connects to**.
- From outside, `https://results.coach.tools` is healthy: valid Google Trust Services
  cert for `coach.tools` + `*.coach.tools` (edge), TLS 1.3, chain verifies
  (`Verify return code: 0`), HTTP 200.
- `NET::ERR_CERT_AUTHORITY_INVALID` therefore means the affected user is **not**
  terminating on Cloudflare. They are almost always connecting straight to the origin
  VPS (via stale DNS from before the Cloudflare migration, or an alternate URL), where
  NPM is presenting a certificate their browser doesn't trust.

## Step 1 — Reproduce and capture the exact cert (do this first)

From an affected user's browser (or any browser that shows the error):

1. Open `https://results.coach.tools`.
2. Click the padlock / "Not secure" → **Certificate**.
3. Record: **Issuer**, **Subject (CN)**, **Not-valid-after**.

That one data point tells you which branch below you're in:

| Certificate shows | Cause | Fix |
|---|---|---|
| `CN=Nginx Proxy Manager` (self-signed) | NPM has SSL enabled but no real cert saved → serves its built-in default | Step 4 — request/reinstall cert |
| Subject is for a different host (e.g. the old `scores.mylesglass.com` cert still selected) | Wrong/old cert selected in NPM host | Step 4 — select the correct cert |
| Issuer is a real CA but **expired** | Let's Encrypt renewal failed | Step 4 — renew cert |
| A valid cert for `results.coach.tools` | Browser isn't reaching NPM via this host; device/network interception or stale DNS | Step 2 & 3 |

## Step 2 — Check DNS from an affected device

On the failing device run:

```bash
nslookup results.coach.tools
```

- If it returns Cloudflare IPs (`104.21.x.x` / `172.67.x.x`) → the browser IS going
  through Cloudflare, so the error can't come from the edge. Investigate device/network
  HTTPS interception, or an alternate URL the user is typing (raw IP, `:443` port, old
  bookmark).
- If it returns your **origin VPS IP** → the user is bypassing Cloudflare. The domain
  moved to Cloudflare ~a week ago and DNS is still propagating. Mitigations:
  1. Confirm the `results.coach.tools` A/AAAA records are **proxied** (orange cloud) in
     Cloudflare DNS.
  2. Lower the record TTL (e.g. 60–300s) so propagation completes quickly.
  3. Make the origin's cert valid (Step 4) so even direct-origin hits validate.

Also check the old domain: users with `scores.mylesglass.com` bookmarks may be landing
somewhere stale — add a 301 redirect on that host to `https://results.coach.tools`.

## Step 3 — Verify Cloudflare SSL mode

In the Cloudflare dashboard → `results.coach.tools` → **SSL/TLS → Overview**:

- Must be **Full** or **Full (strict)**. Do **not** use **Flexible**.
- With a Cloudflare Origin Certificate installed on NPM, use **Full (strict)** (Step 4).

## Step 4 — Fix the origin certificate (NPM)

From the VPS, inspect what NPM actually serves for the host (replace `<VPS_IP>`):

```bash
echo | openssl s_client -connect <VPS_IP>:443 -servername results.coach.tools 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

Compare the output with what the browser reported and what NPM shows in
**Hosts → results.coach.tools → SSL tab**.

**Option A — Let's Encrypt (standard):**
1. In NPM, open the proxy host → **SSL** tab.
2. Select "Request a new SSL Certificate" → Let's Encrypt → force SSL on.
3. Port 80 must be reachable from the internet for HTTP-01 validation (Cloudflare passes
   port 80 through to the origin, so this works while proxied).
4. Save, then re-run the verification in Step 5.

**Option B — Cloudflare Origin Certificate (recommended, permanent):**
1. Cloudflare dashboard → SSL/TLS → **Origin Server** → Create Certificate (free, e.g.
   15-year, `*.coach.tools`).
2. In NPM, select **"Use a custom certificate"** and paste the Origin cert + key.
3. Set Cloudflare SSL/TLS mode to **Full (strict)**.
4. Result: even users who hit the origin directly via stale DNS get a valid cert, and
   Cloudflare→origin is encrypted end-to-end.

## Step 5 — Verify

After any fix, re-run from a non-CDN vantage point and from the VPS:

```bash
# Edge: valid chain + hostname coverage
echo | openssl s_client -connect results.coach.tools:443 -servername results.coach.tools 2>/dev/null \
  | grep "Verify return code"

# Origin: the cert NPM presents must be the one you just configured
echo | openssl s_client -connect <VPS_IP>:443 -servername results.coach.tools 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# Page serves
curl -sI https://results.coach.tools | head -5
```

Then repeat Step 1/2 from an affected device — it should now show a valid cert and
`nslookup` should return Cloudflare IPs.

## App-level configuration check

Not the cert cause, but part of a clean domain migration:

- The deployed frontend's `ORIGIN` env must be `https://results.coach.tools`
  (`docker-compose.prod.yml:26` defaults to `http://localhost:3000` — easy to miss when
  redeploying with a new domain).
- The API proxy (`hooks.server.ts`) and `API_BASE` are same-origin, so they need no
  change for a domain move.

## Deploying (caching & restarts)

- Hashed `_app/immutable/*` bundles are served `Cache-Control: public,max-age=31536000,immutable`,
  so a new build's bundles are fetched automatically on the next page load; the HTML shell
  is not cached. Users with the app open in a tab are prompted to reload via the
  `version.pollInterval`/`updated` banner (see `svelte.config.js` + `+layout.svelte`).
- The backend in-memory cache (`GranularTTLCache`) is process-local and clears on every
  container restart, so no server-side data goes stale across a deploy. Browser/CDN
  caching of public API reads is capped at `max-age=300, stale-while-revalidate=60`.
- Both services define `healthcheck`s and the frontend `depends_on backend:
  condition: service_healthy`. With single replicas a brief 502/second window is still
  possible while a container restarts during `docker compose up -d --build`; Cloudflare
  sits in front and may absorb/serve cached responses during that window.
