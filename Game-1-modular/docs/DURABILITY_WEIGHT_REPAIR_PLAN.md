# Durability, Weight, and Repair Systems - Implementation Plan

**Created**: December 31, 2025
**Status**: Planning Complete - Ready for Implementation
**Priority**: HIGH (Referenced throughout codebase but not fully functional)

---

## Executive Summary

Three interconnected systems need implementation:
1. **Durability** - Partially implemented (~60%), needs completion
2. **Weight** - Data structure exists (~5%), needs full implementation
3. **Repair** - Skills defined (~10%), needs functional implementation

These systems are heavily referenced in GAME_MECHANICS_V6.md and multiple skills/enchantments depend on them.

---

## PART 1: DURABILITY SYSTEM

### Current Implementation Status: 60%

#### What Already Exists (✅)

| Component | Location | Status |
|-----------|----------|--------|
| Data structures | `equipment.py:17-18`, `tool.py:15-16` | `durability_current`, `durability_max` |
| Effectiveness calculation | `equipment.py:48-54`, `tool.py:30-36` | 50% effectiveness at 0 durability |
| Tool durability loss | `character.py:839-856` | -1 per use, -2 for wrong tool type |
| Armor durability loss | `character.py:1325-1339` | -1 per hit taken |
| Unbreaking enchantment | `character.py:844-850` | Reduces durability loss |
| Console warnings | `character.py:854-856, 1336-1339` | Low/broken durability alerts |
| Save/Load | `save_manager.py:141-142` | Durability persists |

#### What's Missing (❌)

| Component | Priority | Description |
|-----------|----------|-------------|
| Weapon durability loss | HIGH | Weapons don't lose durability in combat |
| DEF stat bonus | MEDIUM | -2% durability loss per DEF point |
| VIT stat bonus | MEDIUM | -1% tool durability loss per VIT point |
| Durability bar UI | LOW | Visual durability indicator on items |
| Tier-based durability | MEDIUM | T1: 500, T2: 1000, T3: 2000, T4: 4000 |

### Implementation Tasks

#### Task 1.1: Weapon Durability in Combat
**File**: `Combat/combat_manager.py`
**Location**: After damage is dealt (around line 654)

```python
# After enemy.take_damage() call
# WEAPON DURABILITY LOSS
if equipped_weapon and hasattr(equipped_weapon, 'durability_current'):
    durability_loss = 1.0

    # Unbreaking enchantment reduces loss
    for ench in equipped_weapon.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'durability_multiplier':
            reduction = effect.get('value', 0.0)
            durability_loss *= (1.0 - reduction)

    equipped_weapon.durability_current = max(0,
        equipped_weapon.durability_current - durability_loss)

    if equipped_weapon.durability_current == 0:
        print(f"   💥 {equipped_weapon.name} has broken!")
    elif equipped_weapon.durability_current <= equipped_weapon.durability_max * 0.2:
        print(f"   ⚠️ {equipped_weapon.name} durability low!")
```

#### Task 1.2: DEF/VIT Stat Bonuses
**File**: `entities/character.py`
**Location**: Modify durability loss calculations

**DEF Stat**: -2% durability loss per point (gear lasts longer)
**VIT Stat**: +1% max durability per point (items are tougher)

```python
def get_durability_reduction_multiplier(self) -> float:
    """Get multiplier for durability loss reduction from DEF stat"""
    def_bonus = self.stats.defense * 0.02  # 2% reduction per DEF point
    return max(0.1, 1.0 - def_bonus)  # Minimum 10% durability loss

def get_durability_bonus_multiplier(self) -> float:
    """Get multiplier for max durability from VIT stat"""
    vit_bonus = self.stats.vitality * 0.01  # +1% max durability per VIT point
    return 1.0 + vit_bonus
```

#### Task 1.3: Tier-Based Durability Values
**File**: `data/databases/equipment_db.py`
**Reference**: `Definitions.JSON/stats-calculations.JSON`

Base durability = 500, Tier multipliers: T1=1x, T2=2x, T3=4x, T4=8x

```python
def _calculate_durability(self, tier: int, category: str) -> int:
    """Calculate durability based on tier"""
    base = 500
    tier_mult = {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}.get(tier, 1.0)
    return int(base * tier_mult)
```

---

## PART 2: WEIGHT SYSTEM

### Current Implementation Status: 5%

#### What Already Exists (✅)

| Component | Location | Status |
|-----------|----------|--------|
| Weight field | `equipment.py:20` | `weight: float = 1.0` |
| Save/Load | `save_manager.py:144, 190` | Weight persists |
| STR carry capacity docs | `GAME_MECHANICS_V6.md:161` | +10 slots per STR |

#### What's Missing (❌)

