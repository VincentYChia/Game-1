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
    """Main function for testing."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python placement_visualizer.py <placement_json_file> [materials_file]")
        print("\nExample:")
        print("  python placement_visualizer.py ../outputs/system_1x2_*.json")
        print("  python placement_visualizer.py ../outputs/system_1x2_*.json ../../../../Game-1-modular/items.JSON/items-materials-1.JSON")
        return

    json_file = sys.argv[1]
    materials_file = sys.argv[2] if len(sys.argv) > 2 else None

    visualize_json_file(json_file, materials_file)


if __name__ == "__main__":
    main()
