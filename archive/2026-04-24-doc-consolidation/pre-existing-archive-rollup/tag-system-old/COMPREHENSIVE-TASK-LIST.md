# Comprehensive Task List: Tag System Final Integration

**Total Estimated Time**: 21-28 hours
**Start Date**: 2025-12-21
**Goal**: Wire up all tag system connections to make combat use tags

---

## PHASE 1: Player Attacks with Tags (CRITICAL)
**Time Estimate**: 3-4 hours
**Priority**: CRITICAL - Must work before proceeding

### 1.1 Add Effect Tag Support to Equipment Model
- [ ] **1.1.1** Read `data/models/equipment.py` to understand current structure
- [ ] **1.1.2** Add `effect_tags: List[str] = None` field to EquipmentItem dataclass
- [ ] **1.1.3** Add `effect_params: Dict = None` field to EquipmentItem dataclass
- [ ] **1.1.4** Add method `get_effect_tags(self) -> List[str]` to return effect_tags or []
- [ ] **1.1.5** Add method `get_effect_params(self) -> Dict` to return effect_params or {}
- [ ] **1.1.6** Test: Verify Equipment model loads without errors

### 1.2 Update Equipment Database Loader
- [ ] **1.2.1** Read `data/databases.py` EquipmentDatabase.load_from_file()
- [ ] **1.2.2** Add loading of `effectTags` field from JSON
- [ ] **1.2.3** Add loading of `effectParams` field from JSON
- [ ] **1.2.4** Store effectTags and effectParams in Equipment object
- [ ] **1.2.5** Add debug output showing loaded tags
- [ ] **1.2.6** Test: Load game and verify no errors

### 1.3 Add effectTags to Test Weapons (JSON)
- [ ] **1.3.1** Open `items.JSON/items-smithing-2.JSON`
- [ ] **1.3.2** Add effectTags to `iron_shortsword`:
  ```json
  "effectTags": ["physical", "slashing", "single"],
  "effectParams": {"baseDamage": 30}
  ```
- [ ] **1.3.3** Add effectTags to `copper_spear`:
  ```json
  "effectTags": ["physical", "piercing", "single"],
  "effectParams": {"baseDamage": 25}
  ```
- [ ] **1.3.4** Add effectTags to `steel_longsword`:
  ```json
  "effectTags": ["physical", "slashing", "single"],
  "effectParams": {"baseDamage": 40}
  ```
- [ ] **1.3.5** Add effectTags to `steel_battleaxe`:
  ```json
  "effectTags": ["physical", "slashing", "single"],
  "effectParams": {"baseDamage": 50}
  ```
- [ ] **1.3.6** Add effectTags to `iron_warhammer`:
  ```json
  "effectTags": ["physical", "crushing", "single"],
  "effectParams": {"baseDamage": 45}
  ```
- [ ] **1.3.7** Test: Load game and verify JSON parses correctly

### 1.4 Add effectTags to Bow (items-tools-1.JSON or find bow location)
- [ ] **1.4.1** Find JSON file containing `pine_shortbow`
- [ ] **1.4.2** Add effectTags to `pine_shortbow`:
  ```json
  "effectTags": ["physical", "piercing", "single"],
  "effectParams": {"baseDamage": 20}
  ```
- [ ] **1.4.3** Test: Load game and verify bow JSON parses correctly

### 1.5 Modify Player Attack to Use Tags
- [ ] **1.5.1** Read `core/game_engine.py` to find player attack call locations (lines ~847, 1454, 2786)
- [ ] **1.5.2** Create helper method `_get_weapon_effect_data(self, hand: str) -> Tuple[List[str], Dict]`
  - Get equipped weapon from hand
  - Extract effect_tags (or fallback to ["physical", "single"])
  - Extract effect_params
  - Calculate baseDamage from weapon damage range
  - Return (effect_tags, effect_params)
