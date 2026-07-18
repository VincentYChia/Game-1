# 08 — Presentation Layer: `rendering/` + `animation/` (Parity Checklist & Porting Contract)

**Subsystem**: `Game-1-modular/rendering/` (8 files, 9,790 LOC) + `Game-1-modular/animation/` (7 files, 1,020 LOC) = **10,810 LOC**, plus ~3,900 LOC of adjacent presentation code that lives outside these directories but belongs to this contract (see §1b).

**Disposition**: This subsystem is **REPLACED by Godot**, not ported line-by-line. The deliverable of this document is the exhaustive feature-parity checklist (§0) — every player-visible behavior with its data source and Godot-native replacement — plus the coupling/contract analysis a C# porter needs. Nothing player-visible may be silently lost.

**Verified against code on 2026-07-17. Every load-bearing claim cites file:line.**

---

## 0. FEATURE-PARITY CHECKLIST (the contract)

Legend per item: **Shows** (what the player sees) / **Data** (what drives it) / **Godot** (replacement node/technique).

### 0.A World rendering — overworld (`renderer.render_world`, renderer.py:1004-1723)

| # | Feature | Shows | Data | Godot replacement |
|---|---------|-------|------|-------------------|
| A1 | Background fill | Solid dark backdrop under tiles | `Config.COLOR_BACKGROUND` (20,20,30) — config.py:196 | WorldEnvironment clear color / ground plane material |
| A2 | Procedural terrain tiles | Noise-varied GRASS/STONE/WATER/DIRT tile textures; warm/cool/accent/dark blends; per-pixel detail (grass blades, cracks, wave highlights, pebbles); chunk boundaries invisible because noise is world-space | `terrain_renderer.py` — palettes 71-104, fbm/hash noise 28-62, detail 220-279, edge dithering 282-336; tile type from `world.get_visible_tiles` (renderer.py:1014) | 3D: tile-index → texture atlas on a GridMap/MeshLibrary, or a ground shader that reproduces the same hash-noise palette blending in GLSL (deterministic from world XZ). Edge dithering → texture blending/splat map in shader |
| A3 | Crafting stations | Station icon `stations/{name}_t{tier}.png` (map smithing→forge, alchemy→alchemy_table, refining→refinery, engineering→engineering_bench, adornments→enchanting_table, renderer.py:1039-1047); green border when in interaction range, grey otherwise (1057); fallback colored diamond (1060-1064); "T{n}" label with black outline when in range (1066-1074) | `world.get_visible_stations`, `character.is_in_range` | Sprite3D/quad-billboard or 3D station meshes; range highlight via shader outline or ring decal; tier via Label3D |
| A4 | Placed entities (turrets/traps/bombs/dropped items) | Icon `devices/{item_id}.png` or item icon for dropped items (1089-1106); tier badge "T{n}" (1124-1131); quantity badge for stacked drops (1132-1144); lifetime bar green→yellow→red at >50%/>25% thresholds (1146-1161); turret range circle (1163-1167); red target line to current turret target (1169-1172) | `world.get_visible_placed_entities`, `PlacedEntityType`, `entity.lifetime/time_remaining/range/target_enemy` | Node3D per placed entity; ProgressBar in SubViewport or shader bar; range = translucent cylinder/decal; target line = ImmediateMesh/Line3D |
| A5 | Spawn storage chest | Icon `devices/storage_chest.png` or drawn chest w/ lid+keyhole (1174-1199); "Click to open" hint in range (1201-1205) | `world.spawn_storage_chest`, `character.is_in_range` | Chest mesh + Label3D interaction prompt |
| A6 | Death chests | Red/crimson chest, brighter when in range (1207-1234); white skull icon w/ eye dots (1236-1241); "💀 Your items" hint (1243-1247); "{n} items" count above (1249-1259) | `world.death_chests`, `death_chest.rich_contents/contents` | Same as A5 with red material; NOTE: emoji "💀" will not survive — replace with icon texture |
| A7 | Dungeon entrances | Portal: rarity-colored outer ring, dark inner circle, brightened glow ring (1270-1277); white highlight ring in range (1279-1281); rarity letter C/U/R/E/L/! with outline (1283-1294); "{Rarity} Dungeon" label in range (1296-1303) | `world.get_visible_dungeon_entrances`, `entrance.get_rarity_color()`, `entrance.rarity` | Portal mesh + GPUParticles3D swirl + Label3D |
| A8 | Resource nodes | Icon via `ResourceNodeDatabase.get_icon_path` (1316-1328; maps `copper_vein`→`copper_ore_node.png`); border: green `COLOR_CAN_HARVEST`/red `COLOR_CANNOT_HARVEST` if in range else black (1343-1349); "T{n}" badge (1351-1357); HP bar when damaged (1370-1375); respawn progress bar + "{n}s" countdown when depleted (1359-1368); depleted non-respawning nodes hidden (1306) | `world.get_visible_resources`, `character.can_harvest_resource`, `resource.current_hp/max_hp/respawn_timer/get_respawn_progress()` | Mesh per node type; harvestability via outline shader color; bars via billboard quads |
| A9 | Enemies — body | Sprite `enemy.definition.icon_path` scaled ×2 of logical size (1548-1561), else tier-colored circle (visual-config tierColors via `visual_colors.tier_color`, renderer.py:1413-1414); boss = gold glow color (1415-1416); size = `TILE_SIZE × ENTITY_VISUAL_SCALE × 0.5 × visual_size` (1408-1410) | `combat_manager.get_all_active_enemies()`, `enemy.definition.{tier,visual_size,icon_path,category}`, `visual-config.JSON > enemyVisuals` | AnimatedSprite3D/mesh; tier tint via material |
| A10 | Enemies — category accents (fallback shapes only) | ooze: lighter inner blob; construct: black square outline; insect: leg lines; beast: ear nubs; undead: hollow eyes; elemental: 3 orbiting dots at 120° rotating with wall-time (1582-1616) | `enemy.definition.category` | Only needed if icon missing — replicate as per-category mesh variants or drop once real 3D models exist (record decision) |
| A11 | Enemies — windup telegraph on body | Sprite scales 1.0→1.12 during windup (1551-1559); additive tint pulse in attack-element color (1562-1580) | `enemy.attack_phase == 'windup'`, `attack_phase_timer`, `_attack_windup_ms`, `attack_anim_tags` | AnimationPlayer scale track + emission energy on material |
| A12 | Enemies — attack swing animation | Shape-aware: circle = expanding ring + inner pulse; line = extending beam w/ glow + tip spark; arc = 3-layer motion-blur ribbons + bright leading blade edge + tip spark + swept-edge outline (renderer.py:1421-1536) | `enemy.attack_anim_timer/attack_anim_tags/attack_anim_angle/attack_anim_duration`, `_attack_arc_degrees/_attack_shape/_attack_radius`; colors from element tags | Custom arc mesh generated per-frame (ImmediateMesh) or a radial-sweep shader on a quad; colors from same tag→color table |
| A13 | Enemies — facing indicator | Small triangle at `facing_angle` outside body (1618-1633) | `enemy.facing_angle` | In 3D, replaced by actual model rotation (see §9); keep optional debug arrow |
| A14 | Enemies — AI state dot | 3px dot top-right of body, colored per state (idle/wander/patrol/guard=green, chase=yellow, attack=red, flee=blue, dead=grey) (1635-1639; palette visual_colors.py:54-63 / visual-config) | `enemy.ai_state.value`, `visual-config.JSON > enemyVisuals.stateIndicatorColors` | Small billboard icon; consider debug-only |
| A15 | Enemies — health bar | 4px bar above head; green >50%, yellow >25%, red below (1641-1649) | `enemy.current_health/max_health` | Billboard ProgressBar (SubViewport) or shader quad — standard 3D nameplate |
| A16 | Enemies — name label | "T{tier} {name}" or "BOSS {name}" on translucent black plate (1651-1659) | `enemy.definition.name/tier`, `enemy.is_boss` | Label3D nameplate |
| A17 | Enemy corpse | Grey circle + yellow "LOOT" text (1661-1667) | `enemy.is_alive == False` | Corpse mesh/ragdoll + loot sparkle + Label3D |
| A18 | NPCs | Square sprite `npcs/{npc_id}.png` else `sprite_color` fill (962-976); yellow 3px border in interaction range else black 2px (978-986); name plate above (988-993); "[F] Talk" prompt below when near (995-1002); chunk-bucket spatial culling for 12k+ NPCs (907-949) | `self._temp_npcs` (injected by engine, game_engine.py:8627), `npc.npc_def.{npc_id,name,sprite_color}`, `npc.is_near` | CharacterBody3D/Sprite3D per NPC; Label3D name; interaction prompt via Area3D; culling via Godot's native frustum culling + VisibleOnScreenNotifier3D |
| A19 | Player | Circle body + outline; color/radius from visual-config (visual_effects.py:201-260); elliptical shadow (222-228); idle bob sine (215-219, suppressed while attack-facing locked); facing triangle (236-250); pulsing blue blocking ring when `is_blocking` (253-260); fallback plain circle (renderer.py:1679-1681) | `character.position/facing_angle/is_blocking/_attack_facing_locked`; `visual-config.JSON > entityVisuals` (playerRadius 0.33, playerColor, shadowAlpha 40, idleBobAmplitude 1.5, idleBobPeriodMs 2000 — visual_config_db.py:113-153) | Player scene: mesh + AnimationPlayer idle; blob shadow via Decal or engine shadows; blocking = shield VFX; facing = model rotation |
| A20 | Placement preview | Green translucent tile + green border at target tile in placement mode (renderer.py:2939-2952) | `preview_pos` from engine | Ghost mesh with green transparent material, red when invalid |

