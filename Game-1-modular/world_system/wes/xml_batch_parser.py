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

**Element-children dialect** (2026-07-10 real-LLM certification): every
real model tested — Haiku 4.5, qwen2.5:14b, gemma3:4b — ignores the
attribute dialect above and emits payloads as CHILD ELEMENTS instead::

    <specs>
      <spec>
        <intent>...</intent>
        <hard_constraints><tier>2</tier><biome>moors</biome></hard_constraints>
        <flavor_hints>{"name_hint": "..."}</flavor_hints>
      </spec>
    </specs>

Only the hand-written fixtures used the canonical attribute shape, so
the WES cascade silently produced ZERO content on real backends. The
parser now accepts both dialects. Dispatcher-driven leniency (missing
``plan_step_id``/``id`` — the hub overwrites plan_step_id
authoritatively anyway) is opt-in via ``default_plan_step_id``;
without it the strict contract is unchanged.
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


def _coerce_leaf(text: str):
    """Best-effort typing for element text: JSON, int, float, or string."""
    t = (text or "").strip()
    if not t:
        return ""
    if t.startswith("{") or t.startswith("["):
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            return t
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return t


def _element_to_value(el: "ET.Element"):
    """Convert an element to a dict (from children) or a typed leaf."""
    children = list(el)
    if not children:
        return _coerce_leaf(el.text or "")
    return {c.tag: _element_to_value(c) for c in children}


def _payload_dict(child: "ET.Element", name: str, spec_id: str) -> dict:
    """Read a JSON payload from an attribute (canonical, strict) or a
    child element (what real models emit, tolerant)."""
    if name in child.attrib:
        return _coerce_json_attr(child.attrib.get(name), name, spec_id)
    el = child.find(name)
    if el is not None:
        value = _element_to_value(el)
        if isinstance(value, dict):
            return value
        if value in ("", None):
            return {}
        raise XMLBatchParseError(
            f"spec {spec_id!r}: element <{name}> must contain a JSON "
            f"object or child elements, got {type(value).__name__}"
        )
    return {}


def parse_xml_batch(raw: str,
                    default_plan_step_id: str = "") -> List[ExecutorSpec]:
    """Parse a hub XML batch into a list of ``ExecutorSpec``.

    Args:
        raw: The raw response text from the hub LLM.
        default_plan_step_id: Dispatcher-supplied step id. When given,
            the parser tolerates a missing ``plan_step_id`` attribute
            (the hub overwrites it authoritatively anyway) and
            auto-generates missing per-spec ids. Without it the strict
            contract is unchanged.

    Returns:
        List of ``ExecutorSpec`` in document order.

    Raises:
        XMLBatchParseError: if the XML is malformed, required ids are
            missing (strict mode), or a JSON payload is invalid.
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
        plan_step_id = (default_plan_step_id or "").strip()
    if not plan_step_id:
        raise XMLBatchParseError(
            "<specs> element missing required 'plan_step_id' attribute"
        )

    specs: List[ExecutorSpec] = []
    for index, child in enumerate(root):
        if child.tag != "spec":
            # Tolerate comments / whitespace; skip but don't error on
            # unknown elements so the hub can add metadata later.
            continue

        spec_id = child.attrib.get("id", "").strip()
        if not spec_id:
            if default_plan_step_id:
                spec_id = f"spec_{len(specs) + 1:03d}"
            else:
                raise XMLBatchParseError(
                    "<spec> element missing required 'id' attribute"
                )

        intent = child.attrib.get("intent", "")
        if not intent:
            intent_el = child.find("intent")
            if intent_el is not None and intent_el.text:
                intent = intent_el.text.strip()
        hard_constraints = _payload_dict(child, "hard_constraints", spec_id)
        flavor_hints = _payload_dict(child, "flavor_hints", spec_id)
        cross_ref_hints = _payload_dict(child, "cross_ref_hints", spec_id)

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

    # Duplicate spec ids would clobber/double-execute downstream work
    # keyed by spec_id — fail closed like every other malformed shape,
    # so the dispatcher's retry path re-prompts the hub (2026-07 audit).
    seen_ids = set()
    for spec in specs:
        if spec.spec_id in seen_ids:
            raise XMLBatchParseError(
                f"duplicate spec id {spec.spec_id!r} in hub batch"
            )
        seen_ids.add(spec.spec_id)

    return specs


__all__ = ["parse_xml_batch", "XMLBatchParseError"]
