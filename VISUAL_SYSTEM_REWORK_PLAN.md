# Visual System Rework Plan

**Date**: 2026-02-25
**Status**: Broken — game loads data fine but renders nothing usable
**Goal**: Make the Unity port visually functional with 2D top-down view matching the Python/Pygame original

---

## Current State: What Works vs What's Broken

### Works
- All databases load (materials, enemies, recipes, skills, etc.)
- World generates with correct seed
- Game state machine transitions (StartMenu → Playing)
- Combat system initializes
- All 27 UI C# files compile and are structurally complete

### Broken
1. **No scene file exists** — zero `.unity`, `.prefab`, `.shader`, `.mat`, `.inputactions` files in the project. All MonoBehaviours exist as code only with no scene wiring.
2. **WorldRenderer crashes** — `_groundTilemap` is null because no Tilemap/Grid exists in scene. Default was changed to `_use3DMesh = false` but no tilemap is wired.
3. **Input broken** — PlayerController.cs, DragDropManager.cs, FishingMinigameUI.cs still use legacy `Input.*` but project Player Settings require Input System package.
4. **Camera wrong** — CameraController defaults changed to orthographic but scene likely has old serialized values (perspective 3D).
5. **No sprites/textures** — SpriteDatabase tries Resources folder and SpriteAtlases but none exist in Unity project.

---

## File Map: Every Visual/Rendering File

### Core (4 files) — `Assets/Scripts/Game1.Unity/Core/`
| File | Lines | Role | Issues |
|------|-------|------|--------|
| `CameraController.cs` | ~170 | Camera follow + zoom + ortho/perspective toggle | Default now `_orthographic=true` but needs scene wiring. Uses `Input.mouseScrollDelta` (legacy?) |
| `PlayerController.cs` | 186 | Movement + interaction | **Lines 86-87, 148: Uses legacy `Input.GetAxisRaw()` and `Input.GetKeyDown()`** |
| `InputManager.cs` | ~310 | Central input routing (rewritten for Input System) | Just rewritten — creates inline InputActions. No `.inputactions` asset file. |
| `GameManager.cs` | ~420 | Bootstrap singleton | References `_cameraController`, `_inputManager`, `_stateManager` via SerializeField (need scene wiring) |

### World Rendering (5 files) — `Assets/Scripts/Game1.Unity/World/`
| File | Lines | Role | Issues |
|------|-------|------|--------|
| `WorldRenderer.cs` | 479 | Chunk-based terrain (3D mesh OR 2D tilemap) | `_use3DMesh=false` now, but `_groundTilemap` null → crash. Tilemap fallback creates 1×1 color tiles. |
| `ChunkMeshGenerator.cs` | ~250 | Procedural 3D mesh per chunk | Only used in 3D mode. Generates vertex-colored terrain with height. |
| `TerrainMaterialManager.cs` | ~200 | Materials for terrain/water/edges | Singleton. Creates URP Lit materials. Water mesh generator. Fields `_waterWaveScale`, `_waterWaveHeight` unused. |
| `BillboardSprite.cs` | 190 | Makes sprites face camera | Y-axis billboard + ground shadow. Used for entities in 3D mode. |
| `EnemyRenderer.cs` | ~150 | Enemy sprite + health bar display | `_healthBarOffset` unused. Depends on SpriteDatabase for enemy sprites. |
| `ParticleEffects.cs` | 322 | 9 particle effect types (sparks, embers, bubbles, etc.) | Auto-creates ParticleSystems at runtime. Singleton. |

### UI (27 files) — `Assets/Scripts/Game1.Unity/UI/`
See full list in CLAUDE.md. Key facts:
- **DragDropManager.cs** lines 133, 139-140: Legacy `Input.mousePosition`, `Input.GetKeyDown`, `Input.GetMouseButtonDown`
- **FishingMinigameUI.cs** lines 88, 169: Legacy `Input.GetMouseButtonDown(0)`, `Input.mousePosition`
- All other UI files use InputManager events (correct)
- Every UI file has `[SerializeField]` fields requiring scene wiring
- 11+ prefabs needed (slot, card, entry prefabs for dynamic content)

### Utilities (3 files) — `Assets/Scripts/Game1.Unity/Utilities/`
| File | Lines | Role |
|------|-------|------|
| `SpriteDatabase.cs` | 189 | Sprite loading/caching by itemId, tileType, enemyId |
| `PositionConverter.cs` | 75 | GamePosition ↔ Vector3 conversion |
| `ColorConverter.cs` | ~100 | Tile colors (TileGrass, TileWater, etc.), rarity colors |

---

## Legacy Input Usage (Must Fix)

3 files still use `UnityEngine.Input` (crashes with Input System active):

| File | Lines | What to change |
|------|-------|----------------|
| `PlayerController.cs` | 86, 87, 148 | `Input.GetAxisRaw("Horizontal"/"Vertical")`, `Input.GetKeyDown(KeyCode.E)` → subscribe to InputManager events |
| `DragDropManager.cs` | 133, 139, 140 | `Input.mousePosition`, `Input.GetKeyDown(Escape)`, `Input.GetMouseButtonDown(1)` → use `Mouse.current.position` or InputManager |
| `FishingMinigameUI.cs` | 88, 169 | `Input.GetMouseButtonDown(0)`, `Input.mousePosition` → use InputManager or `Mouse.current` |

