# Tag System Migration Guide

**Date:** 2025-12-15
**Purpose:** Step-by-step guide to migrate existing JSON files to the new tag-to-effects system
**Version:** 1.0

---

## Overview

This guide explains how to convert existing JSON files from the current text-based effect descriptions to the new tag-based system.

### What Changes:
1. **`effect` field** → Removed (replaced by tags + effectParams)
2. **`tags` field** → Enhanced with functional tags
3. **`effectParams` field** → New field containing effect parameters

### What Stays:
- All existing metadata
- Item IDs, names, tiers, rarities
- Non-functional tags (rarity, discipline, etc.)

---

## Migration Checklist

### Phase 1: Preparation
- [ ] Run tag_collector.py to inventory current tags
- [ ] Back up all JSON files
- [ ] Review TAG-DEFINITIONS-PHASE2.md for tag reference
- [ ] Review TAG-COMBINATIONS-EXAMPLES.md for examples

### Phase 2: JSON Conversion
- [ ] Convert engineering items (turrets, bombs, traps)
- [ ] Convert hostile special abilities
- [ ] Convert skills
- [ ] Convert enchantments
- [ ] Convert weapons/armor with special properties

### Phase 3: Code Implementation
- [ ] Implement effect registry
- [ ] Implement tag parser
- [ ] Implement geometry calculators
- [ ] Implement status effect system
- [ ] Update equipment manager
- [ ] Update turret system
- [ ] Update combat system

### Phase 4: Testing
- [ ] Unit tests for each tag
- [ ] Integration tests for combinations
- [ ] Validate all items load correctly
- [ ] Performance testing

---

## Step 1: Analyze Current Effect Descriptions

### Extract Keywords from Effect Text

**Example Current Entry:**
```json
{
  "itemId": "lightning_cannon",
  "effect": "Fires lightning bolts, 70 damage + chain, 10 unit range",
  "tags": ["device", "turret", "lightning", "advanced"]
}
```

**Extract Keywords:**
- "Fires" → projectile attack
- "lightning bolts" → lightning damage type
- "70 damage" → baseDamage parameter
- "+ chain" → chain geometry tag!
- "10 unit range" → attackRange parameter

---

## Step 2: Map Keywords to Tags

### Common Keyword → Tag Mappings

| Keyword in Effect | Tag | Category |
|---|---|---|
| "chain" | `chain` | Geometry |
| "cone" / "sweeps cone" | `cone` | Geometry |
| "radius" / "area" | `circle` | Geometry |
| "beam" / "laser" | `beam` | Geometry |
| "penetrates" / "through" | `pierce` | Geometry Modifier |
| "projectile" / "fires" / "shoots" | `projectile` | Geometry |
| "burn" / "burning" / "lingering burn" | `burn` | Status Effect |
| "slow" / "slows" | `slow` / `chill` | Status Effect |
| "freeze" / "frozen" | `freeze` | Status Effect |
| "bleed" / "bleeding" | `bleed` | Status Effect |
| "immobilize" / "immobilizes" | `root` / `immobilize` | Status Effect |
| "stun" / "stuns" | `stun` | Status Effect |
| "heal" / "heals" | `healing` | Damage Type (positive) |
| "poison" | `poison`, `poison_status` | Damage + Status |
| "fire" / "flame" | `fire` | Damage Type |
| "frost" / "ice" / "cold" | `frost` | Damage Type |
| "lightning" / "electric" | `lightning` | Damage Type |
| "holy" / "light" | `holy` | Damage Type |
| "shadow" / "dark" | `shadow` | Damage Type |
| "physical" | `physical` | Damage Type |
| "splits" / "cluster" | `cluster` (special handling) | Mechanic |

---

## Step 3: Convert Individual Items

### Template for Conversion

**BEFORE:**
```json
{
  "itemId": "item_id_here",
  "effect": "Text description of effect",
  "tags": ["descriptive", "tags", "only"]
}
```

**AFTER:**
```json
{
  "itemId": "item_id_here",
  "tags": ["descriptive", "tags", "functional", "tags", "here"],
  "effectParams": {
    "baseDamage": 0,
    "geometry_params": {},
    "status_params": {}
  }
}
```

---

