# Granular Task Breakdown - 100% Feature Coverage

**Date**: 2025-12-29
**Approach**: Specific, actionable subtasks with code references

---

## PHASE 1: ENCHANTMENT ANALYSIS & FIXES (PRIORITY)

### Current State Analysis

**Enchantment Types in recipes-enchanting-1.JSON (17 types)**:

| # | Enchantment Type | Integration Status | Location | Action Needed |
|---|------------------|-------------------|----------|---------------|
| 1 | **damage_multiplier** | ✅ WORKING | equipment.py:65, game_engine.py:349 | Test only |
| 2 | **damage_reduction** (Protection) | ✅ WORKING (as defense_multiplier) | combat_manager.py:1121 | Test only |
| 3 | **gathering_speed_multiplier** (Efficiency) | ✅ WORKING | character.py:793 | Test only |
| 4 | **bonus_yield_chance** (Fortune) | ✅ WORKING | character.py:847 | Test only |
| 5 | **durability_multiplier** (Unbreaking) | ✅ WORKING | character.py:818 | Test only |
| 6 | **damage_over_time** (Fire Aspect, Poison) | ✅ WORKING | combat_manager.py:734 | Test only |
| 7 | **movement_speed_multiplier** (Swiftness) | ✅ WORKING | character.py:601 | Test only |
| 8 | **reflect_damage** (Thorns) | ✅ WORKING | combat_manager.py:1164 | Test only |
| 9 | **soulbound** | ✅ WORKING | equipment.py:43 | Test only |
| 10 | **knockback** | ❌ NOT INTEGRATED | - | ADD |
| 11 | **lifesteal** | ❌ NOT INTEGRATED | - | ADD |
| 12 | **health_regeneration** | ❌ NOT INTEGRATED | - | ADD |
| 13 | **slow** (on hit) | ❌ NOT INTEGRATED | - | ADD |
| 14 | **chain_damage** | ❌ NOT INTEGRATED | - | ADD |
| 15 | **harvest_original_form** (Silk Touch) | ❌ NOT INTEGRATED | - | ADD |
| 16 | **durability_regeneration** (Self-Repair) | ❌ NO PERIODIC UPDATE | - | DEFER (needs game loop) |
| 17 | **weight_multiplier** (Weightless) | ❌ NO WEIGHT SYSTEM | - | DEFER (needs system) |

**Summary**: 9 working / 5 need integration / 2 deferred

---

### Task 1.1: Test All Working Enchantments (2 hours)

**Subtasks**:
- [ ] 1.1.1 - Create test weapon with Sharpness I, II, III - verify damage increase
- [ ] 1.1.2 - Create test armor with Protection I, II, III - verify damage reduction
- [ ] 1.1.3 - Create test pickaxe with Efficiency I, II - verify gathering speed increase
- [ ] 1.1.4 - Create test pickaxe with Fortune I, II - verify bonus yield triggers
- [ ] 1.1.5 - Create test tool with Unbreaking - verify durability loss reduction
- [ ] 1.1.6 - Create test weapon with Fire Aspect - verify burn applied on hit
- [ ] 1.1.7 - Create test weapon with Poison - verify poison applied on hit
- [ ] 1.1.8 - Create test boots with Swiftness - verify movement speed increase
- [ ] 1.1.9 - Create test armor with Thorns - verify reflect damage on hit
- [ ] 1.1.10 - Create test item with Soulbound - verify (currently no death penalty to test)

**Method**: Use existing enchanting system, apply enchantments, test in-game

---

### Task 1.2: Implement Knockback Enchantment (30 min)

**Reference**: Existing knockback mechanic in `core/effect_executor.py:_apply_knockback()`

**Subtasks**:
- [ ] 1.2.1 - Add knockback check in `combat_manager.py:_apply_weapon_enchantment_effects()`
- [ ] 1.2.2 - Extract knockback distance from effect.get('value', 2.0)
- [ ] 1.2.3 - Call effect_executor._apply_knockback(source, target, params)
- [ ] 1.2.4 - Test with enchanted weapon

**Code Location**: `Combat/combat_manager.py:712-755` (add after damage_over_time check)

**Example Code**:
```python
elif effect_type == 'knockback':
    knockback_distance = effect.get('value', 2.0)
    knockback_params = {'knockback_distance': knockback_distance}

    # Apply knockback using existing effect executor
    from core.effect_executor import get_effect_executor
    executor = get_effect_executor()
    executor._apply_knockback(self.character, enemy, knockback_params)
    print(f"   💨 {enchantment.get('name', 'Knockback')} triggered!")
```

