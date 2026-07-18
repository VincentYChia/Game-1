# Subsystem porting contracts — index

Eleven inventory documents, one per subsystem, written 2026-07-17 by parallel
exhaustive-read agents. Each is the **porting contract** for its subsystem:
file dispositions, public surface, dependency edges, engine coupling,
constants (file:line), event topics, content JSON, save state, 3D notes,
Godot mapping, complexity and risks.

| Doc | Subsystem | Focus |
|---|---|---|
| [01-core-engine.md](01-core-engine.md) | `core/game_engine.py` (12,035 lines) | Decomposition map: responsibility clusters → Godot scenes/autoloads; per-frame update-order contract |
| [02-core-logic.md](02-core-logic.md) | `core/` minus the engine | Tag pipeline, effect executor dispatch, both calculators, interactive crafting |
| [03-data-layer.md](03-data-layer.md) | `data/` models + 16 DB singletons | Load paths, Update-N overlay, normalizations, generated-content merge |
| [04-entities.md](04-entities.md) | `entities/` character + components | Stat/leveling semantics, inventory/equipment math, status effects |
| [05-systems.md](05-systems.md) | `systems/` 21 managers | World gen determinism, save manager, sidecar-bound LLM/ML call interfaces |
| [06-combat.md](06-combat.md) | `Combat/` 11 files | Action-path damage pipeline, hitboxes/projectiles as 3D-redesign input |
| [07-crafting.md](07-crafting.md) | `Crafting-subdisciplines/` | Logic-vs-draw split per minigame; shared-method collapse plan |
| [08-presentation.md](08-presentation.md) | `rendering/` + `animation/` | **Feature-parity checklist** — nothing player-visible silently lost |
| [09-worldsystem-boundary.md](09-worldsystem-boundary.md) | `events/` + world_system seam | **The sidecar IPC contract** (every crossing, sync/async, latency) |
| [10-content-and-saves.md](10-content-and-saves.md) | content JSON + assets + saves | Engine-agnosticism audit; save schema for cross-engine compatibility |
| [11-constants-and-tests.md](11-constants-and-tests.md) | constants ledger + test map | Every balance number (file:line); conformance mining guide |

## Verification status

The planned adversarial verification pass (independent agents re-checking ≥8
load-bearing claims per doc against the code) was **cut short by the monthly
subagent spend limit** — all 11 docs were written; **none received its formal
verification pass yet**.

Inline spot-checks performed 2026-07-17 (3/3 confirmed exactly):
- `game_engine.py` is exactly 12,035 lines (doc 01's count, against CLAUDE.md's stale ~11,700)
- invented-item LLM `temperature=0.7` at `game_engine.py:5031` (docs say 0.4 — code wins)
- activity-time double-tick: `_update_activity_time(dt)` called at both 8394 and 8442

**Treat file:line citations as high-confidence but re-verify before acting on
any single claim.** To run the formal verification pass once subagent budget
is available again, resume the workflow — completed inventory agents return
cached, only verifiers run:
`Workflow(scriptPath: <session>/workflows/scripts/godot-migration-inventory-wf_243bf9af-658.js, resumeFromRunId: "wf_243bf9af-658")`
