"""Daily aggregation and meta-stats for the World Memory System.

At each game-day boundary, all Layer 2 events for that day are aggregated
into a DailyLedger (one row, never pruned).  MetaDailyStats track streaks,
records, and rolling averages across ledger history.

Design authority: WORLD_MEMORY_SYSTEM.md §8.1-8.2
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from world_system.world_memory.event_schema import WorldMemoryEvent
from world_system.world_memory.event_store import EventStore


@dataclass
class DailyLedger:
    """One row summarizing all activity for a single game-day."""
    game_day: int
    game_time_start: float = 0.0
    game_time_end: float = 0.0

    # Combat
    damage_dealt: float = 0.0
    damage_taken: float = 0.0
    enemies_killed: int = 0
    deaths: int = 0
    highest_single_hit: float = 0.0
    unique_enemy_types_fought: int = 0

    # Gathering
    resources_gathered: int = 0
    unique_resources_gathered: int = 0
    nodes_depleted: int = 0

    # Crafting
    items_crafted: int = 0
    unique_disciplines_used: int = 0

    # Exploration
    chunks_visited: int = 0
    new_chunks_discovered: int = 0

    # Social
    npc_interactions: int = 0
    quests_completed: int = 0

    # Meta
    primary_activity: str = "idle"

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("game_day")  # Stored as PK, not in JSON blob
        d.pop("game_time_start")
        d.pop("game_time_end")
        return json.dumps(d)

    @classmethod
    def from_json(cls, game_day: int, game_time_start: float,
                  game_time_end: float, json_str: str) -> DailyLedger:
        data = json.loads(json_str) if json_str else {}
        return cls(
            game_day=game_day,
            game_time_start=game_time_start,
            game_time_end=game_time_end,
            **{k: v for k, v in data.items()
               if k in cls.__dataclass_fields__},
        )


@dataclass
class MetaDailyStats:
    """Streak tracking, records, and rolling averages across days."""
    # Streaks (consecutive days)
    consecutive_combat_days: int = 0
    consecutive_peaceful_days: int = 0
    consecutive_crafting_days: int = 0
    consecutive_gathering_days: int = 0
    # Records
    longest_combat_streak: int = 0
    longest_peaceful_streak: int = 0
    # Day counts
    days_with_heavy_combat: int = 0
    days_with_no_combat: int = 0
    # Single-day records
    most_kills_in_a_day: int = 0
    most_damage_in_a_day: float = 0.0
    most_resources_in_a_day: int = 0
    # Rolling averages (last 7 days)
    avg_kills_per_day_7d: float = 0.0
    avg_damage_per_day_7d: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> MetaDailyStats:
        data = json.loads(json_str) if json_str else {}
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


class DailyLedgerManager:
    """Computes and stores daily ledgers.  Called at game-day boundaries."""

    def __init__(self):
        self._last_game_day: int = -1

    def compute_ledger(self, game_day: int,
                       events: List[WorldMemoryEvent]) -> DailyLedger:
        """Aggregate a day's events into a DailyLedger."""
        ledger = DailyLedger(game_day=game_day)
        if not events:
            return ledger

        ledger.game_time_start = min(e.game_time for e in events)
        ledger.game_time_end = max(e.game_time for e in events)

        enemy_types: Set[str] = set()
        resource_types: Set[str] = set()
        disciplines: Set[str] = set()
        chunks: Set[str] = set()
        activity_counts: Dict[str, int] = {}

        for event in events:
            et = event.event_type

            if et == "attack_performed":
                ledger.damage_dealt += event.magnitude
                ledger.highest_single_hit = max(
                    ledger.highest_single_hit, event.magnitude
                )
                activity_counts["combat"] = activity_counts.get("combat", 0) + 1

            elif et == "damage_taken":
                ledger.damage_taken += event.magnitude

            elif et == "enemy_killed":
                ledger.enemies_killed += 1
                enemy_types.add(event.event_subtype)
                activity_counts["combat"] = activity_counts.get("combat", 0) + 1

            elif et == "player_death":
                ledger.deaths += 1

            elif et == "resource_gathered":
                ledger.resources_gathered += max(1, int(event.magnitude))
                resource_types.add(event.event_subtype)
                activity_counts["gathering"] = activity_counts.get("gathering", 0) + 1

            elif et == "node_depleted":
                ledger.nodes_depleted += 1

            elif et == "craft_attempted":
                ledger.items_crafted += 1
                disc = event.context.get("discipline", "unknown")
                disciplines.add(disc)
                activity_counts["crafting"] = activity_counts.get("crafting", 0) + 1

            elif et == "chunk_entered":
                chunk_key = f"{event.chunk_x},{event.chunk_y}"
                chunks.add(chunk_key)
                activity_counts["exploration"] = activity_counts.get("exploration", 0) + 1

            elif et == "npc_interaction":
                ledger.npc_interactions += 1
                activity_counts["social"] = activity_counts.get("social", 0) + 1

            elif et == "quest_completed":
                ledger.quests_completed += 1

        ledger.unique_enemy_types_fought = len(enemy_types)
        ledger.unique_resources_gathered = len(resource_types)
        ledger.unique_disciplines_used = len(disciplines)
        ledger.chunks_visited = len(chunks)

        # Determine primary activity
        if activity_counts:
            ledger.primary_activity = max(activity_counts, key=activity_counts.get)
        else:
            ledger.primary_activity = "idle"

        return ledger

    def update_meta_stats(self, ledgers: List[DailyLedger]) -> MetaDailyStats:
        """Compute streaks and records from ledger history."""
        stats = MetaDailyStats()
        if not ledgers:
            return stats

        # Sort by game_day
        sorted_ledgers = sorted(ledgers, key=lambda l: l.game_day)

        combat_streak = 0
        peaceful_streak = 0
        crafting_streak = 0
        gathering_streak = 0

        for ledger in sorted_ledgers:
            # Update single-day records
            stats.most_kills_in_a_day = max(stats.most_kills_in_a_day,
                                             ledger.enemies_killed)
            stats.most_damage_in_a_day = max(stats.most_damage_in_a_day,
                                              ledger.damage_dealt)
            stats.most_resources_in_a_day = max(stats.most_resources_in_a_day,
                                                 ledger.resources_gathered)

            # Track streaks
            has_combat = ledger.enemies_killed > 0 or ledger.damage_dealt > 100
            if has_combat:
                combat_streak += 1
                peaceful_streak = 0
                stats.days_with_heavy_combat += (1 if ledger.damage_dealt > 500 else 0)
            else:
                peaceful_streak += 1
                combat_streak = 0
                stats.days_with_no_combat += 1

            if ledger.items_crafted > 0:
                crafting_streak += 1
            else:
                crafting_streak = 0

            if ledger.resources_gathered > 0:
                gathering_streak += 1
            else:
                gathering_streak = 0

            # Update longest streaks
            stats.longest_combat_streak = max(stats.longest_combat_streak,
                                               combat_streak)
            stats.longest_peaceful_streak = max(stats.longest_peaceful_streak,
                                                 peaceful_streak)

        # Current streaks (from the end of the list)
        stats.consecutive_combat_days = combat_streak
        stats.consecutive_peaceful_days = peaceful_streak
        stats.consecutive_crafting_days = crafting_streak
        stats.consecutive_gathering_days = gathering_streak

        # Rolling 7-day averages
        recent = sorted_ledgers[-7:]
        if recent:
            stats.avg_kills_per_day_7d = sum(l.enemies_killed for l in recent) / len(recent)
            stats.avg_damage_per_day_7d = sum(l.damage_dealt for l in recent) / len(recent)

        return stats

    def save_ledger(self, ledger: DailyLedger, event_store: EventStore) -> None:
        """Write ledger to SQLite daily_ledgers table."""
        event_store.store_daily_ledger(
            ledger.game_day, ledger.game_time_start,
            ledger.game_time_end, ledger.to_json(),
        )

    def load_ledgers(self, event_store: EventStore) -> List[DailyLedger]:
        """Load all ledgers from SQLite."""
        rows = event_store.load_daily_ledgers()
        return [
            DailyLedger.from_json(day, start, end, data)
            for day, start, end, data in rows
        ]

    def check_day_boundary(self, game_time: float,
                           game_day_length: float = 1.0) -> Optional[int]:
        """Check if we've crossed a day boundary.  Returns new day number or None."""
        current_day = int(game_time / game_day_length) if game_day_length > 0 else 0
        if current_day > self._last_game_day:
            previous_day = self._last_game_day
            self._last_game_day = current_day
            if previous_day >= 0:
                return previous_day  # The day that just ended
        return None
