# Consolidation & Executive Technical Brief — Plan

**Status:** Plan only (to be executed AFTER the WNS continuity fixes + a compact).
**Owner directive:** collapse the excessive temporary documentation into ONE authoritative,
professionally-designed technical brief that presents **every workflow, information transfer,
and communication in the game** — deep enough to answer any question (exemplar depth:
*"how are WNS threads coordinated and searched for?"*).

---

## 0. North star

One living artifact — the **Game Systems Technical Brief** — that an executive/technical reader
can open and, from it alone, understand how the entire game works: what each system does, how
data and control flow between them, and how they communicate. Every claim in it is
**code-verified**. It supersedes the scattered audit/ledger/trace docs, which get archived.

Two output forms of the SAME content:
- **Presentation** (executive-grade slides): the narrative walkthrough, one workflow per section.
- **Reference appendix** (the durable Markdown): the deep detail behind each slide.

Guiding principles:
1. **Single source of truth.** After this, there is one brief; everything else is archived history.
2. **Evidence-backed.** Every workflow/claim carries a `file:line` anchor (the 1-code + 1-doc rule).
3. **Answer-anything depth.** Each workflow is traced end-to-end, not summarized.
4. **Show the flow, not the folder.** Diagrams of data/control/message flow, not file listings.
5. **Honest state.** Mark what's built / stubbed / unimplemented — no aspirational claims as fact.

---

## 1. The problem (current doc sprawl)

`Development-Plan/` alone holds 17 top-level docs + 12 feature-traces + a repo-audit subdir;
`Game-1-modular/docs/` and `world_system/docs/` hold ~30 more. Much is **point-in-time**
(audits, ledgers, backward-design traces, session snapshots) that has served its purpose and now
competes with the canonical spec for authority — which is exactly the visibility loss to fix.

**Classification (disposition decided in Phase A):**

