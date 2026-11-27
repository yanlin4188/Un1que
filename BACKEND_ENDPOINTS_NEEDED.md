# Backend API Endpoints to Implement

This file outlines the Flask routes that need to be added/updated in `app.py` to support the new frontend flow.

---

## 1. Create Party (Updated)
```python
@app.route('/api/parties', methods=['POST'])
def create_party_endpoint():
    """
    POST /api/parties
    
    Create a new party and add the organizer as the first attendee.
    
    Request body:
    {
        "title": "Halloween Bash",
        "organizer_name": "Alice",
        "password_hash": "abc123..."  # SHA-256 hash from frontend
    }
    
    Response (201):
    {
        "success": true,
        "party": {
            "code": "ABC123",
            "id": 1,
            "title": "Halloween Bash",
            "organizer_name": "Alice",
            "member_count": 1
        },
        "attendee": {
            "id": 1,
            "name": "Alice",
            "is_organizer": true
        },
        "token": "token_xyz..."
    }
    
    Errors (400):
    - Missing required fields
    - Invalid password hash
    """
    body = request.get_json() or {}
    
    title = body.get('title')
    organizer_name = body.get('organizer_name')
    password_hash = body.get('password_hash')
    
    if not organizer_name or not password_hash:
        return {'success': False, 'message': 'Missing organizer_name or password_hash'}, 400
    
    try:
        party = repo.create_party(
            title=title or 'Costume Party',
            organizer_name=organizer_name
        )
        
        # Add organizer as first attendee
        import secrets
        token = secrets.token_urlsafe(24)
        
        attendee = repo.join_party(
            code=party.code,
            name=organizer_name,
            password_hash=password_hash,
            is_organizer=True
        )
        repo.set_attendee_token(attendee.id, token)
        
        return {
            'success': True,
            'party': party_to_dict(party),
            'attendee': {'id': attendee.id, 'name': attendee.name, 'is_organizer': True},
            'token': token
        }, 201
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## 2. Get Party (Existing, May Need Update)
```python
@app.route('/api/parties/<code>', methods=['GET'])
def get_party_endpoint(code):
    """
    GET /api/parties/<code>
    
    Public endpoint to preview a party (used by join_room.html).
    Does NOT require authentication.
    
    Response (200):
    {
        "success": true,
        "party": {
            "code": "ABC123",
            "id": 1,
            "title": "Halloween Bash",
            "organizer_name": "Alice",
            "member_count": 2,
            "members": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
        }
    }
    
    Errors (404):
    - Party not found
    """
    from app import clean_code  # or import from models
    
    code = clean_code(code)
    
    try:
        party = repo.get_party_by_code(code)
        if not party:
            return {'success': False, 'message': 'Party not found'}, 404
        
        return {
            'success': True,
            'party': party_to_dict(party)
        }, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## 3. Join Party (Updated with Password & Upsert)
