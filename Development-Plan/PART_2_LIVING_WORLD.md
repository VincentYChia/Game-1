# Part 2: Living World AI System

**Priority**: P2 — After Combat Visuals
**Goal**: Build the agent infrastructure that makes the world feel alive — NPCs with memory, factions with relationships, world events with consequence, and dynamic quests grounded in real game state.

---

## What Exists Today

| System | State | Key Files | Gap |
|--------|-------|-----------|-----|
| **Event Memory (Layers 1-2)** | ✅ COMPLETE | `world_system/world_memory/` (22 files, ~6,500 LOC) | Layers 3-7 schema exist, no data writes yet |
| **Backend Manager** | ✅ COMPLETE | `world_system/living_world/backends/backend_manager.py` (553 LOC) | Abstracts Ollama/Claude/Mock; production-ready |
| **NPC Agents** | ✅ SCAFFOLDED | `world_system/living_world/npc/npc_agent.py` (506 LOC) | Memory model, dialogue generation ready; needs game integration |
| **Faction System** | ✅ PHASE 2+ COMPLETE | `world_system/living_world/factions/` (1,300+ LOC, 50 tests) | Recording + retrieval + prompt UI wired; stylization pending |
| **GameEventBus** | ✅ COMPLETE | `events/event_bus.py` (194 LOC) | Pub/sub fully functional across all systems |
| **StatTracker** | ✅ COMPLETE | `entities/components/stat_tracker.py` (1,149 LOC) | 65 SQL-backed record methods, wired to Character |
| **Quest System** | ⚠️ SCAFFOLDED | `systems/quest_system.py` + `factions/quest_tool.py` | Hardcoded quest deltas exist; dynamic generation pending |
| **World Events** | ⚠️ SCAFFOLDED | Evaluators emit triggers; no firing system yet | Trigger config ready; execution pending |
| **Ecosystem** | ⚠️ FUTURE | `world_system/living_world/ecosystem/` | Resource tracking exists; integrates as tool call, not standalone agent |

**Key Realization**: Ecosystem is NOT a separate agent. It's a toolset (resource depletion tracking, biome pressure, spawn shifts) that the **Living World Coordinator** (the overarching LLM) calls as needed when generating quests, world events, and NPC reactions. This simplifies architecture and avoids redundant LLM calls.

---

## Phase 2.1: Event Memory Layer (FOUNDATION)

**Status**: ✅ COMPLETE (Layers 1-2)  
**Files**: `world_system/world_memory/` (22 files, ~6,500 LOC)  
**Tests**: 56 passing

This is the **absolute foundation** — without it, agents are stateless. The WMS captures every notable action in a structured, queryable format.

### Event Recording

The system captures:
- Combat: kills, damage, status effects
- Crafting: completed recipes, invented items, discoveries
- Gathering: resource harvested, node depleted
- Social: NPC spoken to, quest accepted/completed, faction reputation changed
- World: areas discovered, dungeons entered, bosses defeated
- Progression: level-ups, titles earned, skills learned

Example flow:
```
Player kills an enemy
  ↓ (game logic runs normally)
  ↓ GameEventBus.publish(WorldEvent(
      event_type="enemy_killed",
      actor_id="player_1",
      target_id="dire_wolf_42",
      location_chunk=(5, 7),
      tags=["combat", "tier_3", "enemy:wolf", "boss"],
      significance=0.85
    ))
  ↓ (all subscribers notified immediately)
  ├─ EventStore.record()        → persists to SQLite
  ├─ FactionSystem.on_event()   → checks if NPC faction enemies were killed
  ├─ EcosystemTool.check()      → updates wolf population pressure
  ├─ NPCAgentSystem.gossip()    → spreads word to nearby NPCs
  └─ TriggerManager.check()     → fires world events if thresholds crossed
```

### Save/Load Integration

Events are persisted independently in SQLite:
```
saves/
├── save_1.json              # Game state (inventory, position, etc.)
├── save_1_faction.db        # Faction affinity, NPC profiles
├── save_1_world_memory.db   # All recorded events, evaluator outputs
├── save_2.json
├── save_2_faction.db
└── save_2_world_memory.db
```

On load, simply reopen the .db files. On save, they auto-commit (no code needed).

---

## Phase 2.2: Model Backend Abstraction

**Status**: ✅ COMPLETE  
**Files**: `world_system/living_world/backends/` (3 files, 553 LOC)  
**Tested**: Fallback chain verified in integration tests

