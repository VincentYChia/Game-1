# Phase 4: Game Systems -- Combat, Crafting, World, Tags, Effects, Save/Load

**Phase**: 4 of N
**Status**: Not Started
**Dependencies**: Phase 3 (Entity Layer -- Character, Inventory, Equipment, Skills must compile)
**Estimated C# Files**: 35-45
**Estimated C# Lines**: ~15,000-18,000
**Source Python Lines**: ~17,505 across 28 files

---

## 1. Overview

### 1.1 Goal

Port all core gameplay systems from Python to C#/Unity. This is the largest and most critical phase, covering every system that drives gameplay: the tag-based effect pipeline, combat damage calculations, all five crafting minigames with their mathematical formulas, world generation with chunk streaming, pathfinding, collision, and the full save/load system. Gameplay correctness depends on exact formula reproduction -- every constant, every multiplier, every clamp must match the Python source within floating-point tolerance.

### 1.2 Why This Phase Is Fourth

Every system in this phase depends on the data models (Phase 1), database singletons (Phase 2), and entity components (Phase 3):
- CombatManager references Character, Equipment, Enemy, Position
- Crafting minigames consume Recipes, Materials from databases
- WorldSystem generates chunks populated with data model types
- SaveManager serializes every entity and system from prior phases
- Tag/Effect systems operate on Character and Enemy entities

### 1.3 Dependencies

**Incoming (must be complete)**:
- Phase 1: All data models, enums, dataclasses
- Phase 2: All database singletons (MaterialDB, RecipeDB, SkillDB, EnemyDB, TitleDB, ClassDB)
- Phase 3: Character, Inventory, Equipment, SkillManager, Buffs, Leveling, Stats

**Outgoing (depend on Phase 4)**:
- Phase 5 (Rendering/UI): Reads from CombatManager, WorldSystem, crafting state
- Phase 6 (LLM/ML Integration): Uses crafting systems, recipe databases
- Phase 7 (Game Engine): Orchestrates all Phase 4 systems in main loop

### 1.4 Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| C# system files | 35-45 | One or more per Python source file |
| Unit test files | 30+ | Formula verification, pipeline tests, roundtrip tests |
| Integration tests | 10+ | Cross-system interaction tests |

### 1.5 Target Project Structure

```
Assets/Scripts/
  Game1.Systems/
    Tags/
      TagRegistry.cs
      TagParser.cs
      EffectContext.cs
      EffectConfig.cs
    Effects/
      EffectExecutor.cs
      TargetFinder.cs
      MathUtils.cs
    Combat/
      CombatConfig.cs
      CombatManager.cs
      DamageCalculator.cs        (extracted from CombatManager)
      EnemySpawner.cs            (extracted from CombatManager)
      AttackEffects.cs
      TurretSystem.cs
    Crafting/
      SmithingMinigame.cs
      AlchemyMinigame.cs
      RefiningMinigame.cs
      EngineeringMinigame.cs
      EnchantingMinigame.cs
      DifficultyCalculator.cs
      RewardCalculator.cs
      InteractiveCrafting.cs
    World/
      WorldSystem.cs
      BiomeGenerator.cs
      Chunk.cs
      CollisionSystem.cs
      NaturalResource.cs
      DungeonSystem.cs
    Progression/
      TitleSystem.cs
      ClassSystem.cs
      QuestSystem.cs
      SkillUnlockSystem.cs
    Items/
      PotionSystem.cs
    Save/
      SaveManager.cs
```

### 1.6 Migration Order (Within Phase 4)

Systems must be ported in dependency order:

1. **Tag System** (no gameplay dependencies, pure data lookup)
2. **Geometry / Math Utils** (pure math, no dependencies)
3. **Effect Executor** (depends on Tags + Geometry)
4. **Difficulty & Reward Calculators** (pure math)
5. **Crafting Minigames** (depends on Calculators)
6. **Collision System** (depends on World models)
7. **World System + Biome + Chunk + NaturalResource** (depends on Collision)
8. **Combat System** (depends on Effects, World, Entities)
9. **Support Systems** (Dungeon, Quest, Title, Class, Potion, Turret, SkillUnlock)
10. **Save/Load** (depends on everything above)
11. **Attack Effects** (visual feedback, lightweight)

---

## 2. System-by-System File Inventory

### 2.1 Tag System (3 files, 439 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `core/tag_system.py` | `Game1.Systems.Tags/TagRegistry.cs` | 192 | Medium |
| `core/tag_parser.py` | `Game1.Systems.Tags/TagParser.cs` | 191 | Medium |
| `core/effect_context.py` | `Game1.Systems.Tags/EffectConfig.cs` + `EffectContext.cs` | 56 | Low |

### 2.2 Effect Execution (3 files, ~935 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `core/effect_executor.py` | `Game1.Systems.Effects/EffectExecutor.cs` | 623 | High |
| `core/geometry/target_finder.py` | `Game1.Systems.Effects/TargetFinder.cs` | ~200 | Medium |
| `core/geometry/math_utils.py` | `Game1.Systems.Effects/MathUtils.cs` | 112 | Low |

### 2.3 Combat System (1 file -> 3 C# files, 2,009 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `Combat/combat_manager.py` | `Game1.Systems.Combat/CombatManager.cs` | 2,009 | Very High |
| (extracted) | `Game1.Systems.Combat/DamageCalculator.cs` | -- | High |
| (extracted) | `Game1.Systems.Combat/EnemySpawner.cs` | -- | Medium |

### 2.4 Crafting System (8 files, 6,111 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `Crafting-subdisciplines/smithing.py` | `Game1.Systems.Crafting/SmithingMinigame.cs` | 909 | High |
| `Crafting-subdisciplines/alchemy.py` | `Game1.Systems.Crafting/AlchemyMinigame.cs` | 1,070 | High |
| `Crafting-subdisciplines/refining.py` | `Game1.Systems.Crafting/RefiningMinigame.cs` | 826 | Medium |
| `Crafting-subdisciplines/engineering.py` | `Game1.Systems.Crafting/EngineeringMinigame.cs` | 1,312 | High |
| `Crafting-subdisciplines/enchanting.py` | `Game1.Systems.Crafting/EnchantingMinigame.cs` | 1,408 | High |
| `core/difficulty_calculator.py` | `Game1.Systems.Crafting/DifficultyCalculator.cs` | 808 | Medium |
| `core/reward_calculator.py` | `Game1.Systems.Crafting/RewardCalculator.cs` | 607 | Medium |
| `core/interactive_crafting.py` | `Game1.Systems.Crafting/InteractiveCrafting.cs` | 1,179 | Medium |

### 2.5 World System (5 files, 3,055 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `systems/world_system.py` | `Game1.Systems.World/WorldSystem.cs` | 1,110 | High |
| `systems/biome_generator.py` | `Game1.Systems.World/BiomeGenerator.cs` | 596 | Medium |
| `systems/chunk.py` | `Game1.Systems.World/Chunk.cs` | 558 | Medium |
| `systems/collision_system.py` | `Game1.Systems.World/CollisionSystem.cs` | 599 | High |
| `systems/natural_resource.py` | `Game1.Systems.World/NaturalResource.cs` | 191 | Low |

### 2.6 Save/Load (1 file, 634 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `systems/save_manager.py` | `Game1.Systems.Save/SaveManager.cs` | 634 | High |

### 2.7 Support Systems (8 files, 2,321 lines)

| Source File | C# Target | Lines | Complexity |
|---|---|---|---|
| `systems/dungeon.py` | `Game1.Systems.World/DungeonSystem.cs` | 805 | High |
| `systems/quest_system.py` | `Game1.Systems.Progression/QuestSystem.cs` | 292 | Medium |
| `systems/title_system.py` | `Game1.Systems.Progression/TitleSystem.cs` | 86 | Low |
| `systems/class_system.py` | `Game1.Systems.Progression/ClassSystem.cs` | 69 | Low |
| `systems/skill_unlock_system.py` | `Game1.Systems.Progression/SkillUnlockSystem.cs` | 205 | Medium |
| `systems/potion_system.py` | `Game1.Systems.Items/PotionSystem.cs` | 386 | Medium |
| `systems/turret_system.py` | `Game1.Systems.Combat/TurretSystem.cs` | 551 | Medium |
| `systems/attack_effects.py` | `Game1.Systems.Combat/AttackEffects.cs` | 233 | Low |

---

## 3. Detailed Migration Instructions

### 3.1 Tag System

