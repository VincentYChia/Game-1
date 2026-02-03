"""
CNN Smithing Dataset Visualizer

Updated for v2 data format with:
- Category-based shapes (metal=square, wood=lines, stone=X, etc.)
- Tier-based fill size (T1=1x1 through T4=4x4)
- Saturation/value variation (hue constant = category)

This visualizer can view both v1 (flat cells) and v2 (shaped cells) datasets.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from colorsys import hsv_to_rgb
import random


class SmithingDatasetVisualizer:
    """Visualize smithing augmented training data with tabs for original/valid/invalid"""

    # Category shape masks (same as valid_smithing_data_v2.py)
    CATEGORY_SHAPES = {
        'metal': np.array([
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1]
        ], dtype=np.float32),

        'wood': np.array([
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [0, 0, 0, 0]
        ], dtype=np.float32),

        'stone': np.array([
            [1, 0, 0, 1],
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [1, 0, 0, 1]
        ], dtype=np.float32),

        'monster_drop': np.array([
            [0, 1, 1, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [0, 1, 1, 0]
        ], dtype=np.float32),

        'elemental': np.array([
            [0, 1, 1, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [0, 1, 1, 0]
        ], dtype=np.float32),
    }

    DEFAULT_SHAPE = np.ones((4, 4), dtype=np.float32)

    TIER_FILL_SIZES = {1: 1, 2: 2, 3: 3, 4: 4}

    def __init__(self, dataset_path, materials_path, placements_path, use_shapes=True):
        """
        Args:
            dataset_path: Path to recipe_dataset.npz or recipe_dataset_v2.npz
            materials_path: Path to materials JSON
            placements_path: Path to placements JSON
            use_shapes: Whether to render with category shapes (True for v2 compatibility)
        """
        self.use_shapes = use_shapes

        print("Loading dataset...")
        data = np.load(dataset_path)

        # Load augmented data
        self.X_train = data['X_train']
        self.y_train = data['y_train']
        self.X_val = data['X_val']
        self.y_val = data['y_val']

        # Combine for visualization
        self.X_all = np.concatenate([self.X_train, self.X_val])
        self.y_all = np.concatenate([self.y_train, self.y_val])

        # Separate valid and invalid
        self.valid_indices = np.where(self.y_all == 1)[0]
        self.invalid_indices = np.where(self.y_all == 0)[0]

        # Load original recipes
        with open(materials_path, 'r') as f:
            materials_data = json.load(f)
        self.materials_dict = {
            mat['materialId']: mat
            for mat in materials_data['materials']
        }

        with open(placements_path, 'r') as f:
            placements_data = json.load(f)

        # Filter out stations (ending with _t1, _t2, _t3, _t4)
        self.original_recipes = [
            p for p in placements_data['placements']
            if not any(p['recipeId'].endswith(f'_t{i}') for i in range(1, 5))
        ]

        # Render original recipes
        print("Rendering original recipes...")
        self.original_images = []
        for recipe in self.original_recipes:
            img = self._render_recipe(recipe)
            self.original_images.append(img)

        print(f"✓ Dataset loaded")
        print(f"  Original recipes: {len(self.original_recipes)}")
        print(f"  Augmented samples: {len(self.X_all)}")
        print(f"    Valid: {len(self.valid_indices)} ({len(self.valid_indices) / len(self.X_all) * 100:.1f}%)")
        print(f"    Invalid: {len(self.invalid_indices)} ({len(self.invalid_indices) / len(self.X_all) * 100:.1f}%)")
        print(f"  Image shape: {self.X_all.shape[1:]}")
        print(f"  Using shapes: {self.use_shapes}\n")

    def _material_to_color(self, material_id):
        """Convert material to RGB color (0-1 range) based on category, tier, tags"""
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        if material_id not in self.materials_dict:
            return np.array([0.3, 0.3, 0.3])

        material = self.materials_dict[material_id]
        category = material.get('category', 'unknown')
        tier = material.get('tier', 1)
        tags = material.get('metadata', {}).get('tags', [])

        # CATEGORY → HUE (constant, encodes category)
        if category == 'elemental':
            element_hues = {
                'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
                'lightning': 270, 'ice': 180, 'light': 45, 'dark': 280,
                'void': 290, 'chaos': 330,
            }
            hue = 280  # Default purple for elementals
            for tag in tags:
                if tag in element_hues:
                    hue = element_hues[tag]
                    break
        else:
            category_hues = {
                'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300,
                'gem': 280, 'herb': 120, 'fabric': 45,
            }
            hue = category_hues.get(category, 0)

        # TIER → VALUE/BRIGHTNESS
        tier_values = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}
        value = tier_values.get(tier, 0.5)

        # TAGS → SATURATION
        base_saturation = 0.6
        if category == 'stone':
            base_saturation = 0.2
        if 'legendary' in tags or 'mythical' in tags:
            base_saturation = min(1.0, base_saturation + 0.2)
        elif 'magical' in tags or 'ancient' in tags:
            base_saturation = min(1.0, base_saturation + 0.1)

        saturation = base_saturation

        # Convert HSV to RGB
        hue_normalized = hue / 360.0
        rgb = hsv_to_rgb(hue_normalized, saturation, value)

        return np.array(rgb)

    def _get_shape_mask(self, material_id):
        """Get the 4x4 shape mask for a material's category."""
        if material_id is None or material_id not in self.materials_dict:
            return self.DEFAULT_SHAPE

        category = self.materials_dict[material_id].get('category', 'unknown')
        return self.CATEGORY_SHAPES.get(category, self.DEFAULT_SHAPE)

    def _get_tier_fill_mask(self, material_id, cell_size=4):
        """Get a mask that limits fill based on tier."""
        if material_id is None or material_id not in self.materials_dict:
            return np.zeros((cell_size, cell_size), dtype=np.float32)

        tier = self.materials_dict[material_id].get('tier', 1)
        fill_size = self.TIER_FILL_SIZES.get(tier, 4)

        mask = np.zeros((cell_size, cell_size), dtype=np.float32)
        offset = (cell_size - fill_size) // 2
        mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0

        return mask

    def _placement_to_grid(self, placement):
        """Convert placement to centered 9x9 grid"""
        grid = [[None] * 9 for _ in range(9)]

        # Find actual bounding box of placements to handle off-center recipes
        positions = []
        for pos_str in placement['placementMap'].keys():
            y_idx, x_idx = map(int, pos_str.split(','))
            positions.append((y_idx, x_idx))

        if not positions:
            return grid

        # Calculate actual placement dimensions
        min_y = min(p[0] for p in positions)
        max_y = max(p[0] for p in positions)
        min_x = min(p[1] for p in positions)
        max_x = max(p[1] for p in positions)
        actual_height = max_y - min_y + 1
        actual_width = max_x - min_x + 1

        # Use actual dimensions for centering
        offset_y = (9 - actual_height) // 2
        offset_x = (9 - actual_width) // 2

        # Parse placement map and center on 9x9 grid
        for pos_str, material_id in placement['placementMap'].items():
            y_idx, x_idx = map(int, pos_str.split(','))
            # Normalize to start at 0,0 then add centering offset
            final_y = offset_y + (y_idx - min_y)
            final_x = offset_x + (x_idx - min_x)

            # Bounds check
            if 0 <= final_y < 9 and 0 <= final_x < 9:
                grid[final_y][final_x] = material_id

        return grid

    def _grid_to_image(self, grid, cell_size=4):
        """
        Convert 9x9 grid to 36x36 RGB image.

        With use_shapes=True:
        - Each cell uses category-based shape mask
        - Each cell uses tier-based fill size
        """
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3), dtype=np.float32)

        for i in range(9):
            for j in range(9):
                material_id = grid[i][j]

                if material_id is None:
                    continue

                color = self._material_to_color(material_id)

                if self.use_shapes:
                    # Apply shape and tier masks
                    shape_mask = self._get_shape_mask(material_id)
                    tier_mask = self._get_tier_fill_mask(material_id, cell_size)
                    combined_mask = shape_mask * tier_mask

                    for c in range(3):
                        img[i * cell_size:(i + 1) * cell_size,
                            j * cell_size:(j + 1) * cell_size, c] = color[c] * combined_mask
                else:
                    # Simple flat fill (v1 style)
                    img[i * cell_size:(i + 1) * cell_size,
                        j * cell_size:(j + 1) * cell_size] = color

        return img

    def _render_recipe(self, recipe):
        """Render original recipe to 36x36 image"""
        grid = self._placement_to_grid(recipe)
        return self._grid_to_image(grid, cell_size=4)

    def show_page(self, tab='original', page=0, recipes_per_page=25):
        """
        Show a page of recipes in 5x5 grid

        Args:
            tab: 'original', 'valid', or 'invalid'
            page: Page number (0-indexed)
            recipes_per_page: Number of recipes per page (max 25 for 5x5 grid)
        """
        recipes_per_page = min(recipes_per_page, 25)  # Max 5x5 = 25

        # Get data for this tab
        if tab == 'original':
            images = self.original_images
            labels = [recipe['recipeId'] for recipe in self.original_recipes]
            title_color = 'blue'
            tab_name = 'ORIGINAL RECIPES'
        elif tab == 'valid':
            # Random sample from valid augmented
            np.random.seed(42 + page)  # Different samples per page
            sample_indices = np.random.choice(
                self.valid_indices,
                min(recipes_per_page, len(self.valid_indices)),
                replace=False
            )
            images = [self.X_all[idx] for idx in sample_indices]
            labels = [f"Valid #{idx}" for idx in sample_indices]
            title_color = 'green'
            tab_name = 'VALID AUGMENTED'
        else:  # invalid
            # Random sample from invalid augmented
            np.random.seed(42 + page)
            sample_indices = np.random.choice(
                self.invalid_indices,
                min(recipes_per_page, len(self.invalid_indices)),
                replace=False
            )
            images = [self.X_all[idx] for idx in sample_indices]
            labels = [f"Invalid #{idx}" for idx in sample_indices]
            title_color = 'red'
            tab_name = 'INVALID AUGMENTED'

        # Calculate page range
        start_idx = page * recipes_per_page
        end_idx = min(start_idx + recipes_per_page, len(images))

        if start_idx >= len(images):
            print(f"Page {page + 1} is beyond available data!")
            return

        page_images = images[start_idx:end_idx]
        page_labels = labels[start_idx:end_idx]

        # Calculate total pages
        total_pages = (len(images) + recipes_per_page - 1) // recipes_per_page

        # Create 5x5 grid
        fig, axes = plt.subplots(5, 5, figsize=(15, 15))
        axes = axes.flatten()

        # Title with page info
        fig.suptitle(
            f'{tab_name} - Page {page + 1}/{total_pages} ({len(page_images)} recipes)',
            fontsize=18, fontweight='bold', color=title_color
        )

        # Plot images
        for i, (img, label) in enumerate(zip(page_images, page_labels)):
            axes[i].imshow(img, interpolation='nearest')
            # Truncate long labels
            display_label = label if len(label) <= 20 else label[:17] + "..."
            axes[i].set_title(display_label, fontsize=8, color=title_color)
            axes[i].axis('off')

        # Hide unused subplots
        for i in range(len(page_images), 25):
            axes[i].axis('off')

        plt.tight_layout()
        plt.show()

    def show_random_samples(self, n_valid=10, n_invalid=10, seed=None):
        """Show random samples of valid and invalid recipes"""

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Sample random indices
        valid_sample_idx = np.random.choice(
            self.valid_indices,
            min(n_valid, len(self.valid_indices)),
            replace=False
        )
        invalid_sample_idx = np.random.choice(
            self.invalid_indices,
            min(n_invalid, len(self.invalid_indices)),
            replace=False
        )

        # Create figure
        fig, axes = plt.subplots(2, max(n_valid, n_invalid), figsize=(max(n_valid, n_invalid) * 2, 5))

        if max(n_valid, n_invalid) == 1:
            axes = axes.reshape(-1, 1)

        fig.suptitle('Smithing Dataset: Valid vs Invalid Recipes', fontsize=16, fontweight='bold')

        # Plot valid recipes (top row)
        for i in range(max(n_valid, n_invalid)):
            if i < len(valid_sample_idx):
                idx = valid_sample_idx[i]
                axes[0, i].imshow(self.X_all[idx], interpolation='nearest')
                axes[0, i].set_title(f'Valid #{idx}', fontsize=9, color='green', fontweight='bold')
            axes[0, i].axis('off')

        # Plot invalid recipes (bottom row)
        for i in range(max(n_valid, n_invalid)):
            if i < len(invalid_sample_idx):
                idx = invalid_sample_idx[i]
                axes[1, i].imshow(self.X_all[idx], interpolation='nearest')
                axes[1, i].set_title(f'Invalid #{idx}', fontsize=9, color='red', fontweight='bold')
            axes[1, i].axis('off')

        # Row labels
        fig.text(0.02, 0.75, 'VALID\nRECIPES', ha='center', va='center',
                 fontsize=12, fontweight='bold', color='green', rotation=90)
        fig.text(0.02, 0.25, 'INVALID\nRECIPES', ha='center', va='center',
                 fontsize=12, fontweight='bold', color='red', rotation=90)

        plt.tight_layout()
        plt.subplots_adjust(left=0.05)
        plt.show()

    def show_category_legend(self):
        """Show a legend of category shapes and tier fills"""
        fig, axes = plt.subplots(2, 5, figsize=(15, 6))

        fig.suptitle('Category Shapes & Tier Fills', fontsize=16, fontweight='bold')

        # Row 1: Category shapes
        categories = ['metal', 'wood', 'stone', 'monster_drop', 'elemental']
        colors = [(0.4, 0.6, 0.8), (0.6, 0.4, 0.2), (0.5, 0.5, 0.5), (0.8, 0.3, 0.8), (0.3, 0.8, 0.3)]

        for i, (cat, color) in enumerate(zip(categories, colors)):
            shape = self.CATEGORY_SHAPES.get(cat, self.DEFAULT_SHAPE)
            img = np.zeros((4, 4, 3))
            for c in range(3):
                img[:, :, c] = shape * color[c]
            axes[0, i].imshow(img, interpolation='nearest')
            axes[0, i].set_title(f'{cat.upper()}', fontsize=10, fontweight='bold')
            axes[0, i].axis('off')

        axes[0, 0].set_ylabel('Category\nShapes', fontsize=12, fontweight='bold')

        # Row 2: Tier fills (using metal shape as base)
        base_shape = self.CATEGORY_SHAPES['metal']
        base_color = (0.4, 0.6, 0.8)

        for tier in range(1, 5):
            fill_size = self.TIER_FILL_SIZES[tier]
            tier_mask = np.zeros((4, 4))
            offset = (4 - fill_size) // 2
            tier_mask[offset:offset+fill_size, offset:offset+fill_size] = 1.0
            combined = base_shape * tier_mask

            img = np.zeros((4, 4, 3))
            for c in range(3):
                img[:, :, c] = combined * base_color[c]

            axes[1, tier-1].imshow(img, interpolation='nearest')
            axes[1, tier-1].set_title(f'Tier {tier}\n({fill_size}x{fill_size})', fontsize=10)
            axes[1, tier-1].axis('off')

        axes[1, 4].axis('off')  # Empty cell
        axes[1, 0].set_ylabel('Tier\nFills', fontsize=12, fontweight='bold')

        plt.tight_layout()
        plt.show()

    def show_mixed_grid(self, samples_per_page=50, page=0, seed=None):
        """Show randomly mixed valid and invalid recipes"""

        if seed is not None:
            random.seed(seed + page)
            np.random.seed(seed + page)

        # Sample random indices from both
        n_valid = samples_per_page // 2
        n_invalid = samples_per_page - n_valid

        valid_sample_idx = np.random.choice(
            self.valid_indices,
            min(n_valid, len(self.valid_indices)),
            replace=False
        )
        invalid_sample_idx = np.random.choice(
            self.invalid_indices,
            min(n_invalid, len(self.invalid_indices)),
            replace=False
        )

        # Combine and shuffle
        sample_indices = list(valid_sample_idx) + list(invalid_sample_idx)
        random.shuffle(sample_indices)

        # Calculate grid
        cols = 10
        rows = (len(sample_indices) + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(20, rows * 2))
        axes = axes.flatten()

        fig.suptitle(f'Smithing Dataset - Mixed (Page {page + 1})',
                     fontsize=16, fontweight='bold')

        for i, idx in enumerate(sample_indices):
            axes[i].imshow(self.X_all[idx], interpolation='nearest')

            # Color code the label
            is_valid = self.y_all[idx] == 1
            color = 'green' if is_valid else 'red'
            label = 'V' if is_valid else 'X'

            axes[i].set_title(label, fontsize=10, color=color, fontweight='bold')
            axes[i].axis('off')

        # Hide unused subplots
        for i in range(len(sample_indices), len(axes)):
            axes[i].axis('off')

        plt.tight_layout()
        plt.show()

    def interactive_viewer(self):
        """Interactive tabbed viewer with page navigation"""

        print("\n" + "=" * 80)
        print("SMITHING DATASET VIEWER - TABBED INTERFACE (v2)")
        print("=" * 80)
        print(f"Tabs available:")
        print(f"  1. Original ({len(self.original_recipes)} recipes)")
        print(f"  2. Valid Augmented ({len(self.valid_indices)} samples)")
        print(f"  3. Invalid Augmented ({len(self.invalid_indices)} samples)")
        print(f"\nGrid: 5x5 (25 recipes per page)")
        print(f"Shapes enabled: {self.use_shapes}")

        print("\nCommands:")
        print("  '1' or 'original' - View original recipes")
        print("  '2' or 'valid' - View valid augmented samples")
        print("  '3' or 'invalid' - View invalid augmented samples")
        print("  'next' or 'n' - Next page")
        print("  'prev' or 'p' - Previous page")
        print("  'page N' - Jump to page N")
        print("  'grid N' - Change recipes per page (1-25)")
        print("  'shuffle' - Reshuffle random samples (for valid/invalid tabs)")
        print("  'random N' - Show N valid vs N invalid side-by-side")
        print("  'mixed N' - Show N mixed samples in grid")
        print("  'legend' - Show category shapes and tier fills legend")
        print("  'quit' or 'q' - Exit")

        current_tab = 'original'
        current_page = 0
        recipes_per_page = 25
        random_seed = 42

        # Show first page
        self.show_page(current_tab, current_page, recipes_per_page)

        while True:
            print("\n" + "-" * 80)
            print(f"Current: {current_tab.upper()} tab, Page {current_page + 1}")
            choice = input("Your choice: ").strip().lower()

            if choice in ['quit', 'q']:
                break

            elif choice in ['1', 'original']:
                current_tab = 'original'
                current_page = 0
                self.show_page(current_tab, current_page, recipes_per_page)

            elif choice in ['2', 'valid']:
                current_tab = 'valid'
                current_page = 0
                self.show_page(current_tab, current_page, recipes_per_page)

            elif choice in ['3', 'invalid']:
                current_tab = 'invalid'
                current_page = 0
                self.show_page(current_tab, current_page, recipes_per_page)

            elif choice in ['next', 'n']:
                current_page += 1
                self.show_page(current_tab, current_page, recipes_per_page)

            elif choice in ['prev', 'p']:
                current_page = max(0, current_page - 1)
                self.show_page(current_tab, current_page, recipes_per_page)

            elif choice.startswith('page'):
                try:
                    page_num = int(choice.split()[1]) - 1
                    current_page = max(0, page_num)
                    self.show_page(current_tab, current_page, recipes_per_page)
                except:
                    print("Invalid format. Use: page N")

            elif choice.startswith('grid'):
                try:
                    n = int(choice.split()[1])
                    recipes_per_page = max(1, min(25, n))
                    current_page = 0
                    print(f"Grid size set to {recipes_per_page} recipes per page")
                    self.show_page(current_tab, current_page, recipes_per_page)
                except:
                    print("Invalid format. Use: grid N (1-25)")

            elif choice == 'shuffle':
                if current_tab in ['valid', 'invalid']:
                    random_seed = random.randint(0, 100000)
                    current_page = 0
                    self.show_page(current_tab, current_page, recipes_per_page)
                    print("Shuffled!")
                else:
                    print("Shuffle only works on valid/invalid tabs")

            elif choice.startswith('random'):
                try:
                    n = int(choice.split()[1]) if len(choice.split()) > 1 else 10
                    self.show_random_samples(n_valid=n, n_invalid=n, seed=random_seed)
                except:
                    print("Invalid format. Use: random N")

            elif choice.startswith('mixed'):
                try:
                    n = int(choice.split()[1]) if len(choice.split()) > 1 else 50
                    self.show_mixed_grid(samples_per_page=n, page=0, seed=random_seed)
                except:
                    print("Invalid format. Use: mixed N")

            elif choice == 'legend':
                self.show_category_legend()

            else:
                print("Invalid command. Try: 1/2/3, next, prev, page N, grid N, shuffle, random N, mixed N, legend, or quit")


