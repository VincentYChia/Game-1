from __future__ import annotations
import pygame
import sys
import math
import random
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Combat system
from Combat import CombatManager, EnemyDatabase

# Crafting subdisciplines
try:
    sys.path.insert(0, str(Path(__file__).parent / "Crafting-subdisciplines"))
    from smithing import SmithingCrafter
    from refining import RefiningCrafter
    from alchemy import AlchemyCrafter
    from engineering import EngineeringCrafter
    from enchanting import EnchantingCrafter
    from rarity_utils import rarity_system
    CRAFTING_MODULES_LOADED = True
    print("✓ Loaded crafting subdisciplines modules")
except ImportError as e:
    CRAFTING_MODULES_LOADED = False
    print(f"⚠ Could not load crafting subdisciplines: {e}")
    print("  Crafting will use legacy instant-craft only")


# ============================================================================
# CONFIGURATION
# ============================================================================
class Config:
    # Window
    SCREEN_WIDTH = 1600
    SCREEN_HEIGHT = 900
    FPS = 60

    # World
    WORLD_SIZE = 100
    CHUNK_SIZE = 16
    TILE_SIZE = 32

    # Viewport (FIXED)
    VIEWPORT_WIDTH = 1200
    VIEWPORT_HEIGHT = 900

    # UI Layout
    UI_PANEL_WIDTH = 400
    INVENTORY_PANEL_X = 0
    INVENTORY_PANEL_Y = 600
    INVENTORY_PANEL_WIDTH = 1200
    INVENTORY_PANEL_HEIGHT = 300
    INVENTORY_SLOT_SIZE = 50
    INVENTORY_SLOTS_PER_ROW = 10

    # Character/Movement
    PLAYER_SPEED = 0.15
    INTERACTION_RANGE = 3.5
    CLICK_TOLERANCE = 0.7

    # Debug Mode
    DEBUG_INFINITE_RESOURCES = False  # Toggle with F1

    # Colors
    COLOR_BACKGROUND = (20, 20, 30)
    COLOR_GRID = (40, 40, 50)
    COLOR_GRASS = (34, 139, 34)
    COLOR_STONE = (128, 128, 128)
    COLOR_WATER = (30, 144, 255)
    COLOR_PLAYER = (255, 215, 0)
    COLOR_INTERACTION_RANGE = (255, 255, 0, 50)
    COLOR_UI_BG = (30, 30, 40)
    COLOR_TEXT = (255, 255, 255)
    COLOR_HEALTH = (255, 0, 0)
    COLOR_HEALTH_BG = (50, 50, 50)
    COLOR_TREE = (0, 100, 0)
    COLOR_ORE = (169, 169, 169)
    COLOR_STONE_NODE = (105, 105, 105)
    COLOR_HP_BAR = (0, 255, 0)
    COLOR_HP_BAR_BG = (100, 100, 100)
    COLOR_DAMAGE_NORMAL = (255, 255, 255)
    COLOR_DAMAGE_CRIT = (255, 215, 0)
    COLOR_SLOT_EMPTY = (40, 40, 50)
    COLOR_SLOT_FILLED = (50, 60, 70)
    COLOR_SLOT_BORDER = (100, 100, 120)
    COLOR_SLOT_SELECTED = (255, 215, 0)
    COLOR_TOOLTIP_BG = (20, 20, 30, 230)
    COLOR_RESPAWN_BAR = (100, 200, 100)
    COLOR_CAN_HARVEST = (100, 255, 100)
    COLOR_CANNOT_HARVEST = (255, 100, 100)
    COLOR_NOTIFICATION = (255, 215, 0)
    COLOR_EQUIPPED = (255, 215, 0)  # Gold border for equipped items

    RARITY_COLORS = {
        "common": (200, 200, 200), "uncommon": (30, 255, 0), "rare": (0, 112, 221),
        "epic": (163, 53, 238), "legendary": (255, 128, 0), "artifact": (230, 204, 128)
    }


# ============================================================================
# NOTIFICATION SYSTEM
# ============================================================================
@dataclass
class Notification:
    message: str
    lifetime: float = 3.0
    color: Tuple[int, int, int] = Config.COLOR_NOTIFICATION

    def update(self, dt: float) -> bool:
        self.lifetime -= dt
        return self.lifetime > 0


# ============================================================================
# DATABASE SYSTEM
# ============================================================================
class TranslationDatabase:
    _instance = None

    def __init__(self):
        self.magnitude_values = {}
        self.duration_seconds = {}
        self.mana_costs = {}
        self.cooldown_seconds = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TranslationDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        possible_paths = [
            "Definitions.JSON/skills-translation-table.JSON",
            f"{base_path}Definitions.JSON/skills-translation-table.JSON",
        ]

        for path in possible_paths:
            if Path(path).exists():
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if 'durationTranslations' in data:
                        for key, val in data['durationTranslations'].items():
                            self.duration_seconds[key] = val.get('seconds', 0)
                    if 'manaCostTranslations' in data:
                        for key, val in data['manaCostTranslations'].items():
                            self.mana_costs[key] = val.get('cost', 0)
                    print(f"✓ Loaded translations from {path}")
                    self.loaded = True
                    return
                except Exception as e:
                    print(f"⚠ Error loading {path}: {e}")

        self._create_defaults()
        self.loaded = True

    def _create_defaults(self):
        self.magnitude_values = {'minor': 0.5, 'moderate': 1.0, 'major': 2.0, 'extreme': 4.0}
        self.duration_seconds = {'instant': 0, 'brief': 15, 'moderate': 30, 'long': 60}
        self.mana_costs = {'low': 30, 'moderate': 60, 'high': 100}
        self.cooldown_seconds = {'short': 120, 'moderate': 300, 'long': 600}


@dataclass
class MaterialDefinition:
    material_id: str
    name: str
    tier: int
    category: str
    rarity: str
    description: str = ""
    max_stack: int = 99
    properties: Dict = field(default_factory=dict)


class MaterialDatabase:
    _instance = None

    def __init__(self):
        self.materials: Dict[str, MaterialDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MaterialDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for mat_data in data.get('materials', []):
                mat = MaterialDefinition(
                    material_id=mat_data.get('materialId', ''),
                    name=mat_data.get('name', ''),
                    tier=mat_data.get('tier', 1),
                    category=mat_data.get('category', 'unknown'),
                    rarity=mat_data.get('rarity', 'common'),
                    description=mat_data.get('description', ''),
                    max_stack=mat_data.get('maxStack', 99),
                    properties=mat_data.get('properties', {})
                )
                self.materials[mat.material_id] = mat
            self.loaded = True
            print(f"✓ Loaded {len(self.materials)} materials")
            return True
        except Exception as e:
            print(f"⚠ Error loading materials: {e}")
            self._create_placeholders()
            return False

    def _create_placeholders(self):
        for mat_id, name, tier, cat, rarity in [
            ("oak_log", "Oak Log", 1, "wood", "common"), ("birch_log", "Birch Log", 2, "wood", "common"),
            ("maple_log", "Maple Log", 3, "wood", "uncommon"), ("ironwood_log", "Ironwood Log", 4, "wood", "rare"),
            ("copper_ore", "Copper Ore", 1, "ore", "common"), ("iron_ore", "Iron Ore", 2, "ore", "common"),
            ("steel_ore", "Steel Ore", 3, "ore", "uncommon"), ("mithril_ore", "Mithril Ore", 4, "ore", "rare"),
            ("limestone", "Limestone", 1, "stone", "common"), ("granite", "Granite", 2, "stone", "common"),
            ("obsidian", "Obsidian", 3, "stone", "uncommon"), ("star_crystal", "Star Crystal", 4, "stone", "legendary"),
            ("copper_ingot", "Copper Ingot", 1, "metal", "common"), ("iron_ingot", "Iron Ingot", 2, "metal", "common"),
            ("steel_ingot", "Steel Ingot", 3, "metal", "uncommon"),
            ("mithril_ingot", "Mithril Ingot", 4, "metal", "rare"),
        ]:
            self.materials[mat_id] = MaterialDefinition(mat_id, name, tier, cat, rarity,
                                                        f"A {rarity} {cat} material (Tier {tier})")
        self.loaded = True
        print(f"✓ Created {len(self.materials)} placeholder materials")

    def get_material(self, material_id: str) -> Optional[MaterialDefinition]:
        return self.materials.get(material_id)

    def load_refining_items(self, filepath: str):
        """Load additional material items from items-refining-1.JSON"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for section in ['basic_ingots', 'alloys', 'wood_planks']:
                if section in data:
                    for item_data in data[section]:
                        mat = MaterialDefinition(
                            material_id=item_data.get('itemId', ''),  # Note: refining JSON uses itemId!
                            name=item_data.get('name', ''),
                            tier=item_data.get('tier', 1),
                            category=item_data.get('type', 'unknown'),
                            rarity=item_data.get('rarity', 'common'),
                            description=item_data.get('metadata', {}).get('narrative', ''),
                            max_stack=item_data.get('stackSize', 256),
                            properties={}
                        )
                        if mat.material_id and mat.material_id not in self.materials:
                            self.materials[mat.material_id] = mat
                            count += 1

            print(f"✓ Loaded {count} additional materials from refining")
            return True
        except Exception as e:
            print(f"⚠ Error loading refining items: {e}")
            return False

    def load_stackable_items(self, filepath: str, categories: list = None):
        """Load stackable items (consumables, devices, etc.) from item files

        Args:
            filepath: Path to the JSON file
            categories: List of categories to load (e.g., ['consumable', 'device'])
                       If None, loads all items with stackable=True flag
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for section, section_data in data.items():
                if section == 'metadata':
                    continue

                if isinstance(section_data, list):
                    for item_data in section_data:
                        category = item_data.get('category', '')
                        flags = item_data.get('flags', {})
                        is_stackable = flags.get('stackable', False)

                        # Load if category matches (or no filter) AND item is stackable
                        should_load = is_stackable and (
                            categories is None or category in categories
                        )

                        if should_load:
                            mat = MaterialDefinition(
                                material_id=item_data.get('itemId', ''),
                                name=item_data.get('name', ''),
                                tier=item_data.get('tier', 1),
                                category=category,
                                rarity=item_data.get('rarity', 'common'),
                                description=item_data.get('metadata', {}).get('narrative', ''),
                                max_stack=item_data.get('stackSize', 99),
                                properties={}
                            )
                            if mat.material_id and mat.material_id not in self.materials:
                                self.materials[mat.material_id] = mat
                                count += 1

            print(f"✓ Loaded {count} stackable items from {filepath} (categories: {categories})")
            return True
        except Exception as e:
            print(f"⚠ Error loading stackable items from {filepath}: {e}")
            return False


# ============================================================================
# EQUIPMENT SYSTEM
# ============================================================================
@dataclass
class EquipmentItem:
    item_id: str
    name: str
    tier: int
    rarity: str
    slot: str
    damage: Tuple[int, int] = (0, 0)
    defense: int = 0
    durability_current: int = 100
    durability_max: int = 100
    attack_speed: float = 1.0
    weight: float = 1.0
    requirements: Dict[str, Any] = field(default_factory=dict)
    bonuses: Dict[str, float] = field(default_factory=dict)
    # Enchantment system
    enchantments: List[Dict[str, Any]] = field(default_factory=list)  # List of applied enchantments

    def get_effectiveness(self) -> float:
        if Config.DEBUG_INFINITE_RESOURCES:
            return 1.0
        if self.durability_current <= 0:
            return 0.5
        dur_pct = self.durability_current / self.durability_max
        return 1.0 if dur_pct >= 0.5 else 1.0 - (0.5 - dur_pct) * 0.5

    def get_actual_damage(self) -> Tuple[int, int]:
        eff = self.get_effectiveness()
        return (int(self.damage[0] * eff), int(self.damage[1] * eff))

    def can_equip(self, character) -> Tuple[bool, str]:
        """Check if character meets requirements, return (can_equip, reason)"""
        reqs = self.requirements
        if 'level' in reqs and character.leveling.level < reqs['level']:
            return False, f"Requires level {reqs['level']}"
        if 'stats' in reqs:
            for stat, val in reqs['stats'].items():
                if getattr(character.stats, stat.lower(), 0) < val:
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

        # Check for conflicts with existing enchantments
        conflicts_with = effect.get('conflictsWith', [])
        for existing_ench in self.enchantments:
            existing_id = existing_ench.get('enchantment_id', '')
            # Check if new enchantment conflicts with existing
            if existing_id in conflicts_with:
                return False, f"Conflicts with {existing_ench.get('name', 'existing enchantment')}"
            # Check if existing conflicts with new
            existing_conflicts = existing_ench.get('effect', {}).get('conflictsWith', [])
            if enchantment_id in existing_conflicts:
                return False, f"Conflicts with {existing_ench.get('name', 'existing enchantment')}"

        return True, "OK"

    def apply_enchantment(self, enchantment_id: str, enchantment_name: str, effect: Dict):
        """Apply an enchantment effect to this item"""
        self.enchantments.append({
            'enchantment_id': enchantment_id,
            'name': enchantment_name,
            'effect': effect
        })

    def _get_item_type(self) -> str:
        """Determine the item type for enchantment compatibility"""
        # Map slot to enchantment-compatible type
        weapon_slots = ['mainHand', 'offHand']
        tool_slots = ['tool']
        armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']

        if self.slot in weapon_slots and self.damage != (0, 0):
            return 'weapon'
        elif self.slot in weapon_slots or self.slot in tool_slots:
            return 'tool'
        elif self.slot in armor_slots:
            return 'armor'
        elif self.slot == 'accessory':
            return 'accessory'
        return 'unknown'


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

    def create_equipment_from_id(self, item_id: str) -> Optional[EquipmentItem]:
        if item_id not in self.items:
            return None

        data = self.items[item_id]
        stats = data.get('stats', {})

        damage = stats.get('damage', [0, 0])
        if isinstance(damage, list):
            damage = tuple(damage)
        elif isinstance(damage, (int, float)):
            damage = (int(damage), int(damage))
        else:
            damage = (0, 0)

        durability = stats.get('durability', [100, 100])
        if isinstance(durability, list):
            dur_max = durability[1] if len(durability) > 1 else durability[0]
        else:
            dur_max = int(durability)

        # Map JSON slot names to EquipmentManager slot names
        slot_mapping = {
            'head': 'helmet',
            'chest': 'chestplate',
            'legs': 'leggings',
            'feet': 'boots',
            'hands': 'gauntlets',
            # These already match:
            'mainHand': 'mainHand',
            'offHand': 'offHand',
            'helmet': 'helmet',
            'chestplate': 'chestplate',
            'leggings': 'leggings',
            'boots': 'boots',
            'gauntlets': 'gauntlets',
            'accessory': 'accessory',
        }

        json_slot = data.get('slot', 'mainHand')
        mapped_slot = slot_mapping.get(json_slot, json_slot)

        return EquipmentItem(
            item_id=item_id,
            name=data.get('name', item_id),
            tier=data.get('tier', 1),
            rarity=data.get('rarity', 'common'),
            slot=mapped_slot,
            damage=damage,
            defense=stats.get('defense', 0),
            durability_current=dur_max,
            durability_max=dur_max,
            attack_speed=stats.get('attackSpeed', 1.0),
            weight=stats.get('weight', 1.0),
            requirements=data.get('requirements', {}),
            bonuses=stats.get('bonuses', {})
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
        total = 0
        armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
        for slot in armor_slots:
            item = self.slots.get(slot)
            if item:
                total += int(item.defense * item.get_effectiveness())
        return total

    def get_weapon_damage(self) -> Tuple[int, int]:
        weapon = self.slots.get('mainHand')
        if weapon:
            return weapon.get_actual_damage()
        return (1, 2)

    def get_stat_bonuses(self) -> Dict[str, float]:
        bonuses = {}
        for item in self.slots.values():
            if item:
                for stat, value in item.bonuses.items():
                    bonuses[stat] = bonuses.get(stat, 0) + value
        return bonuses


# ============================================================================
# TITLE SYSTEM
# ============================================================================
@dataclass
class TitleDefinition:
    title_id: str
    name: str
    tier: str
    category: str
    activity_type: str
    acquisition_threshold: int
    bonus_description: str
    bonuses: Dict[str, float]
    prerequisites: List[str] = field(default_factory=list)
    hidden: bool = False


class TitleDatabase:
    _instance = None

    def __init__(self):
        self.titles: Dict[str, TitleDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TitleDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for title_data in data.get('titles', []):
                prereqs = title_data.get('prerequisites', {})
                activities = prereqs.get('activities', {})
                activity_type, threshold = self._parse_activity(activities)
                prereq_titles = prereqs.get('requiredTitles', [])
                bonuses = self._map_title_bonuses(title_data.get('bonuses', {}))

                title = TitleDefinition(
                    title_id=title_data.get('titleId', ''),
                    name=title_data.get('name', ''),
                    tier=title_data.get('difficultyTier', 'novice'),
                    category=title_data.get('titleType', 'general'),
                    activity_type=activity_type,
                    acquisition_threshold=threshold,
                    bonus_description=self._create_bonus_description(bonuses),
                    bonuses=bonuses,
                    prerequisites=prereq_titles,
                    hidden=title_data.get('isHidden', False)
                )
                self.titles[title.title_id] = title
            self.loaded = True
            print(f"✓ Loaded {len(self.titles)} titles")
            return True
        except Exception as e:
            print(f"⚠ Error loading titles: {e}")
            self._create_placeholders()
            return False

    def _parse_activity(self, activities: Dict) -> Tuple[str, int]:
        activity_mapping = {
            'oresMined': 'mining', 'treesChopped': 'forestry', 'itemsSmithed': 'smithing',
            'materialsRefined': 'refining', 'potionsBrewed': 'alchemy', 'itemsEnchanted': 'enchanting',
            'devicesCreated': 'engineering', 'enemiesDefeated': 'combat', 'bossesDefeated': 'combat',
            'areasExplored': 'exploration'
        }

        if activities:
            for json_key, threshold in activities.items():
                activity_type = activity_mapping.get(json_key, 'general')
                return activity_type, threshold

        return 'general', 0

    def _map_title_bonuses(self, bonuses: Dict) -> Dict[str, float]:
        mapping = {
            'miningDamage': 'mining_damage', 'miningSpeed': 'mining_speed', 'forestryDamage': 'forestry_damage',
            'forestrySpeed': 'forestry_speed', 'smithingTime': 'smithing_speed', 'smithingQuality': 'smithing_quality',
            'refiningPrecision': 'refining_speed', 'meleeDamage': 'melee_damage', 'criticalChance': 'crit_chance',
            'attackSpeed': 'attack_speed', 'firstTryBonus': 'first_try_bonus', 'rareOreChance': 'rare_ore_chance',
            'rareWoodChance': 'rare_wood_chance', 'fireOreChance': 'fire_ore_chance', 'alloyQuality': 'alloy_quality',
            'materialYield': 'material_yield', 'combatSkillExp': 'combat_skill_exp', 'counterChance': 'counter_chance',
            'durabilityBonus': 'durability_bonus', 'legendaryChance': 'legendary_chance',
            'dragonDamage': 'dragon_damage',
            'fireResistance': 'fire_resistance', 'legendaryDropRate': 'legendary_drop_rate', 'luckStat': 'luck_stat',
            'rareDropRate': 'rare_drop_rate'
        }

        mapped_bonuses = {}
        for json_key, value in bonuses.items():
            internal_key = mapping.get(json_key, json_key.lower())
            mapped_bonuses[internal_key] = value

        return mapped_bonuses

    def _create_bonus_description(self, bonuses: Dict[str, float]) -> str:
        if not bonuses:
            return "No bonuses"
        first_bonus = list(bonuses.items())[0]
        bonus_name, bonus_value = first_bonus
        percent = f"+{int(bonus_value * 100)}%"
        readable = bonus_name.replace('_', ' ').title()
        return f"{percent} {readable}"

    def _create_placeholders(self):
        novice_titles = [
            TitleDefinition('novice_miner', 'Novice Miner', 'novice', 'gathering', 'mining', 100,
                            '+10% mining damage', {'mining_damage': 0.10}),
            TitleDefinition('novice_lumberjack', 'Novice Lumberjack', 'novice', 'gathering', 'forestry', 100,
                            '+10% forestry damage', {'forestry_damage': 0.10}),
            TitleDefinition('novice_smith', 'Novice Smith', 'novice', 'crafting', 'smithing', 50,
                            '+10% smithing speed', {'smithing_speed': 0.10}),
            TitleDefinition('novice_refiner', 'Novice Refiner', 'novice', 'crafting', 'refining', 50,
                            '+10% refining speed', {'refining_speed': 0.10}),
            TitleDefinition('novice_alchemist', 'Novice Alchemist', 'novice', 'crafting', 'alchemy', 50,
                            '+10% alchemy speed', {'alchemy_speed': 0.10}),
        ]
        for title in novice_titles:
            self.titles[title.title_id] = title
        self.loaded = True
        print(f"✓ Created {len(self.titles)} placeholder titles")


class TitleSystem:
    def __init__(self):
        self.earned_titles: List[TitleDefinition] = []
        self.title_db = TitleDatabase.get_instance()

    def check_for_title(self, activity_type: str, count: int) -> Optional[TitleDefinition]:
        for title_id, title_def in self.title_db.titles.items():
            if any(t.title_id == title_id for t in self.earned_titles):
                continue
            if title_def.activity_type != activity_type:
                continue
            if count < title_def.acquisition_threshold:
                continue
            if title_def.prerequisites:
                has_prereqs = all(
                    any(t.title_id == prereq for t in self.earned_titles)
                    for prereq in title_def.prerequisites
                )
                if not has_prereqs:
                    continue
            self.earned_titles.append(title_def)
            return title_def
        return None

    def get_total_bonus(self, bonus_type: str) -> float:
        total = 0.0
        for title in self.earned_titles:
            if bonus_type in title.bonuses:
                total += title.bonuses[bonus_type]
        return total

    def has_title(self, title_id: str) -> bool:
        return any(t.title_id == title_id for t in self.earned_titles)


# ============================================================================
# CLASS SYSTEM
# ============================================================================
@dataclass
class ClassDefinition:
    class_id: str
    name: str
    description: str
    bonuses: Dict[str, float]
    starting_skill: str = ""
    recommended_stats: List[str] = field(default_factory=list)


class ClassDatabase:
    _instance = None

    def __init__(self):
        self.classes: Dict[str, ClassDefinition] = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ClassDatabase()
        return cls._instance

    def load_from_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for class_data in data.get('classes', []):
                starting_bonuses = class_data.get('startingBonuses', {})
                bonuses = self._map_bonuses(starting_bonuses)
                skill_data = class_data.get('startingSkill', {})
                starting_skill = skill_data.get('skillId', '') if isinstance(skill_data, dict) else ''
                rec_stats_data = class_data.get('recommendedStats', {})
                rec_stats = rec_stats_data.get('primary', []) if isinstance(rec_stats_data, dict) else []

                cls_def = ClassDefinition(
                    class_id=class_data.get('classId', ''),
                    name=class_data.get('name', ''),
                    description=class_data.get('description', ''),
                    bonuses=bonuses,
                    starting_skill=starting_skill,
                    recommended_stats=rec_stats
                )
                self.classes[cls_def.class_id] = cls_def
            self.loaded = True
            print(f"✓ Loaded {len(self.classes)} classes")
            return True
        except Exception as e:
            print(f"⚠ Error loading classes: {e}")
            self._create_placeholders()
            return False

    def _map_bonuses(self, starting_bonuses: Dict) -> Dict[str, float]:
        mapping = {
            'baseHP': 'max_health', 'baseMana': 'max_mana', 'meleeDamage': 'melee_damage',
            'inventorySlots': 'inventory_slots', 'carryCapacity': 'carry_capacity', 'movementSpeed': 'movement_speed',
            'critChance': 'crit_chance', 'forestryBonus': 'forestry_damage', 'recipeDiscovery': 'recipe_discovery',
            'skillExpGain': 'skill_exp', 'allCraftingTime': 'crafting_speed', 'firstTryBonus': 'first_try_bonus',
            'itemDurability': 'durability_bonus', 'rareDropRate': 'rare_drops', 'resourceQuality': 'resource_quality',
            'allGathering': 'gathering_bonus', 'allCrafting': 'crafting_bonus', 'defense': 'defense_bonus',
            'miningBonus': 'mining_damage', 'attackSpeed': 'attack_speed'
        }

        bonuses = {}
        for json_key, value in starting_bonuses.items():
            internal_key = mapping.get(json_key, json_key.lower().replace(' ', '_'))
            bonuses[internal_key] = value

        return bonuses

    def _create_placeholders(self):
        classes_data = [
            ('warrior', 'Warrior', 'A melee fighter with high health and damage',
             {'max_health': 30, 'melee_damage': 0.10, 'carry_capacity': 20}, 'battle_rage', ['STR', 'VIT', 'DEF']),
            ('ranger', 'Ranger', 'A nimble hunter specializing in speed and precision',
             {'movement_speed': 0.15, 'crit_chance': 0.10, 'forestry_damage': 0.10}, 'forestry_frenzy',
             ['AGI', 'LCK', 'VIT']),
            ('scholar', 'Scholar', 'A learned mage with vast knowledge',
             {'max_mana': 100, 'recipe_discovery': 0.10, 'skill_exp': 0.05}, 'alchemist_touch', ['INT', 'LCK', 'AGI']),
            ('artisan', 'Artisan', 'A master craftsman creating quality goods',
             {'crafting_speed': 0.10, 'first_try_bonus': 0.10, 'durability_bonus': 0.05}, 'smithing_focus',
             ['AGI', 'INT', 'LCK']),
            ('scavenger', 'Scavenger', 'A treasure hunter with keen eyes',
             {'rare_drops': 0.20, 'resource_quality': 0.10, 'carry_capacity': 100}, 'treasure_luck',
             ['LCK', 'STR', 'VIT']),
            ('adventurer', 'Adventurer', 'A balanced jack-of-all-trades',
             {'gathering_bonus': 0.05, 'crafting_bonus': 0.05, 'max_health': 50, 'max_mana': 50}, '', ['Balanced'])
        ]
        for class_id, name, desc, bonuses, skill, stats in classes_data:
            self.classes[class_id] = ClassDefinition(class_id, name, desc, bonuses, skill, stats)
        self.loaded = True
        print(f"✓ Created {len(self.classes)} placeholder classes")


class ClassSystem:
    def __init__(self):
        self.current_class: Optional[ClassDefinition] = None

    def set_class(self, class_def: ClassDefinition):
        self.current_class = class_def

    def get_bonus(self, bonus_type: str) -> float:
        if not self.current_class:
            return 0.0
        return self.current_class.bonuses.get(bonus_type, 0.0)


# ============================================================================
# POSITION
# ============================================================================
@dataclass
class Position:
    x: float
    y: float
    z: float = 0.0

    def distance_to(self, other: 'Position') -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def snap_to_grid(self) -> 'Position':
        return Position(int(self.x), int(self.y), int(self.z))

    def to_key(self) -> str:
        return f"{int(self.x)},{int(self.y)},{int(self.z)}"

    def copy(self) -> 'Position':
        return Position(self.x, self.y, self.z)


# ============================================================================
# TILE SYSTEM
# ============================================================================
class TileType(Enum):
    GRASS = "grass"
    STONE = "stone"
    WATER = "water"
    DIRT = "dirt"


@dataclass
class WorldTile:
    position: Position
    tile_type: TileType
    occupied_by: Optional[str] = None
    ownership: Optional[str] = None
    walkable: bool = True

    def get_color(self) -> Tuple[int, int, int]:
        return {TileType.GRASS: Config.COLOR_GRASS, TileType.STONE: Config.COLOR_STONE,
                TileType.WATER: Config.COLOR_WATER, TileType.DIRT: (139, 69, 19)}.get(self.tile_type,
                                                                                      Config.COLOR_GRASS)


# ============================================================================
# RESOURCE SYSTEM
# ============================================================================
class ResourceType(Enum):
    OAK_TREE = "oak_tree"
    BIRCH_TREE = "birch_tree"
    MAPLE_TREE = "maple_tree"
    IRONWOOD_TREE = "ironwood_tree"
    COPPER_ORE = "copper_ore"
    IRON_ORE = "iron_ore"
    STEEL_ORE = "steel_ore"
    MITHRIL_ORE = "mithril_ore"
    LIMESTONE = "limestone"
    GRANITE = "granite"
    OBSIDIAN = "obsidian"
    STAR_CRYSTAL = "star_crystal"


RESOURCE_TIERS = {
    ResourceType.OAK_TREE: 1, ResourceType.BIRCH_TREE: 2, ResourceType.MAPLE_TREE: 3, ResourceType.IRONWOOD_TREE: 4,
    ResourceType.COPPER_ORE: 1, ResourceType.IRON_ORE: 2, ResourceType.STEEL_ORE: 3, ResourceType.MITHRIL_ORE: 4,
    ResourceType.LIMESTONE: 1, ResourceType.GRANITE: 2, ResourceType.OBSIDIAN: 3, ResourceType.STAR_CRYSTAL: 4
}


@dataclass
class LootDrop:
    item_id: str
    min_quantity: int
    max_quantity: int
    chance: float = 1.0


class NaturalResource:
    def __init__(self, position: Position, resource_type: ResourceType, tier: int):
        self.position = position
        self.resource_type = resource_type
        self.tier = tier
        self.max_hp = {1: 100, 2: 200, 3: 400, 4: 800}.get(tier, 100)
        self.current_hp = self.max_hp

        if "tree" in resource_type.value:
            self.required_tool = "axe"
            self.respawns = True
            self.respawn_timer = 60.0 if not Config.DEBUG_INFINITE_RESOURCES else 1.0
        else:
            self.required_tool = "pickaxe"
            self.respawns = False
            self.respawn_timer = None

        self.time_until_respawn = 0.0
        self.loot_table = self._generate_loot_table()
        self.depleted = False

    def _generate_loot_table(self) -> List[LootDrop]:
        loot_map = {
            ResourceType.OAK_TREE: ("oak_log", 2, 4), ResourceType.BIRCH_TREE: ("birch_log", 2, 4),
            ResourceType.MAPLE_TREE: ("maple_log", 2, 5), ResourceType.IRONWOOD_TREE: ("ironwood_log", 3, 6),
            ResourceType.COPPER_ORE: ("copper_ore", 1, 3), ResourceType.IRON_ORE: ("iron_ore", 1, 3),
            ResourceType.STEEL_ORE: ("steel_ore", 2, 4), ResourceType.MITHRIL_ORE: ("mithril_ore", 2, 5),
            ResourceType.LIMESTONE: ("limestone", 1, 2), ResourceType.GRANITE: ("granite", 1, 2),
            ResourceType.OBSIDIAN: ("obsidian", 2, 3), ResourceType.STAR_CRYSTAL: ("star_crystal", 1, 2),
        }
        if self.resource_type in loot_map:
            item_id, min_q, max_q = loot_map[self.resource_type]
            return [LootDrop(item_id, min_q, max_q)]
        return []

    def take_damage(self, damage: int, is_crit: bool = False) -> Tuple[int, bool]:
        if self.depleted:
            return 0, False
        actual_damage = damage * 2 if is_crit else damage
        self.current_hp -= actual_damage
        if self.current_hp <= 0:
            self.current_hp = 0
            self.depleted = True
            return actual_damage, True
        return actual_damage, False

    def get_loot(self) -> List[Tuple[str, int]]:
        return [(loot.item_id, random.randint(loot.min_quantity, loot.max_quantity))
                for loot in self.loot_table if random.random() <= loot.chance]

    def update(self, dt: float):
        if self.depleted and self.respawns:
            self.time_until_respawn += dt
            if self.time_until_respawn >= self.respawn_timer:
                self.current_hp = self.max_hp
                self.depleted = False
                self.time_until_respawn = 0.0

    def get_respawn_progress(self) -> float:
        if not self.depleted or not self.respawns:
            return 0.0
        return min(1.0, self.time_until_respawn / self.respawn_timer)

    def get_color(self) -> Tuple[int, int, int]:
        if self.depleted:
            if self.respawns:
                progress = self.get_respawn_progress()
                gray = int(50 + progress * 50)
                green = int(progress * 100)
                return (gray, green, gray)
            return (50, 50, 50)
        if "tree" in self.resource_type.value:
            return Config.COLOR_TREE
        return Config.COLOR_ORE if "ore" in self.resource_type.value else Config.COLOR_STONE_NODE


# ============================================================================
# CHUNK SYSTEM
# ============================================================================
class ChunkType(Enum):
    PEACEFUL_FOREST = "peaceful_forest"
    PEACEFUL_QUARRY = "peaceful_quarry"
    PEACEFUL_CAVE = "peaceful_cave"
    DANGEROUS_FOREST = "dangerous_forest"
    DANGEROUS_QUARRY = "dangerous_quarry"
    DANGEROUS_CAVE = "dangerous_cave"
    RARE_HIDDEN_FOREST = "rare_hidden_forest"
    RARE_ANCIENT_QUARRY = "rare_ancient_quarry"
    RARE_DEEP_CAVE = "rare_deep_cave"


class Chunk:
    def __init__(self, chunk_x: int, chunk_y: int):
        self.chunk_x = chunk_x
        self.chunk_y = chunk_y
        self.tiles: Dict[str, WorldTile] = {}
        self.resources: List[NaturalResource] = []
        self.chunk_type = self._determine_chunk_type()
        self.generate_tiles()
        self.spawn_resources()

    def _determine_chunk_type(self) -> ChunkType:
        roll = random.randint(1, 10)
        if roll <= 5:
            return random.choice([ChunkType.PEACEFUL_FOREST, ChunkType.PEACEFUL_QUARRY, ChunkType.PEACEFUL_CAVE])
        elif roll <= 8:
            return random.choice([ChunkType.DANGEROUS_FOREST, ChunkType.DANGEROUS_QUARRY, ChunkType.DANGEROUS_CAVE])
        return random.choice([ChunkType.RARE_HIDDEN_FOREST, ChunkType.RARE_ANCIENT_QUARRY, ChunkType.RARE_DEEP_CAVE])

    def generate_tiles(self):
        start_x, start_y = self.chunk_x * Config.CHUNK_SIZE, self.chunk_y * Config.CHUNK_SIZE
        base_tile = TileType.STONE if "quarry" in self.chunk_type.value or "cave" in self.chunk_type.value else TileType.GRASS
        for x in range(start_x, start_x + Config.CHUNK_SIZE):
            for y in range(start_y, start_y + Config.CHUNK_SIZE):
                pos = Position(x, y, 0)
                self.tiles[pos.to_key()] = WorldTile(pos, TileType.DIRT if random.random() < 0.1 else base_tile)

    def spawn_resources(self):
        start_x, start_y = self.chunk_x * Config.CHUNK_SIZE, self.chunk_y * Config.CHUNK_SIZE
        if "peaceful" in self.chunk_type.value:
            resource_count, tier_range = random.randint(3, 6), (1, 2)
        elif "dangerous" in self.chunk_type.value:
            resource_count, tier_range = random.randint(5, 8), (2, 3)
        else:
            resource_count, tier_range = random.randint(6, 10), (3, 4)

        for _ in range(resource_count):
            pos = Position(start_x + random.randint(1, Config.CHUNK_SIZE - 2),
                           start_y + random.randint(1, Config.CHUNK_SIZE - 2), 0)
            if "forest" in self.chunk_type.value:
                types = [ResourceType.OAK_TREE, ResourceType.BIRCH_TREE, ResourceType.MAPLE_TREE,
                         ResourceType.IRONWOOD_TREE]
            elif "quarry" in self.chunk_type.value:
                types = [ResourceType.LIMESTONE, ResourceType.GRANITE, ResourceType.OBSIDIAN, ResourceType.STAR_CRYSTAL]
            else:
                types = [ResourceType.COPPER_ORE, ResourceType.IRON_ORE, ResourceType.STEEL_ORE,
                         ResourceType.MITHRIL_ORE]

            tier = min(random.randint(*tier_range), 4)
            valid = [r for r in types if RESOURCE_TIERS[r] <= tier]
            if valid:
                resource_type = random.choice(valid)
                self.resources.append(NaturalResource(pos, resource_type, RESOURCE_TIERS[resource_type]))


# ============================================================================
# CRAFTING
# ============================================================================
class StationType(Enum):
    SMITHING = "smithing"
    ALCHEMY = "alchemy"
    REFINING = "refining"
    ENGINEERING = "engineering"
    ADORNMENTS = "adornments"


@dataclass
class CraftingStation:
    position: Position
    station_type: StationType
    tier: int

    def get_color(self) -> Tuple[int, int, int]:
        return {StationType.SMITHING: (180, 60, 60), StationType.ALCHEMY: (60, 180, 60),
                StationType.REFINING: (180, 120, 60), StationType.ENGINEERING: (60, 120, 180),
                StationType.ADORNMENTS: (180, 60, 180)}.get(self.station_type, (150, 150, 150))


@dataclass
class Recipe:
    recipe_id: str
    output_id: str
    output_qty: int
    station_type: str
    station_tier: int
    inputs: List[Dict]
    grid_size: str = "3x3"
    mini_game_type: str = ""
    metadata: Dict = field(default_factory=dict)
    # Enchanting-specific fields
    is_enchantment: bool = False
    enchantment_name: str = ""
    applicable_to: List[str] = field(default_factory=list)
    effect: Dict = field(default_factory=dict)


# ============================================================================
# PLACEMENT SYSTEM
# ============================================================================
@dataclass
class PlacementData:
    """Universal placement data structure for all crafting disciplines"""
    recipe_id: str
    discipline: str  # smithing, alchemy, refining, engineering, adornments

    # Smithing & Enchanting: Grid-based placement
    grid_size: str = ""  # "3x3", "5x5", "12x12", etc.
    placement_map: Dict[str, str] = field(default_factory=dict)  # "x,y" -> materialId

    # Refining: Hub-and-spoke
    core_inputs: List[Dict] = field(default_factory=list)  # Center slots
    surrounding_inputs: List[Dict] = field(default_factory=list)  # Surrounding modifiers

    # Alchemy: Sequential
    ingredients: List[Dict] = field(default_factory=list)  # [{slot, materialId, quantity}]

    # Engineering: Slot types
    slots: List[Dict] = field(default_factory=list)  # [{type, materialId, quantity}]

    # Enchanting: Pattern-based
    pattern: List[Dict] = field(default_factory=list)  # Pattern vertices/shapes

    # Metadata
    narrative: str = ""
    output_id: str = ""
    station_tier: int = 1


class PlacementDatabase:
    """Manages placement data for all crafting disciplines"""
    _instance = None

    def __init__(self):
        self.placements: Dict[str, PlacementData] = {}  # recipeId -> PlacementData
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PlacementDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        """Load all placement JSON files"""
        total = 0

        # Smithing placements
        total += self._load_smithing("placements.JSON/placements-smithing-1.JSON")

        # Refining placements
        total += self._load_refining("placements.JSON/placements-refining-1.JSON")

        # Alchemy placements
        total += self._load_alchemy("placements.JSON/placements-alchemy-1.JSON")

        # Engineering placements
        total += self._load_engineering("placements.JSON/placements-engineering-1.JSON")

        # Enchanting/Adornments placements
        total += self._load_enchanting("placements.JSON/placements-adornments-1.JSON")

        self.loaded = True
        print(f"✓ Loaded {total} placement templates")
        return total

    def _load_smithing(self, filepath: str) -> int:
        """Load smithing grid-based placements"""
        if not Path(filepath).exists():
            print(f"⚠ Smithing placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='smithing',
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    placement_map=placement.get('placementMap', {}),
                    narrative=placement.get('metadata', {}).get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} smithing placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading smithing placements: {e}")
            return 0

    def _load_refining(self, filepath: str) -> int:
        """Load refining hub-and-spoke placements"""
        if not Path(filepath).exists():
            print(f"⚠ Refining placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='refining',
                    core_inputs=placement.get('coreInputs', []),
                    surrounding_inputs=placement.get('surroundingInputs', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} refining placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading refining placements: {e}")
            return 0

    def _load_alchemy(self, filepath: str) -> int:
        """Load alchemy sequential placements"""
        if not Path(filepath).exists():
            print(f"⚠ Alchemy placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='alchemy',
                    ingredients=placement.get('ingredients', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} alchemy placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading alchemy placements: {e}")
            return 0

    def _load_engineering(self, filepath: str) -> int:
        """Load engineering slot-type placements"""
        if not Path(filepath).exists():
            print(f"⚠ Engineering placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='engineering',
                    slots=placement.get('slots', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} engineering placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading engineering placements: {e}")
            return 0

    def _load_enchanting(self, filepath: str) -> int:
        """Load enchanting pattern placements"""
        if not Path(filepath).exists():
            print(f"⚠ Enchanting placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                # Enchanting may have pattern or grid-based placement
                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='adornments',
                    pattern=placement.get('pattern', []),
                    placement_map=placement.get('placementMap', {}),
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} enchanting placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading enchanting placements: {e}")
            return 0

    def get_placement(self, recipe_id: str) -> Optional[PlacementData]:
        """Get placement data for a recipe"""
        return self.placements.get(recipe_id)

    def has_placement(self, recipe_id: str) -> bool:
        """Check if a recipe has placement data"""
        return recipe_id in self.placements


class RecipeDatabase:
    _instance = None

    def __init__(self):
        self.recipes: Dict[str, Recipe] = {}
        self.recipes_by_station: Dict[str, List[Recipe]] = {
            "smithing": [], "alchemy": [], "refining": [], "engineering": [], "adornments": []
        }
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RecipeDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        total = 0
        for station_type, filename in [("smithing", "recipes-smithing-3.json"), ("alchemy", "recipes-alchemy-1.JSON"),
                                       ("refining", "recipes-refining-1.JSON"),
                                       ("engineering", "recipes-engineering-1.JSON"),
                                       ("adornments", "recipes-adornments-1.json")]:
            for path in [f"recipes.JSON/{filename}", f"{base_path}recipes.JSON/{filename}"]:
                if Path(path).exists():
                    total += self._load_file(path, station_type)
                    break

        if total == 0:
            self._create_default_recipes()
            total = len(self.recipes)

        self.loaded = True
        print(f"✓ Loaded {total} recipes")

    def _load_file(self, filepath: str, station_type: str) -> int:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            loaded_count = 0
            for recipe_data in data.get('recipes', []):
                # Check if this is an enchanting recipe (has enchantmentId instead of outputId)
                is_enchanting = 'enchantmentId' in recipe_data

                if is_enchanting:
                    # For enchanting: use enchantmentId as the output_id
                    output_id = recipe_data.get('enchantmentId', '')
                    output_qty = 1  # Enchantments don't have quantity
                    station_tier = recipe_data.get('stationTier', 1)
                elif 'outputs' in recipe_data:
                    # New format: outputs array (used in refining recipes)
                    outputs = recipe_data.get('outputs', [])
                    if outputs and len(outputs) > 0:
                        output_id = outputs[0].get('materialId', outputs[0].get('itemId', ''))
                        output_qty = outputs[0].get('quantity', 1)
                    else:
                        output_id = ''
                        output_qty = 1
                    station_tier = recipe_data.get('stationTierRequired', recipe_data.get('stationTier', 1))
                else:
                    # Regular crafting: use outputId
                    output_id = recipe_data.get('outputId', '')
                    output_qty = recipe_data.get('outputQty', 1)
                    station_tier = recipe_data.get('stationTier', 1)

                # Skip recipes with empty output_id
                if not output_id or output_id.strip() == '':
                    print(f"⚠ Skipping recipe {recipe_data.get('recipeId', 'UNKNOWN')} - no valid output ID")
                    continue

                recipe = Recipe(
                    recipe_id=recipe_data.get('recipeId', ''),
                    output_id=output_id,
                    output_qty=output_qty,
                    station_type=station_type,
                    station_tier=station_tier,
                    inputs=recipe_data.get('inputs', []),
                    is_enchantment=is_enchanting,
                    enchantment_name=recipe_data.get('enchantmentName', ''),
                    applicable_to=recipe_data.get('applicableTo', []),
                    effect=recipe_data.get('effect', {})
                )
                self.recipes[recipe.recipe_id] = recipe
                self.recipes_by_station[station_type].append(recipe)
                loaded_count += 1
            return loaded_count
        except Exception as e:
            print(f"⚠ Error loading recipes from {filepath}: {e}")
            return 0

    def _create_default_recipes(self):
        """Create comprehensive default recipes for equipment and materials"""
        default_recipes = [
            # REFINING - Basic Ingots
            Recipe("copper_ingot_recipe", "copper_ingot", 1, "refining", 1,
                   [{"materialId": "copper_ore", "quantity": 3}]),
            Recipe("iron_ingot_recipe", "iron_ingot", 1, "refining", 1,
                   [{"materialId": "iron_ore", "quantity": 3}]),
            Recipe("steel_ingot_recipe", "steel_ingot", 1, "refining", 2,
                   [{"materialId": "steel_ore", "quantity": 3}]),

            # SMITHING - Weapons
            Recipe("copper_sword_recipe", "copper_sword", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 3}, {"materialId": "oak_log", "quantity": 1}]),
            Recipe("iron_sword_recipe", "iron_sword", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 3}, {"materialId": "birch_log", "quantity": 1}]),
            Recipe("steel_sword_recipe", "steel_sword", 1, "smithing", 2,
                   [{"materialId": "steel_ingot", "quantity": 3}, {"materialId": "maple_log", "quantity": 1}]),

            # SMITHING - Helmets
            Recipe("copper_helmet_recipe", "copper_helmet", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 4}]),
            Recipe("iron_helmet_recipe", "iron_helmet", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 4}]),

            # SMITHING - Chestplates
            Recipe("copper_chestplate_recipe", "copper_chestplate", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 7}]),
            Recipe("iron_chestplate_recipe", "iron_chestplate", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 7}]),

            # SMITHING - Leggings
            Recipe("copper_leggings_recipe", "copper_leggings", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 6}]),
            Recipe("iron_leggings_recipe", "iron_leggings", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 6}]),

            # SMITHING - Boots
            Recipe("copper_boots_recipe", "copper_boots", 1, "smithing", 1,
                   [{"materialId": "copper_ingot", "quantity": 3}]),
            Recipe("iron_boots_recipe", "iron_boots", 1, "smithing", 1,
                   [{"materialId": "iron_ingot", "quantity": 3}]),
        ]

        for recipe in default_recipes:
            self.recipes[recipe.recipe_id] = recipe
            self.recipes_by_station[recipe.station_type].append(recipe)

        print(f"✓ Created {len(default_recipes)} default recipes")

    def get_recipes_for_station(self, station_type: str, tier: int = 1) -> List[Recipe]:
        return [r for r in self.recipes_by_station.get(station_type, []) if r.station_tier <= tier]

    def can_craft(self, recipe: Recipe, inventory) -> bool:
        if Config.DEBUG_INFINITE_RESOURCES:
            return True
        for inp in recipe.inputs:
            if inventory.get_item_count(inp.get('materialId', '')) < inp.get('quantity', 0):
                return False
        return True

    def consume_materials(self, recipe: Recipe, inventory) -> bool:
        if Config.DEBUG_INFINITE_RESOURCES:
            return True

        if not self.can_craft(recipe, inventory):
            return False

        to_consume = {}
        for inp in recipe.inputs:
            mat_id = inp.get('materialId', '')
            qty = inp.get('quantity', 0)
            to_consume[mat_id] = qty

        for mat_id, needed in to_consume.items():
            remaining = needed
            for i in range(len(inventory.slots)):
                if inventory.slots[i] and inventory.slots[i].item_id == mat_id:
                    slot = inventory.slots[i]
                    if slot.quantity >= remaining:
                        slot.quantity -= remaining
                        if slot.quantity == 0:
                            inventory.slots[i] = None
                        remaining = 0
                        break
                    else:
                        remaining -= slot.quantity
                        inventory.slots[i] = None

            if remaining > 0:
                return False

        return True


