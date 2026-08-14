# Archive — 2026‑08 Documentation Consolidation

These docs were **harvested into the single authoritative
[`Development-Plan/GAME_SYSTEMS_BRIEF.md`](../../Development-Plan/GAME_SYSTEMS_BRIEF.md)** (and its
companion deck `GAME_SYSTEMS_BRIEF.html`) and then archived. They are retained for history only —
the brief is now the source of truth. Nothing here is deleted; every doc's durable content lives on
in the brief section noted below.

**Why:** `Development-Plan/` had grown to 32 top‑level docs + a 12‑file `feature-traces/` subdir, much
of it point‑in‑time (backward‑design traces, audits, session logs, an execution plan) competing with
the canonical spec for authority. The consolidation collapsed the spent material into one verified,
code‑anchored brief.

## Migration map

| Archived doc | Was | Content migrated to |
|---|---|---|
| `feature-traces/00-consolidation.md` + `01-11` (12 files) | 2026‑04 backward‑design trace pass (COMPLETE) | Brief §9–§12 (WMS/WNS/WES/factions), §16 gap register |
| `TOOL_CONTRACT_AUDIT.md` | Per‑tool WES contract audit | Brief §11 (WES) + §16; live guard = `tools/prompt_orchestration_dashboard.py` |
| `ORCHESTRATION_GAP_FIX_LOG.md` | C1‑C3/M1‑M2/Mn1‑Mn2 fix log (all resolved) | Brief §10, §15, §16 ("Resolved this cycle"); dashboard self‑checks the fixes |
| `CONSOLIDATION_AND_PRESENTATION_PLAN.md` | The plan for this consolidation (executed) | Superseded by the delivered brief + deck |
| `WORLD_MEMORY_POINTER.md` | Pointer stub → `world_system/docs/` | Canonical WMS docs remain in `Game-1-modular/world_system/docs/` |
| `controls-agent-render-ui.md` | One‑off controls/render note | Brief §2 (core loop) / §5 (combat) where durable |

## Still authoritative (NOT archived)

- **Canonical spec:** `Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`, `SYSTEMS_CATALOG.md`,
  `REPOSITORY_MAP.md`, `WMS_WNS_LAYER_CORRESPONDENCE.md`, `Game-1-modular/docs/GAME_MECHANICS_V6.md`,
  `Game-1-modular/world_system/docs/*`.
- **Roadmap (forward‑looking):** `OVERVIEW.md`, `PART_1/2/3`, `SHARED_INFRASTRUCTURE.md`.
- **Living TODO ledgers:** `DESIGNER_LEDGER.md`, `PLACEHOLDER_LEDGER.md`, `PLACEHOLDER_FURNISHING_WORKSHEET.md`.
- **Evidence trail:** `Development-Plan/repo-audit-2026-06-10/` (kept — cited by `REPOSITORY_MAP.md`).

See also the prior consolidation: `archive/2026-04-24-doc-consolidation/`.
