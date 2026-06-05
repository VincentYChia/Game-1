"""Resource node data crafting_classifier_models - loaded from JSON"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ResourceDrop:
    """A single drop from a resource node"""
    material_id: str
    quantity: str  # Qualitative: "few", "several", "many", "abundant"
    chance: str  # Qualitative: "guaranteed", "high", "moderate", "low", "rare", "improbable"

    def get_quantity_range(self) -> tuple:
        """Convert qualitative quantity to numeric range"""
        quantity_map = {
            "few": (1, 2),
            "several": (2, 4),
            "many": (3, 5),
            "abundant": (4, 8)
        }
        return quantity_map.get(self.quantity, (1, 3))

    def get_chance_value(self) -> float:
        """Convert qualitative chance to float 0.0-1.0"""
        chance_map = {
            "guaranteed": 1.0,
            "high": 0.8,
            "moderate": 0.5,
            "low": 0.25,
            "rare": 0.1,
            "improbable": 0.05
        }
        return chance_map.get(self.chance, 1.0)


@dataclass
class ResourceNodeDefinition:
    """Definition of a harvestable resource node from JSON"""
    resource_id: str
    name: str
    category: str  # "tree", "ore", "stone"
    tier: int
    required_tool: str  # "axe", "pickaxe"
    base_health: int
    drops: List[ResourceDrop] = field(default_factory=list)
    respawn_time: Optional[str] = None  # "quick"/"fast"/"normal"/"slow"/"very_slow", or None (no respawn)
    tags: List[str] = field(default_factory=list)
    narrative: str = ""

    # Phase 4 reverse cross-ref field (2026-06-03). Optional; set by
    # WES generation when the node was minted in a chunk's mixed-trigger
    # DAG cascade (Phase 5 behavior_inheritance flavor).
    inherited_from_chunk_id: Optional[str] = None

    def get_respawn_seconds(self) -> Optional[float]:
        """Convert qualitative respawn time to seconds.

        Phase 0 G18.4 fix (2026-06-03): added ``"quick"`` synonym for
        ``"fast"`` because the sacred ``resource-node-1.JSON`` uses
        ``"quick"`` 9 times. Without this entry, those 9 sacred nodes
        silently fell through to the default 60 s ("normal") respawn —
        e.g., basic oak trees respawning at twice their intended rate.
        Sacred files remain untouched per CLAUDE.md sacred-boundary
        policy; the synonym lives in code.
        """
        if self.respawn_time is None:
            return None
        respawn_map = {
            "quick": 30.0,
            "fast": 30.0,
            "normal": 60.0,
            "slow": 120.0,
            "very_slow": 300.0,
        }
        return respawn_map.get(self.respawn_time, 60.0)

    def does_respawn(self) -> bool:
        """Check if this resource respawns"""
        return self.respawn_time is not None

    @property
    def is_tree(self) -> bool:
        return self.category == "tree"

    @property
    def is_ore(self) -> bool:
        return self.category == "ore"

    @property
    def is_stone(self) -> bool:
        return self.category == "stone"
