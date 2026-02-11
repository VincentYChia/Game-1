# Phase 3: Entity Layer -- Character, Components, Status Effects, Enemies, and Tools

**Phase**: 3 of N
**Status**: Not Started
**Dependencies**: Phase 1 (Data Models & Enums), Phase 2 (Database Singletons loaded)
**Estimated C# Files**: 22+
**Estimated C# Lines**: ~9,000-11,000
**Source Python Lines**: ~7,638 across 17 files

---

## 1. Overview

### 1.1 Goal

Port all entity-layer classes from Python to C#: the `Character` class with its 11 component subsystems, the 17-type status effect hierarchy with factory and manager, the full `Enemy` AI state machine with `EnemyDatabase` singleton, and supporting utility entities (`Tool`, `DamageNumber`). After this phase, a Character can be instantiated with all components wired, status effects can be applied and tick, enemies can spawn and run their AI, and save/load can roundtrip all entity state.

### 1.2 Why Phase 3

Phase 3 sits between the static data layer (Phases 1-2) and the gameplay systems (Phase 4: Combat, Phase 5: Crafting). Every gameplay system operates on entities:

- **Combat** (Phase 4) requires `Character`, `Enemy`, `StatusEffectManager`, `EquipmentManager`, `WeaponTagCalculator`
- **Crafting** (Phase 5) requires `Character.inventory`, `Character.buffs`, `Character.stat_tracker`
- **World Systems** (Phase 6) require `Character.position`, `Character.move()`
- **Save/Load** (Phase 8) requires serialization methods on `Character` and all components
- **Rendering** (Phase 7) requires `DamageNumber`, `Enemy.position`, `Character.facing`

No gameplay phase can begin until entities compile, instantiate, and pass behavioral validation.

### 1.3 Dependencies

**Incoming (must be complete)**:
- **Phase 1**: `Position`, `EquipmentItem`, `MaterialDefinition`, `ClassDefinition`, `TitleDefinition`, `SkillDefinition`, `PlayerSkill`, `Recipe`, `CraftingStation`, `AIState` enum
- **Phase 2**: `MaterialDatabase`, `EquipmentDatabase`, `SkillDatabase`, `ClassDatabase`, `TitleDatabase`, `RecipeDatabase` (all singletons must load and query)

**Outgoing (phases that depend on Phase 3)**:
- Phase 4 (Combat): `Enemy`, `Character`, `StatusEffectManager`, `WeaponTagCalculator`
- Phase 5 (Crafting): `Character.inventory`, `Character.buffs`, `Character.activities`
- Phase 6 (World): `Character.move()`, `Character.position`
- Phase 7 (Rendering): `DamageNumber`, entity positions, visual state
- Phase 8 (Save/Load): `Character.save_to_file()`, `Character.restore_from_save()`

### 1.4 Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| C# entity files | 3 | Character.cs, Tool.cs, DamageNumber.cs |
| C# component files | 11 | One per Python component |
| C# status effect files | 3+ | Base class, 17 implementations, manager |
| C# enemy files | 2 | Enemy.cs, EnemyDatabase.cs |
| Unit test files | 17+ | One per source file minimum |
| Integration tests | 3 | Character creation, save/load roundtrip, enemy AI |

### 1.5 Target Project Structure

```
Game1.Entities/
    Character.cs                          # Main player entity (from entities/character.py)
    Tool.cs                               # Tool dataclass (from entities/tool.py)
    DamageNumber.cs                       # Floating damage data (from entities/damage_number.py)

Game1.Entities.Components/
    CharacterStats.cs                     # 6 stats + bonus calculations
    LevelingSystem.cs                     # EXP curve, level-up
    Inventory.cs                          # 30-slot inventory + ItemStack
    EquipmentManager.cs                   # 10 equipment slots + hand validation
    SkillManager.cs                       # 5 hotbar, skill learning, buff/combat dual system
    BuffManager.cs                        # ActiveBuff tracking, regeneration
    StatTracker.cs                        # 850+ statistics across 14 categories
    CraftedStats.cs                       # Quality-based stat generation
    ActivityTracker.cs                    # 8 activity counters
    WeaponTagCalculator.cs                # Tag-to-bonus conversions

Game1.Entities.StatusEffects/
    StatusEffect.cs                       # Abstract base class
    DotEffects.cs                         # BurnEffect, BleedEffect, PoisonEffect, ShockEffect
    CrowdControlEffects.cs                # FreezeEffect, SlowEffect, StunEffect, RootEffect
    BuffEffects.cs                        # RegenerationEffect, ShieldEffect, HasteEffect,
                                          #   EmpowerEffect, FortifyEffect
    DebuffEffects.cs                      # WeakenEffect, VulnerableEffect
    SpecialEffects.cs                     # PhaseEffect, InvisibleEffect
    StatusEffectFactory.cs                # STATUS_EFFECT_CLASSES dict + create_status_effect()
    StatusEffectManager.cs                # Stacking rules, mutual exclusions, update loop
    StackingBehavior.cs                   # Enum: None, Additive, Refresh

Game1.Entities.Enemies/
    EnemyDefinition.cs                    # EnemyDefinition, DropDefinition, SpecialAbility,
                                          #   AIPattern dataclasses
    EnemyDatabase.cs                      # Singleton loader from hostiles JSON
    Enemy.cs                              # Active enemy instance with AI state machine
```

---

## 2. Systems Included (17 files, ~7,638 lines)

### 2.1 Character & Simple Entities (3 files)

| # | Python File | C# Target | Lines | Key Characteristics |
|---|-------------|-----------|-------|---------------------|
| 1 | `entities/character.py` | `Game1.Entities/Character.cs` | 2,576 | Main player entity integrating all components. Key methods: `move()` with collision sliding, `recalculate_stats()`, `save_to_file()`, `restore_from_save()`. Stat formulas: VIT x 15 HP, INT x 20 mana. Movement speed: `PLAYER_SPEED = 0.15`. Knockback: 10% player input during knockback. Health regen: 5 HP/s after 5s without combat. |
| 2 | `entities/tool.py` | `Game1.Entities/Tool.cs` | 42 | Simple dataclass. `get_effectiveness()`: returns 1.0 if durability >= 50%, else linearly degrades to 0.5 at 0% durability. Items never break. |
| 3 | `entities/damage_number.py` | `Game1.Entities/DamageNumber.cs` | 19 | Floating damage display. `velocity_y = -1.0`, `lifetime = 1.0s`. `update()` returns false when expired. |

### 2.2 Status Effect System (2 files)

| # | Python File | C# Target | Lines | Key Characteristics |
|---|-------------|-----------|-------|---------------------|
| 4 | `entities/status_effect.py` | `Game1.Entities.StatusEffects/` (6 files) | 827 | Abstract `StatusEffect` base + 17 concrete implementations. Factory dict with 26 entries (17 canonical + 9 aliases). |
| 5 | `entities/status_manager.py` | `Game1.Entities.StatusEffects/StatusEffectManager.cs` | 294 | Mutual exclusions: burn<->freeze, stun<->freeze. Stacking rules: DoT=ADDITIVE, CC=REFRESH, Buffs=varies. Integration helper: `add_status_manager_to_entity()`. |

### 2.3 Components (11 files)