- [ ] **1.5.3** Locate first player attack call (line ~847, offHand click)
- [ ] **1.5.4** Replace with tag-based attack:
  ```python
  effect_tags, effect_params = self._get_weapon_effect_data('offHand')
  damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(
      enemy, effect_tags, effect_params
  )
  ```
- [ ] **1.5.5** Locate second player attack call (line ~1454, mainHand left-click)
- [ ] **1.5.6** Replace with tag-based attack (same pattern)
- [ ] **1.5.7** Locate third player attack call (line ~2786, if exists)
- [ ] **1.5.8** Replace with tag-based attack (same pattern)
- [ ] **1.5.9** Test: Compile and run without errors

### 1.6 Update player_attack_enemy_with_tags to Pass Tags to Damage
- [ ] **1.6.1** Read `Combat/combat_manager.py` `player_attack_enemy_with_tags()` (line ~573)
- [ ] **1.6.2** Find where effect_executor is called
- [ ] **1.6.3** Verify effect_executor passes tags to enemy.take_damage()
- [ ] **1.6.4** Check if effect_executor properly configured with context
- [ ] **1.6.5** Test: Attack training dummy and verify tags appear in output

### 1.7 Fix Training Dummy Tag Reception (if needed)
- [ ] **1.7.1** Read `systems/training_dummy.py` take_damage() method
- [ ] **1.7.2** Verify it accepts both `source_tags` and `tags` parameters
- [ ] **1.7.3** Verify tag normalization logic works
- [ ] **1.7.4** Test: Attack training dummy with iron_shortsword
- [ ] **1.7.5** Verify console shows: `🏷️  Attack Tags: physical, slashing, single`

### 1.8 Test Phase 1 End-to-End
- [ ] **1.8.1** Craft iron_shortsword with smithing
- [ ] **1.8.2** Equip iron_shortsword to mainHand
- [ ] **1.8.3** Spawn training dummy
- [ ] **1.8.4** Attack dummy with equipped sword
- [ ] **1.8.5** Verify console output shows:
  - ⚔️ PLAYER TAG ATTACK (not legacy attack)
  - Tags: physical, slashing, single
  - 🎯 TRAINING DUMMY HIT with Attack Tags
- [ ] **1.8.6** Test with different weapons (spear, axe, hammer, bow)
- [ ] **1.8.7** Verify each weapon's tags appear correctly
- [ ] **1.8.8** Commit Phase 1 changes

---

## PHASE 2: Turrets with Tags
**Time Estimate**: 4-5 hours
**Priority**: HIGH

### 2.1 Add effectTags to Turret JSON
- [ ] **2.1.1** Open `items.JSON/items-engineering-1.JSON`
- [ ] **2.1.2** Add effectTags to `basic_arrow_turret`:
  ```json
  "effectTags": ["physical", "piercing", "single"],
  "effectParams": {
    "baseDamage": 20,
    "range": 5.0
  }
  ```
- [ ] **2.1.3** Add effectTags to `fire_arrow_turret`:
  ```json
  "effectTags": ["fire", "piercing", "single", "burn"],
  "effectParams": {
    "baseDamage": 35,
    "range": 7.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 5.0
  }
  ```
- [ ] **2.1.4** Add effectTags to `lightning_cannon`:
  ```json
  "effectTags": ["lightning", "chain", "shock"],
  "effectParams": {
    "baseDamage": 70,
    "range": 10.0,
    "chain_count": 2,
    "chain_range": 5.0,
    "shock_duration": 2.0,
    "shock_damage": 5.0
  }
  ```
- [ ] **2.1.5** Add effectTags to `flamethrower_turret`:
  ```json
  "effectTags": ["fire", "cone", "burn"],
  "effectParams": {
    "baseDamage": 60,
    "range": 8.0,
    "cone_angle": 60.0,
    "cone_range": 8.0,
    "burn_duration": 5.0,
    "burn_damage_per_second": 8.0
  }
  ```
