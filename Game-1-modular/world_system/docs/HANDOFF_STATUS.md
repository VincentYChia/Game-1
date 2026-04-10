# World Memory System — Handoff Status

**Date**: 2026-04-10
**Branch**: `claude/game1-world-memory-context-YDXhm`
**Phase**: Layer 1-2 fully operational. LLM pipeline wired. Layer 3 ready to build.
**Tests**: 61 passing (0 failures)

---

## Current Architecture

```
Game Action → GameEventBus → EventRecorder (priority -10)
                                    ↓
              ┌─────────────────────┼─────────────────────────┐
              ↓                     ↓                         ↓
    StatStore (Layer 1)    Raw Fact Log (EventStore)    TriggerManager
    name, value, tags,     events + event_tags           dual-track thresholds
    description            (25-col structured facts)     (1,3,5,10,25,50,100...)
                                                              ↓
                                                    WorldInterpreter
                                                    33 evaluators check relevance
                                                              ↓
                                                    WmsAI.generate_narration()
                                                    PromptAssembler (123 fragments)
                                                    → BackendManager → Claude API
                                                              ↓
                                                    InterpretedEvent (Layer 2)
                                                    stored in EventStore + LayerStore
```

---

## Layer 1: StatStore (COMPLETE — REFACTORED)

**Schema**: `stats(name TEXT PK, value REAL, tags TEXT, description TEXT, updated_at REAL)` + `stat_tags` junction table.

**Key files**:
- `world_system/world_memory/stat_store.py` (647 lines)
- `entities/components/stat_tracker.py` (1,156 lines) — 74 `record_*` methods

**Write ops**: `increment(name, amount)`, `set_value(name, value)`, `set_max(name, value)`
**Read ops**: `get(name)`, `get_prefix(prefix)`, `query_by_tags(tags)`, `get_with_meta(name)`

Tags auto-derived from name structure on first write. Manifest (`stat-key-manifest.json`, 374 patterns) provides richer tags. LayerStore no longer duplicates Layer 1 — StatStore is the single source of truth.

**Save format**: `to_dict()` serializes as `{name: value}` flat dicts. `from_dict()` handles v2.0 (flat), v1.0 (count/total/max dicts), and legacy formats.

---

## Layer 2: LLM Narrations (COMPLETE — OPERATIONAL)

**Pipeline**: Threshold trigger → evaluator produces data context → WmsAI assembles prompt from tag-indexed fragments → LLM generates one-sentence narration → stored as InterpretedEvent.

**Key files**:
- `world_system/world_memory/interpreter.py` (394 lines) — orchestrates 33 evaluators + LLM upgrade
- `world_system/world_memory/wms_ai.py` (354 lines) — WMS AI central, routes to Claude/Ollama/Mock
- `world_system/world_memory/prompt_assembler.py` (321 lines) — tag-indexed fragment selection
- `world_system/config/prompt_fragments.json` — 123 fragments across 20 categories
- `world_system/world_memory/evaluators/` — 33 evaluator files

**How it works**:
1. EventRecorder detects threshold crossing (1st, 3rd, 5th, 10th... occurrence)
2. Calls `interpreter.on_trigger(action)`
3. Interpreter runs all relevant evaluators — each checks `is_relevant(event)` then `evaluate()` to produce category, severity, spatial scope, cause chain, and a template narrative
4. `_upgrade_narrative()` calls WmsAI with the evaluator's context
5. WmsAI uses PromptAssembler to select matching fragments from the 123-fragment library
6. Full prompt sent to Claude via BackendManager (fallback: Ollama → Mock → template)
7. LLM response replaces the template narrative
8. InterpretedEvent stored in EventStore (`interpretations` table) and LayerStore (`layer2_events` + `layer2_tags`)

**Prompt assembly**: `core + domain + entity fragments + data block + output instruction` ≈ 250-350 tokens input.

