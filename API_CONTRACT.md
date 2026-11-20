# API Contract: Frontend ↔ Backend

## Current State: What Frontend Can Call Now ✅

### Endpoint: POST /judge-costume
**Purpose**: Submit costume description and get matching result against other guests

**Request**:
```json
{
  "costume_description": "vampire, red cape, fangs",
  "party_code": "A3KZ91",
  "attendee_id": null
}
```

**Response** (Success):
```json
{
  "success": true,
  "level": "unique",
  "clash": false,
  "clash_count": 0,
  "similar_count": 0,
  "score": 10,
  "message": "Your costume is unique so far!",
  "feedback": "Nobody at this party has described anything close. We'll keep checking as more guests join.",
  "shared_keywords": [],
  "participant_name": null,
  "saved": false
}
```

**Response** (Error):
```json
{
  "success": false,
  "message": "No party found with that code"
}
```

**What Happens**:
- ✅ Validates party code exists
- ✅ Parses costume description into keywords
- ✅ Gets all other guests' costume keywords
- ✅ Runs matching algorithm
- ✅ Returns result (does NOT save costume)

**Current Frontend Usage**:
```javascript
const payload = {
    costume_description: textInput.value.trim(),
    party_code: document.getElementById('partyCode').textContent
};

fetch('/judge-costume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
})
```

---

## What's Missing: Party Creation ⚠️

### Endpoint: POST /api/parties
**Purpose**: Create a new party and register the organizer as first attendee

**Request**:
```json
{
  "title": "Halloween Party",
  "organizer_name": "Alice",
  "location": "123 Main St",
  "starts_at": "2026-10-31T20:00:00"
}
```

**Response**:
```json
{
  "success": true,
  "party": {
    "code": "A3KZ91",
    "title": "Halloween Party",
    "organizer_name": "Alice",
    "location": "123 Main St",
    "starts_at": "2026-10-31T20:00:00",
    "member_count": 1,
    "members": [
      {
        "name": "Alice",
        "status": "going",
        "has_costume": false
      }
    ]
  },
  "attendee": {
    "id": 1,
    "name": "Alice",
    "status": "going",
    "has_costume": false
  }
}
```

**What Frontend Should Do**:
1. Call this endpoint when user clicks "Create Room"
2. Store `party.code` in sessionStorage
3. Store `attendee.id` in sessionStorage
4. Display `party.code` in the banner
5. Use stored `attendee.id` in future `/judge-costume` calls

**Proposed Frontend Code**:
```javascript
async function createParty() {
    const organizer = prompt("Enter your name:");
    
    const payload = {
        title: "Costume Party",
        organizer_name: organizer,
        location: "",
        starts_at: null
    };
    
    const response = await fetch('/api/parties', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    
    if (data.success) {
        sessionStorage.setItem('partyCode', data.party.code);
        sessionStorage.setItem('attendeeId', data.attendee.id);
        document.getElementById('partyCode').textContent = data.party.code;
    }
}
```

---

## What Else is Available (For Full Integration)

### Endpoint: GET /api/parties/<code>
**Purpose**: Get party details and current members

**Response**:
```json
{
  "success": true,
  "party": {
    "code": "A3KZ91",
    "title": "Halloween Party",
    "organizer_name": "Alice",
    "location": "123 Main St",
    "starts_at": "2026-10-31T20:00:00",
    "member_count": 2,
    "members": [
      { "name": "Alice", "status": "going", "has_costume": false },
      { "name": "Bob", "status": "going", "has_costume": true }
    ]
  }
}
```

**Use Case**: Refresh member list, show who has submitted costumes

---

### Endpoint: POST /api/parties/<code>/join
**Purpose**: Add a new attendee to an existing party

**Request**:
```json
{
  "name": "Bob"
}
```

**Response**:
```json
{
  "success": true,
  "party": { ... },
  "attendee": {
    "id": 2,
    "name": "Bob",
    "status": "going",
    "has_costume": false
  }
}
```

**Use Case**: Used by `join_room.html` to register a new guest

---

### Endpoint: POST /judge-costume (with attendee_id)
**Purpose**: Check costume AND save it to the database

**Request**:
```json
{
  "costume_description": "vampire, red cape",
  "party_code": "A3KZ91",
  "attendee_id": 1
}
```

**Response**:
```json
{
  "success": true,
  "level": "unique",
  "score": 10,
  "message": "Your costume is unique so far!",
  "feedback": "...",
  "participant_name": "Alice",
  "saved": true
}
```

**Key Difference**: With `attendee_id`, the costume is saved to `attendee.costume_keywords`

---

## Full Integration Flow

```
User opens create_room.html
         ↓
JavaScript runs window.load event
         ↓
Calls: POST /api/parties
         ↓
Stores party.code and attendee.id in sessionStorage
         ↓
Displays party code in banner ✅
         ↓
User types costume description
         ↓
Clicks "Submit for Judgment"
         ↓
Calls: POST /judge-costume
  {
    costume_description: "...",
    party_code: sessionStorage.partyCode,
    attendee_id: sessionStorage.attendeeId  ← KEY ADDITION
  }
         ↓
Backend saves costume_keywords to database ✅
         ↓
Backend checks against other guests
         ↓
Returns result with score/feedback
         ↓
UI displays result ✅
         ↓
Attendee's costume is now saved!
```

---

## Error Codes & Messages

| Scenario | HTTP | Message |
|----------|------|---------|
| Invalid JSON | 400 | "request body must be a JSON object" |
| Missing required field | 400 | "'title' is required" |
| Party not found | 404 | "No party found with that code" |
| Attendee not found | 404 | "No guest with that id in this party" |
| Invalid costume description | 400 | "describe your costume with at least one keyword" |
| Costume too long | 400 | "costume description must be at most 400 characters" |
| Server error | 500 | "Something went wrong on the server" |

---

## CORS Headers (for development)

All `/api/` and `/judge-costume` endpoints return:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, OPTIONS
```

This allows frontend served from different port to call the API during development.

---

## Summary

| What | Status | Integrated? |
|------|--------|-------------|
| POST /judge-costume (check only) | ✅ Working | Partially |
| POST /api/parties (create) | ✅ Ready | ❌ Not called |
| GET /api/parties/<code> | ✅ Ready | ❌ Optional |
| POST /api/parties/<code>/join | ✅ Ready | ❌ Not called (for join_room.html) |
| POST /judge-costume (with save) | ✅ Ready | ❌ attendee_id not included |

**Next action**: Update frontend to call `/api/parties` on page load, then include `attendee_id` in `/judge-costume` calls.