#### 3.1.1 EffectConfig.cs + EffectContext.cs (from `core/effect_context.py`, 56 lines)

**Python dataclasses to C# classes:**

```csharp
// EffectConfig.cs
public class EffectConfig
{
    public List<string> RawTags { get; set; } = new();
    public string GeometryTag { get; set; }           // nullable
    public List<string> DamageTags { get; set; } = new();
    public List<string> StatusTags { get; set; } = new();
    public List<string> ContextTags { get; set; } = new();
    public List<string> SpecialTags { get; set; } = new();
    public List<string> TriggerTags { get; set; } = new();
    public string Context { get; set; } = "enemy";    // "ally", "enemy", "self", "all"
    public float BaseDamage { get; set; } = 0f;
    public float BaseHealing { get; set; } = 0f;
    public Dictionary<string, object> Params { get; set; } = new();
    public List<string> Warnings { get; set; } = new();
    public List<string> ConflictsResolved { get; set; } = new();
}

// EffectContext.cs
public class EffectContext
{
    public object Source { get; set; }                 // Entity that created the effect
    public object PrimaryTarget { get; set; }          // Primary target entity
    public EffectConfig Config { get; set; }
    public float Timestamp { get; set; } = 0f;
    public List<object> Targets { get; set; } = new(); // All targets after geometry
}
```

**Post-init logic**: If `Targets` is empty and `PrimaryTarget` is not null, initialize `Targets = new List<object> { PrimaryTarget }`.

#### 3.1.2 TagRegistry.cs (from `core/tag_system.py`, 192 lines)

**TagDefinition data class:**

```csharp
public class TagDefinition
{
    public string Name { get; set; }
    public string Category { get; set; }
    public string Description { get; set; }
    public int Priority { get; set; } = 0;
    public List<string> RequiresParams { get; set; } = new();
    public Dictionary<string, object> DefaultParams { get; set; } = new();
    public List<string> ConflictsWith { get; set; } = new();
    public List<string> Aliases { get; set; } = new();
    public string AliasOf { get; set; }               // nullable
    public string Stacking { get; set; }               // nullable
    public List<string> Immunity { get; set; } = new();
    public Dictionary<string, Dictionary<string, object>> Synergies { get; set; } = new();
    public Dictionary<string, object> ContextBehavior { get; set; } = new();
    public float AutoApplyChance { get; set; } = 0f;
    public string AutoApplyStatus { get; set; }        // nullable
    public string Parent { get; set; }                 // nullable
}
```

**TagRegistry singleton methods:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `get_instance()` | `public static TagRegistry Instance { get; }` | Thread-safe lazy singleton |
| `load()` | `public void Load()` | Loads `Definitions.JSON/tag-definitions.JSON` via `JsonConvert.DeserializeObject` |
| `resolve_alias(tag)` | `public string ResolveAlias(string tag)` | Lookup in `_aliases` dict, return tag if not found |
| `get_definition(tag)` | `public TagDefinition GetDefinition(string tag)` | Resolve alias first, then look up |
| `get_category(tag)` | `public string GetCategory(string tag)` | Returns `tag_def.Category` or null |
| `is_geometry_tag(tag)` | `public bool IsGeometryTag(string tag)` | Category == "geometry" |
| `is_damage_tag(tag)` | `public bool IsDamageTag(string tag)` | Category == "damage_type" |
| `is_status_tag(tag)` | `public bool IsStatusTag(string tag)` | Category in {"status_debuff", "status_buff"} |
| `is_context_tag(tag)` | `public bool IsContextTag(string tag)` | Category == "context" |
| `get_tags_by_category(cat)` | `public List<string> GetTagsByCategory(string category)` | Filter non-alias definitions |
| `resolve_geometry_conflict(tags)` | `public string ResolveGeometryConflict(List<string> tags)` | Use `_geometryPriority` order |
| `check_mutual_exclusion(t1,t2)` | `public bool CheckMutualExclusion(string t1, string t2)` | Resolve aliases first |
| `get_default_params(tag)` | `public Dictionary<string,object> GetDefaultParams(string tag)` | Returns copy of defaults |
| `merge_params(tag, user)` | `public Dictionary<string,object> MergeParams(string tag, Dictionary<string,object> userParams)` | Defaults overridden by user params |

**JSON loading**: Path is `Definitions.JSON/tag-definitions.JSON`. Structure has `categories`, `tag_definitions`, `conflict_resolution` (with `geometry_priority` and `mutually_exclusive`), and `context_inference`.

**Thread safety note**: TagRegistry is read-only after loading, so no locking needed for reads. Ensure `Load()` is called once at startup before any reads.

#### 3.1.3 TagParser.cs (from `core/tag_parser.py`, 191 lines)

**Methods:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `parse(tags, params)` | `public EffectConfig Parse(List<string> tags, Dictionary<string,object> effectParams)` | Main entry point |
| `_infer_context(...)` | `private string InferContext(...)` | Returns "enemy" or "ally" based on tag categories |
| `_merge_all_params(tags, user)` | `private Dictionary<string,object> MergeAllParams(...)` | Iterates all tags, collects defaults, then applies user overrides |
| `_apply_synergies(config)` | `private void ApplySynergies(EffectConfig config)` | Multiplicative bonus: `current * (1.0 + bonus)` for `_bonus` suffixed params |
| `_check_mutual_exclusions(config)` | `private void CheckMutualExclusions(EffectConfig config)` | Pairwise check across all categorized tags |

**Context inference logic** (exact from Python):
1. If explicit context tags exist, use the first one
2. If `baseDamage > 0` or debuff status tags present, return `"enemy"`
3. If `baseHealing > 0` or buff status tags present, return `"ally"`
4. Default: `"enemy"`

**Default geometry**: If no geometry tag found after categorization, default to `"single_target"`.

---

### 3.2 Effect Execution

#### 3.2.1 MathUtils.cs (from `core/geometry/math_utils.py`, 112 lines)

**Pure static utility class:**

```csharp
public static class MathUtils
{
    public static float Distance(Position a, Position b);
    public static (float dx, float dy) NormalizeVector(float dx, float dy);
    public static float DotProduct((float, float) v1, (float, float) v2);
    public static float AngleBetweenVectors((float, float) v1, (float, float) v2);
    // Returns degrees 0-180, uses Mathf.Acos with clamp to [-1,1]
    public static (float, float) DirectionVector(Position from, Position to);
    public static bool IsInCone(Position source, (float,float) facing, Position target,
                                float coneAngle, float coneRange);
    // coneAngle is TOTAL angle; test against halfAngle = coneAngle / 2
    public static bool IsInCircle(Position center, Position target, float radius);
    public static (float, float) GetFacingFromTarget(Position source, Position target);
    public static (float, float) EstimateFacingDirection(object source);
    // Tries last_move_direction, velocity, falls back to (1, 0)
}
```

**Pygame replacement**: None. This is pure math.

#### 3.2.2 TargetFinder.cs (from `core/geometry/target_finder.py`, ~200 lines)

**Methods:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `find_targets(geometry, source, target, params, context, entities)` | `public List<object> FindTargets(string geometry, object source, object target, Dictionary<string,object> parms, string context, List<object> entities)` | Main dispatcher |
| `find_single_target(target, context)` | Returns `[target]` if valid | Simple wrapper |
| `find_chain_targets(source, primary, count, range, ctx, entities)` | Chain targeting: start at primary, find nearest unvisited within `chain_range`, up to `chain_count` | Default: count=2, range=5.0 |
| `find_cone_targets(source, target, angle, range, ctx, entities)` | Filter by `IsInCone` using facing from source to target | Default: angle=60, range=8.0 |
| `find_circle_targets(center, radius, maxTargets, ctx, entities)` | Filter by `IsInCircle`, optional max targets (0=unlimited) | Default: radius=3.0 |
| `find_beam_targets(source, target, range, width, pierceCount, ctx, entities)` | Line from source toward target, filter by perpendicular distance <= width/2 | Default: range=10.0, width=0.5 |

**Context flipping for enemy sources**: When source is an Enemy (has `definition` and `is_alive` attributes), flip "enemy"<->"ally" so enemies target the player with damage and buff other enemies.

**Circle origin**: Parameter `origin` controls center -- `"target"` uses primary_target position, `"source"` uses source position.

#### 3.2.3 EffectExecutor.cs (from `core/effect_executor.py`, 623 lines)