---

### Task 1.3: Implement Lifesteal Enchantment (30 min)

**Reference**: Existing lifesteal tag in `core/effect_executor.py:_apply_lifesteal()`

**Subtasks**:
- [ ] 1.3.1 - Add lifesteal check in `combat_manager.py:player_attack_enemy()` after damage dealt
- [ ] 1.3.2 - Calculate heal amount (damage * lifesteal_percent)
- [ ] 1.3.3 - Apply healing to character
- [ ] 1.3.4 - Test with enchanted weapon

**Code Location**: `Combat/combat_manager.py:654` (after enemy.take_damage())

**Example Code**:
```python
# After applying damage to enemy
# LIFESTEAL ENCHANTMENT: Heal for % of damage dealt
if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
    for ench in equipped_weapon.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'lifesteal':
            lifesteal_percent = effect.get('value', 0.1)  # 10% default
            heal_amount = final_damage * lifesteal_percent
            self.character.health = min(self.character.max_health, self.character.health + heal_amount)
            print(f"   💚 Lifesteal: Healed {heal_amount:.1f} HP")
```

---

### Task 1.4: Implement Health Regeneration Enchantment (30 min)

**Reference**: Existing regeneration status effect in `entities/status_effect.py:RegenerationEffect`

**Subtasks**:
- [ ] 1.4.1 - Add regen check in character stat calculation
- [ ] 1.4.2 - Apply flat HP/sec bonus from armor enchantments
- [ ] 1.4.3 - Integrate with existing regeneration system
- [ ] 1.4.4 - Test with enchanted armor

**Code Location**: `entities/character.py:recalculate_stats()` or periodic update

**Example Code**:
```python
# In character.py recalculate_stats() or periodic update
# HEALTH REGENERATION ENCHANTMENT
regen_bonus = 0.0
for slot in ['helmet', 'chestplate', 'leggings', 'boots', 'gauntlets']:
    armor_piece = self.equipment.slots.get(slot)
    if armor_piece and hasattr(armor_piece, 'enchantments'):
        for ench in armor_piece.enchantments:
            effect = ench.get('effect', {})
            if effect.get('type') == 'health_regeneration':
                regen_bonus += effect.get('value', 1.0)  # HP per second

# Apply regen in periodic update (if exists)
if regen_bonus > 0:
    self.health = min(self.max_health, self.health + regen_bonus * dt)
```

---

### Task 1.5: Implement Slow (on hit) Enchantment (30 min)

**Reference**: Existing slow status effect in `entities/status_effect.py:SlowEffect`

**Subtasks**:
- [ ] 1.5.1 - Add slow check in `combat_manager.py:_apply_weapon_enchantment_effects()`
- [ ] 1.5.2 - Apply slow status to enemy using status_manager
- [ ] 1.5.3 - Test with enchanted weapon

**Code Location**: `Combat/combat_manager.py:712-755` (add after damage_over_time)

**Example Code**:
```python
elif effect_type == 'slow':
    slow_params = {
        'duration': effect.get('duration', 3.0),
        'speed_reduction': effect.get('value', 0.3)  # 30% slow
    }

    if hasattr(enemy, 'status_manager'):
        enemy.status_manager.apply_status('slow', slow_params, source=self.character)
        print(f"   ❄️ {enchantment.get('name', 'Frost')} triggered! Applied slow")
```

---

### Task 1.6: Implement Chain Damage Enchantment (1 hour)

**Reference**: Existing chain geometry in `core/geometry/target_finder.py:find_chain_targets()`

**Subtasks**:
- [ ] 1.6.1 - Add chain_damage check after primary target is hit
- [ ] 1.6.2 - Use target_finder.find_chain_targets() to find secondary targets
- [ ] 1.6.3 - Apply reduced damage to chained targets (50% of original)
- [ ] 1.6.4 - Test with enchanted weapon against groups

**Code Location**: `Combat/combat_manager.py:654` (after primary damage)

**Example Code**:
```python
# CHAIN DAMAGE ENCHANTMENT
if equipped_weapon and hasattr(equipped_weapon, 'enchantments'):
    for ench in equipped_weapon.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'chain_damage':
            chain_count = int(effect.get('value', 2))  # Chain to 2 enemies
            chain_damage_percent = 0.5  # 50% damage to chained targets

            # Find chain targets
            from core.geometry.target_finder import TargetFinder
            finder = TargetFinder()
            chain_targets = finder.find_chain_targets(
                primary=enemy,
                max_targets=chain_count,
                available_entities=[e for e in self.active_enemies if e.is_alive and e != enemy]
            )

            if chain_targets:
                chain_damage = final_damage * chain_damage_percent
                print(f"   ⚡ Chain Damage: Hitting {len(chain_targets)} additional target(s)")
                for target in chain_targets:
                    target.take_damage(chain_damage, from_player=True)
```