| # | Python File | C# Target | Lines | Key Characteristics |
|---|-------------|-----------|-------|---------------------|
| 6 | `components/stats.py` | `CharacterStats.cs` | 89 | 6 stats (STR/DEF/VIT/LCK/AGI/INT), all start at 0. Scaling: STR x 0.05 damage, DEF x 0.02 reduction (min 0.1), VIT x 0.01 durability, LCK x 0.02 crit. Flat bonuses: VIT x 15 HP, INT x 20 mana, STR x 10 carry. |
| 7 | `components/leveling.py` | `LevelingSystem.cs` | 26 | EXP curve: `200 * 1.75^(level-1)`, max level 30, +1 stat point per level. |
| 8 | `components/inventory.py` | `Inventory.cs` | 231 | 30 slots, `ItemStack` with stacking rules (same ID, not equipment, same rarity, same crafted_stats). Drag-and-drop with swap on occupied slots. Equipment items always `max_stack = 1`. |
| 9 | `components/equipment_manager.py` | `EquipmentManager.cs` | 171 | 10 slots: mainHand, offHand, helmet, chestplate, leggings, boots, gauntlets, accessory, axe, pickaxe. Hand validation: 2H blocks offhand, shields only in offhand with 1H/versatile, versatile offhand only allows 1H or shield. Unarmed: (1,2) mainHand, (0,0) offHand. |
| 10 | `components/skill_manager.py` | `SkillManager.cs` | 971 | 5 hotbar slots. Dual effect systems: legacy buff-based (empower/quicken/fortify/pierce/restore/enrich/elevate/regenerate/devastate/transcend) and tag-based combat. Level scaling: +10% per level. Skill EXP: 100 per use, curve `1000 * 2^(level-1)`, max level 10. Class affinity bonus from tag overlap. |
| 11 | `components/buffs.py` | `BuffManager.cs` | 156 | `ActiveBuff` dataclass + `BuffManager`. Effect types: empower, quicken, fortify, pierce, restore, enrich, elevate, regenerate, devastate, transcend. `consume_on_use` flag for instant-effect buffs. Regenerate applies HP/mana/durability per tick. |
| 12 | `components/stat_tracker.py` | `StatTracker.cs` | 1,721 | 14 tracking categories, 850+ statistics. `StatEntry`, `CraftingEntry`, `SkillStatEntry` dataclasses. Full serialization to/from dict. Consider phased migration: core tracking first, detailed categories later. |
| 13 | `components/crafted_stats.py` | `CraftedStats.cs` | 295 | Quality-based stat generation from minigame performance. Key formulas: `damage_mult = (quality - 50) / 100` (-0.5 to +0.5), `efficiency = 0.5 + (quality / 100)` (0.5 to 1.5), `durability_mult = (quality - 50) / 100`. |
| 14 | `components/activity_tracker.py` | `ActivityTracker.cs` | 16 | Simple counter for 8 activities: mining, forestry, smithing, refining, alchemy, engineering, enchanting, combat. |
| 15 | `components/weapon_tag_calculator.py` | `WeaponTagCalculator.cs` | 173 | Static methods. Tag bonuses: 2H = +20% damage, versatile = +10% (no offhand), fast = +15% speed, precision = +10% crit, reach = +1.0 range, armor_breaker = 25% pen, crushing = +20% vs armored. `has_cleaving()` returns bool. |

### 2.4 Combat Entities (1 file, split to 3 C# files)

| # | Python File | C# Target | Lines | Key Characteristics |
|---|-------------|-----------|-------|---------------------|
| 16 | `Combat/enemy.py` (definitions) | `EnemyDefinition.cs` + `EnemyDatabase.cs` | ~385 | `EnemyDefinition`, `DropDefinition`, `SpecialAbility`, `AIPattern` dataclasses. `EnemyDatabase` singleton loads `hostiles-1.JSON`. Health scaling: JSON value x 0.1. Chance mapping: guaranteed=1.0, high=0.75, moderate=0.5, low=0.25, rare=0.1, improbable=0.05. |
| 17 | `Combat/enemy.py` (instance) | `Enemy.cs` | ~590 | Active enemy with AI state machine (9 states: IDLE, WANDER, PATROL, GUARD, CHASE, ATTACK, FLEE, DEAD, CORPSE). Movement bounded to 3x3 chunks around spawn. Collision sliding. Special ability system with priority-sorted evaluation and per-fight usage tracking. |

---

## 3. Migration Steps -- Per-File Details

### 3.1 File: `entities/tool.py` -> `Game1.Entities/Tool.cs` (42 lines)

**Priority**: Migrate first (zero dependencies, used by Character).

#### Fields
| Python Field | C# Field | Type | Default |
|-------------|----------|------|---------|
| `tool_id` | `ToolId` | `string` | (required) |
| `name` | `Name` | `string` | (required) |
| `tool_type` | `ToolType` | `string` | (required) |
| `tier` | `Tier` | `int` | (required) |
| `damage` | `Damage` | `int` | (required) |
| `durability_current` | `DurabilityCurrent` | `int` | (required) |
| `durability_max` | `DurabilityMax` | `int` | (required) |
| `efficiency` | `Efficiency` | `float` | `1.0f` |

#### Methods
| Python Method | C# Signature | Logic |
|---------------|-------------|-------|
| `can_harvest(resource_tier)` | `bool CanHarvest(int resourceTier)` | `return Tier >= resourceTier;` |
| `use()` | `bool Use()` | If debug infinite, return true. If `DurabilityCurrent <= 0`, return false. Else decrement by 1, return true. |
| `get_effectiveness()` | `float GetEffectiveness()` | If debug infinite, return 1.0. If `DurabilityCurrent <= 0`, return 0.5. If durability percent >= 0.5, return 1.0. Else: `1.0 - (0.5 - durPct) * 0.5`. |
| `repair(amount=None)` | `void Repair(int? amount = null)` | If null, set current = max. Else `min(max, current + amount)`. |

**Pygame dependencies**: NONE. Pure logic.
**Dynamic imports**: `core.config.Config` for `DEBUG_INFINITE_RESOURCES`.

---

### 3.2 File: `entities/damage_number.py` -> `Game1.Entities/DamageNumber.cs` (19 lines)

#### Fields
| Python Field | C# Field | Type | Default |
|-------------|----------|------|---------|
| `damage` | `Damage` | `int` | (required) |
| `position` | `Position` | `Position` | (required) |
| `is_crit` | `IsCrit` | `bool` | (required) |
| `lifetime` | `Lifetime` | `float` | `1.0f` |
| `velocity_y` | `VelocityY` | `float` | `-1.0f` |

#### Methods
| Python Method | C# Signature | Logic |
|---------------|-------------|-------|
| `update(dt)` | `bool Update(float dt)` | `Lifetime -= dt; Position.Y += VelocityY * dt; return Lifetime > 0;` |

**Pygame dependencies**: NONE.
**Dynamic imports**: `data.models.Position` (Phase 1).

---

### 3.3 File: `entities/status_effect.py` -> `Game1.Entities.StatusEffects/` (827 lines)

**Priority**: Migrate before Character and Enemy (both use status effects).

#### 3.3.1 Abstract Base: `StatusEffect.cs`

```csharp
public abstract class StatusEffect
{
    public string StatusId { get; set; }
    public string Name { get; set; }
    public float Duration { get; set; }
    public float DurationRemaining { get; set; }
    public int Stacks { get; set; } = 1;
    public int MaxStacks { get; set; } = 1;
    public object Source { get; set; }
    public Dictionary<string, object> Params { get; set; }

    public bool Update(float dt, object target);      // Decrements timer, calls ApplyPeriodicEffect
    public abstract void OnApply(object target);       // Called when first applied
    public abstract void OnRemove(object target);      // Called when removed
    protected abstract void ApplyPeriodicEffect(float dt, object target);
    public void AddStack(int amount = 1);              // min(Stacks + amount, MaxStacks)
    public void RefreshDuration(float? newDuration);   // Reset timer
    public float GetProgressPercent();                 // DurationRemaining / Duration, clamped [0,1]
}
```

#### 3.3.2 DoT Effects: `DotEffects.cs`

**BurnEffect** (`status_id = "burn"`):
- Constructor params: `burn_max_stacks` (default 3), `burn_damage_per_second` (default 5.0)
- Periodic: `damage = dps * stacks * dt` -- LINEAR scaling
- Damage type: `"fire"`, tags: `["burn", "fire"]`
- Visual: adds/removes `"burn"` from `visual_effects`

**BleedEffect** (`status_id = "bleed"`):
- Constructor params: `bleed_max_stacks` (default 5), `bleed_damage_per_second` (default 3.0)
- Periodic: `damage = dps * stacks * dt` -- LINEAR scaling
- Damage type: `"physical"`, tags: `["bleed", "physical"]`

