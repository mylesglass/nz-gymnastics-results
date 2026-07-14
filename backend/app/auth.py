import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def _admin_password() -> str | None:
    pw = os.environ.get("ADMIN_PASSWORD")
    if pw == "":
        return None
    return pw


def is_auth_configured() -> bool:
    return _admin_password() is not None


def check_password(password: str) -> bool:
    pw = _admin_password()
    if pw is None:
        return True
    return pw == password
