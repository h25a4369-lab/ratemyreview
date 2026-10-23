"""Country and state helpers.

Places store their own country and state, so a review inherits them from the
place it belongs to (one source of truth, no duplicated values that can drift
apart). These helpers infer the pair for the sample data and power the
country / state dropdowns.
"""
from __future__ import annotations

MALAYSIA_STATES = [
    "Johor", "Kedah", "Kelantan", "Kuala Lumpur", "Labuan", "Melaka",
    "Negeri Sembilan", "Pahang", "Penang", "Perak", "Perlis", "Putrajaya",
    "Sabah", "Sarawak", "Selangor", "Terengganu",
]

UK_NATIONS = ["England", "Scotland", "Wales", "Northern Ireland"]

# City or town name -> UK nation, for addresses that do not name the nation.
UK_CITIES = {
    "bristol": "England",
    "bath": "England",
    "weston-super-mare": "England",
    "leeds": "England",
    "london": "England",
    "manchester": "England",
    "birmingham": "England",
    "oxford": "England",
    "cambridge": "England",
    "cardiff": "Wales",
    "swansea": "Wales",
    "edinburgh": "Scotland",
    "glasgow": "Scotland",
    "belfast": "Northern Ireland",
}

COUNTRIES = ["Malaysia", "United Kingdom", "Singapore", "Indonesia", "Thailand", "Australia"]


def infer_country_state(location: str | None) -> tuple[str, str]:
    """Best guess for a free-text address. Returns ("", "") when unsure.

    Used for the sample rows and for filling in older databases; anything added
    through the admin form has its country and state typed in explicitly.
    """
    text = (location or "").lower()

    for state in MALAYSIA_STATES:
        if state.lower() in text:
            return "Malaysia", state

    for nation in UK_NATIONS:
        if nation.lower() in text:
            return "United Kingdom", nation

    for city, nation in UK_CITIES.items():
        if city in text:
            return "United Kingdom", nation

    return "", ""
