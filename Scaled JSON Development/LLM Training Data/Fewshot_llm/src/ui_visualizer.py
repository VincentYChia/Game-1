"""
UI Visualizer - Uses game's actual pygame rendering to display placements

This visualizer integrates with the game's Renderer class to show
placements exactly as they appear in-game using pygame.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add game module to path
GAME_ROOT = Path(__file__).parent.parent.parent.parent.parent / "Game-1-modular"
sys.path.insert(0, str(GAME_ROOT))

# Try to import pygame and game components
try:
    import pygame
    from rendering.renderer import Renderer
    from data.databases.material_db import MaterialDatabase
    from data.models.recipes import Recipe, PlacementData
    PYGAME_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Warning: Could not import pygame or game components: {e}")
    print("  UI visualization not available. Use visualize_placement.py for ASCII mode.")
    PYGAME_AVAILABLE = False


class GameUIVisualizer:
    """Visualizes placements using the game's actual pygame UI."""

    def __init__(self):
        """Initialize pygame and game renderer."""
        if not PYGAME_AVAILABLE:
            raise RuntimeError("Pygame not available. Cannot initialize UI visualizer.")

        pygame.init()

        # Create display window
        self.width = 1000
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Placement Visualizer - Game UI")

        # Initialize clock for frame rate
        self.clock = pygame.Clock()

        # Initialize game renderer
        self.renderer = Renderer(self.screen)

        # Load material database
        self.material_db = None
        try:
            self.material_db = MaterialDatabase.get_instance()
            materials_path = GAME_ROOT / "items.JSON" / "items-materials-1.JSON"
            if materials_path.exists():
                self.material_db.load_from_file(str(materials_path))
                print(f"✓ Loaded {len(self.material_db.materials)} materials")
        except Exception as e:
            print(f"⚠️  Warning: Could not load materials: {e}")

        # Colors
        self.bg_color = (20, 20, 25)
        self.text_color = (220, 220, 220)

        # Font
        self.font = pygame.font.Font(None, 24)
        self.title_font = pygame.font.Font(None, 36)

    def create_mock_recipe(self, placement_data: Dict[str, Any], system_type: str) -> Tuple[Recipe, Dict[str, str]]:
        """
        Create a mock Recipe object and user_placement dict from placement JSON.

        Returns: (Recipe, user_placement_dict)
        """
        recipe_id = placement_data.get('recipeId', 'mock_recipe')

        # Determine station tier
        tier = placement_data.get('stationTier', 1)

        # Create mock Recipe object
        # Note: We only need the fields required for rendering
        recipe = Recipe(
            recipe_id=recipe_id,
            output_id=placement_data.get('outputId', placement_data.get('itemId', 'unknown')),
            output_qty=1,
            station_type=self._get_station_type(system_type),
            station_tier=tier,
            inputs=[],  # Not needed for visualization
            metadata={}
        )

        # Create user_placement dict from placement_data
        user_placement = {}

        if system_type == '1x2':  # Smithing
            placement_map = placement_data.get('placementMap', {})
            for key, material_id in placement_map.items():
                user_placement[key] = material_id

        elif system_type == '2x2':  # Refining
            # For refining, we need to convert core/surrounding to placement dict
            # The renderer expects user_placement format, but refining uses different structure
            # We'll mark core and surrounding positions
            core_inputs = placement_data.get('coreInputs', [])
            for i, core_input in enumerate(core_inputs):
                user_placement[f"core_{i}"] = core_input.get('materialId', '')

            surrounding_inputs = placement_data.get('surroundingInputs', [])
            for i, surr_input in enumerate(surrounding_inputs):
                user_placement[f"surr_{i}"] = surr_input.get('materialId', '')

        elif system_type == '3x2':  # Alchemy
            # Convert ingredients to slot positions
            ingredients = placement_data.get('ingredients', [])
            for ingredient in ingredients:
                slot = ingredient.get('slot', 0)
                material_id = ingredient.get('materialId', '')
                user_placement[f"slot_{slot}"] = material_id

        elif system_type == '4x2':  # Engineering
            # Convert slot types to user_placement
            slots = placement_data.get('slots', [])
            for i, slot in enumerate(slots):
                slot_type = slot.get('type', 'UNKNOWN')
                material_id = slot.get('materialId', '')
                user_placement[f"{slot_type}_{i}"] = material_id

        elif system_type == '5x2':  # Enchanting
            # Convert vertices to placement
            placement_map_data = placement_data.get('placementMap', {})
            if 'vertices' in placement_map_data:
                vertices = placement_map_data['vertices']
                for coord, vertex_data in vertices.items():
                    material_id = vertex_data.get('materialId', '')
                    user_placement[coord] = material_id
            elif isinstance(placement_map_data, dict):
                # Sometimes placementMap directly contains coordinate keys
                for key, material_id in placement_map_data.items():
                    if key not in ['gridType', 'vertices', 'shapes']:
                        user_placement[key] = material_id

        return recipe, user_placement

    def _get_station_type(self, system_type: str) -> str:
        """Map system type to station type."""
        mapping = {
            '1x2': 'smithing',
            '2x2': 'refining',
            '3x2': 'alchemy',
            '4x2': 'engineering',
            '5x2': 'adornments'
        }
        return mapping.get(system_type, 'smithing')

    def detect_system_type(self, placement_data: Dict[str, Any]) -> str:
        """Detect which placement system this data uses."""
        # Same logic as visualize_placement.py
        if 'placementMap' in placement_data:
            placement_map = placement_data.get('placementMap', {})
            if isinstance(placement_map, dict):
                if 'gridType' in placement_map or 'vertices' in placement_map:
                    return '5x2'  # Enchanting
                return '1x2'  # Smithing

        if 'coreInputs' in placement_data or 'surroundingInputs' in placement_data:
            return '2x2'  # Refining

        if 'ingredients' in placement_data:
            return '3x2'  # Alchemy

        if 'slots' in placement_data:
            return '4x2'  # Engineering

        return 'unknown'

    def visualize_placement(self, placement_data: Dict[str, Any], system_type: str = None):
        """
        Visualize placement using game's renderer.

        Args:
            placement_data: Placement JSON data
            system_type: '1x2', '2x2', '3x2', '4x2', or '5x2' (auto-detected if None)
        """
        if system_type is None:
            system_type = self.detect_system_type(placement_data)

        if system_type == 'unknown':
            print("❌ Could not detect placement system type")
            return

        # Create mock recipe and user placement
        recipe, user_placement = self.create_mock_recipe(placement_data, system_type)

        # Calculate placement rect (centered in window)
        placement_width = 800
        placement_height = 600
        placement_x = (self.width - placement_width) // 2
        placement_y = 100
        placement_rect = pygame.Rect(placement_x, placement_y, placement_width, placement_height)

        # Main loop
        running = True
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        running = False

            # Clear screen
            self.screen.fill(self.bg_color)

            # Draw title
            title_text = f"System {system_type} - {self._get_station_type(system_type).title()} Placement"
            title_surf = self.title_font.render(title_text, True, self.text_color)
            title_rect = title_surf.get_rect(centerx=self.width // 2, top=20)
            self.screen.blit(title_surf, title_rect)

            # Draw instructions
            inst_text = "Press ESC or Q to close"
            inst_surf = self.font.render(inst_text, True, (150, 150, 150))
            inst_rect = inst_surf.get_rect(centerx=self.width // 2, top=60)
            self.screen.blit(inst_surf, inst_rect)

            # Get mouse position
            mouse_pos = pygame.mouse.get_pos()

            # Render placement using game's renderer
            try:
                station_type = self._get_station_type(system_type)
                station_tier = recipe.station_tier

                if system_type == '1x2':
                    self.renderer.render_smithing_grid(
                        self.screen, placement_rect, station_tier,
                        recipe, user_placement, mouse_pos
                    )
                elif system_type == '2x2':
                    self.renderer.render_refining_hub(
                        self.screen, placement_rect, station_tier,
                        recipe, user_placement, mouse_pos
                    )
                elif system_type == '3x2':
                    self.renderer.render_alchemy_sequence(
                        self.screen, placement_rect, station_tier,
                        recipe, user_placement, mouse_pos
                    )
                elif system_type == '4x2':
                    self.renderer.render_engineering_slots(
                        self.screen, placement_rect, station_tier,
                        recipe, user_placement, mouse_pos
                    )
                elif system_type == '5x2':
                    self.renderer.render_adornment_pattern(
                        self.screen, placement_rect, station_tier,
                        recipe, user_placement, mouse_pos
                    )
            except Exception as e:
                # Show error on screen
                error_text = f"Rendering error: {str(e)}"
                error_surf = self.font.render(error_text, True, (255, 100, 100))
                error_rect = error_surf.get_rect(center=(self.width // 2, self.height // 2))
                self.screen.blit(error_surf, error_rect)

            # Update display
            pygame.display.flip()
            self.clock.tick(30)  # 30 FPS

        pygame.quit()


def visualize_json_file(json_file: str):
    """Visualize a placement JSON file with game's UI."""
    if not PYGAME_AVAILABLE:
        print("❌ Pygame not available. Cannot visualize with UI.")
        print("   Use visualize_placement.py for ASCII visualization.")
        return

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return

    # Check if wrapped in API response format
    placement_data = data
    if 'response' in data:
        response_text = data['response']
        try:
            # Remove markdown code blocks if present
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()

            placement_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from response: {e}")
            return

    # Create visualizer and display
    try:
        visualizer = GameUIVisualizer()
        print(f"\n{'='*80}")
        print(f"Visualizing: {os.path.basename(json_file)}")
        print(f"{'='*80}")
        print("\nRendering with game's UI...")
        print("Close window or press ESC/Q to exit")

        visualizer.visualize_placement(placement_data)
    except Exception as e:
        print(f"❌ Error during visualization: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Interactive mode - select files to visualize with game UI."""
    if not PYGAME_AVAILABLE:
        print("\n" + "="*80)
        print("❌ PYGAME NOT AVAILABLE")
        print("="*80)
        print("\nCannot run UI visualizer without pygame and game components.")
        print("Use visualize_placement.py for ASCII visualization instead.")
        return

    import glob

    print("\n" + "="*80)
    print("PLACEMENT UI VISUALIZER - Game Rendering")
    print("="*80)
    print("\nThis visualizer uses the game's actual pygame renderer")
    print("to show placements exactly as they appear in-game.")

    # Find placement files
    output_dir = Path(__file__).parent.parent / "outputs"
    placement_files = []

    for pattern in ['system_1x2_*.json', 'system_2x2_*.json', 'system_3x2_*.json',
                   'system_4x2_*.json', 'system_5x2_*.json']:
        files = list(output_dir.glob(pattern))
        placement_files.extend([str(f) for f in files])

    if not placement_files:
        print("\n❌ No placement files found in outputs/")
        return

    # Sort and display
    placement_files.sort()

    while True:
        print(f"\n✅ Found {len(placement_files)} placement file(s):")
        for i, filepath in enumerate(placement_files, 1):
            filename = os.path.basename(filepath)
            print(f"  {i}. {filename}")

        print("\nOptions:")
        print("  - Enter number to visualize a file")
        print("  - Enter 'q' to quit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == 'q':
            print("\n👋 Goodbye!\n")
            break

        try:
            file_index = int(choice) - 1
            if 0 <= file_index < len(placement_files):
                visualize_json_file(placement_files[file_index])
            else:
                print(f"\n❌ Invalid choice. Please enter 1-{len(placement_files)}")
        except ValueError:
            print("\n❌ Invalid input. Please enter a number or 'q'")


if __name__ == "__main__":
    main()
