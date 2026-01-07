"""
Interactive Crafting UI System

Allows players to manually place materials on grids/patterns to discover and execute recipes.
Material palette organized by tier → category → alphabetically.

STRUCTURE:
- Smithing: Grid-based placement (4x4 to 6x6)
- Refining: Hub-and-spoke (core slots + surrounding slots)
- Alchemy: Sequential slots (order matters)
- Engineering: Slot-type system (FRAME, POWER, FUNCTION, MODIFIER, UTILITY, etc)
- Adornments: Grid-based placement (4x4 to 6x6)
"""

from typing import Dict, List, Optional, Tuple, Any
from entities.components.inventory import ItemStack
from data.databases import (
    MaterialDatabase, RecipeDatabase, PlacementDatabase, EquipmentDatabase
)
from data.models import Recipe


MATERIAL_CATEGORIES_ORDER = ["metal", "wood", "stone", "elemental", "monster_drop"]


class InteractiveBaseUI:
    """Base class for all interactive crafting UIs"""

    def __init__(self, character, station_tier: int, discipline: str):
        self.character = character
        self.station_tier = station_tier
        self.discipline = discipline
        self.matched_recipe: Optional[Recipe] = None
        self.mat_db = MaterialDatabase.get_instance()
        self.recipe_db = RecipeDatabase.get_instance()
        self.placement_db = PlacementDatabase.get_instance()
        self.equip_db = EquipmentDatabase.get_instance()

    def get_available_materials(self) -> List[ItemStack]:
        """
        Get materials from inventory organized by tier, category, then alphabetically.
        Filter by station tier and exclude equipment.
        """
        available = []

        # Collect all eligible materials from inventory
        for slot in self.character.inventory.slots:
            if not slot or slot.quantity <= 0:
                continue

            # Skip equipment items
            if slot.is_equipment():
                continue

            mat_def = self.mat_db.get_material(slot.item_id)
            if not mat_def:
                continue

            # Check tier restriction
            if mat_def.tier > self.station_tier:
                continue

            available.append(slot)

        # Sort by: tier (asc) → category (custom order) → name (asc)
        def sort_key(item_stack):
            mat = self.mat_db.get_material(item_stack.item_id)
            if not mat:
                return (999, 999, "")

            tier = mat.tier
            category = mat.category or "unknown"

            # Get category order index
            try:
                cat_index = MATERIAL_CATEGORIES_ORDER.index(category)
            except ValueError:
                cat_index = len(MATERIAL_CATEGORIES_ORDER)

            name = mat.name or ""
            return (tier, cat_index, name)

        available.sort(key=sort_key)
        return available

    def clear_placement(self):
        """Clear all placed materials"""
        self.matched_recipe = None

    def _check_recipe_match(self):
        """Override in subclass to check if current placement matches any recipe"""
        raise NotImplementedError


class InteractiveSmithingUI(InteractiveBaseUI):
    """Interactive UI for smithing (grid-based placement)"""

    def __init__(self, character, station_tier: int):
        super().__init__(character, station_tier, "smithing")
        self.grid_size = min(3 + station_tier, 6)  # T1=4x4, T2=5x5, T3=6x6, T4=6x6
        self.grid: Dict[Tuple[int, int], str] = {}  # (x,y) -> material_id

    def place_material(self, grid_pos: Tuple[int, int], material_id: str) -> bool:
        """Place a material at a grid position"""
        x, y = grid_pos

        # Validate position
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False

        # Check material exists and has inventory quantity
        mat = self.mat_db.get_material(material_id)
        if not mat or mat.tier > self.station_tier:
            return False

        if self.character.inventory.get_item_count(material_id) <= 0:
            return False

        # Place material
        self.grid[grid_pos] = material_id
        self._check_recipe_match()
        return True

    def remove_material(self, grid_pos: Tuple[int, int]) -> bool:
        """Remove material from grid position"""
        if grid_pos in self.grid:
            del self.grid[grid_pos]
            self._check_recipe_match()
            return True
        return False

    def _check_recipe_match(self):
        """Check if current grid matches any smithing recipe"""
        self.matched_recipe = None

        # Get all smithing recipes at this tier
        recipes = self.recipe_db.get_recipes_for_station("smithing", self.station_tier)

        for recipe in recipes:
            placement_data = self.placement_db.get_placement(recipe.recipe_id)
            if not placement_data:
                continue

            # Check if grid matches this recipe's placement_map
            if self._grids_match(self.grid, placement_data.placement_map):
                self.matched_recipe = recipe
                return

    def _grids_match(self, placed: Dict[Tuple[int, int], str],
                    template: Dict[str, str]) -> bool:
        """Check if placed grid matches template placement_map"""
        if len(placed) != len(template):
            return False

        # Convert template keys to tuples for comparison
        template_positions = {}
        for key_str, mat_id in template.items():
            try:
                parts = key_str.split(",")
                pos = (int(parts[0]), int(parts[1]))
                template_positions[pos] = mat_id
            except (ValueError, IndexError):
                return False

        # Check each position matches
        for pos, mat_id in placed.items():
            if template_positions.get(pos) != mat_id:
                return False

        return True

    def get_grid_contents(self) -> Dict[Tuple[int, int], str]:
        """Get current grid contents"""
        return self.grid.copy()


