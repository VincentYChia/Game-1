# World System Working Document

**Status**: Active planning — Living World architecture
**Created**: 2026-04-20
**Owner**: Development
**Supersedes as planning doc**: None (this is fresh; the 2026-03-14 `WORLD_SYSTEM_SCRATCHPAD.md` is kept for research citations but its "Tier 1/2/3" framing is retired in favor of the WNS/WES vocabulary below)

---

## Why This Doc Exists

The World Memory System (WMS) is built and storing narratives. Everything downstream of it — the part of the game that *uses* those narratives to make the world react and to generate new content — does not exist yet. This doc is the plan for that downstream half.

The user's framing, preserved verbatim:

> It can broadly split into two parts. **A World Narrative System (WNS)** — in charge of designing and narrative from the World Memory System. **A World Executor System (WES)** — in charge of executing and deciding game realities from the narrative of the WNS. The issue is that it is not a simple clean cut and handoff between the models. They broadly speaking feed into each other.

> The tools of course will likely be agentic themselves. With the most basic level of tools being creating the JSONs for hostiles, skills, nodes, materials, titles, and quests (however these will need their own interconnected system so nothing is orphaned). **The true difficulty of this is the information.**

Everything in this doc orbits those three framings: WNS/WES are coupled, tools generate JSON, and **context assembly is the hard problem**.

---

## Table of Contents

