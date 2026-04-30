"""Tests for world_system.wes.plan_resolution."""

from __future__ import annotations

import unittest
from typing import Any, Dict, List

from world_system.wes.dataclasses import WESPlan, WESPlanStep
from world_system.wes.dependency_resolver import CoemitRecommendation
from world_system.wes.plan_resolution import (
    MAX_CASCADE_STEPS_PER_PASS,
    MAX_RUNTIME_CASCADE_DEPTH,
    PLANNER_ACKNOWLEDGMENT_MARKER,
    build_extension_plan,
    build_registry_snapshot,
    build_unresolved_xml_warning,
    evaluate_plan_for_bounce,
    find_runtime_orphans,
    planner_acknowledged,
)


# ── Stub registry for tests (no SQLite dep) ──────────────────────────


class _StubRegistry:
    """Minimal registry exposing list_live + list_staged_by_plan."""

    def __init__(
        self,
        live: Dict[str, List[Dict[str, Any]]] = None,
        staged: Dict[str, Dict[str, List[Dict[str, Any]]]] = None,
    ) -> None:
        # live: {tool: [{content_id, ...}, ...]}
        # staged: {plan_id: {tool: [{content_id, payload_json, ...}, ...]}}
        self._live = live or {}
        self._staged = staged or {}

    def list_live(self, tool_name: str, filters=None) -> List[Dict[str, Any]]:
        return list(self._live.get(tool_name, []))

    def list_staged_by_plan(self, plan_id: str):
        return self._staged.get(plan_id, {})


def _step(step_id: str, tool: str, depends_on=None, **slots) -> WESPlanStep:
    return WESPlanStep(
        step_id=step_id, tool=tool, intent=f"{tool}-{step_id}",
        depends_on=list(depends_on or []), slots=dict(slots),
    )


def _plan(plan_id: str, *steps: WESPlanStep, rationale: str = "") -> WESPlan:
    return WESPlan(
        plan_id=plan_id, source_bundle_id="bundle_test",
        steps=list(steps), rationale=rationale,
    )


# ── Build registry snapshot ──────────────────────────────────────────


class TestBuildRegistrySnapshot(unittest.TestCase):
    def test_none_registry_returns_empty(self) -> None:
        self.assertEqual(build_registry_snapshot(None), {})

    def test_extracts_content_ids_per_tool(self) -> None:
        reg = _StubRegistry(live={
            "materials": [{"content_id": "iron"}, {"content_id": "copper"}],
            "hostiles": [{"content_id": "wolf"}],
        })
        snap = build_registry_snapshot(reg)
        self.assertEqual(snap["materials"], frozenset({"iron", "copper"}))
        self.assertEqual(snap["hostiles"], frozenset({"wolf"}))
        # Empty tools default to empty frozenset
        self.assertEqual(snap["skills"], frozenset())

    def test_registry_without_list_live_returns_empty(self) -> None:
        # Bare object without list_live attribute
        class Bare:
            pass
        self.assertEqual(build_registry_snapshot(Bare()), {})


# ── Bounce-back warning ──────────────────────────────────────────────