**Fragment categories** (123 total):
| Category | Count | Purpose |
|----------|-------|---------|
| domain | 16 | Evaluator lens (combat, gathering, crafting, ...) |
| species | 13 | Enemy identity from hostiles-1.JSON |
| status_effect | 13 | DoT, CC, buff context |
| result | 10 | Success, failure, critical, first, record, ... |
| item_category | 9 | Weapon, armor, consumable, tool, device, ... |
| material_category | 9 | Metal, wood, stone, plant, fish, ... (expanded) |
| element | 8 | Physical, fire, ice, lightning, ... |
| attack_type | 6 | Melee, ranged, magic, critical, aoe, chain |
| discipline | 6 | Smithing, alchemy, refining, ... |
| rarity | 5 | Common through legendary |
| source | 5 | Combat, quest, crafting, loot, fishing |
| tier | 4 | T1-T4 significance scaling |
| tool | 4 | Pickaxe, axe, hammer, fishing_rod |
| npc | 3 | Combat trainer, mysterious trader, tutorial guide |
| rank | 3 | Normal, boss, unique |
| resource | 3 | Gold, exp, mana |
| quality | 2 | Masterwork, legendary |
| action | 2 | Deplete, invent (edge case disambiguation) |

**Backend configuration** (`backend-config.json`): All WMS layers (2-7) route to Claude as primary. Fallback chain: Claude → Ollama → Mock.

---

## Prompt Fragment Design Principles

Documented in `prompt_fragments.json` `_meta.design_principles`:

1. **P1**: Simple language. A tiny LLM needs CLARITY over PRECISION.
2. **P2**: No internal mechanics (formulas, multipliers, balance constants).
3. **P3**: No flavor or lore. Fragments are CONTEXT, not worldbuilding.
4. **P4**: Be explicit about what game terms MEAN for narration.
5. **P5**: If the developer doesn't immediately understand it, rewrite it.
6. **P6**: Every sentence should help the LLM DISTINGUISH this event from others.

**Auto-expansion** (future): New game entities auto-generate fragments via Claude meta-prompt, indexed by tag.

**Developer tool**: `tools/prompt_editor.py` — tkinter three-panel editor for browsing, editing, and simulating prompt assembly. Run: `python tools/prompt_editor.py`

---

## Temporal Storage Design (DESIGNED — NOT YET IMPLEMENTED)

Three SQL tiers for time-dimensional data. See `LAYER_1_2_REDESIGN.md` for full schema.

- **Tier 1**: `current_day_events` — individual events during current game-day, cleared at day boundary
- **Tier 2**: `daily_summary` + `daily_detail` — one detailed row per completed day, kept forever
- **Tier 3**: `monthly_summary` + `monthly_detail` — 30-day rollups, kept forever

Day boundary: `game_engine.py:443` `CYCLE_LENGTH = 1440.0s`. Month = 30 game-days.

All temporal calculations derived on demand from these tiers + StatStore. No stored calculations.

---

## Known Issues / Remaining Work

### Prompt Editor Locations
The location dropdown in `tools/prompt_editor.py` has hardcoded locality names. This is a stopgap — the real system uses `GeographicRegistry` with full hierarchical addressing (locality → district → province → realm). The editor should load localities from the geographic system or from a generated world's `geographic-map.json`.

### EventStore Cleanup (Designed, Not Implemented)
The EventStore currently has 24 tables mixing raw facts, counters, interpretations, consumer state, and higher-layer schemas. The redesign (documented in `LAYER_1_2_REDESIGN.md`) splits these:
- **Keep**: `events`, `event_tags` (raw facts)
- **Remove**: 3 counter tables (redundant), 2 trigger tables (dead code)
- **Move**: interpretations → LayerStore, consumer state → consumer systems, Layer 3-7 → LayerStore

### Layer 3: Consolidators (NEXT)
Four consolidators designed in `WORLD_MEMORY_SYSTEM.md` §6.3:
1. Regional Activity Synthesizer
2. Cross-Domain Pattern Detector
3. Player Identity Consolidator
4. Faction Narrative Synthesizer

These read Layer 2 interpretations and produce cross-domain consolidated narratives. WmsAI is already configured for Layer 3 (`wms_layer3` task, temperature 0.4, max_tokens 300).

### StatTracker Method Cleanup
10 methods use the old `record(key, value)` pattern which increments by magnitude instead of by 1. In the new single-value schema, these stats store the magnitude total but lose the separate occurrence count. The stats that need splitting (e.g., `skills.used` = count vs magnitude) should be updated.

---

