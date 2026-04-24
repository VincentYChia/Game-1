# Turret Tag Configuration Guide

This document provides examples of how to configure engineering turrets using the tag system.

---

## Overview

Turrets now support tag-based effects through the `tags` and `effect_params` fields in `PlacedEntity`. This allows for complex, composable behavior without hardcoding specific turret types.

---

## Configuration Structure

Each turret should have:
- **tags**: List of effect tags (e.g., `["fire", "single_target", "burn"]`)
- **effect_params**: Dictionary of parameters for the effects

---

## Example Turret Configurations

### Basic Arrow Turret (T1)

**Legacy:**
```json
{
  "itemId": "basic_arrow_turret",
  "effect": "Fires arrows at enemies, 20 damage, 5 unit range"
}
```

**Tag System:**
```python
PlacedEntity(
    tags=["physical", "single_target"],
    effect_params={
        "baseDamage": 20,
        "range": 5.0
    }
)
```

---

### Fire Arrow Turret (T2)

**Legacy:**
```json
{
  "itemId": "fire_arrow_turret",
  "effect": "Fires flaming arrows, 35 damage + burn, 7 unit range"
}
```

**Tag System:**
```python
PlacedEntity(
    tags=["fire", "single_target", "burn"],
    effect_params={
        "baseDamage": 35,
        "range": 7.0,
        "burn_duration": 5.0,
        "burn_damage_per_second": 5.0
    }
)
```

**Behavior:**
- Fires at single target
- Deals 35 fire damage
- Applies burn status (5 DPS for 5 seconds = 25 additional damage)
- Total potential: 60 damage

---

### Lightning Cannon (T3)

**Legacy:**
```json
{
  "itemId": "lightning_cannon",
  "effect": "Fires lightning bolts, 70 damage + chain, 10 unit range"
}
```

**Tag System:**
```python
PlacedEntity(
    tags=["lightning", "chain", "shock"],
    effect_params={
        "baseDamage": 70,
        "range": 10.0,
        "chain_count": 2,         # Hits 3 total (primary + 2 chains)
        "chain_range": 5.0,       # Chain within 5 units
        "chain_falloff": 0.3,     # 30% less damage per jump
        "shock_duration": 2.0     # Stun for 2 seconds
    }
)
```

**Behavior:**
- Hits primary target for 70 lightning damage
- Chains to 2 nearby enemies within 5 units
  - 2nd target: 70 * 0.7 = 49 damage
  - 3rd target: 49 * 0.7 = 34 damage
- Each target is shocked (stunned) for 2 seconds
- Total damage: 153 across 3 targets
- Synergy bonus: Lightning + chain = +20% chain range (from tag-definitions.JSON)

---

### Flamethrower Turret (T3)

**Legacy:**
```json
{
  "itemId": "flamethrower_turret",
  "effect": "Sweeps area with fire, 50 damage + burn, 8 unit range"
}
```

**Tag System:**
```python
PlacedEntity(
    tags=["fire", "cone", "burn"],
    effect_params={
        "baseDamage": 50,
        "range": 8.0,
        "cone_angle": 60.0,       # 60 degree cone
        "cone_range": 8.0,        # 8 unit range
        "burn_duration": 8.0,     # Long burn
        "burn_damage_per_second": 8.0
    }
)
```

**Behavior:**
- Fires in a 60-degree cone
- Hits all enemies in cone for 50 fire damage
- Applies burn (8 DPS for 8 seconds = 64 additional damage)
- Excellent for grouped enemies
- Total damage per target: 114

---

### Frost Turret (Example)

**Not in current items, but could be created:**
```python
PlacedEntity(
    tags=["frost", "circle", "freeze", "slow"],
    effect_params={
        "baseDamage": 30,
        "range": 6.0,
        "circle_radius": 4.0,     # AOE around turret
        "freeze_duration": 3.0,   # Freeze for 3 seconds
        "slow_duration": 5.0,     # Slow after freeze
        "slow_percent": 0.5       # 50% slow
    }
)
```

**Behavior:**
- AOE around turret (4 unit radius)
- Deals 30 frost damage to all enemies in radius
- Freezes enemies for 3 seconds (immobilized)
- After freeze expires, applies 50% slow for 5 seconds
- Defensive turret for area control

---

### Laser Turret (T3)

**Current:**
```json
{
  "itemId": "laser_turret",
  "effect": "Precise and devastating laser beam"
}
```

**Tag System (Beam Geometry):**
```python
PlacedEntity(
    tags=["energy", "beam", "pierce"],
    effect_params={
        "baseDamage": 80,
        "range": 12.0,
        "beam_range": 12.0,
        "beam_width": 1.0,        # Narrow beam
        "pierce_count": 3,        # Hits up to 3 enemies
        "pierce_falloff": 0.2     # 20% less per enemy
    }
)
```

**Behavior:**
- Fires a narrow beam 12 units long
- Pierces up to 3 enemies in line
  - 1st: 80 damage
  - 2nd: 64 damage
  - 3rd: 51 damage
- Total: 195 damage across 3 targets
- Best when enemies are lined up

---

### Healing Beacon (T3)

