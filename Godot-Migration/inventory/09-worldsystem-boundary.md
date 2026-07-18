# 09 — events/ + world_system Sidecar IPC Surface (Porting Contract)

**Subsystem**: `Game-1-modular/events/event_bus.py` + every boundary crossing between game code and
`Game-1-modular/world_system/` (WMS/WNS/WES), plus the sidecar-bound `systems/llm_item_generator.py`
and `systems/crafting_classifier.py`.

**Standing decision (do not relitigate)**: `world_system/` (~20.6k LOC), the ML crafting classifiers,
and LLM invented-item generation are **NOT ported** — they run as a Python sidecar process; Godot
talks to them over local IPC. This document IS the IPC contract. Everything below is verified
against code (file:line), not docs.

**Verification date**: 2026-07-17, branch `crux-foundry`.

---

## 1. File Table

Paths relative to `Game-1-modular/`. LOC from `wc -l` (2026-07-17).

| File | LOC | Responsibility | Disposition |
|---|---|---|---|
| `events/event_bus.py` | 194 | `GameEventBus` singleton pub/sub. Typed topics (strings), wildcard `"*"`, priority ordering, mute, stats. Synchronous in-place dispatch. | **port-to-C#** (pure logic; becomes the C# event bus AND the IPC fan-out point) |
| `events/__init__.py` | 4 | Package marker/re-export. | port-to-C# (trivial) |
| `entities/components/stat_tracker.py` | 1,156 | 65 `record_*` methods; builds hierarchical stat keys via `build_dimensional_keys` and writes through `StatStore` (direct import of `world_system.world_memory.stat_store`, line 25). | **decompose**: API + key-building port to C#; the SQLite write side becomes batched IPC to sidecar (sidecar keeps owning `world_memory.db`) |
| `rendering/visual_effect_bridge.py` (lines 194–276 only) | ~80 of file | `publish_damage_dealt / publish_enemy_killed / publish_player_hit / publish_dodge_performed / publish_attack_started` helper functions — canonical payload shapes for combat topics. | port-to-C# (the helpers define payload DTOs; the rest of the file is engine-replaces) |
| `core/game_engine.py` (boundary blocks only) | ~500 of ~11,700 | Boot wiring `_init_world_memory` (5062–5283), per-frame `world_memory.update` (8446), NPC dialogue async glue (1720–1810), quest turn-in affinity call (1631–1644), NPC registration (1856–1935+), F12 overlay (1307–1310, 8658–8665), invent/classifier/LLM glue (4444–4560, 4880–5060, 5285–5340), schema-validator + degrade-bridge boot (109–132), autosave WMS flush (629–632). | **decompose**: becomes C# `WorldSidecarClient` + glue in the Godot host |
| `systems/quest_system.py` (boundary blocks) | ~120 of file | `_pregenerate_rewards` (303–335), `_adapt_rewards` (506–536), `_archive_quest_record` (428–504), bus publishes (293, 402, 552). | decompose: quest logic ports to C#; reward pregen/adapt/archive become IPC requests |
| `systems/save_manager.py` (boundary blocks) | ~90 of file | Faction save/restore (74–80, 642–665), ContentRegistry flush (89–123), degrade logging (110). | decompose: becomes `save.flush` / `session.restore` IPC calls |
| `systems/llm_item_generator.py` | 1,531 | Claude API invented-item generation; module-level background-thread machinery (`generate_async`, `is_background_generation_running`, `get_background_result`, `clear_background_result`, `abandon_background_generation`), loading-state UI hooks, cache. | **stays-python-sidecar** (C# gets a thin async client + loading-overlay reimplementation) |
| `systems/crafting_classifier.py` | 1,421 | CNN (TF/Keras) + LightGBM recipe validation; `CraftingClassifierManager.validate/preload/unload`; renders placement → image for CNN internally. | **stays-python-sidecar** |
| `world_system/world_memory/world_memory_system.py` | 743 | WMS facade: `initialize/update/save/load/shutdown/get_world_summary/stats`. | stays-python-sidecar (its public surface becomes IPC methods) |
| `world_system/world_memory/event_recorder.py` | 549 | Bus→SQLite bridge. Subscribes `"*"` (line 97), filters via `BUS_TO_MEMORY_TYPE`/`SKIP_BUS_EVENTS`, enriches (geo address, tags, intensity), triggers interpreter. | stays-python-sidecar (fed by the `event.publish` IPC stream) |
| `world_system/world_memory/event_schema.py` | 576 | `WorldMemoryEvent`, `BUS_TO_MEMORY_TYPE` (78–112), `SKIP_BUS_EVENTS` (115–121). | stays-python-sidecar; **the mapping table must be mirrored in C# as the "which topics to forward" allow-list** |
| `world_system/world_memory/trigger_manager.py` | 254 | Dual-track thresholds; `THRESHOLDS` (23–26); publishes `WMS_TRIGGER_FIRED` (190). | stays-python-sidecar |
| `world_system/world_memory/interpreter.py` | 548 | 33 evaluators; publishes `WMS_INTERPRETATION_CREATED` (199–212); async L2 narrative upgrades drained on main thread. | stays-python-sidecar |
| `world_system/world_memory/stat_store.py` | 719 | SQL-backed hierarchical stats; `build_dimensional_keys`. | stays-python-sidecar (server side of `stats.record`) |
| `world_system/wns/wms_to_wns_bridge.py` | 454 | Subscribes `WMS_INTERPRETATION_CREATED` (148) + `WMS_LAYER_{3..7}_SUMMARY_CREATED` (153); drives cascade → weaver. | stays-python-sidecar (internal to sidecar) |
| `world_system/wns/behavior_interpreter.py` | 731 | Subscribes `WMS_TRIGGER_FIRED` (260) + `WNS_CALL_WES_REQUESTED` (263–264); publishes `WNS_CALL_WES_REQUESTED` (412). | stays-python-sidecar (internal) |
| `world_system/wns/world_narrative_system.py` | 620 | WNS facade; NL1 dialogue capture publishes `WMS_DIALOGUE_CAPTURED` (463). | stays-python-sidecar |
| `world_system/wns/affinity_resolver.py` | 367 | Deterministic `<AffinityShift>` post-processor; clamps per-shift to ±25 (43); writes FactionSystem/NPC state. | stays-python-sidecar |
| `world_system/wns/affinity_shift_parser.py` | 116 | Parses `<AffinityShift>` XML out of weaver narrative. | stays-python-sidecar |
| `world_system/wes/wes_orchestrator.py` | 889 | Subscribes `WNS_CALL_WES_REQUESTED` (206); runs plan on async runner (262–265, fire-and-forget). | stays-python-sidecar |
| `world_system/wes/quest_reward_adapter.py` | 467 | `pregenerate` (180) / `adapt` (210) — **synchronous** LLM calls (`_call_with_task`, 248–288) invoked from the game thread today. | stays-python-sidecar; **crossing must become async in Godot** |
| `world_system/wes/observability_runtime.py` | 313 | Ring buffer (256) + counters + `WES_VERBOSE` stdout stream + graceful-degrade bridge (`install_graceful_degrade_bridge`). | stays-python-sidecar (exposed via `observability.recent` IPC) |
| `world_system/wes/observability_overlay.py` | 177 | **pygame** rendering of the F12 panel (`render_overlay(surface, font, ...)`, 64). | **engine-replaces** (Godot Control panel; data comes over IPC) |
| `world_system/content_registry/content_registry.py` | 579 | Staging/commit/rollback of generated content; `commit()` writes generated JSON files then calls `reload_for_tools` (292). | stays-python-sidecar |
| `world_system/content_registry/database_reloader.py` | 306 | `_RELOAD_TARGETS` (40–111) → calls `reload()` on **game** database singletons in-process; publishes `EVT_DATABASE_RELOADED` (271–275). | **decompose**: in-process reload dispatch is impossible cross-process — becomes a `content.committed` IPC notification that triggers C#-side reload |
| `world_system/living_world/backends/backend_manager.py` | 740 | LLM abstraction (Ollama/Claude/Mock/fixtures, rate limiting); `generate(task, system_prompt, user_prompt, ...) -> (text, err)`. | stays-python-sidecar |
| `world_system/living_world/npc/npc_agent.py` | 680 | `NPCAgentSystem.generate_dialogue` (184) → `NPCDialogueResult` (33–40); `register_npc` (144); `on_world_event` (631). | stays-python-sidecar (server side of `npc.dialogue.generate`) |
| `world_system/living_world/npc/npc_memory.py` | 291 | `NPCMemoryManager`; `wire_faction_system` for SQLite persistence. | stays-python-sidecar |
| `world_system/living_world/factions/faction_system.py` | 682 | SQLite affinity store; publishes `FACTION_AFFINITY_CHANGED` (664–672). | stays-python-sidecar |
| `world_system/living_world/factions/quest_tool.py` | 195 | `QuestGenerator.apply_turn_in` (135–195) — the quest turn-in affinity entry point; constants at 130–133. | stays-python-sidecar (server side of `quest.turn_in`) |
| `world_system/living_world/factions/consolidator.py` | 131 | Publishes `FACTION_AFFINITY_CONSOLIDATED` (108). | stays-python-sidecar |
| `world_system/living_world/factions/__init__.py` | 63 | `initialize_faction_systems` (34) / `save_faction_systems` (49) / `restore_faction_systems` (58). | stays-python-sidecar (folded into `session.init` / `save.flush` / `session.restore`) |
| `world_system/living_world/factions/dialogue_helper.py` | 50 | `assemble_dialogue_context` for prompts. | stays-python-sidecar |
| `world_system/living_world/ecosystem/ecosystem_agent.py` | 398 | Subscribes `RESOURCE_GATHERED` (164), publishes `RESOURCE_SCARCITY`/`RESOURCE_RECOVERED` (265–281). | **drop-dead-code at runtime** — no game code ever calls `EcosystemAgent.get_instance()`/`initialize()` (grep of core/systems/entities/Combat/rendering/events: zero hits). Only tools/tests touch it. Keep in sidecar, unwired. |
| `world_system/living_world/infra/graceful_degrade.py` | 315 | `log_degrade(...)` structured fallback logging; bridged to observability ring buffer at boot (game_engine.py:109–115). | stays-python-sidecar; C# needs its own equivalent for client-side degrades |
| `world_system/config/schema_validator.py` | 305 | `validate_known_configs()` — designer JSON schema check at boot (game_engine.py:122–132). | stays-python-sidecar (run at sidecar boot; result returned in `session.init` response) |

Not enumerated file-by-file: the other ~70 `world_system/` modules (layer managers, evaluators,
weavers, prompt assembler, WES tools, fixtures) are all **stays-python-sidecar** and are interior
to the sidecar — they never cross the boundary except through the topics and calls listed below.

---

## 2. Public Surface (what game code actually calls)

### 2.1 GameEventBus (`events/event_bus.py`)

| Member | Signature | Notes |
|---|---|---|
| `get_event_bus()` | `() -> GameEventBus` | module accessor, line 192 |
| `GameEventBus.get_instance()` | classmethod | line 82 |
| `subscribe` | `(event_type: str, handler: Callable[[GameEvent], None], priority: int = 0)` — `"*"` = wildcard | lines 94–111; lower priority runs first |
| `unsubscribe` | `(event_type, handler)` | 113–122 |
| `publish` | `(event_type: str, data: dict \| None, source: str = "") -> GameEvent` | 124–164. **Synchronous**: every handler runs inline in the publisher's thread; handler exceptions are caught and printed (149–162), never propagated |
| `mute()` / `unmute()` / `clear()` / `stats` | | 166–189 |
| `GameEvent` | `{event_type: str, data: dict, timestamp: float (time.time()), source: str}` | 20–27 |

Callers: ~40 publish sites across the whole game (see §6); subscribers on the game side are the
visual bridge, on the world_system side the five runtime subscriptions in §6.3.

### 2.2 WMS facade (`world_system/world_memory/world_memory_system.py`)

| Call | Caller (file:line) | Signature |
|---|---|---|
| `WorldMemorySystem.get_instance()` | game_engine.py:5105 | singleton |
| `.initialize(save_dir, character=None, world=None, geo_map_path=None)` | game_engine.py:5106–5111 | reads `world.geographic_map` / `world.loaded_chunks`; wires `character.stat_tracker.set_store(stat_store)` (154–155) |
| `.update(dt: float, game_time: float, character=None)` | game_engine.py:8446 — **every frame** | drains async L2 upgrades, samples player position, day-boundary ledger, runs L3–L7 summarizers **synchronously on the game loop** (509–532, stall warning at >0.25 s line 530), retention prune, stat flush |
| `.save() -> dict` | game_engine.py:631 (quit autosave) | returns `{memory_db_path, session_id, game_time, trigger_state}` (630–635). **Return value is discarded at the call site** — see §8 gotcha |
| `.world_query` (attr) | game_engine.py:5242 → NPCAgentSystem | `WorldQuery` instance handed to the NPC agent |
| `.stat_store` (attr) | game_engine.py:5207–5211 → BehaviorInterpreter | |
| `.get_world_summary(game_time=None) -> dict` | narrative/NPC consumers (facade passthrough, 714–726) | |
| `.load(save_data, save_dir, ...)` | **no game-code caller** (grep: none in core/systems) — load happens implicitly via `initialize` at boot | 637–683 |
| `.shutdown()` | test/reset paths | 687–710 |

### 2.3 Living-world consumers

| Call | Caller | Signature / return |
|---|---|---|
| `initialize_faction_systems()` | game_engine.py:5089–5090 | `() -> None`, raises on failure (factions/__init__.py:34–46) |
| `save_faction_systems() -> Dict[str, Any]` | save_manager.py:76–77 | faction.db persists itself; returns metadata dict |
| `restore_faction_systems(data: dict)` | save_manager.py:660–661 | |
| `BackendManager.get_instance().initialize()` | game_engine.py:5239–5240 | |
| `NPCAgentSystem.get_instance().initialize(world_query=, backend_manager=)` | game_engine.py:5243–5247 | npc_agent.py:97 |
| `NPCAgentSystem.register_npc(npc_id, personality=None, location_hierarchy=None, template_name=None)` | game_engine.py `_register_npcs_with_agent_system` 1856–1935+ (called at 5253) | npc_agent.py:144–162 |
| `NPCAgentSystem.generate_dialogue(npc_id, player_input, character=None, npc_name="NPC") -> NPCDialogueResult` | game_engine.py:1761–1766 (**worker thread**, polled per frame at 1788–1810) | `NPCDialogueResult{text, emotion="neutral", relationship_delta=0.0, success=True, from_fallback=False}` (npc_agent.py:33–40) |
| `NPCMemoryManager.get_instance().wire_faction_system(fs)` | game_engine.py:5262–5271 | |
| `QuestGenerator.apply_turn_in(player_id, giver_npc_id, quest_id="", game_time=0.0, explicit_deltas=None) -> Dict[str, float]` | game_engine.py:1632–1640 (quest turn-in) | quest_tool.py:135–195; best-effort, `{}` on failure |
| `get_reward_adapter().pregenerate(quest_def, character) -> (QuestRewards, List[str]) \| None` | quest_system.py:319–326 (`accept_quest`, **synchronous on caller thread**) | quest_reward_adapter.py:180–208 |
| `get_reward_adapter().adapt(quest, character, game_time_now) -> QuestRewards \| None` | quest_system.py:520–529 (`complete_quest`, **synchronous**) | quest_reward_adapter.py:210–246 |
| `WorldNarrativeSystem.get_instance().initialize(save_dir, geo_map_path, wms_facade)` | game_engine.py:5132–5140 | |
| `ContentRegistry.get_instance().initialize(save_dir, game_root=None)` | game_engine.py:5171–5175 (`GAME1_HERMETIC` confines writes) | content_registry.py:90 |
| `ContentRegistry.initialized` / `.db_path` / `.stats` | save_manager.py:92–100 | content_registry.py:130–139, 513+ |
| `WESOrchestrator.get_instance().initialize(registry, subscribe_to_bus=True)` | game_engine.py:5177–5181 | |
| `BehaviorInterpreter.get_instance().attach(bus, stat_store)` | game_engine.py:5212–5216 | behavior_interpreter.py:249 |
| `install_graceful_degrade_bridge()` | game_engine.py:110–113 (before anything else) | observability_runtime |
| `validate_known_configs() -> Dict[str, list]` | game_engine.py:122–128 | config/schema_validator |
| `log_degrade(subsystem, operation, failure_reason, fallback_taken, severity, context)` | game_engine.py:1735, 1770, 5067; save_manager.py:110–120 | graceful_degrade |
| `render_overlay(surface, font, *, x=8, y=8, width=600, max_events=15)` | game_engine.py:8660–8663 (F12) | observability_overlay.py:64–72; **pygame** |

### 2.4 Sidecar-bound systems (game → `systems/`)

| Call | Caller | Signature / return |
|---|---|---|
| `get_classifier_manager()` / `init_classifier_manager(project_root, materials_db)` | game_engine.py:4454–4464, 4496–4508, 4898–4910 | singleton |
| `CraftingClassifierManager.validate(discipline, interactive_ui) -> ClassifierResult` | game_engine.py:4913 | `ClassifierResult{valid, confidence, probability, discipline, error}` (crafting_classifier.py:35–45). **Takes the live UI object** — see §11 risks |
| `.preload(discipline=None)` / `.unload(discipline=None)` | game_engine.py:4467; UI close path | crafting_classifier.py:1298, 1385 |
| `.get_backend(discipline)` + `backend.predict(ndarray)` | game_engine.py:4520–4543 (startup CNN warmup, dummy 36×36×3 / 56×56×3) | |
| `get_item_generator()` / `init_item_generator(...)` | game_engine.py:4882–4885, 4998+ | |
| `LLMItemGenerator.generate_async(discipline, interactive_ui, narrative="") -> bool` | game_engine.py:5045 | starts module-level worker thread + loading overlay (llm_item_generator.py:1462+) |
| `LLMItemGenerator.extract_placement_data(discipline, interactive_ui)` | game_engine.py:4885 (duplicate-recipe check) | serializable placement snapshot — **this is the DTO seed for IPC** |
| `is_background_generation_running() / get_background_result() / clear_background_result() / abandon_background_generation()` | game_engine.py:5288–5338 (polled per frame), ESC cancel path | llm_item_generator.py:336–366 |
| `get_loading_state()` | game_engine.py:610 (`_is_llm_overlay_blocking`), 4475–4476 | UI-blocking overlay state |

### 2.5 StatTracker → StatStore

- `entities/components/stat_tracker.py:25` — `from world_system.world_memory.stat_store import StatStore, build_dimensional_keys`.
- `StatTracker(stat_store=None)` creates an in-memory `StatStore()` until WMS init swaps in the
  SQL-backed one via `set_store` (stat_tracker.py:61–63 ← world_memory_system.py:154–155).
- 65 `record_*` methods, ~51 call sites across game code (docstring, stat_tracker.py:16–17); all
  write via `self._store.record_multi / record_count / record_count_multi / set_value / get_max`.

---

## 3. Dependency Edges

### 3.1 This subsystem imports FROM

- `events/event_bus.py`: stdlib only (`dataclasses`, `typing`, `time`). Zero game imports. Fully pure.
- `world_system/*` (sidecar side) imports from game code — **reverse dependencies that must be severed
  or served by the sidecar's own copy of the loaders**:
  - `data.databases.npc_db.NPCDatabase` (world_memory_system.py:415, database_reloader.py:85–95)
  - `data.databases.{material_db, resource_node_db, skill_db, title_db, chunk_template_db}` + `Combat.enemy.EnemyDatabase` (database_reloader.py:40–111)
  - `data.models.quests.{QuestDefinition, QuestRewards}` (quest_reward_adapter.py:38)
  - `core.config.Config.CHUNK_SIZE` (world_memory_system.py:336–338)
  - `core.paths.PathManager` (used game-side to compute paths handed to world_system: game_engine.py:5100–5103)
  - `events.event_bus` (every subscription/publish inside world_system)
- `systems/llm_item_generator.py` / `systems/crafting_classifier.py` import `MaterialDatabase`,
  placement/recipe models, TF/LightGBM/numpy, `anthropic` — all stay Python.

### 3.2 Who imports THIS subsystem

- `events.event_bus` is imported by ~35 game modules (combat_manager, skill_manager, leveling,
  inventory, equipment_manager, character, quest_system, title_system, class_system, turret_system,
  natural_resource, game_engine, player_actions, visual_effect_bridge, …) — see §6 for lines.
- `world_system.*` is imported by exactly five game modules (non-test, non-tool):
  `core/game_engine.py` (17 import sites, §2), `entities/components/stat_tracker.py:25`,
  `systems/quest_system.py:319,520`, `systems/save_manager.py:76,90,110,660`, and the packaged
  `dist/` copy (ignore).
- Dev tools importing world_system (`tools/prompt_studio`, `tools/hub_cert_harness.py`,
  `tools/wes_real_llm_smoketest.py`, `tools/prompt_coverage_slideshow.py`) remain Python and keep
  working against the sidecar unchanged — no port needed.

---

## 4. Engine Coupling (pygame / input / clock touchpoints to redesign)

| Touchpoint | file:line | Redesign |
|---|---|---|
| F12 overlay renders with pygame `Surface` + `pygame.font.Font` | `world_system/wes/observability_overlay.py:64–177`; glue `core/game_engine.py:8658–8665` (creates `pygame.font.Font(None, 16)`) | Godot `Control` panel (CanvasLayer); data fetched via `observability.recent` IPC; overlay module is not ported |
| F12 key toggle | `core/game_engine.py:1307–1310` (`wes_overlay_open` flip) | Godot InputMap action |
| Per-frame `world_memory.update(dt, game_time, character)` on the render loop | `core/game_engine.py:8446`; sync L3–L7 LLM stalls logged >0.25 s at `world_memory_system.py:509–532` | becomes a throttled IPC tick (§10); LLM stalls disappear from the frame loop by construction (they move to the sidecar process) |
| NPC dialogue worker thread + per-frame poll | `core/game_engine.py:1748–1786` (`threading.Thread`), `1788–1810` (`_poll_async_npc_dialogue` each frame), token supersede `_npc_dialogue_token` | C# `async/await` on the IPC request with a CancellationToken per conversation; keep the token-supersede semantics |
| Invented-item background thread + per-frame poll + input-blocking overlay | `core/game_engine.py:5285–5338` (`_check_background_generation`), `610` (`_is_llm_overlay_blocking`), ESC cancel (645–649 comment; `abandon_background_generation`, llm_item_generator.py:355–366) | async IPC request + Godot modal overlay; ESC sends `invent.cancel` |
| Classifier preload/warmup threads | `core/game_engine.py:4450–4482, 4484–4560` | `invent.preload` IPC notification at UI-open; warmup happens inside sidecar at its own boot |
| Wall-clock timestamps on events | `events/event_bus.py:25` (`time.time()`), `event_recorder.py:211` (`real_time`), `quest_system.py:371` (`turned_in_at = time.time()`) | keep wall clock for real_time; **game_time must ride in the IPC envelope** because the sidecar can no longer read the engine clock |
| Game clock / day-night constants live in the engine | `core/game_engine.py:492–494` (`DAY_LENGTH=960.0`, `NIGHT_LENGTH=480.0`, `CYCLE_LENGTH=1440.0`); WMS day boundary `daily_ledger.py:268–274` (`game_day_length=1.0` — day == 1.0 game_time unit as passed) | C# owns the clock; game_time semantics (what one "day" is) must be pinned in the IPC contract — see §11 risk |
| Bus handler exceptions print to stdout | `events/event_bus.py:154, 162` | C# bus should log via engine logger; never throw across dispatch |
| `WES_VERBOSE` stdout streaming; `print()` everywhere in world_system | e.g. observability_runtime.py:9–13 | sidecar keeps stdout; the Godot host captures sidecar stdout/stderr into its log |
| Classifier/generator take the live pygame UI object (`interactive_ui`) | `crafting_classifier.py:1144–1156`, `llm_item_generator.py:1462`, `extract_placement_data` game_engine.py:4885 | define a serializable `PlacementSnapshot` DTO (grid cells → material ids + discipline metadata); sidecar reconstructs the image/features from the snapshot, never the UI object |

---

## 5. Constants & Formulas (exact values from code)

| Constant | Value | file:line |
|---|---|---|
| Trigger thresholds (both tracks) | `[1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]` | `world_memory/trigger_manager.py:23–26` |
| Intensity tier baselines | `{T1:10, T2:25, T3:60, T4:150}` | `world_memory/event_recorder.py:28` |
| Intensity tag cutoffs (magnitude/baseline) | `>3.0 extreme, >1.5 heavy, >0.5 moderate, else light` | `event_recorder.py:387–396` |
| Chunk derivation | `chunk = int(position) // 16` | `event_recorder.py:433–434`; `Config.CHUNK_SIZE` fallback 16 at `world_memory_system.py:334–338` |
| Default geography bounds | world ±800; 4 province quadrants; 5×5 localities of 16 tiles around spawn | `world_memory_system.py:342–401` |
| Layer-run frame-stall warning threshold | `0.25 s` | `world_memory_system.py:530` |
| Day-night engine clock | `DAY_LENGTH=960.0`, `NIGHT_LENGTH=480.0`, `CYCLE_LENGTH=1440.0` (seconds) | `core/game_engine.py:492–494` |
| WMS day boundary | `current_day = int(game_time / game_day_length)`, default `game_day_length=1.0` | `world_memory/daily_ledger.py:268–274` |
| Quest archive day stamp | `int(completed // 86400)` (**inconsistent with the above** — uses real seconds) | `systems/quest_system.py:502` |
| Turn-in affinity deltas | `NPC_TURN_IN_DELTA=5.0`, `FACTION_PRIMARY_DELTA=4.0`, `FACTION_SECONDARY_DELTA=2.0`, `MAX_FACTION_TAGS=3` | `factions/quest_tool.py:130–133` |
| Affinity value clamp | FactionSystem clamps to `[-100, 100]`; per-WNS-shift clamp `MAX_SHIFT_MAGNITUDE=25.0` | `wns/affinity_resolver.py:37–43` |
| Hand-written per-quest affinity outcome maps | smith_contract / merchant_trade / guard_patrol tables | `quest_tool.py:38–78` |
| NPC dialogue LLM defaults | `temperature=0.4`, `max_tokens=2000` (BackendManager `generate` defaults) | `backends/backend_manager.py:72–76` |
| Invented-item LLM config | model `claude-haiku-4-5`, `max_tokens=2000`, `temperature=0.4`, `top_p=0.95` (**must not be sent together with temperature — Haiku 4.5 400s**), `timeout=30.0`, cache dir `invented_items_cache` | `systems/llm_item_generator.py:83–99` |
| CNN input shapes | smithing `36×36×3`, adornments `56×56×3` | `game_engine.py:4529–4534`; model configs `crafting_classifier.py:1015, 1022` |
| Observability ring buffer | 256 events | `observability_runtime.py:132` |
| F12 overlay defaults | `x=8, y=8, width=600, max_events=15`; font size 16 | `observability_overlay.py:64–72`; `game_engine.py:8662` |
| Event bus priority semantics | lower value runs first; recorder subscribes at `priority=-10` (before visuals) | `event_bus.py:102`; `event_recorder.py:97` |

The sacred game constants (damage pipeline, EXP, tiers, durability, LCK 0.12) do **not** live in
this subsystem — nothing here computes them; payloads only carry their results (`amount`, `tier`).

---

## 6. Event Topics (complete pub/sub census)

### 6.1 Game code → bus (publishers; these must all cross IPC to feed the WMS recorder)

| Topic | Publisher file:line | Payload keys (as published) |
|---|---|---|
| `DAMAGE_DEALT` | `Combat/combat_manager.py:781, 1052`; helper `rendering/visual_effect_bridge.py:204` | `target_id, attacker_id, amount, damage_type, is_crit, position_x, position_y` |
| `ENEMY_KILLED` | `Combat/combat_manager.py:817, 1163`; `systems/turret_system.py:194`; helper bridge:223 | `enemy_id, killer_id, position_x, position_y, tier, visual_size, is_boss, loot` |
| `PLAYER_HIT` | `Combat/combat_manager.py:2127`; helper bridge:242 | `attacker_id, amount, damage_type, player_x, player_y` |
| `PLAYER_DIED` | `entities/character.py:1918` | position, killer |
| `STATUS_APPLIED` | `Combat/combat_manager.py:1897` | `target_id, status_type, duration` |
| `DODGE_PERFORMED` | `Combat/player_actions.py:165`; helper bridge:257 | `position_x, position_y, direction` |
| `ATTACK_STARTED` | helper bridge:270 (visual-only; WMS skips) | `entity_id, attack_id, weapon_type, tags` |
| `SKILL_ACTIVATED` | `entities/components/skill_manager.py:247, 873, 898` | skill_id, tags, position |
| `SKILL_LEARNED` | `skill_manager.py:120` | skill_id |
| `REPAIR_PERFORMED` | `skill_manager.py:729` | item info |
| `LEVEL_UP` | `entities/components/leveling.py:40` | `new_level, stat_points` |
| `ITEM_ACQUIRED` | `entities/components/inventory.py:130` | item_id, qty |
| `EQUIPMENT_CHANGED` | `entities/components/equipment_manager.py:89, 115` | slot, old, new |
| `RESOURCE_GATHERED` | `core/game_engine.py:3075` | resource_id, position, tool, tier… |
| `NODE_DEPLETED` | `systems/natural_resource.py:148` | node info |
| `ITEM_CRAFTED` | `core/game_engine.py:8990` | recipe_id, quality, discipline |
| `ITEM_INVENTED` | `core/game_engine.py:5380, 5472` | invented item info |
| `RECIPE_DISCOVERED` | `core/game_engine.py:5800` | recipe info |
| `NPC_INTERACTION` | `core/game_engine.py:1709` | `npc_id, npc_name, position_x, position_y` |
| `QUEST_ACCEPTED` | `systems/quest_system.py:293` | `quest_id, quest_type, npc_id` |
| `QUEST_COMPLETED` | `systems/quest_system.py:402` | `quest_id, player_id, quest_type, npc_id, rewards{experience, gold}` |
| `QUEST_FAILED` | `systems/quest_system.py:552` | `quest_id, quest_type` |
| `TITLE_EARNED` | `systems/title_system.py:49` | title_id |
| `CLASS_CHANGED` | `systems/class_system.py:63` | class_id |
| `CHUNK_ENTERED` | `core/game_engine.py:7609` | chunk coords |
| `AREA_DISCOVERED` | `core/game_engine.py:7619` | area info |
| `CHEST_OPENED` | `core/game_engine.py:8207` | chest info |
| `FISH_CAUGHT` | `core/game_engine.py:11927` | fish info |
| `TURRET_PLACED` | `core/game_engine.py:2808` | item_id, position |
| `BARRIER_PLACED` | `core/game_engine.py:7352` | material_id, position |

### 6.2 world_system → bus (publishers; internal to sidecar except where noted)

| Topic | Publisher file:line | Cross-boundary relevance |
|---|---|---|
| `POSITION_SAMPLE` | `world_memory/position_sampler.py:40` | internal loop-back into recorder |
| `WMS_TRIGGER_FIRED` | `world_memory/trigger_manager.py:190`; `world_memory_system.py:582` (presence drift) | internal (BehaviorInterpreter) |
| `WMS_INTERPRETATION_CREATED` | `world_memory/interpreter.py:199–212` | internal (WNS bridge); mirrored to observability |
| `WMS_LAYER_{3..7}_SUMMARY_CREATED` | layer managers via `layer_publish` | internal (WNS peak path) |
| `WMS_DIALOGUE_CAPTURED` | `world_memory/layer_publish.py:133`; `wns/world_narrative_system.py:463` | internal (Layer3Manager, subscribed at `world_memory_system.py:208–211`) |
| `WNS_CALL_WES_REQUESTED` | `wns/nl_weaver.py:922`; `wns/behavior_interpreter.py:412` | internal (WESOrchestrator) |
| `FACTION_AFFINITY_CHANGED` | `factions/faction_system.py:664–672` | **should cross back to game** (UI standing display) — currently no game-side subscriber |
| `FACTION_AFFINITY_CONSOLIDATED` | `factions/consolidator.py:108` | same |
| `EVT_DATABASE_RELOADED` | `content_registry/database_reloader.py:271–275`, payload `{tool_name}` | **becomes the `content.committed` IPC notification**; today only tests subscribe (`tests/test_database_reload_e2e.py:352`) |
| `RESOURCE_SCARCITY` / `RESOURCE_RECOVERED` | `ecosystem_agent.py:265–281` | dead at runtime (agent never initialized) |

### 6.3 world_system ← bus (runtime subscriptions — the sidecar's ingest contract)

| Topic | Subscriber file:line | Wired at runtime? |
|---|---|---|
| `"*"` (wildcard, priority -10) | `world_memory/event_recorder.py:97` | YES — via `WorldMemorySystem.initialize` |
| `WMS_DIALOGUE_CAPTURED` | `world_memory_system.py:208–211` → Layer3Manager | YES |
| `WMS_INTERPRETATION_CREATED` | `wns/wms_to_wns_bridge.py:148` | YES (when WNS init succeeds) |
| `WMS_LAYER_{3..7}_SUMMARY_CREATED` | `wms_to_wns_bridge.py:153` (handler factory 272–276) | YES |
| `WNS_CALL_WES_REQUESTED` | `wes/wes_orchestrator.py:206`; `wns/behavior_interpreter.py:263–264` | YES (unless `GAME1_HERMETIC=1`, game_engine.py:5170–5181) |
| `WMS_TRIGGER_FIRED` | `wns/behavior_interpreter.py:260` | YES |
| `RESOURCE_GATHERED` | `ecosystem_agent.py:164` | **NO — dead** (no initializer) |

**Which wildcard events the recorder actually keeps**: only topics in `BUS_TO_MEMORY_TYPE`
(`event_schema.py:78–112` — the 32 mappings incl. `WORLD_EVENT`, `POSITION_SAMPLE`, `ITEM_EQUIPPED`);
`SKIP_BUS_EVENTS` = `{SCREEN_SHAKE, PARTICLE_BURST, FLASH_ENTITY, ATTACK_PHASE, ATTACK_STARTED}`
(115–121). Everything else (e.g. `NPC_INTERACTION` variants not in the map — actually mapped;
but `EVT_DATABASE_RELOADED`, `FACTION_AFFINITY_CHANGED`, `WMS_*`) is silently skipped by the recorder.

**Hidden dead path found**: `FACTION_AFFINITY_CHANGED` is NOT in `BUS_TO_MEMORY_TYPE`
(grep confirms zero matches in event_schema.py), yet
`world_memory/evaluators/faction_reputation.py:32` declares `RELEVANT_TYPES = {"FACTION_AFFINITY_CHANGED"}`
and its docstring claims it consolidates those events into L2. The recorder skips the topic, so a
`WorldMemoryEvent` with that type is never created via the bus, and `record_direct` has no non-test
caller (grep: tests only). The evaluator is unreachable through the standard pipeline. Port note:
either add the mapping in the sidecar or drop the evaluator — do not replicate the broken wiring.

### 6.4 Game-side subscriptions (stay in C#, no IPC)

`rendering/visual_effect_bridge.py` and the animation system subscribe to combat/visual topics —
they are engine-replaced; the C# bus serves them locally.

---

## 7. Content JSON Consumed (by this boundary)

| Path | Loader | Notes |
|---|---|---|
| `world_system/config/geographic-map.json` | `GeographicRegistry.load_base_map` — path computed game-side (`game_engine.py:5103, 5129–5131`) and passed into `initialize` | sidecar-owned after port; path handed over in `session.init` |
| `world_system/config/stat-key-manifest.json` | `StatStore.load_manifest` (`world_memory_system.py:110–117`) | sidecar |
| `world_system/config/npc-personalities.json` | `NPCAgentSystem.initialize(config_path)` (`npc_agent.py:97–115`) | sidecar |
| `world_system/config/prompt_fragments_wes_quest_reward_pregen.json` / `..._adapt.json` | `quest_reward_adapter.py:203–205, 234–236` | sidecar |
| `world_system/config/*.json` (7 configs: memory, geographic, backend, faction, event-triggers, npc, tags) | respective world_system loaders; schema-checked at boot by `validate_known_configs` (`game_engine.py:122–128`) | sidecar |
| `Fewshot_llm/` prompt files | `llm_item_generator.py` PromptLoader | sidecar |
| `Scaled JSON Development/crafting_classifier_models/{smithing,adornment,alchemy,refining,engineering}/…` | `CraftingClassifierManager` configs (`crafting_classifier.py:1010–1044`) | sidecar (model binaries: .keras / .txt / .pkl) |
| **Written** (not read): generated content overlays — `progression/npcs-generated-*.JSON`, `Definitions.JSON/Chunk-templates-generated-*.JSON`, plus per-tool generated files for materials/hostiles/nodes/skills/titles | `ContentRegistry.commit()` writes; `database_reloader.py:40–111` names the target DB singletons | after port, the **C# loaders** must glob these generated siblings exactly like the Python loaders do (game_engine.py:169 comment: "sacred glob + generated overlay") |
| `progression/npcs-1.JSON` (NPC personalities/speechbanks inline, v3 schema) | game-side `NPCDatabase`; personalities forwarded to sidecar via `register_npc` (`game_engine.py:1856+`) | dual-consumer: C# loader for game, snapshot over IPC for agent |

Content JSON is reused verbatim per the migration ground rules — no file in this table is modified
by the port; the generated-overlay siblings are *runtime products* of the sidecar.

---

## 8. Persistent State

All in the save directory (`core/paths.PathManager.save_path`):

| Artifact | Owner | Contents |
|---|---|---|
| `world_memory.db` (SQLite, WAL) | EventStore + StatStore (shared connection, `world_memory_system.py:105–108`) | 20 event tables, occurrence counters, entity/region states, daily ledgers, meta stats, interpretations |
| `layer_store.db` | LayerStore (`world_memory_system.py:119–127`) | L2–L7 tag-indexed narratives |
| `faction.db` | FactionSystem (schema.py) | npc_affinity, player_affinity, location_affinity_defaults, NPC dynamic state (via NPCMemoryManager wiring) |
| `content_registry.db` | ContentRegistry | staged/live generated content + xrefs |
| `world_narrative.db` | WNS | narrative rows, NL1 dialogue log |
| Save-JSON key `faction_state` | `save_manager.py:74–80` → `save_faction_systems()` | metadata dict (db persists itself) |
| Save-JSON key `content_registry_state` | `save_manager.py:97–104` | `{db_path, stats}` or `{initialized: False}` |
| `invented_items_cache/` | LLMItemGenerator (`llm_item_generator.py:99`) | cached generations |
| `llm_debug_logs/` (`wes_<session>.jsonl` + per-call JSON) | backends + item generator | audit logs |

**Gotchas found**:
- `WorldMemorySystem.save()` returns `{memory_db_path, session_id, game_time, trigger_state}`
  (`world_memory_system.py:630–635`) but the only caller discards the return
  (`game_engine.py:631`), and `WorldMemorySystem.load(save_data, …)` has **no game-code caller**
  (grep: none in core/systems). Net effect: `trigger_state` (in-memory threshold counters) is never
  persisted or restored; SQLite occurrence counts DO persist. The C# port should either wire
  `wms.save` state into the save JSON properly or accept the current semantics deliberately.
- WMS DB schema mismatch on load deletes and regenerates the DB (self-healing, `world_memory_system.py:661–680`).
- Save/restore of factions is metadata-only; the .db file is the real state (`save_manager.py:646` comment).

---

## 9. 3D Notes (what necessarily changes 2D→3D)

1. **Every boundary payload is 2D**: `position_x`/`position_y` (or `player_x`/`player_y`) floats in
   tile units flow through every event (`event_recorder.py:176–177`), chunk derivation is
   `int(pos)//16` (433–434), and geographic addresses resolve from 2D bounds rectangles
   (`geographic_registry.get_full_address`, called at 437–439). **Decision**: the IPC contract keeps
   2D ground-plane semantics. C# converts `Vector3(x, y, z)` → `(x, z)` before publishing (matches
   the standing `GamePosition` decision: Python `(x,y)` → Unity/Godot `(x,0,z)`). The sidecar never
   learns about height.
