# Phase 3: Implementation Preparation

**Status:** Ready to Begin
**Estimated Duration:** 2-3 weeks

---

## What We Have (Phase 2 Complete)

✅ 80+ functional tags defined with parameters
✅ Context-aware behavior specified
✅ Combination rules documented
✅ Migration guide with examples
✅ Quick reference (TAG-REFERENCE.md)
✅ Conflict resolution rules
✅ Default parameters

---

## What We Need (Phase 3 Tasks)

### Week 1: Foundation Systems

**1. Effect Registry (`Game-1-modular/core/effect_registry.py`)**
```python
class EffectRegistry:
    """Maps tag names to effect executor functions"""
    def register(tag: str, executor: Callable)
    def get_executor(tag: str) -> Callable
    def execute_tag(tag: str, context: EffectContext)
```

**2. Tag Parser (`Game-1-modular/core/tag_parser.py`)**
```python
class TagParser:
    """Parse tags from JSON and categorize"""
    def parse(tags: List[str], params: dict) -> EffectConfig
    def categorize_tags(tags) -> Dict[str, List[str]]
    def resolve_conflicts(tags) -> str  # geometry priority
    def infer_context(tags, effect_type) -> str
```

**3. Effect Context (`Game-1-modular/core/effect_context.py`)**
```python
@dataclass
class EffectContext:
    source: Entity
    primary_target: Entity
    tags: List[str]
    params: dict
    timestamp: float
```

**4. Debug Logger (`Game-1-modular/core/tag_debug.py`)**
```python
class TagDebugger:
    def log_effect(context: EffectContext)
    def log_conflict(tags: List[str], resolution: str)
    def log_context_mismatch(tag: str, target: Entity)
```

---

### Week 2: Geometry Systems

**1. Target Finder (`Game-1-modular/core/geometry/target_finder.py`)**
```python
def find_chain_targets(source, initial_target, count, range, exclude) -> List[Entity]
def find_cone_targets(source, angle, range, context) -> List[Entity]
def find_circle_targets(center, radius, context, max_targets) -> List[Entity]
def find_beam_targets(source, direction, range, width) -> List[Entity]
def is_valid_target(entity, context) -> bool
```

**2. Geometry Utils (`Game-1-modular/core/geometry/math_utils.py`)**
```python
def calculate_distance(pos1, pos2) -> float
def normalize(vector) -> Vector
def dot(v1, v2) -> float
def angle_between(v1, v2) -> float
def is_in_cone(point, cone_origin, cone_dir, angle, range) -> bool
```

**3. Chain Calculator**
- Find nearest valid target from last hit
- Track already-hit targets (no double-hit)
- Apply falloff per jump
- Context-aware (enemies vs allies)

**4. Cone Calculator**
- Get facing direction from source
- Calculate angle to each nearby entity
- Filter by cone angle and range

**5. Circle Calculator**
- Distance check from center
- Sort by distance
- Apply max_targets limit

---

### Week 3: Status Effect System

**1. Status Effect Manager (`Game-1-modular/entities/status_manager.py`)**
```python
class StatusEffectManager:
    def __init__(self, owner: Entity):
        self.active_statuses: Dict[str, StatusEffect] = {}

    def apply_status(status_type: str, params: dict)
    def remove_status(status_type: str)
    def update(dt: float)
    def has_status(status_type: str) -> bool
    def get_status(status_type: str) -> StatusEffect
```

**2. Status Effect Base (`Game-1-modular/entities/status_effect.py`)**
```python
@dataclass
class StatusEffect:
    status_type: str
    duration: float
    remaining: float
    params: dict

    def update(dt: float, owner: Entity) -> bool  # returns False to remove
    def on_apply(owner: Entity)
    def on_remove(owner: Entity)
```

**3. Individual Status Effects**
- `BurnEffect` - DoT with tick rate
- `FreezeEffect` - Movement lock
- `SlowEffect` - Speed multiplier
- `StunEffect` - Action disable
- `BleedEffect` - Physical DoT
- `PoisonEffect` - Poison DoT (immunity checks)
- `RegenerationEffect` - Healing over time
- `ShieldEffect` - Damage absorption

**4. Mutual Exclusion Rules**
```python
MUTUALLY_EXCLUSIVE = {
    'burn': ['freeze'],
    'freeze': ['burn']
}
```

**5. Stacking Rules**
```python
STACKING_RULES = {
    'burn': 'additive',      # Multiple burns stack
    'slow': 'multiplicative', # Slows multiply
    'freeze': 'no_stack',    # Only one freeze
    'shield': 'no_stack'     # Only one shield
}
```

