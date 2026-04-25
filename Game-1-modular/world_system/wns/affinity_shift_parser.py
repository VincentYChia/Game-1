"""WNS affinity-shift parser — extracts inline ``<AffinityShift>`` blocks
from weaver narrative output.

Per user direction (memory: wns_affinity_modifier_tool): affinity
shifts are NARRATIVE, not content generation. WES is overkill for
'faction X loses standing in region Y because of event Z'. WNS emits
a lightweight XML directive and a deterministic resolver applies it.

Target shape::

    <AffinityShift>
      <Target>faction:moors_raiders</Target>
      <Scope>region:salt_moors</Scope>
      <Effect>standing_delta: -0.15</Effect>
    </AffinityShift>

Rules (from memory note):
- ``<Target>``: faction tag (``faction:X``), NPC reference (``npc:Y``),
  or entity group identifier.
- ``<Scope>``: one address at the largest common denominator per entry
  (nation-wide -> ``nation:X``, region-specific override -> ``region:Y``).
- ``<Effect>``: numeric delta (``standing_delta: -0.15``) or typed
  effect string. Resolver-side parsing handles forms.
- Multiple ``<AffinityShift>`` blocks per weaving run are allowed —
  most-specific scope wins at apply time.

The parser is permissive: missing children, malformed tags, and
unexpected attributes degrade gracefully (skipping bad blocks rather
than raising) so a slightly-off LLM output still produces useful data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


# Match the outer block. re.DOTALL so multi-line bodies work.
_BLOCK_RE = re.compile(
    r"<AffinityShift\b[^>]*>(?P<body>.*?)</AffinityShift>",
    re.IGNORECASE | re.DOTALL,
)

# Match a single <Target>...</Target> child (or any tag name).
def _child_re(tag: str) -> "re.Pattern[str]":
    return re.compile(
        rf"<{tag}\b[^>]*>(?P<v>.*?)</{tag}>",
        re.IGNORECASE | re.DOTALL,
    )


_TARGET_RE = _child_re("Target")
_SCOPE_RE = _child_re("Scope")
_EFFECT_RE = _child_re("Effect")


@dataclass
class AffinityShift:
    """One parsed affinity-shift directive.

    Attributes:
        target: the entity being modified (e.g. ``"faction:moors_raiders"``).
        scope: the address scope (e.g. ``"region:salt_moors"``).
        effect: the raw effect string (e.g. ``"standing_delta: -0.15"``).
            Numeric parsing happens in the resolver — the parser keeps
            the string verbatim.
    """
    target: str
    scope: str
    effect: str


def _extract_child(pattern: "re.Pattern[str]", body: str) -> Optional[str]:
    m = pattern.search(body)
    if not m:
        return None
    return (m.group("v") or "").strip() or None


def parse_affinity_shifts(
    text: str,
) -> Tuple[List[AffinityShift], str]:
    """Extract ``<AffinityShift>`` blocks from a string.

    Returns ``(shifts, cleaned_text)`` where:
    - ``shifts`` is the list of valid AffinityShift directives. Blocks
      missing any of Target/Scope/Effect are silently dropped.
    - ``cleaned_text`` is the input with ALL ``<AffinityShift>`` blocks
      removed and whitespace tidied.
    """
    if not text:
        return [], ""

    shifts: List[AffinityShift] = []
    for m in _BLOCK_RE.finditer(text):
        body = m.group("body") or ""
        target = _extract_child(_TARGET_RE, body)
        scope = _extract_child(_SCOPE_RE, body)
        effect = _extract_child(_EFFECT_RE, body)
        if not (target and scope and effect):
            continue
        shifts.append(AffinityShift(target=target, scope=scope, effect=effect))

    cleaned = _BLOCK_RE.sub("", text)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    return shifts, cleaned


__all__ = [
    "AffinityShift",
    "parse_affinity_shifts",
]
