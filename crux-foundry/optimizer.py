"""
crux-foundry — auto-tuning optimizer (measurement -> tune, and its honest limit).

Grid-searches the tunable balance knob CRUX_STR_DMG_PER_POINT and reports the value
that MINIMIZES the cross-build viability spread. This is the measurement->tune loop
(CPU, non-RL grid search; swap in Bayesian opt / CMA-ES for a bigger space).

It also surfaces the optimizer's LIMIT: if a build is non-competitive because of a
WIRING bug rather than a mis-tuned value, no parameter setting fixes it. FINDINGS F4
(LCK is dead on the action-combat path) is exactly this — so lck_crit stays the
viability floor at every knob value, and the optimizer names it as needing a dev
code fix, not a tune. The optimizer tunes PARAMETERS; it cannot fix WIRING.

CLI:  python crux-foundry/optimizer.py [n_seeds]
"""
import sys
import os
import json
import subprocess
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'runner.py'
RUNS = HERE / 'runs'
PERSONAS = ['str_brawler', 'vit_tank', 'lck_crit', 'balanced']
KNOB = 'CRUX_STR_DMG_PER_POINT'
GRID = [0.03, 0.05, 0.08]


def run(persona, seed, val):
    out = RUNS / f'opt_str{val:.2f}' / f'{persona}_s{seed}'
    res = out / 'result.json'
    if not res.exists():
        env = dict(os.environ, **{KNOB: str(val)})
        subprocess.run([sys.executable, str(RUNNER), str(seed), str(out), persona],
                       check=True, cwd=str(HERE.parent), env=env)
    return json.loads(res.read_text(encoding='utf-8'))


def viability(n, val):
    v = {}
    for p in PERSONAS:
        rs = [run(p, s, val) for s in range(1, n + 1)]
        gsz = rs[0]['manifest']['config']['gauntlet_size']
        mk = statistics.mean(r['metrics']['kills'] for r in rs)
        md = statistics.mean(r['metrics']['deaths'] for r in rs)
        v[p] = mk / gsz - 0.05 * md
    return v


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    RUNS.mkdir(parents=True, exist_ok=True)

    print(f"\n===== AUTO-TUNE {KNOB} (x {n} seeds/persona) =====")
    print(f"objective: minimize viability spread across {PERSONAS}\n")
    print(f'{"STR/pt":>7}  ' + ''.join(f'{p[:9]:>11}' for p in PERSONAS) + f'{"spread":>9}')

    grid_res = []
    for val in GRID:
        v = viability(n, val)
        spread = max(v.values()) - min(v.values())
        floor = min(v, key=v.get)
        grid_res.append((val, v, spread, floor))
        print(f'{val:>7.2f}  ' + ''.join(f'{v[p]:>11.3f}' for p in PERSONAS) + f'{spread:>9.3f}')

    best = min(grid_res, key=lambda x: x[2])
    worst = max(r[2] for r in grid_res)
    invariant_spread = best[2] >= worst - 1e-9

    # Viability RANGE per build across the grid: ~0 range => build does NOT respond
    # to the knob. The untunable floor = the lowest build that is ALSO invariant.
    ranges = {p: max(gr[1][p] for gr in grid_res) - min(gr[1][p] for gr in grid_res)
              for p in PERSONAS}
    v_best = best[1]
    overall_min = min(v_best.values())
    invariant = [p for p in PERSONAS if ranges[p] < 1e-6]
    stuck = min(invariant, key=lambda p: v_best[p]) if invariant else None

    if invariant_spread:
        print(f"\nLIMIT: spread is INVARIANT (~{best[2]:.3f}) across ALL {KNOB} values --")
        print(f"       no setting of this knob balances the builds.")
    else:
        print(f"\nbest {KNOB} = {best[0]:.2f}  (min spread {best[2]:.3f}; baseline {grid_res[0][2]:.3f})")

    if stuck is not None and v_best[stuck] <= overall_min + 1e-9:
        print(f"       '{stuck}' is a viability floor ({v_best[stuck]:.3f}) INVARIANT to the knob")
        print(f"       (range {ranges[stuck]:.3f}) -> NOT tunable here (FINDINGS F4: LCK dead on")
        print(f"       the action path). Auto-tuning tunes PARAMETERS; a WIRING bug needs code.")


if __name__ == '__main__':
    main()
