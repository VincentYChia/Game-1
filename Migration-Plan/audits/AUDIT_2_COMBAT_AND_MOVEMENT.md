# Domain 2: Combat & Movement — Audit Report
**Date**: 2026-02-19
**Scope**: Player movement, attacks, damage pipeline, enchantments, status effects, enemy AI, spawning, skills, death system

---

## Executive Summary

**Status**: ~60% Implemented, ~30% Code Exists (Not Wired), ~10% Missing

The core combat math (damage pipeline, enemy AI states, status effects, tag system) is ported to C#, but the integration layer — input handling, attack triggering, movement collision, knockback, death/loot, and real-time combat execution — remains **unwired**. The migration has clean separation but lacks the MonoBehaviour connectors (Phase 6) that tie it all together.

---

## DETAILED FEATURE AUDIT

### 1. PLAYER MOVEMENT (WASD, Diagonals, Encumbrance Penalty, Collision)

**Python Source**: `core/game_engine.py` lines 6673-6703, `entities/character.py` lines 768-871

**Status**: ✅ **IMPLEMENTED & WIRED** (90%)

**What's Done**:
- ✅ `PlayerRenderer.cs` reads `InputManager.OnMoveInput` event
- ✅ Movement applied to `Character.Position` (XZ plane for 3D)
- ✅ Direction-based sprite facing ("up", "down", "left", "right")
- ✅ Diagonal movement normalized (0.7071 × speed)
- ✅ Basic BillboardSprite integration for 3D camera facing
- ✅ Movement speed stored in `Character.MovementSpeed`

**What's Missing**:
- ❌ **Encumbrance penalty** (Python: `character.get_encumbrance_speed_penalty()`) — not wired in C#
  - Need to call `Equipment.CalculateEncumbrance()` in movement
  - No penalty message when over-encumbered
- ❌ **Collision detection** — no walkability checks on terrain
  - `WorldSystem.IsWalkable()` exists but not called in movement
  - Can walk through mountains/water in current version
- ❌ **Movement blocking from status effects** — Python checks `status_manager.is_immobilized()`
  - Freeze/Stun/Root should prevent movement
- ❌ **Activity tracking** — not updating `StatTracker.RecordMovement()`

**Acceptance Criteria for Low-Fidelity**:
- [x] WASD/arrow keys move player in world space
- [ ] Diagonal movement feels responsive and not "sticky"
- [ ] Player can't move when frozen/stunned/rooted
- [ ] Movement speed reduced when over-encumbered
- [ ] Player can't walk through terrain/obstacles
- [ ] Facing direction updates as player moves

**Code Locations**:
- PlayerRenderer: `/home/user/Game-1/Unity/Assets/Scripts/Game1.Unity/World/PlayerRenderer.cs`
- Character: `/home/user/Game-1/Unity/Assets/Scripts/Game1.Entities/Character.cs`

---

### 2. ATTACK SYSTEM (Left-Click Mainhand, Right-Click/X Offhand, Per-Hand Cooldowns, Range, Tag Extraction)

**Python Source**: `core/game_engine.py` lines 6717-6812, `Combat/combat_manager.py` lines 684-982

**Status**: ⚠️ **CODE EXISTS, NOT WIRED** (40%)

**What's Done in C#**:
- ✅ `InputManager` has `OnPrimaryAttack` event (left-click)
- ✅ `InputManager` has `OnSecondaryAction` event (right-click)
- ✅ `DamageCalculator` class fully ported with complete damage pipeline
- ✅ Weapon tag extraction structure exists
- ✅ Per-hand cooldown fields in `Character` (`MainhandCooldown`, `OffhandCooldown`)

**What's NOT Done**:
- ❌ **No attack handler** — no MonoBehaviour subscribing to `OnPrimaryAttack`/`OnSecondaryAction`
- ❌ **Cooldown checking** — `Character.CanAttack()` exists but never called from input
- ❌ **Enemy target detection** — no raycasting/geometry to find enemy at click position
- ❌ **Cooldown reset** — `Character.ResetAttackCooldown()` exists but never called
- ❌ **Attack tag extraction** — weapon effect tags not pulled from JSON
- ❌ **Off-hand logic** — can't distinguish shield blocking from off-hand attacks
- ❌ **Weapon range checking** — `Equipment.GetWeaponRange()` exists but not used in range validation
- ❌ **Visual feedback** — no attack effect (slash animation, hit particle)
- ❌ **Damage number display** — no floating damage text