**Main execution flow** (`ExecuteEffect`):
1. Parse tags via TagParser -> EffectConfig
2. Create EffectContext
3. Find targets via TargetFinder using geometry
4. For each target (indexed):
   a. Calculate magnitude multiplier (chain/pierce falloff)
   b. Apply damage if `BaseDamage > 0`
   c. Apply healing if `BaseHealing > 0`
   d. Apply status effects
   e. Apply special mechanics

**Methods:**

| Python Method | C# Signature | Critical Formula |
|---|---|---|
| `_calculate_magnitude_multiplier` | `private float CalculateMagnitudeMultiplier(EffectConfig config, int targetIndex, int totalTargets)` | Chain: `(1 - falloff)^index`, default falloff=0.3. Pierce: `(1 - falloff)^index`, default falloff=0.1. Others: 1.0 |
| `_apply_damage` | `private void ApplyDamage(object source, object target, EffectConfig config, float magnitudeMult)` | base * magnitudeMult * critMultiplier. Crit: `Random < crit_chance` (default 0.15) -> multiply by `crit_multiplier` (default 2.0). Per damage tag, check context_behavior for damage_multiplier and converts_to_healing |
| `_apply_healing` | `private void ApplyHealing(object source, object target, EffectConfig config, float magnitudeMult)` | `baseHealing * magnitudeMult` |
| `_apply_status_effects` | `private void ApplyStatusEffects(object target, EffectConfig config)` | For each status tag: merge default params with config params, check immunity |
| `_apply_special_mechanics` | `private void ApplySpecialMechanics(...)` | Dispatcher for: lifesteal, knockback, pull, execute, teleport, dash, phase |

**Special mechanics detail:**

| Mechanic | Parameters | Formula |
|---|---|---|
| **Lifesteal** | `lifesteal_percent` (default 0.15) | `heal = damage * lifesteal_percent` applied to source |
| **Knockback** | `knockback_distance` (default 2.0), `knockback_duration` (default 0.5) | velocity = distance / duration, direction = normalized(target - source). Sets `knockback_velocity_x/y` and `knockback_duration_remaining` on target |
| **Pull** | `pull_distance` / `pull_strength` (default 2.0) | Direction toward source, `actual_pull = min(pull_distance, distance)`. Instant position update |
| **Execute** | `threshold_hp` (default 0.2), `bonus_damage` (default 2.0) | If `target.current_health / max_health <= threshold`, apply `baseDamage * magnitude * (bonus_damage - 1.0)` as extra damage |
| **Teleport** | `teleport_range` (default 10.0), `teleport_type` (default "targeted") | Instant position set if distance <= range |
| **Dash** | `dash_distance` (default 5.0), `dash_speed` (default 20.0) | `dash_duration = actual_dash / dash_speed`. Uses knockback velocity system toward target. Fallback: instant position move |
| **Phase** | `phase_duration` (default 2.0), `can_pass_walls` (default false) | Applies "phase" status effect via status_manager |

**Auto-apply status**: After applying damage for a damage tag, check `tag_def.auto_apply_status` and `auto_apply_chance`. If `Random < chance`, apply that status with default params.

**Pygame replacement**: None -- EffectExecutor is pure logic. Remove `print()` calls; replace with C# debug logging or event system.

---

### 3.3 Combat System

#### 3.3.1 CombatConfig.cs (extracted from `Combat/combat_manager.py`, lines 24-108)

**Constants (exact values from Python):**

```csharp
public class CombatConfig
{
    // EXP rewards per tier
    public Dictionary<string, int> ExpRewards = new()
    {
        {"tier1", 100}, {"tier2", 400}, {"tier3", 1600}, {"tier4", 6400}
    };
    public float BossMultiplier = 10.0f;

    // Safe zone (no enemy spawning)
    public float SafeZoneX = 0f;
    public float SafeZoneY = 0f;
    public float SafeZoneRadius = 15f;

    // Spawn density weights
    public Dictionary<string, float> DensityWeights = new()
    {
        {"very_low", 0.5f}, {"low", 0.75f}, {"moderate", 1.0f},
        {"high", 2.0f}, {"very_high", 3.0f}
    };

    // Combat timing
    public float BaseAttackCooldown = 1.0f;
    public float ToolAttackCooldown = 0.5f;
    public float CorpseLifetime = 30.0f;
    public float CombatTimeout = 5.0f;

    // Enemy spawning
    public int MaxEnemiesPerChunk = 3;
    public int ChunkSize = 16;

    // Night modifiers
    public float NightAggroMultiplier = 1.3f;
    public float NightSpeedMultiplier = 1.15f;

    public bool LoadFromFile(string filepath); // JSON loading
}
```

#### 3.3.2 DamageCalculator.cs (extracted -- pure math, testable in isolation)

**The complete damage pipeline** (from `player_attack_enemy`, lines 684-982):

```csharp
public static class DamageCalculator
{
    /// <summary>
    /// Full damage pipeline matching Python CombatManager.player_attack_enemy exactly.
    /// </summary>
    public static DamageResult CalculatePlayerDamage(
        int weaponDamage,
        float toolTypeEffectiveness,
        WeaponTagModifiers weaponTags,
        CharacterStats stats,
        TitleSystem titles,
        BuffManager buffs,
        EnemyDefinition enemy,
        System.Random rng)
    {
        // Step 1: Base weapon damage (0 = unarmed = 5)
        float baseDmg = weaponDamage == 0 ? 5f : weaponDamage;

        // Step 2: Tool effectiveness penalty
        baseDmg *= toolTypeEffectiveness;

        // Step 3: Weapon tag damage multiplier (2H=+20%, versatile without offhand=+10%)
        baseDmg *= weaponTags.DamageMultiplier;

        // Step 4: STR multiplier: 1.0 + (STR * 0.05)
        float strMult = 1.0f + (stats.Strength * 0.05f);
        baseDmg *= strMult;

        // Step 5: Title melee bonus
        float titleMeleeBonus = titles.GetTotalBonus("meleeDamage");
        baseDmg *= (1.0f + titleMeleeBonus);

        // Step 6: Enemy-specific damage multiplier (beastDamage, etc.)
        baseDmg *= enemyDamageMultiplier;

        // Step 7: Crushing bonus vs armored (defense > 10)
        if (weaponTags.CrushingBonus > 0f && enemy.Defense > 10)
            baseDmg *= (1.0f + weaponTags.CrushingBonus);

        // Step 8: Skill buff bonus (empower)
        float skillDmgBonus = Mathf.Max(
            buffs.GetDamageBonus("damage"),
            buffs.GetDamageBonus("combat"));
        if (skillDmgBonus > 0f)
            baseDmg *= (1.0f + skillDmgBonus);

        // Step 9: Critical hit
        float effectiveLuck = stats.GetEffectiveLuck();
        float baseCritChance = 0.02f * effectiveLuck;
        float pierceBuff = buffs.GetTotalBonus("pierce", "damage");
        float titleCritBonus = titles.GetTotalBonus("criticalChance");
        float critChance = baseCritChance + pierceBuff + weaponTags.CritBonus + titleCritBonus;
        bool isCrit = rng.NextDouble() < critChance;
        if (isCrit) baseDmg *= 2.0f;

        // Step 10: Defense reduction (with armor penetration)
        float effectiveDefense = enemy.Defense * (1.0f - weaponTags.ArmorPenetration);
        float defenseReduction = effectiveDefense * 0.01f;  // 1% per point
        float finalDamage = baseDmg * (1.0f - Mathf.Min(0.75f, defenseReduction));

        return new DamageResult(finalDamage, isCrit);
    }
}
```

**Key constants to verify:**
- STR multiplier: `1.0 + STR * 0.05` (5% per point)
- Crit chance base: `0.02 * effective_luck` (2% per luck)
- Crit multiplier: `2.0x`
- Defense: `1% reduction per defense point, capped at 75%`
- Unarmed damage: `5`
- Armor penetration: reduces effective defense by percentage
- Crushing: `+20%` vs armored (defense > 10)

**Enchantment effects applied after damage** (lines 855-892):
- **Lifesteal**: `heal = finalDamage * min(lifestealPercent, 0.50)` -- 50% cap
- **Chain Damage**: Find `chainCount` nearest enemies, deal `finalDamage * chainDamagePercent` (default 50%)

**Durability loss** (lines 898-980):
- Proper weapon use: -1 durability per attack
- Improper tool use (axe/pickaxe in combat): -2 durability
- DEF stat multiplier applied: `stats.GetDurabilityLossMultiplier()`
- Unbreaking enchantment: `loss *= (1.0 - enchantment_value)`

