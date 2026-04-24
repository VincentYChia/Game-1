# High-Impact Gameplay Features - Comprehensive Analysis

**Created**: 2025-12-29
**Purpose**: Complete audit of special mechanics, turret/trap AI, and adornment effects

---

## Executive Summary

### ✅ What Works
- **Turret AI**: Fully implemented with targeting, attacking, and tag system integration
- **Basic Special Mechanics**: lifesteal, knockback, pull (velocity-based)
- **Tag System Foundation**: All tags defined, registry working, effect executor extensible
- **Equipment Tags**: Weapons use tags, modifiers calculated

### ❌ What's Missing
- **5 Special Mechanics**: reflect, summon, teleport, dash, execute (TODO in code)
- **Trap Triggering**: No proximity/contact detection system
- **Adornment Effects**: Accessories load but tags NOT collected for attacks
- **Device Effects**: Bombs, utility devices (grappling hook, healing beacon, etc.)

---

## 1. Special Tag Mechanics - DETAILED AUDIT

### 📋 Complete Tag Inventory (from tag-definitions.JSON)

#### ✅ IMPLEMENTED Special Mechanics

| Tag | Category | Status | Implementation Location |
|-----|----------|--------|------------------------|
| **lifesteal** | special | ✅ WORKING | `effect_executor.py:214` `_apply_lifesteal()` |
| **vampiric** | special | ✅ WORKING | Alias for lifesteal |
| **knockback** | special | ✅ WORKING | `effect_executor.py:221` `_apply_knockback()` - Velocity-based, smooth motion |
| **pull** | special | ✅ WORKING | `effect_executor.py:283` `_apply_pull()` - Instant position change |

**Knockback Implementation Details**:
```python
# Velocity-based smooth knockback over 0.5s (not instant teleport)
velocity_magnitude = knockback_distance / knockback_duration  # tiles/second
target.knockback_velocity_x = dx * velocity_magnitude
target.knockback_velocity_y = dy * velocity_magnitude
target.knockback_duration_remaining = knockback_duration
```

#### ❌ NOT IMPLEMENTED Special Mechanics

| Tag | Default Params | Required For | Difficulty | Notes |
|-----|----------------|--------------|------------|-------|
| **reflect** | `reflect_percent: 0.3`<br>`reflect_type: "damage"` | Thorns armor, reflect shields | MEDIUM | Need damage tracking, reverse source/target |
| **summon** | `summon_id: required`<br>`summon_count: 1`<br>`summon_duration: 30.0` | Summoning spells, minions | HARD | Need entity spawning system, AI control |
| **teleport** | `teleport_range: 10.0`<br>`teleport_type: "targeted"` | Blink skills, teleport items | MEDIUM | Need position validation, pathing check |
| **dash** | `dash_distance: 5.0`<br>`dash_speed: 20.0`<br>`damage_on_contact: false` | Charge abilities, gap closers | MEDIUM | Need rapid movement, collision detection |
| **execute** | `threshold_hp: 0.2`<br>`bonus_damage: 2.0` | Finisher abilities | EASY | Simple HP threshold check |
| **critical** | `crit_chance: 0.15`<br>`crit_multiplier: 2.0` | Crit-based builds | EASY | Random roll, damage multiplication |
| **phase** | `phase_duration: 2.0`<br>`can_pass_walls: false` | Intangibility skills | HARD | Need collision system override |

**Code Location**: `core/effect_executor.py:206-212` (TODO comment)

```python
# TODO: Implement other special mechanics
# - reflect/thorns
# - summon
# - teleport
# - dash/charge
# - execute
# - critical
```

---

## 2. Turret/Trap AI and Triggering

### ✅ TURRET SYSTEM - Fully Implemented

**File**: `systems/turret_system.py` (139 lines)

#### Architecture
```python
class TurretSystem:
    def update(placed_entities, combat_manager, dt):
        # 1. Update lifetime (despawn expired)
        # 2. Find nearest enemy in range
        # 3. Check attack cooldown
        # 4. Attack using tag system or legacy damage
```

#### Features That Work
- ✅ **Lifetime Management**: Turrets despawn after duration (default 300s)
- ✅ **Enemy Targeting**: `_find_nearest_enemy()` - distance-based targeting
- ✅ **Attack Cooldown**: Respects attack_speed (attacks per second)
- ✅ **Tag System Integration**: Uses `effect_executor.execute_effect()` with turret tags
- ✅ **Legacy Fallback**: Direct damage if no tags configured
- ✅ **Visual Feedback**: Console output for attacks, target lines for rendering

