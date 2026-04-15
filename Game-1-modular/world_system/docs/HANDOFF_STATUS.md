# World Memory System — Handoff Status

**Date**: 2026-04-16
**Branch**: `claude/review-handoff-status-XG5iC`
**Phase**: Layers 1-5 operational on a corrected 6-tier hierarchy
(`World → Nation → Region → Province → District → Locality`). Layer 6
is the next task — a mechanical copy of Layer 5's pattern one tier
coarser. See the **Layer 6 Implementation Playbook** near the end of
this document.
**Tests**: 130 passing (54 Layer 3 + 39 Layer 4 + 37 Layer 5, 0 failures)
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

## Layer 6 Implementation Playbook (Next Task)

**Aggregation tier**: game Nation (parent of game Region). Layer 6
consolidates Layer 5 region summaries across every region within one
game Nation. Drops `region:` on output, retains `world:` and
`nation:`.

**Key insight**: Layer 6 is a **mechanical copy of Layer 5's pattern**,
one tier coarser. The architecture is settled; this is a 1–2 day
implementation task, not a design task. Every part has a proven
template.

### File-by-file plan

All tier-specific constants live in `geographic_registry.py` already
(`ADDRESS_TAG_PREFIXES`, `RegionLevel.NATION`, `RegionLevel.REGION`,
`propagate_address_facts`, `is_address_tag`,
`partition_address_and_content`). Do NOT re-declare them.

**New files**:
- `world_system/world_memory/layer6_manager.py` (~550 lines) — copy
  of `layer5_manager.py`, then:
  - `BUCKET_PREFIX = "layer6_nation_"`
  - Class renamed `Layer6Manager`
  - `_max_l5_per_nation` config key (fallback default 40)
  - `_min_regions_contributing` optional quorum gate
  - `on_layer5_created(l5_event_dict)` instead of `on_layer4_created`
  - `_resolve_nation_id_from_tags` — trivially scans for `nation:X`
  - `_fetch_l5_events(nation_id, ...)` queries `layer=5` with
    `tags=[f"nation:{nation_id}"]`
  - `_query_relevant_l4(nation_id, fired_tags, l5_events)` — two
    layers down, queries layer=4 by the same nation: tag, passes to
    `Layer6Summarizer.filter_relevant_l4`
  - `_summarize_nation` analog of `_summarize_region`
  - `_build_geo_context` returns `{"nation_name": ..., "regions": [...]}`
  - `_upgrade_narrative` uses `partition_address_and_content` +
    `is_address_tag` (identical shape to L5)
  - `_store_summary` writes category `"nation_summary"` to
    `layer6_events`
  - `_find_supersedable` reads `layer6_events` where category =
    `"nation_summary"`
  - Expose a `set_layer7_callback` hook for future L7 wiring

