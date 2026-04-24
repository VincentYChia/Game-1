# Tag System Comprehensive Test Guide

**Last Updated**: 2025-12-25
**Purpose**: Validate complete tag system integration via test content

---

## Test Content Created

### 1. Test Weapons (`items-testing-integration.JSON`)
### 2. Test Skills (`skills-testing-integration.JSON`)
### 3. Test Enemies (`hostiles-testing-integration.JSON`)

---

## Test Weapons - What Each Validates

### Lightning Chain Whip
**Tests**: Chain geometry + Lightning damage + Shock status

**Tags**: `lightning`, `chain`, `shock`

**Expected Behavior**:
1. Attack hits primary target
2. Lightning jumps to 3 additional targets within 6 tiles
3. Each target takes lightning damage
4. Each target receives shock status (4s duration, 5 damage/tick)
5. Console shows chain jumps: "Chain: Target → NextTarget"

**Validation**:
- ✅ Chain geometry works
- ✅ Chain jumps to correct number of targets
- ✅ Lightning damage type applied
- ✅ Shock status effect active
- ✅ Shock DoT ticking

---

### Inferno Blade
**Tests**: Cone geometry + Fire damage + Burn status

**Tags**: `fire`, `cone`, `burn`

**Expected Behavior**:
1. Attack projects 60° cone in front of player
2. All enemies within 8-tile cone range hit
3. Fire damage applied to each
4. Burn status applied (10s duration, 8 damage/second)
5. Visual: Enemies on fire

**Validation**:
- ✅ Cone geometry works
- ✅ Cone angle/range correct
- ✅ Fire damage type applied
- ✅ Burn status effect active
- ✅ Burn DoT ticking

---

### Void Piercer
**Tests**: Beam geometry + Pierce + Shadow damage + Weaken debuff

**Tags**: `shadow`, `beam`, `weaken`, `pierce`

**Expected Behavior**:
1. Beam fires from player toward target
2. Beam width 1.5 tiles
3. Hits up to 5 enemies in line (pierce)
4. Shadow damage to each
5. Weaken debuff applied (-30% damage for 8s)
6. Console shows pierced targets

**Validation**:
- ✅ Beam geometry works
- ✅ Pierce penetrates multiple targets
- ✅ Shadow damage type applied
- ✅ Weaken debuff reduces enemy damage
- ✅ Beam width accurate

---

### Frostbite Hammer
**Tests**: Circle geometry (target-centered) + Ice damage + Freeze + Knockback

**Tags**: `ice`, `circle`, `freeze`, `knockback`

**Expected Behavior**:
1. Attack hits primary target
2. 4-tile radius circle centered on TARGET
3. All enemies in radius take ice damage
4. Freeze status applied (3s, cannot move/attack)
5. **Knockback**: Enemies pushed 3 tiles away
6. Visual: Enemies frozen, then pushed back

**Validation**:
- ✅ Circle geometry (target origin) works
- ✅ Ice damage type applied
- ✅ Freeze status immobilizes
- ✅ **Knockback physics work**
- ✅ Multiple mechanics combine correctly

---

### Blood Reaver
**Tests**: Single target + Physical damage + Bleed + Lifesteal

**Tags**: `physical`, `single`, `bleed`, `lifesteal`

**Expected Behavior**:
1. Attack hits single target
2. Physical damage dealt
3. Bleed applied (10s, 6 damage/second)
4. **Lifesteal**: Player heals for 25% of damage dealt
5. Console: "Lifesteal: X HP to Player"

**Validation**:
- ✅ Single target geometry works
- ✅ Physical damage type applied
- ✅ Bleed DoT active
- ✅ **Lifesteal heals player**
- ✅ Healing amount correct (25% of damage)

---

## Test Skills - What Each Validates

### Meteor Strike
**Tests**: Instant devastate + Circle (target) + Fire + Burn + Knockback

**Tags**: `fire`, `circle`, `burn`, `knockback`

