"""
Combat data loader — dynamic attack generation.

Instead of loading weapon attacks, enemy attacks, and projectiles from JSON,
this module generates them dynamically from weapon properties, enemy definitions,
and tags. This follows the project philosophy: system mechanics in code,
content values from existing JSON (items, enemies).

Attack definitions are created on-the-fly based on:
- Weapon type, range, attack speed, and tags
- Enemy category, tier, tags, and special abilities
- Projectile visuals derived from tags (no projectile JSON)
"""

import math
import random
from typing import Dict, List, Optional, Any

from Combat.attack_state_machine import AttackDefinition
from Combat.projectile_system import ProjectileDefinition
from Combat.hitbox_system import HitboxDefinition


# ============================================================================
# TAG-DRIVEN ATTACK GENERATION
# ============================================================================

# Weapon type -> base attack shape/timing profile
_WEAPON_PROFILES = {
    'sword_1h': {'shape': 'arc', 'arc': 90, 'windup': 300, 'active': 200, 'recovery': 240},
    'sword_2h': {'shape': 'arc', 'arc': 120, 'windup': 500, 'active': 300, 'recovery': 400},
    'dagger':   {'shape': 'arc', 'arc': 60, 'windup': 160, 'active': 120, 'recovery': 160},
    'axe':      {'shape': 'arc', 'arc': 100, 'windup': 400, 'active': 240, 'recovery': 360},
    'mace':     {'shape': 'arc', 'arc': 80, 'windup': 440, 'active': 260, 'recovery': 400},
    'hammer_2h': {'shape': 'arc', 'arc': 130, 'windup': 600, 'active': 360, 'recovery': 500},
    'spear':    {'shape': 'line', 'length': 2.5, 'windup': 360, 'active': 200, 'recovery': 300},
    'staff':    {'shape': 'arc', 'arc': 70, 'windup': 400, 'active': 240, 'recovery': 320},
    'bow':      {'shape': 'projectile', 'windup': 600, 'active': 100, 'recovery': 400},
    'unarmed':  {'shape': 'arc', 'arc': 70, 'windup': 200, 'active': 160, 'recovery': 200},
}

# Element tag -> telegraph/visual color
ELEMENT_COLORS = {
    "physical": [220, 220, 240],
    "fire": [255, 120, 30],
    "ice": [100, 200, 255],
    "frost": [100, 200, 255],
    "lightning": [255, 255, 80],
    "poison": [100, 255, 80],
    "arcane": [180, 80, 255],
    "shadow": [130, 80, 180],
    "holy": [255, 255, 180],
}

# Enemy category -> base attack profile
_ENEMY_ATTACK_PROFILES = {
    'beast':     {'shape': 'arc', 'arc': 80, 'windup': 600, 'active': 240, 'recovery': 400},
    'ooze':      {'shape': 'circle', 'radius': 1.0, 'windup': 800, 'active': 400, 'recovery': 600},
    'insect':    {'shape': 'arc', 'arc': 60, 'windup': 400, 'active': 160, 'recovery': 300},
    'construct': {'shape': 'arc', 'arc': 100, 'windup': 800, 'active': 400, 'recovery': 600},
    'undead':    {'shape': 'arc', 'arc': 90, 'windup': 700, 'active': 300, 'recovery': 500},
    'elemental': {'shape': 'circle', 'radius': 1.2, 'windup': 700, 'active': 360, 'recovery': 500},
    'aberration': {'shape': 'arc', 'arc': 120, 'windup': 600, 'active': 320, 'recovery': 400},
    'dragon':    {'shape': 'cone', 'arc': 140, 'windup': 1000, 'active': 500, 'recovery': 700},
    'humanoid':  {'shape': 'arc', 'arc': 80, 'windup': 500, 'active': 200, 'recovery': 360},
}


