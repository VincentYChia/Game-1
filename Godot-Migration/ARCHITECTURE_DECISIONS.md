# Godot Migration — Architecture Decision Records

**Branch:** `godot-migration` · **Started:** 2026-07-17
**Goal:** Complete migration of Game-1 to Godot 4 in 3D. Zero gameplay features lost;
features added only where the 2D→3D change necessitates them.

These ADRs are the standing decisions the migration is built on. Each records the
decision, the rationale, the alternatives rejected, and the escape hatch if it proves
wrong. **Challenge them before mass porting starts, not after.**

---

## ADR-1: Godot 4.x (.NET edition), not Godot 3, not a from-scratch engine

**Decision:** Target Godot 4.4+ .NET edition.

**Rationale:** Godot 4 is the current major line (Vulkan renderer, GDExtension,
first-class 3D). The .NET edition is required for ADR-2. Godot 3 is legacy; nothing
in this project needs its compatibility profile.

**Consequence:** Dev machine needs Godot 4.x .NET *and* the .NET 8 SDK installed
(neither is present as of 2026-07-17 — see MIGRATION_PLAN.md § Operator setup).

---

## ADR-2: C# for game logic, not GDScript

**Decision:** All ported game logic is C#. GDScript is permitted only for trivial
scene-local glue (a button handler, an editor tool script), never for game rules.

**Rationale:**
1. **This is a ~160k LOC typed port, not a prototype.** The Python code leans heavily
   on `@dataclass`, singletons, and typed component composition — it maps 1:1 onto C#
   records/classes. GDScript's dynamic typing would re-introduce the exact class of
   silent-drift bug the July 2026 audit spent weeks burning out.
2. **Conformance testing without the engine.** Pure-C# assemblies (`Game1.Core`) run
   under `dotnet test` against golden fixtures generated from the live Python code —
   no Godot boot, CI-friendly, fast. GDScript cannot execute outside Godot. This is
   the mechanism that makes "no gameplay features lost" *provable* (see ADR-5).
   This mirrors the property the Python codebase already has (1,219 tests run headless
   with a dummy SDL driver).
3. Performance headroom for the hot paths (per-frame status ticks, hitbox sweeps,
   chunk generation) without GDScript-specific optimization contortions.

**Rejected:** GDScript-only (untestable outside engine, untyped at this scale);
hybrid GDScript-UI/C#-logic (two languages for one team is a tax with no payoff —
Godot's C# API covers UI fine).

**Note on the failed Unity attempt:** the language is incidental. The Unity plan
failed on approach (big-bang phase structure, logic ported into an engine nobody had
validated end-to-end, no behavioral oracle). We keep the *lesson* — thin engine glue,
logic testable without a scene — and none of the artifacts. Per project direction the
Unity folder is ignored; nothing in this migration builds on it.

**Structure:**
- `Game1.Core` — pure .NET 8 class library. Zero Godot references. All rules, formulas,
  data models, loaders, combat/crafting/progression logic. Testable with `dotnet test`.
- `Game1.Godot` — the Godot C# project. Nodes, scenes, input, rendering, audio. Thin:
  it *calls* Game1.Core, it never *implements* rules.
- `Game1.Core.Tests` — xunit conformance + unit tests, driven by golden fixtures.

---

## ADR-3: The AI brain stays Python, as a bundled sidecar process

**Decision:** `world_system/` (WMS 7-layer memory, WNS narrative, WES content pipeline,
faction/NPC affinity — ~20.6k LOC), plus the ML crafting classifiers (CNN/LightGBM)
and LLM invented-item generation, are **not ported**. They run as a local Python
sidecar process that Godot launches and talks to over local IPC (JSON over a
localhost socket). The WMS SQLite databases remain owned by the sidecar.

**Rationale:**
1. **Certification is the asset.** This subsystem carries 1,219 passing tests and was
   certified against real LLMs at three fidelities in July 2026, including
   model-specific parser dialects and safety gates. A port throws that away and
   re-derives it in a second language for zero player-visible gain.