---

### Week 4: Integration

**1. Update Turret System (`systems/turret_system.py`)**

Current:
```python
def _attack_enemy(self, turret, enemy):
    enemy.current_health -= turret.damage
```

New:
```python
def _attack_enemy(self, turret, enemy):
    # Load turret tags from item definition
    item_def = equipment_db.get_item(turret.item_id)
    tags = item_def.tags
    params = item_def.effectParams

    # Parse and execute
    effect_config = tag_parser.parse(tags, params)
    execute_effect(turret, enemy, effect_config)
```

**2. Update Combat System (`Combat/combat_manager.py`)**
- Replace hardcoded damage with tag system
- Apply status effects from tags
- Handle geometry (AOE attacks)

**3. Update Equipment Manager (`entities/components/equipment_manager.py`)**
- Already handles 1H/2H/versatile
- No changes needed (already tag-based)

**4. Update Skill System (`entities/components/skill_manager.py`)**

Current:
```python
def _apply_skill_effect(self, skill_def, character, player_skill):
    effect = skill_def.effect
    # Hardcoded effect types
```

New:
```python
def _apply_skill_effect(self, skill_def, character, player_skill):
    tags = skill_def.tags
    params = skill_def.effectParams

    effect_config = tag_parser.parse(tags, params)
    execute_effect(character, target, effect_config)
```

**5. Hostile Ability System (NEW)**
- Create `systems/ability_system.py`
- Load abilities from `Definitions.JSON/ability-definitions.JSON`
- Execute abilities using tag system

---

## Missing Pieces Identified

### 1. Visual Effects System
Not defined in Phase 2. Need to specify:
- How to trigger particle effects
- Cone/circle ground indicators
- Chain lightning visuals
- Status effect icons

**Solution:** Create VFX mapping in Phase 3
```python
VFX_MAP = {
    'fire': 'fire_particles',
    'chain': 'lightning_arc',
    'cone': 'cone_indicator',
    'burn': 'burn_icon'
}
```

### 2. Hostile Special Abilities JSONs
Defined how to convert, but didn't create `ability-definitions.JSON`

**Action:** Create in Phase 3 Week 4

### 3. Skill JSON Conversion
Defined conversion, but didn't update actual skill JSONs

**Action:** Migrate in Phase 3 Week 4

### 4. Performance Optimization
No specific optimization strategy defined

**Action:** Profile in Week 5, optimize hot paths

### 5. Existing Buff System Integration
Current buff system in `entities/components/buffs.py` - need to integrate

**Action:** Week 3 - extend existing buff system, don't replace

---

## Implementation Order (Detailed)

### Day 1-2: Core Systems
- [ ] Create `core/effect_registry.py`
- [ ] Create `core/tag_parser.py`
- [ ] Create `core/effect_context.py`
- [ ] Create `core/tag_debug.py`
- [ ] Unit tests for parser

### Day 3-5: Geometry
- [ ] Create `core/geometry/` module
- [ ] Implement `target_finder.py`
- [ ] Implement `math_utils.py`
- [ ] Unit tests for each geometry type
- [ ] Visual debug for cone/circle

### Day 6-8: Status Effects
- [ ] Create `entities/status_manager.py`
- [ ] Create base `StatusEffect` class
- [ ] Implement burn, freeze, slow, stun
- [ ] Implement bleed, poison, regen
- [ ] Add to Entity base class

### Day 9-10: Special Mechanics
- [ ] Implement lifesteal
- [ ] Implement knockback/pull
- [ ] Implement reflect/thorns
- [ ] Implement critical hits

### Day 11-13: Turret Integration
- [ ] Update `systems/turret_system.py`
- [ ] Test with basic arrow turret
- [ ] Test with fire turret (burn)
- [ ] Test with lightning cannon (chain)
- [ ] Test with flamethrower (cone)

### Day 14-15: Combat Integration
- [ ] Update `Combat/combat_manager.py`
- [ ] Test player attacks
- [ ] Test enemy attacks
- [ ] Test status effects in combat

### Day 16-17: Skill Integration
- [ ] Update `entities/components/skill_manager.py`
- [ ] Migrate skills to new format
- [ ] Test skill effects

### Day 18-19: Hostile Abilities
- [ ] Create `Definitions.JSON/ability-definitions.JSON`
- [ ] Create `systems/ability_system.py`
- [ ] Convert all special abilities
- [ ] Test hostile abilities

