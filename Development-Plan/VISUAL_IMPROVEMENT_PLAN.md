# Visual Improvement Plan — Tier 1 & Tier 2

**Status**: Ready for implementation
**Depends on**: Existing codebase (75K LOC), Development-Plan/PART_1_COMBAT_VISUALS.md
**Scope**: Tier 1 (low risk, high value) and Tier 2 (medium effort, high value) from animation research
**Philosophy**: New modules only, JSON-driven data, minimal changes to existing code
**Last Updated**: 2026-03-08

---

## Existing Infrastructure Audit

Before planning new work, here is what **already exists** in the codebase:

| System | Status | Location | Notes |
|--------|--------|----------|-------|
| Animation Manager | **EXISTS** | `animation/animation_manager.py` (121 lines) | Singleton, entity→SpriteAnimation registry, update_all/play/stop |
| Animation Data | **EXISTS** | `animation/animation_data.py` (42 lines) | AnimationFrame, AnimationDefinition dataclasses |
| Sprite Animation | **EXISTS** | `animation/sprite_animation.py` (69 lines) | Frame player with progress, hitbox_active, completion callback |
| Procedural Animations | **EXISTS** | `animation/procedural.py` (368 lines) | swing_arc, telegraph_pulse, hit_flash, idle_bob, slash_trail, ground_telegraph |
| Combat Particles | **EXISTS** | `animation/combat_particles.py` (212 lines) | World-space particles: hit_sparks, slash_trail, dodge_dust, projectile_trail |
| Weapon Visuals | **EXISTS** | `animation/weapon_visuals.py` (181 lines) | Tag-driven visual style resolver (element colors, tier scaling, weight/speed) |
| Damage Numbers | **BASIC** | `entities/damage_number.py` (20 lines) | Simple dataclass — no color, no easing, no pop effect |
| Screen Shake | **BASIC** | `core/minigame_effects.py:556-596` | Works but coupled to minigame UI, not centralized |
| Easing Functions | **PARTIAL** | `core/minigame_effects.py:48-84` + `animation/procedural.py:20-31` | Duplicated across files, no Tween/TweenGroup class |
| Attack Effects | **EXISTS** | `systems/attack_effects.py` | Tag-driven slash/thrust/impact/blocked/area effects |
| Telegraph Rendering | **EXISTS** | `rendering/renderer.py:1597-1850` | Arc/circle telegraphs with progress-based fill |

**Key gaps**: No centralized easing+Tween system, no enhanced damage numbers (color/pop/easing), no centralized screen effects (shake/pause/flash/slow-mo), no JSON-driven particle emitters, telegraph visuals could be more readable.

---

## Table of Contents

