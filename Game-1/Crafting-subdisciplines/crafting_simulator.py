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
- Tier filtering (T1/T2/T3/T4)
"""

import pygame
import sys
import json
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
    "orichalcum_ingot": (218, 165, 32),
    "dragonsteel_ingot": (139, 0, 0),
    "voidsteel_ingot": (75, 0, 130),
    "oak_plank": (139, 69, 19),
    "pine_plank": (139, 90, 43),
    "ash_plank": (160, 130, 109),
    "maple_plank": (210, 105, 30),
    "birch_plank": (222, 184, 135),
    "ironwood_plank": (105, 105, 105),
    "ebony_plank": (60, 60, 60),
    "fire_crystal": (255, 69, 0),
    "water_crystal": (0, 191, 255),
    "earth_crystal": (139, 69, 19),
    "air_crystal": (135, 206, 250),
    "ice_crystal": (175, 238, 238),
    "lightning_shard": (255, 255, 0),
    "lightning_core": (255, 215, 0),
    "storm_heart": (75, 0, 130),
    "wolf_pelt": (169, 169, 169),
    "dire_fang": (245, 245, 220),
    "beetle_carapace": (85, 107, 47),
    "slime_gel": (50, 205, 50),
    "granite": (128, 128, 128),
    "marble": (245, 245, 245),
    "obsidian": (0, 0, 0),
    "leather_strip": (139, 90, 43),
    "spectral_thread": (230, 230, 250),
    "golem_core": (105, 105, 105),
    "dragon_scale": (220, 20, 60),
    "void_essence": (75, 0, 130),
    "healing_herb": (50, 205, 50),
    "fire_flower": (255, 99, 71),
    "dragon_blood": (139, 0, 0),
    "phoenix_ash": (255, 140, 0),
    "crystal_quartz": (255, 255, 255),
    "light_gem": (255, 255, 224),
    "diamond": (185, 242, 255),
    "iron_ore": (169, 169, 169),
    "copper_ore": (184, 115, 51),
    "tin_ore": (211, 211, 211),
    "pine_log": (139, 90, 43),
    "oak_log": (101, 67, 33),
    "ash_log": (120, 100, 80),
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

        # Load item metadata database
        print("Loading item metadata...")
        self.item_metadata = self._load_item_metadata()

        # Initialize all crafters
        print("Initializing crafting systems...")
        self.smithing = SmithingCrafter()
        self.refining = RefiningCrafter()
        self.alchemy = AlchemyCrafter()
        self.engineering = EngineeringCrafter()
        self.enchanting = EnchantingCrafter()

        # Current discipline
        self.current_discipline = "smithing"
        self.disciplines = {
            "smithing": self.smithing,
            "refining": self.refining,
            "alchemy": self.alchemy,
            "engineering": self.engineering,
            "enchanting": self.enchanting
        }

        # Tier filter (0 = all, 1-4 = specific tier)
        self.tier_filter = 0

        # Simulated inventory (unlimited for testing)
        self.inventory = self._create_test_inventory()

        # Material rarity lookup (for bonus calculations)
        self.material_rarities = self._load_material_rarities()

        # Crafted items inventory (now with enchantment support)
        # Format: {item_id: {'quantity': int, 'enchantments': [list of enchantment dicts], 'rarity': str, 'stats': dict}}
        self.crafted_items = {}

        # UI state
        self.selected_recipe = None
        self.recipe_scroll = 0
        self.inventory_scroll = 0
        self.current_minigame = None
        self.minigame_result = None

        # Enchanting UI state
        self.enchanting_mode = False  # True when viewing enchanting pattern
        self.selected_enchant_target = None  # Item to apply enchantment to
        self.enchant_item_scroll = 0

        # Running state
        self.running = True

    def _create_test_inventory(self):
        """Create test inventory with ALL materials (unlimited for testing)"""
        # Load actual materials from JSON file
        materials = []

        try:
            with open('../items.JSON/items-materials-1.JSON', 'r') as f:
                data = json.load(f)
                materials_list = data.get('materials', [])
                for mat in materials_list:
                    materials.append(mat['materialId'])
                print(f"[Inventory] Loaded {len(materials)} materials from items-materials-1.JSON")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[Inventory] WARNING: Could not load materials from JSON: {e}")
            # Fallback to basic materials if JSON not found
            materials = [
                "copper_ore", "copper_ingot", "iron_ore", "iron_ingot",
                "oak_log", "oak_plank", "granite", "fire_crystal", "water_crystal"
            ]

        return {mat: 999 for mat in materials}  # Unlimited for testing

    def _load_material_rarities(self):
        """Load material rarity information from JSON for bonus calculations"""
        rarities = {}

        try:
            with open('../items.JSON/items-materials-1.JSON', 'r') as f:
                data = json.load(f)
                materials_list = data.get('materials', [])
                for mat in materials_list:
                    mat_id = mat.get('materialId')
                    rarity = mat.get('rarity', 'common')
                    if mat_id:
                        rarities[mat_id] = rarity
                print(f"[Rarities] Loaded rarities for {len(rarities)} materials")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[Rarities] WARNING: Could not load material rarities: {e}")

        return rarities

    def calculate_rarity_bonus(self, inputs):
        """
        Calculate rarity bonus multiplier based on input materials

        Formula: For each rarity level above common:
        - Count items at that rarity
        - Bonus per item = rarity_level * 2.5%
        - Total = sum all bonuses, apply as multiplier

        Example: 6 common, 1 rare (level 2), 2 epic (level 3)
        - Common: 6 * 0 * 2.5% = 0%
        - Rare: 1 * 2 * 2.5% = 5%
        - Epic: 2 * 3 * 2.5% = 15%
        - Total: 20% → 1.20x multiplier

        Args:
            inputs: List of {materialId, quantity} dicts

        Returns:
            float: Multiplier (e.g., 1.20 for 20% bonus)
        """
        # Rarity levels
        RARITY_LEVELS = {
            "common": 0,
            "uncommon": 1,
            "rare": 2,
            "epic": 3,
            "legendary": 4
        }

        total_bonus = 0.0

        for inp in inputs:
            mat_id = inp.get('materialId', '')
            quantity = inp.get('quantity', 0)

            # Get material rarity
            rarity = self.material_rarities.get(mat_id, 'common')
            rarity_level = RARITY_LEVELS.get(rarity, 0)

            # Calculate bonus: rarity_level * 2.5% * quantity
            bonus_per_item = rarity_level * 0.025
            total_bonus += bonus_per_item * quantity

        # Return as multiplier (1.0 + bonus percentage)
        multiplier = 1.0 + total_bonus

        print(f"[Rarity Bonus] Calculated {total_bonus:.1%} bonus → {multiplier:.2f}x multiplier")
        return multiplier

    def _load_item_metadata(self):
        """Load all item metadata from recipes and items JSON files"""
        metadata = {}

        # Load from recipe files (recipes have metadata.narrative for outputs)
        recipe_paths = [
            "../recipes.JSON/recipes-smithing-1.JSON",
            "../recipes.JSON/recipes-smithing-2.JSON",
            "../recipes.JSON/recipes-smithing-3.JSON",
            "../recipes.JSON/recipes-refining-1.JSON",
            "../recipes.JSON/recipes-alchemy-1.JSON",
            "../recipes.JSON/recipes-engineering-1.JSON",
            "../recipes.JSON/recipes-enchanting-1.JSON",
            "../recipes.JSON/recipes-adornments-1.json",
            "recipes.JSON/recipes-smithing-1.JSON",
            "recipes.JSON/recipes-smithing-2.JSON",
            "recipes.JSON/recipes-smithing-3.JSON",
            "recipes.JSON/recipes-refining-1.JSON",
            "recipes.JSON/recipes-alchemy-1.JSON",
            "recipes.JSON/recipes-engineering-1.JSON",
            "recipes.JSON/recipes-enchanting-1.JSON",
            "recipes.JSON/recipes-adornments-1.json",
        ]

        for path in recipe_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    recipes = data.get('recipes', [])
                    for recipe in recipes:
                        # Get output ID (varies by discipline)
                        output_id = None
                        if 'outputId' in recipe:
                            output_id = recipe['outputId']
                        elif 'enchantmentId' in recipe:
                            output_id = recipe['enchantmentId']
                        elif 'outputs' in recipe and recipe['outputs']:
                            output_id = recipe['outputs'][0].get('materialId')

                        if output_id:
                            narrative = recipe.get('metadata', {}).get('narrative', '')
                            name = recipe.get('name', output_id.replace('_', ' ').title())
                            if narrative:
                                metadata[output_id] = {
                                    'name': name,
                                    'narrative': narrative,
                                    'tier': recipe.get('stationTier', 1),
                                    'source': 'recipe'
                                }
            except (FileNotFoundError, json.JSONDecodeError):
                continue

        # Load from item files (items have metadata.narrative)
        # IMPORTANT: Items have type/category info, so we should UPDATE existing metadata
        item_paths = [
            "../items.JSON/items-smithing-1.JSON",
            "../items.JSON/items-smithing-2.JSON",
            "../items.JSON/items-alchemy-1.JSON",
            "../items.JSON/items-refining-1.JSON",
            "../items.JSON/items-materials-1.JSON",
            "../items.JSON/items-tools-1.JSON",
            "items.JSON/items-smithing-1.JSON",
            "items.JSON/items-smithing-2.JSON",
            "items.JSON/items-alchemy-1.JSON",
            "items.JSON/items-refining-1.JSON",
            "items.JSON/items-materials-1.JSON",
            "items.JSON/items-tools-1.JSON",
        ]

        for path in item_paths:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    # Items can be in various arrays (turrets, bombs, consumables, etc.)
                    for key, items_list in data.items():
                        if isinstance(items_list, list):
                            for item in items_list:
                                if isinstance(item, dict) and 'itemId' in item:
                                    item_id = item['itemId']
                                    narrative = item.get('metadata', {}).get('narrative', '')
                                    name = item.get('name', item_id.replace('_', ' ').title())
                                    item_type = item.get('type', '')
                                    item_category = item.get('category', '')

                                    # UPDATE existing metadata or create new
                                    # Items have more complete info (type, category) than recipes
                                    if narrative:
                                        if item_id in metadata:
                                            # Update existing with type/category from item data
                                            metadata[item_id]['type'] = item_type
                                            metadata[item_id]['category'] = item_category
                                        else:
                                            # Create new entry
                                            metadata[item_id] = {
                                                'name': name,
                                                'narrative': narrative,
                                                'tier': item.get('tier', 1),
                                                'category': item_category,
                                                'type': item_type,
                                                'source': 'item'
                                            }
            except (FileNotFoundError, json.JSONDecodeError):
                continue

        print(f"Loaded metadata for {len(metadata)} items")
        return metadata

    def get_current_crafter(self):
        """Get current discipline's crafter"""
        return self.disciplines[self.current_discipline]

    def get_current_recipes(self):
        """Get recipes for current discipline, filtered by tier"""
        all_recipes = self.get_current_crafter().get_all_recipes()

        if self.tier_filter == 0:
            return all_recipes

        # Filter by tier (handle both stationTier and stationTierRequired)
        filtered = {}
        for recipe_id, recipe in all_recipes.items():
            recipe_tier = recipe.get('stationTier', recipe.get('stationTierRequired', 1))
            if recipe_tier == self.tier_filter:
                filtered[recipe_id] = recipe

        return filtered

    def switch_discipline(self, discipline):
        """Switch to different discipline"""
        if discipline in self.disciplines:
            self.current_discipline = discipline
            self.selected_recipe = None
            self.recipe_scroll = 0
            self.current_minigame = None
            self.minigame_result = None

    def cycle_tier_filter(self):
        """Cycle through tier filters: All -> T1 -> T2 -> T3 -> T4 -> All"""
        self.tier_filter = (self.tier_filter + 1) % 5
        self.selected_recipe = None
        self.recipe_scroll = 0

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.enchanting_mode:
                        # Exit enchanting mode
                        self.enchanting_mode = False
                        self.selected_enchant_target = None
                    elif self.current_minigame:
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

                # T key to toggle tier filter
                elif event.key == pygame.K_t:
                    self.cycle_tier_filter()

                # Minigame controls
                elif event.key == pygame.K_SPACE:
                    if self.current_minigame and self.current_discipline == "smithing":
                        self.current_minigame.handle_fan()
                    elif self.current_minigame and self.current_discipline == "refining":
                        self.current_minigame.handle_attempt()
                    elif self.current_minigame and self.current_discipline == "alchemy":
                        self.current_minigame.chain()

            elif event.type == pygame.MOUSEWHEEL:
                # Scroll recipes or inventory
                if 50 <= pygame.mouse.get_pos()[0] <= 400:
                    # Recipe list scrolling
                    recipes = list(self.get_current_recipes().keys())
                    max_scroll = max(0, len(recipes) - 10)
                    self.recipe_scroll = max(0, min(max_scroll, self.recipe_scroll - event.y))
                elif 1000 <= pygame.mouse.get_pos()[0] <= 1550:
                    # Inventory scrolling
                    max_inv_scroll = max(0, len(self.inventory) // 8 - 15)
                    self.inventory_scroll = max(0, min(max_inv_scroll, self.inventory_scroll - event.y))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_click(event.pos)

    def handle_click(self, pos):
        """Handle mouse clicks"""
        x, y = pos

        # Enchanting mode clicks
        if self.enchanting_mode:
            self.handle_enchanting_click(pos)
            return

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

        # Tier filter button
        if 1400 <= x <= 1550 and 50 <= y <= 100:
            self.cycle_tier_filter()
            return

        # Recipe list
        if 50 <= x <= 400 and 150 <= y <= 800:
            recipes = list(self.get_current_recipes().items())
            visible_recipes = recipes[self.recipe_scroll:self.recipe_scroll + 10]

            recipe_y = 150
            for recipe_id, recipe in visible_recipes:
                if recipe_y <= y <= recipe_y + 55:
                    self.selected_recipe = recipe_id
                    return
                recipe_y += 60

        # Craft buttons (when in main UI, not minigame)
        if not self.current_minigame and not self.minigame_result:
            if self.selected_recipe:
                crafter = self.get_current_crafter()

                # Recipe panel location
                panel_x = 450
                panel_y = 120

                # Instant craft button
                instant_x = panel_x + 20
                instant_y = panel_y + 600
                instant_w = 460
                instant_h = 45

                if instant_x <= x <= instant_x + instant_w and instant_y <= y <= instant_y + instant_h:
                    # For enchanting, show the pattern UI and item selection
                    if self.current_discipline == "enchanting":
                        self.enchanting_mode = True
                        self.selected_enchant_target = None
                        print("Enchanting mode: Select an item to enchant")
                    else:
                        # Other disciplines: instant craft
                        result = crafter.craft_instant(self.selected_recipe, self.inventory)
                        if result.get('success'):
                            output_id = result['outputId']
                            qty = result['quantity']
                            # Initialize item entry if doesn't exist
                            if output_id not in self.crafted_items:
                                self.crafted_items[output_id] = {'quantity': 0, 'enchantments': []}
                            self.crafted_items[output_id]['quantity'] += qty
                            print(f"Crafted {qty}x {output_id} (instant)")
                        else:
                            print(f"Failed to craft: {result.get('message')}")
                    return

                # Minigame button (NOT for enchanting)
                if self.current_discipline != "enchanting":
                    minigame_x = panel_x + 20
                    minigame_y = panel_y + 655
                    minigame_w = 460
                    minigame_h = 45

                    if minigame_x <= x <= minigame_x + minigame_w and minigame_y <= y <= minigame_y + minigame_h:
                        if crafter.can_craft(self.selected_recipe, self.inventory):
                            self.start_minigame()
                        else:
                            print("Cannot craft: Insufficient materials")
                        return

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
            print(f"Started minigame for {self.selected_recipe}")

    def handle_enchanting_click(self, pos):
        """Handle clicks in enchanting mode"""
        x, y = pos

        if not self.selected_recipe:
            return

        recipe = self.get_current_crafter().get_recipe(self.selected_recipe)
        if not recipe:
            return

        # Get applicable items
        applicable_to = recipe.get('applicableTo', ['any'])
        enchantable_items = []

        for item_id, item_data in self.crafted_items.items():
            if isinstance(item_data, dict):
                qty = item_data.get('quantity', 0)
            else:
                qty = item_data

            if qty > 0:
                # Check item metadata for proper type matching
                item_meta = self.item_metadata.get(item_id, {})
                item_type = item_meta.get('type', '')
                item_category = item_meta.get('category', '')

                if ('any' in applicable_to or
                    item_type in applicable_to or
                    item_category in applicable_to or
                    any(app_type in item_id.lower() for app_type in applicable_to)):
                    enchantable_items.append(item_id)

        # Item list clicks (select item to enchant)
        panel_x = 950
        panel_y = 150
        item_y = panel_y + 50

        for i, item_id in enumerate(enchantable_items[:20]):
            item_rect = pygame.Rect(panel_x + 10, item_y, 580, 25)
            if item_rect.collidepoint(x, y):
                self.selected_enchant_target = item_id
                print(f"Selected {item_id} for enchanting")
                return
            item_y += 28

        # Apply button
        button_x = 950
        button_y = 770
        button_w = 280
        button_h = 50

        if button_x <= x <= button_x + button_w and button_y <= y <= button_y + button_h:
            if self.selected_enchant_target and self.get_current_crafter().can_craft(self.selected_recipe, self.inventory):
                self.apply_enchantment()
            return

        # Cancel button
        cancel_x = button_x + button_w + 20
        if cancel_x <= x <= cancel_x + 280 and button_y <= y <= button_y + button_h:
            self.enchanting_mode = False
            self.selected_enchant_target = None
            print("Cancelled enchanting")
            return

    def apply_enchantment(self):
        """Apply selected enchantment to selected item"""
        if not self.selected_recipe or not self.selected_enchant_target:
            return

        crafter = self.get_current_crafter()
        recipe = crafter.get_recipe(self.selected_recipe)

        if not crafter.can_craft(self.selected_recipe, self.inventory):
            print("Insufficient materials!")
            return

        # Deduct materials
        for inp in recipe.get('inputs', []):
            self.inventory[inp['materialId']] -= inp['quantity']

        # Add enchantment to the item
        enchantment = {
            'id': recipe.get('enchantmentId', ''),
            'name': recipe.get('enchantmentName', 'Unknown'),
            'effect': recipe.get('effect', {})
        }

        # Ensure item has enchantments list
        item_data = self.crafted_items[self.selected_enchant_target]
        if not isinstance(item_data, dict):
            self.crafted_items[self.selected_enchant_target] = {'quantity': item_data, 'enchantments': []}
            item_data = self.crafted_items[self.selected_enchant_target]

        # Add enchantment
        item_data['enchantments'].append(enchantment)

        print(f"Applied {enchantment['name']} to {self.selected_enchant_target}!")

        # Exit enchanting mode
        self.enchanting_mode = False
        self.selected_enchant_target = None

    def handle_minigame_click(self, pos):
        """Handle clicks within minigame"""
        x, y = pos

        if self.current_discipline == "smithing":
            # Hammer button
            if 500 <= x <= 900 and 650 <= y <= 700:
                self.current_minigame.handle_hammer()

        # Result continue button - FIXED: Use correct box_height (450 not 400)
        box_width, box_height = 600, 450
        box_x = (SCREEN_WIDTH - box_width) // 2
        box_y = (SCREEN_HEIGHT - box_height) // 2
        button_width, button_height = 200, 50
        button_x = (SCREEN_WIDTH - button_width) // 2
        button_y = box_y + box_height - 80

        if self.minigame_result and button_x <= x <= button_x + button_width and button_y <= y <= button_y + button_height:
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
                rarity = result.get('rarity')  # Get rarity from refining
                stats = result.get('stats')  # Get stats from engineering
                quality = result.get('quality')  # Get quality from engineering/refining

                # Calculate and apply rarity bonus based on input materials
                recipe = crafter.get_recipe(self.selected_recipe)
                if recipe:
                    inputs = recipe.get('inputs', [])
                    rarity_multiplier = self.calculate_rarity_bonus(inputs)

                    # Apply rarity bonus to stats (for smithing, alchemy, engineering, enchanting)
                    if stats and rarity_multiplier > 1.0:
                        # Apply multiplier to all stats
                        for stat_name in stats:
                            stats[stat_name] = int(stats[stat_name] * rarity_multiplier)
                        print(f"[Rarity Bonus] Applied {rarity_multiplier:.2f}x to stats: {stats}")

                if output_id:
                    # Initialize item entry if doesn't exist
                    if output_id not in self.crafted_items:
                        self.crafted_items[output_id] = {'quantity': 0, 'enchantments': [], 'rarity': None, 'stats': None}
                    self.crafted_items[output_id]['quantity'] += qty

                    # Store rarity if present (from refining minigames)
                    if rarity and not self.crafted_items[output_id].get('rarity'):
                        self.crafted_items[output_id]['rarity'] = rarity
                        print(f"[DEBUG] Stored rarity '{rarity}' for {output_id}")

                    # Store stats if present (from engineering minigames)
                    if stats and not self.crafted_items[output_id].get('stats'):
                        self.crafted_items[output_id]['stats'] = stats
                        print(f"[DEBUG] Stored stats {stats} for {output_id}")

                    # Debug: Show what's in the dict
                    print(f"[DEBUG] crafted_items[{output_id}] = {self.crafted_items[output_id]}")

                # Format output message
                rarity_str = f" ({rarity})" if rarity else ""
                stats_str = ""
                if stats:
                    # Calculate average stat for display
                    avg_stat = sum(stats.values()) / len(stats) if stats else 0
                    stats_str = f" [Stats: {avg_stat:.0f}]"

                print(f"Crafted {qty}x {output_id}{rarity_str}{stats_str} via minigame")
            else:
                print(f"Minigame failed: {result.get('message')}")

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

        if self.enchanting_mode:
            self.draw_enchanting_ui()
        elif self.current_minigame and not self.minigame_result:
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

        # Quick help text
        help_text = self.small_font.render(
            "Keys: 1-5=Switch Discipline | T=Toggle Tier Filter | ESC=Exit | Mouse: Click recipes, scroll lists",
            True, LIGHT_GRAY
        )
        self.screen.blit(help_text, (50, 830))

        # Discipline tabs
        self.draw_discipline_tabs()

        # Tier filter button
        self.draw_tier_filter()

        # Recipe list
        self.draw_recipe_list()

        # Recipe details / craft buttons
        self.draw_recipe_panel()

        # Pattern display (if recipe selected and not enchanting mode)
        if self.selected_recipe and not self.enchanting_mode:
            self.draw_pattern_display()

        # Visual inventory
        self.draw_visual_inventory()

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

    def draw_tier_filter(self):
        """Draw tier filter toggle"""
        button_x = 1400
        button_y = 50
        button_w = 150
        button_h = 50

        pygame.draw.rect(self.screen, PURPLE, (button_x, button_y, button_w, button_h))
        pygame.draw.rect(self.screen, WHITE, (button_x, button_y, button_w, button_h), 2)

        tier_text = "All Tiers" if self.tier_filter == 0 else f"Tier {self.tier_filter}"
        text = self.font.render(f"T: {tier_text}", True, WHITE)
        text_rect = text.get_rect(center=(button_x + button_w // 2, button_y + button_h // 2))
        self.screen.blit(text, text_rect)

    def draw_recipe_list(self):
        """Draw recipe list for current discipline"""
        panel_x = 50
        panel_y = 120
        panel_width = 350
        panel_height = 700

        # Background
        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 3)

        # Title
        tier_suffix = f" (T{self.tier_filter})" if self.tier_filter > 0 else ""
        title = self.font.render(f"{self.current_discipline.title()} Recipes{tier_suffix}", True, WHITE)
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

            # Tier (handle both stationTier and stationTierRequired)
            tier = recipe.get('stationTier', recipe.get('stationTierRequired', 1))
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
        if len(recipe_name) > 25:
            recipe_name = recipe_name[:23] + "..."
        name_text = self.large_font.render(recipe_name, True, WHITE)
        self.screen.blit(name_text, (panel_x + 20, panel_y + 20))

        # Tier and output (handle both stationTier and stationTierRequired)
        tier = recipe.get('stationTier', recipe.get('stationTierRequired', 1))
        output_id = recipe.get('outputId') or recipe.get('enchantmentId') or \
                    (recipe.get('outputs', [{}])[0].get('materialId') if recipe.get('outputs') else 'unknown')
        if len(output_id) > 30:
            output_id = output_id[:28] + "..."

        # Show tier with color coding
        tier_colors = {1: GREEN, 2: CYAN, 3: PURPLE, 4: ORANGE}
        tier_color = tier_colors.get(tier, WHITE)
        info_text = self.font.render(f"Tier {tier} | Output: {output_id}", True, tier_color)
        self.screen.blit(info_text, (panel_x + 20, panel_y + 70))

        # Show recipe description if available
        recipe_desc = recipe.get('metadata', {}).get('narrative', '')
        if recipe_desc:
            # Show first 80 chars of description
            if len(recipe_desc) > 80:
                recipe_desc = recipe_desc[:77] + "..."
            desc_text = self.small_font.render(recipe_desc, True, LIGHT_GRAY)
            self.screen.blit(desc_text, (panel_x + 20, panel_y + 95))
            mat_y_start = panel_y + 125
        else:
            mat_y_start = panel_y + 110

        # Materials required
        mat_y = mat_y_start
        materials_title = self.font.render("Materials Required:", True, YELLOW)
        self.screen.blit(materials_title, (panel_x + 20, mat_y))
        mat_y += 35

        for inp in recipe.get('inputs', [])[:15]:  # Limit to 15 to fit
            mat_id = inp['materialId']
            qty = inp['quantity']
            has = self.inventory.get(mat_id, 0)

            mat_color = GREEN if has >= qty else RED
            mat_name = mat_id.replace('_', ' ').title()
            if len(mat_name) > 25:
                mat_name = mat_name[:23] + "..."
            mat_text = self.small_font.render(f"• {mat_name}: {has}/{qty}", True, mat_color)
            self.screen.blit(mat_text, (panel_x + 30, mat_y))
            mat_y += 25

        # Craft buttons
        crafter = self.get_current_crafter()
        can_craft = crafter.can_craft(self.selected_recipe, self.inventory)

        # Instant craft button
        instant_y = panel_y + 600
        instant_color = GREEN if can_craft else LIGHT_GRAY
        pygame.draw.rect(self.screen, instant_color, (panel_x + 20, instant_y, panel_width - 40, 45))

        if self.current_discipline == "enchanting":
            # Enchanting is BASIC CRAFT ONLY - no minigame
            instant_text = self.font.render("CRAFT ENCHANTMENT", True, WHITE)
            self.screen.blit(instant_text, (panel_x + 130, instant_y + 15))
        else:
            instant_text = self.font.render("INSTANT CRAFT (Base Stats)", True, WHITE)
            self.screen.blit(instant_text, (panel_x + 100, instant_y + 15))

        # Minigame button (NOT for enchanting)
        minigame_y = panel_y + 655
        if self.current_discipline != "enchanting":
            minigame_color = BLUE if can_craft else LIGHT_GRAY
            pygame.draw.rect(self.screen, minigame_color, (panel_x + 20, minigame_y, panel_width - 40, 45))
            minigame_text = self.font.render("START MINIGAME (Bonus Stats)", True, WHITE)
            self.screen.blit(minigame_text, (panel_x + 90, minigame_y + 15))
        else:
            # Enchanting has NO minigame
            pygame.draw.rect(self.screen, DARK_GRAY, (panel_x + 20, minigame_y, panel_width - 40, 45))
            info_text = self.small_font.render("Enchanting has no minigame - basic craft only", True, LIGHT_GRAY)
            self.screen.blit(info_text, (panel_x + 75, minigame_y + 15))

    def draw_visual_inventory(self):
        """Draw visual inventory with grid of material squares"""
        panel_x = 1000
        panel_y = 120
        panel_width = 550
        panel_height = 350

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, CYAN, (panel_x, panel_y, panel_width, panel_height), 3)

        title = self.font.render("Inventory (Unlimited Testing Mode)", True, CYAN)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        # Draw materials in grid (8 per row)
        cell_size = 60
        cells_per_row = 8
        start_x = panel_x + 15
        start_y = panel_y + 50

        materials = sorted(self.inventory.items())
        visible_start = self.inventory_scroll * cells_per_row
        visible_materials = materials[visible_start:visible_start + cells_per_row * 4]  # 4 rows

        for idx, (mat_id, qty) in enumerate(visible_materials):
            row = idx // cells_per_row
            col = idx % cells_per_row

            cell_x = start_x + col * (cell_size + 5)
            cell_y = start_y + row * (cell_size + 5)

            # Draw cell
            color = MATERIAL_COLORS.get(mat_id, GRAY)
            pygame.draw.rect(self.screen, color, (cell_x, cell_y, cell_size, cell_size))
            pygame.draw.rect(self.screen, WHITE, (cell_x, cell_y, cell_size, cell_size), 2)

            # Draw quantity
            qty_text = self.small_font.render(str(qty), True, WHITE)
            qty_rect = qty_text.get_rect(center=(cell_x + cell_size // 2, cell_y + cell_size - 12))

            # Draw background for qty
            bg_rect = pygame.Rect(cell_x + 2, cell_y + cell_size - 18, cell_size - 4, 16)
            pygame.draw.rect(self.screen, BLACK, bg_rect)
            self.screen.blit(qty_text, qty_rect)

        # Material name tooltip on hover
        mouse_pos = pygame.mouse.get_pos()
        for idx, (mat_id, qty) in enumerate(visible_materials):
            row = idx // cells_per_row
            col = idx % cells_per_row
            cell_x = start_x + col * (cell_size + 5)
            cell_y = start_y + row * (cell_size + 5)

            if cell_x <= mouse_pos[0] <= cell_x + cell_size and cell_y <= mouse_pos[1] <= cell_y + cell_size:
                # Draw tooltip
                tooltip_text = mat_id.replace('_', ' ').title()
                tooltip = self.small_font.render(tooltip_text, True, WHITE)
                tooltip_bg = pygame.Rect(mouse_pos[0] + 10, mouse_pos[1] - 25, tooltip.get_width() + 10, 20)
                pygame.draw.rect(self.screen, BLACK, tooltip_bg)
                pygame.draw.rect(self.screen, CYAN, tooltip_bg, 1)
                self.screen.blit(tooltip, (mouse_pos[0] + 15, mouse_pos[1] - 23))
                break

        # Scroll indicator
        total_rows = (len(materials) + cells_per_row - 1) // cells_per_row
        if total_rows > 4:
            scroll_text = self.small_font.render(f"Scroll: Row {self.inventory_scroll + 1}/{total_rows - 3}", True, WHITE)
            self.screen.blit(scroll_text, (panel_x + 400, panel_y + 15))

    def draw_crafted_items(self):
        """Draw crafted items inventory with tooltips"""
        panel_x = 1000
        panel_y = 490
        panel_width = 550
        panel_height = 330

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 3)

        title = self.font.render("Crafted Items (Hover for details)", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        if not self.crafted_items:
            empty_text = self.small_font.render("No items crafted yet", True, LIGHT_GRAY)
            self.screen.blit(empty_text, (panel_x + 200, panel_y + 150))
            return

        # Display crafted items with hover tooltips
        mouse_pos = pygame.mouse.get_pos()
        item_y = panel_y + 50
        hovered_item = None

        for item_id, item_data in list(self.crafted_items.items())[:12]:
            # Handle both old format (just a number) and new format (dict)
            if isinstance(item_data, dict):
                qty = item_data.get('quantity', 0)
                enchantments = item_data.get('enchantments', [])
            else:
                # Legacy support - migrate to new format
                qty = item_data
                enchantments = []
                self.crafted_items[item_id] = {'quantity': qty, 'enchantments': enchantments}

            # Get metadata
            metadata = self.item_metadata.get(item_id, {})
            item_name = metadata.get('name', item_id.replace('_', ' ').title())
            if len(item_name) > 40:
                item_name = item_name[:38] + "..."

            # Item row
            item_rect = pygame.Rect(panel_x + 20, item_y, panel_width - 40, 22)

            # Highlight if hovering
            is_hovering = item_rect.collidepoint(mouse_pos)
            if is_hovering:
                pygame.draw.rect(self.screen, LIGHT_GRAY, item_rect)
                item_stats = item_data.get('stats') if isinstance(item_data, dict) else None
                hovered_item = (item_id, metadata, mouse_pos, enchantments, item_stats)

            # Draw item text with rarity and enchantment indicator
            rarity = item_data.get('rarity') if isinstance(item_data, dict) else None
            item_stats = item_data.get('stats') if isinstance(item_data, dict) else None

            rarity_suffix = f" ({rarity})" if rarity else ""
            # Add stats quality indicator for engineering devices
            stats_suffix = ""
            if item_stats:
                avg_stat = sum(item_stats.values()) / len(item_stats)
                stats_suffix = f" [Q:{avg_stat:.0f}]"

            enchant_suffix = f" [{len(enchantments)} ench]" if enchantments else ""
            item_color = PURPLE if enchantments else (YELLOW if is_hovering else GREEN)
            item_text = self.font.render(f"{item_name}: x{qty}{rarity_suffix}{stats_suffix}{enchant_suffix}", True, item_color)
            self.screen.blit(item_text, (panel_x + 25, item_y))

            item_y += 25

        # Draw tooltip for hovered item (on top of everything)
        if hovered_item:
            item_stats = hovered_item[4] if len(hovered_item) > 4 else None
            self._draw_item_tooltip(hovered_item[0], hovered_item[1], hovered_item[2], hovered_item[3], item_stats)

    def _draw_item_tooltip(self, item_id, metadata, mouse_pos, enchantments=None, stats=None):
        """Draw detailed tooltip for an item (similar to main.py format)"""
        if enchantments is None:
            enchantments = []

        # Get item data to show rarity
        item_data = self.crafted_items.get(item_id, {})
        rarity = item_data.get('rarity') if isinstance(item_data, dict) else None

        # Tooltip dimensions
        tooltip_width = 400
        tooltip_padding = 10
        line_height = 20

        # Calculate lines needed
        lines_needed = 3  # Name, tier/category/rarity, blank line

        if metadata and metadata.get('narrative'):
            narrative = metadata.get('narrative', '')
            wrapped_lines = self._wrap_text(narrative, tooltip_width - 2 * tooltip_padding)
            lines_needed += len(wrapped_lines)

        if stats:
            lines_needed += len(stats) + 2  # +2 for header and spacing
        if enchantments:
            lines_needed += len(enchantments) + 1

        tooltip_height = tooltip_padding * 2 + line_height * lines_needed

        # Position tooltip (try to show near mouse, but keep on screen)
        tooltip_x = mouse_pos[0] + 15
        tooltip_y = mouse_pos[1] - tooltip_height // 2

        # Keep on screen
        if tooltip_x + tooltip_width > SCREEN_WIDTH:
            tooltip_x = mouse_pos[0] - tooltip_width - 15
        if tooltip_y < 0:
            tooltip_y = 0
        if tooltip_y + tooltip_height > SCREEN_HEIGHT:
            tooltip_y = SCREEN_HEIGHT - tooltip_height

        # Draw tooltip background
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
        pygame.draw.rect(self.screen, BLACK, tooltip_rect)
        pygame.draw.rect(self.screen, ORANGE, tooltip_rect, 2)

        # Rarity colors (like main.py)
        RARITY_COLORS = {
            "common": (200, 200, 200),
            "uncommon": (100, 255, 100),
            "rare": (100, 150, 255),
            "epic": (200, 100, 255),
            "legendary": (255, 165, 0),
            "Standard": (200, 200, 200),
            "Fine": (100, 255, 100),
            "Exceptional": (255, 165, 0)
        }

        # Draw item name (colored by rarity)
        text_y = tooltip_y + tooltip_padding
        item_color = RARITY_COLORS.get(rarity, YELLOW) if rarity else YELLOW
        name_text = self.font.render(metadata.get('name', item_id) if metadata else item_id, True, item_color)
        self.screen.blit(name_text, (tooltip_x + tooltip_padding, text_y))
        text_y += line_height + 5

        # Draw tier, category, and rarity (like main.py)
        tier = metadata.get('tier', '?') if metadata else '?'
        category = metadata.get('category', 'Item').capitalize() if metadata else 'Item'
        rarity_display = rarity if rarity else "Common"

        info_line = f"Tier {tier} | {category}"
        if rarity:
            info_line += f" | {rarity_display}"

        info_text = self.small_font.render(info_line, True, item_color)
        self.screen.blit(info_text, (tooltip_x + tooltip_padding, text_y))
        text_y += line_height + 3

        # Draw narrative (wrapped)
        if metadata and metadata.get('narrative'):
            narrative = metadata.get('narrative', '')
            wrapped_lines = self._wrap_text(narrative, tooltip_width - 2 * tooltip_padding)
            for line in wrapped_lines:
                line_text = self.small_font.render(line, True, WHITE)
                self.screen.blit(line_text, (tooltip_x + tooltip_padding, text_y))
                text_y += line_height - 2

        # Draw device stats if any (from engineering)
        if stats:
            text_y += 8
            stats_title = self.small_font.render("Device Stats:", True, CYAN)
            self.screen.blit(stats_title, (tooltip_x + tooltip_padding, text_y))
            text_y += line_height - 2
            for stat_name, stat_value in stats.items():
                stat_text = self.small_font.render(f"  {stat_name.title()}: {stat_value}", True, GREEN)
                self.screen.blit(stat_text, (tooltip_x + tooltip_padding, text_y))
                text_y += line_height - 2

        # Draw enchantments if any
        if enchantments:
            text_y += 8
            for enchant in enchantments:
                enchant_name = enchant.get('name', 'Unknown Enchantment')
                enchant_text = self.small_font.render(f"• {enchant_name}", True, PURPLE)
                self.screen.blit(enchant_text, (tooltip_x + tooltip_padding, text_y))
                text_y += line_height - 2

    def draw_pattern_display(self):
        """Draw placement pattern for current selected recipe"""
        if not self.selected_recipe:
            return

        try:
            crafter = self.get_current_crafter()
            if not hasattr(crafter, 'get_placement'):
                return

            placement = crafter.get_placement(self.selected_recipe)
            if not placement:
                return

            # Display pattern based on discipline
            if self.current_discipline == "smithing":
                self.draw_smithing_pattern(placement)
            elif self.current_discipline == "refining":
                self.draw_refining_pattern(placement)
            elif self.current_discipline == "alchemy":
                self.draw_alchemy_pattern(placement)
            elif self.current_discipline == "engineering":
                self.draw_engineering_pattern(placement)
        except Exception as e:
            print(f"[Pattern Display] Error drawing pattern for {self.current_discipline}: {e}")

    def draw_smithing_pattern(self, placement):
        """Draw smithing grid pattern"""
        # Panel location (below recipe panel, above buttons)
        panel_x = 470
        panel_y = 410
        panel_width = 460
        panel_height = 180

        pygame.draw.rect(self.screen, (40, 40, 40), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 2)

        title = self.small_font.render("Crafting Pattern:", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 5))

        # Get placementMap (dict like "2,3": "iron_ingot")
        placement_map = placement if isinstance(placement, dict) else {}

        # Dynamically calculate grid size from actual coordinates (more robust than metadata)
        max_row = 0
        max_col = 0
        for coord_str in placement_map.keys():
            if coord_str != 'metadata' and ',' in coord_str:
                try:
                    row, col = map(int, coord_str.split(','))
                    max_row = max(max_row, row)
                    max_col = max(max_col, col)
                except (ValueError, IndexError):
                    pass

        # Use the larger dimension for a square grid (or could use max_row x max_col for rectangular)
        grid_size = max(max_row, max_col, 3)  # Minimum 3x3

        # Draw grid
        cell_size = min(40, (panel_width - 40) // grid_size)
        grid_start_x = panel_x + 20
        grid_start_y = panel_y + 30

        for row in range(grid_size):
            for col in range(grid_size):
                x = grid_start_x + col * cell_size
                y = grid_start_y + row * cell_size
                pygame.draw.rect(self.screen, (60, 60, 60), (x, y, cell_size - 1, cell_size - 1))
                pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, cell_size - 1, cell_size - 1), 1)

        # Draw materials - placement format is "row,col" (1-indexed)
        for coord_str, material_id in placement_map.items():
            if coord_str != 'metadata' and ',' in coord_str:
                try:
                    row, col = map(int, coord_str.split(','))
                    row -= 1  # Convert to 0-indexed
                    col -= 1

                    if 0 <= row < grid_size and 0 <= col < grid_size:
                        x = grid_start_x + col * cell_size
                        y = grid_start_y + row * cell_size

                        # Draw material cell
                        mat_color = MATERIAL_COLORS.get(material_id, CYAN)
                        pygame.draw.rect(self.screen, mat_color, (x + 2, y + 2, cell_size - 5, cell_size - 5))

                        # Draw label
                        if cell_size >= 30:
                            label = material_id[:4].upper()
                            label_text = self.small_font.render(label, True, WHITE)
                            self.screen.blit(label_text, (x + 4, y + cell_size - 16))
                except (ValueError, IndexError) as e:
                    print(f"[Smithing] Invalid coordinate {coord_str}: {e}")

    def draw_refining_pattern(self, placement):
        """Draw refining hub-and-spoke pattern"""
        panel_x = 470
        panel_y = 410
        panel_width = 460
        panel_height = 180

        pygame.draw.rect(self.screen, (40, 40, 40), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, CYAN, (panel_x, panel_y, panel_width, panel_height), 2)

        title = self.small_font.render("Refining Pattern (Hub & Spoke):", True, CYAN)
        self.screen.blit(title, (panel_x + 10, panel_y + 5))

        # Core inputs (center)
        core_inputs = placement.get('coreInputs', [])
        core_y = panel_y + 35
        if core_inputs:
            core_label = self.font.render("Core (Center):", True, YELLOW)
            self.screen.blit(core_label, (panel_x + 20, core_y))
            core_y += 25

            for inp in core_inputs:
                mat_id = inp.get('materialId', 'unknown')
                qty = inp.get('quantity', 1)
                mat_color = MATERIAL_COLORS.get(mat_id, GRAY)

                # Draw circle for core
                pygame.draw.circle(self.screen, mat_color, (panel_x + 30, core_y + 10), 8)
                mat_text = self.small_font.render(f"{mat_id} x{qty}", True, WHITE)
                self.screen.blit(mat_text, (panel_x + 50, core_y + 3))
                core_y += 22

        # Surrounding inputs (spokes)
        surrounding = placement.get('surroundingInputs', [])
        if surrounding:
            surr_y = core_y + 10
            surr_label = self.font.render("Surrounding (Spokes):", True, YELLOW)
            self.screen.blit(surr_label, (panel_x + 20, surr_y))
            surr_y += 25

            for inp in surrounding[:6]:  # Limit display
                mat_id = inp.get('materialId', 'unknown')
                qty = inp.get('quantity', 1)
                mat_color = MATERIAL_COLORS.get(mat_id, GRAY)

                # Draw small circle for spoke
                pygame.draw.circle(self.screen, mat_color, (panel_x + 30, surr_y + 8), 6)
                mat_text = self.small_font.render(f"{mat_id} x{qty}", True, LIGHT_GRAY)
                self.screen.blit(mat_text, (panel_x + 50, surr_y + 1))
                surr_y += 20

    def draw_alchemy_pattern(self, placement):
        """Draw alchemy sequential pattern"""
        panel_x = 470
        panel_y = 410
        panel_width = 460
        panel_height = 180

        pygame.draw.rect(self.screen, (40, 40, 40), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, GREEN, (panel_x, panel_y, panel_width, panel_height), 2)

        title = self.small_font.render("Alchemy Sequence (Order Matters!):", True, GREEN)
        self.screen.blit(title, (panel_x + 10, panel_y + 5))

        # Ingredients in order
        ingredients = placement.get('ingredients', [])
        ing_y = panel_y + 35

        for ing in ingredients:
            slot = ing.get('slot', 0)
            mat_id = ing.get('materialId', 'unknown')
            qty = ing.get('quantity', 1)
            mat_color = MATERIAL_COLORS.get(mat_id, GRAY)

            # Draw slot number
            slot_text = self.font.render(f"{slot}.", True, YELLOW)
            self.screen.blit(slot_text, (panel_x + 20, ing_y))

            # Draw arrow
            arrow_text = self.font.render("→", True, LIGHT_GRAY)
            self.screen.blit(arrow_text, (panel_x + 45, ing_y))

            # Draw material
            pygame.draw.rect(self.screen, mat_color, (panel_x + 70, ing_y + 3, 15, 15))
            mat_text = self.small_font.render(f"{mat_id} x{qty}", True, WHITE)
            self.screen.blit(mat_text, (panel_x + 90, ing_y + 2))

            ing_y += 25

    def draw_engineering_pattern(self, placement):
        """Draw engineering slot-based pattern"""
        panel_x = 470
        panel_y = 410
        panel_width = 460
        panel_height = 180

        pygame.draw.rect(self.screen, (40, 40, 40), (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, BLUE, (panel_x, panel_y, panel_width, panel_height), 2)

        title = self.small_font.render("Engineering Slots:", True, BLUE)
        self.screen.blit(title, (panel_x + 10, panel_y + 5))

        # Slot types with colors
        slot_colors = {
            'FRAME': (150, 150, 150),
            'FUNCTION': (255, 200, 100),
            'POWER': (255, 100, 100),
            'MODIFIER': (150, 100, 255),
            'ENHANCEMENT': (100, 255, 150)
        }

        # Slots
        slots = placement.get('slots', [])
        slot_y = panel_y + 35

        for slot_data in slots:
            slot_type = slot_data.get('type', 'UNKNOWN')
            mat_id = slot_data.get('materialId', 'unknown')
            qty = slot_data.get('quantity', 1)

            slot_color = slot_colors.get(slot_type, GRAY)
            mat_color = MATERIAL_COLORS.get(mat_id, GRAY)

            # Draw slot type label
            type_rect = pygame.Rect(panel_x + 20, slot_y, 100, 20)
            pygame.draw.rect(self.screen, slot_color, type_rect)
            pygame.draw.rect(self.screen, WHITE, type_rect, 1)
            type_text = self.small_font.render(slot_type, True, BLACK)
            self.screen.blit(type_text, (panel_x + 25, slot_y + 3))

            # Draw material
            pygame.draw.rect(self.screen, mat_color, (panel_x + 130, slot_y + 2, 16, 16))
            mat_text = self.small_font.render(f"{mat_id} x{qty}", True, WHITE)
            self.screen.blit(mat_text, (panel_x + 150, slot_y + 2))

            slot_y += 25

    def draw_enchanting_ui(self):
        """Draw enchanting pattern UI and item selection"""
        # Title
        title = self.title_font.render("Enchanting Station", True, PURPLE)
        self.screen.blit(title, (550, 10))

        if not self.selected_recipe:
            self.enchanting_mode = False
            return

        recipe = self.get_current_crafter().get_recipe(self.selected_recipe)
        if not recipe:
            self.enchanting_mode = False
            return

        # Get placement pattern
        placement = self.get_current_crafter().get_placement(self.selected_recipe)

        # Enchantment info panel
        self.draw_enchantment_info(recipe, placement)

        # Pattern grid display
        if placement:
            self.draw_pattern_grid(placement)

        # Item selection panel
        self.draw_enchantable_items(recipe)

        # Bottom buttons
        self.draw_enchanting_buttons()

        # ESC hint
        esc_text = self.small_font.render("Press ESC to return", True, LIGHT_GRAY)
        self.screen.blit(esc_text, (700, 870))

    def draw_enchantment_info(self, recipe, placement):
        """Draw enchantment recipe information"""
        panel_x = 50
        panel_y = 80
        panel_width = 350
        panel_height = 300

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, PURPLE, (panel_x, panel_y, panel_width, panel_height), 3)

        # Enchantment name
        enchant_name = recipe.get('enchantmentName', 'Unknown')
        name_text = self.large_font.render(enchant_name, True, YELLOW)
        self.screen.blit(name_text, (panel_x + 10, panel_y + 10))

        # Applicable to
        applicable_to = recipe.get('applicableTo', ['any'])
        applicable_text = self.font.render(f"Applies to: {', '.join(applicable_to)}", True, CYAN)
        self.screen.blit(applicable_text, (panel_x + 10, panel_y + 50))

        # Narrative
        narrative = recipe.get('metadata', {}).get('narrative', 'No description')
        wrapped = self._wrap_text(narrative, panel_width - 20)
        text_y = panel_y + 80
        for line in wrapped[:6]:  # Limit to 6 lines
            line_text = self.small_font.render(line, True, WHITE)
            self.screen.blit(line_text, (panel_x + 10, text_y))
            text_y += 20

        # Materials required
        mat_y = panel_y + 220
        mats_title = self.font.render("Materials:", True, YELLOW)
        self.screen.blit(mats_title, (panel_x + 10, mat_y))
        mat_y += 25

        for inp in recipe.get('inputs', [])[:3]:
            mat_id = inp['materialId']
            qty = inp['quantity']
            has = self.inventory.get(mat_id, 0)
            mat_color = GREEN if has >= qty else RED
            mat_text = self.small_font.render(f"• {mat_id.replace('_', ' ').title()}: {has}/{qty}", True, mat_color)
            self.screen.blit(mat_text, (panel_x + 15, mat_y))
            mat_y += 18

    def draw_pattern_grid(self, placement):
        """Draw the enchanting pattern grid"""
        grid_x = 450
        grid_y = 150
        cell_size = 40
        grid_type = placement.get('gridType', 'square_8x8')
        grid_size = int(grid_type.split('_')[1].split('x')[0])

        # Draw grid background
        grid_pixel_size = grid_size * cell_size
        pygame.draw.rect(self.screen, (30, 30, 30), (grid_x, grid_y, grid_pixel_size, grid_pixel_size))

        # Draw grid cells
        for row in range(grid_size):
            for col in range(grid_size):
                x = grid_x + col * cell_size
                y = grid_y + row * cell_size
                pygame.draw.rect(self.screen, LIGHT_GRAY, (x, y, cell_size - 1, cell_size - 1), 1)

        # Draw center axes
        half = grid_size // 2
        center_x = grid_x + half * cell_size
        center_y = grid_y + half * cell_size
        pygame.draw.line(self.screen, GRAY, (center_x, grid_y), (center_x, grid_y + grid_pixel_size), 2)
        pygame.draw.line(self.screen, GRAY, (grid_x, center_y), (grid_x + grid_pixel_size, center_y), 2)

        # Draw shape connecting lines first (so they appear behind vertices)
        shapes = placement.get('shapes', [])
        for shape in shapes:
            shape_vertices = shape.get('vertices', [])
            if len(shape_vertices) > 1:
                # Draw lines connecting the vertices in the shape
                for i in range(len(shape_vertices)):
                    v1_str = shape_vertices[i]
                    v2_str = shape_vertices[(i + 1) % len(shape_vertices)]  # Wrap around to close the shape

                    # Parse coordinates
                    if ',' in v1_str and ',' in v2_str:
                        gx1, gy1 = map(int, v1_str.split(','))
                        gx2, gy2 = map(int, v2_str.split(','))

                        # Convert to screen positions
                        sx1 = grid_x + (gx1 + half) * cell_size + cell_size // 2
                        sy1 = grid_y + (half - gy1) * cell_size + cell_size // 2
                        sx2 = grid_x + (gx2 + half) * cell_size + cell_size // 2
                        sy2 = grid_y + (half - gy2) * cell_size + cell_size // 2

                        # Draw connecting line
                        pygame.draw.line(self.screen, BLUE, (sx1, sy1), (sx2, sy2), 3)

        # Draw vertices from placement (on top of lines)
        vertices = placement.get('vertices', {})
        for coord_str, vertex_data in vertices.items():
            if ',' in coord_str:
                gx, gy = map(int, coord_str.split(','))
                # Convert centered coordinates to screen position
                screen_x = grid_x + (gx + half) * cell_size + cell_size // 2
                screen_y = grid_y + (half - gy) * cell_size + cell_size // 2

                # Draw material dot
                material_id = vertex_data.get('materialId')
                is_key = vertex_data.get('isKey', False)
                color = RED if is_key else CYAN
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), 6)
                pygame.draw.circle(self.screen, BLACK, (screen_x, screen_y), 6, 1)

                # Draw material label
                if material_id:
                    mat_label = material_id[:4].upper()
                    label_text = self.small_font.render(mat_label, True, WHITE)
                    self.screen.blit(label_text, (screen_x - 12, screen_y - 25))

        # Grid title
        grid_title = self.font.render(f"Pattern ({grid_type})", True, CYAN)
        self.screen.blit(grid_title, (grid_x, grid_y - 30))

    def draw_enchantable_items(self, recipe):
        """Draw list of items that can be enchanted"""
        panel_x = 950
        panel_y = 150
        panel_width = 600
        panel_height = 600

        pygame.draw.rect(self.screen, GRAY, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, ORANGE, (panel_x, panel_y, panel_width, panel_height), 3)

        title = self.font.render("Select Item to Enchant", True, ORANGE)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        # Filter applicable items
        applicable_to = recipe.get('applicableTo', ['any'])
        enchantable_items = []

        for item_id, item_data in self.crafted_items.items():
            # Get item quantity
            if isinstance(item_data, dict):
                qty = item_data.get('quantity', 0)
            else:
                qty = item_data

            if qty > 0:
                # Check if applicable
                if 'any' in applicable_to:
                    enchantable_items.append(item_id)
                else:
                    # Check item metadata to see if it matches applicable types
                    item_meta = self.item_metadata.get(item_id, {})
                    item_type = item_meta.get('type', '')
                    item_category = item_meta.get('category', '')

                    # Check if item type matches any of the applicable types
                    # Also check item_id as fallback for items without metadata
                    if (item_type in applicable_to or
                        item_category in applicable_to or
                        any(app_type in item_id.lower() for app_type in applicable_to)):
                        enchantable_items.append(item_id)

        if not enchantable_items:
            no_items = self.font.render("No applicable items to enchant", True, LIGHT_GRAY)
            self.screen.blit(no_items, (panel_x + 150, panel_y + 250))
            info = self.small_font.render(f"This enchantment applies to: {', '.join(applicable_to)}", True, LIGHT_GRAY)
            self.screen.blit(info, (panel_x + 100, panel_y + 290))
            return

        # Draw item list
        item_y = panel_y + 50
        mouse_pos = pygame.mouse.get_pos()

        for i, item_id in enumerate(enchantable_items[:20]):  # Limit to 20 items
            item_data = self.crafted_items[item_id]
            if isinstance(item_data, dict):
                qty = item_data.get('quantity', 0)
                enchantments = item_data.get('enchantments', [])
            else:
                qty = item_data
                enchantments = []

            # Item row
            item_rect = pygame.Rect(panel_x + 10, item_y, panel_width - 20, 25)
            is_selected = item_id == self.selected_enchant_target
            is_hovering = item_rect.collidepoint(mouse_pos)

            # Background
            if is_selected:
                pygame.draw.rect(self.screen, PURPLE, item_rect)
            elif is_hovering:
                pygame.draw.rect(self.screen, LIGHT_GRAY, item_rect)

            # Item name
            item_name = self.item_metadata.get(item_id, {}).get('name', item_id.replace('_', ' ').title())
            if len(item_name) > 35:
                item_name = item_name[:33] + "..."

            enchant_suffix = f" [{len(enchantments)} ench]" if enchantments else ""
            item_text = self.font.render(f"{item_name}: x{qty}{enchant_suffix}", True, WHITE)
            self.screen.blit(item_text, (panel_x + 20, item_y + 2))

            item_y += 28

    def draw_enchanting_buttons(self):
        """Draw enchanting action buttons"""
        # Apply button
        button_x = 950
        button_y = 770
        button_w = 280
        button_h = 50

        can_apply = (self.selected_enchant_target is not None and
                     self.get_current_crafter().can_craft(self.selected_recipe, self.inventory))

        button_color = GREEN if can_apply else LIGHT_GRAY
        pygame.draw.rect(self.screen, button_color, (button_x, button_y, button_w, button_h))
        pygame.draw.rect(self.screen, WHITE, (button_x, button_y, button_w, button_h), 2)

        button_text = self.font.render("APPLY ENCHANTMENT", True, WHITE)
        self.screen.blit(button_text, (button_x + 30, button_y + 15))

        # Cancel button
        cancel_x = button_x + button_w + 20
        pygame.draw.rect(self.screen, RED, (cancel_x, button_y, 280, button_h))
        pygame.draw.rect(self.screen, WHITE, (cancel_x, button_y, 280, button_h), 2)

        cancel_text = self.font.render("CANCEL", True, WHITE)
        self.screen.blit(cancel_text, (cancel_x + 90, button_y + 15))

    def _wrap_text(self, text, max_width):
        """Wrap text to fit within max_width"""
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            test_surface = self.small_font.render(test_line, True, WHITE)

            if test_surface.get_width() <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Word is too long, add it anyway
                    lines.append(word)

        if current_line:
            lines.append(' '.join(current_line))

        return lines

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
            import math
            pygame.draw.arc(self.screen, GREEN, (center_x - radius, center_y - radius, radius * 2, radius * 2),
                            math.radians(-10), math.radians(10), 10)

            # Draw current position
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
        box_width, box_height = 600, 450
        box_x = (SCREEN_WIDTH - box_width) // 2
        box_y = (SCREEN_HEIGHT - box_height) // 2

        pygame.draw.rect(self.screen, GRAY, (box_x, box_y, box_width, box_height))

        # Border color based on success
        border_color = GREEN if self.minigame_result.get('success') else RED
        pygame.draw.rect(self.screen, border_color, (box_x, box_y, box_width, box_height), 4)

        # Success or failure
        if self.minigame_result.get('success'):
            status_text = self.title_font.render("SUCCESS!", True, GREEN)
        else:
            status_text = self.title_font.render("FAILED", True, RED)

        status_rect = status_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 60))
        self.screen.blit(status_text, status_rect)

        # Discipline name
        disc_text = self.font.render(f"{self.current_discipline.title()} Minigame", True, CYAN)
        disc_rect = disc_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 110))
        self.screen.blit(disc_text, disc_rect)

        # Message
        message = self.minigame_result.get('message', 'Crafting complete')
        msg_text = self.font.render(message, True, WHITE)
        msg_rect = msg_text.get_rect(center=(SCREEN_WIDTH // 2, box_y + 160))
        self.screen.blit(msg_text, msg_rect)

        # Additional details based on discipline
        detail_y = box_y + 210
        if 'score' in self.minigame_result:
            score_text = self.font.render(f"Score: {self.minigame_result['score']:.1f}", True, CYAN)
            score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
            self.screen.blit(score_text, score_rect)
            detail_y += 35

        if 'bonus' in self.minigame_result:
            bonus_text = self.font.render(f"Bonus: +{self.minigame_result['bonus']}%", True, YELLOW)
            bonus_rect = bonus_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
            self.screen.blit(bonus_text, bonus_rect)
            detail_y += 35

        if 'quality' in self.minigame_result:
            quality = self.minigame_result['quality']
            # Handle both numeric quality (float) and text quality (string)
            if isinstance(quality, str):
                quality_text = self.font.render(f"Quality: {quality}", True, YELLOW)
            else:
                quality_text = self.font.render(f"Quality: {quality:.0%}", True, YELLOW)
            quality_rect = quality_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
            self.screen.blit(quality_text, quality_rect)
            detail_y += 35

        # Materials consumed/lost notification
        if not self.minigame_result.get('success'):
            if self.minigame_result.get('materials_lost'):
                loss_text = self.small_font.render("Materials consumed", True, RED)
                loss_rect = loss_text.get_rect(center=(SCREEN_WIDTH // 2, detail_y))
                self.screen.blit(loss_text, loss_rect)

        # Continue button
        button_width, button_height = 200, 50
        button_x = (SCREEN_WIDTH - button_width) // 2
        button_y = box_y + box_height - 80

        pygame.draw.rect(self.screen, BLUE, (button_x, button_y, button_width, button_height))
        pygame.draw.rect(self.screen, WHITE, (button_x, button_y, button_width, button_height), 2)
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
