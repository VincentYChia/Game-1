# Time-Based Tracking & Recency Design

**Companion to**: WORLD_MEMORY_SYSTEM.md, TRIGGER_SYSTEM.md
**Status**: Design Phase

---

## 1. The Game-Day as a Unit

### 1.1 Daily Ledger

At the end of each game-day (configurable duration, e.g., 1.0 game-time units), compute a **DailyLedger** — a single-row summary of that day's activity:

```python
@dataclass
class DailyLedger:
    """One row per game-day. Stored in SQLite."""
    game_day: int                    # Day number since game start
    game_time_start: float           # Start of this day
    game_time_end: float             # End of this day

    # Combat
    damage_dealt: float              # Total damage output
    damage_taken: float              # Total damage received
    enemies_killed: int              # Total kills
    deaths: int                      # Player deaths
    highest_single_hit: float        # Max damage in one attack
    unique_enemy_types_fought: int   # Variety

    # Gathering
    resources_gathered: int          # Total resources
    unique_resources_gathered: int   # Variety
    nodes_depleted: int              # Resources exhausted

    # Crafting
    items_crafted: int               # Total craft attempts
    craft_quality_avg: float         # Average quality score (0-1)
    unique_disciplines_used: int     # Variety

    # Exploration
    chunks_visited: int              # Unique chunks entered
    new_chunks_discovered: int       # First-time visits
    distance_traveled: float         # From position samples

    # Social
    npc_interactions: int            # Total NPC talks
    quests_completed: int
    quests_accepted: int
    trades_completed: int

    # Health/Resource Management
    total_healing: float             # HP restored (potions, regen, etc.)
    mana_spent: float                # Total mana used
    skills_activated: int            # Skill uses

    # Meta
    active_playtime: float           # Real seconds of active play this day
    primary_activity: str            # "combat", "gathering", "crafting", "exploring", "idle"
```

### 1.2 Computing the Ledger

At each day boundary, query Layer 2 events for that day's time range and aggregate:

```python
def compute_daily_ledger(event_store: EventStore, day_start: float,
                         day_end: float, day_number: int) -> DailyLedger:
    events = event_store.query(since_game_time=day_start, before_game_time=day_end)
    ledger = DailyLedger(game_day=day_number, game_time_start=day_start,
                         game_time_end=day_end)

    for event in events:
        if event.event_type == "attack_performed":
            ledger.damage_dealt += event.magnitude
            ledger.highest_single_hit = max(ledger.highest_single_hit, event.magnitude)
        elif event.event_type == "damage_taken":
            ledger.damage_taken += event.magnitude
        elif event.event_type == "enemy_killed":
            ledger.enemies_killed += 1
        # ... etc for each event type

    ledger.primary_activity = _classify_primary_activity(ledger)
    return ledger
```

### 1.3 Storage

```sql
CREATE TABLE IF NOT EXISTS daily_ledgers (
    game_day INTEGER PRIMARY KEY,
    game_time_start REAL,
    game_time_end REAL,
    data_json TEXT NOT NULL  -- Full DailyLedger serialized
);
```

One row per day. After 365 in-game days: 365 rows. Trivial.

---

## 2. Meta-Daily Stats (Streaks and Patterns)

Track patterns ACROSS days using the daily ledgers:

### 2.1 Streak Tracking

```python
@dataclass
class MetaDailyStats:
    """Computed from DailyLedger history. Updated daily."""

    # Current streaks (consecutive days)
    consecutive_combat_days: int      # Days with enemies_killed > 0
    consecutive_peaceful_days: int    # Days with damage_dealt == 0
    consecutive_crafting_days: int    # Days with items_crafted > 0
    consecutive_gathering_days: int   # Days with resources_gathered > 0
    consecutive_exploration_days: int # Days with new_chunks_discovered > 0

    # Record streaks (longest ever)
    longest_combat_streak: int
    longest_peaceful_streak: int
    longest_crafting_streak: int

    # Day counts (total days where condition was met)
    days_with_heavy_combat: int       # damage_dealt > heavy_threshold
    days_with_no_combat: int          # damage_dealt == 0
    days_with_crafting: int           # items_crafted > 0
    days_with_deaths: int             # deaths > 0
    deathless_days: int               # deaths == 0

    # Records (single-day bests)
    most_kills_in_a_day: int
    most_damage_in_a_day: float
    most_resources_in_a_day: int
    most_crafts_in_a_day: int
    most_distance_in_a_day: float

    # Rolling averages (last 7 days)
    avg_kills_per_day_7d: float
    avg_damage_per_day_7d: float
    avg_resources_per_day_7d: float
```

### 2.2 Computing Meta-Stats

