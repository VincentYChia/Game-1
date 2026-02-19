# Domain 6: 3D Low-Fidelity Requirements — Comprehensive Specification
**Date**: 2026-02-19
**Scope**: Every game system's 3D requirements — terrain, entities, camera, lighting, effects, UI

**Document Purpose**: Define what "low-fidelity 3D" means for EVERY game system in Game-1's Unity migration. Each system includes current state, low-fidelity target, specific Unity implementation, and acceptance criteria.

**Context**: Game-1 is currently rendering in 2D (Tilemap + SpriteRenderer). The migration plan defers 3D to "Phase IV" as an enhancement. This document elevates 3D to THE goal, with minimum viable implementations for each system.

**User's Reference Definition**: "For hostiles/combat, hostiles appear as cubes, move around, attack with a simple 3D radius, and abilities are working."

**UI Philosophy**: "The game should have a 2D overlay of inventory and UIs similar to the 2D version... Think almost Minecraft style (not in element style but in overall graphic layout)."

---

## Table of Contents

1. [Terrain & World](#1-terrain--world)
2. [Entities](#2-entities)
3. [Camera](#3-camera)
4. [Lighting](#4-lighting)
5. [Effects & Particles](#5-effects--particles)
6. [UI & World-Space Elements](#6-ui--world-space-elements)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Verification Checklist](#8-verification-checklist)

---

## 1. Terrain & World

### 1.1 Tile-Based World (Terrain Mesh)

**Current State**:
- 2D Tilemap with flat colored 1×1 pixel tiles on XY plane (rotated to look XZ)
- `WorldRenderer.cs` uses Unity Tilemap API with fallback color tiles
- Tile types: grass, water, stone, sand, cave, snow, dirt, mountain, forest
- World is 100×100 tiles, organized into 16×16 chunks

**Low-Fidelity 3D Target**:
- Each chunk becomes a single 3D mesh (16×16 quads on XZ plane)
- Each tile type has a distinct height (water -0.3, grass 0, stone +0.15, snow +0.2, mountain +0.5)
- Vertex colors per tile (no textures required, but textures can overlay)
- No LOD, no height-per-vertex variation (flat quads per tile)
- Water tiles sit lower with semi-transparent blue surface overlay

**Specific Unity Implementation**:
- **File**: `ChunkMeshGenerator.cs` (ALREADY EXISTS - 360 lines)
  - Generates mesh from tile array
  - 4 vertices per quad, vertex-colored
  - Height lookups: `TileHeights` dict maps tile type → Y offset
  - Color lookups: `GetTileColor()` returns per-tile RGB
  - Edge mesh for cliff faces between height transitions
  - Water mesh as separate overlay (semi-transparent, slightly above water tile)
- **File**: `TerrainMaterialManager.cs` (ALREADY EXISTS - 255 lines)
  - Singleton material provider
  - `TerrainMaterial`: vertex-colored, Lit shader, no instancing needed for chunks
  - `WaterMaterial`: semi-transparent, blue tint, animated wave offset
  - `EdgeMaterial`: darker version of terrain for cliff sides
  - Auto-creates fallback materials if not assigned
- **File**: `WorldRenderer.cs` (PARTIALLY UPGRADED - uses existing mesh gen)
  - `_use3DMesh` flag to toggle between 3D and legacy Tilemap
  - Chunk loading (per-chunk mesh instantiation)
  - Chunk unloading (destroy GameObjects)
  - Camera integration for chunk culling

**Changes Needed** (minimal — most code exists):
1. **Activate 3D mode** in inspector: Set `WorldRenderer._use3DMesh = true`
2. **Verify mesh generation** in `_loadChunk3D()`:
   - Extract tile array from chunk
   - Call `ChunkMeshGenerator.GenerateChunkMesh()`
   - Create MeshFilter + MeshRenderer per chunk
3. **Test water rendering** separately as overlay mesh
4. **Add collision** (optional for MVP): Use `MeshCollider` on terrain chunks (not required for movement, but improves feel)

**Acceptance Criteria**:
- [ ] Chunks render as 3D meshes instead of flat tiles
- [ ] Tile height variation is visible (stone raised, water lowered)
- [ ] Water appears as blue semi-transparent surface
- [ ] Cliff edges visible where height changes
- [ ] No z-fighting or visible seams between tiles
- [ ] Chunk loading/unloading works, player can traverse 100×100 world
- [ ] Performance: 60 FPS with 4-6 chunks loaded (each ~256 vertices, ~512 triangles)

---

### 1.2 Biome Visual Differentiation

**Current State**:
- Biome type determined by position (BiomeGenerator)
- No visual difference on terrain — all tiles same color regardless of biome
- Biome types: forest, plains, desert, snow, mountain, tundra, swamp, lava

**Low-Fidelity 3D Target**:
- Each biome has 2-3 distinct tile colors
- Tile heights vary by biome (desert flatter, mountain taller)
- Biome transitions smooth (no hard cutoff)
- Color tinting via vertex color only (no textures needed)

**Specific Unity Implementation**:
- **Extend**: `ChunkMeshGenerator.cs`
  - Add `BiomeData GetBiomeAtPosition(int chunkX, int chunkZ)` method
  - Modify `GetTileColor()` to accept biome type:
    ```csharp
    GetTileColor(string tileType, BiomeType biome)
    ```
  - Biome color shifts:
    - **Forest**: grass = darker green, water = brown tint
    - **Desert**: grass = tan/sand, stone = light brown
    - **Snow**: grass = white, stone = light blue
    - **Mountain**: stone = dark gray, grass = sparse green
    - **Swamp**: grass = dark olive, water = murky green
  - Store biome type in chunk metadata
- **Extend**: `WorldRenderer.cs`
  - Pass biome ID to `ChunkMeshGenerator` when generating mesh
  - Biome data obtained from `WorldSystem.GetChunk()` → `Chunk.BiomeType`

**Changes Needed**:
1. Modify `WorldRenderer._loadChunk3D()` to get biome from chunk
2. Update `ChunkMeshGenerator.GenerateChunkMesh()` signature to accept biome
3. Add biome color lookup table in `ChunkMeshGenerator`
4. Test color transitions at biome boundaries

**Acceptance Criteria**:
- [ ] Forest biome has green tones
- [ ] Desert biome has tan/brown tones
- [ ] Snow biome has white/blue tones
- [ ] Mountain biome has gray tones
- [ ] Biome transitions are smooth (gradient, not hard cutoff)
- [ ] Each biome is visually distinct from 2-3 tiles away

---

### 1.3 Water Tiles

**Current State**:
- Water tiles rendered as blue-colored 2D squares
- No animation, no depth, flat plane

**Low-Fidelity 3D Target**:
- Water tiles sit lower than land (-0.3 Y offset)
- Water surface is a separate semi-transparent mesh above the depressed water tile
- Optional: wave animation (sine wave offset to UV, no vertex deformation)
- Simple shader with alpha transparency

**Specific Unity Implementation**:
- **Existing**: `ChunkMeshGenerator.GenerateWaterMesh()` (COMPLETE - 60 lines)
  - Generates water surface overlay mesh
  - Water tiles only, sits at Y = -0.08
  - Separate mesh from terrain mesh
- **Existing**: `TerrainMaterialManager._createWaterMaterial()` (COMPLETE)
  - Semi-transparent blue (0.12, 0.45, 0.82, 0.85)
  - Wave shader property: `_WaveOffset` (animated in Update)
  - Blend mode: SrcAlpha / OneMinusSrcAlpha
- **Integrate** in `WorldRenderer._loadChunk3D()`:
  - After creating terrain mesh, check if chunk has water tiles
  - If yes, generate water mesh and create separate GameObject with WaterMaterial
  - Ensure water GameObject is sorted correctly (render after terrain but before entities)

**Changes Needed**:
1. Enable water mesh generation in `_loadChunk3D()`
2. Create second MeshFilter/MeshRenderer for water with `WaterMaterial`
3. Test transparency and sorting

**Acceptance Criteria**:
- [ ] Water tiles visibly lower than adjacent land
- [ ] Water surface is semi-transparent, shows color gradient (shallow = light blue, deep = dark blue)
- [ ] Water surface visible from camera angle (not clipped by terrain)
- [ ] Optional: water surface animates (subtle wave effect)
- [ ] No z-fighting between water mesh and terrain mesh

---

### 1.4 Resource Nodes (Trees, Ores, Stones)

**Current State**:
- Resource nodes are invisible in world (no visual representation)
- `ResourceRenderer.cs` exists but never instantiated
- Nodes defined in `NaturalResource.cs` with position, type, HP, required tool

**Low-Fidelity 3D Target**:
- Resource nodes appear as simple 3D shapes:
  - **Trees**: Vertical cylinder (0.3 radius, 2.0 height) with green foliage on top (cube)
  - **Ore**: Small cube (0.4 × 0.4 × 0.4) in ore color (brown/gray)
  - **Stones**: Irregular cylinder (0.5 radius, 0.8 height) in stone gray
  - **Herbs**: Small sphere (0.2 radius) in green
- All nodes have HP bar above them (world-space)
- No model files needed — use primitive shapes or billboarded sprites

**Specific Unity Implementation**:
- **File**: Create `ResourceNodeRenderer.cs` (NEW - 200-300 lines)
  - Monobehaviour component for individual resource
  - Inputs: `NaturalResource` data, 3D position
  - Renders one of:
    - **Primitive option**: `GameObject.CreatePrimitive()` for cylinder/cube/sphere
    - **Sprite billboard option**: Single quad with resource sprite, billboard-rotated via `BillboardSprite.cs`
  - Health bar: WorldSpace Canvas with Image fill component
  - Tool icon overlay (if tool required)
  - On hit: damage visual (brief red tint or impact effect)
  - On depletion: sprite fades out or cube shrinks
- **Integrate** in chunk spawning:
  - When chunk loads, get resource nodes from `WorldSystem.GetChunk().Resources`
  - Instantiate `ResourceNodeRenderer` for each resource
  - Parent to chunk container
  - On chunk unload, destroy renderers
- **Option A (simplest)**: Use billboarded sprites from existing `SpriteDatabase`
  - Tree/ore/herb sprites already exist in Python assets
  - Render as quad with `BillboardSprite.cs` component
  - Much faster than primitives, same visual result
- **Option B (next tier)**: Use simple primitive shapes
  - Cylinder for trees + cube for foliage
  - Better 3D feel, no sprites needed

**Changes Needed**:
1. Create `ResourceNodeRenderer.cs` component
2. Integrate into `WorldRenderer._loadChunk3D()` resource spawning
3. Link to `ResourceRenderer.cs` for health bar updates
4. Test interaction (E-key gather) with rendered nodes

**Acceptance Criteria**:
- [ ] Tree nodes appear as tall green objects
- [ ] Ore nodes appear as distinct colored shapes
- [ ] Resource health bars visible above nodes
- [ ] Tool requirement icon visible (if applicable)
- [ ] Nodes deplete visually when gathered
- [ ] No performance degradation with 50+ visible nodes

---

### 1.5 Crafting Stations

**Current State**:
- Crafting stations are invisible (no 3D representation)
- Stations defined in JSON: forge, alchemy_bench, refining_table, etc.
- Game tracks station location and tier (T1-T4)
- Interaction radius: 2 tiles

**Low-Fidelity 3D Target**:
- Crafting stations appear as simple 3D props:
  - **Smithing**: Brown/gray block (anvil-like) 0.8×0.8×1.0 units
  - **Alchemy**: Purple/blue cylinder with swirls on top (potion bottles)
  - **Refining**: Yellow/orange flat table with glowing edges
  - **Engineering**: Gray mechanical frame with spinning gear overlay
  - **Enchanting**: Blue/purple pillar with floating runes around it (particle effect)
- All stations glow slightly (emissive) or have point light
- Station tier affects size and intensity (T4 = 2× larger, 1.5× brighter)
- Interaction prompt above station when player is within range

**Specific Unity Implementation**:
- **File**: Create `CraftingStationRenderer.cs` (NEW - 200-250 lines)
  - Monobehaviour for individual station
  - Inputs: station type, tier, position
  - Visuals: single primitive shape or custom mesh
  - Point light component (intensity scaled by tier)
  - Emissive material with station-type color
  - Interactive highlight on proximity (color brighten or pulse)
  - Interaction prompt text (world-space)
- **Extend**: `WorldSystem.InitializeStations()`
  - Spawn station renderers for all stations
  - Set up point lights
  - Register with interaction system
- **Interaction**: When player within 2 tiles + presses E:
  - `CraftingUI` opens with correct discipline
  - Station visual highlights (outline or glow pulse)

**Changes Needed**:
1. Create `CraftingStationRenderer.cs`
2. Spawn stations in WorldSystem or GameManager
3. Link to interaction handler
4. Add point lights with tier-based intensity

**Acceptance Criteria**:
- [ ] Each station type is visually distinct (color + shape)
- [ ] Stations glow appropriately (emissive or point light)
- [ ] Station tier affects visual scale
- [ ] Interaction prompt visible when player is in range
- [ ] CraftingUI opens with correct discipline when E-pressed
- [ ] Stations don't block player movement (or have low collision)

---

### 1.6 Placed Entities (Turrets, Traps, Barriers)

**Current State**:
- Placed entities defined in data but not rendered
- `TurretSystem.cs` (674 lines) manages turret logic
- No visual representation in world

**Low-Fidelity 3D Target**:
- **Turrets**: Cone/pyramid shape pointing up, weapon type indicated by color
  - Rotating top (small spinning cube) indicating aim
  - Damage radius shown as faint circle on ground
- **Traps**: Flat square on ground with spring/spike visual
  - Color indicates trap type (red = damage, blue = freeze, etc.)
- **Barriers**: Short walls/fences (0.1 tall, 0.5 wide)
  - Semi-transparent or outline to avoid blocking vision
  - Color by material (wood = brown, stone = gray, ice = blue)

**Specific Unity Implementation**:
- **File**: Create `PlacedEntityRenderer.cs` (NEW - 250-300 lines)
  - Base class for turret/trap/barrier rendering
  - Primitive shapes: cone for turret, plane for trap, cube for barrier
  - Type-specific colors and rotations
  - Turret: animated top rotation, damage radius circle (LineRenderer or decal)
  - Trap: pulse animation
  - Barrier: static placement
- **Integrate** into world spawning:
  - When player places entity, spawn renderer
  - When player loads world, spawn all placed entities from save
  - Link to `TurretSystem` for activation/targeting updates

**Changes Needed**:
1. Create `PlacedEntityRenderer.cs`
2. Spawn placed entities on world load
3. Animate turret rotations based on system state
4. Render damage radius indicators

**Acceptance Criteria**:
- [ ] Turrets appear as distinct 3D shapes
- [ ] Traps appear as flat ground objects
- [ ] Barriers appear as short walls
- [ ] Each type is visually distinct by color
- [ ] Turret targeting visible (rotation direction)
- [ ] Damage radius visible (circle on ground)

---

### 1.7 Dungeon Environments

**Current State**:
- Dungeons defined in dungeon-config JSON
- No visual differentiation from surface world
- Dungeon entrance tracked but invisible

**Low-Fidelity 3D Target**:
- Dungeon tiles appear different from surface:
  - Cave tiles: darker, rocky (dark gray vertices)
  - Lava tiles: bright orange/red, flickering light effect
  - Ice tiles: bright cyan/white with icy glow
- Entrance portal: floating ring or spiral effect
- Dungeon lighting: dimmer ambient, point lights for enemy spawn areas

**Specific Unity Implementation**:
- **Extend**: `ChunkMeshGenerator.GetTileColor()`
  - Check if chunk is dungeon
  - Apply dungeon-specific colors (darker, more saturated)
  - Dungeon flag stored in `Chunk.IsDungeon` or `BiomeType.Dungeon`
- **Create**: `DungeonEntranceRenderer.cs` (NEW - 100-150 lines)
  - Floating ring mesh (torus) or spiral quad mesh
  - Particle effect (portal vortex)
  - Glow shader or point light
  - Interaction prompt when player is on entrance tile
- **Lighting**: Modify `DayNightOverlay`
  - Check if player is in dungeon
  - Use darker ambient light in dungeon
  - No directional light rotation (always dark)

**Changes Needed**:
1. Mark chunks as dungeon in world generation
2. Modify tile coloring for dungeon tiles
3. Create entrance portal renderer
4. Adjust lighting for dungeon zones

**Acceptance Criteria**:
- [ ] Dungeon tiles visibly different from surface
- [ ] Entrance portal appears as distinct structure
- [ ] Dungeon areas are darker
- [ ] Interaction prompt on entrance tile
- [ ] Portal effect animates (particles, glow)

---

### 1.8 Environmental Effects

**Current State**:
- Day/night cycle via screen overlay (2D)
- No weather, no environmental hazards, no seasonal variation

**Low-Fidelity 3D Target**:
- **Day/Night**: Replace screen overlay with directional light rotation (ALREADY PLANNED)
- **Fog**: Simple height fog or distance fog in dungeons (optional for MVP)
- **Weather**: Optional — rain particles, snow particles in appropriate biomes (future)
- **Hazards**: Lava tiles damage over time, ice slow, toxic gas clouds (visual only, logic exists)

**Specific Unity Implementation**:
- **Existing**: `DayNightOverlay.cs` (269 lines)
  - `_sunLight`: directional light that rotates through day
  - Already calculates sun angle and color
  - Adjusts ambient light color
  - Just need to ensure it's active (not just screen overlay)
- **Optional**: Add `RenderSettings.fog` in dungeon zones
  - Unity built-in fog system
  - Fog color matches dungeon atmosphere
  - No custom code needed
- **Optional**: `HazardRenderer.cs` for lava/gas visual effects
  - Particle effect over hazard tiles
  - Orange/red for lava, green for gas
  - Spawned per chunk

**Changes Needed**:
1. Ensure `DayNightOverlay._use3DLighting = true` in scene
2. Test sun rotation and ambient light transitions
3. Optional: Add fog zones for dungeons

**Acceptance Criteria**:
- [ ] Directional light rotates through day/night cycle
- [ ] Ambient light color changes with day progress
- [ ] Shadows visible and rotate with sun
- [ ] Night is noticeably darker than day
- [ ] Optional: Fog visible in dungeons

---

## 2. Entities

### 2.1 Player Character

**Current State**:
- Rendered as cyan square (placeholder SpriteRenderer)
- Facing direction: up/down/left/right sprites or flipX
- No 3D model, no animations
- Height above terrain: configurable offset (0.5 units)

**Low-Fidelity 3D Target**:
- Player appears as:
  - **Option A (simplest)**: Billboarded sprite that always faces camera (via `BillboardSprite.cs`)
  - **Option B (next tier)**: Cylinder with head/body shape (3 stacked primitives: yellow, purple, skin)
  - **Option C (future)**: 3D character model (humanoid with arms, legs, equipment)
- Visual feedback:
  - Color change when damaged (red tint)
  - Shadow blob under player (auto-created by `BillboardSprite`)
  - Equipment visible on body (sword in hand, armor tint)
- No facial animation, no complex rigging

**Specific Unity Implementation**:
- **File**: Extend `PlayerRenderer.cs` (currently 154 lines)
  - Already uses `BillboardSprite` component (lines 68-70)
  - Already sets height above terrain (lines 122-124)
  - For **Option A**: Billboard is complete, just ensure sprite is imported
  - For **Option B**: Replace sprite with 3D cylinder assembly:
    ```csharp
    // Create simple 3D player shape
    var body = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
    body.transform.localScale = new Vector3(0.3f, 0.8f, 0.3f); // thin cylinder
    var head = GameObject.CreatePrimitive(PrimitiveType.Sphere);
    head.transform.localPosition = new Vector3(0, 0.6f, 0);
    head.transform.localScale = Vector3.one * 0.3f;
    ```
  - Remove SpriteRenderer, keep BillboardSprite for shadows/rotation
- **Equipment Visibility**: When equipment changes
  - Swap material/color on body parts
  - Add weapon visual (small cube) in hand position
  - Shield visual on arm (optional)

**Changes Needed**:
1. For Option A: Ensure player sprite is imported and assigned
2. For Option B: Create 3D shape assembly in PlayerRenderer
3. Test equipment visibility
4. Test damage flash (red tint on hit)

**Acceptance Criteria**:
- [ ] Player visible as distinct 3D shape
- [ ] Shadow blob under player
- [ ] Facing direction maintained (if using sprites)
- [ ] Equipment visible on player body
- [ ] Damage dealt → red flash for 0.2s
- [ ] Camera follows player correctly

---

### 2.2 Enemies (50+ Types Across 4 Tiers)

**Current State**:
- Enemies defined in hostiles-1.JSON (50+ types)
- Rendered as sprites from SpriteDatabase
- No 3D representation
- Health bar above enemy
- Multiple tiers: T1-T4 with stat scaling
- Boss enemies 1.5× larger

**Low-Fidelity 3D Target** (per user example):
- Enemy appears as simple 3D shape:
  - **Option A (simplest, per user's example)**: Colored cube (0.4 × 0.4 × 0.8)
    - Color by enemy type (red = aggressive, blue = magic, green = ranged, brown = melee)
    - Size scales by tier: T1 = 1.0×, T2 = 1.2×, T3 = 1.4×, T4 = 1.6×
    - Boss flag: 1.5× size, glow effect
  - **Option B (next tier)**: Cylinder with head (stacked primitives)
  - **Option C (future)**: Billboarded sprite (2.5D, same as player)
- **Attack visual**: Line or cone extending from enemy to target when attacking
- **Movement**: Smooth path from current position to target
- **Death**: Fade out and disappear (corpse fades over 2 seconds)

**Specific Unity Implementation**:
- **File**: Extend `EnemyRenderer.cs` (currently 177 lines, already billboards!)
  - Already has health bar, death fade, shadows
  - Currently uses SpriteRenderer
  - Replace sprite with 3D primitive:
    ```csharp
    // In Initialize()
    var shape = GameObject.CreatePrimitive(PrimitiveType.Cube);
    shape.transform.SetParent(transform);
    shape.transform.localScale = new Vector3(0.4f, 0.8f, 0.4f);
    shape.GetComponent<MeshRenderer>().material.color = GetEnemyColor(enemyId, tier);
    // Remove collider
    Destroy(shape.GetComponent<Collider>());
    ```
  - Keep BillboardSprite for proper 3D positioning
  - Scale adjustment for tiers already exists (line 91, `transform.localScale`)
- **Enemy Color** by type:
  - Get enemy type from `enemyId` (e.g., "goblin", "skeleton")
  - Map to color: melee = brown, ranged = green, magic = blue, aggressive = red, boss = gold
- **Attack visual**: Drawn by `AttackEffectRenderer.cs` (already exists!)
  - Line from attacker to target
  - Already in place, just needs to be called by CombatManager

**Changes Needed**:
1. Modify `EnemyRenderer.Initialize()` to create 3D shape instead of loading sprite
2. Add color lookup by enemy type
3. Ensure tier scaling applied correctly
4. Test boss visuals (larger, glow)
5. Wire `AttackEffectRenderer` calls into combat system

**Acceptance Criteria**:
- [ ] Enemy appears as colored 3D shape
- [ ] Color indicates enemy type (red = dangerous, etc.)
- [ ] Size scales by tier
- [ ] Boss enemies visibly larger and distinct
- [ ] Shadow blob under enemy
- [ ] Health bar visible above enemy
- [ ] Attack line visible when enemy attacks
- [ ] Death fade smooth and complete
- [ ] 50+ enemies visible simultaneously without major FPS drop

---

### 2.3 NPCs

**Current State**:
- NPCs defined in npcs-1.JSON
- Not rendered or spawned
- Quest givers, shop keepers, story NPCs

**Low-Fidelity 3D Target**:
- NPCs appear as:
  - **Option A (simplest)**: Taller cylinder (0.3 × 1.2) with distinct color (purple or robes)
  - **Option B (next)**: Humanoid shape (head + body)
  - **Option C (future)**: Billboarded human sprite
- Visual indicators:
  - Quest marker (!) above NPC if player has available quest
  - Shop indicator ($) if NPC is merchant
  - Name label above NPC
  - Glow or highlight on proximity (interaction range)

**Specific Unity Implementation**:
- **File**: Create `NPCRenderer.cs` (NEW - 150-200 lines)
  - Similar to EnemyRenderer but for NPCs
  - 3D primitive shape (cylinder, distinct color)
  - World-space Canvas for name + quest/shop icons
  - No health bar, no damage feedback
  - Glow effect on player proximity (material brightness increase)
  - Interaction prompt: "Press E to talk"
- **Integrate**: Spawn NPCs on world init
  - Query `NPCDatabase.GetAllNPCs()`
  - Spawn renderer at NPC position
  - Register with interaction system

**Changes Needed**:
1. Create `NPCRenderer.cs`
2. Spawn NPCs in GameManager.StartNewGame()
3. Add quest marker visibility toggle
4. Test interaction flow (E-key → dialogue opens)

**Acceptance Criteria**:
- [ ] NPCs visible at their spawned positions
- [ ] Distinct visual from enemies (different color, shape)
- [ ] Name label visible above NPC
- [ ] Quest marker visible if quest available
- [ ] Interaction prompt visible in range
- [ ] Dialogue UI opens on E-press

---

### 2.4 Corpses & Loot Drops

**Current State**:
- When enemy dies, loot should appear
- No visual representation of corpse or loot
- Loot stored in WorldSystem or saved to map

**Low-Fidelity 3D Target**:
- **Corpse**: Enemy body fades out over 2 seconds (ALREADY DONE in EnemyRenderer)
- **Loot drop**: Items appear as small glowing cubes or spheres
  - Golden glow for rarity (green = common, blue = uncommon, purple = rare, orange = epic, red = legendary)
  - Slight bounce/float animation
  - Interaction prompt: "Press E to loot"
- **Loot chest**: Wooden chest model (box) when death drop occurs
  - Opens on interaction
  - Lists items (Inventory-style UI)

**Specific Unity Implementation**:
- **File**: Create `LootDropRenderer.cs` (NEW - 150-200 lines)
  - Spawned on enemy death
  - Small sphere or cube, material color by rarity
  - Point light for glow (intensity by rarity)
  - Gentle bob animation (sine wave Y offset)
  - Interaction: Press E → `ChestUI` opens with loot
- **Loot Chest**: Create `LootChestRenderer.cs` (NEW - 100-150 lines)
  - Cube-based chest visual (0.6 × 0.3 × 0.4 box with hinged lid)
  - Lid rotates open on interaction
  - Interior shows items as grid
- **Integration**:
  - When enemy dies, get loot table from `Enemy.GetLoot()`
  - Create `LootDropRenderer` or `LootChestRenderer` at enemy death position
  - Register with interaction system
  - On loot pickup, delete renderer and add items to player inventory

**Changes Needed**:
1. Create `LootDropRenderer.cs`
2. Create `LootChestRenderer.cs`
3. Spawn on enemy death in CombatManager
4. Test rarity coloring
5. Test interaction and inventory addition

**Acceptance Criteria**:
- [ ] Loot appears as glowing object at death location
- [ ] Color matches item rarity
- [ ] Glow intensity visible
- [ ] Interaction prompt appears on proximity
- [ ] ChestUI/InventoryUI opens on E-press
- [ ] Items transfer to player inventory correctly
- [ ] Multiple loot drops don't overlap visually

---

### 2.5 Training Dummies

**Current State**:
- Not implemented
- Concept: NPCs that enemies don't attack, players use for practice

**Low-Fidelity 3D Target**:
- Dummy appears as simple wooden structure:
  - Tall post (0.2 × 1.5 cylinder, tan/brown color)
  - Crossbar with target circles (wooden beam)
  - Bullseye on front (concentric circles painted on)
- Damage numbers visible but dummy doesn't die
- Reset button or auto-heals after 10 seconds

**Specific Unity Implementation**:
- **File**: Create `TrainingDummyRenderer.cs` (NEW - 100-150 lines)
  - Similar to enemy renderer but no health tracking
  - Cylinder + cube for beam
  - Texture or material for bullseye pattern
  - Damage feedback: brief shake or color flash
  - Optional: health bar that resets after 10 seconds
- **Integration**: Spawn in dedicated training area or on demand

**Changes Needed**:
1. Create `TrainingDummyRenderer.cs`
2. Spawn in training area or via command
3. Test damage feedback
4. Test health reset

**Acceptance Criteria**:
- [ ] Dummy appears as distinct wooden structure
- [ ] Damage numbers visible
- [ ] Dummy doesn't die
- [ ] Damage feedback visual (flash or shake)
- [ ] Health resets after timeout

---

## 3. Camera

### 3.1 Perspective Camera with Configurable Angle

**Current State**:
- Orthographic camera at Y = 50, looking straight down (90° pitch)
- No rotation, no zoom (only zoom via orthographic size)
- Top-down 2D view
- ScreenToWorldXZ works by ray-casting to Y=0 plane

**Low-Fidelity 3D Target**:
- Perspective camera in 3D world
- Default: ~45° pitch (neither top-down nor eye-level)
- Distance: ~18 units from player
- Follows player position smoothly (no snapping)
- Zoom support: scroll wheel adjusts distance (6-40 units)
- Orbit support: right-click drag rotates yaw (0-360°)
- Reset to default orientation (Home key)

**Specific Unity Implementation**:
- **File**: `CameraController.cs` (ALREADY EXISTS - 343 lines, COMPLETE)
  - `_orthographic`: Toggle between ortho and perspective
  - `_pitch`: Vertical angle (20-85°, default 50°)
  - `_yaw`: Horizontal angle (0-360°)
  - `_distance`: Distance from player (6-40)
  - `_heightOffset`: Extra height above target (1.0)
  - Smooth follow, smooth yaw/pitch interpolation
  - Zoom on mouse wheel
  - Orbit on right-click drag
  - `ScreenToWorldXZ()` works with perspective rays
- **Integration**: In `GameManager` or `InputManager`:
  - Detect scroll input → `CameraController.Zoom()`
  - Detect right-click drag → `CameraController.OrbitHorizontal()` / `OrbitVertical()`
  - Player position update → `CameraController.SetTarget()`

**Changes Needed**:
1. Set `_orthographic = false` in inspector
2. Test perspective rendering
3. Wire input handlers (scroll, right-click)
4. Test `ScreenToWorldXZ()` with perspective rays
5. Adjust `_pitch` to desired default (45° or 50°)

**Acceptance Criteria**:
- [ ] Camera renders in perspective mode
- [ ] Pitch is not 90° (not top-down)
- [ ] Camera follows player position smoothly
- [ ] Scroll wheel zooms in/out
- [ ] Right-click drag rotates camera around player
- [ ] World UI elements (tooltips, prompts) positioned correctly
- [ ] Player/enemies/objects not clipped by near plane
- [ ] Framerate stable in perspective mode

---

### 3.2 Camera Clipping & Culling

**Current State**:
- Orthographic camera sees entire loaded world
- No near/far plane issues
- Chunk culling based on camera position

**Low-Fidelity 3D Target**:
- Perspective camera with proper near/far planes:
  - **Near plane**: 0.3 units (close to player)
  - **Far plane**: 500 units (far enough to see all chunks)
- Frustum culling: Only render chunks in camera view
- No terrain behind player visible

**Specific Unity Implementation**:
- **File**: `CameraController.cs` Start() method
  - Already sets: `_camera.nearClipPlane = 0.3f; _camera.farClipPlane = 500f;`
  - Chunk culling via `WorldRenderer._chunkLoadRadius` / `_chunkUnloadRadius`
  - Frustum check: `CameraController.GetVisibleBounds()` returns screen footprint
- **Integration**: Already integrated, no changes needed

**Changes Needed**: None — already implemented

**Acceptance Criteria**:
- [ ] No terrain clipping near camera
- [ ] Distant chunks visible up to 500 units
- [ ] Chunks outside frustum not rendering
- [ ] Framerate maintains with large draw distance

---

## 4. Lighting

### 4.1 Day/Night Cycle (Directional Light)

**Current State**:
- Screen overlay with color tint (2D)
- No 3D lights
- Overlay colors: dawn=orange, day=white, dusk=orange, night=dark blue

**Low-Fidelity 3D Target**:
- Directional light (sun) rotates through sky during day
- Light color changes: warm at dawn/dusk, neutral at day, dim at night
- Shadows visible on terrain and entities
- Ambient light color cycles too (warm to cool)
- Night is noticeably darker than day

**Specific Unity Implementation**:
- **File**: `DayNightOverlay.cs` (ALREADY EXISTS - 269 lines, COMPLETE)
  - `_sunLight`: Directional light component
  - `_updateSunLight()`: Rotates light, updates color/intensity
  - Light angle: 0° = dawn (horizon east), 90° = midday, 180° = dusk (horizon west)
  - Color: dawn = orange (1, 0.7, 0.4), day = white (1, 0.96, 0.92), night = dark blue (0.15, 0.15, 0.3)
  - Intensity: day = 1.2, dawn/dusk = 0.6, night = 0.08
  - `_updateAmbientLight()`: Sets `RenderSettings.ambientLight` color
  - Screen overlay still applies (reduced by 50% in 3D mode)
- **Integration**: Already integrated
  - `_use3DLighting = true` enables sun light
  - Update loop already rotates light based on day progress

**Changes Needed**:
1. Set `_use3DLighting = true` in inspector
2. Ensure `_sunLight` is assigned (auto-created if null)
3. Test light rotation speed (adjust sun angle formula if needed)
4. Test shadow quality and performance

**Acceptance Criteria**:
- [ ] Directional light visible (shadows on terrain)
- [ ] Light color changes with day progress
- [ ] Day is bright, night is dim
- [ ] Shadows rotate with sun
- [ ] Ambient light color cycles (warm day, cool night)
- [ ] No harsh transitions between day phases
- [ ] Shadow strength doesn't cause excessive performance impact

---

### 4.2 Ambient Lighting

**Current State**:
- Flat ambient from orthographic rendering
- No RenderSettings.ambientLight adjustment

**Low-Fidelity 3D Target**:
- Ambient light color cycles with day progress
- Day: neutral gray (0.5, 0.5, 0.5)
- Dawn/dusk: warm (0.4, 0.35, 0.45)
- Night: cool dark (0.08, 0.08, 0.15)
- Smooth transitions between phases

**Specific Unity Implementation**:
- **File**: `DayNightOverlay.cs`
  - `_updateAmbientLight()` method (lines 190-220)
  - Sets `RenderSettings.ambientMode = AmbientMode.Flat`
  - Sets `RenderSettings.ambientLight = color`
  - Already interpolates between phases smoothly
- **Integration**: Called every frame in Update()

**Changes Needed**: None — already implemented

**Acceptance Criteria**:
- [ ] Ambient light is visible and colored
- [ ] Day has neutral bright ambient
- [ ] Night has cool dark ambient
- [ ] Transitions smooth over ~10 minutes (game time)
- [ ] Ambient color affects overall scene brightness appropriately

---

### 4.3 Point Lights (Crafting Stations, Campfires)

**Current State**:
- No point lights
- Crafting stations don't glow

**Low-Fidelity 3D Target**:
- Crafting station emits point light:
  - **Smithing**: Orange/red glow (forge fire)
  - **Alchemy**: Purple/blue glow (magical)
  - **Refining**: Yellow glow (heating)
  - **Engineering**: Green glow (mechanical)
  - **Enchanting**: Blue glow (magical)
- Light intensity scaled by station tier (T1 = 1.0, T4 = 2.0)
- Radius: ~5 units
- Soft shadows

**Specific Unity Implementation**:
- **File**: Extend `CraftingStationRenderer.cs` (TO BE CREATED)
  - In constructor, create child Light component:
    ```csharp
    var lightGO = new GameObject("Light");
    var light = lightGO.AddComponent<Light>();
    light.type = LightType.Point;
    light.range = 5f * tierScale;
    light.intensity = tierScale;
    light.color = GetStationColor(stationType);
    light.shadows = LightShadows.Soft;
    ```
  - Enable/disable light based on nearby player or always-on
- **Optional**: Pulsing animation
  - Sine wave modulation of intensity
  - `light.intensity = baseIntensity * (0.8f + 0.2f * Sin(time * 2))`

**Changes Needed**:
1. Add Light component creation in `CraftingStationRenderer`
2. Set color per station type
3. Test shadow quality and FPS impact
4. Optional: Add pulsing animation

**Acceptance Criteria**:
- [ ] Crafting stations emit colored light
- [ ] Light color matches station type
- [ ] Light radius appropriate (doesn't extend too far)
- [ ] Tier affects light intensity
- [ ] Shadows visible on nearby terrain/entities
- [ ] Point lights don't cause FPS issues (max 5-6 lights visible)

---

### 4.4 Fog (Optional for MVP, Recommended for Dungeons)

**Current State**:
- No fog
- Far plane at 500 units, far terrain visible

**Low-Fidelity 3D Target** (Optional):
- Distance fog in dungeons
- Fog color matches dungeon atmosphere (dark, murky)
- Fog start: 10 units, fog end: 30 units
- No fog in surface world (or very light)

**Specific Unity Implementation**:
- **File**: Extend `DayNightOverlay.cs` or create `FogController.cs`
  - Check if player is in dungeon
  - Set `RenderSettings.fog = true` in dungeon
  - Set `RenderSettings.fogMode = FogMode.Linear`
  - Set `RenderSettings.fogColor` to dungeon color (dark blue/gray)
  - Set `RenderSettings.fogStartDistance = 10f`
  - Set `RenderSettings.fogEndDistance = 30f`
- **Integration**: Update every frame or on dungeon entry

**Changes Needed**:
1. Create `FogController.cs` or extend `DayNightOverlay`
2. Detect dungeon presence
3. Toggle fog on/off
4. Test fog rendering

**Acceptance Criteria**:
- [ ] Fog visible in dungeons (not surface)
- [ ] Fog color matches atmosphere
- [ ] Distant objects fade smoothly
- [ ] No performance impact

---

## 5. Effects & Particles

### 5.1 Damage Numbers (Floating Text)

**Current State**:
- `DamageNumberRenderer.cs` (150 lines) renders floating text
- Uses TextMeshPro with world-space positioning
- Numbers float upward and fade
- Color by damage type

**Low-Fidelity 3D Target**:
- Same as current, but in 3D world space (not 2D overlay)
- Numbers appear above entity, float up, fade out
- Color: white = physical, red = fire, blue = ice, purple = poison, yellow = lightning
- Critical damage: 1.5× larger, red color, exclamation point

**Specific Unity Implementation**:
- **File**: `DamageNumberRenderer.cs` (ALREADY EXISTS - 150 lines)
  - Already uses world-space positioning
  - Already colors by damage type
  - Already floats and fades
  - Just needs to be called by combat system
- **Integration**: In `CombatManager.DealDamage()`
  - Call `DamageNumberRenderer.Instance.SpawnDamageNumber(position, damage, isCrit, damageType)`
  - Position: target entity position + small random offset

**Changes Needed**:
1. Wire `CombatManager` to call `DamageNumberRenderer.SpawnDamageNumber()`
2. Test color mapping
3. Test pool recycling (30 numbers max)

**Acceptance Criteria**:
- [ ] Damage numbers appear above hit target
- [ ] Numbers float upward smoothly
- [ ] Numbers fade out over 1.5 seconds
- [ ] Color matches damage type
- [ ] Critical hits are visually distinct (larger, different color)
- [ ] Pool reuses objects, no garbage collection hiccups

---

### 5.2 Attack Effects (Slash, Impact, Beams)

**Current State**:
- `AttackEffectRenderer.cs` (172 lines) draws line effects
- Supports attack lines (melee), AoE circles, beams
- Lines fade over duration

**Low-Fidelity 3D Target**:
- Melee attack: Line from attacker to target, brief flash
- Ranged attack: Line with arrow-like marker
- AoE effect: Circle on ground showing damage radius
- Beam effect: Thick line from source to target, color by element type
- All effects fade smoothly

**Specific Unity Implementation**:
- **File**: `AttackEffectRenderer.cs` (ALREADY EXISTS - 172 lines, COMPLETE)
  - `DrawAttackLine()`: Line from A to B, fades
  - `DrawAoECircle()`: Circle on ground, fades
  - `DrawBeam()`: Thick line, fades
  - LineRenderers positioned at Y = 0.5 (above terrain, visible)
- **Integration**: In `CombatManager` / `EffectExecutor`:
  - On skill activation, call `AttackEffectRenderer.DrawAttackLine()` or `DrawBeam()`
  - On AoE skill, call `DrawAoECircle()`
  - Color by element/skill type

**Changes Needed**:
1. Wire combat system to call `AttackEffectRenderer` methods
2. Assign colors per damage type
3. Test line visibility from camera angle
4. Test AoE circle positioning

**Acceptance Criteria**:
- [ ] Attack lines visible between attacker and target
- [ ] AoE circles visible on ground
- [ ] Colors match element type (fire = orange, ice = blue, etc.)
- [ ] Effects fade smoothly
- [ ] No z-fighting with terrain
- [ ] Multiple effects visible simultaneously

---

### 5.3 Skill Effects (Fire, Ice, Lightning, Poison)

**Current State**:
- No visual effects for skills
- `ParticleEffects.cs` (322 lines) can spawn particles

**Low-Fidelity 3D Target**:
- Skill activation spawns particle effect:
  - **Fire**: Orange/red burst, upward bias, sparks
  - **Ice**: Blue/cyan burst, floats down, snowflake-like
  - **Lightning**: Yellow/white beam, branching effect
  - **Poison**: Green cloud, expands outward, lingering
  - **Holy**: White/gold burst, upward
  - **Shadow**: Dark purple, downward
- Effect spawns at target position or between caster and target
- Effect lasts 0.5-2.0 seconds
- Loops if effect duration > particle lifetime

**Specific Unity Implementation**:
- **File**: `ParticleEffects.cs` (ALREADY EXISTS - 322 lines, COMPLETE)
  - `PlaySparks()`: Orange sparks (smithing, but can be fire)
  - `PlayEmbers()`: Orange embers (heating, but can be fire AoE)
  - Custom call methods for each element:
    ```csharp
    public void PlayFireBurst(Vector3 position)
        => _playEffect(_fireExplosionPrefab, position, 30);
    public void PlayIceShatter(Vector3 position)
        => _playEffect(_icePrefab, position, 20);
    public void PlayLightningBolt(Vector3 from, Vector3 to)
        => /* beam effect */;
    ```
  - Particles already auto-created if prefabs not assigned
- **Integration**: In `EffectExecutor._ExecuteEffect()` or `CombatManager.ApplyEffect()`:
  - Check effect tag (e.g., "fire")
  - Call `ParticleEffects.PlayFireBurst(position)`

**Changes Needed**:
1. Extend `ParticleEffects` with per-element methods
2. Wire `EffectExecutor` to call particle methods
3. Create particle prefabs (optional, fallback system exists)
4. Test effect timing with skill cooldowns
5. Test visual clarity (not too many particles)

**Acceptance Criteria**:
- [ ] Fire skills spawn orange particle burst
- [ ] Ice skills spawn blue particle burst
- [ ] Lightning skills spawn yellow/white particles
- [ ] Poison skills spawn green expanding cloud
- [ ] Holy skills spawn white burst
- [ ] Shadow skills spawn dark particles
- [ ] Effects don't obscure gameplay
- [ ] Multiple effects visible without FPS drop

---

### 5.4 Crafting Minigame Effects

**Current State**:
- `ParticleEffects.cs` has prefabs for crafting:
  - Sparks (smithing)
  - Bubbles (alchemy)
  - Embers (refining)
  - Gears (engineering)
  - Runes (enchanting)

**Low-Fidelity 3D Target**:
- Minigame progress → visible particle effect at crafting station
- **Smithing**: Sparks fly from anvil
- **Alchemy**: Bubbles rise from potion
- **Refining**: Embers glow
- **Engineering**: Gears spin
- **Enchanting**: Runes glow and spiral
- Effects play during minigame, intensify on success

**Specific Unity Implementation**:
- **File**: `ParticleEffects.cs` + per-minigame UI
  - Methods already exist: `PlaySparks()`, `PlayBubbles()`, etc.
  - Extend minigame UIs to call particle methods
- **Integration**: In each minigame UI Update():
  - If minigame active, spawn effect every frame (or every few frames)
  - On success, spawn success effect (`PlayCraftSuccess()`)
  - On failure, spawn fail effect (red particles or shake)

**Changes Needed**:
1. Extend minigame UI files to call `ParticleEffects` methods
2. Integrate with crafting progress
3. Add success/fail effects
4. Test effect frequency (not too many, not too few)

**Acceptance Criteria**:
- [ ] Crafting station emits effect during minigame
- [ ] Effect matches discipline (sparks for smithing, etc.)
- [ ] Effect intensity matches minigame difficulty
- [ ] Success effect distinct from normal effect
- [ ] Effects visible from camera angle

---

### 5.5 Status Effect Indicators

**Current State**:
- Status effects apply (burn, bleed, poison, freeze, etc.)
- No visual indicator on entity
- Text UI shows active effects

**Low-Fidelity 3D Target**:
- Entity body tinted by active status effect:
  - **Burn**: Red glow, flickering intensity
  - **Bleed**: Dark red tint, slow ooze particles
  - **Poison**: Green glow + particles
  - **Freeze**: Blue tint, icy particles
  - **Stun**: Yellow glow, stars circling head
  - **Slow**: Purple tint
  - **Invisible**: Translucent (alpha = 0.3)
- Icons above entity showing active effects (UI)
- Effect duration shown as progress bar above entity

**Specific Unity Implementation**:
- **File**: Extend `EnemyRenderer.cs` + `PlayerRenderer.cs`
  - In Update(), check `Character.BuffManager.ActiveBuffs`
  - Modify material color based on buff:
    ```csharp
    Color tint = Color.white;
    foreach (var effect in activeEffects) {
        switch (effect.Type) {
            case StatusEffect.Burn: tint = Color.Lerp(tint, Color.red, 0.3f); break;
            case StatusEffect.Poison: tint = Color.Lerp(tint, Color.green, 0.3f); break;
            // ...
        }
    }
    meshRenderer.material.color = tint;
    ```
  - Optional: Particle effect for each status (already have particles)
  - Icons via world-space Canvas above entity
- **Integration**: Already have `StatusEffect` data in character components

**Changes Needed**:
1. Extend entity renderers to apply status tints
2. Query active effects from character
3. Create icon prefab for status display
4. Instantiate/update icons above entity

**Acceptance Criteria**:
- [ ] Burning entity glows red
- [ ] Poisoned entity glows green
- [ ] Frozen entity glows blue
- [ ] Status tints are subtle (not overwhelming)
- [ ] Multiple status effects visible together
- [ ] Icons above entity show active effects
- [ ] Duration bar shows effect remaining time

---

## 6. UI & World-Space Elements

### 6.1 Health Bars (Enemies, Resources)

**Current State**:
- `EnemyRenderer.cs` has health bar (lines 32-39, 102-120)
- Uses world-space Canvas with Image fill
- Bar above enemy, updates on health change
- Hidden when full health, shown when damaged

**Low-Fidelity 3D Target**:
- Same visual, but ensure compatibility with 3D camera
- Bar always faces camera (world-space Canvas rotates)
- Bar positioned above entity correctly in 3D
- Color: green = full health, yellow = half, red = low health

**Specific Unity Implementation**:
- **File**: `EnemyRenderer.cs` (ALREADY EXISTS)
  - Lines 169-173: Billboard health bar to camera
  - `_worldCanvas.transform.rotation = Camera.main.transform.rotation`
  - Already implemented correctly
  - Same approach for `ResourceRenderer.cs` (lines 124-131)
- **Resource Bars**: `ResourceRenderer.cs` (ALREADY EXISTS, 134 lines)
  - Same health bar system as enemies
  - Color: green = full, gray = depleted

**Changes Needed**: None — already implemented for 3D

**Acceptance Criteria**:
- [ ] Health bars visible above entities in 3D
- [ ] Bars face camera correctly
- [ ] Bars update when entity takes damage
- [ ] Color changes with health level
- [ ] Bars positioned correctly (no overlap with entity)

---

### 6.2 Interaction Prompts (World-Space)

**Current State**:
- No interaction prompts
- No visual feedback for interaction range

**Low-Fidelity 3D Target**:
- Text prompt "Press E" appears when player within interaction range (2 tiles)
- Prompt appears above entity:
  - Crafting station: "Press E to craft"
  - Resource: "Press E to gather"
  - NPC: "Press E to talk"
  - Chest: "Press E to loot"
- Text is world-space, faces camera
- Highlights when player is very close (1 tile)

**Specific Unity Implementation**:
- **File**: Create `InteractionPromptRenderer.cs` (NEW - 100-150 lines)
  - World-space Canvas with TextMeshPro text
  - Positioned above entity
  - Rotates to face camera
  - Appears only when player in range
  - Color changes on close proximity
- **Integration**: In interaction system (to be created):
  - Check nearby entities every frame
  - Show/hide prompt based on range
  - Update prompt text per entity type
- **Alternative**: Use 3D text or billboard instead of Canvas

**Changes Needed**:
1. Create `InteractionPromptRenderer.cs`
2. Create interaction system that tracks nearby entities
3. Show/hide prompts based on distance
4. Wire to entity types (station, resource, NPC, chest)

**Acceptance Criteria**:
- [ ] Prompt visible when player in range (2 tiles)
- [ ] Prompt text matches entity type
- [ ] Prompt faces camera
- [ ] Prompt hidden when out of range
- [ ] Prompt highlights on very close proximity

---

### 6.3 2D UI Panels (Screen-Space Overlay)

**Current State**:
- StartMenu, ClassSelection, StatusBar, Notifications, DebugOverlay, DayNight panels created (partial)
- Missing: Inventory, Equipment, Crafting, Stats, SkillBar, Tooltip, Map, Encyclopedia, NPC, Chest, Minigames

**Low-Fidelity 3D Target** (Minecraft-style 2D overlay):
- All UI remains 2D, on top of 3D world
- Screen-space Canvas (not world-space)
- Panels arranged:
  - **Top-left**: Health/mana bar, buffs
  - **Top-right**: Minimap
  - **Bottom-left**: Hotbar (skills 1-9)
  - **Bottom-right**: Inventory (Tab key)
  - **Center**: Equipment/stats panels (on demand)
  - **Center**: Crafting UI (when at station)
  - **Center**: NPC dialogue (when talking)
  - **Top-center**: Notifications, damage numbers (floating text)
  - **Center**: Damage numbers (world-space)
- Panels have dark background with borders (Minecraft-style: flat, grid-like)
- No complex animations, just show/hide

**Specific Unity Implementation**:
- **File**: Most UI panels already exist (18 UI components listed in UNITY_MIGRATION_CHECKLIST)
  - Just need to be wired into scene and game flow
- **Scene Structure**:
  - `Canvas` (Screen Space Overlay)
    - `StatusBar` (top-left)
    - `SkillBar` / `HotbarUI` (bottom-left)
    - `InventoryUI` (bottom-right, hidden by default)
    - `EquipmentUI` (right side, hidden by default)
    - `StatsUI` (right side, hidden by default)
    - `CraftingUI` (center, hidden by default)
    - `MapUI` (top-right, hidden by default)
    - `NPCDialogueUI` (center, hidden by default)
    - `ChestUI` (center, hidden by default)
    - `SkillUnlockUI` (center, hidden by default)
    - `TitleUI` (center, hidden by default)
    - `NotificationsUI` (top-center)
    - `TooltipRenderer` (top-left, under mouse)
  - `DamageNumberCanvas` (World Space, for floating text)
- **Panel Styling**: Dark background, grid-like borders
  - Background: Semi-transparent dark (0, 0, 0, 0.7)
  - Border: Thin light line (gray, 1-2 pixels)
  - Text: White TextMeshPro, size 12-16

**Changes Needed**:
1. Create missing UI panels (Extend Game1Setup.cs to instantiate all)
2. Wire Tab key to toggle InventoryUI
3. Wire C key to toggle CraftingUI (if at station)
4. Wire E key to open NPC/Chest/etc UIs
5. Style panels consistently (dark + border)
6. Test layout (no UI overlap, visible hotbar)

**Acceptance Criteria**:
- [ ] All UI panels visible in scene (created or instantiated)
- [ ] Tab opens/closes inventory
- [ ] E-key opens appropriate UI (crafting, NPC, etc.)
- [ ] Hotbar visible bottom-left with skill icons
- [ ] Health/mana bars visible top-left
- [ ] No UI overlap or cutoff
- [ ] Damage numbers visible floating over entities
- [ ] Consistent visual style (Minecraft-like)

---

## 7. Implementation Roadmap

**Recommended Priority Order** (based on dependencies and visual impact):

### Phase 1: Core 3D Foundation (Days 1-2, ~10 hours)
1. Camera: Switch to perspective (CameraController already ready)
2. Terrain mesh: Activate 3D mesh rendering (ChunkMeshGenerator ready)
3. Lighting: Activate directional light day/night (DayNightOverlay ready)
4. Test world generates and renders in 3D

### Phase 2: Entity 3D (Days 3-4, ~8 hours)
5. Enemies: Replace sprite with colored cube (EnemyRenderer modification)
6. Player: Ensure billboard or simple shape visible
7. Resources: Render trees/ores as shapes or billboards
8. Test combat, gathering in 3D

### Phase 3: Combat Visual Effects (Days 5-6, ~8 hours)
9. Damage numbers: Wire to combat system
10. Attack lines: Wire to CombatManager
11. Particle effects: Wire to skill system
12. Status effect tints: Add to entity renderers

### Phase 4: World Interaction (Days 7-8, ~8 hours)
13. Crafting stations: Create and render
14. NPCs: Create and render
15. Interaction prompts: Show when in range
16. Loot drops: Render on enemy death

### Phase 5: UI & Polish (Days 9-10, ~10 hours)
17. Complete scene setup (all UI panels)
18. Wire input (Tab, E, C, etc.)
19. Test game flow (spawn → gather → craft → fight)
20. Polish visuals (colors, sizing, alignment)

**Estimated Total**: 44 hours to full 3D MVP

---

## 8. Verification Checklist

After implementing all systems, verify:

**Terrain**:
- [ ] Chunks render as 3D mesh (not tilemap)
- [ ] Tile heights vary (water lower, stone higher, snow highest)
- [ ] Water surface visible and semi-transparent
- [ ] Cliff edges visible where heights change
- [ ] Biome colors distinct
- [ ] No visible seams or z-fighting
- [ ] Chunks load/unload as player moves
- [ ] 60+ FPS with 4 chunks loaded

**Entities**:
- [ ] Player visible as 3D shape or billboard
- [ ] Enemies visible as colored cubes/shapes
- [ ] Enemy health bars above each enemy
- [ ] Enemy size scales by tier
- [ ] Boss enemies visibly larger
- [ ] Resources visible (trees, ores, herbs)
- [ ] Resource health bars visible
- [ ] NPCs visible at spawn positions
- [ ] Training dummy visible and targetable
- [ ] Corpses fade on death
- [ ] Loot appears as glowing drop or chest

**Camera**:
- [ ] Camera in perspective mode (not orthographic)
- [ ] Camera angle ~45° (not top-down)
- [ ] Camera follows player smoothly
- [ ] Scroll wheel zooms in/out
- [ ] Right-click drag orbits camera
- [ ] Entities not clipped by near plane
- [ ] Framerate stable

**Lighting**:
- [ ] Directional light rotates (sun moves)
- [ ] Light color changes day/night
- [ ] Shadows visible on entities/terrain
- [ ] Ambient light color cycles (warm day, cool night)
- [ ] Night noticeably darker than day
- [ ] Crafting station point lights glow
- [ ] Dungeons dimmer than surface

**Effects**:
- [ ] Damage numbers appear on hit
- [ ] Attack lines visible between combatants
- [ ] AoE circles visible on ground
- [ ] Skill particles play (fire burst, ice, lightning, poison, etc.)
- [ ] Crafting particles play at station
- [ ] Status effect tints visible (red = burn, blue = freeze, etc.)
- [ ] Multiple effects visible simultaneously

**UI**:
- [ ] All panels visible in scene
- [ ] StatusBar shows health/mana
- [ ] Hotbar shows skills
- [ ] Tab opens inventory
- [ ] E-key opens crafting/NPC/chest UI
- [ ] Interaction prompts appear in range
- [ ] Tooltips show item details
- [ ] All panels have consistent dark background + border style

**Gameplay**:
- [ ] WASD moves player
- [ ] Can gather resources
- [ ] Can open crafting UI at station
- [ ] Can select recipe and place materials
- [ ] Minigame launches and completes
- [ ] Crafted item appears in inventory
- [ ] Can equip items
- [ ] Can attack enemies (if combat wired)
- [ ] Enemies take damage
- [ ] Enemies die and drop loot
- [ ] Can pick up loot
- [ ] Game saves and loads
- [ ] Day/night cycle progresses
- [ ] Map shows explored chunks

**Performance**:
- [ ] 60 FPS during normal play
- [ ] No hitches on chunk load/unload
- [ ] No memory leaks (watch GPU/RAM over 30 min)
- [ ] Particle effects don't cause lag
- [ ] 50+ visible entities without major FPS drop

---

## Summary

This document defines **low-fidelity 3D** for every game system:

| System | Current (2D) | Low-Fidelity 3D | Implementation Status |
|--------|---|---|---|
| **Terrain** | Flat tilemap | Height-varied mesh per chunk | Ready (ChunkMeshGenerator.cs) |
| **Water** | Colored tile | Semi-transparent surface overlay | Ready (GenerateWaterMesh) |
| **Resources** | Invisible | Colored shapes or billboards | Needs ResourceNodeRenderer |
| **Stations** | Invisible | Colored primitives + point light | Needs CraftingStationRenderer |
| **Enemies** | Sprites | Colored cubes, tier-scaled | Ready (modify EnemyRenderer) |
| **Player** | Sprite | Billboard or cylinder | Ready (PlayerRenderer) |
| **NPCs** | Invisible | Colored primitives | Needs NPCRenderer |
| **Camera** | Orthographic 90° | Perspective 45° | Ready (CameraController) |
| **Lighting** | Screen overlay | Directional light + ambient | Ready (DayNightOverlay) |
| **Point Lights** | None | Station glows | Needs Light components |
| **Fog** | None | Optional dungeon fog | Needs FogController |
| **Damage Numbers** | World-space text | Same, in 3D world | Ready (wire to combat) |
| **Attack Effects** | Lines | Same, in 3D world | Ready (wire to combat) |
| **Particles** | Per crafting | Per skill + status | Ready (wire to systems) |
| **Status Tints** | None | Body color by effect | Needs renderer modifications |
| **Health Bars** | World Canvas | Same, camera-facing | Ready (already implemented) |
| **Prompts** | None | Text "Press E" in range | Needs InteractionPromptRenderer |
| **UI Panels** | Partial (2D) | All panels, dark style | Mostly ready, needs wiring |

**Most code already exists**. The implementation is 80% plumbing (wiring systems together) and 20% new UI/renderer components.

**Estimated effort to playable 3D MVP: 40-50 hours** of focused development.