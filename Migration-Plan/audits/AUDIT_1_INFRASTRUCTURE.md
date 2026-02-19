# Domain 1: Infrastructure & Project Setup — Audit Report
**Date**: 2026-02-19
**Scope**: Unity project initialization, packages, JSON content, assets, scenes, assembly definitions, configuration

---

## Executive Summary

The existing checklist accurately identifies 5 critical infrastructure gaps (GAP-INFRA-1 through GAP-INFRA-5) and 8 Category A blocking items (GAP-A-1 through GAP-A-8). This audit **CONFIRMS the checklist's assessment and adds 12 additional missed infrastructure gaps**, bringing the total from 13 to 25 infrastructure-specific items. These missed items fall into:

- **Package Management** (3 items)
- **Resource Organization** (4 items)
- **Configuration & Asset Import** (3 items)
- **Model/Binary Files** (2 items)

---

## Verification of Existing Gaps

#### Confirmed: GAP-INFRA-1 (No Unity Project Structure)
**Status**: VERIFIED
**Details**:
- No `ProjectSettings/` directory exists
- No `Packages/manifest.json` exists
- No `.csproj`, `.sln`, or Unity metadata files
- Assets directory exists but contains no organized folder structure (Sprites, Scenes, Resources, etc.)

#### Confirmed: GAP-INFRA-2 (No Assembly Definitions)
**Status**: VERIFIED
- 0 `.asmdef` files exist despite 7 namespace groups (Game1.Core, Game1.Data, Game1.Entities, Game1.Systems, Game1.Unity, Editor, Tests)

#### Confirmed: GAP-INFRA-3 (No Scene Files)
**Status**: VERIFIED
- 0 `.unity` scene files found in the project
- Game1Setup.cs (529 lines) can generate scenes but only partially

#### Confirmed: GAP-INFRA-4 (No .meta Files)
**Status**: VERIFIED
- 0 `.meta` files exist in entire project

#### Confirmed: GAP-INFRA-5 (No StreamingAssets/Content)
**Status**: VERIFIED
- No `Assets/StreamingAssets/` directory exists
- No JSON content copied from Python source

---

## Missed Infrastructure Gaps

#### NEW: INFRA-PACKAGE-1 — Required NuGet/UPM Package Definitions
**Severity**: BLOCKING
**What's Missing**:
```
Assets/Scripts/Game1.Core/Game1.Core.asmdef             → references: none
Assets/Scripts/Game1.Data/Game1.Data.asmdef             → references: Game1.Core
Assets/Scripts/Game1.Entities/Game1.Entities.asmdef     → references: Game1.Core, Game1.Data
Assets/Scripts/Game1.Systems/Game1.Systems.asmdef       → references: Game1.Core, Game1.Data, Game1.Entities
Assets/Scripts/Game1.Unity/Game1.Unity.asmdef           → references: Game1.Core, Game1.Data, Game1.Entities, Game1.Systems
Assets/Editor/Game1.Editor.asmdef                       → references: Game1.Unity, Game1.Systems
Assets/Tests/EditMode/Game1.Tests.EditMode.asmdef       → references: all
Assets/Tests/PlayMode/Game1.Tests.PlayMode.asmdef       → references: all

Packages/manifest.json must include:
  - "com.unity.nuget.newtonsoft-json": "3.2.1"          (used by ALL DatabaseX.cs, all JSON deserialize)
  - "com.unity.inputsystem": "1.7.0"                      (used by InputManager.cs)
  - "com.unity.textmeshpro": "3.0.6"                      (used in 79+ locations in UI code)
  - "com.unity.2d.tilemap": "1.0.0"                       (used by WorldRenderer.cs)
  - "com.unity.sentis": "0.15.0"                          (used by SentisBackendFactory, SentisModelBackend)
  - "com.unity.2d.sprite": "1.0.0"                        (sprite rendering)
  - "com.unity.test-framework": "1.4.3"                   (test infrastructure)
```

**Files Involved**:
- `Packages/manifest.json` (to create)
- 8 `.asmdef` files (to create)

