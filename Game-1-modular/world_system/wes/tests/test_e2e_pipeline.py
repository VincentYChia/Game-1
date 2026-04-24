"""End-to-end pseudo-mock WES pipeline test (v4 P5 exit criterion +
P6 gate). Verifies the full stack runs bundle → planner → hub → tool →
registry commit without real LLMs.

Two flavors:

1. **Stub tier pipeline** — uses the P5 stub tiers that consult the P0
   fixture registry directly. Fastest, most deterministic.
2. **LLM tier pipeline** — uses Agent D's LLMExecutionPlanner /
   LLMExecutionHub / LLMExecutorTool / LLMSupervisor, with MockBackend
   routing to fixtures. Exercises the real prompt-assembler +
   JSON-parse + XML-parse paths.

Both pipelines must commit successfully.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid

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
)
from world_system.content_registry.content_registry import ContentRegistry  # noqa: E402
from world_system.wes.tool_registry import WESToolRegistry  # noqa: E402
from world_system.wes.wes_orchestrator import WESOrchestrator  # noqa: E402


def _make_bundle() -> WESContextBundle:
    delta = NarrativeDelta(
        address="region:ashfall_moors",
        layer=4,
        start_time=0.0,
        end_time=100.0,
    )
    ctx = NarrativeContextSlice(
        firing_layer_summary="The moors restructure around copper.",
    )
    directive = WNSDirective(
        directive_text=(
            "Generate content responding to the moors' economic "
            "realignment: new material and new hostile raiding the copper trade."
        ),
        firing_tier=4,
    )
    return WESContextBundle(
        bundle_id=f"bundle_{uuid.uuid4().hex[:8]}",
        created_at=time.time(),
        delta=delta,
        narrative_context=ctx,
        directive=directive,
    )


class _PipelineBase(unittest.TestCase):
    """Fresh ContentRegistry per-test (separate tempdir), fresh orchestrator."""

    def setUp(self) -> None:
        self._tempdir = tempfile.mkdtemp(prefix="wes_e2e_")
        ContentRegistry.reset()
        self._registry = ContentRegistry.get_instance()
        # Bind BOTH save_dir (SQLite) and game_root (generated JSON files)
        # to the tempdir so tests don't pollute sacred content directories.
        self._registry.initialize(
            save_dir=self._tempdir,
            game_root=self._tempdir,
        )

        BackendManager.reset()
        BackendManager.get_instance().initialize()

        WESToolRegistry.reset()
        WESOrchestrator.reset()

    def tearDown(self) -> None:
        WESOrchestrator.reset()
        WESToolRegistry.reset()
        ContentRegistry.reset()
        shutil.rmtree(self._tempdir, ignore_errors=True)


class TestStubPipeline(_PipelineBase):
    """P5 exit: stub tiers + fixture registry → commit."""

    def test_full_pipeline_commits(self) -> None:
        orch = WESOrchestrator.get_instance()
        # Default initialize = stubs. Subscribe to bus disabled for test.
        orch.initialize(
            registry=self._registry,
            subscribe_to_bus=False,
        )

        result = orch.run_plan(_make_bundle())

        self.assertIn(result["status"], ("committed", "abandoned", "rolled_back"),
                      f"unexpected status: {result}")
        # The stub path is designed to commit cleanly.
        self.assertEqual(result["status"], "committed",
                         msg=f"stub pipeline did not commit: {result}")


class TestLLMTierPipeline(_PipelineBase):
    """P6 gate: LLM tiers through MockBackend → fixtures → commit."""

    def test_full_pipeline_commits_with_llm_tiers(self) -> None:
        # Build real LLM tiers from the tool registry.
        reg = WESToolRegistry.get_instance(use_stubs=False)
        reg.initialize()

        hubs = {n: reg.get_hub(n) for n in reg.tool_names()}
        tools = {n: reg.get_tool(n) for n in reg.tool_names()}
        planner = reg.get_planner()
        supervisor = reg.get_supervisor()

        orch = WESOrchestrator.get_instance()
        orch.initialize(
            planner=planner,
            hubs=hubs,
            tools=tools,
            supervisor=supervisor,
            registry=self._registry,
            subscribe_to_bus=False,
        )

        result = orch.run_plan(_make_bundle())

        # The LLM-driven path should also commit cleanly, since the
        # fixtures we provide are cross-reference-clean.
        self.assertIn(result["status"], ("committed", "abandoned", "rolled_back"),
                      f"unexpected status: {result}")
        # Soft assertion — fixtures should be clean; if they're not,
        # dump the full result for diagnosis.
        self.assertEqual(result["status"], "committed",
                         msg=(
                             "LLM-tier pipeline did not commit. Likely a fixture "
                             "cross-reference mismatch or parse error. "
                             f"Full result: {result}"
                         ))


if __name__ == "__main__":
    unittest.main()