### Day 20-21: Testing & Polish
- [ ] Full integration tests
- [ ] Performance profiling
- [ ] Bug fixes
- [ ] Visual effects hookup

---

## Test Strategy

### Unit Tests
```python
# test_chain_geometry.py
def test_chain_finds_nearest_targets()
def test_chain_respects_range()
def test_chain_excludes_already_hit()
def test_chain_applies_falloff()

# test_status_effects.py
def test_burn_applies_dot()
def test_burn_stacks()
def test_freeze_immobilizes()
def test_freeze_and_burn_mutually_exclusive()

# test_tag_parser.py
def test_parse_single_tag()
def test_parse_multiple_tags()
def test_conflict_resolution()
def test_context_inference()
```

### Integration Tests
```python
# test_turret_effects.py
def test_lightning_cannon_chains()
def test_flamethrower_cone()
def test_fire_arrow_applies_burn()

# test_skill_effects.py
def test_whirlwind_strike_aoe()
def test_healing_chain_targets_allies()
def test_chain_harvest_gathers_multiple()
```

### Performance Tests
```python
def test_parse_10k_tags_under_100ms()
def test_chain_calculation_under_1ms()
def test_cone_calculation_under_1ms()
```

---

## Risk Mitigation

### Risk: Breaking Existing Systems
**Mitigation:** Feature flag to toggle between old/new systems
```python
USE_TAG_SYSTEM = os.getenv('USE_TAG_SYSTEM', 'false').lower() == 'true'

if USE_TAG_SYSTEM:
    execute_tag_based_effect()
else:
    execute_old_effect()
```

### Risk: Performance Degradation
**Mitigation:** Profile early, optimize geometry calculations, cache parsed configs

### Risk: Complex Debugging
**Mitigation:** Comprehensive logging at DEBUG level, visual debug UI

---

## Success Criteria

### Week 1 Complete When:
- [ ] Tag parser categorizes tags correctly
- [ ] Context inference works
- [ ] Debug logging functional

### Week 2 Complete When:
- [ ] Chain targeting works with falloff
- [ ] Cone geometry accurate
- [ ] Circle AOE functional
- [ ] All unit tests pass

### Week 3 Complete When:
- [ ] Burn applies DoT correctly
- [ ] Freeze immobilizes
- [ ] Status effects stack properly
- [ ] Mutual exclusion works

### Week 4 Complete When:
- [ ] Turrets use tag system
- [ ] Lightning cannon chains correctly
- [ ] Flamethrower cone works
- [ ] Skills use tag system

### Phase 3 Complete When:
- [ ] All functional tags implemented
- [ ] All tests passing
- [ ] Performance acceptable (< 1ms per effect)
- [ ] No regressions in existing gameplay

---

## Files to Create (Phase 3)

```
Game-1-modular/
├── core/
│   ├── effect_registry.py       (NEW)
│   ├── tag_parser.py             (NEW)
│   ├── effect_context.py         (NEW)
│   ├── tag_debug.py              (NEW)
│   └── geometry/                 (NEW)
│       ├── __init__.py
│       ├── target_finder.py
│       └── math_utils.py
├── entities/
│   ├── status_manager.py         (NEW)
│   ├── status_effect.py          (NEW)
│   └── status_effects/           (NEW)
│       ├── burn.py
│       ├── freeze.py
│       ├── slow.py
│       ├── stun.py
│       ├── bleed.py
│       └── poison.py
├── systems/
│   ├── turret_system.py          (UPDATE)
│   ├── ability_system.py         (NEW)
│   └── vfx_system.py             (NEW - optional)
├── Combat/
│   └── combat_manager.py         (UPDATE)
└── Definitions.JSON/
    └── ability-definitions.JSON  (NEW)
```

---

## Questions to Consider Before Starting

1. **Should we create feature flag for gradual rollout?**
   - YES - reduce risk of breaking changes

2. **Should we migrate JSONs incrementally or all at once?**
   - INCREMENTAL - start with turrets, then expand

3. **Should we create visual debug UI for tag system?**
   - YES - helps with debugging geometry/targeting

4. **Should we optimize early or optimize later?**
   - PROFILE EARLY, optimize only if needed

5. **Should existing buff system be replaced or extended?**
   - EXTEND - integrate StatusEffectManager with existing BuffManager

---

**Phase 3 Ready to Begin** ✅

**Next Step:** Create `core/effect_registry.py` and start Week 1
