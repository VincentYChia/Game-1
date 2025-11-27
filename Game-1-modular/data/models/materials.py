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
