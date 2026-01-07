"""
Interactive Crafting UI System - Manual material placement for recipe discovery

This module provides interactive crafting UIs for all 5 disciplines where players
can manually place materials to discover and craft recipes.

Created: 2026-01-07
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from entities.components.inventory import Inventory, ItemStack
from data.databases import MaterialDatabase, RecipeDatabase, PlacementDatabase
from data.models.recipes import Recipe, PlacementData


# Material category ordering for palette organization
MATERIAL_CATEGORIES_ORDER = [
    'metal', 'wood', 'stone', 'elemental', 'monster_drop',
    'fabric', 'herb', 'gem', 'other'
]


@dataclass
class PlacedMaterial:
    """Represents a material placed in the interactive UI"""
    item_id: str
    quantity: int
    crafted_stats: Optional[Dict[str, Any]] = None
    rarity: str = 'common'


class InteractiveBaseUI(ABC):
    """Base class for all interactive crafting UIs"""

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        self.station_type = station_type
        self.station_tier = station_tier
        self.inventory = inventory

        self.matched_recipe: Optional[Recipe] = None
        self.selected_material: Optional[ItemStack] = None
        self.material_palette_scroll = 0

        # Track materials borrowed from inventory (to return on cancel)
        self.borrowed_materials: Dict[str, int] = {}  # {item_id: quantity}

    def get_available_materials(self) -> List[ItemStack]:
        """
        Get materials from inventory that can be used at this station.
        Organized by: tier (ascending) → category (custom order) → name (alphabetically)

        In debug mode (Config.DEBUG_INFINITE_RESOURCES), shows 99 of every material
        up to the station tier.
        """
        from core.config import Config

        mat_db = MaterialDatabase.get_instance()
        available = []

        # DEBUG MODE: Show 99 of every material up to station tier
        if Config.DEBUG_INFINITE_RESOURCES:
            for material_id, mat_def in mat_db.materials.items():
                if mat_def.tier <= self.station_tier:
                    # Create a temporary ItemStack with 99 quantity
                    debug_stack = ItemStack(
                        item_id=material_id,
                        quantity=99,
                        rarity=mat_def.rarity
                    )
                    available.append(debug_stack)
        else:
            # NORMAL MODE: Show only inventory materials
            for slot in self.inventory.slots:
                if slot and slot.quantity > 0:
                    mat_def = mat_db.get_material(slot.item_id)
                    if mat_def and mat_def.tier <= self.station_tier:
                        available.append(slot)

        # Sort by tier, then category, then name
        def sort_key(item_stack: ItemStack):
            mat = mat_db.get_material(item_stack.item_id)
            if not mat:
                return (999, 999, item_stack.item_id)

            # Get category index (lower = earlier in list)
            try:
                category_idx = MATERIAL_CATEGORIES_ORDER.index(mat.category)
            except ValueError:
                category_idx = len(MATERIAL_CATEGORIES_ORDER)  # Put unknown categories at end

            return (mat.tier, category_idx, mat.name)

        available.sort(key=sort_key)
        return available

    def borrow_material(self, item_id: str, quantity: int = 1) -> bool:
        """
        Temporarily remove material from inventory for placement.
        Returns True if successful, False if insufficient quantity.
        """
        removed = self.inventory.remove_item(item_id, quantity)
        if removed > 0:
            self.borrowed_materials[item_id] = self.borrowed_materials.get(item_id, 0) + removed
            return True
        return False

    def return_material(self, item_id: str, quantity: int = 1):
        """Return a borrowed material to inventory"""
        if item_id in self.borrowed_materials and self.borrowed_materials[item_id] >= quantity:
            self.inventory.add_item(item_id, quantity)
            self.borrowed_materials[item_id] -= quantity
            if self.borrowed_materials[item_id] == 0:
                del self.borrowed_materials[item_id]

    def return_all_materials(self):
        """Return all borrowed materials to inventory (called on cancel/close)"""
        for item_id, quantity in list(self.borrowed_materials.items()):
            self.inventory.add_item(item_id, quantity)
        self.borrowed_materials.clear()

    @abstractmethod
    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Place a material at the given position. Returns True if successful."""
        pass

    @abstractmethod
    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        """Remove material from position. Returns the removed material or None."""
        pass

    @abstractmethod
    def clear_placement(self):
        """Clear all placed materials and return them to inventory"""
        pass

    @abstractmethod
    def check_recipe_match(self) -> Optional[Recipe]:
        """Check if current placement matches any recipe. Returns matched recipe or None."""
        pass

    @abstractmethod
    def get_placement_data(self) -> Dict[str, Any]:
        """Get current placement as a dictionary for rendering"""
        pass