# Example usage
if __name__ == "__main__":
    import sys

    # Default paths - try v2 first, then v1
    DATASET_PATH_V2 = "recipe_dataset_v2.npz"
    DATASET_PATH_V1 = "recipe_dataset.npz"
    MATERIALS_PATH = "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "../../../Game-1-modular/placements.JSON/placements-smithing-1.JSON"

    # Try v2 first
    if Path(DATASET_PATH_V2).exists():
        dataset_path = DATASET_PATH_V2
        use_shapes = True
        print("Found v2 dataset (with shapes)")
    elif Path(DATASET_PATH_V1).exists():
        dataset_path = DATASET_PATH_V1
        use_shapes = False
        print("Found v1 dataset (flat cells)")
    else:
        dataset_path = input("Dataset path: ").strip()
        use_shapes = input("Use shapes? (y/n): ").strip().lower() == 'y'

    # Get paths
    materials_path = MATERIALS_PATH if Path(MATERIALS_PATH).exists() else input("Materials path: ").strip()
    placements_path = PLACEMENTS_PATH if Path(PLACEMENTS_PATH).exists() else input("Placements path: ").strip()

    # Create visualizer
    viz = SmithingDatasetVisualizer(dataset_path, materials_path, placements_path, use_shapes=use_shapes)

    # Interactive mode
    viz.interactive_viewer()
