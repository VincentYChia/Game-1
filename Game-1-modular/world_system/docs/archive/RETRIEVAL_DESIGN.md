# Data Retrieval Design

**Created**: 2026-03-24
**Scope**: How stored data is queried, assembled, and delivered to consumers (NPC agents, quest generators, content tools)

---

## The Retrieval Problem

Storage is solved — 7 layers of progressively compressed data in SQLite. The hard question: **when an NPC needs to talk, or a quest needs context, what data do you pull and from which layers?**

The answer is never "scan everything." It's always "start from the consumer's identity and radiate outward."

---

## Three Retrieval Pathways

### 1. Fast Path — Layer 1 Aggregates

**Use when**: You need a single number, fast. "How many wolves has the player killed?" "What's the player's level?" "Total crafts in smithing?"

**Source**: `stat_tracker.py` in-memory dicts. Zero SQL.

**Latency**: Microseconds.

**Consumers**: Unlock conditions, UI displays, evaluator context checks.

### 2. Narrative Path — Layers 3-5 Interpretations

**Use when**: You need to understand what's *happening* in a region, to an entity, or in the world. This is the primary path for NPC dialogue, quest generation, and content tools.

**How it works**: Entity-first query. Start from WHO is asking, radiate outward through WHERE they are and WHAT they care about.

**Latency**: Milliseconds (indexed SQL queries).

**Consumers**: NPC dialogue prompts, quest context, faction narrative, content generation.

### 3. Detail Path — Layer 2 Raw Events

**Use when**: You need specific timestamped facts. "What exactly happened at Iron Hills in the last 5 game-minutes?" Rare — mostly for evaluators building interpretations, not for end consumers.

**Source**: `events` table with indexed queries.

**Latency**: Milliseconds, but results can be large.

**Consumers**: Layer 3 evaluators, debug/audit, specific detail-drill situations.

---

## Entity-First Query Architecture

**Core principle**: Never search events directly. Find the entity, then radiate outward through their location and interests.

### What is an Entity?

Anything that can be a subject or consumer of information:
- **Player** — the human's character
- **NPC** — a named character in the world
- **Region** — a locality, district, or province (geographic entities have state too)
- **Faction** — an organization with interests and territory

### Entity Identity = Tags

An entity's tags define what information is relevant to them. Tags are overapplied by design — better to match too broadly and filter than to miss something relevant.

```
blacksmith_01 tags:
  job:blacksmith, domain:smithing, domain:metals, concern:resources,
  location:central_forge, faction:crafters_guild, preference:quality_work

village_guard_captain tags:
  job:guard, domain:combat, concern:safety, concern:law,
  location:guard_barracks, faction:village_guard, preference:order
```

### Query Flow

```
Consumer requests context for entity "blacksmith_01"
    │
    ▼
1. Load entity tags: [job:blacksmith, domain:smithing, domain:metals, ...]
    │
    ▼
2. Determine location: locality "central_forge" → district "central" → province "heartlands"
    │
    ▼
3. Query Layer 3-5 interpretations:
   a. In this entity's locality (full detail)
   b. In this entity's district (severity >= moderate)
   c. In this entity's province (severity >= significant)
   d. World-level (Layer 7 active threads, severity >= major)
    │
    ▼
4. Score results by tag relevance:
   - "Iron ore is scarce in Iron Hills" → matches domain:metals, concern:resources → HIGH
   - "Wolf population declining in Old Forest" → matches nothing → LOW
   - "Player crafted a masterwork longsword" → matches domain:smithing → HIGH
   - "Eastern Caves are dangerous" → matches concern:safety weakly → LOW
    │
    ▼
5. Apply dual window:
   - Take all results from the last N game-time units (recency window)
   - If fewer than K results, backfill from history (static minimum)
   - Default: recency=5.0 game-time, static_min=10 items
    │
    ▼
6. Return top-ranked results (max M items for prompt assembly)
   - Default: M=5 for NPC dialogue, M=10 for quest generation
```

### Tag Relevance Scoring

Each tag on a query result is compared against the consumer entity's tags. Scoring rules:

| Match Type | Score | Example |
|-----------|:---:|---------|
| Exact tag match | 1.0 | Entity has `domain:smithing`, result tagged `domain:smithing` |
| Same category, different value | 0.3 | Entity has `domain:smithing`, result tagged `domain:alchemy` |
| Related concern | 0.5 | Entity has `concern:resources`, result tagged `resource:iron_ore` |
| Geographic proximity | 0.2-0.8 | Same locality=0.8, same district=0.5, same province=0.2 |
| No match | 0.0 | No overlapping tags |

Final score = max(tag_scores) × geographic_proximity_bonus. Results sorted by score descending.

---

## Distance-Based Information Quality

When retrieving narrative threads (Layer 7) or interpretations for entities far from the event source, the retrieved text is **filtered by distance**, not served raw.

```
Distance from source       Information quality
─────────────────────────────────────────────────────
Same locality (0)          Full detail, accurate, emotional
Adjacent localities (1-2)  Good detail, mostly accurate
Same district (3-5)        Summary, some compression
Adjacent district (6-10)   Key facts only, details lost
Same province (10-15)      Rumor — vague, possibly distorted
Cross-province (15+)       May not have heard at all (unless significance > 0.8)
```

