# Playtest Changes Tracker

> **Last Playtest**: Prior to commit 0531b65
> **Document Created**: Session date (track changes requiring playtester attention)
> **Latest Update**: Tag-driven class system implementation

---

## Quick Reference: What to Test

### HIGH PRIORITY (Bug Fixes - Previous Commit)
| Change | Location | What to Test | Expected Behavior |
|--------|----------|--------------|-------------------|
| Inventory click fix | game_engine.py | Click on any inventory slot | Clicks should register correctly on all slots |
| Tooltip z-order fix | renderer.py | Hover items while equipment menu open | Tooltips appear ON TOP of equipment menu |
| Icon path restoration | character.py | Save game → Load game → Check equipment icons | All equipment icons should display correctly |

### NEW FEATURES (Current Commit)
| Feature | Location | What to Test | Expected Behavior |
|---------|----------|--------------|-------------------|
| Tag-driven class system | classes.py, classes-1.JSON | Select each class, check tags load | Classes have identity tags (warrior=melee/physical/tanky) |
| Skill affinity bonus | skill_manager.py | Use skills matching class tags in combat | Console shows affinity bonus, up to +20% damage |
| Class selection tooltips | renderer.py | Hover over class cards during selection | Tooltip shows tags, affinity explanation, preferred types |
| Tool slot tooltips | renderer.py | Hover over equipped axe/pickaxe slots | Tooltip shows tool stats, durability, class bonus |
| Tag-driven tool bonus | class_system.py, character.py | Select Ranger/Scavenger, check tool efficiency | Ranger: +15% axe, Scavenger: +15% pickaxe |

### MEDIUM PRIORITY (Enchantments Need Verification)
| Feature | Location | What to Test | Expected Behavior |
|---------|----------|--------------|-------------------|
| Knockback enchantment | combat_manager.py:802-810 | Attack enemy with knockback weapon | Enemy pushed back ~2 tiles |
| Lifesteal enchantment | combat_manager.py:673-677 | Attack with lifesteal weapon | Player heals 10% of damage dealt |
| Slow enchantment | combat_manager.py:812-821 | Attack with frost weapon | Enemy movement slowed 30% for 3s |
| Chain damage enchantment | combat_manager.py:683-703 | Attack in group of enemies | 2 nearby enemies take 50% splash damage |
| Health regen enchantment | character.py:983-996 | Equip armor with health regen | Passive HP/sec regeneration |

### LOW PRIORITY (Documentation)
| Change | Location | Purpose |
|--------|----------|---------|
| TESTING_SYSTEM_PLAN.md | docs/ | Planning document for automated testing |
| MASTER_ISSUE_TRACKER.md | root | Comprehensive issue tracking |
| test_enchantments.py | root | Automated enchantment logic tests (43 tests) |
| test_class_tags.py | root | Automated class tag system tests (36 tests) |

---

## Detailed Changes

### Commit: 0531b65 - BUGFIX: Inventory/Tooltip UI fixes + Testing System Plan

#### 1. Inventory Click Spacing Fix
**Files Changed**: `core/game_engine.py`
**Lines Modified**: 872, 1368, 2824

**Problem**: Inventory slot click detection used `spacing = 5` while renderer used `spacing = 10`, causing clicks to miss their intended slots.

**Fix**: Changed all three locations to use `spacing = 10`:
```python
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10  # Must match renderer spacing
```

**Test Steps**:
1. Open inventory (press I or click inventory panel)
2. Click on each slot systematically (row by row)
3. Verify tooltip appears for the correct slot
4. Test right-click consumables work on correct slot
5. Test drag-and-drop starts from correct slot

**Expected**: All clicks should register on the correct slot, no offset errors.

---

#### 2. Tooltip Z-Order Fix (Deferred Rendering)
**Files Changed**: `rendering/renderer.py`, `core/game_engine.py`
**Lines Modified**: renderer.py (54, 2522-2525, 3240-3251, 3384-3399), game_engine.py (3044-3045)

**Problem**: Tooltips rendered during inventory panel, but equipment UI rendered AFTER, causing tooltips to appear behind equipment menu.

**Fix**: Implemented deferred tooltip system:
- Added `pending_tooltip` attribute to store tooltip data
- Tooltips stored during render, drawn at END of frame
- Added `render_pending_tooltip()` method called last in render loop

**Test Steps**:
1. Open equipment UI (press E or click equipment button)
2. Hover over any equipped item
3. Move to inventory panel while equipment UI is open
4. Hover over inventory items

**Expected**: Tooltips ALWAYS appear on top of all UI elements, including modals and equipment menu.

---

#### 3. Icon Path Restoration in Save/Load
**Files Changed**: `entities/character.py`
**Lines Modified**: 384, 437

