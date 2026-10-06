"""Small dependency-free password and signed token helpers."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return "pbkdf2_sha256$310000$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode(), base64.urlsafe_b64encode(digest).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, expected = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured in the environment")
    return secret.encode()


def create_access_token(user: User) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": str(user.id), "exp": int(time.time()) + 3600}).encode()).rstrip(b"=").decode()
    unsigned = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(hmac.new(_secret(), unsigned.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{unsigned}.{signature}"


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status_code=401, detail="Valid bearer token required", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        header, payload, signature = credentials.credentials.split(".")
        unsigned = f"{header}.{payload}"
        expected = base64.urlsafe_b64encode(hmac.new(_secret(), unsigned.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(signature, expected):
            raise unauthorized
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data["exp"] < time.time():
            raise unauthorized
        user = db.get(User, int(data["sub"]))
        if user is None or not user.is_active:
            raise unauthorized
        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise unauthorized


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user
