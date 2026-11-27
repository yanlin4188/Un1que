# Un1que Implementation Summary

## Overview
This document summarizes the complete refactor to implement room code storage, session management, authentication, and API integration.

---

## Backend Changes

### 1. Models (`models.py`)
**Added columns to Party:**
- `ended_at` (DateTime) — Soft delete timestamp

**Added columns to Attendee:**
- `party_id` with `index=True` — Foreign key index
- `password_hash` (String(200)) — For rejoining
- `token` (String(64), unique, indexed) — API authentication
- `is_organizer` (Boolean) — Organizer flag
- `kicked_at` (DateTime) — Soft kick timestamp
- `costume_description` (Text) — Raw description from user

**Updated Attendee relationship:**
- Party.attendees now has `cascade="all, delete-orphan"`

### 2. Repository Functions (`repository.py`)
**Modified existing:**
- `join_party()` — Now upsert (creates or returns existing attendee), accepts password_hash, is_organizer

**New functions:**
- `set_attendee_token(attendee_id, token)` — Set auth token
- `get_attendee_by_token(token)` — Lookup by token
- `save_costume(attendee_id, description, keywords)` — Atomic costume save (description + keywords)
- `kick_attendee(attendee_id)` — Soft kick (marks kicked_at)
- `end_party(party_code)` — Soft end party (marks ended_at)
- `delete_party(party_code)` — Hard delete party + attendees

### 3. Database Migration
Since app uses `db.create_all()` (not Alembic):
1. Delete `instance/party.db` to recreate from scratch, OR
2. Run SQL manually:
   ```sql
   ALTER TABLE party ADD COLUMN ended_at DATETIME;
   ALTER TABLE attendee ADD COLUMN party_id INTEGER;
   ALTER TABLE attendee ADD COLUMN password_hash VARCHAR(200);
   ALTER TABLE attendee ADD COLUMN token VARCHAR(64) UNIQUE;
   ALTER TABLE attendee ADD COLUMN is_organizer BOOLEAN DEFAULT 0;
   ALTER TABLE attendee ADD COLUMN kicked_at DATETIME;
   ALTER TABLE attendee ADD COLUMN costume_description TEXT DEFAULT '';
   CREATE INDEX idx_attendee_party_id ON attendee(party_id);
   CREATE INDEX idx_attendee_token ON attendee(token);
   ```

---

## Frontend Changes

### 1. New Shared Session File (`room_session.js`)
**Provides:**
- `normalize(code)` — Uppercase alphanumeric only ("ABC-123" → "ABC123")
- `format(code)` — Display format ("ABC123" → "ABC-123")
- `save(room)` — Save to localStorage
- `load(code)` — Load from localStorage
- `clear(code)` — Clear from localStorage
- `getCodeFromUrl()` — Read from URL (?code=ABC123)
- `setCodeInUrl(code)` — Write to URL

**Session object structure:**
```js
{
  code: "ABC123",           // Canonical, no dash
  attendeeId: 5,
  token: "token_abc...",
  name: "Alice",
  isOrganizer: true
}
```

### 2. index.html Updates
**Changes:**
- "Create Room" button → opens modal dialog
- Modal captures: party title, organizer name, password
- Posts `POST /api/parties` with `password_hash`
- Returns `party.code` and `token`
- Saves session via `Un1queRoom.save()`
- Navigates to `create_room.html`

**New dependencies:**
- Loads `room_session.js` before inline script

### 3. join_room.html Complete Rewrite
**Changes:**
- Removed hardcoded `roomDatabase`
- Added `guestName` and `guestPassword` inputs
- Code lookup via `GET /api/parties/<code>` (real API)
- Accepts `name + password` to join
- Posts `POST /api/parties/<code>/join`
- Saves session via `Un1queRoom.save()`
- Navigates to `create_room.html`
- Prefills code from URL parameter if present

**Features:**
- 350ms debounce on code lookup to avoid spam
- Abort previous requests if user types quickly
- Password hashing (SHA-256) on client

**Dependencies:**
- Loads `room_session.js` before inline script

### 4. create_room.html + create_room.js
**Completely new flow:**
- Loads `room_session.js` and `create_room.js`
- On load: check session, load from DB
- Renders party code (formatted) and members list
- Shows "End Party" button only if `isOrganizer === true`
- Member badges have kick buttons (organizer only)
- Costume submission includes `token` header
- 5-second polling for member updates + kick detection

**create_room.js functions:**
- `initializeParty()` — Load from session or redirect home
- `loadParty(code)` — Fetch from API
- `renderParty()` — Display code + members
- `addMemberBadge(name, memberId, isOrganizer)` — Add badge with optional kick button
- `kickMember(memberId, name)` — Soft kick via DELETE (organizer only)
- `endParty()` — Hard delete party via DELETE (organizer only)
- `submitCostume()` — Upload + POST to `/api/parties/<code>/judge` with token
- `startPolling()` — Poll every 5s for updates

**Dependencies:**
- Loads `room_session.js` and `create_room.js`

---

## API Endpoints (Backend Routes)

### Party Management
| Method | Route | Auth | Return | Notes |
|--------|-------|------|--------|-------|
| POST | `/api/parties` | None | `{party, attendee, token}` | Create party + organizer |
| GET | `/api/parties/<code>` | None | `{party, members}` | Public room preview |
| DELETE | `/api/parties/<code>` | Token | `{success}` | Organizer hard-deletes |

