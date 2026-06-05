"""Material definition data model"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    narrative: str = ""  # Flavor text from metadata.narrative
    tags: List[str] = field(default_factory=list)  # Descriptive tags from metadata.tags (drives UI/search/CNN input)

    # Phase 4 reverse cross-ref fields (2026-06-03). Optional; set by
    # WES generation. gather_quest_id binds the material to the quest
    # that motivated its creation (so the quest's narrative and the
    # material's narrative rhyme). inherited_from_chunk_id signals
    # the material was minted in a chunk's mixed-trigger DAG cascade
    # (Phase 5 behavior_inheritance flavor).
    gather_quest_id: Optional[str] = None
    inherited_from_chunk_id: Optional[str] = None
