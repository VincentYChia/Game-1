# Phase Contracts: Inputs, Outputs & Integration Points

**Purpose**: Every phase has a formal contract. A developer can read ONLY this document + their phase document and know exactly what they receive and what they must deliver. This is the bridge that enables modular, parallel work.

**Rule**: If you start a phase, verify ALL inputs exist before writing code. If an input is missing, the upstream phase is not complete — do NOT proceed.

---

## How to Read This Document

Each phase has three sections:
1. **RECEIVES** — What must exist before you start (files, classes, interfaces)
2. **DELIVERS** — What you must produce (files, classes, tests, quality gate)
3. **INTEGRATION POINTS** — Exact method signatures other phases will call on your code

A developer working on Phase 3 reads:
- Phase 3 RECEIVES → verify Phase 1 and 2 outputs exist
- Phase 3 DELIVERS → this is what you build
- Phase 3 INTEGRATION POINTS → this is the public API other phases depend on

---

## Phase 1: Foundation (Data Models, Enums, JSON Schemas)

### RECEIVES
Nothing. Phase 1 has zero dependencies.

**Prerequisites**:
- C# compiler (C# 9+ for records/pattern matching)
- Newtonsoft.Json NuGet package
- Unity 2022.3 LTS or later
- Python source at `Game-1-modular/` for reference

### DELIVERS

**13 Model Files** (namespace `Game1.Data.Models`):
| C# File | Key Class | Must Support |
|---------|-----------|-------------|
| `MaterialDefinition.cs` | `MaterialDefinition` | JSON deserialization via `[JsonProperty]`, equality by `MaterialId` |
| `EquipmentItem.cs` | `EquipmentItem` | `Copy()`, `CanEquip(int level)`, `GetEffectiveness()` → `durability == 0 ? 0.5f : durability / maxDurability` |
| `SkillDefinition.cs` | `SkillDefinition` | Nested `SkillEffect`, `SkillCost`, `SkillEvolution`, `SkillRequirements` |
| `Recipe.cs` | `Recipe` | `IsEnchantment` flag, `Inputs` as `List<RecipeInput>` |
| `PlacementData.cs` | `PlacementData` | Discipline-specific fields (grid_size for smithing, ingredients for alchemy, etc.) |
| `TitleDefinition.cs` | `TitleDefinition` | `Bonuses` as `Dictionary<string, float>` |
| `ClassDefinition.cs` | `ClassDefinition` | `Tags` as `List<string>`, `Bonuses` as `Dictionary<string, float>` |
| `NPCDefinition.cs` | `NPCDefinition` | Position as `(float X, float Y, float Z)` |
| `QuestDefinition.cs` | `QuestDefinition` | `QuestObjective`, `QuestRewards` nested classes |
| `ResourceNodeDefinition.cs` | `ResourceNodeDefinition` | `Drops` as `List<ResourceDrop>` |
| `SkillUnlock.cs` | `SkillUnlock` | `UnlockRequirements`, `UnlockTrigger`, `UnlockCost` |
| `StatusEffectData.cs` | `StatusEffectData` | `StatusEffectType` enum, `StackBehavior` enum |
| `TagDefinition.cs` | `TagDefinition` | `Conflicts`, `Synergies` as `List<string>` |

**7 Enum Files** (namespace `Game1.Data.Enums`):
| C# File | Enum | Values |
|---------|------|--------|
| `DamageType.cs` | `DamageType` | Physical, Fire, Ice, Lightning, Poison, Arcane, Shadow, Holy |
| `Rarity.cs` | `Rarity` | Common, Uncommon, Rare, Epic, Legendary, Artifact |
| `EquipmentSlot.cs` | `EquipmentSlot` | MainHand, OffHand, Head, Chest, Legs, Feet, Hands, Accessory |
| `TileType.cs` | `TileType` | Grass, Water, Stone, Sand, DirtPath, Tree, Ore, CraftingStation, etc. |
| `StatusEffectType.cs` | `StatusEffectType` | Burn, Bleed, Poison, Freeze, Stun, Root, Slow, Shock, etc. |
| `CraftingDiscipline.cs` | `CraftingDiscipline` | Smithing, Alchemy, Refining, Engineering, Enchanting, Fishing |
| `ResourceCategory.cs` | `ResourceCategory` | Metal, Wood, Stone, MonsterDrop, Gem, Herb, Fabric, Elemental |