#### Turret Data Structure (PlacedEntity)
```python
@dataclass
class PlacedEntity:
    position: Position
    item_id: str
    entity_type: PlacedEntityType  # TURRET, TRAP, BOMB, etc.
    tier: int = 1
    health: float = 100.0

    # Turret-specific (legacy)
    range: float = 5.0
    damage: float = 20.0
    attack_speed: float = 1.0  # Attacks per second

    # Tag system integration
    tags: List[str] = []  # e.g., ["fire", "chain", "burn"]
    effect_params: Dict = {}  # e.g., {"baseDamage": 25, "chain_count": 3}

    # Lifetime
    lifetime: float = 300.0
    time_remaining: float = 300.0
```

#### How Turrets Attack
```python
def _attack_enemy(turret, enemy):
    if turret.tags and len(turret.tags) > 0:
        # TAG SYSTEM - preferred
        context = effect_executor.execute_effect(
            source=turret,
            primary_target=enemy,
            tags=turret.tags,
            params=turret.effect_params,
            available_entities=[enemy]
        )
        # Applies geometry (chain, cone), damage types (fire), status (burn)
    else:
        # LEGACY - fallback
        enemy.current_health -= turret.damage
```

### ❌ TRAP SYSTEM - Triggering NOT Implemented

**Status**: Infrastructure exists (PlacedEntityType.TRAP), but NO triggering logic

#### What Exists
- ✅ `PlacedEntityType.TRAP` enum value
- ✅ Can place traps in world
- ✅ Traps have lifetime management
- ⚠️ `turret_system.py:38` - Only processes `TURRET` type, skips traps

```python
# Only process turrets for combat
if entity.entity_type != PlacedEntityType.TURRET:
    continue  # TRAPS ARE SKIPPED!
```

#### What's Missing
| Feature | Status | Required Implementation |
|---------|--------|------------------------|
| **Proximity Detection** | ❌ NOT IMPL | Need distance check to player/enemies |
| **Contact Detection** | ❌ NOT IMPL | Need collision system integration |
| **Trigger Activation** | ❌ NOT IMPL | Need `on_proximity` / `on_contact` handlers |
| **One-time Triggers** | ❌ NOT IMPL | Need consumed/triggered state |
| **Multi-trigger Traps** | ❌ NOT IMPL | Need trigger count tracking |

#### Implementation Requirements

**Option 1: Proximity Traps**
```python
def update_traps(placed_entities, all_enemies, player_position, dt):
    for trap in [e for e in placed_entities if e.entity_type == TRAP]:
        trigger_range = trap.effect_params.get('trigger_range', 2.0)

        # Check player proximity
        player_dist = distance(trap.position, player_position)
        if player_dist <= trigger_range:
            trigger_trap(trap, player)
            continue

        # Check enemy proximity
        for enemy in all_enemies:
            enemy_dist = distance(trap.position, enemy.position)
            if enemy_dist <= trigger_range:
                trigger_trap(trap, enemy)
                break
```

**Option 2: Contact Traps**
```python
def check_trap_collision(trap, entity):
    # Check if entity moved into trap tile this frame
    trap_tile = (int(trap.position.x), int(trap.position.y))
    entity_tile = (int(entity.position.x), int(entity.position.y))

    if trap_tile == entity_tile and not trap.triggered:
        trigger_trap(trap, entity)
```

**Trigger Execution**
```python
def trigger_trap(trap, target):
    if trap.tags:
        # Use tag system
        context = effect_executor.execute_effect(
            source=trap,
            primary_target=target,
            tags=trap.tags,
            params=trap.effect_params,
            available_entities=[target]
        )
    else:
        # Legacy damage
        target.current_health -= trap.damage

    # Mark as triggered, remove if one-time
    trap.triggered = True
    if trap.effect_params.get('one_time', True):
        placed_entities.remove(trap)
```

### ❌ BOMB SYSTEM - Placement Mechanics Incomplete

**Status**: Explosion works (via tag system), but placement/detonation incomplete

#### What Works
- ✅ `PlacedEntityType.BOMB` enum value
- ✅ Tag system can handle `["fire", "circle", "burn"]` explosions
- ✅ Geometry (circle) calculates AOE targets

#### What's Missing
| Feature | Status | Needed For |
|---------|--------|------------|
| **Placement UI** | ❌ NOT IMPL | Where to throw bomb? |
| **Fuse Timer** | ❌ NOT IMPL | Delayed detonation |
| **Manual Detonation** | ❌ NOT IMPL | Remote trigger bombs |
| **Physics/Arc** | ❌ NOT IMPL | Thrown bomb trajectory |

