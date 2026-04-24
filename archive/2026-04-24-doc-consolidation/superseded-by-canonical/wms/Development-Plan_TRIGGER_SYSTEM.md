# Trigger & Escalation System Design

**Companion to**: WORLD_MEMORY_SYSTEM.md Section 5
**Status**: Design Phase — replaces prime-number triggers with dual-track system

---

## 1. Trigger Thresholds (The Original Sequence)

The occurrence-count thresholds that decide when the system "pays attention":

```
1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
```

These are NOT primes. They are hand-chosen for:
- Heavy early coverage (1, 3, 5 — first few events get full attention)
- Less aggressive growth than exponential (good for filtered/cataloged counts)
- Natural breakpoints that feel meaningful (10, 100, 1000)

**These thresholds are reused at every layer transition.** The same sequence governs:
- Layer 2→3: Raw event counts trigger interpretation
- Layer 3→4: Interpretation counts trigger local aggregation refresh
- Layer 4→5: Local-level event counts trigger regional re-summarization

### 1.1 What Gets Counted (Layer 2→3)

Counting key: `(actor_id, event_type, event_subtype, locality_id)`

Examples:
- `(player, enemy_killed, killed_wolf, whispering_woods)` → count=5 → TRIGGER
- `(player, resource_gathered, mined_iron, iron_hills)` → count=25 → TRIGGER
- `(player, craft_attempted, smithing_iron_sword, anywhere)` → count=3 → TRIGGER

When the count crosses a threshold value, the interpreter is called.

### 1.2 What Gets Counted (Layer 3→4→5)

**The Problem**: Layer 3 outputs are narrative text, not numbers. You can't count "similar" narratives directly.

**The Solution**: Count by `(category, primary_affected_tag, region_id)` tuple.

Each Layer 3 interpretation has a `category` and `affects_tags`. We extract the primary tag and count:
- `(population_change, species:wolf, whispering_woods)` → 3rd interpretation about wolves here → TRIGGER Layer 4 refresh
- `(resource_pressure, resource:iron, iron_hills)` → 5th interpretation about iron here → TRIGGER Layer 4 refresh

Layer 4→5 uses the same idea: count how many times a district's summary has been updated, trigger province re-summarization at the threshold sequence.

### 1.3 A Trigger Does NOT Mean Change

**Critical**: Hitting a threshold triggers evaluation, NOT automatic escalation. The interpreter (an LLM) can look at the evidence and decide:

- **Generate**: Create/update an interpretation and pass it upward
- **Ignore**: "Not significant enough yet" — no output, wait for next threshold
- **Absorb**: Merge into an existing interpretation (update narrative, bump severity)

This means the system self-regulates. Early triggers (1, 3, 5) will often be ignored. Later triggers (100, 250) are more likely to generate meaningful interpretations.

---

## 2. Pass-Through Cascade Model

Each layer acts as a filter with pass-through option:

```
Layer 2 event hits threshold count
    │
    ▼
Layer 3 Interpreter (small LLM)
    ├── IGNORE — "5 wolf kills isn't notable" → stop
    ├── GENERATE — create interpretation → pass to Layer 4
    └── ABSORB — update existing interpretation → pass to Layer 4
                    │
                    ▼
              Layer 4 Aggregator (small LLM)
                  ├── ACCEPT — incorporate into local summary → stop
                  ├── IGNORE — "not relevant to this locality" → stop
                  └── ESCALATE — "significant enough" → pass to Layer 5
                                    │
                                    ▼
                              Layer 5 Aggregator (medium LLM)
                                  ├── ACCEPT — incorporate into regional summary
                                  └── IGNORE — "not notable at this scale"
```

### 2.1 LLM Sizing by Layer

| Layer | LLM Size | Why |
|-------|----------|-----|
| 3 (Interpreter) | Tiny (Haiku-class) | High volume, simple pattern recognition. "Is 25 wolf kills in one area notable?" |
| 4 (Local) | Tiny (Haiku-class) | Summarize a few interpretations into local knowledge |
| 5 (Regional) | Small-Medium (Sonnet-class) | Cross-locality trend detection, richer narrative |

No parallelism needed — events don't arrive faster than a small LLM can process them (except at game start — see §2.3).

### 2.2 Benefits and Risks

**Benefits of pass-through**:
- Nothing permanently lost — every trigger gets evaluated
- Natural severity escalation (local→regional only if significant)
- Each layer is an independent filter with its own judgment

**Risk: Over-escalation** — too many things bubble up.
**Mitigation**: Higher layers have higher ignore thresholds. Layer 5 only accepts severity >= "significant". Layer 4 absorbs most things into existing summaries rather than creating new entries.

**Risk: Consistent loss** — certain event types always get ignored.
**Mitigation**: The threshold sequence guarantees re-evaluation. Even if wolf kills at count=5 are ignored, count=10 triggers again with more evidence. Eventually the accumulation becomes undeniable.

