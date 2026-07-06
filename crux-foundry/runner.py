"""
crux-foundry — the run unit:  run_once(seed, out_dir, persona) -> result

Boots the real GameEngine headless in an ISOLATED per-run save dir (so the
WMS/StatStore SQLite is private to the run), seeds it, drives a persona against a
controlled enemy gauntlet through the capture-feeding action-combat path,
captures the StatStore, GUARDS against capture-blindness, and writes result.json
atomically. This is the embryo of the Crux job-array worker.

CLI:  python crux-foundry/runner.py <seed> <out_dir> [persona]
"""
import os
import sys
import io
import json
import contextlib
from pathlib import Path

for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(os.path.dirname(HERE), 'Game-1-modular')
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

GAUNTLET_SIZE = 3
GAUNTLET_TIER = 1
SWINGS_CAP = 30


def boot_engine(save_dir: Path):
    """Boot GameEngine + enter the temp world; WMS/StatStore write to save_dir."""
    import core.paths as paths
    paths._path_manager.save_path = Path(save_dir)

    from core.config import Config
    _orig = Config.init_screen_settings
    Config.init_screen_settings = lambda width=None, height=None, fullscreen=False: _orig(1280, 720, False)

    from core.game_engine import GameEngine
    eng = GameEngine()
    eng.handle_start_menu_selection(3)
    if getattr(eng.character, 'class_selection_open', False):
        from data.databases.class_db import ClassDatabase
        eng.character.select_class(next(iter(ClassDatabase.get_instance().classes.values())))
        eng.character.class_selection_open = False
    return eng


def spawn_gauntlet(eng, n, tier):
    """Clean arena at (0,0), clear boot-spawned enemies, spawn a controlled,
    hitbox-registered gauntlet in a row in front of the player."""
    from Combat.enemy import Enemy
    cm = eng.combat_manager
    c = eng.character
    c.position.x, c.position.y = 0.0, 0.0
    cm.enemies.clear()
    cm.corpses.clear()
    chunk = (0, 0)
    gauntlet = []
    for i in range(n):
        edef = cm.enemy_db.get_random_enemy(tier)
        if edef is None:
            continue
        e = Enemy(edef, (2.0 + i * 2.0, 0.0), chunk)
        cm.enemies.setdefault(chunk, []).append(e)
        cm._register_enemy_action_combat(e)
        gauntlet.append(e)
    return gauntlet


def drive_melee_persona(harness):
    """Persona 'melee_basic': walk up to each gauntlet enemy and swing until dead."""
    eng = harness.engine
    c = eng.character
    gauntlet = spawn_gauntlet(eng, GAUNTLET_SIZE, GAUNTLET_TIER)
    kills = 0
    for e in gauntlet:
        c.position.x, c.position.y = e.position[0] - 1.0, e.position[1]
        for _ in range(SWINGS_CAP):
            if not e.is_alive:
                break
            harness.melee_swing(e, frames=30)
        if not e.is_alive:
            kills += 1
        harness.tick(3)
    return {'gauntlet': len(gauntlet), 'kills': kills}


def capture(eng):
    c = eng.character
    store = c.stat_tracker._store
    store.flush()
    return {
        'level': c.leveling.level,
        'exp': c.leveling.current_exp,
        'combat': store.get_prefix('combat'),
        'progression': store.get_prefix('progression'),
        'total_stat_keys': len(store.get_all()),
    }


def run_once(seed, out_dir, persona='melee_basic'):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wms_dir = out_dir / 'wms'
    wms_dir.mkdir(exist_ok=True)

    import random
    with contextlib.redirect_stdout(io.StringIO()):
        # Seed BEFORE boot so ambient enemy spawns + spawn-timers created during
        # world entry are deterministic per seed; seed_all() after boot re-seeds
        # for the fight (combat crit stream + a clean global-stream restart).
        random.seed(seed)
        eng = boot_engine(wms_dir)
        from tests.integration.harness import PlaytestHarness
        h = PlaytestHarness(eng)
        h.settle()
        h.seed_all(seed)
        drive = drive_melee_persona(h)
        cap = capture(eng)

    combat = cap['combat']
    capture_ok = combat.get('combat.damage_dealt', 0.0) > 0.0
    result = {
        'manifest': {'run_id': f'{persona}-{seed}', 'seed': seed, 'persona': persona},
        'outcome': 'ok' if capture_ok else 'CAPTURE_BLIND',
        'metrics': {
            'level': cap['level'],
            'exp': cap['exp'],
            'gauntlet': drive['gauntlet'],
            'kills': drive['kills'],
            'damage_dealt': combat.get('combat.damage_dealt', 0.0),
            'damage_taken': combat.get('combat.damage_taken', 0.0),
            'combat_kills': combat.get('combat.kills', 0.0),
            'total_stat_keys': cap['total_stat_keys'],
        },
        'combat_stats': combat,
        'progression_stats': cap['progression'],
    }
    tmp = out_dir / 'result.json.tmp'
    tmp.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    os.replace(tmp, out_dir / 'result.json')  # atomic
    return result


def main():
    if len(sys.argv) < 3:
        print("usage: runner.py <seed> <out_dir> [persona]")
        sys.exit(2)
    seed = int(sys.argv[1])
    out_dir = sys.argv[2]
    persona = sys.argv[3] if len(sys.argv) > 3 else 'melee_basic'
    r = run_once(seed, out_dir, persona)
    print(json.dumps({**r['manifest'], **r['metrics'], 'outcome': r['outcome']}, default=str))


if __name__ == '__main__':
    main()