**PoisonEffect** (`status_id = "poison"`):
- Constructor params: `poison_max_stacks` (default 10), `poison_damage_per_second` (default 2.0)
- Periodic: `damage = dps * (stacks ^ 1.2) * dt` -- MULTIPLICATIVE scaling (critical difference!)
- Damage type: `"poison"`, tags: `["poison", "poison_status"]`

**ShockEffect** (`status_id = "shock"`):
- Constructor params: `shock_max_stacks` (default 3), `shock_damage_per_tick`/`damage_per_tick` (default 5.0), `shock_tick_rate`/`tick_rate` (default 2.0)
- Additional field: `float timeSinceLastTick = 0.0`
- Periodic: Accumulates dt. When `timeSinceLastTick >= tickRate`, applies `damage_per_tick * stacks` (NOT per-second -- per-tick). Resets timer.
- Damage type: `"lightning"`, tags: `["shock", "lightning"]`

#### 3.3.3 CC Effects: `CrowdControlEffects.cs`

**FreezeEffect** (`status_id = "freeze"`):
- `MaxStacks = 1` (never stacks)
- `OnApply`: stores original speed, sets speed to 0.0, sets `is_frozen = true`
- `OnRemove`: restores original speed, sets `is_frozen = false`
- Checks both `speed` and `movement_speed` properties on target
- No periodic effect

**SlowEffect** (`status_id = "slow"`):
- Constructor params: `slow_max_stacks` (default 1), `slow_percent` (default 0.5 = 50%)
- `OnApply`: stores speed, multiplies by `(1.0 - slow_percent)`
- `OnRemove`: restores stored speed
- No periodic effect

**StunEffect** (`status_id = "stun"`):
- `MaxStacks = 1`
- `OnApply`: sets `is_stunned = true`
- `OnRemove`: sets `is_stunned = false`
- No periodic effect

**RootEffect** (`status_id = "root"`):
- `MaxStacks = 1`
- `OnApply`: stores speed, sets to 0.0, sets `is_rooted = true`
- `OnRemove`: restores speed, sets `is_rooted = false`
- No periodic effect

#### 3.3.4 Buff Effects: `BuffEffects.cs`

**RegenerationEffect** (`status_id = "regeneration"`):
- Constructor params: `regen_max_stacks` (default 3), `regen_heal_per_second` (default 5.0)
- Periodic: `healing = hps * stacks * dt`, applied via `heal()` or direct `current_health` modification

**ShieldEffect** (`status_id = "shield"`):
- `MaxStacks = 1`
- Constructor params: `shield_amount` (default 50.0)
- `OnApply`: adds `shield_amount` to target's `shield_amount` attribute
- `OnRemove`: subtracts `current_shield` from target's `shield_amount`
- No periodic damage/heal

**HasteEffect** (`status_id = "haste"`):
- `MaxStacks = 1`
- Constructor params: `haste_speed_bonus` (default 0.3 = +30%)
- `OnApply`: stores speed and attack_speed, multiplies both by `(1.0 + speed_bonus)`
- `OnRemove`: restores original values

**EmpowerEffect** (`status_id = "empower"`):
- `MaxStacks = 1`
- Constructor params: `empower_damage_bonus` (default 0.25 = +25%)
- `OnApply`: adds `damage_bonus` to target's `empower_damage_multiplier` (starts at 1.0)
- `OnRemove`: subtracts `damage_bonus`

**FortifyEffect** (`status_id = "fortify"`):
- `MaxStacks = 1`
- Constructor params: `fortify_defense_bonus` (default 0.20 = +20%)
- `OnApply`: adds to `fortify_damage_reduction`
- `OnRemove`: subtracts from `fortify_damage_reduction`

#### 3.3.5 Debuff Effects: `DebuffEffects.cs`

**WeakenEffect** (`status_id = "weaken"`):
- Constructor params: `weaken_max_stacks` (default 3), `weaken_percent` (default 0.25)
- `OnApply`: `target.damage_multiplier *= (1.0 - damage_reduction)` -- MULTIPLICATIVE
- `OnRemove`: `target.damage_multiplier /= (1.0 - damage_reduction)` -- exact inverse

**VulnerableEffect** (`status_id = "vulnerable"`):
- Constructor params: `vulnerable_max_stacks` (default 3), `vulnerable_percent` (default 0.25)
- `OnApply`: `target.damage_taken_multiplier *= (1.0 + damage_increase)` -- MULTIPLICATIVE
- `OnRemove`: `target.damage_taken_multiplier /= (1.0 + damage_increase)`

#### 3.3.6 Special Effects: `SpecialEffects.cs`

**PhaseEffect** (`status_id = "phase"`):
- `MaxStacks = 1`
- Constructor params: `can_pass_walls` (default false)
- `OnApply`: sets `is_phased = true`, optionally `ignore_collisions = true`
- `OnRemove`: restores both

**InvisibleEffect** (`status_id = "invisible"`):
- `MaxStacks = 1`
- Constructor params: `breaks_on_action` (default true)
- `OnApply`: sets `is_invisible = true`
- `OnRemove`: sets `is_invisible = false`

#### 3.3.7 Factory: `StatusEffectFactory.cs`

Implement as a `Dictionary<string, Func<float, Dictionary<string, object>, object, StatusEffect>>` or use a switch statement. Must support all 26 keys:

| Key | Class | Notes |
|-----|-------|-------|
| `"burn"` | BurnEffect | Canonical |
| `"bleed"` | BleedEffect | Canonical |
| `"poison"` | PoisonEffect | Canonical |
| `"poison_status"` | PoisonEffect | Alias |
| `"freeze"` | FreezeEffect | Canonical |
| `"slow"` | SlowEffect | Canonical |
| `"chill"` | SlowEffect | Alias |
| `"stun"` | StunEffect | Canonical |
| `"root"` | RootEffect | Canonical |
| `"shock"` | ShockEffect | Canonical |
| `"regeneration"` | RegenerationEffect | Canonical |
| `"regen"` | RegenerationEffect | Alias |
| `"shield"` | ShieldEffect | Canonical |
| `"barrier"` | ShieldEffect | Alias |
| `"haste"` | HasteEffect | Canonical |
| `"quicken"` | HasteEffect | Alias |
| `"empower"` | EmpowerEffect | Canonical |
| `"fortify"` | FortifyEffect | Canonical |
| `"phase"` | PhaseEffect | Canonical |
| `"ethereal"` | PhaseEffect | Alias |
| `"intangible"` | PhaseEffect | Alias |
| `"invisible"` | InvisibleEffect | Canonical |
| `"stealth"` | InvisibleEffect | Alias |
| `"hidden"` | InvisibleEffect | Alias |
| `"weaken"` | WeakenEffect | Canonical |
| `"vulnerable"` | VulnerableEffect | Canonical |

**Duration resolution**: `params["{status_tag}_duration"]` first, then `params["duration"]`, fallback `5.0`.

---

### 3.4 File: `entities/status_manager.py` -> `StatusEffectManager.cs` + `StackingBehavior.cs` (294 lines)

#### StackingBehavior Enum
```csharp
public enum StackingBehavior { None, Additive, Refresh }
```

#### Mutual Exclusion Pairs (constant)
```csharp
private static readonly (string, string)[] MutualExclusions = {
    ("burn", "freeze"),
    ("stun", "freeze"),
};
```

#### Stacking Rules (constant dictionary)
| Status Tag | Behavior |
|-----------|----------|
| burn, bleed, poison, poison_status | Additive |
| freeze, stun, root, slow, chill | Refresh |
| regeneration, regen, shield, barrier | Additive |
| haste, quicken | Refresh |
| weaken, vulnerable | Additive |

