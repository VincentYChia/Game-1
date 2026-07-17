# Crux Foundry — automated playtester & relative-balance tuner

A hermetic, deterministic, isolated automated playtester for Game-1 that runs the
**real headless engine** at scale on ALCF **Crux** (CPU) to answer: *"is every
build/path viable, and by how much?"* — and to auto-tune balance parameters toward
"everything viable."

It is **CPU-only, non-RL, no GPU**. The heavy compute is embarrassingly parallel
runs of the real game rules; the "thinking" is search/aggregation/optimization.

## Pipeline

```
runner.py        one isolated run: boot real engine (hermetic) -> seed -> apply a
                 persona build -> fight the fixed gauntlet through the capture-
                 feeding action-combat path -> capture StatStore -> score ->
                 atomic result.json  (schema-versioned, self-describing)
batch.py         local N-run fan-out + isolation/determinism self-check
viability_report reduce: aggregate personas x seeds -> ranked viability + spread
optimizer.py     grid-search a tunable balance knob to minimize the spread
run_shard.py     one Crux job-array element: a disjoint slice of (persona x seed)
crux_job.pbs     the PBS array + conventions; reduce = viability_report on login
```

## Guarantees (all proven by tests / self-checks)
- **Determinism:** same seed -> bit-identical result across processes (`test_09`,
  batch self-check). Two RNG streams (`CombatManager._rng` + global `random`) seeded
  by `harness.seed_all`, pre-boot + post-boot.
- **Isolation:** one OS process per run + private per-run WMS/StatStore DB dir. Zero
  cross-run bleed; zero shared-content pollution (`GAME1_HERMETIC` disables WES gen).
- **Capture-complete:** combat drives the real action-combat path so StatStore records
  kills/damage/etc. (`test_10`); a capture-blind run fails loudly.

## Run locally
```bash
# one combat-build run
python crux-foundry/runner.py <seed> <out_dir> <persona>
# a FULL PLAYTHROUGH: craft -> equip -> fight -> level (exercises crafting + progression,
# not just combat; makes the progression score meaningful)
python crux-foundry/loop_runner.py <seed> <out_dir> [rounds]
# an emergent LIFE: an agent lives many in-game days -> a narrated CHRONICLE from the
# WMS (daily ledgers + milestones, all hermetic/no-LLM). A corpus of these at scale is
# the deep-simulated-world payoff. (writes story.txt + result.json)
python crux-foundry/life_runner.py <seed> <out_dir> [days]
# determinism/isolation self-check (seeds 1,2,1)
python crux-foundry/batch.py
# relative-viability report (personas x N seeds)
python crux-foundry/viability_report.py 5
# auto-tune a balance knob
python crux-foundry/optimizer.py 2
```
Personas: `str_brawler`, `vit_tank`, `lck_crit`, `balanced`, `melee_basic`.

## Run on Crux
```bash
# 1. edit crux_job.pbs: replace `#PBS -A REPLACE_WITH_ALLOCATION` with a BARE
#    allocation line; set -J range = N_SHARDS-1; tune N_SEEDS/N_SHARDS/OUT.
qsub crux-foundry/crux_job.pbs            # plain qsub — NO -v/-V

# 2. after the array finishes, reduce on the login node (read-only, tolerates
#    failed runs), from the project dir:
module load cray-python
CRUX_REDUCE_ONLY=1 python crux-foundry/viability_report.py <N_SEEDS>
find crux-foundry/runs -name result.json | wc -l    # count outputs (not ls)
```
- **Hermetic + no TF:** `GAME1_HERMETIC=1` (set by the job) disables WES generation
  and skips the TensorFlow/CNN warmup — so Crux's `cray-python` needs no TF, and runs
  write nothing outside their own dir.
- **Robust at scale:** each run has a wall cap (`CRUX_RUN_TIMEOUT_S`, default 120s);
  a hung/crashed run is marked `FAILED.txt` and the shard continues. Resumable via
  skip-if-exists — re-`qsub` to fill gaps.

## Tunable balance knobs (env, default = current game behavior)
| env | default | effect |
|---|---|---|
| `CRUX_GAUNTLET_SIZE` / `CRUX_GAUNTLET_TIER` | 8 / 2 | challenge difficulty (calibrated to differentiate builds) |
| `CRUX_STR_DMG_PER_POINT` | 0.05 | STR damage-per-point (action-combat path) — optimizer knob |
| `CRUX_RUN_TIMEOUT_S` | 120 | per-run wall cap (shard crash isolation) |
| `CRUX_REDUCE_ONLY` | unset | reduce reads existing results only (never launches runs) |

## Findings
See `FINDINGS.md` — balance results with git-sha + confidence. Headline: **F4 — LCK
is a dead stat on the action-combat path** (crit only wired on the unused legacy
path), so pure-luck builds are non-competitive. This is a **wiring bug (dev fix)**,
not a tunable — the optimizer confirms lck_crit stays the viability floor at every
knob value.

## Determinism ledger
`DETERMINISM_LEDGER.md` records every behavior-preserving code change (RNG injection,
wall-clock fixes, hermetic mode, tunable knobs) with verification. All are
env/seed-gated: normal play is byte-identical when the harness isn't driving.

## Design docs
`METHODOLOGY.md` (the traced design + decisions) · `SCORING.md` (the progression
score / viability currency).