| Component | Priority | Description |
|-----------|----------|-------------|
| Weight calculation | HIGH | Sum of all equipped item weights |
| Carry capacity system | HIGH | Max weight based on STR |
| Encumbrance effects | HIGH | Movement speed reduction |
| Weight UI | MEDIUM | Current/max weight display |
| Material weight values | MEDIUM | JSON needs weight data |
| Weightless enchantment | LOW | Reduces item weight |

### Design Decisions

**Weight Formula**:
- Base carry capacity: 100.0 weight units
- Per STR point: +2% capacity (capacity = base × (1 + STR × 0.02))
- Example: 10 STR = 100 × 1.20 = 120 capacity

**Encumbrance Penalties** (Linear):
- At or under 100% capacity: No penalty
- Over 100%: For every 1% over max, -2% movement speed
- Example: 110% capacity = -20% movement speed
- Example: 125% capacity = -50% movement speed

### Implementation Tasks

#### Task 2.1: Character Weight Tracking
**File**: `entities/character.py`
**New methods**:

```python
def get_total_weight(self) -> float:
    """Calculate total weight of equipped items and inventory"""
    total = 0.0

    # Equipment weight
    for slot, item in self.equipment.slots.items():
        if item and hasattr(item, 'weight'):
            total += item.weight

    # Tool weight
    if self.axe and hasattr(self.axe, 'weight'):
        total += self.axe.weight
    if self.pickaxe and hasattr(self.pickaxe, 'weight'):
        total += self.pickaxe.weight

    # Inventory weight (materials have weight too)
    for slot in self.inventory.slots:
        if slot and slot.item_id:
            # Get material weight from database
            from data.databases.material_db import get_material_db
            mat_db = get_material_db()
            mat = mat_db.get(slot.item_id)
            if mat and hasattr(mat, 'weight'):
                total += mat.weight * slot.quantity
            elif slot.equipment_data and hasattr(slot.equipment_data, 'weight'):
                total += slot.equipment_data.weight

    return total

def get_max_carry_capacity(self) -> float:
    """Calculate max carry capacity based on STR (+2% per point)"""
    base = 100.0
    str_multiplier = 1.0 + (self.stats.strength * 0.02)  # +2% per STR
    # Title bonuses could add here
    return base * str_multiplier

def get_encumbrance_percent(self) -> float:
    """Get how much over capacity (0.0 = at capacity, 0.1 = 10% over)"""
    weight = self.get_total_weight()
    capacity = self.get_max_carry_capacity()
    if capacity <= 0:
        return 1.0
    ratio = weight / capacity
    return max(0.0, ratio - 1.0)  # 0 if under/at capacity

def get_movement_speed_multiplier(self) -> float:
    """Get movement speed multiplier including encumbrance

    Linear penalty: -2% speed for every 1% over capacity
    """
    base_mult = 1.0 + (self.stats.agility * 0.02)  # AGI bonus

    over_percent = self.get_encumbrance_percent()
    if over_percent > 0:
        # -2% speed per 1% over capacity
        penalty = over_percent * 2.0  # 10% over = 20% penalty
        base_mult *= max(0.0, 1.0 - penalty)

    return base_mult
```

#### Task 2.2: Movement Speed Integration
**File**: `core/game_engine.py`
**Location**: Movement handling (around WASD controls)

```python
# Modify movement to use encumbrance
def handle_movement(self, keys, dt):
    speed_mult = self.character.get_movement_speed_multiplier()

    if speed_mult <= 0:
        self.add_notification("Too encumbered to move!", "warning")
        return

    speed = self.character.movement_speed * speed_mult
    # ... rest of movement logic
```

#### Task 2.3: Weight UI Display
**File**: `rendering/renderer.py`
**Location**: Inventory panel (around line 2470)

```python
def render_weight_bar(self, surface, character):
    """Render weight/capacity bar in inventory"""
    current = character.get_total_weight()
    max_cap = character.get_max_carry_capacity()
    ratio = current / max_cap if max_cap > 0 else 0

    # Color based on encumbrance (green until over, then red gradient)
    if ratio <= 1.0:
        color = (100, 200, 100)  # Green - under/at capacity
    else:
        # Red intensity based on how far over
        over_percent = min(0.5, ratio - 1.0)  # Cap visual at 50% over
        red_intensity = int(100 + over_percent * 200)
        color = (red_intensity, 100, 100)

    # Draw bar
    bar_width = 200
    bar_height = 15
    x, y = Config.INVENTORY_PANEL_X + 10, Config.INVENTORY_PANEL_Y + 25

    # Background
    pygame.draw.rect(surface, (50, 50, 50), (x, y, bar_width, bar_height))
    # Fill (cap at bar width for visual, but show overflow via color)
    fill_width = min(bar_width, int(bar_width * ratio))
    pygame.draw.rect(surface, color, (x, y, fill_width, bar_height))
    # Text
    weight_text = f"{current:.1f}/{max_cap:.1f}"
    # ... render text
```

