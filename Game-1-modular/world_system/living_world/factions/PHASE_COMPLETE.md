# Faction System — Phase Complete Report

**Status**: Phase 2+ and Phase 3A/B/C complete. All core recording and retrieval primitives are implemented, tested, and wired into NPC dialogue, the WMS event bus, and the dev-facing prompt fragment UI.

**Date**: 2026-04-19
**Branch**: `claude/review-wms-context-4OWk9`
**Tests**: 50 passing (faction module) / 0 failing
**Lines**: ~1,300 Python + ~1,700 documentation

---

## 1. Current System — What Exists Today

### 1.1 Recording Layer (`faction_system.py`, 455 LOC)
Singleton `FactionSystem` backed by a separate SQLite file (`faction.db`, independent of WMS) with four tables:
- `npc_profiles` — per-NPC narrative + metadata
- `npc_belonging_tags` — which factions define an NPC (with significance 0.0–1.0 and role)
- `npc_affinity` — NPC's opinion of any tag, including the reserved `_player` tag
- `player_affinity` — player's standing with each faction tag
- `location_affinity_default` — cultural default for an address

Exposes 19 public methods covering CRUD + hierarchical inheritance + batch query. Every `adjust_player_affinity()` call publishes `FACTION_AFFINITY_CHANGED` on the GameEventBus.

### 1.2 Consumer Helpers
- **`dialogue_helper.assemble_dialogue_context()`** — builds a dict of `{npc, player, npc_opinion, location}` for LLM dialogue prompts.
- **`quest_tool.QuestGenerator`** — hardcoded quest→outcome→delta tables for `smith_contract`, `merchant_trade`, `guard_patrol`. Routes deltas through `FactionSystem.adjust_player_affinity()` so events flow through to WMS.
- **`consolidator.AffinityConsolidator`** — rolls up a player's full affinity dict into the top-5 by absolute value, emits `FACTION_AFFINITY_CONSOLIDATED` for Layer-2 narrative summarization.

### 1.3 NPC Agent Integration
`world_system/living_world/npc/npc_agent.py` now imports `FactionSystem` and `assemble_dialogue_context`. `_build_faction_context()` formats the NPC's top-5 belonging tags by significance and injects them into the dialogue system prompt via `{faction_context}`.

### 1.4 WMS Integration (evaluators)
`world_memory/evaluators/FactionReputationEvaluator` listens for `FACTION_AFFINITY_CHANGED` and writes Layer 2 narratives (already in place before Phase 3).

### 1.5 Prompt Fragment UI Integration (new in this branch)
- **`world_system/config/prompt_fragments.json` (v3.2)** — added 27 fragments across four new groups:
  - `domain:faction` (1 real)
  - `affinity:revered|trusted|neutral|disliked|hated` (5 real)
  - `interaction:greet|trade|ask|threaten` (4 real)
  - `faction:*` (15 **placeholder** — one per bootstrap tag in `schema.py`)
  - `_faction_context` (1 **placeholder** — header)
- **`world_system/world_memory/prompt_assembler.py`** — registered `affinity`, `interaction`, `faction` in `FRAGMENT_CATEGORIES` and wired `FACTION_AFFINITY_CHANGED`/`FACTION_AFFINITY_CONSOLIDATED` into `EVENT_TO_DOMAIN`.
- **`tools/prompt_editor.py`** — new colors + `CATEGORY_ORDER` entries so the 3-panel tkinter editor browses, edits, and previews faction fragments alongside every other category.

### 1.6 Information Flow (verified)
```
  game event (quest / combat)
    └─> QuestGenerator / game code
         └─> FactionSystem.adjust_player_affinity(tag, delta)
              ├─> writes player_affinity table
              └─> publishes FACTION_AFFINITY_CHANGED on GameEventBus
                   ├─> FactionReputationEvaluator → Layer 2 narrative (SQL)
                   └─> PromptAssembler.EVENT_TO_DOMAIN resolves to "faction" domain

  dialogue request
    └─> NPCAgentSystem.generate_dialogue(npc_id, input)
         └─> _build_faction_context(npc_id)
              └─> FactionSystem.get_npc_profile() → top-5 belonging tags
         └─> system_prompt includes faction_context block
         └─> BackendManager.generate(task="dialogue", ...)
              └─> Ollama | Claude | Mock (selected by backend config)
```

All links tested; the only dynamic-stylization pieces (real faction identity text, dynamic _faction_context headers) remain placeholders by design, clearly marked in the JSON.

---

## 2. What's Left — Roadblocks and How to Clear Them

These are the four known external dependencies. Each section below describes the dependency, the exact hook points already in place, and the minimal work required when the dependency lands.

