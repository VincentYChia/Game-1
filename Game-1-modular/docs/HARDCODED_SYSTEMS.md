# Hardcoded Systems & Non-Modifiable Mechanics
**Last Updated**: 2026-01-15
**Purpose**: Track systems that are NOT tag-driven or JSON-modifiable

---

## ❌ Fully Hardcoded Systems

### 1. Alchemy Potions (character.py:1662-1965)

**Status**: 100% hardcoded

**Problem**: Every potion requires explicit if/elif statement based on itemId.

**Affected Fields**:
- `effect` - Ignored (documentation only)
- `duration` - Ignored (hardcoded in Python)
- `subtype` - Ignored

**Only Field Used**:
- `itemId` - Triggers hardcoded function

**List of Hardcoded Potions** (17 total):
```
1.  minor_health_potion      → 50 HP
2.  health_potion             → 100 HP
3.  greater_health_potion     → 200 HP
4.  minor_mana_potion         → 50 Mana
5.  mana_potion               → 100 Mana
6.  greater_mana_potion       → 200 Mana
7.  regeneration_tonic        → 5 HP/sec, 60s
8.  strength_elixir           → 20% damage, 300s
9.  iron_skin_potion          → 10 defense, 300s
10. swiftness_draught         → 25% speed, 240s
11. titans_brew               → 40% damage + 30% defense, 300s
12. fire_resistance_potion    → 50% fire resist, 360s
13. frost_resistance_potion   → 50% frost resist, 360s
14. elemental_harmony_potion  → All element resist, 600s
15. efficiency_oil            → 15% gathering speed, 1800s
16. armor_polish              → 10 defense, 1800s
17. weapon_oil                → 10% damage, 7200s
```

**Code Location**: `entities/character.py:1662-1965`

**Impact**: Cannot add new potions via JSON alone. Requires Python code changes.

**Workaround**: Use existing itemId values only.

---

## ⚠️ Enum-Based Systems (Modifiable but Limited)

### 2. Skill Effect Types

**Status**: Limited to 10 types

**Problem**: Skill `effect.type` must match one of 10 hardcoded types.

**Supported Types** (skill_manager.py:261-374):
```
1. empower      → Damage/power buff
2. quicken      → Speed buff
3. fortify      → Flat defense buff
4. regenerate   → HP/mana per second
5. pierce       → Critical hit chance
6. restore      → Instant HP/mana/durability
7. enrich       → Extra drops
8. elevate      → Rarity upgrade chance
9. devastate    → AoE radius buff
10. transcend   → Tier bypass
```

**Code Location**: `entities/components/skill_manager.py:261-374`

**Impact**: Cannot add new buff types without code changes.

**Values ARE Modifiable**: magnitude, duration, category all work.

---

### 3. Skill Magnitude Values

**Status**: Hardcoded enum mapping

**Problem**: `effect.magnitude` strings map to fixed percentages.

**Mapping** (skill_manager.py:261-280):
```
minor    → 0.10 (10%)
moderate → 0.25 (25%)
major    → 0.50 (50%)
extreme  → 1.00 (100%)
```

**Code Location**: `entities/components/skill_manager.py:261-280`

**Impact**: Cannot create custom magnitude values (e.g., "tiny" = 5%).

**Workaround**: Use existing magnitude strings.

---

### 4. Skill Duration Values

**Status**: Hardcoded enum mapping

**Problem**: `effect.duration` strings map to fixed seconds.

**Mapping** (SkillDatabase):
```
instant  → 0s (consume_on_use buff)
brief    → 30s
moderate → 180s (3 minutes)
long     → 600s (10 minutes)
extreme  → 3600s (1 hour)
```

**Code Location**: `data/databases/skill_db.py`

**Impact**: Cannot create custom durations (e.g., "short" = 60s).

**Workaround**: Use existing duration strings.

---

### 5. Skill Mana Costs

**Status**: Hardcoded enum mapping

**Problem**: `cost.mana` strings map to fixed values.

**Mapping** (SkillDatabase):
```
minor    → 20 mana
moderate → 50 mana
major    → 100 mana
extreme  → 200 mana
```

**Code Location**: `data/databases/skill_db.py`

**Impact**: Cannot create custom mana costs (e.g., "tiny" = 10 mana).

**Workaround**: Use existing cost strings.

---

### 6. Skill Cooldowns

**Status**: Hardcoded enum mapping