### Example 1: Lightning Cannon

**BEFORE:**
```json
{
  "metadata": {
    "narrative": "Lightning cannon that channels storm energy.",
    "tags": ["device", "turret", "lightning", "advanced"]
  },
  "itemId": "lightning_cannon",
  "name": "Lightning Cannon",
  "category": "device",
  "type": "turret",
  "subtype": "energy",
  "tier": 3,
  "rarity": "rare",
  "effect": "Fires lightning bolts, 70 damage + chain, 10 unit range"
}
```

**AFTER:**
```json
{
  "metadata": {
    "narrative": "Lightning cannon that channels storm energy. The bolts arc between enemies, chain lightning made manifest.",
    "tags": ["device", "turret", "lightning", "advanced"]
  },
  "itemId": "lightning_cannon",
  "name": "Lightning Cannon",
  "category": "device",
  "type": "turret",
  "subtype": "energy",
  "tier": 3,
  "rarity": "rare",
  "tags": ["device", "turret", "lightning", "projectile", "chain", "enemy"],
  "effectParams": {
    "baseDamage": 70,
    "attackRange": 10.0,
    "attackSpeed": 1.2,
    "chain_count": 2,
    "chain_range": 6.0,
    "chain_falloff": 0.2
  }
}
```

**Changes:**
- ❌ Removed `effect` field
- ✅ Added functional tags: `projectile`, `chain`, `enemy`
- ✅ Moved metadata tags to main `tags` array
- ✅ Added `effectParams` with all numeric values

---

### Example 2: Flamethrower Turret

**BEFORE:**
```json
{
  "metadata": {
    "narrative": "Flamethrower turret that sweeps area with fire.",
    "tags": ["device", "turret", "fire", "area"]
  },
  "itemId": "flamethrower_turret",
  "effect": "Sweeps cone of fire, 60 damage + lingering burn"
}
```

**AFTER:**
```json
{
  "metadata": {
    "narrative": "Flamethrower turret that sweeps area with fire. The roar is almost as terrifying as the flames themselves.",
    "tags": ["device", "turret", "fire", "area"]
  },
  "itemId": "flamethrower_turret",
  "tags": ["device", "turret", "fire", "cone", "burn", "enemy"],
  "effectParams": {
    "baseDamage": 60,
    "attackRange": 8.0,
    "attackSpeed": 0.8,
    "cone_angle": 60,
    "cone_range": 8.0,
    "burn_duration": 6.0,
    "burn_damage_per_tick": 8.0,
    "burn_tick_rate": 1.0
  }
}
```

**Changes:**
- ❌ Removed `effect` field
- ✅ Added `cone` tag (replacing vague "area")
- ✅ Added `burn` tag (from "lingering burn")
- ✅ Added `enemy` context tag
- ✅ Added cone and burn parameters

---

### Example 3: Spike Trap

**BEFORE:**
```json
{
  "metadata": {
    "narrative": "Spike trap with spring-loaded iron spikes.",
    "tags": ["device", "trap", "physical", "basic"]
  },
  "itemId": "spike_trap",
  "effect": "Triggers on contact, 30 damage + bleed"
}
```

**AFTER:**
```json
{
  "metadata": {
    "narrative": "Spike trap with spring-loaded iron spikes. The spikes punch through leather and flesh alike.",
    "tags": ["device", "trap", "physical", "basic"]
  },
  "itemId": "spike_trap",
  "tags": ["device", "trap", "physical", "slashing", "bleed", "single_target", "on_contact", "enemy"],
  "effectParams": {
    "baseDamage": 30,
    "trigger_type": "contact",
    "bleed_duration": 6.0,
    "bleed_damage_per_tick": 5.0,
    "bleed_tick_rate": 1.0
  }
}
```

**Changes:**
- ✅ Added `slashing` damage subtype
- ✅ Added `bleed` status tag
- ✅ Added `single_target` geometry
- ✅ Added `on_contact` trigger
- ✅ Added bleed parameters

---

### Example 4: Healing Beacon

**BEFORE:**
```json
{
  "metadata": {
    "narrative": "Healing beacon that emanates restorative energy.",
    "tags": ["device", "utility", "healing", "support"]
  },
  "itemId": "healing_beacon",
  "effect": "Heals 10 HP/sec in 5 unit radius for 2 minutes"
}
```