- [ ] **2.1.6** Add effectTags to `laser_turret`:
  ```json
  "effectTags": ["energy", "beam"],
  "effectParams": {
    "baseDamage": 80,
    "range": 12.0,
    "beam_range": 12.0,
    "beam_width": 1.0
  }
  ```
- [ ] **2.1.7** Test: Load game and verify turret JSON parses

### 2.2 Update MaterialDatabase to Load Turret Tags
- [ ] **2.2.1** Read `data/databases.py` MaterialDatabase class
- [ ] **2.2.2** Find where device items are loaded
- [ ] **2.2.3** Check if MaterialDefinition has effect_tags field
- [ ] **2.2.4** If not, add effect_tags and effect_params fields to MaterialDefinition
- [ ] **2.2.5** Update loader to read effectTags and effectParams from JSON
- [ ] **2.2.6** Store in MaterialDefinition object
- [ ] **2.2.7** Test: Load game and verify turret tags load correctly

### 2.3 Update Turret Placement to Use Tags
- [ ] **2.3.1** Read `core/game_engine.py` turret placement code (line ~1380)
- [ ] **2.3.2** Find where `world.place_entity()` is called
- [ ] **2.3.3** Before calling place_entity, extract tags from material definition:
  ```python
  effect_tags = mat_def.effect_tags if hasattr(mat_def, 'effect_tags') else []
  effect_params = mat_def.effect_params if hasattr(mat_def, 'effect_params') else {}
  ```
- [ ] **2.3.4** Modify world.place_entity() signature to accept tags and params
- [ ] **2.3.5** Pass tags and params to PlacedEntity creation
- [ ] **2.3.6** Test: Compile without errors

### 2.4 Update WorldSystem.place_entity() Signature
- [ ] **2.4.1** Read `systems/world_system.py` place_entity() method (line ~105)
- [ ] **2.4.2** Add parameters `tags: List[str] = None, effect_params: dict = None`
- [ ] **2.4.3** Update PlacedEntity creation to include tags and effect_params:
  ```python
  entity = PlacedEntity(
      position=position.snap_to_grid(),
      item_id=item_id,
      entity_type=entity_type,
      tier=tier,
      range=range,
      damage=damage,
      tags=tags if tags else [],
      effect_params=effect_params if effect_params else {}
  )
  ```
- [ ] **2.4.4** Test: Compile without errors

### 2.5 Update Game Engine to Pass Tags When Placing
- [ ] **2.5.1** Return to `core/game_engine.py` turret placement
- [ ] **2.5.2** Update place_entity call to include tags:
  ```python
  self.world.place_entity(
      player_pos,
      item_stack.item_id,
      entity_type,
      tier=mat_def.tier,
      range=range_val,
      damage=damage_val,
      tags=effect_tags,
      effect_params=effect_params
  )
  ```
- [ ] **2.5.3** Add debug output showing tags being placed
- [ ] **2.5.4** Test: Compile without errors

### 2.6 Test Phase 2 End-to-End
- [ ] **2.6.1** Craft `flamethrower_turret` with engineering
- [ ] **2.6.2** Place turret near training dummy
- [ ] **2.6.3** Wait for turret to attack
- [ ] **2.6.4** Verify console output shows:
  - 🏹 TURRET ATTACK (not legacy)
  - Tags: fire, cone, burn
  - Effect Params with cone_angle, baseDamage, etc.
  - ✓ Effect executed successfully
  - 🎯 TRAINING DUMMY HIT with Attack Tags
- [ ] **2.6.5** Test with basic_arrow_turret (single target)
- [ ] **2.6.6** Test with fire_arrow_turret (burn status)
- [ ] **2.6.7** Verify turret attacks use tag system
- [ ] **2.6.8** Commit Phase 2 changes

---

## PHASE 3: Enchantment Effects Trigger
**Time Estimate**: 2-3 hours
**Priority**: HIGH