2. **Distance/proximity**: NPC interaction range (`npc.is_near(self.character.position)`,
   `game_engine.py:1669`) and gossip source positions (`GossipEvent.source_x/y`, npc_agent.py:48–50)
   are ground-plane distances. Keep them 2D; if vertical gameplay is added later, filter candidates
   engine-side before calling the sidecar.
3. **Default geography** (±800 world bounds, quadrant provinces, 16-tile localities,
   `world_memory_system.py:342–401`) assumes the 100×100 tile plane. World-map regeneration for a 3D
   terrain must still emit the same 6-tier 2D-bounds hierarchy or WMS address enrichment breaks.
4. **No camera/facing/hitbox coupling** exists in this subsystem — those live in Combat/rendering.
   The only "facing"-adjacent data is `direction` in `DODGE_PERFORMED` (bridge:253), a 2D tuple.
5. **F12 overlay** is screen-space UI — Godot Control; no 3D implications.

---

## 10. Godot Mapping + Proposed IPC Message Schema

### 10.1 C# / Godot structure

**Pure-logic assembly (`Game1.Core`, dotnet-testable, no Godot references)**:
- `GameEventBus` — direct port of event_bus.py (singleton, string topics, priority, wildcard, sync
  dispatch, swallow-and-log handler exceptions). ~1 day.
