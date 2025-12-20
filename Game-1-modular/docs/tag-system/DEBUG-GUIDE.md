# Tag System Debug Guide

**Purpose**: This guide explains all the debug output added to verify the tag system is working correctly, not just "not crashing".

## Quick Start: Verification Checklist

Run the game and perform these actions to see debug output:

1. ✓ **Craft a test recipe** → Should see smithing craft output with tags
2. ✓ **Place a turret near training dummy** → Should see turret attack output with tags
3. ✓ **Spawn training dummy and attack** → Should see tag breakdown
4. ✓ **Apply an enchantment** → Should see enchantment application output

If you DON'T see output or see "⚠️ NO TAGS" warnings, the system is NOT working correctly.

---

## 1. Test Recipe Loading

### What It Shows
When the game starts, each crafting system reports how many recipes it loaded:
```
[Smithing] Loaded 45 recipes from 50 total
[Alchemy] Loaded 12 recipes from 15 total
[Refining] Loaded 8 recipes from 10 total
```

### How to Interpret
- **"from X total"** means X recipes passed the stationType filter
- Test recipes should be included in these counts
- If counts seem too low, recipes might not be loading

### Expected Test Recipes (recipes-tag-tests.JSON)
- **Smithing**: 4 test recipes (max_tags, conflicting_hands, no_functional_tags, empty_tags)
- **Alchemy**: 6 test recipes (explicit_potion, explicit_transmutation, etc.)
- **Refining**: 5 test recipes (all_bonuses, high_probability, etc.)

### Where to Find Recipes
Open the smithing/alchemy/refining UI and scroll through recipes. Look for:
- `test_smithing_*` in smithing station
- `test_alchemy_*` in alchemy station
- `test_refining_*` in refining station

---

## 2. Smithing Craft Debug Output

### What It Shows
When you craft a smithing item (instant or minigame):
```
⚒️  SMITHING CRAFT: iron_sword
   Recipe: recipe_iron_sword_1h
   Recipe Tags: weapon, sword, 1H, melee, slashing
   ✓ Inherited Tags: 1H, melee, slashing
   Rarity: common
```

### How to Interpret
- **Recipe Tags**: ALL tags from recipe metadata
- **Inherited Tags**: Only functional tags that pass through to item
- **⚠️  NO TAGS INHERITED**: Recipe has no functional combat/damage tags

### Red Flags
- Recipe has tags but "NO TAGS INHERITED" → Tag filtering too aggressive
- No output at all when crafting → Craft method not being called

### Test with Test Recipes
1. Craft `test_ultimate_sword` (test_smithing_max_tags)
   - Should inherit: 1H, 2H, versatile, melee, slashing, piercing, crushing, fast, precision, reach, armor_breaker, cleaving
2. Craft `test_plain_sword` (test_smithing_no_functional_tags)
   - Should show: "⚠️  NO TAGS INHERITED"

---

## 3. Turret Attack Debug Output

### What It Shows
When a turret attacks an enemy:
```
🏹 TURRET ATTACK
   Turret: arrow_turret_tier1
   Target: Training Dummy
   Tags: piercing, fast, single
   Effect Params: {'damage': 15, 'damage_type': 'physical'}
   ✓ Effect executed successfully
```

### How to Interpret
- **Tags**: Tags configured on the turret (from item/recipe)
- **Effect Params**: Parameters passed to effect_executor
- **✓ Effect executed successfully**: Effect_executor processed tags correctly
- **✗ Effect execution FAILED**: Error in effect_executor (check error message)

### Legacy Mode Warning
If turret has NO tags configured:
```
⚠️  TURRET LEGACY ATTACK (NO TAGS)
   Turret: basic_turret
   Target: Training Dummy
   Damage: 10
```
This means turret is using old damage system, not tag system.

### Red Flags
- Turret fires but no output → Turret system not calling _attack_enemy
- "LEGACY ATTACK" for turrets that SHOULD have tags → Tags not being set on turret
- "Effect execution FAILED" → Bug in effect_executor

---

## 4. Training Dummy Output (CRITICAL)

### What It Shows
When ANY entity damages training dummy (player, turret, trap, status effect):
```
🎯 TRAINING DUMMY HIT #5
   Attacker: arrow_turret_tier1
   Damage: 18.5 (physical)
   🏷️  Attack Tags: piercing, fast, single
      Damage Types: piercing
      Properties: fast
      Geometry: single
   HP: 9907.5/10000.0 (99.1%)
   Total damage taken: 92.5
```