**AFTER:**
```json
{
  "metadata": {
    "narrative": "Healing beacon that emanates restorative energy. The light feels warm, comforting, alive.",
    "tags": ["device", "utility", "healing", "support"]
  },
  "itemId": "healing_beacon",
  "tags": ["device", "utility", "healing", "circle", "regeneration", "ally"],
  "effectParams": {
    "baseHealing": 10,
    "radius": 5.0,
    "duration": 120.0,
    "tick_rate": 1.0,
    "affect_player": true,
    "affect_turrets": true
  }
}
```

**Changes:**
- ✅ Added `circle` geometry (radius effect)
- ✅ Added `regeneration` (healing over time)
- ✅ Added `ally` context (heals allies, not enemies)
- ✅ Converted "2 minutes" to 120.0 seconds
- ✅ Added healing parameters

---

### Example 5: Simple Bomb

**BEFORE:**
```json
{
  "metadata": {
    "narrative": "Simple explosive using blast powder.",
    "tags": ["device", "bomb", "basic", "explosive"]
  },
  "itemId": "simple_bomb",
  "effect": "Explodes for 40 damage in 3 unit radius"
}
```

**AFTER:**
```json
{
  "metadata": {
    "narrative": "Simple explosive using blast powder in iron casing. Pull pin, throw, run. In that order.",
    "tags": ["device", "bomb", "basic", "explosive"]
  },
  "itemId": "simple_bomb",
  "tags": ["device", "bomb", "physical", "circle", "explosive", "enemy"],
  "effectParams": {
    "baseDamage": 40,
    "radius": 3.0,
    "origin": "position",
    "splash_falloff": "linear"
  }
}
```

**Changes:**
- ✅ Added `physical` damage type
- ✅ Added `circle` geometry
- ✅ Added `enemy` context
- ✅ Specified origin as "position" (bomb location)

---

## Step 4: Convert Hostile Special Abilities

### Current Format

**BEFORE:**
```json
{
  "enemyId": "wolf_elder",
  "aiPattern": {
    "specialAbilities": ["howl_buff", "leap_attack"]
  }
}
```

### New Format

**Option A: Convert to Tags (Recommended)**
```json
{
  "enemyId": "wolf_elder",
  "tags": ["wolf", "rare", "boss", "end-game"],
  "abilities": [
    {
      "abilityId": "howl_buff",
      "tags": ["sound", "buff", "circle", "empower", "ally"],
      "effectParams": {
        "radius": 10.0,
        "damage_increase": 0.3,
        "duration": 15.0
      }
    },
    {
      "abilityId": "leap_attack",
      "tags": ["physical", "dash", "single_target", "knockback", "enemy"],
      "effectParams": {
        "baseDamage": 60,
        "leap_range": 8.0,
        "knockback_distance": 3.0
      }
    }
  ]
}
```

**Option B: Keep Abilities, Add Tag Definitions Separately**

Create new file: `Definitions.JSON/ability-definitions.JSON`

```json
{
  "abilities": [
    {
      "abilityId": "howl_buff",
      "name": "Pack Howl",
      "tags": ["sound", "buff", "circle", "empower", "ally"],
      "effectParams": {
        "radius": 10.0,
        "damage_increase": 0.3,
        "duration": 15.0
      }
    },
    {
      "abilityId": "leap_attack",
      "name": "Savage Leap",
      "tags": ["physical", "dash", "single_target", "knockback", "enemy"],
      "effectParams": {
        "baseDamage": 60,
        "leap_range": 8.0,
        "knockback_distance": 3.0
      }
    }
  ]
}
```

Then in hostiles file, keep references:
```json
{
  "enemyId": "wolf_elder",
  "aiPattern": {
    "specialAbilities": ["howl_buff", "leap_attack"]
  }
}
```

**Recommendation:** Use Option B for cleaner separation and reusability.

---

## Step 5: Convert Skills

### Example: Whirlwind Strike

**BEFORE:**
```json
{
  "skillId": "whirlwind_strike",
  "name": "Whirlwind Strike",
  "tags": ["aoe", "combat", "damage"],
  "effect": {
    "type": "devastate",
    "category": "combat",
    "magnitude": "major",
    "target": "area",
    "duration": "instant"
  }
}
```

