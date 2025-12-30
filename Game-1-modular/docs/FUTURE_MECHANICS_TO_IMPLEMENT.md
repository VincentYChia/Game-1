# Future Mechanics to Implement

These mechanics are **defined in the tag system** but not yet implemented in code. They can be added when needed.

---

## 1. Reflect/Thorns Mechanics

**Status**: Defined in tag-definitions.JSON, not implemented
**Priority**: Medium
**Complexity**: Medium

### Description
When the entity takes damage, a percentage is reflected back to the attacker.

### Implementation Needed

**File**: `core/effect_executor.py`

```python
def _apply_reflect(self, source: Any, target: Any, config: EffectConfig):
    """Apply reflect/thorns effect to target"""
    reflect_percent = config.params.get('reflect_percent', 0.3)  # 30% default

    # Add reflect buff to target
    if hasattr(target, 'buffs'):
        from entities.components.buffs import ActiveBuff
        buff = ActiveBuff(
            buff_id="reflect",
            name="Reflect",
            effect_type="reflect",
            category="defensive",
            bonus_value=reflect_percent,
            duration=config.params.get('reflect_duration', 10.0),
            duration_remaining=config.params.get('reflect_duration', 10.0)
        )
        target.buffs.add_buff(buff)
```

**Integration**: Modify `Character.take_damage()` to check for reflect buffs:

```python
def take_damage(self, damage: float, damage_type: str = "physical", **kwargs):
    # Apply damage as normal
    self.health -= damage

    # Check for reflect/thorns buffs
    if hasattr(self, 'buffs'):
        for buff in self.buffs.active_buffs:
            if buff.effect_type == 'reflect':
                reflect_damage = damage * buff.bonus_value
                source = kwargs.get('source')
                if source and hasattr(source, 'take_damage'):
                    source.take_damage(reflect_damage, damage_type)
                    print(f"   ⚡ Reflected {reflect_damage:.1f} damage!")
```

### Tag Usage
```json
{
  "tags": ["physical", "single_target", "reflect"],
  "effectParams": {
    "baseDamage": 20,
    "reflect_percent": 0.5,
    "reflect_duration": 15.0
  }
}
```

---

## 2. Summon Mechanics

**Status**: Defined in tag-definitions.JSON, not implemented
**Priority**: Low
**Complexity**: High

### Description
Spawns temporary or permanent allied entities (minions, turrets, etc.)

### Implementation Needed

**File**: `core/effect_executor.py`

```python
def _apply_summon(self, source: Any, target: Any, config: EffectConfig):
    """Summon allied entity"""
    summon_type = config.params.get('summon_type', 'skeleton')
    summon_count = config.params.get('summon_count', 1)
    summon_duration = config.params.get('summon_duration', 30.0)  # 0 = permanent

    # Get spawn position (near target or source)
    spawn_pos = self._get_position(target)

    # This requires game engine integration to spawn entities
    # Would need to call combat_manager or world.spawn_entity()
    if hasattr(source, 'world'):
        for i in range(summon_count):
            # Offset position slightly for multiple summons
            offset_x = (i % 3 - 1) * 1.5
            offset_y = (i // 3) * 1.5
            pos = Position(spawn_pos.x + offset_x, spawn_pos.y + offset_y, 0.0)

            # Spawn entity (implementation depends on game architecture)
            # source.world.spawn_ally(summon_type, pos, owner=source, duration=summon_duration)
```

**Requirements**:
- Enemy/NPC spawning system
- Ownership/allegiance system
- Temporary entity cleanup (for timed summons)
- Summon definitions (skeleton, turret, etc.)

### Tag Usage
```json
{
  "tags": ["arcane", "circle", "summon"],
  "effectParams": {
    "circle_radius": 3.0,
    "summon_type": "skeleton_warrior",
    "summon_count": 3,
    "summon_duration": 60.0
  }
}
```

---

## 3. Teleport/Dash/Phase Mechanics

**Status**: Defined in tag-definitions.JSON, not implemented
**Priority**: Medium
**Complexity**: Medium-High

