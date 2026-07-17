# Crux Foundry — Balance Findings

Findings the automated playtester surfaces. Each is stamped with the git sha of the
code it was observed against and its confidence. **Single-seed observations are
provisional** — combat has high-variance RNG (crit), so a finding is only
"confirmed" once it holds across many seeds (that's what the multi-seed
relative-viability report is for).

---

## F1 — Gauntlet difficulty calibration (tier 2 / size 8 differentiates builds)
**Status:** methodology result (not a game issue) · observed @ `ac8b2454`

A single-swing melee gauntlet only differentiates builds in a narrow difficulty band:
- tier 1 / size 3 → every mid-game build trivially clears (no signal).
- **tier 2 / size 8 → builds rank distinctly** (chosen default).
- tier 3+ / size 8 → everything wipes (no signal, though the tank dies *fewest* times).

Calibration sweep (seed 1, level-10 builds, iron_shortsword):

| tier·size | str_brawler | vit_tank | lck_crit |
|---|---|---|---|
| 2·8 | 7/8, 2 deaths, 179 dmg | 7/8, 2 deaths, 326 dmg | 6/8, 4 deaths, 292 dmg |
| 3·8 | wiped, 54 deaths | wiped, **26** deaths | wiped, 58 deaths |
| 4·8 | 2/8, 74 deaths | wiped, 44 deaths | 1/8, 84 deaths |

Note "deaths" = respawn count (death is a setback, not a run-ender), so it is a
graded viability signal even in a loss (the tank consistently dies fewest).

---

## F2 — pure-LCK build is non-competitive; STR/VIT/balanced are well-balanced (CONFIRMED, 5 seeds)
**Status:** CONFIRMED (multi-seed) · observed @ `a0732bc5`

Relative-viability report — level-10 builds, all 9 points in one stat, tier-2/size-8
gauntlet, **mean over 5 seeds** (viability = mean(kills)/8 − 0.05·mean(deaths)):

| build | kills | deaths | dmg_taken | clear% | viability |
|---|---|---|---|---|---|
| str_brawler | 7.20 | 2.00 | 170.4 | 20% | **0.800** |
| vit_tank | 7.00 | 2.00 | 315.3 | 0% | 0.775 |
| balanced | 7.20 | 2.80 | 274.1 | 60% | 0.760 |
| lck_crit | 5.80 | 4.40 | 318.3 | 0% | **0.505** |

**Verdict:** STR / VIT / balanced cluster within ~5% (well-balanced with each other);
`lck_crit` is the sole outlier ~35% below. So the imbalance is specific: **pure-LCK is
non-competitive** — +2%/pt crit (≈+18% *conditional* damage) is a weaker combat
investment than STR's +5%/pt flat damage or VIT's +15 HP/pt survivability.
**Recommendation:** raise LCK's crit value (or add a small base crit — see F3) so
luck builds are viable. Single-seed provisionality is now resolved by the 5-seed mean.

Interpretation note: +2%/pt crit (≈+18% *conditional* damage) is a weaker combat
investment than STR's +5%/pt flat damage or VIT's +15 HP/pt survivability.

**Corrected mid-investigation:** an earlier single-seed run made `lck_crit` look
*identical* to a no-crit build (LCK "dead"). Code check refuted the "dead" reading —
LCK **is** wired to crit: `base_crit_chance = 0.02 * effective_luck`
(`combat_manager.py:958-959`). The identical result was just crit not firing in a
short fight (18% × few hits). Lesson: never conclude a balance finding from one seed;
crit variance demands multi-seed averaging.

---

## F3 — Two divergent crit implementations (code inconsistency, to verify)
**Status:** note · observed @ `ac8b2454`

`combat_manager.py` has two crit computations:
- `:747` `crit_chance = 0.10` (hardcoded, no LCK) — a secondary/legacy attack path.
- `:958-959` `base_crit_chance = 0.02 * effective_luck` (LCK-scaled) — the action-combat
  path the player actually uses.

Note there is **no base crit** in the LCK path (luck 0 → 0% crit), whereas the legacy
path gives a flat 10%. Worth reconciling: a 0-LCK character crits 10% via one path and
0% via the other depending on which attack code runs. Not blocking the playtester, but
a real balance/consistency question for the game.

---

## F4 — LCK is a DEAD stat on the action-combat path (ROOT CAUSE of F2) — CONFIRMED
**Status:** CONFIRMED (code + knob test + optimizer) · observed @ `f9158c4e`+