---

## 3. Adornment (Accessory) Effects

### ⚠️ CRITICAL FINDING: Adornments Load But Tags NOT Collected

#### What Exists

**Adornment Items in JSON** (`items-smithing-2.JSON`):
```json
{
  "itemId": "copper_fire_ring",
  "name": "Copper Fire Ring",
  "type": "accessory",
  "subtype": "ring",
  "slot": "accessory",
  "tier": 1,
  "attributes": [
    {
      "type": "damage",
      "element": "fire",
      "value": 5,
      "effect": "Adds fire damage to attacks"
    }
  ],
  "metadata": {
    "tags": ["accessory", "ring", "fire", "elemental"]
  }
}
```

**3 Adornments Found**:
1. `copper_fire_ring` - T1, adds fire damage, tags: `["accessory", "ring", "fire", "elemental"]`
2. `iron_water_amulet` - T2, adds water damage, tags: `["accessory", "amulet", "water", "elemental"]`
3. `steel_lightning_bracelet` - T3, adds lightning damage, tags: `["accessory", "bracelet", "lightning", "elemental"]`

#### The Problem: Tags Not Applied to Attacks

**Where Weapon Tags ARE Collected** (`combat_manager.py:556-575`):
```python
# Weapon tags collected and applied
weapon_tags = equipped_weapon.get_metadata_tags()
if weapon_tags:
    weapon_tag_damage_mult = WeaponTagModifiers.get_damage_multiplier(weapon_tags)
    weapon_tag_crit_bonus = WeaponTagModifiers.get_crit_chance_bonus(weapon_tags)
    # ... applied to attack
```

**Where Accessory Tags SHOULD BE Collected** (MISSING):
```python
# ❌ NO CODE EXISTS FOR THIS
# Need to add:
accessory_tags = self.character.equipment.get_all_accessory_tags()
# Merge with weapon tags
all_tags = weapon_tags + accessory_tags
# Pass to effect executor
```

#### Adornment Tag Effects (Based on Tag Definitions)

| Adornment | Tags | Expected Effect | Current Status |
|-----------|------|-----------------|----------------|
| Copper Fire Ring | `["fire", "elemental"]` | +5 fire damage, 10% burn chance | ❌ Tags ignored, only `attributes.damage` applied |
| Iron Water Amulet | `["water", "elemental"]` | +10 water damage | ❌ Tags ignored |
| Steel Lightning Bracelet | `["lightning", "elemental"]` | +20 lightning damage, chain synergy | ❌ Tags ignored |

#### What SHOULD Happen (If Implemented)

1. **Elemental Damage Addition**:
   - Fire ring adds `"fire"` tag → 10% chance to apply `burn` status
   - Lightning bracelet adds `"lightning"` tag → Synergy with chain effects

2. **Tag Merging**:
   ```python
   weapon_tags = ["physical", "single_target"]  # From equipped weapon
   accessory_tags = ["fire"]  # From fire ring
   combined_tags = ["physical", "fire", "single_target"]  # Merged for attack
   ```

3. **Effect Execution**:
   - Physical damage (from weapon stats)
   - Fire damage (from ring `attributes.damage`)
   - 10% burn chance (from `fire` tag auto-apply)
   - Status effects stack with weapon effects

#### Implementation Required

**Step 1: Collect Accessory Tags** (Equipment Manager):
```python
# In equipment.py or equipment_manager.py
def get_all_accessory_tags(self) -> List[str]:
    """Collect tags from all equipped accessories"""
    all_tags = []

    # Check all accessory slots
    for slot_name in ['accessory', 'ring', 'amulet', 'bracelet']:  # Multi-slot?
        item = self.slots.get(slot_name)
        if item and hasattr(item, 'get_metadata_tags'):
            tags = item.get_metadata_tags()
            if tags:
                all_tags.extend(tags)

    return all_tags
```

**Step 2: Merge Tags in Combat** (Combat Manager):
```python
# In combat_manager.py:player_attack_enemy_with_tags()
# BEFORE execute_effect():

# Merge weapon tags + accessory tags
base_tags = tags.copy()  # From weapon/skill
accessory_tags = self.character.equipment.get_all_accessory_tags()

# Filter out non-combat tags (accessory, ring, amulet labels)
combat_tags = [t for t in accessory_tags if t not in ['accessory', 'ring', 'amulet', 'bracelet']]

# Merge
final_tags = base_tags + combat_tags
print(f"   🏷️  Merged tags: {final_tags}")

# Execute with merged tags
context = self.effect_executor.execute_effect(
    source=self.character,
    primary_target=enemy,
    tags=final_tags,  # Use merged tags!
    params=effect_params,
    available_entities=alive_enemies
)
```