**AFTER:**
```json
{
  "skillId": "whirlwind_strike",
  "name": "Whirlwind Strike",
  "tags": ["physical", "slashing", "circle", "damage", "combat", "instant", "enemy"],
  "effectParams": {
    "baseDamage": 100,
    "damageScaling": "strength",
    "radius": 3.0,
    "origin": "self",
    "cooldown": 8.0,
    "manaCost": 25
  }
}
```

**Changes:**
- ❌ Removed old `effect` object structure
- ✅ Added damage type tags: `physical`, `slashing`
- ✅ Added geometry: `circle`
- ✅ Added trigger: `instant`
- ✅ Added context: `enemy`
- ✅ New `effectParams` with all skill parameters

---

### Example: Chain Harvest (Gathering Skill)

**BEFORE:**
```json
{
  "skillId": "chain_harvest",
  "name": "Chain Harvest",
  "tags": ["aoe", "gathering", "efficiency"],
  "effect": {
    "type": "devastate",
    "category": "gathering",
    "magnitude": "moderate",
    "target": "area",
    "duration": "instant"
  }
}
```

**AFTER:**
```json
{
  "skillId": "chain_harvest",
  "name": "Chain Harvest",
  "tags": ["gathering", "chain", "efficiency", "instant", "resource_node"],
  "effectParams": {
    "bonusYield": 2,
    "chain_count": 2,
    "chain_range": 5.0,
    "cooldown": 30.0,
    "manaCost": 15
  }
}
```

**Changes:**
- ✅ Added `chain` geometry (harvest chains to nearby nodes)
- ✅ Added `resource_node` context (targets nodes, not enemies)
- ✅ Changed from "area" to chain (more specific)
- ✅ Parameters specific to gathering

---

## Step 6: Parameter Guidelines

### Required Parameters (All Items)

```json
"effectParams": {
  "baseDamage": 0,        // Base damage/healing amount
  "attackRange": 5.0,     // Max range of attack
  "attackSpeed": 1.0      // Attacks per second (turrets)
}
```

### Geometry-Specific Parameters

**Chain:**
```json
"chain_count": 2,
"chain_range": 5.0,
"chain_falloff": 0.3
```

**Cone:**
```json
"cone_angle": 60,
"cone_range": 8.0
```

**Circle/AOE:**
```json
"radius": 3.0,
"origin": "target",  // "source", "target", "position"
"max_targets": 0     // 0 = unlimited
```

**Beam:**
```json
"beam_range": 10.0,
"beam_width": 0.5,
"pierce_count": 0    // 0 = stop at first hit
```

**Projectile:**
```json
"projectile_speed": 15.0,
"projectile_gravity": 0.0,
"projectile_homing": 0.0
```

### Status Effect Parameters

**Burn:**
```json
"burn_duration": 8.0,
"burn_damage_per_tick": 10.0,
"burn_tick_rate": 1.0
```

**Freeze:**
```json
"freeze_duration": 3.0,
"damage_to_break": 50.0  // 0 = unbreakable
```

**Slow/Chill:**
```json
"slow_amount": 0.5,       // 0.5 = 50% slower
"slow_duration": 4.0,
"affect_attack_speed": false
```

**Poison:**
```json
"poison_duration": 10.0,
"poison_damage_per_tick": 4.0,
"poison_tick_rate": 2.0
```

**Bleed:**
```json
"bleed_duration": 6.0,
"bleed_damage_per_tick": 5.0,
"bleed_tick_rate": 1.0,
"movement_increases_damage": true
```

### Special Mechanics Parameters

**Lifesteal:**
```json
"lifesteal_percent": 0.15  // 15% of damage as healing
```

**Knockback:**
```json
"knockback_distance": 2.0,
"knockback_duration": 0.5
```

**Shield:**
```json
"shield_amount": 50.0,
"shield_duration": 15.0,
"shield_type": "all"  // "physical", "elemental", "all"
```

---

## Step 7: Tag Consolidation

### Duplicate Tags to Merge