- `GameEvent` record `{ string EventType; Dictionary<string, object> Data; double Timestamp; string Source; }`.
- `StatTracker` — port the 65 `record_*` methods and `BuildDimensionalKeys`; back it with an
  `IStatSink` (`BufferedIpcStatSink` in prod, `InMemoryStatSink` in tests).
- `WorldSidecarProtocol` — DTOs + (de)serialization for every message below; `WesTopicFilter`
  mirroring `BUS_TO_MEMORY_TYPE` keys + `SKIP_BUS_EVENTS` so we only forward topics the sidecar uses.
- `PlacementSnapshot` DTO (discipline, grid dims, cell→materialId map, station tier) replacing the
  `interactive_ui` parameter of classifier/generator calls.
- `QuestRewardsDto`, `NpcDialogueResultDto`, `ClassifierResultDto`, `GeneratedItemDto`,
  `ArchivedQuestRecordDto`, `PipelineEventDto` — field-for-field with the dataclasses cited in §2.

**Engine glue (Godot project)**:
- `WorldSidecar` **autoload** (Node): spawns/monitors the Python process
  (`OS.CreateProcess`/`System.Diagnostics.Process`), owns the transport, restarts on crash
  (with `session.init` replay), exposes `Task<T> Request<T>(method, params, timeout, ct)` and
  `Notify(method, params)`; drains inbound sidecar events onto the main thread
  (mirrors `_poll_async_npc_dialogue` / `_check_background_generation` per-frame drains).
