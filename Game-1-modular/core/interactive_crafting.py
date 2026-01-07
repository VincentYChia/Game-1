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
        """
        mat_db = MaterialDatabase.get_instance()
        available = []

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
    Hub-and-spoke model for refining:
          [0]
           |
    [5]--[CORE]--[1]
           |
         [2]
    [4]     [3]
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        self.core_slot: Optional[PlacedMaterial] = None
        self.surrounding_slots: List[Optional[PlacedMaterial]] = [None] * 6

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position can be 'core' or an index 0-5 for surrounding slots"""
        if position == 'core':
            # Return previous material if exists
            if self.core_slot:
                self.return_material(self.core_slot.item_id, self.core_slot.quantity)

            # Borrow new material
            if self.borrow_material(item_stack.item_id, 1):
                self.core_slot = PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                )
                self.matched_recipe = self.check_recipe_match()
                return True

        elif isinstance(position, int) and 0 <= position < 6:
            # Return previous material if exists
            if self.surrounding_slots[position]:
                old = self.surrounding_slots[position]
                self.return_material(old.item_id, old.quantity)

            # Borrow new material
            if self.borrow_material(item_stack.item_id, 1):
                self.surrounding_slots[position] = PlacedMaterial(
                    item_id=item_stack.item_id,
                    quantity=1,
                    crafted_stats=item_stack.crafted_stats,
                    rarity=item_stack.rarity
                )
                self.matched_recipe = self.check_recipe_match()
                return True

        return False

    def remove_material(self, position: Any) -> Optional[PlacedMaterial]:
        if position == 'core' and self.core_slot:
            mat = self.core_slot
            self.return_material(mat.item_id, mat.quantity)
            self.core_slot = None
            self.matched_recipe = self.check_recipe_match()
            return mat

        elif isinstance(position, int) and 0 <= position < 6:
            if self.surrounding_slots[position]:
                mat = self.surrounding_slots[position]
                self.return_material(mat.item_id, mat.quantity)
                self.surrounding_slots[position] = None
                self.matched_recipe = self.check_recipe_match()
                return mat

        return None

    def clear_placement(self):
        if self.core_slot:
            self.return_material(self.core_slot.item_id, self.core_slot.quantity)
            self.core_slot = None

        for i in range(6):
            if self.surrounding_slots[i]:
                mat = self.surrounding_slots[i]
                self.return_material(mat.item_id, mat.quantity)
                self.surrounding_slots[i] = None

        self.matched_recipe = None

    def check_recipe_match(self) -> Optional[Recipe]:
        """Match against refining recipes"""
        if not self.core_slot:
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Get all refining recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'refining':
                continue

            # Match core inputs
            core_match = False
            if placement.core_inputs:
                for core_input in placement.core_inputs:
                    if core_input.get('materialId') == self.core_slot.item_id:
                        core_match = True
                        break

            if not core_match:
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
            'core': self.core_slot,
            'surrounding': self.surrounding_slots
        }


class InteractiveAlchemyUI(InteractiveBaseUI):
    """
    Sequential slots model for alchemy:
    [Slot 0] -> [Slot 1] -> [Slot 2] -> [Result]
       Base      Reagent    Catalyst
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        # More slots at higher tiers (3 + tier)
        num_slots = min(3 + station_tier, 7)
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
    [Core] [Core]        <- Core components
    [Spring] [Gear]      <- Mechanical parts
    [Wiring]             <- Optional enhancements
    """

    SLOT_TYPES = ['core', 'spring', 'gear', 'wiring', 'enhancement']

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
    Grid size depends on station tier (T1=4x4, T2=5x5, T3=6x6, T4=6x6)
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        self.grid_size = min(3 + station_tier, 6)  # T1=4, T2=5, T3=6, T4=6
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
    Grid-based placement with pattern support for adornments/enchanting.
    Similar to smithing but with vertex-based patterns.
    """

    def __init__(self, station_type: str, station_tier: int, inventory: Inventory):
        super().__init__(station_type, station_tier, inventory)
        self.grid_size = min(3 + station_tier, 6)
        self.grid: Dict[Tuple[int, int], PlacedMaterial] = {}

    def place_material(self, position: Any, item_stack: ItemStack) -> bool:
        """Position is a tuple (x, y)"""
        if not isinstance(position, tuple) or len(position) != 2:
            return False

        x, y = position
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False

        # Return previous material if exists
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
        """Match against adornment recipes - supports both grid and pattern matching"""
        if not self.grid:
            return None

        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        # Convert current grid to string-key format
        current_placement = {
            f"{x},{y}": mat.item_id for (x, y), mat in self.grid.items()
        }

        # Get all adornment recipes for this tier
        recipes = recipe_db.get_recipes_for_station(self.station_type, self.station_tier)

        for recipe in recipes:
            placement = placement_db.get_placement(recipe.recipe_id)
            if not placement or placement.discipline != 'adornments':
                continue

            # Try grid-based match first
            if placement.placement_map and current_placement == placement.placement_map:
                return recipe

            # TODO: Pattern-based matching for complex enchantments
            # This would involve checking placement.pattern for vertex-based shapes

        return None

    def get_placement_data(self) -> Dict[str, Any]:
        return {
            'type': 'adornments',
            'grid_size': self.grid_size,
            'grid': self.grid
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
