# Rate My Review

A complete place-review website built for a university project demonstration.
Visitors browse and search places, registered users rate and review them, and
administrators manage places, users, reviews and reports.

Built with **Python FastAPI + SQLite + server-rendered HTML, CSS and JavaScript**.
No paid services, no AI, no external integrations — the whole site runs on your
laptop.

---

## 1. Quick start

Requirements: **Python 3.10+** (3.12 recommended) and a terminal.

### Windows (easiest)

Double-click **`run.bat`**. It creates the virtual environment, installs the
dependencies, loads the sample data and starts the server.

### Windows (manual)

```bat
cd "C:\Users\User\Desktop\rate-my-review"
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### macOS / Linux

```bash
cd path/to/rate-my-review
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

The SQLite database (`rate_my_review.db`) is created automatically on first
start, together with the sample places and reviews. Data survives a restart
because it lives in that file.

To stop the server press **Ctrl+C**.

### Short links

Filter URLs are long to type, so the site also answers to short ones:

| Short link | Opens |
|---|---|
| `/s/kl` | Kuala Lumpur places, busiest reviews first (6 results) |
| `/s/klcc` | Places located in KLCC (2 results) |
| `/s/food` | Malaysian restaurants (2 results) |
| `/s/klcc-food` | The full KLCC + Restaurant + Kuala Lumpur filter (0 results — no sample place matches every filter) |

Add or change codes in the `SHORT_LINKS` dictionary at the top of section 3 in
`app/main.py`; each code is redirected with a `307`, so the visitor ends up on
the real URL and can copy or bookmark it.

### Share it online with GitHub Codespaces

The project includes a `.devcontainer` setup, so GitHub can run it in the cloud
and give you a public link — useful when the marker cannot open `127.0.0.1`.

```bash
git init
git add .
git commit -m "Rate My Review"
git branch -M main
git remote add origin https://github.com/<your-username>/rate-my-review.git
git push -u origin main
```

Then on GitHub: **Code → Codespaces → Create codespace on main**. Wait for it to
install the dependencies, and the site starts on port 8000 automatically
(the sample data is re-seeded because `*.db` is not committed).

Finally, in the Codespace **Ports** tab, right-click port 8000 →
**Port Visibility → Public**, then copy the forwarded address. It looks like:

```
https://<codespace-name>-8000.app.github.dev/places
```

That address works for anybody with the link while the Codespace is running
(Codespaces stop after ~30 minutes of inactivity; open the Codespace again to
restart). Prefer the local `http://127.0.0.1:8000` link when demonstrating on
your own laptop — it is faster and needs no internet.

---

## 2. Demo accounts

These are created automatically with the sample data:

| Role | Email | Password |
|---|---|---|
| Registered user | `demo@ratemyreview.com` | `Password123` |
| Administrator | `admin@ratemyreview.com` | `Admin123!` |
| Sample reviewer | `alice@example.com` | `Password123` |
| Sample reviewer | `ben@example.com` | `Password123` |
| Sample reviewer | `chloe@example.com` | `Password123` |

All sample places are labelled **"Sample place"** in their description, sample
reviews begin with **"Sample review"**, and one sample report is waiting in the
admin queue. You can edit or delete all of it.

---

## 3. What you can do

**Visitor (no account)**
- Search by place name, location, country, state or category from the homepage or Explore Places.
- Filter by country → state, plus category/location, and sort by top rated, most reviewed, newest or name.
- Open a place page to read its description, address, country, state, average rating, rating breakdown and reviews.
- Read About, Contact, Privacy Policy and Terms of Service.

**Registered user**
- Create an account (name, email, password) and log in/out.
- Write one review per place: choose the country, then the state, then the place, and add 1–5 stars + a comment.
- Edit or delete their own reviews at any time; averages update immediately.
- Report another user's review with a reason (spam, abuse, off-topic, private
  information, other). Reporting never deletes the review.
- See all their own reviews on **My Reviews**.

**Administrator**
- Dashboard with place/review/user counts and open reports.
- Add, edit and delete places.
- Moderate all reviews, including deleting inappropriate ones.
- Resolve or dismiss reports; the review stays online until a person decides.
- Promote/demote users and delete accounts (with safeguards: you cannot demote
  yourself and there is always at least one administrator).

---

## 4. Project structure