Real melee runs `player_attack_enemy_with_tags` (reached via the hitbox resolver
`_ac_process_hit`). Reading it (`combat_manager.py:1580-1607`): it applies the STR
multiplier (`strength * 0.05`, :1590) and title/skill bonuses, then executes the tag
effect system — but has **NO crit computation at all** (no luck, no ×2). The
luck→crit wiring (`base_crit_chance = 0.02 * effective_luck`) exists ONLY in the
legacy `player_attack_enemy` (:965), which action combat never calls.

**Proof:** a tunable `CRUX_LCK_CRIT_PER_POINT` injected at the legacy site and swept
0.02→0.10 produced **bit-identical** persona results — the personas never execute that
code. And `optimizer.py` finds `lck_crit` is the viability FLOOR at every STR-knob value.

**Impact:** a player investing in LCK for crit gets **zero** combat benefit in real
(action) melee — this is the root cause of F2 (pure-LCK non-competitive).
**Fix (dev CODE, not a tune):** apply luck-based crit in `player_attack_enemy_with_tags`
(and/or the effect executor), reconciling F3's two crit paths. *Then* the optimizer
could tune the crit value to make luck builds viable.

**Optimizer corollary (the key lesson):** this is the archetypal problem the optimizer
**cannot** fix — a value can't be auto-tuned if the code never reads it. The tester's
job was to FIND it; the fix is a code change. Auto-tuning tunes PARAMETERS, not WIRING.

### F4 — FIXED ✅ (the measure -> fix -> verify loop, closed)
Wired luck-based crit into `player_attack_enemy_with_tags` (mirrors the legacy path;
`crit_chance = _LCK_CRIT_PER_POINT * effective_luck + title bonus`, applied last on the
fully-bonused damage; threaded to the return, StatStore `was_crit`, and DAMAGE_DEALT).
This is an intentional GAME BEHAVIOR change (adds the missing crit), not a
determinism-preserving injection — luck now matters in real combat.

**Verified (single build, seed 1, default 0.02 crit/pt):** `lck_crit` went from
`6 kills / 4 deaths / partial` (dead LCK) to **`8 kills / 2 deaths / cleared`** — just
fixing the wiring (9 luck now = 18% crit instead of 0%) made it competitive. It also
now *responds* to the knob (dmg 886 -> 1078 as crit/pt 0.02 -> 0.10). Guarded by `tests/integration/test_11_crux_foundry.py`; full game suite green (1143 passed).

**Aggregate (8-seed viability report):** the wiring fix lifted `lck_crit` from **0.505**
(pre-fix, weakest) to **0.566** and cut the spread **0.295 → 0.209**. It stays weakest at
the DEFAULT 0.02 crit (crit is *undertuned*), but `optimizer.py` shows tuning
`CRUX_LCK_CRIT_PER_POINT` up to ~0.10–0.14 lifts lck_crit to ~0.900 and cuts the spread a
further 32%. So the **FIX makes luck matter; the OPTIMIZER prescribes the value** the game
devs would set — the full find → fix → tune → verify loop, run entirely locally.

---

## F5–F9 — Action-path conformance cluster (siblings of F4) — FIXED ✅
**Status:** FIXED @ `234990c4` · verified by `tests/integration/test_12_combat_conformance.py`

Firsthand re-audit of the F4 site surfaced that the action path (the ONLY melee path
players hit) was missing MORE documented pipeline components than crit:

- **F5 (major):** enemy DEFENSE was never applied — players did full damage to armored
  enemies. Now applied per-target in the effect executor (`_apply_enemy_defense`),
  honoring armor penetration, capped at 75%. Skill-path damage intentionally still
  bypasses enemy defense (open design question — see report).
- **F6:** crit composition lacked pierce-buff and weapon-tag components; three divergent
  implementations unified into `CombatManager._player_crit_chance` (closes F3).
- **F7:** hand-requirement damage bonus (×1.1–1.2) was absent on the action path.
- **F8:** the legacy AoE sub-path used `STR × 0.01` (docs: 0.05) and a flat LCK-ignoring
  10% crit; both now use the shared constants/helper.
- **F9:** enemy-type title bonuses (`get_enemy_damage_multiplier`) never applied.

