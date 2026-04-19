# Game-1 Development Plan — Living World & Visual Overhaul

**Created**: 2026-03-06
**Status**: Active Development (Python/Pygame — Unity migration paused indefinitely)
**Priority Order**: Combat Visuals → Living World AI → Player Intelligence

---

## Strategic Pivot

All development from this point forward targets the **2D Python/Pygame version**. The Unity/C# migration is paused. This plan replaces the migration plan as the active development roadmap.

---

## Plan Structure

This plan is split into focused documents for maintainability:

| Document | Priority | Description |
|----------|----------|-------------|
| [PART_1_COMBAT_VISUALS.md](PART_1_COMBAT_VISUALS.md) | **P1 — First** | Animation system, action combat, hitboxes, projectiles, enemy scaling, visual polish |
| [PART_2_LIVING_WORLD.md](PART_2_LIVING_WORLD.md) | **P2 — Second** | Memory layer, model backend, NPC agents, factions, ecosystem, world events, quests |
| [PART_3_PLAYER_INTELLIGENCE.md](PART_3_PLAYER_INTELLIGENCE.md) | **P3 — Last** | Behavior classifier, preference model, adaptive content |
| [SHARED_INFRASTRUCTURE.md](SHARED_INFRASTRUCTURE.md) | **Cross-cutting** | Balance validator, embedding model, event schema |

---

## Current State Summary (Updated 2026-03-29)

| System | State | Key Files | LOC |
|--------|-------|-----------|-----|
| Combat | **Action combat with hitboxes, projectiles, dodge, attack state machine** | `Combat/` (11 files) | ~5,562 |
| Animation | **Procedural animation framework, combat particles, weapon visuals** | `animation/` (7 files) | ~1,008 |
| Rendering | **Enhanced renderer with tag-driven VFX, damage numbers, death effects, visual config** | `rendering/` (5 files) | ~8,841 |
| Enemy AI | FSM (patrol/chase/attack/retreat), phased attacks with windup/active/recovery | `Combat/enemy.py`, `Combat/attack_profile_generator.py` | ~1,690 |
| World | Infinite chunks, static resource nodes, seed-based | `systems/world_system.py` | ~1,125 |
| NPCs | Static quest dispensers, JSON dialogue, no memory | `systems/npc_system.py`, `quest_system.py` | ~378 |
| AI/ML | LLM item gen (Claude API), CNN/LightGBM classifiers | `systems/llm_item_generator.py`, `crafting_classifier.py` | ~2,811 |
| Events | **GameEventBus pub/sub connecting all systems** | `events/event_bus.py` | ~194 |
| **World Memory** | **Layers 1-2 complete, 33 evaluators, tag library, 56 tests** | `world_system/` (71 files) | **~14,269** |
| **Living World** | **BackendManager, NPC agents, factions complete (Phase 2+); ecosystem as tool** | `world_system/living_world/` | ~2,079 |
| **StatTracker** | **65 SQL-backed recording methods wired into Character** | `entities/components/stat_tracker.py` | ~1,149 |
| Assets | 3,749 PNGs, all enemy sprites 1024x1024, no sprite sheets | `assets/` | — |

### Technical Constraints
- **Engine**: Pygame (SDL2 wrapper) — no built-in animation, physics, or scene graph
- **Resolution**: 1600x900 base, 32px tiles, 60 FPS target
- **Architecture**: Monolithic GameEngine (~10,809 lines), singleton databases, component-based Character
- **Threading**: Background threading exists for LLM calls — pattern available for AI agents

---

## Dependency Graph

```
PART 1: Combat Visuals
  Phase 1.1: Animation Framework ──────────────────────┐  ✅ COMPLETE (animation/ module)
  Phase 1.2: Attack State Machine ─────────────────────┤  ✅ COMPLETE (Combat/attack_state_machine.py)
  Phase 1.3: Hitbox & Hurtbox System ──────────────────┤  ✅ COMPLETE (Combat/hitbox_system.py)
  Phase 1.4: Projectile System ────────────────────────┤  ✅ COMPLETE (Combat/projectile_system.py)
  Phase 1.5: Player Actions (dodge, combo) ────────────┤  ✅ COMPLETE (Combat/player_actions.py)
  Phase 1.6: Enemy Tier Scaling & Patterns ────────────┤  ✅ COMPLETE (Combat/attack_profile_generator.py)
  Phase 1.7: Integration & Polish ─────────────────────┘  ⚠️ NEEDS OVERHAUL (visual quality insufficient — new plan needed)

PART 2: Living World (starts after Phase 1.3 complete)
  Phase 2.1: Memory Layer (FOUNDATION) ────────────────┐  ✅ COMPLETE (world_system/world_memory/ — Layers 1-2, 33 evaluators)
  Phase 2.2: Model Backend Abstraction ────────────────┤  ✅ COMPLETE (world_system/living_world/backends/backend_manager.py)
  Phase 2.3: NPC Agent System ─────────────────────────┤  ⚠️ SCAFFOLDED (npc_agent.py exists, needs game integration)
  Phase 2.4: Faction System ───────────────────────────┤  ✅ PHASE 2+ COMPLETE (Phase 2, 3A/B/C done; stylization pending)
  Phase 2.5: World Event System ───────────────────────┼──→ Phase 2.6: Quest Generator  ⚠️ SCAFFOLDED
  Phase 2.6: Ecosystem as Tool ────────────────────────┘  (queries only — no separate agent)

PART 3: Player Intelligence (starts after Phase 2.1)
  Phase 3.1: Behavior Classifier ──────────────────────┐
  Phase 3.2: Preference Model ─────────────────────────┤──→ Feeds all generators
  Phase 3.3: Player Arc Tracker ───────────────────────┘
```