```python
def update_meta_stats(ledgers: List[DailyLedger], meta: MetaDailyStats):
    """Called once per day with full ledger history."""
    if not ledgers:
        return

    latest = ledgers[-1]

    # Update streaks
    if latest.enemies_killed > 0:
        meta.consecutive_combat_days += 1
        meta.consecutive_peaceful_days = 0
    else:
        meta.consecutive_peaceful_days += 1
        meta.consecutive_combat_days = 0

    meta.longest_combat_streak = max(meta.longest_combat_streak,
                                     meta.consecutive_combat_days)

    # Update day counts
    if latest.damage_dealt > _get_threshold("heavy_combat", ledgers):
        meta.days_with_heavy_combat += 1
    if latest.damage_dealt == 0:
        meta.days_with_no_combat += 1

    # Update records
    meta.most_kills_in_a_day = max(meta.most_kills_in_a_day, latest.enemies_killed)
    meta.most_damage_in_a_day = max(meta.most_damage_in_a_day, latest.damage_dealt)

    # Rolling averages (last 7 days)
    recent = ledgers[-7:]
    meta.avg_kills_per_day_7d = sum(l.enemies_killed for l in recent) / len(recent)
    meta.avg_damage_per_day_7d = sum(l.damage_dealt for l in recent) / len(recent)
```

---

## 3. Thresholds for Daily Stats

### 3.1 Option A: Static Thresholds (Start Here)

Hardcoded tiers based on game balance knowledge:

```python
DAILY_THRESHOLDS = {
    "combat_intensity": {
        "quiet":    {"damage_dealt": (0, 100),    "enemies_killed": (0, 3)},
        "active":   {"damage_dealt": (100, 500),  "enemies_killed": (3, 10)},
        "intense":  {"damage_dealt": (500, 2000), "enemies_killed": (10, 30)},
        "extreme":  {"damage_dealt": (2000, None), "enemies_killed": (30, None)},
    },
    "gathering_intensity": {
        "quiet":    {"resources_gathered": (0, 20)},
        "active":   {"resources_gathered": (20, 100)},
        "intense":  {"resources_gathered": (100, 500)},
        "extreme":  {"resources_gathered": (500, None)},
    },
    "crafting_intensity": {
        "quiet":    {"items_crafted": (0, 3)},
        "active":   {"items_crafted": (3, 10)},
        "intense":  {"items_crafted": (10, 30)},
        "extreme":  {"items_crafted": (30, None)},
    },
    "exploration_intensity": {
        "quiet":    {"new_chunks_discovered": (0, 2)},
        "active":   {"new_chunks_discovered": (2, 8)},
        "intense":  {"new_chunks_discovered": (8, 20)},
        "extreme":  {"new_chunks_discovered": (20, None)},
    },
}
```

Pros: Simple, predictable, works from day 1.
Cons: May not fit all playstyles. A casual player's "intense" might be a power player's "active."

### 3.2 Option B: Dynamic Percentile Thresholds

After 7+ days of data, compute thresholds from the player's own history:

```python
def compute_dynamic_thresholds(ledgers: List[DailyLedger], stat_key: str) -> Dict:
    """Compute percentile-based thresholds from player history."""
    if len(ledgers) < 7:
        return STATIC_DEFAULTS[stat_key]  # Fall back to static

    values = sorted(getattr(l, stat_key) for l in ledgers)
    return {
        "quiet":   (0, _percentile(values, 25)),
        "active":  (_percentile(values, 25), _percentile(values, 50)),
        "intense": (_percentile(values, 50), _percentile(values, 75)),
        "extreme": (_percentile(values, 75), None),
    }
```

Pros: Self-calibrating to each player's style.
Cons: A player who only crafts will have combat thresholds of (0, 0, 0, 0) — need minimum floors.

### 3.3 Recommended: Hybrid

```
Days 1-6:   Use static thresholds
Days 7-29:  Blend 70% static + 30% dynamic (player history is short)
Days 30+:   Blend 30% static + 70% dynamic (player history is reliable)
```

Always enforce minimum floors from static thresholds — dynamic can raise bars but not lower them below game-balance minimums.

---

## 4. Time Envelopes (Solving the Timestamp Problem)

### 4.1 The Problem

To interpret "100 wolf kills," the system needs temporal context. But we don't want:
- 100 individual timestamps (too much data)
- The average timestamp (meaningless — kills over 50 days vs. 2 days look the same)

### 4.2 The Solution: Time Envelope

A compact temporal descriptor that captures the **shape** of activity:

```python
@dataclass
class TimeEnvelope:
    """Compact temporal summary for a set of events."""
    first_at: float           # Game-time of first event
    last_at: float            # Game-time of most recent event
    total_count: int          # How many events total
    total_span: float         # last_at - first_at

    # Bucketed counts (how many in each recent period)
    last_1_day: int           # Events in the last 1 game-day
    last_3_days: int          # Events in the last 3 game-days
    last_7_days: int          # Events in the last 7 game-days

    # Rate and trend
    recent_rate: float        # Events per game-time-unit (last 7 days)
    overall_rate: float       # Events per game-time-unit (all time)
    trend: str                # "accelerating", "steady", "decelerating", "burst", "dormant"
```

### 4.3 Computing the Envelope

```python
def compute_time_envelope(event_store: EventStore, event_type: str,
                          event_subtype: str, locality_id: str,
                          current_time: float) -> TimeEnvelope:
    # Get boundary events (first and last)
    first = event_store.query(event_type=event_type, event_subtype=event_subtype,
                              locality_id=locality_id, order_by="game_time ASC", limit=1)
    last = event_store.query(event_type=event_type, event_subtype=event_subtype,
                             locality_id=locality_id, order_by="game_time DESC", limit=1)
    total = event_store.count_filtered(event_type=event_type, event_subtype=event_subtype,
                                       locality_id=locality_id)

    # Bucketed counts
    last_1 = event_store.count_filtered(event_type=event_type, event_subtype=event_subtype,
                                        locality_id=locality_id,
                                        since_game_time=current_time - 1.0)
    last_3 = event_store.count_filtered(..., since_game_time=current_time - 3.0)
    last_7 = event_store.count_filtered(..., since_game_time=current_time - 7.0)

    # Trend detection
    if last_7 == 0:
        trend = "dormant"
    elif last_1 > last_7 / 7 * 2:
        trend = "accelerating"
    elif last_1 < last_7 / 7 * 0.3:
        trend = "decelerating"
    elif last_1 > total * 0.3:
        trend = "burst"
    else:
        trend = "steady"

    span = last[0].game_time - first[0].game_time if first and last else 0
    return TimeEnvelope(
        first_at=first[0].game_time if first else 0,
        last_at=last[0].game_time if last else 0,
        total_count=total, total_span=span,
        last_1_day=last_1, last_3_days=last_3, last_7_days=last_7,
        recent_rate=last_7 / 7.0 if last_7 > 0 else 0,
        overall_rate=total / max(span, 1.0),
        trend=trend,
    )
```

### 4.4 How Interpreters Use Time Envelopes

The interpreter receives the time envelope alongside the trigger event. This enables temporal awareness in the narrative:

```python
# Interpreter prompt context example:
"""
Event: 100th wolf killed in Whispering Woods
Time envelope:
  - First kill: day 3, Most recent: day 47
  - Total span: 44 days
  - Last day: 2 kills, Last 3 days: 8 kills, Last 7 days: 15 kills
  - Trend: accelerating
  - Overall rate: 2.3/day, Recent rate: 2.1/day

Generate an interpretation of this pattern's significance.
"""
```

The LLM can then produce:
- "Wolf hunting has been **steady** in the Whispering Woods, with 100 killed over 44 days. Recently, the pace has picked up — 15 kills in the last week alone, suggesting **escalating** pressure on the local wolf population."

vs. if trend were "burst":
- "A **sudden spike** in wolf kills has been observed in the Whispering Woods. Nearly all 100 kills occurred in the past few days, suggesting an intense hunting campaign."

### 4.5 Recency Weighting in Severity

The time envelope directly influences severity assessment:

```python
def recency_severity_modifier(envelope: TimeEnvelope) -> float:
    """
    Boost severity for recent/accelerating patterns.
    Returns multiplier: 0.5 (old/dormant) to 2.0 (recent burst).
    """
    if envelope.trend == "dormant":
        return 0.5   # Old pattern, less urgent
    elif envelope.trend == "burst":
        return 2.0   # Happening RIGHT NOW
    elif envelope.trend == "accelerating":
        return 1.5   # Getting worse
    elif envelope.trend == "decelerating":
        return 0.8   # Fading
    else:  # steady
        return 1.0
```

---

## 5. Relationship to Existing Systems

### stat_tracker.py (Layer 1)
- DailyLedger is computed FROM Layer 2, not from stat_tracker
- stat_tracker continues to track lifetime totals independently
- MetaDailyStats supplements stat_tracker with temporal patterns it doesn't have
- No changes to stat_tracker.py needed

### Retention Policy
- DailyLedgers are NEVER pruned — one row per day is tiny
- Time envelopes are computed on-demand from surviving events (works even after pruning because retention keeps milestone events and timeline markers)

### Save System
- DailyLedger table and MetaDailyStats row serialize with the SQLite database
- No changes to existing save_manager.py beyond the existing memory DB path hook
