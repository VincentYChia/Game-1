"""
crux-foundry — one Crux job-array shard.

Runs a disjoint slice of the (persona x seed) matrix as independent runner
SUBPROCESSES (process-per-run isolation — proven safe; singletons never shared).
Resumable: a run whose result.json exists is skipped, so a killed/re-queued array
element resumes cleanly. Writes result.json into OUT/<persona>_s<seed>.

CLI:  python crux-foundry/run_shard.py <shard_index> <n_shards> <n_seeds> <out_dir>
      (shard_index = $PBS_ARRAY_INDEX)
"""
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'runner.py'
PERSONAS = ['str_brawler', 'vit_tank', 'lck_crit', 'balanced']


def main():
    shard = int(sys.argv[1])
    n_shards = int(sys.argv[2])
    n_seeds = int(sys.argv[3])
    out = Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)

    # Full matrix, then this shard's disjoint stride (balances load across shards).
    matrix = [(p, s) for s in range(1, n_seeds + 1) for p in PERSONAS]
    mine = matrix[shard::n_shards]

    for persona, seed in mine:
        d = out / f'{persona}_s{seed}'
        if (d / 'result.json').exists():
            continue  # resumable
        # runner writes result.json atomically (temp + os.replace)
        subprocess.run([sys.executable, str(RUNNER), str(seed), str(d), persona],
                       check=True, cwd=str(HERE.parent))
    print(f"[shard {shard}/{n_shards}] completed {len(mine)} runs")


if __name__ == '__main__':
    main()
