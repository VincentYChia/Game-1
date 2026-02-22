# Unity Manual Tasks Guide

**What this is**: A checklist of everything that can't be auto-migrated from the Python/Pygame codebase.
Each task has a **full approach** (production quality) and a **quick workaround** (get it running fast).

---

## 1. Scene Setup

### 1.1 Main Scene Bootstrap

**What**: Create the main game scene with a root `GameManager` GameObject.

**Full approach**: Create `Assets/Scenes/MainScene.unity`. Add an empty GameObject named `GameManager`, attach `GameManager.cs`. Add child objects for `InputManager`, `AudioManager`, `GameStateManager`, `PlayerController`, and `CameraController`. Wire all `[SerializeField]` references in the Inspector.

**Quick workaround**: Create a single scene, add one GameObject, attach `GameManager.cs`. It auto-creates missing singletons at runtime. Other managers can be added as needed.

### 1.2 Camera Rig

**What**: `CameraController.cs` has 16 `[SerializeField]` fields (follow target, zoom limits, rotation speed, etc.).

**Full approach**: Create a Camera GameObject with `CameraController.cs`. Configure isometric/top-down angle, zoom range (5-20 units), follow smoothing, and rotation. Set up Cinemachine for smooth transitions.

**Quick workaround**: Use Unity's default Main Camera. Attach `CameraController.cs`, set the player transform as the follow target. Defaults in the script are playable.

---

## 2. UI Canvases & Prefabs (~270 SerializeField references across 25+ UI scripts)

### 2.1 HUD Canvas

**What**: Screen-space overlay for health/mana bars, hotbar, minimap.

**Scripts to wire**:
- `StatusBarUI.cs` (13 fields) — HP bar, MP bar, XP bar, level text, status icons
- `SkillBarUI.cs` (4 fields) — 5 hotbar skill slots
- `NotificationUI.cs` (6 fields) — toast notification panel
- `DebugOverlay.cs` (2 fields) — FPS counter, debug text

**Full approach**: Create a Canvas (Screen Space - Overlay), build each HUD element as a child panel with Image + TextMeshPro components. Create prefabs for reusable pieces (skill slot, status icon). Wire all `[SerializeField]` references.

**Quick workaround**: Create a single Canvas, add a few TextMeshPro objects for HP/MP/Level. Skip the hotbar and minimap — skills can be tested via keyboard input without visual slots.

### 2.2 Inventory UI

**What**: 30-slot grid inventory with drag-and-drop.

**Scripts to wire**:
- `InventoryUI.cs` (8 fields) — grid container, slot prefab, weight text
- `DragDropManager.cs` (3 fields) — drag icon, canvas reference
- `TooltipRenderer.cs` (9 fields) — tooltip panel, name/desc/stats text, icon

**Full approach**: Create an inventory panel with a GridLayoutGroup (6 columns, 5 rows). Create a slot prefab (Image + Button + icon child + quantity text). Build a tooltip prefab with name, description, stats, and rarity border.

**Quick workaround**: Use Unity's built-in `GridLayoutGroup` with simple Image children. Skip drag-and-drop — use click-to-select, click-to-place. Use `Debug.Log` for item info instead of tooltips.

### 2.3 Equipment UI

**What**: 8 equipment slots (head, chest, legs, feet, main hand, off hand, ring, necklace).

**Scripts to wire**:
- `EquipmentUI.cs` (4 fields) — slot containers, character preview

**Full approach**: Create a paper-doll layout with positioned slot Images matching body locations. Add a 3D character preview render texture.

**Quick workaround**: Use a simple vertical list of 8 labeled slots. No character preview — just text showing equipped item names.

### 2.4 Crafting UI + 6 Minigame UIs

**What**: Station selection UI plus discipline-specific minigame interfaces.

**Scripts to wire**:
- `CraftingUI.cs` (15 fields) — recipe list, material grid, craft button
- `SmithingMinigameUI.cs` (10 fields) — temperature bar, hammer timing bar, bellows button
- `AlchemyMinigameUI.cs` (4 fields) — ingredient slots, mixing controls
- `RefiningMinigameUI.cs` (3 fields) — refinement progress, purity gauge
- `EngineeringMinigameUI.cs` (4 fields) — assembly grid, component slots
- `EnchantingMinigameUI.cs` (7 fields) — rune selection, power gauge
- `FishingMinigameUI.cs` (14 fields) — water area, ripple indicators, tension bar, catch meter