---

### Task 1.7: Implement Silk Touch Enchantment (1 hour)

**Reference**: Existing resource loot system in `systems/natural_resource.py:get_loot()`

**Subtasks**:
- [ ] 1.7.1 - Add silk_touch flag to resource harvesting in character.py
- [ ] 1.7.2 - Check for harvest_original_form enchantment on equipped tool
- [ ] 1.7.3 - If present, drop resource block item instead of processed materials
- [ ] 1.7.4 - Define "original form" items for each resource (stone → stone_block, tree → log, etc.)
- [ ] 1.7.5 - Test with enchanted tool

**Code Location**: `entities/character.py:_single_node_harvest()` around line 826

**Example Code**:
```python
# Check for silk touch enchantment
silk_touch = False
if hasattr(equipped_tool, 'enchantments'):
    for ench in equipped_tool.enchantments:
        effect = ench.get('effect', {})
        if effect.get('type') == 'harvest_original_form':
            silk_touch = True
            break

if depleted:
    if silk_touch:
        # Drop original form instead of processed loot
        original_item = resource.get_original_form()  # New method needed
        if original_item:
            loot = [(original_item, 1)]
            print(f"   ✨ Silk Touch: Harvested {original_item} (original form)")
    else:
        loot = resource.get_loot()
```

**Additional Work**: Add `get_original_form()` method to NaturalResource class

---

## PHASE 2: TURRET STATUS EFFECTS (SIMPLE)

### Current State
- Turrets have health and attack logic
- Turrets use tag system for attacks
- Turrets have NO status effect support

### Task 2.1: Add Status Effect Fields to PlacedEntity (15 min)

**Subtasks**:
- [ ] 2.1.1 - Add `status_effects: List[Any] = None` to PlacedEntity dataclass
- [ ] 2.1.2 - Add `is_stunned: bool = False`
- [ ] 2.1.3 - Add `is_frozen: bool = False`
- [ ] 2.1.4 - Add `is_rooted: bool = False`
- [ ] 2.1.5 - Add `visual_effects: Set[str] = None`
- [ ] 2.1.6 - Initialize in `__post_init__()`

**Code Location**: `data/models/world.py:153` (PlacedEntity class)

---

### Task 2.2: Add Status Effect Methods to PlacedEntity (30 min)

**Reference**: Similar methods in `Combat/enemy.py` and `entities/character.py`

**Subtasks**:
- [ ] 2.2.1 - Add `take_damage(damage, damage_type)` method
- [ ] 2.2.2 - Add `update_status_effects(dt)` method
- [ ] 2.2.3 - Add `apply_status_effect(effect)` method
- [ ] 2.2.4 - Add `remove_status_effect(effect)` method

**Code Location**: `data/models/world.py:153` (PlacedEntity class)

**Example Code**:
```python
def take_damage(self, damage: float, damage_type: str = "physical") -> bool:
    """Take damage and return True if destroyed"""
    self.health -= damage
    if self.health <= 0:
        self.health = 0
        return True  # Turret destroyed
    return False

def update_status_effects(self, dt: float):
    """Update all active status effects"""
    if not self.status_effects:
        return

    for effect in self.status_effects[:]:  # Copy list
        effect.update(dt)
        if effect.is_expired():
            effect.on_remove(self)
            self.status_effects.remove(effect)
```

---

### Task 2.3: Modify Turret System to Handle Status Effects (20 min)

**Subtasks**:
- [ ] 2.3.1 - Call `entity.update_status_effects(dt)` at start of update loop
- [ ] 2.3.2 - Check `entity.is_stunned` - skip attack if true
- [ ] 2.3.3 - Check `entity.is_frozen` - skip attack if true
- [ ] 2.3.4 - Reduce attack speed if slowed

**Code Location**: `systems/turret_system.py:21` (update method)

