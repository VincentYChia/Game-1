"""Encyclopedia/Compendium system for displaying game information"""

from typing import List


class Encyclopedia:
    """
    Encyclopedia/Compendium that displays information about skills, titles, and game mechanics.
    This helps players understand progression and hidden systems.
    """
    def __init__(self):
        self.is_open = False
        self.current_tab = "guide"  # guide, quests, skills, titles
        self.scroll_offset = 0

    def toggle(self):
        self.is_open = not self.is_open
        if self.is_open:
            self.scroll_offset = 0

    def get_game_guide_text(self) -> List[str]:
        """Returns the game guide/tutorial text as a list of paragraphs"""
        return [
            "=== WELCOME TO THE GAME ===",
            "",
            "CONTROLS:",
            "• WASD - Move your character",
            "• TAB - Cycle through tools and weapons",
            "• Left Click - Harvest resources, attack enemies, interact",
            "• C - Open character stats",
            "• E - Open equipment menu",
            "• K - Open skills menu",
            "• L - Open this encyclopedia",
            "• 1-5 - Use equipped skills",
            "• Mouse Wheel - Scroll in menus",
            "",
            "PROGRESSION:",
            "• Mine ores and chop trees to gather materials",
            "• Craft tools, weapons, and armor at stations",
            "• Gain experience to level up and unlock skills",
            "• Earn titles by completing activities",
            "• Defeat enemies to gain combat experience",
            "",
            "CRAFTING:",
            "• Approach a crafting station and click to open",
            "• Choose between instant craft (no XP) or minigame (1.5x XP)",
            "• Each discipline has a unique minigame mechanic",
            "• Higher quality outcomes give better stats and rarity",
            "",
            "SKILLS:",
            "• Skills are unlocked when you meet level and stat requirements",
            "• Open the Skills menu (K) to learn and equip skills",
            "• Equip up to 5 skills on your hotbar (keys 1-5)",
            "• Skills consume mana and have cooldowns",
            "• Skills level up as you use them (max level 10)",
            "",
            "TITLES:",
            "• Titles are earned by performing activities",
            "• Novice titles are guaranteed at thresholds",
            "• Higher tier titles have chance-based acquisition",
            "• Titles provide permanent stat bonuses",
            "• Check this encyclopedia to see all title requirements!",
        ]