**Problem**: When loading a saved game, equipment items lost their `icon_path` property, causing missing/wrong icons.

**Fix**: Added `icon_path=eq_data.get("icon_path")` to both EquipmentItem constructors in restore_from_save:
```python
item_stack.equipment_data = EquipmentItem(
    # ... other fields ...
    icon_path=eq_data.get("icon_path")  # Restore icon path for proper PNG rendering
)
```

**Test Steps**:
1. Equip several items with distinct icons
2. Save the game
3. Close and reopen game
4. Load the save file
5. Check equipment panel and inventory

**Expected**: All equipment icons should display correctly, matching what was shown before save.

---

## Previously Implemented Features Needing Verification

The following enchantment integrations exist in the codebase but haven't been playtested:

### Knockback Enchantment
**Location**: `Combat/combat_manager.py:802-810`
```python
elif effect_type == 'knockback':
    knockback_distance = effect.get('value', 2.0)
    knockback_params = {'knockback_distance': knockback_distance}
    executor._apply_knockback(self.character, enemy, knockback_params)
```

**Test Steps**:
1. Obtain/craft a weapon with knockback enchantment
2. Attack an enemy near a wall
3. Attack an enemy in open space
4. Observe knockback behavior

**Expected**:
- Enemy pushed back ~2 tiles away from player
- Print message: "💨 Knockback triggered! Pushed enemy back"
- Smooth knockback over 0.5 seconds

---

### Lifesteal Enchantment
**Location**: `Combat/combat_manager.py:673-677`
```python
if effect.get('type') == 'lifesteal':
    lifesteal_percent = effect.get('value', 0.1)  # 10% default
    heal_amount = final_damage * lifesteal_percent
    self.character.health = min(self.character.max_health, self.character.health + heal_amount)
```

**Test Steps**:
1. Damage yourself (walk into enemy, fall damage, etc.)
2. Equip lifesteal weapon
3. Attack enemies and observe health bar
4. Note healing amount vs damage dealt

**Expected**:
- Heal 10% of damage dealt per hit
- Print message: "💚 Lifesteal: Healed X.X HP"
- Cannot overheal past max health

---

### Slow (Frost) Enchantment
**Location**: `Combat/combat_manager.py:812-821`
```python
elif effect_type == 'slow':
    slow_params = {
        'duration': effect.get('duration', 3.0),
        'speed_reduction': effect.get('value', 0.3)  # 30% slow default
    }
    enemy.status_manager.apply_status('slow', slow_params, source=self.character)
```

**Test Steps**:
1. Obtain weapon with frost/slow enchantment
2. Attack a mobile enemy (one that moves toward you)
3. Observe enemy movement speed
4. Time the slow duration

**Expected**:
- Enemy movement speed reduced by 30%
- Duration: 3 seconds
- Print message: "❄️ Frost triggered! Applied slow"

---

### Chain Damage Enchantment
**Location**: `Combat/combat_manager.py:683-703`
```python
if effect.get('type') == 'chain_damage':
    chain_count = int(effect.get('value', 2))
    chain_damage_percent = effect.get('damagePercent', 0.5)
    # ... chains to nearby enemies
```

**Test Steps**:
1. Obtain weapon with chain damage enchantment
2. Find a group of 3+ enemies close together
3. Attack one enemy
4. Observe damage to nearby enemies

**Expected**:
- Primary target takes full damage
- Up to 2 nearby enemies take 50% of damage
- Print message: "⚡ Chain Damage: Hitting X additional target(s)"
- Print per-target: "→ EnemyName: X.X damage"

---

### Health Regeneration Enchantment
**Location**: `entities/character.py:983-996`
```python
# HEALTH REGENERATION ENCHANTMENT: Always active bonus regen from armor
for slot in armor_slots:
    armor_piece = self.equipment.slots.get(slot)
    if armor_piece and hasattr(armor_piece, 'enchantments'):
        for ench in armor_piece.enchantments:
            if effect.get('type') == 'health_regeneration':
                enchant_regen_bonus += effect.get('value', 1.0)  # HP per second
```

**Test Steps**:
1. Take some damage
2. Equip armor with health regeneration enchantment
3. Stand still and observe health bar
4. Note regeneration rate

**Expected**:
- Passive HP regeneration (stacks with out-of-combat regen)
- Rate: ~1 HP/sec per enchantment level
- Works during combat (unlike base regen which requires 5s no-combat)

---

## Tag-Driven Class System (FULLY INTEGRATED)

