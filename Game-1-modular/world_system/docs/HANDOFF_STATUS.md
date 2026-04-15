# World Memory System — Handoff Status

**Date**: 2026-04-16 (updated 2026-04-16 after Layer 6 completion)
**Branch**: `claude/implement-layer-6-nation-N6Xdy`
**Phase**: Layers 1-6 operational on a corrected 6-tier hierarchy
(`World → Nation → Region → Province → District → Locality`). Layer 7
is the next task — final aggregation tier at the game World level.
**Tests**: 166 passing (54 Layer 3 + 39 Layer 4 + 37 Layer 5 + 36 Layer 6, 0 failures)
**Schema**: `EventStore.SCHEMA_VERSION = 2` (v1 databases hard-fail on
load; `WorldMemorySystem.load` recovers by deleting the stale file).

## Single Sources of Truth

Every module that touches address tags reads from **one** place. Do
not redeclare these anywhere else:

| Concept | Source | Consumers |
|---|---|---|
| 6-tier `RegionLevel` enum | `world_system/world_memory/geographic_registry.py` | Entire WMS |
| `ADDRESS_TAG_PREFIXES` tuple | `geographic_registry.py` (derived from `ADDRESS_TIERS_COARSE_TO_FINE`) | Every layer manager + summarizer + test that strips addresses |
| `is_address_tag(tag)` | `geographic_registry.py` | LLM output filters |
| `partition_address_and_content(tags)` | `geographic_registry.py` | Every `_upgrade_narrative` call |
| `propagate_address_facts(events, tiers)` | `geographic_registry.py` | Every `_build_tags` in summarizers |
| Game geographic hierarchy | `systems/geography/models.py` | `GeographicRegistry.load_from_world_map` |
| Layer aggregation contract | `ARCHITECTURAL_DECISIONS.md` §6 | Every layer manager |
| `WorldMemoryEvent.{locality,district,province,region,nation,world}_id` fields | `event_schema.py` | `EventRecorder._enrich_geographic`, interpreter |
| `events` table SQL columns | `event_store.py::_SCHEMA_SQL` | `_event_insert_params` + `_row_to_event` |
| `SCHEMA_VERSION` | `EventStore.SCHEMA_VERSION` class attr | Boot-time schema check |

When adding Layer 6 (or any future tier-specific code), **import from
this table's sources**. Never copy a prefix tuple or re-declare an
enum value.

> **Major migration this session**: The WMS geography labels were
> previously shifted one tier relative to the game's own hierarchy,
> which caused `province:region_17` to mean "WMS province, game region
> 17" — contradictory. The loader, event fields, tag namespaces, layer
> targets, and test fixtures have all been realigned to the game's
> terms (`systems/geography/models.py`). Layer 5 was structurally
> wrong (it aggregated game Region straight to game World); it now
> correctly aggregates one tier up from Layer 4, targeting game
> Region. Address tags are now **facts**: assigned at L2 capture from
> chunk position, propagated unchanged, never synthesized or rewritten
> by the LLM. See `ARCHITECTURAL_DECISIONS.md` §6.

> **Pipeline scope**: The WMS layer pipeline consumes **raw gameplay
> events only**. `FactionSystem` and `EcosystemAgent` are separate
> sibling trackers that listen to the same GameEventBus but **do not
> feed into any WMS layer**. `FACTION_REP_CHANGED`,
> `FACTION_MILESTONE_REACHED`, `RESOURCE_SCARCITY`, and
> `RESOURCE_RECOVERED` are explicitly **not** wired into
> `BUS_TO_MEMORY_TYPE`, and no layer code reads from
> `FactionSystem` or `EcosystemAgent`. See
> [`ARCHITECTURAL_DECISIONS.md`](ARCHITECTURAL_DECISIONS.md) §§1-5 for
> full rationale.

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
                                                    Province summarizer per game Province
                                                              ↓
                                                    ProvinceSummaryEvent (Layer 4)
                                                    stored in LayerStore layer4_events
                                                              ↓
                                                    Layer5Manager (per-region weighted triggers)
                                                    Region summarizer per game Region
                                                              ↓
                                                    RegionSummaryEvent (Layer 5)
                                                    stored in LayerStore layer5_events
                                                              ↓
                                                    Layer6Manager (per-nation weighted triggers)
                                                    Nation summarizer per game Nation
                                                              ↓
                                                    NationSummaryEvent (Layer 6)
                                                    stored in LayerStore layer6_events
