import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def _is_auth_enabled() -> bool:
    pw = os.environ.get("ADMIN_PASSWORD")
    return bool(pw)


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    secret_path = Path(__file__).resolve().parent.parent / "data" / "jwt_secret.txt"
    if secret_path.exists():
        return secret_path.read_text().strip()
    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text(secret)
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def seed_admin_user() -> str | None:
    from app.database import get_session
    from app.models import User

    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        return None
    username = os.environ.get("ADMIN_USERNAME", "admin")
    session = get_session()
    try:
        hashed = hash_password(password)
        admin = session.query(User).filter(User.role == "admin").first()
        if admin:
            admin.hashed_password = hashed
            if admin.username != username:
                admin.username = username
        else:
            user = User(username=username, hashed_password=hashed, role="admin")
            session.add(user)
        session.commit()
        return username
    finally:
        session.close()


async def get_current_user(
    authorization: str | None = Header(None),
) -> dict:
    if not _is_auth_enabled():
        return {"username": "dev", "role": "admin"}
    if not authorization:
        raise HTTPException(401, "Not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Invalid authorization scheme")
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    return {"username": payload["sub"], "role": payload["role"]}


def is_auth_configured() -> bool:
    return _is_auth_enabled()


def require_role(*roles: str):
    """FastAPI dependency: require authenticated user with one of the given roles."""

    async def _dependency(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user

    return _dependency
