# Stat Modifier System Design
**Based on Game Mechanics v5**

## Current System Issues

### What We Have Now:
- **Refining**: Outputs material with rarity (Fine, Exceptional) ✓ CORRECT
- **Other Disciplines**: Calculate rarity bonus from input material rarities, multiply output stats by rarity level
  - Problem: Game Mechanics v5 says minigames give "+stats/attributes", NOT rarity multipliers

### What Game Mechanics v5 Actually Says:

**Smithing (Line 3541):**
- Formula: "workbench tier + recipe size + material tier + **rarity**"
- Gives "+stats/attributes bonuses"
- **NOT** rarity upgrades to output

**Refining (Line 3651):**
- Success: "Full designed output + **rarity upgrade** (if applicable) + attributes"
- ✓ ONLY discipline that gives rarity upgrades

**Alchemy (Lines 3743-3747):**
- "**Handcrafting Bonus (Unique to Alchemy): Unlike other crafting (which gives +stats/attributes), Alchemy handcrafting can boost TIER**"
- Perfect execution: T2 becomes effectively T2.5 (stronger numbers, longer duration)
- **NOT** rarity upgrades

**Engineering (Lines 4148-4149):**
- "**Device stats purely from material quality and slot configuration, NOT puzzle performance**"
- "**Puzzles are gateway/skill-check, not optimization minigame**"
- Solving puzzle just unlocks the device - performance doesn't affect stats

**Enchanting (Lines 4272-4273):**
- "Pattern quality (precision) determines bonus strength percentage"
- Pattern-based, not rarity-based

---

## Proposed New System: Stat Modifiers

### Core Concept:
Materials have **specific stat modifiers** instead of generic rarity bonuses.

### Example Material with Modifiers:
```json
{
  "materialId": "steel_ingot",
  "rarity": "uncommon",
  "modifiers": {
    "durability": 0.10,      // +10% durability
    "damage": 0.05,          // +5% damage
    "sharpness": 0.08        // +8% sharpness
  }
}
```

### How It Works:

**During Crafting:**
1. Collect all modifiers from input materials
2. Sum modifiers by type: `total_durability_bonus = sum(all durability modifiers from inputs)`
3. Apply to output item **only if output has that stat field**
4. Example:
   ```python
   # Inputs: 3x steel_ingot (each +10% durability, +5% damage)
   # Total modifiers: durability +30%, damage +15%

   # Output: iron_sword
   # Base stats: {durability: 100, damage: 25}
   # Final stats: {durability: 130, damage: 28.75}  # Applied bonuses
   ```

**If Output Doesn't Have The Stat:**
- Modifier is ignored (not wasted, just not applicable)
- Example: Crafting a torch with steel_ingot (+damage) → damage modifier ignored (torch has no damage stat)

---

## Implementation Per Discipline

### Smithing
**Current:** Rarity multiplier on all stats
**New:** Sum material modifiers, apply to weapon/armor/tool stats

```python
# Input materials: steel_ingot (+10% durability), dire_fang (+15% damage)
# Output: steel_longsword
# Base: {durability: 120, damage: 40, attack_speed: 1.0}
# Final: {durability: 132 (+10%), damage: 46 (+15%), attack_speed: 1.0}
```

**Minigame Bonus:** Additional modifier based on performance
- Perfect hammer: +5% to all applicable stats
- Good: +3%
- Okay: +1%

### Refining
**Current:** Outputs rarity (Fine, Exceptional) ✓ KEEP THIS
**New:** Add stat modifiers to output material based on minigame performance

```python
# Input: common copper_ore (no modifiers)
# Minigame: 95% quality (Exceptional)
# Output: copper_ingot
#   - rarity: "Exceptional"
#   - modifiers: {durability: 0.05, conductivity: 0.08}  # NEW!
```

**Minigame Performance → Modifier Strength:**
- Standard (50-69%): No modifiers
- Fine (70-89%): +3% to 2 relevant stats
- Exceptional (90%+): +5% to 3 relevant stats

### Alchemy
**Current:** Stats based on effect multipliers
**New:** Boost TIER effectiveness instead (as per v5)

```python
# Base recipe: T2 healing potion (heals 50 HP over 30s)
# Perfect minigame (100% quality)
# Output: T2.5 healing potion (heals 65 HP over 37s)  # 30% boost to tier effectiveness
```

**Minigame Performance → Tier Boost:**
- Weak (0-40%): 0.8x tier (T2 becomes T1.6)
- Standard (41-70%): 1.0x tier (T2 stays T2)
- Strong (71-90%): 1.2x tier (T2 becomes T2.4)
- Perfect (91%+): 1.5x tier (T2 becomes T3 equivalent!)

