"""Path normalization and bot detection for traffic aggregation.

Anonymous usage is counted into ``traffic_daily`` as per-day/hour aggregates
keyed by a normalized path group so raw paths (which embed event IDs, slugs and
query strings) collapse into a bounded set of countable buckets. Bot-like
user-agents are excluded so crawlers and scrapers don't skew the stats; the
user-agent is only inspected in the middleware, never stored.
"""

import re

_BOT_PATTERN = re.compile(
    r"bot|spider|crawl|slurp|curl|wget|python-requests|Go-http-client|"
    r"HeadlessChrome|UptimeRobot|pingdom",
    re.IGNORECASE,
)

_NUMERIC_SEGMENT = re.compile(r"/\d+")
_HEX_SLUG_SEGMENT = re.compile(r"/[0-9a-fA-F]{10}")


def normalize_path(path: str) -> str:
    """Collapse a request path into a countable path group.

    Strips the query string, rewrites pure-numeric segments to ``[id]`` and
    10-char hex segments (athlete slugs) to ``[slug]``. Everything else (e.g.
    club names) is kept verbatim.
    """
    path = (path or "").split("?", 1)[0]
    path = _NUMERIC_SEGMENT.sub("/[id]", path)
    path = _HEX_SLUG_SEGMENT.sub("/[slug]", path)
    return path or "/"


def is_bot(user_agent: str | None) -> bool:
    """Whether a user-agent looks like an automated client or crawler."""
    if not user_agent:
        return False
    return bool(_BOT_PATTERN.search(user_agent))
