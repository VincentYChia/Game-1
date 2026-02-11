# Phase 7: Polish, LLM Stub, and End-to-End Testing

**Phase**: 7 of 7
**Status**: Not Started
**Dependencies**: Phase 6 (Unity Integration -- full game must be runnable)
**Estimated C# Files**: 10-15
**Estimated C# Lines**: ~2,000-2,800
**Source Python Lines**: ~1,393 (systems/llm_item_generator.py) -- stub only, not full port
**Created**: 2026-02-10

---

## 1. Overview

### 1.1 Goal

Complete the migration with a fully functional LLM stub system, a debug notification overlay for unimplemented features, and a comprehensive end-to-end test suite that exercises every major gameplay path. This phase validates that all prior phases integrate correctly, that no regressions exist in the assembled game, and that the architecture is ready for future LLM integration without requiring structural changes.

### 1.2 Why This Phase Is Last

Phase 7 depends on the entire game being assembled and runnable:
- The LLM stub must produce items that flow through the inventory, equipment, and save systems (Phases 1-4)
- Debug notifications require the UI system (Phase 6)
- End-to-end tests exercise every system simultaneously
- The migration completion report cannot be written until all systems are verified together

### 1.3 Dependencies

**Incoming (must be complete)**:
- Phase 1: Data models (ItemGenerationRequest, GeneratedItem data structures)
- Phase 2: Database singletons (RecipeDatabase for invented recipe persistence)
- Phase 3: Entity layer (Inventory, Equipment for placeholder item integration)
- Phase 4: Game systems (Crafting pipeline, Save/Load for full cycle)
- Phase 5: ML classifiers (ClassifierManager triggers LLM generation after validation)
- Phase 6: Unity integration (UI, input, rendering, scene management)

**Outgoing**: None. Phase 7 is the final migration phase. Future work (full LLM integration, 3D graphics, multiplayer) begins after Phase 7 is complete.

### 1.4 Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| C# interface files | 1 | `IItemGenerator.cs` -- the LLM contract |
| C# stub implementation | 1 | `StubItemGenerator.cs` -- placeholder generator |
| C# data structures | 3 | `ItemGenerationRequest.cs`, `GeneratedItem.cs`, `LoadingState.cs` |
| C# notification system | 2 | `NotificationSystem.cs`, `NotificationUI.cs` |
| C# logging utility | 1 | `MigrationLogger.cs` (if not created in earlier phase) |
| E2E test scripts | 1-2 | `EndToEndTests.cs` covering all 10 scenarios |
| Migration completion report | 1 | `MIGRATION_COMPLETION_REPORT.md` |

### 1.5 Target Project Structure

```
Assets/Scripts/
  Game1.Systems/
    LLM/
      IItemGenerator.cs              # Interface contract
      StubItemGenerator.cs           # Stub implementation
      ItemGenerationRequest.cs       # Request data structure
      GeneratedItem.cs               # Result data structure
      LoadingState.cs                # Thread-safe loading indicator state
  Game1.UI/
    Notifications/
      NotificationSystem.cs          # Queue-based notification manager
      NotificationUI.cs              # On-screen notification rendering
  Game1.Core/
    MigrationLogger.cs               # Structured logging for migration validation

Assets/Tests/
  PlayMode/
    EndToEndTests.cs                 # Full game flow tests
    LLMStubTests.cs                  # Stub-specific integration tests
  EditMode/
    NotificationSystemTests.cs       # Unit tests for notification queue
    StubItemGeneratorTests.cs        # Unit tests for stub output validation
```

---

## 2. LLM Stub System

### 2.1 Source Analysis

**Source file**: `Game-1-modular/systems/llm_item_generator.py` (1,393 lines)

The Python LLM system contains several components with different migration dispositions:

| Component | Lines | Migration Action |
|-----------|-------|-----------------|
| `LLMDebugLogger` | 29-73 | Defer -- replace with `MigrationLogger` |
| `LLMConfig` | 80-98 | Port data structure only (no API key needed) |
| `LoadingState` | 104-244 | Port -- needed for UI indicator |
| `GeneratedItem` | 322-345 | Port -- result data structure |
| `FewshotPromptLoader` | 347-431 | Defer -- no prompts needed for stub |
| `AnthropicBackend` | 433-469 | Defer -- no API calls in stub |
| `MockBackend` | 471-499 | Adapt into `StubItemGenerator` |
| `LLMItemGenerator` | 502-1393 | Port interface signature only |

### 2.2 Interface Definition

