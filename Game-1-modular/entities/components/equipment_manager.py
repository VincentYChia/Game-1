"""Equipment management component"""

from typing import Dict, Optional, Tuple

from data.models import EquipmentItem


class EquipmentManager:
    def __init__(self):
        self.slots = {
            'mainHand': None,
            'offHand': None,
            'helmet': None,
            'chestplate': None,
            'leggings': None,
            'boots': None,
            'gauntlets': None,
            'accessory': None,
            'axe': None,  # Tool slot for axes
            'pickaxe': None,  # Tool slot for pickaxes
        }

    def equip(self, item: EquipmentItem, character) -> Tuple[Optional[EquipmentItem], str]:
        """Equip an item, returns (previously_equipped_item, status_message)"""
        print(f"      🔧 EquipmentManager.equip() called")
        print(f"         - item: {item.name} (slot: {item.slot}, hand_type: {item.hand_type})")

        can_equip, reason = item.can_equip(character)
        print(f"         - can_equip: {can_equip}, reason: {reason}")

        if not can_equip:
            print(f"         ❌ Cannot equip: {reason}")
            return None, reason

        slot = item.slot
        if slot not in self.slots:
            print(f"         ❌ Invalid slot '{slot}' not in {list(self.slots.keys())}")
            return None, f"Invalid slot: {slot}"

        # HAND TYPE VALIDATION
        if slot == 'mainHand':
            # Note: 2H weapon offhand unequip is handled by try_equip_from_inventory
            # This validation is just a safety check
            if item.hand_type == "2H":
                if self.slots['offHand'] is not None:
                    print(f"         ⚠️ Warning: 2H weapon equipped with offhand still occupied")
                    print(f"            This should have been auto-unequipped by caller")
        elif slot == 'offHand':
            # Check if mainhand allows offhand
            mainhand = self.slots['mainHand']
            if mainhand is not None:
                if mainhand.hand_type == "2H":
                    return None, "Cannot equip offhand - mainhand is 2H weapon"
                elif mainhand.hand_type == "default":
                    # Default weapons can't have offhand unless this is a shield
                    if item.item_type != "shield":
                        return None, "Mainhand weapon doesn't support offhand"
                elif mainhand.hand_type == "versatile":
                    # Versatile weapons can have 1H in offhand, but not versatile/2H
                    if item.item_type != "shield" and item.hand_type != "1H":
                        return None, "Versatile mainhand only allows 1H or shield in offhand"

            # Offhand can only equip 1H items or shields (NOT versatile or 2H)
            if item.hand_type not in ["1H"] and item.item_type != "shield":
                return None, "Item cannot be equipped in offhand (must be 1H or shield)"

        old_item = self.slots[slot]
        self.slots[slot] = item
        print(f"         ✅ Equipped to slot '{slot}'")

        # Debug: Show weapon damage if equipping to weapon slot
        if slot in ['mainHand', 'offHand']:
            print(f"         🗡️  Weapon damage: {item.damage}")
            print(f"         🗡️  Actual damage (with effectiveness): {item.get_actual_damage()}")

        # Recalculate character stats
        character.recalculate_stats()

        # Debug: Show new weapon damage total
        if slot in ['mainHand', 'offHand']:
            weapon_dmg = self.get_weapon_damage()
            print(f"         🎯 Total weapon damage range: {weapon_dmg}")

        return old_item, "OK"

    def unequip(self, slot: str, character) -> Optional[EquipmentItem]:
        """Unequip item from slot"""
        if slot not in self.slots:
            return None
        item = self.slots[slot]
        self.slots[slot] = None

        # Recalculate character stats
        character.recalculate_stats()

        return item

    def is_equipped(self, item_id: str) -> bool:
        """Check if an item is currently equipped"""
        for item in self.slots.values():
            if item and item.item_id == item_id:
                return True
        return False

    def get_total_defense(self) -> int:
        """Get total defense from all armor pieces including enchantment effects"""
        total = 0
        armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
        for slot in armor_slots:
            item = self.slots.get(slot)
            if item:
                total += item.get_defense_with_enchantments()
        return total

    def get_weapon_damage(self, hand: str = 'mainHand') -> Tuple[int, int]:
        """Get damage from specified hand (mainHand or offHand)"""
        weapon = self.slots.get(hand)
        if weapon:
            return weapon.get_actual_damage()
        if hand == 'mainHand':
            return (1, 2)  # Unarmed damage for mainhand
        return (0, 0)  # No offhand

    def get_weapon_range(self, hand: str = 'mainHand') -> float:
        """Get range of equipped weapon in specified hand, default to 1.0 for unarmed"""
        weapon = self.slots.get(hand)
        if weapon:
            base_range = weapon.range

            # Add tag-based range bonus (reach)
            weapon_tags = weapon.get_metadata_tags()
            if weapon_tags:
                from entities.components.weapon_tag_calculator import WeaponTagModifiers
                range_bonus = WeaponTagModifiers.get_range_bonus(weapon_tags)
                return base_range + range_bonus

            return base_range
        if hand == 'mainHand':
            return 1.0  # Unarmed/default range
        return 0.0  # No offhand range

    def get_weapon_attack_speed(self, hand: str = 'mainHand') -> float:
        """Get attack speed multiplier of weapon in specified hand"""
        weapon = self.slots.get(hand)
        if weapon:
            return weapon.attack_speed
        return 1.0  # Default attack speed

    def get_stat_bonuses(self) -> Dict[str, float]:
        bonuses = {}
        for item in self.slots.values():
            if item:
                for stat, value in item.bonuses.items():
                    bonuses[stat] = bonuses.get(stat, 0) + value
        return bonuses
