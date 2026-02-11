# Phase 6: Unity Integration -- GameEngine Decomposition, Rendering Rebuild, Input, and UI

**Phase**: 6 of N
**Status**: Not Started
**Dependencies**: Phase 4 (Game Systems -- all logic ported), Phase 5 (ML Classifiers -- ONNX models loaded via Sentis)
**Estimated C# Files**: 40-50
**Estimated C# Lines**: ~18,000-22,000
**Source Python Lines**: 10,098 (game_engine.py) + 6,936 (renderer.py) + 2,968 (supporting files) = ~20,002
**Created**: 2026-02-10

---

## 1. Overview

### 1.1 Goal

Decompose the 10,098-line monolithic `game_engine.py` and the 6,936-line monolithic `renderer.py` into approximately 40+ focused Unity MonoBehaviours, UI components, and ScriptableObjects. This phase replaces Pygame's event loop, rendering surface, and input polling with Unity's component architecture, UI Toolkit/uGUI, Tilemap system, and Input System.

This is NOT a direct line-by-line port. The Python code merges initialization, state management, input handling, game logic orchestration, and UI layout into two massive files. Unity's component model demands decomposition into single-responsibility components that communicate through events, references, and the Unity lifecycle.

### 1.2 Why This Phase Depends on 4 and 5

Every Unity component in this phase calls into the pure C# systems ported in Phases 1-4:
- GameManager bootstraps all database singletons (Phase 2) and system managers (Phase 4)
- CraftingUI calls `InteractiveCrafting`, `DifficultyCalculator`, `RewardCalculator` (Phase 4)
- MinigameUIs call smithing/alchemy/refining/engineering/enchanting logic (Phase 4)
- CraftingUI triggers `ClassifierManager.Validate()` for invented recipes (Phase 5)
- CombatManager, WorldSystem, SaveManager are all Phase 4 deliverables consumed here
- InventoryUI, EquipmentUI, SkillBarUI read from Character components (Phase 3)

### 1.3 Non-Goals

- **3D graphics**: This phase produces 2D sprite-based visuals matching the Pygame version. The architecture supports future 3D upgrades, but visual fidelity improvements are a separate effort.
- **New features**: No gameplay additions. The Unity version must be functionally identical to the Python version.
- **Mobile input**: Desktop keyboard+mouse only. Touch input is a future phase.

### 1.4 Deliverables

| Deliverable | Count | Description |
|-------------|-------|-------------|
| Core MonoBehaviours | 5 | GameManager, GameStateManager, InputManager, CameraController, AudioManager |
| UI Components | 16 | Inventory, Equipment, Crafting, 5 Minigames, SkillBar, StatusBar, Map, etc. |
| World Rendering | 8 | Tilemap, resources, entities, enemies, player, particles, effects |
| ScriptableObjects | 4 | GameConfig, CraftingConfig, CombatConfig, RenderingConfig |
| Prefabs | 8+ | Player, Enemy, ResourceNode, CraftingStation, Turret, Trap, Bomb, DamageNumber |
| Scene files | 2 | MainScene, MainMenuScene |
| Input Action Asset | 1 | Unity Input System action map |
| Sprite Atlases | 5+ | Organized by category (materials, equipment, UI, world, effects) |

### 1.5 Target Project Structure

```
Assets/
  Scenes/
    MainMenu.unity
    GameWorld.unity
  Scripts/Game1.Unity/
    Core/
      GameManager.cs                  # Bootstrap, initialization order
      GameStateManager.cs             # State machine: Menu, Playing, Crafting, Combat, etc.
      InputManager.cs                 # Unity Input System routing
      CameraController.cs            # Follow player, zoom, bounds
      AudioManager.cs                # Sound effect playback (placeholder)
    UI/
      InventoryUI.cs                 # 30-slot grid, drag-and-drop
      EquipmentUI.cs                 # 10 equipment slots
      CraftingUI.cs                  # Station interaction, recipe selection
      MinigameUI.cs                  # Abstract base for minigame UIs
      SmithingMinigameUI.cs          # Temperature bar, hammer animation
      AlchemyMinigameUI.cs           # Reaction chain visualization
      RefiningMinigameUI.cs          # Cylinder rotation display
      EngineeringMinigameUI.cs       # Grid puzzle / logic switch display
      EnchantingMinigameUI.cs        # Spinning wheel animation
      SkillBarUI.cs                  # 5 hotbar slots, cooldown overlay
      StatusBarUI.cs                 # HP/Mana/EXP bars
      MapUI.cs                       # World map, waypoints, fog of war
      EncyclopediaUI.cs              # Recipe browser, invented recipes
      NotificationUI.cs              # Toast notifications, debug messages
      DebugOverlay.cs                # F1-F7 debug toggles, stat display
      StartMenuUI.cs                 # Main menu (New/Load/Temp world)
      ClassSelectionUI.cs            # Class picker at game start
      StatsUI.cs                     # Character stats allocation
      NPCDialogueUI.cs              # NPC interaction, quest UI
      TooltipRenderer.cs             # Deferred tooltip rendering
      DragDropManager.cs             # Shared drag-and-drop state
      ChestUI.cs                     # Dungeon/spawn/death chest display
    World/
      WorldRenderer.cs               # Tilemap rendering, chunk visibility
      ResourceRenderer.cs            # Resource node sprites, HP bars
      EntityRenderer.cs              # Placed entities (turrets, traps, stations)
      EnemyRenderer.cs               # Enemy sprites, health bars, AI state indicators
      PlayerRenderer.cs              # Player sprite, facing direction, animation
      DamageNumberRenderer.cs        # Floating damage text with fade
      AttackEffectRenderer.cs        # Attack lines, AoE circles, beam visuals
      ParticleEffects.cs             # Crafting particles (replaces minigame_effects.py)
      DayNightOverlay.cs             # Time-of-day lighting overlay
    Config/
      GameConfig.asset               # ScriptableObject: screen, tile, chunk settings
      CraftingConfig.asset           # ScriptableObject: minigame visual settings
      CombatConfig.asset             # ScriptableObject: visual feedback settings
      RenderingConfig.asset          # ScriptableObject: colors, sizes, atlas refs
  Prefabs/
    Player.prefab
    Enemy.prefab
    ResourceNode.prefab
    CraftingStation.prefab
    Turret.prefab
    Trap.prefab
    Bomb.prefab
    DamageNumber.prefab
    LootChest.prefab
  Input/
    GameInputActions.inputactions    # Unity Input System action asset
  Sprites/
    Materials/                       # Material icons
    Equipment/                       # Weapon/armor icons
    World/                           # Tile sprites, resource sprites
    UI/                              # UI element sprites
    Effects/                         # Particle textures, attack effects
  Resources/
    Models/                          # ONNX files (from Phase 5)
    JSON/                            # Game data JSONs (copied from Python)
```

