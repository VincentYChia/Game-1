# Faction System Phases 4-6 — NPC Dialogue, LLM Integration & Advanced Features

**Status**: Implemented  
**Date**: 2026-04-18  
**Scope**: Phase 4 (NPC Dialogue Context), Phase 5 (LLM Integration), Phase 6 (Affinity Tiers, Ripples, Decay, Milestones)

## Phase 4: NPC Dialogue Integration

### Overview
NPC dialogue now incorporates faction affinity data. When an NPC speaks to a player, the dialogue tone, helpfulness, and emotion reflect the player's reputation with the NPC's affiliated factions.

### Component: FactionDialogueGenerator

**File**: `faction_dialogue_generator.py` (287 lines)

**Purpose**: Build rich dialogue context combining:
- NPC profile and narrative
- NPC's belonging tags (their affiliations)
- NPC's cultural affinity (how their location feels toward factions)
- Player's affinity with NPC's tags
- Recent quest history

**Core Method**: `build_npc_dialogue_context(npc_id, player_id)`

```python
context = generator.build_npc_dialogue_context("smith_village", "player")
# Returns NPCContextForDialogue with:
# - NPC narrative: "A gruff blacksmith from the north..."
# - NPC tags: ["profession:blacksmith", "nation:stormguard"]
# - Cultural affinity: {"guild:smiths": 50, "nation:stormguard": 30}
# - Player affinity: {"profession:blacksmith": 25, "nation:stormguard": -10}
# - Quest history: [quest_1, quest_3, ...]
```

**Dialogue Generation**: `generate_faction_dialogue(context, player_input)`

Uses BackendManager to generate Claude-powered dialogue with affinity-aware tone:

```python
dialogue = generator.generate_faction_dialogue(
    context,
    player_input="Can you craft a sword for me?",
    character=player_character,
    npc_name="Gunnar the Smith"
)
# Returns: {
#   "text": "Ah, you again. I suppose I can fit you in...",
#   "emotion": "grudging",
#   "success": True
# }
```

**System Prompt Composition**:
```
You are Gunnar the Smith...
Background: A gruff blacksmith from the north...
Primary identity: profession:blacksmith

Affiliations:
- profession:blacksmith (significance: +90)
- nation:stormguard (significance: +60)

Cultural context (local attitudes):
- nation:stormguard: +70
- guild:merchants: -20

=== PLAYER REPUTATION ===
- profession:blacksmith: +25 (respected)
- nation:stormguard: -10 (neutral)

Dialogue tone: Cordial, professional. You regard this player positively.
Respond in-character...
```

### Integration with NPCAgentSystem

The FactionDialogueGenerator is wired into `NPCAgentSystem.generate_dialogue()`:

1. When NPC dialogue is requested, NPCAgentSystem calls `FactionDialogueGenerator.build_npc_dialogue_context()`
2. Passes rich context to BackendManager with task="faction_dialogue"
3. Receives Claude-generated dialogue with affinity-appropriate tone
4. Updates NPC memory with disposition changes

**Example Flow**:
```
Player: "Hello, Gunnar"
  ↓
NPCAgentSystem.generate_dialogue(npc_id="smith", player_input="Hello, Gunnar")
  ↓
FactionDialogueGenerator.build_npc_dialogue_context("smith", "player")
  ↓ (context with affinity data)
BackendManager.generate(task="faction_dialogue", system_prompt=..., user_prompt=...)
  ↓ (routes to Claude API)
Claude: "Ah, you again. Your work has improved since last time."
  ↓
NPCAgentSystem updates memory: relationship_delta=+0.05
```

---

## Phase 5: LLM Integration via BackendManager

### Configuration Changes

**File**: `backend-config.json`

Added new task routing:
```json
"faction_dialogue": {
  "primary": "claude",
  "description": "NPC dialogue enhanced with faction affinity context"
}
```