- `EventBridge` autoload: subscribes `"*"` on the C# bus at priority −10 (same as
  event_recorder.py:97), filters via `WesTopicFilter`, batches, ships `event.publish`.
- `WmsTick` in the game-loop node: sends `wms.update` at ~5 Hz (NOT per frame; see latency table).
- `ObservabilityOverlay` (Control + CanvasLayer): F12 toggle; pulls `observability.recent`.
- `InventOverlay` (Control): modal blocking overlay replacing `get_loading_state()` UI.

**Transport**: newline-delimited JSON (JSON-RPC 2.0 flavored) over stdio of the child process
(fallback: TCP on 127.0.0.1 for debugging with an externally-launched sidecar). Requests carry
`id`; notifications omit it; sidecar→game events are server-notifications. All floats are doubles;
positions are ground-plane `(x, y)` in tile units per §9.

**Envelope**:
```json
{"jsonrpc":"2.0", "id":123, "method":"...", "params":{...}}
{"jsonrpc":"2.0", "id":123, "result":{...}}
{"jsonrpc":"2.0", "id":123, "error":{"code":-32000, "message":"...", "data":{"degrade":{...}}}}
{"jsonrpc":"2.0", "method":"evt/...", "params":{...}}          // notification, either direction
```

### 10.2 Message catalog (one per boundary crossing)

