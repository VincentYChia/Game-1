# Ship-Readiness Report — Full-Codebase Review, Resumed & Completed

> **2026-07-17 addendum — playtest GO.** Everything below plus five further
> passes (F13–F20): real-LLM certification of all Haiku tasks (found + fixed
> the temperature+top_p 400 that broke every game-path Claude call since the
> June model swap), the WES hub deep-work (format delivery, sibling
> visibility, retry, dedup — certified 3 fidelities: subagent roleplay /
> Haiku / gemma3:4b, all 8/8), the faction/NPC affinity audit (quest turn-in
> now moves affinity, NPC memory persists across sessions, the WNS
> AffinityShift bridge un-broken), prompt furnishing (allow-lists inlined,
> snake_case ids, LCK retuned 0.02→0.12 per optimizer, 150/150-fragment
> coverage slideshow tool), and leak-proofed hub example sets with a
> deterministic registry-dedup guard (64-run matrix, 0 leaks). Suite at
> close: **1,219 passed / 0 failed**. The ONE operator action before
> playtest: replace the dead `ANTHROPIC_API_KEY` env var (it 401s and
> shadows the working `.env` temp key). Posture: `WES_REQUIRE_REAL_LLM=1
> WES_DISABLE_FIXTURES=1`, verify with `tools/wes_real_llm_smoketest.py`,
> tail `llm_debug_logs/wes_*.jsonl` during play, F12 for the live overlay.

**Date:** 2026-07-09 · **Branch:** `crux-foundry` · **Suite:** 1,201 passed / 0 failed
**Scope:** the "final test before playtesters" review — resumed from the halted Fable-5 effort,
expanded to combat conformance, progression, WMS internals, and a full adversarial audit of
every LLM pipeline. Findings ledger: [FINDINGS.md](FINDINGS.md) (F1–F17).

---

## 1. Session arc

| Phase | Commits | What happened |
|---|---|---|
| Resume + ground state | (20 inherited commits pushed) | Validated the halted crux-foundry infrastructure, adopted its runners as measurement instruments |
| Combat conformance | `234990c4` | F3/F5–F9: the shipped action-combat path was missing most of the documented damage pipeline |
| AI context management (Phase A) | `132ac8aa` | Budgets enforced at assembly time, boundary truncation, composition telemetry |
| Progression correctness (Batch 1) | `3a9e1030` | EXP multi-level cascade; failure-loss restored to designed 30–90% |
| Dead documented stats (Batch 2) | `d85e183d` | VIT regen, DEF armor effectiveness, INT elemental wired |
| WMS responsiveness (Batch 3) | `0295036b` | Async L2 narrative upgrades, retention N+1, generated-content leak gate |
| Ledger | `dee5806c` | F5–F12 recorded with verification scoreboard |
| LLM pipeline audit | `0951c3f8` | Every parse seam adversarially tested; four rewritten/hardened |

Test count: 1,111 (session start baseline) → **1,201** (+90, all green, 0 regressions at every step).

## 2. Combat: the action path was not the documented game

The action-combat path (`player_attack_enemy_with_tags` via `_ac_process_hit`) is the ONLY
melee path players hit — the legacy `player_attack_enemy` has zero engine callers. Diffing it
against the documented pipeline `base × hand × STR × skill × class × crit − def(≤75%)`:

- **F5 — enemy DEFENSE was never applied.** Players did full damage to a defense-500 boss.
  Fixed per-target in the effect executor (honors armor penetration, caps at 75%).
- **F6 — crit composition incomplete**; three divergent crit implementations unified into
  `_player_crit_chance` (LCK + pierce buffs + weapon tags + titles). Closes F3.
- **F7 — hand-requirement bonus (×1.1–1.2) absent.**
- **F8 — AoE sub-path used STR×0.01** (docs: 0.05) and a flat LCK-ignoring 10% crit.
- **F9 — enemy-type title bonuses never applied.**

**Measured impact (8-seed viability report, tier-2/size-8 gauntlet):** relative spread HELD at
0.209 pre/post fix — vit_tank 0.775, str_brawler 0.762, balanced 0.653, lck_crit 0.566.
Relative balance preserved; absolute difficulty up slightly (enemy DEF is now real). No
rebalance emergency. `lck_crit` remains the undertuned floor; the optimizer prescribes
0.10–0.14 crit/pt (vs current 0.02) — a designer decision, exposed as `CRUX_LCK_CRIT_PER_POINT`.

## 3. AI context management — the focus area