---

## 2. GameEngine Decomposition

The Python `GameEngine` class (10,098 lines, `core/game_engine.py`) is a monolith that handles initialization (lines 91-400), event processing (lines 488-1165), game loop update (lines 1167-1570), mouse click routing (lines 1573-3165), crafting interaction (lines 3169-3550), minigame orchestration (lines 3550-5700), mouse release/drag (lines 5700-6544), inventory management (lines 6544-7000), and high-level game logic (lines 7000-10098). This must be decomposed into 15-20 Unity components.

### 2.1 Core Game Loop Components

| Unity Component | Responsibility | Python Source Lines |
|---|---|---|
| GameManager.cs (MonoBehaviour) | Bootstrap, initialization order, database loading, system wiring, game state machine | game_engine.py:91-400 (init), 1167-1570 (update) |
| GameStateManager.cs | State transitions: StartMenu, Playing, Paused, Crafting, MinigameActive, Combat, Inventory, Equipment, Map, Encyclopedia, NPCDialogue, ClassSelection, StatsUI, ChestOpen | game_engine.py:518-660 (state flags), 1165-1180 (state guards) |
| InputManager.cs | Keyboard + Mouse input routing via Unity Input System, action map binding | game_engine.py:488-1165 (handle_events) |
| CameraController.cs | Camera follow player, zoom controls, viewport bounds | core/camera.py (30 lines) |

### 2.2 GameManager.cs -- Initialization Order

The Python `__init__` (lines 91-400) loads systems in a specific order. Unity must preserve this:

```
1.  Config.init_screen_settings()          -> ScriptableObject loaded at edit time
2.  pygame.init() / screen setup           -> Unity handles automatically
3.  Database loading (lines 105-150)       -> GameManager.Awake() or loading scene
4.  Crafting crafter init (lines 152-166)  -> Lazy init on first crafting open
5.  WorldSystem init (line 169)            -> WorldRenderer.Initialize()
6.  SaveManager init (line 170)            -> SaveManager singleton (Phase 4)
7.  MapWaypointSystem init (line 171)      -> MapUI component
8.  Character creation (lines 183-196)     -> After menu selection
9.  CombatManager init (lines 202-213)     -> CombatManager singleton (Phase 4)
10. DungeonManager init (line 211)         -> DungeonSystem singleton (Phase 4)
11. NPC spawning (lines 232-238)           -> NPCManager component
12. UI state initialization (lines 241-400) -> Individual UI components self-init
```

**Key principle**: Each UI component initializes its own state in `Awake()` or `Start()`. GameManager only handles cross-system wiring and boot ordering.

### 2.3 GameStateManager.cs -- State Machine

Python uses boolean flags (`crafting_ui_open`, `equipment_ui_open`, `skills_ui_open`, `map_open`, `encyclopedia.is_open`, `start_menu_open`, `npc_dialogue_open`, `class_selection_open`, `stats_ui_open`, `dungeon_chest_open`, `spawn_chest_open`, `death_chest_open`) scattered across GameEngine and Character. Unity should use a proper state machine:

```csharp
public enum GameState
{
    StartMenu,
    ClassSelection,
    Playing,
    Paused,
    InventoryOpen,
    EquipmentOpen,
    CraftingOpen,
    MinigameActive,
    StatsOpen,
    SkillsOpen,
    EncyclopediaOpen,
    MapOpen,
    NPCDialogue,
    DungeonChestOpen,
    SpawnChestOpen,
    DeathChestOpen,
    EnchantmentSelection,
    Loading
}
```

**State transition rules** (from Python escape-key handling, lines 630-660):
- Escape from any UI state returns to `Playing`
- Escape from `Playing` opens pause menu (not implemented in Python, but architecture should support it)
- Only one modal UI state active at a time
- `MinigameActive` blocks all other state transitions until minigame completes or cancels
- `StartMenu` and `ClassSelection` block gameplay entirely

### 2.4 UI Components (Split from GameEngine + Renderer)