#### Task 2.4: Material Weight Values
**File**: `items.JSON/items-materials-1.JSON`

Add weight field to materials based on tier and type:
- T1 materials: 0.1 - 0.5 weight per unit
- T2 materials: 0.3 - 1.0 weight per unit
- T3 materials: 0.5 - 2.0 weight per unit
- T4 materials: 1.0 - 5.0 weight per unit
- Metals heavier than wood/cloth

---

## PART 3: REPAIR SYSTEM

### Current Implementation Status: 10%

#### What Already Exists (✅)

| Component | Location | Status |
|-----------|----------|--------|
| Tool.repair() method | `tool.py:38-42` | Restores durability |
| Quick Repair skill | `skills-skills-1.JSON:159-193` | Defined, not functional |
| Tool Preservation skill | `skills-skills-1.JSON:582-616` | Defined, not functional |
| Phoenix Resurrection skill | `skills-skills-1.JSON:955-983` | Defined, not functional |
| "restore" effect type | `skills-translation-table.JSON` | For durability category |
| Self-Repair enchantment | `recipes-enchanting-1.JSON` | Deferred |

#### What's Missing (❌)

| Component | Priority | Description |
|-----------|----------|-------------|
| Equipment.repair() method | HIGH | Only Tool has repair |
| Skill effect handler | HIGH | Connect restore/durability to actual repair |
| Repair costs | MEDIUM | Material costs for repairs |
| Repair station/NPC | DEFERRED | Place to repair items |
| Partial repair | MEDIUM | Repair by percentage |
| Self-repair enchantment | HIGH | Passive durability regen |
| Repair UI | MEDIUM | Interface for repairing |

### Design Decisions

**Repair Methods**:
1. **Skill-based** (Quick Repair): Instant, costs mana, long cooldown
2. **Station-based** (Anvil/Forge): Costs materials, no cooldown
3. **NPC-based** (Blacksmith): Costs gold, convenient

**Repair Costs** (Station-based):
- Requires 10% of original crafting materials
- OR generic "repair kit" consumable
- Repair amount = 50% per repair action (2 actions for full)

**Skill Repair Amounts**:
- Quick Repair: 30% durability restored (moderate magnitude)
- Phoenix Resurrection: 50% durability restored (major magnitude)

### Implementation Tasks

#### Task 3.1: Equipment.repair() Method
**File**: `data/models/equipment.py`

```python
def repair(self, amount: int = None, percent: float = None):
    """Repair this equipment

    Args:
        amount: Flat durability to restore
        percent: Percentage of max durability to restore (0.0-1.0)
    """
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

def get_repair_cost(self) -> Dict[str, int]:
    """Calculate materials needed to repair this item"""
    # 10% of original materials, minimum 1
    # This would need recipe lookup
    return {"repair_kit": 1}  # Simplified version
```

#### Task 3.2: Skill Effect Handler for Repair
**File**: `entities/components/skill_manager.py`
**Location**: In `_apply_skill_effect()` method

```python
def _apply_restore_effect(self, effect: dict, target: str):
    """Apply restore effect (heal HP, mana, or durability)"""
    category = effect.get('category', 'health')
    magnitude = effect.get('magnitude', 'moderate')

    # Get restore amount from translation table
    magnitude_values = {
        'minor': 0.15,
        'moderate': 0.30,
        'major': 0.50,
        'extreme': 0.75
    }
    restore_percent = magnitude_values.get(magnitude, 0.30)

    if category == 'durability':
        self._restore_durability(restore_percent)
    elif category == 'health':
        restore_amount = int(self.character.max_health * restore_percent)
        self.character.health = min(self.character.max_health,
            self.character.health + restore_amount)
    elif category == 'mana':
        restore_amount = int(self.character.max_mana * restore_percent)
        self.character.mana = min(self.character.max_mana,
            self.character.mana + restore_amount)

def _restore_durability(self, percent: float):
    """Restore durability to all equipped items and tools"""
    repaired_items = []

    # Repair equipped items
    for slot_name, item in self.character.equipment.slots.items():
        if item and hasattr(item, 'repair'):
            old_dur = item.durability_current
            item.repair(percent=percent)
            if item.durability_current > old_dur:
                repaired_items.append(item.name)

    # Repair tools
    for tool in [self.character.axe, self.character.pickaxe]:
        if tool and hasattr(tool, 'repair'):
            old_dur = tool.durability_current
            tool.repair(int(tool.durability_max * percent))
            if tool.durability_current > old_dur:
                repaired_items.append(tool.name)

    if repaired_items:
        print(f"   🔧 Repaired: {', '.join(repaired_items)}")
```