```csharp
namespace Game1.Systems.LLM
{
    /// <summary>
    /// Contract for item generation from validated crafting placements.
    ///
    /// The Python implementation uses Claude API via AnthropicBackend.
    /// During migration, StubItemGenerator provides placeholder items.
    /// Future implementation will restore full LLM generation.
    /// </summary>
    public interface IItemGenerator
    {
        /// <summary>
        /// Generate a new item definition from a validated crafting placement.
        /// Returns a GeneratedItem with either valid item data or an error.
        /// Must be safe to call from a background thread.
        /// </summary>
        Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request);

        /// <summary>
        /// Whether the generator is available and ready to produce items.
        /// StubItemGenerator always returns true.
        /// A real LLM implementation would check API key availability.
        /// </summary>
        bool IsAvailable { get; }
    }
}
```

### 2.3 Data Structures to Port

#### 2.3.1 ItemGenerationRequest

```csharp
namespace Game1.Systems.LLM
{
    /// <summary>
    /// Encapsulates all information needed to generate an invented item.
    /// Built from the crafting UI state after ML classifier validation.
    /// </summary>
    [Serializable]
    public class ItemGenerationRequest
    {
        /// <summary>Crafting discipline (smithing, alchemy, refining, engineering, enchanting)</summary>
        public string Discipline { get; set; }

        /// <summary>Station tier used for crafting (1-4)</summary>
        public int StationTier { get; set; }

        /// <summary>Materials placed in the crafting grid with their quantities</summary>
        public List<MaterialPlacement> Materials { get; set; } = new();

        /// <summary>ML classifier confidence score (0.0-1.0)</summary>
        public float ClassifierConfidence { get; set; }

        /// <summary>
        /// Hash of the placement for recipe lookup and caching.
        /// Computed from sorted material IDs + quantities + positions.
        /// </summary>
        public string PlacementHash { get; set; }
    }

    [Serializable]
    public class MaterialPlacement
    {
        public string MaterialId { get; set; }
        public int Quantity { get; set; }
        public string SlotType { get; set; }  // For engineering: FRAME, POWER, etc.
        public int SlotIndex { get; set; }
    }
}
```

#### 2.3.2 GeneratedItem

Ported from Python `GeneratedItem` dataclass (lines 322-345):

```csharp
namespace Game1.Systems.LLM
{
    /// <summary>
    /// Result of an item generation attempt (either LLM or stub).
    /// Contains the full item definition if successful, or an error message.
    /// </summary>
    [Serializable]
    public class GeneratedItem
    {
        public bool Success { get; set; }
        public Dictionary<string, object> ItemData { get; set; }
        public string ItemId { get; set; }
        public string ItemName { get; set; }
        public string Discipline { get; set; } = "";
        public string Error { get; set; }
        public bool FromCache { get; set; }

        // Recipe data for save system persistence
        public List<Dictionary<string, object>> RecipeInputs { get; set; }
        public int StationTier { get; set; } = 1;
        public string Narrative { get; set; } = "";

        /// <summary>Whether this item was generated by a stub (not a real LLM)</summary>
        public bool IsStub { get; set; } = false;

        public bool IsValid => Success && ItemData != null;
    }
}
```

#### 2.3.3 LoadingState

Ported from Python `LoadingState` class (lines 104-244). This is needed by the UI to show a progress indicator while item generation is in progress.

```csharp
namespace Game1.Systems.LLM
{
    /// <summary>
    /// Thread-safe loading state for UI progress indicators.
    /// Supports both small indicator and full-screen overlay modes.
    /// Includes smooth animation for indeterminate progress.
    /// </summary>
    public class LoadingState
    {
        // Animation constants (exact match to Python)
        public const float SmoothProgressDuration = 15.0f;
        public const float SmoothProgressMax = 0.90f;
        public const float CompletionDelay = 0.5f;

        private readonly object _lock = new object();
        private bool _isLoading;
        private string _message = "";
        private float _progress;
        private bool _overlayMode;
        private string _subtitle = "";
        private float _startTime;
        private bool _completeState;
        private float _completeTime;
        private bool _useSmoothAnimation = true;

        public bool IsLoading { get { /* thread-safe read */ } }
        public string Message { get { /* "Item Generation Complete" if complete */ } }
        public string Subtitle { get { /* empty if complete */ } }
        public float Progress { get { /* 1.0 if complete */ } }
        public bool OverlayMode { get { /* thread-safe read */ } }
        public bool IsComplete { get { /* thread-safe read */ } }

        /// <summary>
        /// Get animated progress for display.
        /// Ease-out cubic from 0% to 90% over SmoothProgressDuration seconds.
        /// Formula: eased = 1 - (1 - t)^3, scaled by SmoothProgressMax.
        /// </summary>
        public float GetAnimatedProgress() { /* match Python exactly */ }

        public void Start(string message = "Loading...",
                          bool overlay = false, string subtitle = "") { }
        public void Update(string message = null,
                           float? progress = null, string subtitle = null) { }
        public void Finish() { /* transition to completion state with delay */ }
    }
}
```

### 2.4 Stub Implementation

