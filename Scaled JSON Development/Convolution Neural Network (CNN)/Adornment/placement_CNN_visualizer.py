import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json
from colorsys import hsv_to_rgb


class AugmentedDatasetVisualizer:
    """Visualize augmented training data with tabs for original/valid/invalid"""

    def __init__(self, dataset_path, materials_path, placements_path):
        """
        Args:
            dataset_path: Path to adornment_dataset.npz
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
        self.original_recipes = placements_data['placements']

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

    def _render_recipe(self, recipe):
        """Render original recipe to 56x56 image"""
        img = np.zeros((56, 56, 3), dtype=np.float32)

        vertices = recipe['placementMap']['vertices']
        shapes = recipe['placementMap']['shapes']

        def coord_to_pixel(x, y):
            px = int((x + 7) * 4)
            py = int((7 - y) * 4)
            return px, py

        def material_to_color(material_id):
            if material_id is None:
                return (0.5, 0.5, 0.5)

            material = self.materials_dict[material_id]
            category = material['category']
            tier = material['tier']
            tags = material['metadata']['tags']

            if category == 'elemental':
                element_hues = {
                    'fire': 0, 'water': 210, 'earth': 120, 'air': 60,
                    'lightning': 270, 'ice': 180, 'light': 45,
                    'dark': 280, 'void': 290, 'chaos': 330,
                }
                hue = 280
                for tag in tags:
                    if tag in element_hues:
                        hue = element_hues[tag]
                        break
            else:
                category_hues = {
                    'metal': 210, 'wood': 30, 'stone': 0, 'monster_drop': 300
                }
                hue = category_hues.get(category, 0)

            tier_values = {1: 0.50, 2: 0.65, 3: 0.80, 4: 0.95}
            value = tier_values.get(tier, 0.5)

            base_saturation = 0.6
            if category == 'stone':
                base_saturation = 0.2
            if 'legendary' in tags or 'mythical' in tags:
                base_saturation = min(1.0, base_saturation + 0.2)
            elif 'magical' in tags or 'ancient' in tags:
                base_saturation = min(1.0, base_saturation + 0.1)

            rgb = hsv_to_rgb(hue / 360.0, base_saturation, value)
            return rgb

        # Draw lines
        for shape in shapes:
            shape_vertices = shape['vertices']
            n = len(shape_vertices)

            for i in range(n):
                v1_str = shape_vertices[i]
                v2_str = shape_vertices[(i + 1) % n]

                x1, y1 = map(int, v1_str.split(','))
                x2, y2 = map(int, v2_str.split(','))
                px1, py1 = coord_to_pixel(x1, y1)
                px2, py2 = coord_to_pixel(x2, y2)

                mat1 = vertices.get(v1_str, {}).get('materialId')
                mat2 = vertices.get(v2_str, {}).get('materialId')

                if mat1 and mat2:
                    color = tuple((np.array(material_to_color(mat1)) +
                                   np.array(material_to_color(mat2))) / 2)
                elif mat1:
                    color = material_to_color(mat1)
                elif mat2:
                    color = material_to_color(mat2)
                else:
                    color = (0.3, 0.3, 0.3)

                self._draw_line(img, px1, py1, px2, py2, color, thickness=2)

        # Draw vertices
        for coord_str, vertex_data in vertices.items():
            x, y = map(int, coord_str.split(','))
            px, py = coord_to_pixel(x, y)
            material_id = vertex_data.get('materialId')
            color = material_to_color(material_id)
            self._draw_circle(img, px, py, radius=3, color=color)

        return img

    def _draw_line(self, img, x0, y0, x1, y1, color, thickness=1):
        """Draw line with Bresenham's algorithm"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    px, py = x0 + tx, y0 + ty
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                        existing = img[py, px]
                        if np.any(existing > 0):
                            img[py, px] = (existing + color) / 2
                        else:
                            img[py, px] = color

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def _draw_circle(self, img, cx, cy, radius, color):
        """Draw filled circle"""
        for y in range(max(0, cy - radius), min(img.shape[0], cy + radius + 1)):
            for x in range(max(0, cx - radius), min(img.shape[1], cx + radius + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    img[y, x] = color

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
            tab_name = 'ORIGINAL PLACEMENTS'
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
            axes[i].imshow(img)
            # Truncate long labels
            display_label = label if len(label) <= 20 else label[:17] + "..."
            axes[i].set_title(display_label, fontsize=8, color=title_color)
            axes[i].axis('off')

        # Hide unused subplots
        for i in range(len(page_images), 25):
            axes[i].axis('off')

        plt.tight_layout()
        plt.show()

    def interactive_viewer(self):
        """Interactive tabbed viewer with page navigation"""

        print("\n" + "=" * 80)
        print("AUGMENTED DATASET VIEWER - TABBED INTERFACE")
        print("=" * 80)
        print(f"Tabs available:")
        print(f"  1. Original ({len(self.original_recipes)} recipes)")
        print(f"  2. Valid Augmented ({len(self.valid_indices)} samples)")
        print(f"  3. Invalid Augmented ({len(self.invalid_indices)} samples)")
        print(f"\nGrid: 5×5 (25 recipes per page)")

        print("\nCommands:")
        print("  '1' or 'original' - View original placements")
        print("  '2' or 'valid' - View valid augmented samples")
        print("  '3' or 'invalid' - View invalid augmented samples")
        print("  'next' or 'n' - Next page")
        print("  'prev' or 'p' - Previous page")
        print("  'page N' - Jump to page N")
        print("  'grid N' - Change recipes per page (1-25)")
        print("  'shuffle' - Reshuffle random samples (for valid/invalid tabs)")
        print("  'quit' or 'q' - Exit")

        current_tab = 'original'
        current_page = 0
        recipes_per_page = 25

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
                    import random
                    # Use random seed based on time
                    np.random.seed(random.randint(0, 100000))
                    current_page = 0
                    self.show_page(current_tab, current_page, recipes_per_page)
                    print("Shuffled!")
                else:
                    print("Shuffle only works on valid/invalid tabs")

            else:
                print("Invalid command. Try: 1/2/3, next, prev, page N, grid N, shuffle, or quit")


# Example usage
if __name__ == "__main__":
    import sys

    # Default paths
    DATASET_PATH = "adornment_dataset.npz"
    MATERIALS_PATH = "C:/Users/Vincent/PycharmProjects/Game-1/Game-1-modular/items.JSON/items-materials-1.JSON"
    PLACEMENTS_PATH = "C:/Users/Vincent/PycharmProjects/Game-1/Game-1-modular/placements.JSON/placements-adornments-1.JSON"

    # Get paths
    dataset_path = DATASET_PATH if Path(DATASET_PATH).exists() else input("Dataset path: ").strip()
    materials_path = MATERIALS_PATH if Path(MATERIALS_PATH).exists() else input("Materials path: ").strip()
    placements_path = PLACEMENTS_PATH if Path(PLACEMENTS_PATH).exists() else input("Placements path: ").strip()

    # Create visualizer
    viz = AugmentedDatasetVisualizer(dataset_path, materials_path, placements_path)

    # Interactive mode
    viz.interactive_viewer()


    def show_random_samples(self, n_valid=10, n_invalid=10, seed=None):
        """Show random samples of valid and invalid recipes"""

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Sample random indices
        valid_sample_idx = np.random.choice(self.valid_indices, min(n_valid, len(self.valid_indices)), replace=False)
        invalid_sample_idx = np.random.choice(self.invalid_indices, min(n_invalid, len(self.invalid_indices)),
                                              replace=False)

        # Create figure
        fig, axes = plt.subplots(2, max(n_valid, n_invalid), figsize=(max(n_valid, n_invalid) * 2, 5))

        if max(n_valid, n_invalid) == 1:
            axes = axes.reshape(-1, 1)

        fig.suptitle('Augmented Dataset: Valid vs Invalid Recipes', fontsize=16, fontweight='bold')

        # Plot valid recipes (top row)
        for i in range(max(n_valid, n_invalid)):
            if i < len(valid_sample_idx):
                idx = valid_sample_idx[i]
                axes[0, i].imshow(self.X_all[idx])
                axes[0, i].set_title(f'Valid #{idx}', fontsize=9, color='green', fontweight='bold')
            axes[0, i].axis('off')

        # Plot invalid recipes (bottom row)
        for i in range(max(n_valid, n_invalid)):
            if i < len(invalid_sample_idx):
                idx = invalid_sample_idx[i]
                axes[1, i].imshow(self.X_all[idx])
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


    def show_side_by_side_grid(self, samples_per_page=25, page=0, seed=None):
        """Show valid and invalid side by side in a grid"""

        if seed is not None:
            random.seed(seed + page)  # Different seed per page
            np.random.seed(seed + page)

        # Calculate grid size
        cols = 10  # 5 valid + 5 invalid per row
        rows = (samples_per_page + 1) // 2

        # Sample random indices
        n_pairs = samples_per_page // 2
        valid_sample_idx = np.random.choice(self.valid_indices, min(n_pairs, len(self.valid_indices)), replace=False)
        invalid_sample_idx = np.random.choice(self.invalid_indices, min(n_pairs, len(self.invalid_indices)),
                                              replace=False)

        # Create figure
        fig, axes = plt.subplots(rows, cols, figsize=(20, rows * 2))
        axes = axes.flatten()

        fig.suptitle(f'Augmented Dataset - Page {page + 1} (Random Samples)',
                     fontsize=16, fontweight='bold')

        idx = 0
        for i in range(n_pairs):
            # Valid recipe
            if i < len(valid_sample_idx):
                axes[idx].imshow(self.X_all[valid_sample_idx[i]])
                axes[idx].set_title('Valid', fontsize=8, color='green', fontweight='bold')
                axes[idx].axis('off')
                idx += 1

            # Invalid recipe
            if i < len(invalid_sample_idx):
                axes[idx].imshow(self.X_all[invalid_sample_idx[i]])
                axes[idx].set_title('Invalid', fontsize=8, color='red', fontweight='bold')
                axes[idx].axis('off')
                idx += 1

        # Hide unused subplots
        for i in range(idx, len(axes)):
            axes[i].axis('off')

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

        valid_sample_idx = np.random.choice(self.valid_indices, min(n_valid, len(self.valid_indices)), replace=False)
        invalid_sample_idx = np.random.choice(self.invalid_indices, min(n_invalid, len(self.invalid_indices)),
                                              replace=False)

        # Combine and shuffle
        sample_indices = list(valid_sample_idx) + list(invalid_sample_idx)
        random.shuffle(sample_indices)

        # Calculate grid
        cols = 10
        rows = (len(sample_indices) + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(20, rows * 2))
        axes = axes.flatten()

        fig.suptitle(f'Augmented Dataset - Mixed (Page {page + 1})',
                     fontsize=16, fontweight='bold')

        for i, idx in enumerate(sample_indices):
            axes[i].imshow(self.X_all[idx])

            # Color code the border
            is_valid = self.y_all[idx] == 1
            color = 'green' if is_valid else 'red'
            label = 'V' if is_valid else 'X'

            axes[i].set_title(label, fontsize=10, color=color, fontweight='bold')
            axes[i].axis('off')

            # Add colored border
            for spine in axes[i].spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(2)

        # Hide unused subplots
        for i in range(len(sample_indices), len(axes)):
            axes[i].axis('off')

        plt.tight_layout()
        plt.show()


    def compare_augmentations(self, n_examples=5, seed=None):
        """Show how augmentation creates variations"""

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Find similar valid recipes (they might be augmentations of same base)
        valid_sample_idx = np.random.choice(self.valid_indices, n_examples * 3, replace=False)

        fig, axes = plt.subplots(n_examples, 3, figsize=(9, n_examples * 3))

        if n_examples == 1:
            axes = axes.reshape(1, -1)

        fig.suptitle('Augmented Variations (Likely from same base recipe)',
                     fontsize=14, fontweight='bold')

        for i in range(n_examples):
            for j in range(3):
                idx = valid_sample_idx[i * 3 + j]
                axes[i, j].imshow(self.X_all[idx])
                axes[i, j].set_title(f'Sample #{idx}', fontsize=8)
                axes[i, j].axis('off')

        plt.tight_layout()
        plt.show()


    def interactive_browser(self):
        """Interactive browser for dataset"""

        print("\n" + "=" * 80)
        print("AUGMENTED DATASET BROWSER")
        print("=" * 80)
        print(f"Total samples: {len(self.X_all)}")
        print(f"Valid: {len(self.valid_indices)}")
        print(f"Invalid: {len(self.invalid_indices)}")

        print("\nCommands:")
        print("  'random N' - Show N random valid and N random invalid (e.g., 'random 10')")
        print("  'side N' - Show N samples side-by-side (e.g., 'side 25')")
        print("  'mixed N' - Show N mixed samples (e.g., 'mixed 50')")
        print("  'compare N' - Show N sets of augmented variations (e.g., 'compare 5')")
        print("  'next' - Show next page (for paginated views)")
        print("  'new' - Reshuffle with new random seed")
        print("  'quit' - Exit")

        current_page = 0
        current_mode = None
        current_n = 50
        current_seed = 42

        while True:
            print("\n" + "-" * 80)
            choice = input("Your choice: ").strip().lower()

            if choice == 'quit':
                break

            elif choice.startswith('random'):
                parts = choice.split()
                n = int(parts[1]) if len(parts) > 1 else 10
                self.show_random_samples(n_valid=n, n_invalid=n, seed=current_seed)
                current_mode = 'random'
                current_n = n
                current_page = 0

            elif choice.startswith('side'):
                parts = choice.split()
                n = int(parts[1]) if len(parts) > 1 else 25
                self.show_side_by_side_grid(samples_per_page=n, page=current_page, seed=current_seed)
                current_mode = 'side'
                current_n = n

            elif choice.startswith('mixed'):
                parts = choice.split()
                n = int(parts[1]) if len(parts) > 1 else 50
                self.show_mixed_grid(samples_per_page=n, page=current_page, seed=current_seed)
                current_mode = 'mixed'
                current_n = n

            elif choice.startswith('compare'):
                parts = choice.split()
                n = int(parts[1]) if len(parts) > 1 else 5
                self.compare_augmentations(n_examples=n, seed=current_seed)
                current_mode = 'compare'
                current_n = n

            elif choice == 'next':
                current_page += 1
                if current_mode == 'side':
                    self.show_side_by_side_grid(samples_per_page=current_n, page=current_page, seed=current_seed)
                elif current_mode == 'mixed':
                    self.show_mixed_grid(samples_per_page=current_n, page=current_page, seed=current_seed)
                else:
                    print("Use 'side N' or 'mixed N' first")

            elif choice == 'new':
                current_seed = random.randint(0, 10000)
                current_page = 0
                print(f"New random seed: {current_seed}")

            else:
                print("Invalid command. Try 'random 10', 'side 25', 'mixed 50', 'compare 5', 'next', 'new', or 'quit'")

# Example usage
if __name__ == "__main__":
    import sys

    # Get dataset path
    dataset_path = "adornment_dataset.npz"

    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    elif not Path(dataset_path).exists():
        dataset_path = input("Enter path to adornment_dataset.npz: ").strip()

    if not Path(dataset_path).exists():
        print(f"Error: Dataset not found at {dataset_path}")
        sys.exit(1)

    # Create visualizer
    viz = AugmentedDatasetVisualizer(dataset_path)

    # Interactive mode
    viz.interactive_browser()