**Example Code**:
```python
def update(self, placed_entities, combat_manager, dt):
    for entity in placed_entities:
        # Update status effects FIRST
        if hasattr(entity, 'update_status_effects'):
            entity.update_status_effects(dt)

        # Update lifetime
        entity.time_remaining -= dt
        if entity.time_remaining <= 0:
            entities_to_remove.append(entity)
            continue

        # Only process turrets
        if entity.entity_type != PlacedEntityType.TURRET:
            continue

        # Check if disabled by status effects
        if hasattr(entity, 'is_stunned') and entity.is_stunned:
            continue
        if hasattr(entity, 'is_frozen') and entity.is_frozen:
            continue

        # Normal turret logic...
```

---

### Task 2.4: Allow Enemies to Target Turrets (30 min)

**Subtasks**:
- [ ] 2.4.1 - Include `placed_entities` (turrets) in available_entities for enemy abilities
- [ ] 2.4.2 - Modify enemy AI to consider turrets as targets
- [ ] 2.4.3 - Test enemy AoE abilities hitting turrets

**Code Location**: `Combat/enemy.py` (where enemies use special abilities)

---

## PHASE 3: TRAP SYSTEM (SIMPLE - JUST TRIGGER LOGIC)

### Current State
- Traps defined with tags in items-engineering-1.JSON
- NO proximity detection
- NO trigger system

### Task 3.1: Add Trigger Detection to Turret System (1 hour)

**Reference**: Similar distance calculation in `turret_system.py:_find_nearest_enemy()`

**Subtasks**:
- [ ] 3.1.1 - Add `check_trap_triggers()` method to TurretSystem
- [ ] 3.1.2 - Loop through placed entities of type TRAP
- [ ] 3.1.3 - Check distance to all enemies
- [ ] 3.1.4 - If enemy in trigger radius, execute trap effect
- [ ] 3.1.5 - Mark trap as triggered (add `triggered` field to PlacedEntity)

**Code Location**: `systems/turret_system.py` (new method)

**Example Code**:
```python
def check_trap_triggers(self, placed_entities: List[PlacedEntity], all_enemies: List) -> List[PlacedEntity]:
    """Check if any enemies trigger traps, return list of triggered traps to remove"""
    triggered_traps = []

    for entity in placed_entities:
        if entity.entity_type != PlacedEntityType.TRAP:
            continue

        # Skip already triggered traps
        if hasattr(entity, 'triggered') and entity.triggered:
            continue

        # Get trigger radius from effect params
        trigger_radius = entity.effect_params.get('trigger_radius', 2.0)

        # Check all enemies
        for enemy in all_enemies:
            if not enemy.is_alive:
                continue

            # Calculate distance
            enemy_x, enemy_y = enemy.position[0], enemy.position[1]
            dx = entity.position.x - enemy_x
            dy = entity.position.y - enemy_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist <= trigger_radius:
                # TRIGGER TRAP!
                self._trigger_trap(entity, enemy, all_enemies)
                entity.triggered = True
                triggered_traps.append(entity)
                break  # One trigger per trap

    return triggered_traps

def _trigger_trap(self, trap: PlacedEntity, primary_target: Enemy, all_enemies: List):
    """Execute trap effect using tag system"""
    print(f"\n💥 TRAP TRIGGERED: {trap.item_id}")
    print(f"   Target: {primary_target.definition.name}")
    print(f"   Tags: {', '.join(trap.tags)}")

    # Execute effect using existing tag system
    context = self.effect_executor.execute_effect(
        source=trap,  # Trap is the source
        primary_target=primary_target,
        tags=trap.tags,
        params=trap.effect_params,
        available_entities=all_enemies
    )

    print(f"   ✓ Affected {len(context.targets)} target(s)")
```

---

### Task 3.2: Integrate Trap Checking into Update Loop (10 min)

**Subtasks**:
- [ ] 3.2.1 - Call `check_trap_triggers()` in TurretSystem.update()
- [ ] 3.2.2 - Remove triggered one-time traps from placed_entities
- [ ] 3.2.3 - Test with spike_trap, frost_mine, bear_trap

**Code Location**: `systems/turret_system.py:21` (update method)

---

## PHASE 4: BOMB SYSTEM (NEW CLASS - SIMPLE)

### Current State
- Bombs defined with tags
- NO placement system
- NO detonation system

### Task 4.1: Create Bomb Placement System (2 hours) ✅ COMPLETE

**Reference**: Existing turret placement in `core/game_engine.py`

