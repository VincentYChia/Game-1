# Repository Audit 2026-06-10 — Findings Ledger (working doc)

Accumulates **verified** findings from the six-area sweep. Every entry carries
primary code evidence + affirming doc reference per the project methodology.
This is a working document for the audit session; final outputs are
`REPOSITORY_MAP.md` + refreshed `SYSTEMS_CATALOG.md`. Archive this directory
when the audit closes.

Status codes: [BUG] clear bug to fix · [OPT] behavior-preserving optimization ·
[DOC] doc correction · [ORG] organization/catalog note · [ARCH] archive candidate ·
[DEAD] dead code/file

---

## Verified firsthand (main session)

### [BUG-1] Duplicate `_complete_minigame` — alloyQuality title bonus + debug-infinite silently dead
- **Code**: `core/game_engine.py:6299` (first def, DEAD — shadowed) vs `:8831` (second def, LIVE).
  Python class-body semantics: later def wins.
- v1 (dead) exclusively carried: `DEBUG_INFINITE_RESOURCES` material injection
  (6322-6330) and `alloy_quality_bonus` computation + pass-through (6332-6338).
- v2 (live) exclusively carries: adornments `target_item` pass (8866-8870),
  defensive missing-material warnings (8857-8862). Calls
  `craft_with_minigame(recipe_id, inv_dict, result)` — **no alloy bonus, defaults 0.0**.
- **Doc**: `Crafting-subdisciplines/refining.py:616` docstring documents the
  param; `progression/titles-1.JSON:127` grants `"alloyQuality": 0.25`;
  `data/databases/title_db.py:174` maps the key.
- **Fix**: merge — keep v2 as base, restore v1's debug block + alloy bonus
  (refining only), delete v1. Re-read both full bodies before merging.