Abstraction layer supporting multiple LLM sources with graceful degradation.

### Key Interface

```python
class BackendManager:
    """Route generation tasks to the right backend with fallback chain"""
    
    def generate(self, task: str, system_prompt: str, user_prompt: str, 
                 temperature: float = 0.6, max_tokens: int = 2000) -> Tuple[str, Optional[Exception]]:
        """
        Route to configured backend for task type. Returns (text, error).
        If primary fails, tries fallback chain: ollama → claude → mock.
        """
```

### Backend Options

| Backend | Use Case | Production Ready | Speed | Cost |
|---------|----------|------------------|-------|------|
| **Ollama** (local llama.cpp) | Dialogue, quests, lore | ✅ Yes | ~500ms | Free |
| **Claude API** | High-quality narrative, validation | ✅ Yes | ~2s | ~$0.01/call |
| **MockBackend** | Testing, fallback | ✅ Yes | Instant | Free |

### Runtime Configuration

`world_system/config/backend-config.json`:
```json
{
  "backends": {
    "dialogue": "ollama",
    "quest_generation": "ollama",
    "narrative": "claude",
    "balance_check": "mock"
  },
  "fallback_order": ["ollama", "claude", "mock"],
  "ollama": {
    "model": "llama3.1:8b",
    "url": "http://localhost:11434"
  }
}
```

---

## Phase 2.3: NPC Agent System

**Status**: ⚠️ SCAFFOLDED (memory model complete, game integration pending)  
**Files**: `world_system/living_world/npc/` (2 files, 665 LOC)  
**Tests**: 6 passing

### NPC Memory Model

Each NPC remembers:
- **Relationship score** (-1.0 = hostile, 0 = neutral, 1.0 = devoted)
- **Interaction count** — how many times spoken to
- **Emotional state** — neutral, happy, angry, fearful, suspicious, grateful
- **Knowledge** — facts known (compressed one-liners, not full events)
- **Conversation summary** — bounded history of past conversations
- **Faction affiliations** — which factions define this NPC
- **Quest state** — active/completed quest tracking

### Dialogue Generation Example

```python
# Game code: NPC is approached for dialogue
result = npc_agent_system.generate_dialogue(
    npc_id="blacksmith_morven",
    player_input="Do you have any work for me?",
    character=player_character
)
# result.text = "Aye, if you can bring me some mithril, I've a commission waiting."
# result.emotion = "hopeful"
# result.relationship_delta = 0.0 (neutral interaction)
```

Under the hood:
1. Load NPC memory for "blacksmith_morven"
2. Build context:
   - NPC personality: "Gruff blacksmith, values craftsmanship, speaks bluntly"
   - NPC knowledge: "Player brought rare ore last week. Player has blacksmith title."
   - NPC faction: "guild:smiths (0.9 significance), nation:stormguard (0.3 significance)"
   - Player visible state: level, class, title, equipment
   - Recent interactions: last spoke 3 days ago, reputation increased 0.15
3. Call `BackendManager.generate(task="dialogue", ...)`
4. Update memory: interaction count++, relationship_score += delta, emotional state = result.emotion
5. Return response

### Gossip Propagation

When a notable event occurs (significance > threshold):
- **Immediate (same chunk)**: NPCs in the location hear instantly
- **Short delay (1 game-day)**: Nearby NPCs hear
- **Medium delay (3 days)**: NPCs in the same biome hear
- **Long delay (7 days)**: All NPCs eventually hear

Only compressed summaries propagate ("The player killed the dire wolf pack leader" not the full event), keeping context windows manageable for local models.

---

## Phase 2.4: Faction System

**Status**: ✅ PHASE 2+ COMPLETE (Phase 2, 3A, 3B, 3C)  
**Files**: `world_system/living_world/factions/` (9 files, 1,300 LOC, 50 tests)  
**Documentation**: `factions/PHASE_COMPLETE.md`

### What's Implemented

**Recording Layer** (Phase 2):
- SQLite sparse storage of NPC/player affinities (-100 to 100)
- NPC "belonging tags" (faction memberships with significance 0.0–1.0)
- Location affinity defaults (cultural baseline per address)
- Every `adjust_player_affinity()` publishes `FACTION_AFFINITY_CHANGED` on the bus