#### Task 3.3: Repair Station Integration
**Status**: DEFERRED - Will implement later

#### Task 3.4: Self-Repair Enchantment (HIGH PRIORITY)
**File**: `entities/character.py`
**Location**: In update() or periodic update method

```python
def update_passive_effects(self, dt: float):
    """Update passive effects like health regen, self-repair"""

    # Self-repair enchantment on equipment
    for slot_name, item in self.equipment.slots.items():
        if item and hasattr(item, 'enchantments'):
            for ench in item.enchantments:
                effect = ench.get('effect', {})
                if effect.get('type') == 'durability_regeneration':
                    regen_rate = effect.get('value', 1.0)  # Per second
                    regen_amount = regen_rate * dt
                    item.durability_current = min(item.durability_max,
                        item.durability_current + regen_amount)
```

---

## PART 4: INTEGRATION POINTS

### Files to Modify

| File | Changes |
|------|---------|
| `entities/character.py` | Weight tracking, encumbrance, durability stat bonuses |
| `data/models/equipment.py` | repair() method |
| `entities/tool.py` | Already has repair() |
| `Combat/combat_manager.py` | Weapon durability loss |
| `entities/components/skill_manager.py` | Restore effect for durability |
| `rendering/renderer.py` | Weight UI, durability bars |
| `core/game_engine.py` | Movement encumbrance check |
| `data/databases/equipment_db.py` | Tier-based durability calculation |

### New Files to Create

| File | Purpose |
|------|---------|
| `systems/repair_system.py` | Repair station logic |
| `systems/weight_system.py` | Weight calculation utilities (optional) |

### JSON Files to Update

| File | Changes |
|------|---------|
| `items-materials-1.JSON` | Add weight field to materials |
| `items-smithing-2.JSON` | Verify weight values |
| `items-tools-1.JSON` | Verify weight values |
| `Definitions.JSON/stats-calculations.JSON` | Add weight/durability formulas |

---

## PART 5: IMPLEMENTATION ORDER

### Phase 1: Durability Completion (2-3 hours)
1. Add weapon durability loss in combat
2. Implement DEF/VIT stat bonuses for durability
3. Ensure tier-based durability values work
4. Test durability across all item types

### Phase 2: Repair System (3-4 hours)
1. Add Equipment.repair() method
2. Implement skill effect handler for restore/durability
3. Connect Quick Repair skill to repair functionality
4. Add repair kit item and station repair option
5. Test all repair methods

### Phase 3: Weight System (4-5 hours)
1. Implement weight calculation methods
2. Add encumbrance level detection
3. Integrate movement speed penalties
4. Add weight UI to inventory
5. Update material JSONs with weight values
6. Test encumbrance across gameplay

### Phase 4: Polish & Integration (2-3 hours)
1. Add UI indicators for all systems
2. Implement Self-Repair enchantment
3. Connect remaining skills (Tool Preservation, Phoenix Resurrection)
4. Comprehensive testing
5. Documentation updates

---

## PART 6: TESTING CHECKLIST

### Durability Tests
- [ ] Tools lose durability when harvesting
- [ ] Weapons lose durability when attacking
- [ ] Armor loses durability when taking damage
- [ ] Unbreaking enchantment reduces durability loss
- [ ] DEF stat reduces durability loss
- [ ] VIT stat reduces tool durability loss
- [ ] 0% durability = 50% effectiveness
- [ ] Tier multipliers work (T2 = 2x durability)

### Weight Tests
- [ ] Weight calculates correctly for equipped items
- [ ] Weight calculates correctly for inventory items
- [ ] STR increases carry capacity (+2% per point)
- [ ] At/under capacity: no movement penalty
- [ ] 10% over capacity: -20% movement speed
- [ ] 25% over capacity: -50% movement speed
- [ ] Weight UI displays correctly

### Repair Tests
- [ ] Quick Repair skill restores durability
- [ ] Tool.repair() works
- [ ] Equipment.repair() works
- [ ] Repair station consumes materials
- [ ] Repair amount matches magnitude (30%/50%/75%)
- [ ] Self-repair enchantment regenerates durability over time
- [ ] All repair skills function (Quick Repair, Tool Preservation, Phoenix Resurrection)

---

## Appendix: Related Documentation

- `docs/GAME_MECHANICS_V6.md` - Master reference (durability/weight base values)
- `docs/MASTER_ISSUE_TRACKER.md` - Related deferred items
- `Skills/skills-skills-1.JSON` - Repair skill definitions
- `Definitions.JSON/skills-translation-table.JSON` - Effect formulas
- `Definitions.JSON/stats-calculations.JSON` - Stat calculations
