# Faction System Design (v1.0)

**Date**: 2026-04-17
**Status**: Foundation Design (Pre-Code)
**Scope**: Tag-based NPC faction belonging + affinity system, integrated with WMS

---

## Core Principles

1. **Belonging ≠ Affinity**
   - **Belonging**: What tags define an NPC (their values, background, identity)
   - **Affinity**: How they feel about other tags (their personal sentiment/opinion)
   - These are independent dimensions.

2. **Affinity is Hierarchical with Exceptions**
   - Defaults exist at: world → nation → region → province → district → locality scale
   - NPCs inherit these defaults by location
   - Only **notable exceptions** are stored per-NPC
   - This scales to thousands of NPCs without per-NPC tuning burden

3. **Players Have No Belonging**
   - Player actions are their own, not designed
   - Players accumulate affinity (how others perceive them)
   - Player affinity is affected by their traits (e.g., charisma)

4. **NPC Creation is Stable & Narrative-First**
   - NPCs are created with a STABLE baseline profile
   - They are NOT time-locked to recent events
   - Narrative comes first; tags emerge from narrative
   - All-in-one LLM pass (not sequential steps)

5. **Quest Completion is the Affinity Event**
   - Affinity changes happen ONLY at quest completion
   - No intermediate updates during gameplay
   - This simplifies tracking and makes the loop explicit

---

## Data Model

### NPC Faction Profile

```python
@dataclass
class FactionTag:
    tag: str                    # e.g., "nation:stormguard"
    significance: str           # Named bucket (see buckets list)
    role: Optional[str]         # e.g., "guard", "elder", "merchant"
    narrative_hooks: List[str]  # ≥3 bullet points (LLM fodder)

@dataclass
class NPCFactionProfile:
    npc_id: str
    
    # STABLE PROFILE (set at NPC creation)
    narrative: str              # Full background narrative paragraph(s)
    belonging: List[FactionTag] # Tags that define them
    affinity: Dict[tag, float]  # ONLY stores exceptions from hierarchy
    
    # MUTABLE (changes with gameplay)
    affinity_overrides: Dict[tag, float]  # Runtime changes (saved state)
    
    # METADATA (for refresh/audit)
    created_at_game_time: float
    created_from_metadata: Dict  # role, location used to create this NPC
```

### Affinity Hierarchy Lookup

When querying NPC affinity toward tag X:

```
effective_affinity(npc, tag) = lookup(npc, tag):
  1. if npc.affinity_overrides[tag] exists → return it
  2. if npc.affinity[tag] exists → return it
  3. if locality_defaults[tag] exists → return it
  4. if district_defaults[tag] exists → return it
  5. if province_defaults[tag] exists → return it
  6. if nation_defaults[tag] exists → return it
  7. if world_defaults[tag] exists → return it
  8. return 0.0 (neutral)
```

**Rationale**: Most NPCs don't need explicit affinity entries. They inherit shared sentiment from their location hierarchy. Only exceptions are stored.

### Player Affinity Profile

```python
@dataclass
class PlayerFactionProfile:
    player_id: str
    
    # Player has NO belonging (actions are their own)
    
    # Player affinity (how NPCs perceive them)
    affinity: Dict[tag, float]  # All values stored (no hierarchy)
    
    # Player traits (affect affinity deltas)
    traits: Dict[str, float]    # e.g., "charisma": 0.1
```

When an NPC gains affinity for the player:
```
delta = base_delta + player_traits_bonus
# Example: quest gives +0.1, player has charisma +0.1 → +0.2 total
```

### Affinity Default Hierarchy

```python
# Stored in config files (see Phase 1)
affinity_defaults = {
    "world": {tag: float},           # Baseline for all tags
    "nation": {nation_id: {tag: float}},
    "region": {region_id: {tag: float}},
    "province": {province_id: {tag: float}},
    "district": {district_id: {tag: float}},
    "locality": {locality_id: {tag: float}}
}
```

