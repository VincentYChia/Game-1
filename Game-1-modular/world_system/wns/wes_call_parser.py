"""WES call parser — extracts inline ``<WES>`` directives from weaver output.

Per user direction: WNS weavers embed WES requests as XML tags inline
within their narrative output:

    <WES purpose="new-npc">A captain for the moors raiders, hardened by the
    loss of his brother on the moors-stone — issues vendetta quests against
    hubtown.</WES>

The parser:
- Pulls every ``<WES purpose="...">body</WES>`` block out of a string.
- Returns each as a structured :class:`WESCall`.
- Strips the tags from the cleaned narrative (so the saved narrative
  doesn't contain them).
- Tolerates missing ``purpose`` attribute (defaults to ``"unspecified"``).
- Tolerates malformed tags by ignoring them (parser is permissive — the
  weaver is allowed to be slightly sloppy with tag formatting).

Spam-cap policy lives at the call site (the weaver enforces ``max_calls``
per run, default 2). This module just parses; it does not enforce caps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


# Default max <WES> calls per weaving run. Beyond this, the runtime
# silently drops extras — the LLM is told (via the prompt) that the cap
# exists, so this is a safety net, not the primary enforcement.
DEFAULT_MAX_CALLS_PER_RUN: int = 2

# Match <WES ...>body</WES>. The body is non-greedy so multiple tags
# in one string parse correctly. ``re.DOTALL`` so \n inside body works.
_WES_TAG_RE = re.compile(
    r"<WES\s*(?P<attrs>[^>]*)>(?P<body>.*?)</WES>",
    re.IGNORECASE | re.DOTALL,
)

# Match purpose="..." or purpose='...' or purpose=bareword inside an attr blob.
_PURPOSE_ATTR_RE = re.compile(
    r"""purpose\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))""",
    re.IGNORECASE,
)


@dataclass
class WESCall:
    """One inline <WES> directive extracted from weaver narrative output.

    Attributes:
        purpose: brief bucket label (e.g. ``"new-npc"``, ``"new-chunk"``,
            ``"affinity-shift"``). Comes from the ``purpose`` attribute.
            Empty/missing attribute -> ``"unspecified"``.
        body: the natural-language directive text. Whitespace-trimmed.
    """
    purpose: str
    body: str


def _extract_purpose(attrs_blob: str) -> str:
    """Pull purpose="..." from an attribute string. Returns 'unspecified' if missing."""
    if not attrs_blob:
        return "unspecified"
    m = _PURPOSE_ATTR_RE.search(attrs_blob)
    if not m:
        return "unspecified"
    # Pick whichever group matched (double, single, or bareword).
    return (m.group(1) or m.group(2) or m.group(3) or "unspecified").strip() or "unspecified"


def parse_wes_calls(
    text: str,
    max_calls: int = DEFAULT_MAX_CALLS_PER_RUN,
) -> Tuple[List[WESCall], str]:
    """Extract <WES> calls from a string and return (calls, cleaned_text).

    Args:
        text: weaver narrative output, possibly containing 0+ <WES> tags.
        max_calls: cap on number of calls returned. Excess are silently
            dropped from the calls list AND from the cleaned_text (the
            tag is stripped so the narrative reads clean either way).

    Returns:
        (calls, cleaned_text):
        - ``calls``: list of :class:`WESCall`, length <= max_calls.
        - ``cleaned_text``: the input with all <WES> tags removed and
          whitespace tidied. The body of each tag is NOT preserved in
          the cleaned text — the directive content lives in ``calls``.
    """
    if not text:
        return [], ""

    calls: List[WESCall] = []
    matches = list(_WES_TAG_RE.finditer(text))

    for m in matches[:max_calls]:
        purpose = _extract_purpose(m.group("attrs") or "")
        body = (m.group("body") or "").strip()
        calls.append(WESCall(purpose=purpose, body=body))

    # Strip ALL tags (even those past the cap) from the cleaned text.
    cleaned = _WES_TAG_RE.sub("", text)
    # Collapse runs of whitespace introduced by tag removal.
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    return calls, cleaned


__all__ = [
    "DEFAULT_MAX_CALLS_PER_RUN",
    "WESCall",
    "parse_wes_calls",
]