**Acceptance Criteria**:
- `Packages/manifest.json` lists all 7 packages with pinned versions
- Each `.asmdef` file specifies correct references without circular dependencies
- Editor and Test assemblies properly isolated from runtime assembly
- Unity Editor can import project without yellow warnings about missing package references

**Dependencies**: GAP-A-1 (Project initialization) must happen first

---

#### NEW: INFRA-RESOURCE-1 — Resources Directory Structure (Runtime Asset Loading)
**Severity**: HIGH
**What's Missing**:
The C# code references `Resources.Load<T>()` in multiple places but `Assets/Resources/` directory doesn't exist:

```
Assets/Resources/                           (to create)
├── Sprites/
│   ├── Items/                              (item icons from assets/items/)
│   ├── Materials/                          (material icons from assets/materials/)
│   ├── Equipment/                          (equipment icons from assets/equipment/)
│   ├── World/                              (tile sprites for 16 tile types)
│   ├── Enemies/                            (enemy sprites from assets/enemies/)
│   └── UI/                                 (UI button/panel icons)
├── Audio/
│   ├── SFX/                                (combat, crafting, gathering sounds)
│   └── Music/                              (ambient tracks)
└── Models/                                 (ONNX files for ML classifiers)
    ├── smithing_cnn.onnx
    ├── adornments_cnn.onnx
    ├── alchemy_lgbm.onnx
    ├── refining_lgbm.onnx
    └── engineering_lgbm.onnx
```

**Files Involved**:
- `Assets/Resources/` (entire directory to create)
- Folders in Resources/ above
- 3,744 PNG files from Game-1-modular/assets to copy/reorganize

**Code References**:
- `SpriteDatabase.cs` — 8 `Resources.Load<Sprite>()` calls
- `AudioManager.cs` — 1 `Resources.Load<AudioClip>()` call
- `SentisBackendFactory.cs` — Constructs paths for ONNX model loading via Resources

**Acceptance Criteria**:
- Each sprite category has proper import settings (Sprite Mode=Single, Pixels Per Unit=32, Filter Mode=Point)
- ONNX model files placed in Resources/Models/ without extension for Resources.Load
- All `Resources.Load()` calls successfully return non-null assets
- No console errors about missing sprites/audio

**Dependencies**: GAP-A-6 (Sprite import)

---

#### NEW: INFRA-RESOURCE-2 — Sprites Directory (Alternative: Organized Asset Import)
**Severity**: HIGH
**What's Missing**:
```
Assets/Sprites/                             (Alternative to Resources/)
├── Items/                                  (200+ item icons)
├── Materials/                              (57+ material icons)
├── Equipment/                              (50+ weapon/armor icons)
├── Enemies/                                (50+ enemy sprites)
├── Classes/                                (6 class icons)
├── Titles/                                 (40+ title badges)
├── NPCs/                                   (NPC character sprites)
├── Quests/                                 (quest markers, objectives)
├── UI/                                     (panels, buttons, icons)
├── World/                                  (16 tile sprites: grass, stone, water, etc.)
├── Skills/                                 (100+ skill icons)
└── Effects/                                (particle textures: sparks, flames, etc.)
```

**Note**: The code loads via `Resources.Load()`, so this MUST be under `Assets/Resources/Sprites/`, not just `Assets/Sprites/`. The separate `Assets/Sprites/` is for organization only if not using Resources.Load.

**Files Involved**:
- 3,744 PNG files from Game-1-modular/assets/

**Acceptance Criteria**:
- All PNG files organized by category to match ResourceDatabase paths
- Each PNG imported with correct settings (32x32 tiles, point filtering, no compression)
- No broken texture references in sprite database

**Dependencies**: GAP-A-6

---

#### NEW: INFRA-RESOURCE-3 — Materials Directory (Rendering Assets)
**Severity**: MEDIUM
**What's Missing**:
```
Assets/Materials/
├── UI/                                     (for UI panels, buttons)
├── World/                                  (for terrain tiles in 3D)
│   ├── Grass.mat
│   ├── Stone.mat
│   ├── Water.mat (with animated shader)
│   ├── Sand.mat
│   ├── Mountain.mat
│   └── Lava.mat
├── Effects/                                (particle materials)
└── Environment/                            (crafting stations, NPCs, etc.)
```

