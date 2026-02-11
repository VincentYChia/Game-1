# Migration Improvements: Architecture & Efficiency

**Purpose**: Improvements to make during the C# migration. Organized by scope: macro-level architecture changes (decide now) and per-file fixes (apply during porting).

**Philosophy**: This is a rewrite, not a blind port. We preserve all game mechanics exactly (formulas, constants, behavior) but improve the architecture that delivers them. Think: same engine output, cleaner engine internals.

**Rule**: Every improvement must work across the ENTIRE system, not just the file it originates from. If a change in EquipmentManager requires changes in SaveManager, Character, and CombatManager — all four must be updated together or the improvement is rejected.

---

## Quick Reference: All Improvements

| ID | Name | Part | Phase(s) |
|----|------|------|----------|
| **MACRO-1** | Event System (GameEvents) | 1 | 1,3,4,6 |
| **MACRO-2** | EquipmentSlot/HandType Enums | 1 | 1,2,3,4 |
| **MACRO-3** | Separate UI State from Data | 1 | 1,6 |
| **MACRO-4** | Save Migration Pipeline | 1 | 1,4 |
| **MACRO-5** | Effect Dispatch Table | 1 | 3,4 |
| **MACRO-6** | GamePosition (Vector3) | 5 | 1,2,3,4 |
| **MACRO-7** | 3D-Ready Combat Geometry | 5 | 4 |
| **MACRO-8** | Crafting Base Class | 6 | 4 |
| **FIX-1** | ItemStack Factory Method | 2 | 1,3 |
| **FIX-2** | Equipment ToDict/FromDict | 2 | 1,4 |
| **FIX-3** | Single Enemy Parser | 2 | 2 |
| **FIX-4** | Inventory Count Cache | 2 | 3 |
| **FIX-5** | Pre-sorted Enemy Abilities | 2 | 2 |
| **FIX-6** | Rarity Single Source of Truth | 2 | 1 |
| **FIX-7** | Cached Available Skills | 2 | 3 |
| **FIX-8** | Invented Recipe UUID | 2 | 4,7 |
| **FIX-9** | Computed Equipment Bonuses | 2 | 3,4 |
| **FIX-10** | GameEngine Decomposition Map | 6 | 6 |
| **FIX-11** | Stat Recalculation Caching | 6 | 3 |
| **FIX-12** | NavMesh-Ready Pathfinder | 6 | 4 |
| **FIX-13** | Centralized ItemFactory | 6 | 1,2,3,4 |
| **Part 4** | IGameItem Type Hierarchy | 4 | 1,2,3,4 |

**Document Structure**: Part 1 (macro changes) → Part 2 (per-file fixes) → Part 3 (what NOT to improve) → Part 4 (item hierarchy) → Part 5 (3D readiness) → Part 6 (additional fixes) → Part 7 (application schedule)

---

## Part 1: Macro Architecture Changes (Decide During Planning, Implement Across All Phases)

These are structural improvements that affect multiple phases and must be designed upfront.

---

### MACRO-1: Event System for Component Decoupling

**Problem Found In**: `character.py:148-149`, `equipment_manager.py:77,85-90`, `character.py:186-198`

**Current State (Python)**:
- Character holds direct references to WorldSystem and DungeonManager (`character.py:148-149`)
- EquipmentManager calls `character.recalculate_stats()` directly (`equipment_manager.py:77`)
- EquipmentManager accesses `character.stat_tracker` via hasattr check (`equipment_manager.py:85`)
- Class selection callback mutates equipment efficiency in-place (`character.py:186-198`)

This creates circular dependencies: `GameEngine → Character → WorldSystem → GameEngine`

**C# Solution**: Simple event bus

```csharp
namespace Game1.Core
{
    // Lightweight event system — no Unity dependency
    public static class GameEvents
    {
        // Equipment
        public static event Action<EquipmentItem, EquipmentSlot> OnEquipmentChanged;
        public static event Action<EquipmentItem, EquipmentSlot> OnEquipmentRemoved;

        // Character
        public static event Action<Character> OnCharacterDied;
        public static event Action<Character, int> OnLevelUp;
        public static event Action<Character, string> OnClassSelected;
        public static event Action<Character, string> OnTitleEarned;

        // Combat
        public static event Action<Character, Enemy, float> OnDamageDealt;
        public static event Action<Enemy> OnEnemyKilled;

        // Crafting
        public static event Action<string, string> OnItemCrafted; // discipline, itemId

        // Skills
        public static event Action<string> OnSkillLearned;
        public static event Action<string> OnSkillUsed;

        // Fire methods
        public static void RaiseEquipmentChanged(EquipmentItem item, EquipmentSlot slot)
            => OnEquipmentChanged?.Invoke(item, slot);
        // ... etc for each event

        // Reset for testing
        public static void ClearAll()
        {
            OnEquipmentChanged = null;
            OnEquipmentRemoved = null;
            OnCharacterDied = null;
            // ... etc
        }
    }
}
```

**How it changes the flow**:
```
PYTHON (current):
  EquipmentManager.equip() → character.recalculate_stats()   // direct call up
                            → character.stat_tracker.record() // hasattr check

C# (improved):
  EquipmentManager.equip() → GameEvents.RaiseEquipmentChanged(item, slot)
                              ↓ subscribers:
                              → CharacterStats.OnEquipmentChanged()    // recalculates
                              → StatTracker.OnEquipmentChanged()       // records
                              → CombatManager.OnEquipmentChanged()     // updates damage cache
```

**Affected Phases**: Phase 1 (define GameEvents), Phase 3 (components subscribe), Phase 4 (systems subscribe), Phase 6 (UI subscribes for display updates)

**Scope**: ~15 direct call sites become event emissions. ~20 subscribers added across systems.

**Risk**: Low. Events are additive — if a subscriber is missing, the game doesn't crash, it just doesn't react to that event.

---

### MACRO-2: EquipmentSlot Enum Replaces Magic Strings

**Problem Found In**: `equipment_manager.py:10-21`, `equipment_db.py:257-301` (triplicated), `character.py` (30+ occurrences), `save_manager.py`, `skill_manager.py:662`

**Current State (Python)**: Slot names are raw strings (`'mainHand'`, `'offHand'`, `'helmet'`, etc.) appearing in 6+ files with no compile-time checking. A typo like `'mainhand'` silently fails.

**C# Solution**: Already planned in Phase 1 enums, but the scope is larger than originally documented:

```csharp
public enum EquipmentSlot
{
    MainHand,
    OffHand,
    Helmet,
    Chestplate,
    Leggings,
    Boots,
    Gauntlets,
    Accessory,
    Axe,      // Tool slots
    Pickaxe
}

public static class EquipmentSlotExtensions
{
    // JSON compatibility: "mainHand" → EquipmentSlot.MainHand
    private static readonly Dictionary<string, EquipmentSlot> JsonMap = new()
    {
        ["mainHand"] = EquipmentSlot.MainHand,
        ["offHand"] = EquipmentSlot.OffHand,
        ["helmet"] = EquipmentSlot.Helmet,
        ["head"] = EquipmentSlot.Helmet,        // JSON alias
        ["chestplate"] = EquipmentSlot.Chestplate,
        ["chest"] = EquipmentSlot.Chestplate,    // JSON alias
        ["leggings"] = EquipmentSlot.Leggings,
        ["legs"] = EquipmentSlot.Leggings,       // JSON alias
        ["boots"] = EquipmentSlot.Boots,
        ["feet"] = EquipmentSlot.Boots,          // JSON alias
        ["gauntlets"] = EquipmentSlot.Gauntlets,
        ["hands"] = EquipmentSlot.Gauntlets,     // JSON alias
        ["accessory"] = EquipmentSlot.Accessory,
        ["axe"] = EquipmentSlot.Axe,
        ["pickaxe"] = EquipmentSlot.Pickaxe,
    };

    public static EquipmentSlot FromJson(string jsonSlot)
        => JsonMap.TryGetValue(jsonSlot, out var slot) ? slot : EquipmentSlot.MainHand;
}
```

**This eliminates**:
- The triple slot_mapping dict in `equipment_db.py` (257-301) → one `FromJson()` method
- All `hasattr` / string comparison in `equipment_manager.py`
- All raw string slot keys in `save_manager.py`
- The 30+ occurrences in `character.py`

**Similarly for HandType**:
```csharp
public enum HandType { OneHanded, TwoHanded, Versatile }
```
Replaces `"1H"`, `"2H"`, `"versatile"`, `"default"` strings in `equipment_manager.py:41-65` and `equipment_db.py:340-347`.

**Affected Phases**: Phase 1 (define enums), Phase 2 (database uses enum), Phase 3 (EquipmentManager uses enum), Phase 4 (combat uses enum)

---

### MACRO-3: Separate UI State from Data Models

**Problem Found In**: `inventory.py:113-115`

**Current State (Python)**: The `Inventory` data class contains drag-and-drop UI state:
```python
self.dragging_slot: Optional[int] = None
self.dragging_stack: Optional[ItemStack] = None
self.dragging_from_equipment: bool = False
```