**Before Migration:**
- `luck` (4 uses) + `fortune` (4 uses) → Merge to `fortune`
- `lifesteal` (2 uses) + `vampiric` (2 uses) → Merge to `lifesteal`
- `master` (4 uses) + `mastery` (2 uses) → Keep `master` only

**Update Strategy:**
```bash
# Find and replace in all JSON files
sed -i 's/"luck"/"fortune"/g' items.JSON/*.JSON
sed -i 's/"vampiric"/"lifesteal"/g' items.JSON/*.JSON
sed -i 's/"mastery"/"master"/g' progression/*.JSON
```

### Remove Redundant Tags

Some tags are purely descriptive and don't need migration:
- Material tags: `copper`, `iron`, `steel` (keep for filtering)
- Rarity tags: `common`, `rare`, `epic` (already have rarity field)
- Discipline tags: `smithing`, `alchemy` (already have category field)

**Decision:** Keep them for backward compatibility and filtering, but they won't generate effects.

---

## Step 8: Validation Script

Create validation script to check all JSONs after migration:

**tools/validate_tags.py:**
```python
#!/usr/bin/env python3
"""Validate tag-to-effects migration"""

import json
from pathlib import Path

REQUIRED_TAGS = {
    'turret': ['geometry_tag', 'damage_tag', 'context_tag'],
    'trap': ['trigger_tag', 'damage_tag', 'context_tag'],
    'skill': ['geometry_tag', 'context_tag'],
}

FUNCTIONAL_TAGS = {
    'geometry': ['single_target', 'chain', 'cone', 'circle', 'beam', 'pierce', 'projectile'],
    'damage': ['physical', 'fire', 'frost', 'lightning', 'poison', 'holy', 'shadow'],
    'status': ['burn', 'freeze', 'slow', 'stun', 'bleed', 'poison_status'],
    'context': ['self', 'ally', 'enemy', 'all', 'player', 'turret'],
}

def validate_item(item_data):
    """Validate single item has proper tags"""
    item_id = item_data.get('itemId')
    tags = item_data.get('tags', [])
    effect_params = item_data.get('effectParams', {})

    errors = []

    # Check if has old effect field
    if 'effect' in item_data and isinstance(item_data['effect'], str):
        errors.append(f"Old 'effect' field still present (should be removed)")

    # Check for required functional tags
    has_geometry = any(tag in FUNCTIONAL_TAGS['geometry'] for tag in tags)
    has_damage = any(tag in FUNCTIONAL_TAGS['damage'] for tag in tags)
    has_context = any(tag in FUNCTIONAL_TAGS['context'] for tag in tags)

    item_type = item_data.get('type')
    if item_type in ['turret', 'trap', 'bomb']:
        if not has_geometry:
            errors.append(f"Missing geometry tag (chain/cone/circle/etc)")
        if not has_damage:
            errors.append(f"Missing damage type tag (fire/frost/physical/etc)")

    # Check effectParams present for combat items
    if item_type in ['turret', 'trap', 'bomb'] and not effect_params:
        errors.append(f"Missing effectParams object")

    return errors

def validate_all_jsons(root_dir):
    """Validate all JSON files"""
    json_files = list(Path(root_dir).rglob("*.JSON")) + list(Path(root_dir).rglob("*.json"))

    all_errors = {}

    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Handle different JSON structures
        items = []
        if 'items' in data:
            items = data['items']
        elif 'turrets' in data:
            items = data['turrets']
        elif 'bombs' in data:
            items = data['bombs']
        elif 'traps' in data:
            items = data['traps']
        # ... etc

        for item in items:
            errors = validate_item(item)
            if errors:
                item_id = item.get('itemId', 'unknown')
                all_errors[f"{json_file.name}:{item_id}"] = errors

    # Print results
    if all_errors:
        print("VALIDATION ERRORS:")
        for key, errors in all_errors.items():
            print(f"\n{key}:")
            for error in errors:
                print(f"  - {error}")
    else:
        print("✓ All items validated successfully!")

if __name__ == "__main__":
    validate_all_jsons("/home/user/Game-1/Game-1-modular")
```

---

## Step 9: Testing Strategy

### Unit Tests for Tags

