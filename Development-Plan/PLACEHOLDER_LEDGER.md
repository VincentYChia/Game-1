# World System v4 — Placeholder Ledger

**Purpose**: running ledger of every value, prompt, schema, threshold, and configuration the AI build process has filled in with **placeholders**. The designer walks this doc after the scaffold is complete and surgically replaces placeholders with their real designed values.

**Metaphor**: AI builds the house; designer furnishes it. This ledger is the furnishing list.

**Status**: Living document — updated as P1-P9 scaffold lands. Last updated 2026-04-23 (P0 complete).

---

## How to read this

Each section below names a **category** of placeholder (e.g. "trigger thresholds", "prompt fragments"). Within each category:

- **Location** — the file and symbol.
- **Placeholder value** — what the AI wrote in.
- **What it should become** — designer fills in.
- **Notes** — why this was a placeholder and any constraints that the real value must satisfy.

Symbols:
- `🔧 REVIEW` — designer action required.
- `✅ FURNISHED` — designer has replaced; AI should not touch.
- `🏗️ BUILDING` — AI is still iterating; come back once that phase is done.

---

## 1. LLM Fixture Registry — canonical mock I/O

**Source of truth**: [Game-1-modular/world_system/living_world/infra/llm_fixtures/builtin.py](Game-1-modular/world_system/living_world/infra/llm_fixtures/builtin.py)

Every LLM role has a fixture. Fixtures exist to (a) make the pipeline pseudo-mockable and (b) serve as schema-faithful sample I/O the designer can use as a starting point for prompt design.

| Fixture code | Status | What it should become |
|---|---|---|
| `wms_layer3` | 🔧 REVIEW | Real L3 system+user prompts (already shipped in `prompt_fragments_l3.json` — fixture should mirror that prompt shape if/when WMS is run through the fixture registry). |
| `wms_layer4` | 🔧 REVIEW | Same note as L3. |
| `wms_layer5` | 🔧 REVIEW | Same note. |
| `wms_layer6` | 🔧 REVIEW | Same note. |
| `wms_layer7` | 🔧 REVIEW | Same note; WMS L7 is shipped, fixture is for parity. |
| `wns_layer2` | 🔧 REVIEW | Designer's intended NL2 weaving prompt + a representative JSON response. Output shape commits to `{narrative, threads[], call_wes}`. |
| `wns_layer3` | 🔧 REVIEW | Same output shape; district-scale prompt + response. |
| `wns_layer4` | 🔧 REVIEW | Region-scale. Note: placeholder is where the `call_wes: true` example lives; double-check this is the tier where WES calls commonly fire, or adjust the example. |
| `wns_layer5` | 🔧 REVIEW | Nation-scale. |
| `wns_layer6` | 🔧 REVIEW | Nation-to-world seam scale. |
| `wns_layer7` | 🔧 REVIEW | World embroidery; output includes `dominant_arcs/regions/factions` + `severity`. |
| `wes_execution_planner` | 🔧 REVIEW | Plan schema is committed (`WESPlan.steps[].{tool, intent, depends_on, slots}`); designer writes the real prompt + example plan. |
| `wes_hub_hostiles` | 🔧 REVIEW | XML batch format `<specs><spec intent hard_constraints flavor_hints cross_ref_hints /></specs>`. Real prompt should preserve this format for parsability. |
| `wes_hub_materials` | 🔧 REVIEW | Same XML format. |
| `wes_hub_nodes` | 🔧 REVIEW | Same XML format. |
| `wes_hub_skills` | 🔧 REVIEW | Same XML format. Must compose from existing tag vocabulary only. |
| `wes_hub_titles` | 🔧 REVIEW | Same XML format. |
| `wes_tool_hostiles` | 🔧 REVIEW | JSON matches existing `Definitions.JSON/hostiles-*.JSON` format. |
| `wes_tool_materials` | 🔧 REVIEW | JSON matches `items.JSON/items-materials-1.JSON`. |
| `wes_tool_nodes` | 🔧 REVIEW | JSON matches `Definitions.JSON/Resource-node-1.JSON`. |
| `wes_tool_skills` | 🔧 REVIEW | JSON matches `Skills/skills-skills-1.JSON`. |
| `wes_tool_titles` | 🔧 REVIEW | JSON matches `progression/titles-1.JSON`. |
| `wes_supervisor` | 🔧 REVIEW | Output `{verdict: "pass"|"fail", rerun: bool, notes: string, adjusted_instructions?: string}`. Designer may want to refine the rerun-trigger criteria. |
| `npc_dialogue_speechbank` | 🔧 REVIEW | Speech-bank format committed to `{npc_id, speech_bank: {greeting, quest_accept, quest_turnin, closing}, mentions[]}`. Designer writes personality-specific prompts. |

