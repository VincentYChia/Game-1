# Tag System Data Flow Bugs - CRITICAL FIXES

**Date**: 2025-12-21
**Status**: ✅ FIXED
**Commits**: e9bec31

## Executive Summary

After the initial tag system implementation, users reported that despite all the code being in place:
1. **Turrets showed "TURRET LEGACY ATTACK (NO TAGS)"** even after save/load fixes
2. **Status effect damage (burn, bleed, poison) showed "NO TAGS (legacy damage or tags not passed)"**

These issues revealed **data flow bugs** where tags existed in JSON files but weren't being passed through the entire processing chain. This document details the root cause analysis and fixes.

---

## 🐛 Bug #1: Turrets Loaded Without Tags

### Symptom
```
⚠️  TURRET LEGACY ATTACK (NO TAGS)
   Turret: lightning_cannon
   Target: Training Dummy
   Damage: 70.0
```

### User Impact
- Newly placed turrets worked correctly ✓
- Turrets loaded from save files had NO tags ✓ (Fixed in previous commit)
- **Turrets placed in current session STILL had NO tags** ✗

This last issue persisted even after the save/load fix, indicating a deeper problem.

### Root Cause Analysis

#### The Data Flow Chain
```
JSON File (effectTags)
    ↓
MaterialDatabase.load_stackable_items()
    ↓
MaterialDefinition (effect_tags, effect_params)
    ↓
GameEngine.handle_input() [item placement]
    ↓
WorldSystem.place_entity()
    ↓
PlacedEntity (tags, effect_params)
    ↓
TurretSystem._attack_enemy()
```

#### The Problem

The `MaterialDatabase` class has TWO loading methods:

1. **`load_from_file()`** (lines 22-69)
   - Used for: Materials from `items-general.JSON`
   - ✅ **Correctly extracts** `effectTags` and `effectParams` at lines 59-60:
     ```python
     effect_tags=mat_data.get('effectTags', []),
     effect_params=mat_data.get('effectParams', {})
     ```

2. **`load_stackable_items()`** (lines 130-200)
   - Used for: Devices, consumables, stations, etc.
   - ❌ **Does NOT extract** `effectTags` or `effectParams`
   - Lines 177-190 create MaterialDefinition but omit these fields

#### Why This Matters

**Turrets are devices**, loaded via `load_stackable_items()`, NOT `load_from_file()`.

When the game loads turret JSON data:
```json
{
  "itemId": "lightning_cannon",
  "effectTags": ["lightning", "single", "shock"],
  "effectParams": {
    "baseDamage": 70.0,
    "shock_chance": 0.3
  }
}
```

The `load_stackable_items()` method creates a MaterialDefinition with:
```python
MaterialDefinition(
    material_id="lightning_cannon",
    name="Lightning Cannon",
    # ... other fields ...
    effect="Shoots lightning bolts",
    # ❌ effect_tags MISSING - defaults to []
    # ❌ effect_params MISSING - defaults to {}
)
```

Later, when `game_engine.py` tries to extract tags during placement (lines 1412-1413):
```python
effect_tags = mat_def.effect_tags if hasattr(mat_def, 'effect_tags') else []
effect_params = mat_def.effect_params if hasattr(mat_def, 'effect_params') else {}
```

It gets empty lists/dicts because the MaterialDefinition class uses `field(default_factory=list)` and `field(default_factory=dict)` - the attributes exist but are empty.

### The Fix

**File**: `data/databases/material_db.py`
**Location**: Lines 191-192 (added)

```python
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
    effect_tags=item_data.get('effectTags', []),        # ← ADDED
    effect_params=item_data.get('effectParams', {})      # ← ADDED
)
```

### Why The Fix Works

Now when turret JSON is loaded:
1. ✅ `load_stackable_items()` extracts `effectTags` and `effectParams` from JSON
2. ✅ MaterialDefinition stores these in `effect_tags` and `effect_params` attributes
3. ✅ `game_engine.py` retrieves non-empty tags during placement
4. ✅ `place_entity()` receives tags and stores them in PlacedEntity
5. ✅ Turret attacks use tag system instead of legacy damage

---

## 🐛 Bug #2: Status Effect Damage Showed "NO TAGS"

### Symptom
```
🎯 TRAINING DUMMY HIT #312
   Damage: 0.3 (fire)
   ⚠️  NO TAGS (legacy damage or tags not passed)
   HP: 8638.3/10000.0 (86.4%)
   Total damage taken: 1361.7
   📋 Active Status Effects:
      - burn (x3, 0.3s, 5.0 dmg/sec)
```

