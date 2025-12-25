# Known Limitations and Missing Features

**Last Updated**: 2025-12-25
**Status**: Documenting current system boundaries and unimplemented features

---

## 📊 System Status Overview

| System | Data Loading | Game Mechanics | Icons | Notes |
|--------|--------------|----------------|-------|-------|
| **Equipment (Weapons/Armor)** | ✅ FULL | ✅ FULL | ⚠️ PARTIAL | Core + Update-N load correctly |
| **Skills** | ✅ FULL | ✅ FULL | ✅ FULL | Tag system functional |
| **Enemies** | ✅ FULL | ✅ FULL | ⚠️ PARTIAL | Special abilities work |
| **Materials** | ✅ FULL | ✅ FULL | ⚠️ PARTIAL | Stackable items work |
| **Devices** | ✅ FULL | ❌ PARTIAL | ❌ MISSING | Data loads, effects not all implemented |
| **Consumables** | ✅ FULL | ⚠️ PARTIAL | ⚠️ PARTIAL | Potions work, some effects missing |
| **Recipes** | ⚠️ CORE ONLY | ✅ FULL | N/A | NOT integrated with Update-N |
| **Crafting Stations** | ✅ FULL | ✅ FULL | ⚠️ PARTIAL | Work but limited recipe support |

---

## ⚠️ Major Limitations

### 1. Recipe System NOT Update-N Integrated

**Issue**: RecipeDatabase uses hardcoded file paths, NOT auto-discovery.

**Impact**:
- ❌ Update-1 weapons appear in inventory but **cannot be crafted**
- ❌ No recipes auto-generate for Update-N content
- ❌ Manual recipe creation required for each Update

**Affected Items**:
- All Update-1 weapons (lightning_chain_whip, inferno_blade, void_piercer, frostbite_hammer, blood_reaver)
- Any future Update-N equipment

**Workarounds**:
1. Manually create recipe JSONs in `recipes.JSON/`
2. Use debug/cheat commands to spawn items
3. Add Update-N recipe support (requires code changes)

**Status**: 🔴 **BLOCKS FULL UPDATE-N WORKFLOW**

---

### 2. Device Effects Not Implemented

**Issue**: Many engineering devices load data but have no functional effects.

**Unimplemented Devices**:

| Device | Loads? | Has Icon? | Effect Status |
|--------|--------|-----------|---------------|
| **grappling_hook** | ✅ Yes | ❌ No | ❌ No movement hook implemented |
| **healing_beacon** | ✅ Yes | ❌ No | ❌ No healing pulse effect |
| **jetpack** | ✅ Yes | ❌ No | ❌ No flight mechanics |
| **net_launcher** | ✅ Yes | ❌ No | ❌ No immobilize effect |
| **emp_device** | ✅ Yes | ❌ No | ❌ No EMP effect |
| **basic_arrow_turret** | ✅ Yes | ❌ No | ⚠️ Partial (turret AI incomplete) |
| **fire_arrow_turret** | ✅ Yes | ❌ No | ⚠️ Partial (turret AI incomplete) |
| **lightning_cannon** | ✅ Yes | ❌ No | ⚠️ Partial (turret AI incomplete) |
| **simple_bomb** | ✅ Yes | ❌ No | ⚠️ Partial (explosion works, placement incomplete) |
| **spike_trap** | ✅ Yes | ❌ No | ⚠️ Partial (trap mechanics incomplete) |

**Why**:
- Data loading ✅ works (MaterialDatabase loads them)
- Effect execution ❌ not implemented (game mechanics layer)
- Icon generation ❌ not run for devices

**Impact**:
- Devices appear in inventory
- Can be placed (if `placeable: true`)
- But do nothing when used/triggered

**Status**: 🟡 **DATA WORKS, MECHANICS DON'T**

---

### 3. Missing Icons

**Issue**: Icon generation not comprehensive for all content types.

**Missing Icon Categories**:
- ❌ All engineering devices (turrets, traps, bombs, utility)
- ⚠️ Some consumables (spot checked)
- ⚠️ Some materials (spot checked)
- ⚠️ Core weapons/armor (if not manually created)