### Description
- **Teleport**: Instant position change
- **Dash**: Fast movement to target location
- **Phase**: Teleport through obstacles

### Implementation Needed

**File**: `core/effect_executor.py`

```python
def _apply_teleport(self, source: Any, target: Any, config: EffectConfig):
    """Teleport entity to target position"""
    teleport_type = config.params.get('teleport_type', 'to_target')  # to_target, away, behind

    source_pos = self._get_position(source)
    target_pos = self._get_position(target)

    if teleport_type == 'to_target':
        # Teleport to target (with small offset to avoid overlap)
        dx = target_pos.x - source_pos.x
        dy = target_pos.y - source_pos.y
        distance = (dx*dx + dy*dy) ** 0.5

        if distance > 0.1:
            # Stop 1 tile before target
            ratio = max(0, distance - 1.0) / distance
            new_x = source_pos.x + dx * ratio
            new_y = source_pos.y + dy * ratio
        else:
            new_x, new_y = target_pos.x, target_pos.y

    elif teleport_type == 'away':
        # Teleport away from target
        teleport_distance = config.params.get('teleport_distance', 5.0)
        dx = source_pos.x - target_pos.x
        dy = source_pos.y - target_pos.y
        distance = (dx*dx + dy*dy) ** 0.5

        if distance > 0.1:
            dx /= distance
            dy /= distance
        else:
            dx, dy = 1.0, 0.0

        new_x = source_pos.x + dx * teleport_distance
        new_y = source_pos.y + dy * teleport_distance

    elif teleport_type == 'behind':
        # Teleport behind target (opposite side from source)
        behind_distance = config.params.get('behind_distance', 2.0)
        dx = target_pos.x - source_pos.x
        dy = target_pos.y - source_pos.y
        distance = (dx*dx + dy*dy) ** 0.5

        if distance > 0.1:
            dx /= distance
            dy /= distance
        else:
            dx, dy = 1.0, 0.0

        new_x = target_pos.x + dx * behind_distance
        new_y = target_pos.y + dy * behind_distance

    # Apply new position (with collision check if phase=False)
    phase_through = config.params.get('phase', False)

    if phase_through:
        # Phase ignores collision
        self._set_position(source, new_x, new_y)
        print(f"   🌀 Phased to ({new_x:.1f}, {new_y:.1f})")
    else:
        # Check if position is walkable
        if self._is_walkable(new_x, new_y):
            self._set_position(source, new_x, new_y)
            print(f"   ⚡ Teleported to ({new_x:.1f}, {new_y:.1f})")
        else:
            print(f"   ❌ Teleport blocked by obstacle")

def _is_walkable(self, x: float, y: float) -> bool:
    """Check if position is walkable (requires world reference)"""
    # Would need access to world/collision system
    return True  # Placeholder

def _set_position(self, entity: Any, x: float, y: float):
    """Set entity position"""
    if hasattr(entity, 'position'):
        if hasattr(entity.position, 'x'):
            entity.position.x = x
            entity.position.y = y
        elif isinstance(entity.position, list):
            entity.position[0] = x
            entity.position[1] = y
```

**Requirements**:
- World/collision system access
- Position validation
- Visual effects for teleport

### Tag Usage
```json
{
  "tags": ["arcane", "single_target", "teleport"],
  "effectParams": {
    "teleport_type": "to_target",
    "phase": false
  }
}
```

```json
{
  "tags": ["shadow", "single_target", "dash"],
  "effectParams": {
    "teleport_type": "away",
    "teleport_distance": 8.0,
    "phase": true
  }
}
```

---

## 4. Execute Mechanics

**Status**: Defined in tag-definitions.JSON, not implemented
**Priority**: Low
**Complexity**: Low

### Description
Instantly kills target if below HP threshold.

### Implementation Needed

**File**: `core/effect_executor.py`