**Step 3: Update Legacy Attack** (For non-tag attacks):
```python
# In combat_manager.py:player_attack_enemy() - legacy method
# Add accessory tag bonuses to damage calculation

accessory_tags = self.character.equipment.get_all_accessory_tags()
if 'fire' in accessory_tags:
    # Apply burn chance
    if random.random() < 0.10:
        apply_burn_status(enemy, duration=5.0, damage_per_tick=5.0)
```

---

## 4. Missing Features - COMPREHENSIVE LIST

### Priority 1: HIGH IMPACT (Core Gameplay)

| Feature | Type | Difficulty | Impact | Estimated Effort |
|---------|------|------------|--------|------------------|
| **Adornment Tag Collection** | Accessory Effects | EASY | HIGH | 1-2 hours |
| **Execute Mechanic** | Special Tag | EASY | MEDIUM | 30 min |
| **Critical Mechanic** | Special Tag | EASY | HIGH | 1 hour |
| **Trap Proximity Triggers** | Device | MEDIUM | HIGH | 2-3 hours |
| **Reflect/Thorns** | Special Tag | MEDIUM | MEDIUM | 2-3 hours |

### Priority 2: MEDIUM IMPACT (Enhanced Gameplay)

| Feature | Type | Difficulty | Impact | Estimated Effort |
|---------|------|------------|--------|------------------|
| **Teleport/Blink** | Special Tag | MEDIUM | MEDIUM | 2-3 hours |
| **Dash/Charge** | Special Tag | MEDIUM | MEDIUM | 3-4 hours |
| **Bomb Placement UI** | Device | MEDIUM | MEDIUM | 2-3 hours |
| **Trap Contact Detection** | Device | MEDIUM | MEDIUM | 1-2 hours |

### Priority 3: LOW IMPACT (Advanced Features)

| Feature | Type | Difficulty | Impact | Estimated Effort |
|---------|------|------------|--------|------------------|
| **Summon System** | Special Tag | HARD | LOW | 6-8 hours |
| **Phase/Intangibility** | Special Tag | HARD | LOW | 4-6 hours |
| **Bomb Physics/Arc** | Device | MEDIUM | LOW | 2-3 hours |
| **Multi-trigger Traps** | Device | EASY | LOW | 1 hour |

---

## 5. Implementation Recommendations

### Quick Wins (< 2 hours each)

#### 1. Adornment Tag Collection ⭐ HIGHEST PRIORITY
**Why**: 3 accessories already exist in game, tags defined, just not collected
**Effort**: 1-2 hours
**Files**: `equipment.py`, `combat_manager.py`

```python
# Add to equipment.py
def get_all_accessory_tags(self):
    tags = []
    for slot in ['accessory']:  # Expand if multiple accessory slots
        item = self.slots.get(slot)
        if item:
            tags.extend(item.get_metadata_tags() or [])
    return [t for t in tags if t not in ['accessory', 'ring', 'amulet']]

# Add to combat_manager.py:player_attack_enemy_with_tags()
accessory_tags = self.character.equipment.get_all_accessory_tags()
final_tags = tags + accessory_tags
# Use final_tags in execute_effect()
```

#### 2. Execute Mechanic
**Why**: Simple HP threshold check, big impact for finisher builds
**Effort**: 30 minutes
**File**: `effect_executor.py`

```python
def _apply_execute(self, source, target, params):
    threshold_hp = params.get('threshold_hp', 0.2)
    bonus_damage = params.get('bonus_damage', 2.0)

    if hasattr(target, 'current_health') and hasattr(target, 'max_health'):
        hp_percent = target.current_health / target.max_health
        if hp_percent <= threshold_hp:
            # Apply bonus damage
            execute_damage = config.base_damage * (bonus_damage - 1.0)
            target.current_health -= execute_damage
            print(f"   ⚡ EXECUTE! +{execute_damage:.1f} bonus damage")
```

#### 3. Critical Mechanic
**Why**: Random crit is engaging, tag system perfect for this
**Effort**: 1 hour
**File**: `effect_executor.py`