**Constraint**: the fixture's `canonical_response` must be **parse-valid** for the structure the code expects. If the designer changes the JSON shape, also update the parser code (not just the fixture).

---

## 2. Context bundle schema (P5 will finalize, P0 sketched)

**Source**: [Game-1-modular/world_system/living_world/infra/context_bundle.py](Game-1-modular/world_system/living_world/infra/context_bundle.py)

The bundle is committed as three parts (delta + narrative context + directive). Leaf types and field names:

| Field | Status | Notes |
|---|---|---|
| `NL1Row.extracted_mentions` | 🔧 REVIEW shape | Currently `List[Dict[str, Any]]`. Designer decides keys — at minimum expects `entity`, `claim_type`, `significance`. May want to upgrade to a dataclass. |
| `WMSLayerRow.tags` | ✅ matches shipped WMS | — |
| `ThreadFragment.relationship` | 🔧 REVIEW vocabulary | Currently `open / continue / reframe / close`. Designer may want to add e.g. `fork / merge`. |
| `NarrativeContextSlice.parent_summaries` keying | 🔧 REVIEW | Currently `"{layer}:{address}"`. Simple and stable; designer might prefer a richer key. |
| `WNSDirective.scope_hint` | 🔧 REVIEW | Free-form `Dict[str, Any]`. Designer decides whether to commit to a typed version. |
| `BundleToolSlice.recent_registry_entries` | 🔧 REVIEW shape | Currently `List[Dict[str, Any]]`. Tool-specific fields depend on each tool's registry table schema. |

---

## 3. Graceful-degrade log entries

**Source**: [Game-1-modular/world_system/living_world/infra/graceful_degrade.py](Game-1-modular/world_system/living_world/infra/graceful_degrade.py)

| Placeholder | Status | Notes |
|---|---|---|
| `GracefulDegradeLogger.MAX_BUFFER = 256` | 🔧 REVIEW | In-memory ring buffer size. Ample for dev; designer may want different for production. |
| `DEFAULT_LOG_DIR = "llm_debug_logs/graceful_degrade"` | 🔧 REVIEW | Matches existing `llm_debug_logs/` convention; confirm fit. |
| `_VALID_SEVERITIES` = {info, warning, error} | 🔧 REVIEW | Three-tier is minimal; designer may want critical/fatal. |
| Surface-sink fires only on severity=error | 🔧 REVIEW | Currently WES failures fire visible UI indicator; designer can lower the threshold if they want warnings to also surface. |

---

## 4. WNS — trigger thresholds (P1-P3 will scaffold with placeholders)

Every NL layer has an every-N-events trigger. Starting guesses per §9.Q1 of the working doc:

| Layer | Placeholder N | Config key | Notes |
|---|---|---|---|
| NL2 (locality weaver) | `5` | `narrative.triggers.nl2.events_per_locality` | Placeholder — tune in playtest. |
| NL3 (district weaver) | `5` | `narrative.triggers.nl3.events_per_district` | Placeholder. |
| NL4 (region weaver) | `8` | `narrative.triggers.nl4.events_per_region` | Placeholder. |
| NL5 (nation weaver) | `12` | `narrative.triggers.nl5.events_per_nation` | Placeholder. |
| NL6 (seam weaver) | `15` | `narrative.triggers.nl6.events_world` | Placeholder. |
| NL7 (world embroidery) | `20` | `narrative.triggers.nl7.events_world` | Placeholder. |

