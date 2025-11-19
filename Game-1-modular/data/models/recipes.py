"""Recipe and placement data models"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Recipe:
    """Crafting recipe definition"""
    recipe_id: str
    output_id: str
    output_qty: int
    station_type: str
    station_tier: int
    inputs: List[Dict]
    grid_size: str = "3x3"
    mini_game_type: str = ""
    metadata: Dict = field(default_factory=dict)
    # Enchanting-specific fields
    is_enchantment: bool = False
    enchantment_name: str = ""
    applicable_to: List[str] = field(default_factory=list)
    effect: Dict = field(default_factory=dict)


@dataclass
class PlacementData:
    """Universal placement data structure for all crafting disciplines"""
    recipe_id: str
    discipline: str  # smithing, alchemy, refining, engineering, adornments

    # Smithing & Enchanting: Grid-based placement
    grid_size: str = ""  # "3x3", "5x5", "12x12", etc.
    placement_map: Dict[str, str] = field(default_factory=dict)  # "x,y" -> materialId

    # Refining: Hub-and-spoke
    core_inputs: List[Dict] = field(default_factory=list)  # Center slots
    surrounding_inputs: List[Dict] = field(default_factory=list)  # Surrounding modifiers

    # Alchemy: Sequential
    ingredients: List[Dict] = field(default_factory=list)  # [{slot, materialId, quantity}]

    # Engineering: Slot types
    slots: List[Dict] = field(default_factory=list)  # [{type, materialId, quantity}]

    # Enchanting: Pattern-based
    pattern: List[Dict] = field(default_factory=list)  # Pattern vertices/shapes

    # Metadata
    narrative: str = ""
    output_id: str = ""
    station_tier: int = 1