```csharp
namespace Game1.Systems.LLM
{
    /// <summary>
    /// Placeholder item generator that returns synthetic items without calling any API.
    ///
    /// Behavior:
    /// - Always available (IsAvailable = true)
    /// - Simulates 500ms async delay to mimic network latency
    /// - Generates deterministic placeholder items based on input materials
    /// - Marks all items with IsStub = true
    /// - Logs every invocation via MigrationLogger
    /// - Triggers a debug notification on every call
    /// </summary>
    public class StubItemGenerator : IItemGenerator
    {
        private readonly LoadingState _loadingState;
        private readonly NotificationSystem _notifications;

        public bool IsAvailable => true;

        public async Task<GeneratedItem> GenerateItemAsync(ItemGenerationRequest request)
        {
            // 1. Log the request
            MigrationLogger.Log("LLM_STUB",
                $"Stub generation invoked for {request.Discipline} " +
                $"with {request.Materials.Count} materials");

            // 2. Show debug notification
            _notifications.Show(
                $"[STUB] Generating {request.Discipline} item...",
                NotificationType.Debug,
                duration: 3.0f);

            // 3. Update loading state
            _loadingState.Start(
                message: "Generating Item (STUB)...",
                overlay: true,
                subtitle: "Using placeholder generator");

            // 4. Simulate async delay (500ms)
            await Task.Delay(500);

            // 5. Generate placeholder item
            var item = GeneratePlaceholderItem(request);

            // 6. Finish loading state
            _loadingState.Finish();

            // 7. Show completion notification
            _notifications.Show(
                $"[STUB] Created: {item.ItemName}",
                NotificationType.Debug,
                duration: 5.0f);

            return item;
        }

        private GeneratedItem GeneratePlaceholderItem(ItemGenerationRequest request)
        {
            // Compute deterministic item ID from placement hash
            string itemId = $"invented_{request.Discipline}_{request.PlacementHash}";

            // Compute stats based on material tiers
            int totalTierPoints = 0;
            string primaryMaterial = "unknown";
            foreach (var mat in request.Materials)
            {
                var matDef = MaterialDatabase.Instance.GetMaterial(mat.MaterialId);
                if (matDef != null)
                {
                    totalTierPoints += matDef.Tier * mat.Quantity;
                    if (primaryMaterial == "unknown")
                        primaryMaterial = matDef.Name;
                }
            }

            // Determine quality tier from total points (matches DifficultyCalculator)
            string qualityPrefix = totalTierPoints switch
            {
                <= 4 => "Common",
                <= 10 => "Uncommon",
                <= 20 => "Rare",
                <= 40 => "Epic",
                _ => "Legendary"
            };

            string itemName = $"[STUB] {qualityPrefix} {request.Discipline} Item";

            // Build item data matching the game's expected JSON schema
            var itemData = new Dictionary<string, object>
            {
                ["itemId"] = itemId,
                ["name"] = itemName,
                ["description"] = $"Placeholder item created from {primaryMaterial}. " +
                                  "This item was generated by the migration stub.",
                ["category"] = GetCategoryForDiscipline(request.Discipline),
                ["tier"] = Mathf.Clamp(totalTierPoints / 4, 1, 4),
                ["rarity"] = qualityPrefix.ToLower(),
                ["isStub"] = true
            };

            // Add discipline-specific stats
            AddDisciplineStats(itemData, request.Discipline, totalTierPoints);

            return new GeneratedItem
            {
                Success = true,
                ItemData = itemData,
                ItemId = itemId,
                ItemName = itemName,
                Discipline = request.Discipline,
                IsStub = true,
                StationTier = request.StationTier,
                RecipeInputs = request.Materials
                    .Select(m => new Dictionary<string, object>
                    {
                        ["materialId"] = m.MaterialId,
                        ["qty"] = m.Quantity
                    }).ToList(),
                Narrative = "This is a placeholder item generated by the migration stub. " +
                            "Full LLM generation will be implemented in a future update."
            };
        }

        private string GetCategoryForDiscipline(string discipline)
        {
            return discipline switch
            {
                "smithing" => "equipment",
                "alchemy" => "consumable",
                "refining" => "material",
                "engineering" => "device",
                "enchanting" => "enchantment",
                _ => "misc"
            };
        }

        private void AddDisciplineStats(Dictionary<string, object> itemData,
                                         string discipline, int tierPoints)
        {
            // Scale placeholder stats by material tier points
            float statMultiplier = 1.0f + (tierPoints * 0.1f);

            switch (discipline)
            {
                case "smithing":
                    itemData["damage"] = Mathf.RoundToInt(10 * statMultiplier);
                    itemData["durability"] = 100;
                    itemData["weight"] = 5.0f;
                    break;
                case "alchemy":
                    itemData["potency"] = Mathf.RoundToInt(50 * statMultiplier);
                    itemData["duration"] = 30.0f;
                    break;
                case "refining":
                    itemData["outputQty"] = Mathf.Max(1, tierPoints / 2);
                    break;
                case "engineering":
                    itemData["attackDamage"] = Mathf.RoundToInt(8 * statMultiplier);
                    itemData["attackSpeed"] = 1.0f;
                    itemData["range"] = 5.0f;
                    break;
                case "enchanting":
                    itemData["enchantmentPower"] = Mathf.RoundToInt(25 * statMultiplier);
                    break;
            }
        }
    }
}
```

