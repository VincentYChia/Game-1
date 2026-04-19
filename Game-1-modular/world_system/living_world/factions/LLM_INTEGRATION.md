# Faction System LLM Integration

**Prompts, payloads, and integration points for LLM-driven features.**

---

## 1. NPC Dialogue Generation

### Overview

Generate contextual NPC dialogue based on faction standing, affinity, and location culture.

### Information Payload Structure

```json
{
  "npc": {
    "id": "smith_1",
    "name": "Thorin Ironforge",
    "narrative": "A master blacksmith from the northern mountains, skilled in forging weapons and armor. Known for his strict standards and high expectations.",
    "tags": [
      {
        "tag": "guild:smiths",
        "significance": 0.9,
        "role": "master",
        "narrative_hooks": [
          "Master craftsman with 20 years experience",
          "Runs the local smithy in Iron Hills",
          "Mentors young blacksmiths"
        ]
      },
      {
        "tag": "profession:blacksmith",
        "significance": 0.95,
        "role": "expert",
        "narrative_hooks": [
          "Specializes in weapon tempering",
          "Known for durability over decoration"
        ]
      },
      {
        "tag": "nation:stormguard",
        "significance": 0.6,
        "role": "supplier",
        "narrative_hooks": [
          "Supplies armor to Stormguard military",
          "Holds contract with kingdom"
        ]
      }
    ],
    "affinity_toward_player": 45,
    "affinity_with_tags": {
      "guild:merchants": -20,
      "profession:merchant": -15,
      "nation:blackoak": 10
    }
  },
  "player": {
    "id": "player_1",
    "character_name": "Aldric",
    "level": 12,
    "affinity_with_tags": {
      "guild:smiths": 60,
      "profession:blacksmith": 50,
      "nation:stormguard": 40,
      "guild:merchants": -10
    }
  },
  "location": {
    "address_tier": "district",
    "location_id": "district:iron_hills",
    "affinity_defaults": {
      "guild:smiths": 50,
      "profession:blacksmith": 45,
      "profession:miner": 30,
      "guild:merchants": -20
    }
  },
  "interaction_type": "greet",
  "context": {
    "time_of_day": "morning",
    "recent_events": ["player_completed_smithing_quest", "player_sold_low_quality_item"]
  }
}
```

### System Prompt (Template)

```
You are an NPC dialogue generator for a fantasy RPG faction system.

Your role:
- Generate immersive, contextual dialogue for NPCs based on their personality, faction roles, and the player's standing
- Respect the NPC's narrative and personality
- Reflect faction relationships and cultural attitudes
- Use affinity scores to determine tone (positive, neutral, negative)

Affinity Interpretation:
- Player affinity with NPC's tags: How well the player stands with the factions the NPC cares about
- NPC affinity toward player: Personal opinion of this specific player
- NPC affinity with tags: How this NPC personally feels about other factions
- Location affinity defaults: Cultural baseline attitudes in this region

Dialogue Guidelines:
- Keep responses conversational and natural (50-150 words)
- Match the NPC's personality and role
- Reference faction relationships when relevant
- Adjust tone based on affinity:
  * High affinity (>50): Warm, helpful, trusting
  * Mid affinity (0-50): Neutral, professional, cautious
  * Low affinity (<0): Cold, dismissive, cautious
- Use the NPC's narrative hooks when appropriate
- Consider location culture and time of day

Output Format:
Dialogue only, no narration or stage directions.
```

### User Prompt (Template)

```
Generate dialogue for the following NPC:

NPC: {npc.name} ({npc.id})
Narrative: {npc.narrative}

Factions: {formatted list of NPC's belonging tags with significance and roles}

Player Standing with NPC's Factions: {player affinity with relevant tags}
NPC's Personal Opinion of Player: {npc.affinity_toward_player}/100
NPC's Feelings About Other Factions: {npc.affinity_with_tags}

Location: {location.location_id}
Cultural Attitudes: {location.affinity_defaults}

Interaction: {interaction_type}
Context: {context events}

Generate natural dialogue for this NPC.
```

### Example Exchange

**System Prompt**: [As above]

**User Prompt**:
```
Generate dialogue for the following NPC:

NPC: Thorin Ironforge (smith_1)
Narrative: A master blacksmith from the northern mountains, skilled in forging weapons and armor. Known for his strict standards and high expectations.

Factions:
- guild:smiths (significance 0.9, role: master)
- profession:blacksmith (significance 0.95, role: expert)
- nation:stormguard (significance 0.6, role: supplier)

Player Standing with NPC's Factions:
- guild:smiths: 60 (positive)
- profession:blacksmith: 50 (positive)
- nation:stormguard: 40 (positive)

NPC's Personal Opinion of Player: 45/100 (likes the player)
NPC's Feelings About Other Factions:
- guild:merchants: -20
- profession:merchant: -15

Location: district:iron_hills
Cultural Attitudes:
- guild:smiths: 50
- profession:blacksmith: 45
- profession:miner: 30

Interaction: greet
Context: player completed smithing quest, sold low quality item

Generate natural dialogue for this NPC.
```

