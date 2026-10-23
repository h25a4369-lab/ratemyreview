"""Project settings.

Everything here can be changed with environment variables, so no secret has to
live inside the source code. A local ``.env`` file is optional (see .env.example).
"""
from __future__ import annotations

import os
from pathlib import Path

# The project root folder (the folder that contains app/, templates/, static/).
BASE_DIR = Path(__file__).resolve().parent.parent

# Optional .env support: copy .env.example to .env to override settings.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:      # python-dotenv is optional
    pass

# SQLite file. Kept in the project root so it survives a restart.
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "rate_my_review.db")))

# Used to sign the session cookie. CHANGE THIS before putting the site online.
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-only-secret-key-please-change-me-in-production-9f2b7c",
)

# Session lifetime in seconds (7 days).
SESSION_MAX_AGE = 60 * 60 * 24 * 7

# Set to False when the site is served over HTTPS.
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

SITE_NAME = "Rate My Review"
SITE_TAGLINE = "Discover places. Share your experience."