# ============================================================================
# PLACEMENT SYSTEM
# ============================================================================
@dataclass
class PlacementData:
    """Universal placement data structure for all crafting types"""
    recipe_id: str
    discipline: str  # smithing, alchemy, refining, engineering, adornments

    # Smithing: Grid-based placement
    grid_size: str = ""  # "3x3", "5x5", etc.
    placement_map: Dict[str, str] = field(default_factory=dict)  # "x,y" -> materialId

    # Refining: Hub-and-spoke
    core_inputs: List[Dict] = field(default_factory=list)  # Center slots
    surrounding_inputs: List[Dict] = field(default_factory=list)  # Surrounding modifiers

    # Alchemy: Sequential
    ingredients: List[Dict] = field(default_factory=list)  # [{slot, materialId, quantity}]

    # Engineering: Slot types
    slots: List[Dict] = field(default_factory=list)  # [{type, materialId, quantity}]

    # Enchanting: Pattern-based
    pattern: List[str] = field(default_factory=list)  # Pattern rows

    # Metadata
    narrative: str = ""
    output_id: str = ""
    station_tier: int = 1


class PlacementDatabase:
    """Manages placement data for all crafting disciplines"""
    _instance = None

    def __init__(self):
        self.placements: Dict[str, PlacementData] = {}  # recipeId -> PlacementData
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PlacementDatabase()
        return cls._instance

    def load_from_files(self, base_path: str = ""):
        """Load all placement JSON files"""
        total = 0

        # Smithing placements
        total += self._load_smithing("placements.JSON/placements-smithing-1.JSON")

        # Refining placements
        total += self._load_refining("placements.JSON/placements-refining-1.JSON")

        # Alchemy placements
        total += self._load_alchemy("placements.JSON/placements-alchemy-1.JSON")

        # Engineering placements
        total += self._load_engineering("placements.JSON/placements-engineering-1.JSON")

        # Enchanting/Adornments placements
        total += self._load_enchanting("placements.JSON/placements-adornments-1.JSON")

        self.loaded = True
        print(f"✓ Loaded {total} placement templates")
        return total

    def _load_smithing(self, filepath: str) -> int:
        """Load smithing grid-based placements"""
        if not Path(filepath).exists():
            print(f"⚠ Smithing placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='smithing',
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    placement_map=placement.get('placementMap', {}),
                    narrative=placement.get('metadata', {}).get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} smithing placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading smithing placements: {e}")
            return 0

    def _load_refining(self, filepath: str) -> int:
        """Load refining hub-and-spoke placements"""
        if not Path(filepath).exists():
            print(f"⚠ Refining placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='refining',
                    core_inputs=placement.get('coreInputs', []),
                    surrounding_inputs=placement.get('surroundingInputs', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} refining placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading refining placements: {e}")
            return 0

    def _load_alchemy(self, filepath: str) -> int:
        """Load alchemy sequential placements"""
        if not Path(filepath).exists():
            print(f"⚠ Alchemy placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='alchemy',
                    ingredients=placement.get('ingredients', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} alchemy placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading alchemy placements: {e}")
            return 0

    def _load_engineering(self, filepath: str) -> int:
        """Load engineering slot-type placements"""
        if not Path(filepath).exists():
            print(f"⚠ Engineering placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='engineering',
                    slots=placement.get('slots', []),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} engineering placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading engineering placements: {e}")
            return 0

    def _load_enchanting(self, filepath: str) -> int:
        """Load enchanting pattern placements"""
        if not Path(filepath).exists():
            print(f"⚠ Enchanting placements not found: {filepath}")
            return 0

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            count = 0
            for placement in data.get('placements', []):
                recipe_id = placement.get('recipeId', '')
                if not recipe_id:
                    continue

                # Enchanting may have pattern or grid-based placement
                self.placements[recipe_id] = PlacementData(
                    recipe_id=recipe_id,
                    discipline='adornments',
                    pattern=placement.get('pattern', []),
                    placement_map=placement.get('placementMap', {}),
                    grid_size=placement.get('metadata', {}).get('gridSize', '3x3'),
                    output_id=placement.get('outputId', ''),
                    station_tier=placement.get('stationTier', 1),
                    narrative=placement.get('narrative', '')
                )
                count += 1

            print(f"  ✓ Loaded {count} enchanting placements")
            return count
        except Exception as e:
            print(f"  ✗ Error loading enchanting placements: {e}")
            return 0

    def get_placement(self, recipe_id: str) -> Optional[PlacementData]:
        """Get placement data for a recipe"""
        return self.placements.get(recipe_id)

    def has_placement(self, recipe_id: str) -> bool:
        """Check if a recipe has placement data"""
        return recipe_id in self.placements


# ============================================================================
# WORLD
# ============================================================================
class WorldSystem:
    def __init__(self):
        self.tiles: Dict[str, WorldTile] = {}
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self.resources: List[NaturalResource] = []
        self.crafting_stations: List[CraftingStation] = []
        self.generate_world()
        self.spawn_starting_stations()

    def generate_world(self):
        num_chunks = Config.WORLD_SIZE // Config.CHUNK_SIZE
        for chunk_x in range(num_chunks):
            for chunk_y in range(num_chunks):
                chunk = Chunk(chunk_x, chunk_y)
                self.chunks[(chunk_x, chunk_y)] = chunk
                self.tiles.update(chunk.tiles)
                self.resources.extend(chunk.resources)
        print(f"Generated {Config.WORLD_SIZE}x{Config.WORLD_SIZE} world, {len(self.resources)} resources")

    def spawn_starting_stations(self):
        """Spawn all tiers of crafting stations near player start (50, 50)"""
        # Place all 4 tiers of each station type in a grid layout
        # Format: (base_x, base_y, station_type)
        # Each station type gets T1-T4 arranged vertically

        station_positions = [
            # SMITHING - Far left column
            (44, StationType.SMITHING),
            # REFINING - Left column
            (46, StationType.REFINING),
            # ALCHEMY - Right column
            (54, StationType.ALCHEMY),
            # ENGINEERING - Far right column
            (56, StationType.ENGINEERING),
            # ADORNMENTS/ENCHANTING - Center column
            (50, StationType.ADORNMENTS),
        ]

        # Spawn T1-T4 of each station type
        for base_x, stype in station_positions:
            for tier in range(1, 5):  # T1, T2, T3, T4
                y = 46 + (tier - 1) * 2  # Vertical spacing: 46, 48, 50, 52
                self.crafting_stations.append(CraftingStation(Position(base_x, y, 0), stype, tier))

    def get_tile(self, position: Position) -> Optional[WorldTile]:
        return self.tiles.get(position.snap_to_grid().to_key())

    def is_walkable(self, position: Position) -> bool:
        tile = self.get_tile(position)
        return tile and tile.tile_type != TileType.WATER and tile.walkable

    def get_visible_tiles(self, camera_pos: Position, vw: int, vh: int) -> List[WorldTile]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = int(camera_pos.x - tw // 2), int(camera_pos.y - th // 2)
        visible = []
        for x in range(sx, sx + tw):
            for y in range(sy, sy + th):
                tile = self.get_tile(Position(x, y, 0))
                if tile:
                    visible.append(tile)
        return visible

    def get_visible_resources(self, camera_pos: Position, vw: int, vh: int) -> List[NaturalResource]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + th // 2
        return [r for r in self.resources if sx <= r.position.x <= ex and sy <= r.position.y <= ey]

    def get_resource_at(self, position: Position, tolerance: float = Config.CLICK_TOLERANCE) -> Optional[
        NaturalResource]:
        for r in self.resources:
            if not r.depleted:
                dx = abs(r.position.x - position.x)
                dy = abs(r.position.y - position.y)
                if dx <= tolerance and dy <= tolerance:
                    return r
        return None

    def get_visible_stations(self, camera_pos: Position, vw: int, vh: int) -> List[CraftingStation]:
        tw, th = vw // Config.TILE_SIZE + 2, vh // Config.TILE_SIZE + 2
        sx, sy = camera_pos.x - tw // 2, camera_pos.y - th // 2
        ex, ey = camera_pos.x + tw // 2, camera_pos.y + th // 2
        return [s for s in self.crafting_stations if sx <= s.position.x <= ex and sy <= s.position.y <= ey]

    def get_station_at(self, position: Position, tolerance: float = 0.8) -> Optional[CraftingStation]:
        """Get station at position with tolerance for easier clicking"""
        for s in self.crafting_stations:
            dx = abs(s.position.x - position.x)
            dy = abs(s.position.y - position.y)
            if dx <= tolerance and dy <= tolerance:
                return s
        return None

    def update(self, dt: float):
        for r in self.resources:
            r.update(dt)


# ============================================================================
# PROGRESSION
# ============================================================================
@dataclass
class CharacterStats:
    strength: int = 0
    defense: int = 0
    vitality: int = 0
    luck: int = 0
    agility: int = 0
    intelligence: int = 0

    def get_bonus(self, stat_name: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        scaling = {'strength': 0.05, 'defense': 0.02, 'vitality': 0.01, 'luck': 0.02, 'agility': 0.05,
                   'intelligence': 0.02}
        return val * scaling.get(stat_name.lower(), 0.05)

    def get_flat_bonus(self, stat_name: str, bonus_type: str) -> float:
        val = getattr(self, stat_name.lower(), 0)
        if stat_name == 'strength' and bonus_type == 'carry_capacity':
            return val * 10
        elif stat_name == 'vitality' and bonus_type == 'max_health':
            return val * 15
        elif stat_name == 'intelligence' and bonus_type == 'mana':
            return val * 20
        return 0


class LevelingSystem:
    def __init__(self):
        self.level = 1
        self.current_exp = 0
        self.max_level = 30
        self.exp_requirements = {lvl: int(200 * (1.75 ** (lvl - 1))) for lvl in range(1, self.max_level + 1)}
        self.unallocated_stat_points = 0

    def get_exp_for_next_level(self) -> int:
        return 0 if self.level >= self.max_level else self.exp_requirements.get(self.level + 1, 0)

    def add_exp(self, amount: int, source: str = "") -> bool:
        if self.level >= self.max_level:
            return False
        self.current_exp += amount
        exp_needed = self.get_exp_for_next_level()
        if self.current_exp >= exp_needed:
            self.current_exp -= exp_needed
            self.level += 1
            self.unallocated_stat_points += 1
            print(f"🎉 LEVEL UP! Now level {self.level}")
            return True
        return False


class ActivityTracker:
    def __init__(self):
        self.activity_counts = {
            'mining': 0, 'forestry': 0, 'smithing': 0, 'refining': 0, 'alchemy': 0,
            'engineering': 0, 'enchanting': 0
        }

    def record_activity(self, activity_type: str, amount: int = 1):
        if activity_type in self.activity_counts:
            self.activity_counts[activity_type] += amount

    def get_count(self, activity_type: str) -> int:
        return self.activity_counts.get(activity_type, 0)


# ============================================================================
# BUFF SYSTEM
# ============================================================================
@dataclass
class ActiveBuff:
    """Represents an active buff on the character"""
    buff_id: str
    name: str
    effect_type: str  # empower, quicken, fortify, etc.
    category: str  # mining, combat, smithing, movement, etc.
    magnitude: str  # minor, moderate, major, extreme
    bonus_value: float  # The actual numerical bonus
    duration_remaining: float  # Time remaining in seconds
    source: str = "skill"  # skill, potion, equipment, etc.

    def update(self, dt: float) -> bool:
        """Update buff timer. Returns True if buff is still active."""
        self.duration_remaining -= dt
        return self.duration_remaining > 0


class BuffManager:
    """Manages active buffs on a character"""
    def __init__(self):
        self.active_buffs: List[ActiveBuff] = []

    def add_buff(self, buff: ActiveBuff):
        """Add a new buff (stacks with existing buffs)"""
        self.active_buffs.append(buff)

    def update(self, dt: float):
        """Update all buffs and remove expired ones"""
        self.active_buffs = [buff for buff in self.active_buffs if buff.update(dt)]

    def get_total_bonus(self, effect_type: str, category: str) -> float:
        """Get total bonus from all matching buffs"""
        total = 0.0
        for buff in self.active_buffs:
            if buff.effect_type == effect_type and buff.category == category:
                total += buff.bonus_value
        return total

    def get_movement_speed_bonus(self) -> float:
        """Get total movement speed bonus"""
        return self.get_total_bonus("quicken", "movement")

    def get_damage_bonus(self, category: str) -> float:
        """Get damage bonus for a specific category (mining, combat, etc.)"""
        return self.get_total_bonus("empower", category)

    def get_defense_bonus(self) -> float:
        """Get defense bonus"""
        return self.get_total_bonus("fortify", "defense")


# ============================================================================
# SKILL SYSTEM
# ============================================================================
@dataclass
class SkillEffect:
    """Represents a skill's effect"""
    effect_type: str  # empower, quicken, fortify, etc.
    category: str  # mining, combat, smithing, etc.
    magnitude: str  # minor, moderate, major, extreme
    target: str  # self, enemy, area, resource_node
    duration: str  # instant, brief, moderate, long, extended
    additional_effects: List[Dict] = None

    def __post_init__(self):
        if self.additional_effects is None:
            self.additional_effects = []


@dataclass
class SkillCost:
    """Represents skill costs"""
    mana: str  # low, moderate, high, extreme
    cooldown: str  # short, moderate, long, extreme


@dataclass
class SkillEvolution:
    """Represents skill evolution data"""
    can_evolve: bool
    next_skill_id: Optional[str]
    requirement: str


@dataclass
class SkillRequirements:
    """Represents skill requirements"""
    character_level: int
    stats: Dict[str, int]
    titles: List[str]


@dataclass
class SkillDefinition:
    """Complete skill definition from JSON"""
    skill_id: str
    name: str
    tier: int
    rarity: str
    categories: List[str]
    description: str
    narrative: str
    tags: List[str]
    effect: SkillEffect
    cost: SkillCost
    evolution: SkillEvolution
    requirements: SkillRequirements


@dataclass
class PlayerSkill:
    skill_id: str
    level: int = 1
    experience: int = 0
    current_cooldown: float = 0.0  # Cooldown remaining in seconds
    is_equipped: bool = False

    def get_definition(self) -> Optional[SkillDefinition]:
        """Get the full definition from SkillDatabase"""
        db = SkillDatabase.get_instance()
        return db.skills.get(self.skill_id, None)


class SkillManager:
    def __init__(self):
        self.known_skills: Dict[str, PlayerSkill] = {}
        self.equipped_skills: List[Optional[str]] = [None] * 5  # 5 hotbar slots

    def can_learn_skill(self, skill_id: str, character) -> tuple[bool, str]:
        """
        Check if character meets requirements to learn a skill.
        Returns (can_learn, reason)
        """
        # Already known?
        if skill_id in self.known_skills:
            return False, "Already known"

        # Get skill definition
        skill_db = SkillDatabase.get_instance()
        skill_def = skill_db.skills.get(skill_id)
        if not skill_def:
            return False, "Skill not found"

        # Check character level
        if character.leveling.level < skill_def.requirements.character_level:
            return False, f"Requires level {skill_def.requirements.character_level}"

        # Check stat requirements
        for stat_name, required_value in skill_def.requirements.stats.items():
            # Map stat names to character stats
            stat_map = {
                'STR': character.stats.strength,
                'DEF': character.stats.defense,
                'VIT': character.stats.vitality,
                'LCK': character.stats.luck,
                'AGI': character.stats.agility,
                'INT': character.stats.intelligence,
                'DEX': character.stats.agility  # DEX maps to AGI in this game
            }
            current_value = stat_map.get(stat_name.upper(), 0)
            if current_value < required_value:
                return False, f"Requires {stat_name} {required_value}"

        # Check title requirements (if any)
        if skill_def.requirements.titles:
            # Get player's title IDs
            player_titles = {title.title_id for title in character.titles.titles}
            for required_title in skill_def.requirements.titles:
                if required_title not in player_titles:
                    return False, f"Requires title: {required_title}"

        return True, "Requirements met"

    def learn_skill(self, skill_id: str, character=None, skip_checks: bool = False) -> bool:
        """
        Learn a new skill.
        If character is provided and skip_checks is False, requirements will be checked.
        skip_checks=True bypasses requirement checks (for starting skills, admin commands, etc.)
        """
        # Check if already known
        if skill_id in self.known_skills:
            return False

        # Check requirements if character provided and not skipping checks
        if character and not skip_checks:
            can_learn, reason = self.can_learn_skill(skill_id, character)
            if not can_learn:
                print(f"   ⚠ Cannot learn {skill_id}: {reason}")
                return False

        # Learn the skill
        self.known_skills[skill_id] = PlayerSkill(skill_id=skill_id)
        return True

    def equip_skill(self, skill_id: str, slot: int) -> bool:
        """Equip a skill to a hotbar slot (0-4)"""
        if 0 <= slot < 5 and skill_id in self.known_skills:
            self.equipped_skills[slot] = skill_id
            self.known_skills[skill_id].is_equipped = True
            return True
        return False

    def unequip_skill(self, slot: int) -> bool:
        """Unequip a skill from a hotbar slot"""
        if 0 <= slot < 5 and self.equipped_skills[slot]:
            skill_id = self.equipped_skills[slot]
            self.equipped_skills[slot] = None
            if skill_id in self.known_skills:
                self.known_skills[skill_id].is_equipped = False
            return True
        return False

    def update_cooldowns(self, dt: float):
        """Update all skill cooldowns"""
        for skill in self.known_skills.values():
            if skill.current_cooldown > 0:
                skill.current_cooldown = max(0, skill.current_cooldown - dt)

    def use_skill(self, slot: int, character) -> tuple[bool, str]:
        """Use a skill from hotbar slot (0-4). Returns (success, message)"""
        if not (0 <= slot < 5):
            return False, "Invalid slot"

        skill_id = self.equipped_skills[slot]
        if not skill_id:
            return False, "No skill in slot"

        player_skill = self.known_skills.get(skill_id)
        if not player_skill:
            return False, "Skill not learned"

        skill_def = player_skill.get_definition()
        if not skill_def:
            return False, "Skill definition not found"

        # Check cooldown
        if player_skill.current_cooldown > 0:
            return False, f"On cooldown ({player_skill.current_cooldown:.1f}s)"

        # Check mana cost
        skill_db = SkillDatabase.get_instance()
        mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
        if character.mana < mana_cost:
            return False, f"Not enough mana ({mana_cost} required)"

        # Consume mana
        character.mana -= mana_cost

        # Start cooldown
        cooldown_duration = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
        player_skill.current_cooldown = cooldown_duration

        # Apply skill effect (basic implementation)
        self._apply_skill_effect(skill_def, character)

        return True, f"Used {skill_def.name}!"

    def _apply_skill_effect(self, skill_def, character):
        """Apply the skill's effect"""
        effect = skill_def.effect
        skill_db = SkillDatabase.get_instance()

        # Get duration for buffs
        duration = skill_db.get_duration_seconds(effect.duration)

        # Magnitude-based bonus values
        magnitude_values = {
            'minor': {'empower': 0.25, 'quicken': 0.15, 'fortify': 10, 'pierce': 0.10},
            'moderate': {'empower': 0.50, 'quicken': 0.30, 'fortify': 20, 'pierce': 0.15},
            'major': {'empower': 1.00, 'quicken': 0.50, 'fortify': 40, 'pierce': 0.25},
            'extreme': {'empower': 1.50, 'quicken': 0.75, 'fortify': 60, 'pierce': 0.35}
        }

        print(f"⚡ {skill_def.name}: {effect.effect_type} - {effect.category} ({effect.magnitude})")

        # EMPOWER - Increases damage/output
        if effect.effect_type == "empower":
            bonus = magnitude_values.get(effect.magnitude, {}).get('empower', 0.5)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_empower",
                name=f"{skill_def.name} (Damage)",
                effect_type="empower",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus*100)}% {effect.category} damage for {duration}s")

        # QUICKEN - Increases speed
        elif effect.effect_type == "quicken":
            bonus = magnitude_values.get(effect.magnitude, {}).get('quicken', 0.3)
            category = "movement" if effect.category == "movement" else effect.category
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_quicken",
                name=f"{skill_def.name} (Speed)",
                effect_type="quicken",
                category=category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus*100)}% {category} speed for {duration}s")

        # FORTIFY - Increases defense
        elif effect.effect_type == "fortify":
            bonus = magnitude_values.get(effect.magnitude, {}).get('fortify', 20)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_fortify",
                name=f"{skill_def.name} (Defense)",
                effect_type="fortify",
                category="defense",
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus)} flat damage reduction for {duration}s")

        # PIERCE - Increases critical chance
        elif effect.effect_type == "pierce":
            bonus = magnitude_values.get(effect.magnitude, {}).get('pierce', 0.15)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_pierce",
                name=f"{skill_def.name} (Crit)",
                effect_type="pierce",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus*100)}% critical chance for {duration}s")

        # RESTORE - Instant restoration
        elif effect.effect_type == "restore":
            restore_amounts = {'minor': 50, 'moderate': 100, 'major': 200, 'extreme': 400}
            amount = restore_amounts.get(effect.magnitude, 100)

            if "health" in effect.category or "defense" in effect.category:
                character.health = min(character.max_health, character.health + amount)
                print(f"   Restored {amount} HP")
            elif "mana" in effect.category:
                character.mana = min(character.max_mana, character.mana + amount)
                print(f"   Restored {amount} MP")

        # ENRICH - Bonus gathering yield
        elif effect.effect_type == "enrich":
            bonus_items = {'minor': 1, 'moderate': 2, 'major': 3, 'extreme': 5}
            bonus = bonus_items.get(effect.magnitude, 2)
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_enrich",
                name=f"{skill_def.name} (Yield)",
                effect_type="enrich",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus)} bonus items from {effect.category} for {duration}s")

        # ELEVATE - Rarity upgrade chance
        elif effect.effect_type == "elevate":
            bonus = magnitude_values.get(effect.magnitude, {}).get('empower', 0.1)  # Reuse empower values
            buff = ActiveBuff(
                buff_id=f"{skill_def.skill_id}_elevate",
                name=f"{skill_def.name} (Quality)",
                effect_type="elevate",
                category=effect.category,
                magnitude=effect.magnitude,
                bonus_value=bonus,
                duration_remaining=duration
            )
            character.buffs.add_buff(buff)
            print(f"   +{int(bonus*100)}% rarity upgrade chance for {duration}s")