**Balance impact (8-seed report, post-fix):** spread HELD at 0.209 — relative balance
preserved; absolute difficulty up slightly (enemy DEF now real). No rebalance emergency.
lck_crit remains the undertuned floor (0.566); prescription unchanged (~0.10–0.14/pt).

---

## F10 — Synchronous LLM calls on the game loop (WMS) — L2 FIXED ✅, L3–L7 mitigated
**Status:** L2 FIXED · observed via firsthand audit of `interpreter.py` / `world_memory_system.py`

Every L2 trigger ran `WmsAI.generate_narration` SYNCHRONOUSLY inside the gameplay event
path (bus publish → trigger → interpreter) — instant with fixtures, but a 300–1500ms
frame stall per trigger with the real Claude backend, and triggers fire *during combat*.
This was the same class of playtest-killer as the 30s NPC-dialogue freeze fixed in June.

**Fix:** the template narrative is recorded immediately; a worker thread runs the LLM
call (bounded at 4 in flight, graceful skip beyond); the result patches EventStore +
LayerStore rows on the main thread via `drain_narrative_upgrades()` in
`WorldMemorySystem.update()`. Workers never touch SQLite (LayerStore is not
thread-safe). Verified by `world_system/tests/test_async_narrative_upgrade.py` (10 tests).

**Residual:** L3–L7 consolidation/summarization still run their LLM calls synchronously
in `update()` — rare (cadence-gated) but each can stall ~1s+ with a real backend. Now
LOGGED when >250ms so playtest hitching is attributable. Full async needs a thread-safe
LayerStore first — recommended follow-up, not a pre-playtest blocker.

---

## F11 — Retention prune was N+1 (up to 5,000 unindexed LIKE scans) — FIXED ✅
**Status:** FIXED · `retention.py` Rule 5

Each prune pass called `is_referenced_by_interpretation(event_id)` — an unindexed
`LIKE '%id%'` full scan of the interpretations table — once per candidate event
(limit 5,000), on the game loop. Replaced with ONE batched pass
(`EventStore.get_all_referenced_event_ids()`), identical semantics (parses the same
`cause_event_ids_json` chains), set-membership per event.

---

## F12 — Test runs leaked WES-generated content into the live content tree — FIXED ✅
**Status:** FIXED · `generated_file_writer.py` + `tests/integration/conftest.py`

In-engine test/soak runs drove real WES ContentRegistry commits, which wrote
`skills-generated-*.JSON`, `hostiles-generated-*.JSON`, and
`items-materials-generated-*.JSON` siblings into `Skills/`, `Definitions.JSON/`, and
`items.JSON/`. Every subsequent boot (game OR test) then auto-loaded them as real
content — the test world was silently playing with machine-generated skills.

**Fix:** `GAME1_GENERATED_CONTENT_ROOT` env redirect honored first by the writer's root
resolver; the integration conftest sets it to a temp dir; `GAME1_HERMETIC=1` now also
forces a temp root as a writer-side backstop (the runner-side gate had been bypassed).
The 12 leaked artifact files (all stamped `"generated": true` with plan ids) deleted.

**Lesson:** the sacred-tree guarantee needs enforcement at the WRITER, not just at
dispatch — any future caller that reaches commit gets the same protection.

---

## F13 — WMS response parser failed its own prompt contract — FIXED ✅
**Status:** FIXED @ `0951c3f8` · probe-verified before/after · 14 tests in `test_wms_response_parsing.py`

The L2–L7 narration parser (`wms_ai._call_llm`) had four failure modes against
realistic model output, found by feeding it adversarial replies:

| Input shape | Old behavior | New behavior |
|---|---|---|
| Compliant JSON with `significance:significant` tag (what the prompt ASKS for) | severity stayed `minor` — parser only matched `severity:` | severity extracted, tag consumed |
| ` ```json {...}``` ` fenced reply (most common real-model shape) | whole fenced blob persisted as the narrative, tags lost, severity picked up "major" from INSIDE the JSON | JSON recovered cleanly |
| Prose preamble + JSON ("Here is the narration: {...}") | garbage narrative | JSON recovered cleanly |
| Narrative prose "a critical blow, a major turning point" | severity=**critical** via substring fallback (severity drives district/province propagation!) | severity stays minor (fallback removed) |
| Invented tags `vibe:spooky` | entered the load-bearing tag index unchecked | dropped via `tag_library.validate_tag` allow-list, warned |
| `severity:catastrophic` | accepted verbatim (not in SEVERITY_ORDER) | ignored with warning |
| Empty reply | `success=True` with empty narrative | failure → template fallback |
| Truncated JSON | broken fragment persisted as narrative | failure → template fallback |