**EXP calculation**: `config.ExpRewards[tier] * (config.BossMultiplier if boss)`. In dungeon: 2x EXP, no loot drops.

#### 3.3.3 EnemySpawner.cs (extracted from CombatManager, lines 250-450)

**Spawning algorithm:**
1. Check safe zone: `distance(chunkCenter, safeZoneCenter) <= safeZoneRadius` -> skip
2. Get danger level from chunk type string: contains "peaceful", "dangerous", or "rare"
3. Build weighted spawn pool from chunk template `enemySpawns` + tier-filtered general pool
4. Select via `Random.choices(enemies, weights)` (weighted random)
5. Cap at `MAX_PER_CHUNK = 3` alive enemies per chunk

**Tier restrictions by danger level:**
- Peaceful: T1 only
- Dangerous: T1-T3
- Rare: T1-T4 (including bosses)

**Dynamic respawn**: Check every `spawnInterval` seconds (from config), respawn in 3x3 chunk area around player.

#### 3.3.4 CombatManager.cs (remaining orchestration)

**Methods to port:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `update(dt, shield_blocking, is_night)` | `public void Update(float dt, bool shieldBlocking, bool isNight)` | Main loop: update enemies, check attacks, manage corpses, dynamic spawning |
| `player_attack_enemy(enemy, hand)` | `public DamageResult PlayerAttackEnemy(Enemy enemy, string hand)` | Calls DamageCalculator, applies enchantments |
| `_enemy_attack_player(enemy, shield_blocking)` | `private void EnemyAttackPlayer(Enemy enemy, bool shieldBlocking)` | Enemy damage to player |
| `_apply_weapon_enchantment_effects(enemy)` | `private void ApplyWeaponEnchantmentEffects(Enemy enemy)` | Fire Aspect, Poison, Knockback, Frost Touch on-hit |
| `_execute_aoe_attack(target, hand, radius)` | `private DamageResult ExecuteAoeAttack(...)` | Devastate buff AoE |
| `_calculate_exp_reward(enemy)` | `private int CalculateExpReward(Enemy enemy)` | Tier-based, boss multiplied, dungeon 2x |
| `_check_dynamic_spawning(dt)` | `private void CheckDynamicSpawning(float dt)` | Respawn in nearby chunks |
| `is_in_safe_zone(x, y)` | `public bool IsInSafeZone(float x, float y)` | Distance check |
| `on_dungeon_enemy_killed(enemy)` | `public void OnDungeonEnemyKilled(Enemy enemy)` | Notify dungeon manager |

**Pygame replacement**: `pygame.time.get_ticks()` is not used in combat_manager.py directly; timing uses `dt` parameter. No Pygame dependencies to replace.

---

### 3.4 Crafting System

#### 3.4.1 DifficultyCalculator.cs (from `core/difficulty_calculator.py`, 808 lines)

**Constants (exact from Python):**

```csharp
public static class DifficultyConstants
{
    // Tier points (LINEAR)
    public static readonly Dictionary<int, int> TierPoints = new()
    {
        {1, 1}, {2, 2}, {3, 3}, {4, 4}
    };

    // Difficulty thresholds
    public static readonly (float min, float max, string name)[] DifficultyTiers =
    {
        (0, 4, "Common"),
        (5, 10, "Uncommon"),
        (11, 20, "Rare"),
        (21, 40, "Epic"),
        (41, 150, "Legendary")
    };

    public const float MinPoints = 1.0f;
    public const float MaxPoints = 80.0f;
}
```

**Smithing parameter ranges** (interpolated between min/max by normalized difficulty):

| Parameter | Easy (0.0) | Hard (1.0) |
|---|---|---|
| `time_limit` | 60s | 25s |
| `temp_ideal_range` | 25 deg | 3 deg |
| `temp_decay_rate` | 0.3/100ms | 0.6/100ms |
| `temp_fan_increment` | 4.0 deg | 1.5 deg |
| `required_hits` | 3 | 12 |
| `target_width` | 100px | 30px |
| `perfect_width` | 50px | 10px |
| `hammer_speed` | 3.0 px/frame | 14.0 px/frame |

**Core calculation**: `material_points = sum(tier_points[material.tier] * quantity)` for each input. Then normalize to 0-1 range and interpolate parameters.

**Per-discipline modifiers:**
- **Smithing**: base_points only
- **Refining**: `base * diversity_mult * station_tier_mult` (station multipliers 1.5x to 4.5x)
- **Alchemy**: `base * diversity_mult * tier_modifier * volatility`
- **Engineering**: `base * diversity_mult * slot_modifier`
- **Enchanting**: `base * diversity_mult`

**Diversity multiplier**: `1.0 + (unique_material_count - 1) * 0.1`

#### 3.4.2 RewardCalculator.cs (from `core/reward_calculator.py`, 607 lines)

**Constants:**

```csharp
public static class RewardConstants
{
    public const float MinDifficultyPoints = 1.0f;
    public const float MaxDifficultyPoints = 80.0f;
    public const float MinRewardMultiplier = 1.0f;
    public const float MaxRewardMultiplier = 2.5f;
    public const float MinFailureLoss = 0.30f;   // 30%
    public const float MaxFailureLoss = 0.90f;    // 90%
    public const float FirstTryBoost = 0.10f;     // +10% performance
    public const float FirstTryThreshold = 0.50f; // 50% minimum to qualify
}
```

**Quality tiers:**

| Performance Range | Quality Tier |
|---|---|
| 0.00 - 0.25 | Normal |
| 0.25 - 0.50 | Fine |
| 0.50 - 0.75 | Superior |
| 0.75 - 0.90 | Masterwork |
| 0.90 - 1.00 | Legendary |

**Max reward multiplier formula**: `1.0 + (normalized_difficulty * 1.5)`, where `normalized = clamp((points - 1) / (80 - 1), 0, 1)`

#### 3.4.3 SmithingMinigame.cs (from `Crafting-subdisciplines/smithing.py`, 909 lines)

**Core state:**

```csharp
public class SmithingMinigame
{
    // Difficulty params (set from DifficultyCalculator)
    private int TEMP_IDEAL_MIN, TEMP_IDEAL_MAX;
    private float TEMP_DECAY;           // per 100ms tick
    private float TEMP_FAN_INCREMENT;
    private float HAMMER_SPEED;         // pixels/frame
    private int REQUIRED_HITS;
    private int TARGET_WIDTH, PERFECT_WIDTH;
    private int timeLimit;
    private const int HAMMER_BAR_WIDTH = 400;

    // Game state
    private float temperature = 50f;
    private int hammerHits = 0;
    private float hammerPosition = 0f;
    private int hammerDirection = 1;
    private List<int> hammerScores = new();
    private float timeLeft;
    private float speedBonus;           // Slows fire decrease
}
```

**Temperature decay** (Update, every 100ms tick):
```
effective_decay = TEMP_DECAY / (1.0 + speedBonus)
temperature = max(0, temperature - effective_decay)
```

**Hammer movement** (Update, per frame):
```
hammerPosition += hammerDirection * HAMMER_SPEED
if hammerPosition <= 0 or hammerPosition >= HAMMER_BAR_WIDTH:
    hammerDirection *= -1
    hammerPosition = clamp(hammerPosition, 0, HAMMER_BAR_WIDTH)
```

**Hammer timing score** (binned system from center):
```
half_width = HAMMER_BAR_WIDTH / 2.0 = 200
w = half_width / 9.0 = ~22.2 pixels

Zone boundaries (distance from center):
  0 to 0.3w  -> 100 (perfect)
  0.3w to 1w -> 90
  1w to 2w   -> 80
  2w to 3w   -> 70
  3w to 4w   -> 60
  4w to 6w   -> 50
  6w to 9w   -> 30
  beyond 9w  -> 0
```

**Temperature multiplier** (exponential falloff):
```
k = ln(2) / 16 = 0.0433
If temperature in [IDEAL_MIN, IDEAL_MAX]: mult = 1.0
Else: deviation = distance to nearest ideal boundary
      mult = max(0.1, exp(-0.0433 * deviation^2))
```

**Final strike score**: `round(hammer_timing_score * temp_multiplier)`

**End result**: `avg(hammerScores)` -> passed to RewardCalculator for quality tier.

**Pygame replacements:**
- `pygame.time.get_ticks()` -> `Time.time * 1000f` or use `Time.deltaTime` accumulator
- Temperature tick at 100ms intervals: use accumulator pattern in Update

