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
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for section in ['weapons', 'armor', 'accessories', 'tools']:  # FIX #3: Added 'tools'
                if section in data:
                    for item_data in data[section]:
                        try:
                            item_id = item_data.get('itemId', '')
                            if item_id:
                                self.items[item_id] = item_data
                                count += 1
                        except Exception as e:
                            print(f"⚠ Skipping invalid item: {e}")
                            continue
            if count > 0:
                self.loaded = True
                print(f"✓ Loaded {count} equipment items")
                return True
            else:
                raise Exception("No valid items loaded")
        except Exception as e:
            print(f"⚠ Error loading equipment: {e}")
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

        return EquipmentItem(
            item_id=item_id,
            name=data.get('name', item_id),
            tier=data.get('tier', 1),
            rarity=data.get('rarity', 'common'),
            slot=data.get('slot', 'mainHand'),
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
        return item_id in self.items


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
        can_equip, reason = item.can_equip(character)
        if not can_equip:
            return None, reason

        slot = item.slot
        if slot not in self.slots:
            return None, f"Invalid slot: {slot}"

        old_item = self.slots[slot]
        self.slots[slot] = item

        # Recalculate character stats
        character.recalculate_stats()

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
            for recipe_data in data.get('recipes', []):
                # Check if this is an enchanting recipe (has enchantmentId instead of outputId)
                is_enchanting = 'enchantmentId' in recipe_data

                if is_enchanting:
                    # For enchanting: use enchantmentId as the output_id
                    output_id = recipe_data.get('enchantmentId', '')
                    output_qty = 1  # Enchantments don't have quantity
                else:
                    # Regular crafting: use outputId
                    output_id = recipe_data.get('outputId', '')
                    output_qty = recipe_data.get('outputQty', 1)

                recipe = Recipe(
                    recipe_id=recipe_data.get('recipeId', ''),
                    output_id=output_id,
                    output_qty=output_qty,
                    station_type=station_type,
                    station_tier=recipe_data.get('stationTier', 1),
                    inputs=recipe_data.get('inputs', []),
                    is_enchantment=is_enchanting,
                    enchantment_name=recipe_data.get('enchantmentName', ''),
                    applicable_to=recipe_data.get('applicableTo', []),
                    effect=recipe_data.get('effect', {})
                )
                self.recipes[recipe.recipe_id] = recipe
                self.recipes_by_station[station_type].append(recipe)
            return len(data.get('recipes', []))
        except:
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
        """Spawn crafting stations near player start (50, 50)"""
        # Place stations in starting chunk around the player
        for x, y, stype in [
            (48, 48, StationType.SMITHING),
            (52, 48, StationType.REFINING),
            (48, 52, StationType.ALCHEMY),
            (52, 52, StationType.ENGINEERING),
            (50, 50, StationType.ADORNMENTS)  # Center station
        ]:
            self.crafting_stations.append(CraftingStation(Position(x, y, 0), stype, 1))

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
# SKILL SYSTEM
# ============================================================================
@dataclass
class PlayerSkill:
    skill_id: str
    level: int = 1
    experience: int = 0
    is_equipped: bool = False

    def get_definition(self):
        @dataclass
        class FakeSkill:
            name: str = "Unknown Skill"

        return FakeSkill()


class SkillManager:
    def __init__(self):
        self.known_skills: Dict[str, PlayerSkill] = {}
        self.equipped_skills: List[str] = []


class SkillDatabase:
    _instance = None

    def __init__(self):
        self.skills = {}
        self.loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SkillDatabase()
        return cls._instance

    def load_from_file(self, filepath: str = ""):
        self.loaded = True


# ============================================================================
# INVENTORY
# ============================================================================
@dataclass
class ItemStack:
    item_id: str
    quantity: int
    max_stack: int = 99
    equipment_data: Optional['EquipmentItem'] = None  # For equipment items, store actual instance

    def __post_init__(self):
        mat_db = MaterialDatabase.get_instance()
        if mat_db.loaded:
            mat = mat_db.get_material(self.item_id)
            if mat:
                self.max_stack = mat.max_stack

        # Equipment items don't stack
        equip_db = EquipmentDatabase.get_instance()
        if equip_db.is_equipment(self.item_id):
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
        if equip_db.is_equipment(item_id):
            for _ in range(quantity):
                empty = self.get_empty_slot()
                if empty is None:
                    return False
                # Use provided equipment instance or create new one
                equip_data = equipment_instance if equipment_instance else None
                self.slots[empty] = ItemStack(item_id, 1, 1, equip_data)
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

        self.active_station: Optional[CraftingStation] = None
        self.crafting_ui_open = False
        self.stats_ui_open = False
        self.equipment_ui_open = False
        self.class_selection_open = False

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
        speed_mult = 1.0 + self.stats.get_bonus('agility') * 0.02 + self.class_system.get_bonus('movement_speed')
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
        damage_mult = 1.0 + stat_bonus + title_bonus

        crit_chance = self.stats.luck * 0.02 + self.class_system.get_bonus('crit_chance')
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

        loot = None
        if depleted:
            loot = resource.get_loot()
            for item_id, qty in loot:
                if random.random() < (self.stats.luck * 0.02 + self.class_system.get_bonus('resource_quality')):
                    qty += 1
                self.inventory.add_item(item_id, qty)
        return (loot, actual_damage, is_crit)

    def switch_tool(self):
        if self.tools:
            idx = self.tools.index(self.selected_tool) if self.selected_tool in self.tools else -1
            self.selected_tool = self.tools[(idx + 1) % len(self.tools)]
            return self.selected_tool.name
        return None

    def interact_with_station(self, station: CraftingStation):
        if self.is_in_range(station.position):
            self.active_station = station
            self.crafting_ui_open = True

    def close_crafting_ui(self):
        self.active_station = None
        self.crafting_ui_open = False

    def toggle_stats_ui(self):
        self.stats_ui_open = not self.stats_ui_open

    def toggle_equipment_ui(self):
        self.equipment_ui_open = not self.equipment_ui_open

    def select_class(self, class_def: ClassDefinition):
        self.class_system.set_class(class_def)
        self.recalculate_stats()
        self.health = self.max_health
        self.mana = self.max_mana
        print(f"✓ Class selected: {class_def.name}")

    def try_equip_from_inventory(self, slot_index: int) -> Tuple[bool, str]:
        """Try to equip item from inventory slot"""
        if slot_index < 0 or slot_index >= self.inventory.max_slots:
            return False, "Invalid slot"

        item_stack = self.inventory.slots[slot_index]
        if not item_stack:
            return False, "Empty slot"

        if not item_stack.is_equipment():
            return False, "Not equipment"

        equipment = item_stack.get_equipment()
        if not equipment:
            return False, "Invalid equipment"

        # Try to equip
        old_item, status = self.equipment.equip(equipment, self)
        if status != "OK":
            return False, status

        # Remove from inventory
        self.inventory.slots[slot_index] = None

        # If there was an old item, put it back in inventory (preserve equipment data)
        if old_item:
            if not self.inventory.add_item(old_item.item_id, 1, old_item):
                # Inventory full, swap back
                self.equipment.slots[equipment.slot] = old_item
                self.inventory.slots[slot_index] = item_stack
                self.recalculate_stats()
                return False, "Inventory full"

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

    def render_world(self, world: WorldSystem, camera: Camera, character: Character,
                     damage_numbers: List[DamageNumber]):
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
            "C - Stats",
            "E - Equipment",
            "F1 - Debug Mode",
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

    def render_crafting_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.crafting_ui_open or not character.active_station:
            return None

        recipe_db = RecipeDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        ww, wh = 900, 600
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
        wy = (Config.VIEWPORT_HEIGHT - wh) // 2

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        header = f"{character.active_station.station_type.value.upper()} (T{character.active_station.tier})"
        surf.blit(self.font.render(header, True, character.active_station.get_color()), (20, 20))
        surf.blit(self.small_font.render("[ESC] Close", True, (180, 180, 180)), (ww - 120, 20))

        recipes = recipe_db.get_recipes_for_station(character.active_station.station_type.value,
                                                    character.active_station.tier)

        if not recipes:
            surf.blit(self.font.render("No recipes available", True, (200, 200, 200)), (20, 80))
        else:
            y_off = 70
            for i, recipe in enumerate(recipes[:6]):
                btn = pygame.Rect(20, y_off, ww - 40, 80)
                can_craft = recipe_db.can_craft(recipe, character.inventory)
                btn_color = (40, 60, 40) if can_craft else (60, 40, 40)
                pygame.draw.rect(surf, btn_color, btn)
                pygame.draw.rect(surf, (100, 100, 100), btn, 2)

                # Check if output is equipment or material
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
                          (btn.x + 10, btn.y + 10))

                req_y = btn.y + 35
                for inp in recipe.inputs[:3]:
                    mat_id = inp.get('materialId', '')
                    req = inp.get('quantity', 0)
                    avail = character.inventory.get_item_count(mat_id)
                    mat = mat_db.get_material(mat_id)
                    mat_name = mat.name if mat else mat_id
                    req_color = (100, 255, 100) if avail >= req or Config.DEBUG_INFINITE_RESOURCES else (255, 100, 100)
                    surf.blit(self.small_font.render(f"{mat_name}: {avail}/{req}", True, req_color),
                              (btn.x + 20, req_y))
                    req_y += 18

                if can_craft:
                    surf.blit(self.small_font.render("[CLICK] Craft", True, (100, 255, 100)),
                              (btn.right - 120, btn.centery - 8))

                y_off += 90

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), recipes[:6] if recipes else []

    def render_equipment_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.equipment_ui_open:
            return None

        ww, wh = 800, 600
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
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

    def render_class_selection_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.class_selection_open:
            return None

        class_db = ClassDatabase.get_instance()
        if not class_db.loaded or not class_db.classes:
            return None

        ww, wh = 900, 700
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
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
        wx = (Config.VIEWPORT_WIDTH - ww) // 2
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
        TranslationDatabase.get_instance().load_from_files()
        SkillDatabase.get_instance().load_from_file()
        RecipeDatabase.get_instance().load_from_files()
        EquipmentDatabase.get_instance().load_from_file("items.JSON/items-smithing-2.JSON")
        TitleDatabase.get_instance().load_from_file("progression/titles-1.JSON")
        ClassDatabase.get_instance().load_from_file("progression/classes-1.JSON")

        print("\nInitializing systems...")
        self.world = WorldSystem()
        self.character = Character(Position(50.0, 50.0, 0.0))
        self.camera = Camera(Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT)
        self.renderer = Renderer(self.screen)

        self.damage_numbers: List[DamageNumber] = []
        self.notifications: List[Notification] = []
        self.crafting_window_rect = None
        self.crafting_recipes = []
        self.stats_window_rect = None
        self.stats_buttons = []
        self.equipment_window_rect = None
        self.equipment_rects = {}
        self.class_selection_rect = None
        self.class_buttons = []

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
                if event.key == pygame.K_ESCAPE:
                    if self.character.crafting_ui_open:
                        self.character.close_crafting_ui()
                    elif self.character.stats_ui_open:
                        self.character.toggle_stats_ui()
                    elif self.character.equipment_ui_open:
                        self.character.toggle_equipment_ui()
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
                elif event.key == pygame.K_F1:
                    Config.DEBUG_INFINITE_RESOURCES = not Config.DEBUG_INFINITE_RESOURCES
                    status = "ENABLED" if Config.DEBUG_INFINITE_RESOURCES else "DISABLED"
                    self.add_notification(f"Debug Mode {status}", (255, 100, 255))
                    print(f"⚠ Debug Mode {status}")
            elif event.type == pygame.KEYUP:
                self.keys_pressed.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_pos = event.pos
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

        # Class selection
        if self.character.class_selection_open and self.class_selection_rect:
            if self.class_selection_rect.collidepoint(mouse_pos):
                self.handle_class_selection_click(mouse_pos)
                return

        # Stats UI
        if self.character.stats_ui_open and self.stats_window_rect:
            if self.stats_window_rect.collidepoint(mouse_pos):
                self.handle_stats_click(mouse_pos)
                return

        # Equipment UI
        if self.character.equipment_ui_open and self.equipment_window_rect:
            if self.equipment_window_rect.collidepoint(mouse_pos):
                self.handle_equipment_click(mouse_pos, shift_held)
                return

        # Crafting UI
        if self.character.crafting_ui_open and self.crafting_window_rect:
            if self.crafting_window_rect.collidepoint(mouse_pos):
                self.handle_craft_click(mouse_pos)
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
                            if item_stack and item_stack.is_equipment():
                                equipment = item_stack.get_equipment()
                                if equipment:  # FIX #4: Check equipment exists before trying to equip
                                    success, msg = self.character.try_equip_from_inventory(idx)
                                    if success:
                                        self.add_notification(f"Equipped {equipment.name}", (100, 255, 100))
                                    else:
                                        self.add_notification(f"Cannot equip: {msg}", (255, 100, 100))
                                else:
                                    self.add_notification("Invalid equipment data", (255, 100, 100))
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

        station = self.world.get_station_at(world_pos)
        if station:
            self.character.interact_with_station(station)
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

    def handle_craft_click(self, mouse_pos: Tuple[int, int]):
        if not self.crafting_window_rect or not self.crafting_recipes:
            return
        rx = mouse_pos[0] - self.crafting_window_rect.x
        ry = mouse_pos[1] - self.crafting_window_rect.y

        for i, recipe in enumerate(self.crafting_recipes):
            btn_top = 70 + (i * 90)
            if btn_top <= ry <= btn_top + 80:
                self.craft_item(recipe)
                break

    def craft_item(self, recipe: Recipe):
        recipe_db = RecipeDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()

        if not recipe_db.can_craft(recipe, self.character.inventory):
            self.add_notification("Not enough materials!", (255, 100, 100))
            return

        # Handle enchanting recipes differently
        if recipe.is_enchantment:
            self._apply_enchantment(recipe)
            return

        # Regular crafting
        if recipe_db.consume_materials(recipe, self.character.inventory):
            activity_map = {
                'smithing': 'smithing', 'refining': 'refining', 'alchemy': 'alchemy',
                'engineering': 'engineering', 'adornments': 'enchanting'
            }
            activity_type = activity_map.get(recipe.station_type, 'smithing')
            self.character.activities.record_activity(activity_type, 1)

            xp_reward = 20 * recipe.station_tier
            self.character.leveling.add_exp(xp_reward)

            new_title = self.character.titles.check_for_title(
                activity_type, self.character.activities.get_count(activity_type)
            )
            if new_title:
                self.add_notification(f"Title Earned: {new_title.name}!", (255, 215, 0))

            # Add to inventory
            self.character.inventory.add_item(recipe.output_id, recipe.output_qty)

            # Get proper name
            if equip_db.is_equipment(recipe.output_id):
                equipment = equip_db.create_equipment_from_id(recipe.output_id)
                out_name = equipment.name if equipment else recipe.output_id
            else:
                out_mat = mat_db.get_material(recipe.output_id)
                out_name = out_mat.name if out_mat else recipe.output_id

            self.add_notification(f"Crafted {out_name} x{recipe.output_qty}", (100, 255, 100))

    def _apply_enchantment(self, recipe: Recipe):
        """Apply an enchantment to an item in inventory"""
        recipe_db = RecipeDatabase.get_instance()

        # Find compatible items in inventory
        compatible_items = []
        for i, slot in enumerate(self.character.inventory.slots):
            if slot and slot.is_equipment() and slot.equipment_data:
                equipment = slot.equipment_data
                can_apply, reason = equipment.can_apply_enchantment(
                    recipe.output_id, recipe.applicable_to, recipe.effect
                )
                if can_apply:
                    compatible_items.append((i, slot))

        if not compatible_items:
            self.add_notification("No compatible items found!", (255, 100, 100))
            return

        # For now, apply to the first compatible item found
        # TODO: Add UI for item selection
        slot_idx, slot = compatible_items[0]
        equipment = slot.equipment_data

        # Consume materials
        if not recipe_db.consume_materials(recipe, self.character.inventory):
            self.add_notification("Failed to consume materials!", (255, 100, 100))
            return

        # Apply enchantment to the equipment instance stored in inventory
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
        self.world.update(dt)
        self.damage_numbers = [d for d in self.damage_numbers if d.update(dt)]
        self.notifications = [n for n in self.notifications if n.update(dt)]

    def render(self):
        self.screen.fill(Config.COLOR_BACKGROUND)
        self.renderer.render_world(self.world, self.camera, self.character, self.damage_numbers)
        self.renderer.render_ui(self.character, self.mouse_pos)
        self.renderer.render_inventory_panel(self.character, self.mouse_pos)

        self.renderer.render_notifications(self.notifications)

        if self.character.class_selection_open:
            result = self.renderer.render_class_selection_ui(self.character, self.mouse_pos)
            if result:
                self.class_selection_rect, self.class_buttons = result
        else:
            self.class_selection_rect = None
            self.class_buttons = []

            if self.character.crafting_ui_open:
                result = self.renderer.render_crafting_ui(self.character, self.mouse_pos)
                if result:
                    self.crafting_window_rect, self.crafting_recipes = result
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

            if self.character.equipment_ui_open:
                result = self.renderer.render_equipment_ui(self.character, self.mouse_pos)
                if result:
                    self.equipment_window_rect, self.equipment_rects = result
            else:
                self.equipment_window_rect = None
                self.equipment_rects = {}

        pygame.display.flip()

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