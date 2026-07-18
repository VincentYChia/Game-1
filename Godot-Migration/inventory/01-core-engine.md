# 01 — Core Engine: `game_engine.py` Decomposition Map

**Subsystem key**: `core-engine`
**Target file**: `Game-1-modular/core/game_engine.py` (12,035 lines — verified `wc -l` 2026-07-17; CLAUDE.md's "~11,700" is stale)
**Structure**: ONE class, `GameEngine` (game_engine.py:90), plus a module-level import block with two `sys.path.insert` hacks (game_engine.py:63, 68) and two feature flags `CRAFTING_MODULES_LOADED` / `FISHING_MODULE_LOADED` (game_engine.py:76-77).
**Disposition**: This monolith is NOT ported 1:1. It dissolves into Godot scenes, autoloads, and input handlers per the cluster table below. Roughly 3,400 LOC of it (minigame rendering + UI rect plumbing) is engine-replaced outright; ~4,500 LOC is game logic that ports to C#; the rest is glue that gets rewritten thin.

---

## 1. File table (responsibility clusters within the one file)

| Cluster | Line range | ~LOC | Responsibility | Disposition |
|---|---|---|---|---|
| Module imports / sys.path hacks | 1-89 | 89 | Imports, optional crafting-module load with fallback flags | drop — replaced by C# assembly refs; the try/except optionality (76-84) becomes a hard dependency |
| Boot / `__init__` | 90-514 | 425 | DB load order, world/save/map/combat/dungeon init, NPC spawn, WMS init hook, state-field soup (~120 UI fields) | decompose — DB loads → `ContentBootstrapper` (pure C#); system wiring → Godot autoload init; UI rect fields → die (Godot Controls own their state) |
| `add_notification` | 516-521 | 6 | Toast queue, cap 8 | engine-replaces (Godot toast scene) |
| `_get_weapon_effect_data` | 523-597 | 75 | Weapon tags/params + enchantment merge + weaken debuff → attack context | **port-to-C#** (pure logic, feeds damage pipeline) |
| `_is_llm_overlay_blocking` | 599-606 | 8 | Poll invented-item LLM loading state | stays-python-sidecar (IPC status poll) |
| `handle_events` | 608-1479 | 872 | THE input dispatcher: quit/autosave, pause/start menu keys, minigame keys, text input (narrative, waypoint rename), ESC close-priority chain, C/E/K/L/M/P/F/Q/J/TAB/SPACE/1-5, F1-F12 debug keys, mouse motion/wheel/down/up | decompose — Godot `_UnhandledInput` + per-UI `_GuiInput`; ESC priority chain becomes a UI stack manager |
| `handle_right_click` | 1481-1561 | 81 | RMB: interactive-craft material removal, SHIFT+RMB consumable use, offhand attack | decompose (input → commands) |
| NPC dialogue/quest glue | 1563-1811 | 249 | Dialogue button clicks (accept/turn-in + affinity call), F-interaction, async LLM opening w/ token superseding, per-frame poll | port-to-C# (logic) + sidecar IPC for `_start_async_npc_opening` (1720-1786) |
| Village NPC spawn + agent registration | 1812-1937 | 126 | Idempotent village NPC append; personality/locality registration with NPCAgentSystem | port-to-C# spawn; registration → sidecar IPC message |
| `_initialize_world_with_loading_screen` | 1939-2005 | 67 | Recreate WorldSystem with seed, re-link refs, progress-callback loading screen, test-village injection | decompose — Godot loading scene + async world gen |
| Pause/start menu selection | 2007-2282 | 276 | Pause (return/save-exit/exit); start menu New/Load/Default/Temp with ~90-line duplicated restore sequence ×2 | port-to-C# (`SaveLoadService.RestoreAll` deduplicates 2078-2167 vs 2169-2253) |
| `handle_mouse_click` | 2284-3132 | 849 | Master click router: pause→start→quest-log→minigame widgets→UI panels (priority chain)→inventory double-click equip/place/use→world clicks (dungeon chest/portal, dropped items, chests, dungeon entrance, station-type mapping table 2979-3022, resource harvest, barrier break, attack-toward fallback) | decompose — UI clicks → Godot Controls; world clicks → 3D raycast + `WorldInteractionService` (pure C#) |
| Small UI click handlers | 3134-3269 | 136 | Enchant-selection, skills menu (equip/learn), class select, equipment (shift-unequip), stats (+1 alloc), encyclopedia tabs | engine-replaces (Godot Control signals call the same Character APIs) |
| Map/waypoint UI + actions | 3271-3458 | 188 | Map click (teleport/rename/delete/drag), waypoint place/rename/delete confirm | decompose — map UI engine-replaced; teleport/place logic ports (calls MapWaypointSystem) |
| Action combat driver | 3464-4103 | 640 | `_init_action_combat` (3464), `_update_action_combat` per-frame (3533), hitbox/projectile spawn (3624), combo buffer (3667), hit routing → damage pipeline + VFX (3697), `_initiate_attack_toward` incl. legacy arc-sweep fallback (3849), `_get_weapon_type` tag mapping (4042), enemy shake drain (4080) | **port-to-C#** (this is the combat glue that MUST keep ordering); VFX side-calls become event emissions |
| `_load_stat_modifiers_config` | 4108-4149 | 42 | stats-calculations.JSON loader w/ hardcoded default fallback | port-to-C# loader |
| Crafting-session glue | 4151-4406 | 256 | inventory→dict, crafter lookup, `_start_minigame_impl` — buff/title bonus math (4220-4261) + INT difficulty mutation of minigame fields (4303-4389) | **port-to-C#** — bonus/INT math is balance-bearing logic |
| Interactive crafting UI glue | 4408-4793 | 386 | Open/close/click interactive UI, borrowed-materials lifecycle, craft dispatch (instant/minigame/enchant) | decompose — UI engine-replaced; borrowed-materials + dispatch logic ports |
| Classifier/LLM preload | 4444-4563 | 120 | Background-thread classifier preload + CNN warmup (TensorFlow) | stays-python-sidecar (warmup becomes a sidecar-process concern) |
| Invented-item pipeline | 4795-5061, 5285-6443 | 1,330 | Placement hash/dup check (4795-4859), invent flow (4861-4966), LLM async kickoff (4968-5060), result poll (5285), add-to-game (5347), LLM→EquipmentItem conversion (5492-5634), material consumption (5636), enchant applicable inference (5701), recipe persistence + 3-DB registration (5742-6202), saved-recipe re-registration (6204-6415), no-LLM fallback (6417) | split: generation itself stays-python-sidecar; **everything from `_add_invented_item_to_game` down ports to C#** (it mutates runtime databases + inventory and must survive) |
| `_init_world_memory` | 5062-5283 | 222 | Init Factions, WMS, WNS, WES orchestrator, BehaviorInterpreter, NPCAgentSystem, NPCMemory↔Faction wiring — all with graceful-degrade reporting | stays-python-sidecar — becomes "launch/handshake sidecar process" in Godot; the graceful-degrade taxonomy maps to IPC health states |
| Recipe placement validate / craft | 6445-7115 | 671 | `add_crafted_item_to_inventory`, `handle_craft_click` (layout-math click mapping 6491-6608), `load_recipe_placement`, `validate_placement` (6694-6924: per-discipline + cross-tier backwards compat), `craft_item`, `_instant_craft` | validate/craft/instant-craft **port-to-C#**; `handle_craft_click`'s pixel-math dies with Godot Controls |
| Enchantment application flow | 7117-7270 | 154 | Compatible-item scan, test-apply-then-revert dupe check (7178-7191), material consume, XP award | **port-to-C#** |
| `handle_mouse_release` | 7272-7364 | 93 | Drag-drop to inventory slot; drag stone → barrier placement (range 3.0) | decompose (drag = Godot drag-and-drop; barrier placement logic ports) |
| Day/night + chunk info | 7366-7450 | 85 | `get_time_of_day` phase math, `is_night`, chunk display-name/danger mapping | **port-to-C#** (drives night combat multipliers + WMS game-date) |
| Biome debug print | 7456-7490 | 35 | Shift+F8 console dump | port trivially or drop |
| Menu-time / activity / exploration trackers | 7492-7629 | 138 | Menu open/close stat timing, single-overlay-panel enforcement (7499-7525), activity/idle accumulation + 30s flush (7527-7569), chunk-entered detection + WMS events (7571-7629) | port-to-C# (StatTracker feed = sidecar IPC) |
| Dungeon flow | 7635-7793, 8326-8361 | 195 | Enter (rolled/fixed rarity), exit, per-frame wave logic + night multipliers, portal exit | **port-to-C#** |
| Chest systems (dungeon/spawn/death) | 7795-8219 | 425 | Open/close/toggle, transfer both directions, death-chest rich restore mirroring save format (8006-8098), retrieve-all | **port-to-C#** (item-state fidelity is save-critical) |
| Inventory hover/drop | 8221-8324 | 104 | Hover slot from pixel grid, Q/Shift+Q drop → DROPPED_ITEM entity (300s lifetime) | hover dies (Godot Control); drop logic ports |
| **`update()` — per-frame order** | 8363-8576 | 214 | THE frame tick — see §"Per-frame order" below | **port-to-C#** as the ordering contract for `_PhysicsProcess` |
| `render()` — render order | 8578-8849 | 272 | World/dungeon draw, day/night overlay, UI panel painting + rect harvesting, overlays (WES F12, quest log), minigames last, tooltips last, pause menu topmost | engine-replaces — survives only as a z-order/visibility contract |
| `_complete_minigame` | 8870-9111 | 242 | Craft resolution: partial-loss failure path (8944-8951), success consume, ITEM_CRAFTED publish, stat tracking, XP `20×tier×1.5`, first-try title bonus (9072-9080), buff consumption | **port-to-C#** — balance-bearing |
| Minigame render methods | 9113-11643 | 2,531 | `_render_smithing/alchemy/refining/engineering(+3 puzzle helpers)/enchanting` — pure pygame Surface drawing (351 pygame/def hits in the block) | engine-replaces — becomes Godot Control-node overlay scenes (minigames stay 2D per standing decision). Survives as feature-parity checklist only |
| Fishing minigame glue | 11645-11667, 11869-11957 | 112 | Start via FishingManager, complete: loot/XP/titles/FISH_CAUGHT | port-to-C# (render 11669-11867 engine-replaces) |
| `run()` + crash guard | 11959-12011 | 53 | Main loop, 5-consecutive-failure emergency-save circuit breaker | engine-replaces — Godot owns the loop; the crash guard concept re-homes to a global exception hook + `_EmergencySave` |
| `_emergency_save` | 12013-12035 | 23 | Save to `crash_recovery.json` (never overwrites autosave) | **port-to-C#** |

---

## 2. Public surface (what other code actually calls)

`GameEngine` is a top-of-world object; almost nothing calls INTO it except the entry point and test harnesses. Its "public surface" is mostly attributes other systems read after the engine wires itself into them.

**Constructors / loop:**
- `main.py:41,47` — `from core.game_engine import GameEngine; game = GameEngine()` then `game.run()`.
- `tests/integration/conftest.py:70-71` and `tests/integration/harness.py` — boot the REAL engine headless (SDL dummy) and drive `handle_events/update/render` as a playtest harness. **Porting contract: the C# decomposition must preserve a headless-drivable seam** (pure-logic assembly + fake clock) or the 19-scenario integration suite has no equivalent.
- `tools/content_xref_report.py:31-33` — boots `GameEngine()` purely for its database-loading side effects. In Godot this becomes `ContentBootstrapper` usable from `dotnet` CLI.
- `tests/test_npc_agent_wiring.py:248-249` — `GameEngine.__new__(GameEngine)` then calls `_register_npcs_with_agent_system` on the shell. Proves that method is logic, not glue.

**Methods invoked from outside the class:**
- `core/testing.py:19-20` — `CraftingSystemTester(self)` (constructed at game_engine.py:249) holds the engine and drives `craft_item`, `inventory_to_dict`, etc. for the F10 in-game test suite.
- `tests/test_invented_items_integration.py:233` — mirrors `_get_placement_hash` (duplicate-recipe detection algorithm is contract).
- `systems/quest_log_overlay.py` / `world_system/wes/observability_overlay.py` — inverse dependency: engine calls them, they document engine attrs (`quest_log_open`, `quest_log_abandon_rects`) as their API.

**Attributes other systems depend on (set by engine, read elsewhere):**
- `character.dungeon_manager`, `character.world_system` (set at 276-277, 2064-2065, etc.) — Character death handling reads these (character.py:147).
- `character._attack_facing_locked` (set 3907, 8520; cleared 3594-3597) — read by character movement (character.py:855).
- `world.dungeon_manager`, `world.map_system` (263-264) — walkability + death-chest markers (world_system.py:82-85).
- `combat_manager.dungeon_manager` (262), `combat_manager.character` (reassigned on every load, 2062/2146/2234).
- `renderer._temp_npcs`, `renderer._temp_ac_systems`, `renderer._temp_combat_manager`, `renderer._temp_scroll_offset`, `renderer._damage_number_manager`, `renderer._death_effect_manager`, `renderer._debug_hitboxes` (8604-8634, 8741) — **smuggled-attribute anti-pattern**; in Godot these become explicit scene-tree references or vanish.
- `world_system/world_memory/game_date.py:19` — documents `CYCLE_LENGTH = 1440.0` in game_engine.py as its source of truth (cross-language constant: the Python sidecar must agree with the C# clock).

---

## 3. Dependency edges

**Imports FROM (by subsystem):**
- `core.*`: config (Config everywhere), camera (228), notifications (517), testing (249), paths/`get_resource_path` (135+), minigame_effects (18-30, 2343, 8556), interactive_crafting (4414, 4637), crafting_tag_processor (2735), crash_handler (11992).
- `data.*`: 9 database singletons (36-47) + ResourceNodeDatabase (47), SkillUnlockDatabase (176), update_loader (181), map_waypoint_db config (797, 1347), placement_db (4831, 5885), models (Position, Recipe, PlacedEntityType, StationType, CraftingStation 3024, ResourceType 3050, NPCDefinition 1838, EquipmentItem 5498, MaterialDefinition 6056, PlacedEntity 8263).
- `entities.*`: Character, DamageNumber (33), ItemStack (50, 8012), Tool (8014), crafted_stats (6448).
- `systems.*`: WorldSystem, NPC (53), TurretSystem (54), SaveManager (55), DungeonManager (56), MapWaypointSystem (57), training_dummy (281), chunk (2106), attack_effects (3957), llm_item_generator (602, 653, 4884, 4984, 5288, 5751), crafting_classifier (4454, 4898), quest_log_overlay (8672).
- `rendering.*`: Renderer (60), visual_effects (378), visual_effect_bridge (390, 966, 3775, 3801, 3838, 3911, 3992, 4020).
- `Combat.*` (via sys.path hack line 63): CombatManager (64), USE_ACTION_COMBAT (3471), hitbox/projectile/attack_state_machine/player_actions/screen_effects/combat_data_loader (3478-3483), combat_event (3608), FACING_TO_ANGLE (938).
- `animation.*`: AnimationManager, CombatParticleSystem (3484-3485).
- `Crafting-subdisciplines` (via sys.path hack line 68): 5 crafters + rarity_system + fishing (69-75).
- `events.event_bus`: `get_event_bus()` at all 12 publish sites (§6).
- `world_system.*` (ALL become sidecar IPC): wes.observability_runtime (110), config.schema_validator (122), world_memory.world_memory_system (5099), wns.world_narrative_system (5125), wns.behavior_interpreter (5203), content_registry (5156), wes.wes_orchestrator (5159), living_world.factions (5089) + quest_tool (1632), backends.backend_manager (5236), npc.npc_agent (5237), npc.npc_memory (5262), infra.graceful_degrade (1735, 5067), wes.observability_overlay (8660).

**Imports OF this file:** main.py, verify_imports.py, core/testing.py (TYPE_CHECKING), core/__init__.py (doc only), tests/integration/{conftest,harness}.py, tests/test_npc_agent_wiring.py, tools/content_xref_report.py. Nothing in game logic imports GameEngine — good news: the monolith is a top-level orchestrator, not a library.

---

## 4. Engine coupling (every touchpoint class that must be redesigned)

**pygame lifecycle:** `pygame.init()` (95), `display.set_mode` (96, re-created on F11 at 1297), `set_caption` (97), `pygame.time.Clock` (98), `clock.tick(Config.FPS)` with `Config.FPS = 60` (12008; config.py:16), `pygame.quit(); sys.exit()` (12010-12011), `display.flip()` (8589, 8594, 8849), `pygame.event.pump()` during loading screen (1979).

**Event pump:** the entire `handle_events` loop (612-1479) — `pygame.event.get()`, event types QUIT/KEYDOWN/KEYUP/MOUSEMOTION/MOUSEWHEEL/MOUSEBUTTONDOWN/MOUSEBUTTONUP, `event.unicode` text input (763, 795), key constants (`pygame.K_*` ~90 sites). Godot: `_UnhandledInput` + `_GuiInput` + InputMap actions; text input → `LineEdit`.

**Polled input state (not event-driven):** `self.keys_pressed` set (663, 1340) read in `update()` for WASD (8412-8419), X-block (8450), shield (8449-8452); `pygame.mouse.get_pos()` mid-logic (977+, 3684, 8464, 8508, 8527); `self.mouse_buttons_pressed` for held-LMB continuous attack (8472) and RMB block (7761, 8449). Godot: `Input.IsActionPressed` in `_PhysicsProcess`.

**Clock/time:** `pygame.time.get_ticks()` used as ms wall-clock for dt (8382-8384), double-click (2336), double-ESC (714), double-F (917), menu timers (865+), slide animations (2425), fishing water shimmer (11694). One stray `time.time()` at 7719 for dungeon duration (unit mismatch with ticks — pre-existing wart). Godot: `delta` in `_Process`, `Time.GetTicksMsec()`.

**Screen↔world transform (2D camera assumption), the formula `(mouse - VIEWPORT/2)/TILE_SIZE + camera.pos`:** 1557-1558, 2854-2855, 7307-7308, 8466-8467, 8529-8530, plus `camera.screen_to_world` for skills (978+). In 3D this becomes camera raycast to ground plane — every one of these sites is a redesign point.

**Rect-based hit testing:** ~120 `self.*_rect(s)` fields harvested from renderer return values each frame (render(): 8683-8826) and consumed by click handlers (handle_mouse_click 2284-3132, all §1 "small UI click handlers"). Entirely dies in Godot — Controls receive their own input.

**Direct drawing:** `_render_*_minigame` block (9113-11643, ~2,531 LOC) draws with `pygame.Surface/draw/font` directly onto `self.screen`; also fishing rect (11686), overlay fonts created lazily (8662, 8674). Godot: Control-node overlay scenes.

**Threads:** `_start_async_npc_opening` worker thread (1748-1786) with token-superseding poll (1788-1810); `_preload_classifier` (4450-4482); `_startup_warmup_cnn_classifiers` (4492-4563, TensorFlow — sidecar concern); LLM background generation polled at 5285. Godot/C#: sidecar IPC with `Task`-based poll; the token-superseding pattern (1750-1757, 1801) is the contract to keep.

**sys.path hacks:** lines 63, 68 — die in C# (assembly references).

**Resolution scaling:** `Config.scale()`/`Config.init_screen_settings()` (93) and `Config.inventory_grid_origin()` (1514, 2664, 7284, 8238) — the "§15 trap 17" single-source-geometry comments mark places where renderer and engine had to agree on pixel math. Godot anchors/containers eliminate the class of bug.

---

## 5. Constants & formulas (exact values from code)

**Day/night cycle** (491-494, 7374-7388): `game_time` starts at **960.0** (noon) for new worlds; `DAY_LENGTH=960.0`, `NIGHT_LENGTH=480.0`, `CYCLE_LENGTH=1440.0` s. Phase boundaries within cycle: night `[0,480)`, dawn `[480,600)`, day `[600,1320)`, dusk `[1320,1440)`. Cross-checked by `world_system/world_memory/game_date.py:19` — the Python sidecar hardcodes 1440.0 too.
**Night combat multipliers** (7757-7758, also passed to `combat_manager.update` 8537): aggro ×**1.3**, speed ×**1.15** when `is_night()`.
**Movement**: diagonal normalization ×**0.7071** (8422-8423); `Config.PLAYER_SPEED = 0.15` tiles/frame-ish (config.py:183) fed to dodge velocity (3558); encumbrance multiplier ≤0 ⇒ movement blocked with 2000 ms warning cooldown (8403-8409).
**Input timing**: double-click window **500 ms** (2337); minigame abandon double-ESC window **1500 ms** (715); dungeon quick-exit double-F **500 ms** (920); idle threshold **10.0 s**, activity flush every **30.0 s** (479-482); notification lifetime **3.0 s**, stack cap **8** (517-521).
**Combat glue**:
- Unarmed fallback `baseDamage = 5`; armed fallback = mean of weapon damage tuple (544-546, 590-595).
- Enchant `damage_multiplier` effects summed additively into `1.0 + Σvalue` then multiply baseDamage (551-571). Weaken status: `baseDamage ×= (1 - stat_reduction)`, default reduction 0.25 (575-582).
- Legacy sweep arc half-widths: default **45°**, bow/staff **15°**, dagger/spear **20°**, axe/sword_2h/hammer_2h **55°** (3932-3938).
- Player hurtbox radius **0.35** tiles (3501).
- Kill screen-shake by tier `{1:2, 2:3, 3:5, 4:8}` intensity /150 ms (3787-3788); hit shake `{1:2,2:3,3:5,4:7}` intensity, `{1:80,2:120,3:180,4:250}` ms (3832-3834).
**XP awards** (sacred-adjacent — these are the engine-side sources of EXP):
- Instant craft = **0 EXP** (7062-7063, comment "per Game Mechanics v5").
- Minigame craft = `int(20 × station_tier × 1.5)` (9034).
- Enchant apply (non-minigame path) = `20 × station_tier` (7211).
- Fishing XP from FishingManager result (11898-11900).
**Crafting glue**:
- INT minigame difficulty (defaults if `stats-calculations.JSON` fails, 4114-4135): `reductionPerPoint=0.02`, `maxEffectiveINT=30`; bounds — hammer-speed min mult 0.4, temp-decay min 0.5 (applied at half rate: `1 - int_reduction*0.5`, 4335), time-limit max mult 1.6, refining rotation min 0.4, alchemy speed-bonus max +0.6. Matches the sacred "INT -2% difficulty".
- Grid size per station tier: `{1:(3,3), 2:(5,5), 3:(7,7), 4:(9,9)}` (6691).
- First-try title bonus multiplies all crafted stats by `(1 + firstTryBonus)` (9072-9080).
- Failure material loss: crafter-provided `loss_fraction` (default 1.0 if absent) via `consume_materials_partial` (8944-8951) — the tier-scaled 30-90% penalty contract.
- Invented-item durability: `BASE_DURABILITY = 250`, `TIER_MULTIPLIERS = {1:1.0, 2:2.0, 3:4.0, 4:8.0}` (5521-5522) — **sacred tier multipliers appear verbatim here; must survive**.
- Invented-item damage spread: scalar dmg → `(int(d*0.8), int(d*1.2))` (5513, 5516).
- Duplicate-recipe detection: MD5 of sorted-key JSON of `{discipline, gridSize, placementMap, vertices, shapes, ingredients, coreInputs, surroundingInputs, slots}` (4795-4823) — hash algorithm is contract (saved recipes compare against it).
**Interaction distances** (tiles): chest/portal/entrance click range **1.5** (2868, 2878, 2942, 2953); chest open / death-chest / portal proximity **2.0** (7817, 7844, 7924, 8347); dropped-item pickup **2.0** (2906); barrier break **2.5** (3098); barrier place max **3.0** (7320); NPC interaction radius default **2.5** (1844).
**Dropped items**: lifetime **300 s** (8306-8307); drop offset +0.5,+0.5 from player (8297-8298).
**World/boot**: `TEMP_WORLD_SEED = 13579` (config.py:44, used 240, 2264); initial enemy spawn count **5** (278); training dummy at **(10.0, 0.0)** (282).
**LLM invented-item config at engine site**: `temperature=0.7` (5031) — **conflicts with CLAUDE.md's documented 0.4**; code wins.
**Text limits**: narrative input **200** chars (765); waypoint name max from `MapWaypointConfig` (798).

---

## 6. Event topics (GameEventBus)

GameEngine **publishes only** (no direct subscriptions; `VisualEffectBridge.connect()` at 391-395 subscribes on its own behalf).

Direct `get_event_bus().publish(...)` sites:

| Topic | Site | Payload highlights |
|---|---|---|
| `NPC_INTERACTION` | 1709 | npc_id, npc_name, position_x/y |
| `TURRET_PLACED` | 2808 | item_id, tier, tags, position |
| `RESOURCE_GATHERED` | 3075 (source="gathering") | resource/material_id, quantity, tool_used, biome, position |
| `ITEM_INVENTED` | 5380 (enchantment), 5472 (item) | actor_id, item_id/name, discipline, category, tier, rarity, position |
| `RECIPE_DISCOVERED` | 5800 | recipe_id `invented_*`, discipline, tier |
| `BARRIER_PLACED` | 7352 | material_id, position |
| `CHUNK_ENTERED` | 7609 | chunk_x/y, biome, position |
| `AREA_DISCOVERED` | 7619 (first visit only) | chunk_x/y, biome, has_dungeon |
| `CHEST_OPENED` | 8207 | chest_id, chest_type="dungeon", position (**bugged — see §11**) |
| `ITEM_CRAFTED` | 8990 (source="crafting") | recipe_id, output_id, discipline, quality, station_tier, position |
| `FISH_CAUGHT` | 11927 | fish_id, quantity, tier, rarity, position (**bugged — see §11**) |

Indirect publishes via `rendering.visual_effect_bridge` helper functions (these wrap bus publishes): `publish_dodge_performed` (966), `publish_damage_dealt` (3775 action-combat, 3992 legacy), `publish_enemy_killed` (3801, 4020), `publish_player_hit` (3838), `publish_attack_started` (3911).

Every direct publish is wrapped in `try/except Exception: pass` — the porting contract is **fire-and-forget, never crash gameplay**. In Godot these become the C#→sidecar IPC event feed (WMS consumes ~60 topics; these 11 + the 5 bridge topics are game_engine's share).

---

## 7. Content JSON consumed (exact paths + loader, boot order matters)

Boot sequence at 135-182 (order is load-bearing: resource nodes before world gen; materials before equipment; updates last):

| # | Path | Loader |
|---|---|---|
| 1 | `Definitions.JSON/resource-node-1.JSON` | `ResourceNodeDatabase.load_from_file` (135) |
| 2 | `items.JSON/items-materials-1.JSON` | `MaterialDatabase.load_from_file` (138) |
| 3 | `items.JSON/items-refining-1.JSON` | `MaterialDatabase.load_refining_items` (139) |
| 4 | `items.JSON/items-alchemy-1.JSON` (categories=['consumable']) | `MaterialDatabase.load_stackable_items` (142) |
| 5 | `items.JSON/items-engineering-1.JSON` (['device']) | same (145) |
| 6 | `items.JSON/items-testing-tags.JSON` (['device','weapon']) | same (148) |
| 7 | `items.JSON/items-smithing-2.JSON` (['station']) | same (151) |
| 8 | `Definitions.JSON/crafting-stations-1.JSON` (['station'], legacy) | same (154) |
| 9 | translations | `TranslationDatabase.load_from_files` (156) |
| 10 | all recipes | `RecipeDatabase.load_from_files` (157) |
| 11 | all placements | `PlacementDatabase.load_from_files` (158) |
| 12 | `items-engineering-1 / items-smithing-2 / items-tools-1 / items-alchemy-1 / items-testing-tags` | `EquipmentDatabase.load_from_file` ×5 (161-167) |
| 13 | titles (sacred glob + generated overlay) | `TitleDatabase.load_from_files` (173) |
| 14 | `progression/classes-1.JSON` | `ClassDatabase.load_from_file` (174) |
| 15 | skills (glob incl. generated) | `SkillDatabase.load_from_files` (175) |
| 16 | `progression/skill-unlocks.JSON` | `SkillUnlockDatabase.load_from_file` (177) |
| 17 | NPCs + quests | `NPCDatabase.load_from_files` (178) |
| 18 | Update-N packages | `update_loader.load_all_updates` (182) |
| 19 | `Definitions.JSON/combat-config.JSON` + `Definitions.JSON/hostiles-1.JSON` | `combat_manager.load_config` (255-258) |
| 20 | `Definitions.JSON/stats-calculations.JSON` → `characterStatModifiers` | `_load_stat_modifiers_config` (4108-4149) |
| 21 | Action-combat JSON (attacks/hitboxes/projectiles) | `CombatDataLoader.load_all` (3488-3489) |

All are reused verbatim in Godot; the loaders port to the pure-logic C# assembly. Note 13/15 use `load_from_files()` glob to pick up WES-generated `*-generated-*.JSON` — the C# loaders must preserve glob+overlay semantics (2026-06-10 fix comment at 169-172).

---

## 8. Persistent state contributed by this file

**Save call signature** (all sites): `save_manager.save_game(character, world, character.quests, npcs, filename, dungeon_manager, game_time, map_system)` — quit-autosave (616-625), start-menu-ESC (690-700), pause Save&Exit (2018-2027), F6 timestamped manual (1191-1200), emergency (12023-12032).
**Filenames**: `autosave.json`, `save_YYYYmmdd_HHMMSS.json`, `default_save.json`, `crash_recovery.json` (12028 — deliberately separate so a corrupt-state save can't clobber a good autosave).
**Engine-owned values in the save**: `game_time` (persisted via save_game arg; restored from `world_state.game_time` at 2131/2219); world `seed` (restored 2088-2096, drives deterministic regeneration); `world.set_chunk_save_directory(filename)` (2096, 2187) ties chunk files to the save.
**`character.invented_recipes`** (list of dicts, appended at 5791): each record = `{timestamp, discipline, item_id, item_name, item_data, from_cache, recipe_inputs, station_tier, narrative, placement_data, icon_path, is_enchantment}` (5772-5789). On every load, `register_saved_invented_recipes()` (6204-6415) rebuilds the runtime registrations in FOUR places: Crafter.recipes + Crafter.placements, RecipeDatabase (+recipes_by_station), PlacementDatabase, and Material/Equipment DB via `_register_invented_item_with_database` (6041-6202). **The C# port must reproduce this 4-way re-registration or invented items silently vanish from crafting after load.**
**Death-chest rich item restore** (8006-8098) deliberately mirrors `_serialize_inventory` in save_manager.py field-for-field (EquipmentItem kwargs incl. soulbound, bonuses, enchantments, requirements; Tool path) — schema coupling to the save format.
**WMS/faction state**: `world_memory.save()` on quit (630-632); faction + dungeon + map restore delegated to SaveManager (1259-1269 etc.). In Godot, WMS save becomes an IPC `flush` command to the sidecar.
**Restore order contract** (F9 handler 1244-1281 and both start-menu load paths): character → invented recipes re-registration → world → quests → NPC state → factions → dungeon → map → respawn wave if in dungeon → camera reset. Duplicated 3× in the file; port once.

---

## 9. 3D notes (what necessarily changes)

1. **Click-to-world mapping**: all five inline `(mouse - VIEWPORT/2)/TILE_SIZE + camera` conversions (§4) become `Camera3D.ProjectRayOrigin/Normal` + ground-plane intersection or physics raycast. Attack-toward, harvest, station/chest/entrance/dropped-item clicks, and barrier drag-place all route through it.
2. **Facing**: `attack_angle = atan2(dy,dx)` degrees in screen-aligned 2D (3875) and `FACING_TO_ANGLE` dodge mapping (938-955) become yaw around Y. `character.facing_angle` and `_attack_facing_locked` (3877, 3907) map to a `FacingComponent` that combat and animation both read. Python `(x, y)` → Godot `(x, 0, z)` per the standing `GamePosition` decision.
3. **Distances**: every `math.sqrt(dx²+dy²)` proximity check (chests 2864-2867, 7813-7816; portal 8343-8346; barrier 7319) needs an explicit planar-distance policy (ignore Y) — same `DistanceMode` toggle as the migration plan's `TargetFinder`.
4. **Hitboxes/dodge**: `_update_action_combat` applies dodge displacement directly to position with no collision check (3558-3562) — in 3D this must go through `CharacterBody3D.MoveAndSlide` or it clips into geometry. Hitbox spawns (3654-3659) become `Area3D` shapes; arcs (hitbox_arc_degrees) become wedge shapes or angle tests in the ported HitboxSystem.
5. **Camera**: `camera.follow(position)` (8428) + screen-shake offset swap (8597-8601, 8638 resets before UI) become a `Camera3D` rig; shake applies to the rig, never to UI (Godot CanvasLayer gives this for free).
6. **Day/night overlay** (8641-8642) becomes `DirectionalLight3D` + `WorldEnvironment` driven by the same `get_time_of_day()` phases — the phase math ports untouched, only presentation changes.
7. **Dungeon as separate space**: dungeon currently swaps rendering + a walkability flag in the same world (8609-8624). In 3D it is cleanest as a separate scene/instanced level; `dungeon.return_position` teleport contract (8352-8356) is preserved.
8. **Dropped items / placed entities**: `PlacedEntity` grid-snap placement (2725, `snap_to_grid`) keeps grid logic but instantiates 3D scenes; DROPPED_ITEM pickup radius unchanged.
9. **Minigames stay 2D**: per standing decision, the six `_render_*_minigame` implementations become Control-node overlay panels; the *input* mappings (SPACE=fan/attempt, C=chain, S=stabilize, clicks on puzzle cells/wheel/pond, 727-736, 2409-2516) are the parity checklist.

---

## 10. Godot mapping (proposed)

**Pure-logic C# assembly (`Game1.Core`, testable via `dotnet test`, no Godot types):**
- `ContentBootstrapper` — §7 load order (boot cluster 135-182 + 4108-4149).
- `GameClock` — game_time, day/night phases, `IsNight` (491-494, 7366-7393).
- `AttackContextBuilder` — `_get_weapon_effect_data` + `_get_weapon_type` (523-597, 4042-4078).
- `CombatOrchestrator` — `_update_action_combat`/`_ac_*`/`_initiate_attack_toward` minus VFX calls (3533-4040); emits events instead of calling particles/shake directly.
- `CraftingSessionService` — `_start_minigame_impl` bonus+INT math (4203-4389), `validate_placement` (6694-6924), `craft_item`/`_instant_craft` (6926-7115), `MinigameResolver` = `_complete_minigame` (8870-9111), `EnchantmentApplicator` (7117-7270).
- `InventedItemService` — placement hash, dedup, `_add_invented_item_to_game` → `_register_invented_item_with_database`, `RegisterSavedInventedRecipes` (4795-6443, minus the sidecar call itself).
- `ChestService` (7795-8219 + rich restore 8006-8098), `DungeonFlowService` (7635-7793, 8326-8361), `WorldInteractionService` (world-click resolution 2850-3132 as ordered predicate chain), `ActivityTracker` (7492-7629), `SaveOrchestrator` (restore-order contract §8 + `_emergency_save`).

**Godot autoload singletons (thin engine glue):**
- `GameRoot` (Node) — owns boot, current-scene swaps (start menu / world / dungeon), the crash guard (frame-guard concept from 11982-12007 re-homed to a global exception handler).
- `UiStack` (CanvasLayer) — replaces the ESC priority chain (805-853) and `_close_other_overlay_panels` single-panel rule (7499-7525) with an explicit modal stack; replaces ~120 rect fields.
- `NotificationHud` — `add_notification` cap-8 queue.
- `SidecarClient` — `_init_world_memory` (5062-5283) becomes process launch + handshake; NPC dialogue async (1720-1810) becomes request/poll with the same token-superseding rule; LLM invented-item flow (4968-5060, 5285-5345) and classifier warmup become sidecar RPCs; F12 overlay reads sidecar health feed.
- `EventBusBridge` — C# in-proc event bus (already decided) + forwarder of §6 topics to the sidecar.
- `DebugConsole` — F1-F12 handlers (1016-1337): F1/F2/F3/F4 save-restore toggle pattern (`debug_saved_state`/`debug_mode_active`, 352-364) ports as a `DebugToggle<TState>` helper; F5 keep-inventory, F6 quicksave, F7 durability, F8 dungeon/biome, F9 load, F10 test-suite, F11 fullscreen (`DisplayServer`), F12 sidecar overlay.

**Scenes:**
- `World3D.tscn` (player CharacterBody3D + camera rig + chunk streamer), `Dungeon3D.tscn`.
- `StartMenu.tscn`, `PauseMenu.tscn` (2007-2282 selection logic ports; rendering dies).
- Overlay panels: `StatsPanel`, `EquipmentPanel`, `SkillsPanel`, `EncyclopediaPanel`, `MapPanel` (+waypoint rename/delete modals), `QuestLog`, `NpcDialogue`, `CraftingPanel`, `InteractiveCraftingPanel`, `EnchantSelect`, chest panels ×3 — each a Control scene emitting signals into the services above; all the pixel-math click handlers (§1) die.
- Minigame overlays (2D Controls per standing decision): `SmithingMinigame.tscn`, `AlchemyMinigame.tscn`, `RefiningMinigame.tscn`, `EngineeringMinigame.tscn` (+3 puzzle sub-scenes), `EnchantingWheel.tscn`, `FishingPond.tscn` — logic classes come from the Crafting-subdisciplines port (separate subsystem); the 2,531 LOC of pygame drawing here is the visual parity reference only.

**Split rule of thumb:** anything in this file that touches `pygame`, `self.screen`, `*_rect`, or `renderer` is glue; anything that mutates Character/Inventory/DB/World state or computes a number is `Game1.Core`.

---

## 11. Port complexity, ordering, risks

**Complexity: XL** for the file overall; by cluster: combat driver **L**, invented-item pipeline **L**, crafting session + minigame resolution **L**, input/UI decomposition **L** (wide, not deep), save/restore orchestration **M**, chests/dungeon/day-night/trackers **M**, boot **M**, minigame renders **M** (re-authoring, not porting), debug keys **S**.

**Ordering constraints (what must exist first):**
1. `ContentBootstrapper` + all data-model/database ports (data/ subsystem) — nothing else runs without them; load ORDER of §7 preserved.
2. Character + Inventory + Equipment components (entities/ subsystem) — every click handler mutates them.
3. CombatManager + action-combat systems (Combat/ subsystem) — `CombatOrchestrator` here is glue over them and encodes the frame ORDER below.
4. WorldSystem/chunks, SaveManager, DungeonManager, MapWaypointSystem.
5. Crafting-subdiscipline crafter classes — `_start_minigame_impl` and `_complete_minigame` call `create_minigame`/`craft_instant`/`craft_with_minigame` and depend on their exact result-dict shape (`success/outputId/quantity/rarity/stats/bonus/loss_fraction/enchanted_item/first_try_eligible`).
6. Sidecar IPC layer last — everything here degrades gracefully without it by design (all world_system imports are try/except non-fatal).

**THE per-frame order contract** (`update()` 8363-8576 — `_PhysicsProcess` must reproduce this sequence):
1. Gate: start menu / pause / no character → nothing ticks (8367-8368; pause = full world freeze).
2. Poll sidecar results: LLM invented-item completion (8371), async NPC dialogue (8374).
3. LLM modal overlay active → camera-follow only, early return (8377-8380).
4. `dt` from wall clock (8382-8384); `game_time += dt` (8387).
5. Trackers: playtime (8391), activity/idle (8394).
6. Player WASD movement w/ encumbrance, diagonal 0.7071 (8396-8426); camera follow (8428).
7. **If no minigame active** (8431): world.update → chunk load/exploration (8432-8438) → activity tracker AGAIN (8442 — see bug list) → **WMS drain** `world_memory.update(dt, game_time, character)` (8446) → shield-block state (8449-8454) → X-key offhand attack (8461-8468) → held-LMB continuous mainhand attack via state machine or buffer (8472-8531) → **dungeon XOR overworld combat**: `_update_dungeon(dt)` (waves, night mults) or `combat_manager.update(dt, shield, is_night)` (8534-8537; enemy AI + enemy status ticks live here, enemy.py:756) → enemy screen-shake drain (8540) → **action-combat tick** `_update_action_combat(dt)` (8543: player actions/dodge → hurtbox invuln → attack SM phase events → hitbox positions → hitbox collisions → projectiles → screen fx → animations → particles, 3553-3622) → **player** cooldown/health-regen/buffs+**player status effects** (character.update_buffs → status_manager.update, character.py:1457-1467)/knockback (8545-8548) → turrets (overworld only, 8551-8552).
8. **Else** (minigame active): minigame.update unless metadata overlay blocks (8555-8558); auto-complete when result set (fishing waits for click) (8561-8566). Note: the whole world pauses during minigames.
9. Damage numbers + notifications decay (8568-8569); enhanced VFX managers (ms-based) (8572-8576).
Key ordering facts to preserve: enemy attacks resolve BEFORE player status/buff ticks in the same frame; hitbox collisions resolve before projectiles; WMS drain happens before combat; dodge i-frames are set inside action-combat tick from `pa.is_invulnerable` (3579-3581).

**Render/z-order contract** (`render()` 8578-8849, for CanvasLayer ordering): world/dungeon → day-night overlay → HUD/inventory/hotbar → notifications → F12 overlay → quest log → chest UIs → class-selection XOR (interactive-crafting | crafting) → stats → skills → equipment → encyclopedia → map → NPC dialogue → enchant selection → **minigames above all UI** → loading indicator → tooltips → **pause menu topmost**. Class-selection open suppresses ALL other panels (8713-8719 else-branch nesting).

**Top risks / gotchas found in code (call out to porter):**
1. **Double activity-time tick**: `_update_activity_time(dt)` runs at 8394 AND again at 8442 when no minigame is active — activity/idle seconds are double-counted outside minigames. Decide: replicate (bug-compat for WMS stats) or fix and note the stat discontinuity.
2. **CHEST_OPENED / FISH_CAUGHT publish position (0,0) always**: `getattr(self.character, 'x', 0)` at 8210-8211 and 11932-11933 — Character has `.position.x`, never `.x`, so the getattr default always wins. Fix in port (use position.x/y) and flag to the WMS team that historical events had zeroed positions.
3. **Per-frame debug print** at 8458 spams the console every frame while blocking is attempted — drop in port.
4. **Enchant "test apply then revert"** (7178-7185): calls the real `apply_enchantment`, then restores a deepcopy of the enchantments list. Any side effect outside `equipment.enchantments` leaks. Port as a pure `CanApplyDetailed` check instead. Also `self.enchantment_selection_items = []` at 7206 writes a never-read attribute (typo for `enchantment_compatible_items`) — dead code.
5. **Duplicated init state**: minigame fields initialized twice (327-332 vs 454-459); `placement_grid_rects` typed dict at 367 then list at 403. Harmless in Python, but do NOT copy the shape confusion into C#.
6. **Three near-identical save-restore sequences** (F9 1244-1281, start-menu Load 2078-2167, Default 2169-2253) with subtle diffs (F9 does NOT restore `game_time`; menu paths do). Port ONE `RestoreAll` and unify deliberately — decide whether F9's missing game_time restore is a bug (it looks like one).
7. **`_start_minigame_impl` mutates minigame instance fields by hasattr-duck-typing** (`HAMMER_SPEED`, `TEMP_DECAY`, `time_limit`, `rotation_speed`, `speed_bonus`, 4325-4389) — in C# this becomes an `IIntScalable` interface on the minigame classes; missing a field silently drops the INT benefit today.
8. **Debug F2 passes the ENGINE as `character`** to `learn_skill(skill_id, character=self, ...)` (1062) while the skills-menu path passes `self.character` (3188). Works only because `skip_checks=True`; port with the correct type.
9. **`time.time()` vs `pygame.time.get_ticks()` mixing** for dungeon completion time (7719) — normalize to one clock in port.
10. **Global-state toggles for debug**: `rarity_system.debug_mode` flipped from the engine (7008-7017, 8907-8914) and `Config.DEBUG_INFINITE_RESOURCES` mutated at runtime (1024, 1040) — in C# these become injected `DebugFlags`, not writes into a library singleton.
11. **Threading contract**: NPC dialogue token superseding (1750-1810), `abandoned` result discarding for cancelled LLM gens (5306-5309), and "materials consumed only on success" (645-649 comment) — the IPC port must preserve all three or you get stale-dialogue swaps and material-loss-on-cancel regressions.
12. **`--temp` CLI flag + `GAME1_HERMETIC=1` env** (213, 507, 5170-5181) gate temp-world boot, CNN warmup skip, and WES isolation — port as launch options; integration tests depend on them.
13. **Stale doc drift confirmed**: file is 12,035 lines not ~11,700; invented-item LLM temperature is 0.7 (5031) not the documented 0.4; station-type map (2979-3022) hardcodes 40 item-id→station mappings that belong in data.

---
*Evidence basis: full read of game_engine.py (all 12,035 lines across 10 chunks), grep of publish sites, cross-file caller grep, character.py:1450-1480, combat_manager.py/enemy.py status-update sites, config.py constants. Code, not docs, was treated as truth throughout.*
