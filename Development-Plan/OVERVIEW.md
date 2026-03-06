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

## Current State Summary

| System | State | Key Files | LOC |
|--------|-------|-----------|-----|
| Combat | Click-to-attack, instant damage, circular collision | `Combat/combat_manager.py`, `enemy.py` | 2,527 |
| Rendering | Static sprites, no animation, single Renderer class | `rendering/renderer.py` | 2,782 |
| Enemy AI | FSM (patrol/chase/attack/retreat), fixed patterns | `Combat/enemy.py` | 867 |
| World | Infinite chunks, static resource nodes, seed-based | `systems/world_system.py` | ~1,200 |
| NPCs | Static quest dispensers, JSON dialogue, no memory | `systems/npc_system.py`, `quest_system.py` | ~800 |
| AI/ML | LLM item gen (Claude API), CNN/LightGBM classifiers | `systems/llm_item_generator.py`, `crafting_classifier.py` | 2,649 |
| Assets | 3,744 PNGs, all enemy sprites 1024x1024, no sprite sheets | `assets/` | — |

### Technical Constraints
- **Engine**: Pygame (SDL2 wrapper) — no built-in animation, physics, or scene graph
- **Resolution**: 1600x900 base, 32px tiles, 60 FPS target
- **Architecture**: Monolithic GameEngine (10K lines), singleton databases, component-based Character
- **Threading**: Background threading exists for LLM calls — pattern available for AI agents

---

## Dependency Graph

```
PART 1: Combat Visuals (independent — start immediately)
  Phase 1.1: Animation Framework ──────────────────────┐
  Phase 1.2: Attack State Machine ─────────────────────┤
  Phase 1.3: Hitbox & Hurtbox System ──────────────────┤──→ Phase 1.7: Integration & Polish
  Phase 1.4: Projectile System ────────────────────────┤
  Phase 1.5: Player Actions (dodge, combo) ────────────┤
  Phase 1.6: Enemy Tier Scaling & Patterns ────────────┘

PART 2: Living World (starts after Phase 1.3 complete)
  Phase 2.1: Memory Layer (FOUNDATION) ────────────────┐
  Phase 2.2: Model Backend Abstraction ────────────────┤
  Phase 2.3: NPC Agent System ─────────────────────────┤──→ Phase 2.7: Quest Generator
  Phase 2.4: Faction System ───────────────────────────┤
  Phase 2.5: Ecosystem Model ──────────────────────────┤──→ Phase 2.6: World Events

PART 3: Player Intelligence (starts after Phase 2.1)
  Phase 3.1: Behavior Classifier ──────────────────────┐
  Phase 3.2: Preference Model ─────────────────────────┤──→ Feeds all generators
  Phase 3.3: Player Arc Tracker ───────────────────────┘
```

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

## File Organization (New)

```
Game-1-modular/
├── combat/                          # Replaces Combat/ (lowercase, new structure)
│   ├── combat_manager.py            # Refactored — uses new systems
│   ├── enemy.py                     # Refactored — tier scaling, attack patterns
│   ├── attack_state_machine.py      # NEW: Phased attack states
│   ├── hitbox_system.py             # NEW: Hitbox/hurtbox collision
│   ├── projectile_system.py         # NEW: Projectile entities
│   └── damage_numbers.py            # NEW: Floating damage text
├── animation/                       # NEW: Animation framework
│   ├── sprite_animation.py          # Frame-based animation player
│   ├── animation_manager.py         # Global animation registry & update
│   ├── animation_data.py            # Data classes for animation definitions
│   └── effects.py                   # Screen shake, flash, trails
├── ai/                              # NEW: Living World AI
│   ├── memory/                      # Memory layer
│   │   ├── event_store.py           # SQLite event storage
│   │   ├── event_schema.py          # Event type definitions
│   │   └── query.py                 # Agent query interface
│   ├── agents/                      # AI agents
│   │   ├── base_agent.py            # Agent base class
│   │   ├── npc_agent.py             # NPC dialogue & behavior
│   │   ├── quest_agent.py           # Quest generation
│   │   ├── ecosystem_agent.py       # Resource tracking
│   │   ├── event_agent.py           # World event triggers
│   │   └── faction_agent.py         # Faction relationships
│   ├── backends/                    # Model inference backends
│   │   ├── base_backend.py          # Abstract backend interface
│   │   ├── claude_backend.py        # Anthropic API (existing, refactored)
│   │   ├── ollama_backend.py        # Ollama local inference
│   │   ├── mock_backend.py          # Testing/fallback
│   │   └── backend_config.py        # Backend selection & config
│   └── player/                      # Player intelligence
│       ├── behavior_classifier.py   # Archetype classification
│       ├── preference_model.py      # Engagement tracking
│       └── arc_tracker.py           # Narrative stage tracking
├── events/                          # NEW: Event bus
│   ├── event_bus.py                 # Pub/sub event system
│   └── game_events.py              # Event type definitions
├── Animation-Data.JSON/             # NEW: Animation definitions
│   ├── attack-animations.json       # Weapon swing timing & hitboxes
│   ├── enemy-animations.json        # Enemy attack patterns
│   ├── effect-animations.json       # VFX timing
│   └── projectile-definitions.json  # Projectile properties
└── AI-Config.JSON/                  # NEW: AI agent configuration
    ├── npc-personalities.json       # NPC personality templates
    ├── faction-definitions.json     # Faction graph seed data
    ├── ecosystem-config.json        # Resource pressure thresholds
    └── event-triggers.json          # World event trigger conditions
```