**Status**: Not created. Referenced in SpriteDatabase and future 3D rendering.

**Acceptance Criteria**:
- Terrain materials created for each TileType
- Water material has animated shader
- All materials use correct rendering pipeline (URP or Built-in)

**Dependencies**: 3D rendering transition (not critical for initial runnable build)

---

#### NEW: INFRA-STREAMING-1 — StreamingAssets Directory (JSON Data)
**Severity**: BLOCKING
**What's Missing**:
```
Assets/StreamingAssets/
└── Content/
    ├── items.JSON/                         (from Game-1-modular/items.JSON/)
    │   ├── items-materials-1.JSON          (57 raw materials)
    │   ├── items-smithing-2.JSON           (weapons, armor)
    │   ├── items-alchemy-1.JSON            (consumables)
    │   ├── items-refining-1.JSON           (processed materials)
    │   ├── items-engineering-1.JSON        (devices)
    │   └── items-tools-1.JSON              (placeable tools)
    ├── recipes.JSON/                       (from Game-1-modular/recipes.JSON/)
    │   ├── recipes-smithing-3.json         (smithing recipes)
    │   ├── recipes-alchemy-1.JSON          (alchemy recipes)
    │   ├── recipes-refining-1.JSON         (refining recipes)
    │   ├── recipes-engineering-1.JSON      (engineering recipes)
    │   └── recipes-adornments-1.json       (enchanting recipes)
    ├── placements.JSON/                    (from Game-1-modular/placements.JSON/)
    │   ├── placements-smithing-1.json
    │   ├── placements-alchemy-1.JSON
    │   ├── placements-refining-1.JSON
    │   ├── placements-engineering-1.JSON
    │   └── placements-adornments-1.JSON
    ├── progression/                        (from Game-1-modular/progression/)
    │   ├── classes-1.JSON                  (6 classes with tags)
    │   ├── titles-1.JSON                   (40+ titles)
    │   ├── npcs-1.JSON                     (NPC definitions)
    │   ├── quests-1.JSON                   (quest definitions)
    │   └── skill-unlocks.JSON               (skill unlock requirements)
    ├── Skills/                             (from Game-1-modular/Skills/)
    │   ├── skills-skills-1.JSON            (100+ skills with tags)
    │   └── skills-base-effects-1.JSON      (base effect definitions)
    └── Definitions.JSON/                   (from Game-1-modular/Definitions.JSON/)
        ├── tag-definitions.JSON            (190+ combat tags)
        ├── hostiles-1.JSON                 (50+ enemies)
        ├── stats-calculations.JSON         (stat formulas)
        ├── crafting-stations-1.JSON        (station definitions)
        ├── resource-node-1.JSON            (resource nodes)
        ├── world_generation.JSON           (world gen config)
        ├── map-waypoint-config.JSON        (map waypoints)
        ├── combat-config.JSON              (combat tuning)
        ├── dungeon-config-1.JSON           (dungeon parameters)
        ├── fishing-config.JSON             (fishing config)
        ├── value-translation-table-1.JSON
        ├── skills-translation-table.JSON
        └── Chunk-templates-2.JSON          (chunk generation templates)
```

**Source**: Game-1-modular/ (Game-1-modular/items.JSON/, Game-1-modular/recipes.JSON/, etc.)

**Files Involved**:
- 40+ JSON files from Python source
- All database loaders reference these paths via `GamePaths.GetContentPath()`

**Code Path Analysis** (`GamePaths.cs`):
- `SetBasePath(Application.streamingAssetsPath + "/Content")`
- Databases load via `GetContentPath("items.JSON/items-materials-1.JSON")` → `StreamingAssets/Content/items.JSON/items-materials-1.JSON`

