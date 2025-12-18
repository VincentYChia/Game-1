"""
Crafting Tag Processor
======================

Centralized tag processing logic for all crafting disciplines (smithing,
engineering, enchanting, alchemy, refining). This module translates recipe
metadata tags into functional behaviors, slot assignments, and validation rules.

Design Philosophy:
- Tags drive all crafting logic (LLM-friendly, extensible)
- User functionality and experience is paramount
- Redundant tags are eliminated automatically
- Wrong applications fail gracefully (no crashes, just no-ops)
- Single source of truth for tag semantics

Tag Categories:
1. Role Tags: Determine what code/logic to use (device, utility, trap, station, potion)
2. Rule Tags: Determine applicability (weapon, armor, universal, tool)
3. Functionality Tags: Determine specific effects (damage, healing, fire, etc.)
4. Metadata Tags: Descriptive only (starter, basic, advanced, quality)
"""

from typing import List, Dict, Any, Optional, Tuple


class SmithingTagProcessor:
    """Process smithing recipe tags for slot assignment and item inheritance"""

    # Slot assignment tags (these determine equipment slot)
    SLOT_TAGS = {
        "weapon": "mainHand",        # Generic weapon → mainhand
        "tool": None,                # Tool → determined by sub-type
        "armor": None,               # Armor → determined by sub-type
        "shield": "offHand",         # Shield → offhand
        "accessory": "accessory",    # Accessory → accessory slot
    }

    # Tool sub-type → slot mapping
    TOOL_SLOT_MAP = {
        "pickaxe": "pickaxe",
        "axe": "axe",
        "shovel": "tool",
        "hoe": "tool",
    }

    # Armor sub-type → slot mapping
    ARMOR_SLOT_MAP = {
        "helmet": "helmet",
        "chestplate": "chestplate",
        "leggings": "leggings",
        "boots": "boots",
        "gauntlets": "gauntlets",
    }

    @staticmethod
    def get_equipment_slot(recipe_tags: List[str]) -> Optional[str]:
        """Determine equipment slot from recipe tags

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Equipment slot name or None if not equipment
        """
        # Check for specific armor pieces first (most specific)
        for tag in recipe_tags:
            if tag in SmithingTagProcessor.ARMOR_SLOT_MAP:
                return SmithingTagProcessor.ARMOR_SLOT_MAP[tag]

        # Check for tool sub-types
        for tag in recipe_tags:
            if tag in SmithingTagProcessor.TOOL_SLOT_MAP:
                return SmithingTagProcessor.TOOL_SLOT_MAP[tag]

        # Check for generic slot tags
        for tag in recipe_tags:
            if tag in SmithingTagProcessor.SLOT_TAGS:
                slot = SmithingTagProcessor.SLOT_TAGS[tag]
                if slot is not None:
                    return slot

        return None

    @staticmethod
    def get_inheritable_tags(recipe_tags: List[str]) -> List[str]:
        """Get tags that should be inherited by the crafted item

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            List of tags to copy to crafted item
        """
        # Tags that provide item functionality (should be inherited)
        FUNCTIONAL_TAGS = [
            "melee", "ranged", "magic",           # Combat style
            "1H", "2H", "versatile",              # Hand requirement
            "sword", "axe", "spear", "bow",       # Weapon type
            "crushing", "slashing", "piercing",   # Damage type
            "fast", "precision", "reach",         # Combat properties
            "armor_breaker", "cleaving",          # Special mechanics
        ]

        # Only inherit functional tags, not metadata tags like "starter", "basic"
        return [tag for tag in recipe_tags if tag in FUNCTIONAL_TAGS]

    @staticmethod
    def remove_redundant_tags(recipe_tags: List[str], item_tags: List[str]) -> List[str]:
        """Remove recipe tags that are redundant with item tags

        Args:
            recipe_tags: Tags from recipe
            item_tags: Tags already on item

        Returns:
            Filtered recipe tags with redundancies removed
        """
        # If item already has the tag, don't duplicate it
        return [tag for tag in recipe_tags if tag not in item_tags]


class EngineeringTagProcessor:
    """Process engineering recipe tags for role/code assignment"""

    # Role tags determine placement/usage behavior
    ROLE_BEHAVIORS = {
        "device": "placeable",           # Can be placed in world (turrets, machines)
        "turret": "placeable_combat",    # Placeable with combat AI
        "trap": "placeable_triggered",   # Placeable with trigger condition
        "station": "placeable_crafting", # Placeable crafting station
        "utility": "usable",             # Usable item (not placeable)
        "consumable": "consumable",      # Single-use item (bombs, grenades)
    }

    @staticmethod
    def get_behavior_type(recipe_tags: List[str]) -> str:
        """Determine behavior type from recipe tags

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Behavior type string (placeable, usable, consumable, etc.)
        """
        # Check in priority order (most specific first)
        priority_order = ["turret", "trap", "station", "device", "consumable", "utility"]

        for role_tag in priority_order:
            if role_tag in recipe_tags:
                return EngineeringTagProcessor.ROLE_BEHAVIORS[role_tag]

        # Default to device if no role tag found
        return "placeable"

    @staticmethod
    def is_combat_device(recipe_tags: List[str]) -> bool:
        """Check if device has combat functionality"""
        combat_tags = ["turret", "weapon", "projectile", "damage", "combat"]
        return any(tag in combat_tags for tag in recipe_tags)

    @staticmethod
    def get_trigger_type(recipe_tags: List[str]) -> Optional[str]:
        """Get trigger type for traps

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Trigger type or None if not a trap
        """
        if "trap" not in recipe_tags:
            return None

        # Determine trigger from functional tags
        if "proximity" in recipe_tags:
            return "proximity"
        elif "pressure" in recipe_tags:
            return "pressure"
        elif "tripwire" in recipe_tags:
            return "tripwire"

        # Default trap trigger
        return "proximity"


