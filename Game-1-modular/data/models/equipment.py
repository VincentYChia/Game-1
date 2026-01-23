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
    efficiency: float = 1.0  # Tool efficiency multiplier
    weight: float = 1.0
    range: float = 1.0  # Weapon range stat
    requirements: Dict[str, Any] = field(default_factory=dict)
    bonuses: Dict[str, float] = field(default_factory=dict)
    enchantments: List[Dict[str, Any]] = field(default_factory=list)  # Applied enchantments
    icon_path: Optional[str] = None  # Optional path to item icon image (PNG/JPG)
    hand_type: str = "default"  # "1H", "2H", "versatile", or "default" (mainhand only)
    item_type: str = "weapon"  # "weapon", "shield", "tool", etc.
    stat_multipliers: Dict[str, float] = field(default_factory=dict)  # Original stat multipliers from JSON
    tags: List[str] = field(default_factory=list)  # Metadata tags from JSON
    effect_tags: List[str] = field(default_factory=list)  # Combat effect tags (fire, slashing, cone, etc.)
    effect_params: Dict[str, Any] = field(default_factory=dict)  # Effect parameters (baseDamage, cone_angle, etc.)
    soulbound: bool = False  # If true, item is kept on death

    def is_soulbound(self) -> bool:
        """Check if this item is soulbound (kept on death)"""
        # Check direct flag
        if self.soulbound:
            return True

        # Check for soulbound enchantment
        for ench in self.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'soulbound':
                return True

        return False

    def get_effectiveness(self) -> float:
        """Get effectiveness multiplier based on durability (for CONFIG check - imported later)"""
        # Note: Config.DEBUG_INFINITE_RESOURCES check moved to caller to avoid circular import
        if self.durability_current <= 0:
            return 0.5
        dur_pct = self.durability_current / self.durability_max
        return 1.0 if dur_pct >= 0.5 else 1.0 - (0.5 - dur_pct) * 0.5

    def repair(self, amount: int = None, percent: float = None) -> int:
        """Repair this equipment's durability.

        Args:
            amount: Flat durability to restore
            percent: Percentage of max durability to restore (0.0-1.0)

        Returns:
            int: Amount of durability actually restored
        """
        old_durability = self.durability_current

        if amount is not None:
            self.durability_current = min(self.durability_max,
                self.durability_current + amount)
        elif percent is not None:
            repair_amount = int(self.durability_max * percent)
            self.durability_current = min(self.durability_max,
                self.durability_current + repair_amount)
        else:
            # Full repair
            self.durability_current = self.durability_max

        return self.durability_current - old_durability

    def needs_repair(self) -> bool:
        """Check if this equipment needs repair.

        Returns:
            bool: True if durability is below max
        """
        return self.durability_current < self.durability_max

    def get_repair_urgency(self) -> str:
        """Get repair urgency level.

        Returns:
            str: 'none', 'low', 'medium', 'high', or 'critical'
        """
        if self.durability_current >= self.durability_max:
            return 'none'

        percent = self.durability_current / self.durability_max
        if percent >= 0.5:
            return 'low'
        elif percent >= 0.2:
            return 'medium'
        elif percent > 0:
            return 'high'
        else:
            return 'critical'

    def get_actual_damage(self) -> Tuple[int, int]:
        """Get actual damage including bonuses, durability and enchantment effects"""
        # Start with base damage
        base_min, base_max = self.damage

        # Apply durability effectiveness
        eff = self.get_effectiveness()
        effective_damage = (base_min * eff, base_max * eff)

        # Apply crafted damage multiplier from bonuses dict
        # damage_multiplier: -0.5 to +0.5 (e.g., 0.25 = 25% more damage, -0.25 = 25% less damage)
        damage_mult = 1.0
        crafted_mult = self.bonuses.get('damage_multiplier', 0)
        damage_mult += crafted_mult

        # Apply efficiency as damage multiplier for tools
        # efficiency directly multiplies (0.5 to 1.5, e.g., 1.2 = 20% more damage)
        if self.item_type == 'tool':
            damage_mult *= self.efficiency

        # Apply enchantment damage multipliers
        for ench in self.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'damage_multiplier':
                damage_mult += effect.get('value', 0.0)

        return (int(effective_damage[0] * damage_mult), int(effective_damage[1] * damage_mult))

    def get_defense_with_enchantments(self) -> int:
        """Get defense value including bonuses and enchantment effects"""
        # Start with base defense
        base_defense = self.defense

        # Apply durability effectiveness
        effective_defense = base_defense * self.get_effectiveness()

        # Apply crafted defense multiplier from bonuses dict
        # defense_multiplier: -0.5 to +0.5 (e.g., 0.25 = 25% more defense, -0.25 = 25% less defense)
        defense_mult = 1.0
        crafted_mult = self.bonuses.get('defense_multiplier', 0)
        defense_mult += crafted_mult

        # Apply enchantment defense multipliers
        for ench in self.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'defense_multiplier':
                defense_mult += effect.get('value', 0.0)

        return int(effective_defense * defense_mult)

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
            enchantments=copy_module.deepcopy(self.enchantments),
            icon_path=self.icon_path,
            hand_type=self.hand_type,
            item_type=self.item_type,
            stat_multipliers=self.stat_multipliers.copy(),
            tags=self.tags.copy()
        )

    def can_apply_enchantment(self, enchantment_id: str, applicable_to: List[str] = None,
                              effect: Dict = None, tags: List[str] = None) -> Tuple[bool, str]:
        """Check if an enchantment can be applied to this item

        Args:
            enchantment_id: ID of the enchantment
            applicable_to: Legacy list of applicable item types (weapon, armor, tool)
            effect: Enchantment effect dict
            tags: Recipe tags (preferred over applicable_to)

        Returns:
            (can_apply, reason) tuple
        """
        # Get item type
        item_type = self._get_item_type()

        # Use EnchantingTagProcessor if tags provided (new system)
        if tags and len(tags) > 0:
            from core.crafting_tag_processor import EnchantingTagProcessor

            # Graceful failure - use tag processor validation
            can_apply, reason = EnchantingTagProcessor.can_apply_to_item(tags, item_type)
            if not can_apply:
                return False, reason  # Returns descriptive message like "Enchantment not applicable to armor items"
            return True, "OK"

        # Fallback to legacy applicable_to list
        elif applicable_to:
            if item_type not in applicable_to:
                return False, f"Cannot apply to {item_type} items"
            return True, "OK"

        # No validation data provided - allow by default (graceful)
        else:
            return True, "OK (no applicability rules provided)"

    def apply_enchantment(self, enchantment_id: str, enchantment_name: str, effect: Dict,
                         metadata_tags: List[str] = None) -> Tuple[bool, str]:
        """Apply an enchantment effect to this item with comprehensive rules

        Args:
            enchantment_id: Unique ID of the enchantment
            enchantment_name: Display name of the enchantment
            effect: Effect dictionary (type, value, etc.)
            metadata_tags: Optional metadata tags from recipe (for combat system)
        """
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
        enchantment_data = {
            'enchantment_id': enchantment_id,
            'name': enchantment_name,
            'effect': effect
        }
        if metadata_tags:
            enchantment_data['metadata_tags'] = metadata_tags

        self.enchantments.append(enchantment_data)

        # Debug output for enchantment verification
        print(f"\n✨ ENCHANTMENT APPLIED")
        print(f"   Item: {self.item_id} ({self.name})")
        print(f"   Enchantment: {enchantment_name} ({enchantment_id})")
        print(f"   Effect: {effect}")
        print(f"   Total Enchantments: {len(self.enchantments)}")

        return True, "OK"

    def _get_item_type(self) -> str:
        """Determine the item type for enchantment compatibility"""
        # Use explicit item_type if set and valid
        if hasattr(self, 'item_type') and self.item_type in ['weapon', 'tool', 'armor', 'shield', 'accessory']:
            # Map 'shield' to 'armor' for enchantment purposes
            if self.item_type == 'shield':
                return 'armor'
            return self.item_type

        # Fall back to slot-based detection
        weapon_slots = ['mainHand', 'offHand']
        tool_slots = ['tool']
        armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']

        if self.slot in weapon_slots and self.damage != (0, 0):
            return 'weapon'
        elif self.slot in tool_slots:
            return 'tool'
        elif self.slot in armor_slots:
            return 'armor'
        else:
            # Items in weapon slots with no damage are tools (axes, pickaxes when equipped)
            if self.slot in weapon_slots:
                return 'tool'
            return 'accessory'

    def get_metadata_tags(self) -> List[str]:
        """Get metadata tags for weapon tag modifiers

        Returns:
            List[str]: Metadata tags from JSON (e.g., ["melee", "sword", "2H", "crushing"])
        """
        return self.tags if self.tags else []

    def get_effect_tags(self) -> List[str]:
        """Get combat effect tags for effect_executor

        Returns:
            List[str]: Effect tags (e.g., ["physical", "slashing", "single"])
        """
        return self.effect_tags if self.effect_tags else []

    def get_effect_params(self) -> Dict[str, Any]:
        """Get effect parameters for effect_executor

        Returns:
            Dict: Effect parameters (e.g., {"baseDamage": 30, "cone_angle": 60.0})
        """
        return self.effect_params if self.effect_params else {}