| Class | Examples | Disposition |
|---|---|---|
| **Canonical spec** | `WORLD_SYSTEM_WORKING_DOC.md`, `world_system/docs/{WORLD_MEMORY_SYSTEM,ARCHITECTURAL_DECISIONS,HANDOFF_STATUS,TAG_LIBRARY}.md`, `SYSTEMS_CATALOG.md`, `REPOSITORY_MAP.md`, `docs/GAME_MECHANICS_V6.md` | **Mine → fold into brief; keep as reference** |
| **Roadmap** | `OVERVIEW.md`, `PART_1/2/3`, `SHARED_INFRASTRUCTURE.md` | Keep (forward-looking, not brief content) |
| **Backward-design traces** | `feature-traces/00-11` | **Harvest durable content → brief; archive** |
| **Point-in-time audits** | `TOOL_CONTRACT_AUDIT.md`, `ORCHESTRATION_GAP_FIX_LOG.md`, `repo-audit-2026-06-10/*`, `WMS_WNS_LAYER_CORRESPONDENCE.md` | **Harvest findings → brief; archive** |
| **Designer action lists** | `DESIGNER_LEDGER.md`, `PLACEHOLDER_LEDGER.md`, `PLACEHOLDER_FURNISHING_WORKSHEET.md` | Keep as living TODO (link from brief; don't inline) |
| **Pointers / stubs / one-offs** | `WORLD_MEMORY_POINTER.md`, `controls-agent-render-ui.md`, `CONTROLS_MAP.md`, `POLITICAL_AND_WMS_USAGE_PLAN.md`, `WMS_TOOLS_AND_SIMULATION.md` | **Archive** (fold anything unique first) |

Rule: **never delete before harvesting.** Every archived doc gets a one-line "content migrated to
brief §X" note; move to `archive/2026-08-doc-consolidation/` (mirrors the prior `archive/2026-04-24`).

---

## 2. Phase A — Triage & cleanup

1. **Inventory** every `.md` under `Development-Plan/`, `Game-1-modular/docs/`, `world_system/docs/`
   into a disposition table (path, class, unique durable content, target brief section, action).
2. **Harvest** the durable content pointer-by-pointer (don't copy prose — extract the *fact* +
   its `file:line`, re-verify it against current code, note if stale).
3. **Archive** the point-in-time docs to `archive/2026-08-doc-consolidation/`, each with a
   migration breadcrumb. Update `CLAUDE.md`'s doc index + `REPOSITORY_MAP.md`.
4. **Result:** Development-Plan shrinks to {roadmap + the brief + living TODO ledgers}.

Guardrail: this plan doc and `ORCHESTRATION_GAP_FIX_LOG.md` are themselves temporary — they get
harvested and archived in the same pass.

---

## 3. Phase B — Detail-finding protocol (how to build verified, deep content)

The presentation is only as good as the tracing behind it. For **each workflow** in the game:

1. **Name the workflow** and its trigger (what starts it) and terminus (what it produces).
2. **Trace it end-to-end in code** — follow the actual call path, not the docs. Record every hop:
   `caller → callee (file:line)`, what data is passed, what is returned/published.
3. **Identify every information transfer**: function args, returned values, event-bus
   publish/subscribe topics, DB writes/reads, LLM prompt context, generated files. For each:
   *what data, from where, to where, in what shape*.
4. **Identify every communication channel**: direct call, `GameEventBus` topic, SQLite table,
   JSON artifact, LLM bundle. Note sync vs async.
5. **"Almost run it"** — assemble/inspect the real artifact (like the prompt dashboard does for
   prompts; do the equivalent for events, bundles, DB rows) to confirm the traced shape is real.
6. **Verify** with the 1-code + 1-doc rule; run/extend a test or a small harness where feasible.
7. **Diagram it** — a sequence or flow diagram per workflow (Mermaid), plus a one-line
   information-transfer table.
8. **Log gaps** — anything that's stubbed, dead, mislabeled, or discontinuous goes to an
   "Areas for improvement" register (see §5), not silently smoothed over.

Depth exemplar to hold every section to (the owner's standard):
> *WNS thread coordination & search* — threads are `ThreadFragment`s with `content_tags`; a new
> fragment is matched to an existing thread via `match_or_mint` (clusters by content_tag overlap
> at an address), promoted across layers via `parent_thread_id`; searched/retrieved via
> `narrative_store.query_by_address` + tag filters; continuity maintained by the cascade feeding
> each layer its lower/self/parent context. Every one of those claims cites `file:line`.

---

## 4. Phase C — Presentation architecture (game-wide)

The brief covers the **whole game**, not just the World System. Proposed section spine (each
section = trigger → workflow diagram → information-transfer table → communication channels →
state written → "what the player experiences" → build/stub status):

1. **System map (1 slide)** — the whole game as boxes + arrows; every subsystem + its channels.
2. **Core loop** — input → game_engine tick → render; the main-loop workflow.
3. **World generation & chunks** — procedural gen, chunk lifecycle, biome/resource placement.
4. **Player entity & components** — character, stats, inventory, equipment, skills composition.
5. **Combat** — damage pipeline, attack state machine, hitboxes, projectiles, status effects.
6. **Crafting** — the 6 disciplines + minigames; difficulty/reward; invented items (LLM + ML).
7. **Progression** — leveling, titles, classes, tag-driven bonuses.
8. **Events** — `GameEventBus`: the full publish/subscribe topic map (the communication backbone).
9. **WMS (memory)** — L1→L7: capture, evaluators, consolidation, tagging, storage, triggers.
10. **WNS (narrative)** — NL1→NL7 weaving; **thread coordination/search**; continuity flow.
11. **WES (content gen)** — bundle → planner → hub → tool → registry → reload; the closed loop.
12. **Factions & NPCs** — affinity tracking, NPC agents, dialogue, `<AffinityShift>`.
13. **Save/load** — full state serialization + reload.
14. **LLM & ML infra** — BackendManager, tag libraries, classifiers.
15. **Cross-cutting: information & continuity** — the money slide: how context flows and stays
    continuous across WMS↔WNS↔WES; the address hierarchy; tags as the connective tissue.

Every section answers: *what triggers it, what data moves and to where, how systems talk, what
persists, what the player feels, and what's real vs stub.*

---

## 5. Phase D — Production (professional design)

- **Format:** a self-contained HTML deck (reveal.js-style, dark technical theme — consistent with
  the existing dashboards) + Mermaid diagrams rendered inline, so it opens in any browser with no
  build step. Markdown reference appendix generated alongside.
- **Diagrams:** Mermaid `sequenceDiagram` per workflow; one `graph` system-map; info-transfer as
  tables. Consistent legend (sync call / async event / DB / LLM / file).
- **Design bar:** executive-grade — clean typography, one idea per slide, progressive disclosure
  (summary slide → detail slides), every slide footnoted with `file:line` sources.
- **Tooling option:** a generator script (like `prompt_orchestration_dashboard.py`) that
  assembles the deck from verified section data, so it can be **regenerated** as code changes —
  a living brief, not a one-off.

---

## 6. Areas for improvement (capture continuously while tracing)

Maintain a register (rolls up into the brief's "honest state" + the TODO ledgers):
- **Continuity gaps** (the class we've been fixing: mislabels, empty-context, discontinuities).
- **Dead outputs** (generated-but-unread fields; unenforced contracts).
- **Silent fallbacks** that mask missing data.
- **Stubs presented as features** anywhere in the docs.
- **Cross-system inconsistencies** (vocab mismatches, ordering, enum locks like ResourceType/ChunkType).
Each entry: `file:line`, severity, bug vs unimplemented-feature vs ambiguous — same verdict
discipline as `ORCHESTRATION_GAP_FIX_LOG.md`.

---

## 7. Sequencing

0. (Now / pre-compact) WNS continuity fixes C3/M1/M2 land and are verified end-to-end.
1. Phase A triage + cleanup (fast; frees visibility).
2. Phase B tracing, subsystem by subsystem (the bulk; parallelizable per subsystem).
3. Phase C content assembly into the section spine.
4. Phase D production of the deck + appendix + generator.
5. Review pass: does it answer arbitrary deep questions? (self-test with a question bank incl.
   the WNS-threads exemplar).

**Deliverables:** `GAME_SYSTEMS_BRIEF.html` (deck) + `GAME_SYSTEMS_BRIEF.md` (appendix) +
optional generator script + a slimmed `Development-Plan/` + `archive/2026-08-doc-consolidation/`.