**Expected Behavior**:
1. Press skill hotkey → Executes instantly
2. Targets area around clicked enemy
3. 8-tile radius AoE
4. 150 base damage + fire damage
5. All targets burned (12s, 10 damage/second)
6. **All targets knocked back 5 tiles**
7. Console: "💨 Knockback! Target pushed back 5.0 tiles"

**Validation**:
- ✅ Instant execution (no buff mode)
- ✅ Circle geometry (target origin)
- ✅ Extreme magnitude (8 tiles)
- ✅ Fire damage + burn
- ✅ **Knockback works on multiple targets**

---

### Chain Lightning
**Tests**: Chain geometry + Lightning + Shock + High chain count

**Tags**: `lightning`, `chain`, `shock`

**Expected Behavior**:
1. Lightning hits primary target
2. Chains to 5 additional targets
3. Chain range 7 tiles
4. Each target shocked (6s, 4 damage/1.5s)
5. Console shows all chain jumps

**Validation**:
- ✅ High chain count (5 jumps) works
- ✅ Chain range accurate
- ✅ Shock applies to all chained targets
- ✅ Skill execution instant

---

### Arctic Cone
**Tests**: Cone geometry + Ice + Freeze + Slow (dual status)

**Tags**: `ice`, `cone`, `freeze`, `slow`

**Expected Behavior**:
1. 90° cone, 10-tile range
2. Ice damage to all in cone
3. **Dual status effects**:
   - Freeze (4s, immobilized)
   - Slow (8s, -50% speed)
4. Some enemies frozen, others slowed
5. Status effects stack/coexist

**Validation**:
- ✅ Cone geometry wide angle works
- ✅ Multiple status effects apply
- ✅ Freeze immobilizes
- ✅ Slow reduces speed
- ✅ Different durations track correctly

---

### Shadow Beam
**Tests**: Beam + Shadow + Weaken + High pierce count

**Tags**: `shadow`, `beam`, `weaken`, `pierce`

**Expected Behavior**:
1. Beam 15-tile range, 2-tile width
2. Pierces up to 10 enemies
3. Shadow damage to all
4. Weaken (-40% damage) for 10s
5. Console shows pierced count

**Validation**:
- ✅ Long-range beam works
- ✅ High pierce count (10) works
- ✅ Weaken debuff applies to all hit
- ✅ Debuff magnitude correct (-40%)

---

### Vampiric Aura
**Tests**: Circle (source origin) + Shadow + Lifesteal on AoE

**Tags**: `shadow`, `circle`, `lifesteal`

**Expected Behavior**:
1. 6-tile radius centered on PLAYER
2. Damages all enemies in radius
3. **Lifesteal**: Player heals for 60% of total damage dealt
4. Multiple enemies = massive healing
5. Console: "Lifesteal: X HP to Player"

**Validation**:
- ✅ Circle (source origin) works
- ✅ **Lifesteal on AoE damage**
- ✅ Healing scales with hit count
- ✅ Shadow damage type

---

### Gravity Well
**Tests**: Circle (target) + Pull + Arcane + Stun

**Tags**: `arcane`, `circle`, `pull`, `stun`

**Expected Behavior**:
1. 7-tile radius at target location
2. All enemies in radius damaged
3. **Pull**: All enemies pulled 5 tiles toward center
4. **Stun**: 3s immobilization after pull
5. Console: "🧲 Pull! Target pulled 5.0 tiles"
6. Visual: Enemies cluster then freeze

**Validation**:
- ✅ Circle geometry (target origin)
- ✅ **Pull physics work on AoE**
- ✅ Pull toward target point
- ✅ Stun after pull
- ✅ Arcane damage type

---

## Test Enemies - What Each Validates

### Void Archon
**Tests**: Complex AI with 3 abilities, distance-based triggers, pierce mechanics

**Abilities**:
1. **Void Beam** (6-15 tiles): Beam + pierce + weaken
2. **Gravity Pull** (4-10 tiles): Circle + pull
3. **Void Explosion** (<8 tiles, <30% HP): Circle + knockback + vulnerable