| Unity Component | Responsibility | Python Source (game_engine.py) | Python Source (renderer.py) |
|---|---|---|---|
| InventoryUI.cs | 30-slot grid, drag-and-drop, tooltips, drop confirmation | lines 6544-7000 (drop logic) | lines 3977-4238 (render_inventory_panel) |
| EquipmentUI.cs | 10 equipment slots, equip/unequip, durability display | lines 1573-1700 (equip clicks) | lines 5720-5987 (render_equipment_ui + tooltip) |
| CraftingUI.cs | Station interaction, recipe browser, recipe selection sidebar, material placement | lines 3169-3550 (interactive clicks, craft, invent) | lines 4429-5720 (render_crafting_ui, render_interactive_crafting_ui) |
| SmithingMinigameUI.cs | Temperature bar, bellows button, hammer timing bar, hit counter | lines 3550-4000 (minigame input) | lines 106-262 (render_smithing_grid) |
| AlchemyMinigameUI.cs | Reaction chain visualization, timing indicators, stage display | lines 4000-4300 (minigame input) | lines 587-760 (render_alchemy_sequence) |
| RefiningMinigameUI.cs | Cylinder rotation display, alignment indicator, timing window | lines 4300-4600 (minigame input) | lines 406-587 (render_refining_hub) |
| EngineeringMinigameUI.cs | Grid puzzle display, pipe rotation, logic switch toggle | lines 4600-5000 (minigame input) | lines 760-904 (render_engineering_slots) |
| EnchantingMinigameUI.cs | Spinning wheel with 20 slices, spin button, result display | lines 5000-5400 (minigame input) | lines 6179-6257 (enchantment selection) |
| SkillBarUI.cs | 5 hotbar slots, cooldown radial overlay, keybind labels | lines 700-750 (skill activation) | lines 2323-2475 (render_skill_hotbar + tooltip) |
| StatusBarUI.cs | HP/Mana/EXP bars, level display, buff icons | -- | lines 2256-2323 (render_health_bar, render_mana_bar, render_active_buffs) |
| MapUI.cs | World map, chunk grid, waypoints, fog of war, zoom/pan | lines 692-700, 1028-1060 (map drag) | lines 2778-3173 (render_map_ui) |
| EncyclopediaUI.cs | Tabbed browser: guide, quests, skills, titles, stats, recipes | lines 650 (toggle) | lines 2690-2778, 3290-3933 (render_encyclopedia_ui + tab content) |
| NotificationUI.cs | Toast notifications with fade, stacking | -- | lines 3933-3948 (render_notifications) |
| DebugOverlay.cs | F1-F7 debug toggles, stat display, debug messages | lines 750-850 (debug keys) | lines 3948-3977 (render_debug_messages) |
| StartMenuUI.cs | New World / Load World / Load Default / Temporary World | lines 518-530 (menu nav) | lines 6257-6344 (render_start_menu) |
| ClassSelectionUI.cs | 6 class cards with tag descriptions, selection confirmation | lines 654 (toggle) | lines 6344-6426 (render_class_selection_ui) |
| StatsUI.cs | 6 stat allocation, point spending, stat descriptions | lines 644 (toggle) | lines 6426-6538 (render_stats_ui) |
| NPCDialogueUI.cs | Dialogue window, quest list, accept/turn-in buttons | lines 1325-1570 (NPC interaction) | lines 3173-3290 (render_npc_dialogue_ui) |
| TooltipRenderer.cs | Deferred tooltip rendering (always on top of all UI) | -- | lines 6063-6179 (render_pending_tooltip, render_tooltip, render_class_tooltip) |
| DragDropManager.cs | Shared drag state, ghost icon rendering, drop validation | lines 5700-6544 (mouse release, drag) | -- |
| ChestUI.cs | Dungeon/spawn/death chest item grid, loot pickup | lines 636-642 (chest interaction) | lines 1637-2022 (render chest UIs) |

### 2.5 World Rendering Components

| Unity Component | Responsibility | Python Source (renderer.py) |
|---|---|---|
| WorldRenderer.cs | Tilemap rendering, chunk load/unload, tile sprite assignment | lines 965-1391 (render_world) |
| ResourceRenderer.cs | Resource node sprites, HP bars, tool requirement icons | lines 965-1391 (resource drawing within render_world) |
| EntityRenderer.cs | Placed entities: turrets, traps, bombs, crafting stations | lines 2022-2037 (render_placement_preview) |
| EnemyRenderer.cs | Enemy sprites, health bars above head, aggro indicators, corpse fade | lines 965-1391 (enemy drawing within render_world) |
| PlayerRenderer.cs | Player sprite, facing direction indicator, equipment visuals | lines 965-1391 (player drawing within render_world) |
| DamageNumberRenderer.cs | Floating damage numbers with upward drift and fade | lines 965-1391 (damage number drawing) |
| AttackEffectRenderer.cs | Attack lines (melee/ranged), AoE circles, beam effects, blocked indicators | lines 6587-6657 (_render_attack_effects) |
| ParticleEffects.cs | Sparks, embers, bubbles, steam, gear teeth for minigames | Replaces minigame_effects.py (1,522 lines) |
| DayNightOverlay.cs | Time-of-day color overlay with alpha blending | lines 2037-2097 (render_day_night_overlay) |

---

## 3. Renderer Decomposition

The Python `Renderer` class (6,936 lines, `rendering/renderer.py`) handles ALL drawing through a single Pygame surface. In Unity, rendering is distributed across multiple systems.

### 3.1 Rendering Strategy Mapping

| Python Rendering | Unity Replacement | Notes |
|---|---|---|
| `pygame.Surface` blitting | `SpriteRenderer` on GameObjects | World tiles, entities, player, enemies |
| `pygame.draw.rect/circle/line` | `UI.Image`, `LineRenderer`, or `GL.Lines` | UI elements, attack effects |
| `pygame.font.render` | `TextMeshPro` or `UI.Text` | All text rendering |
| Manual pixel manipulation | `Texture2D.SetPixels` or shaders | Minimap, special effects |
| Surface alpha blending | `CanvasGroup.alpha` or sprite alpha | Day/night, fade effects |
| Screen-space drawing | `Canvas` (Screen Space - Overlay) | All HUD and menu UI |
| World-space drawing | `Canvas` (World Space) or `SpriteRenderer` | Health bars, damage numbers |

### 3.2 Tilemap Rendering (WorldRenderer.cs)

Python draws tiles by iterating visible chunks and blitting colored rectangles or sprites. Unity replaces this with the Tilemap system:

```
Python:                          Unity:
for chunk in visible_chunks:     Grid GameObject with Tilemap component
  for tile in chunk.tiles:       TileBase subclasses per tile type
    draw_rect(color)             Rule Tiles or Scriptable Tiles
    draw_resource_icon()         Separate Tilemap layer for resources
```

**Chunk visibility**: Python calculates visible chunks from camera position. Unity Tilemap handles culling automatically, but chunk loading/unloading must still be managed by WorldRenderer based on camera position.