### User Impact
- Initial attacks with tags work correctly ✓
- Status effects are applied correctly ✓
- **Status effect damage ticks show "NO TAGS"** ✗

### Root Cause Analysis

#### The Damage Flow
```
Player/Turret Attack
    ↓
EffectExecutor.execute_effect() [with tags]
    ↓
_apply_status_effects() [creates BurnEffect with params]
    ↓
StatusEffect.update() [called every frame]
    ↓
_apply_periodic_effect() [deals damage]
    ↓
target.take_damage(damage, damage_type)  ← ❌ NO TAGS!
```

#### The Problem

Status effects store all the information they need:
- `status_id`: "burn", "bleed", "poison"
- `source`: The entity that applied the effect
- `params`: Effect parameters from the original attack

But when they deal damage, they only pass damage amount and type:

**Before Fix** - `entities/status_effect.py` lines 109-115:
```python
def _apply_periodic_effect(self, dt: float, target: Any):
    """Apply fire damage"""
    damage = self.damage_per_second * self.stacks * dt
    if hasattr(target, 'take_damage'):
        target.take_damage(damage, 'fire')  # ← Only 2 params!
    elif hasattr(target, 'current_health'):
        target.current_health = max(0, target.current_health - damage)
```

Meanwhile, the TrainingDummy's `take_damage()` signature accepts tags:

**training_dummy.py** lines 69-70:
```python
def take_damage(self, damage: float, damage_type: str = "physical",
                from_player: bool = False, source_tags: list = None,
                attacker_name: str = None, source=None, tags=None, **kwargs):
```

When tags are not provided, the training dummy shows:
```python
if tags:
    print(f"   Using tags: {tags}")
else:
    print(f"   ⚠️  NO TAGS (legacy damage or tags not passed)")
```

#### Why This Matters

The tag system is designed to be **declarative** - every damage source should identify what it is via tags. When status effects don't pass tags:

1. ❌ Combat logs are incomplete/misleading
2. ❌ Future tag-based damage resistance/weaknesses won't work for DoTs
3. ❌ Analytics and debugging become difficult
4. ❌ The training dummy can't properly report status effect damage

### The Fix

**File**: `entities/status_effect.py`
**Locations**: Lines 113, 145, 178 (BurnEffect, BleedEffect, PoisonEffect)

#### BurnEffect (lines 109-115)
```python
def _apply_periodic_effect(self, dt: float, target: Any):
    """Apply fire damage"""
    damage = self.damage_per_second * self.stacks * dt
    if hasattr(target, 'take_damage'):
        target.take_damage(damage, 'fire', tags=['burn', 'fire'], source=self.source)  # ← FIXED
    elif hasattr(target, 'current_health'):
        target.current_health = max(0, target.current_health - damage)
```

#### BleedEffect (lines 141-147)
```python
def _apply_periodic_effect(self, dt: float, target: Any):
    """Apply bleed damage"""
    damage = self.damage_per_second * self.stacks * dt
    if hasattr(target, 'take_damage'):
        target.take_damage(damage, 'physical', tags=['bleed', 'physical'], source=self.source)  # ← FIXED
    elif hasattr(target, 'current_health'):
        target.current_health = max(0, target.current_health - damage)
```

#### PoisonEffect (lines 173-180)
```python
def _apply_periodic_effect(self, dt: float, target: Any):
    """Apply poison damage (scales heavily with stacks)"""
    damage = self.damage_per_second * (self.stacks ** 1.2) * dt
    if hasattr(target, 'take_damage'):
        target.take_damage(damage, 'poison', tags=['poison', 'poison_status'], source=self.source)  # ← FIXED
    elif hasattr(target, 'current_health'):
        target.current_health = max(0, target.current_health - damage)
```

### Why The Fix Works

Now when status effects deal damage:
1. ✅ Tags identify the damage source (e.g., `['burn', 'fire']`)
2. ✅ Source entity is passed for attribution
3. ✅ Training dummy can properly log and categorize the damage
4. ✅ Future damage resistance/weakness systems can process DoT tags
5. ✅ Combat analytics have complete data

---

## 📊 Impact Summary

### Before Fixes
- ❌ All turrets (devices) loaded with empty tags
- ❌ Status effect damage appeared as "legacy damage"
- ❌ Tag system partially non-functional despite code being "complete"

### After Fixes
- ✅ Turrets load with proper tags from JSON
- ✅ Status effects properly identify their damage via tags
- ✅ Complete tag system data flow from JSON → Placement → Combat → Damage Application

---

## 🧪 Testing Requirements

