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
                # Add detailed recipe entry
                lines.extend(self._format_recipe_entry(recipe, disc))

        # Add unknown disciplines at the end
        for disc, recipes in by_discipline.items():
            if disc not in discipline_order:
                lines.append(f"--- {disc.upper()} ({len(recipes)}) ---")
                lines.append("")
                for recipe in recipes:
                    lines.extend(self._format_recipe_entry(recipe, disc))

        return lines

    def _format_recipe_entry(self, recipe: Dict[str, Any], discipline: str) -> List[str]:
        """Format a single recipe entry with full metadata, stats, and narrative."""
        lines = []

        item_name = recipe.get('item_name', 'Unknown')
        tier = recipe.get('station_tier', 1)
        item_data = recipe.get('item_data', {})
        narrative = recipe.get('narrative', '')
        recipe_inputs = recipe.get('recipe_inputs', [])

        # Extract metadata
        metadata = item_data.get('metadata', {})

        # Get rarity with fallback
        rarity = item_data.get('rarity', 'common')

        # Get type info
        category = item_data.get('category', '')
        item_type = item_data.get('type', '')
        subtype = item_data.get('subtype', '')

        # Build type string
        type_parts = [p for p in [category, item_type, subtype] if p]
        type_str = ' / '.join(type_parts) if type_parts else ''

        # Header line with tier and name
        tier_str = f"T{tier}"
        rarity_tag = f" ({rarity.title()})" if rarity and rarity != 'common' else ""
        lines.append(f"  [{tier_str}] {item_name}{rarity_tag}")

        # Type info
        if type_str:
            lines.append(f"@type       {type_str}")

        # Stats section based on discipline
        stats_lines = self._extract_stats_lines(item_data, discipline)
        for stat_line in stats_lines:
            lines.append(f"@stat       {stat_line}")

        # Effect tags
        effect_tags = item_data.get('effectTags', [])
        if not effect_tags:
            effect_tags = metadata.get('tags', [])
        if effect_tags:
            # Filter out generic tags
            display_tags = [t for t in effect_tags if t not in ['invented', 'material', 'refined']]
            if display_tags:
                lines.append(f"@tags       {', '.join(display_tags[:6])}")

        # Enchantment-specific: applicable equipment
        if discipline in ['adornments', 'enchanting']:
            applicable = item_data.get('applicableTo', item_data.get('applicable_to', []))
            if applicable:
                lines.append(f"@applies    {', '.join(applicable)}")

            # Enchantment effect
            effect = item_data.get('effect', {})
            if isinstance(effect, dict) and effect:
                effect_type = effect.get('type', '')
                effect_value = effect.get('value', 0)
                if effect_type:
                    if isinstance(effect_value, float) and effect_value < 1:
                        lines.append(f"@effect     {effect_type}: +{int(effect_value * 100)}%")
                    else:
                        lines.append(f"@effect     {effect_type}: +{effect_value}")

        # Recipe inputs (materials used)
        if recipe_inputs:
            material_names = []
            for inp in recipe_inputs[:4]:  # Limit to 4 materials
                mat_id = inp.get('materialId', inp.get('material_id', ''))
                qty = inp.get('qty', inp.get('quantity', 1))
                if mat_id:
                    # Clean up material ID for display
                    mat_name = mat_id.replace('_', ' ').title()
                    if qty > 1:
                        material_names.append(f"{mat_name} x{qty}")
                    else:
                        material_names.append(mat_name)
            if material_names:
                lines.append(f"@recipe     {', '.join(material_names)}")

        # Narrative/description - show full text, wrapped
        full_narrative = metadata.get('narrative', narrative)
        if full_narrative:
            # Word wrap narrative to ~55 chars per line
            wrapped = self._wrap_text(full_narrative, 55)
            for i, line in enumerate(wrapped[:3]):  # Max 3 lines
                if i == 0:
                    lines.append(f'@lore       "{line}')
                elif i == len(wrapped[:3]) - 1:
                    lines.append(f'@lore        {line}"')
                else:
                    lines.append(f'@lore        {line}')

        lines.append("")  # Blank line after entry
        return lines

    def _extract_stats_lines(self, item_data: Dict[str, Any], discipline: str) -> List[str]:
        """Extract key stats from item data based on discipline."""
        stats = []

        effect_params = item_data.get('effectParams', {})
        stat_multipliers = item_data.get('statMultipliers', {})

        if discipline == 'smithing':
            # Weapons/armor stats
            if 'baseDamage' in effect_params:
                stats.append(f"Damage: {effect_params['baseDamage']}")
            if 'baseDefense' in effect_params:
                stats.append(f"Defense: {effect_params['baseDefense']}")
            if 'attackSpeed' in stat_multipliers:
                speed = stat_multipliers['attackSpeed']
                if speed != 1.0:
                    stats.append(f"Speed: {speed:.1f}x")
            if 'critChance' in effect_params:
                stats.append(f"Crit: {int(effect_params['critChance'] * 100)}%")
            # Check for elemental damage
            for key in ['fire_damage', 'ice_damage', 'lightning_damage', 'poison_damage']:
                if key in effect_params:
                    element = key.replace('_damage', '').title()
                    stats.append(f"{element}: +{effect_params[key]}")

        elif discipline == 'alchemy':
            # Potion stats
            healing = effect_params.get('healing', {})
            if isinstance(healing, dict):
                if 'heal_amount' in healing:
                    stats.append(f"Heals: {healing['heal_amount']} HP")
                if 'heal_per_second' in healing:
                    stats.append(f"Regen: {healing['heal_per_second']} HP/s")
            if 'mana_restore' in effect_params:
                stats.append(f"Mana: +{effect_params['mana_restore']}")
            if 'buff_duration' in effect_params:
                stats.append(f"Duration: {effect_params['buff_duration']}s")
            if 'damage_boost' in effect_params:
                stats.append(f"Damage: +{int(effect_params['damage_boost'] * 100)}%")
            if 'defense_boost' in effect_params:
                stats.append(f"Defense: +{int(effect_params['defense_boost'] * 100)}%")

        elif discipline == 'engineering':
            # Device stats
            if 'baseDamage' in effect_params:
                stats.append(f"Damage: {effect_params['baseDamage']}")
            if 'range' in effect_params:
                stats.append(f"Range: {effect_params['range']}")
            if 'duration' in effect_params:
                stats.append(f"Duration: {effect_params['duration']}s")
            if 'cooldown' in effect_params:
                stats.append(f"Cooldown: {effect_params['cooldown']}s")
            stack_size = item_data.get('stackSize', 1)
            if stack_size > 1:
                stats.append(f"Stack: {stack_size}")

        elif discipline == 'refining':
            # Material stats
            if 'hardness' in stat_multipliers:
                stats.append(f"Hardness: {stat_multipliers['hardness']:.1f}")
            if 'conductivity' in stat_multipliers:
                stats.append(f"Conductivity: {stat_multipliers['conductivity']:.1f}")
            if 'weight' in stat_multipliers:
                weight = stat_multipliers['weight']
                if weight != 1.0:
                    stats.append(f"Weight: {weight:.1f}x")
            stack_size = item_data.get('stackSize', 1)
            if stack_size > 1:
                stats.append(f"Stack: {stack_size}")

        return stats

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """Simple word wrap for text."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

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