This ensures faction dialogue always uses Claude (high-quality contextual generation), with fallback chain: Claude → Mock.

### Backend Routing

When `BackendManager.generate(task="faction_dialogue", ...)` is called:

1. **Primary**: Checks if Claude backend is available
   - Resolves API key from env or .env file
   - Calls Claude API with system + user prompts
2. **Fallback**: If Claude unavailable, uses Mock backend
   - Returns template-based dialogue (graceful degradation)
3. **Rate Limiting**: Enforces cooldown (1s per request) to prevent API throttling

### Prompt Engineering

**System Prompt Sections** (in order):
1. NPC identity and background
2. Affiliations with tags and significance scores
3. Cultural affinity (location context)
4. **CRITICAL: Player Reputation** (tone driver)
5. Tone guidance based on average affinity
6. JSON format specification

**User Prompt Sections**:
1. Player input
2. Player visible stats (level, class)
3. Quest history with this NPC
4. Affinity summary (friendly/hostile tags)

**Tone Mapping**:
- Affinity ≥ 50: "Warm, friendly, helpful. This player has earned your respect."
- Affinity 25-50: "Cordial, professional. You regard this player positively."
- Affinity -25 to 25: "Neutral, reserved. This player is unremarkable to you."
- Affinity -50 to -25: "Cool, dismissive. This player has done things you disapprove of."
- Affinity ≤ -50: "Hostile, contemptuous. This player is an enemy. Refuse to help."

### JSON Response Format

Claude returns dialogue wrapped in JSON:
```json
{
  "dialogue": "Ah, you again. Your work has improved since last time.",
  "emotion": "pleased"
}
```

Parsed by `FactionDialogueGenerator._parse_dialogue_response()` with markdown support.

---

## Phase 6: Advanced Affinity Features

### Overview

Four interconnected systems deepen faction mechanics:

1. **AffinityTierSystem**: Reputation thresholds unlock special interactions
2. **AffinityRippleSystem**: Affinity changes propagate across related tags
3. **AffinityDecayScheduler**: Background thread for time-based reputation degradation
4. **AffinityMilestoneSystem**: Events published when crossing thresholds

**File**: `affinity_features.py` (407 lines)

### 1. Affinity Tier System

**Purpose**: Define reputation thresholds and special interactions

**Tiers** (default):
| Affinity | Tier | Effects | Special Interactions |
|----------|------|---------|----------------------|
| 75+ | beloved | - | exclusive_quest, gift_access |
| 50-74 | favored | - | discount_trading |
| 25-49 | respected | - | - |
| 0-24 | neutral | - | - |
| -25 to -1 | disliked | - | increased_prices |
| -50 to -25 | hated | - | quest_refusal |
| ≤ -80 | reviled | - | active_opposition |

**Usage**:
```python
tier_system = get_tier_system()

# Check if player can access exclusive quests
if tier_system.can_access_interaction(current_affinity, "exclusive_quest"):
    # Offer special quest from faction

# Get all accessible interactions
interactions = tier_system.get_all_accessible_interactions(affinity)
# Returns: ["discount_trading", "gift_access"]
```

**NPC Behavior Integration**:
- At affinity 80+: NPC offers faction-exclusive quests
- At affinity 50+: NPC provides 10% discount on goods
- At affinity -80: NPC refuses quests entirely, becomes active enemy
- NPCs check tier before responding to player

### 2. Affinity Ripple System

**Purpose**: Reputation changes propagate to related factions

When player gains affinity with one faction, related factions see proportional changes.

**Example Ripple Map**:
```python
RIPPLE_RELATIONSHIPS = {
    "guild:smiths": [
        ("guild:crafters", 0.3),    # 30% of smith gains → crafter gains
        ("nation:stormguard", 0.1), # 10% ripple to nation
    ],
    "guild:merchants": [
        ("guild:crafters", 0.2),
        ("nation:merchant_alliance", 0.4),
    ],
}
```

