# Unified Testing System Plan

**Created**: 2025-12-30
**Status**: Planning
**Priority**: Medium (improves development velocity)

---

## Overview

This document outlines a comprehensive testing system for Game-1, designed to:
1. Test all tag-based mechanics in isolation
2. Provide a creative mode testing bed
3. Detect hidden errors (false math, silent failures)
4. Speed up testing vs manual playtesting

---

## PART 1: Tag Testing Framework

### 1.1 Architecture

```
tests/
    tag_tests/
        __init__.py
        test_runner.py           # Main test orchestrator
        test_damage_tags.py      # physical, fire, frost, etc.
        test_status_tags.py      # burn, freeze, stun, slow, etc.
        test_geometry_tags.py    # single, chain, cone, circle, beam, pierce
        test_mechanic_tags.py    # lifesteal, knockback, execute, etc.
        test_enchantment_tags.py # All enchantment effects
        test_turret_tags.py      # Turret attacks and status effects
        fixtures/
            mock_character.py    # Minimal character for testing
            mock_enemy.py        # Minimal enemy for testing
            mock_combat.py       # Combat simulation without rendering
```

### 1.2 Tag Test Categories

#### A. Damage Tags
| Tag | Test | Expected Outcome |
|-----|------|------------------|
| `physical` | Apply 100 base damage | Enemy HP reduced by 100 (modified by defense) |
| `fire` | Apply 100 fire damage | HP reduced, check fire resistance |
| `frost` | Apply 100 frost damage | HP reduced, check frost resistance |
| `lightning` | Apply 100 lightning damage | HP reduced |
| `poison` | Apply 100 poison damage | HP reduced |
| `holy` | Apply 100 holy damage | HP reduced |
| `shadow` | Apply 100 shadow damage | HP reduced |
| `arcane` | Apply 100 arcane damage | HP reduced |
| `chaos` | Apply 100 chaos damage | HP reduced (ignores resistances) |

#### B. Status Effect Tags
| Tag | Test | Expected Outcome |
|-----|------|------------------|
| `burn` | Apply burn, wait 3 seconds | Enemy takes 3 ticks of fire DoT |
| `freeze` | Apply freeze | Enemy movement = 0, cannot attack |
| `slow` | Apply 50% slow | Enemy movement *= 0.5 |
| `stun` | Apply stun | Enemy cannot act for duration |
| `poison_status` | Apply poison | Enemy takes poison DoT over time |
| `bleed` | Apply bleed | Enemy takes physical DoT |
| `root` | Apply root | Enemy cannot move but can attack |
| `vulnerable` | Apply vulnerable | Enemy takes 25% more damage |
| `weaken` | Apply weaken | Enemy deals 25% less damage |

#### C. Geometry Tags
| Tag | Test | Expected Outcome |
|-----|------|------------------|
| `single` | Attack single target | Only 1 enemy hit |
| `chain` | Attack with chain:3 | Up to 3 enemies hit in chain |
| `cone` | Attack in 60° cone | Enemies in cone hit |
| `circle` | Attack in radius | All enemies in radius hit |
| `beam` | Attack in line | All enemies in line hit |
| `pierce` | Attack with pierce | Hits through multiple enemies |

#### D. Mechanic Tags
| Tag | Test | Expected Outcome |
|-----|------|------------------|
| `lifesteal` | Deal 100 damage with 10% lifesteal | Player healed 10 HP |
| `knockback` | Apply knockback | Enemy position moved away |
| `pull` | Apply pull | Enemy position moved toward |
| `teleport` | Apply teleport | Entity position changed |
| `execute` | Attack at <20% HP | Bonus damage or instant kill |
| `critical` | Force crit | Damage multiplied by crit multiplier |

### 1.3 Test Output Format

```python
class TagTestResult:
    tag_name: str
    passed: bool
    expected_value: float
    actual_value: float
    error_margin: float  # Acceptable difference
    debug_log: List[str]  # Step-by-step calculation trace

# Example output:
# [PASS] physical: Expected 100 damage, got 100.0 (defense=0)
# [FAIL] lifesteal: Expected 10 HP heal, got 0.0 (lifesteal not triggering!)
#        Debug: damage=100, lifesteal_percent=0.1, heal_amount=0
#        Error: heal_amount calculation returned 0, character.health not updated
```

### 1.4 Debug Instrumentation

Add debug logging to critical combat functions:

