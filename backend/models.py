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

    # Backref lets us do party.attendees to get the list of Attendee rows.
    attendees = db.relationship("Attendee", backref="party", lazy=True)

    def __repr__(self):
        return f"<Party {self.code!r} – {self.title!r}>"


class Attendee(db.Model):
    __tablename__ = "attendee"

    id       = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=False)
    name     = db.Column(db.String(80), nullable=False)
    # "going" or "not_going"
    status   = db.Column(db.String(20), nullable=False, default="going")
    # Comma-separated costume keywords, e.g. "vampire,cape,red"
    # Kept in the DB only for internal matching – never sent to other users.
    costume_keywords = db.Column(db.String(500), default="")

    def __repr__(self):
        return f"<Attendee {self.name!r} party={self.party_id} status={self.status!r}>"
