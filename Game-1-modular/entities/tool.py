"""Tool entity class"""

from dataclasses import dataclass

from core.config import Config


@dataclass
class Tool:
    tool_id: str
    name: str
    tool_type: str
    tier: int
    damage: int
    durability_current: int
    durability_max: int
    efficiency: float = 1.0

    def can_harvest(self, resource_tier: int) -> bool:
        return self.tier >= resource_tier

    def use(self) -> bool:
        if Config.DEBUG_INFINITE_RESOURCES:
            return True
        if self.durability_current <= 0:
            return False
        self.durability_current -= 1
        return True

    def get_effectiveness(self) -> float:
        if Config.DEBUG_INFINITE_RESOURCES:
            return 1.0
        if self.durability_current <= 0:
            return 0.5
        dur_pct = self.durability_current / self.durability_max
        return 1.0 if dur_pct >= 0.5 else 1.0 - (0.5 - dur_pct) * 0.5

    def repair(self, amount: int = None):
        if amount is None:
            self.durability_current = self.durability_max
        else:
            self.durability_current = min(self.durability_max, self.durability_current + amount)
