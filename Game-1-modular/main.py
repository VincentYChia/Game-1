"""
Game-1 Modular - Main Entry Point

This is the modular refactored version of Game-1, with code organized into
clean modules for maintainability and scalability.

Architecture:
- core/         - Core game systems (engine, config, camera)
- data/         - Data crafting_classifier_models and database loaders
- entities/     - Game entities (character, components)a
- systems/      - Game systems (world, quests, NPCs, titles)
- rendering/    - All rendering code
- Combat/       - Combat system
- Crafting-subdisciplines/ - Crafting minigames
"""

import sys
import os

# The codebase prints emoji status markers (⚒️ 📜 ✅) throughout gameplay.
# On a default Windows console (cp1252) those prints raise UnicodeEncodeError
# — e.g. every smithing craft crashed via tag_debug's INFO log. Reconfigure
# stdio to UTF-8 with replacement so console encoding can never crash play.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

# Report key PRESENCE only — never echo the secret itself (it would land in
# console logs, screenshares, and crash reports).
print("=" * 50)
print(f"ANTHROPIC_API_KEY: {'set' if os.environ.get('ANTHROPIC_API_KEY') else '(NOT SET)'}")
print("=" * 50)


# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.game_engine import GameEngine


def main():
    """Main entry point - create and run the game engine"""
    try:
        game = GameEngine()
    except Exception:
        # Boot failure in the windowed build is otherwise invisible
        # (console=False) — leave a crash report behind, then re-raise.
        from core.crash_handler import write_crash_report
        write_crash_report(context={"phase": "boot"})
        raise
    game.run()


if __name__ == "__main__":
    main()
