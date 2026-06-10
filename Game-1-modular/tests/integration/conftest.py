"""
Headless playtest fixtures — boots the REAL GameEngine and plays it.

These are integration tests in the truest sense: the same GameEngine,
WorldSystem, CombatManager, crafters, and SaveManager the player runs,
driven through the same entry points the player's mouse and keyboard hit
(handle_events / handle_start_menu_selection / update / render), with the
SDL dummy video driver instead of a window.

Design notes:
- SDL env vars MUST be set before pygame is imported anywhere in the
  process (pattern proven by tests/test_quest_log_overlay.py).
- Screen is pinned to 1280x720: under the dummy driver the auto-detect
  path of Config.init_screen_settings() can report 0x0, which would make
  UI_SCALE zero and crash layout math. Fixed dims also make every UI
  coordinate reproducible across machines.
- Saves are redirected to a pytest temp dir by reassigning the PathManager
  singleton's save_path; core.paths convenience functions read it at call
  time, so SaveManager / faction.db / WMS SQLite all follow.
- One engine per test session (boot is heavy: every database, world gen,
  combat config). Scenarios share the world like a real play session.
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)  # suite-wide convention (all JSON paths are relative)

import pytest  # noqa: E402


@pytest.fixture(scope='session')
def engine(tmp_path_factory):
    """Boot the real GameEngine headless and enter a temporary world.

    Uses the exact same code path as the player clicking "Temporary World"
    on the start menu (handle_start_menu_selection(3)): world generation
    with TEMP_WORLD_SEED, character creation, enemy + training-dummy
    spawning, class selection prompt.
    """
    # Redirect all save-side writes (autosave, faction.db, world memory)
    # away from the developer's real saves BEFORE anything opens them.
    from pathlib import Path
    import core.paths as paths
    save_dir = tmp_path_factory.mktemp('saves')
    paths._path_manager.save_path = Path(save_dir)

    # Pin deterministic screen dims through the engine's own init call.
    from core.config import Config
    _orig_init = Config.init_screen_settings

    def _headless_init(width=None, height=None, fullscreen=False):
        _orig_init(width=1280, height=720, fullscreen=False)

    Config.init_screen_settings = _headless_init

    from core.game_engine import GameEngine
    eng = GameEngine()

    # Enter the temporary world exactly as the menu click does.
    eng.handle_start_menu_selection(3)
    assert eng.character is not None, "Temp world entry must create a character"

    # Resolve the class-selection prompt through the real selection API.
    if eng.character.class_selection_open:
        from data.databases.class_db import ClassDatabase
        class_db = ClassDatabase.get_instance()
        class_def = next(iter(class_db.classes.values()))
        eng.character.select_class(class_def)
        eng.character.class_selection_open = False

    yield eng

    Config.init_screen_settings = _orig_init


@pytest.fixture()
def play(engine):
    """A PlaytestHarness wrapped around the session engine."""
    from tests.integration.harness import PlaytestHarness
    harness = PlaytestHarness(engine)
    harness.settle()
    yield harness
    harness.settle()