### [ARCH-1] `Game-1/` and `Game-1-singular/` at repo root are pycache husks
- **Code**: `find` shows 0 non-pycache files in both. Untracked by git.
- **Doc**: git log — `c3047ef "Refactor monolithic main.py into modular architecture"`,
  `0dd1e98 "Move Game-1-singular to archive folder"`. CLAUDE.md directory layout
  omits both (correctly — they shouldn't exist).
- **Fix**: delete both directories (pure compiled-bytecode debris; history in git).

---

## From Agent 1 (core/entities/events/rendering/animation) — spot-verified items marked ✓

### [DOC-1] CLAUDE.md line counts stale across the board
- game_engine.py 11,888 actual vs 10,809 claimed; renderer.py 8,197 vs 7,931;
  rendering/ is 8 files / 9,751 LOC vs claimed 5 / 8,841 (terrain_renderer,
  visual_colors, map_cache, visual_effect_bridge unlisted). Fix in CLAUDE.md refresh.

### [DOC-2] "Effect dispatch table replaces 250-line if/elif chain" (CLAUDE.md) is aspirational
- `core/effect_executor.py:205-234` `_apply_special_mechanics` is an if/elif chain.
- Disposition: doc correction (don't refactor for elegance alone; LOW priority OPT).

### [OPT-1] Per-frame singleton fetches in game_engine render paths (~41 sites)
- `MaterialDatabase.get_instance()` etc. fetched inside per-frame render methods.
- Fix: cache refs on GameEngine in __init__. Zero behavior change.

### [OPT-2] `ImageCache.get_instance()` inside render loops
- `rendering/renderer.py:93,219,239,278-279,421-422,537+` — hoist outside loops
  (up to 81 calls/frame during smithing grid render).

### [OPT-3] Tag-def lookups per target per damage tag in effect executor
- `core/effect_executor.py:78-95` — pre-fetch `{tag: registry.get_definition(tag)}`
  before the target loop.

### [ORG-1] `core/testing.py` + `core/testing_difficulty_distribution.py` are dev tools living in core/
- testing.py IS used by game_engine (line ~16 import). Catalog as misplaced-but-wired.

### Minor (no action beyond catalog)
- effect_executor.py:52 `timestamp=0.0  # TODO` — context timestamp unused downstream.
- effect_executor.py:416-418 forward teleport unimplemented, graceful.

---

## All six agent reports received; high-impact claims verified firsthand

### VERIFIED BUGS (fix phase)
- **[BUG-2] `self.active_enemies` undefined** — combat_manager.py:649 (`_execute_aoe_attack`,
  reached via DEVASTATE buff) and :1051 (chain-damage enchant). Zero assignments anywhere
  (full-tree grep). 12 other sites use `get_all_active_enemies()` (def at :2309).
  Doc: MODULE_REFERENCE.md:1148 documents the attribute (intent). Fix: use the method;
  fix MODULE_REFERENCE. AoE + chain damage currently crash when reached.
- **[BUG-3] SkillDatabase boot double-load** — game_engine.py:157 calls `load_from_file()`
  no-arg (opens "" → caught exception, useless), then :172 loads skills-skills-1.JSON
  directly — bypassing `load_from_files()` (skill_db.py:59-87) whose documented purpose
  is the sacred+generated overlay. Fix: drop :157, switch :172 → `load_from_files()`.
- **[BUG-4] TitleDatabase boot bypasses generated glob** — game_engine.py:170 loads
  titles-1.JSON directly; `load_from_files()` (title_db.py:40-70) exists with the same
  documented overlay. WES-generated titles invisible until a reload. Fix: switch call.
- **[BUG-5] Placement case mismatch** — placement_db.py:29 requests
  `placements-smithing-1.JSON`; git-tracked file is `.json` (verified `git ls-files`).
  Works on Windows; silently loses smithing placements on Linux CI (build-game.yml
  builds Linux). Fix: lowercase the extension in the loader.
- **[BUG-6] Silent terminal parse fallbacks, no log_degrade** — llm_execution_planner.py
  `_parse_json_blob` terminal None (lines 72→82), llm_execution_hub.py (~45),
  llm_executor_tool.py (~64-75), llm_supervisor.py (~62-72), prompt_assembler.py `_load`
  (line 83). Violates graceful_degrade.py:19-20 own rule ("Silent try/except is not
  acceptable"). Fix: log_degrade at terminal fallbacks only (mid-retry fallthrough is fine).

### VERIFIED OPTIMIZATIONS (fix phase)
- **[OPT-4] Turret rescan per enemy per frame** — combat_manager.py:559-563 rebuilds the
  turret list inside the enemy update loop. Hoist to once per update() pass.
- **[OPT-5] sqrt in AoE radius check** — combat_manager.py:653; use squared distance
  (touching the function anyway for BUG-2).
- **[OPT-2] ImageCache.get_instance() inside render loops** — renderer.py multiple sites.
- **[OPT-3] Tag-def pre-fetch** — effect_executor.py:78-95.
- **[OPT-6] EventStore composite index** — add idx_events_type_locality_time
  (event_type, locality_id, game_time DESC) matching evaluator hot query.

### AGENT CLAIMS REJECTED ON VERIFICATION (do not act)
- "Layer 3 never publishes" — WRONG: layer3_manager.py:454 calls
  `_publish_layer_summary_created` (agent grep missed it). Model C peak path intact.
- "WES_REQUIRE_REAL_LLM doesn't block mock templates" — WRONG: chain strip at
  backend_manager.py:559-565 + visible-failure surfacing at :630-652. Agent conflated
  WES_DISABLE_FIXTURES with WES_REQUIRE_REAL_LLM.
- "recipe glob case-sensitivity bug" — WRONG: recipe_db.py:26-35 hardcodes exact
  filenames (incl. lowercase smithing-3.json/adornments-1.json), no glob involved.
- "quest_archive_db.py never imported" — WRONG: function-level import + use at
  quest_system.py:441/504 (+ tests). Agent only scanned top-level imports.

### KEY DOC CORRECTIONS QUEUED (map/catalog phase)
- CLAUDE.md "100+ skills" → 30 base + 5 fishing (Update-2) = 35 actual
  (skills-skills-1.JSON metadata totalSkills: 30).
- "100+ recipes" → 167 actual (53 smithing + 18 alchemy + 55 refining + 16 engineering
  + 25 adornments).
- Materials: 57 in items-materials-1.JSON (file metadata) but ~77 total loaded into
  MaterialDatabase incl. refining/consumables/devices — clarify both numbers.
- "33 evaluators" → 36 registered (interpreter.py) — 3 added 2026-06-05 (fishing,
  turret, chest_loot). WORLD_MEMORY_SYSTEM.md:653 same fix.
- Tag taxonomy: 64 categories in code vs 65 in TAG_LIBRARY.md. L6 has `regional_effect`
  where doc says `nation_effect` — tags are LOAD-BEARING (memory rule): fix DOCS to match
  code, note the semantic wart; do NOT rename the code key.
- LOC drift: game_engine 11,888 (doc 10,809); renderer 8,197 (7,931); rendering/ 8 files
  9,751 LOC (doc 5 files 8,841); combat_manager 2,070 (2,317); BackendManager 708 (553);
  alchemy 906 (1,070); crafting_simulator 1,928 (2,337); smithing 776 (909).
- Python file count: 434 total incl. tests/tools (doc says 239).
- PLAYTEST_README: 5 → 6 crafting disciplines (fishing missing).
- README.md world_system: 71 files → 87+.
- MODULE_REFERENCE.md:1148 — `active_enemies` attribute doesn't exist (method does).
- CLAUDE.md "Effect dispatch table replaces if/elif" — aspirational; actual code is
  if/elif (effect_executor.py:205-234).

### ORPHAN CONTENT JSONs (catalog-only; content JSON is sacred — designer review)
- items.JSON/items-testing-integration.JSON (Update-1 has its own loaded copy)
- recipes.JSON/recipes-tag-tests.JSON (15 test recipes, never loaded)
- Skills/skills-testing-integration.JSON (doesn't match any loader glob)
- placements.JSON/placements-smithing-1-pre-fish.JSON (pre-Update-2 backup)
- Definitions.JSON/value-translation-table-1.JSON, templates-crafting-1.JSON (no loader refs)
- Update-1/npcs-village-dummy.JSON (update_loader has no NPC scanner)

### LATENT RISK (catalog as known limitation, not fixed now)
- SkillDatabase/TitleDatabase `reload()` (WES commit path) clears + reloads sacred+generated
  but does NOT re-merge Update-N files — a WES skill/title commit mid-session would drop
  Update-2 fishing skills/titles until restart. Pre-existing; affects reload path only.

### DOC ARCHIVE CANDIDATES (archive pass)
- docs/REPOSITORY_STATUS_REPORT_2026-01-27.md → superseded by SYSTEMS_CATALOG.md
- docs/INTERN_DOCUMENTATION_CLEANUP_PLAN.md → plan executed 2026-04-24
- docs/json-reference/JSON_EXPLORATION_REPORT.md → historical snapshot
- Stale-flag (not archive): FISHING_EXPANSION_PLAN.md, TOOL_CONTRACT_AUDIT.md,
  WMS_TOOLS_AND_SIMULATION.md (61-category + future-L6/7 claims),
  POLITICAL_AND_WMS_USAGE_PLAN.md (references implemented work as future),
  SHARED_INFRASTRUCTURE.md (BalanceValidator spec-only header)
- DO NOT touch DESIGNER_LEDGER.md (active user walkthrough) or
  PLACEHOLDER_FURNISHING_WORKSHEET.md (furnishing not done).
- tools/prompt_editor.py — superseded by prompt_studio; catalog only (code stays put).


---

## Gap-closure pass (owner asked "did you actually cover everything?")

Honest gaps identified and closed where cheap:

### [BUG-7] Game1.spec bundled the WRONG ML directory + missing runtime data — FIXED
- **Code**: spec bundled `Convolution Neural Network (CNN)` + `Simple Classifiers
  (LightGBM)` (training dirs — only a code COMMENT references them) while
  `crafting_classifier.py:1010-1030` loads from `crafting_classifier_models/{discipline}/`
  — absent from the bundle. Also missing: `Update-1/`, `Update-2/`,
  `updates_manifest.json` (packaged builds lost fishing content), and
  `world_system/config/` (Living World booted fully degraded in packaged builds).
- **Doc**: docs/PACKAGING.md + PLAYTEST_README.md document packaged builds as a
  supported distribution channel; CI builds them (build-game.yml).
- **Fix**: spec datas corrected. NOT yet verified with an actual PyInstaller build —
  flagged as a follow-up before the next binary playtest.

### Verified clean (paths the audit had not traced)
- CNN/LightGBM model files exist for all 5 disciplines at the exact paths the
  classifier expects (`smithing_best.keras`, `adornment_best.keras`,
  `{alchemy,refining,engineering}_model.txt`). `alchemy_extractor.pkl` confirmed
  absent — the existing known-limitation (inline extractor workaround) stands.
- Fewshot prompts present where `llm_item_generator.py:362-387` loads them
  (system_*.txt + few_shot_examples.json).
- `.claude/` contains INDEX.md + NAMING_CONVENTIONS.md (as CLAUDE.md claims) plus
  an uncataloged `FACTION_SYSTEM_CORRECTIONS_AND_ROADMAP.md` (not reviewed).
- `assets/*.py` = 5 dev one-off scripts (icon-selector, scan_generated_icons,
  remove-1_from_PNG, Vheer-automation, broken_vheer_automation — the last is
  self-flagged dead by its filename). No runtime imports.
- `tools/prompt_editor.py` imports are stdlib+tkinter only — it RUNS; superseded
  by Prompt Studio, not broken.

### Acknowledged remaining gaps (not closed — would need dedicated passes)
1. Entry-level JSON cross-reference validation (does every recipe input name an
   existing material, every skill-unlock a real skill, etc.) — file-level orphan
   check done; entry-level xref NOT done.
2. `Scaled JSON Development/` training scripts (~15 .py: trainers, validators,
   ollama/together adapters) — inventoried, not audited.
3. The god-classes were sampled, not read line-by-line (20K LOC combined).
4. Several `Definitions.JSON` configs marked CONDITIONAL without tracing each
   consumer (dungeon-config, fishing-config, village-config, combat-config,
   stats-calculations, world_generation).
5. Packaged-build smoke test of the corrected spec.
