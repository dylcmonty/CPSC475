"""Standardize the unit an auction price is quoted in.

The reports spell the same unit many ways ("1/2 bushel cartons",
"half bushel", "1/2 bushel ctns") and misspell some ("pecl", "hangning
basket"). A price per peck and a price per bushel cannot be averaged
together, so every query that summarizes prices groups by this
standard unit. Strings that name no unit ("Red", "Indian type") give
None, shown as "unspecified".
"""
import re

# Ordered: the first pattern found anywhere in the text wins, so the
# longer units ("1/2 bushel", "8 quart flat") come before their parts.
PATTERNS = [
    (r"hang\w*\s+bas\w*", "hanging basket"),
    (r"1 1/9 bushel", "1 1/9 bushel"),
    (r"(?:1/2|half|haf)\s+bu\w*", "1/2 bushel"),
    (r"(?:1/2|half|haf)\s+pe\w*", "1/2 peck"),
    (r"\bbushels?\b", "bushel"),
    (r"\b(?:pecks?|pecl|pech|pecx|pecck|pk)\b", "peck"),
    (r"(?<![\d/])(\d+|1/2)\s*-?\s*(?:#|lbs?\b)", "{} lb"),
    (r"(\d+)\s*(?:oz|ounc\w*)\b", "{} oz"),
    (r"\b5\s*doz\w*", "5 dozen"),
    (r"\bdoz\w*", "dozen"),
    (r"\b24\s*count\b|\b24s\b", "24 count"),
    (r"\b12\s*(?:/1|1-)?\s*-?\s*p(?:in)?t", "12 pint flat"),
    (r"\b8\s*-?\s*quarts?\b", "8 quart flat"),
    (r"\bquarts?\b", "quart"),
    (r"\bhalf pint\b", "1/2 pint"),
    (r"\bpints?\b|\bpts?\b", "pint"),
    (r"\bbunch\w*|\bbuncle\b|\bbun\b", "bunch"),
    (r"\b(?:each|melons?|heads?|pumpkins?|squash|bulbs?|stalks?|piece)\b", "each"),
    (r"\bpots?\b", "pot"),
    (r"\bplanters?\b|\bwindow box\b", "planter"),
    (r"\bpacks?\b", "pack"),
    (r"\bf\W?lats?\b", "flat"),
    (r"\bbox(?:es)?\b", "box"),
    (r"\bcas(?:e|ae)\b", "case"),
    (r"\bbags?\b", "bag"),
    (r"\bbins?\b", "bin"),
    (r"\bbundles?\b", "bundle"),
    (r"\bbuckets?\b", "bucket"),
    (r"\bbarrels?\b", "barrel"),
    (r"\bsacks?\b", "sack"),
    (r"\bcartons?\b|\bctns?\b", "carton"),
]
COMPILED = [(re.compile(p), unit) for p, unit in PATTERNS]


def standardize(text):
    """The standard unit named in text, or None."""
    if not text:
        return None
    text = text.lower()
    for pattern, unit in COMPILED:
        m = pattern.search(text)
        if m:
            return unit.format(*m.groups()) if "{}" in unit else unit
    return None
