# Tag System Naming Conventions

**Purpose**: Reference document for consistent naming across the tag system implementation.

---

## JSON Field Names

### Equipment Items (Weapons, Armor)
```json
{
  "itemId": "iron_shortsword",           // Snake_case, unique identifier
  "name": "Iron Shortsword",             // Title Case, display name
  "category": "equipment",               // Lowercase
  "metadata": {
    "tags": ["weapon", "sword", "1H"]    // Metadata tags (crafting/filtering)
  },
  "effectTags": ["physical", "slashing", "single"],  // NEW: Combat effect tags
  "effectParams": {                      // NEW: Effect parameters
    "baseDamage": 30
  }
}
```

### Devices (Turrets, Traps, Bombs)
```json
{
  "itemId": "flamethrower_turret",
  "category": "device",
  "type": "turret",                      // Lowercase
  "subtype": "area",                     // Lowercase
  "metadata": {
    "tags": ["device", "turret", "fire"] // Metadata tags
  },
  "effectTags": ["fire", "cone", "burn"],// NEW: Combat effect tags
  "effectParams": {                      // NEW: Effect parameters
    "baseDamage": 60,
    "cone_angle": 60.0,
    "cone_range": 8.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  }
}
```

### Enchantments
```json
{
  "enchantmentId": "fire_aspect_1",
  "name": "Fire Aspect I",
  "effect": {
    "type": "damage_over_time",          // Snake_case
    "element": "fire",                   // Lowercase
    "damagePerSecond": 10,               // camelCase (legacy)
    "duration": 5
  }
}
```

---

## Python Class/Method Names

### Combat Manager
```python
class CombatManager:
    def player_attack_enemy(self, enemy: Enemy, hand: str = 'mainHand')
        # OLD METHOD - legacy damage

    def player_attack_enemy_with_tags(self, enemy: Enemy, tags: List[str], params: dict = None)
        # NEW METHOD - tag-based effects
```

### Equipment
```python
class Equipment:
    # Fields
    self.tags: List[str]                 # Metadata tags from JSON
    self.enchantments: List[dict]        # List of enchantment dicts

    # Methods
    def get_metadata_tags(self) -> List[str]
    def get_effect_tags(self) -> List[str]      # NEW: Get combat effect tags
    def get_effect_params(self) -> dict         # NEW: Get effect parameters
```

### PlacedEntity
```python
@dataclass
class PlacedEntity:
    position: Position
    item_id: str                         # Snake_case
    entity_type: PlacedEntityType        # Enum
    tags: List[str]                      # Effect tags (not metadata tags!)
    effect_params: Dict[str, any]        # Effect parameters
```

### Effect Executor
```python
class EffectExecutor:
    def execute_effect(self, source: Any, primary_target: Any,
                      tags: List[str], params: dict,
                      available_entities: List[Any])
        # Tags = effect tags (fire, cone, burn)
        # Params = effect parameters (baseDamage, cone_angle, etc.)
```

---

## Parameter Naming Patterns

### Damage Methods
```python
def take_damage(self,
                damage: float,           # Amount of damage
                damage_type: str = "physical",  # physical/fire/ice/lightning/poison
                from_player: bool = False,
                source_tags: list = None,  # Player attacks use this
                tags: list = None,         # Effect executor uses this
                attacker_name: str = None,
                source = None,
                **kwargs)
```

### Effect Parameters (in effectParams JSON)
```python
effect_params = {
    # Damage
    "baseDamage": 50,                    # camelCase (follow existing pattern)

    # Geometry - Single
    "range": 5.0,

    # Geometry - Circle
    "circle_radius": 4.0,                # Snake_case

    # Geometry - Cone
    "cone_angle": 60.0,                  # Snake_case
    "cone_range": 8.0,

    # Geometry - Chain
    "chain_count": 2,                    # Snake_case
    "chain_range": 5.0,

    # Geometry - Beam
    "beam_range": 12.0,                  # Snake_case
    "beam_width": 1.0,

    # Status Effects - Burning
    "burn_duration": 5.0,                # Snake_case
    "burn_damage_per_second": 8.0,

    # Status Effects - Frozen
    "freeze_duration": 3.0,
    "freeze_slow_factor": 0.5,           # 0.5 = 50% speed

    # Status Effects - Shocked
    "shock_duration": 2.0,
    "shock_damage": 5.0,

    # Status Effects - Poisoned
    "poison_duration": 10.0,
    "poison_damage_per_second": 3.0,

    # Status Effects - Bleeding
    "bleed_duration": 8.0,
    "bleed_damage_per_second": 5.0
}
```

