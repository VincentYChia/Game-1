# Placeholder Furnishing Worksheet

**Companion to**: [`PLACEHOLDER_LEDGER.md`](PLACEHOLDER_LEDGER.md) (the full reference)
**Purpose**: Action-oriented triage of everything the v4 WNS/WES scaffold wrote in as placeholder. Tick each item as you furnish it. Ledger sections preserved; this doc just makes them tackleable.
**Last Updated**: 2026-04-24

---

## How to use this

Each section below maps 1:1 to a ledger section. Each has:

- **What's there now** — the concrete current state (file paths + values)
- **What you decide** — the actual question
- **Blocking?** — whether placeholders are gating anything

Mark `[x]` when furnished. Priorities at the end if you want a tackle order.

---

## §1 — LLM Fixture Registry (24 fixture codes)

**What's there**: `world_system/living_world/infra/llm_fixtures/builtin.py`. Every LLM role has a canonical system prompt + user prompt + response. Pipeline runs end-to-end on these with MockBackend routing.

**What you decide**: For each fixture, replace placeholder prompt text and canonical response with what you actually want.

- [ ] `wes_execution_planner` — plan quality drives everything downstream
- [ ] `wns_layer7` (embroidery) — world narrative the planner reads
- [ ] `wes_hub_hostiles` — flavor/diversity for hostiles
- [ ] `wes_hub_materials` — flavor for materials
- [ ] `wes_hub_nodes` — flavor for nodes
- [ ] `wes_hub_skills` — flavor for skills (MUST compose from existing tags only)
- [ ] `wes_hub_titles` — flavor for titles
- [ ] `wns_layer2` — locality weaver
- [ ] `wns_layer3` — district weaver
- [ ] `wns_layer4` — region weaver (note: `call_wes: true` example placeholder lives here)
- [ ] `wns_layer5` — nation weaver
- [ ] `wns_layer6` — nation-to-world seam weaver
- [ ] `wes_tool_hostiles` — JSON artifact generator
- [ ] `wes_tool_materials` — JSON artifact generator
- [ ] `wes_tool_nodes` — JSON artifact generator
- [ ] `wes_tool_skills` — JSON artifact generator
- [ ] `wes_tool_titles` — JSON artifact generator
- [ ] `wes_supervisor` — common-sense checker criteria
- [ ] `npc_dialogue_speechbank` — personality-specific speech-bank prompt
- [ ] `wms_layer3-7` (5 fixtures) — mirror shipped WMS prompts into fixture registry for parity (lower priority)

**Constraint**: If you change a JSON shape (e.g. add a field to executor_tool output), update the parser too.

**Blocking?**: Not code-blocking (pipeline runs on placeholders), but gates real gameplay quality.

---

## §2 — Context bundle schema

**What's there**: `world_system/living_world/infra/context_bundle.py` — 8 dataclasses. Main shape is locked: `WESContextBundle = NarrativeDelta + NarrativeContextSlice + WNSDirective`.

**What you decide**: Which loose `Dict[str, Any]` fields should harden into typed dataclasses.

- [ ] `NL1Row.extracted_mentions` — is `{entity, claim_type, significance}` enough, or do you want a dataclass?
- [ ] `ThreadFragment.relationship` — `open/continue/reframe/close` — add `fork/merge`?
- [ ] `NarrativeContextSlice.parent_summaries` keying — currently `"{layer}:{address}"` — keep or richer?
- [ ] `WNSDirective.scope_hint` — keep free-form or typed?
- [ ] `BundleToolSlice.recent_registry_entries` — type per-tool?

**Blocking?**: No. Can harden incrementally as prompts stabilize.

---

## §3 — Graceful-degrade constants

**What's there**: `world_system/living_world/infra/graceful_degrade.py`. `MAX_BUFFER=256`, `DEFAULT_LOG_DIR=llm_debug_logs/graceful_degrade`, severities = `{info, warning, error}`. WES failures (severity=error) fire the on-screen surface-sink.

**What you decide**:

- [ ] Buffer size (256 plenty for dev; different for prod?)
- [ ] Severities — need a `critical` / `fatal` tier?
- [ ] Surface-sink threshold (error today; drop to warning for dev?)

**Blocking?**: No. Sensible defaults shipped.

---

## §4 — WNS trigger thresholds (every-N per layer per address)

**What's there**: `world_system/config/narrative-config.json`. Per-layer N values (all placeholders):

| Layer | N | Scope |
|---|---:|---|
| NL2 | 5 | per locality |
| NL3 | 5 | per district |
| NL4 | 8 | per region |
| NL5 | 12 | per nation |
| NL6 | 15 | world-wide |
| NL7 | 20 | world-wide |