**Tile colors** (from renderer.py, must be preserved as tile sprite tints or palette):
```
grass     = (34, 139, 34)    # Forest green
water     = (30, 144, 255)   # Dodger blue
stone     = (128, 128, 128)  # Gray
sand      = (238, 214, 175)  # Sandy beige
cave      = (64, 64, 64)     # Dark gray
snow      = (240, 240, 255)  # Near white
dirt      = (139, 90, 43)    # Brown
```

### 3.3 Key Rendering Constants to Preserve

```csharp
// Tile and chunk dimensions
public const int TILE_SIZE = 32;           // Pixels per tile (or Unity units)
public const int CHUNK_SIZE = 16;          // Tiles per chunk side
public const int CHUNK_PIXEL_SIZE = 512;   // TILE_SIZE * CHUNK_SIZE

// Viewport
// Dynamic based on screen resolution (Config.VIEWPORT_WIDTH, VIEWPORT_HEIGHT)

// Rarity colors (used throughout UI for item borders, text, backgrounds)
public static readonly Color RarityCommon    = new Color(200/255f, 200/255f, 200/255f);  // Light gray
public static readonly Color RarityUncommon  = new Color(50/255f, 200/255f, 50/255f);    // Green
public static readonly Color RarityRare      = new Color(80/255f, 80/255f, 255/255f);    // Blue
public static readonly Color RarityEpic      = new Color(180/255f, 50/255f, 255/255f);   // Purple
public static readonly Color RarityLegendary = new Color(255/255f, 165/255f, 0/255f);    // Orange

// UI spacing (scaled by Config.scale() in Python, use Unity's responsive layout)
public const int SLOT_SIZE = 40;           // Inventory slot dimension
public const int SLOT_PADDING = 4;         // Between inventory slots
public const int TOOLTIP_PADDING = 8;      // Tooltip internal padding

// Damage number rendering
public const float DAMAGE_NUMBER_RISE_SPEED = 30f;  // Pixels per second upward
public const float DAMAGE_NUMBER_LIFETIME = 1.5f;    // Seconds before fade complete

// Attack effect rendering
public const float ATTACK_LINE_DURATION = 0.3f;  // Seconds visible
public const float ATTACK_LINE_FADE_START = 0.7f; // Start fading at 70% of duration
```

### 3.4 UI Layout Architecture

Python renders all UI to a single surface with manual coordinate calculations. Unity should use a layered Canvas approach:

```
Canvas (Screen Space - Overlay, Sort Order: 100)
  +-- HUD Layer (always visible during gameplay)
  |     +-- StatusBarUI (HP/Mana/EXP)
  |     +-- SkillBarUI (bottom center)
  |     +-- NotificationUI (top right)
  |     +-- DebugOverlay (top left, toggleable)
  |
  +-- Panel Layer (modal, one at a time)
  |     +-- InventoryUI
  |     +-- EquipmentUI
  |     +-- CraftingUI
  |     +-- StatsUI
  |     +-- SkillsUI (EncyclopediaUI skills tab)
  |     +-- EncyclopediaUI
  |     +-- MapUI
  |     +-- NPCDialogueUI
  |     +-- ChestUI
  |
  +-- Minigame Layer (blocks all other UI)
  |     +-- SmithingMinigameUI
  |     +-- AlchemyMinigameUI
  |     +-- RefiningMinigameUI
  |     +-- EngineeringMinigameUI
  |     +-- EnchantingMinigameUI
  |
  +-- Overlay Layer (top of everything)
  |     +-- TooltipRenderer
  |     +-- DragDropManager (ghost icon)
  |     +-- StartMenuUI
  |     +-- ClassSelectionUI
  |
  +-- Loading Layer (highest priority)
        +-- LoadingIndicator
```

---

## 4. Input System Migration

### 4.1 Pygame to Unity Input Mapping

| Pygame Input | Unity Input System | Context |
|---|---|---|
| `pygame.KEYDOWN` / `pygame.KEYUP` | `InputAction.performed` / `InputAction.canceled` | All key events |
| `pygame.MOUSEBUTTONDOWN` | `InputAction.performed` (pointer click action) | UI clicks, world interaction |
| `pygame.MOUSEBUTTONUP` | `InputAction.canceled` (pointer click action) | Drag-and-drop release |
| `pygame.mouse.get_pos()` | `Mouse.current.position.ReadValue()` or `Input.mousePosition` | Tooltip positioning, hover detection |
| `pygame.MOUSEWHEEL` (event.y) | `InputAction` bound to scroll wheel | Recipe list scroll, map zoom |
| `pygame.key.get_pressed()` | `InputAction.ReadValue<float>()` for continuous input | WASD movement (polled every frame) |

### 4.2 Input Action Map

```
GameInputActions:
  Player:
    Move          : WASD / Arrow Keys       -> Vector2 (continuous)
    Interact      : E                        -> Button
    Attack        : Left Mouse Button        -> Button
    SecondaryAttack: Right Mouse Button      -> Button
    ToggleInventory: Tab                     -> Button
    ToggleEquipment: (from inventory)        -> Button
    ToggleMap     : M                        -> Button
    ToggleEncyclopedia: J                    -> Button
    ToggleStats   : C                        -> Button
    ToggleSkills  : K                        -> Button
    Escape        : Escape                   -> Button
    Skill1-5      : 1-5 number keys          -> Button (5 actions)
    PlaceEntity   : P                        -> Button
    Zoom          : Mouse Scroll Wheel       -> Value (float)

  Crafting:
    CraftAction   : Spacebar                 -> Button (hammer strike, spin wheel, etc.)
    Click         : Left Mouse Button        -> Button (grid placement, slot selection)
    Cancel        : Escape                   -> Button (exit minigame)

  Debug:
    DebugToggle   : F1                       -> Button (infinite resources)
    LearnAllSkills: F2                       -> Button
    GrantAllTitles: F3                       -> Button
    MaxLevel      : F4                       -> Button
    InfiniteDurability: F7                   -> Button

  UI:
    Click         : Left Mouse Button        -> Button
    ScrollWheel   : Mouse Scroll Wheel       -> Value (float)
    NavigateUp    : Up Arrow / W             -> Button (menu navigation)
    NavigateDown  : Down Arrow / S           -> Button (menu navigation)
    Confirm       : Enter / Return           -> Button (menu confirm)
```

