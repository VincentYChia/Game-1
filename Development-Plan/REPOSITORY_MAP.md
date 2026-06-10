# Game-1 Repository Map

**Created**: 2026-06-10 (full-repository audit — six parallel area sweeps + firsthand verification)
**Answers**: "WHERE is X, and is it load-bearing?" — for "DOES X work?" see [SYSTEMS_CATALOG.md](SYSTEMS_CATALOG.md).
**Audit evidence**: [repo-audit-2026-06-10/FINDINGS_LEDGER.md](repo-audit-2026-06-10/FINDINGS_LEDGER.md)

**Hard numbers (verified 2026-06-10)**: 434 Python files / ~159,800 LOC (including tests + tools; "game code only" is ~290 files), ~113 game-definition JSONs across content dirs, 1,085 passing tests (10 known failures: geometry_patterns ×8, status_effects ×1, tag_system ×1).

> Older docs cite "239 Python files / ~96,400 LOC" — that was a pre-tools/tests count from March 2026. Use the numbers above.

---

## Repo root

| Path | What it is | Status |
|---|---|---|
| `Game-1-modular/` | **The game.** Everything live is here. | ACTIVE |
| `Development-Plan/` | Active roadmap + canonical design docs (SYSTEMS_CATALOG, WORLD_SYSTEM_WORKING_DOC, WMS_WNS_LAYER_CORRESPONDENCE, this map) | ACTIVE |
| `Scaled JSON Development/` | ML training data + trained CNN/LightGBM models + LLM fewshot templates (67 MB) | REFERENCE (used at runtime for classifier model loads) |
| `archive/` | Superseded docs, paused Unity migration plan, 2026-04-24 consolidation | HISTORICAL |
| `Python/`, `Unity/` | Pointer READMEs only (Python → Game-1-modular; Unity = paused migration placeholder) | POINTERS |
| `llm_debug_logs/` | Runtime LLM call logs (`wes_<session>.jsonl`, graceful_degrade/) | RUNTIME OUTPUT (gitignored) |
| ~~`Game-1/`, `Game-1-singular/`~~ | Deleted 2026-06-10 — were untracked `__pycache__` husks left by the Nov 2025 refactor | REMOVED |

---

## Game-1-modular/ — source tree

### Core gameplay (the 60fps loop)

| Directory | Files / LOC | What lives here | Notes |
|---|---|---|---|
| `core/` | 20 + `geometry/` (3) / ~19,900 | `game_engine.py` (**11.7K LOC god-class** — main loop, input, UI dispatch, boot wiring), `effect_executor.py` (tag-based combat effects), `difficulty_calculator.py` / `reward_calculator.py` (crafting math), `tag_system.py` + `tag_parser.py` + `crafting_tag_processor.py` (tag registry/parsing), `interactive_crafting.py`, `minigame_effects.py`, `config.py`, `paths.py`, `camera.py` | `testing.py` + `testing_difficulty_distribution.py` are dev tools living in core/ (testing.py IS imported by game_engine). The "effect dispatch table" in CLAUDE.md is aspirational — `_apply_special_mechanics` is an if/elif chain (works fine). |
| `entities/` | 6 + `components/` (11) / ~7,450 | `character.py` (2.6K — player entity), `status_effect.py`, `status_manager.py`; components: `stat_tracker.py` (65 record_* → SQL), `skill_manager.py`, `inventory.py`, `equipment_manager.py`, `stats.py`, `buffs.py`, `leveling.py`, `crafted_stats.py`, `weapon_tag_calculator.py`, `activity_tracker.py` | Component pattern — Character composes these. |
| `Combat/` | 11 / ~5,500 | `combat_manager.py` (2.1K — damage pipeline, enchantments, spawning), `enemy.py` (Enemy + EnemyDatabase), `attack_state_machine.py`, `hitbox_system.py`, `projectile_system.py`, `attack_profile_generator.py`, `combat_data_loader.py`, `player_actions.py`, `screen_effects.py` | Capitalized package name (`from Combat import ...`) — sole PascalCase package; functional, just inconsistent. Enemy storage is per-chunk: `enemies: Dict[(cx,cy), List[Enemy]]`; flatten via `get_all_active_enemies()`. |
| `Crafting-subdisciplines/` | 9 / ~7,500 | One minigame + crafter pair per discipline: `smithing.py`, `alchemy.py`, `refining.py`, `engineering.py`, `enchanting.py`, `fishing.py`; plus `crafting_simulator.py` (1.9K) and `rarity_utils.py` (shared rarity singleton) | Known tech debt: `can_craft`/`load_recipes`/`get_all_recipes` near-identical across 5 crafter classes (~150-200 dup lines, no base class). Fishing enters via resource interaction in game_engine, not the craft UI. |
| `rendering/` | 8 / ~9,750 | `renderer.py` (**8.2K LOC god-class** — all drawing), `terrain_renderer.py`, `visual_effects.py`, `visual_effect_bridge.py`, `image_cache.py`, `map_cache.py`, `visual_colors.py` | Older docs say "5 files / 8,841 LOC" — three newer files were never added to the docs. |
| `animation/` | 7 / ~1,020 | `animation_manager.py` (singleton), `sprite_animation.py`, `animation_data.py`, `procedural.py`, `combat_particles.py`, `weapon_visuals.py` | Wired into game_engine + renderer. |
| `events/` | 2 / ~200 | `event_bus.py` — GameEventBus pub/sub, the spine connecting gameplay → WMS | ~60 event types. Handlers swallow exceptions by design. |
| `systems/` | 22 + `geography/` (13) / ~13,400 | `world_system.py` (1.3K — chunks, generation), `quest_system.py`, `quest_log_overlay.py` (J-key UI), `save_manager.py`, `dungeon.py`, `collision_system.py`, `map_waypoint_system.py`, `turret_system.py`, `npc_system.py`, `crafting_classifier.py` (CNN/LightGBM), `llm_item_generator.py` (invented items via Claude), `biome_generator.py`, `chunk.py`, `natural_resource.py`, `potion_system.py`, `encyclopedia.py`, `title_system.py`, `class_system.py`, `skill_unlock_system.py`, `training_dummy.py`; geography/: world/nation/region/village/political generators + name_generator + noise | All wired — no orphans found in this tree. |