### 3.1 Understand Current Enchantment System
- [ ] **3.1.1** Read `data/models/equipment.py` apply_enchantment() method
- [ ] **3.1.2** Check enchantment effect structure
- [ ] **3.1.3** Find enchantment JSON files (recipes.JSON/recipes-enchanting-1.JSON)
- [ ] **3.1.4** Document enchantment effect types (onHit, damage_over_time, etc.)

### 3.2 Add Enchantment Processing to player_attack_enemy_with_tags
- [ ] **3.2.1** Read `Combat/combat_manager.py` player_attack_enemy_with_tags()
- [ ] **3.2.2** Find location after damage is dealt (after effect_executor)
- [ ] **3.2.3** Add enchantment effect processing:
  ```python
  # After effect_executor.execute_effect()
  # Check weapon enchantments
  weapon = self.character.equipment.slots.get(hand)
  if weapon and weapon.enchantments:
      for ench in weapon.enchantments:
          effect = ench.get('effect', {})
          effect_type = effect.get('type')

          if effect_type == 'damage_over_time':
              # Apply burning/poison/etc status
              element = effect.get('element', 'fire')
              duration = effect.get('duration', 5)
              dps = effect.get('damagePerSecond', 5)

              # Apply to primary target
              if hasattr(primary_target, 'apply_status_effect'):
                  primary_target.apply_status_effect(f"{element}_status", duration, dps)
                  print(f"   ✨ {ench['name']} triggered: {element} for {duration}s")
  ```
- [ ] **3.2.4** Test: Compile without errors

### 3.3 Add apply_status_effect() to Enemy Class
- [ ] **3.3.1** Read `entities/enemy.py` to check if status effects exist
- [ ] **3.3.2** If no status effect system, add basic implementation:
  ```python
  def __init__(self):
      # ...existing code...
      self.status_effects = {}  # {effect_name: {'duration': float, 'dps': float}}

  def apply_status_effect(self, effect_name: str, duration: float, dps: float = 0):
      """Apply or refresh a status effect"""
      self.status_effects[effect_name] = {
          'duration': duration,
          'dps': dps,
          'time_elapsed': 0
      }

  def update_status_effects(self, dt: float):
      """Update status effects and apply damage"""
      to_remove = []
      for effect_name, data in self.status_effects.items():
          data['time_elapsed'] += dt
          data['duration'] -= dt

          # Apply damage
          if data['dps'] > 0 and data['time_elapsed'] >= 1.0:
              self.current_health -= data['dps']
              data['time_elapsed'] = 0

          # Remove if expired
          if data['duration'] <= 0:
              to_remove.append(effect_name)

      for effect_name in to_remove:
          del self.status_effects[effect_name]
  ```
- [ ] **3.3.3** Test: Compile without errors

### 3.4 Add Status Effect Update to Combat Loop
- [ ] **3.4.1** Find combat update loop in game_engine.py or combat_manager.py
- [ ] **3.4.2** Add enemy status effect updates:
  ```python
  for enemy in active_enemies:
      if enemy.is_alive:
          enemy.update_status_effects(dt)
  ```
- [ ] **3.4.3** Test: Compile without errors

### 3.5 Add apply_status_effect() to TrainingDummy
- [ ] **3.5.1** Read `systems/training_dummy.py`
- [ ] **3.5.2** Add status_effects tracking (same as Enemy)
- [ ] **3.5.3** Add apply_status_effect() method
- [ ] **3.5.4** Add update_status_effects() method
- [ ] **3.5.5** Update display to show active status effects
- [ ] **3.5.6** Test: Compile without errors

### 3.6 Test Phase 3 End-to-End
- [ ] **3.6.1** Craft weapon (iron_shortsword)
- [ ] **3.6.2** Apply Fire Aspect enchantment to weapon
- [ ] **3.6.3** Equip enchanted weapon
- [ ] **3.6.4** Attack training dummy
- [ ] **3.6.5** Verify console output shows:
  - ✨ Fire Aspect triggered: fire for 5s
  - 📋 Active Status Effects: - burning (x1, 5.0s, 10.0 dmg/tick)
