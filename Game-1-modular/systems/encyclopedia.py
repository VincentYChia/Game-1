"""Encyclopedia/Compendium system for displaying game information"""

from typing import List, Dict, Any, Optional


class Encyclopedia:
    """
    Encyclopedia/Compendium that displays information about skills, titles, and game mechanics.
    This helps players understand progression and hidden systems.
    """
    def __init__(self):
        self.is_open = False
        self.current_tab = "guide"  # guide, quests, skills, titles, stats, recipes
        self.scroll_offset = 0

    def toggle(self):
        self.is_open = not self.is_open
        if self.is_open:
            self.scroll_offset = 0

    def get_invented_recipes_text(self, invented_recipes: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        Returns formatted text for invented recipes tab.

        Recipes are sorted by:
        1. Discipline (alphabetically)
        2. Tier (ascending)
        3. Name (alphabetically)

        Args:
            invented_recipes: List of recipe records from character.invented_recipes

        Returns:
            List of formatted strings for display
        """
        if not invented_recipes:
            return [
                "=== INVENTED RECIPES ===",
                "",
                "No recipes invented yet!",
                "",
                "To invent a new recipe:",
                "1. Open interactive crafting at a station",
                "2. Place materials in a new pattern",
                "3. Click INVENT to validate your creation",
                "",
                "Valid placements will generate unique items!",
            ]

        lines = [
            "=== INVENTED RECIPES ===",
            "",
            f"Total Inventions: {len(invented_recipes)}",
            "",
        ]

        # Group by discipline, then sort within groups
        by_discipline: Dict[str, List[Dict]] = {}
        for recipe in invented_recipes:
            disc = recipe.get('discipline', 'unknown')
            if disc not in by_discipline:
                by_discipline[disc] = []
            by_discipline[disc].append(recipe)

        # Display order for disciplines
        discipline_order = ['smithing', 'refining', 'alchemy', 'engineering', 'adornments']

        for disc in discipline_order:
            if disc not in by_discipline:
                continue

            recipes = by_discipline[disc]
            # Sort by tier, then by name
            recipes.sort(key=lambda r: (r.get('station_tier', 1), r.get('item_name', '')))

            # Discipline header
            disc_display = disc.upper()
            if disc == 'adornments':
                disc_display = 'ENCHANTING'

            lines.append(f"--- {disc_display} ({len(recipes)}) ---")
            lines.append("")

            for recipe in recipes:
                item_name = recipe.get('item_name', 'Unknown')
                tier = recipe.get('station_tier', 1)
                narrative = recipe.get('narrative', '')

                # Format entry
                tier_str = f"T{tier}"
                lines.append(f"  [{tier_str}] {item_name}")

                # Add item type for enchantments
                if disc in ['adornments', 'enchanting']:
                    item_data = recipe.get('item_data', {})
                    applicable = item_data.get('applicableTo', item_data.get('applicable_to', []))
                    if applicable:
                        lines.append(f"       Applies to: {', '.join(applicable)}")

                # Add brief narrative if available
                if narrative:
                    # Truncate long narratives
                    if len(narrative) > 60:
                        narrative = narrative[:57] + "..."
                    lines.append(f"       \"{narrative}\"")

                lines.append("")

        # Add unknown disciplines at the end
        for disc, recipes in by_discipline.items():
            if disc not in discipline_order:
                lines.append(f"--- {disc.upper()} ({len(recipes)}) ---")
                lines.append("")
                for recipe in recipes:
                    item_name = recipe.get('item_name', 'Unknown')
                    tier = recipe.get('station_tier', 1)
                    lines.append(f"  [T{tier}] {item_name}")
                    lines.append("")

        return lines

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