**Flow**:
```
Quest completion: +10 with "guild:smiths"
  ↓
FactionQuestListener publishes FACTION_AFFINITY_CHANGED
  ↓
AffinityRippleSystem.apply_ripples("player", "guild:smiths", +10)
  ↓
- guild:crafters: +3 (10 × 0.3)
- nation:stormguard: +1 (10 × 0.1)
  ↓
Database updated; affinity propagation complete
```

**Usage**:
```python
# In quest_listener.py or wherever affinity changes occur:
ripple_sys = get_ripple_system()
ripple_sys.apply_ripples(player_id, tag, delta)

# Add new relationships at runtime:
ripple_sys.add_ripple_relationship("guild:smiths", "profession:mining", 0.2)
```

### 3. Affinity Decay Scheduler

**Purpose**: Time-based reputation degradation

Affinity slowly returns toward 0 if the player doesn't interact with a faction.

**Mechanics**:
- Decay rate: -0.1 per day (configurable)
- Soft decay: Only decreases if affinity != 0
- Decay toward 0, never crossing: +10 → +5 → +0, stops at 0
- Symmetric: Both positive and negative affinity decay

**Background Thread**:
- Runs continuously in daemon thread
- Checks every 60 seconds (configurable)
- Applies proportional decay based on real elapsed time
- Scales: 1 full day of game time = -0.1 affinity

**Flow**:
```
Initial: guild:smiths = +50
After 1 day of no interaction: +49.9
After 500 days: +0

Initial: nation:stormguard = -30
After 1 day: -29.9
After 300 days: -0
```

**Usage**:
```python
# Starts automatically in initialize_faction_systems(enable_decay=True)
scheduler = get_decay_scheduler()

# Manual control if needed:
scheduler.stop()  # Pause decay (e.g., before saving)
scheduler.start() # Resume decay
```

**Save/Load Integration**:
- Before save: `save_faction_systems()` stops the scheduler
- After load: `restore_faction_systems()` restarts it
- Prevents mutations during serialization

### 4. Affinity Milestone System

**Purpose**: Publish events when affinity crosses thresholds

Triggers special reactions or quests at key reputation points.

**Milestones**:
```python
MILESTONES = {
    75: "beloved",
    50: "favored",
    25: "respected",
    0: "neutral",
    -25: "disliked",
    -50: "hated",
    -80: "reviled",
}
```

**Event Published**:
```python
# When player affinity changes from 49.5 → 50.5 with "guild:smiths":
AFFINITY_MILESTONE = {
    "player_id": "player",
    "tag": "guild:smiths",
    "milestone": "favored",
    "affinity": 50.5,
    "direction": "reached",
    "narrative": "You have reached favored status with guild:smiths. (Affinity: +51)"
}
```

**Example Listener**:
```python
def on_affinity_milestone(event):
    tag = event.data.get("tag")
    milestone = event.data.get("milestone")
    
    if milestone == "beloved" and tag.startswith("guild:"):
        # Grant special quest item
        player_inventory.add_item("guild_signet_ring")
    
    if milestone == "reviled" and tag == "nation:stormguard":
        # Trigger bounty on player
        create_bounty_hunter_quest()

get_event_bus().subscribe("AFFINITY_MILESTONE", on_affinity_milestone)
```

**Usage**:
```python
# Starts automatically in initialize_faction_systems(enable_milestones=True)
milestone_sys = get_milestone_system()

# Milestones are checked automatically when affinity changes
# via FactionQuestListener or manual db.add_player_affinity_delta()
```

---

## Integration Flow: End-to-End

### Scenario: Player Completes a Quest for Gunnar the Blacksmith

