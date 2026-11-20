"""
matching.py — 撞衫检测 (costume clash detection) for Un1que.

Pure functions only: no Flask or database imports, so this file stays
independent of app.py / routes.py / models.py and is easy to test.

Typical use from routes.py when a guest joins a party (lobby):

    from matching import check_costume

    others = [(g.id, g.costume) for g in party.guests if g.id != me.id]
    result = check_costume(me.costume, others)
    return {"clash": result.is_clash, "match_count": result.match_count}

Privacy: check_costume() reports only *whether* and *how many* other guests
match. It never returns who they are or what anyone else wrote, so the API
can warn a guest without revealing other people's costumes.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable, Iterable

MAX_COSTUME_LENGTH = 100

GuestId = Hashable  # int from the DB, or str — whatever models.py uses


def normalize_costume(costume: str) -> str:
    """Return the comparison key for a self-reported costume.

    Rules:
      * Unicode NFKC, so full-width "ＳＰＩＤＥＲＭＡＮ" == "spiderman"
      * casefold(), a stronger lower(): "Spiderman" == "spiderman"
      * keep only letters and digits, so "Spider-Man", "spider man" and
        "SPIDERMAN!" all match. Chinese characters count as letters, so
        "蜘蛛侠" works as-is.

    Raises ValueError if the input is not a string, is too long, or has
    no letters/digits at all (e.g. "" or "!!!").
    """
    if not isinstance(costume, str):
        raise ValueError("costume must be a string")
    if len(costume) > MAX_COSTUME_LENGTH:
        raise ValueError(f"costume must be at most {MAX_COSTUME_LENGTH} characters")

    text = unicodedata.normalize("NFKC", costume).casefold()
    key = "".join(ch for ch in text if unicodedata.category(ch)[0] in ("L", "N"))

    if not key:
        raise ValueError("costume must contain at least one letter or number")
    return key


def costumes_match(a: str, b: str) -> bool:
    """True if two costume strings count as the same costume."""
    return normalize_costume(a) == normalize_costume(b)


@dataclass(frozen=True)
class MatchResult:
    is_clash: bool    # True if at least one other guest has the same costume
    match_count: int  # how many other guests have it
    normalized: str   # the key used for comparison (safe to store in the DB)


def check_costume(
    costume: str,
    others: Iterable[tuple[GuestId, str]],
) -> MatchResult:
    """Check one guest's costume against the other guests in the same party.

    `others` is (guest_id, costume) pairs for everyone else in the lobby;
    leave the guest being checked out of it. Entries with an unusable
    costume (empty, punctuation only, None) are skipped rather than
    crashing the whole check.
    """
    key = normalize_costume(costume)
    count = 0
    for _guest_id, other in others:
        try:
            if normalize_costume(other) == key:
                count += 1
        except ValueError:
            continue
    return MatchResult(is_clash=count > 0, match_count=count, normalized=key)


def find_clashes(guests: Iterable[tuple[GuestId, str]]) -> dict[str, list[GuestId]]:
    """Group every guest in a party by costume and return only the clashes.

    Returns {normalized_costume: [guest_id, ...]} for each costume worn by
    two or more guests, e.g. {"spiderman": [3, 7]}. Meant for server-side
    use (e.g. notifying everyone affected); don't send it to the frontend
    as-is, since it reveals who is wearing what.
    """
    groups: dict[str, list[GuestId]] = defaultdict(list)
    for guest_id, costume in guests:
        try:
            groups[normalize_costume(costume)].append(guest_id)
        except ValueError:
            continue
    return {key: ids for key, ids in groups.items() if len(ids) > 1}


def clashing_guest_ids(guests: Iterable[tuple[GuestId, str]]) -> set[GuestId]:
    """IDs of every guest whose costume clashes with someone else's."""
    return {gid for ids in find_clashes(guests).values() for gid in ids}