class InteractiveRefiningUI(InteractiveBaseUI):
    """
    Hub-and-spoke model for refining with tier-varying slot counts:
    T1: 1 core + 2 surrounding
    T2: 1 core + 4 surrounding
    T3: 2 cores + 5 surrounding
    T4: 3 cores + 6 surrounding
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # CORRECT slot configuration by tier from GAME_MECHANICS_V6.md
        slot_config = {
            1: {'core': 1, 'surrounding': 2},
            2: {'core': 1, 'surrounding': 4},
            3: {'core': 2, 'surrounding': 5},
            4: {'core': 3, 'surrounding': 6}
        }
        config = slot_config.get(station_tier, {'core': 1, 'surrounding': 2})
        self.num_core_slots = config['core']
        self.num_surrounding_slots = config['surrounding']

        self.core_slots: List[Optional[PlacedMaterial]] = [None] * self.num_core_slots
        self.surrounding_slots: List[Optional[PlacedMaterial]] = [None] * self.num_surrounding_slots

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple: ('core', index) or ('surrounding', index)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        slot_type, index = position

        if slot_type == 'core' and 0 <= index < self.num_core_slots:
            # Return previous material if exists
            if self.core_slots[index]:
                old = self.core_slots[index]
                self.return_material(old.item_id, old.quantity)

            # Borrow new material
            if self.borrow_material(item_stack.item_id, 1):
                self.core_slots[index] = PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                )
                self.matched_recipe = self.check_recipe_match()
                return True

        elif slot_type == 'surrounding' and 0 <= index < self.num_surrounding_slots:
            # Return previous material if exists
            if self.surrounding_slots[index]:
                old = self.surrounding_slots[index]
                self.return_material(old.item_id, old.quantity)

            # Borrow new material
            if self.borrow_material(item_stack.item_id, 1):
                self.surrounding_slots[index] = PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                )
                self.matched_recipe = self.check_recipe_match()
                return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if not isinstance(position, tuple) or len(position) != 2:
            return None

        slot_type, index = position

        if slot_type == 'core' and 0 <= index < self.num_core_slots and self.core_slots[index]:
            mat = self.core_slots[index]
            self.return_material(mat.item_id, mat.quantity)
            self.core_slots[index] = None
            self.matched_recipe = self.check_recipe_match()
            return mat

        elif slot_type == 'surrounding' and 0 <= index < self.num_surrounding_slots:
            if self.surrounding_slots[index]:
                mat = self.surrounding_slots[index]
                self.return_material(mat.item_id, mat.quantity)
                self.surrounding_slots[index] = None
                self.matched_recipe = self.check_recipe_match()
                return mat

        return None

    def clear_placement(self):
        # Clear all core slots
        for i in range(self.num_core_slots):
            if self.core_slots[i]:
                mat = self.core_slots[i]
                self.return_material(mat.item_id, mat.quantity)
                self.core_slots[i] = None

        # Clear all surrounding slots
        for i in range(self.num_surrounding_slots):
            if self.surrounding_slots[i]:
                mat = self.surrounding_slots[i]
                self.return_material(mat.item_id, mat.quantity)
                self.surrounding_slots[i] = None

        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against refining recipes"""
        # Check if at least one core slot is filled
        if not any(self.core_slots):
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Get all refining recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'refining':
                continue

            # Get placed core materials
            placed_cores = [s.item_id for s in self.core_slots if s is not None]
            required_cores = [inp.get('materialId') for inp in placement.core_inputs]

            # Match core inputs (order doesn't matter)
            if sorted(placed_cores) != sorted(required_cores):
                continue

            # Match surrounding inputs (order doesn't matter for refining)
            placed_surrounding = [s.item_id for s in self.surrounding_slots if s is not None]
            required_surrounding = [inp.get('materialId') for inp in placement.surrounding_inputs]

            # Check if all required surrounding materials are present
            if sorted(placed_surrounding) == sorted(required_surrounding):
                return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'refining',
            'core_slots': self.core_slots,
            'surrounding_slots': self.surrounding_slots,
            'num_core_slots': self.num_core_slots,
            'num_surrounding_slots': self.num_surrounding_slots
        }