```
1. Player completes quest from Gunnar (npc_id="smith_village")
   ↓
2. GameEventBus.publish("QUEST_COMPLETED", {
     quest_id: "smith_fetch_ore",
     player_id: "player",
     npc_id: "smith_village",
     ...
   })
   ↓
3. FactionQuestListener.on_quest_completed()
   - Gets NPC tags: ["profession:blacksmith" (sig=+85), "nation:stormguard" (sig=+60)]
   - Calculates deltas: +10 * (1 + 85/200) = +14.25, +10 * (1 + 60/200) = +13
   - Applies via db.add_player_affinity_delta()
   ↓
4. Database updates:
   - player_affinity: profession:blacksmith += 14.25 (now 64.25)
   - player_affinity: nation:stormguard += 13 (now 63)
   ↓
5. GameEventBus.publish("FACTION_AFFINITY_CHANGED", {
     player_id: "player",
     tag: "profession:blacksmith",
     delta: 14.25,
     new_value: 64.25,
     source: "quest_completion",
   })
   (Repeated for nation:stormguard)
   ↓
6. FactionReputationEvaluator (WMS Layer 2)
   - Aggregates recent changes (5 min lookback)
   - Creates narrative: "The player is becoming favored among profession:blacksmith."
   - Publishes to WMS: FACTION_REPUTATION_CHANGE
   ↓
7. AffinityRippleSystem.apply_ripples("player", "profession:blacksmith", 14.25)
   - guild:crafters += 4.3 (14.25 * 0.3)
   - Checks milestones for each
   ↓
8. AffinityMilestoneSystem.check_milestone("player", "profession:blacksmith", 64.25)
   - Was 50 (favored), now 64.25 (still favored) → No crossing
   - No milestone event published
   ↓
9. AffinityTierSystem checks
   - profession:blacksmith at 64.25 → "favored" tier
   - Unlocks: ["discount_trading"]
   ↓
10. Player interacts with Gunnar again
    ↓
11. NPCAgentSystem.generate_dialogue(npc_id="smith_village", player_input="Hello again")
    ↓
12. FactionDialogueGenerator.build_npc_dialogue_context()
    - Retrieves: affinity=64.25, tier="favored"
    - Retrieves cultural affinity from village location
    - Assembles NPCContextForDialogue
    ↓
13. BackendManager.generate(
      task="faction_dialogue",
      system_prompt="...profession:blacksmith: +64 (favored)...",
      user_prompt="The player says: Hello again"
    )
    ↓
14. Claude API: "Good to see you. Your recent work on the ore shipment was solid. 
               How can I help you further?"
    ↓
15. NPCDialogueResult returned with emotion="pleased", disposition_delta=+0.02
    ↓
16. NPC memory updated with new emotion and relationship
```

---

## Testing Checklist

- [ ] FactionDialogueGenerator builds context correctly
- [ ] NPCContextForDialogue includes all fields (affinity, cultural, quest history)
- [ ] BackendManager routes "faction_dialogue" task to Claude
- [ ] Claude generates tone-appropriate dialogue based on affinity
- [ ] AffinityTierSystem correctly maps affinity → tier
- [ ] Tier system unlocks interactions correctly
- [ ] AffinityRippleSystem propagates deltas to related tags
- [ ] Ripple strengths apply correctly (30% → 0.3 multiplier)
- [ ] AffinityDecayScheduler runs in background
- [ ] Decay only occurs when affinity != 0
- [ ] Decay is symmetric (+/-)
- [ ] AffinityMilestoneSystem detects threshold crossing
- [ ] Milestones publish correct AFFINITY_MILESTONE events
- [ ] NPC dialogue tone changes with affinity (test at multiple tiers)
- [ ] Save/load preserves all systems
- [ ] Decay scheduler restarts after load

---

## Files Created/Modified

**New Files**:
- `faction_dialogue_generator.py` (287 lines) — NPC dialogue context building
- `affinity_features.py` (407 lines) — Tiers, ripples, decay, milestones
- `PHASES_4-6_INTEGRATION.md` (this file)

