"""
Unified Crafting Simulator

Tests all 5 crafting subdisciplines:
1. Smithing (temperature + hammering)
2. Refining (lockpicking-style cylinder alignment)
3. Alchemy (reaction chain management)
4. Engineering (cognitive puzzles)
5. Enchanting (freeform pattern creation)

Features:
- Switch between disciplines
- Test minigames with simulated inventory
- Material limitations
- Recipe browsing
- Result tracking
"""

import pygame
import sys
from pathlib import Path

# Import all crafting subdisciplines
from smithing import SmithingCrafter
from refining import RefiningCrafter
from alchemy import AlchemyCrafter
from engineering import EngineeringCrafter
from enchanting import EnchantingCrafter

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 900
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
PURPLE = (180, 100, 255)
CYAN = (78, 205, 196)

# Material colors (expanded)
MATERIAL_COLORS = {
    "iron_ingot": (176, 176, 176),
    "copper_ingot": (184, 115, 51),
    "steel_ingot": (119, 136, 153),
    "mithril_ingot": (192, 192, 192),
    "oak_plank": (139, 69, 19),
    "ash_plank": (160, 130, 109),
    "maple_plank": (210, 105, 30),
    "ironwood_plank": (105, 105, 105),
    "fire_crystal": (255, 69, 0),
    "water_crystal": (0, 191, 255),
    "earth_crystal": (139, 69, 19),
    "air_crystal": (135, 206, 250),
    "lightning_shard": (255, 255, 0),
    "wolf_pelt": (169, 169, 169),
    "beetle_carapace": (85, 107, 47),
    "slime_gel": (50, 205, 50),
    "granite": (128, 128, 128),
    "leather_strip": (139, 90, 43),
    "spectral_thread": (230, 230, 250),
    "golem_core": (105, 105, 105),
    "dragon_scale": (220, 20, 60),
    "void_essence": (75, 0, 130),
    "healing_herb": (50, 205, 50),
    "fire_flower": (255, 99, 71),
    "dragon_blood": (139, 0, 0),
}