class InteractiveAlchemyUI(InteractiveBaseUI):
    """
    Sequential slots model for alchemy:
    [Slot 0] -> [Slot 1] -> [Slot 2] -> [Result]
       Base      Reagent    Catalyst

    Max slots by tier: T1=2, T2=3, T3=4, T4=6
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # CORRECT max slots by tier from placements-alchemy-1.JSON
        max_slots_by_tier = {1: 2, 2: 3, 3: 4, 4: 6}
        num_slots = max_slots_by_tier.get(station_tier, 2)
        self.slots: List[Optional[PlacedMaterial]] = [None] * num_slots

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is an integer index"""
        if not isinstance(position, int) or position < 0 or position >= len(self.slots):
            return False

        # Return previous material if exists
        if self.slots[position]:
            old = self.slots[position]
            self.return_material(old.item_id, old.quantity)

        # Borrow new material
        if self.borrow_material(item_stack.item_id, 1):
            self.slots[position] = PlacedMaterial(
                item_id=item_stack.item_id,
                quantity=1,
                crafted_stats=item_stack.crafted_stats,
                rarity=item_stack.rarity
            )
            self.matched_recipe = self.check_recipe_match()
            return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if isinstance(position, int) and 0 <= position < len(self.slots):
            if self.slots[position]:
                mat = self.slots[position]
                self.return_material(mat.item_id, mat.quantity)
                self.slots[position] = None
                self.matched_recipe = self.check_recipe_match()
                return mat
        return None

    def clear_placement(self):
        for i in range(len(self.slots)):
            if self.slots[i]:
                mat = self.slots[i]
                self.return_material(mat.item_id, mat.quantity)
                self.slots[i] = None
        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against alchemy recipes - order matters!"""
        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Get current placement sequence
        current_sequence = [s.item_id if s else None for s in self.slots]

        # Get all alchemy recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'alchemy':
                continue

            # Build required sequence from placement ingredients
            required_sequence = []
            for ingredient in placement.ingredients:
                slot_idx = ingredient.get('slot', 0)
                mat_id = ingredient.get('materialId', '')
                # Extend list if needed
                while len(required_sequence) <= slot_idx:
                    required_sequence.append(None)
                required_sequence[slot_idx] = mat_id

            # Match exact sequence (None values are wildcards)
            if len(current_sequence) >= len(required_sequence):
                match = True
                for i, required_mat in enumerate(required_sequence):
                    if required_mat and current_sequence[i] != required_mat:
                        match = False
                        break

                if match:
                    return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'alchemy',
            'slots': self.slots
        }


class InteractiveEngineeringUI(InteractiveBaseUI):
    """
    Slot-type model for engineering:
    Canvas system with 5 slot types: FRAME, FUNCTION, POWER, MODIFIER, UTILITY

    Each slot type can hold specific materials that define the device's behavior.
    Recipes specify which slot types are required and what materials go in each.
    """

    # CORRECT slot types from placements-engineering-1.JSON
    SLOT_TYPES = ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY']

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # Each slot type can hold multiple materials
        self.slots: Dict[str, List[PlacedMaterial]] = {
            slot_type: [] for slot_type in self.SLOT_TYPES
        }

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple: (slot_type, index_within_type)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        slot_type, index = position
        if slot_type not in self.slots:
            return False

        # Borrow material
        if self.borrow_material(item_stack.item_id, 1):
            mat = PlacedMaterial(
                item_id=item_stack.item_id,
                quantity=1,
                crafted_stats=item_stack.crafted_stats,
                rarity=item_stack.rarity
            )

            # If index is within current list, replace; otherwise append
            if index < len(self.slots[slot_type]):
                # Return old material
                old = self.slots[slot_type][index]
                self.return_material(old.item_id, old.quantity)
                self.slots[slot_type][index] = mat
            else:
                self.slots[slot_type].append(mat)

            self.matched_recipe = self.check_recipe_match()
            return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if not isinstance(position, tuple) or len(position) != 2:
            return None

        slot_type, index = position
        if slot_type not in self.slots or index >= len(self.slots[slot_type]):
            return None

        mat = self.slots[slot_type][index]
        self.return_material(mat.item_id, mat.quantity)
        self.slots[slot_type].pop(index)
        self.matched_recipe = self.check_recipe_match()
        return mat

    def clear_placement(self):
        for slot_type in self.SLOT_TYPES:
            for mat in self.slots[slot_type]:
                self.return_material(mat.item_id, mat.quantity)
            self.slots[slot_type].clear()
        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against engineering recipes - slot types matter, order doesn't"""
        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Build current placement by slot type
        current_by_type: Dict[str, List[str]] = {}
        for slot_type, materials in self.slots.items():
            if materials:
                current_by_type[slot_type] = sorted([m.item_id for m in materials])

        # Get all engineering recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'engineering':
                continue

            # Build required placement by slot type
            required_by_type: Dict[str, List[str]] = {}
            for slot_entry in placement.slots:
                slot_type = slot_entry.get('type', '')
                mat_id = slot_entry.get('materialId', '')
                if slot_type and mat_id:
                    if slot_type not in required_by_type:
                        required_by_type[slot_type] = []
                    required_by_type[slot_type].append(mat_id)

            # Sort each type's materials for comparison
            for slot_type in required_by_type:
                required_by_type[slot_type].sort()

            # Compare
            if current_by_type == required_by_type:
                return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'engineering',
            'slots': self.slots
        }


