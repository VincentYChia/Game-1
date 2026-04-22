# World System Working Document

**Status**: Active planning — Living World architecture (**v3, awaiting user review**)
**Created**: 2026-04-20
**Last Updated**: 2026-04-21 (v3 — after second round of user feedback)
**Owner**: Development
**Supersedes as planning doc**: `Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md` (2026-03-14). The scratchpad is retained for its research citations only; its "Tier 1/2/3" framing is retired in favor of the WNS/WES vocabulary below.

> **⚠️ RESUMPTION PROTOCOL — READ FIRST.** When a new session resumes work on the Living World / World System, the *first* action should be to ask the user to read this doc (v3) end-to-end and give feedback. The user has been actively co-authoring this via two rounds of structured feedback (v1→v2, v2→v3) and has not yet done a full read-through of v3. Do NOT start implementation work, refactoring, or generating further revisions until they've confirmed the doc lands. Save the extra-round that would otherwise be spent guessing.
>
> Specifically surface:
> 1. "Your last instruction was to treat v3 as a handoff and postpone the read-through. You've since been working on a parallel topic. Want to read v3 now and give feedback?"
> 2. Point at §4 (WNS as extraction→weaving→embroidery), §5 (WES three-tier with renamed roles), §8 (live-query model replacing shared-immutable-context) as the v3 high-impact changes to sanity-check.
> 3. Only after feedback is incorporated should any code phases (§10 P0-P9) begin.

---

## Why This Doc Exists

The World Memory System (WMS) is built and storing narratives. Everything downstream of it — the part of the game that *uses* those narratives to make the world react and to generate new content — does not exist yet. This doc is the plan for that downstream half.

The user's framing, preserved verbatim:

> It can broadly split into two parts. **A World Narrative System (WNS)** — in charge of designing and narrative from the World Memory System. **A World Executor System (WES)** — in charge of executing and deciding game realities from the narrative of the WNS. The issue is that it is not a simple clean cut and handoff between the models. They broadly speaking feed into each other.

> The tools of course will likely be agentic themselves. With the most basic level of tools being creating the JSONs for hostiles, skills, nodes, materials, titles, and quests (however these will need their own interconnected system so nothing is orphaned). **The true difficulty of this is the information.**

Everything in this doc orbits those three framings: WNS/WES are coupled, tools generate JSON, and **context assembly is the hard problem**.

---

## Revision History

- **v1** (2026-04-20) — initial doc.
- **v2** (2026-04-20) — first major restructure after user feedback. Unidirectional flow, WNS as parallel-WMS, three-tier WES stack, Coordinator+Specialist tool mini-stacks, shared immutable context object, LLM Roster. 7→10 phase roadmap.
- **v3** (2026-04-21) — second restructure after user feedback. Major changes:
  - **WNS reframed via string-thread-embroidery metaphor.** WMS provides the string (raw facts). Low WNS layers *extract* narrative threads from events ("given event Y, what narrative thread exists?"). High WNS layers *weave* threads into embroidered world narrative. Aggregation is the wrong word — *extraction* at the bottom, *weaving* at the top.
  - **Layer count is TBD.** v2 assumed 7 NL layers (mirroring WMS L1-L7). That is a starting point, not a commitment. The number depends on how extraction/weaving divides naturally.
  - **Assume every WMS and WNS layer is LLM-driven.** v2 noted WMS L2 is currently template-only. The design now assumes WMS will also be fully LLM once a tuned model lands. WNS is LLM at every layer from the start.
  - **Shared immutable context object deleted.** v2 made it first-class; user prefers flexibility. Each LLM queries the current narrative-interpretation store live. The only cross-cutting "context" is (1) overall game awareness — the game's rules, taxonomies, canonical constants — and (2) task awareness — what this specific LLM is being asked to produce. Both are small enough not to need a propagation schema.
  - **Tier names renamed** to user's preferred vocabulary: Orchestrator → `execution_planner`, Coordinator → `execution_hub_<tool>`, Specialist → `executor_tool_<tool>`. Published pattern names (Anthropic's Orchestrator-Workers, Berkeley's compound AI) kept as citations.
  - **Narrative thread retention is forever, archived.** Same model as WMS events: retain in SQLite; context budget limits inclusion, not retention.

## Table of Contents

