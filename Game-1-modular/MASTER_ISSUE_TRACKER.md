# Master Issue Tracker

**Created**: 2025-12-30
**Purpose**: Comprehensive tracking of all known issues, improvements, and testing requirements

---

## Quick Status Overview

| Category | Issue | Priority | Status | Effort |
|----------|-------|----------|--------|--------|
| Testing | Enchantments (5 missing) | HIGH | Needs Integration | 2-3 hrs |
| Testing | Hostile/Engineering Tags | MEDIUM | Needs Testing | 1-2 hrs |
| Testing | Turret Status Effects | LOW | Implemented | 30 min |
| Bug | Inventory Click Misalignment | **CRITICAL** | Needs Fix | 30 min |
| Bug | Default Save Loading | HIGH | Needs Fix | 1 hr |
| UI | Tooltip Z-Order | MEDIUM | Needs Fix | 30 min |
| UI | Class Selection Tags | LOW | Enhancement | 1-2 hrs |
| UI | Crafting Missing Items | LOW | Consistent | N/A |
| Content | Crafting Stations JSON | WAITLIST | Placeholder | 2-3 hrs |
| **Overhaul** | Crafting UI & Minigames | **HIGH** | Planning Complete | Multi-week |

---

## SECTION 1: TESTING REQUIRED

### 1.1 Enchantment System Testing

**Status**: 9/17 enchantments working, 5 need integration, 2 deferred

#### Working Enchantments (Test to Verify)
| # | Enchantment | Type | Location | Test Method |
|---|-------------|------|----------|-------------|
| 1 | Sharpness I-III | `damage_multiplier` | equipment.py:65, game_engine.py:349 | Attack enemy, check damage increase |
| 2 | Protection I-III | `defense_multiplier` | combat_manager.py:1188 | Take damage, check reduction |
| 3 | Efficiency I-II | `gathering_speed_multiplier` | character.py:793 | Harvest resource, check speed |
| 4 | Fortune I-II | `bonus_yield_chance` | character.py:847 | Harvest many resources, check bonus drops |
| 5 | Unbreaking I-II | `durability_multiplier` | character.py:818 | Use tool repeatedly, check durability loss |
| 6 | Fire Aspect | `damage_over_time` | combat_manager.py:780-800 | Attack enemy, check burn applied |
| 7 | Poison | `damage_over_time` | combat_manager.py:780-800 | Attack enemy, check poison applied |
| 8 | Swiftness | `movement_speed_multiplier` | character.py:601 | Equip boots, check speed increase |
| 9 | Thorns | `reflect_damage` | combat_manager.py:1221-1242 | Get hit, check enemy takes damage |

#### Enchantments Needing Integration
| # | Enchantment | Type | JSON Location | Integration Point |
|---|-------------|------|---------------|-------------------|
| 10 | **Knockback** | `knockback` | recipes-enchanting-1.JSON:627-652 | combat_manager.py:802-810 (partial) |
| 11 | **Lifesteal** | `lifesteal` | recipes-enchanting-1.JSON:686-710 | combat_manager.py:670-679 (partial) |
| 12 | **Health Regen** | `health_regeneration` | recipes-enchanting-1.JSON:514-540 | Needs periodic update loop |
| 13 | **Frost Touch** | `slow` | recipes-enchanting-1.JSON:183-205 | combat_manager.py:812-821 (partial) |
| 14 | **Chain Damage** | `chain_damage` | recipes-enchanting-1.JSON:207-235 | combat_manager.py:683-703 (implemented!) |

#### Deferred Enchantments
| # | Enchantment | Type | Reason |
|---|-------------|------|--------|
| 15 | Self-Repair | `durability_regeneration` | Needs game loop periodic update |
| 16 | Weightless | `weight_multiplier` | No weight system exists |
| 17 | Silk Touch | `harvest_original_form` | Needs harvesting system changes |

