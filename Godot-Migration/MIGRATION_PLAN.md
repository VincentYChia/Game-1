# Game-1 → Godot 4 (3D) — Master Migration Plan

**Branch:** `godot-migration` · **Started:** 2026-07-17
**Mandate:** Complete game migration to Godot 3D. **No gameplay features lost** —
only features *added* where 2D→3D necessitates them.

Read [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) first — the nine ADRs
are the load-bearing choices. [CONFORMANCE.md](CONFORMANCE.md) is the verification
doctrine. [inventory/](inventory/) holds the eleven per-subsystem porting contracts
(each adversarially verified against the code).

---

## 1. Purpose and non-negotiables

The Python/Pygame build (434 files, ~159,800 LOC, 1,219 green tests, playtest-GO as
of 2026-07-17) is the **reference build**. It keeps running unmodified throughout
the migration — it is the oracle, the fallback, and the playtest vehicle until the
Godot build reaches parity.

Non-negotiables:
1. **Sacred constants survive verbatim** — damage `base × hand(1.1–1.2) ×
   STR(1+STR×0.05) × skill × class(≤1.2) × crit(2×) − def(≤75%)`; EXP
   `int(200 × 1.75^(lvl−1))`, max level 30; tier multipliers 1/2/4/8; durability
   floor 50% (never breaks); LCK crit 0.12/pt; the full ledger is
   [inventory/11-constants-and-tests.md](inventory/11-constants-and-tests.md).
2. **Content JSON untouched** (ADR-4). Loaders port; content does not move.
3. **Every phase exits through an oracle**, not through "looks right" (ADR-5).
4. **The feature-parity checklist** ([inventory/08-presentation.md](inventory/08-presentation.md))
   must be fully ticked before the Python build is retired. Nothing player-visible
   is silently dropped.

## 2. Methodology

**Conformance-gated vertical slices** (strangler-fig, not big-bang):

- Port bottom-up along the dependency graph: pure logic → data layer → simulation →
  engine presentation. Each phase produces a *playable or testable* artifact.
- `Game1.Core` (pure .NET, no Godot) holds all rules; `dotnet test` runs the
  conformance suite on every change without booting an engine. Engine glue stays thin.
- The golden-vector generator is re-runnable at any time; if Python balance changes
  mid-migration (it will — playtests are running), regenerate and the C# suite tells
  you exactly what moved.
- Each subsystem's inventory doc is its **porting contract**: file dispositions,
  public surface, constants, event topics, 3D notes, Godot mapping. A port PR is
  reviewed against its contract.
- **Why the Unity attempt failed, and what we do differently:** it ported logic in
  engine-shaped phases with no behavioral oracle and no continuously-runnable
  reference. Here the reference build never stops working, every slice is
  conformance-gated, and the engine is the last thing wired, not the first.

## 3. Phase plan

Ordering follows the dependency graph; each phase lists its **exit oracle**.