### How to Interpret
- **Attacker**: Source of damage (player, turret ID, effect name)
- **Attack Tags**: Tags passed to take_damage (THIS IS THE KEY!)
- **Categorized tags**: Breaks down tags by type for easy reading
- **⚠️  NO TAGS**: Damage source didn't pass tags OR used legacy system

### Critical Test: Turret → Training Dummy
1. Spawn training dummy: `/spawn_dummy` or via debug menu
2. Place turret near dummy (in range)
3. Wait for turret to fire
4. **EXPECTED**: Should see BOTH outputs:
   - 🏹 TURRET ATTACK (from turret_system.py)
   - 🎯 TRAINING DUMMY HIT (from training_dummy.py)
5. **Check**: Training dummy output should show tags

### Red Flags
- Dummy HP goes down but NO OUTPUT → take_damage not being called (broken)
- "⚠️  NO TAGS" for turret attacks → Tags not being passed from turret → effect_executor → dummy
- Only shows tags for PLAYER attacks but not turrets → effect_executor not passing tags parameter

---

## 5. Enchantment Application Debug Output

### What It Shows
When an enchantment is applied to an item:
```
✨ ENCHANTMENT APPLIED
   Item: iron_sword (Iron Sword)
   Enchantment: Fire Aspect I (fire_aspect_1)
   Effect: {'type': 'onHit', 'status': 'burning', 'duration': 3, 'damage': 5}
   Total Enchantments: 1
```

### How to Interpret
- **Item**: Item receiving enchantment
- **Enchantment**: Name and ID of enchantment
- **Effect**: Full effect configuration (shows what SHOULD happen)
- **Total Enchantments**: How many enchantments item now has

### Red Flags
- No output when applying enchantment → apply_enchantment not being called
- Effect looks wrong → Enchantment JSON has wrong data
- **IMPORTANT**: This only shows enchantment APPLIED, not TRIGGERED in combat

### Known Issue: Enchantment Effects in Combat
**Current Status**: Enchantments can be APPLIED to items, but effect TRIGGERING during combat may not be implemented yet.

If you see:
- ✨ ENCHANTMENT APPLIED (fire aspect)
- Player attacks enemy with enchanted weapon
- No burning status applied to enemy

**Diagnosis**: OnHit enchantment effects not hooked up to combat system yet.

**Next Steps**: Search for "onHit" effect processing in combat_manager.py. May need to add enchantment effect execution after damage calculation.

---

## 6. Status Effects on Training Dummy

### What It Shows
If training dummy has active status effects (burn, poison, etc.):
```
📋 Active Status Effects:
   - burning (x1, 2.8s, 5.0 dmg/tick)
   - poison (x2, 5.0s, 3.0 dmg/tick)
```

### How to Interpret
- **Effect name**: Status effect type
- **Stacks**: How many stacks active
- **Duration**: Seconds remaining
- **dmg/tick**: Damage per tick (if applicable)

### How to Test
1. Place fire turret (if configured with 'burning' tag)
2. OR apply fire aspect enchantment to weapon
3. Attack training dummy
4. **EXPECTED**: Should see burning in status effects list

### Red Flags
- Enchantment applied but status never appears → OnHit not triggering
- Tag configured but status never appears → Effect_executor not applying status

---

## 7. Tag Debug Logger (Optional)

### What It Shows
If tag debug logging is enabled, you'll see detailed tag processing:
```
[TAG-DEBUG] ⚒️  Smithing: Recipe 'recipe_iron_sword_1h' tag inheritance
   recipe_tags=['weapon', 'sword', '1H', 'melee', 'slashing', 'starter']
   inherited=['1H', 'melee', 'slashing']
   filtered=['weapon', 'sword', 'starter']
```

### How to Enable
Tag debug logger may output to console automatically, or may need to be enabled in core/tag_debug.py.

### How to Interpret
- **inherited**: Tags that PASSED the filter (will be on item)
- **filtered**: Tags that were REMOVED (metadata only)

---

## Common Debugging Scenarios

### Scenario 1: "I crafted an item but don't know if it has tags"

**Action**: Craft the item and check console output.

**Look For**:
```
⚒️  SMITHING CRAFT: iron_sword
   ✓ Inherited Tags: 1H, melee, slashing
```

**If you see "⚠️  NO TAGS INHERITED"**: Recipe doesn't have functional tags OR tag filtering is broken.

---

### Scenario 2: "Turret damages dummy but I can't tell if tags are working"

**Action**: Place turret near dummy and watch console.

