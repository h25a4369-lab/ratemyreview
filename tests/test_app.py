"""End-to-end tests for the Rate My Review site.

Run with:  pytest -q
"""
from __future__ import annotations

import re

from conftest import (
    SAMPLE_PASSWORD,
    get_csrf,
    login,
    logout,
    place_id,
    register,
    review_count,
    submit_review,
)

from app.database import connect


# ==========================================================================
# Feature 1 — Browse and search places
# ==========================================================================
def test_home_page_has_branding_heading_and_search(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Rate" in response.text and "My" in response.text and "Review" in response.text
    assert "Discover Places." in response.text
    assert "Share Your Experience." in response.text
    assert 'name="q"' in response.text
    assert "How it works" in response.text
    assert "About Us" in response.text and "Privacy Policy" in response.text


def test_search_finds_place_by_name(client):
    response = client.get("/places", params={"q": "Blue Fork"})
    assert response.status_code == 200
    assert "The Blue Fork Bistro" in response.text
    assert "Cloud Nine Coffee" not in response.text


def test_search_by_location_and_category(client):
    by_location = client.get("/places", params={"location": "Bath"})
    assert "Riverside Park" in by_location.text
    assert "The Blue Fork Bistro" not in by_location.text

    by_category = client.get("/places", params={"category": "Museum"})
    assert "City Art Museum" in by_category.text
    assert "Cloud Nine Coffee" not in by_category.text


def test_search_with_no_matches_shows_clear_message(client):
    response = client.get("/places", params={"q": "does-not-exist-xyz"})
    assert response.status_code == 200
    assert "No places found" in response.text
    assert "0</strong> results" in response.text


def test_search_is_safe_with_quotes(client):
    response = client.get("/places", params={"q": "' OR 1=1 --"})
    assert response.status_code == 200
    assert "The Blue Fork Bistro" not in response.text


def test_short_link_redirects_to_the_long_filtered_url(client):
    response = client.get("/s/kl", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("/places?")
    assert "q=kuala+lumpur" in location
    assert "state=Kuala+Lumpur" in location
    assert "sort=reviews" in location

    page = client.get("/s/kl")            # following the redirect lands on results
    assert page.status_code == 200
    assert "Petronas Twin Towers" in page.text


def test_short_link_is_case_insensitive_and_unknown_codes_404(client):
    assert client.get("/s/KL", follow_redirects=False).status_code == 307
    assert client.get("/s/not-a-real-code", follow_redirects=False).status_code == 404


def test_short_link_all_shows_every_place(client):
    response = client.get("/s/all", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/places?sort=reviews"

    page = client.get("/s/all")
    assert page.status_code == 200
    assert "Showing all" in page.text


def test_place_detail_shows_name_location_category_and_rating(client):
    pid = place_id("The Blue Fork Bistro")
    response = client.get(f"/places/{pid}")
    assert response.status_code == 200
    assert "The Blue Fork Bistro" in response.text
    assert "12 Harbour Street, Bristol" in response.text
    assert "Restaurant" in response.text
    assert "4.7" in response.text          # (5 + 4 + 5) / 3 = 4.67 → 4.7
    assert "3 reviews" in response.text


def test_unknown_place_returns_friendly_404(client):
    response = client.get("/places/99999")
    assert response.status_code == 404
    assert "could not find that place" in response.text.lower()
    assert "Back to home" in response.text


def test_sorting_reviews_by_lowest_rating(client):
    pid = place_id("The Blue Fork Bistro")
    response = client.get(f"/places/{pid}", params={"sort": "lowest"})
    assert response.status_code == 200
    # The 4-star review should come before the 5-star ones.
    assert response.text.index("Service was a little slow") < response.text.index("mushroom risotto")


def test_malaysian_sample_places_are_searchable(client):
    kelantan = client.get("/places", params={"location": "Kelantan"})
    assert "Nasi Kerabu Kak Wani" in kelantan.text
    assert "Pasar Siti Khadijah" in kelantan.text
    assert "Kopi Kita Cafe" not in kelantan.text

    kl_museum = client.get(
        "/places", params={"location": "Kuala Lumpur", "category": "Museum"}
    )
    assert "Muzium Negara" in kl_museum.text
    assert "City Art Museum" not in kl_museum.text

    twins = client.get(f"/places/{place_id('Petronas Twin Towers')}")
    assert "KLCC, Kuala Lumpur" in twins.text
    assert "4.6" in twins.text
    assert "5 reviews" in twins.text


def test_search_filters_by_country_and_state(client):
    malaysia = client.get("/places", params={"country": "Malaysia"})
    assert "Kopi Kita Cafe" in malaysia.text
    assert "The Blue Fork Bistro" not in malaysia.text

    melaka = client.get("/places", params={"country": "Malaysia", "state": "Melaka"})
    assert "Jonker Street Night Market" in melaka.text
    assert "Nyonya Heritage Museum" in melaka.text
    assert "Nasi Kerabu Kak Wani" not in melaka.text

    uk = client.get("/places", params={"country": "United Kingdom", "state": "Wales"})
    assert "The Book Nook Cafe" in uk.text
    assert "The Blue Fork Bistro" not in uk.text

    # The keyword box also covers country and state names.
    keyword = client.get("/places", params={"q": "Sabah"})
    assert "Kota Kinabalu Waterfront" in keyword.text

    empty = client.get("/places", params={"country": "Malaysia", "state": "Perlis"})
    assert "No places found" in empty.text


def test_places_carry_country_and_state(client):
    page = client.get(f"/places/{place_id('Kota Kinabalu Waterfront')}")
    assert page.status_code == 200
    assert "Sabah" in page.text
    assert "Malaysia" in page.text

    london = client.get(f"/places/{place_id('The Blue Fork Bistro')}")
    assert "England" in london.text
    assert "United Kingdom" in london.text


def test_review_form_asks_for_country_state_and_place(client):
    login(client, "demo@ratemyreview.com")
    response = client.get("/write-review")
    assert response.status_code == 200
    assert 'id="review-country"' in response.text
    assert 'id="review-state"' in response.text
    assert 'name="place_id"' in response.text
    assert 'data-country="Malaysia"' in response.text
    assert "Nasi Kerabu Kak Wani" in response.text


# ==========================================================================
# Feature 2 — Registration and login
# ==========================================================================
def test_register_creates_account_and_stores_a_hash(client):
    response = register(client, name="Nina Patel", email="nina@example.com")
    assert response.status_code == 200
    assert "Welcome to Rate My Review" in response.text
    assert "Nina" in response.text

    conn = connect()
    try:
        row = conn.execute(
            "SELECT name, email, password_hash, role FROM users WHERE email = ?",
            ("nina@example.com",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["role"] == "user"
    assert row["password_hash"] != SAMPLE_PASSWORD
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert SAMPLE_PASSWORD not in row["password_hash"]


def test_duplicate_email_is_rejected(client):
    register(client, email="dup@example.com")
    logout(client)
    response = register(client, name="Someone Else", email="DUP@example.com")
    assert response.status_code == 400
    assert "already exists" in response.text


def test_invalid_email_and_short_password_are_rejected(client):
    bad_email = register(client, email="not-an-email")
    assert bad_email.status_code == 400
    assert "does not look valid" in bad_email.text

    weak = register(client, email="weak@example.com", password="short")
    assert weak.status_code == 400
    assert "at least 8 characters" in weak.text

    mismatch = register(client, email="mismatch@example.com", confirm="Different123")
    assert mismatch.status_code == 400
    assert "do not match" in mismatch.text


def test_blank_registration_shows_required_field_errors(client):
    response = register(client, name="", email="", password="")
    assert response.status_code == 400
    assert "enter your name" in response.text
    assert "enter your email address" in response.text
    assert "at least 8 characters" in response.text


def test_login_with_correct_credentials(client):
    register(client, name="Omar Haddad", email="omar@example.com")
    logout(client)
    response = login(client, "omar@example.com")
    assert response.status_code == 200
    assert "Welcome back, Omar!" in response.text
    assert "Log out" in response.text


def test_login_with_wrong_password_is_denied(client):
    register(client, email="casey@example.com")
    logout(client)
    response = login(client, "casey@example.com", "WrongPassword1")
    assert response.status_code == 400
    assert "Email or password is incorrect" in response.text
    assert "Log out" not in response.text


def test_login_with_unknown_email_gives_same_message(client):
    response = login(client, "nobody@example.com", "Whatever123")
    assert response.status_code == 400
    assert "Email or password is incorrect" in response.text


def test_logout_ends_the_session(client):
    register(client, email="bye@example.com")
    response = logout(client)
    assert response.status_code == 200
    assert "Log out" not in response.text
    assert "Register" in response.text


# ==========================================================================
# Feature 3 — Submit ratings and reviews
# ==========================================================================
def test_guest_is_asked_to_log_in_before_reviewing(client):
    pid = place_id("Cloud Nine Coffee")
    page = client.get(f"/write-review?place_id={pid}", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"].startswith("/login")

    posted = client.post(
        "/reviews",
        data={"place_id": pid, "rating": 5, "comment": "Nice place"},
        follow_redirects=False,
    )
    assert posted.status_code == 303
    assert posted.headers["location"].startswith("/login")

    followed = client.get(posted.headers["location"])
    assert "Please log in to continue" in followed.text


def test_logged_in_user_can_submit_a_review(client):
    register(client, name="Riya Shah", email="riya@example.com")
    pid = place_id("Cloud Nine Coffee")
    before = review_count(pid)

    response = submit_review(client, pid, 5, "The cardamom bun was outstanding and the staff were lovely.")
    assert response.status_code == 200
    assert "Thank you — your review has been posted." in response.text
    assert "The cardamom bun was outstanding" in response.text
    assert review_count(pid) == before + 1


def test_rating_outside_one_to_five_is_rejected(client):
    register(client, email="rate@example.com")
    pid = place_id("Riverside Park")

    for bad_rating in (0, 6, -1, 99):
        response = submit_review(client, pid, bad_rating, "A comment that is long enough.")
        assert response.status_code == 400, f"rating {bad_rating} should be rejected"
        assert "star rating between 1 and 5" in response.text

    conn = connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews r JOIN users u ON u.id = r.user_id"
            " WHERE u.email = 'rate@example.com'"
        ).fetchone()["n"]
    finally:
        conn.close()
    assert count == 0


def test_review_without_comment_is_rejected(client):
    register(client, email="empty@example.com")
    pid = place_id("Riverside Park")
    response = submit_review(client, pid, 4, "   ")
    assert response.status_code == 400
    assert "Please write a comment" in response.text


def test_review_for_unknown_place_returns_404(client):
    register(client, email="ghost@example.com")
    token = get_csrf(client, "/")
    response = client.post(
        "/reviews",
        data={"place_id": "99999", "rating": 5, "comment": "Nowhere at all", "csrf_token": token},
    )
    assert response.status_code == 404


def test_second_review_for_same_place_redirects_to_edit(client):
    register(client, email="twice@example.com")
    pid = place_id("Harbour View Hotel")
    submit_review(client, pid, 4, "A perfectly pleasant first stay.")
    after_first = review_count(pid)
    response = submit_review(client, pid, 5, "Trying to post a second review for the same place.")
    assert response.status_code == 200
    assert "already reviewed this place" in response.text
    assert review_count(pid) == after_first
    assert "Edit your review" in response.text


# ==========================================================================
# Feature 4 — Reviews and average ratings
# ==========================================================================
def test_average_rating_matches_saved_ratings(client):
    pid = place_id("The Book Nook Cafe")

    register(client, name="Average One", email="avg1@example.com")
    submit_review(client, pid, 5, "Excellent cakes and very quiet.")
    logout(client)

    register(client, name="Average Two", email="avg2@example.com")
    submit_review(client, pid, 2, "Service was slow and the coffee was cold.")
    logout(client)

    response = client.get(f"/places/{pid}")
    assert "3.5" in response.text          # (5 + 2) / 2
    assert "2 reviews" in response.text
    assert "No review" not in response.text.split("Rating summary")[0]


def test_place_without_reviews_shows_empty_message(client):
    pid = place_id("The Green Leaf Kitchen")
    response = client.get(f"/places/{pid}")
    assert response.status_code == 200
    assert "No reviews yet." in response.text
    assert "Be the first" in response.text


def test_reviews_belong_to_their_own_place_only(client):
    blue_fork = client.get(f"/places/{place_id('The Blue Fork Bistro')}")
    riverside = client.get(f"/places/{place_id('Riverside Park')}")
    assert "mushroom risotto" in blue_fork.text
    assert "mushroom risotto" not in riverside.text
    assert "ducks" in riverside.text


# ==========================================================================
# Feature 5 — Edit and delete your own reviews
# ==========================================================================
def test_user_can_edit_their_own_review(client):
    register(client, name="Editor Person", email="editor@example.com")
    pid = place_id("Harbour View Hotel")
    submit_review(client, pid, 5, "Absolutely wonderful, would return.")

    conn = connect()
    try:
        row = conn.execute(
            "SELECT r.id FROM reviews r JOIN users u ON u.id = r.user_id"
            " WHERE u.email = 'editor@example.com'"
        ).fetchone()
    finally:
        conn.close()
    rid = row["id"]

    form = client.get(f"/reviews/{rid}/edit")
    assert form.status_code == 200
    assert "Absolutely wonderful" in form.text

    token = get_csrf(client, "/")
    updated = client.post(
        f"/reviews/{rid}/edit",
        data={"rating": "3", "comment": "Revisited and the room was noisy this time.", "csrf_token": token},
    )
    assert updated.status_code == 200
    assert "Your review has been updated." in updated.text
    assert "Revisited and the room was noisy" in updated.text
    assert f"Based on {review_count(pid)} reviews" in updated.text

    place = client.get(f"/places/{pid}")
    assert "Revisited and the room was noisy" in place.text
    assert "Absolutely wonderful" not in place.text


def test_user_cannot_edit_someone_elses_review(client):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT r.id FROM reviews r JOIN users u ON u.id = r.user_id"
            " WHERE u.email = 'alice@example.com' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    register(client, name="Intruder", email="intruder@example.com")
    token = get_csrf(client, "/")
    response = client.post(
        f"/reviews/{row['id']}/edit",
        data={"rating": "1", "comment": "This should never be saved.", "csrf_token": token},
    )
    assert response.status_code == 403
    assert "only edit your own reviews" in response.text

    page = client.get(f"/reviews/{row['id']}/edit")
    assert page.status_code == 403


def test_user_can_delete_their_own_review(client):
    register(client, name="Deleter", email="deleter@example.com")
    pid = place_id("Northgate Shopping Centre")
    before = review_count(pid)
    submit_review(client, pid, 3, "It was fine but the parking cost too much.")
    assert review_count(pid) == before + 1

    conn = connect()
    try:
        rid = conn.execute(
            "SELECT r.id FROM reviews r JOIN users u ON u.id = r.user_id"
            " WHERE u.email = 'deleter@example.com'"
        ).fetchone()["id"]
    finally:
        conn.close()

    token = get_csrf(client, "/")
    response = client.post(f"/reviews/{rid}/delete", data={"csrf_token": token})
    assert response.status_code == 200
    assert "Your review has been deleted." in response.text
    assert review_count(pid) == before


def test_user_cannot_delete_someone_elses_review(client):
    conn = connect()
    try:
        rid = conn.execute("SELECT id FROM reviews ORDER BY id LIMIT 1").fetchone()["id"]
    finally:
        conn.close()

    register(client, name="Not Owner", email="notowner@example.com")
    token = get_csrf(client, "/")
    response = client.post(f"/reviews/{rid}/delete", data={"csrf_token": token})
    assert response.status_code == 403


# ==========================================================================
# Feature 6 — Reporting reviews
# ==========================================================================
def test_report_is_saved_and_review_stays_visible(client):
    conn = connect()
    try:
        review = conn.execute(
            "SELECT r.id, r.place_id, r.comment FROM reviews r"
            " JOIN users u ON u.id = r.user_id WHERE u.email = 'ben@example.com' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    register(client, name="Reporter", email="reporter@example.com")
    token = get_csrf(client, "/")
    response = client.post(
        f"/reviews/{review['id']}/report",
        data={"reason": "spam", "csrf_token": token},
    )
    assert response.status_code == 200
    assert "Your report has been sent to our moderators" in response.text
    assert review["comment"][:30] in response.text   # review is still shown

    conn = connect()
    try:
        row = conn.execute(
            "SELECT reason, status FROM reports WHERE review_id = ?", (review["id"],)
        ).fetchone()
    finally:
        conn.close()
    assert row["status"] == "open"
    assert row["reason"] == "Spam or advertising"


def test_report_without_reason_is_rejected(client):
    conn = connect()
    try:
        review = conn.execute("SELECT id, place_id FROM reviews ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()

    register(client, email="noreason@example.com")
    token = get_csrf(client, "/")
    response = client.post(
        f"/reviews/{review['id']}/report",
        data={"reason": "", "csrf_token": token},
    )
    assert response.status_code == 200
    assert "Please choose a reason" in response.text

    conn = connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM reports rp JOIN users u ON u.id = rp.reporter_id"
            " WHERE u.email = 'noreason@example.com'"
        ).fetchone()["n"]
    finally:
        conn.close()
    assert count == 0


def test_guest_must_log_in_to_report(client):
    conn = connect()
    try:
        review = conn.execute("SELECT id FROM reviews ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()

    response = client.post(
        f"/reviews/{review['id']}/report",
        data={"reason": "spam"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_duplicate_report_is_handled_gently(client):
    conn = connect()
    try:
        review = conn.execute("SELECT id FROM reviews ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()

    register(client, email="double.report@example.com")
    token = get_csrf(client, "/")
    first = client.post(f"/reviews/{review['id']}/report", data={"reason": "abusive", "csrf_token": token})
    assert "Your report has been sent" in first.text

    token = get_csrf(client, "/")
    second = client.post(f"/reviews/{review['id']}/report", data={"reason": "abusive", "csrf_token": token})
    assert "already reported this review" in second.text


def test_admin_sees_reports_and_can_resolve_them(client):
    login(client, "admin@ratemyreview.com", "Admin123!")
    page = client.get("/admin/reports")
    assert page.status_code == 200
    assert "Reported reviews" in page.text
    assert "Sample report" in page.text

    conn = connect()
    try:
        report = conn.execute("SELECT id FROM reports WHERE status = 'open' LIMIT 1").fetchone()
    finally:
        conn.close()

    token = get_csrf(client, "/admin/reports")
    resolved = client.post(
        f"/admin/reports/{report['id']}/status",
        data={"status": "resolved", "csrf_token": token},
    )
    assert resolved.status_code == 200
    assert "Report marked as resolved." in resolved.text

    conn = connect()
    try:
        status = conn.execute("SELECT status FROM reports WHERE id = ?", (report["id"],)).fetchone()["status"]
    finally:
        conn.close()
    assert status == "resolved"


# ==========================================================================
# Administrator permissions and management
# ==========================================================================
def test_visitor_and_user_cannot_open_admin_pages(client):
    # A visitor is sent to the login page first.
    guest = client.get("/admin", follow_redirects=False)
    assert guest.status_code == 303
    assert guest.headers["location"].startswith("/login")

    # A signed-in non-admin is refused outright.
    register(client, email="normal@example.com")
    forbidden = client.get("/admin")
    assert forbidden.status_code == 403
    assert "administrators" in forbidden.text
    assert client.get("/admin/users").status_code == 403


def test_admin_can_add_edit_and_delete_a_place(client):
    login(client, "admin@ratemyreview.com", "Admin123!")
    token = get_csrf(client, "/admin/places/new")
    created = client.post(
        "/admin/places/new",
        data={
            "name": "Test Gallery",
            "country": "Malaysia",
            "state": "Selangor",
            "location": "5 Test Street, Shah Alam",
            "category": "Museum",
            "description": "A place created by the test suite.",
            "csrf_token": token,
        },
    )
    assert created.status_code == 200
    assert "Test Gallery" in created.text

    new_id = place_id("Test Gallery")

    token = get_csrf(client, f"/admin/places/{new_id}/edit")
    edited = client.post(
        f"/admin/places/{new_id}/edit",
        data={
            "name": "Test Gallery Renamed",
            "country": "Malaysia",
            "state": "Selangor",
            "location": "5 Test Street, Shah Alam",
            "category": "Museum",
            "description": "Updated description.",
            "csrf_token": token,
        },
    )
    assert edited.status_code == 200
    assert "Test Gallery Renamed" in edited.text

    token = get_csrf(client, "/admin/places")
    deleted = client.post(f"/admin/places/{new_id}/delete", data={"csrf_token": token})
    assert deleted.status_code == 200
    assert client.get(f"/places/{new_id}").status_code == 404


def test_admin_can_delete_an_inappropriate_review(client):
    conn = connect()
    try:
        review = conn.execute("SELECT id, place_id FROM reviews ORDER BY id LIMIT 1").fetchone()
    finally:
        conn.close()

    login(client, "admin@ratemyreview.com", "Admin123!")
    token = get_csrf(client, "/admin/reviews")
    response = client.post(f"/reviews/{review['id']}/delete", data={"csrf_token": token})
    assert response.status_code == 200
    assert client.get(f"/places/{review['place_id']}").status_code == 200

    conn = connect()
    try:
        gone = conn.execute("SELECT id FROM reviews WHERE id = ?", (review["id"],)).fetchone()
    finally:
        conn.close()
    assert gone is None


def test_forms_require_a_csrf_token(client):
    register(client, email="csrf@example.com")
    response = client.post(
        "/reviews",
        data={"place_id": place_id("Riverside Park"), "rating": 5, "comment": "No token here at all"},
    )
    assert response.status_code == 400
    assert "expired" in response.text.lower()


# ==========================================================================
# Privacy and data handling
# ==========================================================================
def test_public_pages_never_show_emails_or_hashes(client):
    pid = place_id("The Blue Fork Bistro")
    pages = [client.get("/"), client.get("/places"), client.get(f"/places/{pid}")]
    for page in pages:
        assert "alice@example.com" not in page.text
        assert "pbkdf2_sha256" not in page.text

    # Reviews show an abbreviated author name instead of a full one.
    assert "Alice M." in pages[2].text
