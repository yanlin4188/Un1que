"""
test_matcher.py — run with:  python -m pytest backend -v
"""

import pytest

import matcher as m


# --- parsing ---------------------------------------------------------------

def test_parse_keywords_splits_and_normalises():
    assert m.parse_keywords("Spider-Man,  Red   Suit; mask\nMASK") == ["spider-man", "red suit", "mask"]


def test_parse_keywords_fullwidth_separators():
    assert m.parse_keywords("吸血鬼，斗篷、红色") == ["吸血鬼", "斗篷", "红色"]


@pytest.mark.parametrize("bad", ["", "   ", ",,,", "!!!"])
def test_parse_keywords_rejects_empty(bad):
    with pytest.raises(ValueError):
        m.parse_keywords(bad)


def test_clean_keywords_rejects_non_list():
    with pytest.raises(ValueError):
        m.clean_keywords("vampire")
    with pytest.raises(ValueError):
        m.clean_keywords(["vampire", 3])


def test_clean_keywords_limits():
    with pytest.raises(ValueError):
        m.clean_keywords([f"kw{i}" for i in range(m.MAX_KEYWORDS + 1)])
    with pytest.raises(ValueError):
        m.clean_keywords(["x" * (m.MAX_KEYWORD_LENGTH + 1)])


# --- similarity ------------------------------------------------------------

@pytest.mark.parametrize("a, b", [
    (["Spider-Man"], ["spiderman"]),
    (["spider man costume"], ["Spider-Man"]),
    (["red capes"], ["red cape"]),
    (["witches hat"], ["witch hat"]),
    (["蜘蛛侠"], ["蜘蛛侠"]),
])
def test_same_costume_written_differently_clashes(a, b):
    assert m.check_uniqueness(a, [b]).level == "clash"


def test_different_characters_are_unique():
    result = m.check_uniqueness(["Spider-Man"], [["Iron Man"], ["Batman"], ["witch", "broom"]])
    assert result.level == "unique"
    assert result.score == 10
    assert result.shared_keywords == []


def test_partial_overlap_is_similar():
    result = m.check_uniqueness(["vampire", "red cape", "fangs"], [["vampire", "black cloak"]])
    assert result.level == "similar"
    assert result.similar_count == 1
    assert result.clash_count == 0
    assert result.shared_keywords == ["vampire"]


def test_sentence_description_is_compared_word_by_word():
    result = m.check_uniqueness(m.parse_keywords("I'm a vampire with a red cape and fangs"), [["vampire"]])
    assert result.level == "similar"


def test_shared_colour_alone_is_not_a_match():
    assert m.check_uniqueness(["ghost", "red cape"], [["zombie", "red"]]).level == "unique"


def test_counts_multiple_guests():
    result = m.check_uniqueness(
        ["pirate", "sword"],
        [["pirate", "sword"], ["Pirate", "swords"], ["ghost"]],
    )
    assert result.is_clash
    assert result.clash_count == 2
    assert result.similar_count == 2


def test_skips_empty_and_junk_others():
    result = m.check_uniqueness(["ghost"], [[], [""], ["!!!"], None])
    assert result.level == "unique"


def test_requires_meaningful_keywords():
    with pytest.raises(ValueError):
        m.check_uniqueness(["the", "a"], [["ghost"]])


def test_generic_words_alone_still_count():
    # "costume" on its own is generic, but it's all the guest gave us
    assert m.check_uniqueness(["costume"], [["costume"]]).level == "clash"


def test_result_never_reveals_other_guests_keywords():
    result = m.check_uniqueness(["vampire", "fangs"], [["vampire", "secret detail"]])
    payload = str(result.to_dict())
    assert "secret" not in payload
    assert "detail" not in payload


def test_to_dict_shape():
    d = m.check_uniqueness(["ghost"], []).to_dict()
    assert set(d) == {"level", "clash", "clash_count", "similar_count", "score",
                      "message", "feedback", "shared_keywords"}


# --- exact matching (original API) ------------------------------------------

def test_exact_helpers_still_work():
    assert m.costumes_match("Spider-Man", "spiderman")
    assert m.check_costume("ghost", [(1, "Ghost!"), (2, "witch")]).match_count == 1
    assert m.clashing_guest_ids([(1, "ghost"), (2, "GHOST"), (3, "witch")]) == {1, 2}