class CraftingSimulator:
    """Unified crafting simulator for all subdisciplines"""

    def __init__(self):
        """Initialize the simulator"""
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Crafting Subdisciplines - Unified Simulator")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 36)
        self.title_font = pygame.font.Font(None, 48)

        # Initialize all crafters
        print("Initializing crafting systems...")
        self.smithing = SmithingCrafter()
        self.refining = RefiningCrafter()
        self.alchemy = AlchemyCrafter()
        self.engineering = EngineeringCrafter()
        self.enchanting = EnchantingCrafter()

        # Current discipline
        self.current_discipline = "smithing"  # smithing, refining, alchemy, engineering, enchanting
        self.disciplines = {
            "smithing": self.smithing,
            "refining": self.refining,
            "alchemy": self.alchemy,
            "engineering": self.engineering,
            "enchanting": self.enchanting
        }

        # Simulated inventory (generous for testing)
        self.inventory = self._create_test_inventory()

        # Crafted items inventory
        self.crafted_items = {}

        # UI state
        self.selected_recipe = None
        self.recipe_scroll = 0
        self.current_minigame = None
        self.minigame_result = None

        # Running state
        self.running = True

    def _create_test_inventory(self):
        """Create test inventory with generous amounts"""
        materials = [
            "iron_ingot", "copper_ingot", "steel_ingot", "mithril_ingot",
            "oak_plank", "ash_plank", "maple_plank", "ironwood_plank",
            "fire_crystal", "water_crystal", "earth_crystal", "air_crystal",
            "lightning_shard", "wolf_pelt", "beetle_carapace", "slime_gel",
            "granite", "leather_strip", "spectral_thread", "golem_core",
            "dragon_scale", "void_essence", "healing_herb", "fire_flower",
            "dragon_blood", "iron_ore", "pine_log", "ash_log", "oak_log",
            "birch_plank", "ebony_plank", "dire_fang", "crystal_quartz",
            "light_gem", "storm_heart", "diamond", "orichalcum_ingot"
        ]

        return {mat: 100 for mat in materials}

    def get_current_crafter(self):
        """Get current discipline's crafter"""
        return self.disciplines[self.current_discipline]

    def get_current_recipes(self):
        """Get recipes for current discipline"""
        return self.get_current_crafter().get_all_recipes()

    def switch_discipline(self, discipline):
        """Switch to different discipline"""
        if discipline in self.disciplines:
            self.current_discipline = discipline
            self.selected_recipe = None
            self.recipe_scroll = 0
            self.current_minigame = None
            self.minigame_result = None

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.current_minigame:
                        # Exit minigame
                        self.current_minigame = None
                        self.minigame_result = None
                    else:
                        self.running = False

                # Number keys to switch disciplines
                elif event.key == pygame.K_1:
                    self.switch_discipline("smithing")
                elif event.key == pygame.K_2:
                    self.switch_discipline("refining")
                elif event.key == pygame.K_3:
                    self.switch_discipline("alchemy")
                elif event.key == pygame.K_4:
                    self.switch_discipline("engineering")
                elif event.key == pygame.K_5:
                    self.switch_discipline("enchanting")

                # Minigame controls
                elif event.key == pygame.K_SPACE:
                    if self.current_minigame and self.current_discipline == "smithing":
                        self.current_minigame.handle_fan()
                    elif self.current_minigame and self.current_discipline == "refining":
                        self.current_minigame.handle_attempt()
                    elif self.current_minigame and self.current_discipline == "alchemy":
                        self.current_minigame.chain()

            elif event.type == pygame.MOUSEWHEEL:
                # Scroll recipes
                recipes = list(self.get_current_recipes().keys())
                max_scroll = max(0, len(recipes) - 10)
                self.recipe_scroll = max(0, min(max_scroll, self.recipe_scroll - event.y))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_click(event.pos)

    def handle_click(self, pos):
        """Handle mouse clicks"""
        x, y = pos

        # Discipline tabs
        tab_y = 50
        tab_height = 50
        tab_width = 200
        disciplines_order = ["smithing", "refining", "alchemy", "engineering", "enchanting"]

        for i, disc in enumerate(disciplines_order):
            tab_x = 50 + i * (tab_width + 10)
            if tab_x <= x <= tab_x + tab_width and tab_y <= y <= tab_y + tab_height:
                self.switch_discipline(disc)
                return

        # Recipe list
        if 50 <= x <= 400 and 150 <= y <= 750:
            recipes = list(self.get_current_recipes().items())
            visible_recipes = recipes[self.recipe_scroll:self.recipe_scroll + 10]

            recipe_y = 150
            for recipe_id, recipe in visible_recipes:
                if recipe_y <= y <= recipe_y + 55:
                    self.selected_recipe = recipe_id
                    return
                recipe_y += 60

        # Craft buttons
        if self.selected_recipe:
            crafter = self.get_current_crafter()

            # Instant craft button (if allowed)
            if 1000 <= x <= 1500 and 700 <= y <= 750:
                if self.current_discipline != "enchanting":  # Enchanting requires minigame
                    result = crafter.craft_instant(self.selected_recipe, self.inventory)
                    if result.get('success'):
                        output_id = result['outputId']
                        qty = result['quantity']
                        self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + qty
                        print(f"Crafted {qty}x {output_id}")

            # Minigame button
            if 1000 <= x <= 1500 and 760 <= y <= 810:
                if crafter.can_craft(self.selected_recipe, self.inventory):
                    self.start_minigame()

        # Minigame-specific clicks
        if self.current_minigame:
            self.handle_minigame_click(pos)

    def start_minigame(self):
        """Start minigame for selected recipe"""
        crafter = self.get_current_crafter()
        self.current_minigame = crafter.create_minigame(self.selected_recipe)

        if self.current_minigame:
            self.current_minigame.start()
            self.minigame_result = None

    def handle_minigame_click(self, pos):
        """Handle clicks within minigame"""
        x, y = pos

        if self.current_discipline == "smithing":
            # Hammer button
            if 500 <= x <= 900 and 650 <= y <= 700:
                self.current_minigame.handle_hammer()

        # Result continue button
        if self.minigame_result and 600 <= x <= 900 and 750 <= y <= 800:
            # Process result
            crafter = self.get_current_crafter()
            result = crafter.craft_with_minigame(
                self.selected_recipe,
                self.inventory,
                self.minigame_result
            )

            if result.get('success'):
                output_id = result.get('outputId')
                qty = result.get('quantity', 1)
                if output_id:
                    self.crafted_items[output_id] = self.crafted_items.get(output_id, 0) + qty
                print(f"Crafted {qty}x {output_id} via minigame")

            # Clear minigame
            self.current_minigame = None
            self.minigame_result = None
            self.selected_recipe = None

    def update(self):
        """Update game state"""
        dt = self.clock.get_time() / 1000.0  # Convert to seconds

        # Update active minigame
        if self.current_minigame and hasattr(self.current_minigame, 'update'):
            self.current_minigame.update(dt)

            # Check for completion
            if hasattr(self.current_minigame, 'result') and self.current_minigame.result:
                self.minigame_result = self.current_minigame.result

    def draw(self):
        """Main draw function"""
        self.screen.fill(DARK_GRAY)

        if self.current_minigame and not self.minigame_result:
            self.draw_minigame()
        elif self.minigame_result:
            self.draw_minigame_result()
        else:
            self.draw_main_ui()

        pygame.display.flip()

    def draw_main_ui(self):
        """Draw main UI"""
        # Title
        title = self.title_font.render("Crafting Subdisciplines Simulator", True, ORANGE)
        self.screen.blit(title, (400, 10))

        # Discipline tabs
        self.draw_discipline_tabs()

        # Recipe list
        self.draw_recipe_list()

        # Recipe details / craft buttons
        self.draw_recipe_panel()

        # Inventory display
        self.draw_inventory_preview()

        # Crafted items
        self.draw_crafted_items()

    def draw_discipline_tabs(self):
        """Draw discipline selection tabs"""
        tab_y = 50
        tab_height = 50
        tab_width = 200
        disciplines = [
            ("smithing", "1. Smithing", ORANGE),
            ("refining", "2. Refining", CYAN),
            ("alchemy", "3. Alchemy", GREEN),
            ("engineering", "4. Engineering", BLUE),
            ("enchanting", "5. Enchanting", PURPLE)
        ]

        for i, (disc_id, disc_name, color) in enumerate(disciplines):
            tab_x = 50 + i * (tab_width + 10)
            is_active = disc_id == self.current_discipline

            # Draw tab
            tab_color = color if is_active else GRAY
            pygame.draw.rect(self.screen, tab_color, (tab_x, tab_y, tab_width, tab_height))
            pygame.draw.rect(self.screen, WHITE, (tab_x, tab_y, tab_width, tab_height), 2)

            # Draw text
            text = self.font.render(disc_name, True, WHITE)
            text_rect = text.get_rect(center=(tab_x + tab_width // 2, tab_y + tab_height // 2))
            self.screen.blit(text, text_rect)

    def draw_recipe_list(self):
        """Draw recipe list for current discipline"""
        panel_x = 50
        panel_y = 120
        panel_width = 350
        panel_height = 650

        # Background
        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 3)

        # Title
        title = self.font.render(f"{self.current_discipline.title()} Recipes", True, WHITE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        # Recipes
        recipes = list(self.get_current_recipes().items())
        if not recipes:
            no_recipes = self.font.render("No recipes loaded", True, LIGHT_GRAY)
            self.screen.blit(no_recipes, (panel_x + 80, panel_y + 300))
            return

        visible_recipes = recipes[self.recipe_scroll:self.recipe_scroll + 10]
        recipe_y = panel_y + 50

        for recipe_id, recipe in visible_recipes:
            is_selected = recipe_id == self.selected_recipe
            crafter = self.get_current_crafter()
            can_craft = crafter.can_craft(recipe_id, self.inventory)

            # Recipe box
            box_color = ORANGE if is_selected else (GREEN if can_craft else LIGHT_GRAY)
            pygame.draw.rect(self.screen, box_color, (panel_x + 10, recipe_y, panel_width - 20, 55))

            # Recipe name
            recipe_name = recipe.get('name', recipe_id.replace('_', ' ').title())
            if len(recipe_name) > 30:
                recipe_name = recipe_name[:28] + "..."

            name_text = self.small_font.render(recipe_name, True, WHITE)
            self.screen.blit(name_text, (panel_x + 20, recipe_y + 5))

            # Tier
            tier = recipe.get('stationTier', 1)
            tier_text = self.small_font.render(f"T{tier}", True, YELLOW)
            self.screen.blit(tier_text, (panel_x + 300, recipe_y + 5))

            # Material count
            mat_count = len(recipe.get('inputs', []))
            mat_text = self.small_font.render(f"{mat_count} mats", True, WHITE)
            self.screen.blit(mat_text, (panel_x + 20, recipe_y + 30))

            recipe_y += 60

        # Scroll indicator
        if len(recipes) > 10:
            scroll_text = self.small_font.render(
                f"{self.recipe_scroll + 1}-{min(self.recipe_scroll + 10, len(recipes))} / {len(recipes)}",
                True, WHITE
            )
            self.screen.blit(scroll_text, (panel_x + 250, panel_y + 15))

    def draw_recipe_panel(self):
        """Draw recipe details and craft buttons"""
        panel_x = 450
        panel_y = 120
        panel_width = 500
        panel_height = 700

        # Background
        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 3)

        if not self.selected_recipe:
            no_selection = self.font.render("Select a recipe", True, LIGHT_GRAY)
            self.screen.blit(no_selection, (panel_x + 150, panel_y + 300))
            return

        recipe = self.get_current_crafter().get_recipe(self.selected_recipe)
        if not recipe:
            return

        # Recipe name
        recipe_name = recipe.get('name', self.selected_recipe)
        name_text = self.large_font.render(recipe_name, True, WHITE)
        self.screen.blit(name_text, (panel_x + 20, panel_y + 20))

        # Tier and output
        tier = recipe.get('stationTier', 1)
        output = recipe.get('outputId', 'unknown')
        info_text = self.font.render(f"Tier {tier} | Output: {output}", True, CYAN)
        self.screen.blit(info_text, (panel_x + 20, panel_y + 70))

        # Materials required
        mat_y = panel_y + 110
        materials_title = self.font.render("Materials Required:", True, YELLOW)
        self.screen.blit(materials_title, (panel_x + 20, mat_y))
        mat_y += 35

        for inp in recipe.get('inputs', []):
            mat_id = inp['materialId']
            qty = inp['quantity']
            has = self.inventory.get(mat_id, 0)

            mat_color = GREEN if has >= qty else RED
            mat_text = self.small_font.render(f"• {mat_id}: {has}/{qty}", True, mat_color)
            self.screen.blit(mat_text, (panel_x + 30, mat_y))
            mat_y += 25

        # Craft buttons
        crafter = self.get_current_crafter()
        can_craft = crafter.can_craft(self.selected_recipe, self.inventory)

        # Instant craft button (if available)
        if self.current_discipline != "enchanting":
            instant_color = GREEN if can_craft else LIGHT_GRAY
            pygame.draw.rect(self.screen, instant_color, (panel_x + 20, panel_y + 600, panel_width - 40, 45))
            instant_text = self.font.render("INSTANT CRAFT (Base Stats)", True, WHITE)
            self.screen.blit(instant_text, (panel_x + 100, panel_y + 615))
        else:
            # Enchanting requires minigame
            info_text = self.small_font.render("Enchanting requires minigame - no instant craft", True, YELLOW)
            self.screen.blit(info_text, (panel_x + 60, panel_y + 615))

        # Minigame button
        minigame_color = BLUE if can_craft else LIGHT_GRAY
        pygame.draw.rect(self.screen, minigame_color, (panel_x + 20, panel_y + 655, panel_width - 40, 45))
        minigame_text = self.font.render("START MINIGAME", True, WHITE)
        self.screen.blit(minigame_text, (panel_x + 150, panel_y + 670))

    def draw_inventory_preview(self):
        """Draw small inventory preview"""
        panel_x = 1000
        panel_y = 120
        panel_width = 550
        panel_height = 200

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 2)

        title = self.font.render("Inventory Preview (Testing)", True, CYAN)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        # Show some materials
        mat_x = panel_x + 20
        mat_y = panel_y + 50
        count = 0
        for mat_id, qty in list(self.inventory.items())[:20]:
            if qty > 0:
                mat_text = self.small_font.render(f"{mat_id}: {qty}", True, WHITE)
                self.screen.blit(mat_text, (mat_x, mat_y))
                count += 1
                if count % 2 == 0:
                    mat_x = panel_x + 20
                    mat_y += 25
                else:
                    mat_x = panel_x + 290

    def draw_crafted_items(self):
        """Draw crafted items inventory"""
        panel_x = 1000
        panel_y = 350
        panel_width = 550
        panel_height = 470

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 3)

        title = self.font.render("Crafted Items", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        if not self.crafted_items:
            empty_text = self.small_font.render("No items crafted yet", True, LIGHT_GRAY)
            self.screen.blit(empty_text, (panel_x + 200, panel_y + 200))
            return

        # Display crafted items
        item_y = panel_y + 50
        for item_id, qty in list(self.crafted_items.items())[:15]:
            item_text = self.font.render(f"{item_id}: x{qty}", True, GREEN)
            self.screen.blit(item_text, (panel_x + 20, item_y))
            item_y += 30

    def draw_minigame(self):
        """Draw active minigame (simplified for now)"""
        # Title
        title = self.large_font.render(f"{self.current_discipline.title()} Minigame", True, ORANGE)
        self.screen.blit(title, (600, 50))

        # Instructions
        instructions = [
            "Smithing: Spacebar to fan, click HAMMER to strike",
            "Refining: Spacebar when cylinder aligns",
            "Alchemy: Spacebar to CHAIN or STABILIZE",
            "Engineering: Click to rotate/interact",
            "Enchanting: Click to place materials, draw connections"
        ]

        inst_index = ["smithing", "refining", "alchemy", "engineering", "enchanting"].index(self.current_discipline)
        inst_text = self.font.render(instructions[inst_index], True, CYAN)
        self.screen.blit(inst_text, (300, 100))

        # Draw discipline-specific minigame
        if self.current_discipline == "smithing":
            self.draw_smithing_minigame()
        elif self.current_discipline == "refining":
            self.draw_refining_minigame()
        elif self.current_discipline == "alchemy":
            self.draw_alchemy_minigame()
        elif self.current_discipline == "engineering":
            self.draw_engineering_minigame()
        elif self.current_discipline == "enchanting":
            self.draw_enchanting_minigame()

        # ESC to exit
        esc_text = self.small_font.render("Press ESC to exit minigame", True, LIGHT_GRAY)
        self.screen.blit(esc_text, (650, 850))

    def draw_smithing_minigame(self):
        """Draw smithing minigame UI"""
        state = self.current_minigame.get_state()

        # Temperature bar
        temp_label = self.font.render("Temperature", True, WHITE)
        self.screen.blit(temp_label, (200, 200))

        temp = state['temperature']
        temp_value = self.font.render(f"{int(temp)}°", True, GREEN if state['temp_ideal_min'] <= temp <= state['temp_ideal_max'] else RED)
        self.screen.blit(temp_value, (1200, 200))

        # Temperature bar
        pygame.draw.rect(self.screen, DARK_GRAY, (200, 240, 1000, 40))
        ideal_start = 200 + int(1000 * state['temp_ideal_min'] / 100)
        ideal_width = int(1000 * (state['temp_ideal_max'] - state['temp_ideal_min']) / 100)
        pygame.draw.rect(self.screen, (0, 100, 0), (ideal_start, 240, ideal_width, 40))
        temp_width = int(1000 * temp / 100)
        pygame.draw.rect(self.screen, ORANGE, (200, 240, temp_width, 40))

        # Fan button
        pygame.draw.rect(self.screen, BLUE, (200, 300, 1000, 50))
        fan_text = self.font.render("FAN FLAMES (Spacebar)", True, WHITE)
        self.screen.blit(fan_text, (550, 315))

        # Hammer
        hammer_label = self.font.render(f"Hammer Hits: {state['hammer_hits']}/{state['required_hits']}", True, WHITE)
        self.screen.blit(hammer_label, (200, 400))

        # Hammer bar
        bar_x = 400
        bar_y = 440
        bar_width = state['hammer_bar_width']

        pygame.draw.rect(self.screen, DARK_GRAY, (bar_x, bar_y, bar_width, 50))

        # Target zones
        center = bar_width / 2
        pygame.draw.rect(self.screen, GREEN, (bar_x + center - state['target_width'] / 2, bar_y, state['target_width'], 50))
        pygame.draw.rect(self.screen, YELLOW, (bar_x + center - state['perfect_width'] / 2, bar_y, state['perfect_width'], 50))

        # Hammer indicator
        pygame.draw.rect(self.screen, WHITE, (bar_x + state['hammer_position'] - 2, bar_y, 4, 50))

        # Hammer button
        pygame.draw.rect(self.screen, ORANGE, (500, 650, 400, 50))
        hammer_text = self.font.render("HAMMER!", True, WHITE)
        self.screen.blit(hammer_text, (650, 665))

    def draw_refining_minigame(self):
        """Draw refining minigame UI (simplified)"""
        state = self.current_minigame.get_state()

        # Progress
        progress_text = self.large_font.render(
            f"Cylinders: {state['aligned_count']}/{state['total_cylinders']}",
            True, CYAN
        )
        self.screen.blit(progress_text, (600, 200))

        # Time
        time_text = self.font.render(f"Time: {state['time_left']:.1f}s", True, YELLOW)
        self.screen.blit(time_text, (700, 250))

        # Failures
        fail_text = self.font.render(
            f"Failures: {state['failed_attempts']}/{state['allowed_failures']}",
            True, RED if state['failed_attempts'] > 0 else GREEN
        )
        self.screen.blit(fail_text, (700, 280))

        # Simplified cylinder visualization
        if state['current_cylinder'] < len(state['cylinders']):
            current = state['cylinders'][state['current_cylinder']]

            # Draw rotating indicator
            center_x, center_y = 800, 500
            radius = 150

            # Draw circle
            pygame.draw.circle(self.screen, GRAY, (center_x, center_y), radius, 3)

            # Draw target zone (top)
            pygame.draw.arc(self.screen, GREEN, (center_x - radius, center_y - radius, radius * 2, radius * 2),
                            math.radians(-10), math.radians(10), 10)

            # Draw current position
            import math
            angle_rad = math.radians(current['angle'])
            indicator_x = center_x + int(radius * math.sin(angle_rad))
            indicator_y = center_y - int(radius * math.cos(angle_rad))
            pygame.draw.circle(self.screen, ORANGE, (indicator_x, indicator_y), 15)

        # Press space to align
        prompt = self.large_font.render("Press SPACE to align!", True, YELLOW)
        self.screen.blit(prompt, (600, 700))

    def draw_alchemy_minigame(self):
        """Draw alchemy minigame UI (simplified)"""
        state = self.current_minigame.get_state()

        # Progress
        progress_text = self.large_font.render(
            f"Ingredient: {state['current_ingredient_index'] + 1}/{state['total_ingredients']}",
            True, CYAN
        )
        self.screen.blit(progress_text, (550, 200))

        # Total progress
        total_prog = state['total_progress']
        prog_text = self.font.render(f"Total Progress: {total_prog:.0%}", True, GREEN)
        self.screen.blit(prog_text, (650, 250))

        # Time
        time_text = self.font.render(f"Time: {state['time_left']:.1f}s", True, YELLOW)
        self.screen.blit(time_text, (700, 280))

        # Current reaction visualization
        if state['current_reaction']:
            reaction = state['current_reaction']

            # Simple bubble visualization
            bubble_x, bubble_y = 800, 500
            bubble_size = int(100 * reaction['size'])
            bubble_glow = int(255 * reaction['glow'])

            color = (bubble_glow, bubble_glow // 2, 0)
            pygame.draw.circle(self.screen, color, (bubble_x, bubble_y), bubble_size)

            # Stage indicator
            stage_text = self.large_font.render(f"Stage {reaction['stage']}/5", True, WHITE)
            self.screen.blit(stage_text, (700, 350))

            # Quality indicator
            quality_text = self.font.render(f"Current Quality: {reaction['quality']:.0%}", True, YELLOW)
            self.screen.blit(quality_text, (680, 390))

        # Controls
        chain_text = self.large_font.render("SPACE: Chain Next", True, BLUE)
        self.screen.blit(chain_text, (600, 700))

    def draw_engineering_minigame(self):
        """Draw engineering minigame UI (placeholder)"""
        state = self.current_minigame.get_state()

        # Progress
        progress_text = self.large_font.render(
            f"Puzzle: {state['current_puzzle_index'] + 1}/{state['total_puzzles']}",
            True, CYAN
        )
        self.screen.blit(progress_text, (600, 200))

        # Placeholder message
        msg = self.font.render("Engineering puzzles are placeholders", True, YELLOW)
        self.screen.blit(msg, (550, 400))

        msg2 = self.font.render("Rotation pipe puzzle would appear here", True, LIGHT_GRAY)
        self.screen.blit(msg2, (520, 440))

    def draw_enchanting_minigame(self):
        """Draw enchanting minigame UI (placeholder)"""
        state = self.current_minigame.get_state()

        # Phase
        phase_text = self.large_font.render(f"Phase: {state['phase']}/2", True, CYAN)
        self.screen.blit(phase_text, (700, 200))

        # Placeholder message
        if state['phase'] == 1:
            msg = self.font.render("Phase 1: Place materials in circular workspace", True, YELLOW)
        else:
            msg = self.font.render("Phase 2: Draw connections between materials", True, YELLOW)

        self.screen.blit(msg, (500, 400))

    def draw_minigame_result(self):
        """Draw minigame result screen"""
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Result box
        box_width, box_height = 600, 400
        box_x = (SCREEN_WIDTH - box_width) // 2
        box_y = (SCREEN_HEIGHT - box_height) // 2

        pygame.draw.rect(self.screen, GRAY, (box_x, box_y, box_width, box_height))
        pygame.draw.rect(self.screen, WHITE, (box_x, box_y, box_width, box_height), 3)

        # Success or failure
        if self.minigame_result.get('success'):
            status_text = self.title_font.render("SUCCESS!", True, GREEN)
        else:
            status_text = self.title_font.render("FAILED", True, RED)

        status_rect = status_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 60))
        self.screen.blit(status_text, status_rect)

        # Message
        message = self.minigame_result.get('message', 'Crafting complete')
        msg_text = self.font.render(message, True, WHITE)
        msg_rect = msg_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 150))
        self.screen.blit(msg_text, msg_rect)

        # Additional details based on discipline
        detail_y = box_y + 200
        if 'score' in self.minigame_result:
            score_text = self.font.render(f"Score: {self.minigame_result['score']:.1f}", True, CYAN)
            score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
            self.screen.blit(score_text, score_rect)
            detail_y += 35

        if 'bonus' in self.minigame_result:
            bonus_text = self.font.render(f"Bonus: +{self.minigame_result['bonus']}%", True, YELLOW)
            bonus_rect = bonus_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
            self.screen.blit(bonus_text, bonus_rect)

        # Continue button
        button_width, button_height = 200, 50
        button_x = (SCREEN_WIDTH - button_width) // 2
        button_y = box_y + box_height - 80

        pygame.draw.rect(self.screen, BLUE, (button_x, button_y, button_width, button_height))
        continue_text = self.font.render("Continue", True, WHITE)
        continue_rect = continue_text.get_rect(center=(button_x + button_width // 2, button_y + button_height // 2))
        self.screen.blit(continue_text, continue_rect)

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    import math  # Needed for refining visualization
    simulator = CraftingSimulator()
    simulator.run()
