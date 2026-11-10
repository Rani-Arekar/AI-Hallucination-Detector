"""Overconfidence signal.

Replaces the old "count 4 hardcoded words, threshold at >3" check with a
density-normalized hybrid: certainty/absolutist language, offset by hedging
language, normalized per 100 words so long answers aren't penalized just for
having more words in them. Still a heuristic, not a trained classifier --
labeled as such wherever this score is surfaced.

Known limitation: this does not do negation-aware parsing. "I would never
claim that's proven" still counts "never" and "proven" as certainty hits.
Proper negation handling would need real NLP (dependency parsing at least);
out of scope for this heuristic layer. Flagging honestly rather than
quietly overclaiming precision this doesn't have.
"""

import re

_CERTAINTY_TERMS = [
    "always", "never", "definitely", "guaranteed", "certainly",
    "undoubtedly", "unquestionably", "without a doubt", "100%",
    "impossible", "must be", "undeniable", "irrefutable", "proven fact",
    "everyone knows", "obviously", "clearly", "no doubt",
]

_HEDGING_TERMS = [
    "may", "might", "could", "possibly", "likely", "probably",
    "it is believed", "some evidence suggests", "it appears",
    "as far as i know", "i'm not certain", "unclear", "seems to",
    "suggests that", "it is thought",
]


def _density_per_100_words(text: str, terms: list[str]) -> float:
    lower = text.lower()
    hits = 0
    for term in terms:
        pattern = r"\b" + re.escape(term) + r"\b"
        hits += len(re.findall(pattern, lower))
    word_count = max(len(lower.split()), 1)
    return hits / word_count * 100


def confidence_score(text: str) -> float:
    """Higher = more appropriately hedged / less overconfident tone.
    Heuristic signal (0.3 - 1.0), not a calibrated probability.
    """
    if not text or not text.strip():
        return 1.0

    certainty_density = _density_per_100_words(text, _CERTAINTY_TERMS)
    hedging_density = _density_per_100_words(text, _HEDGING_TERMS)

    net_overconfidence = certainty_density - hedging_density

    if net_overconfidence <= 0:
        return 1.0
    if net_overconfidence < 1.5:
        return 0.8
    if net_overconfidence < 3.0:
        return 0.5
    return 0.3
