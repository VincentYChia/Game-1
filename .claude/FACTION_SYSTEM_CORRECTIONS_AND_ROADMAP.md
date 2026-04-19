# Faction System: Design Corrections & Roadmap Audit

**Date**: 2026-04-17
**Purpose**: Record what was corrected from initial brainstorm, and re-audit the phase roadmap

---

## What I Got Wrong (Initial Brainstorm)

| Mistake | Why Wrong | Correction |
|---------|----------|-----------|
| **Multi-axis affinity per tag** | Overcomplex; LLMs don't need it. | Single affinity per tag. Nuance comes from quest outcomes, not tagging. |
| **Global tag-relationship matrix** | Not needed. | Affinity is per-NPC. Global defaults exist at hierarchy tiers. |
| **NPC creation reads WMS events** | Locks NPCs in time. Defeats "stable profile" goal. | NPC creation reads ONLY: role, location, affinity defaults. Nothing recent. |
| **NPC creation reads quest hooks** | Same problem; time-locks NPC. | Quests are a SECOND PASS (interaction), not creation. |
| **Affinity as ripple through relationship matrix** | Over-engineered. | Affinity is direct math: quest delta + player traits. No matrix. |
| **Per-NPC affinity for every tag** | Storage bloat; N×M explosion. | Only store EXCEPTIONS. Inherit defaults from hierarchy. |
| **Affinity defaults auto-computed by decay** | Unnecessary; just use authored defaults. | Defaults are config entries; no computation. |
| **Faction-reputation-evaluator as the main event mechanism** | Backwards. | WMS captures QUEST_COMPLETED; Evaluator tags it. Affinity is direct math. |
| **Separation of NPC creation from "coming alive"** | Confused two things. | Creation = stable profile. "Coming alive" = interaction enriches the profile. Same NPC, not different objects. |
| **Locations have full faction-context schemas** | Too much work. World gen not that advanced yet. | Locations are prompts hints (type, name). Full schemas are future work. |

---

## What Was Right (and Confirmed)

✅ Tag-based system (not faction objects)  
✅ Belonging ≠ Affinity (crucial distinction)  
✅ Narrative-first NPC creation  
✅ Single affinity value per tag  
✅ Significance buckets (scale-agnostic terms)  
✅ Players have NO belonging (only affinity)  
✅ TagRegistry singleton  
✅ Archetype library for guidance  
✅ Quest completion as an affinity event  
✅ WMS Layer 2 observes QUEST_COMPLETED  
✅ Affinity hierarchy (world → nation → region → … → locality)  

---

## Roadmap Re-Audit

### Phase 0 — Bucket Terms Decision ✅
- **Blocker**: User provides final 10 bucket terms
- **Output**: Named buckets (float → name mapping)
- **Effort**: Minimal; naming task

### Phase 1 — Tag Registry, Archetype Library, Affinity Defaults ✅
- **Inputs**: None (bootstrap phase)
- **Outputs**:
  - `tag-registry.json` — all known tags, appearance counts, gloss
  - `faction-archetypes.json` — role → narrative seed + suggested tag spread
  - `affinity-defaults.json` — world + nation + region + province + district + locality defaults for all tags
  - `TagRegistry` singleton class
  - `AffinityDefaults` hierarchy lookup class
- **Why first**: Everything downstream depends on these vocabularies
- **Missing before**: Affinity default config was not in my original roadmap

### Phase 2 — Data Models (NPC + Player, Save/Load) ✅
- **Outputs**:
  - NPCFactionProfile dataclass (narrative, belonging, affinity_exceptions, affinity_overrides)
  - PlayerFactionProfile dataclass (affinity, traits)
  - Significance bucket enum/constants
  - FactionSystem rewritten as tag-indexed store
  - Save/load integration for both
- **Depends on**: Phase 1 (bucket terms, tag registry API)
- **Missing before**: affinity_overrides field (runtime changes)