```python
# In combat_manager.py
def _apply_damage(self, source, target, damage, tags, debug=False):
    debug_log = []
    if debug:
        debug_log.append(f"Base damage: {damage}")
        debug_log.append(f"Tags: {tags}")

    # Calculate resistances
    for tag in tags:
        if tag in target.resistances:
            resistance = target.resistances[tag]
            damage *= (1.0 - resistance)
            if debug:
                debug_log.append(f"  {tag} resistance {resistance*100}%: damage now {damage}")

    # ... rest of damage calculation

    if debug:
        debug_log.append(f"Final damage: {damage}")
        return damage, debug_log
    return damage
```

---

## PART 2: Creative Mode Testing Bed

### 2.1 Features

| Feature | Hotkey | Description |
|---------|--------|-------------|
| Toggle God Mode | `F2` | Invincibility + infinite resources |
| Spawn Enemy Menu | `F3` | Opens enemy spawn selector |
| Spawn All Enemies | `Shift+F3` | Spawns one of each enemy type |
| Spawn Resource Menu | `F4` | Opens resource node spawner |
| Spawn All Resources | `Shift+F4` | Spawns one of each resource type |
| Spawn Crafting Stations | `F5` | Places all T4 crafting stations nearby |
| Give All Items | `F6` | Fills inventory with all item types |
| Level Up | `+` | Instantly gain a level |
| Level Down | `-` | Lose a level |
| Teleport | `T + Click` | Teleport to clicked position |
| Kill All Enemies | `K` | Kill all active enemies |
| Reset World | `Ctrl+R` | Regenerate world state |

### 2.2 Spawn Menu UI

```
┌─────────────────────────────────────┐
│ ENEMY SPAWNER (F3)                  │
├─────────────────────────────────────┤
│ [Tier 1]  [Tier 2]  [Tier 3]  [T4]  │
├─────────────────────────────────────┤
│ ○ Slime           ○ Orc             │
│ ○ Goblin          ○ Troll           │
│ ○ Skeleton        ○ Mage            │
│ ○ Spider          ○ ...             │
├─────────────────────────────────────┤
│ Quantity: [1] [5] [10] [25]         │
│ [SPAWN AT CURSOR] [SPAWN ALL]       │
└─────────────────────────────────────┘
```

### 2.3 Implementation Location

```python
# New file: core/debug_mode.py

class DebugMode:
    def __init__(self, game_engine):
        self.engine = game_engine
        self.enabled = False
        self.spawn_menu_open = False
        self.resource_menu_open = False

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.engine.add_notification("DEBUG MODE ENABLED", (255, 200, 0))
            self._apply_debug_state()

    def _apply_debug_state(self):
        # Infinite resources (already exists via F1)
        Config.DEBUG_INFINITE_RESOURCES = True
        # God mode
        self.engine.character.invincible = True

    def spawn_enemy(self, enemy_id: str, position: Tuple[float, float], count: int = 1):
        """Spawn enemy(s) at position"""
        from Combat.enemy import EnemyDatabase
        enemy_db = EnemyDatabase.get_instance()
        for _ in range(count):
            enemy_def = enemy_db.get_enemy(enemy_id)
            if enemy_def:
                self.engine.combat_manager.spawn_enemy(enemy_def, position)

    def spawn_all_enemies(self, position: Tuple[float, float]):
        """Spawn one of each enemy type near position"""
        from Combat.enemy import EnemyDatabase
        enemy_db = EnemyDatabase.get_instance()
        offset = 0
        for enemy_id in enemy_db.get_all_enemy_ids():
            spawn_pos = (position[0] + (offset % 5) * 3, position[1] + (offset // 5) * 3)
            self.spawn_enemy(enemy_id, spawn_pos, 1)
            offset += 1

    def spawn_crafting_stations(self, center: Tuple[float, float]):
        """Place all T4 crafting stations in a grid"""
        stations = [
            ("forge_t4", (-3, -3)),
            ("refinery_t4", (0, -3)),
            ("alchemy_table_t4", (3, -3)),
            ("engineering_bench_t4", (-3, 0)),
            ("enchanting_table_t4", (0, 0)),
        ]
        for station_id, offset in stations:
            pos = (center[0] + offset[0], center[1] + offset[1])
            self.engine.world.place_crafting_station(station_id, pos)

    def give_all_items(self):
        """Fill inventory with examples of all items"""
        from data.databases.material_db import MaterialDatabase
        from data.databases.equipment_db import EquipmentDatabase
        mat_db = MaterialDatabase.get_instance()
        eq_db = EquipmentDatabase.get_instance()

        # Give materials (stack of 99 each)
        for mat_id in mat_db.get_all_material_ids()[:20]:  # First 20
            self.engine.character.inventory.add_item(mat_id, 99)

        # Give equipment (1 each)
        for eq_id in eq_db.get_all_equipment_ids()[:10]:  # First 10
            self.engine.character.inventory.add_equipment(eq_id)
```