```

---

## Geographic Hierarchy (6-tier, aligned to the game)

As of the 2026-04-16 migration, the WMS hierarchy mirrors the game's
`systems/geography/models.py` 1:1 — no tier shifting. See
`ARCHITECTURAL_DECISIONS.md` §6.

| WMS `RegionLevel` | Game term | ID format | Always present? | Layer |
|---|---|---|---|---|
| `WORLD` | World | `world_0` | yes (singleton) | L7 target (future) |
| `NATION` | Nation | `nation_X` | yes | L6 target (future) |
| `REGION` | Region | `region_X` | yes | **L5 target** |
| `PROVINCE` | Province | `province_X` | yes | **L4 target** |
| `DISTRICT` | District | `district_X` | yes | **L3 target** |
| `LOCALITY` | Locality | `locality_X` | sparse — only if chunk has a POI | L2 capture only |

Tag addressing (coarsest → finest as emitted at L2 capture):
`world:world_0`, `nation:nation_X`, `region:region_X`,
`province:province_X`, `district:district_X`, `locality:locality_X`.

**Address tags are facts.** They are assigned at L2 capture from the
chunk's `GeographicData` and propagated unchanged to every higher
layer. The LLM at L4/L5 is given only *content* tags to rewrite;
address tags are partitioned out before the LLM call and re-attached
afterwards. See `ARCHITECTURAL_DECISIONS.md` §6 for the rule set.

**One tier per layer.** Each layer drops exactly one address tag on
its output because the aggregation is summed across that tier's
children:

| Layer | Aggregation tier | Drops | Retains |
|---|---|---|---|
| L2 | capture | — | world, nation, region, province, district, locality |
| L3 | district | locality | world, nation, region, province, district |
| L4 | province | district | world, nation, region, province |
| L5 | region | province | world, nation, region |
| L6 (future) | nation | region | world, nation |
| L7 (future) | world | nation | world |

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

## Layer 5: Region Summarization (COMPLETE)

**Aggregation tier**: game Region (parent of game Province). Layer 5
consolidates L4 province summaries across every province within one
game Region.

**Pipeline**: Layer 4 event created → Layer5Manager reads the
`region:X` tag directly from the event (no parent-chain walking —
address tags are facts assigned at L2 capture) → address tags stripped
before scoring → content tags scored in a per-region
`WeightedTriggerBucket` (named `layer5_region_{region_id}`) → when any
content tag crosses 100 points within a region → contributing L4
events + fired-tag-filtered L3 events gathered → region summary built
→ LLM CONTENT-tag rewrite (address tags preserved by layer code) →
RegionSummaryEvent stored in LayerStore `layer5_events` (superseding
previous summary for that region).

**Key files**:
- `layer5_manager.py` (~550 lines) — per-region trigger routing,
  trivial region resolution (one-tag lookup), L3 relevance filtering,
  LLM upgrade, supersession on second run
- `layer5_summarizer.py` (~500 lines) — region-level summary builder,
  XML data block with province grouping, `filter_relevant_l3` static
  method, propagates `world:`/`nation:`/`region:` facts from L4 inputs
- `prompt_fragments_l5.json` — 5 Layer 5 prompt fragments (address
  tags explicitly excluded from rewrite instructions)
- `event_schema.py` — `RegionSummaryEvent` dataclass

### Per-Region Tag-Weighted Triggers

Each game Region gets its own bucket (`layer5_region_{region_id}`),
created lazily when the first L4 event for that region arrives.
Events from different regions never cross-contaminate. Region
resolution is a single-tag lookup: the `region:X` tag is present on
every event (fact-propagated from L2 capture), so there is **no
parent-chain walking** — the fallback logic that existed in an earlier
pre-migration draft has been deleted. Events without a `region:` tag
are dropped silently.

Scoring reuses the same positional weights as Layer 4 (1st=10, 2nd=8,
…) and the same structural skip list (`significance:`, `scope:`,
`consolidator:`). Note that Layer4Summarizer always emits a
`scope:province` tag at position 0 of its output, so on typical L4
events the first *scoring* content tag lands at position 1 = 8 pts.
Threshold is 100 points.

### L3 Visibility (Fired-Tag Overlap Filter)

Layer 5 sees L4 (full, per-region) and L3 (filtered by fired-tag
overlap), following the "two-layers-down" visibility rule. Both L4
and L3 candidates are queried directly by their `region:X` tag — no
per-province enumeration needed. The fired tag set from the weighted
bucket drives relevance ranking:

1. Number of fired content tags they contain (desc; min 1 match)
2. Best-matched-tag position within the L3 event's own tag list (asc)
3. Game time (desc, most recent first)

Address tags are stripped from the fired set before matching. If the
fired set is empty after stripping, there is a fallback that derives
a content-tag set from the L4 events themselves. Results are capped
at 8 L3 events.

### LLM Upgrade — Content Tags Only

The Layer 5 LLM call partitions `summary.tags` into **address tags**
(`world:/nation:/region:/province:/district:/locality:`) and **content
tags**, sends only the content tags to the LLM, and re-attaches the
address half after the rewrite returns. Any address tag the LLM
emitted in its output is discarded. The prompt fragments are updated
to explicitly instruct the LLM not to emit address tags. See
`ARCHITECTURAL_DECISIONS.md` §6.

### Pure Pipeline — No Sibling Tracker Reads

**Layer 5 does not read `FactionSystem`, `EcosystemAgent`,
`NPCMemory`, or any other state tracker.** The `faction_standings`,
`economic_summary`, and `player_reputation` fields from older drafts
are not populated from external systems. See
`ARCHITECTURAL_DECISIONS.md` §§4-5 for rationale.

**Tests**: 37 passing (`world_system/tests/test_layer5.py`) — covers
`RegionSummaryEvent` dataclass, `Layer5Summarizer` (is_applicable,
summarize, XML data block, `filter_relevant_l3`), `Layer5Manager`
(on_layer4_created, region resolution via tag lookup, should_run,
run_summarization, multi-region isolation, supersession, stats),
`PromptAssemblerL5` (assemble_l5, fragment loading, cross-layer
fragment cascade), and a full integration test exercising L4 events
→ per-region trigger → stored L5 summary.

---

## Province Summaries Table

The `province_summaries` table in EventStore (from the original design doc) is **not used** by Layer 4. Instead, Layer 4 stores events in `layer4_events` + `layer4_tags` via LayerStore, consistent with the append-only pattern used by Layers 2-3. The `province_summaries` table remains in the schema but is dormant — it may be repurposed as a materialized view or removed in a future cleanup.

---

## Known Issues / Remaining Work

### Faction / Ecosystem are OUT of the Pipeline (Deliberate)
`FactionSystem` and `EcosystemAgent` are separate sibling trackers and
explicitly **not** part of the WMS layer pipeline. No layer reads from
them and `FACTION_REP_CHANGED` / `FACTION_MILESTONE_REACHED` /
`RESOURCE_SCARCITY` / `RESOURCE_RECOVERED` are intentionally absent
from `BUS_TO_MEMORY_TYPE`. Any future cross-system weaving belongs in
a parallel narrative layer, not inside the WMS layers. See
[`ARCHITECTURAL_DECISIONS.md`](ARCHITECTURAL_DECISIONS.md) §§2-5.

### EventStore Cleanup (Designed, Not Implemented)
EventStore has 24 tables mixing raw facts, counters, interpretations, and higher-layer schemas. Some are redundant with LayerStore.

---

## Layer 6: Nation Summarization (COMPLETE)

**Pipeline**: L5 event routed to per-nation bucket → geo tags stripped, content tags scored by position → content tag crosses 150 points within a nation → contributing L5 events + top-8-tag-matched L4 events gathered → single nation summary → LLM full tag rewrite → NationSummaryEvent stored in LayerStore.

**Key files**:
- `layer6_manager.py` (550 lines) — per-nation trigger routing, L4 filtering, LLM upgrade, L7 callback hook
- `layer6_summarizer.py` (500 lines) — nation-level summary builder, XML data block
- `prompt_fragments_l6.json` — 5 Layer 6 prompt fragments (address tags explicitly excluded)
- `event_schema.py` — `NationSummaryEvent` dataclass

### Per-Nation Tag-Weighted Triggers

Each game Nation gets its own bucket (`layer6_nation_{nation_id}`), created lazily when the first L5 event for that nation arrives. Events from different nations never cross-contaminate. Nation resolution is a single-tag lookup: the `nation:X` tag is present on every event (fact-propagated from L2 capture), so there is **no parent-chain walking**. Events without a `nation:` tag are dropped silently.

Scoring reuses the same positional weights as Layer 5 (1st=10, 2nd=8, …) and the same structural skip list (`significance:`, `scope:`, etc.). Note that Layer5Summarizer always emits a `scope:region` tag at position 0 of its output, so on typical L5 events the first *scoring* content tag lands at position 1 = 8 pts. Threshold is 150 points (higher than Layer 5's 100 because nation summaries should be rarer than region summaries).

### L4 Visibility (Fired-Tag Overlap Filter)

Layer 6 sees L5 (full, per-nation) and L4 (filtered by fired-tag overlap), following the "two-layers-down" visibility rule. Both L5 and L4 candidates are queried directly by their `nation:X` tag. The fired tag set from the weighted bucket drives relevance ranking (same algorithm as Layer 5). Results are capped at 8 L4 events.

### LLM Upgrade — Content Tags Only

The Layer 6 LLM call partitions `summary.tags` into **address tags** (`world:/nation:`) and **content tags**, sends only the content tags to the LLM, and re-attaches the address half after the rewrite returns. Any address tag the LLM emitted in its output is discarded.

### L7 Callback Hook

Layer 6 Manager includes a `set_layer7_callback` hook to notify Layer 7 when a nation summary is stored. This enables the callback chain for future world-level aggregation (Layer 7).

**Tests**: 36 passing (`world_system/tests/test_layer6.py`) — covers
`NationSummaryEvent` dataclass, `Layer6Summarizer` (is_applicable,
summarize, XML data block, `filter_relevant_l4`), `Layer6Manager`
(on_layer5_created, nation resolution via tag lookup, should_run,
run_summarization, multi-nation isolation with 25-event threshold
trigger, supersession, stats), `PromptAssemblerL6` (assemble_l6,
fragment loading, cross-layer fragment cascade), and a full integration
test exercising L5 events → per-nation trigger → stored L6 summary.

---

## Layer 7 Implementation Playbook (Next Task)

**Status**: Ready to implement. All architectural rules proven by Layers 3-6.

**Aggregation tier**: game World (singleton, `world_0`). Layer 7 consolidates
Layer 6 nation summaries across every nation within the single game World.
Drops `nation:` on output, retains `world:` only. This is the top tier — no
Layer 8 planned.

**Key insight**: Layer 7 is a **mechanical copy of Layer 6's pattern**, one
tier coarser. Only difference: single world bucket instead of per-nation
buckets (game has exactly one World). Architecture is proven; this is a
**1–2 day implementation task**. Copy-paste from Layer 6, rename classes/variables, adjust one tier.

### File-by-file Implementation Plan

All constants imported from `geographic_registry.py` (NO re-declarations).

**New files**:
- `world_system/world_memory/layer7_manager.py` (~610 lines) — copy of
  `layer6_manager.py`, then:
  - `BUCKET_PREFIX = "layer7_world_"` — single world bucket
  - Class renamed `Layer7Manager`
  - `_max_l6_per_world` config key (fallback default 20)
  - `on_layer6_created(l6_event_dict)` instead of `on_layer5_created`
  - `_resolve_world_id_from_tags` — scans for `world:X` tag (always `world_0`)
  - `_fetch_l6_events(world_id, ...)` queries `layer=6` with `world: tag`
  - `_query_relevant_l5(world_id, fired_tags, l6_events)` — two layers down,
    queries `layer=5` by `world:` tag, passes to `Layer7Summarizer.filter_relevant_l5`
  - `_summarize_world` analog of `_summarize_nation`
  - `_build_geo_context` returns `{"world_name": "...", "nations": [...]}`
  - `_upgrade_narrative` — identical pattern to L6 (partition/filter/re-attach)
  - `_store_summary` writes category `"world_summary"` to `layer7_events`
  - `_find_supersedable` reads `layer7_events` where category = `"world_summary"`
  - No Layer 8 callback (this is the final tier)

- `world_system/world_memory/layer7_summarizer.py` (~510 lines) — copy of
  `layer6_summarizer.py`, then:
  - Class renamed `Layer7Summarizer`
  - `summarize(..., world_id=...)` returns `WorldSummaryEvent`
  - `is_applicable(..., world_id=...)` — min 2 L6 events (or set to 1?)
  - `build_xml_data_block` root element `<world name="...">`, children
    `<nation name="...">`, cross-nation bucket `<cross-nation>`
  - `filter_relevant_l5` analog of `filter_relevant_l4` (same fired-tag
    overlap algorithm, different input layer)
  - `_extract_dominant_activities` unchanged (global scope)
  - `_extract_dominant_nations` replaces `_extract_dominant_regions`
    (scans for `nation:` tags)
  - `_determine_world_condition` — same severity/threat classifier, renamed
  - `_build_tags(world_id, ...)` propagates only `world:world_0` (always),
    appends `scope:world`
  - `_L5_MAX_RESULTS = 8` (same as L6's L4 cap)

- `world_system/config/prompt_fragments_l7.json` — copy of
  `prompt_fragments_l6.json`, s/nation/world/ in prose, s/region/nation/ in
  examples. `_l7_core`, `_l7_output`, `l7_context:world_summary`,
  `l7_example:world`. Address-tag exclusion unchanged.

- `world_system/tests/test_layer7.py` — copy of `test_layer6.py`, then:
  - `_setup_geo_registry_single_world` — single world, 2 nations, 2 regions per nation
  - `_make_l6_event(nation_id=, world_id=, ...)` helper emits
    `world:/nation:/scope:nation` + content tags
  - **Crucial arithmetic**: L6 events carry `scope:nation` at pos 0
    (skipped), so first content tag at pos 1 = 8 pts. Threshold 200 = **25
    events** (same as L6 for consistency — can be tuned later).
  - Test classes: `TestWorldSummaryEvent`, `TestLayer7Summarizer`,
    `TestLayer7XmlBlock`, `TestFilterRelevantL5`, `TestLayer7Manager`
    (simpler: no multi-world isolation, only one world), `TestPromptAssemblerL7`,
    `TestLayer7Integration`.
  - Expected: ~25-30 tests (fewer than L6 because only one world bucket).

**Modified files**:
- `world_system/world_memory/event_schema.py`:
  - Add `WorldSummaryEvent` dataclass. Fields: `summary_id, world_id,
    created_at, narrative, severity, dominant_activities, dominant_nations
    (List[str]), world_condition, source_nation_summary_ids, relevant_l5_ids,
    tags, supersedes_id`. Factory `create(world_id=, ...)`.
  - Update module header to list `WorldSummaryEvent` at Layer 7.

- `world_system/world_memory/world_memory_system.py`:
  - Import `Layer7Manager`.
  - Add attribute `self.layer7_manager: Optional[Layer7Manager] = None`.
  - Section `# 7f. Layer 7 Manager (world summarization)` after L6 init.
    Initialize with `(layer_store, geo_registry, wms_ai, trigger_registry)`.
  - Wire `self.layer6_manager.set_layer7_callback(
    self.layer7_manager.on_layer6_created)` (already has the hook!).
  - Add `# Layer 7 world summarization check` block to periodic `update()`
    after the L6 drain.
  - Add `Layer7Manager.reset()` to `shutdown()`.