**Session lifecycle** (replaces `_init_world_memory`, game_engine.py:5062–5283):

```jsonc
// game → sidecar, request, once at boot / world load. Latency budget: seconds OK (loading screen).
"session.init" {
  "save_dir": "C:/.../saves/slot1",
  "geo_map_path": ".../world_system/config/geographic-map.json",
  "game_root": null,                 // non-null only in hermetic/test mode (GAME1_HERMETIC)
  "hermetic": false,                 // ==> orchestrator subscribe_to_bus=false (game_engine.py:5170-5181)
  "character": {"name":"...", "level":1, "class_id":"...", "position":{"x":0,"y":0}},
  "world_chunks": [{"cx":0,"cy":0,"biome":"forest"}, ...],   // biome map for _generate_geography_from_world
  "npcs": [ /* register_npc records, see npc.register */ ],
  "game_time": 0.0
} -> {
  "session_id": "ab12cd34",
  "config_schema_issues": {"npc-personalities.json": ["..."]},   // validate_known_configs report
  "subsystems": {"wms":true,"wns":true,"wes":true,"factions":true,"npc_agent":true}
}
```

**Event stream** (replaces the wildcard bus subscription, event_recorder.py:97):

```jsonc
// game → sidecar, notification, batched per frame or per 50 ms. Fire-and-forget; loss on crash acceptable.
"event.publish" {
  "game_time": 1234.56,              // sidecar calls set_game_time with this (event_recorder.py:86-88)
  "events": [
    {"topic":"ENEMY_KILLED", "t_real": 1789683200.123, "source":"combat",
     "data":{"enemy_id":"wolf_3","killer_id":"player","position_x":42.0,"position_y":17.0,
             "tier":2,"is_boss":false,"loot":[...]}},
    ...
  ]
}
```
Only topics in the mirrored `BUS_TO_MEMORY_TYPE` allow-list are forwarded (32 topics, §6.1/§6.3);
visual topics are dropped client-side (cheaper than sidecar-side `SKIP_BUS_EVENTS`).

