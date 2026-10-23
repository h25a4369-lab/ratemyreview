"""Rate My Review — routes and page rendering.

Structure of this file:
  1. App setup (templates, filters, middleware, startup)
  2. Small helpers
  3. Public pages: home, browse/search, place details, info pages
  4. Accounts: register, login, logout
  5. Reviews: write, edit, delete
  6. Reports
  7. Administrator pages
  8. Error handlers
"""
from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import (
    DB_PATH,
    SECRET_KEY,
    SESSION_HTTPS_ONLY,
    SESSION_MAX_AGE,
    SITE_NAME,
    SITE_TAGLINE,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from .database import connect, execute, fetch_all, fetch_one, get_db, init_db
from .locations import COUNTRIES, MALAYSIA_STATES, UK_NATIONS
from .security import (
    REPORT_REASONS,
    LoginRequired,
    check_csrf,
    get_csrf_token,
    hash_password,
    is_valid_email,
    login_redirect,
    require_admin,
    require_user,
    safe_next,
    verify_password,
)
from .seed import seed_database

CATEGORIES = [
    "Restaurant", "Cafe", "Hotel", "Attraction",
    "Shopping", "Park", "Museum", "Other",
]
CATEGORY_ICONS = {
    "Restaurant": "🍽️", "Cafe": "☕", "Hotel": "🏨", "Attraction": "🎡",
    "Shopping": "🛍️", "Park": "🌳", "Museum": "🏛️", "Other": "📍",
}
REVIEW_SORTS = {
    "newest": "r.created_at DESC",
    "oldest": "r.created_at ASC",
    "highest": "r.rating DESC, r.created_at DESC",
    "lowest": "r.rating ASC, r.created_at DESC",
}


# ==========================================================================
# 1. App setup
# ==========================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the tables and load sample data before the first request."""
    init_db()
    seed_database()
    yield


app = FastAPI(title=SITE_NAME, description=SITE_TAGLINE, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def load_current_user(request: Request, call_next):
    """Put the signed-in user, a CSRF token and any flash messages on state."""
    request.state.user = None
    request.state.flashes = request.session.pop("flashes", [])

    user_id = request.session.get("user_id")
    if user_id:
        conn = connect()
        try:
            row = fetch_one(
                conn,
                "SELECT id, name, email, role, created_at FROM users WHERE id = ?",
                (user_id,),
            )
        finally:
            conn.close()
        if row:
            request.state.user = row
        else:                       # account was deleted while logged in
            request.session.pop("user_id", None)

    request.state.csrf_token = get_csrf_token(request)
    return await call_next(request)


# Added after load_current_user so it runs first and provides request.session.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="rmr_session",
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _datefmt(value: str | None, fmt: str = "%d %b %Y") -> str:
    """Turn a stored timestamp into something friendly to read."""
    if not value:
        return ""
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:19], pattern).strftime(fmt)
        except ValueError:
            continue
    return str(value)


def _short_name(name: str | None) -> str:
    """Public display name: first name plus the initial of the last name."""
    parts = (name or "").strip().split()
    if not parts:
        return "Guest"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def _stars_label(rating: float | None) -> str:
    return f"{rating:.1f}" if rating else "No rating"


templates.env.filters["datefmt"] = _datefmt
templates.env.filters["short_name"] = _short_name
templates.env.filters["stars_label"] = _stars_label
templates.env.globals.update(
    SITE_NAME=SITE_NAME,
    SITE_TAGLINE=SITE_TAGLINE,
    CATEGORIES=CATEGORIES,
    CATEGORY_ICONS=CATEGORY_ICONS,
    REPORT_REASONS=REPORT_REASONS,
    COUNTRIES=COUNTRIES,
    MALAYSIA_STATES=MALAYSIA_STATES,
    UK_NATIONS=UK_NATIONS,
    current_year=datetime.now().year,
)


# ==========================================================================
# 2. Small helpers
# ==========================================================================
def flash(request: Request, message: str, kind: str = "success") -> None:
    """Queue a one-time message shown on the next page."""
    messages = request.session.get("flashes", [])
    messages.append({"message": message, "kind": kind})
    request.session["flashes"] = messages


def render(request: Request, template: str, status_code: int = 200, **context):
    context.setdefault("user", getattr(request.state, "user", None))
    context.setdefault("csrf_token", getattr(request.state, "csrf_token", ""))
    context.setdefault("flashes", getattr(request.state, "flashes", []))
    context.setdefault("current_path", request.url.path)
    context.setdefault("query", request.query_params.get("q", ""))
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