### Data layer

| Directory | Files | What lives here | Notes |
|---|---|---|---|
| `data/models/` | 13 | Pure dataclasses: materials, equipment, skills, recipes, world/Position, titles, classes, npcs (v3 schema), quests, resources, skill_unlocks, unlock_conditions | `npcs.py` docstring is the canonical v3 static-vs-dynamic split rationale. |
| `data/databases/` | 18 | Singleton loaders: material, equipment, recipe, skill, title, class, npc (+quests), placement, translation, skill_unlock, resource_node, chunk_template, world_generation, quest_archive, map_waypoint, visual_config, update_loader | All `get_instance()` singletons (pattern duplicated ~16× — accepted debt). `load_from_files()` (sacred glob + `*-generated-*` overlay) is the canonical boot call for skill/title/chunk DBs as of 2026-06-10. All JSON opens are `encoding='utf-8'` as of 2026-06-10. |

### Content JSON (sacred — never modified by code work)

| Directory | Loaded by | Orphans (nothing loads them) |
|---|---|---|
| `items.JSON/` (8 files) | material_db (SACRED_LOAD_SEQUENCE) + equipment_db | `items-testing-integration.JSON` (Update-1 carries its own loaded copy) |
| `recipes.JSON/` (6 + archive/) | recipe_db — 167 recipes total (53 smithing / 18 alchemy / 55 refining / 16 engineering / 25 adornments) | `recipes-tag-tests.JSON` (15 test recipes) |
| `placements.JSON/` (6 files) | placement_db — 193 templates | `placements-smithing-1-pre-fish.JSON` (pre-Update-2 backup). NOTE: live smithing file is lowercase `.json`. |
| `progression/` (7 files) | class_db (6 classes), title_db (**10** base titles, not "40+"), npc_db (v3 preferred: npcs-3 / quests-3, v2 fallback) | none |
| `Skills/` (3 files) | skill_db (**30** base skills, not "100+"), translation_db (base effects) | `skills-testing-integration.JSON` |
| `Definitions.JSON/` (17 files) | resource_node_db, translation_db, tag_system, enemy/combat/dungeon/fishing/village/world-gen/map/visual config loaders | `value-translation-table-1.JSON`, `templates-crafting-1.JSON` (likely dead — designer review) |
| `Update-1/`, `Update-2/` | update_loader via `updates_manifest.json` (auto at boot). Update-2 adds 5 fishing skills + 4 fishing titles + stations | `Update-1/npcs-village-dummy.JSON` (update_loader has no NPC scanner) |

**Real loaded totals** (verified): 167 recipes · 35 skills (30+5) · ~14 titles (10+4) · 6 classes · 57 base materials (77 entries in MaterialDatabase incl. refining/consumables/devices) · 193 placements.

