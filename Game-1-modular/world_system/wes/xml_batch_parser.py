"""XML batch parser for hub output (v4 §5.3, §6, CC9).

Hubs emit a single pass of executor_tool specs as an XML-tagged batch::

    <specs plan_step_id="s2" count="3">
      <spec id="spec_001"
            intent="..."
            hard_constraints='{"tier": 2, "biome": "moors"}'
            flavor_hints='{"name_hint": "..."}'
            cross_ref_hints='{}' />
      <spec id="spec_002" ... />
    </specs>

The three JSON-valued attributes (``hard_constraints``, ``flavor_hints``,
``cross_ref_hints``) are JSON strings inside the XML attribute. They are
parsed into Python dicts here.

This module is a thin deterministic parser — it does no prompt
engineering, no semantic validation (that lives in the dispatcher's
schema/balance pass), and no LLM calls. If the hub LLM produces
unparseable output the dispatcher retries or fails the step.

**Robustness requirements** (verified by ``test_xml_batch_parser.py``):
- Whitespace / line breaks inside ``<specs>`` tolerated.
- Single- or double-quoted JSON attributes tolerated.
- Extra whitespace inside JSON values tolerated.
- Missing optional attributes (any of ``flavor_hints`` /
  ``cross_ref_hints`` / ``hard_constraints``) default to ``{}``.
- ``intent`` attribute is optional; defaults to ``""`` on absence.
- Unrecognized attributes ignored (forward-compatible).
- Markdown fences (```xml ... ```) stripped before parsing.
"""

from __future__ import annotations

import json
import re
from typing import List
from xml.etree import ElementTree as ET

from world_system.wes.dataclasses import ExecutorSpec


class XMLBatchParseError(Exception):
    """Raised when hub XML output cannot be parsed into specs.

    The dispatcher catches this, records the error on the plan step, and
    either retries the hub or marks the step failed.
    """


_CODE_FENCE = re.compile(r"^```(?:xml)?\s*|```\s*$", re.MULTILINE)


def _strip_fences(raw: str) -> str:
    """Strip surrounding markdown code fences if present."""
    return _CODE_FENCE.sub("", raw).strip()


def _coerce_json_attr(value: str, attr_name: str, spec_id: str) -> dict:
    """Parse a JSON-string attribute into a dict. Empty strings -> ``{}``."""
    if value is None:
        return {}
    v = value.strip()
    if not v:
        return {}
    try:
        parsed = json.loads(v)
    except json.JSONDecodeError as e:
        raise XMLBatchParseError(
            f"spec {spec_id!r}: attribute {attr_name!r} is not valid JSON: {e}"
        ) from e
    if not isinstance(parsed, dict):
        raise XMLBatchParseError(
            f"spec {spec_id!r}: attribute {attr_name!r} must be a JSON object, "
            f"got {type(parsed).__name__}"
        )
    return parsed


def parse_xml_batch(raw: str) -> List[ExecutorSpec]:
    """Parse a hub XML batch into a list of ``ExecutorSpec``.

    Args:
        raw: The raw response text from the hub LLM.

    Returns:
        List of ``ExecutorSpec`` in document order.

    Raises:
        XMLBatchParseError: if the XML is malformed, a ``<spec>`` is
            missing required attributes, or an attribute holding JSON
            is not valid JSON / not an object.
    """
    if raw is None:
        raise XMLBatchParseError("hub response is None")
    stripped = _strip_fences(raw)
    if not stripped:
        raise XMLBatchParseError("hub response is empty")

    # ElementTree doesn't like surrounding prose; try to extract the <specs>
    # element even if the model emitted preamble or postscript.
    match = re.search(r"<specs\b.*?</specs>", stripped, re.DOTALL)
    if match is None:
        raise XMLBatchParseError(
            "hub response does not contain a <specs>...</specs> block"
        )
    xml_text = match.group(0)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise XMLBatchParseError(f"malformed XML: {e}") from e

    if root.tag != "specs":
        raise XMLBatchParseError(
            f"root element must be <specs>, got <{root.tag}>"
        )

    plan_step_id = root.attrib.get("plan_step_id", "").strip()
    if not plan_step_id:
        raise XMLBatchParseError(
            "<specs> element missing required 'plan_step_id' attribute"
        )

    specs: List[ExecutorSpec] = []
    for child in root:
        if child.tag != "spec":
            # Tolerate comments / whitespace; skip but don't error on
            # unknown elements so the hub can add metadata later.
            continue

        spec_id = child.attrib.get("id", "").strip()
        if not spec_id:
            raise XMLBatchParseError(
                "<spec> element missing required 'id' attribute"
            )

        intent = child.attrib.get("intent", "")
        hard_constraints = _coerce_json_attr(
            child.attrib.get("hard_constraints", ""),
            "hard_constraints",
            spec_id,
        )
        flavor_hints = _coerce_json_attr(
            child.attrib.get("flavor_hints", ""),
            "flavor_hints",
            spec_id,
        )
        cross_ref_hints = _coerce_json_attr(
            child.attrib.get("cross_ref_hints", ""),
            "cross_ref_hints",
            spec_id,
        )

        specs.append(
            ExecutorSpec(
                spec_id=spec_id,
                plan_step_id=plan_step_id,
                item_intent=intent,
                flavor_hints=flavor_hints,
                cross_ref_hints=cross_ref_hints,
                hard_constraints=hard_constraints,
            )
        )

    return specs


__all__ = ["parse_xml_batch", "XMLBatchParseError"]