class TestUnresolvedXmlWarning(unittest.TestCase):
    def test_satisfiable_returns_empty(self) -> None:
        plan = _plan("p", _step("s1", "materials"))
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        self.assertFalse(decision.bounce)
        self.assertEqual(decision.warning, "")

    def test_unresolved_produces_xml_warning(self) -> None:
        plan = _plan("p", _step(
            "s1", "quests", given_by="orphan_npc", title_hint="orphan_title",
        ))
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        self.assertTrue(decision.bounce)
        self.assertIn("<WES_PLANNER_WARNING>", decision.warning)
        self.assertIn("</WES_PLANNER_WARNING>", decision.warning)
        self.assertIn("orphan_npc", decision.warning)
        self.assertIn("orphan_title", decision.warning)
        self.assertIn("not_in_registry_or_plan", decision.warning)
        # XML escaping: the marker is referenced in the action text
        self.assertIn("wes_plan_acknowledgment", decision.warning)

    def test_xml_well_formed(self) -> None:
        # Smoke check: parse with ElementTree to verify structure.
        import xml.etree.ElementTree as ET
        plan = _plan("p", _step(
            "s1", "quests", given_by="orphan_npc",
        ))
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        tree = ET.fromstring(decision.warning)
        self.assertEqual(tree.tag, "WES_PLANNER_WARNING")
        refs = tree.find("unresolved_refs")
        self.assertIsNotNone(refs)
        ref_elements = list(refs)
        self.assertEqual(len(ref_elements), 1)
        self.assertEqual(ref_elements[0].attrib["target_id"], "orphan_npc")

    def test_planner_acknowledgment_skips_bounce(self) -> None:
        plan = _plan(
            "p",
            _step("s1", "quests", given_by="orphan_npc"),
            rationale=(
                "I am intentionally referencing orphan_npc. "
                + PLANNER_ACKNOWLEDGMENT_MARKER
            ),
        )
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        self.assertFalse(decision.bounce, "acknowledgment should skip bounce")
        # The analysis still has unresolved refs (we still see them)
        self.assertIsNotNone(decision.analysis)
        self.assertFalse(decision.analysis.is_satisfiable)

    def test_acknowledgment_case_insensitive(self) -> None:
        plan = _plan(
            "p",
            _step("s1", "quests", given_by="orphan_npc"),
            rationale="<WES_PLAN_ACKNOWLEDGMENT>TRUE</WES_PLAN_ACKNOWLEDGMENT>",
        )
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        self.assertFalse(decision.bounce)

    def test_abandoned_plan_skips_bounce(self) -> None:
        plan = WESPlan(
            plan_id="p", source_bundle_id="b",
            steps=[], abandoned=True,
            abandonment_reason="bundle was incoherent",
        )
        decision = evaluate_plan_for_bounce(plan, registry=_StubRegistry())
        self.assertFalse(decision.bounce)

    def test_registry_resolves_skips_bounce(self) -> None:
        # missing material is in the registry; no bounce.
        reg = _StubRegistry(live={"materials": [{"content_id": "iron"}]})
        plan = _plan(
            "p",
            _step("s1", "nodes", material_id="iron"),  # no depends_on but resolved via registry
        )
        decision = evaluate_plan_for_bounce(plan, registry=reg)
        self.assertFalse(decision.bounce)


# ── Planner acknowledgment helper ────────────────────────────────────


class TestPlannerAcknowledged(unittest.TestCase):
    def test_marker_in_rationale(self) -> None:
        plan = _plan("p", rationale=PLANNER_ACKNOWLEDGMENT_MARKER)
        self.assertTrue(planner_acknowledged(plan))

    def test_no_marker_returns_false(self) -> None:
        plan = _plan("p", rationale="just a regular rationale")
        self.assertFalse(planner_acknowledged(plan))

    def test_empty_rationale(self) -> None:
        plan = _plan("p")
        self.assertFalse(planner_acknowledged(plan))


# ── Runtime orphans ──────────────────────────────────────────────────