### 4.3 Input Context Switching

Python checks boolean state flags to determine which input handler runs (game_engine.py lines 1165-1180). Unity should use Input Action Maps that are enabled/disabled based on GameState:

```csharp
void OnGameStateChanged(GameState oldState, GameState newState)
{
    // Disable all maps
    _inputActions.Player.Disable();
    _inputActions.Crafting.Disable();
    _inputActions.Debug.Disable();
    _inputActions.UI.Disable();

    // Enable based on new state
    switch (newState)
    {
        case GameState.Playing:
            _inputActions.Player.Enable();
            _inputActions.Debug.Enable();
            break;
        case GameState.MinigameActive:
            _inputActions.Crafting.Enable();
            break;
        case GameState.StartMenu:
        case GameState.ClassSelection:
            _inputActions.UI.Enable();
            break;
        default: // Any open UI panel
            _inputActions.UI.Enable();
            _inputActions.Debug.Enable();
            break;
    }
}
```

---

## 5. Asset Migration

### 5.1 Icons (3,749 images)

The Python project contains 3,749 image files used as material icons, equipment sprites, UI elements, and world graphics.

**Migration steps**:
1. Copy all images to `Assets/Sprites/` with organized subfolders mirroring the Python structure
2. Set import settings: `Sprite Mode = Single`, `Pixels Per Unit = 32`, `Filter Mode = Point` (pixel art)
3. Create sprite atlases for performance:
   - `MaterialAtlas` -- all material icons
   - `EquipmentAtlas` -- weapons, armor, tools
   - `WorldAtlas` -- tile sprites, resource sprites
   - `UIAtlas` -- buttons, frames, backgrounds
   - `EffectsAtlas` -- particles, attack effect sprites
4. Maintain icon naming conventions from Python (used by `ImageCache` lookups)
5. Build a `SpriteDatabase` that maps item IDs to sprite references (replaces Python `ImageCache`)

### 5.2 JSON Content

All game content is defined in JSON files. These must be accessible at runtime:

**Option A -- StreamingAssets (moddable)**:
```
Assets/StreamingAssets/Content/
  items.JSON/
  recipes.JSON/
  placements.JSON/
  progression/
  Skills/
  Definitions.JSON/
```
Loaded via `Application.streamingAssetsPath` + `File.ReadAllText()`. Supports player modding.

**Option B -- Resources (bundled)**:
```
Assets/Resources/JSON/
  (same structure)
```
Loaded via `Resources.Load<TextAsset>()`. Faster, but not moddable.

**Recommendation**: Use StreamingAssets for all content JSON. The game's JSON-driven design philosophy favors moddability. No schema changes needed -- the Phase 2 database loaders already parse the exact same JSON format.

### 5.3 ML Models

From Phase 5, the 5 ONNX model files are placed in:
```
Assets/Resources/Models/
  smithing.onnx
  adornments.onnx
  alchemy.onnx
  refining.onnx
  engineering.onnx
```

Loaded by `ClassifierManager` via `Resources.Load<ModelAsset>()` (Unity Sentis).

---

## 6. Scene Setup

### 6.1 MainMenu Scene

Minimal scene with:
- `Canvas` with `StartMenuUI` component
- `EventSystem` for UI interaction
- `AudioManager` (persistent across scenes via `DontDestroyOnLoad`)

### 6.2 GameWorld Scene

Full gameplay scene hierarchy:

```
GameWorld (Scene Root)
  +-- GameManager              [GameManager.cs, GameStateManager.cs]
  +-- InputManager             [InputManager.cs, GameInputActions reference]
  +-- Main Camera              [Camera, CameraController.cs]
  +-- Grid                     [Grid component]
  |     +-- GroundTilemap      [Tilemap, TilemapRenderer, WorldRenderer.cs]
  |     +-- ResourceTilemap    [Tilemap, TilemapRenderer, ResourceRenderer.cs]
  +-- EntityContainer          [Transform only, parent for spawned entities]
  +-- Canvas (HUD)             [Canvas - Screen Space Overlay, Sort=0]
  |     +-- StatusBars         [StatusBarUI.cs]
  |     +-- SkillBar           [SkillBarUI.cs]
  |     +-- Notifications      [NotificationUI.cs]
  |     +-- DebugOverlay       [DebugOverlay.cs]
  +-- Canvas (Panels)          [Canvas - Screen Space Overlay, Sort=10]
  |     +-- InventoryPanel     [InventoryUI.cs]
  |     +-- EquipmentPanel     [EquipmentUI.cs]
  |     +-- CraftingPanel      [CraftingUI.cs]
  |     +-- MapPanel           [MapUI.cs]
  |     +-- EncyclopediaPanel  [EncyclopediaUI.cs]
  |     +-- StatsPanel         [StatsUI.cs]
  |     +-- NPCDialoguePanel   [NPCDialogueUI.cs]
  |     +-- ChestPanel         [ChestUI.cs]
  +-- Canvas (Minigames)       [Canvas - Screen Space Overlay, Sort=20]
  |     +-- SmithingMinigame   [SmithingMinigameUI.cs]
  |     +-- AlchemyMinigame    [AlchemyMinigameUI.cs]
  |     +-- RefiningMinigame   [RefiningMinigameUI.cs]
  |     +-- EngineeringMinigame[EngineeringMinigameUI.cs]
  |     +-- EnchantingMinigame [EnchantingMinigameUI.cs]
  +-- Canvas (Overlay)         [Canvas - Screen Space Overlay, Sort=30]
  |     +-- TooltipRenderer    [TooltipRenderer.cs]
  |     +-- DragGhost          [DragDropManager.cs]
  |     +-- ClassSelection     [ClassSelectionUI.cs]
  |     +-- LoadingIndicator   [LoadingUI.cs]
  +-- Canvas (WorldSpace)      [Canvas - World Space]
  |     +-- DamageNumbers      [DamageNumberRenderer.cs]
  |     +-- EnemyHealthBars    [EnemyRenderer.cs manages these]
  +-- EventSystem              [EventSystem, InputSystemUIInputModule]
  +-- Audio                    [AudioManager.cs, AudioSource]
```