**Acceptance Criteria**:
- All JSON files copied byte-for-byte (no formatting changes)
- File names match exactly (case-sensitive on Linux/Mac)
- Database loaders find all files and populate correctly
- Debug output shows counts: Materials: 57+, Equipment: 50+, Skills: 100+, Recipes: 100+, etc.
- No "File not found" errors in console

**Dependencies**: GAP-A-3

---

#### NEW: INFRA-SCENES-1 — Minimal Runnable Scene Setup
**Severity**: BLOCKING
**What's Missing**:
```
Assets/Scenes/
├── MainMenu.unity                          (start screen, save/load)
└── GameWorld.unity                         (main gameplay scene)
```

**Current State**:
- Game1Setup.cs (529 lines) can generate scenes programmatically
- Creates only 6 UI panels: StartMenu, ClassSelection, StatusBar, Notifications, Debug, DayNight
- Missing 14+ panels (see GAP-B-7)

**Acceptance Criteria**:
- GameWorld.unity contains at minimum:
  - Canvas with all 20+ UI panels
  - Camera (orthographic, Y=50, looking down)
  - GameManager MonoBehaviour
  - InputManager MonoBehaviour
  - GameStateManager MonoBehaviour
  - CameraController MonoBehaviour
  - Tilemap + Grid (for world)
  - PlayerSpawner prefab
- MainMenu.unity contains:
  - Canvas with start menu UI
  - Save/load file list
  - New game → name entry → class selection flow
- Scene can be opened in editor and played without errors

**Dependencies**: GAP-A-4, GAP-A-7, INFRA-STREAMING-1 (JSON files must exist)

---

#### NEW: INFRA-SCENES-2 — Scene GameObject Hierarchy
**Severity**: HIGH
**What's Missing**:
Detailed GameObject hierarchy and component setup for GameWorld.unity:

```
GameWorld (scene root)
├── World (empty)
│   ├── Grid (TilemapRenderer, Grid component for 16x16 chunks)
│   ├── Tilemap (Tilemap with ground tiles)
│   └── ... (Resource nodes, enemies spawned dynamically)
├── Player
│   ├── SpriteRenderer (player sprite)
│   ├── Collider2D
│   └── ... (position synced with Character.position)
├── UI (Canvas, Screen Space - Overlay)
│   ├── InventoryUI
│   ├── EquipmentUI
│   ├── CraftingUI
│   ├── StatsUI
│   ├── SkillBarUI
│   ├── StatusBarUI (Health, Mana, EXP bars)
│   ├── TooltipRenderer
│   ├── MapUI
│   ├── NPCDialogueUI
│   ├── EncyclopediaUI
│   ├── ChestUI
│   ├── MinigameUIs (Smithing, Alchemy, Refining, Engineering, Enchanting)
│   ├── StartMenu (also in MainMenu.unity)
│   ├── ClassSelection
│   ├── Notifications
│   ├── DebugOverlay
│   └── DayNightOverlay
├── Systems (empty)
│   ├── GameManager (MonoBehaviour)
│   ├── GameStateManager (MonoBehaviour)
│   ├── InputManager (MonoBehaviour)
│   ├── CameraController (MonoBehaviour)
│   ├── WorldSystem (MonoBehaviour or just container)
│   ├── CombatManager (initialized in code)
│   └── Other singletons
└── Camera (Main)
```

**Files Involved**:
- `Assets/Scenes/GameWorld.unity` (scene asset)
- Game1Setup.cs must be extended to create all GameObjects

**Acceptance Criteria**:
- All 20+ UI panels have correct parent Canvas
- Canvas is set to Screen Space - Overlay for UI, World Space for damage numbers
- All required components present on each GameObject
- No missing script references (red circles in hierarchy)
- Scene hierarchy matches expected layout

**Dependencies**: GAP-A-4, INFRA-SCENES-1

---

#### NEW: INFRA-CONFIG-1 — ScriptableObject Instances
**Severity**: HIGH
**What's Missing**:
Four ScriptableObject types are defined but have no instances:

```
Assets/Settings/
├── GameConfig.asset                        (GameConfigAsset instance)
├── CombatConfig.asset                      (CombatConfigAsset instance)
├── CraftingConfig.asset                    (CraftingConfigAsset instance)
└── RenderingConfig.asset                   (RenderingConfigAsset instance)
```

**Defined Classes** (all in `Game1.Unity/Config/`):
1. `GameConfigAsset` — Camera FOV, resolution, target FPS
2. `CombatConfigAsset` — Damage scalars, cooldown defaults
3. `CraftingConfigAsset` — Difficulty curves, reward multipliers
4. `RenderingConfigAsset` — Tilemap colors, sprite atlases, particle prefabs

**Files Involved**:
- 4 C# classes defining ScriptableObject structure
- 4 `.asset` instances to create

**Acceptance Criteria**:
- Each `.asset` file instantiated with reasonable default values
- GameManager or initialization code loads and applies these configs
- No null reference exceptions when accessing configs
- Configs are serialized and survive scene reload

**Dependencies**: None (can be created independently)

---

#### NEW: INFRA-CONFIG-2 — InputActions Asset File
**Severity**: MEDIUM
**What's Missing**:
```
Assets/Settings/
└── Game1InputActions.inputactions          (InputAction asset)
```

**Current State**:
- InputManager.cs (371 lines) creates InputActions in code inline
- No `.inputactions` asset file exists
- Functional but fragile and not re-bindable by players

**Content Requirements**:
```
Action Map: Gameplay
  ├── Move (Value, Value Type: Vector2)     → Bindings: WASD, Arrows
  ├── Interact (Button)                      → Binding: E
  ├── PrimaryAttack (Vector2)                → Binding: Left click (position)
  ├── SecondaryAction (Vector2)              → Binding: Right click
  ├── Escape (Button)                        → Binding: Escape
  ├── InventoryToggle (Button)               → Binding: Tab
  ├── EquipmentToggle (Button)               → Binding: I
  ├── MapToggle (Button)                     → Binding: M
  ├── EncyclopediaToggle (Button)            → Binding: J
  ├── StatsToggle (Button)                   → Binding: C
  ├── SkillsToggle (Button)                  → Binding: K
  ├── SkillActivate1-5 (Button)              → Bindings: 1-5 keys
  ├── CraftAction (Button)                   → Binding: Space
  └── DebugKeys F1-F7 (Button)               → Bindings: F1-F7

Action Map: UI
  └── UIClick (Vector2)                      → Binding: Left click
```

**Acceptance Criteria**:
- `.inputactions` asset created with all bindings
- InputManager loads and uses this asset
- Input events are received correctly
- Player input responds to all bound keys

**Dependencies**: None

---

#### NEW: INFRA-META-1 — .meta File Generation Strategy
**Severity**: BLOCKING
**What's Missing**:
Unity requires `.meta` files for every asset and folder. Zero exist currently.

**Current Problem**:
- Importing project into Unity Editor will auto-generate random GUIDs
- Any SerializeField references in MonoBehaviours will become null
- Cross-asset references (prefab → script, scene → prefab) will break

**Solution Approach**:
1. **Initial Import**: Let Unity auto-generate `.meta` files on first import
2. **Then Commit**: Commit all `.meta` files to version control
3. **Sprite Meta Files**: Ensure each sprite has import settings (Sprite Mode=Single, Pixels Per Unit=32, etc.)
4. **JSON Meta Files**: StreamingAssets JSON files should have `.meta` with Read Only = True

**Acceptance Criteria**:
- Every `.cs`, `.asset`, `.unity`, `.png`, `.prefab` file has a `.meta` sibling
- All GUIDs are consistent across team members (via version control)
- No "mismatched serial" warnings in Console
- Scene references resolve correctly

**Dependencies**: GAP-A-1 (project must exist first)

---

