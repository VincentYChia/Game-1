# Tag Definitions: Phase 2 - Complete Tag Reference

**Date:** 2025-12-15
**Purpose:** Detailed definitions for all functional tags in the tag-to-effects system
**Version:** 1.0

---

## How to Read This Document

Each tag definition includes:
- **Tag Name**: Primary identifier (lowercase, underscores for multi-word)
- **Aliases**: Alternative names that map to the same tag
- **Category**: Functional grouping
- **Parameters**: Data required for the tag to function
- **Context Behavior**: How the tag behaves in different contexts
- **Combination Rules**: How it interacts with other tags
- **Implementation Notes**: Technical considerations
- **Examples**: Real-world usage from JSONs

---

## Tag Categories

1. [Equipment Properties](#1-equipment-properties) - How items can be equipped
2. [Attack Geometry](#2-attack-geometry) - Target selection and hit patterns
3. [Damage Types](#3-damage-types) - Types of damage dealt
4. [Status Effects - Debuffs](#4-status-effects---debuffs) - Negative effects on targets
5. [Status Effects - Buffs](#5-status-effects---buffs) - Positive effects
6. [Special Mechanics](#6-special-mechanics) - Unique gameplay mechanics
7. [Trigger Conditions](#7-trigger-conditions) - When effects activate
8. [Targeting Context](#8-targeting-context) - Who/what is affected

---

## 1. Equipment Properties

### `1H` (One-Handed)

**Category:** Equipment Property
**Aliases:** `one_handed`, `onehand`
**Parameters:** None

**Context Behavior:**
- **On Equipment Item:** Can be equipped in mainHand OR offHand slot
- **On Other Entities:** No effect (silent ignore)

**Combination Rules:**
- **Mutually Exclusive With:** `2H`, `versatile`
- **Compatible With:** Dual-wielding mechanics (can equip two `1H` items)

**Implementation Notes:**
- Checked during equipment validation in `EquipmentManager`
- When equipped in mainHand, player can still use offHand slot
- When equipped in offHand, no special restrictions

**Examples:**
```json
"itemId": "copper_dagger",
"tags": ["weapon", "dagger", "1H", "fast"]
```

---

### `2H` (Two-Handed)

**Category:** Equipment Property
**Aliases:** `two_handed`, `twohand`
**Parameters:** None

**Context Behavior:**
- **On Equipment Item:** Requires both mainHand AND offHand slots, blocks offHand
- **On Other Entities:** No effect (silent ignore)

**Combination Rules:**
- **Mutually Exclusive With:** `1H`, `versatile`
- **Cannot Dual-Wield:** Prevents any offHand equipment

**Implementation Notes:**
- When equipping `2H` item, automatically unequip offHand item
- Equipment UI should show both slots occupied visually
- Stat bonuses apply once (not doubled for occupying two slots)

**Examples:**
```json
"itemId": "iron_warhammer",
"tags": ["weapon", "mace", "2H", "crushing"]
```

---

### `versatile`

**Category:** Equipment Property
**Aliases:** `vers`, `adaptable`
**Parameters:** None

**Context Behavior:**
- **On Equipment Item:** Can use offHand optionally (benefits from both modes)
- **On Other Entities:** No effect (silent ignore)

**Combination Rules:**
- **Mutually Exclusive With:** `1H`, `2H`
- **Bonus Mechanic:** May have different stats when used with vs without offHand
  - Example: Battleaxe - more damage two-handed, more speed with shield

**Implementation Notes:**
- Check if offHand is occupied when calculating stats
- Two stat profiles: `stats_one_handed` and `stats_two_handed`
- Default to one-handed stats if only one profile exists

**Examples:**
```json
"itemId": "steel_battleaxe",
"tags": ["weapon", "axe", "versatile", "cleaving"],
"statMultipliers": {
  "damage_one_handed": 1.0,
  "damage_two_handed": 1.3,
  "speed_one_handed": 1.1,
  "speed_two_handed": 0.9
}
```

---

## 2. Attack Geometry

Attack geometry tags determine **how targets are selected** and **what area is affected**.

### `single_target`

**Category:** Attack Geometry
**Aliases:** `single`, `targeted`
**Parameters:** None

**Context Behavior:**
- **On Attack/Skill:** Affects only the primary target
- **With Chain Tags:** Acts as starting point for chain
- **With AOE Tags:** Ignored (AOE takes precedence)

**Combination Rules:**
- **Default Behavior:** If no geometry tag present, assumes `single_target`
- **Overridden By:** Any multi-target geometry tag

**Implementation Notes:**
- Simplest targeting - just pass through primary target
- Used as base for most weapon attacks

**Examples:**
```json
"effect": "20 damage",
"tags": ["physical", "single_target"]
```

---

### `chain`

**Category:** Attack Geometry
**Aliases:** `arc`, `chaining`, `bounce`
**Parameters:**
- `chain_count` (int, default: 2) - Number of additional targets after primary
- `chain_range` (float, default: 5.0) - Max distance to next target
- `chain_falloff` (float, default: 0.0) - Damage reduction per jump (0.0 = no falloff, 0.5 = 50% reduction)

**Context Behavior:**
- **On Damage Effect:**
  - PRIMARY: Hit initial target
  - CHAIN: Find nearest valid target within `chain_range` of last hit
  - Repeat `chain_count` times
  - Cannot chain back to already-hit targets

- **On Healing Effect:**
  - PRIMARY: Heal initial target (usually caster)
  - CHAIN: Find nearest ally within `chain_range`
  - Prioritize lowest HP percentage allies

- **On Buff Effect:**
  - PRIMARY: Buff initial target
  - CHAIN: Spread buff to nearby allies

**Combination Rules:**
- **+ Damage Type Tags:** Chain carries the damage type
  - `chain` + `fire` = Fire damage chains, may apply `burn` to all targets
- **+ Status Tags:** Each chained target gets status effect
  - `chain` + `burn` = All chained targets get burning
- **+ AOE Tags:** CONFLICT - need resolution rule
  - Resolution: Chain takes precedence, AOE ignored (log warning)

**Implementation Notes:**
```python
def apply_chain_effect(source, initial_target, effect, chain_count, chain_range, chain_falloff):
    hit_targets = set([initial_target])
    current_target = initial_target
    current_magnitude = effect.magnitude

    apply_effect(initial_target, effect, current_magnitude)

    for i in range(chain_count):
        # Find nearest valid target
        next_target = find_nearest_target(
            position=current_target.position,
            max_range=chain_range,
            exclude=hit_targets,
            context=effect.context  # 'enemy', 'ally', etc.
        )

        if not next_target:
            break  # No more targets

        # Apply falloff
        current_magnitude *= (1.0 - chain_falloff)
        apply_effect(next_target, effect, current_magnitude)

        hit_targets.add(next_target)
        current_target = next_target
```

**Visual Indicators:**
- Lightning bolt VFX between chained targets
- Timing: Stagger hits by 0.1s per jump for visual clarity
- Color: Tint based on damage type (red for fire, blue for frost, etc.)

**Examples:**
```json
{
  "itemId": "lightning_cannon",
  "effect": "70 damage",
  "tags": ["turret", "lightning", "chain"],
  "effectParams": {
    "chain_count": 2,
    "chain_range": 6.0,
    "chain_falloff": 0.3
  }
}
```

---

### `cone`

**Category:** Attack Geometry
**Aliases:** `frontal`, `sweep_forward`
**Parameters:**
- `cone_angle` (float, default: 60.0) - Angle in degrees
- `cone_range` (float, default: 5.0) - Max distance from source
- `cone_origin` (str, default: "source") - "source" or "target"

**Context Behavior:**
- **On Damage/Debuff:**
  - Calculate cone from source facing direction
  - Hit all valid enemies in cone area

- **On Healing/Buff:**
  - Calculate cone from source facing direction
  - Affect all allies in cone area

**Combination Rules:**
- **+ Status Tags:** All targets in cone receive status
- **+ Damage Types:** Uniform damage type across cone
- **+ Chain:** CONFLICT - cone takes precedence

**Implementation Notes:**
```python
def get_cone_targets(source, cone_angle, cone_range, context):
    targets = []
    facing_vector = source.get_facing_direction()

    for entity in get_all_entities_in_range(source.position, cone_range):
        if not is_valid_target(entity, context):
            continue

        # Vector from source to entity
        to_entity = normalize(entity.position - source.position)

        # Angle between facing and to_entity
        angle = acos(dot(facing_vector, to_entity)) * 180 / PI

        if angle <= cone_angle / 2:
            targets.append(entity)

    return targets
```

**Visual Indicators:**
- Semi-transparent cone overlay when aiming (for player)
- Particle effects along cone edges during execution
- Ground decal showing affected area
- **IMPORTANT:** On-click visual indicator for AOE preview

**Examples:**
```json
{
  "itemId": "flamethrower_turret",
  "effect": "60 damage + lingering burn",
  "tags": ["turret", "fire", "cone", "burn"],
  "effectParams": {
    "cone_angle": 90.0,
    "cone_range": 8.0
  }
}
```

---

### `circle` / `aoe` / `radius`

**Category:** Attack Geometry
**Aliases:** `circular`, `radial`, `sphere`, `area`
**Parameters:**
- `radius` (float, default: 3.0) - Radius in game units
- `origin` (str, default: "target") - "source", "target", or "position"
- `max_targets` (int, default: 0) - 0 = unlimited

**Context Behavior:**
- **Origin "target":** Circle centered on hit target (fireball explosion)
- **Origin "source":** Circle centered on caster (nova, shockwave)
- **Origin "position":** Circle at specific coordinates (placed bomb)

**Combination Rules:**
- **+ Damage Types:** All targets take typed damage
- **+ Status Effects:** All targets receive status
- **+ Chain:** CONFLICT - circle takes precedence

**Implementation Notes:**
```python
def get_circle_targets(origin_point, radius, context, max_targets=0):
    targets = []

    for entity in get_all_entities():
        distance = calculate_distance(origin_point, entity.position)

        if distance <= radius and is_valid_target(entity, context):
            targets.append((entity, distance))

    # Sort by distance, closest first
    targets.sort(key=lambda x: x[1])

    if max_targets > 0:
        targets = targets[:max_targets]

    return [t[0] for t in targets]
```

**Visual Indicators:**
- Circular ground decal at detonation point
- Expanding ring VFX
- **IMPORTANT:** On-click preview showing radius before activation
- Height indicator if vertical component exists

**Examples:**
```json
{
  "itemId": "simple_bomb",
  "effect": "40 damage in 3 unit radius",
  "tags": ["device", "bomb", "explosive", "circle"],
  "effectParams": {
    "radius": 3.0,
    "origin": "position"
  }
}
```

---

### `beam` / `line`

**Category:** Attack Geometry
**Aliases:** `ray`, `laser`
**Parameters:**
- `beam_range` (float, default: 10.0) - Max distance
- `beam_width` (float, default: 0.5) - Width of beam
- `pierce_count` (int, default: 0) - Targets to penetrate (0 = first hit stops)

**Context Behavior:**
- Cast ray from source in facing direction
- Hit all entities intersecting beam
- If `pierce_count` > 0, continue through targets
- If `pierce_count` = 0, stop at first target (hitscan)

**Combination Rules:**
- **+ Pierce Tag:** Beam automatically pierces all targets in line
- **+ Status Effects:** Apply to all targets hit

**Implementation Notes:**
- Use raycast for hitscan beams
- Use box-cast (width parameter) for thick beams
- Sort hits by distance along ray
- Apply effects in order

**Visual Indicators:**
- Continuous beam visual from source to endpoint
- Hit markers on each target
- Bright flash at beam origin

**Examples:**
```json
{
  "itemId": "laser_turret",
  "effect": "80 damage",
  "tags": ["turret", "energy", "beam", "precision"],
  "effectParams": {
    "beam_range": 12.0,
    "beam_width": 0.3,
    "pierce_count": 0
  }
}
```

---

### `pierce`

**Category:** Attack Geometry Modifier
**Aliases:** `penetrating`, `punch_through`
**Parameters:**
- `pierce_count` (int, default: -1) - Targets to penetrate (-1 = infinite)
- `pierce_falloff` (float, default: 0.1) - Damage reduction per target

**Context Behavior:**
- **On Projectile:** Continues through targets after hit
- **On Beam:** Automatically penetrates (redundant but acceptable)
- **On Melee:** Hits multiple targets in line

**Combination Rules:**
- **+ Projectile:** Projectile continues, hitting multiple targets
- **+ Single Target:** Converts to line attack through target
- **+ AOE:** CONFLICT - pierce ignored on true AOE

**Implementation Notes:**
- Track penetration count per projectile instance
- Reduce damage after each penetration
- Stop when pierce_count exhausted or no more targets

---

### `projectile`

**Category:** Attack Geometry
**Aliases:** `missile`, `arrow`
**Parameters:**
- `projectile_speed` (float, default: 10.0) - Units per second
- `projectile_gravity` (float, default: 0.0) - Gravity effect
- `projectile_homing` (float, default: 0.0) - Homing strength (0.0-1.0)

**Context Behavior:**
- Spawn projectile entity at source
- Move toward target at specified speed
- Apply effect on collision with target or terrain

**Combination Rules:**
- **+ Pierce:** Projectile continues through targets
- **+ AOE:** Explosion on impact
- **+ Chain:** Projectile chains to new target after first hit

**Implementation Notes:**
- Projectile is a physical entity in game world
- Can be dodged, blocked, or intercepted
- Collision detection each frame

---

### `splash`

**Category:** Attack Geometry Modifier
**Aliases:** `impact_aoe`
**Parameters:**
- `splash_radius` (float, default: 2.0) - AOE radius on impact
- `splash_falloff` (str, default: "linear") - "none", "linear", "quadratic"

**Context Behavior:**
- Primary target takes full effect
- Nearby targets take scaled effect based on distance and falloff

**Combination Rules:**
- **+ Projectile:** AOE triggers on projectile impact
- **+ Single Target:** Adds AOE component to single-target attack

---

## 3. Damage Types

Damage types determine **what kind of damage** is dealt and may interact with resistances/weaknesses.

### `physical`

**Category:** Damage Type
**Aliases:** None
**Parameters:** None

**Context Behavior:**
- Base physical damage
- Affected by armor and physical defense
- No special interactions

**Combination Rules:**
- **Base Type:** Can combine with subtype (`slashing`, `crushing`, `piercing`)
- **+ Elemental:** Hybrid damage (50% physical, 50% elemental)

---

### `slashing`

**Category:** Damage Type (Physical Subtype)
**Aliases:** `slash`, `cutting`
**Parameters:** None

**Context Behavior:**
- Physical damage with cutting component
- May have bonus against unarmored/light armor
- Weapons: Swords, axes, scythes

**Combination Rules:**
- **Sub-type of:** `physical`
- **Resist/Weakness:** Check target's resistance to slashing specifically

**Examples:**
```json
"tags": ["weapon", "sword", "slashing", "versatile"]
```

---

### `piercing`

**Category:** Damage Type (Physical Subtype)
**Aliases:** `pierce_damage`, `puncture`
**Parameters:** None

**Context Behavior:**
- Physical damage that penetrates armor
- Ignores portion of armor (e.g., 25% armor penetration)
- Weapons: Spears, arrows, daggers

**Combination Rules:**
- **Sub-type of:** `physical`
- **Special:** May ignore partial defense based on item stats

---

### `crushing` / `blunt`

**Category:** Damage Type (Physical Subtype)
**Aliases:** `impact`, `bludgeoning`
**Parameters:** None

**Context Behavior:**
- Physical damage from impact
- May have bonus against armored targets (armor breaking)
- Weapons: Maces, hammers, clubs

**Combination Rules:**
- **Sub-type of:** `physical`
- **Special:** May reduce target armor temporarily

---

### `fire`

**Category:** Damage Type (Elemental)
**Aliases:** `flame`, `thermal`
**Parameters:** None

**Context Behavior:**
- Elemental fire damage
- Affected by fire resistance
- May apply `burn` status if specified

**Combination Rules:**
- **+ Chain:** Fire damage chains, visually shows fire arcing
- **+ AOE:** Fire explosion, may apply burn in radius
- **+ Burn (status):** Applies burning DoT
- **Countered By:** `frost` resistance

**Implementation Notes:**
- Check target fire resistance before applying damage
- Fire damage has inherent chance to apply minor burn (10%) even without burn tag
- VFX: Red/orange particles

**Examples:**
```json
"tags": ["turret", "fire", "projectile", "burn"]
```

---

### `frost` / `ice`

**Category:** Damage Type (Elemental)
**Aliases:** `cold`, `frozen`
**Parameters:** None

**Context Behavior:**
- Elemental cold damage
- Affected by frost resistance
- May apply `chill` or `freeze` status

**Combination Rules:**
- **+ Chill:** Slows movement speed
- **+ Freeze:** Immobilizes target
- **Countered By:** `fire` resistance

**Implementation Notes:**
- Frost damage has inherent 15% chance to apply minor chill
- VFX: Blue/white particles, ice crystals

---

### `lightning` / `electric`

**Category:** Damage Type (Elemental)
**Aliases:** `shock`, `thunder`
**Parameters:** None

**Context Behavior:**
- Elemental lightning damage
- Affected by lightning resistance
- Natural synergy with `chain` geometry

**Combination Rules:**
- **+ Chain:** SYNERGY - increased chain range (+20%)
- **+ Shock (status):** Periodic damage and interrupt attacks

**Implementation Notes:**
- Lightning naturally chains (if chain tag present, bonus to chain_range)
- VFX: Blue/white electrical arcs

---

### `poison`

**Category:** Damage Type (Elemental/Status)
**Aliases:** `toxic`, `venom`
**Parameters:** None

**Context Behavior:**
- Poison damage (may be instant or over time)
- Affected by poison resistance
- Typically combined with `poison_status` for DoT

**Combination Rules:**
- **+ Poison Status:** Applies lingering poison effect
- **Stacks:** Poison stacks can accumulate

---

### `arcane` / `magic`

**Category:** Damage Type (Elemental)
**Aliases:** `magical`, `mystic`
**Parameters:** None

**Context Behavior:**
- Pure magical damage
- Bypasses physical armor
- Affected by magic resistance

---

### `holy` / `light`

**Category:** Damage Type (Elemental)
**Aliases:** `radiant`, `divine`
**Parameters:** None

**Context Behavior:**
- Holy damage
- Bonus against undead and demons
- Healing effect on allies if context allows

**Context-Aware:**
- **On Enemy (Undead):** 150% damage
- **On Ally:** May provide minor heal instead of damage

---

### `shadow` / `dark`

**Category:** Damage Type (Elemental)
**Aliases:** `void`, `necrotic`
**Parameters:** None

**Context Behavior:**
- Shadow damage
- May reduce healing received
- Bonus against holy/light entities

---

### `chaos`

**Category:** Damage Type (Elemental)
**Aliases:** `void`, `entropy`
**Parameters:** None

**Context Behavior:**
- Chaotic damage - random type each hit
- Hard to resist (ignores 50% resistance)
- Unpredictable effects

---

## 4. Status Effects - Debuffs

Status effects are **temporary conditions** applied to targets.

### `burn` / `burning`

**Category:** Status Effect (Debuff, DoT)
**Aliases:** `ignite`, `on_fire`
**Parameters:**
- `duration` (float, default: 5.0) - Seconds
- `tick_rate` (float, default: 1.0) - Damage per second
- `damage_per_tick` (float, default: 5.0) - Damage each tick
- `stacks` (bool, default: true) - Can multiple burns stack?

**Context Behavior:**
- **On Enemy:** Applies fire DoT, visual fire particles
- **On Ally:** ERROR - friendly fire? (log warning, optionally apply if FF enabled)
- **On Object:** May set object on fire (destructible terrain)

**Combination Rules:**
- **+ Fire Damage:** Automatically applies burn
- **+ Chain:** Burn applies to all chained targets
- **+ AOE:** All targets in AOE get burn
- **Stacking:** Each application adds new instance (multiple ticks)

**Implementation Notes:**
```python
class BurnEffect:
    def __init__(self, duration, tick_rate, damage_per_tick):
        self.duration = duration
        self.tick_rate = tick_rate
        self.damage_per_tick = damage_per_tick
        self.elapsed = 0.0
        self.next_tick = tick_rate

    def update(self, dt, target):
        self.elapsed += dt
        self.next_tick -= dt

        if self.next_tick <= 0:
            target.take_damage(self.damage_per_tick, "fire")
            self.next_tick = self.tick_rate

        return self.elapsed < self.duration  # Return false to remove
```

**Visual Indicators:**
- Fire particles on affected entity
- HP bar shows DoT tick damage
- Status icon above target

**Examples:**
```json
{
  "tags": ["fire", "burn", "cone"],
  "effectParams": {
    "duration": 8.0,
    "tick_rate": 1.0,
    "damage_per_tick": 10.0
  }
}
```

---

### `freeze` / `frozen`

**Category:** Status Effect (Debuff, CC)
**Aliases:** `frozen_solid`, `ice_block`
**Parameters:**
- `duration` (float, default: 3.0) - Seconds
- `damage_to_break` (float, default: 0.0) - Damage needed to shatter (0 = unbreakable)

**Context Behavior:**
- **On Enemy:** Complete immobilization, cannot move or attack
- **On Ally:** Same effect (friendly fire scenario)
- **On Object:** Freezes object in place

**Combination Rules:**
- **+ Frost Damage:** Chance to freeze
- **+ Shatter:** If frozen target takes physical damage > threshold, instant kill
- **Mutually Exclusive:** Cannot freeze and burn simultaneously (freeze overrides burn)

**Implementation Notes:**
- Sets target velocity to zero
- Disables all actions
- Accumulating damage breaks freeze early if threshold set
- VFX: Ice block around entity

**Visual Indicators:**
- Ice encasing target
- Blue tint on sprite/model
- Shatter animation if broken

---

### `chill` / `slow`

**Category:** Status Effect (Debuff)
**Aliases:** `slowed`, `slow_effect`
**Parameters:**
- `duration` (float, default: 4.0) - Seconds
- `slow_amount` (float, default: 0.5) - Movement speed multiplier (0.5 = 50% slower)
- `affect_attack_speed` (bool, default: false) - Also slow attack speed?

**Context Behavior:**
- **On Enemy:** Reduces movement and optionally attack speed
- **On Ally:** Same (debuff)

**Combination Rules:**
- **+ Frost Damage:** Natural combination
- **Stacks:** Multiple slows multiply (0.5 * 0.5 = 0.25 speed)
- **Caps:** Minimum speed 10% of base (cannot reduce to 0)

**Implementation Notes:**
```python
target.movement_speed *= slow_amount
if affect_attack_speed:
    target.attack_speed *= slow_amount
```

---

### `stun` / `stunned`

**Category:** Status Effect (Debuff, CC)
**Aliases:** `dazed`, `incapacitated`
**Parameters:**
- `duration` (float, default: 2.0) - Seconds

**Context Behavior:**
- **On Target:** Prevents all actions, can still take damage

**Combination Rules:**
- **Stun Resistance:** Consecutive stuns have diminishing duration
- **Break on Damage:** Optionally, massive damage breaks stun

**Implementation Notes:**
- Disable input processing
- Clear action queue
- VFX: Stars/birds circling head

---

### `root` / `rooted`

**Category:** Status Effect (Debuff, CC)
**Aliases:** `immobilize`, `snare`
**Parameters:**
- `duration` (float, default: 3.0) - Seconds

**Context Behavior:**
- **On Target:** Cannot move, CAN still attack/cast

**Combination Rules:**
- **Different from Stun:** Can act, just can't move
- **Different from Freeze:** No immobilization, just movement lock

---

### `bleed` / `bleeding`

**Category:** Status Effect (Debuff, DoT)
**Aliases:** `hemorrhage`
**Parameters:**
- `duration` (float, default: 6.0) - Seconds
- `tick_rate` (float, default: 1.0) - Seconds per tick
- `damage_per_tick` (float, default: 3.0) - Damage each tick
- `movement_increases_damage` (bool, default: true) - Moving increases bleed rate

**Context Behavior:**
- **On Organic Targets:** Physical DoT
- **On Constructs/Mechanical:** No effect (immune)

**Combination Rules:**
- **+ Slashing Damage:** Natural application
- **Stacks:** Each bleed instance separate

**Implementation Notes:**
- Check target type (organic vs construct)
- If movement detected, increase tick rate or damage
- VFX: Blood particles

---

### `poison_status`

**Category:** Status Effect (Debuff, DoT)
**Aliases:** `poisoned`, `toxic_status`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `tick_rate` (float, default: 2.0) - Seconds per tick
- `damage_per_tick` (float, default: 4.0) - Damage each tick

**Context Behavior:**
- **On Organic:** Poison DoT
- **On Construct/Undead:** Immune or reduced effect

**Combination Rules:**
- **+ Poison Damage:** Applies status
- **Cured By:** Antidote items/skills

---

### `weaken` / `weakened`

**Category:** Status Effect (Debuff)
**Aliases:** `enfeeble`, `vulnerability`
**Parameters:**
- `duration` (float, default: 5.0) - Seconds
- `stat_reduction` (float, default: 0.25) - 25% stat reduction
- `affected_stats` (list, default: ["damage", "defense"]) - Which stats to reduce

**Context Behavior:**
- **On Target:** Reduces specified stats by percentage

---

## 5. Status Effects - Buffs

### `haste` / `quicken`

**Category:** Status Effect (Buff)
**Aliases:** `speed_buff`, `swiftness`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `speed_increase` (float, default: 0.5) - Movement speed multiplier (0.5 = +50%)
- `attack_speed_increase` (float, default: 0.0) - Attack speed increase

**Context Behavior:**
- **On Ally/Self:** Increases movement and attack speed

**Combination Rules:**
- **Stacks Additively:** Multiple hastes add together
- **Caps:** Maximum 200% total speed

---

### `empower`

**Category:** Status Effect (Buff)
**Aliases:** `strengthen`, `damage_buff`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `damage_increase` (float, default: 0.5) - Damage multiplier (+50%)

**Context Behavior:**
- **On Ally/Self:** Increases damage output

**Combination Rules:**
- **Stacks Multiplicatively:** 1.5 * 1.3 = 1.95x damage

---

### `fortify`

**Category:** Status Effect (Buff)
**Aliases:** `armor_buff`, `defense_buff`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `defense_increase` (float or int) - Flat (+20) or multiplier (0.5 = +50%)
- `damage_reduction` (float, default: 0.0) - Direct damage reduction (0.2 = 20% less damage taken)

**Context Behavior:**
- **On Ally/Self:** Increases defense/reduces incoming damage

---

### `regeneration` / `regen`

**Category:** Status Effect (Buff, HoT)
**Aliases:** `heal_over_time`, `hot`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `tick_rate` (float, default: 1.0) - Seconds per tick
- `heal_per_tick` (float, default: 5.0) - HP restored per tick

**Context Behavior:**
- **On Ally/Self:** Restores HP over time
- **On Enemy:** Rare, but could apply (e.g., healing enemy to control it)

**Implementation Notes:**
- Similar to burn, but restores HP instead of damage
- VFX: Green particles, glowing outline

---

### `shield` / `barrier`

**Category:** Status Effect (Buff)
**Aliases:** `damage_shield`, `absorb`
**Parameters:**
- `duration` (float, default: 15.0) - Seconds or until depleted
- `shield_amount` (float, default: 50.0) - HP absorbed
- `shield_type` (str, default: "all") - "physical", "elemental", "all"

**Context Behavior:**
- **On Ally/Self:** Absorbs damage before HP is affected
- **On Enemy:** Protects enemy (if buff applied by ally)

**Implementation Notes:**
```python
def take_damage(self, amount, damage_type):
    if self.has_shield():
        if self.shield_type == "all" or self.shield_type == damage_type:
            absorbed = min(amount, self.shield_amount)
            self.shield_amount -= absorbed
            amount -= absorbed

            if self.shield_amount <= 0:
                self.remove_shield()

    self.current_hp -= amount
```

---

### `invisible` / `stealth`

**Category:** Status Effect (Buff)
**Aliases:** `hidden`, `cloaked`
**Parameters:**
- `duration` (float, default: 10.0) - Seconds
- `breaks_on_action` (bool, default: true) - Breaking stealth on attack

**Context Behavior:**
- **On Ally/Self:** Becomes undetectable by enemies
- Enemies do not aggro or target invisible entities

**Implementation Notes:**
- Set entity visibility flag
- Remove from enemy target lists
- Break on damage dealt if configured

---

## 6. Special Mechanics

### `lifesteal` / `vampiric`

**Category:** Special Mechanic
**Aliases:** `drain`, `life_drain`
**Parameters:**
- `lifesteal_percent` (float, default: 0.15) - 15% of damage dealt as healing

**Context Behavior:**
- **On Damage Dealt:** Heal source by percentage of damage

**Combination Rules:**
- **+ AOE:** Heal from all targets hit
- **+ DoT:** Heal from each tick

**Implementation Notes:**
```python
def on_damage_dealt(self, target, damage):
    if self.has_lifesteal():
        heal_amount = damage * self.lifesteal_percent
        self.heal(heal_amount)
```

---

### `reflect` / `thorns`

**Category:** Special Mechanic
**Aliases:** `reflect_damage`, `retaliation`
**Parameters:**
- `reflect_percent` (float, default: 0.3) - 30% of damage reflected
- `reflect_type` (str, default: "damage") - "damage" or "projectile"

**Context Behavior:**
- **On Damage Taken (damage):** Attacker takes reflected damage
- **On Projectile Hit (projectile):** Projectile bounces back to source

**Combination Rules:**
- **+ Shield:** Reflect only applies to damage absorbed by shield
- **Reflect Chains:** Prevent infinite reflect loops (max 1 reflection)

---

### `knockback`

**Category:** Special Mechanic
**Aliases:** `push`, `displace`
**Parameters:**
- `knockback_distance` (float, default: 2.0) - Units pushed away
- `knockback_duration` (float, default: 0.5) - Time of displacement

**Context Behavior:**
- **On Hit:** Target pushed away from source

**Combination Rules:**
- **+ AOE:** All targets knocked outward from center
- **+ Wall Collision:** Additional stun if knocked into wall

---

### `pull`

**Category:** Special Mechanic
**Aliases:** `draw_in`, `attract`
**Parameters:**
- `pull_distance` (float, default: 2.0) - Units pulled toward source
- `pull_duration` (float, default: 0.5) - Time of pull

**Context Behavior:**
- **On Hit:** Target pulled toward source

---

### `teleport`

**Category:** Special Mechanic
**Aliases:** `blink`, `warp`
**Parameters:**
- `teleport_range` (float, default: 10.0) - Max distance
- `teleport_type` (str, default: "targeted") - "targeted", "random", "behind_target"

**Context Behavior:**
- **On Self:** Instant movement to new position
- **On Target:** Teleport target to position

**Implementation Notes:**
- Validate destination (not inside wall)
- VFX: Disappear/reappear effects

---

### `summon`

**Category:** Special Mechanic
**Aliases:** `spawn`, `create`
**Parameters:**
- `summon_id` (str, required) - Entity to summon
- `summon_count` (int, default: 1) - Number of summons
- `summon_duration` (float, default: 30.0) - Lifespan (0 = permanent)

**Context Behavior:**
- **On Activation:** Spawns entities at position

**Examples:**
```json
{
  "tags": ["summon"],
  "effectParams": {
    "summon_id": "crystal_shard_minion",
    "summon_count": 3,
    "summon_duration": 20.0
  }
}
```

---

### `dash` / `charge`

**Category:** Special Mechanic
**Aliases:** `rush`, `sprint_forward`
**Parameters:**
- `dash_distance` (float, default: 5.0) - Distance traveled
- `dash_speed` (float, default: 20.0) - Speed of dash
- `damage_on_contact` (bool, default: false) - Deal damage during dash

**Context Behavior:**
- **On Activation:** Rapid movement in direction

---

### `phase` / `phase_shift`

**Category:** Special Mechanic
**Aliases:** `intangible`, `ethereal`
**Parameters:**
- `phase_duration` (float, default: 2.0) - Seconds intangible
- `can_pass_walls` (bool, default: false) - Clip through terrain

**Context Behavior:**
- **On Self:** Become intangible, attacks pass through
- Cannot be hit or targeted

**Implementation Notes:**
- Disable collision
- Remove from target lists
- VFX: Ghostly/transparent appearance

---

### `block` / `parry`

**Category:** Special Mechanic
**Aliases:** `deflect`, `counter`
**Parameters:**
- `block_chance` (float, default: 0.5) - 50% block chance
- `counter_damage` (float, default: 0.0) - Damage on successful block

**Context Behavior:**
- **On Being Hit:** Chance to negate attack
- If `counter_damage` > 0, deal damage to attacker

---

### `execute`

**Category:** Special Mechanic
**Aliases:** `finisher`, `threshold_bonus`
**Parameters:**
- `threshold_hp` (float, default: 0.2) - HP threshold (20%)
- `bonus_damage` (float, default: 2.0) - Damage multiplier below threshold

**Context Behavior:**
- **On Damage Dealt:** If target below HP threshold, multiply damage

**Examples:**
```json
{
  "tags": ["execute", "single_target"],
  "effectParams": {
    "threshold_hp": 0.25,
    "bonus_damage": 3.0
  }
}
```

---

### `critical` / `crit`

**Category:** Special Mechanic
**Aliases:** `crit_chance`, `critical_hit`
**Parameters:**
- `crit_chance` (float, default: 0.15) - 15% crit chance
- `crit_multiplier` (float, default: 2.0) - 2x damage on crit

**Context Behavior:**
- **On Damage Roll:** Chance to deal multiplied damage

**Implementation Notes:**
```python
damage = base_damage
if random() < crit_chance:
    damage *= crit_multiplier
    show_crit_visual()
```

---

## 7. Trigger Conditions

Trigger conditions determine **when** an effect activates.

### `on_hit`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect triggers when attack successfully hits target

---

### `on_kill`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect triggers when this attack kills target

---

### `on_damage`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect triggers when source takes damage

---

### `on_crit`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect triggers when landing critical hit

---

### `passive`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect is always active (no trigger needed)

---

### `active`

**Category:** Trigger
**Parameters:**
- `cooldown` (float, default: 10.0) - Seconds between activations

**Context Behavior:**
- Effect requires manual activation
- Subject to cooldown

---

### `toggle`

**Category:** Trigger
**Parameters:** None

**Context Behavior:**
- Effect can be turned on/off
- No cooldown between toggles

---

## 8. Targeting Context

Context tags determine **who or what** can be affected.

### `self`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect only affects the caster

---

### `ally` / `friendly`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets allies (same team as caster)
- **Healing Effects:** Default to ally targeting
- **Damage Effects:** Friendly fire (usually unintended, log warning)

---

### `enemy` / `hostile`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets enemies (opposite team)
- **Damage Effects:** Default to enemy targeting
- **Healing Effects:** Unusual (healing enemy, log warning unless intended)

---

### `all`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets all entities regardless of team

---

### `player`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect only targets player entities

---

### `turret` / `device`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets placed devices/turrets
- **Healing Beacon:** `chain` + `healing` + `turret` = heals nearby turrets

---

### `construct`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets construct-type enemies
- May have unique interactions (e.g., immune to bleed)

---

### `undead`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets undead enemies
- May have bonuses (holy damage)

---

### `mechanical`

**Category:** Targeting Context
**Parameters:** None

**Context Behavior:**
- Effect targets mechanical enemies
- Immune to organic status (bleed, poison)

---

## 9. Tag Combination Rules & Examples

### Rule 1: Context Detection (Implicit)

**If no context tag specified:**
- **Damage/Debuff Effects:** Default to `enemy`
- **Healing/Buff Effects:** Default to `ally` or `self`
- **Neutral Effects:** Default to `all`

**Example:**
```json
{
  "tags": ["fire", "chain", "burn"],
  "effectParams": {...}
}
// Implicitly: context = "enemy" (damage effect)
```

---

### Rule 2: Geometry Conflicts

**If multiple conflicting geometry tags:**
- **Priority Order:** `chain` > `cone` > `circle` > `beam` > `single_target`
- **Log Warning:** "Multiple geometry tags detected, using {priority_tag}"

**Example:**
```json
{
  "tags": ["chain", "cone"]  // Conflict!
  // Resolution: chain takes precedence, cone ignored
}
```

---

### Rule 3: Damage Type Stacking

**Multiple damage types combine:**
- **Hybrid Damage:** Split evenly between types
- **Example:** `fire` + `lightning` = 50% fire, 50% lightning

**Implementation:**
```python
if len(damage_types) > 1:
    for dtype in damage_types:
        partial_damage = total_damage / len(damage_types)
        apply_damage(target, partial_damage, dtype)
```

---

### Rule 4: Status Effect + Geometry = All Targets Get Status

**Combination:**
```json
{
  "tags": ["fire", "burn", "cone"]
}
```

**Behavior:**
- All targets in cone take fire damage
- All targets in cone get burn status

---

### Rule 5: Chain + Healing = Context Switch

**Combination:**
```json
{
  "tags": ["healing", "chain"]
}
```

**Context-Aware Behavior:**
- Primary target: Caster (heals self)
- Chain targets: Nearby allies (lowest HP priority)
- Does NOT chain to enemies

---

### Rule 6: Fire + Chain = Chain Spreading Burn

**Combination:**
```json
{
  "tags": ["fire", "chain", "burn"]
}
```

**Behavior:**
- Initial target: Fire damage + burn
- Chained targets: Fire damage + burn (all get burning)
- VFX: Fire visually arcs between targets

---

### Rule 7: Elemental + Opposite = Neutralization

**Combinations:**
- `fire` + `freeze` effect on same target = Cancel each other
- Active burn + apply freeze = Freeze overrides, removes burn
- Active freeze + apply burn = Thaw target, burn applies

---

### Rule 8: Pierce + Projectile = Penetrating Projectile

**Combination:**
```json
{
  "tags": ["projectile", "pierce"]
}
```

**Behavior:**
- Projectile continues through first target
- Hits all targets in line
- Each hit applies full effect

---

### Rule 9: AOE + Status = Area Status Application

**Combination:**
```json
{
  "tags": ["circle", "slow", "frost"]
}
```

**Behavior:**
- All enemies in radius take frost damage
- All enemies in radius get slow status

---

### Rule 10: Buff + Enemy Target = Warning

**Unusual Combination:**
```json
{
  "tags": ["empower", "enemy"]
}
```

**Behavior:**
- Technically valid (empowering enemy)
- **Log Warning:** "Buff effect applied to enemy target - is this intentional?"
- Useful for mind control or confusion mechanics

---

## 10. Implementation Architecture Overview

### 10.1 Effect Registry

**Central registry mapping tags to effect executors:**

```python
class EffectRegistry:
    def __init__(self):
        self.effects = {}

    def register(self, tag, effect_class):
        self.effects[tag] = effect_class

    def get_effect(self, tag):
        return self.effects.get(tag)

# Global registry
effect_registry = EffectRegistry()

# Register effects
effect_registry.register("burn", BurnEffect)
effect_registry.register("chain", ChainGeometry)
effect_registry.register("cone", ConeGeometry)
# ... etc
```

---

### 10.2 Tag Parser

**Parse tags from JSON and build effect pipeline:**

```python
class TagParser:
    def parse_tags(self, tags, params):
        """Parse tags and return effect configuration"""

        # Categorize tags
        geometry_tags = []
        damage_tags = []
        status_tags = []
        context_tags = []
        trigger_tags = []

        for tag in tags:
            category = get_tag_category(tag)
            if category == "geometry":
                geometry_tags.append(tag)
            elif category == "damage":
                damage_tags.append(tag)
            # ... etc

        # Resolve conflicts
        geometry = resolve_geometry(geometry_tags)
        context = resolve_context(context_tags, geometry, damage_tags)

        return EffectConfiguration(
            geometry=geometry,
            damage_types=damage_tags,
            statuses=status_tags,
            context=context,
            params=params
        )
```

---

### 10.3 Effect Application Pipeline

**Execute effects in order:**

```python
def apply_effect(source, target, effect_config):
    """Apply effect with full tag system"""

    # 1. Validate context
    if not is_valid_target(target, effect_config.context):
        log_debug(f"Target {target} invalid for context {effect_config.context}")
        return

    # 2. Get targets based on geometry
    targets = get_targets_by_geometry(
        source,
        target,
        effect_config.geometry,
        effect_config.context
    )

    # 3. Apply damage types
    for tgt in targets:
        for damage_type in effect_config.damage_types:
            damage = calculate_damage(effect_config.base_damage, damage_type)
            apply_damage(tgt, damage, damage_type)

    # 4. Apply status effects
    for tgt in targets:
        for status in effect_config.statuses:
            apply_status(tgt, status, effect_config.params)

    # 5. Special mechanics
    if "lifesteal" in effect_config.tags:
        heal_source(source, total_damage * lifesteal_percent)
```

---

### 10.4 Debug Logging Framework

**Comprehensive logging for tag system:**

```python
class TagDebugger:
    def __init__(self, log_level="INFO"):
        self.log_level = log_level

    def log_effect_application(self, source, target, effect_config):
        if self.log_level == "DEBUG":
            print(f"[TAG_SYSTEM] {source.name} -> {target.name}")
            print(f"  Geometry: {effect_config.geometry}")
            print(f"  Damage: {effect_config.damage_types}")
            print(f"  Status: {effect_config.statuses}")
            print(f"  Context: {effect_config.context}")

    def log_tag_conflict(self, tags, resolution):
        print(f"[TAG_WARNING] Conflicting tags: {tags}")
        print(f"  Resolution: Using {resolution}")

    def log_context_mismatch(self, tag, target, context):
        print(f"[TAG_INFO] Tag '{tag}' on {target.type} - context '{context}' - no effect (expected)")

    def log_silent_failure(self, reason):
        if self.log_level in ["DEBUG", "INFO"]:
            print(f"[TAG_SILENT] {reason}")
```

---

## 11. Migration Strategy

### Step 1: Validate Existing Tags
- Run tag_collector.py to identify all current tags
- Flag any tags that need renaming/consolidation
- Create mapping for old → new tag names

### Step 2: Add Missing Tags to JSONs
- Update items with proper geometry tags (`chain`, `cone`, etc.)
- Add status effect tags (`burn`, `slow`, `bleed`)
- Convert hostile abilities to tags

### Step 3: Implement Core Systems
- Effect registry
- Tag parser
- Geometry calculators (cone, chain, circle)
- Status effect managers

### Step 4: Replace Hardcoded Effects
- Skills: Replace hardcoded skill effects with tags
- Turrets: Convert turret logic to tag-based
- Hostiles: Migrate special abilities to tags

### Step 5: Testing & Validation
- Unit tests for each tag
- Integration tests for combinations
- Performance profiling

---

**END OF PHASE 2**

**Next Document:** `TAG-IMPLEMENTATION-PHASE3.md` - Actual code implementation