**Acceptance Criteria for Low-Fidelity**:
- [ ] Left-click attacks nearest enemy within weapon range
- [ ] Attack animations/effects appear (slash line or particle)
- [ ] Damage floats above enemy as number
- [ ] Mainhand and offhand have separate attack speeds
- [ ] Can't attack while stunned/frozen
- [ ] Shield blocks/X key works for offhand weapons
- [ ] Weapon range varies by weapon type

**Why It's Not Wired**:
The `InputManager` events are defined but **never subscribed to by a game system**. There's no `CombatInputHandler` or similar MonoBehaviour that:
1. Listens to `OnPrimaryAttack`
2. Raycasts to find target
3. Calls `DamageCalculator.CalculateDamage()`
4. Applies damage to enemy
5. Triggers visual effects

**Code Locations**:
- InputManager: `/home/user/Game-1/Unity/Assets/Scripts/Game1.Unity/Core/InputManager.cs`
- DamageCalculator: `/home/user/Game-1/Unity/Assets/Scripts/Game1.Systems/Combat/DamageCalculator.cs`
- CombatManager: `/home/user/Game-1/Unity/Assets/Scripts/Game1.Systems/Combat/CombatManager.cs`

---

### 3. SHIELD BLOCKING (Right-Mouse or X Key + Shield Equipped)

**Python Source**: `core/game_engine.py` lines 6717-6722

**Status**: ❌ **MISSING** (0%)

**What's Done**:
- ✅ `InputManager` has `OnSecondaryAction` event
- ✅ `Character.IsShieldActive()` method exists
- ✅ `Character.GetShieldDamageReduction()` calculates reduction %

**What's Missing**:
- ❌ **Block detection** — no input handler checking shield+right-click
- ❌ **Block visual** — no shield raise animation
- ❌ **Block state** — `Character.IsBlocking` property exists but never set
- ❌ **Damage reduction** — no code applying shield reduction to incoming damage
- ❌ **Counter requirement** — Python checks `X key + not blocking` for offhand; no equivalent

**Acceptance Criteria**:
- [ ] Right-click or X key while holding a shield raises shield
- [ ] Shield icon appears on screen while blocking
- [ ] Incoming damage reduced by shield defense value
- [ ] Can't block with two-handed weapon
- [ ] Movement possible while blocking (slower?)

**Why It's Missing**:
No `CombatInputHandler` exists to implement blocking logic. The feature is designed in Python but the input-to-game-state connection doesn't exist in C#.

---

### 4. DAMAGE PIPELINE (Base × Hand × STR × Skill × Class × Title × Crit - DEF, max 75%)

**Python Source**: `Combat/combat_manager.py` lines 684-982 (full damage formula)

**Status**: ✅ **FULLY PORTED TO C#** (100% code, needs testing)

**What's Done**:
- ✅ `DamageCalculator.CalculateDamage()` implements exact Python formula
- ✅ Damage breakdown tracking in `DamageBreakdown`
- ✅ All multipliers: STR (1.0 + STR×0.05), hand type (1.1-1.2), skill buffs, class affinity, title bonuses
- ✅ Critical hit calculation (2x damage)
- ✅ Defense reduction capped at 75%
- ✅ Weapon tag modifiers (crushing, precision, armor_breaker)
- ✅ Enemy-specific damage multipliers

**What Needs Wiring**:
- ⚠️ Method exists but never **called** from attack handler
- ⚠️ `DamageResult` never applied to enemy

**Critical Constants (MUST VERIFY)**:
```
STR Multiplier: 1.0 + STR * 0.05 ✓
Hand Type: 2H=1.2, versatile=1.1 ✓
Defense Cap: 75% ✓
Crit: 2x ✓
```

