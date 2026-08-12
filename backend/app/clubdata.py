"""Resolve the active clubs_and_regions.json path and seed it from the image.

The canonical club data lives in the persistent ``data/`` volume
(``data/clubs_and_regions.json``) so aliases added at runtime survive
container recreations. The repo file shipped inside the image
(``backend/clubs_and_regions.json``) acts as the seed for fresh volumes.
"""

import json
import os
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
os.makedirs(DATA_DIR, exist_ok=True)


def active_path() -> Path:
    """Return the persistent club-data file (inside the data volume)."""
    return DATA_DIR / "clubs_and_regions.json"


def seed_path() -> Path:
    """Return the bundled seed file shipped inside the image."""
    return Path(__file__).resolve().parent.parent / "clubs_and_regions.json"


def ensure_seed() -> Path:
    """Copy the bundled seed into the data volume when it's missing.

    Returns the active path. No-op once the volume copy exists.
    """
    active = active_path()
    if not active.exists():
        seed = seed_path()
        if seed.exists():
            shutil.copy(seed, active)
    return active


def load_club_data() -> dict:
    """Load the active club data, seeding the volume copy first if needed."""
    with open(ensure_seed()) as f:
        return json.load(f)
