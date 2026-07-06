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
os.environ.setdefault('GAME1_HERMETIC', '1')  # no WES content generation / no shared-tree writes

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(os.path.dirname(HERE), 'Game-1-modular')
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

SCHEMA_VERSION = 1
WEAPON_ID = 'iron_shortsword'
GAUNTLET_SIZE = 3
GAUNTLET_TIER = 1
GAUNTLET_COMPOSE_SEED = 20260706  # fixed: identical challenge across all run seeds
SWINGS_CAP = 30


def _git_sha():
    try:
        import subprocess
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return 'unknown'


_GIT_SHA = _git_sha()


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
    # Compose a FIXED challenge (same enemies every run) independent of the run
    # seed, so seeds vary only combat RNG (crit / enemy-damage / loot), not the
    # challenge itself. Save/restore the global RNG so the run-seed stream that
    # the fight draws from is untouched.
    import random
    _state = random.getstate()
    random.seed(GAUNTLET_COMPOSE_SEED)
    try:
        for i in range(n):
            edef = cm.enemy_db.get_random_enemy(tier)
            if edef is None:
                continue
            e = Enemy(edef, (2.0 + i * 2.0, 0.0), chunk)
            cm.enemies.setdefault(chunk, []).append(e)
            cm._register_enemy_action_combat(e)
            gauntlet.append(e)
    finally:
        random.setstate(_state)
    return gauntlet


def drive_melee_persona(harness):
    """Persona 'melee_basic': walk up to each gauntlet enemy and swing until dead."""
    eng = harness.engine
    c = eng.character
    # Arm the persona with a T1 sword (30 base dmg) so combat is realistic:
    # crit fires on the tag path and the persona can actually win fights.
    harness.equip(WEAPON_ID)
    c._selected_slot = 'mainHand'
    gauntlet = spawn_gauntlet(eng, GAUNTLET_SIZE, GAUNTLET_TIER)
    gauntlet_ids = [getattr(e.definition, 'enemy_id', '?') for e in gauntlet]
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
    return {'gauntlet': len(gauntlet), 'gauntlet_ids': gauntlet_ids, 'kills': kills}


def capture(eng):
    c = eng.character
    store = c.stat_tracker._store
    store.flush()
    allstats = store.get_all()
    return {
        'level': c.leveling.level,
        'exp': c.leveling.current_exp,
        'combat': store.get_prefix('combat'),
        'progression': store.get_prefix('progression'),
        'total_stat_keys': len(allstats),
        'all': allstats,
    }


def compute_score(stats, level):
    """SCORING.md progression score — the universal viability currency.

    `stats` is the full StatStore dict (name -> value). Combat performance is NOT
    scored here (kills are a *means* to progression; they live in metrics). The
    score measures how far a persona progressed, so a combat-only gauntlet scores
    low BY DESIGN — meaningful totals need a full-loop persona (level/craft/gather).
    Weights are gaming-hardened per SCORING.md (no raw event-volume term).
    """
    def sv(k):
        return float(stats.get(k, 0.0))

    b = {}
    b['levels'] = 100.0 * max(0, level - 1)                    # +100 / level gained (start=1)
    b['skills'] = 20.0 * sv('progression.skills_learned')      # +20 / skill
    b['titles'] = 40.0 * sv('progression.titles_earned')       # +40 / title  (verify key on full-loop)
    b['discovery'] = 5.0 * sv('encyclopedia.discovered')       # +5 / first-time discovery
    # gathering: +1 per 50 resources, scaled by tier
    g = 0.0
    for t in range(1, 5):
        g += (sv(f'gathering.collected.tier.{t}') / 50.0) * t
    b['gathering'] = g
    # crafting: +15/+10/+5/0 diminishing per DISTINCT recipe first-crafted.
    # (StatStore per-recipe key TBD on a crafting persona; 0 for the combat gauntlet.)
    b['crafting'] = 0.0

    b = {k: round(v, 2) for k, v in b.items()}
    return {'total': round(sum(b.values()), 2), 'breakdown': b}


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
    kills, gauntlet_n = drive['kills'], drive['gauntlet']
    captured = combat.get('combat.damage_dealt', 0.0) > 0.0

    # Explicit terminal state. capture_blind is a HARNESS failure (the driving
    # path didn't feed the capture layer) — surfaced loudly, never silent.
    if not captured:
        outcome = 'capture_blind'
    elif gauntlet_n > 0 and kills >= gauntlet_n:
        outcome = 'cleared'
    elif kills == 0:
        outcome = 'wiped'
    else:
        outcome = 'partial'

    result = {
        'schema': SCHEMA_VERSION,
        'manifest': {
            'run_id': f'{persona}-{seed}',
            'seed': seed,
            'persona': persona,
            'config': {
                'weapon': WEAPON_ID,
                'gauntlet_size': GAUNTLET_SIZE,
                'gauntlet_tier': GAUNTLET_TIER,
                'compose_seed': GAUNTLET_COMPOSE_SEED,
            },
            'git_sha': _GIT_SHA,
        },
        'outcome': outcome,
        'score': compute_score(cap['all'], cap['level']),
        'metrics': {
            'level': cap['level'],
            'exp': cap['exp'],
            'gauntlet': gauntlet_n,
            'gauntlet_ids': drive['gauntlet_ids'],
            'kills': kills,
            'deaths': combat.get('combat.deaths', 0.0),
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

    if outcome == 'capture_blind':
        sys.stderr.write(
            f"[runner] WARNING {result['manifest']['run_id']}: CAPTURE_BLIND — combat "
            f"stats empty; the driving path is not feeding the capture layer\n")
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