**Key Files**:
- Definitions: `recipes.JSON/recipes-enchanting-1.JSON`
- Equipment Model: `data/models/equipment.py`
- Combat Application: `Combat/combat_manager.py:758-822`
- Gathering Application: `entities/character.py:787-853`

---

### 1.2 Hostile Tags on Turrets

**Status**: IMPLEMENTED - Needs Testing

Turrets can receive status effects from enemy abilities:

**Implementation Locations**:
- `data/models/world.py:152-252` - PlacedEntity with status_effects field
- `systems/turret_system.py:34-52` - Status effect update and stun/freeze checks
- `Combat/combat_manager.py:328-342` - Enemies include turrets in available_targets

**Status Effects Turrets Can Receive**:
| Effect | Impact | Flag |
|--------|--------|------|
| Stun | Cannot attack | `is_stunned = True` |
| Freeze | Cannot attack | `is_frozen = True` |
| Root | Cannot move (N/A for turrets) | `is_rooted = True` |
| Burn | Takes fire damage over time | `is_burning = True` |
| Poison | Takes poison damage over time | Via status_effects list |
| Slow | Reduced attack speed | Via status_effects list |

**Test Method**:
1. Place a turret near enemies
2. Wait for enemy to use special ability with stun/freeze tag
3. Verify turret stops attacking when stunned/frozen
4. Verify turret resumes after effect expires

---

### 1.3 Engineering Tags (Traps/Bombs/Utility)

**Status**: Implemented per COMPLETE_FEATURE_COVERAGE_PLAN.md

| Device Type | Items | Status |
|-------------|-------|--------|
| Turrets (5) | basic_arrow, fire_arrow, lightning_cannon, flamethrower, laser | Working |
| Traps (3) | spike_trap, frost_mine, bear_trap | Working |
| Bombs (3) | simple_bomb, fire_bomb, cluster_bomb | Working |
| Utility (3) | healing_beacon, net_launcher, emp_device | Working |

**Test Method**:
1. Place each device type
2. Verify turrets attack enemies
3. Verify traps trigger on enemy proximity (2.0 unit radius)
4. Verify bombs detonate after fuse timer (3.0 seconds default)
5. Verify utility devices function (healing, slowing, stunning constructs)

---

## SECTION 2: BUGS TO FIX

### 2.1 Inventory Click Misalignment [CRITICAL]

**Root Cause**: Spacing mismatch between rendering and click detection

| Component | File | Line | Spacing Value |
|-----------|------|------|---------------|
| Renderer | renderer.py | 2472 | `spacing = 10` |
| Right-click handler | game_engine.py | 872 | `spacing = 5` |
| Left-click handler | game_engine.py | 1366 | `spacing = 5` |
| Drag end handler | game_engine.py | 2820 | `spacing = 5` |

**Additional Issues**:
- Right-click: `start_y = INVENTORY_PANEL_Y` should be `+125`
- Drag end: Same start_y issue

**Impact**: After loading saves (or any time), inventory clicks register on wrong slots

**Fix Required**:
```python
# In game_engine.py, change ALL instances of:
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
# To:
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10

# Also fix start_y in handle_right_click() and handle_mouse_release():
start_y = Config.INVENTORY_PANEL_Y + 125  # Not just INVENTORY_PANEL_Y
```

---

### 2.2 Default Save Loading Issues

**Issues Found**:

1. **Missing icon_path on equipment** (HIGH)
   - Location: `entities/character.py:369-384`
   - Problem: EquipmentItem creation doesn't restore `icon_path`
   - Fix: Add `icon_path=eq_data.get("icon_path", "")` to constructor

2. **Default save missing icon_path data** (HIGH)
   - Location: `saves/default_save.json`
   - Problem: Equipment items don't include icon_path field
   - Fix: Regenerate default save with icon_path data

3. **Spacing mismatch** (CRITICAL - see 2.1)
   - This is the PRIMARY cause of clicks not working after load

