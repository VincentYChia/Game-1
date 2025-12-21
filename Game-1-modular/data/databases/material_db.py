"""Material Database - manages stackable materials, consumables, and devices"""

import json
from pathlib import Path
from typing import Dict, Optional
from data.models.materials import MaterialDefinition


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
                material_id = mat_data.get('materialId', '')
                category = mat_data.get('category', 'unknown')

                # Auto-generate icon path if not provided
                icon_path = mat_data.get('iconPath')
                if not icon_path and material_id:
                    # Determine subdirectory based on category
                    if category in ['consumable']:
                        subdir = 'consumables'
                    elif category in ['device']:
                        subdir = 'devices'
                    elif category in ['station']:
                        subdir = 'stations'
                    else:
                        subdir = 'materials'
                    icon_path = f"{subdir}/{material_id}.png"

                flags = mat_data.get('flags', {})
                mat = MaterialDefinition(
                    material_id=material_id,
                    name=mat_data.get('name', ''),
                    tier=mat_data.get('tier', 1),
                    category=category,
                    rarity=mat_data.get('rarity', 'common'),
                    description=mat_data.get('description', ''),
                    max_stack=mat_data.get('maxStack', 99),
                    properties=mat_data.get('properties', {}),
                    icon_path=icon_path,
                    placeable=flags.get('placeable', False),
                    item_type=mat_data.get('type', ''),
                    item_subtype=mat_data.get('subtype', ''),
                    effect=mat_data.get('effect', ''),
                    effect_tags=mat_data.get('effectTags', []),
                    effect_params=mat_data.get('effectParams', {})
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
                        material_id = item_data.get('itemId', '')  # Note: refining JSON uses itemId!
                        category = item_data.get('type', 'unknown')

                        # Auto-generate icon path if not provided
                        icon_path = item_data.get('iconPath')
                        if not icon_path and material_id:
                            icon_path = f"materials/{material_id}.png"

                        mat = MaterialDefinition(
                            material_id=material_id,
                            name=item_data.get('name', ''),
                            tier=item_data.get('tier', 1),
                            category=category,
                            rarity=item_data.get('rarity', 'common'),
                            description=item_data.get('metadata', {}).get('narrative', ''),
                            max_stack=item_data.get('stackSize', 256),
                            properties={},
                            icon_path=icon_path
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
        """Load stackable and placeable items (consumables, devices, stations, etc.) from item files

        Args:
            filepath: Path to the JSON file
            categories: List of categories to load (e.g., ['consumable', 'device', 'station'])
                       If None, loads all items with stackable=True or placeable=True flag
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
                        is_placeable = flags.get('placeable', False)

                        # Load if category matches (or no filter) AND (item is stackable OR placeable)
                        should_load = (is_stackable or is_placeable) and (
                            categories is None or category in categories
                        )

                        if should_load:
                            material_id = item_data.get('itemId', '')
                            category = item_data.get('category', '')

                            # Auto-generate icon path if not provided
                            icon_path = item_data.get('iconPath')
                            if not icon_path and material_id:
                                # Determine subdirectory based on category
                                if category in ['consumable']:
                                    subdir = 'consumables'
                                elif category in ['device']:
                                    subdir = 'devices'
                                elif category in ['station']:
                                    subdir = 'stations'
                                else:
                                    subdir = 'materials'
                                icon_path = f"{subdir}/{material_id}.png"

                            mat = MaterialDefinition(
                                material_id=material_id,
                                name=item_data.get('name', ''),
                                tier=item_data.get('tier', 1),
                                category=category,
                                rarity=item_data.get('rarity', 'common'),
                                description=item_data.get('metadata', {}).get('narrative', ''),
                                max_stack=item_data.get('stackSize', 99),
                                properties={},
                                icon_path=icon_path,
                                placeable=flags.get('placeable', False),
                                item_type=item_data.get('type', ''),
                                item_subtype=item_data.get('subtype', ''),
                                effect=item_data.get('effect', ''),
                                effect_tags=item_data.get('effectTags', []),
                                effect_params=item_data.get('effectParams', {})
                            )
                            if mat.material_id and mat.material_id not in self.materials:
                                self.materials[mat.material_id] = mat
                                count += 1

            print(f"✓ Loaded {count} stackable items from {filepath} (categories: {categories})")
            return True
        except Exception as e:
            print(f"⚠ Error loading stackable items from {filepath}: {e}")
            return False
