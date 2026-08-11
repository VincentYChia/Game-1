I have plenty now. Let me produce the report.

---

# Rendering, Animation, UI, Audio, Input — Tunable Controls Survey

## Files most-tuned-by-designer

| Path | What's in here |
|---|---|
| `Game-1-modular/Definitions.JSON/visual-config.JSON` | Master VFX/animation timing JSON: damage numbers, telegraphs, particles, screen effects, debug, entity visuals, enemy tier scale. **The first place to tune anything visual.** |
| `Game-1-modular/Definitions.JSON/map-waypoint-config.JSON` | Map UI tuning: zoom defaults/min/max, biome colors, marker icons, waypoint unlock schedule, teleport cooldown, UI window size, keybindings. |
| `Game-1-modular/Definitions.JSON/combat-config.JSON` | Spawn rates by danger tier, respawn times, crit multiplier, shield reduction cap, safe-zone radius. (Crosses into combat balance.) |
| `Game-1-modular/core/config.py` | Hardcoded global constants — screen, FPS, tile size, viewport %, all UI colors, RARITY_COLORS, debug flags. |
| `Game-1-modular/animation/weapon_visuals.py` | Tag→VFX tables (ELEMENT_COLORS, weapon type profiles, tier intensity). Authored in Python, not JSON. |

## Files mostly code-internal but containing tunables

| Path | Brief |
|---|---|
| `Game-1-modular/data/databases/visual_config_db.py` | Singleton wrapper; defines fallback defaults if visual-config.JSON keys are missing — defaults are duplicated here. |
| `Game-1-modular/rendering/renderer.py` | 8029 lines. Many hardcoded layout numbers per UI panel (slot sizes, padding, button heights). Also embedded `_ETAG_COLORS`, `_STATE_COLORS`, `_ELEMENT_COLORS`, `COLORS` dicts. |
| `Game-1-modular/rendering/visual_effects.py` | Enhanced damage numbers, player rendering helpers, enemy death effects, debug hitbox visualization. Mostly reads VisualConfig. |
| `Game-1-modular/rendering/visual_effect_bridge.py` | Event→VFX dispatcher. Hardcoded `_KILL_SHAKE` (per-tier) and `_TIER_COLORS` (per-tier) dicts at top of file. |
| `Game-1-modular/rendering/terrain_renderer.py` | Procedural tile color palettes (TILE_PALETTES) + cache size `_CACHE_MAX = 4096`. |
| `Game-1-modular/rendering/map_cache.py` | Map image generation: ppc=4 (pixels per chunk), border colors, blur radius. |
| `Game-1-modular/rendering/image_cache.py` | Asset path resolution. Subfolder mapping. |
| `Game-1-modular/animation/animation_data.py` | Pure dataclasses (no constants). |
| `Game-1-modular/animation/animation_manager.py` | Pure singleton registry (no constants). |
| `Game-1-modular/animation/procedural.py` | Procedural animation generator — default arc degrees / radius / num_frames / colors are function args (designer can override at registration site). |
| `Game-1-modular/animation/sprite_animation.py` | Pure player class (no constants). |
| `Game-1-modular/animation/combat_particles.py` | Hit-spark/dodge-dust/trail particle counts, lifetimes, gravity, drag. `DAMAGE_SPARK_COLORS` per element. |
| `Game-1-modular/core/minigame_effects.py` | All discipline ColorPalettes, particle behaviors, screen shake, flame effect, rotating gears, animated progress bar, animated button. Big VFX library. |
| `Game-1-modular/core/camera.py` | Tiny — just world↔screen math; shake_offset injected by ScreenEffects. |
| `Game-1-modular/core/notifications.py` | Notification dataclass: `lifetime: float = 3.0` default. |
| `Game-1-modular/core/debug_display.py` | Debug log overlay: max_messages = 5, abbreviation table. |
| `Game-1-modular/core/game_engine.py` | All keybindings + observability overlay font size + main loop FPS. |
| `Game-1-modular/Combat/screen_effects.py` | Afterimage life (300ms), shake/flash logic. |
| `Game-1-modular/Combat/player_actions.py` | Dodge duration/cooldown/iframe duration/dodge speed mult (hardcoded). `FACING_TO_ANGLE` dict. |
| `Game-1-modular/world_system/wes/observability_overlay.py` | F12 overlay color map, panel max_events=15, width=600, font size set in game_engine. |

**Audio:** No `audio/`, `sound/`, `sfx/`, `music/` directory exists in `Game-1-modular/`. No pygame.mixer usage. Audio is **not implemented**. No sound triggers, no volume sliders, no music params, no UI click sounds.

---

## Tunable controls table

### Screen / Engine / Camera (Global)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 1 | screen | Design baseline width | `core/config.py:10` | `BASE_WIDTH=1600` | P2 |
| 2 | screen | Design baseline height | `core/config.py:11` | `BASE_HEIGHT=900` | P2 |
| 3 | screen | Default window width | `core/config.py:14` | `SCREEN_WIDTH=1600` | P1 |
| 4 | screen | Default window height | `core/config.py:15` | `SCREEN_HEIGHT=900` | P1 |
| 5 | screen | FPS cap | `core/config.py:16` | `FPS=60` | P0 |
| 6 | screen | Fullscreen default | `core/config.py:17` | `FULLSCREEN=False` | P2 |
| 7 | screen | UI scale | `core/config.py:20` | `UI_SCALE=1.0` (auto-derived from height) | P1 |
| 8 | screen | Clamp min size | `core/config.py:85-86` | min 1280×720 / max 3840×2160 | P2 |
| 9 | screen | Windowed area % of display | `core/config.py:81-82` | 90% | P2 |
| 10 | viewport | Viewport width % | `core/config.py:95` | 75% of screen | P1 |
| 11 | viewport | Viewport height % | `core/config.py:96` | 100% | P2 |
| 12 | world | Chunk size (tiles) | `core/config.py:24` | `CHUNK_SIZE=16` | P0 |
| 13 | world | Tile pixel size | `core/config.py:25` | `TILE_SIZE=32` | P0 |
| 14 | world | Entity visual scale | `core/config.py:26` | `ENTITY_VISUAL_SCALE=1.0` | P1 |
| 15 | world | Chunk load radius | `core/config.py:32` | `CHUNK_LOAD_RADIUS=4` | P1 |
| 16 | world | Spawn always-loaded radius | `core/config.py:33` | `SPAWN_ALWAYS_LOADED=1` | P2 |
| 17 | world | Player spawn (x,y,z) | `core/config.py:40-42` | `(0.0, 0.0, 0.0)` | P2 |
| 18 | world | Safe zone radius (default) | `core/config.py:45` | `SAFE_ZONE_RADIUS=8` | P1 |
| 19 | player | Player speed (tiles/tick) | `core/config.py:151` | `PLAYER_SPEED=0.15` | P0 |
| 20 | player | Interaction range (tiles) | `core/config.py:152` | `INTERACTION_RANGE=3.5` | P0 |
| 21 | player | Click tolerance | `core/config.py:153` | `CLICK_TOLERANCE=0.7` | P1 |
| 22 | camera | Screen shake plumbing | `core/camera.py:16` | injected from ScreenEffects | P2 |

### Menu size presets (scaled by UI_SCALE)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 23 | menus | Small menu W×H | `core/config.py:111-112` | 600×500 | P1 |
| 24 | menus | Medium menu W×H | `core/config.py:113-114` | 800×600 | P1 |
| 25 | menus | Large menu W×H | `core/config.py:115-116` | 1000×700 | P1 |
| 26 | menus | XLarge menu W×H | `core/config.py:117-118` | 1200×750 | P1 |

### UI Panel / Inventory layout

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 27 | ui | UI panel width | `core/config.py:52` | `UI_PANEL_WIDTH=400` (auto = screen-viewport) | P1 |
| 28 | inv | Panel X (left) | `core/config.py:53` | 0 | P2 |
| 29 | inv | Panel Y (top) | `core/config.py:54` | 600 (auto-scaled) | P1 |
| 30 | inv | Panel width | `core/config.py:55` | 1200 (=viewport) | P2 |
| 31 | inv | Panel height | `core/config.py:56` | 300 (auto = h - panelY) | P2 |
| 32 | inv | Slot pixel size | `core/config.py:57` | `INVENTORY_SLOT_SIZE=50` (scaled) | P0 |
| 33 | inv | Slots per row | `core/config.py:58,108` | 10 (auto from width / slot+5) | P0 |
| 34 | inv | Slot spacing fudge | `core/config.py:106` | `slot_spacing=5` (calc only) | P2 |
| 35 | inv | Inventory render spacing | `rendering/renderer.py:5063,5069` | `spacing=10` (hardcoded; *must match engine click handling at 1401/2203/6903*) | P1 |
| 36 | inv | Weight bar position/size | `rendering/renderer.py:4943-4947` | x=120 y=panelY+12 w=120 h=12 | P2 |
| 37 | inv | Encumbrance bar colors | `rendering/renderer.py:4954-4959` | green/red dynamic | P2 |
| 38 | inv | Tool slot size (axe/pick) | `rendering/renderer.py:4978` | 50 | P2 |
| 39 | inv | Tool slot spacing | `rendering/renderer.py:4979` | 10 | P2 |