**Modified Files**:
- `factions/__init__.py` — Added initialization for Phase 4-6 systems
- `backend-config.json` — Added `faction_dialogue` task routing
- `PHASE_3_INTEGRATION.md` — References Phase 4-6 continuation

**Total Phase 4-6 LOC**: 694 lines (functional code) + 200 lines (docs)

---

## Known Limitations & Future Work

### Phase 4-5 (NPC Dialogue)
1. **Player ID**: Still using "player" as placeholder (hardcoded in FactionQuestListener)
   - Should derive from active character save slot
   - Blocks multi-character support

2. **NPC Position Lookup**: Gossip delay calculation uses flat delay, not distance
   - Would need EntityRegistry integration to get NPC positions
   - Currently: all NPCs hear gossip with same delay

3. **Dialogue History Truncation**: Conversation summary bounded to 2000 chars
   - May lose context in long interactions
   - Could switch to rolling window or separate memory layers

### Phase 6 (Advanced Features)
1. **Ripple Configuration**: Hardcoded RIPPLE_RELATIONSHIPS dict
   - Should load from JSON config for flexibility
   - Currently requires code change to add new ripples

2. **Affinity Tier Customization**: Tiers hardcoded in DEFAULT_AFFINITY_TIERS
   - Should load per-faction tier definitions from database
   - Would enable unique thresholds for different factions

3. **Decay Performance**: Applies decay to all tags every 60 seconds
   - Linear scan of all affinities; could batch with aggregation
   - For 100+ tags × many players, becomes slow
   - Optimize: Only update tags with non-zero affinity

4. **Milestone Double-triggering**: Only stores last_value, not direction
   - Could publish duplicate milestones on affinity oscillation
   - Add hysteresis: require min change to retrigger same threshold

5. **Background Decay Accuracy**: Uses real time as proxy for game time
   - Correct approach: Pass game_time from game engine tick
   - Currently: Decay rate doesn't scale with game speed

### Phase 7 (Future Enhancements)
- **Affinity Quests**: "Prove your loyalty by..."  quests unlocked at tiers
- **Factional Conflicts**: High affinity with one faction auto-decreases with enemies
- **Reputation Markets**: Player reputation affects NPC prices, availability
- **Legacy System**: Long-term reputation persists as "history" separate from current affinity
- **Dynamic Tier Events**: Special one-time quests/rewards at milestone thresholds

---

## Architecture Decisions Rationale

### Why Claude for faction_dialogue?
- Needs rich contextual understanding (affinity, cultural, quest history)
- Must generate tone-appropriate responses (friendly, hostile, professional)
- Single response per interaction (not streamed) → manageable token count
- Local Ollama insufficient for nuanced tone modulation

### Why separate FactionDialogueGenerator from NPCAgentSystem?
- Single Responsibility: Faction context building is distinct from memory/gossip
- Testability: Can test context building independently
- Composability: Other systems (quest generator, lore builder) can reuse context
- Extensibility: Can add affinity-unaware dialogue path for simple NPCs

### Why soft decay (toward 0) not hard decay (constant loss)?
- Soft decay (asymptotic) mimics natural reputation drift: fades but doesn't invert
- Hard decay could turn +100 beloved → -100 reviled if afk long enough (unintuitive)
- Soft decay preserves player effort: +50 affinity never becomes -50
- More realistic: people remember good deeds, just less enthusiastically

### Why milestones published as events, not callbacks?
- Decouples milestone logic from reward logic
- Multiple handlers can respond (UI toast, quest generation, NPC behavior)
- Events logged to WMS for narrative context
- Consistent with GameEventBus pattern throughout codebase

---

## References

- Phase 3: `PHASE_3_INTEGRATION.md`
- Backend Manager: `world_system/living_world/backends/backend_manager.py`
- NPC Agent System: `world_system/living_world/npc/npc_agent.py`
- Event Bus: `events/event_bus.py`
- Faction Database: `factions/database.py`
- Models: `factions/models.py`