### Test 1: Verify Turret Tags Load Correctly
```python
# 1. Start fresh game or reload material database
# 2. Check lightning_cannon material definition
mat_db = MaterialDatabase.get_instance()
lightning = mat_db.get_material('lightning_cannon')
assert lightning.effect_tags == ['lightning', 'single', 'shock']
assert lightning.effect_params.get('baseDamage') == 70.0

# 3. Place a lightning cannon turret
# 4. Verify placed entity has tags
placed_entity = world_system.placed_entities[-1]
assert placed_entity.tags == ['lightning', 'single', 'shock']
assert placed_entity.effect_params.get('baseDamage') == 70.0
```

### Test 2: Verify Turret Combat Uses Tags
```
Expected Output:
⚡ TAG-BASED TURRET ATTACK
   Turret: lightning_cannon
   Tags: ['lightning', 'single', 'shock']
   Target: Training Dummy

🎯 TRAINING DUMMY HIT #1
   Damage: 70.0 (lightning)
   Using tags: ['lightning', 'single', 'shock']  ← Must show tags
   HP: 9930.0/10000.0 (99.3%)
```

### Test 3: Verify Status Effect Damage Has Tags
```
1. Attack training dummy with burn weapon
2. Wait for burn ticks
3. Verify burn damage shows tags

Expected Output:
🎯 TRAINING DUMMY HIT #5
   Damage: 5.0 (fire)
   Using tags: ['burn', 'fire']  ← Must show tags
   HP: 9800.0/10000.0 (98.0%)
   📋 Active Status Effects:
      - burn (x1, 4.3s, 5.0 dmg/sec)
```

### Test 4: Verify All Three DoT Types
- Burn: tags=['burn', 'fire']
- Bleed: tags=['bleed', 'physical']
- Poison: tags=['poison', 'poison_status']

---

## 🎯 Lessons Learned

### Why These Bugs Were Missed

1. **Incomplete Testing Coverage**
   - Previous tests focused on "does the code exist?" not "does data flow through it?"
   - Testing newly placed entities worked, but not loaded entities
   - Testing initial attacks worked, but not status effect ticks

2. **Multiple Loading Paths**
   - Having TWO material loading methods (load_from_file vs load_stackable_items) created asymmetry
   - Only one path was updated with tag support initially

3. **Implicit Assumptions**
   - Assumed that if MaterialDefinition has tag fields, they'd be populated
   - Didn't verify that ALL loading paths actually populate those fields

### Prevention Strategies

1. **Test Data Flow End-to-End**
   - JSON → Database → Placement → Combat → Damage Application
   - Don't just test that functions accept tags, test that they RECEIVE tags

2. **Check All Code Paths**
   - If there are multiple loading methods, ensure ALL extract required data
   - Use grep to find all MaterialDefinition() instantiations

3. **Explicit Validation**
   - Add assertions or logging to verify tags are non-empty at key points
   - Example: `assert len(effect_tags) > 0, f"Turret {item_id} has no tags!"`

---

## 📝 Related Files

### Modified Files
- `data/databases/material_db.py` - Added tag extraction to load_stackable_items()
- `entities/status_effect.py` - Added tag passing to BurnEffect, BleedEffect, PoisonEffect

### Key Related Files (Reference Only)
- `data/models/materials.py` - MaterialDefinition class with effect_tags/effect_params fields
- `core/game_engine.py` - Extracts tags from MaterialDefinition during placement
- `systems/world_system.py` - place_entity() receives and stores tags
- `systems/turret_system.py` - Uses tags for combat if available
- `systems/training_dummy.py` - Reports tags in combat logs

---

## ✅ Verification Checklist

- [x] Bug #1 Fix: material_db.py extracts effectTags and effectParams
- [x] Bug #2 Fix: BurnEffect passes tags when dealing damage
- [x] Bug #2 Fix: BleedEffect passes tags when dealing damage
- [x] Bug #2 Fix: PoisonEffect passes tags when dealing damage
- [x] Committed with descriptive message
- [x] Pushed to feature branch
- [x] Documentation created

---

## 🚀 Next Steps

1. **User Testing Required**
   - User should delete old save file or restart game
   - Place new turrets and verify they attack with tags
   - Apply status effects and verify DoT ticks show tags

2. **Potential Future Work**
   - Consider consolidating load_from_file() and load_stackable_items() to avoid duplication
   - Add validation to ensure placeable devices always have tags
   - Create automated tests for the complete tag data flow

3. **Monitor For Additional Issues**
   - Watch for other entities that might use different loading paths
   - Verify bombs, traps, and other devices also load tags correctly
   - Check if any other damage sources fail to pass tags

---

**Document Version**: 1.0
**Last Updated**: 2025-12-21
**Author**: Claude (AI Assistant)
**Status**: Complete - Ready for User Testing
