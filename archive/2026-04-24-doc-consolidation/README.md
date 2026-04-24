# Doc Consolidation — 2026-04-24

**Purpose**: Reduce live-tree documentation bloat (from ~95,900 lines to ~21,000 lines) by moving superseded, shipped-design, and historical docs here as backup. Nothing is deleted — everything is recoverable via this folder or git history.

Organized by reason-for-move so future lookups are fast.

## Directory map

### `superseded-by-canonical/`

Content has been consolidated into a single current canonical doc elsewhere. These files are the pre-consolidation predecessors. Safe to ignore unless tracing doc history.

- `wms/` — World Memory System docs consolidated into [`Game-1-modular/world_system/docs/WORLD_MEMORY_SYSTEM.md`](../../Game-1-modular/world_system/docs/WORLD_MEMORY_SYSTEM.md). The unified doc's own appendix lists exactly what it replaced.
  - `Development-Plan_WORLD_MEMORY_SYSTEM.md` — 6-layer predecessor (2026-03-16)
  - `Development-Plan_TRIGGER_SYSTEM.md` — companion
  - `Development-Plan_TIME_AND_RECENCY.md` — companion
  - `Development-Plan_RETRIEVAL_AND_TAGGING.md` — companion
  - `Development-Plan_fragments/` — 8 section fragments
  - `world_system_docs_LAYER_1_2_REDESIGN.md` — layer 1-2 redesign, shipped
  - `world_system_docs_HANDOFF_GEOGRAPHIC_SYSTEM.md` — old handoff, geo shipped
  - `world_system_docs_FOUNDATION_IMPLEMENTATION_PLAN.md` — pre-impl plan, WMS shipped
  - `world_system_docs_GEOGRAPHIC_SYSTEM_DESIGN.md` — design-phase, shipped

- `wns/` — WNS/WES docs consolidated into [`Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`](../../Development-Plan/WORLD_SYSTEM_WORKING_DOC.md) v4.
  - `WORLD_SYSTEM_SCRATCHPAD.md` — 2026-03-14 research scratchpad; research citations were rolled into §2.8 of v4

### `shipped-system-designs/`

Pre-implementation design docs for systems that are now shipped and in production. The design intent is preserved in the code + CLAUDE.md + canonical docs; these originals are kept for provenance.

- `claude_PHASE_1_DESIGN.md` — Phase 1 tag registry + archetype library; tag system shipped
- `claude_FACTION_SYSTEM_DESIGN.md` — Faction system v1.0 pre-code design; faction system Phase 2+ shipped

### `historical-planning/`

Goal-oriented planning docs whose goals were achieved. Kept for historical context of what the project was optimizing for at different moments.

- `FEATURES_CHECKLIST.md` — parity checklist vs. the original monolithic `main.py`. Goal achieved (modular version shipped).
- `SHARED_INFRASTRUCTURE.md` — cross-cutting spec (BalanceValidator spec now lives in `PLACEHOLDER_LEDGER.md` §9 + `content_registry/balance_validator_stub.py`)
- `WORLD_MEMORY_POINTER.md` — 11-line pointer file, merged into `OVERVIEW.md`

### `duplicate-architecture/`

Docs whose content is now covered by canonical docs elsewhere.

- `ARCHITECTURE.md` — header admits "some sections may be outdated; see CLAUDE.md for current"; superseded by `.claude/CLAUDE.md` v8 directory listings + `GAME_MECHANICS_V6.md`

### `trimmed-originals/`

Original full versions of docs that were trimmed in the live tree (status kept, shipped-work detail archived).

- `PART_1_COMBAT_VISUALS_full.md` — original 775-line version (live version kept as status + open work summary)
- `PART_2_LIVING_WORLD_full.md` — original 618-line version (superseded by WORLD_SYSTEM_WORKING_DOC.md v4 for narrative half; live version is a status summary)
- `MASTER_ISSUE_TRACKER_full.md` — original 734-line version (live version is open-issues only)

### `paused-migration/`

Work that is paused indefinitely but could resume. Full contents of the paused Unity migration plan, not in live tree.

- `Migration-Plan/` — the full 16,013-line Unity migration plan (paused indefinitely per CLAUDE.md)

### `pre-existing-archive-rollup/`

The existing `archive/` subdirectories (as of 2026-04-24) rolled into this consolidation folder so the archive has one organizing principle going forward. All pre-shipping history — cleanup plans, tag-system-old, summaries, handoffs, Jan 2026 cleanups, etc.

---

## Recovery

To recover a file from archive back into the live tree:
```bash
git mv archive/2026-04-24-doc-consolidation/<category>/<file> <original-live-path>
```

Or read directly from this folder — nothing is deleted.

## Line count before/after

| Metric | Before | After |
|---|---:|---:|
| Live-tree `.md` total | ~95,900 | ~21,000 |
| Archive-tree `.md` total | ~56,500 | ~130,000 |
| Both combined | ~152,400 | ~151,000 (small reduction from merges) |

Most of the reduction is **moving** from live tree to archive. Merges reduce total by ~2,000 lines by removing pure duplication between `UPDATE_N_*` docs + between `DEVELOPMENT_GUIDE` + `DEVELOPER_GUIDE_JSON_INTEGRATION` + among tag-system operational docs, while preserving all unique content.