def _color_from_tags(tags: List[str], fallback=None) -> List[int]:
    """Get element color from tags."""
    if fallback is None:
        fallback = [220, 220, 240]
    for t in tags:
        if t in ELEMENT_COLORS:
            return list(ELEMENT_COLORS[t])
    return list(fallback)


def generate_weapon_attack(weapon_type: str, weapon_range: float,
                           attack_speed: float = 1.0,
                           weapon_tags: Optional[List[str]] = None) -> AttackDefinition:
    """Generate an attack definition dynamically from weapon properties.

    The hitbox radius matches the actual weapon range so visuals align with mechanics.
    """
    tags = weapon_tags or []
    profile = _WEAPON_PROFILES.get(weapon_type, _WEAPON_PROFILES['unarmed'])

    # Scale timing by attack speed (faster = shorter phases)
    speed_factor = 1.0 / max(0.3, attack_speed)

    # Determine shape and params based on profile
    shape = profile['shape']
    hitbox_params = {'offset_forward': 0.8}

    if shape == 'arc':
        hitbox_params['shape'] = 'arc'
        hitbox_params['radius'] = weapon_range  # Match actual weapon range
        hitbox_params['arc_degrees'] = profile['arc']
    elif shape == 'line':
        hitbox_params['shape'] = 'line'
        hitbox_params['length'] = weapon_range  # Match actual weapon range
    elif shape == 'projectile':
        hitbox_params['shape'] = 'arc'
        hitbox_params['radius'] = 0.5  # Small for projectile spawn point
        hitbox_params['arc_degrees'] = 30

    telegraph_color = _color_from_tags(tags)

    return AttackDefinition(
        attack_id=f"dynamic_{weapon_type}",
        windup_ms=profile['windup'] * speed_factor,
        active_ms=profile['active'] * speed_factor,
        recovery_ms=profile['recovery'] * speed_factor,
        cooldown_ms=100 * speed_factor,
        hitbox_shape=hitbox_params.get('shape', 'arc'),
        hitbox_params=hitbox_params,
        damage_multiplier=1.0,
        movement_multiplier=0.7,
        can_be_interrupted=True,
        animation_id=f"swing_{weapon_type}",
        projectile_id=f"dynamic_{weapon_type}_proj" if shape == 'projectile' else None,
        status_tags=[t for t in tags if t in ('burn', 'bleed', 'poison', 'freeze', 'stun', 'slow')],
        screen_shake=False,
        telegraph_color=telegraph_color,
        tags=tags,
    )


def generate_enemy_attack(enemy_def, attack_index: int = 0) -> AttackDefinition:
    """Generate an attack definition from an enemy definition.

    Uses the enemy's category for base shape, tier for timing/radius scaling,
    and tags for visual coloring.
    """
    category = getattr(enemy_def, 'category', 'beast')
    tier = getattr(enemy_def, 'tier', 1)
    enemy_tags = getattr(enemy_def, 'tags', [])
    visual_size = getattr(enemy_def, 'visual_size', 1.0)

    profile = _ENEMY_ATTACK_PROFILES.get(category, _ENEMY_ATTACK_PROFILES['beast'])

    # Tier scales attack radius and timing
    tier_radius_mult = {1: 1.0, 2: 1.3, 3: 1.6, 4: 2.0}.get(tier, 1.0)
    tier_speed_mult = {1: 1.0, 2: 0.95, 3: 0.9, 4: 0.85}.get(tier, 1.0)

    shape = profile['shape']
    hitbox_params = {'offset_forward': visual_size * 0.6}

    base_radius = visual_size * 0.8 * tier_radius_mult

    if shape == 'arc' or shape == 'cone':
        hitbox_params['shape'] = 'arc'
        hitbox_params['radius'] = base_radius
        hitbox_params['arc_degrees'] = profile.get('arc', 90)
    elif shape == 'circle':
        hitbox_params['shape'] = 'circle'
        hitbox_params['radius'] = base_radius
    elif shape == 'line':
        hitbox_params['shape'] = 'line'
        hitbox_params['length'] = base_radius * 1.5

    telegraph_color = _color_from_tags(enemy_tags, [255, 100, 100])

    return AttackDefinition(
        attack_id=f"enemy_{getattr(enemy_def, 'enemy_id', 'unknown')}_{attack_index}",
        windup_ms=profile['windup'] * tier_speed_mult,
        active_ms=profile['active'] * tier_speed_mult,
        recovery_ms=profile['recovery'] * tier_speed_mult,
        cooldown_ms=200 * tier_speed_mult,
        hitbox_shape=hitbox_params.get('shape', 'arc'),
        hitbox_params=hitbox_params,
        damage_multiplier=1.0,
        movement_multiplier=0.5,
        can_be_interrupted=True,
        animation_id=f"enemy_{category}_attack",
        status_tags=[],
        screen_shake=tier >= 3,
        telegraph_color=telegraph_color,
        tags=enemy_tags,
    )


