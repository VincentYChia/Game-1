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
        print(f"         - item: {item.name} (slot: {item.slot})")

        can_equip, reason = item.can_equip(character)
        print(f"         - can_equip: {can_equip}, reason: {reason}")

        if not can_equip:
            print(f"         ❌ Cannot equip: {reason}")
            return None, reason

        slot = item.slot
        if slot not in self.slots:
            print(f"         ❌ Invalid slot '{slot}' not in {list(self.slots.keys())}")
            return None, f"Invalid slot: {slot}"

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

    def get_weapon_damage(self) -> Tuple[int, int]:
        weapon = self.slots.get('mainHand')
        if weapon:
            return weapon.get_actual_damage()
        return (1, 2)

    def get_weapon_range(self) -> float:
        """Get range of equipped weapon, default to 1.0 for unarmed"""
        weapon = self.slots.get('mainHand')
        if weapon:
            return weapon.range
        return 1.0  # Unarmed/default range

    def get_stat_bonuses(self) -> Dict[str, float]:
        bonuses = {}
        for item in self.slots.values():
            if item:
                for stat, value in item.bonuses.items():
                    bonuses[stat] = bonuses.get(stat, 0) + value
        return bonuses
