"""Material definition data model"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class MaterialDefinition:
    """Definition for a material item (stackable resources, consumables, etc.)"""
    material_id: str
    name: str
    tier: int
    category: str  # wood, ore, stone, metal, elemental, monster_drop, consumable, device, etc.
    rarity: str    # common, uncommon, rare, epic, legendary, artifact
    description: str = ""
    max_stack: int = 99
    properties: Dict = field(default_factory=dict)
    icon_path: Optional[str] = None  # Optional path to item icon image (PNG/JPG)
    placeable: bool = False  # Can this item be placed in the world?
    item_type: str = ""  # turret, trap, bomb, utility, station, etc.
    item_subtype: str = ""  # projectile, area, elemental, etc.
    effect: str = ""  # Description of what the item does when used/placed
    effect_tags: list = field(default_factory=list)  # Combat effect tags (fire, cone, burn, etc.)
    effect_params: dict = field(default_factory=dict)  # Effect parameters (baseDamage, cone_angle, etc.)