**Latent reload risk**: SkillDatabase/TitleDatabase `reload()` (WES-commit path) re-reads sacred+generated but does NOT re-merge Update-N files — a mid-session WES skill/title commit drops fishing skills/titles until restart. Catalogued, not yet fixed.

### World System (WMS / WNS / WES / Living World)

| Directory | Files / LOC | What lives here | Notes |
|---|---|---|---|
| `world_system/world_memory/` | 40 + evaluators (38) + consolidators (5) / ~20K | 7-layer event memory: `event_store.py` (23 SQL tables), `event_recorder.py` (bus→SQLite), `stat_store.py`, `trigger_manager.py` (dual-track thresholds), `interpreter.py` (**36 registered evaluators**, not 33), layer3-7 managers + summarizers (all publish `WMS_LAYER_N_SUMMARY_CREATED` via `layer_publish.py`), `tag_library.py` (**64 categories**, not 65), `layer_store.py`, `geographic_registry.py`, `query.py`, `daily_ledger.py`, retention/position_sampler/time_envelope | L6 category `regional_effect` is semantically `nation_effect` — code name kept (tags are load-bearing); docs note the wart. |
| `world_system/wns/` | 21 / ~6,300 | Narrative weaving: `nl_weaver.py`, `world_narrative_system.py`, `wms_to_wns_bridge.py` (cascade + L3-L7 peak-path subscriptions), `cascade_trigger.py`, `wms_context_builder.py` (cascade-down reads), `behavior_interpreter.py`, `nl1_ingestor.py`, `narrative_store.py`, `affinity_resolver.py`, parsers, `presence_drift_detector.py`, `mixed_trigger_arbiter.py` | Model C (2026-06-05) wired and verified. |
| `world_system/wes/` | 19 + `llm_tiers/` (7) / ~7,100 | Content executor: `wes_orchestrator.py`, `plan_dispatcher.py`, `request_layer.py` (single-step orphan resolution), `tool_registry.py`, `observability_runtime.py` + `observability_overlay.py` (F12), `metrics.py`, `xml_batch_parser.py`, `quest_reward_adapter.py`; llm_tiers: planner / hub / executor_tool / supervisor + `prompt_assembler.py` | All terminal parse failures log via `log_parse_failure` as of 2026-06-10. |
| `world_system/living_world/` | backends (3) + npc (3) + factions (11) + ecosystem (2) + infra (6) | `backend_manager.py` (708 LOC — Claude-only chain, `WES_REQUIRE_REAL_LLM` strip verified real), `llm_dev_log.py`, `npc_agent.py` + `npc_memory.py` (v3 inline personalities), `faction_system.py` (SQLite affinity) + dialogue_helper/quest_tool/consolidator, `graceful_degrade.py` (CC3 logging contract + F12 bridge), `context_bundle.py`, `llm_fixtures/` (32 registered fixtures) | **`ecosystem/ecosystem_agent.py` (398 LOC) is the one confirmed orphan** — imported nowhere; owner disposition "leave as-is (unused)". factions/ keeps 4 inline phase-test files + 4 .md docs (pedagogical; left in place). |
| `world_system/content_registry/` | 8 + tests (9) / ~2,700 | `content_registry.py` (stage/commit facade), `registry_store.py` (SQLite), `xref_rules.py`, `database_reloader.py`, `generated_file_writer.py`, `orphan_detector.py`, `balance_validator_stub.py` | Constructed at game boot; chunks E2E covered. |
| `world_system/config/` | 48 JSONs + `schema_validator.py` | backend/memory/narrative/faction/geographic configs; prompt_fragments_* (33 LLM task prompts); narrative_fragments_nl2-7; tag-registry | 4 designer-prone configs schema-validated at boot (2026-06-09). |
| `world_system/docs/` | 7 + archive (7) | WORLD_MEMORY_SYSTEM.md (canonical WMS design), HANDOFF_STATUS.md, TAG_LIBRARY.md, ARCHITECTURAL_DECISIONS.md, POLITICAL_AND_WMS_USAGE_PLAN.md, WMS_TOOLS_AND_SIMULATION.md | Stale-flags added 2026-06-10 to the last two (they predate L6/L7 completion). |

### Tests, tools, assets, docs

