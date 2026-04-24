# Retrieval Design & Tagging Strategy

**Companion to**: WORLD_MEMORY_SYSTEM.md, TRIGGER_SYSTEM.md, TIME_AND_RECENCY.md
**Status**: Design Phase

---

## 1. Tagging Strategy Overview

Every piece of data in the system carries tags in `category:value` format. Tags serve three purposes:
1. **Identity** — What is this entity/event/interpretation about?
2. **Routing** — Which entities/regions should care about this?
3. **Counting** — How do we group "similar" things for threshold triggers?

---

## 2. Layer 1 Tagging (Stat Tracker — Existing)

Layer 1 (stat_tracker.py) doesn't use explicit tags. It uses nested dict keys as implicit categories:

```
gathering_stats.iron_ore         → implicitly: event:gathering, resource:iron
combat_stats.wolf_kills          → implicitly: event:combat, species:wolf
crafting_stats.smithing_attempts → implicitly: event:crafting, domain:smithing
exploration_stats.chunks_visited → implicitly: event:exploration
```

### How Layer 1 Connects to Tags

A static lookup table maps stat keys to tag equivalents. This lets the query system bridge Layer 1 fast-path lookups with the tag-based architecture:

```python
STAT_KEY_TO_TAGS = {
    "combat_stats.total_kills": ["event:combat", "event:kill"],
    "combat_stats.wolf_kills": ["event:combat", "species:wolf"],
    "combat_stats.total_damage_dealt": ["event:combat", "metric:damage"],
    "gathering_stats.iron_ore": ["event:gathering", "resource:iron"],
    "gathering_stats.oak_log": ["event:gathering", "resource:oak"],
    "crafting_stats.smithing_attempts": ["event:crafting", "domain:smithing"],
    "crafting_stats.alchemy_attempts": ["event:crafting", "domain:alchemy"],
    "exploration_stats.chunks_visited": ["event:exploration"],
    # Pattern: "{category}_stats.{specific}" → ["event:{category}", "{detail_tag}"]
}
```

**No changes to stat_tracker.py.** This mapping lives in the query layer.

---

## 3. Layer 2 Tagging (Raw Events — Auto-Generated)

Every Layer 2 event gets tags auto-generated at recording time. This is the most critical tagging layer — it determines what entities notice what events.

### 3.1 The Auto-Tagging Pipeline

Tags are built from event data fields using a **field-to-tag derivation map**:

```python
# Always added: event type tag
tags = [f"event:{event.event_type}"]

# Field-to-tag derivation (data-driven, configurable)
FIELD_TAG_MAP = {
    # Field name in event.data    Tag prefix     Example output
    "resource_type":              "resource:",   # "resource:iron"
    "material_id":                "resource:",   # "resource:oak_log"
    "enemy_type":                 "species:",    # "species:wolf"
    "enemy_id":                   "species:",    # "species:wolf" (extracted)
    "weapon_type":                "combat:",     # "combat:melee"
    "damage_type":                "element:",    # "element:fire"
    "discipline":                 "domain:",     # "domain:smithing"
    "recipe_id":                  "domain:",     # "domain:smithing" (extracted)
    "skill_id":                   "skill:",      # "skill:fireball"
    "biome":                      "biome:",      # "biome:forest"
    "tier":                       "tier:",       # "tier:2"
    "npc_id":                     "npc:",        # "npc:gareth"
    "quest_id":                   "quest:",      # "quest:wolf_bounty"
}
```

### 3.2 Derived Tags (Computed, Not Direct)

Some tags can't be read from a single field — they're derived:

```python
def _derive_extra_tags(event: WorldMemoryEvent) -> List[str]:
    extra = []

    # Location tags (from geographic enrichment, already on the event)
    if event.locality_id:
        extra.append(f"location:{event.locality_id}")
    if event.district_id:
        extra.append(f"location:{event.district_id}")

    # Intensity tag (based on magnitude relative to tier norms)
    if event.magnitude > 0:
        tier = event.tier or 1
        tier_baseline = {1: 10, 2: 25, 3: 60, 4: 150}.get(tier, 10)
        ratio = event.magnitude / tier_baseline
        if ratio > 3.0:
            extra.append("intensity:extreme")
        elif ratio > 1.5:
            extra.append("intensity:heavy")
        elif ratio > 0.5:
            extra.append("intensity:moderate")
        else:
            extra.append("intensity:light")

    # Critical hit tag
    if event.result == "critical":
        extra.append("combat:critical")

    # Quality tag (for crafting)
    if event.quality:
        extra.append(f"quality:{event.quality}")

    return extra
```