**Every enum MUST have**:
- `[JsonConverter(typeof(StringEnumConverter))]` attribute for JSON compatibility
- Extension method `ToJsonString()` returning lowercase (e.g., `DamageType.Fire.ToJsonString()` → `"fire"`)
- Static method `FromJsonString(string)` for deserialization

**Verification tests (80+ unit tests)**:
- Every model deserializes from sample JSON
- Every model roundtrips (serialize → deserialize → equal)
- Every enum converts to/from string correctly
- `EquipmentItem.GetEffectiveness()` returns 0.5 when durability is 0
- `EquipmentItem.Copy()` produces independent instance (deep copy)

### INTEGRATION POINTS

Phase 2 will call:
```csharp
// Deserialize JSON into models
var materials = JsonConvert.DeserializeObject<List<MaterialDefinition>>(json);
var equipment = JsonConvert.DeserializeObject<List<EquipmentItem>>(json);
var recipes = JsonConvert.DeserializeObject<List<Recipe>>(json);

// Access model properties
string id = material.MaterialId;
int tier = material.Tier;
string category = material.Category;

// Equipment methods
var copy = equipment.Copy();
bool canEquip = equipment.CanEquip(playerLevel: 10);
float effectiveness = equipment.GetEffectiveness();
```

Phase 3 will call:
```csharp
// Character components use models directly
var stats = new CharacterStats();
var inventory = new Inventory(maxSlots: 30);
inventory.AddItem(materialDefinition, quantity: 5);
var equippedItem = equipmentItem.Copy(); // Always work on copies
```

---

## Phase 2: Data Layer (Databases, Config, JSON Loading)

### RECEIVES

**From Phase 1**:
- All 13 model classes compile and have `[JsonProperty]` attributes
- All 7 enum classes compile with `ToJsonString()`/`FromJsonString()` methods
- `EquipmentItem.Copy()` works (deep copy)
- Sample JSON roundtrip tests pass

**Verify before starting**:
```csharp
// This must compile and work:
string json = File.ReadAllText("test-materials.json");
var materials = JsonConvert.DeserializeObject<MaterialWrapper>(json);
Assert.IsNotNull(materials.Materials[0].MaterialId);
```

### DELIVERS

**14 Database Files** (namespace `Game1.Data.Databases`):
| C# File | Singleton Class | Key Methods |
|---------|----------------|-------------|
| `MaterialDatabase.cs` | `MaterialDatabase.Instance` | `LoadFromFile(path)`, `GetMaterial(id) → MaterialDefinition?` |
| `EquipmentDatabase.cs` | `EquipmentDatabase.Instance` | `LoadFromFile(path)`, `CreateEquipmentFromId(id) → EquipmentItem?`, `IsEquipment(id) → bool` |
| `RecipeDatabase.cs` | `RecipeDatabase.Instance` | `LoadFromFiles(basePath)`, `GetRecipesForStation(type, tier) → List<Recipe>`, `CanCraft(recipe, inventory) → bool` |
| `SkillDatabase.cs` | `SkillDatabase.Instance` | `LoadFromFile(path)`, `GetSkill(id) → SkillDefinition?`, `GetManaCost(value) → int`, `GetCooldownSeconds(value) → float` |
| `PlacementDatabase.cs` | `PlacementDatabase.Instance` | `LoadFromFiles(basePath) → int`, `GetPlacement(recipeId) → PlacementData?` |
| `TitleDatabase.cs` | `TitleDatabase.Instance` | `LoadFromFile(path)`, titles by id |
| `ClassDatabase.cs` | `ClassDatabase.Instance` | `LoadFromFile(path)`, classes by id |
| `NPCDatabase.cs` | `NPCDatabase.Instance` | `LoadFromFiles()`, NPCs and quests by id |
| `ResourceNodeDatabase.cs` | `ResourceNodeDatabase.Instance` | `LoadFromFile(path)`, `GetResourcesForChunk(chunkType, tierRange)` |
| `SkillUnlockDatabase.cs` | `SkillUnlockDatabase.Instance` | `LoadFromFile(path)`, `GetUnlockForSkill(skillId)` |
| `TranslationDatabase.cs` | `TranslationDatabase.Instance` | `LoadFromFiles(basePath)` |
| `WorldGenerationConfig.cs` | `WorldGenerationConfig.Instance` | `GetDangerDistribution(distance)`, `GetResourceConfig(dangerLevel)` |
| `MapWaypointConfig.cs` | `MapWaypointConfig.Instance` | `GetBiomeColor(chunkType)`, `GetMaxWaypointsForLevel(level)` |
| `UpdateLoader.cs` | (static class) | `LoadAllUpdates(projectRoot)` |