### Joining
| Method | Route | Auth | Return | Notes |
|--------|-------|------|--------|-------|
| POST | `/api/parties/<code>/join` | None | `{party, attendee, token}` | Upsert join; returns token |

### Attendees
| Method | Route | Auth | Return | Notes |
|--------|-------|------|--------|-------|
| DELETE | `/api/attendees/<id>` | Token | `{success}` | Soft kick |

### Costume
| Method | Route | Auth | Return | Notes |
|--------|-------|------|--------|-------|
| POST | `/api/parties/<code>/judge` | Token | `{score, feedback}` | Calls matcher; saves description + keywords |

---

## Security & Auth

### Password Handling
- **Frontend:** SHA-256 hash sent to backend
- **Backend:** `werkzeug.security.generate_password_hash()` stores salted hash
- **Rejoin:** Compare password vs stored hash on join (upsert)

### Tokens
- **Issue:** On POST `/api/parties` and POST `.../join`
- **Generated:** `secrets.token_urlsafe(24)` on backend
- **Storage:** Attendee.token column
- **Usage:** `X-Attendee-Token: <token>` header on protected routes
- **Refresh:** Tokens persist in localStorage; refresh on each poll/update

### Kicked Attendees
- **Soft kick:** Marks `Attendee.kicked_at`
- **On rejoin:** Check `kicked_at` → 403 "You were removed"
- **On poll:** 404 party → "Party ended", clear session

---

## Flow Diagrams

### Create Party
```
index.html (modal) 
  → POST /api/parties 
  → server: creates Party + Attendee (organizer), issues token
  → frontend: saves session, navigates to create_room.html
  → create_room.js: loads party, renders banner + members
```

### Join Party
```
join_room.html (code input)
  → GET /api/parties/<code> (preview)
  → (if found) display creator + member count
  → user enters name + password
  → POST /api/parties/<code>/join (upsert attendee)
  → server: creates or returns attendee, issues token
  → frontend: saves session, navigates to create_room.html
  → create_room.js: loads party, renders banner + members
```

### Room Session
```
create_room.html
  → create_room.js: load() from Un1queRoom
  → GET /api/parties/<code> → renderParty()
  → startPolling() every 5s
  → user: submit costume → POST with token
  → user (organizer): kick member → DELETE attendee
  → user (organizer): end party → DELETE party
  → polling detects kick/end → clear session, redirect home
```

---

## File Structure
```
d:\GitHub\Un1que\
���── backend\
│   ├── models.py              (Updated: Party.ended_at, Attendee columns)
│   ├── repository.py          (Updated: join upsert, new functions)
│   ├── app.py                 (Needs: new routes, token auth)
│   └── ...
├── frontend\
│   ├── index.html             (Updated: modal dialog for create)
│   ├── join_room.html         (Rewritten: real API + password)
│   ├── create_room.html       (Rewritten: uses create_room.js)
│   ├── room_session.js        (NEW: shared session helpers)
│   ├── create_room.js         (NEW: party loading + polling)
│   ├── style.css              (Unchanged)
│   └── ...
└── IMPLEMENTATION_SUMMARY.md  (this file)
```

---

## Testing Checklist

- [ ] Delete `instance/party.db`; server starts and creates fresh schema
- [ ] Open `http://127.0.0.1:5000/index.html`
- [ ] Click "Create Room" → modal opens
- [ ] Enter name + password → POST `/api/parties` succeeds
- [ ] Session saved; navigate to room page
- [ ] Code displays in banner (formatted ABC-123)
- [ ] In second tab: `http://127.0.0.1:5000/join_room.html`
- [ ] Enter code → GET `/api/parties/<code>` shows creator + members
- [ ] Enter name + password → POST `.../join` succeeds
- [ ] Both tabs show same party code + member list
- [ ] Upload costume (organizer) → POST `.../judge` calls matcher
- [ ] Polling updates member list every 5s
- [ ] Organizer: hover member badge → see kick button ✕
- [ ] Organizer: click kick → DELETE attendee → kicked user gets 403 on next poll
- [ ] Organizer: "End Party" button → DELETE party → both tabs see redirect to home
- [ ] Run backend tests: `python -m pytest backend -q`

---

## Known Limitations & Future Work

1. **Password hashing:** SHA-256 on frontend is simplified; use bcrypt in production
2. **Token refresh:** Tokens never expire; add `expires_at` column + refresh endpoint
3. **Code format:** 6-char codes only; could allow custom vanity codes
4. **Soft deletes:** `ended_at` and `kicked_at` allow "undelete"; can remove if not needed
5. **Polling:** 5s poll = 720 requests/hour; consider WebSocket for real-time
6. **Costume keywords:** Comma-separated string; normalize to separate table if needed
7. **Error handling:** Minimal frontend feedback; add toast/snackbar notifications

---

## Deployment Notes

1. **Dev:** Delete `instance/party.db`, restart Flask, tables auto-create
2. **Prod:** Use Alembic or manual SQL for migrations
3. **CORS:** Relative URLs work; ensure frontend served from same origin as API
4. **File uploads:** Configure Flask `UPLOAD_FOLDER` and `MAX_CONTENT_LENGTH`
5. **Secrets:** Store `SECRET_KEY` in environment, not code

---

## Questions?

Refer to:
- Backend test suite: `backend/tests/` (pytest)
- Google Doc: Detailed design + rationale
- This file: Architecture overview

Enjoy! 🎃
