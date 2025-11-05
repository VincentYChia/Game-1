"""
Rarity System Utilities

Shared utilities for the crafting rarity system.
Used by all 5 crafting subdisciplines (smithing, alchemy, refining, engineering, enchanting).

Key features:
- Check rarity uniformity (all materials must be same rarity)
- Load material rarities from items JSON
- Apply category-based rarity modifiers
- Handle special effects for epic/legendary items
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


class RaritySystem:
    """Manages rarity checking and modifier application for crafting"""

    def __init__(self):
        """Initialize rarity system by loading material rarities and modifiers"""
        self.material_rarities = {}
        self.rarity_modifiers = {}
        self._load_material_rarities()
        self._load_rarity_modifiers()

    def _load_material_rarities(self):
        """Load material rarities from items JSON"""
        materials_path = Path(__file__).parent.parent / "items.JSON" / "items-materials-1.JSON"

        try:
            with open(materials_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for material in data.get('materials', []):
                mat_id = material.get('materialId')
                rarity = material.get('rarity', 'common')
                if mat_id:
                    self.material_rarities[mat_id] = rarity

            print(f"[RaritySystem] Loaded {len(self.material_rarities)} material rarities")
        except Exception as e:
            print(f"[RaritySystem] Error loading material rarities: {e}")

    def _load_rarity_modifiers(self):
        """Load rarity modifiers from JSON"""
        modifiers_path = Path(__file__).parent / "rarity-modifiers.JSON"

        try:
            with open(modifiers_path, 'r', encoding='utf-8') as f:
                self.rarity_modifiers = json.load(f)

            print(f"[RaritySystem] Loaded rarity modifiers for {len(self.rarity_modifiers) - 1} categories")
        except Exception as e:
            print(f"[RaritySystem] Error loading rarity modifiers: {e}")

    def check_rarity_uniformity(self, inputs: List[Dict[str, Any]]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check that all input materials have the same rarity

        Args:
            inputs: List of input dicts with 'materialId' and 'quantity'

        Returns:
            Tuple of (is_uniform, rarity, error_message)
            - is_uniform: True if all materials same rarity
            - rarity: The common rarity if uniform, None otherwise
            - error_message: Error description if not uniform
        """
        if not inputs:
            return True, 'common', None

        rarities = set()
        for inp in inputs:
            mat_id = inp.get('materialId')
            rarity = self.material_rarities.get(mat_id, 'common')
            rarities.add(rarity)

        if len(rarities) > 1:
            rarity_list = ', '.join(sorted(rarities))
            return False, None, f"Mixed rarities: {rarity_list}. All materials must be the same rarity."

        return True, list(rarities)[0], None

    def get_material_rarity(self, material_id: str) -> str:
        """Get rarity for a specific material"""
        return self.material_rarities.get(material_id, 'common')

    def apply_rarity_modifiers(
        self,
        base_stats: Dict[str, Any],
        item_category: str,
        rarity: str
    ) -> Dict[str, Any]:
        """
        Apply category-based rarity modifiers to base stats

        Args:
            base_stats: Dict of base item stats (durability, damage, etc.)
            item_category: Category (weapon/armor/tool/consumable/device)
            rarity: Rarity tier (common/uncommon/rare/epic/legendary)

        Returns:
            Dict of modified stats with rarity bonuses applied
        """
        if rarity == 'common':
            # Common items have no modifiers
            return base_stats.copy()

        # Get modifiers for this category and rarity
        category_data = self.rarity_modifiers.get(item_category, {})
        rarity_data = category_data.get(rarity, {})
        modifiers = rarity_data.get('modifiers', {})
        special_effects = rarity_data.get('special_effects', {})

        if not modifiers and not special_effects:
            print(f"[RaritySystem] No modifiers found for {item_category}/{rarity}")
            return base_stats.copy()

        # Apply modifiers to stats
        modified_stats = base_stats.copy()

        for stat, bonus in modifiers.items():
            if stat in modified_stats:
                # Numerical modifiers (percentage bonuses)
                if isinstance(bonus, (int, float)) and not isinstance(bonus, bool):
                    modified_stats[stat] = int(modified_stats[stat] * (1 + bonus))

        # Add special effects as boolean flags
        if special_effects:
            modified_stats['special_effects'] = special_effects.copy()

        return modified_stats

    def get_item_category(self, item_id: str, item_metadata: Dict[str, Any]) -> str:
        """
        Determine item category from metadata

        Args:
            item_id: Item identifier
            item_metadata: Item metadata dict

        Returns:
            Category string (weapon/armor/tool/consumable/device/station)
        """
        # Check metadata for explicit category
        category = item_metadata.get('category', '').lower()

        # Map various category names to our 5 main categories
        category_mapping = {
            'weapon': 'weapon',
            'sword': 'weapon',
            'axe': 'weapon',
            'bow': 'weapon',
            'staff': 'weapon',
            'armor': 'armor',
            'helmet': 'armor',
            'chestplate': 'armor',
            'leggings': 'armor',
            'boots': 'armor',
            'shield': 'armor',
            'tool': 'tool',
            'pickaxe': 'tool',
            'axe': 'tool',
            'shovel': 'tool',
            'hoe': 'tool',
            'consumable': 'consumable',
            'potion': 'consumable',
            'food': 'consumable',
            'elixir': 'consumable',
            'device': 'device',
            'turret': 'device',
            'trap': 'device',
            'machine': 'device',
            'station': 'station',
            'workbench': 'station',
            'furnace': 'station',
        }

        mapped_category = category_mapping.get(category, None)

        if mapped_category:
            return mapped_category

        # Fallback: try to infer from item_id
        item_lower = item_id.lower()

        if any(word in item_lower for word in ['sword', 'axe', 'bow', 'staff', 'dagger', 'spear']):
            return 'weapon'
        elif any(word in item_lower for word in ['armor', 'helmet', 'chestplate', 'leggings', 'boots', 'shield']):
            return 'armor'
        elif any(word in item_lower for word in ['pickaxe', 'shovel', 'hoe']):
            return 'tool'
        elif any(word in item_lower for word in ['potion', 'elixir', 'tonic', 'brew']):
            return 'consumable'
        elif any(word in item_lower for word in ['turret', 'trap', 'device', 'machine']):
            return 'device'
        elif any(word in item_lower for word in ['station', 'workbench', 'furnace', 'anvil']):
            return 'station'

        # Default to weapon if can't determine
        print(f"[RaritySystem] Could not determine category for {item_id}, defaulting to 'weapon'")
        return 'weapon'

    def format_item_display_name(self, base_name: str, rarity: str) -> str:
        """
        Format item name with rarity

        Args:
            base_name: Base item name (e.g., "Iron Sword")
            rarity: Rarity tier

        Returns:
            Formatted name (e.g., "Iron Sword (Rare)")
        """
        if rarity == 'common':
            return base_name
        return f"{base_name} ({rarity.capitalize()})"

    def get_rarity_color(self, rarity: str) -> tuple:
        """
        Get display color for rarity tier

        Args:
            rarity: Rarity tier

        Returns:
            RGB color tuple
        """
        colors = {
            'common': (200, 200, 200),     # Gray
            'uncommon': (100, 255, 100),   # Green
            'rare': (100, 150, 255),       # Blue
            'epic': (200, 100, 255),       # Purple
            'legendary': (255, 165, 0)     # Orange
        }
        return colors.get(rarity, (255, 255, 255))


# Global instance for easy import
rarity_system = RaritySystem()
