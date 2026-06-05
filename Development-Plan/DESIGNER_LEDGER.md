# Designer Ledger — Living World

## What this document is

The Living World has three systems that work in sequence:

- **WMS — World Memory System.** Watches gameplay, writes down what happened, tags each event, rolls events up to bigger geographic scopes (locality → district → region → province → nation → world).
- **WNS — World Narrative System.** Reads WMS events and writes them up as story — threads, arcs, tone, emerging factions. When a pattern wants new content, WNS emits a directive.
- **WES — World Executor System.** Takes a WNS directive and produces actual game content — a new monster, a new biome, a new quest. Writes JSON the game can load.

This document tracks every place where **designer judgment** is needed to take the system from "scaffold runs end-to-end" to "real game with real content." Anything the code can decide on its own (parsers, schemas, file paths) is excluded — those pass or fail mechanically.

Status legend used below: **Works** (verified end-to-end), **Half-built** (specific known gap), **Stub** (functional shape, designer authoring needed), **Not started**, **Locked** (do not edit — code depends on it).

---

## State of the build

### Works today
| What | Notes |
|---|---|
| WMS layers 1-7 + all 33 evaluators | 93 passing tests; canonical event catalog |
| WMS prompts L2-L7 | Designer-reviewed. Factual chronicle voice locked in. |
| Faction system (Phase 2+) | NPC/player affinity tracking; prompt UI wired |
| NPC dialogue runtime | F-press uses speechbank (greeting → idle barks → quest offer → quest complete) |
| Chunk generation → reload → game-spawn | Full pipeline, E2E test passing |
| NPC + quest generation → reload | Same; quest lifecycle E2E test passing |
| Prompt Studio | 33-task editor; simulator with fixture/mock/real-LLM modes; schema validator; coverage report |
| F12 overlay + `WES_VERBOSE` env | Live observability of WMS → WNS → WES pipeline events |
| Request Layer | Code-driven cross-reference fix (skips planner+hub round-trip) |
| Real-LLM safety gate | `WES_REQUIRE_REAL_LLM=1` prevents silent fallback to mock during playtest |
| Bundle round-trip | 8 tests confirm WNS → WES schema fidelity |
| BalanceValidator (stub) | Rejects values outside [0.5×, 2×] of tier nominal — placeholder ranges |

### Half-built — known specific gaps

- **Five content types can't hot-reload.** Generated materials, hostiles, nodes, skills, and titles land on disk but the in-game database doesn't see them until restart. The reload-method pattern exists (used by chunks and NPCs); just needs to be repeated for 5 singletons. Developer task, blocks designer playtest of those 5 content types.
- **WNS prompts have new data shape but the code doesn't read it yet.** The narrative weaver prompts were just rebuilt as tag-indexed fragments that reuse the WMS tag library. The runtime code currently reads only the top-level system blurb, missing the per-layer scope rules, WES invocation rules, and tag-specific narrative context. **Fixing in this commit.**
- **BalanceValidator placeholder ranges.** The guard rail works; the actual ranges are designer-tunable but currently a guess.

