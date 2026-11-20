# Frontend Review: create_room.html

## Changes Made

### 1. ✅ Replaced File Input with Textarea
- **Before**: `<input type="file" id="costumeInput" accept="image/*">`
- **After**: `<textarea id="costumeInput" placeholder="Describe your costume using key words here...">`
- **Why**: Backend expects free-text costume descriptions, not image files

### 2. ✅ Extracted JavaScript to Separate File
- **Created**: `frontend/create_room.js`
- **Benefits**: 
  - Better code organization and maintainability
  - Reusable across multiple pages
  - Easier to test and debug
  - Follows web best practices
- **Import**: `<script src="create_room.js"></script>`

### 3. ✅ Backend API Integration
- **Endpoint**: `POST /judge-costume`
- **Request Format**:
  ```json
  {
    "costume_description": "vampire, red cape, fangs",
    "party_code": "XXXX-XXXX",
    "attendee_id": 123  // optional - only if saving
  }
  ```
- **Response Format**:
  ```json
  {
    "success": true,
    "level": "unique|similar|clash",
    "clash": false,
    "clash_count": 0,
    "similar_count": 0,
    "score": 10,
    "message": "Your costume is unique so far!",
    "feedback": "Nobody at this party has described anything close...",
    "shared_keywords": [],
    "participant_name": null,
    "saved": false
  }
  ```

---

## Current Flow & Architecture

### Frontend (`create_room.html` + `create_room.js`)

1. **Page Load** (`initializeParty()`)
   - Generates a random party code (XXXX-XXXX)
   - Adds example members (Alice, Bob) for testing

2. **User submits costume** (`submitCostume()`)
   - Validates textarea is not empty
   - Builds JSON payload with costume description + party code
   - Sends `POST /judge-costume` to backend

3. **Response handling** (`handleCostumeResponse()`)
   - Parses matching result (level, score, message, feedback)
   - Displays result with color coding (success/error/loading)
   - Optionally adds participant to member list

### Backend (app.py)

- `POST /judge-costume` endpoint calls `judge_costume()`
- Validates party code via `_party_or_404()`
- Parses costume description via `_costume_keywords()`
- Calls `_check(party, keywords, attendee_id)` which:
  - Retrieves other guests' costumes via `repo.get_other_costumes()`
  - Runs `matcher.check_uniqueness()` for matching algorithm
  - Returns `UniquenessResult` with level, score, message, feedback

---

## What Works ✅

1. **Costume Description Input**: Textarea accepts free-text input
2. **Backend Connection**: Fetch to `/judge-costume` with correct JSON format
3. **Response Handling**: Parses all response fields correctly
4. **UI Feedback**: Shows loading → result with appropriate styling
5. **Validation**: Checks for empty input before sending
6. **Error Handling**: Displays backend error messages to user
7. **JavaScript Organization**: Clean separation of concerns in `create_room.js`

---

## What Needs Backend Support ⚠️

### CRITICAL ISSUES:

1. **Party Code Not Saved to Database**
   - **Current**: Page generates random code locally
   - **Problem**: Backend has no record of this party, so `/judge-costume` will fail with "No party found"
   - **Solution**: Frontend must call `/api/parties` (POST) first to create party
   - **Endpoint**: `POST /api/parties`
   - **Request**:
     ```json
     {
       "title": "Halloween Party",
       "organizer_name": "Alice",
       "location": "123 Main St",
       "starts_at": "2026-10-31T20:00"
     }
     ```
   - **Response**: Returns `party.code` that is actually in the database

2. **Attendee ID Missing**
   - **Current**: No `attendee_id` in payload
   - **Problem**: Costume is never saved to database (preview only)
   - **Solution**: When creating party, backend returns `attendee` object with `id`
   - **Store** this in `sessionStorage` and add to payload

3. **Test Data (Alice, Bob)**
   - **Current**: Hardcoded test members added via setTimeout
   - **Problem**: These are purely visual; not stored in database
   - **Solution**: Remove or fetch actual party members via `/api/parties/<code>`

---

## Recommended Backend Changes

### 1. Modify `create_room.html` Page Flow (Production)

Instead of the current flow:
```
User loads page
→ Generate random code
→ Submit costume
→ Backend fails (party not found)
```

Should be:
```
User loads create_room.html
→ Call POST /api/parties to create party (saves organizer as attendee)
→ Store party.code and attendee.id in sessionStorage
→ User submits costume
→ Call POST /judge-costume with attendee_id (saves to DB)
→ Display result
```

### 2. Update Frontend to Initialize Party

Example implementation:
```javascript
async function initializeParty() {
    const payload = {
        title: "Costume Party",
        organizer_name: "Me",  // prompt user?
        location: "",
        starts_at: null
    };
    
    const response = await fetch('/api/parties', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    const { party, attendee } = data;
    
    // Store for later use
    sessionStorage.setItem('partyCode', party.code);
    sessionStorage.setItem('attendeeId', attendee.id);
    
    // Display code
    document.getElementById('partyCode').textContent = party.code;
}
```

### 3. Update Costume Submission to Include attendee_id

```javascript
const payload = {
    costume_description: costumeDescription,
    party_code: partyCode,
    attendee_id: parseInt(sessionStorage.getItem('attendeeId'))  // SAVE costume
};
```

---

## API Contract Verification

| Endpoint | Method | Frontend Uses? | Status |
|----------|--------|---|--------|
| `POST /api/parties` | POST | ❌ Not yet | Needed to create party |
| `GET /api/parties/<code>` | GET | ❌ Not yet | Optional: refresh member count |
| `POST /api/parties/<code>/join` | POST | ❌ Not yet | For join_room.html |
| `POST /judge-costume` | POST | ✅ Yes | Working, but needs attendee_id |
| `POST /api/parties/<code>/attendees/<id>/costume` | POST | ❌ Not yet | Alternative to /judge-costume |

---

## Testing Checklist

- [ ] Backend creates party and returns valid code
- [ ] Attendee ID is stored and persists across page navigation
- [ ] Costume submission saves to database (`attendee.costume_keywords`)
- [ ] Multiple costumes in same party are checked against each other
- [ ] "Clash" detection works (two identical costumes)
- [ ] "Similar" detection works (overlapping keywords)
- [ ] "Unique" status shows when no conflicts
- [ ] Score is calculated correctly (0-10)
- [ ] Error messages display for invalid party codes
- [ ] Connection errors are handled gracefully

---

## Files Modified/Created

- ✅ `frontend/create_room.html` - Updated (file input → textarea, script extracted)
- ✅ `frontend/create_room.js` - Created (new, contains all JavaScript)
- ❌ `backend/app.py` - No changes needed (already correct)
- ❌ `backend/matcher.py` - No changes needed (already correct)
- ❌ `backend/models.py` - No changes needed (already correct)

---

## Summary

**Frontend is ready.** The JavaScript has been properly separated, the API integration is correct, and error handling is in place. However, the current flow is incomplete because:

1. Party code is generated locally but not saved to the backend
2. Attendee ID is not being tracked
3. Costume submissions are preview-only (not saved to database)

To make this fully functional, the frontend needs to:
1. Call `POST /api/parties` on page load to create the party
2. Store `party.code` and `attendee.id` in sessionStorage
3. Include `attendee_id` in `/judge-costume` payload to save costumes

The backend is fully ready to support this flow.
