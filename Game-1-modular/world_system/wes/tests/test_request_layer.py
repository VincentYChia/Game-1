"""Tests for the Request Layer + dispatcher's tool-only fan-out.

Two integration surfaces:

1. :class:`world_system.wes.request_layer.RequestLayer` — turns
   :class:`CoemitRecommendation` into :class:`ExecutorSpec`. Pure
   functions: tested standalone without Tk / pygame.

2. :meth:`world_system.wes.plan_dispatcher.PlanDispatcher.run_request_specs`
   — runs the specs through Tier-3 executor_tools without a hub call.
   Tested with a fake registry + fake tools so we can assert glue
   behaviour (orphan scan, balance check, stage_content invocation,
   step_errors aggregation under synthetic step ids).
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)

from world_system.wes.async_runner import AsyncLLMRunner  # noqa: E402
from world_system.wes.dataclasses import ExecutorSpec  # noqa: E402
from world_system.wes.plan_dispatcher import PlanDispatcher  # noqa: E402
from world_system.wes.plan_resolution import CoemitRecommendation  # noqa: E402
from world_system.wes.request_layer import (  # noqa: E402
    RequestLayer,
    RequestSpecBatch,
)


# ── Fake helpers used across tests ──────────────────────────────────────

class _FakeRegistry:
    """Minimal registry stub with the methods the dispatcher uses."""

    def __init__(self, staged_by_plan: Dict[str, Dict[str, List[Dict[str, Any]]]] = None):
        self._staged = staged_by_plan or {}
        self.staged_calls: List[Dict[str, Any]] = []

    def list_staged_by_plan(self, plan_id: str) -> Dict[str, List[Dict[str, Any]]]:
        return self._staged.get(plan_id, {})

    def stage_content(
        self,
        *,
        tool_name: str,
        content_json: Dict[str, Any],
        plan_id: str,
        source_bundle_id: str,
    ) -> str:
        # Record + return a synthetic id derived from the content.
        cid = (
            content_json.get("content_id")
            or content_json.get("enemyId")
            or content_json.get("materialId")
            or content_json.get("npc_id")
            or "stub_id"
        )
        self.staged_calls.append({
            "tool_name": tool_name,
            "plan_id": plan_id,
            "content_id": cid,
        })
        return cid


class _FakeTool:
    """Tool stub: maps spec.spec_id → predetermined response (or raises)."""

    def __init__(self, responses: Dict[str, Any]):
        self.responses = responses
        self.calls: List[ExecutorSpec] = []

    def generate(self, spec: ExecutorSpec) -> Any:
        self.calls.append(spec)
        out = self.responses.get(spec.spec_id, {})
        if isinstance(out, BaseException):
            raise out
        return out


class _StubBundle:
    """Minimal bundle the request layer can read addresses off."""

    class _Delta:
        def __init__(self, address: str = ""):
            self.address = address

    def __init__(self, address: str = ""):
        self.delta = self._Delta(address)
        self.bundle_id = "fake_bundle"


# ── RequestLayer tests ──────────────────────────────────────────────────

class TestRequestLayerSpecConstruction(unittest.TestCase):
    """Pure-function tests for :class:`RequestLayer.build_specs`."""

    def setUp(self) -> None:
        self.layer = RequestLayer()

    def test_empty_recs_returns_empty_batch(self) -> None:
        batch = self.layer.build_specs(
            [], registry=None, bundle=None, plan_id="p1", cascade_depth=1,
        )
        self.assertIsInstance(batch, RequestSpecBatch)
        self.assertTrue(batch.is_empty())
        self.assertEqual(batch.total_specs(), 0)

    def test_single_rec_produces_one_spec_for_target_tool(self) -> None:
        rec = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="copperlash_rider",
            requested_by_step_id="runtime_quests:apprentice_haul",
            suggested_intent="Generate the moors raider hostile.",
        )
        batch = self.layer.build_specs(
            [rec], registry=None, bundle=None, plan_id="p1", cascade_depth=1,
        )
        self.assertEqual(set(batch.tool_specs), {"hostiles"})
        specs = batch.tool_specs["hostiles"]
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec.cross_ref_hints["required_id"], "copperlash_rider")
        self.assertEqual(spec.cross_ref_hints["referenced_by_tool"], "quests")
        self.assertEqual(spec.cross_ref_hints["referenced_by_id"], "apprentice_haul")
        self.assertIn("Generate the moors raider hostile.", spec.item_intent)

    def test_dedup_by_target_tool_and_id(self) -> None:
        rec1 = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="moors_copper",
            requested_by_step_id="runtime_quests:q1",
            suggested_intent="",
        )
        rec2 = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="moors_copper",   # duplicate
            requested_by_step_id="runtime_hostiles:h1",
            suggested_intent="",
        )
        rec3 = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="other_enemy",
            requested_by_step_id="runtime_quests:q2",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [rec1, rec2, rec3], registry=None, bundle=None,
            plan_id="p1", cascade_depth=2,
        )
        self.assertEqual(len(batch.tool_specs["materials"]), 1)
        self.assertEqual(len(batch.tool_specs["hostiles"]), 1)
        self.assertEqual(batch.total_specs(), 2)

    def test_groups_specs_by_target_tool(self) -> None:
        recs = [
            CoemitRecommendation(
                missing_ref_type="hostiles",
                missing_ref_id="enemy_a",
                requested_by_step_id="runtime_quests:q1",
                suggested_intent="",
            ),
            CoemitRecommendation(
                missing_ref_type="hostiles",
                missing_ref_id="enemy_b",
                requested_by_step_id="runtime_quests:q1",
                suggested_intent="",
            ),
            CoemitRecommendation(
                missing_ref_type="materials",
                missing_ref_id="mat_a",
                requested_by_step_id="runtime_hostiles:h1",
                suggested_intent="",
            ),
        ]
        batch = self.layer.build_specs(
            recs, registry=None, bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        self.assertEqual(len(batch.tool_specs["hostiles"]), 2)
        self.assertEqual(len(batch.tool_specs["materials"]), 1)

    def test_malformed_rec_is_skipped(self) -> None:
        good = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="enemy_a",
            requested_by_step_id="runtime_quests:q1",
            suggested_intent="",
        )
        bad = CoemitRecommendation(
            missing_ref_type="",       # empty
            missing_ref_id="anything",
            requested_by_step_id="x",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [good, bad], registry=None, bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        self.assertEqual(batch.total_specs(), 1)

    def test_address_pulled_from_bundle(self) -> None:
        rec = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="enemy_a",
            requested_by_step_id="runtime_quests:q1",
            suggested_intent="",
        )
        bundle = _StubBundle(address="region:ashfall_moors")
        batch = self.layer.build_specs(
            [rec], registry=None, bundle=bundle,
            plan_id="p1", cascade_depth=1,
        )
        spec = batch.tool_specs["hostiles"][0]
        self.assertEqual(spec.hard_constraints["address"], "region:ashfall_moors")
        self.assertEqual(spec.flavor_hints["geographic_address"], "region:ashfall_moors")

    def test_tier_inferred_from_requesting_payload(self) -> None:
        registry = _FakeRegistry({
            "p1": {
                "quests": [
                    {"content_id": "q_haul",
                     "payload_json": {"quest_id": "q_haul", "tier": 3}},
                ],
            },
        })
        rec = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="enemy_a",
            requested_by_step_id="runtime_quests:q_haul",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [rec], registry=registry, bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        spec = batch.tool_specs["hostiles"][0]
        self.assertEqual(spec.hard_constraints["tier"], 3)

    def test_narrative_pulled_from_requesting_payload(self) -> None:
        registry = _FakeRegistry({
            "p1": {
                "chunks": [
                    {"content_id": "test_biome",
                     "payload_json": {
                         "chunkType": "test_biome",
                         "metadata": {"narrative": "Windswept copper moors."},
                     }},
                ],
            },
        })
        rec = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="copperlash_rider",
            requested_by_step_id="runtime_chunks:test_biome",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [rec], registry=registry, bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        spec = batch.tool_specs["hostiles"][0]
        self.assertEqual(
            spec.flavor_hints["referenced_by_narrative"],
            "Windswept copper moors.",
        )

    def test_unparseable_requested_by_does_not_crash(self) -> None:
        rec = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="x",
            requested_by_step_id="totally_not_runtime_format",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [rec], registry=_FakeRegistry(), bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        self.assertEqual(batch.total_specs(), 1)

    def test_humanize_id_used_as_name_hint_fallback(self) -> None:
        rec = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="moors_copper_seam",
            requested_by_step_id="runtime_quests:q1",
            suggested_intent="",
        )
        batch = self.layer.build_specs(
            [rec], registry=None, bundle=None,
            plan_id="p1", cascade_depth=1,
        )
        spec = batch.tool_specs["materials"][0]
        self.assertEqual(spec.flavor_hints["name_hint"], "Moors Copper Seam")


# ── Dispatcher.run_request_specs integration tests ──────────────────────

class TestDispatcherRunRequestSpecs(unittest.TestCase):
    """Tool-only fan-out tests with fake registry + fake tools."""

    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        # Sync runner — no real threads, no event loop.
        self.runner = AsyncLLMRunner.get_instance()

    def _make_dispatcher(self, tools: Dict[str, _FakeTool]) -> PlanDispatcher:
        return PlanDispatcher(
            hubs={},                 # request layer doesn't use hubs
            tools=tools,
            registry=self.registry,
            async_runner=self.runner,
            orphan_checker=lambda **_: [],   # never reports orphans
            balance_checker=lambda *_a, **_k: None,  # never fails balance
        )

    def test_specs_dispatch_to_correct_tool(self) -> None:
        hostiles_tool = _FakeTool({
            "req_d1_00_hostiles_enemy_a": {
                "enemyId": "enemy_a", "tier": 1,
            }
        })
        dispatcher = self._make_dispatcher({"hostiles": hostiles_tool})

        spec = ExecutorSpec(
            spec_id="req_d1_00_hostiles_enemy_a",
            plan_step_id="request_layer_d1_hostiles",
            item_intent="generate enemy_a",
            hard_constraints={"tier": 1},
        )
        result = dispatcher.run_request_specs(
            {"hostiles": [spec]},
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        self.assertEqual(len(hostiles_tool.calls), 1)
        self.assertEqual(result.staged_content_ids["hostiles"], ["enemy_a"])
        self.assertFalse(result.had_errors())
        self.assertEqual(len(self.registry.staged_calls), 1)
        self.assertEqual(self.registry.staged_calls[0]["tool_name"], "hostiles")

    def test_unknown_tool_records_error_no_crash(self) -> None:
        dispatcher = self._make_dispatcher(tools={})
        spec = ExecutorSpec(
            spec_id="req_d1_00_unknown_x",
            plan_step_id="request_layer_d1_unknown",
            item_intent="x",
        )
        result = dispatcher.run_request_specs(
            {"unknown_tool_xyz": [spec]},
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        # Expect an error but no exception propagated.
        self.assertTrue(result.had_errors())
        self.assertIn("request_layer_d1_unknown_tool_xyz", result.step_errors)

    def test_tool_exception_records_error(self) -> None:
        bad_tool = _FakeTool({
            "req_d1_00_hostiles_x": RuntimeError("boom"),
        })
        dispatcher = self._make_dispatcher({"hostiles": bad_tool})
        spec = ExecutorSpec(
            spec_id="req_d1_00_hostiles_x",
            plan_step_id="request_layer_d1_hostiles",
            item_intent="x",
        )
        result = dispatcher.run_request_specs(
            {"hostiles": [spec]},
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        self.assertTrue(result.had_errors())
        # Error recorded against the synthetic step id.
        errors = result.step_errors["request_layer_d1_hostiles"]
        self.assertTrue(any("boom" in e for e in errors))
        # Nothing staged when generation failed.
        self.assertEqual(len(self.registry.staged_calls), 0)

    def test_non_dict_response_records_error(self) -> None:
        odd_tool = _FakeTool({
            "req_d1_00_hostiles_x": "not a dict",
        })
        dispatcher = self._make_dispatcher({"hostiles": odd_tool})
        spec = ExecutorSpec(
            spec_id="req_d1_00_hostiles_x",
            plan_step_id="request_layer_d1_hostiles",
            item_intent="x",
        )
        result = dispatcher.run_request_specs(
            {"hostiles": [spec]},
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        self.assertTrue(result.had_errors())
        self.assertEqual(len(self.registry.staged_calls), 0)

    def test_orphan_in_response_blocks_staging(self) -> None:
        # Orphan checker is normally injected; here we install one
        # that always reports a missing ref.
        tool = _FakeTool({
            "req_d1_00_quests_x": {
                "quest_id": "x", "tier": 1,
                "given_by": "missing_npc",
            },
        })
        dispatcher = PlanDispatcher(
            hubs={}, tools={"quests": tool}, registry=self.registry,
            async_runner=self.runner,
            orphan_checker=lambda **_: ["missing_npc"],
            balance_checker=lambda *_a, **_k: None,
        )
        spec = ExecutorSpec(
            spec_id="req_d1_00_quests_x",
            plan_step_id="request_layer_d1_quests",
            item_intent="x",
            hard_constraints={"tier": 1},
        )
        result = dispatcher.run_request_specs(
            {"quests": [spec]},
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        # Orphan blocks staging; error recorded.
        self.assertEqual(len(self.registry.staged_calls), 0)
        self.assertTrue(result.had_errors())

    def test_multi_tool_fan_out(self) -> None:
        h_tool = _FakeTool({
            "req_d1_00_hostiles_e1": {"enemyId": "e1", "tier": 1},
        })
        m_tool = _FakeTool({
            "req_d1_01_materials_m1": {"materialId": "m1", "tier": 1},
        })
        dispatcher = self._make_dispatcher({
            "hostiles": h_tool, "materials": m_tool,
        })
        result = dispatcher.run_request_specs(
            {
                "hostiles": [ExecutorSpec(
                    spec_id="req_d1_00_hostiles_e1",
                    plan_step_id="request_layer_d1_hostiles",
                    item_intent="generate e1",
                    hard_constraints={"tier": 1},
                )],
                "materials": [ExecutorSpec(
                    spec_id="req_d1_01_materials_m1",
                    plan_step_id="request_layer_d1_materials",
                    item_intent="generate m1",
                    hard_constraints={"tier": 1},
                )],
            },
            plan_id="p1",
            source_bundle_id="b1",
            cascade_depth=1,
        )
        self.assertEqual(len(h_tool.calls), 1)
        self.assertEqual(len(m_tool.calls), 1)
        self.assertEqual(set(result.staged_content_ids), {"hostiles", "materials"})
        self.assertFalse(result.had_errors())

    def test_empty_tool_specs_returns_empty_result(self) -> None:
        dispatcher = self._make_dispatcher({})
        result = dispatcher.run_request_specs(
            {}, plan_id="p1", source_bundle_id="b1", cascade_depth=1,
        )
        self.assertEqual(result.tier_results, [])
        self.assertEqual(result.staged_content_ids, {})
        self.assertFalse(result.had_errors())


if __name__ == "__main__":
    unittest.main()