### 6.3 Prefab Definitions

| Prefab | Components | Instantiation |
|---|---|---|
| Player.prefab | SpriteRenderer, PlayerRenderer, Rigidbody2D, BoxCollider2D | Once at game start |
| Enemy.prefab | SpriteRenderer, EnemyRenderer, Rigidbody2D, CircleCollider2D | Spawned by EnemySpawner |
| ResourceNode.prefab | SpriteRenderer, ResourceRenderer, BoxCollider2D | Spawned per chunk |
| CraftingStation.prefab | SpriteRenderer, EntityRenderer, BoxCollider2D (trigger) | Spawned at world gen or placed by player |
| Turret.prefab | SpriteRenderer, EntityRenderer, CircleCollider2D (range) | Placed by player |
| Trap.prefab | SpriteRenderer, EntityRenderer, CircleCollider2D (trigger) | Placed by player |
| DamageNumber.prefab | TextMeshPro (World Space), DamageNumberRenderer | Spawned on damage dealt |
| LootChest.prefab | SpriteRenderer, BoxCollider2D (trigger) | Spawned by DungeonSystem |

### 6.4 ScriptableObject Definitions

```csharp
[CreateAssetMenu(fileName = "GameConfig", menuName = "Game1/GameConfig")]
public class GameConfig : ScriptableObject
{
    [Header("World")]
    public int ChunkSize = 16;
    public int TileSize = 32;
    public int WorldSize = 100;   // 100x100 chunks
    public float PlayerSpawnX = 50f;
    public float PlayerSpawnY = 50f;

    [Header("Camera")]
    public float CameraFollowSpeed = 5f;
    public float MinZoom = 0.5f;
    public float MaxZoom = 2.0f;

    [Header("Inventory")]
    public int InventorySlots = 30;
    public int EquipmentSlots = 10;

    [Header("Performance")]
    public int ChunkLoadRadius = 4;    // Chunks around player to keep loaded
    public int ChunkUnloadRadius = 6;  // Distance to unload chunks
}
```

---

## 7. Quality Control

### 7.1 Phase 6 Quality Gate

All of the following must pass before Phase 6 is considered complete:

**Core Loop**:
- [ ] Game boots to start menu without errors
- [ ] New World creates character and loads into gameplay
- [ ] Load World restores full game state from save file
- [ ] Core gameplay loop functional: move, gather resources, open inventory, equip items, craft, fight, level up
- [ ] Game state transitions work correctly (Escape closes panels, Tab opens inventory, M opens map, etc.)
- [ ] No null reference exceptions during normal gameplay flow

**World Rendering**:
- [ ] Tiles render with correct colors/sprites per tile type
- [ ] Chunks load and unload based on camera position
- [ ] Resource nodes display with correct sprites and HP bars
- [ ] Crafting stations render at correct world positions
- [ ] Placed entities (turrets, traps, bombs) render correctly
- [ ] Day/night overlay applies correct alpha per time phase
- [ ] Performance: 60 FPS with 9x9 chunks loaded (81 chunks, 20,736 tiles)

**Entity Rendering**:
- [ ] Player sprite displays and faces movement direction
- [ ] Enemies display with correct sprites per enemy type
- [ ] Enemy health bars update in real-time during combat
- [ ] Damage numbers float upward and fade correctly
- [ ] Attack effect lines render between attacker and target
- [ ] AoE attack circles render at correct radius
- [ ] Corpses fade and disappear after timeout

**Crafting UI**:
- [ ] All 5 crafting discipline placement grids render correctly (smithing 3x3-9x9, refining hub-spoke, alchemy sequential, engineering slot types, adornments Cartesian)
- [ ] Material placement via drag-and-drop works in all 5 disciplines
- [ ] Recipe selection sidebar scrolls and filters correctly
- [ ] Minigame UIs render all visual elements (temperature bar, hammer, reaction chain, cylinders, pipe grid, spinning wheel)
- [ ] Minigame input works: spacebar for actions, mouse clicks for selections
- [ ] Crafting results display with correct quality tier and rewards
- [ ] Invented recipe flow works: place materials, validate via classifier, generate via LLM, receive item

**Inventory and Equipment**:
- [ ] 30 inventory slots render with correct icons and quantities
- [ ] Drag-and-drop between inventory slots works
- [ ] Drag-and-drop to equipment slots validates hand types and slot restrictions
- [ ] Tooltips display correct item information (stats, tags, durability, enchantments)
- [ ] Tooltips render on top of all other UI elements (deferred rendering)
- [ ] Item drop confirmation dialog works
- [ ] Equipment stat bonuses apply and display correctly

**Combat**:
- [ ] Enemies spawn in appropriate chunks based on danger level
- [ ] Player attacks connect and deal displayed damage
- [ ] Enemy attacks deal damage and health bar decreases
- [ ] Status effect icons display on affected entities
- [ ] Enchantment on-hit effects trigger visually (fire, poison, frost, knockback)
- [ ] Death handling: death chest spawns, respawn at spawn point
- [ ] Dungeon entry, wave combat, and loot chest work

**Progression UI**:
- [ ] HP/Mana/EXP bars update in real-time
- [ ] Level-up notification displays
- [ ] Skill hotbar shows correct skills with cooldown overlays
- [ ] Skill activation via number keys 1-5 works
- [ ] Stats allocation screen allows point spending
- [ ] Encyclopedia displays all tabs (guide, quests, skills, titles, stats, recipes)

