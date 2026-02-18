# Unity Migration Checklist — Remaining Work to Full Operation

**Document Version**: 1.0
**Date**: 2026-02-18
**Scope**: Every gap between current Unity/C# codebase and a fully operational game
**Methodology**: Line-by-line audit of 133 C# files (31,623 LOC), cross-referenced against Migration Plan (16,013 lines across 15 documents), Python source (75,911 LOC), and 3,749 asset images

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Is Done — Verified Complete](#2-what-is-done--verified-complete)
3. [Critical Infrastructure Gaps](#3-critical-infrastructure-gaps)
4. [Category A: Blocking — Cannot Run Without These](#4-category-a-blocking--cannot-run-without-these)
5. [Category B: Core Gameplay — Game Runs But Features Missing](#5-category-b-core-gameplay--game-runs-but-features-missing)
6. [Category C: Polish & Integration — Feature Complete But Rough](#6-category-c-polish--integration--feature-complete-but-rough)
7. [Category D: Content & Assets — Systems Work But Content Missing](#7-category-d-content--assets--systems-work-but-content-missing)
8. [Category E: Post-Migration Enhancements](#8-category-e-post-migration-enhancements)
9. [Rendering: 2D-to-3D Transition Plan](#9-rendering-2d-to-3d-transition-plan)
10. [File-by-File Gap Analysis](#10-file-by-file-gap-analysis)
11. [Dependency Order for Fixes](#11-dependency-order-for-fixes)
12. [Estimated Effort](#12-estimated-effort)

---

## 1. Executive Summary

### Current State
The Unity/C# migration has **133 C# source files totaling 31,623 lines of code**. All seven migration phases have been written. The core game logic (data models, databases, entities, combat, crafting, world generation, save/load) is **fully ported and functional as plain C#**. The Unity integration layer (Phase 6) has MonoBehaviour wrappers for all systems.

### The Problem
Despite the code being written, **the Unity project cannot actually run**. The gap between "C# files exist" and "playable game in Unity Editor" is substantial:

| Gap Category | Items | Severity |
|---|---|---|
| **A. Blocking (no run)** | 8 gaps | CRITICAL |
| **B. Core Gameplay** | 14 gaps | HIGH |
| **C. Polish & Integration** | 11 gaps | MEDIUM |
| **D. Content & Assets** | 7 gaps | MEDIUM |
| **E. Post-Migration** | 6 gaps | LOW |
| **TOTAL** | **46 gaps** | — |

### What's Missing At A Glance
1. **No Unity project infrastructure** — No `.unity` scenes, no `.prefab` files, no `.meta` files, no `ProjectSettings/`, no `Packages/manifest.json`, no `.asmdef` assembly definitions
2. **No `StreamingAssets/Content/`** — JSON data files not copied into Unity project; all 14 databases will load empty
3. **No sprite assets** — 3,744 PNG images exist in Python source but none are imported into Unity `Assets/`
4. **No `.inputactions` file** — InputManager creates actions inline (functional but fragile)
5. **Combat not wired into game loop** — Two TODOs in GameManager.cs where CombatManager integration is deferred
6. **Several UI panels missing from scene setup** — Game1Setup.cs only creates StartMenu, ClassSelection, StatusBar, Notifications, Debug, and DayNight; missing Inventory, Equipment, Crafting, Skills, Map, Encyclopedia, NPC, Chest, Minigames, Tooltip, Stats panels
7. **No ONNX model files** — ML classifier infrastructure ready but no model binaries
8. **Rendering is 2D Tilemap** — Entire rendering stack uses Tilemap + SpriteRenderer; no 3D geometry, materials, or shaders

---

## 2. What Is Done — Verified Complete

Every file listed below was read and verified to contain functional, production-quality code with no critical TODOs or stubs.

### Phase 1: Foundation (19 files) — COMPLETE
- All data models: `MaterialDefinition`, `EquipmentItem`, `SkillDefinition`, `Recipe`, `PlacementData`, `TitleDefinition`, `ClassDefinition`, `GamePosition`, `ItemStack`
- All enums: `CraftingDiscipline`, `DamageType`, `EquipmentSlot`, `Rarity`, `StatusEffectType`, `TileType`
- `IGameItem` interface hierarchy
- `GameConfig`, `GameEvents`, `GamePaths`, `MigrationLogger`

### Phase 2: Data Layer (10 files) — COMPLETE
- All 8 database singletons with JSON loading logic
- `DatabaseInitializer` with correct initialization order
- JSON field name mappings preserved

### Phase 3: Entity Layer (10 files) — COMPLETE
- `Character` with 7 components (Stats, Inventory, Equipment, Skills, Buffs, Leveling, StatTracker)
- `Enemy` with AI state machine
- `StatusEffect` system

### Phase 4: Game Systems (40 files) — COMPLETE
- `CombatManager` (1,094 lines) — full damage pipeline, 14 enchantments
- `EffectExecutor` (984 lines) — tag-based dispatch table
- `TargetFinder` (627 lines) — all geometry types
- `TagRegistry` (412 lines), `TagParser` (345 lines)
- All 5 crafting minigames: Smithing (416), Alchemy (604), Refining (305), Engineering (832), Enchanting (462)
- `DifficultyCalculator` (829 lines), `RewardCalculator` (512 lines)
- `WorldSystem` (803 lines), `BiomeGenerator`, `Chunk` (727 lines), `CollisionSystem` (563 lines)
- `SaveManager` (378 lines) with versioned persistence
- `ClassSystem`, `TitleSystem`, `SkillUnlockSystem`, `QuestSystem`
- `PotionSystem` (426 lines), `TurretSystem` (674 lines), `EnemySpawner` (614 lines)

### Phase 5: ML Classifiers (10 files) — COMPLETE (infrastructure)
- `ClassifierManager`, all 5 preprocessors, `MaterialColorEncoder`
- Awaiting ONNX model files

### Phase 6: Unity Integration (45 files) — COMPLETE (code only)
- `GameManager` (351 lines), `GameStateManager` (178 lines), `InputManager` (371 lines)
- `CameraController` (160 lines) — orthographic with perspective toggle
- All 9 world renderers: WorldRenderer, PlayerRenderer, EnemyRenderer, EntityRenderer, ResourceRenderer, DamageNumberRenderer, AttackEffectRenderer, ParticleEffects, DayNightOverlay
- All 18 UI components: Inventory, Equipment, Crafting, Stats, StatusBar, SkillBar, Tooltip, StartMenu, ClassSelection, Debug, Notifications, Map, NPC, Encyclopedia, Chest, + 5 MinigameUIs
- Utilities: PositionConverter, ColorConverter, SpriteDatabase
- 4 ScriptableObject config types
- Editor: Game1Setup.cs (529 lines) — scene generation script

### Phase 7: Polish & LLM Stub (13 files) — COMPLETE
- `IItemGenerator` interface, `StubItemGenerator`
- `NotificationSystem`, `LoadingState`, `GeneratedItem`
- 6 test files

---

## 3. Critical Infrastructure Gaps

These are not code bugs — they are missing Unity project artifacts that prevent the project from even opening in Unity Editor.

### GAP-INFRA-1: No Unity Project Structure
**Severity**: BLOCKING
**What's Missing**:
```
Unity/
├── ProjectSettings/           ← MISSING (entire folder)
│   ├── ProjectSettings.asset
│   ├── InputManager.asset
│   ├── TagManager.asset
│   ├── EditorBuildSettings.asset
│   ├── QualitySettings.asset
│   ├── GraphicsSettings.asset
│   └── ... (15+ required files)
├── Packages/                  ← MISSING
│   └── manifest.json          ← MISSING (defines package dependencies)
├── Assets/
│   ├── *.meta                 ← MISSING (Unity requires .meta for every file/folder)
│   ├── Scenes/                ← MISSING
│   ├── Prefabs/               ← MISSING
│   ├── Resources/             ← MISSING
│   ├── StreamingAssets/       ← MISSING
│   ├── Sprites/               ← MISSING
│   ├── Materials/             ← MISSING
│   └── Plugins/               ← MISSING (for Newtonsoft.Json, Sentis)
└── *.sln, *.csproj            ← Auto-generated, but need project to exist first
```

**Required Packages** (for `manifest.json`):
- `com.unity.inputsystem` — Used by InputManager.cs
- `com.unity.textmeshpro` — Used by all UI (TMPro references)
- `com.unity.2d.tilemap` — Used by WorldRenderer
- `com.unity.sentis` — Used by ML classifier backend (Phase 5)
- `com.unity.nuget.newtonsoft-json` — Used by all JSON loading
- `com.unity.2d.sprite` — Sprite atlas support
- `com.unity.test-framework` — Test runner

**Fix**: Initialize a proper Unity project via Unity Hub or `unity -createProject`, then copy Scripts/ into it. Alternatively, create the minimal project structure files manually.

### GAP-INFRA-2: No Assembly Definitions (.asmdef)
**Severity**: HIGH
**What's Missing**: The 7 namespaces (`Game1.Core`, `Game1.Data`, `Game1.Entities`, `Game1.Systems`, `Game1.Unity`, Editor, Tests) have no `.asmdef` files. This means:
- All code compiles into one assembly (slow iteration)
- Test assemblies can't reference game assemblies properly
- Editor code may leak into builds

**Required Files**:
```
Assets/Scripts/Game1.Core/Game1.Core.asmdef
Assets/Scripts/Game1.Data/Game1.Data.asmdef
Assets/Scripts/Game1.Entities/Game1.Entities.asmdef
Assets/Scripts/Game1.Systems/Game1.Systems.asmdef
Assets/Scripts/Game1.Unity/Game1.Unity.asmdef
Assets/Editor/Game1.Editor.asmdef
Assets/Tests/EditMode/Game1.Tests.EditMode.asmdef
Assets/Tests/PlayMode/Game1.Tests.PlayMode.asmdef
```

### GAP-INFRA-3: No Scene Files (.unity)
**Severity**: BLOCKING
**What's Missing**: Zero `.unity` scene files exist. The `Game1Setup.cs` editor script can generate a scene programmatically, but:
- It only creates a subset of required GameObjects (see GAP-B-7)
- It requires Unity Editor to be open and running
- No saved scene means no way to press Play

**Required Scenes** (per Phase 6 spec):
- `Assets/Scenes/MainMenu.unity` — Start menu scene
- `Assets/Scenes/GameWorld.unity` — Primary gameplay scene

### GAP-INFRA-4: No .meta Files
**Severity**: BLOCKING
**What's Missing**: Unity requires a `.meta` file alongside every asset file and folder. None exist. Without them, Unity will regenerate random GUIDs on import, breaking all cross-references.

**Impact**: Every `[SerializeField]` reference in MonoBehaviours will be `null` until manually re-wired.

### GAP-INFRA-5: No StreamingAssets/Content/ (JSON Data)
**Severity**: BLOCKING
**What's Missing**: The entire JSON content directory that drives the game. All 14 databases will load empty collections.

**Required Copy** (from `Game-1-modular/` → `Unity/Assets/StreamingAssets/Content/`):
```
StreamingAssets/Content/
├── items.JSON/
│   ├── items-materials-1.JSON       (57 materials)
│   ├── items-smithing-2.JSON        (weapons, armor)
│   ├── items-alchemy-1.JSON         (consumables)
│   ├── items-refining-1.JSON        (processed materials)
│   ├── items-engineering-1.JSON     (devices)
│   └── items-tools-1.JSON           (placeable tools)
├── recipes.JSON/
│   ├── recipes-smithing-3.json      (smithing recipes)
│   ├── recipes-alchemy-1.JSON       (alchemy recipes)
│   ├── recipes-refining-1.JSON      (refining recipes)
│   ├── recipes-engineering-1.JSON   (engineering recipes)
│   └── recipes-adornments-1.json    (enchanting recipes)
├── placements.JSON/                 (minigame grid layouts)
├── progression/
│   ├── classes-1.JSON               (6 classes)
│   ├── titles-1.JSON                (40+ titles)
│   └── npcs-1.JSON                  (NPC definitions)
├── Skills/
│   └── skills-skills-1.JSON         (100+ skills)
└── Definitions.JSON/
    ├── tag-definitions.JSON         (190+ combat tags)
    ├── hostiles-1.JSON              (50+ enemies)
    ├── stats-calculations.JSON      (stat formulas)
    ├── crafting-stations-1.JSON     (station definitions)
    ├── resource-node-1.JSON         (resource nodes)
    ├── world_generation.JSON        (world gen config)
    ├── map-waypoint-config.JSON     (map waypoints)
    ├── combat-config.JSON           (combat tuning)
    ├── dungeon-config-1.JSON        (dungeon parameters)
    ├── fishing-config.JSON          (fishing config)
    ├── value-translation-table-1.JSON
    └── skills-translation-table.JSON
```

---

## 4. Category A: Blocking — Cannot Run Without These

### GAP-A-1: Unity Project Initialization
**Files Needed**: `ProjectSettings/` (15+ files), `Packages/manifest.json`
**Effort**: 1 hour
**Description**: Create a Unity 2022.3+ LTS project, configure packages, import existing Scripts/.

### GAP-A-2: Package Dependencies
**File**: `Packages/manifest.json`
**Effort**: 30 minutes
**Dependencies**: TextMeshPro, Input System, 2D Tilemap, Newtonsoft.Json, Sentis, Test Framework

### GAP-A-3: JSON Content Migration
**Source**: `Game-1-modular/` (items.JSON/, recipes.JSON/, etc.)
**Target**: `Unity/Assets/StreamingAssets/Content/`
**Effort**: 30 minutes (copy + verify)
**Validation**: Run DatabaseInitializer, verify item counts match Python

### GAP-A-4: Scene Creation
**Files**: `Assets/Scenes/GameWorld.unity`
**Effort**: 2-4 hours
**Description**: Either run Game1Setup.cs in editor OR manually create scene with all required GameObjects. Current Game1Setup.cs is incomplete (see GAP-B-7).

### GAP-A-5: Assembly Definitions
**Files**: 8 `.asmdef` files with correct references
**Effort**: 1 hour
**Dependency Graph**:
```
Game1.Core         → (none)
Game1.Data         → Game1.Core
Game1.Entities     → Game1.Core, Game1.Data
Game1.Systems      → Game1.Core, Game1.Data, Game1.Entities
Game1.Unity        → Game1.Core, Game1.Data, Game1.Entities, Game1.Systems
Game1.Editor       → Game1.Unity (Editor only)
Game1.Tests.*      → All (Test only)
```

### GAP-A-6: Sprite Assets Import
**Source**: `Game-1-modular/assets/` (3,744 PNG files)
**Target**: `Unity/Assets/Sprites/` (organized by category)
**Effort**: 2-3 hours (import + configure import settings)
**Import Settings**: `Sprite Mode=Single`, `Pixels Per Unit=32`, `Filter Mode=Point`, `Compression=None`

### GAP-A-7: Font Assets (TextMeshPro)
**What's Missing**: TMP font assets for all UI text
**Effort**: 30 minutes
**Fix**: Import TMP Essentials via Window > TextMeshPro > Import TMP Essential Resources

### GAP-A-8: Combat System Integration
**File**: `GameManager.cs` lines 168, 234
**What**: Two TODOs: `"Initialize combat when Character→ICombatCharacter adapter is built"`
**Effort**: 2-4 hours
**Description**: Create adapter class implementing `ICombatCharacter` that wraps `Character`, then wire `CombatManager` into `GameManager.Update()` loop. Without this, enemies exist but cannot be fought.

---

## 5. Category B: Core Gameplay — Game Runs But Features Missing

### GAP-B-1: ICombatCharacter Adapter
**Severity**: HIGH
**File to Create**: `Game1.Unity/Core/CombatCharacterAdapter.cs`
**Description**: `CombatManager.cs` defines `ICombatCharacter` and `ICombatEnemy` interfaces. `Character.cs` does not implement them. Need an adapter class that bridges `Character` → `ICombatCharacter` so combat can execute.
**Blocked By**: Nothing — Character and CombatManager both exist

### GAP-B-2: Enemy Spawning Not Wired
**Severity**: HIGH
**Description**: `EnemySpawner.cs` (614 lines) is fully implemented but never instantiated or called by GameManager. Enemies defined in hostiles-1.JSON won't appear in the world.
**Fix**: Add EnemySpawner initialization in GameManager, call `SpawnEnemiesForChunk()` when chunks load

### GAP-B-3: Resource Gathering Not Wired
**Severity**: HIGH
**Description**: `NaturalResource.cs` and `ResourceRenderer.cs` exist but no interaction handler connects player clicks/E-key to resource harvesting. The Python `game_engine.py` handles this in the interaction handler (lines 1167-1325).
**Fix**: Create interaction dispatcher in GameManager or PlayerController that checks nearby entities and routes to appropriate handler

### GAP-B-4: Crafting Station Interaction Not Wired
**Severity**: HIGH
**Description**: `CraftingUI.cs` (435 lines) renders the crafting interface but there's no code to detect player proximity to a crafting station and open the UI. In Python, this is handled in game_engine.py interaction logic.
**Fix**: Add crafting station detection to interaction handler, open CraftingUI with correct discipline

### GAP-B-5: Minigame Launch Not Connected
**Severity**: HIGH
**Description**: `CraftingUI.cs` line 340 — `_onCraftClicked` only transitions game state but doesn't actually launch a minigame. The 5 minigame systems (SmithingMinigame, etc.) and their UIs (SmithingMinigameUI, etc.) exist independently but aren't connected.
**Fix**: CraftingUI.OnCraft → instantiate appropriate minigame → pass materials/recipe → run → collect result → create item

### GAP-B-6: Classifier Integration Not Connected
**Severity**: MEDIUM
**Description**: `CraftingUI.cs` line 360 — `_onInventClicked` shows "Validating placement..." notification but never actually calls `ClassifierManager.Validate()`. The classifier system (510 lines) is fully built but disconnected.
**Fix**: Wire CraftingUI invent button → ClassifierManager.Validate() → on success → IItemGenerator.Generate()

### GAP-B-7: Incomplete Scene Setup (Game1Setup.cs)
**Severity**: HIGH
**Description**: The editor setup script creates only 6 of 20+ required UI panels. Missing panels:

| Panel | Created by Game1Setup? | Status |
|---|---|---|
| StartMenu | YES | Wired |
| ClassSelection | YES | Wired |
| StatusBar | YES | Partial (no bars created) |
| Notifications | YES | Wired |
| DebugOverlay | YES | Wired |
| DayNight | YES | Wired |
| **InventoryUI** | **NO** | Missing |
| **EquipmentUI** | **NO** | Missing |
| **CraftingUI** | **NO** | Missing |
| **StatsUI** | **NO** | Missing |
| **SkillBarUI** | **NO** | Missing |
| **TooltipRenderer** | **NO** | Missing |
| **MapUI** | **NO** | Missing |
| **EncyclopediaUI** | **NO** | Missing |
| **NPCDialogueUI** | **NO** | Missing |
| **ChestUI** | **NO** | Missing |
| **5× MinigameUI** | **NO** | Missing |
| **DragDropManager** | **NO** | Missing |

**Fix**: Extend Game1Setup.cs to create all panels with proper hierarchy, OR create them as prefabs

### GAP-B-8: Drag-and-Drop Manager Not Created
**Severity**: HIGH
**Description**: `InventoryUI.cs` references drag-drop functionality and `DragDropManager` but no standalone `DragDropManager.cs` MonoBehaviour exists as a scene component. Need a centralized drag state tracker.
**Fix**: Create DragDropManager singleton MonoBehaviour, add to scene

### GAP-B-9: NPC Spawning Not Wired
**Severity**: MEDIUM
**Description**: `NPCDatabase` loads NPC definitions but no system spawns them into the world. Python's `game_engine.py` spawns NPCs during initialization.
**Fix**: Add NPC spawning in GameManager.StartNewGame()

### GAP-B-10: Potion/Consumable Use Not Wired
**Severity**: MEDIUM
**Description**: `PotionSystem.cs` (426 lines) exists but no UI or input handler lets the player use consumables from inventory.
**Fix**: Add right-click handler in InventoryUI → check if consumable → call PotionSystem.Use()

### GAP-B-11: Death/Respawn Not Implemented
**Severity**: MEDIUM
**Description**: No death screen or respawn logic. When player HP reaches 0, nothing happens visually.
**Fix**: Add death state to GameStateManager, death chest creation via WorldSystem, respawn at spawn point

### GAP-B-12: Dungeon Entry Not Wired
**Severity**: MEDIUM
**Description**: `WorldSystem` tracks dungeon entrances and `DungeonSystem` exists but no interaction connects player stepping on entrance → loading dungeon → spawning enemies → boss fight → loot.

### GAP-B-13: Save Slot UI Not Complete
**Severity**: LOW
**Description**: `StartMenuUI.cs` discovers save files but the load-game flow only lists `.json` files by name. No metadata display (level, class, playtime).
**Fix**: Parse save file headers for metadata display

### GAP-B-14: Encyclopedia Content Empty
**Severity**: LOW
**Description**: `EncyclopediaUI.cs` has 6 tabs but only shows placeholder text. Guide, Quests, Titles, Recipes tabs show "Coming soon" or minimal info.
**Fix**: Populate tabs from databases (RecipeDatabase for recipes, SkillDatabase for skills, etc.)

---

## 6. Category C: Polish & Integration — Feature Complete But Rough

### GAP-C-1: Equipment Total Stats Not Displayed
**File**: `EquipmentUI.cs` lines 35-36
**Description**: `_totalDamageText` and `_totalDefenseText` fields declared but never populated. Player can't see aggregate combat stats.

### GAP-C-2: Buff Icons Not Rendered
**File**: `StatusBarUI.cs` line 46
**Description**: Buff icon prefab referenced but never instantiated. Active buffs/debuffs not visible on HUD.

### GAP-C-3: Map Waypoints Not Rendered
**File**: `MapUI.cs`
**Description**: Waypoint prefab referenced but never instantiated. Chunks only colored green (grass). No biome-specific coloring, no waypoint markers, no dungeon markers.

### GAP-C-4: F3 Debug (Grant Titles) Is Stub
**File**: `DebugOverlay.cs` line 125-126
**Description**: F3 only shows notification "All titles granted" but doesn't actually call TitleSystem to grant titles.

### GAP-C-5: Engineering Puzzle Solvability
**File**: `EngineeringMinigameUI.cs`
**Description**: Puzzle grid generated randomly with no guarantee of solvability. May create impossible puzzles.

### GAP-C-6: Quest Accept/Turn-In Are Stubs
**File**: `NPCDialogueUI.cs` lines 97-103
**Description**: Accept and turn-in buttons show notifications but don't modify quest state via QuestSystem.

### GAP-C-7: StatusBar Health/Mana Bars Missing Visual Elements
**File**: `StatusBarUI.cs`
**Description**: StatusBarUI component is added to scene but the actual Image and fill components for HP/Mana/EXP bars aren't created by Game1Setup.cs.

### GAP-C-8: Skill Learning UI Missing
**Description**: No UI for learning new skills. `SkillUnlockSystem` exists but no panel lets the player browse and learn skills.

### GAP-C-9: Title Display UI Missing
**Description**: No UI for viewing earned titles or switching active title. `TitleSystem` exists but has no visual interface.

### GAP-C-10: Repair System UI Missing
**Description**: `EquipmentItem.Repair()` method exists but no UI or interaction for repairing equipment at crafting stations.

### GAP-C-11: Weight/Carry Capacity Not Displayed
**Description**: Weight system exists in Inventory but not shown in UI. No encumbrance feedback.

---

## 7. Category D: Content & Assets — Systems Work But Content Missing

### GAP-D-1: Sprite Assets Not in Unity Project
**Description**: 3,744 PNG images in `Game-1-modular/assets/` not imported into Unity `Assets/Sprites/`
**Categories**: classes (6), enemies (50+), items (200+), resources (50+), skills (100+), titles (40+), NPCs, quests, minigame backgrounds

### GAP-D-2: No Sprite Atlases
**Description**: `SpriteDatabase.cs` references 5 SpriteAtlas objects (materials, equipment, world, UI, effects) but none exist as `.spriteatlas` assets

### GAP-D-3: No Tile Assets
**Description**: WorldRenderer creates fallback 1x1 pixel colored tiles. Proper tile sprites should be imported and configured as Unity Tile assets for visual quality.

### GAP-D-4: No ONNX Model Files
**Description**: Phase 5 classifier system requires 5 `.onnx` model files:
- `smithing_cnn.onnx` (36×36×3 RGB input)
- `adornments_cnn.onnx` (56×56×3 RGB input)
- `alchemy_lgbm.onnx` (34 features)
- `refining_lgbm.onnx` (18 features)
- `engineering_lgbm.onnx` (28 features)

**Source**: Must be exported from trained Python models in `Scaled JSON Development/`

### GAP-D-5: No Audio Assets
**Description**: `AudioManager.cs` exists as placeholder. No `.wav`, `.ogg`, or `.mp3` files for SFX or music.

### GAP-D-6: No Particle Effect Prefabs
**Description**: `ParticleEffects.cs` references 9 effect prefabs (sparks, bubbles, embers, steam, gears, runes, level-up, craft-success, hit-impact) but no `.prefab` files exist.

### GAP-D-7: No ScriptableObject Instances
**Description**: 4 ScriptableObject types defined (GameConfigAsset, CombatConfigAsset, CraftingConfigAsset, RenderingConfigAsset) but no `.asset` instances created in the project.

---

## 8. Category E: Post-Migration Enhancements

### GAP-E-1: Full LLM Integration
**Description**: Replace `StubItemGenerator` with `AnthropicItemGenerator` using Claude API
**Blocked By**: API key management in Unity, async HTTP in WebGL builds

### GAP-E-2: 3D Visual Upgrade
**Description**: Replace 2D Tilemap + SpriteRenderer with 3D meshes, materials, and shaders
**See**: [Section 9](#9-rendering-2d-to-3d-transition-plan) for detailed plan

### GAP-E-3: Audio System
**Description**: Implement sound effects for combat, crafting, gathering, UI, ambient
**Scope**: 50+ sound effects, background music, volume mixing

### GAP-E-4: Advanced AI Pathfinding
**Description**: Replace simple `_MoveTowards()` with Unity NavMesh for proper obstacle avoidance
**Interface**: `IPathfinder` already defined, just needs NavMesh implementation

### GAP-E-5: Multiplayer Foundation
**Description**: Not in current scope but architecture supports it via event system

### GAP-E-6: Performance Optimization
**Description**: Object pooling for enemies/projectiles, LOD for distant chunks, occlusion culling
**Priority**: After functional gameplay is verified

---

## 9. Rendering: 2D-to-3D Transition Plan

### Current Rendering State

The entire rendering stack is **2D**:
- **World**: Unity Tilemap with 1x1 pixel colored tiles (flat XY plane rotated to XZ)
- **Player**: SpriteRenderer with placeholder cyan square
- **Enemies**: SpriteRenderer with sprites from SpriteDatabase
- **Resources**: SpriteRenderer with color tinting
- **UI**: Screen Space Overlay Canvas (uGUI)
- **Camera**: Orthographic at Y=50, looking straight down (90° pitch)
- **Effects**: LineRenderer for attacks, object-pooled TextMeshPro for damage numbers

### Target Rendering State

A **3D world with 2D UI overlay**:

#### Layer 1: 3D Terrain
- Replace Tilemap with 3D terrain mesh or tiled 3D geometry
- Each tile type gets a 3D material (grass plane, water plane with shader, stone with height)
- Chunk-based mesh generation matching existing WorldSystem chunk boundaries
- Normal-mapped surfaces for visual depth
- Water shader with animation

#### Layer 2: 3D Entities
- Player character: 3D model or 2.5D billboard sprite on 3D plane
- Enemies: 3D models or billboarded sprites with shadows
- Resources: 3D models (trees, ore deposits, stone formations)
- Crafting stations: 3D models with interaction highlights
- Placed entities: 3D turrets, barriers, traps

#### Layer 3: 3D Effects
- Particle systems for combat (slash, fire, ice, lightning, poison)
- Projectile trajectories in 3D space
- AoE indicators as ground projectors
- Day/night via directional light rotation (not screen overlay)

#### Layer 4: 2D UI (Preserved)
- All UI panels remain as Screen Space Canvas (uGUI)
- Tooltip, inventory, equipment, crafting, stats — all stay 2D
- Damage numbers transition to World Space Canvas
- Health bars above enemies as World Space Canvas

### 3D Transition Implementation Steps

#### Step 1: Camera Transition
**File**: `CameraController.cs`
**Changes**:
- Switch `_orthographic = false`
- Set camera to perspective mode with configurable FOV (45-60°)
- Adjust camera height and angle (45° instead of 90°)
- Add camera rotation support (orbit around player)
- Keep ScreenToWorldXZ working with perspective ray

#### Step 2: Terrain System
**New Files**:
- `ChunkMeshGenerator.cs` — Generates mesh per chunk (16×16 quads)
- `TerrainMaterialManager.cs` — Maps tile types to 3D materials
- `WaterShader.shader` — Animated water surface

**Approach**: Each chunk becomes a single mesh with per-tile UV mapping to a terrain texture atlas. Height variation per tile type (water=-0.1, grass=0, stone=+0.2, mountain=+0.5).

#### Step 3: Entity 3D Representation
**Approach**: Start with billboarded sprites (3D planes always facing camera), evolve to 3D models later. This maintains visual compatibility while establishing 3D positioning.

**New Files**:
- `BillboardSprite.cs` — Component that rotates sprite plane to face camera
- `EntityShadow.cs` — Dynamic shadow blob beneath entities

#### Step 4: Lighting System
**Changes**:
- Replace DayNightOverlay (screen overlay) with directional light rotation
- Add ambient light color cycling (warm day, cool night)
- Point lights for crafting stations, campfires
- Dynamic shadows from directional light

#### Step 5: Effect System Upgrade
**Changes**:
- Particle systems in 3D space (not screen space)
- Slash/swing arcs as mesh-based trails
- Projectiles with 3D trajectories
- Ground-projected AoE indicators (decal projectors)

#### Step 6: World Space UI
**Changes**:
- Damage numbers on World Space Canvas (positioned in 3D, face camera)
- Enemy health bars on World Space Canvas
- Resource interaction prompts in world space
- Floating name labels for NPCs

### 3D Transition Priority Order
1. Camera (perspective + angle) — 1-2 hours, immediate visual impact
2. Terrain mesh generation — 4-6 hours, replaces flat tilemap
3. Billboarded entities — 2-3 hours, entities exist in 3D space
4. Lighting — 2-3 hours, dramatic visual upgrade
5. World Space UI elements — 2-3 hours, damage numbers + health bars in 3D
6. Water shader — 2-3 hours, animated water
7. 3D particle effects — 3-4 hours, combat feels real
8. Height variation — 2-3 hours, terrain has depth
9. Shadows — 1-2 hours, grounding in 3D space
10. 3D models (future) — Ongoing asset creation

---

## 10. File-by-File Gap Analysis

### Files With Known Issues

| File | Lines | Issue | Fix Effort |
|---|---|---|---|
| `GameManager.cs` | 351 | 2 TODOs: Combat not wired | 2-4 hours |
| `CraftingUI.cs` | 435 | Craft button doesn't launch minigame, Invent doesn't call classifier | 4-6 hours |
| `EquipmentUI.cs` | 145 | Total damage/defense text never populated | 30 min |
| `StatusBarUI.cs` | 110 | No buff icon rendering | 1-2 hours |
| `NPCDialogueUI.cs` | 120 | Quest accept/turn-in are stubs | 2-3 hours |
| `EncyclopediaUI.cs` | 127 | All tabs show placeholder content | 3-4 hours |
| `MapUI.cs` | 169 | No waypoints, no biome colors, no dungeon markers | 2-3 hours |
| `DebugOverlay.cs` | 157 | F3 grant titles is stub | 15 min |
| `EngineeringMinigameUI.cs` | 158 | Random puzzles may be unsolvable | 2-3 hours |
| `Game1Setup.cs` | 529 | Only creates 6 of 20+ required panels | 6-8 hours |
| `AudioManager.cs` | 107 | Placeholder with no audio assets | N/A (asset) |

### Files That Are Complete (No Issues Found)

All other 122 C# files were verified complete with no TODOs, stubs, or missing functionality.

---

## 11. Dependency Order for Fixes

### Phase I: Make It Run (Days 1-3)
```
1. GAP-A-1: Create Unity project structure
2. GAP-A-2: Configure package dependencies
3. GAP-A-5: Create assembly definitions
4. GAP-A-7: Import TMP font assets
5. GAP-A-3: Copy JSON content to StreamingAssets
6. GAP-A-6: Import sprite assets
7. GAP-A-4: Create scene (extend Game1Setup.cs or manual)
```

### Phase II: Make It Playable (Days 4-7)
```
8.  GAP-A-8 + GAP-B-1: ICombatCharacter adapter + combat wiring
9.  GAP-B-2: Wire enemy spawning
10. GAP-B-3: Wire resource gathering interaction
11. GAP-B-4: Wire crafting station interaction
12. GAP-B-5: Connect minigame launch flow
13. GAP-B-7: Complete scene setup (all UI panels)
14. GAP-B-8: DragDropManager singleton
15. GAP-B-11: Death/respawn system
```

### Phase III: Full Feature Parity (Days 8-12)
```
16. GAP-B-6: Classifier integration
17. GAP-B-9: NPC spawning
18. GAP-B-10: Potion/consumable use
19. GAP-B-12: Dungeon entry
20. GAP-C-1 through GAP-C-11: Polish items
```

### Phase IV: 3D Rendering Transition (Days 13-18)
```
21. Camera to perspective
22. Chunk mesh terrain generation
23. Billboarded entity sprites
24. Directional lighting + day/night
25. World Space UI (damage numbers, health bars)
26. Water shader
27. 3D particle effects
28. Height variation
```

### Phase V: Content & Polish (Days 19-22)
```
29. GAP-D-2: Sprite atlases
30. GAP-D-3: Proper tile art
31. GAP-D-6: Particle effect prefabs
32. GAP-D-7: ScriptableObject instances
33. GAP-B-13: Save slot metadata
34. GAP-B-14: Encyclopedia content
35. GAP-E-1: LLM integration (if desired)
```

---

## 12. Estimated Effort

| Phase | Description | Effort | Cumulative |
|---|---|---|---|
| I | Make It Run | 8-12 hours | 8-12 hours |
| II | Make It Playable | 20-30 hours | 28-42 hours |
| III | Full Feature Parity | 15-20 hours | 43-62 hours |
| IV | 3D Rendering | 20-25 hours | 63-87 hours |
| V | Content & Polish | 10-15 hours | 73-102 hours |
| **TOTAL** | **Fully Operational 3D Game** | **73-102 hours** | — |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unity version incompatibility with C# syntax | Medium | High | Target Unity 2022.3 LTS, avoid C# 12 features |
| JSON deserialization failures | Medium | High | Extensive fallback/placeholder logic already in databases |
| Package version conflicts (Sentis, Input System) | Low | Medium | Pin specific versions in manifest.json |
| Performance issues with 3D terrain | Low | Medium | Chunk-based LOD, frustum culling already designed |
| Asset import volume (3,744 images) | Low | Low | Batch import with scripted settings |

---

## Appendix A: Quick Reference — Files to Create

### New C# Files Needed
```
Game1.Unity/Core/CombatCharacterAdapter.cs     — ICombatCharacter wrapper for Character
Game1.Unity/Core/InteractionHandler.cs         — Routes player interactions (gather, craft, NPC, chest)
Game1.Unity/Core/PlayerController.cs           — Player movement + interaction trigger
Game1.Unity/World/ChunkMeshGenerator.cs        — 3D terrain mesh per chunk
Game1.Unity/World/TerrainMaterialManager.cs    — Tile type → 3D material mapping
Game1.Unity/World/BillboardSprite.cs           — Sprite always faces camera
Game1.Unity/World/EntityShadow.cs              — Shadow blob under entities
```

### New Unity Assets Needed
```
Assets/Scenes/GameWorld.unity
Assets/Sprites/ (3,744 PNGs organized by category)
Assets/StreamingAssets/Content/ (all JSON from Python source)
Assets/Resources/Models/ (5 ONNX files when available)
Assets/Materials/ (terrain materials, water shader, UI materials)
Assets/Prefabs/ (Player, Enemy, Resource, CraftingStation, Turret, Trap, DamageNumber, LootChest)
Assets/Settings/Game1InputActions.inputactions
8× .asmdef files
4× .asset ScriptableObject instances
```

---

## Appendix B: Verification Checklist

After completing all fixes, verify each item:

- [ ] Unity Editor opens project without errors
- [ ] Press Play → Start menu appears
- [ ] Click "Quick Start" → World generates, player spawns
- [ ] Click "New World" → Name entry → Class selection → World generates
- [ ] WASD moves player, camera follows smoothly
- [ ] Tab opens inventory (30 empty slots)
- [ ] Resources visible in world, E-key harvests them
- [ ] Materials appear in inventory after gathering
- [ ] Crafting station interaction opens CraftingUI
- [ ] Recipe selection works, material placement works
- [ ] Minigame launches and completes, item created
- [ ] Equipment panel shows equipped items with durability
- [ ] Enemies spawn and pursue player on proximity
- [ ] Attack deals damage, damage numbers float
- [ ] Enemy death drops loot
- [ ] Status effects apply and tick (burn, poison, etc.)
- [ ] Skills activate from hotbar (1-5 keys)
- [ ] Level up grants stat point, stat allocation works
- [ ] Save game preserves all state
- [ ] Load game restores all state
- [ ] Map shows explored chunks
- [ ] Day/night cycle affects lighting
- [ ] Debug keys (F1-F7) function
- [ ] 60 FPS sustained during normal gameplay
- [ ] 3D terrain renders with height variation
- [ ] Camera in perspective mode with proper angle
- [ ] Entities cast shadows
- [ ] Water animated
- [ ] Particle effects play for combat and crafting

---

**Document End**
**Author**: AI Assistant
**Date**: 2026-02-18
**Next Action**: Begin Phase I fixes (GAP-A-1 through GAP-A-8)
