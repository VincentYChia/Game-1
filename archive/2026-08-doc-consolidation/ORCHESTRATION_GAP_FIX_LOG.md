# World System — Orchestration Gap Fix Log

**Date:** 2026-08-03 · **Branch:** godot-migration · **Scope:** WMS/WNS/WES LLM prompt-orchestration

This log exists so you keep design visibility over changes I made. Each gap below carries a
**verdict** — *bug*, *unimplemented feature*, or *fix-direction-corrected* — so you can tell
which are genuine defects vs missing features vs places my first instinct was wrong.

**See the live state any time:** `python Game-1-modular/tools/prompt_orchestration_dashboard.py`
opens a per-prompt dashboard (32 prompts) with each one's output-tag contract, injection mode,
enforcement, and open gaps. It **self-checks the source**, so a fixed gap shows green and
**re-reddens automatically if the fix is reverted** — a regression check, not a static claim.

How the gaps were found: two agent traces (design-doc synthesis + runtime var/context trace),
every finding confirmed at file:line, cross-checked against the design docs
(`WORLD_SYSTEM_WORKING_DOC.md`, the `feature-traces/`, `WMS_WNS_LAYER_CORRESPONDENCE.md`).

---

## Summary

| ID | Gap | Verdict | Status |
|----|-----|---------|--------|
| **C1** | WNS never validates its output tags | **Bug** (unimplemented enforcement) | ✅ Fixed |
| **C2** | Planner leaks literal `${thread_headlines}` to the model | **Bug** | ✅ Fixed |
| **Mn1** | WES hubs render empty context as blank sections | **Minor bug** (style) | ✅ Fixed |
| **Mn2** | Tool `_output` schema key vs assembler | **Latent** — my first fix was wrong | ✅ Fixed (corrected direction) |
| **M1** | NL7 emits `dominant_*`/`severity` nobody reads | **Unimplemented feature** | ✅ Fixed (Round 2) — persisted + cascaded DOWN |
| **C3** | NL3–7 lower-layer context is structurally always empty | **Bug** (architectural) | ✅ Fixed (Round 2) — child-address aggregation |
| **M2** | Planner `registry_counts` is a permanent `"n/a"` stub | **Unimplemented feature** | ✅ Fixed (Round 2) — live registry counts |

---

## Fixed

### C1 — WNS output-tag enforcement · Bug (unimplemented)
- **Was:** `narrative_tag_library.validate_tag()` existed but was **never called**. WNS split
  tags into address/content (`partition_address_and_content`) and stored the content ones
  verbatim (`nl_weaver.py:666` row, `:877` thread). Any LLM-invented narrative tag entered the
  store and the **thread match/search index** (`match_or_mint`). WMS guards this; WNS didn't.
- **Change:** added `NLWeaver._validate_content_tags()` and call it at both storage sites.
- **Fix-direction note (important):** the naive fix — validate against the WNS taxonomy only —
  would have **wrongly dropped legitimately-reused WMS tags** (`tier:`, `domain:`, `species:`,
  which WNS reuses by reference). So the validator keeps a tag if it's valid in the **WNS
  taxonomy OR the WMS library**, dropping only pairs invented in *neither*. Non-destructive.
- **Behavior change:** previously-storable invented tags are now dropped (with a logged warning).
  `emergent_entity` (the free-form escape hatch) still passes — it's a dynamic category.
- **Open question:** should WNS content_tags be **WNS-taxonomy-only** (stricter — the prompt's
  allow-list and examples suggest this) or **WNS+WMS** (what I implemented, safest)? I chose the
  non-destructive option; tell me if you want it strict.

### C2 — planner `${thread_headlines}` leak · Bug
- **Was:** the planner template reads `${thread_headlines}` but `_bundle_to_vars`
  (`llm_execution_planner.py:236`) never supplied it → the literal string `${thread_headlines}`
  reached the planner LLM on every plan (the substituter leaves unknowns verbatim).
- **Change:** `_bundle_to_vars` now supplies `thread_headlines` rendered from
  `bundle.narrative_context.open_threads` (`(none)` when empty).
- **Fix-direction note:** two options — *supply* it or *delete the line*. I **supplied** it
  because the design (trace 10 context contract) says the planner should reason about open
  threads. If you'd rather the planner not see threads, we delete the template line instead.

### Mn1 — WES hub empty-context markers · Minor bug (style)
- **Was:** hub renderers returned `""` for empty parent-narratives / WMS-events / NPC-dialogue,
  so the prompt showed a labeled heading followed by a blank line — the model can't tell
  "genuinely empty" from "accidentally dropped." WNS marks these `(none)`.
- **Change:** the three renderers (`llm_execution_hub.py:309/322/340`) now emit
  `(none)` / `(no recent WMS events)` / `(no recent dialogue)`.
- **Note:** the old empty-string was an intentional choice per the docstrings; I changed it for
  WNS parity and model clarity. Low risk.

### Mn2 — tool output-schema key · Latent; **fix direction corrected**
- **This is the clearest "my first instinct was wrong" case.** The original finding said "only
  `chunks` uses `schema_description` while others use `schema` — rename chunks." On verification:
  **all 8 tools use `schema_description`**, hubs use `schema`, and the runtime assembler reads
  `schema`. The tool key is currently harmless (tools inject `_output.example`, not `schema`).
- **Why the naive rename was wrong:** `schema_description` is **also read by Prompt Studio**
  (`tools/prompt_studio/app.py`) to show you the schema. Renaming it to `schema` would have
  **broken the designer tool** — and wouldn't have helped, since tools don't inject `schema` at
  runtime anyway.
