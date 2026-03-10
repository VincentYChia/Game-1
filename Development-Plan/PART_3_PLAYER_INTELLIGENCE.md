# Part 3: Player Intelligence

**Priority**: P3 — Last
**Goal**: Classify player behavior, track preferences, and feed this data into all content generators so the world adapts to how the player actually plays.

**Depends on**: Phase 2.1 (Memory Layer — reads from EventStore)

---

## Phase 3.1: Behavior Classifier

**New file**: `ai/player/behavior_classifier.py`

### Player Archetypes

```python
class PlayerArchetype(Enum):
    COMBATANT = "combatant"       # Seeks fights, levels through combat
    CRAFTER = "crafter"           # Focuses on crafting disciplines
    EXPLORER = "explorer"         # Discovers areas, gathers widely
    OPTIMIZER = "optimizer"       # Min-maxes stats, farms efficiently
    STORYTELLER = "storyteller"   # Engages NPCs, follows quests

class BehaviorClassifier:
    """Classifies player archetype from event history — updates per session"""

    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.archetype_scores: Dict[str, float] = {a.value: 0.0 for a in PlayerArchetype}
        self.primary_archetype: PlayerArchetype = PlayerArchetype.EXPLORER  # Default
        self.secondary_archetype: Optional[PlayerArchetype] = None

    def update(self, session_events: List[WorldEvent]):
        """Reclassify based on recent session activity"""
        counts = self._count_event_categories(session_events)

        # Weighted scoring
        self.archetype_scores["combatant"] = (
            counts["enemy_killed"] * 2.0 +
            counts["damage_dealt"] * 0.1 +
            counts["dungeon_entered"] * 3.0
        )
        self.archetype_scores["crafter"] = (
            counts["item_crafted"] * 2.0 +
            counts["item_invented"] * 5.0 +
            counts["recipe_discovered"] * 3.0
        )
        self.archetype_scores["explorer"] = (
            counts["area_discovered"] * 3.0 +
            counts["resource_gathered"] * 0.5 +
            counts["dungeon_entered"] * 2.0
        )
        self.archetype_scores["optimizer"] = (
            counts["item_crafted"] * 1.0 +
            counts["resource_gathered"] * 1.5 +
            counts["level_up"] * 2.0 +
            counts["title_earned"] * 3.0
        )
        self.archetype_scores["storyteller"] = (
            counts["npc_talked"] * 2.0 +
            counts["quest_completed"] * 3.0 +
            counts["quest_accepted"] * 1.0
        )

        # Normalize and determine primary/secondary
        total = sum(self.archetype_scores.values()) or 1.0
        for k in self.archetype_scores:
            self.archetype_scores[k] /= total

        sorted_archetypes = sorted(self.archetype_scores.items(), key=lambda x: -x[1])
        self.primary_archetype = PlayerArchetype(sorted_archetypes[0][0])
        if sorted_archetypes[1][1] > 0.2:  # Secondary only if significant
            self.secondary_archetype = PlayerArchetype(sorted_archetypes[1][0])

    def get_generation_weights(self) -> Dict[str, float]:
        """Weights for content generators — what to generate more of"""
        return {
            "combat_encounters": self.archetype_scores["combatant"],
            "crafting_opportunities": self.archetype_scores["crafter"],
            "exploration_rewards": self.archetype_scores["explorer"],
            "optimization_challenges": self.archetype_scores["optimizer"],
            "narrative_content": self.archetype_scores["storyteller"],
        }
```

This is purely **rule-based** — no ML model needed. The weights are heuristic. If you want to train a proper classifier later, the EventStore provides all the labeled data you need.

---

## Phase 3.2: Preference Model

**New file**: `ai/player/preference_model.py`

### Engagement Tracking

