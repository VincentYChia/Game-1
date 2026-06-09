"""Pygame quest log overlay (2026-06-09).

Closes Cross-cutting Risk #9 — until now the player had no in-game UI to
see active quests, their progress, or to abandon them. This module owns
the drawing + click region computation so ``game_engine`` stays mostly
untouched (mirror of the F12 observability overlay pattern).

Toggle from ``game_engine`` with ``self.quest_log_open = not self.quest_log_open``
on the K_J keybind. Render the panel from the main render pass; the
returned ``Dict[quest_id → abandon_rect]`` is what the input handler
checks for Abandon-button clicks.

The QuestManager already exposes ``active_quests`` (the live dict) and
``abandon_quest(quest_id, character)`` — this module is pure UI on top.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


_BG_COLOR: Tuple[int, int, int] = (10, 12, 22)
_BG_ALPHA: int = 220
_BORDER_COLOR: Tuple[int, int, int] = (90, 80, 140)
_TITLE_COLOR: Tuple[int, int, int] = (250, 220, 120)
_QUEST_TITLE_COLOR: Tuple[int, int, int] = (220, 220, 240)
_OBJECTIVE_COLOR: Tuple[int, int, int] = (180, 200, 200)
_PROGRESS_COLOR: Tuple[int, int, int] = (140, 220, 140)
_DIM_COLOR: Tuple[int, int, int] = (140, 140, 150)
_ABANDON_BG: Tuple[int, int, int] = (140, 40, 40)
_ABANDON_BG_HOVER: Tuple[int, int, int] = (200, 60, 60)
_ABANDON_TEXT: Tuple[int, int, int] = (240, 240, 240)


def render_quest_log_overlay(
    surface,
    font,
    small_font,
    character,
    mouse_pos: Tuple[int, int],
    *,
    x: int = 60,
    y: int = 80,
    width: int = 560,
    max_height: int = 600,
) -> Dict[str, Any]:
    """Draw the quest log + return click region dict.

    Returned dict shape:
        {
            "window_rect": pygame.Rect,
            "abandon_buttons": {quest_id: pygame.Rect, ...},
        }

    Args:
        surface: Target pygame surface (usually the screen).
        font: Primary pygame font (titles, quest names).
        small_font: Smaller font for objective text + button label.
        character: Player Character (provides ``character.quests`` and
                   ``character.inventory`` for gather-progress display).
        mouse_pos: ``(x, y)`` cursor position — used for Abandon hover.
        x, y: Top-left corner of the panel.
        width: Panel width in pixels.
        max_height: Hard cap on rendered height.

    Returns empty dicts (with a 0-sized rect) when there is nothing to
    render so the caller can treat "no quest log" and "no quests" the
    same way.
    """
    try:
        import pygame  # type: ignore
    except Exception:
        return {"window_rect": None, "abandon_buttons": {}}

    quests_manager = getattr(character, "quests", None)
    if quests_manager is None:
        return {"window_rect": None, "abandon_buttons": {}}

    active = list(getattr(quests_manager, "active_quests", {}).values())
    completed_count = len(getattr(quests_manager, "completed_quests", []) or [])

    line_h = font.get_linesize()
    small_h = small_font.get_linesize()
    title_height = line_h + 6                # title bar
    footer_height = small_h + 6              # completed count
    padding = 12

    # Estimate per-quest block height: 1 title line + 2 small lines + abandon row.
    per_quest_height = line_h + small_h + small_h + small_h + 8
    estimated_height = (
        title_height + padding + footer_height
        + max(1, len(active)) * per_quest_height
    )
    height = min(max_height, estimated_height + padding)

    # Translucent background + border.
    bg = pygame.Surface((width, height), pygame.SRCALPHA)
    bg.fill((*_BG_COLOR, _BG_ALPHA))
    surface.blit(bg, (x, y))
    window_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, _BORDER_COLOR, window_rect, 2)

    # Title.
    yy = y + 6
    title_surf = font.render("QUEST LOG", True, _TITLE_COLOR)
    surface.blit(title_surf, (x + padding, yy))
    yy += line_h

    # Subtitle: counts.
    subtitle = f"Active: {len(active)}    Completed: {completed_count}    [J to close]"
    subtitle_surf = small_font.render(subtitle, True, _DIM_COLOR)
    surface.blit(subtitle_surf, (x + padding, yy))
    yy += small_h + 6

    abandon_buttons: Dict[str, Any] = {}

    if not active:
        empty_surf = font.render(
            "No active quests. Talk to an NPC to start one.",
            True,
            _DIM_COLOR,
        )
        surface.blit(empty_surf, (x + padding, yy + 6))
        return {"window_rect": window_rect, "abandon_buttons": abandon_buttons}

    for quest in active:
        if yy + per_quest_height > y + height - footer_height:
            # Out of space — show truncation hint and stop.
            trunc_surf = small_font.render(
                f"... and {len(active) - len(abandon_buttons)} more (panel full)",
                True,
                _DIM_COLOR,
            )
            surface.blit(trunc_surf, (x + padding, yy))
            break

        quest_id = getattr(quest.quest_def, "quest_id", "?")
        quest_title = getattr(quest.quest_def, "title", quest_id) or quest_id
        objective_text = _format_objective(quest, character)
        progress_text = _format_progress(quest, character)

        # Quest title.
        qsurf = font.render(quest_title[:60], True, _QUEST_TITLE_COLOR)
        surface.blit(qsurf, (x + padding, yy))
        yy += line_h

        # Objective.
        if objective_text:
            osurf = small_font.render(
                _truncate(objective_text, 80), True, _OBJECTIVE_COLOR
            )
            surface.blit(osurf, (x + padding + 8, yy))
            yy += small_h

        # Progress.
        if progress_text:
            psurf = small_font.render(
                _truncate(progress_text, 80), True, _PROGRESS_COLOR
            )
            surface.blit(psurf, (x + padding + 8, yy))
            yy += small_h

        # Abandon button (right-aligned).
        btn_w = small_font.size(" Abandon ")[0] + 10
        btn_h = small_h + 4
        btn_x = x + width - padding - btn_w
        btn_y = yy
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        hover = btn_rect.collidepoint(mouse_pos)
        bg_col = _ABANDON_BG_HOVER if hover else _ABANDON_BG
        pygame.draw.rect(surface, bg_col, btn_rect, border_radius=3)
        pygame.draw.rect(surface, _BORDER_COLOR, btn_rect, 1, border_radius=3)
        label = small_font.render("Abandon", True, _ABANDON_TEXT)
        surface.blit(
            label,
            (btn_x + (btn_w - label.get_width()) // 2,
             btn_y + (btn_h - label.get_height()) // 2),
        )
        abandon_buttons[quest_id] = btn_rect
        yy += btn_h + 8

    return {"window_rect": window_rect, "abandon_buttons": abandon_buttons}


def _truncate(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


def _format_objective(quest, character) -> str:
    """Render the objective in one human-readable line."""
    obj = getattr(quest.quest_def, "objectives", None)
    if obj is None:
        return ""
    obj_type = getattr(obj, "objective_type", "")
    if obj_type == "gather":
        items = getattr(obj, "items", []) or []
        if not items:
            return "Gather requested items."
        labels = []
        for spec in items:
            if isinstance(spec, dict):
                qty = spec.get("quantity", 1)
                item_id = spec.get("item_id", "?")
                labels.append(f"{qty}x {item_id}")
        return "Gather " + ", ".join(labels)
    if obj_type == "combat":
        n = getattr(obj, "enemies_killed", 0) or 0
        return f"Defeat {n} enemies."
    return obj_type or ""


def _format_progress(quest, character) -> str:
    """Render current progress vs requirement."""
    obj = getattr(quest.quest_def, "objectives", None)
    if obj is None:
        return ""
    obj_type = getattr(obj, "objective_type", "")
    if obj_type == "gather":
        items = getattr(obj, "items", []) or []
        parts = []
        inv = getattr(character, "inventory", None)
        for spec in items:
            if not isinstance(spec, dict):
                continue
            item_id = spec.get("item_id", "?")
            required = spec.get("quantity", 1)
            current = 0
            if inv and hasattr(inv, "get_item_count"):
                current = inv.get_item_count(item_id)
            baseline = quest.baseline_inventory.get(item_id, 0) if hasattr(quest, "baseline_inventory") else 0
            gathered = max(0, current - baseline)
            parts.append(f"{item_id}: {gathered}/{required}")
        return "Progress: " + ", ".join(parts) if parts else ""
    if obj_type == "combat":
        required = getattr(obj, "enemies_killed", 0) or 0
        baseline = getattr(quest, "baseline_combat_kills", 0)
        try:
            current = character.activities.get_count("combat")
        except Exception:
            current = baseline
        killed = max(0, current - baseline)
        return f"Progress: {killed}/{required} kills"
    return ""


__all__ = ["render_quest_log_overlay"]