Example setup:
```json
{
  "world": {
    "guild:merchants": -0.1,
    "nation:stormguard": 0.0
  },
  "nation": {
    "nation:stormguard": {
      "guild:merchants": -0.2,  // National policy skepticism
      "guild:smiths": 0.1       // Valued for defense goods
    }
  },
  "locality": {
    "village_westhollow": {
      "guild:merchants": -0.3   // Local overreliance on trade, creates resentment
    }
  }
}
```

### Tag Registry

```python
@dataclass
class TagEntry:
    tag: str
    namespace: str              # e.g., "nation", "guild", "cult"
    appearance_count: int       # Total uses in game (NPC creation)
    first_seen_game_time: float
    human_gloss: str            # What this tag means
    is_generated: bool          # Did LLM create it?

class TagRegistry:
    """Durable dictionary of all tags ever used"""
    def register(tag: str, namespace: str, gloss: str) -> None
    def get(tag: str) -> Optional[TagEntry]
    def all_tags(namespace: Optional[str]) -> List[TagEntry]
    def appearance_count(tag: str) -> int
```

---

## NPC Creation Pipeline

### Inputs (Minimalist)

**ONLY**:
1. `role: str` — what this NPC does (e.g., "village_blacksmith", "merchant_trader")
2. `location_id: str` — where they live (e.g., "village_westhollow")
3. `faction_landscape: Dict[tag, float]` — world + nation + region + province + district + locality affinity defaults

