# Architectural Decisions — World Memory System & Sibling Systems

**Status**: Living document
**Last updated**: 2026-04-13

This document captures the top-level architectural decisions about what is and
isn't part of the layered memory pipeline. Read this before extending or
integrating systems under `world_system/`.

---

## 1. Naming: "WMS" is the Central System, not the Entire System

Historically, everything under `world_system/` has been informally called
"the WMS" (World Memory System). This is misleading. The **World Memory
System** proper — the 7-layer event/narrative pipeline in
`world_system/world_memory/` — is the **central system** because it holds the
vast majority of persistent world data. But it is not the whole of
`world_system/`.

The broader `world_system/` package is more accurately called the **World
System** and contains several cooperating subsystems:

| Subsystem | Location | Role |
|---|---|---|
| **World Memory System (WMS)** | `world_memory/` | Event-driven 7-layer narrative pipeline. Append-only. Central data hub. |
| **FactionSystem** | `living_world/factions/` | State-driven reputation tracker. Needs a full overhaul (see §2). |
| **EcosystemAgent** | `living_world/ecosystem/` | Stateful resource-availability tracker. Candidate for removal or reframing (see §3). |
| **NPCAgentSystem / NPCMemory** | `living_world/npc/` | Per-NPC dialogue and memory state. |
| **BackendManager** | `living_world/backends/` | LLM abstraction layer shared by all consumers. |

When this documentation refers to "the WMS" or "the layers" it means
`world_memory/` specifically. When it refers to "the World System" it means
the whole of `world_system/`.

The WMS is **one tracker among several**. It is the largest and the most
central, but not exclusive. Other trackers coexist with it and do not feed
into the layer pipeline unless an evaluator explicitly bridges them.

---

## 2. FactionSystem — Incomplete, Needs Full Overhaul

### Current state

`world_system/living_world/factions/faction_system.py` (464 lines) implements
a basic reputation tracker with 4 hardcoded factions, scalar reputation
(-1.0 to +1.0), ripple effects between allied/hostile factions, and milestone
thresholds. It subscribes to `ENEMY_KILLED`, `ITEM_CRAFTED`,
`RESOURCE_GATHERED`, `LEVEL_UP` and adjusts reputation per event type.

`world_system/config/faction-definitions.json` defines the current 4
factions: `village_guard`, `crafters_guild`, `forest_wardens`,
`miners_collective`.

### Decision: Mark as INCOMPLETE

**`faction-definitions.json` is a placeholder, not a finished design.** It
was created without a directive and will change drastically. The current
content should be treated as throwaway fixtures — useful only for keeping
the system compiling and the tests passing.

Future iteration will need:
- Many more factions with meaningful differentiation
- Detailed territory/member relationships (eventually comparable in depth
  to the geography system in `config/geographic-map.json`)
- Nuanced reputation axes (not just a single scalar)
- Multi-dimensional inter-faction state (not just allied/hostile scalars)
- Inner-faction dynamics (power struggles, leadership, splinter groups)
- Faction-driven quest generation hooks
- Faction-specific dialogue tone modifiers

**Nothing in Layer 5+ work should assume FactionSystem is a reliable data
source.** When the overhaul happens, the consumer contract will change.

### Decision: FactionSystem is OUTSIDE the layer pipeline

FactionSystem is a **separate event/stat tracker**. It listens to the same
GameEventBus the WMS listens to, but runs an independent projection
(reputation math). It does **not** feed into the layer pipeline:

- `FACTION_REP_CHANGED` and `FACTION_MILESTONE_REACHED` events are **not**
  in `BUS_TO_MEMORY_TYPE` in `event_schema.py`. They are silently dropped
  by the EventRecorder. **Leave it this way.**
- No Layer 2 evaluator reads FactionSystem state.
- The `faction_narrative` Layer 3 consolidator does not query FactionSystem
  — it infers faction relevance from L2 event tags independently.
- Layer 5 (region summaries) does **not** read `faction_standings` from
  FactionSystem. Region narratives are built purely from the layer pipeline.

Think of FactionSystem as a **synchronous query API for NPCs and quest
generation** (current game state: "what's my rep with the Miners?"). The
WMS is an **asynchronous historical narrative pipeline** (past story:
"what has happened in this province?"). They have different shapes and
different consumers.

There is minor overlap — the WMS counts quest completions as events, and
FactionSystem adjusts rep for those same events — but that's fine.
Overlap on "quantity of quests" is expected. The WMS does not track
"quality of quests" or "faction sentiment towards quest giver" — those
belong to FactionSystem and dialogue systems respectively.

### Decision: Future narrative systems read from BOTH

Layer 5+ narratives will eventually be enriched by a **parallel narrative
layer** (not the WMS event layer) that reads the WMS *and* other trackers
(FactionSystem, EcosystemAgent, NPCMemory) and weaves them together.