class EnchantingTagProcessor:
    """Process enchanting recipe tags for rule validation and functionality"""

    # Rule tags determine what items can be enchanted
    RULE_TAGS = {
        "universal": ["weapon", "armor", "tool"],  # Can apply to anything
        "weapon": ["weapon"],                       # Weapons only
        "armor": ["armor"],                         # Armor only
        "tool": ["tool"],                           # Tools only
    }

    @staticmethod
    def get_applicable_item_types(recipe_tags: List[str]) -> List[str]:
        """Determine which item types this enchantment can apply to

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            List of applicable item types
        """
        # Check for rule tags
        for tag in recipe_tags:
            if tag in EnchantingTagProcessor.RULE_TAGS:
                return EnchantingTagProcessor.RULE_TAGS[tag]

        # Default to universal if no rule tag specified
        return EnchantingTagProcessor.RULE_TAGS["universal"]

    @staticmethod
    def can_apply_to_item(recipe_tags: List[str], item_type: str) -> Tuple[bool, str]:
        """Check if enchantment can be applied to item

        Args:
            recipe_tags: Tags from enchanting recipe
            item_type: Type of item being enchanted ("weapon", "armor", "tool")

        Returns:
            (can_apply, reason) tuple
        """
        applicable_types = EnchantingTagProcessor.get_applicable_item_types(recipe_tags)

        if item_type in applicable_types:
            return True, "OK"
        else:
            # Graceful failure - return False but don't crash
            return False, f"Enchantment not applicable to {item_type} items"

    @staticmethod
    def get_functionality_tags(recipe_tags: List[str]) -> List[str]:
        """Extract functionality tags (what the enchantment does)

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            List of functionality tags
        """
        # Remove rule tags and metadata tags, keep only functional tags
        RULE_AND_METADATA = ["universal", "weapon", "armor", "tool", "basic", "advanced", "legendary", "starter", "quality"]

        return [tag for tag in recipe_tags if tag not in RULE_AND_METADATA]


class AlchemyTagProcessor:
    """Process alchemy recipe tags for potion vs transmutation logic"""

    @staticmethod
    def is_consumable(recipe_tags: List[str]) -> bool:
        """Check if recipe produces a consumable potion

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            True if potion (consumable), False if transmutation (item output)
        """
        # "potion" tag overrides "transmutation" tag
        if "potion" in recipe_tags:
            return True

        # If transmutation tag is present (and no potion tag), it's NOT consumable
        if "transmutation" in recipe_tags:
            return False

        # Default: assume transmutation (item output) since everything is an item
        # User said: "transmutation might as well be a default tag since everything is an item in the game anyway"
        return False

    @staticmethod
    def get_effect_type(recipe_tags: List[str]) -> Optional[str]:
        """Determine effect type from tags

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Effect type string or None
        """
        EFFECT_TAGS = {
            "healing": "heal",
            "buff": "buff",
            "damage": "damage",
            "utility": "utility",
            "strength": "buff_strength",
            "defense": "buff_defense",
            "speed": "buff_speed",
        }

        for tag in recipe_tags:
            if tag in EFFECT_TAGS:
                return EFFECT_TAGS[tag]

        return None

    @staticmethod
    def get_rule_tags(recipe_tags: List[str]) -> List[str]:
        """Get rule tags (similar to enchanting - determines application rules)

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            List of rule tags
        """
        RULE_TAGS = ["potion", "transmutation", "elixir", "tincture"]
        return [tag for tag in recipe_tags if tag in RULE_TAGS]


class RefiningTagProcessor:
    """Process refining recipe tags for LLM scaling logic"""

    @staticmethod
    def get_process_type(recipe_tags: List[str]) -> str:
        """Determine refining process type

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Process type string
        """
        PROCESS_TYPES = ["smelting", "crushing", "grinding", "purifying", "alloying"]

        for tag in recipe_tags:
            if tag in PROCESS_TYPES:
                return tag

        # Default to smelting
        return "smelting"

    @staticmethod
    def get_material_tier(recipe_tags: List[str]) -> int:
        """Determine material tier from tags

        Args:
            recipe_tags: List of tags from recipe metadata

        Returns:
            Tier number (1-4)
        """
        TIER_MAP = {
            "basic": 1,
            "starter": 1,
            "advanced": 2,
            "quality": 3,
            "legendary": 4,
            "master": 4,
        }

        for tag in recipe_tags:
            if tag in TIER_MAP:
                return TIER_MAP[tag]

        # Default tier 1
        return 1

    @staticmethod
    def generate_recipe_template(material_name: str, tier: int) -> Dict[str, Any]:
        """Generate LLM-friendly recipe template for scaling

        This is the core of the LLM scaling logic - provides a structured
        template that an LLM can use to generate new refining recipes

        Args:
            material_name: Name of material being refined
            tier: Material tier (1-4)

        Returns:
            Recipe template dict
        """
        return {
            "recipeId": f"refining_{material_name}_ore_to_ingot",
            "inputs": [
                {"materialId": f"{material_name}_ore", "quantity": 1}
            ],
            "outputs": [
                {"materialId": f"{material_name}_ingot", "quantity": 1, "rarity": "common"}
            ],
            "stationRequired": "refinery",
            "stationTierRequired": tier,
            "fuelRequired": None,
            "metadata": {
                "narrative": f"Refining {material_name} ore into usable ingots.",
                "tags": ["smelting", material_name, "basic" if tier == 1 else "advanced"]
            }
        }
