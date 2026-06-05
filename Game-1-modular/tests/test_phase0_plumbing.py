"""Phase 0 plumbing regression tests (G02/G03/G14, 2026-06-03).

Three small infrastructure fixes that unblock the behavior-causal path:

- **G02** — ``build_wes_bundle`` and ``_build_narrative_delta`` now
  accept ``npc_dialogue_since_last`` / ``wms_events_since_last`` /
  ``previous_firing_time`` so callers can populate the delta. The
  default (no args) preserves the prior empty-delta shape.

- **G03** — ``TriggerManager.on_event`` publishes
  ``WMS_TRIGGER_FIRED`` to the :class:`GameEventBus` for each
  threshold crossing. The actions are still returned for the WMS
  interpreter pipeline; the publish forks the same stream so WNS
  subscribers (Phase 2 BehaviorInterpreter) can react.

- **G14** — ``StatStore.activity_profile(locality_id)`` returns the
  per-locality discipline-mix dict the BehaviorInterpreter needs
  (consolidation §3 rung 8). Categories with zero activity are
  always present in the result so callers can read the seven
  canonical buckets without missing-key handling.
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


# ── G02: bridge delta populate ───────────────────────────────────────


class BridgeDeltaPopulateTests(unittest.TestCase):
    """G02 — build_wes_bundle accepts and threads dialogue/event/time
    sources into the delta. Phase 1 will wire actual data; Phase 0
    just establishes the channel."""

    def _make_inputs(self):
        from world_system.living_world.infra.context_bundle import (
            NL1Row, WMSLayerRow,
        )
        from world_system.wns.cascading_context import WeaverContext
        from world_system.wns.wes_call_parser import WESCall

        weaver_ctx = WeaverContext(layer=4, address="region:ashfall_moors")
        wes_call = WESCall(purpose="new-skill", body="moors signature skill")

        dialogue = [NL1Row(
            event_id="nl1_test_001",
            created_at=42.0,
            npc_id="captain_vell",
            address="region:ashfall_moors",
            dialogue_text="copperlash riders strike at dawn",
        )]
        wms_events = [WMSLayerRow(
            event_id="wms_test_001",
            layer=2,
            created_at=41.0,
            address="region:ashfall_moors",
            narrative="three ambushes this week along the copper road",
        )]
        return weaver_ctx, wes_call, dialogue, wms_events

    def test_bundle_default_keeps_empty_delta_lists(self) -> None:
        from world_system.wns.wns_to_wes_bridge import build_wes_bundle

        weaver_ctx, wes_call, _, _ = self._make_inputs()
        bundle = build_wes_bundle(
            layer=4,
            address="region:ashfall_moors",
            wes_call=wes_call,
            weaver_ctx=weaver_ctx,
            geo_ctx=None,
            just_written_narrative="the moors restructure around copper",
            source_row_id="nl_row_test_001",
        )
        self.assertEqual(bundle.delta.npc_dialogue_since_last, [])
        self.assertEqual(bundle.delta.wms_events_since_last, [])

    def test_bundle_populated_when_sources_provided(self) -> None:
        from world_system.wns.wns_to_wes_bridge import build_wes_bundle

        weaver_ctx, wes_call, dialogue, wms_events = self._make_inputs()
        bundle = build_wes_bundle(
            layer=4,
            address="region:ashfall_moors",
            wes_call=wes_call,
            weaver_ctx=weaver_ctx,
            geo_ctx=None,
            just_written_narrative="the moors restructure",
            source_row_id="nl_row_test_002",
            npc_dialogue_since_last=dialogue,
            wms_events_since_last=wms_events,
            previous_firing_time=30.0,
            game_time=45.0,
        )
        self.assertEqual(len(bundle.delta.npc_dialogue_since_last), 1)
        self.assertEqual(len(bundle.delta.wms_events_since_last), 1)
        self.assertEqual(bundle.delta.start_time, 30.0)
        self.assertEqual(bundle.delta.end_time, 45.0)


# ── G03: WMS_TRIGGER_FIRED publish ──────────────────────────────────


class TriggerManagerPublishTests(unittest.TestCase):
    """G03 — on_event publishes WMS_TRIGGER_FIRED for each threshold
    crossing. The actions are STILL returned for the WMS interpreter
    pipeline; the publish forks the same stream."""

    def setUp(self) -> None:
        from events.event_bus import get_event_bus
        from world_system.world_memory.trigger_manager import TriggerManager
        TriggerManager.reset()
        self.tm = TriggerManager.get_instance()
        self.bus = get_event_bus()
        self._received: list[dict] = []

        def _handler(event) -> None:
            self._received.append(getattr(event, "data", {}))

        self._handler = _handler
        self.bus.subscribe("WMS_TRIGGER_FIRED", self._handler)

    def tearDown(self) -> None:
        self.bus.unsubscribe("WMS_TRIGGER_FIRED", self._handler)
        from world_system.world_memory.trigger_manager import TriggerManager
        TriggerManager.reset()

    def _make_event(self, event_type: str = "item_consumed",
                    event_subtype: str = "potion",
                    locality_id: str = "tarmouth"):
        # Build a minimal WorldMemoryEvent — only the attributes
        # TriggerManager.on_event reads need to be set.
        from types import SimpleNamespace
        return SimpleNamespace(
            event_id="evt_test",
            event_type=event_type,
            event_subtype=event_subtype,
            actor_id="player",
            target_id="",
            locality_id=locality_id,
            game_time=1.0,
            payload={},
            tags=[],
        )

    def test_first_event_crosses_threshold_1_and_publishes(self) -> None:
        # THRESHOLDS includes 1, so the very first event in a stream
        # fires a trigger. The publish should fire too.
        actions = self.tm.on_event(self._make_event())
        self.assertGreaterEqual(len(actions), 1)
        self.assertGreater(len(self._received), 0,
                           "expected at least one WMS_TRIGGER_FIRED publish")

        # Verify payload shape per spec.
        any_potion = any(
            evt.get("event_subtype") == "potion"
            and evt.get("locality_id") == "tarmouth"
            for evt in self._received
        )
        self.assertTrue(any_potion,
                        "publish payload should include event_subtype + "
                        "locality_id from the originating event")

    def test_subthreshold_event_does_not_publish(self) -> None:
        # First event hits threshold 1 → publishes. Second event lands
        # the stream at count 2, which is NOT in THRESHOLD_SET, so no
        # publish from the second event. Drain the first.
        self.tm.on_event(self._make_event())
        self._received.clear()
        self.tm.on_event(self._make_event())  # count == 2
        self.assertEqual(self._received, [],
                         "count=2 is not a threshold; nothing should publish")

    def test_actions_still_returned_when_publish_disabled(self) -> None:
        # Even if the bus is unsubscribed/broken, on_event returns
        # actions for the WMS interpreter pipeline. We can't easily
        # break the bus here; instead, assert the action stream is
        # populated independent of the receiver state.
        self.bus.unsubscribe("WMS_TRIGGER_FIRED", self._handler)
        actions = self.tm.on_event(self._make_event())
        self.assertGreaterEqual(len(actions), 1)


# ── G14: StatStore.activity_profile ──────────────────────────────────


class StatStoreActivityProfileTests(unittest.TestCase):
    """G14 — per-locality discipline-mix dict for the BehaviorInterpreter.

    Stat name → tag derivation follows the convention in
    ``StatStore._derive_tags`` (parses ``base.kind.dim1.val1.dim2.val2``).
    To get ``locality:tarmouth`` tags, the test seeds an explicit
    manifest so tags are deterministic regardless of name conventions.
    """

    def setUp(self) -> None:
        import sqlite3
        from world_system.world_memory.stat_store import StatStore
        conn = sqlite3.connect(":memory:")
        self.store = StatStore(conn=conn)
        # Inject manifest patterns so each canonical-category test stat
        # gets the expected (domain:X, locality:Y) tag pair.
        self.store._manifest = {
            "combat.kills.locality.*": {
                "tags": ["domain:combat", "locality:{dim}"],
            },
            "gathering.resources.locality.*": {
                "tags": ["domain:gathering", "locality:{dim}"],
            },
            "crafting.attempts.locality.*": {
                "tags": ["domain:crafting", "locality:{dim}"],
            },
            "exploration.chunks.locality.*": {
                "tags": ["domain:exploration", "locality:{dim}"],
            },
        }

    def test_no_data_returns_empty_dict(self) -> None:
        profile = self.store.activity_profile("nonexistent_locality")
        self.assertEqual(profile, {})

    def test_profile_normalizes_to_one(self) -> None:
        # 6 combat + 3 gathering + 1 crafting = 10 total at tarmouth
        self.store.increment(
            "combat.kills.locality.tarmouth", 6.0,
        )
        self.store.increment(
            "gathering.resources.locality.tarmouth", 3.0,
        )
        self.store.increment(
            "crafting.attempts.locality.tarmouth", 1.0,
        )

        profile = self.store.activity_profile("tarmouth")
        # All 7 canonical categories present
        for cat in ("combat", "gathering", "crafting", "economy",
                    "progression", "exploration", "social"):
            self.assertIn(cat, profile)

        self.assertAlmostEqual(sum(profile.values()), 1.0, places=6)
        self.assertAlmostEqual(profile["combat"], 0.6, places=6)
        self.assertAlmostEqual(profile["gathering"], 0.3, places=6)
        self.assertAlmostEqual(profile["crafting"], 0.1, places=6)

    def test_profile_raw_counts_when_normalize_false(self) -> None:
        self.store.increment(
            "combat.kills.locality.tarmouth", 5.0,
        )
        self.store.increment(
            "exploration.chunks.locality.tarmouth", 2.0,
        )
        profile = self.store.activity_profile(
            "tarmouth", normalize=False,
        )
        self.assertEqual(profile["combat"], 5.0)
        self.assertEqual(profile["exploration"], 2.0)

    def test_other_locality_does_not_contaminate(self) -> None:
        # Data at tarmouth must not bleed into ashfall_moors
        self.store.increment(
            "combat.kills.locality.tarmouth", 10.0,
        )
        moors_profile = self.store.activity_profile("ashfall_moors")
        self.assertEqual(moors_profile, {})


# ── G18: Nodes wiring failures ──────────────────────────────────────


class NodesWiringFixesTests(unittest.TestCase):
    """G18 — five silent wiring failures in the Nodes pipeline that
    Agent 5 Trace 05 surfaced. Four are code-level; one (sacred file
    using ``quick``) is fixed by the in-code respawn map gaining a
    ``quick`` → 30 s entry."""

    def test_extract_node_xrefs_reads_drops_array(self) -> None:
        # G18.1 — _extract_node_xrefs must iterate drops[].materialId,
        # not just top-level material_id / yields[].
        from world_system.content_registry.xref_rules import (
            _extract_node_xrefs,
        )
        node_json = {
            "resourceId": "moors_copper_seam",
            "name": "Moors Copper Seam",
            "drops": [
                {"materialId": "moors_copper", "quantity": "many",
                 "chance": "guaranteed"},
                {"materialId": "salt_crystal", "quantity": "few",
                 "chance": "low"},
            ],
        }
        xrefs = _extract_node_xrefs("moors_copper_seam", node_json)
        target_ids = [t[3] for t in xrefs]
        self.assertIn("moors_copper", target_ids,
                      "primary drop should be extracted from drops[]")
        self.assertIn("salt_crystal", target_ids,
                      "secondary drop should be extracted from drops[]")

    def test_sacred_top_level_key_nodes_is_nodes(self) -> None:
        # G18.2 — SACRED_TOP_LEVEL_KEY[TOOL_NODES] must be "nodes"
        # because that is what ResourceNodeDatabase.load_from_file
        # reads (data.get('nodes', [])). Was "resourceNodes" — caused
        # every generated node file to load as empty.
        from world_system.content_registry.xref_rules import (
            SACRED_TOP_LEVEL_KEY, TOOL_NODES,
        )
        self.assertEqual(SACRED_TOP_LEVEL_KEY[TOOL_NODES], "nodes")

    def test_request_layer_node_id_candidates_include_resourceId(self) -> None:
        # G18.3 — _ID_KEY_CANDIDATES["nodes"] must include "resourceId"
        # because that is the canonical sacred schema field. Without it,
        # the request layer's staged-payload lookup falls through to a
        # thin spec with no flavor context.
        from world_system.wes.request_layer import _ID_KEY_CANDIDATES
        self.assertIn("resourceId", _ID_KEY_CANDIDATES["nodes"])
        self.assertEqual(_ID_KEY_CANDIDATES["nodes"][0], "resourceId",
                         "resourceId should be the FIRST candidate "
                         "(canonical sacred schema)")

    def test_respawn_map_handles_quick(self) -> None:
        # G18.4 — sacred resource-node-1.JSON uses "quick" 9 times.
        # The respawn map must accept it (mapped to 30 s, synonym for
        # "fast") without falling through to the default 60 s.
        from data.models.resources import ResourceNodeDefinition
        node = ResourceNodeDefinition(
            resource_id="probe",
            name="Probe",
            category="tree",
            tier=1,
            required_tool="axe",
            base_health=100,
            drops=[],
            respawn_time="quick",
        )
        self.assertEqual(node.get_respawn_seconds(), 30.0)


# ── G17: Materials category allow-list alignment ─────────────────────


class MaterialsCategoryAlignmentTests(unittest.TestCase):
    """G17 — hub and tool prompts must agree on the materials category
    allow-list. Was a mismatch (tool: metal/wood/stone/elemental/
    monster_drop, hub: ore/wood/fish/herb/stone). Phase 0 G17 aligns
    the hub to the tool's vocabulary."""

    def test_hub_prompt_references_tool_categories(self) -> None:
        import json
        from pathlib import Path
        path = Path("world_system/config/prompt_fragments_hub_materials.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        system_prompt = data["_core"]["system"]
        # The hub must reference the tool's canonical category list.
        for cat in ("metal", "wood", "stone", "elemental", "monster_drop"):
            self.assertIn(cat, system_prompt,
                          f"hub prompt missing category '{cat}' — "
                          "G17 alignment regressed?")
        # And must NOT reference the OLD (mismatched) categories that
        # were never in the tool prompt.
        # "ore" / "fish" / "herb" appeared in the old hub allow-list
        # but never in the tool allow-list. They are explicitly NOT
        # valid material categories; checking exact allow-list strings.
        self.assertNotIn(
            "PICK from [ore, wood, fish, herb, stone]",
            system_prompt,
            "old mismatched hub allow-list still present",
        )


if __name__ == "__main__":
    unittest.main()
