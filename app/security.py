"""Passwords, form protection and access rules.

Passwords are hashed with PBKDF2-HMAC-SHA256 from Python's standard library,
so no extra dependency is needed. Every hash gets its own random salt:

    pbkdf2_sha256$260000$<salt hex>$<hash hex>

Two extra protections are included:

* CSRF tokens on every form, so another website cannot submit forms as a
  signed-in user.
* Login-required / admin-required helpers that redirect or refuse politely.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from urllib.parse import quote

from fastapi import HTTPException, Request

PBKDF2_ITERATIONS = 260_000
PBKDF2_ALGORITHM = "sha256"
SALT_BYTES = 16

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

REPORT_REASONS = {
    "spam": "Spam or advertising",
    "abusive": "Abusive or hateful language",
    "off-topic": "Not about this place",
    "personal": "Shares private information",
    "other": "Something else",
}


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return a salted, slow hash that is safe to store in the database."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Compare a typed password with the stored hash in constant time."""
    try:
        scheme, iterations, salt_hex, hash_hex = stored.split("$")
        if not scheme.startswith("pbkdf2_"):
            return False
        algorithm = scheme.split("_", 1)[1]
        digest = hashlib.pbkdf2_hmac(
            algorithm,
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


# --------------------------------------------------------------------------
# CSRF protection
# --------------------------------------------------------------------------
def get_csrf_token(request: Request) -> str:
    """Return the visitor's CSRF token, creating one on first use."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def check_csrf(request: Request, token: str | None) -> None:
    """Reject the request when the hidden form token is missing or wrong."""
    expected = request.session.get("csrf_token")
    if not expected or not token or not hmac.compare_digest(str(expected), str(token)):
        raise HTTPException(
            status_code=400,
            detail="This form expired or was not sent from this website. Please try again.",
        )


# --------------------------------------------------------------------------
# Access rules
# --------------------------------------------------------------------------
class LoginRequired(Exception):
    """Raised when a page needs a signed-in user; handled with a redirect."""

    def __init__(self, next_url: str = "/"):
        self.next_url = next_url


def require_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        raise LoginRequired(target)
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="This page is only available to administrators.",
        )
    return user


def safe_next(target: str | None, fallback: str = "/") -> str:
    """Only allow relative, same-site redirects (no open redirects)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback


def login_redirect(url_path: str) -> str:
    return f"/login?next={quote(url_path)}"