- **Change (safe):** the assembler now reads `_output.schema` **OR** `_output.schema_description`
  (`prompt_assembler.py:200`). Latent gap closed, Prompt Studio untouched, no JSON renamed.

---

## Round 2 (2026-08-03) — C3 / M1 / M2 implemented (continuity fixes)

Driven by the principle you set: **the entire point of the layered World System is context
management and CONTINUITY** — context must flow up the layers and cascade back down, the way WMS
does with facts; WNS does it with *stories + tags*. A background workflow deep-mapped WMS's
mechanism, traced each gap, designed the fix, and adversarially stress-tested C3 before code was
touched; the implementation matches (and slightly exceeds) that verified design.

### C3 — restore the lower-layer continuity link · Bug (architectural) → ✅ Fixed
- **The break:** the cascade fires NL_N at a PARENT address (NL3 at `district:X`) but the child
  layer wrote its rows at DESCENDANT addresses (NL2 at the `locality:*` inside that district).
  `get_layer_snapshot` did an exact-address read → `${lower_primary_narrative}` /
  `${lower_primary_threads}` were **structurally always empty at NL3+**. Every district/region/
  nation/world story was written *blind to the stories inside it.*
- **The fix (mirrors WMS):** `build_weaver_context` now takes the geographic registry and, for
  NL3+, aggregates the lower layer from the firing address's **CHILD addresses**
  (`get_children` → per-child `query_by_address`, merged by recency, bounded). New helpers
  `_descendant_addresses` + `get_lower_snapshot_aggregated` (`cascading_context.py`); the caller
  passes `geo_registry=self._geographic_registry` (`nl_weaver.py:565`). NL2 keeps its direct read
  (NL1 sits at the same locality); no-registry paths fall back to old behavior (backward compat).
- **Continuity + player experience:** coarse-scale narrative is now *caused by what the player
  did in the places below* — a district names the cross-village pattern, a region reflects its
  districts, arcs started in a village get **promoted upward** (`parent_thread_id` works again
  because real child thread_ids now reach the parent). The world reads as one continuous story
  that remembers and escalates the player's footprint instead of seven disconnected layers.
- **Locked in:** `test_cascading_context.py::TestC3ChildAggregation` (empty-without-registry,
  populated-from-children incl. real thread_ids, NL2-unchanged).

### M1 — NL7 world currents made continuous · Unimplemented feature → ✅ Fixed
- **Not stripped** (that would delete a designed capability). Instead made LIVE: `run_weaving`
  now parses NL7's `dominant_arcs`/`dominant_regions`/`dominant_factions`/`severity` and
  **persists** them on the world row (`payload.world_state`); `WorldNarrativeSystem.get_world_state()`
  exposes them.
- **The real reader (the continuity closer):** those world currents now **cascade DOWN** —
  `build_weaver_context` renders them (`render_world_dominant`) into a `${world_framing}` slot
  injected into NL2–NL6 prompts, so every lower firing stays aligned with the top of the pyramid
  (the WNS analogue of WMS L7 cascading its world condition down). NL7 itself doesn't re-read its
  own currents (its self-continuity is its own prior narrative).
- **Player experience:** local and regional stories subtly cohere with the world's current age /
  dominant factions instead of drifting independently.
- **Locked in:** `test_cascading_context.py::TestM1WorldCascadeDown` (frames lower layer,
  NL7 excluded, empty-before-world-fires).

### M2 — planner `registry_counts` made real · Unimplemented feature → ✅ Fixed
- Replaced the hardcoded `"n/a"` with `_registry_counts_summary()` — live per-tool counts from the
  content registry (`ContentRegistry.counts()`, the documented diversity/saturation signal),
  best-effort with a clear marker when the registry is empty/uninitialized. This counts WES's OWN
  output registry (not a canonical narrative store), so it respects the "bundle is the only input"
  contract; design-ideal follow-up (noted in code) is to pre-compute it into the bundle at build
  time, since WNS lacks a registry handle today.

**Verification:** `world_system/wns` + `world_system/wes` → **357 passed, 1 pre-existing/unrelated
fail** (the WES e2e fixture `rolled_back`, same assertion + reason, no reference to the new code).
Dashboard self-check: WMS + WNS enforced, 0 unresolved-var, 0 placeholder leaks, **no verified
findings remaining** (only the 7 WES content-tool hardcoded/unenforced tag lists — the separate
"no content-tag library exists" infra item).

---

## Verification
- `python -m pytest world_system/wns world_system/wes` → **351 passed, 1 failed**. The 1 failure
  (`test_e2e_pipeline.py::…test_full_pipeline_commits_with_llm_tiers`, `rolled_back`) is
  **pre-existing and unrelated** — proven earlier to fail identically on a clean baseline; same
  assertion location, no new error from these changes.
- Dashboard after fixes: enforced = **WMS + WNS**; unresolved-var prompts **0**; placeholder
  leaks **0**; remaining findings **C3×5, M1×1, M2×1** (all above).

## Still-standing structural facts (not "bugs", but design realities)
- **WES content tools** (7) still inject **hardcoded, unenforced** tag lists — no content-tag
  library exists to generate from, and the `NEW:` proposal mechanism is documented but unbuilt.
  Same as prior finding; a separate infrastructure decision.
- **Doc-flagged plumbing** (not prompt-text): G01 bundle-slice strips narrative context so the 8
  tools are narrative-blind by construction; G02 empty `NarrativeDelta`; **G07 five missing
  `reload()` methods** (Materials/Hostiles/Nodes/Skills/Titles → generated content invisible
  until restart). These are the load-bearing items the design docs themselves flag.