#### 3.4.4 AlchemyMinigame.cs (from `Crafting-subdisciplines/alchemy.py`, 1,070 lines)

**AlchemyReaction class (inner):**

**Secret value calculation:**
```
vowels = {'a','e','i','o','u','A','E','I','O','U'}
vowel_count = count of vowels in ingredient_id (alpha chars only)
total_chars = count of alpha chars in ingredient_id
vowel_ratio = vowel_count / total_chars (or 0.5 if total_chars == 0)
secret_value = clamp((vowel_ratio - 0.2) * 2.0, 0.0, 1.0)
```

**Oscillation pattern assignment:**
```
secret < 0.25  -> 1 oscillation (25% of ingredients)
secret < 0.65  -> 2 oscillations (40% of ingredients)
secret >= 0.65 -> 3 oscillations (35% of ingredients)
```

**Timing by ingredient type:**
- stable: stage durations [1.0, 2.5, 2.0, 2.0, 1.5]s, sweet_spot=2.0s, no false peaks
- moderate: [0.8, 2.0, 1.5, 1.5, 1.2]s, sweet_spot=1.5s, false_peaks=[0.4, 0.7]
- volatile: [0.5, 1.5, 1.0, 1.0, 0.8]s, sweet_spot=1.0s, false_peaks=[0.3, 0.5, 0.7, 0.9]

**5 reaction stages**: Initiation, Building (false peaks), Sweet Spot (TARGET), Degrading, Critical Failure.

**Volatility calculation** (from difficulty calculator):
```
volatility = clamp((vowel_ratio - 0.3) * 2.5, 0.0, 1.0)
```

**Pygame replacements:** `pygame.time.get_ticks()` -> Unity time accumulator.

#### 3.4.5 RefiningMinigame.cs (from `Crafting-subdisciplines/refining.py`, 826 lines)

**Core mechanic**: Cylinder alignment. Player rotates cylinders to align windows.

**Timing window formula:**
```
window = timing_window * rotation_speed * 360 * 0.625
```

**Rarity upgrade**: 4:1 ratio (4 lower materials produce 1 higher rarity).

**Pygame replacements:** `pygame.time.get_ticks()` -> Unity time.

#### 3.4.6 EngineeringMinigame.cs (from `Crafting-subdisciplines/engineering.py`, 1,312 lines)

**Two sub-minigames:**

1. **Pipe Rotation**: Grid of pipe tiles that must be rotated to create valid paths. Path validation uses **BFS** from source node to drain node through connected pipes.

2. **Logic Switch** (lights-out variant): Toggling one switch affects neighbors. Goal: all switches in target state.

**Scoring formula:**
```
score = reward * exp(-(moves / ideal_moves - 1))
```

Where `moves` is actual player moves and `ideal_moves` is computed minimum.

**BFS path validation** must be ported exactly -- pipe connection rules define which orientations connect.

**Pygame replacements:** Input handling (click/keyboard) -> Unity input. `pygame.time.get_ticks()` -> Unity time.

#### 3.4.7 EnchantingMinigame.cs (from `Crafting-subdisciplines/enchanting.py`, 1,408 lines)

**Spinning wheel with 20 slices.**

**Spin multipliers (per spin round):**

| Spin | Great | Good | Bad |
|---|---|---|---|
| Spin 1 | 1.2x | 1.0x | 0.66x |
| Spin 2 | 1.5x | 0.95x | 0.5x |
| Spin 3 | 2.0x | 0.8x | 0.0x (total loss) |

**Efficacy formula:**
```
efficacy = (currency_diff / 100) * 50
```

Where `currency_diff` is the difference between spent and required enchanting currency.

**Pygame replacements:** Rendering of spinning wheel animation -> Unity UI/shader. `pygame.time.get_ticks()` -> Unity time.

#### 3.4.8 InteractiveCrafting.cs (from `core/interactive_crafting.py`, 1,179 lines)

**5 UI layout configurations:**

| Discipline | Grid Type | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| Smithing | Square grid | 3x3 | 5x5 | 7x7 | 9x9 |
| Refining | Hub-spoke | 1 hub + 2 spokes | 2 hub + 4 | 2 hub + 5 | 3 hub + 6 |
| Alchemy | Sequential | 2 slots | 3 slots | 4 slots | 6 slots |
| Engineering | 5 slot types | type-specific | type-specific | type-specific | type-specific |
| Adornments | Shape-based Cartesian | -7 to +7 coordinate space | same | same | same |

**Factory method**: `create_interactive_ui(discipline, station_tier)` returns appropriate UI class.

**Pygame replacements:** All Pygame rendering and mouse handling -> Unity UI. This file is heavily UI-coupled and requires the most adaptation. Separate logic (slot layout, validation, material placement rules) from rendering.

---

### 3.5 World System

#### 3.5.1 WorldSystem.cs (from `systems/world_system.py`, 1,110 lines)

**Key state:**
```csharp
public class WorldSystem
{
    public int Seed { get; }
    private System.Random _worldRng;
    public BiomeGenerator BiomeGenerator { get; }
    public Dictionary<(int, int), Chunk> LoadedChunks { get; }
    public List<CraftingStation> CraftingStations { get; }
    public List<PlacedEntity> PlacedEntities { get; }
    private HashSet<(int, int)> _barrierPositions;  // O(1) collision lookup cache
    public Dictionary<(int, int), DungeonEntrance> DiscoveredDungeonEntrances { get; }
    public List<LootChest> DeathChests { get; }
    public float GameTime { get; set; }
}
```

**Methods:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `__init__(seed)` | Constructor | Generate random seed if null: `Random(0, 2^32-1)` |
| `_load_initial_chunks()` | `private void LoadInitialChunks()` | Load spawn_always_loaded_radius from WorldGenerationConfig |
| `get_chunk(cx, cy)` | `public Chunk GetChunk(int cx, int cy)` | Lazy-load: generate if not loaded |
| `get_tile(position)` | `public WorldTile GetTile(Position pos)` | Convert world pos to chunk + local offset |
| `get_resource_at(pos)` | `public NaturalResource GetResourceAt(Position pos)` | Check chunk resources |
| `is_walkable(pos)` | `public bool IsWalkable(Position pos)` | Tile + barrier check |
| `spawn_starting_stations()` | `private void SpawnStartingStations()` | Place crafting stations at spawn |
| `update_chunks(player_pos)` | `public void UpdateChunks(Position playerPos)` | Load/unload chunks based on view distance |
| `place_entity(entity)` | `public void PlaceEntity(PlacedEntity entity)` | Add barrier to cache if barrier type |
| `remove_entity(entity)` | `public void RemoveEntity(PlacedEntity entity)` | Remove from barrier cache |

**Seed initialization**: `seed ?? new System.Random().Next(0, int.MaxValue)`

**Chunk coordinates**: `chunk_x = floor(world_x / 16)`, `chunk_y = floor(world_y / 16)`. CHUNK_SIZE = 16.

**Unity consideration**: Map to Unity Tilemap or custom chunk renderer. Keep chunk logic in pure C# for testability; add MonoBehaviour wrapper for rendering.

#### 3.5.2 BiomeGenerator.cs (from `systems/biome_generator.py`, 596 lines)

**Deterministic seed derivation** (Szudzik pairing for negative coordinates):
```csharp
public int GetChunkSeed(int chunkX, int chunkY)
{
    // Map negatives to positives: n -> 2*n (positive), n -> -2*n-1 (negative)
    long a = chunkX >= 0 ? 2L * chunkX : -2L * chunkX - 1;
    long b = chunkY >= 0 ? 2L * chunkY : -2L * chunkY - 1;
    // Szudzik pairing
    long paired = (a >= b) ? a * a + a + b : a + b * b;
    // Combine with world seed
    return (int)((paired ^ seed) & 0x7FFFFFFF);
}
```

**Constants:**
- `SAFE_ZONE_RADIUS = 8` chunks
- Biome distribution loaded from WorldGenerationConfig JSON: water/forest/cave ratios

**Danger zone**: Within 8 chunks of spawn, progressively safer (higher peaceful chance closer to origin). Beyond 8 chunks: no bias.

#### 3.5.3 Chunk.cs (from `systems/chunk.py`, 558 lines)

