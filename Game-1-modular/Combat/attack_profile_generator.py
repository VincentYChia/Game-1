"""
Attack Profile Generator — derives per-enemy attack definitions from existing JSON fields.

Instead of adding explicit "attacks" arrays to hostiles-1.JSON, this module
interprets the existing fields (category, tier, behavior, stats, metadata.tags,
aiPattern, specialAbilities) to procedurally generate EnemyAttackDef lists.

Design philosophy:
  - Zero JSON modifications — all attack variety comes from interpreting what's already there
  - Category defines the attack *style* (shapes, arc widths, timing feel)
  - Tier scales *power* (range, damage multipliers, screen shake)
  - Behavior refines *tempo* (aggressive = faster windups, boss = more variety)
  - Stats fine-tune (attackSpeed modulates timing, speed implies lunges, defense implies slow heavies)
  - Metadata tags add *flavor* (e.g., "aggressive" tag → shorter windups)
  - Special abilities inform secondary attacks (an enemy with "bleed" abilities gets a bleed melee)
"""
from __future__ import annotations

import random
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Combat.enemy import EnemyDefinition, EnemyAttackDef


# ============================================================================
# CATEGORY ATTACK ARCHETYPES
# ============================================================================
# Each category defines a base "feel" — the shapes and timing that make a
# wolf feel different from a golem. These are the building blocks that get
# combined and scaled by tier/behavior/stats.