### Not started
- Hub dependency resolution (when generating a quest needs a hostile that doesn't exist, fire the hostile tool first).
- WNS affinity modifier tool (lightweight directive parser for faction standing shifts).
- NPC dynamic context registry read-path queries (write path works).

---

## What needs your judgment

### 1. The 33 LLM prompts

Each is a JSON file in `world_system/config/`. You edit the system prompt and the user template; the output schema is locked because the runtime parses it. Edit them in Prompt Studio (`python tools/prompt_studio_main.py`).

| Group | Count | State | What to author |
|---|---|---|---|
| WMS layers L2-L7 | 6 | Done | — |
| WNS narrative weavers NL2-NL7 | 6 | Stub | Per-layer voice and scope. NL7 (world narrative) is the substrate the planner reads — highest impact. |
| WES Execution Planner | 1 | Stub | The single most leveraged prompt in the system. Its `scope_by_firing_tier` section defines what kind of content can be generated when a small-scale event fires vs. a large-scale one. The whole architecture rests on prose. |
| WES Hubs | 8 | Stub | One per content type (hostiles, materials, nodes, skills, titles, chunks, npcs, quests). Hubs are the middle tier — they read the planner's request and decide *which specific things* to ask for. Designer prose sets the flavor. |
| WES Tools | 8 | Stub-with-shape | Tools write the actual content JSON. The materials tool is the most authored reference; others follow the pattern. Needs voice polish and naming-convention prose. |
| Supervisor | 1 | Stub | Reviews each generation batch, decides commit/rerun/reject. Criteria need refinement. |
| Quest Reward Pregen + Adapt | 2 | Stub | First turns the writer's prose hints into concrete rewards at quest accept. Second adjusts at turn-in based on how the player completed the quest. |
| NPC Dialogue | 1 | Stub | Currently built inline in `NPCMemoryManager`. Decide whether to externalize. |

### 2. The narrative tag vocabulary

Tags are short strings like `tier:3`, `domain:combat`, `species:wolf_grey` that the game attaches to events. They drive everything: which prompts get assembled, which evaluators fire, which content is allowed. The WMS tag vocabulary is locked; WNS adds five new categories:

- `thread_stage` — where in an arc a story sits (inciting_incident → coda)
- `tone` — its mood (hopeful, ominous, mundane, grim, …)
- `relationship` — alliances and rivalries between actors
- `narrative_domain` — kind of story (political, mystical, economic, …)
- `agency` — who's driving (player, npc, faction, world)

Each has a starter value set. You confirm, extend, or rename.

File: `world_system/config/narrative-tag-definitions.JSON`.

### 3. World content configuration

Five designer-owned JSON files in `world_system/config/`. Currently sketched; you fill out.

- `affinity-defaults.json` — faction standing baselines per nation. 4 nations sketched (stormguard, blackoak, shattered_isles, verdant_reaches); more if you want them.
- `faction-archetypes.json` and `faction-definitions.json` — base archetypes and concrete factions.
- `npc-personalities.json` — personality archetypes that speechbanks reference for tone.
- `ecosystem-config.json` — resource regeneration and population dynamics.
- `geo_chunk_dispatch.json` — biome string → chunk type mapping (15 entries; add as new biomes appear).

### 4. Numbers to tune in playtest

Real values commit when you see the system in motion. Current values are guesses.

- **Cascade threshold = 3.** How often each narrative layer fires. With 3, NL2 (locality) fires after 3 WMS events at one locality; NL3 (district) after 3 NL2 fires at one district; geometric upward. Lower for chatty world, higher for rationed.
- **Caps per weaving run.** Threads per fragment, `<WES>` calls per run, new proper nouns the LLM can coin per fragment / per run.
- **Character budgets** for the WMS-events context block fed to each weaver.
- **Supervisor rerun budget = 2.** Reruns per plan before giving up.
- **Quest reward adaptation window = [0.5×, 1.5×]** of original reward.
- **BalanceValidator ranges per tier per stat.** Currently `[0.5×, 2×]` of nominal — designer commits the real numbers.
- **Backend routing.** Which LLM tasks pay for Claude vs. run on local Ollama. Currently load-bearing tasks (planner, world narrative, NPCs, quests, quest reward pregen) use Claude; mechanical tasks (hubs, simple tools, supervisor) use Ollama. Adjust as quality demands.

### 5. Information flow — does each tier actually receive what it needs?

For each handoff between layers, confirm the receiving prompt sees what it asks for. This is verification work, not authoring.

- WMS → WNS: is the events slice enough for the locality weaver to ground itself?
- Inside WNS: does each layer see its parent + grandparent at appropriate depths? Are open threads surfaced correctly?
- WNS → WES: does the bundle carry firing tier, severity, scope hint, and narrative context intact?
- Planner → Hubs: do hubs receive the planner's instruction with intent and dependencies, or are some fields silently dropped?
- Hubs → Tools: do tools receive flavor hints, cross-reference hints, and hard constraints from the spec?
- Tools → Game: when a generated piece lands, does the running game see it on the next tick? (Blocked on the 5 missing reload methods above.)
- Quest reward adapter: at turn-in, does the adapter receive original prose, play time, urgency, and party state?

---

## What's locked — do not edit

The code or sacred content depends on these. A JSON change here breaks the pipeline.

- **Address tags** (`thread:`, `arc:`, `witness:`, `locality:`, `district:`, `region:`, `province:`, `nation:`, `world:`). Only the server writes these.
- **Game formulas** — damage pipeline, EXP curve, tier multipliers, stat scaling.
- **Sacred content files** in `items.JSON/`, `recipes.JSON/`, `Skills/`, `progression/`, `Definitions.JSON/`. Generated content always goes to `<name>-generated-<timestamp>.JSON` siblings; sacred files are never modified. Drop the generated files to revert to base.
- **Resource density buckets** (very_low / low / moderate / high / very_high → weights 0.5 / 0.75 / 1.0 / 2.0 / 3.0). Bucket picked per content; weights not negotiable.
- **Content registry table shape, WES three-tier topology, prompt output schemas** — the runtime parses these.
- **Backend routing structure** — values tunable, structure not.

---

## Suggested order

1. **Close the broken half.** Add the 5 missing `reload()` methods (developer task) and finish the WNS assembler code change. Without these, designer prose for the affected content types can't be validated end-to-end.
2. **Author the keystone prompts.** WES Planner's `scope_by_firing_tier`, then WNS NL7 (world narrative), then the narrative tag vocabulary, then the 8 hub prompts.
3. **Verify information flow** tier-by-tier — make sure each prompt receives what it asks for.
4. **Author the 8 executor tool prompts** — tone, naming, voice.
5. **Calibrate in playtest** — cascade threshold, weaver caps, distance budgets, supervisor rerun budget, BalanceValidator ranges, backend routing.
6. **Fill out world content configs** — factions, NPCs, affinity, ecosystem, biome dispatch.
7. **Polish** — supervisor criteria, quest reward voice, NPC dialogue refinements.

---

## Reference

- Architecture spec: [`WORLD_SYSTEM_WORKING_DOC.md`](WORLD_SYSTEM_WORKING_DOC.md)
- Scaffold-time placeholder snapshot: [`PLACEHOLDER_LEDGER.md`](PLACEHOLDER_LEDGER.md)
- Tool contract audit: [`TOOL_CONTRACT_AUDIT.md`](TOOL_CONTRACT_AUDIT.md)