**Full approach**: Each minigame needs its own panel/prefab. Smithing needs an animated temperature bar with a "perfect zone" highlight and a timing cursor. Alchemy needs draggable ingredient slots. Fishing needs a water area with spawn points for ripple indicators.

**Quick workaround**: Create one generic panel per minigame with a progress bar and action button. The `BaseCraftingMinigame` logic runs in the background — you only need minimal UI to call `HandleInput()` and display `CalculatePerformance()` results.

### 2.5 Other Menus

| Script | Fields | What it needs |
|--------|--------|---------------|
| `StatsUI.cs` | 3 | Stat labels (STR/DEF/VIT/LCK/AGI/INT) + values |
| `SkillsMenuUI.cs` | 15 | Skill tree/list with icons, descriptions, equip buttons |
| `TitleUI.cs` | 11 | Title list with earned/locked states |
| `ClassSelectionUI.cs` | 7 | 6 class cards with descriptions and select button |
| `SkillUnlockUI.cs` | 8 | Unlock prompt with skill preview |
| `ChestUI.cs` | 6 | Loot chest grid (similar to inventory) |
| `SaveLoadUI.cs` | 9 | Save slot list with load/save/delete buttons |
| `StartMenuUI.cs` | 11 | Main menu (New Game, Continue, Settings) |
| `NPCDialogueUI.cs` | 9 | Dialogue box, portrait, choice buttons |
| `EncyclopediaUI.cs` | 15 | Tabbed reference (items, monsters, recipes) |
| `MapUI.cs` | 10 | World map with waypoints and fog of war |

**Quick workaround for all**: Stub each menu with a single Panel + a few TextMeshPro labels. The game logic runs without fully-built UIs — menus just display data from the C# systems.

---

## 3. 3D Models & Rigging

### 3.1 Player Character

**What**: The Python game uses 2D sprites. Unity needs a 3D model (or billboard sprite).

**Full approach**: Model a low-poly humanoid character in Blender. Rig with Unity's Humanoid avatar. Create animations: idle, walk, run, attack (per weapon type), gather, craft, hit reaction, death. Export as FBX.

**Quick workaround**: Use Unity Asset Store free characters (e.g., "Starter Assets - Third Person Character Controller" or "Jammo Character"). Import the FBX, set rig to Humanoid, and use the included animations. The `PlayerRenderer.cs` (7 fields) just needs a reference to the model's Animator.

### 3.2 Enemies (16 types)

**What**: 16 enemy sprites exist in `assets/enemies/`. Need 3D equivalents or billboards.

**Existing sprites**: bear, boar, cave_spider, dragon, forest_spirit, goblin, goblin_archer, griffin, living_shadow, phantom_wolf, rock_golem, shadow_knight, skeleton_warrior, toxic_slime, treant, wolf

**Full approach**: Model each enemy or find asset packs. Rig and animate (idle, walk, attack, hit, death). Configure in `EnemyRenderer.cs` (9 fields) with per-enemy prefabs.

**Quick workaround**: Use `BillboardSprite.cs` (6 fields) — this component renders a quad that always faces the camera. Import the existing 2D enemy PNGs as sprites, assign to billboard quads. They'll look like classic JRPG sprites in 3D space. Alternatively, use Unity primitive shapes (capsules) with different colors per enemy type.

### 3.3 NPCs (3 types)

**What**: 3 NPC sprites exist. Need 3D models or billboards.

**Full approach**: Model or source NPC characters with idle animations.

**Quick workaround**: Reuse the player model with different material colors, or use billboard sprites from the existing PNGs.

### 3.4 Resource Nodes (48 types)

**What**: 48 resource sprites (trees, ores, fishing spots). Need 3D equivalents.

**Existing sprites**: Various trees (ash, birch, ebony, ironwood, etc.), ore nodes (copper, iron, mythril, etc.), fishing spots (10 types)

**Full approach**: Model or source 3D trees, rocks, ore veins. Trees need sway animations. Ore nodes need glow/shimmer effects per tier.

**Quick workaround**: Use Unity's built-in 3D primitives:
- **Trees**: Use Unity Terrain tree painting or free SpeedTree assets
- **Ores**: Colored cubes/spheres with emissive materials (T1=grey, T2=blue, T3=purple, T4=gold)
- **Fishing spots**: A flat plane with an animated water shader

`ResourceRenderer.cs` (8 fields) handles spawning — just needs prefab references.

---

## 4. Terrain & World Rendering

### 4.1 Tile Materials