**Current:**
```json
{
  "itemId": "healing_beacon",
  "effect": "Continuous healing in area"
}
```

**Tag System (Support Device):**
```python
PlacedEntity(
    tags=["healing", "circle", "ally", "regeneration"],
    effect_params={
        "baseHealing": 0,         # No instant heal
        "range": 8.0,
        "circle_radius": 8.0,
        "regen_heal_per_second": 10.0,
        "regen_duration": 10.0    # 10 seconds regen
    }
)
```

**Behavior:**
- Pulses every attack (based on attack_speed)
- Affects all allies in 8 unit radius
- Applies regeneration (10 HP/sec for 10 seconds)
- Total healing: 100 HP per pulse
- Refreshes on each pulse (stacks up to 3 times)

---

### Poison Trap (T2)

**Current:**
```json
{
  "itemId": "poison_trap",
  "effect": "Poison gas on trigger"
}
```

**Tag System:**
```python
PlacedEntity(
    tags=["poison", "circle", "poison_status", "slow"],
    effect_params={
        "baseDamage": 20,
        "range": 3.0,             # Trigger range
        "circle_radius": 4.0,     # Gas cloud
        "poison_duration": 15.0,  # Long poison
        "poison_damage_per_second": 3.0,
        "slow_duration": 8.0,
        "slow_percent": 0.4       # 40% slow
    }
)
```

**Behavior:**
- Triggered when enemy enters range
- AOE cloud (4 unit radius)
- Deals 20 initial poison damage
- Applies poison status (3 DPS for 15 seconds = 45 damage)
- Applies 40% slow for 8 seconds
- Total damage: 65 per target
- Area denial effect

---

## Advanced Combinations

### Multi-Element Turret (Hypothetical)

```python
PlacedEntity(
    tags=["fire", "frost", "chain", "burn", "slow"],
    effect_params={
        "baseDamage": 60,
        "range": 8.0,
        "chain_count": 2,
        "chain_range": 4.0,
        "burn_duration": 4.0,
        "burn_damage_per_second": 6.0,
        "slow_duration": 6.0,
        "slow_percent": 0.3
    }
)
```

**Behavior:**
- Chains to 3 targets total
- Each target takes fire AND frost damage
- Applies burn (24 damage over time)
- Applies slow (30% for 6 seconds)
- Note: Fire and frost are conflicting elements, may have reduced effectiveness

---

## Implementation Notes

### Creating Tagged Turrets

When crafting or placing a turret, the game should:

1. Look up the turret definition in `items-engineering-1.JSON`
2. Convert the `effect` text to appropriate tags (or use pre-defined tags in JSON)
3. Create `PlacedEntity` with tags and effect_params
4. Turret system automatically uses tag-based effects

### Backward Compatibility

The turret system supports both:
- **Legacy**: `damage` field for simple damage
- **Tag System**: `tags` + `effect_params` for complex effects

If `tags` is empty, falls back to legacy damage.

### Geometry and Targeting

Turrets can use geometry tags to control firing patterns:
- `single_target` - Fires at nearest enemy (default)
- `chain` - Arcs to multiple enemies
- `cone` - Sweeps area in front of turret
- `circle` - AOE around turret or target
- `beam` - Line of sight piercing

The turret's `range` field determines detection range, while geometry tags determine effect range.

---

## Migration Path

### Step 1: Add Tags to Item JSONs

Update `items-engineering-1.JSON`:

```json
{
  "itemId": "fire_arrow_turret",
  "name": "Fire Arrow Turret",
  "effect": "Fires flaming arrows, 35 damage + burn, 7 unit range",
  "tags": ["fire", "single_target", "burn"],
  "effectParams": {
    "baseDamage": 35,
    "burn_duration": 5.0,
    "burn_damage_per_second": 5.0
  }
}
```

### Step 2: Update Placement Logic

When creating `PlacedEntity` from item:

```python
def create_turret(item_def, position):
    return PlacedEntity(
        position=position,
        item_id=item_def["itemId"],
        entity_type=PlacedEntityType.TURRET,
        tier=item_def["tier"],
        range=item_def.get("range", 5.0),
        attack_speed=item_def.get("attackSpeed", 1.0),
        tags=item_def.get("tags", []),
        effect_params=item_def.get("effectParams", {})
    )
```

### Step 3: Test

Place turrets and verify:
- Single-target turrets hit correctly
- Chain turrets jump to nearby enemies
- Cone turrets hit multiple enemies in arc
- Status effects apply correctly
- Debug logs show tag execution

---

## Performance Considerations

- Tag system adds minimal overhead (~1ms per effect)
- Geometry calculations cached where possible
- Effect executor optimized for repeated calls
- Status effects update efficiently

---

## Future Enhancements

Potential additions:
- **Turret upgrades**: Add tags/modify params dynamically
- **Combo effects**: Turrets synergize with nearby turrets
- **Smart targeting**: Priority targets (low HP, high threat)
- **Conditional effects**: Triggers based on enemy type
- **Multi-phase**: Different effects at different health thresholds

---

**END OF TURRET TAG CONFIGURATION GUIDE**