_CATEGORY_ARCHETYPES = {
    'beast': {
        # Beasts bite (narrow arc) and claw (wider arc). Fast, physical.
        'primary':   {'id': 'bite',      'shape': 'arc', 'arc': 55,  'range': 1.4, 'windup': 500, 'active': 200, 'recovery': 350, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'claw',      'shape': 'arc', 'arc': 90,  'range': 1.2, 'windup': 400, 'active': 180, 'recovery': 300, 'weight': 2, 'tags': ['physical']},
        'heavy':     {'id': 'lunge',     'shape': 'arc', 'arc': 35,  'range': 2.2, 'windup': 650, 'active': 220, 'recovery': 450, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.3},
    },
    'ooze': {
        # Oozes engulf (circle) and splash (wide). Slow, often status-inflicting.
        'primary':   {'id': 'engulf',    'shape': 'circle', 'arc': 360, 'range': 1.2, 'windup': 700, 'active': 350, 'recovery': 500, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'splash',    'shape': 'circle', 'arc': 360, 'range': 1.8, 'windup': 850, 'active': 400, 'recovery': 600, 'weight': 1, 'tags': ['physical'], 'dmg_mult': 0.8},
        'heavy':     {'id': 'dissolve',  'shape': 'circle', 'arc': 360, 'range': 2.0, 'windup': 950, 'active': 450, 'recovery': 700, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.2},
    },
    'insect': {
        # Insects snap (narrow, fast) and charge (line). Fastest attacks.
        'primary':   {'id': 'mandible',  'shape': 'arc', 'arc': 45,  'range': 1.2, 'windup': 350, 'active': 140, 'recovery': 250, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'sting',     'shape': 'arc', 'arc': 30,  'range': 1.6, 'windup': 400, 'active': 160, 'recovery': 280, 'weight': 2, 'tags': ['physical']},
        'heavy':     {'id': 'charge',    'shape': 'arc', 'arc': 40,  'range': 2.5, 'windup': 550, 'active': 200, 'recovery': 400, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.4},
    },
    'construct': {
        # Constructs slam (wide, slow) and smash (huge). Heaviest timing.
        'primary':   {'id': 'slam',      'shape': 'arc', 'arc': 100, 'range': 1.6, 'windup': 750, 'active': 350, 'recovery': 550, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'sweep',     'shape': 'arc', 'arc': 140, 'range': 1.8, 'windup': 850, 'active': 400, 'recovery': 600, 'weight': 2, 'tags': ['physical']},
        'heavy':     {'id': 'smash',     'shape': 'arc', 'arc': 120, 'range': 2.4, 'windup': 1000, 'active': 450, 'recovery': 700, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.5},
    },
    'undead': {
        # Undead swipe (medium arc) and grab (narrow, slow). Eerie timing.
        'primary':   {'id': 'swipe',     'shape': 'arc', 'arc': 80,  'range': 1.4, 'windup': 600, 'active': 260, 'recovery': 420, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'grab',      'shape': 'arc', 'arc': 50,  'range': 1.6, 'windup': 700, 'active': 300, 'recovery': 500, 'weight': 2, 'tags': ['physical']},
        'heavy':     {'id': 'rend',      'shape': 'arc', 'arc': 70,  'range': 2.0, 'windup': 800, 'active': 350, 'recovery': 550, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.3},
    },
    'elemental': {
        # Elementals pulse (circle) and blast (cone). Magical flavor.
        'primary':   {'id': 'pulse',     'shape': 'circle', 'arc': 360, 'range': 1.5, 'windup': 600, 'active': 300, 'recovery': 450, 'weight': 3, 'tags': ['arcane']},
        'secondary': {'id': 'blast',     'shape': 'arc', 'arc': 120, 'range': 1.8, 'windup': 650, 'active': 320, 'recovery': 480, 'weight': 2, 'tags': ['arcane']},
        'heavy':     {'id': 'eruption',  'shape': 'circle', 'arc': 360, 'range': 2.5, 'windup': 800, 'active': 400, 'recovery': 600, 'weight': 1, 'tags': ['arcane'], 'shake': True, 'dmg_mult': 1.4},
    },
    'aberration': {
        # Aberrations lash (wide arc) and warp (circle). Unpredictable.
        'primary':   {'id': 'lash',      'shape': 'arc', 'arc': 110, 'range': 1.6, 'windup': 550, 'active': 280, 'recovery': 380, 'weight': 3, 'tags': ['shadow']},
        'secondary': {'id': 'warp_strike','shape': 'circle', 'arc': 360, 'range': 1.4, 'windup': 600, 'active': 300, 'recovery': 400, 'weight': 2, 'tags': ['shadow']},
        'heavy':     {'id': 'devour',    'shape': 'arc', 'arc': 90,  'range': 2.2, 'windup': 700, 'active': 350, 'recovery': 500, 'weight': 1, 'tags': ['shadow'], 'shake': True, 'dmg_mult': 1.4},
    },
    'dragon': {
        # Dragons breathe (huge cone) and tail (wide behind). Slowest but deadly.
        'primary':   {'id': 'bite',      'shape': 'arc', 'arc': 80,  'range': 2.0, 'windup': 800, 'active': 400, 'recovery': 600, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'breath',    'shape': 'arc', 'arc': 140, 'range': 3.0, 'windup': 1000, 'active': 500, 'recovery': 700, 'weight': 2, 'tags': ['fire'], 'dmg_mult': 1.2},
        'heavy':     {'id': 'tail_sweep','shape': 'arc', 'arc': 180, 'range': 2.5, 'windup': 900, 'active': 450, 'recovery': 650, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.5},
    },
    'humanoid': {
        # Humanoids swing (medium arc) and thrust (narrow). Balanced.
        'primary':   {'id': 'swing',     'shape': 'arc', 'arc': 75,  'range': 1.4, 'windup': 450, 'active': 180, 'recovery': 320, 'weight': 3, 'tags': ['physical']},
        'secondary': {'id': 'thrust',    'shape': 'arc', 'arc': 35,  'range': 1.8, 'windup': 500, 'active': 200, 'recovery': 360, 'weight': 2, 'tags': ['physical']},
        'heavy':     {'id': 'overhead',  'shape': 'arc', 'arc': 60,  'range': 1.6, 'windup': 600, 'active': 240, 'recovery': 420, 'weight': 1, 'tags': ['physical'], 'shake': True, 'dmg_mult': 1.3},
    },
}


# ============================================================================
# BEHAVIOR MODIFIERS
# ============================================================================
# Behavior string tells us the enemy's combat *tempo* and *variety*.
# Aggressive enemies attack faster; bosses get more attack types.

_BEHAVIOR_MODS = {
    # behavior_keyword: (windup_mult, recovery_mult, extra_attacks)
    'passive':     (1.15, 1.1, False),   # Slow, hesitant
    'docile':      (1.2,  1.15, False),  # Very slow
    'stationary':  (1.3,  1.2, False),   # Rooted, deliberate
    'territorial': (1.0,  1.0, False),   # Normal tempo
    'aggressive':  (0.85, 0.9, True),    # Fast, gets heavy attack
    'boss':        (0.9,  0.85, True),   # Fast + extra variety
}


