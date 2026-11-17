"""
test_repository.py
------------------
Simple tests for the database layer.
Run with:  python -m pytest test_repository.py -v
Each test uses a fresh in-memory SQLite database so nothing persists between runs.
"""

import pytest
from flask import Flask

from database import db
from models import Party, Attendee
import repository as repo


# ---------------------------------------------------------------------------
# Shared test fixture — fresh in-memory DB for every test
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal Flask app backed by an in-memory SQLite database."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True

    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ---------------------------------------------------------------------------
# Party tests
# ---------------------------------------------------------------------------

def test_create_party_returns_party_with_code(app):
    with app.app_context():
        party = repo.create_party("Halloween Bash", "Alice", location="123 Main St")
        assert isinstance(party, Party)
        assert len(party.code) == 6
        assert party.title == "Halloween Bash"
        assert party.organizer_name == "Alice"
        assert party.location == "123 Main St"


def test_create_party_generates_unique_codes(app):
    with app.app_context():
        p1 = repo.create_party("Party 1", "Alice")
        p2 = repo.create_party("Party 2", "Bob")
        assert p1.code != p2.code


def test_get_party_by_code_found(app):
    with app.app_context():
        created = repo.create_party("Spooky Night", "Carol")
        found = repo.get_party_by_code(created.code)
        assert found is not None
        assert found.id == created.id


def test_get_party_by_code_case_insensitive(app):
    with app.app_context():
        created = repo.create_party("Spooky Night", "Carol")
        found = repo.get_party_by_code(created.code.lower())
        assert found is not None


def test_get_party_by_code_not_found(app):
    with app.app_context():
        result = repo.get_party_by_code("ZZZZZZ")
        assert result is None


# ---------------------------------------------------------------------------
# Attendee / join tests
# ---------------------------------------------------------------------------

def test_join_party_creates_attendee(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        attendee = repo.join_party(party.code, "Bob")
        assert isinstance(attendee, Attendee)
        assert attendee.name == "Bob"
        assert attendee.status == "going"
        assert attendee.party_id == party.id


def test_join_party_invalid_code_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="No party found"):
            repo.join_party("BADCOD", "Bob")


# ---------------------------------------------------------------------------
# RSVP tests
# ---------------------------------------------------------------------------

def test_update_rsvp_to_not_going(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        attendee = repo.join_party(party.code, "Bob")
        updated = repo.update_rsvp(attendee.id, "not_going")
        assert updated.status == "not_going"


def test_update_rsvp_invalid_status_raises(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        attendee = repo.join_party(party.code, "Bob")
        with pytest.raises(ValueError, match="Invalid status"):
            repo.update_rsvp(attendee.id, "maybe")


def test_update_rsvp_nonexistent_attendee_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="No attendee found"):
            repo.update_rsvp(999, "going")


# ---------------------------------------------------------------------------
# Costume keyword tests
# ---------------------------------------------------------------------------

def test_save_costume_keywords(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        attendee = repo.join_party(party.code, "Bob")
        updated = repo.save_costume_keywords(attendee.id, ["Vampire", "Cape", " Red "])
        # Should be lowercase and trimmed
        assert updated.costume_keywords == "vampire,cape,red"


def test_save_costume_keywords_overwrites_previous(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        attendee = repo.join_party(party.code, "Bob")
        repo.save_costume_keywords(attendee.id, ["vampire", "cape"])
        updated = repo.save_costume_keywords(attendee.id, ["pirate"])
        assert updated.costume_keywords == "pirate"


def test_save_costume_keywords_nonexistent_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="No attendee found"):
            repo.save_costume_keywords(999, ["vampire"])


# ---------------------------------------------------------------------------
# get_other_costumes tests
# ---------------------------------------------------------------------------

def test_get_other_costumes_excludes_self(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        bob   = repo.join_party(party.code, "Bob")
        carol = repo.join_party(party.code, "Carol")

        repo.save_costume_keywords(bob.id,   ["vampire", "cape"])
        repo.save_costume_keywords(carol.id, ["witch", "hat"])

        # Bob asks for others — should only see Carol's keywords
        others = repo.get_other_costumes(party.code, bob.id)
        assert len(others) == 1
        assert others[0] == ["witch", "hat"]


def test_get_other_costumes_excludes_not_going(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        bob   = repo.join_party(party.code, "Bob")
        carol = repo.join_party(party.code, "Carol")

        repo.save_costume_keywords(bob.id,   ["vampire"])
        repo.save_costume_keywords(carol.id, ["witch"])
        repo.update_rsvp(carol.id, "not_going")

        others = repo.get_other_costumes(party.code, bob.id)
        assert others == []   # Carol is not going, so excluded


def test_get_other_costumes_excludes_no_keywords(app):
    with app.app_context():
        party = repo.create_party("Bash", "Alice")
        bob   = repo.join_party(party.code, "Bob")
        _dave = repo.join_party(party.code, "Dave")   # Dave never sets keywords

        repo.save_costume_keywords(bob.id, ["vampire"])

        others = repo.get_other_costumes(party.code, bob.id)
        assert others == []   # Dave has no keywords yet


def test_get_other_costumes_invalid_code_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="No party found"):
            repo.get_other_costumes("BADCOD", 1)
