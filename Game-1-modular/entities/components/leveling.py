"""Character leveling system component"""


class LevelingSystem:
    def __init__(self):
        self.level = 1
        self.current_exp = 0
        self.max_level = 30
        self.exp_requirements = {lvl: int(200 * (1.75 ** (lvl - 1))) for lvl in range(1, self.max_level + 1)}
        self.unallocated_stat_points = 0

    def get_exp_for_next_level(self) -> int:
        return 0 if self.level >= self.max_level else self.exp_requirements.get(self.level + 1, 0)

    def add_exp(self, amount: int, source: str = "") -> bool:
        if self.level >= self.max_level:
            return False
        self.current_exp += amount
        exp_needed = self.get_exp_for_next_level()
        if self.current_exp >= exp_needed:
            self.current_exp -= exp_needed
            self.level += 1
            self.unallocated_stat_points += 1
            print(f"🎉 LEVEL UP! Now level {self.level}")
            return True
        return False