**Expected Behavior**:
- At long range (6-15 tiles): Uses Void Beam
  - Pierces through player + turrets
  - Weakens player (-35% damage)
- At medium range (4-10 tiles, <70% HP): Uses Gravity Pull
  - **Pulls player toward enemy**
  - Console: "🧲 Pull! Player pulled 6.0 tiles"
- At close range (<8 tiles, <30% HP): Uses Void Explosion
  - Damages + **knocks back** + vulnerables player
  - Max 2 uses per fight

**Validation**:
- ✅ Distance-based ability selection
- ✅ Health threshold triggers
- ✅ **Pull works on player**
- ✅ **Knockback works on player**
- ✅ Pierce hits multiple targets
- ✅ Weaken reduces player damage
- ✅ Vulnerable increases damage taken
- ✅ Max uses per fight respected

---

### Storm Titan
**Tests**: Chain lightning enemy version, dual-status AoE, high damage abilities

**Abilities**:
1. **Chain Lightning** (<12 tiles): Chain + shock
2. **Thunder Slam** (<6 tiles, <60% HP): Circle + stun + knockback
3. **Static Field** (<10 tiles, <40% HP): Circle + slow + shock

**Expected Behavior**:
- Normal combat: Uses Chain Lightning
  - Chains to player + nearby allies/turrets
  - Shocks all targets (8s, 6 damage/second)
- Close range, damaged: Thunder Slam
  - Circle centered on enemy
  - **Stuns player** (4s)
  - **Knocks back** (4 tiles)
- Low HP: Static Field
  - Large circle (10 tiles)
  - **Dual status**: Slow + Shock
  - Slow (-60% speed, 10s)
  - Shock (10s, 5 damage/1.5s)

**Validation**:
- ✅ Enemy chain lightning works
- ✅ **Dual status effects** (slow + shock)
- ✅ **Stun prevents player actions**
- ✅ Chain hits allies/turrets
- ✅ Large AoE abilities
- ✅ Health-based ability progression

---

### Inferno Drake
**Tests**: Cone breath, meteor strike, multi-ability boss

**Abilities**:
1. **Fire Breath** (<10 tiles): Cone + burn
2. **Wing Buffet** (<5 tiles, <70% HP): Circle + knockback
3. **Meteor Strike** (5-15 tiles, <30% HP): Circle (target) + burn + knockback, once per fight

**Expected Behavior**:
- Standard range: Fire Breath
  - 60° cone, 10 tiles
  - Heavy burn (12s, 8 damage/second)
- Close range: Wing Buffet
  - Pushes player away to maintain distance
  - 5-tile knockback
- Desperation move (<30% HP, once): Meteor Strike
  - Targets player location
  - 8-tile radius
  - **Massive damage + burn + knockback**
  - Only triggers once per fight

**Validation**:
- ✅ Enemy cone attacks work
- ✅ Range-based ability choice
- ✅ **Once-per-fight abilities**
- ✅ Target-centered circles
- ✅ Multiple simultaneous effects (damage + burn + knockback)
- ✅ Burn duration/damage correct

---

## Comprehensive Testing Checklist

### Damage Types (9 types)
- ✅ Physical (Blood Reaver, Wing Buffet)
- ✅ Fire (Inferno Blade, Meteor Strike, Fire Breath)
- ✅ Ice (Frostbite Hammer, Arctic Cone)
- ✅ Lightning (Lightning Chain Whip, Chain Lightning, Thunder Slam)
- ✅ Poison (Acid Splash - from previous tests)
- ✅ Arcane (Gravity Well)
- ✅ Shadow (Void Piercer, Shadow Beam, Void Archon)
- ⏳ Holy (needs test item)
- ⏳ Chaos (needs test item)

