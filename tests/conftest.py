"""Shared pytest setup.

The temporary database path must be set *before* app.config is imported, so the
whole test run uses a throw-away SQLite file instead of the real one.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="rmr-tests-"))
os.environ["DATABASE_PATH"] = str(TMP_DIR / "test.db")
os.environ["SECRET_KEY"] = "test-secret-key-not-used-in-production"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import connect  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import reset_database  # noqa: E402

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')

SAMPLE_PASSWORD = "Password123"


@pytest.fixture()
def client():
    """A fresh database + fresh browser session for every test."""
    reset_database()
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Helpers used by the tests
# --------------------------------------------------------------------------
def get_csrf(client: TestClient, path: str = "/") -> str:
    response = client.get(path)
    match = CSRF_RE.search(response.text)
    assert match, f"No CSRF token found on {path}"
    return match.group(1)


def register(
    client: TestClient,
    name: str = "Test User",
    email: str = "test@example.com",
    password: str = SAMPLE_PASSWORD,
    confirm: str | None = None,
):
    token = get_csrf(client, "/register")
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password if confirm is None else confirm,
            "csrf_token": token,
        },
    )


def login(client: TestClient, email: str, password: str = SAMPLE_PASSWORD):
    token = get_csrf(client, "/login")
    return client.post(
        "/login",
        data={"email": email, "password": password, "next": "", "csrf_token": token},
    )


def logout(client: TestClient):
    token = get_csrf(client, "/")
    return client.post("/logout", data={"csrf_token": token})


def place_id(name: str) -> int:
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM places WHERE name = ?", (name,)).fetchone()
        assert row, f"Sample place missing: {name}"
        return row["id"]
    finally:
        conn.close()


def review_count(place: int) -> int:
    conn = connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE place_id = ?", (place,)
        ).fetchone()["n"]
    finally:
        conn.close()


def submit_review(client: TestClient, place: int, rating, comment: str, token: str | None = None):
    if token is None:
        token = get_csrf(client, f"/write-review?place_id={place}")
    return client.post(
        "/reviews",
        data={
            "place_id": str(place),
            "rating": str(rating),
            "comment": comment,
            "csrf_token": token,
        },
    )