**Why**:
- `create_placeholder_icons_simple.py` only runs on Update-N content
- Core content icons assumed to exist
- No audit/verification of icon coverage

**Impact**:
- Items show as blank/default icons
- No visual differentiation
- Poor user experience

**Workaround**:
```bash
# Generate icons for specific items
python tools/create_placeholder_icons_simple.py --json items.JSON/items-engineering-1.JSON
```

**Status**: 🟡 **COSMETIC ISSUE**

---

### 4. Tag Warnings for Area Skills

**Issue**: Skills with `"target": "area"` trigger warnings when loaded/tested.

**Example Warning**:
```
[TAG_WARNING] Combat skill meteor_strike is area effect - needs combat context
⚠ Area skill requires combat context
```

**Why**:
- Skills are tested during loading outside combat
- Area skills need enemy targets to function
- Warning is technically correct but spammy

**Affected Skills**:
- Update-1: meteor_strike, chain_lightning, arctic_cone, gravity_well
- Core: Any area-effect skills

**Impact**:
- ⚠️ Spam warnings in console
- ✅ Skills work fine in actual combat
- 😕 Confusing for developers

**Status**: 🟢 **BENIGN BUT ANNOYING**

---

## 📋 Detailed Feature Matrix

### Consumable Effects

| Effect Type | Implemented? | Notes |
|-------------|--------------|-------|
| **Healing (HP)** | ✅ Yes | Potions work |
| **Mana Restore** | ✅ Yes | Mana potions work |
| **Stat Buffs** | ⚠️ Partial | Simple buffs work, complex ones may not |
| **Status Resistance** | ⚠️ Partial | May not work for all status types |
| **DoT Effects** | ❌ No | Poison consumables don't apply DoT |
| **Crafting Buffs** | ❌ No | Efficiency oils don't work |

### Device Mechanics

| Mechanic | Implemented? | Notes |
|----------|--------------|-------|
| **Turret Placement** | ⚠️ Partial | Can place, AI incomplete |
| **Turret Targeting** | ⚠️ Partial | Basic targeting may work |
| **Turret Damage** | ⚠️ Partial | May fire but damage calculation incomplete |
| **Bomb Explosion** | ⚠️ Partial | Explosion works, placement mechanics incomplete |
| **Trap Triggering** | ❌ No | No trigger detection |
| **Utility Devices** | ❌ No | No special effects (grapple, heal beacon, etc.) |

### Tag System Coverage

| Tag Category | Support Level | Notes |
|--------------|---------------|-------|
| **Element Tags** | ✅ FULL | fire, ice, lightning, shadow, etc. |
| **Geometry Tags** | ✅ FULL | cone, circle, beam, chain, etc. |
| **Status Tags** | ✅ FULL | burn, shock, freeze, poison, etc. |
| **Mechanic Tags** | ⚠️ PARTIAL | pierce, knockback work; reflect, summon incomplete |
| **Target Tags** | ✅ FULL | player, enemy, ally, self |

---

## 🔧 Required Fixes for Full Production

### Priority 1: Recipe System Integration

**Required Changes**:
1. Add `load_recipe_updates()` to `update_loader.py`
2. Create `RecipeDatabase.load_from_file()` method (currently only `load_from_files()`)
3. Allow Update-N directories to include `recipes-*.JSON` files
4. OR implement auto-recipe generation for Update-N items

**Estimated Effort**: 2-4 hours
**Blocks**: Full Update-N crafting workflow

### Priority 2: Icon Audit and Generation

**Required Changes**:
1. Audit ALL items in ALL databases for missing icons
2. Generate placeholders for missing icons
3. Run icon generation on core content, not just Update-N
4. Add validation to `update_manager.py` to check icon coverage

**Estimated Effort**: 1-2 hours
**Blocks**: Polish and UX

### Priority 3: Device Effect Implementation

