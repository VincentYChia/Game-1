"""Configuration loader for the World Memory System.

Loads tunable thresholds, windows, and evaluator parameters from
AI-Config.JSON/memory-config.json so they can be checked and modified
without touching Python code.

Usage:
    from world_memory.memory.config_loader import get_memory_config
    cfg = get_memory_config()
    lookback = cfg["evaluators"]["population_change"]["lookback_time"]
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

_CONFIG_FILENAME = "memory-config.json"

# Cached config dict
_cached_config: Optional[Dict[str, Any]] = None
_cached_path: Optional[str] = None


def _find_config_path() -> Optional[str]:
    """Search for memory-config.json relative to common roots."""
    # Try relative to this file: world_memory/memory/ → world_memory/config/
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(this_dir, "..", "config", _CONFIG_FILENAME),
        os.path.join(os.getcwd(), "world_memory", "config", _CONFIG_FILENAME),
    ]
    for path in candidates:
        resolved = os.path.normpath(path)
        if os.path.isfile(resolved):
            return resolved
    return None


def get_memory_config(force_reload: bool = False) -> Dict[str, Any]:
    """Return the memory config dict (cached after first load).

    Falls back to empty dict if no config file found — callers use defaults.
    """
    global _cached_config, _cached_path
    if _cached_config is not None and not force_reload:
        return _cached_config

    path = _find_config_path()
    if path is None:
        _cached_config = {}
        return _cached_config

    with open(path, "r", encoding="utf-8") as f:
        _cached_config = json.load(f)
    _cached_path = path
    return _cached_config


def get_section(section: str) -> Dict[str, Any]:
    """Get a top-level config section (e.g. 'retention', 'evaluators')."""
    return get_memory_config().get(section, {})


def get_evaluator_config(evaluator_name: str) -> Dict[str, Any]:
    """Get config for a specific evaluator (e.g. 'population_change')."""
    evaluators = get_memory_config().get("evaluators", {})
    return evaluators.get(evaluator_name, {})


def get_query_window_config(window_name: str) -> Dict[str, Any]:
    """Get config for a specific query window (e.g. 'npc_local')."""
    windows = get_memory_config().get("query_windows", {})
    return windows.get(window_name, {})


def reload_config() -> Dict[str, Any]:
    """Force reload from disk (for hot-reloading during development)."""
    return get_memory_config(force_reload=True)
