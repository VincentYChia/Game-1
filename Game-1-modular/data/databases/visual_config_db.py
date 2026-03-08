"""VisualConfig — singleton loader for visual-config.JSON.

Provides typed access to all visual parameters (damage numbers, telegraphs,
particles, entity visuals, screen effects, debug overlays) without hardcoding
values in rendering code.

Usage:
    vc = get_visual_config()
    color = vc.damage_type_color("fire")  # (255, 140, 40)
    scale = vc.enemy_tier_scale(3)         # 1.6
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple


class VisualConfig:
    """Singleton configuration loaded from Definitions.JSON/visual-config.JSON."""

    _instance: Optional[VisualConfig] = None

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._loaded = False

    @classmethod
    def get_instance(cls) -> VisualConfig:
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def _load(self) -> None:
        """Load visual config from JSON file."""
        # Search relative to this file's location (data/databases/ -> up to Game-1-modular)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base_dir, "Definitions.JSON", "visual-config.JSON")
        try:
            with open(path, 'r') as f:
                self._data = json.load(f)
            self._loaded = True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[VisualConfig] Could not load {path}: {e}")
            self._data = {}
            self._loaded = False

    def _get(self, *keys: str, default: Any = None) -> Any:
        """Nested dict access: _get("damageNumbers", "lifetimeMs", default=1200)."""
        d = self._data
        for key in keys:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return default
        return d

    # --- Damage Numbers ---

    def damage_type_color(self, damage_type: str) -> Tuple[int, int, int]:
        colors = self._get("damageNumbers", "typeColors", default={})
        c = colors.get(damage_type, [255, 255, 255])
        return (c[0], c[1], c[2])

    @property
    def damage_number_lifetime_ms(self) -> float:
        return self._get("damageNumbers", "lifetimeMs", default=1200)

    @property
    def damage_number_velocity_y(self) -> float:
        return self._get("damageNumbers", "initialVelocityY", default=-2.5)

    @property
    def damage_number_horizontal_spread(self) -> float:
        return self._get("damageNumbers", "horizontalSpread", default=0.6)

    @property
    def damage_number_gravity(self) -> float:
        return self._get("damageNumbers", "gravity", default=0.08)

    @property
    def damage_number_shrink_rate(self) -> float:
        return self._get("damageNumbers", "shrinkRate", default=0.997)

    @property
    def damage_number_crit_scale(self) -> float:
        return self._get("damageNumbers", "critScaleMultiplier", default=1.8)

    @property
    def damage_number_crit_color(self) -> Tuple[int, int, int]:
        c = self._get("damageNumbers", "critColor", default=[255, 220, 50])
        return (c[0], c[1], c[2])

    @property
    def damage_number_stack_offset(self) -> int:
        return self._get("damageNumbers", "stackOffsetPx", default=18)

    def damage_special_text(self, special_type: str) -> Tuple[str, Tuple[int, int, int]]:
        """Get text and color for miss/block/dodge indicators."""
        text = self._get("damageNumbers", f"{special_type}Text", default=special_type.upper())
        c = self._get("damageNumbers", f"{special_type}Color", default=[180, 180, 180])
        return (text, (c[0], c[1], c[2]))

    # --- Entity Visuals ---

    @property
    def player_radius_tiles(self) -> float:
        return self._get("entityVisuals", "playerRadius", default=0.33)

    @property
    def player_color(self) -> Tuple[int, int, int]:
        c = self._get("entityVisuals", "playerColor", default=[80, 180, 255])
        return (c[0], c[1], c[2])

    @property
    def player_outline_color(self) -> Tuple[int, int, int]:
        c = self._get("entityVisuals", "playerOutlineColor", default=[40, 100, 160])
        return (c[0], c[1], c[2])

    @property
    def facing_indicator_length(self) -> float:
        return self._get("entityVisuals", "facingIndicatorLength", default=0.5)

    @property
    def facing_indicator_color(self) -> Tuple[int, int, int]:
        c = self._get("entityVisuals", "facingIndicatorColor", default=[200, 220, 255])
        return (c[0], c[1], c[2])

    @property
    def shadow_enabled(self) -> bool:
        return self._get("entityVisuals", "shadowEnabled", default=True)

    @property
    def shadow_alpha(self) -> int:
        return self._get("entityVisuals", "shadowAlpha", default=40)

    @property
    def shadow_scale(self) -> float:
        return self._get("entityVisuals", "shadowScale", default=0.7)

    @property
    def idle_bob_amplitude(self) -> float:
        return self._get("entityVisuals", "idleBobAmplitude", default=1.5)

    @property
    def idle_bob_period_ms(self) -> float:
        return self._get("entityVisuals", "idleBobPeriodMs", default=2000)

    # --- Enemy Visuals ---

    def enemy_tier_scale(self, tier: int) -> float:
        return self._get("enemyVisuals", "tierScale", str(tier), default=1.0)

    def enemy_tier_has_glow(self, tier: int) -> bool:
        return self._get("enemyVisuals", "tierGlow", str(tier), default=False)

    def enemy_tier_glow_intensity(self, tier: int) -> float:
        return self._get("enemyVisuals", "tierGlowIntensity", str(tier), default=0.0)

    @property
    def boss_glow_color(self) -> Tuple[int, int, int]:
        c = self._get("enemyVisuals", "bossGlowColor", default=[255, 215, 0])
        return (c[0], c[1], c[2])

    @property
    def death_fade_duration_ms(self) -> float:
        return self._get("enemyVisuals", "deathFadeDurationMs", default=600)

    @property
    def death_shrink_factor(self) -> float:
        return self._get("enemyVisuals", "deathShrinkFactor", default=0.3)

    @property
    def corpse_linger_ms(self) -> float:
        return self._get("enemyVisuals", "corpseLingerMs", default=5000)

    @property
    def spawn_fade_in_ms(self) -> float:
        return self._get("enemyVisuals", "spawnFadeInMs", default=400)

    def enemy_state_color(self, state: str) -> Tuple[int, int, int]:
        colors = self._get("enemyVisuals", "stateIndicatorColors", default={})
        c = colors.get(state, [150, 150, 150])
        return (c[0], c[1], c[2])

    # --- Telegraphs ---

    @property
    def telegraph_player_color(self) -> Tuple[int, int, int]:
        c = self._get("telegraphs", "playerColor", default=[100, 180, 255])
        return (c[0], c[1], c[2])

    @property
    def telegraph_enemy_color(self) -> Tuple[int, int, int]:
        c = self._get("telegraphs", "enemyColor", default=[255, 100, 100])
        return (c[0], c[1], c[2])

    @property
    def telegraph_pulse_frequency(self) -> float:
        return self._get("telegraphs", "pulseFrequency", default=10.0)

    # --- Particles ---

    @property
    def max_particles(self) -> int:
        return self._get("particles", "maxParticles", default=400)

    @property
    def hit_spark_count(self) -> Tuple[int, int]:
        c = self._get("particles", "hitSparkCount", default=[5, 8])
        return (c[0], c[1])

    @property
    def death_burst_count(self) -> int:
        return self._get("particles", "deathBurstCount", default=12)

    # --- Screen Effects ---

    @property
    def shake_decay_rate(self) -> float:
        return self._get("screenEffects", "shakeDecayRate", default=0.88)

    @property
    def shake_max_offset(self) -> int:
        return self._get("screenEffects", "shakeMaxOffset", default=12)

    # --- Debug ---

    def debug_hitbox_color(self) -> Tuple[int, int, int]:
        c = self._get("debug", "hitboxColor", default=[255, 60, 60])
        return (c[0], c[1], c[2])

    @property
    def debug_hitbox_alpha(self) -> int:
        return self._get("debug", "hitboxAlpha", default=100)

    def debug_hurtbox_color(self) -> Tuple[int, int, int]:
        c = self._get("debug", "hurtboxColor", default=[60, 255, 60])
        return (c[0], c[1], c[2])

    @property
    def debug_hurtbox_alpha(self) -> int:
        return self._get("debug", "hurtboxAlpha", default=80)

    def debug_iframe_color(self) -> Tuple[int, int, int]:
        c = self._get("debug", "iframeHurtboxColor", default=[60, 60, 255])
        return (c[0], c[1], c[2])

    @property
    def debug_show_facing(self) -> bool:
        return self._get("debug", "showFacingAngles", default=True)

    @property
    def debug_show_attack_phase(self) -> bool:
        return self._get("debug", "showAttackPhase", default=True)


def get_visual_config() -> VisualConfig:
    """Module-level accessor following project singleton pattern."""
    return VisualConfig.get_instance()
