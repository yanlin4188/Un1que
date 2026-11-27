/**
 * room_session.js
 * ----------------
 * Shared session management for party code, attendee ID, and token.
 * Loaded before create_room.js and join_room.js so both can use Un1queRoom.
 * 
 * Stores in both localStorage and URL for resilience:
 *   localStorage = "un1que.room.<CODE>" → {attendeeId, token, name, isOrganizer}
 *   URL = ?code=ABC123 for shareable invite links
 */

(function (global) {
  /**
   * Mirrors backend clean_code(): "a3kz-91 " → "A3KZ91"
   * @param {string} code
   * @returns {string} Uppercase alphanumeric only
   */
  function normalize(code) {
    return (code || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  /**
   * Display format: ABC123 → ABC-123
   * Never send this to the API — always use normalize() for requests.
   * @param {string} code
   * @returns {string} Formatted code
   */
  function format(code) {
    const c = normalize(code);
    return c.length === 6 ? c.slice(0, 3) + '-' + c.slice(3) : c;
  }

  /**
   * Save room session to localStorage
   * @param {object} room - {code, attendeeId, token, name, isOrganizer}
   */
  function save(room) {
    if (!room || !room.code) {
      console.error('Un1queRoom.save(): room.code is required');
      return;
    }
    const key = 'un1que.room.' + normalize(room.code);
    localStorage.setItem(key, JSON.stringify(room));
  }

  /**
   * Load room session from localStorage by code
   * @param {string} code - If omitted, tries all stored rooms (returns first valid)
   * @returns {object|null}
   */
  function load(code) {
    try {
      if (code) {
        const key = 'un1que.room.' + normalize(code);
        return JSON.parse(localStorage.getItem(key) || 'null');
      }
      // If no code specified, return the first stored room
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key?.startsWith('un1que.room.')) {
          return JSON.parse(localStorage.getItem(key) || 'null');
        }
      }
      return null;
    } catch (e) {
      console.error('Un1queRoom.load() JSON parse error:', e);
      return null;
    }
  }

  /**
   * Clear a room session from localStorage
   * @param {string} code - If omitted, clears all rooms
   */
  function clear(code) {
    if (code) {
      const key = 'un1que.room.' + normalize(code);
      localStorage.removeItem(key);
    } else {
      const keys = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key?.startsWith('un1que.room.')) {
          keys.push(key);
        }
      }
      keys.forEach(k => localStorage.removeItem(k));
    }
  }

  /**
   * Get code from URL (?code=ABC123) or return null
   * @returns {string|null}
   */
  function getCodeFromUrl() {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    return code ? normalize(code) : null;
  }

  /**
   * Update URL with code (without page reload)
   * @param {string} code
   */
  function setCodeInUrl(code) {
    if (!code) return;
    const c = normalize(code);
    const params = new URLSearchParams(location.search);
    params.set('code', c);
    window.history.replaceState({}, '', `?${params.toString()}`);
  }

  // Expose all functions
  global.Un1queRoom = {
    normalize,
    format,
    save,
    load,
    clear,
    getCodeFromUrl,
    setCodeInUrl
  };
})(window);
