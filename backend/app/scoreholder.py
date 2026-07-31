"""Fetch Scoreholder event JSON exports from public event URLs."""

import json
import re

import httpx

SCOREHOLDER_API = "https://scoreholder.com/api/events/{event_id}?context=public"
_EVENT_ID_RE = re.compile(r"/events/([0-9a-f]{24})")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


class ScoreholderFetchError(Exception):
    """Raised when a Scoreholder event export cannot be fetched."""


def extract_event_id(url: str) -> str | None:
    """Return the 24-hex event ID from a Scoreholder event URL, or None."""
    match = _EVENT_ID_RE.search(url)
    return match.group(1) if match else None


def fetch_event_json(url: str) -> dict:
    """Fetch and decode the public JSON export for a Scoreholder event URL.

    Raises:
        ScoreholderFetchError: on network failure, HTTP error, or invalid JSON.
    """
    event_id = extract_event_id(url)
    if not event_id:
        raise ScoreholderFetchError("Could not find a Scoreholder event ID in the URL")

    api_url = SCOREHOLDER_API.format(event_id=event_id)
    try:
        with httpx.Client(follow_redirects=True, timeout=60, headers=_HEADERS) as client:
            response = client.get(api_url)
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise ScoreholderFetchError(f"Could not reach Scoreholder: {e}") from e

    if response.status_code == 404:
        raise ScoreholderFetchError("Scoreholder event not found (404)")
    if response.status_code == 204 or not response.text.strip():
        raise ScoreholderFetchError("Scoreholder returned no data for this event")
    if response.status_code >= 400:
        raise ScoreholderFetchError(f"Scoreholder returned HTTP {response.status_code}")

    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise ScoreholderFetchError(f"Scoreholder returned invalid JSON: {e}") from e
