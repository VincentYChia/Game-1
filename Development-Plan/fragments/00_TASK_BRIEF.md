# TASK BRIEF — World Memory System Design

## What This Document Captures
All user feedback, design decisions, and constraints collected across multiple sessions.
This is the source of truth for writing the implementation plan.

## User's Layer Structure (FINAL)
- Layer 0: Raw actions (GameEventBus, ephemeral, in-memory only)
- Layer 1: Raw stat tracking (existing stat_tracker.py — 1,755 lines, ~1,000 counters)
- Layer 2: Raw event tracking (NEW — SQLite, structured events with spatial/temporal context)
- Layer 3: Interpreted events (NEW — pattern detection, narrative descriptions)
- Layer 4: Local events (NEW — per-locality/district aggregation)
- Layer 5: Regional events (NEW — per-province/realm aggregation)

## User's Specific Design Decisions

### 1. Interest Tags = Identity
- Tags are the DEFAULT search mechanism for any entity
- OVERAPPLY tags: species, location, affiliation, job, tendency, hobby, preference, etc.
- Must be unique and specific enough to distinguish entities
- Not a filter/stopper — this IS how you find and understand what an entity cares about

### 2. Static Window + Recency Window (Event Retrieval)
- Static window = fixed size (e.g., 10 events)
- Recency window = recent time period
- If fewer recent events than static window → backfill from history
- If more recent events than static window → capture ALL recent
- This ensures you always have enough context, never too little

### 3. Threshold Sequence Triggers for Interpreter
- Interpreter fires at threshold occurrences: 1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
- NOT exponential (too sparse at high counts)
- NOT every occurrence (too expensive)
- Heavy skew toward beginning (1st, 3rd, 5th all trigger)
- A trigger does NOT mean change — ignoring is valid
- Dual-track: individual event streams + regional accumulators
- Pass-through cascade: each layer can generate, ignore, or escalate
- Interpreters are LLMs: tiny at Layer 3, bigger at Layer 5
- Early game templates for count=1 events (no LLM needed)
- See `TRIGGER_SYSTEM.md` for full design

### 4. Geographic System — Scalable
- Static map defined and addable, OR procedural at world creation
- Address hierarchy: Realm > Province > District > Locality
- Everything except Realm indexed by tile position bounds
- Realm uses named keys (not position indices) for future expansion
- Named regions superimposed on existing 16x16 chunk grid

### 5. Event Pruning with Milestone Preservation
- ALWAYS keep: first occurrence of any event type per entity/location
- ALWAYS keep: events at threshold counts (1, 3, 5, 10, 25, 50, 100, 250, 500, 1000...)
- ALWAYS keep: power-of-10 milestones (100th, 1000th, 10000th)
- ALWAYS keep: events that triggered Layer 3 interpretations
- KEEP: longitude/timeline markers (spread across time to preserve temporal shape)
- PRUNE: everything else after configurable age threshold
- Example: 10,000 oak logs harvested → keep 1st, primes, 100th, 1000th, 10000th, plus timeline samples

### 6. Event Propagation is NARRATIVE ONLY
- NOT JSON effects like {"wood": -0.8}
- Text descriptions: "A fire has swept through the Northern Pines, consuming woodland"
- This layer is INFORMATION STATE only
- Mechanical effects applied by a SEPARATE system reading this information
- The memory system records what happened and what it means, not what game stats change

### 7. Entity-First Query Pattern
- Start from the entity being asked about (not from events)
- Get entity metadata, location, interest tags
- Fan out: find relevant events by proximity + recency
- For named regions: map region name to geographic position for proximity calc
- Provide: recent events + historical context (static+recency window)

### 8. Query Examples (User-Specified)
- "Near the blacksmith?" → blacksmith metadata → location → all layers sorted by proximity → recency
- "Player killing wolves?" → player stats (L1) → recent kills (L2) → interpreted events (L3)
- "Iron scarce in eastern forest?" → forest metadata → spawn rates → harvest rates → events
- "What does NPC know?" → NPC metadata → interests → nearby events filtered by interests

## Existing Codebase Patterns (Must Match)

### Singleton Pattern
```python
class MySystem:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

### Serialization Pattern
```python
def to_dict(self) -> Dict[str, Any]: ...

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> 'MyClass': ...
```

### EventBus API
```python
bus = GameEventBus.get_instance()
bus.subscribe("EVENT_TYPE", handler, priority=0)
bus.publish("EVENT_TYPE", {"key": "value"}, source="system_name")
```

### Config Pattern
```python
class Config:
    CONSTANT_NAME = value  # Class variable, no instances
```

### File Conventions
- Enums use string values matching JSON keys
- Type hints everywhere: Optional[T], Dict[K, V], List[T], Tuple[int, int]
- Error handling: try/except with print fallback
- Debug output: print(f"✓ Loaded X items") or print(f"⚠ Error: {e}")

## Existing Infrastructure to Build On
- GameEventBus: events/event_bus.py (195 lines, working)
- StatTracker: entities/components/stat_tracker.py (1,755 lines, working)
- WorldSystem: systems/world_system.py (1,126 lines, 16x16 chunks)
- BiomeGenerator: systems/biome_generator.py (deterministic, Szudzik pairing)
- Position: data/models/world.py (x, y, z float coords)
- ChunkType enum: 12 biome types (peaceful/dangerous/rare × forest/quarry/cave + water types)
- SaveManager: systems/save_manager.py (JSON serialization)
- NPC Database: data/databases/npc_db.py (static positions, no memory)

## What This System Does NOT Do
- Does NOT replace stat_tracker.py (Layer 1 stays as-is)
- Does NOT modify any existing game content JSON
- Does NOT apply mechanical game effects (narrative only)
- Does NOT replace the GameEventBus (subscribes to it)
- Does NOT handle NPC dialogue generation (downstream consumer)
- Does NOT handle quest generation (downstream consumer)

## From Scratchpad (Carry Forward)
- Narrative threads with canonical_facts + distance-based distortion
- Two usage modes: Reactive (bottom-up) + Thematic (top-down injection)
- NPCs have beliefs, not facts
- Information flows as compressed narrative units
- Gossamer/DF-inspired gossip propagation
- PlayerProfile computed from behavior (not stored directly)
- Research sources: Gossamer, DF rumors, Talk of the Town, PAN world model, SLM task decomposition
