"""Compact temporal descriptor for event streams.

A TimeEnvelope summarizes WHEN events happened without storing every timestamp.
Evaluators use it to distinguish "steady hunting over 44 days" from
"sudden spike — all kills in the past few hours."

Design authority: WORLD_MEMORY_SYSTEM.md §8.4 (Time Envelopes)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from world_system.world_memory.event_schema import WorldMemoryEvent


@dataclass
class TimeEnvelope:
    """Compact temporal summary of an event stream."""
    first_at: float       # Game-time of first event
    last_at: float        # Game-time of last event
    total_count: int
    total_span: float     # last_at - first_at
    last_1_day: int       # Events in last 1 game-day
    last_3_days: int      # Events in last 3 game-days
    last_7_days: int      # Events in last 7 game-days
    recent_rate: float    # Events per game-time-unit (last 7 days)
    overall_rate: float   # Events per game-time-unit (all time)
    trend: str            # "accelerating", "steady", "decelerating", "burst", "dormant"


# Recency severity modifiers — evaluators multiply severity by this factor.
TREND_SEVERITY_MODIFIER: Dict[str, float] = {
    "burst": 2.0,
    "accelerating": 1.5,
    "steady": 1.0,
    "decelerating": 0.8,
    "dormant": 0.5,
}


def compute_envelope(events: List[WorldMemoryEvent],
                     current_game_time: float,
                     game_day_length: float = 1.0) -> TimeEnvelope:
    """Compute a TimeEnvelope from a list of events.

    Args:
        events: Events (any order — sorted internally by game_time).
        current_game_time: Current game time for recency calculations.
        game_day_length: How many game-time units equal one game-day.

    Returns:
        A TimeEnvelope summarizing the temporal pattern.
    """
    if not events:
        return TimeEnvelope(
            first_at=0.0, last_at=0.0, total_count=0, total_span=0.0,
            last_1_day=0, last_3_days=0, last_7_days=0,
            recent_rate=0.0, overall_rate=0.0, trend="dormant",
        )

    times = sorted(e.game_time for e in events)
    first = times[0]
    last = times[-1]
    total_count = len(times)
    total_span = last - first

    # Bucketed counts by recency
    cutoff_1 = current_game_time - game_day_length
    cutoff_3 = current_game_time - 3 * game_day_length
    cutoff_7 = current_game_time - 7 * game_day_length

    last_1 = sum(1 for t in times if t >= cutoff_1)
    last_3 = sum(1 for t in times if t >= cutoff_3)
    last_7 = sum(1 for t in times if t >= cutoff_7)

    # Rates
    recent_span = min(7 * game_day_length, current_game_time - first)
    recent_rate = last_7 / max(recent_span, 0.001)
    overall_rate = total_count / max(total_span, 0.001)

    # Trend detection (Design doc §8.4)
    trend = _detect_trend(last_1, last_7, total_count, game_day_length)

    return TimeEnvelope(
        first_at=first, last_at=last,
        total_count=total_count, total_span=total_span,
        last_1_day=last_1, last_3_days=last_3, last_7_days=last_7,
        recent_rate=recent_rate, overall_rate=overall_rate,
        trend=trend,
    )


def _detect_trend(last_1_day: int, last_7_days: int,
                  total_count: int, game_day_length: float) -> str:
    """Detect temporal trend from bucketed counts.

    Rules (Design doc §8.4):
      - last_7_days == 0 → "dormant"
      - last_1_day > daily_avg_7d * 2 → "accelerating"
      - last_1_day < daily_avg_7d * 0.3 → "decelerating"
      - last_1_day > total_count * 0.3 → "burst"
      - else → "steady"
    """
    if last_7_days == 0:
        return "dormant"

    daily_avg_7d = last_7_days / 7.0

    # Burst check FIRST: a large fraction of all-time events in a single day
    # indicates a sudden burst regardless of weekly average.
    if total_count > 0 and last_1_day > total_count * 0.3:
        return "burst"
    if daily_avg_7d > 0 and last_1_day > daily_avg_7d * 2:
        return "accelerating"
    if daily_avg_7d > 0 and last_1_day < daily_avg_7d * 0.3:
        return "decelerating"

    return "steady"