1. [Current Shipped State (Grounding)](#1-current-shipped-state-grounding)
2. [System Architecture: WMS → WNS → WES → Tools → Game (unidirectional)](#2-system-architecture)
3. [Trigger Signal Chain (L7 feeds WNS, NL7 fires WES)](#3-trigger-signal-chain)
4. [WNS Design — Parallel WMS for Narratives](#4-wns-design)
5. [WES Loop — Three-Tier Stack (Planner → Hub → Tool)](#5-wes-loop)
6. [Tool Architecture (5 Hub+Tool Mini-Stacks)](#6-tool-architecture)
7. [Content Registry (Anti-Orphan Cross-Reference)](#7-content-registry)
8. [Information / Context Flow — The Hard Problem](#8-information-flow--the-hard-problem)
9. [Open Questions & Decisions Needed](#9-open-questions--decisions-needed)
10. [Phased Implementation Roadmap (P0-P9)](#10-phased-implementation-roadmap)
11. [Appendix: References to Existing Code](#appendix-references-to-existing-code)

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

> **Revision note (2026-04-20, v2):** An earlier draft of this section described WNS ↔ WES as a bidirectional loop with mid-execution clarification round-trips. **That framing is wrong.** Narrative leads execution. WNS → WES is unidirectional. Execution does not feed narrative directly; instead, game events produced by execution flow back through the WMS, which eventually informs the *next* WNS cycle. The loop is macro, not synchronous.

### 2.1 The macro loop

```
┌──────────────────────────────────────────────────────────────────┐
│                         THE GAME                                 │
│  character, combat, crafting, NPCs, quests, world_system, ...    │
└────────────────┬──────────────────────────────────▲──────────────┘
                 │ events (via GameEventBus)        │ new content
                 ▼                                  │ becomes part
┌──────────────────────────────────────────────────────────────────┐
│  WMS — World Memory System (SHIPPED)                             │
│  L1 raw stats → L2 evaluators → L3-L6 consolidation →            │
│  L7 WorldSummaryEvent                                            │
└────────────────┬─────────────────────────────────────────────────┘
                 │ "what the world has become"
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  WNS — World Narrative System (NEW)                              │
│  A *parallel WMS for narratives* with its own geographic         │
│  addressing. Narrative layers NL1-NL7 mirror WMS L1-L7.          │
│  Tracks: player action narrations, NPC mentions, beat history,   │
│  emergent narrative threads. Each layer = one focused LLM call.  │
└────────────────┬─────────────────────────────────────────────────┘
                 │ latest narrative summary ("what the story is")
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  WES — World Executor System (NEW, orchestrator-workers topology) │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 1: execution_planner (1 LLM, cloud-eligible)       │   │
│   │  Plans what to build from the narrative summary.         │   │
│   └─────────────────────────┬────────────────────────────────┘   │
│                             │ structured plan                    │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 2: execution_hub_<tool> (1 LLM per tool, local)    │   │
│   │  Owns flavor + per-item spec shaping. Feeds items one-   │   │
│   │  by-one into its executor_tool below.                    │   │
│   └─────────────────────────┬────────────────────────────────┘   │
│                             │ per-item spec                      │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 3: executor_tool_<tool> (1 LLM per JSON, local)    │   │
│   │  Raw JSON generator — pure "one input → one JSON" calls  │   │
│   └─────────────────────────┬────────────────────────────────┘   │
└─────────────────────────────┼────────────────────────────────────┘
                              │ JSON outputs
                              ▼
                ┌──────────────────────────────┐
                │  Content Registry            │
                │  (staging + anti-orphan      │
                │   cross-reference)           │
                └──────────────┬───────────────┘
                               │ commit on verify
                               ▼ (content becomes live in game DBs)
                       [back to the top]
```

### 2.2 Key split: narrative vs execution

| | **WNS** | **WES** |
|---|---|---|
| **Role** | Produces narrative state (a parallel WMS for story) | Turns the current narrative state into game reality |
| **Input** | WMS L7 summaries + ongoing conditions + NPC mention log | Latest WNS narrative summary + registry snapshot |
| **Output** | Narrative events at layers NL1-NL7; emergent narrative threads | Staged content across 6 tool types |
| **LLM style** | Flat per layer (each narrative layer = one focused call). Pipeline depth varies. | Layered — three tiers: planner → hub → executor_tool |
| **Writes to game?** | No. Reads game, records narrative. | Yes. Writes registered content. |
| **Talks to the other?** | No direct call. | No direct call. |

### 2.3 Why this isn't a clean handoff (but also isn't a sync loop)

The user's earlier statement — "they feed into each other" — describes the **macro loop**, not direct coupling:

1. WMS observes gameplay and produces world state.
2. WNS reads WMS and produces narrative state.
3. WES reads WNS and produces new content.
4. The content enters gameplay; gameplay produces events.
5. Events flow to WMS. Go to step 1.

The loop closes through the game. WES does not call WNS. WNS does not read WES output. Each subsystem reads the output of the one above it and writes its own artifact. **This is a compound AI system (Berkeley BAIR terminology) with a hierarchical topology, not an agent dialogue.**

### 2.4 Live queries over stored narrative interpretations

> **Revision note (v3):** Earlier drafts designed a "shared immutable context object" that propagated through every tier as a game-of-telephone mitigation. **Deleted.** User preference is flexibility. The substitute: each LLM call queries live from canonical stores, and the canonical narrative stores are the WNS's own layer outputs (stored the same way WMS stores its layers). Each LLM reads from source; nothing is serialized through multiple hops of prose.

One principle cuts across every LLM call in the system: **each call takes one focused input, produces one output, and that output becomes a reusable artifact stored in a canonical store.** LLMs are treated as composable transforms, not agents. Later calls read from stores, not from propagated snapshots.

Consequences:

- WMS layer outputs → queried live via `WorldQuery` / `LayerStore` (shipped).
- WNS layer outputs → queried live via a parallel `WorldNarrativeSystem` facade (new). Stored in SQLite alongside WMS data.
- Game state (registries, taxonomies, faction state, etc.) → queried live via existing singletons.

**The only cross-cutting "context" each LLM receives is small enough not to need a schema:**

1. **Game awareness** — the game's canonical rules: tier multipliers (T1-T4), biome taxonomy, domain taxonomy, stat names, ADDRESS_TAG_PREFIXES. Static per-session, loaded from JSON at boot.
2. **Task awareness** — what this specific LLM is being asked to produce: its role, its output schema, its single input.

That's it. No propagating narrative headlines through three tiers. No frozen snapshots. If an LLM needs the latest narrative summary, it queries the narrative store at call time. If the world shifted during a long-running plan, downstream LLMs see the newer state — that's a feature, not a flaw.

**Why game-of-telephone doesn't apply:** telephone is a problem when each tier paraphrases the tier above. Here, no tier paraphrases narrative state — each tier *queries* it. Freshness replaces fidelity as the guarantee.

### 2.5 LLM Roster

Naming every LLM in the system, with its tier, backend preference, and call shape. "LLM" alone is too coarse — each role has different quality/latency/cost requirements.

| LLM role | Layer | Backend (preferred) | Call shape | Frequency |
|---|---|---|---|---|
| WMS L3 consolidator | WMS internal | Local (Ollama) | 1 call per district per interval | Moderate |
| WMS L4/L5/L6 summarizer | WMS internal | Local | 1 call per aggregation unit on weighted fire | Low |
| WMS L7 summarizer | WMS internal | Local | 1 call when world bucket fires | Very low |
| **WNS low-layer extractors** (NL1-mid) | WNS | Local | 1 call per narrative-worthy event cluster | Moderate |
| **WNS mid-layer weavers** (regional/national) | WNS | Local | 1 call per aggregation unit on weighted fire | Low |
| **WNS top-layer embroiderer** (world) | WNS | Local (Cloud tolerated) | 1 call when world bucket fires | Very low |
| **WES `execution_planner`** | WES Tier 1 | Cloud-tolerated | 1 call per WNS world-summary update | Low |
| **WES `execution_hub_<tool>`** | WES Tier 2 | Local | N calls per run (one per item fed to executor_tool) | Moderate |
| **WES `executor_tool_<tool>`** | WES Tier 3 | Local | N calls per run (one per JSON artifact) | High |
| NPC dialogue | Existing (NPCAgentSystem) | Local | 1 per player-NPC exchange | Variable |

**Cloud minimization rule:** cloud APIs (Claude) are *tolerated* only for the WES `execution_planner` and *possibly* the WNS top-layer embroiderer. Everything else runs locally. These calls don't need to be fast — they represent slow-moving world state, not per-frame reactions. Per user: *"Ideally none"* — cloud is the fallback, not the default.

**Layered vs flat:**
- **Flat LLM** = single focused call, no LLM-to-LLM dispatch. WMS layers, WNS layers, NPC dialogue.
- **Layered LLM** = an LLM whose job is to orchestrate other LLMs. Only WES has this shape. Its three tiers are `execution_planner` → `execution_hub_<tool>` → `executor_tool_<tool>`. Each tier is deterministically invoked by code between tiers — LLMs never call LLMs directly.

### 2.6 Vocabulary this doc uses (and the published equivalents)

Grounding terminology in the published literature so future contributors can search:

| This doc | Published equivalent | Source |
|---|---|---|
| Compound AI system | Compound AI systems | Berkeley BAIR 2024 |
| WES as "orchestrator-workers" | Orchestrator-Workers pattern | Anthropic "Building Effective Agents" |
| Three-tier stack | Hierarchical agent teams | LangGraph |
| Local-at-bottom, cloud-at-top | LLM cascading / model routing | FrugalGPT (Chen et al. 2023) |
| One-input-one-output-reusable | LLM-as-function / functional pipelines | DSPy, Outlines, Mirascope |
| Live query over stored interpretations | Blackboard / shared store | Standard blackboard architecture; replaces "shared immutable context" pattern |

### 2.7 Philosophy: LLMs write content, code owns structure

Every LLM call in the system follows the discipline the WMS already uses ([layer7_manager.py:442-500](Game-1-modular/world_system/world_memory/layer7_manager.py#L442-L500)):

- **Code builds the prompt and assembles context.** LLMs never see raw SQL results.
- **Code validates every output.** LLM JSON is parsed, schema-checked, retried on failure.
- **Address tags are facts, never LLM-writable.** This rule extends verbatim to WNS's narrative address tags (§4).
- **Structured artifacts between layers, not prose.** The `execution_hub` receives JSON plans from the `execution_planner`; `executor_tool` receives JSON specs from `execution_hub`. Prose is for humans; machines pass typed data.

---

## 3. Trigger Signal Chain

> **Revision note (2026-04-20, v2):** Previous draft framed L7 as the direct trigger for WES. **Updated.** Per the restructured §4, L7 feeds into WNS's parallel NL-pipeline as one of its inputs. The trigger that invokes **WES** is **NL7** (the world-level narrative summary), not L7 directly. L7 is still the most important WMS→WNS signal, but it is no longer one-hop to WES.

The WNS pipeline needs a heartbeat — some signal that says "enough has changed, re-narrate the world." L7 provides that for WNS, and NL7 in turn provides it for WES.

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

> **Revision note (v3):** v2 treated WNS as a parallel WMS with 7 layers mirroring L1-L7 and characterized each layer as "aggregation." **Both refined.** Per user:
>
> > *"The Narrative firing might honestly be something more akin to narrative extraction. Like given Y event what narrative thread exists? Then that goes up the WNS so a full narrative can be woven. The string is WMS, the thread is made by the lower levels of WNS, than the final embroidery is framed by the WNS."*
>
> The operation WNS performs is **extraction → weaving → embroidery**, not aggregation. The number of layers is a starting design choice (likely 4-7), not a commitment to mirror WMS exactly. And WNS is LLM-driven at every layer, not template at the bottom.

### 4.1 The string / thread / embroidery framing (canonical)

The user's metaphor is the design's anchor:

```
┌─────────────────────────────────────────────────────────────┐
│  STRING — WMS                                               │
│  Raw factual events + layered factual narrations.           │
│  Continuous, granular, address-tagged.                      │
│  (Already built. Assume LLM-driven at every layer.)         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  THREAD — LOW WNS LAYERS                                    │
│  NARRATIVE EXTRACTION. Given an event (or a cluster of      │
│  them), what narrative thread does it create or extend?     │
│  Extracted threads are first-class artifacts, stored in     │
│  SQLite, queryable, address-tagged.                         │
│  One focused LLM call per extraction event.                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  EMBROIDERY — HIGH WNS LAYERS                               │
│  NARRATIVE WEAVING. Given many threads in an area (region,  │
│  nation, world), how do they fit together into a coherent   │
│  narrative frame? Each higher layer weaves threads from     │
│  below into a summary whose content is itself queryable.    │
│  One focused LLM call per aggregation unit on fire.         │
└─────────────────────────────────────────────────────────────┘
```

Three operations, not seven-layer aggregation:
- **Extraction** (low WNS): "what story does this event or event-cluster tell?" — a per-event or per-small-cluster LLM call that produces a thread fragment.
- **Weaving** (middle WNS): "what do the threads in this region add up to?" — local narrative assembly.
- **Embroidery** (top WNS): "what is the world's current story?" — the frame that gives everything below it coherence.

The distinction from v2: v2 described all layers as the same operation (aggregation via weighted triggers). v3 says the operation changes by tier.

### 4.2 Relationship to WMS (parallel, not identical)

WNS still reuses most WMS infrastructure:

- **Address-tag immutability** ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)) — narrative layer events carry geographic addresses as facts, never LLM-written.
- **Prompt-fragment JSON structure** (`_meta`, `_core`, `_output`, `context:X`, `example:Y`) from `prompt_fragments_l*.json`.
- **Address-partition-before-LLM-reattach-after** pattern from each WMS layer manager.
- **Lazy evaluation** via `should_run()`.
- **`BackendManager.generate(task, system_prompt, user_prompt)`** call shape.

**What WNS does *differently* from WMS:**

- Operation per layer varies (extraction / weaving / embroidery). WMS layers are all the same operation (tag-rewriting narrations).
- Layer count is TBD. 7 is a starting point for matching WMS address hierarchy, but extraction might want fewer / different-shaped layers. We commit to the operational distinction, not the count.
- Triggers fire less often than WMS. Narrative moves slower than fact. Early guess: WMS thresholds × 2 per-layer, then tune.
- WNS is LLM at every layer from v1. No template-only pipeline tiers. (Assumes WMS will also move to LLM-at-every-layer once a tuned model lands — design for the future state.)

### 4.2 The narrative address system

WMS uses geographic address tags: `world:`, `nation:`, `region:`, `province:`, `district:`, `locality:`, `biome:`. Every WMS event carries its address as an immutable fact.

WNS reuses these exact same address tags. Narrative events happen *somewhere*. A rumor about mining unrest is addressed to the region where the mining is happening. A faction-tension beat is addressed to the nation where the factions clash. The user's framing, preserved:

> narratives will of course be affected greatly by geography. We will essentially be building a parallel WMS but for narratives.

Narrative events may *also* carry additional narrative-specific address tags that don't exist in the WMS:

- `thread:<thread_id>` — which emergent narrative thread this belongs to (if any)
- `arc:<arc_stage>` — opening / rising / climax / falling / resolved (optional, used by NL4+)
- `witness:<actor_id>` — who observed this (for NPC-grounded narrative events)

Same immutability rule as WMS address tags: these are facts about the narrative event, set at capture, never rewritten by an LLM.

### 4.3 The narrative layers — a working starting shape

The layer count is TBD. The starting shape below is a candidate to build against and tune:

| Layer | Operation | Unit | Input | Contents |
|---|---|---|---|---|
| **NL1** | Capture | Per raw event | WMS L2+ narrations tagged narratively-interesting; NPC mentions; player milestones | Narrative events — address-tagged, tagged for thread hints, stored |
| **NL2** | **Extraction** | Per event / small cluster | NL1 events | **Thread fragments**: "given this event or cluster, what narrative thread does it create or extend?" One LLM call per extraction event |
| **NL3** | **Weaving (local)** | Per district / locality | NL2 thread fragments in an address | Local narrative: "what story is this village telling this week?" |
| **NL4** | Weaving (regional) | Per region | NL3 + relevant NL2 | Regional narrative state |
| **NL5** | Weaving (national) | Per nation | NL4 + relevant NL3 | National-scale narrative arcs, tensions |
| **NL6** | **Embroidery (world)** | World | NL5 + selected NL4 | The world narrative summary — the artifact WES consumes |

**NL6 may be the terminal layer** (six total), or we may add an NL7 "world-arc retrospective" layer later. Starting with six is aligned with the address hierarchy (locality → district → region → nation → world) collapsing one level into extraction.

**Every layer is an LLM call.** No template layers. Each is one focused transform: address-tagged input → narrative output + rewritten content tags. Address tags pass through unchanged.

Prompt fragment files follow the existing pattern:
- `narrative_fragments_nl2.json` (extraction) through `narrative_fragments_nl6.json` (embroidery)

Backend task names: `"wns_layer2"` through `"wns_layer6"` in `backend-config.json`.

**This is a starting point, not a commitment.** Concrete layer count and per-layer responsibilities will shift during early playtest. What we commit to:
- NL1 is capture (no LLM).
- There is at least one extraction layer near the bottom.
- There is at least one embroidery layer at the top.
- Layers in between do progressively wider weaving.
- Every layer (except NL1 capture) is an LLM call.

### 4.4 NPC mentions as NL1 inputs (not NL1 creators)

The user was explicit that NPCs **do not create events**. If an LLM-driven NPC mentions "I heard the Ashen Cabal is hiring mercenaries in the capital," that dialogue does NOT become a canonical fact — the Ashen Cabal may not even exist. But the mention is still information:

> That way big events don't come from purely nothing.

WNS captures NPC mentions as **NL1 grounding inputs**. Mechanism:

1. `NPCAgentSystem` already has a dialogue pipeline. After every dialogue exchange, a *mention extractor* runs over the generated text (deterministic keyword/pattern extraction, not an LLM call) and pulls out:
   - Named entities mentioned (factions, locations, person names)
   - Claim type (rumor, observation, recollection, boast)
   - Significance hint (how much the NPC seemed to emphasize it)
2. Each extracted mention becomes an NL1 event with address tags (the NPC's current locality, carried over verbatim).
3. NL2/NL3 consolidators read NL1 mentions alongside WMS-derived narrations. **If a rumor recurs across multiple NPCs in the same region, it gains weight and eventually becomes part of the regional narrative.** If only one NPC ever mentions it, it fades with time.
4. Crucially, **a mention alone never triggers WES content generation**. Only the aggregated narrative that emerges from recurring mentions does — and only after it has bubbled up the pipeline to NL7.

This is the mechanism that makes "big events don't come from nothing" real. NPC hallucinations get filtered through the narrative pipeline's aggregation logic. Only patterns survive.

### 4.5 Narrative threads — the active product of extraction

> **Revision note (v3):** v2 framed threads as purely emergent (a supersession chain, discovered retrospectively). **Promoted in v3 to the explicit product of the NL2 extraction layer.** The user's metaphor requires it — *"the thread is made by the lower levels of WNS"* — threads are what extraction produces, not a side-effect of summarization.

A narrative thread is the primary artifact of the extraction layer. When NL2 receives an event (or small cluster of events) from NL1, it asks: **"given this event, what narrative thread does it create or extend?"** The answer is a thread fragment — a small, address-tagged, content-tagged narrative atom that is either:

- a new thread opening, or
- a continuation of an existing thread in scope, or
- a variation / reframing of a recent thread.

Thread fragments are first-class events, stored in SQLite, queryable, and directly consumed by the weaving layers above.

Concrete implications:

- NL2's LLM call outputs a thread fragment with fields: headline, content_tags, parent_thread_id (nullable), relationship (open/continue/reframe/close), address tags (pass-through from input).
- Extraction reads prior threads in the same address scope as context — continuity is informed, not imposed.
- Thread identity is the chain of parent_thread_id links. A dev tool can walk these chains to show named thread arcs, but the chain itself IS the thread — no separate "thread" table needed.
- Threads are forever. Archived, never deleted (per §9.Q10). Context budget manages inclusion; retention is unbounded.

**What this replaces:** v2's "emergent supersession chain" was closer than v1's explicit schema, but still underspecified. v3 makes threads the explicit output of one layer, which makes them first-class without making them heavyweight.

### 4.6 Inputs (what flows into WNS)

```
WMS:
  ├─ L7 WorldSummaryEvent  ─── drives NL7 work
  ├─ L6 nation summaries   ─── drive NL6 work
  ├─ L5 regional summaries ─── drive NL5 work
  ├─ L4/L3/L2 as needed   ─── drive lower NL layers
  └─ get_world_summary()  ─── ambient context

NPC system:
  └─ NPCAgentSystem dialogue events + mention extraction → NL1

Player activity (via existing GameEventBus):
  ├─ Milestones (level up, title earned, first-kill-of-boss) → NL1
  └─ Dramatic events (near-death, long journey, resource strike) → NL1

Faction system:
  ├─ Affinity deltas crossing thresholds → NL1 or NL2 depending on scope
  └─ Faction state summaries → context for NL3+

GeographicRegistry + EntityRegistry:
  └─ Proper names, biome types, entity identities for prompt humanization
```

### 4.7 Output (what WES consumes)

WES consumes exactly one artifact: **the latest NL7 world narrative summary**. Not a `NarrativeBeat`. The summary is a `WorldNarrativeSummary` event (parallel structure to `WorldSummaryEvent`):

```python
@dataclass
class WorldNarrativeSummary:
    summary_id: str
    world_id: str                          # always "world_0"
    created_at: float                      # game time
    narrative: str                         # 2-5 sentence world-narrative prose
    tags: List[str]                        # address + content tags
    severity: str                          # minor | moderate | significant | major | critical
    dominant_arcs: List[str]               # the story threads currently in play (emergent)
    dominant_regions: List[str]            # where the story is
    dominant_factions: List[str]           # who's in it
    source_nl6_summary_ids: List[str]      # backlinks
    supersedes_id: Optional[str]
```

When WES is invoked (§5), it reads the latest `WorldNarrativeSummary`. No `NarrativeBeat` dataclass is needed — a summary IS the artifact the executor plans against.

Lower-layer summaries also exist as queryable narrative state but aren't directly consumed by WES's `execution_planner`; they're used as context when a later embroidery-layer summary is being written, and may be consulted by individual `execution_hub_<tool>` calls (via live queries) for region/faction-specific flavor (§6).

### 4.8 Triggering (lazy, mirroring WMS)

No callback-based real-time trigger. Same `should_run()` / interval + weighted bucket pattern as WMS:

- NL1 events accumulate continuously.
- NL2 consolidator runs every N NL1 events per district (interval-based, default 15 — copy the WMS L3 interval).
- NL3+ each have weighted trigger buckets per aggregation unit, firing on narratively-interesting content tag accumulation. Thresholds tuned per layer (start with WMS values + adjust in playtest).
- An `NLTriggerManager` (parallel to `TriggerManager`) schedules `should_run()` ticks on each game-loop cycle.

NL7 trigger doubles as the WES invocation signal: when a new `WorldNarrativeSummary` is stored, publish `WORLD_NARRATIVE_SUMMARY_UPDATED` on the GameEventBus. WES subscribes.

### 4.9 Address-tag immutability — same rule

Verbatim extension of the WMS rule ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)):

- `ADDRESS_TAG_PREFIXES` extends to include narrative-specific addresses (`thread:`, `arc:`, `witness:`).
- Before every NL3+ LLM call: `partition_address_and_content()` splits tags, only content tags go to the LLM.
- After: re-attach address tags unchanged. Any invented-by-LLM address tag is dropped.

This is not just copy-paste — it's the *same function* reused. The immutability contract is a code-level invariant shared between WMS and WNS.

### 4.10 Storage

Narrative layer events stored in SQLite tables mirroring WMS's per-layer tables:

```sql
CREATE TABLE nl1_events (id TEXT PRIMARY KEY, created_at REAL, narrative TEXT, tags_json TEXT, payload_json TEXT);
CREATE TABLE nl2_events (...);
CREATE TABLE nl3_events (...);
...
CREATE TABLE nl7_events (...);

-- Tag junction tables per layer
CREATE TABLE nl1_tags (event_id TEXT, tag TEXT, PRIMARY KEY(event_id, tag));
...
CREATE TABLE nl7_tags (...);
```

Same SQLite file as WMS (keeps save/load atomic). Save-file version bumped on introduction.

### 4.11 No template fallbacks

v2 proposed template fallbacks at every NL layer (so the pipeline still produces valid events when backends are offline). **Removed in v3.**

Per user direction, WNS is LLM-driven at every layer. The design assumes:
- Ollama local inference is available whenever a layer fires.
- If Ollama is unreachable, the layer does not fire — it queues its pending work and retries on the next tick. Nothing crashes; nothing gets bypassed with a template.
- For dev/offline iteration, `MockBackend` (existing in `BackendManager`) still returns deterministic placeholder JSON. That's a backend-level fallback, not a layer-level template.

The invariant: a layer either produces a valid LLM-generated event, or produces no event at that tick. No halfway state with flat template output polluting higher layers.

### 4.12 Summary of changes

| v1 (single-call WNS) | v2 (parallel WMS, 7 layers, emergent threads) | v3 (extraction → weaving → embroidery) |
|---|---|---|
| `NarrativeBeat` schema | NL1-NL7 layer tables | Same table structure; operation per layer is different |
| — | 7 layers mirroring L1-L7 | **6 layers starting**; count is tunable; operation = extraction at bottom, embroidery at top |
| — | WNS L2 is template, rest LLM | **Every layer is LLM** (NL1 is capture-only, no synthesis) |
| `NarrativeThread` explicit schema | Threads emergent from supersession | **Threads are the explicit output of the extraction layer (NL2)** — first-class artifacts, address-tagged, retained forever |
| — | Template fallbacks at every LLM layer | **No template layers.** If LLM is unavailable, layer defers; MockBackend handles offline dev |
| Beat → WES input | `WorldNarrativeSummary` → WES input | Same — embroidery layer's output is what WES consumes |

---

## 5. WES Loop

> **Revision notes across versions.**
> - **v2:** Reframed as three-tier orchestrator-workers compound AI system; LLM self-critique dropped; mid-execution WES→WNS clarification dropped.
> - **v3:** Tier names renamed per user's preferred vocabulary. Shared immutable context object deleted; live queries against WNS's narrative-interpretation store take its place.

The **World Executor System** is where the user's description gets concrete. The WES must:

> **plan the narrative out, reason how to get there with the game, call upon the proper tools providing proper context, and then check the work.**

The user also described WES specifically as layered: *"LLMs as layers... WES needs to call LLM tools, then ensure balance, ensure proper handling, etc. So in some way agentic because of LLM tool calling connected to simpler LLMs."*

Architecturally, this is the **Orchestrator-Workers pattern** ([Anthropic, "Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents)): a central LLM dynamically breaks down tasks, delegates to worker LLMs, and synthesizes results. WES has three tiers, named per the user's vocabulary:

| Tier | Name | Role | Count |
|---|---|---|---|
| 1 | `execution_planner` | Decomposes narrative state into a structured plan of tool invocations. | One per invocation. Cloud-tolerated. |
| 2 | `execution_hub_<tool>` | Tool-specific coordinator. Turns one plan step into per-item specs, feeding them one-by-one into its executor_tool. Where flavor lives. | One LLM per tool type. Local. |
| 3 | `executor_tool_<tool>` | Pure JSON generator. One spec → one schema-valid artifact. | One LLM per JSON artifact. Local. |

Published equivalents (for searchability): planner ≈ Orchestrator / Supervisor; hub ≈ Coordinator / Worker-Supervisor; executor_tool ≈ Specialist / Worker.

### 5.1 The three-tier stack

```
Input: latest WorldNarrativeSummary (from WNS's top / embroidery layer)

        ┌──────────────────────────────────────────────────┐
        │  TIER 1 — execution_planner  (1 LLM)             │
        │                                                  │
        │  Reads (live query, at call time):               │
        │    - latest world narrative summary              │
        │    - registry counts (what content exists)       │
        │    - game awareness (tiers, biomes, domains)     │
        │                                                  │
        │  Produces: WESPlan (JSON) — ordered steps, slots,│
        │  dependencies, or explicit abandonment.          │
        └──────────────────────┬───────────────────────────┘
                               │ WESPlan
                               ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Deterministic code: resolve deps, topo-sort steps,        │
  │  reject cycles, verify known biomes/factions/tiers,        │
  │  check registry for duplicate IDs.                         │
  └────────────────────────────┬───────────────────────────────┘
                               ▼
  Plan dispatched step-by-step in topological order:
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │  TIER 2 — execution_hub_<tool>  (1 LLM per tool) │
        │                                                  │
        │  Reads (live query, at call time):               │
        │    - the plan step (handed in by code)           │
        │    - game awareness (same as planner)            │
        │    - tool-specific registry slice (live)         │
        │    - relevant narrative threads (live from WNS)  │
        │    - prior outputs from this hub's executor_tool │
        │      (sequential feedback within this plan step) │
        │                                                  │
        │  Produces: list of ExecutorSpecs, one per JSON   │
        │  artifact to be generated.                       │
        └──────────────────────┬───────────────────────────┘
                               │ ExecutorSpec (fed one by one)
                               ▼
        ┌──────────────────────────────────────────────────┐
        │  TIER 3 — executor_tool_<tool>  (1 LLM per JSON) │
        │                                                  │
        │  Reads (handed in by code):                      │
        │    - one ExecutorSpec                            │
        │    - task awareness (output schema, constraints) │
        │                                                  │
        │  Produces: one JSON dict matching tool's schema. │
        │  Pure "one input → one JSON" transform.          │
        └──────────────────────┬───────────────────────────┘
                               │ JSON
                               ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Deterministic code: parse + schema-validate + cross-ref   │
  │  check + balance-range check. Stage into Content Registry. │
  └────────────────────────────┬───────────────────────────────┘
                               ▼
                    [next ExecutorSpec, or next plan step]
                               │
                               ▼ (after all steps)
  ┌────────────────────────────────────────────────────────────┐
  │  Deterministic verification (no LLM): registry-wide orphan │
  │  scan, duplicate check, schema-wide consistency.           │
  │  COMMIT or ROLLBACK atomically.                            │
  └────────────────────────────────────────────────────────────┘
```

The three tiers never call each other directly. **Deterministic code is the only thing that crosses tier boundaries.** Each LLM takes a prompt constructed by code and produces structured output that code parses and hands to the next tier. This is the user's "one input for one LLM" principle enforced architecturally.

Abandonment is the only escape hatch: at any tier, failure may cause the plan to be marked `abandoned`. The narrative summary that justified the plan stays in history; nothing commits. No clarification loop with WNS — execution does not ask narrative for help.

### 5.2 Tier 1 — `execution_planner`

**Role**: single LLM call that decomposes a narrative summary into a structured plan.

**Backend**: cloud-tolerated (Claude via `BackendManager`, task `"wes_execution_planner"`). Per user: cloud only where necessary. The planner is one of the few roles where cloud is tolerated because (a) it's infrequent — once per WNS summary update — and (b) plan quality drives everything downstream. Local Ollama is the default; Claude is the escalation path when local output is structurally invalid on retry.

**What it reads (live, at call time):**
- The latest world narrative summary from `WorldNarrativeSystem.get_latest_summary()`.
- Registry counts via `ContentRegistry` (what exists, what's saturated).
- Game awareness block (tier definitions, biome taxonomy, domain taxonomy, faction registry, address tag prefixes).

No snapshot. No frozen context. When the planner runs, it sees the state of the world *right now*.

**Output: `WESPlan` (structured JSON)**

```python
@dataclass
class WESPlanStep:
    step_id: str
    tool: str                     # "hostiles" | "materials" | "nodes" | "skills" | "titles"
    intent: str                   # one-line human-readable goal
    depends_on: List[str]         # upstream step_ids
    slots: Dict[str, Any]         # tier, biome, domain, faction_id, etc.
                                  # may include <from s1.outputs.X> placeholders

@dataclass
class WESPlan:
    plan_id: str
    source_summary_id: str
    steps: List[WESPlanStep]
    rationale: str
    abandoned: bool = False
    abandonment_reason: str = ""
```

**Why produce a plan first, instead of dispatching to hubs directly?** Two reasons:

1. **Dependencies.** A hostile that drops a new material needs the material to exist first. Plan graph makes this explicit.
2. **Veto.** The planner can look at the whole plan and abort if it would produce orphan content or saturated tiers, before any executor_tool runs.

**What the planner does NOT do:**
- It does not call hubs or executor_tools. It outputs JSON that code dispatches.
- It does not see raw events or stats — it queries already-compressed narrative state.
- It does not write flavor text or per-item prose — that's the hub's job.

### 5.3 Tier 2 — `execution_hub_<tool>`

**Role**: each tool type (hostiles, materials, nodes, skills, titles) has its own hub. Given one plan step, the hub expands it into per-item ExecutorSpecs and dispatches each one to the executor_tool below. **This is where the tool becomes "agentic"** — the hub can decide "this step says make 3 hostiles; let me plan each one to feel distinct" and feed three specs in sequence.

**Backend**: local (Ollama, task `"wes_hub_<tool>"`).

**What it reads (live, at call time):**
- The plan step (handed in by code).
- Game awareness (same as planner).
- Tool-specific registry slice — queried live from `ContentRegistry` just before this hub's call.
- Relevant narrative threads — queried live from the WNS narrative store (e.g., active threads in the plan step's focal address).
- Prior outputs from this hub's own executor_tool within the same plan step (the sequential feedback loop).

**Output: a list of `ExecutorSpec`s**, dispatched one at a time to the executor_tool below.

```python
@dataclass
class ExecutorSpec:
    spec_id: str
    plan_step_id: str
    item_intent: str                      # e.g. "a T3 apex predator, ambush hunter, tundra-adapted"
    flavor_hints: Dict[str, Any]          # naming cues, prose fragments, narrative framing
    cross_ref_hints: Dict[str, Any]       # "this hostile should drop this staged material"
    hard_constraints: Dict[str, Any]      # tier range, biome, balance envelope
```

The hub is where **narrative flavor lives** — the user was explicit: *"The very bottom output of tools will be just the JSON. They are agentic because an LLM above the final tools... will feed one by one into the tools. This is where the flavor text would exist."*

**The "feed one by one" rule:** the hub emits one ExecutorSpec, waits for the executor_tool's JSON output, queries the registry fresh, then emits the next spec. Each executor_tool call is focused on one artifact; the hub adapts between calls — *"the first hostile came out as a wolf variant, so the second spec should diverge more."* It's a classic feedback loop that stays within the hub ↔ executor_tool pair. No other LLM in the system sees this loop.

### 5.4 Tier 3 — `executor_tool_<tool>`

**Role**: produce one schema-valid JSON artifact from one `ExecutorSpec`.

**Backend**: local (Ollama, task `"wes_tool_<tool>"`). High volume. Tuned for JSON correctness. Structured-output constrained decoding (Ollama grammars or server-side schema enforcement) where possible.

**What it reads:**
- The single ExecutorSpec (handed in by code from the hub above).
- Task awareness (its output schema, hard constraints).

That's it. No registry queries, no narrative queries, no game-state lookups — the hub has already done that work and compressed it into the spec. The executor_tool is a pure functional transform: **one spec in, one JSON out**.

Why this tier is thin on purpose:
- Local 7-13B models can be fine-tuned or prompt-engineered aggressively for *one focused JSON output*.
- Structured decoding is cheap when the output schema is fixed.
- Pure-function semantics makes parallel dispatch trivial later (deferred, see §6.7).

**No LLM-to-LLM calls.** The executor_tool cannot invoke another executor_tool, cannot query another hub, cannot reach back up to the planner. If it needs information the spec doesn't have, that's a design-error in the hub above it.

### 5.5 Deterministic glue — between every tier

The code between tiers is load-bearing. At each boundary:

1. **Parse** — LLM JSON + markdown-fence stripping (reuse `npc_agent._parse_dialogue_response` pattern).
2. **Schema validate** — hard reject on violation; one retry with stricter prompt; then mark step failed.
3. **Address-tag strip** — any invented `world:` / `region:` / etc. tag is dropped, same as WMS/WNS pattern.
4. **Cross-reference check** — referenced IDs must exist (live) or be staged in this plan (§7.3).
5. **Balance-range check** — stat values within tier multiplier envelope. Uses the `BalanceValidator` stub (§Q3).
6. **Stage** — insert into Content Registry with `staged=1`.

No verification LLM. Per user: *"a robust architecture with some smart detection and calls is enough."*

### 5.6 Final verification and commit

After all plan steps have staged outputs, one last deterministic pass runs registry-wide checks:

- **Orphan scan**: every `content_xref.ref_id` must resolve to a live or same-plan-staged content_id.
- **Duplicate scan**: no staged content_id collides with a live one.
- **Completeness**: every `WESPlanStep` has produced its expected staged artifact (or the plan is marked partial).

On pass → commit: flip all staged rows to live, publish `CONTENT_GENERATED` events per entity (these flow back to WMS via existing `EventRecorder`, closing the macro loop).

On fail → rollback: delete all staged rows for this plan, emit `PLAN_ABANDONED`, log for developer review.

**Observability is mandatory** (hierarchical LLM stacks are debugging nightmares without it): every tier logs its prompt + response + latency + token usage to `llm_debug_logs/wes/<plan_id>/<tier>_<step>_<spec>.json`. Root-cause analysis of "why did the hostile come out as a wolf again?" requires seeing all three tiers' I/O for that specific executor_tool call.

### 5.7 Asynchrony

Every LLM call goes through a unified async runner (extracted from `llm_item_generator.generate_async`). The game thread never blocks for a WES plan — plans run as background jobs on their own task queue. When a plan commits, new content appears "later that day" from the player's perspective. The world is in motion; we're not waiting.

### 5.8 What this shape rules out (intentionally)

- **No WES → WNS clarification calls.** Narrative leads. If a summary is under-specified, the planner abandons and waits for the next world-narrative update.
- **No LLM verifier.** Code owns verification. Smart detection is the deterministic cross-reference / balance / schema pipeline.
- **No per-tool custom topology.** Every tool uses the same `execution_hub_<tool>` ↔ `executor_tool_<tool>` pair. Differences are in prompts, not structure.
- **No frozen context snapshot passed through tiers.** Each tier queries live from canonical stores at its own call time. If the world shifted between the planner and the executor_tool, the executor_tool sees the newer state — that's the flexibility the design deliberately chose.

---

## 6. Tool Architecture

> **Revision notes across versions.**
> - **v2:** each tool reframed as a Coordinator+Specialist mini-stack (not a single LLM call).
> - **v3:** tier names renamed — each tool is an `execution_hub_<tool>` + `executor_tool_<tool>` pair. Contract updated to remove `shared_context` / `envelope` parameters; each tier reads live from canonical stores instead.

Five active tools (quests deferred). Each is a 2-LLM mini-stack. From the `execution_planner`'s perspective it's one tool; internally it's a hub + executor_tool pair.

1. The **`execution_hub_<tool>`** LLM takes one plan step, thinks about what items to generate, and produces a list of per-item ExecutorSpecs with flavor framing.
2. The **`executor_tool_<tool>`** LLM is invoked once per spec, producing one JSON artifact per call.
3. The hub sees each executor_tool output before emitting the next spec (sequential feedback within the mini-stack).

The planner and the final verification pipeline don't need to know this — they see "tool was invoked, N artifacts were staged." But everyone implementing a new tool works inside this two-LLM structure.

### 6.1 The mini-stack contract

```python
class ExecutionHub(Protocol):
    name: str                       # "hostiles" | "materials" | "nodes" | "skills" | "titles"
    registry_type: str              # registry table to write into

    def build_specs(self, step: WESPlanStep) -> List[ExecutorSpec]:
        """One LLM call: convert a plan step into a list of per-item specs.
        Reads live from ContentRegistry, WorldNarrativeSystem, and game-awareness
        sources internally — no context envelope passed in."""

    def adapt_after_output(self,
                           previous_specs: List[ExecutorSpec],
                           previous_outputs: List[Dict[str, Any]],
                           remaining_specs: List[ExecutorSpec]
                           ) -> List[ExecutorSpec]:
        """Optional LLM call: adjust remaining specs based on prior executor_tool
        outputs. Default implementation is a passthrough."""


class ExecutorTool(Protocol):
    name: str                       # same tool name as the hub
    schema_path: str                # JSON schema for the output

    def generate(self, spec: ExecutorSpec) -> Dict[str, Any]:
        """One LLM call: spec → JSON artifact. Purely functional."""

    def validate(self, output: Dict[str, Any],
                 registry: ContentRegistry) -> List[str]:
        """Deterministic code — return list of validation issues (empty = OK)."""

    def stage(self, output: Dict[str, Any],
              registry: ContentRegistry, plan_id: str) -> str:
        """Insert into registry with staged=True; return content_id."""
```

Shared infrastructure (one implementation, reused across all 5 mini-stacks):
- JSON parsing with markdown-fence stripping (reuse `npc_agent._parse_dialogue_response` pattern).
- Schema validation via `jsonschema` or lightweight dataclass validators.
- Retry policy (one retry on parse failure with stricter prompt).
- Observability: per-tier logs per spec to `llm_debug_logs/wes/<plan_id>/<tool>/<spec_id>_{hub,executor}.json`.

### 6.2 What goes where — hub vs executor_tool

| Concern | `execution_hub_<tool>` | `executor_tool_<tool>` |
|---|---|---|
| Reads the narrative / threads | ✅ (live query) | Sees only the distilled spec |
| Decides how many items to generate | ✅ | One spec → one output |
| Writes prose / name hints / flavor | ✅ | Fills schema fields |
| Chooses cross-references | ✅ | Honors references given |
| Enforces tier / biome constraints | — | ✅ (via schema + validator) |
| Produces game-valid JSON | — | ✅ |
| Backend | Local (Ollama) | Local (Ollama) |
| Frequency | 1 call per plan step | N calls per plan step |

The hub is where the tool becomes "agentic." The executor_tool is a pure transform.

### 6.3 The 5 tool mini-stacks

Five active tools; quests deferred. Each is an `execution_hub_<tool>` + `executor_tool_<tool>` pair following §6.1.

Each tool is described below with: **purpose**, **input slots**, **output schema**, **cross-refs to other tools**.

---

#### 6.3.1 `hostiles` — Enemy generator

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

#### 6.3.2 `materials` — Material generator

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

#### 6.3.3 `nodes` — Resource node generator

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

#### 6.3.4 `skills` — Skill generator

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

#### 6.3.5 `titles` — Title generator

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

#### 6.3.6 `quests` — Quest generator (DEFERRED)

**Purpose** (when implemented): create a quest that stitches other generated content into a playable arc.

**Status**: explicitly out of scope for this phase per the user. Listed here so the architecture slots don't need rework later. The quest tool will differ from the other five in one important way: it **references** other generated content rather than creating new content. A quest's "kill 5 hostileX" presumes hostileX exists. So:

- Quest tool runs last in any plan that contains one.
- Its context envelope includes a full list of same-plan content IDs.
- Its output schema matches `progression/npcs-1.JSON` quest blocks + existing quest system.

Until WES reaches the quest phase, the planner prompt explicitly excludes `quests` from available tool choices.

### 6.4 Generation order within a plan

Dependencies are naturally ordered and enforced by `execution_planner`'s `depends_on` output + code-level topo sort:

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

### 6.5 The "agentic" behavior — precisely defined

The user's phrasing: *"agentic because of LLM tool calling connected to simpler LLMs."* Within each mini-stack, the `execution_hub_<tool>` is the "agentic" one because:

- **It sees and responds to executor_tool outputs** before emitting the next spec (`adapt_after_output`). Classic feedback loop.
- **It owns narrative flavor** — cross-references, naming, prose framing. The executor_tool is mechanical.
- **It can decide to produce more or fewer items than the plan step suggested** within constraints, if the narrative calls for it.
- **It queries live** — ContentRegistry, WNS narrative store, faction state — all at call time. No pre-built envelope is handed to it.

**What the hub cannot do:**
- It cannot call another tool's hub (that's the `execution_planner`'s job via the plan).
- It cannot create plan steps.
- It cannot skip its executor_tool (every artifact must go through the bottom tier for schema validation).

This bounds the agency: each hub iterates on its own executor_tool's outputs within the scope of one plan step. Cross-tool coordination is mediated by the `execution_planner` and deterministic code, never by direct hub-to-hub calls.

### 6.6 Where prompts live

Two prompt fragment files per tool (one per tier):

- `prompt_fragments_hub_<tool>.json` — hub prompts (fan-out, flavor, specs)
- `prompt_fragments_tool_<tool>.json` — executor_tool prompts (spec → JSON schema)

Follows the existing `prompt_fragments_l*.json` layout (`_meta`, `_core`, `_output`, per-context variants). Same structure greppable across the whole config directory.

### 6.7 Parallelism (future, not v1)

In v1, an executor_tool within a single hub runs sequentially so the hub can adapt between calls. Two future parallelization opportunities, both deferred:

- **Parallel tools within a plan** — if two plan steps have no cross-dependency, run their hubs in parallel.
- **Parallel independent specs** — if the hub declares "these 3 specs don't depend on each other's outputs," skip sequential feedback and batch them to the executor_tool in parallel.

Both require infrastructure from `AsyncLLMRunner` that doesn't exist yet.

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

> **Revision notes across versions.**
> - **v2:** Dropped universal `ContextEnvelope` with 20/50/25/5 ratios; introduced per-LLM assemblers + shared immutable context as cross-cutting invariant.
> - **v3:** **Shared immutable context deleted entirely.** Each LLM queries canonical stores live at its own call time. "Context" shrinks to two things: game awareness (static, boot-loaded) and task awareness (what this call is asked to produce). The substitute for immutability is that every LLM reads from the *same canonical stores*, so there's no telephone to play.

The user's framing, preserved:

> **The true difficulty of this is the information.**

Every LLM call in this system is a focused transform: one input, one output. The entire system works only if each of those inputs is composed well — enough context for the call to succeed, nothing more. This section is the doc's center of gravity.

### 8.1 The core principle: LLMs as composable transforms reading from stores

Paraphrasing the user's framing:

> **"Usually for most LLMs it will be one input for one LLM, that output is then more useful and may or may not be used multiple times."**

And, on how context flows:

> **"It would be as it is. So we query in real time, just nicer and easier that way. But that's why we will store the narrative interpretations though. So the WNS high level will see only the narrative interpretations of events and use those."**

Two ideas, combined:

1. **LLMs are functions.** One input → one output → reusable artifact. Matches DSPy / Outlines / Mirascope. (Berkeley BAIR frames the whole thing as a **compound AI system**.)
2. **The "reusable artifact" lives in a canonical store.** Later LLMs read from that store directly — not from a propagated snapshot, not from paraphrased prose, not from a frozen dataclass. **Live queries over canonical stores.**

Three implications:

1. **Each LLM has one job.** Not "decide whether to do X or Y." One transform. Routing decisions are code.
2. **Outputs are stored, not paraphrased.** A WMS L6 summary is a row in SQLite that six different downstream callers can query. A NL3 regional narrative is a row in SQLite that the NL5 summarizer reads when it fires. No intermediate prose-paraphrase hop.
3. **Inputs are assembled per-call, per-role, via live queries.** No universal envelope. No LLM-shared memory. No snapshot propagation.

### 8.2 Why this replaces the "shared immutable context" idea

v2 had a `WESSharedContext` dataclass frozen at plan start, propagated through every tier. The goal was to mitigate **game of telephone** in a hierarchical LLM stack (by the time the bottom tier runs, the original intent has been paraphrased through the middle tiers and details are lost).

v3 solves the same problem a different way: **each tier reads from the same canonical stores**, so there is no telephone.

- The `execution_planner` reads the narrative summary from `WorldNarrativeSystem.get_latest_summary()`.
- The `execution_hub_<tool>` reads the **same** `get_latest_summary()` at its own call time, plus tool-relevant registry slices.
- The `executor_tool_<tool>` needs less — it sees only the ExecutorSpec prepared by the hub.

If the narrative shifts mid-plan (because new WMS events accumulated and a new embroidery-layer summary landed), downstream tiers see the newer state. Per user: *"It would be as it is"* — we accept that flexibility, and we accept the small risk that a late-running spec might diverge slightly from the plan that justified it. In practice the shift would be minor (narrative layers fire rarely), and the hub's registry-check step would catch any actual cross-reference breakage.

### 8.3 The two small things that DO propagate

Per user: *"There really isn't a shared immutable context besides overall game awareness and task awareness."*

Two tiny blocks travel with every prompt:

- **Game awareness** — static canonical constants loaded from JSON at boot:
  - Tier multipliers (T1=1.0x .. T4=8.0x)
  - Biome taxonomy
  - Domain taxonomy
  - Known faction_ids
  - `ADDRESS_TAG_PREFIXES` (for tag validation)
  - Narrative tag vocabulary
- **Task awareness** — what this call is asked to do:
  - Role (e.g., "you are an execution_hub_hostiles")
  - Output schema pointer
  - Hard constraints for this invocation

Both blocks are small (~500 tokens combined), stable across a session, and cheap to embed. Neither is a "context object" in the dataclass sense — they are small prompt fragments assembled from config plus per-call specifics.

### 8.4 The shape of the problem

Every LLM call has a budget:
- **Token budget** — local 7-13B models handle 4-8k context comfortably; degrade past ~8k. Cloud models handle 200k but at cost and latency.
- **Cognitive budget** — quality drops on dense, unstructured context regardless of max tokens. Relevant tokens > total tokens.
- **Coherence budget** — more context means more chances for self-contradiction, more places to hallucinate a cross-reference.

Meanwhile, the data available is enormous:
- WMS accumulates thousands of L1 events per play session (becomes LLM-narrated once tuned model lands).
- WNS mirrors this in parallel with narrative-specific extraction and weaving.
- Faction affinity, geographic registry, entity registry — hundreds of rows.
- Content Registry grows with every generated entity.

**Composing the right ~2-4k tokens per call is the entire game.**

### 8.5 Per-LLM context assemblers (no universal ratios)

There is no `ContextEnvelope` dataclass with fixed tier ratios. Each LLM role has its own `ContextAssembler` that composes its prompt from live queries. "Tune for everything" is the rule — assemblers iterate independently.

Current assemblers (one per LLM role):

| Assembler | Feeds | Queries (live) |
|---|---|---|
| `WNSExtractionAssembler` (low layers) | NL2 extraction LLMs | NL1 events in scope + prior threads in same address |
| `WNSWeavingAssembler` (mid layers) | NL3-NL5 weaving LLMs | Same-layer prior summary (supersession chain) + lower-layer events in the aggregation unit |
| `WNSEmbroideryAssembler` (top) | NL6 embroidery LLM | NL5 nation summaries + selected NL4 + current ongoing conditions from WMS facade |
| `ExecutionPlannerAssembler` | WES Tier 1 | `get_latest_summary()` + `ContentRegistry.counts()` + game-awareness |
| `ExecutionHubAssembler_<tool>` (one per tool) | WES Tier 2 | Plan step (handed in) + tool-specific registry slice + narrative threads in focal address |
| `ExecutorToolAssembler_<tool>` (one per tool) | WES Tier 3 | Single ExecutorSpec + schema |
| `NPCDialogueAssembler` (existing) | NPCAgentSystem | NPC memory + faction context + latest world summary |

Each assembler is free to pick its own token budget target, its own priorities, its own inclusion rules. Assemblers share NO universal structure beyond "embed the small game-awareness + task-awareness blocks from §8.3."

### 8.6 Pre-compression via WMS + WNS layers

Both pipelines are context-compression pyramids:

- **WMS**: raw events (thousands) → layer narrations (fewer at each step) → world-level summary (one).
- **WNS**: narrative-worthy events → thread fragments (extraction) → regional/national narrative (weaving) → world narrative (embroidery).

This means **later LLMs never walk raw events**. They read from the top of their pyramid. Each layer's LLM call was already one focused transform — the one-input-one-output principle applied recursively. By the time WES reads the WNS embroidery output, thousands of underlying events have been compressed through multiple LLM-driven passes.

This is why WNS must *be* a pipeline, not a single call. A single-call WNS would have to compress thousands of events in one prompt. A layered WNS compresses incrementally, producing reusable artifacts at each level that higher layers query live.

### 8.7 NPC mention tracking — grounding without event creation

Per §4.4, NPC dialogue doesn't create canonical events. But NPC mentions *do* flow into NL1 as grounding inputs, and eventually bubble into regional narratives if they recur.

Information-flow mechanics:

1. After each NPC exchange, a **deterministic mention extractor** (no LLM call) runs over dialogue text — keyword patterns, named-entity hints, significance heuristics.
2. Extracted mentions become NL1 events with the NPC's locality address.
3. The NL2 extraction layer sees mentions alongside WMS-derived narrations. Only mentions that recur (same entity mentioned by multiple NPCs in the same region) gain enough weight to be extracted into a thread fragment.
4. Single-NPC hallucinations never get extracted. They stay as isolated NL1 entries, archived forever but ignored by weaving layers.

This gives NPCs a path to seed future narrative without letting any one NPC control it. The extraction layer's pattern-recognition (and its own LLM judgment) is the filter.

### 8.8 Distance decay (narrative address system)

Narrative address tags (§4.2) enable geographic filtering for local consumers:

```
Event occurs at (region_R, locality_L)
  ├─ same locality  : full narrative, immediate
  ├─ same district  : full narrative, with delay
  ├─ same region    : headline only
  ├─ same nation    : "I heard something about..."
  └─ distant        : dropped, OR if major severity, rumor variant
```

This matters for:
- **NPC dialogue assembler** (existing, in `NPCAgentSystem`) — distant events should not appear as casual NPC knowledge.
- **Future WES localized runs** — if WES generates content tied to a specific region, the hub's live queries should weight same-region narrative state more heavily than world-level.

Implementation: the `GeographicRegistry` already computes parent-child relationships. A `NarrativeDistanceFilter` utility class on top of it is small work; the harder piece is deciding the concrete decay curve per consumer, which is playtest-tuned.

Out of scope for WNS v1 (world-scope only). In scope when WES starts producing localized content.

### 8.9 Context poisoning — mitigations across the whole stack

A single bad LLM output anywhere in WMS or WNS can pollute downstream. Mitigations:

**Already in place (WMS):**
- Address-tag immutability ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)) — LLMs cannot invent regions.
- Content tags must exist in `tag_library.py` — new-tag pollution blocked.
- Narrations are bounded length; over-length outputs truncated.

**New in WNS (mirrored):**
- Narrative address tags (`thread:`, `arc:`, `witness:`) follow the same immutability rule.
- NL-layer LLM calls strip address tags before the call, re-attach after.
- NL summarizers pick content tags from a known narrative-tag taxonomy, cannot invent.

**New in WES:**
- No LLM-to-LLM direct calls, so no tier-to-tier pollution vector.
- Each tier queries canonical stores live — no stale context to pollute a downstream call.
- Every `executor_tool` output goes through schema validation + registry cross-reference check before being staged.
- Observability: full prompt+response logs per tier per spec. "Why did this happen?" is answerable by reading the logs.

### 8.10 Where context actually comes from — concrete sources

| Source | API | Queried by (live, at call time) |
|---|---|---|
| `WorldMemorySystem.get_world_summary()` | facade (shipped) | WNS assemblers, `execution_planner` |
| `LayerStore.query_by_tags(layer=N, ...)` | existing | WNS assemblers (WMS layer N narrations as input) |
| `WorldNarrativeSystem.get_latest_summary()` | **NEW** (§4.7) | `execution_planner` assembler |
| `WorldNarrativeSystem.query_threads(address, ...)` | **NEW** (§4.5) | `execution_hub_<tool>` assemblers (flavor in focal address) |
| `NLLayerStore.query_by_tags(layer=N, ...)` | **NEW** (§4.10) | WNS assemblers (prior same-unit summaries) |
| `FactionSystem.stats` / `get_npc_profile()` | existing | WNS assemblers, `execution_hub_<tool>` |
| `GeographicRegistry` | existing singleton | All (address resolution, name humanization) |
| `EntityRegistry` | existing singleton | `execution_hub_<tool>` (what NPCs/enemies exist) |
| `StatTracker.get_summary()` | existing | `execution_hub_titles` (unlock hints) |
| `ContentRegistry` | **NEW** (§7) | `execution_planner`, `execution_hub_<tool>`, verify step (anti-orphan, diversity) |
| NPC mention log | **NEW** (§4.4, §8.7) | NL1 input source |

Everything shipped is battle-tested. Everything NEW is green-field for this phase.

### 8.11 Observability — non-negotiable

Hierarchical LLM stacks are debugging nightmares without tracing. "Why did this hostile come out as a wolf variant again?" must be answerable.

Every LLM call logs:
- Assembled prompt (system + user)
- Game-awareness + task-awareness blocks that were embedded
- The queries that were run (store + filter + result count)
- Raw response
- Parsed output
- Token usage + latency
- Backend used (Ollama/Claude/Mock)

File layout:
```
llm_debug_logs/
  ├─ wms/                          # Existing
  │  └─ <timestamp>_<layer>.json
  ├─ wns/                          # New
  │  ├─ nl2/<timestamp>_<address>.json    # extraction
  │  ├─ nl3/<timestamp>_<address>.json    # weaving (local)
  │  ├─ ...
  │  └─ nl6/<timestamp>.json              # embroidery
  └─ wes/                          # New
     └─ <plan_id>/
        ├─ execution_planner.json
        ├─ hub_<tool>_<step>.json
        └─ tool_<tool>_<step>_<spec>.json
```

This makes every generation event root-causeable by reading files on disk. No special UI required; grep and jq suffice. Observability tools like LangSmith or Langfuse can be layered on later if the log volume warrants.

---

## 9. Open Questions & Decisions Needed

> **Revision notes across versions.**
> - **v2:** First round of resolved items captured.
> - **v3:** Four more questions resolved (NL2 LLM-everywhere, live queries, threads-forever, tier names). Q1 reframed around extraction/weaving.

### Active questions

#### Q1. NL layer trigger configuration + extraction granularity

**Problem**: WNS layers must fire — but at what granularity?

User's framing:
> *"The Narrative firing might honestly be something more akin to narrative extraction. Like given Y event what narrative thread exists? Then that goes up the WNS so a full narrative can be woven."*
> *"Depends on how many layers for the NL, but likely something like every X amount of events by layer. Less often for sure."*

So: fewer fires than WMS, and the bottom NL layer isn't an aggregation — it's an extraction. Two independent sub-questions:

**Q1a. Extraction granularity at NL2.** When does the extraction layer fire — per single NL1 event? per small cluster? per fixed interval?
- Per-event: every narratively-interesting event triggers an extraction LLM call. Highest resolution, highest volume.
- Per-cluster: extraction waits for N NL1 events in a locality, then extracts what thread(s) they form together. Lower volume, may miss fast single-event threads.
- Per-interval: extraction runs on a timer regardless of event count. Predictable, may miss bursts.

**Lean**: per-cluster at first (N≈3-5 events per locality), with a cluster-timeout so an event that's alone for a while still gets extracted. Tune in playtest.

**Q1b. Weaving cadence at middle/upper layers.** How much narrative aggregation before NL3-NL6 fires?
- Direct copy of WMS thresholds = too frequent for narrative.
- WMS thresholds × 2 = reasonable first guess.
- "Every X amount of events by layer" (user's phrasing) = match WMS's event-count + weighted-bucket pattern but scaled up.

**Lean**: start with WMS values × 2 for each NL weaving layer. Every layer logs its fire rate so we can tune in playtest.

#### Q3. BalanceValidator — stub, build, or skip?

**Problem**: Same as v1. CLAUDE.md flags BalanceValidator as designed-not-built. `executor_tool` outputs need balance checking.

**Options**:
- **A**: Minimal stub (~50 LOC) reading tier multipliers from `Definitions.JSON/stats-calculations.JSON`, rejecting outliers.
- **B**: Skip balance checks in v1.
- **C**: Build per full spec before WES ships.

**Lean**: A. The stub is enough to prevent embarrassing outputs; the full BalanceValidator remains a separate project.

#### Q4. Generated JSONs on disk or registry-only?

**Problem**: Sacred boundary: existing content JSON directories are off-limits. Where does generated content live?

**Options**:
- **A**: Parallel `generated/` directories, loaders glob both.
- **B**: Registry-resident only — databases learn to union live JSON with registry rows.
- **C**: Both — registry is authoritative, JSON written as backup / export.

**Lean**: B. Avoids touching sacred directories; cleaner save/load; registry is already the authority for cross-references.

#### Q5. Narrative tag taxonomy — new file or extension of existing?

**Problem**: WMS enforces content-tag membership via `tag_library.py` / `tag-definitions.JSON`. WNS needs its own narrative-content tag vocabulary (arc stages, tone descriptors, thread-lineage tags). Where does it live?

**Options**:
- **A**: Extend `tag-definitions.JSON` with a new namespace (`narrative:*` prefix).
- **B**: New sibling file `narrative-tag-definitions.JSON` loaded by an extended `TagLibrary`.
- **C**: Inline in each `narrative_fragments_nl*.json` (no central taxonomy).

**Lean**: B. Keeps narrative tag evolution independent of game-content tag evolution. Both get loaded by the same `TagLibrary` singleton via a minor extension.

#### Q6. SQLite database — shared with WMS or separate?

**Problem**: WNS needs tables for narrative layer events + tag junctions. Co-locate in the WMS SQLite file (`world_memory.db`) or separate (`world_narrative.db`)?

**Options**:
- **A**: Shared database. Pro: atomic save/load, single connection, easy cross-table queries. Con: file grows.
- **B**: Separate database. Pro: clean separation, independent evolution. Con: save/load atomicity requires coordination.

**Lean**: A. The save system already handles the WMS SQLite file. Adding narrative tables to it is zero extra save/load work.

#### Q8. Player Intelligence (Part 3) — dependency or defer?

Part 3 (player profile) isn't built. WNS/WES would benefit.

**Lean**: B — ship WNS/WES without it; `execution_planner` and hubs run without player profile; add it later when Part 3 arrives.

#### Q9. When do executor_tool calls within a hub run in parallel?

**Problem**: §6.7 notes parallelism is deferred. Real question: when should a hub declare "these specs are independent" vs. "I need to see each output before emitting the next"?

**Options**:
- **A**: Always sequential in v1.
- **B**: Parallel when the hub flags `independent=true` on a batch.
- **C**: Auto-parallelize any spec that doesn't reference a prior spec's output.

**Lean**: A in v1, B in v2. C requires static analysis of spec references — more infrastructure than we want to build early.

---

### Resolved (decision captured, no longer blocking)

- **[RESOLVED v2] Backend selection per LLM call** — Cloud (Claude) only for `execution_planner` and possibly the WNS top layer. Everything else local (Ollama). Per user: *"Ideally none"* — cloud is fallback, not default. Routing via `backend-config.json` task types.
- **[RESOLVED v2] Unified async runner** — Yes. Build `AsyncLLMRunner` for WES; migrate NPC dialogue to it; leave `llm_item_generator` alone until it needs touching.
- **[RESOLVED v2] Rollback semantics** — Hard rollback (all-or-nothing per plan) in v1.
- **[RESOLVED v2] LLM verifier / evaluator** — None. Verification is deterministic code plus observability logging. Per user: *"a robust architecture with some smart detection and calls is enough."*
- **[RESOLVED v2] WES → WNS clarification loop** — Dropped. Narrative leads, execution serves. If a narrative summary is under-specified, the `execution_planner` abandons. The next narrative update produces a new summary.
- **[RESOLVED v2] Universal ContextEnvelope with fixed tier ratios** — Dropped. Per-LLM-role assemblers with individual tuning.
- **[RESOLVED v3] NL2 template vs LLM** → **LLM at every layer.** No template-only NL tiers. Assume WMS also moves to LLM-at-every-layer once the tuned model lands. For offline dev, MockBackend is the fallback at the backend level, not at the layer level.
- **[RESOLVED v3] Thread retention** → **Forever, archived.** No time-based pruning. Threads remain queryable indefinitely. Context budget manages inclusion, not retention — same model as WMS events.
- **[RESOLVED v3] Threading — emergent schema vs first-class** → **First-class output of NL2 extraction layer.** Not an explicit `NarrativeThread` dataclass table, but thread fragments are the primary artifact extraction produces, address- and tag-tagged, with `parent_thread_id` forming the thread chain.
- **[RESOLVED v3] Shared context — snapshot vs live** → **Live queries.** No frozen context propagates through tiers. Each LLM queries canonical stores at its own call time. Two tiny things travel with every prompt: game awareness (static constants) and task awareness (what to produce). Per user: *"we query in real time, just nicer and easier that way."*
- **[RESOLVED v3] Tier naming** → `execution_planner` → `execution_hub_<tool>` → `executor_tool_<tool>`. Published pattern names (Orchestrator-Workers, etc.) retained as citations.

---

## 10. Phased Implementation Roadmap

> **Revision notes across versions.**
> - **v2:** 7→10 phase expansion to reflect WNS-as-pipeline scope.
> - **v3:** Template-NL2 step removed (LLM at every layer). Tier names renamed. `WESSharedContext` removed (live queries instead). NL layer count loosened from 7 to "extraction + weaving + embroidery, ~6 starting."

Each phase produces a shippable increment. No phase requires the next phase to provide value. The total scope is larger than a single-call WNS would have been — narrative extraction + weaving + embroidery is a real pipeline.

### P0 — Shared Infrastructure

Plumbing. Every later phase needs it.

- **P0.1** `AsyncLLMRunner` — unified background-thread executor with dependency-ordered step execution. Extract from `llm_item_generator.generate_async` into `world_system/living_world/async_runner.py`.
- **P0.2** Game-awareness + task-awareness prompt blocks — small helper that emits the two tiny context blocks described in §8.3. Used by every assembler.
- **P0.3** `ContextAssemblerBase` — framework class for per-LLM-role assemblers. Subclasses own their query logic; base provides the two awareness blocks and the logging hook.
- **P0.4** NPC dialogue async migration — move synchronous `_generate_npc_opening` onto the new runner. Acceptance test for P0.1.
- **P0.5** L7 subscription hook — `Layer7Manager.register_world_summary_callback()` for WMS→WNS notification.

Exit criteria: NPC dialogue no longer blocks the UI; ≥5 new passing tests covering the runner + assembler base.

---

### P1 — WNS Foundation (NL1 capture + NL2 extraction)

The bottom of the narrative pipeline: ingesting events into NL1, and producing the first thread fragments via LLM extraction at NL2. **Every LLM layer in WNS is real — no template tier.**

- **P1.1** Narrative tag taxonomy — new `narrative-tag-definitions.JSON` + extended `TagLibrary`. Includes narrative address prefixes (`thread:`, `arc:`, `witness:`) appended to `ADDRESS_TAG_PREFIXES`.
- **P1.2** NL layer storage — SQLite tables `nl1_events` through `nl6_events` (starting shape — count TBD per §4.3) + tag junctions. Co-located in the WMS database.
- **P1.3** NL1 ingestion pipeline:
  - Subscribe to WMS L2+ events tagged "narratively interesting"
  - Subscribe to player milestone events
  - Deterministic NPC-mention extractor (no LLM) ingests dialogue output
- **P1.4** NL2 extraction LLM — *given a cluster of NL1 events, what thread does it create/extend?* Output: thread fragments with address tags, content tags, `parent_thread_id` (nullable). Prompt fragments in `narrative_fragments_nl2.json`. BackendManager task: `"wns_layer2"`. Per-cluster trigger (~3-5 events per locality, with cluster-timeout).
- **P1.5** `NLTriggerManager` — parallel to `TriggerManager`. Interval/cluster triggers for NL2, weighted buckets for higher layers.
- **P1.6** `WorldNarrativeSystem` facade (parallel to `WorldMemorySystem`) with initial methods: `initialize()`, `get_instance()`, `query_threads(address)`.

Exit criteria: a play session generates at least one thread fragment per active locality. Every NL2 fire writes a valid row to `nl2_events` with address + content tags. Threads are queryable by address.

---

### P2 — WNS Weaving Layers (NL3-NL5)

The middle of the pipeline: weaving thread fragments into local/regional/national narrative.

- **P2.1** NL3 weaving LLM — per district/locality. Reads NL2 thread fragments in scope + prior NL3 for same address (supersession). Prompt fragments: `narrative_fragments_nl3.json`. Weighted trigger (start WMS threshold × 2).
- **P2.2** NL4 weaving LLM — per region. Reads NL3 + selected NL2.
- **P2.3** NL5 weaving LLM — per nation. Reads NL4 + selected NL3.
- **P2.4** Address-tag immutability enforced at every layer — reuse `partition_address_and_content()` from `geographic_registry.py`.
- **P2.5** Each layer has a template fallback for offline dev (MockBackend is fine — no layer-level template needed, just backend-level Mock).

Exit criteria: a play session produces narrative state at all three scopes (local, regional, national) for areas with enough activity. Narrative reads coherently across layers (region summary references thread fragments that extraction produced).

---

### P3 — WNS Embroidery Layer (NL6) + WorldNarrativeSummary

The top of the pipeline. The artifact WES consumes.

- **P3.1** NL6 embroidery LLM — single world bucket, world narrative summary output. `narrative_fragments_nl6.json`. Supersession logic.
- **P3.2** `WorldNarrativeSummary` event schema (§4.7).
- **P3.3** Publish `WORLD_NARRATIVE_SUMMARY_UPDATED` on GameEventBus when NL6 fires.
- **P3.4** `WorldNarrativeSystem.get_latest_summary()` — the method WES's `execution_planner` queries.
- **P3.5** Minimal dev UI — F-key overlay showing the latest world-narrative summary. Sanity check for playtesters.

Exit criteria: L7 fires → NL pipeline responds up through extraction + weaving → eventually NL6 fires → a new `WorldNarrativeSummary` is queryable and reads like actual story.

---

### P4 — Content Registry

Coordination layer for generated content. No generators yet.

- **P4.1** Registry SQLite tables (§7.2): per-tool tables + unified `content_xref`.
- **P4.2** Registry API: `stage_content`, `commit`, `rollback`, `list_live`, `list_staged_by_plan`, `find_orphans`, `counts()`.
- **P4.3** Integration with existing databases — `MaterialDatabase`, `EnemyDatabase`, etc. learn to union JSON-loaded content with registry-live content.
- **P4.4** Save/load wiring — registry state persists atomically with the rest of the save.

Exit criteria: can manually stage a fake material, commit it, see it in `MaterialDatabase.get_instance().materials`, roll back via API.

---

### P5 — WES Deterministic Shell (no LLM)

The whole WES pipeline except the LLM calls. Proves the plumbing before any prompt tuning.

- **P5.1** `WESPlanStep` + `WESPlan` dataclasses (§5.2).
- **P5.2** `ExecutorSpec` dataclass (§5.3).
- **P5.3** Topological plan dispatcher — deterministic code that walks a plan and invokes tiers in order.
- **P5.4** Staging + atomic commit/rollback flow.
- **P5.5** Final verification pipeline (§5.6): orphan scan, duplicate scan, completeness.
- **P5.6** Observability scaffolding — `llm_debug_logs/wes/<plan_id>/` directory structure, per-tier logging.
- **P5.7** Stub `execution_planner` + stub `execution_hub` + stub `executor_tool` — hardcoded plans/specs/JSONs for test runs. No LLM calls yet.

Exit criteria: a hardcoded stub plan with 2-3 stub tool steps runs end-to-end, stages content, commits, and the content is live in the relevant databases. Rollback also works.

---

### P6 — WES `execution_planner` (Tier 1 LLM)

Replace the stub planner with a real LLM call.

- **P6.1** `ExecutionPlannerAssembler` — queries latest world-narrative summary, registry counts, taxonomies live at call time.
- **P6.2** Planner LLM integration — `BackendManager.generate(task="wes_execution_planner")`. Ollama default; cloud (Claude) as escalation on retry.
- **P6.3** Prompt fragments: `prompt_fragments_wes_execution_planner.json`.
- **P6.4** Subscribe to `WORLD_NARRATIVE_SUMMARY_UPDATED`. On trigger, queue a plan-generation job.

Exit criteria: world-narrative summary updates → planner runs → produces a valid plan → stub tiers complete it → content appears in the registry. Plans are coherent with the summary they came from.

---

### P7 — First Tool Mini-Stack: `materials`

End-to-end LLM generation for one tool type. Proves the hub + executor_tool pattern.

- **P7.1** `execution_hub_materials` — Tier 2 LLM call producing `ExecutorSpec` list. Prompt fragments: `prompt_fragments_hub_materials.json`.
- **P7.2** `executor_tool_materials` — Tier 3 LLM call producing JSON material. Prompt fragments: `prompt_fragments_tool_materials.json`. Structured output via Ollama grammar if available.
- **P7.3** BalanceValidator stub (§9.Q3) — tier multiplier range check.
- **P7.4** Dev CLI `debug_create_material(plan_step)` — bypass planner, test hub + executor_tool in isolation.

Exit criteria: planner plan → materials mini-stack → valid staged material → commit → gathering the relevant node yields the new material. Real end-to-end play.

---

### P8 — Tool Expansion

Remaining 4 tools. Each follows the P7 pattern.

- **P8.1** `execution_hub_nodes` + `executor_tool_nodes` — cross-ref to materials. Proves the cross-reference path.
- **P8.2** `execution_hub_skills` + `executor_tool_skills` — compose from existing tags only (no tag invention).
- **P8.3** `execution_hub_titles` + `executor_tool_titles` — cross-ref to StatTracker stats + skills.
- **P8.4** `execution_hub_hostiles` + `executor_tool_hostiles` — capstone; cross-refs to materials (drops), skills (enemy skills), biomes, factions.

Exit criteria per tool: single-tool plans produce schema-valid, cross-ref-clean content. Full test: 4-step plan with all 4 new tools runs end-to-end.

---

### P9 — Multi-Step Plans + Observability

Unlock the planner to produce multi-tool plans; ship the observability tools.

- **P9.1** Planner prompt updated to allow multi-step plans.
- **P9.2** Topological dependency execution stress-tested (plans with 5+ steps, 2+ tools).
- **P9.3** Cross-plan diversity — planner queries recent `CONTENT_GENERATED` history live, avoids repetition.
- **P9.4** Metrics dashboard — plans/hour, tool success %, orphan count, tier usage by backend.
- **P9.5** Retrospective thread detector — offline tool that clusters NL2 supersession chains into named threads for dev-side visualization.
- **P9.6** "Why this output?" tracer — given a generated content_id, walk backwards through the logs to show the world-narrative summary, the planner plan, the hub specs, and the executor_tool prompt that produced it.

Exit criteria: 10-minute play session produces ≥1 multi-tool plan that commits successfully. A developer can pick any generated item in-game and get the full provenance chain from logs alone.

---

### Deferred — Explicit Scope Exclusions

Per user direction. Re-open when P0-P9 are proven:

- **Quest generation** (§6.3.6) — needs Content Registry + ≥3 active tools to have enough material to reference.
- **Ecosystem integration** — `EcosystemAgent` exists as a query tool; extend `execution_hub_materials` / `execution_hub_nodes` to consult `get_scarcity_report()` when planning.
- **Player Intelligence (Part 3)** — WES and WNS run fine without it; add player-profile slot to the task-awareness block when Part 3 lands.
- **Distance-decayed context for localized content** — §8.8. Only needed when WES produces sub-regional content.
- **Parallel executor_tool execution within a hub** — §6.7. Sequential in v1.
- **Developer injection tool** — CLI for seeding world-narrative summaries, bypassing the pipeline. Useful for playtest, not critical path.
- **Replacing `llm_item_generator` with AsyncLLMRunner** — leave alone until it needs touching.
- **WMS layers going LLM** — assumed to happen once user's tuned model lands; WNS is designed for the post-transition world so no WNS change is needed when it does.

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

