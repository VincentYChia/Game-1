"""Tests for WESToolRegistry (v4 P6-P7)."""

from __future__ import annotations

import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.wes.protocols import (  # noqa: E402
    ExecutionHub,
    ExecutionPlanner,
    ExecutorTool,
    Supervisor,
)
from world_system.wes.tool_registry import (  # noqa: E402
    TOOL_NAMES,
    WESToolRegistry,
    get_tool_registry,
)


class TestWESToolRegistry(unittest.TestCase):
    def setUp(self) -> None:
        WESToolRegistry.reset()

    def tearDown(self) -> None:
        WESToolRegistry.reset()

    def test_singleton(self) -> None:
        a = WESToolRegistry.get_instance()
        b = WESToolRegistry.get_instance()
        self.assertIs(a, b)
        self.assertIs(a, get_tool_registry())

    def test_all_tool_names_exported(self) -> None:
        self.assertEqual(
            sorted(TOOL_NAMES),
            sorted((
                "hostiles", "materials", "nodes", "skills", "titles",
                "chunks", "npcs", "quests",
            )),
        )

    def test_initialize_builds_every_role(self) -> None:
        reg = WESToolRegistry(use_stubs=True)
        reg.initialize()

        self.assertIsInstance(reg.get_planner(), ExecutionPlanner)
        self.assertIsInstance(reg.get_supervisor(), Supervisor)
        for name in TOOL_NAMES:
            hub = reg.get_hub(name)
            tool = reg.get_tool(name)
            self.assertIsInstance(hub, ExecutionHub)
            self.assertIsInstance(tool, ExecutorTool)
            self.assertEqual(hub.name, name)
            self.assertEqual(tool.name, name)

    def test_use_stubs_forces_stub_tiers(self) -> None:
        reg = WESToolRegistry(use_stubs=True)
        reg.initialize()
        from world_system.wes.stub_tiers import StubExecutionPlanner
        from world_system.wes.supervisor_tap import StubSupervisor
        self.assertIsInstance(reg.get_planner(), StubExecutionPlanner)
        self.assertIsInstance(reg.get_supervisor(), StubSupervisor)

    def test_unknown_tool_raises(self) -> None:
        reg = WESToolRegistry(use_stubs=True)
        reg.initialize()
        with self.assertRaises(KeyError):
            reg.get_hub("ecosystem")   # dropped per v4
        with self.assertRaises(KeyError):
            reg.get_tool("dialogue")   # never a WES tool

    def test_lazy_initialization_through_get_planner(self) -> None:
        reg = WESToolRegistry(use_stubs=True)
        self.assertFalse(reg.stats["initialized"])
        _ = reg.get_planner()
        self.assertTrue(reg.stats["initialized"])

    def test_default_attempts_real_llm_tiers(self) -> None:
        """Without use_stubs, real LLM tiers are constructed. They should
        still satisfy Protocol (MockBackend routes to fixtures)."""
        reg = WESToolRegistry(use_stubs=False)
        reg.initialize()
        self.assertIsInstance(reg.get_planner(), ExecutionPlanner)
        self.assertIsInstance(reg.get_supervisor(), Supervisor)
        for name in TOOL_NAMES:
            self.assertIsInstance(reg.get_hub(name), ExecutionHub)
            self.assertIsInstance(reg.get_tool(name), ExecutorTool)


if __name__ == "__main__":
    unittest.main()
