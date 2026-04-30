"""ContentRegistry — singleton facade exposed to the rest of the game.

Implements the §7 contract:

- Stage generator-authored content under a plan.
- Atomically commit (flip staged→live, write generated JSON files,
  trigger database reloads) or rollback.
- Expose queries that WNS and the WES bundle assembler use for
  diversity / saturation checks (``counts``, ``list_live``).
- Expose provenance (``lineage``).
- Expose orphan detection (Pass 2 — ``find_orphans``).

The whole facade is a thin wrapper over :class:`RegistryStore`,
:class:`GeneratedFileWriter`, :mod:`database_reloader`, and
:mod:`xref_rules`. Business-rule seams live here; raw SQL is below.

Initialization is two-step:

1. :meth:`get_instance` — cheap, no I/O.
2. :meth:`initialize` — binds the save directory, opens SQLite,
   and becomes usable.

Callers must call ``initialize()`` before any stage/commit/list.
Queries before init return empty results + log a graceful-degrade.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

from world_system.content_registry.balance_validator_stub import (
    check_within_tier_range,
)
from world_system.content_registry.database_reloader import (
    reload_for_tools,
)
from world_system.content_registry.generated_file_writer import (
    GeneratedFileWriter,
)
from world_system.content_registry.registry_store import (
    DB_FILENAME,
    RegistryStore,
    TOOL_TABLE,
)
from world_system.content_registry.xref_rules import (
    VALID_TOOLS,
    extract_header_fields,
    extract_xrefs,
)
from world_system.living_world.infra.graceful_degrade import log_degrade


class ContentRegistry:
    """Singleton facade for staged/live generator-authored content."""

    _instance: Optional["ContentRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._store: Optional[RegistryStore] = None
        self._initialized = False
        self._save_dir: Optional[str] = None
        self._db_path: Optional[str] = None
        self._game_root: Optional[str] = None
        self._instance_lock = threading.RLock()

    # ── Lifecycle ────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "ContentRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ContentRegistry()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton."""
        with cls._lock:
            if cls._instance and cls._instance._store is not None:
                try:
                    cls._instance._store.close()
                except Exception:
                    pass
            cls._instance = None

    def initialize(
        self,
        save_dir: str,
        game_root: Optional[str] = None,
    ) -> None:
        """Bind the registry to a save directory and open SQLite.

        Idempotent: calling twice with the same save_dir is a no-op;
        calling with a different dir closes the previous DB first.
        """
        with self._instance_lock:
            if self._initialized and self._save_dir == save_dir:
                return
            if self._initialized and self._store is not None:
                try:
                    self._store.close()
                except Exception as e:
                    log_degrade(
                        subsystem="content_registry",
                        operation="initialize.close_previous",
                        failure_reason=f"{type(e).__name__}: {e}",
                        fallback_taken="continuing with new db",
                        severity="warning",
                    )

            os.makedirs(save_dir, exist_ok=True)
            self._save_dir = save_dir
            self._db_path = os.path.join(save_dir, DB_FILENAME)
            self._game_root = game_root
            self._store = RegistryStore(db_path=self._db_path)
            self._initialized = True

    def close(self) -> None:
        with self._instance_lock:
            if self._store is not None:
                self._store.close()
            self._store = None
            self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def db_path(self) -> Optional[str]:
        return self._db_path

    @property
    def save_dir(self) -> Optional[str]:
        return self._save_dir

    # ── Staging ──────────────────────────────────────────────────────

    def stage_content(
        self,
        tool_name: str,
        content_json: Dict[str, Any],
        plan_id: str,
        source_bundle_id: str,
    ) -> str:
        """Stage a generator JSON payload under ``plan_id``.

        Extracts header fields + cross-refs automatically via
        :mod:`xref_rules`. Returns the staged ``content_id``.

        Raises ``ValueError`` if the content is unusable (unknown
        tool, missing id). Schema/balance concerns are upstream.
        """
        self._require_store()
        if tool_name not in VALID_TOOLS:
            raise ValueError(
                f"stage_content: unknown tool_name '{tool_name}'"
            )

        headers = extract_header_fields(content_json, tool_name)
        content_id = headers["content_id"]
        if not content_id:
            raise ValueError(
                f"stage_content: could not determine content_id for "
                f"tool '{tool_name}' payload (no id field found)"
            )

        payload_json = RegistryStore.serialize_payload(content_json)
        now = time.time()

        self._store.insert_staged_row(  # type: ignore[union-attr]
            tool_name=tool_name,
            content_id=content_id,
            display_name=headers["display_name"],
            tier=int(headers["tier"] or 0),
            biome=headers["biome"],
            faction_id=headers["faction_id"],
            plan_id=plan_id,
            source_bundle_id=source_bundle_id,
            created_at=now,
            payload_json=payload_json,
        )

        xrefs = extract_xrefs(tool_name, content_json)
        if xrefs:
            self._store.insert_xrefs_bulk(xrefs, plan_id)  # type: ignore[union-attr]

        return content_id

    def stage_xref(
        self,
        src_type: str,
        src_id: str,
        ref_type: str,
        ref_id: str,
        relationship: str,
        plan_id: Optional[str] = None,
    ) -> None:
        """Insert a cross-reference directly. Usually the extractor
        handles this — call this only for cross-refs the extractor
        can't see (e.g., tool-authored explicit relationships)."""
        self._require_store()
        self._store.insert_xref(  # type: ignore[union-attr]
            src_type=src_type,
            src_id=src_id,
            ref_type=ref_type,
            ref_id=ref_id,
            relationship=relationship,
            plan_id=plan_id or "",
        )

    # ── Commit / rollback ────────────────────────────────────────────

    def commit(self, plan_id: str) -> Dict[str, Any]:
        """Atomically flip staged→live and write generated JSON files.

        Order of operations (matches §7.4 'both' resolution):

        1. Collect all staged rows for this plan.
        2. Write generated JSON files (one per tool per commit).
        3. Flip registry rows staged=0.
        4. Trigger database reloads.

        On failure in step 2: no flip, registry remains staged.
        On failure in step 3: file rollback, registry remains staged.
        On failure in step 4: logged but not rolled back — content is
        live in files and registry, it just won't appear until game
        restart.

        Returns a result dict with ``plan_id``, ``files`` map, and
        per-tool commit counts.
        """
        self._require_store()

        rows_by_tool = self._staged_rows_for_plan(plan_id)
        if not any(rows_by_tool.values()):
            log_degrade(
                subsystem="content_registry",
                operation="commit",
                failure_reason=f"no staged rows for plan_id='{plan_id}'",
                fallback_taken="commit is a no-op",
                severity="info",
                context={"plan_id": plan_id},
            )
            return {
                "plan_id": plan_id,
                "files": {},
                "counts": {t: 0 for t in VALID_TOOLS},
                "reload_results": {},
            }

        # Step 2: write files. If this raises, nothing else runs.
        writer = GeneratedFileWriter(game_root=self._game_root)
        try:
            files = writer.write_commit_batch(rows_by_tool, plan_id)
        except Exception as e:
            log_degrade(
                subsystem="content_registry",
                operation="commit.write_files",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="rolling back any files written; "
                               "staging untouched",
                severity="error",
                context={"plan_id": plan_id},
            )
            writer.rollback()
            raise

        # Step 3: flip staged rows. On failure we roll back the files.
        try:
            counts = self._store.flip_staged_to_live(plan_id)  # type: ignore[union-attr]
        except Exception as e:
            log_degrade(
                subsystem="content_registry",
                operation="commit.flip_staged",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="rolling back generated files; "
                               "registry rows still staged",
                severity="error",
                context={"plan_id": plan_id},
            )
            writer.rollback()
            raise

        # Step 4: best-effort reload.
        tools_with_rows = [t for t, rs in rows_by_tool.items() if rs]
        try:
            reload_results = reload_for_tools(tools_with_rows)
        except Exception as e:
            log_degrade(
                subsystem="content_registry",
                operation="commit.reload_databases",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="content is live; databases may need "
                               "restart to surface it",
                severity="warning",
                context={"plan_id": plan_id},
            )
            reload_results = {}

        # Best-effort live observability. Surfaces "content X committed,
        # databases reloaded" to the in-game overlay and prompt studio
        # without the caller having to subscribe to an event bus.
        try:
            from world_system.wes.observability_runtime import (
                EVT_DB_RELOADED,
                EVT_DB_RELOAD_FAILED,
                EVT_REGISTRY_COMMITTED,
                obs_record,
            )
            row_summary = {t: len(rs) for t, rs in rows_by_tool.items() if rs}
            obs_record(
                EVT_REGISTRY_COMMITTED,
                "ContentRegistry committed",
                plan_id=plan_id,
                tools=",".join(sorted(row_summary)),
                rows=sum(row_summary.values()),
            )
            for cls_name, ok in (reload_results or {}).items():
                obs_record(
                    EVT_DB_RELOADED if ok else EVT_DB_RELOAD_FAILED,
                    f"{cls_name} reload {'ok' if ok else 'FAILED'}",
                    db=cls_name,
                    ok=bool(ok),
                )
        except Exception:
            pass  # observability failures must not break commit path

        return {
            "plan_id": plan_id,
            "files": files,
            "counts": counts,
            "reload_results": reload_results,
        }

    def rollback(self, plan_id: str) -> Dict[str, int]:
        """Delete every staged row for this plan. Atomic — either all
        staged rows are gone or none are (one SQLite transaction per
        batch handled inside the store)."""
        self._require_store()
        try:
            return self._store.delete_staged_rows(plan_id)  # type: ignore[union-attr]
        except Exception as e:
            log_degrade(
                subsystem="content_registry",
                operation="rollback",
                failure_reason=f"{type(e).__name__}: {e}",
                fallback_taken="rollback may be partial",
                severity="error",
                context={"plan_id": plan_id},
            )
            raise

    # ── Queries ──────────────────────────────────────────────────────

    def list_live(
        self,
        tool_name: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """All live (staged=0) rows for a tool type, optionally filtered."""
        if not self._require_store(soft=True):
            return []
        return self._store.list_rows(  # type: ignore[union-attr]
            tool_name=tool_name,
            staged=0,
            filters=filters,
        )

    def list_staged_by_plan(self, plan_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Every staged row across every tool, grouped by tool_name."""
        if not self._require_store(soft=True):
            return {t: [] for t in VALID_TOOLS}
        return self._staged_rows_for_plan(plan_id)

    def find_orphans(
        self, plan_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Pass 2 orphan detection.

        Walks ``content_xref``. For every row, checks whether the
        referenced id exists in ``reg_<ref_type>`` (live OR staged,
        since staged-in-this-plan is a valid resolution).

        If ``plan_id`` is given, limits the scan to that plan's xrefs;
        otherwise scans the whole table.

        Each orphan is returned as a dict:
        ``{src_type, src_id, ref_type, ref_id, relationship, plan_id}``.
        """
        if not self._require_store(soft=True):
            return []

        if plan_id is None:
            xrefs = self._store.all_xrefs()  # type: ignore[union-attr]
        else:
            xrefs = self._store.xrefs_for_plan(plan_id)  # type: ignore[union-attr]

        orphans: List[Dict[str, Any]] = []
        for row in xrefs:
            ref_type = row.get("ref_type") or ""
            ref_id = row.get("ref_id") or ""
            if ref_type not in VALID_TOOLS or not ref_id:
                # Non-registry refs (tags/biomes) aren't orphan
                # candidates here.
                continue
            if self.exists(ref_type, ref_id, include_staged=True):
                continue
            orphans.append(
                {
                    "src_type": row.get("src_type"),
                    "src_id": row.get("src_id"),
                    "ref_type": ref_type,
                    "ref_id": ref_id,
                    "relationship": row.get("relationship"),
                    "plan_id": row.get("plan_id"),
                }
            )
        return orphans

    def counts(
        self,
        tool_name: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """Live-row counts per tool. Used by the bundle assembler
        for diversity / saturation checks.

        If ``tool_name`` is given, returns ``{tool_name: count}``.
        If None, returns counts for every tool.
        """
        if not self._require_store(soft=True):
            return {t: 0 for t in VALID_TOOLS}

        if tool_name is not None:
            if tool_name not in VALID_TOOLS:
                return {tool_name: 0}
            return {
                tool_name: self._store.count_rows(  # type: ignore[union-attr]
                    tool_name=tool_name,
                    staged=0,
                    filters=filters,
                )
            }

        result: Dict[str, int] = {}
        for t in VALID_TOOLS:
            result[t] = self._store.count_rows(  # type: ignore[union-attr]
                tool_name=t,
                staged=0,
                filters=filters,
            )
        return result

    def exists(
        self, tool_name: str, content_id: str, include_staged: bool = False
    ) -> bool:
        if not self._require_store(soft=True):
            return False
        if tool_name not in VALID_TOOLS:
            return False
        row = self._store.get_row(  # type: ignore[union-attr]
            tool_name=tool_name,
            content_id=content_id,
            include_staged=include_staged,
        )
        return row is not None

    # ── Lineage ──────────────────────────────────────────────────────

    def lineage(self, content_id: str) -> Dict[str, Any]:
        """Walk provenance: content_id → plan_id → source_bundle_id.

        Returns a dict with the row's tool_name, plan_id, and
        source_bundle_id, plus ``staged`` and ``created_at`` for
        completeness. Returns an empty dict if the id is unknown.
        """
        if not self._require_store(soft=True):
            return {}
        row = self._store.find_row_anywhere(content_id)  # type: ignore[union-attr]
        if row is None:
            return {}
        return {
            "content_id": row.get("content_id"),
            "tool_name": row.get("tool_name"),
            "plan_id": row.get("plan_id"),
            "source_bundle_id": row.get("source_bundle_id"),
            "staged": bool(row.get("staged")),
            "created_at": row.get("created_at"),
            "display_name": row.get("display_name"),
            "tier": row.get("tier"),
        }

    # ── Balance stub passthrough ─────────────────────────────────────

    @staticmethod
    def balance_check(
        field_value: Any, tier: int, field_name: str
    ) -> Optional[str]:
        """Convenience passthrough to
        :func:`balance_validator_stub.check_within_tier_range` so
        WES tool code can call ``ContentRegistry.balance_check(...)``
        without importing the stub module directly."""
        return check_within_tier_range(field_value, tier, field_name)

    # ── Stats ────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        """Summary stats — useful for dev overlays and tests."""
        if not self._initialized or self._store is None:
            return {
                "initialized": False,
                "live_counts": {t: 0 for t in VALID_TOOLS},
                "staged_rows": 0,
                "xref_rows": 0,
            }
        live_counts = {
            t: self._store.count_rows(tool_name=t, staged=0)
            for t in VALID_TOOLS
        }
        staged_total = sum(
            self._store.count_rows(tool_name=t, staged=1)
            for t in VALID_TOOLS
        )
        # Count all xrefs as single query.
        xref_count = len(self._store.all_xrefs())
        return {
            "initialized": True,
            "db_path": self._db_path,
            "live_counts": live_counts,
            "staged_rows": staged_total,
            "xref_rows": xref_count,
        }

    # ── Internals ────────────────────────────────────────────────────

    def _staged_rows_for_plan(
        self, plan_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for tool_name in TOOL_TABLE.keys():
            out[tool_name] = self._store.list_rows(  # type: ignore[union-attr]
                tool_name=tool_name,
                staged=1,
                plan_id=plan_id,
            )
        return out

    def _require_store(self, soft: bool = False) -> bool:
        """Assert that the registry is initialized.

        Hard mode (``soft=False``): raises ``RuntimeError``.
        Soft mode (``soft=True``): returns False + logs.
        """
        if self._initialized and self._store is not None:
            return True
        if soft:
            log_degrade(
                subsystem="content_registry",
                operation="query",
                failure_reason="ContentRegistry not initialized",
                fallback_taken="returning empty result",
                severity="warning",
            )
            return False
        raise RuntimeError(
            "ContentRegistry not initialized. Call initialize(save_dir) "
            "before staging/committing/rolling back."
        )


def get_content_registry() -> ContentRegistry:
    """Module-level accessor following project singleton pattern."""
    return ContentRegistry.get_instance()