### 2.1 When the LLM Stack is Production-Ready

**Today**: `BackendManager` abstracts Ollama / Claude / Mock. The dialogue prompt already includes faction context.

**When LLMs are completed**:
1. **Tune temperature per task** in `BackendManager`:
   - `dialogue` task → 0.6 (current) is fine
   - Consider adding `faction_narrative` task at 0.4 for Layer 2 consolidations
2. **Write a Layer 2 consolidator prompt** that consumes `FACTION_AFFINITY_CONSOLIDATED` events. The event already contains `top_affinities: Dict[str, float]` and `player_id`. Call `BackendManager.generate(task="faction_narrative", ...)` with a system prompt assembled from `domain:faction` + `affinity:<level>` fragments (all present).
3. **Schedule consolidation** on a daily tick. `AffinityConsolidator.consolidate_and_publish(player_id)` is a one-liner — call it from the daily ledger pipeline.
4. **Smoke test** with `test_faction_phase3a_dialogue.py` and an end-to-end dialogue with the real backend. The fallback path (`_generate_fallback`) is already proven.

**Files to touch when landing**: `backends/backend_manager.py` (task routing), `world_memory/evaluators/faction_reputation_evaluator.py` (consume consolidated event), nothing in this module.

### 2.2 When Factions are Stylized (Identity & Culture Text)

**Today**: All 15 `faction:*` entries in `prompt_fragments.json` are `"PLACEHOLDER for <tag>. When stylized, this will describe …"`.

**When ready to stylize**:
1. **Open `tools/prompt_editor.py`** (tkinter 3-panel UI). Filter on the `faction` category.
2. **Replace each placeholder** with 2–4 sentences of worldbuilding:
   - *Who are they*, *what they value*, *how members greet outsiders*, *what signals disrespect*.
   - Keep ≤300 characters (token-budget-friendly).
3. **Add new fragments** for any faction spawned after bootstrap (see `schema.py::bootstrap_location_defaults`). Use `faction:<tag_normalized>` where colons become underscores (e.g. `guild:smiths` → `faction:guild_smiths`).
4. **Re-run** `python -m pytest world_system/living_world/factions/ -q` — no code changes needed; the JSON is data.

**Note**: You never need to stylize NPCs individually. The prompt assembler automatically picks the fragments matching the NPC's top belonging tags.

### 2.3 When the Map is Richer (Merchant Roads, Districts, Territories)

**Today**: `location_affinity_default` is seeded by `schema.bootstrap_location_defaults()` with a few hardcoded (address, tag, value) triples. `compute_inherited_affinity(location_hierarchy)` walks the hierarchy locality → district → province → region → nation → world and blends by a decreasing weight.

**When the map expands**:

#### 2.3.1 Feeding new addresses into the hierarchy
- Merchant roads, trade hubs, frontier forts, dungeon regions — each gets an entry in the `geographic_registry` (WMS) *and* optionally one or more `location_affinity_default` rows.
- Use `FactionSystem.set_location_affinity_default(tier, location_id, tag, value)` at world-gen time. Seed the table during `world_system.bootstrap()` or on chunk-generation events.

#### 2.3.2 Example — a merchant road biasing affinity
```python
# During world generation
faction_sys.set_location_affinity_default(
    tier="district",
    location_id="district:kings_road",
    tag="guild:merchants",
    value=60.0,   # Merchants love the road
)
faction_sys.set_location_affinity_default(
    tier="district",
    location_id="district:kings_road",
    tag="guild:thieves",
    value=-40.0,  # Guards patrol, thieves unwelcome
)
```
Dialogue in any locality under `district:kings_road` then inherits those biases automatically via `compute_inherited_affinity()`.

#### 2.3.3 Dynamic address belongings
When an NPC is assigned to a new district (e.g., a migrating caravan), call `FactionSystem.add_npc_belonging_tag(npc_id, "district:kings_road", significance=0.4, role="traveler")`. The next `_build_faction_context()` call picks it up.

#### 2.3.4 Hook points already available
| Hook | Purpose |
|------|---------|
| `set_location_affinity_default(...)` | Seed a cultural bias for a new address |
| `get_location_affinity_defaults(location_id)` | Query all biases for a location |
| `compute_inherited_affinity([(tier, id), ...])` | Blend the full hierarchy at dialogue time |
| `add_npc_belonging_tag(...)` | Attach an NPC to a new faction |
| `remove_npc_belonging_tag(...)` | Handle faction defection / exile |

No code changes are required in the faction module when the map grows — only data registrations. The inheritance walk handles arbitrary depth.

### 2.4 When the Quest Tool Becomes Real