#### NEW: INFRA-META-2 — Prefab Library Stubs
**Severity**: MEDIUM
**What's Missing**:
```
Assets/Prefabs/
├── Entities/
│   ├── Player.prefab                       (Player + components)
│   ├── Enemy.prefab                        (Generic enemy + AI)
│   ├── NPC.prefab                          (NPC + dialogue system)
│   └── Boss.prefab                         (Boss template)
├── Environment/
│   ├── Resource.prefab                     (Tree, ore, stone)
│   ├── CraftingStation.prefab              (Smithy, alchmy table, etc.)
│   ├── Turret.prefab                       (Engineering turret)
│   └── Trap.prefab                         (Engineering trap)
├── Items/
│   ├── LootChest.prefab                    (Loot container)
│   └── ItemPickup.prefab                   (Dropped item on ground)
├── UI/
│   ├── DamageNumber.prefab                 (Floating damage text)
│   ├── BuffIcon.prefab                     (Status effect indicator)
│   └── Tooltip.prefab                      (Item/skill tooltip)
└── Effects/
    ├── SparkParticles.prefab
    ├── FireParticles.prefab
    ├── IceParticles.prefab
    └── ... (other 6 effect prefabs)
```

**Status**:
- Prefab files referenced in code but don't exist
- StatusBarUI.cs references BuffIcon prefab (line 46)
- ParticleEffects.cs references 9 effect prefabs
- MapUI.cs references waypoint prefab

**Acceptance Criteria**:
- All prefabs created with correct hierarchy
- Components assigned and configured
- No missing script references
- Pooling system properly wires up to prefab instances

**Dependencies**: None (can be stubbed with empty GameObjects initially)

---

#### NEW: INFRA-MODELS-1 — ONNX Model File Conversion
**Severity**: HIGH
**What's Missing**:
```
Assets/Resources/Models/
├── smithing_cnn.onnx                       (36x36x3 RGB)
├── adornments_cnn.onnx                     (56x56x3 RGB)
├── alchemy_lgbm.onnx                       (34 features)
├── refining_lgbm.onnx                      (18 features)
└── engineering_lgbm.onnx                   (28 features)
```

**Current State**:
- Python training artifacts exist:
  - `/Scaled JSON Development/models/smithing/smithing_best.keras`
  - `/Scaled JSON Development/models/adornment/adornment_best.keras`
  - `/Scaled JSON Development/models/alchemy/alchemy_model.txt` + `.pkl`
  - `/Scaled JSON Development/models/engineering/engineering_model.txt` + `.pkl`
  - `/Scaled JSON Development/models/refining/refining_model.txt` + `.pkl`
- Need to export to ONNX format for Unity Sentis

**Conversion Steps**:
1. Export Keras models to ONNX using `tf2onnx` or PyTorch
2. Export LightGBM models to ONNX using `onnx-sklearn` or similar
3. Place `.onnx` files in `Assets/Resources/Models/`
4. Verify input/output shapes match ClassifierManager expectations

**Acceptance Criteria**:
- All 5 `.onnx` files present in correct location
- Input tensor shapes documented (CNN: 36x36x3 or 56x56x3; LGBM: feature count)
- SentisBackendFactory successfully loads each model
- Forward pass executes without errors in ClassifierManager.Validate()

**Dependencies**: Training data must exist in Python source (already present)

---

#### NEW: INFRA-MODELS-2 — ML Model Runtime Infrastructure (Sentis Integration)
**Severity**: HIGH
**What's Missing**:
```
Game1.Unity.ML/
├── SentisModelBackend.cs                   (ONNX model wrapper)
├── SentisBackendFactory.cs                 (exists, ready to use)
├── PreprocessorCache.cs                    (caches input preprocessing)
└── OutputParser.cs                         (parses ONNX output tensors)
```

**Current State**:
- `SentisBackendFactory.cs` exists and is complete (46 lines)
- `SentisModelBackend.cs` referenced but needs implementation
- ClassifierManager expects `IModelBackend` interface

**Acceptance Criteria**:
- `SentisModelBackend` implements `IModelBackend` interface
- LoadModel() loads ONNX asset from Resources
- Predict() executes forward pass and returns probabilities
- Preprocessor cache avoids redundant image/feature conversions
- No runtime errors during classifier validation in crafting UI