1. [Current Shipped State (Grounding)](#1-current-shipped-state-grounding)
2. [System Architecture: WMS → WNS ↔ WES → Tools → Game](#2-system-architecture)
3. [Trigger Signal Chain (L7 as Fire Point)](#3-trigger-signal-chain)
4. [WNS Design — Narrative Designer](#4-wns-design)
5. [WES Loop — Plan, Reason, Call, Verify](#5-wes-loop)
6. [Tool Architecture (6 Generators)](#6-tool-architecture)
7. [Content Registry (Anti-Orphan Cross-Reference)](#7-content-registry)
8. [Information / Context Flow — The Hard Problem](#8-information-flow)
9. [Open Questions & Decisions Needed](#9-open-questions)
10. [Phased Implementation Roadmap](#10-phased-roadmap)
11. [Appendix: References to Existing Code](#appendix-references)

---

## 1. Current Shipped State (Grounding)

As of this doc, the two integration steps that bridge WMS to the rest of the game **are live on `main`**. Any plan below starts from this baseline — do not re-do these, build on them.

### 1.1 WMS facade passthrough (`get_world_summary()`)

File: [Game-1-modular/world_system/world_memory/world_memory_system.py:642-654](Game-1-modular/world_system/world_memory/world_memory_system.py#L642-L654)

```python
def get_world_summary(self, game_time: Optional[float] = None) -> Dict[str, Any]:
    """High-level world state for narrative/NPC consumers.

    Returns the current ``ongoing_conditions`` set plus aggregate
    counts. Thin passthrough to WorldQuery; exists so consumers can
    depend on the facade rather than reaching into
    world_memory.world_query directly.
    """
    if not self._initialized or not self.world_query:
        return {"ongoing_conditions": [], "total_events_recorded": 0,
                "regions_with_activity": 0}
    t = self._game_time if game_time is None else game_time
    return self.world_query.get_world_summary(t)
```

Returns a dict with three fields, all consumed by downstream systems today:
- `ongoing_conditions` — list of active Layer-2 interpretations (narrative + category + severity)
- `total_events_recorded` — aggregate count from EventStore
- `regions_with_activity` — count of regions whose recent_events buffer is non-empty

This is the **WMS → consumer API surface**. WNS/WES will extend this, but today's callers (NPCAgentSystem) already go through it.

### 1.2 Living-World consumer boot (`_init_world_memory`)

File: [Game-1-modular/core/game_engine.py:4488-4537](Game-1-modular/core/game_engine.py#L4488-L4537)

`_init_world_memory()` now initializes four subsystems in order, each with a non-fatal try/except so boot never hard-fails:

1. `FactionSystem` (via `initialize_faction_systems()`)
2. `WorldMemorySystem` (the pipeline itself, geo map + save dir wired)
3. `BackendManager.initialize()` — resolves Ollama/Claude/Mock routing from `backend-config.json`
4. `NPCAgentSystem.initialize(world_query=..., backend_manager=...)` — depends on the two above

On failure of the Living World consumers, `self.npc_agent_system = None` and dialogue degrades to hardcoded lines. This graceful-degrade pattern is the template WES components should follow.

### 1.3 NPC dialogue routing (`_generate_npc_opening`)

File: [Game-1-modular/core/game_engine.py:1482-1562](Game-1-modular/core/game_engine.py#L1482-L1562)

`handle_npc_interaction()` no longer returns `npc.get_next_dialogue()` directly. It calls a new helper:

```python
def _generate_npc_opening(self, npc) -> str:
    agent = getattr(self, "npc_agent_system", None)
    if agent is None:
        return npc.get_next_dialogue()
    try:
        result = agent.generate_dialogue(
            npc_id=npc.npc_def.npc_id,
            player_input="*approaches and greets you*",
            character=self.character,
            npc_name=npc.npc_def.name,
        )
        if result and result.text:
            return result.text
    except Exception as e:
        print(f"[NPCAgent] generate_dialogue failed for {npc.npc_def.npc_id}: {e}")
    return npc.get_next_dialogue()
```

**Caveat, deliberately left in the code comment**: the call is synchronous. UI blocks for the LLM round-trip. Making it async is one of the P0 items in the roadmap (§10).

### 1.4 What is NOT yet done

- **Quest generation** — deferred per user prompt; needs the WES + Content Registry first.
- **Ecosystem integration** — `EcosystemAgent` exists as a stateless query tool ([world_system/living_world/ecosystem/ecosystem_agent.py](Game-1-modular/world_system/living_world/ecosystem/ecosystem_agent.py)), but WES does not yet route decisions through it. Deferred.
- **L7 WorldSummaryEvent consumer** — L7 fires and stores today, but **no subscriber reads it**. This is the natural hook point for WNS (§3).
- **Async LLM path** — both NPC dialogue and all future WES calls currently block the main thread.

---

## 2. System Architecture

### 2.1 The four layers

```
┌─────────────────────────────────────────────────────────────────┐
│                         THE GAME                                │
│  character, combat, crafting, NPCs, quests, world_system, ...   │
└────────────────┬──────────────────────────────────▲─────────────┘
                 │ events (pub via GameEventBus)    │ new content:
                 │                                  │ JSONs, entities,
                 ▼                                  │ quest hooks
┌─────────────────────────────────────────────────────────────────┐
│              WMS — World Memory System (SHIPPED)                │
│  L1 raw stats → L2 evaluators → L3–L6 consolidation →           │
│  L7 WorldSummaryEvent                                           │
│  API: get_world_summary(), WorldQuery.*, layer_store queries    │
└────────────────┬──────────────────────────────────▲─────────────┘
                 │ "here is what the world feels    │ "here is what
                 │  like right now"                 │  we built"
                 ▼                                  │
┌─────────────────────────┐       ┌──────────────────────────────┐
│  WNS — Narrative        │◄─────►│  WES — Executor              │
│  Designer               │       │                              │
│  (LLM writer)           │       │  Plan → Reason → Call →      │
│                         │       │          Verify              │
│  Outputs: NarrativeBeat │       │  (LLM planner + tool caller) │
└─────────────────────────┘       └──────────────┬───────────────┘
                                                 │ tool calls
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  Tool Layer (6 generators)   │
                                  │  hostiles · skills · nodes · │
                                  │  materials · titles · quests │
                                  │                              │
                                  │  Each: agentic LLM call      │
                                  │  producing JSON + registry   │
                                  │  entry                       │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  Content Registry            │
                                  │  (anti-orphan cross-ref)     │
                                  └──────────────────────────────┘
```

### 2.2 Key split: narrative vs execution

| | **WNS** | **WES** |
|---|---|---|
| **Role** | Interprets WMS state into a story beat | Turns a story beat into game reality |
| **Input** | L7 summaries, ongoing conditions, faction state, geographic context | A WNS beat + current game state + registry index |
| **Output** | `NarrativeBeat` — structured intent (theme, locale, factions, tone, scope) | Tool calls + content JSONs + verification report |
| **LLM role** | Writer / director | Planner / executor / verifier |
| **Frequency** | On each L7 fire (rare, significant) | Any time WES decides the current world needs new content |
| **Stateful?** | Reads state, writes the beat log | Reads state + beat log, writes content |

### 2.3 "Not a clean handoff" — what that means concretely

The user was explicit that WNS and WES feed into each other. Two mechanisms in this architecture honor that:

1. **WES can request narrative clarification.** If a WNS beat is under-specified ("trouble in the north"), WES can call WNS mid-loop with a focused question ("I need a faction name and a resource trigger"). WNS returns a refined beat, WES continues.
2. **WNS can observe WES output.** When WES creates content, the creation itself becomes a WMS event (via `CONTENT_GENERATED` or similar). That flows back through the pipeline and affects the *next* L7 summary. The narrative evolves in response to what the executor produced.

This is a loop, not a pipeline. The architecture diagram's double-arrow between WNS and WES is load-bearing.

### 2.4 Philosophy: LLMs write content, code owns structure

Every LLM call in the system follows the same discipline the WMS layer-7 summarizer already uses (see [layer7_manager.py:442-500](Game-1-modular/world_system/world_memory/layer7_manager.py#L442-L500)):

- **Code builds the prompt and assembles context.** LLMs never see raw SQL results.
- **Code validates every output.** LLM JSON is parsed, schema-checked, and rejected/retried on failure.
- **Address tags (world/nation/region/…) are facts, never LLM-writable.** Content tags can be rewritten.

WES tools are agentic in that they plan multi-step work (see §6), but the framework gives them structured context and enforces structured output. No free-floating prose becomes game state.

---

## 3. Trigger Signal Chain

The WNS/WES loop needs a heartbeat — some signal that says "enough has changed, re-narrate the world." That signal already exists in the WMS and has been engineered to be rare, weighted, and meaningful.

### 3.1 Why L7 is the natural fire point

The WMS L7 trigger mechanism is a weighted, tag-scored bucket per world ([layer7_manager.py:78-165](Game-1-modular/world_system/world_memory/layer7_manager.py#L78-L165)). Default threshold: **200 points**. Each L6 nation summary contributes content-tag points by position:

> Position 1 = 10 pts, Position 2 = 8 pts, Position 3 = 6 pts, Position 4 = 5 pts, Position 5 = 4 pts, Position 6 = 3 pts, Positions 7–12 = 2 pts, Position 13+ = 1 pt.

When any **content tag** (never an address tag — those are facts) crosses 200 points, L7 fires. Address tags are stripped before scoring so domain/intensity/status tags get full positional weight. The net result:

- A quiet world produces **zero** L7 fires — nothing to narrate.
- A burst of activity in a single domain (heavy mining, a war, a plague) produces an L7 fire **only when the pattern is sustained enough to cross threshold across multiple nations**.
- L7 supersedes previous L7 summaries for the same world (see `_find_supersedable`) — only the latest summary is canonical.

This is **exactly the cadence WNS needs**: fire only when something genuinely world-shaping has accumulated, not on every event.

### 3.2 The signal chain end-to-end

```
Player action (e.g., kills 50 monsters over an hour)
  └─► StatTracker.record_* (65 recording methods)
        └─► StatStore (SQLite) + L1 raw event
              └─► 33 Layer-2 evaluators fire narrations at thresholds
                    └─► Layer 3-6 consolidators roll up by geography
                          └─► L7 weighted bucket accumulates points
                                └─► threshold crossed (≥200)
                                      └─► Layer7Manager.run_summarization()
                                            └─► WorldSummaryEvent stored
                                                  └─► 🔔 HOOK POINT: WNS
```

The hook point is currently unsubscribed. The WMS writes `WorldSummaryEvent` to the `layer7_events` table and that's the end of the line. **Making WNS a subscriber is step 1 of §10's roadmap.**

### 3.3 What the WorldSummaryEvent carries

From [event_schema.py](Game-1-modular/world_system/world_memory/event_schema.py):

```python
@dataclass
class WorldSummaryEvent:
    summary_id: str
    world_id: str                    # always "world_0"
    created_at: float                # game time
    narrative: str                   # LLM-written or template world summary
    severity: str                    # minor, moderate, significant, major, critical
    dominant_activities: List[str]   # e.g. ["mining", "combat"]
    dominant_nations: List[str]      # nation IDs driving the summary
    world_condition: str             # stable | shifting | volatile | crisis
    source_nation_summary_ids: List[str]  # backlinks to contributing L6
```

The tags on the event (stored in `layer7_tags`) carry the content signals that fired — these are the load-bearing "what's happening" signal, far more structured than the narrative prose.

### 3.4 Two trigger modes for WNS/WES (beyond L7)

L7 is the default heartbeat but WNS/WES also need to respond to other cadences:

| Trigger | Source | Use case |
|---|---|---|
| **L7 fire** | `Layer7Manager.run_summarization()` | Default — world-shaping change accumulated |
| **Developer injection** | Manual CLI / debug command | Testing, seeding, directed content development |
| **Session boot** | `GameEngine` startup, post-save-load | Re-hydrate narrative state; optionally produce a "catch up" beat |
| **WES self-request** | WES mid-execution | If a plan step needs a new narrative beat to make sense |

All four produce the same downstream artifact — a `NarrativeBeat` — so the rest of the pipeline stays uniform.

### 3.5 Subscription pattern (concrete)

Preferred subscription mechanism: **add a callback hook to `Layer7Manager`**, mirroring the `_layer7_callback` pattern that Layer6Manager already uses to notify Layer7 ([layer7_manager.py:49-52](Game-1-modular/world_system/world_memory/layer7_manager.py#L49-L52) explicitly notes "No callback beyond Layer 7"). We lift that restriction by adding one:

```python
# In Layer7Manager:
_on_world_summary_callbacks: List[Callable[[WorldSummaryEvent], None]]

def register_world_summary_callback(self, cb): ...

# After _store_summary():
for cb in self._on_world_summary_callbacks:
    try:
        cb(summary)
    except Exception as e:
        print(f"[Layer7] subscriber error: {e}")
```

WNS registers itself during boot. The callback fires synchronously but should queue WNS work for the async runner (see §10.P0). **Critically, WNS never mutates WMS state from the callback** — it reads the summary, adds its output to its own store, and lets the normal event flow close the loop.

---

## 4. WNS Design

The **World Narrative System** is the easier of the two LLM subsystems. It's a focused writer: "given everything the WMS knows, what story beat is worth telling?"

### 4.1 Single responsibility

WNS does exactly one thing: convert WMS state into a `NarrativeBeat`. It does not decide whether anything should be built, it does not call tools, it does not pick enemies or items. It writes a beat.

```
WNS.generate_beat(world_summary_event) -> NarrativeBeat
```

This narrow surface is deliberate. WES is the decision-maker; WNS is the voice.

### 4.2 Inputs

All inputs come from the WMS facade and a few sibling systems. **WNS never issues raw SQL.**

| Input | Source | Purpose |
|---|---|---|
| `world_summary` | `WorldMemorySystem.get_world_summary()` | Headline ongoing conditions + event count |
| `world_summary_event` | L7 callback payload (or latest row) | The structured fire trigger |
| Contributing L6 narratives | `LayerStore.query_by_tags(layer=6, tags=[world:world_0])` | What nation-level stories caused this fire |
| Faction state | `FactionSystem.get_instance().stats` / `get_profile_summary()` | Who's rising, who's falling, current alliances |
| Geographic registry | `GeographicRegistry` | Names, relationships, biome types of regions involved |
| Previous beats | WNS's own `narrative_beats` SQLite table | Continuity — avoid repeating or contradicting |
| Player profile summary *(future)* | Player Intelligence (Part 3) | What the player cares about; preferences for beat tone |

The last row is aspirational — Part 3 isn't built. WNS v1 ships without it and degrades to generic tone selection.

### 4.3 Output: `NarrativeBeat`

Proposed dataclass (subject to revision during implementation):

```python
@dataclass
class NarrativeBeat:
    beat_id: str
    created_at: float                     # game time
    source_summary_id: str                # which WorldSummaryEvent fired this
    trigger_mode: str                     # "l7" | "developer" | "session" | "wes"

    # The narrative content
    headline: str                         # one-sentence beat (displayable)
    prose: str                            # 2-4 sentence beat (for logs/UI)
    theme_tags: List[str]                 # content tags for routing (e.g. "domain:combat", "intensity:escalating")

    # Structured hints for WES — the "director's note"
    focal_factions: List[str]             # which factions the beat centers on
    focal_regions: List[str]              # which regions should feel it
    focal_domains: List[str]              # mining | combat | diplomacy | magic | ...
    tone: str                             # tense | hopeful | eerie | triumphant | ...
    scope: str                            # local | regional | national | world

    # Director's suggestions for the executor
    suggested_content_types: List[str]    # ["hostiles", "materials"] — hints only
    content_constraints: Dict[str, Any]   # e.g. {"tier_range": [2,3], "biome": "tundra"}

    # Continuity
    supersedes_beat_id: Optional[str]     # replaces an earlier beat
    thread_id: Optional[str]              # long-running narrative thread (§8.4)
```

WES reads this and decides whether to act. A beat alone does nothing to the game — it's authorial intent waiting for execution.

### 4.4 Prompt assembly

WNS uses `BackendManager.generate(task="world_narration", ...)`. The config lives in `backend-config.json` (route to local Ollama by default, fall back to Claude, with Mock for tests). Temperature ~0.7 — we want some creative latitude.

Prompt fragment files to create (follows existing `prompt_fragments_l7.json` convention in `world_system/config/`):

- `prompt_fragments_wns.json` — WNS system prompts, output schema, examples

Assembly order (code, not LLM):

```
[SYSTEM]
  "You are the narrative designer of a procedural world..."
  Output schema (strict JSON with all NarrativeBeat fields)
  Style guide: second-person omniscient, present tense, 2-4 sentences

[CONTEXT BLOCK — built by code]
  <world_summary>
    {narrative from WorldSummaryEvent}
    Severity: {severity}, Condition: {world_condition}
  </world_summary>
  <dominant>
    Activities: {dominant_activities}
    Nations: {dominant_nations}
  </dominant>
  <recent_l6 limit="5">
    {5 most recent nation summaries, narrative field only}
  </recent_l6>
  <factions>
    {top 3 rising / top 3 falling factions by affinity delta}
  </factions>
  <continuity>
    Previous beat ({hours_ago}): {previous.headline}
    Active thread: {thread.name if any}
  </continuity>

[USER]
  "Produce the next world narrative beat. Return JSON only."
```

Key constraint: **no raw event IDs, no region IDs, no SQL artifacts in the prompt**. The LLM sees human-readable names and narrations. This keeps prompts stable across schema changes.

### 4.5 Validation & fallback

1. Parse JSON. On failure → retry once with "return JSON only" reinforcement → on failure again, use template fallback (see §4.6).
2. Schema-check every field. Missing required fields → retry once with the specific field called out.
3. Content-tag check: every `theme_tag` must exist in `tag_library.py`'s registered taxonomy. Unknown tags → dropped with a warning.
4. Address-tag check: if the LLM invents a `world:` / `nation:` / `region:` tag, **strip it**. Same rule L7 already enforces.

### 4.6 Template fallback (no LLM)

Mirrors the existing MockBackend pattern. A minimal deterministic writer that reads `world_summary_event` fields and produces a flat-but-valid `NarrativeBeat`:

```
headline = f"The {world_condition} continues across {len(dominant_nations)} nations."
theme_tags = event.tags (filtered to content tags)
focal_regions = dominant_nations (promoted up or left as-is)
tone = {"crisis": "tense", "volatile": "uneasy", "stable": "steady"}[world_condition]
```

Not beautiful prose, but valid beats. WES can execute against these exactly as it would against LLM-generated beats. **Keeping the fallback at 100% feature parity with the LLM path is a non-negotiable invariant** — it protects the system when backends are down or rate-limited.

### 4.7 Storage

WNS owns a new SQLite table (co-located with the WMS database):

```sql
CREATE TABLE narrative_beats (
    beat_id TEXT PRIMARY KEY,
    created_at REAL,
    source_summary_id TEXT,
    trigger_mode TEXT,
    headline TEXT,
    prose TEXT,
    tone TEXT,
    scope TEXT,
    supersedes_beat_id TEXT,
    thread_id TEXT,
    payload_json TEXT  -- full NarrativeBeat serialized
);

CREATE TABLE narrative_beat_tags (
    beat_id TEXT,
    tag TEXT,
    FOREIGN KEY (beat_id) REFERENCES narrative_beats(beat_id)
);
```

Beats are first-class events. They show up in the game's narrative log, can be referenced by save files, and — critically — **they are published to the `GameEventBus`** (`NARRATIVE_BEAT_CREATED`) so any system (including WES and a future UI) can subscribe.

---

## 5. WES Loop

The **World Executor System** is where the user's description gets hard. The WES must:

> **plan the narrative out, reason how to get there with the game, call upon the proper tools providing proper context, and then check the work.**

That's four phases. Below, each is expanded into its concrete shape, inputs, outputs, and failure modes.

### 5.1 Loop shape

```
┌─────────────────────────────────────────────────────────────┐
│  NarrativeBeat arrives                                      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Phase 1: PLAN       │──► WESPlan (n-step,
                 │  Decompose beat      │    tool calls, deps)
                 └──────────┬───────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Phase 2: REASON     │──► Augmented plan
                 │  Game-state check;   │    (revised / pruned /
                 │  pick tools; build   │     abandoned) + context
                 │  context per call    │    envelopes
                 └──────────┬───────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Phase 3: CALL       │──► Tool outputs
                 │  Execute tools in    │    (JSON per type) +
                 │  dependency order    │    registry insertions
                 └──────────┬───────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Phase 4: VERIFY     │──► Verification report
                 │  Self-check +        │    (OK, retry, rollback)
                 │  registry-coherence  │
                 └──────────┬───────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Commit or rollback  │
                 │  Publish to EventBus │
                 └──────────────────────┘
```

Two escape hatches in this loop:

- **Clarification request**: during PLAN or REASON, if the beat is under-specified, WES calls WNS with a specific sub-question and receives a refined beat. This is the "not a clean handoff" mechanism (§2.3).
- **Abandonment**: at any phase, WES can decide "this beat cannot be executed right now" and log the reason. Beat stays in history; nothing is built.

### 5.2 Phase 1 — PLAN

**Input**: a `NarrativeBeat`.
**Output**: a `WESPlan` — an ordered list of tool calls with dependencies, unresolved slots, and a rationale.

Planner prompt (code-assembled, single LLM call):

```
[SYSTEM]
  You are the world executor. Given a narrative beat, produce a
  JSON plan of tool calls that make the beat real in the game.
  Available tools: hostiles, skills, nodes, materials, titles, quests.
  (Quests are deferred for now — do NOT emit quests tool calls.)
  Return JSON: {steps: [{step_id, tool, intent, depends_on, slots}]}

[CONTEXT]
  <beat>
    {NarrativeBeat JSON}
  </beat>
  <registry_snapshot>
    Existing hostiles (count, tier spread, biome coverage)
    Existing materials (count, tier spread, domain coverage)
    Existing nodes (count, biome coverage)
    Existing skills (count, domain coverage)
    Existing titles (count, category coverage)
  </registry_snapshot>
  <game_constraints>
    Tier definitions (T1..T4 multipliers — canonical)
    Biome taxonomy (from geographic-map.json)
    Domain taxonomy (from tag-definitions.JSON)
  </game_constraints>

[USER]
  Produce a plan. Each step may reference prior steps via depends_on.
```

**WESPlan shape**:

```python
@dataclass
class WESPlanStep:
    step_id: str
    tool: str                     # "hostiles" | "materials" | ...
    intent: str                   # one-line human-readable goal
    depends_on: List[str]         # upstream step_ids
    slots: Dict[str, Any]         # slot fillers (tier, biome, domain, etc.)
    # Slots may include unresolved placeholders like "<from step s1.outputs.faction_id>"

@dataclass
class WESPlan:
    plan_id: str
    beat_id: str
    steps: List[WESPlanStep]
    rationale: str
    abandoned: bool = False
    abandonment_reason: str = ""
```

**Why plan first, then call?** Two reasons:
1. Dependencies. A new hostile that drops a new material needs the material to exist first.
2. Veto. The planner can look at the full plan and say "this would create 12 orphan materials; abort."

### 5.3 Phase 2 — REASON

**Input**: `WESPlan`.
**Output**: augmented `WESPlan` with context envelopes per step, or a decision to abandon.

This phase is **deterministic code, not an LLM call**. It's where "reason how to get there with the game" is enforced.

For each step:

1. **Resolve depends_on slots.** If step `s2` references `<from s1.outputs.faction_id>`, ensure `s1` is queueable first.
2. **Game-state sanity check.** Query the Content Registry (§7):
   - Does the plan introduce a new material tier already saturated?
   - Is the target biome known to `geographic-map.json`?
   - Are referenced factions live in `FactionSystem`?
3. **Build per-step context envelope.** This is **the single most important WES responsibility** — see §8 for the full context-budget discussion. Short version: each tool gets only the context it needs, compressed to fit its token budget.
4. **Check backend quota.** If BackendManager reports the primary backend is rate-limited, either reorder steps to batch calls, or degrade non-critical steps to Mock.

Failure modes:
- **Circular dependencies** in `depends_on` → abandon plan, log.
- **Unknown biome / domain / faction** → drop the step, or request clarification from WNS, or abandon.
- **Budget exceeded** (too many tool calls for the frame) → defer the tail of the plan to a follow-up beat.

### 5.4 Phase 3 — CALL

**Input**: augmented `WESPlan`.
**Output**: tool outputs + registry insertions (staged, not committed).

Execute each step in topological order. For each:

1. Load the tool's prompt template.
2. Inject the context envelope from Phase 2.
3. Call `BackendManager.generate(task="tool_<name>", ...)`.
4. Parse + schema-validate the output JSON.
5. On parse failure → one retry with stricter prompt → on failure, mark step failed.
6. On success → write to **staging registry** (not live) and continue to next step.

**Staging is the key invariant.** Nothing is live until Phase 4 verifies the whole plan. If step 3 of a 5-step plan fails unrecoverably, we can roll back everything from staging without the game ever having seen broken content.

Concrete staging: the Content Registry (§7) has a "staged" flag on every row. WES's commit step flips the flag from staged → live atomically.

### 5.5 Phase 4 — VERIFY

**Input**: staged outputs.
**Output**: verification report; commit or rollback.

Verifier uses a mix of **code checks** and one **LLM self-critique**:

**Code checks** (all must pass):
- Every tool output schema-valid.
- Every cross-reference resolves (no orphan IDs — §7 handles this).
- No balance violations (tier multipliers, stat ranges — run against `Definitions.JSON/stats-calculations.JSON`).
- No duplicate IDs with existing live content.

**LLM self-critique** (single call):
```
[SYSTEM]
  You review generated content for narrative coherence.
  Return JSON: {coherent: bool, issues: [...], severity: "minor"|"block"}

[CONTEXT]
  <beat>{NarrativeBeat}</beat>
  <staged_content>
    Summary of every staged item (not full JSON — summaries)
  </staged_content>

[USER]
  Does the staged content deliver the beat? Flag any issue.
```

**Policy on self-critique output**:
- `issues = []` + `coherent = true` → commit.
- `severity = "minor"` → commit, log issues for dev review.
- `severity = "block"` → rollback; log beat + plan for manual review.

**Why not trust the planner implicitly?** Because the planner wrote the plan and the tools wrote the content. A fresh critic call is cheap (~1k tokens), catches "we drifted from the beat" problems, and gives us one more layer before content goes live.

### 5.6 Commit / rollback

On commit:

1. Flip all staged rows → live in registry.
2. Publish `CONTENT_GENERATED` events to `GameEventBus`, one per created entity.
3. The events flow into WMS (existing `EventRecorder` path), which records them as L1 stats. They will eventually influence the *next* L7 summary — closing the WNS/WES loop.

On rollback:
1. Delete all staged rows for this plan.
2. Emit a `PLAN_ABANDONED` event with the reason.
3. Increment a counter on the beat (so WNS can learn over time that certain beat shapes fail).

### 5.7 Asynchrony

Every LLM call in the WES loop must go through an async runner. The main game thread cannot block for 5–20 seconds per tool call. Pattern: same as existing `llm_item_generator.generate_async` (background thread + polling for completion).

Concretely, each WES plan becomes a background job. The game continues. When the plan commits, new content appears in the world "later that day" from the player's perspective. This is a feature, not a latency problem — the world should feel like things are in motion, not frozen while we wait.

---

## 6. Tool Architecture

Six tools. Each is an LLM-powered generator that produces a JSON artifact matching an existing game schema. **The tools do not know about beats or plans** — they are stateless workers. WES gives them a focused prompt with a focused context envelope and gets back one JSON object (or a small batch).

### 6.1 Shared tool contract

Every tool implements the same interface:

```python
class WESTool(Protocol):
    name: str                       # "hostiles" | "materials" | ...
    schema_path: str                # path to the JSON schema this tool writes
    registry_type: str              # registry category for anti-orphan checks

    def build_prompt(self, intent: str, slots: Dict[str, Any],
                     context_envelope: ContextEnvelope) -> Tuple[str, str]:
        """Return (system_prompt, user_prompt)."""

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Parse LLM JSON; raise on schema violation."""

    def validate_against_registry(self, output: Dict[str, Any],
                                   registry: ContentRegistry) -> List[str]:
        """Return list of validation issues (empty = OK)."""

    def stage(self, output: Dict[str, Any], registry: ContentRegistry) -> str:
        """Insert into registry with staged=True; return content_id."""
```

Shared infrastructure (one implementation, reused by all 6 tools):
- JSON parsing with markdown-fence stripping (see `npc_agent._parse_dialogue_response` for the pattern).
- Schema validation via `jsonschema` (or lightweight dataclass-based validators).
- Retry policy (one retry on parse failure with stricter prompt).
- Output logging to `llm_debug_logs/wes/` (mirrors existing `llm_debug_logs/`).

### 6.2 The 6 tools

Each tool is described below with: **purpose**, **input slots**, **output schema**, **cross-refs to other tools**.

---

#### 6.2.1 `hostiles` — Enemy generator

**Purpose**: create a new hostile/enemy definition that fits the current beat (biome, tier, faction pressure).

**Input slots** (from `WESPlanStep.slots`):
- `biome` — target biome (must exist in `geographic-map.json`)
- `tier` — 1..4
- `role` — "predator" | "raider" | "guardian" | "horde" | ...
- `faction_id` *(optional)* — tie hostile to a faction
- `domain_tags` — e.g. `["fire", "nocturnal"]`

**Output schema**: matches `Definitions.JSON/hostiles-*.JSON` (existing format; WES writes a new file `hostiles-generated-<timestamp>.JSON` rather than mutating existing files — sacred boundary from CLAUDE.md).

**Cross-refs**:
- Drops → must reference materials that exist OR are created in the same plan (`materials` tool).
- Skills used → reference existing skill IDs OR created via `skills` tool.
- Biome → must be a known biome.
- Faction → must be in `FactionSystem`.

**Reuses existing combat system**. No changes to `combat_manager.py` — the new JSON is loaded by existing `EnemyDatabase`.

---

#### 6.2.2 `materials` — Material generator

**Purpose**: create a new raw material / ingredient.

**Input slots**:
- `tier` — 1..4
- `category` — "ore" | "wood" | "herb" | "hide" | "gem" | ...
- `biome` — source biome
- `properties` — flavor tags (e.g. `["brittle", "conductive"]`)

**Output schema**: matches `items.JSON/items-materials-1.JSON` structure.

**Cross-refs**:
- Must fit existing tier multipliers (T1=1.0x .. T4=8.0x) — canonical constants, checked by verifier.
- Referenced by: nodes (source), recipes (ingredient), hostiles (drops).

---

#### 6.2.3 `nodes` — Resource node generator

**Purpose**: create a new gatherable resource node that spawns a material.

**Input slots**:
- `material_id` — what it yields (must exist or be created same-plan)
- `biome` — where it spawns
- `tool_required` — `axe|pickaxe|sickle|...`
- `rarity` — common..legendary
- `yield_range` — `[min, max]` items per harvest

**Output schema**: matches `Definitions.JSON/Resource-node-1.JSON`.

**Cross-refs**:
- `material_id` → must exist.
- `biome` → known biome.
- `tool_required` → existing tool type.

---

#### 6.2.4 `skills` — Skill generator

**Purpose**: create a new skill with tag-driven effects.

**Input slots**:
- `domain` — `fire | ice | lightning | physical | ...`
- `geometry` — `single | chain | cone | circle | beam | pierce`
- `status_tags` — e.g. `["burn", "bleed"]`
- `unlock_condition` — who gets it, how (hint for title/class integration)

**Output schema**: matches `Skills/skills-skills-1.JSON` structure with `tags` + `effectParams`.

**Cross-refs**:
- Tags must exist in `tag-definitions.JSON` (sacred — no new tags).
- Effect params validate against existing effect executor (range checks via a future `BalanceValidator` stub — see §9.Q3).
- Referenced by: hostiles (enemy skills), titles (unlocks), classes.

**Critical constraint**: this tool MUST NOT invent new tags. The existing tag vocabulary is sacred content (CLAUDE.md). It composes from what exists.

---

#### 6.2.5 `titles` — Title generator

**Purpose**: create a new achievement title with an unlock condition.

**Input slots**:
- `category` — `combat | gathering | crafting | exploration | social`
- `tier` — `novice | apprentice | journeyman | expert | master`
- `unlock_stat` — which `StatTracker` stat gates it
- `unlock_threshold` — number to hit
- `bonus_tags` — which gameplay buffs apply while equipped

**Output schema**: matches `progression/titles-1.JSON`.

**Cross-refs**:
- `unlock_stat` must be a registered StatTracker recording method (see `entities/components/stat_tracker.py`, 65 methods).
- `bonus_tags` must be in the tag taxonomy.
- May grant access to a `skills` output from the same plan.

---

#### 6.2.6 `quests` — Quest generator (DEFERRED)

**Purpose** (when implemented): create a quest that stitches other generated content into a playable arc.

**Status**: explicitly out of scope for this phase per the user. Listed here so the architecture slots don't need rework later. The quest tool will differ from the other five in one important way: it **references** other generated content rather than creating new content. A quest's "kill 5 hostileX" presumes hostileX exists. So:

- Quest tool runs last in any plan that contains one.
- Its context envelope includes a full list of same-plan content IDs.
- Its output schema matches `progression/npcs-1.JSON` quest blocks + existing quest system.

Until WES reaches the quest phase, the planner prompt explicitly excludes `quests` from available tool choices.

### 6.3 Generation order within a plan

Dependencies are naturally ordered:

```
materials  ──┐
             ├──► nodes (consumes materials)
             └──► hostiles (consumes materials as drops)
                       │
                       ▼
             skills ──► hostiles (skills used by hostile)
                   └──► titles (title unlocks a skill)
                          │
                          ▼
                         quests (DEFERRED)
```

Planner produces steps in this order by default; the REASON phase enforces it via `depends_on`.

### 6.4 Each tool is "agentic" — what that means here

The user described the tools as "agentic themselves." In practice this means a single tool call may do more than produce one JSON:

- **Iterative refinement within the tool**: a hostile generator might call the backend twice — once for "design", once for "balance-check". This is internal to the tool.
- **Tool-to-tool gossip through WES, not directly**: a tool never calls another tool. If the hostile generator realizes it needs a new material, it emits a `tool_request` in its output; WES catches it, inserts a new step, and re-plans.
- **Local memory per tool**: each tool can read the Content Registry to see what it and its siblings have made recently. This prevents "every hostile is a wolf variant" drift.

### 6.5 Where tool prompts live

New config files under `world_system/config/`:

- `prompt_fragments_tool_hostiles.json`
- `prompt_fragments_tool_materials.json`
- `prompt_fragments_tool_nodes.json`
- `prompt_fragments_tool_skills.json`
- `prompt_fragments_tool_titles.json`

Follows the existing `prompt_fragments_l7.json` layout (`_meta`, `_core`, `_output`, plus per-context variants). Reusing that structure keeps all fragment files greppable with one pattern.

---

## 7. Content Registry

The user's exact concern, preserved:

> these will need their own interconnected system so nothing is orphaned.

The Content Registry is that system. It is a **single source of truth for every piece of generated content and its relationships to other pieces**. Without it, the tool layer produces JSON files that reference IDs that may or may not exist — the classic orphan problem.

### 7.1 What "orphan" means here

An orphan is any referenced ID that has no definition. Examples:

- A hostile drops `mythril_ore` but no material with that ID exists.
- A skill is referenced by a title but the skill was never created.
- A quest asks for 10 `iron_fang` pelts but the `iron_fang` hostile was rolled back.
- A node yields a material that was staged in a plan that later got abandoned.

The WMS, crafting, and combat systems all tolerate some referential slack today because human-authored content doesn't introduce orphans. A procedural system **will** produce them at scale unless something blocks it.

### 7.2 Registry shape

SQLite tables, colocated with the WMS database. One table per content type + one unified cross-reference table.

```sql
-- Per-content-type tables (one per tool)
CREATE TABLE reg_hostiles (
    content_id TEXT PRIMARY KEY,
    display_name TEXT,
    tier INTEGER,
    biome TEXT,
    faction_id TEXT,              -- may be NULL
    staged INTEGER DEFAULT 1,     -- 1 = staged, 0 = live
    plan_id TEXT,                 -- the WESPlan that produced this
    created_at REAL,
    source_beat_id TEXT,
    payload_json TEXT             -- the full generated JSON
);

CREATE TABLE reg_materials (...);
CREATE TABLE reg_nodes (...);
CREATE TABLE reg_skills (...);
CREATE TABLE reg_titles (...);
-- reg_quests (future)

-- Unified cross-reference table
CREATE TABLE content_xref (
    src_type TEXT,                -- "hostiles"
    src_id TEXT,                  -- "wolf_ashen"
    ref_type TEXT,                -- "materials"
    ref_id TEXT,                  -- "ashen_pelt"
    relationship TEXT,            -- "drops" | "uses_skill" | "unlocks" | "yields" | ...
    PRIMARY KEY (src_type, src_id, ref_type, ref_id, relationship)
);

CREATE INDEX idx_xref_ref ON content_xref(ref_type, ref_id);
CREATE INDEX idx_xref_src ON content_xref(src_type, src_id);
```

### 7.3 Orphan detection — three passes

**Pass 1: During tool output parsing** (§6.1).
Tool's `validate_against_registry` walks every `ref_type/ref_id` in the generated JSON. If a referenced ID is not in the registry AND not staged in the same plan, the tool emits an issue. WES can choose to:
- Retry the tool with stricter prompt ("do not reference X — it does not exist"),
- Insert a new plan step to create X, or
- Drop the reference from the output.

**Pass 2: Verification phase** (§5.5).
Before commit, run `SELECT src_id FROM content_xref WHERE ref_id NOT IN (SELECT content_id FROM reg_<ref_type>)`. Any rows → orphan → block commit.

**Pass 3: Nightly / on-save scrub**.
Hard invariant enforcement: if any live content ever references a missing ID (due to a bug, a corrupted save, manual JSON edits, etc.), log a repair action. Default repair is "downgrade reference to a safe fallback" (e.g., orphan material drop → generic tier-matched material). This is defensive; should not fire in normal operation.

### 7.4 Integration with existing databases

The Content Registry does not replace `MaterialDatabase`, `EnemyDatabase`, etc. Those load from JSON files at startup. Instead, WES's commit step:

1. Flips registry rows to `staged=0` (live).
2. **Writes the JSON to a generated content file** in the appropriate directory (`items.JSON/items-materials-generated.JSON`, etc.).
3. Re-triggers the relevant database to reload (or appends in-memory).

The databases remain the runtime truth. The registry is the coordination layer + relationship graph. **This separation lets human-authored JSON and generator-authored JSON coexist seamlessly** — both end up in the same databases, the registry just happens to also know about the generator-authored subset and their relationships.

### 7.5 What the registry enables beyond anti-orphan

- **Lineage queries**: "which beat created this enemy?" → `reg_hostiles.source_beat_id → narrative_beats`. Makes generated content narratively auditable.
- **Diversity checks**: WES's REASON phase can query "how many T3 materials in the tundra biome already?" before asking for another.
- **Pruning / retirement**: old generated content (low player interaction, orphaned after a save-edit, superseded by a better variant) can be flagged for retirement via registry queries.
- **Save/load integrity**: the registry is part of the save file. Load = rehydrate `live` rows + reload JSONs.

### 7.6 What the registry is NOT

- **Not a replacement for the WMS.** The WMS tracks *events and interpretations*. The registry tracks *generated content and its structure*. They are siblings, both consumed by WNS/WES.
- **Not a tag authority.** Tags live in `tag-definitions.JSON` and `tag_library.py`. The registry stores tag *references* but cannot define new tags.
- **Not authoritative at runtime.** Databases (`MaterialDatabase`, etc.) remain runtime truth. The registry is authoritative for *coordination and lineage*, not hot-path lookups.

---

## 8. Information Flow — The Hard Problem

The user's framing, preserved:

> **The true difficulty of this is the information.**

Everything about WNS/WES is solvable in principle. What makes it actually work is whether the right context reaches each LLM call in a form it can use. This section is the doc's center of gravity.

### 8.1 The shape of the problem

Every LLM call has a budget:
- **Token budget** — local models (Ollama Llama 3.1 8B) realistically handle 4–8k context; Claude Sonnet handles 200k but at cost and latency.
- **Cognitive budget** — even with 200k tokens available, LLMs degrade on dense, unstructured context. Quality drops sharply past ~8k relevant tokens per call.
- **Coherence budget** — the more context a call sees, the higher the chance of self-contradiction or hallucinated cross-references.

Meanwhile, the available data is enormous:
- WMS EventStore accumulates thousands of L1 events per play session.
- 33 evaluators produce L2 narrations continually.
- Faction affinity state, geographic registry, entity registry all carry hundreds of rows.
- Content Registry grows with every generated entity.

**Assembling the right 2–4k tokens per call is the entire game.**

### 8.2 The principle: tiered, role-aware, compressed

Context assembly for every LLM call in the system follows three rules:

1. **Tiered.** Most relevant facts first; inclusion threshold tightens as budget fills.
2. **Role-aware.** A `hostiles` tool gets combat/biome/tier context; a `titles` tool gets StatTracker/milestone context. Never the same envelope.
3. **Compressed.** Raw data is never sent. Narrations (already LLM-compressed at each WMS layer) are the default. Numbers become adjectives ("heavy mining" not "4,200 nodes/day").

### 8.3 The `ContextEnvelope`

One dataclass, filled differently per consumer:

```python
@dataclass
class ContextEnvelope:
    purpose: str                       # "wns_beat" | "wes_plan" | "tool_hostiles" | ...
    token_budget: int                  # hard cap for assembled prompt

    # Tier 1: always included (≤ 20% of budget)
    world_summary: Dict[str, Any]      # ongoing_conditions, world_condition
    active_beat: Optional[NarrativeBeat]

    # Tier 2: role-relevant (≤ 50% of budget)
    tier2_narrations: List[str]        # pre-compressed WMS narrations
    tier2_faction: List[str]           # relevant faction state snippets
    tier2_geography: List[str]         # biome/region names in play

    # Tier 3: specifics (≤ 25% of budget)
    tier3_recent_events: List[str]     # last N relevant L2 narrations
    tier3_registry_snapshot: Dict[str, Any]  # anti-orphan hints

    # Tier 4: continuity (≤ 5% of budget)
    previous_output_summary: Optional[str]  # e.g. "last plan made 3 T2 materials"

    # Metadata (not counted toward LLM budget)
    assembly_trace: List[str]          # for debugging what got included/dropped
```

The envelope is built by a dedicated **ContextAssembler** module, one per consumer type (WNS assembler, WES planner assembler, one per tool). The assemblers share a common base that enforces the 20/50/25/5 ratios.

### 8.4 Narrative threads — long-running context

An individual L7 summary is a snapshot. But a story is a thread — things that persist across multiple beats. Without explicit thread tracking, every beat reads as isolated and the world feels amnesiac.

**NarrativeThread** (SQLite, owned by WNS):

```python
@dataclass
class NarrativeThread:
    thread_id: str
    name: str                          # e.g. "The Ashen Incursion"
    theme_tags: List[str]
    status: str                        # "emerging" | "active" | "resolving" | "dormant" | "closed"
    significance: float                # 0.0..1.0
    created_at: float
    last_touched_at: float
    decay_rate: float                  # per-game-day dampening
    associated_beats: List[str]        # beat_ids
    associated_content: List[Tuple[str, str]]  # (registry_type, content_id)
    prose_summary: str                 # 1-paragraph running summary
```

Threads get `last_touched_at` bumped whenever a beat is tagged with one of their `theme_tags`. If `last_touched_at` ages out past `decay_rate`, status → dormant. Dormant threads are no longer included in context but are not deleted — a new beat with matching tags can re-awaken them.

This is how the context budget stays small **while still feeling continuous**. The WNS context envelope carries 1–2 active threads; the rest are off-stage.

### 8.5 Pre-compression via WMS layers (already built)

The WMS's 7-layer design is, in effect, a context-compression pyramid:

- L1 = raw events (thousands).
- L2 = ~36 evaluators narrate into ~100 interpretations per session.
- L3–L6 = consolidators reduce to region/province/nation summaries.
- L7 = one world-level summary.

This means **context assembly never walks L1**. The pyramid has done the work. For a WNS beat, pulling the latest L7 summary + top 5 L6 narrations + top 3 ongoing conditions gets you ~1000 tokens of *pre-compressed* context that already represents thousands of underlying events.

This is the WMS's real payoff for WNS/WES. Without it, we'd be trying to summarize events on every LLM call — which is exactly what L2 evaluators already do.

### 8.6 Distance decay (for NPC/local consumers, not for WNS)

WNS looks at world-level context — it doesn't need distance decay. But downstream NPC dialogue (which already goes through `NPCAgentSystem`) and any future localized WES beats do. The rule, borrowed from the scratchpad's Dwarf Fortress / Gossamer analysis:

```
Event occurs at (x, y)
  ├─ same chunk (r ≤ 1): full narrative
  ├─ same region (r ≤ 4): headline only
  ├─ same nation (r ≤ 16): "I heard something about..."
  └─ distant: dropped, OR if significance = critical, rumor variant
```

Implementing this requires geographic distance calculations in the context assembler. It is **out of scope for WNS v1** but will be needed when WES produces localized events (phased in §10).

### 8.7 Context poisoning and how to avoid it

A single bad LLM output in the WMS (e.g., an L5 narrative with hallucinated factions) can pollute all downstream context. Mitigations already in place:

- L5/L6/L7 all enforce **address-tag immutability** — LLMs cannot invent regions.
- Content tags must exist in `tag_library.py`'s taxonomy — no new-tag pollution.
- Narrations are bounded length; over-length outputs are truncated.

New mitigations needed for WNS/WES:

- **Beat quarantine**: if an LLM-written beat fails self-critique (§5.5), it's marked quarantined and excluded from future context.
- **Thread sanity**: threads whose `prose_summary` drifts from their `theme_tags` get flagged for re-summarization.
- **Registry cross-check on beats**: if a beat mentions "the Ashen Cabal" and no faction with that name exists, either create it (via the `factions` extension — future) or rewrite the beat's prose to remove invented entities.

### 8.8 Where the context **actually** comes from (concrete sources)

| Source | API | Used by |
|---|---|---|
| `WorldMemorySystem.get_world_summary()` | facade method (shipped) | WNS, WES REASON, all tools |
| `LayerStore.query_by_tags(layer=6, ...)` | existing query | WNS (L6 narrations for prompt) |
| `LayerStore.query_by_tags(layer=2, ongoing=True)` | existing query | WNS, tools (ongoing_conditions) |
| `FactionSystem.stats` / `get_npc_profile()` | existing API | WNS, tools (faction-driven content) |
| `GeographicRegistry` | existing singleton | All (biome/region names) |
| `EntityRegistry` | existing singleton | Tools (what NPCs/enemies live) |
| `StatTracker.get_summary()` | existing component | `titles` tool (unlock condition design) |
| `ContentRegistry` | **NEW** (§7) | WES REASON, all tools (anti-orphan, diversity) |
| `narrative_beats` + `NarrativeThread` | **NEW** (§4.7, §8.4) | WNS (continuity) |

Everything on this list that is already shipped is battle-tested. Everything marked NEW is a green-field concern for this phase.

### 8.9 Observability: logging what context got sent

Every LLM call logs its assembled envelope to `llm_debug_logs/wes/<timestamp>_<task>.json`, mirroring the existing `llm_debug_logs/` pattern for the item generator. The `assembly_trace` field records which candidates were considered and which got dropped for budget. This makes "why did the hostiles tool produce a wolf in a fire biome?" answerable by reading one JSON file.

---

## 9. Open Questions & Decisions Needed

Blockers and forks that need to be resolved before or during early implementation. Each has options and a lean.

### Q1. L7 cadence — is the 200-point threshold right for WNS?

**Problem**: the current L7 threshold (200) was tuned for creating WorldSummaryEvents, not for driving narrative beats. If it fires too often, WNS over-produces; too rarely, the world feels static.

**Options**:
- **A**: Keep 200, measure in early playtest, tune.
- **B**: Decouple — WNS subscribes to L7 but also to a time-based "heartbeat" (e.g., every N game-hours of player activity).
- **C**: Split — one low-threshold trigger for "minor beats" (flavor) and one high-threshold for "major beats" (content generation).

**Lean**: A for v1, then C after observation. Logging every L7 fire during playtest tells us the natural cadence.

---

### Q2. Backend selection per LLM call

**Problem**: the system has three backends (Ollama/Claude/Mock). Some calls are quality-sensitive (WNS beats, self-critique); others are volume-sensitive (tool calls during a plan). Which goes where?

**Options**:
- **A**: All routing via `backend-config.json` task types — no per-call override.
- **B**: Each WES component declares its backend preference; config is default but not law.
- **C**: Adaptive — use Ollama first, escalate to Claude on low confidence.

**Lean**: A for v1 (simplest, one place to tune), revisit as we see quality gaps. The existing `BackendManager.generate(backend_override=...)` signature already supports B and C if needed.

---

### Q3. BalanceValidator — build, stub, or skip?

**Problem**: the CLAUDE.md explicitly states BalanceValidator is "designed but NOT implemented" (spec only in `Development-Plan/SHARED_INFRASTRUCTURE.md`). WES verification (§5.5) would like to rely on it for stat-range checks. It doesn't exist.

**Options**:
- **A**: Build a minimal stub now — just "does this hostile's HP fall within its tier range?" — skip everything else in the spec.
- **B**: Skip balance checks entirely in v1; let content be produced unbalanced and fix post-hoc.
- **C**: Build the full BalanceValidator per spec before WES ships.

**Lean**: A. A 50-line stub that reads tier multipliers from `Definitions.JSON/stats-calculations.JSON` and rejects obvious outliers is enough to prevent embarrassing outputs, without blocking progress on the full validator.

---

### Q4. Async runner — reuse, wrap, or build new?

**Problem**: `llm_item_generator` has its own background-thread pattern; `NPCAgentSystem` blocks synchronously; WES needs full async with multi-step dependency execution. Three codebases for the same concern.

**Options**:
- **A**: Build a unified `AsyncLLMRunner` as shared infrastructure; migrate all three over time.
- **B**: Give WES its own runner; leave the other two alone.
- **C**: Extract the existing `llm_item_generator` threading code into a module, use it for WES.

**Lean**: A, but in phases. Build the runner for WES first; fold the others into it only when the API is proven.

---

### Q5. Where do generated JSONs live on disk?

**Problem**: sacred boundary from CLAUDE.md: "No content JSON modifications — all `items.JSON/`, `recipes.JSON/`, ... are OFF LIMITS." Generated content is also content. Where does it go?

**Options**:
- **A**: New parallel directories: `items.JSON/generated/items-materials-<timestamp>.JSON`. Existing loaders glob both.
- **B**: Single `generated/` top-level directory mirroring the schema.
- **C**: Don't write to disk — keep generated content in the ContentRegistry DB and synthesize JSON on demand for the databases.

**Lean**: C for v1. Avoids touching the sacred directories entirely; registry is the authority; loaders learn to pull from both DB and JSON. Simpler save/load story too.

---

### Q6. Thread detection — seeded or emergent?

**Problem**: `NarrativeThread` (§8.4) is how continuity works. But: do threads get seeded by developers (finite list in a JSON config), emerge from WNS beats (first beat with unique theme tags starts a thread), or both?

**Options**:
- **A**: Purely emergent — WNS decides each beat whether it's opening/continuing/closing a thread, outputs the decision in the beat JSON.
- **B**: Purely seeded — a `narrative-threads.json` config defines all allowed threads; WNS only selects among them.
- **C**: Hybrid — a seed config exists for the world's dominant themes; WNS may also create emergent threads flagged `source=emergent`.

**Lean**: C. Seeded threads give the world immediate identity; emergent threads let the world surprise us. The hybrid lets a designer (or a future developer-injection trigger) steer the world without blocking organic stories.

---

### Q7. Player Intelligence (Part 3) — hard dependency or graceful absence?

**Problem**: WNS/WES would benefit from knowing the player's preferences and arc (combat-focused? crafter? explorer?). Part 3 isn't built.

**Options**:
- **A**: Block WNS shipping until Part 3 has a minimal player profile.
- **B**: Ship WNS/WES without Part 3; leave a clear "profile" slot in the context envelope that's filled with a no-op default.
- **C**: Build just a minimal `StatTracker`-derived profile alongside WNS v1 — no ML, just heuristics.

**Lean**: B for v1, C later. A dedicated mini-profile (top 3 stats by activity, top 1 domain by time) is achievable without the full Part 3 plan and closes the biggest "world feels generic" gap.

---

### Q8. Rollback semantics — hard or soft?

**Problem**: when WES verification fails (§5.5), staged content is rolled back. But if the LLM already spent tokens, and parts of the plan are executable in isolation, should we commit what's valid and discard only the broken parts?

**Options**:
- **A**: Hard rollback — all-or-nothing per plan. Simple, predictable.
- **B**: Soft rollback — commit valid steps, log discarded ones for later retry.
- **C**: Plan-by-plan choice — planner declares whether the plan is "atomic" (A) or "best-effort" (B).

**Lean**: A for v1. Easier invariants. B/C are optimizations for later.

---

### Q9. Evaluation — how do we know WNS/WES is working?

**Problem**: LLM-driven systems fail silently. A broken WES might still produce JSON that loads without error but is thematically garbage.

**Options**:
- **A**: Developer spot-checks + `llm_debug_logs`.
- **B**: Automated metrics: beats per hour, tool success rates, orphan counts, player-content-interaction rate.
- **C**: LLM-based evaluator that scores beat/plan/content coherence automatically.

**Lean**: A+B combined. A alone is subjective; B alone misses qualitative failures. C is tempting but compounds the "LLMs grading LLMs" problem — defer.

---

## 10. Phased Implementation Roadmap

Each phase produces a shippable increment. No phase requires the next phase to provide value. Estimated effort is engineering-time, not calendar-time.

### P0 — Shared Infrastructure (prereq for all LLM work)

Prepare the plumbing before building WNS. These are independent, small, and unlock everything else.

- **P0.1 Async LLM runner** — unified background-thread executor with dependency-ordered step execution. Start with the pattern in `llm_item_generator.generate_async`; extract to `world_system/living_world/async_runner.py`.
- **P0.2 L7 subscription hook** — add `Layer7Manager.register_world_summary_callback()` and fire it in `_store_summary()`. Keep the "no L8 callback" comment historically accurate by updating it to reflect the new subscriber mechanism.
- **P0.3 `ContextEnvelope` + base `ContextAssembler`** — the dataclass from §8.3 plus a base assembler enforcing the 20/50/25/5 tiering. No consumer yet — just the framework and a unit test.
- **P0.4 NPC dialogue async migration** — move the existing synchronous `_generate_npc_opening` over to the new runner. This is the acceptance test for P0.1.

Exit criteria: all four ship, NPC dialogue no longer blocks the UI, and the test suite has ≥5 new passing tests covering the runner + envelope.

---

### P1 — WNS v1 (Template + Minimal LLM)

The narrative designer, with a fallback that works without any LLM.

- **P1.1 `narrative_beats` SQLite tables** — schema from §4.7.
- **P1.2 Template NarrativeBeat generator** — pure Python, no LLM. Reads L7 summary → produces a valid beat. This is the always-works baseline.
- **P1.3 LLM NarrativeBeat generator** — same interface as template; uses `BackendManager.generate(task="world_narration")`. New prompt fragment file: `prompt_fragments_wns.json`.
- **P1.4 WNS context assembler** — concrete assembler for WNS prompts, extending the base from P0.3.
- **P1.5 Subscribe WNS to L7 hook** — via P0.2.
- **P1.6 Publish `NARRATIVE_BEAT_CREATED` events** — to `GameEventBus`.

Exit criteria: a play session produces at least one meaningful beat; beats are visible in a developer log panel (F-key overlay, minimal UI); fallback produces valid beats when backend is offline.

---

### P2 — Content Registry

No tools yet, just the coordination layer.

- **P2.1 Registry SQLite tables** — per §7.2.
- **P2.2 Registry API** — `stage_content`, `commit`, `rollback`, `list_live`, `list_staged_by_plan`, `find_orphans`.
- **P2.3 Integration with databases** — loader paths for generator-authored content (option C from §Q5 — registry-resident, not JSON-on-disk). Modify `MaterialDatabase`, `EnemyDatabase`, etc., to union their JSON-loaded content with registry-live content.
- **P2.4 Save/load wiring** — registry state persists with saves.

Exit criteria: can manually stage a fake material via API, commit it, see it in `MaterialDatabase.get_instance().materials`, and roll back via API.

---

### P3 — First Tool: `materials`

Smallest surface area, most relied on by others. Proves the tool pattern end-to-end.

- **P3.1 `WESTool` protocol** + shared validation/retry helpers (§6.1).
- **P3.2 `MaterialsTool`** — prompt fragments, parser, validator, stager.
- **P3.3 Manual invocation** — dev-only CLI hook `debug_create_material(beat, slots)` that bypasses the full WES. Useful for iterating on tool prompt quality.
- **P3.4 BalanceValidator stub** (per §Q3 option A) — reads tier multipliers, rejects outliers.

Exit criteria: can give the tool a beat + slots, get back a schema-valid, registry-staged, balance-clean material JSON. Orphan check passes.

---

### P4 — WES v1 (Single-Tool Plans)

The full loop, but every plan is constrained to exactly one `materials` call. Validates the loop architecture without drowning in tool complexity.

- **P4.1 `WESPlanStep` + `WESPlan`** dataclasses (§5.2).
- **P4.2 WES Planner** — LLM call producing plans. Constrained output: one step, tool=`materials`.
- **P4.3 WES Reasoner** — §5.3 checks.
- **P4.4 WES Caller** — executes the single tool step via the P3 tool.
- **P4.5 WES Verifier** — code checks + self-critique.
- **P4.6 Commit / rollback** — via P2 registry.
- **P4.7 WES subscribes to `NARRATIVE_BEAT_CREATED`** — closes the WNS→WES loop.

Exit criteria: NPC says something → L7 eventually fires → WNS writes a beat → WES plans a single material → new material is live in the next gathering session.

---

### P5 — Tool Expansion

Add the remaining 4 tools (skills, nodes, titles, hostiles). Each is a clone of P3's pattern with per-tool context assembler and prompts. Order matters:

1. **P5.1 `nodes`** — depends on materials; proves cross-reference works.
2. **P5.2 `skills`** — self-contained; proves tag-compose without tag-invent.
3. **P5.3 `titles`** — depends on skills + StatTracker.
4. **P5.4 `hostiles`** — depends on all of the above. The capstone tool.

Exit criteria per tool: WES plan with that tool produces live, cross-referentially clean content.

---

### P6 — Multi-Step WES Plans

Now that plans can involve multiple tools, the planner and reasoner get stretched.

- **P6.1 Unblock multi-step plans** in the WES planner prompt.
- **P6.2 `depends_on` graph execution** in the caller.
- **P6.3 Mid-plan WNS clarification** (§5.1 escape hatch).
- **P6.4 Plan metrics dashboard** — beats per hour, tool success %, orphan count (from §Q9 option B).

Exit criteria: a single beat triggers a plan with ≥3 tool steps, completes, commits, and the generated items cross-reference each other correctly.

---

### P7 — Narrative Threads

Continuity across beats.

- **P7.1 `NarrativeThread` schema** + SQLite.
- **P7.2 Thread detection in WNS** — each beat declares thread_id (seeded from config or emergent, per §Q6 option C).
- **P7.3 `narrative-threads.json` config** — seed threads for the world's dominant themes.
- **P7.4 Thread decay** — dormant threads excluded from context.
- **P7.5 Thread-aware context** — WNS envelope always includes active threads.

Exit criteria: two beats separated by hours of play reference the same thread by name, and the world feels like it remembered.

---

### Deferred — Explicit Scope Exclusions

Per user direction, NOT included in this phase. Re-open when P0–P7 are proven:

- **Quest generation** — §6.2.6; needs Content Registry + ≥3 tools live to have enough material to reference.
- **Ecosystem integration** — `EcosystemAgent` exists as a query tool but WES does not route decisions through it. Phase X: extend WES REASON to consult `EcosystemAgent.get_scarcity_report()` when planning `materials` / `nodes` generation.
- **Player Intelligence (Part 3)** — the `profile` slot in the context envelope is stubbed; Part 3 fills it later.
- **Distance-decayed context for localized events** — §8.6; only needed when WES starts producing localized (sub-regional) content.
- **Developer beat injection tool** — a CLI for seeding beats, bypassing L7. Useful but not on the critical path.

---

## Appendix: References to Existing Code

Quick-reference index of what's already built and where to find it. All paths relative to repo root.

### WMS (World Memory System)

| Concern | File | Key API |
|---|---|---|
| Facade | [Game-1-modular/world_system/world_memory/world_memory_system.py](Game-1-modular/world_system/world_memory/world_memory_system.py) | `get_instance()`, `initialize()`, `get_world_summary()`, `stats` |
| World summary | [Game-1-modular/world_system/world_memory/query.py](Game-1-modular/world_system/world_memory/query.py) | `WorldQuery.get_world_summary(game_time)` |
| L7 manager | [Game-1-modular/world_system/world_memory/layer7_manager.py](Game-1-modular/world_system/world_memory/layer7_manager.py) | `should_run()`, `run_summarization(game_time)`, `on_layer6_created()` |
| L7 summarizer (LLM) | [Game-1-modular/world_system/world_memory/layer7_summarizer.py](Game-1-modular/world_system/world_memory/layer7_summarizer.py) | `summarize(...)` |
| Event schema | [Game-1-modular/world_system/world_memory/event_schema.py](Game-1-modular/world_system/world_memory/event_schema.py) | `WorldSummaryEvent`, all layer event dataclasses |
| LayerStore | [Game-1-modular/world_system/world_memory/layer_store.py](Game-1-modular/world_system/world_memory/layer_store.py) | `query_by_tags()`, `insert_event()` |
| Tag taxonomy | [Game-1-modular/world_system/world_memory/tag_library.py](Game-1-modular/world_system/world_memory/tag_library.py) | `TagLibrary.get_instance()` |
| Geographic registry | [Game-1-modular/world_system/world_memory/geographic_registry.py](Game-1-modular/world_system/world_memory/geographic_registry.py) | `GeographicRegistry`, `ADDRESS_TAG_PREFIXES` |

### Living World consumers

| Concern | File | Key API |
|---|---|---|
| Backend routing | [Game-1-modular/world_system/living_world/backends/backend_manager.py](Game-1-modular/world_system/living_world/backends/backend_manager.py) | `BackendManager.get_instance().generate(task, system_prompt, user_prompt)` |
| NPC agent | [Game-1-modular/world_system/living_world/npc/npc_agent.py](Game-1-modular/world_system/living_world/npc/npc_agent.py) | `NPCAgentSystem.generate_dialogue()` |
| Faction system | [Game-1-modular/world_system/living_world/factions/](Game-1-modular/world_system/living_world/factions/) | `FactionSystem.get_instance()`, 19-method API |
| Ecosystem tool | [Game-1-modular/world_system/living_world/ecosystem/ecosystem_agent.py](Game-1-modular/world_system/living_world/ecosystem/ecosystem_agent.py) | `EcosystemAgent.get_scarcity_report()`, `get_biome_state()` |

### Game integration

| Concern | File | Key API |
|---|---|---|
| Game engine init | [Game-1-modular/core/game_engine.py:4488](Game-1-modular/core/game_engine.py#L4488) | `_init_world_memory()` |
| NPC interaction | [Game-1-modular/core/game_engine.py:1482](Game-1-modular/core/game_engine.py#L1482) | `handle_npc_interaction()` |
| NPC opening helper | [Game-1-modular/core/game_engine.py:1540](Game-1-modular/core/game_engine.py#L1540) | `_generate_npc_opening(npc)` |
| Event bus | [Game-1-modular/events/event_bus.py](Game-1-modular/events/event_bus.py) | `get_event_bus().publish(event_type, data)` |
| Stat tracker | [Game-1-modular/entities/components/stat_tracker.py](Game-1-modular/entities/components/stat_tracker.py) | 65 `record_*` methods |

### Config files (`Game-1-modular/world_system/config/`)

| File | Purpose |
|---|---|
| `backend-config.json` | LLM routing per task |
| `geographic-map.json` | World/nation/region/province/district/locality hierarchy |
| `memory-config.json` | WMS thresholds, retention, evaluator params |
| `npc-personalities.json` | Personality templates for NPCs |
| `faction-definitions.json` | Faction list + reputation ranges |
| `ecosystem-config.json` | Resource tier thresholds |
| `tag-registry.json` | Tag taxonomy |
| `prompt_fragments.json` (+ `_l3`..`_l7`) | Per-layer LLM prompts |

### Existing LLM generator (reference pattern for tools)

- [Game-1-modular/systems/llm_item_generator.py](Game-1-modular/systems/llm_item_generator.py) — `LLMItemGenerator`, `generate_async()`, debug logging pattern, async runner pattern.

### Related planning docs

| Doc | Purpose |
|---|---|
| [Development-Plan/OVERVIEW.md](Development-Plan/OVERVIEW.md) | Roadmap + dependency graph for the broader Living World + Combat Overhaul |
| [Development-Plan/PART_2_LIVING_WORLD.md](Development-Plan/PART_2_LIVING_WORLD.md) | Phase-level plan for the memory layer + consumers |
| [Development-Plan/SHARED_INFRASTRUCTURE.md](Development-Plan/SHARED_INFRASTRUCTURE.md) | BalanceValidator spec (not yet implemented) |
| [Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md](Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md) | 2026-03-14 research notes; retained for bibliography only |
| [Game-1-modular/world_system/docs/HANDOFF_STATUS.md](Game-1-modular/world_system/docs/HANDOFF_STATUS.md) | Current WMS implementation state |
| [Game-1-modular/world_system/docs/WORLD_MEMORY_SYSTEM.md](Game-1-modular/world_system/docs/WORLD_MEMORY_SYSTEM.md) | Canonical WMS design doc |

---

## Resumption Notes

If picking this work up in a fresh context:

1. Read §1 (shipped state) first — know the baseline.
2. Read §2 and §5 for the system shape. §8 if you're working on anything that assembles LLM context.
3. The roadmap in §10 is the execution order. Do NOT skip P0; every later phase assumes it.
4. Quest generation and ecosystem integration are explicitly deferred — do not scope them in until P7 has shipped.
5. Every LLM call must: go through `BackendManager`, have a template fallback, log to `llm_debug_logs/`, and use a typed `ContextEnvelope`. These are the non-negotiables.
6. The Content Registry (§7) is the glue. If a tool does not write to it, the tool is broken — even if its JSON output is valid.
7. "The true difficulty is the information." When in doubt, re-read §8 before reaching for another LLM call.