**Code Location**:
- `/home/user/Game-1/Unity/Assets/Scripts/Game1.Systems/Combat/DamageCalculator.cs`

---

### 5. ENCHANTMENT EFFECTS (14 Types: Sharpness, Protection, Fire Aspect, Poison, Lifesteal, Thorns, Knockback, etc.)

**Python Source**: `entities/components/equipment_manager.py`, embedded in equipment JSON

**Status**: ⚠️ **FRAMEWORK EXISTS, NO EXECUTION** (40%)

**What's Done**:
- ✅ Enchantment data models in equipment JSON
- ✅ Equipment parsing loads enchantments
- ✅ `EffectExecutor` framework for applying effects
- ✅ Tag system can theoretically trigger on-hit effects

**What's Missing**:
- ❌ **No enchantment trigger on attack** — never checks weapon enchantments when damage applied
- ❌ **No passive enchantments** — Sharpness/Protection (passive stat bonuses) not applied to stats
- ❌ **No on-hit effects** — Fire Aspect, Poison, Lifesteal, Knockback not triggered
- ❌ **Durability reduction** — no code reducing equipment durability on attack
- ❌ **Protection enchantment** — defense bonus not applied to character stats

**List of 14 Enchantments (Status)**:
1. ✅ **Sharpness I-III** — damage_multiplier — **CODE EXISTS, NOT APPLIED**
2. ✅ **Protection I-III** — defense_multiplier — **CODE EXISTS, NOT APPLIED**
3. ✅ **Efficiency I-II** — gathering_speed_multiplier — **CODE EXISTS, NOT APPLIED**
4. ✅ **Fortune I-II** — bonus_yield_chance — **CODE EXISTS, NOT APPLIED**
5. ✅ **Unbreaking I-II** — durability_multiplier — **CODE EXISTS, NOT APPLIED**
6. ❌ **Fire Aspect** — damage_over_time on hit — **MISSING TRIGGER**
7. ❌ **Poison** — damage_over_time on hit — **MISSING TRIGGER**
8. ❌ **Swiftness** — movement_speed_multiplier — **NOT APPLIED**
9. ❌ **Thorns** — reflect_damage on hit received — **MISSING TRIGGER**
10. ❌ **Knockback** — knockback on hit — **MISSING TRIGGER**
11. ❌ **Lifesteal** — lifesteal on hit — **MISSING TRIGGER**
12. ❌ **Health Regen** — health_regeneration — **NOT APPLIED TO CHARACTER**
13. ❌ **Frost Touch** — slow on hit — **MISSING TRIGGER**
14. ❌ **Chain Damage** — chain_damage on hit — **MISSING TRIGGER**

**Acceptance Criteria**:
- [ ] Sharpness adds damage to attacks
- [ ] Protection reduces incoming damage
- [ ] Lifesteal heals player on hit
- [ ] Fire Aspect applies burn status
- [ ] Knockback pushes enemies back
- [ ] Frost Touch slows enemies

---

### 6. STATUS EFFECTS (18 Types: DoT, CC, Buffs, Debuffs)

**Python Source**: `entities/status_effect.py`, `entities/status_manager.py`

**Status**: ✅ **FRAMEWORK PORTED** (70%), ⚠️ **NO TRIGGER SYSTEM**

**What's Done**:
- ✅ `StatusEffect` class ported to C#
- ✅ `StatusEffectType` enum with 18+ status types
- ✅ `StackingBehavior` system (Additive, Refresh, None)
- ✅ Duration tracking and update logic
- ✅ Per-status behavior (DamagePerSecond, PreventsMovement, etc.)

**What's Missing**:
- ❌ **No status manager attachment** — character doesn't have attached status manager
- ❌ **No damage application** — DoT effects exist but don't apply damage over time
- ❌ **No movement blocking** — Freeze/Stun/Root status exists but doesn't prevent movement
- ❌ **No effect trigger** — status effects never created from tag system
- ❌ **No mutual exclusions** — Burn/Freeze don't cancel each other
- ❌ **No visual feedback** — no burning animation, frozen overlay, etc.

