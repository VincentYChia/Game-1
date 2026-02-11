# Migration Improvements: Architecture & Efficiency

**Purpose**: Improvements to make during the C# migration. Organized by scope: macro-level architecture changes (decide now) and per-file fixes (apply during porting).

**Philosophy**: This is a rewrite, not a blind port. We preserve all game mechanics exactly (formulas, constants, behavior) but improve the architecture that delivers them. Think: same engine output, cleaner engine internals.

**Rule**: Every improvement must work across the ENTIRE system, not just the file it originates from. If a change in EquipmentManager requires changes in SaveManager, Character, and CombatManager — all four must be updated together or the improvement is rejected.

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

## Part 3: Improvement Application Schedule

| Phase | Macro Changes to Implement | Per-File Fixes |
|-------|---------------------------|----------------|
| **Phase 1** | MACRO-2 (EquipmentSlot enum, HandType enum) | FIX-1 (ItemStack factory), FIX-2 (Equipment ToDict/FromDict), FIX-6 (single rarity) |
| **Phase 2** | — | FIX-3 (single enemy parser), FIX-5 (pre-sort abilities) |
| **Phase 3** | MACRO-1 (GameEvents), MACRO-3 (UI state separation) | FIX-4 (inventory count cache), FIX-7 (cached skills), FIX-9 (computed bonuses) |
| **Phase 4** | MACRO-4 (save migration pipeline), MACRO-5 (effect dispatch) | FIX-8 (invented recipe UUID) |
| **Phase 5** | — | — |
| **Phase 6** | MACRO-3 UI layer (InventoryDragHandler) | — |
| **Phase 7** | — | — |

---

## Part 4: What NOT to Improve

Some things look improvable but should be left as-is during migration:

1. **Tag system architecture** — It works well. The composable tag pattern is clean. Don't refactor.
2. **Crafting minigame formulas** — The math is correct and tuned. Port exactly.
3. **Difficulty/Reward calculators** — These are well-designed. Port 1:1.
4. **World generation algorithm** — Deterministic chunk generation works. Port exactly.
5. **JSON file schemas** — Don't change field names, structure, or organization. Moddability depends on stability.
6. **ML preprocessing** — Must match Python EXACTLY for model compatibility. Zero improvements.
7. **Database singleton pattern** — Already addressed in CONVENTIONS.md. The pattern itself is fine.
8. **Game balance numbers** — ALL constants transfer verbatim. Do not rebalance.
