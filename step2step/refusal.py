"""Safeguard-refusal detection: provider-neutral text heuristics.

A harness that climbs a model ladder on a refusal has to recognise one. The
autonomy record's driver kept that rule outside the library -- unreusable and
untested -- and it never fired (0 of 12 units), so the markers here come from
the published refusal phrasing, not from a measured refusal. Treat a hit as a
SIGNAL only: the harness rule is "a refusal phrase AND no code change"
(`barrel.core.failures.classify`), never the phrase by itself, because a
working response can quote or discuss these phrases.

Two cheap shapes are recognised: a refusal that opens the response (within
LEAD_CHARS) and a short response that contains one anywhere (SHORT_CHARS).
"""
from __future__ import annotations

REFUSAL_MARKERS = (
    "i can't help with",
    "i cannot help with",
    "i can't assist with",
    "i cannot assist with",
    "i'm not able to help with",
    "i am not able to help with",
    "i'm unable to help with",
    "i am unable to help with",
    "i won't help with",
    "i will not help with",
    "i can't provide",
    "i cannot provide",
    "i must decline",
    "i have to decline",
    "i'll have to decline",
    "i need to decline",
    "i can't comply",
    "i cannot comply",
    "against my guidelines",
    "violates my guidelines",
    "i'm not going to help",
    "i am not going to help",
    "i can't continue with this",
    "i cannot continue with this",
)
LEAD_CHARS = 400
SHORT_CHARS = 1200


def refusal_evidence(text: str | None) -> list[str]:
    """The markers that make `text` look like a refusal (empty = none)."""
    if not text:
        return []
    low = " ".join(text.split()).casefold()
    lead = low[:LEAD_CHARS]
    scope = low if len(low) <= SHORT_CHARS else lead
    return [m for m in REFUSAL_MARKERS if m in scope]


def looks_like_refusal(text: str | None) -> bool:
    return bool(refusal_evidence(text))