**18 Status Effects**:
| Type | Category | Status |
|------|----------|--------|
| Burn | DoT | ✅ Structure, ❌ No trigger |
| Bleed | DoT | ✅ Structure, ❌ No trigger |
| Poison | DoT | ✅ Structure, ❌ No trigger |
| Shock | DoT | ✅ Structure, ❌ No trigger |
| Freeze | CC | ✅ Structure, ❌ Movement not blocked |
| Stun | CC | ✅ Structure, ❌ Action not blocked |
| Root | CC | ✅ Structure, ❌ Movement not blocked |
| Chill/Slow | CC | ✅ Structure, ❌ Speed not reduced |
| Empower | Buff | ✅ Structure, ❌ Damage not increased |
| Fortify | Buff | ✅ Structure, ❌ Defense not increased |
| Haste | Buff | ✅ Structure, ❌ Speed not increased |
| Regeneration | Buff | ✅ Structure, ❌ HP not healed |
| Shield | Buff | ✅ Structure, ❌ No absorption layer |
| Vulnerable | Debuff | ✅ Structure, ❌ Damage not increased |
| Weaken | Debuff | ✅ Structure, ❌ Damage not reduced |
| Phase/Ethereal | Special | ✅ Structure, ❌ Damage immunity not applied |
| Invisible | Special | ✅ Structure, ❌ No visual hiding |
| Shock (electric) | Utility | ✅ Structure, ❌ No stun mechanic |

**Acceptance Criteria**:
- [ ] Status effects appear visually (burning flame, frozen overlay)
- [ ] DoT effects apply damage each tick
- [ ] CC effects prevent movement/action
- [ ] Buff effects increase stats/speed
- [ ] Stacking rules enforced (additive vs refresh)
- [ ] Mutual exclusions prevent conflicting effects

---

### 7. ENEMY AI (State Machine: Idle, Patrol, Chase, Attack, Flee, Dead)

**Python Source**: `Combat/enemy.py` lines 21-30 (AIState enum), enemy.py full file

**Status**: ✅ **FRAMEWORK PORTED** (60%), ❌ **NO ACTIVE BEHAVIOR**

**What's Done**:
- ✅ `AIState` enum (Idle, Wander, Patrol, Guard, Chase, Attack, Flee, Dead, Corpse)
- ✅ `EnemyDefinition` class with AI pattern data
- ✅ `SpecialAbility` class for tag-based attacks
- ✅ Loot drop system with drop tables
- ✅ Enemy interface `ICombatEnemy` for damage application

**What's Missing**:
- ❌ **No AI update loop** — `UpdateAi()` method exists but never called
- ❌ **No state transitions** — enemy stays in Idle forever
- ❌ **No pathfinding** — chase/patrol don't move enemies
- ❌ **No aggro mechanics** — enemies don't detect player
- ❌ **No special abilities** — tag-based attacks never triggered
- ❌ **No enemy spawning** — no code creating Enemy instances
- ❌ **No loot generation** — drop tables never executed
- ❌ **No corpse management** — no timeout/removal of dead enemies

**Acceptance Criteria** (Low-Fidelity):
- [ ] Enemies visible as cubes/simple shapes in world
- [ ] Enemies detect player within aggro range
- [ ] Enemies chase player toward last known position
- [ ] Enemies attack when in melee range
- [ ] Enemies flee when health < 25% (configurable)
- [ ] Dead enemies fade out and disappear
- [ ] Loot drops appear on ground when enemy dies

---

### 8. ENEMY SPAWNING (Chunk-Based, Weighted Pools, Biome-Specific, Respawn Timers)

**Python Source**: `Combat/combat_manager.py` lines 195-451

**Status**: ⚠️ **FRAMEWORK PORTED, NOT INTEGRATED** (50%)

**What's Done**:
- ✅ `EnemySpawner` class with full spawning logic
- ✅ Safe zone protection (no spawns near origin)
- ✅ Weighted spawn pools by biome/danger level
- ✅ Tier-based enemy selection
- ✅ Spawn timer tracking