**Key data:**
```csharp
public class Chunk
{
    public int ChunkX { get; }
    public int ChunkY { get; }
    public ChunkType ChunkTypeValue { get; }
    public WorldTile[,] Tiles { get; }           // 16x16
    public List<NaturalResource> Resources { get; }
    public bool IsModified { get; set; }
    public float LastAccessTime { get; set; }
}
```

Size: 16x16 tiles. Resource spawning by chunk type. Modification tracking for save optimization.

#### 3.5.4 CollisionSystem.cs (from `systems/collision_system.py`, 599 lines)

**Line-of-sight** (Bresenham's line algorithm):
```csharp
public CollisionResult HasLineOfSight(
    (float, float) source, (float, float) target,
    List<string> attackTags = null,
    bool checkResources = true, bool checkBarriers = true, bool checkTiles = true)
```
Tags in `BYPASS_LOS_TAGS = {"circle", "aoe", "ground"}` skip the check entirely.

**A\* Pathfinding:**
```csharp
public List<(float, float)> FindPath(
    (float, float) start, (float, float) goal,
    int maxIterations = 200, int maxPathLength = 50)
```

**A\* implementation details:**
- 8-directional movement (cardinal + diagonal)
- Diagonal cost: `1.414` (sqrt(2)), cardinal cost: `1.0`
- Heuristic: Octile distance = `max(dx,dy) + 0.414 * min(dx,dy)`
- Corner-cutting prevention: diagonal move only if both adjacent cardinal tiles are walkable
- Path cache: keyed by `"startX,startY->goalX,goalY"`
- Returns tile-center positions: `(x + 0.5, y + 0.5)`
- If goal is unwalkable, find nearest walkable tile within radius 4

**Movement collision** (`CanMoveTo`):
1. Try direct move to (newX, newY)
2. If blocked, try X-only slide: (newX, currentY)
3. If blocked, try Y-only slide: (currentX, newY)
4. If all blocked, stay at current position

#### 3.5.5 NaturalResource.cs (from `systems/natural_resource.py`, 191 lines)

Harvestable resource with HP, yield amounts, tool requirements, respawn timer. Straightforward data class with `Harvest()` and `Update(dt)` for respawn tracking.

---

### 3.6 Save/Load System

#### 3.6.1 SaveManager.cs (from `systems/save_manager.py`, 634 lines)

**Save version**: `"3.0"` -- infinite world with seed-based generation.

**Top-level save structure:**
```json
{
  "version": "3.0",
  "save_timestamp": "ISO-8601",
  "player": { ... },
  "world_state": { ... },
  "quest_state": { ... },
  "npc_state": { ... },
  "game_settings": { "keep_inventory": true },
  "dungeon_state": { ... },
  "map_state": { ... }
}
```

**Methods:**

| Python Method | C# Signature | Notes |
|---|---|---|
| `create_save_data(...)` | `public SaveData CreateSaveData(Character, WorldSystem, QuestManager, ...)` | Aggregates all state |
| `save_to_file(path, data)` | `public void SaveToFile(string path, SaveData data)` | JSON serialization via Newtonsoft.Json |
| `load_from_file(path)` | `public SaveData LoadFromFile(string path)` | Deserialize + version migration |
| `_serialize_character(char)` | `private JObject SerializeCharacter(Character c)` | Position, stats, inventory, equipment, skills, buffs, leveling |
| `_serialize_world_state(world, time)` | `private JObject SerializeWorldState(...)` | Seed, game_time, stations, placed_entities, death_chests, dungeon_entrances |
| `_serialize_quest_state(mgr)` | `private JObject SerializeQuestState(...)` | Active quests with progress |

**Unity considerations:**
- Use `Newtonsoft.Json` (Json.NET) for full compatibility with existing save format
- Save path: `Application.persistentDataPath` on Unity
- Keep JSON format for cross-platform compatibility and debugging
- Version migration: support loading v2.0 saves into v3.0 format

---

### 3.7 Support Systems

#### 3.7.1 DungeonSystem.cs (from `systems/dungeon.py`, 805 lines)

**Constants:**
- Dungeon size: 2x2 chunks = 32x32 tiles
- 3 waves of enemies per dungeon
- 2x EXP from dungeon mobs, no material drops
- Loot chest appears after clearing all waves

**Rarity distribution:**
| Rarity | Chance | Mob Count | Tier Mix |
|---|---|---|---|
| Common | 25% | 20 | Mostly T1 |
| Uncommon | 30% | 30 | T1-T2 mix |
| Rare | 20% | 40 | T2-T3 mix |
| Epic | 15% | 50 | Mostly T3 |
| Legendary | 8% | 50 | T3-T4 heavy |
| Unique | 2% | 50 | Almost all T4 |

**Key classes**: `LootChest`, `DungeonInstance`, `DungeonManager`. Configuration loaded from `Definitions.JSON/dungeon-config-1.JSON` with fallback to hardcoded `DUNGEON_CONFIG`.

#### 3.7.2 QuestSystem.cs (from `systems/quest_system.py`, 292 lines)

**Quest class with baseline tracking:**
- On quest accept: snapshot current inventory counts and combat kills
- Check completion: `gathered_since_start = current - baseline`
- Objective types: `"gather"` (item-based) and `"combat"` (kill count)
- `consume_items()`: Remove required items from inventory on turn-in
- `grant_rewards()`: EXP, items, titles, skill unlocks

#### 3.7.3 TitleSystem.cs (from `systems/title_system.py`, 86 lines)

**Acquisition methods:**
- `guaranteed_milestone`: Auto-granted when conditions met
- `event_based_rng`: `Random < title.generation_chance`
- `hidden_discovery`: Auto-granted (hidden from UI until earned)
- `special_achievement`: RNG with usually very low chance
- `random_drop` (legacy): tier-based chances: novice=100%, apprentice=20%, journeyman=10%, expert=5%, master=2%

**Bonus aggregation**: `GetTotalBonus(bonusType)` sums all earned title bonuses of that type.

#### 3.7.4 ClassSystem.cs (from `systems/class_system.py`, 69 lines)

**Tag-driven tool bonuses:**
- `nature` tag: +10% axe efficiency
- `gathering` tag: +10% pickaxe efficiency, +5% axe
- `explorer` tag: +5% pickaxe
- `physical` tag: +5% tool damage
- `melee` tag: +5% tool damage

**Callback pattern**: `RegisterOnClassSet(Action<ClassDefinition>)` for notifying other systems.

#### 3.7.5 SkillUnlockSystem.cs (from `systems/skill_unlock_system.py`, 205 lines)

**Three-state skill unlock flow:**
1. Check conditions (level, title, quest completion)
2. If no cost: unlock immediately
3. If has cost (gold, materials, skill points): mark as `pending`, await player confirmation
4. On confirmation: deduct cost, unlock skill, add to `SkillManager`

#### 3.7.6 PotionSystem.cs (from `systems/potion_system.py`, 386 lines)

**Tag-driven effect application:**
- `healing` + `instant`: Restore HP immediately
- `healing` + `over_time`: HP regen buff
- `mana_restore`: Restore mana
- `buff`: Stat buffs (strength, defense, speed)
- `resistance`: Elemental damage resistance
- `utility`: Tool/armor enhancements

**Quality scaling:**
```
potency = crafted_stats.potency / 100.0  // Effect strength multiplier
duration_mult = crafted_stats.duration / 100.0  // Duration multiplier
```

Supports both legacy single-effect `effectParams` (dict) and modular array format.

#### 3.7.7 TurretSystem.cs (from `systems/turret_system.py`, 551 lines)

**Update loop:**
1. Update status effects on all placed entities
2. Decrement lifetime, remove expired
3. For turrets: find nearest enemy in range, check cooldown, attack via `EffectExecutor`
4. Check trap triggers (proximity activation)
5. Check bomb detonations (timed fuse)

**Attack cooldown**: `cooldown = 1.0 / attackSpeed` (attacks per second converted to seconds between attacks).

**Stun/Freeze check**: Stunned or frozen turrets cannot attack.

**Uses EffectExecutor**: Turret attacks go through the tag system, using turret's configured tags and params.

#### 3.7.8 AttackEffects.cs (from `systems/attack_effects.py`, 233 lines)

**Visual feedback data (logic-only, rendering in Phase 5):**

```csharp
public enum AttackEffectType { Line, Blocked, HitParticle, Area }
public enum AttackSourceType { Player, Turret, Enemy, Environment }

public class AttackEffect
{
    public AttackEffectType EffectType;
    public AttackSourceType SourceType;
    public (float, float) StartPos;
    public (float, float) EndPos;
    public float StartTime;
    public float Duration = 0.3f;
    public bool Blocked;
    public float Damage;
    public List<string> Tags;

    public float Age => Time.time - StartTime;
    public float Alpha => age < duration * 0.7f ? 1.0f :
        1.0f - ((age - duration * 0.7f) / (duration * 0.3f));
    public bool IsExpired => Age >= Duration;
}
```

**Color mapping**: Player=blue(50,150,255), Turret=cyan, Enemy=red, Blocked=yellow(255,200,0).

---

## 4. Pygame-Specific Code Replacement Guide

Every crafting minigame uses Pygame for timing and input. Here is the systematic replacement strategy:

| Python (Pygame) | C# (Unity) | Used In |
|---|---|---|
| `pygame.time.get_ticks()` | `Time.time * 1000f` or accumulator with `Time.deltaTime` | smithing.py, alchemy.py, refining.py, engineering.py, enchanting.py |
| `if now - last_update > 100:` | `_tickAccumulator += dt; while (_tickAccumulator >= 0.1f) { ... _tickAccumulator -= 0.1f; }` | smithing.py temperature decay (100ms tick) |
| `pygame.event handling` | Unity InputSystem or `Input.GetKeyDown()` / `Input.GetMouseButtonDown()` | All crafting minigames |
| `pygame.Surface`, `pygame.draw` | Unity UI Canvas / SpriteRenderer / LineRenderer | interactive_crafting.py (all rendering) |
| `time.time()` | `Time.time` (float seconds) | turret_system.py, attack_effects.py |
| `random.random()` | `UnityEngine.Random.value` or `System.Random.NextDouble()` | combat, spawning, titles |
| `random.choices(items, weights)` | Custom weighted random or `System.Random` | enemy spawning |
| `random.uniform(a, b)` | `UnityEngine.Random.Range(a, b)` | spawn positions |
| `random.randint(a, b)` | `UnityEngine.Random.Range(a, b+1)` | spawn counts (note: inclusive) |

**Important**: Separate logic from rendering in crafting minigames. Create `IMinigameLogic` interface for testable game logic, with Unity MonoBehaviour wrappers for rendering.

---

## 5. Key Architectural Decisions

### 5.1 CombatManager Decomposition

The 2,009-line Python CombatManager should be split into three C# classes:

1. **DamageCalculator** (static, pure math): All damage formula calculations. No state, fully testable. ~300 lines.
2. **EnemySpawner**: Spawn logic, weighted pools, tier filtering, chunk templates. ~400 lines.
3. **CombatManager**: Orchestration, update loop, state management, enchantment application. ~800 lines.

### 5.2 Crafting Minigame Architecture

Each minigame should be split into:
- **Logic class** (pure C#, no Unity dependencies): All formulas, state transitions, scoring. Testable with unit tests.
- **MonoBehaviour wrapper**: Unity lifecycle, input handling, calls into logic class.
- **UI class**: Visual representation (rendered in Phase 5).

### 5.3 WorldSystem and Unity Tilemap

Two options:
1. **Custom chunk renderer**: Keep WorldSystem as pure C#, add rendering layer in Phase 5.
2. **Unity Tilemap integration**: Map Chunk tile data to Unity Tilemap. Requires TileBase subclasses.

**Recommendation**: Option 1 for Phase 4 (pure logic), add Tilemap rendering in Phase 5.

### 5.4 Save System Serialization

Use **Newtonsoft.Json** (Json.NET for Unity) to maintain JSON compatibility:
- Existing save files can be loaded during testing
- Human-readable for debugging
- `[JsonProperty("snake_case")]` attributes on C# properties to match Python key names

### 5.5 Singleton Pattern

Python uses module-level singletons (`_instance = None`). In C#, use thread-safe lazy pattern:

```csharp
public class TagRegistry
{
    private static readonly Lazy<TagRegistry> _instance =
        new Lazy<TagRegistry>(() => { var r = new TagRegistry(); r.Load(); return r; });
    public static TagRegistry Instance => _instance.Value;
}
```

### 5.6 Deterministic Randomness

For world generation and biome assignment, use `System.Random` with explicit seed (NOT `UnityEngine.Random` which is global). This ensures save/load determinism:

```csharp
var chunkRng = new System.Random(GetChunkSeed(cx, cy));
```

For combat (non-deterministic), either `System.Random` or `UnityEngine.Random` is acceptable.

---

## 6. Integration Points Between Systems

| System A | System B | Integration |
|---|---|---|
| TagParser | TagRegistry | Parser calls `Registry.ResolveAlias`, `GetDefinition`, `ResolveGeometryConflict` |
| EffectExecutor | TagParser + TargetFinder | Executor calls `Parser.Parse()` then `Finder.FindTargets()` |
| CombatManager | EffectExecutor | Combat uses executor for skill effects, turret attacks |
| CombatManager | WorldSystem | Enemy spawning checks chunk types, safe zones |
| CombatManager | Character (Phase 3) | Reads stats, equipment, buffs; writes health, EXP |
| Crafting Minigames | DifficultyCalculator | All 5 minigames get params from calculator |
| Crafting Minigames | RewardCalculator | All 5 minigames get quality/bonus from calculator |
| WorldSystem | BiomeGenerator | World delegates chunk type to biome gen |
| WorldSystem | CollisionSystem | Collision reads tiles/resources from world |
| CollisionSystem | Enemy AI | A* pathfinding for enemy navigation |
| SaveManager | ALL systems | Serializes/deserializes complete game state |
| TurretSystem | EffectExecutor | Turret attacks routed through tag system |
| PotionSystem | Character.Buffs | Potions apply buffs to character |
| QuestSystem | Character.Inventory | Checks item counts, consumes on turn-in |
| DungeonSystem | CombatManager | Dungeon spawns enemies via combat manager |

---

## 7. Quality Control

### 7.1 Damage Pipeline Verification

**Test case 1: Basic melee attack**
- STR=10, weapon damage range (20,30) avg=25, 2H (+20%), no buffs, no crit, enemy defense=50
- base = 25
- x tool effectiveness (weapon = 1.0) = 25
- x 2H multiplier = 25 * 1.2 = 30
- x STR multiplier = 30 * (1.0 + 10*0.05) = 30 * 1.5 = 45
- x title bonus (0) = 45 * 1.0 = 45
- x enemy type bonus (1.0) = 45
- x crushing (defense 50 > 10, but need crushing tag) = 45
- x skill buff (0) = 45
- x crit (forced no) = 45
- defense reduction = 50 * 0.01 = 0.50, capped at 0.75 -> 0.50
- final = 45 * (1.0 - 0.50) = 22.5

**Test case 2: Critical with armor penetration**
- Same as above but forced crit, 25% armor penetration
- effective defense = 50 * (1.0 - 0.25) = 37.5
- defense reduction = 37.5 * 0.01 = 0.375
- pre-crit damage = 45
- x crit = 45 * 2.0 = 90
- final = 90 * (1.0 - 0.375) = 56.25

**Validation**: Run both Python and C# with same inputs, compare within 0.01 tolerance.

### 7.2 Crafting Formula Verification

**Smithing temperature multiplier test cases:**

| Temperature | Ideal Range | Deviation | k*dev^2 | Multiplier |
|---|---|---|---|---|
| 70 (in range) | 60-80 | 0 | 0 | 1.000 |
| 56 | 60-80 | 4 | 0.693 | 0.500 |
| 50 | 60-80 | 10 | 4.33 | 0.013 -> clamped to 0.100 |
| 85 | 60-80 | 5 | 1.083 | 0.339 |

**Smithing hammer timing test cases (bar width 400):**

| Position | Distance from center (200) | Score |
|---|---|---|
| 200 (center) | 0 | 100 (perfect, < 0.3w = 6.67) |
| 190 | 10 | 90 (< 1w = 22.2) |
| 170 | 30 | 80 (< 2w = 44.4) |
| 130 | 70 | 60 (< 4w = 88.9) |
| 50 | 150 | 30 (< 9w = 200) |
| 0 | 200 | 30 (= 9w exactly, still in zone) |

**Alchemy secret value test cases:**
- `"iron_ingot"`: alpha chars = "ironingot" = 9, vowels = i,o,i,o = 4, ratio=4/9=0.444, secret = (0.444-0.2)*2 = 0.489
- `"oak_log"`: alpha = "oaklog" = 6, vowels = o,a,o = 3, ratio=0.5, secret = (0.5-0.2)*2 = 0.6

### 7.3 World Generation Determinism

**Test**: Generate world with seed=12345. Record chunk types for 5x5 area around origin. Regenerate with same seed. All chunk types must match exactly.

**Szudzik pairing test**: Verify `GetChunkSeed(5, -3)` produces same value across Python and C# implementations.

### 7.4 A* Pathfinding Verification

**Test**: Create 10x10 grid with known obstacles. Run pathfinding from (0,0) to (9,9). Verify:
- Path avoids all obstacles
- Path cost matches octile distance calculation
- No corner cutting (diagonal only when both adjacent cardinal tiles walkable)
- Max 200 iterations respected

### 7.5 Save/Load Roundtrip

**Test**: Create game state with all systems populated. Save to JSON. Load from JSON. Compare every field:
- Character: position, all 6 stats, level, EXP, health, mana
- Inventory: all 30 slots with exact quantities
- Equipment: all 8 slots with durability, enchantments
- World: seed, crafting stations, placed entities, death chests
- Quests: active quests with progress and baselines
- Dungeon: in-dungeon state if applicable

---

## 8. Phase 4 Quality Gate

All of the following must pass before Phase 4 is considered complete:

- [ ] **Tag System**: All 190+ tags load from JSON. Alias resolution works. Geometry conflict resolution matches Python priority order.
- [ ] **Effect Pipeline**: `ExecuteEffect` produces identical damage/healing numbers as Python for 10+ test cases covering all geometry types and special mechanics.
- [ ] **Damage Calculation**: `DamageCalculator` matches Python within +/-0.01 for all test cases including crit, armor pen, enchantments, and buffs.
- [ ] **All 5 Crafting Minigames**: Formula outputs match Python for each discipline's scoring system (smithing temp multiplier, alchemy oscillation, refining window, engineering BFS, enchanting spin).
- [ ] **Difficulty Calculator**: All 5 discipline difficulty calculations produce identical difficulty_points for same recipe inputs.
- [ ] **Reward Calculator**: Quality tier assignment matches for all performance score boundaries (0.0, 0.24, 0.25, 0.49, 0.50, 0.74, 0.75, 0.89, 0.90, 1.0).
- [ ] **World Generation**: Same seed produces identical chunk types for 100 test coordinates.
- [ ] **Biome Generator**: Szudzik pairing produces identical seeds. Danger zone progressive safety matches Python behavior.
- [ ] **A\* Pathfinding**: Produces valid paths for 20 test cases. Octile heuristic matches. Corner-cutting prevented. Max iterations respected.
- [ ] **Collision System**: Bresenham line matches Python for 10 test cases. LoS bypass tags work correctly.
- [ ] **Save/Load**: Full roundtrip preserves 100% of game state. Version "3.0" format matches exactly.
- [ ] **Quest System**: Gather and combat quests complete correctly with baseline tracking.
- [ ] **Title System**: All 4 acquisition methods award correctly. Bonus aggregation sums accurately.
- [ ] **Class System**: Tag-driven tool bonuses calculate correctly for all 6 classes.
- [ ] **Dungeon System**: Wave spawning, 2x EXP, loot chest generation all work.
- [ ] **Potion System**: All tag types (healing, mana, buff, resistance, utility) apply correctly with quality scaling.
- [ ] **Turret System**: Targeting, cooldown, stun/freeze prevention, bomb/trap triggers all function.
- [ ] **No Pygame imports**: Zero references to pygame in any Phase 4 C# file.
- [ ] **Thread safety**: TagRegistry and other singletons are safe for concurrent reads.
- [ ] **Unit tests**: 100+ tests across all systems with >90% code coverage on formulas.

---

## 9. Estimated Effort

| Subsystem | Estimated Days | Risk Level |
|---|---|---|
| Tag System (3 files) | 2 | Low |
| Geometry + Math Utils | 1 | Low |
| Effect Executor | 3 | Medium |
| Difficulty + Reward Calculators | 2 | Low |
| Smithing Minigame | 2 | Medium |
| Alchemy Minigame | 3 | High (oscillation formulas) |
| Refining Minigame | 2 | Medium |
| Engineering Minigame | 3 | High (BFS validation) |
| Enchanting Minigame | 2 | Medium |
| Interactive Crafting (UI layouts) | 3 | Medium |
| Collision System + A* | 2 | Medium |
| World System + Biome + Chunk | 4 | High (determinism) |
| Combat Manager (split into 3) | 4 | High (formula accuracy) |
| Dungeon System | 2 | Medium |
| Save/Load | 3 | High (roundtrip fidelity) |
| Support Systems (5 files) | 3 | Low |
| Integration Testing | 3 | Medium |
| **Total** | **~44 days** | |

---

## 10. Risk Mitigation

### 10.1 Formula Drift
**Risk**: C# floating-point produces different results than Python.
**Mitigation**: Use `float` consistently (not `double`). Write comparison tests that run both Python and C# on identical inputs. Accept tolerance of +/-0.01.

### 10.2 Random Number Divergence
**Risk**: Different RNG implementations break deterministic world generation.
**Mitigation**: Use `System.Random` with explicit seed for all deterministic systems. Write seed-comparison tests against Python `random.Random`.

### 10.3 Crafting Minigame Complexity
**Risk**: 5,525 lines of minigame code with intricate formulas.
**Mitigation**: Port one minigame at a time. Write formula-level unit tests before porting full minigame. Start with Smithing (simplest formulas), end with Engineering (BFS complexity).

### 10.4 Save Format Compatibility
**Risk**: C# serialization produces JSON that differs from Python format.
**Mitigation**: Use `[JsonProperty]` attributes to match Python key names exactly. Write roundtrip test: Python save -> C# load -> C# save -> compare JSON structure.

### 10.5 CombatManager Size
**Risk**: 2,009 lines is too large for a single migration unit.
**Mitigation**: Split into DamageCalculator, EnemySpawner, CombatManager before porting. Port and test DamageCalculator first (pure math, easy to verify).

---

## 11. 3D Readiness (Phase 4 Responsibilities)

Phase 4 is where 3D readiness matters most — combat geometry, pathfinding, and world systems all currently assume 2D.

### 11.1 Combat Geometry — TargetFinder

All AoE geometry (circle, cone, beam, pierce, chain) must use the `TargetFinder` utility class with configurable `DistanceMode`:

```csharp
// TargetFinder.Mode = DistanceMode.Horizontal (default — matches Python 2D behavior)
// TargetFinder.Mode = DistanceMode.Full3D (future — when vertical gameplay added)
```

Python's `effect_executor.py` AoE calculations (lines 89-190) port to `TargetFinder.FindInRadius()`, `FindInCone()`, `FindInBeam()`. These methods use `GetDistance()` which respects the mode toggle.

**Test**: Same inputs must produce same targets in Horizontal mode as Python produces in 2D.

### 11.2 Pathfinding — IPathfinder Interface

`collision_system.py` (599 lines) uses A* on a 2D tile grid. Port as `GridPathfinder` implementing `IPathfinder`:

```csharp
public interface IPathfinder
{
    List<GamePosition> FindPath(GamePosition start, GamePosition end);
    bool HasLineOfSight(GamePosition from, GamePosition to);
    bool IsWalkable(GamePosition position);
}
```

This enables swapping to `NavMeshPathfinder` later without changing any combat or AI code.

### 11.3 World System — Tile-to-World Conversion

Centralize all tile-to-world coordinate conversions:

```csharp
public class WorldSystem
{
    public Vector3 TileToWorld(int tileX, int tileZ)
        => new Vector3(tileX * GameConfig.TileSize, GetHeight(tileX, tileZ), tileZ * GameConfig.TileSize);

    // Returns 0 for flat world. Future: terrain heightmap lookup.
    private float GetHeight(int tileX, int tileZ) => 0f;
}
```

### 11.4 Crafting Base Class (MACRO-8)

All 5 crafting minigames share ~1,240 lines of duplicated code. Port as:
- `BaseCraftingMinigame` — abstract class with shared lifecycle (timer, state, completion, performance calculation)
- Concrete classes (`SmithingMinigame`, `AlchemyMinigame`, etc.) implement only discipline-specific mechanics

See `IMPROVEMENTS.md` MACRO-8 for full code.

### 11.5 Effect Dispatch Table (MACRO-5)

The 250-line if/elif chain in `skill_manager.py:315-567` becomes a `SkillEffectDispatcher` with pluggable handlers. See `IMPROVEMENTS.md` MACRO-5.