### 3.3 Complete Example: A Wolf Kill Event

```python
# Bus event: ENEMY_KILLED
# data = {"enemy_id": "wolf_3", "enemy_type": "wolf", "tier": 1,
#          "damage_type": "physical", "weapon_type": "melee",
#          "position_x": 45.2, "position_y": 23.7, "biome": "forest"}

# Auto-generated tags:
tags = [
    "event:enemy_killed",          # From event_type
    "species:wolf",                # From enemy_type field
    "combat:melee",                # From weapon_type field
    "element:physical",            # From damage_type field
    "biome:forest",                # From biome field
    "tier:1",                      # From tier field
    "location:whispering_woods",   # From geographic enrichment
    "location:eastern_province",   # From geographic enrichment (district)
    "intensity:moderate",          # Derived from magnitude vs tier baseline
]
```

An NPC with tags `["species:wolf", "biome:forest", "concern:wildlife"]` would score high relevance for this event — they share `species:wolf` and `biome:forest`.

A blacksmith NPC with tags `["domain:smithing", "resource:iron"]` would score low — no tag overlap.

### 3.4 Tag Assignment for Different Event Types

| Event Type | Key Tags Generated | From Fields |
|------------|-------------------|-------------|
| enemy_killed | event:enemy_killed, species:X, combat:X, element:X, tier:X, biome:X, location:X | enemy_type, weapon_type, damage_type, tier, biome, locality |
| resource_gathered | event:resource_gathered, resource:X, biome:X, tier:X, location:X | resource_type/material_id, biome, tier, locality |
| craft_attempted | event:craft_attempted, domain:X, quality:X, tier:X, location:X | discipline, quality, tier, locality |
| damage_taken | event:damage_taken, species:X (attacker), element:X, intensity:X, location:X | attacker enemy_type, damage_type, magnitude, locality |
| skill_used | event:skill_used, skill:X, element:X, domain:X, location:X | skill_id, damage_type, tags from skill definition |
| npc_interaction | event:npc_interaction, npc:X, location:X | npc_id, locality |
| quest_completed | event:quest_completed, quest:X, npc:X, location:X | quest_id, quest_giver, locality |
| chunk_entered | event:chunk_entered, biome:X, location:X | biome, locality |
| level_up | event:level_up, event:progression | (minimal tags — affects player only) |
| trade_completed | event:trade_completed, npc:X, resource:X, location:X | npc_id, traded items, locality |

---

## 4. Layer 3 Tagging (Interpretations — Inherited + Derived)

Layer 3 interpretations get tags from TWO sources:

### 4.1 Inherited Tags (From Cause Events)

The interpretation inherits unique tags from its cause_event_ids — the Layer 2 events that formed the evidence:

```python
def inherit_tags_from_causes(cause_events: List[WorldMemoryEvent]) -> List[str]:
    """Collect unique tags across all cause events."""
    all_tags = set()
    for event in cause_events:
        all_tags.update(event.tags)

    # Remove overly specific tags (event IDs, exact positions)
    # Keep: species, resource, biome, location, domain, element, tier
    KEEP_CATEGORIES = {"species", "resource", "biome", "location", "domain",
                       "element", "tier", "combat", "npc", "quest"}
    filtered = [t for t in all_tags if t.split(":")[0] in KEEP_CATEGORIES]
    return filtered
```

### 4.2 Derived Tags (From Interpretation Properties)