```
rate-my-review/
├─ app/
│  ├─ __init__.py
│  ├─ config.py          settings, database path, secret key (.env support)
│  ├─ database.py        SQLite schema, connections, query helpers
│  ├─ security.py        password hashing, CSRF tokens, role checks
│  ├─ locations.py       country/state inference and dropdown data
│  ├─ seed.py            sample users, places, reviews, report  (+ CLI reset)
│  └─ main.py            all routes and page rendering
├─ templates/            Jinja2 templates (shared layout + one file per page)
│  ├─ base.html          header, navigation, footer
│  ├─ index.html         homepage
│  ├─ places.html        search / browse results
│  ├─ place_detail.html  place page with reviews and rating summary
│  ├─ review_form.html   write and edit review form
│  ├─ my_reviews.html
│  ├─ login.html, register.html, error.html
│  ├─ partials/          stars, flash messages, place card
│  ├─ pages/             about, contact, privacy, terms
│  └─ admin/             dashboard, places, place form, reviews, reports, users
├─ static/
│  ├─ css/style.css      the complete design system and responsive layout
│  └─ js/main.js         mobile menu, star picker hint, counters, confirmations
├─ tests/
│  ├─ conftest.py        temporary database + test helpers
│  └─ test_app.py        43 end-to-end tests
├─ requirements.txt
├─ run.bat / run.sh      one-step start scripts
└─ .env.example          optional configuration template
```

---

## 5. Database

Four tables with real foreign keys (`PRAGMA foreign_keys = ON`):

```
users ──< reviews >── places
  │           │
  └──< reports ┘
```

| Table | Columns |
|---|---|
| `users` | `id` PK, `name`, `email` (unique, case-insensitive), `password_hash`, `role` (`user`/`admin`), `created_at` |
| `places` | `id` PK, `name`, `country`, `state`, `location`, `category`, `description`, `created_at` |
| `reviews` | `id` PK, `user_id` → users, `place_id` → places, `rating` 1–5 (CHECK), `comment` (CHECK not empty), `created_at`, `updated_at`, **UNIQUE (user_id, place_id)** |
| `reports` | `id` PK, `review_id` → reviews, `reporter_id` → users, `reason`, `status` (`open`/`resolved`/`dismissed`), `created_at`, **UNIQUE (review_id, reporter_id)** |

Deleting a user or place cascades to its reviews and reports. Indexes cover
place name, country, state, location and category, plus the review/report lookups.

**Where country and state live**

A place stores its own `country` and `state`, next to its street address. A
review points at a place, so the review inherits its country/state from that
place — there is one copy of the location data, and it cannot disagree with
itself. The write-review form walks Country → State → Place, and every review,
place page and search result displays the same values.

Databases created before these columns existed are upgraded automatically at
startup: `init_db()` adds the columns and fills them from each place's address.

**How the average is calculated**

```sql
SELECT COALESCE(ROUND(AVG(rating), 2), 0) AS avg_rating,
       COUNT(*) AS review_count
FROM reviews WHERE place_id = ?
```

The place page shows the average to one decimal place (4.67 → 4.7) and a
per-star breakdown. A place with no reviews shows **"No reviews yet."** and no
average. One review per person per place keeps the average honest; a second
attempt is redirected to editing the existing review.

---

## 6. Validation and security

| Area | What is done |
|---|---|
| Passwords | PBKDF2-HMAC-SHA256, 260,000 iterations, 16-byte random salt per password, stored as `pbkdf2_sha256$iterations$salt$hash`. Compared with `hmac.compare_digest`. Plain passwords are never stored or logged. |
| Registration | Required fields, name length, email regex, password ≥ 8 characters, password confirmation, duplicate email rejected (case-insensitive, also enforced by a UNIQUE index). |
| Login | Wrong password and unknown email return the *same* message; a dummy hash is verified for unknown emails so timing does not reveal which accounts exist. The session is cleared and re-created on login. |
| Roles | `require_user` / `require_admin` on every protected route; guests are redirected to login with a `next` return path; non-admins get a 403 page. |
| Ownership | Edit and delete check `review.user_id == current_user.id` (administrators may also remove reviews). |
| Ratings | Whole numbers 1–5 validated on the server (`validate_review`) *and* by a database CHECK constraint; the form also uses `required` radio inputs. |
| Reviews | Place must exist; comment required, 5–1000 characters; one review per user per place enforced by the schema. |
| Places | Administrator form requires name, country, state/region, address and a category; lengths validated on the server (country ≤ 60, state ≤ 80, description ≤ 2000). |
| Reports | Login required, review must exist, reason must be one of the fixed list, duplicates blocked by a UNIQUE index. A report never changes or deletes the review. |
| CSRF | Every POST form carries a signed per-session token checked with `compare_digest`. Missing/expired tokens get a friendly 400 page. |
| SQL injection | Every query uses parameter placeholders (`?`); the sort option is a whitelist, never raw SQL from the request. |
| XSS | Jinja2 auto-escaping is on for all templates; no user text is rendered as HTML. |
| Privacy | Public pages show abbreviated author names ("Alice M."), never email addresses or hashes. Errors never include passwords. |
| Sessions | Signed, `HttpOnly`, `SameSite=Lax` cookie (set `SESSION_HTTPS_ONLY=true` behind HTTPS). |

