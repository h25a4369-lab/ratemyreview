"""Sample data so the site is not empty on the first run.

Every place and review below is clearly labelled as sample data.

Commands
--------
    python -m app.seed           # load sample data if the database is empty
    python -m app.seed --add     # add anything missing, keep existing rows
    python -m app.seed --reset   # delete everything and reload from scratch

``--add`` is safe to re-run: users, places and reviews are matched by their
unique keys, so nothing is duplicated and nothing you created is removed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from .database import connect, execute, fetch_one, init_db
from .locations import infer_country_state
from .security import hash_password

SAMPLE_PASSWORD = "Password123"
ADMIN_EMAIL = "admin@ratemyreview.com"
ADMIN_PASSWORD = "Admin123!"

SAMPLE_USERS = [
    {"name": "Alice Morgan", "email": "alice@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Ben Carter", "email": "ben@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Chloe Daniels", "email": "chloe@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Demo User", "email": "demo@ratemyreview.com", "password": SAMPLE_PASSWORD},
    # Malaysian reviewers — these four write the extra reviews below.
    {"name": "Nurul Aisyah", "email": "nurul@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Aiman Hakim", "email": "aiman@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Mei Ling Tan", "email": "meiling@example.com", "password": SAMPLE_PASSWORD},
    {"name": "Raj Kumar", "email": "raj@example.com", "password": SAMPLE_PASSWORD},
]

# (email, rating, comment, days ago)
SAMPLE_PLACES = [
    {
        "name": "The Blue Fork Bistro",
        "location": "12 Harbour Street, Bristol",
        "category": "Restaurant",
        "description": (
            "Sample place — a friendly neighbourhood bistro serving seasonal British "
            "food, with a small terrace and a good vegetarian menu."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — Lovely little bistro. The mushroom risotto was rich and "
             "the staff made us feel welcome on a busy Friday night.", 2),
            ("ben@example.com", 4,
             "Sample review — Good food and fair prices. Service was a little slow at "
             "the start, but everything arrived hot and tasty.", 6),
            ("chloe@example.com", 5,
             "Sample review — Best Sunday lunch I have had in Bristol. Book ahead, it "
             "fills up quickly.", 12),
        ],
    },
    {
        "name": "Cloud Nine Coffee",
        "location": "4 Market Lane, Bristol",
        "category": "Cafe",
        "description": (
            "Sample place — a small independent coffee shop with a quiet upstairs "
            "seating area, free Wi-Fi and fresh pastries each morning."
        ),
        "reviews": [
            ("ben@example.com", 4,
             "Sample review — Great flat white and plenty of plug sockets. It gets "
             "busy around 9am, so come early if you want a table.", 1),
            ("alice@example.com", 3,
             "Sample review — Coffee was good but the upstairs room was quite noisy "
             "and the pastry selection was limited by the afternoon.", 9),
            ("chloe@example.com", 4,
             "Sample review — My go-to for a quiet morning coffee. The upstairs seats "
             "are the best spot and the banana bread is excellent.", 14),
        ],
    },
    {
        "name": "Riverside Park",
        "location": "River Road, Bath",
        "category": "Park",
        "description": (
            "Sample place — a large riverside park with a playground, a walking loop "
            "and plenty of benches. Free to enter and open all year."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Perfect for an afternoon walk. Clean paths, lots of "
             "ducks and a nice playground for younger children.", 3),
            ("ben@example.com", 4,
             "Sample review — Peaceful and well kept. Would be five stars with a "
             "proper coffee kiosk near the entrance.", 15),
            ("alice@example.com", 5,
             "Sample review — Took the dog for an early walk and had the place almost "
             "to ourselves. Well-kept paths and plenty of bins.", 22),
        ],
    },
    {
        "name": "Harbour View Hotel",
        "location": "1 Quay Parade, Bristol",
        "category": "Hotel",
        "description": (
            "Sample place — a mid-range harbour-side hotel with breakfast included "
            "and rooms facing the water."
        ),
        "reviews": [
            ("alice@example.com", 4,
             "Sample review — Clean room, comfortable bed and a really good breakfast. "
             "The harbour view was worth the extra cost.", 5),
            ("ben@example.com", 3,
             "Sample review — Comfortable bed and a great view, but the walls are thin "
             "and breakfast gets busy after nine.", 11),
            ("chloe@example.com", 5,
             "Sample review — Staff upgraded us to a harbour-facing room without being "
             "asked. Breakfast was fresh and plentiful.", 19),
        ],
    },
    {
        "name": "City Art Museum",
        "location": "8 Civic Square, Bath",
        "category": "Museum",
        "description": (
            "Sample place — a free city museum with local history galleries, a "
            "family activity room and a small gift shop."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Well laid out and free entry. The local history gallery "
             "was fascinating and the staff were happy to answer questions.", 8),
            ("alice@example.com", 4,
             "Sample review — Nice way to spend two hours. Some exhibits could use "
             "better lighting, but the collection is impressive.", 20),
            ("ben@example.com", 5,
             "Sample review — Free entry and genuinely interesting. The family "
             "activity room kept the children happy for an hour.", 25),
        ],
    },
    {
        "name": "Northgate Shopping Centre",
        "location": "Northgate, Bristol",
        "category": "Shopping",
        "description": (
            "Sample place — an indoor shopping centre with high street brands, a food "
            "court and a multi-storey car park."
        ),
        "reviews": [
            ("ben@example.com", 2,
             "Sample review — Convenient for the big shops, but it was crowded and the "
             "car park prices are high for a short visit.", 4),
            ("alice@example.com", 2,
             "Sample review — Fine for the big chains, but it feels dated and the food "
             "court was mostly closed by six.", 13),
            ("chloe@example.com", 3,
             "Sample review — Everything under one roof, which is handy in the rain. "
             "Parking is expensive though.", 27),
        ],
    },
    {
        "name": "Sunset Pier",
        "location": "Pier Head, Weston-super-Mare",
        "category": "Attraction",
        "description": (
            "Sample place — a traditional seaside pier with arcades, a small funfair "
            "and excellent views at sunset."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Went for the sunset and it was beautiful. The arcades are "
             "a bit dated but that is part of the charm.", 7),
            ("ben@example.com", 3,
             "Sample review — Fine for a walk, though several attractions were closed "
             "when we visited in the afternoon.", 18),
            ("alice@example.com", 3,
             "Sample review — Nice views and a pleasant stroll, but half the arcade "
             "machines were out of order.", 24),
        ],
    },
    {
        "name": "The Old Town Library",
        "location": "14 King Street, Bristol",
        "category": "Other",
        "description": (
            "Sample place — a volunteer-run library with a quiet reading room, free "
            "Wi-Fi and a small local history section."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — A calm place to work for an afternoon. The reading room "
             "is quiet, the staff are helpful and the local history shelf is a nice "
             "surprise.", 2),
            ("ben@example.com", 4,
             "Sample review — Good selection of books and plenty of desks. Opening "
             "hours are a bit limited at weekends.", 16),
        ],
    },
    {
        "name": "Nasi Kerabu Kak Wani",
        "location": "Jalan Pengkalan Chepa, Kota Bharu, Kelantan",
        "category": "Restaurant",
        "description": (
            "Sample place — a family-run Kelantanese stall serving nasi kerabu with "
            "grilled fish, fresh ulam and a fiery budu dip. Busiest at lunchtime."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — The nasi kerabu was fragrant and the budu packed a real "
             "punch. Portions are generous and the price is very reasonable.", 2),
            ("ben@example.com", 4,
             "Sample review — Great local food and quick service. Seating is limited at "
             "peak lunch hour, so come before noon.", 5),
            ("demo@ratemyreview.com", 5,
             "Sample review — Ate here twice during my trip. The grilled fish and fresh "
             "ulam were excellent and the staff were friendly.", 9),
        ],
    },
    {
        "name": "Kopi Kita Cafe",
        "location": "Lebuh Armenian, George Town, Penang",
        "category": "Cafe",
        "description": (
            "Sample place — a small shophouse cafe serving local coffee, kaya toast and "
            "homemade cakes, with a quiet courtyard at the back."
        ),
        "reviews": [
            ("ben@example.com", 4,
             "Sample review — Good local coffee and excellent kaya toast. The courtyard "
             "is a nice escape from the afternoon heat.", 3),
            ("chloe@example.com", 4,
             "Sample review — Cosy spot with friendly staff. Service slowed down when it "
             "got busy, but the cakes were worth the wait.", 8),
            ("alice@example.com", 3,
             "Sample review — Coffee was decent but the upstairs room was warm and the "
             "seats are cramped.", 17),
        ],
    },
    {
        "name": "The RuMa Hotel",
        "location": "Jalan Kia Peng, Kuala Lumpur",
        "category": "Hotel",
        "description": (
            "Sample place — a boutique city hotel within walking distance of KLCC, with "
            "a small pool and a good breakfast spread."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — Attentive staff, a comfortable room and a pool with a view "
             "of the towers. Breakfast had plenty of local options.", 4),
            ("chloe@example.com", 4,
             "Sample review — Lovely design and a quiet location, though the walk to the "
             "train station is longer than it looks on the map.", 12),
        ],
    },
    {
        "name": "Petronas Twin Towers",
        "location": "KLCC, Kuala Lumpur",
        "category": "Attraction",
        "description": (
            "Sample place — the iconic twin towers, with a skybridge tour, an observation "
            "deck and a park at their base. Best visited around sunset."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — Stunning at night when the towers are lit up. Book the "
             "skybridge slot online to avoid the queue.", 1),
            ("ben@example.com", 5,
             "Sample review — The view from the observation deck is worth it, and the "
             "park below is a great place to sit afterwards.", 6),
            ("chloe@example.com", 4,
             "Sample review — Impressive building and well organised tours. It gets "
             "crowded, so go early in the day.", 14),
        ],
    },
    {
        "name": "Suria KLCC",
        "location": "KLCC, Kuala Lumpur",
        "category": "Shopping",
        "description": (
            "Sample place — a large mall at the base of the twin towers with "
            "international brands, a food court and a supermarket."
        ),
        "reviews": [
            ("ben@example.com", 4,
             "Sample review — Easy to spend a whole afternoon here. The food court has "
             "good local options and the layout is clear.", 7),
            ("alice@example.com", 3,
             "Sample review — Convenient and clean, but prices are aimed at tourists. "
             "The park outside is the better reason to visit.", 19),
        ],
    },
    {
        "name": "Taman Tasik Titiwangsa",
        "location": "Titiwangsa, Kuala Lumpur",
        "category": "Park",
        "description": (
            "Sample place — a lakeside park with a walking loop, playgrounds and clear "
            "views of the city skyline. Popular with joggers at sunrise."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Beautiful at sunrise with the skyline across the lake. "
             "Paths are wide and partly shaded.", 5),
            ("ben@example.com", 4,
             "Sample review — Good place for a morning run. Parking fills up quickly at "
             "weekends.", 21),
        ],
    },
    {
        "name": "Muzium Negara",
        "location": "Jalan Damansara, Kuala Lumpur",
        "category": "Museum",
        "description": (
            "Sample place — the national museum, covering Malaysian history from "
            "prehistory to independence across four galleries."
        ),
        "reviews": [
            ("alice@example.com", 4,
             "Sample review — Well organised galleries and inexpensive entry. The "
             "independence section was the highlight for me.", 10),
            ("ben@example.com", 3,
             "Sample review — Interesting collection but some displays need updating. "
             "Worth an hour if you are nearby.", 23),
        ],
    },
    {
        "name": "Pasar Siti Khadijah",
        "location": "Jalan Buluh Kubu, Kota Bharu, Kelantan",
        "category": "Other",
        "description": (
            "Sample place — a four-storey market known for wet goods, local snacks, "
            "batik and handicrafts. Lively from early morning."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Amazing local market. Go early for the food stalls on the "
             "ground floor and bring cash.", 3),
            ("alice@example.com", 4,
             "Sample review — Great for batik and kuih. It is busy and warm inside, but "
             "that is part of the experience.", 11),
            ("ben@example.com", 4,
             "Sample review — Huge selection and fair prices if you compare a few stalls "
             "first.", 26),
        ],
    },
    {
        "name": "Warung Nasi Dagang Kak Pah",
        "location": "Jalan Sultan Zainal Abidin, Kuala Terengganu, Terengganu",
        "category": "Restaurant",
        "description": (
            "Sample place — a small Terengganu warung serving nasi dagang with tuna "
            "curry, plus kuih and strong local coffee. Sells out before lunch."
        ),
        "reviews": [
            ("nurul@example.com", 5,
             "Sample review — The nasi dagang with tuna curry is the real deal: sweet, "
             "sour and spicy all at once. Arrive before 10am, it sells out.", 3),
            ("raj@example.com", 4,
             "Sample review — Simple warung with quick service and very fair prices. "
             "Seating is basic but the food is excellent.", 8),
            ("alice@example.com", 4,
             "Sample review — Stopped here on the way to the islands and it was the best "
             "meal of the trip. The kuih by the counter are worth trying.", 15),
            ("meiling@example.com", 5,
             "Sample review — A proper local breakfast. The curry is rich without being "
             "overpowering and the staff are very friendly.", 21),
        ],
    },
    {
        "name": "Ah Seng Kopitiam",
        "location": "Jalan Bandar Timah, Ipoh, Perak",
        "category": "Cafe",
        "description": (
            "Sample place — an old-school kopitiam in Ipoh serving white coffee, kaya "
            "toast, half-boiled eggs and egg tarts from early morning."
        ),
        "reviews": [
            ("ben@example.com", 5,
             "Sample review — Proper Ipoh white coffee and silky kaya toast. The shop is "
             "old-fashioned in the best way.", 4),
            ("meiling@example.com", 4,
             "Sample review — Great breakfast stop, though it gets packed after 8am. Egg "
             "tarts sell out early.", 10),
            ("chloe@example.com", 4,
             "Sample review — Friendly aunties running the place and very reasonable "
             "prices. A bit warm inside at midday.", 18),
        ],
    },
    {
        "name": "The Jonker Boutique Hotel",
        "location": "Jalan Tun Tan Cheng Lock, Melaka",
        "category": "Hotel",
        "description": (
            "Sample place — a restored shophouse hotel near Jonker Street, with a "
            "courtyard breakfast area and rooms full of Peranakan details."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — Beautifully restored shophouse right by Jonker Street. Rooms "
             "are small but full of character and the staff were lovely.", 2),
            ("raj@example.com", 4,
             "Sample review — Great location for the night market. Ask for a room at the "
             "back if you want quiet at weekends.", 9),
            ("nurul@example.com", 5,
             "Sample review — The courtyard breakfast was a highlight. Walking distance to "
             "most of the heritage area.", 17),
        ],
    },
    {
        "name": "Batu Caves",
        "location": "Gombak, Selangor",
        "category": "Attraction",
        "description": (
            "Sample place — a limestone cave temple reached by a steep flight of colourful "
            "steps, with a large statue at the entrance. Free to visit."
        ),
        "reviews": [
            ("ben@example.com", 5,
             "Sample review — The climb is worth it for the view from the top. Watch your "
             "belongings around the monkeys.", 2),
            ("nurul@example.com", 4,
             "Sample review — Impressive and free to enter. Go early to avoid the heat and "
             "the tour groups.", 7),
            ("raj@example.com", 4,
             "Sample review — Easy to reach by train from KL. Wear comfortable shoes, the "
             "steps are steep.", 13),
            ("chloe@example.com", 5,
             "Sample review — Visually stunning, especially in the morning light. Dress "
             "respectfully, shoulders and knees covered.", 20),
        ],
    },
    {
        "name": "Jonker Street Night Market",
        "location": "Jalan Hang Jebat, Melaka",
        "category": "Shopping",
        "description": (
            "Sample place — a Friday-to-Sunday street market with food stalls, souvenirs "
            "and handicrafts along the old chinatown street."
        ),
        "reviews": [
            ("meiling@example.com", 4,
             "Sample review — Great for snacks and souvenirs. Come hungry and bring cash, "
             "most stalls do not take cards.", 5),
            ("alice@example.com", 3,
             "Sample review — Fun atmosphere but very crowded and repetitive after a while. "
             "Go early in the evening.", 12),
            ("aiman@example.com", 4,
             "Sample review — The chicken rice balls and cendol stalls are the highlights. "
             "Parking is a nightmare, so walk or take a Grab.", 19),
        ],
    },
    {
        "name": "Perdana Botanical Garden",
        "location": "Jalan Kebun Bunga, Kuala Lumpur",
        "category": "Park",
        "description": (
            "Sample place — a large landscaped garden with a lake, an orchid garden, a "
            "deer park and shaded walking paths. Free entry."
        ),
        "reviews": [
            ("chloe@example.com", 5,
             "Sample review — Huge, green and free. The orchid garden was beautiful and it "
             "is easy to spend a whole morning here.", 6),
            ("aiman@example.com", 4,
             "Sample review — Good for a shaded walk, though some sections were closed for "
             "renovation. Bring mosquito repellent.", 14),
            ("meiling@example.com", 4,
             "Sample review — Peaceful escape from the city. The lake view and the deer "
             "park are nice for children.", 22),
        ],
    },
    {
        "name": "Baba & Nyonya Heritage Museum",
        "location": "Jalan Tun Tan Cheng Lock, Melaka",
        "category": "Museum",
        "description": (
            "Sample place — a preserved Peranakan family townhouse with guided tours of "
            "the carved furniture, tiles and family history."
        ),
        "reviews": [
            ("alice@example.com", 5,
             "Sample review — Fascinating guided tour of a Peranakan family home. The guide "
             "brought the history to life.", 4),
            ("raj@example.com", 4,
             "Sample review — Small but beautifully kept. Entry is a bit pricey for the "
             "size, though the tour is included.", 11),
            ("chloe@example.com", 5,
             "Sample review — One of the best museums I visited in Malaysia. Book ahead at "
             "weekends.", 23),
        ],
    },
    {
        "name": "Kota Kinabalu Waterfront",
        "location": "Jalan Tun Fuad Stephen, Kota Kinabalu, Sabah",
        "category": "Other",
        "description": (
            "Sample place — a seafront promenade with sunset views, seafood restaurants "
            "and a night market next door. Busiest in the evening."
        ),
        "reviews": [
            ("ben@example.com", 4,
             "Sample review — Great place for sunset and cheap seafood. The Filipino market "
             "next door is worth a wander.", 6),
            ("nurul@example.com", 5,
             "Sample review — Sunset here was stunning, and the night market seafood was "
             "fresh and affordable.", 16),
            ("raj@example.com", 4,
             "Sample review — Lively in the evening. A bit messy in places, but that is part "
             "of the charm.", 25),
        ],
    },
    {
        "name": "The Green Leaf Kitchen",
        "location": "22 Elm Street, Bath",
        "category": "Restaurant",
        "description": (
            "Sample place — a plant-based kitchen with a seasonal menu. Deliberately "
            "left without reviews so you can see the empty state."
        ),
        "reviews": [],
    },
    {
        "name": "The Book Nook Cafe",
        "location": "31 Castle Arcade, Cardiff",
        "category": "Cafe",
        "description": (
            "Sample place — a bookshop cafe with reading corners and a quiet back room. "
            "Deliberately left without reviews so you can see the empty state."
        ),
        "reviews": [],
    },
]

SAMPLE_REPORT_REASON = (
    "Sample report — the comment feels more like a complaint about parking than a "
    "review of the shopping centre."
)

# Extra reviews for the Malaysian places, so each one has five reviews from a
# wider mix of people. Format: (place name, email, rating, comment, days ago).
MALAYSIAN_EXTRA_REVIEWS = [
    ("Nasi Kerabu Kak Wani", "nurul@example.com", 5,
     "Sample review — The best nasi kerabu I have had in Kota Bharu. The kerabu is "
     "fresh and the grilled chicken is worth the queue.", 4),
    ("Nasi Kerabu Kak Wani", "aiman@example.com", 4,
     "Sample review — Generous portion and a good price. Parking along the road is "
     "tricky at lunchtime.", 12),

    ("Kopi Kita Cafe", "meiling@example.com", 5,
     "Sample review — Lovely heritage shophouse and properly brewed local coffee. The "
     "courtyard is the best seat in the house.", 6),
    ("Kopi Kita Cafe", "raj@example.com", 4,
     "Sample review — Kaya toast was spot on and the staff were welcoming. Would be "
     "five stars if there were more power sockets.", 16),

    ("The RuMa Hotel", "aiman@example.com", 5,
     "Sample review — Service was excellent from check-in to checkout. The room was "
     "quiet and breakfast had a good mix of local and western options.", 5),
    ("The RuMa Hotel", "meiling@example.com", 4,
     "Sample review — Beautifully designed hotel and a very comfortable bed. The pool "
     "is small but rarely crowded.", 13),
    ("The RuMa Hotel", "raj@example.com", 4,
     "Sample review — Great location for KLCC and the staff arranged a late checkout "
     "without fuss. Drinks at the bar are pricey.", 20),

    ("Petronas Twin Towers", "nurul@example.com", 5,
     "Sample review — Went up for the sunset slot and the view over the city was "
     "unforgettable. Security checks are quick and well organised.", 3),
    ("Petronas Twin Towers", "raj@example.com", 4,
     "Sample review — Worth doing once. The skybridge is impressive, though the tour "
     "moves quite fast.", 15),

    ("Suria KLCC", "meiling@example.com", 4,
     "Sample review — Clean, cool and easy to navigate. The supermarket downstairs is "
     "handy for gifts and local snacks.", 9),
    ("Suria KLCC", "aiman@example.com", 3,
     "Sample review — Fine for branded shopping, but the food court is crowded at lunch "
     "and seating is hard to find.", 18),
    ("Suria KLCC", "nurul@example.com", 4,
     "Sample review — Good place to escape the afternoon heat. The park outside is "
     "nicer than the mall itself.", 22),

    ("Taman Tasik Titiwangsa", "raj@example.com", 5,
     "Sample review — Did a 5km loop at sunrise and the skyline across the lake was "
     "superb. Well maintained and felt safe.", 7),
    ("Taman Tasik Titiwangsa", "aiman@example.com", 4,
     "Sample review — Great for families, with a decent playground and plenty of shade. "
     "Some paths were closed for maintenance.", 17),
    ("Taman Tasik Titiwangsa", "meiling@example.com", 4,
     "Sample review — Peaceful on weekday mornings. Bring water, the nearest shops are "
     "a short drive away.", 24),

    ("Muzium Negara", "nurul@example.com", 4,
     "Sample review — A good introduction to Malaysian history and the building itself "
     "is impressive. Allow about two hours.", 11),
    ("Muzium Negara", "raj@example.com", 5,
     "Sample review — The independence galleries are well presented and entry is cheap. "
     "A worthwhile stop near the lake gardens.", 19),
    ("Muzium Negara", "aiman@example.com", 3,
     "Sample review — Informative but a little old-fashioned. Some interactive displays "
     "were out of order when I visited.", 26),

    ("Pasar Siti Khadijah", "meiling@example.com", 5,
     "Sample review — Come hungry. The ground-floor food stalls are excellent and the "
     "batik selection upstairs is huge.", 8),
    ("Pasar Siti Khadijah", "nurul@example.com", 4,
     "Sample review — Lively, colourful and busy. Prices are fair if you compare a few "
     "stalls before buying.", 21),
]


def _days_ago(days: int, hours: int = 0) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _ensure_users(conn) -> dict[str, int]:
    """Create the sample accounts that do not exist yet; return email -> id."""
    user_ids: dict[str, int] = {}

    for person in SAMPLE_USERS:
        row = fetch_one(conn, "SELECT id FROM users WHERE email = ?", (person["email"],))
        if row:
            user_ids[person["email"]] = row["id"]
            continue
        user_ids[person["email"]] = execute(
            conn,
            "INSERT INTO users (name, email, password_hash, role, created_at)"
            " VALUES (?, ?, ?, 'user', ?)",
            (person["name"], person["email"], hash_password(person["password"]),
             _days_ago(45)),
        )

    admin = fetch_one(conn, "SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,))
    if admin:
        user_ids[ADMIN_EMAIL] = admin["id"]
    else:
        user_ids[ADMIN_EMAIL] = execute(
            conn,
            "INSERT INTO users (name, email, password_hash, role, created_at)"
            " VALUES (?, ?, ?, 'admin', ?)",
            ("Site Administrator", ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), _days_ago(60)),
        )
    return user_ids


def _ensure_places_and_reviews(conn, user_ids: dict[str, int]) -> tuple[int, int]:
    """Insert sample places/reviews that are missing. Returns (places, reviews)."""
    places_added = 0
    reviews_added = 0

    for index, place in enumerate(SAMPLE_PLACES):
        row = fetch_one(conn, "SELECT id FROM places WHERE name = ?", (place["name"],))
        if row:
            place_id = row["id"]
        else:
            country = place.get("country") or infer_country_state(place["location"])[0]
            state = place.get("state") or infer_country_state(place["location"])[1]
            place_id = execute(
                conn,
                "INSERT INTO places"
                " (name, country, state, location, category, description, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (place["name"], country, state, place["location"], place["category"],
                 place["description"], _days_ago(36 - index)),
            )
            places_added += 1

        for email, rating, comment, days in place["reviews"]:
            existing = fetch_one(
                conn,
                "SELECT id FROM reviews WHERE user_id = ? AND place_id = ?",
                (user_ids[email], place_id),
            )
            if existing:
                continue
            execute(
                conn,
                "INSERT INTO reviews (user_id, place_id, rating, comment, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_ids[email], place_id, rating, comment, _days_ago(days, days % 7)),
            )
            reviews_added += 1

    # Extra Malaysian reviews — skipped when that reviewer already reviewed
    # the place, so running this again never duplicates anything.
    for place_name, email, rating, comment, days in MALAYSIAN_EXTRA_REVIEWS:
        place = fetch_one(conn, "SELECT id FROM places WHERE name = ?", (place_name,))
        if not place:
            continue
        existing = fetch_one(
            conn,
            "SELECT id FROM reviews WHERE user_id = ? AND place_id = ?",
            (user_ids[email], place["id"]),
        )
        if existing:
            continue
        execute(
            conn,
            "INSERT INTO reviews (user_id, place_id, rating, comment, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_ids[email], place["id"], rating, comment, _days_ago(days, days % 7)),
        )
        reviews_added += 1

    return places_added, reviews_added


def _ensure_sample_report(conn, user_ids: dict[str, int]) -> None:
    """Add one sample report for the admin queue, if it is not there already."""
    review = fetch_one(
        conn,
        "SELECT r.id FROM reviews r JOIN places p ON p.id = r.place_id"
        " WHERE p.name = 'Northgate Shopping Centre' AND r.user_id = ? LIMIT 1",
        (user_ids["ben@example.com"],),
    )
    if not review:
        return

    existing = fetch_one(
        conn,
        "SELECT id FROM reports WHERE review_id = ? AND reporter_id = ?",
        (review["id"], user_ids["alice@example.com"]),
    )
    if existing:
        return

    execute(
        conn,
        "INSERT INTO reports (review_id, reporter_id, reason, status, created_at)"
        " VALUES (?, ?, ?, 'open', ?)",
        (review["id"], user_ids["alice@example.com"], SAMPLE_REPORT_REASON, _days_ago(1)),
    )


def seed_database() -> None:
    """First-run seeding: only acts when there are no places at all."""
    conn = connect()
    try:
        existing = fetch_one(conn, "SELECT COUNT(*) AS n FROM places")
        if existing and existing["n"] > 0:
            return
        user_ids = _ensure_users(conn)
        _ensure_places_and_reviews(conn, user_ids)
        _ensure_sample_report(conn, user_ids)
    finally:
        conn.close()


def top_up_sample_data() -> tuple[int, int]:
    """Add any missing sample places/reviews without deleting anything.

    Returns the number of places and reviews that were inserted.
    """
    init_db()
    conn = connect()
    try:
        user_ids = _ensure_users(conn)
        places_added, reviews_added = _ensure_places_and_reviews(conn, user_ids)
        _ensure_sample_report(conn, user_ids)
        return places_added, reviews_added
    finally:
        conn.close()


def reset_database() -> None:
    """Delete every table and start again with fresh sample data."""
    conn = connect()
    try:
        conn.executescript(
            "DROP TABLE IF EXISTS reports;"
            "DROP TABLE IF EXISTS reviews;"
            "DROP TABLE IF EXISTS places;"
            "DROP TABLE IF EXISTS users;"
        )
        conn.commit()
    finally:
        conn.close()
    init_db()
    seed_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load sample data for Rate My Review.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reset", action="store_true",
                       help="delete all data, recreate the tables and reload the sample rows")
    group.add_argument("--add", action="store_true",
                       help="add only the sample places/reviews that are missing")
    args = parser.parse_args()

    if args.reset:
        reset_database()
        print("Database reset with fresh sample data.")
    elif args.add:
        added_places, added_reviews = top_up_sample_data()
        print(f"Added {added_places} place(s) and {added_reviews} review(s). "
              "Existing data was kept.")
    else:
        init_db()
        seed_database()
        print("Sample data loaded (existing data was kept).")
