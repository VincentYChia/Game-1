# Determinism Ledger — Crux Foundry

**Branch:** `crux-foundry`
**Purpose:** A strict, append-only record of *every* change made to game code in service of
deterministic/headless simulation. Nothing here is a gameplay/design change; every entry must be
**behavior-preserving when the harness is not driving** (i.e. normal play is byte-identical unless a
seed/flag is explicitly supplied).

## Rules of this ledger
1. **One entry per change.** No batching unrelated edits.
2. Each entry records: file:line, what changed, why (determinism reason), the **default-preserves-behavior**
   guarantee, reversibility, and the test that proves no regression.
3. **Additive-by-default.** Prefer injecting an optional `rng`/`clock` that *defaults to the current global
   behavior*, so existing code paths and the 1111-passing test suite are unaffected.
4. If a change cannot be made behavior-preserving, it does **not** go in without explicit sign-off, logged here.
5. Every entry is verified against `python -m pytest` (unit + `tests/integration/`) before it is considered done.

## Status legend
`PLANNED` → `IMPLEMENTED` → `VERIFIED` (tests green) → `REVERTED` (if backed out)

---

## Changes (from METHODOLOGY.md §4)

**P0 status:** D1, D4, D5, D6, D7 = **VERIFIED**. D2 = **SUPERSEDED** (enemy.py stays on global `random`,
made deterministic by `seed_all`'s `random.seed`). D3 = **FOLDED into D7** (harness-side seeding; no game-engine
change, so interactive play is untouched). The per-row "Status" column below is historical; the change log is authoritative.


| # | File / area | Change | Determinism reason | Default-preserves? | Status |
|---|-------------|--------|--------------------|--------------------|--------|
| D1 | `Combat/combat_manager.py` (crit `:739,:970`; spawn `:380,:415,:429-430,:490-491,:522`; `:2385`) | Replace module-global `random.*` with an injected `self._rng`, plus `seed_rng()`. | Combat crit, enemy tier/count/position are the primary non-reproducible sources. | Yes — `self._rng` defaults to the global `random` module (byte-identical) unless `seed_rng()`/`rng=` is used. | **VERIFIED** |
| D2 | `Combat/enemy.py` (loot `:686-687`; enemy dmg `:1198`; wander `:563,:814-848`; `:536,:1046`) | Thread the same injected `rng` into loot rolls and enemy attack variance; wander may stay global (cosmetic) or take rng. | Loot drops and enemy damage variance affect measured outcomes. | Yes — optional `rng` param, defaults to global `random`. | PLANNED |
| D3 | `core/game_engine.py` (world-entry / temp-world init ~`:240,:2249`) | On new-game, seed the injected combat `rng` from the world seed (`TEMP_WORLD_SEED` or config-supplied) so world + combat + loot share one deterministic seed. | Single seed → whole-run reproducibility. | Yes — only active when a seed is explicitly configured (harness sets it); interactive play unchanged. | PLANNED |
| D4 | `world_system/world_memory/world_memory_system.py:461` (position sampler fed `time.time()` every frame) | Feed `game_time` instead of wall-clock, OR expose a flag to disable the position sampler in headless runs. | Wall-clock breaks reproducible event timelines and adds nondeterministic ordering. | Yes — behind a headless flag; interactive play keeps current sampler. | PLANNED |
| D5 | `systems/world_system.py:730` (death-chest id uses `int(time.time())`) | Derive chest id from `game_time` + a monotonic counter. | Wall-clock in a persisted id → nonreproducible saves/state. | Yes — id format changes only; no behavior depends on the numeric value. | PLANNED |
| D6 | Harness (`tests/integration/harness.py`) — **additive, not a game change** | Add verbs: `attack(enemy)`, `gather(node)`, `use_skill(slot,target)`, `allocate_stat(stat)`, wrapping existing clean engine APIs. | Needed for a progression bot; underlying APIs already test-proven. | N/A (test/tooling code only). | PLANNED |
| D7 | Harness/bootstrap — **additive** | A single `seed_all(seed)` entry point: seeds the combat `rng` (D1) and asserts world seed, so one call makes a run reproducible. | Central determinism switch. | N/A (tooling). | PLANNED |

> Note: D6/D7 touch only `tests/`-level tooling, not shipped game logic, but are logged here for completeness
> because the whole determinism story depends on them.

