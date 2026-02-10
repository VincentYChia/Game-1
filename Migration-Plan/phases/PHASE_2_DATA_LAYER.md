# Phase 2: Data Layer Migration
## Database Singletons, Configuration Loading, and JSON File Management

**Phase**: 2 of 10
**Depends On**: Phase 1 (Data Models & Enums)
**Estimated Scope**: 15 database files + 2 config files (~3,500 lines Python -> ~4,200 lines C#)
**Created**: 2026-02-10

---

## 1. Overview

### Goal
Port all 13 database singleton classes, the update loader module, and the configuration system to C# with full JSON loading support. Every database must load the same JSON files used by the Python version, produce identical data structures, and expose equivalent query methods.

### Dependency
Phase 1 must be complete: all data models (MaterialDefinition, EquipmentItem, Recipe, PlacementData, SkillDefinition, TitleDefinition, ClassDefinition, NPCDefinition, QuestDefinition, ResourceNodeDefinition, SkillUnlock, etc.) and all enums must compile successfully in C# before Phase 2 begins.

### Deliverables
1. **13 Database C# classes** in `Game1.Data.Databases/` namespace
2. **1 UpdateLoader C# class** for dynamic content loading from Update-N directories
3. **1 GameConfig C# class** porting all Config constants
4. **1 GamePaths C# class** porting the PathManager singleton
5. **JSON loading infrastructure** (Newtonsoft.Json integration, deserialization helpers)
6. **Unit tests** for every database (load, query, fallback)
7. **Integration test** for full initialization sequence

---

## 2. Systems Included

### 2.1 Database Singletons (15 files, ~3,156 lines)

| # | Python File | C# Target | Lines | Singleton Class | Primary JSON Files |
|---|-------------|-----------|-------|-----------------|-------------------|
| 1 | `data/databases/material_db.py` | `Game1.Data.Databases/MaterialDatabase.cs` | 203 | MaterialDatabase | `items.JSON/items-materials-1.JSON`, `items.JSON/items-refining-1.JSON` |
| 2 | `data/databases/equipment_db.py` | `Game1.Data.Databases/EquipmentDatabase.cs` | 401 | EquipmentDatabase | `items.JSON/items-smithing-2.JSON`, `items.JSON/items-alchemy-1.JSON`, `items.JSON/items-engineering-1.JSON`, `items.JSON/items-tools-1.JSON` |
| 3 | `data/databases/recipe_db.py` | `Game1.Data.Databases/RecipeDatabase.cs` | 212 | RecipeDatabase | `recipes.JSON/recipes-smithing-3.json`, `recipes.JSON/recipes-alchemy-1.JSON`, `recipes.JSON/recipes-refining-1.JSON`, `recipes.JSON/recipes-engineering-1.JSON`, `recipes.JSON/recipes-adornments-1.json` |
| 4 | `data/databases/skill_db.py` | `Game1.Data.Databases/SkillDatabase.cs` | 123 | SkillDatabase | `Skills/skills-skills-1.JSON` |
| 5 | `data/databases/placement_db.py` | `Game1.Data.Databases/PlacementDatabase.cs` | 217 | PlacementDatabase | `placements.JSON/placements-smithing-1.JSON`, `placements.JSON/placements-refining-1.JSON`, `placements.JSON/placements-alchemy-1.JSON`, `placements.JSON/placements-engineering-1.JSON`, `placements.JSON/placements-adornments-1.JSON` |
| 6 | `data/databases/title_db.py` | `Game1.Data.Databases/TitleDatabase.cs` | 176 | TitleDatabase | `progression/titles-1.JSON` |
| 7 | `data/databases/class_db.py` | `Game1.Data.Databases/ClassDatabase.cs` | 109 | ClassDatabase | `progression/classes-1.JSON` |
| 8 | `data/databases/npc_db.py` | `Game1.Data.Databases/NPCDatabase.cs` | 147 | NPCDatabase | `progression/npcs-enhanced.JSON`, `progression/quests-enhanced.JSON` (fallback: `npcs-1.JSON`, `quests-1.JSON`) |
| 9 | `data/databases/resource_node_db.py` | `Game1.Data.Databases/ResourceNodeDatabase.cs` | 258 | ResourceNodeDatabase | `Definitions.JSON/Resource-node-1.JSON` |
| 10 | `data/databases/skill_unlock_db.py` | `Game1.Data.Databases/SkillUnlockDatabase.cs` | 138 | SkillUnlockDatabase | `progression/skill-unlocks.JSON` |
| 11 | `data/databases/translation_db.py` | `Game1.Data.Databases/TranslationDatabase.cs` | 53 | TranslationDatabase | `Definitions.JSON/skills-translation-table.JSON` |
| 12 | `data/databases/world_generation_db.py` | `Game1.Data.Databases/WorldGenerationConfig.cs` | 441 | WorldGenerationConfig | `Definitions.JSON/world_generation.JSON` |
| 13 | `data/databases/map_waypoint_db.py` | `Game1.Data.Databases/MapWaypointConfig.cs` | 301 | MapWaypointConfig | `Definitions.JSON/map-waypoint-config.JSON` |
| 14 | `data/databases/update_loader.py` | `Game1.Data.Databases/UpdateLoader.cs` | 364 | (module functions) | Dynamic: `Update-N/*.JSON` via `updates_manifest.json` |

### 2.2 Configuration (from core/)

| Python File | C# Target | Lines | Class |
|-------------|-----------|-------|-------|
| `core/config.py` | `Game1.Core/GameConfig.cs` | 200 | Config (all class variables) |
| `core/paths.py` | `Game1.Core/GamePaths.cs` | 146 | PathManager singleton |

---

## 3. Migration Steps

### 3.1 Singleton Pattern Decision

Three options were evaluated for porting the Python singleton pattern to C#:

**Option A: Manual Singletons (Recommended for Data Layer)**
```csharp
public class MaterialDatabase
{
    private static MaterialDatabase _instance;
    private static readonly object _lock = new object();

    public static MaterialDatabase GetInstance()
    {
        if (_instance == null)
        {
            lock (_lock)
            {
                if (_instance == null)
                    _instance = new MaterialDatabase();
            }
        }
        return _instance;
    }

    private MaterialDatabase() { }

    // For testing: allow resetting singleton
    internal static void ResetInstance() => _instance = null;
}
```

**Option B: ScriptableObject Singletons (Unity-native)**
- Better for Unity inspector configuration
- Requires asset creation in Unity Editor
- Not suitable for JSON-loaded data that must match Python exactly

**Option C: Dependency Injection (Zenject/VContainer)**
- Best long-term architecture
- Higher complexity for initial migration
- Consider for Phase 8+ refactoring

**Decision**: Use Option A for all 13 databases. This matches the Python pattern 1:1, requires no Unity-specific infrastructure, and allows trivial unit testing via `ResetInstance()`. Thread-safe via double-checked locking. Consider migrating to DI in a later phase once all systems are ported and stable.

### 3.2 JSON Loading Strategy

**JSON Library: Newtonsoft.Json (Json.NET)**

Unity's built-in `JsonUtility` cannot handle:
- `Dictionary<string, object>` types (used extensively in bonuses, properties, effectParams)
- Polymorphic deserialization
- camelCase to PascalCase mapping
- Nullable types

**Recommendation**: Use `Newtonsoft.Json` (available via Unity Package Manager as `com.unity.nuget.newtonsoft-json`).

**File Location Strategy**:
```
Unity Project/
  Assets/
    StreamingAssets/           <-- Moddable content (File.ReadAllText at runtime)
      Content/
        items.JSON/            <-- Copied from Python project
        recipes.JSON/
        placements.JSON/
        progression/
        Skills/
        Definitions.JSON/
        Update-N/              <-- Dynamic content packs
```

Use `StreamingAssets` (not `Resources`) because:
1. Files remain as-is on disk (moddable)
2. No Unity import step required for JSON
3. Matches Python's file-based loading pattern
4. Players can edit JSON files directly

**Loading Helper**:
```csharp
public static class JsonLoader
{
    public static string GetContentPath(string relativePath)
    {
        return Path.Combine(Application.streamingAssetsPath, "Content", relativePath);
    }

    public static T LoadJson<T>(string relativePath)
    {
        string fullPath = GetContentPath(relativePath);
        if (!File.Exists(fullPath))
        {
            Debug.LogWarning($"JSON file not found: {fullPath}");
            return default;
        }

        string json = File.ReadAllText(fullPath);
        return JsonConvert.DeserializeObject<T>(json);
    }

    public static JObject LoadRawJson(string relativePath)
    {
        string fullPath = GetContentPath(relativePath);
        if (!File.Exists(fullPath))
            return null;

        string json = File.ReadAllText(fullPath);
        return JObject.Parse(json);
    }
}
```

### 3.3 Per-Database Migration Instructions

---

#### 3.3.1 TranslationDatabase (53 lines -> ~80 lines C#)

**Python source**: `data/databases/translation_db.py`
**C# target**: `Game1.Data.Databases/TranslationDatabase.cs`
**JSON file**: `Definitions.JSON/skills-translation-table.JSON`
**Dependencies**: None

**Fields**:
```csharp
public Dictionary<string, float> MagnitudeValues { get; private set; }
public Dictionary<string, float> DurationSeconds { get; private set; }
public Dictionary<string, int> ManaCosts { get; private set; }
public Dictionary<string, float> CooldownSeconds { get; private set; }
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static TranslationDatabase GetInstance();
public void LoadFromFiles(string basePath = "");
```

**Loading Logic**:
- Parse `durationTranslations` section: for each key, extract `.seconds` value into `DurationSeconds`
- Parse `manaCostTranslations` section: for each key, extract `.cost` value into `ManaCosts`
- On failure, call `CreateDefaults()` with hardcoded values

**Hardcoded Default Values (MUST PRESERVE EXACTLY)**:
```csharp
MagnitudeValues = new Dictionary<string, float>
{
    { "minor", 0.5f }, { "moderate", 1.0f }, { "major", 2.0f }, { "extreme", 4.0f }
};
DurationSeconds = new Dictionary<string, float>
{
    { "instant", 0f }, { "brief", 15f }, { "moderate", 30f }, { "long", 60f }
};
ManaCosts = new Dictionary<string, int>
{
    { "low", 30 }, { "moderate", 60 }, { "high", 100 }
};
CooldownSeconds = new Dictionary<string, float>
{
    { "short", 120f }, { "moderate", 300f }, { "long", 600f }
};
```

**Special Notes**: The `SkillDatabase` also has its own inline translation tables that include `"extreme"` entries not present in TranslationDatabase defaults. SkillDatabase's inline tables are the canonical values. See Section 3.5 for full translation table values.

---

#### 3.3.2 WorldGenerationConfig (441 lines -> ~500 lines C#)

**Python source**: `data/databases/world_generation_db.py`
**C# target**: `Game1.Data.Databases/WorldGenerationConfig.cs`
**JSON file**: `Definitions.JSON/world_generation.JSON`
**Dependencies**: None

**Nested Config Classes to Port** (all are `@dataclass` in Python, become `[Serializable] public class` in C#):
- `ChunkLoadingConfig` (load_radius=4, spawn_always_loaded_radius=1, chunk_size=16)
- `BiomeDistributionConfig` (water=0.10, forest=0.50, cave=0.40) with `Validate()` method
- `BiomeClusteringConfig` (biome_noise_scale=4.0, biome_noise_octaves=3, danger_noise_scale=6.0)
- `DangerDistribution` (peaceful=0.5, dangerous=0.4, rare=0.1)
- `DangerZonesConfig` (safe_zone_radius=2, transition_zone_radius=10, three DangerDistribution sub-objects)
- `ResourceSpawnConfig` (min_resources, max_resources, tier_range as `(int, int)`)
- `ResourceSpawningConfig` (peaceful_chunks, dangerous_chunks, rare_chunks)
- `FishingSpotConfig` (min_spots, max_spots, tier_range)
- `WaterChunksConfig` (normal_water, cursed_swamp, lake/river/cursed_swamp chances)
- `DungeonSpawningConfig` (enabled=true, spawn_chance_per_chunk=0.083, etc.)
- `SpawnAreaConfig` (resource_exclusion_radius=8, crafting_stations_enabled=true)
- `ChunkUnloadingConfig` (enabled=true, save_modified_chunks=true, track_unload_time=true)
- `DebugConfig` (log_chunk_generation=false, log_biome_assignments=false, etc.)

**Public Methods**:
```csharp
public static WorldGenerationConfig GetInstance();
public static WorldGenerationConfig Reload();
public DangerDistribution GetDangerDistribution(int chunkDistance);
public ResourceSpawnConfig GetResourceConfig(string dangerLevel);
public Dictionary<string, object> GetSummary();
```

**Critical Logic - Dilutive Normalization**:
The `_parse_danger_distribution` and water subtype parsing use dilutive normalization: if values do not sum to 1.0, they are divided by their total. This MUST be preserved:
```csharp
private DangerDistribution ParseDangerDistribution(JObject data, DangerDistribution defaultVal)
{
    if (data == null) return defaultVal;

    float peaceful = data.Value<float>("peaceful");
    float dangerous = data.Value<float>("dangerous");
    float rare = data.Value<float>("rare");

    float total = peaceful + dangerous + rare;
    if (Math.Abs(total - 1.0f) > 0.001f && total > 0)
    {
        peaceful /= total;
        dangerous /= total;
        rare /= total;
    }

    return new DangerDistribution(peaceful, dangerous, rare);
}
```

**Singleton Pattern**: Uses `__new__` + `_loaded` flag in Python. In C#, use the standard manual singleton with a `_loaded` flag to prevent double initialization.

---

#### 3.3.3 MapWaypointConfig (301 lines -> ~350 lines C#)

**Python source**: `data/databases/map_waypoint_db.py`
**C# target**: `Game1.Data.Databases/MapWaypointConfig.cs`
**JSON file**: `Definitions.JSON/map-waypoint-config.JSON`
**Dependencies**: None

**Nested Config Classes**:
- `MapDisplayConfig` (default_zoom=1.0, min_zoom=0.25, max_zoom=4.0, zoom_step=0.25, chunk_render_size=12, show_grid=true, etc.)
- `MarkerConfig` (color as `(int,int,int)`, size=8, shape="circle", show_label=false)
- `WaypointSystemConfig` (enabled=true, spawn_always_available=true, unlock_levels=[5,10,15,20,25,30], max_waypoints=7, teleport_cooldown=30.0, etc.)
- `UIConfig` (map_window_size=(700,600), waypoint_panel_width=200, background_color=(20,20,30,240), etc.)

**Public Methods**:
```csharp
public static MapWaypointConfig GetInstance();
public Color GetBiomeColor(string chunkType);  // Returns UnityEngine.Color or custom Color struct
public int GetMaxWaypointsForLevel(int level);
public Dictionary<string, object> GetSummary();
```

**Biome Color Defaults** (14 entries):
```
peaceful_forest=(34,139,34), dangerous_forest=(0,100,0), rare_hidden_forest=(50,205,50),
peaceful_cave=(105,105,105), dangerous_cave=(64,64,64), rare_deep_cave=(138,43,226),
peaceful_quarry=(160,82,45), dangerous_quarry=(139,69,19), rare_ancient_quarry=(255,140,0),
water_lake=(65,105,225), water_river=(70,130,180), water_cursed_swamp=(75,0,130),
unexplored=(30,30,40), spawn_area=(255,215,0)
```

**Special Notes**: Path resolution in Python uses `Path(__file__).parent.parent.parent` to find the JSON. In C#, use `JsonLoader.GetContentPath()` from the helper class.

---

#### 3.3.4 ClassDatabase (109 lines -> ~150 lines C#)

**Python source**: `data/databases/class_db.py`
**C# target**: `Game1.Data.Databases/ClassDatabase.cs`
**JSON file**: `progression/classes-1.JSON`
**Dependencies**: None

**Fields**:
```csharp
public Dictionary<string, ClassDefinition> Classes { get; private set; }
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static ClassDatabase GetInstance();
public bool LoadFromFile(string filepath);
```

**Critical: Bonus Key Mapping** (`_map_bonuses`):
The JSON uses camelCase bonus keys that must be mapped to snake_case internal keys. This mapping MUST be preserved exactly:
```
baseHP          -> max_health
baseMana        -> max_mana
meleeDamage     -> melee_damage
inventorySlots  -> inventory_slots
carryCapacity   -> carry_capacity
movementSpeed   -> movement_speed
critChance      -> crit_chance
forestryBonus   -> forestry_damage
recipeDiscovery -> recipe_discovery
skillExpGain    -> skill_exp
allCraftingTime -> crafting_speed
firstTryBonus   -> first_try_bonus
itemDurability  -> durability_bonus
rareDropRate    -> rare_drops
resourceQuality -> resource_quality
allGathering    -> gathering_bonus
allCrafting     -> crafting_bonus
defense         -> defense_bonus
miningBonus     -> mining_damage
attackSpeed     -> attack_speed
```

Unmapped keys fall through to `jsonKey.ToLower().Replace(" ", "_")`.

**Additional JSON Fields**:
- `startingSkill` can be a dict (`{"skillId": "..."}`) or a string -- Python handles both cases
- `recommendedStats` can be a dict (`{"primary": [...]}`) or direct list -- Python handles both
- `tags`, `preferredDamageTypes`, `preferredArmorType` are loaded directly

**Placeholders**: 6 classes (warrior, ranger, scholar, artisan, scavenger, adventurer) with complete data. Port these exactly for fallback behavior.

---

#### 3.3.5 ResourceNodeDatabase (258 lines -> ~310 lines C#)

**Python source**: `data/databases/resource_node_db.py`
**C# target**: `Game1.Data.Databases/ResourceNodeDatabase.cs`
**JSON file**: `Definitions.JSON/Resource-node-1.JSON`
**Dependencies**: None

**Fields**:
```csharp
public Dictionary<string, ResourceNodeDefinition> Nodes { get; private set; }
public bool Loaded { get; private set; }

// Cached category lists
private List<ResourceNodeDefinition> _trees;
private List<ResourceNodeDefinition> _ores;
private List<ResourceNodeDefinition> _stones;
private Dictionary<string, int> _tierMap;
```

**Public Methods**:
```csharp
public static ResourceNodeDatabase GetInstance();
public bool LoadFromFile(string filepath);
public ResourceNodeDefinition GetNode(string resourceId);
public int GetTier(string resourceId);
public List<ResourceNodeDefinition> GetAllTrees();
public List<ResourceNodeDefinition> GetAllOres();
public List<ResourceNodeDefinition> GetAllStones();
public List<ResourceNodeDefinition> GetTreesByTier(int maxTier);
public List<ResourceNodeDefinition> GetOresByTier(int maxTier);
public List<ResourceNodeDefinition> GetStonesByTier(int maxTier);
public List<ResourceNodeDefinition> GetResourcesForChunk(string chunkType, (int min, int max) tierRange);
public List<string> GetAllResourceIds();
public Dictionary<string, int> BuildTierMap();
public string GetIconName(string resourceId);
public string GetIconPath(string resourceId);
```

**Critical: ICON_NAME_MAP**:
A static `Dictionary<string, string>` mapping JSON resource IDs to PNG filenames. Contains 22+ entries. Example mappings:
```
copper_vein      -> copper_ore_node
iron_deposit     -> iron_ore_node
steel_node       -> steel_ore_node
mithril_cache    -> mithril_ore_node
limestone_outcrop -> limestone_node
granite_formation -> granite_node
obsidian_flow    -> obsidian_node
```
Trees use identity mapping (e.g., `oak_tree` -> `oak_tree`). Port this dictionary exactly.

**JSON Field Mapping**:
```
resourceId    -> resource_id
requiredTool  -> required_tool (string: "pickaxe" or "axe")
baseHealth    -> base_health (int)
respawnTime   -> respawn_time (nullable string)
drops[].materialId -> material_id
drops[].quantity   -> quantity (string: "several", "many", "few", "abundant")
drops[].chance     -> chance (string: "guaranteed", "high")
metadata.tags      -> tags (List<string>)
metadata.narrative -> narrative (string)
```

**Category Caching**: After loading, nodes are cached into `_trees`, `_ores`, `_stones` lists based on the `is_tree`, `is_ore`, `is_stone` properties from the model. Ensure the Phase 1 model has these computed properties.

---

#### 3.3.6 MaterialDatabase (203 lines -> ~260 lines C#)

**Python source**: `data/databases/material_db.py`
**C# target**: `Game1.Data.Databases/MaterialDatabase.cs`
**JSON files**: `items.JSON/items-materials-1.JSON`, `items.JSON/items-refining-1.JSON`, plus stackable items from any `items.JSON/*.JSON`
**Dependencies**: None

**Fields**:
```csharp
public Dictionary<string, MaterialDefinition> Materials { get; private set; }
public bool Loaded { get; private set; }
```

**Public Methods (3 load methods!)**:
```csharp
public static MaterialDatabase GetInstance();
public bool LoadFromFile(string filepath);           // Primary: items-materials-1.JSON
public bool LoadRefiningItems(string filepath);      // Secondary: items-refining-1.JSON
public bool LoadStackableItems(string filepath, List<string> categories = null);  // Tertiary: any items file
public MaterialDefinition GetMaterial(string materialId);
```

**LoadFromFile** - JSON structure:
```json
{ "materials": [ { "materialId": "...", "name": "...", "tier": 1, ... } ] }
```
Field mapping:
```
materialId   -> material_id
maxStack     -> max_stack (default: 99)
flags.placeable -> placeable (bool)
type         -> item_type
subtype      -> item_subtype
effectTags   -> effect_tags (List<string>)
effectParams -> effect_params (Dictionary)
```

**Icon Path Auto-Generation**:
```csharp
if (iconPath == null && materialId != "")
{
    string subdir = category switch
    {
        "consumable" => "consumables",
        "device"     => "devices",
        "station"    => "stations",
        _            => "materials"
    };
    iconPath = $"{subdir}/{materialId}.png";
}
```

**LoadRefiningItems** - Different JSON structure:
- Uses `itemId` (not `materialId`) as the ID field
- Sections: `basic_ingots`, `alloys`, `wood_planks`
- Description from `metadata.narrative`
- Stack size from `stackSize` (default: 256)
- Only adds if `material_id` not already in dictionary (no overwrites)

**LoadStackableItems** - Most complex loader:
- Iterates all sections except `metadata`
- Only loads items where `flags.stackable == true` OR `flags.placeable == true`
- Applies optional category filter
- Uses `itemId` as the ID field
- Same icon path auto-generation as primary loader

**Placeholder Materials**: 16 entries (4 wood types, 4 ore types, 4 stone types, 4 metal ingots) with tiers 1-4. Port exactly.

---

#### 3.3.7 EquipmentDatabase (401 lines -> ~470 lines C#)

**Python source**: `data/databases/equipment_db.py`
**C# target**: `Game1.Data.Databases/EquipmentDatabase.cs`
**JSON files**: Multiple `items.JSON/*.JSON` files (accumulated, not single file)
**Dependencies**: `SmithingTagProcessor.GetEquipmentSlot()` for tag-based slot detection

**Fields**:
```csharp
public Dictionary<string, Dictionary<string, object>> Items { get; private set; }  // Raw JSON dicts
public bool Loaded { get; private set; }
```

**IMPORTANT**: EquipmentDatabase stores raw JSON dictionaries, NOT typed EquipmentItem objects. The `CreateEquipmentFromId()` method constructs typed objects on demand.

**Public Methods**:
```csharp
public static EquipmentDatabase GetInstance();
public bool LoadFromFile(string filepath);  // Called MULTIPLE TIMES for different files
public EquipmentItem CreateEquipmentFromId(string itemId);
public bool IsEquipment(string itemId);
```

**LoadFromFile** - Accumulative loading:
- Iterates all sections except `metadata`
- ONLY loads items where `category == "equipment"`
- Skips consumables, devices, materials (those go to MaterialDatabase)
- Can be called repeatedly to accumulate items from multiple files

**CreateEquipmentFromId** - Complex construction logic:

1. **Stat Calculation Formulas** (from `stats-calculations.JSON`):
   - Weapon damage: `globalBase(10) * tierMult * typeMult * subtypeMult * itemMult * variance(0.85-1.15)`
   - Armor defense: `globalBase(10) * tierMult * slotMult * itemMult`
   - Durability: `globalBase(250) * tierMult * itemMult`
   - Tier multipliers: `{1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}`

2. **Weapon Type Multipliers**:
   ```
   sword=1.0, axe=1.1, spear=1.05, mace=1.15, dagger=0.8, bow=1.0, staff=0.9, shield=1.0
   ```

3. **Subtype Multipliers**:
   ```
   shortsword=0.9, longsword=1.0, greatsword=1.4, dagger=1.0, spear=1.0, pike=1.2,
   halberd=1.4, mace=1.0, warhammer=1.3, maul=1.5
   ```

4. **Armor Slot Multipliers**:
   ```
   helmet=0.8, chestplate=1.5, leggings=1.2, boots=0.7, gauntlets=0.6
   ```

5. **Slot Assignment Priority** (4-tier cascade):
   - Weapons (`type` in weapon_types): use explicit `slot` from JSON with mapping
   - Tools (`type == "tool"`): use `subtype` (`axe` -> `axe` slot, `pickaxe` -> `pickaxe` slot)
   - Armor (`type` in armor_types): try `SmithingTagProcessor.GetEquipmentSlot(tags)` first, fallback to JSON `slot`
   - Other: try tag-based, then JSON `slot`

6. **Slot Mapping**:
   ```
   head -> helmet, chest -> chestplate, legs -> leggings, feet -> boots,
   hands -> gauntlets, mainHand -> mainHand, offHand -> offHand
   ```

7. **Hand Type from Tags**: Check `metadata.tags` for `1H`, `2H`, `versatile` -> set `hand_type`

8. **Effect Tags**: Support both `effect_tags`/`effectTags` and `effect_params`/`effectParams` (dual casing)

**Icon Path Auto-Generation**:
```
mainHand/offHand with damage -> weapons/
helmet/chestplate/leggings/boots/gauntlets -> armor/
tool/axe/pickaxe -> tools/
accessory -> accessories/
station -> stations/
default -> weapons/
```

**Placeholder Equipment**: 10 items (copper/iron sword, helmet, chestplate, leggings, boots). Port exactly.

---

#### 3.3.8 SkillDatabase (123 lines -> ~170 lines C#)

**Python source**: `data/databases/skill_db.py`
**C# target**: `Game1.Data.Databases/SkillDatabase.cs`
**JSON file**: `Skills/skills-skills-1.JSON`
**Dependencies**: None

**Fields**:
```csharp
public Dictionary<string, SkillDefinition> Skills { get; private set; }
public bool Loaded { get; private set; }

// Inline translation tables (canonical values)
private readonly Dictionary<string, int> _manaCosts;
private readonly Dictionary<string, float> _cooldowns;
private readonly Dictionary<string, float> _durations;
```

**Public Methods**:
```csharp
public static SkillDatabase GetInstance();
public bool LoadFromFile(string filepath);
public SkillDefinition GetSkill(string skillId);
public int GetManaCost(object costValue);         // Accepts string OR int/float
public float GetCooldownSeconds(object cooldownValue);  // Accepts string OR int/float
public float GetDurationSeconds(string durationText);
```

**Translation Tables (HARDCODED IN CONSTRUCTOR - CANONICAL)**:
```csharp
_manaCosts = new Dictionary<string, int>
{
    { "low", 30 }, { "moderate", 60 }, { "high", 100 }, { "extreme", 150 }
};
_cooldowns = new Dictionary<string, float>
{
    { "short", 120f }, { "moderate", 300f }, { "long", 600f }, { "extreme", 1200f }
};
_durations = new Dictionary<string, float>
{
    { "instant", 0f }, { "brief", 15f }, { "moderate", 30f }, { "long", 60f }, { "extended", 120f }
};
```

**GetManaCost/GetCooldownSeconds Dual-Type Support**:
These methods accept BOTH string enums (`"moderate"`) AND direct numeric values (`60`). In C#, use method overloads or a union parameter:
```csharp
public int GetManaCost(string costText) => _manaCosts.GetValueOrDefault(costText, 60);
public int GetManaCost(int costValue) => costValue;
public int GetManaCost(float costValue) => (int)costValue;
```

**Skill Parsing** - Each skill has nested objects:
- `effect` -> `SkillEffect` (type, category, magnitude, target, duration, additionalEffects)
- `cost` -> `SkillCost` (mana, cooldown)
- `evolution` -> `SkillEvolution` (canEvolve, nextSkillId, requirement)
- `requirements` -> `SkillRequirements` (characterLevel, stats, titles)
- `combatTags` and `combatParams` are loaded directly

**Icon Auto-Generation**: `skills/{skillId}.png`

---

#### 3.3.9 RecipeDatabase (212 lines -> ~270 lines C#)

**Python source**: `data/databases/recipe_db.py`
**C# target**: `Game1.Data.Databases/RecipeDatabase.cs`
**JSON files**: 5 recipe files (see table above)
**Dependencies**: Cross-references MaterialDatabase for input validation (in `CanCraft`), Config for debug flags

**Fields**:
```csharp
public Dictionary<string, Recipe> Recipes { get; private set; }
public Dictionary<string, List<Recipe>> RecipesByStation { get; private set; }
public bool Loaded { get; private set; }
```

**RecipesByStation** initialized with 5 keys: `"smithing"`, `"alchemy"`, `"refining"`, `"engineering"`, `"adornments"`.

**Public Methods**:
```csharp
public static RecipeDatabase GetInstance();
public void LoadFromFiles(string basePath = "");
public List<Recipe> GetRecipesForStation(string stationType, int tier = 1);
public bool CanCraft(Recipe recipe, Inventory inventory);
public bool ConsumeMaterials(Recipe recipe, Inventory inventory);
```

**File-to-Station Mapping**:
```
recipes-smithing-3.json     -> "smithing"
recipes-alchemy-1.JSON      -> "alchemy"
recipes-refining-1.JSON     -> "refining"
recipes-engineering-1.JSON  -> "engineering"
recipes-adornments-1.json   -> "adornments"
```

**Critical: Three Recipe Output Formats**:
1. **Enchanting recipes** (`enchantmentId` present): `outputId = enchantmentId`, `outputQty = 1`, `stationTier` from `stationTier`
2. **Refining recipes** (`outputs` array present): `outputId = outputs[0].materialId || outputs[0].itemId`, `stationTier` from `stationTierRequired || stationTier`
3. **Standard recipes**: `outputId`, `outputQty`, `stationTier` directly from JSON

Additional enchanting fields: `enchantmentName`, `applicableTo`, `effect`

**GetRecipesForStation**: Returns recipes where `recipe.station_tier <= tier` (not equality, less-than-or-equal).

**CanCraft/ConsumeMaterials**: These reference `Config.DEBUG_INFINITE_RESOURCES`. When true, `CanCraft` returns true and `ConsumeMaterials` skips consumption. Port this debug flag integration.

**Default Recipes**: 14 fallback recipes (3 refining ingots, 6 smithing weapons, 2 helmets, 2 chestplates, 1 leggings pair). Port exactly.

---

#### 3.3.10 PlacementDatabase (217 lines -> ~270 lines C#)

**Python source**: `data/databases/placement_db.py`
**C# target**: `Game1.Data.Databases/PlacementDatabase.cs`
**JSON files**: 5 placement files
**Dependencies**: Cross-references RecipeDatabase for recipe_id matching

**Fields**:
```csharp
public Dictionary<string, PlacementData> Placements { get; private set; }  // recipeId -> PlacementData
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static PlacementDatabase GetInstance();
public int LoadFromFiles(string basePath = "");
public PlacementData GetPlacement(string recipeId);
public bool HasPlacement(string recipeId);
```

**5 Discipline-Specific Loaders** (each loads different PlacementData fields):

| Discipline | Method | Key PlacementData Fields |
|------------|--------|-------------------------|
| Smithing | `LoadSmithing()` | `grid_size` (from metadata.gridSize, default "3x3"), `placement_map` |
| Refining | `LoadRefining()` | `core_inputs`, `surrounding_inputs`, `output_id`, `station_tier` |
| Alchemy | `LoadAlchemy()` | `ingredients`, `output_id`, `station_tier` |
| Engineering | `LoadEngineering()` | `slots`, `output_id`, `station_tier` |
| Enchanting | `LoadEnchanting()` | `pattern`, `placement_map`, `grid_size`, `output_id`, `station_tier` |

Each loader sets the `discipline` field on PlacementData to identify the type.

---

#### 3.3.11 TitleDatabase (176 lines -> ~230 lines C#)

**Python source**: `data/databases/title_db.py`
**C# target**: `Game1.Data.Databases/TitleDatabase.cs`
**JSON file**: `progression/titles-1.JSON`
**Dependencies**: `ConditionFactory` for parsing requirement conditions

**Fields**:
```csharp
public Dictionary<string, TitleDefinition> Titles { get; private set; }
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static TitleDatabase GetInstance();
public bool LoadFromFile(string filepath);
```

**Critical: Title Bonus Mapping** (`_map_title_bonuses`):
```
miningDamage     -> mining_damage
miningSpeed      -> mining_speed
forestryDamage   -> forestry_damage
forestrySpeed    -> forestry_speed
smithingTime     -> smithing_speed
smithingQuality  -> smithing_quality
refiningPrecision -> refining_speed
meleeDamage      -> melee_damage
criticalChance   -> crit_chance
attackSpeed      -> attack_speed
firstTryBonus    -> first_try_bonus
rareOreChance    -> rare_ore_chance
rareWoodChance   -> rare_wood_chance
fireOreChance    -> fire_ore_chance
alloyQuality     -> alloy_quality
materialYield    -> material_yield
combatSkillExp   -> combat_skill_exp
counterChance    -> counter_chance
durabilityBonus  -> durability_bonus
legendaryChance  -> legendary_chance
dragonDamage     -> dragon_damage
fireResistance   -> fire_resistance
legendaryDropRate -> legendary_drop_rate
luckStat         -> luck_stat
rareDropRate     -> rare_drop_rate
fishingSpeed     -> fishing_speed
fishingAccuracy  -> fishing_accuracy
rareFishChance   -> rare_fish_chance
fishingYield     -> fishing_yield
```

**Activity Mapping** (`_parse_activity`):
```
oresMined        -> mining
treesChopped     -> forestry
itemsSmithed     -> smithing
materialsRefined -> refining
potionsBrewed    -> alchemy
itemsEnchanted   -> enchanting
devicesCreated   -> engineering
enemiesDefeated  -> combat
bossesDefeated   -> combat
areasExplored    -> exploration
```

**Title Parsing Flow**:
1. Map bonuses via `_map_title_bonuses`
2. Parse `prerequisites` via `ConditionFactory.CreateRequirementsFromJson()`
3. Extract legacy `activity_type` and `threshold` from `prerequisites.activities`
4. Extract `prerequisite_titles` from `prerequisites.requiredTitles`
5. Read `acquisitionMethod` (default: `"guaranteed_milestone"`)
6. Read `generationChance` (default: 1.0, for RNG-based titles)
7. Auto-generate icon path: `titles/{titleId}.png`

**Bonus Description Generation**:
```csharp
string CreateBonusDescription(Dictionary<string, float> bonuses)
{
    if (bonuses.Count == 0) return "No bonuses";
    var first = bonuses.First();
    string percent = $"+{(int)(first.Value * 100)}%";
    string readable = first.Key.Replace("_", " ").ToTitleCase();
    return $"{percent} {readable}";
}
```

**Placeholder Titles**: 5 novice titles (miner, lumberjack, smith, refiner, alchemist). Port exactly.

---

#### 3.3.12 SkillUnlockDatabase (138 lines -> ~180 lines C#)

**Python source**: `data/databases/skill_unlock_db.py`
**C# target**: `Game1.Data.Databases/SkillUnlockDatabase.cs`
**JSON file**: `progression/skill-unlocks.JSON`
**Dependencies**: `ConditionFactory` for parsing conditions, `SkillDatabase` for validation

**Fields**:
```csharp
public Dictionary<string, SkillUnlock> Unlocks { get; private set; }       // unlockId -> SkillUnlock
public Dictionary<string, SkillUnlock> UnlocksBySkill { get; private set; } // skillId -> SkillUnlock
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static SkillUnlockDatabase GetInstance();
public void LoadFromFile(string filepath);
public SkillUnlock GetUnlock(string unlockId);
public SkillUnlock GetUnlockForSkill(string skillId);
public List<SkillUnlock> GetUnlocksByMethod(string unlockMethod);
public List<SkillUnlock> GetUnlocksByTriggerType(string triggerType);
public List<SkillUnlock> GetAllUnlocks();
```

**JSON Field Mapping**:
```
unlockId          -> unlock_id
skillId           -> skill_id
unlockMethod      -> unlock_method
conditions        -> parsed via ConditionFactory
unlockTrigger.type -> trigger.type
unlockTrigger.triggerValue -> trigger.trigger_value
unlockTrigger.message -> trigger.message
cost.gold         -> cost.gold
cost.materials    -> cost.materials (List)
cost.skillPoints  -> cost.skill_points
metadata.narrative -> narrative
metadata.category -> category
```

**Validation**: Skips entries missing `unlockId`, `skillId`, or `unlockMethod`.

---

#### 3.3.13 NPCDatabase (147 lines -> ~200 lines C#)

**Python source**: `data/databases/npc_db.py`
**C# target**: `Game1.Data.Databases/NPCDatabase.cs`
**JSON files**: `progression/npcs-enhanced.JSON` (fallback: `progression/npcs-1.JSON`), `progression/quests-enhanced.JSON` (fallback: `progression/quests-1.JSON`)
**Dependencies**: None (strict)

**Fields**:
```csharp
public Dictionary<string, NPCDefinition> Npcs { get; private set; }
public Dictionary<string, QuestDefinition> Quests { get; private set; }
public bool Loaded { get; private set; }
```

**Public Methods**:
```csharp
public static NPCDatabase GetInstance();
public void LoadFromFiles();
```

**Dual-Format NPC Loading** (supports v1.0 and v2.0):
- `position` -> `Position(x, y, z)`
- `sprite_color` -> tuple (int array in JSON)
- `dialogue_lines`: Try direct field first, then `dialogue.dialogue_lines`, then fallback to `dialogue.greeting.default/questInProgress/questComplete`
- `interaction_radius`: Direct field (default 3.0), or `behavior.interactionRange`
- `quests`: list of quest IDs

**Dual-Format Quest Loading**:
- `quest_id` OR `questId` for ID
- `title` OR `name` for display name
- `description`: can be string OR dict (`{long: "...", short: "..."}`)
- `npc_id` OR `givenBy` for assigner
- `objectives.type` OR `objectives.objective_type` for objective type
- `rewards.statPoints` OR `rewards.stat_points` for stat points

**File Loading Strategy**: Try enhanced file first. If it exists, use it and break. Otherwise fall back to v1.0 file. Same pattern for both NPCs and Quests.

---

#### 3.3.14 UpdateLoader (364 lines -> ~400 lines C#)

**Python source**: `data/databases/update_loader.py`
**C# target**: `Game1.Data.Databases/UpdateLoader.cs`
**JSON files**: Dynamic -- reads `updates_manifest.json`, then scans `Update-N/` directories
**Dependencies**: All other databases (this runs LAST)

**Public Methods (module-level functions -> static class)**:
```csharp
public static class UpdateLoader
{
    public static List<string> GetInstalledUpdates(string projectRoot);
    public static List<string> ScanUpdateDirectory(string updateDir, string databaseType);
    public static void LoadEquipmentUpdates(string projectRoot);
    public static void LoadSkillUpdates(string projectRoot);
    public static void LoadEnemyUpdates(string projectRoot);
    public static void LoadMaterialUpdates(string projectRoot);
    public static void LoadTitleUpdates(string projectRoot);
    public static void LoadSkillUnlockUpdates(string projectRoot);
    public static void LoadRecipeUpdates(string projectRoot);
    public static void LoadAllUpdates(string projectRoot = null);
    public static void ListUpdateContent(string updateName, string projectRoot = null);
}
```

**Scan Patterns by Database Type**:
| Type | File Patterns |
|------|--------------|
| equipment | `*items*`, `*weapons*`, `*armor*`, `*tools*` |
| skills | `*skills*` |
| enemies | `*hostiles*`, `*enemies*` |
| materials | `*materials*`, `*consumables*`, `*devices*` |
| titles | `*titles*` |
| skill_unlocks | `*skill-unlocks*`, `*skill_unlocks*` |
| recipes | `*recipes*` |

**Recipe Station Auto-Detection** from filename:
```
*smithing*    -> "smithing"
*alchemy*     -> "alchemy"
*refining*    -> "refining"
*engineering* -> "engineering"
*adornment*/*enchanting* -> "adornments"
default       -> "smithing"
```

**LoadAllUpdates** execution order:
1. Equipment
2. Skills
3. Enemies
4. Materials
5. Recipes
6. Titles
7. Skill Unlocks

---

### 3.4 Key JSON Field Name Mappings

Throughout the codebase, JSON files use camelCase while Python internal fields use snake_case. C# should use PascalCase for properties but store dictionary keys in snake_case to match Python behavior for bonus/effect lookups.

**Universal Mappings** (appear across multiple databases):

| JSON Field | Python Internal | C# Property | Notes |
|------------|----------------|-------------|-------|
| `materialId` | `material_id` | `MaterialId` | Primary key for materials |
| `itemId` | `item_id` / `material_id` | `ItemId` | Used in refining, equipment, stackable items |
| `recipeId` | `recipe_id` | `RecipeId` | Primary key for recipes |
| `skillId` | `skill_id` | `SkillId` | Primary key for skills |
| `titleId` | `title_id` | `TitleId` | Primary key for titles |
| `classId` | `class_id` | `ClassId` | Primary key for classes |
| `resourceId` | `resource_id` | `ResourceId` | Primary key for resource nodes |
| `unlockId` | `unlock_id` | `UnlockId` | Primary key for skill unlocks |
| `outputId` | `output_id` | `OutputId` | Recipe output reference |
| `outputQty` | `output_qty` | `OutputQty` | Recipe output quantity |
| `stationType` | `station_type` | `StationType` | Crafting station type |
| `stationTier` | `station_tier` | `StationTier` | Required station tier |
| `stationTierRequired` | `station_tier` | `StationTier` | Alternate field name (refining) |
| `maxStack` | `max_stack` | `MaxStack` | Material stack limit |
| `stackSize` | `max_stack` | `MaxStack` | Alternate field name (refining) |
| `iconPath` | `icon_path` | `IconPath` | Asset path for icon |
| `effectTags` | `effect_tags` | `EffectTags` | Combat effect tags |
| `effectParams` | `effect_params` | `EffectParams` | Effect parameter dictionary |
| `statMultipliers` | `stat_multipliers` | `StatMultipliers` | Equipment stat scaling |
| `baseHealth` | `base_health` | `BaseHealth` | Resource node HP |
| `requiredTool` | `required_tool` | `RequiredTool` | Tool needed for gathering |
| `respawnTime` | `respawn_time` | `RespawnTime` | Resource respawn timer |
| `characterLevel` | `character_level` | `CharacterLevel` | Level requirement |
| `attackSpeed` | `attack_speed` | `AttackSpeed` | Weapon speed |
| `combatTags` | `combat_tags` | `CombatTags` | Skill combat tags |
| `combatParams` | `combat_params` | `CombatParams` | Skill combat parameters |
| `canEvolve` | `can_evolve` | `CanEvolve` | Skill evolution flag |
| `nextSkillId` | `next_skill_id` | `NextSkillId` | Evolution target |
| `additionalEffects` | `additional_effects` | `AdditionalEffects` | Extra skill effects |
| `difficultyTier` | `tier` | `Tier` | Title difficulty tier |
| `titleType` | `category` | `Category` | Title category |
| `isHidden` | `hidden` | `Hidden` | Hidden title flag |
| `acquisitionMethod` | `acquisition_method` | `AcquisitionMethod` | How title is earned |
| `generationChance` | `generation_chance` | `GenerationChance` | RNG title probability |
| `startingBonuses` | `bonuses` | `Bonuses` | Class bonuses (after mapping) |
| `startingSkill` | `starting_skill` | `StartingSkill` | Class starter skill |
| `recommendedStats` | `recommended_stats` | `RecommendedStats` | Class stat priorities |
| `preferredDamageTypes` | `preferred_damage_types` | `PreferredDamageTypes` | Class damage affinity |
| `preferredArmorType` | `preferred_armor_type` | `PreferredArmorType` | Class armor type |
| `enchantmentId` | (used as output_id) | `EnchantmentId` | Enchanting recipe output |
| `enchantmentName` | `enchantment_name` | `EnchantmentName` | Display name |
| `applicableTo` | `applicable_to` | `ApplicableTo` | Valid target types |
| `gridSize` | `grid_size` | `GridSize` | Placement grid dimensions |
| `placementMap` | `placement_map` | `PlacementMap` | Grid position mapping |
| `coreInputs` | `core_inputs` | `CoreInputs` | Refining placement |
| `surroundingInputs` | `surrounding_inputs` | `SurroundingInputs` | Refining placement |

### 3.5 Translation Tables (MUST PRESERVE EXACT VALUES)

These translation tables convert human-readable text values in JSON to numeric game values. They appear in both `SkillDatabase` (inline) and `TranslationDatabase` (from JSON). The SkillDatabase values are canonical.

**Mana Costs**:
| Text | Numeric Value |
|------|--------------|
| `"low"` | 30 |
| `"moderate"` | 60 |
| `"high"` | 100 |
| `"extreme"` | 150 |

**Cooldowns** (in seconds, used as game ticks at 60fps):
| Text | Seconds |
|------|---------|
| `"short"` | 120 |
| `"moderate"` | 300 |
| `"long"` | 600 |
| `"extreme"` | 1200 |

**Durations** (in seconds):
| Text | Seconds |
|------|---------|
| `"instant"` | 0 |
| `"brief"` | 15 |
| `"moderate"` | 30 |
| `"long"` | 60 |
| `"extended"` | 120 |

**Magnitudes** (multiplier values):
| Text | Value |
|------|-------|
| `"minor"` | 0.5 |
| `"moderate"` | 1.0 |
| `"major"` | 2.0 |
| `"extreme"` | 4.0 |

### 3.6 Config System

**Python source**: `core/config.py` (200 lines)
**C# target**: `Game1.Core/GameConfig.cs`

Port the `Config` class as a static class with all constants. In Unity, display/screen management will use Unity's built-in systems, so the `init_screen_settings` method becomes simplified.

**Display Constants**:
```csharp
public static class GameConfig
{
    // Base resolution (design baseline)
    public const int BASE_WIDTH = 1600;
    public const int BASE_HEIGHT = 900;

    // Runtime values (set during init)
    public static int ScreenWidth = 1600;
    public static int ScreenHeight = 900;
    public const int FPS = 60;
    public static bool Fullscreen = false;
    public static float UIScale = 1.0f;
}
```

**World Constants**:
```csharp
public const int CHUNK_SIZE = 16;
public const int TILE_SIZE = 32;
public const int CHUNK_LOAD_RADIUS = 4;
public const int SPAWN_ALWAYS_LOADED = 1;
public const int WORLD_SIZE = 176;       // Deprecated - infinite world
public const int NUM_CHUNKS = 11;        // Deprecated
```

**Player Constants**:
```csharp
public const float PLAYER_SPAWN_X = 0.0f;
public const float PLAYER_SPAWN_Y = 0.0f;
public const float PLAYER_SPAWN_Z = 0.0f;
public const int SAFE_ZONE_RADIUS = 8;
public const float PLAYER_SPEED = 0.15f;
public const float INTERACTION_RANGE = 3.5f;
public const float CLICK_TOLERANCE = 0.7f;
```

**UI Layout Constants** (base values at 1600x900):
```csharp
public static int VIEWPORT_WIDTH = 1200;
public static int VIEWPORT_HEIGHT = 900;
public static int UI_PANEL_WIDTH = 400;
public static int INVENTORY_PANEL_X = 0;
public static int INVENTORY_PANEL_Y = 600;
public static int INVENTORY_PANEL_WIDTH = 1200;
public static int INVENTORY_PANEL_HEIGHT = 300;
public static int INVENTORY_SLOT_SIZE = 50;
public static int INVENTORY_SLOTS_PER_ROW = 10;
```

**Debug Flags**:
```csharp
public static bool DEBUG_INFINITE_RESOURCES = false;  // F1
public static bool DEBUG_INFINITE_DURABILITY = false;  // F3 (note: labeled F7 in CLAUDE.md)
public static bool KEEP_INVENTORY = true;              // F5
```

**Color Constants** (convert to Unity Color32 or custom struct):
```csharp
public static readonly Color32 COLOR_BACKGROUND = new Color32(20, 20, 30, 255);
public static readonly Color32 COLOR_GRID = new Color32(40, 40, 50, 255);
public static readonly Color32 COLOR_GRASS = new Color32(34, 139, 34, 255);
public static readonly Color32 COLOR_STONE = new Color32(128, 128, 128, 255);
public static readonly Color32 COLOR_WATER = new Color32(30, 144, 255, 255);
public static readonly Color32 COLOR_PLAYER = new Color32(255, 215, 0, 255);
public static readonly Color32 COLOR_UI_BG = new Color32(30, 30, 40, 255);
public static readonly Color32 COLOR_TEXT = new Color32(255, 255, 255, 255);
public static readonly Color32 COLOR_HEALTH = new Color32(255, 0, 0, 255);
public static readonly Color32 COLOR_HEALTH_BG = new Color32(50, 50, 50, 255);
public static readonly Color32 COLOR_TREE = new Color32(0, 100, 0, 255);
public static readonly Color32 COLOR_ORE = new Color32(169, 169, 169, 255);
public static readonly Color32 COLOR_STONE_NODE = new Color32(105, 105, 105, 255);
public static readonly Color32 COLOR_HP_BAR = new Color32(0, 255, 0, 255);
public static readonly Color32 COLOR_HP_BAR_BG = new Color32(100, 100, 100, 255);
public static readonly Color32 COLOR_DAMAGE_NORMAL = new Color32(255, 255, 255, 255);
public static readonly Color32 COLOR_DAMAGE_CRIT = new Color32(255, 215, 0, 255);
public static readonly Color32 COLOR_SLOT_EMPTY = new Color32(40, 40, 50, 255);
public static readonly Color32 COLOR_SLOT_FILLED = new Color32(50, 60, 70, 255);
public static readonly Color32 COLOR_SLOT_BORDER = new Color32(100, 100, 120, 255);
public static readonly Color32 COLOR_SLOT_SELECTED = new Color32(255, 215, 0, 255);
public static readonly Color32 COLOR_TOOLTIP_BG = new Color32(20, 20, 30, 230);
public static readonly Color32 COLOR_RESPAWN_BAR = new Color32(100, 200, 100, 255);
public static readonly Color32 COLOR_CAN_HARVEST = new Color32(100, 255, 100, 255);
public static readonly Color32 COLOR_CANNOT_HARVEST = new Color32(255, 100, 100, 255);
public static readonly Color32 COLOR_NOTIFICATION = new Color32(255, 215, 0, 255);
public static readonly Color32 COLOR_EQUIPPED = new Color32(255, 215, 0, 255);
```

**Rarity Colors** (dictionary):
```csharp
public static readonly Dictionary<string, Color32> RARITY_COLORS = new Dictionary<string, Color32>
{
    { "common",    new Color32(200, 200, 200, 255) },
    { "uncommon",  new Color32(30, 255, 0, 255) },
    { "rare",      new Color32(0, 112, 221, 255) },
    { "epic",      new Color32(163, 53, 238, 255) },
    { "legendary", new Color32(255, 128, 0, 255) },
    { "artifact",  new Color32(230, 204, 128, 255) }
};
```

**Scale Methods**:
```csharp
public static int Scale(int value) => (int)(value * UIScale);
public static float ScaleF(float value) => value * UIScale;
```

**GamePaths** (from `core/paths.py`):

Port `PathManager` as a singleton. In Unity, base path detection changes:
```csharp
public class GamePaths
{
    private static GamePaths _instance;

    public string BasePath { get; private set; }
    public string SavePath { get; private set; }
    public bool IsBundled { get; private set; }

    public static GamePaths GetInstance() { ... }

    private void SetupPaths()
    {
        // In Unity, use Application.streamingAssetsPath for content
        BasePath = Path.Combine(Application.streamingAssetsPath, "Content");
        // Saves go to Application.persistentDataPath
        SavePath = Path.Combine(Application.persistentDataPath, "saves");
        Directory.CreateDirectory(SavePath);
    }

    public string GetResourcePath(string relativePath)
        => Path.Combine(BasePath, relativePath);

    public string GetSavePath(string filename = null)
        => filename != null ? Path.Combine(SavePath, filename) : SavePath;

    public bool ResourceExists(string relativePath)
        => File.Exists(GetResourcePath(relativePath));
}
```

---

## 4. Critical Initialization Order

The databases must be initialized in this exact order due to cross-references. The Python `game_engine.py` establishes this order and it must be preserved in C#.

```
 Step  Database                    Dependencies / Notes
 ----  --------------------------  ------------------------------------------
  1.   GameConfig                  No deps. Must be first (other systems read constants).
  2.   GamePaths                   No deps. Must be before any file loading.
  3.   TranslationDatabase         No deps. Loads skills-translation-table.JSON.
  4.   WorldGenerationConfig       No deps. Loads world_generation.JSON.
  5.   MapWaypointConfig           No deps. Loads map-waypoint-config.JSON.
  6.   ClassDatabase               No deps. Loads classes-1.JSON.
  7.   ResourceNodeDatabase        No deps. Loads Resource-node-1.JSON.
  8.   MaterialDatabase            No deps. Loads items-materials-1.JSON,
                                   then items-refining-1.JSON,
                                   then stackable items from other items files.
  9.   EquipmentDatabase           Depends: SmithingTagProcessor for slot detection.
                                   Loads items-smithing-2.JSON, items-alchemy-1.JSON,
                                   items-engineering-1.JSON, items-tools-1.JSON.
 10.   SkillDatabase               No deps. Loads skills-skills-1.JSON.
 11.   RecipeDatabase              Cross-refs: MaterialDatabase for input validation.
                                   Loads 5 recipe files.
 12.   PlacementDatabase           Cross-refs: RecipeDatabase for recipe_id matching.
                                   Loads 5 placement files.
 13.   TitleDatabase               Depends: ConditionFactory for requirement parsing.
                                   Loads titles-1.JSON.
 14.   SkillUnlockDatabase         Depends: ConditionFactory, SkillDatabase.
                                   Loads skill-unlocks.JSON.
 15.   NPCDatabase                 No strict deps. Loads NPCs then Quests.
 16.   UpdateLoader.LoadAllUpdates Post-init. Reads updates_manifest.json,
                                   then accumulates into all databases above.
```

**C# Initialization Entry Point**:
```csharp
public static class DatabaseInitializer
{
    public static void InitializeAll()
    {
        // Phase 1: Independent databases
        TranslationDatabase.GetInstance().LoadFromFiles();
        WorldGenerationConfig.GetInstance();  // Loads in constructor
        MapWaypointConfig.GetInstance();      // Loads in constructor
        ClassDatabase.GetInstance().LoadFromFile(JsonLoader.GetContentPath("progression/classes-1.JSON"));
        ResourceNodeDatabase.GetInstance().LoadFromFile(JsonLoader.GetContentPath("Definitions.JSON/Resource-node-1.JSON"));

        // Phase 2: Material loading (multi-file)
        var matDb = MaterialDatabase.GetInstance();
        matDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-materials-1.JSON"));
        matDb.LoadRefiningItems(JsonLoader.GetContentPath("items.JSON/items-refining-1.JSON"));
        matDb.LoadStackableItems(JsonLoader.GetContentPath("items.JSON/items-alchemy-1.JSON"), new List<string> { "consumable" });
        matDb.LoadStackableItems(JsonLoader.GetContentPath("items.JSON/items-engineering-1.JSON"), new List<string> { "device" });
        matDb.LoadStackableItems(JsonLoader.GetContentPath("items.JSON/items-tools-1.JSON"), new List<string> { "station" });

        // Phase 3: Equipment (depends on SmithingTagProcessor)
        var equipDb = EquipmentDatabase.GetInstance();
        equipDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-smithing-2.JSON"));
        equipDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-alchemy-1.JSON"));
        equipDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-engineering-1.JSON"));
        equipDb.LoadFromFile(JsonLoader.GetContentPath("items.JSON/items-tools-1.JSON"));

        // Phase 4: Skills
        SkillDatabase.GetInstance().LoadFromFile(JsonLoader.GetContentPath("Skills/skills-skills-1.JSON"));

        // Phase 5: Cross-referencing databases
        RecipeDatabase.GetInstance().LoadFromFiles();
        PlacementDatabase.GetInstance().LoadFromFiles();

        // Phase 6: Progression databases
        TitleDatabase.GetInstance().LoadFromFile(JsonLoader.GetContentPath("progression/titles-1.JSON"));
        SkillUnlockDatabase.GetInstance().LoadFromFile(JsonLoader.GetContentPath("progression/skill-unlocks.JSON"));
        NPCDatabase.GetInstance().LoadFromFiles();

        // Phase 7: Dynamic content
        UpdateLoader.LoadAllUpdates();
    }
}
```

---

## 5. Quality Control Instructions

### 5.1 Pre-Migration Checklist

- [ ] Verify all JSON files parse correctly: run `python -m json.tool` on every JSON file
- [ ] Document every JSON file path relative to `Game-1-modular/` root
- [ ] Confirm Phase 1 data models compile with no errors
- [ ] Confirm Phase 1 unit tests all pass
- [ ] Create JSON schema definitions for each major data type (optional but recommended)
- [ ] Set up Newtonsoft.Json in Unity project (`com.unity.nuget.newtonsoft-json`)
- [ ] Create `StreamingAssets/Content/` directory structure in Unity project
- [ ] Copy all JSON files from Python project to Unity StreamingAssets

### 5.2 Per-Database QC Checklist

For each of the 13 databases, verify:

- [ ] **Load count matches Python**: Same number of items/entries loaded from identical JSON files
- [ ] **Fallback placeholders work**: When JSON file is missing, placeholder data is created
- [ ] **All public methods exist**: Every Python public method has a C# equivalent
- [ ] **Return types correct**: Query methods return correct C# types
- [ ] **Singleton pattern works**: `GetInstance()` always returns same reference; `ResetInstance()` works in tests
- [ ] **Error handling**: Graceful failure on missing files (log warning, use defaults)
- [ ] **No exceptions on empty data**: Empty collections handled, not null references
- [ ] **Field mapping correct**: Spot-check 3+ entries for correct field values

### 5.3 Post-Migration Validation Tests

**MaterialDatabase**:
- [ ] Loads 57+ materials from `items-materials-1.JSON`
- [ ] `GetMaterial("copper_ore")` returns tier=1, category="metal", rarity="common"
- [ ] `GetMaterial("mithril_ore")` returns tier=4 (or correct tier from JSON)
- [ ] Refining items load without overwriting existing materials
- [ ] Stackable items only loaded when `flags.stackable` or `flags.placeable` is true
- [ ] Icon paths auto-generated correctly per category

**EquipmentDatabase**:
- [ ] `CreateEquipmentFromId("copper_sword")` returns correct damage range, slot="mainHand"
- [ ] `CreateEquipmentFromId("iron_helmet")` returns correct defense, slot="helmet"
- [ ] `IsEquipment("copper_sword")` returns true
- [ ] `IsEquipment("copper_ore")` returns false (materials excluded)
- [ ] Weapon damage formula: copper_sword (T1) base ~10, iron_sword (T2) base ~20
- [ ] Durability formula: T1=250, T2=500, T3=1000, T4=2000 (with 1.0 multiplier)
- [ ] Hand type detection from metadata tags works (1H, 2H, versatile)

**RecipeDatabase**:
- [ ] `GetRecipesForStation("smithing", 1)` returns correct recipe list
- [ ] `GetRecipesForStation("smithing", 2)` includes tier 1 AND tier 2 recipes
- [ ] Enchanting recipes use `enchantmentId` as `output_id`
- [ ] Refining recipes parse `outputs` array correctly
- [ ] `CanCraft` respects `DEBUG_INFINITE_RESOURCES` flag

**SkillDatabase**:
- [ ] `GetManaCost("moderate")` returns 60
- [ ] `GetManaCost("extreme")` returns 150
- [ ] `GetManaCost(75)` returns 75 (numeric passthrough)
- [ ] `GetCooldownSeconds("short")` returns 120.0
- [ ] `GetDurationSeconds("extended")` returns 120.0
- [ ] Skill parsing includes all nested objects (effect, cost, evolution, requirements)

**PlacementDatabase**:
- [ ] Loads all 5 discipline placement files
- [ ] `GetPlacement("copper_sword_recipe")` returns smithing placement with grid_size
- [ ] `HasPlacement` returns false for nonexistent recipe IDs
- [ ] Each discipline loader populates correct PlacementData fields

**TitleDatabase**:
- [ ] Bonus mapping converts `miningDamage` to `mining_damage`
- [ ] Activity mapping converts `oresMined` to `mining`
- [ ] Requirements parsed via ConditionFactory
- [ ] Icon paths auto-generated as `titles/{titleId}.png`

**ClassDatabase**:
- [ ] Loads 6 classes from JSON
- [ ] `baseHP` mapped to `max_health` in bonuses dictionary
- [ ] `meleeDamage` mapped to `melee_damage` in bonuses
- [ ] Tags, preferred damage types, and armor type loaded correctly

**WorldGenerationConfig**:
- [ ] Danger distribution at spawn (distance=0) is 100% peaceful (1.0, 0.0, 0.0)
- [ ] Danger distribution at transition zone has correct values
- [ ] Biome distribution sums to 1.0 (validated)
- [ ] Dilutive normalization works when values do not sum to 1.0
- [ ] `GetDangerDistribution(0)` returns safe zone distribution
- [ ] `GetResourceConfig("peaceful")` returns correct spawn config

**NPCDatabase**:
- [ ] Loads NPCs with correct positions
- [ ] Quest parsing handles both v1.0 and v2.0 formats
- [ ] Dialogue lines extracted from enhanced format correctly

**ResourceNodeDatabase**:
- [ ] Loads all nodes with correct categories (tree/ore/stone)
- [ ] `GetIconName("copper_vein")` returns `"copper_ore_node"`
- [ ] `GetTreesByTier(2)` returns only tier 1 and 2 trees
- [ ] Category caching produces correct list sizes

**TranslationDatabase**:
- [ ] Default values match Section 3.5 exactly
- [ ] Loading from JSON file populates `DurationSeconds` and `ManaCosts`

**Config Constants**:
- [ ] `GameConfig.BASE_WIDTH` == 1600
- [ ] `GameConfig.BASE_HEIGHT` == 900
- [ ] `GameConfig.CHUNK_SIZE` == 16
- [ ] `GameConfig.TILE_SIZE` == 32
- [ ] `GameConfig.PLAYER_SPEED` == 0.15f
- [ ] `GameConfig.INTERACTION_RANGE` == 3.5f
- [ ] `GameConfig.RARITY_COLORS["legendary"]` == (255, 128, 0)
- [ ] All 28 color constants match Python values exactly

### 5.4 Phase 2 Quality Gate

All of the following must pass before Phase 2 is considered complete:

- [ ] All 13 databases load correctly from JSON files
- [ ] All query methods return correct data types and values
- [ ] Translation tables are exact matches (mana, cooldown, duration, magnitude)
- [ ] Config constants match Python values exactly (spot-check all categories)
- [ ] Initialization order preserved (no circular dependencies, no null references)
- [ ] Fallback/placeholder behavior works when JSON files are missing
- [ ] UpdateLoader scans and loads dynamic content correctly
- [ ] Comparison tests pass: load same JSON in Python and C#, compare output counts and sample values
- [ ] No compilation warnings in database code
- [ ] All unit tests pass (see Section 6)

---

## 6. Testing Requirements

### 6.1 Unit Tests Per Database

Each database requires the following test categories:

**Load Tests**:
```csharp
[Test] public void LoadFromFile_ValidJson_LoadsCorrectCount()
[Test] public void LoadFromFile_MissingFile_CreatesPlaceholders()
[Test] public void LoadFromFile_MalformedJson_HandlesGracefully()
[Test] public void LoadFromFile_EmptyCollections_NoExceptions()
```

**Query Tests**:
```csharp
[Test] public void GetItem_ExistingId_ReturnsCorrectData()
[Test] public void GetItem_NonexistentId_ReturnsNull()
[Test] public void GetItem_EmptyString_ReturnsNull()
```

**Singleton Tests**:
```csharp
[Test] public void GetInstance_MultipleCalls_ReturnsSameInstance()
[Test] public void ResetInstance_ThenGetInstance_ReturnsNewInstance()
```

### 6.2 Integration Tests

**Full Initialization Sequence**:
```csharp
[Test]
public void DatabaseInitializer_InitializeAll_CompletesWithoutErrors()
{
    // Arrange: copy test JSON files to StreamingAssets
    // Act
    DatabaseInitializer.InitializeAll();
    // Assert: all databases report Loaded == true
}
```

**Cross-Reference Tests**:
```csharp
[Test]
public void RecipeInputs_ReferenceExistingMaterials()
{
    // Every recipe input materialId should exist in MaterialDatabase
}

[Test]
public void RecipeOutputs_ReferenceExistingEquipmentOrMaterials()
{
    // Every recipe outputId should exist in either EquipmentDatabase or MaterialDatabase
}

[Test]
public void PlacementRecipeIds_MatchRecipeDatabase()
{
    // Every PlacementDatabase recipe_id should exist in RecipeDatabase
}
```

### 6.3 Comparison Tests (Python vs C#)

For critical databases, create a Python script that outputs canonical data and compare with C# output:

```python
# comparison_export.py
import json
mat_db = MaterialDatabase.get_instance()
mat_db.load_from_file("items.JSON/items-materials-1.JSON")
output = {
    "total_count": len(mat_db.materials),
    "sample_items": {
        "copper_ore": {"tier": mat_db.get_material("copper_ore").tier, "category": mat_db.get_material("copper_ore").category},
        "iron_ingot": {"tier": mat_db.get_material("iron_ingot").tier, "category": mat_db.get_material("iron_ingot").category},
    }
}
with open("comparison_material_db.json", "w") as f:
    json.dump(output, f)
```

Run the same queries in C# and assert results match. Priority databases for comparison testing:
1. MaterialDatabase (most entries)
2. EquipmentDatabase (most complex construction logic)
3. SkillDatabase (translation tables)
4. RecipeDatabase (multiple output formats)
5. WorldGenerationConfig (normalization logic)

### 6.4 Edge Case Tests

- [ ] Loading a JSON file with unknown/extra fields (should not crash)
- [ ] Loading a JSON file with missing optional fields (should use defaults)
- [ ] Empty `materials` array in JSON (should result in empty dict, not error)
- [ ] Duplicate material IDs across files (later load should NOT overwrite in MaterialDatabase)
- [ ] Unicode characters in material names and descriptions
- [ ] Very large JSON files (stress test with 1000+ entries)
- [ ] `null` values in JSON where strings expected (should use empty string defaults)

---

## 7. Common Pitfalls

### 7.1 JSON Field Name Casing
Python internally uses snake_case but JSON uses camelCase. The database loaders perform manual mapping (e.g., `mat_data.get('materialId', '')`). In C#, use `[JsonProperty("materialId")]` attributes on deserialization DTOs, or manual `JObject` parsing matching the Python approach.

### 7.2 Multiple Load Methods in MaterialDatabase
`MaterialDatabase` has THREE separate load methods (`LoadFromFile`, `LoadRefiningItems`, `LoadStackableItems`) that use DIFFERENT JSON field names for the same concept:
- `materialId` in materials JSON
- `itemId` in refining and stackable item JSONs
- `stackSize` in refining vs `maxStack` in materials

### 7.3 EquipmentDatabase Accumulates from Multiple Files
`EquipmentDatabase.LoadFromFile()` is called 4+ times with different files. Each call adds to the existing `Items` dictionary. Do NOT clear the dictionary between loads.

### 7.4 RecipeDatabase Enchanting Recipe Differences
Enchanting/adornment recipes use `enchantmentId` instead of `outputId`. The recipe also has `enchantmentName`, `applicableTo`, and `effect` fields not present in other recipes. The `is_enchantment` flag on the Recipe model distinguishes these.

### 7.5 WorldGenerationConfig Dilutive Normalization
Danger distributions and water subtype probabilities use dilutive normalization: if values do not sum to 1.0, they are all divided by their sum. This is NOT clamping -- it is proportional scaling. Example: `(6, 3, 1)` becomes `(0.6, 0.3, 0.1)`.

### 7.6 Icon Path Auto-Generation Differs Per Database
Each database has its own logic for generating icon paths when `iconPath` is missing from JSON:
- MaterialDatabase: `{category_subdir}/{materialId}.png`
- EquipmentDatabase: `{slot_based_subdir}/{itemId}.png`
- SkillDatabase: `skills/{skillId}.png`
- TitleDatabase: `titles/{titleId}.png`
- ResourceNodeDatabase: `resources/{icon_name_mapped}.png` (uses ICON_NAME_MAP!)

### 7.7 ClassDatabase Bonus Key Mapping is NOT Generic
The `_map_bonuses` method has a hardcoded dictionary of 20 JSON-to-internal key mappings. Unmapped keys fall through to `key.ToLower().Replace(" ", "_")`. The same pattern exists in TitleDatabase with 29 mappings. These two mapping dictionaries are DIFFERENT and must be ported independently.

### 7.8 NPCDatabase Dual-Format Support
Both NPC and Quest loading support two JSON formats (v1.0 and v2.0/enhanced). The loader tries the enhanced file first and falls back. Within each file, individual fields also have dual-format support (e.g., `quest_id` vs `questId`). All these fallbacks must be preserved.

### 7.9 PlacementDatabase Five Separate Loaders
Each crafting discipline has its own PlacementData fields. The `PlacementData` model is a union type -- different fields are populated depending on the discipline. In C#, consider using a discriminated union pattern or simply nullable fields matching the Python approach.

### 7.10 Singleton Thread Safety
Python's GIL provides implicit thread safety for singleton creation. C# requires explicit locking (double-checked locking pattern). Use `lock` in `GetInstance()` for all databases. This is especially important because `UpdateLoader` may run on a background thread.

### 7.11 ConditionFactory Dependency
`TitleDatabase` and `SkillUnlockDatabase` both depend on `ConditionFactory` (from `data/models/unlock_conditions.py`) to parse requirement conditions from JSON. This class must be ported in Phase 1 as part of the data models. Verify it exists before starting Phase 2.

### 7.12 RecipeDatabase Debug Flag Integration
`RecipeDatabase.CanCraft()` and `ConsumeMaterials()` check `Config.DEBUG_INFINITE_RESOURCES`. In Python, this is done with a try/except import to avoid circular imports. In C#, reference `GameConfig.DEBUG_INFINITE_RESOURCES` directly since static classes have no circular dependency issues.

---

## 8. File Inventory

### JSON Files to Copy to Unity StreamingAssets/Content/

```
items.JSON/
  items-materials-1.JSON
  items-smithing-2.JSON
  items-alchemy-1.JSON
  items-refining-1.JSON
  items-engineering-1.JSON
  items-tools-1.JSON

recipes.JSON/
  recipes-smithing-3.json
  recipes-alchemy-1.JSON
  recipes-refining-1.JSON
  recipes-engineering-1.JSON
  recipes-adornments-1.json

placements.JSON/
  placements-smithing-1.JSON
  placements-refining-1.JSON
  placements-alchemy-1.JSON
  placements-engineering-1.JSON
  placements-adornments-1.JSON

progression/
  classes-1.JSON
  titles-1.JSON
  npcs-enhanced.JSON
  npcs-1.JSON
  quests-enhanced.JSON
  quests-1.JSON
  skill-unlocks.JSON

Skills/
  skills-skills-1.JSON

Definitions.JSON/
  skills-translation-table.JSON
  world_generation.JSON
  map-waypoint-config.JSON
  Resource-node-1.JSON
  stats-calculations.JSON
  tag-definitions.JSON
  hostiles-1.JSON
  crafting-stations-1.JSON
```

### C# Files to Create

```
Game1.Data.Databases/
  MaterialDatabase.cs
  EquipmentDatabase.cs
  RecipeDatabase.cs
  SkillDatabase.cs
  PlacementDatabase.cs
  TitleDatabase.cs
  ClassDatabase.cs
  NPCDatabase.cs
  ResourceNodeDatabase.cs
  SkillUnlockDatabase.cs
  TranslationDatabase.cs
  WorldGenerationConfig.cs
  MapWaypointConfig.cs
  UpdateLoader.cs
  DatabaseInitializer.cs
  JsonLoader.cs

Game1.Core/
  GameConfig.cs
  GamePaths.cs
```

Total: **18 C# files** to create in Phase 2.

---

## 9. Estimated Effort

| Task | Estimated Hours |
|------|----------------|
| JsonLoader helper + StreamingAssets setup | 2 |
| GameConfig + GamePaths | 2 |
| TranslationDatabase | 1 |
| WorldGenerationConfig (complex, many nested types) | 4 |
| MapWaypointConfig | 3 |
| ClassDatabase | 2 |
| ResourceNodeDatabase | 2 |
| MaterialDatabase (3 load methods) | 3 |
| EquipmentDatabase (complex creation logic) | 5 |
| SkillDatabase | 2 |
| RecipeDatabase (3 output formats) | 3 |
| PlacementDatabase (5 discipline loaders) | 3 |
| TitleDatabase (bonus mapping + ConditionFactory) | 3 |
| SkillUnlockDatabase | 2 |
| NPCDatabase (dual-format) | 3 |
| UpdateLoader | 3 |
| DatabaseInitializer | 1 |
| Unit tests (all databases) | 8 |
| Integration tests + comparison tests | 4 |
| **Total** | **~56 hours** |

---

## 10. Success Criteria

Phase 2 is complete when:

1. All 18 C# files compile without errors or warnings
2. `DatabaseInitializer.InitializeAll()` runs to completion with all JSON files present
3. Every database reports `Loaded == true` after initialization
4. All unit tests pass (minimum: load, query, fallback per database)
5. Comparison tests confirm Python and C# load identical data from same JSON files
6. Translation table values are bit-for-bit identical
7. Config constants match Python values exactly
8. Initialization order is documented and enforced (no circular dependencies)
9. Error handling is graceful: missing files produce warnings and fallback data, not crashes
10. Code review confirms all 7 common pitfalls (Section 7) are addressed

**Next Phase**: Phase 3 (Tag System) depends on Phase 2 for database access to tag definitions, skill definitions, and equipment data.