**What's Missing**:
- ❌ **No spawn triggering** — never called from game loop
- ❌ **No chunk loading** — doesn't know which chunks player is in
- ❌ **No enemy instance creation** — no code creating Enemy GameObjects
- ❌ **No respawn timers** — enemies don't respawn after death
- ❌ **No chunk templates** — biome/danger data not loaded

**Acceptance Criteria**:
- [ ] 1-4 enemies spawn per chunk as player moves
- [ ] More enemies in dangerous biomes
- [ ] Fewer enemies in peaceful zones
- [ ] Safe zone (15-tile radius) remains enemy-free
- [ ] Enemies respawn after 5+ minutes (configurable)
- [ ] Tier matches chunk danger level

---

### 9. CORPSE/LOOT SYSTEM (Corpse Lifetime, Loot Tables, Material Drops)

**Python Source**: `Combat/combat_manager.py` loot generation and corpse handling

**Status**: ❌ **PARTIALLY PORTED, NEEDS EXECUTION** (30%)

**What's Done**:
- ✅ `DropDefinition` class in `EnemyDefinition`
- ✅ `Enemy.GenerateLoot()` method exists (returns drops)
- ✅ Loot table in JSON (chance, quantity_min/max)

**What's Missing**:
- ❌ **No corpse cleanup** — corpses don't disappear
- ❌ **No loot pickup** — loot appears nowhere
- ❌ **No death chest** — no chest created on death
- ❌ **No soulbound filtering** — all items dropped regardless of binding
- ❌ **No item entity creation** — items don't appear as world objects

**Acceptance Criteria**:
- [ ] Corpse visible for 30 seconds after death
- [ ] Loot appears in/around corpse
- [ ] Loot auto-adds to inventory if room
- [ ] Soulbound items not dropped on player death
- [ ] Player death creates chest with remaining items
- [ ] Can move over loot to collect

---

### 10. TAG SYSTEM (190+ Tags, Geometry Types: Single, Chain, Cone, Circle, Beam, Pierce)

**Python Source**: `core/effect_executor.py`, `core/tag_parser.py`, `core/tag_system.py`

**Status**: ✅ **FULLY PORTED** (95%)

**What's Done**:
- ✅ `TagRegistry` with 190+ tags
- ✅ `TagParser` converts tag strings to `EffectConfig`
- ✅ `TargetFinder` handles geometry (single, chain, cone, circle, beam, pierce)
- ✅ `EffectExecutor` applies parsed effects
- ✅ All tag categories: damage types, geometry, status effects, special behaviors

**What's Missing**:
- ⚠️ **Not integrated with attacks** — never called from combat
- ❌ **No skill casting** — skills use tags but never execute them
- ❌ **No enemy special abilities** — tag-based abilities never trigger

**Geometry Types** (all ported):
- ✅ `single` — one target
- ✅ `chain` — jump to nearby enemies
- ✅ `cone` — sector effect
- ✅ `circle` — radial AoE
- ✅ `beam` — line from source
- ✅ `pierce` — line through targets

**Acceptance Criteria**:
- [ ] Skills with geometry affect multiple targets
- [ ] Chain damage bounces to nearby enemies
- [ ] Cone effect hits enemies in wedge
- [ ] Circle effect hits enemies in radius
- [ ] Beam hits all enemies in line
- [ ] Pierce damage stacks on each target

---

### 11. SKILLS (100+ Skills, Hotbar 5 Slots, Mana, Cooldowns, Affinity Bonuses)

**Python Source**: `entities/components/skill_manager.py`

**Status**: ⚠️ **COMPONENT PORTED, NO EXECUTION** (60%)

**What's Done**:
- ✅ `SkillManager` component with learn/equip/activate
- ✅ Hotbar slots (5 fixed slots)
- ✅ Skill requirements checking (level, stats, titles)
- ✅ Available skills computation with caching (FIX-7)
- ✅ Cooldown structure in `PlayerSkill`
- ✅ Mana cost checking

