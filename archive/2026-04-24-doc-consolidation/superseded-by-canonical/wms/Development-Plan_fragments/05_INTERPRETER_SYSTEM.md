# Part 5: Interpreter System (Layer 3)

## Purpose

The Interpreter transforms raw facts (Layer 2) into narrative meaning (Layer 3). It detects patterns, crosses thresholds, and generates **text descriptions** — not JSON effects. This is the "journalist" of the world: it reads the ledger and writes the news.

## Trigger Mechanism: Prime Numbers

### Why Primes

The Interpreter doesn't run on every event (too expensive) or at fixed intervals (misses rare events). Instead, it fires when the **occurrence count** of an event type crosses a prime number.

Prime sequence: **1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, ...**

Properties:
- **Heavy coverage at the start**: 1st, 2nd, 3rd events all trigger. The beginning of any pattern gets maximum attention.
- **Natural thinning**: Gaps grow but never become exponential. Between 90 and 100: three triggers (97, 101, 103). Between 990 and 1010: three triggers (997, 1009).
- **Never stops**: Even at 10,000 occurrences, triggers still happen every 10-20 events.

### What Counts as an "Occurrence"

The count is tracked per `(actor_id, event_type, event_subtype)`:
- Player kills their 1st wolf → trigger (count=1, prime)
- Player kills their 2nd wolf → trigger (count=2, prime)
- Player kills their 3rd wolf → trigger (count=3, prime)
- Player kills their 4th wolf → NO trigger (4 is not prime)
- Player kills their 5th wolf → trigger (count=5, prime)
- ...
- Player kills their 97th wolf → trigger
- Player kills their 100th wolf → NO trigger on prime (but 100 IS a power-of-10 milestone, so it's still kept in retention)
- Player kills their 101st wolf → trigger

### Coverage Analysis

| Occurrences | Prime triggers | Coverage |
|-------------|---------------|----------|
| 1-10 | 1,2,3,5,7 = **5** | 50% |
| 1-100 | **25** | 25% |
| 1-1,000 | **168** | 16.8% |
| 1-10,000 | **1,229** | 12.3% |

Heavy at the start, gradually thinning, but always present.

## Interpreted Event Schema

```python
@dataclass
class InterpretedEvent:
    """A narrative description derived from Layer 2 patterns. Layer 3."""

    # Identity
    interpretation_id: str            # UUID
    created_at: float                 # Game time when this interpretation was generated

    # The narrative description — THIS IS THE CORE OUTPUT
    narrative: str                    # Human-readable text description
                                      # "Wolf population is declining in the Whispering Woods.
                                      #  The player has killed 23 wolves in this area over the
                                      #  past 5 game-days, well above the natural recovery rate."

    # Classification
    category: str                     # "population_change", "resource_pressure", "player_milestone",
                                      # "area_danger_shift", "world_event", "economic_shift"
    severity: str                     # "minor", "moderate", "significant", "major", "critical"

    # What triggered this
    trigger_event_id: str             # The Layer 2 event that triggered interpretation
    trigger_count: int                # The prime number count that triggered it
    cause_event_ids: List[str]        # Layer 2 events that form the evidence base

    # Spatial scope
    affected_locality_ids: List[str]  # Which localities this concerns
    affected_district_ids: List[str]  # Which districts
    affected_province_ids: List[str]  # Which provinces (for significant events)
    epicenter_x: float                # Geographic center of the pattern
    epicenter_y: float

    # What this concerns (for routing to affected entities/regions)
    affects_tags: List[str]           # Tags of what's affected
                                      # ["species:wolf", "biome:forest", "resource:wolf_pelt"]
                                      # These are matched against entity/region tags

    # Duration
    is_ongoing: bool                  # Is this still happening or a one-time observation?
    expires_at: Optional[float]       # Game time when this interpretation expires (if ongoing)

    # History tracking
    supersedes_id: Optional[str]      # If this updates a previous interpretation (same pattern,
                                      # higher count), reference the old one
    update_count: int = 1             # How many times this pattern has been re-interpreted
```

## The Interpreter

```python
class WorldInterpreter:
    """
    Reads Layer 2 patterns, generates Layer 3 narrative interpretations.
    Called when EventRecorder detects a prime-number trigger.
    Singleton.
    """
    _instance = None

    def __init__(self):
        self.event_store: Optional[EventStore] = None
        self.geo_registry: Optional[GeographicRegistry] = None
        self.entity_registry: Optional[EntityRegistry] = None
        self.interpretation_store: Optional[InterpretationStore] = None

        # Pattern evaluators — pluggable rules
        self._evaluators: List[PatternEvaluator] = []

    def initialize(self, event_store, geo_registry, entity_registry, interpretation_store):
        self.event_store = event_store
        self.geo_registry = geo_registry
        self.entity_registry = entity_registry
        self.interpretation_store = interpretation_store

        # Register pattern evaluators
        self._evaluators = [
            PopulationChangeEvaluator(),
            ResourcePressureEvaluator(),
            PlayerMilestoneEvaluator(),
            AreaDangerEvaluator(),
            CraftingTrendEvaluator(),
            ExplorationPatternEvaluator(),
            SocialPatternEvaluator(),
        ]

    def on_trigger(self, trigger_event: WorldMemoryEvent):
        """
        Called when a prime-number trigger fires.
        Evaluates all relevant pattern evaluators and generates interpretations.
        """
        for evaluator in self._evaluators:
            if evaluator.is_relevant(trigger_event):
                interpretation = evaluator.evaluate(
                    trigger_event=trigger_event,
                    event_store=self.event_store,
                    geo_registry=self.geo_registry,
                    entity_registry=self.entity_registry,
                    existing_interpretations=self.interpretation_store
                )
                if interpretation is not None:
                    # Check if this supersedes an existing interpretation
                    existing = self.interpretation_store.find_supersedable(
                        category=interpretation.category,
                        affects_tags=interpretation.affects_tags,
                        locality_ids=interpretation.affected_locality_ids
                    )
                    if existing:
                        interpretation.supersedes_id = existing.interpretation_id
                        interpretation.update_count = existing.update_count + 1
                        self.interpretation_store.archive(existing.interpretation_id)

                    self.interpretation_store.record(interpretation)

                    # Propagate to Layers 4/5 (see Part 6)
                    self._propagate(interpretation)

    def _propagate(self, interpretation: InterpretedEvent):
        """Route interpretation to affected regions (narrative propagation)"""
        geo = self.geo_registry

        # Update affected localities
        for locality_id in interpretation.affected_locality_ids:
            region = geo.regions.get(locality_id)
            if region:
                region.state.recent_events.append(interpretation.interpretation_id)
                if interpretation.is_ongoing:
                    region.state.active_conditions.append(interpretation.interpretation_id)
                # Trim to window size
                max_recent = 20
                if len(region.state.recent_events) > max_recent:
                    region.state.recent_events = region.state.recent_events[-max_recent:]

        # Propagate to districts and provinces based on severity
        if interpretation.severity in ("significant", "major", "critical"):
            for district_id in interpretation.affected_district_ids:
                region = geo.regions.get(district_id)
                if region:
                    region.state.recent_events.append(interpretation.interpretation_id)
                    if interpretation.is_ongoing:
                        region.state.active_conditions.append(interpretation.interpretation_id)

        if interpretation.severity in ("major", "critical"):
            for province_id in interpretation.affected_province_ids:
                region = geo.regions.get(province_id)
                if region:
                    region.state.recent_events.append(interpretation.interpretation_id)
                    if interpretation.is_ongoing:
                        region.state.active_conditions.append(interpretation.interpretation_id)
```

## Pattern Evaluators

Each evaluator looks for a specific kind of pattern. They're the "reporters" — each covers a different beat.

### Example: Population Change Evaluator

```python
class PopulationChangeEvaluator(PatternEvaluator):
    """Detects when enemy kills in a region exceed natural recovery."""

    RELEVANT_TYPES = {"enemy_killed"}

    def is_relevant(self, event: WorldMemoryEvent) -> bool:
        return event.event_type in self.RELEVANT_TYPES

    def evaluate(self, trigger_event, event_store, geo_registry,
                 entity_registry, existing_interpretations) -> Optional[InterpretedEvent]:
        """
        Check: has the kill rate for this enemy type in this locality
        exceeded a threshold that suggests population impact?
        """
        locality_id = trigger_event.locality_id
        if not locality_id:
            return None

        # Get enemy subtype from the event
        enemy_subtype = trigger_event.event_subtype  # e.g., "killed_wolf"

        # Count kills of this type in this locality over recent time window
        recent_kills = event_store.count_filtered(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - 50.0  # Last 50 game-time units
        )

        # Thresholds (could be configurable per enemy type)
        if recent_kills < 5:
            return None  # Too few to matter

        # Determine severity based on count
        if recent_kills >= 50:
            severity = "major"
            narrative = (f"The {enemy_subtype.replace('killed_', '')} population has been "
                        f"devastated in {geo_registry.regions[locality_id].name}. "
                        f"{recent_kills} have been killed in a short period. "
                        f"The species may take significant time to recover in this area.")
        elif recent_kills >= 20:
            severity = "significant"
            narrative = (f"{enemy_subtype.replace('killed_', '').title()} numbers are noticeably "
                        f"declining in {geo_registry.regions[locality_id].name}. "
                        f"{recent_kills} have been killed recently.")
        elif recent_kills >= 10:
            severity = "moderate"
            narrative = (f"Increased hunting activity has thinned the "
                        f"{enemy_subtype.replace('killed_', '')} population in "
                        f"{geo_registry.regions[locality_id].name}.")
        else:
            severity = "minor"
            narrative = (f"Several {enemy_subtype.replace('killed_', '')}s have been killed "
                        f"in {geo_registry.regions[locality_id].name}.")

        # Get cause events (the actual kill records)
        cause_events = event_store.query(
            event_type="enemy_killed",
            event_subtype=enemy_subtype,
            locality_id=locality_id,
            since_game_time=trigger_event.game_time - 50.0,
            limit=10  # Just the most recent as evidence
        )

        region = geo_registry.regions[locality_id]
        return InterpretedEvent(
            interpretation_id=str(uuid.uuid4()),
            created_at=trigger_event.game_time,
            narrative=narrative,
            category="population_change",
            severity=severity,
            trigger_event_id=trigger_event.event_id,
            trigger_count=trigger_event.interpretation_count,
            cause_event_ids=[e.event_id for e in cause_events],
            affected_locality_ids=[locality_id],
            affected_district_ids=[region.parent_id] if region.parent_id else [],
            affected_province_ids=[],  # Only if severity warrants
            epicenter_x=trigger_event.position_x,
            epicenter_y=trigger_event.position_y,
            affects_tags=[f"species:{enemy_subtype.replace('killed_', '')}",
                         f"biome:{trigger_event.biome}",
                         f"resource:{enemy_subtype.replace('killed_', '')}_pelt"],
            is_ongoing=True,
            expires_at=trigger_event.game_time + 100.0  # Ongoing for 100 game-time units
        )
```

### Other Evaluators (Signature Only)

```python
class ResourcePressureEvaluator(PatternEvaluator):
    """Detects when gathering outpaces node respawn in an area."""
    # Tracks: resource_gathered events per resource type per locality
    # Threshold: gathering rate > estimated respawn rate × 1.5

class PlayerMilestoneEvaluator(PatternEvaluator):
    """Detects notable player achievements worth narrating."""
    # Tracks: first kills, level ups, title earns, craft milestones
    # Fires on first occurrence and at significant counts

class AreaDangerEvaluator(PatternEvaluator):
    """Detects when an area becomes more or less dangerous."""
    # Tracks: player_death + damage_taken frequency per locality
    # Compares to historical baseline

class CraftingTrendEvaluator(PatternEvaluator):
    """Detects crafting specialization and quality trends."""
    # Tracks: craft_attempted per discipline per quality level
    # Detects improving quality over time or discipline focus

class ExplorationPatternEvaluator(PatternEvaluator):
    """Detects exploration milestones and area abandonment."""
    # Tracks: chunk_entered events, time since last visit per area
    # Detects new area discovery or area abandonment

class SocialPatternEvaluator(PatternEvaluator):
    """Detects NPC interaction patterns."""
    # Tracks: npc_interaction frequency per NPC
    # Detects favorite NPCs, avoided NPCs, quest streaks
```

## Narrative Propagation — Information State Only

**Critical design decision**: Event propagation produces **narrative text**, not mechanical effects.

When a "forest fire" interpreted event is created:

```python
# WHAT HAPPENS (narrative propagation):
InterpretedEvent(
    narrative="A forest fire has swept through the Northern Pines, consuming "
              "much of the woodland. The fire appears to have started near the "
              "old logging camp and spread quickly through the dry underbrush. "
              "Wildlife has fled the area and timber resources are severely impacted.",
    category="world_event",
    severity="major",
    affects_tags=["terrain:forest", "resource:wood", "species:wildlife",
                  "biome:forest", "feature:pine_forest"],
    is_ongoing=True,
    expires_at=current_game_time + 200.0
)

# WHAT DOES NOT HAPPEN:
# ❌ No {"wood_availability": -0.8, "wildlife_spawn_rate": 0.3}
# ❌ No direct modification of resource node spawn rates
# ❌ No direct modification of enemy spawn tables
# ❌ No JSON effect payloads
```

The narrative text IS the information. A separate downstream system (the gameplay effects system, not part of this design) reads these interpretations and decides what mechanical changes to make. This keeps the memory system pure — it records and interprets, nothing more.

### Why Narrative-Only

1. **Decoupling**: The memory system doesn't need to know about game mechanics. It just knows what happened and what it means in words.
2. **LLM-friendly**: Downstream NPC agents and quest generators consume text, not JSON. Narrative descriptions go directly into LLM prompts as context.
3. **Flexibility**: A human-readable description can mean different things to different consumers. The quest generator reads "forest fire" and creates fire-related quests. The NPC agent reads it and generates worried dialogue. The ecosystem system reads it and adjusts spawn rates. Each consumer interprets the narrative for their own domain.
4. **Debuggability**: You can read the interpretations and immediately understand the world state. No need to decode JSON effect payloads.

### Expiration and Cleanup

Ongoing interpreted events expire:
```python
def cleanup_expired(self, current_game_time: float):
    """Remove expired ongoing conditions from region states"""
    for region in self.geo_registry.regions.values():
        active = []
        for interp_id in region.state.active_conditions:
            interp = self.interpretation_store.get(interp_id)
            if interp and (not interp.expires_at or interp.expires_at > current_game_time):
                active.append(interp_id)
        region.state.active_conditions = active
```