- [ ] **3.6.6** Wait and verify burning damage ticks
- [ ] **3.6.7** Verify burning expires after duration
- [ ] **3.6.8** Commit Phase 3 changes

---

## PHASE 4: Complete Weapon Coverage
**Time Estimate**: 4-5 hours
**Priority**: MEDIUM

### 4.1 Add effectTags to All Weapons in items-smithing-2.JSON
- [ ] **4.1.1** Open `items.JSON/items-smithing-2.JSON`
- [ ] **4.1.2** For each weapon in "weapons" section:
  - [ ] Determine damage type from metadata tags (slashing/piercing/crushing)
  - [ ] Add effectTags: ["physical", "<damage_type>", "single"]
  - [ ] Add effectParams: {"baseDamage": <average of damage range>}
- [ ] **4.1.3** Update weapons:
  - [ ] iron_shortsword (if not done in Phase 1)
  - [ ] copper_spear (if not done in Phase 1)
  - [ ] steel_longsword (if not done in Phase 1)
  - [ ] steel_battleaxe (if not done in Phase 1)
  - [ ] iron_warhammer (if not done in Phase 1)
  - [ ] (Any other weapons found)
- [ ] **4.1.4** Test: Load game and verify all weapons parse

### 4.2 Add effectTags to All Tools in items-tools-1.JSON
- [ ] **4.2.1** Open `items.JSON/items-tools-1.JSON`
- [ ] **4.2.2** For each tool that can be used in combat:
  - [ ] copper_axe: ["physical", "slashing", "single"], {"baseDamage": 15}
  - [ ] iron_axe: ["physical", "slashing", "single"], {"baseDamage": 20}
  - [ ] steel_axe: ["physical", "slashing", "single"], {"baseDamage": 25}
  - [ ] copper_pickaxe: ["physical", "piercing", "single"], {"baseDamage": 12}
  - [ ] iron_pickaxe: ["physical", "piercing", "single"], {"baseDamage": 18}
  - [ ] steel_pickaxe: ["physical", "piercing", "single"], {"baseDamage": 22}
  - [ ] pine_shortbow: ["physical", "piercing", "single"], {"baseDamage": 20}
  - [ ] (Any other bows found)
- [ ] **4.2.3** Test: Load game and verify all tools parse

### 4.3 Find and Update Any Other Weapon Files
- [ ] **4.3.1** Search for other JSON files with weapons:
  ```bash
  find . -name "items-*.JSON" -exec grep -l "weapon" {} \;
  ```
- [ ] **4.3.2** Update any additional weapons found
- [ ] **4.3.3** Test: Load game and verify all weapons parse

### 4.4 Add Special Geometry Tags to Appropriate Weapons
- [ ] **4.4.1** Identify weapons that should have AOE (battleaxe, warhammer)
- [ ] **4.4.2** Consider adding "cleaving" tag for potential multi-target
- [ ] **4.4.3** Update effectTags if needed:
  ```json
  "steel_battleaxe": {
    "effectTags": ["physical", "slashing", "single", "cleaving"]
  }
  ```
- [ ] **4.4.4** Test: Verify cleaving weapons work

### 4.5 Test Phase 4 Comprehensively
- [ ] **4.5.1** Create test script or manual test plan
- [ ] **4.5.2** Test 5 different weapon types:
  - [ ] Sword (slashing)
  - [ ] Spear (piercing)
  - [ ] Hammer (crushing)
  - [ ] Axe (slashing)
  - [ ] Bow (piercing, ranged)
- [ ] **4.5.3** Verify each shows correct tags
- [ ] **4.5.4** Verify training dummy categorizes tags correctly
- [ ] **4.5.5** Commit Phase 4 changes

---

## PHASE 5: Complete Turret/Trap/Bomb Coverage
**Time Estimate**: 6-8 hours
**Priority**: MEDIUM

