"""Database reload dispatcher — commit-time notification.

After the Content Registry writes generated JSON files to the sacred
subdirectories, the runtime databases (``MaterialDatabase``,
``EquipmentDatabase`` / ``EnemyDatabase``, ``SkillDatabase``,
``TitleDatabase``, ``ResourceNodeDatabase``) need to pick up the new
content. This module is the glue.

Per PLACEHOLDER_LEDGER §10, the current reload trigger is
"call ``_reload()`` / ``reload()`` on each database singleton if it
exists; log via graceful_degrade if it doesn't." Future designer work
may swap this for a GameEventBus notification pattern.

**Design rules**:

- The dispatcher never raises — a missing ``reload`` method degrades
  gracefully with a structured log entry.
- Database imports are deferred to call time so the Content Registry
  can initialize in contexts where the full game engine isn't loaded
  (tests, headless tools).
- Reload targets are keyed by tool_name so a commit only reloads
  databases whose tool produced content.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from world_system.living_world.infra.graceful_degrade import log_degrade


# (module_path, class_name, reload_method_candidates). Each tool can
# resolve 0..N databases. The method candidates are ordered — the
# dispatcher calls the first one that exists.
#
# TODO(PLACEHOLDER_LEDGER §10): designer may want a GameEventBus
# notification here instead of direct method calls. Replace this
# table + _call_reload with a bus-publish once the designer commits.
_RELOAD_TARGETS: Dict[str, List[Tuple[str, str, Tuple[str, ...]]]] = {
    "materials": [
        (
            "data.databases.material_db",
            "MaterialDatabase",
            ("reload", "_reload", "reload_all"),
        ),
    ],
    "hostiles": [
        # EnemyDatabase lives inside Combat/enemy.py. It is loaded
        # elsewhere via Combat.combat_data_loader; we defer to
        # whatever reload path it exposes, if any.
        (
            "Combat.enemy",
            "EnemyDatabase",
            ("reload", "_reload", "reload_all"),
        ),
    ],
    "nodes": [
        (
            "data.databases.resource_node_db",
            "ResourceNodeDatabase",
            ("reload", "_reload", "reload_all"),
        ),
    ],
    "skills": [
        (
            "data.databases.skill_db",
            "SkillDatabase",
            ("reload", "_reload", "reload_all"),
        ),
    ],
    "titles": [
        (
            "data.databases.title_db",
            "TitleDatabase",
            ("reload", "_reload", "reload_all"),
        ),
    ],
    "npcs": [
        # NPCDatabase loads BOTH npcs and quests (single SQL-less
        # database holding two cache dicts), so reloading either tool
        # name routes to the same target. NPCDatabase.reload() picks
        # up `progression/npcs-generated-*.JSON` siblings.
        (
            "data.databases.npc_db",
            "NPCDatabase",
            ("reload", "_reload"),
        ),
    ],
    "quests": [
        (
            "data.databases.npc_db",
            "NPCDatabase",
            ("reload", "_reload"),
        ),
    ],
    # NOTE(2026-04-27): "chunks" deliberately has no reload target yet.
    # WES-generated chunk templates land in
    # ``Definitions.JSON/chunks-generated-*.JSON`` but the biome
    # generator + chunk dispatcher (systems/biome_generator.py,
    # systems/chunk.py) don't yet consult a chunk-template database
    # keyed by region — they use a code-locked geo→ChunkType dict.
    # ChunkType is already a namespace class so new strings won't
    # crash, but they also won't spawn until that runtime integration
    # lands. Bridge work is registered (no-targets path), and the
    # reloader's existing graceful-degrade log surfaces the gap.
}


def _resolve_instance(
    module_path: str, class_name: str
) -> Optional[Any]:
    """Import ``module_path`` and call ``ClassName.get_instance()``.

    Returns ``None`` on any failure. All failures are logged.
    """
    try:
        module = importlib.import_module(module_path)
    except Exception as e:
        log_degrade(
            subsystem="content_registry",
            operation="database_reloader.import",
            failure_reason=f"{type(e).__name__}: {e}",
            fallback_taken="skipping this database (module not loadable)",
            severity="warning",
            context={"module_path": module_path, "class_name": class_name},
        )
        return None

    cls = getattr(module, class_name, None)
    if cls is None:
        log_degrade(
            subsystem="content_registry",
            operation="database_reloader.getattr",
            failure_reason=f"{class_name} not found in {module_path}",
            fallback_taken="skipping this database",
            severity="warning",
            context={"module_path": module_path, "class_name": class_name},
        )
        return None

    get_instance = getattr(cls, "get_instance", None)
    if not callable(get_instance):
        log_degrade(
            subsystem="content_registry",
            operation="database_reloader.get_instance",
            failure_reason=f"{class_name}.get_instance is not callable",
            fallback_taken="skipping this database",
            severity="warning",
            context={"class_name": class_name},
        )
        return None

    try:
        return get_instance()
    except Exception as e:
        log_degrade(
            subsystem="content_registry",
            operation="database_reloader.get_instance_call",
            failure_reason=f"{type(e).__name__}: {e}",
            fallback_taken="skipping this database",
            severity="warning",
            context={"class_name": class_name},
        )
        return None


def _call_reload(
    instance: Any,
    class_name: str,
    method_candidates: Iterable[str],
) -> bool:
    """Call the first reload method on ``instance`` that exists.

    Returns True if a method was found and called without raising.
    Otherwise logs and returns False.

    TODO(PLACEHOLDER_LEDGER §10): databases may not implement
    reload today. The designer will add reload() methods as needed;
    this dispatcher logs a warning for each missing method so the
    designer has a visible TODO surface.
    """
    for method_name in method_candidates:
        method = getattr(instance, method_name, None)
        if callable(method):
            try:
                method()
                return True
            except Exception as e:
                log_degrade(
                    subsystem="content_registry",
                    operation=f"database_reloader.{method_name}",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="database not reloaded; "
                                   "new content may not appear until "
                                   "next game restart",
                    severity="warning",
                    context={"class_name": class_name},
                )
                return False

    log_degrade(
        subsystem="content_registry",
        operation="database_reloader.no_reload_method",
        failure_reason=(
            f"{class_name} has none of: "
            f"{', '.join(method_candidates)}"
        ),
        fallback_taken="database not reloaded; designer TODO to add "
                       "a reload() method (PLACEHOLDER_LEDGER §10)",
        severity="warning",
        context={"class_name": class_name},
    )
    return False


def reload_for_tools(tool_names: Iterable[str]) -> Dict[str, bool]:
    """Reload every database registered for the given tool names.

    Returns a dict ``{class_name: reloaded_successfully}`` for
    observability. Unknown tool names are ignored (logged).
    """
    results: Dict[str, bool] = {}
    for tool_name in tool_names:
        targets = _RELOAD_TARGETS.get(tool_name)
        if not targets:
            log_degrade(
                subsystem="content_registry",
                operation="database_reloader.unknown_tool",
                failure_reason=f"no reload targets registered for "
                               f"tool '{tool_name}'",
                fallback_taken="nothing reloaded for this tool",
                severity="info",
                context={"tool_name": tool_name},
            )
            continue
        for (module_path, class_name, method_candidates) in targets:
            instance = _resolve_instance(module_path, class_name)
            if instance is None:
                results[class_name] = False
                continue
            results[class_name] = _call_reload(
                instance, class_name, method_candidates
            )
    return results


def register_reload_target(
    tool_name: str,
    module_path: str,
    class_name: str,
    method_candidates: Tuple[str, ...] = ("reload", "_reload"),
) -> None:
    """Register an additional reload target. Exposed so tests (and
    future systems like ``EquipmentDatabase``) can plug in without
    editing this file."""
    _RELOAD_TARGETS.setdefault(tool_name, []).append(
        (module_path, class_name, method_candidates)
    )


def registered_targets() -> Dict[str, List[Tuple[str, str, Tuple[str, ...]]]]:
    """Inspection helper — used by tests. Returns a deep-ish copy."""
    return {k: list(v) for k, v in _RELOAD_TARGETS.items()}