### Debug Flags

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 40 | debug | Infinite resources (F1) | `core/config.py:156` | False | P2 |
| 41 | debug | Infinite durability (F7) | `core/config.py:157` | False | P2 |
| 42 | debug | Keep inventory on death (F5) | `core/config.py:160` | True | P1 |

### Color palette (Config class — global UI tone)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 43 | colors | Background | `core/config.py:164` | (20,20,30) | P2 |
| 44 | colors | Grid | `core/config.py:165` | (40,40,50) | P2 |
| 45 | colors | Grass | `core/config.py:166` | (34,139,34) | P2 |
| 46 | colors | Stone | `core/config.py:167` | (128,128,128) | P2 |
| 47 | colors | Water | `core/config.py:168` | (30,144,255) | P2 |
| 48 | colors | Player | `core/config.py:169` | (255,215,0) (NOTE: visual-config.JSON overrides to blue 80,180,255) | P1 |
| 49 | colors | Interaction range overlay | `core/config.py:170` | (255,255,0,50) | P2 |
| 50 | colors | UI BG | `core/config.py:171` | (30,30,40) | P1 |
| 51 | colors | Text | `core/config.py:172` | (255,255,255) | P1 |
| 52 | colors | Health (foreground) | `core/config.py:173` | (255,0,0) | P1 |
| 53 | colors | Health BG | `core/config.py:174` | (50,50,50) | P2 |
| 54 | colors | Tree | `core/config.py:175` | (0,100,0) | P2 |
| 55 | colors | Ore | `core/config.py:176` | (169,169,169) | P2 |
| 56 | colors | Stone node | `core/config.py:177` | (105,105,105) | P2 |
| 57 | colors | HP bar | `core/config.py:178` | (0,255,0) | P2 |
| 58 | colors | HP bar BG | `core/config.py:179` | (100,100,100) | P2 |
| 59 | colors | Damage normal | `core/config.py:180` | (255,255,255) | P2 |
| 60 | colors | Damage crit | `core/config.py:181` | (255,215,0) | P2 |
| 61 | colors | Slot empty | `core/config.py:182` | (40,40,50) | P2 |
| 62 | colors | Slot filled | `core/config.py:183` | (50,60,70) | P2 |
| 63 | colors | Slot border | `core/config.py:184` | (100,100,120) | P2 |
| 64 | colors | Slot selected | `core/config.py:185` | (255,215,0) | P2 |
| 65 | colors | Tooltip BG | `core/config.py:186` | (20,20,30,230) | P2 |
| 66 | colors | Respawn bar | `core/config.py:187` | (100,200,100) | P2 |
| 67 | colors | Can harvest | `core/config.py:188` | (100,255,100) | P2 |
| 68 | colors | Cannot harvest | `core/config.py:189` | (255,100,100) | P2 |
| 69 | colors | Notification | `core/config.py:190` | (255,215,0) | P1 |
| 70 | colors | Equipped indicator | `core/config.py:191` | (255,215,0) (gold border) | P2 |
| 71 | colors | RARITY common | `core/config.py:194` | (200,200,200) | P1 |
| 72 | colors | RARITY uncommon | `core/config.py:195` | (30,255,0) | P1 |
| 73 | colors | RARITY rare | `core/config.py:196` | (0,112,221) | P1 |
| 74 | colors | RARITY epic | `core/config.py:197` | (163,53,238) | P1 |
| 75 | colors | RARITY legendary | `core/config.py:198` | (255,128,0) | P1 |
| 76 | colors | RARITY artifact | `core/config.py:199` | (230,204,128) | P1 |

### visual-config.JSON: damageNumbers

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 77 | damage# | Lifetime (ms) | `visual-config.JSON:damageNumbers.lifetimeMs` | 1200 | P0 |
| 78 | damage# | Initial vy | `…initialVelocityY` | -2.5 | P1 |
| 79 | damage# | Horizontal spread | `…horizontalSpread` | 0.6 | P2 |
| 80 | damage# | Gravity | `…gravity` | 0.08 | P2 |
| 81 | damage# | Shrink rate / frame | `…shrinkRate` | 0.997 | P2 |
| 82 | damage# | Crit scale multiplier | `…critScaleMultiplier` | 1.8 | P1 |
| 83 | damage# | Crit bounce flag | `…critBounce` | true | P2 |
| 84 | damage# | Anti-stack offset (px) | `…stackOffsetPx` | 18 | P2 |
| 85 | damage# | Type color: physical | `…typeColors.physical` | [255,255,255] | P1 |
| 86 | damage# | Type color: fire | `…typeColors.fire` | [255,140,40] | P1 |
| 87 | damage# | Type color: ice | `…typeColors.ice` | [100,200,255] | P1 |
| 88 | damage# | Type color: lightning | `…typeColors.lightning` | [255,255,80] | P1 |
| 89 | damage# | Type color: poison | `…typeColors.poison` | [100,255,80] | P1 |
| 90 | damage# | Type color: arcane | `…typeColors.arcane` | [200,100,255] | P1 |
| 91 | damage# | Type color: shadow | `…typeColors.shadow` | [160,100,200] | P1 |
| 92 | damage# | Type color: holy | `…typeColors.holy` | [255,255,180] | P1 |
| 93 | damage# | Type color: heal | `…typeColors.heal` | [80,255,80] | P1 |
| 94 | damage# | Type color: shield | `…typeColors.shield` | [100,180,255] | P1 |
| 95 | damage# | Crit color | `…critColor` | [255,220,50] | P1 |
| 96 | damage# | Miss text | `…missText` | "MISS" | P1 |
| 97 | damage# | Miss color | `…missColor` | [180,180,180] | P2 |
| 98 | damage# | Block text | `…blockText` | "BLOCKED" | P1 |
| 99 | damage# | Block color | `…blockColor` | [100,160,255] | P2 |
| 100 | damage# | Dodge text | `…dodgeText` | "DODGE" | P1 |
| 101 | damage# | Dodge color | `…dodgeColor` | [150,200,255] | P2 |

### visual-config.JSON: entityVisuals (player)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 102 | player | Render radius (tiles) | `entityVisuals.playerRadius` | 0.33 | P0 |
| 103 | player | Body color | `…playerColor` | [80,180,255] | P0 |
| 104 | player | Outline color | `…playerOutlineColor` | [40,100,160] | P1 |
| 105 | player | Facing indicator length | `…facingIndicatorLength` | 0.5 | P2 |
| 106 | player | Facing indicator width | `…facingIndicatorWidth` | 2 | P2 |
| 107 | player | Facing indicator color | `…facingIndicatorColor` | [200,220,255] | P2 |
| 108 | player | Weapon arc preview enabled | `…weaponArcPreview` | true | P2 |
| 109 | player | Weapon arc alpha | `…weaponArcAlpha` | 40 | P2 |
| 110 | player | Shadow enabled | `…shadowEnabled` | true | P2 |
| 111 | player | Shadow alpha | `…shadowAlpha` | 40 | P2 |
| 112 | player | Shadow scale | `…shadowScale` | 0.7 | P2 |
| 113 | player | Idle bob amplitude (px) | `…idleBobAmplitude` | 1.5 | P2 |
| 114 | player | Idle bob period (ms) | `…idleBobPeriodMs` | 2000 | P2 |

### visual-config.JSON: enemyVisuals

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 115 | enemy | Tier 1 scale | `enemyVisuals.tierScale.1` | 1.0 | P1 |
| 116 | enemy | Tier 2 scale | `…tierScale.2` | 1.3 | P1 |
| 117 | enemy | Tier 3 scale | `…tierScale.3` | 1.6 | P1 |
| 118 | enemy | Tier 4 scale | `…tierScale.4` | 2.0 | P1 |
| 119 | enemy | Tier glow flags (per tier) | `…tierGlow.{1-4}` | T1/T2=false, T3/T4=true | P1 |
| 120 | enemy | Tier 3 glow intensity | `…tierGlowIntensity.3` | 0.3 | P2 |
| 121 | enemy | Tier 4 glow intensity | `…tierGlowIntensity.4` | 0.6 | P2 |
| 122 | enemy | Boss glow color | `…bossGlowColor` | [255,215,0] | P2 |
| 123 | enemy | Death fade duration (ms) | `…deathFadeDurationMs` | 600 | P1 |
| 124 | enemy | Death shrink factor | `…deathShrinkFactor` | 0.3 | P2 |
| 125 | enemy | Death rotation deg | `…deathRotationDegrees` | 15 | P2 |
| 126 | enemy | Corpse linger ms | `…corpseLingerMs` | 5000 | P1 |
| 127 | enemy | Corpse fade ms | `…corpseFadeMs` | 1000 | P2 |
| 128 | enemy | Spawn fade-in ms | `…spawnFadeInMs` | 400 | P2 |
| 129 | enemy | Hit flash duration ms | `…hitFlashDurationMs` | 80 | P1 |
| 130 | enemy | State color: idle | `…stateIndicatorColors.idle` | [100,200,100] | P2 |
| 131 | enemy | State color: wander | `…wander` | [100,200,100] | P2 |
| 132 | enemy | State color: patrol | `…patrol` | [100,200,100] | P2 |
| 133 | enemy | State color: guard | `…guard` | [180,180,100] | P2 |
| 134 | enemy | State color: chase | `…chase` | [255,200,50] | P1 |
| 135 | enemy | State color: attack | `…attack` | [255,80,60] | P0 |
| 136 | enemy | State color: flee | `…flee` | [100,150,255] | P2 |
| 137 | enemy | State color: dead | `…dead` | [100,100,100] | P2 |

