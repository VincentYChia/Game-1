"""Lightweight JSON config schema validator (2026-06-09).

Closes Cross-cutting Risk #5 — until now, missing or mistyped keys in
JSON configs silently fell back to hardcoded defaults across many
subsystems. Designers tuning the prompt fragments, faction definitions,
or backend routing get no signal when they break the file.

This module provides:

- A small dict-based schema language (no jsonschema dependency).
- A loader that reads the config file, runs the schema check, and
  emits ``log_degrade`` warnings for every violation. Warnings ALSO
  appear in the F12 overlay because the graceful_degrade → observability
  bridge is installed at boot.
- A boot-time registry of schemas for the configs designers most
  commonly edit (backend, memory, narrative, NPC personalities, faction).

The validator never raises — boot is never blocked. A missing config
file is a single info-level degrade; an invalid one yields per-issue
warning-level degrades that the player or designer can see live.

Schema shape::

    {
        "required_keys": ["name", "version"],
        "type_checks": {
            "version": str,
            "count": (int, float),       # tuple = any of these
        },
        "nested": {
            "config_subsection": {
                "required_keys": [...],
                "type_checks": {...},
            },
        },
    }

Usage::

    from world_system.config.schema_validator import (
        validate_known_configs,
    )
    validate_known_configs(project_root)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from world_system.living_world.infra.graceful_degrade import (
    SEVERITY_INFO,
    SEVERITY_WARNING,
    log_degrade,
)


_TypeSpec = Union[Type, Tuple[Type, ...]]


# ─────────────────────────────────────────────────────────────────────
# Generic validator
# ─────────────────────────────────────────────────────────────────────

def validate_against_schema(
    data: Any,
    schema: Dict[str, Any],
    *,
    config_name: str,
    path: str = "",
) -> List[str]:
    """Validate ``data`` against ``schema``. Returns list of issue strings.

    Mutates nothing. Recursively walks ``nested`` schemas.

    Args:
        data: Loaded JSON value (typically a dict).
        schema: Schema dict — see module docstring.
        config_name: Human-readable name used in issue messages.
        path: Dotted key path (used recursively; callers pass "").

    Returns:
        List of issue strings. Empty list means the schema check passed.
    """
    issues: List[str] = []
    prefix = f"{config_name}{('.' + path) if path else ''}"

    if not isinstance(data, dict):
        issues.append(
            f"{prefix}: expected dict at root, got {type(data).__name__}"
        )
        return issues

    required = schema.get("required_keys", [])
    for key in required:
        if key not in data:
            issues.append(f"{prefix}: required key '{key}' is missing")

    type_checks = schema.get("type_checks", {})
    for key, expected in type_checks.items():
        if key not in data:
            continue                     # already reported above (if required)
        if not isinstance(data[key], expected):
            actual = type(data[key]).__name__
            wanted = _format_type_spec(expected)
            issues.append(
                f"{prefix}: key '{key}' has wrong type — expected {wanted}, got {actual}"
            )

    nested = schema.get("nested", {})
    for key, sub_schema in nested.items():
        if key not in data:
            continue
        sub_path = key if not path else f"{path}.{key}"
        issues.extend(
            validate_against_schema(
                data[key], sub_schema,
                config_name=config_name, path=sub_path,
            )
        )

    return issues


def _format_type_spec(spec: _TypeSpec) -> str:
    if isinstance(spec, tuple):
        return " | ".join(t.__name__ for t in spec)
    return spec.__name__


# ─────────────────────────────────────────────────────────────────────
# Built-in schemas — designer-edit-prone configs only.
# ─────────────────────────────────────────────────────────────────────
# We deliberately do NOT exhaustively cover every key in every config —
# that would freeze the schemas to today's shape and bite during normal
# evolution. Each schema lists the keys whose absence would *silently*
# degrade the runtime to a hardcoded default that the designer cannot
# see was wrong.

SCHEMA_BACKEND_CONFIG: Dict[str, Any] = {
    "required_keys": ["backends", "task_routing", "fallback_chain"],
    "type_checks": {
        "backends": dict,
        "task_routing": dict,
        "fallback_chain": list,
    },
    "nested": {
        "backends": {
            "type_checks": {},
            # backends.* are per-backend dicts with at least 'enabled'.
        },
    },
}

SCHEMA_MEMORY_CONFIG: Dict[str, Any] = {
    "required_keys": [
        "position_sampler", "retention", "event_recorder", "interpreter",
    ],
    "type_checks": {
        "position_sampler": dict,
        "retention": dict,
        "event_recorder": dict,
        "interpreter": dict,
    },
    "nested": {
        "retention": {
            "required_keys": [
                "prune_age_threshold", "timeline_window", "prune_interval",
            ],
            "type_checks": {
                "prune_age_threshold": (int, float),
                "timeline_window": (int, float),
                "prune_interval": (int, float),
            },
        },
        "event_recorder": {
            "required_keys": ["prime_sieve_limit", "chunk_size"],
            "type_checks": {
                "prime_sieve_limit": int,
                "chunk_size": int,
            },
        },
    },
}

SCHEMA_NPC_PERSONALITIES: Dict[str, Any] = {
    "required_keys": ["personality_templates"],
    "type_checks": {"personality_templates": dict},
    # The "default" template is load-bearing: every NPC without an inline
    # personality + tag-mapped template falls back to it. Silent absence
    # = every NPC speaks with whatever the agent's empty-dict default is.
    "nested": {
        "personality_templates": {
            "required_keys": ["default"],
        },
    },
}

SCHEMA_FACTION_DEFINITIONS: Dict[str, Any] = {
    "required_keys": ["factions"],
    "type_checks": {"factions": (dict, list)},
}

SCHEMA_NARRATIVE_CONFIG: Dict[str, Any] = {
    # Designer mostly tunes thresholds here; required_keys reflects the
    # ones that the runtime reads with a hardcoded fallback.
    "type_checks": {},
    # Intentionally permissive — added on first reported drift.
}


_KNOWN_SCHEMAS: Dict[str, Tuple[str, Dict[str, Any]]] = {
    "backend-config.json": ("backend_config", SCHEMA_BACKEND_CONFIG),
    "memory-config.json": ("memory_config", SCHEMA_MEMORY_CONFIG),
    "npc-personalities.json": ("npc_personalities", SCHEMA_NPC_PERSONALITIES),
    "faction-definitions.json": ("faction_definitions", SCHEMA_FACTION_DEFINITIONS),
    "narrative-config.json": ("narrative_config", SCHEMA_NARRATIVE_CONFIG),
}


# ─────────────────────────────────────────────────────────────────────
# Boot-time entry point
# ─────────────────────────────────────────────────────────────────────

def validate_known_configs(
    config_root: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Validate every registered config file, report issues via log_degrade.

    Returns a ``{config_name: [issue_str, ...]}`` map for callers (mostly
    used by tests). Every issue also lands in the graceful_degrade log
    and (via the bridge installed at boot) the F12 overlay.

    Args:
        config_root: Directory containing the JSON files. Defaults to
            ``<game-root>/world_system/config``.
    """
    if config_root is None:
        # Default — relative to this module so test runs and production
        # boots both resolve to the same place.
        module_dir = Path(__file__).resolve().parent
        config_root = module_dir
    else:
        config_root = Path(config_root)

    report: Dict[str, List[str]] = {}

    for filename, (subsystem, schema) in _KNOWN_SCHEMAS.items():
        path = config_root / filename
        if not path.exists():
            log_degrade(
                subsystem=f"schema_validator.{subsystem}",
                operation="load",
                failure_reason=f"file not found: {path}",
                fallback_taken="subsystem will use hardcoded defaults",
                severity=SEVERITY_INFO,
                context={"path": str(path)},
            )
            report[filename] = [f"missing file: {path}"]
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            issue = f"failed to parse: {type(e).__name__}: {e}"
            log_degrade(
                subsystem=f"schema_validator.{subsystem}",
                operation="parse",
                failure_reason=issue,
                fallback_taken="subsystem will use hardcoded defaults",
                severity=SEVERITY_WARNING,
                context={"path": str(path)},
            )
            report[filename] = [issue]
            continue

        issues = validate_against_schema(
            data, schema, config_name=filename,
        )
        report[filename] = issues
        for issue in issues:
            log_degrade(
                subsystem=f"schema_validator.{subsystem}",
                operation="validate",
                failure_reason=issue,
                fallback_taken="key uses hardcoded default at runtime",
                severity=SEVERITY_WARNING,
                context={"path": str(path)},
            )

    return report


__all__ = [
    "validate_against_schema",
    "validate_known_configs",
    "SCHEMA_BACKEND_CONFIG",
    "SCHEMA_MEMORY_CONFIG",
    "SCHEMA_NPC_PERSONALITIES",
    "SCHEMA_FACTION_DEFINITIONS",
    "SCHEMA_NARRATIVE_CONFIG",
]
