# Post-Migration Plan: From Source Files to Playable Prototype

**Date**: 2026-02-16
**Goal**: Get the migrated C# code running in Unity as a play-testable prototype with placeholder visuals
**Scope**: Everything needed between "139 C# files in a folder" and "press Play, walk around, fight, craft"
**Excludes**: Full LLM integration, trained ML classifiers, final art — these use placeholders/stubs

---

## Table of Contents

0. [Current State Assessment](#0-current-state-assessment)
1. [User Setup Guide (Manual Steps)](#1-user-setup-guide-manual-steps)
2. [Assembly Definitions](#2-assembly-definitions)
3. [Compilation Fix Pass](#3-compilation-fix-pass)
4. [JSON Data Pipeline](#4-json-data-pipeline)
5. [Editor Automation Scripts](#5-editor-automation-scripts)
6. [Placeholder Visual Systems](#6-placeholder-visual-systems)
7. [Integration Wiring](#7-integration-wiring)
8. [Test Infrastructure](#8-test-infrastructure)
9. [Play-Test Readiness Checklist](#9-play-test-readiness-checklist)
10. [What's Deferred](#10-whats-deferred)

---

## 0. Current State Assessment

### What Exists

| Category | Count | Status |
|----------|-------|--------|
| C# source files | 133 | Written, never compiled |
| C# test files | 6 | Custom framework (no NUnit), pure C# |
| Python ONNX scripts | 2 | Exist, never run |
| Migration documentation | 24+ docs | Complete |
| Adaptive changes logged | 25 | Complete |

### What Does NOT Exist

| Category | Impact | Required For |
|----------|--------|-------------|
| Unity project (ProjectSettings/, Packages/) | Cannot open in Editor | Everything |
| .meta files (0 of 139 files) | No asset GUIDs | Everything |
| Assembly definitions (.asmdef) | All code in one assembly | Compilation isolation |
| .unity scene files | No game world | Playing the game |
| Prefabs | No reusable objects | Scene assembly |
| StreamingAssets/Content/ | No game data | Database loading |
| Resources/ folder | No sprites, audio, models | Rendering |
| ScriptableObject asset instances | No config assets | GameManager initialization |
| ONNX model files | No ML inference | Classifier validation |
| Sprite atlases | No visual assets | Rendering |

### Key Code Characteristics (From Audit)

These findings directly affect the plan:

1. **InputManager has full fallback bindings** — No InputActionAsset required. All keybindings (WASD, E, Tab, M, J, C, K, 1-5, F1-F7) are created inline when no asset is assigned.

2. **Most UI components create elements dynamically** — InventoryUI, CraftingUI, StatusBarUI all check `if (prefab == null)` and create UI elements via `new GameObject()`. Missing prefabs degrade visuals, not functionality.

3. **WorldRenderer has fallback tile creation** — If no TileBase assets are assigned, it calls `_createFallbackTiles()` to generate colored tiles at runtime.

4. **GameManager uses SerializeField for manager references** — Currently requires Inspector wiring. This should be changed to use `FindFirstObjectByType<>()` for zero-configuration setup.

5. **Tests use a custom framework** — No NUnit attributes, no Unity Test Runner integration. Tests are standalone C# classes with `static int RunAll()` methods. They work without Unity entirely.

6. **All Phase 1-5 code is pure C#** — Zero UnityEngine references. Only Phase 6 (Game1.Unity namespace) imports UnityEngine.

7. **SpriteDatabase loads from Resources/** — Falls back to generated colored textures when sprites are missing.

8. **Database singletons all have `ResetInstance()`** — Good for testing, means state can be cleaned between test runs.

### What "Play-Testable Prototype" Means

The player can:
- Start a new game, select a class
- Move around the world (WASD), see colored tiles representing terrain
- See colored rectangles representing enemies, resources, player
- Open inventory (Tab), equipment (E), stats, map, encyclopedia
- Gather resources (interact with resource nodes)
- Craft items (select recipe, run minigame)
- Fight enemies (auto-attack, skills on hotbar 1-5)
- Level up, allocate stats
- Save and load the game
- See placeholder UI for all panels
- See damage numbers, status bars, notifications

The player will NOT see:
- Final sprite art (colored shapes instead)
- Particle effects (placeholder or none)
- Real ML classifier validation (mock/always-valid)
- Real LLM item generation (stub items)
- Audio (placeholder AudioManager with no clips)
- Polished UI layouts (functional but rough)

---

## 1. User Setup Guide (Manual Steps)

**This section is for the project owner.** These steps require the Unity Editor GUI and cannot be automated by an AI coding assistant. Everything else in this document CAN be done via code.

### Prerequisites

- **Computer**: Windows 10/11, macOS 12+, or Ubuntu 20.04+
- **Disk space**: ~10 GB free (Unity Editor + project)
- **Internet**: Required for download

### Step 1: Install Unity Hub (5 minutes)

Unity Hub is the launcher that manages Unity Editor installations and projects.

1. Go to https://unity.com/download
2. Click "Download Unity Hub"
3. Run the installer, accept defaults
4. Open Unity Hub
5. Sign in (create a free Unity account if you don't have one)
6. Accept the Personal license (free for revenue under $200K)

### Step 2: Install Unity Editor (10-30 minutes, depending on internet)

1. In Unity Hub, click **Installs** in the left sidebar
2. Click **Install Editor**
3. Select **Unity 6000.0 LTS** (or the latest LTS version available)
   - LTS = Long Term Support = most stable
   - If Unity 6 LTS isn't available, use **2022.3 LTS** instead
4. On the modules page, check:
   - **Microsoft Visual Studio Community** (or your preferred IDE) — for editing C# code
   - You can uncheck platforms you don't need (Android, iOS, etc.) to save disk space
5. Click **Install** and wait for download + installation

### Step 3: Create a New Unity Project (2 minutes)

1. In Unity Hub, click **Projects** in the left sidebar
2. Click **New project**
3. Select the **3D (Built-in Render Pipeline)** template
   - This is the simplest template — the code uses basic rendering
   - Do NOT pick URP or HDRP — the MonoBehaviours don't use those
4. Set **Project name** to `Game1-Unity`
5. Set **Location** to wherever you want the project
6. Click **Create project**
7. Wait for Unity to initialize (1-2 minutes first time)

The Editor will open with an empty scene.

### Step 4: Install Required Packages (3 minutes)

In the Unity Editor:

1. Go to **Window > Package Manager**
2. In the top-left dropdown, select **Unity Registry**
3. Search for and install each of these packages (click the package, then click **Install**):

| Package | Why It's Needed |
|---------|----------------|
| **Input System** | InputManager.cs uses the new Input System |
| **TextMeshPro** | All UI text uses TextMeshProUGUI |
| **Newtonsoft Json** | All database loaders use Newtonsoft.Json |

When you install TextMeshPro, it may ask to import "TMP Essential Resources" — click **Import**.

**Skip for now** (placeholder mode):
- Unity Sentis (ML classifiers are mocked for the prototype)

4. Close the Package Manager

### Step 5: Copy the Migrated Code Into the Project (2 minutes)

The Unity project you just created has an `Assets/` folder. You need to copy the migrated code into it.

1. In your file explorer, navigate to your Game-1 repository:
   ```
   Game-1/Unity/Assets/Scripts/
   Game-1/Unity/Assets/Tests/
   ```

2. Copy **both folders** (`Scripts/` and `Tests/`) into your new Unity project's `Assets/` folder:
   ```
   Game1-Unity/Assets/Scripts/    <-- paste here
   Game1-Unity/Assets/Tests/      <-- paste here
   ```

3. Switch back to the Unity Editor. It will detect the new files and start compiling. **This will produce errors** — that's expected. The next sections of this plan fix them.

### Step 6: Copy JSON Game Data (2 minutes)

1. In your new Unity project, create the folder path:
   ```
   Game1-Unity/Assets/StreamingAssets/Content/
   ```
   You can do this in the Unity Editor: right-click in the Project panel > Create > Folder.
   Create `StreamingAssets` inside `Assets/`, then `Content` inside `StreamingAssets`.

2. From the Game-1 repository, copy these folders into `StreamingAssets/Content/`:
   ```
   Game-1/Game-1-modular/items.JSON/         → Content/items.JSON/
   Game-1/Game-1-modular/recipes.JSON/       → Content/recipes.JSON/
   Game-1/Game-1-modular/placements.JSON/    → Content/placements.JSON/
   Game-1/Game-1-modular/Definitions.JSON/   → Content/Definitions.JSON/
   Game-1/Game-1-modular/progression/        → Content/progression/
   Game-1/Game-1-modular/Skills/             → Content/Skills/
   ```

   The final structure should look like:
   ```
   Assets/StreamingAssets/Content/
   ├── items.JSON/           (6-8 .JSON files)
   ├── recipes.JSON/         (6-7 .JSON files)
   ├── placements.JSON/      (5-6 .JSON files)
   ├── Definitions.JSON/     (14+ .JSON files)
   ├── progression/          (5-7 .JSON files)
   └── Skills/               (2-3 .JSON files)
   ```

3. Do NOT rename or reformat any files. They must be byte-identical to the Python originals.

### What Happens Next

After Step 6, you'll have a Unity project with:
- The Unity Editor open
- 139 C# files showing compilation errors in the Console
- JSON game data in StreamingAssets

**From this point, all remaining work is code changes** that can be made by a coding assistant (Claude, etc.) in your IDE or terminal. The remaining sections of this plan describe that work.

### Summary of User Work

| Step | Time | What |
|------|------|------|
| Install Unity Hub | 5 min | Download and run installer |
| Install Unity Editor | 10-30 min | Download (mostly waiting) |
| Create project | 2 min | Click through wizard |
| Install packages | 3 min | 3 packages from Package Manager |
| Copy C# files | 2 min | Copy 2 folders |
| Copy JSON data | 2 min | Copy 6 folders |
| **Total** | **~25-45 min** | Mostly waiting for downloads |

---

## 2. Assembly Definitions

Assembly definition files (`.asmdef`) are JSON files that tell Unity how to organize code into separate compilation units. Without them, all 139 files compile into one giant assembly and cross-namespace dependency rules can't be enforced.

### Files to Create

Each `.asmdef` is a small JSON file placed in the root of its directory.

| File | Location | References |
|------|----------|------------|
| `Game1.Core.asmdef` | `Scripts/Game1.Core/` | `Newtonsoft.Json` |
| `Game1.Data.asmdef` | `Scripts/Game1.Data/` | `Game1.Core`, `Newtonsoft.Json` |
| `Game1.Entities.asmdef` | `Scripts/Game1.Entities/` | `Game1.Core`, `Game1.Data`, `Newtonsoft.Json` |
| `Game1.Systems.asmdef` | `Scripts/Game1.Systems/` | `Game1.Core`, `Game1.Data`, `Game1.Entities`, `Newtonsoft.Json` |
| `Game1.Unity.asmdef` | `Scripts/Game1.Unity/` | `Game1.Core`, `Game1.Data`, `Game1.Entities`, `Game1.Systems`, `Unity.InputSystem`, `Unity.TextMeshPro` |
| `Game1.Tests.EditMode.asmdef` | `Tests/EditMode/` | All above, `nunit.framework`, Editor-only |
| `Game1.Tests.PlayMode.asmdef` | `Tests/PlayMode/` | All above, `nunit.framework` |

### Example .asmdef Format

```json
{
    "name": "Game1.Core",
    "rootNamespace": "Game1.Core",
    "references": [
        "Newtonsoft.Json"
    ],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": true
}
```

**Critical detail**: `"noEngineReferences": true` for Game1.Core, Game1.Data, Game1.Entities, and Game1.Systems. This enforces at compile time that Phase 1-5 code cannot accidentally import UnityEngine. Only Game1.Unity gets `"noEngineReferences": false`.

### Dependency Graph

```
Game1.Core (no engine)
  ↓
Game1.Data (no engine)
  ↓
Game1.Entities (no engine)
  ↓
Game1.Systems (no engine)
  ↓
Game1.Unity (with engine) ← Unity.InputSystem, Unity.TextMeshPro
  ↓
Game1.Tests.EditMode / Game1.Tests.PlayMode
```

### Implementation Notes

- The `Newtonsoft.Json` assembly name in Unity's package is `"Newtonsoft.Json"` (from `com.unity.nuget.newtonsoft-json`)
- For InputSystem: reference name is `"Unity.InputSystem"`
- For TextMeshPro: reference name is `"Unity.TextMeshPro"`
- Test assemblies need `"overrideReferences": true` with `"precompiledReferences": ["nunit.framework.dll"]` and `"defineConstraints": ["UNITY_INCLUDE_TESTS"]`

---

## 3. Compilation Fix Pass

The 139 C# files were written by an LLM without a C# compiler. They'll need a fix pass once Unity attempts compilation. This section catalogs the expected categories of errors and the strategy for each.

### 3.1 Expected Error Categories

#### Category A: Missing or Incorrect Using Statements
**Likelihood**: Medium
**Fix**: Add the correct `using` directive

Common cases:
- `System.Linq` missing (for `.Where()`, `.Select()`, `.ToList()`)
- `System.Collections.Generic` missing (for `Dictionary<>`, `List<>`)
- `Newtonsoft.Json.Linq` missing (for `JObject`, `JArray`, `JToken`)
- Cross-namespace references (e.g., `Game1.Systems.Combat` referencing `Game1.Entities`)

#### Category B: Unity API Differences
**Likelihood**: Medium-High (Phase 6 files only)
**Fix**: Update to match installed Unity version's API

Common cases:
- `FindFirstObjectByType<T>()` vs `FindObjectOfType<T>()` (name changed in Unity 2023+)
- `Tilemap` API changes between versions
- `InputAction` constructor signature differences
- `TextMeshProUGUI` vs `TMP_Text` naming
- `Resources.Load<ModelAsset>()` — Sentis type names evolve between versions

#### Category C: Type Mismatches at Phase Boundaries
**Likelihood**: Low-Medium
**Fix**: Align types between caller and callee

Cases:
- Phase 6 MonoBehaviour calling Phase 4 system with wrong parameter types
- Method signatures that evolved during implementation but weren't updated across phases
- `object` vs specific type casts (e.g., ManaCost as `object` per AC-006)

#### Category D: Sentis/ML References Without Package
**Likelihood**: Certain (by design)
**Fix**: Wrap in `#if UNITY_SENTIS` preprocessor directives or provide mock

The two files `SentisModelBackend.cs` and `SentisBackendFactory.cs` reference Unity Sentis types. Since Sentis is excluded from the prototype, these files need to either:
1. Be excluded from compilation (move out of Scripts/ temporarily), OR
2. Be wrapped in `#if UNITY_SENTIS` / `#endif` blocks, OR
3. Be replaced with mock implementations that return placeholder results

**Recommended**: Option 3 — replace with mocks that match the `IModelBackend` interface but return `(0.8f, null)` (always valid, 80% confidence). This keeps the classifier pipeline functional without Sentis.

#### Category E: Test Framework Incompatibility
**Likelihood**: Low
**Fix**: Adapt custom test runner to Unity Test Framework

The 6 test files use a custom `RunAll()` pattern instead of NUnit `[Test]` attributes. They won't show up in Unity's Test Runner window. Options:
1. Add `[Test]` wrapper methods that call the existing test methods
2. Create an Editor menu item that runs `RunAll()` directly
3. Leave as-is and run via editor script

**Recommended**: Option 2 for now — add a `[MenuItem("Game1/Run Tests")]` that calls all `RunAll()` methods.

### 3.2 Fix Strategy

**Phase 1**: Let Unity compile and collect all errors from the Console.

**Phase 2**: Fix in dependency order:
1. Game1.Core (should compile cleanly — no dependencies)
2. Game1.Data (depends only on Core + Newtonsoft)
3. Game1.Entities (depends on Core + Data)
4. Game1.Systems (depends on all above)
5. Game1.Unity (depends on all above + Unity packages)
6. Tests (depends on everything)

**Phase 3**: Handle Sentis — mock out or exclude the 2 ML backend files.

**Phase 4**: Verify test compilation separately.

### 3.3 Anticipated Code Changes

Based on the audit, specific files likely to need changes:

| File | Likely Issue | Fix |
|------|-------------|-----|
| `SentisModelBackend.cs` | Missing Sentis package | Replace with mock |
| `SentisBackendFactory.cs` | Missing Sentis package | Replace with mock |
| `GameManager.cs` | SerializeField wiring | Add FindFirstObjectByType fallbacks |
| `WorldRenderer.cs` | Tilemap API version | Check against installed Unity version |
| `InputManager.cs` | InputSystem API version | Check InputAction constructor |
| `DragDropManager.cs` | IBeginDragHandler etc. | Verify EventSystems interface names |
| `MapUI.cs` | Texture2D creation | Verify runtime texture API |

---

## 4. JSON Data Pipeline

### 4.1 Path Resolution

`GamePaths.cs` resolves the content root in this priority order:
1. Explicit path set via `GamePaths.SetBasePath(path)` (called by GameManager)
2. `{AppDomain.BaseDirectory}/StreamingAssets/Content/`
3. `{AppDomain.BaseDirectory}/../StreamingAssets/Content/`
4. `{AppDomain.BaseDirectory}/Content/`
5. `{CurrentDirectory}/Content/`

In Unity Editor, `GameManager.Awake()` calls:
```csharp
GamePaths.SetBasePath(Application.streamingAssetsPath + "/Content");
```

This resolves to: `{ProjectRoot}/Assets/StreamingAssets/Content/`

### 4.2 Required JSON Files

**Minimum viable set** (the DatabaseInitializer loads these):

| Database | JSON Path (relative to Content/) | Required? |
|----------|----------------------------------|-----------|
| ClassDatabase | `progression/classes-1.JSON` | Yes |
| ResourceNodeDatabase | `Definitions.JSON/resource-node-1.JSON` | Yes |
| MaterialDatabase | `items.JSON/items-materials-1.JSON` | Yes |
| MaterialDatabase | `items.JSON/items-refining-1.JSON` | Yes |
| MaterialDatabase | `items.JSON/items-alchemy-1.JSON` | Yes |
| MaterialDatabase | `items.JSON/items-engineering-1.JSON` | Yes |
| MaterialDatabase | `items.JSON/items-tools-1.JSON` | Yes |
| EquipmentDatabase | `items.JSON/items-smithing-2.JSON` | Yes |
| SkillDatabase | `Skills/skills-skills-1.JSON` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-smithing-3.json` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-alchemy-1.JSON` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-refining-1.JSON` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-engineering-1.JSON` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-enchanting-1.JSON` | Yes |
| RecipeDatabase | `recipes.JSON/recipes-adornments-1.json` | Yes |
| PlacementDatabase | `placements.JSON/placements-smithing-1.json` | Yes |
| PlacementDatabase | `placements.JSON/placements-alchemy-1.JSON` | Yes |
| PlacementDatabase | `placements.JSON/placements-refining-1.JSON` | Yes |
| PlacementDatabase | `placements.JSON/placements-engineering-1.JSON` | Yes |
| PlacementDatabase | `placements.JSON/placements-adornments-1.JSON` | Yes |
| TitleDatabase | `progression/titles-1.JSON` | Yes |
| WorldGenerationConfig | `Definitions.JSON/world_generation.JSON` | Yes |
| TagRegistry | `Definitions.JSON/tag-definitions.JSON` | Yes |

**Also needed for full functionality** (loaded by specific systems, not DatabaseInitializer):

| System | JSON Path | Impact If Missing |
|--------|-----------|-------------------|
| CombatConfig | `Definitions.JSON/hostiles-1.JSON` | No enemies spawn |
| CombatConfig | `Definitions.JSON/combat-config.JSON` | Default combat values used |
| QuestSystem | `progression/quests-1.JSON` | No quests available |
| SkillUnlockSystem | `progression/skill-unlocks.JSON` | All skills locked |
| WorldSystem | `Definitions.JSON/Chunk-templates-2.JSON` | Basic chunk generation |

### 4.3 Validation Script

An Editor script should be created to validate all JSON files load correctly:

```
[MenuItem("Game1/Validate/Check All JSON Data")]
```

This calls `DatabaseInitializer.InitializeAll()` and reports:
- Which databases loaded successfully
- How many records each database contains
- Which files were missing or failed to parse
- Total load time

### 4.4 Copy Automation

A shell script or Editor script to copy JSON files from the Python source:

```
[MenuItem("Game1/Setup/Copy JSON From Python Source")]
```

This script:
1. Prompts for the path to `Game-1-modular/` (or reads from a config file)
2. Copies the 6 source directories to `StreamingAssets/Content/`
3. Excludes test files (`*-testing-*.JSON`)
4. Reports file count and total size

---

## 5. Editor Automation Scripts

The goal is to minimize manual Unity Editor work. These Editor scripts run via menu items and set up the project programmatically.

### 5.1 Master Setup Script

**File**: `Assets/Editor/Game1Setup.cs`

**Menu**: `Game1 > Setup > Full Project Setup`

Runs all setup steps in sequence:
1. Validate packages are installed
2. Validate StreamingAssets/Content/ has JSON files
3. Create the scene hierarchy
4. Create the Canvas layers and UI panels
5. Wire all MonoBehaviour references
6. Create placeholder ScriptableObject assets
7. Save the scene
8. Report results

### 5.2 Scene Hierarchy Creator

**Menu**: `Game1 > Setup > Create Game Scene`

Creates the full GameObject hierarchy documented in Phase 6 Implementation Summary §6:

```
Game1Scene
├── [GameManager]           + GameManager.cs
├── [GameStateManager]      + GameStateManager.cs
├── [InputManager]          + InputManager.cs
├── [AudioManager]          + AudioManager.cs
├── MainCamera              + Camera + CameraController.cs
│                             (Orthographic, size=8, rotation=(90,0,0))
├── World
│   ├── Grid                + Grid component
│   │   └── GroundTilemap   + Tilemap + TilemapRenderer + WorldRenderer.cs
│   ├── Player              + SpriteRenderer + PlayerRenderer.cs
│   ├── DamageNumbers       + DamageNumberRenderer.cs
│   ├── AttackEffects       + AttackEffectRenderer.cs
│   └── ParticleEffects     + ParticleEffects.cs
├── Canvas_HUD              (ScreenSpaceOverlay, sortOrder=0)
│   ├── StatusBars          + StatusBarUI.cs
│   ├── SkillBar            + SkillBarUI.cs
│   ├── Notifications       + NotificationUI.cs
│   ├── DayNightOverlay     + DayNightOverlay.cs (Image, raycastTarget=false)
│   └── DebugOverlay        + DebugOverlay.cs
├── Canvas_Panels           (ScreenSpaceOverlay, sortOrder=10)
│   ├── Inventory           + InventoryUI.cs (starts inactive)
│   ├── Equipment           + EquipmentUI.cs (starts inactive)
│   ├── Crafting            + CraftingUI.cs (starts inactive)
│   ├── Stats               + StatsUI.cs (starts inactive)
│   ├── Chest               + ChestUI.cs (starts inactive)
│   ├── NPCDialogue         + NPCDialogueUI.cs (starts inactive)
│   ├── Map                 + MapUI.cs (starts inactive)
│   ├── Encyclopedia        + EncyclopediaUI.cs (starts inactive)
│   ├── StartMenu           + StartMenuUI.cs (starts active)
│   └── ClassSelection      + ClassSelectionUI.cs (starts inactive)
├── Canvas_Minigames        (ScreenSpaceOverlay, sortOrder=20)
│   ├── SmithingMinigame    + SmithingMinigameUI.cs (starts inactive)
│   ├── AlchemyMinigame     + AlchemyMinigameUI.cs (starts inactive)
│   ├── RefiningMinigame    + RefiningMinigameUI.cs (starts inactive)
│   ├── EngineeringMinigame + EngineeringMinigameUI.cs (starts inactive)
│   └── EnchantingMinigame  + EnchantingMinigameUI.cs (starts inactive)
├── Canvas_Overlay          (ScreenSpaceOverlay, sortOrder=30)
│   ├── Tooltip             + TooltipRenderer.cs
│   └── DragGhost           + DragDropManager.cs
└── [SpriteDatabase]        + SpriteDatabase.cs
```

Every `+` component is added via `AddComponent<>()`. Every Canvas gets `Canvas`, `CanvasScaler` (ScaleWithScreenSize, 1920x1080), `GraphicRaycaster`.

The `[brackets]` indicate empty GameObjects that exist only to hold their component.

### 5.3 GameManager Self-Wiring

**Problem**: GameManager currently expects 4 SerializeField references to be wired in Inspector:
```csharp
[SerializeField] private GameStateManager _stateManager;
[SerializeField] private InputManager _inputManager;
[SerializeField] private CameraController _cameraController;
[SerializeField] private AudioManager _audioManager;
```

**Solution**: Add fallback auto-discovery in `Awake()`:

```csharp
private void Awake()
{
    // Auto-wire if not set in Inspector
    if (_stateManager == null) _stateManager = FindFirstObjectByType<GameStateManager>();
    if (_inputManager == null) _inputManager = FindFirstObjectByType<InputManager>();
    if (_cameraController == null) _cameraController = FindFirstObjectByType<CameraController>();
    if (_audioManager == null) _audioManager = FindFirstObjectByType<AudioManager>();
    // ... rest of initialization
}
```

This eliminates the need for Inspector wiring entirely. The scene setup script creates the GameObjects; auto-discovery wires them.

**Apply the same pattern** to any other MonoBehaviour that uses `[SerializeField]` for cross-component references:
- InputManager → GameStateManager
- WorldRenderer → CameraController
- All UI panels → GameStateManager

### 5.4 ScriptableObject Asset Creator

**Menu**: `Game1 > Setup > Create Config Assets`

Creates the 4 ScriptableObject instances in `Assets/Resources/Config/`:
- `GameConfigAsset.asset`
- `CraftingConfigAsset.asset`
- `CombatConfigAsset.asset`
- `RenderingConfigAsset.asset`

All with their default values (which are already sensible — camera speed, damage number colors, etc.). GameManager loads them via `Resources.Load<GameConfigAsset>("Config/GameConfigAsset")`.

### 5.5 Reference Auto-Wirer

**Menu**: `Game1 > Setup > Wire All References`

After scene creation, this script:
1. Finds all MonoBehaviours in the scene
2. For each `null` SerializeField, attempts to resolve it:
   - Component references → `FindFirstObjectByType<>()`
   - ScriptableObject references → `Resources.Load<>()`
   - Transform/GameObject references → `transform` (self) or named child
3. Reports any references it couldn't resolve

---

## 6. Placeholder Visual Systems

The prototype uses colored shapes instead of sprites. This section defines what each visual system needs.

### 6.1 Placeholder Tiles (WorldRenderer)

WorldRenderer already has `_createFallbackTiles()` that generates:
- Grass: green (34, 139, 34)
- Water: blue (30, 144, 255)
- Stone: gray (128, 128, 128)
- Sand: tan (194, 178, 128)

**No additional work needed** — fallback tiles are built in.

### 6.2 Placeholder Sprites (SpriteDatabase)

SpriteDatabase has fallback behavior:

```csharp
// If sprite not found, generates a colored texture
private Sprite CreateFallbackSprite(Color color)
```

**No additional work needed** for basic functionality. Items, enemies, and resources will appear as colored squares.

### 6.3 Placeholder Player

PlayerRenderer needs a SpriteRenderer. The setup script should:
1. Create a 1x1 white sprite (generated at runtime)
2. Tint it blue for the player
3. Assign to PlayerRenderer's SpriteRenderer

### 6.4 Placeholder Enemies

EnemyRenderer creates health bars dynamically. The sprite can be a colored rectangle:
- Regular enemies: red tint
- Boss enemies: red tint, 1.5x scale (already in code)

### 6.5 Placeholder UI

All UI panels already create elements dynamically when prefabs are null. The visual quality will be "programmer art" (default Unity UI elements with white backgrounds and black text), but functionally complete.

**Optional improvement**: Create a basic UI stylesheet that sets:
- Panel background: dark semi-transparent (0, 0, 0, 200)
- Text color: white
- Button background: gray
- Button hover: light gray

This can be applied in the setup script via code.

### 6.6 Sentis/ML Classifier Mock

Replace `SentisModelBackend.cs` and `SentisBackendFactory.cs` with mock implementations:

```csharp
// MockModelBackend.cs
public class MockModelBackend : IModelBackend
{
    public (float probability, string error) Predict(float[] inputData)
    {
        return (0.85f, null); // Always returns valid with 85% confidence
    }
    public bool IsLoaded => true;
    public void Dispose() { }
}

public class MockBackendFactory : IModelBackendFactory
{
    public IModelBackend Create(string modelPath, string classifierType)
    {
        return new MockModelBackend();
    }
}
```

GameManager initialization changes:
```csharp
ClassifierManager.Instance.Initialize(new MockBackendFactory());
```

This means every crafting "invention" attempt will pass validation. The stub LLM item generator (already implemented in Phase 7) will produce placeholder items.

---

## 7. Integration Wiring

These are connections between systems that were documented but not implemented in code.

### 7.1 NotificationSystem → NotificationUI Bridge

**Status**: Both systems exist independently. `NotificationSystem` (Phase 7, pure C#) manages a notification queue. `NotificationUI` (Phase 6, MonoBehaviour) renders toast notifications.

**Wire in GameManager or NotificationUI.Start()**:
```csharp
NotificationSystem.Instance.OnNotificationShow += (message, type, duration) =>
{
    var color = NotificationSystem.GetColor(type);
    NotificationUI.Instance.Show(message, new Color(color.R / 255f, color.G / 255f, color.B / 255f), duration);
};
```

### 7.2 IItemGenerator → CraftingUI Pipeline

**Status**: `StubItemGenerator` exists (Phase 7). `CraftingUI` exists (Phase 6). They aren't connected.

**Wire when classifier returns valid for an "invented" recipe**:
```csharp
// In CraftingUI, when player clicks "Invent" and classifier says valid:
private async void OnInventAttempt(CraftingDiscipline discipline, /* placement data */)
{
    IItemGenerator generator = new StubItemGenerator();
    var request = new ItemGenerationRequest
    {
        Discipline = discipline,
        StationTier = currentStationTier,
        Materials = GetCurrentPlacements(),
        ClassifierConfidence = lastClassifierResult.Confidence,
        PlacementHash = ComputePlacementHash()
    };

    GameEvents.RaiseItemGenerationStarted(discipline.ToString());
    var result = await generator.GenerateItemAsync(request);

    if (result.IsValid)
    {
        GameManager.Instance.Player.Inventory.AddItem(result.ItemId, 1);
        GameEvents.RaiseItemInvented(discipline.ToString(), result.ItemId, result.IsStub);
        NotificationSystem.Instance.Show($"Created: {result.ItemId}", NotificationType.Success);
    }

    GameEvents.RaiseItemGenerationCompleted(discipline.ToString(), result.IsValid);
}
```

### 7.3 GameManager Initialization Sequence

Verify the full initialization order in `GameManager.Awake()`:

```
1. SetBasePath(Application.streamingAssetsPath + "/Content")
2. Auto-wire manager references (new — FindFirstObjectByType)
3. DatabaseInitializer.InitializeAll()
4. TagRegistry.Instance.LoadDefinitions()
5. ClassifierManager.Instance.Initialize(new MockBackendFactory())
6. Create Character with spawn position
7. Initialize WorldSystem
8. Initialize CombatManager
9. Register GameEvents listeners
```

### 7.4 Save/Load → UI Integration

`SaveManager` exists. `StartMenuUI` has Load World and save slot UI. Verify:
- `StartMenuUI` calls `SaveManager.Instance.GetSaveSlots()` to list saves
- Load button calls `SaveManager.Instance.LoadGame(slotName)`
- Save button (or auto-save) calls `SaveManager.Instance.SaveGame(slotName)`
- `GameManager.LoadGame()` and `GameManager.SaveGame()` delegate correctly

---

## 8. Test Infrastructure

### 8.1 Current State

All 6 test files use a custom test runner — `static int RunAll()` with manual assert methods. No NUnit `[Test]` attributes. The tests are pure C# and don't need Unity to run.

### 8.2 Unity Test Runner Integration

To make tests visible in Unity's Test Runner window, create thin wrappers:

**File**: `Assets/Tests/EditMode/TestBridge.cs`

```csharp
using NUnit.Framework;

[TestFixture]
public class TestBridge
{
    [Test] public void ClassifierPreprocessorTests()
    {
        int failures = Game1.Tests.ClassifierPreprocessorTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} classifier tests failed");
    }

    [Test] public void StubItemGeneratorTests()
    {
        int failures = Game1.Tests.StubItemGeneratorTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} stub generator tests failed");
    }

    [Test] public void NotificationSystemTests()
    {
        int failures = Game1.Tests.NotificationSystemTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} notification tests failed");
    }

    [Test] public void LoadingStateTests()
    {
        int failures = Game1.Tests.LoadingStateTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} loading state tests failed");
    }

    [Test] public void EndToEndTests()
    {
        int failures = Game1.Tests.EndToEndTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} E2E tests failed");
    }

    [Test] public void LLMStubIntegrationTests()
    {
        int failures = Game1.Tests.LLMStubIntegrationTests.RunAll();
        Assert.AreEqual(0, failures, $"{failures} LLM integration tests failed");
    }
}
```

This wraps each test suite as a single NUnit test. Unity Test Runner will show 6 entries, each running the full suite internally.

### 8.3 Editor Menu Shortcut

**File**: `Assets/Editor/TestMenuItems.cs`

```csharp
[MenuItem("Game1/Tests/Run All Tests")]
public static void RunAllTests()
{
    int total = 0;
    total += ClassifierPreprocessorTests.RunAll();
    total += StubItemGeneratorTests.RunAll();
    // ... etc
    Debug.Log(total == 0 ? "ALL TESTS PASSED" : $"{total} TESTS FAILED");
}
```

### 8.4 New Tests to Write

**Priority 1 — Database Loading** (validates JSON pipeline):
- MaterialDatabase loads >50 materials
- EquipmentDatabase loads weapons and armor
- RecipeDatabase loads recipes for all 5 disciplines
- SkillDatabase loads >100 skills

**Priority 2 — Damage Formula** (validates Pillar 1: Exact Mechanical Fidelity):
- Base damage calculation
- STR multiplier: 1 + STR * 0.05
- Defense cap at 75%
- Critical hit 2x
- Hand type bonus (1H=1.1, 2H=1.2)

**Priority 3 — Crafting Pipeline** (validates end-to-end crafting):
- DifficultyCalculator tier boundaries
- RewardCalculator quality thresholds
- BaseCraftingMinigame performance scoring

---

## 9. Play-Test Readiness Checklist

### Milestone 1: Compiles Clean
- [ ] All 7 assembly definitions created
- [ ] All compilation errors fixed (zero errors in Console)
- [ ] Sentis references replaced with mocks
- [ ] All warnings reviewed (fix critical, suppress cosmetic)

### Milestone 2: Scene Runs
- [ ] Editor setup script created and executed
- [ ] Scene hierarchy matches Phase 6 specification
- [ ] GameManager.Awake() completes without errors
- [ ] All databases load from StreamingAssets/Content/
- [ ] Console shows database load counts (50+ materials, 100+ skills, etc.)

### Milestone 3: Core Loop Works
- [ ] Start menu appears
- [ ] Class selection works
- [ ] Player spawns on world tiles
- [ ] WASD movement works
- [ ] Camera follows player
- [ ] World chunks load/unload as player moves
- [ ] Resources appear on tiles

### Milestone 4: Systems Work
- [ ] Tab opens inventory
- [ ] E opens equipment
- [ ] Items can be gathered from resource nodes
- [ ] Items appear in inventory
- [ ] Equipment can be equipped/unequipped
- [ ] Crafting menu shows recipes
- [ ] At least 1 crafting minigame runs to completion
- [ ] Enemy spawns and can be fought
- [ ] Damage numbers appear
- [ ] Player can die and respawn
- [ ] EXP gained from kills
- [ ] Level up works
- [ ] Stat allocation works
- [ ] Save and load preserves state

### Milestone 5: All Systems Verified
- [ ] All 5 crafting minigames functional
- [ ] All F1-F7 debug keys work
- [ ] Map UI shows explored chunks
- [ ] Encyclopedia shows data from databases
- [ ] Title system awards titles
- [ ] Class affinity bonuses apply
- [ ] Status effects apply (burn, freeze, etc.)
- [ ] Enchantment effects work
- [ ] Potion system works
- [ ] Stub LLM item generation works via Invent button
- [ ] Notifications display
- [ ] Day/night cycle visible

### Milestone 6: Tests Pass
- [ ] All 6 existing test suites pass
- [ ] Database loading tests pass
- [ ] Damage formula tests pass

---

## 10. What's Deferred

These are explicitly out of scope for the prototype and will be addressed later:

| Item | Reason | When to Address |
|------|--------|----------------|
| Full LLM integration (AnthropicItemGenerator) | Requires Claude API HTTP client in C# | After prototype validates gameplay |
| Trained ML classifiers (ONNX models) | Requires Python ML environment to convert | After prototype validates classifier UI flow |
| Unity Sentis package | Only needed with real ONNX models | When ML classifiers are ready |
| Final sprite art | Colored shapes are sufficient for playtesting | Art production phase |
| Particle effects | ParticleEffects.cs exists but needs particle prefabs | Polish phase |
| Audio | AudioManager placeholder exists | Audio production phase |
| Polished UI layouts | Functional programmer art is sufficient | UI/UX polish phase |
| Performance optimization | Not needed at prototype scale | After content expansion |
| Mobile/console builds | PC prototype first | Platform phase |
| Multiplayer | Single-player prototype first | Architecture supports it via SaveManager |

---

## Implementation Order Summary

```
USER WORK (25-45 min, mostly waiting for downloads):
  Install Unity Hub + Editor → Create Project → Install 3 Packages
  → Copy C# Files → Copy JSON Data

CODE WORK (done by coding assistant, in this order):
  ├── [1] Assembly definitions (7 .asmdef files)
  ├── [2] Compilation fixes (iterative)
  │     ├── Fix using statements
  │     ├── Fix Unity API differences
  │     ├── Mock out Sentis (2 files)
  │     └── Fix any type mismatches
  ├── [3] GameManager self-wiring (FindFirstObjectByType fallbacks)
  ├── [4] Editor setup scripts
  │     ├── Scene hierarchy creator
  │     ├── Canvas UI creator
  │     ├── Config asset creator
  │     └── Reference auto-wirer
  ├── [5] Integration wiring
  │     ├── NotificationSystem → NotificationUI
  │     ├── IItemGenerator → CraftingUI
  │     └── Verify save/load pipeline
  ├── [6] Placeholder visuals
  │     ├── Verify fallback tiles work
  │     ├── Verify fallback sprites work
  │     ├── Placeholder player/enemy sprites
  │     └── Basic UI styling
  ├── [7] Test infrastructure
  │     ├── NUnit bridge wrappers
  │     ├── Editor test menu item
  │     └── Database loading tests
  └── [8] Play-test iteration
        ├── Press Play
        ├── Fix runtime errors
        ├── Verify core loop
        └── Walk through checklist
```

---

## Estimated Effort

| Phase | Effort | Description |
|-------|--------|-------------|
| User setup | 25-45 min | Install Unity, create project, copy files |
| Assembly definitions | 30 min | 7 JSON files |
| Compilation fixes | 2-4 hours | Iterative error fixing |
| Editor scripts | 2-3 hours | Scene creator, UI creator, auto-wirer |
| Integration wiring | 1-2 hours | Connect systems that aren't wired |
| Placeholder visuals | 1 hour | Verify fallbacks, add basic styling |
| Test infrastructure | 1 hour | NUnit bridges, database tests |
| Play-test iteration | 2-4 hours | Fix runtime issues, verify systems |
| **Total code work** | **~10-17 hours** | After user completes setup |

---

**Document Created**: 2026-02-16
**For**: Post-migration development from source files to playable prototype
**Prerequisite**: Completed migration (147 C# files, all 7 phases)