2. **It has no engine dependency.** It consumes game *events* and returns *content
   and text*. It never touches rendering, input, or the frame loop. It is already
   async-by-design (the July audit moved LLM calls off the game loop).
3. **The ML models are Python artifacts.** CNN + LightGBM inference in C# means ONNX
   export + numerical re-validation of every classifier — pure risk, no reward.
4. **The seam already exists.** GameEventBus is the boundary today; serializing those
   events over a socket instead of an in-process call is a transport change, not an
   architecture change.

**Distribution:** the sidecar ships as a PyInstaller-frozen executable next to the
Godot build; Godot launches it, health-checks it, restarts it on crash, and degrades
gracefully (same degrade paths that exist today when the LLM backend is down).

**This is not feature loss.** Every living-world feature ships; only the process
boundary moves. **Escape hatch:** the IPC contract doc (inventory doc 09) is written
so that a future C# reimplementation can slot in behind the same message schema if
we ever want a single-binary build.

---

## ADR-4: Content JSON is reused verbatim; loaders are ported, content is not touched

**Decision:** All ~113 game-definition JSONs (`items.JSON/`, `recipes.JSON/`,
`placements.JSON/`, `Skills/`, `Definitions.JSON/`, `progression/`, `Update-*/`,
`world_system/config/`) are consumed byte-for-byte by the C# loaders. No renames, no
re-keying, no "cleanup while we're here."

**Rationale:** The content layer is engine-agnostic by design (the project's founding
principle: hardcode mechanics, JSON content) and is the designer's domain. Any
migration-driven mutation of it destroys the ability to diff behavior between the
Python reference build and the Godot build. `stats-calculations.JSON` already drives
stat scaling in Python — the C# port reads the same file with the same fallbacks.

**Dev vs export:** in development the Godot project reads the content directories
from the repo (single source of truth, shared with the still-runnable Python
reference build). For exported builds, a build script snapshots content into the
`.pck`. A single `ContentPaths` resolver in Game1.Core owns this indirection.

**Pixel-space fields:** any content field that encodes 2D/pixel assumptions
(placement grids, visual configs, waypoints) gets an *interpretation layer* in C#,
never a content edit. Inventory doc 10 is the audit of which fields those are.

---

## ADR-5: Conformance oracle — golden vectors generated from the live Python code

**Decision:** "No gameplay features lost" is enforced mechanically, not by review.
Two instruments:

1. **Golden vectors** — `Game-1-Godot/conformance/generate_goldens.py` imports the
   *actual running Python modules* (never re-derives formulas by hand) and emits
   JSON fixtures: EXP curve + cascade scenarios, stat scaling tables, crit-chance
   composition, defense reduction, damage composition, difficulty points/tiers,
   reward quality bands, failure-loss, durability. C# xunit tests load the same
   fixtures and must match exactly (integer) or to 1e-9 (float). Regenerating goldens
   after a Python balance change is one command; a golden diff IS the behavior diff.