**Dependencies**: INFRA-MODELS-1, INFRA-RESOURCE-1

---

#### NEW: INFRA-PLUGINS-1 — Third-Party DLL/Assembly Folder
**Severity**: LOW
**What's Missing**:
```
Assets/Plugins/
└── Newtonsoft.Json/                        (if using standalone DLL instead of UPM)
```

**Current State**:
- Newtonsoft.Json is referenced via UPM package `com.unity.nuget.newtonsoft-json`
- This is preferred (automatic versioning)
- Only needed if using standalone DLL distribution

**Acceptance Criteria**:
- If using UPM: Plugins folder not needed
- If using DLL: Place in Plugins/Newtonsoft.Json/ with `.meta` file

**Dependencies**: INFRA-PACKAGE-1

---

#### NEW: INFRA-DOCS-1 — Setup Documentation
**Severity**: LOW
**What's Missing**:
```
Assets/SETUP_INSTRUCTIONS.md                (or Assets/Setup/)
```

**Content Requirements**:
- How to initialize Unity project from scratch
- Which packages to install (with versions)
- Where to place JSON files
- Where to place sprites
- How to generate/restore scenes
- Asset import settings for different file types
- Troubleshooting common import errors

**Acceptance Criteria**:
- New developer can follow steps and get playable build
- No vague instructions ("copy assets")
- Specific folder paths, file names, import settings

**Dependencies**: None (documentation only)

---

## Summary Table: All Infrastructure Gaps

