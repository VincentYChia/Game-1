# Tag System - Comprehensive Guide

**Status**: Production Ready
**Last Updated**: 2025-12-29

---

## Overview

The tag-driven effect system is the core combat mechanic in Game-1. All combat effects (damage, status effects, geometry, special behaviors) are defined through composable tags in JSON files.

**Key Principle**: Tags flow from JSON → Database → Equipment/Skills → Effect Executor → Game World

---

## Quick Reference

### Damage Type Tags
- `physical` - Physical damage (affected by defense)
- `fire` - Fire damage + can apply burn
- `ice` / `frost` - Ice damage + can apply freeze/chill
- `lightning` / `shock` - Lightning damage + can apply shock
- `poison` - Poison damage + can apply poison DoT
- `arcane` / `magic` - Magic damage (bypasses physical defense)
- `shadow` / `dark` - Shadow damage
- `holy` / `light` - Holy damage (bonus vs undead)
- `chaos` - Chaos damage (random effects)

### Geometry Tags
- `single` - Single target (primary target only)
- `chain` - Chain to nearby enemies (requires chain_count param)
- `cone` - Cone AoE in front of source (requires cone_angle, cone_range)
- `circle` - Circle AoE around point (requires circle_radius)
- `beam` - Line beam through enemies (requires beam_range, beam_width)
- `pierce` - Pierces through enemies in line

### Status Effect Tags
- `bleed` - Physical DoT (requires bleed_duration, bleed_damage_per_second)
- `burn` - Fire DoT (requires burn_duration, burn_damage_per_second)
- `poison` / `poison_status` - Poison DoT (requires poison_duration, poison_damage_per_second)
- `freeze` - Complete immobilization (requires freeze_duration)
- `chill` / `slow` - Movement speed reduction (requires duration, slow_factor)
- `stun` - Prevents all actions (requires duration)
- `root` - Prevents movement (requires duration)
- `shock` - Lightning DoT (requires shock_duration, shock_damage)
- `confuse` - Random movement (requires duration)
- `silence` - Prevents ability use (requires duration)
- `vulnerable` - Increased damage taken (requires duration, vulnerable_percent)
- `weaken` - Reduced damage dealt (requires duration, weaken_percent)

### Special Behavior Tags
- `knockback` - Push enemies away (requires knockback_distance)
- `pull` - Pull enemies toward source (requires pull_distance)
- `lifesteal` / `vampiric` - Heal for % of damage dealt (requires lifesteal_percent)
- `execute` - Bonus damage to low-health enemies (requires execute_threshold)
- `critical` - Critical hit mechanics
- `teleport` / `blink` - Teleport to target location
- `dash` / `charge` - Quick movement
- `phase` / `ethereal` - Pass through entities/walls
- `invisible` - Become invisible
- `reflect` - Reflect damage back to source
- `shield` - Absorb damage
- `summon` - Spawn entity (requires summonId, summonCount)

### Context Tags
- `self` - Effect applies to source
- `ally` - Effect applies to allies
- `enemy` - Effect applies to enemies (default)
- `all` - Effect applies to all entities
- `player` - Effect applies to player specifically

### Buff/Debuff Tags
- `empower` - Increase damage (requires empower_percent, duration)
- `fortify` - Increase defense (requires fortify_percent, duration)
- `haste` - Increase speed (requires haste_speed_bonus, duration)
- `enrage` - Increase damage but take more damage (requires duration)

---

## Tag System Applications

### 1. Skills (Player Abilities)

**File**: `Definitions.JSON/skills-*.JSON`

```json
{
  "skillId": "fireball",
  "name": "Fireball",
  "tags": ["fire", "circle", "burn"],
  "effectParams": {
    "baseDamage": 50,
    "circle_radius": 3.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  },
  "manaCost": 30,
  "cooldown": 5.0
}
```

**How it works**:
1. Player casts skill
2. SkillDatabase loads tags
3. EffectExecutor reads tags and creates EffectConfig
4. Geometry system (circle) finds all enemies in 3.0 radius
5. Damage system applies 50 fire damage to all targets
6. Status system applies burn DoT to all targets

### 2. Turrets (Placed Devices)