# ============================================================================
# ABILITY TAG → STATUS TAG INFERENCE
# ============================================================================
# If an enemy has special abilities with certain tags, their melee attacks
# can inherit a status flavor. A wolf with "bleed" abilities might rake with claws.

_ABILITY_TAG_TO_STATUS = {
    'bleed': 'bleed',
    'poison': 'poison',
    'poison_status': 'poison',
    'burn': 'burn',
    'freeze': 'freeze',
    'chill': 'chill',
    'stun': 'stun',
    'slow': 'slow',
    'shock': 'shock',
}

# Damage type tags that can flavor melee attacks
_ABILITY_TAG_TO_ELEMENT = {
    'fire': 'fire',
    'ice': 'ice',
    'lightning': 'lightning',
    'poison': 'poison',
    'arcane': 'arcane',
    'shadow': 'shadow',
    'holy': 'holy',
    'chaos': 'shadow',  # chaos maps to shadow for visual purposes
}


# ============================================================================
# MAIN GENERATOR
# ============================================================================

def generate_attack_profile(enemy_def: 'EnemyDefinition') -> List['EnemyAttackDef']:
    """Generate a list of EnemyAttackDef from an enemy's existing JSON fields.

    Interpretation rules:
      1. category  → base attack archetype (shapes, arcs, timing feel)
      2. tier      → range scaling, screen shake on heavies (T3+), damage multipliers
      3. behavior  → tempo (aggressive=faster), variety (boss=more attacks)
      4. stats     → attackSpeed fine-tunes timing; high speed = melee gets shorter range;
                      high defense + low speed = heavier, slower swings
      5. metadata.tags → "aggressive"/"passive" override behavior feel
      6. specialAbilities → infer elemental/status tags for secondary melee attacks
    """
    from Combat.enemy import EnemyAttackDef

    category = enemy_def.category
    tier = enemy_def.tier
    behavior = enemy_def.behavior

    # 1. Get base archetype for this category
    archetype = _CATEGORY_ARCHETYPES.get(category, _CATEGORY_ARCHETYPES['beast'])

    # 2. Determine behavior modifier
    behavior_mod = _resolve_behavior_mod(behavior)
    windup_mult, recovery_mult, include_heavy = behavior_mod

    # 3. Check metadata tags for overrides
    meta_tags = set(enemy_def.tags)
    if 'aggressive' in meta_tags:
        windup_mult *= 0.9
        recovery_mult *= 0.9
        include_heavy = True
    if 'passive' in meta_tags or 'docile' in meta_tags:
        windup_mult *= 1.1
        recovery_mult *= 1.1

    # 4. Tier-based scaling
    tier_range_mult = {1: 1.0, 2: 1.15, 3: 1.3, 4: 1.5}.get(tier, 1.0)
    tier_shake_threshold = 3  # T3+ heavies get screen shake

    # 5. Infer elemental/status tags from special abilities
    inferred_element, inferred_status = _infer_tags_from_abilities(enemy_def.special_abilities)

    # 6. Stats-based adjustments
    #    High defense + low speed → "tank" feel: slower but wider arcs
    #    High speed + low defense → "glass cannon": faster, narrower
    is_tanky = enemy_def.defense > 20 and enemy_def.speed <= 0.8
    is_agile = enemy_def.speed >= 1.3 and enemy_def.defense < 15

    # 7. Build attack list
    attacks: List[EnemyAttackDef] = []

    # -- Primary attack (always present) --
    attacks.append(_build_attack(
        archetype['primary'],
        enemy_def,
        tier_range_mult=tier_range_mult,
        windup_mult=windup_mult,
        recovery_mult=recovery_mult,
        is_tanky=is_tanky,
        is_agile=is_agile,
    ))

    # -- Secondary attack (always present for T2+, gives variety) --
    if tier >= 2 or include_heavy:
        secondary = archetype['secondary'].copy()
        # Agile enemies get status-infused secondary (e.g., bleed claw)
        if inferred_status and is_agile:
            secondary['tags'] = secondary['tags'] + [inferred_status]
            secondary['status'] = [inferred_status]
        elif inferred_element:
            secondary['tags'] = [inferred_element]
        attacks.append(_build_attack(
            secondary,
            enemy_def,
            tier_range_mult=tier_range_mult,
            windup_mult=windup_mult,
            recovery_mult=recovery_mult,
            is_tanky=is_tanky,
            is_agile=is_agile,
        ))

    # -- Heavy attack (bosses, aggressive T3+, or behavior says so) --
    is_boss = 'boss' in behavior or 'boss' in meta_tags
    if include_heavy or is_boss or tier >= 3:
        heavy = archetype['heavy'].copy()
        # Bosses always get screen shake on heavy
        if is_boss or tier >= tier_shake_threshold:
            heavy['shake'] = True
        # Tanky enemies get even wider arcs on heavy
        if is_tanky:
            heavy['arc'] = min(360, int(heavy['arc'] * 1.3))
        # Infer element for heavy if abilities suggest it
        if inferred_element:
            heavy['tags'] = [inferred_element]
        attacks.append(_build_attack(
            heavy,
            enemy_def,
            tier_range_mult=tier_range_mult,
            windup_mult=windup_mult,
            recovery_mult=recovery_mult,
            is_tanky=is_tanky,
            is_agile=is_agile,
        ))

    # 8. Prefix attack IDs with enemy category for uniqueness
    for atk in attacks:
        atk.attack_id = f"{category}_{atk.attack_id}"

    return attacks


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _resolve_behavior_mod(behavior: str):
    """Match behavior string to modifier tuple. Handles compound behaviors
    like 'aggressive_pack' by checking for keyword containment."""
    for keyword, mod in _BEHAVIOR_MODS.items():
        if keyword in behavior:
            return mod
    # Default: normal tempo, no extra attacks
    return (1.0, 1.0, False)