def generate_projectile_from_tags(weapon_type: str,
                                  tags: Optional[List[str]] = None,
                                  base_speed: float = 12.0,
                                  base_range: float = 10.0) -> ProjectileDefinition:
    """Create a projectile definition dynamically from tags.

    Visual shape, color, trail, and behavior are all derived from tags.
    No JSON needed.
    """
    tags = tags or ['physical']
    color = _color_from_tags(tags)

    # Determine visual shape from tags
    is_arrow = any(t in tags for t in ('arrow', 'bow', 'crossbow'))
    is_beam = any(t in tags for t in ('beam', 'lightning'))
    is_shard = any(t in tags for t in ('ice', 'frost', 'crystal'))

    if is_arrow:
        vis_shape = 'elongated'
        length_px, width_px = 12, 3
    elif is_beam:
        vis_shape = 'beam'
        length_px, width_px = 20, 4
    elif is_shard:
        vis_shape = 'elongated'
        length_px, width_px = 8, 5
    else:
        vis_shape = 'orb'
        length_px, width_px = 8, 8

    # Trail type from element tags
    trail_type = None
    for t in tags:
        if t in ('fire', 'ice', 'frost', 'lightning', 'poison', 'arcane', 'shadow', 'holy'):
            trail_type = f"{t}_trail"
            break

    # Glow for magic projectiles
    has_glow = any(t in tags for t in ('fire', 'ice', 'frost', 'lightning', 'arcane', 'holy', 'shadow'))

    visual = {
        'shape': vis_shape,
        'color': color,
        'glow': has_glow,
        'glow_color': [min(255, c + 60) for c in color],
        'length_px': length_px,
        'width_px': width_px,
    }

    # Homing for certain types
    homing = 0.0
    if any(t in tags for t in ('homing', 'seeking')):
        homing = 0.5

    return ProjectileDefinition(
        projectile_id=f"dynamic_{weapon_type}_proj",
        speed=base_speed,
        max_range=base_range,
        hitbox_radius=0.3,
        sprite_id=vis_shape,
        trail_type=trail_type,
        homing=homing,
        gravity=0.0,
        piercing=any(t in tags for t in ('pierce', 'piercing')),
        visual=visual,
        tags=tags,
    )


# ============================================================================
# COMBAT DATA LOADER
# ============================================================================

