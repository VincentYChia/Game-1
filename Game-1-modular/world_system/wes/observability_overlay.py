"""Pygame debug overlay for runtime observability events.

Renders a small bottom-left panel showing the last ~15 pipeline events
plus per-type counters drawn from
:class:`world_system.wes.observability_runtime.RuntimeObservability`.

The overlay is toggled by F12 in the game engine; this module owns the
drawing logic so game_engine.py stays mostly untouched. We import pygame
lazily (top-of-module would force a dep on every test importer).

Color convention:

- Cascade fires            → green
- WNS fires / WES dispatch → cyan
- Registry commits         → orange
- DB reload OK / failed    → orange / red
- Misc / unknown           → gray
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from world_system.wes.observability_runtime import (
    EVT_CASCADE_FIRED,
    EVT_DB_RELOAD_FAILED,
    EVT_DB_RELOADED,
    EVT_REGISTRY_COMMITTED,
    EVT_WES_DISPATCHED,
    EVT_WES_PLAN_COMPLETED,
    EVT_WES_PLAN_STARTED,
    EVT_WMS_EVENT_RECEIVED,
    EVT_WNS_CALL_WES,
    EVT_WNS_FIRED,
    obs_recent,
    obs_stats,
    obs_verbose_enabled,
)


_COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    EVT_WMS_EVENT_RECEIVED:    (140, 140, 140),
    EVT_CASCADE_FIRED:         (90, 220, 90),
    EVT_WNS_FIRED:             (90, 200, 240),
    EVT_WNS_CALL_WES:          (200, 200, 90),
    EVT_WES_DISPATCHED:        (90, 200, 240),
    EVT_WES_PLAN_STARTED:      (90, 200, 240),
    EVT_WES_PLAN_COMPLETED:    (90, 220, 200),
    EVT_REGISTRY_COMMITTED:    (240, 160, 60),
    EVT_DB_RELOADED:           (240, 160, 60),
    EVT_DB_RELOAD_FAILED:      (240, 90, 90),
}

_DEFAULT_COLOR: Tuple[int, int, int] = (180, 180, 180)
_HEADER_COLOR: Tuple[int, int, int] = (250, 220, 120)
_BG_COLOR: Tuple[int, int, int] = (10, 10, 16)
_BG_ALPHA: int = 210


def render_overlay(
    surface,
    font,
    *,
    x: int = 8,
    y: int = 8,
    width: int = 600,
    max_events: int = 15,
) -> None:
    """Draw the WES observability panel on ``surface``.

    Args:
        surface: Target pygame surface (usually the screen).
        font: A pygame.font.Font. Caller controls size.
        x, y: Top-left position of the panel.
        width: Panel width in pixels.
        max_events: How many recent events to show (newest first).

    Imports pygame lazily so test importers don't pay the cost.
    """
    try:
        import pygame  # type: ignore
    except Exception:
        return

    events = obs_recent(max_events)
    stats = obs_stats()
    line_h = font.get_linesize()

    # Header lines: title + summary.
    title = "WES OBSERVABILITY"
    if obs_verbose_enabled():
        title += "  [WES_VERBOSE=on]"

    # Compose summary line — 4 most-frequent event types + total.
    notable_types = [
        EVT_WNS_FIRED, EVT_WES_DISPATCHED, EVT_REGISTRY_COMMITTED,
        EVT_DB_RELOADED,
    ]
    parts = [f"total={stats.get('_total', 0)}"]
    for t in notable_types:
        if stats.get(t):
            parts.append(f"{_short_event_type(t)}={stats[t]}")
    summary = "  ".join(parts)

    # Compute panel height.
    line_count = 2 + max(1, len(events))  # title + summary + N event lines
    height = line_h * line_count + 12

    # Draw translucent background.
    bg = pygame.Surface((width, height), pygame.SRCALPHA)
    bg.fill((*_BG_COLOR, _BG_ALPHA))
    surface.blit(bg, (x, y))

    # Title + summary.
    yy = y + 4
    title_surf = font.render(title, True, _HEADER_COLOR)
    surface.blit(title_surf, (x + 6, yy))
    yy += line_h
    summary_surf = font.render(summary, True, (200, 200, 200))
    surface.blit(summary_surf, (x + 6, yy))
    yy += line_h

    # Event lines (newest first, top-down inside the panel).
    if not events:
        empty_surf = font.render(
            "(no events recorded yet)", True, (140, 140, 140)
        )
        surface.blit(empty_surf, (x + 6, yy))
        return

    # Reverse so newest is at the top.
    for evt in reversed(events):
        color = _COLOR_MAP.get(evt.event_type, _DEFAULT_COLOR)
        line = _format_event_for_overlay(evt, max_chars=int(width / 6))
        line_surf = font.render(line, True, color)
        surface.blit(line_surf, (x + 6, yy))
        yy += line_h


def _short_event_type(event_type: str) -> str:
    """Compact event_type for header summary (drop common prefixes)."""
    return (
        event_type
        .replace("WMS_", "")
        .replace("WNS_", "")
        .replace("WES_", "")
        .replace("REGISTRY_", "REG_")
        .replace("DB_", "DB_")
        .lower()
    )


def _format_event_for_overlay(evt: Any, max_chars: int = 100) -> str:
    """Render one event as a single panel line, truncated to ``max_chars``."""
    import time
    ts = time.strftime("%H:%M:%S", time.localtime(evt.timestamp))
    base = f"{ts}  [{_short_event_type(evt.event_type)}]"
    if evt.message:
        base += f"  {evt.message}"
    if evt.fields:
        # Show fields compactly. Skip large/None values.
        compact = " ".join(
            f"{k}={v}" for k, v in evt.fields.items()
            if v is not None and len(str(v)) < 40
        )
        if compact:
            base += f"  ({compact})"
    if len(base) > max_chars:
        base = base[: max_chars - 3] + "..."
    return base


__all__ = ["render_overlay"]
