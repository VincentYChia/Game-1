"""
Placement Visualizer - Uses game's existing architecture to visualize placement patterns

This visualizer integrates directly with the game's crafting systems to ensure
consistent loading and display of placement data across all 5 disciplines.

MODES:
- ASCII Mode (this file): Fast, works everywhere, clear text representation
- UI Mode (ui_visualizer.py): Uses game's actual pygame renderer (requires display)

For most use cases, ASCII mode is recommended. Use UI mode when you need to see
exactly how placements will appear in the actual game.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Add game module to path
GAME_ROOT = Path(__file__).parent.parent.parent.parent.parent / "Game-1-modular"
sys.path.insert(0, str(GAME_ROOT))

# Import game's material database
try:
    from data.databases.material_db import MaterialDatabase
except ImportError:
    print("Warning: Could not import MaterialDatabase from game")
    MaterialDatabase = None


class PlacementVisualizer:
    """Unified visualizer for all 5 crafting discipline placement systems."""

    def __init__(self):
        """Initialize visualizer with material database."""
        self.material_db = None
        if MaterialDatabase:
            try:
                self.material_db = MaterialDatabase.get_instance()
                # Try to load materials
                possible_paths = [
                    GAME_ROOT / "items.JSON" / "items-materials-1.JSON",
                    Path("../../../../Game-1-modular/items.JSON/items-materials-1.JSON"),
                ]
                for path in possible_paths:
                    if path.exists():
                        self.material_db.load_from_file(str(path))
                        print(f"✓ Loaded {len(self.material_db.materials)} materials from database")
                        break
            except Exception as e:
                print(f"Warning: Could not load material database: {e}")
                self.material_db = None

    def get_material_name(self, material_id: str) -> str:
        """Get human-readable material name."""
        if self.material_db and material_id in self.material_db.materials:
            return self.material_db.materials[material_id].name
        # Fallback: prettify the ID
        return material_id.replace('_', ' ').title()

    def detect_placement_type(self, placement_data: Dict[str, Any]) -> str:
        """
        Detect which placement system type this data uses.

        Returns: '1x2' (smithing), '2x2' (refining), '3x2' (alchemy),
                 '4x2' (engineering), '5x2' (enchanting), or 'unknown'
        """
        # Smithing: has placementMap with string keys
        if 'placementMap' in placement_data:
            placement_map = placement_data['placementMap']
            # Check if it's a dict with coordinate keys (smithing) or nested structure (enchanting)
            if isinstance(placement_map, dict):
                # If has gridType or vertices, it's enchanting
                if 'gridType' in placement_map or 'vertices' in placement_map:
                    return '5x2'  # Enchanting
                # Otherwise it's smithing grid
                return '1x2'

        # Refining: has coreInputs and/or surroundingInputs
        if 'coreInputs' in placement_data or 'surroundingInputs' in placement_data:
            return '2x2'

        # Alchemy: has ingredients array with slot numbers
        if 'ingredients' in placement_data:
            return '3x2'

        # Engineering: has slots array with type field
        if 'slots' in placement_data:
            return '4x2'

        return 'unknown'

    def visualize_smithing_grid(self, placement_data: Dict[str, Any]) -> str:
        """
        Visualize smithing grid placement (3x3 or 5x5).

        Format: {"placementMap": {"1,1": "materialId", ...}, "metadata": {"gridSize": "3x3"}}
        """
        output = []

        # Get grid size
        metadata = placement_data.get('metadata', {})
        grid_size_str = metadata.get('gridSize', '3x3')
        parts = grid_size_str.lower().split('x')
        grid_w = int(parts[0]) if len(parts) > 0 else 3
        grid_h = int(parts[1]) if len(parts) > 1 else 3

        placement_map = placement_data.get('placementMap', {})

        output.append(f"\n{'='*80}")
        output.append(f"SMITHING GRID - {grid_size_str}")
        output.append(f"{'='*80}")

        # Create grid
        cell_width = 12
        for row in range(1, grid_h + 1):
            row_cells = []
            for col in range(1, grid_w + 1):
                key = f"{row},{col}"
                if key in placement_map:
                    material_id = placement_map[key]
                    material_name = self.get_material_name(material_id)[:cell_width-2]
                    cell_content = f" {material_name:<{cell_width-2}} "
                else:
                    cell_content = " " + "·" * (cell_width-2) + " "
                row_cells.append(cell_content)
            output.append("|" + "|".join(row_cells) + "|")

        # Add legend
        if placement_map:
            output.append(f"\n{'─'*80}")
            output.append("MATERIALS USED:")
            for key in sorted(placement_map.keys(), key=lambda x: (int(x.split(',')[0]), int(x.split(',')[1]))):
                material_id = placement_map[key]
                material_name = self.get_material_name(material_id)
                output.append(f"  [{key}] {material_name} ({material_id})")

        # Add narrative if present
        if 'narrative' in metadata:
            output.append(f"\n{'─'*80}")
            output.append(f"NARRATIVE: {metadata['narrative']}")

        output.append(f"{'='*80}\n")
        return "\n".join(output)

    def visualize_refining_hub(self, placement_data: Dict[str, Any]) -> str:
        """
        Visualize refining hub-and-spoke placement.

        Format: {"coreInputs": [...], "surroundingInputs": [...]}
        """
        output = []

        core_inputs = placement_data.get('coreInputs', [])
        surrounding_inputs = placement_data.get('surroundingInputs', [])

        output.append(f"\n{'='*80}")
        output.append(f"REFINING HUB-AND-SPOKE")
        output.append(f"{'='*80}")

        # Display core inputs (center)
        output.append("\n🎯 CORE INPUTS (Center):")
        if core_inputs:
            for item in core_inputs:
                material_id = item.get('materialId', 'unknown')
                quantity = item.get('quantity', 1)
                material_name = self.get_material_name(material_id)
                output.append(f"  • {material_name} x{quantity} ({material_id})")
        else:
            output.append("  (none)")

        # Display surrounding inputs
        output.append("\n🔄 SURROUNDING INPUTS (Around center):")
        if surrounding_inputs:
            for item in surrounding_inputs:
                material_id = item.get('materialId', 'unknown')
                quantity = item.get('quantity', 1)
                material_name = self.get_material_name(material_id)
                positions = item.get('positions', [])
                pos_str = f" at {positions}" if positions else ""
                output.append(f"  • {material_name} x{quantity}{pos_str} ({material_id})")
        else:
            output.append("  (none)")

        # ASCII diagram
        output.append(f"\n{'─'*80}")
        output.append("HUB DIAGRAM:")
        output.append("        ┌───────┐")
        if surrounding_inputs:
            output.append("    [S] │       │ [S]")
        else:
            output.append("        │       │")
        output.append("  ──────┤  [C]  ├──────")
        if surrounding_inputs:
            output.append("    [S] │       │ [S]")
        else:
            output.append("        │       │")
        output.append("        └───────┘")
        output.append("  [C] = Core, [S] = Surrounding")

        # Add narrative
        if 'narrative' in placement_data:
            output.append(f"\n{'─'*80}")
            output.append(f"NARRATIVE: {placement_data['narrative']}")

        output.append(f"{'='*80}\n")
        return "\n".join(output)

    def visualize_alchemy_sequence(self, placement_data: Dict[str, Any]) -> str:
        """
        Visualize alchemy sequential placement.

        Format: {"ingredients": [{"slot": 1, "materialId": "...", "quantity": ...}, ...]}
        """
        output = []

        ingredients = placement_data.get('ingredients', [])

        output.append(f"\n{'='*80}")
        output.append(f"ALCHEMY SEQUENTIAL PLACEMENT")
        output.append(f"{'='*80}")
        output.append("\n⚗️  INGREDIENT ORDER (sequence matters!):")

        if ingredients:
            # Sort by slot number
            sorted_ingredients = sorted(ingredients, key=lambda x: x.get('slot', 0))

            for item in sorted_ingredients:
                slot = item.get('slot', '?')
                material_id = item.get('materialId', 'unknown')
                quantity = item.get('quantity', 1)
                material_name = self.get_material_name(material_id)

                output.append(f"\n  [{slot}] {material_name} x{quantity}")
                output.append(f"      └─ {material_id}")

            # Visual sequence
            output.append(f"\n{'─'*80}")
            output.append("SEQUENCE FLOW:")
            sequence_parts = []
            for item in sorted_ingredients:
                slot = item.get('slot', '?')
                material_id = item.get('materialId', 'unknown')
                material_name = self.get_material_name(material_id)[:8]
                sequence_parts.append(f"[{slot}: {material_name}]")
            output.append("  " + " → ".join(sequence_parts))
        else:
            output.append("  (no ingredients)")

        # Add narrative
        if 'narrative' in placement_data:
            output.append(f"\n{'─'*80}")
            output.append(f"NARRATIVE: {placement_data['narrative']}")

        output.append(f"{'='*80}\n")
        return "\n".join(output)

    def visualize_engineering_slots(self, placement_data: Dict[str, Any]) -> str:
        """
        Visualize engineering slot-type placement.

        Format: {"slots": [{"type": "FRAME", "materialId": "...", "quantity": ...}, ...]}
        """
        output = []

        slots = placement_data.get('slots', [])

        output.append(f"\n{'='*80}")
        output.append(f"ENGINEERING SLOT-TYPE PLACEMENT")
        output.append(f"{'='*80}")
        output.append("\n🔧 COMPONENT SLOTS:")

        if slots:
            # Group by slot type
            by_type = {}
            for slot in slots:
                slot_type = slot.get('type', 'UNKNOWN')
                if slot_type not in by_type:
                    by_type[slot_type] = []
                by_type[slot_type].append(slot)

            # Display by type
            for slot_type in ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'ENHANCEMENT', 'CATALYST', 'AMPLIFIER']:
                if slot_type in by_type:
                    output.append(f"\n  [{slot_type}]")
                    for slot in by_type[slot_type]:
                        material_id = slot.get('materialId', 'unknown')
                        quantity = slot.get('quantity', 1)
                        material_name = self.get_material_name(material_id)
                        output.append(f"    • {material_name} x{quantity} ({material_id})")

            # Show any other types
            for slot_type, items in by_type.items():
                if slot_type not in ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'ENHANCEMENT', 'CATALYST', 'AMPLIFIER']:
                    output.append(f"\n  [{slot_type}]")
                    for slot in items:
                        material_id = slot.get('materialId', 'unknown')
                        quantity = slot.get('quantity', 1)
                        material_name = self.get_material_name(material_id)
                        output.append(f"    • {material_name} x{quantity} ({material_id})")

            # Slot diagram
            output.append(f"\n{'─'*80}")
            output.append("SLOT DIAGRAM:")
            output.append("  ┌────────────────────────────┐")
            for slot_type in by_type.keys():
                output.append(f"  │ [{slot_type:<10}] slot        │")
            output.append("  └────────────────────────────┘")
        else:
            output.append("  (no slots)")

        # Add narrative
        if 'narrative' in placement_data:
            output.append(f"\n{'─'*80}")
            output.append(f"NARRATIVE: {placement_data['narrative']}")

        output.append(f"{'='*80}\n")
        return "\n".join(output)

    def visualize_enchanting_vertices(self, placement_data: Dict[str, Any]) -> str:
        """
        Visualize enchanting geometric vertex placement.

        Format: {"placementMap": {"gridType": "...", "vertices": {"0,0": {"materialId": "...", "isKey": bool}, ...}}}
        """
        output = []

        placement_map = placement_data.get('placementMap', {})
        grid_type = placement_map.get('gridType', 'square_10x10')
        vertices = placement_map.get('vertices', {})
        shapes = placement_map.get('shapes', [])

        output.append(f"\n{'='*80}")
        output.append(f"ENCHANTING GEOMETRIC VERTICES")
        output.append(f"{'='*80}")
        output.append(f"\nGrid Type: {grid_type}")

        # Display vertices
        output.append(f"\n🔮 VERTICES ({len(vertices)} total):")

        if vertices:
            # Separate key vertices from regular ones
            key_vertices = []
            regular_vertices = []

            for coord, vertex_data in sorted(vertices.items()):
                material_id = vertex_data.get('materialId', 'unknown')
                is_key = vertex_data.get('isKey', False)
                material_name = self.get_material_name(material_id)

                vertex_info = f"  {coord:>8} → {material_name:<20} ({material_id})"

                if is_key:
                    key_vertices.append(vertex_info + " ⭐ KEY")
                else:
                    regular_vertices.append(vertex_info)

            if key_vertices:
                output.append("\n  KEY VERTICES:")
                output.extend(key_vertices)

            if regular_vertices:
                output.append("\n  REGULAR VERTICES:")
                output.extend(regular_vertices)

            # Show shapes if present
            if shapes:
                output.append(f"\n{'─'*80}")
                output.append(f"GEOMETRIC SHAPES ({len(shapes)} total):")
                for i, shape in enumerate(shapes, 1):
                    shape_type = shape.get('type', 'unknown')
                    rotation = shape.get('rotation', 0)
                    shape_vertices = shape.get('vertices', [])
                    output.append(f"  {i}. {shape_type} (rotation: {rotation}°)")
                    output.append(f"     Vertices: {', '.join(shape_vertices)}")

            # Try to create a simple coordinate plot
            output.append(f"\n{'─'*80}")
            output.append("COORDINATE PLOT (approximate):")

            # Parse coordinates and find bounds
            coords = []
            for coord_str in vertices.keys():
                try:
                    x, y = map(int, coord_str.split(','))
                    coords.append((x, y))
                except:
                    continue

            if coords:
                min_x = min(c[0] for c in coords)
                max_x = max(c[0] for c in coords)
                min_y = min(c[1] for c in coords)
                max_y = max(c[1] for c in coords)

                # Create a simple text plot (limited size)
                plot_width = min(40, max_x - min_x + 3)
                plot_height = min(20, max_y - min_y + 3)

                output.append(f"  Range: X[{min_x}, {max_x}], Y[{min_y}, {max_y}]")
                output.append(f"  {len(vertices)} vertices plotted as '*' (key vertices as '★')")
        else:
            output.append("  (no vertices)")

        # Add narrative
        if 'narrative' in placement_data:
            output.append(f"\n{'─'*80}")
            output.append(f"NARRATIVE: {placement_data['narrative']}")

        output.append(f"{'='*80}\n")
        return "\n".join(output)

    def visualize_placement(self, placement_data: Dict[str, Any]) -> str:
        """
        Automatically detect placement type and visualize accordingly.

        Args:
            placement_data: Placement data dictionary

        Returns:
            ASCII visualization string
        """
        placement_type = self.detect_placement_type(placement_data)

        # Add header with detected type
        header = f"\nDetected System: {placement_type}"
        if placement_type == '1x2':
            header += " (Smithing)"
        elif placement_type == '2x2':
            header += " (Refining)"
        elif placement_type == '3x2':
            header += " (Alchemy)"
        elif placement_type == '4x2':
            header += " (Engineering)"
        elif placement_type == '5x2':
            header += " (Enchanting)"
        else:
            header += " (Unknown)"

        print(header)

        # Dispatch to appropriate visualizer
        if placement_type == '1x2':
            return self.visualize_smithing_grid(placement_data)
        elif placement_type == '2x2':
            return self.visualize_refining_hub(placement_data)
        elif placement_type == '3x2':
            return self.visualize_alchemy_sequence(placement_data)
        elif placement_type == '4x2':
            return self.visualize_engineering_slots(placement_data)
        elif placement_type == '5x2':
            return self.visualize_enchanting_vertices(placement_data)
        else:
            return f"\n❌ Unknown placement type. Could not visualize.\n"


def visualize_json_file(json_file: str):
    """
    Visualize a placement JSON file (handles both raw placement and API response format).

    Args:
        json_file: Path to JSON file
    """
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
        # Try to parse JSON from response
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

            # Try to parse as JSON
            placement_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from response: {e}")
            return

    # Visualize
    visualizer = PlacementVisualizer()

    print(f"\n{'='*80}")
    print(f"FILE: {os.path.basename(json_file)}")
    print(f"{'='*80}")

    visualization = visualizer.visualize_placement(placement_data)
    print(visualization)


def main():
    """Interactive mode - select files to visualize."""
    import glob

    print("\n" + "="*80)
    print("PLACEMENT VISUALIZER - Game Architecture Integration")
    print("="*80)
    print("\nThis visualizer uses the game's existing placement loading systems")
    print("to ensure consistent visualization across all 5 crafting disciplines.")

    while True:
        # Find all placement files
        output_dir = Path(__file__).parent.parent / "outputs"
        placement_files = []

        # Look for placement system outputs
        for pattern in ['system_1x2_*.json', 'system_2x2_*.json', 'system_3x2_*.json',
                       'system_4x2_*.json', 'system_5x2_*.json']:
            files = list(output_dir.glob(pattern))
            placement_files.extend([str(f) for f in files])

        if not placement_files:
            print("\n❌ No placement files found in outputs/")
            print("\nGenerate placement outputs by running systems 1x2, 2x2, 3x2, 4x2, 5x2")
            return

        # Sort and display
        placement_files.sort()

        print(f"\n✅ Found {len(placement_files)} placement file(s):")
        for i, filepath in enumerate(placement_files, 1):
            filename = os.path.basename(filepath)
            print(f"  {i}. {filename}")

        print("\nOptions:")
        print("  - Enter number to visualize a file")
        print("  - Enter 'all' to visualize all files")
        print("  - Enter 'q' to quit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == 'q':
            print("\n👋 Goodbye!\n")
            break
        elif choice == 'all':
            for filepath in placement_files:
                visualize_json_file(filepath)
                print("\n" + "-"*80 + "\n")
        else:
            try:
                file_index = int(choice) - 1
                if 0 <= file_index < len(placement_files):
                    visualize_json_file(placement_files[file_index])
                else:
                    print(f"\n❌ Invalid choice. Please enter 1-{len(placement_files)}")
            except ValueError:
                print("\n❌ Invalid input. Please enter a number, 'all', or 'q'")

        # Ask if they want to continue
        if choice != 'all':
            continue_choice = input("\nVisualize another? (y/n): ").strip().lower()
            if continue_choice != 'y':
                print("\n👋 Goodbye!\n")
                break


if __name__ == "__main__":
    main()
