# Faction System Information Flow

**Clear, simplified explanation of how data flows through the faction system.**

## TL;DR

**Recording**: Events → Affinity Deltas → Database  
**Retrieval**: Dialog Request → Fetch Context → LLM → Response

---

## 1. Recording Flow (Events → Database)

### When a Quest Completes

```
1. Quest System completes quest
2. Quest provides affinity deltas estimate:
   {
       "guild:smiths": +10,
       "profession:blacksmith": +5
   }
3. FactionSystem.adjust_player_affinity() called for each delta
4. Database updated (sparse: only non-zero values)
5. GameEventBus publishes FACTION_AFFINITY_CHANGED event
6. WMS Layer 2 Evaluator listens, produces narrative
```

**Code Entry Point**:
```python
deltas = quest.get_affinity_deltas()  # From quest system
for tag, delta in deltas.items():
    faction_sys.adjust_player_affinity(player_id, tag, delta)
```

### When NPC Opinion Changes

```
1. Dialogue system or game event triggers NPC opinion shift
2. FactionSystem.adjust_npc_affinity_toward_player() called
3. npc_affinity table updated (under reserved tag `_player`)
4. (Optional) GameEventBus event published for WMS
```

**Code Entry Point**:
```python
# Player compliments NPC
faction_sys.adjust_npc_affinity_toward_player(npc_id, +15)

# Dialogue system can query this later
opinion = faction_sys.get_npc_affinity_toward_player(npc_id)
```

---

## 2. Retrieval Flow (Dialogue Context Assembly)

### When NPC Dialogue is Generated

```
┌─────────────────────────────────────┐
│ User triggers NPC dialogue          │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ NPC Agent gathers context:          │
│                                     │
│ 1. get_npc_profile(npc_id)          │
│    ├─ narrative                     │
│    ├─ belonging_tags (with roles)   │
│    └─ npc_affinity (toward tags)    │
│                                     │
│ 2. get_all_player_affinities()      │
│    └─ {tag: affinity} across all    │
│                                     │
│ 3. get_npc_affinity_toward_player() │
│    └─ NPC's personal opinion        │
│                                     │
│ 4. compute_inherited_affinity()     │
│    └─ Location cultural baseline    │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Assemble dialogue context dict      │
│                                     │
│ {                                   │
│   "npc": {                          │
│     "id": "smith_1",                │
│     "narrative": "...",             │
│     "tags": [                       │
│       {"tag": "guild:smiths",       │
│        "significance": 0.8,         │
│        "role": "master"}            │
│     ],                              │
│     "affinity_toward_player": 45    │
│   },                                │
│   "player": {                       │
│     "affinity_with_npc_tags": {     │
│       "guild:smiths": 60,           │
│       "profession:blacksmith": 40   │
│     }                               │
│   },                                │
│   "location": {                     │
│     "affinity_defaults": {          │
│       "guild:smiths": 30,           │
│       "profession:blacksmith": 20   │
│     }                               │
│   }                                 │
│ }                                   │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Pass context to LLM                 │
│ (Claude via BackendManager)         │
│                                     │
│ System Prompt:                      │
│ "You are an NPC dialogue generator" │
│                                     │
│ User Prompt:                        │
│ "Generate dialogue for this NPC"    │
│ + context JSON                      │
│                                     │
│ Output: Dialogue string             │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Return dialogue to game             │
└─────────────────────────────────────┘
```

---

## 3. Data Structures

### NPC Context (from `get_npc_profile()`)
```python
NPCProfile:
  - npc_id: str
  - narrative: str (personality/background)
  - created_at: float
  - last_updated: float
  - belonging_tags: Dict[str, FactionTag]
      - tag: str (e.g., "guild:smiths")
      - significance: float (0-1, Nominal to Nucleus)
      - role: str (e.g., "master")
      - narrative_hooks: List[str] (specific facts)
      - since_game_time: float
  - affinity: Dict[str, float] (tag → how NPC feels about that tag, -100 to 100)
```

### Player Affinity (from `get_all_player_affinities()`)
```python
Dict[str, float]:
  "guild:smiths": 60          # Player's standing with guild
  "profession:blacksmith": 40 # Player's standing with profession
  "nation:stormguard": -20    # Player's standing with nation
```

### NPC Opinion of Player (from `get_npc_affinity_toward_player()`)
```python
float: -100 to 100
  100  = NPC loves player
    0  = Neutral (default)
 -100  = NPC hates player
```

### Location Affinity Defaults (from `compute_inherited_affinity()`)
```python
Dict[str, float]:
  "guild:smiths": 30          # Cultural baseline affinity
  "profession:blacksmith": 20 # How location feels about this tag
  "guild:merchants": -10      # Location dislikes merchants
```

---

## 4. Affinity Value Interpretation