**What's Missing**:
- ❌ **No skill activation** — `ActivateSkill()` exists but never called
- ❌ **No mana consumption** — mana costs never applied
- ❌ **No cooldown enforcement** — cooldowns never reset
- ❌ **No effect execution** — tag system never invoked for skills
- ❌ **No visual feedback** — skill activation has no animation/effect
- ❌ **No hotbar input** — keys 1-5 never trigger skills

**Acceptance Criteria**:
- [ ] Player can equip skills to hotbar (1-5 keys)
- [ ] Hotbar UI shows equipped skills
- [ ] 1-5 keys activate equipped skill
- [ ] Mana cost deducted on use
- [ ] Cooldown prevents re-use for duration
- [ ] Skill effect applies tags to targets

---

### 12. TURRET SYSTEM (Player-Placed Turrets, Auto-Targeting, Damage)

**Python Source**: `systems/turret_system.py`

**Status**: ⚠️ **FRAMEWORK PORTED, NOT SPAWNED** (50%)

**What's Done**:
- ✅ Turret placement in `PlacedEntity`
- ✅ Turret targeting logic (`_find_nearest_enemy()`)
- ✅ Attack cooldown per turret
- ✅ Range checking

**What's Missing**:
- ❌ **No turret placement from UI** — engineer minigame doesn't create turrets
- ❌ **No spawn into world** — turrets never appear
- ❌ **No damage application** — attacks never dealt
- ❌ **No special abilities** — turret abilities not executed
- ❌ **No visual feedback** — no attack effect

**Acceptance Criteria**:
- [ ] Turrets appear as placeable items in inventory
- [ ] Player can place turrets on ground
- [ ] Turrets auto-target nearby enemies
- [ ] Turrets fire and deal damage
- [ ] Turrets have limited lifetime (set in engineering)
- [ ] Visual effect shows turret firing

---

### 13. TRAINING DUMMY (Test Target for Damage)

**Python Source**: `systems/training_dummy.py`

**Status**: ✅ **FRAMEWORK EXISTS, NOT SPAWNABLE** (50%)

**What's Done**:
- ✅ `TrainingDummy` class inherits from `Enemy`
- ✅ 10,000 HP for durability
- ✅ Detailed damage reporting
- ✅ No aggro/attack
- ✅ Auto-reset at 10% health

**What's Missing**:
- ❌ **No spawn mechanism** — no command to create dummy
- ❌ **No debug integration** — F key not bound to dummy spawn
- ❌ **No UI display** — no damage readout shown

**Acceptance Criteria**:
- [ ] F key or debug command spawns training dummy
- [ ] Dummy takes all damage types
- [ ] Damage numbers displayed clearly
- [ ] Dummy resets health if dropped to 10%

---

### 14. KNOCKBACK (Velocity-Based Forced Movement)

**Python Source**: `entities/character.py` lines 88-91, status effects (Knockback)

**Status**: ⚠️ **STRUCTURE PORTED, NO TRIGGER** (40%)

**What's Done**:
- ✅ `Character` has `KnockbackVelocityX`, `KnockbackVelocityZ`, `KnockbackDurationRemaining`
- ✅ Data structures match Python exactly

**What's Missing**:
- ❌ **No knockback application** — no code calling `ApplyKnockback()`
- ❌ **No knockback update loop** — no code reducing duration and moving character
- ❌ **No enchantment trigger** — Knockback enchantment never applied
- ❌ **No status effect trigger** — knockback status never created

**Acceptance Criteria**:
- [ ] Enemy attacks with knockback tag push player back
- [ ] Knockback duration visible (player continues sliding)
- [ ] Movement during knockback is reduced
- [ ] Knockback respects terrain collisions

---

### 15. DEATH HANDLING (Death Chests, Item Drops, Respawn at Spawn, Keep-Inventory Toggle F5)

**Python Source**: `entities/character.py` lines 1849-1920

**Status**: ❌ **NOT PORTED** (0%)