### Phase 3 — NPC Creation Pipeline ✅
- **Outputs**:
  - LLM prompt template (role + location + affinity defaults → narrative + belonging + affinity exceptions)
  - NPC creation function that calls LLM
  - Input validation (role, location must exist)
  - Output validation (tags exist in registry, narrative is non-empty)
- **Depends on**: Phase 1, Phase 2
- **Missing before**: Explicit "don't read WMS" constraint

### Phase 4 — Quest System (Core, Not Deferred) ✅
- **Outputs**:
  - QuestDatabase singleton (load quests-1.JSON + custom quests)
  - QuestDefinition schema (id, title, description, npc_id, faction_rewards, location, type)
  - NPC.get_available_quests(player_id) → filters by player affinity + faction requirements
  - QUEST_COMPLETED event type + payload
  - Quest completion handler that applies affinity deltas
- **Depends on**: Phase 1, Phase 2
- **Why Phase 4, not deferred**: This is THE mechanism for affinity changes. Everything else waits on it.
- **Missing before**: This was Phase 6 before. Needs to move earlier.

### Phase 5 — WMS Evaluator (Faction → Layer 2) ✅
- **Outputs**:
  - QUEST_COMPLETED + FACTION_REP_CHANGED event types registered in event_schema.py
  - BUS_TO_MEMORY_TYPE mappings for both
  - FactionReputationEvaluator (Layer 2) that observes QUEST_COMPLETED and FACTION_REP_CHANGED
  - Rich tags: domain:faction, action:quest_completed, rep_direction, rep_magnitude, etc.
  - memory-config.json entry for evaluator
  - Tests in test_new_evaluators.py
- **Depends on**: Phase 4 (QUEST_COMPLETED must exist)
- **Missing before**: Explicit mapping of QUEST_COMPLETED → WMS observation

### Phase 6 — NPC Agent Wiring + LLM Dialogue ✅
- **Outputs**:
  - Initialize NPCAgentSystem, BackendManager, NPCMemoryManager in game_engine._init_world_memory()
  - NPC.build_context() assembles: base profile + WMS recent events + NPC memory + available quests + player affinity
  - ACTION_INTERACT handler calls LLM (via NPCAgentSystem.generate_dialogue)
  - Output: quest offer + enriched narrative + dialogue context
  - Static fallback for nodes without LLM
  - Conversation manager can propose tag mutations post-dialogue (editorial rights)
- **Depends on**: Phase 1-5 (all building blocks must exist)
- **Missing before**: Explicit split between "NPC creation context" and "NPC interaction context"

### Phase 7 — UI & Polish (Deferred, Legitimate Phase 6+) ✅
- Faction reputation panel (per-tag affinity + bucket names)
- World Chronicle UI (WMS narrative drill-down)
- Territory map highlighting
- Quest log with faction rewards preview
- This is AFTER the core loop works

---

## Information Flow (Corrected)