---

## Tag Naming Standards

### Damage Type Tags (Lowercase, Single Word)
```python
# Elemental
"physical", "fire", "ice", "lightning", "poison"

# Weapon damage types
"slashing", "piercing", "crushing"

# Special
"true"  # True damage (ignores defense)
```

### Geometry Tags (Lowercase, Underscore if Multi-Word)
```python
"single"         # Single target
"circle"         # Circle AOE
"cone"           # Cone AOE
"chain"          # Chain between targets
"beam"           # Beam/line through targets
```

### Status Effect Tags (Past Tense, Lowercase, Underscore)
```python
"burn"           # Applies burning status
"burning"        # Alternative form
"freeze"         # Applies frozen status
"frozen"         # Alternative form
"shock"          # Applies shocked status
"shocked"        # Alternative form
"poison"         # Applies poisoned status
"poisoned"       # Alternative form
"bleed"          # Applies bleeding status
"bleeding"       # Alternative form
```

### Property Tags (Lowercase, Underscore)
```python
# Weapon properties
"fast"           # Fast attack speed
"reach"          # Extended range
"precision"      # High crit chance
"armor_breaker"  # Armor penetration
"cleaving"       # Hits multiple enemies

# Hand requirements
"1H"             # One-handed (special case: uppercase)
"2H"             # Two-handed (special case: uppercase)
"versatile"      # Can use one or two hands

# Attack types
"melee"          # Melee attack
"ranged"         # Ranged attack
```

---

## Common Code Patterns

### Pattern 1: Getting Tags from Equipment
```python
# Get metadata tags (for weapon bonuses)
weapon_tags = equipped_weapon.get_metadata_tags()

# Get effect tags (for effect executor) - NEW
effect_tags = equipped_weapon.get_effect_tags()
effect_params = equipped_weapon.get_effect_params()
```

### Pattern 2: Calling Effect Executor
```python
from core.effect_executor import EffectExecutor

executor = EffectExecutor(debugger)
context = executor.execute_effect(
    source=source_entity,              # Who's attacking (weapon, turret, etc.)
    primary_target=target_enemy,       # Main target
    tags=effect_tags,                  # List of effect tags
    params=effect_params,              # Dict of parameters
    available_entities=all_enemies     # List of all possible targets
)
```

### Pattern 3: Creating PlacedEntity with Tags
```python
from data.models.world import PlacedEntity, PlacedEntityType

entity = PlacedEntity(
    position=position,
    item_id="flamethrower_turret",
    entity_type=PlacedEntityType.TURRET,
    tier=3,
    range=8.0,
    damage=60.0,                       # Legacy fallback
    tags=["fire", "cone", "burn"],     # Effect tags
    effect_params={                    # Effect parameters
        "baseDamage": 60,
        "cone_angle": 60.0,
        "cone_range": 8.0,
        "burn_duration": 5.0,
        "burn_damage_per_second": 8.0
    }
)
```

### Pattern 4: Loading Tags from JSON
```python
# For equipment items
item_data = json.load(f)
effect_tags = item_data.get("effectTags", [])
effect_params = item_data.get("effectParams", {})

# Store in Equipment object
equipment.effect_tags = effect_tags
equipment.effect_params = effect_params
```

### Pattern 5: Applying Status Effects
```python
# In combat after damage dealt
if "burn" in tags or "burning" in tags:
    duration = params.get("burn_duration", 5.0)
    dps = params.get("burn_damage_per_second", 5.0)
    enemy.apply_status_effect("burning", duration, dps)

# Pattern for all status effects
status_map = {
    ("burn", "burning"): ("burning", "burn_duration", "burn_damage_per_second"),
    ("freeze", "frozen"): ("frozen", "freeze_duration", "freeze_slow_factor"),
    ("shock", "shocked"): ("shocked", "shock_duration", "shock_damage"),
    ("poison", "poisoned"): ("poisoned", "poison_duration", "poison_damage_per_second"),
    ("bleed", "bleeding"): ("bleeding", "bleed_duration", "bleed_damage_per_second")
}
```