**What**: `TerrainMaterialManager.cs` (8 fields) manages materials for 6+ tile types (grass, forest, mountain, water, desert, snow).

**Full approach**: Create PBR terrain materials with albedo, normal, and roughness textures. Use Unity Terrain with texture layers and splat maps for smooth blending.

**Quick workaround**: Create solid-color materials for each tile type (green=grass, dark green=forest, grey=mountain, blue=water, tan=desert, white=snow). Assign to `ChunkMeshGenerator.cs` which builds mesh geometry from chunk data.

### 4.2 Water

**What**: `WaterSurfaceAnimator.cs` (11 fields) — animated water with waves, color cycling, foam.

**Full approach**: Use a water shader (Shader Graph) with vertex displacement for waves, depth-based transparency, and foam at shorelines.

**Quick workaround**: Use a blue semi-transparent plane with Unity's default transparent material. Add a simple UV-scroll script for the illusion of movement.

### 4.3 Day/Night Cycle

**What**: `DayNightOverlay.cs` (19 fields) — sky color transitions, directional light rotation, ambient changes.

**Full approach**: Animate a Directional Light rotation on a 24h cycle. Use gradient textures for sky color. Adjust ambient light and fog.

**Quick workaround**: Set a static directional light at a 45-degree angle. Skip the day/night cycle — it's cosmetic only and doesn't affect gameplay.

### 4.4 World Renderer

**What**: `WorldRenderer.cs` (12 fields) — chunk loading/unloading, LOD management.

**Full approach**: Implement chunk-based mesh generation. Load/unload chunks in a radius around the player. Add LOD for distant chunks.

**Quick workaround**: Generate flat colored quads per tile (100x100 = 10,000 quads). Unity handles this easily. No LOD needed for a 100x100 world.

---

## 5. Visual Effects

### 5.1 Particle Effects

**What**: `ParticleEffects.cs` (9 fields) — spell impacts, crafting sparks, gathering particles, level-up effects.

**Full approach**: Create Particle System prefabs for each effect type (fire, ice, lightning, poison, arcane, shadow, holy, heal, levelup, craft_spark, gather_dust). Design visuals per damage type.

**Quick workaround**: Create one generic particle burst prefab (Unity default particle system). Tint it by damage type color (red=fire, blue=ice, yellow=lightning, green=poison). Assign the same prefab to all effect slots.

### 5.2 Attack Effects

**What**: `AttackEffectRenderer.cs` (3 fields) — weapon swing arcs, projectiles, beam effects.

**Full approach**: Create trail renderers for melee swings, projectile prefabs with particle trails, beam line renderers for lightning/holy.

**Quick workaround**: Skip visual attack effects. Damage numbers alone communicate combat clearly. Add a simple white flash on the hit target.

### 5.3 Damage Numbers

**What**: `DamageNumberRenderer.cs` (5 fields) — floating damage text that rises and fades.

**Full approach**: Create a world-space TextMeshPro prefab that floats up, scales, and fades. Color by damage type. Larger font for crits.

**Quick workaround**: Use `Debug.Log` for damage output, or create a single TextMeshPro prefab that spawns at the hit position and destroys itself after 1 second via a simple script.

---

## 6. Audio

### 6.1 Sound Effects

**What**: `AudioManager.cs` loads clips from `Resources/Audio/`. The Python game has no audio files — this is entirely new content.

**Audio needed**:
- UI: button click, inventory open/close, item pickup, craft success/fail
- Combat: sword swing, bow shot, spell cast (per element), hit impact, enemy death
- Gathering: axe chop, pickaxe strike, fishing cast/reel
- Crafting: anvil hammer, potion bubble, furnace roar, enchant shimmer
- Ambient: forest, cave, water, wind
- Music: menu theme, exploration, combat, boss, crafting

**Full approach**: Source or create all audio assets. Organize in `Assets/Resources/Audio/SFX/` and `Assets/Resources/Audio/Music/`.

**Quick workaround**: The game runs silently with no issues — audio is entirely optional. If you want basic audio, grab a free SFX pack from the Unity Asset Store (search "RPG Sound Effects Free") and drop clips into `Resources/Audio/`. `AudioManager.cs` loads by name string, so match filenames to the names used in code.

---

## 7. Item Icons (178 items + 41 skills + 10 titles)

### 7.1 Item Sprites

**What**: 178 item PNGs exist in `assets/items/`. These need to be imported as Unity Sprites.