## File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `stat_store.py` | 647 | Layer 1: (name, value, tags, description) schema |
| `stat_tracker.py` | 1,156 | 74 record_* methods writing to StatStore |
| `event_store.py` | 1,140 | Raw fact log + Layer 2 interpretations (24 tables) |
| `event_recorder.py` | 484 | Bus → SQLite bridge, trigger checking |
| `interpreter.py` | 394 | 33 evaluators + WmsAI narrative upgrade |
| `wms_ai.py` | 354 | LLM call routing, prompt assembly, fallback |
| `prompt_assembler.py` | 321 | Tag-indexed fragment selection engine |
| `world_memory_system.py` | 478 | Facade coordinating all subsystems |
| `layer_store.py` | 334 | Per-layer tag-indexed storage (Layers 2-7) |
| `prompt_editor.py` | 571 | Tkinter developer tool |
| `prompt_fragments.json` | 123 fragments | Tag-indexed prompt context library |
| `stat-key-manifest.json` | 374 patterns | Stat → tag mappings |
| `backend-config.json` | — | LLM routing (Claude primary for all WMS layers) |
| `LAYER_1_2_REDESIGN.md` | — | Design decisions document |

**Total new/modified**: ~5,879 lines across core WMS files.
**Tests**: 61 passing (24 stat + 27 pipeline + 10 integration).

---

## How to Continue

1. **Read** this file + `LAYER_1_2_REDESIGN.md` for all design decisions
2. **Run tests**: `python world_system/world_memory/test_stat_store.py && python world_system/world_memory/test_foundation_pipeline.py && python world_system/world_memory/test_memory_system.py`
3. **Edit prompts**: `python tools/prompt_editor.py` (requires tkinter)
4. **Test with Claude**: Set `ANTHROPIC_API_KEY` env var, run game — WmsAI auto-detects and routes to Claude
5. **Next task**: Implement Layer 3 consolidators (see Layer 3 design section below)

---

## Layer 3 Design — Ready to Implement

### What Layer 3 Does

Layer 3 is the **first cross-domain layer**. Where Layer 2 evaluators each look through a single lens (combat kills evaluator, gathering evaluator, crafting evaluator), Layer 3 reads MULTIPLE Layer 2 outputs for a geographic area and synthesizes them into a consolidated picture.

**Visibility rule**: Layer 3 sees Layer 2 interpretations (full) and Raw Event Pipeline (limited). It does NOT see Layer 1 stats or Layers 4-7.

**Trigger**: When a district accumulates 3+ Layer 2 interpretations OR 2+ from different categories.

### The Four Consolidators

**1. Regional Activity Synthesizer** (`regional_synthesis`)
- Reads: All Layer 2 interpretations for a district
- Input: List of Layer 2 narratives with categories, severities, locality IDs
- Output: One paragraph summarizing the district's overall activity state
- Example input: ["Player killed 15 wolves in Whispering Woods", "Player gathered 30 iron in Iron Hills", "Player depleted 4 nodes in Iron Hills"]
- Example output: "The Western Frontier district shows mixed combat and gathering activity. Whispering Woods has sustained wolf culling while Iron Hills is under heavy resource extraction with node depletion."

**2. Cross-Domain Pattern Detector** (`cross_domain`)
- Reads: Layer 2 interpretations across categories in the same geographic area
- Input: Pairs/groups of interpretations from different domains
- Output: Detected pattern connecting domains
- Example: combat_kills + gathering_depletion in same locality → "Heavy combat and resource depletion co-occurring in Whispering Woods — the player is working this area intensively across multiple activities."

**3. Player Identity Consolidator** (`player_identity`)
- Reads: All player-related Layer 2 interpretations across all locations
- Input: All recent Layer 2 narratives about the player
- Output: Behavioral profile summary
- Example: "The player is primarily a melee combatant with growing smithing expertise, focused on the western regions. 3-day combat streak, T1-T2 enemies."

**4. Faction Narrative Synthesizer** (`faction_narrative`)
- Reads: Social + economy + combat interpretations involving faction-tagged entities
- Input: Layer 2 narratives tagged with faction-relevant tags
- Output: Faction relationship narrative
- Example: "Player reputation with Miners Guild rising through sustained gathering activity and quest completion in their territory."

