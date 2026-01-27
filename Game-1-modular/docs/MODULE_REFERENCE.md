# Module Reference Guide

**Last Updated**: 2026-01-27

Complete documentation of every Python module in Game-1-Modular.

**Purpose**: Quick reference for understanding what each file does and how to use it.

**Statistics**: 136 Python files, ~62,380 lines of code

---

## Table of Contents

1. [Entry Point](#entry-point)
2. [Core Systems](#core-systems)
3. [Data Models](#data-models)
4. [Data Databases](#data-databases)
5. [Entities](#entities)
6. [Entity Components](#entity-components)
7. [Game Systems](#game-systems)
8. [LLM Integration](#llm-integration) *(NEW)*
9. [Rendering](#rendering)
10. [Crafting Subdisciplines](#crafting-subdisciplines)
11. [Combat System](#combat-system)
12. [Tools & Utilities](#tools--utilities)

---

## Entry Point

### main.py
**Path**: `/main.py`
**Lines**: ~25
**Dependencies**: `core.game_engine`

**Purpose**: Application entry point. Initializes and starts the game engine.

**Key Features**:
- Sets up Python path for imports
- Creates GameEngine instance
- Starts game loop
- Handles top-level exceptions

**Usage**:
```bash
python main.py
```

**Code Structure**:
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.game_engine import GameEngine

if __name__ == "__main__":
    game = GameEngine()
    game.run()
```

---

## Core Systems

### core/config.py
**Lines**: ~75
**Dependencies**: None

**Purpose**: Global game configuration constants.

**Key Constants**:
- Screen dimensions (1600x900)
- World settings (100x100, chunk size 16)
- Tile size (32 pixels)
- Inventory layout
- Color palette
- Rarity colors
- Debug mode flags

**Usage**:
```python
from core.config import Config

width = Config.SCREEN_WIDTH
slot_size = Config.INVENTORY_SLOT_SIZE
```

**Design Notes**:
- No runtime state, only constants
- Modify here to change game-wide behavior
- Single source of truth for all numeric constants

---

### core/game_engine.py
**Lines**: ~7,817
**Dependencies**: Everything (orchestrator)

**Purpose**: Main game engine that coordinates all systems.

**Responsibilities**:
1. Initialize pygame and all databases
2. Create world and character
3. Run main game loop (event → update → render)
4. Handle all input events
5. Manage game state (menus, minigames, dialogs)
6. Coordinate rendering
7. Save/load game state
8. Render all 5 crafting minigames
9. Handle LLM item generation callbacks

**Key Methods**:
```python
__init__():  # Initialize everything (189 lines)
run():  # Main game loop
handle_events():  # Process keyboard/mouse input (300+ lines)
handle_mouse_click():  # Handle all click interactions (230+ lines)
handle_right_click():  # Right-click actions (consumables)
handle_mouse_release():  # Drag-and-drop completion
update(delta_time):  # Update game state
render():  # Delegate rendering to Renderer
craft_item():  # Start crafting (instant or minigame)
_start_minigame():  # Initialize minigame
_complete_minigame():  # Handle minigame results
_render_minigame():  # Render active minigame
handle_npc_interaction():  # Show NPC dialog
```

**State Variables**:
```python
self.world: WorldSystem
self.character: Character
self.combat_manager: CombatManager
self.renderer: Renderer
self.camera: Camera

# UI State
self.start_menu_open: bool
self.active_minigame: Optional[Any]
self.npc_dialogue_open: bool
self.enchantment_selection_active: bool

# Interaction state
self.last_click_time: int  # For double-click detection
self.last_clicked_slot: Optional[int]
```

**Event Flow**:
1. `handle_events()` → keyboard/mouse/wheel events
2. `update()` → physics, AI, timers
3. `render()` → draw everything

---

### core/camera.py
**Lines**: ~40
**Dependencies**: `core.config`

**Purpose**: Viewport camera for scrolling world view.

**Key Methods**:
```python
__init__(viewport_width, viewport_height):
    # Create camera with viewport size

center_on(world_x, world_y):
    # Center camera on world position

world_to_screen(world_x, world_y) -> (screen_x, screen_y):
    # Convert world coords to screen coords
```

**Coordinate Systems**:
- **World**: Tile-based (0-99 for 100x100 world)
- **Screen**: Pixel-based (0-1600 width, 0-900 height)

---

### core/testing.py
**Lines**: ~180
**Dependencies**: Game engine and all systems

**Purpose**: Automated testing framework for crafting system.

**Key Methods**:
```python
run_all_tests():  # Run complete test suite
test_database_loading():  # Test database init
test_recipe_loading():  # Test recipe loading
test_placement_data():  # Test grid layouts
```

**Usage**:
```python
tester = CraftingSystemTester(game_engine)
tester.run_all_tests()
```

---

### core/notifications.py
**Lines**: ~50
**Dependencies**: pygame, config

**Purpose**: (Note: Appears to be unused stub - notifications handled in game_engine)

---

## Data Models

All models use Python dataclasses for type safety and immutability.

### data/models/world.py
**Lines**: ~150
**Dependencies**: None (pure data)

**Key Classes**:
```python
@dataclass
class Position:
    x: float
    y: float
    z: float = 0.0

class TileType(Enum):
    GRASS = 0
    STONE = 1
    WATER = 2
    SAND = 3
    SNOW = 4

@dataclass
class WorldTile:
    tile_type: TileType
    walkable: bool

class ResourceType(Enum):
    TREE = 0
    STONE_NODE = 1
    METAL_ORE = 2

@dataclass
class LootDrop:
    item_id: str
    quantity: Tuple[int, int]  # (min, max)
    weight: float  # Probability weight

class ChunkType(Enum):
    GRASSLAND = "grassland"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    DESERT = "desert"

class StationType(Enum):
    SMITHING = "smithing"
    ALCHEMY = "alchemy"
    REFINING = "refining"
    ENGINEERING = "engineering"
    ENCHANTING = "enchanting"

@dataclass
class CraftingStation:
    station_type: StationType
    position: Position
    interaction_radius: float = 2.0
```

---

### data/models/materials.py
**Lines**: ~50
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class MaterialDefinition:
    item_id: str
    name: str
    category: str  # "ore", "log", "craftable", "consumable"
    tier: int  # 1-4
    max_stack: int  # Stack size
    rarity: str  # "common", "uncommon", "rare", "epic", "legendary"
    description: str  # Flavor text
```

**Usage**:
```python
copper_ore = MaterialDefinition(
    item_id="copper_ore",
    name="Copper Ore",
    category="ore",
    tier=1,
    max_stack=99,
    rarity="common",
    description="Basic metal ore"
)
```

---

### data/models/equipment.py
**Lines**: ~200
**Dependencies**: Type hints only

**Key Classes**:
```python
@dataclass
class EquipmentItem:
    item_id: str
    name: str
    tier: int  # 1-4
    rarity: str
    slot: str  # "mainHand", "helmet", "pickaxe", etc.

    # Combat stats
    damage: Tuple[int, int]  # (min, max) for weapons
    defense: int  # For armor

    # Durability
    durability_current: int
    durability_max: int

    # Modifiers
    attack_speed: float  # 1.0 = normal
    weight: float  # Affects movement
    range: float  # Attack range

    # Requirements
    requirements: Dict[str, int]  # {"level": 5, "strength": 10}

    # Bonuses
    bonuses: Dict[str, float]  # {"critChance": 0.1}

    # Enchantments
    enchantments: List[Tuple[str, int]]  # [(enchant_id, level)]
    enchantment_slots: int

    # Quality (for crafted items)
    quality: str  # "poor", "normal", "good", "excellent"
    crafted_by: Optional[str]

    # Methods
    def can_equip(self, character) -> Tuple[bool, str]:
        """Check if character meets requirements"""

    def get_actual_damage(self) -> Tuple[int, int]:
        """Get damage with enchantments"""

    def get_defense_with_enchantments(self) -> int:
        """Get defense with enchantments"""
```

---

### data/models/skills.py
**Lines**: ~180
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class SkillEffect:
    type: str  # "damage", "heal", "buff", "debuff"
    value: float  # Base value
    duration: float  # For buffs/debuffs
    stat_affected: Optional[str]  # "strength", "defense", etc.

@dataclass
class SkillCost:
    mana: int
    health: int
    stamina: int
    cooldown: float  # Seconds

@dataclass
class SkillEvolution:
    next_skill: str  # ID of upgraded skill
    unlock_level: int  # Skill level required

@dataclass
class SkillRequirements:
    character_level: int
    stats: Dict[str, int]  # {"strength": 10}
    prerequisite_skills: List[str]

@dataclass
class SkillDefinition:
    skill_id: str
    name: str
    description: str
    effects: List[SkillEffect]
    cost: SkillCost
    requirements: SkillRequirements
    evolution: Optional[SkillEvolution]
    rarity: str
    tier: int

@dataclass
class PlayerSkill:
    """Instance of a learned skill"""
    skill_id: str
    level: int  # 1-10
    experience: int
    current_cooldown: float
    is_equipped: bool
    hotbar_slot: Optional[int]  # 0-4

    def get_definition(self) -> Optional[SkillDefinition]:
        """Get skill definition from database"""

    def get_exp_for_next_level(self) -> int:
        """Get EXP needed for next level"""

    def add_exp(self, amount: int) -> tuple:
        """Add EXP and check for level up"""

    def get_level_scaling_bonus(self) -> float:
        """Get damage/effectiveness bonus from level"""
```

---

### data/models/recipes.py
**Lines**: ~80
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class Recipe:
    recipe_id: str
    output_id: str  # Item created
    output_quantity: int
    discipline: str  # "smithing", "alchemy", etc.
    tier: int  # 1-4
    inputs: List[Dict[str, Any]]  # [{"materialId": "copper_ore", "quantity": 5}]
    base_craft_time: float  # Base seconds to craft

@dataclass
class PlacementData:
    """Grid-based crafting layout"""
    recipe_id: str
    grid_width: int
    grid_height: int
    placements: List[Dict[str, Any]]  # [{"materialId": "...", "x": 0, "y": 1}]
```

---

### data/models/titles.py
**Lines**: ~50
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class TitleDefinition:
    title_id: str
    name: str
    description: str
    unlock_requirements: Dict[str, int]  # {"harvesting": 100, "combat": 50}
    bonuses: Dict[str, float]  # {"strength": 5, "defense": 3}
```

---

### data/models/classes.py
**Lines**: ~60
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class ClassDefinition:
    class_id: str
    name: str
    description: str
    unlock_requirements: Dict[str, int]  # {"level": 10}
    stat_multipliers: Dict[str, float]  # {"strength": 1.2, "intelligence": 0.8}
    starting_skills: List[str]  # Skill IDs granted on selection
```

---

### data/models/npcs.py
**Lines**: ~40
**Dependencies**: world (Position)

**Key Classes**:
```python
@dataclass
class NPCDefinition:
    npc_id: str
    name: str
    position: Position
    sprite_color: Tuple[int, int, int]
    interaction_radius: float
    dialogue_lines: List[str]
    quests: List[str]  # Quest IDs this NPC offers
```

---

### data/models/quests.py
**Lines**: ~90
**Dependencies**: None

**Key Classes**:
```python
@dataclass
class QuestObjective:
    objective_type: str  # "gather", "combat", "explore"
    items: List[Dict[str, Any]]  # [{"item_id": "oak_log", "quantity": 5}]
    enemies_killed: int  # For combat quests

@dataclass
class QuestRewards:
    experience: int
    gold: int
    items: List[Dict[str, Any]]
    skills: List[str]  # Skill IDs to unlock
    title: Optional[str]  # Title ID to grant
    health_restore: int
    mana_restore: int

@dataclass
class QuestDefinition:
    quest_id: str
    title: str
    description: str
    objectives: QuestObjective
    rewards: QuestRewards
    prerequisites: List[str]  # Quest IDs that must be complete
```

---

## Data Databases

All databases use Singleton pattern.

### data/databases/material_db.py
**Lines**: ~80
**Dependencies**: `data.models.materials`

**Purpose**: Manage all material definitions loaded from JSON.

**Key Methods**:
```python
@classmethod
def get_instance() -> MaterialDatabase:
    """Get singleton instance"""

def load_from_file(filepath: str):
    """Load materials from JSON file"""

def get_material(item_id: str) -> Optional[MaterialDefinition]:
    """Lookup material by ID"""
```

**Usage**:
```python
mat_db = MaterialDatabase.get_instance()
mat_db.load_from_file("items.JSON/items-materials-1.JSON")
copper = mat_db.get_material("copper_ore")
```

---

### data/databases/equipment_db.py
**Lines**: ~280
**Dependencies**: `data.models.equipment`

**Purpose**: Manage equipment definitions and create equipment instances.

**Key Methods**:
```python
def load_from_file(filepath: str):
    """Load equipment from JSON (filters by category='equipment')"""

def is_equipment(item_id: str) -> bool:
    """Check if item ID is equipment"""

def create_equipment_from_id(item_id: str) -> Optional[EquipmentItem]:
    """Create EquipmentItem instance with calculated stats"""

def _calculate_weapon_damage(...) -> Tuple[int, int]:
    """Calculate damage based on tier/type/multipliers"""

def _calculate_armor_defense(...) -> int:
    """Calculate defense based on tier/slot/multipliers"""
```

**Design Notes**:
- Calculates stats dynamically from tier + type + multipliers
- Supports both old format (explicit stats) and new format (formulas)
- Creates placeholder equipment if JSON loading fails

---

### data/databases/recipe_db.py
**Lines**: ~180
**Dependencies**: `data.models.recipes`, `core.config`

**Purpose**: Manage crafting recipes.

**Key Methods**:
```python
def load_from_files():
    """Load all recipe JSON files"""

def get_recipe(recipe_id: str) -> Optional[Recipe]:
    """Get recipe by ID"""

def get_recipes_by_discipline(discipline: str, tier: int) -> List[Recipe]:
    """Get filtered recipes for crafting UI"""

def can_craft(recipe: Recipe, inventory) -> bool:
    """Check if inventory has materials (respects debug mode)"""

def consume_materials(recipe: Recipe, inventory) -> bool:
    """Remove materials from inventory (respects debug mode)"""
```

**Debug Mode Integration**:
```python
if Config.DEBUG_INFINITE_RESOURCES:
    return True  # Always can craft in debug mode
```

---

### data/databases/skill_db.py
**Lines**: ~200
**Dependencies**: `data.models.skills`

**Purpose**: Manage skill definitions.

**Key Methods**:
```python
def load_from_file():
    """Load skills from JSON"""

def get_skill(skill_id: str) -> Optional[SkillDefinition]:
    """Lookup skill by ID"""

def _create_placeholders():
    """Create basic skills if loading fails"""
```

---

### data/databases/title_db.py
**Lines**: ~120
**Dependencies**: `data.models.titles`

**Purpose**: Manage title definitions.

**Key Methods**:
```python
def load_from_file(filepath: str):
    """Load titles from JSON"""

def check_unlock(activity_counts: Dict[str, int]) -> Optional[TitleDefinition]:
    """Find unlockable title based on activities"""
```

---

### data/databases/class_db.py
**Lines**: ~100
**Dependencies**: `data.models.classes`

**Purpose**: Manage class definitions.

**Key Methods**:
```python
def load_from_file(filepath: str):
    """Load classes from JSON"""

def get_class(class_id: str) -> Optional[ClassDefinition]:
    """Lookup class by ID"""
```

---

### data/databases/npc_db.py
**Lines**: ~150
**Dependencies**: `data.models.npcs`, `data.models.quests`

**Purpose**: Manage NPCs and quests (combined).

**Key Methods**:
```python
def load_from_files():
    """Load NPCs and quests (supports v1.0 and v2.0 formats)"""

def get_npc(npc_id: str) -> Optional[NPCDefinition]:
    """Lookup NPC by ID"""

def get_quest(quest_id: str) -> Optional[QuestDefinition]:
    """Lookup quest by ID"""
```

**Format Support**:
- v1.0: Simple dialogue_lines array
- v2.0: Enhanced dialogue object with greetings/responses

---

### data/databases/placement_db.py
**Lines**: ~80
**Dependencies**: `data.models.recipes`

**Purpose**: Manage grid-based crafting layouts.

**Key Methods**:
```python
def load_from_files():
    """Load placement data from JSON"""

def get_placement(recipe_id: str) -> Optional[PlacementData]:
    """Get placement layout for recipe"""
```

---

### data/databases/translation_db.py
**Lines**: ~100
**Dependencies**: None

**Purpose**: Multi-language translation support.

**Key Methods**:
```python
def load_from_files():
    """Load translation files"""

def get_text(key: str, lang: str = "en") -> str:
    """Get translated text, fallback to English"""
```

**Usage**:
```python
trans_db = TranslationDatabase.get_instance()
text = trans_db.get_text("ui.inventory.title", "en")
```

---

## Entities

### entities/character.py
**Lines**: ~740
**Dependencies**: All components, all databases

**Purpose**: Main player character with all game capabilities.

**Composition**:
```python
class Character:
    # Core attributes
    position: Position
    facing: str
    movement_speed: float
    interaction_range: float

    # Components (mix-and-match capabilities)
    stats: CharacterStats
    leveling: LevelingSystem
    skills: SkillManager
    buffs: BuffManager
    equipment: EquipmentManager
    inventory: Inventory
    activities: ActivityTracker
    encyclopedia: Encyclopedia
    quests: QuestManager
    titles: TitleSystem
    class_system: ClassSystem

    # Health/Mana
    health: float
    max_health: float
    mana: float
    max_mana: float

    # UI state
    crafting_ui_open: bool
    stats_ui_open: bool
    equipment_ui_open: bool
    skills_ui_open: bool
    class_selection_open: bool
    active_station: Optional[CraftingStation]
```

**Key Methods**:
```python
def recalculate_stats():
    """Recalculate all stats from equipment/titles/class"""

def try_equip_from_inventory(slot_index: int) -> Tuple[bool, str]:
    """Equip item from inventory slot"""

def try_unequip_to_inventory(slot_name: str) -> Tuple[bool, str]:
    """Unequip to inventory"""

def take_damage(damage: float):
    """Take damage, handle death"""

def save_to_file(filename: str) -> bool:
    """Save character to JSON"""

@staticmethod
def load_from_file(filename: str) -> Optional['Character']:
    """Load character from JSON"""
```

---

### entities/tool.py
**Lines**: ~30
**Dependencies**: None

**Purpose**: Legacy tool system (now replaced by equipment system).

**Note**: Kept for compatibility but tools are now handled as equipment items with slot="axe" or slot="pickaxe".

---

### entities/damage_number.py
**Lines**: ~50
**Dependencies**: pygame

**Purpose**: Floating damage numbers displayed during combat.

**Key Attributes**:
```python
class DamageNumber:
    damage: int
    position: Tuple[int, int]
    color: Tuple[int, int, int]
    lifetime: float
    velocity_y: float  # Floats upward
```

---

## Entity Components

All components are pluggable systems attached to Character.

### entities/components/stats.py
**Lines**: ~60
**Dependencies**: None

**Purpose**: Character base stats.

```python
class CharacterStats:
    # Base stats
    strength: int = 10
    defense: int = 10
    vitality: int = 10
    luck: int = 10
    agility: int = 10
    intelligence: int = 10

    # Derived stats (calculated from base)
    max_health: int = 100
    max_mana: int = 100
    critical_chance: float = 0.05
    dodge_chance: float = 0.05
```

---

### entities/components/leveling.py
**Lines**: ~100
**Dependencies**: None

**Purpose**: Experience and leveling system.

```python
class LevelingSystem:
    level: int = 1
    max_level: int = 100
    current_exp: int = 0
    unallocated_stat_points: int = 0

    def add_exp(self, amount: int) -> bool:
        """Add EXP, return True if leveled up"""

    def get_exp_for_next_level(self) -> int:
        """Get EXP required for next level (exponential)"""
```

---

### entities/components/inventory.py
**Lines**: ~200
**Dependencies**: `data.databases`, `data.models`

**Purpose**: Item storage and management.

```python
@dataclass
class ItemStack:
    item_id: str
    quantity: int
    max_stack: int
    equipment_data: Optional[EquipmentItem]
    rarity: str
    crafted_stats: Optional[Dict]

    def is_equipment(self) -> bool:
        """Check if this is equipment"""

    def get_equipment(self) -> Optional[EquipmentItem]:
        """Get equipment instance"""

class Inventory:
    slots: List[Optional[ItemStack]]
    max_slots: int = 30
    dragging_slot: Optional[int]
    dragging_stack: Optional[ItemStack]

    def add_item(item_id: str, quantity: int, equipment_instance=None) -> bool:
        """Add item to inventory"""

    def remove_item(item_id: str, quantity: int) -> bool:
        """Remove item from inventory"""

    def get_item_count(item_id: str) -> int:
        """Count total quantity of item"""

    def start_drag(slot_index: int):
        """Start drag-and-drop"""

    def end_drag(target_slot: int):
        """Complete drag-and-drop"""

    def cancel_drag():
        """Cancel drag-and-drop"""
```

---

### entities/components/equipment_manager.py
**Lines**: ~110
**Dependencies**: `data.models.equipment`

**Purpose**: Manage equipped items.

```python
class EquipmentManager:
    slots: Dict[str, Optional[EquipmentItem]] = {
        'mainHand': None,
        'offHand': None,
        'helmet': None,
        'chestplate': None,
        'leggings': None,
        'boots': None,
        'gauntlets': None,
        'accessory': None,
        'axe': None,
        'pickaxe': None,
    }

    def equip(item: EquipmentItem, character) -> Tuple[Optional[EquipmentItem], str]:
        """Equip item, return old item and status"""

    def unequip(slot: str, character) -> Optional[EquipmentItem]:
        """Unequip item from slot"""

    def is_equipped(item_id: str) -> bool:
        """Check if item is equipped"""

    def get_total_defense() -> int:
        """Sum defense from all armor"""

    def get_weapon_damage() -> Tuple[int, int]:
        """Get equipped weapon damage"""

    def get_stat_bonuses() -> Dict[str, float]:
        """Get stat bonuses from all equipment"""
```

---

### entities/components/skill_manager.py
**Lines**: ~709
**Dependencies**: `data.databases.skill_db`, `data.models.skills`

**Purpose**: Manage learned skills, hotbar, and class affinity bonuses.

```python
class SkillManager:
    learned_skills: Dict[str, PlayerSkill]
    active_slots: List[Optional[str]]  # 5 hotbar slots
    global_cooldown: float = 0.0

    def learn_skill(skill_id: str, character, skip_checks=False) -> bool:
        """Learn new skill"""

    def activate_skill(slot: int, character) -> bool:
        """Activate skill from hotbar"""

    def assign_to_hotbar(skill_id: str, slot: int):
        """Assign skill to hotbar slot"""

    def update_cooldowns(delta_time: float):
        """Reduce cooldowns"""

    def get_affinity_bonus(skill_id: str, character) -> float:
        """Calculate class affinity bonus for skill"""
```

---

### entities/components/buffs.py
**Lines**: ~100
**Dependencies**: None

```python
@dataclass
class ActiveBuff:
    buff_id: str
    stat_affected: str
    value: float
    remaining_time: float

class BuffManager:
    active_buffs: List[ActiveBuff]

    def add_buff(buff: ActiveBuff):
        """Add buff (refreshes if already active)"""

    def update(delta_time: float):
        """Update buff timers, remove expired"""

    def get_stat_bonus(stat: str) -> float:
        """Get total bonus for stat from all buffs"""
```

---

### entities/components/activity_tracker.py
**Lines**: ~50
**Dependencies**: None

**Purpose**: Track player activities for titles/quests.

```python
class ActivityTracker:
    activities: Dict[str, int] = {}  # {"harvesting": 42, "combat": 15}

    def increment(activity_type: str, amount: int = 1):
        """Increment activity counter"""

    def get_count(activity_type: str) -> int:
        """Get activity count"""
```

---

## Game Systems

### systems/world_system.py
**Lines**: ~400
**Dependencies**: `data.models.world`, `systems.natural_resource`

**Purpose**: World generation and management.

```python
class WorldSystem:
    tiles: Dict[Tuple[int, int], WorldTile]  # (x, y) -> tile
    resources: List[NaturalResource]
    crafting_stations: List[CraftingStation]
    npcs: List['NPC']

    def generate_world():
        """Generate 100x100 world with biomes"""

    def get_tile(x: int, y: int) -> WorldTile:
        """Get tile at position"""

    def spawn_resources():
        """Place trees, ore nodes"""

    def spawn_crafting_stations():
        """Place smithing, alchemy stations"""

    def spawn_npcs(npc_db: NPCDatabase):
        """Create NPCs from database"""

    def update(delta_time: float):
        """Update resources (respawn timers)"""
```

---

### systems/natural_resource.py
**Lines**: ~120
**Dependencies**: `data.models.world`

**Purpose**: Individual resource node (tree, ore).

```python
class NaturalResource:
    resource_type: ResourceType
    position: Position
    tier: int
    health: int
    max_health: int
    loot_table: List[LootDrop]
    respawn_time: float
    current_respawn: float

    def take_damage(amount: int):
        """Damage resource"""

    def is_destroyed() -> bool:
        """Check if health <= 0"""

    def drop_loot(character):
        """Add loot to character inventory"""

    def update(delta_time: float):
        """Handle respawn timer"""
```

---

## Combat System

### Combat/combat_manager.py
**Lines**: ~1,655
**Dependencies**: `entities.character`, `entities.status_effect`, `core.effect_executor`

**Purpose**: Full combat system with damage pipeline, enchantments, and status effects.

```python
class CombatManager:
    character: Character
    active_enemies: List[Enemy]
    spawn_cooldown: float

    def calculate_damage(base_damage: int, attacker, defender) -> int:
        """Full damage pipeline with multipliers, enchantments, defense."""

    def apply_enchantment_effects(weapon, target, damage: int):
        """Apply weapon enchantments (Fire Aspect, Lifesteal, etc.)."""

    def spawn_initial_enemies(center: Tuple, count: int):
        """Spawn enemies around position"""

    def update(delta_time: float, character_pos: Tuple):
        """Update AI, attacks, respawns, status effects"""
```

**Damage Pipeline**:
```
Base Damage (weapon)
  × Hand Type Bonus (+10-20%)
  × Strength Multiplier (1.0 + STR × 0.05)
  × Skill Buff Bonus (+50% to +400%)
  × Class Affinity Bonus (up to +20%)
  × Title Bonus
  × Weapon Tag Bonuses
  × Critical Hit (2x if triggered)
  - Enemy Defense (max 75% reduction)
  = Final Damage
```

**Implemented Enchantments** (9 fully working):
| Enchantment | Type | Trigger |
|-------------|------|---------|
| Sharpness | damage_multiplier | Passive |
| Protection | defense_multiplier | Passive |
| Fire Aspect | damage_over_time | On hit |
| Lifesteal | lifesteal | On hit |
| Knockback | knockback | On hit |
| Chain Damage | chain_damage | On hit |
| Thorns | reflect_damage | On hit received |
| Unbreaking | durability_multiplier | Passive |
| Slow (Frost) | slow | On hit |

---

### Combat/enemy.py
**Lines**: ~867
**Dependencies**: `data.databases`, `data.models.world`

**Purpose**: Enemy entities, AI behavior, and loot drops.

```python
class Enemy:
    position: Tuple[float, float]
    health: int
    max_health: int
    damage: int
    speed: float
    attack_range: float
    attack_cooldown: float
    loot_table: List[LootDrop]

    def update(delta_time: float, target_pos: Tuple):
        """Move toward and attack player"""

    def take_damage(amount: int):
        """Receive damage, check for death"""

    def drop_loot(character):
        """Add loot to player inventory on death"""

class EnemyDatabase:
    """Load enemy definitions from JSON."""
```

---

### systems/quest_system.py
**Lines**: ~160
**Dependencies**: `data.databases.npc_db`, `data.models.quests`

**Purpose**: Quest tracking and progression.

```python
class Quest:
    quest_def: QuestDefinition
    baseline_inventory: Dict[str, int]  # Inventory snapshot on accept
    baseline_combat_kills: int  # Combat count on accept

    def is_complete(character) -> bool:
        """Check if objectives met"""

    def consume_items(character) -> bool:
        """Remove quest items from inventory"""

    def grant_rewards(character) -> List[str]:
        """Grant XP, items, skills, titles"""

class QuestManager:
    active_quests: Dict[str, Quest]  # Max 3 active
    completed_quests: List[str]  # Quest IDs

    def start_quest(quest_def: QuestDefinition, character) -> bool:
        """Accept new quest"""

    def complete_quest(quest_id: str, character) -> Tuple[bool, List[str]]:
        """Complete quest and grant rewards"""

    def has_completed(quest_id: str) -> bool:
        """Check if quest is complete"""
```

---

### systems/encyclopedia.py
**Lines**: ~150
**Dependencies**: Databases for lookups

**Purpose**: Discovery tracking and game guide.

```python
class Encyclopedia:
    is_open: bool
    current_tab: str  # "guide", "materials", "equipment", "skills", "titles"

    discovered_materials: Set[str]
    discovered_equipment: Set[str]
    discovered_skills: Set[str]

    def toggle():
        """Open/close encyclopedia"""

    def discover_material(item_id: str):
        """Mark material as discovered"""

    def get_game_guide_text() -> List[str]:
        """Get game guide content"""
```

---

### systems/title_system.py
**Lines**: ~80
**Dependencies**: `data.databases.title_db`

**Purpose**: Title unlocking and management.

```python
class TitleSystem:
    earned_titles: List[str]  # Title IDs
    active_title: Optional[str]

    def check_for_title(activity_type: str, count: int) -> Optional[TitleDefinition]:
        """Check if activity unlocks new title"""

    def earn_title(title_id: str):
        """Grant title to player"""

    def set_active_title(title_id: str):
        """Select active title"""

    def get_total_bonus(bonus_type: str) -> float:
        """Sum bonus from all earned titles"""
```

---

### systems/class_system.py
**Lines**: ~100
**Dependencies**: `data.databases.class_db`

**Purpose**: Class selection and bonuses.

```python
class ClassSystem:
    current_class: Optional[str]  # Class ID
    unlocked_classes: List[str]

    def select_class(class_id: str, character) -> bool:
        """Select class (grants starting skills)"""

    def get_stat_multipliers() -> Dict[str, float]:
        """Get class stat multipliers"""

    def can_select_class(class_id: str, character) -> Tuple[bool, str]:
        """Check if requirements met"""
```

---

## LLM Integration

### systems/llm_item_generator.py *(NEW - January 2026)*
**Lines**: ~1,393
**Dependencies**: `anthropic`, `json`, `threading`

**Purpose**: Generate procedural items via Claude API when players invent new recipes.

**Key Classes**:
```python
class LLMItemGenerator:
    """Main interface for LLM item generation."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = "claude-sonnet-4-20250514"
        self.temperature = 0.4
        self.max_tokens = 2000
        self.timeout = 30.0

    def generate_item(self, materials: List[Dict], discipline: str,
                      callback: Callable) -> None:
        """Generate item asynchronously (runs in background thread)."""

    def _build_prompt(self, materials: List[Dict], discipline: str) -> str:
        """Build few-shot prompt from training data."""

    def _parse_response(self, response: str) -> Dict:
        """Parse LLM response into item definition."""

class MockBackend:
    """Fallback when API unavailable - generates placeholder items."""
```

**Configuration**:
- API Key: Set `ANTHROPIC_API_KEY` environment variable
- Fallback: MockBackend generates placeholder items without API

**Debug Logs**: All API calls logged to `llm_debug_logs/TIMESTAMP_discipline.json`

---

### systems/crafting_classifier.py *(NEW - January 2026)*
**Lines**: ~1,256
**Dependencies**: `numpy`, `PIL`, `onnxruntime` (CNN), `lightgbm` (LightGBM)

**Purpose**: Validate invented recipe placements using ML classifiers.

**Key Classes**:
```python
class CraftingClassifierManager:
    """Manages all discipline classifiers."""

    def __init__(self):
        self.smithing_cnn = SmithingCNN()      # 36×36×3 RGB
        self.adornments_cnn = AdornmentsCNN()   # 56×56×3 RGB
        self.alchemy_lgb = AlchemyLightGBM()    # 34 features
        self.refining_lgb = RefiningLightGBM()  # 18 features
        self.engineering_lgb = EngineeringLightGBM()  # 28 features

    def validate_placement(self, placement: Dict, discipline: str) -> Tuple[bool, float]:
        """Validate placement, return (is_valid, confidence)."""

class SmithingCNN:
    """CNN classifier for smithing grid patterns."""

    def preprocess(self, grid: List[List[str]]) -> np.ndarray:
        """Convert grid to 36×36×3 RGB image using material colors."""

    def predict(self, image: np.ndarray) -> Tuple[bool, float]:
        """Run inference, return (is_valid, confidence)."""
```

**Classifier Mapping**:
| Discipline | Model | Input Size | Features |
|------------|-------|------------|----------|
| Smithing | CNN (ONNX) | 36×36×3 | RGB image from grid |
| Adornments | CNN (ONNX) | 56×56×3 | RGB image from grid |
| Alchemy | LightGBM | 34 | Tier counts, material types, ratios |
| Refining | LightGBM | 18 | Tier balance, category counts |
| Engineering | LightGBM | 28 | Slot usage, component types |

**CNN Warmup**: Models warm up at startup to avoid first-call latency.

---

### systems/npc_system.py
**Lines**: ~60
**Dependencies**: `data.models.npcs`

**Purpose**: NPC entity class.

```python
class NPC:
    npc_def: NPCDefinition
    current_dialogue_index: int

    def is_near(player_pos: Position) -> bool:
        """Check if player in interaction range"""

    def get_next_dialogue() -> str:
        """Get next dialogue line"""

    def get_available_quests(quest_manager: QuestManager) -> List[str]:
        """Get quests player can accept"""

    def has_quest_to_turn_in(quest_manager: QuestManager, character) -> Optional[str]:
        """Check for completable quests"""
```

---

## Rendering

### rendering/renderer.py
**Lines**: ~2,700
**Dependencies**: Everything (renders all game state)

**Purpose**: All rendering code in one place.

**Key Methods**:
```python
def render_world(world: WorldSystem, camera: Camera):
    """Render tiles, resources, stations"""

def render_entities(character: Character, enemies: List, npcs: List, camera: Camera):
    """Render character, enemies, NPCs"""

def render_hud(character: Character):
    """Render health/mana/XP bars, level, FPS"""

def render_inventory_panel(character: Character, mouse_pos):
    """Render inventory grid"""

def render_equipment_ui(character: Character):
    """Render equipment window"""

def render_stats_ui(character: Character):
    """Render stats window"""

def render_skills_ui(character: Character):
    """Render skills window"""

def render_encyclopedia_ui(character: Character):
    """Render encyclopedia"""

def render_crafting_ui(character: Character, recipes: List, ...):
    """Render crafting window"""

def render_npc_dialogue_ui(npc: NPC, ...):
    """Render dialogue window"""

def render_class_selection_ui(character: Character):
    """Render class selection"""

def render_item_tooltip(item_stack: ItemStack, mouse_pos, character):
    """Render item tooltip on hover"""

def render_damage_numbers(damage_numbers: List):
    """Render floating combat numbers"""

def render_notifications(notifications: List):
    """Render notification messages"""

def render_start_menu():
    """Render start menu"""
```

**Design Philosophy**:
- All pygame drawing code centralized here
- Receives data, renders it, returns nothing
- Stateless (doesn't modify game state)
- Uses helper methods for common patterns

---

## Crafting Subdisciplines

All 5 discipline minigames with difficulty/reward integration.

### Crafting-subdisciplines/smithing.py
**Lines**: ~749
**Dependencies**: `core.difficulty_calculator`, `core.reward_calculator`

**Purpose**: Smithing minigame - hammer timing on forge aesthetic.

```python
class SmithingMinigame:
    def __init__(self, recipe: Recipe, materials: List[Dict]):
        self.recipe = recipe
        self.difficulty = calculate_smithing_difficulty(materials)
        self.target_zone_width = scale_by_difficulty(self.difficulty)
        self.hits = 0
        self.required_hits = 5

    def handle_hammer(self):
        """Player hits hammer - check timing within target zone"""

    def update(self, delta_time: float):
        """Move hammer indicator back and forth"""

    def get_result(self) -> Dict:
        """Get performance score and quality tier"""
```

---

### Crafting-subdisciplines/alchemy.py
**Lines**: ~1,052
**Dependencies**: `core.difficulty_calculator`, `core.reward_calculator`

**Purpose**: Alchemy minigame - chain/stabilize reaction balance.

```python
class AlchemyMinigame:
    # Vowel-based volatility + tier modifier
    # Click CHAIN to combine reagents (risky but fast)
    # Click STABILIZE to prevent explosion (safe but slow)

    def chain(self):
        """Combine reagents - risk increases with volatility"""

    def stabilize(self):
        """Stabilize reaction - reduces risk, costs time"""

    def get_volatility(self, materials: List) -> float:
        """Calculate volatility from material names (vowels)"""
```

---

### Crafting-subdisciplines/refining.py
**Lines**: ~820
**Dependencies**: `core.difficulty_calculator`, `core.reward_calculator`

**Purpose**: Refining minigame - lock mechanism temperature control.

```python
class RefiningMinigame:
    # Keep temperature in target zone
    # Diversity multiplier + station tier affects difficulty
    # Too hot = burn, Too cold = slow

    def adjust_temperature(self, delta: float):
        """Increase/decrease furnace temperature"""

    def update(self, delta_time: float):
        """Update temperature decay, check progress"""
```

---

### Crafting-subdisciplines/engineering.py
**Lines**: ~1,315
**Dependencies**: `core.difficulty_calculator`, `core.reward_calculator`

**Purpose**: Engineering minigame - wire puzzles with blueprint aesthetic.

```python
class EngineeringMinigame:
    # Slot count × diversity formula for difficulty
    # Rarity-based puzzle selection
    # Connect wires to match pattern

    def connect(self, from_node: int, to_node: int):
        """Connect two circuit nodes"""

    def check_solution(self) -> bool:
        """Validate wire configuration matches target"""

    def get_hint(self) -> Tuple[int, int]:
        """Provide hint for stuck players"""
```

---

### Crafting-subdisciplines/enchanting.py
**Lines**: ~1,410
**Dependencies**: `core.difficulty_calculator`, `core.reward_calculator`

**Purpose**: Enchanting minigame - spinning wheel with material-based slices.

```python
class EnchantingMinigame:
    # Spin wheel to land on green (success) vs red (failure) slices
    # Material-based wheel distribution
    # Spin-progressive difficulty (later spins harder)

    def spin(self):
        """Spin the wheel with physics"""

    def update(self, delta_time: float):
        """Update wheel rotation, check result"""

    def get_wheel_distribution(self, materials: List) -> List[Slice]:
        """Calculate green/red slice distribution from materials"""
```

---

### Crafting-subdisciplines/rarity_utils.py
**Lines**: ~100
**Dependencies**: None

**Purpose**: Shared rarity system and color utilities.

```python
def get_rarity_color(rarity: str) -> Tuple[int, int, int]:
    """Get color for rarity tier (common through legendary)"""

def calculate_quality_tier(performance: float) -> str:
    """Map performance (0.0-1.0) to quality tier"""
```

---

## Tools & Utilities

### tools/json_generators/
**Purpose**: Generate JSON files from templates.

Files:
- `item_generator.py` - Generate item definitions
- `recipe_generator.py` - Generate recipes
- `item_validator.py` - Validate JSON structure

---

### verify_imports.py
**Lines**: ~140
**Dependencies**: All modules

**Purpose**: Test that all imports work correctly.

**Usage**:
```bash
python verify_imports.py
```

**Output**: Reports which modules import successfully and which require pygame.

---

## Summary

**Total Modules**: 136 Python files
**Total Lines**: ~62,380
**Organization**: Layered by concern
**Pattern**: Component-based + Singleton databases + Tag-driven effects
**Testing**: 13 test files + manual testing

### Key Systems by Lines of Code
| System | Lines | Purpose |
|--------|-------|---------|
| game_engine.py | 7,817 | Main loop, UI, event handling |
| renderer.py | 2,782 | All visual rendering |
| combat_manager.py | 1,655 | Damage pipeline, enchantments |
| llm_item_generator.py | 1,393 | Claude API integration |
| enchanting.py | 1,410 | Enchanting minigame |
| engineering.py | 1,315 | Engineering minigame |
| crafting_classifier.py | 1,256 | CNN + LightGBM validation |
| alchemy.py | 1,052 | Alchemy minigame |
| character.py | 1,008 | Player entity |
| skill_manager.py | 709 | Skill system |

For architecture overview, see [ARCHITECTURE.md](ARCHITECTURE.md).
For development guide, see [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md).
For LLM system, see [Fewshot_llm/README.md](../../Scaled%20JSON%20Development/LLM%20Training%20Data/Fewshot_llm/README.md).

---

**Last Updated**: 2026-01-27