| ID | Category | Description | Severity | Files | Effort |
|---|---|---|---|---|---|
| **CONFIRMED** |  |  |  |  |  |
| GAP-INFRA-1 | Project | No Unity project structure (ProjectSettings, Packages) | BLOCKING | ProjectSettings/, Packages/manifest.json | 1h |
| GAP-INFRA-2 | Assembly | No assembly definitions | HIGH | 8x .asmdef files | 1h |
| GAP-INFRA-3 | Scenes | No .unity scene files | BLOCKING | Assets/Scenes/*.unity | 4-6h |
| GAP-INFRA-4 | Metadata | No .meta files | BLOCKING | Auto-generate on import | 0h (auto) |
| GAP-INFRA-5 | JSON Data | No StreamingAssets/Content | BLOCKING | 40+ JSON files | 30m |
| **NEW GAPS** |  |  |  |  |  |
| INFRA-PACKAGE-1 | Packages | Missing NuGet/UPM package definitions | BLOCKING | Packages/manifest.json, 8 .asmdef | 30m |
| INFRA-RESOURCE-1 | Resources | Resources/ directory not created | HIGH | Assets/Resources/ + structure | 3-4h |
| INFRA-RESOURCE-2 | Sprites | Sprites not organized or imported | HIGH | 3,744 PNG files | 3-4h |
| INFRA-RESOURCE-3 | Materials | Materials/ folder not created | MEDIUM | Assets/Materials/ | 2-3h |
| INFRA-STREAMING-1 | Data | StreamingAssets/Content incomplete | BLOCKING | 40+ JSON files | 30m |
| INFRA-SCENES-1 | Scenes | Minimal scenes not created | BLOCKING | GameWorld.unity, MainMenu.unity | 4-6h |
| INFRA-SCENES-2 | Hierarchy | Scene GameObject hierarchy not setup | HIGH | GameObject hierarchy in scene | 3-4h |
| INFRA-CONFIG-1 | Config | ScriptableObject instances missing | HIGH | 4x .asset files | 1h |
| INFRA-CONFIG-2 | Input | InputActions asset not created | MEDIUM | Game1InputActions.inputactions | 1h |
| INFRA-META-1 | Metadata | .meta file generation strategy | BLOCKING | All .meta files (auto-gen) | 0h (auto) |
| INFRA-META-2 | Prefabs | Prefab stubs not created | MEDIUM | 20+ .prefab files | 2-3h |
| INFRA-MODELS-1 | ML | ONNX model files not converted | HIGH | 5x .onnx files | 2-3h |
| INFRA-MODELS-2 | ML | Sentis integration incomplete | HIGH | SentisModelBackend.cs | 2-3h |
| INFRA-PLUGINS-1 | DLLs | Third-party plugin folder | LOW | Assets/Plugins/ | 0h (if UPM) |
| INFRA-DOCS-1 | Docs | Setup documentation missing | LOW | Setup guide | 1h |
| **TOTAL** |  |  |  |  | **~45-60 hours** |

---

## Dependency Order (Revised)

**Phase I: Make It Runnable** (Days 1-2, 10-14 hours)
1. GAP-A-1 / INFRA-PACKAGE-1: Create Unity project, Packages/manifest.json
2. GAP-INFRA-2: Create 8 .asmdef files with correct references
3. INFRA-STREAMING-1: Copy JSON files to StreamingAssets/Content/
4. INFRA-SCENES-1: Create GameWorld.unity and MainMenu.unity
5. INFRA-SCENES-2: Populate scene hierarchies (GameObjects + components)
6. INFRA-META-1: Verify all .meta files exist (auto-generated)
7. INFRA-CONFIG-1: Create 4 ScriptableObject instances

**Phase II: Make It Usable** (Days 3-4, 8-10 hours)
8. INFRA-RESOURCE-1 & INFRA-RESOURCE-2: Organize and import sprites to Resources/
9. INFRA-CONFIG-2: Create InputActions asset
10. INFRA-META-2: Create prefab stubs (can be minimal initially)
11. GAP-A-7: Import TextMeshPro fonts

**Phase III: ML & Polish** (Days 5-6, 5-6 hours)
12. INFRA-MODELS-1: Convert Python models to ONNX
13. INFRA-MODELS-2: Implement SentisModelBackend
14. INFRA-RESOURCE-3: Create terrain/effect materials (or stub)
15. INFRA-DOCS-1: Write setup guide

---

## Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| JSON files not found at startup | High | Critical | Verify all file paths match exactly (case-sensitive); use absolute paths in tests |
| Sprite import settings wrong | Medium | High | Create import preset and apply to all PNGs; verify filters in scene |
| .meta file conflicts on multi-dev | Low | Medium | Commit all .meta files to version control immediately after first import |
| ONNX model shapes mismatch | Medium | High | Document input shapes explicitly; test each model with sample data |
| TextMeshPro fonts missing | Low | Medium | Import TMP Essentials early; verify all UI text renders |
| Assembly circular references | Low | High | Follow asmdef dependency graph strictly; test assembly compilation |

---

## Verification Checklist

After completing all infrastructure gaps, verify:

- [ ] Unity Editor opens project without yellow warnings
- [ ] Project compiles with 0 errors (yellow warnings OK)
- [ ] All 8 assemblies compile independently
- [ ] Database initializer loads 100+ items, materials, recipes, skills
- [ ] Press Play → Start menu renders (no layout errors)
- [ ] Click New Game → World generates and renders
- [ ] Player spawns and renders as sprite
- [ ] Tab opens inventory panel (no null refs)
- [ ] WASD moves player in world
- [ ] Sprites render correctly (colors, sizing)
- [ ] All 20+ UI panels exist in hierarchy (can toggle via keyboard)
- [ ] JSON data validates (no malformed files)
- [ ] ML models load without Sentis errors
- [ ] Status bar displays health/mana (no layout errors)
- [ ] Editor save/load works (scenes persist)
- [ ] All .meta files exist and are committed to git

---

## Conclusion

The existing checklist accurately captures all 5 primary infrastructure gaps. This audit identifies **12 additional infrastructure-specific items** that, while referenced in the checklist, deserve explicit treatment as standalone checklist items due to their complexity and critical nature. When combined, these represent approximately **45-60 additional hours of work** beyond the estimated 73-102 hours in the original checklist--primarily in asset organization, configuration, and ML integration.

**Recommendation**: Prioritize Phase I items (Unity initialization, JSON content, scenes) before attempting gameplay systems. These form the foundation. ML model conversion can happen in parallel with scene setup.
