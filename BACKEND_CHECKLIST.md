# Backend Checklist: What's Needed

## ✅ Already Implemented in Backend

### Core Infrastructure
- [x] SQLite database with Party and Attendee models
- [x] Party code generation and storage
- [x] Attendee creation and RSVP tracking
- [x] Costume keyword parsing and normalization
- [x] Costume matching algorithm (clash/similar/unique detection)
- [x] Score calculation and feedback generation

### API Endpoints
- [x] `POST /api/parties` - Create party + organizer
- [x] `GET /api/parties/<code>` - Get party details and members
- [x] `POST /api/parties/<code>/join` - Add new attendee
- [x] `PATCH /api/parties/<code>/attendees/<id>/rsvp` - Update RSVP status
- [x] `POST /api/parties/<code>/attendees/<id>/costume` - Submit & check costume
- [x] `GET /api/parties/<code>/attendees/<id>/costume` - Re-check saved costume
- [x] `POST /judge-costume` - Legacy endpoint (supports create_room.html)

### Error Handling
- [x] Validation for all inputs
- [x] Proper HTTP status codes (201, 400, 404, 500)
- [x] JSON error responses with messages
- [x] CORS headers for cross-origin development

---

## ❌ Missing: Frontend Integration Points

### What Frontend Needs to Call

1. **On Page Load** (create_room.html)
   ```
   POST /api/parties
   {
     "title": "...",
     "organizer_name": "...",
     "location": "...",
     "starts_at": "2026-10-31T20:00"
   }
   → Store party.code and attendee.id
   ```

2. **Get Current Party** (optional refresh)
   ```
   GET /api/parties/{party_code}
   → Update member list UI
   ```

3. **Submit Costume** (on button click)
   ```
   POST /judge-costume
   {
     "costume_description": "...",
     "party_code": "...",
     "attendee_id": 123  ← ADD THIS
   }
   ```

4. **Join Room** (join_room.html)
   ```
   POST /api/parties/{code}/join
   {
     "name": "..."
   }
   → Get attendee.id back
   ```

---

## Optional Enhancements (Not Required Now)

- [ ] Real-time updates via WebSocket (polling works for MVP)
- [ ] Polling mechanism to detect new guests and re-check costume
- [ ] Organizer admin interface to manage party
- [ ] Per-attendee costume history
- [ ] Photo-based matching (would need image processing)

---

## Current State

**Backend**: ✅ 100% Ready - All endpoints working, proper validation, correct matching logic

**Frontend**: 🟡 70% Ready
- ✅ UI design complete
- ✅ Textarea input working
- ✅ JavaScript organized cleanly
- ✅ API calls structured correctly
- ❌ Party creation not implemented
- ❌ Attendee ID not tracked
- ❌ Costumes not being saved to database

---

## What Will Happen When Frontend is Complete

1. User loads `create_room.html`
2. JavaScript calls `POST /api/parties` → gets party code & attendee ID
3. Code displays in banner: `XXXX-XXXX`
4. User describes costume and clicks submit
5. JavaScript calls `POST /judge-costume` with **attendee_id**
6. Backend saves costume keywords to database
7. Backend checks against other guests' costumes
8. Returns match result (unique/similar/clash)
9. User sees score, feedback, and shared keywords
10. Name added to "Party Members" list
11. When other guests join and submit costumes, they also get checked

---

## Testing the Backend Now

```bash
# Start the backend
cd backend
python app.py

# In another terminal, test the API:

# 1. Create a party
curl -X POST http://127.0.0.1:5000/api/parties \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Halloween",
    "organizer_name": "Alice",
    "location": "123 Main St"
  }'

# Response:
# {
#   "success": true,
#   "party": { "code": "A3KZ91", ... },
#   "attendee": { "id": 1, "name": "Alice", ... }
# }

# 2. Join the party
curl -X POST http://127.0.0.1:5000/api/parties/A3KZ91/join \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob"}'

# 3. Submit costume (Alice)
curl -X POST http://127.0.0.1:5000/api/parties/A3KZ91/attendees/1/costume \
  -H "Content-Type: application/json" \
  -d '{"description": "vampire, red cape"}'

# 4. Submit costume (Bob) - should detect if similar/clash
curl -X POST http://127.0.0.1:5000/api/parties/A3KZ91/attendees/2/costume \
  -H "Content-Type: application/json" \
  -d '{"description": "vampire with fangs"}'

# Response will show clash_count > 0 and level="clash"
```