> **Note (2026-03-09)**: Part 1 Phases 1.1–1.6 are structurally complete — the systems exist and function. However, the **visual quality** of combat animations needs a grand overhaul. The current implementation uses procedural geometric shapes (arcs, polygons, lines) rather than true sprite-based animations. A new visual overhaul plan is needed to replace these with proper animated sprites and high-quality VFX.

---

## Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| New files, don't gut existing | Combat overhaul lives in new modules; existing combat_manager.py refactored incrementally |
| JSON-driven animation data | Animation timing, hitbox data, attack patterns all in JSON — consistent with project philosophy |
| Local models preferred for AI | User handles fine-tuning; infrastructure must support Ollama/llama.cpp/local inference alongside Claude API |
| SQLite for memory layer | Structured queries needed for agent retrieval; JSON files too slow for real-time lookups |
| Event-driven architecture | New `GameEventBus` decouples systems; memory layer observes all events passively |
| Phased combat states | IDLE→WINDUP→ACTIVE→RECOVERY replaces instant damage; enables animation-driven gameplay |

---

## File Organization (Actual — Updated 2026-03-29)

> **Note**: The original plan proposed `ai/`, `combat/` (lowercase), `Animation-Data.JSON/`, and `AI-Config.JSON/` directories. The actual implementation diverged — Living World code lives in `world_system/`, combat stayed in `Combat/` (uppercase), and config JSONs live in `world_system/config/`.

```
Game-1-modular/
├── Combat/                          # Expanded from 3 → 11 files (uppercase retained)
│   ├── combat_manager.py            # CombatManager (2,317 lines)
│   ├── enemy.py                     # Enemy, EnemyDatabase (1,348 lines)
│   ├── attack_state_machine.py      # Phased attack states
│   ├── hitbox_system.py             # Hitbox/hurtbox collision
│   ├── projectile_system.py         # Projectile entities
│   ├── attack_profile_generator.py  # Tier-based attack patterns
│   ├── combat_data_loader.py        # Combat data loading
│   ├── player_actions.py            # Dodge, combo actions
│   ├── screen_effects.py            # Screen shake, flash
│   └── combat_event.py              # Combat event types
├── animation/                       # Animation framework (7 files, 1,008 LOC)
│   ├── animation_manager.py         # Global animation registry & update
│   ├── sprite_animation.py          # Frame-based animation player
│   ├── animation_data.py            # Data classes for animation definitions
│   ├── procedural.py                # Procedural animation generation
│   ├── weapon_visuals.py            # Weapon swing visuals
│   └── combat_particles.py          # Combat particle effects
├── world_system/                    # Living World + World Memory (71 files, 14,269 LOC)
│   ├── world_memory/                # Core WMS engine
│   │   ├── world_memory_system.py   # Facade coordinating all subsystems (449 lines)
│   │   ├── stat_store.py            # SQL-backed hierarchical stats (327 lines)
│   │   ├── event_store.py           # 20 SQL tables (1,140 lines)
│   │   ├── event_recorder.py        # Bus→SQLite bridge (481 lines)
│   │   ├── trigger_manager.py       # Threshold-based triggers (194 lines)
│   │   ├── tag_library.py           # 65-category taxonomy (559 lines)
│   │   ├── tag_assignment.py        # Layer 1→7 tag engine (410 lines)
│   │   ├── evaluators/              # 33 Layer 2 evaluators (1,700+ lines)
│   │   └── (+ query, interpreter, geographic_registry, entity_registry,
│   │        daily_ledger, time_envelope, retention, layer_store, etc.)
│   ├── living_world/                # Consumer systems (NOT part of WMS)
│   │   ├── backends/                # BackendManager — LLM abstraction (553 lines)
│   │   ├── npc/                     # NPCAgentSystem + NPCMemory (665 lines)
│   │   ├── factions/                # FactionSystem Phase 2+ (1,300 LOC, 50 tests)
│   │   └── ecosystem/               # Tool interface for resource queries (no state)
│   ├── config/                      # 7 JSON configs
│   │   ├── memory-config.json       # Event types, evaluator config, retention rules
│   │   ├── backend-config.json      # LLM backend routing
│   │   ├── geographic-map.json      # World region hierarchy
│   │   ├── npc-personalities.json   # Per-NPC personality profiles
│   │   ├── faction-definitions.json # Faction list, rep ranges
│   │   ├── ecosystem-config.json    # Resource tiers, depletion thresholds
│   │   └── layer1-stat-tags.json    # 374 stat patterns with tag mappings
│   ├── tests/                       # 56 passing tests
│   └── docs/                        # WORLD_MEMORY_SYSTEM.md (canonical design doc)
├── events/                          # Event bus (2 files, 194 LOC)
│   └── event_bus.py                 # GameEventBus pub/sub
├── entities/components/
│   └── stat_tracker.py              # 65 record_* methods writing to StatStore (1,149 lines)
└── Definitions.JSON/
    └── visual-config.JSON           # Visual effect configuration
```

### Player Intelligence (Part 3 — NOT YET STARTED)
The `ai/player/` directory from the original plan does not exist. Behavior classifier, preference model, and arc tracker remain future work.
