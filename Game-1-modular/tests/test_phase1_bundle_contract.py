"""Phase 1 bundle-contract propagation tests (2026-06-03).

Verifies the post-trace-pass consolidation §2.2 fix: ``BundleToolSlice``
now carries the narrative-context fields the prior thin-shape contract
stripped (firing_layer_summary, parent_summaries, geographic_chain,
parent-address threads, WMS events delta, NPC dialogue delta,
trigger_archetype). One slice extension, all eight content tools win.

The tests anchor on three load-bearing checks:

1. **Dataclass round-trip** — to_dict / from_dict preserves every new
   field shape so observability logs and replay-based testing stay
   faithful.

2. **Slice extraction** — ``slice_bundle_for_tool`` pulls the right
   fields from the bundle (narrative_context, delta, scope_hint).
   Threads get partitioned by focal-vs-parent address.

3. **Hub vars exposure** — the planner and every hub's ``_make_vars``
   surface the new fields as template variables so prompts can
   reference them as ``${firing_narrative}`` / ``${parent_narratives}``
   / etc.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)


def _make_bundle(
    *,
    address: str = "region:ashfall_moors",
    parent_summaries=None,
    geographic_chain=None,
    parent_threads=None,
):
    from world_system.living_world.infra.context_bundle import (
        NL1Row,
        NarrativeContextSlice,
        NarrativeDelta,
        ThreadFragment,
        WESContextBundle,
        WMSLayerRow,
        WNSDirective,
    )

    focal_threads = [
        ThreadFragment(
            fragment_id="frag_focal_1",
            layer=4,
            address=address,
            headline="copperlash riders strike at dawn",
            content_tags=["faction:moors_raiders", "thread_stage:rising"],
            created_at=10.0,
        ),
    ]
    parent_threads = parent_threads or [
        ThreadFragment(
            fragment_id="frag_parent_1",
            layer=5,
            address="province:valdren",
            headline="dual crises strain the crown",
            content_tags=["nation:valdren", "thread_stage:complication"],
            created_at=8.0,
        ),
    ]

    delta = NarrativeDelta(
        address=address,
        layer=4,
        start_time=5.0,
        end_time=15.0,
        npc_dialogue_since_last=[
            NL1Row(
                event_id="nl1_001",
                created_at=12.0,
                npc_id="captain_vell",
                address=address,
                dialogue_text="they ride the rust-cliffs again",
            ),
        ],
        wms_events_since_last=[
            WMSLayerRow(
                event_id="wms_001",
                layer=2,
                created_at=11.0,
                address=address,
                narrative="three ambushes this week along the copper road",
            ),
        ],
    )

    ctx = NarrativeContextSlice(
        firing_layer_summary="The moors restructure around the copper trade.",
        parent_summaries=parent_summaries or {
            "5:province:valdren": "Valdren strains under dual crises.",
        },
        open_threads=focal_threads + parent_threads,
    )

    scope_hint = {
        "firing_address": address,
        "purpose": "new-quest",
        "weaver_layer": 4,
        "geographic_chain": geographic_chain or [
            {"tier": 4, "region_id": "ashfall_moors", "name": "Ashfall Moors",
             "biome": "moors", "description": "salt-cured cliff country",
             "tags": ["salt", "copper", "moors"]},
            {"tier": 5, "region_id": "valdren", "name": "Valdren",
             "biome": "varied", "description": "fractious crown province",
             "tags": ["nation", "crisis"]},
        ],
    }

    directive = WNSDirective(
        directive_text="Generate content responding to the moors' realignment.",
        firing_tier=4,
        scope_hint=scope_hint,
    )

    return WESContextBundle(
        bundle_id="bundle_phase1_test_001",
        created_at=100.0,
        delta=delta,
        narrative_context=ctx,
        directive=directive,
        source_narrative_layer_ids=["nl_row_test_001"],
    )


# ── Dataclass round-trip ─────────────────────────────────────────────


class BundleToolSliceRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_new_fields(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            BundleToolSlice,
            slice_bundle_for_tool,
        )
        bundle = _make_bundle()
        slice_ = slice_bundle_for_tool(bundle, tool_name="hostiles")

        # Sanity: new fields populated
        self.assertEqual(
            slice_.firing_layer_summary,
            "The moors restructure around the copper trade.",
        )
        self.assertIn(
            "5:province:valdren", slice_.parent_summaries,
        )
        self.assertEqual(len(slice_.geographic_chain), 2)
        self.assertEqual(slice_.trigger_archetype, "narrative")

        # Round-trip via dict
        d = slice_.to_dict()
        restored = BundleToolSlice.from_dict(d)
        self.assertEqual(
            restored.firing_layer_summary, slice_.firing_layer_summary,
        )
        self.assertEqual(
            restored.parent_summaries, slice_.parent_summaries,
        )
        self.assertEqual(
            restored.geographic_chain, slice_.geographic_chain,
        )
        self.assertEqual(
            len(restored.wms_events_since_last),
            len(slice_.wms_events_since_last),
        )
        self.assertEqual(
            len(restored.npc_dialogue_since_last),
            len(slice_.npc_dialogue_since_last),
        )
        self.assertEqual(
            restored.trigger_archetype, slice_.trigger_archetype,
        )


# ── Slice extraction ─────────────────────────────────────────────────


class SliceExtractionTests(unittest.TestCase):
    def test_threads_partitioned_by_address(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            slice_bundle_for_tool,
        )
        bundle = _make_bundle()
        slice_ = slice_bundle_for_tool(bundle, tool_name="quests")

        # Focal threads should contain only address-matching fragments.
        for t in slice_.threads_in_focal_address:
            self.assertEqual(t.address, "region:ashfall_moors")

        # Parent-address threads must NOT include the focal-address ones.
        for t in slice_.threads_in_parent_addresses:
            self.assertNotEqual(t.address, "region:ashfall_moors")

        # Together they should sum to the bundle's open_threads count.
        self.assertEqual(
            len(slice_.threads_in_focal_address)
            + len(slice_.threads_in_parent_addresses),
            len(bundle.narrative_context.open_threads),
        )

    def test_geographic_chain_from_scope_hint(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            slice_bundle_for_tool,
        )
        bundle = _make_bundle(geographic_chain=[
            {"tier": 2, "region_id": "tarmouth", "name": "Tarmouth",
             "biome": "harbor", "description": "a copper port",
             "tags": ["port"]},
        ])
        slice_ = slice_bundle_for_tool(bundle, tool_name="materials")
        self.assertEqual(len(slice_.geographic_chain), 1)
        self.assertEqual(slice_.geographic_chain[0]["region_id"], "tarmouth")

    def test_default_trigger_archetype_is_narrative(self) -> None:
        # The bridge does not set trigger_archetype on the directive
        # scope_hint today (Phase 2 BehaviorInterpreter will). The
        # slice must default to "narrative" so existing pipelines
        # operate unchanged.
        from world_system.living_world.infra.context_bundle import (
            slice_bundle_for_tool,
        )
        bundle = _make_bundle()
        bundle.directive.scope_hint.pop("trigger_archetype", None)
        slice_ = slice_bundle_for_tool(bundle, tool_name="chunks")
        self.assertEqual(slice_.trigger_archetype, "narrative")


# ── Hub vars exposure ────────────────────────────────────────────────


class HubVarsExposureTests(unittest.TestCase):
    """The planner and every hub's _make_vars must surface the Phase 1
    template variables. Without this, prompts can't reference
    ${firing_narrative} / ${parent_narratives} / etc."""

    def _all_hub_vars(self) -> dict:
        from world_system.living_world.infra.context_bundle import (
            slice_bundle_for_tool,
        )
        from world_system.wes.dataclasses import WESPlanStep
        from world_system.wes.llm_tiers.llm_execution_hub import (
            LLMExecutionHub,
        )
        bundle = _make_bundle()
        slice_ = slice_bundle_for_tool(bundle, tool_name="quests")
        step = WESPlanStep(
            step_id="s1", tool="quests", intent="probe",
            depends_on=[], slots={},
        )
        hub = LLMExecutionHub(tool_name="quests")
        return hub._make_vars(step, slice_)

    def test_hub_exposes_phase1_template_variables(self) -> None:
        vars_ = self._all_hub_vars()
        for required in (
            "firing_narrative",
            "parent_narratives",
            "geographic_chain",
            "thread_fragments",
            "parent_thread_fragments",
            "parent_thread_headlines",
            "wms_events_summary",
            "npc_dialogue_summary",
            "trigger_archetype",
        ):
            self.assertIn(required, vars_,
                          f"hub _make_vars missing '{required}'")

    def test_parent_narratives_rendered_as_lines(self) -> None:
        vars_ = self._all_hub_vars()
        rendered = vars_["parent_narratives"]
        # Single parent summary in the fixture
        self.assertIn("5:province:valdren", rendered)
        self.assertIn("dual crises", rendered)

    def test_wms_events_summary_rendered(self) -> None:
        vars_ = self._all_hub_vars()
        rendered = vars_["wms_events_summary"]
        self.assertIn("three ambushes", rendered)

    def test_npc_dialogue_summary_rendered(self) -> None:
        vars_ = self._all_hub_vars()
        rendered = vars_["npc_dialogue_summary"]
        self.assertIn("captain_vell", rendered)


class PlannerVarsExposureTests(unittest.TestCase):
    def test_planner_exposes_phase1_template_variables(self) -> None:
        from world_system.wes.llm_tiers.llm_execution_planner import (
            LLMExecutionPlanner,
        )
        bundle = _make_bundle()
        planner = LLMExecutionPlanner()
        vars_ = planner._bundle_to_vars(bundle)
        for required in (
            "bundle_parent_summaries",
            "geographic_chain",
            "trigger_archetype",
        ):
            self.assertIn(required, vars_,
                          f"planner _bundle_to_vars missing '{required}'")
        # Content sanity
        self.assertIn("province:valdren", vars_["bundle_parent_summaries"])
        self.assertEqual(len(vars_["geographic_chain"]), 2)
        self.assertEqual(vars_["trigger_archetype"], "narrative")


# ── Cross-cutting: every hub-tool combo materializes vars ─────────────


class EveryToolHubVarsTests(unittest.TestCase):
    """One slice fix, eight tools win. Verify every hub's _make_vars
    exposes the Phase 1 contract."""

    def test_all_eight_hubs_carry_new_vars(self) -> None:
        from world_system.living_world.infra.context_bundle import (
            slice_bundle_for_tool,
        )
        from world_system.wes.dataclasses import WESPlanStep
        from world_system.wes.llm_tiers.llm_execution_hub import (
            LLMExecutionHub,
        )

        bundle = _make_bundle()
        step = WESPlanStep(
            step_id="s1", tool="materials", intent="probe",
            depends_on=[], slots={},
        )
        for tool in ("hostiles", "materials", "nodes", "skills",
                     "titles", "chunks", "npcs", "quests"):
            hub = LLMExecutionHub(tool_name=tool)
            slice_ = slice_bundle_for_tool(bundle, tool_name=tool)
            vars_ = hub._make_vars(step, slice_)
            self.assertEqual(
                vars_["trigger_archetype"], "narrative",
                f"{tool} hub lost trigger_archetype",
            )
            self.assertEqual(
                vars_["firing_narrative"],
                "The moors restructure around the copper trade.",
                f"{tool} hub lost firing_narrative",
            )


if __name__ == "__main__":
    unittest.main()
