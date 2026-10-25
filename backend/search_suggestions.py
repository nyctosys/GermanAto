"""'Did you mean' suggestions for searches that find nothing.

Two different things go wrong, and they need different answers:

  * the query is misspelled - "air fillter" should suggest searching for
    "AIR FILTER" instead;
  * the *data* is misspelled - someone typed "MASTER SWTICH" when the item was
    entered, so a correct search for "MASTER SWITCH" finds nothing. No query
    correction helps there; the answer is to show the closest records.

So a failed search returns both: a corrected query to re-run, and the nearest
actual records to jump straight to.

Uses difflib from the standard library - no index to maintain, and the corpus is
only read when a search has already come back empty, so successful searches pay
nothing.
"""
import difflib
import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]{3,}")

# Only correct words long enough for a typo to be distinguishable from a
# different word. Below this, "pd" would happily become "PAD" or "PSI".
MIN_CORRECTABLE = 4

# A correction should be a near-miss, not a different word of similar shape.
CORRECTION_CUTOFF = 0.8
MAX_LENGTH_GAP = 2

# Record matching can be looser: the user is staring at zero results, so a
# plausible near-match is more use than nothing.
RECORD_CUTOFF = 0.55


def build_vocabulary(values):
    """Word frequencies across a corpus, ignoring part-number noise."""
    words = Counter()
    for value in values:
        if value:
            words.update(WORD.findall(str(value).upper()))
    return words


def suggest_correction(query, vocabulary):
    """A corrected version of the query, or None if nothing looks misspelled.

    Words already in the vocabulary are left alone - they are real, even if the
    search using them found nothing.
    """
    if not query or not vocabulary:
        return None

    corrected, changed = [], False
    for token in query.split():
        upper = token.upper()
        if len(upper) < MIN_CORRECTABLE or not upper.isalpha() or upper in vocabulary:
            corrected.append(upper)
            continue

        # Only consider words of a similar length, so a short odd token cannot
        # latch onto an unrelated longer one.
        candidates = [w for w in vocabulary if abs(len(w) - len(upper)) <= MAX_LENGTH_GAP]
        match = difflib.get_close_matches(upper, candidates, n=1, cutoff=CORRECTION_CUTOFF)
        if match:
            corrected.append(match[0])
            changed = True
        else:
            corrected.append(upper)

    return " ".join(corrected) if changed else None


def closest_records(query, corpus, limit=5):
    """The nearest actual values - the answer when the data holds the typo."""
    if not query or not corpus:
        return []
    lookup = {}
    for value in corpus:
        if value:
            lookup.setdefault(str(value).upper(), str(value))
    matches = difflib.get_close_matches(
        query.upper(), list(lookup), n=limit, cutoff=RECORD_CUTOFF)
    return [lookup[m] for m in matches]


def suggestions_for(query, corpus, limit=5):
    """Everything a zero-result search should offer back.

    Returns {'did_you_mean': str|None, 'closest': [str]} - omit whichever is
    empty when building the response.
    """
    corpus = [c for c in corpus if c]
    return {
        'did_you_mean': suggest_correction(query, build_vocabulary(corpus)),
        'closest': closest_records(query, corpus, limit),
    }