class InteractiveRefiningUI(InteractiveBaseUI):
    """Interactive UI for refining (hub-and-spoke model)"""

    def __init__(self, character, station_tier: int):
        super().__init__(character, station_tier, "refining")
        # T1: 1 core, T2: 1 core, T3: 2 cores, T4: 3 cores
        num_cores = 1 if station_tier <= 2 else (2 if station_tier == 3 else 3)
        # T1: 2 surrounding, T2: 4 surrounding, T3: 5 surrounding, T4: 6 surrounding
        num_surrounding = [2, 4, 5, 6][station_tier - 1]

        self.core_slots: List[Optional[str]] = [None] * num_cores
        self.surrounding_slots: List[Optional[str]] = [None] * num_surrounding

    def place_core(self, core_index: int, material_id: str) -> bool:
        """Place material in core slot"""
        if not (0 <= core_index < len(self.core_slots)):
            return False

        if material_id is None:
            self.core_slots[core_index] = None
        else:
            if not self._validate_material(material_id):
                return False
            self.core_slots[core_index] = material_id

        self._check_recipe_match()
        return True

    def place_surrounding(self, slot_index: int, material_id: str) -> bool:
        """Place material in surrounding slot"""
        if not (0 <= slot_index < len(self.surrounding_slots)):
            return False

        if material_id is None:
            self.surrounding_slots[slot_index] = None
        else:
            if not self._validate_material(material_id):
                return False
            self.surrounding_slots[slot_index] = material_id

        self._check_recipe_match()
        return True

    def _validate_material(self, material_id: str) -> bool:
        """Check if material exists and is available"""
        mat = self.mat_db.get_material(material_id)
        if not mat or mat.tier > self.station_tier:
            return False

        if self.character.inventory.get_item_count(material_id) <= 0:
            return False

        return True

    def _check_recipe_match(self):
        """Check if current placement matches any refining recipe"""
        self.matched_recipe = None

        # Get all refining recipes
        recipes = self.recipe_db.get_recipes_for_station("refining", self.station_tier)

        for recipe in recipes:
            placement_data = self.placement_db.get_placement(recipe.recipe_id)
            if not placement_data:
                continue

            # Check if placement matches
            if self._refining_matches(placement_data):
                self.matched_recipe = recipe
                return

    def _refining_matches(self, placement_data) -> bool:
        """Check if refining placement matches"""
        if not placement_data.core_inputs:
            return False

        # Get non-None core slots
        filled_cores = [mat for mat in self.core_slots if mat is not None]

        # Get expected core inputs
        expected_cores = [inp.get("materialId") for inp in placement_data.core_inputs]

        # Core slots must match exactly
        if len(filled_cores) != len(expected_cores):
            return False

        if sorted(filled_cores) != sorted(expected_cores):
            return False

        # Surrounding: any subset of expected materials is acceptable
        filled_surrounding = [mat for mat in self.surrounding_slots if mat is not None]
        expected_surrounding = [inp.get("materialId") for inp in placement_data.surrounding_inputs]

        # If we placed surrounding, they must be from expected list
        for placed_mat in filled_surrounding:
            if placed_mat not in expected_surrounding:
                return False

        return True

    def get_placement(self) -> Dict[str, Any]:
        """Get current placement state"""
        return {
            "cores": self.core_slots.copy(),
            "surrounding": self.surrounding_slots.copy()
        }


