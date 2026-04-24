"""Generated JSON file writer — commit-time file emission.

Per §7.4 of the working doc and PLACEHOLDER_LEDGER §17, the Content
Registry commits BOTH the SQLite rows AND a set of generated JSON
files colocated with the sacred game-content files. The sacred files
are never mutated; generated files are new siblings.

Filename scheme (placeholder per PLACEHOLDER_LEDGER §17):

- ``items.JSON/items-materials-generated-<ts>.JSON``
- ``Definitions.JSON/hostiles-generated-<ts>.JSON``
- ``Definitions.JSON/Resource-node-generated-<ts>.JSON``
- ``Skills/skills-generated-<ts>.JSON``
- ``progression/titles-generated-<ts>.JSON``

Timestamps are ISO 8601 with ``:`` and ``.`` replaced for filename
safety.

The writer accepts a list of content rows per tool (the exact row
shape returned by ``RegistryStore.list_rows``) and writes ONE file
per tool per commit, wrapping the payloads under the top-level key
used by the matching sacred file (``materials``, ``enemies``, etc.
— see :data:`xref_rules.SACRED_TOP_LEVEL_KEY`).

The writer uses a temp-file + atomic rename so a partial write can
be cleaned up by the caller's rollback path.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from world_system.content_registry.registry_store import RegistryStore
from world_system.content_registry.xref_rules import (
    SACRED_OUTPUT_PREFIX,
    SACRED_OUTPUT_SUBDIR,
    SACRED_TOP_LEVEL_KEY,
    VALID_TOOLS,
)
from world_system.living_world.infra.graceful_degrade import log_degrade


def _safe_timestamp() -> str:
    """Return an ISO-ish timestamp safe to drop into a filename.

    TODO(PLACEHOLDER_LEDGER §17): designer may prefer sequential
    numbers or a different tagging scheme.
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace(":", "-")
        .replace("+", "_")
    )


def _resolve_game_root(explicit_root: Optional[str]) -> str:
    """Resolve the Game-1-modular root directory.

    Caller-supplied root wins. Otherwise we try ``core.paths`` (the
    same resolver the rest of the codebase uses) and fall back to a
    path walk from this module.
    """
    if explicit_root:
        return str(explicit_root)
    try:
        from core.paths import get_resource_path  # type: ignore

        return str(get_resource_path("."))
    except Exception:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        # content_registry/ -> world_system/ -> Game-1-modular/
        return os.path.abspath(os.path.join(this_dir, "..", ".."))


def _build_file_contents(
    tool_name: str, rows: List[Dict[str, Any]], plan_id: str
) -> Dict[str, Any]:
    """Wrap deserialized payloads under the sacred top-level key.

    Adds a ``metadata`` block with the plan_id + timestamp so the
    designer can match generated files back to the registry.
    """
    top_key = SACRED_TOP_LEVEL_KEY[tool_name]
    payloads: List[Dict[str, Any]] = []
    for row in rows:
        payload = RegistryStore.deserialize_payload(
            row.get("payload_json") or ""
        )
        if payload:
            payloads.append(payload)
    return {
        "metadata": {
            "generated": True,
            "plan_id": plan_id,
            "tool": tool_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(payloads),
            "note": "Generator-authored sibling of the sacred file. "
                    "Do not mutate by hand. See "
                    "Development-Plan/WORLD_SYSTEM_WORKING_DOC.md §7.",
        },
        top_key: payloads,
    }


class GeneratedFileWriter:
    """Writes generated JSON files for a commit, atomically per tool.

    The caller hands in ``{tool_name: [row, row, ...]}`` and gets
    back ``{tool_name: path}`` for every file actually written. A
    tool with no rows is silently skipped.

    On failure mid-batch, :meth:`rollback` cleans up any files this
    writer created — callers do that when the registry commit itself
    fails and needs to be undone.
    """

    def __init__(
        self,
        game_root: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self._root = _resolve_game_root(game_root)
        self._timestamp = timestamp or _safe_timestamp()
        self._written_paths: List[str] = []

    @property
    def written_paths(self) -> List[str]:
        return list(self._written_paths)

    @property
    def timestamp(self) -> str:
        return self._timestamp

    def write_commit_batch(
        self,
        rows_by_tool: Dict[str, List[Dict[str, Any]]],
        plan_id: str,
    ) -> Dict[str, str]:
        """Write one file per tool that has rows. Returns
        ``{tool_name: absolute_path}``.

        NEVER touches sacred files — the generated file always has
        ``-generated-<ts>`` in the name and sits alongside the
        sacred file in the same directory.
        """
        results: Dict[str, str] = {}
        for tool_name, rows in rows_by_tool.items():
            if tool_name not in VALID_TOOLS:
                continue
            if not rows:
                continue
            try:
                path = self._write_one_tool_file(tool_name, rows, plan_id)
            except Exception as e:
                log_degrade(
                    subsystem="content_registry",
                    operation="write_generated_file",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="no file written; commit should abort "
                                   "and rollback registry flip",
                    severity="error",
                    context={
                        "tool_name": tool_name,
                        "plan_id": plan_id,
                        "row_count": len(rows),
                    },
                )
                # Surface the error — caller must rollback. Raising
                # is the callee's contract with the caller: atomic
                # commit depends on it.
                raise
            if path:
                results[tool_name] = path
        return results

    def _write_one_tool_file(
        self, tool_name: str, rows: List[Dict[str, Any]], plan_id: str
    ) -> str:
        subdir = SACRED_OUTPUT_SUBDIR[tool_name]
        prefix = SACRED_OUTPUT_PREFIX[tool_name]

        # Resolve target directory and ensure it exists. We never
        # create missing sacred directories — if they don't exist
        # something is seriously wrong — but we DO create the folder
        # if, for example, the codebase is being tested in isolation.
        target_dir = os.path.join(self._root, subdir)
        os.makedirs(target_dir, exist_ok=True)

        filename = f"{prefix}-generated-{self._timestamp}.JSON"
        final_path = os.path.join(target_dir, filename)
        tmp_path = final_path + ".tmp"

        # Hard stop: if a sacred file with this exact name somehow
        # already exists (shouldn't happen — sacred files never carry
        # "-generated-" in their name), refuse to overwrite it. Raise
        # so the caller rollback fires.
        if os.path.exists(final_path):
            raise FileExistsError(
                f"Refusing to overwrite existing generated file "
                f"{final_path}. Caller must pick a new timestamp."
            )

        contents = _build_file_contents(tool_name, rows, plan_id)

        # Atomic write: write to .tmp, fsync, rename. Same idiom
        # as save_manager's save flow.
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(contents, f, indent=2, sort_keys=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (OSError, AttributeError):
                # fsync unsupported (e.g. Windows non-disk file);
                # the rename below is still atomic on same filesystem.
                pass
        os.replace(tmp_path, final_path)
        self._written_paths.append(final_path)
        return final_path

    def rollback(self) -> int:
        """Delete every file this writer created. Safe to call
        multiple times. Returns the number of files removed.

        Used when the commit's registry flip or reload phase fails
        after files were already written. Pair with
        :meth:`ContentRegistry.rollback` for a full undo.
        """
        removed = 0
        for path in list(self._written_paths):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
            except OSError as e:
                log_degrade(
                    subsystem="content_registry",
                    operation="rollback_generated_file",
                    failure_reason=f"{type(e).__name__}: {e}",
                    fallback_taken="leaving file on disk",
                    severity="warning",
                    context={"path": path},
                )
        self._written_paths.clear()
        return removed