class TestFindRuntimeOrphans(unittest.TestCase):
    def test_no_staged_content_no_orphans(self) -> None:
        reg = _StubRegistry()
        recs = find_runtime_orphans(reg, plan_id="p")
        self.assertEqual(recs, [])

    def test_chunk_referencing_unknown_hostile(self) -> None:
        # The dispatcher staged a chunk that names a hostile we never
        # planned and the registry doesn't have. Cascade should pick it up.
        reg = _StubRegistry(staged={"p_test": {
            "chunks": [{
                "content_id": "moors_chunk",
                "payload_json": {
                    "chunkType": "moors_chunk",
                    "resourceDensity": {"copper_seam": {"density": "high"}},
                    "enemySpawns": {"unknown_raider": {"density": "moderate", "tier": 2}},
                },
            }],
        }})
        recs = find_runtime_orphans(reg, plan_id="p_test")
        types_ids = {(r.missing_ref_type, r.missing_ref_id) for r in recs}
        self.assertIn(("hostiles", "unknown_raider"), types_ids)
        self.assertIn(("nodes", "copper_seam"), types_ids)

    def test_dedup_across_multiple_xrefs(self) -> None:
        reg = _StubRegistry(staged={"p": {
            "hostiles": [
                {"content_id": "a", "payload_json": {
                    "enemyId": "a",
                    "drops": [{"materialId": "shared_mat"}],
                }},
                {"content_id": "b", "payload_json": {
                    "enemyId": "b",
                    "drops": [{"materialId": "shared_mat"}],
                }},
            ],
        }})
        recs = find_runtime_orphans(reg, plan_id="p")
        # Should appear once even though referenced twice
        mat_recs = [r for r in recs if r.missing_ref_id == "shared_mat"]
        self.assertEqual(len(mat_recs), 1)

    def test_sibling_staged_satisfies_ref(self) -> None:
        # Hostile refs material_iron which IS in the same plan's staging.
        reg = _StubRegistry(staged={"p": {
            "materials": [{"content_id": "material_iron",
                           "payload_json": {"materialId": "material_iron"}}],
            "hostiles": [{"content_id": "wolf",
                          "payload_json": {
                              "enemyId": "wolf",
                              "drops": [{"materialId": "material_iron"}],
                          }}],
        }})
        recs = find_runtime_orphans(reg, plan_id="p")
        self.assertEqual(recs, [])

    def test_registry_satisfies_ref(self) -> None:
        reg = _StubRegistry(
            live={"materials": [{"content_id": "ironl"}]},
            staged={"p": {
                "hostiles": [{"content_id": "wolf",
                              "payload_json": {
                                  "enemyId": "wolf",
                                  "drops": [{"materialId": "ironl"}],
                              }}],
            }},
        )
        recs = find_runtime_orphans(reg, plan_id="p")
        self.assertEqual(recs, [])


# ── Extension plan builder ───────────────────────────────────────────


class TestBuildExtensionPlan(unittest.TestCase):
    def test_no_recs_returns_none(self) -> None:
        parent = _plan("primary")
        self.assertIsNone(build_extension_plan(parent, []))

    def test_recs_become_steps(self) -> None:
        parent = _plan("primary")
        recs = [
            CoemitRecommendation(
                missing_ref_type="materials",
                missing_ref_id="moors_copper",
                requested_by_step_id="rt",
                suggested_intent="Auto-gen moors_copper.",
                suggested_slots={"tier": 2, "biome": "moors"},
            ),
            CoemitRecommendation(
                missing_ref_type="hostiles",
                missing_ref_id="copperlash_rider",
                requested_by_step_id="rt",
                suggested_intent="Auto-gen copperlash_rider.",
                suggested_slots={"tier": 2},
            ),
        ]
        ext = build_extension_plan(parent, recs, cascade_depth=1)
        self.assertIsNotNone(ext)
        self.assertEqual(len(ext.steps), 2)
        self.assertTrue(ext.plan_id.startswith("primary_ext"))
        self.assertEqual({s.tool for s in ext.steps}, {"materials", "hostiles"})
        self.assertTrue(ext.steps[0].slots)  # slots inherited

    def test_max_steps_caps(self) -> None:
        parent = _plan("primary")
        recs = [
            CoemitRecommendation(
                missing_ref_type="materials",
                missing_ref_id=f"mat_{i}",
                requested_by_step_id="rt",
                suggested_intent=f"#{i}",
                suggested_slots={},
            )
            for i in range(20)
        ]
        ext = build_extension_plan(parent, recs, cascade_depth=1, max_steps=5)
        self.assertIsNotNone(ext)
        self.assertEqual(len(ext.steps), 5)


class TestKnobs(unittest.TestCase):
    def test_default_max_runtime_cascade_depth(self) -> None:
        self.assertEqual(MAX_RUNTIME_CASCADE_DEPTH, 2)

    def test_default_max_cascade_steps_per_pass(self) -> None:
        self.assertEqual(MAX_CASCADE_STEPS_PER_PASS, 8)


if __name__ == "__main__":
    unittest.main()