### 5.1 Add effectTags to All Remaining Turrets
- [ ] **5.1.1** Open `items.JSON/items-engineering-1.JSON`
- [ ] **5.1.2** Verify turrets from Phase 2:
  - [ ] basic_arrow_turret (done in Phase 2)
  - [ ] fire_arrow_turret (done in Phase 2)
  - [ ] lightning_cannon (done in Phase 2)
  - [ ] flamethrower_turret (done in Phase 2)
  - [ ] laser_turret (done in Phase 2)
- [ ] **5.1.3** Test: All turrets load correctly

### 5.2 Add effectTags to All Traps
- [ ] **5.2.1** Continue in `items.JSON/items-engineering-1.JSON`
- [ ] **5.2.2** Add effectTags to `spike_trap`:
  ```json
  "effectTags": ["physical", "piercing", "circle"],
  "effectParams": {
    "baseDamage": 40,
    "circle_radius": 2.0
  }
  ```
- [ ] **5.2.3** Add effectTags to `frost_mine`:
  ```json
  "effectTags": ["ice", "circle", "freeze", "slow"],
  "effectParams": {
    "baseDamage": 30,
    "circle_radius": 3.0,
    "freeze_duration": 3.0,
    "freeze_slow_factor": 0.5
  }
  ```
- [ ] **5.2.4** Add effectTags to `bear_trap`:
  ```json
  "effectTags": ["physical", "crushing", "single", "root"],
  "effectParams": {
    "baseDamage": 50,
    "root_duration": 5.0
  }
  ```
- [ ] **5.2.5** Add effectTags to any other traps found
- [ ] **5.2.6** Test: All traps load correctly

### 5.3 Add effectTags to All Bombs
- [ ] **5.3.1** Continue in `items.JSON/items-engineering-1.JSON`
- [ ] **5.3.2** Add effectTags to `simple_bomb`:
  ```json
  "effectTags": ["physical", "circle"],
  "effectParams": {
    "baseDamage": 80,
    "circle_radius": 4.0
  }
  ```
- [ ] **5.3.3** Add effectTags to `fire_bomb`:
  ```json
  "effectTags": ["fire", "circle", "burn"],
  "effectParams": {
    "baseDamage": 100,
    "circle_radius": 5.0,
    "burn_duration": 8.0,
    "burn_damage_per_second": 10.0
  }
  ```
- [ ] **5.3.4** Add effectTags to `cluster_bomb`:
  ```json
  "effectTags": ["physical", "circle"],
  "effectParams": {
    "baseDamage": 120,
    "circle_radius": 6.0
  }
  ```
- [ ] **5.3.5** Test: All bombs load correctly

### 5.4 Update Trap Trigger System (If Needed)
- [ ] **5.4.1** Search for trap triggering code
- [ ] **5.4.2** Verify traps use effect_executor when triggered
- [ ] **5.4.3** If using legacy system, update to use tags
- [ ] **5.4.4** Test: Place trap, trigger it, verify tags used

### 5.5 Update Bomb Explosion System (If Needed)
- [ ] **5.5.1** Search for bomb explosion code
- [ ] **5.5.2** Verify bombs use effect_executor on explosion
- [ ] **5.5.3** If using legacy system, update to use tags
- [ ] **5.5.4** Test: Place bomb, explode it, verify tags used

### 5.6 Test Phase 5 Comprehensively
- [ ] **5.6.1** Test each turret type:
  - [ ] basic_arrow_turret (single target)
  - [ ] fire_arrow_turret (burn)
  - [ ] lightning_cannon (chain)
  - [ ] flamethrower_turret (cone)
  - [ ] laser_turret (beam)
- [ ] **5.6.2** Test each trap type:
  - [ ] spike_trap (circle AOE)
  - [ ] frost_mine (freeze)
  - [ ] bear_trap (root/stun)
- [ ] **5.6.3** Test each bomb type:
  - [ ] simple_bomb (explosion)
  - [ ] fire_bomb (burn)
  - [ ] cluster_bomb (large explosion)