### 2.4 Existing Debug Mode Extension

Current `F1` debug mode already provides:
- Infinite materials for crafting
- Level 30 + 100 stat points
- No material requirements
- Instant resource respawn
- Infinite durability

**Extend with**:
- F2: Full debug/creative mode toggle
- F3-F6: Spawn menus and utilities
- Visual indicator showing debug state

---

## PART 3: Automated Test Runner

### 3.1 Test Suite Structure

```python
# tests/run_all_tests.py

def run_all_tests():
    results = []

    # Unit tests (no game state)
    results.extend(run_tag_damage_tests())
    results.extend(run_tag_status_tests())
    results.extend(run_tag_geometry_tests())
    results.extend(run_enchantment_tests())

    # Integration tests (mock game state)
    results.extend(run_combat_integration_tests())
    results.extend(run_crafting_tests())
    results.extend(run_save_load_tests())

    # Report
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print(f"\n{'='*50}")
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}")

    for r in results:
        if not r.passed:
            print(f"\n[FAIL] {r.test_name}")
            print(f"  Expected: {r.expected}")
            print(f"  Actual: {r.actual}")
            for line in r.debug_log:
                print(f"  {line}")
```

### 3.2 Running Tests

```bash
# Run all tests
python -m tests.run_all_tests

# Run specific category
python -m tests.run_all_tests --category=damage_tags

# Run with verbose debug output
python -m tests.run_all_tests --verbose

# Run single test
python -m tests.tag_tests.test_damage_tags --test=fire_damage
```

---

## PART 4: Implementation Phases

### Phase 1: Core Testing Infrastructure (4-6 hours)
- [ ] Create `tests/` directory structure
- [ ] Implement `TagTestResult` class
- [ ] Create mock character/enemy fixtures
- [ ] Implement basic test runner

### Phase 2: Tag Tests (6-8 hours)
- [ ] Damage tag tests (9 tags)
- [ ] Status effect tag tests (10 effects)
- [ ] Geometry tag tests (6 geometries)
- [ ] Mechanic tag tests (6 mechanics)

### Phase 3: Debug Mode Extensions (4-6 hours)
- [ ] Create `core/debug_mode.py`
- [ ] Implement spawn menus
- [ ] Add F2-F6 hotkeys
- [ ] Create spawn UI

### Phase 4: Integration Tests (4-6 hours)
- [ ] Combat flow tests
- [ ] Crafting system tests
- [ ] Save/load validation tests
- [ ] Enchantment application tests

---

## PART 5: Debug Instrumentation Points

Key locations to add debug logging:

| File | Function | Debug Points |
|------|----------|--------------|
| `combat_manager.py` | `_calculate_damage()` | Base damage, modifiers, final damage |
| `combat_manager.py` | `_apply_status_effect()` | Effect type, duration, params |
| `effect_executor.py` | `execute_effect()` | Tag processing, target selection |
| `effect_executor.py` | `_apply_lifesteal()` | Damage dealt, heal amount |
| `effect_executor.py` | `_apply_knockback()` | Force, direction, distance |
| `character.py` | `take_damage()` | Incoming damage, reductions |
| `character.py` | `apply_status()` | Status type, stacking behavior |
| `turret_system.py` | `_turret_attack()` | Target, damage, effects |

### Debug Flag Pattern

```python
# Global debug flag
import os
DEBUG_COMBAT = os.environ.get('DEBUG_COMBAT', 'false').lower() == 'true'

def calculate_damage(base, modifiers):
    if DEBUG_COMBAT:
        print(f"[DEBUG] calculate_damage: base={base}, modifiers={modifiers}")

    result = base
    for mod in modifiers:
        result *= mod
        if DEBUG_COMBAT:
            print(f"[DEBUG]   Applied modifier {mod}: result={result}")

    return result
```

---

## Summary

This testing system will provide:

1. **Comprehensive Tag Coverage**: Every tag tested in isolation
2. **Debug Instrumentation**: Step-by-step calculation tracing
3. **Creative Mode**: Fast testing without grinding
4. **Spawn Controls**: Test specific scenarios on demand
5. **Automated Validation**: CI-friendly test suite
6. **Error Detection**: Silent failure and math error catching

**Estimated Total Effort**: 18-26 hours

**Recommended Priority Order**:
1. Phase 1 (infrastructure) - Required foundation
2. Phase 3 (debug mode) - Immediate playtesting benefit
3. Phase 2 (tag tests) - Validation coverage
4. Phase 4 (integration) - Regression prevention

---

**Next Steps**:
1. Create `tests/` directory structure
2. Implement basic test runner
3. Add F2 creative mode toggle
4. Build spawn menu UI
