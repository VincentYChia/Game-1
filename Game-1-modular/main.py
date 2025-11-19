#!/usr/bin/env python3
"""
Game-1 Modular - Main Entry Point

This is the modular refactored version of Game-1, with code organized into
clean modules for maintainability and scalability.

Architecture:
- core/         - Core game systems (engine, config, camera)
- data/         - Data models and database loaders
- entities/     - Game entities (character, components)
- systems/      - Game systems (world, quests, NPCs, titles)
- rendering/    - All rendering code
- Combat/       - Combat system
- Crafting-subdisciplines/ - Crafting minigames
"""

from core.game_engine import GameEngine


def main():
    """Main entry point - create and run the game engine"""
    game = GameEngine()
    game.run()


if __name__ == "__main__":
    main()