Benchmarked against the designer doctrine (WORKING_DOC §8.4 "composing the right ~2–4k tokens
per call is the entire game"; §8.11 observability non-negotiable).

**Input side (context assembly) — fixed in Phase A:**
- WMS L2–L7 data blocks were UNBOUNDED (a burst district could stuff arbitrarily many events
  into one consolidation prompt). Budgets now enforced at the single choke point every layer
  call flows through (`generate_narration`), per-layer `data_budget` (2,400–9,000 chars),
  whole-event truncation with an explicit `<omitted count=.../>` marker.
- Three mid-sentence tail-slice truncations replaced with boundary-aware helpers
  (`text_budget.py`: sentence→word boundary; snippet-window for NPC conversation memory).
- Silently-dropped missing prompt fragments now counted and warned once per tag.
- Per-call composition telemetry (`log_extra`: layer, fragments used, fragment/data chars,
  events omitted, token estimate) threaded through BackendManager into the dev log.

**Output side (response parsing) — fixed in the LLM audit (`0951c3f8`):** see §4.

**Responsiveness — fixed in Batch 3:**
- L2 narrative upgrades ran a SYNCHRONOUS LLM call on the gameplay event path (bus → trigger →
  interpreter), firing during combat: 300–1,500 ms frame stall per trigger with a real backend.
  Now async: template narrative records immediately; a worker (max 4 in flight, graceful skip
  beyond) runs the LLM; `drain_narrative_upgrades()` patches EventStore + LayerStore rows on
  the main thread each frame. Workers never touch SQLite (LayerStore is not thread-safe).
- L3–L7 consolidations still call the LLM synchronously (cadence-gated, rarer); stalls >250 ms
  are now logged so playtest hitching is attributable. Full async needs a thread-safe
  LayerStore — recommended follow-up, not a blocker.
- Retention Rule 5 was N+1: up to 5,000 unindexed `LIKE '%id%'` scans per prune, on the game
  loop. Replaced with one batched cause-chain pass, identical semantics.

## 4. LLM pipelines: adversarial audit of every parse seam

Inventory: 33 LLM tasks — WMS L2–L7 (6), WNS NL2–NL7 (6), WES planner + 8 hubs + 8 tools +
supervisor + 2 quest-reward (20), NPC dialogue (1). Method: trace prompt→call→parse→consume,
then feed each parser well-formed AND adversarial replies (fences, preambles, truncation,
invented tags, absurd values, empty, prose-only) and classify fail-open vs fail-closed.

| Seam | Verdict | Action |
|---|---|---|
| WMS `_call_llm` (L2–L7 + NPC dialogue text) | **4 failure modes** incl. failing its own prompt contract | REWRITTEN (F13) |
| WES `parse_xml_batch` (hubs) | Robust, fail-closed | dup-id hole fixed (F14) |
| WES planner / executor-tool JSON | Robust (fence-strip + substring + stricter-suffix retry) | confirmed |
| WES supervisor verdict | Fail-OPEN — correct by design (rerun-only authority, loudly logged) | confirmed |
| WNS NL weaver JSON | Robust, fail-closed, logged degrade | confirmed |
| WNS AffinityShift resolver | Structure gated; magnitude UNBOUNDED | ±25 clamp (F15) |
| Invented items post-parse | Validation was "has an itemId" ONLY | sanity gate (F16) |
| Backend chain + gates | `WES_REQUIRE_REAL_LLM` gate proven live (caught the dead key) | 401 message hardened (F17) |

Full before/after tables per finding: [FINDINGS.md](FINDINGS.md) F13–F17.

## 5. Other correctness fixes

- **EXP cascade** — one large grant crossing several thresholds resolved only one level per
  call (no EXP lost, but phantom late level-ups). Now cascades with per-level LEVEL_UP publish.
- **Failure-loss** — designed tier-scaled 30–90% material loss had silently become 100%
  (crafters deducted from a throwaway dict copy; engine consumed the full recipe).
  `consume_materials_partial` restores design intent.
- **Dead stats wired** — VIT +1%/pt regen, DEF +3%/pt armor effectiveness, INT +5%/pt
  elemental (action path, elemental-tag gated).
- **F12 content leak** — in-engine test runs drove real WES ContentRegistry commits into the
  live content tree (12 generated JSON files in `Skills/`, `Definitions.JSON/`, `items.JSON/`,
  auto-loaded as real content on every boot — the test world was silently playing with
  machine-generated skills). Fixed at the WRITER: explicit root > `GAME1_GENERATED_CONTENT_ROOT`
  env > `GAME1_HERMETIC` backstop. Artifacts deleted.

## 6. Verification discipline

Every delegated claim was verified firsthand before acting. Session scoreboard: ~9 confirmed,
2 corrected-in-mechanism ("2× loss" was actually 100%-not-designed-loss; "EXP lost" was
actually deferred), **6 rejected** (debug-mode leak, reward-band off-by-one, encumbrance
unwired, carry capacity orphaned, trigger double-fire = documented dual-track design, missing
composite indexes = `idx_events_type_locality_time` exists). The LLM-audit subagent fan-out hit
the session usage cap mid-run; the entire audit was re-executed inline with probe scripts —
every F13–F17 behavior in the ledger is reproduced output, not a report from a subagent.

## 7. Soak

4 seeds × 15 in-game days through the real engine (life_runner), sharing one WMS database
across four boots: 1,308 events, 92 coherent daily ledgers, 50 milestone interpretations
(44 minor / 4 moderate / 2 major), zero errors, no cross-session corruption.

## 8. GO/NO-GO for the playtest

**GO items (done):** combat pipeline conformant + regression-pinned; context budgets enforced;
L2 LLM path async; all parse seams fail-closed or clamped; content tree leak sealed; suite
1,201/0.

**Operator actions before GO:**
1. **Rotate ANTHROPIC_API_KEY** — the current key 401s (F17). Then re-run
   `python tools/wes_real_llm_smoketest.py` with `WES_DISABLE_FIXTURES=1 WES_REQUIRE_REAL_LLM=1`.
2. Recommended: a handful of real L2 narration round-trips post-rotation (live-output testing
   was blocked this session by the dead key).

**Open designer decisions (documented, not blocking):**
1. Skill damage bypasses enemy defense on the executor path (melee now applies it) — intent?
2. STR +10 inventory slots/pt unwired — 330 slots at STR 30 breaks the fixed 30-slot grid;
   needs a pagination design.
3. LCK crit value: optimizer prescribes 0.10–0.14/pt (currently 0.02).
4. LCK resource-quality/rare-drop semantics are ambiguous in the docs.
5. Invented-item TAGS unvalidated (`execute`/`chain` on a T1 dagger is legal) — tag-per-tier
   policy is balance design.
6. Two new constants are deliberately-generous defaults to retune: invented-item stat ceilings
   (60/120/240/480 by tier), AffinityShift per-directive cap (±25).
7. L3–L7 consolidation is still synchronous LLM on the game loop (logged when >250 ms);
   full async needs a thread-safe LayerStore.