- `world_system/world_memory/layer6_manager.py`:
  - Already has `self._layer7_callback = None` and `set_layer7_callback()`
  - In `_store_summary`, after LayerStore write, invoke
    `self._layer7_callback(l6_event_dict)` wrapped in try/except
    (mirror existing L4→L5 pattern).

- `world_system/world_memory/wms_ai.py`:
  - Verify `wms_layer7` entry exists in `LAYER_CONFIG` (it should from migration).
    If not, add: temperature 0.6, max_tokens 600, description "Layer 7:
    world-level summaries".

- `world_system/config/backend-config.json`:
  - Verify `wms_layer7` entry exists (should already be there).

- `world_system/config/memory-config.json`:
  - Add `"layer7"` section:
    ```json
    {
      "trigger_threshold": 200,
      "max_l6_per_world": 20,
      "max_l5_relevance": 8,
      "description": "Layer 7 world summarization config (game World tier, singleton). Same WeightedTriggerBucket pattern as Layer 6 but single world bucket. trigger_threshold defaults to 200 (same as Layer 6 for tuning flexibility). max_l6_per_world = max L6 nation events included in prompt. max_l5_relevance = max Layer 5 supporting-detail events."
    }
    ```

- `world_system/world_memory/prompt_assembler.py`:
  - Add `assemble_l7(data_block, event_tags)` method mirroring `assemble_l6`.
    Uses `_l7_core` / `l7_context:world_summary` / `l7_example:world` /
    `_l7_output` fragments. Tags `["layer:7", "scope:world"]`.
  - Add `get_l7_fragment(key)` method and `self._l7_fragments: Dict[str, Any] = {}`.
  - Extend `load()` to read `world_system/config/prompt_fragments_l7.json`.