Test each tag individually:
```python
def test_burn_tag():
    """Test burn status effect"""
    effect = parse_tags(['fire', 'burn'], {'burn_duration': 5.0})
    target = create_test_enemy()

    apply_effect(source=None, target=target, effect=effect)

    assert target.has_status('burn')
    assert target.get_status('burn').duration == 5.0
```

### Integration Tests for Combinations

Test tag combinations:
```python
def test_fire_chain_burn():
    """Test fire + chain + burn combination"""
    effect = parse_tags(['fire', 'chain', 'burn'], {
        'baseDamage': 70,
        'chain_count': 2
    })

    enemies = create_test_enemies(3)
    apply_effect(source=None, target=enemies[0], effect=effect)

    # All three should take damage and have burn
    for enemy in enemies:
        assert enemy.damage_taken > 0
        assert enemy.has_status('burn')
```

### Performance Tests

Ensure tag system doesn't degrade performance:
```python
def test_tag_parsing_performance():
    """Ensure tag parsing is fast"""
    import time

    tags = ['fire', 'chain', 'burn', 'projectile', 'enemy']
    params = {'baseDamage': 70, 'chain_count': 2}

    start = time.time()
    for _ in range(10000):
        parse_tags(tags, params)
    elapsed = time.time() - start

    assert elapsed < 0.1  # Should parse 10k items in < 100ms
```

---

## Step 10: Rollout Plan

### Phase 1: Engineering Items (Week 1)
- ✅ Convert all turrets
- ✅ Convert all bombs
- ✅ Convert all traps
- ✅ Test in isolated environment

### Phase 2: Hostile Abilities (Week 2)
- ✅ Create ability-definitions.JSON
- ✅ Convert all special abilities
- ✅ Test hostile combat

### Phase 3: Skills (Week 3)
- ✅ Convert combat skills
- ✅ Convert gathering skills
- ✅ Convert crafting skills
- ✅ Test skill system

### Phase 4: Weapons & Enchantments (Week 4)
- ✅ Convert weapon special properties
- ✅ Convert enchantments to tags
- ✅ Test equipment system

### Phase 5: Full Integration (Week 5)
- ✅ Enable tag system globally
- ✅ Disable old effect parsing
- ✅ Full regression testing
- ✅ Performance profiling

---

## Common Migration Patterns

### Pattern 1: Simple Damage Item
```
"effect": "40 damage" →
"tags": ["physical", "single_target", "enemy"],
"effectParams": {"baseDamage": 40}
```

### Pattern 2: AOE Damage
```
"effect": "60 damage in 3-unit radius" →
"tags": ["physical", "circle", "enemy"],
"effectParams": {"baseDamage": 60, "radius": 3.0}
```

### Pattern 3: Damage + Status
```
"effect": "50 damage + slow" →
"tags": ["physical", "slow", "single_target", "enemy"],
"effectParams": {
  "baseDamage": 50,
  "slow_amount": 0.5,
  "slow_duration": 4.0
}
```

### Pattern 4: Chain Attack
```
"effect": "70 damage + chain" →
"tags": ["physical", "chain", "enemy"],
"effectParams": {
  "baseDamage": 70,
  "chain_count": 2,
  "chain_range": 5.0
}
```

### Pattern 5: Healing
```
"effect": "Heals 10 HP/sec in 5-unit radius" →
"tags": ["healing", "circle", "regeneration", "ally"],
"effectParams": {
  "baseHealing": 10,
  "radius": 5.0,
  "tick_rate": 1.0
}
```

---

## FAQ

**Q: Do I need to remove the old effect field immediately?**
A: No. During migration, you can keep both. The new system will ignore the old field.

**Q: What if I don't know the exact parameters?**
A: Use sensible defaults. Fine-tune during testing.

**Q: Can I have both descriptive and functional tags?**
A: Yes! Keep descriptive tags like "legendary", "mythical" for filtering.

**Q: What about items with no effects?**
A: Skip effectParams. Tags can be purely descriptive.

**Q: How do I test changes without breaking the game?**
A: Implement feature flag to toggle between old and new systems during migration.

---

**END OF MIGRATION GUIDE**

**Next Steps:**
1. Run tag_collector.py to current inventory
2. Start with engineering items (smallest scope)
3. Validate with validate_tags.py
4. Gradually expand to other categories