**2 Config Files** (namespace `Game1.Core`):
| C# File | Class | Key Constants |
|---------|-------|---------------|
| `GameConfig.cs` | `GameConfig` | `BaseWidth=1600`, `BaseHeight=900`, `FPS=60`, `ChunkSize=16`, `TileSize=32`, `MaxLevel=30`, all rarity colors |
| `GamePaths.cs` | `GamePaths` | `GetContentPath(relative)`, `GetIconPath(category, id)` |

**1 Utility File**:
| C# File | Class | Purpose |
|---------|-------|---------|
| `JsonLoader.cs` | `JsonLoader` | Centralized JSON loading from StreamingAssets (see CONVENTIONS.md §4) |

**1 Initialization File**:
| C# File | Class | Purpose |
|---------|-------|---------|
| `DatabaseInitializer.cs` | `DatabaseInitializer` | `InitializeAll()` loads all databases in correct order |

**Database initialization order** (enforced by `DatabaseInitializer.InitializeAll()`):
```csharp
public static class DatabaseInitializer
{
    public static void InitializeAll()
    {
        // Group 1: No dependencies (can be parallel in theory)
        TranslationDatabase.Instance.LoadFromFiles();
        WorldGenerationConfig.Instance; // loads in constructor
        MapWaypointConfig.Instance;     // loads in constructor
        ClassDatabase.Instance.LoadFromFile("progression/classes-1.JSON");
        ResourceNodeDatabase.Instance.LoadFromFile("Definitions.JSON/resource-node-1.JSON");

        // Group 2: Standalone loaders
        MaterialDatabase.Instance.LoadFromFile("items.JSON/items-materials-1.JSON");
        MaterialDatabase.Instance.LoadRefiningItems("items.JSON/items-refining-1.JSON");
        MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-alchemy-1.JSON");
        MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-engineering-1.JSON");
        MaterialDatabase.Instance.LoadStackableItems("items.JSON/items-tools-1.JSON");

        // Group 3: Equipment (uses SmithingTagProcessor for slot detection)
        EquipmentDatabase.Instance.LoadFromFile("items.JSON/items-smithing-2.JSON");
        EquipmentDatabase.Instance.LoadFromFile("items.JSON/items-tools-1.JSON");

        // Group 4: Content databases
        SkillDatabase.Instance.LoadFromFile("Skills/skills-skills-1.JSON");
        RecipeDatabase.Instance.LoadFromFiles();
        PlacementDatabase.Instance.LoadFromFiles();
        TitleDatabase.Instance.LoadFromFile("progression/titles-1.JSON");
        SkillUnlockDatabase.Instance.LoadFromFile("progression/skill-unlocks.JSON");
        NPCDatabase.Instance.LoadFromFiles();

        // Group 5: Update packages (post-init accumulation)
        UpdateLoader.LoadAllUpdates();
    }
}
```

**Verification tests (60+ unit tests)**:
- Each database loads correct number of items (e.g., MaterialDatabase: 57+)
- Each database returns null for unknown IDs (not exception)
- Translation tables: `GetManaCost("moderate") == 60`, `GetCooldownSeconds("short") == 120f`
- WorldGenerationConfig: danger at spawn distance 0 is 100% peaceful
- Full initialization sequence completes without errors
- Each database creates fallback placeholders when JSON missing

### INTEGRATION POINTS

Phase 3 will call:
```csharp
// Lookup materials by ID
var mat = MaterialDatabase.Instance.GetMaterial("iron_ore");

// Create equipment instances
var sword = EquipmentDatabase.Instance.CreateEquipmentFromId("iron_sword");

// Check skill costs
int manaCost = SkillDatabase.Instance.GetManaCost("moderate"); // 60

// Get class definitions
var warrior = ClassDatabase.Instance.Classes["warrior"];
```