---

## 7. Tests

```bash
.venv\Scripts\python.exe -m pytest -q      # Windows
./.venv/bin/python -m pytest -q            # macOS / Linux
```

The suite creates its own temporary database (it never touches your real data)
and exercises the site through FastAPI's test client:

- homepage content, search by name/location/category, no-results message, 404s
- registration, duplicate email, invalid email, short password, login/logout
- guest protection, review submission, out-of-range ratings, empty comments
- average calculation, empty states, reviews scoped to the right place
- editing/deleting own reviews, blocked from other users' reviews
- reporting, missing reasons, duplicate reports, admin resolution
- admin place CRUD, admin deletion of reviews, role protection
- CSRF rejection, no emails or hashes on public pages

Latest run: **46 passed**.

---

## 8. Managing content

**Through the site (recommended):** log in as the administrator and open
**Admin → Places → Add a place**. Everything is validated and appears on the
public site immediately.

**Sample data**

The seed file contains 26 sample places and 90 sample reviews, covering every
category: Restaurant, Cafe, Hotel, Attraction, Shopping, Park, Museum and Other.
Sixteen of the places are Malaysian, with two in every category — Kota Bharu,
Kuala Terengganu, George Town, Ipoh, Melaka, Kuala Lumpur, Gombak and Kota
Kinabalu. Examples: Nasi Kerabu Kak Wani, Warung Nasi Dagang Kak Pah, Ah Seng
Kopitiam, Petronas Twin Towers, Batu Caves, Jonker Street Night Market, Baba &
Nyonya Heritage Museum and Kota Kinabalu Waterfront. Malaysian places carry three
to five reviews each, written by eight sample reviewers (Alice, Ben, Chloe, Demo,
Nurul, Aiman, Mei Ling and Raj). Two places are deliberately left without reviews
so the "No reviews yet" empty state can be demonstrated.

**.venv\Scripts\python.exe -m app.seed --add**

Adds only the sample places and reviews that are missing — useful after updating
this project, because it never deletes or overwrites your own accounts, reviews
or reports. Safe to run more than once.

**Reset the sample data (deletes everything):**

```bash
.venv\Scripts\python.exe -m app.seed --reset
```

This deletes all tables and reloads the sample users, places and reviews.
Run without arguments to insert sample data only when the database is empty.

**Backup:** the whole database is the single file `rate_my_review.db`. Copy it
to back up, replace it to restore.

---

## 9. Configuration

Copy `.env.example` to `.env` if you want to change defaults:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev key in `config.py` | Signs the session cookie — **change before deploying** |
| `DATABASE_PATH` | `rate_my_review.db` | Location of the SQLite file |
| `SESSION_HTTPS_ONLY` | `false` | Set `true` when served over HTTPS |

---

## 10. Design notes

- White background with blue (`#2563eb`) and purple (`#7c3aed`) accents, a
  gradient logo mark, rounded cards and consistent 16–22px radii.
- Typography: Inter / system UI stack, with `clamp()` based headings so text
  scales smoothly instead of jumping between breakpoints.
- Layout: 1160px container, CSS grid card layouts, sticky header, sticky rating
  sidebar on desktop, single-column stacking on tablets and phones.
- Accessibility: skip link, visible focus rings, labelled inputs, `aria-live`
  flash messages, `aria-label`ed star ratings, keyboard-operable controls,
  `prefers-reduced-motion` support.
- No JavaScript is required for any feature: the star picker is CSS-only and
  report forms use `<details>`. `main.js` only adds conveniences (mobile menu,
  character counter, confirm dialogs, auto-dismissing messages).

---

## 11. Troubleshooting

**`py` is not recognised (Windows)** — install Python 3.12 from python.org and
tick "Add python.exe to PATH", or replace `py -3.12` with `python`.

**Port 8000 already in use** — run
`uvicorn app.main:app --reload --port 8001` and open that port.

**`ModuleNotFoundError: fastapi`** — the virtual environment is not active.
Use `.venv\Scripts\python.exe -m uvicorn ...` directly (as the run scripts do)
or activate the environment first.

**I want a clean demo** — stop the server, delete `rate_my_review.db`, start it
again; the sample data is recreated automatically.

**Styles look stale** — hard-refresh the browser with Ctrl+F5.