**LLM Response**:
```
*Thorin looks up from the anvil, wiping sweat from his brow*

Ah, Aldric! Good timing. I heard you completed that smithing contract—solid work, that. Shows you've got the discipline for craftsmanship. But I also heard you've been selling subpar gear to the merchants. *shakes head* That's not the way of a true craftsman. Quality is everything. You've earned my respect as a smith, but don't let the merchants' coin turn you away from your principles.

What brings you to the forge today?
```

### LLM Configuration

```python
backend = BackendManager.get_instance()

context = {
    "npc": faction_sys.get_npc_profile(npc_id),
    "player": {"affinity_with_tags": faction_sys.get_all_player_affinities(player_id)},
    "npc_opinion": faction_sys.get_npc_affinity_toward_player(npc_id),
    "location_affinity": faction_sys.compute_inherited_affinity(location_hierarchy)
}

dialogue = backend.generate_dialogue(
    model_type="dialogue_npc",  # Config-driven model selection
    system_prompt=DIALOGUE_SYSTEM_PROMPT,
    user_prompt=format_user_prompt(context),
    temperature=0.7,
    max_tokens=200
)
```

---

## 2. Location Affinity Defaults Generation

### Overview

Generate cultural affinity baselines for locations (how that region feels about different factions/professions).

### Information Payload Structure

```json
{
  "location": {
    "id": "district:iron_hills",
    "name": "Iron Hills",
    "tier": "district",
    "parent": "nation:stormguard",
    "description": "A mountainous district known for rich iron deposits and skilled metalworking. The population is primarily dwarven and human craftspeople.",
    "history": "Historic center of Stormguard's metalworking industry, home to master smiths and ore refineries.",
    "dominant_professions": ["blacksmith", "miner", "merchant"],
    "cultural_values": ["craftsmanship", "quality", "military strength"]
  },
  "tag_registry": [
    "guild:smiths",
    "guild:merchants",
    "profession:blacksmith",
    "profession:miner",
    "profession:guard",
    "nation:stormguard",
    "nation:blackoak"
  ],
  "parent_affinity_defaults": {
    "guild:smiths": 30,
    "profession:blacksmith": 20,
    "nation:stormguard": 40
  }
}
```

### System Prompt (Template)

```
You are a cultural attitudes generator for a fantasy RPG faction system.

Your role:
- Generate cultural affinity defaults for a location based on its description, history, and dominant factions
- Affinity represents how the local culture feels about each faction/profession
- Values range from -100 (hated) to +100 (loved)
- Default is 0 (neutral) for unspecified factions

Guidelines:
- High affinity (>30): Faction is valued, respected, or dominant in the region
- Mid affinity (0-30): Faction has some presence, neutral attitude
- Low affinity (<0): Faction is disliked, discouraged, or competing
- Be consistent with location description and history
- Consider parent region's baseline attitudes
- Only include non-zero values (sparse storage)

Output Format:
JSON object: {"faction_tag": affinity_value, ...}
```

### User Prompt (Template)

```
Generate cultural affinity defaults for the following location:

Location: {location.name} ({location.id})
Tier: {location.tier}
Description: {location.description}
History: {location.history}
Dominant Groups: {location.dominant_professions}
Values: {location.cultural_values}

Parent Region Baseline:
{parent_affinity_defaults formatted}

Available Tags:
{tag_registry}

Generate affinity values for each tag. Only include non-zero values.
Respond with JSON object only.
```

### Example Exchange

**System Prompt**: [As above]

**User Prompt**:
```
Generate cultural affinity defaults for the following location:

Location: Iron Hills (district:iron_hills)
Tier: district
Description: A mountainous district known for rich iron deposits and skilled metalworking. The population is primarily dwarven and human craftspeople.
History: Historic center of Stormguard's metalworking industry, home to master smiths and ore refineries.
Dominant Groups: blacksmith, miner, merchant
Values: craftsmanship, quality, military strength

Parent Region Baseline:
{
  "guild:smiths": 30,
  "profession:blacksmith": 20,
  "nation:stormguard": 40
}

Available Tags:
- guild:smiths
- guild:merchants
- profession:blacksmith
- profession:miner
- profession:guard
- nation:stormguard
- nation:blackoak

Generate affinity values for each tag. Only include non-zero values.
Respond with JSON object only.
```

**LLM Response**:
```json
{
  "guild:smiths": 50,
  "profession:blacksmith": 45,
  "profession:miner": 30,
  "profession:guard": 20,
  "nation:stormguard": 50,
  "guild:merchants": -20,
  "nation:blackoak": -15
}
```