Phase 4 will call:
```csharp
// Get recipes for a crafting station
var recipes = RecipeDatabase.Instance.GetRecipesForStation("smithing", tier: 2);

// Check if player can craft
bool canCraft = RecipeDatabase.Instance.CanCraft(recipe, character.Inventory);

// Get placement data for minigame
var placement = PlacementDatabase.Instance.GetPlacement("smithing_iron_sword_001");

// World generation config
var danger = WorldGenerationConfig.Instance.GetDangerDistribution(chunkDistance: 5);
```

Phase 5 will call:
```csharp
// ML preprocessing needs material lookups
var mat = MaterialDatabase.Instance.GetMaterial(materialId);
string category = mat.Category;   // "metal", "wood", etc.
int tier = mat.Tier;              // 1-4
```

---

## Phase 3: Entity Layer (Character, Components, Enemies)

### RECEIVES

**From Phase 1**: All model classes and enums compile
**From Phase 2**: All databases load and query correctly. `DatabaseInitializer.InitializeAll()` succeeds.

**Verify before starting**:
```csharp
DatabaseInitializer.InitializeAll();
Assert.IsTrue(MaterialDatabase.Instance.Loaded);
Assert.IsTrue(EquipmentDatabase.Instance.Loaded);
Assert.IsTrue(SkillDatabase.Instance.Loaded);
var ironOre = MaterialDatabase.Instance.GetMaterial("iron_ore");
Assert.IsNotNull(ironOre);
```

### DELIVERS

**Character class** (`Game1.Entities/Character.cs`):
- Properties: `Name`, `Level`, `Experience`, `ClassId`, `TitleId`, `Position`
- Components: `Stats`, `Inventory`, `Equipment`, `SkillManager`, `Buffs`, `Leveling`, `StatTracker`
- Methods: `Initialize()`, `GainExperience(int)`, `LevelUp()`
- Component initialization order: Stats → Leveling → Skills → Buffs → Equipment → Inventory → Titles → Class → Activities

**11 Component classes** (`Game1.Entities.Components/`):
| C# File | Class | Key Methods |
|---------|-------|-------------|
| `CharacterStats.cs` | `CharacterStats` | `GetStatBonus(stat)` → STR: +5% dmg, DEF: +2% red, VIT: +15 HP, LCK: +2% crit, AGI: +5% forestry, INT: -2% diff +20 mana |
| `Inventory.cs` | `Inventory` | `AddItem(id, qty) → bool`, `RemoveItem(id, qty) → bool`, `HasItem(id, qty) → bool`, `GetItemCount(id) → int` |
| `EquipmentManager.cs` | `EquipmentManager` | `Equip(EquipmentItem, slot) → EquipmentItem?` (returns unequipped), `Unequip(slot) → EquipmentItem?` |
| `SkillManager.cs` | `SkillManager` | `LearnSkill(id) → bool`, `ActivateSkill(id) → bool`, `IsOnCooldown(id) → bool`, `GetActiveBuffs() → List` |
| `LevelingSystem.cs` | `LevelingSystem` | `GainExperience(int)`, `GetExpForLevel(level) → int` = `200 * 1.75^(level-1)`, `CanLevelUp() → bool` |
| `BuffManager.cs` | `BuffManager` | `AddBuff(type, magnitude, duration)`, `RemoveBuff(type)`, `GetActiveBuffs()`, `Update(deltaTime)` |
| `StatTracker.cs` | `StatTracker` | `RecordActivity(type, count)`, `GetActivityCount(type) → int` (for title/unlock checks) |

**Enemy class** (`Game1.Entities/Enemy.cs`):
- `EnemyDefinition` loaded from `hostiles-1.JSON`
- AI states: `Idle`, `Patrol`, `Chase`, `Attack`, `Flee`, `Dead`
- Methods: `TakeDamage(float) → bool (died)`, `Update(deltaTime)`, `GetLootDrops() → List`

**17 Status effects** (`Game1.Entities/StatusEffect.cs` + `StatusEffectManager.cs`):
- Abstract base: `StatusEffect` with `Apply()`, `Tick(dt)`, `Remove()`
- Concrete: Burn, Bleed, Poison, Freeze, Stun, Root, Slow, Shock, Empower, Fortify, Haste, Regeneration, Shield, Vulnerable, Weaken, Phase, Invisible

