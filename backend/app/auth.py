import os

ADMIN_PASSWORD: str | None = os.environ.get("ADMIN_PASSWORD")


def is_auth_configured() -> bool:
    return ADMIN_PASSWORD is not None


def check_password(password: str) -> bool:
    if not is_auth_configured():
        return True
    return ADMIN_PASSWORD == password