### visual-config.JSON: telegraphs

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 138 | tele | Player telegraph color | `telegraphs.playerColor` | [100,180,255] | P1 |
| 139 | tele | Enemy telegraph color | `…enemyColor` | [255,100,100] | P0 |
| 140 | tele | Fill alpha base | `…fillAlphaBase` | 30 | P2 |
| 141 | tele | Fill alpha max | `…fillAlphaMax` | 210 | P2 |
| 142 | tele | Edge alpha multiplier | `…edgeAlphaMultiplier` | 0.9 | P2 |
| 143 | tele | Glow pad base | `…glowPadBase` | 4 | P2 |
| 144 | tele | Glow pad max | `…glowPadMax` | 10 | P2 |
| 145 | tele | Pulse frequency (Hz) | `…pulseFrequency` | 10.0 | P1 |
| 146 | tele | Danger indicator size | `…dangerIndicatorSize` | 4 | P2 |
| 147 | tele | Projectile aim line width | `…projectileAimLineWidth` | 2 | P2 |
| 148 | tele | Projectile aim glow width | `…projectileAimGlowWidth` | 5 | P2 |

### visual-config.JSON: particles

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 149 | particles | Max particles (budget) | `particles.maxParticles` | 400 | P1 |
| 150 | particles | Hit spark count (min,max) | `…hitSparkCount` | [5, 8] | P0 |
| 151 | particles | Hit spark speed range | `…hitSparkSpeed` | [1.5, 4.0] | P1 |
| 152 | particles | Hit spark life ms range | `…hitSparkLifeMs` | [200, 500] | P1 |
| 153 | particles | Hit spark gravity | `…hitSparkGravity` | 3.0 | P2 |
| 154 | particles | Slash trail count | `…slashTrailCount` | 6 | P1 |
| 155 | particles | Dodge dust count | `…dodgeDustCount` | 6 | P2 |
| 156 | particles | Dodge dust life ms | `…dodgeDustLifeMs` | 300 | P2 |
| 157 | particles | Projectile trail interval | `…projectileTrailInterval` | 0.03 | P2 |
| 158 | particles | Death burst count | `…deathBurstCount` | 12 | P1 |
| 159 | particles | Death burst speed range | `…deathBurstSpeed` | [2.0, 5.0] | P1 |
| 160 | particles | Death burst life ms range | `…deathBurstLifeMs` | [400, 800] | P1 |
| 161 | particles | Level-up burst count | `…levelUpBurstCount` | 20 | P2 |

### visual-config.JSON: screenEffects

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 162 | screen | Shake decay rate (per frame) | `screenEffects.shakeDecayRate` | 0.88 | P1 |
| 163 | screen | Max shake offset (px) | `…shakeMaxOffset` | 12 | P1 |
| 164 | screen | Flash default duration ms | `…flashDefaultDurationMs` | 80 | P2 |
| 165 | screen | Afterimage fade rate | `…afterimageFadeRate` | 8.0 | P2 |
| 166 | screen | Afterimage max count | `…afterimageMaxCount` | 10 | P2 |
| 167 | screen | Hit pause enabled | `…hitPauseEnabled` | false (no-op in code) | P2 |
| 168 | screen | Slow motion enabled | `…slowMotionEnabled` | false (no-op in code) | P2 |

### visual-config.JSON: debug

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 169 | debug | Hitbox color | `debug.hitboxColor` | [255,60,60] | P2 |
| 170 | debug | Hitbox alpha | `…hitboxAlpha` | 100 | P2 |
| 171 | debug | Hurtbox color | `…hurtboxColor` | [60,255,60] | P2 |
| 172 | debug | Hurtbox alpha | `…hurtboxAlpha` | 80 | P2 |
| 173 | debug | iframe hurtbox color | `…iframeHurtboxColor` | [60,60,255] | P2 |
| 174 | debug | iframe hurtbox alpha | `…iframeHurtboxAlpha` | 60 | P2 |
| 175 | debug | Projectile trail color | `…projectileTrailColor` | [255,255,100] | P2 |
| 176 | debug | Show entity IDs | `…showEntityIds` | false | P2 |
| 177 | debug | Show facing angles | `…showFacingAngles` | true | P2 |
| 178 | debug | Show attack phase | `…showAttackPhase` | true | P2 |
| 179 | debug | Show damage context | `…showDamageContext` | false | P2 |

### Weapon visual styling (animation/weapon_visuals.py) — currently Python-coded

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 180 | weapon-vfx | Element→color: physical | `weapon_visuals.py:18-29` | (220,225,245) | P0 |
| 181 | weapon-vfx | Element→color: fire | `weapon_visuals.py:20` | (255,120,25) | P0 |
| 182 | weapon-vfx | Element→color: ice/frost | `weapon_visuals.py:21-22` | (90,200,255) | P0 |
| 183 | weapon-vfx | Element→color: lightning | `weapon_visuals.py:23` | (255,255,70) | P0 |
| 184 | weapon-vfx | Element→color: poison | `weapon_visuals.py:24` | (90,255,70) | P0 |
| 185 | weapon-vfx | Element→color: arcane | `weapon_visuals.py:25` | (190,70,255) | P0 |
| 186 | weapon-vfx | Element→color: shadow | `weapon_visuals.py:26` | (140,70,200) | P0 |
| 187 | weapon-vfx | Element→color: holy | `weapon_visuals.py:27` | (255,255,170) | P0 |
| 188 | weapon-vfx | Element→color: chaos | `weapon_visuals.py:28` | (220,50,50) | P0 |
| 189 | weapon-vfx | sword_1h profile | `weapon_visuals.py:37` | arc 65, trail 3, thick 1.0, swing | P1 |
| 190 | weapon-vfx | sword_2h profile | `weapon_visuals.py:38` | arc 100, trail 4, thick 1.4, swing | P1 |
| 191 | weapon-vfx | dagger profile | `weapon_visuals.py:39` | arc 30, trail 2, thick 0.6, swing | P1 |
| 192 | weapon-vfx | axe profile | `weapon_visuals.py:40` | arc 80, trail 4, thick 1.3, swing | P1 |
| 193 | weapon-vfx | mace profile | `weapon_visuals.py:41` | arc 55, trail 3, thick 1.2, swing | P1 |
| 194 | weapon-vfx | hammer_2h profile | `weapon_visuals.py:42` | arc 90, trail 5, thick 1.6, swing | P1 |
| 195 | weapon-vfx | spear profile | `weapon_visuals.py:43` | arc 12, trail 2, thick 0.8, thrust | P1 |
| 196 | weapon-vfx | staff profile | `weapon_visuals.py:44` | arc 35, trail 3, thick 0.7, swing | P1 |
| 197 | weapon-vfx | bow profile | `weapon_visuals.py:45` | arc 0, trail 0, thick 0.5, none | P1 |
| 198 | weapon-vfx | unarmed profile | `weapon_visuals.py:46` | arc 55, trail 2, thick 0.8, swing | P1 |
| 199 | weapon-vfx | Tier intensity table | `weapon_visuals.py:50` | T1=0.7, T2=1.0, T3=1.3, T4=1.6 | P1 |
| 200 | weapon-vfx | Heavy weight threshold | `weapon_visuals.py:125` | weight > 3.0 | P2 |
| 201 | weapon-vfx | Heavy speed_feel formula | `weapon_visuals.py:126` | max(0.6, 1.0-(w-3)*0.1) | P2 |
| 202 | weapon-vfx | Heavy shake intensity | `weapon_visuals.py:127` | min(1.0,(w-3)*0.15) | P2 |
| 203 | weapon-vfx | Light weight threshold | `weapon_visuals.py:130` | weight < 1.0 | P2 |
| 204 | weapon-vfx | Lifesteal glow override | `weapon_visuals.py:150-152` | (255,80,80), +0.15 intensity | P2 |
| 205 | weapon-vfx | Trail color phase ramps | `weapon_visuals.py:165-172` | 0-0.3 ramp, 0.3-0.7 hold, 0.7-1.0 fade | P2 |