### Overview
Classes are now fully tag-driven with active gameplay effects:
- **Skill affinity bonuses**: Skills matching class tags get up to 20% bonus (INTEGRATED)
- **Tag-driven tool bonuses**: Starting tools get efficiency bonuses based on class tags (INTEGRATED)
- **Class selection tooltips**: Detailed tooltips showing tags, affinity, and preferred types (NEW)
- **Tool slot tooltips**: Equipped tools show stats and class bonuses (NEW)
- Future: Class-specific content gating

### Class Tags

| Class | Tags | Preferred Damage | Armor Type | Tool Bonus |
|-------|------|------------------|------------|------------|
| Warrior | warrior, melee, physical, tanky, frontline | physical, slashing, crushing | heavy | +10% tool damage |
| Ranger | ranger, ranged, agile, nature, mobile | physical, piercing, poison | light | +15% axe efficiency |
| Scholar | scholar, magic, alchemy, arcane, caster | arcane, fire, frost, lightning | robes | - |
| Artisan | artisan, crafting, smithing, engineering, utility | physical | medium | - |
| Scavenger | scavenger, luck, gathering, treasure, explorer | physical | light | +15% pickaxe efficiency |
| Adventurer | adventurer, balanced, versatile, generalist, adaptive | physical, arcane | medium | - |

### Skill Affinity Bonus (NOW ACTIVE IN COMBAT)
When a skill's tags overlap with the class's tags, a damage/effectiveness bonus is applied:
- 1 matching tag = +5% effectiveness
- 2 matching tags = +10% effectiveness
- 3 matching tags = +15% effectiveness
- 4+ matching tags = +20% effectiveness (capped)

**Integration Points**:
- `entities/components/skill_manager.py:_apply_combat_skill_with_context()` - Combat skills
- `entities/components/skill_manager.py:_apply_skill_effect()` - Buff-based skills
- Console output shows affinity bonus: `⚡ SkillName Lv2 (+10% affinity)`

### Tool Efficiency Bonus (NOW ACTIVE)
Classes with relevant tags get tool efficiency bonuses applied when class is selected:
- `nature` tag → +10% axe efficiency (Rangers)
- `gathering` tag → +5% axe efficiency, +10% pickaxe efficiency (Scavengers)
- `explorer` tag → +5% pickaxe efficiency (Scavengers)
- `physical`/`melee` tags → +5% each to tool damage in combat

**Integration Points**:
- `systems/class_system.py:get_tool_efficiency_bonus()` - Calculates bonus
- `entities/character.py:_on_class_selected()` - Applies bonus when class is set
- Tool tooltips show class bonus when hovering over equipped tools

### Files Changed
- `data/models/classes.py` - Added tags, preferred_damage_types, preferred_armor_type fields
- `data/databases/class_db.py` - Load tag data from JSON
- `progression/classes-1.JSON` - Added tags to all 6 classes
- `Definitions.JSON/tag-definitions.JSON` - Added class, playstyle, armor_type categories
- `systems/class_system.py` - Added tool efficiency/damage bonus methods
- `entities/character.py` - Added _on_class_selected callback
- `entities/components/skill_manager.py` - Integrated skill affinity bonus
- `rendering/renderer.py` - Added class tooltips and tool tooltips

---

## Non-Tag-Driven Systems Identified

The following systems should be converted to tag-driven for consistency:

| System | Current Implementation | Status |
|--------|----------------------|--------|
| Class Selection | Hardcoded stat bonuses | ✅ NOW TAG-DRIVEN |
| Skill Affinity | Same for all classes | ✅ NOW INTEGRATED IN COMBAT |
| Starting Tools | Fixed copper tools for all classes | ✅ NOW TAG-DRIVEN (efficiency bonuses) |
| Starting Equipment | Fixed armor/weapons | ⏳ FUTURE: Use class tags to select gear |

---

## Changelog

| Date | Commit | Changes |
|------|--------|---------|
| Current | TBD | Tag-driven class system, enchantment tests, class tag tests |
| Previous | 0531b65 | Inventory spacing fix, tooltip z-order, icon_path restoration |
| Previous | 9107a36 | Created MASTER_ISSUE_TRACKER.md |
| Previous | aa01674 | Fixed encoding corruption in README.md |

---

## Notes for Testers

1. **Debug Output**: Many enchantments print debug messages (emoji prefixed). Watch the console for confirmation of triggers.

2. **Enchantment Sources**: To test enchantments, you'll need to either:
   - Use the enchanting minigame to apply them
   - Use debug commands to spawn enchanted items
   - Edit save file to add enchantments manually

3. **Known Issue**: The base health regeneration only activates after 5 seconds of no combat. The enchantment-based regen is ALWAYS active.

4. **Verification Method**: Compare expected console output with actual output. If enchantments aren't printing their trigger messages, they may not be firing.
