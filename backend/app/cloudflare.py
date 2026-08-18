"""Fetch Cloudflare zone HTTP traffic analytics via the GraphQL Analytics API.

The admin dashboard shows a Cloudflare overview band (unique visitors, total
requests, percent cached and total data served as stacked sparklines) alongside
the site's own server-side analytics. Everything is fetched from the
``httpRequests1dGroups`` (daily rollup, ~30 days retention) and
``httpRequestsAdaptiveGroups`` (fine-grained series, capped at a 1-day query
range) datasets. Credentials come from ``CLOUDFLARE_ZONE_ID`` and
``CLOUDFLARE_API_TOKEN`` (zone-scoped, Analytics:Read).
"""

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"
_DAILY_RETENTION_DAYS = 30
# The httpRequestsAdaptiveGroups quota limits a query to a 1-day time range,
# so top-country/status-code breakdowns only cover the last 24 hours.
_BREAKDOWN_RETENTION_DAYS = 1


class CloudflareFetchError(Exception):
    """Raised when Cloudflare analytics cannot be fetched or parsed."""


def is_configured() -> bool:
    """Whether zone + API token env vars are present."""
    return bool(
        os.environ.get("CLOUDFLARE_ZONE_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    )


def _graphql(query: str) -> dict:
    """Run one GraphQL query against the Cloudflare Analytics API."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise CloudflareFetchError("Cloudflare API token not configured")
    try:
        with httpx.Client(
            timeout=20,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            response = client.post(GRAPHQL_ENDPOINT, json={"query": query})
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise CloudflareFetchError(f"Could not reach Cloudflare: {e}") from e

    if response.status_code >= 400:
        raise CloudflareFetchError(f"Cloudflare returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as e:
        raise CloudflareFetchError(f"Cloudflare returned invalid JSON: {e}") from e
    if data.get("errors"):
        raise CloudflareFetchError(f"Cloudflare GraphQL error: {data['errors']}")
    return data


def build_daily_query(zone_id: str, days: int) -> str:
    """GraphQL query for per-day rollups over the last ``days`` days."""
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return f"""
    query {{
      viewer {{
        zones(filter: {{ zoneTag: "{zone_id}" }}) {{
          httpRequests1dGroups(
            limit: {days}
            orderBy: [date_ASC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            dimensions {{ date }}
            sum {{ requests bytes cachedRequests cachedBytes threats }}
            uniq {{ uniques }}
          }}
        }}
      }}
    }}
    """


def build_breakdown_query(zone_id: str, days: int) -> str:
    """GraphQL query for last-24h breakdowns (countries, status, paths, cache, device)."""
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return f"""
    query {{
      viewer {{
        zones(filter: {{ zoneTag: "{zone_id}" }}) {{
          topCountries: httpRequestsAdaptiveGroups(
            limit: 10
            orderBy: [count_DESC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ clientCountryName }}
          }}
          statusCodes: httpRequestsAdaptiveGroups(
            limit: 12
            orderBy: [count_DESC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ edgeResponseStatus }}
          }}
          topPaths: httpRequestsAdaptiveGroups(
            limit: 10
            orderBy: [count_DESC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ clientRequestPath }}
          }}
          cacheStatus: httpRequestsAdaptiveGroups(
            limit: 10
            orderBy: [count_DESC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ cacheStatus }}
          }}
          deviceType: httpRequestsAdaptiveGroups(
            limit: 10
            orderBy: [count_DESC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ clientDeviceType }}
          }}
          hourly: httpRequestsAdaptiveGroups(
            limit: 48
            orderBy: [datetimeHour_ASC]
            filter: {{ date_geq: "{start}" }}
          ) {{
            count
            dimensions {{ datetimeHour }}
          }}
        }}
      }}
    }}
    """


def build_hourly_series_query(zone_id: str, with_uniques: bool = True) -> str:
    """GraphQL query for a rolling last-24h hourly series.

    Groups the adaptive dataset by ``datetimeHour`` over the trailing 24-hour
    window (UTC). ``with_uniques`` selects per-hour ``uniq { uniques }`` too —
    some zone-scoped Analytics:Read tokens reject that field, in which case the
    caller retries with it disabled.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:00:00Z")
    end = now.strftime("%Y-%m-%dT%H:00:00Z")
    uniq_field = "\n            uniq { uniques }" if with_uniques else ""
    return f"""
    query {{
      viewer {{
        zones(filter: {{ zoneTag: "{zone_id}" }}) {{
          hourlySeries: httpRequestsAdaptiveGroups(
            limit: 24
            orderBy: [datetimeHour_ASC]
            filter: {{ datetimeHour_geq: "{start}", datetimeHour_lt: "{end}" }}
          ) {{
            sum {{ requests bytes cachedBytes cachedRequests }}
            {uniq_field}
            dimensions {{ datetimeHour }}
          }}
        }}
      }}
    }}
    """


