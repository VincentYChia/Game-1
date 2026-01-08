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

        # DEBUG MODE: Show 99 of every material (all tiers, not limited by station tier)
        # This allows testing recipes that require higher-tier materials
        if Config.DEBUG_INFINITE_RESOURCES:
            for material_id, mat_def in mat_db.materials.items():
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

        In debug mode, always returns True without touching inventory.
        """
        from core.config import Config

        # DEBUG MODE: Skip inventory operations
        if Config.DEBUG_INFINITE_RESOURCES:
            # Track borrowed materials for consistency but don't touch inventory
            self.borrowed_materials[item_id] = self.borrowed_materials.get(item_id, 0) + quantity
            return True

        # NORMAL MODE: Remove from inventory
        removed = self.inventory.remove_item(item_id, quantity)
        if removed > 0:
            self.borrowed_materials[item_id] = self.borrowed_materials.get(item_id, 0) + removed
            return True
        return False

    def return_material(self, item_id: str, quantity: int = 1):
        """Return a borrowed material to inventory"""
        from core.config import Config

        # DEBUG MODE: Skip inventory operations
        if Config.DEBUG_INFINITE_RESOURCES:
            if item_id in self.borrowed_materials and self.borrowed_materials[item_id] >= quantity:
                self.borrowed_materials[item_id] -= quantity
                if self.borrowed_materials[item_id] == 0:
                    del self.borrowed_materials[item_id]
            return

        # NORMAL MODE: Return to inventory
        if item_id in self.borrowed_materials and self.borrowed_materials[item_id] >= quantity:
            self.inventory.add_item(item_id, quantity)
            self.borrowed_materials[item_id] -= quantity
            if self.borrowed_materials[item_id] == 0:
                del self.borrowed_materials[item_id]

    def return_all_materials(self):
        """Return all borrowed materials to inventory (called on cancel/close)"""
        from core.config import Config

        # DEBUG MODE: Just clear the tracking dict
        if Config.DEBUG_INFINITE_RESOURCES:
            self.borrowed_materials.clear()
            return

        # NORMAL MODE: Return to inventory
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
            existing = self.core_slots[index]

            # If same material already in slot, increment quantity
            if existing and existing.item_id == item_stack.item_id:
                if self.borrow_material(item_stack.item_id, 1):
                    existing.quantity += 1
                    self.matched_recipe = self.check_recipe_match()
                    return True

            # Different material - return previous and place new
            if existing:
                self.return_material(existing.item_id, existing.quantity)

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
            existing = self.surrounding_slots[index]

            # If same material already in slot, increment quantity
            if existing and existing.item_id == item_stack.item_id:
                if self.borrow_material(item_stack.item_id, 1):
                    existing.quantity += 1
                    self.matched_recipe = self.check_recipe_match()
                    return True

            # Different material - return previous and place new
            if existing:
                self.return_material(existing.item_id, existing.quantity)

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

            # Get placed core materials with quantities
            placed_cores = [(s.item_id, s.quantity) for s in self.core_slots if s is not None]
            required_cores = [(inp.get('materialId'), inp.get('quantity', 1)) for inp in placement.core_inputs]

            # Match core inputs (order doesn't matter, but quantities must match)
            if sorted(placed_cores) != sorted(required_cores):
                continue

            # Match surrounding inputs (order doesn't matter for refining)
            placed_surrounding = [(s.item_id, s.quantity) for s in self.surrounding_slots if s is not None]
            required_surrounding = [(inp.get('materialId'), inp.get('quantity', 1)) for inp in placement.surrounding_inputs]

            # Check if all required surrounding materials with quantities are present
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
        """
        Position is an integer index.
        If placing the same material that's already in the slot, increment quantity.
        Otherwise, replace with new material.
        """
        if not isinstance(position, int) or position < 0 or position >= len(self.slots):
            return False

        existing = self.slots[position]

        # If same material already in slot, increment quantity
        if existing and existing.item_id == item_stack.item_id:
            if self.borrow_material(item_stack.item_id, 1):
                existing.quantity += 1
                self.matched_recipe = self.check_recipe_match()
                return True
            return False

        # Different material or empty slot - replace
        if existing:
            self.return_material(existing.item_id, existing.quantity)

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
        """Match against alchemy recipes - order AND quantities matter!"""
        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Get current placement sequence (material_id, quantity) tuples
        current_sequence = [
            (s.item_id, s.quantity) if s else (None, 0)
            for s in self.slots
        ]

        # Get all alchemy recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'alchemy':
                continue

            # Build required sequence from placement ingredients
            # NOTE: JSON uses 1-indexed slots, but UI uses 0-indexed arrays
            required_sequence = []
            for ingredient in placement.ingredients:
                slot_idx = ingredient.get('slot', 1) - 1  # Convert 1-indexed to 0-indexed
                mat_id = ingredient.get('materialId', '')
                quantity = ingredient.get('quantity', 1)
                # Extend list if needed
                while len(required_sequence) <= slot_idx:
                    required_sequence.append((None, 0))
                required_sequence[slot_idx] = (mat_id, quantity)

            # Match exact sequence with quantities (None values are wildcards)
            if len(current_sequence) >= len(required_sequence):
                match = True
                for i, (required_mat, required_qty) in enumerate(required_sequence):
                    current_mat, current_qty = current_sequence[i]
                    if required_mat:  # Not a wildcard
                        if current_mat != required_mat or current_qty != required_qty:
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

    # All possible slot types
    ALL_SLOT_TYPES = ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY']

    # Slot types available by tier (based on actual recipe usage in placements-engineering-1.JSON)
    TIER_SLOT_TYPES = {
        1: ['FRAME', 'FUNCTION', 'POWER'],
        2: ['FRAME', 'FUNCTION', 'POWER'],
        3: ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY'],
        4: ['FRAME', 'FUNCTION', 'POWER', 'MODIFIER', 'UTILITY']
    }

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # Get available slot types for this tier
        self.available_slot_types = self.TIER_SLOT_TYPES.get(station_tier, self.ALL_SLOT_TYPES)
        # Each slot type can hold multiple materials (only create slots for available types)
        self.slots: Dict[str, List[PlacedMaterial]] = {
            slot_type: [] for slot_type in self.available_slot_types
        }

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple: (slot_type, index_within_type)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        slot_type, index = position
        if slot_type not in self.slots:
            return False

        # If index is within current list, check for stacking
        if index < len(self.slots[slot_type]):
            existing = self.slots[slot_type][index]
            # If same material, increment quantity
            if existing.item_id == item_stack.item_id:
                if self.borrow_material(item_stack.item_id, 1):
                    existing.quantity += 1
                    self.matched_recipe = self.check_recipe_match()
                    return True
                return False

            # Different material - return old and place new
            if self.borrow_material(item_stack.item_id, 1):
                self.return_material(existing.item_id, existing.quantity)
                self.slots[slot_type][index] = PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                )
                self.matched_recipe = self.check_recipe_match()
                return True
        else:
            # Append new material
            if self.borrow_material(item_stack.item_id, 1):
                self.slots[slot_type].append(PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                ))
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

        # Build current placement by slot type (material_id, quantity) tuples
        current_by_type: Dict[str, List[Tuple[str, int]]] = {}
        for slot_type, materials in self.slots.items():
            if materials:
                current_by_type[slot_type] = sorted([(m.item_id, m.quantity) for m in materials])

        # Get all engineering recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'engineering':
                continue

            # Build required placement by slot type with quantities
            required_by_type: Dict[str, List[Tuple[str, int]]] = {}
            for slot_entry in placement.slots:
                slot_type = slot_entry.get('type', '')
                mat_id = slot_entry.get('materialId', '')
                quantity = slot_entry.get('quantity', 1)
                if slot_type and mat_id:
                    if slot_type not in required_by_type:
                        required_by_type[slot_type] = []
                    required_by_type[slot_type].append((mat_id, quantity))

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
        # JSON uses 1-indexed Cartesian coordinates (y=1 is bottom, y=grid_size is top)
        # UI uses 0-indexed screen coordinates (y=0 is top, y=grid_size-1 is bottom)
        # So we need to: 1) add 1 for x indexing, 2) invert y coordinate
        current_placement = {
            f"{x+1},{self.grid_size - y}": mat.item_id for (x, y), mat in self.grid.items()
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
    Shape-based Cartesian coordinate system for adornments/enchanting.

    Players place geometric shapes (triangles, squares) on a grid, which creates
    vertices at specific coordinates. Materials are then assigned to these vertices.

    Grid size by tier: T1=8x8, T2=10x10, T3=12x12, T4=14x14
    Coordinate range: -7 to +7 (origin at 0,0)

    Available shapes by tier (cumulative):
    - T1: triangle_equilateral_small, square_small
    - T2: + triangle_isosceles_small
    - T3: + triangle_equilateral_large, square_large
    - T4: + triangle_isosceles_large

    Recipe matching validates both shapes AND vertex materials.
    """

    # Shape vertex templates (offsets from anchor point)
    SHAPE_TEMPLATES = {
        # Small shapes (2-3 units)
        "triangle_equilateral_small": [(0, 0), (-1, -2), (1, -2)],  # Width 2, height 2
        "square_small": [(0, 0), (2, 0), (2, -2), (0, -2)],  # Side length 2
        "triangle_isosceles_small": [(0, 0), (-1, -3), (1, -3)],  # Width 2, height 3

        # Large shapes (4-6 units)
        "triangle_equilateral_large": [(0, 0), (-2, -3), (2, -3)],  # Width 4, height 3
        "square_large": [(0, 0), (4, 0), (4, -4), (0, -4)],  # Side length 4
        "triangle_isosceles_large": [(0, 0), (-1, -5), (1, -5)],  # Width 2, height 5
    }

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)

        # Grid configuration
        grid_sizes = {1: 8, 2: 10, 3: 12, 4: 14}
        self.grid_size = grid_sizes.get(station_tier, 8)
        self.grid_template = f'square_{self.grid_size}x{self.grid_size}'
        self.coordinate_range = 7

        # Shape and vertex storage
        self.shapes: List[Dict[str, Any]] = []  # [{type, anchor, rotation, vertices}]
        self.vertices: Dict[str, PlacedMaterial] = {}  # "x,y" -> PlacedMaterial

        # UI state
        self.selected_shape_type: Optional[str] = None
        self.selected_rotation: int = 0  # degrees (0, 45, 90, 135, 180, 225, 270, 315)

    def get_available_shapes(self) -> List[str]:
        """Get available shape types for this tier (cumulative)"""
        shapes = []
        if self.station_tier >= 1:
            shapes.extend(["triangle_equilateral_small", "square_small"])
        if self.station_tier >= 2:
            shapes.append("triangle_isosceles_small")
        if self.station_tier >= 3:
            shapes.extend(["triangle_equilateral_large", "square_large"])
        if self.station_tier >= 4:
            shapes.append("triangle_isosceles_large")
        return shapes

    @staticmethod
    def rotate_point(x: int, y: int, degrees: int) -> Tuple[int, int]:
        """Rotate a point around origin by degrees"""
        import math
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        new_x = round(x * cos_a - y * sin_a)
        new_y = round(x * sin_a + y * cos_a)
        return (new_x, new_y)

    def get_shape_vertices(self, shape_type: str, anchor_x: int, anchor_y: int, rotation: int) -> List[Tuple[int, int]]:
        """Get absolute vertices for a shape at anchor position with rotation"""
        if shape_type not in self.SHAPE_TEMPLATES:
            return []

        template = self.SHAPE_TEMPLATES[shape_type]
        vertices = []
        for dx, dy in template:
            # Rotate offset around origin
            rx, ry = self.rotate_point(dx, dy, rotation)
            # Add anchor position
            vertices.append((anchor_x + rx, anchor_y + ry))
        return vertices

    def place_shape(self, shape_type: str, anchor_x: int, anchor_y: int, rotation: int = 0) -> bool:
        """Place a geometric shape at anchor position"""
        if shape_type not in self.get_available_shapes():
            return False

        # Get shape vertices
        vertices = self.get_shape_vertices(shape_type, anchor_x, anchor_y, rotation)

        # Validate all vertices fit in grid
        for vx, vy in vertices:
            if not (-self.coordinate_range <= vx <= self.coordinate_range and
                    -self.coordinate_range <= vy <= self.coordinate_range):
                return False

        # Add shape
        shape_data = {
            "type": shape_type,
            "anchor": (anchor_x, anchor_y),
            "rotation": rotation,
            "vertices": [f"{v[0]},{v[1]}" for v in vertices]
        }
        self.shapes.append(shape_data)

        # Activate vertices (create empty slots for material assignment)
        for vx, vy in vertices:
            coord_key = f"{vx},{vy}"
            if coord_key not in self.vertices:
                # Don't create a PlacedMaterial yet - just mark vertex as available
                pass

        return True

    def remove_shape(self, shape_index: int) -> bool:
        """Remove a shape by index"""
        if not (0 <= shape_index < len(self.shapes)):
            return False

        shape = self.shapes[shape_index]
        shape_vertices = set(shape['vertices'])

        # Check if any other shape uses these vertices
        other_shapes_vertices = set()
        for i, s in enumerate(self.shapes):
            if i != shape_index:
                other_shapes_vertices.update(s['vertices'])

        # Remove materials from vertices not used by other shapes
        vertices_to_clear = shape_vertices - other_shapes_vertices
        for coord_key in vertices_to_clear:
            if coord_key in self.vertices:
                mat = self.vertices[coord_key]
                self.return_material(mat.item_id, mat.quantity)
                del self.vertices[coord_key]

        # Remove shape
        self.shapes.pop(shape_index)
        self.matched_recipe = self.check_recipe_match()
        return True

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """
        Position is a tuple (x, y) in Cartesian coordinates.
        Materials can only be placed at vertices that are part of a shape.
        """
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        x, y = position
        coord_key = f"{x},{y}"

        # Check if this coordinate is part of any shape
        is_valid_vertex = False
        for shape in self.shapes:
            if coord_key in shape['vertices']:
                is_valid_vertex = True
                break

        if not is_valid_vertex:
            return False

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
        """Remove material from a vertex"""
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
        """Clear all shapes and materials"""
        for coord_key, mat in list(self.vertices.items()):
            self.return_material(mat.item_id, mat.quantity)
        self.vertices.clear()
        self.shapes.clear()
        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """
        Match against adornment recipes using shape-based pattern matching.
        Validates both shapes AND vertex materials.
        """
        if not self.shapes or not self.vertices:
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Build current placement
        current_vertices = {
            coord_key: mat.item_id for coord_key, mat in self.vertices.items()
        }

        # Normalize shapes for comparison (sort by vertices to handle order differences)
        def normalize_shape(shape):
            return {
                'type': shape['type'],
                'rotation': shape['rotation'],
                'vertices': tuple(sorted(shape['vertices']))
            }

        current_shapes_normalized = [normalize_shape(s) for s in self.shapes]
        current_shapes_normalized.sort(key=lambda s: (s['type'], s['rotation'], s['vertices']))

        # Get all adornment recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'adornments':
                continue

            if not placement.placement_map:
                continue

            # Check shapes match
            required_shapes = placement.placement_map.get('shapes', [])
            required_shapes_normalized = [normalize_shape(s) for s in required_shapes]
            required_shapes_normalized.sort(key=lambda s: (s['type'], s['rotation'], s['vertices']))

            if current_shapes_normalized != required_shapes_normalized:
                continue

            # Check vertices match
            required_vertices = placement.placement_map.get('vertices', {})

            # Only check vertices that have materials assigned
            # Required vertices should have materialId
            required_materials = {
                coord: data['materialId']
                for coord, data in required_vertices.items()
                if data.get('materialId')
            }

            if current_vertices == required_materials:
                return recipe

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        """Get current placement data for rendering"""
        return {
            'type': 'adornments',
            'grid_size': self.grid_size,
            'grid_template': self.grid_template,
            'coordinate_range': self.coordinate_range,
            'shapes': self.shapes,
            'vertices': self.vertices,
            'available_shapes': self.get_available_shapes()
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
