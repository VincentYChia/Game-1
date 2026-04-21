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

## Revision History

- **v1** (2026-04-20) — initial doc.
- **v2** (2026-04-20) — restructured after user feedback. Major changes:
  - Unidirectional flow `WMS → WNS → WES → Tools → Game` (dropped bidirectional WNS↔WES).
  - WNS reframed as a **parallel WMS for narratives** with geographic addressing (NL1-NL7), not a single LLM call.
  - WES reframed as a **three-tier orchestrator-workers compound AI system** (Orchestrator → Coordinator → Specialist).
  - Each tool is a Coordinator+Specialist mini-stack, not a single LLM call.
  - Shared immutable context object propagates through every tier (game-of-telephone mitigation).
  - Dropped: LLM self-critique, WES→WNS clarification loop, universal `ContextEnvelope` with fixed tier ratios.
  - Added: LLM Roster (§2.5), narrative address system (§4.2), NPC mention tracking as NL1 (§4.4), emergent narrative threads (§4.5), observability (§5.7, §8.10).
  - Roadmap expanded from 7 to 10 phases to reflect WNS-as-pipeline scope.

## Table of Contents

1. [Current Shipped State (Grounding)](#1-current-shipped-state-grounding)
2. [System Architecture: WMS → WNS → WES → Tools → Game (unidirectional)](#2-system-architecture)
3. [Trigger Signal Chain (L7 feeds WNS, NL7 fires WES)](#3-trigger-signal-chain)
4. [WNS Design — Parallel WMS for Narratives](#4-wns-design)
5. [WES Loop — Three-Tier Orchestrator-Workers Stack](#5-wes-loop)
6. [Tool Architecture (5 Coordinator+Specialist Mini-Stacks)](#6-tool-architecture)
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
│  WES — World Executor System (NEW, orchestrator-workers)         │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 1: ORCHESTRATOR (1 LLM, cloud-eligible)            │   │
│   │  Plans what to build from the narrative summary.         │   │
│   └─────────────────────────┬────────────────────────────────┘   │
│                             │ structured plan                    │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 2: COORDINATORS (1 LLM per tool, local)            │   │
│   │  Owns flavor + context shaping. Feeds items one-by-one   │   │
│   │  into the Specialist below it.                           │   │
│   └─────────────────────────┬────────────────────────────────┘   │
│                             │ per-item spec                      │
│                             ▼                                    │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Tier 3: SPECIALISTS (1 LLM per call, local)             │   │
│   │  Raw JSON generators — pure "one input → one JSON" calls │   │
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
| **LLM style** | Flat — each narrative layer = one focused call (mirrors WMS) | Layered — orchestrator-workers (three tiers) |
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

### 2.4 The shared immutable context object

One principle cuts across every LLM call in the system: **each call takes one focused input, produces one output, and that output becomes a reusable artifact downstream.** LLMs are treated as composable transforms, not agents.

But a danger in hierarchical stacks is **game of telephone** — by the time a Specialist LLM runs, the original narrative intent has been paraphrased three times and critical detail is gone. Mitigation: every call at every tier receives the same **shared immutable context object** alongside its tier-specific prompt. This object carries the non-negotiable invariants of the current run:

- The narrative beat ID + headline (verbatim, never paraphrased)
- The geographic address(es) in scope
- The active narrative threads
- The calling player's profile snapshot (future, from Part 3)
- Hard constraints (tier range, biome restrictions, faction refs)

Each layer appends its interpretation to its prompt; the **shared context is never rewritten**. Specialists see both their Coordinator's instructions *and* the original intent. This is the single highest-leverage choice in the whole design.

### 2.5 LLM Roster

Naming every LLM in the system, with its tier, backend preference, and call shape. "LLM" alone is too coarse — each role has different quality/latency/cost requirements.

| LLM role | Layer | Backend (preferred) | Call shape | Frequency |
|---|---|---|---|---|
| WMS L3 consolidator | WMS internal | Local (Ollama) | 1 call per district per interval | Moderate |
| WMS L4/L5/L6 summarizer | WMS internal | Local | 1 call per aggregation unit on weighted fire | Low |
| WMS L7 summarizer | WMS internal | Local | 1 call when world bucket fires | Very low |
| **WNS NL3-NL7 summarizers** | WNS | Local (mirrors WMS) | 1 call per narrative aggregation unit | Low-moderate |
| **WES Orchestrator** | WES Tier 1 | Cloud-eligible (Claude) | 1 call per WNS summary delivery | Low |
| **WES Tool Coordinators** | WES Tier 2 | Local | N calls per run (one per item fed to Specialist) | Moderate |
| **WES Tool Specialists** | WES Tier 3 | Local | N calls per run (one per JSON artifact) | High |
| NPC dialogue | Existing (NPCAgentSystem) | Local | 1 per player-NPC exchange | Variable |

**Cloud minimization rule:** cloud APIs (Claude) are reserved for the WES Orchestrator and *possibly* the WNS top layer (NL7 summarizer). Everything else runs locally. Cloud latency is tolerable here because orchestrator and high-layer summaries don't need to be instant — they represent slow-moving world state, not per-frame reactions.

**Layered vs flat:**
- **Flat LLM** = single focused call, no LLM-to-LLM dispatch. WMS layers, WNS layers, NPC dialogue.
- **Layered LLM** = an LLM whose job is to orchestrate other LLMs. Only the WES has this, and only because generating content coherently across 6 tool types with cross-refs requires planning that a flat call can't do.

### 2.6 Vocabulary this doc uses (and the published equivalents)

Grounding terminology in the published literature so future contributors can search:

| This doc | Published equivalent | Source |
|---|---|---|
| Compound AI system | Compound AI systems | Berkeley BAIR 2024 |
| WES as "orchestrator-workers" | Orchestrator-Workers pattern | Anthropic "Building Effective Agents" |
| Three-tier stack | Hierarchical agent teams | LangGraph |
| Local-at-bottom, cloud-at-top | LLM cascading / model routing | FrugalGPT (Chen et al. 2023) |
| One-input-one-output-reusable | LLM-as-function / functional pipelines | DSPy, Outlines, Mirascope |
| Shared immutable context object | Shared blackboard / invariant context | Cognition AI "Don't Build Multi-Agents" (anti-pattern mitigation) |

### 2.7 Philosophy: LLMs write content, code owns structure

Every LLM call in the system follows the discipline the WMS already uses ([layer7_manager.py:442-500](Game-1-modular/world_system/world_memory/layer7_manager.py#L442-L500)):

- **Code builds the prompt and assembles context.** LLMs never see raw SQL results.
- **Code validates every output.** LLM JSON is parsed, schema-checked, retried on failure.
- **Address tags are facts, never LLM-writable.** This rule extends verbatim to WNS's narrative address tags (§4).
- **Structured artifacts between layers, not prose.** Coordinators receive JSON plans from the Orchestrator; Specialists receive JSON specs from Coordinators. Prose is for humans; machines pass typed data.

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

> **Revision note (2026-04-20, v2):** Previous draft treated WNS as a single LLM call producing a `NarrativeBeat`. **That is wrong.** WNS is a **parallel WMS for narratives** with its own geographic addressing and its own 7-layer pipeline mirroring the WMS. Narrative threads are an *emergent property* of good WNS output, not a bolted-on schema.

### 4.1 WNS is a parallel WMS for narratives

The WMS compresses gameplay events into a geographically-addressed 7-layer pipeline ([layer3..7_manager.py](Game-1-modular/world_system/world_memory/)). Each higher WMS layer is one focused LLM call that takes an aggregation unit's events and writes a narration with rewritten content tags (the address tags are facts, never rewritten).

WNS does the same thing, but for **narrative state** rather than factual state. The inputs are different (WMS narrations, NPC mentions, player milestones); the outputs are different (beats, threads, locale-flavored rumors); but **the structural pipeline is the same**.

```
WMS:  L1 raw events → L2 evaluator narrations → L3..L7 geographic summaries
WNS:  NL1 narrative events → NL2 local beats → NL3..NL7 aggregated story at wider scopes
```

This means WNS reuses, directly:

- The address-tag immutability pattern (§2.7, [geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)) — narrative address tags are facts, never LLM-written.
- The prompt-fragment JSON structure (`_meta`, `_core`, `_output`, `context:X`, `example:Y`) pioneered in `prompt_fragments_l*.json`.
- The "partition address vs content, strip before LLM, reattach after" mechanism from each WMS layer manager.
- The lazy evaluation / `should_run()` triggering pattern.
- The `BackendManager.generate(task, system_prompt, user_prompt)` call shape and layer-specific temperature/max_tokens config.

**What WNS does NOT reuse:** trigger conditions. Narrative fires on narratively-interesting patterns, not on factual accumulation. See §4.5.

### 4.2 The narrative address system

WMS uses geographic address tags: `world:`, `nation:`, `region:`, `province:`, `district:`, `locality:`, `biome:`. Every WMS event carries its address as an immutable fact.

WNS reuses these exact same address tags. Narrative events happen *somewhere*. A rumor about mining unrest is addressed to the region where the mining is happening. A faction-tension beat is addressed to the nation where the factions clash. The user's framing, preserved:

> narratives will of course be affected greatly by geography. We will essentially be building a parallel WMS but for narratives.

Narrative events may *also* carry additional narrative-specific address tags that don't exist in the WMS:

- `thread:<thread_id>` — which emergent narrative thread this belongs to (if any)
- `arc:<arc_stage>` — opening / rising / climax / falling / resolved (optional, used by NL4+)
- `witness:<actor_id>` — who observed this (for NPC-grounded narrative events)

Same immutability rule as WMS address tags: these are facts about the narrative event, set at capture, never rewritten by an LLM.

### 4.3 The narrative layers (NL1 through NL7)

Mirroring WMS, but with narrative-appropriate content at each layer:

| Layer | Aggregation unit | Input | LLM? | Contents |
|---|---|---|---|---|
| **NL1** | (raw event) | Raw narrative events: NPC mentions, player milestones, dialogue-introduced rumors, WMS L2 narrations tagged narratively interesting | No (template) | Like WMS L1 — captured, not narrated |
| **NL2** | Locality / district | NL1 events clustered per district | No (template, mirrors WMS L2 evaluators being template-based today) | "Local color" narrations: a particular village's ongoing gossip |
| **NL3** | District → Region | NL2 beats clustered per region | Yes, 1 LLM call per region per interval | Regional story — e.g. "the mines of the Ashen Hills are emptying, and people have started blaming the guild" |
| **NL4** | Region → Province | NL3 + selected NL2 | Yes, weighted trigger | Province-level narrative arc |
| **NL5** | Province → Region-band | NL4 + selected NL3 | Yes, weighted trigger | Multi-province narrative crosscurrents |
| **NL6** | Region-band → Nation | NL5 + selected NL4 | Yes, weighted trigger | National narrative state — tensions, triumphs, dominant arcs |
| **NL7** | Nation → World | NL6 + selected NL5 | Yes, weighted trigger | **The world narrative summary** — the artifact WES consumes |

Each layer's LLM call is **one focused transform**: aggregation-unit narrative events (address-tagged) → rewritten content tags + narrative text. Exactly the WMS pattern ([layer4_manager.py:237-240](Game-1-modular/world_system/world_memory/layer4_manager.py#L237-L240) being the canonical reference).

Prompt fragment files (one per layer, following the existing pattern):
- `narrative_fragments_nl2.json` through `narrative_fragments_nl7.json`

Backend task names follow `BackendManager` conventions: `"wns_layer3"`, `"wns_layer4"`, ..., `"wns_layer7"`. Config lives in `backend-config.json` alongside the existing `wms_layer*` tasks.

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

### 4.5 Narrative threads — emergent, not bolted on

Earlier draft proposed a `NarrativeThread` schema where WNS explicitly tags each beat with a thread_id. User correction:

> The narrative threads are actually a really cool idea... Ideally I would want the WNS produce as it will, but hopefully creating something like narrative threading.

Threading is the **aspirational emergent property** of a well-tuned WNS pipeline, not a schema. Mechanism:

- Each NL3+ summarizer has access to prior summaries from the same aggregation unit (WMS already does this via `_find_supersedable`).
- When a new summary references narrative elements from the prior one (same factions, same arc stage, same named entities) — *that continuity is threading, by emergence*.
- We do NOT force thread IDs. We do log which summaries superseded which. Thread identity is the chain of supersession.
- A retrospective thread detector (dev-tool, runs offline) can assign thread labels by clustering chained summaries. Useful for debug UI and observability, not required for system function.

**What this means for implementation**: no `narrative_threads` table in v1. Just the narrative layer tables with supersession backlinks. Thread-as-concept lives in the LLM's prompt context ("your last summary for this region said X — keep continuity or show evolution") but is not a first-class schema field until we prove it's needed.

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

Lower-layer summaries (NL3-NL6) also exist as queryable narrative state but aren't directly consumed by WES; they're used as context when a later NL7 summary is being written, and may be consulted by WES Coordinators for region/faction-specific flavor (§6).

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

### 4.11 Template fallback

Every NL3+ LLM call has a template fallback. When the backend is unavailable, the summarizer falls back to a deterministic synthesis: concatenate headline strings from contributing lower-layer events, attach pass-through tags, set severity from the max contributor. Uglier than LLM output; still structurally valid. Same invariant as before: the fallback path must produce valid events that higher layers can consume.

### 4.12 Summary — what changes vs. the v1 draft

| v1 draft | v2 (this doc) |
|---|---|
| Single LLM call producing `NarrativeBeat` | Parallel WMS pipeline NL1-NL7 |
| `narrative_beats` + `narrative_beat_tags` tables | Per-layer `nl1..nl7_events` tables + tag junctions |
| `NarrativeThread` as explicit schema | Threads as emergent supersession chains |
| WNS fires on L7 callback directly | NL layers fire lazily; NL7 fires on bucket threshold; NL7 output triggers WES |
| Beat → WES input | `WorldNarrativeSummary` → WES input |
| NPC dialogue doesn't affect narrative | NPC mentions feed NL1 (tracked, not event-creating) |

---

## 5. WES Loop

> **Revision note (2026-04-20, v2):** Previous draft framed WES as a four-phase linear pipeline (Plan → Reason → Call → Verify) with LLM self-critique in Verify. **Replaced.** WES is now an **orchestrator-workers compound AI system** — a three-tier LLM stack. Reason is folded into the Orchestrator. Self-critique LLM is dropped per user direction: "a robust architecture with some smart detection and calls is enough." Mid-execution clarification calls to WNS are removed: narrative leads, execution serves, execution does not talk back to narrative.

The **World Executor System** is where the user's description gets concrete. The WES must:

> **plan the narrative out, reason how to get there with the game, call upon the proper tools providing proper context, and then check the work.**

The user also described WES specifically as layered: *"LLMs as layers... WES needs to call LLM tools, then ensure balance, ensure proper handling, etc. So in some way agentic because of LLM tool calling connected to simpler LLMs."*

That is the **Orchestrator-Workers pattern** ([Anthropic, "Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents)): a central LLM dynamically breaks down tasks, delegates to worker LLMs, and synthesizes results. The WES has three tiers of LLMs, with deterministic code at every boundary.

### 5.1 The three-tier stack

```
Input: latest WorldNarrativeSummary (from WNS NL7)

            ┌──────────────────────────────────────────────┐
            │  TIER 1 — ORCHESTRATOR (1 LLM, cloud-tier)   │
            │                                              │
            │  Reads: narrative summary + registry counts  │
            │         + game constraints (shared ctx)      │
            │  Produces: structured WESPlan (JSON)         │
            │  - ordered tool steps with slots and         │
            │    dependencies                              │
            │  - or explicit abandonment with reason       │
            └────────────────────┬─────────────────────────┘
                                 │ WESPlan (JSON, immutable)
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Deterministic code: resolve deps, build per-tool envelopes, │
  │  reject circular deps, verify known biomes/factions,         │
  │  check registry for duplicates / diversity constraints.      │
  │  (This replaces the old "Phase 2: REASON" LLM step.)         │
  └──────────────────────────────┬───────────────────────────────┘
                                 ▼
  Plan dispatched step-by-step in topological order:
                                 │
                                 ▼
            ┌──────────────────────────────────────────────┐
            │  TIER 2 — COORDINATOR (1 LLM, per tool type) │
            │                                              │
            │  Reads: step intent + slots + envelope       │
            │         + shared immutable context           │
            │  Produces: one or more specialist prompts    │
            │  This is where flavor, cross-ref hints, and  │
            │  per-item narrative framing live.            │
            └────────────────────┬─────────────────────────┘
                                 │ per-item specialist spec
                                 ▼ (fed one by one)
            ┌──────────────────────────────────────────────┐
            │  TIER 3 — SPECIALIST (1 LLM, per JSON item)  │
            │                                              │
            │  Reads: single item spec + shared ctx        │
            │  Produces: raw JSON matching game schema     │
            │                                              │
            │  One input → one JSON → composable artifact  │
            └────────────────────┬─────────────────────────┘
                                 │ JSON
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Deterministic code: parse + schema-validate + cross-ref     │
  │  check + balance-range check. Stage into Content Registry.   │
  └──────────────────────────────┬───────────────────────────────┘
                                 ▼
                      [next step in plan]
                                 │
                                 ▼ (after all steps)
  ┌──────────────────────────────────────────────────────────────┐
  │  Deterministic verification (no LLM): registry-wide          │
  │  orphan check, duplicate check, schema-wide consistency.     │
  │  COMMIT or ROLLBACK atomically.                              │
  └──────────────────────────────────────────────────────────────┘
```

The Orchestrator, Coordinators, and Specialists never talk directly LLM-to-LLM. **Deterministic code is the only thing that crosses tier boundaries.** Each LLM takes a prompt constructed by code and produces structured output that code parses and hands to the next tier. This is the user's "one input for one LLM" principle enforced architecturally.

Abandonment is the only "escape hatch": at any tier, a failure may cause the Orchestrator's plan to be marked `abandoned`. The beat-summary that triggered the plan stays in history; nothing commits. No clarification loop with WNS — execution does not ask narrative for help.

### 5.2 Tier 1 — Orchestrator

**Role**: single LLM call that decomposes a narrative summary into a structured plan of tool invocations.

**Backend**: cloud-eligible (Claude via `BackendManager`, task `"wes_orchestrator"`). Per user: *"Maybe the highest level executor and WNS"* gets cloud. Everything else local.

**Input**: a `WorldNarrativeSummary` + registry snapshot + geographic/domain taxonomies (the **shared immutable context object**, §2.4).

**Output**: `WESPlan` (structured JSON).

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

**Why a plan first, not direct dispatch to Coordinators?** Two reasons:
1. **Dependencies.** A new hostile that drops a new material needs the material to exist first. Plan graph makes this explicit.
2. **Veto.** The Orchestrator can look at the full plan and say "this would create 12 orphan materials; abort" before any Specialist runs.

**What the Orchestrator does NOT do:**
- It does not call Coordinators or Specialists. It outputs JSON that code dispatches.
- It does not see raw events or stats — only the pre-compressed narrative summary.
- It does not write flavor text or per-item prose — that's the Coordinator's job.

### 5.3 Tier 2 — Coordinators (one LLM per tool type)

**Role**: each tool (hostiles, materials, nodes, skills, titles) has a Coordinator LLM that takes one `WESPlanStep` and expands it into one or more specialist specs to be generated. **This is where the tool becomes "agentic"** — the Coordinator can decide "this step says make 3 hostiles; let me plan each one to feel distinct" and feed three specs into the Specialist below.

**Backend**: local (Ollama, task `"wes_coord_<tool>"`). Quality/creativity important but volume is manageable.

**Input**: a single `WESPlanStep` + the shared immutable context object + a tool-specific context envelope assembled by code (registry slice relevant to this tool, see §8).

**Output**: a list of **Specialist specs** — one per JSON artifact the Specialist will generate.

```python
@dataclass
class SpecialistSpec:
    spec_id: str
    plan_step_id: str
    item_intent: str                      # e.g. "a T3 apex predator, ambush hunter, tundra-adapted"
    flavor_hints: Dict[str, Any]          # naming cues, prose fragments, narrative framing
    cross_ref_hints: Dict[str, Any]       # "this hostile should drop this staged material"
    hard_constraints: Dict[str, Any]      # tier range, biome, balance envelope
```

The Coordinator is where **narrative flavor lives** — the user was explicit: *"The very bottom output of tools will be just the JSON. They are agentic because an LLM above the final tools... will feed one by one into the tools. This is where the flavor text would exist."*

**The "feed one by one" rule:** Coordinators produce a list of specs but dispatch them to Specialists **sequentially**. Each Specialist call is focused on one artifact; the Coordinator sees each output before generating the next spec. This lets the Coordinator adapt — "the first hostile came out as a wolf variant, so the second spec should diverge more." It's a classic feedback loop that stays within the Coordinator→Specialist pair.

### 5.4 Tier 3 — Specialists (one LLM per JSON artifact)

**Role**: produce a single schema-valid JSON artifact from a single `SpecialistSpec`.

**Backend**: local (Ollama, task `"wes_spec_<tool>"`). High volume. Tuned for JSON correctness. Structured-output constrained decoding (via Ollama's grammar support or server-side schema enforcement) where possible.

**Input**: one `SpecialistSpec` + the shared immutable context object.

**Output**: one JSON dict matching the tool's output schema.

Specialists are **pure functional transforms**. One spec in, one JSON out. No loops, no multi-step reasoning, no awareness of other specialists. They exist at this tier because:

- Local models can be fine-tuned or prompt-engineered aggressively for *one focused JSON output*
- Structured decoding (e.g., JSON schema enforcement) is cheap when the output shape is fixed
- Parallel dispatch across multiple Specialists becomes possible once the Coordinator has stopped needing feedback

In v1, Specialists dispatch sequentially (driven by the Coordinator's feedback loop). In v2, independent specs may be dispatched in parallel to a local inference server.

### 5.5 The shared immutable context object

Propagated through every LLM call at every tier. Never rewritten, only read. Mitigates the "game of telephone" failure mode identified as the single highest-risk issue in hierarchical LLM stacks ([Cognition AI: Don't Build Multi-Agents](https://cognition.ai/blog/dont-build-multi-agents)).

```python
@dataclass(frozen=True)
class WESSharedContext:
    # From WNS — the narrative that justifies this run
    narrative_summary_id: str
    narrative_headline: str              # verbatim NL7 narrative field
    focal_regions: List[str]             # address tags from the summary
    focal_factions: List[str]
    focal_arcs: List[str]

    # Invariants from the game
    tier_definitions: Dict[int, float]   # T1..T4 multipliers (canonical)
    biome_taxonomy: List[str]            # known biomes
    domain_taxonomy: List[str]           # known domains
    faction_registry: List[str]          # existing faction_ids
    address_prefixes: List[str]          # ADDRESS_TAG_PREFIXES (for tag validation)

    # Player profile (stub until Part 3 ships)
    player_profile: Optional[Dict[str, Any]] = None
```

Every prompt at every tier embeds a fixed `<shared_context>` block derived from this object. Coordinators and Specialists see **exactly what the Orchestrator saw**, plus their tier-specific additions. A Specialist generating the 5th hostile has the same narrative_headline the Orchestrator saw 20 LLM calls ago.

### 5.6 Deterministic glue — between every tier

The code between tiers is load-bearing. At each boundary:

1. **Parse** — LLM JSON + markdown-fence stripping (reuse `npc_agent._parse_dialogue_response` pattern).
2. **Schema validate** — hard reject on violation; one retry with stricter prompt; then mark step failed.
3. **Address-tag strip** — any invented `world:` / `region:` / etc. tag is dropped, same as WMS/WNS pattern.
4. **Cross-reference check** — referenced IDs must exist (live) or be staged in this plan (§7.3).
5. **Balance-range check** — stat values within tier multiplier envelope. Uses the `BalanceValidator` stub (§Q3).
6. **Stage** — insert into Content Registry with `staged=1`.

No verification LLM. Per user: *"robust architecture with some smart detection and calls is enough."*

### 5.7 Final verification and commit

After all plan steps have staged outputs, one last deterministic pass runs registry-wide checks:

- **Orphan scan**: every `content_xref.ref_id` must resolve to a live or same-plan-staged content_id.
- **Duplicate scan**: no staged content_id collides with a live one.
- **Completeness**: every `WESPlanStep` has produced its expected staged artifact (or the plan is marked partial).

On pass → commit: flip all staged rows to live, publish `CONTENT_GENERATED` events per entity (these flow back to WMS via existing `EventRecorder`, closing the macro loop).

On fail → rollback: delete all staged rows for this plan, emit `PLAN_ABANDONED`, log for developer review.

**Observability is mandatory** (from Agent B's research — hierarchical stacks are debugging nightmares): every tier logs its prompt + response + latency + token usage to `llm_debug_logs/wes/<plan_id>/<tier>_<step>_<spec>.json`. Root-cause analysis of "why did the hostile come out as a wolf again?" requires seeing all three tiers' I/O for that specific specialist.

### 5.8 Asynchrony

Every LLM call goes through a unified async runner (extracted from `llm_item_generator.generate_async`). The game thread never blocks for a WES plan — plans run as background jobs on their own task queue. When a plan commits, new content appears "later that day" from the player's perspective. The world is in motion; we're not waiting.

### 5.9 What this shape rules out (intentionally)

- **No WES → WNS clarification calls.** Narrative leads. If a summary is under-specified, the Orchestrator abandons and waits for the next NL7 summary.
- **No LLM verifier.** Code owns verification. Smart detection is the deterministic cross-reference / balance / schema pipeline.
- **No per-tool custom topology.** Every tool uses the same Coordinator → Specialist pair. Differences are in prompts and envelope contents, not structure.

---

## 6. Tool Architecture

> **Revision note (2026-04-20, v2):** Earlier draft treated each tool as a single LLM call + validator. **Replaced.** Per user: *"The very bottom output of tools will be just the JSON. They are agentic because an LLM above the final tools (but still part of the same tool from the executors perspective) will feed one by one into the tools. This is where the flavor text would exist."* Every tool is now a **Coordinator + Specialist mini-stack** (§5.3-5.4). From the Orchestrator's perspective it's one tool; internally it's a two-LLM pipeline.

Six tools. Each is a Coordinator+Specialist pair, not a single LLM call. From WES Tier 1's perspective, the Orchestrator calls a named tool with a plan step. What happens inside that tool is:

1. The **Coordinator LLM** takes the plan step, thinks about what items to generate, and produces a list of per-item Specialist specs with flavor framing.
2. The **Specialist LLM** is invoked once per spec, producing one JSON artifact per call.
3. Coordinator sees each Specialist output before emitting the next spec (sequential feedback within the tool).

The Orchestrator and the verification pipeline don't need to know this — they see "tool was invoked, N artifacts were produced, here they are staged." But everyone writing a new tool works inside this two-LLM structure.

### 6.1 The mini-stack contract

```python
class WESToolCoordinator(Protocol):
    name: str                       # "hostiles" | "materials" | "nodes" | "skills" | "titles"
    registry_type: str              # registry table to write into

    def build_specs(self, step: WESPlanStep,
                    shared_context: WESSharedContext,
                    envelope: ContextEnvelope) -> List[SpecialistSpec]:
        """One LLM call: convert a plan step into a list of per-item specs."""

    def adapt_after_specialist(self, previous_specs: List[SpecialistSpec],
                               previous_outputs: List[Dict[str, Any]],
                               remaining_specs: List[SpecialistSpec]
                               ) -> List[SpecialistSpec]:
        """Optional LLM call: adjust remaining specs based on prior Specialist outputs.
        Default implementation is a passthrough (no adaptation)."""


class WESToolSpecialist(Protocol):
    name: str                       # same tool name as the Coordinator
    schema_path: str                # JSON schema for the output

    def generate(self, spec: SpecialistSpec,
                 shared_context: WESSharedContext) -> Dict[str, Any]:
        """One LLM call: spec → JSON artifact. Purely functional."""

    def validate(self, output: Dict[str, Any],
                 registry: ContentRegistry) -> List[str]:
        """Return list of validation issues (empty = OK).
        Deterministic code, not an LLM call."""

    def stage(self, output: Dict[str, Any],
              registry: ContentRegistry, plan_id: str) -> str:
        """Insert into registry with staged=True; return content_id."""
```

Shared infrastructure (one implementation, reused across all 5 tool mini-stacks):
- JSON parsing with markdown-fence stripping (reuse `npc_agent._parse_dialogue_response` pattern).
- Schema validation via `jsonschema` or lightweight dataclass validators.
- Retry policy (one retry on parse failure with stricter prompt).
- Observability: per-tier logs per spec to `llm_debug_logs/wes/<plan_id>/tool_<name>/<spec_id>_{coord,spec}.json`.

### 6.2 What goes where — Coordinator vs Specialist

A useful split-of-concerns rubric:

| Concern | Coordinator | Specialist |
|---|---|---|
| Reads the narrative flavor | ✅ | Sees only the distilled spec |
| Decides how many items to generate | ✅ | One spec → one output |
| Writes prose / name hints | ✅ | Fills schema fields |
| Chooses cross-references | ✅ | Honors references given |
| Enforces tier / biome constraints | — | ✅ (via schema + validator) |
| Produces game-valid JSON | — | ✅ |
| Backend | Local (Ollama) | Local (Ollama) |
| Frequency | 1 call per plan step | N calls per plan step |

The Coordinator is where the tool becomes "agentic." The Specialist is a pure transform.

### 6.3 The 5 tool mini-stacks

The six tools listed originally have **quests deferred**. Five are active. Each is a Coordinator + Specialist pair following §6.1.

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

Dependencies are naturally ordered and enforced by Orchestrator `depends_on` + code-level topo sort:

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

The user's phrasing: *"agentic because of LLM tool calling connected to simpler LLMs."* Within each tool mini-stack, the Coordinator is the "agentic" one because:

- **It sees and responds to Specialist outputs** before emitting the next spec (`adapt_after_specialist`). Classic feedback loop.
- **It owns narrative flavor** — cross-references, naming, prose framing. The Specialist is mechanical.
- **It can decide to produce more or fewer items than the plan step suggested** within constraints, if the beat calls for it.

**What the Coordinator cannot do:**
- It cannot call another tool (that's the Orchestrator's job).
- It cannot create plan steps (Orchestrator's job).
- It cannot query WNS or WMS directly — it only sees what the deterministic envelope-builder hands it.

This bounds the agency: Coordinators iterate on their own Specialist's outputs within the scope of one plan step. Cross-tool coordination is always mediated by the Orchestrator and deterministic code.

### 6.6 Where prompts live

Two prompt fragment files per tool (one per tier):

- `prompt_fragments_coord_<tool>.json` — Coordinator prompts (fan-out, flavor, specs)
- `prompt_fragments_spec_<tool>.json` — Specialist prompts (spec → JSON schema)

Follows the existing `prompt_fragments_l*.json` layout (`_meta`, `_core`, `_output`, per-context variants). Same structure greppable across the whole config directory.

### 6.7 Parallelism (future, not v1)

In v1, Specialists within a single tool run sequentially so the Coordinator can adapt. Two future parallelization opportunities, both deferred:

- **Parallel tools within a plan step** — if `depends_on` is empty between two plan steps of different tools, run their Coordinators in parallel.
- **Parallel independent specs** — if the Coordinator declares "these 3 specs don't depend on each other's outputs," skip sequential feedback and batch to the Specialist in parallel.

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

> **Revision note (2026-04-20, v2):** The earlier draft invented a single `ContextEnvelope` dataclass with fixed 20/50/25/5 tier ratios, and framed `NarrativeThread` as a context-budget device. **Replaced.** No universal ratios (per user: *"Tune for everything. It needs to be different by each LLM. I can't really give a strong rule."*). Per-LLM-role envelopes instead, plus the shared immutable context object as a first-class cross-cutting invariant. Threads as a context notion are folded into §4.5 (emergent supersession chains), not a separate schema.

The user's framing, preserved:

> **The true difficulty of this is the information.**

Every LLM call in this system is a focused transform: one input, one output. The entire system works only if each of those inputs is composed well — enough context for the call to succeed, nothing more. This section is the doc's center of gravity.

### 8.1 The core principle: LLMs as composable transforms

Paraphrasing the user's framing:

> **"Usually for most LLMs it will be one input for one LLM, that output is then more useful and may or may not be used multiple times."**

This is a **functional pipeline** model, not an agent loop. It matches the DSPy / Outlines / Mirascope school of thought: treat prompts as compiled-ish functions, their outputs as typed artifacts, and build compound behavior by composing them. The theoretical frame (Berkeley BAIR): this is a **compound AI system**, not an agent.

Three implications:

1. **Each LLM has one job.** Not "decide whether to do X or Y." One transform. Routing decisions are code.
2. **Outputs are artifacts, not conversations.** A WMS L6 summary is a structured event that six different downstream callers can read. Don't discard it after one use.
3. **Inputs are assembled per-call, per-role, from artifacts.** No universal envelope, no LLM shared memory.

### 8.2 The shape of the problem

Every LLM call has a budget:
- **Token budget** — local 7-13B models handle 4-8k context comfortably; degrade past ~8k. Cloud models handle 200k but at cost and latency.
- **Cognitive budget** — quality drops on dense, unstructured context regardless of max tokens. Relevant tokens > total tokens.
- **Coherence budget** — more context means more chances for self-contradiction, more places to hallucinate a cross-reference.

Meanwhile, the data available in this system is enormous:
- WMS accumulates thousands of L1 events per play session.
- ~33 WMS evaluators produce L2 narrations continuously.
- WNS mirrors this with NL1-NL7 accumulating in parallel.
- Faction affinity, geographic registry, entity registry — hundreds of rows.
- Content Registry grows with every generated entity.

**Composing the right ~2-4k tokens per call is the entire game.**

### 8.3 Per-LLM context envelopes (no universal ratios)

There is no `ContextEnvelope` dataclass with fixed tier ratios. Instead, each LLM *role* has its own `ContextAssembler` class that builds the prompt from first principles for that role.

Current assemblers (one per LLM role):

| Assembler | Feeds | Tuned for |
|---|---|---|
| `WNSLayerNAssembler` (one per narrative layer) | WNS NL3-NL7 summarizers | Aggregation-unit narrative events + upstream facts + prior same-unit summary |
| `WESOrchestratorAssembler` | WES Tier 1 | Latest NL7 summary + registry counts + taxonomies + shared immutable context |
| `WESCoordinatorAssembler` (one per tool) | WES Tier 2 | Plan step + tool-specific registry slice + shared immutable context |
| `WESSpecialistAssembler` (one per tool) | WES Tier 3 | Single SpecialistSpec + schema pointer + shared immutable context |

Each assembler is free to pick its own token budget target, its own tier priorities, its own inclusion rules. **"Tune for everything"** is a real engineering constraint — we expect to iterate on each assembler independently as we see what each role actually needs.

The only universal rule: **every assembler emits a `<shared_context>` block with identical content** (the immutable context object, §5.5). This is the game-of-telephone mitigation.

### 8.4 The shared immutable context object — propagated, never rewritten

Re-covered from §5.5 because it belongs here too: every LLM call at every tier receives the same immutable snapshot of:

- The narrative summary that justified this run (headline verbatim, not paraphrased)
- Geographic address(es) in scope
- Relevant emergent threads (from NL supersession chains)
- Tier definitions, biome taxonomy, domain taxonomy, faction registry
- Player profile snapshot (stub until Part 3)

**Why this matters:** in a three-tier stack, by the time a Specialist runs, the Orchestrator's intent has been paraphrased through the Coordinator. The Specialist is generating JSON from a third-hand summary — classic game-of-telephone (Cognition AI: *Don't Build Multi-Agents*). The shared immutable context is the canonical source of truth alongside every tier-specific prompt. The Specialist sees the same narrative headline the Orchestrator saw.

This is the single most important design choice across the whole system. Retrofitting it later means rewriting every prompt template.

### 8.5 Pre-compression via WMS + WNS layers

Both pipelines are context-compression pyramids:

- **WMS**: L1 events (thousands) → L2 narrations (~100) → L3-L7 summaries (tens). By the time WES reads, it's seeing a small set of pre-compressed artifacts.
- **WNS**: NL1 narrative inputs (many) → NL2 local color (some) → NL3-NL7 aggregated narrative (few).

This means **WES context assembly never walks raw events**. It reads the top of the pyramid. The bulk of the compression work already happened in layers below — and those layers were each one focused LLM call, exactly the one-input-one-output principle applied recursively.

This is also why WNS needs to *be* a parallel pipeline, not a single call. A single-call WNS would have to compress thousands of events in one prompt. A layered WNS compresses incrementally at every address level, and each layer's output is a reusable artifact multiple upstream layers can draw from.

### 8.6 NPC mention tracking — grounding without event creation

Per §4.4, NPC dialogue doesn't create canonical events. But NPC mentions *do* flow into NL1 as grounding inputs, and eventually bubble into regional narratives if they recur.

Information-flow mechanics:

1. After each NPC exchange, a **deterministic mention extractor** (no LLM call) runs over dialogue text — keyword patterns, named-entity hints, significance heuristics.
2. Extracted mentions become NL1 events with the NPC's locality address.
3. NL2 consolidators see mentions alongside WMS-derived narrations. Only mentions that recur (same entity mentioned by multiple NPCs in the same region) gain weight.
4. Single-NPC hallucinations fade via time-decay on NL1 retention.

This gives NPCs a path to seed future narrative without letting any one NPC control the narrative. The aggregation logic is the filter.

### 8.7 Distance decay (narrative address system)

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
- **Future WES localized runs** — if WES generates content tied to a specific region, the Coordinator's context should weight same-region narrative state more heavily than world-level.

Implementation: the `GeographicRegistry` already computes parent-child relationships. A `NarrativeDistanceFilter` utility class on top of it is small work; the harder piece is deciding the concrete decay curve per consumer, which is playtest-tuned.

Out of scope for WNS v1 (world-scope only). In scope when WES starts producing localized content.

### 8.8 Context poisoning — mitigations across the whole stack

A single bad LLM output anywhere in WMS or WNS can pollute downstream. Mitigations:

**Already in place (WMS):**
- Address-tag immutability ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)) — LLMs cannot invent regions.
- Content tags must exist in `tag_library.py` — new-tag pollution blocked.
- Narrations are bounded length; over-length outputs truncated.

**New in WNS (mirrored):**
- Narrative address tags (`thread:`, `arc:`, `witness:`) follow the same immutability rule.
- NL-layer LLM calls strip address tags before the call, re-attach after.
- NL layers inherit the content-tag-vocabulary rule: NL summarizers pick from a known narrative-tag taxonomy, cannot invent.

**New in WES:**
- No LLM-to-LLM direct calls, so no tier-to-tier pollution vector.
- Shared immutable context object = canonical source of truth, never rewritten.
- Every Specialist output goes through schema validation + registry cross-reference check before being staged.
- Observability: full prompt+response logs per tier per spec. "Why did this happen?" is answerable by reading the logs.

### 8.9 Where context actually comes from — concrete sources

| Source | API | Consumed by |
|---|---|---|
| `WorldMemorySystem.get_world_summary()` | facade (shipped) | WNS NL-assemblers, WES Orchestrator |
| `LayerStore.query_by_tags(layer=N, ...)` | existing | WNS NL-assemblers (WMS layer N narrations as input) |
| `WorldNarrativeSystem.get_latest_summary()` | **NEW** (§4.7) | WES Orchestrator assembler |
| `WNLayerStore.query_by_tags(layer=N, ...)` | **NEW** (§4.10, mirrors WMS) | WNS NL-assemblers (prior same-unit summaries), WES Coordinator assemblers (regional flavor) |
| `FactionSystem.stats` / `get_npc_profile()` | existing | WNS NL assemblers, WES Coordinators |
| `GeographicRegistry` | existing singleton | All (address resolution, name humanization) |
| `EntityRegistry` | existing singleton | WES Coordinators (what NPCs/enemies exist) |
| `StatTracker.get_summary()` | existing | `titles` Coordinator (unlock hints) |
| `ContentRegistry` | **NEW** (§7) | WES Orchestrator, Coordinators, Specialists (anti-orphan, diversity) |
| NPC mention log | **NEW** (§4.4, §8.6) | NL1 input source |

Everything shipped is battle-tested. Everything NEW is green-field for this phase.

### 8.10 Observability — non-negotiable

From Agent B's research: hierarchical LLM stacks are debugging nightmares. Without tracing, "why did this hostile come out as a wolf variant again?" is unanswerable.

Every LLM call in the system logs:
- Assembled prompt (system + user)
- Shared immutable context snapshot
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
  │  ├─ nl3/<timestamp>_<region>.json
  │  ├─ nl4/<timestamp>_<province>.json
  │  ├─ ...
  │  └─ nl7/<timestamp>.json
  └─ wes/                          # New
     └─ <plan_id>/
        ├─ orchestrator.json
        ├─ coord_<tool>_<step>.json
        └─ spec_<tool>_<step>_<spec>.json
```

This makes every generation event root-causeable by reading files on disk. No special UI required; grep and jq suffice. Observability tools like LangSmith or Langfuse can be layered on later if the log volume warrants.

---

## 9. Open Questions & Decisions Needed

> **Revision note (2026-04-20, v2):** Several questions from v1 were resolved by user feedback. Resolved items kept as "[RESOLVED]" with the decision for traceability; active questions re-numbered. New questions raised by the restructure are appended.

### Active questions

#### Q1. NL layer trigger configuration

**Problem**: WNS is a parallel WMS pipeline with 7 layers. Each layer needs a `should_run()` trigger: interval-based for NL2 (mirrors WMS L3's 15-event interval), weighted buckets per aggregation unit for NL3+. The concrete thresholds are open.

**Options**:
- **A**: Copy WMS thresholds exactly (interval=15, weighted=50 at NL3, escalating to 200 at NL7). Pro: consistent. Con: WMS thresholds were tuned for factual aggregation, not narrative pacing.
- **B**: Start with WMS values × 2 for all NL layers (narrative is "slower" than facts). Measure in playtest.
- **C**: Hybrid — copy for NL2-NL5, double for NL6-NL7 (where narrative pacing matters most to player experience).

**Lean**: B. Easier to tune down than up — over-production is worse than under-production for narrative coherence.

#### Q2. NL2 template or LLM?

**Problem**: WMS L2 evaluators are template-based (template narrations, no LLM). Does NL2 follow that, or does NL2 need LLM voice because "narratives need narrative voice"?

**Options**:
- **A**: Template at NL2 (mirror WMS). Narratives start sounding "real" at NL3+. Pro: cheap, deterministic, fast. Con: NL3+ gets flat inputs.
- **B**: LLM at NL2 — every locality narration is a focused LLM call. Pro: narrative voice from the ground up. Con: high-volume local LLM calls (thousands per session), even on Ollama this is heavy.
- **C**: Hybrid — NL2 is template by default but upgrades to LLM when a locality has crossed a "significance" floor (enough going on that voice matters).

**Lean**: C. Default template keeps volume manageable; LLM voice kicks in only for places the player actually spends time.

#### Q3. BalanceValidator — stub, build, or skip?

**Problem**: Same as v1. CLAUDE.md flags BalanceValidator as designed-not-built. WES Specialist outputs need balance checking.

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

**Lean**: B. Avoids touching sacred directories; cleaner save/load; registry is already the authority for cross-references. Writing JSON files adds latency and file churn for no benefit.

#### Q5. Narrative tag taxonomy — new file or extension of existing?

**Problem**: WMS enforces content-tag membership via `tag_library.py` / `tag-definitions.JSON`. WNS needs its own narrative-content tag vocabulary (arc stages, tone descriptors, thread-lineage tags). Where does it live?

**Options**:
- **A**: Extend `tag-definitions.JSON` with a new namespace (`narrative:*` prefix).
- **B**: New sibling file `narrative-tag-definitions.JSON` loaded by an extended `TagLibrary`.
- **C**: Inline in each `narrative_fragments_nl*.json` (no central taxonomy).

**Lean**: B. Keeps narrative tag evolution independent of game-content tag evolution. Both get loaded by the same `TagLibrary` singleton via a minor extension.

#### Q6. SQLite database — shared with WMS or separate?

**Problem**: WNS needs tables for NL1-NL7 events + tag junctions. Co-locate in the WMS SQLite file (`world_memory.db`) or separate (`world_narrative.db`)?

**Options**:
- **A**: Shared database. Pro: atomic save/load, single connection, easy cross-table queries. Con: file grows.
- **B**: Separate database. Pro: clean separation, independent evolution. Con: save/load atomicity requires coordination.

**Lean**: A. The save system already handles the WMS SQLite file. Adding narrative tables to it is zero extra save/load work.

#### Q7. Shared context object — snapshot or live?

**Problem**: The shared immutable context object propagates through every tier (§5.5). If a WES plan runs for several minutes and world state shifts mid-run, should a later Specialist call see the frozen snapshot or a refreshed one?

**Options**:
- **A**: Snapshotted at plan start, immutable for the whole plan. Pro: coherence. Con: stale if the world moved.
- **B**: Refreshed before each tier transition. Pro: current. Con: game-of-telephone risk partially returns.
- **C**: Snapshot for intent invariants (narrative, thread IDs); refresh for fact invariants (registry counts).

**Lean**: A. The plan was justified by a specific NL7 summary; executing it against a newer summary risks incoherence. If the world shifts significantly mid-run, the next NL7 fire will produce a new plan.

#### Q8. Player Intelligence (Part 3) — dependency or defer?

Same as v1. Part 3 (player profile) isn't built. WNS/WES would benefit.

**Lean**: B — ship WNS/WES with a no-op profile slot in the shared context; fill it when Part 3 arrives.

#### Q9. When do Specialists run in parallel?

**Problem**: §6.7 notes parallelism is deferred. Real question: when should the Coordinator declare "these specs are independent" vs. "I need to see each output before emitting the next"?

**Options**:
- **A**: Always sequential in v1.
- **B**: Parallel when Coordinator flags `independent=true` on a batch.
- **C**: Auto-parallelize any spec that doesn't reference a prior spec's output.

**Lean**: A in v1, B in v2. C requires static analysis of spec references — more infrastructure than we want to build early.

#### Q10. Narrative thread retention — how long before dormant beats get pruned?

**Problem**: Threads emerge via supersession chains (§4.5). Old threads whose pattern stops recurring will stop being "touched." When do they prune from active context?

**Options**:
- **A**: Time-based — thread is dormant if not touched for N game-days, pruned after M days.
- **B**: Count-based — thread needs at least K mentions per N summaries to stay active.
- **C**: Never prune — dormant threads stay queryable forever (save file grows).

**Lean**: A. Simple, predictable. Defaults to something like 30 game-days dormant / 180 game-days pruned; tune in playtest.

---

### Resolved (decision captured, no longer blocking)

- **[RESOLVED] Backend selection per LLM call** — Cloud (Claude) only for WES Orchestrator and possibly WNS NL7. Everything else local (Ollama). Routing via `backend-config.json` task types; no per-call overrides in v1.
- **[RESOLVED] Unified async runner** — Yes. Build `AsyncLLMRunner` for WES; migrate NPC dialogue to it; leave `llm_item_generator` alone until it needs touching.
- **[RESOLVED] Thread detection seeded vs. emergent** — Emergent, via supersession chains in WNS layers. No explicit `NarrativeThread` schema in v1. Retrospective thread detector can be a dev tool.
- **[RESOLVED] Rollback semantics** — Hard rollback (all-or-nothing per plan) in v1. Soft rollback / partial commit is a future optimization.
- **[RESOLVED] LLM verifier / evaluator** — None. Verification is deterministic code (schema + cross-ref + balance stub) plus observability logging. Per user: *"a robust architecture with some smart detection and calls is enough."*
- **[RESOLVED] WES → WNS clarification loop** — Dropped. Narrative leads, execution serves. If a WNS summary is under-specified for execution, Orchestrator abandons. The next NL7 fire produces a new summary.
- **[RESOLVED] Universal ContextEnvelope with fixed tier ratios** — Dropped. Per-LLM-role assemblers with individual tuning. Only universal element: the shared immutable context block.

---

## 10. Phased Implementation Roadmap

> **Revision note (2026-04-20, v2):** v1 roadmap assumed WNS was a single LLM call. **Replaced.** WNS is now a parallel 7-layer pipeline; the roadmap reflects that scope. Tools are Coordinator+Specialist pairs. Thread schema phase is dropped (threads are emergent). Self-critique phase is dropped (no LLM verifier per §9.RESOLVED). New observability phase added (per Agent B research).

Each phase produces a shippable increment. No phase requires the next phase to provide value. Estimated effort is engineering-time, not calendar-time. The total scope is larger than v1 — WNS alone is most of P1+P2, not a one-phase item.

### P0 — Shared Infrastructure

Plumbing. Every later phase needs it.

- **P0.1** `AsyncLLMRunner` — unified background-thread executor with dependency-ordered step execution. Extract from `llm_item_generator.generate_async` into `world_system/living_world/async_runner.py`.
- **P0.2** `WESSharedContext` dataclass + builder (§5.5). Frozen snapshot pattern.
- **P0.3** `ContextAssemblerBase` — framework class for per-LLM-role assemblers (§8.3). No universal ratios; subclasses own their logic. Shared concern: the `<shared_context>` block gets formatted identically everywhere.
- **P0.4** NPC dialogue async migration — move synchronous `_generate_npc_opening` onto the new runner. Acceptance test for P0.1.
- **P0.5** L7 subscription hook — `Layer7Manager.register_world_summary_callback()` for WMS→WNS notification.

Exit criteria: NPC dialogue no longer blocks the UI; ≥5 new passing tests covering the runner + shared context + assembler base.

---

### P1 — WNS Foundation (NL1, NL2, NL3)

The bottom of the narrative pipeline. NL1 ingestion, NL2 template consolidation, NL3 first real LLM narrations.

- **P1.1** Narrative tag taxonomy — new `narrative-tag-definitions.JSON` + extended `TagLibrary`. Includes narrative address prefixes (`thread:`, `arc:`, `witness:`) appended to `ADDRESS_TAG_PREFIXES`.
- **P1.2** NL layer storage — SQLite tables `nl1_events` through `nl7_events` + tag junctions. Co-located in the WMS database (per §9.Q6).
- **P1.3** NL1 ingestion pipeline:
  - Subscribe to WMS L2 events tagged "narratively interesting"
  - Subscribe to player milestone events
  - Deterministic NPC-mention extractor (no LLM) ingests dialogue output
- **P1.4** NL2 template consolidator — mirrors WMS L2 pattern (template-only). Interval-based trigger (start with 15 NL1 events per locality).
- **P1.5** NL3 LLM consolidator — first narrative LLM call. Prompt fragments in `narrative_fragments_nl3.json`. BackendManager task: `"wns_layer3"`. Template fallback mandatory.
- **P1.6** `NLTriggerManager` — parallel to `TriggerManager`. Weighted buckets per aggregation unit.

Exit criteria: a play session produces at least one valid NL3 narrative for an active region. NL1/NL2 fill up observably. Template fallback works when Ollama is offline.

---

### P2 — WNS Upper Layers (NL4-NL7) + WorldNarrativeSummary

The rest of the narrative pipeline up to the world-level artifact WES consumes.

- **P2.1** NL4 summarizer — weighted bucket per province, LLM call, address-tag partitioning. `narrative_fragments_nl4.json`.
- **P2.2** NL5 summarizer — weighted bucket per region-band. `narrative_fragments_nl5.json`.
- **P2.3** NL6 summarizer — weighted bucket per nation. `narrative_fragments_nl6.json`.
- **P2.4** NL7 summarizer — single world bucket, world narrative summary output. `narrative_fragments_nl7.json`. Supersession logic (mirrors `_find_supersedable` from WMS L7).
- **P2.5** `WorldNarrativeSummary` event schema (§4.7).
- **P2.6** Publish `WORLD_NARRATIVE_SUMMARY_UPDATED` on GameEventBus when NL7 fires.
- **P2.7** `WorldNarrativeSystem` facade (mirror of `WorldMemorySystem`) with `get_latest_summary()` for consumers.
- **P2.8** Minimal dev UI — F-key overlay showing the latest NL7 summary. Sanity check.

Exit criteria: L7 fires → NL pipeline responds → eventually NL7 fires → a new `WorldNarrativeSummary` appears in dev UI, reads plausibly, and is queryable by API.

---

### P3 — Content Registry

Coordination layer for generated content. No generators yet.

- **P3.1** Registry SQLite tables (§7.2): per-tool tables + unified `content_xref`.
- **P3.2** Registry API: `stage_content`, `commit`, `rollback`, `list_live`, `list_staged_by_plan`, `find_orphans`.
- **P3.3** Integration with existing databases — `MaterialDatabase`, `EnemyDatabase`, etc. learn to union JSON-loaded content with registry-live content (option B from §Q4).
- **P3.4** Save/load wiring — registry state persists atomically with the rest of the save.

Exit criteria: can manually stage a fake material, commit it, see it in `MaterialDatabase.get_instance().materials`, roll back via API.

---

### P4 — WES Deterministic Shell (no LLM)

The whole WES pipeline except the LLM calls. Proves the plumbing before any prompt tuning.

- **P4.1** `WESPlanStep` + `WESPlan` dataclasses (§5.2).
- **P4.2** `SpecialistSpec` dataclass (§5.3).
- **P4.3** Topological plan dispatcher — deterministic code that walks a plan and invokes tiers in order.
- **P4.4** Staging + atomic commit/rollback flow.
- **P4.5** Final verification pipeline (§5.7): orphan scan, duplicate scan, completeness.
- **P4.6** Observability scaffolding — `llm_debug_logs/wes/<plan_id>/` directory structure, per-tier logging.
- **P4.7** Stub Orchestrator + stub Coordinator + stub Specialist — produce hardcoded plans/specs/JSONs for test runs. No LLM calls yet.

Exit criteria: a hardcoded stub plan with 2-3 stub tool steps runs end-to-end, stages content, commits, and the content is live in the relevant databases. Rollback also works.

---

### P5 — WES Orchestrator (Tier 1 LLM)

Replace the stub Orchestrator with a real LLM call.

- **P5.1** `WESOrchestratorAssembler` — per-LLM-role context assembler.
- **P5.2** Orchestrator LLM integration — `BackendManager.generate(task="wes_orchestrator")`. Cloud backend (Claude) preferred; Ollama fallback for offline/dev.
- **P5.3** Prompt fragments: `prompt_fragments_wes_orchestrator.json`.
- **P5.4** Subscribe to `WORLD_NARRATIVE_SUMMARY_UPDATED`. On trigger, queue a plan-generation job.
- **P5.5** Orchestrator template fallback — a deterministic plan generator from the summary's tags for when the backend is unavailable. Produces valid but flat plans.

Exit criteria: NL7 fires → Orchestrator runs → produces a valid (but still stub-executed) plan → stub tiers complete it → content appears. Plans are coherent with the summary they came from.

---

### P6 — First Tool Mini-Stack: `materials`

End-to-end LLM generation for one tool type. Proves the Coordinator+Specialist pattern.

- **P6.1** `MaterialsCoordinator` — Tier 2 LLM call producing `SpecialistSpec` list. Prompt fragments: `prompt_fragments_coord_materials.json`.
- **P6.2** `MaterialsSpecialist` — Tier 3 LLM call producing JSON material. Prompt fragments: `prompt_fragments_spec_materials.json`. Structured output via Ollama grammar if available.
- **P6.3** BalanceValidator stub (§9.Q3) — tier multiplier range check.
- **P6.4** Dev CLI `debug_create_material(plan_step)` — bypass Orchestrator, test Coordinator+Specialist in isolation.
- **P6.5** Both template fallbacks — Coordinator and Specialist each have deterministic versions.

Exit criteria: Orchestrator plan → materials mini-stack → valid staged material → commit → gathering the relevant node yields the new material. Real end-to-end play.

---

### P7 — Tool Expansion

Remaining 4 tools. Each follows the P6 pattern.

- **P7.1** `nodes` Coordinator+Specialist — cross-ref to materials. Proves the cross-reference path.
- **P7.2** `skills` Coordinator+Specialist — compose from existing tags only (no tag invention).
- **P7.3** `titles` Coordinator+Specialist — cross-ref to StatTracker stats + skills.
- **P7.4** `hostiles` Coordinator+Specialist — capstone; cross-refs to materials (drops), skills (enemy skills), biomes, factions.

Exit criteria per tool: single-tool plans produce schema-valid, cross-ref-clean content. Full test: 4-step plan with all 4 new tools runs end-to-end.

---

### P8 — Multi-Step Plans + Metrics

Unlock the Orchestrator to produce multi-tool plans.

- **P8.1** Orchestrator prompt updated to allow multi-step plans.
- **P8.2** Topological dependency execution stress-tested (plans with 5+ steps, 2+ tools).
- **P8.3** Cross-plan diversity — Orchestrator sees recent `CONTENT_GENERATED` history and avoids repetition.
- **P8.4** Metrics dashboard — beats/hour, tool success %, orphan count, tier usage by backend.

Exit criteria: 10-minute play session produces ≥1 multi-tool plan that commits successfully; metrics dashboard shows non-zero values across all tracked dimensions.

---

### P9 — Observability + Emergent Thread Detection

Make the system debuggable and expose its emergent behavior.

- **P9.1** Retrospective thread detector — offline tool that clusters NL supersession chains into named threads.
- **P9.2** Thread dev UI — view active and dormant threads, trace beat→content chains.
- **P9.3** Per-tier latency + cost reports.
- **P9.4** "Why this output?" tracer — given a generated content_id, walk backwards through the logs to show the NL7 summary, the Orchestrator plan, the Coordinator specs, and the Specialist prompt that produced it.

Exit criteria: a developer can pick any generated item in-game and get the full provenance chain from logs alone. Emergent threads are visible in the dev UI.

---

### Deferred — Explicit Scope Exclusions

Per user direction. Re-open when P0-P9 are proven:

- **Quest generation** (§6.3.6) — needs Content Registry + ≥3 active tools to have enough material to reference.
- **Ecosystem integration** — `EcosystemAgent` exists as a query tool; extend WES Coordinators to consult `get_scarcity_report()` when planning `materials`/`nodes` generation.
- **Player Intelligence (Part 3)** — `player_profile` slot in `WESSharedContext` stays stubbed until Part 3 lands.
- **Distance-decayed context for localized content** — §8.7. Only needed when WES produces sub-regional content.
- **NL2 LLM upgrade** — §9.Q2 option C. Template at NL2 by default; upgrade to LLM only when a locality crosses a significance floor.
- **Parallel Specialist execution** — §6.7. Sequential in v1.
- **Developer injection tool** — CLI for seeding NL7 summaries, bypassing the pipeline. Useful for playtest, not critical path.
- **Replacing `llm_item_generator` with AsyncLLMRunner** — leave alone until it needs touching.

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