**WMS tick** (replaces `world_memory.update`, game_engine.py:8446):

```jsonc
// game → sidecar, notification, ~5 Hz (position sampling + ledger cadence tolerate this easily;
// today's per-frame call exists only because it's in-process).
"wms.update" {
  "dt": 0.2, "game_time": 1234.56,
  "player": {"x": 42.0, "y": 17.0, "health_pct": 0.85}
}
```
The sidecar runs its own drain/ledger/L3-7 logic on receipt — LLM stalls now cost sidecar time,
not frames.

**Stats** (replaces `StatTracker`→`StatStore` direct writes, stat_tracker.py:25):

```jsonc
// game → sidecar, notification, batched (flush every ~1 s or 200 entries; explicit flush on save).
"stats.record" {
  "entries": [
    {"op":"add",   "key":"gathering.collected.resource.iron_ore", "value":3.0},
    {"op":"count", "key":"gathering.actions.tier.2"},
    {"op":"max",   "key":"gathering.longest_streak", "value":17.0}
  ]
}
```
C# `StatTracker` keeps the 65 semantic `record_*` methods and `BuildDimensionalKeys` locally
(pure logic, unit-testable against golden key lists); only flat key ops cross the wire. Streaks /
session caches stay client-side exactly as today (stat_tracker.py:43–55).

