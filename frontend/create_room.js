/**
 * create_room.js - Handles party creation, costume submission, and real-time updates
 * 
 * Integration with backend API:
 * - POST /judge-costume: Submit costume description and get matching result
 * - GET /api/parties/<code>: Fetch party details
 */

// =========================================================================
// Party Management
// =========================================================================

/**
 * Generate a random party code (XXXX-XXXX format)
 * Note: This is a client-side placeholder. The backend generates and stores the real code.
 */
function generatePartyCode() {
    const code = Math.random().toString(36).substring(2, 6).toUpperCase() + '-' + 
                Math.random().toString(36).substring(2, 6).toUpperCase();
    document.getElementById('partyCode').textContent = code;
    console.log('Party Code (local):', code);
    return code;
}

/**
 * Add a member badge to the party members list
 * Called when someone submits a costume or joins the party
 */
function addMember(name) {
    const partyMembers = document.getElementById('partyMembers');
    
    // Avoid duplicates
    const existingMembers = Array.from(partyMembers.querySelectorAll('.member-badge'))
        .map(badge => badge.textContent.trim());
    if (existingMembers.includes(name)) {
        return;
    }
    
    const memberBadge = document.createElement('div');
    memberBadge.className = 'member-badge';
    memberBadge.textContent = name;
    partyMembers.appendChild(memberBadge);
}

/**
 * Initialize party on page load
 * - Generates party code
 * - Fetches existing party details (optional)
 */
function initializeParty() {
    generatePartyCode();
    
    // Example: add test members (remove in production)
    setTimeout(() => addMember('Alice'), 500);
    setTimeout(() => addMember('Bob'), 1000);
    
    // In production: fetch actual party from backend
    // fetchPartyDetails(partyCode);
}

// =========================================================================
// Costume Submission & Matching
// =========================================================================

/**
 * Submit a costume description for matching against other guests
 * 
 * Backend contract (POST /judge-costume):
 * Request: {
 *   costume_description: "vampire, red cape, fangs",
 *   party_code: "XXXX-XXXX",
 *   attendee_id?: number (optional - if set, saves the costume)
 * }
 * 
 * Response: {
 *   success: boolean,
 *   message?: string (error message if failed),
 *   level: "unique" | "similar" | "clash",
 *   clash: boolean,
 *   clash_count: number,
 *   similar_count: number,
 *   score: 0-10 (uniqueness score),
 *   message: string (human-readable result),
 *   feedback: string (advice for the participant),
 *   shared_keywords: string[] (overlapping keywords),
 *   participant_name?: string (name of participant if saved),
 *   saved: boolean (whether costume was saved to DB)
 * }
 */
function submitCostume() {
    const textInput = document.getElementById('costumeInput');
    const resultDiv = document.getElementById('result');
    const costumeDescription = textInput.value.trim();
    
    // Validation
    if (!costumeDescription) {
        displayResult('error', '❌ Please describe your costume first!');
        return;
    }

    const partyCode = document.getElementById('partyCode').textContent;
    if (!partyCode || partyCode === 'XXXX-XXXX') {
        displayResult('error', '❌ Party code not generated. Please refresh the page.');
        return;
    }

    // Show loading state
    displayResult('loading', '⏳ Analyzing your costume...');

    // Build request payload
    const payload = {
        costume_description: costumeDescription,
        party_code: partyCode
        // Note: attendee_id is omitted here, so this is a "check-only" preview.
        // In production, add attendee_id to save the costume to the database.
    };

    // Send to backend
    fetch('/judge-costume', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => handleCostumeResponse(data, textInput))
    .catch(error => {
        console.error('Fetch error:', error);
        displayResult('error', `❌ Connection Error: ${error.message}`);
    });
}

/**
 * Handle the response from /judge-costume endpoint
 */
function handleCostumeResponse(data, textInput) {
    if (!data.success) {
        displayResult('error', `❌ Error: ${data.message || 'Unknown error'}`);
        return;
    }

    // Extract result details
    const level = data.level || 'unknown';
    const score = data.score || 0;
    const message = data.message || 'Judgment complete.';
    const feedback = data.feedback || '';
    const sharedKeywords = data.shared_keywords || [];
    const participantName = data.participant_name;

    // Build result display
    let resultHTML = `<strong style="color: #5cb85c;">✓ Judgment Complete!</strong>`;
    resultHTML += `<p><strong>Status:</strong> ${capitalizeLevel(level)}</p>`;
    resultHTML += `<p><strong>Score:</strong> ${score}/10</p>`;
    resultHTML += `<p><strong>Message:</strong> ${message}</p>`;
    
    if (sharedKeywords.length > 0) {
        resultHTML += `<p><strong>Overlapping Keywords:</strong> ${sharedKeywords.join(', ')}</p>`;
    }
    
    resultHTML += `<p><strong>Feedback:</strong> ${feedback}</p>`;

    displayResult('success', resultHTML);

    // Add participant to member list if they were saved
    if (participantName) {
        addMember(participantName);
        textInput.value = '';
        textInput.placeholder = `Thanks, ${participantName}! 🎃`;
    }
}

/**
 * Display result to the user with color coding
 */
function displayResult(type, html) {
    const resultDiv = document.getElementById('result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = html;
    
    // Add color based on result type
    if (type === 'error') {
        resultDiv.style.background = 'rgba(217, 83, 79, 0.1)';
        resultDiv.style.borderLeft = '4px solid #d9534f';
    } else if (type === 'success') {
        resultDiv.style.background = 'rgba(92, 184, 92, 0.1)';
        resultDiv.style.borderLeft = '4px solid #5cb85c';
    } else if (type === 'loading') {
        resultDiv.style.background = 'rgba(255, 255, 255, 0.9)';
        resultDiv.style.borderLeft = '4px solid #FF8C00';
    }
}

/**
 * Capitalize level string for display
 */
function capitalizeLevel(level) {
    const levels = {
        'unique': '🎉 Unique - Nobody else is close!',
        'similar': '⚠️ Similar - Someone has a similar costume',
        'clash': '🚨 Clash - Someone is wearing the same costume!'
    };
    return levels[level] || 'Unknown';
}

// =========================================================================
// Page Initialization
// =========================================================================

/**
 * Initialize the page on load
 */
window.addEventListener('load', () => {
    initializeParty();
});

/**
 * Allow Enter key to submit costume (in addition to button click)
 */
document.addEventListener('DOMContentLoaded', () => {
    const costumeInput = document.getElementById('costumeInput');
    if (costumeInput) {
        costumeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                submitCostume();
            }
        });
    }
});
