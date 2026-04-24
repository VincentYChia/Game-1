"""WES LLM-backed tier implementations (v4 P6-P9).

Each module here implements one of the four Protocols in
``world_system.wes.protocols``:

- :class:`LLMExecutionPlanner` (:mod:`llm_execution_planner`) — Tier 1.
- :class:`LLMExecutionHub`     (:mod:`llm_execution_hub`)     — Tier 2.
- :class:`LLMExecutorTool`     (:mod:`llm_executor_tool`)     — Tier 3.
- :class:`LLMSupervisor`       (:mod:`llm_supervisor`)        — cross-tier.

Plus:

- :class:`PromptAssembler` (:mod:`prompt_assembler`) — loads JSON prompt
  fragments, substitutes ``${var}`` placeholders, and embeds the shared
  game-awareness / task-awareness blocks.

All tiers call out through ``BackendManager.generate(task="wes_...")``.
When real backends are unavailable, MockBackend consults the P0 LLM
Fixture Registry and returns canonical responses — end-to-end tests run
without any real LLM call via that fixture path.

Graceful degrade: every LLM-facing call is wrapped with
``log_degrade(subsystem="wes", ...)`` on parse/empty/backend failure, per
CC3. Nothing here raises through to the orchestrator; plans can still be
marked abandoned or return empty batches as the relevant tier dictates.
"""

from world_system.wes.llm_tiers.llm_execution_planner import LLMExecutionPlanner
from world_system.wes.llm_tiers.llm_execution_hub import LLMExecutionHub
from world_system.wes.llm_tiers.llm_executor_tool import LLMExecutorTool
from world_system.wes.llm_tiers.llm_supervisor import LLMSupervisor
from world_system.wes.llm_tiers.prompt_assembler import PromptAssembler

__all__ = [
    "LLMExecutionPlanner",
    "LLMExecutionHub",
    "LLMExecutorTool",
    "LLMSupervisor",
    "PromptAssembler",
]
