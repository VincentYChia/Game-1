"""
crux-foundry — local end-to-end smoke run (embryo of the Crux playtest worker).

Boots the REAL GameEngine headless (no pytest, no window), seeds it for
reproducibility, drives a short combat burst, then dumps what the capture layer
(StatTracker/StatStore + WMS) actually recorded. This proves the whole spine
works together locally before any scale-out.

Run:  python crux-foundry/smoke_run.py [seed]
"""
import os
import sys
import io
import json
import tempfile
import contextlib
from pathlib import Path

# Force UTF-8 stdio so the game's Unicode prints (✓, ⚔️, …) don't crash on a
# Windows cp1252 console. (Linux/Crux stdout is already UTF-8.)
for _s in ('stdout', 'stderr'):
    try:
        getattr(sys, _s).reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# SDL dummy MUST be set before pygame is imported anywhere.
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(os.path.dirname(HERE), 'Game-1-modular')
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)  # all JSON paths are relative to here


def boot_engine(save_dir: Path):
    """Boot GameEngine + enter the temp world exactly as conftest does."""
    import core.paths as paths
    paths._path_manager.save_path = Path(save_dir)

    from core.config import Config
    _orig = Config.init_screen_settings
    Config.init_screen_settings = lambda width=None, height=None, fullscreen=False: _orig(1280, 720, False)

    from core.game_engine import GameEngine
    eng = GameEngine()
    eng.handle_start_menu_selection(3)  # "Temporary World" (TEMP_WORLD_SEED)
    assert eng.character is not None, "temp world entry must create a character"

    if getattr(eng.character, 'class_selection_open', False):
        from data.databases.class_db import ClassDatabase
        class_def = next(iter(ClassDatabase.get_instance().classes.values()))
        eng.character.select_class(class_def)
        eng.character.class_selection_open = False
    return eng


def run_combat_burst(harness, max_targets=6, swings_cap=30):
    """Fight the spawned enemies through the REAL action-combat path so the
    full capture pipeline fires. Teleports the player adjacent to each target
    (the bot will path there for real later; here we validate capture)."""
    c = harness.engine.character
    kills = 0
    for _ in range(max_targets):
        living = harness.living_enemies(exclude_dummy=True)
        if not living:
            break
        target = living[0]
        # Put the player within melee reach, facing the enemy.
        c.position.x = target.position[0] - 1.0
        c.position.y = target.position[1]
        for _ in range(swings_cap):
            if not target.is_alive:
                break
            harness.melee_swing(target, frames=30)
        if not target.is_alive:
            kills += 1
        harness.tick(3)
    return kills


def capture_summary(eng):
    """Read back what the capture layer recorded — the point of the smoke run."""
    c = eng.character
    out = {
        'level': getattr(c.leveling, 'level', None),
        'current_exp': getattr(c.leveling, 'current_exp', None),
        'hp': f"{getattr(c, 'health', None)}/{getattr(c, 'max_health', None)}",
    }
    # StatTracker writes to a StatStore (get_all/get_prefix); to_dict() is only a
    # curated summary, so read the store directly (flush buffered writes first).
    st = getattr(c, 'stat_tracker', None)
    store = getattr(st, '_store', None) if st is not None else None
    if store is not None:
        try:
            if hasattr(store, 'flush'):
                store.flush()
            out['total_stat_keys'] = len(store.get_all())
            out['combat_sample'] = store.get_prefix('combat')
            out['progression_sample'] = store.get_prefix('progression')
        except Exception as e:
            out['store_error'] = repr(e)
    else:
        out['total_stat_keys'] = 'StatStore unavailable'
    # WMS event timeline (dogfooding the history mechanism)
    wm = getattr(eng, 'world_memory', None)
    es = getattr(wm, 'event_store', None) if wm else None
    if es is not None:
        for meth in ('count', 'count_events', 'total_count'):
            if hasattr(es, meth):
                try:
                    out['wms_events_recorded'] = getattr(es, meth)()
                except Exception as e:
                    out['wms_events_recorded'] = f'query-failed: {e!r}'
                break
    return out


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 12345
    with tempfile.TemporaryDirectory(prefix='crux_smoke_', ignore_cleanup_errors=True) as td:
        # Silence the game's verbose per-frame prints during boot + combat;
        # we only care about the capture summary.
        with contextlib.redirect_stdout(io.StringIO()):
            eng = boot_engine(Path(td))
            from tests.integration.harness import PlaytestHarness
            h = PlaytestHarness(eng)
            h.settle()
            h.seed_all(seed)
            kills = run_combat_burst(h)
            summary = capture_summary(eng)
        summary['seed'] = seed
        summary['kills'] = kills

        print("\n===== CRUX-FOUNDRY SMOKE RUN SUMMARY =====")
        print(json.dumps(summary, indent=2, default=str))
        print("==========================================")


if __name__ == '__main__':
    main()