- `world_system/world_memory/layer6_summarizer.py` (~500 lines) —
  copy of `layer5_summarizer.py`, then:
  - Class renamed `Layer6Summarizer`
  - `summarize(..., nation_id=...)` returns `NationSummaryEvent`
  - `is_applicable(..., nation_id=...)` — min 2 L5 events
  - `build_xml_data_block` root element `<nation name="...">`,
    children `<region name="...">`, cross-region bucket
    `<cross-region>`
  - `filter_relevant_l4` analog of `filter_relevant_l3` (same
    fired-tag overlap algorithm, different input layer)
  - `_extract_dominant_activities` unchanged
  - `_extract_dominant_regions` replaces `_extract_dominant_provinces`
    (scans for `region:` tags)
  - `_determine_nation_condition` — same severity/threat classifier
    as L5, renamed
  - `_build_tags(nation_id, ...)` uses
    `propagate_address_facts(l5_events, (RegionLevel.WORLD,
    RegionLevel.NATION))` — note NATION is the layer's own target, so
    it's redundant to propagate it; we emit `nation:{nation_id}`
    explicitly from the known id instead. Only propagate `WORLD`.
    `tags.append(f"nation:{nation_id}")`, `tags.append("scope:nation")`
  - `_L4_MAX_RESULTS = 8` (same as L5's L3 cap)

- `world_system/config/prompt_fragments_l6.json` — copy of
  `prompt_fragments_l5.json`, s/region/nation/ in prose, s/province/region/
  in examples, version bump. `_l6_core`, `_l6_output`,
  `l6_context:nation_summary`, `l6_example:nation`. Address-tag
  exclusion instructions unchanged ("do NOT include any address tags
  … those are facts").

- `world_system/tests/test_layer6.py` — copy of `test_layer5.py`,
  then:
  - `_setup_geo_registry_multi_nation` — two-nation fixture. Both
    under world_0. Each nation has a region, each region has one or
    two provinces. Pattern: world_0 → {nation_1, nation_2} → region
    → province.
  - `_make_l5_event(region_id=, nation_id=, world_id=, ...)` helper
    emits `world:/nation:/region:/scope:region` + content tags
    (mirrors `_make_l4_event` in test_layer5, shifted one tier).
  - **Crucial arithmetic**: after the L5 summarizer, typical L5
    events carry `scope:region` at position 0 of what survives
    address-stripping (since addresses are stripped). `scope:` is
    skipped by the weighted bucket → first content tag lands at
    position 1 = 8 pts. Threshold 100 = **13 events**, same as L5.
  - Test classes: `TestNationSummaryEvent`, `TestLayer6Summarizer`,
    `TestLayer6XmlBlock`, `TestFilterRelevantL4`, `TestLayer6Manager`
    (includes `test_multi_nation_isolation`), `TestPromptAssemblerL6`,
    `TestLayer6Integration`.

**Modified files**:
- `world_system/world_memory/event_schema.py`:
  - Add `NationSummaryEvent` dataclass at the end of the summary-event
    block. Fields: `summary_id, nation_id, created_at, narrative,
    severity, dominant_activities, dominant_regions (List[str]),
    nation_condition, source_region_summary_ids, relevant_l4_ids,
    tags, supersedes_id`. Factory `create(nation_id=, ...)`.
  - Update the module header comment to list NationSummaryEvent at
    Layer 6.

- `world_system/world_memory/world_memory_system.py`:
  - Import `Layer6Manager`.
  - Add attribute `self.layer6_manager: Optional[Layer6Manager] = None`.
  - Section `# 7e. Layer 6 Manager (nation summarization)` after
    the existing L5 init block. Initialize with
    `(layer_store, geo_registry, wms_ai, trigger_registry)`.
  - Wire `self.layer5_manager.set_layer6_callback(
    self.layer6_manager.on_layer5_created)` — requires adding
    `set_layer6_callback` on `Layer5Manager` and having
    `Layer5Manager._store_summary` invoke the callback after
    writing to LayerStore, mirroring how
    `Layer4Manager._store_summary` already calls the L5 callback.
  - Add `# Layer 6 nation summarization check` block to the
    periodic `update()` path after the L5 drain.
  - Add `Layer6Manager.reset()` to `shutdown()`.

- `world_system/world_memory/layer5_manager.py`:
  - Add `self._layer6_callback = None` in `__init__`.
  - Add `set_layer6_callback(callback)` method.
  - In `_store_summary`, after the LayerStore write, invoke
    `self._layer6_callback(l5_event_dict)` where the dict mirrors
    what Layer4 passes to L5 (id, tags, game_time, category,
    severity, narrative). Wrap in try/except that prints an error
    and keeps the L5 write intact on callback failure (same pattern
    as `Layer4Manager._store_summary`).

- `world_system/world_memory/wms_ai.py`:
  - Update the `wms_layer6` entry in the `_LAYER_CONFIG` dict if it
    exists; otherwise add one. Temperature 0.5, max_tokens 500,
    description `"Layer 6: nation-level summaries"` (already done
    in the 2026-04-16 migration, verify).

- `world_system/config/backend-config.json`:
  - Already has a `wms_layer6` entry pointing at claude with
    description `"WMS Layer 6: nation-level summaries"`. Verify no
    changes needed.

- `world_system/config/memory-config.json`:
  - Add a `"layer6"` section mirroring `"layer5"`. Defaults:
    ```json
    {
      "trigger_threshold": 150,
      "max_l5_per_nation": 40,
      "max_l4_relevance": 8,
      "min_regions_contributing": 1,
      "description": "Layer 6 nation summarization config (game Nation tier). Same per-nation WeightedTriggerBucket pattern as Layer 5 but one tier coarser. trigger_threshold defaults to 150 (higher than Layer 5) because nation summaries should be rarer than region summaries."
    }
    ```
  - **Do not tune thresholds** — defaults are placeholders, real
    tuning comes later after the full WMS is up and can be
    exercised.

- `world_system/world_memory/prompt_assembler.py`:
  - Add `assemble_l6(data_block, event_tags)` method mirroring
    `assemble_l5`. Uses `_l6_core` / `l6_context:nation_summary` /
    `l6_example:nation` / `_l6_output` fragments. Tags
    `["layer:6", "scope:nation"]`. Tag cascade includes all lower
    layer fragments (same `_collect_all_tag_fragments` call).
  - Add `get_l6_fragment(key)` method and
    `self._l6_fragments: Dict[str, Any] = {}`.
  - Extend `load()` to read
    `world_system/config/prompt_fragments_l6.json`.

- `world_system/world_memory/tag_library.py`:
  - Optional — add a `"nation_condition"` tag category under Layer 6
    if the summarizer emits `nation_condition:X` tags (mirroring the
    `region_condition:X` pattern at L5).

- `world_system/docs/HANDOFF_STATUS.md` — update the test count
  (130 → ~160 once L6 tests are added), add L6 to the pipeline
  diagram, add the Layer 6 section after Layer 5.

- `world_system/docs/ARCHITECTURAL_DECISIONS.md` — add a note in the
  §7 Document History confirming L6 completion.

### Address-tag contract (reminder — do not deviate)

1. **Address tags are facts**. The `nation:X` tag on every L5 event
   is propagated from L2 capture. Layer 6's trigger bucket reads it
   directly — no parent-chain walk.
2. **Layer 6 output address tags**: `world:world_0` (propagated from
   any input), `nation:{layer's own target}`. **Drops**: `region:`,
   `province:`, `district:`, `locality:`.
3. **LLM rewrites CONTENT tags only**. Use
   `partition_address_and_content(summary.tags)` before the LLM
   call; re-attach `address_tags` after; filter LLM output with
   `is_address_tag` to drop any hallucinated address tags.
4. **No new tag-prefix constants**. Import
   `ADDRESS_TAG_PREFIXES` from `geographic_registry`.

### Testing ladder (run these in order as you build)

```bash
# After Phase 1 (dataclass + summarizer skeleton):
python -m unittest world_system.tests.test_layer6.TestNationSummaryEvent \
    world_system.tests.test_layer6.TestLayer6Summarizer

# After Phase 2 (manager + integration):
python -m unittest world_system.tests.test_layer6

# Full regression (must stay green throughout):
python -m unittest world_system.world_memory.test_layer3 \
    world_system.tests.test_layer4 \
    world_system.tests.test_layer5 \
    world_system.tests.test_layer6
```

Expected final count: **~160 tests** (54 L3 + 39 L4 + 37 L5 + ~30 L6),
all passing.

### Known gotchas

- The `scope:province` → pos-0-skip arithmetic from L5's test file
  applies identically at L6: L5 summarizer emits `scope:region`,
  which is structural and skipped, so the first scoring content tag
  in an L5 event lands at position 1 = 8 pts. Size the trigger tests
  for 13 events × 8 pts = 104 > 100 threshold (or 19 × 8 = 152 > 150
  if you use the higher 150 threshold for L6).
- `Layer5Manager._store_summary` must invoke the L6 callback
  **after** the LayerStore write succeeds, wrapped in try/except.
  Otherwise an L6 error crashes L5 storage. Mirror the existing
  pattern in `Layer4Manager._store_summary`.
- The dormant `province_summaries` table in `event_store.py` is
  still dormant and unused. Do NOT try to repurpose it for L6.
- `WorldMemorySystem.save()` returns `memory_db_path`. Do NOT add
  an L6-specific save field — all L6 state lives in
  `layer6_events`/`layer6_tags` which persist via the existing
  SQLite DB. No schema bump needed.

### Out of scope for the L6 work

- Trigger threshold tuning (deferred until full WMS is built).
- Layer 7 (world-level aggregation — even easier, another mechanical copy).
- BalanceValidator (still designed, not implemented — separate work).
- Faction/economy narrative weaving (per-system narrative layer, not L6).

---

## How to Continue

1. **Read** this file + `WORLD_MEMORY_SYSTEM.md` +
   `ARCHITECTURAL_DECISIONS.md` for design reference
2. **Run tests**: `python -m unittest world_system.world_memory.test_layer3 world_system.tests.test_layer4 world_system.tests.test_layer5 -v`
3. **Next task**: Layer 6 nation-level aggregation — trivial copy of Layer 5's pattern, bucketed by `nation:X` tag, drops `region:` on output, reads `layer5_events`.
4. **Test with Claude**: Set `ANTHROPIC_API_KEY` env var — WmsAI auto-detects and routes to Claude.
