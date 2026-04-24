# World System Working Document

**Status**: Active planning — Living World architecture (**v4 — feedback lock applied, implementation authorized**)
**Created**: 2026-04-20
**Last Updated**: 2026-04-22 (v4 — after third round of designer feedback, now locked)
**Owner**: Development
**Supersedes as planning doc**: `Development-Plan/WORLD_SYSTEM_SCRATCHPAD.md` (2026-03-14). The scratchpad is retained for its research citations only; its "Tier 1/2/3" framing is retired in favor of the WNS/WES vocabulary below.

> **⚠️ RESUMPTION PROTOCOL — READ FIRST.** v4 is the designer's locked spec. Three rounds of structured feedback shaped it (v1→v2→v3→v4). The v4 revision applies the 2026-04-22 *World System v3 — Designer Feedback Lock* document; that lock is now closed. Implementation is authorized; P0 work begins immediately after v4 commits.
>
> Substantive v4 load-bearing changes (read these first when resuming):
> 1. **Live queries replaced by WNS-authored context bundles** (§2, §5, §8). Downstream consumers never query live — WNS pre-assembles everything WES needs.
> 2. **WNS fires at every layer NL1-NL7** on an every-N-events-per-layer-per-address cadence; NL7 is *not* the sole WES trigger (§3, §4). WNS decides when to call WES.
> 3. **NL1 = pre-generated NPC dialogue captured as narrative events** (§4, CC6). NPC interactions are bounded (greeting → accept → turn-in → closing), not live conversation.
> 4. **Supervisor LLM added** (§2, §5, CC1). Common-sense checker over all WES I/O. Rerun-only authority.
> 5. **Hubs are dispatchers, not orchestrators** (§5, §6, CC9). Batch XML fan-out in one pass; no sequential feedback loop; parallelism within a plan step by default.
> 6. **WNS/WMS are sibling systems**, fully separate SQLite DBs, separate tag taxonomies, separate prompt fragment files (CC5, §9.Q5/Q6).
> 7. **Pseudo-mock infrastructure is P0 plumbing** — every LLM role gets a fixture code + canonical mock I/O pair (CC4, §10.P0).

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
- **v3** (2026-04-21) — second restructure after user feedback. WNS reframed via string-thread-embroidery metaphor; 6-layer starting shape; every WMS/WNS layer LLM-driven; shared immutable context deleted in favor of live queries; tier names → `execution_planner` / `execution_hub_<tool>` / `executor_tool_<tool>`; threads retained forever.
- **v4** (2026-04-22) — third restructure after designer feedback lock. Major inversions from v3:
  - **Live queries deleted.** The v3 premise that "each LLM queries canonical stores live at its own call time" is reversed. Live querying is too expensive in cognitive load for small local models. Context is **pre-assembled by WNS** into a typed **context bundle** (§2.4, §8) and handed down to WES. The WNS itself still reads canonical stores as it weaves — but downstream consumers (WES planner, hubs, executor_tools) never do.
  - **Supervisor LLM added.** v3's resolved item "No LLM verifier" is reopened. A supervisor LLM observes all WES inputs and outputs as a common-sense checker, with a single authority: trigger a WES rerun with adjusted instructions. Not a balance/schema/cross-ref validator — those remain deterministic code. (§2, §5, CC1.)
  - **WNS fires at every layer, not only NL7.** v3 said WES subscribes to NL6/NL7 world-narrative summaries. v4 says **WNS fires every layer NL1-NL7 on every-N-events-per-layer-per-address cadence**, and **WNS** — not L7, not auto-subscription — decides when to call WES. Scope of a firing (what WES can touch) lives in the planner prompt, not an architectural permissions matrix. (§3, §4, §5, CC7, CC8.)
  - **NL1 = pre-generated NPC dialogue.** v3 had NL1 as capture-only ingestion of WMS events + NPC mentions + player milestones. v4 narrows NL1 to **pre-generated NPC dialogue** captured at speech-bank generation time. Player milestones enter via WMS events; mention extraction runs once per speech-bank, not per player interaction. Live conversation is a future capability — NPC interactions are bounded (greeting → accept → turn-in → closing). (§1, §4, CC6.)
  - **WNS layer count fixed at NL1-NL7.** v3 had 6 starting ("maybe add NL7 later"). v4 commits to 7 with NL1 as its own stored layer (pre-generated dialogue).
  - **Threads first-class at every weaving layer, not just NL2.** v3 made threads the explicit output of NL2. v4 generalizes: threads are the output of the weaving operation, which happens at every LLM layer.
  - **Hubs non-adaptive.** v3's `execution_hub_<tool>` had `adapt_after_output` for sequential feedback between executor_tool calls. v4 removes it. **Hubs batch all executor_tool calls into XML-tagged fan-out in a single pass.** Executor_tools within a plan step parallelize by default. (§5, §6, §9.Q9, CC9.)
  - **WNS is the orchestrator between narrative and execution.** Not a stylistic framing — a structural commitment. WNS assembles the bundle, authors the directive, decides when to fire. WES is a pure execution engine. (§4, §5, CC8.)
  - **Ecosystem dropped** from active scope. v3 listed ecosystem as a deferred tool. v4 removes it from the tool set entirely; it may later re-appear as a WNS-side context source, if at all.
  - **All five tools are unbuilt.** v3 implied a distinction between shippable tools (hostiles/materials/nodes/skills/titles) and deferred (quests). v4 notes none are built; quests are the most narratively central of the six, but the others are not shipped either.
  - **NPC dialogue model committed.** v3's "async is a P0 item" is preserved, but the underlying model is now "pre-generated, bounded interaction cycle." Live conversation deferred.
  - **Graceful-degrade discipline tightened.** v3 described silent try/except fallback. v4 requires every graceful-degrade event to emit a structured debug log, and **WES failures must additionally surface visibly on-screen** — not just log. No crashes anywhere. (CC3.)
  - **Pseudo-mock infrastructure promoted to P0.** Every LLM role gets a fixture code + canonical sample I/O, so the full pipeline is end-to-end testable without touching a real LLM. (CC4, §10.P0.)
  - **WNS and WMS are sibling systems, fully separate.** Separate SQLite DBs, separate tag taxonomies, separate prompt fragment files. v3 had "shared SQLite, shared tag library extension." (CC5, §9.Q5, §9.Q6.)
  - **Q4 resolved as "both"**: generated content is registry-resident AND written to generated JSON files on commit (so existing databases reload cleanly). (§7, §9.Q4.)
  - **Three trigger modes removed**: session-boot catch-up, developer injection, WES self-request. All dropped. Game continues on load as if nothing happened; dev injection is a future feature; WES self-request violates unidirectional flow. (§3.)
  - **Distance decay day-one**, not v2 follow-up. Low-tier WES firings are day-one scope and need the WNS bundle to already apply distance-decay. (§8.)
  - **Phase order demoted to mental model.** Single-pass AI-driven implementation is likely; the phase sequence is useful for dependency reasoning but not a shipping schedule. (§10.)

## Table of Contents