**Retrieval Layer** (Phase 3A):
- `assemble_dialogue_context()` builds full faction context for LLM dialogue
- Dialog system prompt now includes NPC affiliations + player standing with those factions
- Tested with real NPC profiles (guild:smiths, profession:guard, nation:stormguard, etc.)

**Quest Integration** (Phase 3B):
- `QuestGenerator` maps quest→outcome→affinity_delta (hardcoded for 3 bootstrap quests)
- `apply_quest_completion()` routes deltas through FactionSystem, triggering event bus

**Consolidation** (Phase 3C):
- `AffinityConsolidator.consolidate_player_standing()` returns top-5 affinities by absolute value
- Publishes `FACTION_AFFINITY_CONSOLIDATED` for Layer 2 narrative generation

**Prompt UI Integration** (this branch):
- 27 new prompt fragments added (5 real affinity levels, 4 real interaction types, 15 faction placeholders)
- Fragments registered in `PromptAssembler.FRAGMENT_CATEGORIES`
- `tools/prompt_editor.py` tkinter UI updated to browse/edit faction fragments

### Real Affinity Example

```python
# Game event: player completes a smithing quest for a guild member
faction_sys = FactionSystem.get_instance()
faction_sys.adjust_player_affinity("guild:smiths", +15.0)
# Event bus publishes FACTION_AFFINITY_CHANGED with deltas

# Next time an NPC with affiliation guild:smiths generates dialogue:
context = assemble_dialogue_context(npc_id="morven", player_id="player_1", 
                                    location_hierarchy=[("locality", "iron_hills"), ...])
# context.npc.belonging_tags = {"guild:smiths": FactionTag(significance=0.9, ...)}
# context.player.affinity_with_tags = {"guild:smiths": 15.0}

# Dialogue system prompt includes:
# "NPC affiliations: guild:smiths (90%), profession:blacksmith (50%)"
# "Player standing: guild:smiths (+15, trusted)"
```

---

## Phase 2.5: World Event System

**Status**: ⚠️ SCAFFOLDED  
**Files**: Event triggers configured in `world_system/config/event-triggers.json`; execution pending

### Trigger Framework

Events fire when conditions are met:
```json
{
  "trigger_id": "iron_famine",
  "description": "Iron ore becomes critically scarce",
  "conditions": [
    { "type": "resource_scarcity", "material_id": "iron_ore", "min_depletion": 0.9 }
  ],
  "event_params": {
    "narrative": "The iron veins have run dry. Smiths desperate, prices soar.",
    "effects": ["npc_dialogue_update", "spawn_quest", "migrate_traders"]
  },
  "cooldown_game_days": 30
}
```

### Condition Types

- `resource_scarcity(material, threshold)` — triggered by EcosystemTool
- `kill_count(enemy_type, count, timeframe)` — tracked by StatTracker
- `player_level(min_level)` — simple stat check
- `faction_reputation(faction, threshold)` — FactionSystem check
- `time_elapsed(game_days)` — game clock check
- `area_explored(biome, percent)` — EntityRegistry coverage check

### Pacing Model (Future)

```python
class PacingModel:
    """Prevents event fatigue or boredom"""
    tension_level: float  # 0 = boring, 1 = overwhelming
    
    def should_trigger_event(self, event_sig: float) -> bool:
        # If tension > 0.8, veto low-significance events
        # If tension < 0.3, approve anything
```

---

## Phase 2.6: Quest Generator

**Status**: ⚠️ SCAFFOLDED  
**Files**: `systems/quest_system.py`, `factions/quest_tool.py` (hardcoded deltas only)

### Flow: From Trigger to Gameplay

```
1. TRIGGER:
   - NPC dialogue: player asks "Do you have work?"
   - World event: faction needs aid
   - Pacing model: player needs challenge

2. GATHER CONTEXT:
   - NPC memory & personality (from npc_agent_system)
   - World state via EcosystemTool.get_report():
     * Which resources are scarce/abundant?
     * Which biomes are pressured?
     * Which enemy populations are growing?
   - Player history (StatTracker queries)
   - Faction state (FactionSystem.get_all_player_affinities())

3. GENERATE:
   - Call BackendManager.generate(task="quest_generation", ...)
   - Prompt includes real world data, not random variables
   - Example prompt:
     ```
     You are a blacksmith NPC in a crafting RPG.
     Recent game events: Player killed a dire wolf. Iron ore is 75% depleted in this biome.
     Player is allied with guild:smiths and neutral with guild:merchants.
     
     Generate a quest for this player in JSON format:
     {
       "title": "...",
       "description": "...",
       "objectives": [...],
       "rewards": {"gold": X, "rep_deltas": {"guild:smiths": +20}}
     }
     ```

4. VALIDATE:
   - Check rewards are within tier-appropriate ranges
   - Ensure objectives are achievable with current world state
   - Prevent duplicate quests

5. REGISTER & PRESENT:
   - Add to QuestSystem
   - NPC presents quest in dialogue
   - Player accepts/rejects
```