---

## The Fundamental Problem

The project has **159 C# files** of game logic but **zero Unity assets**:
- No `.unity` scene files
- No `.prefab` files
- No `.mat` material files
- No `.shader` files
- No `.inputactions` asset files
- No sprite atlases or textures in Unity format

Everything was written as code-only MonoBehaviours assuming they'd be wired in a scene editor. The scene that currently exists was apparently hand-created by the user but has mismatched/missing references.

---

## Recommended Rework Strategy

### Option A: Scene-Bootstrap Approach (Recommended)
Create a **SceneBootstrapper.cs** MonoBehaviour that programmatically:
1. Creates the Canvas hierarchy (Main Canvas, Overlay Canvas for tooltips, Drag Canvas)
2. Creates all UI GameObjects with proper RectTransform layouts
3. Creates and wires a Grid + Tilemap for WorldRenderer
4. Sets up Camera as orthographic top-down
5. Instantiates all manager singletons (GameManager, InputManager, StateManager, etc.)
6. Wires all SerializeField references via code

This eliminates the need for manual scene setup and makes the game self-bootstrapping.

### Option B: Minimal Scene + Prefabs
Create the absolute minimum scene file and prefab set manually. Fragile — serialized references break easily.

### Either way, these must happen:
1. **Fix 3 legacy Input files** (PlayerController, DragDropManager, FishingMinigameUI)
2. **Create or wire a Tilemap** for WorldRenderer's 2D mode
3. **Set camera to orthographic top-down** (looking down Y axis at XZ plane)
4. **Create basic tile sprites** or use the 1×1 color tile fallback (already coded in WorldRenderer._createFallbackTiles)
5. **Wire all 27 UI components** to actual GameObjects with proper Canvas setup

---

## Key Architecture Context for New Conversation

### Coordinate System
- Python: `(x, y)` screen coordinates
- Unity: `GamePosition(X, Y, Z)` where X=east/west, Y=height(always 0 for 2D), Z=north/south
- `PositionConverter.cs` handles conversion

### Rendering Pipeline (Python original)
- `rendering/renderer.py` (2,782 lines) draws everything in paint order
- 100×100 tile world, 10×10 chunks
- Tiles are flat colored squares (grass=green, water=blue, stone=gray, etc.)
- Entities rendered as sprites on top of tiles
- Camera centered on player, renders visible chunk radius

### What the Python Game Looks Like
- Top-down 2D, flat colored tiles
- Player sprite centered
- UI panels overlay (inventory grid, equipment slots, crafting, etc.)
- Simple but functional — colored rectangles with text

### Config Constants (in `GameConfig`)
- `ChunkSize` = 10
- `WorldSizeX` = 100, `WorldSizeZ` = 100
- Tile size = 1 Unity unit

### Tile Colors (in `ColorConverter`)
- Grass: green, Water: blue, Stone: gray, Sand: yellow, Cave: dark brown, Snow: white, Dirt: brown

### Key Singletons (must all exist in scene)
`GameManager`, `GameStateManager`, `InputManager`, `CameraController`, `WorldRenderer`, `SpriteDatabase`, `DragDropManager`, `TooltipRenderer`, `NotificationUI`, `ParticleEffects`

---

## Files to Read First in New Conversation

Priority order for understanding the visual system:
1. `VISUAL_SYSTEM_REWORK_PLAN.md` (this file)
2. `Unity/Assets/Scripts/Game1.Unity/Core/GameManager.cs` (bootstrap, dependencies)
3. `Unity/Assets/Scripts/Game1.Unity/World/WorldRenderer.cs` (terrain rendering)
4. `Unity/Assets/Scripts/Game1.Unity/Core/CameraController.cs` (camera setup)
5. `Unity/Assets/Scripts/Game1.Unity/Core/InputManager.cs` (input system)
6. `Unity/Assets/Scripts/Game1.Unity/Core/PlayerController.cs` (movement — has legacy Input bug)
7. `Unity/Assets/Scripts/Game1.Unity/Utilities/ColorConverter.cs` (tile colors)
8. `.claude/CLAUDE.md` (full project context)

---

## Warnings for CS Compiler (Current)

These are cosmetic, not breaking:
```
CS0067: InputManager.OnToggleEquipment never used
CS0414: TerrainMaterialManager._waterWaveHeight assigned but never used
CS0414: TooltipRenderer._padding assigned but never used
CS0414: SaveLoadUI._isSaveMode assigned but never used
CS0414: InventoryUI._rows, _columns assigned but never used
CS0414: PlayerController._moveSpeed, _diagonalFactor, _interactionRange assigned but never used
CS0414: EnemyRenderer._healthBarOffset assigned but never used
CS0414: TerrainMaterialManager._waterWaveScale assigned but never used
CS0414: TooltipRenderer._maxWidth assigned but never used
```

The `_moveSpeed`/`_diagonalFactor`/`_interactionRange` warnings in PlayerController are because movement reads `Input.GetAxisRaw` directly with `_character.MovementSpeed` instead of using the serialized `_moveSpeed` field.
