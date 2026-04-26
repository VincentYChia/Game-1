"""WES tool registry — factory + holder for real LLM-backed tiers (v4 P6-P7).

Constructs one ``LLMExecutionHub`` and one ``LLMExecutorTool`` per tool
type, plus a single ``LLMExecutionPlanner`` and ``LLMSupervisor``. The
WES orchestrator consumes this registry rather than reaching into the
llm_tiers package directly, so swapping to stubs (for tests/offline dev)
is a one-line construction change.

**Contract** — see :mod:`world_system.wes.protocols`. Every object this
registry hands out satisfies the corresponding Protocol.

**Graceful degrade** — if any llm_tiers class fails to import or
initialize, the registry logs via ``graceful_degrade`` and falls back to
the stub tier from :mod:`world_system.wes.stub_tiers` for that role. The
orchestrator never sees a missing tier.
"""

from __future__ import annotations

from typing import ClassVar, Dict, Optional

from world_system.wes.protocols import (
    ExecutionHub,
    ExecutionPlanner,
    ExecutorTool,
    Supervisor,
)


# All eight tool types shipped in v4. The original five (hostiles,
# materials, nodes, skills, titles) were the P6/P7 baseline; chunks,
# npcs, and quests landed in Steps 6-8 with their own hub + tool prompts
# and fixtures. Keeping every tool registered lets a plan reference any
# of them without the registry handing back a stub by accident.
TOOL_NAMES = (
    "hostiles", "materials", "nodes", "skills", "titles",
    "chunks", "npcs", "quests",
)


class WESToolRegistry:
    """Singleton registry of WES LLM tiers.

    Construct-once, read-many. The orchestrator calls ``get_planner``,
    ``get_hub(name)``, ``get_tool(name)``, ``get_supervisor`` per plan
    run; no per-call construction overhead.

    ``use_stubs=True`` forces every role to the stub tier regardless of
    llm_tiers availability. Useful for CI and offline dev.
    """

    _instance: ClassVar[Optional["WESToolRegistry"]] = None

    def __init__(self, use_stubs: bool = False) -> None:
        self._use_stubs = use_stubs
        self._planner: Optional[ExecutionPlanner] = None
        self._supervisor: Optional[Supervisor] = None
        self._hubs: Dict[str, ExecutionHub] = {}
        self._tools: Dict[str, ExecutorTool] = {}
        self._initialized = False

    # ── singleton ────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls, use_stubs: bool = False) -> "WESToolRegistry":
        if cls._instance is None:
            cls._instance = cls(use_stubs=use_stubs)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton and any cached tiers."""
        cls._instance = None

    # ── construction ─────────────────────────────────────────────────

    def initialize(self) -> None:
        """Construct every tier. Idempotent."""
        if self._initialized:
            return

        self._planner = self._build_planner()
        self._supervisor = self._build_supervisor()
        for tool_name in TOOL_NAMES:
            self._hubs[tool_name] = self._build_hub(tool_name)
            self._tools[tool_name] = self._build_tool(tool_name)
        self._initialized = True

    def _build_planner(self) -> ExecutionPlanner:
        if self._use_stubs:
            return self._stub_planner()
        try:
            from world_system.wes.llm_tiers.llm_execution_planner import (
                LLMExecutionPlanner,
            )
            return LLMExecutionPlanner()
        except Exception as e:
            self._log_degrade("planner_construction_failed", e)
            return self._stub_planner()

    def _build_supervisor(self) -> Supervisor:
        if self._use_stubs:
            return self._stub_supervisor()
        try:
            from world_system.wes.llm_tiers.llm_supervisor import LLMSupervisor
            return LLMSupervisor()
        except Exception as e:
            self._log_degrade("supervisor_construction_failed", e)
            return self._stub_supervisor()

    def _build_hub(self, tool_name: str) -> ExecutionHub:
        if self._use_stubs:
            return self._stub_hub(tool_name)
        try:
            from world_system.wes.llm_tiers.llm_execution_hub import (
                LLMExecutionHub,
            )
            return LLMExecutionHub(tool_name=tool_name)
        except Exception as e:
            self._log_degrade(f"hub_{tool_name}_construction_failed", e)
            return self._stub_hub(tool_name)

    def _build_tool(self, tool_name: str) -> ExecutorTool:
        if self._use_stubs:
            return self._stub_tool(tool_name)
        try:
            from world_system.wes.llm_tiers.llm_executor_tool import (
                LLMExecutorTool,
            )
            return LLMExecutorTool(tool_name=tool_name)
        except Exception as e:
            self._log_degrade(f"tool_{tool_name}_construction_failed", e)
            return self._stub_tool(tool_name)

    # ── stub fallbacks ───────────────────────────────────────────────

    @staticmethod
    def _stub_planner() -> ExecutionPlanner:
        from world_system.wes.stub_tiers import StubExecutionPlanner
        return StubExecutionPlanner()

    @staticmethod
    def _stub_supervisor() -> Supervisor:
        # StubSupervisor lives in supervisor_tap (Agent C's file layout).
        from world_system.wes.supervisor_tap import StubSupervisor
        return StubSupervisor()

    @staticmethod
    def _stub_hub(tool_name: str) -> ExecutionHub:
        from world_system.wes.stub_tiers import StubExecutionHub
        return StubExecutionHub(tool_name=tool_name)

    @staticmethod
    def _stub_tool(tool_name: str) -> ExecutorTool:
        from world_system.wes.stub_tiers import StubExecutorTool
        return StubExecutorTool(tool_name=tool_name)

    # ── public access ────────────────────────────────────────────────

    def get_planner(self) -> ExecutionPlanner:
        if not self._initialized:
            self.initialize()
        assert self._planner is not None
        return self._planner

    def get_supervisor(self) -> Supervisor:
        if not self._initialized:
            self.initialize()
        assert self._supervisor is not None
        return self._supervisor

    def get_hub(self, tool_name: str) -> ExecutionHub:
        if not self._initialized:
            self.initialize()
        if tool_name not in self._hubs:
            raise KeyError(f"No hub registered for tool '{tool_name}'")
        return self._hubs[tool_name]

    def get_tool(self, tool_name: str) -> ExecutorTool:
        if not self._initialized:
            self.initialize()
        if tool_name not in self._tools:
            raise KeyError(f"No executor_tool registered for tool '{tool_name}'")
        return self._tools[tool_name]

    def tool_names(self) -> tuple:
        """Return the canonical tool-type tuple."""
        return TOOL_NAMES

    @property
    def stats(self) -> Dict[str, object]:
        return {
            "initialized": self._initialized,
            "use_stubs": self._use_stubs,
            "hubs": list(self._hubs.keys()),
            "tools": list(self._tools.keys()),
            "has_planner": self._planner is not None,
            "has_supervisor": self._supervisor is not None,
        }

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _log_degrade(operation: str, exc: BaseException) -> None:
        try:
            from world_system.living_world.infra.graceful_degrade import (
                log_degrade,
            )
            log_degrade(
                subsystem="wes_tool_registry",
                operation=operation,
                failure_reason=f"{type(exc).__name__}: {exc}",
                fallback_taken="stub tier used",
                severity="warning",
            )
        except Exception:
            pass


def get_tool_registry(use_stubs: bool = False) -> WESToolRegistry:
    """Module-level accessor following project singleton pattern."""
    return WESToolRegistry.get_instance(use_stubs=use_stubs)