### 2.5 What NOT to Port (Deferred to Future)

The following components from `llm_item_generator.py` are explicitly deferred:

| Component | Reason for Deferral |
|-----------|-------------------|
| `AnthropicBackend` (lines 433-469) | Requires Claude API key and `anthropic` Python package equivalent. Future phase will implement C# HTTP client for Anthropic API. |
| `FewshotPromptLoader` (lines 347-431) | Loads system prompts and few-shot examples from disk. Not needed until real LLM calls are implemented. |
| Response parsing logic (lines 600-750) | Parses Claude's JSON response into item definitions. Tightly coupled to prompt format. |
| Cache management (lines 800-900) | Invented recipe cache using placement hashes. The `RecipeDatabase` already handles invented recipe persistence; the LLM-level cache is an optimization. |
| `LLMDebugLogger` (lines 29-73) | Replaced by the unified `MigrationLogger` system. |

### 2.6 Integration with Crafting Pipeline

The stub plugs into the existing crafting flow at the same point as the Python LLM system:

```
Player places materials in crafting grid
  -> ClassifierManager.Validate(discipline, uiState)     [Phase 5]
  -> If classifier says VALID and no existing recipe match:
       -> IItemGenerator.GenerateItemAsync(request)       [Phase 7 -- THIS]
       -> GeneratedItem added to Inventory                [Phase 3]
       -> Invented recipe saved to RecipeDatabase         [Phase 2]
       -> Save state updated                              [Phase 4]
```

The `InteractiveCrafting` system (ported in Phase 4) should accept an `IItemGenerator` via constructor injection, making it trivial to swap the stub for a real implementation later.

---

## 3. Debug Notification System

### 3.1 Purpose

The notification system serves two roles:
1. **During migration**: Display debug notifications whenever a stub or placeholder is invoked, making it visible to testers which features are not yet fully implemented.
2. **Post-migration**: Display gameplay notifications (item acquired, level up, quest complete) using the same infrastructure.

### 3.2 NotificationSystem.cs

```csharp
namespace Game1.UI.Notifications
{
    public enum NotificationType
    {
        Info,       // General information (white)
        Success,    // Positive feedback (green)
        Warning,    // Caution (yellow)
        Error,      // Failure (red)
        Debug       // Stub/migration markers (cyan, debug builds only)
    }

    public class Notification
    {
        public string Message { get; set; }
        public NotificationType Type { get; set; }
        public float Duration { get; set; }
        public float TimeRemaining { get; set; }
        public float Alpha { get; set; } = 1.0f;  // For fade-out animation
    }

    /// <summary>
    /// Queue-based notification manager.
    /// Displays notifications in a vertical stack on the right side of the screen.
    /// Debug notifications are only shown in debug/development builds.
    /// </summary>
    public class NotificationSystem : MonoBehaviour
    {
        private const int MaxVisibleNotifications = 5;
        private const float FadeOutDuration = 0.5f;
        private const float DefaultDuration = 3.0f;

        private readonly Queue<Notification> _pendingQueue = new();
        private readonly List<Notification> _activeNotifications = new();

        private static NotificationSystem _instance;
        public static NotificationSystem Instance => _instance;

        public void Show(string message, NotificationType type = NotificationType.Info,
                         float duration = DefaultDuration)
        {
            // Filter Debug notifications in release builds
            #if !DEBUG && !UNITY_EDITOR
            if (type == NotificationType.Debug)
                return;
            #endif

            var notification = new Notification
            {
                Message = message,
                Type = type,
                Duration = duration,
                TimeRemaining = duration
            };

            if (_activeNotifications.Count < MaxVisibleNotifications)
                _activeNotifications.Add(notification);
            else
                _pendingQueue.Enqueue(notification);
        }

        private void Update()
        {
            // Update active notifications
            for (int i = _activeNotifications.Count - 1; i >= 0; i--)
            {
                var n = _activeNotifications[i];
                n.TimeRemaining -= Time.deltaTime;

                // Fade out in final 0.5 seconds
                if (n.TimeRemaining <= FadeOutDuration)
                    n.Alpha = Mathf.Max(0f, n.TimeRemaining / FadeOutDuration);

                // Remove expired
                if (n.TimeRemaining <= 0f)
                {
                    _activeNotifications.RemoveAt(i);

                    // Promote from pending queue
                    if (_pendingQueue.Count > 0)
                        _activeNotifications.Add(_pendingQueue.Dequeue());
                }
            }
        }

        /// <summary>
        /// Color mapping for notification types.
        /// Matches the Python game's UI color conventions.
        /// </summary>
        public static Color GetColor(NotificationType type)
        {
            return type switch
            {
                NotificationType.Info => Color.white,
                NotificationType.Success => new Color(0.2f, 0.8f, 0.2f),   // Green
                NotificationType.Warning => new Color(1.0f, 0.8f, 0.0f),   // Yellow
                NotificationType.Error => new Color(1.0f, 0.3f, 0.3f),     // Red
                NotificationType.Debug => new Color(0.0f, 0.8f, 0.8f),     // Cyan
                _ => Color.white
            };
        }
    }
}
```