**What's Missing**:
- ❌ **No death detection** — no code checking `Character.IsAlive`
- ❌ **No death chest creation** — no chest spawned at death location
- ❌ **No item dropping** — inventory items don't fall out
- ❌ **No respawn** — player doesn't teleport to spawn
- ❌ **No soulbound filtering** — soulbound items should be kept
- ❌ **No keep-inventory toggle** — F5 key not implemented
- ❌ **No death UI** — death screen not shown

**Acceptance Criteria**:
- [ ] Player death creates chest with non-soulbound items
- [ ] Player respawns at spawn location
- [ ] Soulbound equipment kept on death
- [ ] F5 toggles keep-inventory mode (admin)
- [ ] Death UI shows death message and respawn timer

---

### 16. ATTACK EFFECTS (Visual Slash/Impact Effects)

**Python Source**: `systems/attack_effects.py`

**Status**: ⚠️ **STRUCTURE PORTED, NO RENDERING** (40%)

**What's Done**:
- ✅ `AttackEffect` class ported
- ✅ Effect types (LINE, BLOCKED, HIT_PARTICLE, AREA)
- ✅ Color coding by source (PLAYER=blue, TURRET=cyan, ENEMY=red)
- ✅ Duration/alpha fade tracking

**What's Missing**:
- ❌ **No effect triggering** — never created on attack
- ❌ **No rendering** — effects not drawn
- ❌ **AttackEffectRenderer** exists but not integrated
- ❌ **No slash animation** — no line drawn from attacker to target
- ❌ **No hit particle** — no impact visual at target

**Acceptance Criteria**:
- [ ] Blue line appears from player to enemy on attack
- [ ] Red line appears from enemy to player on attack
- [ ] Particle effects at impact location
- [ ] X mark shown for blocked attacks
- [ ] Circle effect shown for AoE attacks
- [ ] Effects fade out over 0.3 seconds

---

### 17. DAMAGE NUMBERS (Floating Text, Crit Coloring)

**Python Source**: `entities/damage_number.py`, renderer.py rendering code

**Status**: ❌ **STRUCTURE PORTED, NOT RENDERED** (30%)

**What's Done**:
- ✅ `DamageNumber` dataclass with position, value, is_crit
- ✅ Lifetime tracking
- ✅ Y velocity for floating effect

**What's Missing**:
- ❌ **No damage number creation** — never instantiated on damage
- ❌ **DamageNumberRenderer** exists but not triggered
- ❌ **No text rendering** — numbers not drawn
- ❌ **No color coding** — crit vs normal not distinguished
- ❌ **No position tracking** — numbers don't move with target

**Acceptance Criteria**:
- [ ] Damage number appears above target on hit
- [ ] White text for normal damage
- [ ] Yellow/gold text for critical hits
- [ ] Numbers float up and fade out
- [ ] Numbers disappear after 1 second

---

## SUMMARY TABLE

| Feature | Lines Python | C# Status | Wired? | Blocking? |
|---------|-------------|----------|--------|-----------|
| **Movement** | 6673-6703, 768-871 | 90% | ✅ Mostly | Collision, Encumbrance |
| **Attacks** | 6717-6812, 684-982 | 40% | ❌ No | **CRITICAL** |
| **Blocking** | 6717-6722 | 0% | ❌ No | **CRITICAL** |
| **Damage Pipeline** | 684-982 | 100% | ❌ No | Needs wiring |
| **Enchantments** | Equipment JSON | 40% | ❌ No | **CRITICAL** |
| **Status Effects** | status_*.py | 70% | ❌ No | **CRITICAL** |
| **Enemy AI** | enemy.py | 60% | ❌ No | **CRITICAL** |
| **Enemy Spawning** | 195-451 | 50% | ❌ No | **CRITICAL** |
| **Corpse/Loot** | 700-1000 | 30% | ❌ No | Quality-of-life |
| **Tag System** | effect_executor.py | 95% | ⚠️ Partial | Needs skill integration |
| **Skills** | skill_manager.py | 60% | ❌ No | **CRITICAL** |
| **Turrets** | turret_system.py | 50% | ❌ No | Quality-of-life |
| **Training Dummy** | training_dummy.py | 50% | ❌ No | Debug only |
| **Knockback** | character.py | 40% | ❌ No | Nice-to-have |
| **Death** | character.py | 0% | ❌ No | **CRITICAL** |
| **Attack Effects** | attack_effects.py | 40% | ❌ No | Visual feedback |
| **Damage Numbers** | damage_number.py | 30% | ❌ No | Visual feedback |

