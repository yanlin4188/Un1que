"""
models.py
---------
ORM table definitions for Party and Attendee.
"""

from database import db


class Party(db.Model):
    __tablename__ = "party"

    id             = db.Column(db.Integer, primary_key=True)
    # Unique invite code shown to users (e.g. "ABC123")
    code           = db.Column(db.String(20), unique=True, nullable=False)
    title          = db.Column(db.String(120), nullable=False)
    organizer_name = db.Column(db.String(80), nullable=False)
    location       = db.Column(db.String(200))
    starts_at      = db.Column(db.DateTime)
    ended_at       = db.Column(db.DateTime)  # Soft delete; NULL = active

    # Backref lets us do party.attendees to get the list of Attendee rows.
    # cascade="all, delete-orphan" ensures attendees are deleted when party is deleted
    attendees = db.relationship("Attendee", backref="party", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Party {self.code!r} – {self.title!r}>"


class Attendee(db.Model):
    __tablename__ = "attendee"

    id       = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False, index=True)
    name     = db.Column(db.String(80), nullable=False)
    # "going" or "not_going"
    status   = db.Column(db.String(20), nullable=False, default="going")
    # Password hash for rejoining from another device
    password_hash = db.Column(db.String(200), nullable=False, default="")
    # Authentication token for API calls
    token    = db.Column(db.String(64), unique=True, index=True)
    # Is this attendee the organizer?
    is_organizer = db.Column(db.Boolean, nullable=False, default=False)
    # Timestamp of when this attendee was kicked (NULL = not kicked)
    kicked_at = db.Column(db.DateTime)
    # Comma-separated costume keywords, e.g. "vampire,cape,red"
    # Kept in the DB only for internal matching – never sent to other users.
    costume_keywords = db.Column(db.String(500), default="")
    # Raw costume description as typed by the user
    costume_description = db.Column(db.Text, default="")

    def __repr__(self):
        return f"<Attendee {self.name!r} party={self.party_id} status={self.status!r}>"
