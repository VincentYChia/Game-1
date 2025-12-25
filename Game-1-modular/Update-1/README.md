# Update-1: Tag System Test Content

**Purpose**: First batch of test content to validate the complete tag-driven game system

**Contents**:
- 5 test weapons (items-testing-integration.JSON)
- 6 test skills (skills-testing-integration.JSON)
- 3 test enemies (hostiles-testing-integration.JSON)

---

## What This Tests

### Complete Integration Pipeline

1. **JSON → Database Loading**
   - Do items load into ItemDatabase?
   - Do skills load into SkillDatabase?
   - Do enemies load into HostileDatabase?

2. **Tag System**
   - All geometry patterns (chain, cone, circle, beam, pierce, single)
   - All status effects (burn, bleed, poison, shock, freeze, stun, slow, weaken)
   - Special mechanics (knockback, pull, lifesteal)
   - Damage types (physical, fire, ice, lightning, shadow, arcane)

3. **Game Systems**
   - Equipment system (can weapons be equipped?)
   - Skill system (do skills appear in skill menu?)
   - Enemy spawning (do enemies spawn correctly?)
   - Combat execution (do effects apply in-game?)

4. **Visual Integration**
   - Placeholder icons display
   - Status effect indicators
   - Geometry visualization

---

## Installation

### Quick Start

```bash
# From Game-1-modular directory

# 1. Create placeholder icons
python tools/create_placeholder_icons.py --all-test-content

# 2. Update Vheer catalog
python tools/update_catalog.py --update Update-1

# 3. (Optional) Generate final icons with Vheer
# Run Vheer automation against updated catalog

# 4. Launch game and test!
python main.py
```

### Manual Installation

If scripts fail, manually copy JSONs:

```bash
# Items
cp Update-1/items-testing-integration.JSON items.JSON/

# Skills
cp Update-1/skills-testing-integration.JSON Skills/

# Enemies
cp Update-1/hostiles-testing-integration.JSON Definitions.JSON/
```

---

## Test Content Details

### Items (5 Weapons)

1. **Lightning Chain Whip**
   - Tests: Chain geometry + shock status
   - Tags: `chain`, `lightning`, `shock`
   - Expected: Arcs to 3 nearby enemies, applies shock DoT

2. **Inferno Blade**
   - Tests: Cone geometry + burn status
   - Tags: `cone`, `fire`, `burn`
   - Expected: Hits enemies in 90° cone, applies burn DoT

3. **Void Piercer**
   - Tests: Beam + pierce + weaken debuff
   - Tags: `beam`, `pierce`, `shadow`, `weaken`
   - Expected: Pierces through 10 targets, reduces damage dealt

4. **Frostbite Hammer**
   - Tests: Circle AoE + freeze + knockback
   - Tags: `circle`, `ice`, `freeze`, `knockback`
   - Expected: Hits 4-tile radius, freezes + pushes enemies

5. **Blood Reaver**
   - Tests: Single target + bleed + lifesteal
   - Tags: `single_target`, `physical`, `bleed`, `lifesteal`
   - Expected: High damage, DoT, heals wielder

### Skills (6 Active Abilities)

1. **Meteor Strike**
   - Tests: Instant AoE execution + multiple effects
   - Type: `devastate` (extreme, 10 tiles)
   - Expected: Instant 10-tile AoE with fire + burn + knockback

2. **Chain Lightning**
   - Tests: Instant AoE + chain jumps
   - Type: `devastate` (major, 7 tiles + chain)
   - Expected: Hits all in 7 tiles, chains to nearby enemies

3. **Arctic Cone**
   - Tests: Dual status application
   - Type: `devastate` (moderate cone)
   - Expected: Freeze + slow on all targets in cone

4. **Shadow Beam**
   - Tests: Beam geometry + pierce + debuff
   - Type: `devastate` (major beam)
   - Expected: Long-range beam piercing 10 targets

5. **Vampiric Aura**
   - Tests: AoE lifesteal
   - Type: `devastate` (moderate circle)
   - Expected: Damage all nearby, heal from total damage

6. **Gravity Well**
   - Tests: Pull + stun combo
   - Type: `devastate` (moderate circle)
   - Expected: Pulls enemies in, then stuns them

### Enemies (3 Boss-Tier)

1. **Void Archon** (Tier 3 Boss, 800 HP)
   - Ability 1: Void Lance (beam + pierce, distance 8-15)
   - Ability 2: Gravity Crush (circle + pull, distance 4-10)
   - Ability 3: Reality Tear (cone + knockback, close range 0-6)
   - Tests: Distance-based triggers, all geometries

2. **Storm Titan** (Tier 2 Elite, 400 HP)
   - Ability 1: Chain Lightning (chain + shock)
   - Ability 2: Thunder Slam (cone + shock + stun)
   - Ability 3: Static Field (circle + shock + slow, dual status)
   - Tests: Shock status, dual status effects

