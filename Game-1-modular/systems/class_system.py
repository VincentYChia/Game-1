"""Class system for managing character class selection and bonuses"""

import json
from typing import Optional, Dict, Callable, List

from data.models import ClassDefinition


# ── §15 trap 7 — JSON-driven tag→tool bonus table ────────────────────
#
# Loaded lazily on first use. Falls back to the historical Python
# constants if classes-1.JSON is missing or doesn't carry a
# ``metadata.tagToolBonuses`` block.

_FALLBACK_TAG_TOOL_BONUSES: Dict[str, Dict[str, float]] = {
    'axe': {'nature': 0.10, 'gathering': 0.05},
    'pickaxe': {'gathering': 0.10, 'explorer': 0.05},
    'toolDamage': {'physical': 0.05, 'melee': 0.05},
}

_TAG_TOOL_BONUSES_CACHE: Optional[Dict[str, Dict[str, float]]] = None


def _load_tag_tool_bonuses() -> Dict[str, Dict[str, float]]:
    global _TAG_TOOL_BONUSES_CACHE
    if _TAG_TOOL_BONUSES_CACHE is not None:
        return _TAG_TOOL_BONUSES_CACHE
    try:
        from core.paths import get_resource_path
        path = get_resource_path("progression/classes-1.JSON")
        if not path.exists():
            _TAG_TOOL_BONUSES_CACHE = _FALLBACK_TAG_TOOL_BONUSES
            return _TAG_TOOL_BONUSES_CACHE
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        metadata = data.get("metadata", {}) or {}
        table = metadata.get("tagToolBonuses") or {}
        # Drop the editor-only _note key if present
        cleaned = {k: {tk: float(tv) for tk, tv in v.items() if not tk.startswith("_")}
                   for k, v in table.items() if not k.startswith("_")}
        _TAG_TOOL_BONUSES_CACHE = cleaned if cleaned else _FALLBACK_TAG_TOOL_BONUSES
    except Exception:
        _TAG_TOOL_BONUSES_CACHE = _FALLBACK_TAG_TOOL_BONUSES
    return _TAG_TOOL_BONUSES_CACHE


def reload_tag_tool_bonuses() -> None:
    """Clear the cache so the next call re-reads the JSON."""
    global _TAG_TOOL_BONUSES_CACHE
    _TAG_TOOL_BONUSES_CACHE = None


class ClassSystem:
    def __init__(self):
        self.current_class: Optional[ClassDefinition] = None
        self._on_class_set_callbacks: List[Callable[[ClassDefinition], None]] = []

    def set_class(self, class_def: ClassDefinition):
        self.current_class = class_def
        # Publish CLASS_CHANGED to GameEventBus for World Memory System
        try:
            from events.event_bus import get_event_bus
            get_event_bus().publish("CLASS_CHANGED", {
                "actor_id": "player",
                "class_id": class_def.class_id,
            })
        except Exception:
            pass
        # Notify any registered callbacks
        for callback in self._on_class_set_callbacks:
            callback(class_def)

    def register_on_class_set(self, callback: Callable[[ClassDefinition], None]):
        """Register a callback to be called when a class is set."""
        self._on_class_set_callbacks.append(callback)

    def get_bonus(self, bonus_type: str) -> float:
        if not self.current_class:
            return 0.0
        return self.current_class.bonuses.get(bonus_type, 0.0)

    def get_tool_efficiency_bonus(self, tool_type: str) -> float:
        """Get tool efficiency bonus based on class tags.

        §15 trap 7: bonuses come from
        ``progression/classes-1.JSON > metadata.tagToolBonuses``.
        """
        if not self.current_class or not self.current_class.tags:
            return 0.0
        tags = set(t.lower() for t in self.current_class.tags)
        per_tool = _load_tag_tool_bonuses().get(tool_type, {})
        return sum(v for k, v in per_tool.items() if k in tags)

    def get_tool_damage_bonus(self) -> float:
        """Get tool damage bonus for combat use based on class tags."""
        if not self.current_class or not self.current_class.tags:
            return 0.0
        tags = set(t.lower() for t in self.current_class.tags)
        per_tool = _load_tag_tool_bonuses().get("toolDamage", {})
        return sum(v for k, v in per_tool.items() if k in tags)
