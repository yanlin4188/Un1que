"""
matcher.py — 撞衫检测 (costume clash detection) for Un1que.

Pure functions only: no Flask or database imports, so this file stays
independent of app.py / models.py / repository.py and is easy to test.

Two levels of matching live here:

1. Keyword matching (what the app uses). Guests describe their costume with
   keywords ("vampire, red cape, fangs"). repository.py stores them as a
   list, and check_uniqueness() scores how similar one guest's keywords are
   to every other guest's:

       import matcher, repository as repo

       mine = matcher.parse_keywords("Spider-Man, red suit")
       repo.save_costume_keywords(me.id, mine)
       others = repo.get_other_costumes(party.code, me.id)
       result = matcher.check_uniqueness(mine, others)
       result.level   # "unique" | "similar" | "clash"

2. Exact matching (check_costume / find_clashes). Compares whole costume
   strings after normalisation; kept for simple one-word costumes and for
   server-side reports.

Privacy: results only say *whether* and *how many* other guests match, plus
which of the requester's OWN keywords overlap. They never say who the other
guests are or what anyone else wrote.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

MAX_KEYWORDS = 20
MAX_KEYWORD_LENGTH = 50

# similarity >= CLASH_THRESHOLD   -> "clash"   (almost certainly the same costume)
# similarity >= SIMILAR_THRESHOLD -> "similar" (worth a heads-up)
CLASH_THRESHOLD = 0.6
SIMILAR_THRESHOLD = 0.3

# Grammar words: ignored everywhere.
STOPWORDS = frozenset(
    "a an the and or with without of in on at to for from by my our your "
    "i im me as is are be wearing wear dressed like some very also plus".split()
)

# Words that just mean "costume": ignored unless they are all a guest wrote.
NOISE_WORDS = frozenset(
    "costume costumes outfit outfits cosplay thing version style".split()
)

# Words that say nothing about *which* costume it is on their own, but are
# part of names. Ignored as standalone terms, kept when gluing a phrase
# together, so "spider man" -> "spiderman" still matches "Spider-Man".
GENERIC_WORDS = frozenset(
    "man men woman women girl girls boy boys guy guys lady person people".split()
)

# A phrase with more content words than this is treated as a sentence
# ("vampire with a red cape and fangs") and compared word by word.
MAX_PHRASE_WORDS = 3

# Two keyword phrases match when the Dice score of their terms is above this.
PHRASE_MATCH_THRESHOLD = 0.5

# Separators between keyword phrases: ASCII and full-width punctuation.
_PHRASE_SPLIT = re.compile(r"[,;\n\r/|+，、；。]+")


def parse_keywords(text: str) -> list[str]:
    """Split a free-text costume description into keyword phrases.

    "Spider-Man, red suit; mask" -> ["spider-man", "red suit", "mask"]

    Phrases are split on commas, semicolons, slashes and new lines (ASCII
    or full-width). Each phrase is lower-cased and whitespace-collapsed;
    phrases with no letters or digits are dropped, and so are duplicates.
    Raises ValueError if nothing usable is left or the limits are exceeded.
    """
    if not isinstance(text, str):
        raise ValueError("costume description must be a string")
    return clean_keywords(_PHRASE_SPLIT.split(text))


def clean_keywords(keywords: Iterable[str]) -> list[str]:
    """Normalise a list of keyword phrases (see parse_keywords).

    Commas inside a phrase are treated as separators too, because the
    database stores the list comma-separated.
    """
    if isinstance(keywords, str):
        raise ValueError("keywords must be a list of strings")

    cleaned: list[str] = []
    for kw in keywords:
        if not isinstance(kw, str):
            raise ValueError("keywords must be a list of strings")
        for part in _PHRASE_SPLIT.split(kw):
            phrase = " ".join(unicodedata.normalize("NFKC", part).casefold().split())
            if not phrase or not _words(phrase):
                continue
            if len(phrase) > MAX_KEYWORD_LENGTH:
                raise ValueError(
                    f"each keyword must be at most {MAX_KEYWORD_LENGTH} characters"
                )
            if phrase not in cleaned:
                cleaned.append(phrase)

    if not cleaned:
        raise ValueError("describe your costume with at least one keyword")
    if len(cleaned) > MAX_KEYWORDS:
        raise ValueError(f"use at most {MAX_KEYWORDS} keywords")
    return cleaned


def _words(phrase: str) -> list[str]:
    """Lower-case letter/digit runs: "Spider-Man!" -> ["spider", "man"]."""
    text = unicodedata.normalize("NFKC", phrase).casefold()
    text = "".join(ch if unicodedata.category(ch)[0] in ("L", "N") else " " for ch in text)
    return text.split()


def _stem(word: str) -> str:
    """Very light English plural stripping: capes->cape, witches->witch."""
    if len(word) <= 3 or not word.isascii():
        return word
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


Unit = tuple[str, frozenset[str]]  # (the keyword phrase it came from, its terms)


def _phrase_units(phrase: str) -> list[Unit]:
    """Comparison units for one keyword phrase.

    "red capes"          -> [{"red", "cape", "redcape"}]
    "spider man costume" -> [{"spider", "spiderman"}]   (man: generic, costume: noise)
    "vampire"            -> [{"vampire"}]
    "vampire with red cape and fangs" -> [{"vampire"}, {"red"}, {"cape"}, {"fang"}]
    """
    words = [_stem(w) for w in _words(phrase) if w not in STOPWORDS]
    meaningful = [w for w in words if w not in NOISE_WORDS] or words
    content = [w for w in meaningful if w not in GENERIC_WORDS] or meaningful
    if not content:
        return []
    if len(content) > MAX_PHRASE_WORDS:
        return [(phrase, frozenset([w])) for w in dict.fromkeys(content)]
    terms = set(content)
    if len(meaningful) >= 2:  # glue so spacing/hyphens don't matter
        terms.add("".join(meaningful))
    return [(phrase, frozenset(terms))]


def _units(keywords: Iterable[str] | None) -> list[Unit]:
    units: list[Unit] = []
    for kw in keywords or []:
        if isinstance(kw, str):
            units.extend(_phrase_units(kw))
    return units


def _units_match(a: frozenset[str], b: frozenset[str]) -> bool:
    return 2 * len(a & b) / (len(a) + len(b)) > PHRASE_MATCH_THRESHOLD


def _compare(mine: list[Unit], theirs: list[Unit]) -> tuple[float, set[str]]:
    """Similarity 0.0-1.0 and the phrases of `mine` that matched.

    similarity = (my matched units + their matched units) / (all units)
    so identical lists score 1.0 and one shared keyword out of five
    total scores 0.4.
    """
    if not mine or not theirs:
        return 0.0, set()
    my_hits = [any(_units_match(m, t) for _, t in theirs) for _, m in mine]
    their_hits = sum(any(_units_match(t, m) for _, m in mine) for _, t in theirs)
    similarity = (sum(my_hits) + their_hits) / (len(mine) + len(theirs))
    matched = {phrase for (phrase, _), hit in zip(mine, my_hits) if hit}
    return similarity, matched


def keyword_similarity(a: Iterable[str], b: Iterable[str]) -> float:
    """How alike two keyword lists are, from 0.0 (nothing shared) to 1.0."""
    return _compare(_units(a), _units(b))[0]


@dataclass(frozen=True)
class UniquenessResult:
    level: str               # "unique" | "similar" | "clash"
    clash_count: int         # other guests at or above CLASH_THRESHOLD
    similar_count: int       # other guests at or above SIMILAR_THRESHOLD (includes clashes)
    max_similarity: float    # 0.0 - 1.0, against the closest other guest
    shared_keywords: list[str] = field(default_factory=list)
    # ^ the requester's OWN keywords that overlap with a similar costume.
    #   Never contains anything another guest wrote that the requester didn't.

    @property
    def is_clash(self) -> bool:
        return self.level == "clash"

    @property
    def score(self) -> int:
        """Uniqueness score out of 10 (10 = nobody else is close)."""
        return round(10 * (1 - self.max_similarity))

    @property
    def message(self) -> str:
        if self.level == "clash":
            n = self.clash_count
            return f"Costume clash! {n} other guest{'s are' if n != 1 else ' is'} wearing nearly the same thing."
        if self.level == "similar":
            n = self.similar_count
            return f"Heads up: {n} other guest{'s have' if n != 1 else ' has'} a similar costume."
        return "Your costume is unique so far!"

    @property
    def feedback(self) -> str:
        if self.level == "unique":
            return "Nobody at this party has described anything close. We'll keep checking as more guests join."
        overlap = ", ".join(f'"{k}"' for k in self.shared_keywords)
        hint = f"Overlapping keywords: {overlap}. " if overlap else ""
        if self.level == "clash":
            return hint + "Consider switching to a different character, or change the main pieces of your outfit."
        return hint + "A twist on colours or accessories should be enough to stand out."

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "clash": self.is_clash,
            "clash_count": self.clash_count,
            "similar_count": self.similar_count,
            "score": self.score,
            "message": self.message,
            "feedback": self.feedback,
            "shared_keywords": list(self.shared_keywords),
        }


def check_uniqueness(
    my_keywords: Iterable[str],
    others: Iterable[Iterable[str]],
) -> UniquenessResult:
    """Compare one guest's keywords with every other guest's keyword list.

    `others` is what repository.get_other_costumes() returns: one keyword
    list per other guest, with the requesting guest already left out.
    Empty or unusable entries are skipped.
    """
    mine = [kw for kw in my_keywords if isinstance(kw, str)]
    my_units = _units(mine)
    if not my_units:
        raise ValueError("describe your costume with at least one keyword")

    clash_count = similar_count = 0
    best = 0.0
    overlapping: set[str] = set()

    for other in others:
        sim, matched = _compare(my_units, _units(other))
        best = max(best, sim)
        if sim >= SIMILAR_THRESHOLD:
            similar_count += 1
            overlapping |= matched
            if sim >= CLASH_THRESHOLD:
                clash_count += 1

    if clash_count:
        level = "clash"
    elif similar_count:
        level = "similar"
    else:
        level = "unique"

    # Report overlaps as the requester's own phrases, in their original order.
    shared = [kw for kw in mine if kw in overlapping]

    return UniquenessResult(
        level=level,
        clash_count=clash_count,
        similar_count=similar_count,
        max_similarity=round(best, 3),
        shared_keywords=shared,
    )