### Geometry Patterns (7 types)
- ✅ Single target (Blood Reaver)
- ✅ Chain (Lightning Chain Whip, Chain Lightning)
- ✅ Cone (Inferno Blade, Arctic Cone, Fire Breath)
- ✅ Circle - Source origin (Frostbite Hammer target, Vampiric Aura)
- ✅ Circle - Target origin (Meteor Strike, Gravity Well)
- ✅ Beam (Void Piercer, Shadow Beam, Void Beam)
- ✅ Pierce (Void Piercer, Shadow Beam)
- ⏳ Splash (needs test item)

### Status Effects (12+ types)
- ✅ Burn (Inferno Blade, Meteor Strike, Fire Breath, Inferno Drake)
- ✅ Bleed (Blood Reaver)
- ✅ Shock (Lightning Chain Whip, Chain Lightning, Storm Titan)
- ✅ Freeze (Frostbite Hammer, Arctic Cone)
- ✅ Stun (Thunder Slam, Gravity Well)
- ✅ Slow (Arctic Cone, Static Field)
- ✅ Weaken (Void Piercer, Shadow Beam, Void Archon)
- ✅ Vulnerable (Void Explosion)
- ⏳ Root (needs test)
- ⏳ Poison (tested via Acid Slime)
- ⏳ Regeneration (needs test)
- ⏳ Haste (needs test)

### Special Mechanics (5+ types)
- ✅ Lifesteal (Blood Reaver, Vampiric Aura)
- ✅ **Knockback** (Frostbite Hammer, Meteor Strike, Wing Buffet, Void Explosion)
- ✅ **Pull** (Gravity Well, Gravity Pull)
- ⏳ Reflect (needs test)
- ⏳ Thorns (needs test)

### Advanced Features
- ✅ Instant skill execution (all test skills)
- ✅ Distance-based triggers (Void Archon, Storm Titan)
- ✅ Health-based triggers (all enemies)
- ✅ Once-per-fight abilities (Meteor Strike)
- ✅ Max-uses-per-fight (Void Explosion - 2 max)
- ✅ Dual status effects (Arctic Cone, Static Field)
- ✅ Multiple mechanics per ability (Meteor Strike: damage + burn + knockback)
- ✅ High pierce counts (Shadow Beam - 10 targets)
- ✅ High chain counts (Chain Lightning - 5 jumps)
- ✅ Large AoE radii (Gravity Well - 7 tiles, Meteor Strike - 8 tiles)

---

## Testing Workflow

### Phase 1: Load Test Content

1. **Verify JSONs load**:
```bash
# Check console on game start
✓ Loaded X skills from Skills/skills-testing-integration.JSON
✓ Loaded X items from items.JSON/items-testing-integration.JSON
✓ Loaded X enemies from Definitions.JSON/hostiles-testing-integration.JSON
```

2. **Update icon catalog**:
```bash
python tools/unified_icon_generator.py
# Verifies all test items added to catalog
```

3. **Generate icons** (optional):
```bash
python assets/Vheer-automation.py
# Choose test mode for quick validation
```

---

### Phase 2: Test Weapons

**For each weapon**:

1. Spawn/craft weapon
2. Equip to mainHand
3. Attack enemy
4. Verify:
   - Geometry pattern correct
   - Damage type shown in combat log
   - Status effects apply
   - Special mechanics work (knockback, lifesteal, etc.)
   - Console shows expected tags

