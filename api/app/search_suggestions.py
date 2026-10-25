"""'Did you mean' suggestions for searches that find nothing."""
import difflib
import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]{3,}")
MIN_CORRECTABLE = 4
CORRECTION_CUTOFF = 0.8
MAX_LENGTH_GAP = 2
RECORD_CUTOFF = 0.55


def build_vocabulary(values):
    words = Counter()
    for value in values:
        if value:
            words.update(WORD.findall(str(value).upper()))
    return words


def suggest_correction(query, vocabulary):
    if not query or not vocabulary:
        return None

    corrected, changed = [], False
    for token in query.split():
        upper = token.upper()
        if len(upper) < MIN_CORRECTABLE or not upper.isalpha() or upper in vocabulary:
            corrected.append(upper)
            continue

        candidates = [w for w in vocabulary if abs(len(w) - len(upper)) <= MAX_LENGTH_GAP]
        match = difflib.get_close_matches(upper, candidates, n=1, cutoff=CORRECTION_CUTOFF)
        if match:
            corrected.append(match[0])
            changed = True
        else:
            corrected.append(upper)

    return " ".join(corrected) if changed else None


def closest_records(query, corpus, limit=5):
    if not query or not corpus:
        return []
    lookup = {}
    for value in corpus:
        if value:
            lookup.setdefault(str(value).upper(), str(value))
    matches = difflib.get_close_matches(
        query.upper(), list(lookup), n=limit, cutoff=RECORD_CUTOFF
    )
    return [lookup[m] for m in matches]


def suggestions_for(query, corpus, limit=5):
    corpus = [c for c in corpus if c]
    return {
        "did_you_mean": suggest_correction(query, build_vocabulary(corpus)),
        "closest": closest_records(query, corpus, limit),
    }
