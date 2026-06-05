"""Character stats component.

§15 trap 6 reconciliation (2026-06-05): the per-stat scaling values now
load from ``Definitions.JSON/stats-calculations.JSON`` at module import.
The previous behaviour (hardcoded defaults) is preserved as a fallback
when the JSON is missing or malformed. Designer tuning of any stat
magnitude should happen in the JSON file; this module just reads it.
"""

import json
from dataclasses import dataclass
from typing import Dict, Optional


# ── JSON-driven scaling (§15 trap 6) ─────────────────────────────────
#
# Loaded once at import. ``_FALLBACK_*`` mirrors the historical
# Python hardcoded values so the module still works if the JSON is
# missing during a unit test or constrained smoketest.

_FALLBACK_SCALING: Dict[str, float] = {
    'strength': 0.05, 'defense': 0.02, 'vitality': 0.01,
    'luck': 0.02, 'agility': 0.05, 'intelligence': 0.02,
}

_FALLBACK_FLAT: Dict[str, Dict[str, float]] = {
    'strength': {'carry_capacity': 10.0, 'inventory_slots': 10.0},
    'vitality': {'max_health': 15.0},
    'intelligence': {'mana': 20.0},
}


def _load_stat_config() -> tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Read ``stats-calculations.JSON`` → (scaling, flat_bonuses).

    Maps the JSON's ``characterStatModifiers.<stat>.<key>`` fields onto
    the legacy ``get_bonus``/``get_flat_bonus`` API surface.  Any
    failure returns the fallback constants so callers never see a
    None.
    """
    scaling = dict(_FALLBACK_SCALING)
    flat = {k: dict(v) for k, v in _FALLBACK_FLAT.items()}
    try:
        from core.paths import get_resource_path
        path = get_resource_path("Definitions.JSON/stats-calculations.JSON")
        if not path.exists():
            return scaling, flat
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mods = data.get("characterStatModifiers", {}) or {}
        # Per-stat percent scaling
        if "strength" in mods:
            scaling['strength'] = float(mods['strength'].get(
                'meleeDamagePerPoint', scaling['strength']))
        if "defense" in mods:
            scaling['defense'] = float(mods['defense'].get(
                'damageReductionPerPoint', scaling['defense']))
        if "vitality" in mods:
            scaling['vitality'] = float(mods['vitality'].get(
                'healthRegenPerPoint', scaling['vitality']))
        if "luck" in mods:
            scaling['luck'] = float(mods['luck'].get(
                'critChancePerPoint', scaling['luck']))
        if "agility" in mods:
            scaling['agility'] = float(mods['agility'].get(
                'forestryDamagePerPoint', scaling['agility']))
        if "intelligence" in mods:
            scaling['intelligence'] = float(mods['intelligence'].get(
                'reductionPerPoint', scaling['intelligence']))
        # Flat-bonus mappings
        if "strength" in mods:
            slots = mods['strength'].get('inventorySlotsPerPoint')
            if slots is not None:
                flat['strength']['carry_capacity'] = float(slots)
                flat['strength']['inventory_slots'] = float(slots)
        if "vitality" in mods:
            hp = mods['vitality'].get('maxHPPerPoint')
            if hp is not None:
                flat['vitality']['max_health'] = float(hp)
        if "intelligence" in mods:
            mana = mods['intelligence'].get('maxManaPerPoint')
            if mana is not None:
                flat['intelligence']['mana'] = float(mana)
    except Exception:
        return _FALLBACK_SCALING, _FALLBACK_FLAT
    return scaling, flat


_SCALING, _FLAT_BONUSES = _load_stat_config()


def reload_stat_config() -> None:
    """Re-read ``stats-calculations.JSON``. Designer hot-reload hook.

    Called by ``database_reloader`` when content is regenerated and by
    test fixtures that mutate the file mid-run.
    """
    global _SCALING, _FLAT_BONUSES
    _SCALING, _FLAT_BONUSES = _load_stat_config()


@dataclass
class CharacterStats:
    strength: int = 0
    defense: int = 0
    vitality: int = 0
    luck: int = 0
    agility: int = 0
    intelligence: int = 0

    def get_bonus(self, stat_name: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        return val * _SCALING.get(stat_name.lower(), 0.05)

    def get_flat_bonus(self, stat_name: str, bonus_type: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        bonuses = _FLAT_BONUSES.get(stat_name.lower(), {})
        return val * bonuses.get(bonus_type, 0.0)

    def get_durability_loss_multiplier(self) -> float:
        """Get multiplier for durability loss based on DEF stat.

        DEF reduces durability loss by 2% per point.
        Example: 10 DEF = 20% less durability loss (0.8 multiplier)

        Returns:
            float: Multiplier between 0.1 and 1.0
        """
        def_reduction = self.defense * 0.02  # 2% per DEF point
        return max(0.1, 1.0 - def_reduction)  # Minimum 10% durability loss

    def get_durability_bonus_multiplier(self) -> float:
        """Get multiplier for max durability based on VIT stat.

        VIT increases max durability by 1% per point.
        Example: 10 VIT = 10% more max durability (1.1 multiplier)

        Returns:
            float: Multiplier >= 1.0
        """
        vit_bonus = self.vitality * 0.01  # +1% per VIT point
        return 1.0 + vit_bonus

    def get_carry_capacity_multiplier(self) -> float:
        """Get multiplier for carry capacity based on STR stat.

        STR increases carry capacity by 2% per point.
        Example: 10 STR = 20% more capacity (1.2 multiplier)

        Returns:
            float: Multiplier >= 1.0
        """
        str_bonus = self.strength * 0.02  # +2% per STR point
        return 1.0 + str_bonus

    def get_effective_luck(self, title_bonus: float = 0.0, skill_bonus: float = 0.0,
                          rare_drop_bonus: float = 0.0) -> float:
        """Get effective luck including all bonuses.

        Luck affects:
        - Critical hit chance (2% per point)
        - Resource quality bonus (2% per point)
        - Rare drops (2% per point)

        Args:
            title_bonus: Flat luck bonus from titles (luckStat)
            skill_bonus: Flat luck bonus from active skills
            rare_drop_bonus: Additional rare drop bonuses (rareDropRate, etc.)
                            converted to equivalent luck

        Returns:
            float: Effective luck value (base + all bonuses)
        """
        # Rare drop bonuses are converted to equivalent luck points
        # 2% per luck point, so 0.15 rare drop bonus = 7.5 luck equivalent
        luck_from_rare_drops = rare_drop_bonus / 0.02 if rare_drop_bonus > 0 else 0

        return self.luck + title_bonus + skill_bonus + luck_from_rare_drops
