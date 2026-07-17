"""Text budgeting utilities for LLM context assembly.

The v4 design doctrine (WORLD_SYSTEM_WORKING_DOC §8.4) is that "composing
the right ~2-4k tokens per call is the entire game" — budgets are enforced
at assembly time, and truncation must respect content boundaries (whole
records / sentences), never mid-word slices that hand the model gibberish.

The WNS side honored this from day one (wms_context_builder's per-line
budget packing); the WMS side (L2-L7 data blocks) and the NPC conversation
memory did not — data blocks were unbounded and summaries were tail-sliced
at char boundaries (2026-07 audit). This module is the shared, tested
implementation both sides now use.
"""
from typing import List, Tuple

TRUNCATION_MARKER = " […]"


def truncate_at_boundary(text: str, budget: int, marker: str = TRUNCATION_MARKER) -> str:
    """Truncate ``text`` to at most ``budget`` chars, cutting at the last
    sentence boundary within budget when possible, else the last word
    boundary, never mid-word. Returns text unchanged when within budget.
    """
    if len(text) <= budget:
        return text
    if budget <= len(marker):
        return text[:max(0, budget)]

    cut = budget - len(marker)
    head = text[:cut]

    # Prefer the last sentence boundary in the kept region.
    best = -1
    for punct in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        idx = head.rfind(punct)
        if idx > best:
            best = idx
    # Only accept a sentence cut that keeps a reasonable amount of text.
    if best >= cut * 0.5:
        return head[:best + 1].rstrip() + marker

    # Fall back to the last word boundary.
    space = head.rfind(" ")
    if space >= cut * 0.5:
        return head[:space].rstrip() + marker

    return head.rstrip() + marker


def clamp_snippet_window(summary: str, budget: int, sep: str = " | ") -> str:
    """Bound a rolling ``sep``-joined snippet log to ``budget`` chars by
    dropping the OLDEST whole snippets (never slicing one mid-way).

    Used for NPC conversation summaries: the log is append-only newest-last,
    so trimming from the front preserves the most recent exchanges intact.
    """
    if len(summary) <= budget:
        return summary
    parts = summary.split(sep)
    while len(parts) > 1 and len(sep.join(parts)) > budget:
        parts.pop(0)
    result = sep.join(parts)
    if len(result) > budget:
        # Single oversized snippet — boundary-truncate it rather than slice.
        result = truncate_at_boundary(result, budget)
    return result


def clamp_xml_events_to_budget(block: str, budget: int) -> Tuple[str, int]:
    """Bound an XML event data block to ``budget`` chars by dropping whole
    ``<event ...>...</event>`` lines (oldest-first within each group),
    preserving all structural lines so the XML stays well-formed.

    The WMS data-block builders emit one event per line inside structural
    wrappers (<district>/<locality>/<province>/...). Dropping whole event
    lines keeps every remaining record intact — the design's whole-record
    truncation ethos — and an ``<omitted .../>`` marker tells the model the
    view was capped.

    Returns (clamped_block, events_omitted).
    """
    if len(block) <= budget:
        return block, 0

    lines = block.split("\n")
    event_idx = [i for i, ln in enumerate(lines)
                 if ln.lstrip().startswith("<event")]
    if not event_idx:
        # No droppable event lines — boundary-truncate as a last resort.
        return truncate_at_boundary(block, budget), 0

    dropped = 0
    keep = [True] * len(lines)
    # Drop oldest events first (builders emit chronologically per group).
    for i in event_idx:
        current_len = sum(len(lines[j]) + 1 for j in range(len(lines)) if keep[j])
        if current_len <= budget:
            break
        keep[i] = False
        dropped += 1

    kept_lines = [ln for j, ln in enumerate(lines) if keep[j]]
    if dropped:
        # Insert the omission marker right after the opening structural line.
        insert_at = 1 if len(kept_lines) > 1 else 0
        indent = "  "
        kept_lines.insert(insert_at,
                          f'{indent}<omitted count="{dropped}" reason="context budget"/>')
    return "\n".join(kept_lines), dropped
