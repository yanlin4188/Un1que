"""
repository.py
-------------
All database operations for the app.
Import these functions in app.py and call them from your Flask routes.

Every function that writes data calls db.session.commit() internally,
so callers don't need to manage transactions themselves.
"""

import random
import string

from database import db
from models import Attendee, Party


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_code(length: int = 6) -> str:
    """Return a random uppercase alphanumeric code, e.g. 'A3KZ91'."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def _unique_code() -> str:
    """Keep generating until we find a code not already in the DB."""
    for _ in range(10):          # safety limit – astronomically unlikely to loop
        code = _generate_code()
        if not Party.query.filter_by(code=code).first():
            return code
    raise RuntimeError("Could not generate a unique party code after 10 attempts.")


# ---------------------------------------------------------------------------
# Party functions
# ---------------------------------------------------------------------------

def create_party(title: str, organizer_name: str, location: str = None, starts_at=None) -> Party:
    """
    Create a new party and return it.

    Example:
        party = create_party("Halloween Bash", "Alice", location="123 Main St")
        print(party.code)   # e.g. "A3KZ91"
    """
    party = Party(
        code=_unique_code(),
        title=title,
        organizer_name=organizer_name,
        location=location,
        starts_at=starts_at,
    )
    db.session.add(party)
    db.session.commit()
    return party


def get_party_by_code(code: str) -> Party | None:
    """
    Return the Party with the given invite code, or None if not found.

    Example:
        party = get_party_by_code("A3KZ91")
        if party is None:
            return "Invalid code", 404
    """
    return Party.query.filter_by(code=code.upper()).first()


# ---------------------------------------------------------------------------
# Attendee functions
# ---------------------------------------------------------------------------

def join_party(code: str, name: str) -> Attendee:
    """
    Add an attendee to a party identified by its invite code.
    Raises ValueError if the code is invalid.

    Example:
        attendee = join_party("A3KZ91", "Bob")
    """
    party = get_party_by_code(code)
    if party is None:
        raise ValueError(f"No party found with code '{code}'.")

    attendee = Attendee(party_id=party.id, name=name, status="going")
    db.session.add(attendee)
    db.session.commit()
    return attendee


def update_rsvp(attendee_id: int, status: str) -> Attendee:
    """
    Set an attendee's status to "going" or "not_going".
    Raises ValueError if the attendee doesn't exist or the status is invalid.

    Example:
        update_rsvp(attendee_id=3, status="not_going")
    """
    if status not in ("going", "not_going"):
        raise ValueError(f"Invalid status '{status}'. Must be 'going' or 'not_going'.")

    attendee = db.session.get(Attendee, attendee_id)
    if attendee is None:
        raise ValueError(f"No attendee found with id {attendee_id}.")

    attendee.status = status
    db.session.commit()
    return attendee


def save_costume_keywords(attendee_id: int, keywords: list[str]) -> Attendee:
    """
    Store or replace an attendee's costume keywords.
    Pass a plain Python list of strings; they are stored comma-separated.
    Raises ValueError if the attendee doesn't exist.

    Example:
        save_costume_keywords(attendee_id=3, keywords=["vampire", "cape", "red"])
    """
    attendee = db.session.get(Attendee, attendee_id)
    if attendee is None:
        raise ValueError(f"No attendee found with id {attendee_id}.")

    # Normalise: lowercase, strip whitespace, drop empties
    cleaned = [kw.strip().lower() for kw in keywords if kw.strip()]
    attendee.costume_keywords = ",".join(cleaned)
    db.session.commit()
    return attendee


def get_other_costumes(party_code: str, attendee_id: int) -> list[list[str]]:
    """
    Return the costume keyword lists of every *other* going attendee in the party.
    This is used ONLY by the backend matcher — never expose this raw data to the frontend.
    Raises ValueError if the party code is invalid.

    Returns a list of keyword lists, e.g.:
        [["witch", "hat", "black"], ["pirate", "sword"]]

    Example (in a route):
        others = get_other_costumes(party_code="A3KZ91", attendee_id=3)
        result = matcher.check_uniqueness(my_keywords, others)
    """
    party = get_party_by_code(party_code)
    if party is None:
        raise ValueError(f"No party found with code '{party_code}'.")

    others = (
        Attendee.query
        .filter(
            Attendee.party_id == party.id,
            Attendee.id != attendee_id,          # exclude the requesting attendee
            Attendee.status == "going",           # only count people who are coming
            Attendee.costume_keywords != "",      # only those who submitted keywords
        )
        .all()
    )

    return [a.costume_keywords.split(",") for a in others]