### 2.3 Early Game Templates

At game start, everything is count=1 simultaneously. Instead of firing the LLM interpreter for every first event, use pre-written templates:

```python
FIRST_EVENT_TEMPLATES = {
    ("enemy_killed", "*"): "A newcomer has begun their first hunt.",
    ("resource_gathered", "*"): "Someone has started harvesting the land.",
    ("craft_attempted", "*"): "A crafter has begun their work.",
    ("level_up", "*"): "An adventurer grows stronger.",
    ("chunk_entered", "*"): None,  # Suppress — exploring is expected
    ("npc_interaction", "*"): None,  # Suppress — talking is expected
}
```

Template rules:
- Count=1 events use templates (no LLM call)
- Count=3 events use templates with locale context (cheap string formatting)
- Count=5+ events use the real LLM interpreter

This avoids the cold-start flood.

---

## 3. Event Counter Model (Alternative/Supplement)

Instead of only triggering on individual event stream thresholds, also maintain **regional accumulation counters**:

```python
# Counter key: (region_id, event_category)
# event_category is broader than event_subtype: "combat", "gathering", "crafting", "exploration"

regional_counters = {
    ("whispering_woods", "combat"): 47,
    ("iron_hills", "gathering"): 156,
    ("iron_hills", "crafting"): 23,
}
```

When a regional counter crosses a threshold (1, 3, 5, 10, 25...), it triggers a **batch interpretation**: the interpreter receives the last N events in that category for that region and produces a summary interpretation.

This catches patterns that individual event streams miss:
- Player kills 3 wolves, 2 bears, 4 bandits in Whispering Woods → individual counts are low, but regional combat counter = 9 → triggers at threshold 10
- This produces: "The Whispering Woods have seen increased conflict lately."

**Relationship to individual triggers**: Both systems run. Individual triggers catch specific patterns ("wolf population declining"). Regional triggers catch aggregate patterns ("area becoming dangerous").

---

## 4. Trigger Implementation Summary

```python
THRESHOLDS = [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
THRESHOLD_SET = set(THRESHOLDS)

class TriggerManager:
    """Manages both individual and regional trigger counting."""

    def __init__(self):
        # Per-stream: (actor_id, event_type, event_subtype, locality_id) → count
        self.stream_counts: Dict[Tuple, int] = {}
        # Per-region: (region_id, event_category) → count
        self.regional_counts: Dict[Tuple[str, str], int] = {}
        # Per-interpretation-category: (category, primary_tag, region_id) → count
        self.interpretation_counts: Dict[Tuple, int] = {}

    def on_event(self, event: WorldMemoryEvent) -> List[TriggerAction]:
        """Check if this event crosses any thresholds. Returns trigger actions."""
        actions = []

        # Individual stream check
        stream_key = (event.actor_id, event.event_type,
                      event.event_subtype, event.locality_id)
        self.stream_counts[stream_key] = self.stream_counts.get(stream_key, 0) + 1
        count = self.stream_counts[stream_key]
        if count in THRESHOLD_SET:
            actions.append(TriggerAction("interpret_stream", stream_key, count))

        # Regional accumulation check
        category = self._event_to_category(event)
        region_key = (event.locality_id, category)
        self.regional_counts[region_key] = self.regional_counts.get(region_key, 0) + 1
        rcount = self.regional_counts[region_key]
        if rcount in THRESHOLD_SET:
            actions.append(TriggerAction("interpret_region", region_key, rcount))

        return actions

    def on_interpretation(self, interp: InterpretedEvent) -> List[TriggerAction]:
        """Check if this interpretation should trigger Layer 4/5 refresh."""
        actions = []
        primary_tag = interp.affects_tags[0] if interp.affects_tags else "general"
        for region_id in interp.affected_locality_ids:
            key = (interp.category, primary_tag, region_id)
            self.interpretation_counts[key] = self.interpretation_counts.get(key, 0) + 1
            count = self.interpretation_counts[key]
            if count in THRESHOLD_SET:
                actions.append(TriggerAction("refresh_local", key, count))
        return actions

    @staticmethod
    def _event_to_category(event: WorldMemoryEvent) -> str:
        """Map specific event types to broad categories for regional counting."""
        CATEGORY_MAP = {
            "attack_performed": "combat", "damage_taken": "combat",
            "enemy_killed": "combat", "player_death": "combat",
            "dodge_performed": "combat", "status_applied": "combat",
            "resource_gathered": "gathering", "node_depleted": "gathering",
            "craft_attempted": "crafting", "item_invented": "crafting",
            "recipe_discovered": "crafting",
            "chunk_entered": "exploration", "landmark_discovered": "exploration",
            "npc_interaction": "social", "quest_accepted": "social",
            "quest_completed": "social",
            "level_up": "progression", "skill_used": "progression",
            "trade_completed": "economy", "item_equipped": "economy",
        }
        return CATEGORY_MAP.get(event.event_type, "other")
```