**Required Changes**:
1. Implement healing beacon pulse effect
2. Implement grappling hook movement
3. Implement jetpack flight
4. Implement net launcher immobilize
5. Implement EMP device effect
6. Complete turret AI and targeting
7. Complete trap trigger detection

**Estimated Effort**: 8-16 hours (major feature work)
**Blocks**: Engineering discipline functionality

### Priority 4: Tag Warning Cleanup

**Required Changes**:
1. Suppress warnings during skill loading/testing
2. Only show warnings during actual failed skill usage
3. OR move validation to separate validation pass

**Estimated Effort**: 30 minutes
**Blocks**: Clean console output

---

## 🎯 Update-N Workflow Status

### ✅ What Works End-to-End

```
1. Create Update-N directory
2. Add items/skills/enemies JSONs
3. Deploy with deploy_update.py
4. Content loads automatically
5. Skills work in combat
6. Enemies spawn with abilities
7. Tag effects trigger correctly
```

**Verified Working**: ✅ Equipment, Skills, Enemies, Materials (data loading)

### ❌ What Doesn't Work Yet

```
1. Crafting Update-N items
   → No recipes auto-generated
   → RecipeDatabase not integrated

2. Using all devices
   → Data loads but effects missing
   → Icons don't generate

3. Clean testing
   → Tag warnings spam console
   → No validation mode
```

**Needs Work**: ❌ Recipes, Device Effects, Icon Coverage

---

## 📝 Recommendations

### For Immediate Production Use

**DO**:
- ✅ Use Update-N for weapons with tag-driven effects
- ✅ Use Update-N for skills with combat tags
- ✅ Use Update-N for enemies with special abilities
- ✅ Use Update-N for materials/consumables

**DON'T**:
- ❌ Expect Update-N items to be craftable (no recipes)
- ❌ Expect all device effects to work (mechanics incomplete)
- ❌ Expect icons for all items (partial coverage)

**WORKAROUND**:
- Manually add recipes to `recipes.JSON/` for Update-N items
- Document which devices work vs don't
- Generate icons manually as needed

### For Full Production Readiness

**Must Fix**:
1. Recipe integration (2-4 hours)
2. Icon audit (1-2 hours)

**Nice to Have**:
3. Device effects (8-16 hours)
4. Tag warning cleanup (30 min)

**Total to Full Production**: ~4-8 hours for critical path (recipes + icons)

---

## 🔄 Current vs Desired State

### Current State

```
Update-N → Data Loads ✅
        → Appears in Inventory ✅
        → Can be Equipped ✅
        → Effects Work ✅
        → Can be Crafted ❌ (no recipes)
        → Has Icons ⚠️ (partial)
        → All Mechanics Work ⚠️ (skills/combat yes, devices no)
```

### Desired State

```
Update-N → Data Loads ✅
        → Appears in Inventory ✅
        → Can be Equipped ✅
        → Effects Work ✅
        → Can be Crafted ✅ (auto-recipes or Update-N recipes)
        → Has Icons ✅ (comprehensive generation)
        → All Mechanics Work ✅ (full device support)
```

**Gap**: Recipe integration + Icon coverage + Device mechanics

---

## 📊 Summary Table

| Feature | Data Loading | Game Mechanics | Icons | Recipes | Overall |
|---------|--------------|----------------|-------|---------|---------|
| **Update-N Weapons** | ✅ | ✅ | ⚠️ | ❌ | 🟡 75% |
| **Update-N Skills** | ✅ | ✅ | ✅ | N/A | ✅ 100% |
| **Update-N Enemies** | ✅ | ✅ | ⚠️ | N/A | 🟡 85% |
| **Update-N Materials** | ✅ | ✅ | ⚠️ | N/A | 🟡 85% |
| **Core Devices** | ✅ | ⚠️ | ❌ | ✅ | 🔴 50% |
| **Core Consumables** | ✅ | ⚠️ | ⚠️ | ✅ | 🟡 75% |

**Overall System Health**: 🟡 **75-80% Complete**

**To Reach 100%**: Fix recipes, icons, and device effects

---

**END OF LIMITATIONS DOCUMENTATION**