**NPC agent**:

```jsonc
// game → sidecar, notification, at boot + whenever NPCs spawn (replaces register_npc, npc_agent.py:144)
"npc.register" {
  "npc_id":"blacksmith_gara", "npc_name":"Gara",
  "personality": { /* v3 inline personality verbatim or null */ },
  "template_name": "blacksmith",                    // fallback archetype (game_engine.py:1880-1893)
  "location_hierarchy": [["nation","stormguard"],["locality","hilltown"],["world",null]]
}

// game → sidecar, REQUEST, async with cancellation. Timeout 30 s (backend timeout).
// Tolerated latency: unbounded — deterministic speechbank line is shown immediately;
// LLM text swaps in when it lands, discarded on token supersede (game_engine.py:1788-1810).
"npc.dialogue.generate" {
  "token": 42,                                       // client-side supersede token
  "npc_id":"blacksmith_gara", "npc_name":"Gara",
  "player_input":"*approaches and greets you*",
  "character": {"name":"...","level":12,"class_id":"...","titles":[...],
                "equipped_summary":"iron sword, leather armor"}   // "visible state" subset
} -> {"text":"...", "emotion":"warm", "relationship_delta":1.5,
      "success":true, "from_fallback":false}
// Client rule (preserve exactly): if from_fallback==true, KEEP the speechbank line (1807-1810).

// game → sidecar, notification, on NL1-worthy dialogue exchanges (feeds WNS NL1 + WMS_DIALOGUE_CAPTURED)
"npc.dialogue.log" {"npc_id":"...", "player_line":"...", "npc_line":"...", "game_time": 1234.5}
```

**Quests** (replaces quest_reward_adapter + quest_tool + archive calls):

```jsonc
// game → sidecar, REQUEST at quest accept. TODAY THIS IS SYNCHRONOUS ON THE GAME THREAD
// (quest_system.py:326 → _call_with_task → backend.generate) — up to 30 s stall.
// Godot: async; quest is playable immediately with design rewards; pregen result attaches when it lands.
"quest.rewards.pregenerate" {
  "quest_def": { /* QuestDefinition asdict, source_origin=="generated" only */ },
  "character": { /* snapshot */ }
} -> {"rewards": {"experience":120,"gold":40,"health_restore":0,"mana_restore":0,
                  "skills":[],"items":[{"item_id":"...","qty":1}],"title":"",
                  "stat_points":0,"status_effects":[],"buffs":[]},
      "completion_dialogue": ["...","..."]}          // or error/null => keep design rewards

// game → sidecar, REQUEST at turn-in (same sync-today caveat, quest_system.py:527).
// Godot: bound it at ~2-3 s then fall back to pre-generated floor (the Python contract already
// defines the fallback chain: adapted ?? pre_generated ?? quest_def.rewards, quest_system.py:362-366).
"quest.rewards.adapt" {
  "quest": {"quest_def":{...}, "pre_generated_rewards":{...},
            "accepted_at":..., "turned_in_at":...},
  "character": {...}, "game_time_now": 1789683200.1
} -> {"rewards": {...}} | null

// game → sidecar, REQUEST (fast, SQLite-only — sub-ms server-side; treat as <50 ms).
// Replaces QuestGenerator.apply_turn_in (game_engine.py:1635-1640).
"quest.turn_in" {
  "player_id":"player", "giver_npc_id":"blacksmith_gara",
  "quest_id":"gather_iron_01", "game_time":1234.5,
  "explicit_deltas": null
} -> {"applied": {"guild:smiths": 4.0, "nation:stormguard": 2.0}}   // {} on failure

// game → sidecar, notification (replaces _archive_quest_record, quest_system.py:428-504)
"quest.archive" { /* ArchivedQuestRecord fields verbatim: quest_id, original_quest_def_json,
  time_started, time_completed, duration, actual_result, actual_rewards_granted,
  participating_npcs, participating_entities, archived_narrative_tags, wns_thread_id,
  archived_at_game_day */ }
```

