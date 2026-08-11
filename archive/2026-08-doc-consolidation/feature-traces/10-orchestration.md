# Feature Trace 10 — Orchestration (Planner + Supervisor + Request Layer)

**Wave:** 3 (cross-cutting; consumes 9 prior traces)
**Owned endpoints:** `wes_execution_planner`, `wes_supervisor`, `world_system/wes/request_layer.py` (no LLM — code-driven alt-dispatch)
**Final output artifact:** **Decisions, not JSON.**
- Planner: `WESPlan` — scope, step set, intent strings, dependency DAG, abandonment verdict.
- Supervisor: `Verdict` — `{pass|fail, rerun, notes, adjusted_instructions}`.
- Request Layer: `RequestSpecBatch` — `Dict[tool, List[ExecutorSpec]]`, deterministic, single-step, hub-bypassing.
**Date:** 2026-05-26

> "I work backwards and anchor as much as I can from the user experience. The level of detail and thought through every branch of possible AI usage needs to be immaculate and enumerated." — user

> "Personal shopper for each feature. At the end of the day you need to get it all with minimal waste." — user

The orchestration agent has no JSON artifact a player will ever see. Its outputs are commitments — the planner commits to *what gets built and in what order at this firing*; the supervisor commits to *whether what was built is fit to land*; the request layer commits to *which orphan resolutions are deterministic enough to skip planner+hub round-trip*. Every commit is downstream of a bundle and upstream of a player-visible artifact authored by one of the 8 content tools. **The orchestration agent is the sole place where wrong-scope, wrong-faction, wrong-locality, wrong-tier, wrong-voice decisions can be averted before content commits.** Slop in this agent metastasizes through every content tool that runs after it.

This trace structures around the three decisions and the prior 9 traces' findings about how those decisions land.

---

## 1. Player anchor + failure modes

### 1.1 The player's literal moment — orchestration as invisible service

Unlike content agents, no player ever opens a "planner panel." Yet orchestration shapes every player moment that involves WES-generated content:

- The player walks into a new tavern. **An NPC stands at the bar.** That NPC's existence at all is a planner decision (firing tier 3+ at a district arc said `<WES purpose="new-npc">` was warranted; the planner sized scope to `[skills, npcs]`). That NPC's faction-coherence with the tavern's locality is a supervisor decision (the supervisor read directive fidelity and thematic coherence before commit). That NPC's signature skill exists because either the planner ordered `[skills] → [npcs]` correctly, OR the request layer caught the orphan at orphan-resolution time. The player feels: *"this NPC belongs here."*
- The player accepts a quest. The quest's `given_by` resolves cleanly because the planner co-emitted the NPC, OR the planner picked an existing NPC whose role plausibly fits, OR the request layer detected the orphan and minted the NPC from the requesting quest's flavor. The reverse failure mode: quest's `given_by` resolves to a real NPC in the WRONG faction, because the planner picked an existing NPC by name-match without affinity-check. The player feels: *"this quest doesn't make sense from this person."*
- The player kills a copperlash rider. The rider drops `moors_copper`. The chunk template that spawned the rider says `enemySpawns: copperlash_rider` and the rider's `drops: moors_copper` resolves to a real material because the request layer cascaded: planner emitted chunks, chunks named the hostile, hostile named the material, request layer fired the material spec mid-pipeline. The player feels: *"the ecology of this place hangs together."*

### 1.2 Timing budgets

- **Planner:** target < 2s real-LLM (Sonnet). One bundle in, one plan out, no retries on first try. Fixture < 200ms. This sits in the WNS cascade-time path; the player is not watching. But 5+ second planner latencies compound across multiple WES firings per session and stall NPC/quest pool refills.
- **Supervisor:** target < 2s real-LLM. The supervisor reads the condensed tier-log (one line per tier result) plus directive + rationale. Out: verdict. Sits between dispatch end and commit; again, off the player's critical path BUT a slow supervisor means content sits in the staged-but-not-committed limbo, where a fresh WNS firing on the same locality can fire BEFORE the prior plan commits and the second firing's planner sees no registry entries. **The order matters more than the latency** here.
- **Request layer:** target < 500ms. Pure code — no LLM call. It's invoked inside `_run_runtime_cascade` between primary dispatch and supervisor; its budget is dominated by spec construction + registry probes + dispatcher fan-out. Each cascade depth costs one async-runner round-trip per tool (parallel within tool). Two-depth cascade = ~2-4 seconds total when all targets fire real-LLM at the executor_tool tier.

### 1.3 Failure modes — what BAD orchestration looks like

**Six failure flavors. Two are catastrophic, four corrosive.**