The WMS layers themselves are **events only** — they do not reach out to
state trackers. The parallel narrative layer is a future concern; for now,
implement the WMS layers purely, and defer cross-system narrative weaving.

---

## 3. EcosystemAgent — Candidate for Reframing

### Current state

`world_system/living_world/ecosystem/ecosystem_agent.py` (399 lines) tracks
per-biome aggregate resource counts with regeneration rates. It subscribes
to `RESOURCE_GATHERED` and publishes `RESOURCE_SCARCITY` / `RESOURCE_RECOVERED`
events at 70% / 90% depletion thresholds.

`world_system/world_memory/evaluators/ecosystem_resource_depletion.py`
independently counts `resource_gathered` and `node_depleted` events per 3×3
chunk ecosystem and produces L2 narratives at 50% / 75% / 90% / 100%.

### Problem: Three trackers, one reality

There are currently three independent depletion trackers for the same
underlying world state:

1. **NaturalResource** (per-node HP / respawn timers) — ground truth in
   the game world.
2. **EcosystemAgent** (per-biome aggregate counts, fake regeneration) —
   not connected to real node spawns.
3. **Layer 2 evaluator** (per 3×3 chunk, counting events) — narrative
   output.

These can and probably will drift from each other.

### Decision: EcosystemAgent is NOT part of the WMS layers

EcosystemAgent is **not part of the WMS**. Like FactionSystem, it does
**not** feed into the layer pipeline:

- `RESOURCE_SCARCITY` and `RESOURCE_RECOVERED` are **not** in
  `BUS_TO_MEMORY_TYPE`. Leave it this way.
- The `ecosystem_resource_depletion` Layer 2 evaluator is the only
  layer-pipeline observer of resource pressure. It operates on
  `resource_gathered` / `node_depleted` raw events independently.

### Decision (tentative): EcosystemAgent should become a queryable tool of the broader World System, not a stateful agent

The current architecture has EcosystemAgent pretending to be a simulation
(with tick-based regen and aggregate counts) but it is disconnected from
the real game state (NaturalResource). This is a bad shape.

The likely future is:

- **Delete EcosystemAgent's state-tracking code** (the `current_total`,
  regeneration tick, scarcity detection).
- Replace it with a thin **query API over the actual World System**: "what
  resources currently exist in biome X?" — computed by scanning loaded
  chunks and querying `NaturalResource` instances.
- Optionally keep the `RESOURCE_SCARCITY` / `RESOURCE_RECOVERED` event
  types, but emit them from wherever the real scarcity is detected
  (possibly inside the world chunk manager).

This reframing is **not blocking Layer 5 work**. For now, EcosystemAgent
stays where it is, and Layer 5 ignores it. Mark this as a future cleanup.

### Why ecosystem is iffier than factions

Factions have genuinely distinct data that the WMS doesn't and shouldn't
track (numeric reputation math, ripple algebra). They earn a separate
system on merit.

Ecosystem doesn't. Its "state" is already present elsewhere (in the world
chunks and the raw event stream). EcosystemAgent mostly duplicates that
state in a less accurate form. A query tool over the real world state
would replace it entirely without loss.

---

## 4. Rule: WMS Layers Are Events Only

The WMS layers (L1 stats → L2 interpretations → L3 district
consolidations → L4 province summaries → L5 region summaries →
L6 nation summaries → L7 world summaries) form a strictly
event-driven pipeline. Each layer:

1. Receives events from the layer below (or from the raw event pipeline
   for L2).
2. Produces events from those inputs via evaluators / consolidators /
   summarizers.
3. Stores them in `LayerStore` (`layer{N}_events` + `layer{N}_tags`).
4. Optionally upgrades narrative + tags via the LLM.

They do **not** reach out to FactionSystem, EcosystemAgent, NPCMemory, or
any other state tracker. If a layer wants faction-awareness, it must come
from the tags on events that flowed up the pipeline — not from a query to
FactionSystem.

This rule exists for three reasons:

1. **Determinism**: The layer pipeline is pure-functional with respect to
   its inputs. Given the same L(N-1) events, it produces the same L(N)
   events. State-tracker queries would break this.
2. **Isolation**: FactionSystem overhauls should not ripple into layer
   logic.
3. **Future parallel narrative layer**: The weaving of WMS output with
   other tracker data is a separate concern that will live in its own
   system.

---

## 5. Layer 5+ Directive

When implementing Layer 5 (and later 6, 7):

- **Do NOT** wire `FACTION_REP_CHANGED`, `FACTION_MILESTONE_REACHED`,
  `RESOURCE_SCARCITY`, `RESOURCE_RECOVERED` into `BUS_TO_MEMORY_TYPE`.
