import pygame
import json
import sys
import math
from pathlib import Path
from collections import Counter

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 920
CELL_SIZE = 50
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
CYAN = (78, 205, 196)
KEY_RED = (255, 107, 107)

# Material colors
MATERIAL_COLORS = {
    "iron_ingot": (176, 176, 176),
    "crystal_quartz": (255, 255, 255),
    "light_gem": (255, 255, 224),
    "earth_crystal": (139, 69, 19),
    "iron_ore": (169, 169, 169),
    "granite": (128, 128, 128),
    "beetle_carapace": (85, 107, 47),
    "fire_crystal": (255, 69, 0),
    "air_crystal": (135, 206, 250),
    "water_crystal": (0, 191, 255),
    "slime_gel": (50, 205, 50),
    "lightning_shard": (255, 255, 0),
    "storm_heart": (75, 0, 130),
    "ash_plank": (160, 130, 109),
    "ironwood_plank": (105, 105, 105),
    "mithril_ingot": (192, 192, 192),
    "diamond": (185, 242, 255),
    "golem_core": (105, 105, 105),
    "orichalcum_ingot": (218, 165, 32),
    "void_essence": (75, 0, 130),
    "dire_fang": (245, 245, 220),
    "spectral_thread": (230, 230, 250)
}


class EnchantingTester:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Enchanting Station - Tester")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 36)

        # Load data
        self.recipes = self.load_recipes()
        self.placements = self.load_placements()
        self.materials_db = self.load_materials()

        # Shape templates (from enchanting designer)
        self.shape_templates = self.define_shape_templates()

        # Game state
        self.mode = "basic"  # "basic", "manual"
        self.selected_recipe = None
        self.current_vertices = {}  # {(x,y): {"materialId": str, "isKey": bool}}
        self.current_shapes = []  # [{"type": str, "vertices": [(x,y)...], "rotation": int}]
        self.selected_material = None
        self.last_selected_material = None
        self.recipe_scroll = 0
        self.material_scroll = 0
        self.grid_size = 8  # Changes based on recipe tier

        # Inventory (generous for testing)
        self.inventory = {
            "iron_ingot": 50,
            "crystal_quartz": 50,
            "light_gem": 50,
            "earth_crystal": 50,
            "iron_ore": 50,
            "granite": 50,
            "beetle_carapace": 50,
            "fire_crystal": 50,
            "air_crystal": 50,
            "water_crystal": 50,
            "slime_gel": 50,
            "lightning_shard": 50,
            "storm_heart": 50,
            "ash_plank": 50,
            "ironwood_plank": 50,
            "mithril_ingot": 50,
            "diamond": 50,
            "golem_core": 50,
            "orichalcum_ingot": 50,
            "void_essence": 50,
            "dire_fang": 50,
            "spectral_thread": 50
        }

        # Crafted items
        self.crafted_items = {}

        # Minigame state (placeholder - not implemented yet)
        self.minigame_active = False
        self.crafting_result = None

        self.running = True

    def define_shape_templates(self):
        """Shape templates from enchanting designer"""
        return {
            "triangle_equilateral_small": [
                (0, 0), (-1, -2), (1, -2)
            ],
            "square_small": [
                (0, 0), (2, 0), (2, -2), (0, -2)
            ],
            "triangle_isosceles_small": [
                (0, 0), (-1, -3), (1, -3)
            ],
            "triangle_equilateral_large": [
                (0, 0), (-2, -3), (2, -3)
            ],
            "square_large": [
                (0, 0), (4, 0), (4, -4), (0, -4)
            ],
            "triangle_isosceles_large": [
                (0, 0), (-1, -5), (1, -5)
            ]
        }

    def load_recipes(self):
        """Load recipes from JSON"""
        possible_paths = [
            "recipes-adornments-1.json",
            "recipes.JSON/recipes-adornments-1.json",
            "../recipes.JSON/recipes-adornments-1.json",
        ]

        recipes = {}
        for path in possible_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipe_list = data.get('recipes', [])
                    for recipe in recipe_list:
                        recipes[recipe['recipeId']] = recipe
                    print(f"Loaded {len(recipes)} recipes from {path}")
                    return recipes
            except FileNotFoundError:
                continue

        print("Could not find recipe JSON, using test data")
        return {
            "enchanting_sharpness_basic": {
                "recipeId": "enchanting_sharpness_basic",
                "enchantmentName": "Sharpness I",
                "outputId": "sharpness_1",
                "outputQty": 1,
                "stationTier": 1,
                "applicableTo": ["weapon"],
                "inputs": [
                    {"materialId": "fire_crystal", "quantity": 3},
                    {"materialId": "iron_ingot", "quantity": 2}
                ],
                "metadata": {
                    "narrative": "Basic sharpness enchantment."
                }
            }
        }

    def load_placements(self):
        """Load placement data from JSON"""
        possible_paths = [
            "placements-adornments-1.JSON",
            "placements.JSON/placements-adornments-1.JSON",
            "../placements.JSON/placements-adornments-1.JSON",
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

        print("Could not find placement JSON, using test data")
        return {
            "enchanting_sharpness_basic": {
                "gridType": "square_8x8",
                "vertices": {
                    "0,2": {"materialId": "fire_crystal", "isKey": True},
                    "1,1": {"materialId": "iron_ingot", "isKey": False},
                    "-1,1": {"materialId": "iron_ingot", "isKey": False}
                },
                "shapes": [
                    {
                        "type": "triangle_equilateral_small",
                        "vertices": ["0,2", "1,1", "-1,1"],
                        "rotation": 0
                    }
                ]
            }
        }

    def load_materials(self):
        """Create materials database"""
        return {
            "iron_ingot": {"name": "Iron Ingot", "tier": 1},
            "crystal_quartz": {"name": "Crystal Quartz", "tier": 1},
            "light_gem": {"name": "Light Gem", "tier": 1},
            "earth_crystal": {"name": "Earth Crystal", "tier": 1},
            "iron_ore": {"name": "Iron Ore", "tier": 1},
            "granite": {"name": "Granite", "tier": 1},
            "beetle_carapace": {"name": "Beetle Carapace", "tier": 1},
            "fire_crystal": {"name": "Fire Crystal", "tier": 1},
            "air_crystal": {"name": "Air Crystal", "tier": 1},
            "water_crystal": {"name": "Water Crystal", "tier": 1},
            "slime_gel": {"name": "Slime Gel", "tier": 1},
            "lightning_shard": {"name": "Lightning Shard", "tier": 2},
            "storm_heart": {"name": "Storm Heart", "tier": 2},
            "ash_plank": {"name": "Ash Plank", "tier": 1},
            "ironwood_plank": {"name": "Ironwood Plank", "tier": 2},
            "mithril_ingot": {"name": "Mithril Ingot", "tier": 3},
            "diamond": {"name": "Diamond", "tier": 3},
            "golem_core": {"name": "Golem Core", "tier": 3},
            "orichalcum_ingot": {"name": "Orichalcum Ingot", "tier": 3},
            "void_essence": {"name": "Void Essence", "tier": 3},
            "dire_fang": {"name": "Dire Fang", "tier": 2},
            "spectral_thread": {"name": "Spectral Thread", "tier": 2}
        }

    def get_grid_size_from_tier(self, tier):
        """Grid size based on tier (from enchanting designer)"""
        tier_to_size = {1: 8, 2: 10, 3: 12, 4: 14}
        return tier_to_size.get(tier, 8)

    def get_recipe_name(self, recipe):
        """Get recipe display name"""
        return recipe.get('enchantmentName', recipe.get('recipeId', 'Unknown'))

    def grid_to_screen(self, x, y):
        """Convert grid coordinates (centered) to screen coordinates"""
        grid_start_x = 400
        grid_start_y = 150
        half = self.grid_size // 2

        screen_x = grid_start_x + (x + half) * CELL_SIZE + CELL_SIZE // 2
        screen_y = grid_start_y + (half - y) * CELL_SIZE + CELL_SIZE // 2

        return screen_x, screen_y

    def screen_to_grid(self, screen_x, screen_y):
        """Convert screen coordinates to grid coordinates (centered)"""
        grid_start_x = 400
        grid_start_y = 150
        half = self.grid_size // 2

        x = round((screen_x - grid_start_x - CELL_SIZE // 2) / CELL_SIZE - half)
        y = round(half - (screen_y - grid_start_y - CELL_SIZE // 2) / CELL_SIZE)

        return x, y

    def parse_vertices_from_placement(self, placement):
        """Parse vertices dictionary from placement JSON"""
        vertices = {}
        vertex_dict = placement.get('vertices', {})

        for key, value in vertex_dict.items():
            if isinstance(key, str):
                x, y = map(int, key.split(','))
                vertices[(x, y)] = value
            else:
                vertices[key] = value

        return vertices

    def parse_shapes_from_placement(self, placement):
        """Parse shapes list from placement JSON"""
        shapes = []
        shape_list = placement.get('shapes', [])

        for shape in shape_list:
            vertices = []
            for v in shape['vertices']:
                if isinstance(v, str):
                    x, y = map(int, v.split(','))
                    vertices.append((x, y))
                else:
                    vertices.append(tuple(v))

            shapes.append({
                'type': shape['type'],
                'vertices': vertices,
                'rotation': shape.get('rotation', 0)
            })

        return shapes

    def auto_fill_pattern(self):
        """Auto-fill pattern for basic crafting mode"""
        if self.selected_recipe:
            placement = self.placements.get(self.selected_recipe, {})
            self.current_vertices = self.parse_vertices_from_placement(placement)
            self.current_shapes = self.parse_shapes_from_placement(placement)

    def detect_recipe(self):
        """Detect which recipe matches current pattern"""
        if not self.current_vertices or not self.current_shapes:
            return None

        for recipe_id, recipe in self.recipes.items():
            placement = self.placements.get(recipe_id, {})
            if not placement:
                continue

            expected_vertices = self.parse_vertices_from_placement(placement)
            expected_shapes = self.parse_shapes_from_placement(placement)

            # Check vertices match
            if set(self.current_vertices.keys()) != set(expected_vertices.keys()):
                continue

            vertices_match = all(
                self.current_vertices.get(k, {}).get('materialId') == v.get('materialId')
                for k, v in expected_vertices.items()
            )

            if not vertices_match:
                continue

            # Check shapes match
            if len(self.current_shapes) != len(expected_shapes):
                continue

            shapes_match = True
            for curr_shape in self.current_shapes:
                found = False
                for exp_shape in expected_shapes:
                    if (curr_shape['type'] == exp_shape['type'] and
                            set(curr_shape['vertices']) == set(exp_shape['vertices'])):
                        found = True
                        break
                if not found:
                    shapes_match = False
                    break

            if shapes_match:
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

        # Add crafted item
        output_id = recipe['outputId']
        output_qty = recipe.get('outputQty', 1)
        self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + output_qty

        print(f"Crafted {output_qty}x {output_id}")

        self.current_vertices = {}
        self.current_shapes = []
        self.selected_recipe = None

    def start_minigame(self):
        """Start minigame (PLACEHOLDER - not implemented yet)"""
        # NOTE: Minigame system will be integrated here later
        # For now, just do instant craft with bonus message
        if not self.selected_recipe:
            detected = self.detect_recipe()
            if detected:
                self.selected_recipe = detected

        if not self.selected_recipe or not self.can_craft_recipe(self.selected_recipe):
            return

        recipe = self.recipes[self.selected_recipe]

        # Deduct materials
        for inp in recipe['inputs']:
            self.inventory[inp['materialId']] -= inp['quantity']

        # Add crafted item
        output_id = recipe['outputId']
        output_qty = recipe.get('outputQty', 1)
        self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + output_qty

        self.crafting_result = {
            "success": True,
            "message": "Minigame not implemented yet - instant craft with base bonus",
            "bonus": "Base stats (minigame coming soon)"
        }

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.MOUSEWHEEL:
                if self.mode == "basic":
                    self.recipe_scroll = max(0, min(len(self.recipes) - 7, self.recipe_scroll - event.y))
                elif self.mode == "manual":
                    self.material_scroll = max(0, min(len(self.materials_db) - 10, self.material_scroll - event.y))

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.mode == "manual" and self.last_selected_material:
                        self.selected_material = self.last_selected_material
                elif event.key == pygame.K_1:
                    self.mode = "basic"
                    self.current_vertices = {}
                    self.current_shapes = []
                elif event.key == pygame.K_2:
                    self.mode = "manual"
                    self.current_vertices = {}
                    self.current_shapes = []
                    self.selected_recipe = None

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_click(event.pos)

    def handle_click(self, pos):
        """Handle mouse clicks"""
        x, y = pos

        # Mode buttons
        if 450 <= x <= 600 and 50 <= y <= 90:
            self.mode = "basic"
            self.current_vertices = {}
            self.current_shapes = []
        elif 620 <= x <= 770 and 50 <= y <= 90:
            self.mode = "manual"
            self.current_vertices = {}
            self.current_shapes = []
            self.selected_recipe = None

        # Recipe list (basic mode)
        if self.mode == "basic" and 50 <= x <= 350:
            recipe_y = 150
            recipe_list = list(self.recipes.keys())
            visible_recipes = recipe_list[self.recipe_scroll:self.recipe_scroll + 7]

            for i, recipe_id in enumerate(visible_recipes):
                if recipe_y <= y <= recipe_y + 60:
                    self.selected_recipe = recipe_id
                    recipe = self.recipes[recipe_id]
                    tier = recipe.get('stationTier', 1)
                    self.grid_size = self.get_grid_size_from_tier(tier)
                    self.auto_fill_pattern()
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

        # Grid clicks (vertex placement in manual mode)
        grid_x_start = 400
        grid_y_start = 150
        grid_pixel_size = self.grid_size * CELL_SIZE

        if grid_x_start <= x <= grid_x_start + grid_pixel_size:
            if grid_y_start <= y <= grid_y_start + grid_pixel_size:
                grid_x, grid_y = self.screen_to_grid(x, y)
                half = self.grid_size // 2

                if abs(grid_x) <= half and abs(grid_y) <= half:
                    self.handle_vertex_click(grid_x, grid_y)

        # Craft button
        if self.mode == "basic" and 1000 <= x <= 1350 and 700 <= y <= 750:
            if self.selected_recipe and self.can_craft_recipe(self.selected_recipe):
                self.handle_basic_craft()

        # Minigame button
        if 1000 <= x <= 1350 and 760 <= y <= 810:
            self.start_minigame()

        # Result continue button
        if self.crafting_result and 600 <= x <= 800 and 650 <= y <= 700:
            self.crafting_result = None
            self.mode = "basic"
            self.selected_recipe = None
            self.current_vertices = {}
            self.current_shapes = []

    def handle_vertex_click(self, x, y):
        """Handle vertex clicks in manual mode"""
        if self.mode != "manual":
            return

        coord = (x, y)

        if coord in self.current_vertices:
            if self.selected_material:
                # Assign material to vertex
                if self.inventory.get(self.selected_material, 0) > 0:
                    self.current_vertices[coord]['materialId'] = self.selected_material
                    self.last_selected_material = self.selected_material
                    self.selected_material = None
            else:
                # Clear material
                if self.current_vertices[coord].get('materialId'):
                    self.current_vertices[coord] = {'materialId': None, 'isKey': False}

    def draw(self):
        """Main draw function"""
        self.screen.fill(DARK_GRAY)

        if self.crafting_result:
            self.draw_result_screen()
        else:
            self.draw_main_ui()

        pygame.display.flip()

    def draw_main_ui(self):
        """Draw main UI"""
        # Title
        title = self.large_font.render("Enchanting Station - Tester", True, ORANGE)
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

        # Crafted items
        self.draw_crafted_inventory()

    def draw_recipe_list(self):
        """Draw recipe list"""
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
            for inp in recipe['inputs'][:2]:
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

        if len(self.recipes) > 7:
            scroll_text = self.small_font.render(
                f"Scroll: {self.recipe_scroll + 1}-{min(self.recipe_scroll + 7, len(self.recipes))} / {len(self.recipes)}",
                True, WHITE)
            self.screen.blit(scroll_text, (50, 120))

    def draw_material_palette(self):
        """Draw material palette"""
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

    def draw_grid(self):
        """Draw enchanting grid with pattern"""
        grid_x = 400
        grid_y = 150

        # Draw grid cells
        half = self.grid_size // 2
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                x = grid_x + col * CELL_SIZE
                y = grid_y + row * CELL_SIZE

                # Light background for all cells
                pygame.draw.rect(self.screen, (40, 40, 40), (x, y, CELL_SIZE - 2, CELL_SIZE - 2))
                pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, CELL_SIZE - 2, CELL_SIZE - 2), 1)

        # Draw center axes
        center_col = half * CELL_SIZE
        center_row = half * CELL_SIZE
        pygame.draw.line(self.screen, GRAY,
                         (grid_x + center_col, grid_y),
                         (grid_x + center_col, grid_y + self.grid_size * CELL_SIZE), 2)
        pygame.draw.line(self.screen, GRAY,
                         (grid_x, grid_y + center_row),
                         (grid_x + self.grid_size * CELL_SIZE, grid_y + center_row), 2)

        # Draw shape lines
        for shape in self.current_shapes:
            vertices = shape['vertices']
            for i in range(len(vertices)):
                v1 = vertices[i]
                v2 = vertices[(i + 1) % len(vertices)]

                x1, y1 = self.grid_to_screen(v1[0], v1[1])
                x2, y2 = self.grid_to_screen(v2[0], v2[1])

                pygame.draw.line(self.screen, BLUE, (x1, y1), (x2, y2), 3)

        # Draw vertices
        for (vx, vy), vertex_data in self.current_vertices.items():
            screen_x, screen_y = self.grid_to_screen(vx, vy)

            has_material = vertex_data.get('materialId')
            is_key = vertex_data.get('isKey', False)

            if has_material:
                color = KEY_RED if is_key else CYAN
                radius = 8

                # Draw vertex
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), radius)
                pygame.draw.circle(self.screen, BLACK, (screen_x, screen_y), radius, 2)

                # Draw material label
                mat_info = self.materials_db.get(has_material, {"name": has_material})
                name = mat_info['name'][:6]
                label = self.small_font.render(name, True, WHITE)
                self.screen.blit(label, (screen_x - 15, screen_y - 25))
            else:
                # Empty vertex
                color = YELLOW
                radius = 5
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), radius)
                pygame.draw.circle(self.screen, BLACK, (screen_x, screen_y), radius, 1)

        # Grid info
        info_text = self.small_font.render(
            f"{self.grid_size}x{self.grid_size} grid (centered coordinates)",
            True, WHITE
        )
        self.screen.blit(info_text, (grid_x, grid_y - 25))

        # Detection in manual mode
        if self.mode == "manual":
            detected = self.detect_recipe()
            if detected:
                det_recipe = self.recipes[detected]
                det_text = self.font.render(f"Detected: {self.get_recipe_name(det_recipe)}", True, GREEN)
                self.screen.blit(det_text, (grid_x, grid_y + self.grid_size * CELL_SIZE + 10))

    def draw_output_panel(self):
        """Draw output panel"""
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

            # Applies to
            applies_text = self.small_font.render(
                f"Applies to: {', '.join(recipe.get('applicableTo', ['any']))}",
                True, LIGHT_GRAY
            )
            self.screen.blit(applies_text, (panel_x + 10, panel_y + 50))

            # Narrative
            narrative = recipe.get('metadata', {}).get('narrative', 'No description')
            words = narrative.split()
            line = ""
            y_offset = panel_y + 80
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

            # Pattern info
            vertex_count = sum(1 for v in self.current_vertices.values() if v.get('materialId'))
            shape_count = len(self.current_shapes)

            info_y = panel_y + 200
            pattern_text = self.small_font.render(f"Pattern: {shape_count} shapes, {vertex_count} materials", True,
                                                  YELLOW)
            self.screen.blit(pattern_text, (panel_x + 10, info_y))

            # Buttons
            can_craft = self.can_craft_recipe(recipe_id)

            if self.mode == "basic":
                craft_color = GREEN if can_craft else LIGHT_GRAY
                pygame.draw.rect(self.screen, craft_color, (panel_x, 700, 350, 50))
                craft_text = self.font.render("CRAFT (Instant)", True, WHITE)
                self.screen.blit(craft_text, (panel_x + 70, 715))

            minigame_color = BLUE if can_craft else LIGHT_GRAY
            pygame.draw.rect(self.screen, minigame_color, (panel_x, 760, 350, 50))
            minigame_text = self.font.render("MINIGAME (TODO)", True, WHITE)
            self.screen.blit(minigame_text, (panel_x + 70, 775))
        else:
            no_recipe = self.font.render("No recipe selected", True, LIGHT_GRAY)
            self.screen.blit(no_recipe, (panel_x + 70, panel_y + 200))

    def draw_crafted_inventory(self):
        """Draw crafted items"""
        panel_x = 50
        panel_y = 700
        panel_width = 900
        panel_height = 180

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 3)

        title = self.font.render("Crafted Enchantments", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        if not self.crafted_items:
            empty_text = self.small_font.render("No enchantments crafted yet!", True, LIGHT_GRAY)
            self.screen.blit(empty_text, (panel_x + 300, panel_y + 80))
            return

        item_x = panel_x + 20
        item_y = panel_y + 45
        items_per_row = 8
        item_spacing = 110

        for i, (item_id, quantity) in enumerate(self.crafted_items.items()):
            if i >= 16:
                break

            col = i % items_per_row
            row = i // items_per_row

            x = item_x + col * item_spacing
            y = item_y + row * 65

            pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, 100, 55))
            pygame.draw.rect(self.screen, WHITE, (x, y, 100, 55), 2)

            item_name = item_id.replace('_', ' ').title()
            if len(item_name) > 12:
                item_name = item_name[:10] + ".."

            name_text = self.small_font.render(item_name, True, WHITE)
            self.screen.blit(name_text, (x + 5, y + 5))

            qty_text = self.font.render(f"x{quantity}", True, GREEN)
            self.screen.blit(qty_text, (x + 5, y + 28))

    def draw_result_screen(self):
        """Draw crafting result"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, GRAY, (400, 250, 600, 400))

        result = self.crafting_result
        if result['success']:
            success_text = self.large_font.render("SUCCESS!", True, GREEN)
            self.screen.blit(success_text, (600, 300))

            if self.selected_recipe:
                recipe = self.recipes[self.selected_recipe]
                crafted = self.font.render(f"Crafted: {self.get_recipe_name(recipe)}", True, WHITE)
                self.screen.blit(crafted, (480, 370))

            msg_text = self.small_font.render(result['message'], True, YELLOW)
            self.screen.blit(msg_text, (450, 420))

            bonus_text = self.font.render(result['bonus'], True, YELLOW)
            self.screen.blit(bonus_text, (500, 460))
        else:
            fail_text = self.large_font.render("FAILED!", True, RED)
            self.screen.blit(fail_text, (600, 350))

        pygame.draw.rect(self.screen, BLUE, (600, 550, 200, 50))
        continue_text = self.font.render("Continue", True, WHITE)
        self.screen.blit(continue_text, (650, 565))

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    tester = EnchantingTester()
    tester.run()