### Engineering
**Current:** Puzzle performance affects stats
**New:** Stats from materials ONLY, puzzle is gate-check

```python
# Materials determine stats:
# FRAME: iron_casing (+20 durability)
# POWER: fire_crystal (+15 damage)
# FUNCTION: explosive_powder (device type)
# MODIFIER: shrapnel (+10 AoE)

# Output: fire_bomb
# Stats: {durability: 20, damage: 15, aoe: 10}
# Puzzle: Just needs to be solved - performance doesn't matter
```

**No minigame bonus** - puzzle is skill gate, not optimization game

### Enchanting
**Current:** Not fully implemented
**New:** Pattern quality determines modifier strength

```python
# Pattern: Triangle (offensive boost)
# Quality: 85% precision
# Materials: ruby (+damage), gold (+conductivity)

# Result: Weapon gains modifiers:
#   - damage: +0.085 * ruby_power = +8.5%
#   - fire_damage: +0.085 * ruby_element = +4%
```

---

## Material Modifier Categories

### Common Modifier Types:
- **Physical:** durability, damage, defense, weight, sharpness
- **Elemental:** fire_damage, ice_damage, lightning_damage, fire_resistance, etc.
- **Utility:** speed, range, aoe, accuracy, critical_chance
- **Special:** mana_efficiency, cooldown_reduction, lifesteal, thorns

### Material Modifier Examples:

```json
{
  "copper_ingot": {
    "modifiers": {
      "conductivity": 0.05,
      "durability": 0.02
    }
  },
  "steel_ingot": {
    "modifiers": {
      "durability": 0.10,
      "damage": 0.05,
      "sharpness": 0.08
    }
  },
  "fire_crystal": {
    "modifiers": {
      "fire_damage": 0.15,
      "fire_resistance": 0.10
    }
  },
  "dire_fang": {
    "modifiers": {
      "damage": 0.15,
      "critical_chance": 0.05,
      "sharpness": 0.12
    }
  },
  "mithril_ingot": {
    "modifiers": {
      "durability": 0.20,
      "damage": 0.15,
      "magic_affinity": 0.10,
      "weight": -0.30  // Reduces weight!
    }
  }
}
```

---

## Advantages of This System

1. **More Intuitive:** "+10% durability" is clearer than "1.20x multiplier from rarity"
2. **Flexible:** Can have materials that boost damage but not durability, or vice versa
3. **Fail-Safe:** Modifiers only apply if output has that stat (no wasted bonuses)
4. **Aligns with v5:** "gives +stats/attributes" directly instead of through rarity
5. **Allows Specialization:** Fire materials give fire bonuses, sharp materials give sharpness, etc.
6. **Still Uses Rarity:** Refining can still output Fine/Exceptional materials with better modifiers

---

## Implementation Steps

1. **Add modifier system to materials JSON**
   - Add "modifiers" field to each material
   - Define appropriate modifiers for each material type

2. **Update refining**
   - Keep rarity output
   - ADD modifiers to output based on minigame quality

3. **Update smithing**
   - Sum input material modifiers
   - Apply to output weapon/armor/tool stats
   - Add minigame bonus modifiers

4. **Update alchemy**
   - Change from stats to tier effectiveness multiplier
   - Perfect execution boosts tier (T2 → T2.5 or T3)

5. **Update engineering**
   - Stats from materials only
   - Remove puzzle performance bonus
   - Puzzle is just gate-check

6. **Display system**
   - Show material modifiers in tooltips
   - Show applied modifiers on crafted items
   - "Crafted with +25% durability, +15% damage from materials"

---

## Questions for User

1. Should ALL materials have modifiers, or only higher rarity ones?
2. Should modifier strength scale with material rarity automatically?
   - e.g., common steel_ingot: +5% durability, epic steel_ingot: +15% durability
3. Should we keep the rarity system for materials from refining?
   - Proposal: YES - refining outputs materials with rarity + modifiers
4. Should negative modifiers be allowed? (e.g., heavy materials reduce speed)
5. How should we handle existing crafted items when switching systems?

---

## Summary

**Problem:** Current system uses generic rarity multipliers, but v5 says minigames give "+stats/attributes"

**Solution:** Materials have specific stat modifiers (+X% durability, +X% damage, etc.) that apply only if output item has those stats

**Key Change:** From "all stats get 1.20x multiplier" → "durability gets +20%, damage gets +15%, speed unaffected"

**Benefits:** More intuitive, flexible, aligns with v5, allows material specialization

**Implementation:** Add modifiers to materials JSON, update each discipline's crafting logic
