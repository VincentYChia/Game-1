"""Phase 5 DAG behavior-inheritance cascade tests (2026-06-03).

Per consolidation §2.1 / Wave 4 §7.3: when a mixed-trigger chunk
firing produces a DAG cascade (nodes / hostiles / materials), the
chunk's behavior-flavor MUST propagate down so the spawned ecosystem
shares the player's identity.

The user's chunks pseudo-trace example: NPC rumors of new terrains
+ exploration milestone + heavy alchemy activity →
alchemy-themed chunk → alchemy-tinted nodes + alchemy-tinted
hostiles + alchemy-tinted materials all share the flavor.

This file tests the RequestLayer propagation surface — when a
cascade spec is built, the parent's behavior_inheritance flavor
should land on the cascade spec's flavor_hints.
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


def _make_bundle(behavior_signal=None):
    from world_system.living_world.infra.context_bundle import (
        NarrativeContextSlice,
        NarrativeDelta,
        WESContextBundle,
        WNSDirective,
    )
    return WESContextBundle(
        bundle_id="bundle_phase5_probe",
        created_at=42.0,
        delta=NarrativeDelta(
            address="region:ashfall_moors", layer=4,
            start_time=40.0, end_time=42.0,
        ),
        narrative_context=NarrativeContextSlice(
            firing_layer_summary="moors restructure", parent_summaries={},
            open_threads=[],
        ),
        directive=WNSDirective(
            directive_text="probe", firing_tier=4,
            scope_hint={"firing_address": "region:ashfall_moors",
                        "purpose": "new-chunk"},
        ),
        behavior_signal=behavior_signal,
    )


class RequestLayerInheritanceTests(unittest.TestCase):
    def test_behavior_inheritance_from_parent_payload(self) -> None:
        # When the cascade is fired from a chunk whose flavor_hints
        # carries behavior_inheritance="alchemy", the cascade spec
        # for a missing material should inherit "alchemy".
        from world_system.wes.request_layer import RequestLayer
        from world_system.wes.dependency_resolver import (
            CoemitRecommendation,
        )

        bundle = _make_bundle()
        layer = RequestLayer()

        # Stub registry matching list_staged_by_plan's actual shape:
        # {tool: [{content_id, payload_json}, ...]}.
        class _StubRegistry:
            def list_staged_by_plan(self, plan_id):
                return {
                    "chunks": [
                        {
                            "content_id": "ashfall_alchemy_bog",
                            "payload_json": {
                                "chunkType": "ashfall_alchemy_bog",
                                "flavor_hints": {
                                    "behavior_inheritance": "alchemy",
                                },
                            },
                        },
                    ],
                }

            def list_live(self, tool):
                return {}

        # _parse_requested_by expects runtime_<tool>:<content_id> with COLON.
        rec = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="fungal_spore_essence",
            requested_by_step_id="runtime_chunks:ashfall_alchemy_bog",
            suggested_intent="",
        )
        target, spec = layer.build_one(
            rec, registry=_StubRegistry(), bundle=bundle,
            plan_id="plan_test", cascade_depth=1, idx=0,
        )
        self.assertEqual(target, "materials")
        self.assertIsNotNone(spec)
        self.assertEqual(
            spec.flavor_hints.get("behavior_inheritance"), "alchemy",
            "cascade spec must inherit parent's flavor",
        )

    def test_behavior_inheritance_from_bundle_signal_when_no_payload(self) -> None:
        # When the parent payload is missing but the bundle has a
        # behavior_signal with a dominant category, the cascade spec
        # falls back to the dominant category.
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
        )
        from world_system.wes.request_layer import RequestLayer
        from world_system.wes.dependency_resolver import (
            CoemitRecommendation,
        )

        bundle = _make_bundle(behavior_signal=BehaviorSignal(
            counter_path="crafting.alchemy.locality.tarmouth",
            threshold_crossed=500, stream_count=500,
            locality_id="tarmouth",
            activity_profile={"alchemy": 0.6, "combat": 0.3, "gathering": 0.1},
        ))
        layer = RequestLayer()

        class _StubRegistry:
            def list_staged_by_plan(self, plan_id):
                return {}

            def list_live(self, tool):
                return {}

        rec = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="probe_material",
            requested_by_step_id="",
            suggested_intent="",  # no parent payload
        )
        _, spec = layer.build_one(
            rec, registry=_StubRegistry(), bundle=bundle,
            plan_id="plan_test", cascade_depth=1, idx=0,
        )
        self.assertIsNotNone(spec)
        self.assertEqual(
            spec.flavor_hints.get("behavior_inheritance"), "alchemy",
            "fallback to dominant category in activity_profile",
        )

    def test_no_inheritance_when_no_signal_no_payload(self) -> None:
        # Plain narrative-causal cascade with no parent payload and no
        # behavior_signal → no behavior_inheritance hint set.
        from world_system.wes.request_layer import RequestLayer
        from world_system.wes.dependency_resolver import (
            CoemitRecommendation,
        )

        bundle = _make_bundle()
        layer = RequestLayer()

        class _StubRegistry:
            def list_staged_by_plan(self, plan_id):
                return {}

            def list_live(self, tool):
                return {}

        rec = CoemitRecommendation(
            missing_ref_type="hostiles",
            missing_ref_id="probe_hostile",
            requested_by_step_id="",
            suggested_intent="",
        )
        _, spec = layer.build_one(
            rec, registry=_StubRegistry(), bundle=bundle,
            plan_id="plan_test", cascade_depth=1, idx=0,
        )
        self.assertIsNotNone(spec)
        self.assertNotIn(
            "behavior_inheritance", spec.flavor_hints,
            "no inheritance should land when nothing supplies it",
        )

    def test_subdominant_activity_does_not_inherit(self) -> None:
        # When the dominant activity is below 0.4, no inheritance fires
        # — too noisy to derive a flavor.
        from world_system.living_world.infra.context_bundle import (
            BehaviorSignal,
        )
        from world_system.wes.request_layer import RequestLayer
        from world_system.wes.dependency_resolver import (
            CoemitRecommendation,
        )

        bundle = _make_bundle(behavior_signal=BehaviorSignal(
            counter_path="x", threshold_crossed=100, stream_count=100,
            locality_id="tarmouth",
            activity_profile={"combat": 0.35, "gathering": 0.33,
                              "crafting": 0.32},
        ))
        layer = RequestLayer()

        class _StubRegistry:
            def list_staged_by_plan(self, plan_id):
                return {}

            def list_live(self, tool):
                return {}

        rec = CoemitRecommendation(
            missing_ref_type="materials",
            missing_ref_id="probe_material",
            requested_by_step_id="",
            suggested_intent="",
        )
        _, spec = layer.build_one(
            rec, registry=_StubRegistry(), bundle=bundle,
            plan_id="plan_test", cascade_depth=1, idx=0,
        )
        self.assertIsNotNone(spec)
        self.assertNotIn(
            "behavior_inheritance", spec.flavor_hints,
            "noisy activity profile should not infer a flavor",
        )


if __name__ == "__main__":
    unittest.main()
