# Phase 1: Foundation Layer -- Data Models, Enums, and JSON Schema Validation

**Phase**: 1 of N
**Status**: Not Started
**Dependencies**: None (this is the root phase)
**Estimated C# Files**: 20+
**Estimated C# Lines**: ~3,500-4,500
**Source Python Lines**: 1,998 (data/models/) + AIState enum from Combat/enemy.py

---

## 1. Overview

### 1.1 Goal

Port all Python dataclasses, enums, and data model classes from `Game-1-modular/data/models/` to C# equivalents under the Unity project. This phase produces the foundational types that every subsequent phase depends on. No gameplay logic, no rendering, no database loading -- only pure data structures, enums, validation logic, and factory patterns.

### 1.2 Why This Phase Is First

Every other system in the game references these data models:
- Combat reads `EquipmentItem`, `Position`, `AIState`
- Crafting reads `Recipe`, `PlacementData`, `MaterialDefinition`
- World generation reads `TileType`, `ChunkType`, `ResourceType`, `WorldTile`
- Progression reads `TitleDefinition`, `ClassDefinition`, `SkillDefinition`
- Save/Load serializes and deserializes all of the above

No other phase can begin until these types compile and pass tests.

### 1.3 Dependencies

**Incoming**: None. Phase 1 has zero dependencies on other phases.

**Outgoing**: Every subsequent phase depends on Phase 1:
- Phase 2 (Databases) loads JSON into these models
- Phase 3 (Entity/Character) composes these models
- Phase 4 (Combat) uses `EquipmentItem`, `Position`, `AIState`
- Phase 5 (Crafting) uses `Recipe`, `PlacementData`, `MaterialDefinition`

### 1.4 Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| C# model files | 12 | One per Python source file (some split further) |
| C# enum files | 7+ | Standalone enum definitions |
| Unit test files | 12+ | One per model file minimum |
| JSON schema docs | 1 | Documents expected JSON shapes for each model |

### 1.5 Target Project Structure

```
Assets/Scripts/Game1.Data/
  Models/
    MaterialDefinition.cs
    EquipmentItem.cs
    Skills.cs
    Recipes.cs
    World.cs
    ClassDefinition.cs
    TitleDefinition.cs
    NPCDefinition.cs
    Quests.cs
    Resources.cs
    UnlockConditions.cs
    SkillUnlocks.cs
  Enums/
    TileType.cs
    ResourceType.cs
    ChunkType.cs
    StationType.cs
    PlacedEntityType.cs
    DungeonRarity.cs
    AIState.cs
  Constants/
    ResourceTiers.cs
    DungeonConfig.cs
    BarrierHealth.cs
```

All files use namespace `Game1.Data.Models` (models) or `Game1.Data.Enums` (enums) or `Game1.Data.Constants` (constant dictionaries).

---

## 2. Systems Included

### 2.1 Data Models (13 Python files, 1,998 lines total)

