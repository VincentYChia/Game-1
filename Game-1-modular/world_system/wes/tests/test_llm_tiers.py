"""Tests for Agent D's LLM-backed WES tiers (v4 P6-P9).

Uses the P0 fixture registry + MockBackend so the full tier stack can be
exercised without touching real LLMs. Each test verifies Protocol
conformance and output shape — not prompt quality (which is placeholder).
"""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.living_world.backends.backend_manager import (  # noqa: E402
    BackendManager,
)
from world_system.living_world.infra.context_bundle import (  # noqa: E402
    NarrativeContextSlice,
    NarrativeDelta,
    WESContextBundle,
    WNSDirective,
    slice_bundle_for_tool,
)
from world_system.wes.dataclasses import (  # noqa: E402
    ExecutorSpec,
    TierRunResult,
    WESPlan,
    WESPlanStep,
)
from world_system.wes.protocols import (  # noqa: E402
    ExecutionHub,
    ExecutionPlanner,
    ExecutorTool,
    Supervisor,
)


def _sample_bundle(firing_tier: int = 4) -> WESContextBundle:
    delta = NarrativeDelta(
        address="region:ashfall_moors",
        layer=firing_tier,
        start_time=0.0,
        end_time=100.0,
    )
    ctx = NarrativeContextSlice(
        firing_layer_summary="The moors restructure around the copper trade.",
        parent_summaries={"5:nation:valdren": "Valdren strains under dual crises."},
        open_threads=[],
    )
    directive = WNSDirective(
        directive_text="Generate content responding to the moors' economic realignment.",
        firing_tier=firing_tier,
        scope_hint={"biome": "moors", "tier": 2},
    )
    return WESContextBundle(
        bundle_id="bundle_test_001",
        created_at=100.0,
        delta=delta,
        narrative_context=ctx,
        directive=directive,
        source_narrative_layer_ids=[],
    )


class _BackendInit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        BackendManager.reset()
        BackendManager.get_instance().initialize()


class TestLLMExecutionPlanner(_BackendInit):
    def test_plan_returns_WESPlan(self) -> None:
        from world_system.wes.llm_tiers.llm_execution_planner import (
            LLMExecutionPlanner,
        )
        planner = LLMExecutionPlanner()
        self.assertIsInstance(planner, ExecutionPlanner)  # Protocol runtime check

        bundle = _sample_bundle()
        plan = planner.plan(bundle)

        self.assertIsInstance(plan, WESPlan)
        self.assertEqual(plan.source_bundle_id, bundle.bundle_id)
        # Planner fixture produces a non-abandoned plan with 2 steps.
        self.assertFalse(plan.abandoned)
        self.assertGreater(len(plan.steps), 0)
        for step in plan.steps:
            self.assertIsInstance(step, WESPlanStep)
            self.assertTrue(step.tool)
            self.assertTrue(step.step_id)


class TestLLMExecutionHub(_BackendInit):
    def test_build_specs_returns_list_of_ExecutorSpec(self) -> None:
        from world_system.wes.llm_tiers.llm_execution_hub import LLMExecutionHub
        hub = LLMExecutionHub(tool_name="hostiles")
        self.assertIsInstance(hub, ExecutionHub)
        self.assertEqual(hub.name, "hostiles")

        bundle = _sample_bundle()
        slice_ = slice_bundle_for_tool(bundle, tool_name="hostiles")
        step = WESPlanStep(
            step_id="s1",
            tool="hostiles",
            intent="new bandit type exploiting copper trade",
            depends_on=[],
            slots={"tier": 2, "biome": "moors", "role": "raider"},
        )

        specs = hub.build_specs(step, slice_)
        self.assertIsInstance(specs, list)
        self.assertGreater(len(specs), 0)
        for spec in specs:
            self.assertIsInstance(spec, ExecutorSpec)
            self.assertEqual(spec.plan_step_id, "s1")
            self.assertTrue(spec.item_intent)

    def test_name_matches_every_tool(self) -> None:
        from world_system.wes.llm_tiers.llm_execution_hub import LLMExecutionHub
        for tool in (
            "hostiles", "materials", "nodes", "skills", "titles",
            "chunks", "npcs", "quests",
        ):
            h = LLMExecutionHub(tool_name=tool)
            self.assertEqual(h.name, tool)


class TestLLMExecutorTool(_BackendInit):
    def test_generate_returns_dict(self) -> None:
        from world_system.wes.llm_tiers.llm_executor_tool import LLMExecutorTool
        tool = LLMExecutorTool(tool_name="materials")
        self.assertIsInstance(tool, ExecutorTool)
        self.assertEqual(tool.name, "materials")

        spec = ExecutorSpec(
            spec_id="spec_t",
            plan_step_id="s1",
            item_intent="moors-specific copper variant",
            flavor_hints={"name_hint": "Moors Copper"},
            cross_ref_hints={},
            hard_constraints={"tier": 2, "category": "ore", "biome": "moors"},
        )
        out = tool.generate(spec)
        self.assertIsInstance(out, dict)
        # Material fixture uses sacred-file key 'materialId' post-2026-04-24;
        # xref_rules also accepts 'material_id' for tolerance, so either passes.
        self.assertTrue(
            "materialId" in out or "material_id" in out,
            f"expected materialId (or material_id), got keys: {list(out.keys())}",
        )
        self.assertIn("tier", out)

    def test_every_tool_type_constructs(self) -> None:
        from world_system.wes.llm_tiers.llm_executor_tool import LLMExecutorTool
        for tool in (
            "hostiles", "materials", "nodes", "skills", "titles",
            "chunks", "npcs", "quests",
        ):
            t = LLMExecutorTool(tool_name=tool)
            self.assertEqual(t.name, tool)


class TestLLMSupervisor(_BackendInit):
    def test_review_returns_verdict_dict(self) -> None:
        from world_system.wes.llm_tiers.llm_supervisor import LLMSupervisor
        sup = LLMSupervisor()
        self.assertIsInstance(sup, Supervisor)

        bundle = _sample_bundle()
        plan = WESPlan(
            plan_id="plan_test",
            source_bundle_id=bundle.bundle_id,
            steps=[],
            rationale="stub",
        )
        tier_results: list[TierRunResult] = []

        verdict = sup.review(plan, tier_results, bundle)
        self.assertIsInstance(verdict, dict)
        self.assertIn("verdict", verdict)
        self.assertIn("rerun", verdict)
        self.assertIn(verdict["verdict"], ("pass", "fail"))


class TestPromptAssembler(unittest.TestCase):
    def test_build_substitutes_variables(self) -> None:
        from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler
        # Pick any shipped fragments file (a placeholder exists for planner).
        path = os.path.join(
            _game_dir, "world_system", "config",
            "prompt_fragments_wes_execution_planner.json",
        )
        if not os.path.exists(path):
            self.skipTest("planner fragments file not present")
        pa = PromptAssembler(path)
        prompts = pa.build({"bundle_delta": "x", "bundle_directive": "y",
                            "bundle_narrative_context": "z",
                            "registry_counts": "0"}, firing_tier=4)
        self.assertIn("system", prompts)
        self.assertIn("user", prompts)
        self.assertIsInstance(prompts["system"], str)
        self.assertIsInstance(prompts["user"], str)


if __name__ == "__main__":
    unittest.main()