1. [Section A — pygame-ce Migration](#section-a--pygame-ce-migration)
2. [Section B — Easing & Tweening Foundation](#section-b--easing--tweening-foundation)
3. [Section C — Animation Controller Enhancement](#section-c--animation-controller-enhancement)
4. [Section D — Procedural Animation Extensions](#section-d--procedural-animation-extensions)
5. [Section E — Floating Combat Text (Damage Numbers)](#section-e--floating-combat-text-damage-numbers)
6. [Section F — Screen Effects System](#section-f--screen-effects-system)
7. [Section G — Combat Particle System Enhancement](#section-g--combat-particle-system-enhancement)
8. [Section H — Attack Telegraph Visuals](#section-h--attack-telegraph-visuals)
9. [Dependency Graph](#dependency-graph)
10. [File Map](#file-map)

---

## Section A — pygame-ce Migration

**Priority**: Tier 1 — Do first
**Risk**: Minimal (drop-in replacement)
**Effort**: ~30 minutes
**Files touched**: `requirements.txt` (or equivalent), no code changes

### What

Replace `pygame` with `pygame-ce` (Community Edition). Drop-in compatible — `import pygame` still works. Better rendering performance, improved `pygame.transform`, active maintenance, additional blend modes.

### Steps

1. `pip install pygame-ce` (replaces `pygame` in the environment)
2. Update any `requirements.txt` or install docs to reference `pygame-ce`
3. Run the game and verify everything works identically
4. No code changes needed — all `import pygame` statements work as-is

### What You Get

- Faster `Surface.blit()` and `pygame.transform` operations
- Improved blend modes (useful for Sections D, F, G)
- Hardware-accelerated transform paths on supported platforms
- Active maintenance and bug fixes (multiple releases per year)
- Foundation for all subsequent visual improvements

### Verification

- Game launches and runs at 60 FPS
- All existing crafting minigames render correctly
- Combat visuals unchanged
- No import errors

---

## Section B — Easing & Tweening Foundation

**Priority**: Tier 1 — Do immediately after pygame-ce
**Risk**: None (new module, no existing code touched)
**Effort**: ~1 hour
**New file**: `animation/easing.py`

### What

A pure-Python easing/tweening module providing 20+ standard easing curves. Every subsequent visual system (combat animations, damage numbers, screen shake, particles) uses this as its timing backbone.

### Architecture

```
animation/
├── __init__.py
└── easing.py          # Easing functions + Tween manager
```

### Core API

```python
# --- Easing functions (pure math, no state) ---
# Each takes progress (0.0 to 1.0), returns eased value (0.0 to 1.0)

def linear(t: float) -> float
def ease_in_quad(t: float) -> float
def ease_out_quad(t: float) -> float
def ease_in_out_quad(t: float) -> float
def ease_out_cubic(t: float) -> float
def ease_in_out_cubic(t: float) -> float
def ease_out_back(t: float) -> float      # Overshoot (damage number pop)
def ease_out_bounce(t: float) -> float    # Bounce (item pickup)
def ease_out_elastic(t: float) -> float   # Spring (hit reaction)
def ease_in_expo(t: float) -> float       # Exponential (screen shake decay)


# --- Tween class (stateful, manages a single interpolation) ---

class Tween:
    """Interpolates a value from start to end over duration using an easing function.

    Usage:
        tween = Tween(start=0, end=100, duration=0.5, easing=ease_out_quad)
        # Each frame:
        tween.update(dt)
        current_value = tween.value
        if tween.is_complete:
            ...
    """
    def __init__(self, start, end, duration, easing=linear, on_complete=None)
    def update(self, dt: float) -> None
    @property
    def value(self) -> float
    @property
    def is_complete(self) -> bool
    def reset(self) -> None


# --- TweenGroup (manages multiple tweens, auto-removes completed) ---

class TweenGroup:
    """Manages a collection of active tweens. Call update() once per frame."""
    def add(self, name: str, tween: Tween) -> None
    def get(self, name: str) -> Optional[Tween]
    def update(self, dt: float) -> List[str]  # Returns names of completed tweens
    def clear(self) -> None
```

### Key Easing Curves and Their Uses

| Easing | Use Case |
|--------|----------|
| `ease_out_quad` | Damage numbers floating up (decelerating rise) |
| `ease_out_back` | Damage number pop-in (overshoot for emphasis) |
| `ease_out_elastic` | Hit reaction knockback (springy settle) |
| `ease_in_expo` | Screen shake decay (fast ramp down) |
| `ease_out_cubic` | Telegraph fill progress (smooth reveal) |
| `ease_in_out_quad` | Weapon swing arc (smooth start and end) |
| `ease_out_bounce` | Item/loot drop animation |
| `linear` | Particle lifetime, cooldown bars |

### Integration Points

- **No existing code touched** — this is a standalone module
- All subsequent sections import from `animation.easing`
- Can be tested independently with `python -m animation.easing` (unit tests)

### Verification

- All easing functions return 0.0 at t=0.0 and 1.0 at t=1.0
- Tween.value interpolates correctly
- TweenGroup auto-removes completed tweens

---

## Section C — Animation Controller Enhancement

**Priority**: Tier 1 — Extend existing foundation
**Risk**: Low (extending existing modules)
**Effort**: ~1.5 hours (reduced — core already exists)
**Modified files**: `animation/animation_data.py`, `animation/animation_manager.py`
**Modified file**: `rendering/renderer.py` (additive — new method, not replacing existing)

### What Already Exists

The animation system is **substantially built**:
- `animation/animation_data.py` — `AnimationFrame` (surface, duration, offset, hitbox_active, scale) and `AnimationDefinition` (frames, loop, total_duration)
- `animation/sprite_animation.py` — Frame player with `update()`, `get_current_frame()`, `progress`, `finished`, completion callback
- `animation/animation_manager.py` — Singleton with `play()`, `stop()`, `update_all()`, `get_current_frame()`, `is_animating()`, definition registry

### What's Missing

1. **AnimationFrame lacks `rotation`, `alpha`, and `event` fields** — needed for weapon swings (rotation), death fade (alpha), and timed events (sound/hitbox triggers)
2. **AnimationManager lacks layer support** — currently one animation per entity; combat needs body + weapon + effect overlays simultaneously
3. **No renderer integration** — `renderer.py` doesn't query the AnimationManager yet
4. **No JSON loading** — definitions are only created procedurally, not loadable from JSON

### Changes Needed

**1. Extend AnimationFrame** (add 3 fields to existing dataclass):

```python
@dataclass
class AnimationFrame:
    surface: Optional[pygame.Surface]
    duration_ms: float
    offset_x: float = 0.0
    offset_y: float = 0.0
    hitbox_active: bool = False
    scale: float = 1.0
    rotation: float = 0.0         # NEW — Degrees of rotation
    alpha: int = 255              # NEW — Transparency
    event: Optional[str] = None   # NEW — Event name fired when frame starts
```

**2. Add layer support to AnimationManager**:

```python
# Change internal storage from Dict[str, SpriteAnimation]
# to Dict[str, Dict[str, SpriteAnimation]] — entity_id → layer → animation
# Layers: 'body', 'weapon', 'effect'

def play(self, entity_id, animation_id, layer='default', ...):
def get_current_frame(self, entity_id, layer='default'):
```

**3. Renderer integration** — add one method to `renderer.py`:

```python
def _draw_animated_entity(self, surface, entity, screen_pos):
    """Draw entity with animation overrides if active. Falls through
    to static sprite if no animation playing."""
```

**4. JSON animation loading** — add a loader method to AnimationManager:

```python
def load_definitions(self, filepath: str) -> int:
    """Load animation definitions from JSON file. Returns count loaded."""
```

### Verification

- Existing procedural animations (swing_arc, hit_flash, etc.) still work
- New rotation/alpha/event fields used by Section D
- Layer support allows body + weapon animations simultaneously
- Renderer falls through to static sprite when no animation is active

---

## Section D — Procedural Animation Extensions

**Priority**: Tier 2 — Extend during combat overhaul
**Risk**: Medium (interacts with combat state machine)
**Effort**: ~2 hours (reduced — core generators exist)
**Modified file**: `animation/procedural.py`
**Depends on**: Section B (easing), Section C (animation controller enhancements)

### What Already Exists

`animation/procedural.py` (368 lines) already provides:
- `create_swing_arc()` — Melee arc with easing, frame-based hitbox_active
- `create_telegraph_pulse()` — Scale + tint for enemy windup
- `create_hit_flash()` — 2-frame white flash on damage
- `create_idle_bob()` — Vertical sine oscillation (looping)
- `create_slash_trail()` — Expanding arc trail with fade
- `create_ground_telegraph()` — Circle/arc fill indicator

Also has internal easing helpers: `_ease_out_cubic`, `_ease_in_out_sine`, `_lerp`, `_tint_surface`, `_white_flash_surface`.

### What's Missing

1. **`create_death_fade()`** — Fade out + vertical collapse for death animation
2. **`create_dodge_roll()`** — Rotation + offset for dodge animation
3. **`create_hit_reaction()`** — White flash + knockback settle (elastic easing) — current `create_hit_flash` is just 2 frames without knockback
4. **Weapon-type-aware swing** — `create_swing_arc()` takes arc/duration but doesn't integrate with `weapon_visuals.py` WeaponVisualStyle
5. **Attack profile integration** — Connect `EnemyAttackDef` from the generator to procedural animations

### Changes Needed

Add 3 new methods to `ProceduralAnimations` class:

```python
@staticmethod
def create_death_fade(base_sprite: pygame.Surface,
                       duration_ms: float = 800.0,
                       collapse: bool = True) -> AnimationDefinition:
    """Fade out + optional vertical collapse. Uses ease_in_quad for alpha."""

@staticmethod
def create_dodge_roll(direction_angle: float,
                       distance_px: float = 48.0,
                       duration_ms: float = 250.0) -> AnimationDefinition:
    """Rotation + position offset in direction. Uses ease_out_quad."""

@staticmethod
def create_hit_reaction(base_sprite: pygame.Surface,
                         knockback_px: float = 8.0,
                         duration_ms: float = 200.0) -> AnimationDefinition:
    """Flash + knockback settle. Uses ease_out_elastic for spring feel."""
```

Add a bridge function to connect AttackProfileGenerator to animations:

```python
def create_enemy_attack_animation(attack_def, enemy_surface):
    """Generate animation from AttackProfileGenerator output.
    Uses existing create_swing_arc for arc attacks,
    create_telegraph_pulse for circle attacks."""
```

### Weapon Type → Animation Mapping

Derived from existing `weapon_visuals.py` profiles (no JSON changes needed):

| Weapon Category | Arc Start | Arc End | Duration | Easing | Feel |
|----------------|-----------|---------|----------|--------|------|
| sword_1h | -32° | +32° | 350ms | ease_in_out_quad | Balanced swing |
| sword_2h | -50° | +50° | 550ms | ease_in_quad | Heavy, committal |
| dagger | -15° | +15° | 220ms | ease_out_quad | Fast slash |
| axe | -40° | +40° | 400ms | ease_in_cubic | Heavy start, fast finish |
| hammer_2h | -45° | +45° | 600ms | ease_in_expo | Overhead slam |
| staff | -17° | +17° | 380ms | ease_in_out_quad | Quick poke |

### Verification

- New death/dodge/hit_reaction animations work alongside existing generators
- AttackProfileGenerator output seamlessly drives enemy attack visuals
- weapon_visuals.py WeaponVisualStyle parameters map to swing arc parameters

---

## Section E — Floating Combat Text (Damage Numbers)

**Priority**: Tier 2 — High value, moderate effort
**Risk**: Low (purely additive rendering)
**Effort**: ~2 hours
**New file**: `combat/damage_numbers.py`
**Modified file**: `rendering/renderer.py` (additive — new draw call)
**Depends on**: Section B (easing)

### What

Floating damage numbers that pop up, arc upward, and fade out. Color-coded by damage type, scaled by severity, with crit emphasis.

### Core Classes

```python
@dataclass
class DamageNumber:
    """A single floating damage number."""
    value: int                        # Damage amount to display
    world_x: float                    # World position (tiles)
    world_y: float
    color: Tuple[int, int, int]       # RGB from damage type
    is_crit: bool = False
    is_heal: bool = False

    # Animation state (managed internally)
    elapsed_ms: float = 0.0
    lifetime_ms: float = 1200.0
    offset_x: float = 0.0            # Random horizontal scatter
    offset_y: float = 0.0            # Computed from easing
    alpha: int = 255
    scale: float = 1.0


class DamageNumberSystem:
    """Manages all active floating damage numbers."""
    _instance = None

    MAX_ACTIVE = 50  # Performance cap

    def spawn(self, value: int, world_x: float, world_y: float,
              damage_type: str = 'physical', is_crit: bool = False,
              is_heal: bool = False) -> None:
        """Spawn a new damage number. Oldest removed if at MAX_ACTIVE."""

    def update(self, dt_ms: float) -> None:
        """Update all active numbers. Remove expired ones."""

    def get_active(self) -> List[DamageNumber]:
        """Return active numbers for renderer to draw."""
```

### Damage Type → Color Mapping

Derived from existing tag system (no new data needed):

| Tag | Color | RGB |
|-----|-------|-----|
| `physical` | White | (255, 255, 255) |
| `fire` | Orange-Red | (255, 120, 40) |
| `ice` | Cyan | (100, 200, 255) |
| `lightning` | Yellow | (255, 255, 100) |
| `poison` | Green | (100, 255, 100) |
| `arcane` | Purple | (180, 100, 255) |
| `shadow` | Dark Purple | (140, 60, 200) |
| `holy` | Gold | (255, 220, 100) |
| `heal` | Bright Green | (50, 255, 50) |
| `crit` | (any color, 2x scale) | — |

### Animation Behavior

```
Spawn:
  - Random horizontal scatter: ±15px
  - Scale pop: 0.5 → 1.2 → 1.0 over first 150ms (ease_out_back)
  - Crit: 2x font size, "!" suffix, extra pop

Rise (0-800ms):
  - Float upward: 0 → -40px (ease_out_quad — decelerating rise)

Fade (800-1200ms):
  - Alpha: 255 → 0 (linear)
  - Scale: 1.0 → 0.7 (ease_in_quad)
```

### Integration

In `combat_manager.py`, after damage is calculated (single line addition):

```python
# After: self.apply_damage(target, final_damage)
DamageNumberSystem.get_instance().spawn(
    final_damage, target.position.x, target.position.y,
    damage_type=primary_tag, is_crit=was_crit)
```

In `renderer.py`, add a draw pass after entities:

```python
def _draw_damage_numbers(self, surface):
    for dn in DamageNumberSystem.get_instance().get_active():
        screen_pos = self.camera.world_to_screen(Position(dn.world_x, dn.world_y))
        # Apply dn.offset_x, dn.offset_y, dn.alpha, dn.scale
        # Render text with pygame.font
```

### Verification

- Numbers appear at entity position on hit
- Numbers float upward and fade
- Crits are larger and more emphatic
- Different damage types show different colors
- Performance stays at 60 FPS with 50 simultaneous numbers
- Numbers are readable against any background (black outline)

---

## Section F — Screen Effects System

**Priority**: Tier 2 — High impact, low effort
**Risk**: Low (modifies camera offset only)
**Effort**: ~2 hours
**New file**: `animation/screen_effects.py`
**Modified files**: `core/camera.py` (1 field), `rendering/renderer.py` (1 call)
**Depends on**: Section B (easing)

### What

A centralized system for screen-wide visual effects: screen shake, hit pause (freeze frames), slow motion, and screen flash. These effects dramatically improve combat "feel" with minimal code.

### Core Class

```python
class ScreenEffects:
    """Manages screen-wide visual effects. Singleton, updated once per frame."""
    _instance = None

    # --- Screen Shake ---
    def shake(self, intensity: float = 8.0, duration_ms: float = 200.0,
              decay: str = 'exponential') -> None:
        """Start screen shake. Intensity = max pixel offset.
        Stacks with existing shake (takes the higher intensity)."""

    def get_shake_offset(self) -> Tuple[int, int]:
        """Returns (dx, dy) pixel offset to apply to camera this frame.
        Called by camera.py each frame."""

    # --- Hit Pause (Freeze Frame) ---
    def hit_pause(self, duration_ms: float = 50.0) -> None:
        """Freeze game time for duration. Creates impactful hit feel.
        Rendering continues but dt=0 for game logic."""

    def get_time_scale(self) -> float:
        """Returns 0.0 during hit pause, 1.0 normally,
        0.3 during slow motion. Multiply with dt."""

    # --- Slow Motion ---
    def slow_motion(self, time_scale: float = 0.3,
                     duration_ms: float = 500.0) -> None:
        """Temporarily slow game time. For critical kills, boss phase changes."""

    # --- Screen Flash ---
    def flash(self, color: Tuple[int, int, int] = (255, 255, 255),
              alpha: int = 80, duration_ms: float = 100.0) -> None:
        """Brief full-screen color flash. For big hits, level ups, etc."""

    def get_flash_surface(self, screen_size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """Returns a semi-transparent surface to blit over everything, or None."""

    # --- Update ---
    def update(self, dt_ms: float) -> None:
        """Update all active effects. Called once per frame."""
```

### Trigger Conditions (from existing combat data)

Screen effects trigger based on data already in the combat system:

| Event | Effect | How Detected |
|-------|--------|--------------|
| Player hit (any) | Shake(4, 100ms) | `_enemy_attack_player()` |
| Player hit (T3+ enemy) | Shake(8, 200ms) + Flash(red, 60) | Enemy tier check |
| Critical hit | Shake(6, 150ms) + HitPause(40ms) | `was_crit` flag |
| Enemy killed | Shake(3, 80ms) | Kill event |
| Boss phase change | SlowMotion(0.3, 500ms) + Flash(white, 100) | Health threshold |
| Player dodge (close miss) | Shake(2, 50ms) | Dodge near active hitbox |
| `EnemyAttackDef.screen_shake=True` | Shake(intensity_from_tier) | AttackProfileGenerator flag |

### Camera Integration

In `core/camera.py`, `world_to_screen()` already applies `self.shake_offset`. The ScreenEffects system sets this each frame:

```python
# In game loop update:
screen_effects.update(dt_ms)
camera.shake_offset = screen_effects.get_shake_offset()
```

### Verification

- Screen shakes visibly on hit
- Shake decays smoothly (no jarring end)
- Hit pause freezes action briefly on big hits
- Slow motion affects all entity movement/animation
- Flash overlays screen and fades
- Effects don't stack to nauseating levels (intensity capping)

---

## Section G — Combat Particle System Enhancement

**Priority**: Tier 2 — Medium effort, high value
**Risk**: Medium (performance sensitive)
**Effort**: ~3 hours (reduced — world-space particles already exist)
**Modified file**: `animation/combat_particles.py`
**New file**: `Animation-Data.JSON/particle-emitters.json`
**Depends on**: Section B (easing)

### What Already Exists

`animation/combat_particles.py` (212 lines) provides:
- `CombatParticle` class with world-space physics (gravity, drag, velocity, lifetime, alpha fade)
- `CombatParticleSystem` with 400 max particles, off-screen culling, world-to-screen rendering
- `emit_hit_sparks()` — Tag-colored burst at hit location (8 damage types mapped to colors)
- `emit_slash_trail()` — Particles along slash arc path
- `emit_dodge_dust()` — Dust cloud at dodge position
- `emit_projectile_trail()` — 7 trail types (fire, ice, arcane, acid, lightning, shadow, arrow)
- `DAMAGE_SPARK_COLORS` — Complete color mapping for all damage types

`core/minigame_effects.py` (1,522 lines) provides separate screen-space particles for crafting:
- Spark, Ember, Bubble, Steam, Spirit, GearTooth particle types
- ScreenShake, GlowEffect, FlameEffect classes

### What's Missing

1. **JSON-driven emitter definitions** — all emitters are currently hardcoded in Python
2. **Continuous emitters** — current system only does bursts, no sustained effects (poison aura, fire trail)
3. **Object pooling** — creates/destroys particle objects each frame (GC pressure)
4. **Status effect auras** — no per-entity continuous visual effects
5. **Death burst** — no enemy death explosion particles

### Architecture

```
animation/
├── particles.py               # ParticleSystem, Emitter, Particle
Animation-Data.JSON/
└── particle-emitters.json     # Emitter definitions
```

### Core Classes

```python
@dataclass
class Particle:
    """Single particle. Minimal state for performance."""
    x: float                    # World position (tiles)
    y: float
    vx: float                   # Velocity (tiles/sec)
    vy: float
    life: float                 # Remaining lifetime (seconds)
    max_life: float             # Starting lifetime
    color: Tuple[int, int, int]
    size: float                 # Radius in pixels
    alpha: int = 255
    gravity: float = 0.0       # Downward acceleration (tiles/sec²)


@dataclass
class EmitterDefinition:
    """Defines how particles are spawned. Loaded from JSON."""
    emitter_id: str
    # Spawn rate
    burst_count: int = 10       # Particles per burst (0 = continuous)
    continuous_rate: float = 0  # Particles per second (0 = burst only)
    # Particle properties (ranges for randomization)
    speed_min: float = 1.0
    speed_max: float = 3.0
    spread_angle: float = 360   # Degrees of spread (360 = all directions)
    life_min: float = 0.3
    life_max: float = 0.8
    size_min: float = 2.0
    size_max: float = 5.0
    gravity: float = 0.0
    # Color (start → end lerp over lifetime)
    color_start: Tuple[int, int, int] = (255, 255, 255)
    color_end: Tuple[int, int, int] = (100, 100, 100)
    # Behavior
    fade_out: bool = True       # Alpha fades over lifetime
    shrink: bool = True         # Size shrinks over lifetime


class ParticleSystem:
    """Manages all combat particles. Singleton, updated once per frame."""
    _instance = None

    MAX_PARTICLES = 3000        # Performance cap

    def emit(self, emitter_id: str, world_x: float, world_y: float,
             direction: float = 0.0, override_color: Tuple = None) -> None:
        """Spawn particles from a named emitter at world position."""

    def emit_continuous(self, emitter_id: str, world_x: float, world_y: float,
                         entity_id: str = None) -> str:
        """Start continuous emission. Returns handle to stop later."""

    def stop_continuous(self, handle: str) -> None:
        """Stop a continuous emitter."""

    def update(self, dt: float) -> None:
        """Update all particles. Remove dead ones."""

    def get_particles(self) -> List[Particle]:
        """Return all active particles for renderer to draw."""

    def load_definitions(self, filepath: str) -> None:
        """Load emitter definitions from JSON."""
```

### Tag → Emitter Mapping

Combat effects are driven by the existing tag system. No new data needed:

| Tag | Emitter ID | Visual |
|-----|-----------|--------|
| `physical` | `hit_sparks` | White/gray sparks, fast, no gravity |
| `fire` | `fire_burst` | Orange/red particles, upward drift, glow |
| `ice` | `ice_shatter` | Blue/white shards, slow drift, angular |
| `lightning` | `electric_sparks` | Yellow/white, fast, erratic paths |
| `poison` | `poison_cloud` | Green mist, slow expand, long life |
| `arcane` | `arcane_motes` | Purple sparkles, spiral motion |
| `shadow` | `shadow_wisps` | Dark purple, slow, fading trails |
| `bleed` | `blood_splatter` | Red droplets, gravity, short life |

### JSON Emitter Definitions

```json
{
  "emitters": {
    "hit_sparks": {
      "burst_count": 12,
      "speed_min": 3.0, "speed_max": 6.0,
      "spread_angle": 120,
      "life_min": 0.15, "life_max": 0.3,
      "size_min": 2, "size_max": 4,
      "color_start": [255, 255, 220],
      "color_end": [180, 180, 120],
      "gravity": 2.0,
      "fade_out": true, "shrink": true
    },
    "fire_burst": {
      "burst_count": 20,
      "speed_min": 1.5, "speed_max": 4.0,
      "spread_angle": 360,
      "life_min": 0.3, "life_max": 0.6,
      "size_min": 3, "size_max": 7,
      "color_start": [255, 180, 40],
      "color_end": [200, 50, 20],
      "gravity": -1.0,
      "fade_out": true, "shrink": false
    }
  }
}
```

### Performance Strategy

1. **Object pool**: Pre-allocate `MAX_PARTICLES` Particle objects, reuse dead ones
2. **Batch rendering**: `pygame.draw.circle()` is faster than blitting tiny surfaces
3. **numpy acceleration** (optional): If particle count is high, use numpy arrays for position/velocity updates (`positions += velocities * dt` vectorized)
4. **Distance culling**: Skip particles far from camera viewport

### Integration

In `combat_manager.py`, after damage is applied (1-2 line additions):

```python
# After damage applied:
primary_tag = attack_tags[0] if attack_tags else 'physical'
ParticleSystem.get_instance().emit(
    TAG_TO_EMITTER.get(primary_tag, 'hit_sparks'),
    target.position.x, target.position.y,
    direction=facing_angle)
```

### Verification

- Particles appear at correct world position
- Particles move, fade, and despawn correctly
- Different damage types produce visually distinct particles
- Performance stays at 60 FPS with 3000 particles
- Emitter definitions load from JSON
- Continuous emitters work for status effects (poison aura, etc.)

---

## Section H — Attack Telegraph Improvements

**Priority**: Tier 2 — Polish existing system
**Risk**: Low (modifying existing renderer methods)
**Effort**: ~2 hours
**Modified file**: `rendering/renderer.py` (existing `_draw_telegraph_arc` method)
**Depends on**: Section B (easing), Section F (screen effects)

### What

Improve the existing telegraph rendering (already working in renderer.py:1597-1696) with:
1. Shape-specific visuals (arc, circle, line — each looks distinct)
2. Eased fill progression (non-linear fill for better readability)
3. Pulsing edge glow (draws attention to danger boundary)
4. Directional indicator for arc attacks (arrow showing sweep direction)
5. Range ring for circle attacks (expanding ring toward max radius)

### Current State

The existing `_draw_telegraph_arc()` method (renderer.py:1597-1696) already handles:
- Arc vs circle shape detection
- Progress-based alpha intensification
- Color from tags
- Polygon-based wedge drawing

### Improvements

```python
# 1. Eased fill progression (replace linear progress)
#    Instead of: alpha = int(base_alpha * progress)
#    Use: alpha = int(base_alpha * ease_out_cubic(progress))
#    Effect: Fill starts slow, accelerates — creates urgency

# 2. Pulsing edge glow
#    Add a sine-wave pulsing bright edge at the boundary of the telegraph
#    Frequency increases as progress approaches 1.0
#    Effect: Draws eye to the danger zone boundary

# 3. Inner sweep line (for arc attacks)
#    A bright line sweeps through the arc from start to end angle
#    during the windup, showing the attack direction
#    Effect: Player sees which direction the swing is coming from

# 4. Expanding ring (for circle attacks)
#    A ring expands from center to max radius during windup
#    At 100% progress, ring reaches full radius = damage imminent
#    Effect: Intuitive "this area is about to be hit" visual

# 5. Flash-on-activation
#    When windup ends and active phase starts, brief bright flash
#    on the telegraph area (signals "damage is NOW")
#    Uses ScreenEffects.flash() integration
```

### Verification

- Telegraphs are more readable than before
- Arc attacks show sweep direction
- Circle attacks show expanding radius
- Flash clearly signals when damage fires
- Performance unchanged (drawing a few more lines/circles per enemy)

---

## Dependency Graph

```
Section A: pygame-ce Migration
    ↓ (prerequisite for all)
Section B: Easing Foundation
    ↓
    ├── Section C: Animation Controller
    │       ↓
    │   Section D: Procedural Combat Animations
    │
    ├── Section E: Damage Numbers
    │
    ├── Section F: Screen Effects
    │       ↓
    │   Section H: Telegraph Improvements
    │
    └── Section G: Particle System
```

**Parallel work possible**: After B is complete, C/E/F/G can all be worked on independently. D depends on C. H depends on F.

**Minimum viable path**: A → B → E + F (gives damage numbers + screen shake — biggest "feel" improvement for least effort).

---

## File Map

### New Files

```
animation/
├── easing.py                        # Section B — Centralized easing + Tween/TweenGroup
└── screen_effects.py                # Section F — Shake, pause, flash, slow-mo

Animation-Data.JSON/
├── attack-animations.json           # Section C — JSON animation definitions
└── particle-emitters.json           # Section G — Particle emitter configs
```

### Modified Files (Minimal Additions)

```
animation/animation_data.py          # Section C — Add rotation, alpha, event fields
animation/animation_manager.py       # Section C — Add layer support, JSON loading
animation/procedural.py              # Section D — Add death_fade, dodge_roll, hit_reaction
animation/combat_particles.py        # Section G — Add JSON emitters, continuous mode, pooling
entities/damage_number.py            # Section E — Enhance with color, easing, pop, crit

rendering/renderer.py
  + _draw_animated_entity()          # Section C — Animation-aware entity drawing
  + _draw_damage_numbers() enhanced  # Section E — Eased floating text
  + _draw_telegraph_arc() improved   # Section H — Better telegraph visuals

Combat/combat_manager.py
  + DamageNumberSystem.spawn(...)    # Section E — Enhanced spawn with tags
  + ScreenEffects.shake(...)         # Section F — 1 line on hit events

core/camera.py
  (already has shake_offset)         # Section F — ScreenEffects sets this

core/game_engine.py
  + ScreenEffects.update(dt)         # Section F — 1 line in game loop
```

### Existing Files NOT Touched

- All JSON files (hostiles, recipes, items, skills, etc.)
- Combat/enemy.py (attack profiles generated separately)
- Combat/attack_profile_generator.py (provides data, doesn't render)
- All crafting minigame files
- Save system
- Entity models
- animation/weapon_visuals.py (already complete)
- animation/sprite_animation.py (already complete)
- systems/attack_effects.py (already complete)

---

## Implementation Order Recommendation

1. **Section A** — pygame-ce swap (30 min)
2. **Section B** — Easing module (1 hr) — consolidates duplicated easing code
3. **Section E** — Damage number enhancement (1.5 hr) — immediate visual payoff
4. **Section F** — Screen effects system (2 hr) — immediate feel payoff
5. **Section H** — Telegraph improvements (1.5 hr) — polish existing
6. **Section C** — Animation controller enhancements (1.5 hr) — layers + JSON loading
7. **Section G** — Particle system enhancement (3 hr) — JSON emitters, continuous mode
8. **Section D** — Procedural animation extensions (2 hr) — death, dodge, hit_reaction

**Total estimated effort**: ~13 hours across all sections.
**Reduced from ~20 hours** thanks to existing animation/, combat_particles, weapon_visuals, and damage_number infrastructure.