**Files to Modify**:
- `entities/character.py:369-384` - Add icon_path restoration
- `saves/default_save.json` - Regenerate with icon_path
- `game_engine.py:872, 1366, 2820` - Fix spacing values

---

### 2.3 Inventory Tooltip Z-Order

**Issue**: Tooltips can be covered by equipment menu

**Current Render Order** (game_engine.py:2932-3040):
1. render_world()
2. render_ui()
3. render_inventory_panel() - tooltips rendered here
4. render_skill_hotbar()
5. render_notifications()
6. **Modal UIs** (equipment, stats, skills) - rendered AFTER inventory

**Fix Options**:
1. Render tooltips AFTER modal UIs (requires tooltip state tracking)
2. Always render equipment UI BEFORE inventory panel
3. Create dedicated tooltip layer rendered last

**Location**: `core/game_engine.py:2932-3040` and `rendering/renderer.py:2522`

---

## SECTION 3: UI ENHANCEMENTS

### 3.1 Class Selection Benefits Display

**Current State**: Only displays stat boosts, no tag integration

**Classes Defined** (progression/classes-1.JSON):
| Class | Stat Bonuses | Starting Skill |
|-------|--------------|----------------|
| Warrior | +30 HP, +10% melee damage | Battle Rage |
| Ranger | +15% speed, +10% crit | Forestry Frenzy |
| Scholar | +100 mana, +10% recipe discovery | Alchemist's Touch |
| Artisan | +10% craft speed, +10% first try | Smithing Focus |
| Scavenger | +100 carry, +20% rare drops | Treasure Hunter's Luck |
| Adventurer | +50 HP/mana, +5% all | Versatile Beginning |

**Enhancement Options**:
1. Add tag-based bonuses to classes (e.g., `["fire_resist", "10%"]`)
2. Display all bonuses on selection screen (currently shows top 2)
3. Show starting skill description

**Files**:
- Class definitions: `progression/classes-1.JSON`
- Class system: `systems/class_system.py`
- Selection UI: `rendering/renderer.py:3536-3614`

---

### 3.2 Crafting UI Missing Items Display

**Current State**: CONSISTENT across all disciplines

All 5 disciplines display ingredients identically:
- **GREEN** text: Have enough (`has >= required`)
- **RED** text: Insufficient (`has < required`)
- Format: `Material Name: {current}/{required}`

**Backend Inconsistency Found**:
- Only Smithing logs detailed console messages
- Other disciplines return generic "Insufficient {materialId}"

**Files**:
- Frontend display: `Crafting-subdisciplines/crafting_simulator.py:1064-1075`
- Backend checks: Each discipline file (smithing.py, alchemy.py, etc.)

**No fix needed** - UI works correctly. Backend logging is optional enhancement.

---

## SECTION 4: CONTENT GAPS (WAITLIST)

### 4.1 Crafting Stations JSON

**Current Stations Defined** (12):
| Station | Tier | Has Icon | Status |
|---------|------|----------|--------|
| forge_t1 | 1 | Yes | Working |
| forge_t2 | 2 | Yes | Working |
| forge_t3 | 3 | Yes | Working |
| forge_t4 | 4 | **NO** | Missing icon |
| refinery_t1 | 1 | Yes | Working |
| refinery_t2 | 2 | Yes | Working |
| alchemy_table_t1 | 1 | Yes | Working |
| alchemy_table_t2 | 2 | Yes | Working |
| engineering_bench_t1 | 1 | Yes | Working |
| engineering_bench_t2 | 2 | Yes | Working |
| enchanting_table_t1 | 1 | Yes | Working |
| enchanting_table_t2 | 2 | **NO** | Missing icon |

**Stations Missing from Definitions** (referenced in recipes):
| Station | Recipes Using It |
|---------|------------------|
| refinery_t3 | 11 recipes |
| refinery_t4 | 12 recipes |
| alchemy_table_t3 | 5 recipes |
| alchemy_table_t4 | 1 recipe |
| enchanting_table_t3 | 18 recipes |
| enchanting_table_t4 | 4 recipes |
| engineering_bench_t3 | 7 recipes |