```python
def derive_interpretation_tags(interp: InterpretedEvent,
                               envelope: TimeEnvelope) -> List[str]:
    """Add category, severity, and temporal tags."""
    tags = []

    # Category tag
    tags.append(f"interpretation:{interp.category}")
    # e.g., "interpretation:population_change"

    # Severity tag
    tags.append(f"severity:{interp.severity}")
    # e.g., "severity:major"

    # Temporal trend tag (from time envelope)
    if envelope:
        tags.append(f"trend:{envelope.trend}")
        # e.g., "trend:accelerating"

        # Timeframe tag
        if envelope.total_span < 3.0:
            tags.append("timeframe:recent")
        elif envelope.total_span < 14.0:
            tags.append("timeframe:ongoing")
        else:
            tags.append("timeframe:historical")

    # Scope tag (how many regions affected)
    region_count = (len(interp.affected_locality_ids) +
                    len(interp.affected_district_ids) +
                    len(interp.affected_province_ids))
    if region_count <= 1:
        tags.append("scope:local")
    elif region_count <= 5:
        tags.append("scope:district")
    else:
        tags.append("scope:regional")

    return tags
```

### 4.3 Complete Example: A Wolf Population Interpretation

```python
# Interpretation: "Wolf population declining in Whispering Woods"
affects_tags = [
    # Inherited from cause events (the wolf kill records):
    "species:wolf", "biome:forest", "location:whispering_woods",
    "combat:melee", "tier:1",
    # Derived from interpretation properties:
    "interpretation:population_change",
    "severity:significant",
    "trend:accelerating",
    "timeframe:ongoing",
    "scope:local",
]
```

Now when an NPC with `concern:wildlife` and `biome:forest` queries, this interpretation scores highly via tag matching.

---

## 5. Similarity Grouping for Threshold Counting

The trigger system (TRIGGER_SYSTEM.md §1.2) needs to count "similar" interpretations. Here's how tags enable that:

### 5.1 Similarity Key Extraction

```python
def get_similarity_key(interp: InterpretedEvent) -> Tuple[str, str, str]:
    """
    Extract a counting key from an interpretation.
    Key: (category, primary_entity_tag, primary_region)
    """
    # Primary entity tag: first non-location, non-interpretation tag
    primary_tag = "general"
    for tag in interp.affects_tags:
        cat = tag.split(":")[0]
        if cat in ("species", "resource", "domain", "npc", "quest"):
            primary_tag = tag
            break

    # Primary region: first affected locality (most specific)
    primary_region = (interp.affected_locality_ids[0]
                      if interp.affected_locality_ids else "global")

    return (interp.category, primary_tag, primary_region)
```

### 5.2 Example Counting

```
Interpretation 1: "Wolves thinning in Whispering Woods" → key: (population_change, species:wolf, whispering_woods)
Interpretation 2: "Wolf population still declining" → same key → count=2
Interpretation 3: "Wolves nearly gone from the area" → same key → count=3 → THRESHOLD HIT

Interpretation 4: "Iron deposits strained" → key: (resource_pressure, resource:iron, iron_hills) → count=1
Interpretation 5: "Iron becoming scarce" → same key → count=2
...
```

---

## 6. Detailed Retrieval Design

### 6.1 Retrieval Paths by Use Case

**Use Case A: "What does this NPC know?"**
```
1. EntityRegistry.get("npc_gareth") → entity with tags, position, home_region
2. entity.activity_log → last N events involving Gareth directly (Layer 2)
3. EventStore.query(near=gareth.position, radius=gareth.awareness_radius)
   → events nearby, filtered by calculate_relevance(gareth.tags, event.tags) > 0.2
4. AggregationManager.local_knowledge[gareth.home_region_id]
   → Layer 4 summary: "The Iron Hills are under resource pressure..."
5. AggregationManager.regional_knowledge[gareth.home_province_id]
   → Layer 5 summary (if significant events exist)
6. InterpretationStore.get_ongoing(gareth.home_region_id)
   → Active conditions, filtered by tag relevance to Gareth

Output: EntityQueryResult with all of the above assembled
```