---

## CRITICAL BLOCKERS (Must Implement Before Beta)

1. **❌ Attack Input Handler** (CombatInputHandler missing)
   - Subscribe to `InputManager.OnPrimaryAttack`/`OnSecondaryAction`
   - Raycast to find enemy at click position
   - Call `DamageCalculator.CalculateDamage()`
   - Apply damage to enemy via `Enemy.TakeDamage()`
   
2. **❌ Enemy Spawning Integration** (EnemySpawner not called)
   - Wire `EnemySpawner` into game loop
   - Create `Enemy` GameObjects with `EnemyRenderer`
   - Call `UpdateAi()` on active enemies each frame
   
3. **❌ Status Effect Application** (StatusManager not triggered)
   - Attach status manager to `Character` and `Enemy`
   - Trigger status effects from `EffectExecutor`
   - Apply DoT damage each tick
   - Enforce movement/action blocking
   
4. **❌ Skill Activation** (Skills never triggered)
   - Wire hotbar keys (1-5) to `SkillManager.ActivateSkill()`
   - Apply mana cost and cooldown
   - Execute skill via `EffectExecutor`
   
5. **❌ Death System** (No respawn)
   - Detect character death
   - Create death chest with inventory
   - Teleport to spawn location
   - Clear inventory

---

## RECOMMENDED IMPLEMENTATION ORDER (Low-Fidelity 3D)

For the fastest path to a playable low-fidelity version with enemies as cubes:

1. **Phase 1**: Create `CombatInputHandler` MonoBehaviour
   - Subscribe to input events
   - Implement basic melee attack with radius check
   - Apply damage via `DamageCalculator`

2. **Phase 2**: Integrate `EnemySpawner`
   - Wire into `GameManager.Update()`
   - Create `Enemy` instances
   - Wire `UpdateAi()` into game loop

3. **Phase 3**: Add `StatusEffectManager` to entities
   - Trigger from effect executor
   - Apply DoT each frame
   - Enforce immobilization

4. **Phase 4**: Implement visual feedback
   - `AttackEffectRenderer` for slash lines
   - `DamageNumberRenderer` for floating text
   - Corpse fade-out

5. **Phase 5**: Skills + hotbar activation
   - Wire keys 1-5
   - Execute via `EffectExecutor`

6. **Phase 6**: Death system
   - Respawn at spawn
   - Create death chest
   - Clear inventory

---

## ACCEPTANCE CRITERIA FOR LOW-FIDELITY VERSION

**Minimum viable combat** (playable alpha):
- [x] Player moves with WASD
- [ ] Left-click attacks enemies
- [ ] Enemies visible as simple shapes
- [ ] Enemies move toward player
- [ ] Damage numbers appear above enemies
- [ ] Status effects apply (burn, freeze)
- [ ] Player can die and respawn
- [ ] Loot appears on ground

**Nice-to-have** (polish):
- [ ] Shield blocking
- [ ] Knockback
- [ ] Enchantment bonuses
- [ ] Turret placement
- [ ] Training dummy

---

## CODE QUALITY NOTES

**Strengths**:
- Clean separation of concerns (Math/Logic vs MonoBehaviours)
- All Python formulas accurately ported
- Well-structured interfaces for loose coupling

**Weaknesses**:
- Missing "glue layer" — Phase 6 integration layer underdeveloped
- No central `CombatSystem` MonoBehaviour to orchestrate
- Input events defined but no listeners
- Game loop incomplete (no update for enemy AI, status effects)

---

**Report Generated**: 2026-02-19  
**Auditor Notes**: The migration has good bones but is "headless" — all the game logic exists but the input→game-state→output pipeline is disconnected. A focused 1-week push on Phase 6 MonoBehaviour wiring would unlock the entire combat system.