**File**: `items.JSON/items-engineering-1.JSON`

```json
{
  "itemId": "fire_arrow_turret",
  "name": "Fire Arrow Turret",
  "type": "turret",
  "effectTags": ["fire", "piercing", "single", "burn"],
  "effectParams": {
    "baseDamage": 35,
    "range": 7.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 5.0
  }
}
```

**How it works**:
1. Player places turret (double-click in inventory)
2. TurretSystem finds nearest enemy in range
3. Uses EffectExecutor with turret's tags
4. Single-target fire damage + burn applied to enemy

### 3. Enemy Abilities

**File**: `Definitions.JSON/hostiles-1.JSON`

```json
{
  "enemyId": "fire_imp",
  "abilities": [
    {
      "abilityId": "fireball",
      "tags": ["fire", "circle", "knockback", "player"],
      "effectParams": {
        "baseDamage": 40,
        "circle_radius": 2.5,
        "knockback_distance": 3.0
      },
      "cooldown": 8.0
    }
  ]
}
```

**How it works**:
1. Enemy AI checks if ability can be used
2. Enemy uses special ability
3. EffectExecutor processes tags (fire damage in circle + knockback)
4. Player and nearby entities take damage and are knocked back

### 4. Weapons (Equipment Tags)

**File**: `items.JSON/items-weapons-*.JSON`

```json
{
  "itemId": "flame_sword",
  "name": "Flame Sword",
  "attackTags": ["physical", "fire", "single", "burn"],
  "attackParams": {
    "burn_duration": 3.0,
    "burn_damage_per_second": 5.0
  }
}
```

**How it works**:
1. Player attacks enemy with weapon equipped
2. CombatManager gets weapon's attackTags
3. EffectExecutor processes tags (physical + fire damage + burn)
4. Enemy takes damage and gets burn status effect

### 5. Enchantments (Equipment Modifiers)

**File**: Equipment JSON `enchantments` array

```json
{
  "enchantments": [
    {
      "name": "Vampiric",
      "effect": {
        "type": "lifesteal",
        "value": 0.15
      }
    },
    {
      "name": "Chain Lightning",
      "effect": {
        "type": "chain_damage",
        "value": 2,
        "damage_percent": 0.5
      }
    }
  ]
}
```

**How it works**:
1. Enchantments processed in CombatManager after base damage
2. Lifesteal: Heal player for 15% of damage dealt
3. Chain Damage: Chain to 2 additional enemies for 50% damage each

### 6. Crafting Output Tags

**File**: Crafting recipes

```json
{
  "output": {
    "itemId": "iron_sword",
    "tags": ["sharp", "durable"]
  },
  "tagModifiers": {
    "sharp": 1.15,
    "durable": 1.2
  }
}
```

**How it works**:
1. Crafting system generates item with tags
2. Tags affect item stats (sharp → +15% damage, durable → +20% durability)
3. Tags stored in crafted_stats for the specific item instance

---

## Tag Combinations

Tags are **composable** - combine multiple tags for complex effects:

```json
["fire", "chain", "burn", "knockback"]
```

This creates:
- Fire damage (fire type)
- That chains to nearby enemies (chain geometry)
- Applies burn DoT to all hit (burn status)
- Knocks back all hit enemies (knockback special)

**Execution Order**:
1. Geometry (determine targets)
2. Damage (apply base damage)
3. Status Effects (apply DoTs/CC)
4. Special Behaviors (knockback, lifesteal, etc.)

---

## Tag Parameters

Most tags require parameters in `effectParams` or `attackParams`:

### Required Parameters by Tag