- `world_system/docs/HANDOFF_STATUS.md` — update test count (166 → ~190-200
  once L7 tests added), update pipeline diagram, add Layer 7 completion
  section (after implementation), remove this playbook, sketch Layer 8
  (probably not needed, but document why).

- `world_system/docs/ARCHITECTURAL_DECISIONS.md` — add Document History
  entry for Layer 7 completion.

### Address-tag contract (Layer 7 specific)

1. **Input**: L6 events carry `world:world_0` + `nation:nation_X` tags.
2. **Output**: L7 drops `nation:` on summary. Retains only `world:world_0`.
3. **Scope tag**: Output includes `scope:world` (single tier).
4. **LLM rewrite**: Partition before call, re-attach after, filter output
   with `is_address_tag()`.

### Testing strategy

```bash
# After Phase 1 (dataclass + summarizer):
python -m unittest world_system.tests.test_layer7.TestWorldSummaryEvent \
    world_system.tests.test_layer7.TestLayer7Summarizer

# After Phase 2 (manager + integration):
python -m unittest world_system.tests.test_layer7

# Full regression (must stay green):
python -m unittest \
    world_system.world_memory.test_layer3 \
    world_system.tests.test_layer4 \
    world_system.tests.test_layer5 \
    world_system.tests.test_layer6 \
    world_system.tests.test_layer7
```