def _infer_tags_from_abilities(abilities) -> tuple:
    """Scan an enemy's special abilities for elemental/status tags.

    Returns (element_tag_or_None, status_tag_or_None).
    Picks the most common element and first matching status.
    """
    element_counts = {}
    found_status = None

    for ability in abilities:
        for tag in ability.tags:
            if tag in _ABILITY_TAG_TO_ELEMENT:
                elem = _ABILITY_TAG_TO_ELEMENT[tag]
                element_counts[elem] = element_counts.get(elem, 0) + 1
            if found_status is None and tag in _ABILITY_TAG_TO_STATUS:
                found_status = _ABILITY_TAG_TO_STATUS[tag]

    # Pick most common element
    best_element = None
    if element_counts:
        best_element = max(element_counts, key=element_counts.get)

    return best_element, found_status


def _build_attack(
    template: dict,
    enemy_def: 'EnemyDefinition',
    tier_range_mult: float,
    windup_mult: float,
    recovery_mult: float,
    is_tanky: bool,
    is_agile: bool,
) -> 'EnemyAttackDef':
    """Build an EnemyAttackDef from an archetype template + enemy context."""
    from Combat.enemy import EnemyAttackDef

    # Base values from template
    arc = template['arc']
    range_val = template['range'] * tier_range_mult
    windup = template['windup'] * windup_mult
    active = template['active']
    recovery = template['recovery'] * recovery_mult
    tags = list(template['tags'])
    shake = template.get('shake', False)
    dmg_mult = template.get('dmg_mult', 1.0)
    status = list(template.get('status', []))

    # Tanky adjustments: wider arcs, slower swing
    if is_tanky:
        arc = min(360, int(arc * 1.2))
        windup *= 1.1
        active *= 1.15

    # Agile adjustments: faster, narrower, slightly more range (lunging feel)
    if is_agile:
        windup *= 0.85
        recovery *= 0.85
        arc = max(20, int(arc * 0.85))
        range_val *= 1.1

    return EnemyAttackDef(
        attack_id=template['id'],
        shape=template['shape'],
        arc=arc,
        range=round(range_val, 2),
        windup=round(windup),
        active=round(active),
        recovery=round(recovery),
        weight=template['weight'],
        tags=tags,
        screen_shake=shake,
        damage_multiplier=dmg_mult,
        status_tags=status,
    )