- [ ] **5.6.4** Verify console output for all devices
- [ ] **5.6.5** Verify training dummy shows tags for all
- [ ] **5.6.6** Commit Phase 5 changes

---

## PHASE 6: Status Effect Tick System
**Time Estimate**: 2-3 hours
**Priority**: MEDIUM

### 6.1 Verify Enemy Status Effect Implementation
- [ ] **6.1.1** Read `entities/enemy.py` thoroughly
- [ ] **6.1.2** Check if status_effects dict exists
- [ ] **6.1.3** Check if apply_status_effect() exists
- [ ] **6.1.4** Check if update_status_effects() exists
- [ ] **6.1.5** If missing, implement from Phase 3 template
- [ ] **6.1.6** Test: Compile without errors

### 6.2 Add Status Effect Update to Combat Loop
- [ ] **6.2.1** Find main game loop in `core/game_engine.py`
- [ ] **6.2.2** Find where enemies are updated
- [ ] **6.2.3** Add status effect update:
  ```python
  # In update loop
  for enemy in self.active_enemies:
      if enemy.is_alive:
          enemy.update_status_effects(dt)
  ```
- [ ] **6.2.4** Test: Compile without errors

### 6.3 Add Status Effect Visual Display
- [ ] **6.3.1** Check if enemies have visual status indicators
- [ ] **6.3.2** If not, add simple text display above enemy:
  ```python
  if enemy.status_effects:
      # Draw status icons or text
      effects_text = ", ".join(enemy.status_effects.keys())
      # Render above enemy sprite
  ```
- [ ] **6.3.3** Test: Visual feedback shows

### 6.4 Verify TrainingDummy Status Effects
- [ ] **6.4.1** Read `systems/training_dummy.py`
- [ ] **6.4.2** Verify status_effects tracking exists (from Phase 3)
- [ ] **6.4.3** Verify update_status_effects() is called
- [ ] **6.4.4** Verify display shows active status effects
- [ ] **6.4.5** Test: Training dummy shows and updates status

### 6.5 Add Status Effect Types
- [ ] **6.5.1** Document all status effect types needed:
  - [ ] burning (fire damage over time)
  - [ ] frozen (slow movement, periodic damage)
  - [ ] shocked (periodic damage, chain to nearby)
  - [ ] poisoned (damage over time, increasing)
  - [ ] bleeding (physical damage over time)
  - [ ] slowed (movement speed reduction)
  - [ ] stunned (cannot act)
  - [ ] rooted (cannot move)
- [ ] **6.5.2** Implement special logic for each type (if needed)
- [ ] **6.5.3** Test: Each status type works

### 6.6 Test Phase 6 End-to-End
- [ ] **6.6.1** Apply Fire Aspect to weapon
- [ ] **6.6.2** Attack enemy (not dummy)
- [ ] **6.6.3** Verify enemy gets burning status
- [ ] **6.6.4** Verify enemy takes damage every second
- [ ] **6.6.5** Verify status expires after duration
- [ ] **6.6.6** Test with frost weapon (if available)
- [ ] **6.6.7** Verify frozen status slows enemy
- [ ] **6.6.8** Test with poison (if available)
- [ ] **6.6.9** Commit Phase 6 changes

---

## FINAL TESTING & CLEANUP
**Time Estimate**: 2-3 hours
**Priority**: CRITICAL

### 7.1 End-to-End Integration Test
- [ ] **7.1.1** Fresh game start
- [ ] **7.1.2** Craft weapon with tags
- [ ] **7.1.3** Craft turret with tags
- [ ] **7.1.4** Apply enchantment
- [ ] **7.1.5** Test complete combat flow:
  - [ ] Player attacks enemy with tagged weapon
  - [ ] Enchantment triggers (burning)
  - [ ] Status effect ticks and deals damage
  - [ ] Turret attacks enemy with tagged effects
  - [ ] Turret effects apply (cone, chain, etc.)
  - [ ] Training dummy shows all tag data
