"""
crux-foundry — full-loop playthrough persona (expansion #1: NOT just combat).

Plays the REAL player loop headlessly for K rounds:
  CRAFT (refine ore->ingot, smith ingot->gear via the real completion pipeline)
  -> FIGHT (a controlled wave through the real action-combat path)
  -> LEVEL + allocate stat points.
Materials are seeded with give() (gather navigation has no headless pathfinder;
teleport-gathering is a later increment). This exercises the CRAFTING ECONOMY and
PROGRESSION pacing + makes the progression SCORE meaningful (it reads ~0 on a
combat-only gauntlet). Reuses runner.py's hermetic/isolated/seeded boot + capture
+ scoring, so it inherits determinism & isolation.

CLI:  python crux-foundry/loop_runner.py <seed> <out_dir> [rounds]
"""
import os
import sys
import io
import json
import contextlib
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Reuse the runner's boot/capture/scoring/gauntlet (importing it sets up env+paths).
from runner import (boot_engine, capture, compute_score, spawn_gauntlet,
                    _GIT_SHA, SCHEMA_VERSION, PROJECT_ROOT)

ROUNDS = 4
STAT_POLICY = 'strength'
WAVE_SIZE = 3            # enemies to fight per round
SWINGS_CAP = 30
CRAFT_SUCCESS = {"success": True, "earned_points": 100, "max_points": 100}


def _t1_recipes(discipline, limit):
    from data.databases.recipe_db import RecipeDatabase
    rdb = RecipeDatabase.get_instance()
    by_station = getattr(rdb, 'recipes_by_station', {})
    recs = [r for r in by_station.get(discipline, []) if getattr(r, 'station_tier', 1) <= 1]
    return recs[:limit]


def _recipe_inputs(recipe):
    out = []
    for inp in getattr(recipe, 'inputs', []) or []:
        mid = inp.get('materialId') or inp.get('itemId')
        qty = int(inp.get('quantity', inp.get('qty', 1)))
        if mid:
            out.append((mid, qty))
    return out


def _craft_round(h, recipes):
    """Seed each recipe's inputs and craft it through the real pipeline."""
    done = []
    for r in recipes:
        inputs = _recipe_inputs(r)
        for mid, qty in inputs:
            h.give(mid, qty)
        try:
            h.craft(r.station_type, r.recipe_id, dict(CRAFT_SUCCESS))
            done.append(r.output_id)
        except Exception:
            pass
    return done


def _fight_wave(h):
    eng = h.engine
    c = eng.character
    gauntlet = spawn_gauntlet(eng, WAVE_SIZE, 1)
    kills = 0
    for e in gauntlet:
        c.position.x, c.position.y = e.position[0] - 1.0, e.position[1]
        for _ in range(SWINGS_CAP):
            if not e.is_alive:
                break
            h.melee_swing(e, frames=30)
        if not e.is_alive:
            kills += 1
        h.tick(3)
    return kills


def drive_loop(h, rounds=ROUNDS):
    c = h.engine.character
    refine = _t1_recipes('refining', 3)
    smith = _t1_recipes('smithing', 3)

    total_crafts, total_kills = [], 0
    for _ in range(rounds):
        total_crafts += _craft_round(h, refine)
        total_crafts += _craft_round(h, smith)
        try:
            h.equip('iron_shortsword')          # wield a weapon we just crafted
            c._selected_slot = 'mainHand'
        except Exception:
            pass
        total_kills += _fight_wave(h)
        while c.leveling.unallocated_stat_points > 0:
            c.allocate_stat_point(STAT_POLICY)
    return {'rounds': rounds, 'crafts': total_crafts, 'crafts_n': len(total_crafts),
            'kills': total_kills}


def run_loop_once(seed, out_dir, rounds=ROUNDS):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wms_dir = out_dir / 'wms'
    wms_dir.mkdir(exist_ok=True)

    import random
    with contextlib.redirect_stdout(io.StringIO()):
        random.seed(seed)
        eng = boot_engine(wms_dir)
        from tests.integration.harness import PlaytestHarness
        h = PlaytestHarness(eng)
        h.settle()
        h.seed_all(seed)
        drive = drive_loop(h, rounds)
        cap = capture(eng)

    combat = cap['combat']
    result = {
        'schema': SCHEMA_VERSION,
        'manifest': {'run_id': f'fullloop-{seed}', 'seed': seed, 'persona': 'full_loop',
                     'config': {'rounds': rounds, 'stat_policy': STAT_POLICY}, 'git_sha': _GIT_SHA},
        'outcome': 'ok' if combat.get('combat.damage_dealt', 0.0) > 0.0 else 'capture_blind',
        'score': compute_score(cap['all'], cap['level']),
        'metrics': {
            'level': cap['level'], 'exp': cap['exp'],
            'rounds': drive['rounds'], 'crafts_n': drive['crafts_n'], 'kills': drive['kills'],
            'damage_dealt': combat.get('combat.damage_dealt', 0.0),
            'total_stat_keys': cap['total_stat_keys'],
        },
        'crafting_stats': {k: v for k, v in cap['all'].items() if k.startswith('crafting')},
        'progression_stats': cap['progression'],
    }
    tmp = out_dir / 'result.json.tmp'
    tmp.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    os.replace(tmp, out_dir / 'result.json')
    return result


def main():
    if len(sys.argv) < 3:
        print("usage: loop_runner.py <seed> <out_dir> [rounds]")
        sys.exit(2)
    seed = int(sys.argv[1]); out_dir = sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else ROUNDS
    r = run_loop_once(seed, out_dir, rounds)
    print(json.dumps({**r['manifest'], **r['metrics'],
                      'score': r['score']['total'], 'outcome': r['outcome']}, default=str))


if __name__ == '__main__':
    main()