**Use Case B: "Is this region in trouble?"**
```
1. EntityRegistry.get("region_whispering_woods") → region entity with tags
2. AggregationManager.local_knowledge["whispering_woods"]
   → ongoing_conditions + recent_interpretations + summary
3. InterpretationStore.query(locality_id="whispering_woods", ongoing_only=True)
   → All active issues in this area
4. EventStore.count_filtered(locality_id="whispering_woods", since=recent)
   → Raw event volume (is this area busy or quiet?)

Output: Region state with narrative summary + active conditions
```

**Use Case C: "What happened globally with wolves?"**
```
1. StatTracker.combat_stats.wolf_kills → fast total count (Layer 1)
2. InterpretationStore.query(category="population_change",
                             tag_filter="species:wolf")
   → All wolf-related interpretations (Layer 3)
3. For each interpretation: get TimeEnvelope → temporal context
4. DailyLedger query: days where enemy type included wolves
   → How many days had wolf combat?

Output: Cross-regional wolf impact analysis
```

**Use Case D: "What's the player been doing lately?"**
```
1. DailyLedger for last 7 days → activity summary per day
2. MetaDailyStats → current streaks, records
3. EntityRegistry.get("player").activity_log → recent direct events
4. InterpretationStore.query(category="player_milestone") → achievements
5. Player entity tags → current playstyle classification

Output: Player behavior profile with temporal context
```

### 6.2 The Catalog: How Retrieval Enables Counting

The retrieval system doubles as a **cataloging system** for trigger counting:

```
                     ┌──────────────────────────┐
                     │     EventStore (SQLite)    │
                     │                            │
                     │  event_tags table:          │
                     │    event_id | tag           │
                     │    ---------|--------       │
                     │    evt_001  | species:wolf  │
                     │    evt_001  | biome:forest  │
                     │    evt_002  | species:wolf  │
                     │    evt_002  | biome:forest  │
                     │    evt_003  | resource:iron │
                     │    ...                      │
                     └──────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    COUNT by tag combo   COUNT by region   COUNT by category
    "species:wolf" AND   "whispering_woods" "combat" events
    "biome:forest"       all event types    any region
         = 47                = 156              = 892
```

The SQL queries that power counting:

```sql
-- Count wolf kills in a specific locality
SELECT COUNT(*) FROM events e
JOIN event_tags t1 ON e.event_id = t1.event_id AND t1.tag = 'species:wolf'
WHERE e.event_type = 'enemy_killed'
AND e.locality_id = 'whispering_woods';

-- Count all combat events in a region (for regional accumulator)
SELECT COUNT(*) FROM events
WHERE event_type IN ('attack_performed', 'enemy_killed', 'damage_taken')
AND locality_id = 'whispering_woods';

-- Count interpretations by similarity key
SELECT COUNT(*) FROM interpretations i
JOIN interpretation_tags t ON i.interpretation_id = t.interpretation_id
WHERE i.category = 'population_change'
AND t.tag = 'species:wolf'
AND 'whispering_woods' IN (
    SELECT value FROM json_each(i.affected_locality_ids_json)
);
```

### 6.3 Query Composition: From Entity to Full Context

The complete query flow for an NPC dialogue system:

```
Input: "Generate dialogue for NPC Gareth"
    │
    ▼
Step 1: IDENTITY
    WorldQuery.query_entity("npc_gareth")
    → metadata: name, job, personality tags
    → 15-20 interest tags defining what he cares about
    │
    ▼
Step 2: DIRECT HISTORY
    Activity log → events where Gareth was actor or target
    → "Player traded 5 iron ingots to Gareth yesterday"
    → "Gareth repaired player's sword 3 days ago"
    │
    ▼
Step 3: NEARBY + RELEVANT (Interest-Filtered)
    Events within 32 tiles of Gareth, filtered by his tags:
    → Iron mining events (resource:iron matches his interests)
    → Smithing events (domain:smithing matches)
    → NOT wolf hunting events (no tag overlap with Gareth)
    │
    ▼
Step 4: LOCAL KNOWLEDGE (Layer 4)
    "The Iron Hills have seen heavy mining activity. Iron deposits
     are becoming strained. Trade has been brisk at the crossing."
    │
    ▼
Step 5: REGIONAL CONTEXT (Layer 5)
    "The Eastern Highlands are peaceful. Notable: iron scarcity
     spreading across multiple districts."
    │
    ▼
Step 6: ACTIVE CONDITIONS
    Ongoing interpretations matching Gareth's tags:
    → "Iron deposits strained in Iron Hills" (resource:iron match)
    → NOT "Wolf population declining" (no tag match for Gareth)
    │
    ▼
Step 7: TIME CONTEXT
    TimeEnvelope for iron gathering in Iron Hills:
    → trend: "accelerating", recent_rate: 12/day
    DailyLedger summary:
    → Player's been a heavy gatherer for 5 consecutive days
    │
    ▼
OUTPUT: Complete NPC context for LLM dialogue generation
```

