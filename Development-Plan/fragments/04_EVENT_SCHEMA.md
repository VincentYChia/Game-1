# Part 4: Event Schema, Recording Pipeline, Retention Policy

## Layer 2 Event Schema

Every meaningful game action becomes a structured record. This is the world's factual memory.

```python
@dataclass
class WorldMemoryEvent:
    """Atomic unit of world memory — one thing that happened."""

    # Identity
    event_id: str                     # UUID (generated at creation)
    event_type: str                   # EventType enum value
    event_subtype: str                # Specific action: "mined_iron", "killed_wolf", "crafted_sword"

    # WHO
    actor_id: str                     # Entity ID: "player", "npc_gareth", "enemy_wolf_pack_3"
    actor_type: str                   # "player", "npc", "enemy", "system"
    target_id: Optional[str]          # What was acted upon (entity ID, resource ID, recipe ID)
    target_type: Optional[str]        # "enemy", "resource", "item", "npc", "station"

    # WHERE (position + geographic context)
    position_x: float
    position_y: float
    chunk_x: int                      # Derived: int(position_x) // 16
    chunk_y: int                      # Derived: int(position_y) // 16
    locality_id: Optional[str]        # From geographic registry (cached per chunk)
    district_id: Optional[str]        # Parent of locality
    province_id: Optional[str]        # Parent of district
    biome: str                        # ChunkType value at this position

    # WHEN
    game_time: float                  # In-game timestamp
    real_time: float                  # Wall clock (time.time()) for debugging
    session_id: str                   # Which play session

    # WHAT HAPPENED
    magnitude: float                  # Primary numeric value (damage, quantity, gold, etc.)
    result: str                       # "success", "failure", "critical", "dodge", "blocked"
    quality: Optional[str]            # "normal", "fine", "superior", "masterwork", "legendary"
    tier: Optional[int]               # T1-T4 of involved item/resource/enemy

    # TAGS — for matching against entity interests
    tags: List[str]                   # Same tag format as entity tags
                                      # e.g., ["event:gathering", "resource:iron", "biome:quarry",
                                      #         "tool:pickaxe", "tier:2"]

    # CONTEXT SNAPSHOT (what was true at this moment)
    context: Dict[str, Any]           # Flexible dict for event-type-specific data
                                      # Examples:
                                      #   combat: {"weapon": "iron_sword", "enemy_tier": 2,
                                      #            "player_health_pct": 0.7, "combo_count": 3}
                                      #   gathering: {"tool": "steel_pickaxe", "node_remaining_pct": 0.4,
                                      #               "rare_drop": false}
                                      #   crafting: {"recipe_id": "iron_sword_001", "discipline": "smithing",
                                      #              "minigame_score": 0.85, "materials_consumed": {...}}

    # INTERPRETATION TRACKING
    interpretation_count: int = 0     # How many times this event TYPE+subtype has occurred for this actor
                                      # Used for prime number trigger checking
    triggered_interpretation: bool = False  # Did this event trigger a Layer 3 interpretation?
```

## Event Types

```python
class EventType(Enum):
    """All trackable event types. Maps to GameEventBus event names."""

    # Combat
    ATTACK_PERFORMED = "attack_performed"
    DAMAGE_TAKEN = "damage_taken"
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DEATH = "player_death"
    DODGE_PERFORMED = "dodge_performed"
    STATUS_APPLIED = "status_applied"
    COMBO_PERFORMED = "combo_performed"

    # Gathering
    RESOURCE_GATHERED = "resource_gathered"
    NODE_DEPLETED = "node_depleted"

    # Crafting
    CRAFT_ATTEMPTED = "craft_attempted"
    ITEM_INVENTED = "item_invented"
    RECIPE_DISCOVERED = "recipe_discovered"

    # Economy/Inventory
    ITEM_ACQUIRED = "item_acquired"
    ITEM_CONSUMED = "item_consumed"
    ITEM_EQUIPPED = "item_equipped"
    TRADE_COMPLETED = "trade_completed"
    REPAIR_PERFORMED = "repair_performed"

    # Progression
    LEVEL_UP = "level_up"
    SKILL_LEARNED = "skill_learned"
    SKILL_USED = "skill_used"
    TITLE_EARNED = "title_earned"
    CLASS_CHANGED = "class_changed"

    # Exploration
    CHUNK_ENTERED = "chunk_entered"
    LANDMARK_DISCOVERED = "landmark_discovered"
    DUNGEON_ENTERED = "dungeon_entered"
    DUNGEON_COMPLETED = "dungeon_completed"

    # Social
    NPC_INTERACTION = "npc_interaction"
    QUEST_ACCEPTED = "quest_accepted"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"

    # World/System
    WORLD_EVENT = "world_event"       # Forest fire, invasion, etc.
    POSITION_SAMPLE = "position_sample"  # Periodic breadcrumb (every ~10s)
```