| Phase | Scope | Exit oracle |
|---|---|---|
| **P0 Foundation & Oracle** *(this session)* | Branch, inventory contracts, ADRs, Godot+C# scaffold, golden generator, first conformance slice (EXP, stats, crit, defense, damage composition, difficulty, reward) | `generate_goldens.py` runs green from live Python; C# tests compile and pass on goldens once SDK installed |
| **P1 Data layer** | C# models + all 16 database loaders, Update-N overlay, generated-content registries, tag definitions | Loader-parity goldens: Python dumps normalized DB contents; C# loads the same JSON; diff is empty |
| **P2 Character core** | Stats, leveling, inventory (30 slots/stacking), equipment (8 slots), buffs, titles, classes, durability/weight/repair, status effects | Golden vectors + ported unit tests; save fragment round-trip |
| **P3 World & 3D ground** | Chunk/biome generation (deterministic), GridMap terrain, collision, player controller, camera, interaction raycasts | Same seed → identical tile grid hash Python vs C#; walkable 3D world |
| **P4 Combat** | Damage pipeline, crit, per-target defense, attack state machine, hitboxes (2D→3D volumes), projectiles, enemies, enchantments (all 14), status ticks, dungeon waves | crux-foundry scenario parity on deterministic seeds (MT19937 port for exact RNG streams where needed); viability report reproduces within tolerance |
| **P5 Gathering & resources** | Resource nodes, tool effectiveness, yields, LCK quality/rare-drop, forestry/mining | Golden yield tables; gather loop playable in 3D |
| **P6 Crafting** | Stations, 6 minigame logic cores + Control-panel UIs, difficulty/reward calculators (pinned in P0), failure-loss, invented items + classifiers via sidecar | Minigame logic goldens (scoring scenarios); classifier round-trip through sidecar |
| **P7 Skills & progression UI** | 35 skills, mana/cooldowns, skill unlocks, encyclopedia, map/waypoints, quest log UI | Skill-effect goldens (executor paths); UI parity checklist |
| **P8 Save/load** | Full save schema, atomic .bak writes, versioning | **A Python save loads in Godot and round-trips** (ADR-9) |
| **P9 Living-world bridge** | Sidecar launcher/health/restart, IPC per the doc-09 contract, event forwarding, NPC dialogue, quests + affinity turn-in, F12 overlay data, speechbanks | All doc-09 crossings exercised end-to-end against the real sidecar; degrade paths verified with sidecar killed |
| **P10 3D polish & parity sign-off** | Camera polish, lighting, 3D audio, nav for NPC wander, art upgrade pass (billboard→model where wanted) | Feature-parity checklist 100% ticked; playtest sign-off on the parity build |
| **P11 True 3D gameplay** — **REQUIRED; the migration is NOT done without it** (user directive 2026-07-18) | Gameplay verticality: jump, cliff/height traversal, fall damage, height-aware hitboxes/AoE/projectiles, vertical camera work, 3D navmesh combat AI; explicit rebalance pass for every number verticality touches | New conformance baseline ratified (deliberate, documented deltas from the parity goldens) + 3D playtest sign-off |

Phases P1–P2 are pure `dotnet` work (no Godot needed). P3 is where the engine enters.
P11 is deliberately last: it *intentionally* breaks planar-parity balance, so it needs
the certified baseline to deviate from on purpose rather than by accident.

## 4. 3D-necessitated additions (the ONLY allowed feature additions)

Tracked explicitly so scope stays honest:
- Third-person camera (orbit/follow, collision-aware)
- Camera-relative WASD movement mapping
- 3D hitbox volumes (extruded equivalents of the 2D shapes — zero balance change)
- Terrain visual relief + biome meshing (visual-only in P3)
- Billboarded entity rendering (Sprite3D) and its draw-order/lighting rules
- 3D-positional audio (was flat 2D)
- NPC navmesh wander (replaces 2D grid wander, same behavioral envelope)
- **True verticality (jump/cliffs/fall damage/height-aware combat) — COMMITTED
  scope, Phase 11.** Not optional: the user's definition of done includes true 3D
  (2026-07-18). Sequenced last because it changes balance and needs the certified
  parity baseline to deviate from deliberately.

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Formula drift during port (the Unity failure mode) | ADR-5 oracle; goldens generated from live code, never hand-derived |
| Python `random` vs C# RNG divergence breaks crux parity | Port MT19937 (fully specified, ~60 lines) behind an injected RNG interface; distribution tests elsewhere |
| game_engine.py hidden coupling (11.7k-line monolith) | Doc-01 decomposition map with per-cluster line ranges + update-order contract; port clusters one at a time |
| Sidecar lifecycle on player machines (no Python installed) | PyInstaller-frozen sidecar, health-check + auto-restart + graceful degrade (degrade paths already exist and are tested) |
| Save incompatibility discovered late | Save round-trip is its own phase gate (P8) and P2 already round-trips fragments |
| Content JSON pixel-space fields misinterpreted in 3D | Doc-10 engine-agnosticism audit enumerates them; interpretation layer, never content edits |
| Balance changes on `main` during long migration | Reference build stays live; goldens regenerate on demand; diff = exact behavioral delta |
| Toolchain absent on dev machine | Two installs (below); everything else in P0 was built file-complete so the first `dotnet test` run is immediate |

## 6. Operator setup (one-time, ~10 minutes)

Neither tool is currently installed (probed 2026-07-17):
1. **.NET 8 SDK** — `winget install Microsoft.DotNet.SDK.8` (or dotnet.microsoft.com)
2. **Godot 4.4+ .NET edition** — godotengine.org/download (the "\.NET" build, not the
   standard one)

Then: `cd Game-1-Godot && dotnet test` (conformance suite) and open the project in
Godot once so it generates its solution glue.