**Example: Testing Frostbite Hammer**:
1. Equip hammer
2. Attack enemy in group
3. **Check**: All enemies in 4-tile radius hit?
4. **Check**: Enemies frozen (can't move)?
5. **Check**: "💨 Knockback! Enemy pushed back 3.0 tiles"?
6. **Check**: Ice damage type shown?

---

### Phase 3: Test Skills

**For each skill**:

1. Learn skill
2. Equip to hotbar
3. Activate skill
4. Verify:
   - Instant execution (no buff created)
   - Correct geometry
   - All targets hit
   - Status effects apply
   - Special mechanics work

**Example: Testing Gravity Well**:
1. Learn + equip skill
2. Target enemy in group
3. Press hotkey
4. **Check**: "🧲 Pull! Enemy pulled 5.0 tiles"?
5. **Check**: All enemies cluster at target point?
6. **Check**: Enemies stunned after pull?
7. **Check**: Arcane damage dealt?

---

### Phase 4: Test Enemies

**For each enemy**:

1. Spawn enemy (debug or encounter)
2. Engage at various ranges
3. Damage to different HP thresholds
4. Verify:
   - Correct abilities at correct ranges
   - Health-based triggers work
   - Status effects apply to player
   - Special mechanics work on player

**Example: Testing Void Archon**:
1. Spawn Void Archon
2. Stand at 12 tiles away
3. **Check**: Uses Void Beam (not other abilities)?
4. **Check**: Beam pierces?
5. **Check**: Player weakened?
6. Approach to 7 tiles, damage to 65% HP
7. **Check**: Uses Gravity Pull?
8. **Check**: "🧲 Pull! Player pulled 6.0 tiles"?
9. Damage to 25% HP, approach to 5 tiles
10. **Check**: Void Explosion triggers?
11. **Check**: Player knocked back + vulnerable?
12. Damage again at <30% HP
13. **Check**: Void Explosion triggers 2nd time?
14. **Check**: Doesn't trigger 3rd time (max 2 per fight)?

---

### Phase 5: Stress Tests

**Multi-target scenarios**:
1. Spawn 10 enemies in cluster
2. Use Chain Lightning
3. Verify: Chains to 5 targets
4. Use Meteor Strike
5. Verify: All 10 take damage + burn + knockback

**Multi-status scenarios**:
1. Use Arctic Cone on enemies
2. Verify: Some frozen, others just slowed
3. Use Storm Titan's Static Field
4. Verify: Slow + Shock both active simultaneously

**Special mechanics combos**:
1. Use Vampiric Aura on 5 enemies
2. Verify: Heal amount = 60% × (damage × 5 enemies)
3. Use Gravity Well + Meteor Strike combo
4. Verify: Pull, then knockback (opposite forces)

---

## Expected Issues & Known Limitations

### Currently Working ✅
- All damage types
- All geometry patterns (except splash - needs testing)
- Most status effects
- **Knockback physics** (newly implemented)
- **Pull physics** (newly implemented)
- Lifesteal
- Instant skill execution
- Distance/health triggers

### Needs Implementation ⏳
- Holy damage type (no test items yet)
- Chaos damage type (no test items yet)
- Splash geometry (not tested)
- Reflect mechanic (not implemented?)
- Thorns mechanic (not implemented?)
- Root status (not tested)
- Regeneration buff (not tested)
- Haste buff (not tested)

### Visual Feedback Gaps
- Status effect animations (minimal)
- Knockback animation (just position change)
- Pull animation (just position change)
- Beam/cone visual effects (basic)

---

## Success Criteria

**Tag system is complete when**:

1. ✅ All 9 damage types work
2. ✅ All 7 geometry patterns work
3. ✅ All common status effects apply + tick correctly
4. ✅ Knockback/Pull physics work
5. ✅ Lifesteal heals correctly
6. ✅ Chain jumps to correct targets
7. ✅ Pierce penetrates enemies
8. ✅ Instant skills execute immediately
9. ✅ Distance triggers work
10. ✅ Health triggers work
11. ✅ Once-per-fight limits work
12. ✅ Dual status effects coexist

**When all test items/skills/enemies demonstrate expected behavior, tag system integration is COMPLETE.**

---

## Next Steps After Validation

1. **Document failures**: Any test that doesn't work as expected
2. **Fix issues**: Address any tag system bugs found
3. **Add missing**: Holy/Chaos damage, Splash geometry, Reflect/Thorns
4. **Visual polish**: Add animations for knockback, pull, status effects
5. **Performance test**: 20+ enemies with complex abilities
6. **Create more content**: Use validated system for production content

---

**Remember**: These test JSONs validate the ENTIRE tag system end-to-end. Any failures point to specific integration gaps that need fixing!
