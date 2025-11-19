"""Natural resource system for harvestable world resources"""

import random
from typing import List, Tuple

from data.models import Position, ResourceType, LootDrop
from core.config import Config


class NaturalResource:
    def __init__(self, position: Position, resource_type: ResourceType, tier: int):
        self.position = position
        self.resource_type = resource_type
        self.tier = tier
        self.max_hp = {1: 100, 2: 200, 3: 400, 4: 800}.get(tier, 100)
        self.current_hp = self.max_hp

        if "tree" in resource_type.value:
            self.required_tool = "axe"
            self.respawns = True
            self.respawn_timer = 60.0 if not Config.DEBUG_INFINITE_RESOURCES else 1.0
        else:
            self.required_tool = "pickaxe"
            self.respawns = False
            self.respawn_timer = None

        self.time_until_respawn = 0.0
        self.loot_table = self._generate_loot_table()
        self.depleted = False

    def _generate_loot_table(self) -> List[LootDrop]:
        loot_map = {
            ResourceType.OAK_TREE: ("oak_log", 2, 4), ResourceType.BIRCH_TREE: ("birch_log", 2, 4),
            ResourceType.MAPLE_TREE: ("maple_log", 2, 5), ResourceType.IRONWOOD_TREE: ("ironwood_log", 3, 6),
            ResourceType.COPPER_ORE: ("copper_ore", 1, 3), ResourceType.IRON_ORE: ("iron_ore", 1, 3),
            ResourceType.STEEL_ORE: ("steel_ore", 2, 4), ResourceType.MITHRIL_ORE: ("mithril_ore", 2, 5),
            ResourceType.LIMESTONE: ("limestone", 1, 2), ResourceType.GRANITE: ("granite", 1, 2),
            ResourceType.OBSIDIAN: ("obsidian", 2, 3), ResourceType.STAR_CRYSTAL: ("star_crystal", 1, 2),
        }
        if self.resource_type in loot_map:
            item_id, min_q, max_q = loot_map[self.resource_type]
            return [LootDrop(item_id, min_q, max_q)]
        return []

    def take_damage(self, damage: int, is_crit: bool = False) -> Tuple[int, bool]:
        if self.depleted:
            return 0, False
        actual_damage = damage * 2 if is_crit else damage
        self.current_hp -= actual_damage
        if self.current_hp <= 0:
            self.current_hp = 0
            self.depleted = True
            return actual_damage, True
        return actual_damage, False

    def get_loot(self) -> List[Tuple[str, int]]:
        return [(loot.item_id, random.randint(loot.min_quantity, loot.max_quantity))
                for loot in self.loot_table if random.random() <= loot.chance]

    def update(self, dt: float):
        if self.depleted and self.respawns:
            self.time_until_respawn += dt
            if self.time_until_respawn >= self.respawn_timer:
                self.current_hp = self.max_hp
                self.depleted = False
                self.time_until_respawn = 0.0

    def get_respawn_progress(self) -> float:
        if not self.depleted or not self.respawns:
            return 0.0
        return min(1.0, self.time_until_respawn / self.respawn_timer)

    def get_color(self) -> Tuple[int, int, int]:
        if self.depleted:
            if self.respawns:
                progress = self.get_respawn_progress()
                gray = int(50 + progress * 50)
                green = int(progress * 100)
                return (gray, green, gray)
            return (50, 50, 50)
        if "tree" in self.resource_type.value:
            return Config.COLOR_TREE
        return Config.COLOR_ORE if "ore" in self.resource_type.value else Config.COLOR_STONE_NODE
