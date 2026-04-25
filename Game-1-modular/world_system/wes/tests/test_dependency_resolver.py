"""Tests for world_system.wes.dependency_resolver."""

from __future__ import annotations

import unittest

from world_system.wes.dataclasses import WESPlan, WESPlanStep
from world_system.wes.dependency_resolver import (
    SLOT_REF_KEYS,
    analyze_plan_dependencies,
)


def _step(step_id: str, tool: str, depends_on=None, **slots) -> WESPlanStep:
    return WESPlanStep(
        step_id=step_id,
        tool=tool,
        intent=f"{tool} step {step_id}",
        depends_on=list(depends_on or []),
        slots=dict(slots),
    )


def _plan(plan_id: str, *steps: WESPlanStep) -> WESPlan:
    return WESPlan(plan_id=plan_id, source_bundle_id="bundle_test", steps=list(steps))


class TestEmptyAndLeafPlans(unittest.TestCase):
    def test_empty_plan_is_satisfiable(self) -> None:
        plan = _plan("p_empty")
        a = analyze_plan_dependencies(plan)
        self.assertTrue(a.is_satisfiable)
        self.assertEqual(a.resolved_refs, [])
        self.assertEqual(a.unresolved_refs, [])

    def test_leaf_only_plan_has_no_refs(self) -> None:
        # Materials and skills are leaves — no cross-refs to extract.
        plan = _plan(
            "p_leaves",
            _step("s1", "materials", tier=2, biome="moors"),
            _step("s2", "skills", tier=2),
        )
        a = analyze_plan_dependencies(plan)
        self.assertTrue(a.is_satisfiable)
        self.assertEqual(len(a.resolved_refs), 0)


class TestSamePlanUpstream(unittest.TestCase):
    def test_node_resolves_via_upstream_material(self) -> None:
        plan = _plan(
            "p_node",
            _step("s1", "materials", tier=2, biome="moors"),
            _step("s2", "nodes", depends_on=["s1"], material_id="moors_copper"),
        )
        a = analyze_plan_dependencies(plan)
        self.assertTrue(a.is_satisfiable)
        self.assertEqual(len(a.resolved_refs), 1)
        self.assertEqual(a.resolved_refs[0].resolution, "same_plan_upstream")
        self.assertEqual(a.resolved_refs[0].target_tool, "materials")
        self.assertEqual(a.resolved_refs[0].target_id, "moors_copper")

    def test_chunk_resolves_lists_via_upstream(self) -> None:
        plan = _plan(
            "p_chunk",
            _step("s1", "nodes", material_id="x"),
            _step("s2", "hostiles"),
            _step(
                "s3", "chunks", depends_on=["s1", "s2"],
                primary_resource_ids=["seam_a", "seam_b"],
                primary_enemy_ids=["raider"],
            ),
        )
        a = analyze_plan_dependencies(plan)
        # chunks->nodes (2 ids) + chunks->hostiles (1 id). nodes->materials orphan.
        chunk_resolved = [r for r in a.resolved_refs if r.source_step_id == "s3"]
        self.assertEqual(len(chunk_resolved), 3)


class TestRegistryResolution(unittest.TestCase):
    def test_registry_resolves_orphan_ref(self) -> None:
        plan = _plan(
            "p_reg",
            # s2 has no depends_on for s1, but registry has the material:
            _step("s1", "materials"),
            _step("s2", "nodes", material_id="committed_iron"),
        )
        registry = {"materials": frozenset({"committed_iron"})}
        a = analyze_plan_dependencies(plan, registry_snapshot=registry)
        self.assertTrue(a.is_satisfiable)
        self.assertEqual(len(a.resolved_refs), 1)
        self.assertEqual(a.resolved_refs[0].resolution, "registry")


class TestUnresolvedRefs(unittest.TestCase):
    def test_missing_depends_on_distinguished_from_truly_missing(self) -> None:
        plan = _plan(
            "p_missing_dep",
            _step("s1", "materials"),
            _step("s2", "nodes", material_id="moors_copper"),  # no depends_on!
        )
        a = analyze_plan_dependencies(plan)
        self.assertFalse(a.is_satisfiable)
        self.assertEqual(len(a.unresolved_refs), 1)
        self.assertEqual(a.unresolved_refs[0].reason, "missing_depends_on")
        # No co-emit recommendation for this case — it's a planner bug,
        # not a content gap.
        self.assertEqual(len(a.coemit_recommendations), 0)

    def test_truly_missing_ref_emits_coemit_recommendation(self) -> None:
        plan = _plan(
            "p_orphan",
            _step("s1", "quests", given_by="orphan_npc", title_hint="orphan_title"),
        )
        a = analyze_plan_dependencies(plan)
        self.assertFalse(a.is_satisfiable)
        self.assertEqual(len(a.unresolved_refs), 2)
        for u in a.unresolved_refs:
            self.assertEqual(u.reason, "not_in_registry_or_plan")
        self.assertEqual(len(a.coemit_recommendations), 2)
        rec_targets = {(r.missing_ref_type, r.missing_ref_id) for r in a.coemit_recommendations}
        self.assertIn(("npcs", "orphan_npc"), rec_targets)
        self.assertIn(("titles", "orphan_title"), rec_targets)

    def test_coemit_recommendation_inherits_thematic_slots(self) -> None:
        plan = _plan(
            "p_inherit",
            _step("s1", "quests", tier=3, biome="moors", given_by="orphan_npc"),
        )
        a = analyze_plan_dependencies(plan)
        self.assertEqual(len(a.coemit_recommendations), 1)
        rec = a.coemit_recommendations[0]
        self.assertEqual(rec.suggested_slots.get("tier"), 3)
        self.assertEqual(rec.suggested_slots.get("biome"), "moors")

    def test_coemit_dedup(self) -> None:
        # Two steps reference the same missing target — only one recommendation.
        plan = _plan(
            "p_dedup",
            _step("s1", "quests", given_by="orphan_npc"),
            _step("s2", "quests", given_by="orphan_npc"),
        )
        a = analyze_plan_dependencies(plan)
        self.assertEqual(len(a.coemit_recommendations), 1)
        # But each unresolved_ref entry is independent (one per source step).
        self.assertEqual(len(a.unresolved_refs), 2)


