"""
Placement Visualizer - ASCII grid display for placement patterns
"""
import json
from typing import Dict, Tuple


class PlacementVisualizer:
    """Visualizes crafting placement grids in ASCII format."""

    def __init__(self):
        """Initialize visualizer."""
        pass

    def parse_grid_size(self, grid_size_str: str) -> Tuple[int, int]:
        """
        Parse grid size string (e.g., "3x3") into (width, height).

        Args:
            grid_size_str: Grid size string like "3x3", "5x5"

        Returns:
            Tuple of (width, height)
        """
        parts = grid_size_str.lower().replace('x', ' ').split()
        if len(parts) == 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
        return (3, 3)  # Default

    def visualize_placement(self, placement_data: dict, material_lookup: Dict[str, str] = None) -> str:
        """
        Create ASCII visualization of placement pattern.

        Args:
            placement_data: Dict with 'gridSize' and 'placementMap'
            material_lookup: Optional dict mapping materialId to short name

        Returns:
            ASCII string representation of grid
        """
        grid_size = placement_data.get('gridSize', '3x3')
        placement_map = placement_data.get('placementMap', {})

        grid_w, grid_h = self.parse_grid_size(grid_size)

        # Build grid
        output = []
        output.append(f"\nGrid Size: {grid_size}")
        output.append("=" * (grid_w * 10 + 1))

        for row in range(1, grid_h + 1):
            row_cells = []
            for col in range(1, grid_w + 1):
                key = f"{row},{col}"  # Format: "row,col"
                if key in placement_map:
                    material_id = placement_map[key]

                    # Get short name
                    if material_lookup and material_id in material_lookup:
                        short_name = material_lookup[material_id][:8]
                    else:
                        # Abbreviate material ID
                        short_name = material_id[:8]

                    cell_content = f" {short_name:<8}"
                else:
                    cell_content = "    ·    "

                row_cells.append(cell_content)

            output.append("|" + "|".join(row_cells) + "|")

        output.append("=" * (grid_w * 10 + 1))

        # Add legend
        if placement_map:
            output.append("\nLegend:")
            for key, material_id in sorted(placement_map.items()):
                if material_lookup and material_id in material_lookup:
                    full_name = material_lookup[material_id]
                else:
                    full_name = material_id
                output.append(f"  {key}: {material_id} ({full_name})")

        return "\n".join(output)

    def visualize_placement_compact(self, placement_data: dict) -> str:
        """
        Create compact ASCII visualization (just grid structure).

        Args:
            placement_data: Dict with 'gridSize' and 'placementMap'

        Returns:
            Compact ASCII representation
        """
        grid_size = placement_data.get('gridSize', '3x3')
        placement_map = placement_data.get('placementMap', {})

        grid_w, grid_h = self.parse_grid_size(grid_size)

        # Build grid with material IDs abbreviated to first letter
        output = []
        output.append(f"{grid_size} Grid:")

        for row in range(1, grid_h + 1):
            row_chars = []
            for col in range(1, grid_w + 1):
                key = f"{row},{col}"
                if key in placement_map:
                    material_id = placement_map[key]
                    # Use first letter or first 2 chars
                    abbrev = material_id[:2].upper()
                    row_chars.append(f"[{abbrev}]")
                else:
                    row_chars.append(" · ")

            output.append(" ".join(row_chars))

        return "\n".join(output)


def load_material_names(materials_file: str) -> Dict[str, str]:
    """Load material ID to name mapping."""
    with open(materials_file, 'r') as f:
        data = json.load(f)

    materials = {}
    for material in data['materials']:
        materials[material['materialId']] = material['name']

    return materials


def visualize_json_file(json_file: str, materials_file: str = None):
    """
    Visualize a placement JSON file.

    Args:
        json_file: Path to JSON file containing placement data
        materials_file: Optional path to materials database
    """
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Load material names if available
    material_lookup = None
    if materials_file:
        try:
            material_lookup = load_material_names(materials_file)
        except Exception as e:
            print(f"Warning: Could not load materials: {e}")

    visualizer = PlacementVisualizer()

    # Check if data is wrapped in response
    if 'response' in data:
        response = data['response']
        # Try to parse JSON from response
        if response.strip().startswith('{'):
            try:
                placement_data = json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON
                start = response.find('{')
                end = response.rfind('}') + 1
                if start != -1 and end > start:
                    placement_data = json.loads(response[start:end])
                else:
                    print("Error: Could not parse placement data from response")
                    return
        else:
            print("Error: Response does not contain JSON")
            return
    else:
        placement_data = data

    # Visualize
    print("\n" + "="*80)
    print(f"Placement Visualization: {json_file}")
    print("="*80)
    print(visualizer.visualize_placement(placement_data, material_lookup))
    print("\n")


def main():
    """Main function - interactive file selection."""
    import sys
    import glob

    print("\n" + "="*80)
    print("PLACEMENT VISUALIZER - Interactive Mode")
    print("="*80)

    # Path to materials database
    materials_file = "../../../../Game-1-modular/items.JSON/items-materials-1.JSON"

    while True:
        # Find all placement files
        output_dir = "../outputs"
        placement_files = []

        # Look for placement system outputs (1x2, 2x2, 3x2, 4x2, 5x2)
        for pattern in ['system_1x2_*.json', 'system_2x2_*.json', 'system_3x2_*.json',
                       'system_4x2_*.json', 'system_5x2_*.json']:
            files = glob.glob(f"{output_dir}/{pattern}")
            placement_files.extend(files)

        # Also check archive folder
        archive_files = glob.glob(f"{output_dir}/2026-*/**/*x2*.json", recursive=True)
        placement_files.extend(archive_files)

        if not placement_files:
            print("\n❌ No placement files found in outputs/")
            print("\nPlacement files should match patterns:")
            print("  - system_1x2_*.json (Smithing)")
            print("  - system_2x2_*.json (Refining)")
            print("  - system_3x2_*.json (Alchemy)")
            print("  - system_4x2_*.json (Engineering)")
            print("  - system_5x2_*.json (Enchanting)")
            print("\nGenerate some placement outputs first by running systems 1x2, 2x2, etc.")
            return

        # Sort and display available files
        placement_files.sort()

        print(f"\n✅ Found {len(placement_files)} placement file(s):")
        for i, filepath in enumerate(placement_files, 1):
            # Get filename only for display
            filename = filepath.split('/')[-1]
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
            print("\n" + "="*80)
            print("VISUALIZING ALL PLACEMENT FILES")
            print("="*80)
            for filepath in placement_files:
                visualize_json_file(filepath, materials_file)
                print("\n" + "-"*80 + "\n")
        else:
            try:
                file_index = int(choice) - 1
                if 0 <= file_index < len(placement_files):
                    visualize_json_file(placement_files[file_index], materials_file)
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