---

## F14 — WES hub batches accepted duplicate spec ids — FIXED ✅
**Status:** FIXED @ `0951c3f8` · everything else in `parse_xml_batch` verified fail-closed

Adversarial probe: fences ✓ preamble ✓ truncation ✓ bad-JSON attrs ✓ missing
plan_step_id ✓ unescaped `&` ✓ — all correctly rejected with typed errors (the
dispatcher retries the hub). The one hole: two `<spec id="a">` elements parsed
fine and would clobber/double-execute downstream work keyed by spec_id. Now
fails closed like every other malformed shape. Supervisor fail-open degrade
CONFIRMED-ACCEPTABLE by design (rerun-only authority, loudly logged; the real
commit gates are verification/xref/schema).

---

## F15 — AffinityShift directives had no magnitude bound — FIXED ✅
**Status:** FIXED @ `0951c3f8` · 3 tests in `test_affinity_shift.py`

The resolver validated structure (unknown scope tiers, unknown target prefixes,
prose effects all rejected + ledgered) but passed `delta` through raw.
FactionSystem clamps the resulting VALUE to [-100,100], so one hallucinated
`standing_delta: -9999` could legally slam a relationship from +100 to −100 in
a single narrative beat. Per-shift clamp ±25 (`MAX_SHIFT_MAGNITUDE`), clamps
recorded in the ledger apply-note with the original value. NL weaver JSON parse
verified robust (prelude/suffix-tolerant, fail-closed, logged degrade) — no change.

---

## F16 — Invented items: the only validation was "has an itemId" — GATED ✅
**Status:** STOPGAP SHIPPED @ `0951c3f8` · 6 tests · BalanceValidator remains the designed answer

`llm_item_generator.generate()` checked nothing but itemId presence. Probe:
`{"itemId": "iron_shortsword", "tier": 99, "damage": 999999}` flowed straight
toward the inventory — shadowing a sacred item id, off-scale tier, absurd stats.
New `_sanitize_item_data`: id-collision guard (`invented_` prefix so LLM output
can never shadow sacred content), tier clamped 1–4, combat-stat ceilings scaled
by the documented tier multipliers (60/120/240/480 for damage/defense/healing
etc.), every adjustment logged. Ceilings are deliberately generous — the
designer owns real balance policy. REMAINING (designer decision): item TAGS are
unvalidated — a T1 dagger with `["execute", "chain"]` gets real combat behavior.

---

## F18 — WES hub deep-work: the fan-out heart certified at three fidelities — FIXED ✅
**Status:** FIXED @ `cc6894b5` + `5d99a4e6` · roleplay 8/8, Haiku 8/8, gemma3:4b 8/8

Full trace of the hub (one plan step → N executor specs; everything the tools
generate is bounded by what the hub scopes) plus a three-round iteration:
subagents roleplaying the hub model on exact assembled prompts, then real
Haiku, then gemma3:4b, with an adversarial prompt review between rounds.

Root causes found and fixed (each verified firsthand):
1. **`_output` schema+example NEVER injected into any prompt** — models were
   told "STRICT XML … <specs> root" and nothing more; the all-models dialect
   failure was the only possible outcome. Now an [OUTPUT FORMAT] block.
2. **Stale [GAME AWARENESS] on every WES prompt**: "quests is deferred; do
   not plan quests" — the planner was forbidden from planning chunks/npcs/
   quests since v3 shipped. Updated to all 8 tools.
