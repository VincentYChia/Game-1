# Faction System Phase 3 — Event Integration & WMS Consolidation

**Status**: Implemented (partial)  
**Date**: 2026-04-18  
**Scope**: Quest event → Affinity Delta integration + WMS Layer 2 consolidation

## What's Implemented

### 1. Quest Event Enhancement
- **Modified**: `systems/quest_system.py`
- Added `player_id` and `npc_id` fields to `QUEST_COMPLETED` event
- Event now contains enough context for faction system to apply affinity changes

### 2. FactionQuestListener (quest_listener.py)
**Purpose**: Listens to quest completion and applies automatic affinity changes

**Workflow**:
```
GameEventBus.publish("QUEST_COMPLETED", {
  quest_id: str,
  player_id: str,
  npc_id: str,
  quest_type: str,
  rewards: {experience, gold}
})
↓
FactionQuestListener.on_quest_completed()
↓
1. Get NPC belonging tags from database
2. For each tag:
   - Calculate delta = base_delta * significance_multiplier
   - Apply delta with db.add_player_affinity_delta()
   - Publish FACTION_AFFINITY_CHANGED event
↓
GameEventBus.publish("FACTION_AFFINITY_CHANGED", {
  player_id: str,
  tag: str,
  delta: float,
  new_value: float,
  source: "quest_completion",
  quest_id: str,
  npc_id: str
})
```

**Key Logic**:
- Base delta: +10 affinity per tag per quest completion
- Weighted by NPC's significance (-100 to +100) for that tag
- Formula: `delta = 10.0 * (1.0 + significance/200.0)` (range: 5x to 15x)
- Result is clamped to [-100, 100] in database

**Example**:
- NPC "Smith" has tags: `guild:smiths` (sig=+85), `nation:stormguard` (sig=+60)
- Player completes a quest from Smith
- Smith's crafting guild (sig=85) → +10 * 1.425 = +14.25 affinity with guild:smiths
- Smith's nation (sig=60) → +10 * 1.3 = +13 affinity with nation:stormguard

### 3. WMS Consolidation (faction_reputation.py)
**Purpose**: Layer 2 evaluator that observes affinity changes and creates narratives

**Integration Point**: Listens to `FACTION_AFFINITY_CHANGED` events

**Narrative Generation**:
- Aggregates recent affinity changes (lookback: 5 minutes)
- Creates reputation tier narratives based on affinity value:
  - 75+: "beloved"
  - 50-74: "favored"
  - 25-49: "respected"
  - 1-24: "liked"
  - 0: "neutral"
  - -1 to -24: "disliked"
  - -50 to -49: "hated"
  - -100 to -51: "reviled"

**Output Event**: 
```
InterpretedEvent(
  event_type: "FACTION_REPUTATION_CHANGE",
  interpretation: "The player is becoming favored among guild:smiths.",
  confidence: 0.9,
  tags: ["faction:guild:smiths", "reputation", "social"],
  source_event_id: original_event_id
)
```

### 4. Initialization Integration
- **Modified**: `world_system/living_world/factions/__init__.py`
- `initialize_faction_systems()` now:
  1. Initializes FactionDatabase
  2. Initializes FactionQuestListener (subscribes to event bus)
- Called from `game_engine._init_world_memory()`

## What's Pending

### Phase 4: NPC Agent Integration
**Goal**: NPCs react to player affinity

**Design**:
1. In NPC dialogue generation, retrieve NPC's perception of player affinity
2. Use `build_npc_dialogue_context()` to assemble full context
3. Modify dialogue tone based on player_affinity values:
   - High affinity (50+): Friendly, helpful
   - Low affinity (-50-): Hostile, dismissive
   - Neutral (0): Professional, reserved

**Implementation**:
- Hook NPC dialogue system to call `build_npc_dialogue_context()`
- Include player_affinity dict in LLM prompt context
- Update NPC response generation to factor in affinity

### Phase 5: LLM Integration
**Goal**: Claude generates contextual NPC dialogue based on faction state

**Design**:
1. Pass `NPCContextForDialogue.to_dict()` to Claude API
2. Include in system prompt:
   ```
   NPC Background: {npc_narrative}
   NPC Tags: {npc_belonging_tags}
   NPC Cultural Affinity: {npc_cultural_affinity}
   Player Affinity with {tag}: {player_affinity[tag]}
   Quest History: {quest_history}
   ```
