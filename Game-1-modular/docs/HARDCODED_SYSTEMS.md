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

## ⚠️ Enum-Based Systems (Acceptable with Limitations)

### 2. Skill Effect Types

**Status**: 10 predefined types, but SCOPED by category field

**Note**: This is NOT a problem because:
- Effect types are scoped by the `effect.category` field (skill_manager.py:279, buffs.py:92)
- "empower" with category="mining" is separate from "empower" with category="combat"
- The category field makes effect types flexible and reusable

**Supported Types** (skill_manager.py:261-374):
```
1. empower      → Damage/power buff (scoped by category)
2. quicken      → Speed buff (scoped by category)
3. fortify      → Flat defense buff
4. regenerate   → HP/mana per second (scoped by category)
5. pierce       → Critical hit chance (scoped by category)
6. restore      → Instant HP/mana/durability (scoped by category)
7. enrich       → Extra drops (scoped by category)
8. elevate      → Rarity upgrade chance (scoped by category)
9. devastate    → AoE radius buff
10. transcend   → Tier bypass
```

**Code Location**: `entities/components/skill_manager.py:261-374`

**Verdict**: ✅ Working as designed - category scoping provides flexibility

---

### 3. Skill Magnitude Values

**Status**: Text enum mapping (ACCEPTABLE)

**Design**: `effect.magnitude` strings map to percentages.

**Mapping** (skill_manager.py:262-265):
```
minor    → 0.10 (10%)
moderate → 0.25 (25%)
major    → 0.50 (50%)
extreme  → 1.00 (100%)
```

**Code Location**: `entities/components/skill_manager.py:262-265`

**Verdict**: ✅ Working as designed - these are the intended magnitude options

---

### 4. Skill Duration Values

**Status**: Text enum mapping (ACCEPTABLE)

**Design**: `effect.duration` strings map to fixed seconds.

**Mapping** (skill_db.py:114-116):
```
instant  → 0s (consume_on_use buff)
brief    → 30s
moderate → 180s (3 minutes)
long     → 600s (10 minutes)
extreme  → 3600s (1 hour)
```

**Code Location**: `data/databases/skill_db.py:114-116`

**Verdict**: ✅ Working as designed - these are the intended duration options

---

### 5. Skill Mana Costs

**Status**: Limited to 4 text enums, NO range support

**Problem**: `cost.mana` strings map to fixed values, cannot specify arbitrary values.

**Mapping** (skill_db.py:106-108):
```
minor    → 20 mana
moderate → 50 mana
major    → 100 mana
extreme  → 200 mana
```

**What's Missing**: Cannot specify custom values like 75 mana or 150 mana.

**Code Location**: `data/databases/skill_db.py:106-108`

**Impact**: ⚠️ Limited flexibility - need to use one of 4 predefined costs

**Recommended Fix**: Support numeric values directly OR expand enum mapping

---

### 6. Skill Cooldowns

**Status**: Limited to 4 text enums, NO range support

**Problem**: `cost.cooldown` strings map to fixed seconds, cannot specify arbitrary values.

**Mapping** (skill_db.py:110-112):
```
short    → 120s (2 minutes)
moderate → 300s (5 minutes)
long     → 600s (10 minutes)
extreme  → 1200s (20 minutes)
```

**What's Missing**: Cannot specify custom values like 180s (3 minutes) or 420s (7 minutes).

**Code Location**: `data/databases/skill_db.py:110-112`

**Impact**: ⚠️ Limited flexibility - need to use one of 4 predefined cooldowns

**Recommended Fix**: Support numeric values directly OR expand enum mapping

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

| System | Modifiable? | Behavior Extendable? | Verdict | Code Location |
|--------|-------------|---------------------|---------|---------------|
| **Alchemy Potions** | ❌ No | ❌ No | ❌ **Issue** | character.py:1662 |
| **Skill Effect Types** | ✅ Values yes | ✅ Category scopes | ✅ **Good** | skill_manager.py:261 |
| **Skill Magnitudes** | ✅ Text enums | ✅ 4 options | ✅ **Good** | skill_manager.py:262 |
| **Skill Durations** | ✅ Text enums | ✅ 5 options | ✅ **Good** | skill_db.py:114 |
| **Skill Mana Costs** | ⚠️ 4 options only | ❌ No range support | ⚠️ **Limited** | skill_db.py:106 |
| **Skill Cooldowns** | ⚠️ 4 options only | ❌ No range support | ⚠️ **Limited** | skill_db.py:110 |
| **Enchantment Triggers** | ✅ Values yes | ⚠️ 5 types work | ✅ **Good** | combat_manager.py:925 |

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
- ⚠️ Skills with mana costs outside [20, 50, 100, 200]
- ⚠️ Skills with cooldowns outside [120s, 300s, 600s, 1200s]

### Can Generate:
- ✅ Smithing weapons with any tag combo
- ✅ Engineering devices with any tag combo
- ✅ Skills using the 10 effect types with any category
- ✅ Skills with any magnitude (minor/moderate/major/extreme)
- ✅ Skills with any duration (instant/brief/moderate/long/extreme)
- ✅ Enchantments using the 5 working types
- ✅ Any effectParams values (all modifiable)

---

## 🔧 Refactoring Recommendations

### High Priority:
1. **Make alchemy tag-driven** - Replace if/elif chain with effect system (character.py:1662-1965)
   - **Effort**: 4-6 hours
   - **Impact**: Enables JSON-only potion creation

### Medium Priority:
2. **Add mana cost range support** - Accept numeric values or expand enum options (skill_db.py:106-108)
   - **Effort**: 1-2 hours
   - **Impact**: Allow custom mana costs (e.g., 75 mana, 150 mana)

3. **Add cooldown range support** - Accept numeric values or expand enum options (skill_db.py:110-112)
   - **Effort**: 1-2 hours
   - **Impact**: Allow custom cooldowns (e.g., 180s, 420s)

### Low Priority:
4. **Add missing enchantment triggers** - Implement lifesteal, thorns, soulbound integration
   - **Effort**: 2-3 hours
   - **Impact**: More enchantment variety

---

## 📝 Notes

- **Effect types are scoped by category**: The 10 effect types (empower, quicken, etc.) are NOT limiting because they're scoped by the `effect.category` field. "empower" for "mining" is completely separate from "empower" for "combat", making the system flexible and reusable.
- **Text enum mappings are acceptable**: magnitude/duration text enums (minor/moderate/major) are working as designed - they provide discrete, balanced options rather than arbitrary values.
- **Mana/cooldown need range support**: Unlike magnitude/duration, mana costs and cooldowns would benefit from numeric value support or expanded enum options (e.g., cannot specify 180s cooldown, must use 120s or 300s).
- **Alchemy is the exception**: Everything else uses data-driven or tag-driven design. Alchemy is the only fully hardcoded content system.

---

**Last Updated**: 2026-01-15
**Maintained By**: Game-1 Development Team