| Directory | What lives here | Notes |
|---|---|---|
| `tests/` (29 files) + `tests/crafting/` (7) + `tests/save/` (3) | Central pytest suite — 1,085 passing | Known failures: geometry_patterns (8), status_effects::test_buff_effects, tag_system::test_equipment_loading. `tests/crafting/test_fixes.py` errors at collection (relative path opened at import). `test_interactive_crafting.py` at repo root is a script-style tester, not pytest. Additional inline tests live in wns/tests, wes/tests, content_registry/tests, living_world/(tests|factions|backends). |
| `tools/` (15 + prompt_studio/ 5) | `prompt_studio_main.py` (designer prompt editor — supersedes `prompt_editor.py`), `wes_real_llm_smoketest.py` (pre-playtest CLI), `simulate_world_memory.py`, `update_manager.py` + `deploy_update.py` + `update_catalog.py` (Update-N), grid/pattern designers, icon tooling, `tag_collector.py`, `stat_catalog.py` | `prompt_editor.py` superseded by Prompt Studio — kept in place (code stays put), don't extend it. |
| `assets/` | 3,749 icon/sprite PNGs + icon pipeline docs | Sacred for visual-overhaul rules: icon PNGs not animation sprites. |
| `docs/` (25 files + tag-system/ 8 + json-reference/) | GAME_MECHANICS_V6.md (master mechanics reference), MODULE_REFERENCE.md, DEVELOPMENT_GUIDE, DEVELOPER_GUIDE_JSON_INTEGRATION, UPDATE_N_SYSTEM, NAMING_CONVENTIONS, PACKAGING, KNOWN_LIMITATIONS, HARDCODED_SYSTEMS, INTERACTIVE_CRAFTING_*, tag-system/TAG-GUIDE et al. | REPOSITORY_STATUS_REPORT_2026-01-27 and INTERN_DOCUMENTATION_CLEANUP_PLAN archived 2026-06-10 (superseded). |
| `save_system/` | Save docs + `create_default_save.py` (v2.0 schema) | Current. |
| `saves/`, `llm_debug_logs/`, `__pycache__/` | Runtime output | Gitignored. |
| Root files | `main.py` (entry), `verify_imports.py`, `Game1.spec` + `build.bat/sh` (PyInstaller), `requirements*.txt` (aligned with imports), README/HOW_TO_RUN/PLAYTEST_README, MASTER_ISSUE_TRACKER | CI: `.github/workflows/build-game.yml` (Win/Linux/macOS) — paths verified valid. |

---

## Development-Plan/ — canonical docs (read these first)

| Doc | Role |
|---|---|
| **SYSTEMS_CATALOG.md** | "Does X work?" — single status baseline, ~120 systems |
| **REPOSITORY_MAP.md** (this file) | "Where is X?" — directory truth |
| **WORLD_SYSTEM_WORKING_DOC.md** (v4 + Model C amendment) | WNS/WES canonical spec |
| **WMS_WNS_LAYER_CORRESPONDENCE.md** | Layer-flow design (Model C) — read before touching layer code |
| **CONTROLS_MAP.md** | Every tunable design knob, §1-§17 |
| **PLACEHOLDER_LEDGER.md** + PLACEHOLDER_FURNISHING_WORKSHEET.md | Designer furnishing list (active) |
| **DESIGNER_LEDGER.md** | Designer walkthrough doc (active with owner) |
| OVERVIEW / PART_1 / PART_2 / PART_3 | Roadmap (P1.7 visual overhaul + P3 are the open fronts) |
| SHARED_INFRASTRUCTURE.md | BalanceValidator spec — **spec only, no code** |
| feature-traces/ (11 docs) | 2026-04 trace pass — stale-flagged where superseded |
| repo-audit-2026-06-10/ | This audit's evidence ledger |

---

## Known naming/organization warts (catalogued, intentionally not "fixed")

1. `Combat/`, `Crafting-subdisciplines/`, `Skills/`, `Update-N/` are capitalized/hyphenated; everything else lowercase. Renaming breaks imports/paths for zero functional gain.
2. Mixed `.JSON`/`.json` extensions in content dirs. Loaders now reference exact tracked case.
3. Test files split between central `tests/` and in-package `*/tests/` + 4 inline faction phase tests. The in-package ones document implementation narratives; pytest collects all.
4. `core/testing.py` is a dev tool wired into game_engine; `core/testing_difficulty_distribution.py` is standalone.
5. The two god-classes (game_engine 11.7K, renderer 8.2K) are the dominant regression risk — extend via new modules, never restructure casually (CLAUDE.md sacred rule).

**Maintenance**: update this map when adding a directory or moving docs; update SYSTEMS_CATALOG when a system's status changes. Counts here were verified 2026-06-10 — re-verify before quoting elsewhere.