### LLM Configuration

```python
backend = BackendManager.get_instance()

context = {
    "location": location_data,
    "tag_registry": tag_library.get_all_tags(),
    "parent_affinity": faction_sys.get_location_affinity_defaults(parent_tier, parent_id)
}

affinities = backend.generate_location_affinities(
    model_type="world_culture",
    system_prompt=LOCATION_SYSTEM_PROMPT,
    user_prompt=format_user_prompt(context),
    temperature=0.5,  # Lower temp for consistency
    max_tokens=500
)

# Parse JSON and store in database
for tag, value in json.loads(affinities).items():
    faction_sys.set_location_affinity_default(tier, location_id, tag, value)
```

---

## 3. NPC Creation

### Overview (Placeholder)

Generate NPC profiles with narrative, belonging tags, and initial affinity toward other tags.

### Information Payload Structure

```json
{
  "archetype": "master_craftsman",
  "faction_context": {
    "primary_faction": "guild:smiths",
    "location": "district:iron_hills",
    "location_affinity": {...}
  },
  "world_context": {
    "current_era": "age_of_rebuilding",
    "major_factions": ["nation:stormguard", "nation:blackoak", "guild:smiths"]
  }
}
```

### Implementation Status

**Currently Placeholder** — NPC creation is external to faction system.

**Future Integration**:
- Get archetype + location context
- Call LLM to generate narrative + tags
- Store via `faction_sys.add_npc()` and `faction_sys.add_npc_belonging_tag()`

---

## 4. Integration with BackendManager

### Using BackendManager for All LLM Calls

All faction system LLM operations should go through `BackendManager` for:
- Model selection (Ollama, Claude, Mock)
- Error handling and fallbacks
- Logging and debugging
- Configuration consistency

### Pattern

```python
from world_system.living_world.backends import BackendManager

backend = BackendManager.get_instance()

# Dialogue generation
response = backend.generate_dialogue(
    model_type="dialogue_npc",
    system_prompt="...",
    user_prompt="...",
    temperature=0.7,
    max_tokens=200
)

# Location affinity generation
response = backend.generate_location_affinities(
    model_type="world_culture",
    system_prompt="...",
    user_prompt="...",
    temperature=0.5,
    max_tokens=500
)
```

### BackendManager Configuration

(See `world_system/living_world/backends/README.md` for full details)

- Model type routing
- Fallback chains (Claude → Ollama → Mock)
- Temperature and max_tokens defaults
- Retry logic
- Logging

---

## 5. Prompt Templates (Quick Reference)

### Dialogue Generation
- **Temperature**: 0.7 (balanced creativity)
- **Max Tokens**: 200
- **Format**: Plain text dialogue

### Location Affinities
- **Temperature**: 0.5 (consistency)
- **Max Tokens**: 500
- **Format**: JSON object

### NPC Creation (Future)
- **Temperature**: 0.8 (creative narrative)
- **Max Tokens**: 1000+
- **Format**: JSON object

---

## 6. Testing & Validation

### Manual Testing

```python
# Test dialogue generation
faction_sys = FactionSystem.get_instance()
npc = faction_sys.get_npc_profile("smith_1")
player_aff = faction_sys.get_all_player_affinities("player_1")
npc_opinion = faction_sys.get_npc_affinity_toward_player("smith_1")
location = faction_sys.compute_inherited_affinity([
    ("locality", "westhollow"),
    ("district", "iron_hills"),
    ("nation", "nation:stormguard"),
    ("world", None)
])

context = {
    "npc": npc,
    "player_affinity": player_aff,
    "npc_opinion": npc_opinion,
    "location": location
}

# Call BackendManager
backend = BackendManager.get_instance()
dialogue = backend.generate_dialogue(
    system_prompt="...",
    user_prompt="...",
    temperature=0.7
)
print(f"Generated: {dialogue}")
```

### Validation Checks

- [ ] Affinity values within -100 to 100 range
- [ ] Dialogue text is natural and contextual
- [ ] Location affinities are sparse (only non-zero values)
- [ ] NPC personality reflected in dialogue
- [ ] Tone matches affinity levels

---

## 7. Debug Logging

All LLM calls should log:
- Input payload (context dict)
- System prompt used
- User prompt used
- Model type and parameters
- Output response
- Execution time

See `world_system/living_world/backends/` for logging configuration.

---

## 8. Next Steps

1. **Implement NPC dialogue integration** in npc_agent_system.py
2. **Wire BackendManager** into NPC dialogue generation
3. **Test with real LLM** (Claude via BackendManager)
4. **Validate affinity influence** on dialogue tone
5. **Implement location affinity generation** (optional Phase 4)
6. **Implement NPC creation** (optional Phase 5)