## Event Recording Pipeline

### The EventRecorder

Subscribes to Layer 0 (GameEventBus) and writes to Layer 2 (SQLite):

```python
class EventRecorder:
    """
    Subscribes to GameEventBus, converts bus events to WorldMemoryEvents,
    enriches with geographic context, writes to SQLite.
    Singleton.
    """
    _instance = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None  # SQLite backend
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.session_id: str = ""

        # Occurrence counters: (actor_id, event_type, event_subtype) → count
        self._occurrence_counts: Dict[Tuple[str, str, str], int] = {}

        # Primes cache for trigger checking
        self._primes_cache: Set[int] = set()
        self._generate_primes(10000)  # Pre-generate primes up to 10K

    def initialize(self, event_store: 'EventStore',
                   geo_registry: 'GeographicRegistry',
                   entity_registry: 'EntityRegistry',
                   session_id: str):
        """Wire up dependencies and subscribe to bus"""
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.session_id = session_id

        # Subscribe to all bus events
        bus = GameEventBus.get_instance()
        bus.subscribe("*", self._on_bus_event, priority=-10)  # Low priority = runs after game logic

        # Load occurrence counts from database
        self._load_occurrence_counts()

    def _on_bus_event(self, event: 'GameEvent'):
        """Convert a GameEventBus event to a WorldMemoryEvent and record it"""
        # Filter: not all bus events are worth recording
        if not self._should_record(event):
            return

        memory_event = self._convert_event(event)
        if memory_event is None:
            return

        # Enrich with geographic context
        self._enrich_geographic(memory_event)

        # Update occurrence count
        count_key = (memory_event.actor_id, memory_event.event_type, memory_event.event_subtype)
        self._occurrence_counts[count_key] = self._occurrence_counts.get(count_key, 0) + 1
        memory_event.interpretation_count = self._occurrence_counts[count_key]

        # Check if this count is a prime number (trigger interpretation)
        count = memory_event.interpretation_count
        if count == 1 or count in self._primes_cache:
            memory_event.triggered_interpretation = True

        # Write to SQLite
        self.event_store.record(memory_event)

        # Update entity activity logs
        self._update_activity_logs(memory_event)

        # If interpretation triggered, notify the Interpreter
        if memory_event.triggered_interpretation:
            self._notify_interpreter(memory_event)

    def _should_record(self, event: 'GameEvent') -> bool:
        """Filter bus events — skip visual-only events, high-frequency noise"""
        # Always skip
        skip_types = {"SCREEN_SHAKE", "PARTICLE_BURST", "FLASH_ENTITY",
                      "ATTACK_PHASE"}  # Per-frame visual updates
        if event.event_type in skip_types:
            return False

        # Position samples: only record periodically (handled by separate timer)
        if event.event_type == "POSITION_SAMPLE":
            return True  # These are already rate-limited by the caller

        return True

    def _convert_event(self, event: 'GameEvent') -> Optional[WorldMemoryEvent]:
        """Convert GameEvent to WorldMemoryEvent with proper field mapping"""
        data = event.data

        # Build tags from event data
        tags = self._build_event_tags(event)

        return WorldMemoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=event.event_type.lower(),
            event_subtype=self._derive_subtype(event),
            actor_id=data.get("actor_id", data.get("attacker_id", "player")),
            actor_type=data.get("actor_type", "player"),
            target_id=data.get("target_id", data.get("enemy_id", None)),
            target_type=data.get("target_type", None),
            position_x=data.get("position_x", data.get("position", {}).get("x", 0)),
            position_y=data.get("position_y", data.get("position", {}).get("y", 0)),
            chunk_x=0, chunk_y=0,  # Filled by _enrich_geographic
            locality_id=None, district_id=None, province_id=None,
            biome=data.get("biome", "unknown"),
            game_time=data.get("game_time", 0.0),
            real_time=event.timestamp,
            session_id=self.session_id,
            magnitude=data.get("amount", data.get("quantity", data.get("value", 0.0))),
            result=data.get("result", data.get("outcome", "success")),
            quality=data.get("quality", None),
            tier=data.get("tier", None),
            tags=tags,
            context=self._extract_context(event)
        )

    def _enrich_geographic(self, event: WorldMemoryEvent):
        """Stamp geographic IDs from position"""
        event.chunk_x = int(event.position_x) // 16
        event.chunk_y = int(event.position_y) // 16
        address = self.geo_registry.get_full_address(event.position_x, event.position_y)
        event.locality_id = address.get("locality")
        event.district_id = address.get("district")
        event.province_id = address.get("province")

    def _build_event_tags(self, event: 'GameEvent') -> List[str]:
        """Generate interest-matching tags from event data"""
        tags = [f"event:{event.event_type.lower()}"]
        data = event.data

        # Resource tags
        if "resource_type" in data:
            tags.append(f"resource:{data['resource_type']}")
        if "material_id" in data:
            tags.append(f"resource:{data['material_id']}")

        # Combat tags
        if "damage_type" in data:
            tags.append(f"element:{data['damage_type']}")
        if "weapon_type" in data:
            tags.append(f"combat:{data['weapon_type']}")
        if data.get("is_crit"):
            tags.append("combat:critical")

        # Tier tags
        if "tier" in data:
            tags.append(f"tier:{data['tier']}")

        # Biome tags
        if "biome" in data:
            tags.append(f"biome:{data['biome']}")

        # Discipline tags
        if "discipline" in data:
            tags.append(f"domain:{data['discipline']}")

        # Existing game tags (from the tag system)
        if "tags" in data and isinstance(data["tags"], list):
            for tag in data["tags"]:
                if ":" not in tag:
                    tags.append(f"game:{tag}")
                else:
                    tags.append(tag)

        return tags

    def _update_activity_logs(self, event: WorldMemoryEvent):
        """Append event to relevant entity activity logs"""
        registry = self.entity_registry

        # Actor's log
        actor_entity = registry.get(event.actor_id)
        if actor_entity:
            actor_entity.activity_log.append(event.event_id)
            if len(actor_entity.activity_log) > actor_entity.activity_log_max:
                actor_entity.activity_log.pop(0)

        # Target's log
        if event.target_id:
            target_entity = registry.get(event.target_id)
            if target_entity:
                target_entity.activity_log.append(event.event_id)
                if len(target_entity.activity_log) > target_entity.activity_log_max:
                    target_entity.activity_log.pop(0)

        # Region's log (the locality where this happened)
        if event.locality_id:
            region_entity = registry.get(f"region_{event.locality_id}")
            if region_entity:
                region_entity.activity_log.append(event.event_id)
                if len(region_entity.activity_log) > region_entity.activity_log_max:
                    region_entity.activity_log.pop(0)

    def _generate_primes(self, up_to: int):
        """Sieve of Eratosthenes for prime trigger checking"""
        sieve = [True] * (up_to + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(up_to ** 0.5) + 1):
            if sieve[i]:
                for j in range(i * i, up_to + 1, i):
                    sieve[j] = False
        self._primes_cache = {i for i, is_prime in enumerate(sieve) if is_prime}
```