class InteractiveAlchemyUI(InteractiveBaseUI):
    """Interactive UI for alchemy (sequential slots)"""

    def __init__(self, character, station_tier: int):
        super().__init__(character, station_tier, "alchemy")
        # T1: 3 slots, T2: 5 slots, T3: 7 slots, T4: 9 slots
        num_slots = [3, 5, 7, 9][station_tier - 1]
        self.slots: List[Optional[str]] = [None] * num_slots

    def place_in_slot(self, slot_index: int, material_id: str) -> bool:
        """Place material in sequential slot"""
        if not (0 <= slot_index < len(self.slots)):
            return False

        if material_id is None:
            self.slots[slot_index] = None
        else:
            if not self._validate_material(material_id):
                return False
            self.slots[slot_index] = material_id

        self._check_recipe_match()
        return True

    def _validate_material(self, material_id: str) -> bool:
        """Check if material exists and is available"""
        mat = self.mat_db.get_material(material_id)
        if not mat or mat.tier > self.station_tier:
            return False

        if self.character.inventory.get_item_count(material_id) <= 0:
            return False

        return True

    def _check_recipe_match(self):
        """Check if current placement matches any alchemy recipe"""
        self.matched_recipe = None

        # Get all alchemy recipes
        recipes = self.recipe_db.get_recipes_for_station("alchemy", self.station_tier)

        for recipe in recipes:
            placement_data = self.placement_db.get_placement(recipe.recipe_id)
            if not placement_data:
                continue

            # Check if ingredients match
            if self._alchemy_matches(placement_data):
                self.matched_recipe = recipe
                return

    def _alchemy_matches(self, placement_data) -> bool:
        """Check if alchemy placement matches"""
        if not placement_data.ingredients:
            return False

        # Build map of slot -> expected material from placement data
        expected_map = {}
        for ing in placement_data.ingredients:
            slot_num = ing.get("slot", 0)  # 1-indexed in JSON
            mat_id = ing.get("materialId")
            expected_map[slot_num] = mat_id

        # Check our placement against expected
        for slot_num, expected_mat in expected_map.items():
            # Convert to 0-indexed for our array
            actual_mat = self.slots[slot_num - 1] if slot_num - 1 < len(self.slots) else None
            if actual_mat != expected_mat:
                return False

        # Check that we don't have extra materials in slots not in recipe
        for slot_num, actual_mat in enumerate(self.slots):
            if actual_mat is not None and (slot_num + 1) not in expected_map:
                return False

        return True

    def get_placement(self) -> List[Optional[str]]:
        """Get current placement state"""
        return self.slots.copy()


class InteractiveEngineeringUI(InteractiveBaseUI):
    """Interactive UI for engineering (slot-type system)"""

    SLOT_TYPES = ["FRAME", "POWER", "FUNCTION", "MODIFIER", "UTILITY", "ENHANCEMENT", "CATALYST"]

    def __init__(self, character, station_tier: int):
        super().__init__(character, station_tier, "engineering")
        # T1-T2: 3 slot types (FRAME, POWER, FUNCTION)
        # T3: 5 slot types (add MODIFIER, UTILITY)
        # T4: 7 slot types (add ENHANCEMENT, CATALYST)
        max_slots = [3, 3, 5, 7][station_tier - 1]
        self.available_types = self.SLOT_TYPES[:max_slots]

        # Store placed materials: type -> list of material_ids
        self.slots: Dict[str, List[str]] = {slot_type: [] for slot_type in self.available_types}

    def place_in_slot_type(self, slot_type: str, material_id: str) -> bool:
        """Place material in a slot type"""
        if slot_type not in self.slots:
            return False

        if not self._validate_material(material_id):
            return False

        self.slots[slot_type].append(material_id)
        self._check_recipe_match()
        return True

    def _validate_material(self, material_id: str) -> bool:
        """Check if material exists and is available"""
        mat = self.mat_db.get_material(material_id)
        if not mat or mat.tier > self.station_tier:
            return False

        if self.character.inventory.get_item_count(material_id) <= 0:
            return False

        return True

    def _check_recipe_match(self):
        """Check if current placement matches any engineering recipe"""
        self.matched_recipe = None

        # Get all engineering recipes
        recipes = self.recipe_db.get_recipes_for_station("engineering", self.station_tier)

        for recipe in recipes:
            placement_data = self.placement_db.get_placement(recipe.recipe_id)
            if not placement_data:
                continue

            # Check if slot configuration matches
            if self._engineering_matches(placement_data):
                self.matched_recipe = recipe
                return

    def _engineering_matches(self, placement_data) -> bool:
        """Check if engineering placement matches"""
        if not placement_data.slots:
            return False

        # Build expected configuration from placement data
        expected_by_type: Dict[str, List[str]] = {}
        for slot_spec in placement_data.slots:
            slot_type = slot_spec.get("type", "FRAME")
            mat_id = slot_spec.get("materialId")

            if slot_type not in expected_by_type:
                expected_by_type[slot_type] = []
            if mat_id not in expected_by_type[slot_type]:
                expected_by_type[slot_type].append(mat_id)

        # Check if our placement matches
        for slot_type in self.available_types:
            placed_materials = set(self.slots[slot_type])
            expected_materials = set(expected_by_type.get(slot_type, []))

            if placed_materials != expected_materials:
                return False

        return True

    def get_placement(self) -> Dict[str, List[str]]:
        """Get current placement state"""
        return {k: v.copy() for k, v in self.slots.items()}


