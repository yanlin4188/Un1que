/**
 * create_room.js
 * ---------------
 * Room management for the main room page (create_room.html).
 * Handles party initialization, loading, member management, and costume submission.
 */

const $ = (id) => document.getElementById(id);
let currentParty = null;
let currentAttendee = null;
let pollInterval = null;

/**
 * Initialize the party on page load
 * - If session exists, load existing party
 * - If no session and ?new=1, force create a new party
 * - Otherwise load from session
 */
async function initializeParty() {
    const session = window.Un1queRoom.load();

    if (session?.code) {
        // Session exists, load from DB
        await loadParty(session.code);
    } else {
        // No session, redirect to home to create/join
        window.location.href = 'index.html';
    }
}

/**
 * Load party data from API
 */
async function loadParty(code) {
    try {
        const normalizedCode = window.Un1queRoom.normalize(code);
        const res = await fetch(`/api/parties/${encodeURIComponent(normalizedCode)}`);
        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Party not found');
        }

        currentParty = data.party;
        renderParty();
        startPolling();
    } catch (err) {
        console.error('loadParty error:', err);
        window.Un1queRoom.clear();
        window.location.href = 'index.html';
    }
}

/**
 * Render party data to the page
 */
function renderParty() {
    if (!currentParty) return;

    const session = window.Un1queRoom.load();
    const isOrganizer = session?.isOrganizer;

    // Display code (formatted for UI only)
    if ($('partyCode')) {
        $('partyCode').textContent = window.Un1queRoom.format(currentParty.code);
    }

    // Display members
    if ($('partyMembers')) {
        $('partyMembers').innerHTML = '';
        currentParty.members?.forEach(member => {
            addMemberBadge(member.name, member.id, isOrganizer);
        });
    }

    // Show/hide organizer buttons
    const endBtn = $('endPartyBtn');
    if (endBtn) {
        endBtn.style.display = isOrganizer ? 'inline-block' : 'none';
    }
}

/**
 * Add a member badge to the display
 */
function addMemberBadge(name, memberId, isOrganizer) {
    const memberBadge = document.createElement('div');
    memberBadge.className = 'member-badge';
    memberBadge.textContent = name;

    if (isOrganizer && memberId) {
        // Add a kick button for organizer
        const kickBtn = document.createElement('span');
        kickBtn.className = 'kick-btn';
        kickBtn.textContent = ' ✕';
        kickBtn.style.cursor = 'pointer';
        kickBtn.style.marginLeft = '8px';
        kickBtn.style.color = '#d9534f';
        kickBtn.onclick = () => kickMember(memberId, name);
        memberBadge.appendChild(kickBtn);
    }

    const memberContainer = $('partyMembers');
    if (memberContainer) {
        memberContainer.appendChild(memberBadge);
    }
}

/**
 * Kick a member (organizer only)
 */
async function kickMember(memberId, memberName) {
    if (!confirm(`Kick ${memberName} from the party?`)) {
        return;
    }

    const session = window.Un1queRoom.load();
    try {
        const res = await fetch(`/api/attendees/${memberId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-Attendee-Token': session.token
            }
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Failed to kick member');
        }

        // Refresh members list
        await loadParty(currentParty.code);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

/**
 * End the party (organizer only)
 */
async function endParty() {
    if (!confirm('End this party? All members will be removed.')) {
        return;
    }

    const session = window.Un1queRoom.load();
    try {
        const normalizedCode = window.Un1queRoom.normalize(currentParty.code);
        const res = await fetch(`/api/parties/${encodeURIComponent(normalizedCode)}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-Attendee-Token': session.token
            }
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Failed to end party');
        }

        // Clear session and redirect home
        window.Un1queRoom.clear();
        window.location.href = 'index.html';
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

/**
 * Submit costume for judgment
 */
async function submitCostume() {
    const session = window.Un1queRoom.load();
    const costumeInput = $('costumeInput');
    const resultDiv = $('result');

    if (!costumeInput?.files?.length) {
        resultDiv.innerHTML = '<strong style="color: #d9534f;">Please select an image first!</strong>';
        resultDiv.style.display = 'block';
        return;
    }

    const file = costumeInput.files[0];
    const formData = new FormData();
    formData.append('costume', file);

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<strong>Analyzing your costume...</strong>';

    try {
        const normalizedCode = window.Un1queRoom.normalize(currentParty.code);
        const res = await fetch(`/api/parties/${encodeURIComponent(normalizedCode)}/judge`, {
            method: 'POST',
            headers: {
                'X-Attendee-Token': session.token
            },
            body: formData
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Judgment failed');
        }

        resultDiv.innerHTML = `
            <strong style="color: #5cb85c;">Judgment Complete!</strong>
            <p>${data.message}</p>
            <p><strong>Score:</strong> ${data.score}/10</p>
            <p><strong>Feedback:</strong> ${data.feedback}</p>
        `;

        // Refresh members list to show costume status
        await loadParty(currentParty.code);
    } catch (err) {
        resultDiv.innerHTML = `<strong style="color: #d9534f;">Error: ${err.message}</strong>`;
    }
}

/**
 * Poll for updates (members list, kicked status, party ended)
 */
function startPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        const session = window.Un1queRoom.load();
        if (!session?.code || !currentParty) return;

        try {
            const res = await fetch(`/api/parties/${encodeURIComponent(currentParty.code)}`);
            const data = await res.json();

            if (!res.ok) {
                // Party no longer exists or user is kicked
                clearInterval(pollInterval);
                window.Un1queRoom.clear();
                alert('You have been removed from this party.');
                window.location.href = 'index.html';
                return;
            }

            currentParty = data.party;
            renderParty();
        } catch (err) {
            console.error('Poll error:', err);
        }
    }, 5000);  // Poll every 5 seconds
}

/**
 * On page load, initialize the party
 */
window.addEventListener('load', () => {
    initializeParty();
});

/**
 * On page unload, clear polling
 */
window.addEventListener('beforeunload', () => {
    if (pollInterval) clearInterval(pollInterval);
});