PLACE_SELECT = """
SELECT p.id, p.name, p.country, p.state, p.location, p.category, p.description,
       p.created_at,
       COALESCE(ROUND(AVG(r.rating), 2), 0) AS avg_rating,
       COUNT(r.id) AS review_count
FROM places p
LEFT JOIN reviews r ON r.place_id = p.id
"""


def place_filter_options(conn) -> tuple[list[str], list[dict]]:
    """Countries and (country, state) pairs that actually exist in the data."""
    countries = [
        row["country"]
        for row in fetch_all(
            conn,
            "SELECT DISTINCT country FROM places"
            " WHERE country <> '' ORDER BY country COLLATE NOCASE",
        )
    ]
    states = fetch_all(
        conn,
        "SELECT DISTINCT country, state FROM places"
        " WHERE state <> '' ORDER BY country COLLATE NOCASE, state COLLATE NOCASE",
    )
    return countries, states


def get_place(conn, place_id: int) -> dict | None:
    return fetch_one(
        conn, PLACE_SELECT + " WHERE p.id = ? GROUP BY p.id", (place_id,)
    )


def get_place_lists(conn) -> list[dict]:
    """All places with their rating summary, for the 'choose a place' select."""
    return fetch_all(conn, PLACE_SELECT + " GROUP BY p.id ORDER BY p.name COLLATE NOCASE")


def overall_stats(conn) -> dict:
    row = fetch_one(
        conn,
        """
        SELECT (SELECT COUNT(*) FROM places)  AS places,
               (SELECT COUNT(*) FROM reviews) AS reviews,
               (SELECT COUNT(*) FROM users WHERE role = 'user') AS users,
               (SELECT ROUND(AVG(rating), 1) FROM reviews) AS avg_rating
        """,
    )
    return row or {"places": 0, "reviews": 0, "users": 0, "avg_rating": None}


def validate_review(rating_raw, comment_raw) -> tuple[int, str, list[str]]:
    """Server-side validation for a review. Returns (rating, comment, errors)."""
    errors: list[str] = []

    try:
        rating = int(str(rating_raw).strip())
    except (TypeError, ValueError):
        rating = 0
    if rating < 1 or rating > 5:
        errors.append("Please choose a star rating between 1 and 5.")

    comment = (comment_raw or "").strip()
    if not comment:
        errors.append("Please write a comment about your experience.")
    elif len(comment) < 5:
        errors.append("Your comment is too short — please write at least 5 characters.")
    elif len(comment) > 1000:
        errors.append("Your comment is too long — please keep it under 1000 characters.")

    return rating, comment, errors


# ==========================================================================
# 3. Public pages
# ==========================================================================
# Short links: friendly one-word URLs for demos, QR codes and sharing.
# Add a code here (lowercase, dashes allowed) and point it at any site path.
SHORT_LINKS: dict[str, str] = {
    "all": "/places?sort=reviews",
    "kl": "/places?q=kuala+lumpur&country=Malaysia&state=Kuala+Lumpur&sort=reviews",
    "klcc": "/places?location=KLCC&country=Malaysia&state=Kuala+Lumpur&sort=reviews",
    "klcc-food": (
        "/places?q=kuala+lumpur&location=KLCC&country=Malaysia"
        "&state=Kuala+Lumpur&category=Restaurant&sort=reviews"
    ),
    "food": "/places?country=Malaysia&category=Restaurant&sort=reviews",
}


@app.get("/s/{code}")
def short_link(code: str):
    """Send /s/<code> to the long filtered URL the code stands for."""
    target = SHORT_LINKS.get(code.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail="Unknown short link.")
    return RedirectResponse(target, status_code=307)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db=Depends(get_db)):
    popular = fetch_all(
        db,
        PLACE_SELECT
        + """
        GROUP BY p.id
        ORDER BY (COUNT(r.id) = 0) ASC, avg_rating DESC, COUNT(r.id) DESC, p.name
        LIMIT 6
        """,
    )
    recent_reviews = fetch_all(
        db,
        """
        SELECT r.id, r.rating, r.comment, r.created_at,
               u.name AS author_name,
               p.id AS place_id, p.name AS place_name, p.location AS place_location,
               p.category AS place_category
        FROM reviews r
        JOIN users  u ON u.id = r.user_id
        JOIN places p ON p.id = r.place_id
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT 4
        """,
    )
    category_counts = {
        row["category"]: row["n"]
        for row in fetch_all(
            db, "SELECT category, COUNT(*) AS n FROM places GROUP BY category"
        )
    }
    countries, _ = place_filter_options(db)
    return render(
        request,
        "index.html",
        popular=popular,
        recent_reviews=recent_reviews,
        stats=overall_stats(db),
        category_counts=category_counts,
        countries=countries,
    )


