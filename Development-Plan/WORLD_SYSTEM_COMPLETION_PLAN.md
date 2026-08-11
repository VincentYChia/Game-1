# World System — Completion Plan (to "pristine professional")

**Goal:** take the World System (WMS → WNS → WES + factions/NPCs/ecosystem) from "certified in the
harness but not connected in the running product" to a **fully wired, quality-gated, verifiable
living-world engine** — done thoroughly, in dependency order, each step with a concrete acceptance
gate so nothing is left half-wired.

**Verified:** 2026-08-11, branch `godot-migration`, against `Game-1-modular/world_system/`.
Every claim carries a `file:line`; code is authoritative. Companion: `GAME_SYSTEMS_BRIEF.md` §9-§12.

---

## Execution status (updated 2026-08-11) — Phase 0 & 1 DONE

- ✅ **Phase 0** — key live (`.env` + `backend_manager` 401→.env fallback hardening); smoketest green.
- ✅ **Phase 1** — **WES now generates real Claude content and COMMITS cleanly end-to-end** (live run:
  `status=committed`, verification passed, 0 step errors; 17 new unit tests green). Delivered:
  - `tools/world_system_driver.py` — headless real-tier runner (the Godot-sidecar seed).
  - `wes/canonical_ids.py` — **canonical-id coordination (approach A) + non-LLM normalizer + `prune_orphan_refs`**,
    wired into `plan_dispatcher` (`_canonical_reconcile`, topological). Solves cross-tool id mismatch.
  - `content_registry/game_content_index.py` — **living index mirroring the game DBs**, refreshed on
    every commit+reload (sacred + invented in sync); `ContentRegistry.exists()` consults it.
  - Fixes: node `resourceId` id-extraction (`xref_rules.py`); cp1252 DB-load-crash (driver stdout utf-8).
- **Discovered along the way (fold into §5/§6):** (a) `ContentRegistry.exists()` was blind to sacred
  content [FIXED]; (b) LLMs invent dangling refs → prune enforces "cross-refs must resolve" [FIXED];
  (c) **#3 tier-result mislabel** — `fixture_tier_result()` stamps `raw_response`/`backend_used="fixture"`
  on REAL results, so the supervisor reviews fixture data not real output [OPEN → Phase 2]; (d) game DBs
  print `⚠` and crash-on-print under piped cp1252 [driver worked around; latent].
- **Remaining decisions:** routing repoint (bulk `ollama→claude` has a per-call cost); flip the 2D
  `game_engine.py:5178` stub wiring (`WES_REAL_TIERS`) — optional, the sidecar is the real target.
- All changes are in the **working tree** (uncommitted).

---

## 1 · The picture — what is actually true

The World System splits cleanly into three truths. The confusion ("I thought WES was done") is
resolved: **it *is* done at the tier level — the LLM planner/hub/tool are built, furnished, and
certified — but those certified tiers were never wired into a running consumer.** The game
orchestrator was left on fixture stubs.

