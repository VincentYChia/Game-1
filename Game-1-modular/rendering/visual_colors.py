"""Central visual-color lookup (§15 traps 13-15 + 20 reconciliation).

Single source of truth for:

- Element colors (damage tags fire/ice/lightning/etc.) — was duplicated
  in 5 places: ``renderer._ETAG_COLORS``, ``renderer._ELEMENT_COLORS``,
  ``weapon_visuals.ELEMENT_COLORS``, ``visual-config.JSON > damageNumbers.typeColors``,
  ``combat_particles.DAMAGE_SPARK_COLORS``.
- Per-tier enemy colors (1-4) — was duplicated in 3 places:
  ``visual_effect_bridge._TIER_COLORS``, ``renderer.tier_colors`` (multiple),
  inline overrides.
- Enemy state indicator colors (idle/wander/chase/attack/flee/dead) —
  was duplicated in ``renderer._STATE_COLORS`` and
  ``visual-config.JSON > enemyVisuals.stateIndicatorColors``.
- Boss glow color — formerly hardcoded gold in renderer; this now reads
  ``enemyVisuals.bossGlowColor`` (§15 trap 20).

All lookups have Python fallbacks so the module never raises if the
JSON is missing during a constrained test boot.
"""

from __future__ import annotations

import json
from typing import Dict, Tuple


_RGB = Tuple[int, int, int]


# Authoritative fallbacks — match the historical Python literals so
# behaviour is byte-identical when the JSON is unreadable.

_FALLBACK_ELEMENT_COLORS: Dict[str, _RGB] = {
    "physical": (255, 255, 255),
    "fire": (255, 140, 40),
    "ice": (100, 200, 255),
    "lightning": (255, 255, 80),
    "poison": (100, 255, 80),
    "arcane": (200, 100, 255),
    "shadow": (160, 100, 200),
    "holy": (255, 255, 180),
    "heal": (80, 255, 80),
    "shield": (100, 180, 255),
}

_FALLBACK_TIER_COLORS: Dict[int, _RGB] = {
    1: (200, 100, 100),
    2: (255, 150, 0),
    3: (200, 100, 255),
    4: (255, 50, 50),
}

_FALLBACK_STATE_COLORS: Dict[str, _RGB] = {
    "idle": (100, 200, 100),
    "wander": (100, 200, 100),
    "patrol": (100, 200, 100),
    "guard": (180, 180, 100),
    "chase": (255, 200, 50),
    "attack": (255, 80, 60),
    "flee": (100, 150, 255),
    "dead": (100, 100, 100),
}

_FALLBACK_BOSS_GLOW: _RGB = (255, 215, 0)


# ── Cache ────────────────────────────────────────────────────────────

_CACHE: Dict[str, object] = {}


def _to_rgb(seq, fallback: _RGB) -> _RGB:
    """Coerce a JSON list/tuple to a 3-tuple of ints."""
    try:
        r, g, b = seq[0], seq[1], seq[2]
        return (int(r), int(g), int(b))
    except Exception:
        return fallback


def _load() -> None:
    """Read ``visual-config.JSON`` into the module cache. Idempotent."""
    if _CACHE:
        return
    elements = dict(_FALLBACK_ELEMENT_COLORS)
    tiers = dict(_FALLBACK_TIER_COLORS)
    states = dict(_FALLBACK_STATE_COLORS)
    boss = _FALLBACK_BOSS_GLOW
    try:
        from core.paths import get_resource_path
        path = get_resource_path("Definitions.JSON/visual-config.JSON")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            dn = data.get("damageNumbers", {}) or {}
            for k, v in (dn.get("typeColors") or {}).items():
                elements[str(k).lower()] = _to_rgb(v, elements.get(
                    str(k).lower(), _FALLBACK_ELEMENT_COLORS["physical"]))
            ev = data.get("enemyVisuals", {}) or {}
            tc_block = ev.get("tierColors") or {}
            for k, v in tc_block.items():
                if str(k).startswith("_"):
                    continue
                try:
                    tier = int(k)
                except (TypeError, ValueError):
                    continue
                tiers[tier] = _to_rgb(v, tiers.get(tier, _FALLBACK_TIER_COLORS[1]))
            for k, v in (ev.get("stateIndicatorColors") or {}).items():
                states[str(k).lower()] = _to_rgb(v, states.get(
                    str(k).lower(), _FALLBACK_STATE_COLORS["idle"]))
            boss = _to_rgb(ev.get("bossGlowColor"), boss)
    except Exception:
        pass
    _CACHE["element"] = elements
    _CACHE["tier"] = tiers
    _CACHE["state"] = states
    _CACHE["boss_glow"] = boss


def reload() -> None:
    """Drop the cache so the next lookup re-reads the JSON."""
    _CACHE.clear()


# ── Public lookups ───────────────────────────────────────────────────


def element_color(tag: str, default: _RGB = (255, 255, 255)) -> _RGB:
    """Return RGB for a damage-type tag (case-insensitive)."""
    _load()
    return _CACHE["element"].get(str(tag).lower(), default)  # type: ignore[union-attr]


def tier_color(tier: int, default: _RGB = (200, 100, 100)) -> _RGB:
    """Return RGB for an enemy tier (1-4)."""
    _load()
    return _CACHE["tier"].get(int(tier), default)  # type: ignore[union-attr]


def state_color(state: str, default: _RGB = (150, 150, 150)) -> _RGB:
    """Return RGB for an enemy AI state name (case-insensitive)."""
    _load()
    return _CACHE["state"].get(str(state).lower(), default)  # type: ignore[union-attr]


def boss_glow_color() -> _RGB:
    _load()
    return _CACHE["boss_glow"]  # type: ignore[return-value]


def element_palette() -> Dict[str, _RGB]:
    """Read-only snapshot — for places that need to iterate the whole map."""
    _load()
    return dict(_CACHE["element"])  # type: ignore[arg-type]


def tier_palette() -> Dict[int, _RGB]:
    _load()
    return dict(_CACHE["tier"])  # type: ignore[arg-type]


def state_palette() -> Dict[str, _RGB]:
    _load()
    return dict(_CACHE["state"])  # type: ignore[arg-type]