@app.get("/places", response_class=HTMLResponse)
def browse_places(
    request: Request,
    q: str = "",
    location: str = "",
    country: str = "",
    state: str = "",
    category: str = "",
    sort: str = "top",
    db=Depends(get_db),
):
    q = (q or "").strip()[:80]
    location = (location or "").strip()[:80]
    country = (country or "").strip()[:60]
    state = (state or "").strip()[:60]
    category = (category or "").strip()

    sql = PLACE_SELECT + " WHERE 1 = 1"
    params: list[str] = []

    if q:
        like = f"%{q}%"
        sql += (
            " AND (p.name LIKE ? OR p.location LIKE ? OR p.country LIKE ?"
            " OR p.state LIKE ? OR p.category LIKE ? OR p.description LIKE ?)"
        )
        params += [like, like, like, like, like, like]
    if location:
        sql += " AND p.location LIKE ?"
        params.append(f"%{location}%")
    if country:
        sql += " AND p.country = ?"
        params.append(country)
    if state:
        sql += " AND p.state = ?"
        params.append(state)
    if category:
        sql += " AND p.category = ?"
        params.append(category)

    sql += " GROUP BY p.id"

    order = {
        "top": "(COUNT(r.id) = 0) ASC, avg_rating DESC, COUNT(r.id) DESC, p.name",
        "newest": "p.created_at DESC, p.id DESC",
        "name": "p.name COLLATE NOCASE ASC",
        "reviews": "COUNT(r.id) DESC, avg_rating DESC",
    }.get(sort, "(COUNT(r.id) = 0) ASC, avg_rating DESC, COUNT(r.id) DESC, p.name")
    sql += f" ORDER BY {order}"

    places = fetch_all(db, sql, params)
    total_places = fetch_one(db, "SELECT COUNT(*) AS n FROM places")["n"]
    countries, states = place_filter_options(db)

    return render(
        request,
        "places.html",
        places=places,
        total_places=total_places,
        countries=countries,
        states=states,
        filters={
            "q": q, "location": location, "country": country,
            "state": state, "category": category, "sort": sort,
        },
        result_count=len(places),
    )


@app.get("/places/{place_id}", response_class=HTMLResponse)
def place_detail(
    request: Request,
    place_id: int,
    sort: str = "newest",
    db=Depends(get_db),
):
    place = get_place(db, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="We could not find that place.")

    order = REVIEW_SORTS.get(sort, REVIEW_SORTS["newest"])
    reviews = fetch_all(
        db,
        f"""
        SELECT r.id, r.rating, r.comment, r.created_at, r.updated_at, r.user_id,
               u.name AS author_name,
               (SELECT COUNT(*) FROM reports rp WHERE rp.review_id = r.id) AS report_count
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.place_id = ?
        ORDER BY {order}
        """,
        (place_id,),
    )

    user = getattr(request.state, "user", None)
    my_reported: set[int] = set()
    if user:
        my_reported = {
            row["review_id"]
            for row in fetch_all(
                db, "SELECT review_id FROM reports WHERE reporter_id = ?", (user["id"],)
            )
        }
    for review in reviews:
        review["is_mine"] = bool(user and review["user_id"] == user["id"])
        review["reported_by_me"] = review["id"] in my_reported

    distribution_rows = fetch_all(
        db,
        "SELECT rating, COUNT(*) AS n FROM reviews WHERE place_id = ? GROUP BY rating",
        (place_id,),
    )
    counts = {row["rating"]: row["n"] for row in distribution_rows}
    total = place["review_count"] or 0
    distribution = [
        {
            "star": star,
            "count": counts.get(star, 0),
            "pct": round(counts.get(star, 0) * 100 / total) if total else 0,
        }
        for star in (5, 4, 3, 2, 1)
    ]

    return render(
        request,
        "place_detail.html",
        place=place,
        reviews=reviews,
        distribution=distribution,
        sort=sort if sort in REVIEW_SORTS else "newest",
        my_review=next((r for r in reviews if r["is_mine"]), None),
    )


# --- About / Contact / Privacy / Terms ------------------------------------
@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return render(request, "pages/about.html")