| Layer | State | Evidence |
|---|---|---|
| **WMS L1–L7** (capture → evaluate → consolidate → tag) | ✅ **Built + wired**, incl. L5/L6/L7 row writes | `world_memory_system.py:438,515-526`; `layer{5,6,7}_manager` `insert_event`. (Old "L5-7 don't write" claim is stale.) |
| **WNS weave pipeline** (cascade → weaver → narrative_store → `<WES>`/`<AffinityShift>`) | ✅ **Built + wired** | `wms_to_wns_bridge.py:366 → nl_weaver.run_weaving`; C3/M1 continuity live |
| **WES real LLM tiers** (planner/hub/tool/supervisor) | ⚠️ **Built + certified, NOT wired into a runtime consumer** | Certified via `hub_cert_harness.py` (8/8 × 3 fidelities, F18/F20); but `game_engine.py:5178` inits orchestrator with no tiers → `wes_orchestrator.py:159-162` defaults to **fixture stubs** |
| **Prompt fragments** (NL2-7, 8 hubs, 8 tools, planner) | ✅ **Furnished designer content** (not placeholder) | `narrative_fragments_nl*.json` v3.1; hub/tool fragments carry ability libraries + worked examples; used by the July cert pass |
| **Content DB reload** (all 8 types) | ✅ **Built + wired** | `content_registry.commit → reload_for_tools` → real `reload()` on all 8 DBs |
| **Affinity on quest turn-in** | ✅ **Built + wired** | `game_engine.py:1635 → quest_tool.apply_turn_in → adjust_player_affinity` |
| **quest_reward_adapter, NPC agent dialogue** | ✅ **Built + wired** | `quest_system.py:326,527`; `npc_agent.py` async dialogue |
| **Content-tag governance** (WES) | 🔴 **Absent** — furnished prompts, but no validation library, `NEW:` unrouted | `prompt_fragments_tool_*.json:10` (hardcoded prose); no `validate_tag` in `wes/` |
| **StubSupervisor** at runtime | 🔴 **Always-pass no-op** | `supervisor_tap.py:106` |
| **FactionReputationEvaluator** | 🟠 **Built, not registered** + not routed to WMS | absent from `interpreter.py:105-154`; `FACTION_AFFINITY_CHANGED` not in `BUS_TO_MEMORY_TYPE` |
| **PresenceDriftDetector** | 🔴 **Wired-to-empty** (no writer for its input) + suppressed category | reads `meta.last_activity_day.*` nothing writes; `presence_drift → other → suppressed` |
| **EcosystemAgent** + scarcity topics | 🟠 **Built, never instantiated**; topics dead | `ecosystem_agent.py`; `RESOURCE_SCARCITY/RECOVERED` no subscriber |
| **WNS `ingest_dialogue`/`maybe_weave`** | 🟠 **Orphans** (replaced by the cascade) | zero non-test callers |
| **`ANTHROPIC_API_KEY`** | 🔴 **Dead env var shadows `.env`** → real Claude 401s | `backend_manager.py:197-217` env checked first |

Legend: ✅ built+wired · ⚠️ built, certified, not connected · 🟠 built, not wired · 🔴 wired-but-stub / missing.

---

## 2 · The reframe that decides the plan

**Do not "fix WES" by editing the legacy 2D `game_engine.py`.** That game is being replaced by Godot.
The World System is Python and — like the invention path (`Game-1-Godot/sidecar/invention_sidecar.py`)
— will be consumed by Godot as a **Python sidecar**. WES is already a *pure function of
`(bundle, registry_state)`* with no live queries (`protocols.py:18-19`), so it is trivially
relocatable behind an IPC boundary.

**Therefore the target "runtime" is a headless real-tier World System service, not the 2D loop.**
The same headless driver we build to *verify* the fixes is the seed of the Godot sidecar. This
collapses "flip the game" and "build the sidecar" into one artifact and de-risks everything: we can
run the full pipeline on real LLMs, offline from any game, and assert on committed content.

The flip itself is small and known (~15 lines): construct real tiers from `WESToolRegistry` and pass
them to `orchestrator.initialize(planner=, hubs={n:get_hub(n)}, tools={n:get_tool(n)}, supervisor=)`.
`test_e2e_pipeline.py:122-155` already proves that wiring commits.

---

## 3 · The plan (dependency-ordered phases)

Each phase has an **acceptance gate**; do not advance until it's green. "DoD" = the whole system's
Definition of Done in §4.

### Phase 0 — Unblock (operational, blocks all real-LLM verification)
| # | Action | Acceptance gate |
|---|---|---|
| 0.1 | Rotate/replace the dead `ANTHROPIC_API_KEY` (env shadows `.env`). Optional code hardening: on a 401 from the env key, fall through to `.env` + retry once, loud one-time warning. | `tools/wes_real_llm_smoketest.py` reports a live Claude chain + a successful round-trip `generate()`. |