### Example: Dynamic Resource Quest

**World State**:
- Iron ore is 85% depleted (scarce)
- Wolf population is pressured in the zone
- Player has guild:smiths reputation +50 (trusted)

**Generated Quest**:
```
Title: "The Smith's Supply Run"
Description: "Morven is desperate for iron. With ore scarce, he's asking adventurers 
             to seek new veins in the deep caves—a wolf-infested region."
Objectives:
  - Find iron ore deposit in Shattered Caves (marked zone)
  - Return with 5 iron ore
Rewards:
  - 200 gold
  - +25 reputation with guild:smiths
  - Unlock "Rare Metals Broker" recipe
Fallback (if LLM fails): Template-based quest from npc_personalities.json
```

### Affinity Deltas from Quest Completion

When player completes the quest:
```python
quest_generator.apply_quest_completion(
    quest_id="smiths_supply_run",
    outcome="success",
    player_id="player_1"
)
# Routes through FactionSystem.adjust_player_affinity():
# - guild:smiths: +25
# - nation:stormguard: +5 (indirect — smiths are nationals)
# Publishes FACTION_AFFINITY_CHANGED → WMS evaluator → Layer 2 narrative
```

---

## Ecosystem as a Tool (Not a Standalone Agent)

**Status**: Integrated as utility functions, called by quest/event generators  
**Purpose**: Provide world-state context (resource pressure, population stress, biome conditions)

Instead of an autonomous EcosystemAgent polling events, the Living World Coordinator **queries** it when needed:

```python
class EcosystemTool:
    """Stateless query interface for world conditions"""
    
    @staticmethod
    def get_resource_report(biome: str) -> Dict:
        """Which resources are scarce/abundant in this biome?"""
        # Queries event_store for RESOURCE_GATHERED events
        # Calculates depletion ratio
        # Returns {"iron_ore": 0.85, "copper_ore": 0.20, ...}
    
    @staticmethod
    def check_wolf_pressure(region: str) -> float:
        """How stressed is the wolf population?"""
        # Queries event_store for ENEMY_KILLED events with tag "enemy:wolf"
        # Calculates kill rate vs. spawn rate
        # Returns pressure as 0.0–1.0
    
    @staticmethod
    def get_biome_conditions(chunk: Tuple[int, int]) -> Dict:
        """What's happening in this biome right now?"""
        # Returns {"pressure_type": "resource_scarce", "level": 0.8, 
        #          "affected_npcs": ["herbalist_quinn"], 
        #          "recommended_events": ["resource_discovery", "npc_migration"]}
```

**When is it called**:
- **Quest generator** calls it to ground objectives in reality
- **NPC dialogue** mentions recent scarcities ("Iron's getting hard to find...")
- **World event trigger** uses it to decide which event to fire
- **Pacing model** uses it to assess world tension

**Why not a separate agent**:
1. **No redundant LLM calls** — avoid asking the same backend twice
2. **Simpler architecture** — Living World Coordinator orchestrates everything
3. **Deterministic output** — same inputs always produce same scarcity values
4. **Easy to test** — pure queries, no state mutations

---

## Integration Order & Concrete Timeline

### Phase 2.1: Event Memory Layer ✅ COMPLETE (Weeks 1-2)
- ✅ EventStore with SQLite
- ✅ GameEventBus pub/sub
- ✅ Wire into combat_manager, crafting, gathering
- ✅ Save/load integration (separate .db per save)

### Phase 2.2: Backend Abstraction ✅ COMPLETE (Weeks 3-4)
- ✅ ModelBackend interface (abstract)
- ✅ OllamaBackend, ClaudeBackend, MockBackend (concrete)
- ✅ BackendManager with fallback chain
- ✅ Configuration in backend-config.json

