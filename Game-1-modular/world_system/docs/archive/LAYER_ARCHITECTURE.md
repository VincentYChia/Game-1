# World System — 7-Layer Architecture

**Created**: 2026-03-24
**Status**: Design — incorporates developer feedback on trigger cadence, evaluator depth, and geographic scale

---

## Layer Overview

Each layer compresses information upward. Lower layers are voluminous and granular. Higher layers are concise and impactful. The world is tracked — not just the player.

| Layer | Name | Geographic Scale | Data Type | Trigger Cadence |
|:---:|-------|-----------------|-----------|----------------|
| 1 | Numerical Stats | None (global counters) | Cumulative integers/floats | Every event |
| 2 | Structured Events | Chunk / Locality | Timestamped facts (SQLite rows) | Every event |
| 3 | Simple Interpretations | Locality / District | One-sentence narratives | Milestone thresholds |
| 4 | Connected Interpretations | District / Province | Cross-domain narratives | Layer 3 accumulation |
| 5 | Principality Summaries | Province | Gross summaries, notable patterns | Layer 4 accumulation |
| 6 | Regional / National State | Multi-province / Realm | Faction landscapes, economic state | Layer 5 accumulation |
| 7 | World State | Entire world | Canonical narrative threads, world identity | Major events only |

### The Compression Principle

Each layer exists to **condense** the layer below into better information transfer. A consumer at Layer 5 should never need to read Layer 2 directly — Layer 5's summaries encode everything relevant at that scale.

Layer N can see:
- **Layer N-1**: Full visibility (its direct input)
- **Layer N-2**: Limited visibility (for context and cross-referencing)

This "two layers down" rule prevents evaluators from needing raw event streams while still grounding their interpretations in real data.

---

## Trigger Thresholds

### Layer 2 → Layer 3 Triggers (Milestone Series)

Replaces the prime-number trigger. Fixed milestones provide predictable evaluation points with logarithmic spacing:

```
1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000
```

Beyond 100,000: repeat the `1, 2.5, 5, 10` pattern (250000, 500000, 1000000...).

**Design intent**: The biggest behavioral leaps happen at **1, 10, 100, 1000**. The intermediate points (3, 5, 25, 50, 250, 500...) give the system chances to detect patterns without requiring change. A trigger is an **opportunity to evaluate** — not a mandate to produce output.

**Per-occurrence key**: `(actor_id, event_type, event_subtype)` — same as current.

**What hits high counts**: Steps taken, damage dealt, individual resource gathers. Most game actions top out at 1000-10000 in a playthrough. Only movement/damage/basic-gathering would approach 100000.

### Layer 3 → Layer 4 Triggers

Layer 4 evaluators watch for **accumulation of Layer 3 interpretations**, not raw events. Triggers fire when:
- A locality/district accumulates N interpretations of the same category
- Multiple Layer 3 interpretations share geographic proximity within a time window
- A Layer 3 interpretation reaches severity "significant" or higher

Example trigger thresholds for Layer 4:
```
Same category in same district: 3, 5, 10, 25
Cross-category in same district: 2, 5, 10
Any "significant"+ severity: immediate
```

### Layer 4 → Layer 5 Triggers

Layer 5 watches for accumulation across districts within a province:
```
Same pattern across 2+ districts: immediate
Layer 4 "significant"+ in any district: immediate
Periodic province sweep: every 50 game-time units
```

### Layer 5 → Layer 6 and Layer 6 → Layer 7

These fire infrequently — only on major state changes:
- Province-level patterns propagate to realm when 2+ provinces show the same trend
- World state updates only on events that would affect the entire game world

---

## Layer Details

### Layer 1 — Numerical Stats

**Existing system**: `stat_tracker.py` (850+ counters) + `activity_tracker.py` (8 counters)

Pure aggregates. No timestamps, no location, no sequence. Answers "how many total?" instantly.

**Role in the hierarchy**: Fast lookups for Layer 3 evaluators. When a Layer 3 evaluator fires at milestone 100 for wolf kills, it can check Layer 1 to see total kills across ALL species, total kills in this tier, kill streaks, etc. — without scanning Layer 2.

**Not modified by this design**. Layer 1 is read-only input to higher layers.

### Layer 2 — Structured Events

**Existing system**: `event_store.py` — SQLite `events` table with full WHO/WHAT/WHERE/WHEN

Every game action becomes a row with actor, target, position, chunk, locality, district, province, biome, game_time, magnitude, quality, tier, tags, and flexible context JSON.

**Role in the hierarchy**: The source of truth. Layer 3 evaluators query Layer 2 to build their interpretations. Layer 4 may query Layer 2 for limited context (the "two layers down" rule).

**28 event types** mapped from GameEventBus. Geographic enrichment stamps every event with its full address (chunk → locality → district → province → biome).

### Layer 3 — Simple Interpretations

**The first narrative layer**. Evaluators consume Layer 2 events (and glance at Layer 1 for context) to produce one-sentence descriptions of what's happening.

This is where the system transitions from **facts** to **meaning**.

**What Layer 3 evaluators produce**: `InterpretedEvent` — a narrative string with category, severity, geographic scope, affected tags, and expiration.