## 7. Status log

- **2026-07-17 — P0 executed.** Branch created; 11 inventory contracts written by
  parallel subagents (the formal adversarial-verification pass was cut short by the
  monthly subagent spend limit — see `inventory/README.md` for status, inline
  spot-check results 3/3 exact, and the workflow-resume command); ADRs 1–9 accepted;
  Godot project + C# solution scaffolded; golden generator built and run against the
  live Python modules (fixtures in `Game-1-Godot/conformance/goldens/`); first C#
  port slice (`GameConstants`, `ExperienceCurve`, `StatScaling`, `CritChance`,
  `DefenseReduction`, `DamageComposition`, reward/difficulty bands) authored with
  xunit conformance tests. Blocked only on the two installs above for the first
  `dotnet test` run.

- **2026-07-18 — ADRs user-confirmed; toolchain live; checkpoint green.** All four
  headline decisions confirmed by the user, with one amendment: **true 3D
  verticality is required scope** — added as Phase 11, the migration's final gate.
  Toolchain installed without winget (broken App Installer): .NET SDK 8.0.423
  user-scoped + Godot 4.4.1 .NET, both on user PATH, DOTNET_ROOT persisted (Godot
  mono hard-crashes without it). First real run: **24/24 conformance tests pass**,
  solution builds clean incl. Game1.Godot, Godot boots the project headless.
  PR #83 (crux-foundry → main) merged.

- **2026-07-18 (later) — P1 data layer: 8 of 16 databases at byte-level parity.**
  New oracle `conformance/dump_databases.py` replays the game_engine.py:135-182
  boot and dumps normalized DB state; `DbParityTests` loads the same content
  through the C# loaders and requires an empty deep-diff. Ported green:
  Material (sacred 7-file sequence + generated overlay), Equipment (raw store),
  Recipe (3 output dialects + station order), Skill, Title, Class, Translation,
  Placement + UpdateLoader overlay. Suite: **33/33**. The parity gate caught a
  real divergence on its first run (four alchemy consumables carry
  `effectParams` as an ARRAY — Python passes raw; a typed helper had coerced
  to `{}`).