### Procedural animation defaults (animation/procedural.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 206 | anim | Swing arc default deg | `procedural.py:62` | 90.0 | P1 |
| 207 | anim | Swing arc default radius px | `procedural.py:63` | 24.0 | P1 |
| 208 | anim | Swing arc duration ms | `procedural.py:64` | 350.0 | P1 |
| 209 | anim | Swing arc num frames | `procedural.py:65` | 6 | P2 |
| 210 | anim | Swing arc default color | `procedural.py:66` | (220,220,240) | P2 |
| 211 | anim | Swing arc default thickness | `procedural.py:67` | 3 | P2 |
| 212 | anim | Swing arc alpha fade phase | `procedural.py:92` | last 25% fades | P2 |
| 213 | anim | Hitbox active window | `procedural.py:115` | 30%-80% of swing | P0 |
| 214 | anim | Telegraph pulse scale range | `procedural.py:134` | (1.0, 1.15) | P1 |
| 215 | anim | Telegraph pulse duration | `procedural.py:135` | 400.0 ms | P1 |
| 216 | anim | Telegraph pulse num frames | `procedural.py:136` | 4 | P2 |
| 217 | anim | Telegraph tint intensity | `procedural.py:162` | progress*0.4 | P2 |
| 218 | anim | Hit flash duration | `procedural.py:181` | 80 ms | P1 |
| 219 | anim | Hit flash color split (60/40) | `procedural.py:189-198` | flash 60%, original 40% | P2 |
| 220 | anim | Hit flash overlay alpha | `procedural.py:53` | 200 (white add) | P2 |
| 221 | anim | Idle bob amplitude default | `procedural.py:209` | 2.0 px | P2 |
| 222 | anim | Idle bob period default | `procedural.py:210` | 1200 ms | P2 |
| 223 | anim | Idle bob num frames | `procedural.py:211` | 8 | P2 |
| 224 | anim | Slash trail default arc | `procedural.py:238` | 90.0 deg | P1 |
| 225 | anim | Slash trail default radius | `procedural.py:239` | 28.0 px | P1 |
| 226 | anim | Slash trail color | `procedural.py:240` | (220,230,255) | P2 |
| 227 | anim | Slash trail thickness | `procedural.py:241` | 3 | P2 |
| 228 | anim | Slash trail duration | `procedural.py:242` | 150.0 ms | P1 |
| 229 | anim | Slash trail num frames | `procedural.py:243` | 4 | P2 |
| 230 | anim | Slash trail alphas/coverages | `procedural.py:253-254` | [255,230,180,80] / [0.25,0.6,1.0,1.0] | P2 |
| 231 | anim | Ground telegraph duration | `procedural.py:296` | 500.0 ms | P1 |
| 232 | anim | Ground telegraph num frames | `procedural.py:297` | 5 | P2 |
| 233 | anim | Ground telegraph alpha ramp | `procedural.py:320` | 40 → 120 | P2 |

### Combat particles (animation/combat_particles.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 234 | particles | DAMAGE_SPARK_COLORS.physical | `combat_particles.py:23` | 3 grey shades | P1 |
| 235 | particles | DAMAGE_SPARK_COLORS.fire | `combat_particles.py:24` | 3 orange shades | P1 |
| 236 | particles | DAMAGE_SPARK_COLORS.ice | `combat_particles.py:25` | 3 blue shades | P1 |
| 237 | particles | DAMAGE_SPARK_COLORS.lightning | `combat_particles.py:26` | 3 yellow/white | P1 |
| 238 | particles | DAMAGE_SPARK_COLORS.poison | `combat_particles.py:27` | 3 green | P1 |
| 239 | particles | DAMAGE_SPARK_COLORS.arcane | `combat_particles.py:28` | 3 purple | P1 |
| 240 | particles | DAMAGE_SPARK_COLORS.shadow | `combat_particles.py:29` | 3 dark purple | P1 |
| 241 | particles | DAMAGE_SPARK_COLORS.holy | `combat_particles.py:30` | 3 yellow-white | P1 |
| 242 | particles | Default particle pool | `combat_particles.py:77` | 400 | P1 |
| 243 | particles | Hit spark count formula | `combat_particles.py:91` | `int(5+intensity*3)` | P1 |
| 244 | particles | Hit spark angle range | `combat_particles.py:94` | 0..2π uniform | P2 |
| 245 | particles | Hit spark speed range | `combat_particles.py:95` | uniform(1.5,4.0)*intensity | P2 |
| 246 | particles | Hit spark life | `combat_particles.py:101` | uniform(0.2,0.5)s | P2 |
| 247 | particles | Hit spark size | `combat_particles.py:102` | uniform(2.0,4.0) | P2 |
| 248 | particles | Hit spark gravity | `combat_particles.py:104` | 5.0 | P2 |
| 249 | particles | Hit spark drag | `combat_particles.py:105` | 3.0 | P2 |
| 250 | particles | Slash trail particle count | `combat_particles.py:112` | 4 | P2 |
| 251 | particles | Dodge dust count | `combat_particles.py:132` | 6 | P2 |
| 252 | particles | Dodge dust color | `combat_particles.py:142` | (180,170,150) | P2 |
| 253 | particles | Projectile-trail palettes | `combat_particles.py:150-158` | per type (fire/ice/arcane/acid/lightning/shadow/arrow) | P1 |
| 254 | particles | Off-screen cull margin | `combat_particles.py:191-193` | ±20 px | P2 |