```python
def _apply_critical(self, config, magnitude_mult):
    crit_chance = config.params.get('crit_chance', 0.15)
    crit_multiplier = config.params.get('crit_multiplier', 2.0)

    if random.random() < crit_chance:
        print(f"   💥 CRITICAL HIT! ({crit_multiplier}x damage)")
        return crit_multiplier
    return 1.0

# In _apply_damage():
crit_mult = self._apply_critical(config, magnitude_mult)
final_damage = base_damage * crit_mult
```

### Medium Complexity (2-4 hours each)

#### 4. Trap Proximity System
**Why**: Traps exist but do nothing, this makes them functional
**Effort**: 2-3 hours
**Files**: `turret_system.py` (rename to `placed_entity_system.py`), `game_engine.py`

```python
class PlacedEntitySystem:
    def update_traps(self, placed_entities, all_enemies, player_pos, dt):
        for trap in [e for e in placed_entities if e.entity_type == TRAP]:
            if trap.triggered:
                continue

            trigger_range = trap.effect_params.get('trigger_range', 2.0)

            # Check all nearby entities
            for enemy in all_enemies:
                dist = distance(trap.position, enemy.position)
                if dist <= trigger_range:
                    self._trigger_trap(trap, enemy)
                    break
```

#### 5. Reflect/Thorns
**Why**: Defensive builds need this
**Effort**: 2-3 hours
**Files**: `effect_executor.py`, status effect tracking

```python
def _apply_reflect(self, source, target, params):
    reflect_percent = params.get('reflect_percent', 0.3)
    reflect_type = params.get('reflect_type', 'damage')

    # Add reflect buff to target
    target.active_buffs.append({
        'type': 'reflect',
        'percent': reflect_percent,
        'duration': params.get('duration', 10.0)
    })

# In damage application:
if hasattr(target, 'active_buffs'):
    for buff in target.active_buffs:
        if buff['type'] == 'reflect':
            reflected = damage * buff['percent']
            source.current_health -= reflected
            print(f"   🛡️ Reflected {reflected:.1f} damage!")
```

---

## 6. Code Snippets for Reference

### Helpful Existing Code

**Knockback Implementation** (effect_executor.py:221-264):
```python
def _apply_knockback(self, source, target, params):
    # Velocity-based smooth motion over time
    knockback_distance = params.get('knockback_distance', 2.0)
    knockback_duration = params.get('knockback_duration', 0.5)

    # Calculate velocity = distance / time
    velocity_magnitude = knockback_distance / knockback_duration
    velocity_x = dx * velocity_magnitude
    velocity_y = dy * velocity_magnitude

    # Apply to target
    target.knockback_velocity_x = velocity_x
    target.knockback_velocity_y = velocity_y
    target.knockback_duration_remaining = knockback_duration
```

**Turret Attack with Tags** (turret_system.py:83-128):
```python
def _attack_enemy(self, turret, enemy):
    if turret.tags and len(turret.tags) > 0:
        context = self.effect_executor.execute_effect(
            source=turret,
            primary_target=enemy,
            tags=turret.tags,
            params=turret.effect_params,
            available_entities=[enemy]
        )
    else:
        enemy.current_health -= turret.damage
```

**Tag-based Player Attack** (combat_manager.py:887-1036):
```python
def player_attack_enemy_with_tags(self, enemy, tags, params):
    # Collect bonuses
    base_damage = params["baseDamage"]
    base_damage += self.character.get_weapon_damage()
    base_damage *= (1.0 + character.stats.strength * 0.05)

    # Execute with tag system
    context = self.effect_executor.execute_effect(
        source=self.character,
        primary_target=enemy,
        tags=tags,
        params=params,
        available_entities=alive_enemies
    )
```

---

## 7. Summary

### What to Implement First (Ranked by Impact/Effort)

1. **Adornment Tag Collection** (1-2 hrs) - 3 accessories immediately functional
2. **Critical Mechanic** (1 hr) - Core combat enhancement
3. **Execute Mechanic** (30 min) - Finisher gameplay
4. **Trap Proximity System** (2-3 hrs) - Makes traps functional
5. **Reflect/Thorns** (2-3 hrs) - Defensive builds

### Architecture Notes

- **Tag System**: Robust foundation, extensible, well-documented
- **Turret System**: Complete implementation, good reference for traps
- **Effect Executor**: Central hub, add new mechanics here
- **Combat Flow**: Supports both legacy and tag-based attacks

### Testing Recommendations

- **Adornments**: Equip fire ring, verify burn procs on attacks
- **Execute**: Test against low-HP enemies, verify bonus damage
- **Traps**: Place spike trap, walk into it, verify damage
- **Reflect**: Give enemy reflect, attack it, verify reverse damage

---

**END OF ANALYSIS**