### 6.4 Distance-Based Information Quality

When querying on behalf of an NPC, distance from an event's epicenter affects how much detail they know:

```python
def filter_by_distance_quality(entity: WorldEntity,
                                events: List[Dict],
                                interpretations: List[InterpretedEvent]
                                ) -> Tuple[List[Dict], List[str]]:
    """
    NPCs closer to events know more detail.
    Returns (filtered_events, narrative_summaries).
    """
    detailed = []
    summaries = []

    for interp in interpretations:
        dist = distance(entity.position_x, entity.position_y,
                       interp.epicenter_x, interp.epicenter_y)

        if dist < 16:  # Same locality (~1 chunk)
            # Full detail
            summaries.append(interp.narrative)
        elif dist < 48:  # Same district (~3 chunks)
            # Summary version — first sentence only
            summaries.append(interp.narrative.split(".")[0] + ".")
        elif dist < 100:  # Same province
            # Vague rumor
            summaries.append(f"Rumors suggest {interp.category.replace('_', ' ')} "
                           f"in a nearby area.")
        else:
            # Too far — NPC doesn't know
            pass

    return detailed, summaries
```

---

## 7. Tag Lifecycle Summary

```
GAME ACTION occurs
    │
    ▼
Layer 0 (Bus): No tags — ephemeral event
    │
    ▼
Layer 1 (StatTracker): Implicit tags via stat key structure
    │                   (unchanged, lookup table bridges to tag format)
    │
    ▼
Layer 2 (EventRecorder): AUTO-TAGGED from event data fields
    │   Tags: event:X, species:X, resource:X, biome:X, location:X, tier:X,
    │         combat:X, element:X, domain:X, intensity:X, quality:X
    │   Source: FIELD_TAG_MAP + derived tags
    │
    ▼
Layer 3 (Interpreter): INHERITED from Layer 2 causes + DERIVED from interpretation
    │   Inherited: species, resource, biome, location, domain, element, tier
    │   Derived: interpretation:category, severity:X, trend:X, timeframe:X, scope:X
    │
    ▼
Layer 4 (Local): Tags from Layer 3 interpretations in this region
    │   Used for: NPC interest filtering, condition matching
    │
    ▼
Layer 5 (Regional): Tags from notable Layer 3 interpretations
        Used for: Broad queries, cross-region trend detection
```

---

## 8. Open Design Questions

### 8.1 Tag Cardinality
How many tags per event is too many? Current estimate: 8-12 per Layer 2 event, 10-15 per Layer 3 interpretation. With 10K events that's 100K tag rows — SQLite handles this trivially.

### 8.2 Tag Evolution
Should NPC interest tags change based on world state? E.g., if iron becomes scarce, should Gareth gain `concern:iron_scarcity`? **Recommendation**: Yes, but slowly — update NPC tags when Layer 3 interpretations directly affect them. The `update_entity_tags()` method already supports this.

### 8.3 Custom Tags from LLM Interpreters
Should the LLM interpreter be allowed to generate NEW tags not in the predefined set? **Recommendation**: No — constrain to the known tag vocabulary. LLMs can choose from the vocabulary but not invent. This prevents tag drift and keeps matching reliable.

### 8.4 Tag Synonyms
"resource:iron_ore" vs "resource:iron" — should these match? **Recommendation**: Normalize at recording time. The derivation map should map "iron_ore" → "iron", "oak_log" → "oak", etc. One canonical tag per concept.
