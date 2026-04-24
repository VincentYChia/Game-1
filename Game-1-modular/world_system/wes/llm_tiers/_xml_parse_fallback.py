"""Fallback XML batch parser — used when :mod:`world_system.wes.xml_batch_parser`
isn't available (Agent C's canonical module).

Parses hub output of the form::

    <specs plan_step_id="s2" count="1">
      <spec id="spec_001" intent="..."
            hard_constraints='{"tier": 2}'
            flavor_hints='{}'
            cross_ref_hints='{}' />
    </specs>

Tolerant of:
- Leading/trailing prose.
- Markdown fences (```xml ... ```).
- Single-quoted attribute values containing JSON.
- Spec bodies (``<spec ...>body</spec>``) with body ignored (attrs only).

**TODO:** swap to :mod:`world_system.wes.xml_batch_parser` once Agent C's
orchestrator lands. The public function name matches what that module is
expected to export.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from world_system.wes.dataclasses import ExecutorSpec


_FENCE_RE = re.compile(r"^```(?:xml)?\s*|\s*```$", re.IGNORECASE)
_SPECS_RE = re.compile(r"<specs\b[^>]*>.*?</specs>", re.DOTALL)


def _strip_fences(text: str) -> str:
    s = text.strip()
    s = _FENCE_RE.sub("", s).strip()
    return s


def _json_attr(val: Optional[str]) -> Dict[str, Any]:
    """Parse an attribute that contains a JSON object; tolerate missing / empty."""
    if not val:
        return {}
    try:
        parsed = json.loads(val)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def parse_specs_xml(text: str, plan_step_id: str) -> List[ExecutorSpec]:
    """Parse a hub's XML batch into :class:`ExecutorSpec` objects.

    Returns an empty list on total parse failure (caller will log_degrade).

    ``plan_step_id`` is supplied by the dispatcher — it authoritatively
    overrides whatever the LLM claims, so mis-labeling can't cross-wire
    specs to the wrong step.
    """
    if not text:
        return []

    cleaned = _strip_fences(text)

    # Extract the first <specs>...</specs> block from surrounding prose.
    match = _SPECS_RE.search(cleaned)
    if not match:
        return []

    xml_blob = match.group(0)

    try:
        root = ET.fromstring(xml_blob)
    except ET.ParseError:
        return []

    specs: List[ExecutorSpec] = []
    for i, elem in enumerate(root.findall("spec")):
        spec_id = elem.attrib.get("id") or f"{plan_step_id}_spec_{i}"
        item_intent = elem.attrib.get("intent", "")
        flavor_hints = _json_attr(elem.attrib.get("flavor_hints"))
        cross_ref_hints = _json_attr(elem.attrib.get("cross_ref_hints"))
        hard_constraints = _json_attr(elem.attrib.get("hard_constraints"))
        specs.append(
            ExecutorSpec(
                spec_id=spec_id,
                plan_step_id=plan_step_id,
                item_intent=item_intent,
                flavor_hints=flavor_hints,
                cross_ref_hints=cross_ref_hints,
                hard_constraints=hard_constraints,
            )
        )
    return specs


__all__ = ["parse_specs_xml"]