### Phase 2.3: NPC Agent System ⚠️ SCAFFOLDED (Weeks 5-6)
- ✅ NPCMemory data model
- ✅ NPCAgent dialogue generation
- ✅ Personality templates loaded
- ⚠️ **TODO**: Wire into game NPC UI (currently fallback dialogue only)
- ⚠️ **TODO**: Gossip propagation listener on event bus

### Phase 2.4: Faction System ✅ PHASE 2+ COMPLETE (Weeks 7-8)
- ✅ Recording layer (adjust_player_affinity)
- ✅ Retrieval layer (assemble_dialogue_context)
- ✅ Quest integration (affinity deltas)
- ✅ Consolidation (top-5 standing summary)
- ✅ Prompt UI wiring
- ⚠️ **TODO**: Stylize faction identity fragments (currently placeholders)

### Phase 2.5: World Event System ⚠️ SCAFFOLDED (Weeks 9-10)
- ✅ EventTrigger config schema
- ✅ Condition checks (scarcity, kill count, faction rep, etc.)
- ⚠️ **TODO**: Implement WorldEventAgent.tick() to fire triggers
- ⚠️ **TODO**: Wire fired events into narrative generation

### Phase 2.6: Quest Generator ⚠️ SCAFFOLDED (Weeks 11-12)
- ✅ QuestTemplate enum (7 archetypes)
- ✅ EcosystemTool query interface
- ✅ Hardcoded quest deltas for 3 bootstrap quests
- ⚠️ **TODO**: Implement QuestAgent.generate_quest() with LLM
- ⚠️ **TODO**: Integrate with NPC dialogue flow ("accept quest?")
- ⚠️ **TODO**: BalanceValidator for reward gates

---

## Critical Design Decisions

1. **Ecosystem is a tool, not an agent**: No polling, no state mutations — query interface called on-demand by generators. Vastly simpler, fewer LLM calls, easier to test.

2. **Event-driven architecture**: All state changes flow through GameEventBus. Agents are subscribers, not pollers. Keeps game loop clean, decouples systems.

3. **Significance scoring gates information**: Gathering 1 copper ore (sig: 0.01) doesn't trigger gossip. Killing a T4 boss (sig: 0.95) does. Prevents information overload and keeps context windows realistic for local models.

4. **NPC knowledge is compressed**: Summaries not full events. "The player killed the dire wolf pack leader" not the entire WorldEvent JSON. Critical for fitting multiple pieces of history in limited context windows.

5. **Fallback chain guarantees uptime**: Ollama down? Try Claude. Claude API key missing? Fall back to MockBackend. Game never crashes due to AI failure. Users see templated responses instead.

6. **Faction system is persistent, not AI-generated**: Affinity values are data (persisted in SQL), not LLM opinions. LLM *generates dialogue* that reacts to affinity, but the affinity itself is earned through gameplay. This preserves player agency.

7. **Prompts ground in real world state**: Every quest, event, and dialogue prompt includes actual game data (not randomization). Players see consequences reflected in NPC behavior and world state.

---

## What to Do After Each Phase Completes

### After Phase 2.3 (NPC Agents):
- Smoke-test dialogue generation with real LLM (not just mocks)
- Compare templated vs. generated dialogue for quality
- Tune temperature and max_tokens per personality template

### After Phase 2.4 (Factions) ✅ JUST COMPLETED:
- **Next immediate**: Stylize the 15 faction identity fragments in `prompt_fragments.json` (2–4 sentences each, no code changes needed)
- Smoke-test NPC dialogue with real faction context ("You've earned the respect of the Smiths Guild...")
- Add more bootstrap factions if world design requires

### After Phase 2.5 (World Events):
- Test trigger firing with a manual date-advance tool
- Verify pacing model prevents event spam
- Tune cooldowns and thresholds

### After Phase 2.6 (Quests):
- Smoke-test quest generation with real LLM
- Verify rewards stay within tier ranges
- Check quest diversity (not all "gather" quests)

---

## Known Gaps (Planned for Future)

- **Dynamic faction spawning**: Factions are bootstrap-only today; a faction-generator could create new ones mid-game
- **Inter-faction conflict**: Factions don't fight each other yet; this is Layer 5+ narrative work
- **Merchant roads & trading nodes**: Map enrichment planned when geography team adds dynamic locations
- **Skill unlock gating by reputation**: Title system exists but isn't gated by faction rep
- **NPC migration/death**: NPCs are static; ecosystem pressure can't drive population shifts yet
- **Crafting supply chains**: Recipes don't have faction-based vendor locks (all craftable everywhere)