**Note**: `refinery_t3` is defined in `items-smithing-2.JSON` (wrong file) - needs moving to `crafting-stations-1.JSON`

**Missing Icons**:
- `assets/items/stations/forge_t4.png`
- `assets/items/stations/enchanting_table_t2.png`

---

## SECTION 5: IMPLEMENTATION GUIDES

### Guide 5.1: Fixing Inventory Click Detection

```python
# File: core/game_engine.py

# === FIX 1: handle_right_click() around line 870 ===
# BEFORE:
start_x, start_y = 20, Config.INVENTORY_PANEL_Y
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5

# AFTER:
tools_y = Config.INVENTORY_PANEL_Y + 55
start_x = 20
start_y = tools_y + 50 + 20  # = INVENTORY_PANEL_Y + 125
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10

# === FIX 2: handle_mouse_click() around line 1366 ===
# BEFORE:
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5

# AFTER:
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10

# === FIX 3: handle_mouse_release() around line 2820 ===
# BEFORE:
start_x, start_y = 20, Config.INVENTORY_PANEL_Y
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5

# AFTER:
tools_y = Config.INVENTORY_PANEL_Y + 55
start_x = 20
start_y = tools_y + 50 + 20  # = INVENTORY_PANEL_Y + 125
slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 10
```

---

### Guide 5.2: Adding Missing Enchantment Integrations

#### Knockback Enchantment
```python
# File: Combat/combat_manager.py, in _apply_weapon_enchantment_effects()
# Add after line 810:

elif effect_type == 'knockback':
    knockback_distance = effect.get('value', 2.0)
    knockback_params = {'knockback_distance': knockback_distance}
    from core.effect_executor import get_effect_executor
    executor = get_effect_executor()
    executor._apply_knockback(self.character, enemy, knockback_params)
    print(f"   Knockback triggered!")
```

#### Lifesteal Enchantment
```python
# File: Combat/combat_manager.py, after enemy.take_damage() around line 654

# LIFESTEAL ENCHANTMENT
if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
    for ench in equipped_weapon.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'lifesteal':
            lifesteal_percent = effect.get('value', 0.1)
            heal_amount = final_damage * lifesteal_percent
            self.character.health = min(self.character.max_health,
                                        self.character.health + heal_amount)
            print(f"   Lifesteal: Healed {heal_amount:.1f} HP")
```

#### Health Regeneration Enchantment
```python
# File: entities/character.py, in update() method or recalculate_stats()

# HEALTH REGENERATION ENCHANTMENT (needs periodic update)
regen_bonus = 0.0
armor_slots = ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']
for slot in armor_slots:
    armor_piece = self.equipment.slots.get(slot)
    if armor_piece and hasattr(armor_piece, 'enchantments'):
        for ench in armor_piece.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'health_regeneration':
                regen_bonus += effect.get('value', 1.0)  # HP per second

# Apply in periodic update (if update() is called with dt)
if regen_bonus > 0:
    self.health = min(self.max_health, self.health + regen_bonus * dt)
```

---

### Guide 5.3: Fixing Icon Path Restoration

```python
# File: entities/character.py, around line 369-384
# In the EquipmentItem creation during restore_from_save()

item_stack.equipment_data = EquipmentItem(
    item_id=eq_data["item_id"],
    name=eq_data.get("name", eq_data["item_id"]),
    tier=eq_data.get("tier", 1),
    rarity=eq_data.get("rarity", "common"),
    slot=eq_data.get("slot", "mainHand"),
    damage=damage,
    defense=eq_data.get("defense", 0),
    durability_current=eq_data.get("durability_current", 100),
    durability_max=eq_data.get("durability_max", 100),
    attack_speed=eq_data.get("attack_speed", 1.0),
    weight=eq_data.get("weight", 1.0),
    range=eq_data.get("range", 1.0),
    hand_type=eq_data.get("hand_type", "default"),
    item_type=eq_data.get("item_type", "weapon"),
    icon_path=eq_data.get("icon_path", "")  # ADD THIS LINE
)
```