**Verification tests (50+)**:
- Character creates with correct default stats
- Inventory add/remove/has operations work
- Equipment equip/unequip returns correct items
- Leveling: level 1 needs 200 EXP, level 2 needs 350 EXP, level 10 needs 14,880 EXP
- Status effects tick correctly (e.g., Burn: `dps * stacks * dt` damage per tick)
- Enemy AI state transitions work

### INTEGRATION POINTS

Phase 4 will call:
```csharp
// Combat system needs:
float damage = character.Stats.GetStatBonus("STR");  // 1.0 + STR * 0.05
var weapon = character.Equipment.GetEquipped(EquipmentSlot.MainHand);
bool isDead = enemy.TakeDamage(finalDamage);

// Crafting system needs:
bool hasMats = character.Inventory.HasItem("iron_ingot", 3);
character.Inventory.RemoveItem("iron_ingot", 3);
character.Inventory.AddItem("iron_sword", 1);

// Skill system needs:
bool activated = character.SkillManager.ActivateSkill("fireball");
int manaCost = character.SkillManager.GetManaCost("fireball");
```

Phase 6 will call:
```csharp
// UI needs:
string name = character.Name;
int level = character.Level;
float hp = character.Stats.CurrentHealth;
float maxHp = character.Stats.MaxHealth;
var inventorySlots = character.Inventory.GetAllSlots();
var equippedItems = character.Equipment.GetAllEquipped();
```

---

## Phase 4: Game Systems (Combat, Crafting, World, Tags, Save/Load)

### RECEIVES

**From Phase 1**: All models and enums
**From Phase 2**: All databases initialized
**From Phase 3**: Character, Enemy, Components, StatusEffects all working

**Verify before starting**:
```csharp
DatabaseInitializer.InitializeAll();
var character = new Character("TestPlayer", "warrior");
character.Stats.SetStat("STR", 10);
var sword = EquipmentDatabase.Instance.CreateEquipmentFromId("iron_sword");
character.Equipment.Equip(sword, EquipmentSlot.MainHand);
Assert.IsNotNull(character.Equipment.GetEquipped(EquipmentSlot.MainHand));
```

### DELIVERS

**Tag System** (`Game1.Systems.Tags/`):
- `TagRegistry.cs`: Loads tag-definitions.JSON, resolves aliases, checks conflicts
- `TagParser.cs`: Parses `List<string>` tags → `EffectConfig` with geometry, damage types, status effects
- `EffectContext.cs`: `EffectConfig` and `EffectContext` data classes

**Effect Execution** (`Game1.Systems.Effects/`):
- `EffectExecutor.cs`: Executes tag-based effects (damage, healing, status, knockback, lifesteal, etc.)
- `TargetFinder.cs`: Geometry patterns (single, chain, cone, circle, beam, pierce)
- `MathUtils.cs`: Distance, angle, LOS calculations

**Combat** (`Game1.Systems.Combat/`):
- `CombatManager.cs`: Full damage pipeline, enemy spawning, death/loot handling
  - `CalculateDamage(attacker, target) → float` — THE critical method
  - Damage pipeline must match Python exactly (see MIGRATION_PLAN.md §6.1)

**Crafting** (`Game1.Systems.Crafting/`):
- 6 minigame classes: `SmithingMinigame`, `AlchemyMinigame`, `RefiningMinigame`, `EngineeringMinigame`, `EnchantingMinigame`, `FishingMinigame`
- `DifficultyCalculator.cs`: Material point calculation → difficulty tier
- `RewardCalculator.cs`: Performance score → quality tier → item stats
- `InteractiveCrafting.cs`: Base UI factory for all disciplines

**World** (`Game1.Systems.World/`):
- `WorldSystem.cs`: Chunk streaming, resource spawning, entity placement
- `BiomeGenerator.cs`: Deterministic from seed (Szudzik pairing function)
- `Chunk.cs`: 16×16 tile grid with resource spawning
- `CollisionSystem.cs`: Bresenham LOS, A* pathfinding

**Save/Load** (`Game1.Systems.Save/`):
- `SaveManager.cs`: Full state serialization (character, world, quests, dungeons)
- Save format: JSON v3.0 (same as Python, backward compatible)

**Support Systems**:
- `DungeonSystem.cs`, `QuestSystem.cs`, `TitleSystem.cs`, `ClassSystem.cs`
- `SkillUnlockSystem.cs`, `PotionSystem.cs`, `TurretSystem.cs`

