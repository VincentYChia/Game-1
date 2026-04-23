"""Tests for the context bundle dataclasses (v4 P0 — CC2, §4.7)."""

from __future__ import annotations

import json
import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.living_world.infra.context_bundle import (  # noqa: E402
    BundleToolSlice,
    NarrativeContextSlice,
    NarrativeDelta,
    NL1Row,
    ThreadFragment,
    WESContextBundle,
    WMSLayerRow,
    WNSDirective,
    slice_bundle_for_tool,
)


def _sample_bundle() -> WESContextBundle:
    thread_in_locality = ThreadFragment(
        fragment_id="frag_a",
        layer=2,
        address="locality:tarmouth_copperdocks",
        headline="Copper rush draws bandits",
        content_tags=["prosperity", "banditry"],
        parent_thread_id=None,
        relationship="open",
        created_at=100.0,
    )
    # A thread at a different address — should NOT appear in slice.
    thread_elsewhere = ThreadFragment(
        fragment_id="frag_b",
        layer=3,
        address="district:tarmouth",
        headline="Labor drain from ironrow",
        content_tags=["economic_shift"],
    )

    nl1 = NL1Row(
        event_id="nl1_1",
        created_at=50.0,
        npc_id="gareth_smith",
        address="locality:tarmouth_ironrow",
        dialogue_text="Half my apprentices ran off to the copperdocks.",
        extracted_mentions=[{"entity": "copperdocks", "claim_type": "observation"}],
    )
    wms_row = WMSLayerRow(
        event_id="wms_1",
        layer=3,
        created_at=60.0,
        address="district:tarmouth",
        narrative="Mining active; bandit pressure rising.",
        tags=["mining", "combat"],
    )

    delta = NarrativeDelta(
        address="locality:tarmouth_copperdocks",
        layer=2,
        start_time=0.0,
        end_time=100.0,
        npc_dialogue_since_last=[nl1],
        wms_events_since_last=[wms_row],
    )

    context = NarrativeContextSlice(
        firing_layer_summary="The copperdocks buzz with prosperity and dread.",
        parent_summaries={
            "3:district:tarmouth": "Tarmouth splits: coast booms, forge declines.",
            "4:region:ashfall_moors": "The moors restructure around copper.",
        },
        open_threads=[thread_in_locality, thread_elsewhere],
    )

    directive = WNSDirective(
        directive_text="Generate a bandit type exploiting the copper trade.",
        firing_tier=4,
        scope_hint={"biome": "moors", "tier": 2},
    )

    return WESContextBundle(
        bundle_id="bundle_001",
        created_at=100.0,
        delta=delta,
        narrative_context=context,
        directive=directive,
        source_narrative_layer_ids=["nl2_evt_1", "nl4_evt_7"],
    )


class TestContextBundleRoundTrip(unittest.TestCase):

    def test_round_trip_preserves_all_fields(self) -> None:
        original = _sample_bundle()
        blob = json.dumps(original.to_dict(), sort_keys=True)
        loaded = WESContextBundle.from_dict(json.loads(blob))

        self.assertEqual(loaded.bundle_id, original.bundle_id)
        self.assertEqual(loaded.created_at, original.created_at)
        self.assertEqual(loaded.directive.directive_text,
                         original.directive.directive_text)
        self.assertEqual(loaded.directive.firing_tier, 4)
        self.assertEqual(loaded.delta.address, original.delta.address)
        self.assertEqual(len(loaded.delta.npc_dialogue_since_last), 1)
        self.assertEqual(len(loaded.delta.wms_events_since_last), 1)
        self.assertEqual(loaded.narrative_context.firing_layer_summary,
                         original.narrative_context.firing_layer_summary)
        self.assertEqual(
            loaded.narrative_context.parent_summaries,
            original.narrative_context.parent_summaries,
        )
        self.assertEqual(len(loaded.narrative_context.open_threads), 2)
        self.assertEqual(loaded.source_narrative_layer_ids,
                         ["nl2_evt_1", "nl4_evt_7"])

    def test_round_trip_is_json_serialisable(self) -> None:
        bundle = _sample_bundle()
        blob = json.dumps(bundle.to_dict())
        # Round trip must produce identical dict shape.
        restored = WESContextBundle.from_dict(json.loads(blob))
        self.assertEqual(restored.to_dict(), bundle.to_dict())


class TestBundleToolSlice(unittest.TestCase):

    def test_slice_filters_threads_by_focal_address(self) -> None:
        bundle = _sample_bundle()

        slice_ = slice_bundle_for_tool(
            bundle=bundle,
            tool_name="hostiles",
            recent_registry_entries=[{"content_id": "boar_t1"}],
        )

        # Only the thread at the focal address should be present.
        self.assertEqual(len(slice_.threads_in_focal_address), 1)
        self.assertEqual(slice_.threads_in_focal_address[0].fragment_id, "frag_a")

        # The other thread (at district address) is excluded.
        ids = {t.fragment_id for t in slice_.threads_in_focal_address}
        self.assertNotIn("frag_b", ids)

        # Registry entries pass through verbatim.
        self.assertEqual(slice_.recent_registry_entries,
                         [{"content_id": "boar_t1"}])

        # Directive + firing_tier propagate.
        self.assertEqual(slice_.firing_tier, 4)
        self.assertEqual(slice_.directive_text,
                         bundle.directive.directive_text)
        self.assertEqual(slice_.tool_name, "hostiles")
        self.assertEqual(slice_.bundle_id, bundle.bundle_id)

    def test_slice_round_trip(self) -> None:
        bundle = _sample_bundle()
        slice_ = slice_bundle_for_tool(bundle, "materials")
        restored = BundleToolSlice.from_dict(
            json.loads(json.dumps(slice_.to_dict()))
        )
        self.assertEqual(restored.to_dict(), slice_.to_dict())


if __name__ == "__main__":
    unittest.main()
