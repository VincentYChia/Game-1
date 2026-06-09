# Game-1 Systems Catalog

**Baseline as of 2026-06-05** (after v8.2 reconciliation + boot-flow + minigame-recipe-path fixes).
Synthesized from 4 parallel codebase audits (core foundation / combat+visuals / crafting / world+NPCs) plus a direct read of the World System layer and a gap-check for tools, ML, audio, UI.

This catalog is intended as the **single baseline reference** for "what systems exist, what works, what's wired in gameplay, what's not." Future playtest plans and feature work should be planned against this document.

## Status legend

| Symbol | Meaning |
|---|---|
| ✓ | **WORKING** — code present, exercised in gameplay, integration verified or routine. |
| ◐ | **PARTIAL** — happy path works; documented gap(s) below. |
| ◯ | **DESIGNED-NOT-WIRED** — implementation exists but is not invoked from the gameplay loop. Silent. |
| ✗ | **BROKEN AT RUNTIME** — referenced by other code but missing files / unreachable / non-functional. |
| ⊘ | **NOT IMPLEMENTED** — designed in docs only, zero code. |

A system is marked ◯ when the code is good but **no caller in gameplay ever invokes it** — these are the "silent" gaps the user's intuition was tracking.

---

## Table of contents

1. [Critical findings (read first)](#critical-findings-read-first)
2. [Foundation](#1-foundation)
3. [Combat & Visuals](#2-combat--visuals)
4. [Crafting + Invented Items](#3-crafting--invented-items)
5. [World Generation & Environment](#4-world-generation--environment)
6. [NPCs, Quests, Factions, Dialogue](#5-npcs-quests-factions-dialogue)
7. [World Memory System (WMS)](#6-world-memory-system-wms)
8. [World Narrative System (WNS)](#7-world-narrative-system-wns)
9. [World Executor System (WES)](#8-world-executor-system-wes)
10. [Living World Infrastructure](#9-living-world-infrastructure)
11. [LLM / ML Pipeline](#10-llm--ml-pipeline)
12. [Save / Load](#11-save--load)
13. [UI & Input](#12-ui--input)
14. [Dev Tools](#13-dev-tools)
15. [Content updates (Update-N)](#14-content-updates-update-n)
16. [Audio — not implemented](#15-audio--not-implemented)
17. [Cross-cutting integration risks](#cross-cutting-integration-risks)
18. [Suggested playtest order](#suggested-playtest-order)

---

## Critical findings (read first)

**Revised 2026-06-05 after owner pushback corrected 5 false negatives.** These are the items where a system *exists* in code but is not actually exercised during gameplay, ranked by owner-stated priority.

### Active gaps to address (in priority order)

| # | Finding | Owner priority | Where |
|---|---|---|---|
| 1 | ~~**WMS Layers 5-7 end-to-end verification**~~ — **RESOLVED 2026-06-05**. Layer 3-7 managers now publish `WMS_LAYER_{N}_SUMMARY_CREATED` on the bus; `WMSToWNSBridge` subscribes and fires NL_N directly (Model C peak path). `wms_context_builder` cascades down. NL1 dialogue feeds L3 point-equivalent to L2 events. Full design + verification in `Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md`. 671/671 tests green (15 new). | Resolved | §6 |
| 2 | ~~**NPC Agent System (LLM dialogue) implemented but never called**~~ — **RESOLVED 2026-06-09**. `_generate_npc_opening` routes through `agent.generate_dialogue` at [game_engine.py:1616](Game-1-modular/core/game_engine.py); `_register_npcs_with_agent_system` walks `self.npcs` after init and registers each NPC's v3 inline personality + locality hierarchy. 11 new tests in [test_npc_agent_wiring.py](Game-1-modular/tests/test_npc_agent_wiring.py). | Resolved | §5, §9 |
| 3 | ~~**Faction system records affinity but never queried in NPC dialogue.**~~ — **RESOLVED 2026-06-09**. `_build_faction_context` calls `assemble_dialogue_context` per-NPC and threads affiliations + personal opinion + player standing + local sentiment into the system prompt. NPCMemoryManager wired to FactionSystem SQLite at boot. | Resolved | §5 |
| 4 | ~~**Content Registry needs proper construction at game-boot path.**~~ — **RESOLVED 2026-06-09** (was always wired; catalog claim was stale). Instantiated at [game_engine.py:4862](Game-1-modular/core/game_engine.py) with the WNS save_dir before WESOrchestrator init. End-to-end chunks reload chain green in [test_chunks_e2e.py](Game-1-modular/world_system/content_registry/tests/test_chunks_e2e.py). | Resolved | §9 |

### Known limitations (not actively prioritized)

| Finding | Disposition |
|---|---|
| LightGBM extractor `.pkl` files missing in `crafting_classifier_models/`. Training infra (`LightGBM_trainer.py`, `data_augment_GBM.py`, `*_train.jsonl`) all present — regeneratable. Workaround: inline `LightGBMFeatureExtractor` is used at runtime so classifiers work despite missing pickles. | Not blocking. |
| Mid-dungeon save not persisted — dungeon-only, minor. | Accepted limitation. |
| Ecosystem tool returns hardcoded stub values. | Owner: leave as-is (unused). |
| Audio not implemented (no `pygame.mixer`). | Owner: not needed at this time. |
| BalanceValidator exists only as spec. | Owner: back burner behind UI work. |
| Block / Parry combat mechanics | Owner: just ideas at this point. |
| Summon mechanics (TODO at `effect_executor.py:233`) | Owner: just ideas at this point. |
| `Self-Repair`, `Weightless`, `Silk Touch` enchantments — recipes exist in `recipes-adornments-1.json` (silk_touch at line 805, weightless at line 943) but combat runtime has no effect-type handler for them. JSON is source of truth; doc claim that they were "deferred" was a hallucination. | Not blocking; add handlers if/when prioritized. |

### Catalog corrections (these earlier "gaps" turned out to be FINE)

- **Fishing IS wired** — `get_fishing_manager()` called from `game_engine.py:11354` (start) + `11587` (process). Activated by clicking a fishing-spot resource at `game_engine.py:2760`, not through `craft_item`. Catalog fixed below. Fishing skills work; titles untested.
- **Update-N AUTO-LOADS at boot** — `game_engine.py:149` calls `load_all_updates(get_resource_path(""))`. Update-1 (5 weapons + 6 skills + 3 bosses) and Update-2 (fishing skills/titles/stations) both load automatically.
- **Quests complete automatically** — passive completion when requirements/goals are fulfilled. No manual turn-in needed. "No waypoint, no log reminder" was a misframing — it's by design.
- **Dungeon entry via interaction is fine** — interact-to-enter is the intended UX.
- **WMS Layers 5-7 ARE implemented** — `layer5_manager.py`, `layer5_summarizer.py` (+ 6, +7) all present and initialized at WorldMemorySystem boot. Catalog row updated. Owner asserts they should be functional end-to-end — needs runtime verification (Action item #1 above).

---

## 1. Foundation

The core gameplay base: engine, entities, data, events, progression.

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 1.1 | **Game Engine** | ✓ | [core/game_engine.py](Game-1-modular/core/game_engine.py) (~11K LOC) | Single 11K-line god-class. Main loop, event handling, UI dispatch, render. Holds references to every other system. |
| 1.2 | **Camera** | ✓ | [core/camera.py](Game-1-modular/core/camera.py) | Follows character, viewport math. |
| 1.3 | **Config / Constants** | ✓ | [core/config.py](Game-1-modular/core/config.py) | Tile/chunk sizes, spawn coords, debug flags, `TEMP_WORLD_SEED=13579` (2026-06-05), `INVENTORY_SLOT_SPACING`. |
| 1.4 | **Path Manager** | ✓ | [core/paths.py](Game-1-modular/core/paths.py) | Resolves paths against `Game-1-modular/` base. Used everywhere — fixes cwd issues. |
| 1.5 | **Game Event Bus** | ✓ | [events/event_bus.py](Game-1-modular/events/event_bus.py) | Pub/sub, ~60 event types. WMS subscribes broadly. Risk: handlers wrapped in `try/except` silently swallow errors. |
| 1.6 | **Character** | ✓ | [entities/character.py](Game-1-modular/entities/character.py) (~2600 LOC) | Composed of components (inventory, equipment, skills, stats, etc.). |
| 1.7 | **Inventory** | ✓ | [entities/components/inventory.py](Game-1-modular/entities/components/inventory.py) | 30 slots, drag/drop, stacking. No max_stack validation on add_item. |
| 1.8 | **Equipment** | ✓ | [entities/components/equipment_manager.py](Game-1-modular/entities/components/equipment_manager.py) | 8-10 slots, hand-type validation, durability, enchantment tracking. |
| 1.9 | **Stats (6 core)** | ✓ | [entities/components/stats.py](Game-1-modular/entities/components/stats.py) | STR/DEF/VIT/LCK/AGI/INT. JSON-driven post v8.2 trap 6. Derived stats recalc on `recalculate_stats()`. |
| 1.10 | **Leveling / EXP** | ✓ | [entities/components/leveling.py](Game-1-modular/entities/components/leveling.py) | 1-30, `200 × 1.75^(L-1)`. Hard cap at 30. |
| 1.11 | **Buffs / Debuffs** | ✓ | [entities/components/buffs.py](Game-1-modular/entities/components/buffs.py) | Duration tracking, consume-on-use. No deduplication; stacks allow duplicates. |
| 1.12 | **Skill Manager** | ✓ | [entities/components/skill_manager.py](Game-1-modular/entities/components/skill_manager.py) | Activation, mana, cooldowns, class affinity. Magnitude/cooldown/duration enums JSON-driven post v8.2 traps 4-5. |
| 1.13 | **Stat Tracker** | ✓ | [entities/components/stat_tracker.py](Game-1-modular/entities/components/stat_tracker.py) | 65 `record_*` methods feeding StatStore (SQL). Risk: any missed method = analytics blind spot. |
| 1.14 | **Activity Tracker** | ✓ | [entities/components/activity_tracker.py](Game-1-modular/entities/components/activity_tracker.py) | Per-action counters used by title unlock checks. |
| 1.15 | **Title System** | ✓ | [systems/title_system.py](Game-1-modular/systems/title_system.py) | Unlock conditions checked from activity tracker. |
| 1.16 | **Class System** | ✓ | [systems/class_system.py](Game-1-modular/systems/class_system.py) | 6 classes. Tag→tool bonuses JSON-driven post v8.2 trap 7. |
| 1.17 | **Tag System** | ✓ | [core/tag_system.py](Game-1-modular/core/tag_system.py), [core/tag_parser.py](Game-1-modular/core/tag_parser.py), [Definitions.JSON/tag-definitions.JSON](Game-1-modular/Definitions.JSON/tag-definitions.JSON) | Load-bearing for combat/skill/crafting. Risk: unknown tag → silent warning + no-op. |
| 1.18 | **Effect Executor** | ◐ | [core/effect_executor.py](Game-1-modular/core/effect_executor.py) | Tag-based effect dispatch. TODOs: summon (line 233), dash-contact-damage (line 510), timestamp (line 52). |
| 1.19 | **Geometry / Target Finder** | ✓ | [core/geometry/](Game-1-modular/core/geometry/) | Cone/circle/chain/beam targeting. |

---

## 2. Combat & Visuals

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 2.1 | **Combat Manager** (damage pipeline) | ✓ | [Combat/combat_manager.py](Game-1-modular/Combat/combat_manager.py) (2.3K LOC) | Full pipeline: `base × hand × STR × skill × class × crit − def`. Two paths (traditional + tag-based). |
| 2.2 | **Attack State Machine** | ✓ | [Combat/attack_state_machine.py](Game-1-modular/Combat/attack_state_machine.py) | IDLE→WINDUP→ACTIVE→RECOVERY→COOLDOWN per-attack. JSON-driven. |
| 2.3 | **Hitbox System** | ✓ | [Combat/hitbox_system.py](Game-1-modular/Combat/hitbox_system.py) | circle/arc/rect/line shapes. No pierce logic. |
| 2.4 | **Projectile System** | ✓ | [Combat/projectile_system.py](Game-1-modular/Combat/projectile_system.py) | Optional homing, gravity, AoE impact. |
| 2.5 | **Attack Profile Generator** | ✓ | [Combat/attack_profile_generator.py](Game-1-modular/Combat/attack_profile_generator.py) | Procedural enemy attacks from tier+damage type. |
| 2.6 | **Player Actions / Dodge / I-Frames** | ✓ | [Combat/player_actions.py](Game-1-modular/Combat/player_actions.py) | JSON-tunable via `combat-config.JSON > dodgeMechanics` (post v8.2 trap 19). |
| 2.7 | **Enemy AI** | ✓ | [Combat/enemy.py](Game-1-modular/Combat/enemy.py) (1.3K LOC) | AggroSystem + AIPattern + status manager. |
| 2.8 | **Status Effects** (17 types) | ✓ | [entities/status_effect.py](Game-1-modular/entities/status_effect.py) (826 LOC) | DoT/CC/buffs/debuffs/specials. Duck-types `hasattr(target, 'take_damage')`. |
| 2.9 | **Enchantments (~11 firing, several JSON-only)** | ◐ | [Combat/combat_manager.py](Game-1-modular/Combat/combat_manager.py) | Verified-firing effect types: `lifesteal`, `chain_damage`, `durability_multiplier` (Unbreaking), `damage_over_time` (Fire Aspect, Poison), `knockback`, `slow` (Frost Touch), `devastate`. Sharpness, Protection, Thorns, Health Regen also firing via separate paths. **`silk_touch`, `weightless`, `self_repair` recipes exist in `recipes-adornments-1.json` but have NO combat-runtime handler** — they craft but don't have runtime effects. JSON is source of truth; doc claim that these were "deferred by design" was hallucinated. |
| 2.10 | **Block / Parry** | (future idea) | TODO comments only | Owner: just an idea at this point. |
| 2.11 | **Summon mechanics** | (future idea) | [core/effect_executor.py:233](Game-1-modular/core/effect_executor.py#L233) | Owner: just an idea at this point. |
| 2.12 | **BalanceValidator** | (deferred) | Spec only in `Development-Plan/SHARED_INFRASTRUCTURE.md` | Owner: back burner behind UI work. |
| 2.13 | **Animation Framework** | ✓ | [animation/](Game-1-modular/animation/) (7 files, 1K LOC) | Manager + procedural + weapon visuals + combat particles + sprite animation. Single-shot only, no looping. |
| 2.14 | **Renderer** (master) | ✓ | [rendering/renderer.py](Game-1-modular/rendering/renderer.py) (~8K LOC, 98 methods) | Single file does world, UI, crafting grids, combat effects, NPCs, dungeons, tooltips. **No subsystem abstraction** — high complexity. |
| 2.15 | **Visual Effect Bridge** | ✓ | [rendering/visual_effect_bridge.py](Game-1-modular/rendering/visual_effect_bridge.py) | Adapts combat events to particle/color/animation calls. |
| 2.16 | **Visual Colors (single source)** | ✓ | [rendering/visual_colors.py](Game-1-modular/rendering/visual_colors.py) | Centralized post v8.2 trap 13. |
| 2.17 | **Terrain Renderer** | ✓ | [rendering/terrain_renderer.py](Game-1-modular/rendering/terrain_renderer.py) | Tile + biome + neighbor-edge dithering. |
| 2.18 | **Image Cache** | ✓ | [rendering/image_cache.py](Game-1-modular/rendering/image_cache.py) | Sprite/icon preloading, no async. |
| 2.19 | **Map Cache** | ✓ | [rendering/map_cache.py](Game-1-modular/rendering/map_cache.py) | Pre-renders geographic map surface. |
| 2.20 | **Loading Screen** | ✓ | [rendering/renderer.py:render_loading_screen](Game-1-modular/rendering/renderer.py) | Added 2026-06-05. Stage labels + flavor line + progress bar. |
| 2.21 | **Pause Menu** | ✓ | [rendering/renderer.py:render_pause_menu](Game-1-modular/rendering/renderer.py) | Added 2026-06-05. Return / Save & Exit / Exit without saving. |
| 2.22 | **Start Menu** | ✓ | [rendering/renderer.py:render_start_menu](Game-1-modular/rendering/renderer.py) | New / Load / Default Save / Temp World. |

---

## 3. Crafting + Invented Items

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 3.1 | **Crafting Classifier Manager** | ◐ | [systems/crafting_classifier.py](Game-1-modular/systems/crafting_classifier.py) (1.4K LOC) | CNN (smithing/adornment) + LightGBM (alchemy/refining/engineering). LightGBM `*.pkl` extractor files MISSING but code uses inline `LightGBMFeatureExtractor` — works in spite of missing files (silent by design). |
| 3.2 | **LLM Item Generator** | ✓ | [systems/llm_item_generator.py](Game-1-modular/systems/llm_item_generator.py) (1.4K LOC) | Claude API with `MockBackend` fallback. Async via background thread. Risk: silent fallback if `ANTHROPIC_API_KEY` not set. |
| 3.3 | **Interactive Crafting UI** | ✓ | [core/interactive_crafting.py](Game-1-modular/core/interactive_crafting.py) (1.2K LOC) | Material palette + placement grid + recipe detection. |
| 3.4 | **Smithing minigame** | ✓ | [Crafting-subdisciplines/smithing.py](Game-1-modular/Crafting-subdisciplines/smithing.py) | Temperature + hammer strikes. Recipe loading cwd-robust post 2026-06-05 fix. |
| 3.5 | **Refining minigame** | ✓ | [Crafting-subdisciplines/refining.py](Game-1-modular/Crafting-subdisciplines/refining.py) | Cylinder alignment. |
| 3.6 | **Alchemy minigame** | ✓ | [Crafting-subdisciplines/alchemy.py](Game-1-modular/Crafting-subdisciplines/alchemy.py) | Reaction-chain 5-stage. |
| 3.7 | **Engineering minigame** | ✓ | [Crafting-subdisciplines/engineering.py](Game-1-modular/Crafting-subdisciplines/engineering.py) | Slot-puzzle. |
| 3.8 | **Enchanting / Adornments minigame** | ✓ | [Crafting-subdisciplines/enchanting.py](Game-1-modular/Crafting-subdisciplines/enchanting.py) | Vertex pattern + CNN-validated. |
| 3.9 | **Fishing** | ✓ | [Crafting-subdisciplines/fishing.py](Game-1-modular/Crafting-subdisciplines/fishing.py) | `FishingMinigame` + `FishingManager`. Wired via **resource interaction**, not `craft_item`: clicking a fishing-spot resource at [game_engine.py:2760](Game-1-modular/core/game_engine.py#L2760) calls `fishing_manager.start_fishing()` at [game_engine.py:11354](Game-1-modular/core/game_engine.py#L11354); result handled at [game_engine.py:11587](Game-1-modular/core/game_engine.py#L11587). Fishing skills work; fishing titles untested (2026-06-05). |
| 3.10 | **Difficulty Calculator** | ✓ | [core/difficulty_calculator.py](Game-1-modular/core/difficulty_calculator.py) | Material tier points + discipline modifiers. Reconciled w/ reward_calculator post v8.2 trap 1. |
| 3.11 | **Reward Calculator** | ✓ | [core/reward_calculator.py](Game-1-modular/core/reward_calculator.py) | Performance → quality tier + first-try bonus per discipline. Centralized post v8.2 traps 1, 3. |
| 3.12 | **Rarity System** | ✓ | [Crafting-subdisciplines/rarity_utils.py](Game-1-modular/Crafting-subdisciplines/rarity_utils.py) | Single source post v8.2 trap 2. |
| 3.13 | **Recipe Database** | ✓ | [data/databases/recipe_db.py](Game-1-modular/data/databases/recipe_db.py) | 155 recipes loaded; uses `get_resource_path` — cwd-robust. |
| 3.14 | **Per-discipline crafter recipe loaders** | ✓ | [Crafting-subdisciplines/*.py](Game-1-modular/Crafting-subdisciplines/) | All 5 made cwd-robust 2026-06-05 (fix for `smithing_steel_longsword` create_minigame=None bug). |
| 3.15 | **Placement Database** | ✓ | [data/databases/placement_db.py](Game-1-modular/data/databases/placement_db.py) | 193 placement templates. |
| 3.16 | **Crafting Tag Processor** | ✓ | [core/crafting_tag_processor.py](Game-1-modular/core/crafting_tag_processor.py) | Translates LLM-output tags into slot assignments + inheritance. |
| 3.17 | **Minigame Effects / Particles** | ✓ | [core/minigame_effects.py](Game-1-modular/core/minigame_effects.py) (1.5K LOC) | Backgrounds + particle systems. |
| 3.18 | **Invented Recipe Persistence** | ✓ | [systems/save_manager.py](Game-1-modular/systems/save_manager.py) | `_serialize_invented_recipes` + `register_saved_invented_recipes` on load. |

---

## 4. World Generation & Environment

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 4.1 | **World System** | ✓ | [systems/world_system.py](Game-1-modular/systems/world_system.py) | Seed-based, `defer_init=True` for loading-screen flow (2026-06-05). `world_map_seed_<seed>.gz` cache. |
| 4.2 | **Chunk System** | ✓ | [systems/chunk.py](Game-1-modular/systems/chunk.py) | 16×16 tiles. New `template_locked` flag (2026-06-05) — unvisited chunks re-roll on `ChunkTemplateDatabase` updates. |
| 4.3 | **Biome Generator (legacy)** | ✓ | [systems/biome_generator.py](Game-1-modular/systems/biome_generator.py) | Fallback only; primary is `systems/geography/`. |
| 4.4 | **Geography System** | ◐ | [systems/geography/](Game-1-modular/systems/geography/) (~13 files, 3K LOC) | Nations→Regions→Provinces→Districts→Biomes hierarchy. Villages generated. **NPC dialogue does NOT yet query faction context from geography.** |
| 4.5 | **Chunk Template Database** | ✓ | [data/databases/chunk_template_db.py](Game-1-modular/data/databases/chunk_template_db.py) | JSON-driven, replaces hardcoded `_GEO_TO_CHUNK_TYPE`. WES-generated chunks flow through here. |
| 4.6 | **Resource Node Database** | ✓ | [data/databases/resource_node_db.py](Game-1-modular/data/databases/resource_node_db.py) | Reloadable. |
| 4.7 | **Material Database** | ✓ | [data/databases/material_db.py](Game-1-modular/data/databases/material_db.py) | 77 materials + 77 rarity entries. SACRED_LOAD_SEQUENCE for 7-call boot consolidation. |
| 4.8 | **Equipment Database** | ✓ | [data/databases/equipment_db.py](Game-1-modular/data/databases/equipment_db.py) | Weapons/armor/tools. Note: uses `load_from_file` (singular), not `load_from_files`. |
| 4.9 | **Translation Database** | ✓ | [data/databases/translation_db.py](Game-1-modular/data/databases/translation_db.py) | Skill mana/cooldown/duration tables. SkillDatabase @properties delegate here post v8.2 trap 5. |
| 4.10 | **Dungeon System** | ✓ | [systems/dungeon.py](Game-1-modular/systems/dungeon.py) (~800 LOC) | Entrance spawning, wave generation, loot chest all work. Entry is interaction-based (intended UX). Minor accepted limitation: mid-dungeon save state not persisted (load while in dungeon → instance lost). |
| 4.11 | **Collision System** | ✓ | [systems/collision_system.py](Game-1-modular/systems/collision_system.py) | LOS, A* pathfinding, walkability. |
| 4.12 | **Map & Waypoint System** | ✓ | [systems/map_waypoint_system.py](Game-1-modular/systems/map_waypoint_system.py) | Chunk exploration + player-placed fast travel. Keybinding `P` (post v8.2 trap 18 reconciliation). |
| 4.13 | **Turret System** | ✓ | [systems/turret_system.py](Game-1-modular/systems/turret_system.py) | Placed-entity AI. No friendly-fire check. |
| 4.14 | **Encyclopedia / Compendium** | ✓ | [systems/encyclopedia.py](Game-1-modular/systems/encyclopedia.py) | Read-only viewer for skills/titles/invented recipes. |
| 4.15 | **Visual Config DB** | ✓ | [data/databases/visual_config_db.py](Game-1-modular/data/databases/visual_config_db.py) | Damage type colors, UI scaling. |

---

## 5. NPCs, Quests, Factions, Dialogue

This category contains the **densest concentration of "designed but not wired" gaps**. Read carefully.

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 5.1 | **NPC Database** | ✓ | [data/databases/npc_db.py](Game-1-modular/data/databases/npc_db.py) | Load + `get_voice_excerpt(npc_id)` for WNS context. |
| 5.2 | **NPC System (static)** | ✓ | [systems/npc_system.py](Game-1-modular/systems/npc_system.py) | Spawn + proximity-based interaction. `get_next_dialogue` uses speechbank (greeting → idle_barks → fallback). |
| 5.3 | **NPC Agent System (LLM)** | ✓ | [world_system/living_world/npc/npc_agent.py](Game-1-modular/world_system/living_world/npc/npc_agent.py), [npc_memory.py](Game-1-modular/world_system/living_world/npc/npc_memory.py) | ~665 LOC. **2026-06-09 update:** `game_engine._generate_npc_opening` routes through `agent.generate_dialogue` at [game_engine.py:1616](Game-1-modular/core/game_engine.py); falls back to static cycling only on agent absence/error. v3 inline personalities are wired via `_register_npcs_with_agent_system` after spawn (data/models/npcs.py:11 design intent). |
| 5.4 | **Quest System** | ✓ | [systems/quest_system.py](Game-1-modular/systems/quest_system.py) | Accept + track + automatic completion + grant rewards all work. Passive completion when objectives are fulfilled (no manual turn-in by design). LLM-adapted rewards path falls back to `effective_rewards` if no adapter call. |
| 5.5 | **Quest Archive** | ✓ | [data/databases/quest_archive_db.py](Game-1-modular/data/databases/quest_archive_db.py) | Phase 7 substrate. Wired into `QuestManager.complete_quest` 2026-06-05. WNS can read completed quests via tags/NPC/entity/result queries. |
| 5.6 | **Faction System** | ✓ | [world_system/living_world/factions/](Game-1-modular/world_system/living_world/factions/) (1.3K LOC, 50 tests) | SQLite-backed, 19-method API, schema fully wired. **2026-06-09:** NPCMemoryManager wired to FactionSystem at boot ([game_engine.py:4950](Game-1-modular/core/game_engine.py)); per-NPC dynamic state persists in `npc_dynamic_state`/`npc_affinity` SQLite tables. NPC agent prompt now threads faction affiliations + personal opinion + player standing + local sentiment via `_build_faction_context`. |
| 5.7 | **Faction Dialogue Helper** | ✓ | [world_system/living_world/factions/dialogue_helper.py](Game-1-modular/world_system/living_world/factions/dialogue_helper.py) | **2026-06-09:** `assemble_dialogue_context` now called from `npc_agent._build_faction_context` per-NPC, using the location hierarchy stored at `register_npc` time. Returns NPC profile + player standing + npc_opinion + inherited location affinity. |
| 5.8 | **Faction Quest Tool** | ◯ | [world_system/living_world/factions/quest_tool.py](Game-1-modular/world_system/living_world/factions/quest_tool.py) | Faction-aware quest filtering. Not called by `game_engine`. |
| 5.9 | **Faction Consolidator** | ◯ | [world_system/living_world/factions/consolidator.py](Game-1-modular/world_system/living_world/factions/consolidator.py) | LLM summary of faction state. Not called at runtime. |
| 5.10 | **Village NPC Spawning** | ✓ | [systems/world_system.py:get_village_npc_definitions](Game-1-modular/systems/world_system.py), [core/game_engine.py:_spawn_village_npcs](Game-1-modular/core/game_engine.py) | Wired via 2026-06-05 helper. Idempotent (re-runnable post-init). |

---

## 6. World Memory System (WMS)

The events-and-evaluators substrate. Cleanest of the three Living World layers — most of it actually fires in gameplay.

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 6.1 | **WMS Facade** | ✓ | [world_system/world_memory/world_memory_system.py](Game-1-modular/world_system/world_memory/world_memory_system.py) (733 LOC) | Top-level entry point. Subscribes to GameEventBus broadly. |
| 6.2 | **Event Recorder** | ✓ | [world_system/world_memory/event_recorder.py](Game-1-modular/world_system/world_memory/event_recorder.py) | GameEventBus → SQLite bridge. |
| 6.3 | **Event Store** | ✓ | [world_system/world_memory/event_store.py](Game-1-modular/world_system/world_memory/event_store.py) (1.1K LOC) | 20 SQL tables. |
| 6.4 | **Stat Store** | ✓ | [world_system/world_memory/stat_store.py](Game-1-modular/world_system/world_memory/stat_store.py) | Hierarchical dimensional stats. `activity_profile(locality_id)` helper added v8.x. |
| 6.5 | **Trigger Manager** | ✓ | [world_system/world_memory/trigger_manager.py](Game-1-modular/world_system/world_memory/trigger_manager.py) | Publishes `WMS_TRIGGER_FIRED` (G03). Risk: tuning of thresholds for short playtest sessions may keep this silent. |
| 6.6 | **Evaluators (33)** | ✓ | [world_system/world_memory/evaluators/](Game-1-modular/world_system/world_memory/evaluators/) | Combat/progression/social/exploration/ecosystem categories. 4 defaults aligned with memory-config.json post v8.2 trap 8. |
| 6.7 | **Consolidators (Layer 3+)** | ✓ | [world_system/world_memory/consolidators/](Game-1-modular/world_system/world_memory/consolidators/) | Interpretation→narrative→province summaries. |
| 6.8 | **Tag Library** | ✓ | [world_system/world_memory/tag_library.py](Game-1-modular/world_system/world_memory/tag_library.py) | 65-category taxonomy. |
| 6.9 | **Tag Assignment Engine** | ✓ | [world_system/world_memory/tag_assignment.py](Game-1-modular/world_system/world_memory/tag_assignment.py) | Layer 1→7 tag flow. |
| 6.10 | **Daily Ledger** | ✓ | [world_system/world_memory/daily_ledger.py](Game-1-modular/world_system/world_memory/daily_ledger.py) | Day-boundary aggregation. PresenceDriftDetector hooks here. |
| 6.11 | **WMS Layers 5-7** | ✓ | [layer5_manager.py](Game-1-modular/world_system/world_memory/layer5_manager.py), [layer5_summarizer.py](Game-1-modular/world_system/world_memory/layer5_summarizer.py), [layer6_manager.py](Game-1-modular/world_system/world_memory/layer6_manager.py), [layer6_summarizer.py](Game-1-modular/world_system/world_memory/layer6_summarizer.py), [layer7_manager.py](Game-1-modular/world_system/world_memory/layer7_manager.py), [layer7_summarizer.py](Game-1-modular/world_system/world_memory/layer7_summarizer.py) | All three manager classes + summarizers exist and are initialized at [world_memory_system.py:226-284](Game-1-modular/world_system/world_memory/world_memory_system.py). Layer 5 = region summarization, Layer 6 = nation summarization, Layer 7 = world summarization (singleton). **2026-06-05: end-to-end firing now verified.** Each layer publishes `WMS_LAYER_{N}_SUMMARY_CREATED` on the bus after `_store_summary`; `WMSToWNSBridge` subscribes and fires NL_N directly at the address (Model C peak path). Downstream readers via `wms_context_builder` cascade-down. See `Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md`. |
| 6.12 | **Geographic Registry** | ✓ | [world_system/world_memory/geographic_registry.py](Game-1-modular/world_system/world_memory/geographic_registry.py) | Locality registry for WMS scope. |
| 6.13 | **Tag Browser** | ✓ | [world_system/world_memory/tag_browser.py](Game-1-modular/world_system/world_memory/tag_browser.py) | Diagnostic / debug. |
| 6.14 | **Query API** | ✓ | [world_system/world_memory/query.py](Game-1-modular/world_system/world_memory/query.py) | Used by WNS context builder. |
| 6.15 | **Retention / Cleanup** | ✓ | [world_system/world_memory/retention.py](Game-1-modular/world_system/world_memory/retention.py) | Old event pruning. |

---

## 7. World Narrative System (WNS)

The narrative-weave layer that turns WMS event milestones into narrative directives for WES.

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 7.1 | **World Narrative System Facade** | ✓ | [world_system/wns/world_narrative_system.py](Game-1-modular/world_system/wns/world_narrative_system.py) (556 LOC) | Top-level WNS entry. |
| 7.2 | **NL Weaver (Layers 2-7)** | ✓ | [world_system/wns/nl_weaver.py](Game-1-modular/world_system/wns/nl_weaver.py) | Composes narrative threads from WMS events. |
| 7.3 | **NL1 Ingestor** | ✓ | [world_system/wns/nl1_ingestor.py](Game-1-modular/world_system/wns/nl1_ingestor.py) | Raw NPC dialogue + WMS events. |
| 7.4 | **NL Trigger Manager** | ✓ | [world_system/wns/nl_trigger_manager.py](Game-1-modular/world_system/wns/nl_trigger_manager.py) | Narrative-causal trigger detection. |
| 7.5 | **Behavior Interpreter** | ✓ | [world_system/wns/behavior_interpreter.py](Game-1-modular/world_system/wns/behavior_interpreter.py) | Phase 2 substrate. Subscribes to `WMS_TRIGGER_FIRED`. CooldownArbiter built in. Wired to GameEngine boot. |
| 7.6 | **Mixed Trigger Arbiter** | ✓ | [world_system/wns/mixed_trigger_arbiter.py](Game-1-modular/world_system/wns/mixed_trigger_arbiter.py) | Phase 7 substrate. Wired into BehaviorInterpreter 2026-06-05. |
| 7.7 | **Presence Drift Detector** | ✓ | [world_system/wns/presence_drift_detector.py](Game-1-modular/world_system/wns/presence_drift_detector.py) | Phase 7 substrate. Wired into WorldMemorySystem daily-ledger boundary 2026-06-05. |
| 7.8 | **WMS→WNS Bridge** | ✓ | [world_system/wns/wms_to_wns_bridge.py](Game-1-modular/world_system/wns/wms_to_wns_bridge.py) | Bundle assembly. |
| 7.9 | **WNS→WES Bridge** | ✓ | [world_system/wns/wns_to_wes_bridge.py](Game-1-modular/world_system/wns/wns_to_wes_bridge.py) | Publishes `WNS_CALL_WES_REQUESTED` with full bundle. NPC dialogue + WMS events context. |
| 7.10 | **Affinity Shift Parser** | ✓ | [world_system/wns/affinity_shift_parser.py](Game-1-modular/world_system/wns/affinity_shift_parser.py) | Parses XML `<AffinityShift>` directives from WNS responses. |
| 7.11 | **Affinity Resolver** | ✓ | [world_system/wns/affinity_resolver.py](Game-1-modular/world_system/wns/affinity_resolver.py) | Commits parsed shifts to FactionSystem. |
| 7.12 | **Cascade Trigger** | ✓ | [world_system/wns/cascade_trigger.py](Game-1-modular/world_system/wns/cascade_trigger.py) | Multi-step thread cascades. |
| 7.13 | **Geographic Context** | ✓ | [world_system/wns/geographic_context.py](Game-1-modular/world_system/wns/geographic_context.py) | Locality chain for context. |
| 7.14 | **Narrative Distance Filter** | ✓ | [world_system/wns/narrative_distance_filter.py](Game-1-modular/world_system/wns/narrative_distance_filter.py) | Relevance scoping. |
| 7.15 | **Narrative Store + Thread Index** | ✓ | [world_system/wns/narrative_store.py](Game-1-modular/world_system/wns/narrative_store.py), [thread_index.py](Game-1-modular/world_system/wns/thread_index.py) | SQLite narrative thread storage. |
| 7.16 | **WES Call Parser** | ✓ | [world_system/wns/wes_call_parser.py](Game-1-modular/world_system/wns/wes_call_parser.py) | Parses WES tool calls from WNS XML output. |

---

## 8. World Executor System (WES)

The deterministic + LLM content-generation layer. WNS publishes intent → WES generates concrete content → ContentRegistry commits.

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 8.1 | **WES Orchestrator** | ✓ | [world_system/wes/wes_orchestrator.py](Game-1-modular/world_system/wes/wes_orchestrator.py) (889 LOC) | Top-level. Planner → Hubs → Tools → Supervisor → Commit. |
| 8.2 | **Plan Dispatcher** | ✓ | [world_system/wes/plan_dispatcher.py](Game-1-modular/world_system/wes/plan_dispatcher.py) | Runs ExecutorSpecs from planner or RequestLayer. |
| 8.3 | **Plan Resolution + Dependency Resolver** | ✓ | [world_system/wes/plan_resolution.py](Game-1-modular/world_system/wes/plan_resolution.py), [dependency_resolver.py](Game-1-modular/world_system/wes/dependency_resolver.py) | Dep graph traversal. |
| 8.4 | **Request Layer** | ✓ | [world_system/wes/request_layer.py](Game-1-modular/world_system/wes/request_layer.py) | Code-driven single-step orphan resolution. Bypasses planner+hub for refinement passes. |
| 8.5 | **LLM Execution Planner** | ✓ | [world_system/wes/llm_tiers/llm_execution_planner.py](Game-1-modular/world_system/wes/llm_tiers/llm_execution_planner.py) | Tier 1: turns bundle into ExecutorSpec plan. Honors `adjusted_instructions` for supervisor reruns. |
| 8.6 | **LLM Execution Hub** | ✓ | [world_system/wes/llm_tiers/llm_execution_hub.py](Game-1-modular/world_system/wes/llm_tiers/llm_execution_hub.py) | Tier 2: per-tool hub (8 disciplines) refines per-tool prompts. Bundle propagation full per Phase 1. |
| 8.7 | **LLM Executor Tool** | ✓ | [world_system/wes/llm_tiers/llm_executor_tool.py](Game-1-modular/world_system/wes/llm_tiers/llm_executor_tool.py) | Tier 3: actual content generation via BackendManager. |
| 8.8 | **LLM Supervisor** | ✓ | [world_system/wes/llm_tiers/llm_supervisor.py](Game-1-modular/world_system/wes/llm_tiers/llm_supervisor.py) | Verifies output; can request rerun w/ `adjusted_instructions`. 9 checks (incl. 3 behavior-causal). |
| 8.9 | **Prompt Assembler** | ✓ | [world_system/wes/llm_tiers/prompt_assembler.py](Game-1-modular/world_system/wes/llm_tiers/prompt_assembler.py) | Modular block assembly (14 designer-tunable blocks). |
| 8.10 | **Tool Registry** | ✓ | [world_system/wes/tool_registry.py](Game-1-modular/world_system/wes/tool_registry.py) | wes_tool_chunks, hostiles, materials, nodes, npcs, quests, skills, titles. |
| 8.11 | **Stub Tiers (mock)** | ✓ | [world_system/wes/stub_tiers.py](Game-1-modular/world_system/wes/stub_tiers.py) | Test-only stubs. |
| 8.12 | **Async Runner** | ✓ | [world_system/wes/async_runner.py](Game-1-modular/world_system/wes/async_runner.py) | Background WES execution. |
| 8.13 | **Quest Reward Adapter** | ✓ | [world_system/wes/quest_reward_adapter.py](Game-1-modular/world_system/wes/quest_reward_adapter.py) | Adapts LLM-generated quest rewards to concrete grants. |
| 8.14 | **Verification** | ✓ | [world_system/wes/verification.py](Game-1-modular/world_system/wes/verification.py) | Schema + content sanity. |
| 8.15 | **XML Batch Parser** | ✓ | [world_system/wes/xml_batch_parser.py](Game-1-modular/world_system/wes/xml_batch_parser.py) | Parses multi-entity LLM responses. |
| 8.16 | **Supervisor Tap** | ✓ | [world_system/wes/supervisor_tap.py](Game-1-modular/world_system/wes/supervisor_tap.py) | Observability hook. |
| 8.17 | **Metrics** | ✓ | [world_system/wes/metrics.py](Game-1-modular/world_system/wes/metrics.py) | Token/time accounting. |
| 8.18 | **Runtime Observability + F12 Overlay** | ✓ | [world_system/wes/observability.py](Game-1-modular/world_system/wes/observability.py), [observability_overlay.py](Game-1-modular/world_system/wes/observability_overlay.py), [observability_runtime.py](Game-1-modular/world_system/wes/observability_runtime.py) | Ring-buffer of pipeline events + F12 toggle. |

---

## 9. Living World Infrastructure

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 9.1 | **Backend Manager** | ✓ | [world_system/living_world/backends/backend_manager.py](Game-1-modular/world_system/living_world/backends/backend_manager.py) (708 LOC) | Claude-only post v8.2. `WES_REQUIRE_REAL_LLM=1` strips Mock at runtime. |
| 9.2 | **LLM Dev Log** | ✓ | [world_system/living_world/backends/llm_dev_log.py](Game-1-modular/world_system/living_world/backends/llm_dev_log.py) | All BackendManager calls → `llm_debug_logs/wes_<session>.jsonl`. |
| 9.3 | **Context Bundle** | ✓ | [world_system/living_world/infra/context_bundle.py](Game-1-modular/world_system/living_world/infra/context_bundle.py) | Phase 1 contract for WMS→WNS→WES propagation. Includes BehaviorSignal. |
| 9.4 | **Graceful Degrade** | ✓ | [world_system/living_world/infra/graceful_degrade.py](Game-1-modular/world_system/living_world/infra/graceful_degrade.py) | Failure handling + logging to `llm_debug_logs/graceful_degrade/`. |
| 9.5 | **LLM Fixtures** | ✓ | [world_system/living_world/infra/llm_fixtures/](Game-1-modular/world_system/living_world/infra/llm_fixtures/) | Canned responses for tests. `WES_DISABLE_FIXTURES=1` bypasses for live playtest. |
| 9.6 | **Content Registry** | ✓ | [world_system/content_registry/content_registry.py](Game-1-modular/world_system/content_registry/content_registry.py) (579 LOC) | WES commits staged JSON here. **2026-06-09 verification:** instantiated at boot ([game_engine.py:4862](Game-1-modular/core/game_engine.py)) with the WNS save_dir, then passed to `WESOrchestrator.initialize`. The full pipeline (commit → reload → live registry) is covered end-to-end by [test_chunks_e2e.py](Game-1-modular/world_system/content_registry/tests/test_chunks_e2e.py). |
| 9.7 | **Database Reloader** | ✓ | [world_system/content_registry/database_reloader.py](Game-1-modular/world_system/content_registry/database_reloader.py) | EVT_DATABASE_RELOADED publish per tool. |
| 9.8 | **Xref Rules** | ✓ | [world_system/content_registry/xref_rules.py](Game-1-modular/world_system/content_registry/xref_rules.py) | Cross-reference validation. |
| 9.9 | **Orphan Detector** | ✓ | [world_system/content_registry/orphan_detector.py](Game-1-modular/world_system/content_registry/orphan_detector.py) | Detects dangling refs. |
| 9.10 | **Generated File Writer** | ✓ | [world_system/content_registry/generated_file_writer.py](Game-1-modular/world_system/content_registry/generated_file_writer.py) | Writes to `*-generated-*.JSON` files (never sacred). |
| 9.11 | **Registry Store** | ✓ | [world_system/content_registry/registry_store.py](Game-1-modular/world_system/content_registry/registry_store.py) | SQLite + JSON. |
| 9.12 | **Balance Validator (stub)** | ⊘ | [world_system/content_registry/balance_validator_stub.py](Game-1-modular/world_system/content_registry/balance_validator_stub.py) | Stub. Spec in `Development-Plan/SHARED_INFRASTRUCTURE.md`. |
| 9.13 | **Ecosystem Agent** | ◯ | [world_system/living_world/ecosystem/ecosystem_agent.py](Game-1-modular/world_system/living_world/ecosystem/ecosystem_agent.py) | Tool interface — but returns **hardcoded stub values** for resource counts. Not connected to live `WorldSystem` counts. |

---

## 10. LLM / ML Pipeline

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 10.1 | **Anthropic API integration** | ✓ | [systems/llm_item_generator.py](Game-1-modular/systems/llm_item_generator.py) (Invented Items), [world_system/living_world/backends/backend_manager.py](Game-1-modular/world_system/living_world/backends/backend_manager.py) (WES/WNS) | `claude-sonnet-4-20250514` default for invented items; backend config drives WES. |
| 10.2 | **ANTHROPIC_API_KEY** | Env-set | shell env / `.env` | Confirmed set. **Treat as secret** — was visible in a prior terminal echo; rotation recommended. |
| 10.3 | **CNN classifiers (TensorFlow/Keras)** | ✓ | `Scaled JSON Development/crafting_classifier_models/smithing/smithing_best.keras`, `adornment/adornment_best.keras` | 36×36×3 (smithing) and 56×56×3 (adornment) RGB. Warmup at startup. |
| 10.4 | **LightGBM classifiers** | ◐ | `crafting_classifier_models/{alchemy,refining,engineering}/*_model.txt` | Models present. Extractor `.pkl` files MISSING but inline `LightGBMFeatureExtractor` is used instead — works. |
| 10.5 | **Few-shot prompts (Invented Items)** | ✓ | `Scaled JSON Development/LLM Training Data/Fewshot_llm/` | System prompts per discipline + examples. |
| 10.6 | **WES fixture library** | ✓ | [world_system/living_world/infra/llm_fixtures/](Game-1-modular/world_system/living_world/infra/llm_fixtures/) | Canned responses; disabled with `WES_DISABLE_FIXTURES=1`. |
| 10.7 | **Real-LLM smoketest** | ✓ | [tools/wes_real_llm_smoketest.py](Game-1-modular/tools/wes_real_llm_smoketest.py) | Pre-playtest probe; resolves chain + runs one generate. |
| 10.8 | **Real-LLM safety gate** | ✓ | env `WES_REQUIRE_REAL_LLM=1` | Strips MockBackend from chain at `generate()` time. |
| 10.9 | **LLM Dev Log reader** | ✓ | [world_system/living_world/backends/llm_dev_log.py:tail_recent](Game-1-modular/world_system/living_world/backends/llm_dev_log.py) | Feeds F12 overlay + Prompt Studio Simulator. |
| 10.10 | **Ollama (local inference)** | ◯ | `backend-config.json:enabled: false` | Disabled in current Claude-only posture. Re-enableable via config. |

---

## 11. Save / Load

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 11.1 | **Save Manager (v3 format)** | ✓ | [systems/save_manager.py](Game-1-modular/systems/save_manager.py) (634 LOC) | Character + world (seed only) + chunks (per-file) + quests + NPCs + factions + dungeon + map waypoints. v1/v2 backwards compat. |
| 11.2 | **Chunk-file save** | ✓ | [systems/world_system.py:_save_chunk_to_file](Game-1-modular/systems/world_system.py), [systems/chunk.py:get_save_data](Game-1-modular/systems/chunk.py) | Per-chunk JSON files. `template_locked` flag persisted. |
| 11.3 | **Geographic-map cache** | ✓ | `saves/world_map_seed_<seed>.gz` | Pickled `WorldMap`. Saved on first gen; loaded if seed matches. 12.9s→1.1s confirmed. |
| 11.4 | **Default save creator** | ✓ | [save_system/create_default_save.py](Game-1-modular/save_system/create_default_save.py) | Used by "Load Default Save" menu option. |
| 11.5 | **Faction state persistence** | ✓ | [world_system/living_world/factions/schema.py](Game-1-modular/world_system/living_world/factions/schema.py) (SQLite) | Auto-created at save path. |
| 11.6 | **WMS state persistence** | ✓ | SQLite tables in `saves/<save>/` | Event store, stat store, layer stores. |
| 11.7 | **Mid-dungeon save** | ✗ | — | Save while in dungeon → instance lost on load. Designed-out, but a visible gap. |
| 11.8 | **Invented recipe persistence** | ✓ | [systems/save_manager.py](Game-1-modular/systems/save_manager.py), [core/game_engine.py:register_saved_invented_recipes](Game-1-modular/core/game_engine.py) | Roundtrip works. |

---

## 12. UI & Input

| # | System | Status | Key files | Notes |
|---|---|---|---|---|
| 12.1 | **Input handling (40+ keybindings)** | ✓ | [core/game_engine.py](Game-1-modular/core/game_engine.py) | WASD movement, hotbar 1-5, X block, F1-F12 debug, ESC pause menu. |
| 12.2 | **Crafting UI (per discipline)** | ✓ | [rendering/renderer.py](Game-1-modular/rendering/renderer.py): `render_smithing_grid`, `render_refining_hub`, `render_alchemy_sequence`, `render_engineering_slots`, `render_adornment_pattern` | 5 grid-style renderers. |
| 12.3 | **Inventory UI** | ✓ | `renderer.render_inventory_ui` | 30 slots, drag/drop. |
| 12.4 | **Equipment UI** | ✓ | `renderer.render_equipment_ui` | 8 slots. |
| 12.5 | **Stats UI** | ✓ | `renderer.render_stats_ui` | C key. |
| 12.6 | **Skills UI + Hotbar** | ✓ | `renderer.render_skills_menu_ui` + `render_skill_hotbar` | |
| 12.7 | **NPC Dialogue UI** | ✓ | `renderer.render_npc_dialogue_ui` | Static dialogue path. Risk: doesn't invoke NPC Agent for dynamic dialogue. |
| 12.8 | **Map UI + Waypoint placement** | ✓ | `renderer.render_map_ui` | Drag, zoom, waypoint placement at `P`. |
| 12.9 | **Class Selection UI** | ✓ | `renderer.render_class_selection_ui` | On new character creation. |
| 12.10 | **Enchantment Selection UI** | ✓ | `renderer.render_enchantment_selection_ui` | Pre-enchanting flow. |
| 12.11 | **Dungeon Chest UI** | ✓ | `renderer.render_dungeon_chest_ui` | Post-wave loot. |
| 12.12 | **Spawn Chest UI** | ✓ | spawn storage chest | Player-placed item storage. |
| 12.13 | **Encyclopedia UI** | ✓ | `renderer.render_encyclopedia_ui` | Read-only viewer. |
| 12.14 | **F12 Observability Overlay** | ✓ | [world_system/wes/observability_overlay.py](Game-1-modular/world_system/wes/observability_overlay.py) | WMS/WNS/WES/Registry/Reload last 15 events + counters. |
| 12.15 | **Pause menu** | ✓ | `renderer.render_pause_menu` | 2026-06-05. |
| 12.16 | **Start menu** | ✓ | `renderer.render_start_menu` | Four options. |
| 12.17 | **Loading screen** | ✓ | `renderer.render_loading_screen` | 2026-06-05. |
| 12.18 | **Tooltip system** | ✓ | `renderer.render_pending_tooltip` | Deferred-rendering for top z-order. |
| 12.19 | **Notifications** | ✓ | `renderer.render_notifications` | Colored toasts. |
| 12.20 | **LLM Loading Indicator** | ✓ | `renderer.render_loading_indicator` | Spinner during async LLM/classifier work. |

---

## 13. Dev Tools

Designer / developer surface — not part of gameplay, but critical for tuning.

| # | Tool | Status | File | Purpose |
|---|---|---|---|---|
| 13.1 | **Prompt Studio** | ✓ | [tools/prompt_studio_main.py](Game-1-modular/tools/prompt_studio_main.py) | Themed Tk multi-panel editor for all 33 LLM tasks. Browser/Editor/Assembly/Simulator/Schema/Coverage. |
| 13.2 | **WES Real-LLM Smoketest** | ✓ | [tools/wes_real_llm_smoketest.py](Game-1-modular/tools/wes_real_llm_smoketest.py) | Pre-playtest probe. |
| 13.3 | **WMS Simulator** | ✓ | [tools/simulate_world_memory.py](Game-1-modular/tools/simulate_world_memory.py) | Replays events. |
| 13.4 | **Smithing Grid Designer** | ✓ | [tools/smithing-grid-designer.py](Game-1-modular/tools/smithing-grid-designer.py) | Recipe authoring. |
| 13.5 | **Enchanting Pattern Designer** | ✓ | [tools/enchanting-pattern-designer.py](Game-1-modular/tools/enchanting-pattern-designer.py) | Vertex layout authoring. |
| 13.6 | **Stat Catalog** | ✓ | [tools/stat_catalog.py](Game-1-modular/tools/stat_catalog.py) | Exports StatTracker dimensional manifest. |
| 13.7 | **Stat Schema Generator** | ✓ | [tools/generate_stat_schema.py](Game-1-modular/tools/generate_stat_schema.py) | StatStore SQL schema. |
| 13.8 | **Tag Collector** | ✓ | [tools/tag_collector.py](Game-1-modular/tools/tag_collector.py) | Sweep code for tag refs. |
| 13.9 | **Update Manager** | ✓ | [tools/update_manager.py](Game-1-modular/tools/update_manager.py) | Update-N package manifest. |
| 13.10 | **Update Catalog** | ✓ | [tools/update_catalog.py](Game-1-modular/tools/update_catalog.py) | List update packages. |
| 13.11 | **Deploy Update** | ✓ | [tools/deploy_update.py](Game-1-modular/tools/deploy_update.py) | Stage Update-N JSON. |
| 13.12 | **Icon Audit** | ✓ | [tools/audit_icon_coverage.py](Game-1-modular/tools/audit_icon_coverage.py) | Verifies icons for items/skills. |
| 13.13 | **Placeholder Icon Generator** | ✓ | [tools/create_placeholder_icons.py](Game-1-modular/tools/create_placeholder_icons.py), [create_placeholder_icons_simple.py](Game-1-modular/tools/create_placeholder_icons_simple.py) | Auto-generate placeholder PNGs. |
| 13.14 | **Prompt Editor (legacy)** | ✓ | [tools/prompt_editor.py](Game-1-modular/tools/prompt_editor.py) | Pre-Prompt-Studio editor. |

---

## 14. Content updates (Update-N)

| # | Update | Status | Files | Notes |
|---|---|---|---|---|
| 14.1 | **Update-N system / loader** | ✓ | [data/databases/update_loader.py](Game-1-modular/data/databases/update_loader.py), [tools/update_manager.py](Game-1-modular/tools/update_manager.py) | `load_all_updates(get_resource_path(""))` called at [game_engine.py:149-150](Game-1-modular/core/game_engine.py#L149) on boot. Scans installed updates from `updates_manifest.json` and auto-extends all databases (equipment, skills, materials, titles, skill-unlocks) without modifying core loader code. |
| 14.2 | **Update-1** (Tag system test content) | ✓ | `Update-1/items-testing-integration.JSON`, `skills-testing-integration.JSON`, `hostiles-testing-integration.JSON` | 5 weapons + 6 skills + 3 boss enemies. Auto-loaded via Update-N loader at boot. |
| 14.3 | **Update-2** (Fishing) | ✓ | `Update-2/skills-fishing.JSON`, `titles-fishing.JSON`, `crafting-stations-update2.JSON`, `skill-unlocks-fishing.JSON` | Skills + titles + stations + skill-unlocks all auto-loaded at boot. Fishing minigame wired separately via resource interaction (§3.9). Fishing titles untested. |

---

## 15. Audio — NOT IMPLEMENTED

Confirmed no `pygame.mixer` usage anywhere in `core/`, `rendering/`, `systems/`. No audio assets in `assets/`. No music, sound effects, ambient audio in any current shipped feature.

This is a confirmed scope gap. Not blocking gameplay but worth tracking explicitly.

---

## Cross-cutting integration risks

These are risks that span multiple systems and won't be caught by per-system testing.

1. **Silent-fallback patterns**: `try/except: pass` is widespread in NPC dialogue, save/load, faction-state save, LLM backend, classifier validation. Any silently-caught exception leaves the system in degraded state with no user-visible signal. Recommend a global "silent error counter" in F12 overlay.

2. **The renderer god-class**: 8K lines, 98 methods, tightly coupled to `game_engine`. Any UI change risks cross-feature regression.

3. **The game-engine god-class**: 11K lines holds references to every subsystem. Any new wiring risks breaking unrelated paths (e.g. minigame regression had nothing to do with the boot-flow change but felt like it might).

4. **Two parallel damage pipelines**: tag-based + traditional. Risk of divergent behavior.

5. **JSON-driven config without validation**: missing keys silently fall back to hardcoded defaults across MANY systems. There's no schema validation at boot.

6. **Database loader naming inconsistency**: most use `load_from_files()`; EquipmentDatabase uses `load_from_file()` (singular). Minor but flags potential silent gaps.

7. **NPC dialogue + faction**: faction system perfectly records affinity but dialogue never queries it. Player will see no in-game evidence of reputation despite SQL rows updating.

8. **NPC Agent System**: code is built, tested, ready — but not invoked. Activating it is a one-call hook.

9. **Quest UX gap**: in-game quest tracking has no waypoint, no abandon, no log reminder. Players can lose track of quests with no recovery.

10. **Update-N runtime loading**: agent audit suggests partial. Means a designer adding content via Update-N may not see it appear without manual JSON copy. Needs verification.

---

## Work order (owner-confirmed 2026-06-05)

After owner pushback, the actual priorities are:

### 1. WMS Layers 5-7 end-to-end verification (HIGHEST)

Managers exist and are initialized at boot ([world_memory_system.py:226-266](Game-1-modular/world_system/world_memory/world_memory_system.py)). What needs verification:

- Do summarizers actually fire on the right triggers in a real gameplay session, or do they only initialize and then stay silent?
- Are summary outputs being written to their respective stores and readable downstream by WNS context builder?
- Is the Layer 4 → 5 → 6 → 7 cascade actually flowing data, or are there hidden gaps where one layer never feeds the next?
- Are the trigger conditions reachable in the kind of play session the owner will actually run (or are thresholds tuned for much longer playtests)?

Approach: read each layer manager's summarize/write entry points, trace what should call them, check whether those callers actually exist in the runtime path. Report a layer-by-layer verdict.

### 2. NPC Agent System hookup

[world_system/living_world/npc/npc_agent.py](Game-1-modular/world_system/living_world/npc/npc_agent.py) + [npc_memory.py](Game-1-modular/world_system/living_world/npc/npc_memory.py) — ~665 LOC, ready, never called. Current dialogue path uses `NPC.get_next_dialogue()` (static speechbank). Hookup: replace the dialogue call site in `game_engine.handle_npc_interaction` with a call to `npc_agent_system.generate_dialogue(npc, context)` that pulls context from WMS + faction system. Falls back to static speechbank if backend unavailable.

### 3. Faction system hookup (bundled with #2)

The hookup is **the same feature** as the NPC Agent System wiring. The agent's dialogue-generation prompt needs faction context: NPC's primary faction, player's affinity toward that faction, the locality's baseline attitude. [world_system/living_world/factions/dialogue_helper.py](Game-1-modular/world_system/living_world/factions/dialogue_helper.py) already returns affinity-modulated context — wire it into the NPC agent's context builder.

### 4. Content Registry proper construction

[world_system/content_registry/content_registry.py](Game-1-modular/world_system/content_registry/content_registry.py) — exists, used by smoketest + tests. Needs to be instantiated at `game_engine.__init__` and wired so the WES → commit → reload pipeline actually flows live content into the game. Without this, anything WES generates during play vanishes.

---

The catalog now reflects this work order. Next session work starts with item #1 unless redirected.

---

## Maintenance notes

This catalog is a **baseline snapshot** as of 2026-06-05.

To keep it useful:
- When you add or substantially modify a system, add/update its row in the right category.
- When a row marked ◯ "DESIGNED-NOT-WIRED" becomes wired, change status to ✓ and remove from "Critical findings".
- When you discover a silent gap during playtest, add it to "Critical findings" with a row pointer.

This document is intended to make any future "what's the state of the game" question answerable by a 5-minute read.