class TestQuestTargetSpecialCase(unittest.TestCase):
    def test_quest_target_id_with_target_tool(self) -> None:
        plan = _plan(
            "p_quest_target",
            _step("s1", "hostiles"),
            _step(
                "s2", "quests", depends_on=["s1"],
                target_id="copperlash_rider", target_tool="hostiles",
                given_by="some_npc",
            ),
        )
        a = analyze_plan_dependencies(
            plan, registry_snapshot={"npcs": frozenset({"some_npc"})}
        )
        # target_id resolves via upstream s1, given_by via registry.
        target_resolved = [
            r for r in a.resolved_refs
            if r.target_id == "copperlash_rider"
        ]
        self.assertEqual(len(target_resolved), 1)
        self.assertEqual(target_resolved[0].resolution, "same_plan_upstream")

    def test_quest_target_without_target_tool_skipped(self) -> None:
        # 'combat' objective_type doesn't have a target — target_tool absent.
        plan = _plan(
            "p_combat_obj",
            _step(
                "s1", "quests",
                given_by="committed_npc", target_id="something",
                # no target_tool — should be skipped silently
            ),
        )
        a = analyze_plan_dependencies(
            plan, registry_snapshot={"npcs": frozenset({"committed_npc"})}
        )
        # given_by resolves; target_id is silently skipped.
        target_refs = [
            r for r in a.resolved_refs + a.unresolved_refs
            if r.target_id == "something"
        ]
        self.assertEqual(len(target_refs), 0)


class TestFullMoorsEcosystem(unittest.TestCase):
    """End-to-end: the canonical 8-step moors plan should be fully satisfiable
    against an empty registry (every cross-ref resolves via depends_on)."""

    def test_full_moors_plan_satisfiable(self) -> None:
        plan = _plan(
            "p_moors_full",
            _step("s1", "materials", tier=2, biome="moors"),
            _step("s2", "nodes", depends_on=["s1"], material_id="moors_copper"),
            _step("s3", "skills", tier=2),
            _step("s4", "hostiles", depends_on=["s1", "s3"], tier=2, biome="moors"),
            _step(
                "s5", "chunks", depends_on=["s2", "s4"],
                primary_resource_ids=["moors_copper_seam"],
                primary_enemy_ids=["copperlash_rider"],
            ),
            _step(
                "s6", "npcs", depends_on=["s5", "s3"],
                home_chunk="dangerous_copper_moors",
                teachable_skill_ids=["copperlash_gash"],
            ),
            _step("s7", "titles", depends_on=["s4"]),
            _step(
                "s8", "quests", depends_on=["s6", "s4", "s7"],
                given_by="moors_copperlash_captain",
                target_id="copperlash_rider", target_tool="hostiles",
                title_hint="apprentice_moors_reaver",
            ),
        )
        a = analyze_plan_dependencies(plan)
        self.assertTrue(
            a.is_satisfiable,
            f"unresolved: {[(u.source_step_id, u.target_id) for u in a.unresolved_refs]}",
        )
        # Expected count of cross-refs threaded through the plan.
        # s2->materials, s5->nodes, s5->hostiles, s6->chunks, s6->skills,
        # s8->npcs (given_by), s8->hostiles (target), s8->titles
        self.assertEqual(len(a.resolved_refs), 8)


class TestSlotRefKeysSchema(unittest.TestCase):
    """Sanity checks on the SLOT_REF_KEYS table itself."""

    def test_every_target_tool_is_known(self) -> None:
        known_tools = set(SLOT_REF_KEYS.keys())
        for tool, rules in SLOT_REF_KEYS.items():
            for slot_key, target_tool, _ in rules:
                if target_tool is not None:
                    self.assertIn(
                        target_tool, known_tools,
                        f"{tool}.{slot_key} -> unknown target tool {target_tool!r}",
                    )

    def test_all_8_tools_have_entries(self) -> None:
        expected = {"materials", "nodes", "hostiles", "skills", "titles",
                    "chunks", "npcs", "quests"}
        self.assertEqual(set(SLOT_REF_KEYS.keys()), expected)


if __name__ == "__main__":
    unittest.main()