### 3.3 Notification Triggers

The following systems should emit debug notifications when stubs or placeholders are used:

| System | Trigger | Message Format |
|--------|---------|----------------|
| LLM Item Generator | Stub invoked | `[STUB] Generating {discipline} item...` |
| LLM Item Generator | Stub complete | `[STUB] Created: {itemName}` |
| Block/Parry | Player attempts block | `[NOT IMPL] Block/Parry not yet implemented` |
| Summon Mechanics | Summon skill used | `[NOT IMPL] Summon mechanics not yet implemented` |
| Spell Combos | Combo attempted | `[NOT IMPL] Spell combo system not yet implemented` |
| Skill Evolution | Evolution trigger | `[NOT IMPL] Skill evolution chains not yet implemented` |

---

## 4. End-to-End Testing

### 4.1 Overview

End-to-end tests verify that all migrated systems work together in complete gameplay scenarios. Each test starts from a known initial state, performs a sequence of player actions, and asserts expected outcomes.

These tests run in Unity Play Mode and require a fully assembled game scene.

### 4.2 Test Scenarios

#### Scenario 1: New Game to Spawn

**Steps**:
1. Start new game
2. Enter character name
3. Select class (e.g., Warrior)
4. Confirm character creation

**Assertions**:
- Character spawns at world origin (0, 0)
- Character has correct class tag bonuses applied
- Starting stats are all 0 (level 1)
- Inventory is empty (30 slots available)
- Equipment slots are all empty (8 slots)
- HP is at maximum (base HP = VIT formula at 0)
- Mana is at maximum (base mana = INT formula at 0)
- World chunks loaded around spawn point

#### Scenario 2: Resource Gathering

**Steps**:
1. Load test save with character near a resource node
2. Move character to adjacent tile with a tree resource
3. Equip an axe tool
4. Interact with resource node (harvest action)

**Assertions**:
- Resource node HP decreases by tool damage amount
- When resource HP reaches 0, materials added to inventory
- Material quantities match resource yield definition
- Tool durability decreases by 1
- STR bonus applied to mining/harvest damage correctly
- Resource begins respawn timer after depletion

#### Scenario 3: Crafting Flow

**Steps**:
1. Load test save with smithing station adjacent and iron ingots in inventory
2. Open crafting station (interact)
3. Select smithing discipline
4. Place materials in grid matching a known recipe (e.g., Iron Sword)
5. Start minigame
6. Complete minigame with known performance score

**Assertions**:
- Difficulty calculator produces correct difficulty tier for input materials
- Minigame parameters match difficulty settings
- Performance score maps to correct quality tier via RewardCalculator
- Crafted item added to inventory with correct quality
- Input materials consumed from inventory
- Crafting EXP granted to player

#### Scenario 4: Combat Flow

**Steps**:
1. Load test save with character equipped with a weapon
2. Spawn test enemy at known position (via debug command)
3. Move within attack range
4. Perform attack

**Assertions**:
- Damage calculation matches DamageCalculator output for the given inputs
- STR multiplier applied correctly (1.0 + STR * 0.05)
- Weapon damage used as base
- Enemy HP reduced by final damage amount
- If enemy dies: EXP awarded matching tier formula
- If enemy dies: loot dropped according to loot table
- Durability of weapon decreased by 1

#### Scenario 5: Level Up and Stat Allocation

**Steps**:
1. Load test save with character at EXP threshold minus 1
2. Grant 1 EXP (trigger level up)
3. Allocate 1 stat point to STR
4. Verify stat bonus changes

**Assertions**:
- Level increments by 1
- Stat point available for allocation
- After allocating STR: melee damage bonus increases by 5%
- After allocating STR: inventory capacity increases by 10 slots
- EXP counter resets for next level (new threshold = floor(200 * 1.75^level))
- Skill unlocks checked after level up

#### Scenario 6: Skill Usage in Combat

**Steps**:
1. Load test save with character that has learned a fire skill (e.g., Fireball)
2. Spawn test enemy
3. Activate Fireball skill targeting the enemy

