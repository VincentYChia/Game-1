# Part 1: Architecture Overview & Layer Definitions

## Purpose

The World Memory System is the **information state layer** for the Living World. It records what happens, detects patterns, and organizes knowledge geographically — so that downstream systems (NPC agents, quest generators, ecosystem managers) can ask entity-first questions and get contextual answers.

This system is **narrative only**. It stores and interprets information. It does NOT apply mechanical game effects (damage numbers, stat changes, spawn rates). A separate system reads this information state and decides what game mechanics change.

## The Six Layers

```
Layer 5: Regional Events        ← Province/realm-level summaries
Layer 4: Local Events           ← Locality/district-level summaries
Layer 3: Interpreted Events     ← Pattern detection, narrative descriptions
─────────────────────────────────────────────────────────────
Layer 2: Raw Event Records      ← Structured facts in SQLite (NEW — this doc)
Layer 1: Raw Stat Tracking      ← Cumulative counters (EXISTING — stat_tracker.py)
Layer 0: Raw Actions            ← Ephemeral bus messages (EXISTING — event_bus.py)
```

The line between Layers 2 and 3 is the critical boundary. Below it: **facts** (immutable records of what happened). Above it: **interpretations** (derived meaning, narrative descriptions, aggregated knowledge).

### Layer 0: Raw Actions (Ephemeral)

**What**: The `GameEventBus` as it exists today. Every game action fires a pub/sub event. Visual systems, sound, UI subscribe for immediate reactions.

**Storage**: None. Events exist for one processing cycle then are gone.

**Role in this system**: Layer 0 is the **input stream**. The World Memory System subscribes to Layer 0 via `bus.subscribe("*", ...)` and selectively records meaningful events into Layer 2.

**No changes needed**. The bus works. We just add a new subscriber.

### Layer 1: Raw Stat Tracking (Existing, Unchanged)

**What**: The existing `stat_tracker.py` — 1,755 lines, ~1,000 cumulative counters organized into 14 categories (gathering, crafting, combat, exploration, time, records, etc.).

**Storage**: Serialized to JSON via the save system.

**Role in this system**: Layer 1 is a **fast-path for aggregate player queries**. "How many wolves has the player killed total?" is answered instantly from Layer 1 without scanning Layer 2. The World Memory System reads Layer 1 for quick checks but never writes to it.

**No changes needed**. stat_tracker.py stays exactly as-is.

### Layer 2: Raw Event Records (NEW — SQLite)

**What**: Every meaningful game action recorded as a structured fact with full spatial, temporal, and contextual data. Not every frame — only actions that change world state or are relevant to world knowledge.

**Storage**: SQLite database, one row per event. Indexed for fast spatial and temporal queries.

**Role in this system**: Layer 2 is the **world's factual memory**. It answers "what happened, where, when, involving whom?" These are immutable atomic facts — once written, they never change.

**Key distinction from Layer 1**: Layer 1 says "47 wolves killed." Layer 2 has 47 individual records, each with position, time, weapon used, wolf tier, nearby NPCs, player health at the time, etc.

**Retention**: Events are pruned over time using the milestone preservation policy (see Part 4). Old events are condensed but never fully lost — first occurrence, prime-number milestones, and timeline markers are always kept.

### Layer 3: Interpreted Events (NEW — SQLite)

**What**: Pattern-detected, threshold-triggered narrative descriptions derived from Layer 2 data. These are the "news stories" of the world.

**Storage**: SQLite, same database as Layer 2 but separate table.

**Examples**:
- "Wolf population declining in Whispering Woods" (wolf kills exceed spawn rate)
- "Iron deposits strained in Iron Hills" (gathering rate exceeds node respawn)
- "A prolific hunter roams the Eastern Highlands" (player combat events concentrated in region)
- "Forest fire has swept through the Northern Pines" (world event propagation)

**Key properties**:
- Each interpreted event has a **cause chain** (which Layer 2 events triggered it)
- Each has **affected tags** (what categories of entities/regions this concerns)
- Each is a **narrative text description**, NOT a JSON effect
- Each has a duration (ongoing vs. one-time) and severity
- Each is spatially anchored to one or more geographic regions

**Trigger mechanism**: The Interpreter checks Layer 2 at **prime-numbered occurrence counts** (see Part 5). The 1st wolf killed triggers interpretation. The 2nd, 3rd, 5th, 7th, 11th, 13th... also trigger. This creates heavy coverage at the start of any pattern with naturally thinning frequency.

### Layer 4: Local Events (NEW — In-Memory with SQLite Backup)

**What**: Per-locality and per-district aggregation of Layer 3 interpreted events. This is "what's happening in this immediate area" — what an NPC standing here would know from their surroundings.

**Storage**: Maintained in-memory as part of the geographic region state, backed to SQLite periodically.

**Contents per locality/district**:
- Recent interpreted events (static window + recency window — see Part 6)
- Ongoing conditions (active Layer 3 events with duration)
- Summary narrative: a compressed text description of current local conditions

**Updated when**: A new Layer 3 event is created or expires within this geographic area.

### Layer 5: Regional Events (NEW — In-Memory with SQLite Backup)

**What**: Per-province and per-realm aggregation. Broader patterns visible at a larger geographic scale. What a traveling merchant or regional authority would know.

**Storage**: Same as Layer 4 — in-memory with SQLite backup.

**Contents per province/realm**:
- Notable interpreted events from child localities (filtered by severity)
- Cross-locality trends ("iron scarce across all eastern districts")
- Regional summary narrative

**Updated when**: Layer 4 summaries change significantly in any child region.

## Data Flow — The Pipeline

```
GAME ACTION (player mines iron)
       │
       ▼
  Layer 0: GameEventBus.publish("RESOURCE_GATHERED", {...})
       │
       ├──→ [Existing systems: VFX, sound, UI]
       │
       ├──→ Layer 1: stat_tracker.record_resource_gathered(...)  [existing, unchanged]
       │
       └──→ Layer 2: EventRecorder.record(...)                   [NEW]
                │     Writes structured event to SQLite with
                │     geographic context (locality, district, province)
                │
                ▼
            Propagator                                            [NEW]
                │     Routes event to affected entities/regions
                │     Updates entity activity logs
                │     Checks: does this event's count hit a prime number?
                │
                ▼
            Interpreter (if prime trigger hit)                    [NEW]
                │     Evaluates patterns in Layer 2 data
                │     Generates narrative description if threshold met
                │     Creates Layer 3 interpreted event
                │
                ▼
            Aggregator                                            [NEW]
                │     Updates Layer 4 (local) for affected localities
                │     Updates Layer 5 (regional) if significant
                │
                ▼
            [Ready for downstream queries]
```

**Critical**: This pipeline runs at **write time**, not query time. By the time anything queries the system, data is already organized, propagated, and aggregated. Queries are fast reads, not expensive scans.

## Strict Layer Boundaries — No Circular Logic

```
WRITES FLOW DOWNWARD (through the pipeline):
  Layer 0 → Layer 2 → Layer 3 → Layer 4 → Layer 5

READS FLOW UPWARD (queries can read any layer):
  Downstream systems (NPC agents, quest gen) read Layers 1-5

THE GAME LOOP (not circular — this is normal gameplay):
  NPC agent reads Layers 2-5 → decides to act → action becomes Layer 0 event
  → flows through pipeline → becomes new Layer 2/3/4/5 data
```

Layer 3 NEVER directly triggers Layer 3. Layer 4 NEVER writes to Layer 2. The cycle goes through the **decision layer** (NPC AI, game systems), which is external to the data layers.
