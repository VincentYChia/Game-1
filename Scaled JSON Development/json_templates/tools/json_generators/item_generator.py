"""
Item Generator - Generate equipment items in bulk

This tool helps create large numbers of equipment items with variations in:
- Tiers (1-4)
- Materials (copper, iron, steel, mithril, etc.)
- Item types (swords, axes, armor pieces, etc.)
- Rarities (common, uncommon, rare, epic, legendary)
"""

import json
from typing import List, Dict, Any


class ItemGenerator:
    """Generate equipment item JSON definitions"""

    # Base stat multipliers by tier
    TIER_MULTIPLIERS = {
        1: 1.0,
        2: 2.0,
        3: 4.0,
        4: 8.0
    }

    # Rarity multipliers
    RARITY_MULTIPLIERS = {
        'common': 1.0,
        'uncommon': 1.2,
        'rare': 1.5,
        'epic': 2.0,
        'legendary': 3.0,
        'artifact': 5.0
    }

    # Item type stats
    WEAPON_TYPES = {
        'sword': {'damage_mult': 1.0, 'attack_speed': 1.0},
        'axe': {'damage_mult': 1.1, 'attack_speed': 0.9},
        'spear': {'damage_mult': 1.05, 'attack_speed': 1.1},
        'mace': {'damage_mult': 1.15, 'attack_speed': 0.8},
        'dagger': {'damage_mult': 0.8, 'attack_speed': 1.4},
    }

    ARMOR_SLOTS = {
        'helmet': {'defense_mult': 0.8},
        'chestplate': {'defense_mult': 1.5},
        'leggings': {'defense_mult': 1.2},
        'boots': {'defense_mult': 0.7},
        'gauntlets': {'defense_mult': 0.6},
    }

    def generate_weapon_series(self,
                               weapon_type: str,
                               materials: List[str],
                               tiers: List[int] = [1, 2, 3, 4],
                               rarities: List[str] = ['common']) -> List[Dict[str, Any]]:
        """
        Generate a series of weapons across tiers and materials

        Example:
            generate_weapon_series('sword', ['copper', 'iron', 'steel'], [1, 2, 3])
            -> Creates copper_sword_t1, iron_sword_t2, steel_sword_t3
        """
        items = []

        for i, (material, tier) in enumerate(zip(materials, tiers)):
            for rarity in rarities:
                item_id = f"{material}_{weapon_type}_t{tier}"
                if rarity != 'common':
                    item_id += f"_{rarity}"

                item = self._create_weapon(item_id, material, weapon_type, tier, rarity)
                items.append(item)

        return items

    def generate_armor_series(self,
                              materials: List[str],
                              tiers: List[int] = [1, 2, 3, 4]) -> List[Dict[str, Any]]:
        """Generate complete armor sets across tiers"""
        items = []

        for material, tier in zip(materials, tiers):
            for slot in self.ARMOR_SLOTS.keys():
                item_id = f"{material}_{slot}_t{tier}"
                item = self._create_armor(item_id, material, slot, tier)
                items.append(item)

        return items

    def _create_weapon(self, item_id: str, material: str, weapon_type: str,
                       tier: int, rarity: str = 'common') -> Dict[str, Any]:
        """Create a single weapon item definition"""
        base_damage = 10
        tier_mult = self.TIER_MULTIPLIERS.get(tier, 1.0)
        rarity_mult = self.RARITY_MULTIPLIERS.get(rarity, 1.0)
        type_mult = self.WEAPON_TYPES.get(weapon_type, {}).get('damage_mult', 1.0)

        min_damage = int(base_damage * tier_mult * type_mult * rarity_mult * 0.85)
        max_damage = int(base_damage * tier_mult * type_mult * rarity_mult * 1.15)

        durability = int(400 * tier_mult)
        attack_speed = self.WEAPON_TYPES.get(weapon_type, {}).get('attack_speed', 1.0)

        name = f"{material.capitalize()} {weapon_type.capitalize()}"
        if rarity != 'common':
            name = f"{rarity.capitalize()} {name}"

        return {
            'itemId': item_id,
            'name': name,
            'category': 'equipment',
            'tier': tier,
            'rarity': rarity,
            'slot': 'mainHand',
            'stats': {
                'damage': [min_damage, max_damage],
                'durability': [durability, durability],
                'attackSpeed': attack_speed
            },
            'requirements': {
                'level': max(1, (tier - 1) * 5)
            },
            'metadata': {
                'narrative': f"A {rarity} tier {tier} {weapon_type} forged from {material}."
            }
        }

    def _create_armor(self, item_id: str, material: str, slot: str, tier: int) -> Dict[str, Any]:
        """Create a single armor piece definition"""
        base_defense = 10
        tier_mult = self.TIER_MULTIPLIERS.get(tier, 1.0)
        slot_mult = self.ARMOR_SLOTS.get(slot, {}).get('defense_mult', 1.0)

        defense = int(base_defense * tier_mult * slot_mult)
        durability = int(400 * tier_mult * slot_mult)

        name = f"{material.capitalize()} {slot.capitalize()}"

        return {
            'itemId': item_id,
            'name': name,
            'category': 'equipment',
            'tier': tier,
            'rarity': 'common',
            'slot': slot,
            'stats': {
                'defense': defense,
                'durability': [durability, durability]
            },
            'requirements': {
                'level': max(1, (tier - 1) * 5)
            },
            'metadata': {
                'narrative': f"A tier {tier} {slot} crafted from {material}."
            }
        }

    def save_to_json(self, items: List[Dict[str, Any]], filepath: str):
        """Save generated items to a JSON file"""
        output = {
            'metadata': {
                'version': '2.0',
                'generated': True,
                'item_count': len(items)
            },
            'equipment': items
        }

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f" Generated {len(items)} items ’ {filepath}")


# Example usage
if __name__ == "__main__":
    generator = ItemGenerator()

    # Generate a weapon series
    swords = generator.generate_weapon_series(
        weapon_type='sword',
        materials=['copper', 'iron', 'steel', 'mithril'],
        tiers=[1, 2, 3, 4],
        rarities=['common', 'uncommon']
    )

    # Generate armor sets
    armor = generator.generate_armor_series(
        materials=['copper', 'iron', 'steel', 'mithril'],
        tiers=[1, 2, 3, 4]
    )

    all_items = swords + armor

    # Save to file
    generator.save_to_json(all_items, 'items-generated.JSON')
    print(f"\nGenerated {len(all_items)} total items")
    print(f"  - {len(swords)} weapons")
    print(f"  - {len(armor)} armor pieces")