Status: **🏗️ BUILDING** — these will be inserted by the WNS agent into `memory-config.json` or a new `narrative-config.json`. The designer replaces each N with real playtest-tuned values.

---

## 5. Narrative tag taxonomy (P1 — CC5 new standalone file)

**Target file**: `Game-1-modular/world_system/config/narrative-tag-definitions.JSON` (WNS-specific, sibling of `tag-definitions.JSON`).

| Placeholder | Status | Notes |
|---|---|---|
| Full narrative tag vocabulary | 🏗️ BUILDING | WNS agent seeds with starter set (thread-stage tags, tone tags, relationship tags). Designer owns the real taxonomy. |
| Address prefixes `thread:` / `arc:` / `witness:` | ✅ committed | Per §4.2b — these are facts, not LLM-writable. |

---

## 6. Prompt fragments (every WNS + WES LLM layer)

**Target files** (all placeholders written by agents, designer replaces):

- `Game-1-modular/world_system/config/narrative_fragments_nl2.json` — NL2 weaving prompt
- `narrative_fragments_nl3.json` through `narrative_fragments_nl7.json`
- `Game-1-modular/world_system/config/prompt_fragments_wes_execution_planner.json`
- `prompt_fragments_hub_hostiles.json`, `prompt_fragments_hub_materials.json`, etc. (5 hub files)
- `prompt_fragments_tool_hostiles.json` etc. (5 tool files)
- `prompt_fragments_wes_supervisor.json`

Status: **🏗️ BUILDING** — each file will be created with minimally valid prompts + schema sections. Designer rewrites the prose for tone, instructions, and examples. The schema must stay synced with the code's expectations (see §1 above for output shapes).

Structure follows existing WMS pattern:
```json
{
  "_meta": { "layer": 2, "purpose": "..." },
  "_core": { "system": "...", "user_template": "..." },
  "_output": { "schema": "...", "example": "..." },
  "context:<hint>": { ... },
  "example:<label>": { ... }
}
```

---

## 7. Planner scope-discipline by firing tier (§5.8)

**Target**: `prompt_fragments_wes_execution_planner.json` — scope-discipline section keyed by `directive.firing_tier`.

| Firing tier | Placeholder scope rule | Notes |
|---|---|---|
| NL2 (locality) | "Narrow scope: small flavor items only. No new NPCs, factions, or biomes." | Placeholder; designer refines. |
| NL3 (district) | "Narrow-medium: small material/node additions, NPC dialogue updates." | Placeholder. |
| NL4 (region) | "Medium: new hostiles/materials tied to biome. No new nations/factions." | Placeholder. |
| NL5 (nation) | "Medium-broad: cross-region content, new faction interests." | Placeholder. |
| NL6 (seams) | "Broad: cross-national dynamics, new regional powers." | Placeholder. |
| NL7 (world) | "Full: anything in scope, including world-shift content." | Placeholder. |

**Why this is critical**: the planner's scope logic is the whole architectural commitment vs. a permissions matrix (§5.8, CC7). Get this prompt text right and the system is configurable via prompt; get it wrong and the LLM over- or under-generates.

---

## 8. Supervisor rerun budget & heuristics (§9.Q12)

**Target**: `prompt_fragments_wes_supervisor.json` + code constant in WES shell.

| Placeholder | Status | Notes |
|---|---|---|
| Rerun budget = `2` | 🔧 REVIEW | Placeholder per v4 Q12 lean. Could be 1 if supervisor rerun quality is inconsistent. |
| Invocation policy | 🔧 REVIEW | Currently "supervisor reviews every plan" (placeholder). Alternatives: only for high-severity directives, or only for multi-tool plans. |
| Supervisor prompt — "what to flag" | 🔧 REVIEW | Placeholder covers "does generated content match directive?". Designer refines with specific checks. |

---

## 9. BalanceValidator stub (§9.Q3)