### Per-discipline minigame VFX (core/minigame_effects.py) — secondary VFX survey

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 255 | mg-vfx | Smithing palette (12 colors) | `minigame_effects.py:95-108` | forge orange/yellow/red set | P1 |
| 256 | mg-vfx | Refining palette (10 colors) | `…111-122` | bronze/kiln set | P1 |
| 257 | mg-vfx | Alchemy palette (13 colors) | `…125-139` | potion blues/greens/purples | P1 |
| 258 | mg-vfx | Engineering palette (11 colors) | `…142-154` | wood/metal/copper/brass | P1 |
| 259 | mg-vfx | Enchanting palette (11 colors) | `…157-169` | spirit light blues | P1 |
| 260 | mg-vfx | AnimationTimer dt cap | `minigame_effects.py:187` | 100 ms (anti-spike) | P2 |
| 261 | mg-vfx | Particle dt formula | `minigame_effects.py:213-222` | linear physics + life | P2 |
| 262 | mg-vfx | ParticleSystem default max | `minigame_effects.py:241` | 200 | P2 |
| 263 | mg-vfx | SparkParticle speed range | `minigame_effects.py:286` | uniform(50,200)*intensity | P2 |
| 264 | mg-vfx | SparkParticle life | `minigame_effects.py:291` | uniform(0.3,0.8) s | P2 |
| 265 | mg-vfx | SparkParticle gravity/drag | `minigame_effects.py:299-300` | 200 / 2.0 | P2 |
| 266 | mg-vfx | Spark trail length | `minigame_effects.py:308` | 3 segments | P2 |
| 267 | mg-vfx | EmberParticle life | `minigame_effects.py:336` | uniform(1.5,3.0) s | P2 |
| 268 | mg-vfx | EmberParticle gravity | `minigame_effects.py:340` | -10 (float up) | P2 |
| 269 | mg-vfx | Ember flicker speed | `minigame_effects.py:344` | uniform(5,15) | P2 |
| 270 | mg-vfx | BubbleParticle size range | `minigame_effects.py:377` | uniform(4,15) | P2 |
| 271 | mg-vfx | BubbleParticle life | `minigame_effects.py:383` | uniform(1.0,2.5) s | P2 |
| 272 | mg-vfx | Bubble wobble speed | `minigame_effects.py:391` | uniform(3,8) | P2 |
| 273 | mg-vfx | SteamParticle size range | `minigame_effects.py:430` | uniform(15,30) | P2 |
| 274 | mg-vfx | Steam expansion rate | `minigame_effects.py:435` | uniform(5,15) | P2 |
| 275 | mg-vfx | SpiritParticle life | `minigame_effects.py:466` | uniform(3.0,6.0) s | P2 |
| 276 | mg-vfx | SpiritParticle drift speed | `minigame_effects.py:484-485` | sin/cos(drift)*30/*20 | P2 |
| 277 | mg-vfx | GearToothParticle gravity | `minigame_effects.py:541` | 400 | P2 |
| 278 | mg-vfx | ScreenShake default intensity | `minigame_effects.py:565` | 5 | P2 |
| 279 | mg-vfx | ScreenShake default duration | `minigame_effects.py:565` | 200 ms | P2 |
| 280 | mg-vfx | GlowEffect default radius | `minigame_effects.py:601` | 20 | P2 |
| 281 | mg-vfx | GlowEffect pulse amount | `minigame_effects.py:601` | 5 | P2 |
| 282 | mg-vfx | GlowEffect pulse speed | `minigame_effects.py:601` | 3.0 | P2 |
| 283 | mg-vfx | FlameEffect default flame count | `minigame_effects.py:629` | 8 | P2 |
| 284 | mg-vfx | FlameEffect height range | `minigame_effects.py:649` | uniform(30,60) | P2 |
| 285 | mg-vfx | RotatingGear default speed | `minigame_effects.py:693` | 30 deg/s | P2 |
| 286 | mg-vfx | RotatingGear inner ring ratio | `minigame_effects.py:713` | 0.6 | P2 |
| 287 | mg-vfx | RotatingGear tooth ratio | `minigame_effects.py:718` | 0.25 | P2 |
| 288 | mg-vfx | AnimatedProgressBar anim speed | `minigame_effects.py:763` | 5.0 | P2 |
| 289 | mg-vfx | AnimatedProgressBar glow fade | `minigame_effects.py:777` | -2/s | P2 |
| 290 | mg-vfx | AnimatedButton hover scale | `minigame_effects.py:838` | 1.02 | P2 |
| 291 | mg-vfx | AnimatedButton press scale | `minigame_effects.py:832` | 0.95 | P2 |
| 292 | mg-vfx | AnimatedButton color lerp | `minigame_effects.py:849` | 8*dt | P2 |
| 293 | mg-vfx | MetadataOverlay duration | `minigame_effects.py:888` | 8.0 s | P1 |
| 294 | mg-vfx | MetadataOverlay fade duration | `minigame_effects.py:894` | 0.5 s | P2 |
| 295 | mg-vfx | MetadataOverlay min display | `minigame_effects.py:895` | 0.5 s | P2 |
| 296 | mg-vfx | MetadataOverlay panel size | `minigame_effects.py:944-945` | 350×200 | P2 |
| 297 | mg-vfx | MetadataOverlay tier colors | `minigame_effects.py:963-969` | per-rarity dict | P1 |
| 298 | mg-vfx | Background overlay alpha | `minigame_effects.py:1033` | 180 | P2 |
| 299 | mg-vfx | Background image lookup | `minigame_effects.py:23` | `assets/minigame_backgrounds/{disc}_bg.{png\|jpg\|jpeg}` | P0 |
| 300 | mg-vfx | SmithingBg flame count | `minigame_effects.py:1084` | 12 | P2 |
| 301 | mg-vfx | SmithingBg ember pool | `minigame_effects.py:1089` | 50 | P2 |
| 302 | mg-vfx | SmithingBg ember rate | `minigame_effects.py:1097` | every 0.1 s | P2 |
| 303 | mg-vfx | RefiningBg gear set | `minigame_effects.py:1132-1141` | 4 gears | P2 |
| 304 | mg-vfx | RefiningBg flame count | `minigame_effects.py:1144` | 10 | P2 |
| 305 | mg-vfx | RefiningBg molten glow radius | `minigame_effects.py:1149` | 150 | P2 |
| 306 | mg-vfx | AlchemyBg bubble pool | `minigame_effects.py:1185` | 30 | P2 |
| 307 | mg-vfx | AlchemyBg steam pool | `minigame_effects.py:1186` | 20 | P2 |
| 308 | mg-vfx | Cauldron size | `minigame_effects.py:1189-1190` | 160×120 | P2 |
| 309 | mg-vfx | EngineeringBg light flicker rate | `minigame_effects.py:1291` | *5 | P2 |
| 310 | mg-vfx | EnchantingBg spirit pool | `minigame_effects.py:1346` | 40 | P2 |
| 311 | mg-vfx | EnchantingBg aura radius | `minigame_effects.py:1380` | 200 | P2 |
| 312 | mg-vfx | Active discipline ParticleSystem max | `minigame_effects.py:1438` | 150 | P2 |

### visual_effect_bridge.py — event→VFX mapping

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 313 | bridge | Kill shake by tier | `visual_effect_bridge.py:29` | {1:2, 2:3, 3:5, 4:8} | P1 |
| 314 | bridge | Death effect color by tier | `visual_effect_bridge.py:32-37` | T1 red, T2 orange, T3 purple, T4 bright red | P1 |
| 315 | bridge | Hit spark intensity formula | `visual_effect_bridge.py:108` | `min(amount/50, 3.0)` | P2 |
| 316 | bridge | Crit hit pause duration | `visual_effect_bridge.py:113` | 40 ms (currently no-op in ScreenEffects) | P2 |
| 317 | bridge | Enemy kill screen shake duration | `visual_effect_bridge.py:131` | 150 ms | P2 |
| 318 | bridge | Enemy kill hit pause | `visual_effect_bridge.py:135` | 60 ms (no-op) | P2 |
| 319 | bridge | Player hit shake formula | `visual_effect_bridge.py:157` | `min(amount/10+1, 8)` | P1 |
| 320 | bridge | Player hit shake duration | `visual_effect_bridge.py:158` | 100 ms | P2 |

### Renderer.py — embedded color/font/layout constants (Python; not JSON)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 321 | fonts | Main font size | `renderer.py:53` | `scale(24)` | P1 |
| 322 | fonts | Small font size | `renderer.py:54` | `scale(18)` | P1 |
| 323 | fonts | Tiny font size | `renderer.py:55` | `scale(14)` | P1 |
| 324 | fonts | Font family | `renderer.py:53-55` | `None` (pygame default) | P2 |
| 325 | smith | Tier→grid size (smithing) | `renderer.py:69-74` | T1=3×3 T2=5×5 T3=7×7 T4=9×9 | P0 |
| 326 | smith | Recipe placement bg colors | `renderer.py:196-199` | green/gold tint | P2 |
| 327 | enemy | Enemy attack-anim element colors `_ETAG_COLORS` | `renderer.py:1347-1353` | 9 entries (duplicates ELEMENT_COLORS) | P1 |
| 328 | enemy | Enemy state colors `_STATE_COLORS` | `renderer.py:1362-1367` | 8 states (duplicates visual-config.JSON) | P2 |
| 329 | enemy | Tier→enemy fallback color | `renderer.py:1377` | T1:(200,100,100) T2:(255,150,0) T3:(200,100,255) T4:(255,50,50) (duplicates bridge) | P1 |
| 330 | enemy | Boss enemy color override | `renderer.py:1380` | (255,215,0) | P1 |
| 331 | combat | Player attack tag colors `_ELEMENT_COLORS` | `renderer.py:1811-1820` | 9 entries (third duplicate) | P1 |
| 332 | HP-bar | Body health bar size | `renderer.py:3145` | 300×25 | P1 |
| 333 | MP-bar | Body mana bar size | `renderer.py:3159` | 300×20 | P1 |
| 334 | MP-bar | Mana fill color | `renderer.py:3162` | (50,150,255) | P2 |
| 335 | buffs | Buff bar width | `renderer.py:3190` | 300 | P2 |
| 336 | buffs | Buff bar height | `renderer.py:3191` | 18 | P2 |
| 337 | buffs | Buff bar bg | `renderer.py:3192` | (40,40,50) | P2 |
| 338 | buffs | Buff color: combat | `renderer.py:3187` | (100,255,100) | P2 |
| 339 | buffs | Buff color: other | `renderer.py:3187` | (100,200,255) | P2 |
| 340 | hotbar | Skill hotbar slot size | `renderer.py:3213` | 60 | P1 |
| 341 | hotbar | Skill hotbar spacing | `renderer.py:3214` | 10 | P2 |
| 342 | hotbar | Skill hotbar num slots | `renderer.py:3215` | 5 | P0 |
| 343 | hotbar | Skill hotbar bottom margin | `renderer.py:3220` | 20 px from bottom | P2 |
| 344 | hotbar | Slot bg color | `renderer.py:3232` | (30,30,40) | P2 |
| 345 | hotbar | Slot border color | `renderer.py:3233` | (100,100,120) | P2 |
| 346 | hotbar | Mana cost color (have) | `renderer.py:3287` | (100,200,255) | P2 |
| 347 | hotbar | Mana cost color (lack) | `renderer.py:3287` | (255,100,100) | P2 |
| 348 | hotbar | Cooldown overlay alpha | `renderer.py:3277` | 180 | P2 |
| 349 | skill-tooltip | Skill tooltip size | `renderer.py:3305-3306` | 350×200 | P2 |
| 350 | skill-tooltip | Tier colors | `renderer.py:3331` | T1 grey, T2 green, T3 magenta, T4 gold | P2 |
| 351 | map | Geo-map window size | `renderer.py:3696-3697` | scale(1200) × scale(900), clamped to viewport | P1 |
| 352 | map | Non-geo map window size | `renderer.py:3699` | from `map_window_size` JSON | P1 |
| 353 | map | Map background tint | `renderer.py:3730` | (15,15,25) | P2 |
| 354 | map | Map upscale max dim | `renderer.py:3787` | 4096 | P2 |
| 355 | map | Nation border draw threshold | `renderer.py:3817` | `_effective_csf >= 1.5` | P2 |
| 356 | map | Region border threshold | `renderer.py:3838` | 2.0 | P2 |
| 357 | map | Province border threshold | `renderer.py:3844` | 5.0 | P2 |
| 358 | map | Nation border color | `renderer.py:3833,3836` | (200,185,140) | P2 |
| 359 | map | Region border color | `renderer.py:3840` | (150,150,165) | P2 |
| 360 | map | Province border color | `renderer.py:3846,3848` | (110,110,125) | P2 |
| 361 | chunk-info | Danger-level color: peaceful | `renderer.py:3037` | (100,200,100) | P2 |
| 362 | chunk-info | Danger-level color: dangerous | `renderer.py:3038` | (255,165,0) | P2 |
| 363 | chunk-info | Danger-level color: rare | `renderer.py:3039` | (180,100,255) | P2 |
| 364 | chunk-info | Danger-level color: water | `renderer.py:3040` | (100,180,255) | P2 |
| 365 | notif | Notification fade-in formula | `renderer.py:4895` | `min(1, lifetime/3.0)` | P2 |
| 366 | notif | Notification top margin | `renderer.py:4893` | y=50 | P2 |
| 367 | notif | Notification bg padding | `renderer.py:4900-4901` | 20×10, alpha ramp 180 | P2 |
| 368 | notif | Notification spacing | `renderer.py:4905` | height + 15 | P2 |
| 369 | debug | Debug msg position | `renderer.py:4920-4921` | x=10, y=VH-120 | P2 |
| 370 | debug | Debug msg color | `renderer.py:4926` | (200,200,255) | P2 |
| 371 | debug | Debug msg bg alpha | `renderer.py:4930` | 150 | P2 |
| 372 | debug | Debug msg line height | `renderer.py:4931-4934` | 22 px | P2 |
| 373 | enc | Encyclopedia tier colors | `renderer.py:4779-4790` | header gold, discipline blue, tier 1-4 grades | P2 |
| 374 | equip | Equipment window placement | `renderer.py:6683-6685` | LARGE×MEDIUM, right-aligned -20 from viewport, top 50 | P1 |
| 375 | equip | Equipment slot size | `renderer.py:6694` | scale(80) | P1 |
| 376 | equip | Equipment horizontal offset | `renderer.py:6697` | scale(110) | P2 |
| 377 | equip | Equipment slot layout | `renderer.py:6698-6707` | dict (helmet/mainHand/chestplate/offHand/gauntlets/leggings/boots/accessory positions) | P0 |
| 378 | equip | Equipment stats panel position | `renderer.py:6768-6769` | scale(20), scale(470) | P2 |
| 379 | tooltip | Default tooltip text color | `renderer.py:7511` | (255,255,255) | P2 |
| 380 | tooltip | Tooltip padding | `renderer.py:7512` | 8 | P2 |
| 381 | tooltip | Tooltip offsets from mouse | `renderer.py:7497` | offset_x=15, offset_y=15 | P2 |
| 382 | tooltip | Tooltip bg color | `renderer.py:7531` | (20,20,20,230) | P2 |
| 383 | tooltip | Tooltip border color | `renderer.py:7532` | (200,200,100) | P2 |
| 384 | class-sel | Class tooltip width | `renderer.py:7070` | scale(320) | P2 |
| 385 | class-sel | Class card height | `renderer.py:7325` | scale(90) | P2 |
| 386 | class-sel | Class card columns | `renderer.py:7324` | 2 | P2 |
| 387 | startmenu | Start menu width | `renderer.py:7220` | MENU_SMALL_W | P2 |
| 388 | startmenu | Start menu height | `renderer.py:7221` | scale(650) | P2 |
| 389 | startmenu | Start menu button h | `renderer.py:7250` | scale(75) | P2 |
| 390 | startmenu | Start menu button spacing | `renderer.py:7251` | scale(15) | P2 |
| 391 | startmenu | Title color | `renderer.py:7231` | (255,215,0) | P2 |
| 392 | startmenu | Button hover bg | `renderer.py:7263-7264` | (80,100,140) / border (150,180,220) | P2 |
| 393 | startmenu | Button selected bg | `renderer.py:7265-7267` | (60,80,120) | P2 |
| 394 | startmenu | Button idle bg | `renderer.py:7268-7270` | (40,50,70) | P2 |
| 395 | npc-dialog | NPC dialogue window size | `renderer.py:4137` | MENU_MEDIUM_W × MENU_MEDIUM_H | P1 |
| 396 | npc-dialog | NPC name color | `renderer.py:4151` | (255,215,0) | P2 |
| 397 | npc-dialog | NPC header height | `renderer.py:4147` | scale(50) | P2 |
| 398 | npc-dialog | Dialogue line spacing | `renderer.py:4163` | scale(25) | P2 |
| 399 | npc-dialog | Max quests shown | `renderer.py:4203` | 3 | P2 |
| 400 | npc-dialog | Quest button accept color | `renderer.py:4186` | (60,120,60)/hover (40,100,40) | P2 |
| 401 | enchant-UI | Enchantment selection window | `renderer.py:7143` | 600×500 (NOT scaled!) | P1 |
| 402 | enchant-UI | Enchantment slot size | `renderer.py:7162` | 60 (not scaled) | P2 |

### Terrain renderer (rendering/terrain_renderer.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 403 | terrain | Tile palette GRASS | `terrain_renderer.py:72-79` | 5 colors + variance 8 | P1 |
| 404 | terrain | Tile palette STONE | `terrain_renderer.py:80-87` | 5 colors + variance 6 | P1 |
| 405 | terrain | Tile palette WATER | `terrain_renderer.py:88-95` | 5 colors + variance 5 | P1 |
| 406 | terrain | Tile palette DIRT | `terrain_renderer.py:96-103` | 5 colors + variance 7 | P1 |
| 407 | terrain | Surface cache max | `terrain_renderer.py:171` | `_CACHE_MAX=4096` | P2 |
| 408 | terrain | Cache eviction batch | `terrain_renderer.py:197-199` | `_CACHE_MAX//4` | P2 |
| 409 | terrain | Detail enabled threshold | `terrain_renderer.py:208` | tile_size ≥ 16 | P2 |
| 410 | terrain | Edge dithering enabled threshold | `terrain_renderer.py:213` | tile_size ≥ 8 | P2 |
| 411 | terrain | Grass FBM scales | `terrain_renderer.py:118,121` | 0.12 (large), 0.33 (medium) | P2 |
| 412 | terrain | Edge dither depth | `terrain_renderer.py:290` | tile_size/4 | P2 |
| 413 | terrain | Grass blade colors | `terrain_renderer.py:232,238` | (60,155,50) / (28,85,30) | P2 |
| 414 | terrain | Stone speck colors | `terrain_renderer.py:249,252-255` | (155,150,140) / (70,68,65) | P2 |
| 415 | terrain | Water highlight | `terrain_renderer.py:263` | (75,155,210) | P2 |
| 416 | terrain | Dirt pebble colors | `terrain_renderer.py:276,279` | (155,130,95) / (72,50,32) | P2 |

### Map cache (rendering/map_cache.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 417 | mapcache | Pixels per chunk | `map_cache.py:52` | `ppc=4` | P1 |
| 418 | mapcache | Background fill | `map_cache.py:55` | (20,22,30) | P2 |
| 419 | mapcache | Nation tint blend | `map_cache.py:65-69` | 75% biome + 25% nation | P1 |
| 420 | mapcache | Blur radius | `map_cache.py:76` | 3 | P2 |
| 421 | mapcache | Nation border color | `map_cache.py:79` | (200,185,140) | P2 |
| 422 | mapcache | Nation border thickness | `map_cache.py:85,91` | 2 | P2 |
| 423 | mapcache | Region border color | `map_cache.py:100,106` | (120,120,135) | P2 |
| 424 | mapcache | Region border thickness | `map_cache.py:100,106` | 1 | P2 |

### Image cache (rendering/image_cache.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 425 | asset | Default target_size | `image_cache.py:30` | (50,50) | P2 |
| 426 | asset | Direct-asset path prefixes | `image_cache.py:59` | enemies/, resources/, skills/, titles/, npcs/, quests/, classes/ | P1 |
| 427 | asset | Item path prefix | `image_cache.py:63-64` | `items/` | P2 |

### Visual_effects.py — player/enemy enhancements

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 428 | dmg# | Crit Y velocity multiplier | `visual_effects.py:85` | 1.4 | P2 |
| 429 | dmg# | Crit horizontal damp | `visual_effects.py:86` | 0.5 | P2 |
| 430 | dmg# | Fade phase start | `visual_effects.py:105` | last 30% (0.7→1.0) | P2 |
| 431 | dmg# | Anti-stack window | `visual_effects.py:172` | 300 ms | P2 |
| 432 | player | Shield pulse frequency | `visual_effects.py:256` | time*6 (≈ ~1Hz) | P2 |
| 433 | player | Shield pulse base alpha | `visual_effects.py:258` | 120*pulse | P2 |
| 434 | player | Shield outline thickness | `visual_effects.py:258` | 3 | P2 |
| 435 | death | Death surface grey formula | `visual_effects.py:349` | half-color w/ floor 40 | P2 |

### Combat / Player Actions (hardcoded; not in JSON)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 436 | dodge | Dodge duration | `Combat/player_actions.py:74` | 250 ms | P0 |
| 437 | dodge | Dodge speed multiplier | `Combat/player_actions.py:75` | 3.0 | P0 |
| 438 | dodge | Dodge cooldown | `Combat/player_actions.py:76` | 800 ms | P0 |
| 439 | dodge | I-frame duration | `Combat/player_actions.py:77` | 200 ms | P0 |
| 440 | input | Input buffer window | `Combat/player_actions.py:24` | 200 ms | P1 |
| 441 | dodge | Facing→angle map | `Combat/player_actions.py:13-18` | right=0, down=90, left=180, up=270 | P2 |
| 442 | screen | Afterimage life | `Combat/screen_effects.py:53` | 300 ms | P2 |
| 443 | screen | Afterimage default alpha | `Combat/screen_effects.py:44` | 180 | P2 |
| 444 | screen | Afterimage default color | `Combat/screen_effects.py:46` | (150,200,255) | P2 |
| 445 | screen | Hit-pause behavior | `Combat/screen_effects.py:34-36` | NO-OP (by design — time always constant) | P2 |
| 446 | dodge-dust | Afterimage emit cadence | `core/game_engine.py:3105` | every dodge_dur/6 | P2 |
| 447 | dodge-dust | Initial dust emit window | `core/game_engine.py:3112` | first 30 ms | P2 |

### F12 observability overlay (world_system/wes/observability_overlay.py)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 448 | F12 | Overlay font size | `core/game_engine.py:8236` | 16 (`pygame.font.Font(None, 16)`) | P2 |
| 449 | F12 | Default x | `observability_overlay.py:64` | 8 | P2 |
| 450 | F12 | Default y | `observability_overlay.py:65` | 8 | P2 |
| 451 | F12 | Default width | `observability_overlay.py:66` | 600 | P2 |
| 452 | F12 | Max events shown | `observability_overlay.py:67` | 15 | P2 |
| 453 | F12 | Background color | `observability_overlay.py:56` | (10,10,16) | P2 |
| 454 | F12 | Background alpha | `observability_overlay.py:57` | 210 | P2 |
| 455 | F12 | Header color | `observability_overlay.py:55` | (250,220,120) | P2 |
| 456 | F12 | Event type → color map | `observability_overlay.py:41-52` | 10 entries | P2 |
| 457 | F12 | Default text color | `observability_overlay.py:54` | (180,180,180) | P2 |
| 458 | F12 | Field len cutoff | `observability_overlay.py:164` | 40 chars | P2 |

### map-waypoint-config.JSON

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 459 | map | Default zoom | `map_display.default_zoom` | 0.5 | P1 |
| 460 | map | Min zoom | `…min_zoom` | 0.08 | P2 |
| 461 | map | Max zoom | `…max_zoom` | 4.0 | P2 |
| 462 | map | Zoom step | `…zoom_step` | 0.25 | P2 |
| 463 | map | Chunk render size base px | `…chunk_render_size` | 12 | P1 |
| 464 | map | Show grid | `…show_grid` | true | P2 |
| 465 | map | Show coordinates | `…show_coordinates` | true | P2 |
| 466 | map | Show player marker | `…show_player_marker` | true | P2 |
| 467 | map | Show waypoint markers | `…show_waypoint_markers` | true | P2 |
| 468 | map | Center on player | `…center_on_player` | true | P2 |
| 469 | map | Biome colors (15 entries) | `biome_colors.*` | forest/cave/quarry/water/etc | P1 |
| 470 | map | Player marker color | `marker_icons.player.color` | (255,255,255) | P2 |
| 471 | map | Player marker size | `…player.size` | 8 | P2 |
| 472 | map | Player marker shape | `…player.shape` | "triangle" (enum: triangle/circle/diamond) | P2 |
| 473 | map | Waypoint marker color | `…waypoint.color` | (255,215,0) | P2 |
| 474 | map | Waypoint marker size | `…waypoint.size` | 10 | P2 |
| 475 | map | Waypoint marker shape | `…waypoint.shape` | "diamond" | P2 |
| 476 | map | Waypoint label visible | `…waypoint.show_label` | true | P2 |
| 477 | map | Dungeon marker color | `…dungeon.color` | (220,20,60) | P2 |
| 478 | waypoint | Unlock levels | `waypoint_system.unlock_schedule.levels` | [5,10,15,20,25,30] | P0 |
| 479 | waypoint | Max waypoints | `…max_waypoints` | 7 | P0 |
| 480 | waypoint | Teleport cooldown (s) | `…teleport_cooldown` | 30.0 | P0 |
| 481 | waypoint | Teleport cost enabled | `…teleport_cost.enabled` | false | P2 |
| 482 | waypoint | Teleport mana cost | `…teleport_cost.mana_cost` | 50 | P2 |
| 483 | waypoint | Min distance between waypoints | `…placement_rules.min_distance_between_waypoints` | 32 tiles | P2 |
| 484 | waypoint | Blocked in dungeons | `…blocked_in_dungeons` | true | P2 |
| 485 | waypoint | Blocked in combat | `…blocked_in_combat` | true | P2 |
| 486 | waypoint | Name max length | `…max_name_length` | 24 | P2 |
| 487 | waypoint | Allow emoji in names | `…allow_emoji` | false | P2 |
| 488 | map-UI | Map window size | `ui_settings.map_window_size` | [700,600] | P1 |
| 489 | map-UI | Waypoint panel width | `…waypoint_panel_width` | 200 | P2 |
| 490 | map-UI | Background color | `…background_color` | [20,20,30,240] | P2 |
| 491 | map-UI | Border color | `…border_color` | [100,100,120] | P2 |
| 492 | map-UI | Font color | `…font_color` | [220,220,220] | P2 |
| 493 | bind | Open map key | `keybindings.open_map` | "M" *(string only, not enforced as remap)* | P2 |
| 494 | bind | Place waypoint key | `…place_waypoint` | "W" *(declared "W" but actually handled as "P" in game_engine line 820)* | P1 |
| 495 | bind | Center on player | `…center_on_player` | "C" *(string only)* | P2 |
| 496 | bind | Zoom in / out | `…zoom_in / zoom_out` | "PLUS"/"MINUS" *(not actually hooked — scroll wheel is)* | P2 |

### combat-config.JSON (subset relevant to spawn / camera / safe zone)

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 497 | combat | Safe zone radius | `safeZone.radius` | 30 | P0 |
| 498 | combat | Crit multiplier | `damageFormulas.critMultiplier` | 2.0 | P0 |
| 499 | combat | Shield max reduction | `shieldMechanics.maxDamageReduction` | 0.75 | P0 |
| 500 | combat | Combat timeout (s) | `combatMechanics.combatTimeout` | 5.0 | P1 |

### Keybindings (game_engine.py — all hardcoded)

| # | Domain | Key | Path | Action | Priority |
|---|---|---|---|---|---|
| 501 | bind | W/A/S/D | `game_engine.py:850-856,7986-7992` | Move | P0 |
| 502 | bind | TAB | `game_engine.py:767` | Switch tool | P1 |
| 503 | bind | C | `game_engine.py:771` | Toggle stats UI | P1 |
| 504 | bind | E | `game_engine.py:780` | Toggle equipment UI | P1 |
| 505 | bind | K | `game_engine.py:789` | Toggle skills menu | P1 |
| 506 | bind | L | `game_engine.py:798` | Toggle encyclopedia | P2 |
| 507 | bind | M | `game_engine.py:807` | Toggle world map | P1 |
| 508 | bind | P | `game_engine.py:820` | Place waypoint (when map open) | P1 |
| 509 | bind | F | `game_engine.py:824` | NPC interact / dungeon double-tap exit | P0 |
| 510 | bind | Q | `game_engine.py:838` | Drop item (Shift+Q = stack) | P1 |
| 511 | bind | SPACE | `game_engine.py:843` | Dodge roll | P0 |
| 512 | bind | 1-5 | `game_engine.py:883-923` | Skill hotbar slots | P0 |
| 513 | bind | ESC | `game_engine.py:711` | Close current menu / quit | P0 |
| 514 | bind | RETURN | `game_engine.py:680,692` | Confirm in input dialogs | P1 |
| 515 | bind | UP/DOWN | `game_engine.py:599-601` | Menu navigation | P1 |
| 516 | bind | F1 | `game_engine.py:924` | Debug: infinite resources + maxed level/stats | P1 |
| 517 | bind | F2 | `game_engine.py:957` | Debug: learn all skills | P2 |
| 518 | bind | F3 | `game_engine.py:997` | Debug: grant all titles | P2 |
| 519 | bind | F4 | `game_engine.py:1030` | Debug (need to inspect further — implied: max stats) | P2 |
| 520 | bind | F5 | `game_engine.py:1080` | Toggle keep inventory on death | P2 |
| 521 | bind | F6 | `game_engine.py:1094` | Quick timestamped save | P2 |
| 522 | bind | F7 | `game_engine.py:1113` | Toggle infinite durability | P2 |
| 523 | bind | F8 | `game_engine.py:1127` | Enter/exit dungeon (Shift+F8 = biome debug print) | P1 |
| 524 | bind | F9 | `game_engine.py:1139` | Load autosave (Shift+F9 = default save) | P1 |
| 525 | bind | F10 | `game_engine.py:1196` | Run automated test suite | P2 |
| 526 | bind | F11 | `game_engine.py:1202` | Toggle fullscreen | P0 |
| 527 | bind | F12 | `game_engine.py:1211` | Toggle WES observability overlay | P1 |
| 528 | bind | X | `game_engine.py:7352,8024,8035` | Block (held) — shield/parry | P0 |
| 529 | bind | SPACE (smithing minigame) | `game_engine.py:633` | Strike anvil | P1 |
| 530 | bind | C (smithing minigame) | `game_engine.py:636` | Cool/quench? (in-context) | P2 |
| 531 | bind | S (smithing minigame) | `game_engine.py:638` | (in-context) | P2 |
| 532 | bind | SPACE (refining minigame) | `game_engine.py:640` | (in-context) | P2 |
| 533 | bind | LSHIFT/RSHIFT | `game_engine.py:1128, 1141, 7854, …` | Modifier for F8/F9/Q | P1 |
| 534 | bind | MOUSEWHEEL | `game_engine.py:1249` | Map zoom / recipe scroll / etc | P1 |
| 535 | bind | Left-click | global | Attack / harvest / UI interaction | P0 |
| 536 | bind | Right-click | hotbar @ `game_engine.py:2698` | Unequip skill from hotbar | P2 |

### Animation/InputBuffer / Engine timing

| # | Domain | Control | Path | Current | Priority |
|---|---|---|---|---|---|
| 537 | engine | Main loop FPS cap | `core/game_engine.py:98 + clock.tick(FPS)` | 60 | P0 |
| 538 | engine | dt computation source | `core/game_engine.py:3079` | dt_ms = dt*1000 | P2 |
| 539 | engine | Wallclock max delta (engine-side) | Not enforced at engine; minigame_effects.py:187 caps at 100ms | 100 ms | P2 |
| 540 | engine | Debug message max | `core/debug_display.py:27` | 5 | P2 |
| 541 | engine | Notification default lifetime | `core/notifications.py:12` | 3.0 s | P1 |
| 542 | engine | Notification default color | `core/notifications.py:13` | Config.COLOR_NOTIFICATION (255,215,0) | P2 |

### Health / Mana bar rendering on body (over-world)

(See enemy-vfx section above; player HP/MP bar in UI panel uses 300×25 and 300×20 — items #332-333.)

---

## Notable observations

1. **Triple-duplication of element→color mapping.** `_ETAG_COLORS` (renderer.py:1347), `_ELEMENT_COLORS` (renderer.py:1811), `ELEMENT_COLORS` (animation/weapon_visuals.py:18), plus `damageNumbers.typeColors` (visual-config.JSON), plus `DAMAGE_SPARK_COLORS` (combat_particles.py:22). Five separate sources of truth for "fire is orange". Changing one will not change the others; recommend consolidating to `visual-config.JSON`.

2. **Triple-duplication of enemy tier color.** `_TIER_COLORS` (visual_effect_bridge.py:32), `tier_colors` dict (renderer.py:1377), and boss override at renderer.py:1380. Tuning kill burst color vs body color requires editing both.

3. **Triple-duplication of state colors.** `_STATE_COLORS` (renderer.py:1362) duplicates `enemyVisuals.stateIndicatorColors` (visual-config.JSON). Visual-config wins via VisualConfig but only if read; renderer.py uses its own hardcoded dict directly.

4. **Hit-pause is a designed no-op.** `Combat/screen_effects.py:35` explicitly states "Time is always constant — freeze frames removed by design." But `visual_effect_bridge.py:113,135` still calls `hit_pause(40)` / `hit_pause(60)`, and `visual-config.JSON` exposes `hitPauseEnabled` / `slowMotionEnabled`. The flags and calls are dead code. P2 cleanup or rewire.

5. **Tooltip z-order bug (mentioned in CLAUDE.md).** Renderer uses `self.pending_tooltip` / `self.pending_class_tooltip` / `self.pending_tool_tooltip` for deferred rendering. The pending field is set in render_equipment_ui (line 6800), but I don't see where it's actually consumed and drawn afterwards. The pattern *intends* to defer, but if the deferred draw happens before chest/death/spawn chest UIs, those will cover the tooltip. **Confirmed mechanism: deferred tooltip rects are set but not necessarily drawn LAST.** Worth tracing how `pending_tooltip` is flushed to confirm fix path.

6. **Enchantment selection UI is NOT scaled.** `renderer.py:7143` uses raw `ww, wh = 600, 500` instead of `Config.scale(…)`. At high-DPI / 4K it will appear tiny. P1.

7. **Inventory slot spacing duplicated.** `Config.INVENTORY_SLOT_SIZE` lives in config.py, but the spacing constant `10` is hardcoded in 4 separate places (renderer.py:5063, game_engine.py:1401, 2203, 6903) with the comment "Must match renderer spacing". Tuning one without the others breaks click-targeting. P1 cleanup.

8. **No audio system.** No `pygame.mixer` initialization, no sound files, no music params, no UI sounds, no audio config JSON. Audio is entirely unimplemented; designer cannot tune anything audio. (Only `pygame.font` is initialized.)

9. **No "tile rendering distance" param.** The render loop iterates loaded chunks; visibility is determined by `Config.CHUNK_LOAD_RADIUS=4` only. No separate "fog of war" or "draw distance" setting beyond chunk culling.

10. **Map_waypoint_config keybindings are decorative.** The JSON declares `open_map: "M"`, `place_waypoint: "W"`, `zoom_in: "PLUS"`, but game_engine.py:807,820,1249 hardcodes `K_m`, `K_p`, and MOUSEWHEEL. The JSON values are inspected but not actually used to drive binding. **`place_waypoint` JSON says "W" but in code the key is "P" (line 820)** — bug or stale config.

11. **Procedural animation defaults are not in JSON.** All numbers in `animation/procedural.py` are Python function defaults (arc_degrees, radius_px, duration_ms, etc.). To tune them, designer must edit Python or override at registration. There's no `animation-config.json`.

12. **Per-skill VFX cannot be tuned per skill.** Element color comes from the skill's first matching element tag (renderer.py:1822-1828; weapon_visuals.py:108-112). There is **no per-skill override** for particle count, lifetime, spread, etc. — those come from VisualConfig globals.

13. **Minigame backgrounds are file-path-driven.** `core/minigame_effects.py:23-41` looks up `assets/minigame_backgrounds/{discipline}_bg.{png|jpg|jpeg}` at runtime. Currently 5 JPGs exist (alchemy, enchanting, engineering, refining, smithing). Replacing a JPG hot-swaps the background. Smithing has no PNG/JPG match path fallback — designer should know.

14. **`renderer.py:7220-7222` start_menu uses `MENU_SMALL_W` but custom `wh = s(650)`** — inconsistent with other menus that use full preset W×H. Minor.

15. **`enemy_color` for boss is overridden in code at renderer.py:1380** to (255,215,0), bypassing whatever `bossGlowColor` in visual-config.JSON says (which is also (255,215,0), so coincident, but **the JSON value isn't actually read here**). P2.

16. **Dodge tuning is fully Python-side.** All dodge values (duration, speed, cooldown, iframe) in `Combat/player_actions.py:74-77` are hardcoded with the comment "can be tuned via config/JSON" but no JSON is actually wired. Designer must edit Python. P0.

17. **`pulseFrequency: 10.0`** in visual-config.JSON has unclear units — looks like radians/sec or Hz multiplier. Worth annotating.

18. **`shrinkRate: 0.997`** is per-frame at 60fps, with `dt_norm = dt_ms / 16.67` in code. So one frame = 0.3% shrink. Total shrink across 1200ms lifetime ≈ 20%. Easy to mis-tune to invisibility.

19. **Renderer reads its main fonts only once at __init__.** Changing `Config.UI_SCALE` post-init via F11 fullscreen toggle doesn't refresh `self.font / self.small_font / self.tiny_font` in Renderer — only the screen + camera get updated (`core/game_engine.py:1206`). Possible bug for F11 dynamic scaling.

20. **The `core/config.py:191` constant `COLOR_EQUIPPED = (255, 215, 0)` is gold border for equipped items** — same gold as title color and player marker. Designer should know these are not isolated.

---

## Open questions for the user

1. **Audio scope.** Is audio actually planned, or is it permanently absent? If it's planned, almost nothing is tunable yet — entire system would need to be built.

2. **Per-skill VFX overrides.** Should each skill JSON be able to declare its own `vfx_color`, `particle_count`, `screen_shake_intensity`, or is "skill inherits from element tag" intentional? Currently the latter.

3. **Should `weapon_visuals.py` (ELEMENT_COLORS, weapon profiles, tier intensity) be migrated to JSON?** It's the "weapon feel" tuning table and is currently Python-only. Big designer win if JSON-ized.

4. **Dodge tuning JSON location.** Where does dodge live? `Combat/player_actions.py:73` says "can be tuned via config/JSON" but there's no wire. Should this go in `visual-config.JSON` (it's gameplay+visual), `combat-config.JSON`, or a new file?

5. **Tooltip z-order bug fix.** Is the intent that the `pending_tooltip` field is flushed at the very end of frame? I see it set but not the flush path. Worth confirming with the user.

6. **Map waypoint keybinding JSON.** Should it actually drive bindings (right now ignored), or is it documentation only? If documentation, the JSON disagrees with code on the "place_waypoint" key (W in JSON, P in code).

7. **Minigame background extensions.** Currently `core/minigame_effects.py:36` checks .png / .jpg / .jpeg. Should .webp / .avif be supported, or is JPG/PNG fine?

8. **Triple-coloring cleanup priority.** Is the 5-source duplication of "fire = orange" (visual-config + 3 renderer dicts + weapon_visuals + combat_particles) a problem to fix now, or accept as tech debt?

9. **InventorySlot spacing constant.** Should `INVENTORY_SLOT_SPACING` be added to Config (currently hardcoded `10` in 4 places)?

10. **Inventory slot count.** Currently auto-computed from screen width (config.py:108). Is that fine, or should designer be able to pin "always 10 per row"?

11. **F4 binding** — I noted it's hardcoded at game_engine.py:1030 but did not read its body. Most likely max-level/stats given the F1-F4 cluster, but worth confirming.

12. **Status effect visualizers** (burn icon, freeze tint) — I found no per-status visual config. Are burn/freeze visuals just inherited from element colors? Where would designer tune the freeze-blue body tint duration?

13. **Time-of-day / lighting.** I see no day/night cycle code in rendering files. Confirmed not implemented?

14. **Splash / loading screen.** I see no splash screen rendering in renderer.py. The "loading databases" prints to console at startup but there's no visual screen. Confirm not implemented?

15. **Subtitle/text speed.** NPC dialogue is rendered statically (lines blitted instantly). No typewriter effect. Confirm not implemented?