### 0.B Action-combat overlays (`_render_action_combat` renderer.py:1830-2290, `_draw_telegraph_arc` 1725-1828, `_render_attack_effects` 7753-7955)

| # | Feature | Shows | Data | Godot replacement |
|---|---------|-------|------|-------------------|
| B1 | Dodge afterimages | Ghost circles trailing the dodge path, fading alpha, outer glow (1869-1887); spawned every ~40ms of dodge progress (game_engine.py:3564-3571) | `ScreenEffects.afterimages` (Combat/screen_effects.py:26,49) | Ghost mesh instances w/ fading transparency, or trail shader |
| B2 | Entity hit-flash | Colored glow circle over player/enemy for 100ms after being hit; color = damage element (1889-1919; set at game_engine.py:3765-3766) | `ScreenEffects.flash_entities` | Material flash: white/element emission spike via AnimationPlayer or shader param tween |
| B3 | Enemy windup ground telegraph | Shared telegraph drawing (1725-1828): circle AoE = glow ring + fill + edge ring + pulsing inner ring; arc = bright edge polyline + 70%-radius ribbon fill + sweeping timing line + faint side boundaries + pulsing origin dot; grows with windup progress `0.3+0.7×progress` (1961); origin offset forward by `visual_size×0.6` tiles to match hitbox (1954-1958) | `enemy.attack_phase/attack_phase_timer/_attack_windup_ms/_attack_arc_degrees/_attack_radius/facing_angle`, element color from `attack_anim_tags` | **Critical gameplay readability feature.** Ground decal/Decal node or projected shader on floor plane; same fill-with-progress animation. Must land exactly where hitbox lands |
| B4 | Player windup telegraph | Same shared arc telegraph in player color for melee (2025-2043); for projectile attacks: aiming line w/ glow + pulsing crosshair + inner dot, length grows with progress (1997-2023); origin offset by `attack_def.hitbox_offset_forward` (1990-1995) | `player_sm.is_in_windup/current_attack/windup_progress/damage_context`; `attack_def.{hitbox_arc_degrees,hitbox_radius,hitbox_offset_forward,projectile_id}` | Same decal system as B3; aim line = Line3D/laser mesh |
| B5 | Dodge i-frame tint | Pulsing translucent blue circle over player while invulnerable (2045-2057) | `player_actions.is_dodging/is_invulnerable` | Shader rim glow / transparency pulse on player material |
| B6 | Active hitbox flashes | Per shape: circle = glow+fill+bright ring (2113-2131); arc = filled wedge + bright edge (2133-2162); line = triple-width beam + tip glow (2164-2190); rect = filled rotated rect (2192-2202); alpha decays with `remaining_ms` (2083); player hitboxes styled by `resolve_weapon_visual` (thickness/glow/color/impact, 2091-2109); heavy-weapon impact flash when hitbox expiring: white-hot center + colored rings (2204-2216) | `hitbox_sys.active_hitboxes`, `hitbox.definition.{shape,radius,arc_degrees,length,width,height}`, `hitbox.facing_angle/damage_context`, `animation/weapon_visuals.py` style | Slash VFX: arc mesh sweep or GPUParticles3D + shader; parameters still driven by weapon type/tags/tier table (§0.G1, port that table to C#) |
| B7 | Projectiles | Visual-driven: 'orb' (radius, optional pulse, optional glow halo + white core), 'elongated' (ellipse arrow/shard), 'beam' (wide glowing line w/ 28px trail + bright tip) (2218-2279); fallback tag-colored circle (2280-2286) | `projectile_sys.projectiles`, `proj.definition.visual{shape,color,glow,glow_color,radius_px,length_px,width_px,pulse}`, `proj.definition.tags` | Projectile scenes: mesh + GPUParticles3D trail + omni light for glow; visual dict fields map 1:1 to scene params |
| B8 | Combat particles | World-space particles: hit sparks (elemental palette, 5-8+intensity count, gravity+drag, upward bias — combat_particles.py:85-106); slash trail along arc (108-128); dodge dust (130-145); size shrinks with life, alpha fades (57-71, 196-204) | `CombatParticleSystem` (max 400, combat_particles.py:77); emitted from game_engine.py:3575, 3662, 3767 and bridge | GPUParticles3D with per-element process materials; color palettes from `DAMAGE_SPARK_COLORS` (combat_particles.py:22-31) — keep the palette table in C# |
| B9 | Attack effects layer | SLASH_ARC: 3-phase (charge glow 0-25% → sweep w/ wake polygon + bright leading edge 25-70% → fade) (7780-7852); THRUST: charge point → extending beam + tip (7854-7901); IMPACT_BURST: expanding ring + 4 cross-hair lines (7903-7925); BLOCKED: X mark + "BLOCKED" text (7927-7940); AREA: filled circle + ring (7942-7952) | `systems/attack_effects.get_attack_effects_manager()` — effect list w/ `{effect_type,start_pos,end_pos,facing_angle,arc_degrees,radius,age,duration,get_color()}` | Same VFX pool as B6; BLOCKED text → Label3D popup |
| B10 | Damage numbers (enhanced) | Physics-arc floating numbers: initial up-velocity + gravity + horizontal spread; type-colored per element; crit = bigger font, ×1.8 scale, "{n}!" text, gold, higher pop; special MISS/DODGE/BLOCK text; fade in last 30% of 1200ms life; slow shrink; anti-stack Y offset within 300ms at same position; 4-direction black outline (visual_effects.py:29-194) | `DamageNumberManager` fed by DAMAGE_DEALT events (bridge) AND direct spawns (game_engine.py:3760-3763); all constants from `visual-config.JSON > damageNumbers` (visual_config_db.py:66-108) | Label3D w/ billboard + Tween arc, or 2D labels via `Camera3D.unproject_position` on a CanvasLayer (keeps crisp text). Config values from same JSON |
| B11 | Damage numbers (legacy fallback) | Simple rising number, white or gold+"!" for crit, 1s fade (renderer.py:1697-1704; entity dataclass entities/damage_number.py:9-19) | `game_engine.damage_numbers` list | Fold into B10 — port ONLY the enhanced path; legacy list is redundant (see §11 risks) |
| B12 | Enemy death effect | Grey-tinted shrinking circle: dying phase (fade 600ms + up-to-15° rotation) → corpse phase (alpha 180, lingers 5000ms, final fade 1000ms) (visual_effects.py:267-377) | `EnemyDeathManager` fed by ENEMY_KILLED event (bridge 121-143); `visual-config.JSON > enemyVisuals.{deathFadeDurationMs,deathShrinkFactor,corpseLingerMs,corpseFadeMs,deathRotationDegrees}` | AnimationPlayer death anim on enemy scene + queue_free timer; params from same JSON |
| B13 | Screen shake | Camera pixel offset each frame; intensity by event (kill shake tier→{1:2,2:3,3:5,4:8} — visual_effect_bridge.py:29, duplicated game_engine.py:3787); player-hit shake `min(amount/10+1, 8)` (bridge 160-162); decay in ScreenEffects (Combat/screen_effects.py:28-75); applied via `camera.shake_offset` inside `world_to_screen` (core/camera.py:22-26, set at game_engine.py:8597-8601, reset 8638 so UI is unaffected) | SCREEN_SHAKE events + direct calls | Camera3D shake (noise-based offset on a shaker node); UI on CanvasLayer naturally unaffected |
| B14 | Debug hitbox/hurtbox wireframes (F1) | Green hurtbox circles, blue i-frame hurtboxes, red hitboxes shape-accurate (circle/arc/rect/line), optional entity-ID labels + owner/remaining-ms labels (visual_effects.py:384-492); projectile debug: hitbox circle + velocity vector + range remaining (495-524); gated by `renderer._debug_hitboxes` = F1 (renderer.py:1706-1718, game_engine.py:8606) | `hitbox_system.hurtboxes/active_hitboxes`, `projectile_system.projectiles`; `visual-config.JSON > debug` colors | Godot debug draw (ImmediateMesh) toggled by same debug flag |

### 0.C Ambience

| # | Feature | Shows | Data | Godot replacement |
|---|---------|-------|------|-------------------|
| C1 | Day/night overlay | Full-viewport tint: night (20,30,60)@α80; dawn interpolates night→(80,50,30), α 80→20; day (255,250,220)@α10; dusk interpolates (80,40,20)→night, α 20→80 (renderer.py:2954-2996) | `get_time_of_day()` → (phase, progress) from engine | DirectionalLight3D color/energy + WorldEnvironment ambient curve over the same 4 phases — this is the one place 3D lighting genuinely replaces a tint quad |
| C2 | Time-of-day label | "Night/Dawn/Day/Dusk" text top-left w/ adaptive contrast plate (2998-3012) | same | HUD Label on CanvasLayer |
| C3 | Loading screen (world gen) | Fullscreen dark card: "LOADING WORLD", stage name, progress bar, %, flavor line; calls `pygame.display.flip()` itself mid-boot (7437-7508; invoked via progress callback game_engine.py:1980) | `WorldSystem.initialize_world(progress_callback=...)` | Dedicated loading scene; progress via signal from async world-gen task |

### 0.D HUD (always-on, drawn over viewport)

| # | Feature | Shows | Data | Godot replacement |
|---|---------|-------|------|-------------------|
| D1 | Character info panel (right, 400px) | "DEBUG MODE" red flag when F1; class icon `classes/{id}.png` + name; position (x.x, y.y); chunk name colored by danger (peaceful=green, dangerous=orange, rare=purple, water=blue — renderer.py:3059-3075); level + "(n pts!)" unallocated; XP cur/next or "MAX LEVEL"; HP bar w/ text + "🛡️ BLOCKING" indicator (3173-3185); MP bar (3187-3194); active buffs (D2); selected tool icon + name + tier + durability (∞ marker w/ F7) + effectiveness %; last-3 titles w/ icons; static controls list (3154-3171) | `character.{class_system,position,leveling,health,mana,selected_tool,titles}`, `chunk_info` dict from engine | Right-side PanelContainer on CanvasLayer; each block a scene; controls list → input-map-driven help |
| D2 | Active buffs | Per-buff bar: name + m:ss timer, fill = remaining fraction, green for combat / blue otherwise, outlined text (3196-3238) | `character.buffs.active_buffs` (`duration_remaining`, `get_progress_percent()`, `category`) | VBox of TextureProgressBar rows |
| D3 | Skill hotbar | 5 slots bottom-center, 60px; key number 1-5; skill icon or initials fallback; cooldown dark overlay + "{s.s}s"; mana cost "{n}MP" blue/red by affordability; "Empty" label; hover tooltip w/ name, tier+rarity color, cost/cooldown, effect line, word-wrapped description (3240-3390) | `character.skills.equipped_skills/known_skills`, `SkillDatabase.get_mana_cost/get_cooldown_seconds`, `pygame.mouse.get_pos()` (3276!) | HBox of slot buttons; cooldown via TextureProgressBar radial; tooltip via Control tooltip or custom panel |
| D4 | Inventory panel | Bottom 300px strip: 30 slots grid, item icons w/ qty, equipped gold border, drag-drop, hover tooltip (renderer.py:4965-5228; slot render 5148-5227) | `character.inventory`, `ItemStack`, Config.INVENTORY_* (config.py:60-63,140) | GridContainer of slot Controls with native drag-and-drop |
| D5 | Notifications | Center-top stacked fading messages with black plate; α from `lifetime/3.0` (4921-4934) | `game_engine.notifications` (`Notification{message,color,lifetime}`) | Toast queue on CanvasLayer w/ Tween fade |
| D6 | Debug messages | Bottom-left, max 5 lines, translucent plates (4936-4963) | `core.debug_display.get_debug_manager()` | Debug CanvasLayer, hidden in release |
| D7 | Quest log overlay (J) | Window w/ active quests + per-quest Abandon buttons; returns clickable rects (game_engine.py:8667-8688; `systems/quest_log_overlay.py`) | `character` quest state | Quest log Window/PanelContainer; buttons are real Buttons (no rect-return protocol) |
| D8 | WES observability overlay (F12) | Bottom-panel: "WES OBSERVABILITY" header (+`[WES_VERBOSE=on]`), counters summary, last 15 pipeline events color-coded (cascade=green, WNS/WES=cyan, registry/db=orange, fail=red, degrade=yellow) (world_system/wes/observability_overlay.py:42-141; toggled game_engine.py:1303-1312, drawn 8655-8665) | `obs_recent()/obs_stats()` ring buffer in world_system | **Must be rebuilt in Godot** reading the ring buffer **over the sidecar IPC** — the current implementation draws with pygame inside world_system, which stays Python (see §11 risks) |
| D9 | LLM loading overlay | Fullscreen dim + center panel: 8 orbiting fading orbs OR animated pop-in checkmark on completion; message + subtitle + animated dots; progress bar w/ shimmer, indeterminate slide when 0%; green/blue theming (renderer.py:7957-8162) | `systems.llm_item_generator.get_loading_state()` (`is_loading/overlay_mode/is_complete/message/subtitle/progress/get_animated_progress`) | Modal Control w/ AnimationPlayer; state polled from sidecar IPC client |
| D10 | Classifier corner indicator | Bottom-right 280px card: truncated message, optional subtitle, progress bar w/ gradient or scrolling stripes (8164-8236) | same loading state, `overlay_mode=False` | Small toast panel |

### 0.E Menus / screens (modal, return click-rect lists to engine)

| # | Feature | Key contents | Code | Godot replacement |
|---|---------|-------------|------|-------------------|
| E1 | Start menu | 4 options (New World / Load World / Load Default Save / Temporary World) w/ hover+keyboard selection, descriptions, "Found n save file(s)" (does `os.listdir("saves")` in the render path! 7325-7330) | renderer.py:7248-7333 | Main-menu scene; save count computed once, not per frame |
| E2 | Pause menu (ESC) | Dim backdrop; Return / Save & Exit (disabled in temp world) / Exit without saving (7335-7435) | renderer.py:7335 | Pause scene w/ `get_tree().paused` |
| E3 | Class selection | Class cards w/ icons + tooltips (7510-7591; class tooltip 7085-7168) | `ClassDatabase` | Selection screen scene |
| E4 | Stats menu (C) | 6 stats + allocation buttons when points available (7592-7703) | `character.stats/leveling` | Stats panel scene |
| E5 | Skills menu (K) | Hotbar assignment (5 slots), known list, available list; returns 4 rect groups (3392-3606; contract game_engine.py:8763-8771) | `SkillDatabase`, `character.skills` | Drag-drop skill assignment UI |
| E6 | Equipment menu (E) | 8 slots w/ icons, durability, equip/unequip; equipment tooltip w/ stat compare (6711-7053) | `character.equipment`, `EquipmentDatabase` | Equipment panel scene |
| E7 | Encyclopedia (L) | Tabs: Guide / Quests / Skills / Titles / Stats / Recipes, each a scrollable content page (3607-3694 + tab renderers 4278-4920) | `character.encyclopedia`, all content DBs | TabContainer scene |
| E8 | World map (M) | Pre-rendered geographic map image (blurred biome colors, 25% nation tint, nation borders 2px gold, region borders 1px — map_cache.py:38-115), zoom/pan w/ pre-scaled cache (renderer.py:3801+), player marker, waypoints panel w/ rename input + delete confirm, explored-chunk count, cooldown display (3695-4160; UI layout from `MapWaypointConfig` 3718) | `world_system.geographic_map`, `world_system.map_images` (generated at world init — systems/world_system.py:367-387), `map_system` state | Map scene: generate map texture from chunk data in C# (ImageTexture), pan/zoom in a SubViewport; waypoint UI native Controls. **Map-image generation must move out of world-gen into presentation** (see §3/§11) |
| E9 | NPC dialogue | Name header, dialogue lines, green "Turn In Quest" button when applicable, up to 3 quest-offer buttons w/ icon `quests/{id}.png` + truncated description, "[F or ESC] Close" (4161-4276) | `npc.npc_def`, `NPCDatabase.quests`, engine-passed dialogue lines/quests | Dialogue panel scene; note emoji "✅"/"📜" replaced by icons |
| E10 | Chest UIs (dungeon/spawn/death) | Grid of contents w/ icons + qty, take/take-all interactions via returned rects (2554-2938) | chest contents | Shared chest-panel scene, 3 skins |
| E11 | Crafting UI (station) | Recipe sidebar grouped by type w/ scroll (5461-5803, grouping logic `_group_recipes_by_type` 5293-5419 — **also called by engine for click handling**, game_engine.py:1410, 6507); discipline placement panel: smithing/adornment grids (tier→3×3/5×5/7×7/9×9, renderer.py:64-75), refining hub, alchemy sequence, engineering slots (109-906, dispatched 5727-5739); recipe-hint dimmed icons; minigame button | `RecipeDatabase`, `PlacementDatabase`, `MaterialDatabase`, `_temp_user_placement/_temp_scroll_offset` injected | **Stays 2D** per architecture decision: Control-node overlay panel. `_group_recipes_by_type` must move to pure-logic C# (it is game logic living in the renderer) |
| E12 | Interactive crafting UI | Full-window discipline UI w/ material list, placement area, buttons (5804-6710; contract returns 4 rect groups, game_engine.py:8723-8736) | `interactive_ui` state | Control overlay (2D), same as E11 |
| E13 | Enchantment selection | Modal list of compatible items w/ scroll (7170-7247) | `enchantment_recipe/compatible_items` | ItemList dialog |
| E14 | Tooltips (deferred) | Item/equipment/tool/class tooltips render LAST via `pending_tooltip`/`render_pending_tooltip` so they sit above all UI (init 56-59, render 7054-7083, called game_engine.py:8836); generic text tooltip 7704-7743 | pending tuples set during panel rendering | Godot handles z-order natively via CanvasLayer/`top_level`; the deferred-tooltip protocol disappears |
| E15 | Dungeon rendering | Dark stone tile floor/walls (flat colors, 2314-2332); chest states (locked 🔒 / LOOT glow / EMPTY, 2334-2368); pulsing exit portal + "EXIT" (2370-2397); enemies w/ **local** tier colors {1:green,2:blue,3:purple,4:red} (2401-2447 — inconsistent w/ overworld palette, see §11); grey corpse dots; legacy damage numbers only (2477-2484); dungeon UI overlay: wave indicator/progress (2489-2553) | `dungeon_manager`, `combat_manager.dungeon_enemies` | Dungeon scene w/ same GridMap approach; unify tier colors with visual-config |

### 0.F Minigame presentation (stays 2D — Control overlays; code lives OUTSIDE rendering/)

`core/minigame_effects.py` (1,522 LOC) + minigame-drawing methods inside `core/game_engine.py` (lines ~9228-10800: `_render_smithing_minigame` "FORGE", alchemy "ALCHEMIST'S WORKSHOP", refining "MATERIAL REFINERY", engineering "ENGINEER'S WORKBENCH", enchanting, fishing) + `Crafting-subdisciplines/*.py` internal draw code.

| # | Feature | Code | Godot |
|---|---------|------|-------|
| F1 | Particle types: Spark, Ember, Bubble, Steam, Spirit (wandering enchant motes), GearTooth | minigame_effects.py:281-554 | GPUParticles2D presets per discipline |
| F2 | ScreenShake (minigame-local), GlowEffect, FlameEffect, RotatingGear | 556-749 | Control-space shake + AnimatedTexture/shaders |
| F3 | AnimatedProgressBar, AnimatedButton (hover/press states) | 750-884 | Native ProgressBar/Button w/ themes |
| F4 | MinigameMetadataOverlay — 8s result card (item name/quality/stats) blocking input | 885-1026 | Result popup scene |
| F5 | Discipline backgrounds: image `find_background_image` or generated (forge glow, tumbler brass, cauldron w/ liquid color, workbench tools, enchant runes) | 1027-1397 | TextureRect background or drawn via `_draw` |
| F6 | Per-discipline HUD text (temperature °C, strike quality, chain/stabilize buttons, tumbler status, puzzle count, timers) | game_engine.py:9228-10800 | Labels/Buttons inside each minigame Control scene |

### 0.G `animation/` behaviors

| # | Feature | Code | Status | Godot |
|---|---------|------|--------|-------|
| G1 | **Weapon visual style resolution** — weapon_type → {arc°, trail frames, thickness, motion swing/thrust/spin/none} (10 profiles, weapon_visuals.py:48-59); tier→intensity {1:0.7, 2:1.0, 3:1.3, 4:1.6} (62); element tag → color (seeded from visual-config, 24-41); weight>3 → slower+shake+impact flash, weight<1 → faster (137-146); attack_speed modifies trail (148-154); tags critical/execute→flash+shake, lifesteal→red glow, chain→×1.5 particles (157-167); trail alpha curve (172-186); impact color (189-192) | weapon_visuals.py:93-169 | **LIVE** (renderer.py:2065, 2099) | Port table + resolver verbatim to pure-logic C# (`WeaponVisualStyle`); feeds Godot VFX parameters |
| G2 | Combat particle emitters (hit sparks/slash/dodge/projectile-trail) | combat_particles.py | LIVE except `emit_projectile_trail` (no callers — dead) | GPUParticles3D (see B8) |
| G3 | Frame-animation stack: `AnimationFrame/AnimationDefinition` (animation_data.py), `SpriteAnimation` player (sprite_animation.py), `AnimationManager` registry (animation_manager.py) | — | **DEAD IN PRACTICE**: `update_all` is called each frame (game_engine.py:3620) but nothing ever calls `.play()`/`play_definition()` — registry is always empty (verified: zero callers repo-wide) | Do NOT port — Godot AnimationPlayer/AnimatedSprite3D replaces the concept entirely |
| G4 | `ProceduralAnimations` (swing arc, telegraph pulse, hit flash, idle bob, slash trail, ground telegraph frame generators) | procedural.py:58-368 | **DEAD** — zero callers repo-wide; the live equivalents are drawn immediate-mode in renderer.py (§0.B) | Do NOT port; keep only as design reference for VFX shapes |

---

## 1. File table

### 1a. In-scope directories

| File | LOC | Responsibility | Disposition |
|------|-----|----------------|-------------|
| `rendering/__init__.py` | 5 | Exports `Renderer` | drop (engine-replaces) |
| `rendering/renderer.py` | 8,236 | God-class: world/dungeon rendering, all HUD, all menus, minigame placement grids, telegraphs, attack effects, loading overlays | **engine-replaces + decompose**: ~40 scenes/nodes in Godot; the small amount of embedded LOGIC (`_group_recipes_by_type` 5293-5419, grid-size-per-tier 64-75, station icon-name map 1039-1046, recipe-hint math) ports to pure-logic C# |
| `rendering/image_cache.py` | 110 | Singleton icon loader/scaler; path routing rules (items/ prefix vs direct for enemies/resources/skills/titles/npcs/quests/classes — 59-64) | engine-replaces (Godot ResourceLoader + `Texture2D` cache); **port the path-routing rules** to an `IconPathResolver` in C# |
| `rendering/map_cache.py` | 127 | Pre-renders geographic map: 4px/chunk image, box blur, 25% nation tint, nation/region borders | **port-to-C#** (generates an `Image`/`ImageTexture` from chunk data — pure algorithm, keep constants); `get_best_lod` (118-127) is dead code (no callers) |
| `rendering/terrain_renderer.py` | 347 | Deterministic world-space noise tile texturing (hash/fbm, 4 palettes, detail pixels, edge dithering) | **port algorithm** (to GLSL ground shader or C# texture baker); constants must survive for identical world look |
| `rendering/visual_colors.py` | 166 | Single source of truth for element/tier/state/boss-glow colors; JSON-backed w/ byte-identical fallbacks | **port-to-C#** (pure logic; loads `visual-config.JSON`) |
| `rendering/visual_effect_bridge.py` | 275 | EventBus subscriber → visual dispatch; publish helper functions used by combat | **split**: publish helpers (197-276) → pure-logic events assembly; subscriber half → Godot-side VFX coordinator node |
| `rendering/visual_effects.py` | 524 | EnhancedDamageNumber/Manager, player enhanced render, EnemyDeathEffect/Manager, debug hitbox/projectile wireframes | engine-replaces; damage-number physics/lifecycle math ports to C# helper driving Label3D/Tween |
| `animation/__init__.py` | 19 | Exports | drop |
| `animation/animation_data.py` | 41 | AnimationFrame/AnimationDefinition dataclasses (hold pygame.Surface) | **drop-dead-code** (only consumer is dead G3 stack) |
| `animation/sprite_animation.py` | 69 | Time-based frame stepper | drop-dead-code |
| `animation/animation_manager.py` | 120 | entity_id→animation registry singleton | drop-dead-code (update_all called, play never — game_engine.py:3620 vs zero play callers) |
| `animation/procedural.py` | 368 | Pre-rendered frame generators (swing/telegraph/flash/bob/trail) | drop-dead-code (zero callers) |
| `animation/combat_particles.py` | 211 | World-space combat particle system + element palettes | engine-replaces (GPUParticles3D); **port palettes + emitter parameters** |
| `animation/weapon_visuals.py` | 192 | Tag/tier/weight/speed → visual style resolver | **port-to-C#** (pure logic, feeds VFX) |

**Total in-scope: 15 files, 10,810 LOC** (wc-verified).

### 1b. Adjacent presentation code this contract also covers (lives elsewhere)

| File | LOC | Why it's in this contract |
|------|-----|---------------------------|
| `core/minigame_effects.py` | 1,522 | Minigame particles/backgrounds/widgets (§0.F) — stays 2D Control overlay |
| `core/camera.py` | ~35 | `world_to_screen`/`screen_to_world` + shake offset — replaced by Camera3D (§9) |
| `Combat/screen_effects.py` | ~122 | Shake/flash/afterimage STATE (logic, port to C#); `hit_pause` is a designed no-op (§15 trap 16 markers at visual_effect_bridge.py:118-119, game_engine.py:3771) |
| `core/game_engine.py` (render section) | ~2,300 | Frame composition `render()` 8578-8849 + minigame drawing 9228-10800 — becomes Godot scene-tree structure |
| `world_system/wes/observability_overlay.py` | 178 | F12 overlay — pygame drawing inside the sidecar-bound package; must be rebuilt Godot-side over IPC |
| `systems/quest_log_overlay.py` | ~200 | J quest log overlay panel |
| `data/databases/visual_config_db.py` | ~300 | Loader for `visual-config.JSON` — **port-to-C#** (pure) |
| `data/databases/map_waypoint_db.py` | — | Map UI layout config loader — port-to-C# |

---

## 2. Public surface (what other subsystems actually call)

| Symbol | Callers (file:line) |
|--------|---------------------|
| `Renderer` (construction) | `core/game_engine.py:60` import; engine owns one instance |
| `Renderer.render_world` | game_engine.py:8635 |
| `Renderer.render_dungeon` | game_engine.py:8618 |
| `Renderer.render_ui` / `render_inventory_panel` / `render_skill_hotbar` / `render_notifications` / `render_debug_messages` | game_engine.py:8646-8653 (+8587-8588 in start menu) |
| `Renderer.render_day_night_overlay` | game_engine.py:8642 |
| `Renderer.render_start_menu` / `render_pause_menu` / `render_loading_screen` | game_engine.py:8583, 8842, 1980 |
| `Renderer.render_{dungeon,spawn,death}_chest_ui` | game_engine.py:8695, 8700, 8708 |
| `Renderer.render_class_selection_ui` / `render_stats_ui` / `render_skills_menu_ui` / `render_equipment_ui` / `render_encyclopedia_ui` / `render_map_ui` / `render_npc_dialogue_ui` / `render_enchantment_selection_ui` | game_engine.py:8714-8826 |
| `Renderer.render_crafting_ui` / `render_interactive_crafting_ui` | game_engine.py:8742, 8723 |
| `Renderer.render_loading_indicator` / `render_pending_tooltip` | game_engine.py:8833, 8836 |
| `Renderer._group_recipes_by_type` | game_engine.py:1410, 6507 — **engine calls a private renderer method for click-hit-testing logic** (must move to shared C# logic) |
| `Renderer.font/small_font/tiny_font` | game_engine minigame drawing, ~100 uses (9228-10800) |
| `ImageCache.get_instance().get_image` | renderer.py throughout (93, 968, 1050, 1333, 1549, 3042...); tests/test_image_system.py:14 |
| `generate_map_images` | systems/world_system.py:374 (called from `_generate_map_images`, results stored `world_system.map_images` :381) |
| `visual_colors.{element_palette,tier_color,state_palette,boss_glow_color}` | renderer.py:1385-1413, 1847; visual_effect_bridge.py:39; animation/weapon_visuals.py:25 |
| `visual_effects.{DamageNumberManager,EnemyDeathManager}` | game_engine.py:378-380 (owned by engine, injected into renderer at 8604-8605) |
| `visual_effects.render_player_enhanced` | renderer.py:1674, 2454 |
| `visual_effects.render_debug_{hitboxes,projectiles}` | renderer.py:1710-1716 |
| `VisualEffectBridge` (+`.connect`) | game_engine.py:390-395; late-wired to screen_fx/particles at 3522-3524 |
| `visual_effect_bridge.publish_damage_dealt/enemy_killed/player_hit/dodge_performed/attack_started` | game_engine.py:966, 3775, 3801, 3838, 3911, 3992, 4020; **Combat/combat_manager.py:798, 843, 1740, 1800, 2142** |
| `AnimationManager.get_instance` / `update_all` | game_engine.py:3484, 3497, 3620 (registry never populated — dead) |
| `CombatParticleSystem` (`emit_hit_sparks/emit_slash_trail/emit_dodge_dust/update/render`) | game_engine.py:3485, 3496, 3575, 3662, 3767, 3622; renderer.py:2288-2290 |
| `weapon_visuals.resolve_weapon_visual` | renderer.py:2065, 2099 |
| `Renderer._get_npc_chunk_buckets` | tests/integration/test_05_ui_polish.py:112,118 |
| Attribute-injection contract (engine → renderer, no method call): `_temp_npcs` (8627), `_temp_ac_systems`/`_temp_combat_manager` (8612-8634), `_damage_number_manager`/`_death_effect_manager`/`_debug_hitboxes` (8604-8606), `_temp_scroll_offset` (8741), `_temp_user_placement` | hidden API — must become explicit constructor/params in Godot |

---

## 3. Dependency edges

**rendering/animation import FROM:**
- `core`: `Config`, `Camera`, `Notification` (renderer.py:10), `core.paths.get_resource_path` (image_cache.py:6, visual_colors.py:91), `core.config.Config` (terrain_renderer.py:21, combat_particles.py:18)
- `data.models`: `Recipe, PlacementData, EquipmentItem, NPCDefinition, Position, PlacedEntityType, TileType` (renderer.py:13-18, 1077, 2303)
- `data.databases`: Material/Placement/Equipment/Recipe/Skill/Title/Class/NPC DBs (renderer.py:21-30), `map_waypoint_db.MapWaypointConfig` (46), `resource_node_db` (1319), `visual_config_db.get_visual_config` (visual_effects.py:22)
- `entities`: `Character, Tool, DamageNumber` (renderer.py:36), `ItemStack` (37)
- `systems`: `WorldSystem, NPC` (renderer.py:40-43), `systems.attack_effects` (7761), `systems.llm_item_generator.get_loading_state` (7964)
- `events`: `event_bus.GameEvent, get_event_bus` (visual_effect_bridge.py:22)
- `animation`: `weapon_visuals` (renderer.py:2065)

**Who imports rendering/animation (reverse edges):**
- `core/game_engine.py` — Renderer, visual_effects managers, bridge, publish helpers, AnimationManager, CombatParticleSystem (see §2)
- **`Combat/combat_manager.py:798,843,1740,1800,2142` — imports `rendering.visual_effect_bridge` publish helpers.** Combat LOGIC depends on the rendering package. In the port these helpers go to the events/pure-logic assembly so `Combat.dll` never references presentation.
- **`systems/world_system.py:374` — world generation imports `rendering.map_cache` and stores pygame Surfaces in `self.map_images` (:61, :381).** Logic layer holds render artifacts; in the port the map texture is generated on the Godot side from chunk data.
- `animation/weapon_visuals.py:25` → `rendering.visual_colors` (fine — both presentation)
- Tests: `tests/test_image_system.py:14`, `tests/integration/test_05_ui_polish.py:112`; `verify_imports.py:88`

---

## 4. Engine coupling (every touchpoint class that must be redesigned)

| Touchpoint | Locations (representative) | Godot redesign |
|------------|---------------------------|----------------|
| `pygame.Surface` creation/blit (thousands) | all files | Scene tree; SubViewports for panel compositing |
| Fonts `pygame.font.Font(None, size)` | renderer.py:53-55; ad-hoc fonts in visual_effects.py:421, 489, 520; game_engine.py:8662, 8674-8675 | Theme + FontFile resources |
| `pygame.display.flip()` inside a render method | renderer.py:7508 (`render_loading_screen`) — mid-boot forced present | Loading scene; never manual present |
| `pygame.mouse.get_pos()` inside renderer | renderer.py:3276 (hotbar hover) | Control `mouse_entered`/`get_global_mouse_position` |
| `pygame.transform.smoothscale/rotate` | image_cache.py:83; renderer.py:1557, 2201, 2474(bridge of debug), map_cache.py:34-35; visual_effects.py:133, 142, 355 | Texture filtering / Node2D-3D scale+rotation |
| Per-pixel `Surface.set_at` | terrain_renderer.py:233-336; combat_particles.py:199 | Shader / GPUParticles |
| Alpha compositing SRCALPHA + `BLEND_RGBA_ADD/MULT` | renderer.py:1569; procedural.py:40-54; everywhere | Material blend modes / CanvasItem modulate |
| Clip rects | renderer.py:3799 (`surf.set_clip`) | Control clip_contents |
| Wall-clock animation `time.time()` | visual_effects.py:169, 218, 252; renderer.py:1577, 1611, 2015, 2052, 2265, 2377; loading overlays 8014+ | `_process(delta)` accumulation or Time.get_ticks_msec; keep phase formulas |
| dt normalization to 60fps `dt_ms/16.67` | visual_effects.py:97 | delta-based physics in C# |
| Filesystem I/O in render path | image_cache.py:68 (`os.path.exists` per new icon), renderer.py:7325 (`os.listdir("saves")` every start-menu frame) | Preload/async load; compute save list on menu open |
| Camera math (2D) | core/camera.py:22-32; shake injection game_engine.py:8597-8601 | Camera3D + shaker; `unproject_position` for world→screen labels |
| Surface caches | terrain_renderer.py:170-199 (4096-entry LRU-ish), image_cache cache dict, renderer `_map_prescaled` 3802, `world_system.map_images` | Godot resource cache; explicit texture cache only for generated map |
| Click-rect return protocol | every menu returns `pygame.Rect` lists consumed by engine mouse handler (game_engine.py:8583-8826) | Native Button signals — the entire rect-protocol disappears |
| Emoji in font rendering | renderer.py:1245 ("💀"), 2364 ("🔒"), 3184 ("🛡️"), 4206 ("✅"), 4227 ("📜") | Replace with icon textures (default pygame font already renders these as boxes on some systems) |

---

## 5. Constants & formulas (exact values from code; visual-layer)

None of these are game-balance constants (sacred constants live in Combat/entities — see inventory docs 02/03); these are the **look-and-feel contract**:

- **Screen layout**: SCREEN 1600×900 base, VIEWPORT 1200×900 (75% width), UI panel 400, inventory panel y=600 h=300 (config.py:14-63); dynamic rescale keeps viewport = 75% width (115-128); UI scale helper `Config.scale` (172-180); menu sizes S/M/L/XL 600×500 → 1200×750 (143-150)
- **Colors (Config)**: background (20,20,30); player (255,215,0); HP bar (0,255,0)/bg (100,100,100); damage normal white / crit gold; can/cannot harvest (100,255,100)/(255,100,100); rarity colors common..artifact (config.py:196-232)
- **Element palette** (fallback, canonical in visual-config.JSON): physical (255,255,255), fire (255,140,40), ice (100,200,255), lightning (255,255,80), poison (100,255,80), arcane (200,100,255), shadow (160,100,200), holy (255,255,180), heal (80,255,80), shield (100,180,255) (visual_colors.py:34-45); render-only aliases frost→ice, chaos (renderer.py:1391-1392, weapon_visuals.py:27-28)
- **Tier colors**: 1 (200,100,100), 2 (255,150,0), 3 (200,100,255), 4 (255,50,50); boss glow (255,215,0) (visual_colors.py:47-65). **Dungeon uses a divergent local table** {1:(100,200,100), 2:(100,150,255), 3:(200,100,200), 4:(255,100,100)} (renderer.py:2401-2406) — reconcile in port
- **Enemy AI-state colors**: idle/wander/patrol green (100,200,100), guard (180,180,100), chase (255,200,50), attack (255,80,60), flee (100,150,255), dead (100,100,100) (visual_colors.py:54-63)
- **Damage numbers** (visual-config defaults): lifetime 1200ms, velY -2.5, spread ±0.6, gravity 0.08, shrink 0.997/frame, crit scale 1.8, crit color (255,220,50), stack offset 18px, fade in last 30%, crit velY ×1.4 & spread ×0.5 (visual_config_db.py:72-102; visual_effects.py:83-113)
- **Death effect**: fade 600ms, shrink to 0.3, corpse linger 5000ms, corpse fade 1000ms, rotation ≤15°, corpse alpha 180 (visual_config_db.py:172-181; visual_effects.py:279-331)
- **Kill screen-shake by tier**: {1:2, 2:3, 3:5, 4:8}, 150ms (visual_effect_bridge.py:29 AND duplicated game_engine.py:3787); player-hit shake `min(amount/10+1, 8)`, 100ms (bridge 160-162); flash 100ms α 220→0 (renderer.py:1892)
- **Telegraphs**: radius grows `0.3 + 0.7×progress`; base alpha `30 + progress×180`; pulse `sin(t×10)`; arc ribbon inner radius 0.7×R; enemy origin offset `visual_size×0.6` tiles; player offset = `hitbox_offset_forward` (renderer.py:1746-1828, 1954-1961, 1992)
- **Attack effect phases**: slash charge 0-25% → sweep 25-70% → fade; thrust charge 0-25% → extend 25-60% → hold (renderer.py:7796-7882)
- **Day/night**: night (20,30,60)@80; dawn→(80,50,30) α80→20; day (255,250,220)@10; dusk (80,40,20)→night α20→80 (renderer.py:2966-2992)
- **Terrain**: 4 palettes w/ warm/cool/accent/dark + variance 5-8 (terrain_renderer.py:71-104); noise scales 0.12 (≈8 tiles) & 0.33 (≈3 tiles) + per-tile hash jitter; blend thresholds ±0.15, accent ±0.4 (107-162); hash constants 374761393/668265263/1274126177 (28-34); cache cap 4096 (171)
- **Map image**: 4 px/chunk, nation tint 25%, blur radius 3, nation border (200,185,140) 2px, region border (120,120,135) 1px, background (20,22,30) (map_cache.py:52-106)
- **Weapon visual profiles**: sword_1h 65°/3/1.0/swing; sword_2h 100°/4/1.4; dagger 30°/2/0.6; axe 80°/4/1.3; mace 55°/3/1.2; hammer_2h 90°/5/1.6; spear 12°/2/0.8/thrust; staff 35°/3/0.7; bow 0/0/0.5/none; unarmed 55°/2/0.8 (weapon_visuals.py:48-59); tier intensity {0.7, 1.0, 1.3, 1.6} (62); weight/speed modifiers (137-154)
- **Particles**: combat max 400 (combat_particles.py:77); hit sparks `5 + 3×intensity`, speed 1.5-4.0 t/s, gravity 5, drag 3, life 0.2-0.5s (91-106); dodge dust 6 @ negative gravity −0.5 (132-145); minigame particle cap 200 (minigame_effects.py:241)
- **Enemy attack anim**: windup scale up to ×1.12; tint α 60×t; blur ribbons 3 layers ×0.15 offset (renderer.py:1553, 1566, 1481-1501)
- **HP bar thresholds**: >0.5 green, >0.25 yellow, else red (renderer.py:1648)
- **NPC render culling**: chunk buckets keyed `(id(list), len)`, ±1 chunk margin (907-949)

---

## 6. Event topics (GameEventBus)

**Subscribed** (VisualEffectBridge.connect, visual_effect_bridge.py:71-78, priority=10):
`DAMAGE_DEALT`, `ENEMY_KILLED`, `PLAYER_HIT`, `DODGE_PERFORMED`, `SCREEN_SHAKE`, `PARTICLE_BURST` (unsubscribe mirror 85-90).

**Published** (helpers in visual_effect_bridge.py; called from game logic):
- `DAMAGE_DEALT` — publish_damage_dealt :197-212 (payload: target_id, attacker_id, amount, damage_type, is_crit, position_x/y) — callers game_engine.py:3776, 3992; Combat/combat_manager.py:798, 1740
- `ENEMY_KILLED` — :215-232 (enemy_id, killer_id, position, tier, visual_size, is_boss, loot) — game_engine.py:3801, 4020; combat_manager.py:843, 1800
- `PLAYER_HIT` — :235-248 — game_engine.py:3838; combat_manager.py:2142
- `DODGE_PERFORMED` — :251-261 — game_engine.py:966
- `ATTACK_STARTED` — :264-276 — game_engine.py:3911 (**no subscriber in the bridge — published into the void unless WMS listens**)

Event-payload contracts (the dict keys above) are the IPC-ready seam: in Godot, game-logic C# publishes these same topics; the VFX coordinator node subscribes.

---

## 7. Content JSON & assets consumed

| Path | Loader | Used for |
|------|--------|----------|
| `Definitions.JSON/visual-config.JSON` | `data/databases/visual_config_db.py` (`get_visual_config`) + `rendering/visual_colors.py:92` | ALL damage-number physics/colors, entity visuals, enemy tiers/death, telegraphs, particles, screen effects, debug colors. This is **system configuration** (allowed to evolve), not sacred content |
| Map/waypoint UI config (via `MapWaypointConfig`) | `data/databases/map_waypoint_db.py` (renderer.py:46, 3718) | Map window size, panel width, colors, chunk render size, center-on-player |
| `assets/**` PNGs (3,749 icons) | `rendering/image_cache.py` — routing: paths starting `enemies/ resources/ skills/ titles/ npcs/ quests/ classes/` load direct; everything else prefixed `items/` (image_cache.py:59-64); station pattern `stations/{name}_t{tier}.png` (renderer.py:1047); devices `devices/{item_id}.png` (1106); classes `classes/{id}.png` (3040); quests `quests/{quest_id}.png` (4246); npcs `npcs/{npc_id}.png` (967) | Reused VERBATIM as Godot import assets; port the path-resolver rules |
| Content DBs (read-only, for icon_path + tooltip data): materials, equipment, recipes, skills, titles, classes, npcs, placements, resource-nodes | singleton DBs (renderer.py:21-30, 1319) | Icons, names, tooltips, recipe hints |
| Minigame backgrounds | `core/minigame_effects.find_background_image` (:25-45) | Optional discipline background images |

The renderer **never writes** any JSON.

---

## 8. Persistent state

**None.** Neither `rendering/` nor `animation/` reads or writes save files. All state is per-session (image cache, terrain surface cache, map prescale cache, live particle/damage-number/death-effect lists, pending tooltips, NPC buckets). Player-visible persistent things rendered here are OWNED elsewhere: map explored chunks + waypoints (`map_system`), quest state (`character`), notifications (engine). One quirk: `render_start_menu` lists `saves/*.json` directly from disk each frame (renderer.py:7325-7330) — read-only.

---

## 9. 3D notes (what NECESSARILY changes 2D→3D)

1. **Coordinates**: Python `Position(x, y)` in tile units → Godot `(x, 0, z)` per standing decision. Every `camera.world_to_screen` call (≈120 sites in renderer) disappears; world-anchored UI (nameplates, damage numbers, prompts) uses Label3D/billboards or `Camera3D.unproject_position`.
2. **Facing**: `facing_angle` degrees in screen plane (renderer.py:1619, visual_effects.py:236) → Y-axis rotation of the model. The 2D "facing triangle" indicators (A13, A19) become actual model orientation; keep only as debug gizmo.
3. **Telegraphs move from overlay to ground**: arcs/circles drawn as screen-space alpha surfaces (B3/B4) must become floor-projected decals/meshes at world Y=0 — same radii in world units (tiles ≡ meters if 1 tile = 1 unit), same fill-with-progress animation. This is the highest-fidelity-critical VFX (dodge gameplay depends on it).
4. **Draw order → depth**: painter's algorithm order in `render_world` (tiles → stations → placed entities → chests → entrances → resources → enemies → NPCs → player → combat overlays → damage numbers → death effects, renderer.py:1004-1723) is replaced by Z-buffer; transparency-sorted VFX need explicit `sorting_offset`/render priority.
5. **Screen shake** becomes Camera3D offset/rotation noise; HUD on CanvasLayer is inherently unaffected (today enforced by resetting `camera.shake_offset` before UI, game_engine.py:8638).
6. **Day/night tint quad** (C1) becomes real lighting (DirectionalLight energy/color + Environment ambient) — the exact color/alpha curves in §5 translate to light color/intensity keyframes.
7. **Tile texturing**: per-tile cached 32px surfaces → ground shader or baked chunk textures; the noise must remain world-space deterministic so the world looks the same in both engines (test: same seed → same warm/cool patches).
8. **Camera assumptions**: current camera is always player-centered top-down with fixed zoom (TILE_SIZE=32 px/tile). A free 3D camera changes what "visible" means — all `get_visible_*` culling calls keyed to viewport pixels (renderer.py:1014, 1033, 1078, 1262, 1305) must switch to camera frustum/distance culling.
9. **Hitbox/telegraph congruence**: hitboxes are 2D shapes (circle/arc/line/rect) in the tile plane. In 3D they stay planar (cylinder/wedge volumes at ground level); telegraph decals must use the SAME geometry source (today guaranteed by reading `attack_def.hitbox_*` and enemy `_attack_*` fields — keep that single-source pattern).
10. **Minigames stay 2D**: Control-node overlay panels in screen space (per standing decision); their input remains mouse/screen coordinates — no 3D changes, only pygame→Control translation.
11. **Mouse-to-world aiming**: attack angle from mouse vs screen-center (game_engine.py:3684-3691) → ray-cast from Camera3D through mouse to ground plane.

---

## 10. Godot mapping (proposed structure)

### Pure-logic assembly (`GameLogic.dll`, dotnet-testable, no Godot types)
- `Presentation.VisualColors` — port of visual_colors.py (element/tier/state palettes, JSON-backed w/ fallbacks)
- `Presentation.VisualConfig` — port of visual_config_db.py (all §5 damage/death/telegraph params)
- `Presentation.WeaponVisualStyle` + `WeaponVisualResolver` — port of weapon_visuals.py verbatim
- `Presentation.IconPathResolver` — image_cache path routing rules (items/ prefix logic)
- `Presentation.TerrainNoise` — hash/fbm + palette blend (pure math; also transpiled to GLSL — keep C# as the reference implementation for tests)
- `Presentation.MapImageBuilder` — port of map_cache.py producing raw RGBA byte array from chunk data (engine glue wraps in ImageTexture)
- `Presentation.DamageNumberSim` — position/alpha/scale lifecycle math from visual_effects.py:88-114 (unit-test the arc)
- `Presentation.ScreenShakeState`, `FlashState`, `AfterimageState` — port of Combat/screen_effects.py
- `Game.Events` — GameEventBus port + the publish helper functions **moved here from rendering** (breaks the Combat→rendering edge)
- `UI.RecipeGrouping` — `_group_recipes_by_type` moved out of the renderer
- `UI.GridSizing` — tier→grid size map (renderer.py:64-75)

### Engine glue (Godot C# nodes/scenes)
| Godot construct | Replaces |
|-----------------|----------|
| `WorldRoot` (Node3D) + `GroundShader`/GridMap | tile rendering (A1-A2) |
| `EntityView` scenes: `StationView`, `PlacedEntityView`, `ChestView`, `DungeonEntranceView`, `ResourceNodeView`, `EnemyView`, `NpcView`, `PlayerView` | render_world entity loops (A3-A19); each owns its Label3D nameplate/bars |
| `VfxCoordinator` (autoload) — subscribes to event topics, spawns pooled VFX | VisualEffectBridge subscriber half |
| `TelegraphDecal` (Decal/quad+shader, pooled) | _draw_telegraph_arc + windup telegraphs (B3/B4) |
| `HitboxFlashVfx`, `SlashArcVfx`, `ThrustVfx`, `ImpactBurstVfx`, `AreaRingVfx`, `BlockedPopup` (pooled scenes) | active-hitbox + attack-effects drawing (B6/B9) |
| `ProjectileView` scenes (orb/elongated/beam) | B7 |
| `CombatParticles3D` (GPUParticles3D presets per element) | animation/combat_particles + emit sites (B8) |
| `DamageNumbers` (autoload; Label3D pool or CanvasLayer w/ unproject) | B10/B11 unified |
| `DeathEffectPlayer` (per-EnemyView AnimationPlayer) | B12 |
| `CameraRig` (Camera3D + shaker) | core/camera.py + shake plumbing (B13) |
| `DayNightController` (DirectionalLight3D + Environment) | C1/C2 |
| `Hud` (CanvasLayer): `CharacterPanel`, `BuffList`, `SkillHotbar`, `InventoryPanel`, `ToastQueue`, `DebugMessages` | D1-D6 |
| Menu scenes: `StartMenu`, `PauseMenu`, `LoadingScreen`, `ClassSelect`, `StatsPanel`, `SkillsMenu`, `EquipmentMenu`, `Encyclopedia`, `MapScreen`, `DialoguePanel`, `ChestPanel`, `CraftingPanel` (+ per-discipline placement Controls), `EnchantSelect` | E1-E14 (all native Controls — click-rect protocol deleted) |
| `MinigameOverlay` Control scenes ×6 + GPUParticles2D presets | §0.F (stays 2D per decision) |
| `WesOverlay` (CanvasLayer, debug builds) — renders ring-buffer events fetched over sidecar IPC | D8 |
| `LlmLoadingOverlay` / `ClassifierToast` — driven by sidecar IPC job status | D9/D10 |
| `DebugDraw` (ImmediateMesh) behind F1 flag | B14 |

Autoload singletons: `EventBus`, `VfxCoordinator`, `DamageNumbers`, `IconCache` (Texture2D dictionary honoring IconPathResolver), `VisualConfigService` (wraps pure-logic loaders, exposes reload for designer tuning).

---

## 11. Port complexity, ordering, risks

### Complexity
- **Overall: XL** (it is the entire game's face), but decomposable:
  - Pure-logic ports (visual_colors, visual_config, weapon_visuals, screen_effects state, map builder, terrain noise, recipe grouping): **S-M** each, fully unit-testable
  - World entity views + HUD: **L** (breadth, not depth — dozens of simple scenes)
  - Combat VFX + telegraphs: **L** (fidelity-critical, gameplay-readability-critical)
  - Menus/panels: **L** breadth (14 screens) but each is routine Control work
  - Minigame overlays: **M-L** (6 disciplines; logic already separate in `Crafting-subdisciplines/`)
  - Map screen: **M** (after MapImageBuilder exists)

### Ordering constraints
1. `Game.Events` bus + moved publish helpers FIRST (combat port depends on it; kills the Combat→rendering edge before Combat is ported)
2. `VisualConfig`/`VisualColors`/`IconPathResolver` (everything visual reads them)
3. CameraRig + world→screen label strategy (every nameplate/damage number needs it)
4. EntityView scenes for world objects (needs world/chunk port from doc 05 and content DB loaders from doc 01)
5. VfxCoordinator + damage numbers + telegraphs (needs Combat hitbox/ASM port emitting the same events/fields: `attack_phase`, `_attack_windup_ms`, `_attack_arc_degrees`, `_attack_radius`, `hitbox_offset_forward`)
6. HUD, then menus (need character/inventory/skills ports)
7. Minigame overlays last (self-contained 2D)

### Top risks / gotchas (all verified in code)
1. **Hidden logic inside the renderer**: `_group_recipes_by_type` (renderer.py:5293-5419) is used by the engine's CLICK HANDLER (game_engine.py:1410, 6507) — if the port treats renderer as pure view and drops it, crafting selection breaks. Same for tier→grid-size (64-75) and the station-icon-name map (1039-1046).
2. **Combat logic imports rendering** (combat_manager.py:798+ → visual_effect_bridge publish helpers). Port order must move these helpers into the events assembly first or Combat can't be a pure-logic DLL.
3. **World gen produces pygame surfaces** (`world_system.map_images`, systems/world_system.py:61,381 via rendering/map_cache) — the sidecar/logic boundary is violated today; the Godot port must regenerate map textures engine-side from chunk data (MapImageBuilder), and the world-gen port must NOT try to carry this over.
4. **F12 overlay is pygame code inside `world_system/`** (observability_overlay.py) — since world_system becomes a Python sidecar, the overlay dies unless rebuilt in Godot consuming `obs_recent()/obs_stats()` over IPC. It is a shipped operator feature (CLAUDE.md-documented); do not lose it.
5. **Double-spawn duplication on the action-combat path**: each player hit spawns an enhanced damage number + hit sparks DIRECTLY (game_engine.py:3760-3769) AND publishes DAMAGE_DEALT which the bridge handles by spawning into the SAME manager (visual_effect_bridge.py:108-116) — today players see stacked duplicate numbers/sparks (anti-stack offsets them). The Godot port must pick ONE path (event-driven) — and note parity means "one number per hit", not bug-for-bug duplication.
6. **Silently-broken bridge features** (don't cargo-cult them): bridge probes `emit_death_burst`/`emit_burst` which **do not exist** on CombatParticleSystem (visual_effect_bridge.py:142-143, 190-191 vs combat_particles.py — hasattr guards make them silent no-ops), and calls `emit_dodge_dust(x, y, direction)` with 3 args against a 2-arg signature (bridge :172 vs combat_particles.py:130) — TypeError swallowed by the EventBus handler guard (events/event_bus.py:152-154). Death-burst particles, PARTICLE_BURST, and event-driven dodge dust have NEVER rendered. Decide deliberately whether to implement or drop them in Godot.
7. **Dead code — do not port**: `animation/procedural.py` (0 callers), `animation/animation_manager.py` registry (update_all ticked at game_engine.py:3620 but `.play()` never called), `animation/sprite_animation.py` + `animation_data.py` (only serve the dead stack), `map_cache.get_best_lod` (0 callers), `terrain_renderer.clear_terrain_cache` (0 callers), `emit_projectile_trail` (0 callers), `ScreenEffects.hit_pause` (designed no-op, §15 trap 16).
8. **Attribute-injection contract**: `_temp_npcs`, `_temp_ac_systems`, `_temp_combat_manager`, `_temp_scroll_offset`, `_temp_user_placement`, `_damage_number_manager`, `_death_effect_manager`, `_debug_hitboxes` are set on the renderer by the engine each frame (game_engine.py:8604-8741). These are the REAL render inputs; the Godot design must make them explicit dependencies or none of the overlays fire.
9. **Palette drift**: dungeon enemies use a hardcoded tier palette different from visual-config (renderer.py:2401-2406); dungeon damage numbers use only the legacy path (2477-2484) while the overworld uses the enhanced manager (1693-1695) — decide one unified look (recommend visual-config everywhere) and record it as an intentional parity deviation.
10. **Telegraph/hitbox congruence is load-bearing gameplay**: origin offsets (`visual_size×0.6` enemy, `hitbox_offset_forward` player) and radii are read from the same attack data the hitbox system uses (renderer.py:1944-1961, 1990-1995). If the Godot decals compute geometry independently, dodge timing visually lies. Keep a single geometry source.
11. **Designer-tunability must survive**: everything in `visual-config.JSON` is designer-owned (§15 reconciliation deliberately centralized colors there, see visual_colors.py docstring:1-20). The Godot port must keep reading the same JSON (or a converted resource with a migration script), not bake values into scenes.
12. **Text/emoji glyphs** (renderer.py:1245, 2364, 3184, 4206, 4227) need icon replacements; "∞" durability marker (3125) and "°C" (game_engine.py:9307) need font coverage checks.

---

*Files covered: 15 in-scope (rendering/ 8 + animation/ 7), plus 8 adjacent presentation files inventoried in §1b. In-scope LOC: 10,810 (wc-verified); ~14,700 including adjacent presentation code this contract governs.*