3. **Inferno Drake** (Tier 2 Boss, 600 HP)
   - Ability 1: Fire Breath (cone + burn, always available)
   - Ability 2: Wing Buffet (circle + knockback, low HP)
   - Ability 3: Meteor Strike (circle + burn + knockback, ONCE)
   - Tests: HP triggers, once-per-fight mechanics

---

## Testing Checklist

### Phase 1: Loading
- [ ] Game starts without errors
- [ ] All 5 weapons appear in item database
- [ ] All 6 skills appear in skill database
- [ ] All 3 enemies appear in hostile database
- [ ] Placeholder icons display correctly

### Phase 2: Equipment
- [ ] Can equip Lightning Chain Whip
- [ ] Can equip Inferno Blade
- [ ] Can equip Void Piercer
- [ ] Can equip Frostbite Hammer
- [ ] Can equip Blood Reaver
- [ ] Items show in inventory with icons

### Phase 3: Skills
- [ ] Meteor Strike appears in skill menu
- [ ] Chain Lightning appears in skill menu
- [ ] Arctic Cone appears in skill menu
- [ ] Shadow Beam appears in skill menu
- [ ] Vampiric Aura appears in skill menu
- [ ] Gravity Well appears in skill menu
- [ ] Can activate skills from hotbar (1-6)

### Phase 4: Combat - Weapons
- [ ] Lightning Chain Whip chains to nearby enemies
- [ ] Shock status applies and ticks
- [ ] Inferno Blade hits cone area
- [ ] Burn status applies and ticks
- [ ] Void Piercer pierces multiple enemies
- [ ] Weaken debuff reduces enemy damage
- [ ] Frostbite Hammer hits circle area
- [ ] Freeze immobilizes enemies
- [ ] Knockback pushes enemies away
- [ ] Blood Reaver applies bleed
- [ ] Lifesteal heals player

### Phase 5: Combat - Skills
- [ ] Meteor Strike executes instantly (not on next click)
- [ ] Hits 10-tile radius
- [ ] Applies burn + knockback
- [ ] Chain Lightning chains correctly
- [ ] Arctic Cone applies both freeze and slow
- [ ] Shadow Beam pierces 10 targets
- [ ] Vampiric Aura heals from all damage
- [ ] Gravity Well pulls then stuns

### Phase 6: Enemy Abilities
- [ ] Void Archon spawns
- [ ] Void Lance fires at 8-15 tile range
- [ ] Gravity Crush only triggers at 4-10 tiles
- [ ] Reality Tear only triggers at 0-6 tiles
- [ ] Storm Titan spawns
- [ ] Chain Lightning chains to player
- [ ] Thunder Slam stuns player
- [ ] Static Field applies shock + slow
- [ ] Inferno Drake spawns
- [ ] Fire Breath hits player
- [ ] Wing Buffet knocks player back
- [ ] Meteor Strike only happens once per fight

### Phase 7: Visual Feedback
- [ ] Status effect indicators appear
- [ ] Knockback animates smoothly
- [ ] Pull animates smoothly
- [ ] Geometry patterns visualize correctly
- [ ] Damage numbers show damage types

---

## Known Issues

### Not Implemented
- Reflect/Thorns mechanics
- Summon mechanics
- Teleport/Dash mechanics
- Execute mechanics
- Critical as tag

### Expected Behavior
- Placeholder icons are simple colored squares (will be replaced by Vheer)
- Some visual effects may be minimal
- Performance with many effects is untested

---

## Troubleshooting

### "Items not appearing in game"
- Check console for JSON parsing errors
- Verify JSONs are in correct directories
- Check ItemDatabase.py for loading logic

### "Skills not in skill menu"
- Verify character level unlocks skills
- Check SkillDatabase.py for loading
- Ensure skill tier requirements met

### "Enemy abilities not working"
- Check console for tag parsing errors
- Verify `combat_manager` is passing to enemies
- Check distance triggers in enemy definitions

### "Status effects not applying"
- Verify character/enemy has `status_manager`
- Check console for immunity messages
- Verify tag-definitions.JSON has effect defined

### "Geometry not working"
- Check `available_entities` is being passed
- Verify context tags (enemy/ally/player)
- Check parameter names (circle_radius vs radius)

---

## Next Steps After Testing

### If Successful
1. Create Update-2 with more complex content
2. Implement missing mechanics (reflect, summon, etc.)
3. Balance pass on damage/durations
4. Visual polish (animations, effects)

### If Issues Found
1. Document all bugs
2. Create test cases for each bug
3. Fix and retest
4. Update documentation

---

## File Structure

```
Update-1/
├── README.md                              # This file
├── items-testing-integration.JSON         # 5 test weapons
├── skills-testing-integration.JSON        # 6 test skills
└── hostiles-testing-integration.JSON      # 3 test enemies
```

---

## Automation Scripts

### create_placeholder_icons.py
```bash
python tools/create_placeholder_icons.py --all-test-content
```
Creates simple colored placeholder PNGs for all test content.

### update_catalog.py
```bash
python tools/update_catalog.py --update Update-1
```
Adds all Update-1 content to Vheer catalog for icon generation.

---

**Ready to test!** Follow the installation steps and use the checklist above.