---

## SECTION 5.5: UNIMPLEMENTED MECHANICS

These mechanics are documented but have NO code implementation:

### Block/Parry Mechanics
**Status**: ❌ NOT IMPLEMENTED
**Documented In**: `docs/tag-system/TAG-DEFINITIONS-PHASE2.md`
**Description**: Chance-based damage negation with counter-attack option
**What's Needed**:
- Add `block_chance` and `parry_chance` stats to CharacterStats
- Add shield items with block values
- Modify `combat_manager.py` to check for block/parry before applying damage
- Add counter-attack damage on successful parry
- UI feedback for successful blocks/parries

**Estimated Effort**: 4-6 hours

### Summon Mechanics
**Status**: ❌ NOT IMPLEMENTED
**Documented In**: `docs/FUTURE_MECHANICS_TO_IMPLEMENT.md:72-126`
**Description**: Spawn temporary allied entities that fight for the player
**What's Needed**:
- Entity spawning system with ownership tracking
- Summon allegiance/faction system (friendly vs hostile)
- Temporary entity lifetime and cleanup
- Summon AI behavior (follow player, attack enemies)
- Skills/items that create summons

**Estimated Effort**: 8-12 hours

---

## SECTION 6: PRIORITY ORDER

### Immediate (Critical Bugs)
1. **Fix inventory click misalignment** - Breaks core gameplay
2. **Fix save loading icon_path** - Visual regression

### Short-term (Testing & Verification)
3. Test all 9 working enchantments
4. Test turret status effects
5. Test traps/bombs/utility devices

### Medium-term (Enhancements)
6. Integrate 5 missing enchantments
7. Fix tooltip z-order
8. Enhance class selection display

### Long-term (Waitlist)
9. Add missing crafting station JSONs
10. Create missing station icons
11. Add class tag-based bonuses

---

## SECTION 6.5: CRAFTING UI & MINIGAME OVERHAUL

**Plan Document**: `docs/CRAFTING_UI_MINIGAME_OVERHAUL_PLAN.md`
**Created**: January 4, 2026
**Status**: Phase 1 & 2 Complete - Phase 3 (Polish/Balance) Pending

### Overview

Major overhaul of crafting system with:
- Material-based difficulty calculation (not just tier)
- Polished, distinct UI for each discipline
- Proportional rewards tied to difficulty

### Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation + Smithing + Refining | ✅ **COMPLETE** |
| 2 | Alchemy + Engineering + Enchanting | ✅ **COMPLETE** |
| 3 | Polish & balance tuning | 🔜 Pending Playtest |

### Phase 1 Completed Items

- ✅ `core/difficulty_calculator.py` - Linear tier points (T1=1, T2=2, T3=3, T4=4)
- ✅ `core/reward_calculator.py` - Proportional rewards with quality tiers
- ✅ Smithing difficulty/reward integration
- ✅ Smithing visual polish (forge/anvil aesthetic)
- ✅ Refining difficulty/reward integration with diversity multiplier
- ✅ Refining visual polish (lock mechanism aesthetic)
- ✅ Rarity-named difficulty thresholds (Common → Legendary)
- ✅ Tier-scaled failure penalties (30% → 90%)

### Phase 2 Completed Items

- ✅ Alchemy: Vowel-based volatility + `1.2^avg_tier` modifier
- ✅ Alchemy: Ingredient-type visual indicators (base/catalyst/reactive)
- ✅ Alchemy: Reward calculator integration with first-try bonus
- ✅ Engineering: Slot count × diversity formula
- ✅ Engineering: Rarity-based puzzle selection (common→legendary)
- ✅ Engineering: Reward calculator with puzzle completion scoring
- ✅ Enchanting: Material-based wheel distribution (green/red slices)
- ✅ Enchanting: Spin-progressive difficulty (later spins harder)
- ✅ Enchanting: Reward calculator with efficacy-based bonuses

