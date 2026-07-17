"""
crux-foundry — relative-viability report (the balance payoff).

Runs each build persona across N seeds against the fixed calibrated gauntlet,
aggregates combat viability (kills / deaths / damage-taken / clear-rate), ranks
the builds, and reports the relative-balance SPREAD — the answer to the user's
"is every path viable / are they roughly even?". Multi-seed averaging cancels
crit variance (FINDINGS F2). Resumable (skip runs whose result.json exists).

CLI:  python crux-foundry/viability_report.py [n_seeds]
"""
import os
import sys
import json
import subprocess
import statistics
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'runner.py'
RUNS = HERE / 'runs'
PERSONAS = ['str_brawler', 'vit_tank', 'lck_crit', 'balanced']
REDUCE_ONLY = os.environ.get('CRUX_REDUCE_ONLY') == '1'  # login-node reduce: never launch runs


def run(persona, seed):
    out = RUNS / f'{persona}_s{seed}'
    res = out / 'result.json'
    if not res.exists():
        if REDUCE_ONLY:
            return None  # read-only reduce: skip missing/failed runs
        subprocess.run([sys.executable, str(RUNNER), str(seed), str(out), persona],
                       check=True, cwd=str(HERE.parent))
    return json.loads(res.read_text(encoding='utf-8'))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seeds = list(range(1, n + 1))
    RUNS.mkdir(parents=True, exist_ok=True)

    data = defaultdict(list)
    for p in PERSONAS:
        for s in seeds:
            r = run(p, s)
            if r is not None:
                data[p].append(r)

    have = [p for p in PERSONAS if data[p]]
    if not have:
        print("no results to reduce (reduce-only with nothing produced yet?)")
        return
    cfg = data[have[0]][0]['manifest']['config']
    gsz, gtr = cfg['gauntlet_size'], cfg['gauntlet_tier']

    print(f"\n===== RELATIVE-VIABILITY REPORT (personas x {n} seeds) =====")
    print(f"challenge: tier {gtr} / size {gsz}, weapon {cfg['weapon']}, level-10 builds")
    print(f"viability index = mean(kills)/{gsz} - 0.05*mean(deaths)  (higher = more viable)\n")
    print(f'{"persona":<14}{"kills":>9}{"deaths":>9}{"dmg_taken":>11}{"clear%":>8}{"viability":>11}')

    rows = []
    for p in have:
        rs = data[p]
        mk = statistics.mean(r['metrics']['kills'] for r in rs)
        md = statistics.mean(r['metrics']['deaths'] for r in rs)
        mdmg = statistics.mean(r['metrics']['damage_taken'] for r in rs)
        clear = statistics.mean(1 if r['outcome'] == 'cleared' else 0 for r in rs)
        viab = mk / gsz - 0.05 * md
        rows.append((p, mk, md, mdmg, clear, viab))

    rows.sort(key=lambda x: -x[5])
    for p, mk, md, mdmg, cl, viab in rows:
        print(f'{p:<14}{mk:>9.2f}{md:>9.2f}{mdmg:>11.1f}{cl*100:>7.0f}%{viab:>11.3f}')

    viabs = [r[5] for r in rows]
    spread = max(viabs) - min(viabs)
    mean_v = statistics.mean(viabs)
    rel = spread / abs(mean_v) if mean_v else float('inf')
    print(f"\nviability spread (max-min): {spread:.3f}  ({rel*100:.0f}% of mean)")
    print(f"strongest: {rows[0][0]}   weakest: {rows[-1][0]}")
    print("verdict: lower spread = more balanced (all paths ~equally viable).")
    print("         a large spread names the dominant + dead builds to rebalance.")


if __name__ == '__main__':
    main()