Expected final count: **~190-200 tests** (54 L3 + 39 L4 + 37 L5 + 36 L6 + 25-30 L7),
all passing.

### Key differences from Layer 6 → Layer 7

| Aspect | Layer 6 | Layer 7 |
|---|---|---|
| Aggregation Tier | Game Nation | Game World |
| Trigger Buckets | Per-nation (many) | Per-world (1) |
| Config Max Events | 40 L5 | 20 L6 |
| is_applicable() | Min 2 L5 events | Min 2 L6 events (or 1?) |
| Tests | 36 | ~25-30 |
| Multi-isolation | YES (test critical) | N/A (only 1 world) |
| LLM Call Path | Identical | Identical |
| Callback | set_layer7_callback() | NONE (final tier) |

### Known gotchas (Layer 7 specific)

- **Single world bucket**: The game always has exactly one World (`world_0`).
  Layer 7 still uses `WeightedTriggerBucket` (named `layer7_world_0`) because
  the architecture is consistent. Multi-world games could extend this.
- **is_applicable threshold**: Layer 7 requires min 2 L6 events OR set to 1?
  Currently matched to L6 (2), but world-scope aggregation might justify
  threshold-of-1 (any event triggers). Decision deferred to implementation.
- **Relevance filtering**: Two-layers-down visibility means L7 sees L6 (full)
  + L5 (fired-tag filtered). Relevance threshold same as L6 (8 L5 events).