#### Methods
| Python Method | C# Signature | Key Logic |
|---------------|-------------|-----------|
| `apply_status(tag, params, source)` | `bool ApplyStatus(string tag, Dictionary params, object source)` | Check existing -> stack/refresh/replace. Check mutual exclusions (remove conflicting). Apply resistance if target has `GetEffectResistance()`. Create via factory. Call `OnApply()`. |
| `remove_status(tag)` | `bool RemoveStatus(string tag)` | Find by `status_id`, call `OnRemove()`, remove from list. |
| `has_status(tag)` | `bool HasStatus(string tag)` | Linq/loop check on `status_id`. |
| `get_status(tag)` | `StatusEffect GetStatus(string tag)` | Return first match or null. |
| `update(dt)` | `void Update(float dt)` | Update all effects. Collect expired. Remove expired (call `OnRemove`). |
| `clear_all()` | `void ClearAll()` | Remove all, calling `OnRemove` on each. |
| `clear_debuffs()` | `void ClearDebuffs()` | Remove effects with `status_id` in debuff list. |
| `get_all_active_effects()` | `List<StatusEffect> GetAllActiveEffects()` | Return copy of list. |
| `is_crowd_controlled()` | `bool IsCrowdControlled()` | Any of: freeze, stun, root, slow, chill. |
| `is_immobilized()` | `bool IsImmobilized()` | Any of: freeze, stun, root. |
| `is_silenced()` | `bool IsSilenced()` | Any of: stun, silence. |

#### Integration Helper
```csharp
public static void AddStatusManagerToEntity(object entity)
```
Adds: `StatusManager`, `is_frozen = false`, `is_stunned = false`, `is_rooted = false`, `visual_effects = new HashSet<string>()`, `damage_multiplier = 1.0`, `damage_taken_multiplier = 1.0`, `shield_health = 0.0`.

In C#, implement as an interface `IStatusEffectable` with these properties, applied to both `Character` and `Enemy`.

---

### 3.5 File: `components/stats.py` -> `CharacterStats.cs` (89 lines)

#### Fields (all `int`, default 0)
`Strength`, `Defense`, `Vitality`, `Luck`, `Agility`, `Intelligence`

#### Methods
| Python Method | C# Signature | Key Formulas |
|---------------|-------------|--------------|
| `get_bonus(stat_name)` | `float GetBonus(string statName)` | Scaling dict: STR=0.05, DEF=0.02, VIT=0.01, LCK=0.02, AGI=0.05, INT=0.02. Returns `value * scaling`. |
| `get_flat_bonus(stat_name, bonus_type)` | `float GetFlatBonus(string statName, string bonusType)` | STR+carry_capacity = val*10, VIT+max_health = val*15, INT+mana = val*20. Else 0. |
| `get_durability_loss_multiplier()` | `float GetDurabilityLossMultiplier()` | `max(0.1, 1.0 - defense * 0.02)` |
| `get_durability_bonus_multiplier()` | `float GetDurabilityBonusMultiplier()` | `1.0 + vitality * 0.01` |
| `get_carry_capacity_multiplier()` | `float GetCarryCapacityMultiplier()` | `1.0 + strength * 0.02` |
| `get_effective_luck(title, skill, rare)` | `float GetEffectiveLuck(float titleBonus, float skillBonus, float rareDropBonus)` | `luck + titleBonus + skillBonus + (rareDropBonus / 0.02)` |

---

### 3.6 File: `components/leveling.py` -> `LevelingSystem.cs` (26 lines)

#### Fields
| Field | Type | Default |
|-------|------|---------|
| `Level` | `int` | `1` |
| `CurrentExp` | `int` | `0` |
| `MaxLevel` | `int` | `30` |
| `ExpRequirements` | `Dictionary<int, int>` | Computed: `200 * 1.75^(lvl-1)` for levels 1-30 |
| `UnallocatedStatPoints` | `int` | `0` |

#### Methods
| Python Method | C# Signature | Logic |
|---------------|-------------|-------|
| `get_exp_for_next_level()` | `int GetExpForNextLevel()` | If at max, return 0. Else `ExpRequirements[Level + 1]`. |
| `add_exp(amount, source)` | `bool AddExp(int amount, string source = "")` | If at max, return false. Add exp. If >= needed: subtract needed, increment level, +1 stat point, return true. |

**Key constant**: Level 5 requires `200 * 1.75^4 = 200 * 9.3789 = 1,876` EXP (truncated to int).

---

### 3.7 File: `components/inventory.py` -> `Inventory.cs` (231 lines)

