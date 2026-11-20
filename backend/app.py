"""
app.py — Flask entry point for Un1que.

Run (from the repo root):
    python backend/app.py
then open http://127.0.0.1:5000/  (the frontend/ folder is served from /)

The database is SQLite at instance/party.db, created on first start.
Set DATABASE_URL to use another database (e.g. PostgreSQL when deploying).

API conventions
---------------
* JSON in, JSON out. Every response has "success": true/false.
* Errors: {"success": false, "message": "..."} with a 4xx status.
* Party codes are case-insensitive and dashes/spaces are ignored,
  so "a3kz-91" and "A3KZ91" are the same party.
* Other guests' costumes are never returned. Costume checks only say
  whether, and how many, other guests are similar.

Endpoints
---------
GET   /api/health
POST  /api/parties                                  create party (+ organizer as first guest)
          {"title", "organizer_name", "location"?, "starts_at"? (ISO 8601)}
          -> 201 {"party": {...}, "attendee": {"id", "name", "status"}}
GET   /api/parties/<code>                           party details page / code check
          -> {"party": {..., "member_count", "members": [{"name", "status", "has_costume"}]}}
POST  /api/parties/<code>/join                      {"name"} -> 201 {"party", "attendee"}
PATCH /api/parties/<code>/attendees/<id>/rsvp       {"status": "going" | "not_going"}
POST  /api/parties/<code>/attendees/<id>/costume    save + check costume
          {"keywords": ["vampire", "red cape"]}  or  {"description": "vampire, red cape"}
          -> {"result": {"level", "clash", "clash_count", "similar_count",
                         "score", "message", "feedback", "shared_keywords"}}
GET   /api/parties/<code>/attendees/<id>/costume    re-check the saved costume
POST  /judge-costume                                what frontend/create_room.html calls today
          {"costume_description", "party_code", "attendee_id"?}
          -> {"success", "message", "score", "feedback", "level", "clash", ...}
          With attendee_id the costume is saved; without it this is a
          check-only preview against everyone already in the party.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import matcher
import repository as repo
from database import db
from models import Attendee, Party

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
INSTANCE_DIR = ROOT_DIR / "instance"

# Column sizes from models.py
MAX_TITLE = 120
MAX_NAME = 80
MAX_LOCATION = 200
MAX_COSTUME_DESCRIPTION = 400
MAX_STORED_KEYWORDS = 500  # Attendee.costume_keywords is String(500)

API_PATH_PREFIXES = ("/api/", "/judge-costume")


# ---------------------------------------------------------------------------
# Errors and responses
# ---------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def ok(status: int = 200, **data):
    return jsonify({"success": True, **data}), status


def fail(message: str, status: int):
    return jsonify({"success": False, "message": message}), status


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ApiError("request body must be a JSON object")
    return data


def _text(data: dict, key: str, max_len: int, required: bool = True) -> str | None:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(f"'{key}' is required")
        return None
    if not isinstance(value, str):
        raise ApiError(f"'{key}' must be a string")
    value = " ".join(value.split())
    if len(value) > max_len:
        raise ApiError(f"'{key}' must be at most {max_len} characters")
    return value


def _datetime(data: dict, key: str) -> datetime | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ApiError(f"'{key}' must be an ISO 8601 date-time string")
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise ApiError(f"'{key}' must be an ISO 8601 date-time, e.g. 2026-10-31T20:00")
    if dt.tzinfo is not None:  # store naive UTC; SQLite has no time zones
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def clean_code(code: str) -> str:
    """'a3kz-91 ' -> 'A3KZ91'"""
    return re.sub(r"[^A-Za-z0-9]", "", code or "").upper()


def _costume_keywords(data: dict) -> list[str]:
    """Keywords from {"keywords": [...]} or a free-text description field."""
    try:
        if data.get("keywords") is not None:
            keywords = matcher.clean_keywords(data["keywords"])
        else:
            text = data.get("description", data.get("costume_description"))
            if not isinstance(text, str) or not text.strip():
                raise ApiError("describe your costume first ('keywords' or 'description')")
            if len(text) > MAX_COSTUME_DESCRIPTION:
                raise ApiError(f"costume description must be at most {MAX_COSTUME_DESCRIPTION} characters")
            keywords = matcher.parse_keywords(text)
    except ValueError as exc:
        raise ApiError(str(exc))
    if len(",".join(keywords)) > MAX_STORED_KEYWORDS:
        raise ApiError("costume description is too long")
    return keywords


# ---------------------------------------------------------------------------
# Lookups and serialisation
# ---------------------------------------------------------------------------

def _party_or_404(code: str) -> Party:
    party = repo.get_party_by_code(clean_code(code))
    if party is None:
        raise ApiError("No party found with that code", 404)
    return party


def _attendee_or_404(party: Party, attendee_id) -> Attendee:
    try:
        attendee_id = int(attendee_id)
    except (TypeError, ValueError):
        raise ApiError("'attendee_id' must be a number")
    attendee = db.session.get(Attendee, attendee_id)
    if attendee is None or attendee.party_id != party.id:
        raise ApiError("No guest with that id in this party", 404)
    return attendee


def attendee_to_dict(a: Attendee) -> dict:
    """Your own guest record. Never includes costume keywords."""
    return {"id": a.id, "name": a.name, "status": a.status, "has_costume": bool(a.costume_keywords)}


def party_to_dict(p: Party) -> dict:
    """Public party info. Lists guests by name only: no ids, no costumes."""
    attendees = sorted(p.attendees, key=lambda a: a.id)
    return {
        "code": p.code,
        "title": p.title,
        "organizer_name": p.organizer_name,
        "location": p.location,
        "starts_at": p.starts_at.isoformat() if p.starts_at else None,
        "member_count": sum(1 for a in attendees if a.status == "going"),
        "members": [
            {"name": a.name, "status": a.status, "has_costume": bool(a.costume_keywords)}
            for a in attendees
        ],
    }


def _check(party: Party, keywords: list[str], exclude_attendee_id: int | None) -> matcher.UniquenessResult:
    # Ids start at 1, so 0 excludes nobody (check-only preview).
    others = repo.get_other_costumes(party.code, exclude_attendee_id or 0)
    try:
        return matcher.check_uniqueness(keywords, others)
    except ValueError as exc:
        raise ApiError(str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health():
    return ok(service="un1que")


@api.post("/parties")
def create_party():
    data = _json_body()
    title = _text(data, "title", MAX_TITLE)
    organizer = _text(data, "organizer_name", MAX_NAME)
    location = _text(data, "location", MAX_LOCATION, required=False)
    starts_at = _datetime(data, "starts_at")

    party = repo.create_party(title, organizer, location=location, starts_at=starts_at)
    organizer_guest = repo.join_party(party.code, organizer)  # organizer wears a costume too
    return ok(201, party=party_to_dict(party), attendee=attendee_to_dict(organizer_guest))


@api.get("/parties/<code>")
def get_party(code):
    return ok(party=party_to_dict(_party_or_404(code)))


@api.post("/parties/<code>/join")
def join_party(code):
    party = _party_or_404(code)
    name = _text(_json_body(), "name", MAX_NAME)
    attendee = repo.join_party(party.code, name)
    return ok(201, party=party_to_dict(party), attendee=attendee_to_dict(attendee))


@api.route("/parties/<code>/attendees/<int:attendee_id>/rsvp", methods=["PATCH", "PUT", "POST"])
def update_rsvp(code, attendee_id):
    party = _party_or_404(code)
    attendee = _attendee_or_404(party, attendee_id)
    status = _text(_json_body(), "status", 20)
    if status not in ("going", "not_going"):
        raise ApiError("'status' must be 'going' or 'not_going'")
    attendee = repo.update_rsvp(attendee.id, status)
    return ok(attendee=attendee_to_dict(attendee))


@api.route("/parties/<code>/attendees/<int:attendee_id>/costume", methods=["POST", "PUT"])
def submit_costume(code, attendee_id):
    party = _party_or_404(code)
    attendee = _attendee_or_404(party, attendee_id)
    keywords = _costume_keywords(_json_body())
    repo.save_costume_keywords(attendee.id, keywords)
    result = _check(party, keywords, attendee.id)
    return ok(attendee=attendee_to_dict(attendee), result=result.to_dict())


@api.get("/parties/<code>/attendees/<int:attendee_id>/costume")
def recheck_costume(code, attendee_id):
    """Guests who joined later may now clash, so the frontend can poll this."""
    party = _party_or_404(code)
    attendee = _attendee_or_404(party, attendee_id)
    if not attendee.costume_keywords:
        raise ApiError("You haven't submitted a costume yet", 404)
    keywords = attendee.costume_keywords.split(",")
    result = _check(party, keywords, attendee.id)
    return ok(attendee=attendee_to_dict(attendee), result=result.to_dict())


def judge_costume():
    """Contract used by frontend/create_room.html (submitCostume)."""
    data = _json_body()
    party = _party_or_404(data.get("party_code") or "")
    keywords = _costume_keywords(data)

    attendee = None
    if data.get("attendee_id") not in (None, ""):
        attendee = _attendee_or_404(party, data["attendee_id"])
        repo.save_costume_keywords(attendee.id, keywords)

    result = _check(party, keywords, attendee.id if attendee else None)
    return ok(
        participant_name=attendee.name if attendee else None,
        saved=attendee is not None,
        **result.to_dict(),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///party.db")
    # Heroku/Render style URLs; SQLAlchemy wants "postgresql://"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def create_app(config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="",          # frontend/style.css -> /style.css
        instance_path=str(INSTANCE_DIR),
    )
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=_database_url(),  # relative sqlite path -> instance/
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_AS_ASCII=False,
    )
    if config:
        app.config.update(config)

    INSTANCE_DIR.mkdir(exist_ok=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(api)
    app.add_url_rule("/judge-costume", "judge_costume", judge_costume, methods=["POST"])

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return fail(exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith(API_PATH_PREFIXES):
            return fail(exc.description or exc.name, exc.code or 500)
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        if isinstance(exc, HTTPException):
            return handle_http_error(exc)
        db.session.rollback()
        app.logger.exception("Unhandled error")
        if request.path.startswith(API_PATH_PREFIXES):
            return fail("Something went wrong on the server", 500)
        raise exc

    @app.after_request
    def allow_cross_origin(response):
        # Lets the frontend call the API when opened from another dev server
        # (e.g. VS Code Live Server on :5500). There are no cookies, so * is fine.
        if request.path.startswith(API_PATH_PREFIXES):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, OPTIONS"
        return response

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
