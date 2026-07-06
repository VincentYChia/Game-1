"""
crux-foundry — local batch runner (embryo of the Crux job array).

Runs N isolated runs (one SUBPROCESS each = trivially isolated singletons + DB),
writes per-run result.json + an aggregated index.jsonl, and reports a
reproducibility/independence check. On Crux this same shape becomes a PBS job
array (one array element per seed/param block); here it's subprocess fan-out.

Resumable: a run whose result.json exists is skipped.

CLI:  python crux-foundry/batch.py
"""
import sys
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'runner.py'
RUNS_DIR = HERE / 'runs'


def run_batch(specs):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (seed, persona) in enumerate(specs):
        out = RUNS_DIR / f'run_{i:04d}_s{seed}'
        res_file = out / 'result.json'
        if not res_file.exists():                      # resumable: skip if done
            subprocess.run([sys.executable, str(RUNNER), str(seed), str(out), persona],
                           check=True, cwd=str(HERE.parent))
        r = json.loads(res_file.read_text(encoding='utf-8'))
        index.append({**r['manifest'], **r['metrics'],
                      'score': r['score']['total'], 'score_breakdown': r['score']['breakdown'],
                      'outcome': r['outcome']})
    (RUNS_DIR / 'index.jsonl').write_text(
        '\n'.join(json.dumps(x) for x in index) + '\n', encoding='utf-8')
    return index


def main():
    # run0 & run2 share a seed (reproducibility); run1 differs (independence)
    specs = [(1, 'melee_basic'), (2, 'melee_basic'), (1, 'melee_basic')]
    index = run_batch(specs)

    print("\n===== BATCH INDEX (index.jsonl) =====")
    for x in index:
        print(json.dumps(x))

    from collections import Counter
    outcomes = Counter(x['outcome'] for x in index)
    print(f"\noutcomes: {dict(outcomes)}")
    if outcomes.get('capture_blind', 0):
        print("!! WARNING: capture_blind run(s) — the driving path is not feeding the capture layer")

    # Post-hermetic the whole run is bit-deterministic, so the full signature
    # (incl. damage_taken) must be identical for a fixed seed and differ across seeds.
    def run_sig(x):
        return (x['damage_dealt'], x['damage_taken'], x['combat_kills'],
                x['exp'], x['level'], x['kills'], x['total_stat_keys'])

    r0, r1, r2 = index[0], index[1], index[2]
    repro = run_sig(r0) == run_sig(r2)
    indep = run_sig(r0) != run_sig(r1)
    fixed_challenge = r0['gauntlet_ids'] == r1['gauntlet_ids'] == r2['gauntlet_ids']

    print("\n===== ISOLATION / DETERMINISM CHECK =====")
    print("isolation: each run ran in its own process with a private WMS/StatStore DB dir")
    print(f"fixed challenge across seeds (gauntlet_ids equal): {fixed_challenge}  {r0['gauntlet_ids']}")
    print(f"same-seed fully reproducible across processes (run0 == run2): {repro}")
    print(f"  run0 sig: {run_sig(r0)}")
    print(f"  run2 sig: {run_sig(r2)}")
    print(f"different-seed independent (run0 != run1): {indep}  (run1 damage_taken={r1['damage_taken']:.3f})")
    print("RESULT:", "PASS" if (repro and indep and fixed_challenge) else "FAIL")


if __name__ == '__main__':
    main()
