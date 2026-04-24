"""Round-trip tests for the WES data model (§5.2 / §5.3 / PLACEHOLDER §11)."""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wes.dataclasses import (  # noqa: E402
    ExecutorSpec,
    TierRunResult,
    WESPlan,
    WESPlanStep,
)


class WESPlanStepRoundTripTests(unittest.TestCase):
    def test_round_trip_full(self) -> None:
        step = WESPlanStep(
            step_id="s1",
            tool="materials",
            intent="make a copper variant",
            depends_on=["s0"],
            slots={"tier": 2, "biome": "moors"},
        )
        d = step.to_dict()
        step2 = WESPlanStep.from_dict(d)
        self.assertEqual(step, step2)

    def test_round_trip_minimal(self) -> None:
        step = WESPlanStep(step_id="s1", tool="titles", intent="")
        d = step.to_dict()
        self.assertEqual(d["depends_on"], [])
        self.assertEqual(d["slots"], {})
        step2 = WESPlanStep.from_dict(d)
        self.assertEqual(step, step2)


class WESPlanRoundTripTests(unittest.TestCase):
    def test_round_trip_with_steps(self) -> None:
        plan = WESPlan(
            plan_id="plan_abc",
            source_bundle_id="bundle_xyz",
            steps=[
                WESPlanStep(step_id="s1", tool="materials", intent="a"),
                WESPlanStep(
                    step_id="s2", tool="hostiles", intent="b",
                    depends_on=["s1"],
                ),
            ],
            rationale="two-step plan",
        )
        d = plan.to_dict()
        plan2 = WESPlan.from_dict(d)
        self.assertEqual(plan, plan2)

    def test_abandoned_plan(self) -> None:
        plan = WESPlan(
            plan_id="plan_x",
            source_bundle_id="bundle_x",
            steps=[],
            abandoned=True,
            abandonment_reason="bundle too thin",
        )
        plan2 = WESPlan.from_dict(plan.to_dict())
        self.assertTrue(plan2.abandoned)
        self.assertEqual(plan2.abandonment_reason, "bundle too thin")


class ExecutorSpecRoundTripTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        spec = ExecutorSpec(
            spec_id="spec_001",
            plan_step_id="s2",
            item_intent="a moors raider",
            flavor_hints={"name_hint": "Copperlash"},
            cross_ref_hints={"material_id": "moors_copper"},
            hard_constraints={"tier": 2, "biome": "moors"},
        )
        spec2 = ExecutorSpec.from_dict(spec.to_dict())
        self.assertEqual(spec, spec2)

    def test_minimal_defaults_empty_dicts(self) -> None:
        spec = ExecutorSpec(spec_id="s", plan_step_id="p")
        d = spec.to_dict()
        self.assertEqual(d["flavor_hints"], {})
        self.assertEqual(d["cross_ref_hints"], {})
        self.assertEqual(d["hard_constraints"], {})


class TierRunResultRoundTripTests(unittest.TestCase):
    def test_round_trip_with_plan_parsed(self) -> None:
        plan = WESPlan(plan_id="p", source_bundle_id="b")
        t = TierRunResult(
            tier="planner",
            prompt="sys",
            raw_response="{}",
            parsed=plan,
            latency_ms=3.14,
            backend_used="fixture",
            errors=["warn1"],
        )
        d = t.to_dict()
        self.assertEqual(d["parsed"]["plan_id"], "p")
        t2 = TierRunResult.from_dict(d)
        # parsed round-trips as a dict — by design (§TierRunResult docs).
        self.assertEqual(t2.parsed["plan_id"], "p")
        self.assertEqual(t2.tier, "planner")
        self.assertEqual(t2.errors, ["warn1"])

    def test_round_trip_with_list_of_specs(self) -> None:
        specs = [
            ExecutorSpec(spec_id="s1", plan_step_id="p1"),
            ExecutorSpec(spec_id="s2", plan_step_id="p1"),
        ]
        t = TierRunResult(
            tier="hub",
            parsed=specs,
        )
        d = t.to_dict()
        self.assertEqual(len(d["parsed"]), 2)
        self.assertEqual(d["parsed"][0]["spec_id"], "s1")


if __name__ == "__main__":
    unittest.main()