**NOT included**:
- NPC memory (no past interactions)
- WMS events (don't lock NPC to recent history)
- Quest hooks (NPC is independent)
- Recent events (baseline is stable)

**Rationale**: We want NPCs to be stable, core profiles. They're not defined by "the war last month." They're defined by who they are. Recent events modify affinity LATER (via quest outcomes), not at creation.

### LLM Prompt Structure

Single prompt (all-at-once, not sequential):

```
You are creating an NPC for a fantasy RPG. 

ROLE: {role}
LOCATION: {location_id} ({location_name})
WORLD AFFINITY CONTEXT:
  {affinity_landscape formatted as readable summary}

Generate:
1. A narrative paragraph (2-3 sentences) establishing this NPC's background, personality, and current situation.
2. Belonging tags (3-5 tags with significance buckets):
   Format: "tag_name [BUCKET]"
   - Examples: "nation:stormguard [REGULAR]", "profession:blacksmith [COMMITTED]"
3. Affinity exceptions (only if this NPC diverges from locality defaults):
   Format: "tag_name: +/-0.X"
   - Only list tags where this NPC differs significantly from their location's defaults
   - Example: "guild:merchants: -0.5" (they're particularly bitter)
4. Narrative hooks (3+ specific facts that emerge from the narrative):
   - These should explain WHY the belonging and affinity are what they are

---Output format:
NARRATIVE:
[full narrative paragraph]

BELONGING:
[tagged list]

AFFINITY EXCEPTIONS:
[only non-default affinities]

NARRATIVE HOOKS:
[bullet points]
```

### Output (Complete NPC Profile)

The LLM produces:
- **Narrative** (stable, describes who they are)
- **Belonging tags** + significance buckets + narrative hooks
- **Affinity exceptions** (only stored if they exist)

This profile is SAVED and STABLE. It doesn't change until:
1. A quest involving this NPC completes
2. World-scale affinity defaults shift (only then do inherited affinities update)

---

## Affinity Modification

### Quest Completion (The Only Affinity Event)

When player completes a quest:

```python
event = QuestCompletedEvent(
    player_id=player,
    quest_id=quest,
    npc_id=npc,
    location_id=location,
    success=True/False  # affects delta magnitude
)

# Quest has a faction_rewards dict:
quest_faction_rewards = {
    "nation:stormguard": 0.01,     # grant this delta to player affinity
    "guild:smiths": 0.02,
    f"npc:{npc_id}": 0.1            # NPC-specific affinity (direct relationship)
}

# Apply deltas
for tag, delta in quest_faction_rewards.items():
    # Apply player traits bonus
    total_delta = delta + player_traits.get(tag, 0)
    player_affinity[tag] += total_delta

# NPC-side change (if quest involved NPC)
npc_affinity_overrides[f"player:{player_id}"] += 0.1

# Publish event to WMS (for narrative capture)
GameEventBus.publish(QUEST_COMPLETED, event)
```

### World-Scale Affinity Changes

When world state shifts dramatically (e.g., a guild is exposed as corrupt):

```python
# Application layer or WMS evaluator can trigger:
faction_system.set_nation_affinity_default(
    nation_id="nation:stormguard",
    tag="guild:merchants",
    delta=-0.2  # decrease affinity by 0.2
)

# All NPCs in that nation now have worse opinion of guild:merchants
# UNLESS they have an explicit affinity_overrides entry
# (Exception: if NPC has explicit affinity[guild:merchants] = 0.3, they're unaffected)
```

This creates the "ripple effect" without recreating NPCs.

### Player Traits (Charisma, etc.)

Player can have persistent traits that affect affinity deltas:

```python
player.traits = {
    "charisma": 0.1,        # +0.1 bonus to all NPC affinity gains
    "notoriety": -0.05,     # -0.05 malus to reputation with certain factions
}

# Applied at quest completion:
total_delta = quest_delta + sum(player.traits.values())
```

---

## Interaction Flow (Second Pass: With Context)

When player encounters an NPC (second and later times):

```
NPC interacts with player:
├─ Read NPC's stable profile (narrative + belonging + affinity)
├─ Query WMS for recent events (L2-L3 summaries of locality)
├─ Query NPCMemory for past interactions (if any)
├─ Query quests available (faction-gated by player affinity)
├─ Query player affinity state (how does NPC perceive player now)
└─ LLM generates:
    ├─ Quest offer (or quest reference)
    ├─ Enriched narrative (internal monologue, current situation)
    └─ Dialogue context (not back-and-forth, but narrative seed)
```

The NPC's narrative includes:
- Their belonging tags' narrative hooks (who they are)
- Their affinity toward the player (how they feel about them now)
- WMS context (what's happening in their area)
- Quest needs (what they want from the player)

Example output:
```
"I've heard rumors about your deeds. The guild has been struggling since 
the recent trade disputes—we've lost access to eastern routes. I could use 
someone I trust to retrieve a shipment from the old warehouse. It's dangerous, 
but the pay is good. Can I count on you?"
```

This narrative is ENRICHED by context, not hardcoded.

---

## The Echo Loop (Simplified)

```
1. NPC created:
   stable profile (narrative + belonging + affinity_exceptions)
   
2. Player receives quest:
   NPC narrative enriched with WMS + NPC memory + player affinity
   
3. Player completes quest:
   QUEST_COMPLETED event published
   Player affinity[npc tags] += deltas
   NPC affinity[player tag] += deltas
   
4. WMS observes QUEST_COMPLETED:
   FactionReputationEvaluator tags it (domain:faction, faction_layer, etc.)
   L2 narrative: "word spreads"
   Cascades to L3-L7
   
5. World-scale affinity might shift:
   If major event, faction_system updates nation/region defaults
   All NPCs in those areas inherit the change (unless they have overrides)
   
6. Next NPC interaction:
   Reads updated affinity (both player-specific + world-scale)
   Narrative reflects the changed world
```

**Key**: Affinity changes do NOT update NPC belonging. Belonging is stable (their identity). Affinity is fluid (their opinions).

---

## Location & Metadata Context

### Location Awareness (Current)

For now, locations are **prompts hints**, not full schemas:

```python
location_metadata = {
    "location_id": "village_westhollow",
    "location_name": "Westhollow",
    "region_id": "region:northern_marches",
    "type": "village",  # guides NPC context generation
    "rough_population": 200,
    "primary_industry": "grain",
}
```

These are used in the NPC creation prompt:
```
LOCATION: village_westhollow (Westhollow, a grain farming village)
```

They're NOT full faction-context schemas yet.

### Future: Location Narratives

When world generation is more sophisticated (Phase X+):

```python
location_metadata = {
    # ... current fields ...
    "narrative": "full description of the location's character",
    "dominant_faction": "nation:stormguard",
    "conflict_factions": [
        {"tag": "ideology:separatist", "severity": 0.4}
    ],
    "interests": ["grain_export", "defense"]
}
```

Then NPCs would be shaped by location narrative. For now, we don't have that.

**Record this as deferred work**.

---

## Significance Buckets

(Awaiting user's final 10-bucket terms. Placeholders below.)

Used to name affinity values and belonging significance:

```python
# Example (not final):
SIGNIFICANCE_BUCKETS = [
    (1.0, "cardinal"),
    (0.9, "vital"),
    (0.8, "principal"),
    (0.7, "integral"),
    (0.6, "committed"),
    (0.5, "engaged"),
    (0.4, "involved"),
    (0.3, "affiliated"),
    (0.2, "regular"),
    (0.1, "nominal")
]
```

In practice:
- NPC is "cardinal" to nation:stormguard (singular defining figure)
- NPC is "nominal" to guild:merchants (just a basic member)
- Player's affinity toward nation:stormguard is 0.4 ("involved" in their affairs)

---

## WMS Integration (Layer 2)

### Event Type: QUEST_COMPLETED

```python
class QuestCompletedEvent(GameEvent):
    event_type = EventType.QUEST_COMPLETED
    player_id: str
    quest_id: str
    npc_id: str
    location_id: str
    success: bool
    faction_rewards: Dict[tag, float]  # may be empty
    reward_items: List[ItemId]
```

### FactionReputationEvaluator (Layer 2)

Observes QUEST_COMPLETED and emits:

```python
tags = [
    "domain:faction",
    "action:quest_completed",
    "npc:" + event.npc_id,
    "player:" + event.player_id,
]

# If quest had faction rewards:
if event.faction_rewards:
    for tag, delta in event.faction_rewards.items():
        if delta > 0:
            tags.append("rep_direction:improved")
        else:
            tags.append("rep_direction:worsened")
    
    # Magnitude based on delta size
    avg_magnitude = mean(abs(d) for d in event.faction_rewards.values())
    if avg_magnitude > 0.05:
        tags.append("rep_magnitude:major")
    else:
        tags.append("rep_magnitude:minor")

interpreted = InterpretedEvent(
    event=event,
    tags=tags,
    summary=f"Player completed quest for {event.npc_id} in {location}, affecting faction sentiment"
)
```

This cascades to L3-L7 as narrative.

---

## Save/Load

### NPC Faction Profile Persistence

```python
# Save
saved_state = {
    "npc_faction_profiles": {
        npc_id: {
            "narrative": str,
            "belonging": List[dict],
            "affinity": Dict,
            "affinity_overrides": Dict,
            "created_at_game_time": float,
            "created_from_metadata": dict
        }
    },
    "affinity_defaults": {
        "world": Dict,
        "nation": Dict[nation_id, Dict],
        # ... etc
    }
}

# Load
faction_system.restore_from_save(saved_state)
```

### Player Affinity Persistence

```python
player_state = {
    "affinity": Dict[tag, float],
    "traits": Dict[str, float]
}
```

---

## Summary of Key Distinctions

| Piece | Stable? | Per-NPC? | Mutable? | Source |
|-------|---------|----------|----------|--------|
| **Belonging** | ✅ Yes | ✅ Yes | ❌ No | NPC creation |
| **Narrative** | ✅ Yes | ✅ Yes | ❌ No | NPC creation |
| **Affinity (base)** | ✅ Yes | ❌ (hierarchy) | ✅ Via overrides | Affinity defaults |
| **Affinity (overrides)** | ❌ No | ✅ Yes | ✅ Yes | Quest completion + world events |
| **Player affinity** | ❌ No | ❌ (global) | ✅ Yes | Quest completion + NPC interactions |
| **Affinity defaults** | ❌ No | ❌ (config) | ✅ Yes | World events (admin) |

---

## Next: Configuration Files & TagRegistry API

(Awaiting bucket terms, then Phase 1 detailed design)