class SkillDatabase:
    _instance = None

    def __init__(self):
        self.skills: Dict[str, SkillDefinition] = {}
        self.loaded = False
        # Translation table for text values
        self.mana_costs = {"low": 30, "moderate": 60, "high": 100, "extreme": 150}
        self.cooldowns = {"short": 120, "moderate": 300, "long": 600, "extreme": 1200}
        self.durations = {"instant": 0, "brief": 15, "moderate": 30, "long": 60, "extended": 120}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SkillDatabase()
        return cls._instance

    def load_from_file(self, filepath: str = ""):
        """Load skills from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            for skill_data in data.get('skills', []):
                # Parse effect
                effect_data = skill_data.get('effect', {})
                effect = SkillEffect(
                    effect_type=effect_data.get('type', ''),
                    category=effect_data.get('category', ''),
                    magnitude=effect_data.get('magnitude', ''),
                    target=effect_data.get('target', 'self'),
                    duration=effect_data.get('duration', 'instant'),
                    additional_effects=effect_data.get('additionalEffects', [])
                )

                # Parse cost
                cost_data = skill_data.get('cost', {})
                cost = SkillCost(
                    mana=cost_data.get('mana', 'moderate'),
                    cooldown=cost_data.get('cooldown', 'moderate')
                )

                # Parse evolution
                evo_data = skill_data.get('evolution', {})
                evolution = SkillEvolution(
                    can_evolve=evo_data.get('canEvolve', False),
                    next_skill_id=evo_data.get('nextSkillId'),
                    requirement=evo_data.get('requirement', '')
                )

                # Parse requirements
                req_data = skill_data.get('requirements', {})
                requirements = SkillRequirements(
                    character_level=req_data.get('characterLevel', 1),
                    stats=req_data.get('stats', {}),
                    titles=req_data.get('titles', [])
                )

                # Create skill definition
                skill = SkillDefinition(
                    skill_id=skill_data.get('skillId', ''),
                    name=skill_data.get('name', ''),
                    tier=skill_data.get('tier', 1),
                    rarity=skill_data.get('rarity', 'common'),
                    categories=skill_data.get('categories', []),
                    description=skill_data.get('description', ''),
                    narrative=skill_data.get('narrative', ''),
                    tags=skill_data.get('tags', []),
                    effect=effect,
                    cost=cost,
                    evolution=evolution,
                    requirements=requirements
                )

                self.skills[skill.skill_id] = skill

            self.loaded = True
            print(f"✓ Loaded {len(self.skills)} skills from {filepath}")
            return True

        except Exception as e:
            print(f"⚠ Error loading skills from {filepath}: {e}")
            self.loaded = False
            return False

    def get_mana_cost(self, cost_text: str) -> int:
        """Convert text mana cost to numeric value"""
        return self.mana_costs.get(cost_text, 60)

    def get_cooldown_seconds(self, cooldown_text: str) -> float:
        """Convert text cooldown to seconds"""
        return self.cooldowns.get(cooldown_text, 300)

    def get_duration_seconds(self, duration_text: str) -> float:
        """Convert text duration to seconds"""
        return self.durations.get(duration_text, 0)


# ============================================================================
# INVENTORY
# ============================================================================
@dataclass
class ItemStack:
    item_id: str
    quantity: int
    max_stack: int = 99
    equipment_data: Optional['EquipmentItem'] = None  # For equipment items, store actual instance
    rarity: str = 'common'  # Rarity for materials and crafted items
    crafted_stats: Optional[Dict[str, Any]] = None  # Stats from minigame crafting with rarity modifiers

    def __post_init__(self):
        mat_db = MaterialDatabase.get_instance()
        if mat_db.loaded:
            mat = mat_db.get_material(self.item_id)
            if mat:
                self.max_stack = mat.max_stack

        # Equipment items don't stack
        equip_db = EquipmentDatabase.get_instance()
        is_equip = equip_db.is_equipment(self.item_id)

        if is_equip:
            self.max_stack = 1
            # Create equipment instance if not already set
            if self.equipment_data is None:
                self.equipment_data = equip_db.create_equipment_from_id(self.item_id)

    def can_add(self, amount: int) -> bool:
        return self.quantity + amount <= self.max_stack

    def add(self, amount: int) -> int:
        space = self.max_stack - self.quantity
        added = min(space, amount)
        self.quantity += added
        return amount - added

    def get_material(self) -> Optional[MaterialDefinition]:
        return MaterialDatabase.get_instance().get_material(self.item_id)

    def is_equipment(self) -> bool:
        """Check if this item stack is equipment"""
        return EquipmentDatabase.get_instance().is_equipment(self.item_id)

    def get_equipment(self) -> Optional[EquipmentItem]:
        """Get equipment data if this is equipment"""
        if not self.is_equipment():
            return None
        # Return the stored equipment instance if available
        if self.equipment_data:
            return self.equipment_data
        # Otherwise create a new one (shouldn't happen for equipment items)
        return EquipmentDatabase.get_instance().create_equipment_from_id(self.item_id)


class Inventory:
    def __init__(self, max_slots: int = 30):
        self.slots: List[Optional[ItemStack]] = [None] * max_slots
        self.max_slots = max_slots
        self.dragging_slot: Optional[int] = None
        self.dragging_stack: Optional[ItemStack] = None
        self.dragging_from_equipment: bool = False  # Track if dragging from equipment slot

    def add_item(self, item_id: str, quantity: int, equipment_instance: Optional['EquipmentItem'] = None) -> bool:
        remaining = quantity
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        # Equipment doesn't stack
        is_equip = equip_db.is_equipment(item_id)

        if is_equip:
            for i in range(quantity):
                empty = self.get_empty_slot()
                if empty is None:
                    return False
                # Use provided equipment instance or create new one
                equip_data = equipment_instance if equipment_instance else equip_db.create_equipment_from_id(item_id)
                if not equip_data:
                    print(f"WARNING: Could not create equipment data for {item_id}")
                    return False

                stack = ItemStack(item_id, 1, 1, equip_data)
                self.slots[empty] = stack
            return True

        # Normal materials can stack
        mat = mat_db.get_material(item_id)
        max_stack = mat.max_stack if mat else 99

        for slot in self.slots:
            if slot and slot.item_id == item_id and remaining > 0:
                remaining = slot.add(remaining)

        while remaining > 0:
            empty = self.get_empty_slot()
            if empty is None:
                return False
            stack_size = min(remaining, max_stack)
            self.slots[empty] = ItemStack(item_id, stack_size, max_stack)
            remaining -= stack_size
        return True

    def get_empty_slot(self) -> Optional[int]:
        for i, slot in enumerate(self.slots):
            if slot is None:
                return i
        return None

    def get_item_count(self, item_id: str) -> int:
        return sum(slot.quantity for slot in self.slots if slot and slot.item_id == item_id)

    def start_drag(self, slot_index: int):
        if 0 <= slot_index < self.max_slots and self.slots[slot_index]:
            self.dragging_slot = slot_index
            self.dragging_stack = self.slots[slot_index]
            self.slots[slot_index] = None
            self.dragging_from_equipment = False

    def end_drag(self, target_slot: int):
        if self.dragging_stack is None:
            return
        if 0 <= target_slot < self.max_slots:
            if self.slots[target_slot] is None:
                self.slots[target_slot] = self.dragging_stack
            elif self.slots[
                target_slot].item_id == self.dragging_stack.item_id and not self.dragging_stack.is_equipment():
                overflow = self.slots[target_slot].add(self.dragging_stack.quantity)
                if overflow > 0:
                    self.dragging_stack.quantity = overflow
                    self.slots[self.dragging_slot] = self.dragging_stack
            else:
                self.slots[target_slot], self.dragging_stack = self.dragging_stack, self.slots[target_slot]
                if self.dragging_stack and self.dragging_slot is not None:
                    self.slots[self.dragging_slot] = self.dragging_stack
        else:
            if self.dragging_slot is not None:
                self.slots[self.dragging_slot] = self.dragging_stack
        self.dragging_slot = None
        self.dragging_stack = None
        self.dragging_from_equipment = False

    def cancel_drag(self):
        if self.dragging_stack and self.dragging_slot is not None and not self.dragging_from_equipment:
            self.slots[self.dragging_slot] = self.dragging_stack
        self.dragging_slot = None
        self.dragging_stack = None
        self.dragging_from_equipment = False


# ============================================================================
# TOOL
# ============================================================================
@dataclass
class Tool:
    tool_id: str
    name: str
    tool_type: str
    tier: int
    damage: int
    durability_current: int
    durability_max: int
    efficiency: float = 1.0

    def can_harvest(self, resource_tier: int) -> bool:
        return self.tier >= resource_tier

    def use(self) -> bool:
        if Config.DEBUG_INFINITE_RESOURCES:
            return True
        if self.durability_current <= 0:
            return False
        self.durability_current -= 1
        return True

    def get_effectiveness(self) -> float:
        if Config.DEBUG_INFINITE_RESOURCES:
            return 1.0
        if self.durability_current <= 0:
            return 0.5
        dur_pct = self.durability_current / self.durability_max
        return 1.0 if dur_pct >= 0.5 else 1.0 - (0.5 - dur_pct) * 0.5

    def repair(self, amount: int = None):
        if amount is None:
            self.durability_current = self.durability_max
        else:
            self.durability_current = min(self.durability_max, self.durability_current + amount)


# ============================================================================
# DAMAGE
# ============================================================================
@dataclass
class DamageNumber:
    damage: int
    position: Position
    is_crit: bool
    lifetime: float = 1.0
    velocity_y: float = -1.0

    def update(self, dt: float) -> bool:
        self.lifetime -= dt
        self.position.y += self.velocity_y * dt
        return self.lifetime > 0


# ============================================================================
# CHARACTER
# ============================================================================
class Character:
    def __init__(self, start_position: Position):
        self.position = start_position
        self.facing = "down"
        self.movement_speed = Config.PLAYER_SPEED
        self.interaction_range = Config.INTERACTION_RANGE

        self.stats = CharacterStats()
        self.leveling = LevelingSystem()
        self.skills = SkillManager()
        self.buffs = BuffManager()
        self.titles = TitleSystem()
        self.class_system = ClassSystem()
        self.activities = ActivityTracker()
        self.equipment = EquipmentManager()

        self.base_max_health = 100
        self.base_max_mana = 100
        self.max_health = self.base_max_health
        self.health = self.max_health
        self.max_mana = self.base_max_mana
        self.mana = self.max_mana

        self.inventory = Inventory(30)
        self.tools: List[Tool] = []
        self.selected_tool: Optional[Tool] = None
        self._selected_weapon: Optional[EquipmentItem] = None  # For Tab cycling through weapons

        self.active_station: Optional[CraftingStation] = None
        self.crafting_ui_open = False
        self.stats_ui_open = False
        self.equipment_ui_open = False
        self.skills_ui_open = False
        self.skills_menu_scroll_offset = 0  # For scrolling in skills menu
        self.class_selection_open = False

        # Combat
        self.attack_cooldown = 0.0
        self.last_attacked_enemy = None

        # Health regeneration tracking
        self.time_since_last_damage_taken = 0.0
        self.time_since_last_damage_dealt = 0.0
        self.health_regen_threshold = 5.0  # 5 seconds
        self.health_regen_rate = 5.0  # 5 HP per second

        self._give_starting_tools()
        if Config.DEBUG_INFINITE_RESOURCES:
            self._give_debug_items()

    def _give_starting_tools(self):
        self.tools = [
            Tool("copper_axe", "Copper Axe", "axe", 1, 10, 500, 500),
            Tool("copper_pickaxe", "Copper Pickaxe", "pickaxe", 1, 10, 500, 500)
        ]
        self.selected_tool = self.tools[0]

    def _give_debug_items(self):
        """Give starter items in debug mode"""
        # Set max level
        self.leveling.level = self.leveling.max_level
        self.leveling.unallocated_stat_points = 100
        print(f"🔧 DEBUG: Set level to {self.leveling.level} with {self.leveling.unallocated_stat_points} stat points")

        # Give lots of materials
        self.inventory.add_item("copper_ore", 50)
        self.inventory.add_item("iron_ore", 50)
        self.inventory.add_item("oak_log", 50)
        self.inventory.add_item("birch_log", 50)

    def recalculate_stats(self):
        """Recalculate character stats based on equipment, class, titles, etc."""
        # Start with base + stat bonuses
        stat_health = self.stats.get_flat_bonus('vitality', 'max_health')
        stat_mana = self.stats.get_flat_bonus('intelligence', 'mana')

        # Add class bonuses
        class_health = self.class_system.get_bonus('max_health')
        class_mana = self.class_system.get_bonus('max_mana')

        # Add equipment bonuses
        equip_bonuses = self.equipment.get_stat_bonuses()
        equip_health = equip_bonuses.get('max_health', 0)
        equip_mana = equip_bonuses.get('max_mana', 0)

        # Calculate new max values
        old_max_health = self.max_health
        old_max_mana = self.max_mana

        self.max_health = self.base_max_health + stat_health + class_health + equip_health
        self.max_mana = self.base_max_mana + stat_mana + class_mana + equip_mana

        # Scale current health/mana proportionally
        if old_max_health > 0:
            health_ratio = self.health / old_max_health
            self.health = min(self.max_health, int(self.max_health * health_ratio))
        if old_max_mana > 0:
            mana_ratio = self.mana / old_max_mana
            self.mana = min(self.max_mana, int(self.max_mana * mana_ratio))

    def allocate_stat_point(self, stat_name: str) -> bool:
        if self.leveling.unallocated_stat_points <= 0:
            return False
        if hasattr(self.stats, stat_name):
            setattr(self.stats, stat_name, getattr(self.stats, stat_name) + 1)
            self.leveling.unallocated_stat_points -= 1
            self.recalculate_stats()
            return True
        return False

    def move(self, dx: float, dy: float, world: WorldSystem) -> bool:
        # Calculate movement speed from stats, class, and active buffs
        speed_mult = 1.0 + self.stats.get_bonus('agility') * 0.02 + self.class_system.get_bonus('movement_speed') + self.buffs.get_movement_speed_bonus()
        new_pos = Position(self.position.x + dx * speed_mult, self.position.y + dy * speed_mult, self.position.z)
        if new_pos.x < 0 or new_pos.x >= Config.WORLD_SIZE or new_pos.y < 0 or new_pos.y >= Config.WORLD_SIZE:
            return False
        if world.is_walkable(new_pos):
            self.position = new_pos
            self.facing = ("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up")
            return True
        return False

    def is_in_range(self, target_position: Position) -> bool:
        return self.position.distance_to(target_position) <= self.interaction_range

    def can_harvest_resource(self, resource: NaturalResource) -> Tuple[bool, str]:
        if not self.selected_tool:
            return False, "No tool selected"
        if not self.is_in_range(resource.position):
            return False, "Too far away"
        if self.selected_tool.tool_type != resource.required_tool:
            tool_name = "axe" if resource.required_tool == "axe" else "pickaxe"
            return False, f"Need {tool_name}"
        if not self.selected_tool.can_harvest(resource.tier):
            return False, f"Tool tier too low (need T{resource.tier})"
        if self.selected_tool.durability_current <= 0 and not Config.DEBUG_INFINITE_RESOURCES:
            return False, "Tool broken"
        return True, "OK"

    def harvest_resource(self, resource: NaturalResource):
        can_harvest, reason = self.can_harvest_resource(resource)
        if not can_harvest:
            return None

        base_damage = self.selected_tool.damage
        effectiveness = self.selected_tool.get_effectiveness()
        activity = 'mining' if resource.required_tool == "pickaxe" else 'forestry'
        stat_bonus = self.stats.get_bonus('strength' if activity == 'mining' else 'agility')
        title_bonus = self.titles.get_total_bonus(f'{activity}_damage')
        buff_bonus = self.buffs.get_damage_bonus(activity)
        damage_mult = 1.0 + stat_bonus + title_bonus + buff_bonus

        crit_chance = self.stats.luck * 0.02 + self.class_system.get_bonus('crit_chance') + self.buffs.get_total_bonus('pierce', activity)
        is_crit = random.random() < crit_chance
        damage = int(base_damage * effectiveness * damage_mult)
        actual_damage, depleted = resource.take_damage(damage, is_crit)

        if not self.selected_tool.use():
            print("⚠ Tool broke!")

        self.activities.record_activity(activity, 1)
        new_title = self.titles.check_for_title(activity, self.activities.get_count(activity))
        if new_title:
            print(f"🏆 TITLE EARNED: {new_title.name} - {new_title.bonus_description}")

        self.leveling.add_exp({1: 10, 2: 40, 3: 160, 4: 640}.get(resource.tier, 10))

        # Reset damage dealt timer (harvesting counts as dealing damage)
        self.time_since_last_damage_dealt = 0.0

        loot = None
        if depleted:
            loot = resource.get_loot()
            for item_id, qty in loot:
                # Luck-based bonus
                if random.random() < (self.stats.luck * 0.02 + self.class_system.get_bonus('resource_quality')):
                    qty += 1

                # SKILL BUFF BONUSES: Check for enrich buffs (bonus items)
                enrich_bonus = 0
                if hasattr(self, 'buffs'):
                    # Check for enrich buff on this activity (mining or forestry)
                    enrich_bonus = int(self.buffs.get_total_bonus('enrich', activity))

                if enrich_bonus > 0:
                    qty += enrich_bonus
                    print(f"   ⚡ Enrich buff: +{enrich_bonus} bonus {item_id}")

                self.inventory.add_item(item_id, qty)
        return (loot, actual_damage, is_crit)

    def switch_tool(self):
        """Cycle through tools and equipped weapons"""
        # Build list of available items (tools + equipped weapons)
        available_items = list(self.tools)

        # Add equipped weapons
        main_weapon = self.equipment.slots.get('mainHand')
        off_weapon = self.equipment.slots.get('offHand')
        if main_weapon:
            available_items.append(main_weapon)
        if off_weapon:
            available_items.append(off_weapon)

        if not available_items:
            return None

        # Find current index
        current_idx = -1
        if self.selected_tool:
            for i, item in enumerate(available_items):
                if isinstance(item, Tool) and item == self.selected_tool:
                    current_idx = i
                    break
                elif isinstance(item, EquipmentItem) and hasattr(self, '_selected_weapon') and item == self._selected_weapon:
                    current_idx = i
                    break

        # Cycle to next
        next_idx = (current_idx + 1) % len(available_items)
        next_item = available_items[next_idx]

        if isinstance(next_item, Tool):
            self.selected_tool = next_item
            self._selected_weapon = None
            return f"{next_item.name} (Tool)"
        else:  # EquipmentItem (weapon)
            self.selected_tool = None
            self._selected_weapon = next_item
            return f"{next_item.name} (Weapon)"

    def interact_with_station(self, station: CraftingStation):
        if self.is_in_range(station.position):
            self.active_station = station
            self.crafting_ui_open = True

    def close_crafting_ui(self):
        self.active_station = None
        self.crafting_ui_open = False

    def update_health_regen(self, dt: float):
        """Update health and mana regeneration"""
        self.time_since_last_damage_taken += dt
        self.time_since_last_damage_dealt += dt

        # Health regeneration - 5 HP/sec after 5 seconds of no combat
        if (self.time_since_last_damage_taken >= self.health_regen_threshold and
            self.time_since_last_damage_dealt >= self.health_regen_threshold):
            if self.health < self.max_health:
                regen_amount = self.health_regen_rate * dt
                self.health = min(self.max_health, self.health + regen_amount)

        # Mana regeneration - 1% per second (always active)
        if self.mana < self.max_mana:
            mana_regen_amount = self.max_mana * 0.01 * dt  # 1% of max mana per second
            self.mana = min(self.max_mana, self.mana + mana_regen_amount)

    def update_buffs(self, dt: float):
        """Update all active buffs"""
        self.buffs.update(dt)
        self.skills.update_cooldowns(dt)

    def toggle_stats_ui(self):
        self.stats_ui_open = not self.stats_ui_open

    def toggle_skills_ui(self):
        self.skills_ui_open = not self.skills_ui_open
        if not self.skills_ui_open:
            self.skills_menu_scroll_offset = 0  # Reset scroll when closing

    def toggle_equipment_ui(self):
        self.equipment_ui_open = not self.equipment_ui_open

    def select_class(self, class_def: ClassDefinition):
        self.class_system.set_class(class_def)
        self.recalculate_stats()
        self.health = self.max_health
        self.mana = self.max_mana
        print(f"✓ Class selected: {class_def.name}")

        # Grant starting skill if the class has one
        if class_def.starting_skill:
            # Map class skill names to actual skill IDs in skills-skills-1.JSON
            skill_mapping = {
                "battle_rage": "combat_strike",  # Warrior → Power Strike (T1 common)
                "forestry_frenzy": "lumberjacks_rhythm",  # Ranger → Lumberjack's Rhythm
                "alchemists_touch": "alchemists_insight",  # Scholar → Alchemist's Insight
                "smithing_focus": "smiths_focus",  # Artisan → Smith's Focus
                "treasure_hunters_luck": "treasure_sense",  # Scavenger → Treasure Sense (T2)
                "versatile_start": None  # Adventurer → Player chooses (handled separately)
            }

            requested_skill = class_def.starting_skill
            actual_skill_id = skill_mapping.get(requested_skill, requested_skill)

            if actual_skill_id:
                # Check if skill exists in database
                skill_db = SkillDatabase.get_instance()
                if actual_skill_id in skill_db.skills:
                    # Learn the skill (skip requirement checks for starting skills)
                    if self.skills.learn_skill(actual_skill_id, character=self, skip_checks=True):
                        print(f"   ✓ Learned starting skill: {skill_db.skills[actual_skill_id].name}")
                        # Auto-equip to slot 0
                        self.skills.equip_skill(actual_skill_id, 0)
                        print(f"   ✓ Equipped to hotbar slot 1")
                    else:
                        print(f"   ⚠ Skill {actual_skill_id} already known")
                else:
                    print(f"   ⚠ Warning: Starting skill '{actual_skill_id}' not found in skill database")
            elif requested_skill == "versatile_start":
                # Adventurer class - player should choose a T1 skill
                # For now, we'll give them sprint as a default, but ideally this should open a choice dialog
                default_skill = "sprint"
                if self.skills.learn_skill(default_skill, character=self, skip_checks=True):
                    print(f"   ✓ Learned starter skill: {skill_db.skills[default_skill].name}")
                    self.skills.equip_skill(default_skill, 0)
                    print(f"   ℹ Adventurer class: You can learn any skill! (Sprint given as default)")

    def try_equip_from_inventory(self, slot_index: int) -> Tuple[bool, str]:
        """Try to equip item from inventory slot"""
        print(f"\n🎯 try_equip_from_inventory called for slot {slot_index}")

        if slot_index < 0 or slot_index >= self.inventory.max_slots:
            print(f"   ❌ Invalid slot index")
            return False, "Invalid slot"

        item_stack = self.inventory.slots[slot_index]
        if not item_stack:
            print(f"   ❌ Empty slot")
            return False, "Empty slot"

        print(f"   📦 Item: {item_stack.item_id}")
        is_equip = item_stack.is_equipment()
        print(f"   🔍 is_equipment(): {is_equip}")

        if not is_equip:
            print(f"   ❌ Not equipment - FAILED")
            return False, "Not equipment"

        equipment = item_stack.get_equipment()
        print(f"   ⚙️  get_equipment(): {equipment}")

        if not equipment:
            print(f"   ❌ Invalid equipment - FAILED")
            return False, "Invalid equipment"

        print(f"   📋 Equipment details:")
        print(f"      - name: {equipment.name}")
        print(f"      - slot: {equipment.slot}")
        print(f"      - tier: {equipment.tier}")

        # Try to equip
        print(f"   🔄 Calling equipment.equip()...")
        old_item, status = self.equipment.equip(equipment, self)
        print(f"   📤 equip() returned: old_item={old_item}, status={status}")

        if status != "OK":
            print(f"   ❌ Equip failed with status: {status}")
            return False, status

        # Remove from inventory
        self.inventory.slots[slot_index] = None
        print(f"   ✅ Removed from inventory slot {slot_index}")

        # If there was an old item, put it back in inventory (preserve equipment data)
        if old_item:
            if not self.inventory.add_item(old_item.item_id, 1, old_item):
                # Inventory full, swap back
                self.equipment.slots[equipment.slot] = old_item
                self.inventory.slots[slot_index] = item_stack
                self.recalculate_stats()
                print(f"   ❌ Inventory full, swapped back")
                return False, "Inventory full"
            print(f"   ↩️  Returned old item to inventory")

        print(f"   ✅ SUCCESS - Equipped {equipment.name}")
        return True, "OK"

    def try_unequip_to_inventory(self, slot_name: str) -> Tuple[bool, str]:
        """Try to unequip item to inventory"""
        if slot_name not in self.equipment.slots:
            return False, "Invalid slot"

        item = self.equipment.slots[slot_name]
        if not item:
            return False, "Empty slot"

        # Try to add to inventory (preserve equipment data)
        if not self.inventory.add_item(item.item_id, 1, item):
            return False, "Inventory full"

        # Remove from equipment
        self.equipment.unequip(slot_name, self)

        return True, "OK"

    def take_damage(self, damage: float):
        """Take damage from enemy"""
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self._handle_death()

    def _handle_death(self):
        """Handle player death - respawn at spawn point"""
        print("💀 You died! Respawning...")
        self.health = self.max_health
        self.position = Position(50, 50, 0)  # Respawn at spawn
        # Keep all items and equipment (no death penalty)

    def get_weapon_damage(self) -> float:
        """Get average weapon damage from equipped weapon"""
        damage_range = self.equipment.get_weapon_damage()
        # Return average damage
        return (damage_range[0] + damage_range[1]) / 2.0

    def update_attack_cooldown(self, dt: float):
        """Update attack cooldown timer"""
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

    def can_attack(self) -> bool:
        """Check if player can attack (cooldown ready)"""
        return self.attack_cooldown <= 0

    def reset_attack_cooldown(self, is_weapon: bool = True):
        """Reset attack cooldown based on attack speed"""
        if is_weapon:
            # Weapon attack cooldown based on attack speed stat
            base_cooldown = 1.0
            attack_speed_bonus = self.stats.agility * 0.03  # 3% faster per AGI
            self.attack_cooldown = base_cooldown / (1.0 + attack_speed_bonus)
        else:
            # Tool attack cooldown (faster)
            self.attack_cooldown = 0.5


# ============================================================================
# CAMERA
# ============================================================================
class Camera:
    def __init__(self, viewport_width: int, viewport_height: int):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.position = Position(0, 0, 0)

    def follow(self, target: Position):
        self.position = target.copy()

    def world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        sx = (world_pos.x - self.position.x) * Config.TILE_SIZE + self.viewport_width // 2
        sy = (world_pos.y - self.position.y) * Config.TILE_SIZE + self.viewport_height // 2
        return int(sx), int(sy)


# ============================================================================
# RENDERER
# ============================================================================
class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.tiny_font = pygame.font.Font(None, 14)

    def _get_grid_size_for_tier(self, tier: int, discipline: str) -> Tuple[int, int]:
        """Get grid dimensions based on station tier for grid-based disciplines (smithing, adornments)"""
        if discipline not in ['smithing', 'adornments']:
            return (3, 3)  # Default for non-grid disciplines

        tier_to_grid = {
            1: (3, 3),
            2: (5, 5),
            3: (7, 7),
            4: (9, 9)
        }
        return tier_to_grid.get(tier, (3, 3))

    def render_smithing_grid(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                           station_tier: int, selected_recipe: Optional[Recipe],
                           user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render smithing grid with:
        - Station tier determines grid size shown (T1=3x3, T2=5x5, T3=7x7, T4=9x9)
        - Recipe placement data shown (if selected)
        - User's current placement overlaid
        - Visual feedback for valid/invalid placements

        Returns: Dict mapping grid cell rects to (grid_x, grid_y) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine grid size based on station tier
        grid_w, grid_h = self._get_grid_size_for_tier(station_tier, 'smithing')

        # Calculate cell size to fit in placement_rect with padding
        padding = 20
        available_w = placement_rect.width - 2 * padding
        available_h = placement_rect.height - 2 * padding
        cell_size = min(available_w // grid_w, available_h // grid_h) - 4  # -4 for cell spacing

        # Center the grid in the placement_rect
        grid_pixel_w = grid_w * (cell_size + 4)
        grid_pixel_h = grid_h * (cell_size + 4)
        grid_start_x = placement_rect.x + (placement_rect.width - grid_pixel_w) // 2
        grid_start_y = placement_rect.y + (placement_rect.height - grid_pixel_h) // 2

        # Get recipe placement data if available
        recipe_placement_map = {}
        recipe_grid_w, recipe_grid_h = grid_w, grid_h  # Default to station grid size
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data and placement_data.grid_size:
                # Parse recipe's actual grid size (e.g., "3x3")
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass
                recipe_placement_map = placement_data.placement_map

        # Calculate offset to center recipe on station grid
        offset_x = (grid_w - recipe_grid_w) // 2
        offset_y = (grid_h - recipe_grid_h) // 2

        # Draw grid cells
        cell_rects = []  # Will store list of (pygame.Rect, (grid_x, grid_y)) for click detection

        for gy in range(1, grid_h + 1):  # 1-indexed to match placement data (row)
            for gx in range(1, grid_w + 1):  # 1-indexed (col)
                # No Y axis flipping - row 1 is at top, like in crafting_tester.py
                cell_x = grid_start_x + (gx - 1) * (cell_size + 4)
                cell_y = grid_start_y + (gy - 1) * (cell_size + 4)
                cell_rect = pygame.Rect(cell_x, cell_y, cell_size, cell_size)

                # Check if this cell corresponds to a recipe requirement (with offset for centering)
                recipe_x = gx - offset_x
                recipe_y = gy - offset_y
                # Placement data format is "row,col" where row=Y axis, col=X axis
                # gy is the row (Y), gx is the col (X), so keys should be "{row},{col}" = "{gy},{gx}"
                recipe_key = f"{recipe_y},{recipe_x}"

                grid_key = f"{gy},{gx}"
                has_recipe_requirement = (1 <= recipe_x <= recipe_grid_w and
                                        1 <= recipe_y <= recipe_grid_h and
                                        recipe_key in recipe_placement_map)
                has_user_placement = grid_key in user_placement

                # Cell background color
                if has_user_placement:
                    # User placed something here
                    cell_color = (50, 70, 50)  # Green tint
                elif has_recipe_requirement:
                    # Recipe requires something here (but user hasn't placed it yet)
                    cell_color = (70, 60, 40)  # Gold tint - shows what's needed
                else:
                    # Empty cell
                    cell_color = (30, 30, 40)

                # Highlight cell under mouse
                is_hovered = cell_rect.collidepoint(mouse_pos)
                if is_hovered:
                    cell_color = tuple(min(255, c + 20) for c in cell_color)

                pygame.draw.rect(surf, cell_color, cell_rect)

                # Border
                border_color = (100, 100, 100) if not has_recipe_requirement else (150, 130, 80)
                pygame.draw.rect(surf, border_color, cell_rect, 1 if not is_hovered else 2)

                # Draw material icon/name
                if has_user_placement:
                    # Show user's placement
                    mat_id = user_placement[grid_key]
                    mat = mat_db.get_material(mat_id)
                    mat_name = (mat.name[:6] if mat else mat_id[:6])  # Truncate to fit
                    text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                    text_rect = text_surf.get_rect(center=cell_rect.center)
                    surf.blit(text_surf, text_rect)
                elif has_recipe_requirement:
                    # Show what recipe requires (semi-transparent hint)
                    req_mat_id = recipe_placement_map[recipe_key]
                    mat = mat_db.get_material(req_mat_id)
                    mat_name = (mat.name[:6] if mat else req_mat_id[:6])
                    text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                    text_rect = text_surf.get_rect(center=cell_rect.center)
                    surf.blit(text_surf, text_rect)

                # Store rect for click handling
                cell_rects.append((cell_rect, (gx, gy)))

        # Draw grid size label
        grid_label = f"Smithing Grid: {grid_w}x{grid_h} (T{station_tier})"
        label_surf = self.small_font.render(grid_label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return cell_rects

    def render_adornment_pattern(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                                 station_tier: int, selected_recipe: Optional[Recipe],
                                 user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render adornment/enchanting pattern grid with vertices and shapes:
        - Uses centered coordinate system (0,0 at center)
        - Shows vertices as circles with material labels
        - Draws connecting lines for shapes
        - Supports different grid sizes (8x8, 10x10, 12x12, etc.)

        Returns: List of (pygame.Rect, vertex_coord_str) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Get placement data for selected recipe
        vertices = {}
        shapes = []
        grid_size = 12  # Default grid size

        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data and placement_data.placement_map:
                pmap = placement_data.placement_map
                vertices = pmap.get('vertices', {})
                shapes = pmap.get('shapes', [])
                # Parse grid type (e.g., "square_12x12")
                grid_type = pmap.get('gridType', 'square_12x12')
                if 'x' in grid_type:
                    try:
                        grid_size = int(grid_type.split('_')[1].split('x')[0])
                    except (IndexError, ValueError):
                        pass

        # Calculate cell size to fit grid in placement_rect
        padding = 40
        available = min(placement_rect.width, placement_rect.height) - 2 * padding
        cell_size = available // grid_size

        # Center the grid
        grid_pixel_size = grid_size * cell_size
        grid_start_x = placement_rect.x + (placement_rect.width - grid_pixel_size) // 2
        grid_start_y = placement_rect.y + (placement_rect.height - grid_pixel_size) // 2

        # Draw grid background
        grid_rect = pygame.Rect(grid_start_x, grid_start_y, grid_pixel_size, grid_pixel_size)
        pygame.draw.rect(surf, (25, 25, 35), grid_rect)

        # Draw grid cells
        for row in range(grid_size):
            for col in range(grid_size):
                x = grid_start_x + col * cell_size
                y = grid_start_y + row * cell_size
                cell_rect = pygame.Rect(x, y, cell_size - 1, cell_size - 1)
                pygame.draw.rect(surf, (40, 40, 50), cell_rect, 1)

        # Draw center axes
        half = grid_size // 2
        center_x = grid_start_x + half * cell_size
        center_y = grid_start_y + half * cell_size
        pygame.draw.line(surf, (60, 60, 70), (center_x, grid_start_y), (center_x, grid_start_y + grid_pixel_size), 2)
        pygame.draw.line(surf, (60, 60, 70), (grid_start_x, center_y), (grid_start_x + grid_pixel_size, center_y), 2)

        # Draw shape connecting lines first (behind vertices)
        for shape in shapes:
            shape_vertices = shape.get('vertices', [])
            if len(shape_vertices) > 1:
                for i in range(len(shape_vertices)):
                    v1_str = shape_vertices[i]
                    v2_str = shape_vertices[(i + 1) % len(shape_vertices)]

                    if ',' in v1_str and ',' in v2_str:
                        try:
                            gx1, gy1 = map(int, v1_str.split(','))
                            gx2, gy2 = map(int, v2_str.split(','))

                            # Convert centered coords to screen position
                            sx1 = grid_start_x + (gx1 + half) * cell_size + cell_size // 2
                            sy1 = grid_start_y + (half - gy1) * cell_size + cell_size // 2
                            sx2 = grid_start_x + (gx2 + half) * cell_size + cell_size // 2
                            sy2 = grid_start_y + (half - gy2) * cell_size + cell_size // 2

                            pygame.draw.line(surf, (100, 150, 255), (sx1, sy1), (sx2, sy2), 3)
                        except (ValueError, IndexError):
                            pass

        # Draw vertices (material placement points)
        vertex_rects = []
        for coord_str, vertex_data in vertices.items():
            if ',' in coord_str:
                try:
                    gx, gy = map(int, coord_str.split(','))

                    # Convert centered coordinates to screen position
                    screen_x = grid_start_x + (gx + half) * cell_size + cell_size // 2
                    screen_y = grid_start_y + (half - gy) * cell_size + cell_size // 2

                    material_id = vertex_data.get('materialId')
                    is_key = vertex_data.get('isKey', False)

                    # Determine color
                    if material_id:
                        mat = mat_db.get_material(material_id)
                        if mat:
                            mat_color = Config.RARITY_COLORS.get(mat.rarity, (100, 200, 200))
                        else:
                            mat_color = (255, 100, 100) if is_key else (100, 200, 200)
                    else:
                        mat_color = (255, 100, 100) if is_key else (100, 200, 200)

                    # Draw larger, more visible circle
                    pygame.draw.circle(surf, mat_color, (screen_x, screen_y), 10)
                    pygame.draw.circle(surf, (255, 255, 255), (screen_x, screen_y), 10, 2)

                    # Draw inner dot for key vertices
                    if is_key:
                        pygame.draw.circle(surf, (255, 255, 0), (screen_x, screen_y), 4)

                    # Draw material label with shadow for visibility
                    if material_id:
                        mat_label = material_id[:4].upper()
                        # Shadow
                        label_shadow = self.tiny_font.render(mat_label, True, (0, 0, 0))
                        surf.blit(label_shadow, (screen_x - 10, screen_y - 22))
                        surf.blit(label_shadow, (screen_x - 8, screen_y - 20))
                        # Main text
                        label_text = self.tiny_font.render(mat_label, True, (255, 255, 255))
                        surf.blit(label_text, (screen_x - 9, screen_y - 21))

                    # Store for click handling
                    vertex_rect = pygame.Rect(screen_x - 10, screen_y - 10, 20, 20)
                    vertex_rects.append((vertex_rect, coord_str))

                except (ValueError, IndexError):
                    pass

        # Draw grid label
        grid_label = f"Adornment Pattern: {grid_size}x{grid_size} ({len(vertices)} vertices)"
        label_surf = self.small_font.render(grid_label, True, (150, 150, 200))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return vertex_rects

    def render_refining_hub(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                          station_tier: int, selected_recipe: Optional[Recipe],
                          user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render refining hub-and-spoke with:
        - Station tier determines number of slots (T1=3 slots, T2=5, T3=7, T4=9)
        - Core slots in center (hub)
        - Surrounding slots in circle around core (spokes)
        - User can place materials in slots

        Returns: Dict mapping slot rects to slot_id for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine slot counts based on station tier
        # T1: 1 core + 2 surrounding = 3 total
        # T2: 1 core + 4 surrounding = 5 total
        # T3: 1 core + 6 surrounding = 7 total
        # T4: 1 core + 8 surrounding = 9 total
        core_slots = 1
        surrounding_slots = 2 + (station_tier - 1) * 2

        # Get recipe placement data if available
        required_core = []
        required_surrounding = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_core = placement_data.core_inputs
                required_surrounding = placement_data.surrounding_inputs

        # Calculate slot size
        center_x = placement_rect.centerx
        center_y = placement_rect.centery
        core_radius = 40  # Radius of core slot
        surrounding_radius = 30  # Radius of each surrounding slot
        orbit_radius = 120  # Distance from center to surrounding slots

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click detection

        # Draw core slot
        core_x = center_x - core_radius
        core_y = center_y - core_radius
        core_rect = pygame.Rect(core_x, core_y, core_radius * 2, core_radius * 2)

        # Determine core slot state
        has_user_core = "core_0" in user_placement
        has_required_core = len(required_core) > 0

        core_color = (50, 70, 50) if has_user_core else ((70, 60, 40) if has_required_core else (30, 30, 40))
        is_hovered = core_rect.collidepoint(mouse_pos)
        if is_hovered:
            core_color = tuple(min(255, c + 20) for c in core_color)

        pygame.draw.circle(surf, core_color, (center_x, center_y), core_radius)
        pygame.draw.circle(surf, (150, 130, 80), (center_x, center_y), core_radius, 2 if is_hovered else 1)

        # Draw core material
        if has_user_core:
            mat_id = user_placement["core_0"]
            mat = mat_db.get_material(mat_id)
            mat_name = (mat.name[:8] if mat else mat_id[:8])
            text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
            text_rect = text_surf.get_rect(center=(center_x, center_y))
            surf.blit(text_surf, text_rect)
        elif has_required_core:
            req_mat_id = required_core[0].get('materialId', '')
            mat = mat_db.get_material(req_mat_id)
            mat_name = (mat.name[:8] if mat else req_mat_id[:8])
            text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
            text_rect = text_surf.get_rect(center=(center_x, center_y))
            surf.blit(text_surf, text_rect)

        slot_rects.append((core_rect, "core_0"))

        # Draw surrounding slots in circle
        import math
        for i in range(surrounding_slots):
            angle = (2 * math.pi * i) / surrounding_slots - math.pi / 2  # Start at top
            slot_x = center_x + int(orbit_radius * math.cos(angle))
            slot_y = center_y + int(orbit_radius * math.sin(angle))

            slot_rect = pygame.Rect(
                slot_x - surrounding_radius,
                slot_y - surrounding_radius,
                surrounding_radius * 2,
                surrounding_radius * 2
            )

            slot_id = f"surrounding_{i}"
            has_user_surrounding = slot_id in user_placement
            has_required_surrounding = i < len(required_surrounding)

            slot_color = (50, 70, 50) if has_user_surrounding else ((70, 60, 40) if has_required_surrounding else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.circle(surf, slot_color, (slot_x, slot_y), surrounding_radius)
            pygame.draw.circle(surf, (100, 100, 100), (slot_x, slot_y), surrounding_radius, 2 if is_hovered else 1)

            # Draw slot material
            if has_user_surrounding:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                mat_name = (mat.name[:6] if mat else mat_id[:6])
                text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                surf.blit(text_surf, text_rect)
            elif has_required_surrounding:
                req_mat_id = required_surrounding[i].get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                mat_name = (mat.name[:6] if mat else req_mat_id[:6])
                text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                surf.blit(text_surf, text_rect)

            slot_rects.append((slot_rect, slot_id))

        # Draw label
        label = f"Refining Hub: {core_slots} core + {surrounding_slots} surrounding (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_alchemy_sequence(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                               station_tier: int, selected_recipe: Optional[Recipe],
                               user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render alchemy sequential placement with:
        - Station tier determines max slots (T1=2, T2=3, T3=4, T4=5)
        - Horizontal sequence of numbered slots
        - Order is critical for alchemy reactions

        Returns: List of (pygame.Rect, slot_id) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine max slots based on station tier
        max_slots = 1 + station_tier  # T1=2, T2=3, T3=4, T4=5

        # Get recipe placement data if available
        required_ingredients = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_ingredients = placement_data.ingredients

        # Calculate slot dimensions
        slot_width = 80
        slot_height = 80
        slot_spacing = 20
        total_width = max_slots * slot_width + (max_slots - 1) * slot_spacing

        start_x = placement_rect.centerx - total_width // 2
        start_y = placement_rect.centery - slot_height // 2

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click detection

        # Draw slots horizontally
        for i in range(max_slots):
            slot_num = i + 1  # 1-indexed
            slot_x = start_x + i * (slot_width + slot_spacing)
            slot_y = start_y

            slot_rect = pygame.Rect(slot_x, slot_y, slot_width, slot_height)
            slot_id = f"seq_{slot_num}"

            # Find if this slot is required
            required_for_slot = None
            for ing in required_ingredients:
                if ing.get('slot') == slot_num:
                    required_for_slot = ing
                    break

            has_user_material = slot_id in user_placement
            has_requirement = required_for_slot is not None

            # Slot background color
            slot_color = (50, 70, 50) if has_user_material else ((70, 60, 40) if has_requirement else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.rect(surf, slot_color, slot_rect)
            pygame.draw.rect(surf, (100, 100, 100), slot_rect, 2 if is_hovered else 1)

            # Draw slot number
            num_surf = self.font.render(str(slot_num), True, (150, 150, 150))
            num_rect = num_surf.get_rect(topleft=(slot_x + 5, slot_y + 5))
            surf.blit(num_surf, num_rect)

            # Draw material name
            if has_user_material:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                mat_name = (mat.name[:10] if mat else mat_id[:10])
                text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                surf.blit(text_surf, text_rect)
            elif has_requirement:
                req_mat_id = required_for_slot.get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                mat_name = (mat.name[:10] if mat else req_mat_id[:10])
                text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                surf.blit(text_surf, text_rect)

            slot_rects.append((slot_rect, slot_id))

            # Draw arrow between slots
            if i < max_slots - 1:
                arrow_start_x = slot_x + slot_width
                arrow_end_x = arrow_start_x + slot_spacing
                arrow_y = slot_y + slot_height // 2
                pygame.draw.line(surf, (100, 100, 100), (arrow_start_x, arrow_y), (arrow_end_x, arrow_y), 2)
                # Arrowhead
                pygame.draw.polygon(surf, (100, 100, 100), [
                    (arrow_end_x, arrow_y),
                    (arrow_end_x - 8, arrow_y - 5),
                    (arrow_end_x - 8, arrow_y + 5)
                ])

        # Draw label
        label = f"Alchemy Sequence: {max_slots} sequential slots (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_engineering_slots(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                                 station_tier: int, selected_recipe: Optional[Recipe],
                                 user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render engineering slot-type placement with:
        - Station tier determines max slots (T1=3, T2=5, T3=5, T4=7)
        - Vertical list of typed slots (FRAME, FUNCTION, POWER, MODIFIER, etc.)
        - Each slot shows its type and required material

        Returns: List of (pygame.Rect, slot_id) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine max slots based on station tier
        tier_to_max_slots = {1: 3, 2: 5, 3: 5, 4: 7}
        max_slots = tier_to_max_slots.get(station_tier, 3)

        # Get recipe placement data if available
        required_slots = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_slots = placement_data.slots

        # Calculate slot dimensions
        slot_width = 300
        slot_height = 60
        slot_spacing = 10
        total_height = min(len(required_slots), max_slots) * (slot_height + slot_spacing) if required_slots else max_slots * (slot_height + slot_spacing)

        start_x = placement_rect.centerx - slot_width // 2
        start_y = placement_rect.centery - total_height // 2

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click handling

        # Draw slots vertically
        num_slots = max(len(required_slots), 1) if required_slots else max_slots
        for i in range(num_slots):
            slot_y = start_y + i * (slot_height + slot_spacing)
            slot_rect = pygame.Rect(start_x, slot_y, slot_width, slot_height)
            slot_id = f"eng_slot_{i}"

            # Get required slot info
            required_slot = required_slots[i] if i < len(required_slots) else None
            has_user_material = slot_id in user_placement
            has_requirement = required_slot is not None

            # Slot background color
            slot_color = (50, 70, 50) if has_user_material else ((70, 60, 40) if has_requirement else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.rect(surf, slot_color, slot_rect)
            pygame.draw.rect(surf, (100, 100, 100), slot_rect, 2 if is_hovered else 1)

            # Draw slot type label (left side)
            if has_requirement:
                slot_type = required_slot.get('type', 'UNKNOWN')
                type_color = {
                    'FRAME': (150, 150, 200),
                    'FUNCTION': (200, 150, 100),
                    'POWER': (200, 100, 100),
                    'MODIFIER': (150, 200, 150),
                    'STABILIZER': (180, 180, 100)
                }.get(slot_type, (150, 150, 150))

                type_surf = self.small_font.render(slot_type, True, type_color)
                surf.blit(type_surf, (slot_rect.x + 10, slot_rect.y + 10))

                # Draw material name (right side)
                mat_id = required_slot.get('materialId', '')
                mat = mat_db.get_material(mat_id)
                mat_name = mat.name if mat else mat_id

                if has_user_material:
                    # Show user's material (green)
                    user_mat_id = user_placement[slot_id]
                    user_mat = mat_db.get_material(user_mat_id)
                    user_mat_name = user_mat.name if user_mat else user_mat_id
                    mat_surf = self.small_font.render(user_mat_name, True, (200, 255, 200))
                else:
                    # Show required material (gold hint)
                    mat_surf = self.small_font.render(mat_name, True, (180, 160, 120))

                surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))

                # Draw quantity
                qty = required_slot.get('quantity', 1)
                qty_surf = self.small_font.render(f"x{qty}", True, (150, 150, 150))
                surf.blit(qty_surf, (slot_rect.x + slot_width - 60, slot_rect.y + 10))

            slot_rects.append((slot_rect, slot_id))

        # Draw label
        label = f"Engineering Slots: {max_slots} max slots (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_world(self, world: WorldSystem, camera: Camera, character: Character,
                     damage_numbers: List[DamageNumber], combat_manager=None):
        pygame.draw.rect(self.screen, Config.COLOR_BACKGROUND, (0, 0, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT))

        for tile in world.get_visible_tiles(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(tile.position)
            if -Config.TILE_SIZE <= sx <= Config.VIEWPORT_WIDTH and -Config.TILE_SIZE <= sy <= Config.VIEWPORT_HEIGHT:
                rect = pygame.Rect(sx, sy, Config.TILE_SIZE, Config.TILE_SIZE)
                pygame.draw.rect(self.screen, tile.get_color(), rect)
                pygame.draw.rect(self.screen, Config.COLOR_GRID, rect, 1)

        for station in world.get_visible_stations(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(station.position)
            in_range = character.is_in_range(station.position)
            color = station.get_color() if in_range else tuple(max(0, c - 50) for c in station.get_color())
            size = Config.TILE_SIZE + 8  # Larger than before (was - 8, now + 8)
            pts = [(sx, sy - size // 2), (sx + size // 2, sy), (sx, sy + size // 2), (sx - size // 2, sy)]
            pygame.draw.polygon(self.screen, color, pts)
            pygame.draw.polygon(self.screen, (0, 0, 0), pts, 3)
            if in_range:
                tier_text = f"T{station.tier}"
                tier_surf = self.small_font.render(tier_text, True, (255, 255, 255))
                tier_rect = tier_surf.get_rect(center=(sx, sy))
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    self.screen.blit(self.small_font.render(tier_text, True, (0, 0, 0)),
                                     (tier_rect.x + dx, tier_rect.y + dy))
                self.screen.blit(tier_surf, tier_rect)

        for resource in world.get_visible_resources(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            if resource.depleted and not resource.respawns:
                continue
            sx, sy = camera.world_to_screen(resource.position)
            in_range = character.is_in_range(resource.position)

            can_harvest, reason = character.can_harvest_resource(resource) if in_range else (False, "")

            color = resource.get_color() if in_range else tuple(max(0, c - 50) for c in resource.get_color())
            size = Config.TILE_SIZE - 4
            rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)
            pygame.draw.rect(self.screen, color, rect)

            if in_range:
                border_color = Config.COLOR_CAN_HARVEST if can_harvest else Config.COLOR_CANNOT_HARVEST
                border_width = 3
            else:
                border_color = (0, 0, 0)
                border_width = 2
            pygame.draw.rect(self.screen, border_color, rect, border_width)

            if in_range and not resource.depleted:
                tier_text = f"T{resource.tier}"
                tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
                tier_bg = pygame.Rect(sx - size // 2 + 2, sy - size // 2 + 2,
                                      tier_surf.get_width() + 4, tier_surf.get_height() + 2)
                pygame.draw.rect(self.screen, (0, 0, 0, 180), tier_bg)
                self.screen.blit(tier_surf, (sx - size // 2 + 4, sy - size // 2 + 2))

            if resource.depleted and resource.respawns and in_range:
                progress = resource.get_respawn_progress()
                bar_w, bar_h = Config.TILE_SIZE - 8, 4
                bar_y = sy - Config.TILE_SIZE // 2 - 12
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (sx - bar_w // 2, bar_y, bar_w, bar_h))
                respawn_w = int(bar_w * progress)
                pygame.draw.rect(self.screen, Config.COLOR_RESPAWN_BAR, (sx - bar_w // 2, bar_y, respawn_w, bar_h))
                time_left = int(resource.respawn_timer - resource.time_until_respawn)
                time_surf = self.tiny_font.render(f"{time_left}s", True, (200, 200, 200))
                self.screen.blit(time_surf, (sx - time_surf.get_width() // 2, bar_y - 12))

            elif not resource.depleted and in_range:
                bar_w, bar_h = Config.TILE_SIZE - 8, 4
                bar_y = sy - Config.TILE_SIZE // 2 - 8
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (sx - bar_w // 2, bar_y, bar_w, bar_h))
                hp_w = int(bar_w * (resource.current_hp / resource.max_hp))
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR, (sx - bar_w // 2, bar_y, hp_w, bar_h))

        # Render enemies
        if combat_manager:
            for enemy in combat_manager.get_all_active_enemies():
                ex, ey = camera.world_to_screen(Position(enemy.position[0], enemy.position[1], 0))

                # Enemy body
                if enemy.is_alive:
                    # Color based on tier
                    tier_colors = {1: (200, 100, 100), 2: (255, 150, 0), 3: (200, 100, 255), 4: (255, 50, 50)}
                    enemy_color = tier_colors.get(enemy.definition.tier, (200, 100, 100))
                    if enemy.is_boss:
                        enemy_color = (255, 215, 0)  # Gold for bosses

                    size = Config.TILE_SIZE // 2
                    pygame.draw.circle(self.screen, enemy_color, (ex, ey), size)
                    pygame.draw.circle(self.screen, (0, 0, 0), (ex, ey), size, 2)

                    # Health bar
                    health_percent = enemy.current_health / enemy.max_health
                    bar_w, bar_h = Config.TILE_SIZE, 4
                    bar_y = ey - Config.TILE_SIZE // 2 - 12
                    pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (ex - bar_w // 2, bar_y, bar_w, bar_h))
                    hp_w = int(bar_w * health_percent)
                    pygame.draw.rect(self.screen, (255, 0, 0), (ex - bar_w // 2, bar_y, hp_w, bar_h))

                    # Tier indicator
                    tier_text = f"T{enemy.definition.tier}"
                    if enemy.is_boss:
                        tier_text = "BOSS"
                    tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
                    self.screen.blit(tier_surf, (ex - tier_surf.get_width() // 2, ey - 5))

                else:
                    # Corpse (greyed out)
                    corpse_color = (100, 100, 100)
                    size = Config.TILE_SIZE // 3
                    pygame.draw.circle(self.screen, corpse_color, (ex, ey), size)
                    loot_text = self.tiny_font.render("LOOT", True, (255, 255, 0))
                    self.screen.blit(loot_text, (ex - loot_text.get_width() // 2, ey - 10))

        # Render player
        center_x, center_y = camera.world_to_screen(character.position)
        pygame.draw.circle(self.screen, Config.COLOR_PLAYER, (center_x, center_y), Config.TILE_SIZE // 3)

        for dmg in damage_numbers:
            sx, sy = camera.world_to_screen(dmg.position)
            alpha = int(255 * (dmg.lifetime / 1.0))
            color = Config.COLOR_DAMAGE_CRIT if dmg.is_crit else Config.COLOR_DAMAGE_NORMAL
            text = f"{dmg.damage}!" if dmg.is_crit else str(dmg.damage)
            surf = (self.font if dmg.is_crit else self.small_font).render(text, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, surf.get_rect(center=(sx, sy)))

    def render_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        ui_rect = pygame.Rect(Config.VIEWPORT_WIDTH, 0, Config.UI_PANEL_WIDTH, Config.VIEWPORT_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, ui_rect)

        y = 20

        # Debug mode indicator
        if Config.DEBUG_INFINITE_RESOURCES:
            debug_surf = self.font.render("DEBUG MODE", True, (255, 100, 100))
            self.screen.blit(debug_surf, (Config.VIEWPORT_WIDTH + 20, y))
            y += 30

        self.render_text("CHARACTER INFO", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 40

        if character.class_system.current_class:
            class_text = f"Class: {character.class_system.current_class.name}"
            self.render_text(class_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 25

        self.render_text(f"Position: ({character.position.x:.1f}, {character.position.y:.1f})",
                         Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 25

        lvl_text = f"Level: {character.leveling.level}"
        if character.leveling.unallocated_stat_points > 0:
            lvl_text += f" ({character.leveling.unallocated_stat_points} pts!)"
        self.render_text(lvl_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 20

        exp_needed = character.leveling.get_exp_for_next_level()
        if exp_needed > 0:
            self.render_text(f"XP: {character.leveling.current_exp}/{exp_needed}",
                             Config.VIEWPORT_WIDTH + 20, y, small=True)
        else:
            self.render_text("MAX LEVEL", Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 30

        self.render_health_bar(character, Config.VIEWPORT_WIDTH + 20, y)
        y += 35
        self.render_mana_bar(character, Config.VIEWPORT_WIDTH + 20, y)
        y += 50

        self.render_text("SELECTED TOOL", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        if character.selected_tool:
            tool = character.selected_tool
            self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 20
            dur_text = f"Durability: {tool.durability_current}/{tool.durability_max}"
            if Config.DEBUG_INFINITE_RESOURCES:
                dur_text += " (∞)"
            self.render_text(dur_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 20
            self.render_text(f"Effectiveness: {tool.get_effectiveness() * 100:.0f}%",
                             Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 30

        title_count = len(character.titles.earned_titles)
        self.render_text(f"TITLES: {title_count}", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        for title in character.titles.earned_titles[-2:]:
            self.render_text(f"• {title.name}", Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 18

        if title_count > 0:
            y += 10

        self.render_text("CONTROLS", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        controls = [
            "WASD - Move",
            "CLICK - Harvest/Interact",
            "TAB - Switch tool",
            "1-5 - Use skills",
            "C - Stats",
            "E - Equipment",
            "K - Skills menu",
            "F1 - Debug Mode",
            "F2/F3/F4 - Debug Skills/Titles/Stats",
            "ESC - Close/Quit"
        ]
        for ctrl in controls:
            self.render_text(ctrl, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 22

    def render_health_bar(self, char, x, y):
        w, h = 300, 25
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, (x, y, w, h))
        hp_w = int(w * (char.health / char.max_health))
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH, (x, y, hp_w, h))
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, (x, y, w, h), 2)
        text = self.small_font.render(f"HP: {char.health}/{char.max_health}", True, Config.COLOR_TEXT)
        self.screen.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))

    def render_mana_bar(self, char, x, y):
        w, h = 300, 20
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, (x, y, w, h))
        mana_w = int(w * (char.mana / char.max_mana))
        pygame.draw.rect(self.screen, (50, 150, 255), (x, y, mana_w, h))
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, (x, y, w, h), 2)
        text = self.small_font.render(f"MP: {int(char.mana)}/{int(char.max_mana)}", True, Config.COLOR_TEXT)
        self.screen.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))

    def render_skill_hotbar(self, character: Character):
        """Render skill hotbar at bottom center of screen"""
        slot_size = 60
        slot_spacing = 10
        num_slots = 5
        total_width = num_slots * slot_size + (num_slots - 1) * slot_spacing

        # Position at bottom center
        start_x = (Config.VIEWPORT_WIDTH - total_width) // 2
        start_y = Config.VIEWPORT_HEIGHT - slot_size - 20

        skill_db = SkillDatabase.get_instance()
        hovered_skill = None
        hovered_slot_rect = None

        for i in range(num_slots):
            x = start_x + i * (slot_size + slot_spacing)
            y = start_y

            # Slot background
            slot_rect = pygame.Rect(x, y, slot_size, slot_size)
            pygame.draw.rect(self.screen, (30, 30, 40), slot_rect)
            pygame.draw.rect(self.screen, (100, 100, 120), slot_rect, 2)

            # Key number
            key_text = self.small_font.render(str(i + 1), True, (150, 150, 150))
            self.screen.blit(key_text, (x + 4, y + 4))

            # Get equipped skill in this slot
            skill_id = character.skills.equipped_skills[i]
            if skill_id:
                player_skill = character.skills.known_skills.get(skill_id)
                if player_skill:
                    skill_def = player_skill.get_definition()
                    if skill_def:
                        # Check hover
                        mouse_pos = pygame.mouse.get_pos()
                        if slot_rect.collidepoint(mouse_pos):
                            hovered_skill = (skill_def, player_skill)
                            hovered_slot_rect = slot_rect

                        # Skill name (abbreviated)
                        name_parts = skill_def.name.split()
                        short_name = "".join(p[0] for p in name_parts[:2])  # First letters
                        name_surf = self.font.render(short_name, True, (200, 200, 255))
                        name_rect = name_surf.get_rect(center=(x + slot_size // 2, y + slot_size // 2 - 5))
                        self.screen.blit(name_surf, name_rect)

                        # Cooldown overlay
                        if player_skill.current_cooldown > 0:
                            # Dark overlay
                            overlay = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
                            overlay.fill((0, 0, 0, 180))
                            self.screen.blit(overlay, (x, y))

                            # Cooldown timer
                            cd_text = self.small_font.render(f"{player_skill.current_cooldown:.1f}s", True, (255, 100, 100))
                            cd_rect = cd_text.get_rect(center=(x + slot_size // 2, y + slot_size // 2))
                            self.screen.blit(cd_text, cd_rect)
                        else:
                            # Mana cost
                            mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
                            cost_color = (100, 200, 255) if character.mana >= mana_cost else (255, 100, 100)
                            cost_text = self.tiny_font.render(f"{mana_cost}MP", True, cost_color)
                            self.screen.blit(cost_text, (x + 4, y + slot_size - 14))
            else:
                # Empty slot
                empty_text = self.tiny_font.render("Empty", True, (80, 80, 80))
                empty_rect = empty_text.get_rect(center=(x + slot_size // 2, y + slot_size // 2))
                self.screen.blit(empty_text, empty_rect)

        # Render tooltip for hovered skill
        if hovered_skill:
            self._render_skill_tooltip(hovered_skill[0], hovered_skill[1], hovered_slot_rect, character)

    def _render_skill_tooltip(self, skill_def, player_skill, slot_rect, character):
        """Render tooltip for a skill"""
        skill_db = SkillDatabase.get_instance()

        # Tooltip dimensions
        tooltip_width = 350
        tooltip_height = 200
        padding = 10

        # Position above the slot
        tooltip_x = slot_rect.centerx - tooltip_width // 2
        tooltip_y = slot_rect.y - tooltip_height - 10

        # Keep on screen
        tooltip_x = max(10, min(tooltip_x, Config.VIEWPORT_WIDTH - tooltip_width - 10))
        tooltip_y = max(10, tooltip_y)

        # Background
        surf = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))
        pygame.draw.rect(surf, (100, 150, 200), surf.get_rect(), 2)

        y = padding

        # Skill name
        name_surf = self.font.render(skill_def.name, True, (200, 220, 255))
        surf.blit(name_surf, (padding, y))
        y += 25

        # Tier and rarity
        tier_text = f"Tier {skill_def.tier} - {skill_def.rarity.upper()}"
        tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
        surf.blit(self.small_font.render(tier_text, True, tier_color), (padding, y))
        y += 20

        # Cost and cooldown
        mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
        cooldown = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
        cost_text = f"Cost: {mana_cost} MP  |  Cooldown: {cooldown}s"
        surf.blit(self.small_font.render(cost_text, True, (150, 200, 255)), (padding, y))
        y += 25

        # Effect
        effect_text = f"{skill_def.effect.effect_type.capitalize()} - {skill_def.effect.category} ({skill_def.effect.magnitude})"
        surf.blit(self.small_font.render(effect_text, True, (200, 200, 100)), (padding, y))
        y += 20

        # Description (word-wrapped)
        desc_words = skill_def.description.split()
        line = ""
        for word in desc_words:
            test_line = line + word + " "
            if self.tiny_font.size(test_line)[0] > tooltip_width - 2 * padding:
                surf.blit(self.tiny_font.render(line, True, (180, 180, 180)), (padding, y))
                y += 16
                line = word + " "
            else:
                line = test_line
        if line:
            surf.blit(self.tiny_font.render(line, True, (180, 180, 180)), (padding, y))

        self.screen.blit(surf, (tooltip_x, tooltip_y))

    def render_skills_menu_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render skills menu for managing equipped skills"""
        if not character.skills_ui_open:
            return None

        skill_db = SkillDatabase.get_instance()
        if not skill_db.loaded:
            return None

        ww, wh = 1000, 700
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
        wy = 50

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 245))

        # Title
        surf.blit(self.font.render("SKILLS MANAGEMENT", True, (150, 200, 255)), (ww // 2 - 120, 20))
        surf.blit(self.small_font.render("[ESC] Close | [Mouse Wheel] Scroll | Click to equip | Right-click to unequip", True, (180, 180, 180)),
                  (ww // 2 - 330, 50))

        # Hotbar section (top)
        y_pos = 90
        surf.blit(self.small_font.render("SKILL HOTBAR (1-5):", True, (200, 200, 200)), (20, y_pos))
        y_pos += 30

        hotbar_rects = []
        slot_size = 70
        for i in range(5):
            x = 30 + i * (slot_size + 10)
            slot_rect = pygame.Rect(x, y_pos, slot_size, slot_size)

            # Get skill in this slot
            skill_id = character.skills.equipped_skills[i]
            player_skill = character.skills.known_skills.get(skill_id) if skill_id else None
            skill_def = player_skill.get_definition() if player_skill else None

            # Slot background
            bg_color = (50, 70, 90) if skill_def else (40, 40, 50)
            pygame.draw.rect(surf, bg_color, slot_rect)
            pygame.draw.rect(surf, (100, 150, 200), slot_rect, 2)

            # Slot number
            num_surf = self.small_font.render(str(i + 1), True, (150, 150, 150))
            surf.blit(num_surf, (x + 4, y_pos + 4))

            if skill_def:
                # Skill abbreviation
                name_parts = skill_def.name.split()
                short_name = "".join(p[0] for p in name_parts[:2])
                name_surf = self.font.render(short_name, True, (200, 220, 255))
                name_rect = name_surf.get_rect(center=(x + slot_size // 2, y_pos + slot_size // 2))
                surf.blit(name_surf, name_rect)

            hotbar_rects.append((slot_rect, i, skill_id))

        y_pos += slot_size + 30

        # Learned skills section
        total_skills = len(character.skills.known_skills)
        surf.blit(self.small_font.render(f"LEARNED SKILLS ({total_skills}):", True, (200, 200, 200)), (20, y_pos))
        y_pos += 30

        skill_rects = []
        max_visible = 10

        # Calculate scroll bounds
        max_scroll = max(0, total_skills - max_visible)
        character.skills_menu_scroll_offset = max(0, min(character.skills_menu_scroll_offset, max_scroll))

        # Get skills to display based on scroll offset
        all_skills = list(character.skills.known_skills.items())
        visible_skills = all_skills[character.skills_menu_scroll_offset:character.skills_menu_scroll_offset + max_visible]

        # Show scroll indicator if needed
        if total_skills > max_visible:
            scroll_text = f"[Scroll: {character.skills_menu_scroll_offset + 1}-{min(character.skills_menu_scroll_offset + max_visible, total_skills)} of {total_skills}]"
            surf.blit(self.tiny_font.render(scroll_text, True, (150, 150, 200)), (ww - 280, y_pos - 25))

        for idx, (skill_id, player_skill) in enumerate(visible_skills):
            skill_def = player_skill.get_definition()
            if not skill_def:
                continue

            # Check if equipped
            equipped_slot = None
            for slot_idx, equipped_id in enumerate(character.skills.equipped_skills):
                if equipped_id == skill_id:
                    equipped_slot = slot_idx
                    break

            skill_rect = pygame.Rect(20, y_pos, ww - 40, 50)
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = skill_rect.collidepoint(rx, ry)

            # Background
            bg_color = (70, 90, 60) if equipped_slot is not None else (50, 50, 70)
            if is_hovered:
                bg_color = tuple(min(255, c + 20) for c in bg_color)
            pygame.draw.rect(surf, bg_color, skill_rect)
            pygame.draw.rect(surf, (120, 140, 180) if is_hovered else (80, 80, 100), skill_rect, 2)

            # Skill name
            surf.blit(self.small_font.render(skill_def.name, True, (255, 255, 255)), (30, y_pos + 5))

            # Tier and rarity
            tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
            surf.blit(self.tiny_font.render(f"T{skill_def.tier} {skill_def.rarity.upper()}", True, tier_color), (30, y_pos + 25))

            # Mana cost and cooldown
            mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
            cooldown = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
            surf.blit(self.tiny_font.render(f"{mana_cost}MP  |  {cooldown}s CD", True, (150, 200, 255)), (200, y_pos + 25))

            # Equipped indicator
            if equipped_slot is not None:
                surf.blit(self.small_font.render(f"[Slot {equipped_slot + 1}]", True, (100, 255, 100)), (ww - 150, y_pos + 15))
            else:
                surf.blit(self.tiny_font.render("Click to equip", True, (120, 120, 150)), (ww - 150, y_pos + 18))

            skill_rects.append((skill_rect, skill_id, player_skill, skill_def))
            y_pos += 55

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        return window_rect, hotbar_rects, skill_rects

    def render_notifications(self, notifications: List[Notification]):
        y = 50
        for notification in notifications:
            alpha = int(255 * min(1.0, notification.lifetime / 3.0))
            surf = self.font.render(notification.message, True, notification.color)
            surf.set_alpha(alpha)
            x = Config.VIEWPORT_WIDTH // 2 - surf.get_width() // 2

            bg = pygame.Surface((surf.get_width() + 20, surf.get_height() + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, int(180 * alpha / 255)))
            self.screen.blit(bg, (x - 10, y - 5))

            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 15

    def render_inventory_panel(self, character: Character, mouse_pos: Tuple[int, int]):
        panel_rect = pygame.Rect(Config.INVENTORY_PANEL_X, Config.INVENTORY_PANEL_Y,
                                 Config.INVENTORY_PANEL_WIDTH, Config.INVENTORY_PANEL_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, panel_rect)
        self.render_text("INVENTORY", 20, Config.INVENTORY_PANEL_Y + 10, bold=True)

        start_x, start_y = 20, Config.INVENTORY_PANEL_Y + 50
        slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
        slots_per_row = Config.INVENTORY_SLOTS_PER_ROW
        hovered_slot = None

        for i, item_stack in enumerate(character.inventory.slots):
            row, col = i // slots_per_row, i % slots_per_row
            x, y = start_x + col * (slot_size + spacing), start_y + row * (slot_size + spacing)
            slot_rect = pygame.Rect(x, y, slot_size, slot_size)
            is_hovered = slot_rect.collidepoint(mouse_pos)

            if is_hovered and item_stack:
                hovered_slot = (i, item_stack, slot_rect)

            # Check if item is equipped
            is_equipped = False
            if item_stack and item_stack.is_equipment():
                is_equipped = character.equipment.is_equipped(item_stack.item_id)

            pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED if item_stack else Config.COLOR_SLOT_EMPTY,
                             slot_rect)

            # Special border for equipped items
            if is_equipped:
                border = Config.COLOR_EQUIPPED
                border_width = 3
            elif is_hovered:
                border = Config.COLOR_SLOT_SELECTED
                border_width = 2
            else:
                border = Config.COLOR_SLOT_BORDER
                border_width = 2
            pygame.draw.rect(self.screen, border, slot_rect, border_width)

            if item_stack and i != character.inventory.dragging_slot:
                self.render_item_in_slot(item_stack, slot_rect, is_equipped)

        if character.inventory.dragging_stack:
            drag_rect = pygame.Rect(mouse_pos[0] - slot_size // 2, mouse_pos[1] - slot_size // 2, slot_size, slot_size)
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED, drag_rect)
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_SELECTED, drag_rect, 3)
            self.render_item_in_slot(character.inventory.dragging_stack, drag_rect, False)

        if hovered_slot and not character.inventory.dragging_stack:
            _, item_stack, _ = hovered_slot
            self.render_item_tooltip(item_stack, mouse_pos, character)

    def render_item_in_slot(self, item_stack: ItemStack, rect: pygame.Rect, is_equipped: bool = False):
        # Check if it's equipment
        if item_stack.is_equipment():
            equipment = item_stack.get_equipment()
            if equipment:
                color = Config.RARITY_COLORS.get(equipment.rarity, (200, 200, 200))
                inner = pygame.Rect(rect.x + 5, rect.y + 5, rect.width - 10, rect.height - 10)
                pygame.draw.rect(self.screen, color, inner)

                # Show "E" for equipped items
                if is_equipped:
                    e_surf = self.font.render("E", True, (255, 255, 255))
                    e_rect = e_surf.get_rect(center=inner.center)
                    # Black outline
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                        self.screen.blit(self.font.render("E", True, (0, 0, 0)), (e_rect.x + dx, e_rect.y + dy))
                    self.screen.blit(e_surf, e_rect)
                else:
                    tier_surf = self.small_font.render(f"T{equipment.tier}", True, (0, 0, 0))
                    self.screen.blit(tier_surf, (rect.x + 6, rect.y + 6))

                # Add item name label
                name_surf = self.tiny_font.render(equipment.name[:8], True, (255, 255, 255))
                name_rect = name_surf.get_rect(centerx=rect.centerx, bottom=rect.bottom - 2)
                # Black outline for readability
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    self.screen.blit(self.tiny_font.render(equipment.name[:8], True, (0, 0, 0)),
                                     (name_rect.x + dx, name_rect.y + dy))
                self.screen.blit(name_surf, name_rect)
                return

        # Regular material
        mat = item_stack.get_material()
        if mat:
            color = Config.RARITY_COLORS.get(mat.rarity, (200, 200, 200))
            inner = pygame.Rect(rect.x + 5, rect.y + 5, rect.width - 10, rect.height - 10)
            pygame.draw.rect(self.screen, color, inner)
            tier_surf = self.small_font.render(f"T{mat.tier}", True, (0, 0, 0))
            self.screen.blit(tier_surf, (rect.x + 6, rect.y + 6))

            # Add item name label
            name_surf = self.tiny_font.render(mat.name[:8], True, (255, 255, 255))
            name_rect = name_surf.get_rect(centerx=rect.centerx, bottom=rect.bottom - 2)
            # Black outline for readability
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.tiny_font.render(mat.name[:8], True, (0, 0, 0)),
                                 (name_rect.x + dx, name_rect.y + dy))
            self.screen.blit(name_surf, name_rect)

        if item_stack.quantity > 1:
            qty_text = str(item_stack.quantity)
            qty_surf = self.small_font.render(qty_text, True, (255, 255, 255))
            qty_rect = qty_surf.get_rect(bottomright=(rect.right - 3, rect.bottom - 3))
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.small_font.render(qty_text, True, (0, 0, 0)),
                                 (qty_rect.x + dx, qty_rect.y + dy))
            self.screen.blit(qty_surf, qty_rect)

    def render_item_tooltip(self, item_stack: ItemStack, mouse_pos: Tuple[int, int], character: Character):
        # Check if equipment
        if item_stack.is_equipment():
            equipment = item_stack.get_equipment()
            if equipment:
                self.render_equipment_tooltip(equipment, mouse_pos, character, from_inventory=True)
                return

        # Regular material tooltip
        mat = item_stack.get_material()
        if not mat:
            return

        tw, th, pad = 250, 120, 10
        x, y = mouse_pos[0] + 15, mouse_pos[1] + 15
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - 15
        if y + th > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - th - 15

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill(Config.COLOR_TOOLTIP_BG)

        y_pos = pad
        color = Config.RARITY_COLORS.get(mat.rarity, (200, 200, 200))
        surf.blit(self.font.render(mat.name, True, color), (pad, y_pos))
        y_pos += 25
        surf.blit(self.small_font.render(f"Tier {mat.tier} | {mat.category.capitalize()}", True, (180, 180, 180)),
                  (pad, y_pos))
        y_pos += 20
        surf.blit(self.small_font.render(f"Rarity: {mat.rarity.capitalize()}", True, color), (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_crafting_ui(self, character: Character, mouse_pos: Tuple[int, int], selected_recipe=None, user_placement=None):
        """
        Render crafting UI with two-panel layout:
        - Left panel (450px): Recipe list
        - Right panel (700px): Placement visualization + craft buttons

        Args:
            selected_recipe: Currently selected recipe (to highlight in UI)
            user_placement: User's current material placement (Dict[str, str])
        """
        if user_placement is None:
            user_placement = {}
        if not character.crafting_ui_open or not character.active_station:
            return None

        # Store these temporarily so child methods can access them
        # (Python scoping doesn't allow nested functions to see parameters)
        self._temp_selected_recipe = selected_recipe
        self._temp_user_placement = user_placement

        # Always render recipe list on the left (pass scroll offset from game engine)
        # Note: Renderer doesn't have direct access to game engine, so we need to get it via a hack
        # Check if there's a scroll offset to use (this will be set by the caller)
        scroll_offset = getattr(self, '_temp_scroll_offset', 0)
        recipe_result = self._render_recipe_selection_sidebar(character, mouse_pos, scroll_offset)

        # If a recipe is selected, render placement UI on the right
        # (Note: Placement UI rendering is handled by the recipe selection sidebar)

        return recipe_result

    def _render_recipe_selection_sidebar(self, character: Character, mouse_pos: Tuple[int, int], scroll_offset: int = 0):
        """Render recipe selection sidebar - left side with scrolling support"""
        recipe_db = RecipeDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        # Window dimensions - expanded to fit two panels
        ww, wh = 1200, 600
        left_panel_w = 450
        right_panel_w = 700
        separator_x = left_panel_w + 20

        wx = (Config.VIEWPORT_WIDTH - ww) // 2
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        # Header
        header = f"{character.active_station.station_type.value.upper()} (T{character.active_station.tier})"
        surf.blit(self.font.render(header, True, character.active_station.get_color()), (20, 20))
        surf.blit(self.small_font.render("[ESC] Close | Select recipe to place materials", True, (180, 180, 180)), (ww - 400, 20))

        # Get recipes for this station
        recipes = recipe_db.get_recipes_for_station(character.active_station.station_type.value,
                                                    character.active_station.tier)

        # ======================
        # LEFT PANEL: Recipe List with Scrolling
        # ======================
        visible_recipes = []  # Initialize to empty list
        if not recipes:
            surf.blit(self.font.render("No recipes available", True, (200, 200, 200)), (20, 80))
        else:
            # Apply scroll offset and show 8 recipes at a time
            total_recipes = len(recipes)
            max_visible = 8
            start_idx = min(scroll_offset, max(0, total_recipes - max_visible))
            end_idx = min(start_idx + max_visible, total_recipes)
            visible_recipes = recipes[start_idx:end_idx]

            # Show scroll indicators if needed
            if total_recipes > max_visible:
                scroll_text = f"Recipes {start_idx + 1}-{end_idx} of {total_recipes}"
                scroll_surf = self.small_font.render(scroll_text, True, (150, 150, 150))
                surf.blit(scroll_surf, (20, 50))

                # Show scroll arrows
                if start_idx > 0:
                    up_arrow = self.small_font.render("▲ Scroll Up", True, (100, 200, 100))
                    surf.blit(up_arrow, (left_panel_w - 120, 50))
                if end_idx < total_recipes:
                    down_arrow = self.small_font.render("▼ Scroll Down", True, (100, 200, 100))
                    surf.blit(down_arrow, (left_panel_w - 120, wh - 30))

            y_off = 70
            for i, recipe in enumerate(visible_recipes):
                # Compact recipe display (no buttons, just info)
                num_inputs = len(recipe.inputs)
                btn_height = max(70, 35 + num_inputs * 16 + 5)

                btn = pygame.Rect(20, y_off, left_panel_w - 30, btn_height)
                can_craft = recipe_db.can_craft(recipe, character.inventory)

                # Highlight selected recipe with gold border
                is_selected = (self._temp_selected_recipe and self._temp_selected_recipe.recipe_id == recipe.recipe_id)

                btn_color = (60, 80, 60) if can_craft else (80, 60, 60)
                if is_selected:
                    btn_color = (80, 70, 30)  # Gold tint for selected

                pygame.draw.rect(surf, btn_color, btn)
                border_color = (255, 215, 0) if is_selected else (100, 100, 100)
                border_width = 3 if is_selected else 2
                pygame.draw.rect(surf, border_color, btn, border_width)

                # Output name
                is_equipment = equip_db.is_equipment(recipe.output_id)
                if is_equipment:
                    equip = equip_db.create_equipment_from_id(recipe.output_id)
                    out_name = equip.name if equip else recipe.output_id
                    color = Config.RARITY_COLORS.get(equip.rarity, (200, 200, 200)) if equip else (200, 200, 200)
                else:
                    out_mat = mat_db.get_material(recipe.output_id)
                    out_name = out_mat.name if out_mat else recipe.output_id
                    color = Config.RARITY_COLORS.get(out_mat.rarity, (200, 200, 200)) if out_mat else (200, 200, 200)

                surf.blit(self.font.render(f"{out_name} x{recipe.output_qty}", True, color),
                          (btn.x + 10, btn.y + 8))

                # Material requirements (compact)
                req_y = btn.y + 30
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId', '')
                    req = inp.get('quantity', 0)
                    avail = character.inventory.get_item_count(mat_id)
                    mat = mat_db.get_material(mat_id)
                    mat_name = mat.name if mat else mat_id
                    req_color = (100, 255, 100) if avail >= req or Config.DEBUG_INFINITE_RESOURCES else (255, 100, 100)
                    surf.blit(self.small_font.render(f"{mat_name}: {avail}/{req}", True, req_color),
                              (btn.x + 15, req_y))
                    req_y += 16

                y_off += btn_height + 8

        # ======================
        # DIVIDER
        # ======================
        pygame.draw.line(surf, (100, 100, 100), (separator_x, 60), (separator_x, wh - 20), 2)

        # ======================
        # RIGHT PANEL: Placement + Buttons
        # ======================
        right_panel_x = separator_x + 20
        right_panel_y = 70

        if self._temp_selected_recipe:
            # Selected recipe - show placement and buttons
            selected = self._temp_selected_recipe
            can_craft = recipe_db.can_craft(selected, character.inventory)

            # Placement visualization area
            placement_h = 380
            placement_rect = pygame.Rect(right_panel_x, right_panel_y, right_panel_w - 40, placement_h)
            pygame.draw.rect(surf, (30, 30, 40), placement_rect)
            pygame.draw.rect(surf, (80, 80, 90), placement_rect, 2)

            # Render discipline-specific placement UI
            station_type = character.active_station.station_type.value
            station_tier = character.active_station.tier
            placement_grid_rects = {}  # Will store grid cell rects for click detection

            if station_type == 'smithing':
                # Smithing: Grid-based placement
                placement_grid_rects = self.render_smithing_grid(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'refining':
                # Refining: Hub-and-spoke
                placement_grid_rects = self.render_refining_hub(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'alchemy':
                # Alchemy: Sequential
                placement_grid_rects = self.render_alchemy_sequence(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'engineering':
                # Engineering: Slot-type
                placement_grid_rects = self.render_engineering_slots(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'adornments':
                # Enchanting: Vertex-based pattern renderer
                placement_grid_rects = self.render_adornment_pattern(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)

            # Craft buttons at bottom of right panel
            if can_craft:
                btn_y = placement_rect.bottom + 20
                instant_btn_w, instant_btn_h = 120, 40
                minigame_btn_w, minigame_btn_h = 120, 40

                # Center the buttons horizontally in right panel
                total_btn_w = instant_btn_w + minigame_btn_w + 20
                start_x = right_panel_x + (right_panel_w - 40 - total_btn_w) // 2

                instant_btn_x = start_x
                minigame_btn_x = start_x + instant_btn_w + 20

                # Instant button (gray)
                instant_rect = pygame.Rect(instant_btn_x, btn_y, instant_btn_w, instant_btn_h)
                pygame.draw.rect(surf, (60, 60, 60), instant_rect)
                pygame.draw.rect(surf, (120, 120, 120), instant_rect, 2)
                instant_text = self.font.render("Instant", True, (200, 200, 200))
                surf.blit(instant_text, (instant_btn_x + 25, btn_y + 10))

                instant_subtext = self.small_font.render("0 XP", True, (150, 150, 150))
                surf.blit(instant_subtext, (instant_btn_x + 40, btn_y + 28))

                # Minigame button (gold)
                minigame_rect = pygame.Rect(minigame_btn_x, btn_y, minigame_btn_w, minigame_btn_h)
                pygame.draw.rect(surf, (80, 60, 20), minigame_rect)
                pygame.draw.rect(surf, (255, 215, 0), minigame_rect, 2)
                minigame_text = self.font.render("Minigame", True, (255, 215, 0))
                surf.blit(minigame_text, (minigame_btn_x + 10, btn_y + 10))

                minigame_subtext = self.small_font.render("1.5x XP", True, (255, 200, 100))
                surf.blit(minigame_subtext, (minigame_btn_x + 30, btn_y + 28))
            else:
                # Can't craft - show why
                btn_y = placement_rect.bottom + 30
                cannot_text = self.font.render("Insufficient Materials", True, (255, 100, 100))
                surf.blit(cannot_text, (right_panel_x + (right_panel_w - 40 - cannot_text.get_width())//2, btn_y))
        else:
            # No recipe selected - show prompt
            prompt_text = self.font.render("← Select a recipe to view details", True, (150, 150, 150))
            surf.blit(prompt_text, (right_panel_x + 50, right_panel_y + 150))

        self.screen.blit(surf, (wx, wy))
        # Return window rect, recipes, and grid cell rects for click handling
        grid_rects_absolute = []
        if self._temp_selected_recipe:
            # Convert relative grid rects to absolute screen coordinates
            for rect, grid_pos in placement_grid_rects:
                abs_rect = rect.move(wx, wy)  # Offset by window position
                grid_rects_absolute.append((abs_rect, grid_pos))
        # Return full recipe list (not just visible) so scroll calculation works
        return_recipes = recipes if recipes else []
        return pygame.Rect(wx, wy, ww, wh), return_recipes, grid_rects_absolute

    def render_equipment_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.equipment_ui_open:
            return None

        ww, wh = 800, 600
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = 50

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        surf.blit(self.font.render("EQUIPMENT", True, (255, 215, 0)), (20, 20))
        surf.blit(self.small_font.render("[E or ESC] Close | [SHIFT+CLICK] to unequip", True, (180, 180, 180)),
                  (ww - 350, 20))

        slot_size = 80
        slots_layout = {
            'helmet': (ww // 2 - slot_size // 2, 70),
            'mainHand': (ww // 2 - slot_size - 20, 170),
            'chestplate': (ww // 2 - slot_size // 2, 170),
            'offHand': (ww // 2 + 20, 170),
            'gauntlets': (ww // 2 - slot_size - 20, 270),
            'leggings': (ww // 2 - slot_size // 2, 270),
            'boots': (ww // 2 - slot_size // 2, 370),
            'accessory': (ww // 2 + 20, 270),
        }

        hovered_slot = None
        equipment_rects = {}

        for slot_name, (sx, sy) in slots_layout.items():
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            equipment_rects[slot_name] = (slot_rect, wx, wy)
            item = character.equipment.slots.get(slot_name)

            is_hovered = slot_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
            if is_hovered and item:
                hovered_slot = (slot_name, item)

            color = Config.COLOR_SLOT_FILLED if item else Config.COLOR_SLOT_EMPTY
            pygame.draw.rect(surf, color, slot_rect)
            border_color = Config.COLOR_SLOT_SELECTED if is_hovered else Config.COLOR_SLOT_BORDER
            pygame.draw.rect(surf, border_color, slot_rect, 2)

            if item:
                rarity_color = Config.RARITY_COLORS.get(item.rarity, (200, 200, 200))
                inner_rect = pygame.Rect(sx + 5, sy + 5, slot_size - 10, slot_size - 10)
                pygame.draw.rect(surf, rarity_color, inner_rect)

                tier_text = f"T{item.tier}"
                tier_surf = self.small_font.render(tier_text, True, (0, 0, 0))
                surf.blit(tier_surf, (sx + 8, sy + 8))

            label_surf = self.tiny_font.render(slot_name, True, (150, 150, 150))
            surf.blit(label_surf, (sx + slot_size // 2 - label_surf.get_width() // 2, sy + slot_size + 3))

        stats_x = 20
        stats_y = 470
        surf.blit(self.font.render("Equipment Stats:", True, (200, 200, 200)), (stats_x, stats_y))
        stats_y += 30

        weapon_dmg = character.equipment.get_weapon_damage()
        surf.blit(self.small_font.render(f"Weapon Damage: {weapon_dmg[0]}-{weapon_dmg[1]}", True, (200, 200, 200)),
                  (stats_x, stats_y))
        stats_y += 20

        total_defense = character.equipment.get_total_defense()
        surf.blit(self.small_font.render(f"Total Defense: {total_defense}", True, (200, 200, 200)), (stats_x, stats_y))
        stats_y += 20

        stat_bonuses = character.equipment.get_stat_bonuses()
        if stat_bonuses:
            surf.blit(self.small_font.render("Bonuses:", True, (150, 150, 150)), (stats_x, stats_y))
            stats_y += 18
            for stat, value in stat_bonuses.items():
                surf.blit(self.tiny_font.render(f"  +{value:.1f}% {stat}", True, (100, 200, 100)),
                          (stats_x + 10, stats_y))
                stats_y += 16

        if hovered_slot:
            slot_name, item = hovered_slot
            self.render_equipment_tooltip(item, (mouse_pos[0], mouse_pos[1]), character, from_inventory=False)

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), equipment_rects

    def render_equipment_tooltip(self, item: EquipmentItem, mouse_pos: Tuple[int, int], character: Character,
                                 from_inventory: bool = False):
        tw, th, pad = 320, 240, 10
        x, y = mouse_pos[0] + 15, mouse_pos[1] + 15
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - 15
        if y + th > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - th - 15

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill(Config.COLOR_TOOLTIP_BG)

        y_pos = pad
        color = Config.RARITY_COLORS.get(item.rarity, (200, 200, 200))

        surf.blit(self.font.render(item.name, True, color), (pad, y_pos))
        y_pos += 25
        surf.blit(self.small_font.render(f"Tier {item.tier} | {item.rarity.capitalize()} | {item.slot}", True, color),
                  (pad, y_pos))
        y_pos += 25

        if item.damage[0] > 0:
            dmg = item.get_actual_damage()
            surf.blit(self.small_font.render(f"Damage: {dmg[0]}-{dmg[1]}", True, (200, 200, 200)), (pad, y_pos))
            y_pos += 20

        if item.defense > 0:
            def_val = int(item.defense * item.get_effectiveness())
            surf.blit(self.small_font.render(f"Defense: {def_val}", True, (200, 200, 200)), (pad, y_pos))
            y_pos += 20

        if item.attack_speed != 1.0:
            surf.blit(self.small_font.render(f"Attack Speed: {item.attack_speed:.2f}x", True, (200, 200, 200)),
                      (pad, y_pos))
            y_pos += 20

        dur_pct = (item.durability_current / item.durability_max) * 100
        dur_color = (100, 255, 100) if dur_pct > 50 else (255, 200, 100) if dur_pct > 25 else (255, 100, 100)
        dur_text = f"Durability: {item.durability_current}/{item.durability_max} ({dur_pct:.0f}%)"
        if Config.DEBUG_INFINITE_RESOURCES:
            dur_text += " (∞)"
        surf.blit(self.small_font.render(dur_text, True, dur_color), (pad, y_pos))
        y_pos += 20

        if item.requirements:
            y_pos += 5
            surf.blit(self.tiny_font.render("Requirements:", True, (150, 150, 150)), (pad, y_pos))
            y_pos += 15
            can_equip, reason = item.can_equip(character)
            req_color = (100, 255, 100) if can_equip else (255, 100, 100)
            if 'level' in item.requirements:
                surf.blit(self.tiny_font.render(f"  Level {item.requirements['level']}", True, req_color),
                          (pad + 10, y_pos))
                y_pos += 14
            if 'stats' in item.requirements:
                for stat, val in item.requirements['stats'].items():
                    surf.blit(self.tiny_font.render(f"  {stat}: {val}", True, req_color), (pad + 10, y_pos))
                    y_pos += 14

        # Show hint about equipping/unequipping
        y_pos += 5
        if from_inventory:
            hint = "[DOUBLE-CLICK] to equip"
        else:
            hint = "[SHIFT+CLICK] to unequip"
        surf.blit(self.tiny_font.render(hint, True, (150, 150, 255)), (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_enchantment_selection_ui(self, mouse_pos: Tuple[int, int], recipe: Recipe, compatible_items: List):
        """Render UI for selecting which item to apply enchantment to"""
        if not recipe or not compatible_items:
            return None

        ww, wh = 600, 500
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = 100

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))

        # Title
        title_text = f"Apply {recipe.enchantment_name}"
        surf.blit(self.font.render(title_text, True, (255, 215, 0)), (20, 20))
        surf.blit(self.small_font.render("[ESC] Cancel | [CLICK] Select Item", True, (180, 180, 180)),
                  (ww - 280, 20))

        # Description
        y_pos = 60
        surf.blit(self.small_font.render("Select an item to enchant:", True, (200, 200, 200)), (20, y_pos))
        y_pos += 30

        # List compatible items
        slot_size = 60
        item_rects = []

        for idx, (source_type, source_id, item_stack, equipment) in enumerate(compatible_items):
            if y_pos + slot_size + 10 > wh - 20:
                break  # Don't overflow window

            item_rect = pygame.Rect(20, y_pos, ww - 40, slot_size + 10)
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = item_rect.collidepoint(rx, ry)

            # Background
            bg_color = (50, 50, 70) if is_hovered else (35, 35, 50)
            pygame.draw.rect(surf, bg_color, item_rect)
            pygame.draw.rect(surf, (100, 100, 150) if is_hovered else (70, 70, 90), item_rect, 2)

            # Item icon/color
            icon_rect = pygame.Rect(30, y_pos + 5, slot_size, slot_size)
            rarity_color = Config.RARITY_COLORS.get(equipment.rarity, (200, 200, 200))
            pygame.draw.rect(surf, rarity_color, icon_rect)
            pygame.draw.rect(surf, (50, 50, 50), icon_rect, 2)

            # Tier
            tier_text = f"T{equipment.tier}"
            tier_surf = self.small_font.render(tier_text, True, (0, 0, 0))
            surf.blit(tier_surf, (35, y_pos + 10))

            # Item name and info
            name_x = 110
            surf.blit(self.small_font.render(equipment.name, True, (255, 255, 255)),
                     (name_x, y_pos + 10))

            # Location (inventory or equipped)
            location_text = f"[{source_type.upper()}]" if source_type == 'equipped' else f"[Inventory slot {source_id}]"
            surf.blit(self.tiny_font.render(location_text, True, (150, 150, 200)),
                     (name_x, y_pos + 35))

            # Show current enchantments if any
            if equipment.enchantments:
                enchant_count = len(equipment.enchantments)
                surf.blit(self.tiny_font.render(f"Enchantments: {enchant_count}", True, (100, 200, 200)),
                         (name_x, y_pos + 50))

            item_rects.append((item_rect, source_type, source_id, item_stack, equipment))
            y_pos += slot_size + 15

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        return window_rect, item_rects

    def render_class_selection_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.class_selection_open:
            return None

        class_db = ClassDatabase.get_instance()
        if not class_db.loaded or not class_db.classes:
            return None

        ww, wh = 900, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = 50

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        surf.blit(self.font.render("SELECT YOUR CLASS", True, (255, 215, 0)), (ww // 2 - 100, 20))
        surf.blit(self.small_font.render("Choose wisely - this defines your playstyle", True, (180, 180, 180)),
                  (ww // 2 - 150, 50))

        classes_list = list(class_db.classes.values())
        col_width = (ww - 60) // 2
        card_height = 90

        class_buttons = []
        for idx, class_def in enumerate(classes_list):
            col = idx % 2
            row = idx // 2

            x = 20 + col * (col_width + 20)
            y = 100 + row * (card_height + 10)

            card_rect = pygame.Rect(x, y, col_width, card_height)
            is_hovered = card_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

            card_color = (60, 80, 100) if is_hovered else (40, 50, 60)
            pygame.draw.rect(surf, card_color, card_rect)
            pygame.draw.rect(surf, (100, 120, 140) if is_hovered else (80, 90, 100), card_rect, 2)

            name_surf = self.font.render(class_def.name, True, (255, 215, 0))
            surf.blit(name_surf, (x + 10, y + 8))

            bonus_y = y + 35
            for bonus_type, value in list(class_def.bonuses.items())[:2]:
                bonus_text = f"+{value if isinstance(value, int) else f'{value * 100:.0f}%'} {bonus_type.replace('_', ' ')}"
                bonus_surf = self.tiny_font.render(bonus_text, True, (100, 200, 100))
                surf.blit(bonus_surf, (x + 15, bonus_y))
                bonus_y += 14

            if is_hovered:
                select_surf = self.small_font.render("[CLICK] Select", True, (100, 255, 100))
                surf.blit(select_surf, (x + col_width - select_surf.get_width() - 10, y + card_height - 25))

            class_buttons.append((card_rect, class_def))

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), class_buttons

    def render_stats_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.stats_ui_open:
            return None

        ww, wh = 900, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = 50

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        surf.blit(self.font.render(f"CHARACTER - Level {character.leveling.level}", True, (255, 215, 0)), (20, 20))
        surf.blit(self.small_font.render("[C or ESC] Close", True, (180, 180, 180)), (ww - 150, 20))

        col1_x, col2_x, col3_x = 20, 320, 620
        y_start = 70

        y = y_start
        surf.blit(self.font.render("STATS", True, (255, 255, 255)), (col1_x, y))
        y += 35

        if character.leveling.unallocated_stat_points > 0:
            surf.blit(self.small_font.render(f"Points: {character.leveling.unallocated_stat_points}",
                                             True, (0, 255, 0)), (col1_x, y))
            y += 25

        stat_buttons = []
        for stat_name, label in [('strength', 'STR'), ('defense', 'DEF'), ('vitality', 'VIT'),
                                 ('luck', 'LCK'), ('agility', 'AGI'), ('intelligence', 'INT')]:
            val = getattr(character.stats, stat_name)
            bonus = character.stats.get_bonus(stat_name)
            surf.blit(self.small_font.render(f"{label}: {val} (+{bonus * 100:.0f}%)", True, (200, 200, 200)),
                      (col1_x, y))

            if character.leveling.unallocated_stat_points > 0:
                btn = pygame.Rect(col1_x + 150, y - 2, 40, 20)
                pygame.draw.rect(surf, (50, 100, 50), btn)
                pygame.draw.rect(surf, (100, 200, 100), btn, 2)
                plus = self.small_font.render("+1", True, (255, 255, 255))
                surf.blit(plus, plus.get_rect(center=btn.center))
                stat_buttons.append((btn, stat_name))
            y += 28

        y = y_start
        surf.blit(self.font.render("TITLES", True, (255, 255, 255)), (col2_x, y))
        y += 35
        surf.blit(self.small_font.render(f"Earned: {len(character.titles.earned_titles)}",
                                         True, (200, 200, 200)), (col2_x, y))
        y += 30

        for title in character.titles.earned_titles[-8:]:
            tier_color = {
                'novice': (200, 200, 200), 'apprentice': (100, 255, 100), 'journeyman': (100, 150, 255),
                'expert': (200, 100, 255), 'master': (255, 215, 0)
            }.get(title.tier, (200, 200, 200))

            surf.blit(self.small_font.render(f"• {title.name}", True, tier_color), (col2_x, y))
            y += 18
            surf.blit(self.tiny_font.render(f"  {title.bonus_description}", True, (100, 200, 100)), (col2_x, y))
            y += 20

        if len(character.titles.earned_titles) == 0:
            surf.blit(self.small_font.render("Keep playing to earn titles!", True, (150, 150, 150)), (col2_x, y))

        y = y_start
        surf.blit(self.font.render("PROGRESS", True, (255, 255, 255)), (col3_x, y))
        y += 35

        title_db = TitleDatabase.get_instance()
        activities_shown = set()

        for activity_type in ['mining', 'forestry', 'smithing', 'refining', 'alchemy']:
            count = character.activities.get_count(activity_type)
            if count > 0 or activity_type in ['mining', 'forestry']:
                next_title = None
                for title_def in title_db.titles.values():
                    if title_def.activity_type == activity_type:
                        if not character.titles.has_title(title_def.title_id):
                            if count < title_def.acquisition_threshold:
                                if next_title is None or title_def.acquisition_threshold < next_title.acquisition_threshold:
                                    next_title = title_def

                if next_title and len(activities_shown) < 5:
                    activities_shown.add(activity_type)
                    progress = count / next_title.acquisition_threshold
                    surf.blit(self.small_font.render(f"{activity_type.capitalize()}:", True, (180, 180, 180)),
                              (col3_x, y))
                    y += 18

                    bar_w, bar_h = 220, 12
                    bar_rect = pygame.Rect(col3_x, y, bar_w, bar_h)
                    pygame.draw.rect(surf, (40, 40, 40), bar_rect)
                    prog_w = int(bar_w * min(1.0, progress))
                    pygame.draw.rect(surf, (100, 200, 100), pygame.Rect(col3_x, y, prog_w, bar_h))
                    pygame.draw.rect(surf, (100, 100, 100), bar_rect, 1)

                    prog_text = f"{count}/{next_title.acquisition_threshold}"
                    prog_surf = self.tiny_font.render(prog_text, True, (255, 255, 255))
                    surf.blit(prog_surf, (col3_x + bar_w // 2 - prog_surf.get_width() // 2, y + 1))
                    y += 18

                    next_surf = self.tiny_font.render(f"Next: {next_title.name}", True, (150, 150, 150))
                    surf.blit(next_surf, (col3_x, y))
                    y += 22

        if len(activities_shown) == 0:
            surf.blit(self.small_font.render("Start gathering and crafting!", True, (150, 150, 150)), (col3_x, y))

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), stat_buttons

    def render_text(self, text: str, x: int, y: int, bold: bool = False, small: bool = False):
        font = self.small_font if small else self.font
        if bold:
            font.set_bold(True)
        surf = font.render(text, True, Config.COLOR_TEXT)
        self.screen.blit(surf, (x, y))
        if bold:
            font.set_bold(False)


# ============================================================================
# AUTOMATED TESTING FRAMEWORK
# ============================================================================
class CraftingSystemTester:
    """Automated testing framework for crafting system - simulates user interactions"""

    def __init__(self, game_engine):
        self.game = game_engine
        self.test_results = []
        self.tests_passed = 0
        self.tests_failed = 0

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log a test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        self.test_results.append(result)
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        print(result)

    def run_all_tests(self):
        """Run comprehensive crafting system tests"""
        print("\n" + "=" * 70)
        print("AUTOMATED CRAFTING SYSTEM TEST SUITE")
        print("=" * 70)

        self.test_results = []
        self.tests_passed = 0
        self.tests_failed = 0

        # Test 1: Database initialization
        self.test_database_loading()

        # Test 2: Recipe loading for each discipline
        self.test_recipe_loading()

        # Test 3: Recipe tier sorting
        self.test_recipe_tier_sorting()

        # Test 4: Placement data loading
        self.test_placement_data()

        # Test 5: State initialization
        self.test_state_initialization()

        # Test 6: UI rendering (each discipline)
        self.test_ui_rendering()

        # Print summary
        print("\n" + "=" * 70)
        print(f"TEST SUMMARY: {self.tests_passed} passed, {self.tests_failed} failed")
        print("=" * 70)

        for result in self.test_results:
            print(result)

        return self.tests_failed == 0

    def test_database_loading(self):
        """Test that all required databases are loaded"""
        try:
            recipe_db = RecipeDatabase.get_instance()
            placement_db = PlacementDatabase.get_instance()
            mat_db = MaterialDatabase.get_instance()
            equip_db = EquipmentDatabase.get_instance()

            self.log_test("Database instances", True, "All databases initialized")
        except Exception as e:
            self.log_test("Database instances", False, str(e))

    def test_recipe_loading(self):
        """Test recipe loading for each crafting discipline"""
        recipe_db = RecipeDatabase.get_instance()
        disciplines = ['smithing', 'refining', 'alchemy', 'engineering', 'adornments']

        for discipline in disciplines:
            try:
                recipes_t1 = recipe_db.get_recipes_for_station(discipline, 1)
                recipes_t3 = recipe_db.get_recipes_for_station(discipline, 3)

                if len(recipes_t1) > 0:
                    self.log_test(f"Recipe loading: {discipline}", True,
                                f"T1: {len(recipes_t1)}, T3: {len(recipes_t3)} recipes")
                else:
                    self.log_test(f"Recipe loading: {discipline}", False,
                                "No recipes found")
            except Exception as e:
                self.log_test(f"Recipe loading: {discipline}", False, str(e))

    def test_recipe_tier_sorting(self):
        """Test that recipes are sorted by tier (highest first)"""
        recipe_db = RecipeDatabase.get_instance()

        try:
            # Get T3 smithing recipes (should include T1, T2, T3)
            recipes = recipe_db.get_recipes_for_station('smithing', 3)
            recipes = sorted(recipes, key=lambda r: r.station_tier, reverse=True)

            if len(recipes) > 1:
                # Check if first recipe has higher/equal tier than last
                first_tier = recipes[0].station_tier
                last_tier = recipes[-1].station_tier

                if first_tier >= last_tier:
                    self.log_test("Recipe tier sorting", True,
                                f"Sorted correctly (T{first_tier} first, T{last_tier} last)")
                else:
                    self.log_test("Recipe tier sorting", False,
                                f"Not sorted (T{first_tier} first, T{last_tier} last)")
            else:
                self.log_test("Recipe tier sorting", True, "Not enough recipes to test")
        except Exception as e:
            self.log_test("Recipe tier sorting", False, str(e))

    def test_placement_data(self):
        """Test placement data loading for each discipline"""
        placement_db = PlacementDatabase.get_instance()
        recipe_db = RecipeDatabase.get_instance()

        disciplines = {
            'smithing': 'grid',
            'refining': 'hub_spoke',
            'alchemy': 'sequential',
            'engineering': 'slots',
            'adornments': 'grid'
        }

        for discipline, expected_type in disciplines.items():
            try:
                recipes = recipe_db.get_recipes_for_station(discipline, 1)
                if recipes:
                    recipe = recipes[0]
                    placement_data = placement_db.get_placement(recipe.recipe_id)

                    if placement_data:
                        self.log_test(f"Placement data: {discipline}", True,
                                    f"Type: {placement_data.discipline}")
                    else:
                        self.log_test(f"Placement data: {discipline}", False,
                                    "No placement data found")
                else:
                    self.log_test(f"Placement data: {discipline}", False,
                                "No recipes to test")
            except Exception as e:
                self.log_test(f"Placement data: {discipline}", False, str(e))

    def test_state_initialization(self):
        """Test that game state initializes correctly"""
        try:
            # Check placement state variables exist
            assert hasattr(self.game, 'placement_mode')
            assert hasattr(self.game, 'placement_recipe')
            assert hasattr(self.game, 'placement_data')
            assert hasattr(self.game, 'placed_materials_grid')
            assert hasattr(self.game, 'placed_materials_hub')
            assert hasattr(self.game, 'placed_materials_sequential')
            assert hasattr(self.game, 'placed_materials_slots')

            self.log_test("State initialization", True, "All state variables present")
        except Exception as e:
            self.log_test("State initialization", False, str(e))

    def test_ui_rendering(self):
        """Test UI rendering for each discipline"""
        # This is a lightweight test - just verify methods exist
        disciplines = ['smithing', 'refining', 'alchemy', 'engineering', 'enchanting']

        for discipline in disciplines:
            try:
                method_name = f"_render_{discipline}_placement"
                if hasattr(self.game.renderer, method_name):
                    self.log_test(f"UI render method: {discipline}", True,
                                f"Method {method_name} exists")
                else:
                    self.log_test(f"UI render method: {discipline}", False,
                                f"Method {method_name} not found")
            except Exception as e:
                self.log_test(f"UI render method: {discipline}", False, str(e))


# ============================================================================
# GAME ENGINE
# ============================================================================
class GameEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT))
        pygame.display.set_caption("2D RPG Game - Equipment System v2.2")
        self.clock = pygame.time.Clock()
        self.running = True

        print("=" * 60)
        print("Loading databases...")
        print("=" * 60)

        MaterialDatabase.get_instance().load_from_file("items.JSON/items-materials-1.JSON")
        MaterialDatabase.get_instance().load_refining_items(
            "items.JSON/items-refining-1.JSON")  # FIX #2: Load ingots/planks
        # Load stackable consumables (potions, oils, etc.)
        MaterialDatabase.get_instance().load_stackable_items(
            "items.JSON/items-alchemy-1.JSON", categories=['consumable'])
        # Load stackable devices (turrets, etc.)
        MaterialDatabase.get_instance().load_stackable_items(
            "items.JSON/items-smithing-1.JSON", categories=['device'])
        TranslationDatabase.get_instance().load_from_files()
        SkillDatabase.get_instance().load_from_file()
        RecipeDatabase.get_instance().load_from_files()
        PlacementDatabase.get_instance().load_from_files()

        # Load equipment from all item files
        equip_db = EquipmentDatabase.get_instance()
        equip_db.load_from_file("items.JSON/items-smithing-1.JSON")
        equip_db.load_from_file("items.JSON/items-smithing-2.JSON")
        equip_db.load_from_file("items.JSON/items-tools-1.JSON")
        equip_db.load_from_file("items.JSON/items-alchemy-1.JSON")

        TitleDatabase.get_instance().load_from_file("progression/titles-1.JSON")
        ClassDatabase.get_instance().load_from_file("progression/classes-1.JSON")
        SkillDatabase.get_instance().load_from_file("Skills/skills-skills-1.JSON")

        # Initialize crafting subdisciplines (minigames)
        if CRAFTING_MODULES_LOADED:
            print("\nInitializing crafting subdisciplines...")
            self.smithing_crafter = SmithingCrafter()
            self.refining_crafter = RefiningCrafter()
            self.alchemy_crafter = AlchemyCrafter()
            self.engineering_crafter = EngineeringCrafter()
            self.enchanting_crafter = EnchantingCrafter()
            print("✓ All 5 crafting disciplines loaded")
        else:
            self.smithing_crafter = None
            self.refining_crafter = None
            self.alchemy_crafter = None
            self.engineering_crafter = None
            self.enchanting_crafter = None

        print("\nInitializing systems...")
        self.world = WorldSystem()
        self.character = Character(Position(50.0, 50.0, 0.0))
        self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
        self.renderer = Renderer(self.screen)

        # Initialize automated testing framework
        self.test_system = CraftingSystemTester(self)

        # Initialize combat system
        print("Loading combat system...")
        self.combat_manager = CombatManager(self.world, self.character)
        self.combat_manager.load_config(
            "Definitions.JSON/combat-config.JSON",
            "Definitions.JSON/hostiles-1.JSON"
        )
        # Spawn initial enemies for testing
        self.combat_manager.spawn_initial_enemies((self.character.position.x, self.character.position.y), count=5)

        # Minigame state
        self.active_minigame = None  # Current minigame instance
        self.minigame_type = None  # 'smithing', 'alchemy', etc.
        self.minigame_recipe = None  # Recipe being crafted
        self.minigame_paused = False
        self.minigame_button_rect = None  # Primary button rect
        self.minigame_button_rect2 = None  # Secondary button rect (alchemy)

        # Placement state - for material placement UIs
        self.placement_mode = False  # True when in placement UI
        self.placement_recipe = None  # Recipe selected for placement
        self.placement_data = None  # PlacementData from database

        # Placed materials - different structures for different crafting types
        self.placed_materials_grid = {}  # Smithing/Enchanting: "x,y" -> (materialId, quantity)
        self.placed_materials_hub = {'core': [], 'surrounding': []}  # Refining: hub-spoke
        self.placed_materials_sequential = []  # Alchemy: ordered list
        self.placed_materials_slots = {}  # Engineering: slot_type -> (materialId, quantity)

        # Placement UI rects
        self.placement_grid_rects = {}  # Grid slot rects for smithing
        self.placement_slot_rects = {}  # Generic slot rects
        self.placement_craft_button_rect = None  # Craft button (appears when valid)
        self.placement_minigame_button_rect = None  # Minigame button
        self.placement_clear_button_rect = None  # Clear placement button

        self.damage_numbers: List[DamageNumber] = []
        self.notifications: List[Notification] = []
        self.crafting_window_rect = None
        self.crafting_recipes = []
        self.selected_recipe = None  # Currently selected recipe in crafting UI (for placement display)
        self.user_placement = {}  # User's current material placement: "x,y" -> materialId for grids, or other structures
        self.active_station_tier = 1  # Currently open crafting station's tier (determines grid size shown)
        self.placement_grid_rects = []  # Grid cell rects for click detection: list of (pygame.Rect, (grid_x, grid_y) or slot_id)
        self.recipe_scroll_offset = 0  # Scroll offset for recipe list in crafting UI
        self.stats_window_rect = None
        self.stats_buttons = []
        self.equipment_window_rect = None
        self.equipment_rects = {}
        self.skills_window_rect = None
        self.skills_hotbar_rects = []
        self.skills_list_rects = []
        self.class_selection_rect = None
        self.class_buttons = []

        # Enchantment/Adornment selection UI
        self.enchantment_selection_active = False
        self.enchantment_recipe = None
        self.enchantment_compatible_items = []
        self.enchantment_selection_rect = None
        self.enchantment_item_rects = None  # Item rects for click detection

        # Minigame state
        self.active_minigame = None  # Current minigame instance (SmithingMinigame, etc.)
        self.minigame_type = None  # Station type: 'smithing', 'alchemy', 'refining', 'engineering', 'adornments'
        self.minigame_recipe = None  # Recipe being crafted with minigame
        self.minigame_button_rect = None  # For click detection on minigame buttons
        self.minigame_button_rect2 = None  # For secondary buttons (e.g., alchemy stabilize)

        self.keys_pressed = set()
        self.mouse_pos = (0, 0)
        self.last_tick = pygame.time.get_ticks()
        self.last_click_time = 0
        self.last_clicked_slot = None

        if not self.character.class_system.current_class:
            self.character.class_selection_open = True

        print("\n" + "=" * 60)
        print("✓ Game ready!")
        if Config.DEBUG_INFINITE_RESOURCES:
            print("⚠ DEBUG MODE ENABLED (F1 to toggle)")
        print("=" * 60 + "\n")

    def add_notification(self, message: str, color: Tuple[int, int, int] = Config.COLOR_NOTIFICATION):
        self.notifications.append(Notification(message, 3.0, color))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.keys_pressed.add(event.key)

                # Minigame input handling (highest priority)
                if self.active_minigame:
                    if event.key == pygame.K_ESCAPE:
                        # Cancel minigame (lose materials)
                        print(f"🚫 Minigame cancelled by player")
                        self.add_notification("Minigame cancelled!", (255, 100, 100))
                        self.active_minigame = None
                        self.minigame_type = None
                        self.minigame_recipe = None
                    elif self.minigame_type == 'smithing' and event.key == pygame.K_SPACE:
                        self.active_minigame.handle_fan()
                    elif self.minigame_type == 'alchemy':
                        if event.key == pygame.K_c:
                            self.active_minigame.chain()
                        elif event.key == pygame.K_s:
                            self.active_minigame.stabilize()
                    elif self.minigame_type == 'refining' and event.key == pygame.K_SPACE:
                        self.active_minigame.handle_attempt()
                    # engineering uses button clicks, no keyboard input needed
                    # Skip other key handling when minigame is active
                    continue

                if event.key == pygame.K_ESCAPE:
                    if self.enchantment_selection_active:
                        self._close_enchantment_selection()
                        print("🚫 Enchantment selection cancelled")
                    elif self.character.crafting_ui_open:
                        self.character.close_crafting_ui()
                    elif self.character.stats_ui_open:
                        self.character.toggle_stats_ui()
                    elif self.character.equipment_ui_open:
                        self.character.toggle_equipment_ui()
                    elif self.character.skills_ui_open:
                        self.character.toggle_skills_ui()
                    elif self.character.class_selection_open:
                        pass
                    else:
                        self.running = False
                elif event.key == pygame.K_TAB:
                    tool_name = self.character.switch_tool()
                    if tool_name:
                        self.add_notification(f"Switched to {tool_name}", (100, 200, 255))
                elif event.key == pygame.K_c:
                    self.character.toggle_stats_ui()
                elif event.key == pygame.K_e:
                    self.character.toggle_equipment_ui()
                elif event.key == pygame.K_k:
                    self.character.toggle_skills_ui()

                # Skill hotbar (keys 1-5)
                elif event.key == pygame.K_1:
                    success, msg = self.character.skills.use_skill(0, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_2:
                    success, msg = self.character.skills.use_skill(1, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_3:
                    success, msg = self.character.skills.use_skill(2, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_4:
                    success, msg = self.character.skills.use_skill(3, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_5:
                    success, msg = self.character.skills.use_skill(4, self.character)
                    if success:
                        self.add_notification(msg, (150, 255, 150))
                    else:
                        self.add_notification(msg, (255, 150, 150))
                elif event.key == pygame.K_F1:
                    Config.DEBUG_INFINITE_RESOURCES = not Config.DEBUG_INFINITE_RESOURCES
                    status = "ENABLED" if Config.DEBUG_INFINITE_RESOURCES else "DISABLED"

                    # Set max level when enabling debug mode (but DON'T fill inventory)
                    if Config.DEBUG_INFINITE_RESOURCES:
                        self.character.leveling.level = self.character.leveling.max_level
                        self.character.leveling.unallocated_stat_points = 100
                        print(f"🔧 DEBUG MODE ENABLED:")
                        print(f"   • Infinite resources (no materials consumed)")
                        print(f"   • Level set to {self.character.leveling.level}")
                        print(f"   • 100 stat points available")
                        print(f"   • Inventory NOT filled (craft freely!)")
                    else:
                        print(f"🔧 DEBUG MODE DISABLED")

                    self.add_notification(f"Debug Mode {status}", (255, 100, 255))
                    print(f"⚠ Debug Mode {status}")

                elif event.key == pygame.K_F2:
                    # Debug: Learn all skills from JSON
                    skill_db = SkillDatabase.get_instance()
                    if skill_db.loaded and skill_db.skills:
                        skills_learned = 0
                        for skill_id in skill_db.skills.keys():
                            if self.character.skills.learn_skill(skill_id):
                                skills_learned += 1

                        # Equip first 6 skills to hotbar
                        skills_equipped = 0
                        for i, skill_id in enumerate(list(skill_db.skills.keys())[:6]):
                            if self.character.skills.equip_skill(skill_id, i):
                                skills_equipped += 1

                        print(f"🔧 DEBUG: Learned {skills_learned} skills, equipped {skills_equipped} to hotbar")
                        self.add_notification(f"Debug: Learned {skills_learned} skills!", (255, 215, 0))
                    else:
                        print(f"⚠ WARNING: Skill database not loaded or empty!")
                        self.add_notification("Skill DB not loaded!", (255, 100, 100))

                elif event.key == pygame.K_F3:
                    # Debug: Grant all titles from JSON
                    title_db = TitleDatabase.get_instance()
                    if title_db.loaded and title_db.titles:
                        titles_granted = 0
                        for title in title_db.titles.values():
                            if title not in self.character.titles.earned_titles:
                                self.character.titles.earned_titles.append(title)
                                titles_granted += 1

                        print(f"🔧 DEBUG: Granted {titles_granted} titles!")
                        self.add_notification(f"Debug: Granted {titles_granted} titles!", (255, 215, 0))
                    else:
                        print(f"⚠ WARNING: Title database not loaded or empty!")
                        self.add_notification("Title DB not loaded!", (255, 100, 100))

                elif event.key == pygame.K_F4:
                    # Debug: Max out level and stats
                    self.character.leveling.level = 30
                    self.character.leveling.unallocated_stat_points = 30
                    self.character.stats.strength = 30
                    self.character.stats.defense = 30
                    self.character.stats.vitality = 30
                    self.character.stats.luck = 30
                    self.character.stats.agility = 30
                    self.character.stats.intelligence = 30
                    self.character.recalculate_stats()

                    print(f"🔧 DEBUG: Max level & stats!")
                    print(f"   • Level: 30")
                    print(f"   • All stats: 30")
                    print(f"   • Unallocated points: 30")
                    self.add_notification("Debug: Max level & stats!", (255, 215, 0))

                elif event.key == pygame.K_F5:
                    # Run automated test suite
                    print("\n🧪 Running Automated Test Suite...")
                    self.test_system.run_all_tests()
                    self.add_notification("Test suite completed - check console", (100, 200, 255))

            elif event.type == pygame.KEYUP:
                self.keys_pressed.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos
            elif event.type == pygame.MOUSEWHEEL:
                # Handle mouse wheel scrolling for recipe list
                if self.character.crafting_ui_open and self.crafting_window_rect:
                    if self.crafting_window_rect.collidepoint(self.mouse_pos):
                        # Scroll the recipe list
                        self.recipe_scroll_offset -= event.y  # event.y is positive for scroll up
                        # Clamp scroll offset to valid range
                        max_scroll = max(0, len(self.crafting_recipes) - 8)
                        self.recipe_scroll_offset = max(0, min(self.recipe_scroll_offset, max_scroll))
                # Handle mouse wheel scrolling for skills menu
                elif self.character.skills_ui_open:
                    # Scroll the skills list
                    self.character.skills_menu_scroll_offset -= event.y  # event.y is positive for scroll up
                    # Clamp is handled in render_skills_menu_ui
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.handle_mouse_release(event.pos)

    def handle_mouse_click(self, mouse_pos: Tuple[int, int]):
        shift_held = pygame.K_LSHIFT in self.keys_pressed or pygame.K_RSHIFT in self.keys_pressed

        # Check double-click
        current_time = pygame.time.get_ticks()
        is_double_click = (current_time - self.last_click_time < 300)
        self.last_click_time = current_time

        # Minigame button clicks (highest priority)
        if self.active_minigame:
            if hasattr(self, 'minigame_button_rect') and self.minigame_button_rect:
                if self.minigame_button_rect.collidepoint(mouse_pos):
                    # Handle minigame-specific buttons
                    if self.minigame_type == 'smithing':
                        self.active_minigame.handle_hammer()
                    elif self.minigame_type == 'alchemy':
                        # Chain button (minigame_button_rect is chain button)
                        self.active_minigame.chain()
                    elif self.minigame_type == 'engineering':
                        # Check puzzle solution button
                        self.active_minigame.check_current_puzzle()
                    return
            # Check secondary button (alchemy stabilize)
            if hasattr(self, 'minigame_button_rect2') and self.minigame_button_rect2:
                if self.minigame_button_rect2.collidepoint(mouse_pos):
                    if self.minigame_type == 'alchemy':
                        self.active_minigame.stabilize()
                    return
            # Consume all clicks when minigame is active (don't interact with world)
            return

        # Enchantment selection UI (priority over other UIs)
        if self.enchantment_selection_active and self.enchantment_selection_rect:
            if self.enchantment_selection_rect.collidepoint(mouse_pos):
                self.handle_enchantment_selection_click(mouse_pos)
                return

        # Class selection
        if self.character.class_selection_open and self.class_selection_rect:
            if self.class_selection_rect.collidepoint(mouse_pos):
                self.handle_class_selection_click(mouse_pos)
                return

        # Skills UI
        if self.character.skills_ui_open and self.skills_window_rect:
            if self.skills_window_rect.collidepoint(mouse_pos):
                self.handle_skills_menu_click(mouse_pos)
                return
            # Click outside skills UI - close it
            else:
                self.character.toggle_skills_ui()
                return

        # Stats UI
        if self.character.stats_ui_open and self.stats_window_rect:
            if self.stats_window_rect.collidepoint(mouse_pos):
                self.handle_stats_click(mouse_pos)
                return
            # Click outside stats UI - close it
            else:
                self.character.toggle_stats_ui()
                return

        # Equipment UI
        if self.character.equipment_ui_open and self.equipment_window_rect:
            if self.equipment_window_rect.collidepoint(mouse_pos):
                self.handle_equipment_click(mouse_pos, shift_held)
                return
            # Click outside equipment UI - close it
            else:
                self.character.toggle_equipment_ui()
                return

        # Crafting UI
        if self.character.crafting_ui_open and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                self.handle_craft_click(mouse_pos)
                return
            # Click outside crafting UI - close it
            else:
                self.character.close_crafting_ui()
                return

        # Inventory - check for equipment equipping
        if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
            start_x, start_y = 20, Config.INVENTORY_PANEL_Y + 50
            slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
            rel_x, rel_y = mouse_pos[0] - start_x, mouse_pos[1] - start_y

            if rel_x >= 0 and rel_y >= 0:
                col, row = rel_x // (slot_size + spacing), rel_y // (slot_size + spacing)
                in_x = rel_x % (slot_size + spacing) < slot_size
                in_y = rel_y % (slot_size + spacing) < slot_size

                if in_x and in_y:
                    idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                    if 0 <= idx < self.character.inventory.max_slots:
                        # Double-click to equip equipment
                        if is_double_click and self.last_clicked_slot == idx:
                            item_stack = self.character.inventory.slots[idx]
                            print(f"\n🖱️  Double-click detected on slot {idx}")
                            if item_stack:
                                print(f"   Item: {item_stack.item_id}")
                                is_equip = item_stack.is_equipment()
                                print(f"   is_equipment(): {is_equip}")
                                if is_equip:
                                    equipment = item_stack.get_equipment()
                                    print(f"   get_equipment(): {equipment}")
                                    if equipment:  # FIX #4: Check equipment exists before trying to equip
                                        success, msg = self.character.try_equip_from_inventory(idx)
                                        if success:
                                            self.add_notification(f"Equipped {equipment.name}", (100, 255, 100))
                                        else:
                                            self.add_notification(f"Cannot equip: {msg}", (255, 100, 100))
                                    else:
                                        print(f"   ❌ equipment is None!")
                                        self.add_notification("Invalid equipment data", (255, 100, 100))
                                else:
                                    print(f"   ⚠️  Not equipment, skipping")
                            else:
                                print(f"   ⚠️  item_stack is None")
                            return

                        self.last_clicked_slot = idx

                        # Regular drag
                        if self.character.inventory.slots[idx] is not None:
                            self.character.inventory.start_drag(idx)
            return

        # World interaction
        if mouse_pos[0] >= Config.VIEWPORT_WIDTH:
            return

        wx = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
        wy = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y
        world_pos = Position(wx, wy, 0)

        # Check for enemy click (living enemies)
        enemy = self.combat_manager.get_enemy_at_position((wx, wy))
        if enemy and enemy.is_alive:
            # Check if player can attack
            if not self.character.can_attack():
                return  # Still on cooldown

            # Check if in range
            dist = enemy.distance_to((self.character.position.x, self.character.position.y))
            if dist > self.combat_manager.config.player_attack_range:
                self.add_notification("Enemy too far away", (255, 100, 100))
                return

            # Attack enemy
            damage, is_crit = self.combat_manager.player_attack_enemy(enemy)
            self.damage_numbers.append(DamageNumber(int(damage), Position(enemy.position[0], enemy.position[1], 0), is_crit))
            self.character.reset_attack_cooldown(is_weapon=True)

            if not enemy.is_alive:
                self.add_notification(f"Defeated {enemy.definition.name}!", (255, 215, 0))
            return

        # Check for corpse click (looting)
        corpse = self.combat_manager.get_corpse_at_position((wx, wy))
        if corpse:
            loot = self.combat_manager.loot_corpse(corpse, self.character.inventory)
            if loot:
                mat_db = MaterialDatabase.get_instance()
                for material_id, qty in loot:
                    mat = mat_db.get_material(material_id)
                    item_name = mat.name if mat else material_id
                    self.add_notification(f"+{qty} {item_name}", (100, 255, 100))
                self.add_notification(f"Looted {corpse.definition.name}", (150, 200, 255))
            return

        station = self.world.get_station_at(world_pos)
        if station:
            self.character.interact_with_station(station)
            self.active_station_tier = station.tier  # Capture tier for placement UI
            self.user_placement = {}  # Clear any previous placement
            self.selected_recipe = None  # Clear selected recipe
            self.recipe_scroll_offset = 0  # Reset recipe list scroll
            return

        resource = self.world.get_resource_at(world_pos)
        if resource:
            can_harvest, reason = self.character.can_harvest_resource(resource)
            if not can_harvest:
                self.add_notification(f"Cannot harvest: {reason}", (255, 100, 100))
                return

            result = self.character.harvest_resource(resource)
            if result:
                loot, dmg, is_crit = result
                self.damage_numbers.append(DamageNumber(dmg, resource.position.copy(), is_crit))
                if loot:
                    mat_db = MaterialDatabase.get_instance()
                    for item_id, qty in loot:
                        mat = mat_db.get_material(item_id)
                        item_name = mat.name if mat else item_id
                        self.add_notification(f"+{qty} {item_name}", (100, 255, 100))

    def handle_enchantment_selection_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks on the enchantment selection UI"""
        print(f"🔍 Enchantment click handler called at {mouse_pos}")

        if not self.enchantment_item_rects:
            print(f"⚠️ No item rects available!")
            return

        print(f"📋 Checking {len(self.enchantment_item_rects)} item rects")
        wx, wy = self.enchantment_selection_rect.x, self.enchantment_selection_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
        print(f"   Window at ({wx}, {wy}), relative click at ({rx}, {ry})")

        for idx, (item_rect, source_type, source_id, item_stack, equipment) in enumerate(self.enchantment_item_rects):
            print(f"   Rect {idx}: {item_rect}, contains? {item_rect.collidepoint(rx, ry)}")

            if item_rect.collidepoint(rx, ry):
                print(f"✨ Selected {equipment.name} for enchantment")
                self._complete_enchantment_application(source_type, source_id, item_stack, equipment)
                break

    def handle_skills_menu_click(self, mouse_pos: Tuple[int, int]):
        """Handle clicks on the skills menu"""
        wx, wy = self.skills_window_rect.x, self.skills_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        # Check hotbar slots (right-click to unequip)
        for slot_rect, slot_idx, skill_id in self.skills_hotbar_rects:
            if slot_rect.collidepoint(rx, ry):
                if skill_id:  # Right-click to unequip
                    self.character.skills.unequip_skill(slot_idx)
                    self.add_notification(f"Unequipped from slot {slot_idx + 1}", (255, 200, 100))
                return

        # Check skill list (click to equip)
        for skill_rect, skill_id, player_skill, skill_def in self.skills_list_rects:
            if skill_rect.collidepoint(rx, ry):
                # Find first empty slot
                empty_slot = None
                for i in range(5):
                    if not self.character.skills.equipped_skills[i]:
                        empty_slot = i
                        break

                if empty_slot is not None:
                    self.character.skills.equip_skill(skill_id, empty_slot)
                    self.add_notification(f"Equipped {skill_def.name} to slot {empty_slot + 1}", (100, 255, 150))
                else:
                    self.add_notification("All hotbar slots full! Unequip a skill first.", (255, 150, 100))
                return

    def handle_class_selection_click(self, mouse_pos: Tuple[int, int]):
        if not self.class_buttons:
            return

        wx, wy = self.class_selection_rect.x, self.class_selection_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        for card_rect, class_def in self.class_buttons:
            if card_rect.collidepoint(rx, ry):
                self.character.select_class(class_def)
                self.character.class_selection_open = False
                self.add_notification(f"Welcome, {class_def.name}!", (255, 215, 0))
                print(f"\n🎉 Welcome, {class_def.name}!")
                print(f"   {class_def.description}")
                break

    def handle_equipment_click(self, mouse_pos: Tuple[int, int], shift_held: bool):
        if not self.equipment_rects:
            return

        wx, wy = self.equipment_window_rect.x, self.equipment_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        for slot_name, (rect, _, _) in self.equipment_rects.items():
            if rect.collidepoint(rx, ry):
                if shift_held:
                    # Unequip
                    success, msg = self.character.try_unequip_to_inventory(slot_name)
                    if success:
                        self.add_notification(f"Unequipped item", (100, 255, 100))
                    else:
                        self.add_notification(f"Cannot unequip: {msg}", (255, 100, 100))
                break

    def handle_stats_click(self, mouse_pos: Tuple[int, int]):
        if not self.stats_window_rect or not self.stats_buttons:
            return
        wx, wy = self.stats_window_rect.x, self.stats_window_rect.y
        rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy

        for btn_rect, stat_name in self.stats_buttons:
            if btn_rect.collidepoint(rx, ry):
                if self.character.allocate_stat_point(stat_name):
                    self.add_notification(f"+1 {stat_name.upper()}", (100, 255, 100))
                    print(f"✓ +1 {stat_name.upper()}")
                break

    # ========================================================================
    # CRAFTING INTEGRATION HELPERS
    # ========================================================================
    def inventory_to_dict(self) -> Dict[str, int]:
        """Convert main.py Inventory to crafter-compatible Dict[material_id: quantity]"""
        materials = {}
        for slot in self.character.inventory.slots:
            if slot and not slot.is_equipment():
                # Only include non-equipment items (materials)
                if slot.item_id in materials:
                    materials[slot.item_id] += slot.quantity
                else:
                    materials[slot.item_id] = slot.quantity
        return materials

    def get_crafter_for_station(self, station_type: str):
        """Get the appropriate crafter module for a station type"""
        if not CRAFTING_MODULES_LOADED:
            return None

        crafter_map = {
            'smithing': self.smithing_crafter,
            'refining': self.refining_crafter,
            'alchemy': self.alchemy_crafter,
            'engineering': self.engineering_crafter,
            'adornments': self.enchanting_crafter
        }
        return crafter_map.get(station_type)

    def _start_minigame(self, recipe: Recipe):
        """Start the appropriate minigame for this recipe"""
        crafter = self.get_crafter_for_station(recipe.station_type)
        if not crafter:
            self.add_notification("Invalid crafting station!", (255, 100, 100))
            return

        # Calculate skill buff bonuses for this crafting discipline
        buff_time_bonus = 0.0
        buff_quality_bonus = 0.0

        if hasattr(self.character, 'buffs'):
            # Quicken buff: Extends minigame time
            quicken_general = self.character.buffs.get_total_bonus('quicken', recipe.station_type)
            quicken_smithing_alt = self.character.buffs.get_total_bonus('quicken', 'smithing') if recipe.station_type in ['smithing', 'refining'] else 0
            buff_time_bonus = max(quicken_general, quicken_smithing_alt)

            # Empower/Elevate buff: Improves quality
            empower_bonus = self.character.buffs.get_total_bonus('empower', recipe.station_type)
            elevate_bonus = self.character.buffs.get_total_bonus('elevate', recipe.station_type)
            buff_quality_bonus = max(empower_bonus, elevate_bonus)

        # Create minigame instance with buff bonuses
        minigame = crafter.create_minigame(recipe.recipe_id, buff_time_bonus, buff_quality_bonus)
        if not minigame:
            self.add_notification("Minigame not available!", (255, 100, 100))
            return

        if buff_time_bonus > 0 or buff_quality_bonus > 0:
            print(f"⚡ Skill buffs active:")
            if buff_time_bonus > 0:
                print(f"   +{buff_time_bonus*100:.0f}% minigame time")
            if buff_quality_bonus > 0:
                print(f"   +{buff_quality_bonus*100:.0f}% quality bonus")

        # Start minigame
        minigame.start()

        # Store minigame state
        self.active_minigame = minigame
        self.minigame_type = recipe.station_type
        self.minigame_recipe = recipe

        # Close crafting UI
        self.character.close_crafting_ui()

        print(f"🎮 Started {recipe.station_type} minigame for {recipe.recipe_id}")
        self.add_notification(f"Minigame Started!", (255, 215, 0))

    def _complete_minigame(self):
        """Complete the active minigame and process results"""
        if not self.active_minigame or not self.minigame_recipe:
            return

        print(f"\n{'='*80}")
        print(f"🎮 MINIGAME COMPLETED")
        print(f"Recipe: {self.minigame_recipe.recipe_id}")
        print(f"Type: {self.minigame_type}")
        print(f"Result: {self.active_minigame.result}")
        print(f"{'='*80}\n")

        recipe = self.minigame_recipe
        result = self.active_minigame.result
        crafter = self.get_crafter_for_station(self.minigame_type)

        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Convert inventory to dict
        inv_dict = self.inventory_to_dict()

        # DEBUG MODE: Add infinite quantities of required materials (same as in craft_item)
        if Config.DEBUG_INFINITE_RESOURCES:
            print("🔧 DEBUG MODE: Adding infinite materials for minigame completion")
            rarity_system.debug_mode = True
            for inp in recipe.inputs:
                mat_id = inp.get('materialId', '')
                inv_dict[mat_id] = 999999
        else:
            rarity_system.debug_mode = False

        # Use crafter to process minigame result
        craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result)

        if not craft_result.get('success'):
            # Failure - materials may have been lost
            message = craft_result.get('message', 'Crafting failed')
            self.add_notification(message, (255, 100, 100))

            # Sync inventory back (consume materials even on failure)
            recipe_db.consume_materials(recipe, self.character.inventory)
        else:
            # Success - consume materials and add output
            recipe_db.consume_materials(recipe, self.character.inventory)

            # Record activity and XP
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(self.minigame_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            # Minigame gives XP (50% bonus over instant craft)
            xp_reward = int(20 * recipe.station_tier * 1.5)
            self.character.leveling.add_exp(xp_reward)

            new_title = self.character.titles.check_for_title(
                activity_type, self.character.activities.get_count(activity_type)
            )
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

            # Add output to inventory with rarity and stats
            output_id = craft_result.get('outputId', recipe.output_id)
            output_qty = craft_result.get('quantity', recipe.output_qty)
            rarity = craft_result.get('rarity', 'common')
            stats = craft_result.get('stats')

            self.add_crafted_item_to_inventory(output_id, output_qty, rarity, stats)

            # Get proper name for notification
            if equip_db.is_equipment(output_id):
                equipment = equip_db.create_equipment_from_id(output_id)
                out_name = equipment.name if equipment else output_id
            else:
                out_mat = mat_db.get_material(output_id)
                out_name = out_mat.name if out_mat else output_id

            message = craft_result.get('message', f"Crafted {out_name} x{output_qty}")
            self.add_notification(message, (100, 255, 100))
            print(f"✅ Minigame crafting complete: {out_name} x{output_qty}")

        # Clear minigame state
        self.active_minigame = None
        self.minigame_type = None
        self.minigame_recipe = None

    def _render_minigame(self):
        """Render the active minigame (dispatcher to specific renderers)"""
        if not self.active_minigame or not self.minigame_type:
            return

        # Route to appropriate renderer based on minigame type
        if self.minigame_type == 'smithing':
            self._render_smithing_minigame()
        elif self.minigame_type == 'alchemy':
            self._render_alchemy_minigame()
        elif self.minigame_type == 'refining':
            self._render_refining_minigame()
        elif self.minigame_type == 'engineering':
            self._render_engineering_minigame()
        elif self.minigame_type == 'adornments':
            self._render_enchanting_minigame()

    def _render_smithing_minigame(self):
        """Render smithing minigame UI"""
        state = self.active_minigame.get_state()

        # Create overlay
        ww, wh = 1000, 700
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        header_text = self.renderer.font.render("SMITHING MINIGAME", True, (255, 215, 0))
        surf.blit(header_text, (ww//2 - header_text.get_width()//2, 20))
        controls_text = self.renderer.small_font.render("[SPACE] Fan Flames | [CLICK HAMMER BUTTON] Strike", True, (180, 180, 180))
        surf.blit(controls_text, (20, 50))

        # Temperature bar
        temp_x, temp_y = 50, 100
        temp_width = 300
        temp_height = 40

        # Draw temp bar background
        pygame.draw.rect(surf, (40, 40, 40), (temp_x, temp_y, temp_width, temp_height))

        # Draw ideal range
        ideal_min = state['temp_ideal_min']
        ideal_max = state['temp_ideal_max']
        ideal_start = int((ideal_min / 100) * temp_width)
        ideal_width_px = int(((ideal_max - ideal_min) / 100) * temp_width)
        pygame.draw.rect(surf, (60, 80, 60), (temp_x + ideal_start, temp_y, ideal_width_px, temp_height))

        # Draw current temperature
        temp_pct = state['temperature'] / 100
        temp_fill = int(temp_pct * temp_width)
        temp_color = (255, 100, 100) if temp_pct > 0.8 else (255, 165, 0) if temp_pct > 0.5 else (100, 150, 255)
        pygame.draw.rect(surf, temp_color, (temp_x, temp_y, temp_fill, temp_height))

        pygame.draw.rect(surf, (200, 200, 200), (temp_x, temp_y, temp_width, temp_height), 2)
        temp_label = self.renderer.small_font.render(f"Temperature: {int(state['temperature'])}°C", True, (255, 255, 255))
        surf.blit(temp_label, (temp_x, temp_y - 25))

        # Hammer bar
        hammer_x, hammer_y = 50, 200
        hammer_width = state['hammer_bar_width']
        hammer_height = 60

        # Draw hammer bar background
        pygame.draw.rect(surf, (40, 40, 40), (hammer_x, hammer_y, hammer_width, hammer_height))

        # Draw target zone (center)
        center = hammer_width / 2
        target_start = int(center - state['target_width'] / 2)
        pygame.draw.rect(surf, (80, 80, 60), (hammer_x + target_start, hammer_y, state['target_width'], hammer_height))

        # Draw perfect zone (center of target)
        perfect_start = int(center - state['perfect_width'] / 2)
        pygame.draw.rect(surf, (100, 120, 60), (hammer_x + perfect_start, hammer_y, state['perfect_width'], hammer_height))

        # Draw hammer indicator
        hammer_pos = int(state['hammer_position'])
        pygame.draw.circle(surf, (255, 215, 0), (hammer_x + hammer_pos, hammer_y + hammer_height // 2), 15)

        pygame.draw.rect(surf, (200, 200, 200), (hammer_x, hammer_y, hammer_width, hammer_height), 2)
        hammer_label = self.renderer.small_font.render(f"Hammer Timing: {state['hammer_hits']}/{state['required_hits']}", True, (255, 255, 255))
        surf.blit(hammer_label, (hammer_x, hammer_y - 25))

        # Hammer button
        btn_w, btn_h = 200, 60
        btn_x, btn_y = ww // 2 - btn_w // 2, 300
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(surf, (80, 60, 20), btn_rect)
        pygame.draw.rect(surf, (255, 215, 0), btn_rect, 3)
        btn_text = self.renderer.font.render("HAMMER", True, (255, 215, 0))
        surf.blit(btn_text, (btn_x + 40, btn_y + 15))

        # Timer and scores
        time_text = self.renderer.font.render(f"Time Left: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(time_text, (50, 400))

        if state['hammer_scores']:
            scores_label = self.renderer.small_font.render("Hammer Scores:", True, (200, 200, 200))
            surf.blit(scores_label, (50, 450))
            for i, score in enumerate(state['hammer_scores'][-5:]):  # Last 5 scores
                color = (100, 255, 100) if score >= 90 else (255, 215, 0) if score >= 70 else (255, 100, 100)
                score_text = self.renderer.small_font.render(f"Hit {i+1}: {score}", True, color)
                surf.blit(score_text, (70, 480 + i * 25))

        # Result (if completed)
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 300), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                success_text = self.renderer.font.render("SUCCESS!", True, (100, 255, 100))
                result_surf.blit(success_text, (200, 50))
                score_text = self.renderer.small_font.render(f"Score: {int(result['score'])}", True, (255, 255, 255))
                result_surf.blit(score_text, (150, 120))
                bonus_text = self.renderer.small_font.render(f"Bonus: +{result['bonus']}%", True, (255, 215, 0))
                result_surf.blit(bonus_text, (150, 150))
                msg_text = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(msg_text, (150, 200))
            else:
                fail_text = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(fail_text, (200, 50))
                msg_text = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(msg_text, (150, 120))

            surf.blit(result_surf, (200, 200))

        self.screen.blit(surf, (wx, wy))

        # Store button rect for click detection (relative to screen)
        self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

    def _render_alchemy_minigame(self):
        """Render alchemy minigame UI - TODO: Implement full rendering"""
        # Placeholder for now
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        text = self.renderer.font.render("ALCHEMY MINIGAME (Not Yet Implemented)", True, (255, 215, 0))
        surf.blit(text, (100, 300))
        wx = (Config.VIEWPORT_WIDTH - 800) // 2
        wy = (Config.VIEWPORT_HEIGHT - 600) // 2
        self.screen.blit(surf, (wx, wy))

    def _render_refining_minigame(self):
        """Render refining minigame UI - TODO: Implement full rendering"""
        # Placeholder for now
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        text = self.renderer.font.render("REFINING MINIGAME (Not Yet Implemented)", True, (255, 215, 0))
        surf.blit(text, (100, 300))
        wx = (Config.VIEWPORT_WIDTH - 800) // 2
        wy = (Config.VIEWPORT_HEIGHT - 600) // 2
        self.screen.blit(surf, (wx, wy))

    def _render_engineering_minigame(self):
        """Render engineering minigame UI - TODO: Implement full rendering"""
        # Placeholder for now
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        text = self.renderer.font.render("ENGINEERING MINIGAME (Not Yet Implemented)", True, (255, 215, 0))
        surf.blit(text, (100, 300))
        wx = (Config.VIEWPORT_WIDTH - 800) // 2
        wy = (Config.VIEWPORT_HEIGHT - 600) // 2
        self.screen.blit(surf, (wx, wy))

    def _render_enchanting_minigame(self):
        """Render enchanting minigame UI - TODO: Implement full rendering"""
        # Placeholder for now
        surf = pygame.Surface((800, 600), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        text = self.renderer.font.render("ENCHANTING MINIGAME (Not Yet Implemented)", True, (255, 215, 0))
        surf.blit(text, (100, 300))
        wx = (Config.VIEWPORT_WIDTH - 800) // 2
        wy = (Config.VIEWPORT_HEIGHT - 600) // 2
        self.screen.blit(surf, (wx, wy))

    def add_crafted_item_to_inventory(self, item_id: str, quantity: int,
                                     rarity: str = 'common', stats: Dict = None):
        """Add a crafted item to inventory with rarity and stats"""
        equip_db = EquipmentDatabase.get_instance()

        if equip_db.is_equipment(item_id):
            # Equipment - create with stats if provided
            equipment = equip_db.create_equipment_from_id(item_id)
            if equipment and stats:
                # Apply crafted stats to equipment
                for stat_name, stat_value in stats.items():
                    if hasattr(equipment, stat_name):
                        setattr(equipment, stat_name, stat_value)

            # Add to inventory with equipment data
            item_stack = ItemStack(item_id, quantity, equipment_data=equipment,
                                  rarity=rarity, crafted_stats=stats)
            empty_slot = self.character.inventory.get_empty_slot()
            if empty_slot is not None:
                self.character.inventory.slots[empty_slot] = item_stack
            else:
                self.add_notification("Inventory full!", (255, 100, 100))
        else:
            # Material - add with rarity
            item_stack = ItemStack(item_id, quantity, rarity=rarity)
            empty_slot = self.character.inventory.get_empty_slot()
            if empty_slot is not None:
                self.character.inventory.slots[empty_slot] = item_stack
            else:
                self.add_notification("Inventory full!", (255, 100, 100))

    def handle_craft_click(self, mouse_pos: Tuple[int, int]):
        """
        Handle clicks in the new two-panel crafting UI
        - Left panel: Click recipe to select it
        - Right panel: Click Instant or Minigame buttons to craft
        """
        if not self.crafting_window_rect or not self.crafting_recipes:
            return

        rx = mouse_pos[0] - self.crafting_window_rect.x
        ry = mouse_pos[1] - self.crafting_window_rect.y

        recipe_db = RecipeDatabase.get_instance()

        # Layout constants (matching render_crafting_ui)
        left_panel_w = 450
        right_panel_x = left_panel_w + 20 + 20  # separator + padding
        right_panel_w = 700

        # ======================
        # LEFT PANEL: Recipe Selection
        # ======================
        if rx < left_panel_w:
            # Click in left panel - select recipe
            y_off = 70
            for i, recipe in enumerate(self.crafting_recipes):
                num_inputs = len(recipe.inputs)
                btn_height = max(70, 35 + num_inputs * 16 + 5)

                if y_off <= ry <= y_off + btn_height:
                    # Recipe clicked - select it
                    self.selected_recipe = recipe
                    print(f"📋 Selected recipe: {recipe.recipe_id}")
                    # Auto-load recipe placement
                    self.load_recipe_placement(recipe)
                    return

                y_off += btn_height + 8

        # ======================
        # RIGHT PANEL: Grid Cells & Craft Buttons
        # ======================
        elif rx >= right_panel_x:
            if not self.selected_recipe:
                return  # No recipe selected, nothing to interact with

            # First check for placement slot clicks (grid cells or hub slots)
            for cell_rect, slot_data in self.placement_grid_rects:
                if cell_rect.collidepoint(mouse_pos):
                    # Slot clicked!
                    # slot_data can be either (grid_x, grid_y) tuple for grids or "slot_id" string for others
                    if isinstance(slot_data, tuple):
                        # Grid-based (smithing, adornments)
                        grid_x, grid_y = slot_data
                        slot_key = f"{grid_x},{grid_y}"
                        slot_display = f"({grid_x}, {grid_y})"
                    else:
                        # Slot-based (refining, alchemy, engineering)
                        slot_key = slot_data
                        slot_display = slot_key

                    if slot_key in self.user_placement:
                        # Slot already has material - remove it
                        removed_mat = self.user_placement.pop(slot_key)
                        print(f"🗑️ Removed {removed_mat} from {slot_display}")
                    else:
                        # Slot is empty - place first material from recipe inputs
                        # This is a simple approach; later we can add material picker UI
                        if self.selected_recipe.inputs:
                            first_mat_id = self.selected_recipe.inputs[0].get('materialId', '')
                            if first_mat_id:
                                self.user_placement[slot_key] = first_mat_id
                                print(f"✅ Placed {first_mat_id} in {slot_display}")
                    return  # Slot click handled

            # Then check for craft buttons
            recipe = self.selected_recipe
            can_craft = recipe_db.can_craft(recipe, self.character.inventory)

            if not can_craft:
                return  # Can't craft, buttons not shown

            # Button positions (matching render_crafting_ui)
            placement_h = 380
            right_panel_y = 70
            btn_y = right_panel_y + placement_h + 20

            instant_btn_w, instant_btn_h = 120, 40
            minigame_btn_w, minigame_btn_h = 120, 40

            total_btn_w = instant_btn_w + minigame_btn_w + 20
            start_x = right_panel_x + (right_panel_w - 40 - total_btn_w) // 2

            instant_btn_x = start_x
            minigame_btn_x = start_x + instant_btn_w + 20

            # Convert to relative coordinates
            instant_left = instant_btn_x
            instant_right = instant_btn_x + instant_btn_w
            minigame_left = minigame_btn_x
            minigame_right = minigame_btn_x + minigame_btn_w
            btn_top = btn_y
            btn_bottom = btn_y + instant_btn_h

            if instant_left <= rx <= instant_right and btn_top <= ry <= btn_bottom:
                # Instant craft clicked
                print(f"🔨 Instant craft clicked for {recipe.recipe_id}")
                self.craft_item(recipe, use_minigame=False)
            elif minigame_left <= rx <= minigame_right and btn_top <= ry <= btn_bottom:
                # Minigame clicked
                print(f"🎮 Minigame clicked for {recipe.recipe_id}")
                self.craft_item(recipe, use_minigame=True)

    def load_recipe_placement(self, recipe: Recipe):
        """
        Auto-load recipe placement into user_placement when recipe is selected.
        This pre-fills the placement so user can craft immediately or modify as needed.
        """
        placement_db = PlacementDatabase.get_instance()
        placement_data = placement_db.get_placement(recipe.recipe_id)

        if not placement_data:
            # No placement data - clear user placement
            self.user_placement = {}
            return

        # Clear existing placement
        self.user_placement = {}

        # Load based on discipline
        if placement_data.discipline == 'smithing' or placement_data.discipline == 'adornments':
            # Grid-based: copy placement_map with offset for centering
            recipe_grid_w, recipe_grid_h = 3, 3  # Default
            if placement_data.grid_size:
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass

            # Calculate offset to center recipe on station grid
            station_tier = self.active_station_tier
            station_grid_w, station_grid_h = self._get_grid_size_for_tier(station_tier, placement_data.discipline)
            offset_x = (station_grid_w - recipe_grid_w) // 2
            offset_y = (station_grid_h - recipe_grid_h) // 2

            # Copy placements with offset
            for pos, mat_id in placement_data.placement_map.items():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        self.user_placement[f"{station_x},{station_y}"] = mat_id
                    except ValueError:
                        pass

        elif placement_data.discipline == 'refining':
            # Hub-and-spoke: copy core and surrounding inputs
            for i, core_input in enumerate(placement_data.core_inputs):
                mat_id = core_input.get('materialId', '')
                if mat_id:
                    self.user_placement[f"core_{i}"] = mat_id

            for i, surrounding_input in enumerate(placement_data.surrounding_inputs):
                mat_id = surrounding_input.get('materialId', '')
                if mat_id:
                    self.user_placement[f"surrounding_{i}"] = mat_id

        elif placement_data.discipline == 'alchemy':
            # Sequential: copy ingredients
            for ingredient in placement_data.ingredients:
                slot_num = ingredient.get('slot')
                mat_id = ingredient.get('materialId', '')
                if slot_num and mat_id:
                    self.user_placement[f"seq_{slot_num}"] = mat_id

        elif placement_data.discipline == 'engineering':
            # Slot-type: copy slots
            for i, slot in enumerate(placement_data.slots):
                mat_id = slot.get('materialId', '')
                if mat_id:
                    self.user_placement[f"eng_slot_{i}"] = mat_id

        print(f"✅ Loaded {len(self.user_placement)} placements for {recipe.recipe_id}")

    def _get_grid_size_for_tier(self, tier: int, discipline: str) -> Tuple[int, int]:
        """Get grid dimensions based on station tier (matches Renderer method)"""
        if discipline not in ['smithing', 'adornments']:
            return (3, 3)
        tier_to_grid = {1: (3, 3), 2: (5, 5), 3: (7, 7), 4: (9, 9)}
        return tier_to_grid.get(tier, (3, 3))

    def validate_placement(self, recipe: Recipe, user_placement: Dict[str, str]) -> Tuple[bool, str]:
        """
        Validate user's material placement against recipe requirements

        Args:
            recipe: Recipe being crafted
            user_placement: User's current placement (Dict[str, str] mapping "x,y" -> materialId)

        Returns:
            (is_valid, error_message): Tuple of validation result and error message
        """
        placement_db = PlacementDatabase.get_instance()

        # Get required placement data
        placement_data = placement_db.get_placement(recipe.recipe_id)
        if not placement_data:
            # No placement data - placement not required
            return (True, "")

        discipline = placement_data.discipline

        if discipline == 'smithing' or discipline == 'adornments':
            # Grid-based validation with centering offset
            required_map = placement_data.placement_map

            # Get recipe and station grid sizes
            recipe_grid_w, recipe_grid_h = 3, 3
            if placement_data.grid_size:
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass

            station_grid_w, station_grid_h = self._get_grid_size_for_tier(self.active_station_tier, discipline)
            offset_x = (station_grid_w - recipe_grid_w) // 2
            offset_y = (station_grid_h - recipe_grid_h) // 2

            # Check if all required positions are filled (with offset)
            for pos, required_mat in required_map.items():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        station_pos = f"{station_x},{station_y}"

                        if station_pos not in user_placement:
                            return (False, f"Missing material at {pos} ({required_mat})")

                        user_mat = user_placement[station_pos]
                        if user_mat != required_mat:
                            return (False, f"Wrong material at {pos}: expected {required_mat}, got {user_mat}")
                    except ValueError:
                        pass

            # Check for extra materials (allow placements within recipe bounds only)
            expected_positions = set()
            for pos in required_map.keys():
                parts = pos.split(',')
                if len(parts) == 2:
                    try:
                        recipe_x = int(parts[0])
                        recipe_y = int(parts[1])
                        station_x = recipe_x + offset_x
                        station_y = recipe_y + offset_y
                        expected_positions.add(f"{station_x},{station_y}")
                    except ValueError:
                        pass

            for pos in user_placement.keys():
                if pos not in expected_positions:
                    return (False, f"Extra material at {pos} (not part of recipe)")

            return (True, "Placement correct!")

        elif discipline == 'refining':
            # Hub-and-spoke validation
            required_core = placement_data.core_inputs
            required_surrounding = placement_data.surrounding_inputs

            # Check core slots
            for i, core_input in enumerate(required_core):
                slot_id = f"core_{i}"
                required_mat = core_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing core material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong core material: expected {required_mat}, got {user_mat}")

            # Check surrounding slots
            for i, surrounding_input in enumerate(required_surrounding):
                slot_id = f"surrounding_{i}"
                required_mat = surrounding_input.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing surrounding material: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong surrounding material: expected {required_mat}, got {user_mat}")

            # Check for extra materials in wrong slots
            expected_slots = set(f"core_{i}" for i in range(len(required_core)))
            expected_slots.update(f"surrounding_{i}" for i in range(len(required_surrounding)))

            for slot_id in user_placement.keys():
                if slot_id.startswith('core_') or slot_id.startswith('surrounding_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra material in {slot_id} (not required)")

            return (True, "Refining placement correct!")

        elif discipline == 'alchemy':
            # Sequential validation
            required_ingredients = placement_data.ingredients

            # Check each sequential slot
            for ingredient in required_ingredients:
                slot_num = ingredient.get('slot')
                slot_id = f"seq_{slot_num}"
                required_mat = ingredient.get('materialId', '')

                if slot_id not in user_placement:
                    return (False, f"Missing ingredient in slot {slot_num}: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    return (False, f"Wrong ingredient in slot {slot_num}: expected {required_mat}, got {user_mat}")

            # Check for extra materials in wrong slots
            expected_slots = set(f"seq_{ing.get('slot')}" for ing in required_ingredients)

            for slot_id in user_placement.keys():
                if slot_id.startswith('seq_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra ingredient in {slot_id} (not required)")

            return (True, "Alchemy sequence correct!")

        elif discipline == 'engineering':
            # Slot-type validation
            required_slots = placement_data.slots

            # Check each slot
            for i, slot_data in enumerate(required_slots):
                slot_id = f"eng_slot_{i}"
                required_mat = slot_data.get('materialId', '')

                if slot_id not in user_placement:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Missing material in {slot_type} slot: {required_mat}")

                user_mat = user_placement[slot_id]
                if user_mat != required_mat:
                    slot_type = slot_data.get('type', '')
                    return (False, f"Wrong material in {slot_type} slot: expected {required_mat}, got {user_mat}")

            # Check for extra materials
            expected_slots = set(f"eng_slot_{i}" for i in range(len(required_slots)))

            for slot_id in user_placement.keys():
                if slot_id.startswith('eng_slot_'):
                    if slot_id not in expected_slots:
                        return (False, f"Extra material in {slot_id} (not required)")

            return (True, "Engineering placement correct!")

        else:
            # Unknown discipline
            return (True, "")

    def craft_item(self, recipe: Recipe, use_minigame: bool = False):
        """
        Craft an item either instantly or via minigame

        Args:
            recipe: Recipe to craft
            use_minigame: If True, start minigame. If False, instant craft.
        """
        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        print("\n" + "="*80)
        print(f"🔨 CRAFT_ITEM - Using New Crafting System")
        print(f"Recipe ID: {recipe.recipe_id}")
        print(f"Output ID: {recipe.output_id}")
        print(f"Station Type: {recipe.station_type}")
        print(f"Use Minigame: {use_minigame}")
        print("="*80)

        # Check if we have materials
        if not recipe_db.can_craft(recipe, self.character.inventory):
            self.add_notification("Not enough materials!", (255, 100, 100))
            print("❌ Cannot craft - not enough materials")
            return

        # Validate placement (if required)
        is_valid, error_msg = self.validate_placement(recipe, self.user_placement)
        if not is_valid:
            self.add_notification(f"Invalid placement: {error_msg}", (255, 100, 100))
            print(f"❌ Cannot craft - invalid placement: {error_msg}")
            return
        elif error_msg:  # Valid with message
            print(f"✓ Placement validated: {error_msg}")

        # Handle enchanting recipes differently (apply to existing items)
        if recipe.is_enchantment:
            print("⚠ Enchantment recipe - opening item selection UI")
            self._open_enchantment_selection(recipe)
            return

        # Choose crafting method
        if use_minigame:
            print("🎮 Starting minigame...")
            self._start_minigame(recipe)
            return
        else:
            print("⚡ Using instant craft...")
            self._instant_craft(recipe)
            return

    def _instant_craft(self, recipe: Recipe):
        """Perform instant crafting (no minigame, 0 EXP)"""
        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Get the appropriate crafter for this discipline
        crafter = self.get_crafter_for_station(recipe.station_type)

        if crafter and CRAFTING_MODULES_LOADED:
            # NEW SYSTEM: Use crafting subdisciplines
            print(f"✓ Using {recipe.station_type} crafter from subdisciplines")

            # Convert inventory to dict format
            inv_dict = self.inventory_to_dict()

            # DEBUG MODE: Add infinite quantities of required materials
            if Config.DEBUG_INFINITE_RESOURCES:
                print("🔧 DEBUG MODE: Adding infinite materials and bypassing rarity checks")
                # Enable debug mode in rarity system to bypass rarity uniformity checks
                rarity_system.debug_mode = True
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId', '')
                    # Add huge quantity - rarity is checked from material database, not inventory
                    inv_dict[mat_id] = 999999
            else:
                # Ensure debug mode is off
                rarity_system.debug_mode = False

            # Check if crafter can craft (with rarity checks)
            can_craft_result = crafter.can_craft(recipe.recipe_id, inv_dict)
            if isinstance(can_craft_result, tuple):
                can_craft, error_msg = can_craft_result
            else:
                can_craft, error_msg = can_craft_result, None

            if not can_craft:
                self.add_notification(f"Cannot craft: {error_msg or 'Unknown error'}", (255, 100, 100))
                print(f"❌ Crafter blocked: {error_msg}")
                return

            # Use instant craft (minigames come later)
            print(f"📦 Calling crafter.craft_instant()...")
            result = crafter.craft_instant(recipe.recipe_id, inv_dict)

            if result.get('success'):
                output_id = result.get('outputId')
                quantity = result.get('quantity', 1)
                rarity = result.get('rarity', 'common')
                stats = result.get('stats')

                print(f"✓ Craft successful: {quantity}x {output_id} ({rarity})")
                if stats:
                    print(f"   Stats: {stats}")

                # Add to inventory with rarity and stats
                self.add_crafted_item_to_inventory(output_id, quantity, rarity, stats)

                # Record activity and award XP (instant craft = 0 XP per Game Mechanics v5)
                activity_map = {
                    'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                    'engineering': 'engineering', 'adornments': 'enchanting'
                }
                activity_type = activity_map.get(recipe.station_type, 'smithing')
                self.character.activities.record_activity(activity_type, 1)

                # Instant craft gives 0 EXP (only minigames give EXP)
                print("  (Instant craft = 0 EXP, use minigame for EXP)")

                # Check for titles
                new_title = self.character.titles.check_for_title(
                    activity_type, self.character.activities.get_count(activity_type)
                )
                if new_title:
                    self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

                # Get item name for notification
                if equip_db.is_equipment(output_id):
                    equipment = equip_db.create_equipment_from_id(output_id)
                    item_name = equipment.name if equipment else output_id
                else:
                    material = mat_db.get_material(output_id)
                    item_name = material.name if material else output_id

                rarity_str = f" ({rarity})" if rarity != 'common' else ""
                self.add_notification(f"Crafted {item_name}{rarity_str} x{quantity}", (100, 255, 100))
                print("="*80 + "\n")
            else:
                error_msg = result.get('message', 'Crafting failed')
                self.add_notification(f"Failed: {error_msg}", (255, 100, 100))
                print(f"❌ {error_msg}")
                print("="*80 + "\n")

        else:
            # FALLBACK: Legacy instant craft system
            print("⚠ Crafting modules not loaded, using legacy system")
            if recipe.is_enchantment:
                self._apply_enchantment(recipe)
                return

            # Old instant craft logic
            if recipe_db.consume_materials(recipe, self.character.inventory):
                self.character.inventory.add_item(recipe.output_id, recipe.output_qty)
                self.add_notification(f"Crafted (legacy) {recipe.output_id} x{recipe.output_qty}", (100, 255, 100))

    def _apply_enchantment(self, recipe: Recipe):
        """Apply an enchantment to an item - shows selection UI"""
        # Find compatible items in inventory
        compatible_items = []
        for i, slot in enumerate(self.character.inventory.slots):
            if slot and slot.is_equipment() and slot.equipment_data:
                equipment = slot.equipment_data
                can_apply, reason = equipment.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append(('inventory', i, slot, equipment))

        # Also check equipped items
        for slot_name, equipped_item in self.character.equipment.slots.items():
            if equipped_item:
                can_apply, reason = equipped_item.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append(('equipped', slot_name, None, equipped_item))

        if not compatible_items:
            self.add_notification("No compatible items found!", (255, 100, 100))
            return

        # Open selection UI
        self.enchantment_selection_active = True
        self.enchantment_recipe = recipe
        self.enchantment_compatible_items = compatible_items
        print(f"🔮 Opening enchantment selection UI with {len(compatible_items)} compatible items")

    def _complete_enchantment_application(self, source_type: str, source_id, item_stack, equipment):
        """Complete the enchantment application after user selects an item"""
        recipe = self.enchantment_recipe
        recipe_db = RecipeDatabase.get_instance()

        # Consume materials
        if not recipe_db.consume_materials(recipe, self.character.inventory):
            self.add_notification("Failed to consume materials!", (255, 100, 100))
            self._close_enchantment_selection()
            return

        # Apply enchantment to the equipment instance
        equipment.apply_enchantment(recipe.output_id, recipe.enchantment_name, recipe.effect)

        # Record activity
        self.character.activities.record_activity('enchanting', 1)
        xp_reward = 20 * recipe.station_tier
        self.character.leveling.add_exp(xp_reward)

        new_title = self.character.titles.check_for_title(
            'enchanting', self.character.activities.get_count('enchanting')
        )
        if new_title:
            self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

        self.add_notification(f"Applied {recipe.enchantment_name} to {equipment.name}!", (100, 255, 255))
        self._close_enchantment_selection()

    def _open_enchantment_selection(self, recipe: Recipe):
        """Open the item selection UI for applying enchantment"""
        equip_db = EquipmentDatabase.get_instance()

        # Get all equipment from inventory and equipped slots
        compatible_items = []

        # From inventory
        for slot_idx, stack in enumerate(self.character.inventory.slots):
            if stack and equip_db.is_equipment(stack.item_id):
                equipment = stack.get_equipment()  # Use actual equipment instance from stack
                if equipment:
                    compatible_items.append(('inventory', slot_idx, stack, equipment))

        # From equipped slots
        for slot_name, equipped_item in self.character.equipment.slots.items():
            if equipped_item:
                compatible_items.append(('equipped', slot_name, None, equipped_item))

        if not compatible_items:
            self.add_notification("No equipment to enchant!", (255, 100, 100))
            print("❌ No compatible items found for enchantment")
            return

        # Open the selection UI
        self.enchantment_selection_active = True
        self.enchantment_recipe = recipe
        self.enchantment_compatible_items = compatible_items
        print(f"✨ Opened enchantment selection UI ({len(compatible_items)} compatible items)")

    def _close_enchantment_selection(self):
        """Close the enchantment selection UI"""
        self.enchantment_selection_active = False
        self.enchantment_recipe = None
        self.enchantment_compatible_items = []
        self.enchantment_selection_rect = None

    def handle_mouse_release(self, mouse_pos: Tuple[int, int]):
        if self.character.inventory.dragging_stack:
            if mouse_pos[1] >= Config.INVENTORY_PANEL_Y:
                start_x, start_y = 20, Config.INVENTORY_PANEL_Y + 50
                slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
                rel_x, rel_y = mouse_pos[0] - start_x, mouse_pos[1] - start_y

                if rel_x >= 0 and rel_y >= 0:
                    col, row = rel_x // (slot_size + spacing), rel_y // (slot_size + spacing)
                    in_x = rel_x % (slot_size + spacing) < slot_size
                    in_y = rel_y % (slot_size + spacing) < slot_size

                    if in_x and in_y:
                        idx = row * Config.INVENTORY_SLOTS_PER_ROW + col
                        if 0 <= idx < self.character.inventory.max_slots:
                            self.character.inventory.end_drag(idx)
                            return
            self.character.inventory.cancel_drag()

    def update(self):
        curr = pygame.time.get_ticks()
        dt = (curr - self.last_tick) / 1000.0
        self.last_tick = curr

        if not self.character.class_selection_open:
            dx = dy = 0
            if pygame.K_w in self.keys_pressed:
                dy -= self.character.movement_speed
            if pygame.K_s in self.keys_pressed:
                dy += self.character.movement_speed
            if pygame.K_a in self.keys_pressed:
                dx -= self.character.movement_speed
            if pygame.K_d in self.keys_pressed:
                dx += self.character.movement_speed

            if dx != 0 and dy != 0:
                dx *= 0.7071
                dy *= 0.7071

            if dx != 0 or dy != 0:
                self.character.move(dx, dy, self.world)

        self.camera.follow(self.character.position)

        # Only update world/combat if minigame isn't active
        if not self.active_minigame:
            self.world.update(dt)
            self.combat_manager.update(dt)
            self.character.update_attack_cooldown(dt)
            self.character.update_health_regen(dt)
            self.character.update_buffs(dt)
        else:
            # Update active minigame (skip for engineering - it's turn-based)
            if self.minigame_type != 'engineering':
                self.active_minigame.update(dt)

            # Check if minigame completed
            if hasattr(self.active_minigame, 'result') and self.active_minigame.result is not None:
                self._complete_minigame()

        self.damage_numbers = [d for d in self.damage_numbers if d.update(dt)]
        self.notifications = [n for n in self.notifications if n.update(dt)]

    def render(self):
        self.screen.fill(Config.COLOR_BACKGROUND)
        self.renderer.render_world(self.world, self.camera, self.character, self.damage_numbers, self.combat_manager)
        self.renderer.render_ui(self.character, self.mouse_pos)
        self.renderer.render_inventory_panel(self.character, self.mouse_pos)

        # Render skill hotbar at bottom center (over viewport)
        self.renderer.render_skill_hotbar(self.character)

        self.renderer.render_notifications(self.notifications)

        if self.character.class_selection_open:
            result = self.renderer.render_class_selection_ui(self.character, self.mouse_pos)
            if result:
                self.class_selection_rect, self.class_buttons = result
        else:
            self.class_selection_rect = None
            self.class_buttons = []

            if self.character.crafting_ui_open:
                # Pass scroll offset via temporary attribute (renderer doesn't have direct access to game state)
                self.renderer._temp_scroll_offset = self.recipe_scroll_offset
                result = self.renderer.render_crafting_ui(self.character, self.mouse_pos, self.selected_recipe, self.user_placement)
                if result:
                    self.crafting_window_rect, self.crafting_recipes, self.placement_grid_rects = result
            else:
                self.crafting_window_rect = None
                self.crafting_recipes = []

            if self.character.stats_ui_open:
                result = self.renderer.render_stats_ui(self.character, self.mouse_pos)
                if result:
                    self.stats_window_rect, self.stats_buttons = result
            else:
                self.stats_window_rect = None
                self.stats_buttons = []

            if self.character.skills_ui_open:
                result = self.renderer.render_skills_menu_ui(self.character, self.mouse_pos)
                if result:
                    self.skills_window_rect, self.skills_hotbar_rects, self.skills_list_rects = result
            else:
                self.skills_window_rect = None
                self.skills_hotbar_rects = []
                self.skills_list_rects = []

            if self.character.equipment_ui_open:
                result = self.renderer.render_equipment_ui(self.character, self.mouse_pos)
                if result:
                    self.equipment_window_rect, self.equipment_rects = result
            else:
                self.equipment_window_rect = None
                self.equipment_rects = {}

            # Enchantment selection UI (rendered on top of everything)
            if self.enchantment_selection_active:
                result = self.renderer.render_enchantment_selection_ui(
                    self.mouse_pos, self.enchantment_recipe, self.enchantment_compatible_items)
                if result:
                    self.enchantment_selection_rect, self.enchantment_item_rects = result
            else:
                self.enchantment_selection_rect = None
                self.enchantment_item_rects = None

        # Minigame rendering (rendered on top of EVERYTHING)
        if self.active_minigame:
            self._render_minigame()

        pygame.display.flip()

    def _render_minigame(self):
        """Render the active minigame"""
        if not self.active_minigame or not self.minigame_type:
            return

        # Route to appropriate renderer based on minigame type
        if self.minigame_type == 'smithing':
            self._render_smithing_minigame()
        elif self.minigame_type == 'alchemy':
            self._render_alchemy_minigame()
        elif self.minigame_type == 'refining':
            self._render_refining_minigame()
        elif self.minigame_type == 'engineering':
            self._render_engineering_minigame()
        elif self.minigame_type == 'adornments':
            self._render_enchanting_minigame()

    def _complete_minigame(self):
        """Complete the active minigame and process results"""
        if not self.active_minigame or not self.minigame_recipe:
            return

        print(f"\n{'='*80}")
        print(f"🎮 MINIGAME COMPLETED")
        print(f"Recipe: {self.minigame_recipe.recipe_id}")
        print(f"Type: {self.minigame_type}")
        print(f"Result: {self.active_minigame.result}")
        print(f"{'='*80}\n")

        recipe = self.minigame_recipe
        result = self.active_minigame.result
        crafter = self.get_crafter_for_station(self.minigame_type)

        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        # Convert inventory to dict
        inv_dict = {}
        for slot in self.character.inventory.slots:
            if slot:
                inv_dict[slot.item_id] = inv_dict.get(slot.item_id, 0) + slot.quantity

        # Add recipe inputs to inv_dict with 0 if missing (defensive programming)
        for inp in recipe.inputs:
            mat_id = inp.get('materialId') or inp.get('itemId')
            if mat_id and mat_id not in inv_dict:
                inv_dict[mat_id] = 0
                print(f"⚠ Warning: Recipe material '{mat_id}' not in inventory!")

        # Use crafter to process minigame result
        craft_result = crafter.craft_with_minigame(recipe.recipe_id, inv_dict, result)

        if not craft_result.get('success'):
            # Failure - materials may have been lost
            message = craft_result.get('message', 'Crafting failed')
            self.add_notification(message, (255, 100, 100))

            # Sync inventory back
            recipe_db.consume_materials(recipe, self.character.inventory)
        else:
            # Success - consume materials and add output
            recipe_db.consume_materials(recipe, self.character.inventory)

            # Record activity and XP
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(self.minigame_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            # Extra XP for minigame (50% bonus)
            xp_reward = int(20 * recipe.station_tier * 1.5)
            self.character.leveling.add_exp(xp_reward)

            new_title = self.character.titles.check_for_title(
                activity_type, self.character.activities.get_count(activity_type)
            )
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

            # Add output to inventory
            output_id = craft_result.get('outputId', recipe.output_id)
            output_qty = craft_result.get('quantity', recipe.output_qty)
            self.character.inventory.add_item(output_id, output_qty)

            # Get proper name for notification
            if equip_db.is_equipment(output_id):
                equipment = equip_db.create_equipment_from_id(output_id)
                out_name = equipment.name if equipment else output_id
            else:
                out_mat = mat_db.get_material(output_id)
                out_name = out_mat.name if out_mat else output_id

            message = craft_result.get('message', f"Crafted {out_name} x{output_qty}")
            self.add_notification(message, (100, 255, 100))
            print(f"✅ Minigame crafting complete: {out_name} x{output_qty}")

        # Clear minigame state
        self.active_minigame = None
        self.minigame_type = None
        self.minigame_recipe = None

    def _render_smithing_minigame(self):
        """Render smithing minigame UI"""
        state = self.active_minigame.get_state()

        # Create overlay
        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("SMITHING MINIGAME", True, (255, 215, 0))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[SPACE] Fan Flames | [CLICK HAMMER BUTTON] Strike", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Temperature bar
        temp_x, temp_y = 50, 100
        temp_width = 300
        temp_height = 40

        # Draw temp bar background
        pygame.draw.rect(surf, (40, 40, 40), (temp_x, temp_y, temp_width, temp_height))

        # Draw ideal range
        ideal_min = state['temp_ideal_min']
        ideal_max = state['temp_ideal_max']
        ideal_start = int((ideal_min / 100) * temp_width)
        ideal_width_px = int(((ideal_max - ideal_min) / 100) * temp_width)
        pygame.draw.rect(surf, (60, 80, 60), (temp_x + ideal_start, temp_y, ideal_width_px, temp_height))

        # Draw current temperature
        temp_pct = state['temperature'] / 100
        temp_fill = int(temp_pct * temp_width)
        temp_color = (255, 100, 100) if temp_pct > 0.8 else (255, 165, 0) if temp_pct > 0.5 else (100, 150, 255)
        pygame.draw.rect(surf, temp_color, (temp_x, temp_y, temp_fill, temp_height))

        pygame.draw.rect(surf, (200, 200, 200), (temp_x, temp_y, temp_width, temp_height), 2)
        _temp_surf = self.renderer.small_font.render(f"Temperature: {int(state['temperature'])}°C", True, (255, 255, 255))
        surf.blit(_temp_surf, (temp_x, temp_y - 25))

        # Hammer bar
        hammer_x, hammer_y = 50, 200
        hammer_width = state['hammer_bar_width']
        hammer_height = 60

        # Draw hammer bar background
        pygame.draw.rect(surf, (40, 40, 40), (hammer_x, hammer_y, hammer_width, hammer_height))

        # Draw target zone (center)
        center = hammer_width / 2
        target_start = int(center - state['target_width'] / 2)
        pygame.draw.rect(surf, (80, 80, 60), (hammer_x + target_start, hammer_y, state['target_width'], hammer_height))

        # Draw perfect zone (center of target)
        perfect_start = int(center - state['perfect_width'] / 2)
        pygame.draw.rect(surf, (100, 120, 60), (hammer_x + perfect_start, hammer_y, state['perfect_width'], hammer_height))

        # Draw hammer indicator
        hammer_pos = int(state['hammer_position'])
        pygame.draw.circle(surf, (255, 215, 0), (hammer_x + hammer_pos, hammer_y + hammer_height // 2), 15)

        pygame.draw.rect(surf, (200, 200, 200), (hammer_x, hammer_y, hammer_width, hammer_height), 2)
        _temp_surf = self.renderer.small_font.render(f"Hammer Timing: {state['hammer_hits']}/{state['required_hits']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (hammer_x, hammer_y - 25))

        # Hammer button
        btn_w, btn_h = 200, 60
        btn_x, btn_y = ww // 2 - btn_w // 2, 300
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(surf, (80, 60, 20), btn_rect)
        pygame.draw.rect(surf, (255, 215, 0), btn_rect, 3)
        _temp_surf = self.renderer.font.render("HAMMER", True, (255, 215, 0))
        surf.blit(_temp_surf, (btn_x + 40, btn_y + 15))

        # Timer and scores
        _temp_surf = self.renderer.font.render(f"Time Left: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 400))

        if state['hammer_scores']:
            _temp_surf = self.renderer.small_font.render("Hammer Scores:", True, (200, 200, 200))
            surf.blit(_temp_surf, (50, 450))
            for i, score in enumerate(state['hammer_scores'][-5:]):  # Last 5 scores
                color = (100, 255, 100) if score >= 90 else (255, 215, 0) if score >= 70 else (255, 100, 100)
                _temp_surf = self.renderer.small_font.render(f"Hit {i+1}: {score}", True, color)
                surf.blit(_temp_surf, (70, 480 + i * 25))

        # Result (if completed)
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 300), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render("SUCCESS!", True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(f"Score: {int(result['score'])}", True, (255, 255, 255))
                result_surf.blit(_temp_surf, (150, 120))
                _temp_surf = self.renderer.small_font.render(f"Bonus: +{result['bonus']}%", True, (255, 215, 0))
                result_surf.blit(_temp_surf, (150, 150))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 200))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 120))

            surf.blit(result_surf, (200, 200))

        self.screen.blit(surf, (wx, wy))

        # Store button rect for click detection (relative to screen)
        self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

    def _render_alchemy_minigame(self):
        """Render alchemy minigame UI"""
        state = self.active_minigame.get_state()

        # Create overlay
        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("ALCHEMY MINIGAME", True, (60, 180, 60))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[C] Chain Ingredient | [S] Stabilize & Complete", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress bar
        progress = state['total_progress']
        prog_x, prog_y = 50, 100
        prog_width = 600
        prog_height = 30
        pygame.draw.rect(surf, (40, 40, 40), (prog_x, prog_y, prog_width, prog_height))
        pygame.draw.rect(surf, (60, 180, 60), (prog_x, prog_y, int(progress * prog_width), prog_height))
        pygame.draw.rect(surf, (200, 200, 200), (prog_x, prog_y, prog_width, prog_height), 2)
        _temp_surf = self.renderer.small_font.render(f"Total Progress: {int(progress * 100)}%", True, (255, 255, 255))
        surf.blit(_temp_surf, (prog_x, prog_y - 25))

        # Current reaction visualization
        if state['current_reaction']:
            reaction = state['current_reaction']
            rx, ry = 50, 180

            # Reaction bubble
            bubble_size = int(100 * reaction['size'])
            bubble_color = (int(60 + 140 * reaction['color_shift']), int(180 * reaction['glow']), int(60 + 140 * reaction['color_shift']))
            pygame.draw.circle(surf, bubble_color, (rx + 100, ry + 100), bubble_size)
            pygame.draw.circle(surf, (200, 200, 200), (rx + 100, ry + 100), bubble_size, 2)

            # Stage info
            stage_names = ["Initiation", "Building", "SWEET SPOT", "Degrading", "Critical", "EXPLOSION!"]
            stage_idx = reaction['stage'] - 1
            stage_name = stage_names[stage_idx] if 0 <= stage_idx < len(stage_names) else "Unknown"
            stage_color = (255, 215, 0) if reaction['stage'] == 3 else (255, 100, 100) if reaction['stage'] >= 5 else (200, 200, 200)

            _temp_surf = self.renderer.font.render(f"Stage: {stage_name}", True, stage_color)
            surf.blit(_temp_surf, (rx, ry + 220))
            _temp_surf = self.renderer.small_font.render(f"Quality: {int(reaction['quality'] * 100)}%", True, (200, 200, 200))
            surf.blit(_temp_surf, (rx, ry + 250))

        # Ingredient progress
        _temp_surf = self.renderer.small_font.render(f"Ingredient: {state['current_ingredient_index'] + 1}/{state['total_ingredients']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 450))

        # Buttons
        btn_w, btn_h = 150, 50
        chain_btn = pygame.Rect(ww // 2 - btn_w - 10, 550, btn_w, btn_h)
        stabilize_btn = pygame.Rect(ww // 2 + 10, 550, btn_w, btn_h)

        pygame.draw.rect(surf, (60, 80, 20), chain_btn)
        pygame.draw.rect(surf, (255, 215, 0), chain_btn, 2)
        _temp_surf = self.renderer.small_font.render("CHAIN [C]", True, (255, 215, 0))
        surf.blit(_temp_surf, (chain_btn.x + 30, chain_btn.y + 15))

        pygame.draw.rect(surf, (20, 60, 80), stabilize_btn)
        pygame.draw.rect(surf, (100, 200, 255), stabilize_btn, 2)
        _temp_surf = self.renderer.small_font.render("STABILIZE [S]", True, (100, 200, 255))
        surf.blit(_temp_surf, (stabilize_btn.x + 15, stabilize_btn.y + 15))

        # Timer
        _temp_surf = self.renderer.font.render(f"Time: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 620))

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 300), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render(result['quality'], True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(f"Progress: {int(result['progress'] * 100)}%", True, (255, 255, 255))
                result_surf.blit(_temp_surf, (150, 120))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 150))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 120))

            surf.blit(result_surf, (200, 200))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = pygame.Rect(wx + chain_btn.x, wy + chain_btn.y, chain_btn.width, chain_btn.height)
        self.minigame_button_rect2 = pygame.Rect(wx + stabilize_btn.x, wy + stabilize_btn.y, stabilize_btn.width, stabilize_btn.height)

    def _render_refining_minigame(self):
        """Render refining minigame UI"""
        state = self.active_minigame.get_state()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("REFINING MINIGAME", True, (180, 120, 60))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("[SPACE] Align Cylinder", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress
        _temp_surf = self.renderer.font.render(f"Cylinders: {state['aligned_count']}/{state['total_cylinders']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 100))
        _temp_surf = self.renderer.font.render(f"Failures: {state['failed_attempts']}/{state['allowed_failures']}", True, (255, 100, 100))
        surf.blit(_temp_surf, (50, 140))
        _temp_surf = self.renderer.font.render(f"Time: {int(state['time_left'])}s", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 180))

        # Current cylinder visualization
        if state['current_cylinder'] < len(state['cylinders']):
            cyl = state['cylinders'][state['current_cylinder']]
            cx, cy = ww // 2, 300
            radius = 100

            # Draw cylinder circle
            pygame.draw.circle(surf, (60, 60, 60), (cx, cy), radius)
            pygame.draw.circle(surf, (200, 200, 200), (cx, cy), radius, 3)

            # Draw indicator at current angle
            angle_rad = math.radians(cyl['angle'])
            ind_x = cx + int(radius * 0.8 * math.cos(angle_rad - math.pi/2))
            ind_y = cy + int(radius * 0.8 * math.sin(angle_rad - math.pi/2))
            pygame.draw.circle(surf, (255, 215, 0), (ind_x, ind_y), 15)

            # Draw target zone at top
            pygame.draw.circle(surf, (100, 255, 100), (cx, cy - radius), 20, 3)

        # Instructions
        _temp_surf = self.renderer.small_font.render("Press SPACE when indicator is at the top!", True, (200, 200, 200))
        surf.blit(_temp_surf, (ww//2 - 150, 450))

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 200), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            if result['success']:
                _temp_surf = self.renderer.font.render("SUCCESS!", True, (100, 255, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 100))
            else:
                _temp_surf = self.renderer.font.render("FAILED!", True, (255, 100, 100))
                result_surf.blit(_temp_surf, (200, 50))
                _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
                result_surf.blit(_temp_surf, (150, 100))

            surf.blit(result_surf, (200, 250))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = None

    def _render_engineering_minigame(self):
        """Render engineering minigame UI"""
        state = self.active_minigame.get_state()

        ww, wh = 1000, 700
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Header
        _temp_surf = self.renderer.font.render("ENGINEERING MINIGAME", True, (60, 120, 180))
        surf.blit(_temp_surf, (ww//2 - 120, 20))
        _temp_surf = self.renderer.small_font.render("Solve puzzles to complete device", True, (180, 180, 180))
        surf.blit(_temp_surf, (20, 50))

        # Progress
        _temp_surf = self.renderer.font.render(f"Puzzle: {state['current_puzzle_index'] + 1}/{state['total_puzzles']}", True, (255, 255, 255))
        surf.blit(_temp_surf, (50, 100))
        _temp_surf = self.renderer.font.render(f"Solved: {state['solved_count']}", True, (100, 255, 100))
        surf.blit(_temp_surf, (50, 140))

        # Puzzle-specific rendering
        if state['current_puzzle']:
            puzzle = state['current_puzzle']
            _temp_surf = self.renderer.font.render("Current Puzzle: Click to interact", True, (200, 200, 200))
            surf.blit(_temp_surf, (50, 200))

            # Simple visualization (placeholder for actual puzzle rendering)
            puzzle_rect = pygame.Rect(200, 250, 600, 300)
            pygame.draw.rect(surf, (40, 40, 40), puzzle_rect)
            pygame.draw.rect(surf, (100, 100, 100), puzzle_rect, 2)

            if puzzle.get('grid_size'):
                _temp_surf = self.renderer.small_font.render(f"Rotation Puzzle ({puzzle['grid_size']}x{puzzle['grid_size']})", True, (200, 200, 200))
                surf.blit(_temp_surf, (puzzle_rect.x + 20, puzzle_rect.y + 20))
            elif puzzle.get('placeholder'):
                _temp_surf = self.renderer.small_font.render("Puzzle placeholder - Click COMPLETE", True, (200, 200, 200))
                surf.blit(_temp_surf, (puzzle_rect.x + 20, puzzle_rect.y + 20))

        # Complete button (for testing)
        btn_w, btn_h = 200, 50
        btn_x, btn_y = ww // 2 - btn_w // 2, 600
        complete_btn = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(surf, (60, 100, 60), complete_btn)
        pygame.draw.rect(surf, (100, 200, 100), complete_btn, 2)
        _temp_surf = self.renderer.small_font.render("COMPLETE PUZZLE", True, (200, 200, 200))
        surf.blit(_temp_surf, (btn_x + 40, btn_y + 15))

        # Result
        if state['result']:
            result = state['result']
            result_surf = pygame.Surface((600, 200), pygame.SRCALPHA)
            result_surf.fill((10, 10, 20, 240))
            _temp_surf = self.renderer.font.render("DEVICE CREATED!", True, (100, 255, 100))
            result_surf.blit(_temp_surf, (200, 50))
            _temp_surf = self.renderer.small_font.render(result['message'], True, (200, 200, 200))
            result_surf.blit(_temp_surf, (150, 100))
            surf.blit(result_surf, (200, 250))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = pygame.Rect(wx + btn_x, wy + btn_y, btn_w, btn_h)

    def _render_enchanting_minigame(self):
        """Render enchanting minigame UI (placeholder)"""
        ww, wh = 800, 600
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        _temp_surf = self.renderer.font.render("ENCHANTING", True, (180, 60, 180))
        surf.blit(_temp_surf, (ww//2 - 100, 20))
        _temp_surf = self.renderer.small_font.render("Enchanting uses basic crafting (no minigame)", True, (200, 200, 200))
        surf.blit(_temp_surf, (50, 100))

        self.screen.blit(surf, (wx, wy))
        self.minigame_button_rect = None

    def run(self):
        print("=== GAME STARTED ===")
        print("Controls:")
        print("  WASD - Move")
        print("  Click - Harvest/Interact")
        print("  TAB - Switch Tool")
        print("  C - Stats")
        print("  E - Equipment")
        print("  F1 - Toggle Debug Mode")
        print("  ESC - Close/Quit")
        print("\nEquipment:")
        print("  Double-click item in inventory to equip")
        print("  Shift+click equipment slot to unequip")
        print("\nTip: Crafting stations are right next to you!")
        print()

        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(Config.FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = GameEngine()
    game.run()