- [ ] **7.1.6** Verify NO legacy warnings
- [ ] **7.1.7** Document any remaining issues

### 7.2 Performance Testing
- [ ] **7.2.1** Spawn 10 enemies
- [ ] **7.2.2** Place 5 turrets
- [ ] **7.2.3** Attack with player
- [ ] **7.2.4** Verify no lag or frame drops
- [ ] **7.2.5** Check for memory leaks
- [ ] **7.2.6** Profile if needed

### 7.3 Edge Case Testing
- [ ] **7.3.1** Test weapon with no effectTags (should fallback gracefully)
- [ ] **7.3.2** Test turret with no effectTags (should use legacy)
- [ ] **7.3.3** Test weapon with empty effectTags array
- [ ] **7.3.4** Test invalid tag names (should ignore or warn)
- [ ] **7.3.5** Test missing effectParams (should use defaults)

### 7.4 Code Cleanup
- [ ] **7.4.1** Remove debug print statements (or gate behind debug flag)
- [ ] **7.4.2** Add docstrings to new methods
- [ ] **7.4.3** Format code consistently
- [ ] **7.4.4** Remove commented-out code
- [ ] **7.4.5** Check for TODOs and FIXMEs

### 7.5 Documentation Update
- [ ] **7.5.1** Update IMPLEMENTATION-STATUS.md with completion
- [ ] **7.5.2** Update SALVAGE-ANALYSIS.md with final status
- [ ] **7.5.3** Create INTEGRATION-COMPLETE.md summary
- [ ] **7.5.4** Update README.md if needed
- [ ] **7.5.5** Document known limitations

### 7.6 Final Commit & Push
- [ ] **7.6.1** Review all changes with git diff
- [ ] **7.6.2** Create comprehensive commit message
- [ ] **7.6.3** Commit all changes
- [ ] **7.6.4** Push to remote
- [ ] **7.6.5** Verify GitHub shows changes

---

## ROLLBACK PLAN (If Needed)

### Rollback Procedure
- [ ] **R.1** Identify commit hash before Phase 1 started
- [ ] **R.2** Create backup branch: `git branch backup-before-tag-integration`
- [ ] **R.3** If needed, revert: `git reset --hard <commit-hash>`
- [ ] **R.4** Document what went wrong
- [ ] **R.5** Plan fixes and retry

---

## SUCCESS CRITERIA

### Phase 1 Success
- ✅ Player attacks show tags in console
- ✅ Training dummy displays attack tags
- ✅ At least 5 weapons have effectTags
- ✅ No "legacy attack" warnings for player

### Phase 2 Success
- ✅ Turrets show tags when firing
- ✅ Training dummy displays turret attack tags
- ✅ At least 3 turrets have effectTags
- ✅ No "legacy attack" warnings for turrets with tags

### Phase 3 Success
- ✅ Fire Aspect applies burning status
- ✅ Training dummy shows active status effects
- ✅ Status effects tick and deal damage
- ✅ Status effects expire after duration

### Phase 4 Success
- ✅ All weapons have effectTags
- ✅ Different damage types work (slashing, piercing, crushing)
- ✅ All weapons show tags when attacking

### Phase 5 Success
- ✅ All turrets, traps, bombs have effectTags
- ✅ Different geometries work (single, circle, cone, chain, beam)
- ✅ All devices show tags when triggered

### Phase 6 Success
- ✅ Status effects tick on real enemies
- ✅ Visual indicators show status
- ✅ Multiple status types work
- ✅ Status effects expire correctly

### Overall Success
- ✅ NO legacy attack warnings anywhere
- ✅ All combat uses tag system
- ✅ Training dummy shows comprehensive tag data
- ✅ Enchantments trigger and work
- ✅ All devices use tags
- ✅ Game runs smoothly with no crashes

---

**Total Tasks**: 250+
**Estimated Time**: 21-28 hours
**Current Status**: Ready to begin
**Next Action**: Start Phase 1, Task 1.1.1
