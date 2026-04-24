# Skill System: Developer Handoff Documentation

**Date**: 2025-12-23
**Session**: `claude/tags-to-effects-019DhmtS6ScBeiY2gorfzexT`
**Status**: 🟡 Partially Complete - Requires Additional Implementation

---

## Executive Summary

This document provides a comprehensive handoff for continuing work on the tag-driven skill system. The ultimate goal is to enable **JSON-only content addition** where new skills, items, and content can be added through JSON files alone without any code changes.

### What's Working ✅

1. **Power Strike** (consume-on-use combat buff) - Working perfectly
2. **Time Dilation** skills (timed buffs) - Working perfectly
3. **Whirlwind Strike** (instant AoE combat) - **JUST IMPLEMENTED**
4. **Magnitude values** - Now loaded from JSON correctly
5. **Consume-on-use system** - Implemented for combat
6. **Debug display** - Shows on-screen messages (max 5, bottom-left)

### What's Broken 🔴

1. **Chain Harvest** (instant AoE gathering) - Needs implementation in gathering system
2. **Crafting buff consumption** - Buffs created but not consumed on craft
3. **Other instant devastate skills** - Similar to Chain Harvest (fishing, forestry)

### What's Next 🎯

1. Implement Chain Harvest (gathering AoE) following the Whirlwind Strike pattern
2. Integrate crafting buff consumption in all 5 crafting systems
3. Comprehensive testing of all 30+ skills
4. Validate tag-driven architecture for JSON-only content addition

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Recent Fixes](#recent-fixes)
3. [Remaining Issues](#remaining-issues)
4. [Implementation Guide: Chain Harvest](#implementation-guide-chain-harvest)
5. [Implementation Guide: Crafting Buff Consumption](#implementation-guide-crafting-buff-consumption)
6. [Tag System Overview](#tag-system-overview)
7. [Testing Guide](#testing-guide)
8. [File Reference](#file-reference)

---

## System Architecture

### Core Principles

1. **Tag-Driven Design**: All effects, damage, geometry, and status effects use declarative tags
2. **JSON-Driven Content**: Game content defined in JSON files, loaded at runtime
3. **Effect System**: Modular effect types (empower, quicken, devastate, etc.)
4. **Buff System**: Timed and consume-on-use buffs applied to characters
5. **Magnitude Values**: Effect strength defined in `Skills/skills-base-effects-1.JSON`

### Data Flow

```
JSON Skill Definition
    ↓
SkillManager.use_skill(slot, character)
    ↓
_apply_skill_effect(skill_def, character, player_skill)
    ↓
Create ActiveBuff (or execute immediately)
    ↓
Buff added to character.buffs
    ↓
Buff applied during relevant action (attack, gather, craft)
    ↓
Buff consumed (if consume_on_use=True)
```

### Skill Types

| Type | Duration | Target | Execution | Example |
|------|----------|--------|-----------|---------|
| **Consume-on-use** | instant | single | On next action | Power Strike |
| **Instant AoE** | instant | area | Immediate | Whirlwind Strike, Chain Harvest |
| **Timed Buff** | 15-120s | self/area | Over time | Rockbreaker, Iron Will |
| **Instant Restore** | instant | self | Immediate | Field Medic, Quick Repair |

---

## Recent Fixes

### Fix #1: Magnitude Values (Completed ✅)

**Problem**: Hardcoded values were wrong (extreme empower: 1.5 instead of 4.0)

**Solution**: Load from `Skills/skills-base-effects-1.JSON` at startup

**File**: `entities/components/skill_manager.py:23-45`

**Code**:
```python
def _load_magnitude_values(self) -> dict:
    """Load magnitude values from skills-base-effects-1.JSON"""
    try:
        base_effects_path = get_resource_path("Skills/skills-base-effects-1.JSON")
        with open(base_effects_path, 'r') as f:
            data = json.load(f)

        magnitude_map = {}
        for effect_name, effect_data in data.get("BASE_EFFECT_TYPES", {}).items():
            magnitude_map[effect_name] = effect_data.get("magnitudeValues", {})

        return magnitude_map
    except Exception as e:
        print(f"[SkillManager] Warning: Could not load magnitude values: {e}")
        return {/* fallback values */}
```

**Result**: Power Strike now correctly shows +400% damage instead of +150%

---

### Fix #2: Instant Duration Handling (Completed ✅)

**Problem**: Skills with "instant" duration (0 seconds) expired immediately before use

**Solution**: Set 60s fallback duration + `consume_on_use=True` flag

**File**: `entities/components/skill_manager.py:216-228`

**Code**:
```python
base_duration = skill_db.get_duration_seconds(effect.duration)
is_instant = (base_duration == 0)

if is_instant:
    duration = 60.0  # Fallback duration (consumed before expiry)
    consume_on_use = True
else:
    duration = base_duration * (1.0 + level_bonus)
    consume_on_use = False
```

**Result**: Instant buffs now persist until consumed, not expire immediately

---

### Fix #3: Consume-on-Use System (Completed ✅)

**Problem**: No mechanism to remove buffs after they were used

**Solution**: Added `consume_buffs_for_action()` method to BuffManager

**File**: `entities/components/buffs.py:81-121`

**Code**:
```python
def consume_buffs_for_action(self, action_type: str, category: str = None):
    """
    Consume (remove) buffs marked consume_on_use for this action type.

    Args:
        action_type: Type of action ("attack", "gather", "craft")
        category: Optional category filter ("combat", "mining", "smithing")
    """
    buffs_to_remove = []

    for buff in self.active_buffs:
        if not buff.consume_on_use:
            continue

        should_consume = False

        if action_type == "attack":
            if buff.category in ["combat", "damage"]:
                should_consume = True
        elif action_type == "gather":
            if category and buff.category == category:
                should_consume = True
            elif buff.category in ["mining", "forestry", "fishing", "gathering"]:
                should_consume = True
        elif action_type == "craft":
            if category and buff.category == category:
                should_consume = True
            elif buff.category in ["smithing", "alchemy", "engineering", "refining", "enchanting"]:
                should_consume = True

        if should_consume:
            buffs_to_remove.append(buff)

    for buff in buffs_to_remove:
        print(f"   ⚡ Consumed: {buff.name}")
        self.active_buffs.remove(buff)
```

**Integration**: Called in `Combat/combat_manager.py:539, 683`

**Result**: Power Strike consumed after first attack, second attack normal damage

---

### Fix #4: Whirlwind Strike (AoE Combat) (Completed ✅)

**Problem**: Devastate buffs created but never applied to multiple targets

**Solution**: Check for devastate buff in `player_attack_enemy()`, execute AoE attack

**File**: `Combat/combat_manager.py:394-505`

**Code**:
```python
def player_attack_enemy(self, enemy: Enemy, hand: str = 'mainHand'):
    # Check for active devastate buffs (AoE attacks like Whirlwind Strike)
    if hasattr(self.character, 'buffs'):
        for buff in self.character.buffs.active_buffs:
            if buff.effect_type == "devastate" and buff.category in ["damage", "combat"]:
                # Execute AoE attack instead
                return self._execute_aoe_attack(enemy, hand, int(buff.bonus_value))

    # ... normal single-target attack logic

def _execute_aoe_attack(self, primary_target: Enemy, hand: str, radius: int):
    """Execute an AoE attack hitting all enemies in radius"""
    # Find all enemies in radius
    targets = []
    for e in self.active_enemies:
        if e.is_alive():
            dx = e.position.x - self.character.position.x
            dy = e.position.y - self.character.position.y
            distance = math.sqrt(dx*dx + dy*dy)
            if distance <= radius:
                targets.append(e)

    print(f"🌀 DEVASTATE (AoE Attack): Hitting {len(targets)} target(s) in {radius}-tile radius!")

    # Consume devastate buff
    self.character.buffs.consume_buffs_for_action("attack")

    # Attack each target
    for target in targets:
        damage, is_crit, loot = self._single_target_attack(target, hand)
        # ... aggregate results

    return (total_damage, any_crit, all_loot)
```

**Result**: Whirlwind Strike now hits all enemies in 5-tile radius

---

### Fix #5: Debug Display (Completed ✅)

**Problem**: No on-screen debug output for testing

**Solution**: Created `DebugMessageManager` with FIFO queue and abbreviation

**Files**:
- `core/debug_display.py` (NEW - 210 lines)
- `rendering/renderer.py:2367-2394` (render method)
- `core/game_engine.py:2891, 2910` (integration)

**Usage**:
```python
from core.debug_display import debug_print

debug_print("Power Strike activated: +400% damage")
# Shows in console AND on-screen (bottom-left, max 5 messages)
```

**Result**: On-screen debug messages visible during gameplay

---

## Remaining Issues

### Issue #1: Chain Harvest (Gathering AoE) 🔴

**Status**: NOT IMPLEMENTED

**Problem**: Same as Whirlwind Strike, but for resource gathering

**Skill**: Chain Harvest (chain_harvest)
- Effect: devastate/mining/minor
- Target: area
- Duration: instant
- Expected: Mine all nodes in 3-tile radius

**Current Behavior**:
1. Skill activated → Creates devastate buff ✓
2. Player clicks resource node → Only mines that single node ❌
3. Buff expires after 60s unused ❌

**Expected Behavior**:
1. Skill activated → Creates devastate buff ✓
2. Player clicks resource node → Mines all nodes in radius ✓
3. Buff consumed after gathering ✓

**Fix Location**: Gathering/resource interaction code (needs investigation)

**Pattern**: Follow Whirlwind Strike implementation:
1. Check for devastate buff before gathering
2. If found, gather from all nodes in radius
3. Consume buff after gathering

**See**: [Implementation Guide: Chain Harvest](#implementation-guide-chain-harvest)

---

### Issue #2: Crafting Buff Consumption 🔴

**Status**: PARTIALLY IMPLEMENTED

**Problem**: Crafting buffs created but not consumed when crafting

**Affected Skills**:
1. **Smith's Focus** (quicken/smithing/major) - Extra minigame time
2. **Alchemist's Insight** (quicken/alchemy/moderate + empower/alchemy/minor) - Time + quality
3. **Engineer's Precision** (quicken/engineering/major + empower/engineering/minor) - Time + quality
4. **Refiner's Touch** (quicken/refining/major + elevate/refining/minor) - Time + rarity
5. **Enchanter's Grace** (pierce/enchanting/major + elevate/enchanting/minor) - Crit + rarity

**Current Behavior**:
1. Skill activated → Creates buffs ✓
2. Buffs applied to minigame (time, quality, etc.) ✓ (assumed, needs verification)
3. Buffs consumed after craft ❌ (missing!)
4. Buffs expire after 60s instead ❌

**Expected Behavior**:
1. Skill activated → Creates buffs ✓
2. Buffs applied to minigame ✓
3. Buffs consumed after craft completion ✓

**Fix Location**: All 5 crafting minigame completion handlers

**Fix Required**: Add this line after minigame completion:
```python
self.character.buffs.consume_buffs_for_action("craft", category="smithing")
```

**Crafting Systems**:
1. Smithing - `core/game_engine.py` (search for smithing minigame completion)
2. Alchemy - `core/game_engine.py` (alchemy completion)
3. Engineering - `core/game_engine.py` (engineering completion)
4. Refining - `core/game_engine.py` (refining completion)
5. Enchanting - `core/game_engine.py` (enchanting completion)

**See**: [Implementation Guide: Crafting Buff Consumption](#implementation-guide-crafting-buff-consumption)

---

### Issue #3: Other Instant Devastate Skills 🔴

**Status**: SAME AS CHAIN HARVEST

**Affected Skills**:
- Any other instant devastate gathering skills (forestry, fishing)

**Fix**: Same pattern as Chain Harvest

---

## Implementation Guide: Chain Harvest

### Step 1: Find Gathering Code

Search for where resource nodes are damaged/harvested:

```bash
grep -rn "node.*damage\|harvest\|gather.*resource" --include="*.py" Game-1-modular/
```

Likely locations:
- `core/game_engine.py` (mouse click handling)
- `systems/chunk.py` (resource node management)
- `entities/character.py` (gathering methods)

### Step 2: Add Devastate Check

In the gathering method, add check similar to combat:

```python
def gather_resource_node(self, node):
    """Gather from a resource node (with AoE support for Chain Harvest)"""

    # Check for active devastate buffs (AoE gathering like Chain Harvest)
    if hasattr(self.character, 'buffs'):
        for buff in self.character.buffs.active_buffs:
            if buff.effect_type == "devastate" and buff.category in ["mining", "forestry", "fishing", "gathering"]:
                # Execute AoE gathering instead
                return self._execute_aoe_gathering(node, int(buff.bonus_value), buff.category)

    # ... normal single-node gathering logic
```

### Step 3: Implement AoE Gathering

```python
def _execute_aoe_gathering(self, primary_node, radius: int, category: str):
    """Execute AoE gathering (devastate effect) hitting all nodes in radius"""
    from core.debug_display import debug_print
    import math

    # Find all resource nodes in radius
    targets = []
    for node in self.active_resource_nodes:  # Adjust based on actual data structure
        if node.is_harvestable():  # Adjust based on actual API
            dx = node.position.x - self.character.position.x
            dy = node.position.y - self.character.position.y
            distance = math.sqrt(dx*dx + dy*dy)
            if distance <= radius:
                # Filter by category (mining = ores, forestry = trees, etc.)
                if self._node_matches_category(node, category):
                    targets.append(node)

    if not targets:
        targets = [primary_node]

    print(f"🌀 CHAIN HARVEST: Gathering from {len(targets)} node(s) in {radius}-tile radius!")
    debug_print(f"🌀 Chain Harvest: {len(targets)} nodes in {radius}-tile radius")

    # Consume devastate buff
    self.character.buffs.consume_buffs_for_action("gather", category=category)

    # Gather from each node
    total_materials = []
    for node in targets:
        materials = self._single_node_gather(node)  # Reuse existing logic
        total_materials.extend(materials)

    return total_materials

def _node_matches_category(self, node, category: str) -> bool:
    """Check if node type matches skill category"""
    if category == "mining":
        return node.type in ["copper_ore", "iron_ore", "coal", ...]  # Ore nodes
    elif category == "forestry":
        return node.type in ["oak_tree", "birch_tree", ...]  # Tree nodes
    elif category == "fishing":
        return node.type in ["fishing_spot", ...]
    return False
```

### Step 4: Test

1. Learn Chain Harvest skill
2. Find cluster of 3+ ore nodes
3. Activate Chain Harvest (press hotkey)
4. Click one ore node
5. **Expected**: All nearby ores harvested, buff consumed
6. Click another node without re-activating skill
7. **Expected**: Only that single node harvested

---

## Implementation Guide: Crafting Buff Consumption

### Overview

Each crafting system has a minigame completion handler. We need to add buff consumption calls in each one.

### Step 1: Find Minigame Completion Handlers

Search for where crafting minigames complete:

```bash
grep -n "minigame.*complete\|_complete_minigame" core/game_engine.py
```

Look for methods like:
- `_complete_minigame()`
- `complete_smithing_minigame()`
- Similar for alchemy, engineering, refining, enchanting

### Step 2: Add Consumption Calls

In each completion handler, add:

```python
def _complete_smithing_minigame(self):
    """Complete smithing minigame and create item"""

    # ... existing logic to get minigame result
    # ... apply buffs to crafting outcome

    # IMPORTANT: Consume smithing buffs after craft completes
    if hasattr(self.character, 'buffs'):
        self.character.buffs.consume_buffs_for_action("craft", category="smithing")

    # ... rest of completion logic
```

### Step 3: Repeat for All Crafting Systems

| System | Category | Skills Affected |
|--------|----------|----------------|
| Smithing | `"smithing"` | Smith's Focus, Master Craftsman |
| Alchemy | `"alchemy"` | Alchemist's Insight |
| Engineering | `"engineering"` | Engineer's Precision |
| Refining | `"refining"` | Refiner's Touch |
| Enchanting | `"enchanting"` | Enchanter's Grace |

**Code Template**:
```python
# At end of each minigame completion handler:
if hasattr(self.character, 'buffs'):
    self.character.buffs.consume_buffs_for_action("craft", category="SYSTEM_NAME")
```

### Step 4: Verify Buff Application

Also verify that buffs are actually being applied during minigame:

**Quicken (extra time)**:
```python
# In minigame initialization
base_time = 30.0
quicken_bonus = self.character.buffs.get_total_bonus("quicken", "smithing")
total_time = base_time + (quicken_bonus * 5.0)  # +5 seconds per magnitude point
```

**Empower (better stats)**:
```python
# In minigame result calculation
base_stats = item.base_stats
empower_bonus = self.character.buffs.get_total_bonus("empower", "smithing")
item.stats = base_stats * (1.0 + empower_bonus * 0.1)  # +10% stats per magnitude point
```

**Pierce (crit chance)**:
```python
# In minigame success check
base_crit = 0.0
pierce_bonus = self.character.buffs.get_total_bonus("pierce", "smithing")
crit_chance = base_crit + pierce_bonus
if random.random() < crit_chance:
    # First-try bonus or double quality
```

**Elevate (rarity boost)**:
```python
# In item creation
base_rarity = "common"
elevate_bonus = self.character.buffs.get_total_bonus("elevate", "smithing")
if random.random() < elevate_bonus:
    # Upgrade rarity (common → uncommon → rare → epic)
```

---

## Tag System Overview

### What is Tag-Driven Design?

Tags are declarative metadata that describe **what** something is or does, not **how** it works. The game systems read tags and apply appropriate logic.

**Example**: A weapon tagged with `["slashing", "2h", "precision"]` automatically gets:
- Slashing damage type (effective vs light armor)
- Two-handed weapon benefits (+20% damage)
- Precision crit bonus (+10% crit chance)

No code changes needed - tags drive behavior.

### Tag Categories

1. **Damage Tags**: `slashing`, `piercing`, `crushing`, `elemental`, `fire`, `cold`, `lightning`
2. **Weapon Tags**: `2h`, `versatile`, `precision`, `armor_breaker`, `balanced`
3. **Effect Tags**: `empower`, `quicken`, `fortify`, `pierce`, `devastate`, `transcend`
4. **Category Tags**: `combat`, `mining`, `forestry`, `fishing`, `smithing`, `alchemy`, etc.
5. **Geometry Tags**: `aoe`, `chain`, `beam`, `projectile`
6. **Status Tags**: `burning`, `frozen`, `shocked`, `poisoned`, `bleeding`

### Tag-Driven Skill Example

**JSON Definition** (`Skills/skills-skills-1.JSON`):
```json
{
  "skillId": "whirlwind_strike",
  "name": "Whirlwind Strike",
  "tags": ["aoe", "combat", "damage"],
  "effect": {
    "type": "devastate",
    "category": "damage",
    "magnitude": "moderate",
    "target": "area",
    "duration": "instant"
  }
}
```

**Tag Interpretation**:
- `tags: ["aoe"]` → Skill hits multiple targets
- `effect.type: "devastate"` → Uses devastate magnitude values (minor=3, moderate=5, major=7, extreme=10 tiles)
- `effect.category: "damage"` → Applies to combat damage
- `effect.target: "area"` → Area of effect, not single target
- `effect.duration: "instant"` → Executes immediately, not over time

**Code (Tag-Driven)**:
```python
# Code reads tags and applies logic automatically
magnitude_value = magnitude_values["devastate"]["moderate"]  # 5 (from JSON)
radius = int(magnitude_value)  # 5 tiles

# Find targets using geometry tag
if "aoe" in skill.tags:
    targets = find_all_in_radius(character.position, radius)

# Execute using effect tag
if effect.type == "devastate":
    for target in targets:
        apply_damage(target)
```

**Result**: No hardcoding. Change JSON, change behavior. Add new skill with same tags, works immediately.

### Adding New Content via JSON Only

**Goal**: Designers should be able to add:
- New skills
- New items
- New enchantments
- New enemies
- New recipes

By editing JSON files alone, without touching code.

**Current Status**:
- ✅ Skills: Partially working (instant AoE needs fixes)
- ✅ Items: Working for equipment/materials
- ✅ Enchantments: Working
- ⚠️ Enemies: Needs tag system integration
- ⚠️ Recipes: Needs buff integration

**Validation Checklist**:
1. Can you add a new skill in JSON and it works immediately? ⚠️ (mostly yes)
2. Can you add a new item and it works with existing systems? ✅ (yes)
3. Can you add a new recipe and it respects buffs? ⚠️ (needs crafting buff fix)
4. Can you modify magnitude values without code changes? ✅ (yes, now loaded from JSON)

---

## Testing Guide

### Testing Methodology

1. **Unit Testing**: Test individual buffs
2. **Integration Testing**: Test buff application in combat/gathering/crafting
3. **Regression Testing**: Ensure fixes don't break working skills
4. **Edge Case Testing**: Test buff stacking, expiry, consumption

### Test Cases: Combat Skills

#### Power Strike (Consume-on-Use) ✅

**Test**:
1. Attack training dummy → Note damage (e.g., 171.2)
2. Activate Power Strike
3. Attack training dummy → Should see ~856 damage (5x multiplier)
4. Attack again → Should see 171.2 damage (buff consumed)

**Expected Output**:
```
⚡ Power Strike Lv1: empower - damage (extreme)
   +400% damage for next action

⚔️ PLAYER ATTACK: Training Dummy
   Weapon damage: 171.2
   Empower bonus: +400% (combat)
   Base damage: 856.0
   ⚡ Consumed: Power Strike (Damage)

⚔️ PLAYER ATTACK: Training Dummy
   Weapon damage: 171.2
   Base damage: 171.2  [No empower bonus]
```

---

#### Whirlwind Strike (Instant AoE) ⚠️ JUST FIXED

**Test**:
1. Spawn 5+ training dummies in cluster
2. Activate Whirlwind Strike
3. Attack one dummy

**Expected Output**:
```
⚡ Whirlwind Strike Lv1: devastate - damage (moderate)
   Next action affects 5-tile radius

🌀 DEVASTATE (AoE Attack): Hitting 5 target(s) in 5-tile radius!
   → Training Dummy (HP: 100/100) - Damage: 171.2
   → Training Dummy (HP: 100/100) - Damage: 171.2
   → Training Dummy (HP: 100/100) - Damage: 171.2
   → Training Dummy (HP: 100/100) - Damage: 171.2
   → Training Dummy (HP: 100/100) - Damage: 171.2
   ⚡ Consumed: Whirlwind Strike (AoE)
```

**On-Screen Debug**:
```
🌀 AoE Attack: 5 targets in 5-tile radius
```

---

### Test Cases: Gathering Skills

#### Chain Harvest (Instant AoE) 🔴 NOT YET FIXED

**Test**:
1. Find cluster of 5+ ore nodes
2. Activate Chain Harvest
3. Click one ore node

**Expected Output**:
```
⚡ Chain Harvest Lv1: devastate - mining (minor)
   Next action affects 3-tile radius

🌀 CHAIN HARVEST: Gathering from 5 node(s) in 3-tile radius!
   → Copper Ore Node - Gathered 3x copper_ore
   → Copper Ore Node - Gathered 3x copper_ore
   → Copper Ore Node - Gathered 3x copper_ore
   → Copper Ore Node - Gathered 3x copper_ore
   → Copper Ore Node - Gathered 3x copper_ore
   ⚡ Consumed: Chain Harvest

Total: 15x copper_ore
```

**Current Output (Broken)**:
```
⚡ Chain Harvest Lv1: devastate - mining (minor)
   Next action affects 3-tile radius

[Click node]
   → Copper Ore Node - Gathered 3x copper_ore

Total: 3x copper_ore  [Only 1 node harvested!]
```

---

### Test Cases: Crafting Skills

#### Smith's Focus (Quicken/Smithing) 🔴 NEEDS VERIFICATION

**Test**:
1. Open smithing station, select recipe
2. Note base minigame time (e.g., 30 seconds)
3. Activate Smith's Focus
4. Start minigame

**Expected**:
- Minigame time: 60+ seconds (base + quicken bonus)
- After completion: Buff consumed

**Needs Verification**:
1. Does the extra time actually apply? (Check minigame initialization)
2. Is buff consumed after completion? (Check minigame end handler)

---

#### Master Craftsman (Empower + Elevate) 🔴 NEEDS VERIFICATION

**Test**:
1. Select copper sword recipe (base stats: damage 20-30)
2. Activate Master Craftsman
3. Complete minigame

**Expected**:
- Item stats: Higher than base (empower bonus)
- Item rarity: Chance to be uncommon/rare (elevate bonus)
- After completion: Buffs consumed

**Needs Verification**:
1. Are stats actually boosted? (Check result calculation)
2. Is rarity upgrade working? (Check rarity roll logic)
3. Are buffs consumed? (Check completion handler)

---

### Test Cases: Timed Buffs

#### Rockbreaker (Timed Buff) ✅

**Test**:
1. Activate Rockbreaker
2. Mine several ore nodes over 60 seconds
3. Each should grant bonus ore
4. After 60s, buff expires
5. Next mine should be normal yield

**Expected**:
```
⚡ Rockbreaker Lv1: enrich - mining (moderate)
   +3 bonus ore for 60s

[Mine node]
   Base yield: 3x copper_ore
   Enrich bonus: +3x copper_ore
   Total: 6x copper_ore

[60 seconds later - buff expires]

[Mine node]
   Base yield: 3x copper_ore
   Total: 3x copper_ore  [No bonus]
```

---

### Edge Case Testing

#### Buff Stacking

**Test**: Activate Power Strike twice (or two different empower skills)

**Expected**: Both buffs should stack (additive)

```
⚡ Power Strike: +400% damage
⚡ Some Other Skill: +100% damage
Total empower bonus: +500% damage
```

**Verify**:
```python
empower_bonus = character.buffs.get_damage_bonus("combat")
# Should return sum of all active empower buffs
```

---

#### Buff Expiry vs Consumption

**Test**:
1. Activate Power Strike
2. Wait 60 seconds without attacking
3. Buff should expire (not consumed)
4. Attack → Normal damage

**Expected**:
```
⚡ Power Strike: +400% damage for next action

[Wait 60s]
[Buff expires naturally]

⚔️ PLAYER ATTACK: Training Dummy
   Damage: 171.2  [Normal, no buff]
```

---

#### Multiple Instant AoE Skills

**Test**:
1. Activate Whirlwind Strike (combat AoE)
2. Activate Chain Harvest (gathering AoE)
3. Attack enemy → Combat AoE triggers
4. Mine node → Gathering AoE triggers

**Expected**: Both buffs should coexist and consume independently

---

## File Reference

### Core Systems

| File | Purpose | Key Methods |
|------|---------|-------------|
| `entities/components/skill_manager.py` | Skill activation, buff creation | `use_skill()`, `_apply_skill_effect()` |
| `entities/components/buffs.py` | Buff management, consumption | `consume_buffs_for_action()` |
| `Combat/combat_manager.py` | Combat damage, AoE attacks | `player_attack_enemy()`, `_execute_aoe_attack()` |
| `core/game_engine.py` | Main game loop, crafting handlers | `_complete_minigame()`, crafting completion methods |
| `core/debug_display.py` | On-screen debug messages | `debug_print()`, `DebugMessageManager` |

---

### Data Files

| File | Purpose | Key Data |
|------|---------|----------|
| `Skills/skills-base-effects-1.JSON` | Effect magnitude values | `magnitudeValues` for each effect type |
| `Skills/skills-skills-1.JSON` | All skill definitions | Skill IDs, effects, costs, cooldowns |
| `Definitions.JSON/skills-translation-table.JSON` | Duration/cost translations | `durationTranslations`, `manaCostTranslations` |
| `items.JSON/items-*.JSON` | Item definitions | Equipment, materials, tools |
| `recipes.JSON/recipes-*.JSON` | Crafting recipes | Smithing, alchemy, engineering, etc. |

---

### Modified Files (This Session)

| File | Lines | Change Summary |
|------|-------|----------------|
| `entities/components/skill_manager.py` | 23-45, 193-442 | Load magnitude values, instant duration handling, consume-on-use |
| `entities/components/buffs.py` | 23, 81-121 | Added consume_on_use field, consumption logic |
| `Combat/combat_manager.py` | 394-505 | AoE attack system (Whirlwind Strike) |
| `core/debug_display.py` | ENTIRE FILE (NEW) | Debug message manager |
| `rendering/renderer.py` | 2367-2394 | Render debug messages |
| `core/game_engine.py` | 2891, 2910 | Call debug rendering |
| `entities/character.py` | 1042-1063 | Fix enchantment damage (previous fix) |

---

### Documentation Files

| File | Purpose |
|------|---------|
| `docs/SKILL-SYSTEM-BUGS.md` | Bug analysis (18 broken skills) |
| `docs/IMPLEMENTATION-SUMMARY.md` | Implementation log (enchantment fix, debug display) |
| `docs/SKILL-SYSTEM-HANDOFF.md` | **THIS FILE** - Developer handoff |

---

## Quick Start for Next Developer

### Priority 1: Fix Chain Harvest 🔴

1. Find gathering code: `grep -rn "gather\|harvest\|resource.*node" --include="*.py"`
2. Add devastate check (follow Whirlwind Strike pattern)
3. Test with cluster of ore nodes
4. Expected: All nodes harvested in radius, buff consumed

**Time Estimate**: 1-2 hours

---

### Priority 2: Fix Crafting Buff Consumption 🔴

1. Find minigame completion handlers: `grep -n "_complete_minigame\|complete.*craft" core/game_engine.py`
2. Add consumption call in each: `self.character.buffs.consume_buffs_for_action("craft", category="...")`
3. Verify buffs actually apply (check minigame init for quicken/empower/pierce/elevate)
4. Test each crafting skill

**Time Estimate**: 2-3 hours

---

### Priority 3: Comprehensive Testing 📋

1. Test all 30+ skills systematically
2. Document which skills work vs broken
3. Fix any remaining silent failures
4. Validate tag-driven architecture

**Time Estimate**: 4-6 hours

---

### Priority 4: JSON-Only Content Validation ✅

1. Add a new skill in JSON (copy existing, change values)
2. Test it works without code changes
3. Add a new recipe
4. Test it respects buffs
5. Document any code changes required → refactor to be tag-driven

**Time Estimate**: 2-3 hours

---

## Success Criteria

### Minimum Viable (MVP)

- [x] Power Strike works (consume-on-use)
- [x] Whirlwind Strike works (instant AoE combat)
- [ ] Chain Harvest works (instant AoE gathering)
- [ ] All crafting skills consume buffs properly
- [x] Debug display shows messages

### Full Feature Complete

- [ ] All 30+ skills tested and working
- [ ] All 5 crafting systems integrate buffs
- [ ] All gathering skills (mining, forestry, fishing) support AoE
- [ ] No silent failures
- [ ] Tag system fully validated

### Ultimate Goal

- [ ] New skill added via JSON only → Works immediately
- [ ] New recipe added via JSON only → Respects all buffs
- [ ] Designer can add content without touching code

---

## Known Gotchas

### 1. Buff Category Matching

Buffs must match action categories **exactly**:

```python
# WRONG:
buff.category = "smithing"
consume_buffs_for_action("craft", category="crafting")  # Won't match!

# CORRECT:
buff.category = "smithing"
consume_buffs_for_action("craft", category="smithing")  # Matches!
```

### 2. Instant vs Timed Duration

Check `is_instant` logic carefully:

```python
base_duration = skill_db.get_duration_seconds(effect.duration)
is_instant = (base_duration == 0)  # "instant" translates to 0

# For instant:
duration = 60.0
consume_on_use = True

# For timed:
duration = base_duration * level_scaling
consume_on_use = False
```

### 3. Buff Consumption Timing

Consume buffs **AFTER** they've been applied, not before:

```python
# WRONG:
self.character.buffs.consume_buffs_for_action("attack")
damage = calculate_damage()  # Buffs already gone!

# CORRECT:
damage = calculate_damage()  # Uses buffs
self.character.buffs.consume_buffs_for_action("attack")  # Then remove
```

### 4. AoE Target Finding

Use **world coordinates**, not screen coordinates:

```python
# Distance calculation must use character.position and enemy.position
# NOT screen x/y coordinates
dx = enemy.position.x - self.character.position.x
dy = enemy.position.y - self.character.position.y
distance = math.sqrt(dx*dx + dy*dy)
```

---

## Questions for User Testing

1. **Chain Harvest**: Do gathering skills exist in separate systems (mining vs forestry vs fishing)? Or one unified gathering system?

2. **Crafting Buffs**: Are buffs currently being applied to minigames? Or is that also missing?

3. **Buff Display**: Should active buffs show in UI? (Currently only in debug log)

4. **Skill Hotkeys**: Are there more than 5 skill slots? Or hard limit of 5?

5. **AoE Radius**: Is radius in world tiles or screen pixels? (Assuming tiles based on JSON)

---

## Final Notes

### Project Vision

**Tag-driven, JSON-only content addition** is the north star. Every decision should ask:

> "Can a designer add this via JSON without touching code?"

If not, refactor until the answer is yes.

### Code Quality Principles

1. **Don't hardcode**: Load from JSON
2. **Don't duplicate**: Extract and reuse
3. **Don't assume**: Validate at boundaries
4. **Don't invent**: Follow existing patterns

### Testing Philosophy

**Silent failures are worse than crashes.**

A crash tells you something is wrong. A silent failure (buff created but not applied) looks like it works but doesn't.

Debug liberally. Use `debug_print()` everywhere during development.

---

**Good luck! The system is 80% there. Just need the final 20% polish. 🚀**

**Questions?** See existing documentation:
- `docs/SKILL-SYSTEM-BUGS.md` - Detailed bug analysis
- `docs/IMPLEMENTATION-SUMMARY.md` - What was fixed
- `docs/ARCHITECTURE.md` - Overall system design