**Full approach**: Import all PNGs into `Assets/Resources/Sprites/Items/`. Set texture type to "Sprite (2D and UI)", filter to "Point" for pixel art or "Bilinear" for painted style. Create a sprite atlas for performance.

**Quick workaround**: Bulk-import the PNGs. Unity auto-detects them. `SpriteDatabase.cs` (8 fields) loads sprites from Resources by name — just ensure filenames match the item IDs used in JSON data.

### 7.2 Skill Icons

**What**: 41 skill PNGs exist in `assets/skills/`.

**Quick workaround**: Same as items — bulk import to `Assets/Resources/Sprites/Skills/`.

### 7.3 Class & Title Icons

**What**: 6 class icons and 10 title icons exist.

**Quick workaround**: Import to `Assets/Resources/Sprites/Classes/` and `Assets/Resources/Sprites/Titles/`.

---

## 8. JSON Data Files

### 8.1 StreamingAssets Setup

**What**: All JSON game data must be copied to `Assets/StreamingAssets/Content/`.

**Full approach**: Copy these folders byte-identical from `Game-1-modular/`:
```
StreamingAssets/Content/
├── items.JSON/           (6 files — materials, weapons, potions, etc.)
├── recipes.JSON/         (6 files — per-discipline recipes)
├── placements.JSON/      (minigame grid layouts)
├── Skills/               (skill definitions)
├── progression/          (classes, titles, NPCs)
└── Definitions.JSON/     (tags, enemies, stats, stations)
```

**Quick workaround**: Copy the entire set of JSON folders. The database singletons load them automatically via `GamePaths.cs`. No manual wiring needed — just file placement.

---

## 9. ScriptableObject Assets

### 9.1 Config Assets

**What**: 4 ScriptableObject types need instances created in the Editor.

| Asset Type | Script | Purpose |
|------------|--------|---------|
| `GameConfigAsset` | `Config/GameConfigAsset.cs` | Tile size, chunk size, world size |
| `CombatConfigAsset` | `Config/CombatConfigAsset.cs` | Damage constants, crit multiplier |
| `CraftingConfigAsset` | `Config/CraftingConfigAsset.cs` | Minigame timers, difficulty curves |
| `RenderingConfigAsset` | `Config/RenderingConfigAsset.cs` | View distance, LOD settings |

**Full approach**: Right-click in Project > Create > Game1 > [ConfigType]. Fill in values matching the Python constants from `core/config.py`.

**Quick workaround**: The C# code has hardcoded defaults matching the Python values. These ScriptableObjects are optional overrides — the game runs fine without them.

---

## 10. ML / ONNX Models (Phase 5)

### 10.1 Sentis Integration

**What**: `SentisModelBackend.cs` is currently a mock (always returns 85% confidence). Real ML inference needs trained ONNX models.

**Models needed**:
| Model | Input | Source |
|-------|-------|--------|
| Smithing CNN | 36x36x3 RGB | `Scaled JSON Development/Convolution Neural Network (CNN)/` |
| Adornment CNN | 56x56x3 RGB | Same directory |
| Alchemy LightGBM | 34 features | `Scaled JSON Development/Simple Classifiers (LightGBM)/` |
| Refining LightGBM | 18 features | Same directory |
| Engineering LightGBM | 28 features | Same directory |

**Full approach**: Export trained models to ONNX format. Install `com.unity.sentis` package. Place `.onnx` files in `Assets/StreamingAssets/Models/`. Update `SentisModelBackend.cs` to load and run inference.

**Quick workaround**: Keep the mock implementation. Crafting invention will always succeed, which is fine for development and playtesting. The `StubItemGenerator` provides placeholder items without needing the Claude API either.

---

## Recommended Setup Order

For the fastest path to a playable prototype:

1. **Scene + GameManager** (5 min) — Create scene, add GameManager GameObject
2. **JSON data** (2 min) — Copy JSON folders to StreamingAssets
3. **Camera** (5 min) — Add camera with CameraController
4. **Terrain** (15 min) — Solid-color materials per tile type, flat quads
5. **Player** (10 min) — Import free asset store character or capsule primitive
6. **Enemies** (10 min) — Billboard sprites from existing PNGs or colored capsules
7. **Item sprites** (5 min) — Bulk import existing PNGs
8. **Basic HUD** (20 min) — HP/MP bars + level text
9. **Inventory UI** (30 min) — Grid layout with slot prefab

This gets you a navigable world with combat and inventory. Everything else can be layered on incrementally.