class InteractiveSmithingUI(InteractiveBaseUI):
    """
    Grid-based placement for smithing:
    Grid size depends on station tier (T1=3x3, T2=5x5, T3=7x7, T4=9x9)
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # CORRECT grid sizes by tier from GAME_MECHANICS_V6.md
        grid_sizes = {1: 3, 2: 5, 3: 7, 4: 9}
        self.grid_size = grid_sizes.get(station_tier, 3)
        self.grid: Dict[Tuple[int, int], PlacedMaterial] = {}

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple (x, y)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        x, y = position
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False

        # Return previous material if exists at this position
        if position in self.grid:
            old = self.grid[position]
            self.return_material(old.item_id, old.quantity)

        # Borrow new material
        if self.borrow_material(item_stack.item_id, 1):
            self.grid[position] = PlacedMaterial(
                item_id=item_stack.item_id,
                quantity=1,
                crafted_stats=item_stack.crafted_stats,
                rarity=item_stack.rarity
            )
            self.matched_recipe = self.check_recipe_match()
            return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if position in self.grid:
            mat = self.grid[position]
            self.return_material(mat.item_id, mat.quantity)
            del self.grid[position]
            self.matched_recipe = self.check_recipe_match()
            return mat
        return None

    def clear_placement(self):
        for pos, mat in list(self.grid.items()):
            self.return_material(mat.item_id, mat.quantity)
        self.grid.clear()
        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against smithing recipes - exact grid match required"""
        if not self.grid:
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Convert current grid to string-key format
        current_placement = {
            f"{x},{y}": mat.item_id for (x, y), mat in self.grid.items()
        }

        # Get all smithing recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'smithing':
                continue

            # Exact match required
            if current_placement == placement.placement_map:
                return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'smithing',
            'grid_size': self.grid_size,
            'grid': self.grid
        }


