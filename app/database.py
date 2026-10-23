"""SQLite database: schema, connections and small query helpers.

A new connection is opened for each request and closed when the request ends.
That keeps the code easy to follow and avoids sharing a connection between
threads. Foreign keys are switched on for every connection so the
relationships between users, places, reviews and reports are enforced.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .config import DB_PATH
from .locations import infer_country_state

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user'
                          CHECK (role IN ('user', 'admin')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS places (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    country     TEXT    NOT NULL DEFAULT '',
    state       TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    place_id   INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT    NOT NULL CHECK (length(trim(comment)) > 0),
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT,
    UNIQUE (user_id, place_id)          -- one review per person per place
);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id   INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    reporter_id INTEGER NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    reason      TEXT    NOT NULL CHECK (length(trim(reason)) > 0),
    status      TEXT    NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'resolved', 'dismissed')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (review_id, reporter_id)     -- one report per person per review
);

CREATE INDEX IF NOT EXISTS idx_places_name     ON places(name);
CREATE INDEX IF NOT EXISTS idx_places_location ON places(location);
CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
CREATE INDEX IF NOT EXISTS idx_reviews_place   ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user    ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_review  ON reports(review_id);
CREATE INDEX IF NOT EXISTS idx_reports_status  ON reports(status);
"""


def connect() -> sqlite3.Connection:
    """Open a connection with rows that behave like dictionaries."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI dependency: one connection per request, always closed."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the tables, upgrade older databases, then add the indexes."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _migrate_places(conn)
        conn.executescript(PLACE_INDEXES)
        conn.commit()
    finally:
        conn.close()


# Indexes that touch the country/state columns are created after the migration,
# because older databases only gain those columns during the upgrade.
PLACE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_places_country  ON places(country);
CREATE INDEX IF NOT EXISTS idx_places_state    ON places(state);
"""


def _migrate_places(conn: sqlite3.Connection) -> None:
    """Add country/state to databases created before those columns existed."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(places)")}
    changed = False

    if "country" not in columns:
        conn.execute("ALTER TABLE places ADD COLUMN country TEXT NOT NULL DEFAULT ''")
        changed = True
    if "state" not in columns:
        conn.execute("ALTER TABLE places ADD COLUMN state TEXT NOT NULL DEFAULT ''")
        changed = True
    if changed:
        conn.commit()

    _backfill_country_state(conn)


def _backfill_country_state(conn: sqlite3.Connection) -> None:
    """Fill blank country/state values from each place's address text."""
    rows = conn.execute(
        "SELECT id, location FROM places WHERE country = '' OR state = ''"
    ).fetchall()
    if not rows:
        return

    for row in rows:
        country, state = infer_country_state(row["location"])
        if country or state:
            conn.execute(
                "UPDATE places SET country = ?, state = ? WHERE id = ?",
                (country, state, row["id"]),
            )
    conn.commit()


def fetch_all(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]


def fetch_one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> dict | None:
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def execute(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    """Run a write statement, commit it and return the new row id."""
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return int(cur.lastrowid or 0)