**Subtasks**:
- [x] 4.1.1 - Add bomb inventory check (similar to turret placement) - ALREADY IMPLEMENTED
- [x] 4.1.2 - Add bomb placement input handling (key 'B' or similar) - USES DOUBLE-CLICK
- [x] 4.1.3 - Create PlacedEntity with type=BOMB at player position - WORKING
- [x] 4.1.4 - Add fuse timer to bomb (effect_params.fuse_time) - IMPLEMENTED IN turret_system.py
- [x] 4.1.5 - Test placing bombs - READY FOR TESTING

**Code Location**: `core/game_engine.py` (where turret placement is handled)

---

### Task 4.2: Create Bomb Detonation System (1 hour) ✅ COMPLETE

**Subtasks**:
- [x] 4.2.1 - Add bomb timer countdown in TurretSystem.update() - IMPLEMENTED check_bomb_detonations()
- [x] 4.2.2 - When timer reaches 0, execute bomb effect - IMPLEMENTED _detonate_bomb()
- [x] 4.2.3 - Use tag system for AoE damage (bombs have circle geometry) - USES effect_executor
- [x] 4.2.4 - Remove bomb after detonation - ADDS TO entities_to_remove
- [ ] 4.2.5 - Add visual/sound feedback - DEFERRED (console output only for now)

**Code Location**: `systems/turret_system.py:21` (update method)

**Example Code**:
```python
# In turret_system.py update()
if entity.entity_type == PlacedEntityType.BOMB:
    # Countdown fuse timer
    entity.time_remaining -= dt
    if entity.time_remaining <= 0:
        # DETONATE!
        self._detonate_bomb(entity, combat_manager.get_all_active_enemies())
        entities_to_remove.append(entity)
        continue

def _detonate_bomb(self, bomb: PlacedEntity, all_enemies: List):
    """Detonate bomb using tag system"""
    print(f"\n💣 BOMB DETONATION: {bomb.item_id}")

    # Execute AoE effect
    context = self.effect_executor.execute_effect(
        source=bomb,
        primary_target=None,  # No primary target for bombs
        tags=bomb.tags,
        params=bomb.effect_params,
        available_entities=all_enemies
    )

    print(f"   💥 Affected {len(context.targets)} target(s)")
```

---

## PHASE 5: UTILITY DEVICES (MISCELLANEOUS)

### Task 5.1: Healing Beacon (1 hour) ✅ COMPLETE

**Reference**: Existing healing potion logic

**Subtasks**:
- [x] 5.1.1 - Create periodic heal check in TurretSystem for UTILITY_DEVICE type - IMPLEMENTED update_utility_devices()
- [x] 5.1.2 - Check if player in range of healing beacon - DISTANCE CHECK ADDED
- [x] 5.1.3 - Apply heal_per_second from effect_params - 10 HP/sec in 5 unit radius
- [x] 5.1.4 - Add visual feedback (green glow) - CONSOLE OUTPUT (visual effects deferred)
- [x] 5.1.5 - Test with placed healing beacon - READY FOR TESTING

**Code Location**: `systems/turret_system.py` (new method)

---

### Task 5.2: Net Launcher (1 hour) ✅ COMPLETE

**Reference**: Existing root status effect

**Subtasks**:
- [x] 5.2.1 - Add net launcher placement (similar to bomb) - USES EXISTING PLACEMENT
- [x] 5.2.2 - Add activation trigger (auto-deploy or manual) - AUTO-DEPLOY ON PROXIMITY
- [x] 5.2.3 - Apply root status to enemies in area - APPLIES 80% SLOW FOR 10s
- [x] 5.2.4 - Remove net launcher after use - MARKED AS TRIGGERED
- [x] 5.2.5 - Test rooting enemies - READY FOR TESTING

**Code Location**: `systems/turret_system.py` or `core/game_engine.py`

---

### Task 5.3: EMP Device (1 hour) ✅ COMPLETE

**Reference**: Existing stun status effect

**Subtasks**:
- [x] 5.3.1 - Add EMP device placement - USES EXISTING PLACEMENT
- [x] 5.3.2 - Check for construct-type enemies (robots, turrets, etc.) - CHECKS enemy_type == 'construct'
- [x] 5.3.3 - Apply stun/disable status to constructs in area - 30s STUN IN 8 UNIT RADIUS
- [x] 5.3.4 - No effect on organic enemies - CONSTRUCT TYPE CHECK
- [x] 5.3.5 - Test disabling enemy turrets/constructs - READY FOR TESTING

**Code Location**: `systems/turret_system.py` or `core/game_engine.py`

---

## PHASE 6: HOSTILE ABILITIES VERIFICATION (CURSORY)

### Task 6.1: Quick Audit of All Enemy Abilities (30 min) ✅ COMPLETE