class CombatDataLoader:
    """Provides combat data via dynamic generation from weapon/enemy properties.

    No JSON files required. All attack definitions are generated from
    weapon type, range, tags, and enemy definitions.
    """

    def __init__(self):
        self._weapon_cache: Dict[str, AttackDefinition] = {}
        self._enemy_cache: Dict[str, List[AttackDefinition]] = {}
        self._projectile_cache: Dict[str, ProjectileDefinition] = {}
        self._loaded = True  # Always "loaded" — data is generated dynamically

    def load_all(self) -> bool:
        """No-op — data is generated dynamically. Returns True."""
        print("✓ Combat data loader ready (dynamic generation)")
        return True

    @property
    def is_loaded(self) -> bool:
        return True

    # --- Weapon attacks ---

    def get_weapon_attack(self, weapon_type: str,
                          combo_index: int = 0,
                          weapon_range: float = 1.5,
                          attack_speed: float = 1.0,
                          weapon_tags: Optional[List[str]] = None) -> AttackDefinition:
        """Get or generate attack definition for a weapon type."""
        cache_key = f"{weapon_type}_{weapon_range}_{attack_speed}"
        if cache_key not in self._weapon_cache:
            self._weapon_cache[cache_key] = generate_weapon_attack(
                weapon_type, weapon_range, attack_speed, weapon_tags)
        return self._weapon_cache[cache_key]

    def get_weapon_combo_length(self, weapon_type: str) -> int:
        """No combo chains — single attacks only."""
        return 1

    def get_attack_by_id(self, attack_id: str) -> Optional[AttackDefinition]:
        """Look up cached attack by ID."""
        for atk in self._weapon_cache.values():
            if atk.attack_id == attack_id:
                return atk
        for enemy_attacks in self._enemy_cache.values():
            for atk in enemy_attacks:
                if atk.attack_id == attack_id:
                    return atk
        return None

    # --- Enemy attacks ---

    def get_enemy_hurtbox_radius(self, enemy_id: str) -> float:
        """Get hurtbox radius — delegates to EnemyDefinition.hurtbox_radius."""
        return 0.5  # Default; actual value comes from enemy.definition.hurtbox_radius

    def get_enemy_attacks(self, enemy_id: str,
                          enemy_def=None) -> List[AttackDefinition]:
        """Get attack definitions for an enemy, generating from its definition."""
        if enemy_id in self._enemy_cache:
            return self._enemy_cache[enemy_id]

        if enemy_def is None:
            # Return a default attack
            default = generate_enemy_attack(type('Def', (), {
                'category': 'beast', 'tier': 1, 'tags': [], 'visual_size': 1.0,
                'enemy_id': enemy_id
            })())
            return [default]

        attacks = [generate_enemy_attack(enemy_def, 0)]
        self._enemy_cache[enemy_id] = attacks
        return attacks

    def get_enemy_phases(self, enemy_id: str) -> Dict[str, Dict[str, float]]:
        """No phase system from JSON — returns empty."""
        return {}

    def select_enemy_attack(self, enemy_id: str,
                            dist_to_player: float,
                            health_ratio: float = 1.0,
                            enemy_def=None) -> Optional[AttackDefinition]:
        """Select an enemy attack based on range."""
        attacks = self.get_enemy_attacks(enemy_id, enemy_def)
        if not attacks:
            return None

        available = []
        for atk in attacks:
            max_reach = atk.hitbox_radius + atk.hitbox_offset_forward
            if atk.projectile_id:
                max_reach = 999
            if dist_to_player <= max_reach * 1.3:
                available.append(atk)

        if not available:
            return None
        return random.choice(available)

    # --- Projectiles ---

    def get_projectile(self, projectile_id: str,
                       weapon_type: str = 'bow',
                       tags: Optional[List[str]] = None) -> ProjectileDefinition:
        """Get or generate a projectile definition from tags."""
        if projectile_id in self._projectile_cache:
            return self._projectile_cache[projectile_id]

        proj = generate_projectile_from_tags(weapon_type, tags)
        self._projectile_cache[projectile_id] = proj
        return proj

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

    def clear_cache(self):
        """Clear all cached definitions."""
        self._weapon_cache.clear()
        self._enemy_cache.clear()
        self._projectile_cache.clear()


# Module-level singleton
_loader = None


def get_combat_data_loader() -> CombatDataLoader:
    """Get global combat data loader instance."""
    global _loader
    if _loader is None:
        _loader = CombatDataLoader()
    return _loader