```python
@app.route('/api/parties/<code>/join', methods=['POST'])
def join_party_endpoint(code):
    """
    POST /api/parties/<code>/join
    
    Join (or rejoin) an existing party. Returns existing attendee if name already in party.
    
    Request body:
    {
        "name": "Bob",
        "password_hash": "def456..."
    }
    
    Response (200/201):
    {
        "success": true,
        "party": {
            "code": "ABC123",
            "organizer_name": "Alice",
            "member_count": 2
        },
        "attendee": {
            "id": 2,
            "name": "Bob",
            "is_organizer": false
        },
        "token": "token_abc...",
        "rejoined": false  # true if re-joining same account
    }
    
    Errors:
    - 404: Party not found
    - 403: Attendee was kicked (kicked_at is not null)
    - 400: Missing fields / invalid password
    """
    from app import clean_code
    import secrets
    from datetime import datetime
    
    code = clean_code(code)
    body = request.get_json() or {}
    
    name = body.get('name', '').strip()
    password_hash = body.get('password_hash')
    
    if not name or not password_hash:
        return {'success': False, 'message': 'Missing name or password_hash'}, 400
    
    try:
        party = repo.get_party_by_code(code)
        if not party:
            return {'success': False, 'message': 'Party not found'}, 404
        
        if party.ended_at:
            return {'success': False, 'message': 'This party has ended'}, 404
        
        attendee = repo.join_party(code, name, password_hash, is_organizer=False)
        
        # Check if kicked
        if attendee.kicked_at:
            return {'success': False, 'message': 'You were removed from this party'}, 403
        
        # Generate or refresh token
        token = secrets.token_urlsafe(24)
        repo.set_attendee_token(attendee.id, token)
        
        return {
            'success': True,
            'party': party_to_dict(party),
            'attendee': {'id': attendee.id, 'name': attendee.name, 'is_organizer': attendee.is_organizer},
            'token': token,
            'rejoined': False  # Could check if attendee.costume_description exists
        }, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## 4. Delete Party (End Party - Organizer Only)
```python
@app.route('/api/parties/<code>', methods=['DELETE'])
def delete_party_endpoint(code):
    """
    DELETE /api/parties/<code>
    
    Delete a party entirely (hard delete). Only organizer can do this.
    Requires X-Attendee-Token header.
    
    Response (200):
    {
        "success": true,
        "message": "Party deleted"
    }
    
    Errors:
    - 401: Missing or invalid token
    - 403: Not the organizer
    - 404: Party not found
    """
    from app import clean_code
    
    # Check auth token
    token = request.headers.get('X-Attendee-Token')
    if not token:
        return {'success': False, 'message': 'Missing X-Attendee-Token'}, 401
    
    attendee = repo.get_attendee_by_token(token)
    if not attendee:
        return {'success': False, 'message': 'Invalid token'}, 401
    
    code = clean_code(code)
    
    try:
        party = repo.get_party_by_code(code)
        if not party:
            return {'success': False, 'message': 'Party not found'}, 404
        
        # Check organizer
        if attendee.party_id != party.id or not attendee.is_organizer:
            return {'success': False, 'message': 'Only organizer can end the party'}, 403
        
        # Hard delete
        success = repo.delete_party(code)
        if not success:
            return {'success': False, 'message': 'Failed to delete party'}, 400
        
        return {'success': True, 'message': 'Party deleted'}, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## 5. Kick Attendee (Organizer Only)
```python
@app.route('/api/attendees/<attendee_id>', methods=['DELETE'])
def kick_attendee_endpoint(attendee_id):
    """
    DELETE /api/attendees/<attendee_id>
    
    Kick an attendee from a party (soft kick). Only organizer can do this.
    Requires X-Attendee-Token header.
    
    Response (200):
    {
        "success": true,
        "message": "Attendee removed"
    }
    
    Errors:
    - 401: Missing or invalid token
    - 403: Not the organizer
    - 404: Attendee not found
    """
    # Check auth token
    token = request.headers.get('X-Attendee-Token')
    if not token:
        return {'success': False, 'message': 'Missing X-Attendee-Token'}, 401
    
    organizer = repo.get_attendee_by_token(token)
    if not organizer:
        return {'success': False, 'message': 'Invalid token'}, 401
    
    try:
        target = db.session.get(Attendee, int(attendee_id))
        if not target:
            return {'success': False, 'message': 'Attendee not found'}, 404
        
        # Check organizer of same party
        if target.party_id != organizer.party_id or not organizer.is_organizer:
            return {'success': False, 'message': 'Only organizer can kick members'}, 403
        
        repo.kick_attendee(int(attendee_id))
        return {'success': True, 'message': 'Attendee removed'}, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## 6. Judge Costume (Updated with Token)
```python
@app.route('/api/parties/<code>/judge', methods=['POST'])
def judge_costume_endpoint(code):
    """
    POST /api/parties/<code>/judge
    
    Upload costume image and get judgment (clash detection).
    Requires X-Attendee-Token header.
    Saves description + keywords to attendee.
    
    Request: multipart/form-data with 'costume' file
    
    Response (200):
    {
        "success": true,
        "message": "Your costume is unique!",
        "score": 9,
        "feedback": "Great vampire costume!"
    }
    
    Response (200) clash:
    {
        "success": true,
        "message": "Clash with...",
        "clash_with": ["Alice", "Bob"],
        "score": 3,
        "feedback": "Similar to..."
    }
    
    Errors:
    - 401: Missing or invalid token
    - 404: Party not found
    - 400: No file uploaded
    """
    from app import clean_code
    import tempfile
    from matcher import check_uniqueness  # your matcher module
    
    # Check auth token
    token = request.headers.get('X-Attendee-Token')
    if not token:
        return {'success': False, 'message': 'Missing X-Attendee-Token'}, 401
    
    attendee = repo.get_attendee_by_token(token)
    if not attendee:
        return {'success': False, 'message': 'Invalid token'}, 401
    
    code = clean_code(code)
    
    # Check party exists
    party = repo.get_party_by_code(code)
    if not party:
        return {'success': False, 'message': 'Party not found'}, 404
    
    # Get uploaded file
    if 'costume' not in request.files:
        return {'success': False, 'message': 'No file uploaded'}, 400
    
    file = request.files['costume']
    if not file or file.filename == '':
        return {'success': False, 'message': 'Invalid file'}, 400
    
    try:
        # Save temp file + run matcher
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            
            # Call matcher (extract keywords from image)
            keywords = matcher.extract_keywords(tmp.name)  # your implementation
            
            # Get other attendees' keywords in this party
            others = repo.get_other_costumes(code, attendee.id)
            
            # Check uniqueness
            result = matcher.check_uniqueness(keywords, others)
            
            # Save costume + keywords
            repo.save_costume(attendee.id, '', keywords)
            
            # Return result
            return {
                'success': True,
                'message': result['message'],
                'score': result['score'],
                'feedback': result['feedback'],
                'clash_with': result.get('clash_with', [])
            }, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400