- **No Layer 8**: This is the final tier. `set_layer7_callback` exists in
  Layer6Manager but is never invoked by anything.

---

## How to Continue

### For Layer 7 Implementation

1. **Read this entire file** — especially this playbook and the Layer 6/5
   sections for reference patterns.
2. **Read** `WORLD_MEMORY_SYSTEM.md` (§7.4 Layer 6, §7.5 Layer 7 stub) and
   `ARCHITECTURAL_DECISIONS.md` §6 for rules.
3. **Copy Layer 6 code** — start with `layer6_manager.py`, mechanically rename,
   adjust one tier up.
4. **Test early and often** — run test ladder after each phase.
5. **Follow the checklist** in the "File-by-file Implementation Plan" above.

### Current Test Status

```bash
$ python -m unittest \
    world_system.world_memory.test_layer3 \
    world_system.tests.test_layer4 \
    world_system.tests.test_layer5 \
    world_system.tests.test_layer6 -v

Ran 166 tests in 0.2s
OK (54 L3 + 39 L4 + 37 L5 + 36 L6)
```

### Commands to Know

```bash
# Full test ladder (run frequently)
python -m unittest world_system.world_memory.test_layer3 \
    world_system.tests.test_layer4 world_system.tests.test_layer5 \
    world_system.tests.test_layer6 -v

# Individual layer tests (for debugging)
python -m unittest world_system.tests.test_layer6 -v

# After creating Layer 7 code, add to ladder:
python -m unittest world_system.world_memory.test_layer3 \
    world_system.tests.test_layer4 world_system.tests.test_layer5 \
    world_system.tests.test_layer6 world_system.tests.test_layer7 -v

# LLM testing (requires ANTHROPIC_API_KEY set)
export ANTHROPIC_API_KEY="sk-ant-..."
python -m unittest world_system.tests.test_layer7.TestLayer7Integration -v
```

### Critical Review Points (Before Committing Layer 7)

- [ ] `WorldSummaryEvent` dataclass has 12 fields (matching L6 pattern)
- [ ] `Layer7Manager._resolve_world_id_from_tags()` scans for `world:X` tag
- [ ] `Layer7Manager._upgrade_narrative()` uses partition/filter pattern
- [ ] `_build_tags()` propagates only `world:world_0` (never hallucinated nations)
- [ ] Tests verify single-bucket behavior (only layer7_world_0 triggers)
- [ ] Prompt fragments (`_l7_core`, etc.) loaded in PromptAssembler.load()
- [ ] `memory-config.json` layer7 section has trigger_threshold, max_l6_per_world, max_l5_relevance
- [ ] L6→L7 callback wired in `WorldMemorySystem.__init__()`
- [ ] All 166 existing tests still pass (regression check)
- [ ] New tests cover: dataclass, summarizer, manager, prompts, integration
- [ ] Documentation updated (HANDOFF_STATUS.md, ARCHITECTURAL_DECISIONS.md)