**Target**: `Game-1-modular/world_system/content_registry/balance_validator.py` (P4 scope).

Placeholder will be a ~50 LOC class that reads `Definitions.JSON/stats-calculations.JSON` for tier multipliers and rejects outliers outside `[0.5x, 2x]` of the nominal.

Status: **🏗️ BUILDING** — content registry agent scaffolds. **🔧 REVIEW** for actual ranges.

---

## 10. Content Registry schema (P4)

**Target**: `Game-1-modular/world_system/content_registry/` — new sibling of `world_memory/`.

| Placeholder | Status | Notes |
|---|---|---|
| Per-tool registry tables: `reg_hostiles`, `reg_materials`, `reg_nodes`, `reg_skills`, `reg_titles` | 🏗️ BUILDING | Fields committed: `content_id, display_name, tier, biome, faction_id, staged, plan_id, created_at, source_bundle_id, payload_json`. |
| `content_xref` table | 🏗️ BUILDING | Fields: `src_type, src_id, ref_type, ref_id, relationship`. |
| Generated JSON file naming: `<tool>-generated-<timestamp>.JSON` | 🔧 REVIEW | Currently timestamps. Designer may prefer sequential numbers. |
| Generated JSON target directories | ✅ matches existing convention | `items.JSON/`, `Definitions.JSON/`, `Skills/`, `progression/`. |
| Commit-time database reload trigger mechanism | 🔧 REVIEW | Placeholder: calls `<Database>.get_instance()._reload()` directly. May need GameEventBus-based notification. |

---

## 11. WES Plan dataclasses (P5)

**Target**: `Game-1-modular/world_system/wes/dataclasses.py`

| Field | Status | Notes |
|---|---|---|
| `WESPlanStep.tool` | ✅ committed | One of: hostiles/materials/nodes/skills/titles. |
| `WESPlanStep.depends_on` | ✅ committed | List[step_id]. |
| `WESPlanStep.slots` | 🔧 REVIEW shape | Currently `Dict[str, Any]`. Tool-specific fields vary — may want typed per-tool variants. |
| `WESPlan.abandoned` + `abandonment_reason` | ✅ committed | — |
| `ExecutorSpec.item_intent` | ✅ committed | — |
| `ExecutorSpec.flavor_hints` / `cross_ref_hints` / `hard_constraints` | 🔧 REVIEW shape | All `Dict[str, Any]`. Designer may want typed variants per tool. |

---

## 12. Backend task routing (existing `backend-config.json`)

WNS/WES LLM tasks need routing entries. Placeholder entries to add:

```json
"task_routing": {
  "wns_layer2": { "primary": "ollama" },
  "wns_layer3": { "primary": "ollama" },
  "wns_layer4": { "primary": "ollama" },
  "wns_layer5": { "primary": "ollama" },
  "wns_layer6": { "primary": "ollama" },
  "wns_layer7": { "primary": "ollama" },
  "wes_execution_planner": { "primary": "claude", "fallback": "ollama" },
  "wes_hub_hostiles": { "primary": "ollama" },
  "wes_hub_materials": { "primary": "ollama" },
  "wes_hub_nodes": { "primary": "ollama" },
  "wes_hub_skills": { "primary": "ollama" },
  "wes_hub_titles": { "primary": "ollama" },
  "wes_tool_hostiles": { "primary": "ollama" },
  "wes_tool_materials": { "primary": "ollama" },
  "wes_tool_nodes": { "primary": "ollama" },
  "wes_tool_skills": { "primary": "ollama" },
  "wes_tool_titles": { "primary": "ollama" },
  "wes_supervisor": { "primary": "ollama" }
}
```

Status: **🏗️ BUILDING** — agents will add routing entries to `backend-config.json`. **🔧 REVIEW** for cloud-vs-local per-task. Default lean per CC: only planner and supervisor (on escalation) allowed cloud.

---

## 13. Model choices per LLM role

Placeholder models (per `backend-config.json` `ollama.default_model`):

