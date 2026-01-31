"""
Game-1 Modular - Main Entry Point

This is the modular refactored version of Game-1, with code organized into
clean modules for maintainability and scalability.

Architecture:
- core/         - Core game systems (engine, config, camera)
- data/         - Data models and database loaders
- entities/     - Game entities (character, components)a
- systems/      - Game systems (world, quests, NPCs, titles)
- rendering/    - All rendering code
- Combat/       - Combat system
- Crafting-subdisciplines/ - Crafting minigames
"""

import sys
import os

print("=" * 50)
print("DEBUG: Checking environment variable")
print(f"ANTHROPIC_API_KEY: {os.environ.get('ANTHROPIC_API_KEY', '(NOT SET)')}")
print("=" * 50)


# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.game_engine import GameEngine


def main():
    """Main entry point - create and run the game engine"""
    game = GameEngine()
    game.run()


if __name__ == "__main__":
    main()