These are **future expansions**, not blocking critical path.

---

## File Organization (Actual)

The plan proposed `ai/` and `AI-Config.JSON/`; actual implementation is under `world_system/`:

```
Game-1-modular/
├── world_system/
│   ├── world_memory/              # Layers 1-2, 33 evaluators
│   │   ├── event_store.py         # 20 SQL tables, 1,140 LOC
│   │   ├── stat_store.py          # Hierarchical stats backend
│   │   ├── evaluators/            # 33 Layer 2 evaluators
│   │   └── (+ tag_library, layer_store, query, trigger_manager, etc.)
│   ├── living_world/              # Consumer systems
│   │   ├── backends/
│   │   │   └── backend_manager.py # Ollama/Claude/Mock abstraction
│   │   ├── npc/
│   │   │   ├── npc_agent.py       # Dialogue generation
│   │   │   └── npc_memory.py      # Memory model
│   │   ├── factions/
│   │   │   ├── faction_system.py  # Recording/retrieval
│   │   │   ├── dialogue_helper.py # Context assembly
│   │   │   ├── quest_tool.py      # Hardcoded deltas
│   │   │   ├── consolidator.py    # Affinity roll-up
│   │   │   ├── PHASE_COMPLETE.md  # Current handoff doc
│   │   │   └── (+ 50 tests, models.py, schema.py, LLM_INTEGRATION.md)
│   │   └── ecosystem/             # Tool interface (queries only)
│   │       └── ecosystem_tool.py   # Stateless resource queries
│   ├── config/
│   │   ├── prompt_fragments.json     # Layer 2 LLM fragments (184 total)
│   │   ├── backend-config.json       # Backend routing
│   │   ├── npc-personalities.json    # Personality templates
│   │   ├── faction-definitions.json  # Bootstrap factions
│   │   ├── event-triggers.json       # World event triggers
│   │   └── (+ geographic, memory config, stat tags)
│   ├── docs/
│   │   ├── WORLD_MEMORY_SYSTEM.md    # Canonical design (1,864 lines)
│   │   ├── HANDOFF_STATUS.md         # Implementation state
│   │   └── TAG_LIBRARY.md            # 65-category taxonomy
│   └── tests/                        # 56 passing tests

├── events/
│   └── event_bus.py                  # GameEventBus pub/sub (194 LOC)

├── entities/components/
│   └── stat_tracker.py               # 65 record_* methods (1,149 LOC)

└── (rest of game-1-modular unchanged)
```

---

## Testing Strategy

```bash
# Phase 2.1: Event memory
pytest world_system/world_memory/tests/ -v

# Phase 2.2: Backends
python -c "from world_system.living_world.backends import BackendManager; \
  bm = BackendManager.get_instance(); \
  text, err = bm.generate(task='test', system_prompt='You are helpful.', \
    user_prompt='Hello'); \
  assert not err, f'Backend failed: {err}'; \
  print(f'Backend OK: {text[:80]}')"

# Phase 2.3: NPC agents
pytest world_system/living_world/npc/tests/ -v

# Phase 2.4: Faction system
pytest world_system/living_world/factions/ -v
# Should show 50 passing tests (Phase 2, 3A, 3B, 3C)

# Phase 2.5/2.6: Trigger firing & quest generation
# Manual testing required (no auto-trigger in tests yet)
```

---

## Success Metrics

- **Phase 2.1**: EventStore can record 1000 events/second; queries return <100ms
- **Phase 2.2**: Backend fallback chain tested; all three backends return valid responses
- **Phase 2.3**: Generated dialogue quality comparable to human-written templates; relationship changes persist across saves
- **Phase 2.4**: ✅ Affinity changes flow through event bus to WMS evaluators; 50 tests pass
- **Phase 2.5**: Triggers fire reliably on thresholds; events don't spam (cooldowns work)
- **Phase 2.6**: Generated quests are specific to world state (not random); rewards within tier bounds; <5% failure rate

---

## References

- **Faction System Handoff**: `world_system/living_world/factions/PHASE_COMPLETE.md`
- **WMS Design**: `world_system/docs/WORLD_MEMORY_SYSTEM.md`
- **Tag Library**: `world_system/docs/TAG_LIBRARY.md`
- **Backend Config**: `world_system/config/backend-config.json`
- **Game Integration**: `CLAUDE.md` § Living World