- **Do NOT** read from FactionSystem or EcosystemAgent.
- **Do NOT** try to populate the `faction_standings` / `economic_summary`
  / `player_reputation` fields from anywhere outside the WMS pipeline.
  Either rename/drop those fields or leave them empty for now.
- **Do** keep the pipeline pure: L5 reads L4 (full) + L3 (filtered, two
  layers down), produces region-scoped events, writes to LayerStore.
- **Do** follow the L4 pattern (WeightedTriggerBucket, LLM content-tag
  rewrite with address-tag preservation, per-region buckets).
- **Do** treat address tags (`world:`, `nation:`, `region:`,
  `province:`, `district:`, `locality:`) as FACTS. Never let the LLM
  touch them. See §6.

Future evaluators for faction-adjacent or ecosystem-adjacent concerns
can be added later. The WMS does not fully require them to function — the
L2-L4 pipeline works on raw gameplay events (combat, gathering, crafting,
progression, exploration) which are already wired in.

---

## 6. Address Tags Are Facts, Not LLM Output

The WMS layer pipeline maps 1:1 to the game's geographic hierarchy:

```
World → Nation → Region → Province → District → Locality (sparse POI)
```

This is 6 tiers (5 guaranteed per chunk plus optional Locality).
See `systems/geography/models.py` and
`world_system/world_memory/geographic_registry.py::RegionLevel`.

### Rule: one tier per layer

Each WMS layer aggregates at exactly one tier of the hierarchy. As
events flow up the pipeline, each layer **drops the finest address
tag on its output** because the summary is now summed across that
tier's children.

| Layer | Aggregation tier | Drops on output | Retains |
|---|---|---|---|
| L2 | capture | — | world, nation, region, province, district, locality |
| L3 | game District | locality | world, nation, region, province, district |
| L4 | game Province | district | world, nation, region, province |
| L5 | game Region | province | world, nation, region |
| L6 (future) | game Nation | region | world, nation |
| L7 (future) | game World | nation | world |

### Rule: addresses are facts, never LLM-synthesized

Every event's address is determined deterministically at **Layer 2
capture time** by looking up the chunk at `(position_x, position_y)`
in `GeographicRegistry.get_full_address()`. From that point on:

1. Higher layers **propagate** address tags by copying them from input
   events — they never synthesize new ones and never re-parent.
2. The LLM at Layer 4 and Layer 5 is given only **content tags** for
   its rewrite step. The layer code partitions `summary.tags` into
   address/content halves before calling the LLM, then re-attaches the
   address half after the rewrite returns. Any address tag the LLM
   emits in its output is discarded.
3. The `region:` / `province:` / etc. tag on a layer's output is
   **always** the aggregation target for that layer — never whatever
   the LLM wrote.

This guarantees that address resolution is:
- **Deterministic**: same inputs always produce the same address.
- **Simple**: no parent-chain walking at higher layers, just tag
  lookup (e.g. `Layer5Manager._resolve_region_id_from_tags` reads the
  `region:X` tag directly).
- **Safe**: the LLM cannot invent geographic tags, drop them, or
  cross-wire events to the wrong place.

### Address tag prefixes (reserved)

The following tag namespaces are reserved for address facts. No layer
and no LLM prompt is permitted to create, rewrite, reorder, or drop
them outside their layer's own aggregation step:

- `world:`, `nation:`, `region:`, `province:`, `district:`, `locality:`

Content prefixes (LLM-rewritable) include `domain:`, `sentiment:`,
`trend:`, `intensity:`, `resource_status:`, `threat_level:`,
`urgency_level:`, `event_status:`, `player_impact:`, `species:`,
`terrain:`, `discipline:`, `tier:`, etc. See `tag_library.py` for the
full list.

---

## 7. Document History

- **2026-04-16**: Added §6 formalizing the 1-tier-per-layer
  aggregation rule and address-tag immutability rule. Aligned WMS
  hierarchy 1:1 with the game's geography system
  (`systems/geography/models.py`). Added `WORLD` and `REGION`
  `RegionLevel` values, shifted `load_from_world_map` to correct
  tier mapping, renamed `RealmSummaryEvent → RegionSummaryEvent`,
  retargeted Layer 5 from world-aggregation to region-aggregation.
  `EventStore` schema bumped to v2 (adds `region_id`/`nation_id`/
  `world_id` columns; old databases fail fast with a rebuild
  message). L4/L5 `_upgrade_narrative` partitions tags into
  address vs content and only hands content to the LLM.
- **2026-04-13**: Initial creation. Captures separation of FactionSystem /
  EcosystemAgent from the WMS layer pipeline, marks
  `faction-definitions.json` as placeholder, reframes "WMS" as central
  rather than whole. Written while preparing Layer 5 implementation.