**Assertions**:
- Mana reduced by skill mana cost
- Skill goes on cooldown for correct duration
- EffectExecutor processes fire + circle + burn tags
- TargetFinder finds targets in circle radius
- Base damage applied with fire damage type
- Burn status effect applied to target (DoT ticking)
- Burn deals damage_per_second for specified duration

#### Scenario 7: Save and Load Verification

**Steps**:
1. Load test save with specific known state
2. Modify state: move character, add items to inventory, damage equipment
3. Save game to new file
4. Load the saved file
5. Compare all state

**Assertions**:
- Character position preserved exactly
- All 6 stats preserved
- Level, EXP preserved
- Current HP, current mana preserved
- All 30 inventory slots preserved (item IDs, quantities, durability)
- All 8 equipment slots preserved (including enchantments)
- World seed preserved
- Crafting stations preserved (positions, types, tiers)
- Placed entities preserved
- Game time preserved
- Quest progress preserved
- Title state preserved

#### Scenario 8: Turret and Trap Placement

**Steps**:
1. Load test save with turret item in inventory
2. Place turret at valid world position
3. Spawn test enemy within turret range
4. Wait for turret attack cooldown

**Assertions**:
- Turret placed in world at correct position
- Turret appears in placed entities list
- TurretSystem finds nearest enemy within range
- Turret attacks via EffectExecutor with its configured tags
- Enemy takes damage from turret attack
- Turret cooldown resets after attack
- Turret lifetime decrements each frame

#### Scenario 9: Dungeon Clearing

**Steps**:
1. Load test save with character near a dungeon entrance
2. Enter dungeon
3. Kill all wave 1 enemies (using debug one-hit-kill)
4. Kill all wave 2 enemies
5. Kill all wave 3 enemies

**Assertions**:
- Dungeon generates correct number of enemies per wave
- Enemy tiers match dungeon rarity distribution
- EXP from dungeon enemies is 2x normal
- No material drops from dungeon enemies
- Loot chest spawns after final wave cleared
- Loot chest contains appropriate rewards
- Player can exit dungeon after clearing

#### Scenario 10: Fast Travel via Waypoint

**Steps**:
1. Load test save with two discovered waypoints
2. Open map
3. Select destination waypoint
4. Confirm fast travel

**Assertions**:
- Character position updated to destination waypoint coordinates
- Chunks loaded around new position
- Previous area chunks unloaded (if outside view distance)
- No enemies spawn during travel (instant)
- Game time does not advance during fast travel

### 4.3 Test Infrastructure

```csharp
[TestFixture]
public class EndToEndTests
{
    private GameManager _gameManager;

    [OneTimeSetUp]
    public void SetUp()
    {
        // Load test scene with all systems initialized
        SceneManager.LoadScene("TestScene", LoadSceneMode.Single);
        _gameManager = Object.FindObjectOfType<GameManager>();
    }

    [UnityTest]
    public IEnumerator Scenario1_NewGameToSpawn()
    {
        // Create new game
        _gameManager.StartNewGame("TestCharacter", "warrior");
        yield return null;  // Wait one frame for initialization

        // Verify spawn state
        var character = _gameManager.Character;
        Assert.AreEqual(0f, character.Position.X, 0.1f);
        Assert.AreEqual(0f, character.Position.Y, 0.1f);
        Assert.AreEqual(1, character.Level);
        Assert.AreEqual(0, character.Inventory.UsedSlots);
        Assert.AreEqual(30, character.Inventory.TotalSlots);
    }

    [UnityTest]
    public IEnumerator Scenario7_SaveLoadRoundtrip()
    {
        // Load known state
        _gameManager.LoadGame("test_save.json");
        yield return null;

        // Record state
        var prePos = _gameManager.Character.Position;
        var preLevel = _gameManager.Character.Level;
        var preItems = _gameManager.Character.Inventory.GetAllItems();

        // Modify state
        _gameManager.Character.Position = new Position(10, 20);
        _gameManager.Character.Inventory.AddItem("iron_ingot", 5);

        // Save and reload
        _gameManager.SaveGame("test_roundtrip.json");
        _gameManager.LoadGame("test_roundtrip.json");
        yield return null;

        // Verify modified state preserved
        Assert.AreEqual(10f, _gameManager.Character.Position.X, 0.01f);
        Assert.AreEqual(20f, _gameManager.Character.Position.Y, 0.01f);
        // ... verify all fields
    }
}
```

### 4.4 Debug Key Verification

All debug keys from the Python version must remain functional:

| Key | Python Behavior | C# Verification |
|-----|----------------|-----------------|
| **F1** | Toggle debug mode (infinite resources, info overlays) | Assert debug flag toggles, resource consumption bypassed |
| **F2** | Auto-learn all skills | Assert SkillManager contains all skills from SkillDatabase |
| **F3** | Grant all titles | Assert TitleSystem has all titles from TitleDatabase |
| **F4** | Max level + stats | Assert level = 30, all 6 stats at maximum |
| **F7** | Infinite durability | Assert equipment durability does not decrease on use |