**Map**:
- [ ] Map displays explored chunks with correct colors
- [ ] Waypoints can be placed and renamed
- [ ] Map zoom and pan work via scroll wheel and drag
- [ ] Player position indicator shows on map
- [ ] Dungeon entrances marked on map

**Save/Load**:
- [ ] Save preserves complete game state (character, world, quests, dungeons, map)
- [ ] Load restores all state correctly including UI positions and scroll offsets
- [ ] Save files are compatible with Phase 4 SaveManager format

**Debug**:
- [ ] F1 toggles infinite resources / debug mode
- [ ] F2 auto-learns all skills
- [ ] F3 grants all titles
- [ ] F4 sets max level and stats
- [ ] F7 toggles infinite durability
- [ ] Debug overlay displays FPS, position, chunk info

**NPC**:
- [ ] NPCs render at correct world positions
- [ ] Interaction opens dialogue window
- [ ] Quest accept and turn-in flow works
- [ ] Quest objectives track correctly

### 7.2 Performance Targets

| Metric | Target | Measurement |
|---|---|---|
| Frame rate | 60 FPS sustained | Unity Profiler, gameplay with 9x9 chunks |
| Chunk load time | < 50ms per chunk | Profiler, on chunk generation |
| UI open time | < 100ms for any panel | Time from key press to fully rendered |
| Minigame frame rate | 60 FPS during all minigames | Profiler during smithing/alchemy/etc. |
| Memory usage | < 500MB total | Profiler, after 30 minutes of gameplay |
| Sprite atlas efficiency | < 10 draw calls for world rendering | Frame Debugger |
| Save/Load time | < 2 seconds for full save | Profiler, with 50+ explored chunks |

---

## 8. Risks and Mitigations

### 8.1 Monolith Decomposition Complexity

**Risk**: The 10,098-line GameEngine has deep coupling between state management, input handling, and UI updates. Splitting into 20+ components may introduce communication bugs where Python used direct attribute access.

**Mitigation**:
- Use a central `GameStateManager` with C# events (`event Action<GameState, GameState>`) for state change notifications
- Use `[SerializeField]` references for direct component-to-component communication where performance matters
- Create an `EventBus` singleton for loose coupling between UI components
- Port one system at a time: start with world rendering (visual verification), then input, then UI panels

### 8.2 Pygame Drawing API Mismatch

**Risk**: Python renderer uses `pygame.draw.rect()`, `pygame.draw.circle()`, `pygame.draw.line()` for everything. Unity has no single equivalent -- different rendering approaches needed for world vs UI vs effects.

**Mitigation**:
- World rendering: Unity Tilemap (automatic batching)
- UI rendering: uGUI `Image` components with sprite references
- Attack effects: `LineRenderer` for beams/attack lines, `SpriteRenderer` for AoE circles
- Debug shapes: `Gizmos.DrawWireSphere` / `Debug.DrawLine` in editor only
- Particle effects: Unity Particle System replaces custom particle classes

### 8.3 Responsive UI Layout

**Risk**: Python UI uses manual pixel coordinate calculations scaled by `Config.scale()`. Hard to replicate exactly in Unity's anchor/layout system.

**Mitigation**:
- Use Unity's `CanvasScaler` with `Scale With Screen Size` (reference resolution matching Python's default)
- Use `LayoutGroup` components for inventory grids and recipe lists instead of manual positioning
- Create a `UIScaler` utility that mirrors `Config.scale()` for constants that need exact pixel values
- Test at multiple resolutions: 1280x720, 1920x1080, 2560x1440

### 8.4 Tooltip Z-Order

**Risk**: Python already has a known issue with tooltip z-order (tooltips covered by equipment menu). The Unity port must fix this.

**Mitigation**:
- Dedicated `TooltipRenderer` component on the highest-sort-order Canvas layer
- All UI components set `TooltipRenderer.Show(content, position)` instead of drawing directly
- `TooltipRenderer` renders in `LateUpdate()` after all other UI updates
- This fixes the existing Python bug as a side effect of proper Unity layering

### 8.5 Drag-and-Drop Across UI Panels

**Risk**: Inventory drag-and-drop in Python uses raw mouse position tracking across frames. Unity's UI event system has its own drag handling that may conflict.

**Mitigation**:
- Implement `IBeginDragHandler`, `IDragHandler`, `IEndDragHandler` on inventory/equipment slot components
- Central `DragDropManager` tracks the dragged `ItemStack` and renders a ghost icon on the overlay Canvas
- Drop targets implement `IDropHandler` and validate placement
- Cancel drag on Escape key or right-click

### 8.6 Minigame Timing Accuracy

**Risk**: Crafting minigames rely on precise timing (100ms temperature ticks, reaction chain stages measured in seconds). Unity's `Time.deltaTime` may introduce drift compared to Python's `pygame.time.get_ticks()`.

**Mitigation**:
- Use accumulator pattern for fixed-interval ticks: `_accumulator += Time.deltaTime; while (_accumulator >= interval) { Tick(); _accumulator -= interval; }`
- For visual smoothness, interpolate display values between logic ticks
- Test timing accuracy with automated frame stepping in Unity Test Framework
- All minigame logic classes (Phase 4) accept `float dt` parameter, not wall-clock time

---

## 9. Migration Order (Within Phase 6)

Components should be built in this order to enable incremental testing:

```
1. Scene setup + GameManager bootstrap          (2 days)
   - Create scene hierarchy
   - GameManager loads all databases
   - Verify no errors on play

2. WorldRenderer + CameraController             (3 days)
   - Tilemap rendering of chunks
   - Camera follows player position (hardcoded)
   - Verify world displays correctly

3. PlayerRenderer + InputManager (movement)     (2 days)
   - Player sprite renders
   - WASD movement works
   - Camera follows player

4. ResourceRenderer + EntityRenderer            (2 days)
   - Resource nodes display
   - Crafting stations display
   - Gathering interaction works

5. EnemyRenderer + combat visuals               (3 days)
   - Enemies display with health bars
   - Attack effects render
   - Damage numbers float
   - DayNightOverlay

6. StatusBarUI + SkillBarUI + NotificationUI    (2 days)
   - HUD elements display
   - HP/Mana/EXP update
   - Skill cooldowns display

7. GameStateManager + panel infrastructure      (2 days)
   - State machine implementation
   - Escape key closes panels
   - Panel open/close transitions

8. InventoryUI + DragDropManager                (3 days)
   - Grid renders with items
   - Drag-and-drop between slots
   - Drop to world

9. EquipmentUI + TooltipRenderer                (2 days)
   - Equipment slots render
   - Equip/unequip via drag
   - Tooltips on hover

10. CraftingUI (recipe selection + placement)   (3 days)
    - Recipe sidebar with filtering
    - Material placement grids (all 5 disciplines)

11. MinigameUIs (all 5)                         (5 days)
    - SmithingMinigameUI (1 day)
    - AlchemyMinigameUI (1 day)
    - RefiningMinigameUI (1 day)
    - EngineeringMinigameUI (1 day)
    - EnchantingMinigameUI (1 day)

12. MapUI + EncyclopediaUI + StatsUI            (3 days)
    - Map rendering with chunks
    - Encyclopedia tabs
    - Stat allocation

13. NPCDialogueUI + ChestUI                    (2 days)
    - NPC interaction flow
    - Chest loot pickup

14. StartMenuUI + ClassSelectionUI              (1 day)
    - Main menu flow
    - Class selection at game start

15. DebugOverlay + ParticleEffects              (2 days)
    - F-key debug toggles
    - Crafting particle systems

16. Save/Load integration + polish              (2 days)
    - Wire SaveManager to UI
    - Test full save/load roundtrip

17. Integration testing + bug fixing            (3 days)
    - Full gameplay loop testing
    - Performance profiling
    - Quality gate validation
```

---

## 10. Estimated Effort

| Subsystem | Files | Estimated Days | Risk |
|---|---|---|---|
| Scene setup + GameManager | 3 | 2 | Low |
| World rendering (Tilemap + chunks) | 3 | 3 | Medium |
| Player + Input | 3 | 2 | Low |
| Resource + Entity rendering | 2 | 2 | Low |
| Enemy rendering + combat visuals | 4 | 3 | Medium |
| HUD (StatusBar, SkillBar, Notifications) | 3 | 2 | Low |
| GameStateManager + panel system | 2 | 2 | Medium |
| Inventory + DragDrop | 3 | 3 | High |
| Equipment + Tooltips | 2 | 2 | Medium |
| Crafting UI (placement + recipes) | 2 | 3 | High |
| 5 Minigame UIs | 6 | 5 | High |
| Map + Encyclopedia + Stats | 3 | 3 | Medium |
| NPC Dialogue + Chests | 2 | 2 | Low |
| Start Menu + Class Selection | 2 | 1 | Low |
| Debug + Particles | 2 | 2 | Low |
| Save/Load integration | 1 | 2 | Medium |
| Integration testing | -- | 3 | Medium |
| **Total** | **~43** | **~42 days** | |

---

## 11. Success Criteria

Phase 6 is complete when:

1. The game boots from Unity Editor to start menu, through class selection, into gameplay without errors
2. The full gameplay loop works: move, gather, craft (all 5 disciplines with minigames), fight, equip, level up
3. All UI panels open, display correct data, and close properly via Escape
4. Inventory drag-and-drop works between all valid source/target combinations
5. All 5 crafting minigame UIs render correctly and accept player input
6. Invented recipe flow works end-to-end: placement, classifier validation (Phase 5), LLM generation, item received
7. World renders with correct tiles, resources, stations, enemies, and player
8. Combat visuals display correctly: attack lines, damage numbers, status effects, death
9. Save/load preserves complete game state and restores all UI to correct state
10. 60 FPS sustained during normal gameplay with 9x9 chunks loaded
11. All debug toggles (F1-F7) function correctly
12. All Phase 6 quality gate items checked off

---

## 3D Readiness (Phase 6 Responsibilities)

Phase 6 is where 2D visuals are rendered in Unity — but the rendering layer MUST be structured to support future 3D upgrades.

### Camera Architecture

```csharp
public class CameraController : MonoBehaviour
{
    [SerializeField] private bool _orthographic = true; // Start 2D, toggle for 3D
    [SerializeField] private float _orthographicSize = 8f;
    [SerializeField] private float _perspectiveFOV = 60f;

    private void Start()
    {
        Camera.main.orthographic = _orthographic;
        if (_orthographic)
            Camera.main.orthographicSize = _orthographicSize;
        else
            Camera.main.fieldOfView = _perspectiveFOV;
    }
}
```

### World Rendering

- Use `Tilemap` on the XZ plane (rotated 90 degrees from Unity's default XY Tilemap)
- OR: Use a custom mesh renderer that places tiles as quads on the XZ plane
- Either approach supports future swap to 3D terrain (heightmap, voxels, etc.)
- All tile positions go through `WorldSystem.TileToWorld()` — never hardcoded pixel offsets

### Entity Rendering

- Player, enemies, and objects are `GameObjects` at `Vector3` positions
- SpriteRenderers face the camera (billboard if needed)
- Positions come from `GamePosition.ToVector3()` — already 3D-ready
- Future: swap SpriteRenderer for MeshRenderer + 3D models

### Particle Effects

- Use Unity Particle System instead of Python pixel-based particles
- Particles work identically in 2D and 3D — no changes needed later

### Input System

- Use Unity Input System with action maps (not legacy `Input.GetKey()`)
- Mouse raycasting uses `Camera.ScreenToWorldPoint()` — works in both ortho and perspective

**Next Phase**: Phase 6 produces a fully playable Unity build matching the Python/Pygame version's functionality. The 3D-ready architecture means subsequent phases can upgrade visuals to 3D models, terrain, and perspective camera by changing content and config — not logic.