All affinity values are **-100 to 100**:

| Value | Interpretation |
|-------|----------------|
| 100 | Extremely positive (best friends, deep loyalty) |
| 50 | Positive (liked, trusted) |
| 0 | Neutral (default, no history) |
| -50 | Negative (disliked, mistrusted) |
| -100 | Extremely negative (hated, enemy) |

### Context Usage

- **Player affinity with tag**: How well the player stands with that faction
- **NPC affinity with tag**: How the NPC personally feels about that faction
- **NPC affinity toward player**: This NPC's personal opinion of the player (separate from reputation)
- **Location affinity default**: Cultural baseline (influences initial dialogue tone)

---

## 5. LLM Integration Points

### 1. Dialogue Generation (Primary)

**Where**: NPC dialogue request  
**What**: Assemble context dict + pass to BackendManager  
**Input**: NPC profile + player affinity + location defaults  
**Output**: Dialogue string  

```python
# Pseudo-code
context = {
    "npc": faction_sys.get_npc_profile(npc_id),
    "player_affinity": faction_sys.get_all_player_affinities(player_id),
    "npc_opinion": faction_sys.get_npc_affinity_toward_player(npc_id),
    "location_affinity": faction_sys.compute_inherited_affinity(hierarchy)
}

dialogue = backend_manager.generate_dialogue(
    system_prompt="You are an NPC dialogue generator...",
    user_prompt=f"Generate dialogue for NPC:\n{json.dumps(context)}",
    temperature=0.7,
    max_tokens=200
)
```

### 2. Location Affinity Defaults (Secondary)

**Where**: During world initialization or location generation  
**What**: LLM generates cultural affinity defaults for new locations  
**Input**: Location description + tag registry  
**Output**: Dict of {tag: affinity} values  

```python
# Placeholder for future implementation
# (Currently hardcoded in schema.py BOOTSTRAP_LOCATION_AFFINITY_DEFAULTS)
```

### 3. NPC Creation (Secondary)

**Where**: During NPC generation  
**What**: LLM generates NPC narrative and initial tags  
**Input**: NPC archetype + location context  
**Output**: NPC profile with narrative and belonging tags  

```python
# Placeholder for future implementation
```

---

## 6. Affinity Consolidation (WMS Layer 2)

### What Happens

When `FACTION_AFFINITY_CHANGED` event is published:

```
1. WMS FactionReputationEvaluator listens
2. Reads current affinity from database
3. Produces InterpretedEvent with tags:
   - domain:faction
   - faction:{tag}
   - rep_direction:improved or rep_direction:worsened
   - rep_magnitude:minor/moderate/major
4. Event feeds into WMS Layer 3+ pipeline
5. Eventually produces consolidated narrative
```

### Example

```
Event: adjust_player_affinity("player_1", "guild:smiths", +10)
  ↓
InterpretedEvent produced:
  - tags: [
      "domain:faction",
      "faction:guild:smiths",
      "rep_direction:improved",
      "rep_magnitude:minor"
    ]
  - description: "The player's standing with guild:smiths has improved"
  ↓
WMS consolidation pipeline processes
  ↓
Results in narrative/NPC behavior changes
```

---

## 7. Integration Checklist

### For Quest System
- [ ] Implement `Quest.get_affinity_deltas()` method
- [ ] Call `faction_sys.adjust_player_affinity()` when quest completes
- [ ] Publish `FACTION_AFFINITY_CHANGED` event

### For NPC Agent
- [ ] Use `faction_sys.get_npc_profile()` for dialogue context
- [ ] Use `faction_sys.get_all_player_affinities()` for player standing
- [ ] Use `faction_sys.get_npc_affinity_toward_player()` for NPC opinion
- [ ] Use `faction_sys.compute_inherited_affinity()` for location baseline
- [ ] Pass assembled context to `BackendManager.generate_dialogue()`

### For Dialogue System
- [ ] Assembly context dict from faction system
- [ ] Pass to BackendManager with system/user prompts
- [ ] Cache dialogue for performance

### For WMS Integration
- [ ] FactionReputationEvaluator listens to `FACTION_AFFINITY_CHANGED`
- [ ] Produces InterpretedEvent with faction tags
- [ ] Feeds into Layer 3+ consolidation

---

## 8. Key Design Properties

1. **Sparse Storage**: Only non-zero affinity values stored in database
2. **Hierarchical Defaults**: Location affinity inherited from world → nation → district → locality
3. **Separation of Concerns**:
   - Player affinity = global standing with tags
   - NPC affinity toward tags = how that NPC feels
   - NPC affinity toward player = personal opinion (separate track)
4. **No Decay**: Affinity persists indefinitely (consolidation will produce "narrative decay" via WMS)
5. **Event-Driven**: All changes publish events for WMS integration