**(a) Catastrophic: Content commits in the wrong locality.** The planner reads `firing_address: region:ashfall_moors` from the bundle, but `step.slots` carries `biome: highland_steppe` because the planner's directive-text parsing is loose. The hub passes `address_hint: ashfall_moors` to the tool but the tool reads `biome: highland_steppe` from `hard_constraints.biome` and authors accordingly. The chunk that lands in the moors has a highland_steppe biome description and references highland nodes. Supervisor's `thematic coherence` check should catch this, but a pass-on-empty-rules supervisor will rubber-stamp. **Player feels: "this place doesn't make sense."** *(Defense: planner's `slots.biome` MUST mirror `firing_address`'s biome by default; deviation requires explicit narrative justification in `intent`. Supervisor's thematic check MUST compare chunk biome to firing-address biome.)*

**(b) Catastrophic: Content commits with wrong faction.** Planner emits NPC with `slots.primary_faction: guild:moors_raiders` for a firing whose `parent_summaries[region:ashfall_moors]` says "the moors raiders have been crushed; the order of the salt now claims the cliffs." The new NPC speaks for a faction the regional narrative says is gone. **Player feels: "the world is contradicting itself."** *(Defense: planner MUST read `parent_summaries` for active-faction signals before picking `slots.primary_faction`. Per Agent 9's contract this requires closing the `parent_summaries` leak; without that closure the planner is blind. Supervisor MUST check NPC faction against current bundle thread + parent narrative for contradiction.)*

**(c) Corrosive: Generated content silently rejected.** Tier results contain a supervisor-failing artifact (off-tier hostile, missing required field after schema validation). Supervisor sets `verdict: fail, rerun: false`. The orchestrator rolls back. Player never sees the artifact. But the WNS narrative the firing wrote IS persisted and says "a strange salt-bound NPC was seen in Tarmouth this week." There's no NPC. **Player feels: "the journal lied."** *(Defense: WNS narrative should not commit to fictions outside what WES produces; supervisor failure should trigger a WNS retraction event OR be visible as a known-degraded firing. Today neither exists. Surfaced as `[WNS-GAP]`.)*

**(d) Corrosive: Generated content commits with broken xrefs.** Orphan detector fails (a planning-time bounce escapes because the planner output an acknowledgment marker without solving the issue) AND the runtime cascade hits its depth cap before resolving the last orphan. Chunk commits with `enemySpawns: ["broken_id"]`. Chunk spawn silently skips. Player walks into the moors-stone biome, finds nothing to fight. **Player feels: "this place is empty."** *(Defense: supervisor MUST fail any plan with unresolved post-cascade xrefs. Today the orphan check is pre-supervisor and the supervisor doesn't re-check post-cascade. Surfaced in §5.)*

**(e) Corrosive: Narrative-disconnected content.** The bundle's `directive_text` says "the moors are restructuring around copper trade" but the planner emits `[skills, titles]` without coupling either to copper. The skill is generic "Power Strike." The title is "Common Wanderer." Neither references copper, moors, or restructuring. Both are off-topic but in-scope. Supervisor's `directive fidelity` check should fail this — but a loose supervisor passes anything that's "fantasy-shaped." **Player feels: "nothing is responding to me."** *(Defense: supervisor's directive-fidelity rule MUST compare every step's `intent` and its tool's resulting artifact `metadata.narrative` against the directive's proper nouns. If the directive mentions copper and no artifact references copper, fail.)*

**(f) Corrosive: NPC voicing skills they couldn't have taught.** Plan DAG order is `[skills, npcs]` (current planner example) — skill emits, NPC emits referencing `teachableSkills: [skill_id]`. But NPC's narrative is written BEFORE seeing the skill (DAG ordering controls dispatch, not artifact awareness). The NPC says "I teach the moors-stone bind" but the skill landed as "Salt-Whisper" because both tools wrote independently from `step.intent` alone. **Player feels: "the NPC said one thing, the skill is another."** *(Defense: cross-feature artifact propagation — when a step depends on another, the dependent's hub should see the dependency's staged artifact summary. Skills agent's intent-anchor pattern is a partial solution. Both DAG fix and intent-anchor pattern are needed. Discussed §6.)*

### 1.4 What "good" orchestration looks like

After an hour of play, the player has met three NPCs. The first is a captain in the moors who teaches a copper-themed bleed skill; the second is a smith in the foothill town adjacent to the moors who works with moors-copper imported up the road; the third is a chronicler in the regional capital who can be asked about the moors economic shift. Each NPC's faction is coherent with their locality. Each one references at least one proper noun the WNS narrative coined. Each one's signature skill exists, is teachable, and matches their faction. None of the three NPCs were in the planner's first plan — the captain came from a tier-4 region firing, the smith from a tier-3 district firing on the foothills, the chronicler from a tier-5 province firing. **The player can name a thread linking the three: copper.** That thread exists because every planner decision read the WNS parent-summary that named copper, and every supervisor decision verified the staged artifact mentioned copper.

Three properties:
- **Locality-coherent** — content lands where it makes sense; xrefs resolve to in-faction entities.
- **Narrative-causal** — every content artifact can be traced back to a WNS thread the planner read.
- **Pool-fresh** — by the time the player walks past, the pool has fresh content; the cascade fired hours ago, the supervisor verified it, the registry holds it.

---

## 2. Output artifact: the decisions

This section enumerates every field on every decision output, with per-field "good ≠ valid" notes. Decisions are the artifact even though no JSON file lands in `progression/`.

### 2.1 Planner output: `WESPlan`

Locked in `Game-1-modular/world_system/wes/dataclasses.py:67-100`. Each field:

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `plan_id` | str | runtime + planner | Server-assigned UUID prefix `plan_`. Planner-emitted ID respected if syntactically clean. |
| `source_bundle_id` | str | **runtime overrides planner** (line 122) | The planner's echoed bundle_id is advisory. Runtime authoritatively sets from the input bundle. |
| `steps[]` | `List[WESPlanStep]` | planner | The decision: WHICH tools fire at WHAT scope. Quality: minimum viable set for the directive; no over-emission; no under-emission. |
| `steps[].step_id` | str | planner | Stable within plan. Used for `depends_on`. Should be short (`s1`, `s4`) — long IDs bloat the DAG. |
| `steps[].tool` | str (one of 8) | planner | Strictly one of `materials, nodes, hostiles, skills, titles, chunks, npcs, quests`. Per-purpose mapping in `_wes_tool` body of each NLn fragment (see §6). Quality: tool MUST match the directive purpose; `<WES purpose="new-quest">` MUST produce at least one `quests` step (modulo abandonment). |
| `steps[].intent` | str (1-2 sentences) | planner | The hub-facing prose. **THE single most important field.** Quality: locality-rooted, proper-noun-bearing, faction-aware. "Vendetta hunt issued by Captain Vell..." beats "Quest about hunting." Per Skills trace, this intent doubles as the *intent-anchor* downstream tools use to author narrative when artifact-propagation isn't available. |
| `steps[].depends_on` | List[str] | planner | DAG edges. Quality: acyclic (PlanCycleError enforces); minimum-necessary (over-dependence stalls parallelism); narratively-sound (NPC-needs-skill should depend, but quest-references-NPC MAY co-emit if intent allows). |
| `steps[].slots` | Dict[str, Any] | planner | Hub-consumed constraints. Quality: every required key for the tool present; values from registry/bundle, never invented. Per planner prompt: `tier`, `biome`, `category`, `role`, `home_chunk`, `primary_faction`, `given_by`, etc. **Critical field for failure mode (a) and (b) above.** |
| `rationale` | str (1-3 sentences) | planner | The supervisor's primary input. Quality: names WHICH directive elements each step addresses; if the plan is partial, explains what was dropped and why. Generic rationales ("plan addresses directive") fail the supervisor's first check. |
| `abandoned` | bool | planner | The deliberate "no plan" verdict. Quality: triggered ONLY when scope, coherence, or grounding makes a plan infeasible — never as a hedge. Per prompt: incoherent directive, missing focal grounding, smallest-viable-plan-exceeds-scope, off-list tool requested. |
| `abandonment_reason` | str (1 sentence) | planner | The audit trail. Quality: cites the specific reason from the four prompt-listed criteria. Generic "could not plan" loses the lesson for future tuning. |

#### 2.1.1 Schema gaps on `WESPlan`

- `[WES-SCHEMA-GAP]` **No `acknowledgment` field.** The plan-time bounce-back system (`plan_resolution.PLANNER_ACKNOWLEDGMENT_MARKER`) reads acknowledgment from a substring of `rationale`. This is brittle — the planner can accidentally trip the substring; a deliberate acknowledgment can be omitted by phrasing. Should be a first-class `planner_acknowledgment: bool` field. Designer call.
- `[WES-SCHEMA-GAP]` **No `purpose` field on the plan or its steps.** The bundle carries `directive.scope_hint.purpose` ("new-quest" / "new-chunk" / ...); the plan loses this binding. For multi-purpose bundles (§7.1 below) the plan should carry per-step `purpose: str` so post-hoc analysis can compare "step's purpose vs. WNS directive purpose" without round-tripping through bundles. Particularly useful when supervisor wants to verify purpose-fidelity.
- `[WES-SCHEMA-GAP]` **No `firing_layer` field.** The plan inherits firing_tier from the bundle, but doesn't echo it on the step. When the request layer's downstream cascade depth produces specs, those specs don't carry the originating firing layer — and the executor_tool can't tier-scope its output. Mitigation: `RequestLayer._build_hard_constraints` echoes `tier` from the requesting payload. Acceptable; flagged for completeness.
- `[FRAGMENT-GAP]` **No "co-emit awareness" record on steps.** When `quests` depends on `npcs` in the same plan, downstream tooling needs to know "the NPC artifact will be ready at hub-call time, and you should reference its proper noun." Today this is implicit in `depends_on`. A `co_emit_with: [step_id, ...]` field with the EXPECTED proper noun would let downstream tools commit to references before staging. Discussed §6.

### 2.2 Supervisor output: `Verdict`

Schema is the dict returned by `LLMSupervisor.review`:

```
{
  "verdict": "pass" | "fail",
  "rerun": bool,
  "notes": str,
  "adjusted_instructions": str | null
}
```

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `verdict` | `"pass" \| "fail"` | supervisor | Binary commit-or-rollback. Quality: pass means "the plan and staged artifacts respond to the directive coherently AND within scope AND with locality-rooted voice"; fail means at least one of those is broken. |
| `rerun` | bool | supervisor | Whether to ask the planner to try again. Quality: rerun=true only when failure is FIXABLE with adjusted instructions (Captain-of-line is wrong faction → tell planner the correct faction); rerun=false when structurally infeasible (directive incoherent → no rerun saves it). |
| `notes` | str (1-2 sentences) | supervisor | Audit + designer-tuning surface. Quality: cites the specific check that triggered (directive fidelity, thematic coherence, scope fidelity, narrative voice, balance tell, NPC v3 / Quest v3 sanity). Pass notes should be one sentence — fail notes one or two — never a paragraph. |
| `adjusted_instructions` | str \| null | supervisor | The lever for rerun. Quality: 1-2 sentences telling the planner *what to change*. "Generate the NPC with primary_faction=order_of_the_salt; the moors raiders are gone per parent summary." Specific. Actionable. Not "do better." Null when verdict=pass. |

#### 2.2.1 Schema gaps on Verdict

- `[WES-SCHEMA-GAP]` **No `failed_checks: List[str]` field.** When supervisor fails, the notes string lumps reason together. For tuning, we want structured "which of the 6 checks fired" (directive_fidelity, thematic_coherence, scope_fidelity, narrative_voice, balance_tell, v3_sanity). Cheap addition; high payoff for designer playtest review.
- `[WES-SCHEMA-GAP]` **No `per_step_verdicts: Dict[step_id, {pass|fail, reason}]`.** Today the supervisor reviews the whole plan and emits one verdict. Realistic supervision is per-step: chunk passes, NPC fails. With per-step verdicts, the supervisor could rerun ONLY the failing step (partial rerun) instead of full plan rollback. **High-value future endpoint, deferred to §9.**
- `[FRAGMENT-GAP]` **No `confidence: float`.** Supervisor binary verdict obscures uncertainty. A confidence score (0.0-1.0) would let the orchestrator weigh borderline cases differently — e.g., commit a 0.6-confidence pass but queue a designer-review flag. Cheap; designer call.
- `[FRAGMENT-GAP]` **Supervisor doesn't see post-cascade artifacts.** After the runtime cascade resolves orphans, the supervisor reviews the FULL tier_results list (primary + request-layer-generated). But the supervisor's prompt doesn't know which artifacts came from primary plan vs. cascade. **For cascade-generated content, the supervisor should apply scope rules differently** — a cascade-emitted material doesn't count against the planner's tier-2 scope cap. Today this distinction is lost. Surfaced in §4.

### 2.3 Request layer output: `RequestSpecBatch`

Locked in `request_layer.py:77-93`:

```
RequestSpecBatch {
  tool_specs: Dict[tool_name, List[ExecutorSpec]],
  cascade_depth: int,
  parent_plan_id: str,
}
```

Each `ExecutorSpec` (`dataclasses.py`) carries:

| Field | Type | Author | Quality bar |
|---|---|---|---|
| `spec_id` | str | request_layer | Prefix `req_d{depth}_{idx}_{tool}_{target_id}`. Provenance-readable in logs. |
| `plan_step_id` | str | request_layer | Virtual: `request_layer_d{depth}_{tool}`. Stable for log-grouping. |
| `item_intent` | str | request_layer | Preferred: `rec.suggested_intent` from `find_runtime_orphans`. Fallback: "Generate {tool} entry '{id}' — referenced by {req_tool} '{req_id}'." Quality: should mention what's drawing the request, not just what's missing. |
| `flavor_hints` | Dict | request_layer | `{name_hint, referenced_by_narrative?, referenced_by?, geographic_address?}`. Quality: when requesting payload exists, narrative excerpt mined from it; bundle address ALWAYS attached when available. |
| `cross_ref_hints` | Dict | request_layer | `{required_id, referenced_by_tool?, referenced_by_id?, ...}`. Echoes any `rec.suggested_slots`. Quality: `required_id` pins what the executor_tool MUST emit; rest is context. |
| `hard_constraints` | Dict | request_layer | `{tier: inferred from requesting payload (default 1), address: from bundle}`. Quality: tier defaults are CONSERVATIVE — better to emit a low-tier orphan resolution than a high-tier slop one. |

#### 2.3.1 Schema gaps on RequestSpecBatch

- `[FRAGMENT-GAP]` **No `narrative_context` field on the spec.** When a request-layer spec fires, the executor_tool sees `item_intent + flavor_hints + cross_ref_hints + hard_constraints` but NOT the upstream firing layer's narrative summary or parent narrative. Per Agent 9's contract these should flow through `BundleToolSlice` for hub-driven specs. For request-layer specs, they should flow through the spec's `flavor_hints.bundle_narrative_summary` (1-2 sentence digest of the firing layer narrative). Cheap addition; closes the same disconnected-narrative failure mode that haunts the hub path.
- `[FRAGMENT-GAP]` **No `requesting_payload_excerpt` digest.** Today `flavor_hints.referenced_by_narrative` carries a single string from the requesting payload. For complex requesting payloads (a chunk with multiple narrative anchors) a richer digest would help. Designer call; the current single-string version handles 80% of cases.
- `[FRAGMENT-GAP]` **No `purpose` carried through.** Same as planner output; for tracing.
- `[WES-SCHEMA-GAP]` **`hard_constraints.address` is a single string, not a `geographic_chain`.** Request-layer specs are exactly where the geographic_chain context matters — a missing material being mined for a chunk in `region:ashfall_moors` should see the region's biome lineage, not just the address string. Wire from bundle's `directive.scope_hint.geographic_chain` once Agent 9's contract is implemented.

### 2.4 The hidden output: orchestrator-level commit decisions

Beyond the three explicit decisions above, the orchestrator (`wes_orchestrator.py`) makes implicit decisions:

- **Rerun budget consumption** (line 423): `DEFAULT_RERUN_BUDGET = 2`. Each plan can be re-planned twice (planner bounce-back OR supervisor rerun). The budget is shared across both triggers. Quality: 2 is the designer's call; too high means runaway costs, too low means no recovery for fixable failures. **Designer-tunable** with telemetry from `WESMetrics.record_plan_bounce`.
- **Cascade depth cap** (`MAX_RUNTIME_CASCADE_DEPTH = 2`): primary plan can cascade twice. Quality: 2 covers chunk → hostile → material (depth 2). Higher depth = exponential xref fanout. Designer-tunable per playtest.
- **Cascade steps per pass cap** (`MAX_CASCADE_STEPS_PER_PASS = 8`): caps fanout per cascade level. Quality: prevents a malformed chunk template that names 30 hostiles from generating 30 hostiles in one pass.
- **Backend chain selection**: not orchestration's call but inherited from `BackendManager` configuration. Planner + supervisor both run through `task="wes_execution_planner"` / `task="wes_supervisor"` task slots. Quality: must respect `WES_REQUIRE_REAL_LLM` for production playtest per memory `prompt_studio_and_observability.md`.

---

## 3. Templated baseline + quality delta

The "what does a 1990s slot machine do here" exercise. This section is the centerpiece for understanding what AI must contribute.

### 3.1 The literal templated planner

A competent procedural planner has zero NLP. It reads `firing_tier` and `purpose` from the bundle, looks up a tier-purpose → tools mapping table, emits a plan with hardcoded DAGs.

```python
def template_plan(bundle):
    tier = bundle.directive.firing_tier
    purpose = bundle.directive.scope_hint.get("purpose", "")
    address = bundle.delta.address

    TIER_PURPOSE_TOOLS = {
        (2, "new-skill"):    [("s1", "skills", {})],
        (3, "new-npc"):      [("s1", "npcs", {"home_chunk": address})],
        (3, "new-quest"):    [("s1", "npcs", {}), ("s2", "quests", {"given_by": "s1"})],
        (4, "new-chunk"):    [
            ("s1", "materials", {}), ("s2", "nodes", {}),
            ("s3", "hostiles", {}), ("s4", "chunks", {}),
        ],
        # ... rest of the 6×8 matrix
    }
    steps_template = TIER_PURPOSE_TOOLS.get((tier, purpose), [])
    return WESPlan(
        plan_id=f"plan_{uuid4().hex[:8]}",
        source_bundle_id=bundle.bundle_id,
        steps=[WESPlanStep(step_id=sid, tool=tool, intent=f"Generate a new {tool}", slots=slots)
               for sid, tool, slots in steps_template],
        rationale=f"Tier {tier} {purpose} → standard plan template.",
        abandoned=not bool(steps_template),
        abandonment_reason="No template for tier/purpose" if not steps_template else "",
    )
```

This is fine. It handles the 80% case. **And it loses every battle.** Every NPC has intent "Generate a new NPC" — the hub has nothing to pass downstream, the tool has nothing to differentiate from the last 50 NPCs. Every quest gets the giver from the same NPC step in the plan; every chunk gets the same hostile spawn pattern. After three sessions the player has seen the template's full output space.

### 3.2 The literal templated supervisor

A competent procedural supervisor runs deterministic checks:

```python
def template_verdict(plan, tier_results, bundle):
    # Check 1: schema validity (already done pre-supervisor)
    # Check 2: xrefs resolve (already done by orphan detector)
    # Check 3: artifact count matches plan step count
    if len(tier_results) < len(plan.steps):
        return {"verdict": "fail", "rerun": False,
                "notes": "Missing artifacts for some steps", "adjusted_instructions": None}
    # Check 4: no errors in tier results
    if any(r.errors for r in tier_results):
        return {"verdict": "fail", "rerun": False,
                "notes": "Tier errors present", "adjusted_instructions": None}
    return {"verdict": "pass", "rerun": False, "notes": "all green", "adjusted_instructions": None}
```

This passes the moors-raider-NPC-in-frost-peaks chunk because the schema validates and xrefs resolve. The deterministic supervisor cannot catch directive infidelity, thematic incoherence, narrative voice collapse, or balance tells. **The single most important supervisor responsibility is NOT what the templated supervisor can do.**

### 3.3 The literal templated request layer

The request layer is ALREADY pure code — `RequestLayer` in `request_layer.py`. **There IS no LLM here, by design.** This is the one place where templated = real, because the user's directive (per the docstring) said:

> "Pure-code detection + spec construction. Faster than asking a supervisor LLM to decide, more robust because the recommendation logic is deterministic and unit-testable."

So the "quality delta" question for the request layer is inverted: **what would an LLM-driven orphan resolver add over the existing pure-code version?** Likely nothing for the common case (`drops: moors_copper` → spec for `moors_copper`). For exotic cases — a chunk that names "the Moors-Stone Tradition" as an emergent_entity which doesn't map to any tool's content_id pattern — an LLM resolver could classify "is this an NPC or a chunk-feature or noise?" Today such ambiguities get dropped silently. **This is the candidate for a `wes_orphan_classifier` future endpoint (§9), not a replacement of the pure-code path.**

### 3.4 What the AI planner adds over the template

Field by field:

1. **`steps[].intent` specificity.** "Vendetta hunt issued by Captain Vell against his own copperlash riders..." vs. "Generate a quest." This is the load-bearing differentiation — the hub reads intent and turns it into `flavor_hints.prose_fragment`, which the tool reads and turns into `description_full.narrative`. Per Agent 1 and Agent 6 traces, the chain only delivers specificity if the planner injects it at the top.
2. **Scope discipline informed by parent narrative.** Template plans tier-4 with `[materials, nodes, hostiles, chunks]` always. AI planner reads `parent_summaries[region:ashfall_moors]` says "the moors are already saturated with copper content" and emits `[npcs, quests]` instead — using existing material/node/hostile content.
3. **Faction-aware slot picking.** Template assigns `slots.primary_faction` from a rotating list. AI planner reads `parent_summaries` to know which factions are active in this address and picks the one whose narrative gives the new NPC a reason to exist.
4. **Abandonment as a deliberate choice.** Template abandons only on table-lookup miss. AI planner abandons on incoherent directive, on smallest-viable-plan exceeding scope, on off-list tool request. This is *quality preservation* — the right answer is sometimes "no plan."
5. **Cross-tool co-emission DAG.** Template uses fixed DAGs per (tier, purpose). AI planner reads the directive_text and decides "this directive implies a faction is rising; we need NPCs+quests+titles co-emitted in a chain." The DAG is intent-shaped, not template-shaped.
6. **`rationale` for supervisor.** Template emits "tier-N standard plan." AI planner emits "tier-4 moors-copper firing: rebuilds ecosystem around copper trade — material → node → hostile → chunk hosts both → captain NPC lives there → title rewards killing his men → vendetta quest. All cross-refs co-emit cleanly inside this plan." (Verbatim from `prompt_fragments_wes_execution_planner.json` example.) Quality: rationale lets the supervisor verify the planner's logic, not just its output.

### 3.5 What the AI supervisor adds over the template

The 6 checks in the supervisor prompt are pure judgment work. None are schema-checkable. Field by field:

1. **Directive fidelity.** Reads `bundle_directive` and each step's intent + each tier_result's `raw_response` excerpt. Asks: does the staged content respond to the directive's proper nouns? "Moors economic realignment" → expect materials/hostiles/chunks/NPCs keyed to moors + copper.
2. **Thematic coherence across artifacts.** Compares cross-artifact references — does the moors raider drop moors_copper? Does the captain live in the moors chunk? Templated cannot do cross-artifact reasoning.
3. **Scope fidelity vs firing tier.** Reads `firing_tier`, counts staged artifacts by tool, applies the scope table from §8. Templated could partially do this — but reading whether `chunks` was emitted out of scope at tier-2 means understanding what content category each step represents at narrative scale.
4. **Narrative voice.** "Specific vs generic." A literal voice judgment. The clear LLM-only check.
5. **Obvious balance tells.** "Tier-2 hostile with 5000 HP" — fuzzy bounds, not strict ranges. The strict ranges are deterministic code's job (BalanceValidator, designed-not-built).
6. **NPC v3 / Quest v3 sanity.** Voice consistency between fields, schema-valid-but-internally-incoherent shapes. Per Agent 2 (NPCs) and Agent 1 (Quests) traces, these v3 schemas have many places where the schema validates but the artifact contradicts itself — different voices in different fields, faction-belonging tags that don't match primary_faction, etc. LLM judgment territory.

### 3.6 What the (already-pure-code) request layer adds over a non-existent baseline

Without a request layer, every orphan would require a synthetic plan → planner re-invocation → hub call → tool call. That's 3 LLM calls per orphan. The request layer collapses this to 1 (just the tool). **The quality delta is latency and determinism, not semantic richness.** This is correct architecture — synthetic plans for cascade orphans is wasted LLM mass; deterministic spec construction is the right call.

The LATER point at which AI could help — the orphan classifier — is §9 future work.

---

## 4. Backward trace through the pipeline

What each orchestration tier needs from upstream + downstream context.

### 4.1 Planner inputs — what the planner reads

From `LLMExecutionPlanner._bundle_to_vars` (lines 162-181):

- `bundle_id` — provenance
- `firing_tier` — scope discipline driver
- `bundle_directive` (= `bundle.directive.directive_text`) — the WNS-authored prose to respond to
- `bundle_narrative_context` (= `bundle.narrative_context.firing_layer_summary`) — what the firing layer just narrated
- `bundle_delta` — stringified counts of npc_dialogue and wms_events
- `registry_counts` — placeholder `"n/a"` today
- `firing_address` — locality/district/region/etc. address

#### 4.1.1 What's MISSING from the planner's inputs

- `[WES-SCHEMA-GAP]` **`parent_summaries` not exposed.** Per Agent 1 and Agent 9, the bundle carries `narrative_context.parent_summaries: Dict[str, str]` but `_bundle_to_vars` reads only `firing_layer_summary`. The planner cannot see what the region / nation / world narratives say at the parent addresses. Without this:
  - Cannot do faction-aware scope picking (failure mode (b)).
  - Cannot cross-reference active vs deprecated factions.
  - Cannot judge "this directive at this firing tier deserves cross-layer co-emission."
  Fix: extend `_bundle_to_vars` with `bundle_parent_summaries: str` (concatenated, key-prefixed string). Add `${parent_narratives}` to the planner user_template. Already covered in Agent 9 §5 — accepting that contract here.
- `[WES-SCHEMA-GAP]` **`open_threads` not exposed.** Active thread headlines + content_tags should reach the planner so it can read "this directive lands in the middle of which arcs." Today `bundle.narrative_context.open_threads` is silently dropped. Fix: `bundle_thread_headlines: List[str]` AND `bundle_thread_tags: List[str]`. `${thread_headlines}` and `${thread_tags}` in user_template.
- `[WES-SCHEMA-GAP]` **`scope_hint.geographic_chain` not exposed.** The bundle's `directive.scope_hint` carries `geographic_chain: [{tier_brief, biome, tags, description}, ...]`. Per Agent 8 (Chunks), the planner is blind to existing biome distribution without this. Critical for chunks step decisions. Fix: extract scope_hint sub-fields into user_template variables — `${geographic_descriptor}`, `${geographic_chain}`.
- `[WES-SCHEMA-GAP]` **`scope_hint.purpose` not exposed.** The directive's purpose ("new-quest" / "new-chunk" / "new-faction") is in the bundle but the planner reads only `directive_text`. The planner can INFER purpose from directive_text but it's brittle. Fix: `${directive_purpose}`. Use it as a hard constraint in the planner prompt: "if purpose is `new-faction`, you SHOULD NOT emit chunks-only plans."
- `[WES-SCHEMA-GAP]` **`registry_counts` is "n/a".** Per Agent 1 §4.5, the diversity guard depends on this. Without it the planner re-emits the same patterns. Fix: orchestrator queries `ContentRegistry.list_live(tool)` count by tool + by-locality-tag. `${registry_counts_by_tool}` slot.
- `[FRAGMENT-GAP]` **`bundle_delta` is stringified counts only.** Per Agent 9, the delta's `wms_events_since_last` and `npc_dialogue_since_last` are currently EMPTY at builder time. Even if populated, the planner sees only counts. Surfacing 2-3 most recent significant events as headlines would help. Fix: `${recent_wms_events}` + `${recent_npc_dialogue}` (3-5 entries each, rendered).
- `[FRAGMENT-GAP]` **`adjusted_instructions` from prior rerun not exposed.** The orchestrator threads `adjusted_instructions` through rerun calls but the planner's `_bundle_to_vars` doesn't pull it. Per `wes_orchestrator.py:395`, the orchestrator stores it on the call site — the planner needs it as `${prior_rerun_feedback}` to actually fix what supervisor flagged.
- `[FRAGMENT-GAP]` **Player faction-affinity state at firing address not exposed.** Per Agent 1 / Agent 2 / Agent 6, the planner picks `slots.primary_faction` for NPCs without knowing player's existing relationship to factions in the area. Add `${player_faction_affinities_in_address}` — small dict from `FactionSystem`.

### 4.2 Supervisor inputs — what the supervisor reads

From `LLMSupervisor.review` (lines 130-148):

- `plan_id`, `plan_rationale`, `plan_abandoned`, `plan_steps` (full dicts)
- `bundle_id`, `bundle_directive`, `bundle_firing_tier`
- `tier_log_blob` — condensed one-line-per-tier-result string
- `staged_counts` — counts of steps and tier_results

#### 4.2.1 What's MISSING from the supervisor's inputs

- `[WES-SCHEMA-GAP]` **`firing_address` not exposed** — user_template references `${firing_address}` (line 11 of prompt) but `LLMSupervisor.review`'s variables dict (lines 130-143) doesn't populate it. **Active bug.** The supervisor can't run thematic coherence checks against the firing address because it doesn't know it.
- `[WES-SCHEMA-GAP]` **`parent_summaries` not exposed.** Same shape as the planner gap. Without it, the supervisor's directive fidelity check is shallow — it can compare staged content to directive_text alone, not to the broader narrative the directive lands in.
- `[WES-SCHEMA-GAP]` **`open_threads` not exposed.** Same. The supervisor cannot check "the staged NPC's faction is one of the active threads' subjects" without this.
- `[FRAGMENT-GAP]` **`tier_log_blob` excerpts only 160 chars of raw_response.** Per `_summarize_tier_results` (line 96). 160 chars is one short paragraph; for a quest with `description_full.narrative` of 200 chars + `rewards_prose.summary` of 100 chars + `completion_dialogue` of 200 chars, the supervisor is judging on truncated samples. Trade-off: longer excerpts = larger prompt = slower supervisor. Designer call. **Recommend: extend to 400 chars OR include structured field-by-field summaries instead of raw-response truncation.**
- `[FRAGMENT-GAP]` **No per-step status (primary vs cascade).** Per §2.2.1, supervisor cannot distinguish "this artifact came from cascade resolution" vs. "this artifact was in the original plan." Scope rules apply differently. Add `from_cascade: bool` on the tier-log line.
- `[FRAGMENT-GAP]` **No `verification_preview`.** The orchestrator runs `run_final_verification` AFTER the supervisor. The supervisor cannot read verification results because they don't exist yet. But the supervisor could see a PREVIEW (orphan-detector results, duplicate-detector results) that already ran pre-supervisor. **Critical for failure mode (d).** Add `${pre_supervisor_verification: {orphan_count, duplicate_count, list of issues}}`.
- `[FRAGMENT-GAP]` **No `prior_supervisor_verdict`.** When supervisor reruns, the prior verdict is consumed by the orchestrator to drive `adjusted_instructions` but isn't shown to the next supervisor invocation. For the THIRD supervisor pass (cap-2 reruns mean up to 3 invocations) the supervisor can't see "I asked the planner to fix X last time; did the planner actually fix it?" Add `${prior_supervisor_feedback}`.

### 4.3 Request layer inputs — what the request layer reads

From `RequestLayer.build_one` (lines 258-314):

- `rec: CoemitRecommendation` — `missing_ref_type`, `missing_ref_id`, `requested_by_step_id`, `suggested_intent`, `suggested_slots`
- `registry` — pulled via `list_staged_by_plan` for requesting-payload context
- `bundle` — pulled via `_extract_address_from_bundle`
- `plan_id`, `cascade_depth`, `idx`

#### 4.3.1 What's MISSING from the request layer's inputs

- `[FRAGMENT-GAP]` **`bundle.directive.directive_text` not used.** The request layer reads `bundle.delta.address` for the geographic_address hint but doesn't pull the directive text. When a chunk's `enemySpawns: [moors_raider_grunt]` triggers a hostile request, the cascade-generated hostile's flavor should still know "the directive at this firing was about copper trade." Today it doesn't. Fix: add `bundle_directive_excerpt` to `flavor_hints` (1-sentence brief).
- `[FRAGMENT-GAP]` **`bundle.narrative_context.firing_layer_summary` not used.** Same shape. Cascade-generated content should respect the firing layer's tone.
- `[FRAGMENT-GAP]` **No view of OTHER staged content from the same plan.** When the request layer fires `hostiles` for a missing reference, it can't see the chunk that referenced it. Today: yes it can (the requesting payload IS the chunk). When it fires `materials` from a cascade of hostiles → material, it can see the hostile but not the original chunk that triggered the hostile. **Multi-hop context loss.** Fix: pass through the originating plan's directive + the requesting payload's *originating step's* intent.
- `[FRAGMENT-GAP]` **No view of the planner's full plan rationale.** When cascade fills orphans, it inherits the plan's spirit, not its prose. Fix: pass `plan_rationale` excerpt to the spec.

### 4.4 The bundle as the single shared dependency

All three orchestration tiers (planner, supervisor, request layer) depend on the bundle. Agent 9 specced the contract for what the bundle SHOULD carry post-fix:

| Field | Required by | Status |
|---|---|---|
| `delta.address` | all three | Present, used |
| `delta.layer` / `firing_tier` | planner, supervisor | Present, used |
| `delta.npc_dialogue_since_last[]` | planner | EMPTY at bridge time per Agent 9 |
| `delta.wms_events_since_last[]` | planner | EMPTY at bridge time per Agent 9 |
| `narrative_context.firing_layer_summary` | planner, request layer (proposed) | Present in bundle, used by planner only |
| `narrative_context.parent_summaries{}` | planner, supervisor | Present in bundle, **NEVER read** today |
| `narrative_context.open_threads[]` | planner, supervisor | Present in bundle, **NEVER read** today |
| `directive.directive_text` | all three | Present, used by planner/supervisor; request layer should read |
| `directive.firing_tier` | planner, supervisor | Present, used |
| `directive.scope_hint.geographic_chain` | planner, request layer | Present in bundle, **NEVER read** today |
| `directive.scope_hint.purpose` | planner | Present in bundle, **NEVER read** today |

**Accepting Agent 9's bundle contract verbatim.** Fixing the bundle assembly side (per Agent 9 §5.1) plus extending the orchestration tiers' `_bundle_to_vars` / `review`-input-builder / `build_one` to pull these fields IS the single largest cross-cutting orchestration improvement.

---

## 5. Per-decision provenance table

Every distinct decision the orchestration agent makes, what signals feed it, the gap marker if any.

### 5.1 Planner decisions

| Decision | Signal source | Layer | Existing? | Marker |
|---|---|---|---|---|
| Scope: which tools to emit at this firing_tier | `firing_tier` + planner's `scope_by_firing_tier` prose + `parent_summaries` (for current saturation) | bundle.directive + bundle.narrative_context + planner prompt | Partial — `parent_summaries` not exposed | `[WES-SCHEMA-GAP]` per §4.1.1 |
| Scope: abandonment vs reduced plan | `firing_tier` + `directive_text` coherence judgment | bundle.directive + planner prompt | Yes (prompt has abandonment criteria) | — |
| Tool count per emission | scope rules + `recent_registry_entries` (diversity guard) | planner prompt + ContentRegistry | Partial — `registry_counts` is "n/a" | `[FRAGMENT-GAP]` planner needs registry counts |
| Step `intent` text | `directive_text` + `parent_summaries` (proper nouns) + `firing_layer_summary` + open threads' headlines | bundle.narrative_context + bundle.directive | Partial — all narrative context except firing_layer_summary is dropped | `[WES-SCHEMA-GAP]` per §4.1.1 |
| Step `slots.tier` | `firing_tier` + `directive_text` weight | planner prompt | Yes | — |
| Step `slots.biome` | `firing_address` + `geographic_chain[].biome` | bundle.directive.scope_hint | Partial — `geographic_chain` not exposed | `[WES-SCHEMA-GAP]` |
| Step `slots.primary_faction` (NPCs) | `parent_summaries` + `open_threads[].content_tags` + (proposed) player faction affinity | bundle.narrative_context + (proposed) FactionSystem | Partial — `parent_summaries` and open_threads not exposed; affinity not exposed | `[WES-SCHEMA-GAP]` + `[FRAGMENT-GAP]` |
| Step `slots.given_by` (quests) | co-emitted NPC step OR existing NPC pool at locality | planner prompt + (proposed) `registry_counts.npcs_by_locality` | Partial — registry data missing | `[FRAGMENT-GAP]` |
| Dependency DAG ordering | tool-pair dependencies in prompt's example DAGs | planner prompt | Yes (but see Skills agent DAG-inversion finding §6) | `[FRAGMENT-GAP]` on intent-anchor; resolved via DAG fix + intent-anchor pattern in §6 |
| Co-emission decisions (multi-tool plan) | `directive_text` intent reading + scope rules | planner prompt | Yes | — |
| Rationale text | reconstruction of which directive aspects each step addresses | planner prompt | Yes | — |
| Abandonment decision | 4 prompt-listed criteria | planner prompt + bundle | Yes | — |
| Acknowledgment of unresolved refs (bounce-back) | prior rerun's `adjusted_instructions` (the bounce warning) | wes_orchestrator + plan_resolution | Partial — `adjusted_instructions` not threaded into planner inputs | `[FRAGMENT-GAP]` per §4.1.1 |

### 5.2 Supervisor decisions

| Decision | Signal source | Layer | Existing? | Marker |
|---|---|---|---|---|
| Directive fidelity (pass/fail) | `bundle_directive` + each tier_result's raw_response excerpt | bundle.directive + supervisor prompt + tier_log_blob | Partial — excerpt is 160 chars; bundle context (parent summaries) absent | `[FRAGMENT-GAP]` excerpt size + `[WES-SCHEMA-GAP]` parent_summaries |
| Thematic coherence across artifacts | tier_log_blob cross-reference inspection | tier_log_blob | Yes — but the supervisor reads truncated excerpts | `[FRAGMENT-GAP]` excerpt size |
| Scope fidelity vs firing tier | `firing_tier` + step count by tool | bundle.directive + plan.steps | Yes | — |
| Narrative voice (pass/fail) | tier_log_blob excerpts | tier_log_blob | Partial — voice is hard to judge from 160-char excerpts | `[FRAGMENT-GAP]` excerpt size |
| Obvious balance tells | tier_log_blob numeric extraction | tier_log_blob | Partial — same excerpt issue + no schema-aware tier-band reference | `[FRAGMENT-GAP]` |
| NPC v3 / Quest v3 sanity | tier_log_blob v3-field inspection | tier_log_blob | Partial — same | `[FRAGMENT-GAP]` |
| Rerun vs hard-fail decision | failure category judgment | supervisor prompt | Yes | — |
| `adjusted_instructions` content | specific fix prescription | supervisor prompt + failure category | Yes | — |
| **Post-cascade orphan verification** | `dispatch_result.staged_content_ids` + xref scan | (proposed) `pre_supervisor_verification` | **NO — not surfaced to supervisor** | `[FRAGMENT-GAP]` per §4.2.1, **failure mode (d)** |
| Sacred biome / sacred entity shadowing check (Chunks-derived) | staged geoTypes + sacred namespace registry | (proposed) sacred-shadowing detector + supervisor prompt | NO — supervisor doesn't get sacred registry as context | `[FRAGMENT-GAP]` — discussed in Chunks trace; add as supervisor input |
| Database-reload-pipeline gate check (Materials/Hostiles-derived) | tool name + reloader registry | (proposed) | NO — supervisor doesn't know which tools have live-reload paths | `[FRAGMENT-GAP]` — should refuse-to-commit when reload isn't wired |

### 5.3 Request layer decisions

| Decision | Signal source | Layer | Existing? | Marker |
|---|---|---|---|---|
| Whether to skip planner+hub vs. mint synthetic plan | `find_runtime_orphans` results (deterministic detection) | plan_resolution | Yes — pure code, deterministic | — |
| `target_tool` for spec | `rec.missing_ref_type` | plan_resolution | Yes | — |
| `required_id` | `rec.missing_ref_id` | plan_resolution | Yes | — |
| `item_intent` for spec | `rec.suggested_intent` else synthesized | plan_resolution + RequestLayer | Yes | — |
| `flavor_hints.referenced_by_narrative` | requesting payload's narrative excerpt mined from registry | ContentRegistry | Yes | — |
| `flavor_hints.geographic_address` | bundle.delta.address | bundle | Yes | — |
| `hard_constraints.tier` | requesting payload tier (default 1) | ContentRegistry payload | Yes | — |
| `hard_constraints.address` | bundle.delta.address | bundle | Yes — but should be richer per §2.3.1 | `[WES-SCHEMA-GAP]` for geographic_chain |
| **Narrative-context propagation to executor_tool** | bundle.narrative_context.firing_layer_summary | bundle | NO — request layer doesn't pull narrative context | `[FRAGMENT-GAP]` per §4.3.1 |
| **Multi-hop request chain context preservation** | upstream requesting-payload's originating step | (multi-hop walk through registry) | NO — single-hop only today | `[FRAGMENT-GAP]` per §4.3.1 |
| Dedup vs prior cascade-pass | `seen: set` in `build_specs` line 240 | RequestLayer | Yes | — |
| Cascade-depth cap (terminate vs continue) | `MAX_RUNTIME_CASCADE_DEPTH` | plan_resolution constants | Yes | — |

### 5.4 The 9-rung WMS-extraction walk — applied to "what does the orchestrator need to know about player history?"

User direction: **"be stringent on any WMS gaps and do not allow the agents to use it as a way to escape problem solving."**

I was tempted twice. Walked both 9-rung paths in writing.

#### 5.4.1 Temptation A: "Planner should know recent player content-discovery patterns to avoid re-generating shapes the player has already seen."

Use case: planner has just received a `<WES purpose="new-skill">` firing at salt-moors region. Should it emit a damage-focused combat skill, a utility skill, or a crafting skill? Knowing what the PLAYER has actually used / learned / overused at this region would shape the answer.

1. **Direct query.** Is there a single WMS event "player learned skill X at locality Y"? Yes — `record_skill_learned` writes to StatStore + emits SKILL_LEARNED on the bus. The evaluator `progression_skills.py` interprets these into L2 narrative rows. **Pass.**
2. **Adjacent events.** Player's recent combat at this region (`combat_kills_regional_*`), recent crafting (`crafting_*`), recent gathering (`gathering_regional`) all carry tags reflecting the kind of activity. Aggregating across these tags tells you "the player is combat-heavy this week at this region."
3. **Negative patterns.** Skills the player has LEARNED but never USED — the most-skill-but-never-fired pattern is a signal that generated skills aren't sticking. Detectable from StatStore as `skill.learn_count > 0 AND skill.use_count == 0`.
4. **Aggregation.** `daily_ledger` and `StatTracker` already aggregate skill usage per discipline, per region. The data is there.
5. **Trajectory.** Skill-use trends over recent game-days — combine `StatTracker.skill_use_count_by_day` filtered by region.
6. **Cross-layer climb.** NL2 narratives at the locality reference "the player's hand grows heavy with the copperlash" — interpretation captured in chronicle voice. Available as `firing_layer_summary` IF the leak is fixed; available as `parent_summaries` (NL3) for trans-locality patterns.
7. **Cross-entity composition.** Skill-use × player-class affinity × locality → a fingerprint of the player's local playstyle.
8. **Stat / ledger lookup.** `StatTracker.activity_profile(locality_id)` — proposed accessor that returns `{combat: 0.6, gathering: 0.3, crafting: 0.1}`. Doesn't exist yet but is trivially constructible from StatStore. Cheap.
9. **Trigger history.** Recent `SKILL_LEARNED` triggers per region accessible via the bus event log if persisted; otherwise via the daily_ledger aggregation.

**Verdict.** NOT a WMS gap. The signal is reachable through (1), (4), and (8). The actual gap is at the planner-input-assembly layer: `_bundle_to_vars` doesn't fetch player activity profile. Marker: `[FRAGMENT-GAP]` — orchestrator fetches `StatTracker.activity_profile(firing_address.locality)` and splices as `${player_activity_profile}` into planner user_template.

#### 5.4.2 Temptation B: "Supervisor should know prior plan failures at the same address to avoid recommending the same fix repeatedly."

Use case: supervisor has just been asked to verify a tier-4 plan that has `slots.primary_faction = guild:moors_raiders` for an NPC. Two firings ago, the supervisor failed an NPC for the same faction at this address. If the supervisor can see that history, it can adjust its judgment ("the planner is doubling down on a faction the world is moving away from — this is now a structural failure, not a fixable one").

Walking the 9 rungs:

1. **Direct query.** Is there a WMS event "supervisor verdict at address X was Y"? No — supervisor verdicts aren't published as WMS events. **Fail at WMS layer.** But: are supervisor verdicts persisted? Yes, via `observability.write_supervisor` — logged to disk per plan_id. Not a WMS event but a log.
2. **Adjacent events.** WES plan run completions / failures at the firing address. `WESMetrics` records pass/fail but not address-tagged. Partial.
3. **Negative patterns.** Has this address NOT received a successful commit in N firings? Detectable from observability logs + registry diff.
4. **Aggregation.** `WESMetrics` aggregates pass/fail counts at the plan level. Could be extended to per-address. Cheap.
5. **Trajectory.** Pass rate at this address trending down — early warning of structural issue.
6. **Cross-layer climb.** Not applicable; this is WES-internal supervisor history, not WNS narrative.
7. **Cross-entity composition.** Could intersect "failed plans" × "common failure_check" → patterns ("at this address, thematic_coherence fails 80% of the time on quests").
8. **Stat / ledger lookup.** No supervisor-history ledger exists. **THIS IS THE TRUE GAP — but it's a WES-side observability gap, not a WMS gap.**
9. **Trigger history.** Same shape.

**Verdict.** NOT a WMS gap. Supervisor history is observability data, not world-memory data. The gap is in `WESMetrics` / `observability` not providing address-tagged supervisor history. Marker: `[FRAGMENT-GAP]` — add `WESMetrics.recent_supervisor_outcomes_at_address(address)` and pass `${recent_supervisor_history_at_address}` to the supervisor prompt. Mirrors how `recent_registry_entries` is plumbed for content tools.

**Zero `[WMS-GAP]` markers raised in this trace.** Consistent with Wave 1 and Wave 2. WMS is solid. The gaps are at the bundle-assembly-to-orchestration-tier boundary and at the orchestrator-to-prompt-input boundary.

---

## 6. Cross-features — what orchestration shares, and what's per-tool

### 6.1 Shared across all 8 content tools

The orchestrator is by definition cross-cutting. The shared infrastructure:

- **The bundle assembly contract** (per Agent 9 §5). One slice-extension fix benefits all 8 tools. The planner's input set, the supervisor's input set, and the request-layer's spec construction all read from the same bundle.
- **The scope-by-firing-tier prose** in the planner prompt (§8 — the centerpiece). This is the rulebook for "how big is the right plan for tier N." Tunes universal cross-tool behavior.
- **The supervisor's 6 checks.** Apply uniformly to every tool's output. The 6 categories are tool-agnostic.
- **The orphan detector + request layer** as deterministic xref-resolution machinery. Per-tool xref keys differ (per `_ID_KEY_CANDIDATES`), but the resolution mechanism is identical.
- **`DEFAULT_RERUN_BUDGET`, `MAX_RUNTIME_CASCADE_DEPTH`, `MAX_CASCADE_STEPS_PER_PASS`.** Single tunables affecting all plans.

### 6.2 Per-tool customization the orchestrator must support

- **Per-tool scope discipline.** Tier-2 firing can emit `materials` but not `chunks`; this is per-tool, encoded in the planner prompt's scope_by_firing_tier text. **Centerpiece work — see §8.**
- **Per-tool `slots` shape.** NPC steps want `home_chunk, primary_faction`; quest steps want `given_by, quest_type, objective_type, target_id`; chunk steps want `theme, primary_resource_ids, primary_enemy_ids`. Planner prompt enumerates per-tool slot vocabularies; hub interprets.
- **Per-tool intent-shape guidance.** A skill intent says "name discipline + lineage + mechanical signature"; a material intent says "name biome + tier + role." Per-tool prose guidance in the planner prompt OR per-tool hub-side `step.intent` parsing rules.
- **Per-tool DAG dependency patterns.** Skills/NPCs/Quests have the most cross-tool dependencies; Materials/Nodes have the fewest. The example DAGs in the planner prompt enumerate the common shapes.
- **Per-tool registry diversity check.** `recent_registry_entries` reads per-tool from the registry; the supervisor needs per-tool counts.

### 6.3 The Skills DAG ordering question — my verdict

Skills agent (Trace 06) surfaced: planner currently emits `[skills, npcs]` (skills before NPCs in the DAG). The skill landed first; the NPC referencing it lands second; the skill tool's writer had no NPC narrative to anchor against; the skill's `narrative` field is voice-blind to the teacher.

**Three options:**

**Option 1: Fix the DAG — emit `[npcs, skills]` instead.** NPC's `services.teachableSkills` becomes a forward reference resolved by the orphan-detector or request layer at runtime.

Pros: NPC narrative is fully present when the skill tool writes its narrative. Skill can reference the teacher by proper noun.

Cons: NPC tool's `teachableSkills: [skill_id]` references a skill that doesn't exist yet at NPC-write time. This is exactly the orphan pattern the request layer handles — the NPC commits with `teachableSkills: [proposed_skill_id]`, the request layer detects the orphan, mints the skill spec at depth-1 cascade with `flavor_hints.taught_by_npc_id` set, the skill tool writes its narrative knowing the NPC. **The cascade chain becomes the architectural answer.**

But: NPC's narrative ALSO references the skill ("I teach the moors-stone bind"). NPC writes about a skill that doesn't exist. The phrase the NPC uses for the skill MAY differ from what the cascade-generated skill ends up named. **Mismatch.**

**Option 2: Keep DAG `[skills, npcs]`, pass artifact summaries forward.** Skills landing first commits a `SkillDefinition` with `name: "Copperlash Gash"`. The NPC hub, on its turn, pulls the staged skill summary from `ContentRegistry.list_staged_by_plan(plan_id)["skills"]` and passes `flavor_hints.skill_to_teach_summary` to the NPC tool. NPC writes its `teachableSkills: ["copperlash_gash"]` AND its narrative ("I teach the copperlash gash, salt-bound and bleeding"). Skill tool, however, still wrote first without NPC context.

Pros: NPC references the canonical skill name.
Cons: Skill tool still writes blind to teacher voice.

**Option 3: Both DAG fix AND intent-anchor pattern.** Emit `[npcs, skills]` so the NPC narrative is canonical AND pass artifact summaries forward via the dispatcher (`step_slots` references staged content). The skill tool sees the NPC's narrative-text + voice + faction; it writes a skill that BELONGS to the teacher. The NPC initially commits with `teachableSkills: [proposed_skill_id]`; the orphan resolver fires the skill at cascade-depth-1; the skill commits; database reload pulls both in.

**The NPC narrative dilemma in Option 1 (mismatch between NPC's narrative phrase and skill name) is mitigated by Option 3:** when the NPC writes "I teach the moors-stone bind" with `teachableSkills: ["moors_stone_bind"]`, the cascade-generated skill tool sees `required_id: "moors_stone_bind"` and writes the skill USING that name. **The proper noun the NPC coined IS the skill name.** Then the skill's narrative anchors back to the NPC via `flavor_hints.taught_by_npc_id`.

**My verdict: BOTH. Fix the DAG to `[npcs, skills]` (and same pattern for any teacher-coupled feature), AND ensure artifact-propagation (step_slots passes staged-content summaries forward).** The cascade chain naturally fills in the dependent. This is the architectural answer the request layer was designed for; we just need to extend it to handle these "teacher names a thing" cases consistently.

Same answer applies to other ordering dependencies the prior traces surfaced:
- **Quest needs NPC giver first?** Yes — `[npcs, quests]`. Quest tool reads NPC's voice via staged-content + `flavor_hints.giver_voice_anchor`. *(This matches Agent 1's quest trace explicitly.)*
- **Hostile needs chunk first?** No — chunk co-emits with hostile reference, request layer resolves if needed. The hostile doesn't need chunk-narrative to write its archetype; the hostile's archetype is the upstream signal that drove the chunk.
- **Quest needs hostile first (for kill_target)?** Optional. If the directive is "hunt the copperlash riders," the hostile probably exists from a prior firing OR co-emits. If neither, request layer fires hostile at cascade-depth-1.
- **Title needs quest first?** Yes when title is `granted_by_quest_id`. Same pattern: `[quests, titles]` with artifact-propagation.

**Generalized rule for the planner prompt's DAG section:**

> When tool A's narrative content REFERENCES tool B's proper noun (an NPC's narrative mentions a quest, a skill's narrative mentions a teacher, a quest's narrative mentions a hostile), tool B emits FIRST. When tool A's STRUCTURAL field references tool B's id (`teachableSkills`, `enemySpawns`, `drops`), use either co-emission (same plan step) or orphan-cascade (request layer handles).

This generalization is the §8 prose work too — the DAG patterns in the planner prompt should follow this rule consistently. Today they don't (the example shows `[skills] -> [npcs]` for the moors-copper scenario).

### 6.4 Cross-feature concerns the prior traces flagged that land in my scope

- **Bundle's `parent_summaries` leak** (Agent 1, Agent 9, every Wave 2 agent). My planner's `_bundle_to_vars` is one of the two places to fix it.
- **`npc_dialogue_since_last[]` / `wms_events_since_last[]` empty in bundle** (Agent 9). Bundle bridge fix; my planner depends on the populated form.
- **Geographic chain not surfaced** (Agent 8). My planner and supervisor must expose it.
- **DAG ordering inversion** (Agent 6). My response is §6.3 above.
- **5 silent wiring failures in Nodes** (Agent 5). One is supervisor-relevant: xref reads `materialId` but schema is `drops[]`. My supervisor's xref-mismatch check should catch this — but supervisor doesn't currently know about xref-key shape mismatches (that's xref_rules' job). The supervisor's role here is to recognize "the orphan detector flagged a hostile's drops field but the dispatcher's pre-supervisor xref scan didn't flag it" — i.e., trust the orphan detector's verdict and surface unresolved-after-cascade as fail-no-rerun.
- **Database reload gaps** (Materials, Hostiles, Nodes, Titles). My supervisor SHOULD verify the reload pipeline is live before committing content for a tool whose DB doesn't reload — see §5.2 table entry. Today supervisor is blind to reload-pipeline state. `[FRAGMENT-GAP]` — surface this in supervisor prompt as `${tools_with_live_reload}`.
- **`geoTypes` collision can suppress sacred biomes** (Chunks). My supervisor's thematic coherence check is the natural place to catch sacred-shadowing. `[FRAGMENT-GAP]` — pass sacred-namespace registry summary to supervisor.
- **WNS has no player-facing UI** (Agent 9). Out of orchestration scope. But: supervisor failures rolling back content leaves WNS narrative orphaned. Address by either (a) supervisor failure publishes `WNS_NARRATIVE_NEEDS_RETRACTION` event so WNS can write a retraction row, OR (b) defer until WNS UI exists — supervisor failures are silent until then. Designer call.

---

## 7. Storage / timing design

### 7.1 Bundle assembly cadence — one bundle per WNS `<WES>` emission

Per Agent 9 §7.1: one WNS firing produces 0-2 `<WES>` calls (capped). Each becomes one bundle, one `WNS_CALL_WES_REQUESTED` event, one orchestrator plan run. Multi-directive emissions produce N separate bundles, each carrying the full state.

**Orchestration implication.** The orchestrator's `_on_bus_event` handles one bundle at a time. **There is no bundle batching across firings today.** Two bundles fired in close succession produce two independent plans; the second's planner does NOT see the first's staged content (because the first hasn't committed yet). **This is a race-condition risk** — two simultaneous firings at the same locality can produce conflicting plans (two NPCs of the same faction with overlapping role) that both pass supervisor and both commit.

`[FRAGMENT-GAP]` **Orchestrator-level bundle queue with same-address coalescing.** Suggested: bundles arriving within N seconds (designer-tunable) at the same address are merged into a multi-directive bundle. Planner runs once, plans across both directives. Eliminates the race. Defer — measure incidence in playtest first.

### 7.2 Multi-purpose dispatch — one bundle → many directives

Per Agent 9 §7.1: a future bundle shape could carry `directives[]: List[WNSDirective]`. The planner would author one plan covering all purposes.

**Orchestration implication.** If we move to multi-directive bundles:
- Planner prompt needs `${directives[]}` instead of single `${directive}`.
- Supervisor scope check applies to the SUM of directives (a tier-3 firing with both `new-npc` AND `new-skill` directives — does the plan respect tier-3 scope for both?).
- Request layer is unchanged (operates on staged orphans, not on directives).

Defer until WNS-side change lands.

### 7.3 Supervisor batching strategy

Today: supervisor runs ONCE per plan pass, after all dispatch + cascade complete, before commit.

Alternative: per-step supervision (a la per-step `Verdict` from §2.2.1). Each tool's output is supervised individually as it stages.

**Trade-off.**
- One-pass supervision: lower LLM cost (1 call per plan); supervisor sees full picture (cross-artifact coherence); cannot partial-rerun.
- Per-step supervision: higher cost (N calls per plan); supervisor catches issues early; can partial-rerun cheap.

**Recommendation: stick with one-pass supervision for v4.** The cost saving outweighs the partial-rerun benefit. Per-step is a future endpoint (§9). The current architecture is the right v4 call.

### 7.4 Request-layer caching

Today: request layer is stateless per cascade pass (`RequestSpecBatch` constructed fresh). No cross-plan caching.

**Should it cache?** Specifically: if plan A's cascade generates `moors_copper`, and plan B (later, same session, same locality) ALSO references `moors_copper`, plan B's cascade doesn't need to regenerate — the registry has it from plan A's commit. The orphan detector's pre-cascade probe (`find_runtime_orphans`) already checks `list_live` so registry-cached content IS reused. **This is correct architecture; no orchestrator-level cache needed.**

The one case where a plan-pass-local cache helps: cascade-depth-1 generates `moors_copper`; cascade-depth-2 generates a hostile that drops `moors_copper`; cascade-depth-2's xref to `moors_copper` should resolve to the depth-1 staged content (which `list_staged_by_plan` provides). **Today this works via `list_staged_by_plan` in `_find_staged_payload`.** Correct architecture.

### 7.5 Plan + bundle log retention

Per Agent 9 §7.4: bundles serialize to JSON; logs accumulate.

**Orchestrator-side:** plan logs sit in `llm_debug_logs/wes/<plan_id>/`. Retention policy: none. Save bloat in long playthroughs.

`[FRAGMENT-GAP]` **Retention policy on plan logs.** Suggested: keep last N plans per session, or last N hours. Cheap to implement; matters at scale. Designer-tunable.

### 7.6 Adjusted-instructions threading

When supervisor sets `rerun=true` with `adjusted_instructions`, the orchestrator (line 549) passes `adjusted_instructions` to the recursive `run_plan` call. But the planner doesn't read it — per §4.1.1, `_bundle_to_vars` doesn't pull `adjusted_instructions`.

**This is an active bug.** Today the rerun mechanism is one-way — supervisor asks for a fix, planner doesn't see the request. The plan it generates on rerun is statistically the same plan (same temperature). Trivially fixable:
- `WESOrchestrator.run_plan` stores `adjusted_instructions` on `self._pending_rerun_instructions` (or passes to planner instance).
- `LLMExecutionPlanner.plan(bundle)` reads pending_rerun_instructions and threads into `_bundle_to_vars` as `${prior_rerun_feedback}`.
- Planner prompt's user_template: "If you received feedback from a prior supervisor pass: ${prior_rerun_feedback}. Address each named issue."

**This fix is small AND solves a real failure mode.** Add to backlog.

### 7.7 Cascade-vs-supervisor ordering

Today: dispatch → cascade → supervisor → verification → commit. Cascade runs BEFORE supervisor, so supervisor sees the full universe of staged content (primary + cascade-generated).

Alternative: cascade AFTER supervisor pass. Supervisor reviews primary plan only; if passes, cascade fills orphans; if fails, no cascade. Saves cascade work on failed plans.

**Trade-off.** Today's order means a 95%-cascade-passes plan can fail supervisor on a cascade-introduced issue. Alternative order means cascade work is wasted on cascade-cause-supervisor-fails plans — but those should be rare. **Recommendation: stick with today's order.** Cascade is cheap relative to supervisor; cascade-AFTER-supervisor means supervisor doesn't see the full content universe and can pass a plan that cascades into incoherence. Today's order is correct.

---

## 8. `scope_by_firing_tier` design — the centerpiece

Per user direction and memory `next_task_wns_wes_backwards_design.md`: this prose is the highest-leverage prose in the orchestration system. It is the rulebook the planner reads at every dispatch decision. It determines what content lands at what scale; it determines whether tier-2 firings can spawn quests (no), whether tier-4 firings can spawn nations (no), whether tier-7 firings can spawn world-shifts (yes).

The current prose (in `prompt_fragments_wes_execution_planner.json` `_core.system`):

```
Tier 1 (chunk):   Tightly local. Allowed: 1 material OR 1 node OR 1 minor hostile. Forbidden: NPCs, quests, chunks, factions, world-shifts.
Tier 2 (locality): Small flavor. Allowed: 1-2 of [material, node, hostile, skill]. Forbidden: NPCs, quests, chunks, factions.
Tier 3 (district): Narrow-medium. Allowed: 1 NPC + 1-2 of [material, node, hostile, skill, title]. Forbidden: chunks, world-shifts, faction creation.
Tier 4 (region):  Medium. Allowed: 1 chunk + cross-tool sets (3-5 steps) tied to existing biomes. NPCs and quests now in scope. Forbidden: new nations, world-shifts.
Tier 5 (province): Medium-broad. Allowed: cross-region content sets, new faction interests via NPC affinities. Forbidden: new nations, world-shifts.
Tier 6 (nation):  Broad. Allowed: cross-national dynamics, new regional powers, multi-NPC arcs. Forbidden: world-shifts.
Tier 7 (world):   Full scope. Anything goes including world-shifts and new chunk taxonomies.
```

This is correct in spirit and shape. **It is also the v3.1 scaffolding the designer hasn't reviewed against playtest data.** Below is my recommended refinement, building from prior traces' insights.

### 8.1 The principle behind the scope rules

The principle is *narrative authority*. A tier-2 firing is the narrative authority of a locality — gossip-scale; it can name a new material in the woodshed but not a new captain commanding the moors. A tier-4 firing is the authority of a region — chronicler-scale; it can name a new captain, a new chunk-territory, a vendetta hunt. A tier-7 firing is the authority of the chronicler of ages — it can change the metaphysics, end an era, name a new world-spanning order.

Scope discipline isn't just LLM-cost management — it's *narrative coherence*. A locality should not be allowed to invent a new nation. A region should not be allowed to invent a new world.

### 8.2 Per-layer refinement (proposed v4 prose)

Below is my recommended scope_by_firing_tier prose, per layer, with allowed PURPOSES (not just allowed tools) and scope limits per purpose.

**Tier 1 — chunk-scale (NL1; primarily WMS-driven, not LLM-woven).**
- This is WMS L1 — events, not interpretation. No WES firings at this scope. The planner should never receive a tier-1 bundle. Treat tier-1 as abandonment-by-default with reason "tier 1 is event-scale; WES does not author at this scale."

**Tier 2 — locality (NL2, "village-gossip" voice).**
- Purposes allowed: `new-material` (1), `new-node` (1), `new-hostile` (1 minor), `new-skill` (1, must be utility/crafting; combat skills should bubble to tier 3+).
- Purposes forbidden: `new-npc` (gossip should NOT author people; NPCs are district-scale narrative authorities), `new-quest`, `new-chunk`, `new-title`, `new-faction`, `new-hostile` (boss/unique tier).
- Diversity constraint: max 2 steps per plan. Plans of 3+ steps at tier 2 indicate over-emission — downsize.
- Co-emission constraint: `materials -> nodes` ok; `materials -> hostiles` ok; no DAG depth > 2.

**Tier 3 — district (NL3, "pattern-watcher" voice).**
- Purposes allowed: `new-npc` (1; must have explicit `home_chunk` in firing-address's localities; must have `primary_faction` from existing or co-emitted), `new-quest` (1; must reference co-emitted or existing NPC giver), `new-skill` (1-2; combat skills now in scope), `new-title` (1; must reference co-emitted or existing achievement source), `new-material` / `new-node` / `new-hostile` (1-2 each, only as support for above).
- Purposes forbidden: `new-chunk` (chunks are region-scale; districts don't get new biomes), `new-faction` (factions are province-scale), world-shifts.
- Diversity constraint: max 4 steps per plan. The "1 NPC + 1-2 supporting content" cap is the load-bearing rule.
- DAG ordering required: `[npcs, skills?, hostiles?, quests?]` — NPC first per §6.3 fix.

**Tier 4 — region (NL4, "regional chronicler" voice). The fullest content emission tier.**
- Purposes allowed: ALL CONTENT PURPOSES.
- `new-chunk` (1; tier-2 or tier-3 by default; tier-4 chunks only when directive explicitly names a region-defining biome), `new-npc` (1-2; captain/leader-tier OK), `new-quest` (1-2; can chain), `new-skill` (1-2; high-tier OK), `new-title` (1-2), `new-material` / `new-node` / `new-hostile` (full sets; co-emitted with chunks).
- Purposes forbidden: `new-nation`, world-shifts.
- Diversity constraint: max 8 steps per plan. The full moors-copper example (8 steps) is the upper bound. Plans of 8+ steps at tier 4 should be split into multiple plans across multiple firings (the planner abandons one, the WNS fires another).
- DAG ordering required: `[materials, nodes, hostiles, skills, chunks, npcs, titles, quests]` per dependency. Per §6.3.
- **The "biome inheritance" rule**: when emitting `new-chunk` at tier 4, the planner MUST check `${geographic_chain}` for parent region's existing chunks. If the parent region already has 5+ chunk types, the planner should question whether ANOTHER chunk is warranted. (Sacred chunks aren't counted; only WES-generated.)

**Tier 5 — province (NL5, "provincial historian" voice).**
- Purposes allowed: `new-faction` (1; province-scale affinity arc), `new-title` (1-2; provincial achievements), `new-npc` (1-2; leaders / political figures), `new-quest` (1; province-spanning arc start).
- Purposes forbidden: `new-chunk` (chunks belong at tier 4), `new-material` / `new-node` / `new-hostile` (these are sub-province and shouldn't fire at province authority — bubble down to tier 4 NL fragment), `new-nation`, world-shifts.
- Diversity constraint: max 4 steps per plan. Province narrative is interpretive, not generative; the plan should be SMALL and political.
- This is where the `new-faction` purpose is the natural fit. Per current `narrative_fragments_nl5.json:19` ("avoid: new-chunk, new-material, new-hostile"), this aligns with my recommended scope. **No change to NL5 needed.**

**Tier 6 — nation (NL6, "court historian" voice).**
- Purposes allowed: `new-faction` (1; nation-spanning), `new-title` (1; royal / dynastic), `new-npc` (1-2; royalty / dynastic figures), `new-quest` (1; nation-spanning arc).
- Purposes forbidden: world-shifts.
- Diversity constraint: max 4 steps per plan. Nation narrative is political; plans should be small.

**Tier 7 — world (NL7, "chronicler of ages" voice).**
- Purposes allowed: ALL. Including world-shifts.
- Diversity constraint: max 3 steps per plan. World-scale firings are RARE; their plans should be SMALL and CIVILIZATIONAL. A tier-7 firing producing 8 NPCs is a category error.

### 8.3 The scope-by-firing-tier prompt prose — concrete draft

Below is the prose I propose replacing the current scope rules with. Length matches current; rules sharpen per-purpose.

```
SCOPE BY FIRING TIER (the bundle's firing_tier drives this):

Tier 2 (locality) — village-gossip authority. The locality knows materials, nodes, minor hostiles, and utility skills. Allowed: 1-2 steps from {materials, nodes, hostiles-grunt, skills-utility}. Forbidden: NPCs (gossip doesn't author people), quests, chunks, titles, factions. If directive purpose is new-npc/new-quest/new-faction at tier 2, ABANDON with reason "purpose exceeds tier-2 authority."

Tier 3 (district) — pattern-watcher authority. Districts know people who span localities, can spawn supporting content. Allowed: 1 NPC step + 1-2 of {materials, nodes, hostiles, skills, titles, quests}. NPC step REQUIRED to land before dependent quest/skill steps in DAG. Forbidden: chunks (region-scale), factions (province-scale), world-shifts. If purpose is new-chunk or new-faction at tier 3, ABANDON.

Tier 4 (region) — regional chronicler authority. Full content scope. Allowed: 1 chunk step + co-emitted content sets up to 8 steps total. NPCs (captain/leader tier), quests, full materials/nodes/hostiles ecosystems. Forbidden: new-nation, world-shifts. DAG ordering REQUIRED: [materials, nodes, hostiles, skills, chunks, npcs, titles, quests] — content tools that author proper nouns referenced by other tools emit FIRST. If the smallest viable plan requires 9+ steps, ABANDON with reason "scope exceeds tier-4 plan limit; WNS should re-fire."

Tier 5 (province) — provincial historian authority. Political-scale only. Allowed: 1-2 of {factions, npcs-leadership, titles, quests-arc}. Forbidden: chunks, materials, nodes, hostiles (sub-province content should bubble down; if those are needed, the planner should ABANDON with reason "content scope is sub-province; WNS should fire at tier 4 instead").

Tier 6 (nation) — court historian authority. Dynastic-scale. Allowed: 1-2 of {factions-national, titles-royal, npcs-royal, quests-dynastic}. Forbidden: world-shifts.

Tier 7 (world) — chronicler of ages authority. Civilizational. Allowed: up to 3 of any purpose, including world-shifts and new chunk taxonomies. Plans should be SMALL and CIVILIZATIONAL.

CROSS-CUTTING RULES (all tiers):
- DAG ORDERING: tool A that REFERENCES tool B's proper noun in narrative MUST emit AFTER B. Quests reference NPCs → npcs first. Skills reference teachers → npcs first. Hostiles reference materials → materials first. NPCs reference home_chunk → chunks first OR rely on existing chunk.
- CO-EMISSION vs CASCADE: when tool A has a STRUCTURAL field referencing tool B's id (teachableSkills, enemySpawns, drops), prefer co-emission (same plan). When B does not exist and cannot fit in tier scope, leave the reference; runtime cascade (request layer) resolves it.
- BIOME INHERITANCE: when emitting chunks at tier 4+, check ${geographic_chain} for parent region's existing chunk types. If >= 5 WES-generated chunks already exist at this region, ABANDON or downsize.
- FACTION CONSISTENCY: when emitting NPCs at any tier, set primary_faction from ${parent_summaries} or ${open_threads}'s active factions. Never invent a faction outside of the new-faction purpose.
- DIVERSITY: ${registry_counts_by_tool} reflects recent emissions; avoid stacking the same shape.
```

### 8.4 What makes this prose load-bearing

Three properties:

1. **It's the only place where per-tier-per-purpose decisions are encoded.** Once the planner authors a step list, every downstream tier accepts the count as given. The scope decision IS this prose.
2. **It mediates between cost and quality.** A loose rule ("anything at tier 4+") means runaway emission and supervisor overload. A tight rule ("1 material at tier 2") means quests rarely generate at gossip scope. The dial is tunable in this prose alone.
3. **It's the load-bearing prose because every planner call reads it.** A bug here is a bug in every plan.

### 8.5 What the designer must do with this prose

Per CLAUDE.md v8.1 ("architecture is now in designer-grindable state"): playtest this prose. For each layer, fire 10-20 WNS firings with varied directives. Inspect:
- Did the planner produce in-scope plans?
- When directives wanted content outside scope, did the planner abandon (correct) or stretch (incorrect)?
- Are content tools getting enough intent specificity to write good content?
- Are abandonment rates reasonable (< 20% target)?

Tune the per-tier rules based on what playtest surfaces.

---

## 9. Speculative future endpoints (orchestration only — no content tools)

Per user direction: NO new content generators (no `wes_tool_recipes`, no `wes_tool_equipment`, no others). Allowed: shared infrastructure, supervisor-feedback evaluators, predictive planner aids.

### 9.1 `wes_orphan_classifier` — LLM-driven orphan classification for exotic cases

Today the request layer treats every cross-ref orphan as a content request (the missing_ref_type names the tool to dispatch). For *exotic* references — a chunk's `metadata.narrative` mentioning "the Moors-Stone Tradition" as a proper noun that doesn't match any tool's content_id key — the orphan detector drops it silently.

- **Trigger:** orphan detected with unknown target tool or ambiguous classification.
- **Inputs:** the orphan reference text + the requesting payload + bundle's directive.
- **Outputs:** `{classification: tool_name | "no_action", confidence: float, target_id: str | null}`.
- **Latency budget:** part of the runtime cascade. < 2s.
- **Cost:** rare invocation — only when deterministic orphan detector returns ambiguous results.

Endpoint count: +1 LLM task. **Probably premature** — quantify "exotic orphan rate" in playtest first; only build if rate > 5%.

### 9.2 `wes_supervisor_feedback_evaluator` — designer-tuning evaluator on supervisor history

Today supervisor history accumulates in observability logs. No system reads it back. A long-running evaluator could digest "the supervisor failed thematic_coherence at salt_moors 15 times this week — pattern detected: the directive consistently asks for X but the planner emits Y."

- **Trigger:** periodic (every N WNS firings) or on-demand from designer tooling.
- **Inputs:** observability log corpus of supervisor verdicts at an address, filtered by failure_check category.
- **Outputs:** a designer-facing report — "structural failure pattern at <address>: <pattern>; suggested fix: <prose>."
- **Latency budget:** offline, not real-time.

Endpoint count: +1 LLM task. Tuning surface, not runtime. Suggested home: Prompt Studio's "Coverage Health" panel.

### 9.3 `wes_predictive_planner` — pre-fetch likely future firings

When WNS firings cluster at a region (3 NL3 firings in 5 minutes around salt_moors), the planner could ANTICIPATE the next firing's plan and pre-build a candidate plan against a synthetic future bundle. If the actual firing's bundle matches predicted shape, dispatch the pre-built plan with confirmation.

- **Trigger:** WNS firing density exceeds threshold at an address.
- **Inputs:** recent bundle history + thread state.
- **Outputs:** speculative plan.
- **Latency budget:** offline / async.

Endpoint count: +1 LLM task. Heavy speculation. Defer.

### 9.4 `wes_per_step_supervisor` — supervisor that operates per-tool, not per-plan

Per §2.2.1 and §7.3: per-step supervision enables partial-rerun. A per-step supervisor reviews EACH artifact as it stages, emits per-step Verdict. Failed step → rerun ONLY that step.

- **Trigger:** post-dispatch per step.
- **Inputs:** the single step + its tier_result + bundle directive.
- **Outputs:** per-step Verdict + suggested adjustment.
- **Latency budget:** < 1s per step.
- **Cost:** N supervisor calls per plan (N = step count).

Endpoint count: +1 LLM task OR refactor of existing supervisor. **Higher-value than the predictive planner; lower-cost than the supervisor history evaluator.** Probably my top speculative pick. Build only after measuring v4 supervisor failure-rerun patterns — if "1 bad artifact tanks the whole plan" is the dominant failure mode, per-step is worth it.

### 9.5 `wes_bundle_coalescer` — multi-firing bundle merge

Per §7.1: race-condition risk when multiple WNS firings target the same address in rapid succession. A coalescer LLM (or, more likely, deterministic code) merges close-in-time bundles into a single multi-directive bundle.

- **Trigger:** WNS firing arrives while another at same address is in-flight.
- **Inputs:** new bundle + in-flight bundle.
- **Outputs:** merged bundle with `directives[]` list.
- **Latency budget:** real-time, < 100ms (deterministic) or < 500ms (LLM).

**Probably deterministic, not LLM.** Defer until WNS-side `directives[]` lands.

### 9.6 `wes_scope_tuner` — automatic scope_by_firing_tier prose evolution

Per §8: scope rules are designer-tuned in playtest. A meta-LLM could read playtest telemetry (abandonment rate, supervisor failure rate by tier, scope-violation rate) and SUGGEST scope rule adjustments to the designer.

- **Trigger:** post-playtest review.
- **Inputs:** telemetry + current scope_by_firing_tier prose.
- **Outputs:** suggested prose edits with rationale.
- **Latency budget:** offline.

Endpoint count: +1 LLM task. Designer-tuning aid; not runtime. Cheap to add to Prompt Studio.

### 9.7 `wes_dispatcher_priority_arbiter` — when multiple cascade orphans compete for limited cascade-depth budget

Per `MAX_CASCADE_STEPS_PER_PASS = 8`: when a chunk template names 12 hostiles, the cascade fires 8 and silently drops 4. Which 4? Today: deterministic order from `find_runtime_orphans`'s output. Suggested: an LLM arbiter that prioritizes by narrative-importance — the chunk's signature hostile gets generated; a random gather-target less critical to the chunk's voice gets dropped.

- **Trigger:** cascade fanout exceeds cap.
- **Inputs:** the full orphan list + the requesting payload's narrative.
- **Outputs:** prioritized N orphans to resolve.
- **Latency budget:** < 1s.

Endpoint count: +1 LLM task. Low priority — the cap is high enough that 12-hostile cascades are rare.

### 9.8 The bigger speculative architecture: an "orchestration layer 0"

A speculative idea: above the planner, a "what is the right purpose for this firing?" tier. Today WNS authors the purpose; planner inherits it. But WNS doesn't see the registry. A meta-orchestrator that re-reads the bundle's directive_text and PROPOSES "the right purpose for this firing is `new-faction`, not the `new-npc` WNS picked, because the directive's narrative implies a faction is rising" would catch WNS-side mis-prioritization.

**Heavy.** Probably wrong direction — WNS should be the purpose authority; the planner should respect it; the supervisor catches mismatches. The meta-orchestrator is a layer too far. Flag for discussion; do not build.

### 9.9 Speculative endpoint count summary

Pragmatic shortlist after consolidation:
- `wes_per_step_supervisor` — strongest candidate, build after measuring v4 patterns.
- `wes_supervisor_feedback_evaluator` — designer-tuning aid, Prompt Studio integration.
- `wes_scope_tuner` — designer-tuning aid, Prompt Studio integration.

Defer or skip:
- `wes_orphan_classifier` (rare; measure first)
- `wes_predictive_planner` (speculative; heavy)
- `wes_bundle_coalescer` (probably deterministic, not LLM)
- `wes_dispatcher_priority_arbiter` (low impact)
- Orchestration layer 0 (wrong direction)

**Net: 3 candidate orchestration endpoints, all designer-tuning aids except per-step supervisor. NO new content tools per the user's constraint.**

---

## End

Five load-bearing fixes this trace surfaces, in priority order:

1. **Close the bundle → orchestration tier propagation gap.** Accept Agent 9's bundle contract; extend `LLMExecutionPlanner._bundle_to_vars`, `LLMSupervisor.review`'s variables dict, and `RequestLayer.build_one` to read `parent_summaries`, `open_threads`, `geographic_chain`, `scope_hint.purpose`. Wire `firing_address` into supervisor inputs (currently a bug — template references it, code doesn't populate it). Single change benefits planner + supervisor + request layer + every content tool downstream. **Highest leverage in the system.**

2. **Fix the DAG ordering rule + adopt artifact-propagation pattern.** Per §6.3: change planner prompt's example DAGs to put narrative-anchoring tools (NPCs, chunks) BEFORE their dependents (skills, quests). Combine with dispatcher passing staged-artifact summaries forward via `step_slots`. Solves the Skills agent's teacher-voice problem AND every analogous cross-tool narrative-coupling case.

3. **Thread `adjusted_instructions` through to the planner.** Currently the rerun loop is one-way (supervisor asks, planner doesn't see). 5-line fix. Real failure mode resolution. §7.6.

4. **Rewrite `scope_by_firing_tier` prose per §8.3.** This is the designer's prose to author; this trace's draft is a starting point. Playtest 10-20 firings per tier; tune.

5. **Surface pre-supervisor verification + post-cascade orphan check to supervisor.** Per §4.2.1 and §5.2: supervisor today doesn't see unresolved-after-cascade orphans. Critical for catching corrosive failure mode (d).

Everything else in this trace — bundle queue coalescing, per-step supervision, orchestrator layer 0, the speculative endpoint matrix — is downstream of those five.