**Verification tests (100+)**:
- Damage pipeline test cases (see Phase 4 document §7 for exact values)
- All 6 minigame formulas produce correct results for known inputs
- World generation deterministic: seed 12345 produces identical world
- A* pathfinding finds valid paths
- Save → Load roundtrip preserves all state

### INTEGRATION POINTS

Phase 5 will call:
```csharp
// Crafting flow calls classifier before minigame
var result = ClassifierManager.Instance.Validate(discipline, placement);
if (result.IsValid && result.Confidence > 0.7f)
{
    // Proceed to minigame
}
```

Phase 6 will call:
```csharp
// GameManager needs:
CombatManager.Instance.ProcessCombat(deltaTime);
WorldSystem.Instance.UpdateChunks(playerPosition);
SaveManager.Instance.SaveGame(character, world, "save_slot_1");
var loaded = SaveManager.Instance.LoadGame("save_slot_1");

// UI needs:
var recipes = RecipeDatabase.Instance.GetRecipesForStation("smithing", 1);
var difficulty = DifficultyCalculator.Calculate(recipe, materials);
var reward = RewardCalculator.Calculate(performance, difficulty);
```

---

## Phase 5: ML Classifiers

### RECEIVES

**From Phase 1**: `MaterialDefinition`, `PlacementData` models
**From Phase 2**: `MaterialDatabase.Instance` initialized (for category/tier lookups in preprocessing)

**Verify before starting**:
```csharp
DatabaseInitializer.InitializeAll();
var mat = MaterialDatabase.Instance.GetMaterial("iron_ore");
Assert.AreEqual("metal", mat.Category);
Assert.AreEqual(1, mat.Tier);
```

**IMPORTANT**: Phase 5 does NOT depend on Phase 3 or 4. It CAN run in parallel with them. But it DOES depend on Phase 2 for MaterialDatabase.

### DELIVERS

**ClassifierManager** (`Game1.Systems.ML/`):
- `ClassifierManager.cs`: `Validate(discipline, placement) → ClassifierResult`
- `ClassifierResult`: `IsValid`, `Confidence`, `Discipline`
- 5 preprocessors: `SmithingPreprocessor`, `AdornmentPreprocessor`, `AlchemyFeatureExtractor`, `RefiningFeatureExtractor`, `EngineeringFeatureExtractor`
- ONNX model loading via Unity Sentis

**Golden file tests (40+)**:
- Every preprocessor compared against Python-generated golden files
- Image pixel tolerance: ±0.001 per pixel
- Feature vector tolerance: ±0.0001 per feature
- Prediction match: same valid/invalid classification

### INTEGRATION POINTS

Phase 4 calls:
```csharp
var result = ClassifierManager.Instance.Validate("smithing", placementData);
// result.IsValid: bool
// result.Confidence: float 0.0-1.0
```

---

## Phase 6: Unity Integration (Rendering, Input, UI, GameManager)

### RECEIVES

**From ALL prior phases**:
- Phase 1: Models compile
- Phase 2: Databases load
- Phase 3: Character, Enemy, Components work
- Phase 4: Combat, Crafting, World, Save/Load work
- Phase 5: ML classifiers work

**Verify before starting**:
```csharp
// Full integration test
DatabaseInitializer.InitializeAll();
var character = new Character("TestPlayer", "warrior");
character.Stats.SetStat("STR", 5);

var sword = EquipmentDatabase.Instance.CreateEquipmentFromId("iron_sword");
character.Equipment.Equip(sword, EquipmentSlot.MainHand);

// Combat works
float damage = CombatManager.Instance.CalculateDamage(character, testEnemy);
Assert.Greater(damage, 0);

// Crafting works
var recipes = RecipeDatabase.Instance.GetRecipesForStation("smithing", 1);
Assert.Greater(recipes.Count, 0);

// World works
var world = new WorldSystem(seed: 12345);
var chunk = world.GetChunk(0, 0);
Assert.IsNotNull(chunk);

// Save/Load works
SaveManager.Instance.SaveGame(character, world, "test");
var loaded = SaveManager.Instance.LoadGame("test");
Assert.IsNotNull(loaded);
```

### DELIVERS