**Faction reads** (new — game UI queries standing; today game code never reads FactionSystem
directly, but the C# UI will want it):

```jsonc
"faction.get_standing" {"player_id":"player", "tags":["guild:smiths"]} -> {"guild:smiths": 23.5}
// sidecar → game notification, forwarded from FACTION_AFFINITY_CHANGED / _CONSOLIDATED publishes:
"evt/faction.affinity_changed" {"scope":"player","tag":"guild:smiths","old":19.5,"new":23.5,"source":"quest_turn_in"}
```

**Content pipeline** (replaces database_reloader in-process dispatch — the key inversion):

```jsonc
// sidecar → game, notification, after ContentRegistry.commit() writes generated JSON files
// (content_registry.py:218-292). The C# side reloads its OWN database singletons from disk;
// the Python _RELOAD_TARGETS table (database_reloader.py:40-111) becomes a C# tool→loader map:
// materials→MaterialDatabase, hostiles→EnemyDatabase, nodes→ResourceNodeDatabase,
// skills→SkillDatabase, titles→TitleDatabase, npcs+quests→NPCDatabase, chunks→ChunkTemplateDatabase.
"evt/content.committed" {
  "plan_id":"plan_ab12", "tools":["chunks","hostiles"],
  "files":["Definitions.JSON/Chunk-templates-generated-3.JSON", "..."]
}
// game → sidecar ack (optional): reload success per class, mirrored to sidecar observability:
"content.reload_report" {"plan_id":"plan_ab12","results":{"ChunkTemplateDatabase":true,"EnemyDatabase":true}}
```

**Save / load**:

```jsonc
// game → sidecar, REQUEST, on save. Budget: <500 ms (SQLite flushes). Blocks the save spinner, not gameplay.
"save.flush" {} -> {
  "wms":   {"memory_db_path":"...","session_id":"...","game_time":1234.5,"trigger_state":{...}},
  "faction_state": {...},
  "content_registry_state": {"db_path":"...","stats":{...}}
}
// The returned blobs go into the save JSON under the same keys save_manager uses today
// (save_manager.py:77, 97-104) — and FIX the discarded-return bug (§8) for free.

// game → sidecar, REQUEST, on load (before session.init completes): pass the blobs back.
"session.restore" {"faction_state":{...}, "wms":{...}} -> {"ok":true}
```

**Observability / F12**:

```jsonc
// game → sidecar, REQUEST, on demand while overlay open (~4 Hz refresh is plenty).
"observability.recent" {"max_events": 15} -> {
  "events":[{"timestamp":1789683200.1,"event_type":"WNS_FIRED","message":"...","fields":{...}}],
  "counters":{"WNS_FIRED":12,"WES_DISPATCHED":4,"DB_RELOADED":4}
}
// sidecar → game notification for degrade visibility (replaces the graceful_degrade → ring-buffer bridge):
"evt/degrade" {"subsystem":"npc_agent","operation":"generate_dialogue","failure_reason":"...",
               "fallback_taken":"...","severity":"warning","context":{...}}
```

**Invented items + classifier** (replaces systems/llm_item_generator.py + crafting_classifier.py callers):

```jsonc
// game → sidecar, notification at crafting-UI open (replaces _preload_classifier, game_engine.py:4444-4482)
"invent.preload" {"discipline":"smithing"}
"invent.unload"  {"discipline": null}          // UI close; null = all

// game → sidecar, REQUEST. CNN inference after warmup: sub-second; first-call warmup can be
// seconds — hence preload. UI shows a "checking..." state; do not hard-block input beyond ~2 s.
"invent.validate" {
  "discipline":"smithing",
  "placement": {"grid_w":6,"grid_h":6,
                "cells":[{"x":1,"y":2,"material_id":"iron_ingot"}, ...],
                "station_tier":2}
} -> {"valid":true,"confidence":0.93,"probability":0.9312,"error":null}

// game → sidecar, REQUEST, long-running (Claude call, 30 s timeout + fallback item server-side).
// Client shows modal overlay; ESC sends invent.cancel; late results after cancel are dropped
// (mirrors abandoned-result semantics, game_engine.py:5303-5309).
"invent.generate" {
  "request_id":"g-17", "discipline":"alchemy",
  "placement":{...}, "narrative":"player-typed flavor text",
  "classifier_confidence":0.93
} -> {"success":true,"item_id":"inv_glimmer_draught","item_name":"Glimmer Draught",
      "item_data":{...},"recipe_inputs":[{"materialId":"...","qty":2}],
      "station_tier":2,"from_cache":false,"error":null}
"invent.cancel" {"request_id":"g-17"}
```

### 10.3 Sync/async + latency tolerance summary (as-measured from today's code)

| Crossing | Today | Tolerated latency | Godot mode |
|---|---|---|---|
| `event.publish` | sync in-process handler (priority −10) | fire-and-forget; ordering within batch matters (occurrence counters) | batched notification |
| `wms.update` | sync per frame (16 ms budget; known to stall seconds on L3-7 LLM, world_memory_system.py:509–532) | seconds (ledger/sampling cadence) | 5 Hz notification |
| `stats.record` | sync SQLite (buffered, periodic flush) | seconds | batched notification |
| NPC dialogue | worker thread + per-frame poll, 30 s timeout, instant speechbank fallback | unbounded (UI never waits) | async request + token supersede |
| Quest pregen/adapt | **synchronous on game thread** (up to 30 s freeze — pre-existing defect to fix in port) | pregen: unbounded (floor exists); adapt: ~2–3 s then floor | async request with deadline |
| Quest turn-in affinity | sync, SQLite-only, ms | <50 ms | request (await inline is fine) |
| Content commit → reload | in-process, sync at commit | seconds; next-chunk-load visibility is the real requirement | sidecar notification → C# reload |
| Save flush | sync at save | <500 ms under save spinner | request |
| F12 observability | direct singleton read per rendered frame | 250 ms staleness invisible | polled request or push stream |
| Classifier validate | sync (sub-second post-warmup) | ~1–2 s with UI feedback | request |
| Invent generate | background thread + input-blocking overlay + ESC cancel | 30 s + cancel | async request + cancel |

---

## 11. Port Complexity, Ordering, Risks

### Complexity

| Piece | Size | Why |
|---|---|---|
| C# `GameEventBus` + `GameEvent` | **S** | 194-line pure port; semantics fully specified |
| `WesTopicFilter` + payload DTOs | **S–M** | mechanical, but payload keys must match §6.1 exactly (the recorder's `_convert_event` key-probing at event_recorder.py:176–195 is the de-facto schema) |
| Sidecar process management (spawn/health/restart/replay) | **M–L** | crash-restart must replay `session.init` + `npc.register` set; decide what buffered events do during downtime (recommend: drop, log count) |
| Transport + request/response plumbing with cancellation | **M** | standard NDJSON-RPC |
| Python-side IPC server shim (translate messages → existing facades) | **M** | thin: `event.publish`→`bus.publish`, `wms.update`→`facade.update`, etc.; the internal bus keeps working untouched inside the sidecar |
| `StatTracker` port (65 methods + key builder + batching sink) | **M** | tedious; golden-file tests against Python key output strongly recommended |
| Quest reward async conversion | **M** | changes a currently-synchronous game flow; fallback chain already designed (quest_system.py:362–366) |
| PlacementSnapshot extraction (replacing `interactive_ui` coupling) | **M** | `extract_placement_data` (game_engine.py:4885) proves a serializable form exists; classifier server-side must rebuild image/features from it |
| Content-reload inversion (`_RELOAD_TARGETS` → C# map + generated-overlay globs in every C# loader) | **M** | touches 7 loader classes in other subsystems — cross-team contract |
| F12 overlay Control + observability polling | **S** | |
| Whole subsystem | **L** overall | (XL only if the sidecar shim is allowed to sprawl — keep it a translator, not a rewrite) |

### Ordering constraints

1. **C# GameEventBus first** — every other ported subsystem (combat, skills, inventory, quests)
   publishes into it; nothing else in this doc can be integration-tested without it.
2. **Sidecar transport + `session.init`** second (needs paths/PathManager equivalent + save-dir layout).
3. **`event.publish` + `wms.update` + `stats.record`** third — this makes WMS record real play and
   is pure fire-and-forget (lowest risk, highest coverage).
4. **NPC register/dialogue** fourth (needs NPC loader ported so personalities/speechbanks exist C#-side).
5. **Quest reward/turn-in/archive** fifth (needs C# quest system).
6. **Content commit → C# reload** sixth (needs all seven C# database loaders to exist AND support
   reload + generated-overlay globbing).
7. **Observability/F12 + save.flush** anytime after 2.
8. **invent.validate / invent.generate** independent of 3–6; needs crafting-UI port for the
   PlacementSnapshot source.

### Top risks / gotchas

1. **Payload shapes are convention, not schema.** The recorder probes multiple alternate keys
   (`position_x` vs `player_x`, `actor_id` vs `attacker_id` vs `killer_id` vs `entity_id`,
   `amount` vs `quantity` vs `value` vs `experience` — event_recorder.py:176–195). If C# publishers
   normalize keys "cleanly", WMS enrichment silently degrades (positions → 0,0 → wrong locality →
   wrong narratives). Mirror the exact key names from §6.1 or add a compatibility normalizer in the
   sidecar shim; write a round-trip test per topic.
2. **game_time semantics are unpinned.** WMS day boundary treats one day as `game_time/1.0`
   (daily_ledger.py:268–274) while quest archive uses `completed // 86400` on wall-clock
   (quest_system.py:502), and the engine's day-night cycle is 1440 s (game_engine.py:492–494).
   These are three different "days". The IPC envelope forces you to define `game_time` once —
   document the chosen unit and audit the three consumers.
3. **Synchronous LLM on the game thread today** (quest pregen at accept, adapt at turn-in,
   WMS L3-7 in `update`). The sidecar move fixes this by construction, but the C# quest flow must
   be redesigned to attach rewards asynchronously — do not faithfully port the blocking call.
4. **Reload inversion is a cross-subsystem contract.** Every C# database loader must (a) support
   in-place reload and (b) glob `*-generated-*.JSON` siblings exactly like Python
   (database_reloader.py:79–110; game_engine.py:169). Miss one and WES content silently never
   reaches gameplay — precisely the class of silent-fallthrough this project has been burned by.
5. **Dead/broken wiring — do not replicate**: (a) `EcosystemAgent` is never initialized by game
   code — its `RESOURCE_GATHERED` subscription and scarcity events are dead at runtime;
   (b) `FACTION_AFFINITY_CHANGED` is absent from `BUS_TO_MEMORY_TYPE`, so `FactionReputationEvaluator`
   is unreachable via the bus (§6.3); (c) `WorldMemorySystem.save()` return is discarded and
   `.load()` never called — `trigger_state` persistence is dead (§8); (d) `EVT_DATABASE_RELOADED`
   has no game-side subscriber (tests only).
6. **Singleton reset/lifecycle across process boundary.** Today `shutdown()` resets a dozen
   singletons in-process (world_memory_system.py:687–710). With a sidecar, "reset" = kill+respawn
   the process; make `session.init` fully idempotent and self-contained (it nearly is — it's the
   one entry point already).
7. **Ordering between `event.publish` and `quest.turn_in`/`stats`**: occurrence counters and
   threshold triggers are order-sensitive (thresholds fire at exact counts 1,3,5,10…,
   trigger_manager.py:23–26,142). Use one ordered stream (single connection, in-order dispatch) for
   all notifications; do not parallelize the notification channel.
8. **Sidecar crash while quest/dialogue requests are in flight**: every consumer already has a
   deterministic fallback (speechbank line, floor rewards, `{}` deltas) — preserve those exact
   fallback semantics in the C# client so a dead sidecar degrades to "static game", identical to
   today's `Init failed (non-fatal)` posture (game_engine.py:5092–5283).
9. **`ANTHROPIC_API_KEY` env handling** moves to the sidecar's environment (known live blocker:
   dead env var shadows `.env` — llm_item_generator.py:83). The Godot host must pass through /
   configure env for the child process explicitly on Windows.