- **2026-07-18 (later still) — P1 at 10/16 databases, suite 38/38.**
  ResourceNodeDatabase (category caches order-gated, tier map, qualitative→
  numeric conversion tables executed from the live model incl. the "quick"
  respawn synonym, ICON_NAME_MAP as the Godot asset remap) and NpcDatabase
  (v3 canonical path: NPCs + quests, speechbank flatten, description
  long→short fallback, rewards normalization incl. statPoints alias,
  generated-merge as reload-only exactly like boot) both passed parity on
  their first run. Documented deviation: the npcs-enhanced.JSON v2 legacy
  adapter is NOT ported (contract doc 03 flags it candidate dead code; the
  C# loader fail-loud logs if v3 files are missing). Position model is
  already 3D (x, y, z) in Python — the (x,y)→(x,0,z) mapping concern from
  the old Unity plan is moot.
- **2026-07-18 (cont.) — P1 at 13/16 databases, suite 43/43.** ChunkTemplate
  (geo dispatch bridge shared with the sidecar, geoTypes auto-register with
  sacred-wins + Python dict insertion-order semantics, str/int/bool()
  coercions mirrored incl. truthiness), WorldGenerationConfig (10 sections,
  dilutive normalization, zone lookups executed), QuestArchive (sidecar-
  boundary substrate — BEHAVIORAL oracle: synthetic records through the
  real Python class, its query results replayed in C#: tag match_all/any +
  limit-break order, stable recency sort, round-trip). All green on first
  parity runs.
- **2026-07-18 (close) — P1 DATA LAYER COMPLETE: 15/16 databases, suite
  47/47.** VisualConfig (every accessor executed as oracle — designer visual
  tuning survives the engine swap) and MapWaypointConfig (waypoint rules
  incl. `get_max_waypoints_for_level` executed for all 30 levels, biome
  color table + UI config kept as Godot-theme data) close out the loaders.
  The 16th database, skill_unlock_db, is **deliberately P2 scope**: it
  parses the UnlockRequirements condition graph, which types together with
  title requirements behind ICharacterQuery. world.py models port alongside
  their consumers in P2/P3. **P1 exit oracle satisfied** — every
  content-loading database reproduces the Python loaders' normalized state
  from the same content files. Next: P2 character core (stats/leveling
  already pinned in P0; inventory, equipment incl. EquipmentItem
  materialization formulas, buffs, titles+conditions, status effects,
  durability/weight, save fragments).

- **2026-07-18 (P2 opened) — UnlockConditions + ICharacterQuery ported; P1 now
  16/16; suite 51/51.** The tag-driven condition system (8 condition types,
  factory with new + legacy formats incl. milestone mappings and the
  gather_count half-split) ports with a two-sided oracle: parse parity (specs
  from the fixture through both factories → identical to_dict/descriptions,
  incl. Python str.title() semantics) and evaluation parity (stub characters ×
  requirement matrix through the real Python classes). Character duck-typing
  is now the explicit ICharacterQuery interface (per contract docs 03/04).
  This closed the P1 titles-requirements exclusion AND unblocked
  SkillUnlockDatabase (sacred + Update-N fishing overlay, trigger/cost/
  requirements gated per unlock). Two dump-harness bugs found by the gate
  itself: sort_keys reordering order-sensitive spec dicts (fixed by
  pre-sorted specs), and the dump loading skill-unlocks after the update
  overlay instead of boot order (fixed to game_engine.py:177 order).
  Remaining P2: EquipmentItem materialization (+ SmithingTagProcessor),
  inventory, buffs, status effects, durability/weight, save fragments.

## 7a. Parked — DO NOT FORGET

| Item | Why parked | Unblock |
|---|---|---|
| Formal adversarial verification of the 11 inventory contracts (0/11 formally verified; 3/3 inline spot-checks exact) | Monthly subagent spend limit hit mid-workflow 2026-07-17 | When budget resets: resume `wf_243bf9af-658` per `inventory/README.md`; until then, re-verify any contract claim firsthand before acting on it |
| **P11 True 3D** — user will "not consider this fully done until we get there" | Deliberately sequenced after parity certification | Automatic: it is the final phase gate, not an optional item |

## 8. Load-bearing findings from the inventory pass

Full detail in the per-subsystem docs; these shape phase work:

1. **The per-frame update order is a contract** — `game_engine.py:8363-8576`
   encodes strict sequencing (WMS drain before combat; enemy attacks/status resolve
   before player buff ticks; hitboxes before projectiles; world fully pauses during
   minigames/pause). `_PhysicsProcess` must reproduce it or combat feel and DoT
   timing silently change. (doc 01)
2. **Two independent crit systems must NOT be unified** — the effect executor's
   `critical` special tag (0.15 chance / 2.0×, `effect_executor.py:119-126`) is
   separate from the sacred LCK crit (0.12/pt) in the combat manager. (doc 02)
3. **Duck typing is the correctness surface** — `hasattr` chains and
   signature-sniffing dispatch silently no-op in Python; the C# port needs explicit
   complete interfaces (`IDamageable`, `IStatusReceiver`, INT-scalable minigames via
   an `IIntScalable` interface or the sacred INT difficulty reduction silently
   drops). (docs 01, 02)
4. **Bug-compatible behaviors survive verbatim until parity is certified** — full
   base damage applied once per damage tag; `converts_to_healing` early-return;
   status params merged only for keys present in tag defaults; first-try-bonus
   inconsistency between reward_calculator and engineering.py. Port them as-is,
   flag for post-parity cleanup. (doc 02)
5. **Invented-item persistence is a 4-way registration** (Crafter, RecipeDatabase,
   PlacementDatabase, Material/Equipment DB) keyed by an MD5 placement-hash dedup —
   miss one on load and player-invented items vanish. (doc 01)
6. **Known engine bugs to DECIDE on, not blindly port** — activity time
   double-ticked per frame (8394 + 8442, verified); CHEST_OPENED/FISH_CAUGHT always
   publish position (0,0); F9 quick-load skips `game_time` restore; enchant
   test-apply mutates real equipment. Decision: fix in C# and note the behavioral
   diff in goldens, or port bug-compatible. Default: fix, document, regenerate. (doc 01)
7. **Doc drift confirmed again** — invented-item LLM temperature is 0.7 in code
   (game_engine.py:5031, verified) vs 0.4 documented; game_engine.py is 12,035
   lines (verified). The code-is-truth doctrine stands.