| Role | Placeholder model | Notes |
|---|---|---|
| WNS weavers (all) | `llama3.1:8b` | Placeholder from existing config. Designer tunes per role — some layers may benefit from larger models. |
| WES planner | cloud (Claude Sonnet) | Designer may prefer Opus for planning quality. |
| WES hubs | `llama3.1:8b` | Placeholder. |
| WES executor_tools | `llama3.1:8b` | Placeholder. JSON tasks benefit from smaller tuned models — designer may override. |
| WES supervisor | `llama3.1:8b` | Placeholder. Common-sense task; smaller model viable. |

Status: **🔧 REVIEW** — model selection per role is playtest-tuned.

---

## 14. `call_wes` trigger condition (§9.Q10)

**Target**: WNS weaver prompts (per-layer).

Placeholder: weaver LLM output includes a `call_wes: boolean` field; WNS acts on it. Examples in fixtures show both true and false cases.

**Alternatives** the designer may want to consider:
- Thread-count threshold (deterministic)
- Severity threshold (deterministic)
- Arc-stage transition detection (deterministic)

Status: **🔧 REVIEW** — pick the approach. The lean is weaver-self-flag; a deterministic fallback can be layered on top.

---

## 15. Distance-decay depth rules per firing tier (§8.8)

**Target**: `NarrativeDistanceFilter` utility (P1 scope).

Starting shallow-going-outward lean (placeholder):

| Firing tier | Full-detail layers | Brief-summary layers | Not included |
|---|---|---|---|
| NL2 | NL2 + NL1 at locality | NL3-NL7 parents (1-2 sentences) | sibling localities |
| NL3 | NL3 + NL2 at district | NL4-NL7 parents | sibling districts |
| NL4 | NL4 + NL3 at region | NL5-NL7 parents | sibling regions |
| NL5 | NL5 + NL4 at nation | NL6-NL7 parents | sibling nations (unless threaded) |
| NL6 | NL6 + NL5 relevant | NL7 parent | — |
| NL7 | NL7 + NL6 + per-nation NL5 summaries | — | — |

Status: **🔧 REVIEW** — word/token budgets per depth TBD in playtest.

---

## 16. Metrics dashboard counters (P9)

**Target**: `Game-1-modular/world_system/wes/metrics.py`

Placeholder metrics:
- `plans_per_hour` — uncapped counter
- `tool_success_rate` — % successful commit per tool
- `orphan_block_rate` — % of plans blocked by orphan check
- `plan_abandonment_rate` — % of plans abandoned
- `supervisor_rerun_rate` — % of plans where supervisor triggered rerun
- `graceful_degrade_events_per_subsystem` — counter
- `tier_usage_by_backend` — ollama/claude/mock/fixture counts per tier

Status: **🏗️ BUILDING** — P9 agent scaffolds. **🔧 REVIEW** for additional metrics.

---

## 17. Sacred directories / generated content targets

Designer commitment per CLAUDE.md: sacred content JSONs are not mutated. Generated JSONs go to:

- `items.JSON/items-materials-generated-<ts>.JSON`
- `items.JSON/items-smithing-generated-<ts>.JSON` (hostiles drops may reference these)
- `Definitions.JSON/hostiles-generated-<ts>.JSON`
- `Definitions.JSON/Resource-node-generated-<ts>.JSON`
- `Skills/skills-generated-<ts>.JSON`
- `progression/titles-generated-<ts>.JSON`

Status: ✅ **committed** — agents honor this boundary. **🔧 REVIEW** for exact paths if designer wants different naming.

---

## Appendix: how to use this ledger

1. After the full scaffold lands, walk each section.
2. Mark items 🔧 → ✅ as you furnish them.
3. When the real prompt/threshold/schema is in place, add a brief note of any changes downstream (e.g. "also updated `<file>` parser").
4. If a placeholder turns out to be a bad idea altogether, note the replacement and why.

The scaffold is a house, not a design. The house should function in placeholder form (pseudo-mock pipeline runs end-to-end); furnishing is about taste, tuning, and the designer's specific vision.
