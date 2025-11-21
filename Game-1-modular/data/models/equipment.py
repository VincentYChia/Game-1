"""Equipment item data model"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional


@dataclass
class EquipmentItem:
    """Equipment item with stats, durability, and enchantments"""
    item_id: str
    name: str
    tier: int
    rarity: str
    slot: str  # mainHand, offHand, helmet, chestplate, leggings, boots, gauntlets, tool
    damage: Tuple[int, int] = (0, 0)
    defense: int = 0
    durability_current: int = 100
    durability_max: int = 100
    attack_speed: float = 1.0
    weight: float = 1.0
    range: float = 1.0  # Weapon range stat
    requirements: Dict[str, Any] = field(default_factory=dict)
    bonuses: Dict[str, float] = field(default_factory=dict)
    enchantments: List[Dict[str, Any]] = field(default_factory=list)  # Applied enchantments

    def get_effectiveness(self) -> float:
        """Get effectiveness multiplier based on durability (for CONFIG check - imported later)"""
        # Note: Config.DEBUG_INFINITE_RESOURCES check moved to caller to avoid circular import
        if self.durability_current <= 0:
            return 0.5
        dur_pct = self.durability_current / self.durability_max
        return 1.0 if dur_pct >= 0.5 else 1.0 - (0.5 - dur_pct) * 0.5

    def get_actual_damage(self) -> Tuple[int, int]:
        """Get actual damage including durability and enchantment effects"""
        eff = self.get_effectiveness()
        base_damage = (self.damage[0] * eff, self.damage[1] * eff)

        # Apply enchantment damage multipliers
        damage_mult = 1.0
        for ench in self.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'damage_multiplier':
                damage_mult += effect.get('value', 0.0)

        return (int(base_damage[0] * damage_mult), int(base_damage[1] * damage_mult))

    def get_defense_with_enchantments(self) -> int:
        """Get defense value including enchantment effects"""
        base_defense = self.defense * self.get_effectiveness()

        # Apply enchantment defense multipliers
        defense_mult = 1.0
        for ench in self.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'defense_multiplier':
                defense_mult += effect.get('value', 0.0)

        return int(base_defense * defense_mult)

    def can_equip(self, character) -> Tuple[bool, str]:
        """Check if character meets requirements, return (can_equip, reason)"""
        # Stat abbreviation mapping to full names
        stat_mapping = {
            'str': 'strength',
            'strength': 'strength',
            'def': 'defense',
            'defense': 'defense',
            'vit': 'vitality',
            'vitality': 'vitality',
            'lck': 'luck',
            'luck': 'luck',
            'agi': 'agility',
            'agility': 'agility',
            'dex': 'agility',  # DEX maps to agility for backwards compatibility
            'dexterity': 'agility',
            'int': 'intelligence',
            'intelligence': 'intelligence'
        }

        reqs = self.requirements
        if 'level' in reqs and character.leveling.level < reqs['level']:
            return False, f"Requires level {reqs['level']}"
        if 'stats' in reqs:
            for stat, val in reqs['stats'].items():
                stat_name = stat_mapping.get(stat.lower(), stat.lower())
                if getattr(character.stats, stat_name, 0) < val:
                    return False, f"Requires {stat.upper()} {val}"
        return True, "OK"

    def copy(self) -> 'EquipmentItem':
        """Create a deep copy of this equipment item"""
        import copy as copy_module
        return EquipmentItem(
            item_id=self.item_id,
            name=self.name,
            tier=self.tier,
            rarity=self.rarity,
            slot=self.slot,
            damage=self.damage,
            defense=self.defense,
            durability_current=self.durability_current,
            durability_max=self.durability_max,
            attack_speed=self.attack_speed,
            weight=self.weight,
            range=self.range,
            requirements=self.requirements.copy(),
            bonuses=self.bonuses.copy(),
            enchantments=copy_module.deepcopy(self.enchantments)
        )

    def can_apply_enchantment(self, enchantment_id: str, applicable_to: List[str], effect: Dict) -> Tuple[bool, str]:
        """Check if an enchantment can be applied to this item"""
        # Check if item type is compatible
        item_type = self._get_item_type()
        if item_type not in applicable_to:
            return False, f"Cannot apply to {item_type} items"

        # Enchantments with conflicts will overwrite existing conflicting enchantments
        return True, "OK"

    def apply_enchantment(self, enchantment_id: str, enchantment_name: str, effect: Dict) -> Tuple[bool, str]:
        """Apply an enchantment effect to this item with comprehensive rules"""
        # Check for exact duplicate
        if any(ench.get('enchantment_id') == enchantment_id for ench in self.enchantments):
            return False, "This enchantment is already applied"

        # Extract enchantment family and tier
        def get_enchantment_info(ench_id: str) -> Tuple[str, int]:
            """Extract family name and tier from enchantment_id (e.g., 'sharpness_3' → ('sharpness', 3))"""
            parts = ench_id.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                return parts[0], int(parts[1])
            return ench_id, 1  # No tier suffix, assume tier 1

        new_family, new_tier = get_enchantment_info(enchantment_id)

        # Check if a higher tier of the same family already exists
        for existing_ench in self.enchantments:
            existing_id = existing_ench.get('enchantment_id', '')
            existing_family, existing_tier = get_enchantment_info(existing_id)

            if existing_family == new_family and existing_tier > new_tier:
                return False, f"Cannot apply {enchantment_name} - {existing_ench.get('name')} (higher tier) is already applied"

        # Remove conflicting enchantments (including lower tiers of same family)
        conflicts_with = effect.get('conflictsWith', [])

        self.enchantments = [
            ench for ench in self.enchantments
            if ench.get('enchantment_id', '') not in conflicts_with
            and enchantment_id not in ench.get('effect', {}).get('conflictsWith', [])
        ]

        # Apply the new enchantment
        self.enchantments.append({
            'enchantment_id': enchantment_id,
            'name': enchantment_name,
            'effect': effect
        })

        return True, "OK"

    def _get_item_type(self) -> str:
        """Determine the item type for enchantment compatibility"""
        weapon_slots = ['mainHand', 'offHand']
        tool_slots = ['tool']
        armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']

        if self.slot in weapon_slots and self.damage != (0, 0):
            return 'weapon'
        elif self.slot in weapon_slots or self.slot in tool_slots:
            return 'tool'
        elif self.slot in armor_slots:
            return 'armor'
        else:
            return 'accessory'