**What Layer 3 evaluators see**:
- **Full**: Layer 2 events within their lookback window and geographic scope
- **Limited**: Layer 1 aggregate stats for broader context (total kills, total crafts, etc.)

**Key design principle**: An evaluator's job is to describe **what is happening**, not to judge significance across domains. "The wolf population has been devastated in Old Forest" is Layer 3. "The player is systematically clearing all wildlife from the northern forests" is Layer 4 — it requires seeing multiple Layer 3 outputs together.

**Evaluators are broad, not narrow**. A single evaluator may watch multiple event types and produce multiple categories of interpretation. Dual coverage of the same event by different evaluators is expected and encouraged.

See [EVALUATOR_DESIGN.md](EVALUATOR_DESIGN.md) for the full evaluator specification.

### Layer 4 — Connected Interpretations

**The pattern-recognition layer**. Consumes Layer 3 interpretations (and glances at Layer 2 for supporting detail) to detect cross-domain and cross-region connections.

**What Layer 4 does that Layer 3 cannot**:
- See that three forests were decimated recently and they're all in the same region → "The player is decimating the northern forests"
- See that resource depletion AND population decline overlap in one district → "The player is plundering Iron Hills of both wildlife and resources"
- See that a player has both high smithing AND high enchanting Layer 3 outputs → "dual specialty" rather than misclassifying as generalist
- See that combat casualties are concentrated in one area with high danger + low-health events → "The player is struggling in the Eastern Caves"

**Geographic scale**: District to Province. Layer 4 looks at patterns across localities within a district, or across districts within a province.

**Trigger**: Accumulation of Layer 3 interpretations, not raw events.

### Layer 5 — Principality Summaries

**The gross summary layer**. What would a provincial governor know?

Consumes Layer 4 connected interpretations across a province. Produces concise summaries of the state of a geographic area at the province scale.

**Examples**:
- "The northern province has been largely cleared of hostile wildlife. Resource extraction is heavy."
- "The eastern caves remain extremely dangerous. Multiple failed expeditions recorded."
- "Crafting activity in the central province is producing consistently high-quality smithing output."

**Data here is remembered**. Layer 5 summaries represent information notable enough to persist — the kind of thing that affects NPC behavior at range, drives quest generation, and informs faction decisions.

### Layer 6 — Regional / National State

**The political and economic layer**. What would a king or faction leader know?

Aggregates Layer 5 province summaries into realm-wide understanding:
- Faction power balances and territorial influence
- Economic state (which resources are globally scarce, trade pressure)
- Major player reputation and achievements at national scale
- Active conflicts or alliances

**If multiplayer is ever added**: A sub-layer at ~3.5 would track per-player connected interpretations before merging into the shared world state at Layer 4+.

### Layer 7 — World State

**The canonical narrative**. The identity of the world itself.

- Active narrative threads (wars, plagues, discoveries, migrations)
- World themes and tone
- Creation myths and historical events (immutable lore)
- Resolved threads that become history
- The "heart of memory" — what the world IS, not just what happened in it

Layer 7 is the input for thematic content generation. When generating a new chunk, NPC, or quest, the generator asks Layer 7 "what kind of world is this?" and gets back active threads, themes, and tone.

---

## What Each Layer Tracks (Not Just the Player)

The World System tracks the **state of the world**, not just player actions. Every layer records information about:

| Subject | Example at Layer 3 | Example at Layer 5 |
|---------|-------------------|-------------------|
| **Player** | "Player has killed 50 wolves in Old Forest" | "Player has cleared wildlife across the northern province" |
| **Regions** | "Old Forest wolf population is declining" | "Northern province ecology is destabilized" |
| **Resources** | "Iron ore is scarce in Iron Hills" | "Metal resources are strained across the eastern province" |
| **NPCs/Factions** | "Player is recognized by Village Guard" | "Village Guard influence is strongest in central province" |
| **Ecosystem** | "Wolf spawns reduced in Old Forest" | "Predator populations recovering in southern province" |

This distinction matters: even without the player doing anything, the world has state. Resource regeneration, faction territory, NPC routines — these exist independently and are tracked through the same layer system.

---

## Storage Summary

| Layer | Storage | Retention |
|:---:|---------|-----------|
| 1 | In-memory dicts (stat_tracker.py), serialized to save JSON | Permanent — cumulative counters never pruned |
| 2 | SQLite `events` table + `event_tags` | Pruned by retention policy. Milestones and first-occurrences preserved. |
| 3 | SQLite `interpretations` table + `interpretation_tags` | Superseded entries archived. Active interpretations expire. |
| 4 | SQLite `connected_interpretations` table (new) | Superseded on update. Province-scoped. |
| 5 | SQLite `province_summaries` table (new) | Rolling window. Latest N per province. |
| 6 | SQLite `realm_state` table (new) | Single row per realm, updated in place. |
| 7 | SQLite `world_narrative` table (new) + `narrative_threads` | Permanent. Threads may decay to "forgotten" but row persists. |

See [STORAGE_SCHEMA.md](STORAGE_SCHEMA.md) for full table definitions.
