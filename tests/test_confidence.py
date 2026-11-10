from app.detector.confidence import confidence_score


def test_empty_text_returns_full_confidence():
    assert confidence_score("") == 1.0
    assert confidence_score("   ") == 1.0


def test_plain_hedged_text_scores_high():
    text = "This might be true, but it's unclear and further evidence is needed to be certain."
    assert confidence_score(text) == 1.0


def test_absolutist_language_lowers_score():
    text = (
        "This is definitely, absolutely, 100% guaranteed to always be true. "
        "It is undeniable and irrefutable, and everyone knows this is a proven fact."
    )
    assert confidence_score(text) < 1.0


def test_word_boundary_matching_avoids_substring_false_positive():
    # "nevertheless" contains "never" as a substring but should NOT match
    # as the standalone word "never".
    text = "Nevertheless, the results were mixed and inconclusive, it seems."
    # should not trip the certainty-language path just because of substring overlap
    score = confidence_score(text)
    assert score == 1.0


def test_hedging_offsets_certainty_language():
    certain_only = "This is definitely, certainly, always true."
    hedged_and_certain = (
        "This is definitely true, but it might also possibly be wrong, "
        "and it's unclear -- it could be either."
    )
    assert confidence_score(hedged_and_certain) >= confidence_score(certain_only)


def test_long_text_is_not_penalized_just_for_length():
    # One certainty word buried in a long, otherwise neutral passage
    # shouldn't score the same as a short, dense wall of absolutist claims.
    long_neutral_ish = ("word " * 300) + "definitely"
    short_dense = "This is definitely, certainly, undeniably, irrefutably always true, obviously."
    assert confidence_score(long_neutral_ish) > confidence_score(short_dense)