---

## 5. Migration Completion Report Template

Upon completing Phase 7, produce a `MIGRATION_COMPLETION_REPORT.md` with the following structure:

### 5.1 Phase Completion Summary

| Phase | Name | Status | Files Ported | Tests Passing |
|-------|------|--------|-------------|---------------|
| 1 | Foundation | Complete | X / X | Y / Y |
| 2 | Data Layer | Complete | X / X | Y / Y |
| 3 | Entity Layer | Complete | X / X | Y / Y |
| 4 | Game Systems | Complete | X / X | Y / Y |
| 5 | ML Classifiers | Complete | X / X | Y / Y |
| 6 | Unity Integration | Complete | X / X | Y / Y |
| 7 | Polish and LLM Stub | Complete | X / X | Y / Y |

### 5.2 Test Coverage Summary

| Category | Tests | Passing | Coverage |
|----------|-------|---------|----------|
| Unit Tests (EditMode) | X | X | X% |
| Integration Tests (PlayMode) | X | X | X% |
| Golden File Tests (ML) | X | X | X% |
| End-to-End Scenarios | 10 | X / 10 | -- |
| Comparison Tests (Python vs C#) | X | X | -- |

### 5.3 Known Issues Remaining

Categorized list of any issues discovered during E2E testing that are not blockers:
- P2 issues (cosmetic, minor behavior differences)
- P3 issues (future improvements, not regressions)

### 5.4 Performance Benchmarks

| Metric | Target | Measured |
|--------|--------|----------|
| Frame rate (idle) | > 60 FPS | X FPS |
| Frame rate (combat, 10 enemies) | > 30 FPS | X FPS |
| ML inference latency | < 100ms | X ms |
| Save file write time | < 1s | X ms |
| Save file load time | < 2s | X ms |
| Initial load time | < 10s | X s |
| Memory usage (steady state) | < 500 MB | X MB |

### 5.5 Architecture Readiness

Checklist for future development:

- [ ] LLM interface ready for real implementation (swap `StubItemGenerator` for `AnthropicItemGenerator`)
- [ ] 3D rendering: all game logic is decoupled from rendering via interfaces
- [ ] Multiplayer: game state is serializable and can be transmitted
- [ ] Modding: JSON content loaded from StreamingAssets, editable by players
- [ ] Platform: no platform-specific code outside of Unity abstraction layer

### 5.6 Next Steps (Post-Migration)

1. **Full LLM Integration**: Implement `AnthropicItemGenerator` with C# HTTP client for Claude API
2. **3D Visual Upgrade**: Replace 2D sprites with 3D models, keep all game logic unchanged
3. **Audio System**: Implement sound effects and music using placeholder audio manager
4. **Content Expansion**: New items, enemies, skills, and recipes (JSON-only changes)
5. **Performance Optimization**: Profile and optimize hot paths identified during benchmarking

---

## 6. Quality Gate

All of the following must pass before Phase 7 and the overall migration are considered complete:

- [ ] **LLM stub callable**: `StubItemGenerator.GenerateItemAsync()` returns a valid `GeneratedItem` with `Success = true`
- [ ] **Stub items functional**: Placeholder items can be added to inventory, equipped (if appropriate type), and appear in save files
- [ ] **Debug notifications display**: `NotificationSystem.Show()` renders notifications on screen with correct colors and fade-out
- [ ] **Debug notifications filtered**: `NotificationType.Debug` notifications do NOT appear in release builds
- [ ] **Notification queue works**: When more than 5 notifications are active, excess notifications queue and display as earlier ones expire
- [ ] **E2E Scenario 1 passes**: New Game -> Character Creation -> Spawn
- [ ] **E2E Scenario 2 passes**: Move -> Find Resource -> Harvest
- [ ] **E2E Scenario 3 passes**: Open Crafting Station -> Place Materials -> Run Minigame -> Receive Item
- [ ] **E2E Scenario 4 passes**: Equip Item -> Find Enemy -> Combat -> Kill -> Loot
- [ ] **E2E Scenario 5 passes**: Level Up -> Allocate Stats -> Learn Skill
- [ ] **E2E Scenario 6 passes**: Use Skill in Combat -> Apply Status Effect
- [ ] **E2E Scenario 7 passes**: Save Game -> Load Game -> Verify State
- [ ] **E2E Scenario 8 passes**: Place Turret/Trap -> Watch it attack enemies
- [ ] **E2E Scenario 9 passes**: Enter Dungeon -> Clear Waves -> Get Reward
- [ ] **E2E Scenario 10 passes**: Fast Travel via Waypoint
- [ ] **Full save/load cycle**: Save in C#, load in C#, all state matches
- [ ] **Zero runtime errors**: 30 minutes of continuous play without exceptions or crashes
- [ ] **All debug keys functional**: F1 (debug mode), F2 (learn skills), F3 (grant titles), F4 (max level), F7 (infinite durability) all work correctly
- [ ] **Migration completion report**: Document produced with all sections filled

---

## 7. Risks and Mitigations

### 7.1 Stub Item Schema Mismatch

**Risk**: Placeholder items generated by the stub may not match the exact JSON schema expected by the inventory, equipment, and save systems, causing runtime errors when stub items are used.

**Mitigation**: Write unit tests that create stub items and pass them through every system that touches items: `Inventory.AddItem()`, `EquipmentManager.Equip()`, `SaveManager.SerializeCharacter()`, `SaveManager.DeserializeCharacter()`. Verify no exceptions and no data loss at each step.

### 7.2 E2E Test Fragility

**Risk**: End-to-end tests are inherently fragile. They depend on scene setup, timing, and the interaction of many systems. Small changes in any phase can break E2E tests.

**Mitigation**: Use deterministic seeds for world generation. Use test-specific save files with known states. Avoid timing-dependent assertions (use yield-based waits, not fixed delays). Isolate each scenario as much as possible.

### 7.3 Debug Notification Performance

**Risk**: If many systems emit debug notifications rapidly, the notification queue could grow unbounded, causing memory pressure or UI clutter.

**Mitigation**: Cap the pending queue at 20 entries. Drop oldest pending notifications when the cap is reached. Rate-limit identical notifications (same message within 1 second = skip).

### 7.4 LoadingState Thread Safety

**Risk**: The `LoadingState` class is accessed from both the main thread (UI reads) and background threads (generation writes). Incorrect locking could cause deadlocks or torn reads.

**Mitigation**: Port the Python locking pattern exactly (simple `lock` around every property access). The Python implementation uses `threading.Lock()` which maps directly to C# `lock(object)`. Keep the critical sections small -- no I/O or allocations inside locks.

### 7.5 Integration Gaps Between Phases

**Risk**: Each prior phase was tested in isolation. When all phases run together for the first time in Phase 7, unexpected interactions may surface (e.g., crafting system assumes a database query returns non-null, but the test data is incomplete).

**Mitigation**: The E2E test suite is specifically designed to catch integration gaps. Run all 10 scenarios with a complete game data set (all JSON files loaded). Log every system interaction during E2E tests via `MigrationLogger` for post-failure analysis.

---

## 8. Estimated Effort

| Task | Estimated Hours |
|------|----------------|
| IItemGenerator interface + data structures | 3 |
| StubItemGenerator implementation | 4 |
| LoadingState port (thread-safe) | 2 |
| NotificationSystem + NotificationUI | 5 |
| Notification integration across systems | 3 |
| E2E test infrastructure (scene, fixtures) | 4 |
| E2E Scenarios 1-5 | 8 |
| E2E Scenarios 6-10 | 8 |
| Debug key verification tests | 2 |
| Integration debugging and fixes | 8 |
| Performance benchmarking | 3 |
| Migration completion report | 3 |
| **Total** | **~53 hours** |

---

## 9. Success Criteria

Phase 7 and the overall migration are complete when:

1. `IItemGenerator` interface is defined and `StubItemGenerator` implements it correctly
2. Stub-generated items flow through inventory, equipment, and save/load without errors
3. Debug notifications display on screen for all stub invocations and unimplemented features
4. All 10 end-to-end scenarios pass consistently (no flaky failures)
5. Full save/load round-trip preserves 100% of game state
6. 30 minutes of continuous gameplay produces zero runtime errors
7. All debug keys (F1, F2, F3, F4, F7) function identically to the Python version
8. Performance meets minimum targets (>30 FPS in combat, <100ms ML inference)
9. Migration completion report is produced with all sections populated
10. Architecture is verified ready for future LLM integration (interface swap, no structural changes needed)

### 3D Readiness Verification

As part of E2E testing, verify these 3D readiness checks:
- [ ] All entity positions serialize as `GamePosition` with X, Y, Z fields (Y=0 for flat world)
- [ ] `TargetFinder.GetDistance()` is used for all combat range checks (no inline distance math)
- [ ] `WorldSystem.TileToWorld()` is the only path from tile coords to world space
- [ ] `IPathfinder` interface is used for all pathfinding (not direct A* calls)
- [ ] Camera supports both orthographic and perspective mode toggle via config
- [ ] Switching `TargetFinder.Mode` from `Horizontal` to `Full3D` doesn't crash any system

**This is the final phase. Upon completion, the Python-to-Unity migration is done. The architecture is 3D-ready: upgrading to full 3D visuals is a content and rendering change, not a logic rewrite.**