If the game saves during a drag, the dragged item is lost (it's removed from the slot at `start_drag` line 173 but `dragging_stack` is not serialized).

**C# Solution**: Data model has NO UI state. UI layer manages its own drag state:

```csharp
// Data layer (Phase 1) — clean
namespace Game1.Entities.Components
{
    public class Inventory
    {
        private ItemStack[] _slots;
        public int MaxSlots { get; }

        // Pure data operations only
        public bool AddItem(string itemId, int quantity) { ... }
        public bool RemoveItem(string itemId, int quantity) { ... }
        public bool HasItem(string itemId, int quantity) { ... }
        public int GetItemCount(string itemId) { ... }
        public ItemStack GetSlot(int index) { ... }
        public void SetSlot(int index, ItemStack stack) { ... }
        public void SwapSlots(int a, int b) { ... }
    }
}

// UI layer (Phase 6) — owns drag state
namespace Game1.UI
{
    public class InventoryDragHandler
    {
        private int _sourceSlot = -1;
        private ItemStack _draggedStack;
        private bool _fromEquipment;

        public void StartDrag(int slotIndex) { ... }
        public void CompleteDrag(int targetSlot) { ... }
        public void CancelDrag() { ... } // Always restores item
    }
}
```

**Affected Phases**: Phase 1 (clean Inventory model), Phase 6 (InventoryDragHandler MonoBehaviour)

---

### MACRO-4: Save System Migration Pipeline

**Problem Found In**: `save_manager.py:484-486`, `character.py:217-361` (legacy save/load)

**Current State (Python)**:
- Version check only warns, never migrates (`save_manager.py:484`)
- Two separate save/load systems exist (`Character.save_to_file`/`load_from_file` AND `SaveManager`)
- The legacy system at `character.py:217-361` loses durability, enchantments, and crafted stats
- Optional fields are conditionally serialized based on Python truthiness (`save_manager.py:226-251`)

**C# Solution**: Proper version-based migration:

```csharp
namespace Game1.Systems.Save
{
    public class SaveMigrator
    {
        private static readonly Dictionary<string, Func<JObject, JObject>> Migrations = new()
        {
            ["2.0"] = MigrateV2ToV2_1,
            ["2.1"] = MigrateV2_1ToV3,
            ["3.0"] = MigrateV3ToV3_1, // Future
        };

        public static JObject MigrateToLatest(JObject saveData)
        {
            string version = saveData["version"]?.ToString() ?? "1.0";

            while (version != SaveManager.CurrentVersion)
            {
                if (!Migrations.TryGetValue(version, out var migrator))
                    throw new SaveCorruptException($"No migration path from v{version}");

                saveData = migrator(saveData);
                version = saveData["version"].ToString();
                Debug.Log($"[SaveMigrator] Migrated save from v{version}");
            }

            return saveData;
        }

        private static JObject MigrateV2ToV2_1(JObject data)
        {
            // Example: Add "soulbound" field to all equipment
            // ...
            data["version"] = "2.1";
            return data;
        }
    }
}
```

**Additional rules**:
- Delete `Character.save_to_file()` and `Character.load_from_file()` — only `SaveManager`
- Always serialize all fields (no conditional serialization)
- Equipment serialization via `EquipmentItem.ToDict()` / `EquipmentItem.FromDict()` (eliminates the triple duplication in save_manager.py:205-318 and character.py:426-536)

**Affected Phases**: Phase 1 (add `ToDict()`/`FromDict()` to models), Phase 4 (SaveManager with migration pipeline)

---

### MACRO-5: Effect Type Dispatch Table Replaces String Chain

**Problem Found In**: `skill_manager.py:315-567` (250+ lines of if/elif on strings)

**Current State (Python)**:
```python
if effect.effect_type == "empower":     # 20 lines
elif effect.effect_type == "quicken":   # 20 lines
elif effect.effect_type == "fortify":   # 20 lines
# ... 10 more branches, each 15-30 lines of nearly identical code
```

Each branch: get magnitude → apply scaling → create ActiveBuff → print message.

**C# Solution**: Strategy/dispatch pattern:

```csharp
namespace Game1.Systems.Effects
{
    public class SkillEffectDispatcher
    {
        private readonly Dictionary<string, ISkillEffectHandler> _handlers;

        public SkillEffectDispatcher()
        {
            _handlers = new Dictionary<string, ISkillEffectHandler>
            {
                ["empower"] = new BuffEffectHandler("melee_damage", 0.5f),
                ["quicken"] = new BuffEffectHandler("attack_speed", 0.3f),
                ["fortify"] = new BuffEffectHandler("defense", 0.4f),
                ["pierce"] = new BuffEffectHandler("armor_penetration", 0.25f),
                ["restore"] = new HealEffectHandler(),
                ["regenerate"] = new HotEffectHandler(), // Heal over time
                ["devastate"] = new DamageBuffHandler(),
                // ... each handler is a small, testable class
            };
        }

        public void Apply(SkillEffect effect, Character caster, float magnitude)
        {
            if (_handlers.TryGetValue(effect.EffectType, out var handler))
                handler.Apply(caster, effect, magnitude);
            else
                Debug.LogWarning($"[SkillEffect] Unknown effect type: {effect.EffectType}");
        }
    }

    public interface ISkillEffectHandler
    {
        void Apply(Character caster, SkillEffect effect, float magnitude);
    }

    // Covers empower, quicken, fortify, pierce, enrich, elevate — all buff variants
    public class BuffEffectHandler : ISkillEffectHandler
    {
        private readonly string _statName;
        private readonly float _baseMultiplier;

        public BuffEffectHandler(string statName, float baseMultiplier)
        {
            _statName = statName;
            _baseMultiplier = baseMultiplier;
        }

        public void Apply(Character caster, SkillEffect effect, float magnitude)
        {
            float scaledMagnitude = magnitude * _baseMultiplier;
            float duration = effect.Duration;

            caster.Buffs.AddBuff(new ActiveBuff
            {
                StatName = _statName,
                Magnitude = scaledMagnitude,
                Duration = duration,
                Source = effect.EffectType
            });
        }
    }
}
```

**This eliminates**: 250+ lines of copy-pasted if/elif, the triple-duplicated level scaling, and the fragile string matching. Each handler is independently testable.

**Affected Phases**: Phase 3 (BuffManager interface), Phase 4 (SkillEffectDispatcher)

---

## Part 2: Per-File Fixes (Apply During Porting of Each File)

These are smaller improvements that the migrator applies as they port each file. They don't require cross-phase design decisions.

---

### FIX-1: ItemStack Factory Method (inventory.py)

**Problem**: `ItemStack.__post_init__` calls database singletons, creating equipment instances that may be immediately overwritten during save loading (`inventory.py:19-34`).

**Fix**: In C#, the `ItemStack` constructor takes only primitive data. A static factory handles DB lookups:

```csharp
public class ItemStack
{
    // Constructor: pure data, no side effects
    public ItemStack(string itemId, int quantity, int maxStack = 99,
                     EquipmentItem equipmentData = null, string rarity = "common")
    {
        ItemId = itemId;
        Quantity = quantity;
        MaxStack = maxStack;
        EquipmentData = equipmentData;
        Rarity = rarity;
    }

    // Factory: uses databases, has side effects
    public static ItemStack CreateFromDatabase(string itemId, int quantity)
    {
        int maxStack = 99;
        EquipmentItem equipData = null;
        string rarity = "common";

        var mat = MaterialDatabase.Instance.GetMaterial(itemId);
        if (mat != null)
        {
            maxStack = mat.MaxStack;
            rarity = mat.Rarity;
        }

        if (EquipmentDatabase.Instance.IsEquipment(itemId))
        {
            maxStack = 1;
            equipData = EquipmentDatabase.Instance.CreateEquipmentFromId(itemId);
        }

        return new ItemStack(itemId, quantity, maxStack, equipData, rarity);
    }
}
```

**Apply during**: Phase 1 (ItemStack model) and Phase 3 (Inventory uses factory)

---

### FIX-2: Equipment Serialization Methods (save_manager.py)

**Problem**: Equipment serialization duplicated in 3 places (`save_manager.py:205-256`, `save_manager.py:270-318`, `character.py:426-536`).

**Fix**: Add `ToDict()` and `FromDict()` to `EquipmentItem` model:

```csharp
public class EquipmentItem
{
    public Dictionary<string, object> ToDict()
    {
        var dict = new Dictionary<string, object>
        {
            ["item_id"] = ItemId,
            ["name"] = Name,
            ["tier"] = Tier,
            ["rarity"] = Rarity,
            ["slot"] = Slot.ToJsonString(),
            ["durability_current"] = DurabilityCurrent,
            ["durability_max"] = DurabilityMax,
            ["damage"] = new[] { Damage.Min, Damage.Max },
            ["defense"] = Defense,
            ["weight"] = Weight,
            ["tags"] = Tags,              // Always include, even if empty
            ["effect_tags"] = EffectTags, // Always include
            ["enchantments"] = Enchantments.Select(e => e.ToDict()).ToList(),
        };
        return dict;
    }

    public static EquipmentItem FromDict(Dictionary<string, object> data)
    {
        return new EquipmentItem
        {
            ItemId = (string)data["item_id"],
            Name = (string)data["name"],
            // ... all fields with defaults for missing keys
        };
    }
}
```

**Apply during**: Phase 1 (add to model), Phase 4 (SaveManager uses it)

---

### FIX-3: Single Enemy Parser (enemy.py)

**Problem**: `load_from_file()` and `load_additional_file()` are ~110 lines each of duplicated parsing (`enemy.py:129-351`). The `* 0.1` health multiplier is baked into both.

**Fix**:
```csharp
public class EnemyDatabase
{
    // Private shared parser — single source of truth
    private List<EnemyDefinition> ParseEnemyData(JObject data, float healthMultiplier)
    {
        var enemies = new List<EnemyDefinition>();
        // ... one implementation of parsing logic
        // healthMultiplier applied here (default 1.0 for production)
        return enemies;
    }

    public void LoadFromFile(string path)
    {
        var data = JsonLoader.LoadDynamic(path);
        var enemies = ParseEnemyData(data, GameConfig.EnemyHealthMultiplier);
        foreach (var e in enemies) _enemies[e.EnemyId] = e;
    }

    public void LoadAdditionalFile(string path)
    {
        var data = JsonLoader.LoadDynamic(path);
        var enemies = ParseEnemyData(data, GameConfig.EnemyHealthMultiplier);
        foreach (var e in enemies) _enemies[e.EnemyId] = e;
    }
}
```

Also moves the `* 0.1` to `GameConfig.EnemyHealthMultiplier` — configurable, visible, not hidden in parsing code.

**Apply during**: Phase 2 (EnemyDatabase) and Phase 4 (CombatManager references config)

---

### FIX-4: Inventory Item Count Cache (inventory.py, recipe_db.py)

**Problem**: Crafting a 5-input recipe causes 15 full inventory scans (`inventory.py:170-171`, `recipe_db.py:152-211`).

**Fix**: Maintain a count cache:
```csharp
public class Inventory
{
    private ItemStack[] _slots;
    private Dictionary<string, int> _countCache = new();

    public int GetItemCount(string itemId)
    {
        return _countCache.TryGetValue(itemId, out int count) ? count : 0;
    }

    public bool AddItem(string itemId, int quantity)
    {
        // ... add to slots ...
        _countCache[itemId] = _countCache.GetValueOrDefault(itemId) + quantity;
        return true;
    }

    public bool RemoveItem(string itemId, int quantity)
    {
        if (GetItemCount(itemId) < quantity) return false;
        // ... remove from slots ...
        _countCache[itemId] -= quantity;
        if (_countCache[itemId] <= 0) _countCache.Remove(itemId);
        return true;
    }

    // Rebuild cache on load or after bulk operations
    public void RebuildCountCache()
    {
        _countCache.Clear();
        foreach (var slot in _slots)
        {
            if (slot != null)
                _countCache[slot.ItemId] = _countCache.GetValueOrDefault(slot.ItemId) + slot.Quantity;
        }
    }
}
```

**Apply during**: Phase 3 (Inventory component)

---

### FIX-5: Pre-sorted Enemy Abilities (enemy.py)

**Problem**: `can_use_special_ability()` sorts abilities by priority every frame per enemy (`enemy.py:862-866`).

**Fix**: Sort once at load time:
```csharp
public class EnemyDefinition
{
    // Sorted once in constructor, immutable after
    public IReadOnlyList<EnemyAbility> SpecialAbilities { get; }

    public EnemyDefinition(/* ... */, List<EnemyAbility> abilities)
    {
        SpecialAbilities = abilities
            .OrderByDescending(a => a.Priority)
            .ToList()
            .AsReadOnly();
    }
}
```

**Apply during**: Phase 2 (EnemyDatabase load) and Phase 4 (Enemy AI just iterates, no sort)

---

### FIX-6: Rarity Single Source of Truth (inventory.py)

**Problem**: `ItemStack.rarity` and `ItemStack.equipment_data.rarity` can diverge (`inventory.py:16`).

**Fix**: Equipment items own their rarity. Non-equipment items have rarity on the stack. Never both:
```csharp
public class ItemStack
{
    public string ItemId { get; }
    public int Quantity { get; set; }
    public EquipmentItem EquipmentData { get; set; }

    // Computed — single source of truth
    public string Rarity =>
        EquipmentData != null ? EquipmentData.Rarity : _baseRarity;

    private string _baseRarity;
}
```

**Apply during**: Phase 1 (ItemStack model)

---

### FIX-7: Cached Available Skills (skill_manager.py)

**Problem**: `get_available_skills()` scans all 100+ skills with requirement checks every time the menu opens (`skill_manager.py:129-149`).

**Fix**: Cache and invalidate on relevant events:
```csharp
public class SkillManager
{
    private List<string> _cachedAvailableSkills;
    private bool _availableSkillsDirty = true;

    public SkillManager()
    {
        // Invalidate cache when relevant things change
        GameEvents.OnLevelUp += (_, _) => _availableSkillsDirty = true;
        GameEvents.OnTitleEarned += (_, _) => _availableSkillsDirty = true;
        GameEvents.OnSkillLearned += _ => _availableSkillsDirty = true;
    }

    public List<string> GetAvailableSkills()
    {
        if (_availableSkillsDirty)
        {
            _cachedAvailableSkills = ComputeAvailableSkills();
            _availableSkillsDirty = false;
        }
        return _cachedAvailableSkills;
    }
}
```

**Apply during**: Phase 3 (SkillManager), requires MACRO-1 (events)

---

### FIX-8: Invented Recipe UUID (character.py)

**Problem**: Invented recipe IDs `f"invented_{item_id}"` can collide if two inventions produce items with the same name (`character.py:658`).

**Fix**:
```csharp
string recipeId = $"invented_{discipline}_{Guid.NewGuid():N}";
```

**Apply during**: Phase 4 (Recipe system) and Phase 7 (LLM stub)

---

### FIX-9: Computed Equipment Bonuses (character.py)

**Problem**: Class selection callback mutates equipment efficiency in-place, permanently baking in the bonus (`character.py:186-198`).

**Fix**: Compute bonuses dynamically:
```csharp
public float GetEffectiveEfficiency(EquipmentItem tool)
{
    float baseEfficiency = tool.Efficiency;
    float classBonus = ClassSystem.GetToolBonus(CurrentClass, tool.ItemType);
    return baseEfficiency * (1f + classBonus);
}
```

Never mutate the source item. The bonus is computed from current class + base item stats.

**Apply during**: Phase 3 (Character) and Phase 4 (ClassSystem)

---

## Part 3: What NOT to Improve

Some things look improvable but should be left as-is during migration:

1. **Tag system architecture** — It works well. The composable tag pattern is clean. Don't refactor.
2. **Crafting minigame formulas** — The math is correct and tuned. Port exactly.
3. **Difficulty/Reward calculators** — These are well-designed. Port 1:1.
4. **World generation algorithm** — Deterministic chunk generation works. Port exactly.
5. **JSON file schemas** — Don't change field names, structure, or organization. Moddability depends on stability.
6. **ML preprocessing** — Must match Python EXACTLY for model compatibility. Zero improvements.
7. **Database singleton pattern** — Already addressed in CONVENTIONS.md. The pattern itself is fine.
8. **Game balance numbers** — ALL constants transfer verbatim. Do not rebalance.

---

## Part 4: Item Pipeline Overhaul — Class Hierarchy for Items

### The Problem

The current Python item system uses a **flat, dict-based approach** where items are fundamentally dictionaries with inconsistent type information. This creates several cascading problems:

**Finding 1: Items lose identity as they move through the pipeline**

- In `inventory.py:6-17`, `ItemStack` is a `@dataclass` that stores `item_id: str` and `quantity: int`. But depending on context, the same item might be represented as:
  - A `MaterialDefinition` object (from `material_db.py`)
  - An `EquipmentItem` object (from `equipment_db.py`)
  - A raw `dict` (during save/load, `save_manager.py:205-318`)
  - A string ID (in recipe inputs, `recipes.py:5-10`)
  - An `ItemStack` with embedded `EquipmentItem` (in inventory)

- There is NO common base type. A material, equipment item, potion, and tool share no common interface.

**Finding 2: Type checks scattered everywhere**

- `inventory.py:19-34` (`__post_init__`) — checks `EquipmentDatabase.is_equipment()` and `MaterialDatabase.get_material()` to determine behavior
- `equipment_manager.py:41-65` — checks string-based `hand_type` field
- `save_manager.py:196-318` — branches on whether an item has `equipment_data`
- `character.py:426-536` — different serialization paths for equipment vs materials
- `game_engine.py` — multiple `isinstance` and `hasattr` checks for item type

**Finding 3: No polymorphism for item behaviors**

Items have behaviors (can be consumed, equipped, stacked, crafted with) but these behaviors are spread across unrelated systems with no shared interface.

### C# Solution: IGameItem Interface + Type Hierarchy

```csharp
namespace Game1.Data.Models
{
    /// <summary>
    /// Common interface for all item types in the game.
    /// Every item that can exist in inventory implements this.
    /// </summary>
    public interface IGameItem
    {
        string ItemId { get; }
        string Name { get; }
        string Category { get; }  // "material", "equipment", "consumable", "tool", "placeable"
        int Tier { get; }
        string Rarity { get; }
        int MaxStack { get; }
        bool IsStackable { get; }

        // Serialization
        Dictionary<string, object> ToSaveData();
        static IGameItem FromSaveData(Dictionary<string, object> data); // factory
    }

    /// <summary>
    /// Raw materials (ores, wood, stone, monster drops, gems, herbs).
    /// Stackable, no special behavior beyond crafting input.
    /// </summary>
    public class MaterialItem : IGameItem
    {
        public string ItemId { get; set; }
        public string Name { get; set; }
        public string Category => "material";
        public int Tier { get; set; }
        public string Rarity { get; set; }
        public int MaxStack => 99;
        public bool IsStackable => true;

        // Material-specific
        public string MaterialCategory { get; set; } // "metal", "wood", "stone", etc.
        public List<string> Tags { get; set; }
    }

    /// <summary>
    /// Weapons, armor, accessories — items with durability, stats, enchantments.
    /// Non-stackable (MaxStack = 1). Each instance is unique (can be enchanted differently).
    /// </summary>
    public class EquipmentItem : IGameItem
    {
        public string ItemId { get; set; }
        public string Name { get; set; }
        public string Category => "equipment";
        public int Tier { get; set; }
        public string Rarity { get; set; }
        public int MaxStack => 1;
        public bool IsStackable => false;

        // Equipment-specific
        public EquipmentSlot Slot { get; set; }
        public HandType HandType { get; set; }
        public DamageRange Damage { get; set; }
        public float Defense { get; set; }
        public float Weight { get; set; }
        public float DurabilityCurrent { get; set; }
        public float DurabilityMax { get; set; }
        public List<Enchantment> Enchantments { get; set; }
        public List<string> Tags { get; set; }
        public List<string> EffectTags { get; set; }
        public CraftedStats CraftedStats { get; set; }

        public float GetEffectiveness()
            => DurabilityMax <= 0 ? 0.5f : 0.5f + (DurabilityCurrent / DurabilityMax) * 0.5f;

        public EquipmentItem Copy() => new EquipmentItem { /* deep copy all fields */ };
    }

    /// <summary>
    /// Potions and consumable items.
    /// Stackable. Consumed on use, applying effects via tags.
    /// </summary>
    public class ConsumableItem : IGameItem
    {
        public string ItemId { get; set; }
        public string Name { get; set; }
        public string Category => "consumable";
        public int Tier { get; set; }
        public string Rarity { get; set; }
        public int MaxStack => 20;
        public bool IsStackable => true;

        // Consumable-specific
        public List<string> EffectTags { get; set; }
        public Dictionary<string, float> EffectParams { get; set; }
    }

    /// <summary>
    /// Placeable tools (crafting stations, turrets, traps, bombs).
    /// Stackable but with special placement behavior.
    /// </summary>
    public class PlaceableItem : IGameItem
    {
        public string ItemId { get; set; }
        public string Name { get; set; }
        public string Category => "placeable";
        public int Tier { get; set; }
        public string Rarity { get; set; }
        public int MaxStack => 10;
        public bool IsStackable => true;

        // Placeable-specific
        public string PlaceableType { get; set; } // "crafting_station", "turret", "trap", "bomb"
        public int StationTier { get; set; }
    }
}
```

### How This Fixes the Pipeline

**ItemStack becomes type-safe**:
```csharp
public class ItemStack
{
    public IGameItem Item { get; }       // Never null — always a typed item
    public int Quantity { get; set; }

    // Type-safe access
    public bool IsEquipment => Item is EquipmentItem;
    public EquipmentItem AsEquipment => Item as EquipmentItem;

    // Delegates to item
    public string Rarity => Item.Rarity;  // Single source of truth
    public int MaxStack => Item.MaxStack;
    public bool IsStackable => Item.IsStackable;
}
```

**Save/load is polymorphic** (no branching on type):
```csharp
// Save: item knows how to serialize itself
var saveData = stack.Item.ToSaveData();

// Load: factory dispatches on "category" field
var item = ItemFactory.FromSaveData(saveData); // returns correct concrete type
```

**Equipment checks are exhaustive** (no `hasattr`):
```csharp
// Instead of: if hasattr(item, 'equipment_data') and item.equipment_data is not None
// C#:
if (stack.Item is EquipmentItem equip)
{
    float effectiveness = equip.GetEffectiveness();
    // ...
}
```

### Application

| Phase | What to Implement |
|-------|-------------------|
| Phase 1 | `IGameItem` interface, `MaterialItem`, `EquipmentItem`, `ConsumableItem`, `PlaceableItem` classes, `ItemFactory` |
| Phase 2 | Databases return typed `IGameItem` (not raw dicts or mixed types) |
| Phase 3 | `ItemStack` references `IGameItem`, `Inventory` uses `ItemStack[]` |
| Phase 4 | Save/load uses `ToSaveData()`/`FromSaveData()`, crafting produces typed items |

---

## Part 5: 3D Migration Considerations

**Context**: This is not just a Python-to-C# migration. It's a migration into Unity — a 3D game engine. Even if the initial visual output is 2D sprites, the underlying architecture should be **3D-ready** so that upgrading to 3D visuals later doesn't require rewriting game logic.

### MACRO-6: Vector3 Position System (Replaces 2D Tuples)

**Current Python State**:
- `data/models/world.py:9-18` — `Position` is `@dataclass` with `x: float, y: float` only
- `character.py` — All movement uses `(x, y)` tuples or `Position(x, y)`
- `combat_manager.py` — Distance calculations use 2D Euclidean: `math.sqrt((x2-x1)**2 + (y2-y1)**2)`
- `collision_system.py` — Bresenham line-of-sight on flat 2D grid
- `effect_executor.py` — AoE geometry (cones, circles, beams) all 2D
- `enemy.py` — Pathfinding and movement on 2D grid
- `world_system.py` — Flat 100x100 tile grid with `(chunk_x, chunk_y)` addressing

**C# Solution**: Use `Vector3` everywhere, with Y as height (Unity convention):

```csharp
// Position is always 3D. For initial 2D gameplay, Y = 0.
public struct GamePosition
{
    public float X { get; set; }  // East-West
    public float Y { get; set; }  // Height (0 for flat world initially)
    public float Z { get; set; }  // North-South

    // Horizontal distance (ignoring height) — used for most game logic
    public float HorizontalDistanceTo(GamePosition other)
        => Mathf.Sqrt((X - other.X) * (X - other.X) + (Z - other.Z) * (Z - other.Z));

    // Full 3D distance — used when height matters (projectiles, flying enemies)
    public float DistanceTo(GamePosition other)
        => Vector3.Distance(ToVector3(), other.ToVector3());

    // Unity integration
    public Vector3 ToVector3() => new Vector3(X, Y, Z);
    public static GamePosition FromVector3(Vector3 v) => new GamePosition { X = v.x, Y = v.y, Z = v.z };

    // Backward compatibility: construct from 2D (height = 0)
    public static GamePosition FromXZ(float x, float z) => new GamePosition { X = x, Y = 0, Z = z };
}
```

**Decision**: The `GamePosition` struct wraps `Vector3` and provides both horizontal (XZ-plane) and full 3D distance methods. All game logic starts using `HorizontalDistanceTo()` for compatibility with 2D formulas. When height is introduced later, switching to `DistanceTo()` is a single method call change per use site.

### MACRO-7: 3D-Ready Geometry for Combat and Effects

**Current Python State** (2D geometry in `effect_executor.py`):

| Geometry | Python Implementation | Lines |
|----------|----------------------|-------|
| `single` | Direct target, no geometry | — |
| `circle` | 2D radius check: `dist <= radius` | `effect_executor.py:89-103` |
| `cone` | 2D angle check: `angle_diff <= cone_angle/2` | `effect_executor.py:105-125` |
| `beam` | 2D line check: point-to-line distance | `effect_executor.py:127-148` |
| `pierce` | 2D ray through targets | `effect_executor.py:150-168` |
| `chain` | Nearest target within range (2D) | `effect_executor.py:170-190` |

**C# Solution**: Abstract geometry into 3D-ready shape types:

```csharp
namespace Game1.Systems.Effects
{
    /// <summary>
    /// All AoE shapes support both 2D (XZ-plane) and 3D evaluation.
    /// Initially use Horizontal mode for parity with Python.
    /// Switch to Full3D when vertical gameplay is added.
    /// </summary>
    public enum DistanceMode { Horizontal, Full3D }

    public static class TargetFinder
    {
        // Global setting — starts as Horizontal for 2D parity
        public static DistanceMode Mode { get; set; } = DistanceMode.Horizontal;

        public static float GetDistance(GamePosition a, GamePosition b)
            => Mode == DistanceMode.Horizontal
                ? a.HorizontalDistanceTo(b)
                : a.DistanceTo(b);

        /// <summary>
        /// Circle/Sphere: All targets within radius.
        /// 2D: circle on XZ plane. 3D: sphere.
        /// </summary>
        public static List<ITargetable> FindInRadius(
            GamePosition center, float radius, List<ITargetable> candidates)
        {
            return candidates
                .Where(t => GetDistance(center, t.Position) <= radius)
                .ToList();
        }

        /// <summary>
        /// Cone: Targets within angle and range.
        /// 2D: fan on XZ plane. 3D: cone frustum.
        /// </summary>
        public static List<ITargetable> FindInCone(
            GamePosition origin, Vector3 direction, float range,
            float coneAngle, List<ITargetable> candidates)
        {
            float halfAngle = coneAngle / 2f;
            var flatDir = Mode == DistanceMode.Horizontal
                ? new Vector3(direction.x, 0, direction.z).normalized
                : direction.normalized;

            return candidates.Where(t =>
            {
                float dist = GetDistance(origin, t.Position);
                if (dist > range) return false;

                var toTarget = (t.Position.ToVector3() - origin.ToVector3());
                if (Mode == DistanceMode.Horizontal) toTarget.y = 0;
                toTarget.Normalize();

                float angle = Vector3.Angle(flatDir, toTarget);
                return angle <= halfAngle;
            }).ToList();
        }

        /// <summary>
        /// Beam/Ray: Targets within perpendicular distance of a line.
        /// 2D: line on XZ plane. 3D: cylinder.
        /// </summary>
        public static List<ITargetable> FindInBeam(
            GamePosition origin, Vector3 direction, float range,
            float beamWidth, List<ITargetable> candidates)
        {
            // Point-to-line distance calculation
            // Works identically in 2D (y=0) or 3D
            var end = origin.ToVector3() + direction.normalized * range;
            return candidates.Where(t =>
            {
                var point = t.Position.ToVector3();
                if (Mode == DistanceMode.Horizontal) { point.y = 0; }
                float dist = PointToLineDistance(origin.ToVector3(), end, point);
                float along = Vector3.Dot(point - origin.ToVector3(), direction.normalized);
                return dist <= beamWidth / 2f && along >= 0 && along <= range;
            }).ToList();
        }
    }
}
```

### Where 3D Changes Apply per Phase

| Phase | 2D Assumption | 3D Adaptation |
|-------|--------------|---------------|
| **Phase 1** | `Position(x, y)` dataclass | `GamePosition(x, y, z)` with `Y=0` default. `HorizontalDistanceTo()` and `DistanceTo()` |
| **Phase 2** | JSON positions `{"x": N, "y": N}` | Deserialize with `z` field (default 0 if missing). `GamePosition.FromJson(JObject)` handles both formats |
| **Phase 3** | `character.position = (x, y)` | `character.Position` is `GamePosition`. Movement uses XZ plane initially |
| **Phase 3** | `enemy.position = (x, y)` | Same as character. Enemy height field for flying enemies (0 by default) |
| **Phase 4** | `distance = sqrt((x2-x1)^2 + (y2-y1)^2)` | `TargetFinder.GetDistance()` — horizontal mode preserves Python behavior exactly |
| **Phase 4** | Bresenham LOS on 2D grid | A* pathfinding on XZ grid, LOS can use `Physics.Raycast` in 3D later |
| **Phase 4** | AoE shapes: circle, cone, beam (all 2D) | `TargetFinder` methods work in both modes. Default to Horizontal |
| **Phase 4** | Tile coordinates `(tile_x, tile_y)` | `WorldPosition` converts tile coords to world space: `new Vector3(tileX * TileSize, height, tileY * TileSize)` |
| **Phase 5** | ML preprocessing uses 2D grids | No change needed — ML preprocessing is about crafting grid images, not world positions |
| **Phase 6** | 2D Tilemap rendering | Start with Tilemap (2D on XZ plane), architecture supports swap to 3D terrain later |
| **Phase 6** | Camera is orthographic 2D | Start orthographic, architecture supports perspective switch |
| **Phase 7** | E2E tests use 2D positions | Tests use `GamePosition.FromXZ()` — 3D-compatible without changes |

### 3D-Ready Constants (Add to GameConfig)

```csharp
public static class GameConfig
{
    // World dimensions
    public const int WorldSizeX = 100;     // tiles east-west
    public const int WorldSizeZ = 100;     // tiles north-south
    public const int ChunkSize = 16;       // tiles per chunk edge
    public const float TileSize = 1.0f;    // Unity world units per tile

    // Height system (unused in 2D mode, ready for 3D)
    public const float DefaultHeight = 0f;
    public const float MaxHeight = 50f;    // for future terrain elevation
    public const float FloorHeight = 0f;   // ground level for dungeons

    // Combat ranges (in world units, not tiles)
    public const float MeleeRange = 1.5f;       // adjacent tiles
    public const float ShortRange = 5f;          // ~5 tiles
    public const float MediumRange = 10f;        // ~10 tiles
    public const float LongRange = 20f;          // ~20 tiles
    public const float MaxCombatRange = 30f;     // furthest possible ability

    // These currently use horizontal distance.
    // When vertical gameplay is added, some skills may use full 3D distance.
    public static bool UseVerticalDistance = false;
}
```

### The 3D Readiness Principle

**Do NOT implement 3D features now.** Instead, structure code so that enabling 3D later is a configuration change, not an architecture change:

1. Store positions as `Vector3` / `GamePosition` — costs nothing, enables everything
2. Use `TargetFinder.GetDistance()` instead of inline distance math — one toggle switches 2D→3D
3. Keep tile-to-world conversion centralized in `WorldSystem` — swap from Tilemap to terrain in one place
4. Use Unity's NavMesh abstraction — works for both 2D and 3D pathfinding
5. Camera system supports both orthographic (2D) and perspective (3D) via config

---

## Part 6: Additional Systemic Inefficiencies

### MACRO-8: Crafting Minigame Base Class (Eliminate 5-Way Duplication)

**Problem Found In**: All 5 crafting files in `Crafting-subdisciplines/`:
- `smithing.py` (909 lines), `alchemy.py` (1,070 lines), `refining.py` (826 lines)
- `engineering.py` (1,312 lines), `enchanting.py` (1,408 lines)

**Current State**: Each minigame file independently implements:
- Grid/canvas initialization and rendering (~80 lines each)
- Material placement handling (~60 lines each)
- Timer management (start, tick, end) (~40 lines each)
- Performance score calculation (~30 lines each)
- Result generation (quality tier → item stats) (~50 lines each)
- Tooltip rendering (~30 lines each)
- Keyboard shortcut handling (~20 lines each)

That's ~310 lines duplicated across 5 files = ~1,240 lines of redundant code.

**C# Solution**: Abstract base class with template method pattern:

```csharp
namespace Game1.Systems.Crafting.Disciplines
{
    public abstract class BaseCraftingMinigame
    {
        // Shared state
        protected Recipe CurrentRecipe { get; private set; }
        protected PlacementData Placement { get; private set; }
        protected float Timer { get; private set; }
        protected float MaxTime { get; private set; }
        protected float PerformanceScore { get; private set; }
        protected MinigameState State { get; private set; }

        // Shared lifecycle
        public void Start(Recipe recipe, PlacementData placement, float maxTime)
        {
            CurrentRecipe = recipe;
            Placement = placement;
            MaxTime = maxTime;
            Timer = maxTime;
            State = MinigameState.Active;
            OnStart(); // subclass hook
        }

        public void Update(float deltaTime)
        {
            if (State != MinigameState.Active) return;
            Timer -= deltaTime;
            if (Timer <= 0) { Complete(); return; }
            OnUpdate(deltaTime); // subclass hook
        }

        public MinigameResult Complete()
        {
            State = MinigameState.Completed;
            PerformanceScore = CalculatePerformance(); // subclass calculates
            var quality = RewardCalculator.GetQualityTier(PerformanceScore);
            OnComplete(); // subclass hook
            return new MinigameResult(CurrentRecipe, PerformanceScore, quality);
        }

        // Abstract hooks — each discipline implements its unique behavior
        protected abstract void OnStart();
        protected abstract void OnUpdate(float deltaTime);
        protected abstract void OnComplete();
        protected abstract float CalculatePerformance();
    }

    // Smithing only needs to implement its unique temperature/hammer mechanics
    public class SmithingMinigame : BaseCraftingMinigame
    {
        private float _temperature;
        private float _targetTemperature;
        private int _hammerHits;

        protected override void OnStart()
        {
            _targetTemperature = CalculateTargetTemp(CurrentRecipe);
            _temperature = 0f;
            _hammerHits = 0;
        }

        protected override float CalculatePerformance()
        {
            float tempAccuracy = 1f - Mathf.Abs(_temperature - _targetTemperature) / _targetTemperature;
            float hitBonus = Mathf.Min(_hammerHits / 10f, 1f);
            return Mathf.Clamp01(tempAccuracy * 0.7f + hitBonus * 0.3f);
        }

        // ... smithing-unique methods
    }
}
```

**Apply during**: Phase 4 (all crafting minigames). Each minigame becomes ~40% smaller.

---

### FIX-10: GameEngine Decomposition Map

**Problem Found In**: `game_engine.py` (10,098 lines) — classic god object

**Current State**: `GameEngine` directly manages:
- Game state machine (menu, playing, crafting, combat, paused, dead) — ~600 lines
- All input handling (keyboard, mouse, click routing) — ~1,200 lines
- Inventory/equipment UI logic — ~800 lines
- Crafting UI orchestration — ~900 lines
- Combat turn management — ~500 lines
- World rendering delegation — ~400 lines
- NPC/quest dialog — ~300 lines
- Map/waypoint interaction — ~400 lines
- Debug overlay — ~200 lines
- Save/load UI — ~300 lines
- Tooltip management — ~200 lines
- Sound effects — ~100 lines
- And 40+ helper methods scattered throughout

**C# Solution**: This decomposition was partially planned in Phase 6, but here's the explicit extraction map showing WHICH lines from `game_engine.py` go WHERE:

| GameEngine Lines (approx) | Responsibility | C# Destination | Phase |
|--------------------------|----------------|----------------|-------|
| 1-106 | Initialization, database loading | `GameManager.cs` | Phase 6 |
| 107-250 | State machine transitions | `GameStateManager.cs` | Phase 6 |
| 251-500 | Keyboard/mouse input routing | `InputManager.cs` | Phase 6 |
| 501-900 | Main update loop dispatch | `GameManager.Update()` | Phase 6 |
| 901-1700 | Inventory UI rendering/interaction | `InventoryUI.cs` | Phase 6 |
| 1701-2600 | Equipment UI rendering/interaction | `EquipmentUI.cs` | Phase 6 |
| 2601-3500 | Crafting station interaction/UI | `CraftingUI.cs` | Phase 6 |
| 3501-4000 | Minigame orchestration | `MinigameManager.cs` | Phase 6 |
| 4001-4500 | Combat HUD | `CombatUI.cs` | Phase 6 |
| 4501-5000 | NPC/quest dialog | `NPCDialogueUI.cs` | Phase 6 |
| 5001-5500 | Map/waypoint rendering | `MapUI.cs` | Phase 6 |
| 5501-6000 | Debug overlay | `DebugOverlay.cs` | Phase 6 |
| 6001-6500 | Save/load file selection | `SaveLoadUI.cs` | Phase 6 |
| 6501-7000 | Tooltip management | `TooltipRenderer.cs` | Phase 6 |
| 7001-7500 | Camera/viewport | `CameraController.cs` | Phase 6 |
| 7501-8000 | World chunk visibility | `WorldRenderer.cs` | Phase 6 |
| 8001-8500 | Class/title selection UI | `ClassSelectionUI.cs`, `StatsUI.cs` | Phase 6 |
| 8501-9000 | Encyclopedia/recipe browser | `EncyclopediaUI.cs` | Phase 6 |
| 9001-9500 | Start menu/new game | `StartMenuUI.cs` | Phase 6 |
| 9501-10098 | Audio, misc helpers | `AudioManager.cs`, various | Phase 6 |

---

### FIX-11: Stat Recalculation Caching

**Problem Found In**: `stat_tracker.py` (1,721 lines), `character.py:200-250`

**Current State**: `character.recalculate_stats()` is called:
- On every equip/unequip (`equipment_manager.py:77`)
- On every buff applied/removed (`buffs.py:45,67`)
- On every level up (`leveling.py:22`)
- On class selection (`character.py:195`)
- On title change (`character.py:215`)

Each call iterates ALL equipment slots, ALL active buffs, ALL title bonuses, ALL class bonuses. With 10 equipment slots, 6 buff types, and 6 stats, that's ~100+ calculations per call.

**C# Solution**: Dirty-flag caching with event-driven invalidation:

```csharp
public class CharacterStats
{
    private Dictionary<string, float> _cachedBonuses;
    private bool _dirty = true;

    public CharacterStats()
    {
        GameEvents.OnEquipmentChanged += (_, _) => _dirty = true;
        GameEvents.OnBuffChanged += (_, _) => _dirty = true;
        GameEvents.OnLevelUp += (_, _) => _dirty = true;
        GameEvents.OnClassSelected += (_, _) => _dirty = true;
        GameEvents.OnTitleEarned += (_, _) => _dirty = true;
    }

    public float GetTotalBonus(string stat)
    {
        if (_dirty)
        {
            RecalculateAll();
            _dirty = false;
        }
        return _cachedBonuses.GetValueOrDefault(stat, 0f);
    }

    private void RecalculateAll()
    {
        _cachedBonuses = new Dictionary<string, float>();
        // Calculate once, cache until dirty
        foreach (var stat in AllStats)
        {
            float bonus = CalculateStatBonus(stat);
            _cachedBonuses[stat] = bonus;
        }
    }
}
```

**Apply during**: Phase 3 (CharacterStats component). Requires MACRO-1 (GameEvents).

---

### FIX-12: Collision System — NavMesh-Ready Abstraction

**Problem Found In**: `collision_system.py` (599 lines)

**Current State**: Custom A* pathfinding on 2D tile grid, Bresenham line-of-sight, rectangular collision. All hardcoded to tile coordinates.

**C# Solution**: Abstraction layer that can swap between grid-based and NavMesh:

```csharp
public interface IPathfinder
{
    List<GamePosition> FindPath(GamePosition start, GamePosition end);
    bool HasLineOfSight(GamePosition from, GamePosition to);
    bool IsWalkable(GamePosition position);
}

// Phase 4: Grid-based implementation (matches Python behavior)
public class GridPathfinder : IPathfinder
{
    public List<GamePosition> FindPath(GamePosition start, GamePosition end)
    {
        // A* on tile grid, same algorithm as Python
        // Positions converted to tile coords internally
    }
}

// Future: NavMesh-based implementation (for 3D)
public class NavMeshPathfinder : IPathfinder
{
    public List<GamePosition> FindPath(GamePosition start, GamePosition end)
    {
        // Unity NavMesh.CalculatePath()
    }
}
```

**Apply during**: Phase 4 (CollisionSystem), injected via config.

---

### FIX-13: Centralized Item Creation (Item Factory)

**Problem Found In**: Items are created in at least 6 different places:
- `inventory.py:19-34` — `ItemStack.__post_init__()` creates equipment instances
- `equipment_db.py:340-390` — `create_equipment_from_definition()` builds equipment
- `save_manager.py:270-318` — `_deserialize_equipment()` reconstructs from save
- `character.py:475-536` — `_load_equipment_slot()` alternative deserialization
- `game_engine.py` — Multiple places create items for debug/drops
- `reward_calculator.py` — Creates crafted items with quality stats

**C# Solution**: Single `ItemFactory` that handles all creation paths:

```csharp
public static class ItemFactory
{
    /// <summary>Create a new item from database definition (for loot, crafting output)</summary>
    public static IGameItem CreateFromId(string itemId)
    {
        if (EquipmentDatabase.Instance.IsEquipment(itemId))
            return EquipmentDatabase.Instance.CreateEquipmentFromId(itemId);

        var mat = MaterialDatabase.Instance.GetMaterial(itemId);
        if (mat != null) return mat.ToItem();

        Debug.LogWarning($"[ItemFactory] Unknown item ID: {itemId}");
        return null;
    }

    /// <summary>Reconstruct item from save data (for load)</summary>
    public static IGameItem FromSaveData(Dictionary<string, object> data)
    {
        string category = data.GetValueOrDefault("category", "material") as string;
        return category switch
        {
            "equipment" => EquipmentItem.FromDict(data),
            "consumable" => ConsumableItem.FromDict(data),
            "placeable" => PlaceableItem.FromDict(data),
            _ => MaterialItem.FromDict(data),
        };
    }

    /// <summary>Create a crafted item with quality stats (for reward calculator)</summary>
    public static EquipmentItem CreateCrafted(string itemId, string quality, CraftedStats stats)
    {
        var baseItem = CreateFromId(itemId) as EquipmentItem;
        if (baseItem == null) return null;
        baseItem.Rarity = quality;
        baseItem.CraftedStats = stats;
        return baseItem;
    }
}
```

**Apply during**: Phase 1 (define `ItemFactory`), Phase 2 (databases use it), Phase 3 (inventory uses it), Phase 4 (save/crafting use it).

---

## Part 7: Improvement Application Schedule

| Phase | Macro Changes | Per-File Fixes |
|-------|--------------|----------------|
| **Phase 1** | MACRO-2 (enums), MACRO-6 (GamePosition) | FIX-1 (ItemStack factory), FIX-2 (Equipment serialization), FIX-6 (single rarity), FIX-13 (ItemFactory) |
| **Phase 1** | Part 4 (IGameItem hierarchy) | — |
| **Phase 2** | — | FIX-3 (single enemy parser), FIX-5 (pre-sort abilities) |
| **Phase 3** | MACRO-1 (GameEvents), MACRO-3 (UI state separation) | FIX-4 (inventory count cache), FIX-7 (cached skills), FIX-9 (computed bonuses), FIX-11 (stat caching) |
| **Phase 4** | MACRO-4 (save migration), MACRO-5 (effect dispatch), MACRO-7 (3D geometry), MACRO-8 (crafting base class) | FIX-8 (invented recipe UUID), FIX-12 (NavMesh-ready pathfinder) |
| **Phase 5** | — | — |
| **Phase 6** | MACRO-3 UI layer | FIX-10 (GameEngine decomposition map) |
| **Phase 7** | — | —  |