**Problem**: `cost.cooldown` strings map to fixed seconds.

**Mapping** (SkillDatabase):
```
short    → 120s (2 minutes)
moderate → 300s (5 minutes)
long     → 600s (10 minutes)
extreme  → 1200s (20 minutes)
```

**Code Location**: `data/databases/skill_db.py`

**Impact**: Cannot create custom cooldowns.

**Workaround**: Use existing cooldown strings.

---

## ⚠️ Partially Hardcoded Systems

### 7. Enchantment Triggers

**Status**: Values modifiable, triggers need code

**Problem**: Some enchantment types work out-of-the-box, others need code integration.

**Works Out-of-Box** (combat_manager.py:925-989):
```
✅ damage_multiplier  → Sharpness (passive, equipment.py:116)
✅ defense_multiplier → Protection (passive, equipment.py:128)
✅ damage_over_time   → Fire Aspect (on hit)
✅ knockback          → Push enemies (on hit)
✅ slow               → Frost effect (on hit)
```

**Needs Code Integration**:
```
⚠️ lifesteal → Must check in damage calculation
⚠️ thorns    → Must check when taking damage
⚠️ soulbound → Must check on death
⚠️ chain     → Needs chain damage handler
⚠️ execute   → Needs low HP check
```

**Code Location**: `Combat/combat_manager.py:925-989`

**Impact**: Can add DoT/knockback/slow enchantments freely. Other types need code.

**Values ARE Modifiable**: `value`, `duration`, `damagePerSecond` all work.

---

## 📊 Summary Table

| System | Modifiable? | Behavior Extendable? | Code Location |
|--------|-------------|---------------------|---------------|
| **Alchemy Potions** | ❌ No | ❌ No | character.py:1662 |
| **Skill Effect Types** | ✅ Values yes | ⚠️ 10 types only | skill_manager.py:261 |
| **Skill Magnitudes** | ❌ No | ❌ No | skill_manager.py:261 |
| **Skill Durations** | ❌ No | ❌ No | skill_db.py |
| **Skill Mana Costs** | ❌ No | ❌ No | skill_db.py |
| **Skill Cooldowns** | ❌ No | ❌ No | skill_db.py |
| **Enchantment Triggers** | ✅ Values yes | ⚠️ 5 types work | combat_manager.py:925 |

---

## ✅ What IS Modifiable (For Comparison)

To clarify what's NOT on this list:

**Fully Tag-Driven**:
- ✅ Smithing weapon effectTags/effectParams
- ✅ Engineering device effectTags/effectParams
- ✅ Skill combat_tags/combat_params
- ✅ All tag parameters (baseDamage, chain_count, burn_duration, etc.)
- ✅ Enchantment values (for supported types)

**Values from tag-definitions.JSON**:
- ✅ 75+ tags with default params
- ✅ JSON overrides all tag defaults
- ✅ Synergies (e.g., lightning + chain = +20% range)

---

## 🎯 Implications for Content Generation

### Don't Generate:
- ❌ New alchemy potions (won't work)
- ❌ New skill effect types beyond the 10
- ❌ Custom magnitude/duration/mana/cooldown values

### Can Generate:
- ✅ Smithing weapons with any tag combo
- ✅ Engineering devices with any tag combo
- ✅ Skills using the 10 supported effect types
- ✅ Enchantments using the 5 working types
- ✅ Any effectParams values (all modifiable)

---

## 🔧 Refactoring Recommendations

### High Priority:
1. **Make alchemy tag-driven** - Replace if/elif chain with effect system
2. **Make skill enums JSON-based** - Load magnitude/duration/cost mappings from JSON

### Medium Priority:
3. **Add missing enchantment triggers** - Implement lifesteal, thorns integration
4. **Document skill effect types** - Clear list in JSON or docs

### Low Priority:
5. **Custom magnitude system** - Allow arbitrary percentage values
6. **Custom duration system** - Allow arbitrary second values

---

## 📝 Notes

- **Effects are forgiven**: Effect system itself is well-designed. The issue is the 10 hardcoded effect types, not the system.
- **Enums could be JSON**: All enum mappings (magnitude, duration, mana, cooldown) could load from JSON instead of being hardcoded.
- **Alchemy is the exception**: Everything else uses data-driven or tag-driven design. Alchemy is the only fully hardcoded content system.

---

**Last Updated**: 2026-01-15
**Maintained By**: Game-1 Development Team