### Phase 1 — Real-tier verification driver (the substrate everything is verified against)
| # | Action | Acceptance gate |
|---|---|---|
| 1.1 | Build `tools/world_system_driver.py` (headless): sets `WES_DISABLE_FIXTURES=1` + `WES_REQUIRE_REAL_LLM=1`, builds real tiers via `WESToolRegistry(use_stubs=False)`, wires them into `WESOrchestrator`, feeds a canned `WESContextBundle`, runs `run_plan` → `commit` → reload. Mirror `invention_sidecar.py` stdout-purity trick. | A real bundle yields `status="committed"` with `tier_results[*].backend_used != "fixture"` and xref-clean content on Claude (and on a local model). |
| 1.2 | Repoint `wes_hub_*` / `wes_tool_*` routing primaries in `backend-config.json` off disabled `ollama` to `claude` (works via fallback today, but fragile). | Resolved chain for every WES task is a real backend with no reliance on the fallback rescue. |
| 1.3 | (Optional, low priority) Flip the 2D `game_engine.py:5178` behind `WES_REAL_TIERS=1` for anyone still using the 2D build. | With flag on, in-game WES dispatch uses `LLMExecutionPlanner` (not stub). |

### Phase 2 — Output governance (make real generation *safe* before it ships content)
| # | Action | Acceptance gate |
|---|---|---|
| 2.1 | **WES content-tag library + validator** (mirror `narrative_tag_library`): one allow-list per tool generated from the existing hardcoded prose (single source). In `LLMExecutorTool.generate`, post-parse split tags → keep known, drop unknown (log_degrade), route `NEW:`-prefixed to a designer-review sink. Replace hardcoded prose in tool `_output` with `{{TAG_ALLOWLIST}}` injection. | Test: response with `{valid, NEW:foo, bar}` → keeps `valid`, `NEW:foo` in review sink, `bar` dropped+logged. No hardcoded tag list remains in tool `_output`. |
| 2.2 | **Wire the real `LLMSupervisor`** (rides on Phase 1's tier swap — `reg.get_supervisor()`). Verify `_run_supervisor` invokes the real reviewer + the rollback/rerun branch. | A deliberately mismatched directive→content yields `rerun=True` and triggers rollback at least once. |

### Phase 3 — Continuity gaps (the "living" behaviors) — parallelizable
| # | Action | Acceptance gate |
|---|---|---|
| 3.1 | **Faction → narrative** (merge of #4+#8): register `FactionReputationEvaluator` in `interpreter.py`; add `FACTION_AFFINITY_CHANGED → EventType.*` to `BUS_TO_MEMORY_TYPE` so the recorder ingests it. | 3 affinity changes on the bus → an L2 `faction_reputation` interpreted row with a `faction:` tag exists. |
| 3.2 | **Presence drift**: write `meta.last_activity_day.locality.<id>` at runtime (event_recorder / daily boundary); add `presence_drift` to a non-suppressed category in `EVENT_CATEGORY_MAP`. | Activity at locality X day 10 → advance to day 45 → drift scan yields a candidate AND behavior_interpreter dispatches it (not suppressed). |
| 3.3 | **EcosystemAgent** — *design decision first*: wire live (instantiate + tick from gather/deplete events + add a `RESOURCE_SCARCITY` subscriber) OR formally mark dormant in the systems catalog. | If wired: gather→deplete publishes `RESOURCE_SCARCITY` and a subscriber records a WMS/WNS event. If deferred: catalog states "instantiated: no" + a guard test. |
| 3.4 | **WNS orphan cleanup**: delete/hard-deprecate `ingest_dialogue` + `maybe_weave` (dead alt-ingress; cascade is the live path). | No non-test caller remains; WNS suite green. |

### Phase 4 — Godot integration (the real consumer)
| # | Action | Acceptance gate |
|---|---|---|
| 4.1 | Promote the Phase-1 driver to `world_system_sidecar.py` (NDJSON stdin/stdout like `invention_sidecar.py`). Ops: `ping`, `event` (forward WMS/WNS game events), `run_wes` (serialized `WESContextBundle` in), `poll` (committed content + reload signals out — surface `commit()`'s `{files, counts, reload_results}`). | Godot sends a bundle over IPC → receives committed content IDs + a reload signal → spawns/reloads the new content (chunks/npcs/quests live; others flagged). |
| 4.2 | Godot-side bridge: forward the game event stream into the sidecar so its own WNS `BehaviorInterpreter` can synthesize bundles (match `game_engine.py:5200-5216`). | A Godot play session drives a real WES generation end-to-end and the content appears in-world. |

### Phase 5 — Regression lock + certification
| # | Action | Acceptance gate |
|---|---|---|
| 5.1 | Regression guards for the working set (L5-7 writes; all 8 reloads; weave pipeline; affinity turn-in; quest_reward_adapter; NPC dialogue). | Guard tests exist + pass. |
| 5.2 | **Full-pipeline real-LLM certification** (new): bundle → planner → hub → tool → supervisor → commit → reload, scored for parse/count/tier+biome/dedup/leakage/**tag-validity**, at 2-3 fidelities (Haiku + local gemma3/qwen3). Extends `hub_cert_harness.py` to the whole pipeline, not just hubs. | ≥ target pass rate across fidelities; committed content is tag-valid and xref-clean; abandon/rollback rate within tolerance. |
| 5.3 | Update `GAME_SYSTEMS_BRIEF.md` §11/§16 to reflect the wired reality; strike resolved gaps. | Brief matches code. |

---

## 4 · Definition of Done (the whole system is "pristine professional" when…)

1. A **headless real-LLM run** takes a `WESContextBundle` → commits **tag-valid, xref-clean,
   non-fixture** content, with the **real supervisor** gating quality (rollback on mismatch).
2. **Continuity is closed**: affinity changes become L2 narrative; presence drift fires behavior
   directives; the ecosystem is either live-with-a-consumer or explicitly dormant (no silent dead
   emitters).
3. **Governance is enforced**: no unvalidated tags can enter generated content; `NEW:` proposals are
   captured for designer review — the tag system that everything depends on cannot drift.
4. **Godot drives it** over the sidecar and sees the generated content appear in-world with correct
   reload behavior.
5. **Regression-guarded + re-certified** at multiple model fidelities; the brief tells the truth.
6. **No orphans / no wired-to-empty / no dead topics** remain unaccounted for (each is either wired
   or formally, testably marked dormant).

---

## 5 · Open decisions (need owner input before/at execution)

- **D1 — Target consumer.** Recommended: **headless driver → Godot sidecar** (Phases 1 & 4), treat
  the 2D `game_engine` flip as optional (1.3). Confirm, or do you also want the 2D game to run real
  WES now?
- **D2 — EcosystemAgent (3.3).** Wire it live for playtest, or formally defer as dormant? (It's the
  one "living" subsystem with no current consumer at all.)
- **D3 — Tag-governance strictness (2.1).** Drop unknown tags silently (log only) vs. quarantine the
  whole artifact on an unknown tag? (Recommend: drop-unknown + keep valid, matching WNS's
  non-destructive posture; `NEW:` always routed to review.)
- **D4 — Key handling (0.1).** Just rotate the env var, or also add the `.env`-fallback-on-401 code
  hardening so this can't silently recur?

---

## 6 · Evidence index

- Cert proof: `crux-foundry/FINDINGS.md` F18/F20; `tools/hub_cert_harness.py:172-189`; runtime-stub
  proof `llm_debug_logs/wes/.../hub_materials_s1.json` (`backend_used: fixture`).
- Flip mechanism + service boundary: `wes_orchestrator.py:137-162,230-265,504-512`;
  `tool_registry.py:160-186`; `test_e2e_pipeline.py:122-155`; `invention_sidecar.py` (template).
- Contract deltas: `backend_manager.py:197-217,370-373,585-596`; `backend-config.json:123-233`.
- Issue file:lines: see the §1 table and `GAME_SYSTEMS_BRIEF.md` §16.