```python
def _apply_execute(self, source: Any, target: Any, config: EffectConfig):
    """Execute target if below HP threshold"""
    execute_threshold = config.params.get('execute_threshold', 0.2)  # 20% HP

    if not hasattr(target, 'current_health') or not hasattr(target, 'max_health'):
        return

    hp_percent = target.current_health / target.max_health

    if hp_percent <= execute_threshold:
        # Instant kill
        target.current_health = 0
        if hasattr(target, 'is_alive'):
            target.is_alive = False

        print(f"   💀 EXECUTED! {getattr(target, 'name', 'Target')} below {execute_threshold*100}% HP")
    else:
        print(f"   ⚠️  Execute failed: {hp_percent*100:.1f}% HP (threshold: {execute_threshold*100}%)")
```

**Integration**: Add to `_apply_special_mechanics()`:

```python
def _apply_special_mechanics(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
    """Apply special mechanics"""
    for special_tag in config.special_tags:
        # ... existing mechanics ...

        elif special_tag == 'execute':
            self._apply_execute(source, target, config.params)
```

### Tag Usage
```json
{
  "tags": ["physical", "single_target", "execute"],
  "effectParams": {
    "baseDamage": 100,
    "execute_threshold": 0.25
  }
}
```

---

## 5. Critical as Tag

**Status**: Crit system exists but not tag-driven
**Priority**: Medium
**Complexity**: Low

### Description
Currently, critical hits are stat-based. Making it tag-driven would allow weapons/skills to have guaranteed crits or bonus crit chance.

### Implementation Needed

**File**: `core/tag_parser.py`

Add critical tag detection:

```python
def parse(self, tags: List[str], params: dict) -> EffectConfig:
    # ... existing parsing ...

    # Check for critical tag
    if 'critical' in tags:
        config.crit_chance_bonus = params.get('crit_chance_bonus', 0.5)  # +50% crit chance
        config.crit_damage_mult = params.get('crit_damage_mult', 2.0)  # 2x damage
        config.guaranteed_crit = params.get('guaranteed_crit', False)
```

**File**: `core/effect_executor.py`

Modify damage application:

```python
def _apply_damage(self, source: Any, target: Any, config: EffectConfig, magnitude_mult: float):
    """Apply damage to target"""
    base_damage = config.base_damage * magnitude_mult

    # Check for critical from tags
    is_crit = False
    crit_mult = 1.0

    if config.guaranteed_crit:
        is_crit = True
        crit_mult = config.crit_damage_mult
    elif config.crit_chance_bonus > 0:
        # Add bonus crit chance from tags
        base_crit_chance = getattr(source, 'crit_chance', 0.0)
        total_crit_chance = base_crit_chance + config.crit_chance_bonus

        if random.random() < total_crit_chance:
            is_crit = True
            crit_mult = config.crit_damage_mult

    if is_crit:
        base_damage *= crit_mult
        print(f"   💥 CRITICAL HIT! ({crit_mult}x damage)")

    # Apply damage for each damage type
    for damage_tag in config.damage_tags:
        # ... rest of damage application ...
```

### Tag Usage
```json
{
  "tags": ["physical", "single_target", "critical"],
  "effectParams": {
    "baseDamage": 80,
    "guaranteed_crit": true,
    "crit_damage_mult": 3.0
  }
}
```

```json
{
  "tags": ["physical", "cone", "critical"],
  "effectParams": {
    "baseDamage": 50,
    "crit_chance_bonus": 0.75,
    "crit_damage_mult": 2.5
  }
}
```

---

## Implementation Priority

### High Priority (Gameplay Impact)
1. **Execute** - Low complexity, high impact for boss fights
2. **Critical as Tag** - Enables build diversity

### Medium Priority (Nice to Have)
3. **Reflect/Thorns** - Defensive gameplay option
4. **Teleport/Dash** - Mobility mechanics

### Low Priority (Complex, Niche)
5. **Summon** - Requires entity spawning system

---

## Testing Checklist

For each implemented mechanic:

- [ ] Unit test created
- [ ] Added to `_apply_special_mechanics()` dispatcher
- [ ] Tag definition updated in tag-definitions.JSON
- [ ] Example weapon/skill created
- [ ] Documented in TAG_SYSTEM_COMPLETION_REPORT.md
- [ ] In-game testing completed