**This is not lying — it's information compression.** An NPC 50 tiles from a battle doesn't know if 100 or 200 wolves died. They just know "something happened with wolves out that way."

**Personality filters the version further**:
- A scholar NPC presents facts precisely
- A merchant focuses on economic impact
- A gossip NPC exaggerates
- A guard focuses on safety implications

---

## What Each Consumer Gets

### NPC Dialogue — ~500 token context budget

```
System prompt receives:
  1. NPC personality + voice                          (~100 tokens, static)
  2. Relationship state + emotion                     (~30 tokens)
  3. Top 5 knowledge items (tag-scored, distance-filtered)  (~150 tokens)
  4. Rolling conversation summary                     (~100 tokens)
  5. Faction reputation with this NPC's faction        (~20 tokens)

User prompt receives:
  1. Player's words                                   (~50 tokens)
  2. Player level/class/title                         (~20 tokens)
  3. 2-3 local conditions (from entity query)         (~60 tokens)
```

The key insight: **don't dump everything in**. Score available context by the NPC's personality tags, pick the 3-5 most relevant items. Small models (Ollama 8B) degrade fast with long prompts.

### Quest Generation — ~1000 token context budget

```
  1. Player profile (computed from Layer 1+3 data)    (~100 tokens)
  2. Active narrative threads relevant to area         (~200 tokens)
  3. Province summary (Layer 5)                        (~100 tokens)
  4. Faction standings                                 (~50 tokens)
  5. Recent notable events (Layer 4 connected)         (~200 tokens)
  6. Resource scarcity data                            (~50 tokens)
  7. Pacing state (recent quest types, cooldowns)     (~100 tokens)
```

### Content Generation (hostiles, materials, etc.) — ~500 token context budget

```
  1. Target region biome + tier                        (~30 tokens)
  2. Active narrative threads for this region          (~200 tokens)
  3. Province summary (Layer 5)                        (~100 tokens)
  4. Existing content in area (avoid duplicates)       (~100 tokens)
  5. World tone + themes (Layer 7)                     (~50 tokens)
```

---

## Gossip Propagation (Write-Time Retrieval)

Not all retrieval is on-demand. Some data is pushed to consumers at write time.

When a Layer 3+ interpretation is created, the gossip system delivers it to relevant NPCs based on:
1. **Geographic proximity** — closer NPCs hear sooner
2. **Interest tags** — NPCs only absorb gossip matching their `gossip_interests`
3. **Significance threshold** — only events above significance 0.1 propagate
4. **Time delay** — news travels with distance

| Distance | Delay | Detail Level |
|----------|-------|-------------|
| Same locality | Immediate | Full narrative text |
| Adjacent localities | ~60 game-seconds | Full narrative text |
| Same district | ~180 game-seconds | Summary version |
| Cross-district | ~420 game-seconds | Key fact only |

Gossip entries land in `npc_memory.knowledge_json` with a timestamp. When the NPC prompt is built, recent gossip is marked `[recent]` and old gossip is `[old]` — enabling "I just heard that..." vs stale references.

---

## Query API Summary

```python
# Entity-first query (the primary interface)
WorldQuery.query_entity(entity_id) -> EntityQueryResult
  .nearby_relevant_events      # Layer 2 events near entity, filtered by tags
  .local_context               # Region state for entity's locality
  .ongoing_conditions          # Active Layer 3 interpretations matching entity tags
  .connected_patterns          # Layer 4 connected interpretations (NEW)
  .province_summary            # Layer 5 summary for entity's province (NEW)

# Location-first query
WorldQuery.query_location(region_id) -> LocationQueryResult
  .active_conditions           # Layer 3 ongoing interpretations
  .recent_events               # Recent Layer 2 events
  .resource_state              # Ecosystem depletion data
  .connected_patterns          # Layer 4 connections involving this location

# World-level query
WorldQuery.query_world() -> WorldQueryResult
  .active_threads              # Layer 7 narrative threads
  .realm_state                 # Layer 6 summary
  .global_conditions           # Layer 3+ severity >= "major"

# Direct layer queries (for evaluators)
EventStore.query(event_type=..., locality_id=..., since_game_time=...) -> List[WorldMemoryEvent]
EventStore.query_interpretations(category=..., severity_min=...) -> List[InterpretedEvent]
EventStore.query_connected(district_id=...) -> List[ConnectedInterpretation]  # NEW
```

---

## Caching Strategy

| Data | Cache Type | Invalidation |
|------|-----------|-------------|
| Entity tags | In-memory dict | On entity update |
| Geographic lookup (position → region) | In-memory with LRU | Never (static map) |
| Layer 1 stats | In-memory (stat_tracker) | On every event (live) |
| Layer 3 ongoing interpretations per region | In-memory dict | On interpretation create/expire |
| Layer 5 province summaries | In-memory, 1 per province | On summary update |
| Layer 7 world state | In-memory singleton | On narrative update |
| NPC knowledge | In-memory (NPCMemory) | On gossip delivery |

Most query paths hit in-memory caches. SQLite is the persistence layer and the source for historical queries, but hot data lives in Python dicts.