### Layer 3 Prompt Architecture

Layer 3 uses the same WmsAI infrastructure as Layer 2 but with different prompt construction. The system prompt needs to:
1. Explain that this is a CONSOLIDATION task (not a single-event narration)
2. Provide geographic context (district/province names, what localities are in it)
3. Present multiple Layer 2 narratives as input
4. Ask for a synthesis, not a list

**Prompt structure** (applying Claude best practices):

```
SYSTEM PROMPT:
You are a game world chronicler. You consolidate individual event reports
into coherent district-level summaries.

Rules:
- Synthesize, do not list. Connect events across domains.
- Write 2-3 sentences maximum.
- State facts about what happened. Do not speculate about causes.
- Use the geographic names provided.
- Do not repeat individual event narratives — summarize patterns.

EXAMPLE INPUT:
<district name="Western Frontier">
<locality name="Whispering Woods">
  <event category="combat" severity="moderate">Player has killed 15 wolves in Whispering Woods.</event>
  <event category="gathering" severity="minor">Player has gathered 8 oak in Whispering Woods.</event>
</locality>
<locality name="Iron Hills">
  <event category="gathering" severity="significant">Player has gathered 45 iron ore in Iron Hills.</event>
  <event category="gathering" severity="moderate">Player has depleted 6 resource nodes in Iron Hills.</event>
</locality>
</district>

EXAMPLE OUTPUT:
The Western Frontier is seeing concentrated activity. Iron Hills is under heavy resource extraction with node depletion, while Whispering Woods has moderate combat with some gathering. Activity spans two localities in the district.

USER PROMPT:
<district name="{district_name}">
{layer_2_events_as_xml}
</district>
```

**Key design choices**:
- XML tags for structured data (Claude parses these reliably)
- Geographic hierarchy explicit in the prompt (district → localities)
- Few-shot example showing input format AND expected output style
- Negative constraints ("do not list", "do not speculate")
- Temperature 0.4 (slightly higher than Layer 2's 0.3 — synthesis needs more flexibility)
- Max tokens 300 (longer than Layer 2's 150 — multi-sentence output)

### Layer 3 Prompt Fragments

Layer 3 needs its own fragment set (separate from Layer 2):

| Fragment | Content |
|----------|---------|
| `_l3_core` | Chronicler role + rules + example (as above) |
| `_l3_output` | "Write 2-3 sentences synthesizing these events." |
| `l3_consolidator:regional_synthesis` | "Summarize all activity in this district across domains." |
| `l3_consolidator:cross_domain` | "Identify connections between different types of activity in the same area." |
| `l3_consolidator:player_identity` | "Describe the player's behavioral pattern based on their recent activities." |
| `l3_consolidator:faction_narrative` | "Describe how the player's activities affect faction relationships." |

These are stored in the same `prompt_fragments.json` with an `l3_` prefix.

### Implementation Plan

1. **Create Layer 3 trigger logic**: Monitor LayerStore `layer2_events` — trigger when a district accumulates 3+ events or 2+ from different categories
2. **Create 4 consolidator evaluators** in `evaluators/` following the PatternEvaluator interface but reading from LayerStore instead of EventStore
3. **Add Layer 3 fragments** to `prompt_fragments.json`
4. **Wire through WmsAI** — already configured (`wms_layer3` task in backend-config.json)
5. **Store output** in LayerStore `layer3_events` + `layer3_tags`

### Data Flow for Layer 3

```
Layer 2 interpretation stored in LayerStore
       ↓
Layer 3 trigger check (in WorldMemorySystem.update())
  "Does district X have 3+ Layer 2 events? 2+ categories?"
       ↓
Layer 3 consolidator runs:
  1. Query LayerStore: layer2_events WHERE district tags match
  2. Group by locality
  3. Build XML data block
  4. Call WmsAI.generate_narration(layer=3)
  5. Store result in layer3_events + layer3_tags
```

### Dependencies

- LayerStore query_by_tags for Layer 2 (already works)
- GeographicRegistry for district→locality hierarchy (already works)
- WmsAI with `wms_layer3` routing (already configured)
- Layer 2 must be producing events (already operational)

**No blockers. Ready to code.**
