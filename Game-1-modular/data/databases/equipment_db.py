"""Equipment Database - manages all equipment items (weapons, armor, tools)"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from data.models.equipment import EquipmentItem


class EquipmentDatabase:
    _instance = None

    def __init__(self):
        self.items: Dict[str, Dict] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EquipmentDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        count = 0
        print(f"\n🔧 EquipmentDatabase.load_from_file('{filepath}')")
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            print(f"   - JSON sections available: {list(data.keys())}")

            # Load from all sections except 'metadata'
            # ONLY load items with category='equipment' (weapons, armor, tools, etc.)
            # Exclude consumables, devices, materials - those should stack!
            for section, section_data in data.items():
                if section == 'metadata':
                    continue

                # Check if this section contains a list of items
                if isinstance(section_data, list):
                    print(f"   - Loading section '{section}'...")
                    for item_data in section_data:
                        try:
                            item_id = item_data.get('itemId', '')
                            category = item_data.get('category', '')

                            # ONLY load equipment items (not consumables, devices, materials)
                            if item_id and category == 'equipment':
                                self.items[item_id] = item_data
                                count += 1
                                if count <= 5:  # Show first 5 items loaded
                                    print(f"      ✓ Loaded: {item_id} (category: {category})")
                            elif item_id and category:
                                print(f"      ⊘ Skipped: {item_id} (category: {category}, not equipment)")
                        except Exception as e:
                            print(f"      ⚠ Skipping invalid item: {e}")
                            continue
                else:
                    print(f"   - Skipping non-list section '{section}'")

            if count > 0:
                self.loaded = True
                print(f"✓ Loaded {count} equipment items from this file")
                print(f"   Total equipment items in DB: {len(self.items)}")
                return True
            else:
                print(f"⚠ No items loaded from {filepath}")
                # Don't fail completely if one file has no items
                return True
        except Exception as e:
            print(f"⚠ Error loading equipment: {e}")
            if not self.loaded:
                print(f"⚠ Creating placeholder equipment...")
                self._create_placeholders()
            return False

    def _create_placeholders(self):
        """Create comprehensive equipment placeholders"""
        self.items = {
            # WEAPONS
            'copper_sword': {
                'itemId': 'copper_sword', 'name': 'Copper Sword', 'tier': 1, 'rarity': 'common', 'slot': 'mainHand',
                'stats': {'damage': [8, 12], 'durability': [400, 400], 'attackSpeed': 1.0}, 'requirements': {'level': 1}
            },
            'iron_sword': {
                'itemId': 'iron_sword', 'name': 'Iron Sword', 'tier': 2, 'rarity': 'common', 'slot': 'mainHand',
                'stats': {'damage': [15, 22], 'durability': [600, 600], 'attackSpeed': 1.0},
                'requirements': {'level': 5}
            },
            'steel_sword': {
                'itemId': 'steel_sword', 'name': 'Steel Sword', 'tier': 3, 'rarity': 'uncommon', 'slot': 'mainHand',
                'stats': {'damage': [28, 38], 'durability': [800, 800], 'attackSpeed': 1.1},
                'requirements': {'level': 10}
            },
            # ARMOR - Helmets
            'copper_helmet': {
                'itemId': 'copper_helmet', 'name': 'Copper Helmet', 'tier': 1, 'rarity': 'common', 'slot': 'helmet',
                'stats': {'defense': 8, 'durability': [400, 400]}, 'requirements': {'level': 1}
            },
            'iron_helmet': {
                'itemId': 'iron_helmet', 'name': 'Iron Helmet', 'tier': 2, 'rarity': 'common', 'slot': 'helmet',
                'stats': {'defense': 15, 'durability': [600, 600]}, 'requirements': {'level': 5}
            },
            # ARMOR - Chestplates
            'copper_chestplate': {
                'itemId': 'copper_chestplate', 'name': 'Copper Chestplate', 'tier': 1, 'rarity': 'common',
                'slot': 'chestplate',
                'stats': {'defense': 15, 'durability': [500, 500]}, 'requirements': {'level': 1}
            },
            'iron_chestplate': {
                'itemId': 'iron_chestplate', 'name': 'Iron Chestplate', 'tier': 2, 'rarity': 'common',
                'slot': 'chestplate',
                'stats': {'defense': 25, 'durability': [700, 700]}, 'requirements': {'level': 5}
            },
            # ARMOR - Leggings
            'copper_leggings': {
                'itemId': 'copper_leggings', 'name': 'Copper Leggings', 'tier': 1, 'rarity': 'common',
                'slot': 'leggings',
                'stats': {'defense': 12, 'durability': [450, 450]}, 'requirements': {'level': 1}
            },
            'iron_leggings': {
                'itemId': 'iron_leggings', 'name': 'Iron Leggings', 'tier': 2, 'rarity': 'common', 'slot': 'leggings',
                'stats': {'defense': 20, 'durability': [650, 650]}, 'requirements': {'level': 5}
            },
            # ARMOR - Boots
            'copper_boots': {
                'itemId': 'copper_boots', 'name': 'Copper Boots', 'tier': 1, 'rarity': 'common', 'slot': 'boots',
                'stats': {'defense': 6, 'durability': [350, 350]}, 'requirements': {'level': 1}
            },
            'iron_boots': {
                'itemId': 'iron_boots', 'name': 'Iron Boots', 'tier': 2, 'rarity': 'common', 'slot': 'boots',
                'stats': {'defense': 12, 'durability': [550, 550]}, 'requirements': {'level': 5}
            },
        }
        self.loaded = True
        print(f"✓ Created {len(self.items)} placeholder equipment")

    def _calculate_weapon_damage(self, tier: int, item_type: str, subtype: str, stat_multipliers: Dict) -> Tuple[int, int]:
        """Calculate weapon damage based on stats-calculations.JSON formula"""
        # Formula: globalBase × tierMult × categoryMult × typeMult × subtypeMult × itemMult × variance
        global_base = 10

        tier_mults = {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}
        tier_mult = tier_mults.get(tier, 1.0)

        category_mult = 1.0  # weapons are 1.0

        type_mults = {
            'sword': 1.0, 'axe': 1.1, 'spear': 1.05, 'mace': 1.15,
            'dagger': 0.8, 'bow': 1.0, 'staff': 0.9, 'shield': 1.0
        }
        type_mult = type_mults.get(item_type, 1.0)

        subtype_mults = {
            'shortsword': 0.9, 'longsword': 1.0, 'greatsword': 1.4,
            'dagger': 1.0, 'spear': 1.0, 'pike': 1.2, 'halberd': 1.4,
            'mace': 1.0, 'warhammer': 1.3, 'maul': 1.5
        }
        subtype_mult = subtype_mults.get(subtype, 1.0)

        item_mult = stat_multipliers.get('damage', 1.0)

        base_damage = global_base * tier_mult * category_mult * type_mult * subtype_mult * item_mult

        # Apply variance range (85%-115%)
        min_damage = int(base_damage * 0.85)
        max_damage = int(base_damage * 1.15)

        return (min_damage, max_damage)

    def _calculate_armor_defense(self, tier: int, slot: str, stat_multipliers: Dict) -> int:
        """Calculate armor defense based on stats-calculations.JSON formula"""
        # Formula: globalBase × tierMult × slotMult × itemMult
        global_base = 10

        tier_mults = {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}
        tier_mult = tier_mults.get(tier, 1.0)

        slot_mults = {
            'helmet': 0.8, 'chestplate': 1.5, 'leggings': 1.2,
            'boots': 0.7, 'gauntlets': 0.6
        }
        slot_mult = slot_mults.get(slot, 1.0)

        item_mult = stat_multipliers.get('defense', 1.0)

        defense = int(global_base * tier_mult * slot_mult * item_mult)

        return defense

    def create_equipment_from_id(self, item_id: str) -> Optional[EquipmentItem]:
        if item_id not in self.items:
            return None

        data = self.items[item_id]
        tier = data.get('tier', 1)
        item_type = data.get('type', '')
        subtype = data.get('subtype', '')
        stat_multipliers = data.get('statMultipliers', {})

        # Old stats format (for placeholder items)
        stats = data.get('stats', {})

        # Define weapon and armor types
        weapon_types = {'weapon', 'sword', 'axe', 'mace', 'dagger', 'spear', 'bow', 'staff'}
        armor_types = {'armor', 'helmet', 'chestplate', 'leggings', 'boots', 'gauntlets'}

        # Calculate damage for weapons
        damage = (0, 0)
        if item_type in weapon_types:
            damage = self._calculate_weapon_damage(tier, item_type, subtype, stat_multipliers)
        elif 'damage' in stats:
            # Fallback for old format
            old_damage = stats.get('damage', [0, 0])
            if isinstance(old_damage, list):
                damage = tuple(old_damage)
            elif isinstance(old_damage, (int, float)):
                damage = (int(old_damage), int(old_damage))

        # Calculate defense for armor
        defense = 0

        # Parse hand_type and tags from metadata early (needed for slot assignment)
        metadata = data.get('metadata', {})
        tags = metadata.get('tags', [])

        # Determine slot using SmithingTagProcessor for tag-based assignment
        from core.crafting_tag_processor import SmithingTagProcessor

        # Try tag-based slot assignment first (more specific and future-proof)
        mapped_slot = SmithingTagProcessor.get_equipment_slot(tags)

        # Fallback to legacy logic if no tag-based slot found
        if mapped_slot is None:
            if item_type == 'tool':
                if subtype in ['axe', 'pickaxe']:
                    mapped_slot = subtype  # 'axe' or 'pickaxe' slot
                else:
                    mapped_slot = 'mainHand'  # Fallback for other tools
            else:
                json_slot = data.get('slot', 'mainHand')
                slot_mapping = {
                    'head': 'helmet', 'chest': 'chestplate', 'legs': 'leggings',
                    'feet': 'boots', 'hands': 'gauntlets',
                    'mainHand': 'mainHand', 'offHand': 'offHand',
                    'helmet': 'helmet', 'chestplate': 'chestplate',
                    'leggings': 'leggings', 'boots': 'boots',
                    'gauntlets': 'gauntlets', 'accessory': 'accessory',
                }
                mapped_slot = slot_mapping.get(json_slot, json_slot)

        if item_type in armor_types:
            defense = self._calculate_armor_defense(tier, mapped_slot, stat_multipliers)
        elif 'defense' in stats:
            defense = stats.get('defense', 0)

        # Calculate durability
        durability = stats.get('durability', [100, 100])
        if isinstance(durability, list):
            dur_max = durability[1] if len(durability) > 1 else durability[0]
        else:
            dur_max = int(durability)

        # Auto-generate icon path if not provided
        icon_path = data.get('iconPath')
        if not icon_path and item_id:
            # Determine subdirectory based on slot/type
            if mapped_slot in ['mainHand', 'offHand'] and damage != (0, 0):
                subdir = 'weapons'
            elif mapped_slot in ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
                subdir = 'armor'
            elif mapped_slot in ['tool', 'axe', 'pickaxe'] or item_type == 'tool':
                subdir = 'tools'
            elif mapped_slot == 'accessory' or item_type == 'accessory':
                subdir = 'accessories'
            elif item_type == 'station':
                subdir = 'stations'
            else:
                subdir = 'weapons'  # Default fallback
            icon_path = f"{subdir}/{item_id}.png"

        # Parse hand_type from metadata tags (metadata and tags already parsed above)
        hand_type = "default"  # Default: mainhand only

        if '1H' in tags:
            hand_type = "1H"  # Can be equipped in either hand
        elif '2H' in tags:
            hand_type = "2H"  # Requires both hands (blocks offhand)
        elif 'versatile' in tags:
            hand_type = "versatile"  # Can have offhand, but not required

        # Determine item_type (weapon, shield, tool, etc.)
        parsed_item_type = "weapon"  # Default
        if item_type == 'shield':
            parsed_item_type = "shield"
        elif item_type == 'tool':
            parsed_item_type = "tool"
        elif item_type == 'armor':
            parsed_item_type = "armor"
        elif item_type == 'accessory':
            parsed_item_type = "accessory"
        elif item_type == 'station':
            parsed_item_type = "station"

        # Load effect tags and params for combat system
        # Support both snake_case (effect_tags) and camelCase (effectTags) for compatibility
        effect_tags = data.get('effect_tags', data.get('effectTags', []))
        effect_params = data.get('effect_params', data.get('effectParams', {}))

        return EquipmentItem(
            item_id=item_id,
            name=data.get('name', item_id),
            tier=tier,
            rarity=data.get('rarity', 'common'),
            slot=mapped_slot,
            damage=damage,
            defense=defense,
            durability_current=dur_max,
            durability_max=dur_max,
            attack_speed=stats.get('attackSpeed', 1.0),
            weight=stats.get('weight', 1.0),
            range=data.get('range', 1.0),  # Range is a top-level field in JSON
            requirements=data.get('requirements', {}),
            bonuses=stats.get('bonuses', {}),
            icon_path=icon_path,
            hand_type=hand_type,
            item_type=parsed_item_type,
            stat_multipliers=stat_multipliers,
            tags=tags,  # Pass the tags from metadata
            effect_tags=effect_tags,  # Pass combat effect tags
            effect_params=effect_params  # Pass effect parameters
        )

    def is_equipment(self, item_id: str) -> bool:
        """Check if an item ID is equipment"""
        result = item_id in self.items
        if not result and item_id == '':
            import traceback
            print(f"      🔍 EquipmentDB.is_equipment('{item_id}'): False - EMPTY STRING!")
            print(f"         Available equipment IDs: {list(self.items.keys())[:10]}...")  # Show first 10
            print(f"         Call stack:")
            traceback.print_stack()
        return result