def _zone_view(data: dict) -> dict:
    """Dig into the GraphQL response to the zone's node."""
    try:
        return data["data"]["viewer"]["zones"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise CloudflareFetchError(f"Unexpected Cloudflare response: {e}") from e


def parse_zone_response(data: dict, days: int) -> dict:
    """Turn the daily-rollup GraphQL response into daily figures + totals."""
    view = _zone_view(data)

    daily = []
    for group in view.get("httpRequests1dGroups") or []:
        dims = group.get("dimensions") or {}
        sums = group.get("sum") or {}
        uniq = group.get("uniq") or {}
        daily.append({
            "date": dims.get("date", ""),
            "requests": sums.get("requests", 0),
            "bytes": sums.get("bytes", 0),
            "threats": sums.get("threats", 0),
            "cached_requests": sums.get("cachedRequests", 0),
            "cached_bytes": sums.get("cachedBytes", 0),
            "unique_visitors": uniq.get("uniques", 0),
        })

    totals = {
        "requests": sum(d["requests"] for d in daily),
        "bytes": sum(d["bytes"] for d in daily),
        "unique_visitors": sum(d["unique_visitors"] for d in daily),
        "threats": sum(d["threats"] for d in daily),
    }
    cached_bytes = sum(d["cached_bytes"] for d in daily)
    totals["cache_hit_ratio"] = round(cached_bytes / totals["bytes"], 4) if totals["bytes"] else None

    return {
        "configured": True,
        "days": days,
        "totals": totals,
        "daily": daily,
    }


def _parse_breakdown(view: dict) -> dict:
    """Turn the adaptive-breakdown response into the 24h breakdown fields."""
    return {
        "top_countries": [
            {"country": (g.get("dimensions") or {}).get("clientCountryName") or "Unknown",
             "requests": g.get("count", 0)}
            for g in view.get("topCountries") or []
        ],
        "status_codes": [
            {"code": (g.get("dimensions") or {}).get("edgeResponseStatus"),
             "requests": g.get("count", 0)}
            for g in view.get("statusCodes") or []
        ],
        "top_paths": [
            {"name": (g.get("dimensions") or {}).get("clientRequestPath") or "/",
             "count": g.get("count", 0)}
            for g in view.get("topPaths") or []
        ],
        "cache_status": [
            {"name": (g.get("dimensions") or {}).get("cacheStatus") or "Unknown",
             "count": g.get("count", 0)}
            for g in view.get("cacheStatus") or []
        ],
        "device_type": [
            {"name": (g.get("dimensions") or {}).get("clientDeviceType") or "Unknown",
             "count": g.get("count", 0)}
            for g in view.get("deviceType") or []
        ],
        "hourly": _bucket_hourly(view.get("hourly") or []),
    }


def _bucket_hourly(hour_groups: list[dict]) -> list[dict]:
    """Aggregate per-hour request counts into 24 hourly buckets (0-23, UTC).

    ``datetimeHour`` (or ``datetimeMinute``) values are ISO timestamps; the
    bucket key is the hour in UTC (Cloudflare timestamps are UTC). Days without
    data fill with zeroes so the chart always has a full 24-slot axis.
    """
    buckets: dict[int, int] = {h: 0 for h in range(24)}
    for group in hour_groups:
        dims = group.get("dimensions") or {}
        ts = dims.get("datetimeHour") or dims.get("datetimeMinute")
        if not ts:
            continue
        try:
            hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
        except ValueError:
            continue
        buckets[hour] += group.get("count", 0)
    return [
        {"hour": h, "requests": buckets[h]}
        for h in range(24)
    ]


def _fetch_hourly_series(zone_id: str) -> tuple[list[dict], bool]:
    """Fetch the rolling last-24h hourly groups, retrying without uniques.

    Some zone-scoped Analytics:Read tokens reject ``uniq { uniques }`` on the
    adaptive dataset; when that happens the query is retried without it and the
    caller is told uniques are unavailable.
    """
    try:
        data = _graphql(build_hourly_series_query(zone_id, with_uniques=True))
        return _zone_view(data).get("hourlySeries") or [], True
    except CloudflareFetchError:
        data = _graphql(build_hourly_series_query(zone_id, with_uniques=False))
        return _zone_view(data).get("hourlySeries") or [], False


def _parse_hourly_series(hour_groups: list[dict], has_uniques: bool, now: datetime | None = None) -> list[dict]:
    """Turn the rolling last-24h adaptive response into 24 hourly series points.

    The window is 24 trailing UTC hours ending at the current hour (or ``now``,
    for tests), zero-filled so the chart always has a full 24-slot axis.
    ``unique_visitors`` is per-hour when Cloudflare provided uniques, otherwise
    ``None``.
    """
    now = now or datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    by_hour: dict[str, dict] = {}
    for group in hour_groups:
        dims = group.get("dimensions") or {}
        ts = dims.get("datetimeHour")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(
                minute=0, second=0, microsecond=0
            )
        except ValueError:
            continue
        sums = group.get("sum") or {}
        uniq = group.get("uniq") or {}
        requests = sums.get("requests", 0)
        bytes_total = sums.get("bytes", 0)
        by_hour[dt.isoformat()] = {
            "label": dt.isoformat(),
            "datetime": dt.isoformat(),
            "requests": requests,
            "bytes": bytes_total,
            "cached_bytes": sums.get("cachedBytes", 0),
            "cached_requests": sums.get("cachedRequests", 0),
            "unique_visitors": uniq.get("uniques", 0) if has_uniques else None,
            "cached_percent": round(sums.get("cachedBytes", 0) / bytes_total, 4)
            if bytes_total else None,
        }
    points = []
    for i in range(24):
        dt = start + timedelta(hours=i)
        point = by_hour.get(dt.isoformat())
        if point is None:
            point = {
                "label": dt.isoformat(),
                "datetime": dt.isoformat(),
                "requests": 0,
                "bytes": 0,
                "cached_bytes": 0,
                "cached_requests": 0,
                "unique_visitors": 0 if has_uniques else None,
                "cached_percent": None,
            }
        points.append(point)
    return points


def _build_daily_series(daily: list[dict]) -> list[dict]:
    """Turn daily rollups into the unified per-day series shape."""
    series = []
    for d in daily:
        cached_percent = round(d["cached_bytes"] / d["bytes"], 4) if d["bytes"] else None
        series.append({
            "label": d["date"],
            "datetime": d["date"],
            "requests": d["requests"],
            "bytes": d["bytes"],
            "cached_bytes": d["cached_bytes"],
            "cached_requests": d["cached_requests"],
            "unique_visitors": d["unique_visitors"],
            "cached_percent": cached_percent,
        })
    return series


def fetch_zone_summary(days: int = 30) -> dict:
    """Fetch and parse Cloudflare zone analytics for the last ``days`` days.

    ``days == 1`` selects a rolling 24-hour window (hourly series); ``7``/``30``
    select trailing per-day windows (daily series, capped at the 30-day
    retention). The unified ``series`` field drives the overview sparklines.
    """
    if not is_configured():
        raise CloudflareFetchError("Cloudflare not configured (zone ID/token missing)")
    zone_id = os.environ["CLOUDFLARE_ZONE_ID"]
    days = _DAILY_RETENTION_DAYS if days > _DAILY_RETENTION_DAYS else max(1, days)

    if days == 1:
        # The rolling 24h window spans parts of two calendar days, so totals are
        # rebuilt from the hourly series (matching what the sparkline shows)
        # rather than today's partial daily rollup.
        hourly_groups, has_uniques = _fetch_hourly_series(zone_id)
        series = _parse_hourly_series(hourly_groups, has_uniques)
        daily_data = _graphql(build_daily_query(zone_id, 1))
        summary = parse_zone_response(daily_data, 1)
        totals = summary["totals"]
        totals["requests"] = sum(p["requests"] for p in series)
        totals["bytes"] = sum(p["bytes"] for p in series)
        cached_bytes = sum(p["cached_bytes"] for p in series)
        totals["cache_hit_ratio"] = round(cached_bytes / totals["bytes"], 4) if totals["bytes"] else None
        if has_uniques:
            totals["unique_visitors"] = sum(p["unique_visitors"] or 0 for p in series)
    else:
        daily_data = _graphql(build_daily_query(zone_id, days))
        summary = parse_zone_response(daily_data, days)
        series = _build_daily_series(summary["daily"])

    breakdown_data = _graphql(build_breakdown_query(zone_id, _BREAKDOWN_RETENTION_DAYS))
    summary.update(_parse_breakdown(_zone_view(breakdown_data)))
    summary["series"] = series
    return summary