class InteractiveAdornmentsUI(InteractiveBaseUI):
    """Interactive UI for enchanting/adornments (grid-based)"""

    def __init__(self, character, station_tier: int):
        super().__init__(character, station_tier, "adornments")
        self.grid_size = min(3 + station_tier, 6)  # T1=4x4, T2=5x5, T3=6x6, T4=6x6
        self.grid: Dict[Tuple[int, int], str] = {}  # (x,y) -> material_id

    def place_material(self, grid_pos: Tuple[int, int], material_id: str) -> bool:
        """Place a material at a grid/vertex position"""
        x, y = grid_pos

        # Validate position
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False

        # Check material exists and has inventory quantity
        mat = self.mat_db.get_material(material_id)
        if not mat or mat.tier > self.station_tier:
            return False

        if self.character.inventory.get_item_count(material_id) <= 0:
            return False

        # Place material
        self.grid[grid_pos] = material_id
        self._check_recipe_match()
        return True

    def remove_material(self, grid_pos: Tuple[int, int]) -> bool:
        """Remove material from grid position"""
        if grid_pos in self.grid:
            del self.grid[grid_pos]
            self._check_recipe_match()
            return True
        return False

    def _check_recipe_match(self):
        """Check if current grid matches any adornment recipe"""
        self.matched_recipe = None

        # Get all adornment recipes at this tier
        recipes = self.recipe_db.get_recipes_for_station("adornments", self.station_tier)

        for recipe in recipes:
            placement_data = self.placement_db.get_placement(recipe.recipe_id)
            if not placement_data:
                continue

            # Check if grid matches this recipe's placement_map
            if self._grids_match(self.grid, placement_data.placement_map):
                self.matched_recipe = recipe
                return

    def _grids_match(self, placed: Dict[Tuple[int, int], str],
                    template: Dict[str, str]) -> bool:
        """Check if placed grid matches template placement_map"""
        if len(placed) != len(template):
            return False

        # Convert template keys to tuples for comparison
        template_positions = {}
        for key_str, mat_id in template.items():
            try:
                parts = key_str.split(",")
                pos = (int(parts[0]), int(parts[1]))
                template_positions[pos] = mat_id
            except (ValueError, IndexError):
                return False

        # Check each position matches
        for pos, mat_id in placed.items():
            if template_positions.get(pos) != mat_id:
                return False

        return True

    def get_grid_contents(self) -> Dict[Tuple[int, int], str]:
        """Get current grid contents"""
        return self.grid.copy()


def create_interactive_ui(discipline: str, character, station_tier: int) -> InteractiveBaseUI:
    """Factory function to create appropriate interactive UI for discipline"""
    ui_classes = {
        "smithing": InteractiveSmithingUI,
        "refining": InteractiveRefiningUI,
        "alchemy": InteractiveAlchemyUI,
        "engineering": InteractiveEngineeringUI,
        "adornments": InteractiveAdornmentsUI,
        "enchanting": InteractiveAdornmentsUI,  # Enchanting uses same as adornments
    }

    ui_class = ui_classes.get(discipline.lower())
    if not ui_class:
        raise ValueError(f"Unknown discipline: {discipline}")

    return ui_class(character, station_tier)