**What you decide**: Playtest-tuned. Run a session, watch fire rates, edit JSON, restart. No code changes.

- [ ] NL2 N tuned
- [ ] NL3 N tuned
- [ ] NL4 N tuned
- [ ] NL5 N tuned
- [ ] NL6 N tuned
- [ ] NL7 N tuned

**Blocking?**: No. Placeholder values run fine.

---

## §5 — Narrative tag taxonomy

**What's there**: `world_system/config/narrative-tag-definitions.JSON`. Starter categories: `thread_stage` (inciting → rising → complication → turning_point → falling → resolution → coda), `tone` (hopeful / ominous / mundane / …), relationship tags.

Address prefixes `thread:` / `arc:` / `witness:` are **locked** (code-level invariant).

**What you decide**: The full narrative tag vocabulary. Categories + their values.

- [ ] `thread_stage` values finalized
- [ ] `tone` values finalized
- [ ] Relationship categories finalized
- [ ] Any new categories needed?

**Blocking?**: No, but narrative LLMs can only compose from these.

---

## §6 — Prompt fragment files (18 files)

**What's there**: 18 prompt files in `world_system/config/`, each ~17-25 lines. Structure: `_meta / _core / _output`. `_core.system` + `_core.user_template` are placeholder text.

| Prefix | Count | Purpose |
|---|---:|---|
| `narrative_fragments_nl2` through `nl7` | 6 | WNS weaving prompts per layer |
| `prompt_fragments_hub_<tool>` | 5 | WES tier 2 hub prompts |
| `prompt_fragments_tool_<tool>` | 5 | WES tier 3 executor_tool prompts |
| `prompt_fragments_wes_execution_planner` | 1 | WES tier 1 planner prompt |
| `prompt_fragments_wes_supervisor` | 1 | Supervisor common-sense checker |

**What you decide**: Real prompts for each file. (Largely overlaps with §1 fixture work — same texts, different layer.)

- [ ] `narrative_fragments_nl2.json`
- [ ] `narrative_fragments_nl3.json`
- [ ] `narrative_fragments_nl4.json`
- [ ] `narrative_fragments_nl5.json`
- [ ] `narrative_fragments_nl6.json`
- [ ] `narrative_fragments_nl7.json`
- [ ] `prompt_fragments_hub_hostiles.json`
- [ ] `prompt_fragments_hub_materials.json`
- [ ] `prompt_fragments_hub_nodes.json`
- [ ] `prompt_fragments_hub_skills.json`
- [ ] `prompt_fragments_hub_titles.json`
- [ ] `prompt_fragments_tool_hostiles.json`
- [ ] `prompt_fragments_tool_materials.json`
- [ ] `prompt_fragments_tool_nodes.json`
- [ ] `prompt_fragments_tool_skills.json`
- [ ] `prompt_fragments_tool_titles.json`
- [ ] `prompt_fragments_wes_execution_planner.json` (see §7 for the scope-by-tier section specifically)
- [ ] `prompt_fragments_wes_supervisor.json`

**Constraint**: Schema sections (`_output`) must stay in sync with parser code.

---

## §7 — Planner scope-by-firing-tier ⚠️ CRITICAL

**What's there**: `prompt_fragments_wes_execution_planner.json` under `_core.scope_by_firing_tier`, keyed 2-7 (one placeholder string per tier).

| Firing tier | Placeholder rule |
|---|---|
| NL2 (locality) | "small flavor items only" |
| NL3 (district) | "small material/node, NPC dialogue updates" |
| NL4 (region) | "hostiles/materials tied to biome; no new nations" |
| NL5 (nation) | "cross-region, new faction interests" |
| NL6 (seams) | "cross-national dynamics" |
| NL7 (world) | "anything, world-shift included" |

**Why this matters**: The whole v4 architectural commitment is *scope-via-prompt, not permissions-matrix*. Get this text sharp and the system is configurable via prompt edits. Get it mushy and the LLM over- or under-generates.

- [ ] NL2 scope prose finalized
- [ ] NL3 scope prose finalized
- [ ] NL4 scope prose finalized
- [ ] NL5 scope prose finalized
- [ ] NL6 scope prose finalized
- [ ] NL7 scope prose finalized

**Blocking?**: Soft-blocking — pipeline works, but tier discipline is only as good as this prose.

---

## §8 — Supervisor rerun budget & heuristics

**What's there**: `WESOrchestrator.DEFAULT_RERUN_BUDGET = 2`. Prompt in `prompt_fragments_wes_supervisor.json` covers "does content match directive?". Invocation: reviews every plan.

**What you decide**:

- [ ] Rerun budget — keep 2, drop to 1, or scale with plan size?
- [ ] Invocation policy — every plan vs. only severity crossings vs. only multi-tool plans?
- [ ] "What to flag" prompt refinement — what specific checks beyond common-sense?

**Blocking?**: No. Defaults run.

---

## §9 — BalanceValidator stub

**What's there**: `world_system/content_registry/balance_validator_stub.py` (~50 LOC). Reads tier multipliers from `Definitions.JSON/stats-calculations.JSON`, rejects outliers outside `[0.5x, 2x]` of nominal. Wired into commit path.

**What you decide**: Real min/max ranges for damage / defense / durability per tier.

- [ ] Damage per-tier ranges
- [ ] Defense per-tier ranges
- [ ] Durability per-tier ranges
- [ ] Other stats (mana, HP, etc.) — add to stub?
- [ ] Tolerance (currently `[0.5x, 2x]`) — tighten?

**Blocking?**: No. Stub catches obvious outliers; won't catch subtle imbalance.

---

## §10 — Content Registry schema

**What's there**: `world_system/content_registry/` — per-tool tables (`reg_hostiles`, `reg_materials`, `reg_nodes`, `reg_skills`, `reg_titles`) + unified `content_xref`. Generated JSON files go to sacred subdirs.

**What you decide**:

- [ ] Generated JSON filename scheme — timestamps or sequential numbers?
- [ ] Commit-time reload mechanism — direct `<Database>._reload()` calls vs. GameEventBus-based notification?

**Blocking?**: No. Schema is solid; cosmetic decisions.

---

## §11 — WES Plan dataclasses

**What's there**: `world_system/wes/dataclasses.py`. `WESPlan`, `WESPlanStep`, `ExecutorSpec`, `TierRunResult`. Some fields are `Dict[str, Any]`:

- [ ] `WESPlanStep.slots` — harden per-tool typed variants?
- [ ] `ExecutorSpec.flavor_hints` — typed per-tool?
- [ ] `ExecutorSpec.cross_ref_hints` — typed per-tool?
- [ ] `ExecutorSpec.hard_constraints` — typed per-tool?

**Blocking?**: No. Loose dicts work.

---

## §12 — Backend task routing (wired; review values)

**What's there**: 18 new routes in `backend-config.json`. Only `wes_execution_planner` primary=Claude; everything else ollama→mock.

**What you decide**: Which tasks should pay for cloud.

- [ ] `wes_execution_planner` — Claude primary (current)
- [ ] `wns_layer7` — upgrade to cloud for world-narrative quality?
- [ ] `wes_supervisor` — upgrade for tighter review?
- [ ] Other tasks — stay local?

**Blocking?**: No. Current defaults are sensible.

---

## §13 — Model choices per role

**What's there**: `ollama.default_model = llama3.1:8b` used everywhere.

**What you decide** (per-role):

- [ ] WNS low weavers (NL2/NL3) — 8B?
- [ ] WNS high weavers (NL6/NL7) — larger model for world context?
- [ ] WES planner — cloud Sonnet default, bump to Opus?
- [ ] WES hubs — 8B fine?
- [ ] WES executor_tools — consider tuned smaller model (7B) with structured decoding?
- [ ] WES supervisor — 8B fine?

**Blocking?**: No. Playtest-tuned.

---

## §14 — `call_wes` trigger condition

**What's there**: Weaver prompts include `call_wes: boolean` field. Code reads it and fires WES when true.

**What you decide**: Is weaver-self-flag enough, or add a deterministic fallback?

- [ ] Confirm self-flag approach in playtest
- [ ] Decide whether to layer a deterministic fallback:
  - [ ] Thread-count threshold (e.g. ≥10 open threads fires)
  - [ ] Severity threshold (moderate → significant auto-fires)
  - [ ] Arc-stage transition detection (rising → falling fires)

**Blocking?**: No. Self-flag wired.

---

## §15 — Distance-decay depth per firing tier

**What's there**: `world_system/config/narrative-config.json` → `distance_filter`. Per-firing-tier depth map. `NarrativeDistanceFilter` utility in `world_system/wns/`.

| Firing tier | Full detail | Brief summary |
|---|---|---|
| NL2 | NL2+NL1 at locality | NL3-NL7 parents |
| NL3 | NL3+NL2 at district | NL4-NL7 parents |
| NL4 | NL4+NL3 at region | NL5-NL7 parents |
| NL5 | NL5+NL4 at nation | NL6-NL7 parents |
| NL6 | NL6+NL5 relevant | NL7 parent |
| NL7 | NL7+NL6+per-nation NL5 | — |

**What you decide**: Word/token budget per depth.