| # | Python File | C# Target | Lines | Classes/Enums Defined |
|---|-------------|-----------|-------|-----------------------|
| 1 | `data/models/materials.py` | `Models/MaterialDefinition.cs` | 24 | `MaterialDefinition` (1 dataclass, 12 fields) |
| 2 | `data/models/equipment.py` | `Models/EquipmentItem.cs` | 360 | `EquipmentItem` (1 dataclass, 24 fields, 15 methods) |
| 3 | `data/models/skills.py` | `Models/Skills.cs` | 135 | `SkillEffect`, `SkillCost`, `SkillEvolution`, `SkillRequirements`, `SkillDefinition`, `PlayerSkill` (6 dataclasses) |
| 4 | `data/models/recipes.py` | `Models/Recipes.cs` | 52 | `Recipe`, `PlacementData` (2 dataclasses) |
| 5 | `data/models/world.py` | `Models/World.cs` + `Enums/*.cs` + `Constants/*.cs` | 526 | `Position`, `WorldTile`, `LootDrop`, `CraftingStation`, `PlacedEntity`, `DungeonEntrance` (6 dataclasses) + `TileType`, `ResourceType`, `ChunkType`, `StationType`, `PlacedEntityType`, `DungeonRarity` (6 enums) + `RESOURCE_TIERS`, `DUNGEON_CONFIG` (2 constant dicts) |
| 6 | `data/models/classes.py` | `Models/ClassDefinition.cs` | 46 | `ClassDefinition` (1 dataclass, 8 fields, 2 methods) |
| 7 | `data/models/titles.py` | `Models/TitleDefinition.cs` | 27 | `TitleDefinition` (1 dataclass, 10 fields) |
| 8 | `data/models/npcs.py` | `Models/NPCDefinition.cs` | 17 | `NPCDefinition` (1 dataclass, 7 fields) |
| 9 | `data/models/quests.py` | `Models/Quests.cs` | 46 | `QuestObjective`, `QuestRewards`, `QuestDefinition` (3 dataclasses) |
| 10 | `data/models/resources.py` | `Models/Resources.cs` | 77 | `ResourceDrop`, `ResourceNodeDefinition` (2 dataclasses, 5 methods, 3 properties) |
| 11 | `data/models/unlock_conditions.py` | `Models/UnlockConditions.cs` | 481 | `UnlockCondition` (ABC), `LevelCondition`, `StatCondition`, `ActivityCondition`, `StatTrackerCondition`, `TitleCondition`, `SkillCondition`, `QuestCondition`, `ClassCondition` (8 implementations), `UnlockRequirements`, `ConditionFactory` (11 classes total) |
| 12 | `data/models/skill_unlocks.py` | `Models/SkillUnlocks.cs` | 182 | `UnlockCost`, `UnlockTrigger`, `SkillUnlock` (3 dataclasses, 6 methods) |
| 13 | `data/models/__init__.py` | (not migrated -- C# uses `using` directives) | 25 | Re-exports only |

### 2.2 Enums to Create

| # | Enum Name | Source File | Values | String Backing Values |
|---|-----------|-------------|--------|-----------------------|
| 1 | `TileType` | `world.py:39-44` | 4 | `"grass"`, `"stone"`, `"water"`, `"dirt"` |
| 2 | `ResourceType` | `world.py:68-136` | 47 | 28 primary + 8 legacy aliases + 1 generic fishing + 10 tiered fishing |
| 3 | `ChunkType` | `world.py:230-244` | 12 | 9 land biomes + 3 water biomes |
| 4 | `StationType` | `world.py:247-253` | 5 | `"smithing"`, `"alchemy"`, `"refining"`, `"engineering"`, `"adornments"` |
| 5 | `PlacedEntityType` | `world.py:274-283` | 8 | `"turret"`, `"trap"`, `"bomb"`, `"utility_device"`, `"crafting_station"`, `"training_dummy"`, `"barrier"`, `"dropped_item"` |
| 6 | `DungeonRarity` | `world.py:458-465` | 6 | `"common"`, `"uncommon"`, `"rare"`, `"epic"`, `"legendary"`, `"unique"` |
| 7 | `AIState` | `Combat/enemy.py:21-30` | 9 | `"idle"`, `"wander"`, `"patrol"`, `"guard"`, `"chase"`, `"attack"`, `"flee"`, `"dead"`, `"corpse"` |

### 2.3 Constants / Static Data to Create

| # | Constant | Source | Description |
|---|----------|--------|-------------|
| 1 | `RESOURCE_TIERS` | `world.py:158-214` | `Dictionary<ResourceType, int>` mapping 45 resource types to tier 1-4 |
| 2 | `DUNGEON_CONFIG` | `world.py:470-507` | `Dictionary<DungeonRarity, DungeonConfigEntry>` with spawn_weight, mob_count, tier_weights, display_name |
| 3 | `BARRIER_HEALTH_BY_TIER` | `world.py:335` | `Dictionary<int, float>` mapping tier to health: `{1:50, 2:100, 3:200, 4:400}` |

---

## 3. Migration Steps -- Detailed Per-File Instructions

### 3.1 MaterialDefinition (materials.py -> MaterialDefinition.cs)

**Source**: `Game-1-modular/data/models/materials.py` (24 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/MaterialDefinition.cs`
**Namespace**: `Game1.Data.Models`

#### Field Mapping

| Python Field | Python Type | C# Property | C# Type | Default Value | Notes |
|-------------|-------------|-------------|---------|---------------|-------|
| `material_id` | `str` | `MaterialId` | `string` | (required) | PascalCase |
| `name` | `str` | `Name` | `string` | (required) | |
| `tier` | `int` | `Tier` | `int` | (required) | Range 1-4 |
| `category` | `str` | `Category` | `string` | (required) | wood, ore, stone, metal, elemental, monster_drop, consumable, device |
| `rarity` | `str` | `Rarity` | `string` | (required) | common, uncommon, rare, epic, legendary, artifact |
| `description` | `str` | `Description` | `string` | `""` | |
| `max_stack` | `int` | `MaxStack` | `int` | `99` | |
| `properties` | `Dict` | `Properties` | `Dictionary<string, object>` | `new Dictionary<string, object>()` | Generic property bag |
| `icon_path` | `Optional[str]` | `IconPath` | `string` | `null` | Nullable reference type |
| `placeable` | `bool` | `Placeable` | `bool` | `false` | |
| `item_type` | `str` | `ItemType` | `string` | `""` | turret, trap, bomb, utility, station |
| `item_subtype` | `str` | `ItemSubtype` | `string` | `""` | projectile, area, elemental |
| `effect` | `str` | `Effect` | `string` | `""` | Description text |
| `effect_tags` | `list` | `EffectTags` | `List<string>` | `new List<string>()` | |
| `effect_params` | `dict` | `EffectParams` | `Dictionary<string, object>` | `new Dictionary<string, object>()` | |

#### C# Skeleton

```csharp
namespace Game1.Data.Models
{
    /// <summary>
    /// Definition for a material item (stackable resources, consumables, etc.).
    /// Migrated from: data/models/materials.py
    /// </summary>
    [Serializable]
    public class MaterialDefinition
    {
        public string MaterialId { get; set; }
        public string Name { get; set; }
        public int Tier { get; set; }
        public string Category { get; set; }
        public string Rarity { get; set; }
        public string Description { get; set; } = "";
        public int MaxStack { get; set; } = 99;
        public Dictionary<string, object> Properties { get; set; } = new();
        public string IconPath { get; set; }
        public bool Placeable { get; set; }
        public string ItemType { get; set; } = "";
        public string ItemSubtype { get; set; } = "";
        public string Effect { get; set; } = "";
        public List<string> EffectTags { get; set; } = new();
        public Dictionary<string, object> EffectParams { get; set; } = new();
    }
}
```

#### Special Handling
- No methods to port (pure data).
- `Dict` (untyped) in Python becomes `Dictionary<string, object>` in C#. Consider creating a typed `MaterialProperties` class in a future pass if property keys become known.
- `list` (untyped) in Python becomes `List<string>` since effect_tags always contains strings.

---

### 3.2 EquipmentItem (equipment.py -> EquipmentItem.cs)

**Source**: `Game-1-modular/data/models/equipment.py` (360 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/EquipmentItem.cs`
**Namespace**: `Game1.Data.Models`

This is the most complex model. It has 24 fields and 15 methods.

#### Field Mapping

| Python Field | Python Type | C# Property | C# Type | Default | Notes |
|-------------|-------------|-------------|---------|---------|-------|
| `item_id` | `str` | `ItemId` | `string` | (required) | |
| `name` | `str` | `Name` | `string` | (required) | |
| `tier` | `int` | `Tier` | `int` | (required) | |
| `rarity` | `str` | `Rarity` | `string` | (required) | |
| `slot` | `str` | `Slot` | `string` | (required) | mainHand, offHand, helmet, chestplate, leggings, boots, gauntlets, tool |
| `damage` | `Tuple[int, int]` | `Damage` | `(int Min, int Max)` | `(0, 0)` | Value tuple |
| `defense` | `int` | `Defense` | `int` | `0` | |
| `durability_current` | `int` | `DurabilityCurrent` | `int` | `100` | |
| `durability_max` | `int` | `DurabilityMax` | `int` | `100` | |
| `attack_speed` | `float` | `AttackSpeed` | `float` | `1.0f` | |
| `efficiency` | `float` | `Efficiency` | `float` | `1.0f` | Tool efficiency multiplier |
| `weight` | `float` | `Weight` | `float` | `1.0f` | |
| `range` | `float` | `Range` | `float` | `1.0f` | Note: `range` is not a C# keyword, safe to use |
| `requirements` | `Dict[str, Any]` | `Requirements` | `Dictionary<string, object>` | `new()` | Contains "level" (int) and "stats" (dict) |
| `bonuses` | `Dict[str, float]` | `Bonuses` | `Dictionary<string, float>` | `new()` | |
| `enchantments` | `List[Dict[str, Any]]` | `Enchantments` | `List<Dictionary<string, object>>` | `new()` | Consider typed `EnchantmentEntry` class |
| `icon_path` | `Optional[str]` | `IconPath` | `string` | `null` | |
| `hand_type` | `str` | `HandType` | `string` | `"default"` | "1H", "2H", "versatile", "default" |
| `item_type` | `str` | `ItemType` | `string` | `"weapon"` | "weapon", "shield", "tool", etc. |
| `stat_multipliers` | `Dict[str, float]` | `StatMultipliers` | `Dictionary<string, float>` | `new()` | |
| `tags` | `List[str]` | `Tags` | `List<string>` | `new()` | Metadata tags |
| `effect_tags` | `List[str]` | `EffectTags` | `List<string>` | `new()` | Combat effect tags |
| `effect_params` | `Dict[str, Any]` | `EffectParams` | `Dictionary<string, object>` | `new()` | |
| `soulbound` | `bool` | `Soulbound` | `bool` | `false` | |

#### Methods to Port

| # | Python Method | C# Signature | Lines | Key Logic |
|---|--------------|-------------|-------|-----------|
| 1 | `is_soulbound()` | `bool IsSoulbound()` | 35-47 | Check flag OR enchantment with type=="soulbound" |
| 2 | `get_effectiveness()` | `float GetEffectiveness()` | 49-55 | **CRITICAL FORMULA**: if durability<=0 return 0.5; if pct>=0.5 return 1.0; else `1.0 - (0.5 - pct) * 0.5` -- this means at 0% durability effectiveness is 0.75, NOT 0.5. The durability<=0 check returns 0.5 only if current is exactly 0 or negative, but the formula path for pct between 0 and 0.5 yields 0.75 to 1.0. Careful: when durability_current is 0, the first check catches it and returns 0.5 |
| 3 | `repair(amount, percent)` | `int Repair(int? amount = null, float? percent = null)` | 57-80 | Returns actual amount repaired |
| 4 | `needs_repair()` | `bool NeedsRepair()` | 82-88 | Simple comparison |
| 5 | `get_repair_urgency()` | `string GetRepairUrgency()` | 90-107 | Returns "none"/"low"/"medium"/"high"/"critical" at thresholds 1.0/0.5/0.2/0.0 |
| 6 | `get_actual_damage()` | `(int Min, int Max) GetActualDamage()` | 109-135 | Applies effectiveness + bonuses.damage_multiplier + tool efficiency + enchantment multipliers |
| 7 | `get_defense_with_enchantments()` | `int GetDefenseWithEnchantments()` | 137-157 | Applies effectiveness + bonuses.defense_multiplier + enchantment multipliers |
| 8 | `can_equip(character)` | `(bool CanEquip, string Reason) CanEquip(ICharacterStats character)` | 159-187 | Stat abbreviation mapping, level check, stat checks. **NOTE**: Use interface instead of concrete Character reference to avoid circular dependency |
| 9 | `copy()` | `EquipmentItem Copy()` | 189-213 | Deep copy with `copy_module.deepcopy` for enchantments. In C#: manual clone or implement `ICloneable` |
| 10 | `can_apply_enchantment(...)` | `(bool CanApply, string Reason) CanApplyEnchantment(string enchantmentId, List<string> applicableTo, Dictionary<string, object> effect, List<string> tags)` | 215-249 | **DYNAMIC IMPORT**: calls `EnchantingTagProcessor.can_apply_to_item()`. In C#: inject via interface or pass validator |
| 11 | `apply_enchantment(...)` | `(bool Success, string Reason) ApplyEnchantment(string enchantmentId, string enchantmentName, Dictionary<string, object> effect, List<string> metadataTags)` | 251-310 | Family/tier extraction via `rsplit('_', 1)`, duplicate check, conflict removal, append |
| 12 | `_get_item_type()` | `string GetItemTypeForEnchanting()` | 312-336 | Slot-based fallback logic |
| 13 | `get_metadata_tags()` | `List<string> GetMetadataTags()` | 338-344 | Returns tags or empty list |
| 14 | `get_effect_tags()` | `List<string> GetEffectTags()` | 346-352 | Returns effect_tags or empty list |
| 15 | `get_effect_params()` | `Dictionary<string, object> GetEffectParams()` | 354-360 | Returns effect_params or empty dict |

#### Critical Constants to Preserve

```
Effectiveness formula thresholds:
  durability_current <= 0  ->  0.5
  dur_pct >= 0.5           ->  1.0
  dur_pct < 0.5            ->  1.0 - (0.5 - dur_pct) * 0.5

Effectiveness examples:
  100% durability -> 1.0
  50% durability  -> 1.0
  49% durability  -> 0.995
  25% durability  -> 0.875
  0% durability   -> 0.5 (caught by <= 0 check)

Repair urgency thresholds:
  >= 100% -> "none"
  >= 50%  -> "low"
  >= 20%  -> "medium"
  > 0%    -> "high"
  == 0%   -> "critical"

Stat abbreviation mapping (8 entries):
  str -> strength, def -> defense, vit -> vitality,
  lck -> luck, agi -> agility, dex -> agility,
  int -> intelligence
  (plus full-name entries: strength -> strength, etc.)

Item type slot mapping:
  weapon slots: mainHand, offHand
  tool slots: tool
  armor slots: helmet, chestplate, leggings, boots, gauntlets
```

#### Special Handling

1. **Dynamic import in `can_apply_enchantment`**: Python does `from core.crafting_tag_processor import EnchantingTagProcessor`. In C#, inject an `IEnchantmentValidator` interface via constructor or method parameter. For Phase 1, define the interface but provide a stub implementation that always returns `(true, "OK")`.

2. **Dynamic import in `can_equip`**: Python accesses `character.leveling.level` and `character.stats.strength`. In C#, define a minimal `ICharacterStats` interface:
   ```csharp
   public interface ICharacterStats
   {
       int Level { get; }
       int Strength { get; }
       int Defense { get; }
       int Vitality { get; }
       int Luck { get; }
       int Agility { get; }
       int Intelligence { get; }
   }
   ```

3. **`Tuple[int, int]` for damage**: Use C# value tuple `(int Min, int Max)`. For JSON serialization, may need a custom converter.

4. **`copy()` method**: Use manual field-by-field copy. Deep-copy `Enchantments` list by creating new `Dictionary<string, object>` instances. Do NOT use `MemberwiseClone` because it shallow-copies collections.

5. **Enchantment family/tier parsing in `apply_enchantment`**: Python uses `rsplit('_', 1)`. C# equivalent:
   ```csharp
   private (string Family, int Tier) GetEnchantmentInfo(string enchantmentId)
   {
       int lastUnderscore = enchantmentId.LastIndexOf('_');
       if (lastUnderscore > 0 && int.TryParse(enchantmentId[(lastUnderscore + 1)..], out int tier))
           return (enchantmentId[..lastUnderscore], tier);
       return (enchantmentId, 1);
   }
   ```

---

### 3.3 Skills (skills.py -> Skills.cs)

**Source**: `Game-1-modular/data/models/skills.py` (135 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/Skills.cs`
**Namespace**: `Game1.Data.Models`

Contains 6 dataclasses. All go in one file.

#### 3.3.1 SkillEffect

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `effect_type` | `str` | `EffectType` | `string` | (required) |
| `category` | `str` | `Category` | `string` | (required) |
| `magnitude` | `str` | `Magnitude` | `string` | (required) |
| `target` | `str` | `Target` | `string` | (required) |
| `duration` | `str` | `Duration` | `string` | (required) |
| `additional_effects` | `List[Dict]` | `AdditionalEffects` | `List<Dictionary<string, object>>` | `new()` |

**`__post_init__`**: Sets `additional_effects` to `[]` if None. In C#, use field initializer `= new()`.

#### 3.3.2 SkillCost

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `mana` | `Union[str, int, float]` | `Mana` | `object` | (required) |
| `cooldown` | `Union[str, int, float]` | `Cooldown` | `object` | (required) |

**Special Handling for Union types**: Python allows `Union[str, int, float]`. Options in C#:
- **Option A (recommended)**: Store as `object` with helper methods `GetManaAsFloat()` and `GetManaAsString()` that attempt parsing.
- **Option B**: Two properties each: `string ManaQualitative` and `float ManaNumeric` with a `bool IsManaNumeric` flag.
- **Option C**: Store as `string` always, parse to float when needed.

Recommend **Option A** for Phase 1, with a TODO to revisit.

#### 3.3.3 SkillEvolution

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `can_evolve` | `bool` | `CanEvolve` | `bool` | (required) |
| `next_skill_id` | `Optional[str]` | `NextSkillId` | `string` | `null` |
| `requirement` | `str` | `Requirement` | `string` | (required) |

#### 3.3.4 SkillRequirements

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `character_level` | `int` | `CharacterLevel` | `int` | (required) |
| `stats` | `Dict[str, int]` | `Stats` | `Dictionary<string, int>` | (required) |
| `titles` | `List[str]` | `Titles` | `List<string>` | (required) |

#### 3.3.5 SkillDefinition

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `skill_id` | `str` | `SkillId` | `string` | (required) |
| `name` | `str` | `Name` | `string` | (required) |
| `tier` | `int` | `Tier` | `int` | (required) |
| `rarity` | `str` | `Rarity` | `string` | (required) |
| `categories` | `List[str]` | `Categories` | `List<string>` | (required) |
| `description` | `str` | `Description` | `string` | (required) |
| `narrative` | `str` | `Narrative` | `string` | (required) |
| `tags` | `List[str]` | `Tags` | `List<string>` | (required) |
| `effect` | `SkillEffect` | `Effect` | `SkillEffect` | (required) |
| `cost` | `SkillCost` | `Cost` | `SkillCost` | (required) |
| `evolution` | `SkillEvolution` | `Evolution` | `SkillEvolution` | (required) |
| `requirements` | `SkillRequirements` | `Requirements` | `SkillRequirements` | (required) |
| `icon_path` | `Optional[str]` | `IconPath` | `string` | `null` |
| `combat_tags` | `Optional[List[str]]` | `CombatTags` | `List<string>` | `new()` |
| `combat_params` | `Optional[Dict]` | `CombatParams` | `Dictionary<string, object>` | `new()` |

**`__post_init__`**: Sets `combat_tags` to `[]` and `combat_params` to `{}` if None. Use field initializers.

#### 3.3.6 PlayerSkill

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `skill_id` | `str` | `SkillId` | `string` | (required) |
| `level` | `int` | `Level` | `int` | `1` |
| `experience` | `int` | `Experience` | `int` | `0` |
| `current_cooldown` | `float` | `CurrentCooldown` | `float` | `0.0f` |
| `is_equipped` | `bool` | `IsEquipped` | `bool` | `false` |
| `hotbar_slot` | `Optional[int]` | `HotbarSlot` | `int?` | `null` |

**Methods to Port**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `get_definition()` | `SkillDefinition GetDefinition(ISkillDatabase db)` | **DYNAMIC IMPORT**: Python does `from data.databases.skill_db import SkillDatabase`. In C#, pass database as parameter or inject via interface. Phase 1: define method signature, implementation deferred to Phase 2 |
| `get_exp_for_next_level()` | `int GetExpForNextLevel()` | Max level 10. Formula: `1000 * (2 ^ (level - 1))`. Level 1->2 = 1000, 2->3 = 2000, ..., 9->10 = 256000 |
| `add_exp(amount)` | `(bool LeveledUp, int NewLevel) AddExp(int amount)` | Loop: while level < 10 and exp >= needed, level up. Returns tuple |
| `get_level_scaling_bonus()` | `float GetLevelScalingBonus()` | `0.1f * (Level - 1)`. Level 1 = 0%, Level 10 = 90% |
| `can_use()` | `bool CanUse()` | `CurrentCooldown <= 0` |
| `update_cooldown(dt)` | `void UpdateCooldown(float dt)` | `CurrentCooldown = Math.Max(0, CurrentCooldown - dt)` |
| `start_cooldown(seconds)` | `void StartCooldown(float cooldownSeconds)` | `CurrentCooldown = cooldownSeconds` |

**Critical Constants**:
```
Max skill level: 10
EXP formula: 1000 * 2^(level - 1)
Level scaling bonus: 10% per level above 1
```

---

### 3.4 Recipes (recipes.py -> Recipes.cs)

**Source**: `Game-1-modular/data/models/recipes.py` (52 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/Recipes.cs`
**Namespace**: `Game1.Data.Models`

#### 3.4.1 Recipe

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `recipe_id` | `str` | `RecipeId` | `string` | (required) |
| `output_id` | `str` | `OutputId` | `string` | (required) |
| `output_qty` | `int` | `OutputQty` | `int` | (required) |
| `station_type` | `str` | `StationType` | `string` | (required) |
| `station_tier` | `int` | `StationTier` | `int` | (required) |
| `inputs` | `List[Dict]` | `Inputs` | `List<Dictionary<string, object>>` | (required) |
| `grid_size` | `str` | `GridSize` | `string` | `"3x3"` |
| `mini_game_type` | `str` | `MiniGameType` | `string` | `""` |
| `metadata` | `Dict` | `Metadata` | `Dictionary<string, object>` | `new()` |
| `is_enchantment` | `bool` | `IsEnchantment` | `bool` | `false` |
| `enchantment_name` | `str` | `EnchantmentName` | `string` | `""` |
| `applicable_to` | `List[str]` | `ApplicableTo` | `List<string>` | `new()` |
| `effect` | `Dict` | `Effect` | `Dictionary<string, object>` | `new()` |

**No methods to port** (pure data).

#### 3.4.2 PlacementData

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `recipe_id` | `str` | `RecipeId` | `string` | (required) |
| `discipline` | `str` | `Discipline` | `string` | (required) |
| `grid_size` | `str` | `GridSize` | `string` | `""` |
| `placement_map` | `Dict[str, str]` | `PlacementMap` | `Dictionary<string, string>` | `new()` |
| `core_inputs` | `List[Dict]` | `CoreInputs` | `List<Dictionary<string, object>>` | `new()` |
| `surrounding_inputs` | `List[Dict]` | `SurroundingInputs` | `List<Dictionary<string, object>>` | `new()` |
| `ingredients` | `List[Dict]` | `Ingredients` | `List<Dictionary<string, object>>` | `new()` |
| `slots` | `List[Dict]` | `Slots` | `List<Dictionary<string, object>>` | `new()` |
| `pattern` | `List[Dict]` | `Pattern` | `List<Dictionary<string, object>>` | `new()` |
| `narrative` | `str` | `Narrative` | `string` | `""` |
| `output_id` | `str` | `OutputId` | `string` | `""` |
| `station_tier` | `int` | `StationTier` | `int` | `1` |

---

### 3.5 World Models (world.py -> World.cs + Enums/ + Constants/)

**Source**: `Game-1-modular/data/models/world.py` (526 lines)
**Target**: Multiple files (see below)
**Namespace**: `Game1.Data.Models`, `Game1.Data.Enums`, `Game1.Data.Constants`

This is the largest source file. It contains 6 dataclasses, 6 enums, 2 constant dictionaries, and 1 builder function. Split across multiple C# files for clarity.

#### 3.5.1 Position (World.cs)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `x` | `float` | `X` | `float` | (required) |
| `y` | `float` | `Y` | `float` | (required) |
| `z` | `float` | `Z` | `float` | `0.0f` |

**Methods**:

| Method | C# Signature | Critical Logic |
|--------|-------------|----------------|
| `distance_to(other)` | `float DistanceTo(Position other)` | `MathF.Sqrt((X-other.X)^2 + (Y-other.Y)^2 + (Z-other.Z)^2)` |
| `snap_to_grid()` | `Position SnapToGrid()` | **CRITICAL**: Must use `MathF.Floor()`, NOT `(int)` cast. `MathF.Floor(-0.5f) = -1.0f`, but `(int)(-0.5f) = 0`. This is documented explicitly in the Python docstring. |
| `to_key()` | `string ToKey()` | `$"{MathF.Floor(X)},{MathF.Floor(Y)},{MathF.Floor(Z)}"` -- must match Python `math.floor` behavior |
| `copy()` | `Position Copy()` | `new Position(X, Y, Z)` |

**Design Decision**: Do NOT use Unity `Vector3` for Position. The game Position has specific `snap_to_grid()` and `to_key()` semantics that Vector3 does not have. Instead, add an extension method or implicit conversion:
```csharp
public UnityEngine.Vector3 ToVector3() => new(X, Y, Z);
public static Position FromVector3(UnityEngine.Vector3 v) => new(v.x, v.y, v.z);
```

**Consider implementing `IEquatable<Position>`** since Python dataclasses have value equality by default.

#### 3.5.2 WorldTile (World.cs)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `position` | `Position` | `Position` | `Position` | (required) |
| `tile_type` | `TileType` | `TileType` | `TileType` | (required) |
| `occupied_by` | `Optional[str]` | `OccupiedBy` | `string` | `null` |
| `ownership` | `Optional[str]` | `Ownership` | `string` | `null` |
| `walkable` | `bool` | `Walkable` | `bool` | `true` |

**Methods**:

| Method | C# Signature | Notes |
|--------|-------------|-------|
| `get_color()` | `(int R, int G, int B) GetColor(IColorConfig config)` | **DYNAMIC IMPORT**: Python does `from core.config import Config`. In C#, inject color config or use a static color lookup class. Phase 1: accept an interface parameter. Fallback color: `Config.COLOR_GRASS`. Dirt is hardcoded `(139, 69, 19)`. |

**Color Constants to Preserve**:
```
DIRT color: (139, 69, 19)  -- hardcoded in Python
GRASS, STONE, WATER colors: from Config (deferred to Phase 2)
Default fallback: COLOR_GRASS
```

#### 3.5.3 LootDrop (World.cs)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `item_id` | `str` | `ItemId` | `string` | (required) |
| `min_quantity` | `int` | `MinQuantity` | `int` | (required) |
| `max_quantity` | `int` | `MaxQuantity` | `int` | (required) |
| `chance` | `float` | `Chance` | `float` | `1.0f` |

No methods.

#### 3.5.4 CraftingStation (World.cs)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `position` | `Position` | `Position` | `Position` | (required) |
| `station_type` | `StationType` | `StationType` | `StationType` | (required) |
| `tier` | `int` | `Tier` | `int` | (required) |

**Methods**:

| Method | C# Signature | Notes |
|--------|-------------|-------|
| `get_color()` | `(int R, int G, int B) GetColor()` | Static color map, no dynamic imports |

**Color Constants**:
```
SMITHING:    (180, 60, 60)
ALCHEMY:     (60, 180, 60)
REFINING:    (180, 120, 60)
ENGINEERING: (60, 120, 180)
ADORNMENTS:  (180, 60, 180)
Default:     (150, 150, 150)
```

#### 3.5.5 PlacedEntity (World.cs)

This is the second most complex model in this phase.

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `position` | `Position` | `Position` | `Position` | (required) |
| `item_id` | `str` | `ItemId` | `string` | (required) |
| `entity_type` | `PlacedEntityType` | `EntityType` | `PlacedEntityType` | (required) |
| `tier` | `int` | `Tier` | `int` | `1` |
| `health` | `float` | `Health` | `float` | `100.0f` |
| `owner` | `Optional[str]` | `Owner` | `string` | `null` |
| `range` | `float` | `Range` | `float` | `5.0f` |
| `damage` | `float` | `Damage` | `float` | `20.0f` |
| `attack_speed` | `float` | `AttackSpeed` | `float` | `1.0f` |
| `last_attack_time` | `float` | `LastAttackTime` | `float` | `0.0f` |
| `target_enemy` | `Optional[Any]` | `TargetEnemy` | `object` | `null` |
| `tags` | `List[str]` | `Tags` | `List<string>` | `new()` |
| `effect_params` | `Dict[str, Any]` | `EffectParams` | `Dictionary<string, object>` | `new()` |
| `lifetime` | `float` | `Lifetime` | `float` | `300.0f` |
| `time_remaining` | `float` | `TimeRemaining` | `float` | `300.0f` |
| `status_effects` | `List[Any]` | `StatusEffects` | `List<object>` | `new()` |
| `is_stunned` | `bool` | `IsStunned` | `bool` | `false` |
| `is_frozen` | `bool` | `IsFrozen` | `bool` | `false` |
| `is_rooted` | `bool` | `IsRooted` | `bool` | `false` |
| `is_burning` | `bool` | `IsBurning` | `bool` | `false` |
| `visual_effects` | `Set[str]` | `VisualEffects` | `HashSet<string>` | `new()` |
| `triggered` | `bool` | `Triggered` | `bool` | `false` |
| `crafted_stats` | `Dict[str, Any]` | `CraftedStats` | `Dictionary<string, object>` | `new()` |

Additional field created in `__post_init__`:
| `max_health` | `float` | `MaxHealth` | `float` | Computed in constructor |

**Constructor Logic (from `__post_init__`)**:

```csharp
public PlacedEntity(Position position, string itemId, PlacedEntityType entityType, int tier = 1, ...)
{
    // ... field assignments ...

    // Initialize mutable defaults
    Tags ??= new List<string>();
    EffectParams ??= new Dictionary<string, object>();
    StatusEffects ??= new List<object>();
    VisualEffects ??= new HashSet<string>();
    CraftedStats ??= new Dictionary<string, object>();

    // Barrier health by tier
    if (EntityType == PlacedEntityType.BARRIER)
    {
        Health = BarrierHealthByTier.GetValueOrDefault(Tier, 50f);
    }

    MaxHealth = Health;

    ApplyCraftedStats();
}
```

**Barrier Health Constants**:
```
Tier 1: 50
Tier 2: 100
Tier 3: 200
Tier 4: 400
Default: 50
```

**Methods to Port**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `_apply_crafted_stats()` | `private void ApplyCraftedStats()` | Power: `damage *= (1 + power/100)`. Durability: `lifetime *= (1 + durability/100)`, reset `time_remaining`. Efficiency: `attack_speed *= (1 + min(efficiency, 900)/100)`. Cap at 900 to prevent near-zero reload. Also update `effect_params["baseDamage"]` if present. |
| `get_color()` | `(int R, int G, int B) GetColor()` | Static color map (8 entries) |
| `take_damage(damage, type)` | `bool TakeDamage(float damage, string damageType = "physical")` | Returns true if destroyed (health <= 0) |
| `update_status_effects(dt)` | `void UpdateStatusEffects(float dt)` | Iterates effects, sets flags by class name, removes expired. **NOTE**: Uses `effect.__class__.__name__` which is Python-specific. In C#, use `is` pattern matching or a `StatusEffectType` enum on the effect. Phase 1: stub this method body, full implementation in Phase 4 (Combat). |

**Crafted Stats Constants**:
```
Power:       damage *= (1 + power / 100)
Durability:  lifetime *= (1 + durability / 100)
Efficiency:  attack_speed *= (1 + min(efficiency, 900) / 100)
Efficiency cap: 900 (prevents near-zero reload times)
```

**Entity Color Constants**:
```
TURRET:          (255, 140, 0)
TRAP:            (160, 82, 45)
BOMB:            (178, 34, 34)
UTILITY_DEVICE:  (60, 180, 180)
CRAFTING_STATION: (105, 105, 105)
TRAINING_DUMMY:  (200, 200, 0)
BARRIER:         (120, 120, 120)
DROPPED_ITEM:    (255, 215, 0)
Default:         (150, 150, 150)
```

#### 3.5.6 DungeonEntrance (World.cs)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `position` | `Position` | `Position` | `Position` | (required) |
| `rarity` | `DungeonRarity` | `Rarity` | `DungeonRarity` | (required) |
| `discovered` | `bool` | `Discovered` | `bool` | `false` |

**Methods**:

| Method | C# Signature | Notes |
|--------|-------------|-------|
| `get_rarity_color()` | `(int R, int G, int B) GetRarityColor()` | Static color map |

**Rarity Color Constants**:
```
COMMON:     (150, 150, 150)
UNCOMMON:   (30, 200, 30)
RARE:       (30, 100, 255)
EPIC:       (180, 60, 255)
LEGENDARY:  (255, 165, 0)
UNIQUE:     (255, 50, 50)
Default:    (150, 150, 150)
```

#### 3.5.7 Enums (separate files in Enums/)

All enums must support string-to-enum and enum-to-string conversion because JSON uses string values.

**Recommended pattern**:

```csharp
namespace Game1.Data.Enums
{
    public enum TileType
    {
        Grass,
        Stone,
        Water,
        Dirt
    }

    public static class TileTypeExtensions
    {
        private static readonly Dictionary<TileType, string> ToStringMap = new()
        {
            { TileType.Grass, "grass" },
            { TileType.Stone, "stone" },
            { TileType.Water, "water" },
            { TileType.Dirt, "dirt" }
        };

        private static readonly Dictionary<string, TileType> FromStringMap =
            ToStringMap.ToDictionary(kvp => kvp.Value, kvp => kvp.Key);

        public static string ToJsonString(this TileType type) => ToStringMap[type];

        public static TileType FromJsonString(string value) =>
            FromStringMap.TryGetValue(value, out var result) ? result : TileType.Grass;
    }
}
```

**ResourceType Special Case -- Legacy Aliases**:

Python allows multiple enum members with the same value (aliases). C# does not support this natively. Solution: Use a separate static dictionary for aliases:

```csharp
public static class ResourceTypeAliases
{
    public static readonly Dictionary<string, ResourceType> LegacyAliases = new()
    {
        { "copper_vein", ResourceType.CopperVein },      // COPPER_ORE alias
        { "iron_deposit", ResourceType.IronDeposit },     // IRON_ORE alias
        { "steel_node", ResourceType.SteelNode },         // STEEL_ORE alias
        { "mithril_cache", ResourceType.MithrilCache },   // MITHRIL_ORE alias
        { "limestone_outcrop", ResourceType.LimestoneOutcrop }, // LIMESTONE alias
        { "granite_formation", ResourceType.GraniteFormation }, // GRANITE alias
        { "obsidian_flow", ResourceType.ObsidianFlow },   // OBSIDIAN alias
        { "diamond_geode", ResourceType.DiamondGeode }    // STAR_CRYSTAL alias
    };
}
```

Note: In Python these aliases resolve to the same enum member (same value). In C#, the alias lookup should return the canonical enum member.

#### 3.5.8 Constants (separate files in Constants/)

**ResourceTiers.cs**: Static class with `Dictionary<ResourceType, int>` containing all 45 tier mappings from `world.py:158-214`. Include both primary and legacy alias entries.

**DungeonConfig.cs**: Static class with `Dictionary<DungeonRarity, DungeonConfigEntry>` where:

```csharp
public class DungeonConfigEntry
{
    public int SpawnWeight { get; set; }
    public int MobCount { get; set; }
    public Dictionary<int, int> TierWeights { get; set; } = new();
    public string DisplayName { get; set; }
}
```

Exact values from `world.py:470-507`:
```
COMMON:     spawn_weight=50,  mob_count=20, tier_weights={1:80, 2:20}
UNCOMMON:   spawn_weight=25,  mob_count=30, tier_weights={1:50, 2:40, 3:10}
RARE:       spawn_weight=15,  mob_count=40, tier_weights={2:60, 3:35, 4:5}
EPIC:       spawn_weight=7,   mob_count=50, tier_weights={2:20, 3:60, 4:20}
LEGENDARY:  spawn_weight=2,   mob_count=50, tier_weights={3:40, 4:60}
UNIQUE:     spawn_weight=1,   mob_count=50, tier_weights={3:10, 4:90}
```

**Note on `_build_resource_tiers()` function**: Python has a dynamic builder that tries to load from the database first, falling back to hardcoded values. In C#, hardcode the defaults in `ResourceTiers.cs`. The database override behavior belongs in Phase 2 (Database layer).

---

### 3.6 ClassDefinition (classes.py -> ClassDefinition.cs)

**Source**: `Game-1-modular/data/models/classes.py` (46 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/ClassDefinition.cs`
**Namespace**: `Game1.Data.Models`

#### Field Mapping

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `class_id` | `str` | `ClassId` | `string` | (required) |
| `name` | `str` | `Name` | `string` | (required) |
| `description` | `str` | `Description` | `string` | (required) |
| `bonuses` | `Dict[str, float]` | `Bonuses` | `Dictionary<string, float>` | (required) |
| `starting_skill` | `str` | `StartingSkill` | `string` | `""` |
| `recommended_stats` | `List[str]` | `RecommendedStats` | `List<string>` | `new()` |
| `tags` | `List[str]` | `Tags` | `List<string>` | `new()` |
| `preferred_damage_types` | `List[str]` | `PreferredDamageTypes` | `List<string>` | `new()` |
| `preferred_armor_type` | `str` | `PreferredArmorType` | `string` | `""` |

#### Methods to Port

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `has_tag(tag)` | `bool HasTag(string tag)` | Case-insensitive search: `Tags.Any(t => t.Equals(tag, StringComparison.OrdinalIgnoreCase))` |
| `get_skill_affinity_bonus(skill_tags)` | `float GetSkillAffinityBonus(List<string> skillTags)` | Count matching tags (case-insensitive), multiply by 0.05, cap at 0.20. Returns 0.0 if either list is null/empty. |

**Critical Constants**:
```
bonus_per_tag = 0.05  (5% per matching tag)
max_bonus = 0.20      (20% maximum)
```

---

### 3.7 TitleDefinition (titles.py -> TitleDefinition.cs)

**Source**: `Game-1-modular/data/models/titles.py` (27 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/TitleDefinition.cs`
**Namespace**: `Game1.Data.Models`

**Note**: This class depends on `UnlockRequirements` from `unlock_conditions.py`. Both are in Phase 1, so this is an intra-phase dependency. Migrate `UnlockConditions.cs` first.

#### Field Mapping

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `title_id` | `str` | `TitleId` | `string` | (required) |
| `name` | `str` | `Name` | `string` | (required) |
| `tier` | `str` | `Tier` | `string` | (required) |
| `category` | `str` | `Category` | `string` | (required) |
| `bonus_description` | `str` | `BonusDescription` | `string` | (required) |
| `bonuses` | `Dict[str, float]` | `Bonuses` | `Dictionary<string, float>` | (required) |
| `requirements` | `UnlockRequirements` | `Requirements` | `UnlockRequirements` | (required) |
| `hidden` | `bool` | `Hidden` | `bool` | `false` |
| `acquisition_method` | `str` | `AcquisitionMethod` | `string` | `"guaranteed_milestone"` |
| `generation_chance` | `float` | `GenerationChance` | `float` | `1.0f` |
| `icon_path` | `Optional[str]` | `IconPath` | `string` | `null` |
| `activity_type` | `str` | `ActivityType` | `string` | `"general"` |
| `acquisition_threshold` | `int` | `AcquisitionThreshold` | `int` | `0` |
| `prerequisites` | `List[str]` | `Prerequisites` | `List<string>` | `new()` |

No methods to port (pure data).

---

### 3.8 NPCDefinition (npcs.py -> NPCDefinition.cs)

**Source**: `Game-1-modular/data/models/npcs.py` (17 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/NPCDefinition.cs`
**Namespace**: `Game1.Data.Models`

#### Field Mapping

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `npc_id` | `str` | `NpcId` | `string` | (required) |
| `name` | `str` | `Name` | `string` | (required) |
| `position` | `Position` | `Position` | `Position` | (required) |
| `sprite_color` | `Tuple[int, int, int]` | `SpriteColor` | `(int R, int G, int B)` | (required) |
| `interaction_radius` | `float` | `InteractionRadius` | `float` | (required) |
| `dialogue_lines` | `List[str]` | `DialogueLines` | `List<string>` | (required) |
| `quests` | `List[str]` | `Quests` | `List<string>` | (required) |

No methods to port. Depends on `Position` (intra-phase).

---

### 3.9 Quests (quests.py -> Quests.cs)

**Source**: `Game-1-modular/data/models/quests.py` (46 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/Quests.cs`
**Namespace**: `Game1.Data.Models`

#### 3.9.1 QuestObjective

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `objective_type` | `str` | `ObjectiveType` | `string` | (required) |
| `items` | `List[Dict[str, Any]]` | `Items` | `List<Dictionary<string, object>>` | `new()` |
| `enemies_killed` | `int` | `EnemiesKilled` | `int` | `0` |

#### 3.9.2 QuestRewards

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `experience` | `int` | `Experience` | `int` | `0` |
| `gold` | `int` | `Gold` | `int` | `0` |
| `health_restore` | `int` | `HealthRestore` | `int` | `0` |
| `mana_restore` | `int` | `ManaRestore` | `int` | `0` |
| `skills` | `List[str]` | `Skills` | `List<string>` | `new()` |
| `items` | `List[Dict[str, Any]]` | `Items` | `List<Dictionary<string, object>>` | `new()` |
| `title` | `str` | `Title` | `string` | `""` |
| `stat_points` | `int` | `StatPoints` | `int` | `0` |
| `status_effects` | `List[Dict[str, Any]]` | `StatusEffects` | `List<Dictionary<string, object>>` | `new()` |
| `buffs` | `List[Dict[str, Any]]` | `Buffs` | `List<Dictionary<string, object>>` | `new()` |

#### 3.9.3 QuestDefinition

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `quest_id` | `str` | `QuestId` | `string` | (required) |
| `title` | `str` | `Title` | `string` | (required) |
| `description` | `str` | `Description` | `string` | (required) |
| `npc_id` | `str` | `NpcId` | `string` | (required) |
| `objectives` | `QuestObjective` | `Objectives` | `QuestObjective` | (required) |
| `rewards` | `QuestRewards` | `Rewards` | `QuestRewards` | (required) |
| `completion_dialogue` | `List[str]` | `CompletionDialogue` | `List<string>` | `new()` |

No methods to port in any quest class.

---

### 3.10 Resources (resources.py -> Resources.cs)

**Source**: `Game-1-modular/data/models/resources.py` (77 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/Resources.cs`
**Namespace**: `Game1.Data.Models`

#### 3.10.1 ResourceDrop

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `material_id` | `str` | `MaterialId` | `string` | (required) |
| `quantity` | `str` | `Quantity` | `string` | (required) |
| `chance` | `str` | `Chance` | `string` | (required) |

**Methods**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `get_quantity_range()` | `(int Min, int Max) GetQuantityRange()` | Lookup map, default `(1, 3)` |
| `get_chance_value()` | `float GetChanceValue()` | Lookup map, default `1.0f` |

**Critical Constants -- Quantity Map**:
```
"few"      -> (1, 2)
"several"  -> (2, 4)
"many"     -> (3, 5)
"abundant" -> (4, 8)
Default    -> (1, 3)
```

**Critical Constants -- Chance Map**:
```
"guaranteed" -> 1.0
"high"       -> 0.8
"moderate"   -> 0.5
"low"        -> 0.25
"rare"       -> 0.1
"improbable" -> 0.05
Default      -> 1.0
```

#### 3.10.2 ResourceNodeDefinition

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `resource_id` | `str` | `ResourceId` | `string` | (required) |
| `name` | `str` | `Name` | `string` | (required) |
| `category` | `str` | `Category` | `string` | (required) |
| `tier` | `int` | `Tier` | `int` | (required) |
| `required_tool` | `str` | `RequiredTool` | `string` | (required) |
| `base_health` | `int` | `BaseHealth` | `int` | (required) |
| `drops` | `List[ResourceDrop]` | `Drops` | `List<ResourceDrop>` | `new()` |
| `respawn_time` | `Optional[str]` | `RespawnTime` | `string` | `null` |
| `tags` | `List[str]` | `Tags` | `List<string>` | `new()` |
| `narrative` | `str` | `Narrative` | `string` | `""` |

**Methods**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `get_respawn_seconds()` | `float? GetRespawnSeconds()` | Returns null if RespawnTime is null. Lookup map, default 60.0 |
| `does_respawn()` | `bool DoesRespawn()` | `RespawnTime != null` |

**Properties**:

| Property | C# Signature |
|----------|-------------|
| `is_tree` | `bool IsTree => Category == "tree"` |
| `is_ore` | `bool IsOre => Category == "ore"` |
| `is_stone` | `bool IsStone => Category == "stone"` |

**Critical Constants -- Respawn Map**:
```
"fast"      -> 30.0
"normal"    -> 60.0
"slow"      -> 120.0
"very_slow" -> 300.0
Default     -> 60.0
```

---

### 3.11 UnlockConditions (unlock_conditions.py -> UnlockConditions.cs)

**Source**: `Game-1-modular/data/models/unlock_conditions.py` (481 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/UnlockConditions.cs`
**Namespace**: `Game1.Data.Models`

This is the most architecturally complex file in Phase 1. It contains an abstract base class, 8 concrete implementations, a composite container, and a factory.

#### 3.11.1 UnlockCondition (Abstract Base)

```csharp
public abstract class UnlockCondition
{
    public abstract bool Evaluate(ICharacterState character);
    public abstract string GetDescription();
    public abstract Dictionary<string, object> ToDict();
}
```

**Important**: Python uses `TYPE_CHECKING` guard for `Character` import. In C#, define an `ICharacterState` interface that exposes only what conditions need:

```csharp
public interface ICharacterState
{
    int Level { get; }
    int Strength { get; }
    int Defense { get; }
    int Vitality { get; }
    int Luck { get; }
    int Agility { get; }
    int Intelligence { get; }
    int GetActivityCount(string activityType);
    bool HasTitle(string titleId);
    bool HasSkill(string skillId);
    bool IsQuestCompleted(string questId);
    string CurrentClassId { get; }
    // Stat tracker access (dot-notation path resolution)
    float GetStatTrackerValue(string statPath);
}
```

This interface lives in Phase 1 but is implemented by Character in Phase 3.

#### 3.11.2 Concrete Conditions (8 implementations)

| # | Class | Constructor Args | Evaluate Logic |
|---|-------|-----------------|----------------|
| 1 | `LevelCondition` | `int minLevel` | `character.Level >= minLevel` |
| 2 | `StatCondition` | `Dictionary<string, int> statRequirements` | Check each stat via mapping. Stats: strength, defense, vitality, luck, agility, intelligence |
| 3 | `ActivityCondition` | `string activityType, int minCount` | `character.GetActivityCount(activityType) >= minCount` |
| 4 | `StatTrackerCondition` | `string statPath, float minValue` | Dot-notation path resolution: split by `.`, navigate nested objects. In C#, delegate to `character.GetStatTrackerValue(statPath) >= minValue` |
| 5 | `TitleCondition` | `List<string> requiredTitles` | All titles must be earned |
| 6 | `SkillCondition` | `List<string> requiredSkills` | All skills must be known |
| 7 | `QuestCondition` | `List<string> requiredQuests` | All quests must be completed |
| 8 | `ClassCondition` | `string requiredClass` | Current class matches |

Each implementation has three methods: `Evaluate()`, `GetDescription()`, `ToDict()`.

**StatCondition Special Note**: The stat mapping in Python (lines 74-81) maps lowercase names to `character.stats.<stat>`. In C#, the `ICharacterState` interface directly exposes named properties.

**StatTrackerCondition Special Note**: Python navigates nested dictionaries/objects with dot notation (lines 146-171). This is complex runtime reflection. In C#, encapsulate this behind `ICharacterState.GetStatTrackerValue(string statPath)` and let the implementation handle the resolution. Phase 1 only defines the interface contract.

#### 3.11.3 UnlockRequirements (Composite)

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `conditions` | `List[UnlockCondition]` | `Conditions` | `List<UnlockCondition>` | `new()` |

**Methods**:

| Method | C# Signature | Logic |
|--------|-------------|-------|
| `evaluate(character)` | `bool Evaluate(ICharacterState character)` | `Conditions.All(c => c.Evaluate(character))` |
| `get_missing_conditions(character)` | `List<UnlockCondition> GetMissingConditions(ICharacterState character)` | Filter where `!Evaluate` |
| `get_description()` | `string GetDescription()` | Join with " AND " |
| `to_dict()` | `Dictionary<string, object> ToDict()` | Serialize conditions list |

#### 3.11.4 ConditionFactory

Two static methods:

**`create_from_json(data)`** -> `static UnlockCondition CreateFromJson(Dictionary<string, object> data)`

Must handle all 8 condition types by `"type"` field. Key mapping logic for `"stat"` type:
- New format: `{"type": "stat", "requirements": {"strength": 10}}`
- JSON format: `{"type": "stat", "stat_name": "STR", "min_value": 5}`
- Stat abbreviation mapping: str->strength, def->defense, vit->vitality, lck->luck, agi->agility, int->intelligence

**`create_requirements_from_json(json_data)`** -> `static UnlockRequirements CreateRequirementsFromJson(Dictionary<string, object> jsonData)`

Must handle:
1. New format: `{"conditions": [...]}`
2. Legacy format: parse from top-level fields (`characterLevel`, `stats`, `titles`, `requiredTitles`, `completedQuests`, `activityMilestones`, `activities`)

**Legacy `activityMilestones` mapping** (lines 431-460):
```
"craft_count" -> StatTrackerCondition("crafting_by_discipline.{discipline}.total_crafts", count)
"kill_count"  -> StatTrackerCondition("combat_kills.total_kills", count)
"gather_count"-> ActivityCondition("mining", count//2) + ActivityCondition("forestry", count//2)
```

**Legacy `activities` key mapping** (lines 466-476):
```
oresMined         -> mining
treesChopped      -> forestry
itemsSmithed      -> smithing
materialsRefined  -> refining
potionsBrewed     -> alchemy
itemsEnchanted    -> enchanting
devicesCreated    -> engineering
enemiesDefeated   -> combat
bossesDefeated    -> combat
```

---

### 3.12 SkillUnlocks (skill_unlocks.py -> SkillUnlocks.cs)

**Source**: `Game-1-modular/data/models/skill_unlocks.py` (182 lines)
**Target**: `Assets/Scripts/Game1.Data/Models/SkillUnlocks.cs`
**Namespace**: `Game1.Data.Models`

#### 3.12.1 UnlockCost

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `gold` | `int` | `Gold` | `int` | `0` |
| `materials` | `List[Dict[str, Any]]` | `Materials` | `List<Dictionary<string, object>>` | `new()` |
| `skill_points` | `int` | `SkillPoints` | `int` | `0` |

**Methods**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `can_afford(character)` | `(bool CanAfford, string Reason) CanAfford(ICharacterEconomy character)` | Check gold, materials, skill points. Uses `hasattr` in Python -- in C# use interface. |
| `pay(character)` | `bool Pay(ICharacterEconomy character)` | Deduct gold, remove materials, deduct skill points |

Define `ICharacterEconomy` interface for Phase 1:
```csharp
public interface ICharacterEconomy
{
    int Gold { get; set; }
    int SkillPoints { get; set; }
    bool HasItem(string materialId, int quantity);
    void RemoveItem(string materialId, int quantity);
}
```

#### 3.12.2 UnlockTrigger

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `type` | `str` | `Type` | `string` | (required) |
| `trigger_value` | `Any` | `TriggerValue` | `object` | (required) |
| `message` | `str` | `Message` | `string` | (required) |

Note: `type` is a reserved keyword consideration in C# -- but `Type` as a property name is valid (it shadows `System.Type`). Consider using `TriggerType` instead to avoid ambiguity.

#### 3.12.3 SkillUnlock

| Python Field | Python Type | C# Property | C# Type | Default |
|-------------|-------------|-------------|---------|---------|
| `unlock_id` | `str` | `UnlockId` | `string` | (required) |
| `skill_id` | `str` | `SkillId` | `string` | (required) |
| `unlock_method` | `str` | `UnlockMethod` | `string` | (required) |
| `requirements` | `UnlockRequirements` | `Requirements` | `UnlockRequirements` | (required) |
| `trigger` | `UnlockTrigger` | `Trigger` | `UnlockTrigger` | (required) |
| `cost` | `UnlockCost` | `Cost` | `UnlockCost` | (required) |
| `narrative` | `str` | `Narrative` | `string` | `""` |
| `category` | `str` | `Category` | `string` | `""` |

**`__post_init__` validation**: Throws `ValueError` if `unlock_id`, `skill_id`, or `unlock_method` are empty. In C#, do this in the constructor:
```csharp
public SkillUnlock(string unlockId, string skillId, string unlockMethod, ...)
{
    if (string.IsNullOrEmpty(unlockId)) throw new ArgumentException("unlockId is required");
    if (string.IsNullOrEmpty(skillId)) throw new ArgumentException("skillId is required");
    if (string.IsNullOrEmpty(unlockMethod)) throw new ArgumentException("unlockMethod is required");
    // ...
}
```

**Methods**:

| Method | C# Signature | Key Logic |
|--------|-------------|-----------|
| `check_conditions(character)` | `bool CheckConditions(ICharacterState character)` | Delegates to `Requirements.Evaluate(character)` |
| `check_cost(character)` | `(bool CanAfford, string Reason) CheckCost(ICharacterEconomy character)` | Delegates to `Cost.CanAfford(character)` |
| `can_unlock(character)` | `(bool CanUnlock, string Reason) CanUnlock(ICharacterState state, ICharacterEconomy economy)` | Check conditions + cost |
| `unlock(character)` | `(bool Success, string Message) Unlock(ICharacterState state, ICharacterEconomy economy, ISkillManager skills)` | Pay cost, add skill. Python uses `hasattr(character, 'skills')` -- in C#, pass `ISkillManager` explicitly |

---

### 3.13 AIState Enum (Combat/enemy.py -> Enums/AIState.cs)

**Source**: `Game-1-modular/Combat/enemy.py` (lines 21-30)
**Target**: `Assets/Scripts/Game1.Data/Enums/AIState.cs`
**Namespace**: `Game1.Data.Enums`

```csharp
public enum AIState
{
    Idle,
    Wander,
    Patrol,
    Guard,
    Chase,
    Attack,
    Flee,
    Dead,
    Corpse
}
```

With corresponding `AIStateExtensions` class for JSON string conversion:
```
"idle", "wander", "patrol", "guard", "chase", "attack", "flee", "dead", "corpse"
```

---

## 4. Quality Control Instructions

### 4.1 Pre-Migration Checklist

Complete these steps BEFORE writing any C# code:

- [ ] Read each of the 13 Python source files (`data/models/*.py`) completely
- [ ] Read `Combat/enemy.py` lines 21-30 for AIState enum
- [ ] Document every field: name, type, default value, and any constraints
- [ ] Identify all dynamic imports and plan interface/DI alternatives:
  - `equipment.py:59` imports `core.config.Config` (for colors)
  - `equipment.py:233` imports `core.crafting_tag_processor.EnchantingTagProcessor`
  - `skills.py:84` imports `data.databases.skill_db.SkillDatabase`
  - `world.py:59` imports `core.config.Config` (for colors)
  - `world.py:143` imports `data.databases.resource_node_db.ResourceNodeDatabase`
  - `unlock_conditions.py:11` uses `TYPE_CHECKING` guard for `Character`
- [ ] List all magic numbers and constants (see Section 3 for complete inventory)
- [ ] Identify all Python-specific patterns that need C# alternatives:
  - `@dataclass` -> class with properties
  - `field(default_factory=...)` -> property initializer or constructor
  - `__post_init__` -> constructor body
  - `Optional[T]` -> nullable types
  - `Union[T1, T2]` -> see Section 6 (Pitfalls)
  - `ABC` / `@abstractmethod` -> `abstract class` / `abstract` methods
  - `Tuple[int, int]` -> value tuples `(int, int)`
  - Python `Set[str]` -> `HashSet<string>`

### 4.2 Per-File QC Checklist

Apply this checklist to EVERY C# file produced:

- [ ] Every Python field has a corresponding C# property with correct type
- [ ] Default values match exactly:
  - `None` -> `null`
  - `[]` -> `new List<T>()`
  - `{}` -> `new Dictionary<K,V>()`
  - `set()` -> `new HashSet<T>()`
  - `""` -> `""`
  - `False` -> `false`
  - `True` -> `true`
  - Numeric defaults preserved exactly (e.g., `100.0` not `100`, `1.0f` not `1`)
- [ ] All methods ported with identical logic (not just signature)
- [ ] No fields lost or renamed without explicit documentation in this plan
- [ ] Naming convention applied: `snake_case` -> `PascalCase` for properties and methods
- [ ] XML documentation comments on all public members
- [ ] File header comment block includes:
  ```csharp
  /// <summary>
  /// Migrated from: data/models/{filename}.py
  /// Migration date: YYYY-MM-DD
  /// Original lines: X-Y
  /// </summary>
  ```
- [ ] `[Serializable]` attribute on all classes that will be serialized to/from JSON
- [ ] No `using` statements for types not yet migrated (stub interfaces instead)
- [ ] All collection properties use concrete `List<T>` / `Dictionary<K,V>` (not `IList<T>` / `IDictionary<K,V>`) for JSON serialization compatibility

### 4.3 Post-Migration Validation

#### 4.3.1 Compilation

- [ ] All C# files compile without errors in the Unity project
- [ ] No compiler warnings (treat warnings as errors)
- [ ] No ambiguous references or namespace conflicts

#### 4.3.2 Behavioral Correctness

Test each of these exact scenarios:

**Position.DistanceTo()**:
- `Position(0,0,0).DistanceTo(Position(3,4,0))` must equal `5.0`
- `Position(1,1,1).DistanceTo(Position(1,1,1))` must equal `0.0`
- `Position(-1,-1,0).DistanceTo(Position(2,3,0))` must equal `5.0`

**Position.SnapToGrid()**:
- `Position(1.5, 2.7, 0).SnapToGrid()` must equal `Position(1, 2, 0)`
- `Position(-0.5, -0.1, 0).SnapToGrid()` must equal `Position(-1, -1, 0)` -- **CRITICAL: Floor behavior**
- `Position(-1.0, 0.0, 0).SnapToGrid()` must equal `Position(-1, 0, 0)`
- `Position(0.0, 0.0, 0).SnapToGrid()` must equal `Position(0, 0, 0)`

**Position.ToKey()**:
- `Position(1.5, 2.7, 0).ToKey()` must equal `"1,2,0"`
- `Position(-0.5, -0.1, 0).ToKey()` must equal `"-1,-1,0"`

**EquipmentItem.GetEffectiveness()**:
- durability 100/100 -> `1.0`
- durability 50/100 -> `1.0`
- durability 49/100 -> `0.995`
- durability 25/100 -> `0.875`
- durability 1/100 -> `0.755`
- durability 0/100 -> `0.5` (caught by <= 0 check)

**ResourceDrop.GetQuantityRange()**:
- `"few"` -> `(1, 2)`
- `"several"` -> `(2, 4)`
- `"many"` -> `(3, 5)`
- `"abundant"` -> `(4, 8)`
- `"unknown_value"` -> `(1, 3)` (default)

**ResourceDrop.GetChanceValue()**:
- `"guaranteed"` -> `1.0`
- `"high"` -> `0.8`
- `"moderate"` -> `0.5`
- `"low"` -> `0.25`
- `"rare"` -> `0.1`
- `"improbable"` -> `0.05`
- `"unknown_value"` -> `1.0` (default)

**ResourceNodeDefinition.GetRespawnSeconds()**:
- `"fast"` -> `30.0`
- `"normal"` -> `60.0`
- `"slow"` -> `120.0`
- `"very_slow"` -> `300.0`
- `null` -> `null` (no respawn)
- `"unknown"` -> `60.0` (default)

**ClassDefinition.GetSkillAffinityBonus()**:
- 0 matching tags -> `0.0`
- 1 matching tag -> `0.05`
- 2 matching tags -> `0.10`
- 4 matching tags -> `0.20` (capped)
- 5 matching tags -> `0.20` (still capped)
- Case insensitive: tags `["Fire"]` and skillTags `["fire"]` -> `0.05`
- Null/empty inputs -> `0.0`

**PlayerSkill.GetExpForNextLevel()**:
- Level 1 -> 1000
- Level 2 -> 2000
- Level 3 -> 4000
- Level 5 -> 16000
- Level 9 -> 256000
- Level 10 -> 0 (max level)

**PlacedEntity barrier health by tier**:
- Tier 1 BARRIER -> health 50.0
- Tier 2 BARRIER -> health 100.0
- Tier 3 BARRIER -> health 200.0
- Tier 4 BARRIER -> health 400.0
- Tier 5 BARRIER -> health 50.0 (default, unknown tier)
- Tier 1 TURRET -> health 100.0 (default, non-barrier)

**ConditionFactory.CreateFromJson()**:
- `{"type": "level", "min_level": 5}` -> `LevelCondition(5)`
- `{"type": "stat", "requirements": {"strength": 10}}` -> `StatCondition({"strength": 10})`
- `{"type": "stat", "stat_name": "STR", "min_value": 5}` -> `StatCondition({"strength": 5})`
- `{"type": "activity", "activity": "mining", "min_count": 100}` -> `ActivityCondition("mining", 100)`
- `{"type": "title", "required_titles": ["master_smith"]}` -> `TitleCondition(["master_smith"])`
- `{"type": "title", "required_title": "novice_miner"}` -> `TitleCondition(["novice_miner"])`
- `{"type": "unknown_type"}` -> `null`

**EquipmentItem enchantment family/tier parsing**:
- `"sharpness_3"` -> family `"sharpness"`, tier `3`
- `"fire_aspect"` -> family `"fire_aspect"`, tier `1` (no trailing digit)
- `"protection_1"` -> family `"protection"`, tier `1`
- `"lifesteal"` -> family `"lifesteal"`, tier `1`

### 4.4 Phase 1 Quality Gate

All of the following must be true before Phase 1 is considered complete:

- [ ] All 27+ data model classes compile without errors
- [ ] All 7 enums defined with correct string backing values
- [ ] All 3 interface stubs (`ICharacterState`, `ICharacterEconomy`, `ISkillManager`) defined
- [ ] 100% unit test coverage on all model classes
- [ ] JSON deserialization works for all model types (using Newtonsoft.Json or System.Text.Json)
- [ ] No compiler warnings in any Phase 1 file
- [ ] All enum string conversions roundtrip correctly (enum -> string -> enum)
- [ ] All constant dictionaries (`RESOURCE_TIERS`, `DUNGEON_CONFIG`, `BARRIER_HEALTH_BY_TIER`) match Python values exactly
- [ ] Code review completed by a second developer
- [ ] All test assertions in Section 4.3.2 pass

---

## 5. Testing Requirements

### 5.1 Minimum Test Count

| Category | Minimum Tests | Covers |
|----------|--------------|--------|
| MaterialDefinition | 2 | Construction with defaults, construction with all fields |
| EquipmentItem | 8 | Construction, GetEffectiveness (4 cases), GetActualDamage, CanEquip, ApplyEnchantment, Copy |
| SkillEffect | 1 | Construction with post_init default |
| SkillCost | 2 | String value, numeric value |
| SkillDefinition | 1 | Construction with all sub-objects |
| PlayerSkill | 5 | GetExpForNextLevel, AddExp (single/multi level), CanUse, UpdateCooldown |
| Recipe | 1 | Construction with defaults |
| PlacementData | 1 | Construction with defaults |
| Position | 5 | DistanceTo, SnapToGrid (positive/negative), ToKey, Copy |
| WorldTile | 1 | Construction with defaults |
| LootDrop | 1 | Construction |
| CraftingStation | 1 | GetColor |
| PlacedEntity | 4 | Construction, barrier health, TakeDamage, ApplyCraftedStats |
| DungeonEntrance | 1 | GetRarityColor |
| ClassDefinition | 3 | HasTag, GetSkillAffinityBonus (matching, capped, empty) |
| TitleDefinition | 1 | Construction with UnlockRequirements |
| NPCDefinition | 1 | Construction |
| QuestObjective | 1 | Construction with defaults |
| QuestRewards | 1 | Construction with defaults |
| QuestDefinition | 1 | Construction |
| ResourceDrop | 3 | GetQuantityRange, GetChanceValue (known + unknown values) |
| ResourceNodeDefinition | 3 | GetRespawnSeconds (known, null, unknown), DoesRespawn, IsTree/IsOre/IsStone |
| UnlockConditions | 9 | One per condition type (8) + UnlockRequirements.Evaluate |
| ConditionFactory | 6 | CreateFromJson for each type + legacy format + unknown type |
| UnlockCost | 2 | CanAfford, Pay |
| SkillUnlock | 3 | Validation, CanUnlock, Unlock |
| Enums | 7 | One per enum: all values + string conversion |
| Constants | 3 | ResourceTiers, DungeonConfig, BarrierHealth value verification |
| **TOTAL** | **77+** | |

### 5.2 Test Categories

**Construction Tests**: Verify that every class can be instantiated with both minimal (required-only) and maximal (all fields) parameters, and that defaults are correct.

**Serialization Roundtrip Tests**: For every model, serialize to JSON and deserialize back, verifying all fields survive the roundtrip.

**Behavioral Tests**: For every method, verify correct output for edge cases and typical cases. See Section 4.3.2 for exact test values.

**Enum Tests**: For every enum, verify:
- All expected members exist
- `ToJsonString()` returns correct lowercase string
- `FromJsonString()` returns correct enum value
- Unknown strings return a sensible default

**Factory Tests**: For `ConditionFactory`, verify creation of all 8 condition types from both new and legacy JSON formats.

### 5.3 Test File Locations

```
Assets/Tests/Game1.Data/
  Models/
    MaterialDefinitionTests.cs
    EquipmentItemTests.cs
    SkillsTests.cs
    RecipesTests.cs
    WorldTests.cs
    ClassDefinitionTests.cs
    TitleDefinitionTests.cs
    NPCDefinitionTests.cs
    QuestsTests.cs
    ResourcesTests.cs
    UnlockConditionsTests.cs
    SkillUnlocksTests.cs
  Enums/
    EnumConversionTests.cs
  Constants/
    ConstantDataTests.cs
```

---

## 6. Common Pitfalls

### 6.1 Python `field(default_factory=list)` vs C# field initializers

**Python**:
```python
tags: List[str] = field(default_factory=list)
```

**Correct C#**:
```csharp
public List<string> Tags { get; set; } = new();
```

**WRONG C#** (shared reference):
```csharp
// DO NOT DO THIS -- static field shared across all instances
private static readonly List<string> _defaultTags = new();
public List<string> Tags { get; set; } = _defaultTags;
```

Each instance MUST get its own collection instance. The `= new()` initializer in C# creates a new instance per object, which is correct.

### 6.2 Python `Optional[T]` vs C# nullable types

**Value types** (int, float, bool):
- `Optional[int]` -> `int?`
- `Optional[float]` -> `float?`

**Reference types** (string, class):
- `Optional[str]` -> `string` (already nullable in C# by default)
- With nullable reference types enabled (`#nullable enable`), use `string?` for explicit intent

### 6.3 Python `Dict[str, Any]` -- loss of type safety

`Any` in Python means truly any type. `Dictionary<string, object>` in C# loses compile-time type safety and requires casting on retrieval. Mitigation strategies:

- For known schemas (e.g., enchantment effects): create typed classes
- For unknown/extensible schemas (e.g., `effect_params`): keep `Dictionary<string, object>` but add typed helper methods
- Use `JsonElement` or `JToken` (Newtonsoft) for deferred parsing

### 6.4 Python `Union[str, int, float]` (SkillCost)

C# has no native union type. Options:

1. **`object` with helpers** (recommended for Phase 1):
   ```csharp
   public object Mana { get; set; }
   public float GetManaAsFloat() => Mana switch {
       float f => f,
       int i => (float)i,
       string s => float.TryParse(s, out var v) ? v : 0f,
       _ => 0f
   };
   ```

2. **Discriminated union record** (cleaner, more complex):
   ```csharp
   public record SkillCostValue
   {
       public string Qualitative { get; init; }
       public float? Numeric { get; init; }
       public bool IsNumeric => Numeric.HasValue;
   }
   ```

### 6.5 Python `math.floor()` vs C# integer cast

**CRITICAL DIFFERENCE**:
```python
math.floor(-0.5)  # Returns -1
```
```csharp
(int)(-0.5f)      // Returns 0 (truncation toward zero!)
MathF.Floor(-0.5f) // Returns -1.0f (correct equivalent)
```

All uses of `math.floor` in Python MUST use `MathF.Floor()` in C#, not integer casting. This affects:
- `Position.SnapToGrid()`
- `Position.ToKey()`

### 6.6 Python enum string values

Python enums with string values:
```python
class TileType(Enum):
    GRASS = "grass"
```

C# enums are numeric by default. String backing requires explicit conversion utilities (see Section 3.5.7 for the recommended pattern with extension methods and lookup dictionaries).

Do NOT use `[EnumMember(Value = "grass")]` as the primary mechanism -- it requires `DataContractSerializer` and does not work with all JSON libraries. The extension method pattern is more portable.

### 6.7 Python `@dataclass` equality vs C# reference equality

Python `@dataclass` generates `__eq__` based on field values. C# classes use reference equality by default.

For models that are used as dictionary keys or in sets (e.g., `Position`), implement `IEquatable<T>` and override `Equals()` and `GetHashCode()`:

```csharp
public class Position : IEquatable<Position>
{
    public bool Equals(Position other) =>
        other != null && X == other.X && Y == other.Y && Z == other.Z;

    public override bool Equals(object obj) => Equals(obj as Position);

    public override int GetHashCode() => HashCode.Combine(X, Y, Z);
}
```

For models that are NOT used as keys (most of them), reference equality is acceptable.

### 6.8 Python `Set[str]` vs C# `HashSet<string>`

Python `set()` -> C# `HashSet<string>`. The `PlacedEntity.visual_effects` field uses `Set[str]` in Python. Use `HashSet<string>` in C#. JSON serializers typically handle `HashSet<T>` as arrays.

### 6.9 Python integer division `//`

In `unlock_conditions.py:456-459`, Python uses `count // 2` for integer division. In C#, `count / 2` is already integer division when both operands are `int`. This is safe.

### 6.10 Python `hasattr()` checks

Several methods use `hasattr(character, 'gold')` etc. This is defensive Python coding against incomplete objects. In C#, the interface contract guarantees the property exists. Remove `hasattr` checks and rely on the interface. If the property is truly optional, make it nullable in the interface.

### 6.11 Python `getattr(obj, name, default)` for dynamic attribute access

`StatCondition.evaluate()` uses `getattr(character.stats, stat_name, 0)`. In C#, this is replaced by explicit property access via the `ICharacterState` interface, or by a `Dictionary<string, int>` lookup. The interface approach is preferred since the stat names are known at design time.

### 6.12 Type safety for enchantments list

`EquipmentItem.enchantments` is `List[Dict[str, Any]]` in Python -- effectively untyped. Consider creating a typed C# class in Phase 1:

```csharp
public class EnchantmentEntry
{
    public string EnchantmentId { get; set; }
    public string Name { get; set; }
    public Dictionary<string, object> Effect { get; set; } = new();
    public List<string> MetadataTags { get; set; } = new();
}
```

This is optional for Phase 1 but recommended for reducing casting errors in later phases. If deferred, add a TODO comment in the EquipmentItem file.

---

## 7. Intra-Phase Dependency Order

Within Phase 1, files must be created in this order due to type references:

```
Step 1: Enums (no dependencies)
  - TileType.cs
  - ResourceType.cs
  - ChunkType.cs
  - StationType.cs
  - PlacedEntityType.cs
  - DungeonRarity.cs
  - AIState.cs

Step 2: Interfaces (no dependencies)
  - ICharacterState.cs
  - ICharacterEconomy.cs
  - ISkillManager.cs (stub)
  - IEnchantmentValidator.cs (stub)
  - IColorConfig.cs (stub)

Step 3: Simple models (depend on enums only)
  - MaterialDefinition.cs
  - LootDrop (in World.cs)
  - Position (in World.cs)
  - QuestObjective, QuestRewards, QuestDefinition (Quests.cs)
  - ResourceDrop, ResourceNodeDefinition (Resources.cs)
  - SkillEffect, SkillCost, SkillEvolution, SkillRequirements (Skills.cs)
  - Recipe, PlacementData (Recipes.cs)

Step 4: Models with model dependencies
  - WorldTile (depends on Position, TileType)
  - CraftingStation (depends on Position, StationType)
  - PlacedEntity (depends on Position, PlacedEntityType)
  - DungeonEntrance (depends on Position, DungeonRarity)
  - NPCDefinition (depends on Position)
  - SkillDefinition (depends on SkillEffect, SkillCost, SkillEvolution, SkillRequirements)
  - PlayerSkill (depends on SkillDefinition reference)

Step 5: Unlock system (depends on interfaces)
  - UnlockCondition (abstract) + 8 implementations (UnlockConditions.cs)
  - UnlockRequirements (depends on UnlockCondition)
  - ConditionFactory (depends on all condition types)

Step 6: Models depending on unlock system
  - TitleDefinition (depends on UnlockRequirements)
  - UnlockCost, UnlockTrigger, SkillUnlock (depends on UnlockRequirements)

Step 7: Complex models
  - EquipmentItem (depends on interfaces)
  - ClassDefinition (no external deps but has methods)

Step 8: Constants
  - ResourceTiers.cs (depends on ResourceType enum)
  - DungeonConfig.cs (depends on DungeonRarity enum)
  - BarrierHealth.cs (standalone)
```

---

## 8. Estimated Effort

| Task Group | Files | Estimated Hours | Complexity |
|------------|-------|----------------|------------|
| Enums (7 files) | 7 | 2-3 | Low |
| Interface stubs (5 files) | 5 | 1-2 | Low |
| Simple models (MaterialDefinition, Quests, Resources, Recipes) | 4 | 3-4 | Low |
| Medium models (Skills, World data classes, ClassDefinition, NPCDefinition, TitleDefinition) | 5 | 4-6 | Medium |
| Complex models (EquipmentItem, PlacedEntity, UnlockConditions, SkillUnlocks) | 4 | 8-12 | High |
| Constants (3 files) | 3 | 1-2 | Low |
| Unit tests (77+ tests) | 14 | 8-12 | Medium |
| Code review and fixes | -- | 2-4 | -- |
| **TOTAL** | **42** | **29-45 hours** | |

---

## 9. Acceptance Criteria Summary

Phase 1 is DONE when:

1. All 7 enums compile and support bidirectional string conversion
2. All 27+ model classes compile with correct field types and defaults
3. All methods produce identical output to their Python equivalents for all test cases in Section 4.3.2
4. All 5 interface stubs are defined for cross-phase contracts
5. All 3 constant dictionaries match Python values exactly
6. 77+ unit tests pass with 100% model coverage
7. JSON serialization roundtrip succeeds for every model type
8. Zero compiler warnings
9. Code review completed

No gameplay, no rendering, no database loading, no save/load. Just pure data types that compile and pass tests.

---

## Appendix A: Complete ResourceType Enum Values (47 entries)

```
# Trees (8)
OAK_TREE = "oak_tree"
PINE_TREE = "pine_tree"
ASH_TREE = "ash_tree"
BIRCH_TREE = "birch_tree"
MAPLE_TREE = "maple_tree"
IRONWOOD_TREE = "ironwood_tree"
EBONY_TREE = "ebony_tree"
WORLDTREE_SAPLING = "worldtree_sapling"

# Ores (8)
COPPER_VEIN = "copper_vein"
IRON_DEPOSIT = "iron_deposit"
TIN_SEAM = "tin_seam"
STEEL_NODE = "steel_node"
MITHRIL_CACHE = "mithril_cache"
ADAMANTINE_LODE = "adamantine_lode"
ORICHALCUM_TROVE = "orichalcum_trove"
ETHERION_NEXUS = "etherion_nexus"

# Stones (12)
LIMESTONE_OUTCROP = "limestone_outcrop"
GRANITE_FORMATION = "granite_formation"
SHALE_BED = "shale_bed"
BASALT_COLUMN = "basalt_column"
MARBLE_QUARRY = "marble_quarry"
QUARTZ_CLUSTER = "quartz_cluster"
OBSIDIAN_FLOW = "obsidian_flow"
VOIDSTONE_SHARD = "voidstone_shard"
DIAMOND_GEODE = "diamond_geode"
ETERNITY_MONOLITH = "eternity_monolith"
PRIMORDIAL_FORMATION = "primordial_formation"
GENESIS_STRUCTURE = "genesis_structure"

# Legacy Aliases (8) -- same values as above, map to canonical entries
COPPER_ORE = "copper_vein"
IRON_ORE = "iron_deposit"
STEEL_ORE = "steel_node"
MITHRIL_ORE = "mithril_cache"
LIMESTONE = "limestone_outcrop"
GRANITE = "granite_formation"
OBSIDIAN = "obsidian_flow"
STAR_CRYSTAL = "diamond_geode"

# Water (1 generic + 12 tiered)
FISHING_SPOT = "fishing_spot"
FISHING_SPOT_CARP = "fishing_spot_carp"
FISHING_SPOT_SUNFISH = "fishing_spot_sunfish"
FISHING_SPOT_MINNOW = "fishing_spot_minnow"
FISHING_SPOT_STORMFIN = "fishing_spot_stormfin"
FISHING_SPOT_FROSTBACK = "fishing_spot_frostback"
FISHING_SPOT_LIGHTEYE = "fishing_spot_lighteye"
FISHING_SPOT_SHADOWGILL = "fishing_spot_shadowgill"
FISHING_SPOT_PHOENIXKOI = "fishing_spot_phoenixkoi"
FISHING_SPOT_VOIDSWIMMER = "fishing_spot_voidswimmer"
FISHING_SPOT_TEMPESTEEL = "fishing_spot_tempesteel"
FISHING_SPOT_LEVIATHAN = "fishing_spot_leviathan"
FISHING_SPOT_CHAOSSCALE = "fishing_spot_chaosscale"
```

---

## Appendix B: Complete RESOURCE_TIERS Mapping (45 entries)

```
# Trees
OAK_TREE: 1, PINE_TREE: 1, ASH_TREE: 1
BIRCH_TREE: 2, MAPLE_TREE: 2
IRONWOOD_TREE: 3, EBONY_TREE: 3
WORLDTREE_SAPLING: 4

# Ores
COPPER_VEIN: 1, IRON_DEPOSIT: 1, TIN_SEAM: 1
STEEL_NODE: 2, MITHRIL_CACHE: 2
ADAMANTINE_LODE: 3, ORICHALCUM_TROVE: 3
ETHERION_NEXUS: 4

# Stones
LIMESTONE_OUTCROP: 1, GRANITE_FORMATION: 1, SHALE_BED: 1
BASALT_COLUMN: 2, MARBLE_QUARRY: 2, QUARTZ_CLUSTER: 2
OBSIDIAN_FLOW: 3, VOIDSTONE_SHARD: 3, DIAMOND_GEODE: 3
ETERNITY_MONOLITH: 4, PRIMORDIAL_FORMATION: 4, GENESIS_STRUCTURE: 4

# Legacy Aliases
COPPER_ORE: 1, IRON_ORE: 1
STEEL_ORE: 2, MITHRIL_ORE: 2
LIMESTONE: 1, GRANITE: 1
OBSIDIAN: 3, STAR_CRYSTAL: 3

# Fishing
FISHING_SPOT: 1
FISHING_SPOT_CARP: 1, FISHING_SPOT_SUNFISH: 1, FISHING_SPOT_MINNOW: 1
FISHING_SPOT_STORMFIN: 2, FISHING_SPOT_FROSTBACK: 2, FISHING_SPOT_LIGHTEYE: 2, FISHING_SPOT_SHADOWGILL: 2
FISHING_SPOT_PHOENIXKOI: 3, FISHING_SPOT_VOIDSWIMMER: 3, FISHING_SPOT_TEMPESTEEL: 3
FISHING_SPOT_LEVIATHAN: 4, FISHING_SPOT_CHAOSSCALE: 4
```

---

## Appendix C: Interface Stubs for Cross-Phase Contracts

These interfaces are defined in Phase 1 but implemented in later phases. They exist to break circular dependencies.

```csharp
// ICharacterState.cs -- implemented by Character in Phase 3
namespace Game1.Data.Models
{
    public interface ICharacterState
    {
        int Level { get; }
        int Strength { get; }
        int Defense { get; }
        int Vitality { get; }
        int Luck { get; }
        int Agility { get; }
        int Intelligence { get; }
        int GetActivityCount(string activityType);
        bool HasTitle(string titleId);
        bool HasSkill(string skillId);
        bool IsQuestCompleted(string questId);
        string CurrentClassId { get; }
        float GetStatTrackerValue(string statPath);
    }
}

// ICharacterEconomy.cs -- implemented by Character in Phase 3
namespace Game1.Data.Models
{
    public interface ICharacterEconomy
    {
        int Gold { get; set; }
        int SkillPoints { get; set; }
        bool HasItem(string materialId, int quantity);
        void RemoveItem(string materialId, int quantity);
    }
}

// ISkillManager.cs -- implemented by SkillManager in Phase 3
namespace Game1.Data.Models
{
    public interface ISkillManager
    {
        bool UnlockSkill(string skillId);
    }
}

// IEnchantmentValidator.cs -- implemented by EnchantingTagProcessor in Phase 5
namespace Game1.Data.Models
{
    public interface IEnchantmentValidator
    {
        (bool CanApply, string Reason) CanApplyToItem(List<string> tags, string itemType);
    }
}

// IColorConfig.cs -- implemented by game config in Phase 2
namespace Game1.Data.Models
{
    public interface IColorConfig
    {
        (int R, int G, int B) ColorGrass { get; }
        (int R, int G, int B) ColorStone { get; }
        (int R, int G, int B) ColorWater { get; }
    }
}
```

---

## 3D Readiness (Phase 1 Responsibilities)

Phase 1 establishes the foundational types that ALL subsequent phases use for positions, distances, and item identity. Getting these right means 3D is a configuration change, not a rewrite.

### GamePosition Struct (NEW — not in Python)

Python uses `Position(x, y)`. C# must use a 3D-ready position:

```csharp
public struct GamePosition
{
    public float X { get; set; }  // East-West (maps to Python x)
    public float Y { get; set; }  // Height (default 0, future: terrain elevation)
    public float Z { get; set; }  // North-South (maps to Python y)

    public float HorizontalDistanceTo(GamePosition other)
        => Mathf.Sqrt((X - other.X) * (X - other.X) + (Z - other.Z) * (Z - other.Z));

    public float DistanceTo(GamePosition other)
        => Vector3.Distance(ToVector3(), other.ToVector3());

    public Vector3 ToVector3() => new Vector3(X, Y, Z);
    public static GamePosition FromXZ(float x, float z) => new() { X = x, Y = 0, Z = z };
}
```

**CRITICAL**: Python's `y` maps to Unity's `z` (north-south). `FromXZ()` ensures Python `(x, y)` becomes `(x, 0, y)` in Unity.

### IGameItem Interface + Type Hierarchy (NEW — see IMPROVEMENTS.md Part 4)

Phase 1 defines `IGameItem` interface and concrete types (`MaterialItem`, `EquipmentItem`, `ConsumableItem`, `PlaceableItem`, `ItemFactory`). Replaces dict-based items with type-safe polymorphism.

---

**End of Phase 1 Foundation Plan**
**Document version**: 1.1
**Created**: 2026-02-10
**Updated**: 2026-02-11 (3D readiness, IGameItem hierarchy)
