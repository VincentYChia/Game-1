import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from colorsys import hsv_to_rgb
import random


class SmithingDatasetVisualizer:
    """Visualize smithing augmented training data with tabs for original/valid/invalid"""

    def __init__(self, dataset_path, materials_path, placements_path):
        """
        Args:
            dataset_path: Path to recipe_dataset.npz
            materials_path: Path to materials JSON
            placements_path: Path to placements JSON
        """
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
        print(f"  Image shape: {self.X_all.shape[1:]}\n")

    def _material_to_color(self, material_id):
        """Convert material to RGB color (0-1 range) based on category, tier, tags"""
        if material_id is None:
            return np.array([0.0, 0.0, 0.0])

        material = self.materials_dict[material_id]
        category = material['category']
        tier = material['tier']
        tags = material['metadata']['tags']

        # CATEGORY → HUE
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
                'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300
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

    def _placement_to_grid(self, placement):
        """Convert placement to centered 9x9 grid"""
        grid = [[None] * 9 for _ in range(9)]

        # Determine grid size and offset
        grid_size_str = placement['metadata']['gridSize']
        recipe_size = int(grid_size_str.split('x')[0])
        offset = (9 - recipe_size) // 2

        # Parse placement map (1-indexed y,x format)
        for pos_str, material_id in placement['placementMap'].items():
            y_idx, x_idx = map(int, pos_str.split(','))
            # Convert to 0-indexed and add offset
            grid[offset + y_idx - 1][offset + x_idx - 1] = material_id

        return grid

    def _grid_to_image(self, grid, cell_size=4):
        """Convert 9x9 grid to 36x36 RGB image"""
        img_size = 9 * cell_size
        img = np.zeros((img_size, img_size, 3))

        for i in range(9):
            for j in range(9):
                color = self._material_to_color(grid[i][j])
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
        print("SMITHING DATASET VIEWER - TABBED INTERFACE")
        print("=" * 80)
        print(f"Tabs available:")
        print(f"  1. Original ({len(self.original_recipes)} recipes)")
        print(f"  2. Valid Augmented ({len(self.valid_indices)} samples)")
        print(f"  3. Invalid Augmented ({len(self.invalid_indices)} samples)")
        print(f"\nGrid: 5×5 (25 recipes per page)")

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

            else:
                print("Invalid command. Try: 1/2/3, next, prev, page N, grid N, shuffle, random N, mixed N, or quit")


# Example usage
if __name__ == "__main__":
    import sys

    # Default paths
    DATASET_PATH = "recipe_dataset.npz"
    MATERIALS_PATH = "../../../Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "../../../Game-1-modular/placements.JSON/placements-smithing-1.JSON"

    # Get paths
    dataset_path = DATASET_PATH if Path(DATASET_PATH).exists() else input("Dataset path: ").strip()
    materials_path = MATERIALS_PATH if Path(MATERIALS_PATH).exists() else input("Materials path: ").strip()
    placements_path = PLACEMENTS_PATH if Path(PLACEMENTS_PATH).exists() else input("Placements path: ").strip()

    # Create visualizer
    viz = SmithingDatasetVisualizer(dataset_path, materials_path, placements_path)

    # Interactive mode
    viz.interactive_viewer()