```python
@dataclass
class EngagementSignal:
    """Tracks player engagement with specific content"""
    content_type: str        # "quest", "enemy", "crafting_discipline", "biome", "npc"
    content_id: str          # Specific identifier
    time_spent_ms: float     # How long player engaged
    completed: bool          # Did they finish?
    revisited: bool          # Did they come back?
    abandoned: bool          # Did they leave early?
    rating: float            # Computed engagement score (0-1)

class PreferenceModel:
    """Learns what content the player engages with vs ignores"""

    def __init__(self, event_store: EventStore):
        self.preferences: Dict[str, Dict[str, float]] = {}
        # e.g., {"biome": {"forest": 0.8, "desert": 0.3}, "enemy": {"wolf": 0.6, "golem": 0.9}}

    def record_engagement(self, signal: EngagementSignal):
        """Update preference scores from engagement signal"""
        category = self.preferences.setdefault(signal.content_type, {})
        current = category.get(signal.content_id, 0.5)
        # Exponential moving average
        category[signal.content_id] = current * 0.7 + signal.rating * 0.3

    def get_preference(self, content_type: str, content_id: str) -> float:
        """How much does the player prefer this content? (0-1)"""
        return self.preferences.get(content_type, {}).get(content_id, 0.5)

    def get_top_preferences(self, content_type: str, n: int = 5) -> List[Tuple[str, float]]:
        """What does the player like most in this category?"""

    def get_generation_bias(self) -> Dict[str, Any]:
        """Bias signals for content generators"""
        return {
            "preferred_biomes": self.get_top_preferences("biome", 3),
            "preferred_enemies": self.get_top_preferences("enemy", 5),
            "preferred_disciplines": self.get_top_preferences("crafting_discipline", 3),
            "preferred_quest_types": self.get_top_preferences("quest_template", 3),
        }
```

---

## Phase 3.3: Player Arc Tracker

**New file**: `ai/player/arc_tracker.py`

### Narrative Stage Tracking

```python
class ArcStage(Enum):
    NEWCOMER = "newcomer"           # Just started, learning basics
    ESTABLISHING = "establishing"   # Has a base, crafting, first kills
    RISING = "rising"               # Tackling T2 content, expanding
    TESTED = "tested"               # First major challenge/death
    PROFICIENT = "proficient"       # T3 content, specializing
    MASTERING = "mastering"         # T4 content, endgame
    LEGENDARY = "legendary"         # Max level, seeking challenges

class ArcTracker:
    """Tracks player's narrative stage — derived from structured milestones, not generated"""

    STAGE_MILESTONES = {
        ArcStage.NEWCOMER: {"max_level": 5, "max_kills": 10, "max_crafts": 5},
        ArcStage.ESTABLISHING: {"max_level": 10, "max_kills": 50, "max_crafts": 20},
        ArcStage.RISING: {"max_level": 15, "max_kills": 150, "max_crafts": 50},
        ArcStage.TESTED: {"deaths_required": 3, "max_level": 20},
        ArcStage.PROFICIENT: {"max_level": 23, "t3_kills": 20, "titles": 10},
        ArcStage.MASTERING: {"max_level": 27, "t4_kills": 5, "legendary_crafts": 1},
        ArcStage.LEGENDARY: {"max_level": 30},
    }

    def evaluate(self, character, event_store: EventStore) -> ArcStage:
        """Determine current narrative stage from milestones"""

    def get_narrative_context(self) -> str:
        """One-line summary for LLM prompts"""
        # e.g., "Player is RISING — level 14, specializing in smithing,
        #        recently discovered the crystal caves, no T3 kills yet"

    def get_unresolved_tensions(self) -> List[str]:
        """What narrative threads are open?"""
        # e.g., ["Has not avenged death to dire wolves", "Iron shortage unresolved",
        #        "Blacksmith NPC asked for mithril — not delivered"]
```

---

## How Player Intelligence Feeds Other Systems

```
BehaviorClassifier ──→ Quest Generator: bias quest types toward player archetype
                   ──→ World Events: trigger exploration events for explorers, combat events for combatants
                   ──→ NPC Dialogue: NPCs recognize and comment on player's playstyle

PreferenceModel ───→ Ecosystem: spawn more of preferred resources in new chunks
                ───→ Enemy AI: vary enemy types toward preferred challenge level
                ───→ Crafting: suggest recipes using preferred materials

ArcTracker ────────→ Pacing Model: scale tension to narrative stage
                ───→ NPC Dialogue: NPCs reference player's journey stage
                ───→ World Events: unlock stage-appropriate events
                ───→ Title Generation: titles reflect actual player story
```

---

## Integration Order

```
Week 1:  Phase 3.1 (Behavior Classifier)
         - Rule-based scoring from EventStore
         - Generation weight output
         - Wire into quest generator and world events

Week 2:  Phase 3.2 (Preference Model)
         - Engagement signal recording
         - Exponential moving average preferences
         - Generation bias output

Week 3:  Phase 3.3 (Arc Tracker)
         - Milestone-based stage detection
         - Narrative context generation
         - Unresolved tension tracking
         - Wire into pacing model and NPC agents
```
