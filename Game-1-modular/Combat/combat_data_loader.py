"""
Combat data loader.

Loads weapon-attacks.json, enemy-attacks.json, and projectile-definitions.json
from Animation-Data.JSON/. Provides lookup methods for the game engine and
combat manager.

Follows the project's JSON loading pattern (PathManager, try/except with
graceful degradation).
"""

import json
import random
from typing import Dict, List, Optional, Any

from core.paths import get_resource_path
from Combat.attack_state_machine import AttackDefinition
from Combat.projectile_system import ProjectileDefinition
from Combat.hitbox_system import HitboxDefinition


class CombatDataLoader:
    """Loads and provides access to combat animation data from JSON."""

    def __init__(self):
        self.weapon_attacks: Dict[str, List[AttackDefinition]] = {}
        self.attack_lookup: Dict[str, AttackDefinition] = {}  # attack_id -> definition
        self.enemy_data: Dict[str, dict] = {}  # enemy_id -> full data
        self.projectiles: Dict[str, ProjectileDefinition] = {}
        self._loaded = False

    def load_all(self) -> bool:
        """Load all combat data files. Returns True if at least weapon attacks loaded."""
        success = True
        success = self._load_weapon_attacks() and success
        self._load_enemy_attacks()
        self._load_projectiles()
        self._loaded = True
        print(f"✓ Combat data loaded: {len(self.weapon_attacks)} weapon types, "
              f"{len(self.enemy_data)} enemy types, {len(self.projectiles)} projectiles")
        return success

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # --- Weapon attacks ---

    def get_weapon_attack(self, weapon_type: str,
                          combo_index: int = 0) -> Optional[AttackDefinition]:
        """Get attack definition for a weapon type at combo position."""
        attacks = self.weapon_attacks.get(weapon_type)
        if not attacks:
            attacks = self.weapon_attacks.get("unarmed")
        if not attacks:
            return self._get_fallback_attack()
        index = combo_index % len(attacks)
        return attacks[index]

    def get_weapon_combo_length(self, weapon_type: str) -> int:
        """How many attacks in the combo chain for this weapon type."""
        attacks = self.weapon_attacks.get(weapon_type, [])
        return len(attacks) if attacks else 1

    def get_attack_by_id(self, attack_id: str) -> Optional[AttackDefinition]:
        """Look up any attack definition by its ID."""
        return self.attack_lookup.get(attack_id)

    # --- Enemy attacks ---

    def get_enemy_hurtbox_radius(self, enemy_id: str) -> float:
        """Get hurtbox radius for an enemy type."""
        data = self.enemy_data.get(enemy_id)
        if data:
            return data.get("hurtbox_radius", 0.5)
        # Fall back to default
        default = self.enemy_data.get("default")
        if default:
            return default.get("hurtbox_radius", 0.5)
        return 0.5

    def get_enemy_attacks(self, enemy_id: str) -> List[AttackDefinition]:
        """Get all attack definitions for an enemy type."""
        data = self.enemy_data.get(enemy_id)
        if not data:
            data = self.enemy_data.get("default", {})
        return data.get("_attack_defs", [])

    def get_enemy_phases(self, enemy_id: str) -> Dict[str, Dict[str, float]]:
        """Get phase-based attack weight overrides."""
        data = self.enemy_data.get(enemy_id, {})
        return data.get("phases", {})

    def select_enemy_attack(self, enemy_id: str,
                            dist_to_player: float,
                            health_ratio: float = 1.0) -> Optional[AttackDefinition]:
        """Select an enemy attack using weighted random, filtered by range and phase."""
        attacks = self.get_enemy_attacks(enemy_id)
        if not attacks:
            attacks = self.get_enemy_attacks("default")
        if not attacks:
            return None

        # Determine phase weights
        phases = self.get_enemy_phases(enemy_id)
        phase_key = "default"
        if health_ratio <= 0.25 and "below_25" in phases:
            phase_key = "below_25"
        elif health_ratio <= 0.5 and "below_50" in phases:
            phase_key = "below_50"

        phase_weights = phases.get(phase_key, {})

        # Build available attacks with weights
        available = []
        for attack_def in attacks:
            max_reach = attack_def.hitbox_radius + attack_def.hitbox_offset_forward
            if attack_def.projectile_id:
                max_reach = 999  # Ranged attacks always "in range"
            if dist_to_player <= max_reach * 1.3:  # 30% buffer
                weight = phase_weights.get(attack_def.attack_id, 1.0)
                if weight > 0:
                    available.append((attack_def, weight))

        if not available:
            return None

        # Weighted random selection
        total = sum(w for _, w in available)
        roll = random.uniform(0, total)
        cumulative = 0.0
        for attack_def, weight in available:
            cumulative += weight
            if roll <= cumulative:
                return attack_def
        return available[-1][0]

    # --- Projectiles ---

    def get_projectile(self, projectile_id: str) -> Optional[ProjectileDefinition]:
        return self.projectiles.get(projectile_id)

    # --- Hitbox definition helper ---

    @staticmethod
    def hitbox_def_from_attack(attack_def: AttackDefinition) -> HitboxDefinition:
        """Create a HitboxDefinition from an AttackDefinition's hitbox_params."""
        params = attack_def.hitbox_params
        return HitboxDefinition(
            shape=attack_def.hitbox_shape,
            radius=params.get("radius", 1.5),
            arc_degrees=params.get("arc_degrees", 90.0),
            width=params.get("width", 1.0),
            height=params.get("height", 0.5),
            length=params.get("length", 2.0),
            offset_forward=params.get("offset_forward", 0.8),
            offset_lateral=params.get("offset_lateral", 0.0),
            piercing=params.get("piercing", False),
        )

    # --- Internal loading ---

    def _load_weapon_attacks(self) -> bool:
        try:
            path = get_resource_path("Animation-Data.JSON/weapon-attacks.json")
            with open(str(path), 'r') as f:
                data = json.load(f)

            weapons = data.get("weapons", {})
            for weapon_type, weapon_data in weapons.items():
                attacks_raw = weapon_data.get("attacks", [])
                attack_defs = []
                for a in attacks_raw:
                    defn = self._parse_attack_definition(a)
                    attack_defs.append(defn)
                    self.attack_lookup[defn.attack_id] = defn
                self.weapon_attacks[weapon_type] = attack_defs

            return True
        except Exception as e:
            print(f"⚠ Error loading weapon attacks: {e}")
            self._create_fallback_weapon_attacks()
            return False

    def _load_enemy_attacks(self) -> bool:
        try:
            path = get_resource_path("Animation-Data.JSON/enemy-attacks.json")
            with open(str(path), 'r') as f:
                data = json.load(f)

            enemies = data.get("enemies", {})
            for enemy_id, enemy_data in enemies.items():
                attacks_raw = enemy_data.get("attacks", [])
                attack_defs = []
                for a in attacks_raw:
                    defn = self._parse_attack_definition(a)
                    attack_defs.append(defn)
                    self.attack_lookup[defn.attack_id] = defn
                enemy_data["_attack_defs"] = attack_defs
                self.enemy_data[enemy_id] = enemy_data

            return True
        except Exception as e:
            print(f"⚠ Error loading enemy attacks: {e}")
            return False

    def _load_projectiles(self) -> bool:
        try:
            path = get_resource_path("Animation-Data.JSON/projectile-definitions.json")
            with open(str(path), 'r') as f:
                data = json.load(f)

            for proj_id, proj_data in data.get("projectiles", {}).items():
                self.projectiles[proj_id] = ProjectileDefinition(
                    projectile_id=proj_id,
                    speed=proj_data.get("speed", 10.0),
                    max_range=proj_data.get("max_range", 15.0),
                    hitbox_radius=proj_data.get("hitbox_radius", 0.3),
                    sprite_id=proj_data.get("sprite_id", "magic_bolt"),
                    trail_type=proj_data.get("trail_type"),
                    homing=proj_data.get("homing", 0.0),
                    gravity=proj_data.get("gravity", 0.0),
                    piercing=proj_data.get("piercing", False),
                    aoe_on_hit=proj_data.get("aoe_on_hit"),
                    aoe_duration_ms=proj_data.get("aoe_duration_ms", 100.0),
                    visual=proj_data.get('visual', {}),
                    tags=proj_data.get('tags', []),
                )

            return True
        except Exception as e:
            print(f"⚠ Error loading projectile definitions: {e}")
            return False

    def _parse_attack_definition(self, data: dict) -> AttackDefinition:
        """Parse a single attack definition from JSON data."""
        hitbox_data = data.get("hitbox", {})
        return AttackDefinition(
            attack_id=data.get("attack_id", "unknown"),
            windup_ms=data.get("windup_ms", 200),
            active_ms=data.get("active_ms", 100),
            recovery_ms=data.get("recovery_ms", 150),
            cooldown_ms=data.get("cooldown_ms", 200),
            hitbox_shape=hitbox_data.get("shape", "arc"),
            hitbox_params=hitbox_data,
            damage_multiplier=data.get("damage_multiplier", 1.0),
            movement_multiplier=data.get("movement_multiplier", 0.7),
            can_be_interrupted=data.get("can_be_interrupted", True),
            animation_id=data.get("animation_id", "swing_medium"),
            projectile_id=data.get("projectile_id"),
            status_tags=data.get("status_tags", []),
            screen_shake=data.get("screen_shake", False),
            telegraph_color=data.get("telegraph_color", [255, 100, 100]),
            combo_next=data.get("combo_next"),
            combo_window_ms=data.get("combo_window_ms", 0),
            tags=data.get("tags", []),
        )

    def _create_fallback_weapon_attacks(self) -> None:
        """Create minimal fallback if JSON fails to load."""
        fallback = AttackDefinition(
            attack_id="fallback_swing",
            windup_ms=150,
            active_ms=100,
            recovery_ms=100,
            cooldown_ms=100,
            hitbox_shape="arc",
            hitbox_params={"shape": "arc", "radius": 1.5, "arc_degrees": 90,
                           "offset_forward": 0.8},
        )
        self.weapon_attacks["unarmed"] = [fallback]
        self.weapon_attacks["sword_1h"] = [fallback]
        self.attack_lookup[fallback.attack_id] = fallback

    def _get_fallback_attack(self) -> AttackDefinition:
        """Return a basic attack if nothing else is available."""
        existing = self.attack_lookup.get("fallback_swing")
        if existing:
            return existing
        self._create_fallback_weapon_attacks()
        return self.attack_lookup["fallback_swing"]


# Module-level singleton
_loader = None


def get_combat_data_loader() -> CombatDataLoader:
    """Get global combat data loader instance."""
    global _loader
    if _loader is None:
        _loader = CombatDataLoader()
    return _loader