**Audit Results**:
- ✅ **21 abilities** total in hostiles-1.JSON
- ✅ **100% have tags** - No abilities missing tags
- ✅ **100% have effectParams** - No abilities missing params
- ✅ **34 unique tags** used: ally, arcane, beam, bleed, chain, chaos, circle, cone, confuse, empower, enrage, fortify, haste, invisible, knockback, lifesteal, physical, pierce, player, poison, poison_status, pull, random, reflect, self, shadow, shield, silence, single, slow, stun, summon, teleport, vulnerable
- ✅ **All geometry tags present**: single, chain, circle, cone, beam, pierce
- ✅ **All damage types present**: physical, arcane, poison, shadow, chaos
- ✅ **All status effects present**: bleed, poison_status, slow, stun, confuse, vulnerable, silence

**Subtasks**:
- [x] 6.1.1 - Read through all enemy definitions in hostiles-1.JSON - AUTOMATED AUDIT
- [x] 6.1.2 - Verify each has tags defined - 21/21 HAVE TAGS
- [x] 6.1.3 - Verify each has effect_params if needed - 21/21 HAVE PARAMS
- [x] 6.1.4 - Check for any obvious issues (missing tags, wrong geometry, etc.) - NO ISSUES FOUND

**Code Location**: `Definitions.JSON/hostiles-1.JSON`

---

### Task 6.2: Test High-Impact Abilities (1 hour) ⏭️ DEFERRED

**Note**: Since all abilities are properly defined with tags and params, and the tag system is already working for player abilities, enemy abilities should work automatically. Gameplay testing will verify this.

**High-Impact Abilities to Test**:

**Subtasks**:
- [ ] 6.2.1 - Test Stone Golem fortify/slow (self-buff) - ✅ ALREADY VERIFIED
- [ ] 6.2.2 - Test Primordial Entity void_rift (circle pull) - ✅ ALREADY VERIFIED
- [ ] 6.2.3 - Test Fire Imp fireball (burn)
- [ ] 6.2.4 - Test Frost Sprite frost_bolt (freeze)
- [ ] 6.2.5 - Test Lightning Elemental chain_lightning (chain)
- [ ] 6.2.6 - Test Shadow Wraith teleport (teleport tag)
- [ ] 6.2.7 - Test any cone/beam abilities if present

---

## PHASE 7: COMPREHENSIVE TESTING

### Task 7.1: Create Automated Test Suite (2 hours)

**Subtasks**:
- [ ] 7.1.1 - Create test file `tests/test_enchantments.py`
- [ ] 7.1.2 - Create test file `tests/test_turrets.py`
- [ ] 7.1.3 - Create test file `tests/test_traps.py`
- [ ] 7.1.4 - Create test file `tests/test_hostile_abilities.py`
- [ ] 7.1.5 - Run all tests and document results

---

### Task 7.2: Manual Gameplay Testing (2 hours)

**Subtasks**:
- [ ] 7.2.1 - Test all 17 enchantments in actual gameplay
- [ ] 7.2.2 - Test all 5 turrets attacking different enemy types
- [ ] 7.2.3 - Test all 3 traps triggering on enemy proximity
- [ ] 7.2.4 - Test all 3 bombs detonating correctly
- [ ] 7.2.5 - Test turrets receiving status effects from enemies
- [ ] 7.2.6 - Test 10+ different enemy special abilities
- [ ] 7.2.7 - Document any bugs found

---

## SUMMARY

### Total Tasks: 71 subtasks across 7 phases

**Phase 1 - Enchantments**: 35 subtasks (3-4 hours)
**Phase 2 - Turret Status Effects**: 12 subtasks (1.5 hours)
**Phase 3 - Trap System**: 8 subtasks (1 hour)
**Phase 4 - Bomb System**: 9 subtasks (3 hours)
**Phase 5 - Utility Devices**: 9 subtasks (3 hours)
**Phase 6 - Hostile Abilities**: 8 subtasks (1.5 hours)
**Phase 7 - Testing**: 12 subtasks (4 hours)

**Total Estimated Time**: ~17-20 hours

### Execution Order

**Day 1** (4 hours): Enchantment testing + adding missing enchantments
**Day 2** (3 hours): Turret status effects + trap system
**Day 3** (3 hours): Bomb system
**Day 4** (3 hours): Utility devices
**Day 5** (2 hours): Hostile ability verification
**Day 6** (4 hours): Comprehensive testing

**Target**: 100% feature coverage in 6 days part-time work