2. **crux-foundry as the behavioral oracle** — the deterministic hermetic playtester
   (seeded personas → kills/deaths/viability) defines expected *emergent* outcomes.
   Phase 4's exit criterion is the Godot build reproducing crux scenario outcomes.
   For RNG-dependent paths the port injects an RNG abstraction; where exact parity is
   required we implement MT19937 in C# to reproduce Python `random.Random(seed)`
   streams (Python's generator is standard MT19937 — ~60 lines, fully specified).

**Doctrine:** the *code* is the source of truth, never the docs (docs drift — proven
repeatedly in the June/July audits). Every golden generator reads behavior from
imported game modules.

---

## ADR-6: 3D representation — same simulation grid, 3D presentation, billboards first

**Decision:**
- The world simulation stays the authoritative 100×100 tile grid with the same chunk
  generation (same seeds → same world). Mapping: tile `(x, y)` → world `(x, 0, z)`;
  the simulation is planar at first. Distances/ranges/AoE radii keep their tile-unit
  values on the XZ plane, so every balance number survives unchanged.
- Terrain renders via GridMap/mesh generation from tile data, with *visual* relief
  (biome-driven height noise) that does not affect simulation distances in Phase 3.
  True gameplay verticality (jumping, cliffs, fall damage, height-aware combat) is
  **committed, required scope** — per user direction 2026-07-18 the migration is
  NOT considered done until true 3D ships. It is sequenced LAST (Phase 11), after
  parity is certified, because it changes balance and therefore needs the locked
  conformance baseline as its reference point before deliberately deviating from it.
- Entities (player, enemies, NPCs, resource nodes) render as **billboarded sprites in
  3D** first (Sprite3D), reusing the existing 3,749-image asset base. This ships full
  gameplay parity without a 3D art pipeline. A model/art upgrade pass is Phase 10 and
  is purely presentational.
- Hitboxes: 2D shapes (arcs, circles, lines) extrude to 3D volumes (cylinder sectors,
  cylinders, capsules) with generous vertical extent — geometrically equivalent to
  the 2D game on flat ground, i.e. zero balance change.
- Camera: third-person orbit follow (new, 3D-necessitated). Input: WASD
  camera-relative movement (new mapping of existing 8-direction movement).

**Rationale:** parity first, spectacle second. Every "necessitated by 3D" feature is
additive on top of a certified-identical simulation, and each one is listed
explicitly in MIGRATION_PLAN.md § 3D-necessitated features so scope stays auditable.

---

## ADR-7: Crafting minigames remain 2D Control-node overlays

**Decision:** The 6 minigames (smithing, alchemy, refining, engineering, enchanting,
fishing) are 2D UI experiences and stay that way: Godot `Control`/`CanvasLayer`
panels over the 3D world, exactly as inventory/menus do. Their *logic* (scoring,
timing windows, grids, performance 0–1, material consumption incl. the 30–90%
tier-scaled failure loss) ports to Game1.Core; their *drawing* is rebuilt in Godot UI.

**Rationale:** the minigames' pygame code is already split logic-vs-draw (the July
port contracts confirm this); a 3D reimagining of six minigames is a game-design
project, not a migration, and would violate "no features lost, only necessitated
additions." The CNN classifiers consume the same grid states either way (sidecar).

---

## ADR-8: Event bus mirrors 1:1; the wire is the sidecar boundary

**Decision:** `Game1.Core` gets a C# `GameEventBus` with the same topic names and
payload keys as `events/event_bus.py`. All ~60 event types keep their exact string
identities. A `SidecarBridge` (engine-side) subscribes to the topics world_system
consumes today and forwards them over IPC; responses/callbacks re-enter as bus
events or direct replies.

**Rationale:** topic identity is what makes the WMS evaluators, triggers, and stat
tracking work unchanged on the other side of the wire. Renaming topics during a
migration is self-sabotage.

---

## ADR-9: Save compatibility — a Python save loads in Godot

**Decision:** The Godot build reads and writes the existing save format (same JSON
schema, same atomic .bak discipline). WMS SQLite files stay sidecar-owned and
therefore carry over untouched. Acceptance test: a save produced by the Python
reference build loads in Godot and round-trips back.

**Rationale:** it forces the C# data model to be *actually* equivalent (the save
touches character, inventory, equipment, skills, world, quests, invented recipes —
everything), and it lets playtesters carry progress across the migration.

---

## Decision log

| # | Decision | Status |
|---|----------|--------|
| 1 | Godot 4.x .NET | Accepted 2026-07-17 |
| 2 | C# logic / thin glue / pure-core assembly | Accepted 2026-07-17 |
| 3 | Python sidecar for world_system + ML | Accepted 2026-07-17 |
| 4 | Content JSON verbatim | Accepted 2026-07-17 |
| 5 | Golden-vector + crux-foundry oracle | Accepted 2026-07-17 |
| 6 | Planar sim in 3D presentation, billboards first; true 3D verticality REQUIRED as final phase (P11) | Accepted 2026-07-17; amended + user-confirmed 2026-07-18 |
| 7 | Minigames as 2D Control overlays | Accepted 2026-07-17 |
| 8 | Event bus 1:1, IPC at the bus seam | Accepted 2026-07-17 |
| 9 | Save compatibility (Python save loads in Godot) | Accepted 2026-07-17 |