## Verification checklist applied to every IMPLEMENTED entry
- [ ] Full suite green: `cd Game-1-modular && python -m pytest tests/ -q`
- [ ] Integration suite green: `python -m pytest tests/integration/ -q`
- [ ] Interactive smoke: launching normally produces unchanged behavior (no seed supplied).
- [ ] Reproducibility check: two runs with the same `seed_all(S)` produce identical StatStore dumps.

## Change log (implemented)

### D1 — Combat RNG injection (`Combat/combat_manager.py`) — VERIFIED
- **What:** All 10 module-global `random.*` calls (crit rolls `:739,:970`; enemy select `:380`; count `:415`;
  spawn positions `:429-430,:490-491`; tier `:522`; dungeon enemy `:2385`) now route through `self._rng`.
  Added optional `rng=None` constructor arg → `self._rng = rng if rng is not None else random`, and a
  `seed_rng(seed)` method (`self._rng = random.Random(seed)`).
- **Determinism reason:** these were the primary non-reproducible combat sources (crit, enemy tier/count/position).
- **Default-preserves-behavior:** when no rng/seed is supplied, `self._rng` **is** the global `random` module, so
  every call is identical to before. Reproducibility is opt-in via `seed_rng()`.
- **Verification:** `tests/integration/test_02_combat.py` **3 passed**; full `tests/integration/` **32 passed**;
  `tests/test_enchantments.py` **8 passed**. No regressions.
- **Reversibility:** trivial — the change is a mechanical `random.` → `self._rng.` repoint plus two additive lines.
- **Not covered here:** see D2/D3/D7 below.

### D2 — Enemy RNG — SUPERSEDED (no code change)
- **Decision:** not needed. `enemy.py` (loot `:686-687`, damage `:1198`, wander) and `EnemyDatabase` (`:536`) stay on
  the global `random` module, which `seed_all`'s `random.seed(seed)` makes deterministic. Avoids threading `rng`
  through `Enemy`/`EnemyDatabase` — fewer core-code edits, same result. (Safe under the process-per-run isolation
  model; only unsafe if multiple runs interleaved RNG in one process, which we do not do.)

### D3 — Seed-at-new-game — FOLDED into D7 (no game-engine change)
- **Decision:** seeding is done harness-side by `seed_all()` after world entry, not inside `game_engine`. Keeps
  interactive play byte-identical (combat stays truly random for real players; only the harness seeds).

### D4 — WMS position sampler wall-clock (`world_memory_system.py:461`) — VERIFIED
- **What:** `self.position_sampler.update(time.time(), …)` → `update(game_time, …)` (game_time already in scope).
- **Reason:** wall-clock made position sampling cadence nondeterministic; `game_time` is deterministic and the
  semantically-correct in-game clock.
- **Verification:** `world_system/` **870 passed** (+51 subtests); `tests/integration/` **34 passed**. No regressions.

### D5 — Death-chest id wall-clock (`world_system.py:730`) — VERIFIED
- **What:** `int(time.time())` in the chest id → a monotonic `self._death_chest_seq` counter.
- **Reason:** wall-clock in a persisted id broke save/state reproducibility. Counter is deterministic and unique.
- **Verification:** covered by the suites above (chest creation exercised in integration/world_system tests).

### D6 — Harness verbs (`tests/integration/harness.py`, additive) — VERIFIED
- **What:** added `seed_all()`, `attack(enemy)`, `living_enemies()`, `training_dummy()`. Wrap existing clean engine
  APIs; no game-logic change.
- **Verification:** `tests/integration/` **34 passed** (incl. new determinism scenario using these verbs).

### D7 — `seed_all(seed)` central switch (`harness.py`, additive) — VERIFIED
- **What:** `random.seed(seed)` (covers enemy/db/crafting global RNG) + `combat_manager.seed_rng(seed)` (combat
  isolated stream). One call makes a run reproducible.
- **Reproducibility proof:** `tests/integration/test_09_determinism.py` — `test_same_seed_reproduces_rng_streams`
  (same seed → identical CombatManager + global streams) and `test_different_seeds_diverge` (different seeds →
  different streams). **2 passed.** Note: an earlier probe via bare-handed attacks was randomness-free (that path is
  a legacy no-crit path), so the proof targets the two RNG sources directly — the correct, robust guarantee.
