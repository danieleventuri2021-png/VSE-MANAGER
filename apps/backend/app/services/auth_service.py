from __future__ import annotations

import base64
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Utente


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000

# Rate-limiting login: blocco temporaneo dopo troppi tentativi falliti (protezione brute-force in LAN).
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_login_lock = threading.Lock()


def check_login_rate_limit(key: str) -> int | None:
    """Restituisce i secondi di attesa se l'utente/IP e' bloccato, altrimenti None."""
    now = time.monotonic()
    with _login_lock:
        attempts = _login_attempts[key]
        while attempts and now - attempts[0] > LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_MAX_ATTEMPTS:
            return int(LOGIN_WINDOW_SECONDS - (now - attempts[0])) + 1
        if not attempts:
            _login_attempts.pop(key, None)
    return None


def register_failed_login(key: str) -> None:
    with _login_lock:
        _login_attempts[key].append(time.monotonic())


def reset_login_attempts(key: str) -> None:
    with _login_lock:
        _login_attempts.pop(key, None)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def authenticate_user(db: Session, username: str, password: str) -> Utente | None:
    user = db.query(Utente).filter(Utente.username == username, Utente.attivo.is_(True)).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: Utente) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.auth_token_expire_minutes)
    payload = {
        "sub": user.username,
        "uid": user.id,
        "role": user.ruolo,
        "exp": int(expires_at.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body, settings.auth_secret_key)
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        raise _credentials_error()
    expected = _sign(body, settings.auth_secret_key)
    if not hmac.compare_digest(signature, expected):
        raise _credentials_error()
    try:
        payload = json.loads(_unb64(body).decode("utf-8"))
    except Exception:
        raise _credentials_error()
    if int(payload.get("exp") or 0) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione scaduta")
    return payload


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Utente:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _credentials_error()
    payload = decode_access_token(token)
    user = db.get(Utente, int(payload.get("uid") or 0))
    if not user or not user.attivo:
        raise _credentials_error()
    return user


def ensure_default_admin(db: Session) -> None:
    if db.query(Utente).count() > 0:
        return
    settings = get_settings()
    username = settings.admin_username.strip() or "admin"
    password = settings.admin_password or secrets.token_urlsafe(16)
    db.add(Utente(username=username, password_hash=hash_password(password), nome="Amministratore", ruolo="admin", attivo=True))
    db.commit()


def _sign(body: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenziali non valide",
        headers={"WWW-Authenticate": "Bearer"},
    )
