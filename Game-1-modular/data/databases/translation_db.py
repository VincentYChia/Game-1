"""Translation Database - single source of truth for skill enum translations.

§15 traps 4 + 5 reconciliation (2026-06-05): this singleton now owns the
canonical translation tables for:

- ``mana_costs``           (skills-translation-table.JSON > manaCostTranslations)
- ``cooldown_seconds``     (skills-translation-table.JSON > cooldownTranslations)
- ``duration_seconds``     (skills-translation-table.JSON > durationTranslations)
- ``magnitude_values``     (Skills/skills-base-effects-1.JSON > BASE_EFFECT_TYPES.*.magnitudeValues)

``SkillDatabase`` and ``SkillManager`` now read from this database
rather than carrying their own hardcoded copies.
"""

import json
from typing import Dict
from core.paths import get_resource_path


# ── Fallback constants (used iff JSON load fails) ─────────────────────
#
# These mirror the pre-reconciliation hardcoded values from
# ``skill_db.py:23-25`` and ``skill_manager.py:42-46``. They exist so
# tests in environments without the JSON files still work.

_FALLBACK_MANA = {"low": 30, "moderate": 60, "high": 100, "extreme": 150}
_FALLBACK_COOLDOWN = {"short": 120, "moderate": 300, "long": 600, "extreme": 1200}
_FALLBACK_DURATION = {
    "instant": 0, "brief": 15, "moderate": 30, "long": 60, "extended": 120,
}
_FALLBACK_MAGNITUDE = {
    'empower': {'minor': 0.5, 'moderate': 1.0, 'major': 2.0, 'extreme': 4.0},
    'quicken': {'minor': 0.3, 'moderate': 0.5, 'major': 0.75, 'extreme': 1.0},
    'fortify': {'minor': 10, 'moderate': 20, 'major': 40, 'extreme': 80},
    'pierce': {'minor': 0.1, 'moderate': 0.15, 'major': 0.25, 'extreme': 0.4},
    'enrich': {'minor': 1, 'moderate': 3, 'major': 6, 'extreme': 12},
    'restore': {'minor': 50, 'moderate': 100, 'major': 200, 'extreme': 400},
    'regenerate': {'minor': 3, 'moderate': 5, 'major': 10, 'extreme': 20},
    'elevate': {'minor': 0.15, 'moderate': 0.25, 'major': 0.40, 'extreme': 0.60},
    'devastate': {'minor': 3, 'moderate': 5, 'major': 7, 'extreme': 10},
    'transcend': {'minor': 1, 'moderate': 2, 'major': 3, 'extreme': 4},
}


class TranslationDatabase:
    _instance = None

    def __init__(self):
        self.magnitude_values: Dict[str, Dict[str, float]] = {}
        self.duration_seconds: Dict[str, int] = {}
        self.mana_costs: Dict[str, int] = {}
        self.cooldown_seconds: Dict[str, int] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationDatabase()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — drop the singleton so the next get_instance reloads."""
        cls._instance = None

    def load_from_files(self, base_path: str = ""):
        self._load_translation_table()
        self._load_base_effects()
        self.loaded = True

    def _load_translation_table(self) -> None:
        path = get_resource_path("Definitions.JSON/skills-translation-table.JSON")
        if not path.exists():
            self._apply_translation_fallbacks()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.get("durationTranslations", {}).items():
                self.duration_seconds[key] = int(val.get("seconds", 0))
            for key, val in data.get("manaCostTranslations", {}).items():
                self.mana_costs[key] = int(val.get("cost", 0))
            for key, val in data.get("cooldownTranslations", {}).items():
                self.cooldown_seconds[key] = int(val.get("seconds", 0))
            print(f"[OK] Loaded translations from {path}")
        except Exception as e:
            print(f"[WARN] translations: {e}")
            self._apply_translation_fallbacks()

    def _load_base_effects(self) -> None:
        path = get_resource_path("Skills/skills-base-effects-1.JSON")
        if not path.exists():
            self.magnitude_values = {k: dict(v) for k, v in _FALLBACK_MAGNITUDE.items()}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = data.get("BASE_EFFECT_TYPES", {}) or {}
            for effect_name, effect_data in base.items():
                self.magnitude_values[effect_name] = effect_data.get(
                    "magnitudeValues", {}) or {}
            print(f"[OK] Loaded magnitude values from {path}")
        except Exception as e:
            print(f"[WARN] magnitude values: {e}")
            self.magnitude_values = {k: dict(v) for k, v in _FALLBACK_MAGNITUDE.items()}

    def _apply_translation_fallbacks(self) -> None:
        if not self.mana_costs:
            self.mana_costs = dict(_FALLBACK_MANA)
        if not self.cooldown_seconds:
            self.cooldown_seconds = dict(_FALLBACK_COOLDOWN)
        if not self.duration_seconds:
            self.duration_seconds = dict(_FALLBACK_DURATION)

    def _create_defaults(self):
        """Backwards-compatible name. Apply all fallbacks."""
        self._apply_translation_fallbacks()
        if not self.magnitude_values:
            self.magnitude_values = {k: dict(v) for k, v in _FALLBACK_MAGNITUDE.items()}

    # ── Public accessors (single source of truth) ────────────────────

    def mana_cost(self, key: str) -> int:
        return self.mana_costs.get(key, 0)

    def cooldown(self, key: str) -> int:
        return self.cooldown_seconds.get(key, 0)

    def duration(self, key: str) -> int:
        return self.duration_seconds.get(key, 0)

    def magnitude(self, effect_type: str, magnitude_key: str, default: float = 0.0) -> float:
        return float(self.magnitude_values.get(effect_type, {}).get(
            magnitude_key, default))