class InteractiveAdornmentsUI(InteractiveBaseUI):
    """
    Vertex-based Cartesian coordinate system for adornments/enchanting.

    Uses a coordinate system where materials are placed at specific (x,y) vertices.
    Coordinate range: -7 to +7 for all tiers (origin at 0,0)
    Grid templates by tier: T1=8x8, T2=10x10, T3=12x12, T4=14x14

    Recipes are matched against exact vertex coordinate patterns stored in
    placement_map with keys like "0,0", "3,3", "-3,-3", etc.
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # CORRECT grid templates by tier from placements-adornments-1.JSON
        grid_templates = {
            1: 'square_8x8',
            2: 'square_10x10',
            3: 'square_12x12',
            4: 'square_14x14'
        }
        self.grid_template = grid_templates.get(station_tier, 'square_8x8')

        # Vertex coordinate system (-7 to +7 range)
        self.coordinate_range = 7  # All tiers use same range
        self.vertices: Dict[str, PlacedMaterial] = {}  # "x,y" -> PlacedMaterial

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple (x, y) in Cartesian coordinates (-7 to +7)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        x, y = position
        if not (-self.coordinate_range <= x <= self.coordinate_range and
                -self.coordinate_range <= y <= self.coordinate_range):
            return False

        # Convert to string key
        coord_key = f"{x},{y}"

        # Return previous material if exists at this vertex
        if coord_key in self.vertices:
            old = self.vertices[coord_key]
            self.return_material(old.item_id, old.quantity)

        # Borrow new material
        if self.borrow_material(item_stack.item_id, 1):
            self.vertices[coord_key] = PlacedMaterial(
                item_id=item_stack.item_id,
                quantity=1,
                crafted_stats=item_stack.crafted_stats,
                rarity=item_stack.rarity
            )
            self.matched_recipe = self.check_recipe_match()
            return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if not isinstance(position, tuple) or len(position) != 2:
            return None

        x, y = position
        coord_key = f"{x},{y}"

        if coord_key in self.vertices:
            mat = self.vertices[coord_key]
            self.return_material(mat.item_id, mat.quantity)
            del self.vertices[coord_key]
            self.matched_recipe = self.check_recipe_match()
            return mat

        return None

    def clear_placement(self):
        for coord_key, mat in list(self.vertices.items()):
            self.return_material(mat.item_id, mat.quantity)
        self.vertices.clear()
        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against adornment recipes using vertex-based coordinate matching"""
        if not self.vertices:
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Build current placement map
        current_placement = {
            coord_key: mat.item_id for coord_key, mat in self.vertices.items()
        }

        # Get all adornment recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'adornments':
                continue

            # Match against vertex-based placement_map
            # The placement_map has "vertices" key containing coordinate -> materialId mappings
            if placement.placement_map and 'vertices' in placement.placement_map:
                required_vertices = placement.placement_map['vertices']

                # Exact match required
                if current_placement == required_vertices:
                    return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'adornments',
            'grid_template': self.grid_template,
            'coordinate_range': self.coordinate_range,
            'vertices': self.vertices
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_interactive_ui(station_type: str, station_tier: int, inventory: Inventory) -> Optional[InteractiveBaseUI]:
    """
    Factory function to create the appropriate interactive UI for a station type.

    Args:
        station_type: One of 'smithing', 'refining', 'alchemy', 'engineering', 'adornments'
        station_tier: Station tier (1-4)
        inventory: Player's inventory

    Returns:
        Interactive UI instance or None if invalid station type
    """
    ui_map = {
        'smithing': InteractiveSmithingUI,
        'refining': InteractiveRefiningUI,
        'alchemy': InteractiveAlchemyUI,
        'engineering': InteractiveEngineeringUI,
        'adornments': InteractiveAdornmentsUI
    }

    ui_class = ui_map.get(station_type)
    if ui_class:
        print(f"✓ Creating interactive UI for {station_type} (tier {station_tier})")
        return ui_class(station_type, station_tier, inventory)

    print(f"⚠ Unknown station type: {station_type}")
    return None