**Expected Output Sequence**:
```
🏹 TURRET ATTACK
   Turret: arrow_turret_tier1
   Tags: piercing, fast, single
   ✓ Effect executed successfully

🎯 TRAINING DUMMY HIT #1
   Attacker: arrow_turret_tier1
   🏷️  Attack Tags: piercing, fast, single
      Damage Types: piercing
      Properties: fast
      Geometry: single
```

**Red Flags**:
- Only see 🏹 TURRET ATTACK but no 🎯 TRAINING DUMMY HIT → take_damage not being called
- See 🎯 but "⚠️  NO TAGS" → effect_executor not passing tags to take_damage
- No output at all → Turret not attacking (check range, target acquisition)

---

### Scenario 3: "Fire aspect enchant applied but enemy doesn't burn"

**Step 1**: Verify enchantment was applied:
```
✨ ENCHANTMENT APPLIED
   Enchantment: Fire Aspect I (fire_aspect_1)
   Effect: {'type': 'onHit', 'status': 'burning', ...}
```

**Step 2**: Attack enemy and check for burning status.

**Step 3**: If no burning appears:
- **Diagnosis**: OnHit enchantment effects not implemented in combat system
- **Fix Required**: Add enchantment effect processing to player_attack_enemy in combat_manager.py

---

### Scenario 4: "Test recipes aren't showing up"

**Check**: Game startup should show:
```
[Smithing] Loaded 45 recipes from 50 total
```

**If counts are lower than expected**:
1. Check recipes-tag-tests.JSON exists in recipes.JSON/
2. Check file is valid JSON (no syntax errors)
3. Check stationType field matches crafter (smithing/alchemy/refining)

**To Test**:
1. Open smithing UI
2. Scroll through recipes
3. Look for recipes starting with "test_"

---

## Summary: What Debug Output Proves

| Debug Output | What It Proves |
|--------------|----------------|
| Recipe load counts | Test recipes loading correctly |
| ⚒️  SMITHING CRAFT | Tag inheritance working in crafting |
| 🏹 TURRET ATTACK | Turret calling effect_executor with tags |
| 🎯 TRAINING DUMMY HIT | Tags flowing all the way to damage receiver |
| ✨ ENCHANTMENT APPLIED | Enchantments being added to items |
| 📋 Active Status Effects | Status effects being tracked on entity |

**Goal**: Every tag operation should have visible output. If you're wondering "is this working?", the debug output should answer definitively YES or NO.

---

## Next Steps After Debugging

Once you've verified the tag system is working:

1. **Remove or disable debug output** in production build
2. **Add configuration flag** to toggle debug mode on/off
3. **Create tag verification command** (e.g., `/verify_tags`) for quick testing
4. **Document edge cases** found during testing

---

## Known Limitations

### Enchantment OnHit Effects
- **Status**: Enchantments can be APPLIED but may not TRIGGER in combat
- **Reason**: OnHit effect processing may not be implemented in combat flow
- **Debug Output**: Shows enchantment applied but NOT when it triggers
- **Fix Required**: Add enchantment effect execution in combat_manager.py

### Tag Flow Visibility
- **Current**: Can see tags at start (recipe) and end (training dummy)
- **Missing**: Can't see intermediate tag processing in effect_executor
- **Enhancement**: Add debug output to effect_executor._apply_damage to show tag routing

### Test Recipe Coverage
- **Current**: 15 test recipes covering edge cases
- **Missing**: No test recipes for enchanting (future work)
- **Missing**: No test recipes for cooking/woodworking (future work)

---

## FAQ

**Q: I see "⚠️  NO TAGS" on training dummy. Is this bad?**
A: Depends on the source. If it's a legacy enemy or old turret, that's expected. If it's a NEW turret/weapon that SHOULD have tags, that's a bug.

**Q: Enchantment shows applied but doesn't work in combat. Bug?**
A: Likely. OnHit enchantment effects may not be hooked up to combat system yet. This is a known limitation.

**Q: Too much console spam. How do I reduce it?**
A: For now, output is always on. Future work: Add debug mode toggle in settings or via command line flag.

**Q: Can I add my own debug output?**
A: Yes! Follow the pattern:
```python
print(f"\n🔍 DEBUG: {description}")
print(f"   Detail: {value}")
```
Use emoji for easy visual scanning.

**Q: How do I test probabilistic bonuses (refining)?**
A: Run the same refining recipe multiple times. You should see DIFFERENT outputs sometimes (bonus yield, rarity upgrade). Check console for "🎲 PROBABILISTIC BONUS ACTIVATED!".

---

**Version**: 1.0
**Last Updated**: 2025-12-20
**Related Docs**: TESTING-GUIDE.md, CRAFTING-TESTS.md, TAG-REFERENCE.md
