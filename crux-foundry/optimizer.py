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
# Post-F4-fix, LCK crit is WIRED into real combat, so it's now the lever that can
# close the lck_crit gap. (Pre-fix this knob was dead; the optimizer correctly
# reported the STR knob left lck_crit an untunable floor -- see FINDINGS F4 / git.)
KNOB = 'CRUX_LCK_CRIT_PER_POINT'
GRID = [0.02, 0.06, 0.10, 0.14]


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
    print(f'{"val":>7}  ' + ''.join(f'{p[:9]:>11}' for p in PERSONAS) + f'{"spread":>9}')

    grid_res = []
    for val in GRID:
        v = viability(n, val)
        spread = max(v.values()) - min(v.values())
        floor = min(v, key=v.get)
        grid_res.append((val, v, spread, floor))
        print(f'{val:>7.2f}  ' + ''.join(f'{v[p]:>11.3f}' for p in PERSONAS) + f'{spread:>9.3f}')

    best = min(grid_res, key=lambda x: x[2])
    base_spread = grid_res[0][2]

    # Viability RANGE per build across the grid: ~0 range => the build does NOT
    # respond to this knob. NB: invariance is EXPECTED for a build with no points in
    # the tuned stat (str/vit have 0 luck) -- that is NOT a bug. A wiring bug is when
    # a build that SHOULD respond is bit-identical across the grid (e.g. F4 pre-fix).
    ranges = {p: max(gr[1][p] for gr in grid_res) - min(gr[1][p] for gr in grid_res)
              for p in PERSONAS}
    responders = [p for p in PERSONAS if ranges[p] >= 1e-6]
    invariant = [p for p in PERSONAS if ranges[p] < 1e-6]
    reduced = (1 - best[2] / base_spread) * 100 if base_spread else 0.0

    print(f"\nbest {KNOB} = {best[0]:.2f}  (spread {best[2]:.3f}; baseline {base_spread:.3f}, "
          f"{reduced:+.0f}% vs baseline)")
    if responders:
        print("responds to knob:   " + ", ".join(f"{p}(range {ranges[p]:.3f})" for p in responders))
    if invariant:
        print("invariant (no points in the tuned stat -> expected): " + ", ".join(invariant))
    if best[2] >= base_spread - 1e-9:
        print("LIMIT: this knob does not reduce the spread -- the binding build does not use")
        print("       the tuned stat. If a build that SHOULD respond is bit-identical across")
        print("       the grid, THAT is a wiring bug (e.g. FINDINGS F4 pre-fix) -- confirm directly.")


if __name__ == '__main__':
    main()