1. [Current Shipped State (Grounding)](#1-current-shipped-state-grounding)
2. [System Architecture: WMS → WNS → WES → Tools → Game (unidirectional, bundle-mediated)](#2-system-architecture)
3. [Trigger Signal Chain (WNS fires every layer NL1-NL7; WNS calls WES)](#3-trigger-signal-chain)
4. [WNS Design — Sibling of WMS, NL1-NL7, Pre-Generated NPC Dialogue at NL1](#4-wns-design)
5. [WES Loop — Three-Tier Stack + Supervisor (Planner → Hub → Tool, Supervisor cross-tier)](#5-wes-loop)
6. [Tool Architecture (5 Hub+Tool Mini-Stacks, XML batch dispatch)](#6-tool-architecture)
7. [Content Registry (Anti-Orphan Cross-Reference, Registry + Generated JSONs)](#7-content-registry)
8. [Information / Context Flow — The Hard Problem (WNS pre-assembles; WES consumes bundle)](#8-information-flow--the-hard-problem)
9. [Open Questions & Decisions Needed (v4: Q10-Q12 new; Q1/3/4/5/6/8/9 resolved)](#9-open-questions--decisions-needed)
10. [Phased Implementation Roadmap (P0-P9, v4 expanded)](#10-phased-implementation-roadmap)
11. [Appendix: Cross-Cutting Decisions (CC1-CC9)](#appendix-cross-cutting-decisions-cc1-cc9)
12. [Appendix: Items Still Outstanding (Non-Blocking)](#appendix-items-still-outstanding-non-blocking)
13. [Appendix: References to Existing Code](#appendix-references-to-existing-code)

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

On failure of the Living World consumers, `self.npc_agent_system = None` and dialogue degrades to hardcoded lines. This graceful-degrade pattern is the template WES components should follow — **tightened in v4**: every graceful-degrade event (LLM backend down, layer skipped, consumer init failed) must emit a structured entry to the debug log (§8.11). Silent try/except is no longer acceptable. WES failures additionally surface visibly on-screen — not a crash, but an unmissable UI indicator so players and developers both see when content generation fell over. See **CC3 Graceful-degrade discipline** at the end of this doc for the full invariant.

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

> **v4 note on dialogue model.** The canonical NPC dialogue model for WNS purposes is **pre-generated, not live**. Each NPC has a speech-bank generated once per content-update window and stored. Player interactions are bounded: **greeting → accept quest → turn-in → closing line.** Mention extraction (§4, §8.7) runs at speech-bank generation time, not on player interaction. The synchronous-live-dialogue caveat above still matters (the blocking call should still move off-thread), but the underlying architectural commitment is pre-generation. Live conversation is a deferred future capability. See **CC6** at the end of this doc.

### 1.4 What is NOT yet done

- **Quest generation** — deferred per designer. Five tool types (hostiles, materials, nodes, skills, titles) come first; quests after.
- **Ecosystem integration** — **dropped from active tool scope in v4.** `EcosystemAgent` still exists as a stateless query helper but is not a WES tool. It may later re-appear as a WNS-side context source; low priority either way.
- **L7 WorldSummaryEvent consumer** — L7 fires and stores today, but **no subscriber reads it**. This is one of many WMS feeds WNS will subscribe to — but in v4, WNS reads WMS at every layer, not only at L7 (§3).
- **Async LLM path** — both NPC dialogue and all future WES/WNS calls currently block the main thread. Async runner is P0.
- **LLM fixture registry** — every LLM role needs a standard code + canonical mock I/O so the full pipeline is pseudo-mockable end-to-end. **P0 infrastructure in v4** (CC4, §10.P0).
- **Structured graceful-degrade logs** — debug logs today are ad-hoc. v4 tightens this into a contract (CC3, §8.11, §10.P0).
- **On-screen WES failure surfacing** — no UI affordance exists today. v4 requires one (CC3, §10.P0).

---

## 2. System Architecture

> **Revision notes across versions.**
> - **v2:** Corrected WNS↔WES from bidirectional to unidirectional. Narrative leads execution; execution loops back through game events → WMS, not through direct backward calls.
> - **v3:** Three-tier WES stack formalized; shared immutable context deleted in favor of live queries.
> - **v4:** **Live queries reversed.** Context is pre-assembled by WNS into a typed context bundle; downstream WES tiers never query live. **Supervisor LLM added** (CC1) as the correction mechanism that compensates for the loss of live re-reads. **WNS is the orchestrator** (CC8) — it decides when to call WES, authors the bundle, and embeds the directive.

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
│  Sibling system to WMS (separate SQLite, separate tag taxonomy). │
│  Layers NL1-NL7: NL1 = pre-generated NPC dialogue captured;      │
│  NL2-NL7 = weaving at increasing address scope.                  │
│  WNS decides when a narrative warrants calling WES, and          │
│  assembles the context bundle (delta + narrative + directive).   │
│  Each layer = one focused LLM call. Sibling of WMS, not a mirror.│
└────────────────┬─────────────────────────────────────────────────┘
                 │ CONTEXT BUNDLE (delta + narrative + directive)
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
| **Role** | Produces narrative state AND **orchestrates execution** (CC8). Decides when to fire WES and what bundle to hand it. | Pure execution engine. Runs what WNS tells it to. |
| **Input** | Pre-generated NPC dialogue (NL1), WMS layer outputs, faction state, entity/geographic registry | Context bundle (delta + narrative + directive) authored by WNS |
| **Output** | Narrative events at layers NL1-NL7; threads; **context bundles handed to WES** | Staged content across 5 tool types (quests deferred) |
| **LLM style** | Flat per layer (each narrative layer = one focused call). NL1 = deterministic capture, no LLM. | Layered — three tiers: planner → hub → executor_tool, plus a cross-tier supervisor |
| **Queries live?** | Yes, when authoring bundles — reads WMS, registries, faction state, NPC mention logs. | **No.** Consumes only the bundle WNS handed it. |
| **Writes to game?** | No. Reads game, records narrative. | Yes. Writes registered content. |
| **Talks to the other?** | No direct call. Talks to WES via bundle. | No direct call back. |

### 2.3 Why this isn't a clean handoff (but also isn't a sync loop)

The user's earlier statement — "they feed into each other" — describes the **macro loop**, not direct coupling:

1. WMS observes gameplay and produces world state.
2. WNS reads WMS and produces narrative state.
3. WES reads WNS and produces new content.
4. The content enters gameplay; gameplay produces events.
5. Events flow to WMS. Go to step 1.

The loop closes through the game. WES does not call WNS. WNS does not read WES output. Each subsystem reads the output of the one above it and writes its own artifact. **This is a compound AI system (Berkeley BAIR terminology) with a hierarchical topology, not an agent dialogue.**

**One important refinement in v4**: the unidirectional arrow from WNS to WES is **mediated by a context bundle**, not by direct tier-reads of a shared narrative store. WNS *is* the orchestrator between narrative and execution (CC8); it decides when a narrative warrants execution, and hands WES exactly the context it needs in one typed artifact.

### 2.4 Pre-assembled context bundle (replaces live queries)

> **Revision note (v4):** v3 had each WES tier query canonical stores live at its own call time. **That's reversed in v4.** Live querying is too cognitively expensive for small local LLMs — the working set explodes, relevance ranking degrades, and coherence drops. Instead, **WNS pre-assembles a typed context bundle** and hands it down to WES. Each tier reads only what code hands it; nothing below the planner ever performs a live query.

One principle cuts across every LLM call in the system: **each call takes one focused input, produces one output, and that output becomes a reusable artifact stored in a canonical store.** LLMs are treated as composable transforms, not agents. Later calls read from pre-assembled inputs, not from live stores.

The canonical artifacts:

- WMS layer outputs → SQLite rows queryable via `WorldQuery` / `LayerStore` (shipped). **Read by WNS, not by WES.**
- WNS layer outputs → SQLite rows in a *separate* SQLite DB from WMS (v4 change: WNS/WMS are sibling systems — CC5). Read by higher WNS layers for weaving; not read by WES.
- Game state (registries, taxonomies, faction state, etc.) → queried via existing singletons. **Read by WNS when authoring the bundle, not by WES directly.**

**The context bundle (authored by WNS) has three parts** — see §8 for the full shape:

1. **Delta** — dialogue + WMS events between WNS's last firing at this layer/address and now, address-tagged.
2. **Narrative context** — current narrative state at the firing's layer, plus parent addresses, bottom-up shallow-going-outward.
3. **Directive** — WNS's high-level instructions on what WES should create. For WES bundles only.

**Two tiny blocks still travel on every LLM prompt regardless of bundle:**

1. **Game awareness** — the game's canonical rules: tier multipliers (T1-T4), biome taxonomy, domain taxonomy, stat names, canonical tag prefixes, `ADDRESS_TAG_PREFIXES`. Static per-session, loaded from JSON at boot.
2. **Task awareness** — what this specific LLM is being asked to produce: its role, its output schema, its single input.

**Why game-of-telephone still doesn't apply**: telephone is a problem when each tier *paraphrases* the tier above. Here, the bundle is **data**, not prose. Code assembles it once; each tier reads exactly the fields it needs. No tier re-summarizes; everyone sees the same structured bundle.

**The tradeoff of pre-assembly vs. live queries**: pre-assembly means the world may have shifted between bundle assembly and the executor_tool call, and downstream tiers won't see the shift. The supervisor LLM (§5, CC1) is the compensating mechanism: if something obvious is wrong (a frost-themed directive produced a volcanic hostile because of stale bundle state or an upstream hallucination), supervisor flags it and triggers a WES rerun with adjusted instructions. Plus: WNS fires frequently enough (every layer, every few events per address — §3) that bundle staleness is small on the horizon of any single plan.

### 2.5 Supervisor LLM (new in v4)

> **Revision note (v4):** v2 and v3 resolved that no LLM verifier would exist; code owns verification. **Partially reopened.** Deterministic code still owns schema validation, cross-reference checks, balance-range checks, and address-tag immutability. But the move to pre-assembled bundles means downstream tiers lose the live-query safety net. The supervisor LLM fills that gap as a **common-sense checker**, not an expert validator.

**Scope:**

- Observes all WES inputs and outputs across tiers (planner input bundle + plan; hub spec-batches + executor_tool outputs).
- Asks one question of every pass-through: "does this make sense given the directive and the content?"
- Example failure to catch: "directive says 'frost-themed village unrest'; tool produced a volcanic hostile." No code check catches that; no schema rule flags it. The supervisor does.

**Authority:**

- **Rerun only.** Supervisor can trigger a WES rerun with adjusted instructions prepended to the next planner call. That's its single lever.
- **No direct state mutation.** Cannot edit bundles, edit plans, mutate registry rows, or mark plans abandoned. Deterministic code still owns rollback.
- **No schema/balance/cross-ref authority.** Those remain code-level invariants.

**Observability coupling:**

- Supervisor consumes the same per-tier logs all other WES LLMs write (§8.11). No separate observability pipeline.
- Its rerun decisions are themselves logged (reason, adjusted-instruction delta, outcome of the rerun).
- Rerun budget is TBD — capped low (likely 1-2 reruns per plan before hard abandonment).

**Integration timing:** supervisor must exist before any tool ships. If not wired during P6 (execution_planner bring-up), it must land at P6.5 before P7's first tool mini-stack. See **CC1** for the full invariant and §10 for the schedule.

### 2.6 Live queries over stored narrative interpretations (historical — v3, superseded)

*v3 described a "live queries" model. Retained here only as historical context; §2.4 above is the v4 replacement.*

### 2.7 LLM Roster

Naming every LLM in the system, with its tier, backend preference, and call shape. "LLM" alone is too coarse — each role has different quality/latency/cost requirements. **Every role also gets a fixture code and canonical mock I/O** (CC4, §10.P0) so the full pipeline can be pseudo-mocked end-to-end.

| LLM role | Layer | Backend (preferred) | Call shape | Frequency |
|---|---|---|---|---|
| WMS L3 consolidator | WMS internal | Local (Ollama) | 1 call per district per interval | Moderate |
| WMS L4/L5/L6 summarizer | WMS internal | Local | 1 call per aggregation unit on weighted fire | Low |
| WMS L7 summarizer | WMS internal | Local | 1 call when world bucket fires | Very low |
| **WNS NL2 weaver** (district/locality) | WNS | Local | 1 call per every-N NL1 per address | Moderate |
| **WNS NL3-NL5 weavers** (regional/national/cross-scale) | WNS | Local | 1 call per every-N events per layer per address | Low |
| **WNS NL6 weaver** (nation-to-world bridge) | WNS | Local (Cloud tolerated) | 1 call per world-scale bucket fire | Very low |
| **WNS NL7 embroiderer** (world) | WNS | Local (Cloud tolerated) | 1 call per world bucket fire | Very low |
| **WES `execution_planner`** | WES Tier 1 | Cloud-tolerated | 1 call per WNS-driven firing | Low |
| **WES `execution_hub_<tool>`** | WES Tier 2 | Local | 1 call per plan step (fan-out in one pass — CC9) | Moderate |
| **WES `executor_tool_<tool>`** | WES Tier 3 | Local | N calls per plan step, parallelizable | High |
| **WES `supervisor`** (new in v4) | WES (cross-tier) | Local (Cloud tolerated) | 1 call per WES pass, consumes all tier logs | Low |
| NPC dialogue (speech-bank generator) | Existing (NPCAgentSystem) | Local | 1 per NPC per content-update window | Very low |

**Cloud minimization rule:** cloud APIs (Claude) are *tolerated* only for the WES `execution_planner`, optionally for the WNS top layer, and optionally for the supervisor on escalated reruns. Everything else runs locally. These calls don't need to be fast — they represent slow-moving world state, not per-frame reactions. Per user: *"Ideally none"* — cloud is the fallback, not the default.

**Layered vs flat:**
- **Flat LLM** = single focused call, no LLM-to-LLM dispatch. WMS layers, WNS layers, NPC dialogue.
- **Layered LLM** = an LLM whose job is to orchestrate other LLMs. Only WES has this shape. Its three tiers are `execution_planner` → `execution_hub_<tool>` → `executor_tool_<tool>`. Each tier is deterministically invoked by code between tiers — LLMs never call LLMs directly.

### 2.8 Vocabulary this doc uses (and the published equivalents)

Grounding terminology in the published literature so future contributors can search:

| This doc | Published equivalent | Source |
|---|---|---|
| Compound AI system | Compound AI systems | Berkeley BAIR 2024 |
| WES as "orchestrator-workers" | Orchestrator-Workers pattern | Anthropic "Building Effective Agents" |
| Three-tier stack | Hierarchical agent teams | LangGraph |
| Local-at-bottom, cloud-at-top | LLM cascading / model routing | FrugalGPT (Chen et al. 2023) |
| One-input-one-output-reusable | LLM-as-function / functional pipelines | DSPy, Outlines, Mirascope |
| Pre-assembled context bundle | Retrieval-augmented prompting / context compilation | RAG literature; also similar to DSPy's declarative signatures |
| Supervisor LLM (common-sense checker) | Evaluator-optimizer / Reflection | Anthropic "Building Effective Agents"; ReAct variants |
| Pseudo-mock LLM fixtures | Replay / golden testing | Standard LLM eval practice; similar to LangSmith datasets |

### 2.9 Philosophy: LLMs write content, code owns structure

Every LLM call in the system follows the discipline the WMS already uses ([layer7_manager.py:442-500](Game-1-modular/world_system/world_memory/layer7_manager.py#L442-L500)):

- **Code builds the prompt and assembles context.** LLMs never see raw SQL results.
- **Code validates every output.** LLM JSON is parsed, schema-checked, retried on failure.
- **Address tags are facts, never LLM-writable.** This rule extends verbatim to WNS's narrative address tags (§4).
- **Structured artifacts between layers, not prose.** The `execution_hub` receives JSON plans from the `execution_planner`; `executor_tool` receives JSON specs from `execution_hub`. Prose is for humans; machines pass typed data.

---

## 3. Trigger Signal Chain

> **Revision notes across versions.**
> - **v2:** L7 → WES direct subscription.
> - **v3:** NL7 (not L7) → WES subscription. L7 feeds WNS; NL7 fires WES.
> - **v4:** **WNS fires at every layer NL1-NL7**, not only the top. And WES is **not auto-subscribed** to any layer's output — WNS decides when to call WES, and the scope of each firing varies with which layer made the decision. Session-boot catch-up, developer injection, and WES self-request triggers are all removed.

v4 rewrites the trigger model to match "narratives and executions exist at all scales." A localized firing at NL3 calls a narrow-scope WES. A world-shift at NL7 calls a broad-scope WES. WNS is the orchestrator (CC8) that makes the call-or-not decision at each layer's firing.

### 3.1 Why L7 is the natural fire point (for WMS — not the sole gate for WNS/WES)

The WMS L7 trigger mechanism is a weighted, tag-scored bucket per world ([layer7_manager.py:78-165](Game-1-modular/world_system/world_memory/layer7_manager.py#L78-L165)). Default threshold: **200 points**. Each L6 nation summary contributes content-tag points by position:

> Position 1 = 10 pts, Position 2 = 8 pts, Position 3 = 6 pts, Position 4 = 5 pts, Position 5 = 4 pts, Position 6 = 3 pts, Positions 7–12 = 2 pts, Position 13+ = 1 pt.

When any **content tag** (never an address tag — those are facts) crosses 200 points, L7 fires. Address tags are stripped before scoring so domain/intensity/status tags get full positional weight. The net result:

- A quiet world produces **zero** L7 fires — nothing to narrate.
- A burst of activity in a single domain (heavy mining, a war, a plague) produces an L7 fire **only when the pattern is sustained enough to cross threshold across multiple nations**.
- L7 supersedes previous L7 summaries for the same world (see `_find_supersedable`) — only the latest summary is canonical.

This is **exactly the cadence WNS needs**: fire only when something genuinely world-shaping has accumulated, not on every event.

### 3.2 The signal chain end-to-end

**v4 model:** WMS fires at every layer independently. WNS subscribes broadly — it reads whatever WMS produces at any layer it needs, and also independently receives pre-generated NPC dialogue into NL1. Each WNS layer fires on its own every-N-events-per-layer-per-address cadence. When a layer decides its output warrants execution, it hands a bundle to WES.

```
Player action / NPC speech-bank generation / faction state change
  ├─► StatTracker.record_* (existing WMS entry point)
  │      └─► WMS pipeline (L1→L7 on thresholds) — unchanged from shipped behavior
  │
  └─► NPC speech-bank generator (when NPCs get new dialogue)
         └─► Deterministic mention extractor runs over speech-bank text
               └─► NL1 events written (address-tagged) — NPC dialogue captured

                       WMS layer outputs + NL1 mentions + faction state
                                         │
                                         ▼
       ┌────────────────────────────────────────────────────────────┐
       │  WNS NLTriggerManager — one trigger bucket per layer per   │
       │  address. Fires every-N events for that layer/address.     │
       │  Lower layers fire more often; higher layers see aggregated│
       │  input from many lower addresses, so fire less often.      │
       └───────────────────────────┬────────────────────────────────┘
                                   │ (layer N fires at address A)
                                   ▼
       ┌────────────────────────────────────────────────────────────┐
       │  NL<N> weaver LLM runs at address A.                       │
       │  Reads: lower-layer narrative within A + parent-address    │
       │         narrative + reconcile instruction in prompt.       │
       │  Writes: NL<N> event row (narrative + threads + tags).     │
       └───────────────────────────┬────────────────────────────────┘
                                   │
       After every NL layer fires: │ (WNS decides: call WES?)
                                   │
                   ┌───────────────┴────────────┐
                   │                            │
                   ▼ (no — narrative just       ▼ (yes — narrative warrants
                     records and waits)           generating content)
                                              ┌────────────────────────┐
                                              │  WNS assembles bundle  │
                                              │  (delta + narrative +  │
                                              │   directive) and calls │
                                              │  WES with firing tier  │
                                              │  = NL<N>, address = A. │
                                              └─────────┬──────────────┘
                                                        ▼
                                                    [§5 WES loop]
```

**Key differences from v3:**
- WNS does not wait for L7 or NL7. It fires at every layer.
- No "L7 callback → WNS auto-subscribe" wiring. WNS subscribes to whatever WMS outputs it needs, across all layers.
- WES is not a subscriber to any WMS or WNS event. WES runs only when WNS calls it.
- The firing tier (NL2, NL3, ..., NL7) rides in the bundle and drives planner-prompt scope (§5).

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

### 3.4 Trigger modes — v4 narrowed

v3 listed four trigger sources (L7 fire, dev injection, session boot, WES self-request). v4 **removes three of them**:

| Trigger | v3 status | v4 status | Reason |
|---|---|---|---|
| **WMS layer fires (any layer)** | L7 only, hard-wired | **Broadened.** WNS reads WMS output at every layer as needed; no hard-wired single hook. | WNS fires at every NL layer; needs WMS at every level. |
| **Every-N-events-per-layer-per-address** | Implicit in WMS thresholds | **Explicit.** Every WNS layer has its own trigger bucket per address. | Narratives and executions exist at all scales. |
| **Developer injection** | Listed | **Removed for now.** | Not a near-term feature. May return later as dev infrastructure, not a live gameplay trigger. |
| **Session boot / catch-up** | Listed | **Removed.** | Game continues on load as if nothing happened. Narrative state is what it was at save time. No synthetic "catch-up" beat. |
| **WES self-request** | Listed | **Removed.** | Violates unidirectional flow (CC8). WNS decides when to fire WES; WES never calls back. |

### 3.5 Subscription pattern — what WNS actually subscribes to

WNS doesn't have a single subscription point. It reads broadly from canonical stores during its weaving work:

- **WMS layer outputs** — `LayerStore.query_by_tags(layer=N, ...)`, or per-layer queries from the WMS facade. No callback strictly required; pull-on-trigger works.
- **NL1 ingestion** — NPC speech-bank generator calls `WNS.ingest_dialogue(npc_id, speech_bank, address)` when a new bank is minted. Deterministic mention extractor runs inline.
- **Faction state** — pulled at bundle assembly time when WNS is authoring a bundle.
- **GeographicRegistry / EntityRegistry** — pulled for address resolution and entity name humanization.

**The substantive commitment** is that WNS has access to WMS at every layer. The mechanism (callback vs. pull at trigger time) is an implementation detail; the first implementation can be pull-based (cheaper, no signal plumbing) and add callbacks later if pull misses events.

Callbacks, when used, never mutate upstream state. Reading is fine; writing upstream is forbidden. This is the same rule as the WMS L6→L7 callback in shipped code, extended to every WMS→WNS subscription path.

### 3.6 How "a certain effect" becomes a WES call — still open

Per the feedback lock: **WNS can call WES, but does not always.** WNS's primary job is tracking and weaving. It calls WES only when a narrative reaches "a certain effect." What defines that effect is still open:

- **Candidate A**: thread fragment count threshold ("this address has 10 open thread fragments; time to resolve something").
- **Candidate B**: severity crossing ("narrative severity went from moderate to significant — worth generating a response").
- **Candidate C**: arc-stage transition ("rising action closed at this scale — generate content to open the next arc").
- **Candidate D**: weaving LLM self-flag — the weaving prompt is instructed to include a `call_wes: yes|no` field in its output, and honor its own judgment.

**Lean** (not locked): Candidate D, with playtest tuning to confirm the LLM's judgment is calibrated. This fits the spirit of "let LLMs reason; let code enforce invariants" — the LLM already has the narrative in hand. Resolution of this choice is a §9 open question, deferred to the first playtest pass.

---

## 4. WNS Design

> **Revision notes across versions.**
> - **v2:** WNS as parallel WMS, 7 layers, aggregation semantics at every layer, emergent threads.
> - **v3:** Extraction (NL2) → weaving (NL3-5) → embroidery (NL6) — three distinct operations; 6 layers starting; threads first-class at NL2.
> - **v4:** **Unified operation** — extraction/weaving/embroidery is one operation (narrative weaving) parameterized by scale of address. String/thread/embroidery stays as mental metaphor but is not three distinct layer types. **NL1 = pre-generated NPC dialogue** captured as narrative events (not WMS ingestion, not player milestones). **NL1-NL7 locked** (not 6, not TBD). **Threads are first-class at every weaving layer**, not just NL2. **WNS authors the bundle WES consumes** — WES does not read NL6 or NL7 directly. **NL1 is the privileged narrative substrate**: stories are people-driven.

### 4.1 The string / thread / embroidery framing — as mental metaphor, not layer types

The user's original metaphor is preserved as a mental model:

- **String** = WMS raw facts.
- **Thread** = what the low WNS layers produce.
- **Embroidery** = what the high WNS layers frame.

v4 refinement: **operationally, it's one operation — narrative weaving — parameterized by scale of address.** At NL2 (district/locality), weaving pulls from a small set of recent NL1 captures and produces thread fragments. At NL7 (world), weaving pulls from the NL6 layer and wide-scope NL5 summaries and produces a world-scale narrative. Same operation, different input scope and different output scale.

```
NL1 (pre-generated NPC dialogue) + WMS layer outputs (via WNS reads)
                     │
                     ▼
        ┌────────────────────────┐
        │ NL2 weaving            │  ← "what threads exist here?"
        │ scope = locality       │     bottom-up reconciliation prompt
        └──────────┬─────────────┘
                   ▼
        ┌────────────────────────┐
        │ NL3 weaving            │  ← "what local story emerges?"
        │ scope = district       │
        └──────────┬─────────────┘
                   ▼
        ┌────────────────────────┐
        │ NL4 weaving            │  ← "what regional arcs?"
        │ scope = region         │
        └──────────┬─────────────┘
                   ▼
        ┌────────────────────────┐
        │ NL5 weaving            │  ← "what cross-regional shifts?"
        │ scope = nation         │
        └──────────┬─────────────┘
                   ▼
        ┌────────────────────────┐
        │ NL6 weaving            │  ← "world seams — where do nations touch?"
        │ scope = nation-to-world│
        └──────────┬─────────────┘
                   ▼
        ┌────────────────────────┐
        │ NL7 embroidery         │  ← "what is the world's current story?"
        │ scope = world          │
        └────────────────────────┘

At every layer: bottom-up reconciliation prompt ensures higher-layer
narrative stays consistent with lower-layer reality in the same address.
```

**Why one operation, not three**: making extraction/weaving/embroidery distinct in code duplicates logic — every layer reads some "below-layer input," references "prior same-layer summary," and produces a similarly-shaped output. The differences are (a) prompt phrasing, and (b) input scope. Both live in config, not code.

**The metaphor still matters** for prompt design: NL2 prompts should be phrased around thread-discovery ("given these events, what narrative thread fragment emerges?"); NL6-NL7 prompts should be phrased around framing and coherence ("what is the world's current story?"). The layer number drives prompt selection; the operation is the same.

### 4.2 Relationship to WMS (sibling system, NOT shared infrastructure)

> **v4 change:** WNS is a **sibling** of WMS, not an extension. Separate SQLite database. Separate tag taxonomy. Separate prompt fragment files. (See CC5 for the full invariant and §9.Q5/Q6 for the resolutions.) WNS *reuses infrastructure patterns* (address-tag immutability, layered lazy triggers, BackendManager task routing) by reference, not by shared code ownership.

What WNS copies by pattern (not shared code):

- **Address-tag immutability rule** — the *pattern* from [geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106) is applied to WNS's own narrative events. Narrative tags like `thread:` and `witness:` follow the same never-LLM-writable rule.
- **Prompt-fragment JSON layout** (`_meta`, `_core`, `_output`, `context:X`, `example:Y`) — copied pattern. WNS has its own `narrative_fragments_nl*.json` files, separate from WMS's `prompt_fragments_l*.json`.
- **`should_run()` + weighted-bucket triggering** — copied pattern in a new `NLTriggerManager`.
- **`BackendManager.generate(task, system_prompt, user_prompt)`** call shape — the only truly shared plumbing, because it's already the cross-cutting LLM abstraction.

What WNS does **differently** from WMS:

- **Separate SQLite database** (`world_narrative.db` vs. `world_memory.db`). Save/load coordinates two files atomically rather than sharing one.
- **Separate tag taxonomy** loaded by a narrative-specific `NarrativeTagLibrary` (mirrors `TagLibrary` but reads from `narrative-tag-definitions.JSON`).
- **Layer count is fixed at 7** (NL1-NL7, v4 commitment).
- **NL1 is a stored layer** with its own table, capturing NPC speech-bank dialogue + mention extraction. NL1 is deterministic (no LLM) — the only non-LLM layer in WNS.
- **Operation is unified across NL2-NL7** (weaving at scale), parameterized by prompt and input scope.
- **Every-N-events-per-layer-per-address trigger pattern** (§3.4). Lower layers fire more often than higher; exact N values are playtest-tuned.
- **Narrative-specific tag unlocks are allowed over time** (mirrors WMS pattern — new tags can join the taxonomy; individual tags remain not LLM-writable once assigned).

### 4.2b The narrative address system

WMS uses geographic address tags: `world:`, `nation:`, `region:`, `province:`, `district:`, `locality:`, `biome:`. Every WMS event carries its address as an immutable fact.

WNS reuses these exact same address tags. Narrative events happen *somewhere*. A rumor about mining unrest is addressed to the region where the mining is happening. A faction-tension beat is addressed to the nation where the factions clash. The user's framing, preserved:

> narratives will of course be affected greatly by geography. We will essentially be building a parallel WMS but for narratives.

Narrative events may *also* carry additional narrative-specific address tags that don't exist in the WMS:

- `thread:<thread_id>` — which emergent narrative thread this belongs to (if any)
- `arc:<arc_stage>` — opening / rising / climax / falling / resolved (optional, used by NL4+)
- `witness:<actor_id>` — who observed this (for NPC-grounded narrative events)

Same immutability rule as WMS address tags: these are facts about the narrative event, set at capture, never rewritten by an LLM.

### 4.3 The narrative layers — NL1 through NL7 (v4 committed)

v4 commits to a 7-layer pipeline. NL1 is its own stored layer (pre-generated NPC dialogue, deterministic capture). NL2-NL7 are all LLM weaving calls parameterized by scope.

| Layer | Operation | Unit | Primary input | Output shape |
|---|---|---|---|---|
| **NL1** | **Deterministic capture** | Per NPC speech-bank generation | Pre-generated NPC dialogue text | NL1 event rows: dialogue excerpt + extracted mentions + address tags (NPC's locality) |
| **NL2** | Weaving (locality) | Per every-N NL1 per locality | NL1 + same-locality WMS L2+ narrations | Thread fragments + local narrative snapshot |
| **NL3** | Weaving (district) | Per every-N NL2 per district | NL2 + selected same-district WMS L3 | Thread fragments + district narrative state |
| **NL4** | Weaving (region) | Per every-N NL3 per region | NL3 + same-region WMS L4 | Thread fragments + regional arcs |
| **NL5** | Weaving (nation) | Per every-N NL4 per nation | NL4 + same-nation WMS L5 | Thread fragments + national narrative arcs, tensions |
| **NL6** | Weaving (nation-to-world seams) | Per every-N NL5 world-wide | NL5 + WMS L6 | Cross-national narrative coherence, seams |
| **NL7** | Embroidery (world) | Per world bucket fire | NL6 + WMS L7 | World narrative summary — the highest-scope embroidery |

**Every layer NL2-NL7 is an LLM call.** No template layers. Each is one focused transform: pre-compressed input → narrative output + content tags. Address tags pass through unchanged (never LLM-writable).

Prompt fragment files (in the WNS-specific directory, separate from WMS):
- `narrative_fragments_nl1.json` — doesn't exist (deterministic capture); mention extractor config lives in a separate JSON
- `narrative_fragments_nl2.json` through `narrative_fragments_nl7.json` — per-layer prompts

Backend task names: `"wns_layer2"` through `"wns_layer7"` in `backend-config.json`.

**Commitments (v4-locked):**
- NL1 is deterministic capture from NPC speech-banks (no LLM).
- NL2-NL7 are all LLM calls, all weaving, parameterized by scale.
- Every NL layer has bottom-up reconciliation in its prompt (see §4.4).
- **Threads are first-class at every weaving layer**, not just NL2.
- Triggers follow every-N-events-per-layer-per-address. Lower layers fire more often. Specific N values are playtest-tuned.

### 4.3b Bottom-up reconciliation (how consistency works)

Higher-layer narrative must stay consistent with lower-layer narrative in the same address. v4 achieves this via **prompt-level reconciliation**, not a separate reconciliation layer:

- Every NL3+ weaving prompt explicitly includes: "Here is the current narrative state at layers below you in this address: [...]. Your output must not contradict them; reconcile any tension before writing the higher-level narrative."
- Lower-layer narrative rides in the prompt as context; the LLM's job is to abstract upward without contradicting the ground truth.
- If contradictions slip through, the supervisor LLM (§5) sees them during the next WES pass and can trigger a rerun. (Supervisor is WES-only; bundles that reach WES surface any unreconciled state.)

**No dedicated reconciliation LLM.** Reconciliation is a prompt design concern at every weaving layer.

### 4.4 NL1 = pre-generated NPC dialogue captured as narrative events

> **v4 commitment (CC6):** NL1 is no longer "event ingestion from WMS + NPC mentions + milestones." NL1 is **pre-generated NPC dialogue**, captured deterministically at speech-bank generation time.

**Design principle (v4):** **stories are people-driven, not event-driven.** NPC dialogue is the privileged narrative substrate WNS weaves from. WMS events are secondary context that WNS reads as it weaves — they are not NL1. Player milestones enter via WMS events; they are not a separate NL1 stream.

**Mechanism:**

1. NPC speech-bank generation runs once per NPC per content-update window (frequency TBD — probably tied to world-narrative updates so speech-banks stay in sync with current state).
2. When a speech-bank is minted, a **deterministic mention extractor** (no LLM call) runs over its text:
   - Named entities mentioned (factions, locations, person names)
   - Claim type (rumor, observation, recollection, boast)
   - Significance hint (emphasis heuristics)
3. Each extracted mention becomes an NL1 event with address tags (the NPC's current locality, carried over verbatim) plus content tags.
4. NL2 (locality weaving) reads NL1 events as the primary narrative input when weaving. The bottom-up reconciliation prompt at every higher layer means mentions that recur propagate upward; mentions that don't, fade.
5. **A mention alone never triggers WES.** Only a weaving layer that sees a pattern and flags "call WES" does.

**Why at speech-bank generation time, not player-interaction time:**

- Player interactions are now bounded (greeting → accept → turn-in → closing). There's no "live exchange" to extract from per-player-interaction.
- Mention extraction during the scripted content-update pass is stable: every NPC's mentions are a known quantity for the duration of that speech-bank's validity.
- This couples NL1 production to the NPC content pipeline directly, rather than to runtime player behavior.

**What this replaces (v3):** v3 had NL1 ingesting WMS L2+ narrations, NPC mentions, and player milestones. In v4, NL1 is narrower (only NPC dialogue/mentions); WMS events and player milestones are read by NL2+ weaving calls as context, not captured into NL1.

### 4.5 Narrative threads — first-class at every weaving layer

> **Revision note (v4):** v3 made threads the explicit output of NL2 alone. v4 generalizes: **threads are first-class output of the weaving operation**, which happens at every LLM layer (NL2-NL7). A thread at NL2 is a locality-scope thread fragment; a thread at NL7 is a world-arc-scope thread. All thread fragments share one schema and live in one table, but their address-tag scope reflects the layer that produced them.

A narrative thread fragment is emitted by every NL2-NL7 LLM call that detects one. Each weaving prompt instructs the LLM: **"If you recognize a thread being opened, continued, reframed, or closed in your scope, emit a thread fragment."** Output fields:

- `headline` — short title
- `content_tags` — from the narrative tag vocabulary (sacred; not LLM-writable as new tags)
- `parent_thread_id` — nullable; links to a prior same-scope thread
- `relationship` — `open | continue | reframe | close`
- `address tags` — pass-through from input, immutable

**Threads are implicitly multi-address.** Each thread fragment carries the address where it happened; "the thread" is the chain of parent_thread_id links across fragments, which may span multiple addresses as a story propagates up layers.

Concrete implications:

- Extraction/weaving reads prior threads in the same address scope as prompt context — continuity is informed, not imposed.
- Thread identity is the chain of parent_thread_id links. A dev tool can walk these chains for visualization; the chain itself IS the thread — no separate "thread" table needed.
- Threads are forever. Archived, never deleted (same retention model as WMS events). Context budget manages inclusion; retention is unbounded.

**What this replaces:** v3's "threads are the output of NL2 specifically" was artificially narrow. Any layer that weaves can recognize a thread — a regional-scale thread that NL4 detects is just as first-class as a locality-scale thread NL2 detects.

### 4.6 Inputs (what flows into WNS)

v4 clarifies which inputs land in NL1 vs. which are read during weaving:

```
Direct NL1 writers (captured as narrative events):
  └─ NPC speech-bank generator → mention extractor → NL1 events

Read by NL2-NL7 weaving calls (as prompt context; NOT captured as NL1):
  WMS:
    ├─ L2 narrations (narratively interesting — filtered by content tag)
    ├─ L3-L6 aggregated summaries
    └─ L7 WorldSummaryEvent

  Faction system:
    ├─ Affinity deltas
    └─ Faction state summaries

  Player activity (via existing GameEventBus, already captured in WMS):
    └─ Milestones and dramatic events surface through WMS L2+ narrations

  GeographicRegistry + EntityRegistry:
    └─ Proper names, biome types, entity identities for prompt humanization
```

**v4 change from v3:** player milestones no longer flow as a separate NL1 stream. They enter via WMS events (StatTracker → L1 → L2 narrations), and WNS reads those narrations during weaving. This honors "no separate player-milestone stream" from the feedback lock.

### 4.7 Output (what WES consumes) — the context bundle

> **v4 major change:** WES does NOT read NL7 directly. WES consumes a **context bundle** authored by WNS. When WNS decides a layer firing warrants execution, it calls WES with a bundle tailored to that firing's tier and address scope.

**Bundle shape (three parts):**

```python
@dataclass
class NarrativeDelta:
    """Dialogue + WMS events between WNS's last firing at this layer/address and now."""
    address: str                              # firing address, e.g. "region:ashfall_moors"
    layer: int                                # firing tier, 2..7
    npc_dialogue_since_last: List[NL1Row]     # NL1 rows since previous firing at this addr
    wms_events_since_last: List[WMSLayerRow]  # WMS narrations newly in scope
    start_time: float
    end_time: float

@dataclass
class NarrativeContextSlice:
    """Current narrative state at the firing's layer + parent addresses.
    Bottom-up, shallow-going-outward: full detail at firing layer,
    narrower snippets at higher layers."""
    firing_layer_summary: str                 # full narrative at firing's layer/address
    parent_summaries: Dict[str, str]          # {address: brief} for each parent layer
    open_threads: List[ThreadFragment]        # threads active in scope

@dataclass
class WNSDirective:
    """WNS's high-level instruction to WES on what to create.
    Authored by the weaving LLM that made the call-WES decision.
    NOT granular specs — directives guide scope and intent."""
    directive_text: str                       # e.g. "Generate content responding to the ashfall moors' new tension with the Silversmiths guild"
    firing_tier: int                          # 2..7; drives planner-prompt scope (§5)
    scope_hint: Dict[str, Any]                # optional slot hints (biomes, factions, tiers)

@dataclass
class WESContextBundle:
    """The single artifact WES consumes. Authored by WNS."""
    bundle_id: str
    created_at: float
    delta: NarrativeDelta
    narrative_context: NarrativeContextSlice
    directive: WNSDirective
    source_narrative_layer_ids: List[str]     # backlinks to NL* events that produced this
```

**Key commitments:**
- Bundle is **typed**, not prose. Code builds it; every LLM in WES reads fields, not paragraphs.
- Directive is **authored by the same weaving LLM that decided to call WES** — in the same prompt (preferred), not as a separate LLM call. Switch to a separate directive LLM only if the colocated approach proves inadequate in playtest.
- Bundle is WNS's working memory externalized. Everything downstream-of-WNS sees is in the bundle.
- Lower-layer narrative is available via `narrative_context.parent_summaries` (keys by address), not by re-querying stores.

**Detailed bundle field semantics, shallow-going-outward rules, and token budget tuning** live in §8.

### 4.7b Narrative table as WNS's working memory

The per-layer NL tables (`nl1_events` through `nl7_events` in the WNS-specific database) are **WNS's working memory**. They exist so higher layers can reconcile with lower layers, so supervisor retries can re-assemble bundles, and so dev tools can trace provenance.

They are **not** directly consumed by WES. WES only sees bundles.

### 4.8 Triggering — every-N-events-per-layer-per-address (v4 pattern)

Same `should_run()` / interval pattern as WMS, but applied per-layer per-address:

- NL1 events accumulate on every NPC speech-bank generation event.
- **Each NL layer NL2-NL7 has its own trigger bucket per address** tracked by `NLTriggerManager`.
- **Lower layers fire more often** than higher layers; higher layers see aggregated input from many sub-addresses so their buckets fill slower.
- **Every-N-events** means N lower-layer events at or under this address before this layer fires.
  - N values are playtest-tuned (§9.Q1). Starting values: NL2 every ~5-10 NL1; NL3 every ~5-10 NL2; and so on, exponentially slower up the pyramid.
- Higher layers can also fire on weighted-bucket content-tag accumulation (same pattern as WMS L7's 200-point threshold), if playtest shows pure every-N is too coarse.

**WES invocation is not coupled to any specific layer's fire.** When a WNS layer fires and its weaving LLM's output indicates a call-WES condition (§3.6, TBD), WNS assembles a bundle at that layer/address and calls WES.

WES does NOT subscribe to any GameEventBus event for firing. WES is called directly by WNS.

### 4.9 Address-tag immutability — same rule

Verbatim extension of the WMS rule ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)):

- `ADDRESS_TAG_PREFIXES` extends to include narrative-specific addresses (`thread:`, `arc:`, `witness:`).
- Before every NL3+ LLM call: `partition_address_and_content()` splits tags, only content tags go to the LLM.
- After: re-attach address tags unchanged. Any invented-by-LLM address tag is dropped.

This is not just copy-paste — it's the *same function* reused. The immutability contract is a code-level invariant shared between WMS and WNS.

### 4.10 Storage

Narrative layer events stored in SQLite tables, one per layer (NL1-NL7) + one tag junction table per layer:

```sql
CREATE TABLE nl1_events (id TEXT PRIMARY KEY, created_at REAL, narrative TEXT, tags_json TEXT, payload_json TEXT);
CREATE TABLE nl2_events (...);
CREATE TABLE nl3_events (...);
CREATE TABLE nl4_events (...);
CREATE TABLE nl5_events (...);
CREATE TABLE nl6_events (...);
CREATE TABLE nl7_events (...);

-- Tag junction tables per layer
CREATE TABLE nl1_tags (event_id TEXT, tag TEXT, PRIMARY KEY(event_id, tag));
...
CREATE TABLE nl7_tags (...);

-- Address index on every layer table (primary query dimension)
CREATE INDEX idx_nl1_address ON nl1_events(...);
... (through nl7)
```

**v4 change:** Storage is in a **separate SQLite database** (`world_narrative.db`), not co-located with the WMS database. Save/load coordinates both files atomically. (See CC5 and §9.Q6 for the rationale — WNS and WMS are sibling systems.)

Primary query dimension is address (e.g. "give me all NL3 events at `district:tarmouth`"). Layer + address is the workhorse query pattern.

### 4.11 No template fallbacks

v2 proposed template fallbacks at every NL layer (so the pipeline still produces valid events when backends are offline). **Removed in v3.**

Per user direction, WNS is LLM-driven at every layer. The design assumes:
- Ollama local inference is available whenever a layer fires.
- If Ollama is unreachable, the layer does not fire — it queues its pending work and retries on the next tick. Nothing crashes; nothing gets bypassed with a template.
- For dev/offline iteration, `MockBackend` (existing in `BackendManager`) still returns deterministic placeholder JSON. That's a backend-level fallback, not a layer-level template.

The invariant: a layer either produces a valid LLM-generated event, or produces no event at that tick. No halfway state with flat template output polluting higher layers.

### 4.12 Summary of changes

| v1 | v2 | v3 | v4 |
|---|---|---|---|
| Single `NarrativeBeat` | NL1-NL7 layer tables, parallel WMS | 6-layer starting (NL1 capture), extraction→weaving→embroidery | **NL1-NL7 locked**, NL1 = NPC dialogue, unified weaving at scale |
| — | 7 layers aggregation | 6 layers, three distinct operations | **7 layers, one operation (weaving) parameterized by scale** |
| — | L2 template, rest LLM | Every layer LLM except NL1 capture | **Same — NL1 deterministic, NL2-NL7 all LLM** |
| — | Shared SQLite with WMS | Shared SQLite with WMS | **Separate SQLite (`world_narrative.db`)** — sibling system |
| — | Template fallbacks every layer | No template fallbacks | **No template fallbacks — plus graceful-degrade logs every skip** |
| Beat → WES | NL7 summary → WES (direct read) | NL6 summary → WES (live-queried) | **Bundle → WES** (authored by WNS; WES never live-queries) |
| — | Threads emergent | Threads = NL2 output | **Threads = first-class at every weaving layer** |
| — | NPC mentions + milestones + WMS → NL1 | Same as v2 | **NL1 = pre-generated NPC dialogue only**; milestones via WMS events; WMS events read by weaving, not captured in NL1 |

---

## 5. WES Loop

> **Revision notes across versions.**
> - **v2:** Reframed as three-tier orchestrator-workers compound AI system; LLM self-critique dropped; mid-execution WES→WNS clarification dropped.
> - **v3:** Tier names renamed per user's preferred vocabulary. Shared immutable context object deleted; live queries against WNS's narrative-interpretation store take its place.
> - **v4:** **Live queries inside WES reversed.** No tier of WES performs a live query. All context comes from the WNS-authored bundle. **Hubs are non-adaptive dispatchers** (CC9): they batch executor_tool specs into XML-tagged fan-out and issue them in one pass, no sequential feedback loop. **Scope per firing tier is a prompt engineering concern**, not an architectural permissions matrix. **Supervisor LLM added** (CC1) as a common-sense checker across all tier I/O. Ecosystem tool dropped entirely.

The **World Executor System** is where the user's description gets concrete. The WES must:

> **plan the narrative out, reason how to get there with the game, call upon the proper tools providing proper context, and then check the work.**

The user also described WES specifically as layered: *"LLMs as layers... WES needs to call LLM tools, then ensure balance, ensure proper handling, etc. So in some way agentic because of LLM tool calling connected to simpler LLMs."*

Architecturally, this is the **Orchestrator-Workers pattern** ([Anthropic, "Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents)): a central LLM dynamically breaks down tasks, delegates to worker LLMs, and synthesizes results. WES has three tiers plus a cross-tier supervisor:

| Tier | Name | Role | Count |
|---|---|---|---|
| 1 | `execution_planner` | Decomposes the WNS-authored bundle into a structured plan of tool invocations. | One per invocation. Cloud-tolerated. |
| 2 | `execution_hub_<tool>` | Tool-specific **dispatcher** (CC9). Unpacks one plan step into an XML-tagged batch of per-item specs. **Non-adaptive** — emits all specs in one pass, no sequential feedback. | One LLM per tool type. Local. |
| 3 | `executor_tool_<tool>` | Pure JSON generator. One spec → one schema-valid artifact. Parallelizable within a plan step. | One LLM per JSON artifact. Local. |
| — | `supervisor` (new v4) | Observes all tier I/O. Common-sense checker. Rerun-only authority. | One per WES pass. Local (Cloud tolerated on escalation). |

Published equivalents (for searchability): planner ≈ Orchestrator; hub ≈ Dispatcher/Coordinator; executor_tool ≈ Specialist/Worker; supervisor ≈ Evaluator/Reflection.

### 5.1 The three-tier stack (v4)

```
Input: WESContextBundle (authored by WNS — §4.7)

        ┌──────────────────────────────────────────────────┐
        │  TIER 1 — execution_planner  (1 LLM)             │
        │                                                  │
        │  Reads (handed in by code, from bundle):         │
        │    - WESContextBundle (delta + narrative + dir.) │
        │    - game awareness (static, tiers/biomes/etc.)  │
        │    - task awareness (output schema, constraints) │
        │                                                  │
        │  NOTE: no live queries. Scope for firing_tier    │
        │  (NL2..NL7) lives in the planner prompt.         │
        │                                                  │
        │  Produces: WESPlan (JSON) — ordered steps, slots,│
        │  dependencies, or explicit abandonment.          │
        └──────────────────────┬───────────────────────────┘
                               │ WESPlan
                               ▼                        ┌─────────────────┐
  ┌────────────────────────────────────────────────────▶│   SUPERVISOR    │
  │  Deterministic code: resolve deps, topo-sort steps,  │   (cross-tier) │
  │  reject cycles, verify known biomes/factions/tiers,  │   observes all │
  │  check registry for duplicate IDs.                   │   tier I/O —   │
  └────────────────────────────┬───────────────────────── │   common-sense │
                               ▼                        │   check, rerun │
  Plan dispatched step-by-step in topological order:    │   authority    │
                               │                        │   only.        │
                               ▼                        └─────────────────┘
        ┌──────────────────────────────────────────────────┐      ▲
        │  TIER 2 — execution_hub_<tool>  (1 LLM per tool) │      │
        │                                                  │      │
        │  Reads (handed in by code):                      │──────┘
        │    - the plan step                               │
        │    - bundle (read-only; plus small slice)        │
        │    - game awareness                              │
        │                                                  │
        │  Produces: XML-tagged batch of ExecutorSpecs,    │
        │  ALL in one pass. Non-adaptive (CC9).            │
        │  e.g. <spec>...</spec><spec>...</spec>          │
        │                                                  │
        │  NO sequential feedback between executor_tool    │
        │  calls. NO live queries. NO narrative authority  │
        │  beyond what the directive and bundle provide.   │
        └──────────────────────┬───────────────────────────┘
                               │ N specs — parallel dispatch
                               ▼
        ┌──────────────────────────────────────────────────┐
        │  TIER 3 — executor_tool_<tool>  (N LLMs parallel)│──────┐
        │                                                  │      │
        │  Reads (handed in by code):                      │      │
        │    - one ExecutorSpec                            │      │
        │    - task awareness (output schema, constraints) │      │
        │                                                  │      │
        │  Produces: one JSON dict matching tool's schema. │      │
        │  Pure "one input → one JSON" transform.          │      │
        └──────────────────────┬───────────────────────────┘      │
                               │ JSON × N                         │
                               ▼                                  │
  ┌────────────────────────────────────────────────────────────┐  │
  │  Deterministic code: parse + schema-validate + cross-ref   │  │
  │  check + balance-range check. Stage into Content Registry. │  │
  └────────────────────────────┬───────────────────────────────┘  │
                               ▼                                  │
                    [next plan step]                               │
                               │                                   │
                               ▼ (after all steps)                 │
  ┌────────────────────────────────────────────────────────────┐  │
  │  Supervisor reviews all tier logs.                          │──┘
  │  Does the content match the directive? Frost-themed dir.    │
  │  produced volcanic hostiles? Rerun with adjusted inst.      │
  └────────────────────────────┬───────────────────────────────┘
                               ▼
  ┌────────────────────────────────────────────────────────────┐
  │  Deterministic verification (no LLM): registry-wide orphan │
  │  scan, duplicate check, schema-wide consistency.           │
  │  COMMIT or ROLLBACK atomically.                            │
  └────────────────────────────────────────────────────────────┘
```

The three tiers never call each other directly. **Deterministic code is the only thing that crosses tier boundaries.** Each LLM takes a prompt constructed by code and produces structured output that code parses and hands to the next tier.

**v4 key changes vs. v3:**
- **Tier 2 is non-adaptive.** The hub emits all executor_tool specs in a single XML-tagged batch. No per-spec feedback loop. Executor_tools run in parallel on the async runner.
- **No live queries anywhere in WES.** Every tier reads only what code hands it. The bundle is authoritative.
- **Supervisor is cross-tier.** Observes planner I/O, hub I/O, executor_tool I/O. Its only lever is triggering a rerun with adjusted instructions. It does not mutate state.
- **Scope per firing tier is a prompt engineering concern.** An L3 firing's bundle includes `directive.firing_tier=3`; the planner prompt instructs: "You are handling a locality-scale firing. Do not plan world-shaking content. Limit scope to NPC state changes, affinity changes, and narrow content updates." An L7 firing gets broader authorization. No architectural permissions matrix.

Abandonment is the only escape hatch: at any tier, failure may cause the plan to be marked `abandoned`. The narrative state that justified the plan stays in history; nothing commits. No clarification loop with WNS — execution does not ask narrative for help.

### 5.2 Tier 1 — `execution_planner`

**Role**: single LLM call that decomposes a WNS-authored context bundle into a structured plan.

**Backend**: cloud-tolerated (Claude via `BackendManager`, task `"wes_execution_planner"`). Per user: cloud only where necessary. The planner is one of the few roles where cloud is tolerated because (a) it's infrequent — once per WNS-driven firing — and (b) plan quality drives everything downstream. Local Ollama is the default; Claude is the escalation path when local output is structurally invalid on retry.

**What it reads (all handed in by code — no live queries):**
- The `WESContextBundle` (§4.7). Delta + narrative context + directive.
- Registry slice included in the bundle by WNS (counts + recent additions in the firing address scope).
- Game awareness block (tier definitions, biome taxonomy, domain taxonomy, address tag prefixes). Static.
- Task awareness block (planner role, output schema, constraints — including the firing-tier scope rules).

The bundle is authoritative. No fallback to live stores. If the bundle is under-specified, the planner abandons.

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

**Role (v4 narrowed)**: each tool type (hostiles, materials, nodes, skills, titles) has its own hub. The hub is a **dispatcher** (CC9), not an orchestrator. Given one plan step, the hub emits a single XML-tagged batch of per-item ExecutorSpecs in one pass. No sequential feedback loop.

**Backend**: local (Ollama, task `"wes_hub_<tool>"`).

**What it reads (all handed in by code — no live queries):**
- The plan step.
- A small bundle slice relevant to this hub's tool type (e.g., recent same-type registry entries, threads in focal address) — pre-extracted by code from the WNS bundle.
- Game awareness.
- Task awareness.

**Output: XML-tagged batch of `ExecutorSpec`s**, dispatched in parallel to the executor_tool below:

```xml
<specs plan_step_id="step_42" count="3">
  <spec id="s1" intent="...">...</spec>
  <spec id="s2" intent="...">...</spec>
  <spec id="s3" intent="...">...</spec>
</specs>
```

Each spec is the same dataclass:

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

**Hubs have LITTLE narrative authority** (v4). Narrative framing lives in WNS (which built the bundle) and in the planner (which decomposed the directive). The hub's job is to split the planner's step into specs a tier-3 LLM can execute in isolation — nothing more. Flavor hints in specs come from what the bundle and plan step already contain; the hub does not invent flavor.

**No sequential feedback loop** (v4 reversal). All N specs are emitted in one pass. Executor_tools run in parallel (§5.7). The cost of not adapting between calls is accepted in exchange for drastically simpler dispatch, natural parallelism, and a smaller model footprint per hub.

**What this rules out (intentionally):**
- No `adapt_after_output` method (removed from the hub protocol).
- No "the first hostile came out as a wolf, so the second should diverge" feedback. Diversity is the hub's responsibility *in the first pass*: if it wants 3 distinct hostiles, it must describe all three distinctly in the initial batch.

### 5.4 Tier 3 — `executor_tool_<tool>`

**Role**: produce one schema-valid JSON artifact from one `ExecutorSpec`. **Parallelizable within a plan step** (v4): since hubs are non-adaptive, all specs for a plan step can run concurrently.

**Backend**: local (Ollama, task `"wes_tool_<tool>"`). High volume. Tuned for JSON correctness. Structured-output constrained decoding (Ollama grammars or server-side schema enforcement) where possible.

**What it reads:**
- The single ExecutorSpec (handed in by code from the hub above).
- Task awareness (its output schema, hard constraints).

That's it. No registry queries, no narrative queries, no game-state lookups — the hub has already compressed everything it needs into the spec. The executor_tool is a pure functional transform: **one spec in, one JSON out**.

Why this tier is thin on purpose:
- Local 7-13B models can be fine-tuned or prompt-engineered aggressively for *one focused JSON output*.
- Structured decoding is cheap when the output schema is fixed.
- Pure-function semantics makes parallel dispatch trivial (it's the default in v4 — see §5.7).

**No LLM-to-LLM calls.** The executor_tool cannot invoke another executor_tool, cannot query another hub, cannot reach back up to the planner. If it needs information the spec doesn't have, that's a design-error in the hub above it — fixable via prompt engineering, not via more plumbing.

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

**After deterministic verification passes, the supervisor LLM gets one final review pass** over all tier logs before commit. If the supervisor flags a problem, it can trigger a WES rerun with adjusted instructions. Rerun budget is bounded (TBD, probably 1-2); after that, the plan hard-abandons.

On pass → commit: flip all staged rows to live, **write generated JSON files** (§7 / CC "Q4 both" resolution), publish `CONTENT_GENERATED` events per entity (these flow back to WMS via existing `EventRecorder`, closing the macro loop).

On fail → rollback: delete all staged rows for this plan, emit `PLAN_ABANDONED`, log for developer review. **Surface a visible on-screen indicator** (CC3) so players and devs see that content generation fell over.

**Observability is mandatory** (hierarchical LLM stacks are debugging nightmares without it): every tier logs its prompt + response + latency + token usage to `llm_debug_logs/wes/<plan_id>/<tier>_<step>_<spec>.json`. Supervisor logs its reasoning and rerun decisions alongside. Root-cause analysis of "why did the hostile come out as a wolf again?" requires seeing all three tiers' I/O plus the supervisor trace for that specific executor_tool call.

### 5.7 Asynchrony

Every LLM call goes through a unified async runner (extracted from `llm_item_generator.generate_async`). The game thread never blocks for a WES plan — plans run as background jobs on their own task queue. When a plan commits, new content appears "later that day" from the player's perspective. The world is in motion; we're not waiting.

**v4 parallelism** (default, not deferred): executor_tools within a plan step run in parallel by default, since hubs are non-adaptive. The async runner fan-outs all specs and collects outputs before handing to the staging code.

### 5.8 Scope per firing tier — prompt engineering, not permissions matrix

v4 handles the "L3 firing should not generate new nations; L7 can" concern **entirely in the planner's prompt**, not via an architectural permissions matrix.

- The bundle's `directive.firing_tier` field rides into the planner's prompt.
- Planner prompt contains a "scope discipline" section keyed by firing tier:
  - **NL2/NL3 (locality/district)**: narrow. Allowed tools: NPCs dialogue updates (via titles), affinity deltas (factions), small quest stubs, small flavor items. Not: world-shift content, new factions, new nations, new biomes.
  - **NL4/NL5 (region/nation)**: medium. Allowed: everything in NL2/NL3 plus new hostiles, new materials tied to existing biomes, regional skills.
  - **NL6 (nation-to-world seams)**: broad. Allowed: cross-national dynamics, new regional power shifts, new titles with cross-region impact.
  - **NL7 (world)**: maximum. Everything.

Hub and executor_tool are structurally identical across tiers — they just receive different plan steps. This keeps the architecture small; scope is adjustable via prompt updates without any code change.

### 5.9 What this shape rules out (intentionally)

- **No WES → WNS clarification calls.** Narrative leads. If the bundle is under-specified, the planner abandons and waits for WNS's next firing.
- **No schema/balance/cross-ref LLM verifier.** Deterministic code owns those. The supervisor is a *common-sense* checker, not a structural validator.
- **No per-tool custom topology.** Every tool uses the same `execution_hub_<tool>` ↔ `executor_tool_<tool>` pair. Differences are in prompts and schemas, not structure.
- **No live queries during WES.** The bundle is everything. If the world shifted after bundle assembly, the supervisor is the rerun trigger, not a re-query.
- **No hub sequential feedback loop.** Hubs emit one XML-tagged batch of specs in one pass.
- **No architectural scope permissions matrix.** Scope rules live in planner prompts, not in per-tier code.

---

## 6. Tool Architecture

> **Revision notes across versions.**
> - **v2:** each tool reframed as a Coordinator+Specialist mini-stack (not a single LLM call).
> - **v3:** tier names renamed — each tool is an `execution_hub_<tool>` + `executor_tool_<tool>` pair. Contract updated to remove `shared_context` / `envelope` parameters; each tier reads live from canonical stores instead.
> - **v4:** Hubs are **non-adaptive dispatchers** (CC9). All executor_tool specs issued in one XML-tagged batch. No sequential feedback. Ecosystem dropped entirely. Quests still deferred (but all five tools are unbuilt — not just quests). Generated JSON files are written on commit alongside registry (Q4: both).

Five active tool types (hostiles, materials, nodes, skills, titles); quests deferred. **None are built yet** — v3 implied shippable-but-unbuilt; v4 is explicit: implementation starts from zero. Each tool is a 2-LLM mini-stack. From the `execution_planner`'s perspective it's one tool; internally it's a hub + executor_tool pair.

1. The **`execution_hub_<tool>`** LLM takes one plan step and emits a single XML-tagged batch of per-item ExecutorSpecs. One call, all specs.
2. The **`executor_tool_<tool>`** LLM is invoked in parallel, once per spec, producing one JSON artifact per call.
3. Code assembles outputs, stages them into the registry, and moves to the next plan step.

No sequential feedback between executor_tools within a plan step. The hub's first (and only) pass must produce all the specs.

### 6.1 The mini-stack contract (v4)

```python
class ExecutionHub(Protocol):
    name: str                       # "hostiles" | "materials" | "nodes" | "skills" | "titles"
    registry_type: str              # registry table to write into

    def build_specs(self,
                    step: WESPlanStep,
                    bundle_slice: BundleToolSlice) -> List[ExecutorSpec]:
        """One LLM call that produces an XML-tagged batch of specs in one pass.
        Reads only: the step + the bundle slice the code hands in. No live queries.
        Non-adaptive — the batch is final when emitted. (CC9)"""


class ExecutorTool(Protocol):
    name: str                       # same tool name as the hub
    schema_path: str                # JSON schema for the output

    def generate(self, spec: ExecutorSpec) -> Dict[str, Any]:
        """One LLM call: spec → JSON artifact. Purely functional.
        Parallelizable — N specs from one hub run concurrently."""

    def validate(self, output: Dict[str, Any],
                 registry: ContentRegistry) -> List[str]:
        """Deterministic code — return list of validation issues (empty = OK)."""

    def stage(self, output: Dict[str, Any],
              registry: ContentRegistry, plan_id: str) -> str:
        """Insert into registry with staged=True; return content_id."""
```

**Changes from v3:**
- `adapt_after_output` removed.
- `build_specs` takes a `bundle_slice` parameter (a small, pre-extracted view of the WNS bundle relevant to this tool) instead of reading live.
- Contract explicitly non-adaptive and parallelism-friendly.

Shared infrastructure (one implementation, reused across all 5 mini-stacks):
- JSON parsing with markdown-fence stripping (reuse `npc_agent._parse_dialogue_response` pattern).
- Schema validation via `jsonschema` or lightweight dataclass validators.
- Retry policy (one retry on parse failure with stricter prompt).
- Observability: per-tier logs per spec to `llm_debug_logs/wes/<plan_id>/<tool>/<spec_id>_{hub,executor}.json`.

### 6.2 What goes where — hub vs executor_tool (v4)

| Concern | `execution_hub_<tool>` | `executor_tool_<tool>` |
|---|---|---|
| Reads the narrative / threads | Only via bundle slice handed by code | Sees only the distilled spec |
| Decides how many items to generate | ✅ (in one pass, no revision) | One spec → one output |
| Writes prose / name hints / flavor | Minimal — passes through what bundle and plan step provide | Fills schema fields |
| Chooses cross-references | ✅ (in one pass) | Honors references given |
| Enforces tier / biome constraints | — | ✅ (via schema + validator) |
| Produces game-valid JSON | — | ✅ |
| Backend | Local (Ollama) | Local (Ollama) |
| Frequency | **1 call per plan step** | **N parallel calls per plan step** |
| Adaptive? | **No** (CC9) | No (pure function) |

The hub is a **dispatcher**, not an orchestrator. The executor_tool is a pure transform.

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

**Output schema**: matches `Definitions.JSON/hostiles-*.JSON` (existing format). **WES writes a new file `hostiles-generated-<timestamp>.JSON` on commit** rather than mutating existing files — sacred boundary from CLAUDE.md. Registry is the coordination truth; generated JSON files feed existing databases on reload (Q4 resolution — both registry + files).

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

**Purpose** (when implemented): create a quest that stitches other generated content into a playable arc. Quests are the most narratively central of the six tool types, which is why they're deferred — getting the others right first is load-bearing for quality quests.

**Status**: explicitly out of scope for this phase. Listed here so the architecture slots don't need rework later. The quest tool will differ from the other five in one important way: it **references** other generated content rather than creating new content. A quest's "kill 5 hostileX" presumes hostileX exists.

**v4 design commitment for when quests arrive**: **quests get minimal context.** The hub and executor_tool for quests should be told exactly what the quest needs (kill X hostiles, gather Y materials, deliver to Z NPC) — no broader narrative reasoning at the tool tier. All narrative reasoning is handled by the layered LLMs above (WNS bundle + planner directive). The quest tool is a shape-filler, not an interpreter.

Implementation constraints:
- Quest tool runs last in any plan that contains one.
- Its spec includes the full list of same-plan content IDs already staged.
- Its output schema matches `progression/npcs-1.JSON` quest blocks + existing quest system.

Until WES reaches the quest phase, the planner prompt explicitly excludes `quests` from available tool choices.

### 6.4 Generation order within a plan

Dependencies are naturally ordered and enforced by `execution_planner`'s `depends_on` output + code-level topo sort. Ecosystem is **not** in this graph (v4 removed it from the tool set):

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

Within a plan step, all executor_tool calls are parallel (CC9). Across plan steps, topo order is enforced by the dispatcher.

### 6.5 "Agentic" — redefined in v4

> **v4 change:** The original framing of "agentic hubs" (live queries, sequential feedback, flavor ownership) is retired. **Hubs are dispatchers, not agents** (CC9). The "agentic" character of WES is split between two parts:

1. **The `execution_planner` decides what to do** — reads the directive, picks which tools to invoke, orders dependencies, writes the plan. This IS a form of agency — goal-directed decomposition.
2. **The hub decides how many items and their broad framing** — but in one shot, not iteratively.

Everything else is deterministic code.

**What each WES tier CAN do:**
- Planner: decompose a bundle/directive into an ordered plan of tool steps. Veto the plan (abandon) if scope disagreement with directive.
- Hub: unpack a step into an XML-tagged batch of ExecutorSpecs in one pass.
- Executor_tool: produce one JSON artifact from one spec.
- Supervisor: observe all tier I/O; trigger rerun with adjusted instructions.

**What each WES tier CANNOT do:**
- Hub cannot revisit its spec batch after seeing executor_tool output.
- Hub cannot call another tool's hub (planner's job).
- Hub cannot create plan steps.
- Executor_tool cannot query live stores.
- Executor_tool cannot see other executor_tools' outputs.
- Supervisor cannot mutate plans, bundles, registry rows, or mark plans abandoned.

This bounds the agency by design. Cross-tool coordination is mediated by the planner; cross-spec coherence within a plan step is the hub's responsibility in its one-shot emission; cross-plan quality is the supervisor's (rerun) concern.

### 6.6 Where prompts live

Two prompt fragment files per tool (one per tier), in a **WES-specific directory** separate from WMS and WNS prompts:

- `prompt_fragments_hub_<tool>.json` — hub prompts (XML-batch dispatching)
- `prompt_fragments_tool_<tool>.json` — executor_tool prompts (spec → JSON schema)

Follows the existing `prompt_fragments_l*.json` layout (`_meta`, `_core`, `_output`, per-context variants). Same JSON shape for greppability; different directory for separation.

There are additionally:
- `prompt_fragments_wes_execution_planner.json` — the single planner prompt
- `prompt_fragments_wes_supervisor.json` — the supervisor prompt (v4 addition)

### 6.7 Parallelism (v4 default, not future)

In v4, **executor_tool calls within a plan step run in parallel by default**, since hubs are non-adaptive (CC9). The async runner (§10.P0) fans out all specs from a hub's XML batch and awaits all outputs before handing to the staging code.

Two remaining parallelization opportunities:

- **Parallel plan steps when there's no cross-dependency** — if two plan steps don't depend on each other's outputs, run their hubs + executor_tools in parallel. Still deferred; currently steps run in topo-order sequentially.
- **Parallel WES plans triggered by different WNS firings** — if NL3 and NL5 fire close together and both call WES, run both WES plans concurrently. Deferred.

These remaining parallelism opportunities require scheduler infrastructure beyond `AsyncLLMRunner`; they're explicit roadmap items for P9+ if needed.

---

## 7. Content Registry

> **Revision notes across versions.**
> - **v2, v3:** Registry as the single source of truth, JSON on disk was the v3 Q4 open lean.
> - **v4:** **Q4 resolved as "both"** — registry is authoritative for coordination, generated JSON files are written on commit so existing databases reload cleanly. Pass 3 (nightly scrub) is deferrable.

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

**Pass 3: Nightly / on-save scrub** (DEFERRABLE per v4).
Hard invariant enforcement: if any live content ever references a missing ID (due to a bug, a corrupted save, manual JSON edits, etc.), log a repair action. Default repair is "downgrade reference to a safe fallback" (e.g., orphan material drop → generic tier-matched material).

**v4 note:** Pass 3 is defensive infrastructure for corruption scenarios that should not occur in normal operation. Passes 1 and 2 are essential and must ship with the first Content Registry milestone. Pass 3 can land later — don't block the registry on it.

### 7.4 Integration with existing databases (v4: both registry AND JSON files)

The Content Registry does not replace `MaterialDatabase`, `EnemyDatabase`, etc. Those load from JSON files at startup. **Q4 is resolved as "both":** registry is authoritative for coordination and relationships; generated JSON files are written on commit so existing databases reload cleanly.

WES's commit step:

1. Flips registry rows to `staged=0` (live).
2. **Writes the JSON to a generated content file** in the appropriate generated subdirectory (e.g., `items.JSON/items-materials-generated-<timestamp>.JSON`, `Definitions.JSON/hostiles-generated-<timestamp>.JSON`). **Never mutates existing sacred content JSONs.**
3. Re-triggers the relevant database to reload (or appends in-memory) so the content is immediately available.

The databases remain the runtime truth. The registry is the coordination layer + relationship graph + provenance ledger. **Human-authored JSON and generator-authored JSON coexist seamlessly** — both end up in the same databases, the registry just additionally knows about the generator-authored subset and their relationships.

**v4 rationale for "both"**: registry-only would require rebuilding how every runtime database loads (a significant, invasive change). Files-only would lose cross-reference integrity, provenance, and lineage queries. Both is the pragmatic answer — registry is source of truth for *what is related to what*; files are source of truth for *what exists at runtime*. They stay in sync because WES writes both on commit as one atomic operation.

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
> - **v3:** Shared immutable context deleted. Each LLM queries canonical stores live at its own call time. Seven per-LLM-role assemblers, each owning its own tuning.
> - **v4:** **Live queries reversed for all downstream consumers.** Context is pre-assembled by WNS into a typed bundle (§4.7). WNS reads canonical stores; **nothing else does**. The seven assemblers collapse into **two**: a WNS-internal assembler (for layer-to-layer weaving) and a WNS-to-WES assembler (for bundle construction). Distance-decay moves from "v2 follow-up" to "WNS day-one" since low-tier firings are day-one scope. Supervisor LLM is the compensating mechanism for the loss of live re-queries.

The user's framing, preserved:

> **The true difficulty of this is the information.**

Every LLM call in this system is a focused transform: one input, one output. The entire system works only if each of those inputs is composed well — enough context for the call to succeed, nothing more. This section is the doc's center of gravity.

### 8.1 The core principle: LLMs as composable transforms reading pre-assembled inputs

Paraphrasing the user's framing:

> **"Usually for most LLMs it will be one input for one LLM, that output is then more useful and may or may not be used multiple times."**

Two ideas, combined:

1. **LLMs are functions.** One input → one output → reusable artifact. Matches DSPy / Outlines / Mirascope. (Berkeley BAIR frames the whole thing as a **compound AI system**.)
2. **The "reusable artifact" lives in a canonical store.** WNS reads from those stores when assembling context. **Downstream consumers do not.** They read from the bundle WNS hands them.

Three implications:

1. **Each LLM has one job.** Not "decide whether to do X or Y." One transform. Routing decisions are code.
2. **Outputs are stored, not paraphrased.** A WMS L6 summary is a row in SQLite that WNS queries when weaving. An NL3 regional narrative is a row in SQLite that the NL5 weaver reads when it fires. No intermediate prose-paraphrase hop.
3. **Inputs to WES are assembled by WNS, once per firing.** No universal envelope. No per-tier live re-queries. No snapshot propagation by paraphrase — the bundle is structured data, and each tier reads its relevant fields.

### 8.2 Why pre-assembled bundles replace v3's live-query model

v3 had each tier read from canonical stores at its own call time. The argument: telephone is avoided because each tier queries the source, not the tier above.

**v4 reversed this for two reasons:**

1. **Cognitive cost for small local LLMs.** Live querying requires the tier's prompt to describe the stores, explain how to query, and then process results. For a local 7-13B model driving the executor_tool, this is dead weight — it crowds out the actual generation task in the prompt.
2. **Variance between tiers.** If the planner sees one narrative state and the hub sees a slightly later one, the hub's spec may not match the plan. The supervisor's job (§5, CC1) is to catch this — but in v3 there was no supervisor, and the variance was silent.

**How v4 preserves v3's telephone-avoidance**: the bundle is **data, not prose**. Code assembles it once; each tier reads the fields it needs. No tier re-summarizes; every tier sees the same structured fields. The bundle is a structured snapshot, not a paraphrase chain.

**The tradeoff accepted**: the bundle may grow stale between assembly and executor_tool completion. The supervisor compensates — if it flags obvious incoherence (directive said "frost," tool made "volcanic"), it reruns with adjusted instructions. If staleness is never flagged, the bundle was close enough.

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

### 8.5 Two context assemblers (not seven)

> **v4 collapse:** v3's seven per-role assemblers are consolidated into **two**, both owned by WNS.

| Assembler | Owns | What it produces |
|---|---|---|
| **WNS-internal assembler** | All NL2-NL7 layer LLM prompts | Input to a weaving layer = lower-layer narrative in same address + parent-address narrative + bottom-up reconciliation instruction |
| **WNS-to-WES bundle assembler** | The `WESContextBundle` | Delta + narrative context slice + directive, per firing. Tool-specific slicing (for hub consumption) is a deterministic code pass over this bundle. |

That's it. The planner, hub, and executor_tool do not own assemblers — code extracts the fields they need from the bundle and hands them over. The NPC dialogue generator (pre-generation path) is a separate existing assembler in `NPCAgentSystem`, not part of WNS or WES.

**Per-LLM token budgets** are still a tuning concern, but the budget is applied by code when extracting bundle slices for each tier, not by a per-role LLM-facing assembler. Token budget discipline:

- **Planner**: gets the full bundle (delta + narrative context + directive). Tightest budget concern, since cloud calls are expensive.
- **Hub**: gets a tool-specific slice — the plan step + relevant narrative threads in focal address + relevant registry entries. Budget is tighter; irrelevant tool-foreign context is dropped.
- **Executor_tool**: gets only the single ExecutorSpec + schema. Smallest budget — local model-friendly.
- **Supervisor**: gets the full log trail from this plan pass. Budget scales with plan size; cloud escalation available if logs exceed local model's comfortable context.

All four tiers still receive the two small blocks from §8.3 (game awareness + task awareness) — those never change.

### 8.6 Pre-compression via WMS + WNS layers

Both pipelines are context-compression pyramids:

- **WMS**: raw events (thousands) → layer narrations (fewer at each step) → world-level summary (one).
- **WNS**: narrative-worthy events → thread fragments (extraction) → regional/national narrative (weaving) → world narrative (embroidery).

This means **later LLMs never walk raw events**. They read from the top of their pyramid. Each layer's LLM call was already one focused transform — the one-input-one-output principle applied recursively. By the time WES reads the WNS embroidery output, thousands of underlying events have been compressed through multiple LLM-driven passes.

This is why WNS must *be* a pipeline, not a single call. A single-call WNS would have to compress thousands of events in one prompt. A layered WNS compresses incrementally, producing reusable artifacts at each level that higher layers query live.

### 8.7 NPC mention tracking — at speech-bank generation time (v4)

Per §4.4, NL1 is **pre-generated NPC dialogue** captured deterministically. Mentions flow into the narrative pipeline from there.

v4 information-flow mechanics:

1. When an NPC's speech-bank is minted (once per content-update window), a **deterministic mention extractor** (no LLM call) runs over the speech-bank text — keyword patterns, named-entity hints, significance heuristics.
2. Extracted mentions become NL1 events with the NPC's locality address.
3. The NL2 weaving layer sees mentions alongside same-address WMS L2+ narrations. Only mentions that recur (same entity mentioned by multiple NPCs in the same region) gain enough weight to be woven into a thread fragment.
4. Single-NPC hallucinations never surface into threads. They stay as isolated NL1 entries, archived forever but ignored by higher weaving layers.

**Why at speech-bank time, not live-interaction time:**

- Player interactions are bounded (CC6), so live mention extraction would be noisy and redundant.
- Speech-bank generation is a scheduled pass — mention extraction is deterministic work that fits that pass naturally.
- NPCs in the same region often mention the same entities (a well-known local faction, a visible geographic feature); that recurrence is the grounding signal WNS uses to separate real patterns from single-NPC imagination.

This gives NPCs a path to seed future narrative without letting any one NPC control it. The weaving layer's pattern-recognition (and its own LLM judgment) is the filter.

### 8.8 Distance decay — WNS day-one concern (v4 accelerated)

> **v4 change:** v3 deferred distance decay to "v2 follow-up when WES produces localized content." **v4 accelerates this** because low-tier WES firings (NL3 locality-scale, NL4 regional) are day-one scope — the planner sees firings at every scale, not only world-scale.

Narrative address tags (§4.2) enable geographic filtering when WNS assembles bundles:

```
Firing at (region_R, locality_L) on layer NL3:
  Bundle narrative_context contains:
    ├─ firing layer summary  (NL3 at locality_L, this address)        [full detail]
    ├─ parent NL4 at region_R                                          [brief summary]
    ├─ parent NL5 at nation containing region_R                        [brief summary]
    ├─ parent NL6 (world seams touching this nation)                   [1-sentence hook]
    └─ parent NL7 world narrative                                      [1-sentence hook]

  Bundle narrative_context DOES NOT contain:
    └─ narrative from sibling regions or other nations                 [not relevant at NL3]

  Bundle delta contains:
    └─ NL1 + WMS events in this locality only                          [tight scope]
```

**Shallow-going-outward principle**: the firing's own layer/address gets full detail; parent addresses (broader scopes containing the firing address) get progressively shorter summaries; sibling addresses (other localities in the same region) are dropped except when explicitly cross-referenced in an open thread.

**Concrete depths for different firing tiers** — specific word/token budgets per-depth are TBD in playtest. Starting lean:
- NL3 firing: full-detail at NL3/NL2 in address; 2-sentence parent summaries at NL4/NL5/NL6/NL7.
- NL5 firing: full-detail at NL5/NL4 for this nation; 2-sentence at NL6/NL7; 1-sentence summaries of sibling-nation NL5 if any are threaded to this nation's arc.
- NL7 firing: full-detail at NL7/NL6; 3-sentence summaries per nation at NL5; brief regional highlights if they're world-shaping.

Implementation:
- `GeographicRegistry` already computes parent-child relationships.
- A `NarrativeDistanceFilter` utility (v4 addition) lives inside the WNS-to-WES bundle assembler.
- Depth rules are prompt-config, not code-wired — easy to tune per firing tier.

**NPC dialogue consumers** (the existing `NPCAgentSystem`) should also use distance decay so distant events don't leak into local-NPC casual knowledge. That's a separate integration from the WES bundle, but uses the same `NarrativeDistanceFilter`.

### 8.9 Context poisoning — mitigations across the whole stack

A single bad LLM output anywhere in WMS or WNS can pollute downstream. Mitigations (v4-current):

**Already in place (WMS):**
- Address-tag immutability ([geographic_registry.py:81-106](Game-1-modular/world_system/world_memory/geographic_registry.py#L81-L106)) — LLMs cannot invent regions.
- Content tags must exist in `tag_library.py` — new-tag pollution blocked.
- Narrations are bounded length; over-length outputs truncated.

**New in WNS (mirrored patterns, sibling tables):**
- Narrative address tags (`thread:`, `arc:`, `witness:`) follow the same immutability rule via a dedicated `NarrativeTagLibrary`.
- NL-layer LLM calls strip address tags before the call, re-attach after.
- NL weavers pick content tags from the narrative tag taxonomy; cannot invent.
- Bottom-up reconciliation prompt at every NL3+ layer (§4.3b) catches lower-layer contradiction before it propagates.

**New in WES:**
- No LLM-to-LLM direct calls; no tier-to-tier pollution vector.
- **Bundle is structured data, not paraphrase.** Each tier reads fields, not prose. No compounding paraphrase drift.
- Every `executor_tool` output goes through schema validation + registry cross-reference check before being staged.
- **Supervisor LLM** (§5, CC1) is the common-sense backstop — it catches "directive said frost, tool made volcanic" by reading tier logs before commit. Rerun-only authority.
- **On-screen graceful-degrade surfacing** (CC3) means even a silent pollution that slipped through to commit is visible during development.
- Observability: full prompt+response logs per tier per spec, including supervisor trace. "Why did this happen?" is answerable by reading the logs.

### 8.10 Where context actually comes from — concrete sources (v4)

> **v4 change:** the right column used to say "Queried by (live, at call time)". In v4, **only WNS queries these sources**. WES consumes the bundle WNS authors.

| Source | API | Read by (only during WNS bundle assembly or internal weaving) |
|---|---|---|
| `WorldMemorySystem.get_world_summary()` | facade (shipped) | WNS-internal assembler (weaving context), WNS-to-WES bundle assembler |
| `LayerStore.query_by_tags(layer=N, ...)` | existing | WNS-internal assembler (WMS layer N narrations as weaving input) |
| `WorldNarrativeSystem.get_layer_summary(layer, address)` | **NEW** (§4.10) | WNS-internal assembler (prior same-layer summaries for supersession) |
| `WorldNarrativeSystem.query_threads(address, ...)` | **NEW** (§4.5) | WNS-internal assembler (weaving context), WNS-to-WES bundle assembler (thread inclusion in bundle) |
| `NLLayerStore.query_by_tags(layer=N, ...)` | **NEW** (§4.10) | WNS-internal assembler |
| `FactionSystem.stats` / `get_npc_profile()` | existing | WNS-to-WES bundle assembler |
| `GeographicRegistry` | existing singleton | All (address resolution, name humanization) — WNS-only except for runtime utility functions |
| `EntityRegistry` | existing singleton | WNS-to-WES bundle assembler (what NPCs/enemies exist) |
| `StatTracker.get_summary()` | existing | WNS-to-WES bundle assembler (title unlock hints fold into bundle) |
| `ContentRegistry` | **NEW** (§7) | WNS-to-WES bundle assembler (counts, recent additions, diversity), AND verify step (anti-orphan) |
| NPC speech-bank | **NEW** (§4.4, §8.7) | NL1 input source (at speech-bank generation time, deterministic) |

Everything shipped is battle-tested. Everything NEW is green-field for this phase.

**WES tiers do NOT appear in the right column.** Planner reads from the bundle WNS handed it. Hub reads from the bundle slice code handed it. Executor_tool reads from the spec code handed it. Supervisor reads from the logs code handed it. Code bridges are the only interfaces between canonical stores and WES LLMs.

### 8.11 Observability — non-negotiable

Hierarchical LLM stacks are debugging nightmares without tracing. "Why did this hostile come out as a wolf variant again?" must be answerable.

**Every LLM call logs:**
- Assembled prompt (system + user)
- Game-awareness + task-awareness blocks that were embedded
- The bundle fields that were read (or queries run, if WNS)
- Raw response
- Parsed output
- Token usage + latency
- Backend used (Ollama/Claude/Mock/Fixture)

**Every graceful-degrade event logs** (CC3 contract):
- What tried to happen
- Why it failed
- What fallback was taken
- Timestamp + game time + call site

File layout:
```
llm_debug_logs/
  ├─ wms/                          # Existing
  │  └─ <timestamp>_<layer>.json
  ├─ wns/                          # New
  │  ├─ nl2/<timestamp>_<address>.json    # weaving (locality)
  │  ├─ nl3/<timestamp>_<address>.json    # weaving (district)
  │  ├─ nl4/<timestamp>_<address>.json    # weaving (region)
  │  ├─ nl5/<timestamp>_<address>.json    # weaving (nation)
  │  ├─ nl6/<timestamp>.json              # weaving (nation-to-world seams)
  │  └─ nl7/<timestamp>.json              # embroidery (world)
  ├─ wes/                          # New
  │  └─ <plan_id>/
  │     ├─ bundle.json                    # the WNS-authored bundle
  │     ├─ execution_planner.json
  │     ├─ hub_<tool>_<step>.json         # one call per step (XML batch emission)
  │     ├─ tool_<tool>_<step>_<spec>.json # N calls per step, parallel
  │     └─ supervisor.json                # supervisor trace, rerun decisions
  └─ graceful_degrade/             # New (CC3)
     └─ <timestamp>_<subsystem>.json
```

**v4 additions:**
- `bundle.json` per plan — the bundle WNS handed to the planner. Reconstructs the full context the planner saw.
- `supervisor.json` per plan — supervisor's reasoning, what it flagged (if anything), rerun decisions.
- `graceful_degrade/` directory — structured log per degrade event, not just console prints.

This makes every generation event root-causeable by reading files on disk. No special UI required; grep and jq suffice. Observability tools like LangSmith or Langfuse can be layered on later if the log volume warrants, but the bar is "answerable without them."

**Supervisor uses the same log infrastructure — no separate observability pipeline for it.** When the supervisor decides to rerun, that decision + reason is a log entry.

---

## 9. Open Questions & Decisions Needed

> **Revision notes across versions.**
> - **v2:** First round of resolved items captured.
> - **v3:** Four more questions resolved (NL2 LLM-everywhere, live queries, threads-forever, tier names). Q1 reframed around extraction/weaving.
> - **v4:** Seven more questions resolved (trigger pattern, BalanceValidator stub, registry+JSON "both", narrative tag file separate, separate DBs, Player Intelligence optional, in-hub parallelism dissolved). Three new open questions introduced ("certain effect" WES trigger, bundle dataclass shape, supervisor budget/heuristics).

### Resolved in v4 (patterns locked; specifics may still be playtest-tuned)

#### Q1. NL layer trigger configuration + extraction granularity — **[RESOLVED v4]**

Pattern: **every-N-events-per-layer-per-address**. Lower layers fire more often than higher layers. Specific N values are playtest-tuned and live in `memory-config.json` (WNS section). Starting guesses: NL2 every ~5-10 NL1 per locality; NL3 every ~5-10 NL2 per district; exponentially slower up the pyramid.

Weighted-bucket content-tag accumulation (WMS L7 pattern) remains an option if pure every-N is too coarse at higher layers — that's a playtest decision during P2-P3. Either way, the mechanism is "trigger bucket per layer per address" managed by `NLTriggerManager`.

#### Q3. BalanceValidator — **[RESOLVED v4]** Minimal stub

Per the feedback lock: validators are genuinely hard; realistic scoping accepted. Minimal stub (~50 LOC) reads tier multipliers from `Definitions.JSON/stats-calculations.JSON`, rejects outliers. Full BalanceValidator remains a separate project (see `Development-Plan/SHARED_INFRASTRUCTURE.md` spec).

#### Q4. Generated JSONs on disk or registry-only — **[RESOLVED v4]** Both

Registry is authoritative for coordination and relationships. On commit, generated JSON files are written to a generated subdirectory (e.g., `items.JSON/items-materials-generated-<timestamp>.JSON`). Existing databases reload to pick up the new files. This is closer to "both" than "either/or." See §7.4 for the commit-step details.

#### Q5. Narrative tag taxonomy — **[RESOLVED v4]** New standalone file

A new standalone `narrative-tag-definitions.JSON` + a `NarrativeTagLibrary` mirror of `TagLibrary`. WNS and WMS do not share tag taxonomy. (CC5 — WNS and WMS are sibling systems.)

#### Q6. SQLite database — **[RESOLVED v4]** Separate databases

`world_narrative.db` separate from `world_memory.db`. Save/load coordinates both files atomically. Prompt fragments, tags, storage — everything separate. (CC5.)

#### Q8. Player Intelligence dependency — **[RESOLVED v4]** Optional addition

WNS/WES ship without player profile. Optional addition when Part 3 lands — the WNS-to-WES bundle gains a `player_profile` field, and planner/hub prompts get updated. No code restructure needed.

#### Q9. In-hub parallelism — **[DISSOLVED v4]**

The question dissolves because hubs always fan out executor_tool calls in parallel (CC9). Sequential feedback loop removed. Parallelism is an async-runner implementation detail, not a design decision.

---

### Still open (v4)

#### Q10. "A certain effect" — WES trigger condition

**Problem**: WNS decides when a narrative warrants calling WES. What specific condition triggers "call WES"?

**Candidates**:
- **A**: Thread fragment count threshold per address (e.g., "10 open threads in this locality → call WES with narrow scope")
- **B**: Severity crossing in the weaving output (moderate → significant triggers a call)
- **C**: Arc-stage transition detection (rising action closed → generate resolution content)
- **D**: Weaving LLM self-flag — prompt instructs the weaver to include a `call_wes: yes|no` field in its output, and honor its judgment.

**Lean**: D with fallback to A if D proves unreliable. Detailed design happens during P6 (execution_planner bring-up) after observing NL-layer output in playtest.

#### Q11. Context bundle dataclass — specific field shapes

**Problem**: §4.7 sketches the three parts (delta + narrative context + directive). Specific field types, serialization format, and per-field token budgets are TBD.

**Resolution path**: P5 (WES deterministic shell) makes the bundle a first-class dataclass. Shape freezes then; a schema sketch lives in P0 so downstream phases build against a stable contract.

#### Q12. Supervisor LLM — rerun budget, invocation heuristics, prompt framing

**Problem**: Supervisor scope is settled (common-sense checker, rerun-only). Specifics TBD:
- Rerun budget (lean: 1-2 per plan, then hard-abandon).
- Invocation heuristics (always after every plan; or only when plan has high-severity content; etc.).
- Prompt framing.

**Resolution path**: P6 / P6.5 when supervisor integrates into WES. Must resolve before P7 (first tool ships).

---

### Resolved (decision captured, no longer blocking)

- **[RESOLVED v2] Backend selection per LLM call** — Cloud (Claude) only for `execution_planner`, possibly the WNS top layer, and escalated supervisor reruns (v4 addition). Everything else local (Ollama). Per user: *"Ideally none"* — cloud is fallback, not default. Routing via `backend-config.json` task types.
- **[RESOLVED v2] Unified async runner** — Yes. Build `AsyncLLMRunner` for WES; migrate NPC dialogue to it; leave `llm_item_generator` alone until it needs touching.
- **[RESOLVED v2] Rollback semantics** — Hard rollback (all-or-nothing per plan) in v1.
- **[RESOLVED v2] LLM verifier / evaluator** — None. **[v4 PARTIAL REOPEN]** Deterministic code still owns schema/balance/cross-ref validation. A supervisor LLM is added as a **common-sense checker** with rerun-only authority (§5, CC1). This does not change the deterministic-code-owns-structure invariant.
- **[RESOLVED v2] WES → WNS clarification loop** — Dropped. Narrative leads, execution serves. If a bundle is under-specified, the `execution_planner` abandons. The next WNS firing produces a new bundle.
- **[RESOLVED v2] Universal ContextEnvelope with fixed tier ratios** — Dropped. Per-LLM-role assemblers with individual tuning. **[v4 refinement]** Collapsed further — two assemblers, both owned by WNS (§8.5).
- **[RESOLVED v3] NL2 template vs LLM** → **LLM at every layer.** No template-only NL tiers. For offline dev, MockBackend is the fallback at the backend level, not at the layer level. **[v4 retained.]** Pseudo-mock fixtures augment MockBackend (CC4).
- **[RESOLVED v3] Thread retention** → **Forever, archived.** No time-based pruning. Threads remain queryable indefinitely. Context budget manages inclusion, not retention. **[v4 retained; extended: threads are multi-address chains.]**
- **[RESOLVED v3] Threading — emergent schema vs first-class** → **First-class.** v4 generalization: **threads are first-class output at every weaving layer, not just NL2.** (§4.5)
- **[RESOLVED v3 / REVERSED v4] Shared context — snapshot vs live** → **v3: live queries. v4: pre-assembled bundle.** (§2.4, §8.) Each LLM queries canonical stores at its own call time is replaced by each LLM reads pre-assembled bundle slices. Two tiny things still travel with every prompt: game awareness (static constants) and task awareness (what to produce).
- **[RESOLVED v3] Tier naming** → `execution_planner` → `execution_hub_<tool>` → `executor_tool_<tool>`. Published pattern names (Orchestrator-Workers, etc.) retained as citations. **[v4 addition]** Supervisor tier added.
- **[RESOLVED v4] Trigger pattern** — every-N-events-per-layer-per-address for WNS; no auto-subscribe for WES. (Q1 above, §3, §4.)
- **[RESOLVED v4] BalanceValidator** — minimal stub ships; full validator deferred. (Q3.)
- **[RESOLVED v4] Generated content on disk + registry** — both. (Q4, §7.4.)
- **[RESOLVED v4] Narrative tag file** — new standalone. (Q5.)
- **[RESOLVED v4] SQLite location** — separate. (Q6, CC5.)
- **[RESOLVED v4] Player Intelligence dependency** — optional later. (Q8.)
- **[RESOLVED v4 / DISSOLVED] In-hub parallelism** — hubs always parallelize. (Q9, CC9.)
- **[RESOLVED v4] NL1 identity** — pre-generated NPC dialogue captured deterministically. Not WMS event ingestion, not player milestones. (§4.4, CC6.)
- **[RESOLVED v4] WNS-WMS separation** — sibling systems, separate DBs, separate tag taxonomies, separate prompt fragment files. (CC5.)
- **[RESOLVED v4] NPC interaction model** — bounded cycle (greeting → accept → turn-in → closing); live conversation deferred. (CC6.)
- **[RESOLVED v4] Ecosystem tool status** — dropped from WES tool scope. May reappear later as a WNS-side context source.
- **[RESOLVED v4] Scope discipline** — planner prompt, not permissions matrix. (§5.8.)
- **[RESOLVED v4] Graceful degrade discipline** — every event logs structured entry; WES failures surface visibly on-screen. (CC3.)
- **[RESOLVED v4] Pseudo-mock infrastructure** — P0 requirement. Every LLM role gets a fixture code + canonical mock I/O. (CC4, §10.P0.)
- **[RESOLVED v4] Three trigger modes dropped** — session-boot catch-up, dev injection, WES self-request all removed. (§3.4.)
- **[RESOLVED v4] Distance decay — day-one WNS concern**, not v2 follow-up. (§8.8.)

---

## 10. Phased Implementation Roadmap

> **Revision notes across versions.**
> - **v2:** 7→10 phase expansion to reflect WNS-as-pipeline scope.
> - **v3:** Template-NL2 step removed (LLM at every layer). Tier names renamed. `WESSharedContext` removed (live queries instead). NL layer count loosened from 7 to "extraction + weaving + embroidery, ~6 starting."
> - **v4:** **Phase order demoted to mental model**, not shipping schedule. Single-pass AI-driven implementation is likely, so the roadmap's dependency structure is still useful for reasoning but shouldn't be treated as a gate sequence. **P0 substantially expanded** (LLM Fixture Registry, graceful-degrade logging, on-screen WES-failure surfacing, context-bundle schema sketch). NL layers locked at NL1-NL7. Hub adapt-loop removed from P7-P8. Supervisor integrated at P6/P6.5. P3 publishes narrative events for observability only — not as a WES trigger.

Each phase produces a shippable increment. No phase requires the next phase to provide value. **The phase numbering reflects dependency logic, not ship order** — a single-pass build may touch P0-P9 intermixed.

### P0 — Shared Infrastructure (v4 expanded)

Plumbing. Every later phase needs it. **P0 is larger in v4** because the feedback lock promoted several items from later phases.

- **P0.1** `AsyncLLMRunner` — unified background-thread executor with dependency-ordered step execution and **parallel fan-out within a step**. Extract from `llm_item_generator.generate_async` into `world_system/living_world/infra/async_runner.py`.
- **P0.2** Game-awareness + task-awareness prompt blocks — small helper that emits the two tiny context blocks described in §8.3. Used by every LLM in the system.
- **P0.3** **LLM Fixture Registry** (v4 NEW — CC4). Every LLM role gets a fixture code + canonical mock I/O pair. Backend manager routes to the fixture when in mock mode, allowing end-to-end pseudo-mock runs without touching a real LLM. Lives in `world_system/living_world/infra/llm_fixtures/`. Tests depend on this.
- **P0.4** **Graceful-degrade logging contract** (v4 NEW — CC3). Structured `graceful_degrade_logger` module. Every subsystem that graceful-degrades calls it. Emits a typed entry to `llm_debug_logs/graceful_degrade/`.
- **P0.5** **On-screen WES failure surfacing** (v4 NEW — CC3). Visible UI indicator when WES plan abandonment or supervisor hard-fail happens. Minimal initial implementation: persistent HUD indicator that stays visible until dev acknowledges. Full UI design refinable later.
- **P0.6** **Context bundle schema sketch** (v4 NEW — CC2). Bundle dataclasses (even if incomplete) so downstream phases build against a stable contract. Full dataclass in P5; this is the sketch.
- **P0.7** NPC dialogue async migration — move synchronous `_generate_npc_opening` onto the new runner. Acceptance test for P0.1.
- **P0.8** WMS subscription infrastructure — WNS subscribes broadly to WMS (not only L7). Either callback registration or a pull-on-trigger abstraction — first impl is pull-based, cheaper.

Exit criteria:
- Fixture registry passes full end-to-end pseudo-mock test (fake WES plan runs from bundle → planner → hub → executor_tool → staging, with every LLM replaced by a fixture).
- Graceful-degrade logger wired into both NPCAgent fallback and `_init_world_memory` fallbacks.
- Context bundle dataclass exists, round-trips through JSON, and is importable by downstream phases.
- NPC dialogue no longer blocks the UI.
- ≥10 new passing tests covering the above.

---

### P1 — WNS Foundation (NL1 capture + NL2 weaving)

The bottom of the narrative pipeline: ingesting pre-generated NPC dialogue into NL1, and producing the first thread fragments via LLM weaving at NL2. Every LLM layer in WNS is real — no template tier. **NL1 is now dialogue-only** (v4).

- **P1.1** **Separate WNS SQLite database** (`world_narrative.db`) bootstrapped; save/load coordinated with `world_memory.db`.
- **P1.2** **Narrative tag taxonomy** — new standalone `narrative-tag-definitions.JSON` + new `NarrativeTagLibrary` (mirror of `TagLibrary`, not an extension). Includes narrative address prefixes (`thread:`, `arc:`, `witness:`) registered into a WNS-specific `ADDRESS_TAG_PREFIXES` list.
- **P1.3** NL layer storage — SQLite tables `nl1_events` through `nl7_events` + tag junctions + address indexes. All in `world_narrative.db`.
- **P1.4** NL1 ingestion pipeline:
  - Deterministic mention extractor (no LLM) that runs over NPC speech-bank text at generation time.
  - Hook on NPC speech-bank generation (post-generation, pre-publish) — extracts mentions, writes NL1 events.
  - Does NOT subscribe to WMS events — WMS events are read by NL2+ during weaving, not captured into NL1.
- **P1.5** NL2 weaving LLM — given lower-layer input at a locality, produce threads + locality narrative. Prompt fragments: `narrative_fragments_nl2.json` in WNS-specific prompt directory. BackendManager task: `"wns_layer2"`.
- **P1.6** `NLTriggerManager` — parallel to `TriggerManager`. Every-N-events-per-layer-per-address trigger buckets.
- **P1.7** `WorldNarrativeSystem` facade (sibling to `WorldMemorySystem`) with initial methods: `initialize()`, `get_instance()`, `ingest_dialogue(...)`, `query_threads(address)`, `get_layer_summary(layer, address)`.

Exit criteria: a play session generates NL1 entries from NPC speech-banks; NL2 fires weave at least one thread fragment per active locality. Every NL2 fire writes a valid row with address + content tags. Threads are queryable by address.

---

### P2 — WNS Weaving Layers (NL3-NL5)

The middle of the pipeline: weaving at district → region → nation scopes. All layers LLM. **Bottom-up reconciliation prompt** in every weaving call (§4.3b) — lower-layer narrative rides in the prompt with instructions to reconcile.

- **P2.1** NL3 weaving LLM — per district. Reads NL2 threads + prior NL3 for same address (supersession) + WMS L3 same-address input. Prompt fragments: `narrative_fragments_nl3.json`.
- **P2.2** NL4 weaving LLM — per region. Reads NL3 + selected NL2 + WMS L4.
- **P2.3** NL5 weaving LLM — per nation. Reads NL4 + selected NL3 + WMS L5.
- **P2.4** Address-tag immutability enforced at every layer — reuse `partition_address_and_content()` pattern from `geographic_registry.py`.
- **P2.5** MockBackend fallback for offline dev (via the P0 Fixture Registry — every layer has a canonical mock).
- **P2.6** Each weaving prompt explicitly includes reconciliation instruction — output must not contradict lower-layer state in same address.

Exit criteria: a play session produces narrative state at all three scopes (district, region, nation) for areas with enough activity. Narrative reads coherently across layers (region summary references thread fragments that lower layers produced). No contradictions between NL2/NL3/NL4/NL5 at overlapping addresses.

---

### P3 — WNS Top Layers (NL6 + NL7)

The top of the pipeline. **v4 note:** P3 publishes narrative events for observability and dev UI only — **not** as a WES trigger. WES triggering design is separate (WNS decides when, not auto-on-every-fire).

- **P3.1** NL6 weaving LLM — nation-to-world seams. Reads NL5 + WMS L6. `narrative_fragments_nl6.json`.
- **P3.2** NL7 embroidery LLM — world narrative embroidery. Reads NL6 + WMS L7. `narrative_fragments_nl7.json`.
- **P3.3** Publish `WNS_LAYER_FIRED` events on GameEventBus per layer fire (for dev observability only — no WES subscription).
- **P3.4** `WorldNarrativeSystem.get_layer_summary(layer=N, address=A)` — canonical query API for internal WNS consumers and any dev tools.
- **P3.5** Dev UI — F-key overlays showing current narrative state per layer (F9 for world-narrative NL7, F10 for region selector). Sanity check for playtesters.

Exit criteria: pipeline fires at all layers NL2-NL7; each layer's output is queryable; dev UI displays the current NL7 embroidery.

---

### P4 — Content Registry

Coordination layer for generated content. No generators yet.

- **P4.1** Registry SQLite tables (§7.2): per-tool tables + unified `content_xref`.
- **P4.2** Registry API: `stage_content`, `commit`, `rollback`, `list_live`, `list_staged_by_plan`, `find_orphans`, `counts()`.
- **P4.3** **Commit writes generated JSON files** (v4 — Q4 "both") alongside flipping staged→live. One file per tool type per commit batch, named `<tool>-generated-<timestamp>.JSON` in a generated subdirectory.
- **P4.4** Integration with existing databases — `MaterialDatabase`, `EnemyDatabase`, etc. re-read their directory globs on commit notification.
- **P4.5** Save/load wiring — registry state persists atomically with the rest of the save.
- **P4.6** Pass 1 + Pass 2 orphan detection (§7.3). Pass 3 (nightly scrub) deferred per v4.

Exit criteria: can manually stage a fake material, commit it, see the JSON file written and then see it in `MaterialDatabase.get_instance().materials`, roll back via API (registry cleared, JSON file deleted).

---

### P5 — WES Deterministic Shell (no LLM)

The whole WES pipeline except the LLM calls. Proves the plumbing before any prompt tuning. **Bundle is a first-class dataclass here** (schema sketched in P0, finalized in P5).

- **P5.1** **`WESContextBundle` full dataclass** (§4.7, bundle sketch from P0.6 promoted to first-class). Delta + narrative context + directive, with serialization.
- **P5.2** `WESPlanStep` + `WESPlan` dataclasses (§5.2).
- **P5.3** `ExecutorSpec` dataclass (§5.3). Plus XML batch parser (hubs emit XML-tagged batches).
- **P5.4** Topological plan dispatcher — deterministic code that walks a plan and invokes tiers in order.
- **P5.5** **Parallel executor_tool fan-out** — dispatcher uses `AsyncLLMRunner` to run all specs from a hub batch concurrently.
- **P5.6** Staging + atomic commit/rollback flow.
- **P5.7** Final verification pipeline (§5.6): orphan scan, duplicate scan, completeness.
- **P5.8** Observability scaffolding — `llm_debug_logs/wes/<plan_id>/` directory structure, `bundle.json` + per-tier logging.
- **P5.9** **Supervisor scaffolding** — log-tap + interface for the supervisor LLM, even if full supervisor integration waits for P6. Supervisor is not yet invoked; the plumbing exists so P6 plugs in cleanly.
- **P5.10** Stub `execution_planner` + stub `execution_hub` + stub `executor_tool` — use the P0 Fixture Registry to return canonical mocks. End-to-end run against bundles+mocks only, no real LLM.

Exit criteria: a hardcoded stub bundle drives a stub plan with 2-3 stub tool steps end-to-end, stages content, commits, and the content is live in the relevant databases. Rollback also works. Bundle serializes cleanly.

---

### P6 — WES `execution_planner` + Supervisor (Tier 1 LLM + cross-tier)

Replace the stub planner with a real LLM call. **Integrate the supervisor** (v4 — must exist before P7 ships tools).

- **P6.1** `ExecutionPlannerAssembler` — takes a `WESContextBundle` + game-awareness + task-awareness, produces the planner prompt. No live queries.
- **P6.2** Planner LLM integration — `BackendManager.generate(task="wes_execution_planner")`. Ollama default; cloud (Claude) as escalation on retry.
- **P6.3** Prompt fragments: `prompt_fragments_wes_execution_planner.json`. **Includes scope-discipline section keyed by `firing_tier`** (§5.8).
- **P6.4** WNS-side: implement the WNS-to-WES bundle assembler and the WNS-side call-WES trigger (driven by the weaving-LLM self-flag, Q10 Candidate D).
- **P6.5** **Supervisor LLM integration** (v4) — observes planner I/O and future tier I/O. Rerun authority only. `BackendManager.generate(task="wes_supervisor")`. Prompt fragments: `prompt_fragments_wes_supervisor.json`. Must ship before P7.

Exit criteria: WNS layer fires → weaving LLM flags call-WES → WNS assembles bundle → planner runs → produces a valid plan → stub hub/tool tiers complete it → supervisor reviews → commit. Plans coherent with bundle's directive.

---

### P7 — First Tool Mini-Stack: `materials`

End-to-end LLM generation for one tool type. Proves the hub + executor_tool pattern. **Hub is non-adaptive** (v4): emits XML-tagged batch in one pass; executor_tools run in parallel.

- **P7.1** `execution_hub_materials` — Tier 2 LLM. Takes a plan step + bundle slice. Emits `<specs>...</specs>` XML-tagged batch. Code parses into `List[ExecutorSpec]`. Prompt fragments: `prompt_fragments_hub_materials.json`.
- **P7.2** `executor_tool_materials` — Tier 3 LLM. One spec → one JSON material. Prompt fragments: `prompt_fragments_tool_materials.json`. Structured output via Ollama grammar if available.
- **P7.3** Parallel dispatch wiring — `AsyncLLMRunner` fans out N specs, collects all outputs.
- **P7.4** BalanceValidator stub (§9.Q3) — tier multiplier range check.
- **P7.5** Dev CLI `debug_create_material(plan_step, bundle_slice)` — bypass planner, test hub + executor_tool in isolation.
- **P7.6** Supervisor reviews the full plan → commit path.

Exit criteria: bundle → planner plan → materials mini-stack fans out specs → parallel executor_tools → supervisor review → commit → gathering the relevant node yields the new material. Real end-to-end play.

---

### P8 — Tool Expansion

Remaining 4 tools. Each follows the P7 pattern — non-adaptive hub with XML batch, parallel executor_tools.

- **P8.1** `execution_hub_nodes` + `executor_tool_nodes` — cross-ref to materials. Proves the cross-reference path.
- **P8.2** `execution_hub_skills` + `executor_tool_skills` — compose from existing tags only (no tag invention).
- **P8.3** `execution_hub_titles` + `executor_tool_titles` — cross-ref to StatTracker stats + skills.
- **P8.4** `execution_hub_hostiles` + `executor_tool_hostiles` — capstone; cross-refs to materials (drops), skills (enemy skills), biomes, factions.

Exit criteria per tool: single-tool plans produce schema-valid, cross-ref-clean content. Full test: 4-step plan with all 4 new tools runs end-to-end; supervisor reviews without triggering rerun.

---

### P9 — Multi-Step Plans + Full Observability

Unlock the planner to produce multi-tool plans; ship the observability tools; finalize supervisor tuning.

- **P9.1** Planner prompt updated to allow multi-step plans. Cross-tool dependency slots validated.
- **P9.2** Topological dependency execution stress-tested (plans with 5+ steps, 2+ tools, parallel specs per step).
- **P9.3** Cross-plan diversity — registry queries (recent additions by type/biome/tier) pre-included in bundle by WNS, so planner avoids repetition without live queries.
- **P9.4** **Supervisor full form** — if integrated as a minimal cut in P6, it gets its full ruleset here. Common-sense review heuristics tuned; rerun budget finalized (likely 1-2).
- **P9.5** **Metrics dashboard** (v4 additions):
  - Plans/hour, tool success %, orphan block rate, plan abandonment rate.
  - **Supervisor rerun rate** (how often supervisor catches a problem vs clean pass).
  - **Graceful-degrade event counts** (per subsystem).
  - Tier usage by backend (Ollama vs Claude vs Mock vs Fixture).
- **P9.6** Retrospective thread detector — offline tool that clusters NL2-NL5 supersession chains into named threads for dev-side visualization.
- **P9.7** "Why this output?" tracer — given a generated content_id, walk backwards through the logs to show the bundle, the planner plan, the hub specs, and the executor_tool prompt + supervisor review that produced it.

Exit criteria: 10-minute play session produces ≥1 multi-tool plan that commits successfully. A developer can pick any generated item in-game and get the full provenance chain from logs alone.

---

### Deferred — Explicit Scope Exclusions (v4)

- **Quest generation** (§6.3.6) — stays deferred. When built, tool gets minimal context (handed-down instructions from layered LLMs; no broader narrative context).
- **Ecosystem integration** — **demoted from "deferred tool" to "maybe a WNS context source if there's time."** Not a WES tool. Low priority either way.
- **Player Intelligence (Part 3)** — WES and WNS run fine without it. Optional addition via a `player_profile` field on the task-awareness block when Part 3 lands.
- **In-hub sequential executor_tool feedback** — **dissolved** (v4). Hubs always fan out in parallel; no sequential loop to defer.
- **Developer injection tool** — **removed from scope** (v4). May return later as dev infrastructure; not a live gameplay trigger.
- **Session-boot catch-up narrative** — **removed** (v4). Game continues on load as if nothing happened.
- **WES self-request** — **removed** (v4). Violates unidirectional flow.
- **Live conversation (NPC dialogue)** — deferred. The v4 commitment is pre-generated speech-banks with bounded interaction cycles. Live conversation is a future capability.
- **Parallel WES plans from different WNS firings** — §6.7. Still deferred; single-plan-at-a-time in v1.
- **Replacing `llm_item_generator` with AsyncLLMRunner** — leave alone until it needs touching.
- **WMS layers going fully LLM** — assumed to happen once the tuned model lands; WNS is designed for the post-transition world, so no WNS change is needed.
- **Distance-decay tuning per firing tier** — shallow-going-outward principle confirmed (§8.8). Specific depths TBD in playtest.

---

## Appendix: Cross-Cutting Decisions (CC1-CC9)

Decisions that ripple across multiple sections. Collected here so anyone reading the doc can see the full set of v4 invariants in one place.

### CC1 — Supervisor LLM

- New role, not in v3.
- Sees all WES inputs and outputs (planner bundle, plan; hub batches, executor_tool outputs).
- Common-sense checker. **NOT** a balance validator. **NOT** a schema checker. **NOT** a cross-reference verifier.
- Authority: trigger a WES rerun with adjusted instructions prepended to the next planner call. Nothing else.
- Consumes the same observability logs all other LLMs produce. No separate observability pipeline.
- Must be integrated before any tool ships (P6 or P6.5 at latest; blocks P7).
- Rerun budget: 1-2 per plan (TBD, §9.Q12), then hard-abandon.
- **Touches**: §2, §5, §6, §8, §10.

### CC2 — Context bundle (the central artifact)

- Load-bearing for the entire v4 architecture.
- Assembled by WNS, consumed by WES's planner (propagated via code to hub and executor_tool as-needed).
- Three parts:
  1. **Delta** — dialogue + events since WNS's last firing at this layer/address.
  2. **Narrative context** — current narrative state at firing layer + parent addresses, shallow-going-outward.
  3. **Directive** — WNS's high-level instructions on what WES should create (WES bundles only).
- First-class dataclass formalized in P5.
- Schema sketch in P0 so downstream phases build against a stable contract.
- Replaces all live-query paths v3 described.
- **Touches**: §2, §4, §5, §6, §8, §10.

### CC3 — Graceful-degrade discipline

- Every subsystem graceful-degrades on failure.
- Every graceful-degrade event emits a structured entry to the debug log (`llm_debug_logs/graceful_degrade/`).
- WES failures additionally surface visibly on-screen (persistent HUD indicator).
- No crashes anywhere in the system. Crashes are bad in general.
- **Touches**: §1, §2, §5, §10.

### CC4 — Pseudo-mock infrastructure

- Every LLM in the system has a fixture code + canonical sample I/O pair.
- The full pipeline must be runnable end-to-end against fixtures only, no real LLM required.
- P0 infrastructure (LLM Fixture Registry, §10.P0.3).
- Enables CI-level testing and offline dev iteration.
- **Touches**: §1, §10, every LLM role in §2.7.

### CC5 — WNS and WMS are sibling systems, completely separate

- Separate SQLite databases (`world_memory.db` + `world_narrative.db`).
- Separate tag taxonomies (two tag files: `tag-definitions.JSON` + `narrative-tag-definitions.JSON`).
- Separate prompt fragment files (distinct directories).
- Shared infrastructure patterns (address-tag immutability, layered lazy triggers, BackendManager routing) are reused **by reference**, not by shared code ownership.
- Save/load coordinates both files atomically.
- **Touches**: §4, §7, §9.Q5, §9.Q6, §10.

### CC6 — Pre-generated NPC dialogue is committed, not ideal

- Dialogue is generated once per NPC per content-update window and stored.
- Interaction cycle is bounded: greeting → accept quest → turn-in → closing line. No live conversation.
- Mention extraction runs at speech-bank generation time, not at interaction time, and is deterministic.
- Live conversation is a future capability, deferred.
- v3's framing of "ideal vs. attainable" is out — this is the commitment.
- **Touches**: §1, §4, §8.

### CC7 — Tiered WNS/WES firings

- WNS fires at every layer NL1 through NL7.
- WES responds at every tier when WNS calls it; scope discipline is carried entirely in the planner's prompt (no architectural permissions matrix).
- **L7 firings** have broad authorization (NPCs, quests, chunks, titles, skills, cross-nation content).
- **L3 firings** have narrow authorization (NPCs, quests, affinity changes).
- In static worlds, low-tier firings keep the game fresh. In volatile worlds, L7 firings carry the heavy lifting.
- **Touches**: §3, §4, §5, §6, §8, §10.

### CC8 — WNS is the orchestrator

- WNS is the orchestrator between narrative and execution.
- WES is a pure execution engine.
- WNS decides when to call WES.
- WNS assembles the context bundle.
- WNS authors the directive.
- WES runs what WNS tells it to run.
- No backward direction (WES → WNS clarification) exists. Unidirectional flow is a structural invariant.
- **Touches**: §3, §4, §5, §8.

### CC9 — Hubs are dispatchers, not orchestrators

- Hubs have little narrative authority (reduced from v3).
- Hubs batch all executor_tool calls in XML tags and fan out in one pass.
- No sequential feedback within a plan step.
- Executor_tools within a plan step are always parallelizable.
- Narrative flavor is owned by WNS (bundle author) and the planner (decomposer); hubs pass it through.
- **Touches**: §5, §6, §9.Q9 (dissolved), §10.

---

## Appendix: Items Still Outstanding (Non-Blocking)

Items flagged as "TBD in playtest" or "resolve during detailed phase design." Not blocking v4 rewrite; captured as open design questions.

- **Specific N values** for every-N-events-per-layer-per-address triggers. Playtest-tuned.
- **"Certain effect" trigger condition** for WNS → WES call (§9.Q10). Lean: weaving-LLM self-flag; confirm in playtest.
- **Specific narrative-context-depth rules** for bundles at different firing tiers. Shallow-going-outward principle confirmed; specific depths TBD.
- **Supervisor rerun budget and invocation heuristics** (§9.Q12). Lean: 1-2 reruns; resolve in P6/P6.5.
- **Whether directive authoring is part of the weaving LLM's output or a separate WNS-side LLM call.** Lean toward former; switch only if directives prove inadequate.
- **Context bundle dataclass — specific field shapes** (§9.Q11). Lean sketch in P0; finalized in P5.
- **Hub XML batch prompt format** — whether XML is the best grammar for structured-output decoding in Ollama for each model choice. Playtest will tell.

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
2. Read §2 (bundle-mediated unidirectional flow) and §5 (three-tier + supervisor) for the system shape. §8 if you're working on anything that assembles LLM context — remember: **only WNS reads canonical stores; WES consumes the bundle**.
3. Read the **Cross-Cutting Decisions appendix (CC1-CC9)** — these are the v4 invariants that ripple across multiple sections.
4. The roadmap in §10 is the *dependency* order, not a ship schedule. P0 is still load-bearing — don't skip the LLM Fixture Registry, graceful-degrade logging, on-screen surfacing, or bundle schema sketch. Later phases assume them.
5. Quest generation and ecosystem integration are explicitly deferred. Live NPC conversation is also deferred — v4 commits to pre-generated speech-banks with bounded interaction cycles (CC6).
6. Every LLM call must: go through `BackendManager`, be registered in the LLM Fixture Registry, log to `llm_debug_logs/`, and graceful-degrade via the structured logger. These are the v4 non-negotiables.
7. The Content Registry (§7) is the glue. On commit, write BOTH the registry rows AND the generated JSON files (v4 Q4 resolution).
8. Supervisor LLM (CC1) is common-sense-only with rerun authority. It is NOT a balance/schema/cross-ref validator — those stay deterministic code.
9. "The true difficulty is the information." When in doubt, re-read §8 before reaching for another LLM call. The bundle is the compression mechanism; keep it well-assembled.