```
┌──────────────────────────────────────────────────────────────────────┐
│                   NPC CREATION (One-Time)                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ Input: role, location_id, affinity_defaults_from_hierarchy           │
│                                                                      │
│ LLM Prompt:                                                          │
│ ├─ "You are creating an NPC for role {role} in {location}"          │
│ ├─ Read affinity defaults (world → nation → region → … → locality)  │
│ ├─ Output: narrative + belonging tags + affinity exceptions          │
│                                                                      │
│ Output: NPCFactionProfile (stable, saved)                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│              PLAYER INTERACTION (On Demand, Multi-Pass)               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ First-time encounter:                                                │
│ ├─ LLM reads: NPC profile + location + current time                  │
│ ├─ Output: basic greeting + quest offer                              │
│                                                                      │
│ Subsequent encounters:                                               │
│ ├─ LLM reads:                                                        │
│ │  ├─ NPC profile (narrative, belonging, affinity)                   │
│ │  ├─ WMS L2-L3 events (recent happenings in locality)              │
│ │  ├─ NPC memory (past interactions with this player)               │
│ │  ├─ Available quests (faction-gated by player affinity)           │
│ │  └─ Player affinity toward NPC's tags                             │
│ ├─ Output:                                                           │
│ │  ├─ Quest offer (enriched by context)                             │
│ │  ├─ Narrative (reflects current world state)                      │
│ │  └─ Dialogue context (who they think you are)                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                   QUEST COMPLETION (Event Loop)                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ Player completes quest → QUEST_COMPLETED event published             │
│                                                                      │
│ Affinity Deltas Applied:                                             │
│ ├─ For each tag in quest.faction_rewards:                            │
│ │  ├─ Apply delta to player_affinity[tag]                            │
│ │  ├─ Add player_traits bonuses                                      │
│ │  └─ Store in affinity_overrides                                    │
│ └─ NPC affinity toward player updated                                │
│                                                                      │
│ WMS Observation (same event):                                        │
│ ├─ FactionReputationEvaluator tags the event                         │
│ ├─ Emits rich tags (domain:faction, rep_direction, etc.)             │
│ └─ Cascades to L3-L7                                                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                  THE ECHO (Affinity Propagation)                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ World-Scale Affinity Shift (if major event):                         │
│ ├─ faction_system.set_nation_affinity_default(tag, delta)            │
│ ├─ All NPCs in that nation inherit new affinity (unless overridden)  │
│ └─ No NPC re-creation; just affinity defaults update                │
│                                                                      │
│ Next NPC Interaction:                                                │
│ ├─ Reads UPDATED affinity (both player-specific + world defaults)    │
│ ├─ Narrative reflects changed world                                  │
│ └─ Loop continues                                                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions (Not Changing)

1. **Affinity is hierarchical with exceptions** — defaults at each tier, only store divergences
2. **NPC creation is stable** — locked at creation time, not time-sensitive
3. **Affinity changes only at quest completion** — no intermediate updates
4. **Belonging is immutable** — tags that define NPC never change via gameplay
5. **Players have no belonging** — only affinity
6. **One LLM pass for NPC creation** — narrative + tags + affinity all in one output
7. **Quest system is core** — not deferred polish

---

## Remaining Questions / Deferred Decisions

### Location Metadata (Deferred)
- Current state: locations are prompt hints (name, type)
- Future state: locations have full narratives + faction context
- This requires advanced world generation
- **Action**: Record as future work; don't block current system

### Default NPC Generation (Deferred)
- Current state: all NPCs are blank slates (no archetype-driven procedural generation)
- Future state: archetype library drives procedural NPCs that "come alive" on first interaction
- This requires mature NPC creation + archetype expansion
- **Action**: Record as Phase X+; build key NPCs now with explicit authoring

### Balance Validation (Not Implemented)
- BalanceValidator is a spec in Development-Plan/SHARED_INFRASTRUCTURE.md
- Could validate quest rewards (affinity deltas, item rewards) against difficulty/tier
- Currently: trust author judgment
- **Action**: Not blocking; implement later if needed

---

## Test Coverage (By Phase)

| Phase | Test Focus |
|-------|-----------|
| 1 | TagRegistry: register, lookup, appearance counts; AffinityDefaults hierarchy lookup |
| 2 | NPCFactionProfile save/load; PlayerFactionProfile; significance buckets |
| 3 | NPC creation input validation; LLM prompt generation; output parsing |
| 4 | QuestDatabase load; NPC.get_available_quests filtering; QUEST_COMPLETED event structure |
| 5 | FactionReputationEvaluator tags; WMS cascade; event observation |
| 6 | NPCAgentSystem initialization; dialogue generation; context assembly |

---

## Implementation Order (Strict Dependency)

```
Phase 0 (bucket terms) ──→ Phase 1 ──→ Phase 2 ──→ Phase 3
                                  ↓                ↓
                            Phase 4 (Quest) ──→ Phase 5 (WMS)
                                               ↓
                                         Phase 6 (LLM Dialogue)
                                               ↓
                                         Phase 7 (UI)
```

Each phase unblocks the next. No shortcuts or parallel runs (except where independent).