@app.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    return render(request, "pages/contact.html")


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return render(request, "pages/privacy.html")


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return render(request, "pages/terms.html")


# ==========================================================================
# 4. Accounts
# ==========================================================================
@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    if request.state.user:
        return RedirectResponse("/", status_code=303)
    return render(request, "register.html", form={}, errors={})


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    check_csrf(request, csrf_token)

    name = name.strip()
    email = email.strip().lower()
    errors: dict[str, str] = {}

    if len(name) < 2:
        errors["name"] = "Please enter your name (at least 2 characters)."
    elif len(name) > 80:
        errors["name"] = "Your name is too long (80 characters maximum)."
    if not email:
        errors["email"] = "Please enter your email address."
    elif not is_valid_email(email):
        errors["email"] = "That email address does not look valid."
    if len(password) < 8:
        errors["password"] = "Your password must be at least 8 characters long."
    elif len(password) > 128:
        errors["password"] = "Your password is too long (128 characters maximum)."
    if password != confirm_password:
        errors["confirm_password"] = "The two passwords do not match."

    if not errors and fetch_one(db, "SELECT id FROM users WHERE email = ?", (email,)):
        errors["email"] = "An account with that email address already exists."

    if errors:
        return render(
            request,
            "register.html",
            form={"name": name, "email": email},
            errors=errors,
            status_code=400,
        )

    try:
        user_id = execute(
            db,
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'user')",
            (name, email, hash_password(password)),
        )
    except sqlite3.IntegrityError:
        # Two people registered the same email at the same moment.
        errors["email"] = "An account with that email address already exists."
        return render(
            request, "register.html", form={"name": name, "email": email},
            errors=errors, status_code=400,
        )

    request.session.clear()
    request.session["user_id"] = user_id
    request.session["csrf_token"] = get_csrf_token(request)
    flash(request, f"Welcome to {SITE_NAME}, {name.split()[0]}! Your account is ready.", "success")
    return RedirectResponse("/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = ""):
    if request.state.user:
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", form={}, errors={}, next_url=safe_next(next, ""))


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    check_csrf(request, csrf_token)

    email = email.strip().lower()
    errors: dict[str, str] = {}

    if not email:
        errors["email"] = "Please enter your email address."
    if not password:
        errors["password"] = "Please enter your password."

    user = None
    if not errors:
        user = fetch_one(
            db,
            "SELECT id, name, email, role, password_hash FROM users WHERE email = ?",
            (email,),
        )
        # Always run a hash check so a missing account and a wrong password look
        # the same to someone trying to guess which emails exist.
        stored = user["password_hash"] if user else (
            "pbkdf2_sha256$260000$" + "00" * 16 + "$" + "00" * 32
        )
        if not verify_password(password, stored) or not user:
            errors["form"] = "Email or password is incorrect."

    if errors:
        return render(
            request,
            "login.html",
            form={"email": email},
            errors=errors,
            next_url=safe_next(next, ""),
            status_code=400,
        )

    request.session.clear()                 # new session id after login
    request.session["user_id"] = user["id"]
    request.session["csrf_token"] = get_csrf_token(request)
    flash(request, f"Welcome back, {user['name'].split()[0]}!", "success")
    return RedirectResponse(safe_next(next, "/"), status_code=303)


@app.post("/logout")
def logout(request: Request, csrf_token: str = Form("")):
    check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ==========================================================================
# 5. Reviews
# ==========================================================================
@app.get("/write-review", response_class=HTMLResponse)
def write_review_form(request: Request, place_id: str = "", db=Depends(get_db)):
    user = require_user(request)
    places = get_place_lists(db)

    selected = None
    if place_id.isdigit():
        selected = get_place(db, int(place_id))
        if selected and fetch_one(
            db,
            "SELECT id FROM reviews WHERE user_id = ? AND place_id = ?",
            (user["id"], selected["id"]),
        ):
            flash(request, "You have already reviewed this place. You can update that review below.", "info")
            return RedirectResponse(f"/places/{selected['id']}#reviews", status_code=303)

    return render(
        request,
        "review_form.html",
        places=places,
        countries=place_filter_options(db)[0],
        mode="create",
        review=None,
        selected_place_id=selected["id"] if selected else "",
        form={"rating": 0, "comment": ""},
        errors={},
    )


@app.post("/reviews", response_class=HTMLResponse)
def create_review(
    request: Request,
    place_id: str = Form(""),
    rating: str = Form(""),
    comment: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    user = require_user(request)
    check_csrf(request, csrf_token)

    place = get_place(db, int(place_id)) if place_id.isdigit() else None
    if not place:
        raise HTTPException(status_code=404, detail="We could not find that place.")

    rating_value, comment_text, errors = validate_review(rating, comment)
    error_map = {"rating": errors[0]} if errors else {}
    if len(errors) > 1:
        error_map["comment"] = errors[1]

    existing = fetch_one(
        db,
        "SELECT id FROM reviews WHERE user_id = ? AND place_id = ?",
        (user["id"], place["id"]),
    )
    if existing:
        flash(request, "You have already reviewed this place. Edit your review instead.", "info")
        return RedirectResponse(f"/reviews/{existing['id']}/edit", status_code=303)

    if errors:
        return render(
            request,
            "review_form.html",
            places=get_place_lists(db),
            countries=place_filter_options(db)[0],
            mode="create",
            review=None,
            selected_place_id=place["id"],
            form={"rating": rating, "comment": comment},
            errors=error_map,
            status_code=400,
        )

    execute(
        db,
        "INSERT INTO reviews (user_id, place_id, rating, comment) VALUES (?, ?, ?, ?)",
        (user["id"], place["id"], rating_value, comment_text),
    )
    flash(request, "Thank you — your review has been posted.", "success")
    return RedirectResponse(f"/places/{place['id']}#reviews", status_code=303)


@app.get("/reviews/{review_id}/edit", response_class=HTMLResponse)
def edit_review_form(request: Request, review_id: int, db=Depends(get_db)):
    user = require_user(request)
    review = fetch_one(
        db,
        """
        SELECT r.*, p.name AS place_name, p.location AS place_location,
               p.category AS place_category, p.country AS place_country,
               p.state AS place_state
        FROM reviews r JOIN places p ON p.id = r.place_id
        WHERE r.id = ?
        """,
        (review_id,),
    )
    if not review:
        raise HTTPException(status_code=404, detail="That review no longer exists.")
    if review["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only edit your own reviews.")

    return render(
        request,
        "review_form.html",
        places=get_place_lists(db),
        countries=place_filter_options(db)[0],
        mode="edit",
        review=review,
        selected_place_id=review["place_id"],
        form={"rating": review["rating"], "comment": review["comment"]},
        errors={},
    )


@app.post("/reviews/{review_id}/edit", response_class=HTMLResponse)
def update_review(
    request: Request,
    review_id: int,
    rating: str = Form(""),
    comment: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    user = require_user(request)
    check_csrf(request, csrf_token)

    review = fetch_one(db, "SELECT * FROM reviews WHERE id = ?", (review_id,))
    if not review:
        raise HTTPException(status_code=404, detail="That review no longer exists.")
    if review["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only edit your own reviews.")

    place = get_place(db, review["place_id"])
    rating_value, comment_text, errors = validate_review(rating, comment)
    error_map = {"rating": errors[0]} if errors else {}
    if len(errors) > 1:
        error_map["comment"] = errors[1]

    if errors:
        review["place_name"] = place["name"] if place else "Unknown place"
        review["place_location"] = place["location"] if place else ""
        review["place_category"] = place["category"] if place else ""
        review["place_country"] = place["country"] if place else ""
        review["place_state"] = place["state"] if place else ""
        return render(
            request,
            "review_form.html",
            places=get_place_lists(db),
            countries=place_filter_options(db)[0],
            mode="edit",
            review=review,
            selected_place_id=review["place_id"],
            form={"rating": rating, "comment": comment},
            errors=error_map,
            status_code=400,
        )

    execute(
        db,
        "UPDATE reviews SET rating = ?, comment = ?, updated_at = datetime('now')"
        " WHERE id = ?",
        (rating_value, comment_text, review_id),
    )
    flash(request, "Your review has been updated.", "success")
    return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)


@app.post("/reviews/{review_id}/delete")
def delete_review(
    request: Request,
    review_id: int,
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    user = require_user(request)
    check_csrf(request, csrf_token)

    review = fetch_one(db, "SELECT * FROM reviews WHERE id = ?", (review_id,))
    if not review:
        raise HTTPException(status_code=404, detail="That review no longer exists.")
    if review["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own reviews.")

    execute(db, "DELETE FROM reviews WHERE id = ?", (review_id,))
    flash(request, "Your review has been deleted.", "success")

    if user["role"] == "admin" and review["user_id"] != user["id"]:
        return RedirectResponse("/admin/reviews", status_code=303)
    return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)


@app.get("/my-reviews", response_class=HTMLResponse)
def my_reviews(request: Request, db=Depends(get_db)):
    user = require_user(request)
    rows = fetch_all(
        db,
        """
        SELECT r.id, r.rating, r.comment, r.created_at, r.updated_at,
               p.id AS place_id, p.name AS place_name, p.location AS place_location,
               p.category AS place_category, p.country AS place_country,
               p.state AS place_state
        FROM reviews r JOIN places p ON p.id = r.place_id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
        """,
        (user["id"],),
    )
    return render(request, "my_reviews.html", reviews=rows)


# ==========================================================================
# 6. Reports
# ==========================================================================
@app.post("/reviews/{review_id}/report")
def report_review(
    request: Request,
    review_id: int,
    reason: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    user = require_user(request)
    check_csrf(request, csrf_token)

    review = fetch_one(db, "SELECT * FROM reviews WHERE id = ?", (review_id,))
    if not review:
        raise HTTPException(status_code=404, detail="That review no longer exists.")

    reason = (reason or "").strip()
    if reason not in REPORT_REASONS:
        flash(request, "Please choose a reason before sending your report.", "error")
        return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)

    if review["user_id"] == user["id"]:
        flash(request, "You cannot report your own review.", "info")
        return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)

    try:
        execute(
            db,
            "INSERT INTO reports (review_id, reporter_id, reason) VALUES (?, ?, ?)",
            (review_id, user["id"], REPORT_REASONS[reason]),
        )
    except sqlite3.IntegrityError:
        flash(request, "You have already reported this review. Our team will look at it.", "info")
        return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)

    # A report never deletes or hides a review — a human decides later.
    flash(
        request,
        "Thank you. Your report has been sent to our moderators and the review stays online until it is checked.",
        "success",
    )
    return RedirectResponse(f"/places/{review['place_id']}#reviews", status_code=303)


