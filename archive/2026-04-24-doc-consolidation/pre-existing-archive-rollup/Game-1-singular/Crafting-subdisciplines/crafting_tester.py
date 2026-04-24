import pygame
import json
import sys
from pathlib import Path

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 920
CELL_SIZE = 70
GRID_SIZE = 5
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
LIGHT_GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)
ORANGE = (255, 140, 0)
GREEN = (0, 200, 0)
RED = (200, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (100, 150, 255)

# Material colors (simplified)
MATERIAL_COLORS = {
    "iron_ingot": (176, 176, 176),
    "oak_plank": (139, 69, 19),
    "ash_plank": (160, 130, 109),
    "steel_ingot": (119, 136, 153),
    "maple_plank": (210, 105, 30),
    "dire_fang": (245, 245, 220),
    "copper_ingot": (184, 115, 51),
    "pine_log": (139, 90, 43),
    "ash_log": (120, 100, 80),
    "oak_log": (101, 67, 33),
    "wolf_pelt": (169, 169, 169),
    "beetle_carapace": (85, 107, 47),
    "slime_gel": (50, 205, 50),
    "granite": (128, 128, 128),
    "birch_plank": (222, 184, 135),
    "ironwood_plank": (105, 105, 105),
    "leather_strip": (139, 90, 43),
    "spectral_thread": (230, 230, 250),
    "lightning_shard": (255, 255, 0),
    "water_crystal": (0, 191, 255),
    "earth_crystal": (139, 69, 19),
    "fire_crystal": (255, 69, 0),
    "golem_core": (105, 105, 105),
    "ebony_plank": (60, 60, 60),
    "mithril_ingot": (192, 192, 192)
}


class SmithingTester:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Smithing Crafting Tester")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 36)

        # Load data
        self.recipes = self.load_recipes()
        self.placements = self.load_placements()
        self.materials_db = self.load_materials()

        # Game state
        self.mode = "basic"  # "basic", "manual", "minigame"
        self.selected_recipe = None
        self.current_grid = {}
        self.selected_material = None
        self.last_selected_material = None
        self.recipe_scroll = 0  # For scrolling through recipes
        self.material_scroll = 0  # For scrolling through materials

        # Inventory (for testing - generous amounts)
        self.inventory = {
            "iron_ingot": 50,
            "oak_plank": 50,
            "ash_plank": 50,
            "steel_ingot": 50,
            "maple_plank": 50,
            "dire_fang": 50,
            "copper_ingot": 50,
            "pine_log": 50,
            "ash_log": 50,
            "oak_log": 50,
            "wolf_pelt": 50,
            "beetle_carapace": 50,
            "slime_gel": 50,
            "granite": 50,
            "birch_plank": 50,
            "ironwood_plank": 50,
            "leather_strip": 50,
            "spectral_thread": 50,
            "lightning_shard": 50,
            "water_crystal": 50,
            "earth_crystal": 50,
            "fire_crystal": 50,
            "golem_core": 50,
            "ebony_plank": 50,
            "mithril_ingot": 50
        }

        # Crafted items inventory
        self.crafted_items = {}  # {outputId: quantity}

        # Minigame state
        self.minigame_active = False
        self.temperature = 50
        self.hammer_hits = 0
        self.hammer_position = 0
        self.hammer_direction = 1
        self.hammer_scores = []
        self.time_left = 30
        self.last_temp_update = 0
        self.crafting_result = None

        # Minigame config
        self.TEMP_IDEAL_MIN = 60
        self.TEMP_IDEAL_MAX = 80
        self.TEMP_FAN_INCREMENT = 3
        self.TEMP_DECAY = 0.5
        self.HAMMER_SPEED = 3
        self.REQUIRED_HITS = 5
        self.HAMMER_BAR_WIDTH = 400
        self.TARGET_WIDTH = 80
        self.PERFECT_WIDTH = 30

        self.running = True

    def load_recipes(self):
        """Load recipes from JSON file"""
        # Try to load from typical locations
        possible_paths = [
            "recipes-smithing-3.json",
            "recipes.JSON/recipes-smithing-3.json",
            "../recipes.JSON/recipes-smithing-3.json",
        ]

        recipes = {}
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:  # Load all recipes
                        recipes[recipe['recipeId']] = recipe
                    print(f"Loaded {len(recipes)} recipes from {path}")
                    return recipes
            except FileNotFoundError:
                continue

        # Fallback: hardcoded test recipes
        print("Could not find recipe JSON, using hardcoded test data")
        return {
            "smithing_iron_shortsword": {
                "recipeId": "smithing_iron_shortsword",
                "name": "Iron Shortsword",
                "outputId": "iron_shortsword",
                "outputQty": 1,
                "stationTier": 1,
                "gridSize": "3x3",
                "inputs": [
                    {"materialId": "iron_ingot", "quantity": 2},
                    {"materialId": "oak_plank", "quantity": 1}
                ],
                "metadata": {
                    "narrative": "A basic iron sword."
                }
            }
        }

    def load_placements(self):
        """Load placement data from JSON file"""
        possible_paths = [
            "placements-smithing-1.JSON",
            "placements.JSON/placements-smithing-1.JSON",
            "../placements.JSON/placements-smithing-1.JSON",
        ]

        placements = {}
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    placement_list = data.get('placements', [])
                    for p in placement_list:
                        placements[p['recipeId']] = p.get('placementMap', {})
                    print(f"Loaded {len(placements)} placements from {path}")
                    return placements
            except FileNotFoundError:
                continue

        # Fallback
        print("Could not find placement JSON, using hardcoded test data")
        return {
            "smithing_iron_shortsword": {
                "3,1": "oak_plank",
                "2,2": "iron_ingot",
                "1,3": "iron_ingot"
            }
        }

    def load_materials(self):
        """Create materials database"""
        return {
            "iron_ingot": {"name": "Iron Ingot", "tier": 1},
            "oak_plank": {"name": "Oak Plank", "tier": 1},
            "ash_plank": {"name": "Ash Plank", "tier": 1},
            "steel_ingot": {"name": "Steel Ingot", "tier": 2},
            "maple_plank": {"name": "Maple Plank", "tier": 2},
            "dire_fang": {"name": "Dire Fang", "tier": 2},
            "copper_ingot": {"name": "Copper Ingot", "tier": 1},
            "pine_log": {"name": "Pine Log", "tier": 1},
            "ash_log": {"name": "Ash Log", "tier": 1},
            "oak_log": {"name": "Oak Log", "tier": 1},
            "wolf_pelt": {"name": "Wolf Pelt", "tier": 1},
            "beetle_carapace": {"name": "Beetle Carapace", "tier": 1},
            "slime_gel": {"name": "Slime Gel", "tier": 1},
            "granite": {"name": "Granite", "tier": 1},
            "birch_plank": {"name": "Birch Plank", "tier": 2},
            "ironwood_plank": {"name": "Ironwood Plank", "tier": 2},
            "leather_strip": {"name": "Leather Strip", "tier": 1},
            "spectral_thread": {"name": "Spectral Thread", "tier": 2},
            "lightning_shard": {"name": "Lightning Shard", "tier": 2},
            "water_crystal": {"name": "Water Crystal", "tier": 1},
            "earth_crystal": {"name": "Earth Crystal", "tier": 1},
            "fire_crystal": {"name": "Fire Crystal", "tier": 1},
            "golem_core": {"name": "Golem Core", "tier": 3},
            "ebony_plank": {"name": "Ebony Plank", "tier": 3},
            "mithril_ingot": {"name": "Mithril Ingot", "tier": 3}
        }

    def get_recipe_grid_size(self, recipe):
        """Extract grid size from recipe"""
        grid_str = recipe.get('gridSize', '3x3')
        return int(grid_str.split('x')[0])

    def get_recipe_name(self, recipe):
        """Get recipe display name"""
        if 'name' in recipe:
            return recipe['name']
        # Fallback: prettify recipeId
        recipe_id = recipe.get('recipeId', 'Unknown')
        # Convert smithing_iron_shortsword -> Iron Shortsword
        parts = recipe_id.replace('smithing_', '').split('_')
        return ' '.join(word.capitalize() for word in parts)

    def center_placement_map(self, placement_map, recipe_size):
        """Center a smaller recipe in the larger grid"""
        offset = (GRID_SIZE - recipe_size) // 2
        centered = {}
        for key, material in placement_map.items():
            row, col = map(int, key.split(','))
            new_row = row + offset
            new_col = col + offset
            centered[f"{new_row},{new_col}"] = material
        return centered

    def auto_fill_grid(self):
        """Auto-fill grid for basic crafting mode"""
        if self.selected_recipe:
            recipe = self.recipes[self.selected_recipe]
            recipe_size = self.get_recipe_grid_size(recipe)
            placement = self.placements.get(self.selected_recipe, {})
            self.current_grid = self.center_placement_map(placement, recipe_size)

    def detect_recipe(self):
        """Detect which recipe matches current grid"""
        for recipe_id, recipe in self.recipes.items():
            recipe_size = self.get_recipe_grid_size(recipe)
            placement = self.placements.get(recipe_id, {})
            centered = self.center_placement_map(placement, recipe_size)

            if set(self.current_grid.keys()) == set(centered.keys()):
                if all(self.current_grid.get(k) == centered.get(k) for k in centered.keys()):
                    return recipe_id
        return None

    def can_craft_recipe(self, recipe_id):
        """Check if player has enough materials"""
        recipe = self.recipes[recipe_id]
        for inp in recipe['inputs']:
            if self.inventory.get(inp['materialId'], 0) < inp['quantity']:
                return False
        return True

    def handle_basic_craft(self):
        """Handle instant basic crafting"""
        if not self.selected_recipe or not self.can_craft_recipe(self.selected_recipe):
            return

        recipe = self.recipes[self.selected_recipe]

        # Deduct materials
        for inp in recipe['inputs']:
            self.inventory[inp['materialId']] -= inp['quantity']

        # Add crafted item to inventory
        output_id = recipe['outputId']
        output_qty = recipe['outputQty']
        self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + output_qty

        print(f"Crafted {output_qty}x {output_id}")

        self.current_grid = {}
        self.selected_recipe = None

    def start_minigame(self):
        """Start the smithing minigame"""
        self.mode = "minigame"
        self.minigame_active = True
        self.temperature = 50
        self.hammer_hits = 0
        self.hammer_position = 0
        self.hammer_direction = 1
        self.hammer_scores = []
        self.time_left = 30
        self.last_temp_update = pygame.time.get_ticks()
        self.crafting_result = None

    def update_minigame(self):
        """Update minigame state"""
        if not self.minigame_active:
            return

        # Temperature decay
        now = pygame.time.get_ticks()
        if now - self.last_temp_update > 100:
            self.temperature = max(0, self.temperature - self.TEMP_DECAY)
            self.last_temp_update = now

        # Hammer movement
        if self.hammer_hits < self.REQUIRED_HITS:
            self.hammer_position += self.hammer_direction * self.HAMMER_SPEED
            if self.hammer_position <= 0 or self.hammer_position >= self.HAMMER_BAR_WIDTH:
                self.hammer_direction *= -1
                self.hammer_position = max(0, min(self.HAMMER_BAR_WIDTH, self.hammer_position))

        # Timer
        if pygame.time.get_ticks() % 1000 < 20:  # Rough second counter
            self.time_left = max(0, self.time_left - 1)
            if self.time_left <= 0:
                self.end_minigame(False)

    def handle_fan(self):
        """Handle fan action (spacebar)"""
        if self.minigame_active:
            self.temperature = min(100, self.temperature + self.TEMP_FAN_INCREMENT)

    def handle_hammer(self):
        """Handle hammer action (click)"""
        if not self.minigame_active or self.hammer_hits >= self.REQUIRED_HITS:
            return

        center = self.HAMMER_BAR_WIDTH / 2
        distance = abs(self.hammer_position - center)

        if distance <= self.PERFECT_WIDTH / 2:
            score = 100
        elif distance <= self.TARGET_WIDTH / 2:
            score = 70
        else:
            score = 30

        self.hammer_scores.append(score)
        self.hammer_hits += 1

        if self.hammer_hits >= self.REQUIRED_HITS:
            self.end_minigame(True)

    def end_minigame(self, completed):
        """End the minigame and calculate results"""
        self.minigame_active = False

        if not completed:
            self.crafting_result = {"success": False, "message": "Time's up!"}
            return

        # Calculate score
        avg_score = sum(self.hammer_scores) / len(self.hammer_scores)
        temp_mult = 1.5 if self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX else 1.0
        final_score = avg_score * temp_mult

        if final_score >= 140:
            bonus = "+15% bonus stats"
        elif final_score >= 100:
            bonus = "+10% bonus stats"
        elif final_score >= 70:
            bonus = "+5% bonus stats"
        else:
            bonus = "Base stats only"

        # Deduct materials
        recipe = self.recipes[self.selected_recipe]
        for inp in recipe['inputs']:
            self.inventory[inp['materialId']] -= inp['quantity']

        # Add crafted item to inventory
        output_id = recipe['outputId']
        output_qty = recipe['outputQty']
        self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + output_qty

        print(f"Crafted {output_qty}x {output_id} with score {final_score:.1f}")

        self.crafting_result = {
            "success": True,
            "score": final_score,
            "bonus": bonus,
            "temp_mult": temp_mult
        }

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.MOUSEWHEEL:
                # Scroll recipe list or material list
                if self.mode == "basic":
                    self.recipe_scroll = max(0, min(len(self.recipes) - 7, self.recipe_scroll - event.y))
                elif self.mode == "manual":
                    self.material_scroll = max(0, min(len(self.materials_db) - 10, self.material_scroll - event.y))

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.minigame_active:
                        self.handle_fan()
                    elif self.mode == "manual" and self.last_selected_material:
                        self.selected_material = self.last_selected_material
                elif event.key == pygame.K_1:
                    self.mode = "basic"
                    self.current_grid = {}
                elif event.key == pygame.K_2:
                    self.mode = "manual"
                    self.current_grid = {}
                    self.selected_recipe = None

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_click(event.pos)

    def handle_click(self, pos):
        """Handle mouse clicks"""
        x, y = pos

        # Mode buttons
        if 450 <= x <= 600 and 50 <= y <= 90:
            self.mode = "basic"
            self.current_grid = {}
        elif 620 <= x <= 770 and 50 <= y <= 90:
            self.mode = "manual"
            self.current_grid = {}
            self.selected_recipe = None

        # Recipe list (basic mode)
        if self.mode == "basic" and 50 <= x <= 350:
            recipe_y = 150
            recipe_list = list(self.recipes.keys())
            visible_recipes = recipe_list[self.recipe_scroll:self.recipe_scroll + 7]

            for i, recipe_id in enumerate(visible_recipes):
                if recipe_y <= y <= recipe_y + 60:
                    self.selected_recipe = recipe_id
                    self.auto_fill_grid()
                    return
                recipe_y += 70

        # Material palette (manual mode)
        if self.mode == "manual" and 50 <= x <= 350:
            mat_y = 150
            material_list = list(self.materials_db.keys())
            visible_materials = material_list[self.material_scroll:self.material_scroll + 10]

            for mat_id in visible_materials:
                if mat_y <= y <= mat_y + 40:
                    if self.inventory.get(mat_id, 0) > 0:
                        self.selected_material = mat_id
                        self.last_selected_material = mat_id
                    return
                mat_y += 50

        # Grid clicks
        grid_x_start = 400
        grid_y_start = 150
        if grid_x_start <= x <= grid_x_start + GRID_SIZE * CELL_SIZE:
            if grid_y_start <= y <= grid_y_start + GRID_SIZE * CELL_SIZE:
                col = (x - grid_x_start) // CELL_SIZE + 1
                row = (y - grid_y_start) // CELL_SIZE + 1
                self.handle_grid_click(row, col)

        # Craft button
        if self.mode == "basic" and 1000 <= x <= 1350 and 700 <= y <= 750:
            if self.selected_recipe and self.can_craft_recipe(self.selected_recipe):
                self.handle_basic_craft()

        # Minigame button
        if 1000 <= x <= 1350 and 760 <= y <= 810:
            if self.mode == "basic" and self.selected_recipe:
                if self.can_craft_recipe(self.selected_recipe):
                    self.start_minigame()
            elif self.mode == "manual":
                detected = self.detect_recipe()
                if detected:
                    self.selected_recipe = detected
                    self.start_minigame()

        # Hammer button in minigame
        if self.minigame_active and 500 <= x <= 900 and 650 <= y <= 700:
            self.handle_hammer()

        # Result continue button
        if self.crafting_result and 600 <= x <= 800 and 650 <= y <= 700:
            self.crafting_result = None
            self.mode = "basic"
            self.selected_recipe = None
            self.current_grid = {}

    def handle_grid_click(self, row, col):
        """Handle grid cell clicks"""
        if self.mode != "manual":
            return

        key = f"{row},{col}"

        if self.selected_material:
            if self.inventory.get(self.selected_material, 0) > 0:
                # Return old material
                if key in self.current_grid:
                    old_mat = self.current_grid[key]
                    self.inventory[old_mat] = self.inventory.get(old_mat, 0) + 1

                # Place new material
                self.current_grid[key] = self.selected_material
                self.inventory[self.selected_material] -= 1
                self.selected_material = None
        elif key in self.current_grid:
            # Remove material
            mat = self.current_grid[key]
            self.inventory[mat] = self.inventory.get(mat, 0) + 1
            del self.current_grid[key]

    def draw(self):
        """Main draw function"""
        self.screen.fill(DARK_GRAY)

        if self.crafting_result:
            self.draw_result_screen()
        elif self.minigame_active:
            self.draw_minigame()
        else:
            self.draw_main_ui()

        pygame.display.flip()

    def draw_main_ui(self):
        """Draw main crafting UI"""
        # Title
        title = self.large_font.render("Smithing Station - Tester", True, ORANGE)
        self.screen.blit(title, (500, 10))

        # Mode buttons
        basic_color = ORANGE if self.mode == "basic" else GRAY
        manual_color = BLUE if self.mode == "manual" else GRAY
        pygame.draw.rect(self.screen, basic_color, (450, 50, 150, 40))
        pygame.draw.rect(self.screen, manual_color, (620, 50, 150, 40))

        basic_text = self.font.render("Basic (1)", True, WHITE)
        manual_text = self.font.render("Manual (2)", True, WHITE)
        self.screen.blit(basic_text, (470, 60))
        self.screen.blit(manual_text, (630, 60))

        # Left panel
        if self.mode == "basic":
            self.draw_recipe_list()
        else:
            self.draw_material_palette()

        # Grid
        self.draw_grid()

        # Output panel
        self.draw_output_panel()

        # Crafted items inventory
        self.draw_crafted_inventory()

    def draw_recipe_list(self):
        """Draw recipe list for basic mode"""
        # Draw scrollable recipe list
        recipe_list = list(self.recipes.items())
        visible_recipes = recipe_list[self.recipe_scroll:self.recipe_scroll + 7]

        y = 150
        for recipe_id, recipe in visible_recipes:
            can_craft = self.can_craft_recipe(recipe_id)
            is_selected = recipe_id == self.selected_recipe

            color = ORANGE if is_selected else (GREEN if can_craft else LIGHT_GRAY)
            pygame.draw.rect(self.screen, color, (50, y, 300, 60))

            name_text = self.font.render(self.get_recipe_name(recipe), True, WHITE)
            self.screen.blit(name_text, (60, y + 5))

            # Show materials
            mat_y = y + 30
            for inp in recipe['inputs'][:2]:  # Show first 2 materials to fit
                mat = self.materials_db.get(inp['materialId'], {})
                has_enough = self.inventory.get(inp['materialId'], 0) >= inp['quantity']
                mat_color = GREEN if has_enough else RED

                mat_text = self.small_font.render(
                    f"{mat.get('name', inp['materialId'])}: {self.inventory.get(inp['materialId'], 0)}/{inp['quantity']}",
                    True, mat_color
                )
                self.screen.blit(mat_text, (70, mat_y))
                mat_y += 20

            y += 70

        # Scroll indicator
        if len(self.recipes) > 7:
            scroll_text = self.small_font.render(
                f"Scroll: {self.recipe_scroll + 1}-{min(self.recipe_scroll + 7, len(self.recipes))} / {len(self.recipes)}",
                True, WHITE)
            self.screen.blit(scroll_text, (50, 120))

    def draw_material_palette(self):
        """Draw material palette for manual mode"""
        # Draw scrollable material list
        material_list = list(self.materials_db.items())
        visible_materials = material_list[self.material_scroll:self.material_scroll + 10]

        y = 150
        for mat_id, mat_info in visible_materials:
            is_selected = mat_id == self.selected_material
            color = YELLOW if is_selected else MATERIAL_COLORS.get(mat_id, GRAY)

            pygame.draw.rect(self.screen, color, (50, y, 300, 40))

            mat_text = self.font.render(
                f"{mat_info['name']}: {self.inventory.get(mat_id, 0)}",
                True, WHITE
            )
            self.screen.blit(mat_text, (60, y + 10))

            y += 50

        # Scroll indicator
        if len(self.materials_db) > 10:
            scroll_text = self.small_font.render(
                f"Scroll: {self.material_scroll + 1}-{min(self.material_scroll + 10, len(self.materials_db))} / {len(self.materials_db)}",
                True, WHITE
            )
            self.screen.blit(scroll_text, (50, 120))

        if self.selected_material:
            info_text = self.small_font.render(
                f"Selected: {self.materials_db[self.selected_material]['name']} (Space to reselect)",
                True, YELLOW
            )
            self.screen.blit(info_text, (50, y + 20))

    def draw_crafted_inventory(self):
        """Draw the crafted items inventory"""
        panel_x = 50
        panel_y = 700
        panel_width = 900
        panel_height = 180

        # Background
        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 3)

        # Title
        title = self.font.render("Crafted Items Inventory", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        if not self.crafted_items:
            empty_text = self.small_font.render("No items crafted yet. Craft something to see it here!", True,
                                                LIGHT_GRAY)
            self.screen.blit(empty_text, (panel_x + 250, panel_y + 80))
            return

        # Display crafted items in a grid
        item_x = panel_x + 20
        item_y = panel_y + 45
        items_per_row = 8
        item_spacing = 110

        for i, (item_id, quantity) in enumerate(self.crafted_items.items()):
            if i >= 16:  # Limit display to 16 items (2 rows)
                break

            col = i % items_per_row
            row = i // items_per_row

            x = item_x + col * item_spacing
            y = item_y + row * 65

            # Item box
            pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, 100, 55))
            pygame.draw.rect(self.screen, WHITE, (x, y, 100, 55), 2)

            # Item name (shortened)
            item_name = item_id.replace('_', ' ').title()
            if len(item_name) > 12:
                item_name = item_name[:10] + ".."

            name_text = self.small_font.render(item_name, True, WHITE)
            self.screen.blit(name_text, (x + 5, y + 5))

            # Quantity
            qty_text = self.font.render(f"x{quantity}", True, GREEN)
            self.screen.blit(qty_text, (x + 5, y + 28))

    def draw_grid(self):
        """Draw crafting grid"""
        grid_x = 400
        grid_y = 150

        recipe = self.recipes.get(self.selected_recipe) if self.selected_recipe else None
        recipe_size = self.get_recipe_grid_size(recipe) if recipe else GRID_SIZE
        offset = (GRID_SIZE - recipe_size) // 2

        for row in range(1, GRID_SIZE + 1):
            for col in range(1, GRID_SIZE + 1):
                x = grid_x + (col - 1) * CELL_SIZE
                y = grid_y + (row - 1) * CELL_SIZE

                # Check if in recipe area
                in_recipe = (recipe and
                             offset + 1 <= row <= offset + recipe_size and
                             offset + 1 <= col <= offset + recipe_size)

                key = f"{row},{col}"
                material = self.current_grid.get(key)

                if material:
                    color = MATERIAL_COLORS.get(material, GRAY)
                else:
                    color = GRAY if in_recipe else (40, 40, 40)

                pygame.draw.rect(self.screen, color, (x, y, CELL_SIZE - 2, CELL_SIZE - 2))
                pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, CELL_SIZE - 2, CELL_SIZE - 2), 2)

        # Grid info
        if recipe and recipe_size < GRID_SIZE:
            info_text = self.small_font.render(
                f"{recipe_size}x{recipe_size} recipe in {GRID_SIZE}x{GRID_SIZE} grid",
                True, WHITE
            )
            self.screen.blit(info_text, (grid_x, grid_y - 25))

        # Detection in manual mode
        if self.mode == "manual":
            detected = self.detect_recipe()
            if detected:
                det_recipe = self.recipes[detected]
                det_text = self.font.render(f"Detected: {self.get_recipe_name(det_recipe)}", True, GREEN)
                self.screen.blit(det_text, (grid_x, grid_y + GRID_SIZE * CELL_SIZE + 10))

    def draw_output_panel(self):
        """Draw output info panel"""
        panel_x = 1000
        panel_y = 150

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, 350, 500))

        recipe_id = self.selected_recipe
        if self.mode == "manual":
            recipe_id = self.detect_recipe()

        if recipe_id:
            recipe = self.recipes[recipe_id]

            # Recipe name
            name_text = self.large_font.render(self.get_recipe_name(recipe), True, WHITE)
            self.screen.blit(name_text, (panel_x + 10, panel_y + 10))

            # Narrative
            narrative = recipe.get('metadata', {}).get('narrative', 'No description')
            # Word wrap narrative
            words = narrative.split()
            line = ""
            y_offset = panel_y + 60
            for word in words:
                test_line = line + word + " "
                if self.small_font.size(test_line)[0] < 330:
                    line = test_line
                else:
                    text = self.small_font.render(line, True, WHITE)
                    self.screen.blit(text, (panel_x + 10, y_offset))
                    line = word + " "
                    y_offset += 25
            if line:
                text = self.small_font.render(line, True, WHITE)
                self.screen.blit(text, (panel_x + 10, y_offset))

            # Buttons
            can_craft = self.can_craft_recipe(recipe_id)

            if self.mode == "basic":
                craft_color = GREEN if can_craft else LIGHT_GRAY
                pygame.draw.rect(self.screen, craft_color, (panel_x, 700, 350, 50))
                craft_text = self.font.render("CRAFT (Instant)", True, WHITE)
                self.screen.blit(craft_text, (panel_x + 70, 715))

            minigame_color = BLUE if (can_craft or self.mode == "manual") else LIGHT_GRAY
            pygame.draw.rect(self.screen, minigame_color, (panel_x, 760, 350, 50))
            minigame_text = self.font.render("START MINIGAME", True, WHITE)
            self.screen.blit(minigame_text, (panel_x + 70, 775))
        else:
            no_recipe = self.font.render("No recipe selected", True, LIGHT_GRAY)
            self.screen.blit(no_recipe, (panel_x + 70, panel_y + 200))

    def draw_minigame(self):
        """Draw minigame interface"""
        # Title
        recipe = self.recipes[self.selected_recipe]
        title = self.large_font.render(f"Smithing: {self.get_recipe_name(recipe)}", True, ORANGE)
        self.screen.blit(title, (500, 50))

        timer_text = self.large_font.render(f"{self.time_left}s", True, ORANGE)
        self.screen.blit(timer_text, (1200, 50))

        # Temperature bar
        temp_label = self.font.render("Temperature", True, WHITE)
        self.screen.blit(temp_label, (200, 150))

        temp_value = self.font.render(f"{int(self.temperature)}°", True,
                                      GREEN if self.TEMP_IDEAL_MIN <= self.temperature <= self.TEMP_IDEAL_MAX else RED)
        self.screen.blit(temp_value, (1100, 150))

        # Temperature bar background
        pygame.draw.rect(self.screen, DARK_GRAY, (200, 190, 900, 40))

        # Ideal zone
        ideal_start = 200 + int(900 * self.TEMP_IDEAL_MIN / 100)
        ideal_width = int(900 * (self.TEMP_IDEAL_MAX - self.TEMP_IDEAL_MIN) / 100)
        pygame.draw.rect(self.screen, (0, 100, 0), (ideal_start, 190, ideal_width, 40))

        # Current temp
        temp_width = int(900 * self.temperature / 100)
        pygame.draw.rect(self.screen, ORANGE, (200, 190, temp_width, 40))

        # Fan button
        pygame.draw.rect(self.screen, BLUE, (200, 250, 900, 50))
        fan_text = self.font.render("FAN FLAMES (Spacebar)", True, WHITE)
        self.screen.blit(fan_text, (500, 265))

        # Hammer bar
        hammer_label = self.font.render(f"Hammer Hits: {self.hammer_hits}/{self.REQUIRED_HITS}", True, WHITE)
        self.screen.blit(hammer_label, (200, 350))

        if self.hammer_scores:
            last_score = self.font.render(f"Last: {self.hammer_scores[-1]}", True, YELLOW)
            self.screen.blit(last_score, (900, 350))

        # Hammer bar background
        bar_x = 500
        bar_y = 390
        pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, self.HAMMER_BAR_WIDTH, 50))

        # Target zones
        center = self.HAMMER_BAR_WIDTH / 2
        pygame.draw.rect(self.screen, GREEN,
                         (bar_x + center - self.TARGET_WIDTH / 2, bar_y, self.TARGET_WIDTH, 50))
        pygame.draw.rect(self.screen, YELLOW,
                         (bar_x + center - self.PERFECT_WIDTH / 2, bar_y, self.PERFECT_WIDTH, 50))

        # Hammer indicator
        pygame.draw.rect(self.screen, WHITE,
                         (bar_x + self.hammer_position - 2, bar_y, 4, 50))

        # Hammer button
        pygame.draw.rect(self.screen, ORANGE, (500, 650, 400, 50))
        hammer_text = self.font.render("HAMMER!", True, WHITE)
        self.screen.blit(hammer_text, (650, 665))

        # Scores display
        if self.hammer_scores:
            x = 500
            for score in self.hammer_scores:
                color = YELLOW if score == 100 else (GREEN if score == 70 else GRAY)
                pygame.draw.rect(self.screen, color, (x, 720, 60, 40))
                score_text = self.font.render(str(score), True, WHITE)
                self.screen.blit(score_text, (x + 15, 730))
                x += 70

    def draw_result_screen(self):
        """Draw crafting result"""
        # Overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Result box
        pygame.draw.rect(self.screen, GRAY, (400, 250, 600, 400))

        result = self.crafting_result
        if result['success']:
            # Success
            success_text = self.large_font.render("SUCCESS!", True, GREEN)
            self.screen.blit(success_text, (600, 300))

            recipe = self.recipes[self.selected_recipe]
            crafted = self.font.render(f"Crafted: {self.get_recipe_name(recipe)}", True, WHITE)
            self.screen.blit(crafted, (520, 370))

            qty_text = self.font.render(f"Quantity: {recipe['outputQty']}", True, WHITE)
            self.screen.blit(qty_text, (590, 400))

            score_text = self.font.render(f"Score: {result['score']:.1f}", True, WHITE)
            self.screen.blit(score_text, (600, 440))

            bonus_text = self.font.render(result['bonus'], True, YELLOW)
            self.screen.blit(bonus_text, (520, 480))

            # Show it's been added to inventory
            inv_text = self.small_font.render("Added to Crafted Items inventory!", True, GREEN)
            self.screen.blit(inv_text, (530, 520))
        else:
            # Failure
            fail_text = self.large_font.render("FAILED!", True, RED)
            self.screen.blit(fail_text, (600, 350))

            msg_text = self.font.render(result['message'], True, WHITE)
            self.screen.blit(msg_text, (550, 420))

        # Continue button
        pygame.draw.rect(self.screen, BLUE, (600, 550, 200, 50))
        continue_text = self.font.render("Continue", True, WHITE)
        self.screen.blit(continue_text, (650, 565))

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()

            if self.minigame_active:
                self.update_minigame()

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    tester = SmithingTester()
    tester.run()