| Tag | Required Parameters | Example |
|-----|-------------------|---------|
| `chain` | `chain_count`, `chain_range` | `{"chain_count": 3, "chain_range": 5.0}` |
| `cone` | `cone_angle`, `cone_range` | `{"cone_angle": 45, "cone_range": 8.0}` |
| `circle` | `circle_radius` | `{"circle_radius": 4.0}` |
| `beam` | `beam_range`, `beam_width` | `{"beam_range": 12.0, "beam_width": 1.0}` |
| `burn` | `burn_duration`, `burn_damage_per_second` | `{"burn_duration": 5.0, "burn_damage_per_second": 8.0}` |
| `bleed` | `bleed_duration`, `bleed_damage_per_second` | `{"bleed_duration": 8.0, "bleed_damage_per_second": 3.0}` |
| `poison` | `poison_duration`, `poison_damage_per_second` | `{"poison_duration": 10.0, "poison_damage_per_second": 6.0}` |
| `freeze` | `freeze_duration` | `{"freeze_duration": 3.0}` |
| `slow` | `duration`, `slow_factor` | `{"duration": 5.0, "slow_factor": 0.5}` |
| `knockback` | `knockback_distance` | `{"knockback_distance": 3.0}` |
| `pull` | `pull_distance` | `{"pull_distance": 5.0}` |
| `lifesteal` | `lifesteal_percent` | `{"lifesteal_percent": 0.15}` |
| `summon` | `summonId`, `summonCount` | `{"summonId": "slime_tiny", "summonCount": 3}` |

---

## Debugging Tags

Use the TagSystemDebugger for comprehensive tag flow tracking:

```python
from core.tag_debug import get_tag_debugger

debugger = get_tag_debugger()
debugger.enable()  # Start logging

# Your code using tags...

debugger.disable()  # Stop logging
```

**Output Example**:
```
[TAG-FLOW] json_load: fireball → ['fire', 'circle', 'burn']
[TAG-FLOW] db_store: fireball → ['fire', 'circle', 'burn']
[TAG-FLOW] effect_executor: fireball → GEOMETRY: circle, DAMAGE: fire, STATUS: burn
[TAG-FLOW] targets: 3 enemies in circle_radius=3.0
[TAG-FLOW] damage: Applied 50 fire damage to 3 targets
[TAG-FLOW] status: Applied burn (5.0s, 8.0 dps) to 3 targets
```

---

## Best Practices

1. **Always include a geometry tag** (single, chain, cone, circle, beam, pierce)
   - Without geometry, effect applies to single target only

2. **Provide required parameters** in effectParams
   - Missing params will use defaults (often 0, causing no effect)

3. **Order matters for readability** (but not execution)
   - Good: `["fire", "chain", "burn"]`
   - Bad: `["burn", "fire", "chain"]`

4. **Test with debug mode** enabled
   - Catches missing params and tag issues early

5. **Use context tags** for targeting
   - `ally` for buffs, `enemy` for damage, `self` for self-buffs

6. **Don't mix contradictory tags**
   - Bad: `["single", "chain"]` - Geometry conflict
   - Bad: `["freeze", "slow"]` - Both apply movement CC

---

## Common Patterns

### High Damage Single Target
```json
["physical", "single", "critical", "bleed"]
```

### AoE Crowd Control
```json
["ice", "circle", "freeze", "slow"]
```

### DoT Damage Over Time
```json
["poison", "circle", "poison_status", "vulnerable"]
```

### Support Buff
```json
["self", "empower", "haste", "shield"]
```

### Chain Lightning
```json
["lightning", "chain", "shock"]
```

### Execute Burst
```json
["physical", "single", "execute", "critical"]
```

---

## Files Reference

**Core System**:
- `core/effect_executor.py` - Main tag processing engine
- `core/tag_registry.py` - Tag definitions and defaults
- `core/tag_debug.py` - Debug logging

**Integration Points**:
- `Combat/combat_manager.py` - Player combat (weapons, skills)
- `Combat/enemy.py` - Enemy AI and abilities
- `systems/turret_system.py` - Turret/trap/bomb effects
- `entities/character.py` - Enchantment processing

**Data Files**:
- `Definitions.JSON/skills-*.JSON` - Skill definitions
- `Definitions.JSON/hostiles-1.JSON` - Enemy abilities
- `items.JSON/items-weapons-*.JSON` - Weapon tags
- `items.JSON/items-engineering-1.JSON` - Turret/trap/bomb tags

---

## Support

For tag system issues:
1. Check `docs/tag-system/DEBUG-GUIDE.md`
2. Enable tag debugger: `get_tag_debugger().enable()`
3. Review `docs/tag-system/TAG-REFERENCE.md` for full tag catalog
4. Check `docs/tag-system/NAMING-CONVENTIONS.md` for naming rules