3. **No hub retry** (planner/tools have one) — added strict retry with example.
4. **Dedup + co-emission context always empty** — dispatcher now injects live
   same-tool rows (source=live: "do NOT recreate") and rows staged by the
   current plan across all tools (source=co_emitted_this_plan: "MAY reference
   by id") — closing the unenforceable "must exist OR be co-emitted" rule.
5. **The quests hub example was malformed XML all along** (SQL-style ''
   escaping inside an attribute).
6. **[TASK AWARENESS] boilerplate contradicted the XML contract** ("strictly
   valid JSON (or XML where specified)") — per-file override added, all 8
   hubs carry XML-specific rules incl. slots.count-is-authoritative and
   JSON-in-XML escaping.
7. **Example-content leakage**: Haiku copied "Copperlash Rider" from the
   example into live output — fixed by SHAPE-not-content instruction +
   source labels. gemma still leaks in 3/8 hubs → designer recommendation:
   domain-neutral example content.
8. **{{...}} double-braced payloads from gemma** — parser strips one layer.

Contract scoring (parse / count / tier+biome propagation / dedup vs seeded
registry / distinctness): subagent roleplay 8/8 (with emergent cross-batch
coherence — nodes referenced the materials batch's exact ids); Haiku 8/8;
gemma3:4b 8/8. Designer-furnishing items from the adversarial review left
open: ID-derivation contract, allow-lists referenced but not shown (titles
bonus keys, skills type×category matrix, hostiles ability library),
context-role lines, key-naming duplications (#10/#12), tier→difficultyTier
mapping, chunks theme enum coverage.

---

## F19 — Faction/NPC affinity: working stores, disconnected pipes — FIXED ✅
**Status:** FIXED @ `5a1e63aa` · 9 time-compressed tests in `test_affinity_long_horizon.py`

User-requested verification of the features only evident after hours of play.
Every store, clamp, threshold, and inheritance mechanism worked; the
*connections* didn't:
1. **Quest turn-in moved zero affinity** — the live quest system had no faction
   reference; the designed quest_tool had no caller. New
   `QuestGenerator.apply_turn_in()` (explicit deltas → outcome map → derived
   from the giver's belonging tags +4/+2, max 3; giver NPC +5; consolidated
   standing published), wired into the engine turn-in block.
2. **NPC dialogue relationships never persisted** — the SQLite facade shipped
   in June with zero callers; hours of dialogue died on quit, never rehydrated
   at boot. NPCAgentSystem now hydrates on first touch and write-through
   flushes after every dialogue.
3. **AffinityConsolidator never invoked** — now fires on quest turn-in.
4. **Real bug:** AffinityResolver passed `source=` provenance that
   `adjust_player_affinity` didn't accept — every live faction-targeted WNS
   AffinityShift died with a TypeError. The earlier certification's fake
   accepted `**kwargs` and masked the drift (lesson: interface drift hides
   behind permissive mocks). Now accepted + forwarded into the event.
Confirmed working unchanged: WNS resolver wiring, location-default
inheritance, label thresholds, ±100 clamps.

---

## F20 — Hub example sets: leak-proofed at the content level + deterministic dedup guard — SHIPPED ✅
**Status:** SHIPPED @ `aeb67ca5` · 64-run certification matrix, 0 leaked names

The moors examples leaked verbatim into moors firings on small models (3/8
hubs on gemma3:4b). Two replacement content sets — identical XML shape and
constraint keys — certified across gemma3:4b (16 runs/set) and qwen3:4b
(8 runs/set): **frostpeak** (off-theme glacial mini-saga; applied) and
**schematic** (placeholder-flavored neutral); `moors_original` preserved for
rollback. Zero example leakage on either set × either model. Tooling:
`tools/hub_example_set_apply.py` (one-command switcher, parse-validates before
writing) + `tools/hub_cert_harness.py` (permanent contract+leakage scorer).
Residual gemma behavior — re-emitting a LIVE registry entry ~1 in 2 hostile
batches — made dedup deterministic instead of prompt-dependent: the hub's
post-parse guard drops specs whose name recreates a `source=live` entry
(logged, unit-tested; co-emitted references stay legal).

---

## F17 — ANTHROPIC_API_KEY in the environment is INVALID (401) — OPERATOR ACTION ⚠️
**Status:** BLOCKING the real-LLM playtest posture · found live by the smoketest gate

`tools/wes_real_llm_smoketest.py` with `WES_DISABLE_FIXTURES=1
WES_REQUIRE_REAL_LLM=1` failed loudly: `401 authentication_error: invalid
x-api-key`. The gate worked exactly as designed (no silent MockBackend
masquerade). Two consequences: (1) rotate the key before the playtest;
(2) `ClaudeBackend.is_available()` only checks key PRESENCE, so the F12 overlay
and boot logs report "claude: available" with a dead key — 401s now return an
unmissable operator-facing "ROTATE YOUR KEY" error (@ `0951c3f8`). Re-run the
smoketest after rotation; recommend a few real L2 narration round-trips as
final confirmation since live-output testing was blocked this session.