#### ItemStack Class

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ItemId` | `string` | (required) | |
| `Quantity` | `int` | (required) | |
| `MaxStack` | `int` | `99` | Overridden from MaterialDatabase or set to 1 for equipment |
| `EquipmentData` | `EquipmentItem?` | `null` | |
| `Rarity` | `string` | `"common"` | |
| `CraftedStats` | `Dictionary<string, object>?` | `null` | |

**Post-init logic**: Query `MaterialDatabase` for max_stack. If `EquipmentDatabase.IsEquipment(itemId)`, set `MaxStack = 1` and auto-create equipment data if null.

| Method | C# Signature | Logic |
|--------|-------------|-------|
| `can_add(amount)` | `bool CanAdd(int amount)` | `Quantity + amount <= MaxStack` |
| `add(amount)` | `int Add(int amount)` | Add up to space, return remainder |
| `get_material()` | `MaterialDefinition? GetMaterial()` | Query `MaterialDatabase` |
| `is_equipment()` | `bool IsEquipment()` | `EquipmentData != null` or DB check |
| `get_equipment()` | `EquipmentItem? GetEquipment()` | Return stored or create from DB |
| `can_stack_with(other)` | `bool CanStackWith(ItemStack other)` | Same ID, both non-equipment, same rarity, same crafted_stats |

#### Inventory Class

| Field | Type | Default |
|-------|------|---------|
| `Slots` | `ItemStack?[]` | `new ItemStack?[maxSlots]` (30) |
| `MaxSlots` | `int` | `30` |
| `DraggingSlot` | `int?` | `null` |
| `DraggingStack` | `ItemStack?` | `null` |
| `DraggingFromEquipment` | `bool` | `false` |

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `add_item(id, qty, equip, rarity, stats)` | `bool AddItem(...)` | Equipment: 1 per empty slot. Materials: try existing stacks first (must pass `CanStackWith`), then new slots. |
| `get_empty_slot()` | `int? GetEmptySlot()` | First null index |
| `get_item_count(id)` | `int GetItemCount(string id)` | Sum quantities across all slots |
| `start_drag(slot)` | `void StartDrag(int slot)` | Store stack, set slot to null |
| `end_drag(target)` | `void EndDrag(int target)` | If empty: place. If stackable: merge (overflow back). Else: swap. |
| `cancel_drag()` | `void CancelDrag()` | Return to original slot |
| `has_item(id, qty)` | `bool HasItem(string id, int qty)` | `GetItemCount >= qty` |
| `remove_item(id, qty)` | `bool RemoveItem(string id, int qty)` | Remove from slots, clear empty slots |

---

### 3.8 File: `components/equipment_manager.py` -> `EquipmentManager.cs` (171 lines)

#### Slot Dictionary
10 slots, all initially null: `mainHand`, `offHand`, `helmet`, `chestplate`, `leggings`, `boots`, `gauntlets`, `accessory`, `axe`, `pickaxe`.

#### Methods

**`Equip(item, character) -> (EquipmentItem?, string)`**:
1. Call `item.CanEquip(character)` -- if false, return `(null, reason)`
2. Validate slot exists
3. **Hand type validation**:
   - mainHand + 2H: warn if offhand occupied (caller should handle unequip)
   - offHand + 2H mainhand: block ("Cannot equip offhand - mainhand is 2H weapon")
   - offHand + default mainhand: only shields allowed
   - offHand + versatile mainhand: only 1H or shield
   - offHand: item must be 1H or shield type
4. Swap old item, set new
5. Call `character.RecalculateStats()`
6. Track in stat_tracker
7. Return `(oldItem, "OK")`

**`Unequip(slot, character) -> EquipmentItem?`**: Remove from slot, recalculate stats, track.

**`GetTotalDefense() -> int`**: Sum armor slots (helmet, chestplate, leggings, boots, gauntlets) via `item.GetDefenseWithEnchantments()`.

**`GetWeaponDamage(hand) -> (int, int)`**: Return weapon damage tuple. Unarmed mainHand: `(1, 2)`. No offhand: `(0, 0)`.

**`GetWeaponRange(hand) -> float`**: Base range + tag bonus (via WeaponTagModifiers). Unarmed: 1.0. No offhand: 0.0.

**`GetWeaponAttackSpeed(hand) -> float`**: From weapon or default 1.0.

**`GetStatBonuses() -> Dictionary<string, float>`**: Aggregate all bonuses from all equipped items.

---

### 3.9 File: `components/skill_manager.py` -> `SkillManager.cs` (971 lines)

This is the largest component. Migrate in two sub-phases:

**Sub-phase A**: Core skill management (learn, equip, cooldowns, mana cost, EXP)
**Sub-phase B**: Effect application (10 buff types + combat skill execution)

#### Key Fields
| Field | Type | Default |
|-------|------|---------|
| `KnownSkills` | `Dictionary<string, PlayerSkill>` | empty |
| `EquippedSkills` | `string?[]` | `new string?[5]` |
| `MagnitudeValues` | `Dictionary<string, Dictionary<string, float>>` | Loaded from `skills-base-effects-1.JSON` |

#### Core Methods
| Method | Key Logic |
|--------|-----------|
| `CanLearnSkill(skillId, character)` | Check: not already known, skill exists, level requirement, stat requirements (STR/DEF/VIT/LCK/AGI/INT, DEX maps to AGI), title requirements. |
| `LearnSkill(skillId, character, skipChecks)` | Add `PlayerSkill` to known_skills. |
| `EquipSkill(skillId, slot)` | Set hotbar slot (0-4), mark `is_equipped = true`. |
| `UnequipSkill(slot)` | Clear slot, mark `is_equipped = false`. |
| `UpdateCooldowns(dt)` | For each known skill: `max(0, cooldown - dt)`. |
| `UseSkill(slot, character, combatManager, mousePos)` | Validate slot/skill/cooldown/mana. Consume mana. Start cooldown. Apply effect. Award 100 skill EXP per use. |

#### Level Scaling
- `get_level_scaling_bonus()` on PlayerSkill: `(level - 1) * 0.1` (so level 5 = +40%)
- Skill EXP per level: `1000 * 2^(level - 1)`, max skill level 10

#### Effect Types (buff system)
Each creates an `ActiveBuff` with appropriate parameters:
- **empower**: Damage bonus (from magnitude JSON)
- **quicken**: Speed bonus
- **fortify**: Defense bonus (flat reduction)
- **pierce**: Crit chance bonus
- **restore**: Instant HP/mana/durability restoration (amounts: minor=50, moderate=100, major=200, extreme=400; durability: minor=15%, moderate=30%, major=50%, extreme=75%)
- **enrich**: Bonus gathering yield
- **elevate**: Rarity upgrade chance
- **regenerate**: HoT/MoT over time
- **devastate**: AoE radius (instant combat or buff)
- **transcend**: Bypass tier restrictions

**Instant skills** (`duration = "instant"`): Set 60s duration, mark `consume_on_use = true`.

---

### 3.10 File: `components/buffs.py` -> `BuffManager.cs` (156 lines)

#### ActiveBuff Class
| Field | Type | Notes |
|-------|------|-------|
| `BuffId` | `string` | |
| `Name` | `string` | |
| `EffectType` | `string` | empower/quicken/fortify/pierce/restore/enrich/elevate/regenerate/devastate/transcend |
| `Category` | `string` | mining/combat/smithing/movement/etc. |
| `Magnitude` | `string` | minor/moderate/major/extreme |
| `BonusValue` | `float` | |
| `Duration` | `float` | Original duration |
| `DurationRemaining` | `float` | Countdown |
| `Source` | `string` | `"skill"` default |
| `ConsumeOnUse` | `bool` | `false` default |

#### BuffManager Methods
| Method | Key Logic |
|--------|-----------|
| `AddBuff(buff)` | Append to list (stacks with existing). |
| `Update(dt, character)` | Apply regenerate effects (HP/mana/durability). Remove expired buffs. |
| `GetTotalBonus(effectType, category)` | Sum `BonusValue` of matching buffs. |
| `GetMovementSpeedBonus()` | `GetTotalBonus("quicken", "movement")` |
| `GetDamageBonus(category)` | `GetTotalBonus("empower", category)` |
| `GetDefenseBonus()` | `GetTotalBonus("fortify", "defense")` |
| `ConsumeBuffsForAction(actionType, category)` | Remove `ConsumeOnUse` buffs matching action type: attack->combat/damage, gather->mining/forestry/fishing, craft->discipline names. |

---

### 3.11 File: `components/stat_tracker.py` -> `StatTracker.cs` (1,721 lines)

**Recommendation**: This is the largest single file. Migrate in two passes:

**Pass 1 (Essential)**: `StatEntry` dataclass (with `Record`, `GetAverage`, `ToDict`, `FromDict`), `CraftingEntry` dataclass, core tracking categories (combat, gathering, crafting, movement). ~400 lines C#.

**Pass 2 (Complete)**: All 14 categories, 850+ statistics, `SkillStatEntry`, full serialization. ~1,200 lines C#.

#### StatEntry Fields
`Count` (int), `TotalValue` (float), `MaxValue` (float), `LastUpdated` (float? nullable timestamp).

#### Key Methods
`Record(value)`, `GetAverage()`, `ToDict()`, `FromDict(data)`.

---

### 3.12 File: `components/crafted_stats.py` -> `CraftedStats.cs` (295 lines)

#### Key Functions (static utility class)

**`GenerateCraftedStats(minigameResult, recipe, itemType, slot)`**:
- Quality: `(earned / maxPoints) * 100`
- Durability mult: `(quality - 50) / 100.0` -- range -0.5 to +0.5
- Weapon: `damage_multiplier = (quality - 50) / 100.0`, `attack_speed` = 0 to +0.20 above 50, -0.10 to 0 below 50
- Armor/Shield: `defense_multiplier = (quality - 50) / 100.0`, shield also gets `block_chance` (0 to +0.10 above 50, -0.05 to 0 below 50)
- Tool: `efficiency = 0.5 + (quality / 100.0)` -- range 0.5 to 1.5

**`ApplyCraftedStatsToEquipment(equipment, stats)`**: Apply each stat to `equipment.bonuses` dict after filtering by `VALID_STATS_BY_TYPE`.

**`GetItemTypeFromSlot(slot)`**: mainHand/offHand -> weapon, helmet/chestplate/leggings/boots -> armor.

**`GetStatDisplayName(statName)`** and **`FormatStatValue(statName, value)`**: Display helpers.

---

### 3.13 File: `components/activity_tracker.py` -> `ActivityTracker.cs` (16 lines)

#### Fields
`ActivityCounts`: `Dictionary<string, int>` with 8 keys: mining, forestry, smithing, refining, alchemy, engineering, enchanting, combat. All start at 0.

#### Methods
| Method | Logic |
|--------|-------|
| `RecordActivity(type, amount)` | Increment if key exists |
| `GetCount(type)` | Return value or 0 |

---

### 3.14 File: `components/weapon_tag_calculator.py` -> `WeaponTagCalculator.cs` (173 lines)

All static methods on `WeaponTagModifiers` class:

| Method | Logic | Constants |
|--------|-------|-----------|
| `GetDamageMultiplier(tags, hasOffhand)` | 2H -> 1.2x, versatile (no offhand) -> 1.1x | 1.2, 1.1 |
| `GetAttackSpeedBonus(tags)` | fast -> +0.15 | 0.15 |
| `GetCritChanceBonus(tags)` | precision -> +0.10 | 0.10 |
| `GetRangeBonus(tags)` | reach -> +1.0 | 1.0 |
| `GetArmorPenetration(tags)` | armor_breaker -> 0.25 | 0.25 |
| `GetDamageVsArmoredBonus(tags)` | crushing -> +0.20 | 0.20 |
| `HasCleaving(tags)` | "cleaving" in tags | -- |
| `GetAllModifiersSummary(tags, hasOffhand)` | Human-readable string | -- |

---

### 3.15 File: `Combat/enemy.py` -> `EnemyDefinition.cs` + `EnemyDatabase.cs` + `Enemy.cs` (975 lines)

#### 3.15.1 Data Classes: `EnemyDefinition.cs`

**DropDefinition**: `MaterialId` (string), `QuantityMin` (int), `QuantityMax` (int), `Chance` (float 0-1).

**SpecialAbility**: `AbilityId`, `Name`, `Cooldown` (float), `Tags` (List<string>), `Params` (Dictionary), `HealthThreshold` (default 1.0), `DistanceMin` (0.0), `DistanceMax` (999.0), `EnemyCount` (0), `AllyCount` (0), `OncePerFight` (false), `MaxUsesPerFight` (0), `Priority` (0).

**AIPattern**: `DefaultState` (string), `AggroOnDamage` (bool), `AggroOnProximity` (bool), `FleeAtHealth` (float), `CallForHelpRadius` (float), `PackCoordination` (bool, default false), `SpecialAbilities` (List<string>).

**EnemyDefinition**: `EnemyId`, `Name`, `Tier`, `Category`, `Behavior`, `MaxHealth`, `DamageMin`, `DamageMax`, `Defense`, `Speed`, `AggroRange`, `AttackSpeed`, `Drops` (List<DropDefinition>), `AiPattern`, `SpecialAbilities` (List<SpecialAbility>), `Narrative`, `Tags`, `IconPath`.

#### 3.15.2 `EnemyDatabase.cs` (Singleton)

**Chance map** (constant):
```csharp
{ "guaranteed", 1.0f }, { "high", 0.75f }, { "moderate", 0.5f },
{ "low", 0.25f }, { "rare", 0.10f }, { "improbable", 0.05f }
```

**Health scaling**: `stats.health * 0.1f` (CRITICAL: 90% reduction for testing balance)

**Methods**: `LoadFromFile(path)`, `LoadAdditionalFile(path)`, `GetEnemy(id)`, `GetEnemiesByTier(tier)`, `GetRandomEnemy(tier)`. Placeholder creation on load failure (Grey Wolf: 80 HP, 8-12 dmg, 5 def).

#### 3.15.3 `Enemy.cs` (Active Instance)

**Constructor** takes `EnemyDefinition`, `(float, float) position`, `(int, int) chunkCoords`.

**Key Fields**:
| Field | Type | Initial Value |
|-------|------|---------------|
| `Position` | `float[]` | From constructor (mutable list) |
| `SpawnPosition` | `float[]` | Copy of position |
| `CurrentHealth` | `float` | `definition.MaxHealth` |
| `AiState` | `AIState` | From `_GetInitialState()` |
| `WanderTimer` | `float` | `0.0` |
| `WanderCooldown` | `float` | `Random(2.0, 5.0)` |
| `AttackCooldown` | `float` | `0.0` |
| `IsAlive` | `bool` | `true` |
| `TimeSinceDeath` | `float` | `0.0` |
| `CorpseLifetime` | `float` | `30.0` |
| `IsDungeonEnemy` | `bool` | `false` |
| `IsBoss` | `bool` | `"boss" in behavior` |
| `AbilityCooldowns` | `Dictionary<string, float>` | All abilities -> 0.0 |
| `AbilityUsesThisFight` | `Dictionary<string, int>` | All abilities -> 0 |

**AI State Machine** (`UpdateAi` method):
1. If dead: transition DEAD->CORPSE, increment `TimeSinceDeath`, return
2. Update knockback, status effects, attack cooldown, ability cooldowns
3. Calculate `distToPlayer`
4. Dispatch to state handler:
   - **IDLE**: Check proximity aggro (with night multiplier)
   - **WANDER**: Timer-based random movement within 3 tiles of spawn. Check proximity aggro.
   - **PATROL**: Move between random points within 5 tiles of spawn. Check proximity aggro.
   - **GUARD**: Return to spawn if > 1.0 away. Check proximity aggro.
   - **CHASE**: If in attack range (1.5), transition to ATTACK. If > 2x aggro range, reset to initial state. Else move toward player.
   - **ATTACK**: If player > 1.5x attack range, transition to CHASE. (Attack execution handled by CombatManager)
   - **FLEE**: Run away from player. If > 2x aggro range, transition to WANDER.

**Movement**: `_MoveTowards(target, dt)` with speed = `definition.Speed * dt * 2 * speedMultiplier`. Clamped to 3x3 chunk bounds. Collision sliding (try full, then X-only, then Y-only).

**Combat Methods**:
| Method | Logic |
|--------|-------|
| `TakeDamage(damage, type, fromPlayer, tags, source)` | Subtract HP. If from player + aggro_on_damage: CHASE. If dead: set DEAD. If health < flee threshold: FLEE. Return true if died. |
| `GenerateLoot()` | For each drop: `Random() <= chance` -> random quantity in range. Return list of (materialId, quantity). |
| `CanAttack()` | Not silenced AND cooldown <= 0 AND state == ATTACK. |
| `PerformAttack()` | Set cooldown = `1.0 / attackSpeed`. Return `Random(damageMin, damageMax)`. |
| `CanUseSpecialAbility(dist)` | Sort by priority descending. Check: health threshold, cooldown, distance range, once-per-fight, max-uses. Return first matching ability or null. |
| `UseSpecialAbility(ability, target, targets)` | Call `AttackWithTags`. On success: start cooldown, increment usage counter. |
| `AttackWithTags(target, tags, params, targets)` | Execute via `EffectExecutor.ExecuteEffect()`. |

---

### 3.16 File: `entities/character.py` -> `Game1.Entities/Character.cs` (2,576 lines)

**Migrate last** -- depends on all components and status effects.

#### Constructor Fields
| Field | Type | Initial Value |
|-------|------|---------------|
| `Position` | `Position` | From constructor arg |
| `Facing` | `string` | `"down"` |
| `MovementSpeed` | `float` | `Config.PLAYER_SPEED` (0.15) |
| `InteractionRange` | `float` | `Config.INTERACTION_RANGE` |
| `KnockbackVelocityX/Y` | `float` | `0.0` |
| `KnockbackDurationRemaining` | `float` | `0.0` |
| `BaseMaxHealth` | `int` | `100` |
| `BaseMaxMana` | `int` | `100` |
| `MaxHealth`, `Health` | `int` | `100` |
| `MaxMana`, `Mana` | `int` | `100` |
| `ShieldAmount` | `float` | `0.0` |
| `Category` | `string` | `"player"` |
| `AttackCooldown` | `float` | `0.0` |
| `MainhandCooldown` | `float` | `0.0` |
| `OffhandCooldown` | `float` | `0.0` |
| `IsBlocking` | `bool` | `false` |
| `HealthRegenThreshold` | `float` | `5.0` (seconds) |
| `HealthRegenRate` | `float` | `5.0` (HP/s) |
| `TimeSinceLastDamageTaken` | `float` | `0.0` |
| `TimeSinceLastDamageDealt` | `float` | `0.0` |
| `InventedRecipes` | `List<Dictionary>` | empty |

#### Component Initialization (in constructor order)
1. `Stats = new CharacterStats()`
2. `Leveling = new LevelingSystem()`
3. `Skills = new SkillManager()`
4. `SkillUnlocks = new SkillUnlockSystem()`
5. `Buffs = new BuffManager()`
6. `Titles = new TitleSystem()`
7. `ClassSystem = new ClassSystem()` + register `_OnClassSelected` callback
8. `Activities = new ActivityTracker()`
9. `StatTracker = new StatTracker()` + `StartSession()`
10. `Equipment = new EquipmentManager()`
11. `Encyclopedia = new Encyclopedia()`
12. `Quests = new QuestManager()`
13. `Inventory = new Inventory(30)`
14. `AddStatusManagerToEntity(this)` -- adds status manager + CC flags
15. `_GiveStartingTools()` -- equips copper_axe and copper_pickaxe from EquipmentDatabase

#### Key Methods

**`RecalculateStats()`**:
```
maxHealth = baseMaxHealth + (VIT * 15) + classBonus("max_health") + equipBonus("max_health")
maxMana   = baseMaxMana   + (INT * 20) + classBonus("max_mana")  + equipBonus("max_mana")
// Scale current proportionally:
health = min(maxHealth, maxHealth * (oldHealth / oldMaxHealth))
mana   = min(maxMana,   maxMana   * (oldMana / oldMaxMana))
```

**`AllocateStatPoint(statName) -> bool`**: Decrement unallocated, increment stat, recalculate.

**`Move(dx, dy, world) -> bool`**:
1. Check `StatusManager.IsImmobilized()` -> return false
2. If knockback active: reduce dx/dy to 10%
3. Calculate speed: `1.0 + (AGI * 0.015) + classBonus + buffBonus`
4. Apply slow/chill status reduction
5. Apply movement enchantments from armor
6. Collision sliding: try full diagonal, then X-only, then Y-only
7. Update facing based on primary direction
8. Track movement in StatTracker
9. Return true if moved

**`UpdateKnockback(dt, world)`**: Apply velocity, check walkability, decrement timer.

**`SaveToFile(filename) -> bool`**: Serialize all state to JSON dict, write to `saves/` directory.

**`RestoreFromSave(playerData)`**: Comprehensive restoration of all state from dict. Handles both old format (item_id strings) and new format (full equipment dicts with durability/enchantments). Re-registers invented recipes with RecipeDatabase.

**UI state flags** (for rendering, not migrated as gameplay logic): `crafting_ui_open`, `stats_ui_open`, `equipment_ui_open`, `skills_ui_open`, `class_selection_open`, scroll offsets. These should be tracked separately in C# (likely in a UI manager, not the entity).

---

## 4. Key Architectural Decisions

### 4.1 Status Effects: Abstract Class Hierarchy

Use an abstract `StatusEffect` base class (not interface) to match the Python ABC pattern. The base class contains shared `Update()`, `AddStack()`, `RefreshDuration()`, and `GetProgressPercent()` logic. Each concrete effect overrides the three abstract methods.

Consider grouping effects into files by category (DoT, CC, Buff, Debuff, Special) rather than one file per effect to reduce file count while maintaining readability.

### 4.2 Enemy AI: State Machine Pattern

Implement using `AIState` enum (already defined in Phase 1) with a `switch` statement in `UpdateAi()`. Each state handler is a private method. This mirrors the Python structure exactly and keeps the state machine readable.

Do NOT use a state object pattern (Strategy pattern) here -- the Python code uses simple method dispatch and the states share too much context to benefit from encapsulation.

### 4.3 Character Composition: Plain C# Objects

Components (`CharacterStats`, `LevelingSystem`, `Inventory`, etc.) should be plain C# classes, NOT MonoBehaviours. The `Character` class owns them as fields. This preserves the Python composition pattern and avoids Unity lifecycle complications.

If later integrating with Unity, a thin `CharacterMonoBehaviour` wrapper can delegate to the plain `Character` instance.

### 4.4 IStatusEffectable Interface

Create an interface to replace the Python duck-typing pattern used by status effects:

```csharp
public interface IStatusEffectable
{
    StatusEffectManager StatusManager { get; }
    bool IsFrozen { get; set; }
    bool IsStunned { get; set; }
    bool IsRooted { get; set; }
    HashSet<string> VisualEffects { get; }
    float DamageMultiplier { get; set; }
    float DamageTakenMultiplier { get; set; }
    float ShieldHealth { get; set; }
}
```

Both `Character` and `Enemy` implement this interface.

### 4.5 StatTracker Scope Reduction

The StatTracker is 1,721 lines with 850+ statistics. For initial migration:
- **Phase 3A**: Migrate `StatEntry`, `CraftingEntry`, and the core `StatTracker` shell with serialization.
- **Phase 3B**: Fill in all 14 category initializations and recording methods.

This prevents the StatTracker from blocking the rest of Phase 3.

### 4.6 Save/Load Separation

The `save_to_file()` and `restore_from_save()` methods on Character are complex (400+ lines combined). Consider migrating the serialization logic into a separate `CharacterSerializer` class in C# rather than embedding it in `Character.cs`. The Character class is already 2,576 lines; separating serialization improves maintainability.

---

## 5. Quality Control Instructions

### 5.1 Per-File QC Checklist

For each migrated file, verify:

- [ ] Every Python method has a C# equivalent with identical logic
- [ ] All numeric constants preserved exactly (no rounding, no unit changes)
- [ ] All default parameter values match Python defaults
- [ ] Status effect factory creates correct types from all 26 keys (17 canonical + 9 aliases)
- [ ] AI state transitions match Python logic for every state pair
- [ ] Component initialization order in Character constructor preserved
- [ ] Inventory stacking rules match exactly (same ID, not equipment, same rarity, same crafted_stats)
- [ ] Equipment hand-type validation matches all cases (2H, 1H, versatile, default, shield)
- [ ] No Pygame imports remain (note: these files have ZERO pygame -- all pure logic)
- [ ] Dynamic/deferred imports resolved to direct references

### 5.2 Behavioral Validation Tests

Each of these tests must produce identical results in Python and C#:

**Status Effects**:
- BurnEffect: 10 dps, 3 stacks, 0.5s dt = `10 * 3 * 0.5 = 15.0` damage
- PoisonEffect (multiplicative): 5 dps, 3 stacks, 1.0s dt = `5 * 3^1.2 * 1.0 = 5 * 3.7372 = 18.686` damage (approximately 18.69)
- ShockEffect: 5 dpt, tick_rate=2.0, 1.5s elapsed = 0 damage (not yet ticked); 2.0s elapsed = 5 damage
- SlowEffect: 50% slow on entity with speed 1.0 -> speed becomes 0.5
- Weaken + Vulnerable stacking: 25% weaken then 25% vulnerable on entity: `damage_mult = 1.0 * 0.75 = 0.75`, `damage_taken_mult = 1.0 * 1.25 = 1.25`

**Mutual Exclusions**:
- Apply burn, then freeze: burn removed, freeze active
- Apply stun, then freeze: stun removed, freeze active
- Apply freeze, then burn: freeze removed, burn active

**EquipmentManager**:
- 2H weapon in mainHand -> offHand must be null (caller responsibility, but equip warns)
- Attempt offHand equip with 2H mainhand -> returns "Cannot equip offhand - mainhand is 2H weapon"
- Versatile mainhand + 1H offhand -> allowed
- Versatile mainhand + 2H offhand -> blocked
- Default mainhand + non-shield offhand -> blocked

**SkillManager**:
- Skill level 1: bonus = `(1-1) * 0.1 = 0.0` (+0%)
- Skill level 5: bonus = `(5-1) * 0.1 = 0.4` (+40%)
- Skill level 10: bonus = `(10-1) * 0.1 = 0.9` (+90%)
- Skill EXP to level 2: `1000 * 2^0 = 1000` (10 uses at 100 EXP each)
- Skill EXP to level 3: `1000 * 2^1 = 2000` (20 additional uses)

**LevelingSystem**:
- Level 1 -> 2: `200 * 1.75^0 = 200` EXP
- Level 5 -> 6: `200 * 1.75^4 = 200 * 9.3789 = 1,876` EXP (int truncation)
- Level 10 -> 11: `200 * 1.75^9 = 200 * 116.415 = 23,283` EXP
- Level 30: max level, `add_exp()` returns false

**EnemyDatabase**:
- Health scaling: JSON value 500 -> actual `500 * 0.1 = 50.0`
- Chance "guaranteed" -> 1.0, "improbable" -> 0.05
- Placeholder creation: Grey Wolf with 80 HP

**Enemy AI**:
- Initial state from behavior "wander" -> AIState.WANDER
- Aggro on proximity: distance < aggro_range -> CHASE
- Chase to attack: distance < 1.5 -> ATTACK
- Chase give-up: distance > aggro_range * 2 -> initial state
- Flee trigger: health < flee_at_health threshold -> FLEE
- Flee escape: distance > aggro_range * 2 -> WANDER

**Character**:
- Base stats: 100 HP, 100 mana at level 1 with 0 stats
- VIT 10: `max_health = 100 + (10 * 15) = 250`
- INT 10: `max_mana = 100 + (10 * 20) = 300`
- Move speed with AGI 10: `1.0 + (10 * 0.015) = 1.15x`
- Tool effectiveness: 100% durability -> 1.0, 50% durability -> 1.0, 25% durability -> 0.875, 0% durability -> 0.5

**Inventory**:
- Add 50 items with max_stack 99: occupies 1 slot with quantity 50
- Add equipment: always occupies 1 slot per item
- Stacking check: same item + same rarity + no crafted_stats = stackable
- Stacking check: same item + different rarity = NOT stackable

---

### 5.3 Phase 3 Quality Gate

All of the following must pass before Phase 3 is marked complete:

- [ ] Character can be created with all components initialized in correct order
- [ ] All 17 status effects instantiate and apply/remove correctly
- [ ] Status effect stacking rules work (ADDITIVE adds stacks, REFRESH resets timer, NONE replaces)
- [ ] Mutual exclusions work (burn<->freeze, stun<->freeze)
- [ ] StatusEffectFactory resolves all 26 keys to correct effect types
- [ ] Inventory add/remove/drag operations work for materials and equipment
- [ ] ItemStack stacking rules enforced (same ID, not equipment, same rarity, same crafted_stats)
- [ ] Equipment slot validation works for all hand types (2H, 1H, versatile, default, shield)
- [ ] Equipment stat bonuses aggregate correctly
- [ ] Weapon tag calculator produces correct values for all tag types
- [ ] Enemy AI state machine transitions correctly for all 9 states
- [ ] Enemy special ability evaluation respects priority, cooldowns, health thresholds, and per-fight limits
- [ ] LevelingSystem EXP curve matches Python exactly for all 30 levels
- [ ] Character.RecalculateStats produces correct maxHealth/maxMana
- [ ] Save/load roundtrip preserves all character state (position, stats, inventory, equipment, skills, titles, activities, invented recipes)
- [ ] Crafted stats generation produces correct values for all item types
- [ ] BuffManager correctly applies/expires/consumes buffs
- [ ] Comparison tests: Python output matches C# output for all behavioral validation scenarios

---

## 6. Migration Order

Execute files in this order to minimize forward references:

| Step | File(s) | Rationale |
|------|---------|-----------|
| 1 | `Tool.cs`, `DamageNumber.cs` | Zero dependencies, trivial |
| 2 | `CharacterStats.cs` | No component dependencies |
| 3 | `LevelingSystem.cs` | No component dependencies |
| 4 | `ActivityTracker.cs` | No component dependencies |
| 5 | `WeaponTagCalculator.cs` | Static utility, no dependencies |
| 6 | `CraftedStats.cs` | Static utility, depends on EquipmentItem (Phase 1) |
| 7 | `StatusEffect.cs` + all 17 effects + `StatusEffectFactory.cs` | Self-contained hierarchy |
| 8 | `StatusEffectManager.cs` + `StackingBehavior.cs` | Depends on step 7 |
| 9 | `BuffManager.cs` | ActiveBuff is self-contained |
| 10 | `Inventory.cs` (ItemStack + Inventory) | Depends on Phase 2 databases |
| 11 | `EquipmentManager.cs` | Depends on EquipmentItem (Phase 1) |
| 12 | `SkillManager.cs` | Depends on steps 9, 11, Phase 2 SkillDatabase |
| 13 | `StatTracker.cs` (Pass 1: core) | Large file, essential for Character |
| 14 | `EnemyDefinition.cs` + `EnemyDatabase.cs` | Data classes + singleton |
| 15 | `Enemy.cs` | Depends on steps 7, 8, 14 |
| 16 | `Character.cs` | Depends on ALL previous steps |
| 17 | `StatTracker.cs` (Pass 2: complete) | Fill remaining categories |

---

## 7. Known Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| StatTracker size (1,721 lines, 850+ stats) | Delays Phase 3 completion | Split into Pass 1 (essential) and Pass 2 (complete). Phase 4 can begin after Pass 1. |
| Character.py UI state flags (crafting_ui_open, etc.) | Mixing entity and UI state | Extract UI flags to a separate `CharacterUIState` class in C#. Character entity remains pure game logic. |
| Dynamic Python `hasattr()` checks in status effects | C# requires explicit interfaces | Define `IStatusEffectable` and `IDamageable` interfaces. Use `is` pattern matching for optional properties. |
| SkillManager dual effect system (buff + combat) | Complex method with 10 branches | Migrate buff system first (sub-phase A), then combat skill execution (sub-phase B). Combat execution requires Phase 4 EffectExecutor. |
| Enemy `_move_towards` references `WorldSystem` | Phase 6 dependency | Use interface `IWorldCollision` with `IsWalkable(Position)`. Provide stub during Phase 3 testing. |
| Invented recipe registration in Character.restore_from_save | Tight coupling to RecipeDatabase | Keep as-is for initial migration. Refactoring to event-based registration is Phase 8 scope. |

---

## 8. Files NOT Included in Phase 3

The following are explicitly excluded and belong to other phases:

- `Combat/combat_manager.py` -> Phase 4 (Combat Systems)
- `core/effect_executor.py` -> Phase 4 (Tag-based combat effects)
- `systems/world_system.py` -> Phase 6 (World Systems)
- `systems/title_system.py` -> Phase 2 or Phase 6 (Systems)
- `systems/class_system.py` -> Phase 2 or Phase 6 (Systems)
- `rendering/renderer.py` -> Phase 7 (Rendering)
- `save_system/save_manager.py` -> Phase 8 (Save/Load)
- `systems/llm_item_generator.py` -> Phase 9 (LLM Integration)
- `systems/crafting_classifier.py` -> Phase 9 (ML Classifiers)

---

## 9. Estimated Effort

| Category | Files | Python Lines | Est. C# Lines | Est. Hours |
|----------|-------|-------------|---------------|-----------|
| Simple entities | 2 | 61 | ~80 | 1 |
| Status effects | 2 | 1,121 | ~1,400 | 6 |
| Components (small) | 5 | 593 | ~750 | 4 |
| Components (large) | 3 | 2,923 | ~3,500 | 12 |
| Enemy system | 1 (split to 3) | 975 | ~1,200 | 6 |
| Character | 1 | 2,576 | ~3,100 | 10 |
| Unit tests | 17+ | -- | ~2,000 | 8 |
| Integration tests | 3 | -- | ~500 | 4 |
| **Total** | **22+ C# files** | **~7,638** | **~12,530** | **~51** |

---

## 3D Readiness (Phase 3 Responsibilities)

### Character and Enemy Positions

- `Character.Position` and `Enemy.Position` MUST be `GamePosition` (not `Vector2` or tuples)
- All movement calculations use XZ plane initially: `character.Position = GamePosition.FromXZ(newX, newZ)`
- Height field (`Y`) defaults to 0 but is stored, serialized, and loaded. Future flying enemies or elevated terrain will use it.
- `Character.move()` and enemy pathfinding operate on XZ coordinates. Y is preserved but not modified during flat-world movement.

### ItemStack Uses IGameItem

- `ItemStack.Item` must be of type `IGameItem` (not a raw string ID or untyped dict)
- The `Inventory` holds `ItemStack[]` where each stack wraps a typed item
- Equipment operations use `stack.Item is EquipmentItem equip` pattern matching
- Save/load uses `stack.Item.ToSaveData()` for serialization and `ItemFactory.FromSaveData()` for deserialization

### Stat Caching with Events (FIX-11)

- `CharacterStats` uses dirty-flag caching, invalidated via `GameEvents` (see IMPROVEMENTS.md FIX-11)
- No per-frame stat recalculation — only recalculates when equipment, buffs, level, class, or title change

---

**Phase 3 Document Version**: 1.1
**Created**: 2026-02-10
**Updated**: 2026-02-11 (3D readiness, IGameItem, stat caching)
**For**: AI assistants and developers performing Python-to-C# migration of Game-1