**MonoBehaviour Components**:
- `GameManager.cs`: Lifecycle orchestration (Awake → databases, Start → character/UI)
- `GameStateManager.cs`: State machine (MainMenu, Playing, Crafting, Combat, Paused, Dead)
- `PlayerController.cs`: Movement, interaction, input routing
- `CameraController.cs`: Follow camera with chunk-based visibility
- `WorldRenderer.cs`: Tilemap rendering from WorldSystem data
- `UIManager.cs`: Panel orchestration
- All crafting UIs, combat HUD, inventory panel, equipment panel, skill panel

**Scene Setup**:
- Main scene with GameManager, Camera, Canvas, EventSystem
- Prefabs for enemies, resources, UI panels

### INTEGRATION POINTS

Phase 7 calls:
```csharp
// LLM stub needs notification system
NotificationSystem.Show("[LLM STUB] Item generated", NotificationType.Debug);

// E2E tests need GameManager
GameManager.Instance.StartNewGame("TestPlayer", "warrior");
GameManager.Instance.LoadGame("test_save");
```

---

## Phase 7: Polish & LLM Stub

### RECEIVES

**From ALL prior phases**: Everything works. Full game loop functional.

**Verify before starting**: Play the game for 5 minutes without crashes.

### DELIVERS

- `IItemGenerator.cs`: Interface for LLM-based item generation
- `StubItemGenerator.cs`: Placeholder implementation with debug notifications
- `NotificationSystem.cs`: On-screen notification queue
- E2E test suite (10 scenarios)
- Migration Completion Report

### INTEGRATION POINTS

Future (post-migration) work will replace `StubItemGenerator` with `AnthropicItemGenerator` that makes real API calls. The `IItemGenerator` interface ensures this is a drop-in replacement.

---

## Cross-Phase Dependency Matrix

```
         Phase 1   Phase 2   Phase 3   Phase 4   Phase 5   Phase 6   Phase 7
Phase 1    -
Phase 2   NEEDS      -
Phase 3   NEEDS    NEEDS       -
Phase 4   NEEDS    NEEDS     NEEDS       -
Phase 5   NEEDS    NEEDS       -         -          -
Phase 6   NEEDS    NEEDS     NEEDS     NEEDS      NEEDS       -
Phase 7   NEEDS    NEEDS     NEEDS     NEEDS      NEEDS     NEEDS       -
```

**Parallel opportunities**:
- Phase 5 can start once Phase 2 is complete (doesn't need Phase 3 or 4)
- Phase 3 and Phase 5 can run in parallel
- Everything else is sequential

---

## Quick Verification Commands

### Phase 1 Complete?
```csharp
// Does MaterialDefinition deserialize?
var json = "{\"materialId\":\"iron_ore\",\"name\":\"Iron Ore\",\"tier\":1,\"category\":\"metal\"}";
var mat = JsonConvert.DeserializeObject<MaterialDefinition>(json);
Assert.AreEqual("iron_ore", mat.MaterialId);
Assert.AreEqual(1, mat.Tier);
```

### Phase 2 Complete?
```csharp
DatabaseInitializer.InitializeAll();
Assert.AreEqual(60, SkillDatabase.Instance.GetManaCost("moderate"));
Assert.IsTrue(MaterialDatabase.Instance.GetMaterial("iron_ore") != null);
```

### Phase 3 Complete?
```csharp
var character = new Character("Test", "warrior");
character.Inventory.AddItem("iron_ore", 5);
Assert.AreEqual(5, character.Inventory.GetItemCount("iron_ore"));
```

### Phase 4 Complete?
```csharp
// Damage calculation test
var character = new Character("Test", "warrior");
character.Stats.SetStat("STR", 10);
// ... setup weapon, enemy
float dmg = CombatManager.Instance.CalculateDamage(character, enemy);
Assert.AreEqual(expectedDamage, dmg, 0.01f);
```

### Phase 5 Complete?
```csharp
var placement = LoadTestPlacement("smithing_test_001.json");
var result = ClassifierManager.Instance.Validate("smithing", placement);
Assert.IsNotNull(result);
Assert.IsTrue(result.Confidence >= 0f && result.Confidence <= 1f);
```

### Phase 6 Complete?
```
1. Open Unity scene
2. Press Play
3. Character spawns, world renders, can move
4. Can open inventory, crafting, skills panels
5. No errors in console
```

### Phase 7 Complete?
```
1. Place materials in crafting grid → LLM stub called → debug notification appears
2. Play for 30 minutes → zero runtime errors
3. Save → Quit → Load → state preserved
```
