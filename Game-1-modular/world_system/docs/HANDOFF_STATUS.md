# World Memory System — Handoff Status

**Date**: 2026-04-12
**Branch**: `claude/review-handoff-status-BZ64g`
**Phase**: Layers 1-4 operational. Layer 5+ designed but not implemented.
**Tests**: 93 passing (54 Layer 3 + 39 Layer 4, 0 failures)

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
                                                    PromptAssembler (123+ fragments)
                                                    → BackendManager → Claude API
                                                              ↓
                                                    InterpretedEvent (Layer 2)
                                                    stored in EventStore + LayerStore
                                                              ↓
                                                    Layer3Manager (every 15 L2 events)
                                                    4 consolidators per district
                                                              ↓
                                                    ConsolidatedEvent (Layer 3)
                                                    stored in LayerStore layer3_events
                                                              ↓
                                                    Layer4Manager (per-province weighted triggers)
                                                    Province summarizer per province
                                                              ↓
                                                    ProvinceSummaryEvent (Layer 4)
                                                    stored in LayerStore layer4_events
```

---

## Geographic Hierarchy (5-level)

The WMS now maps the game's full 5-tier hierarchy 1:1:

| WMS Level | Game Concept | ID Format | Example |
|-----------|-------------|-----------|---------|
| REALM | World | `realm_0` | The Known Lands |
| NATION | Nation | `nation_X` | Northern Kingdom |
| PROVINCE | Region | `region_X` | Iron Reaches (Layer 4 scope) |
| DISTRICT | Province | `province_X` | Western Mines (Layer 3 scope) |
| LOCALITY | District | `district_X` | Deep Mine (Layer 2 / position lookup) |

Tag addressing: `locality:district_X`, `district:province_X`, `province:region_X`, `nation:nation_X`.

---

## Layer 1: StatStore (COMPLETE)

**Schema**: `stats(name TEXT PK, value REAL, tags TEXT, description TEXT, updated_at REAL)` + `stat_tags` junction table.

**Key files**: `stat_store.py` (647 lines), `stat_tracker.py` (1,156 lines — 74 `record_*` methods).

---

## Layer 2: LLM Narrations (COMPLETE)

**Pipeline**: Threshold trigger → evaluator produces data context → WmsAI assembles prompt from tag-indexed fragments → LLM generates one-sentence narration → stored as InterpretedEvent.

**Key files**: `interpreter.py` (394 lines), `wms_ai.py` (~375 lines), `prompt_assembler.py` (~460 lines), `prompt_fragments.json` (123 fragments), 33 evaluator files.

---

## Layer 3: Consolidation (COMPLETE)

**Pipeline**: Every 15 Layer 2 events → Layer3Manager runs 4 consolidators per district → LLM upgrades narrative → ConsolidatedEvent stored in LayerStore.

**Key files**:
- `layer3_manager.py` (~440 lines) — orchestrator with counter-based trigger, L4 callback
- `consolidator_base.py` (167 lines) — ABC with XML builder, severity logic
- `consolidators/` — 4 consolidator modules:
  - `regional_synthesis.py` — district activity summary
  - `cross_domain.py` — inter-domain pattern detection
  - `player_identity.py` — behavioral profile (global scope)
  - `faction_narrative.py` — faction relationship tracking (global scope)
- `prompt_fragments_l3.json` — 10 Layer 3 prompt fragments
- `event_schema.py` — ConsolidatedEvent dataclass

**Trigger**: Counter-based. Every 15 L2 events, runs consolidation for all districts with 3+ L2 events or 2+ categories.

**LLM**: Sonnet-class, temperature 0.4, max_tokens 300. Assigns interpretive tags (sentiment, trend, intensity, etc.) via JSON output. Structural tags (district, consolidator) preserved from template.

**Tests**: 54 passing.

---

## Layer 4: Province Summarization (COMPLETE)

**Pipeline**: L3 event routed to per-province bucket → geo tags stripped, content tags scored by position → content tag crosses 50 points within a province → contributing L3 events + top-5-tag-matched L2 events gathered → single province summary → LLM full tag rewrite → ProvinceSummaryEvent stored in LayerStore.

**Key files**:
- `layer4_manager.py` (530 lines) — per-province trigger routing, L2 filtering, LLM upgrade
- `layer4_summarizer.py` (437 lines) — province-level summary builder, XML data block
- `trigger_registry.py` (372 lines) — centralized trigger system (simple + weighted + prefix ops)
- `prompt_fragments_l4.json` — 5 Layer 4 prompt fragments
- `event_schema.py` — ProvinceSummaryEvent dataclass

### Per-Province Tag-Weighted Triggers

Each province gets its own `WeightedTriggerBucket` (named `layer4_province_{province_id}`), created lazily when the first L3 event for that province arrives. This ensures tags accumulate independently per province — `domain:combat` in region_1 does not combine with `domain:combat` in region_2.

**Geographic tag stripping**: Before ingestion, geographic address tags (`province:`, `district:`, `locality:`, `nation:`) are stripped from the tag list. This promotes content tags to earlier positions (e.g. `domain:combat` moves from position 2 → position 0 = 10 pts instead of 6 pts). Only content tags drive triggers.

Tags are scored by position in the **stripped** tag list:
| Position | Points |
|----------|--------|
| 1st | 10 |
| 2nd | 8 |
| 3rd | 6 |
| 4th | 5 |
| 5th | 4 |
| 6th | 3 |
| 7th-12th | 2 |
| 13th+ | 1 |

When any content tag crosses 50 points within a province, it fires. All L3 events that contributed to that tag's score are used as primary context. Structural tags (`significance:`, `scope:`, `consolidator:`) are also excluded from scoring.

**Reset behavior**: After firing, the tag's score resets to 0 and all contributing events are voided — the trigger is recurring (fires every 50 points, not once). If the score reaches 55, ALL contributing events are voided with no carryover.

### LLM Full Tag Rewrite

At Layer 4+, the LLM receives ALL inherited tags from input events as context (shown in XML `tags="[...]"` attributes) and outputs a complete reordered tag list:
- Keep 66-80% of aggregate tags
- Reorder by relevance to the generated narrative (most relevant first)
- Add Layer 4 categories: `faction`, `urgency_level`, `event_status`, `player_impact`
- Tag order matters — position determines weight in future trigger calculations

### L2 Visibility (Top-5 Tag Matching)

Layer 4 sees L3 (full) and L2 (filtered by top-tag matching):

1. Collect all content tags from L3 events, ranked by frequency (geo/structural stripped)
2. Take the **top 5** as the matching set (rank 0 = most important)
3. For each L2 candidate in the province, count how many of the 5 it contains
4. **Minimum 3/5 match** required — below this, the L2 event is excluded
5. Sort by: match count (desc) → best matched tag rank (asc, **winner-take-all**: having the #1 tag beats having only #2-5) → game_time (desc, most recent)
6. Return at most **5** L2 events

### L3 Tag Ordering

Layer 3 tags are ordered by **frequency** across origin L2 events (most frequent first, tiebreak by first appearance). This is documented as an intentional design choice in `tag_assignment.py:_merge_origin_tags()`, with LLM prompting noted as an alternative.

### Prompt Fragment Aggregation

Layer 4 prompts aggregate fragments from ALL lower layers (L2 + L3 + L4). The `_collect_all_tag_fragments()` method matches event tags against all fragment sources, giving the LLM full context about species, materials, disciplines, etc.

### TriggerRegistry (Centralized)

`trigger_registry.py` provides two bucket types:
- **TriggerBucket** — simple per-key counter (used by Layer 3)
- **WeightedTriggerBucket** — tag-positional scoring (used by Layer 4+)

Prefix-based operations (`any_weighted_fired_with_prefix`, `pop_all_fired_weighted_with_prefix`, `get_weighted_bucket_names`) support per-province bucket management without iterating private state. Both bucket types support save/load serialization. The registry is a singleton shared across all layers.

**Tests**: 39 passing.

---

## Province Summaries Table

The `province_summaries` table in EventStore (from the original design doc) is **not used** by Layer 4. Instead, Layer 4 stores events in `layer4_events` + `layer4_tags` via LayerStore, consistent with the append-only pattern used by Layers 2-3. The `province_summaries` table remains in the schema but is dormant — it may be repurposed as a materialized view or removed in a future cleanup.

---

## Known Issues / Remaining Work

### Layer 5-7 (Designed, Not Implemented)
- Layer 5: Realm-level summaries from multiple provinces
- Layer 6: Cross-realm patterns
- Layer 7: World-level narrative threads
- All use LayerStore tables (already created), WmsAI routing (already configured)

### Prompt Editor Geographic Dropdown
The location dropdown in `tools/prompt_editor.py` has hardcoded locality names. Should load from GeographicRegistry.

### EventStore Cleanup (Designed, Not Implemented)
EventStore has 24 tables mixing raw facts, counters, interpretations, and higher-layer schemas. Some are redundant with LayerStore.

---

## How to Continue

1. **Read** this file + `WORLD_MEMORY_SYSTEM.md` for design reference
2. **Run tests**: `python -m unittest world_system.world_memory.test_layer3 world_system.tests.test_layer4 -v`
3. **Next task**: Layer 5 realm summaries (uses same WeightedTriggerBucket pattern, reading layer4_events)
4. **Test with Claude**: Set `ANTHROPIC_API_KEY` env var — WmsAI auto-detects and routes to Claude
