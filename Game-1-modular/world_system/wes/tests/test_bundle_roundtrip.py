"""Tests for the WNS → WES bundle serialization round-trip.

The smoking-gun question this file answers: when WNS's NL weaver
publishes a ``WNS_CALL_WES_REQUESTED`` event with a serialized
``WESContextBundle`` in the payload, does the WES orchestrator's
:meth:`WESOrchestrator._extract_bundle_from_event` deserialize it back
into a bundle whose fields match the originals — or does it silently
fall through to ``_build_fixture_bundle``, decoupling WES generation
from the narrative WNS just wove?

These tests construct the bundle with the SAME builder NL weaver uses
(:func:`world_system.wns.wns_to_wes_bridge.build_wes_bundle`), serialize
it the SAME way, wrap it in the SAME event shape (a stand-in for
:class:`GameEvent` with ``.data`` carrying the payload dict), and check
the round-trip end-to-end.

Catches a regression class that the existing nl_weaver tests miss:
``test_nl4_weaver_publishes_wes_event_on_call_wes_true`` only asserts
that some event is published with layer/address — it never opens the
``wes_bundle`` key or deserializes it.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

from world_system.living_world.infra.context_bundle import (  # noqa: E402
    NarrativeContextSlice,
    NarrativeDelta,
    ThreadFragment,
    WESContextBundle,
    WNSDirective,
)
from world_system.wes.wes_orchestrator import WESOrchestrator  # noqa: E402
from world_system.wns.wns_to_wes_bridge import build_wes_bundle  # noqa: E402


# ── Minimal stubs for the WeaverContext + WESCall + GeographicContext ──
# We import the real types but build instances by hand so the test is
# self-contained — no SQLite, no narrative store, no live WNS plumbing.

class _FakeWeaverCtx:
    """Stand-in for :class:`world_system.wns.cascading_context.WeaverContext`.

    The real WeaverContext is a frozen dataclass with several fields
    the bundle builder reads; we mirror the field names / types but
    skip the full constructor's invariants since the builder only
    reads attributes.
    """

    def __init__(
        self,
        *,
        layer: int = 4,
        address: str = "region:ashfall_moors",
        self_latest_narrative: str = "Self-layer narrative.",
        above_primary_address: str = "province:northern_marches",
        above_primary_narrative: str = "Above-primary narrative.",
        above_fading_address: str = "nation:kingdom_of_iron",
        above_fading_narrative: str = "Above-fading narrative.",
        threads: List[ThreadFragment] = None,
    ):
        self.layer = layer
        self.address = address
        self.self_latest_narrative = self_latest_narrative
        self.above_primary_address = above_primary_address
        self.above_primary_narrative = above_primary_narrative
        self.above_fading_address = above_fading_address
        self.above_fading_narrative = above_fading_narrative
        self.self_active_threads = threads or []


@dataclass
class _FakeTierBrief:
    tier: int
    region_id: str
    name: str
    biome: str
    description: str
    tags: List[str] = field(default_factory=list)


class _FakeGeoCtx:
    """Stand-in for :class:`GeographicContext` — same attribute names."""

    def __init__(self, rendered: str = "", tier_briefs: List[Any] = None):
        self.rendered = rendered
        self.tier_briefs = tier_briefs or []


class _FakeWESCall:
    """Stand-in for :class:`WESCall` — same attribute names."""

    def __init__(self, purpose: str, body: str):
        self.purpose = purpose
        self.body = body


class _FakeGameEvent:
    """Mirrors :class:`events.event_bus.GameEvent`'s relevant shape:
    a ``.data`` attribute carrying the published payload dict."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data


# ── Builder fixture: a fully-populated bundle ──────────────────────────

def _make_bundle() -> WESContextBundle:
    """Construct a richly-populated bundle the way NL weaver does."""
    threads = [
        ThreadFragment(
            fragment_id="frag_moors_001",
            layer=4,
            address="region:ashfall_moors",
            headline="Moors copper economy in flux.",
            content_tags=["economy", "copper"],
            thread_id="thread_moors_copper",
            parent_thread_id=None,
            relationship="open",
            created_at=1100.0,
        ),
    ]
    weaver_ctx = _FakeWeaverCtx(threads=threads)
    geo_ctx = _FakeGeoCtx(
        rendered="Ashfall Moors: rust-veined heath.",
        tier_briefs=[
            _FakeTierBrief(
                tier=4, region_id="ashfall_moors",
                name="Ashfall Moors",
                biome="moors",
                description="Windswept heath.",
                tags=["dangerous", "ore-rich"],
            ),
        ],
    )
    wes_call = _FakeWESCall(
        purpose="Materialize moors copper economy expansion",
        body=(
            "Generate content responding to the moors' copper trade "
            "restructuring: new faction interests, NPCs drawn to copper "
            "markets, possibly a new node variant."
        ),
    )
    return build_wes_bundle(
        layer=4,
        address="region:ashfall_moors",
        wes_call=wes_call,
        weaver_ctx=weaver_ctx,
        geo_ctx=geo_ctx,
        just_written_narrative=(
            "Ashfall Moors restructuring around copper trade; three "
            "smithies expanded; merchant guild forming."
        ),
        source_row_id="row_nl4_42",
        game_time=1234567890.0,
    )


# ── Tests ───────────────────────────────────────────────────────────────

