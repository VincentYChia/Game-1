"""
crux-foundry — one Crux job-array shard.

Runs a disjoint slice of the (persona x seed) matrix as independent runner
SUBPROCESSES (process-per-run isolation — proven safe; singletons never shared).
Resumable: a run whose result.json exists is skipped, so a killed/re-queued array
element resumes cleanly. Writes result.json into OUT/<persona>_s<seed>.

CLI:  python crux-foundry/run_shard.py <shard_index> <n_shards> <n_seeds> <out_dir>
      (shard_index = $PBS_ARRAY_INDEX)
"""
import os
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'runner.py'
PERSONAS = ['str_brawler', 'vit_tank', 'lck_crit', 'balanced']
RUN_TIMEOUT_S = int(os.environ.get('CRUX_RUN_TIMEOUT_S', '120'))  # per-run wall cap


def main():
    shard = int(sys.argv[1])
    n_shards = int(sys.argv[2])
    n_seeds = int(sys.argv[3])
    out = Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)

    # Full matrix, then this shard's disjoint stride (balances load across shards).
    matrix = [(p, s) for s in range(1, n_seeds + 1) for p in PERSONAS]
    mine = matrix[shard::n_shards]

    ok = failed = skipped = 0
    for persona, seed in mine:
        d = out / f'{persona}_s{seed}'
        if (d / 'result.json').exists():
            skipped += 1  # resumable — already done
            continue
        # Crash isolation: a hung (timeout) or crashed run must NOT kill the shard.
        # Mark it FAILED and continue so the array element completes.
        try:
            subprocess.run([sys.executable, str(RUNNER), str(seed), str(d), persona],
                           check=True, cwd=str(HERE.parent), timeout=RUN_TIMEOUT_S)
            ok += 1
        except Exception as e:
            failed += 1
            d.mkdir(parents=True, exist_ok=True)
            (d / 'FAILED.txt').write_text(f'{type(e).__name__}: {e}\n', encoding='utf-8')
            sys.stderr.write(f"[shard {shard}] FAILED {persona} s{seed}: {type(e).__name__}\n")
    print(f"[shard {shard}/{n_shards}] {ok} ok, {failed} failed, {skipped} skipped of {len(mine)}")


if __name__ == '__main__':
    main()