---

## Database/Model Field Names

### Equipment Model (data/models/equipment.py)
```python
@dataclass
class EquipmentItem:
    item_id: str
    name: str
    tier: int
    rarity: str
    slot: str
    damage: Tuple[int, int]
    tags: List[str]                    # Metadata tags
    enchantments: List[dict]
    # NEW FIELDS:
    effect_tags: List[str] = None      # Combat effect tags
    effect_params: Dict = None         # Effect parameters
```

### Material Definition (for turrets/traps in MaterialDatabase)
```python
# MaterialDefinition already has:
self.effect: str                       # String description (legacy)

# Need to check if it has:
self.effect_tags: List[str]            # Combat effect tags
self.effect_params: dict               # Effect parameters
```

---

## Import Statements (Standard Order)

```python
# Python standard library
import json
import math
import random
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

# Game modules - data models
from data.models.world import PlacedEntity, PlacedEntityType, Position
from data.models.equipment import EquipmentItem

# Game modules - systems
from core.effect_executor import EffectExecutor
from core.tag_debug import get_tag_debugger

# Game modules - entities
from entities.enemy import Enemy
```

---

## Testing Patterns

### Pattern 1: Verify Tags Loaded
```python
print(f"DEBUG: effect_tags = {equipment.effect_tags}")
print(f"DEBUG: effect_params = {equipment.effect_params}")
```

### Pattern 2: Verify Effect Execution
```python
print(f"🎯 Executing effect with tags: {tags}")
print(f"   Params: {params}")
context = executor.execute_effect(...)
print(f"   ✓ Effect executed, affected {len(context.affected_entities)} entities")
```

### Pattern 3: Verify Tag Inheritance
```python
print(f"⚒️  SMITHING CRAFT: {output_id}")
print(f"   Recipe Tags: {', '.join(recipe_tags)}")
print(f"   ✓ Inherited Tags: {', '.join(inheritable_tags)}")
```

---

## Common Gotchas

### 1. Metadata Tags vs Effect Tags
```python
# WRONG: Using metadata tags for combat
tags = ["weapon", "sword", "1H", "slashing", "starter"]
executor.execute_effect(..., tags=tags)  # "weapon" is not an effect tag!

# CORRECT: Use effect tags
effect_tags = ["physical", "slashing", "single"]
executor.execute_effect(..., tags=effect_tags)
```

### 2. camelCase vs snake_case
```python
# JSON uses camelCase for legacy compatibility
"effectParams": {
    "baseDamage": 50,        # camelCase
    "cone_angle": 60.0       # But geometry uses snake_case
}

# Python uses snake_case
effect_params = {
    "baseDamage": 50,        # Keep camelCase from JSON
    "cone_angle": 60.0
}
```

### 3. Optional Fields
```python
# Always use .get() with defaults
effect_tags = item_data.get("effectTags", [])
effect_params = item_data.get("effectParams", {})
base_damage = params.get("baseDamage", 0)
```

### 4. List vs String
```python
# WRONG: Tags as string
tags = "fire, cone, burn"

# CORRECT: Tags as list
tags = ["fire", "cone", "burn"]
```

---

## File Naming Standards

### JSON Files
```
items-smithing-1.JSON          # Kebab-case with number
items-engineering-1.JSON
recipes-tag-tests.JSON
tag-definitions.JSON
```

### Python Files
```
effect_executor.py             # Snake_case
crafting_tag_processor.py
weapon_tag_calculator.py
```

### Documentation Files
```
SALVAGE-ANALYSIS.md            # CAPS-KEBAB-CASE.md
NAMING-CONVENTIONS.md
DEBUG-GUIDE.md
```

---

## Version Control Commit Message Format

```
<Type>: <Short Description>

<Detailed description in present tense>

## Changes
- Added effectTags to 5 weapons
- Modified player_attack to use effect_executor
- Updated PlacedEntity creation

## Testing
- ✓ Player attacks show tags in training dummy
- ✓ Fire damage applies burning status

Files Modified:
- items.JSON/items-smithing-2.JSON
- core/game_engine.py
- Combat/combat_manager.py
```

Types: `Feature`, `Fix`, `Refactor`, `Docs`, `Test`, `Phase1`, `Phase2`, etc.

---

**Last Updated**: 2025-12-21
**Status**: Active Reference Document