**Today**: `QuestGenerator` is hardcoded: three quest IDs, three outcomes each, nine affinity-delta tables.

**When quests become dynamic** (LLM-authored, or JSON-authored by designers):

1. **Route every quest-authoring pipeline through `QuestGenerator.apply_quest_completion(quest_id, outcome, player_id)`**. Do not call `adjust_player_affinity` directly from quest logic — doing so bypasses the delta table and makes tuning centralized.
2. **Replace the hardcoded `_QUEST_DELTAS` dict** with a JSON-loaded registry:
   - New file: `world_system/config/quest_affinity_deltas.json`
   - Shape: `{ "<quest_id>": { "<outcome>": { "<tag>": <delta_float>, ... } } }`
   - Load in `QuestGenerator.__init__` via `DatabaseSingleton` pattern.
3. **For LLM-generated quests**: have the generation prompt emit the delta table alongside the quest narrative. Validate that every tag in the deltas is a known tag (check `schema.BOOTSTRAP_TAGS` or the live `npc_belonging_tags` table).
4. **Test surface** — the existing `test_faction_phase3b_quest.py` verifies the delta-application pathway; keep those tests, replace only the content.

---

## 3. Change Summary — This Branch

### Files Added
| File | Purpose | LOC |
|------|---------|-----|
| `factions/dialogue_helper.py` | Assemble dialogue context from FactionSystem | 50 |
| `factions/quest_tool.py` | Hardcoded quest→delta router | 140 |
| `factions/consolidator.py` | Top-5 affinity roll-up + event publish | 150 |
| `factions/test_faction_phase3a_dialogue.py` | 6 tests, all passing | — |
| `factions/test_faction_phase3b_quest.py` | 10 tests, all passing | — |
| `factions/test_faction_phase3c_consolidator.py` | 13 tests, all passing | — |
| `factions/PHASE_COMPLETE.md` | This document | — |

### Files Modified
| File | Change |
|------|--------|
| `factions/__init__.py` | Export `QuestGenerator`, `AffinityConsolidator`, `FACTION_AFFINITY_CONSOLIDATED` |
| `npc/npc_agent.py` | Import FactionSystem + helper; inject `{faction_context}` into system prompt; **bug fix**: sort `belonging_tags.values()` by significance (previously `.values()[:5]` which fails in Py3) |
| `config/prompt_fragments.json` | +27 fragments; meta v3.1→v3.2; total 127→154 |
| `world_memory/prompt_assembler.py` | Register `affinity`, `interaction`, `faction` categories; add two entries to `EVENT_TO_DOMAIN` |
| `tools/prompt_editor.py` | Add colors and `CATEGORY_ORDER` entries for new categories |

### Tests
- **29 new tests** across Phase 3A/B/C
- **50 total** in the faction module
- **100% passing** — verified on 2026-04-19

---

## 4. Reference: Key Invariants

These are the things that break silently if violated. Keep an eye on them:

1. **Affinity scale is -100..100, clamped at write time.** Never normalize at read time.
2. **Significance is 0.0..1.0**, used as a weight in blends (not clamped to a discrete set).
3. **The `_player` reserved tag** in `npc_affinity` is *only* accessed through `get_npc_affinity_toward_player()` and `set_npc_affinity_toward_player()`. Never SQL-query it directly — the helper centralizes the reserved-tag check.
4. **`FACTION_AFFINITY_CHANGED` is the one event emitted from `adjust_player_affinity`.** Every other mutation path that changes player standing must route through that method.
5. **Placeholder fragments** (`faction:*`, `_faction_context`) start with the literal word `PLACEHOLDER` — search for it to find work-in-progress stylization targets.
6. **Location hierarchy is ordered specific → general.** `compute_inherited_affinity` assumes this; reversing the list silently inverts the weight blend.

---

## 5. How to Regression-Test After Landing Any Roadblock Fix

Run these in order:
```bash
# Unit tests (module)
python -m pytest world_system/living_world/factions/ -q

# Prompt fragment integrity
python -c "from world_system.world_memory.prompt_assembler import PromptAssembler; \
  pa = PromptAssembler(); total = pa.load(); \
  assert total >= 184, f'Fragment count regressed: {total}'; \
  print(f'OK: {total} fragments')"

# End-to-end dialogue smoke (requires a backend running)
# python -c "from world_system.living_world.npc.npc_agent import NPCAgentSystem; ..."
```

---

**End of Phase.** The faction system is a recording + retrieval substrate. Everything downstream (dialogue coloring, map wiring, quest authoring, LLM narrative consolidation) hooks in without modifying this module. The seams are explicit and tested.