### Bus-to-Memory Event Mapping

How existing GameEventBus events map to WorldMemoryEvents:

| Bus Event | Memory Event Type | Key Data Extracted |
|-----------|------------------|-------------------|
| `DAMAGE_DEALT` | `attack_performed` | amount, damage_type, target_id, is_crit, weapon |
| `PLAYER_HIT` | `damage_taken` | amount, damage_type, attacker_id |
| `ENEMY_KILLED` | `enemy_killed` | enemy_id, tier, position, loot |
| `PLAYER_DIED` | `player_death` | killer_id, position |
| `DODGE_PERFORMED` | `dodge_performed` | success (was i-frame hit?) |
| `RESOURCE_GATHERED` | `resource_gathered` | resource_id, quantity, tool, position |
| `ITEM_CRAFTED` | `craft_attempted` | recipe_id, quality, discipline, success |
| `SKILL_ACTIVATED` | `skill_used` | skill_id, tags, mana_cost, targets |
| `LEVEL_UP` | `level_up` | new_level, stat_points |
| `EQUIPMENT_CHANGED` | `item_equipped` | slot, item_id, old_item_id |

Events not currently published by the bus but needed:
- `QUEST_ACCEPTED`, `QUEST_COMPLETED` — add publishing to quest_system.py
- `NPC_INTERACTION` — add publishing to NPC dialogue handling
- `TRADE_COMPLETED` — add publishing to trade system
- `CHUNK_ENTERED` — add publishing to world_system.py chunk loading

## Retention Policy — Milestone Preservation

### The Problem

At 2,000-5,000 events per hour of play, a 100-hour save would have 200K-500K events. Most are routine (mined ore, killed wolf, walked to chunk). Keeping everything forever wastes space and slows queries.

### The Solution: Keep Milestones, Prune Routine

For each unique combination of `(actor_id, event_type, event_subtype)`:

**Always Keep:**
1. **First occurrence** — the very first event of this type (historical baseline)
2. **Prime-indexed events** — every event whose occurrence count is a prime number (these are the interpretation triggers). Sequence: 1st, 2nd, 3rd, 5th, 7th, 11th, 13th, 17th, 19th, 23rd, 29th, 31st...
3. **Power-of-10 milestones** — 100th, 1000th, 10000th occurrence
4. **Events that triggered interpretations** — any event where `triggered_interpretation = True`
5. **Events referenced by Layer 3** — any event_id in an interpreted event's cause chain

**Timeline Markers (Longitude Data):**
6. **One event per time window** — keep at least one event per configurable time interval (e.g., per game-day or per real-hour) to preserve the temporal shape. If the player mined 200 iron in one game-day, we keep one representative from that day even if its index number isn't prime.

**Prune:**
Everything else, after a configurable age threshold (e.g., events older than 50 game-days that don't meet any keep criteria).

### Retention Example

Player has mined 10,000 oak logs over 200 hours of play:

| Kept | Why | Count |
|------|-----|-------|
| 1st oak log | First occurrence | 1 |
| 2nd, 3rd, 5th, 7th, 11th, 13th... primes up to ~10000 | Prime triggers | ~1,229 |
| 100th, 1000th, 10000th | Power-of-10 milestones | 3 |
| Any that triggered interpretations | Interpretation anchors | varies |
| One per game-day | Timeline longitude | ~200 |
| **Total kept** | | **~1,400-1,500 out of 10,000** |

That's ~15% retention with full temporal coverage and heavy detail at the start.

### Pruning Implementation

```python
class EventRetentionManager:
    """Runs periodically to prune old events"""

    # Configurable thresholds
    PRUNE_AGE_THRESHOLD = 50.0        # Game-time units before events become pruneable
    TIMELINE_WINDOW = 1.0             # Game-time units per mandatory timeline marker
    PRUNE_INTERVAL = 10.0             # How often to run pruning (game-time units)

    def prune(self, event_store: 'EventStore', current_game_time: float):
        """Remove old events that don't meet retention criteria"""
        cutoff_time = current_game_time - self.PRUNE_AGE_THRESHOLD

        # Get all events older than cutoff
        old_events = event_store.query(before_time=cutoff_time)

        # Group by (actor_id, event_type, event_subtype)
        groups = {}
        for event in old_events:
            key = (event.actor_id, event.event_type, event.event_subtype)
            groups.setdefault(key, []).append(event)

        events_to_delete = []
        for key, events in groups.items():
            # Sort by game_time
            events.sort(key=lambda e: e.game_time)

            # Identify which to keep
            kept_times = set()  # For timeline marker dedup
            for event in events:
                keep = False

                # Rule 1: First occurrence (interpretation_count == 1)
                if event.interpretation_count == 1:
                    keep = True

                # Rule 2: Prime-indexed
                elif self._is_prime(event.interpretation_count):
                    keep = True

                # Rule 3: Power-of-10
                elif event.interpretation_count in {100, 1000, 10000, 100000}:
                    keep = True

                # Rule 4: Triggered interpretation
                elif event.triggered_interpretation:
                    keep = True

                # Rule 5: Referenced by Layer 3 (check via event_store)
                elif event_store.is_referenced_by_interpretation(event.event_id):
                    keep = True

                # Rule 6: Timeline marker (one per window)
                else:
                    time_bucket = int(event.game_time / self.TIMELINE_WINDOW)
                    if time_bucket not in kept_times:
                        keep = True

                if keep:
                    time_bucket = int(event.game_time / self.TIMELINE_WINDOW)
                    kept_times.add(time_bucket)
                else:
                    events_to_delete.append(event.event_id)

        # Batch delete
        if events_to_delete:
            event_store.delete_events(events_to_delete)
            print(f"✓ Pruned {len(events_to_delete)} old events")
```

## Position Sampling

The player's position is sampled periodically to create a breadcrumb trail:

```python
class PositionSampler:
    """Records player position every N seconds as a POSITION_SAMPLE event"""

    SAMPLE_INTERVAL = 10.0  # Real seconds between samples

    def __init__(self):
        self._last_sample_time = 0.0
        self._last_position = None

    def update(self, current_time: float, player_position: 'Position',
               player_health_pct: float, is_sprinting: bool,
               is_encumbered: bool):
        """Called each frame — records sample if interval elapsed"""
        if current_time - self._last_sample_time < self.SAMPLE_INTERVAL:
            return

        self._last_sample_time = current_time

        bus = GameEventBus.get_instance()
        bus.publish("POSITION_SAMPLE", {
            "position_x": player_position.x,
            "position_y": player_position.y,
            "health_pct": player_health_pct,
            "is_sprinting": is_sprinting,
            "is_encumbered": is_encumbered,
            "velocity": self._calc_velocity(player_position, current_time),
        }, source="position_sampler")

        self._last_position = player_position.copy()
```
