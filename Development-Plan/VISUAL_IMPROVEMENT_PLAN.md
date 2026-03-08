# Visual Improvement Plan — Tier 1 & Tier 2

**Status**: Ready for implementation
**Depends on**: Existing codebase (75K LOC), Development-Plan/PART_1_COMBAT_VISUALS.md
**Scope**: Tier 1 (low risk, high value) and Tier 2 (medium effort, high value) from animation research
**Philosophy**: New modules only, JSON-driven data, minimal changes to existing code
**Last Updated**: 2026-03-08

---

## Table of Contents

1. [Section A — pygame-ce Migration](#section-a--pygame-ce-migration)
2. [Section B — Easing & Tweening Foundation](#section-b--easing--tweening-foundation)
3. [Section C — Frame-Based Animation Controller](#section-c--frame-based-animation-controller)
4. [Section D — Procedural Combat Animations](#section-d--procedural-combat-animations)
5. [Section E — Floating Combat Text (Damage Numbers)](#section-e--floating-combat-text-damage-numbers)
6. [Section F — Screen Effects System](#section-f--screen-effects-system)
7. [Section G — Combat Particle System](#section-g--combat-particle-system)
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

## Section C — Frame-Based Animation Controller

**Priority**: Tier 1 — Core foundation
**Risk**: Low (new module, renderer integration is additive)
**Effort**: ~3 hours
**New files**: `animation/sprite_animation.py`, `animation/animation_manager.py`
**Modified file**: `rendering/renderer.py` (additive — new method, not replacing existing)

### What

A state machine that sequences sprite frames with per-frame timing, events, and transitions. This is the backbone for all sprite-based animations (idle bob, attack swings, hit reactions, death).

### Architecture

```
animation/
├── __init__.py
├── easing.py                  # (Section B)
├── sprite_animation.py        # AnimationFrame, AnimationDefinition, SpriteAnimation
└── animation_manager.py       # AnimationManager singleton
```

### Core Data Structures

```python
@dataclass
class AnimationFrame:
    """Single frame of animation."""
    surface: pygame.Surface        # The rendered frame (or None for procedural)
    duration_ms: float             # How long this frame is shown
    offset_x: float = 0.0         # Pixel offset from entity center
    offset_y: float = 0.0
    rotation: float = 0.0         # Degrees of rotation for this frame
    scale: float = 1.0            # Scale multiplier
    alpha: int = 255              # Transparency (0=invisible, 255=opaque)
    event: Optional[str] = None   # Event fired when this frame starts ("hit", "sound", etc.)


@dataclass
class AnimationDefinition:
    """Complete animation sequence. Loaded from JSON or generated procedurally."""
    animation_id: str
    frames: List[AnimationFrame]
    loop: bool = False
    total_duration_ms: float = 0   # Computed from frames


class SpriteAnimation:
    """Plays an AnimationDefinition. Tracks current frame, elapsed time, events."""
    def __init__(self, definition: AnimationDefinition)
    def update(self, dt_ms: float) -> List[str]   # Returns events fired this frame
    def get_current_frame(self) -> AnimationFrame
    @property
    def is_complete(self) -> bool
    def reset(self) -> None
```

### AnimationManager (Singleton)

```python
class AnimationManager:
    """Global animation manager. Updated once per game loop tick."""
    _instance = None

    def play(self, entity_id: str, animation: SpriteAnimation,
             layer: str = 'default', blend_mode: str = 'replace') -> None

    def stop(self, entity_id: str, layer: str = 'default') -> None

    def update(self, dt_ms: float) -> Dict[str, List[str]]
        # Returns {entity_id: [events_fired]} for all active animations

    def get_frame(self, entity_id: str, layer: str = 'default') -> Optional[AnimationFrame]
        # Returns current frame for renderer to draw

    def is_playing(self, entity_id: str, layer: str = 'default') -> bool
```

### Layer System

Each entity can have multiple simultaneous animation layers:
- `'body'` — Base sprite animation (idle, walk, hit)
- `'weapon'` — Weapon swing overlay
- `'effect'` — Visual effect overlay (glow, flash)

Layers composite in order: body → weapon → effect.

### Renderer Integration

Add a single new method to `renderer.py` (does NOT replace existing drawing):

```python
def _draw_animated_entity(self, surface, entity, screen_pos):
    """Draw entity with animation overrides if any are playing.
    Called from existing entity drawing code — falls through to
    static sprite if no animation is active."""
    anim_mgr = AnimationManager.get_instance()
    frame = anim_mgr.get_frame(entity.entity_id)
    if frame is None:
        return False  # No animation — caller draws static sprite
    # Apply frame transforms (offset, rotation, scale, alpha) and blit
    ...
    return True  # Animation handled drawing
```

### JSON Schema (Animation-Data.JSON/)

```json
{
  "animations": {
    "idle_bob": {
      "loop": true,
      "frames": [
        {"offset_y": 0, "duration_ms": 200},
        {"offset_y": -2, "duration_ms": 200},
        {"offset_y": 0, "duration_ms": 200},
        {"offset_y": 1, "duration_ms": 200}
      ]
    },
    "hit_flash": {
      "loop": false,
      "frames": [
        {"alpha": 255, "scale": 1.05, "duration_ms": 50, "event": "flash_white"},
        {"alpha": 200, "scale": 1.0, "duration_ms": 50},
        {"alpha": 255, "scale": 1.0, "duration_ms": 100}
      ]
    }
  }
}
```

### Verification

- AnimationManager.play() → update() → get_frame() returns correct frames
- Frame events fire at correct times
- Looping animations restart correctly
- Non-looping animations report is_complete
- Renderer falls through to static sprite when no animation is active

---

## Section D — Procedural Combat Animations

**Priority**: Tier 2 — Build during combat overhaul
**Risk**: Medium (interacts with combat state machine)
**Effort**: ~4 hours
**New file**: `animation/procedural_animations.py`
**Depends on**: Section B (easing), Section C (animation controller)

### What

Generate animation frames procedurally from static sprites. Instead of requiring hand-drawn sprite sheets (which don't exist — the game has 3,749 static PNGs), this creates attack swings, hit reactions, idle bobs, and death animations by applying transforms (rotation, scale, offset, alpha, tint) to existing sprites using easing curves.

### Core Factory Functions

```python
class ProceduralAnimations:
    """Factory for creating animations from static sprites using easing curves."""

    @staticmethod
    def create_weapon_swing(
        weapon_surface: pygame.Surface,
        arc_start: float,           # Starting angle (degrees)
        arc_end: float,             # Ending angle
        duration_ms: float,         # Total swing time
        easing: Callable = ease_in_out_quad,
        num_frames: int = 8,
    ) -> AnimationDefinition:
        """Create a weapon swing animation through an arc.

        The weapon sprite rotates from arc_start to arc_end over duration_ms.
        Easing controls the acceleration curve (fast start = slash,
        slow start = heavy overhead).
        """

    @staticmethod
    def create_hit_reaction(
        entity_surface: pygame.Surface,
        knockback_px: float = 8.0,     # Pixels of knockback
        flash_color: Tuple = (255, 255, 255),
        duration_ms: float = 200.0,
        easing: Callable = ease_out_elastic,
    ) -> AnimationDefinition:
        """White flash + knockback settle. Used when entity takes damage."""

    @staticmethod
    def create_windup_pulse(
        entity_surface: pygame.Surface,
        scale_peak: float = 1.15,       # Max scale during windup
        glow_color: Tuple = (255, 100, 100),
        duration_ms: float = 500.0,
    ) -> AnimationDefinition:
        """Scale pulse + color tint for attack telegraph on the entity itself.
        Grows slightly during windup, giving visual "charging" feel."""

    @staticmethod
    def create_death_fade(
        entity_surface: pygame.Surface,
        duration_ms: float = 800.0,
        collapse: bool = True,         # Shrink vertically as well
    ) -> AnimationDefinition:
        """Fade out + optional vertical collapse for death animation."""

    @staticmethod
    def create_idle_bob(
        amplitude_px: float = 2.0,
        period_ms: float = 800.0,
    ) -> AnimationDefinition:
        """Subtle vertical bob for idle entities. Loop animation."""

    @staticmethod
    def create_dodge_roll(
        direction_angle: float,
        distance_px: float = 48.0,
        duration_ms: float = 250.0,
    ) -> AnimationDefinition:
        """Roll animation: rotation + position offset in direction."""
```

### Weapon Type → Animation Mapping

Derived from existing weapon data (no JSON changes needed):

| Weapon Category | Arc Start | Arc End | Duration | Easing | Feel |
|----------------|-----------|---------|----------|--------|------|
| sword_1h | -45° | +45° | 350ms | ease_in_out_quad | Balanced swing |
| sword_2h | -60° | +60° | 550ms | ease_in_quad | Heavy, committal |
| dagger | -30° | +30° | 220ms | ease_out_quad | Fast slash |
| axe_1h | -50° | +50° | 400ms | ease_in_cubic | Heavy start, fast finish |
| hammer | +90° | -30° | 600ms | ease_in_expo | Overhead slam |
| staff | -20° | +20° | 380ms | ease_in_out_quad | Quick poke |
| bow | 0° | 0° | 400ms | linear | Drawback + release (scale-based) |

### Integration with Attack Profile Generator

The existing `EnemyAttackDef` already has `shape`, `arc`, and timing. Procedural animations read these directly:

```python
def create_enemy_attack_animation(attack_def: EnemyAttackDef,
                                   enemy_surface: pygame.Surface) -> AnimationDefinition:
    """Generate attack animation from the attack profile generator's output.

    No additional data needed — the generator already computed shape, arc,
    windup timing, etc. from the enemy's JSON fields.
    """
    if attack_def.shape == 'arc':
        return ProceduralAnimations.create_weapon_swing(
            enemy_surface,
            arc_start=-attack_def.arc / 2,
            arc_end=attack_def.arc / 2,
            duration_ms=attack_def.active,
        )
    elif attack_def.shape == 'circle':
        return ProceduralAnimations.create_windup_pulse(
            enemy_surface,
            scale_peak=1.2,
            duration_ms=attack_def.windup,
        )
```

### Verification

- Weapon swing rotates smoothly through arc
- Hit reaction flashes white and settles
- Windup pulse is visible and matches attack timing
- Death fade completes and entity is invisible at end
- Idle bob loops seamlessly

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

## Section G — Combat Particle System

**Priority**: Tier 2 — Medium effort, high value
**Risk**: Medium (performance sensitive)
**Effort**: ~5 hours
**New files**: `animation/particles.py`, `Animation-Data.JSON/particle-emitters.json`
**Depends on**: Section B (easing)
**Builds on**: `core/minigame_effects.py` (existing particle system, ~2,000 lines)

### What

A generalized, JSON-driven particle system for combat effects: hit sparks, blood/slime splatter, magic trails, status effect auras, death bursts. Built by extracting and generalizing patterns from the existing `minigame_effects.py`.

### Why Not Just Use minigame_effects.py?

The existing system is tightly coupled to crafting minigame UI coordinates and effects. Combat particles need:
- World-space positioning (follows camera)
- Tag-driven appearance (fire particles look different from ice)
- JSON-driven emitter definitions (consistent with project philosophy)
- Performance budget awareness (combat has more simultaneous effects)

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
├── __init__.py                      # Section B
├── easing.py                        # Section B — Easing functions + Tween
├── sprite_animation.py              # Section C — AnimationFrame, SpriteAnimation
├── animation_manager.py             # Section C — AnimationManager singleton
├── procedural_animations.py         # Section D — Factory for procedural anims
├── screen_effects.py                # Section F — Shake, pause, flash, slow-mo
└── particles.py                     # Section G — ParticleSystem, Emitter, Particle

combat/
└── damage_numbers.py                # Section E — Floating combat text

Animation-Data.JSON/
├── attack-animations.json           # Section C/D — Animation definitions
└── particle-emitters.json           # Section G — Particle emitter configs
```

### Modified Files (Minimal Additions)

```
rendering/renderer.py
  + _draw_animated_entity()          # Section C — Animation-aware entity drawing
  + _draw_damage_numbers()           # Section E — Floating text draw pass
  + _draw_telegraph_arc() improved   # Section H — Better telegraph visuals
  + _draw_particles()                # Section G — Particle draw pass

Combat/combat_manager.py
  + DamageNumberSystem.spawn(...)    # Section E — 1 line after damage applied
  + ParticleSystem.emit(...)         # Section G — 1 line after damage applied
  + ScreenEffects.shake(...)         # Section F — 1 line on hit events

core/camera.py
  (already has shake_offset)         # Section F — ScreenEffects sets this

core/game_engine.py
  + AnimationManager.update(dt)      # Section C — 1 line in game loop
  + ScreenEffects.update(dt)         # Section F — 1 line in game loop
  + ParticleSystem.update(dt)        # Section G — 1 line in game loop
  + DamageNumberSystem.update(dt)    # Section E — 1 line in game loop
```

### Existing Files NOT Touched

- All JSON files (hostiles, recipes, items, skills, etc.)
- Combat/enemy.py (attack profiles generated separately)
- Combat/attack_profile_generator.py (provides data, doesn't render)
- All crafting minigame files
- Save system
- Entity models

---

## Implementation Order Recommendation

1. **Section A** — pygame-ce swap (30 min)
2. **Section B** — Easing module (1 hr)
3. **Section E** — Damage numbers (2 hr) — immediate visual payoff
4. **Section F** — Screen effects (2 hr) — immediate feel payoff
5. **Section H** — Telegraph improvements (2 hr) — polish existing
6. **Section C** — Animation controller (3 hr) — foundation for D
7. **Section G** — Particle system (5 hr) — eye candy
8. **Section D** — Procedural animations (4 hr) — full animation system

**Total estimated effort**: ~20 hours across all sections.