3. Claude generates dialogue reflecting:
   - NPC's cultural background (affinity defaults for location)
   - NPC's personal affiliations (belonging tags)
   - Player's reputation with NPC's factions

### Phase 6: Affinity Features
**Goal**: Advanced reputation mechanics

**Features to implement**:
1. **Affinity Tiers**: Define thresholds for special interactions
   - 80+: NPC offers faction-exclusive quests
   - -80-: NPC refuses to interact

2. **Affinity Ripples**: Changes propagate across related tags
   - Player gains +10 with `guild:smiths` → also gains +3 with `nation:stormguard`
   - Implemented via computed relationships in database

3. **Affinity Decay**: Reputation slowly degrades over time
   - -0.1 per day if no interaction with faction
   - Soft decay (asymptotes to 0)

4. **Affinity Milestones**: Events triggered at reputation thresholds
   - Hits 50: "You've earned the trust of this faction"
   - Hits -80: "You've made enemies; they now actively oppose you"

## Data Flow Diagram

```
Quest Completion (game_engine)
    ↓
QUEST_COMPLETED event published (GameEventBus)
    ↓ (npc_id, player_id, quest_id)
FactionQuestListener.on_quest_completed()
    ↓
FactionDatabase.add_player_affinity_delta()
    ↓ (writes to player_affinity table)
FACTION_AFFINITY_CHANGED event published
    ↓ (tag, delta, new_value)
FactionReputationEvaluator.evaluate()
    ↓
FACTION_REPUTATION_CHANGE event published (WMS Layer 2)
    ↓
Stored in WorldMemorySystem for consolidation
    ↓
NPC dialogue generation retrieves context
    ↓
LLM uses affinity in dialogue
```

## Testing Checklist

- [ ] Create NPC with belonging tags (test: `add_npc_belonging_tag`)
- [ ] Complete quest from that NPC
- [ ] Verify FACTION_AFFINITY_CHANGED event published
- [ ] Check player_affinity table for new entries
- [ ] Verify FactionReputationEvaluator creates narrative
- [ ] Integrate NPC dialogue to use affinity context
- [ ] Test LLM dialogue generation with affinity data
- [ ] Verify affinity ripples (if implemented)
- [ ] Test affinity tier thresholds (if implemented)

## Known Issues & Limitations

1. **Player ID**: Currently using "player" as hardcoded ID. Should be:
   - Derived from character object or save file
   - Support for multiple characters/slots

2. **NPC ID in Events**: Quest system gets npc_id from quest_def, but:
   - What if NPC was deleted after quest creation?
   - Should validate NPC exists before applying affinity

3. **Affinity Deltas**: Currently uniform (+10 base)
   - Should vary by quest type (combat vs gather)
   - Should scale by difficulty/rewards

4. **WMS Integration**: FactionReputationEvaluator:
   - Uses hardcoded config; should load from JSON
   - Not yet wired into WMS consolidation pipeline
   - Needs testing with actual WMS event store

5. **Performance**: No caching of cultural affinity
   - Dialogue context builds ~300 SQL queries
   - Should implement `cultural_affinity_cache` table
   - Or batch query with single aggregation

## Files Modified/Created

**New Files**:
- `quest_listener.py` (156 lines) — Quest event listener
- `faction_reputation.py` (124 lines) — WMS evaluator
- `PHASE_3_INTEGRATION.md` (this file)

**Modified Files**:
- `systems/quest_system.py` — Added player_id, npc_id to QUEST_COMPLETED
- `world_system/living_world/factions/__init__.py` — Initialize listener

**Total Phase 3 LOC**: 280 lines (functional code) + 150 lines (docs)

## Next Steps

1. **Immediate** (Phase 3 completion):
   - Test event flow end-to-end (quest → affinity change → WMS narrative)
   - Verify database writes and reads work correctly
   - Debug any event bus issues

2. **Short term** (Phase 4):
   - Integrate NPC dialogue system to use affinity context
   - Test with existing NPC agents

3. **Medium term** (Phase 5):
   - Wire up LLM dialogue generation with affinity context
   - Test with Claude API

4. **Long term** (Phase 6+):
   - Implement affinity ripples
   - Add decay mechanics
   - Define affinity tiers and special interactions

## References

- WMS: `world_system/docs/WORLD_MEMORY_SYSTEM.md`
- Phase 2: `IMPLEMENTATION_STATUS.md`
- Event Bus: `events/event_bus.py`
- Quest System: `systems/quest_system.py`
- NPC Agents: `world_system/living_world/npc/`
