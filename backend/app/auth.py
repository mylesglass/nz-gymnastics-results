import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

ADMIN_PASSWORD: str | None = os.environ.get("ADMIN_PASSWORD")


def is_auth_configured() -> bool:
    return ADMIN_PASSWORD is not None


def check_password(password: str) -> bool:
    if not is_auth_configured():
        return True
    return ADMIN_PASSWORD == password