```

---

## Helper Function: party_to_dict()

```python
def party_to_dict(party):
    """
    Convert Party ORM object to dict for JSON response.
    Public view—never include password hashes or tokens.
    """
    return {
        'code': party.code,
        'id': party.id,
        'title': party.title,
        'organizer_name': party.organizer_name,
        'member_count': len(party.attendees) if party.attendees else 0,
        'members': [
            {'id': a.id, 'name': a.name}
            for a in party.attendees
            if a.kicked_at is None  # Don't show kicked attendees
        ]
    }
```

---

## Summary of Changes to app.py

| Endpoint | Method | Existing? | Changes |
|----------|--------|-----------|---------|
| `/api/parties` | POST | Yes | Add password_hash + organizer token return |
| `/api/parties/<code>` | GET | Yes | May need minor tweaks |
| `/api/parties/<code>` | DELETE | No | NEW: Hard delete party (organizer) |
| `/api/parties/<code>/join` | POST | Yes | Add password_hash, upsert join, token return, kicked check |
| `/api/attendees/<id>` | DELETE | No | NEW: Soft kick attendee (organizer) |
| `/api/parties/<code>/judge` | POST | Yes | Add token auth, save description |

---

## Import/Setup Needed

```python
# At top of app.py
import secrets
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

# Your existing imports
from repository import *  # or specific functions
from models import Attendee, Party
from matcher import check_uniqueness  # your implementation
```

---

## Testing with curl

```bash
# 1. Create party
curl -X POST http://127.0.0.1:5000/api/parties \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","organizer_name":"Alice","password_hash":"abc123"}'

# 2. Get party (should return code from step 1)
curl http://127.0.0.1:5000/api/parties/ABC123

# 3. Join party
curl -X POST http://127.0.0.1:5000/api/parties/ABC123/join \
  -H "Content-Type: application/json" \
  -d '{"name":"Bob","password_hash":"def456"}'

# 4. Judge costume (need token from steps 1 or 3)
curl -X POST http://127.0.0.1:5000/api/parties/ABC123/judge \
  -H "X-Attendee-Token: token_from_response" \
  -F "costume=@costume.jpg"

# 5. Kick attendee (need organizer token)
curl -X DELETE http://127.0.0.1:5000/api/attendees/2 \
  -H "X-Attendee-Token: organizer_token"

# 6. End party
curl -X DELETE http://127.0.0.1:5000/api/parties/ABC123 \
  -H "X-Attendee-Token: organizer_token"
```

---

Done! All endpoints are ready to implement. 🎃
