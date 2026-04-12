"""Game date utility — converts game_time floats to readable dates.

Game time is a continuous float incremented each frame. One full
day/night cycle = 1440.0 seconds (CYCLE_LENGTH in game_engine.py).
A "month" is 30 game days (no in-game calendar exists — this is an
artificial boundary for the World Memory System).

Usage:
    from world_system.world_memory.game_date import game_day, format_relative

    day = game_day(game_time)              # → 14
    label = format_relative(event_time, now)  # → "2 months and 5 days ago"
    stamp = date_stamp(game_time)          # → {"game_day": 14, "game_month": 0}
"""

from __future__ import annotations

# One full day/night cycle in game_time units (seconds).
# Source of truth: core/game_engine.py CYCLE_LENGTH = 1440.0
CYCLE_LENGTH = 1440.0

# Artificial month boundary (30 game days).
DAYS_PER_MONTH = 30


def game_day(game_time: float) -> int:
    """Convert game_time to an integer game day number (0-indexed)."""
    return int(game_time / CYCLE_LENGTH) if game_time >= 0 else 0


def game_month(game_time: float) -> int:
    """Convert game_time to a game month number (0-indexed)."""
    return game_day(game_time) // DAYS_PER_MONTH


def date_stamp(game_time: float) -> dict:
    """Get full date stamp for a game_time value.

    Returns:
        {"game_day": int, "game_month": int, "day_in_month": int}
    """
    day = game_day(game_time)
    month = day // DAYS_PER_MONTH
    day_in_month = day % DAYS_PER_MONTH
    return {
        "game_day": day,
        "game_month": month,
        "day_in_month": day_in_month,
    }


def format_relative(event_time: float, current_time: float) -> str:
    """Format a game_time as a relative date for LLM consumption.

    Examples:
        "today"
        "1 day ago"
        "5 days ago"
        "1 month and 3 days ago"
        "2 months and 15 days ago"

    Args:
        event_time: The game_time of the event.
        current_time: The current game_time.

    Returns:
        Human-readable relative date string.
    """
    event_day = game_day(event_time)
    current_day_num = game_day(current_time)
    days_ago = current_day_num - event_day

    if days_ago <= 0:
        return "today"
    if days_ago == 1:
        return "1 day ago"

    months_ago = days_ago // DAYS_PER_MONTH
    remaining_days = days_ago % DAYS_PER_MONTH

    if months_ago == 0:
        return f"{days_ago} days ago"

    parts = []
    if months_ago == 1:
        parts.append("1 month")
    else:
        parts.append(f"{months_ago} months")

    if remaining_days == 1:
        parts.append("1 day")
    elif remaining_days > 0:
        parts.append(f"{remaining_days} days")

    return " and ".join(parts) + " ago"


def format_date_label(game_time: float) -> str:
    """Format a game_time as an absolute date label.

    Returns "Day X" or "Month Y, Day Z" style labels.
    """
    stamp = date_stamp(game_time)
    if stamp["game_month"] == 0:
        return f"Day {stamp['game_day'] + 1}"
    return f"Month {stamp['game_month'] + 1}, Day {stamp['day_in_month'] + 1}"