class BundleSerializationTestCase(unittest.TestCase):
    """The bundle itself must round-trip cleanly through to_dict /
    from_dict before we can trust the orchestrator's deserializer."""

    def test_bundle_to_dict_preserves_all_fields(self) -> None:
        bundle = _make_bundle()
        d = bundle.to_dict()
        # Spot-check the most load-bearing fields.
        self.assertTrue(d["bundle_id"].startswith("wns_to_wes_"))
        self.assertEqual(d["delta"]["address"], "region:ashfall_moors")
        self.assertEqual(d["delta"]["layer"], 4)
        self.assertIn(
            "three smithies",
            d["narrative_context"]["firing_layer_summary"],
        )
        # Parent summaries must include both layer-up and same-layer.
        ps = d["narrative_context"]["parent_summaries"]
        self.assertIn("4:region:ashfall_moors", ps)  # self-layer
        self.assertIn("5:province:northern_marches", ps)  # above-primary
        # Threads serialize as a list of dicts.
        threads = d["narrative_context"]["open_threads"]
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0]["fragment_id"], "frag_moors_001")
        self.assertEqual(threads[0]["thread_id"], "thread_moors_copper")
        # Directive text is the WES call body, firing_tier matches layer.
        self.assertIn("copper trade", d["directive"]["directive_text"])
        self.assertEqual(d["directive"]["firing_tier"], 4)
        # Scope hint contains the geo descriptor + purpose.
        scope = d["directive"]["scope_hint"]
        self.assertEqual(scope["firing_address"], "region:ashfall_moors")
        self.assertIn("Materialize moors", scope["purpose"])
        # Source provenance.
        self.assertEqual(d["source_narrative_layer_ids"], ["row_nl4_42"])

    def test_round_trip_via_dataclass(self) -> None:
        original = _make_bundle()
        recovered = WESContextBundle.from_dict(original.to_dict())
        self.assertEqual(recovered.bundle_id, original.bundle_id)
        self.assertEqual(recovered.delta.address, original.delta.address)
        self.assertEqual(recovered.delta.layer, original.delta.layer)
        self.assertEqual(
            recovered.narrative_context.firing_layer_summary,
            original.narrative_context.firing_layer_summary,
        )
        self.assertEqual(
            recovered.directive.directive_text,
            original.directive.directive_text,
        )
        self.assertEqual(
            recovered.directive.firing_tier,
            original.directive.firing_tier,
        )
        self.assertEqual(
            recovered.source_narrative_layer_ids,
            original.source_narrative_layer_ids,
        )


# ── Orchestrator extraction tests (the smoking gun) ─────────────────────


class ExtractBundleFromEventTestCase(unittest.TestCase):
    """End-to-end: build → serialize → wrap in event → orchestrator extracts."""

    def setUp(self) -> None:
        # Reset the singleton between tests.
        WESOrchestrator._instance = None
        self.orchestrator = WESOrchestrator.get_instance()

    def test_round_trip_through_orchestrator(self) -> None:
        original = _make_bundle()
        serialized = original.to_dict()
        event = _FakeGameEvent(data={"wes_bundle": serialized})

        recovered = self.orchestrator._extract_bundle_from_event(event)
        self.assertIsNotNone(
            recovered,
            "Orchestrator returned None — bundle was lost on the way",
        )
        self.assertEqual(recovered.bundle_id, original.bundle_id)
        self.assertEqual(recovered.delta.address, original.delta.address)
        self.assertEqual(recovered.delta.layer, original.delta.layer)
        self.assertEqual(
            recovered.narrative_context.firing_layer_summary,
            original.narrative_context.firing_layer_summary,
        )
        self.assertEqual(
            recovered.directive.directive_text,
            original.directive.directive_text,
        )

    def test_dict_payload_also_unwraps(self) -> None:
        """Some publishers pass a plain dict instead of a GameEvent
        with .data; the orchestrator must handle both."""
        original = _make_bundle()
        recovered = self.orchestrator._extract_bundle_from_event(
            {"wes_bundle": original.to_dict()},
        )
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.bundle_id, original.bundle_id)

    def test_event_without_wes_bundle_returns_none(self) -> None:
        event = _FakeGameEvent(data={
            "layer": 4, "address": "region:x",
            # No "wes_bundle" key.
        })
        recovered = self.orchestrator._extract_bundle_from_event(event)
        self.assertIsNone(
            recovered,
            "Orchestrator should return None so caller falls through "
            "to fixture bundle (legacy publisher path)",
        )

    def test_malformed_bundle_dict_returns_none(self) -> None:
        # Missing required keys → from_dict raises → extract catches.
        event = _FakeGameEvent(data={
            "wes_bundle": {"bundle_id": "x"},  # incomplete
        })
        recovered = self.orchestrator._extract_bundle_from_event(event)
        self.assertIsNone(recovered)

    def test_non_dict_wes_bundle_returns_none(self) -> None:
        event = _FakeGameEvent(data={"wes_bundle": "not a dict"})
        recovered = self.orchestrator._extract_bundle_from_event(event)
        self.assertIsNone(recovered)

    def test_non_dict_event_payload_returns_none(self) -> None:
        # Some bus publishers might pass a string or None.
        for bogus in (None, "string", 42, ["list"]):
            recovered = self.orchestrator._extract_bundle_from_event(bogus)
            self.assertIsNone(
                recovered,
                f"expected None for bogus event payload: {bogus!r}",
            )


if __name__ == "__main__":
    unittest.main()
