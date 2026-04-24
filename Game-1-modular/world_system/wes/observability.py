"""WES observability — structured logging per §8.11.

File layout (§8.11)::

    llm_debug_logs/
      └─ wes/
         └─ <plan_id>/
            ├─ bundle.json                       # WNS-authored bundle
            ├─ execution_planner.json            # tier 1 I/O
            ├─ hub_<tool>_<step>.json            # one per plan step
            ├─ tool_<tool>_<step>_<spec>.json    # parallel fan-out
            └─ supervisor.json                   # supervisor trace

The orchestrator calls these functions at tier boundaries; this module
owns file layout, serialization, and the "never raises" contract shared
with :mod:`graceful_degrade`.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any, Dict, Optional

from world_system.wes.dataclasses import TierRunResult


# Module-level log root — overridable by tests via ``set_wes_log_root``.
_DEFAULT_WES_LOG_ROOT = os.path.join("llm_debug_logs", "wes")

_root_lock = threading.Lock()
_wes_log_root = _DEFAULT_WES_LOG_ROOT


def set_wes_log_root(path: str) -> None:
    """Override the base ``llm_debug_logs/wes`` directory.

    Tests call this to redirect logs into a tmp directory; production
    code leaves it alone.
    """
    global _wes_log_root
    with _root_lock:
        _wes_log_root = path


def get_wes_log_root() -> str:
    with _root_lock:
        return _wes_log_root


def plan_log_dir(plan_id: str) -> str:
    """Directory for a plan's logs. Created lazily on first write."""
    safe = "".join(
        c if c.isalnum() or c in ("_", "-") else "_" for c in plan_id
    )
    return os.path.join(get_wes_log_root(), safe)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` as indented JSON. Never raises."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, default=str)
    except Exception as e:  # pragma: no cover — disk-failure path
        sys.stderr.write(
            f"[wes.observability] failed to write {path}: {e}\n"
        )


def write_bundle(plan_id: str, bundle_dict: Dict[str, Any]) -> str:
    """Persist the WNS-authored bundle alongside a plan's logs.

    Args:
        plan_id: The plan whose log directory this belongs to.
        bundle_dict: Serialized bundle (``WESContextBundle.to_dict()``).

    Returns:
        The path written.
    """
    path = os.path.join(plan_log_dir(plan_id), "bundle.json")
    _write_json(path, bundle_dict)
    return path


def write_planner(plan_id: str, result: TierRunResult) -> str:
    """Persist the planner tier result."""
    path = os.path.join(plan_log_dir(plan_id), "execution_planner.json")
    _write_json(path, result.to_dict())
    return path


def write_hub(plan_id: str, tool: str, step_id: str,
              result: TierRunResult) -> str:
    """Persist a hub tier result for one plan step.

    Filename::

        hub_<tool>_<step>.json
    """
    filename = f"hub_{tool}_{step_id}.json"
    path = os.path.join(plan_log_dir(plan_id), filename)
    _write_json(path, result.to_dict())
    return path


def write_tool(plan_id: str, tool: str, step_id: str, spec_id: str,
               result: TierRunResult) -> str:
    """Persist one executor_tool result.

    Filename::

        tool_<tool>_<step>_<spec>.json
    """
    filename = f"tool_{tool}_{step_id}_{spec_id}.json"
    path = os.path.join(plan_log_dir(plan_id), filename)
    _write_json(path, result.to_dict())
    return path


def write_supervisor(plan_id: str, result: TierRunResult) -> str:
    """Persist the supervisor tier result (once per plan pass)."""
    path = os.path.join(plan_log_dir(plan_id), "supervisor.json")
    _write_json(path, result.to_dict())
    return path


def write_verification(plan_id: str, verification: Dict[str, Any]) -> str:
    """Persist final-verification outcome (§5.6).

    Supplementary log — not in the §8.11 file list but useful for
    debugging commits vs rollbacks.
    """
    path = os.path.join(plan_log_dir(plan_id), "verification.json")
    _write_json(path, verification)
    return path


__all__ = [
    "set_wes_log_root",
    "get_wes_log_root",
    "plan_log_dir",
    "write_bundle",
    "write_planner",
    "write_hub",
    "write_tool",
    "write_supervisor",
    "write_verification",
]