- [ ] Cap lengths for "brief summary" depth
- [ ] Cap lengths for "full detail" depth
- [ ] Per-tier cap overrides?

**Blocking?**: No. Depths are tunable JSON.

---

## §16 — Metrics dashboard counters

**What's there**: `world_system/wes/metrics.py`. 8 counters, all JSON-serializable:

- `plans_run_total / plans_committed / plans_abandoned`
- `plans_per_hour` (sliding window)
- `tool_successes_by_type` / `tool_failures_by_type`
- `orphan_blocks_total`
- `supervisor_reruns_total` / `supervisor_rerun_rate`
- `graceful_degrade_events_by_subsystem`
- `tier_usage_by_backend`

**What you decide**:

- [ ] Any counters missing for your operational questions?
- [ ] Dashboard UI layer — defer or wire now?

**Blocking?**: No. Measurement is sensible.

---

## §17 — Sacred directories / generated content targets

**What's there**: `content_registry/generated_file_writer.py` routes per-tool:

- Materials → `items.JSON/items-materials-generated-<ts>.JSON`
- Hostiles → `Definitions.JSON/hostiles-generated-<ts>.JSON`
- Nodes → `Definitions.JSON/Resource-node-generated-<ts>.JSON`
- Skills → `Skills/skills-generated-<ts>.JSON`
- Titles → `progression/titles-generated-<ts>.JSON`

**What you decide**:

- [ ] Paths (current matches CLAUDE.md sacred-directory convention)
- [ ] Naming scheme (see §10)

**Blocking?**: No.

---

## Triage — suggested tackle order

### Tier 1: Most load-bearing (do first)

- [ ] §7 — Scope-by-firing-tier prompts (the whole v4 architectural commitment)
- [ ] §1/§6 — `wes_execution_planner` prompt (plan quality drives everything)
- [ ] §1/§6 — `wns_layer7` prompt + full §5 narrative tag taxonomy (world narrative substrate)
- [ ] §1/§6 — `wes_hub_*` prompts for all 5 tools (this is where flavor lives)

### Tier 2: Playtest-tuned (observe first, then adjust)

- [ ] §4 trigger N values
- [ ] §13 model choices per role
- [ ] §15 distance-decay token budgets
- [ ] §8 supervisor rerun budget
- [ ] §14 call_wes self-flag calibration

### Tier 3: Cosmetic / low-risk (fold in when convenient)

- [ ] §3 graceful-degrade constants
- [ ] §10 filename scheme
- [ ] §2 bundle dict → typed hardening
- [ ] §11 plan dataclasses hardening
- [ ] §16 additional counters

### Locked (don't touch — code invariants)

- Address-tag immutability rules (`thread:` / `arc:` / `witness:` / geographic prefixes)
- Content registry schema shape
- WES 3-tier + supervisor topology
- Sacred content boundaries
- Backend task routing structure (values are tunable; structure is not)

---

## §WNS-A1 — WNS affinity modifier tool (separate queue)

**Status**: design only, not yet implemented. See memory: `wns_affinity_modifier_tool.md`.

**What it is**: lightweight WNS tool (not WES) that emits XML `<AffinityShift>` directives to nudge faction/NPC standing across geographic scopes. A deterministic resolver (not LLM) attaches time + causing-event id and commits deltas to faction system + NPC context registry.

**Shape sketch**:
```xml
<AffinityShift>
  <Target>faction:merchants</Target>
  <Scope>nation:blackoak</Scope>
  <Effect>standing_delta: -0.15</Effect>
</AffinityShift>
```

**What you decide**:
- [ ] Lock the Effect schema (numeric delta? typed? `affinity_change | belonging_shift | reputation_tweak`?)
- [ ] Lock scope vocabulary (already geographic: nation / region / district / locality — confirm override rules work as described)
- [ ] Which WNS layers emit these (NL3-NL6 probably, where faction/NPC dynamics live)
- [ ] Integration point with NPC v3 dynamic context registry (see `npc_schema_overhaul_v3.md`)

**Blocking?**: No. Queued for post-v4-tools implementation. Design captured.

**When to implement**: After v4 content tools (Steps 2-6) ship and NPC schema overhaul is designed. This hooks into both.

---

## Recovery / reference

- Full ledger reference: [`PLACEHOLDER_LEDGER.md`](PLACEHOLDER_LEDGER.md)
- v4 canonical spec: [`WORLD_SYSTEM_WORKING_DOC.md`](WORLD_SYSTEM_WORKING_DOC.md)
- Constraint: when you furnish, sync the code-side parser if the JSON shape changes (most fixtures don't require this — they fit the existing schema)