# ==========================================================================
# 7. Administrator pages
# ==========================================================================
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db=Depends(get_db)):
    require_admin(request)
    stats = overall_stats(db)
    open_reports = fetch_one(
        db, "SELECT COUNT(*) AS n FROM reports WHERE status = 'open'"
    )["n"]
    reports = fetch_all(
        db,
        """
        SELECT rp.id, rp.reason, rp.status, rp.created_at,
               r.id AS review_id, r.rating, r.comment,
               p.name AS place_name, p.id AS place_id,
               reporter.name AS reporter_name,
               author.name   AS author_name
        FROM reports rp
        JOIN reviews r ON r.id = rp.review_id
        JOIN places  p ON p.id = r.place_id
        JOIN users   reporter ON reporter.id = rp.reporter_id
        JOIN users   author   ON author.id   = r.user_id
        ORDER BY (rp.status = 'open') DESC, rp.created_at DESC
        LIMIT 6
        """,
    )
    top_places = fetch_all(
        db,
        PLACE_SELECT + """
        GROUP BY p.id
        ORDER BY avg_rating DESC, COUNT(r.id) DESC
        LIMIT 5
        """,
    )
    return render(
        request,
        "admin/dashboard.html",
        stats=stats,
        open_reports=open_reports,
        reports=reports,
        top_places=top_places,
    )


