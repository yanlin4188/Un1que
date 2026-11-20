"""
test_app.py — API tests against an in-memory database.
Run with:  python -m pytest backend -v
"""

import pytest

from app import create_app
from database import db


@pytest.fixture
def client():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
    with app.app_context():
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def make_party(client, **overrides):
    body = {"title": "Halloween Bash", "organizer_name": "Alice", "location": "123 Main St",
            "starts_at": "2026-10-31T20:00"} | overrides
    res = client.post("/api/parties", json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def join(client, code, name):
    res = client.post(f"/api/parties/{code}/join", json={"name": name})
    assert res.status_code == 201, res.get_json()
    return res.get_json()["attendee"]


def submit(client, code, attendee_id, **body):
    return client.post(f"/api/parties/{code}/attendees/{attendee_id}/costume", json=body)


# --- parties -----------------------------------------------------------------

def test_create_party_adds_organizer_as_guest(client):
    data = make_party(client)
    assert data["success"] is True
    party = data["party"]
    assert len(party["code"]) == 6
    assert party["organizer_name"] == "Alice"
    assert party["starts_at"] == "2026-10-31T20:00:00"
    assert party["member_count"] == 1
    assert data["attendee"]["name"] == "Alice"


@pytest.mark.parametrize("body", [{}, {"title": "x"}, {"title": " ", "organizer_name": "A"},
                                  {"title": "x", "organizer_name": "A", "starts_at": "tomorrow"},
                                  {"title": "x" * 200, "organizer_name": "A"}])
def test_create_party_validation(client, body):
    res = client.post("/api/parties", json=body)
    assert res.status_code == 400
    assert res.get_json()["success"] is False
    assert res.get_json()["message"]


def test_get_party_ignores_case_and_dashes(client):
    code = make_party(client)["party"]["code"]
    messy = (code[:4] + "-" + code[4:]).lower()
    res = client.get(f"/api/parties/{messy}")
    assert res.status_code == 200
    assert res.get_json()["party"]["code"] == code


def test_unknown_party_is_json_404(client):
    res = client.get("/api/parties/ZZZZZZ")
    assert res.status_code == 404
    assert res.get_json() == {"success": False, "message": "No party found with that code"}


def test_unknown_api_route_is_json(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.get_json()["success"] is False


def test_join_and_member_list_hides_costumes(client):
    code = make_party(client)["party"]["code"]
    bob = join(client, code, "Bob")
    submit(client, code, bob["id"], description="vampire, secret cape")

    party = client.get(f"/api/parties/{code}").get_json()["party"]
    assert [mem["name"] for mem in party["members"]] == ["Alice", "Bob"]
    assert party["members"][1]["has_costume"] is True
    assert "secret" not in str(party)
    assert "id" not in party["members"][0]


def test_rsvp(client):
    code = make_party(client)["party"]["code"]
    bob = join(client, code, "Bob")
    res = client.patch(f"/api/parties/{code}/attendees/{bob['id']}/rsvp", json={"status": "not_going"})
    assert res.get_json()["attendee"]["status"] == "not_going"
    assert client.get(f"/api/parties/{code}").get_json()["party"]["member_count"] == 1

    bad = client.patch(f"/api/parties/{code}/attendees/{bob['id']}/rsvp", json={"status": "maybe"})
    assert bad.status_code == 400


def test_attendee_must_belong_to_party(client):
    code_a = make_party(client)["party"]["code"]
    data_b = make_party(client, organizer_name="Zed")
    res = submit(client, code_a, data_b["attendee"]["id"], keywords=["ghost"])
    assert res.status_code == 404


# --- costume matching ----------------------------------------------------------

def test_costume_flow_unique_then_clash(client):
    data = make_party(client)
    code, alice = data["party"]["code"], data["attendee"]
    bob = join(client, code, "Bob")

    first = submit(client, code, alice["id"], description="Spider-Man, red suit").get_json()
    assert first["result"]["level"] == "unique"

    second = submit(client, code, bob["id"], keywords=["spiderman", "red suit"]).get_json()
    assert second["result"]["level"] == "clash"
    assert second["result"]["clash_count"] == 1

    # Alice re-checks later and now sees the clash too
    recheck = client.get(f"/api/parties/{code}/attendees/{alice['id']}/costume").get_json()
    assert recheck["result"]["clash"] is True


def test_not_going_guests_are_ignored(client):
    data = make_party(client)
    code, alice = data["party"]["code"], data["attendee"]
    bob = join(client, code, "Bob")
    submit(client, code, bob["id"], keywords=["ghost"])
    client.patch(f"/api/parties/{code}/attendees/{bob['id']}/rsvp", json={"status": "not_going"})

    res = submit(client, code, alice["id"], keywords=["ghost"]).get_json()
    assert res["result"]["level"] == "unique"


def test_costume_validation(client):
    data = make_party(client)
    code, alice = data["party"]["code"], data["attendee"]
    assert submit(client, code, alice["id"]).status_code == 400
    assert submit(client, code, alice["id"], description="!!!").status_code == 400
    assert submit(client, code, alice["id"], keywords="ghost").status_code == 400
    assert submit(client, code, alice["id"], description="x" * 401).status_code == 400


def test_recheck_without_costume(client):
    data = make_party(client)
    res = client.get(f"/api/parties/{data['party']['code']}/attendees/{data['attendee']['id']}/costume")
    assert res.status_code == 404


# --- /judge-costume (frontend/create_room.html contract) -----------------------

def test_judge_costume_preview_does_not_save(client):
    data = make_party(client)
    code, alice = data["party"]["code"], data["attendee"]
    submit(client, code, alice["id"], keywords=["witch", "broom"])

    res = client.post("/judge-costume", json={"costume_description": "Witch, broom", "party_code": code})
    body = res.get_json()
    assert res.status_code == 200
    assert body["success"] is True
    assert body["level"] == "clash"
    assert body["saved"] is False
    assert isinstance(body["score"], int)
    assert body["message"] and body["feedback"]


def test_judge_costume_with_attendee_saves(client):
    data = make_party(client)
    code = data["party"]["code"]
    bob = join(client, code, "Bob")
    res = client.post("/judge-costume", json={"costume_description": "ghost",
                                              "party_code": code, "attendee_id": bob["id"]})
    body = res.get_json()
    assert body["saved"] is True
    assert body["participant_name"] == "Bob"
    party = client.get(f"/api/parties/{code}").get_json()["party"]
    assert party["members"][1]["has_costume"] is True


def test_judge_costume_bad_code(client):
    res = client.post("/judge-costume", json={"costume_description": "ghost", "party_code": "XXXX-XXXX"})
    assert res.status_code == 404
    assert res.get_json()["success"] is False


# --- static frontend -----------------------------------------------------------

def test_serves_frontend(client):
    assert b"Un1que" in client.get("/").data
    assert client.get("/style.css").status_code == 200
    assert client.get("/join_room.html").status_code == 200
