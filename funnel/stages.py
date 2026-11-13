"""Works out which bucket (level) every lifecycle stage name of an export belongs to.

One list of names serves every account (see the bucket text in settings.py), so a new account normally needs no
change. A stage name is placed by these rules, in this order:

1. Names in brackets are hints. "Awareness (MQL)" is read as MQL, "Development (Customer)" as Customer.
2. The name (or the hint) is matched against the listed names as WHOLE WORDS, and the LONGEST listed name wins:
   "Marketing Qualified Lead" is MQL and not Lead, "Not Right for Circle" is Other because "NOT RIGHT FOR" is listed.
3. A small typo is forgiven: "Propsect" is read as PROSPECT, "Unqualifed" as UNQUALIFIED.
4. A name that matches nothing goes to OTHER (the caller prints a warning), so every company is still counted.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Sequence


def normalize(text: str) -> str:
    """Lower case, with every run of spaces and punctuation turned into one space: ``"Sales-Lead"`` -> ``"sales lead"``."""
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def build_vocabulary(bucket_texts: Sequence[str]) -> dict[str, int]:
    """Turn the bucket texts of settings.py into one lookup: listed name -> level.

    Args:
        bucket_texts: One comma separated text per bucket, bottom to top (so the position is the level).

    Returns:
        ``{normalized listed name: level}``.

    Raises:
        SystemExit: when the same name is listed in two different buckets.
    """
    vocabulary: dict[str, int] = {}
    for level, text in enumerate(bucket_texts):
        for piece in text.split(","):
            name = normalize(piece)
            if not name:
                continue                                   # an empty piece (or an empty bucket "")
            if name in vocabulary and vocabulary[name] != level:
                raise SystemExit(f'The stage "{name}" is in two buckets. A stage can only be in one.')
            vocabulary[name] = level
    return vocabulary


def _pieces(name: str) -> list[str]:
    """The texts to try for one stage name, best first: each bracketed hint, the name without brackets, the whole name."""
    hints = re.findall(r"\(([^)]*)\)", name)
    outside = re.sub(r"\([^)]*\)", " ", name)
    return [normalize(h) for h in hints] + [normalize(outside), normalize(name)]


def classify_stage(name: str, vocabulary: dict[str, int]) -> tuple[int | None, str]:
    """Find the level of one stage name.

    Args:
        name: The stage name as it appears in the export.
        vocabulary: The result of ``build_vocabulary``.

    Returns:
        ``(level, how)``. ``how`` is "listed" for a normal match or the listed name it was read as, with the word
        "typo", for a forgiven typo. ``level`` is None when nothing matches.
    """
    pieces = [p for p in _pieces(name) if p]
    for piece in pieces:                                   # rules 1 and 2: whole words, longest listed name wins
        padded = f" {piece} "
        found = [alias for alias in vocabulary if f" {alias} " in padded]
        if found:
            return vocabulary[max(found, key=len)], "listed"
    for piece in pieces:                                   # rule 3: a typo
        close = difflib.get_close_matches(piece, list(vocabulary), n=1, cutoff=0.82)
        if close:
            return vocabulary[close[0]], f"typo for {close[0]}"
    return None, ""


def classify_names(names: Iterable[str], vocabulary: dict[str, int], other_level: int
                   ) -> tuple[dict[str, int], dict[str, str], list[str]]:
    """Place every stage name of an export in a bucket.

    Args:
        names: The lower case stage names found in the export.
        vocabulary: The result of ``build_vocabulary``.
        other_level: The level of the OTHER bucket, where names that match nothing go.

    Returns:
        ``(levels, typos, unmatched)``: the level of each name, the typo notes (name -> "typo for ..."), and the names
        that matched nothing (they are in ``levels`` too, at ``other_level``).
    """
    levels: dict[str, int] = {}
    typos: dict[str, str] = {}
    unmatched: list[str] = []
    for name in sorted(set(names)):
        level, how = classify_stage(name, vocabulary)
        if level is None:
            levels[name] = other_level
            unmatched.append(name)
        else:
            levels[name] = level
            if how.startswith("typo"):
                typos[name] = how
    return levels, typos, unmatched


def own_first_name(sub_level: int, levels: dict[str, int], display: dict[str, str], typos: dict[str, str],
                   counts: dict[str, int]) -> str | None:
    """Find what this account calls its first stage (Subscriber, Prospect, Target ...).

    Args:
        sub_level: The level of the SUBSCRIBER bucket.
        levels: The level of each stage name of the export.
        display: Each lower case name -> how the export writes it.
        typos: The names read as a typo (the corrected spelling is shown instead of the typo).
        counts: How many companies each name covers (the busiest name wins when an export has two).

    Returns:
        The name to show, or None when the export has no stage in the SUBSCRIBER bucket (some accounts start at Lead).
    """
    candidates = [name for name, level in levels.items() if level == sub_level]
    if not candidates:
        return None
    best = max(candidates, key=lambda n: (counts.get(n, 0), n))
    if best in typos:
        return typos[best].replace("typo for ", "").title()    # show "Prospect", not the typo "Propsect"
    return display.get(best, best.title())