@app.get("/admin/places", response_class=HTMLResponse)
def admin_places(request: Request, db=Depends(get_db)):
    require_admin(request)
    places = fetch_all(db, PLACE_SELECT + " GROUP BY p.id ORDER BY p.name COLLATE NOCASE")
    return render(request, "admin/places.html", places=places)


@app.get("/admin/places/new", response_class=HTMLResponse)
def admin_place_new(request: Request):
    require_admin(request)
    return render(
        request, "admin/place_form.html", mode="create", place={}, errors={}
    )


@app.post("/admin/places/new", response_class=HTMLResponse)
def admin_place_create(
    request: Request,
    name: str = Form(""),
    country: str = Form(""),
    state: str = Form(""),
    location: str = Form(""),
    category: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    values, errors = _validate_place(name, country, state, location, category, description)
    if errors:
        return render(
            request, "admin/place_form.html", mode="create",
            place=values, errors=errors, status_code=400,
        )

    execute(
        db,
        "INSERT INTO places (name, country, state, location, category, description)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (values["name"], values["country"], values["state"], values["location"],
         values["category"], values["description"]),
    )
    flash(request, f"“{values['name']}” was added.", "success")
    return RedirectResponse("/admin/places", status_code=303)


@app.get("/admin/places/{place_id}/edit", response_class=HTMLResponse)
def admin_place_edit_form(request: Request, place_id: int, db=Depends(get_db)):
    require_admin(request)
    place = get_place(db, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="That place no longer exists.")
    return render(request, "admin/place_form.html", mode="edit", place=place, errors={})