### BALANCE TUNING REQUIRED (Post-Implementation)

| Item | Issue | Priority |
|------|-------|----------|
| **Difficulty scaling** | Currently too easy across all tiers | HIGH |
| **Reward scaling** | Currently too generous for difficulty | HIGH |
| **Timing windows** | May need further tightening for challenge | MEDIUM |
| **Quality tier thresholds** | May need adjustment for rarity feel | MEDIUM |

*Note: Balance tuning deferred until all disciplines implemented and playtested (Phase 3)*

### DEFERRED Items (Tracked Here)

| Item | Reason | Priority |
|------|--------|----------|
| Enchanting pattern minigame | Keep wheel spin, apply same difficulty system | Medium |
| User recipe creation system | Requires validation, persistence, UI | Low |
| Material-based sub-modifiers | Complexity - implement after core overhaul | Low |
| Sub-specialization mechanics | Complexity - implement after core overhaul | Low |
| Refining fuel system | Keep in V6 docs but skip implementation | Low |

### Key Design Decisions

1. **Difficulty Formula**: `material_points × diversity_multiplier`
   - Material points: `tier × quantity` (LINEAR scaling)
   - Diversity: `1.0 + (unique_materials - 1) × 0.1`

2. **Difficulty Thresholds** (rarity naming):
   - Common: 1-8 points
   - Uncommon: 9-20 points
   - Rare: 21-40 points
   - Epic: 41-70 points
   - Legendary: 71+ points

3. **Discipline-Specific Modifiers**:
   - Smithing: No diversity (single-focus craft)
   - Refining: Diversity multiplier applied
   - Alchemy: Vowel-based volatility + `1.2^avg_tier` (Phase 2)
   - Engineering: Slot count × diversity (Phase 2)

4. **Reward Scaling**: Harder difficulty = higher max bonus potential (1.0x to 2.5x)

5. **Tier-Scaled Penalties**: Common: 30% loss → Legendary: 90% loss on failure

6. **First-Try Bonus**: +10% performance boost on first attempt

### Files Created/Modified

| File | Status |
|------|--------|
| `core/difficulty_calculator.py` | ✅ Created + Phase 2 functions |
| `core/reward_calculator.py` | ✅ Created + Phase 2 functions |
| `Crafting-subdisciplines/smithing.py` | ✅ Updated (Phase 1) |
| `Crafting-subdisciplines/refining.py` | ✅ Updated (Phase 1) |
| `core/game_engine.py` | ✅ Updated (visual polish) |
| `Crafting-subdisciplines/alchemy.py` | ✅ Updated (Phase 2) |
| `Crafting-subdisciplines/engineering.py` | ✅ Updated (Phase 2) |
| `Crafting-subdisciplines/enchanting.py` | ✅ Updated (Phase 2) |

---

## SECTION 7: FILE QUICK REFERENCE

| System | Primary Files |
|--------|---------------|
| Enchantments | `recipes.JSON/recipes-enchanting-1.JSON`, `Combat/combat_manager.py:758-822`, `entities/character.py:787-853` |
| Turret Status | `data/models/world.py:152-252`, `systems/turret_system.py:34-52` |
| Inventory UI | `rendering/renderer.py:2396-2523`, `core/game_engine.py:870-902, 1358-1376, 2817-2833` |
| Class System | `progression/classes-1.JSON`, `systems/class_system.py`, `rendering/renderer.py:3536-3614` |
| Crafting UI | `Crafting-subdisciplines/crafting_simulator.py:1064-1105` |
| Save System | `systems/save_manager.py`, `entities/character.py:298-497` |
| Crafting Stations | `Definitions.JSON/crafting-stations-1.JSON` |

---

**Last Updated**: 2026-01-04