@app.post("/admin/places/{place_id}/edit", response_class=HTMLResponse)
def admin_place_update(
    request: Request,
    place_id: int,
    name: str = Form(""),
    country: str = Form(""),
    state: str = Form(""),
    location: str = Form(""),
    category: str = Form(""),
    description: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    existing = fetch_one(db, "SELECT id FROM places WHERE id = ?", (place_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="That place no longer exists.")

    values, errors = _validate_place(name, country, state, location, category, description)
    values["id"] = place_id
    if errors:
        return render(
            request, "admin/place_form.html", mode="edit",
            place=values, errors=errors, status_code=400,
        )

    execute(
        db,
        "UPDATE places SET name = ?, country = ?, state = ?, location = ?,"
        " category = ?, description = ? WHERE id = ?",
        (values["name"], values["country"], values["state"], values["location"],
         values["category"], values["description"], place_id),
    )
    flash(request, f"“{values['name']}” was updated.", "success")
    return RedirectResponse("/admin/places", status_code=303)


@app.post("/admin/places/{place_id}/delete")
def admin_place_delete(
    request: Request,
    place_id: int,
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    place = fetch_one(db, "SELECT name FROM places WHERE id = ?", (place_id,))
    if not place:
        raise HTTPException(status_code=404, detail="That place no longer exists.")
    execute(db, "DELETE FROM places WHERE id = ?", (place_id,))
    flash(
        request,
        f"“{place['name']}” and its reviews were deleted.",
        "success",
    )
    return RedirectResponse("/admin/places", status_code=303)


def _validate_place(name, country, state, location, category, description) -> tuple[dict, dict]:
    values = {
        "name": (name or "").strip(),
        "country": (country or "").strip(),
        "state": (state or "").strip(),
        "location": (location or "").strip(),
        "category": (category or "").strip(),
        "description": (description or "").strip(),
    }
    errors: dict[str, str] = {}
    if len(values["name"]) < 2:
        errors["name"] = "Please enter a place name (at least 2 characters)."
    elif len(values["name"]) > 100:
        errors["name"] = "Place names must be 100 characters or fewer."
    if len(values["country"]) < 2:
        errors["country"] = "Please enter the country."
    elif len(values["country"]) > 60:
        errors["country"] = "Country names must be 60 characters or fewer."
    if len(values["state"]) < 2:
        errors["state"] = "Please enter the state or region."
    elif len(values["state"]) > 80:
        errors["state"] = "State names must be 80 characters or fewer."
    if len(values["location"]) < 2:
        errors["location"] = "Please enter a location."
    if values["category"] not in CATEGORIES:
        errors["category"] = "Please choose a category from the list."
    if len(values["description"]) > 2000:
        errors["description"] = "Please keep the description under 2000 characters."
    return values, errors


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, db=Depends(get_db)):
    require_admin(request)
    users = fetch_all(
        db,
        """
        SELECT u.id, u.name, u.email, u.role, u.created_at,
               (SELECT COUNT(*) FROM reviews r WHERE r.user_id = u.id) AS review_count
        FROM users u
        ORDER BY u.role DESC, u.name COLLATE NOCASE
        """,
    )
    admin_count = sum(1 for u in users if u["role"] == "admin")
    return render(request, "admin/users.html", users=users, admin_count=admin_count)


@app.post("/admin/users/{user_id}/role")
def admin_user_role(
    request: Request,
    user_id: int,
    role: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    admin = require_admin(request)
    check_csrf(request, csrf_token)

    target = fetch_one(db, "SELECT id, name, role FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(status_code=404, detail="That user no longer exists.")
    if role not in ("user", "admin"):
        flash(request, "That is not a valid role.", "error")
        return RedirectResponse("/admin/users", status_code=303)
    if user_id == admin["id"] and role != "admin":
        flash(request, "You cannot remove your own administrator role.", "error")
        return RedirectResponse("/admin/users", status_code=303)
    if target["role"] == "admin" and role == "user":
        remaining = fetch_one(
            db, "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND id != ?", (user_id,)
        )["n"]
        if remaining == 0:
            flash(request, "There must always be at least one administrator.", "error")
            return RedirectResponse("/admin/users", status_code=303)

    execute(db, "UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    flash(request, f"{target['name']} is now {'an administrator' if role == 'admin' else 'a registered user'}.", "success")
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/delete")
def admin_user_delete(
    request: Request,
    user_id: int,
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    admin = require_admin(request)
    check_csrf(request, csrf_token)

    target = fetch_one(db, "SELECT id, name FROM users WHERE id = ?", (user_id,))
    if not target:
        raise HTTPException(status_code=404, detail="That user no longer exists.")
    if user_id == admin["id"]:
        flash(request, "You cannot delete your own account from here.", "error")
        return RedirectResponse("/admin/users", status_code=303)

    execute(db, "DELETE FROM users WHERE id = ?", (user_id,))
    flash(request, f"{target['name']}'s account and reviews were deleted.", "success")
    return RedirectResponse("/admin/users", status_code=303)


@app.get("/admin/reviews", response_class=HTMLResponse)
def admin_reviews(request: Request, db=Depends(get_db)):
    require_admin(request)
    reviews = fetch_all(
        db,
        """
        SELECT r.id, r.rating, r.comment, r.created_at,
               u.name AS author_name, u.id AS author_id,
               p.name AS place_name, p.id AS place_id,
               (SELECT COUNT(*) FROM reports rp WHERE rp.review_id = r.id) AS report_count
        FROM reviews r
        JOIN users  u ON u.id = r.user_id
        JOIN places p ON p.id = r.place_id
        ORDER BY report_count DESC, r.created_at DESC
        """,
    )
    return render(request, "admin/reviews.html", reviews=reviews)


@app.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(request: Request, status: str = "open", db=Depends(get_db)):
    require_admin(request)
    sql = """
        SELECT rp.id, rp.reason, rp.status, rp.created_at,
               r.id AS review_id, r.rating, r.comment,
               p.name AS place_name, p.id AS place_id,
               reporter.name AS reporter_name,
               author.name AS author_name
        FROM reports rp
        JOIN reviews r ON r.id = rp.review_id
        JOIN places  p ON p.id = r.place_id
        JOIN users   reporter ON reporter.id = rp.reporter_id
        JOIN users   author   ON author.id   = r.user_id
    """
    params: list = []
    if status in ("open", "resolved", "dismissed"):
        sql += " WHERE rp.status = ?"
        params.append(status)
    sql += " ORDER BY rp.created_at DESC"

    reports = fetch_all(db, sql, params)
    counts = {
        row["status"]: row["n"]
        for row in fetch_all(
            db, "SELECT status, COUNT(*) AS n FROM reports GROUP BY status"
        )
    }
    return render(
        request,
        "admin/reports.html",
        reports=reports,
        status=status,
        counts=counts,
        total_reports=sum(counts.values()),
    )


@app.post("/admin/reports/{report_id}/status")
def admin_report_status(
    request: Request,
    report_id: int,
    status: str = Form(""),
    csrf_token: str = Form(""),
    db=Depends(get_db),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    report = fetch_one(db, "SELECT id FROM reports WHERE id = ?", (report_id,))
    if not report:
        raise HTTPException(status_code=404, detail="That report no longer exists.")
    if status not in ("open", "resolved", "dismissed"):
        flash(request, "That is not a valid report status.", "error")
        return RedirectResponse("/admin/reports", status_code=303)

    execute(db, "UPDATE reports SET status = ? WHERE id = ?", (status, report_id))
    flash(
        request,
        "Report marked as resolved." if status == "resolved" else "Report dismissed.",
        "success",
    )
    return RedirectResponse("/admin/reports", status_code=303)


# ==========================================================================
# 8. Error handlers
# ==========================================================================
def _error_page(request: Request, code: int, title: str, message: str):
    return render(
        request, "error.html", code=code, title=title, message=message,
        status_code=code,
    )


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    flash(request, "Please log in to continue.", "info")
    return RedirectResponse(login_redirect(exc.next_url), status_code=303)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception(request: Request, exc: StarletteHTTPException):
    messages = {
        400: ("That did not work", "The form could not be processed. Please go back and try again."),
        403: ("Not allowed", "You do not have permission to open this page."),
        404: ("Page not found", "We could not find the page you were looking for."),
    }
    if request.url.path.startswith("/static") or exc.status_code not in messages:
        return await http_exception_handler(request, exc)
    title, fallback = messages[exc.status_code]
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail else fallback
    return _error_page(request, exc.status_code, title, detail)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    return _error_page(
        request, 500, "Something went wrong",
        "An unexpected error occurred. Please try again in a moment.",
    )


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "database": str(Path(DB_PATH).name)})
