# Combat Visuals — Detailed Action Plan

**Purpose**: This is the exact implementation blueprint for transforming click-to-attack into action combat. Every section specifies what code to write, where it goes, and how it connects to existing systems. The next task after this plan is to write the code directly from these instructions.

**Scope**: Animation framework, attack state machine, hitboxes, projectiles, dodge, enemy scaling, screen effects.

**Guiding Principle**: The damage pipeline is sacred. We control WHEN damage fires, never HOW it calculates.

---

## Table of Contents

1. [Foundation: File Structure & Bootstrapping](#1-foundation)
2. [Animation System](#2-animation-system)
3. [Attack State Machine](#3-attack-state-machine)
4. [Hitbox & Hurtbox System](#4-hitbox-system)
5. [Projectile System](#5-projectile-system)
6. [Player Actions: Dodge & Input Buffer](#6-player-actions)
7. [Enemy Tier Scaling & Attack Patterns](#7-enemy-scaling)
8. [Screen Effects & Visual Polish](#8-screen-effects)
9. [Renderer Integration](#9-renderer-integration)
10. [Game Engine Integration](#10-engine-integration)
11. [JSON Data Files](#11-json-data)
12. [Migration Strategy: Legacy Coexistence](#12-migration)
13. [Testing Checkpoints](#13-testing)

---

## 1. Foundation: File Structure & Bootstrapping

### 1.1 New Directory Layout

All new combat visual code lives in two new packages inside `Game-1-modular/`:

```
Game-1-modular/
├── animation/                          # NEW PACKAGE
│   ├── __init__.py                     # Exports: AnimationManager, SpriteAnimation, ProceduralAnimations
│   ├── animation_data.py              # AnimationFrame, AnimationDefinition dataclasses
│   ├── sprite_animation.py            # SpriteAnimation player class
│   ├── animation_manager.py           # Global singleton registry
│   ├── procedural.py                  # ProceduralAnimations — generates frames from static sprites
│   └── combat_particles.py            # CombatParticleSystem — world-space particles for VFX
│
├── combat/                             # NEW PACKAGE (lowercase, distinct from existing Combat/)
│   ├── __init__.py                     # Exports: AttackStateMachine, HitboxSystem, ProjectileSystem, etc.
│   ├── attack_state_machine.py        # AttackPhase enum, AttackDefinition, AttackStateMachine
│   ├── hitbox_system.py               # HitboxShape, HitboxDefinition, ActiveHitbox, Hurtbox, HitboxSystem
│   ├── projectile_system.py           # ProjectileDefinition, Projectile, ProjectileSystem
│   ├── player_actions.py             # PlayerActionSystem (dodge, i-frames), InputBuffer
│   ├── screen_effects.py             # ScreenEffects (shake, flash, hit pause, slow motion)
│   ├── combat_data_loader.py         # Loads attack-animations.json, enemy-attacks.json, projectiles.json
│   └── combat_event.py               # CombatEvent dataclass — communication between systems
│
├── Animation-Data.JSON/               # NEW DATA DIRECTORY
│   ├── weapon-attacks.json            # Per-weapon-type attack timing and hitbox definitions
│   ├── enemy-attacks.json             # Per-enemy attack patterns, windups, hitboxes
│   └── projectile-definitions.json    # Projectile speed, range, hitbox, trail
│
├── Combat/                             # EXISTING — minimal modifications
│   ├── combat_manager.py              # Add USE_ACTION_COMBAT flag, delegate to state machine when on
│   └── enemy.py                        # Add attack_state_machine field, facing_angle, hurtbox_radius
```

### 1.2 Why Two Packages (animation/ vs combat/)

`animation/` is **pure visual** — sprite frames, procedural generation, particle effects. It has zero knowledge of damage, health, or game logic. It could animate a menu or a crafting minigame just as well.

`combat/` is **game logic** — attack phases, collision detection, damage timing. It references `animation/` to trigger visual effects, but animation never imports combat.

Dependency flow:
```
JSON data → combat/combat_data_loader.py → combat/* systems
                                         → animation/* visuals
game_engine.py → combat/* (update logic)
                → animation/* (render logic)
renderer.py → animation/* (get current frames, draw debug)
```

### 1.3 The Existing `Combat/` Directory (Capital C)

The existing `Combat/` package contains `combat_manager.py` and `enemy.py`. We do NOT move, rename, or restructure these files. We modify them minimally:

**combat_manager.py changes**:
- Add `USE_ACTION_COMBAT = True` flag at module level (can be set to False to revert)
- In `player_attack_enemy()` and `player_attack_enemy_with_tags()`: when flag is True, route through AttackStateMachine instead of instant damage
- Add `process_attack_hit()` method that the hitbox system calls when a hit lands — this method calls the existing `calculate_hit_damage()` pipeline unchanged

**enemy.py changes**:
- Add `self.attack_state_machine: Optional[AttackStateMachine] = None` field to Enemy
- Add `self.facing_angle: float = 0.0` — computed from movement direction each frame
- Add `self.hurtbox_radius: float = 0.5` — derived from tier (T1=0.5, T2=0.65, T3=0.8, T4=1.0)
- In `update_ai()`: compute `facing_angle` from `(player_pos - self.position)` when in CHASE/ATTACK states

### 1.4 Bootstrapping: How Systems Initialize

Initialization happens in `game_engine.py.__init__()`, after existing systems are created:

```python
# After combat_manager is created (around line 170 of __init__):
from combat.hitbox_system import HitboxSystem
from combat.projectile_system import ProjectileSystem
from combat.attack_state_machine import AttackStateMachine
from combat.player_actions import PlayerActionSystem
from combat.screen_effects import ScreenEffects
from combat.combat_data_loader import CombatDataLoader
from animation.animation_manager import AnimationManager

# Load JSON data
self.combat_data = CombatDataLoader(self.resource_path)
self.combat_data.load_all()

# Initialize systems
self.animation_manager = AnimationManager.get_instance()
self.hitbox_system = HitboxSystem()
self.projectile_system = ProjectileSystem(self.hitbox_system)
self.player_actions = PlayerActionSystem(self.character)
self.screen_effects = ScreenEffects()

# Register player hurtbox
self.hitbox_system.register_hurtbox('player', radius=0.35)

# Player gets an attack state machine
self.player_attack_sm = AttackStateMachine('player')
```

Enemy attack state machines are created per-enemy in `combat_manager.spawn_enemies_in_chunk()` — each Enemy gets its own `AttackStateMachine` instance.

### 1.5 System Update Order (Per Frame)

In `game_engine.update()`, the new systems update in this order:

```python
# 1. Input processing (existing) — captures attack intent, dodge intent
# 2. Player movement (existing) — WASD movement, encumbrance

# 3. NEW: Player action system — dodge roll physics, i-frame timer
self.player_actions.update(dt_ms)

# 4. NEW: Player attack state machine — advance windup/active/recovery phases
player_events = self.player_attack_sm.update(dt_ms)

# 5. NEW: Enemy attack state machines — advance their phases too
#    (inside combat_manager.update, enemies update their own ASMs)

# 6. NEW: Hitbox system — check all active hitbox vs hurtbox collisions
hit_events = self.hitbox_system.update(dt_ms)

# 7. NEW: Process hits — route through existing damage pipeline
for hit in hit_events:
    self.combat_manager.process_attack_hit(hit)

# 8. NEW: Projectile system — move projectiles, check collisions
proj_hits = self.projectile_system.update(dt_ms)
for hit in proj_hits:
    self.combat_manager.process_attack_hit(hit)

# 9. Existing: combat_manager.update() — enemy AI, spawning, corpses
# 10. Existing: character cooldowns, health regen, buffs, knockback

# 11. NEW: Animation manager — advance all animation timers
self.animation_manager.update_all(dt_ms)

# 12. NEW: Screen effects — decay shake, flash, hit pause timers
self.screen_effects.update(dt_ms)
```

### 1.6 Position Format Reconciliation

**The problem**: Player uses `Position(x, y, z)` dataclass. Enemies use `list([x, y])`. The hitbox system needs a uniform interface.

**The solution**: The hitbox system works in raw `(float, float)` tuples internally. Conversion happens at the boundary:

```python
# Player position → tuple
player_pos = (character.position.x, character.position.y)

# Enemy position → tuple
enemy_pos = (enemy.position[0], enemy.position[1])
```

The `Hurtbox` class stores `world_x, world_y` as plain floats, updated each frame from the owning entity's position. No new Position types.

### 1.7 Facing Direction: Strings to Angles

The player currently tracks facing as a string: `"up"`, `"down"`, `"left"`, `"right"`. The hitbox system needs angles in degrees for arc-shaped hitboxes.

```python
FACING_TO_ANGLE = {
    'right': 0.0,
    'down': 90.0,
    'left': 180.0,
    'up': 270.0,
}
```

For enemies, `facing_angle` is computed directly from the vector toward their target:
```python
facing_angle = math.degrees(math.atan2(target_y - self.position[1], target_x - self.position[0]))
```

We also add `self.facing_angle` to the Character class, updated alongside `self.facing` in the move method, and optionally from mouse position during combat (so the player swings toward where they clicked, not where they walked).

---

## 2. Animation System

### 2.1 The Core Problem

We have 16 enemy sprites — each a single static 1024x1024 JPEG. No sprite sheets, no animation frames, no weapon swing art. The player is a colored circle. We need to make combat *feel* visceral using only these assets plus procedurally generated effects.

This means our animation system is fundamentally **procedural**: rotations, scale pulses, color tints, arc trails, and particle bursts — not hand-drawn frame sequences. The architecture still supports traditional sprite sheets (for future art), but day-one everything is generated.

### 2.2 animation/animation_data.py — Data Structures

```python
@dataclass
class AnimationFrame:
    surface: pygame.Surface        # The rendered frame (pre-computed or generated)
    duration_ms: float             # How long this frame displays
    offset_x: float = 0.0         # Pixel offset from entity center (for swing arcs)
    offset_y: float = 0.0
    hitbox_active: bool = False    # Whether the attack hitbox is live during this frame
    scale: float = 1.0            # Scale multiplier applied to entity

@dataclass
class AnimationDefinition:
    animation_id: str              # e.g., "sword_1h_swing", "wolf_bite_windup"
    frames: List[AnimationFrame]
    loop: bool = False             # True for idle/walk, False for attacks
    total_duration_ms: float = 0.0 # Computed: sum of frame durations

    def __post_init__(self):
        self.total_duration_ms = sum(f.duration_ms for f in self.frames)
```

**Why pre-computed surfaces?** Calling `pygame.transform.rotozoom()` every frame is expensive. We generate all rotated/tinted frames once when the animation is created, then just blit the cached surface each frame. A 6-frame sword swing with pre-rendered surfaces costs ~6 surface blits total over 350ms — negligible.

### 2.3 animation/sprite_animation.py — The Player

```python
class SpriteAnimation:
    """Plays an AnimationDefinition instance. One per active animation."""

    def __init__(self, definition: AnimationDefinition, on_complete: Optional[Callable] = None):
        self.definition = definition
        self.on_complete = on_complete
        self.elapsed_ms: float = 0.0
        self.current_frame_index: int = 0
        self.finished: bool = False

    def update(self, dt_ms: float) -> None:
        """Advance animation by dt milliseconds."""
        if self.finished:
            return

        self.elapsed_ms += dt_ms

        # Advance frames
        accumulated = 0.0
        for i, frame in enumerate(self.definition.frames):
            accumulated += frame.duration_ms
            if self.elapsed_ms < accumulated:
                self.current_frame_index = i
                return

        # Reached end
        if self.definition.loop:
            self.elapsed_ms %= self.definition.total_duration_ms
            self.current_frame_index = 0
        else:
            self.finished = True
            self.current_frame_index = len(self.definition.frames) - 1
            if self.on_complete:
                self.on_complete()

    def get_current_frame(self) -> AnimationFrame:
        return self.definition.frames[self.current_frame_index]

    @property
    def is_hitbox_active(self) -> bool:
        return self.get_current_frame().hitbox_active

    def reset(self) -> None:
        self.elapsed_ms = 0.0
        self.current_frame_index = 0
        self.finished = False
```

### 2.4 animation/animation_manager.py — Global Registry

```python
class AnimationManager:
    """Singleton. Maps entity_id → active SpriteAnimation."""
    _instance = None

    def __init__(self):
        self._animations: Dict[str, SpriteAnimation] = {}
        self._definitions: Dict[str, AnimationDefinition] = {}  # loaded from JSON

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_definition(self, definition: AnimationDefinition) -> None:
        self._definitions[definition.animation_id] = definition

    def play(self, entity_id: str, anim_id: str, on_complete: Callable = None) -> None:
        defn = self._definitions.get(anim_id)
        if defn:
            self._animations[entity_id] = SpriteAnimation(defn, on_complete)

    def stop(self, entity_id: str) -> None:
        self._animations.pop(entity_id, None)

    def update_all(self, dt_ms: float) -> None:
        dead = []
        for entity_id, anim in self._animations.items():
            anim.update(dt_ms)
            if anim.finished:
                dead.append(entity_id)
        for eid in dead:
            del self._animations[eid]

    def get_current_frame(self, entity_id: str) -> Optional[AnimationFrame]:
        anim = self._animations.get(entity_id)
        if anim and not anim.finished:
            return anim.get_current_frame()
        return None

    def is_animating(self, entity_id: str) -> bool:
        return entity_id in self._animations
```

### 2.5 animation/procedural.py — The Heart of the Visual System

This is where the magic happens. Since we have no sprite sheets, we generate animation frames programmatically.

**Key methods:**

#### Weapon Swing Arc
For melee attacks. Takes the weapon sprite (or a generated slash shape) and rotates it through an arc.

```python
@staticmethod
def create_swing_arc(base_sprite: Surface, arc_degrees: float,
                     duration_ms: float, num_frames: int,
                     pivot_distance: float = 0.0) -> AnimationDefinition:
    """
    Generate frames of a weapon swinging through an arc.

    base_sprite: The weapon or slash image
    arc_degrees: Total arc (e.g., 90° for a sword swing)
    duration_ms: Total animation time
    num_frames: How many frames to generate
    pivot_distance: How far from entity center the sprite orbits (pixels)

    Frame generation:
    - start_angle = -arc_degrees / 2
    - end_angle = +arc_degrees / 2
    - For each frame, compute rotation angle via ease-out interpolation
    - Rotate sprite with pygame.transform.rotozoom()
    - Compute offset from center based on angle and pivot_distance
    - Middle frames get hitbox_active = True
    """
```

The ease-out curve makes the swing accelerate out of windup and decelerate into recovery — matching the feel of a real weapon swing. Linear rotation looks robotic.

#### Enemy Telegraph Pulse
For enemy windup phases. The enemy sprite scales up slightly and gets a colored tint.

```python
@staticmethod
def create_telegraph_pulse(base_sprite: Surface, tint_color: Tuple[int,int,int],
                          scale_range: Tuple[float, float],
                          duration_ms: float, num_frames: int) -> AnimationDefinition:
    """
    Generate frames of an enemy 'charging up' before attacking.

    tint_color: (255, 100, 0) for fire, (100, 100, 255) for ice, etc.
    scale_range: (1.0, 1.15) — subtle grow during windup

    Frame generation:
    - Progress 0→1 over duration
    - Scale: lerp(scale_range[0], scale_range[1], progress)
    - Tint: blend base_sprite with tint_color, intensity = progress * 0.4
    - Apply via per-pixel color multiply on a copy of base_sprite
    """
```

The tint is the primary readability tool. When a wolf starts glowing red, the player learns "it's about to bite." When a golem pulses with brown/orange, "slam incoming."

#### Hit Flash
When an entity takes damage, its sprite flashes white for ~80ms.

```python
@staticmethod
def create_hit_flash(base_sprite: Surface, flash_color: Tuple[int,int,int] = (255, 255, 255),
                     duration_ms: float = 80.0) -> AnimationDefinition:
    """
    2 frames: full-white tinted sprite, then original.

    Implementation:
    - Create white version: fill a copy with flash_color, blit original with BLEND_RGB_ADD
    - Frame 1: white version (duration_ms * 0.6)
    - Frame 2: original sprite (duration_ms * 0.4)
    """
```

#### Idle Bob
Subtle vertical oscillation to make entities feel alive.

```python
@staticmethod
def create_idle_bob(base_sprite: Surface, amplitude_px: float = 2.0,
                    period_ms: float = 1200.0, num_frames: int = 8) -> AnimationDefinition:
    """
    Looping animation. Sprite moves up/down by amplitude pixels.
    Uses sine wave for smooth motion.

    Frame offsets: offset_y = amplitude * sin(2π * frame_index / num_frames)
    Surface is the same for all frames — only offset changes.
    """
```

#### Slash Trail (Procedural Geometry)
For the actual visible "slash" during a melee attack — a crescent arc drawn procedurally.

```python
@staticmethod
def create_slash_trail(arc_degrees: float, radius_px: float,
                       color: Tuple[int,int,int], thickness: int = 3,
                       duration_ms: float = 150.0, num_frames: int = 4) -> AnimationDefinition:
    """
    Draws an expanding arc/crescent that represents the weapon swing path.
    NOT the weapon itself — this is the trail the blade leaves.

    Frame generation:
    - Each frame draws a wider portion of the arc
    - Frame 1: 25% of arc, thin, full alpha
    - Frame 2: 60% of arc, medium, 90% alpha
    - Frame 3: 100% of arc, thick, 70% alpha
    - Frame 4: 100% of arc, thin, 30% alpha (fading out)

    Rendering: pygame.draw.arc() on SRCALPHA surface, centered on entity
    """
```

### 2.6 animation/combat_particles.py — World-Space Particles

Separate from minigame particles (which render in UI-space). Combat particles exist in world coordinates and move with the camera.

```python
class CombatParticleSystem:
    """World-space particle system for combat VFX."""

    def __init__(self, max_particles: int = 400):
        self.particles: List[CombatParticle] = []
        self.max_particles = max_particles

    def emit_hit_sparks(self, world_x: float, world_y: float,
                        damage_type: str, intensity: float) -> None:
        """Burst of sparks at hit location. Color based on damage type."""

    def emit_slash_trail(self, world_x: float, world_y: float,
                         angle: float, arc_degrees: float, radius: float) -> None:
        """Particles along a slash arc path."""

    def emit_blood_splatter(self, world_x: float, world_y: float,
                            direction: float, amount: int = 5) -> None:
        """Directional blood/damage particles on hit."""

    def emit_dodge_dust(self, world_x: float, world_y: float) -> None:
        """Small dust cloud at dodge start position."""

    def update(self, dt_ms: float) -> None:
        """Update all particles, remove dead ones."""

    def render(self, screen: Surface, camera) -> None:
        """Convert world positions to screen, draw all particles."""
```

Particle types reuse the architecture from `minigame_effects.py` (gravity, drag, alpha decay, SRCALPHA surfaces) but operate in world coordinates. The `render()` method calls `camera.world_to_screen()` per particle.

### 2.7 Performance Considerations

**Surface caching**: Every `ProceduralAnimations.create_*()` method returns an `AnimationDefinition` with pre-rendered frames. These are generated once (on first use or during loading) and cached in `AnimationManager._definitions`. A sword swing generates 6 surfaces once — the cost is paid at load time, not per frame.

**Particle budget**: `max_particles=400`. At 60fps, updating 400 particles with simple physics (position += velocity, alpha decay) costs <1ms. Each particle draws one small SRCALPHA surface blit. Budget is well within 16.67ms frame time.

**No per-frame transforms**: We never call `rotozoom()` during the game loop. All rotated frames are pre-computed. The only per-frame cost is selecting which cached frame to blit.

---

## 3. Attack State Machine

### 3.1 What Changes and What Doesn't

**What changes**: The *timing* of when damage is calculated. Currently, left-click → instant damage. After this, left-click → enter WINDUP → hitbox appears during ACTIVE → damage only on collision → RECOVERY → IDLE.

**What does NOT change**: The actual damage formula. `player_attack_enemy()` and `player_attack_enemy_with_tags()` still compute the exact same numbers. The state machine calls into them at the right moment instead of the game engine calling them directly.

### 3.2 combat/combat_event.py — Inter-System Communication

```python
@dataclass
class CombatEvent:
    """Emitted by combat systems for other systems to react to."""
    event_type: str          # "phase_change", "hit_landed", "attack_start", "projectile_spawn"
    source_id: str           # Entity that caused this event
    target_id: Optional[str] = None
    data: Optional[dict] = None  # Event-specific payload

@dataclass
class HitEvent:
    """Emitted when a hitbox overlaps a hurtbox."""
    attacker_id: str
    target_id: str
    hitbox: 'ActiveHitbox'         # The hitbox that made contact
    damage_context: dict           # Preserved from attack start: weapon tags, enchantments, etc.
    hit_position: Tuple[float, float]  # World position of the hit
```

`HitEvent` is the bridge between the hitbox system and the damage pipeline. When the HitboxSystem detects overlap, it emits a `HitEvent`. The game engine routes this to `combat_manager.process_attack_hit()`, which runs the existing damage formula.

### 3.3 combat/attack_state_machine.py — Core Logic

```python
class AttackPhase(Enum):
    IDLE = "idle"
    WINDUP = "windup"        # Telegraph visible, can be interrupted
    ACTIVE = "active"        # Hitbox is live
    RECOVERY = "recovery"   # Follow-through, vulnerable
    COOLDOWN = "cooldown"   # Brief lockout before next attack

@dataclass
class AttackDefinition:
    """Loaded from JSON. Defines one attack type."""
    attack_id: str
    windup_ms: float
    active_ms: float
    recovery_ms: float
    cooldown_ms: float
    hitbox_shape: str            # "circle", "arc", "rect", "line"
    hitbox_params: dict          # radius, arc_degrees, width, height, length, offset
    damage_multiplier: float     # Applied on top of base damage pipeline
    animation_id: str            # Which animation to play
    can_be_interrupted: bool     # Can stun/damage cancel the windup?
    movement_multiplier: float   # 0.5 = half speed during attack, 1.0 = full speed
    projectile_id: Optional[str] # If set, spawns projectile instead of melee hitbox
    status_tags: List[str]       # Tags to apply on hit (e.g., ["burn", "knockback"])
    screen_shake: bool           # Trigger screen shake on hit?
    combo_next: Optional[str]    # Next attack_id in combo chain (or None)
    combo_window_ms: float       # How long after recovery to accept combo input
```

The `AttackStateMachine` class:

```python
class AttackStateMachine:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.phase: AttackPhase = AttackPhase.IDLE
        self.phase_timer: float = 0.0
        self.current_attack: Optional[AttackDefinition] = None
        self.hits_this_swing: Set[str] = set()  # Prevent multi-hit per swing
        self.combo_count: int = 0
        self.combo_timer: float = 0.0
        self._pending_events: List[CombatEvent] = []
        self.damage_context: dict = {}  # Weapon data, tags, enchantments preserved from attack start

    def start_attack(self, attack_def: AttackDefinition, damage_context: dict) -> bool:
        """Begin attack if IDLE (or COOLDOWN with buffered combo).
        damage_context: preserved weapon/tag data for when the hit lands.
        Returns False if can't attack right now."""
        if self.phase not in (AttackPhase.IDLE, AttackPhase.COOLDOWN):
            return False
        # ... transition to WINDUP, store attack_def and context

    def update(self, dt_ms: float) -> List[CombatEvent]:
        """Advance the state machine. Returns events that occurred this frame."""
        events = []

        if self.phase == AttackPhase.IDLE:
            # Decay combo timer
            if self.combo_timer > 0:
                self.combo_timer -= dt_ms
                if self.combo_timer <= 0:
                    self.combo_count = 0  # Combo dropped
            return events

        self.phase_timer -= dt_ms

        if self.phase_timer <= 0:
            # Transition to next phase
            if self.phase == AttackPhase.WINDUP:
                self.phase = AttackPhase.ACTIVE
                self.phase_timer = self.current_attack.active_ms
                self.hits_this_swing.clear()
                events.append(CombatEvent("phase_change", self.entity_id,
                              data={"phase": "active"}))

            elif self.phase == AttackPhase.ACTIVE:
                self.phase = AttackPhase.RECOVERY
                self.phase_timer = self.current_attack.recovery_ms
                events.append(CombatEvent("phase_change", self.entity_id,
                              data={"phase": "recovery"}))

            elif self.phase == AttackPhase.RECOVERY:
                self.phase = AttackPhase.COOLDOWN
                self.phase_timer = self.current_attack.cooldown_ms
                # Start combo window
                self.combo_timer = self.current_attack.combo_window_ms
                events.append(CombatEvent("phase_change", self.entity_id,
                              data={"phase": "cooldown"}))

            elif self.phase == AttackPhase.COOLDOWN:
                self.phase = AttackPhase.IDLE
                self.current_attack = None
                events.append(CombatEvent("phase_change", self.entity_id,
                              data={"phase": "idle"}))

        return events

    def interrupt(self) -> bool:
        """Cancel during WINDUP (e.g., enemy got stunned). Returns success."""
        if self.phase == AttackPhase.WINDUP and self.current_attack.can_be_interrupted:
            self.phase = AttackPhase.IDLE
            self.current_attack = None
            return True
        return False

    def record_hit(self, target_id: str) -> bool:
        """Record that we hit this target. Returns False if already hit (prevent multi-hit)."""
        if target_id in self.hits_this_swing:
            return False
        self.hits_this_swing.add(target_id)
        return True

    @property
    def is_in_active_phase(self) -> bool:
        return self.phase == AttackPhase.ACTIVE

    @property
    def is_attacking(self) -> bool:
        return self.phase != AttackPhase.IDLE

    @property
    def is_vulnerable(self) -> bool:
        """True during RECOVERY — bonus damage window for counter-attacks."""
        return self.phase == AttackPhase.RECOVERY

    @property
    def movement_multiplier(self) -> float:
        if self.current_attack and self.phase in (AttackPhase.WINDUP, AttackPhase.ACTIVE, AttackPhase.RECOVERY):
            return self.current_attack.movement_multiplier
        return 1.0
```

### 3.4 How the Player Attack Flow Changes

**Current flow** (game_engine.py lines 6771-6812):
```
Left-click held → can_attack('mainHand') → get enemy at mouse → check range →
  player_attack_enemy_with_tags() → instant damage → reset_attack_cooldown
```

**New flow**:
```
Left-click → determine attack definition from equipped weapon →
  build damage_context (weapon tags, enchantments, hand) →
  player_attack_sm.start_attack(attack_def, damage_context)
    → if accepted: WINDUP begins
    → AnimationManager.play(player, swing_animation)
    → Spawn hitbox when ACTIVE phase begins (via CombatEvent)
    → HitboxSystem detects collision → emits HitEvent
    → combat_manager.process_attack_hit(hit_event) → existing damage pipeline
    → RECOVERY → COOLDOWN → IDLE
```

The key method that replaces the direct call:

```python
# In game_engine.py, replacing lines 6796-6802:
if USE_ACTION_COMBAT:
    weapon_type = self._get_weapon_type('mainHand')  # "sword_1h", "hammer_2h", etc.
    attack_def = self.combat_data.get_weapon_attack(weapon_type, self.player_attack_sm.combo_count)
    damage_context = {
        'hand': 'mainHand',
        'effect_tags': effect_tags,
        'effect_params': effect_params,
        'target_direction': (wx - self.character.position.x, wy - self.character.position.y),
    }
    self.player_attack_sm.start_attack(attack_def, damage_context)
else:
    # Legacy instant attack
    damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(...)
```

### 3.5 How Enemy Attacks Change

**Current flow** (combat_manager.py line 498-501):
```
enemy.can_attack() → dist <= 1.5 → _enemy_attack_player(enemy, shield_blocking)
  → instant damage
```

**New flow**:
```
enemy.can_attack() → dist <= attack_range →
  enemy.attack_state_machine.start_attack(enemy_attack_def, damage_context)
    → WINDUP: enemy telegraph animation plays (visual warning to player)
    → ACTIVE: hitbox spawned at enemy position with facing angle
    → HitboxSystem detects collision with player hurtbox
      → BUT: check player_actions.is_invulnerable() first (dodge i-frames)
      → If not invulnerable: combat_manager.process_enemy_hit(hit_event)
    → RECOVERY: enemy is vulnerable (player can counter-attack for bonus)
```

The combat_manager.update() method changes from calling `_enemy_attack_player()` directly to calling `enemy.attack_state_machine.start_attack()`. The actual damage path (`_enemy_attack_player()`) is called later by `process_enemy_hit()` when the hitbox system confirms a collision.

### 3.6 process_attack_hit() — The Bridge

This new method on CombatManager routes HitEvents to the correct damage path:

```python
def process_attack_hit(self, hit_event: HitEvent) -> None:
    """Called by game_engine when hitbox system detects a collision."""

    if hit_event.attacker_id == 'player':
        # Player hit an enemy
        enemy = self._find_enemy_by_id(hit_event.target_id)
        if enemy and enemy.is_alive:
            # Check if attack state machine allows this hit (prevent multi-hit)
            if not self.player_attack_sm.record_hit(hit_event.target_id):
                return  # Already hit this target this swing

            ctx = hit_event.damage_context
            # Route to existing damage pipeline
            damage, is_crit, loot = self.player_attack_enemy_with_tags(
                enemy, ctx['effect_tags'], ctx['effect_params']
            )

            # Apply attack definition's damage multiplier
            # (This is already factored into the hitbox — no double-application)

            # Emit visual effects
            self._on_player_hit(enemy, damage, is_crit, hit_event.hit_position)

    else:
        # Enemy hit the player
        enemy = self._find_enemy_by_id(hit_event.attacker_id)
        if enemy:
            # Check i-frames
            if self.player_actions.is_invulnerable:
                return  # Player dodged

            # Route to existing enemy damage pipeline
            self._enemy_attack_player(enemy, shield_blocking=self._current_shield_blocking)
```

The beauty here is that `player_attack_enemy_with_tags()` and `_enemy_attack_player()` are called exactly as before — same damage formula, same enchantment processing, same buff consumption. The only difference is *who* calls them and *when*.

### 3.7 Weapon Type to Attack Definition Mapping

The `CombatDataLoader` provides a mapping from weapon type strings to `AttackDefinition`:

```python
# Weapon type is derived from equipment tags
def _get_weapon_type(self, hand: str) -> str:
    weapon = self.character.equipment.slots.get(hand)
    if not weapon:
        return "unarmed"
    tags = weapon.get_metadata_tags() if hasattr(weapon, 'get_metadata_tags') else []
    if "two_handed" in tags and "hammer" in tags:
        return "hammer_2h"
    elif "two_handed" in tags:
        return "sword_2h"
    elif "ranged" in tags or "bow" in tags:
        return "bow"
    elif "staff" in tags or "magic" in tags:
        return "staff"
    elif "dagger" in tags:
        return "dagger"
    else:
        return "sword_1h"  # Default melee
```

Each weapon type maps to 1-3 AttackDefinitions (combo chain):
- `sword_1h` → swing_1, swing_2, heavy_finisher
- `dagger` → stab_1, stab_2, flurry
- `hammer_2h` → overhead_1, slam
- `bow` → draw_shot (spawns projectile)
- `staff` → cast (spawns projectile)
- `unarmed` → punch_1, punch_2, kick

### 3.8 Timing Feel — Why These Numbers Matter

Attack timings aren't arbitrary. They define the game's rhythm:

| Weapon | Total ms | Attacks/sec | Feel |
|--------|----------|-------------|------|
| Dagger (80+60+80) | 220ms | ~4.5 | Rapid, responsive. You press, it happens NOW. |
| Sword 1H (150+100+100) | 350ms | ~2.9 | Balanced. Slight commitment, but not punishing. |
| Sword 2H (250+120+180) | 550ms | ~1.8 | Heavy. You think before you swing. |
| Hammer (300+100+200) | 600ms | ~1.7 | Deliberate. Miss = punished. Land = devastating. |
| Bow (200+50+150) | 400ms | ~2.5 | Drawback → instant release → long follow-through. |

The WINDUP is the most important timing: it's the player's telegraph window for reading enemy attacks, and it's the commitment cost for the player's own attacks. Too short = no skill expression. Too long = sluggish and frustrating.

Enemy windups are intentionally longer than player windups (400ms for T1 wolf vs 150ms for sword). This asymmetry creates the core combat loop: the player is faster, but must read and dodge enemy telegraphs.

---

## 4. Hitbox & Hurtbox System

### 4.1 Conceptual Model

Every attack creates a **hitbox** — a geometric shape in world space that exists for a brief window (the ACTIVE phase). Every damageable entity has a **hurtbox** — a persistent circle representing their vulnerable area.

Each frame during ACTIVE phase:
1. For each active hitbox, check against every hurtbox
2. Skip if same owner (can't hit yourself)
3. Skip if already hit this swing (multi-hit prevention)
4. Skip if hurtbox is invulnerable (dodge i-frames)
5. If geometric overlap → emit HitEvent

This is fundamentally an N×M collision check. With <50 entities and typically 1-3 active hitboxes, this is well under budget.

### 4.2 Hitbox Shapes and Collision Math

All coordinates are in **world space** (tiles). All angles in **degrees**, with 0° = right, 90° = down (matching Pygame's y-down convention).

#### CIRCLE — Melee swings, explosions, AoE

```
Collision: distance(hitbox_center, hurtbox_center) < hitbox.radius + hurtbox.radius
```

The simplest and most common. Used for hammer slams, explosion AoE, large enemy stomps. No rotation needed.

#### ARC — Sword swings, cone attacks, breath weapons

An arc is a pie slice: a circle sector defined by center, radius, facing angle, and arc width.

```python
def _collides_arc_circle(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
    dx = hurtbox.world_x - hitbox.world_x
    dy = hurtbox.world_y - hitbox.world_y
    dist = math.sqrt(dx*dx + dy*dy)

    # Step 1: Distance check (treat arc as full circle first)
    if dist > hitbox.definition.radius + hurtbox.radius:
        return False

    # Step 2: Angle check — is the hurtbox center within the arc?
    angle_to_target = math.degrees(math.atan2(dy, dx))
    angle_diff = (angle_to_target - hitbox.facing_angle + 180) % 360 - 180
    half_arc = hitbox.definition.arc_degrees / 2.0

    if abs(angle_diff) > half_arc:
        # Hurtbox center is outside arc — but edge might still overlap
        # Check if the closest arc edge is within hurtbox.radius
        edge_angle = hitbox.facing_angle + (half_arc if angle_diff > 0 else -half_arc)
        edge_rad = math.radians(edge_angle)
        edge_x = hitbox.world_x + math.cos(edge_rad) * hitbox.definition.radius
        edge_y = hitbox.world_y + math.sin(edge_rad) * hitbox.definition.radius
        edge_dist = math.sqrt((hurtbox.world_x - edge_x)**2 + (hurtbox.world_y - edge_y)**2)
        return edge_dist < hurtbox.radius

    return True
```

Arc collision is the most important shape — sword swings are arcs. Getting this wrong means attacks miss when they look like they hit (or vice versa). The edge-case handling for hurtboxes near the arc boundary is critical.

#### RECT — Beam attacks, wide cleaves

Axis-aligned rectangle rotated by facing angle.

```python
def _collides_rect_circle(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
    # Rotate hurtbox position into hitbox's local space
    dx = hurtbox.world_x - hitbox.world_x
    dy = hurtbox.world_y - hitbox.world_y
    angle_rad = math.radians(-hitbox.facing_angle)
    local_x = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
    local_y = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)

    # Now check circle vs axis-aligned rect in local space
    half_w = hitbox.definition.width / 2.0
    half_h = hitbox.definition.height / 2.0

    # Closest point on rect to circle center
    closest_x = max(-half_w, min(local_x, half_w))
    closest_y = max(-half_h, min(local_y, half_h))

    dist_sq = (local_x - closest_x)**2 + (local_y - closest_y)**2
    return dist_sq < hurtbox.radius ** 2
```

#### LINE — Piercing attacks, laser beams

A line segment from origin in the facing direction.

```python
def _collides_line_circle(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
    # Line from hitbox center to hitbox center + direction * length
    angle_rad = math.radians(hitbox.facing_angle)
    end_x = hitbox.world_x + math.cos(angle_rad) * hitbox.definition.length
    end_y = hitbox.world_y + math.sin(angle_rad) * hitbox.definition.length

    # Closest point on line segment to circle center
    seg_dx = end_x - hitbox.world_x
    seg_dy = end_y - hitbox.world_y
    seg_len_sq = seg_dx*seg_dx + seg_dy*seg_dy

    if seg_len_sq == 0:
        # Degenerate line
        t = 0
    else:
        t = max(0, min(1, ((hurtbox.world_x - hitbox.world_x) * seg_dx +
                           (hurtbox.world_y - hitbox.world_y) * seg_dy) / seg_len_sq))

    closest_x = hitbox.world_x + t * seg_dx
    closest_y = hitbox.world_y + t * seg_dy

    dist_sq = (hurtbox.world_x - closest_x)**2 + (hurtbox.world_y - closest_y)**2
    return dist_sq < hurtbox.radius ** 2
```

### 4.3 Hitbox Positioning — Offset and Facing

A hitbox isn't centered on the attacker. A sword swing hitbox is centered *in front* of the attacker, offset by the weapon's reach.

```python
@dataclass
class HitboxDefinition:
    shape: str                   # "circle", "arc", "rect", "line"
    radius: float = 1.0         # tiles (circle, arc)
    width: float = 1.0          # tiles (rect)
    height: float = 0.5         # tiles (rect)
    arc_degrees: float = 90.0   # degrees (arc)
    length: float = 2.0         # tiles (line)
    offset_forward: float = 0.8 # tiles — how far in front of entity center
    offset_lateral: float = 0.0 # tiles — left/right offset
    follows_facing: bool = True # rotate with entity
    piercing: bool = False      # hit multiple targets?

def compute_world_position(self, entity_x: float, entity_y: float,
                           facing_angle: float) -> Tuple[float, float]:
    """Compute hitbox center in world space."""
    angle_rad = math.radians(facing_angle)
    wx = entity_x + math.cos(angle_rad) * self.offset_forward
    wy = entity_y + math.sin(angle_rad) * self.offset_forward
    # Lateral offset (perpendicular to facing)
    if self.offset_lateral != 0:
        wx += math.cos(angle_rad + math.pi/2) * self.offset_lateral
        wy += math.sin(angle_rad + math.pi/2) * self.offset_lateral
    return (wx, wy)
```

This means a sword_1h with `offset_forward=0.8` and `arc_degrees=90` creates a 90° pie slice centered 0.8 tiles in front of the player, facing wherever the player is looking. The slash trail animation is aligned to this same geometry.

### 4.4 HitboxSystem — The Manager

```python
class HitboxSystem:
    def __init__(self):
        self.active_hitboxes: List[ActiveHitbox] = []
        self.hurtboxes: Dict[str, Hurtbox] = {}  # entity_id → hurtbox

    def register_hurtbox(self, entity_id: str, radius: float) -> Hurtbox:
        hb = Hurtbox(entity_id, radius)
        self.hurtboxes[entity_id] = hb
        return hb

    def unregister_hurtbox(self, entity_id: str) -> None:
        self.hurtboxes.pop(entity_id, None)

    def spawn_hitbox(self, definition: HitboxDefinition, world_pos: Tuple[float, float],
                     facing: float, owner_id: str, duration_ms: float,
                     damage_context: dict) -> ActiveHitbox:
        hb = ActiveHitbox(definition, world_pos[0], world_pos[1], facing,
                          owner_id, duration_ms, damage_context)
        self.active_hitboxes.append(hb)
        return hb

    def update_hurtbox_positions(self, positions: Dict[str, Tuple[float, float]]) -> None:
        """Called each frame with entity_id → (world_x, world_y)."""
        for eid, (wx, wy) in positions.items():
            hb = self.hurtboxes.get(eid)
            if hb:
                hb.world_x = wx
                hb.world_y = wy

    def update(self, dt_ms: float) -> List[HitEvent]:
        """Advance hitbox timers, check collisions, return hits."""
        hits = []
        expired = []

        for hitbox in self.active_hitboxes:
            hitbox.remaining_ms -= dt_ms
            if hitbox.remaining_ms <= 0:
                expired.append(hitbox)
                continue

            for hurtbox in self.hurtboxes.values():
                # Skip self-hits
                if hurtbox.entity_id == hitbox.owner_id:
                    continue
                # Skip already-hit targets (unless piercing)
                if hurtbox.entity_id in hitbox.hits and not hitbox.definition.piercing:
                    continue
                # Skip invulnerable (dodge i-frames)
                if hurtbox.invulnerable:
                    continue
                # Check collision
                if self._check_collision(hitbox, hurtbox):
                    hitbox.hits.add(hurtbox.entity_id)
                    hits.append(HitEvent(
                        attacker_id=hitbox.owner_id,
                        target_id=hurtbox.entity_id,
                        hitbox=hitbox,
                        damage_context=hitbox.damage_context,
                        hit_position=(hurtbox.world_x, hurtbox.world_y)
                    ))

        for hb in expired:
            self.active_hitboxes.remove(hb)

        return hits

    def _check_collision(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
        shape = hitbox.definition.shape
        if shape == "circle":
            return self._collides_circle_circle(hitbox, hurtbox)
        elif shape == "arc":
            return self._collides_arc_circle(hitbox, hurtbox)
        elif shape == "rect":
            return self._collides_rect_circle(hitbox, hurtbox)
        elif shape == "line":
            return self._collides_line_circle(hitbox, hurtbox)
        return False
```

### 4.5 Hurtbox Sizing

Player hurtbox radius: **0.35 tiles** (about 11 pixels at 32px/tile). This is deliberately smaller than the player's visual circle (10.67px radius ≈ 0.33 tiles). A slightly generous hurtbox means dodges feel fair — if the player *looks* like they dodged, they did.

Enemy hurtbox radii scale with tier:
- T1: 0.5 tiles (16px) — small creatures like wolves, slimes
- T2: 0.65 tiles (21px) — medium like golems, dire wolves
- T3: 0.8 tiles (26px) — large like drakes, titans
- T4: 1.0 tiles (32px) — boss-sized, hard to miss

These radii are loaded from the enemy attacks JSON, not hardcoded, so they can be tuned per-enemy.

### 4.6 When Hitboxes Spawn

Hitboxes are NOT spawned by the hitbox system itself. They're spawned by the **game engine** in response to `CombatEvent("phase_change", data={"phase": "active"})` from the attack state machine:

```python
# In game_engine.py, processing ASM events:
for event in player_events:
    if event.event_type == "phase_change" and event.data["phase"] == "active":
        attack_def = self.player_attack_sm.current_attack
        facing = self.character.facing_angle
        pos = (self.character.position.x, self.character.position.y)
        hitbox_pos = attack_def.hitbox_params_as_definition().compute_world_position(pos[0], pos[1], facing)

        if attack_def.projectile_id:
            # Ranged: spawn projectile instead
            self.projectile_system.spawn(attack_def.projectile_id, pos, facing,
                                         'player', self.player_attack_sm.damage_context)
        else:
            # Melee: spawn hitbox
            self.hitbox_system.spawn_hitbox(
                attack_def.hitbox_params_as_definition(),
                hitbox_pos, facing, 'player',
                attack_def.active_ms,
                self.player_attack_sm.damage_context
            )
```

This separation means the state machine only tracks timing, the hitbox system only tracks geometry, and the game engine connects them.

---

## 5. Projectile System

### 5.1 What Projectiles Are

A projectile is a hitbox that moves through space. It has velocity, a maximum range, and an optional trail effect. When it collides with a hurtbox (or reaches max range), it despawns. Some projectiles explode into an AoE hitbox on impact.

Projectiles are used for: bow attacks, staff spells, enemy ranged attacks (acid spit, fireball breath), thrown items, and turret attacks.

### 5.2 ProjectileDefinition — From JSON

```python
@dataclass
class ProjectileDefinition:
    projectile_id: str
    speed: float              # Tiles per second
    max_range: float          # Tiles before despawn (infinity = no limit)
    hitbox: HitboxDefinition  # Usually a small circle (radius 0.2-0.5)
    sprite_id: str            # Visual asset key (or "procedural_fireball", etc.)
    trail_type: Optional[str] # "fire_trail", "ice_trail", "arrow_trail", None
    homing: float = 0.0      # 0 = straight line, 0.5 = gentle curve, 1.0 = missile lock
    gravity: float = 0.0     # Tiles/sec² downward (for arcing projectiles)
    piercing: bool = False    # Pass through first target?
    aoe_on_hit: Optional[HitboxDefinition] = None  # Explode on impact?
    aoe_duration_ms: float = 100.0  # How long the AoE hitbox lives
```

### 5.3 Projectile — Live Instance

```python
class Projectile:
    def __init__(self, definition: ProjectileDefinition,
                 start_pos: Tuple[float, float],
                 direction_angle: float,
                 owner_id: str,
                 damage_context: dict):
        self.definition = definition
        self.x, self.y = start_pos
        self.owner_id = owner_id
        self.damage_context = damage_context
        self.alive = True
        self.distance_traveled = 0.0
        self.hits: Set[str] = set()

        # Velocity from direction and speed
        angle_rad = math.radians(direction_angle)
        self.vx = math.cos(angle_rad) * definition.speed
        self.vy = math.sin(angle_rad) * definition.speed
        self.facing_angle = direction_angle

        # For homing: store target position at launch
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None

    def update(self, dt_seconds: float) -> None:
        if not self.alive:
            return

        # Apply gravity (arcing projectiles)
        if self.definition.gravity > 0:
            self.vy += self.definition.gravity * dt_seconds

        # Apply homing (gentle steering toward target)
        if self.definition.homing > 0 and self.target_x is not None:
            desired_dx = self.target_x - self.x
            desired_dy = self.target_y - self.y
            desired_angle = math.atan2(desired_dy, desired_dx)
            current_angle = math.atan2(self.vy, self.vx)

            # Steer toward target
            angle_diff = (desired_angle - current_angle + math.pi) % (2*math.pi) - math.pi
            steer = angle_diff * self.definition.homing * dt_seconds * 5.0
            new_angle = current_angle + steer

            speed = math.sqrt(self.vx**2 + self.vy**2)
            self.vx = math.cos(new_angle) * speed
            self.vy = math.sin(new_angle) * speed

        # Move
        move_x = self.vx * dt_seconds
        move_y = self.vy * dt_seconds
        self.x += move_x
        self.y += move_y
        self.distance_traveled += math.sqrt(move_x**2 + move_y**2)

        # Update facing angle for rendering
        if self.vx != 0 or self.vy != 0:
            self.facing_angle = math.degrees(math.atan2(self.vy, self.vx))

        # Range check
        if self.distance_traveled >= self.definition.max_range:
            self.alive = False
```

### 5.4 ProjectileSystem — Manager

```python
class ProjectileSystem:
    def __init__(self, hitbox_system: HitboxSystem):
        self.projectiles: List[Projectile] = []
        self.hitbox_system = hitbox_system

    def spawn(self, proj_def: ProjectileDefinition,
              start: Tuple[float, float], direction_angle: float,
              owner_id: str, damage_context: dict,
              target_pos: Optional[Tuple[float, float]] = None) -> Projectile:
        proj = Projectile(proj_def, start, direction_angle, owner_id, damage_context)
        if target_pos and proj_def.homing > 0:
            proj.target_x, proj.target_y = target_pos
        self.projectiles.append(proj)
        return proj

    def update(self, dt_ms: float) -> List[HitEvent]:
        """Move all projectiles, check collisions, handle despawn."""
        dt_sec = dt_ms / 1000.0
        hits = []
        dead = []

        for proj in self.projectiles:
            proj.update(dt_sec)

            if not proj.alive:
                dead.append(proj)
                continue

            # Check collision against all hurtboxes
            for hurtbox in self.hitbox_system.hurtboxes.values():
                if hurtbox.entity_id == proj.owner_id:
                    continue
                if hurtbox.entity_id in proj.hits:
                    continue
                if hurtbox.invulnerable:
                    continue

                # Simple circle-circle collision
                dx = hurtbox.world_x - proj.x
                dy = hurtbox.world_y - proj.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist < proj.definition.hitbox.radius + hurtbox.radius:
                    proj.hits.add(hurtbox.entity_id)
                    hits.append(HitEvent(
                        attacker_id=proj.owner_id,
                        target_id=hurtbox.entity_id,
                        hitbox=None,  # projectile hit, not hitbox hit
                        damage_context=proj.damage_context,
                        hit_position=(proj.x, proj.y)
                    ))

                    if not proj.definition.piercing:
                        proj.alive = False

                    # AoE explosion on impact
                    if proj.definition.aoe_on_hit:
                        self.hitbox_system.spawn_hitbox(
                            proj.definition.aoe_on_hit,
                            (proj.x, proj.y),
                            0.0,  # AoE explosions have no facing
                            proj.owner_id,
                            proj.definition.aoe_duration_ms,
                            proj.damage_context
                        )

                    if not proj.alive:
                        dead.append(proj)
                        break

        for p in dead:
            if p in self.projectiles:
                self.projectiles.remove(p)

        return hits

    def get_active_projectiles(self) -> List[Projectile]:
        """For rendering."""
        return self.projectiles
```

### 5.5 Dodgeability — The Design Intent

Projectiles have **real travel time**. This is the entire point. A fireball at 8 tiles/sec aimed at a player 5 tiles away arrives in 625ms. At player speed 9 tiles/sec, the player can sidestep ~5.6 tiles in that time — easily dodged if they react during the enemy's 500ms windup.

The skill expression chain:
1. Enemy enters WINDUP (500ms) — player sees telegraph
2. Player identifies attack type from visual cue (fire glow = ranged, red arc = melee)
3. If ranged: player moves perpendicular to dodge. If melee: player dodges through with i-frames
4. Enemy's ACTIVE phase fires, but player is no longer there

This creates engagement. The current instant-damage system has no skill expression — you either out-stat the enemy or you don't. With travel time and telegraphs, a skilled player can fight above their level.

### 5.6 Projectile Visuals

Projectiles need to render with rotation (facing the direction of travel) and optional trails.

**Rendering** (handled by renderer, not projectile system):
```python
# In renderer, during entity drawing:
for proj in projectile_system.get_active_projectiles():
    sx, sy = camera.world_to_screen_float(proj.x, proj.y)
    # Get sprite, rotate to facing angle
    sprite = self._get_projectile_sprite(proj.definition.sprite_id, proj.facing_angle)
    self.screen.blit(sprite, sprite.get_rect(center=(int(sx), int(sy))))

    # Trail particles
    if proj.definition.trail_type:
        combat_particles.emit_trail(proj.x, proj.y, proj.definition.trail_type)
```

For day-one implementation without projectile art assets, we draw simple procedural shapes:
- **Arrow**: Small rotated triangle (3 points, 6px long)
- **Fireball**: Orange filled circle (4px radius) with glow
- **Acid spit**: Green filled circle (5px radius)
- **Magic bolt**: Blue/purple filled circle (3px radius) with particle trail

These are generated once and cached, just like the procedural animations.

---

## 6. Player Actions: Dodge & Input Buffer

### 6.1 Dodge Roll — The Defensive Core

The dodge roll is the player's primary defensive tool. It provides a brief invulnerability window (i-frames) during which hitbox collisions are ignored. Without it, action combat doesn't work — the player would have no way to avoid melee attacks with telegraphs shorter than their reaction time + movement time.

**Parameters** (loaded from config, tunable without code changes):

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| Duration | 250ms (15 frames) | Short enough to feel snappy, long enough to clear a hitbox |
| Speed multiplier | 3.0x | 0.15 × 3.0 = 0.45 tiles/frame = 27 tiles/sec. Covers ~6.75 tiles in 250ms |
| I-frame window | 200ms (12 frames) | Starts immediately, ends 50ms before roll ends |
| Cooldown | 800ms | Prevents spam-dodging. One dodge per ~1 second |
| Stamina cost | None (for now) | Keep it simple. Stamina system can be added later if needed |

**Why 200ms i-frames, not 250ms?** The last 50ms of the roll has no invulnerability. This prevents players from dodging *into* an attack and being invulnerable when they land on top of the hitbox. The vulnerability gap forces directional dodging — you need to actually move *out of* the danger zone, not just press dodge whenever.

### 6.2 PlayerActionSystem

```python
class PlayerActionSystem:
    def __init__(self, character):
        self.character = character

        # Dodge state
        self.is_dodging: bool = False
        self.dodge_timer: float = 0.0          # Remaining dodge duration
        self.dodge_cooldown: float = 0.0       # Time until next dodge allowed
        self.iframe_timer: float = 0.0         # Remaining i-frame duration
        self.dodge_direction: Tuple[float, float] = (0, 0)  # Normalized direction

        # Configurable parameters
        self.dodge_duration_ms: float = 250.0
        self.dodge_speed_mult: float = 3.0
        self.dodge_cooldown_ms: float = 800.0
        self.iframe_duration_ms: float = 200.0

        # Input buffer
        self.input_buffer = InputBuffer()

    @property
    def is_invulnerable(self) -> bool:
        return self.iframe_timer > 0

    def try_dodge(self, direction: Tuple[float, float]) -> bool:
        """Initiate dodge roll. Returns False if on cooldown or already dodging."""
        if self.is_dodging or self.dodge_cooldown > 0:
            return False

        # Normalize direction
        mag = math.sqrt(direction[0]**2 + direction[1]**2)
        if mag < 0.01:
            # No direction input — dodge in facing direction
            angle = math.radians(FACING_TO_ANGLE[self.character.facing])
            self.dodge_direction = (math.cos(angle), math.sin(angle))
        else:
            self.dodge_direction = (direction[0]/mag, direction[1]/mag)

        self.is_dodging = True
        self.dodge_timer = self.dodge_duration_ms
        self.iframe_timer = self.iframe_duration_ms
        self.dodge_cooldown = self.dodge_cooldown_ms

        # Set hurtbox invulnerable
        # (Done via hitbox_system — game_engine sets hurtbox.invulnerable = True)

        return True

    def update(self, dt_ms: float) -> None:
        # Update dodge
        if self.is_dodging:
            self.dodge_timer -= dt_ms
            if self.dodge_timer <= 0:
                self.is_dodging = False
                self.dodge_timer = 0

        # Update i-frames (can outlast or underlast dodge)
        if self.iframe_timer > 0:
            self.iframe_timer -= dt_ms
            if self.iframe_timer <= 0:
                self.iframe_timer = 0

        # Update cooldown
        if self.dodge_cooldown > 0:
            self.dodge_cooldown -= dt_ms
            if self.dodge_cooldown <= 0:
                self.dodge_cooldown = 0

        # Update input buffer
        self.input_buffer.update(dt_ms)

    def get_dodge_velocity(self) -> Tuple[float, float]:
        """Returns (dx, dy) to add to player movement this frame during dodge."""
        if not self.is_dodging:
            return (0, 0)
        speed = self.character.movement_speed * self.dodge_speed_mult
        return (self.dodge_direction[0] * speed, self.dodge_direction[1] * speed)
```

### 6.3 Integration with Movement

The dodge roll overrides normal movement during its duration. In `game_engine.update()`:

```python
# Current movement code (lines 6688-6703):
dx = dy = 0
if pygame.K_w in self.keys_pressed: dy -= effective_speed
# ... etc

# NEW: Override movement during dodge
if self.player_actions.is_dodging:
    dodge_vel = self.player_actions.get_dodge_velocity()
    dx, dy = dodge_vel
else:
    # Normal WASD movement (existing code)
    dx = dy = 0
    if pygame.K_w in self.keys_pressed: dy -= effective_speed
    # ...

# Apply movement speed reduction during attacks
if self.player_attack_sm.is_attacking:
    mult = self.player_attack_sm.movement_multiplier
    dx *= mult
    dy *= mult
```

### 6.4 Dodge Input — Space Bar

Dodge is triggered by Space bar (not used for anything currently in combat):

```python
# In game_engine.handle_events(), KEYDOWN handler:
if event.key == pygame.K_SPACE:
    # Determine dodge direction from held movement keys
    dir_x = dir_y = 0
    if pygame.K_w in self.keys_pressed: dir_y -= 1
    if pygame.K_s in self.keys_pressed: dir_y += 1
    if pygame.K_a in self.keys_pressed: dir_x -= 1
    if pygame.K_d in self.keys_pressed: dir_x += 1
    self.player_actions.try_dodge((dir_x, dir_y))
```

If no movement keys are held, the player dodges in their current facing direction. This is important — panic-pressing Space without a direction should still do something useful.

### 6.5 InputBuffer — Responsive Chaining

The input buffer solves a classic game-feel problem: the player presses attack during an animation, but nothing happens because the game only checks input on the frame it was pressed. The buffer queues the input and replays it when the current action ends.

```python
class InputBuffer:
    BUFFER_WINDOW_MS = 200  # Accept inputs this far before current action ends

    def __init__(self):
        self.buffered_action: Optional[str] = None  # "attack", "dodge", "skill_X"
        self.buffered_data: Optional[dict] = None    # Context for the action
        self.buffer_timer: float = 0.0

    def buffer(self, action: str, data: dict = None) -> None:
        """Queue an action."""
        self.buffered_action = action
        self.buffered_data = data
        self.buffer_timer = self.BUFFER_WINDOW_MS

    def consume(self) -> Optional[Tuple[str, Optional[dict]]]:
        """Get and clear buffered action if still valid."""
        if self.buffered_action and self.buffer_timer > 0:
            action = self.buffered_action
            data = self.buffered_data
            self.buffered_action = None
            self.buffered_data = None
            return (action, data)
        return None

    def update(self, dt_ms: float) -> None:
        if self.buffer_timer > 0:
            self.buffer_timer -= dt_ms
            if self.buffer_timer <= 0:
                self.buffered_action = None
                self.buffered_data = None
```

Usage in game engine:
```python
# When player presses attack but state machine is busy:
if attack_pressed and self.player_attack_sm.is_attacking:
    self.player_actions.input_buffer.buffer("attack", {"hand": "mainHand"})

# When state machine returns to IDLE or COOLDOWN:
for event in player_events:
    if event.data.get("phase") in ("cooldown", "idle"):
        buffered = self.player_actions.input_buffer.consume()
        if buffered:
            action, data = buffered
            if action == "attack":
                # Start next attack (combo chain)
                self.player_attack_sm.start_attack(next_combo_attack, ...)
```

### 6.6 Attack Combos

Combos are simple: consecutive attacks within a window chain through different `AttackDefinition`s.

```
Hit 1: sword_1h_swing_1  → normal swing left-to-right, 350ms
Hit 2: sword_1h_swing_2  → return swing right-to-left, 300ms (slightly faster)
Hit 3: sword_1h_heavy    → overhead slam, 500ms, 1.5x damage, bigger hitbox
→ Combo resets, back to swing_1
```

The `combo_next` field on `AttackDefinition` points to the next attack in the chain. The `combo_window_ms` defines how long after RECOVERY the player has to input the next attack before the combo drops.

The `AttackStateMachine.combo_count` tracks position in the chain. When the combo drops (timer expires), it resets to 0.

This is deliberately simple — no complex input sequences or timing windows. Just "keep attacking within the window to advance the combo." The complexity comes from deciding *when* to attack vs when to dodge.

### 6.7 Dodge Visual Feedback

When the player dodges:
1. **Dust particles** emit from start position (`combat_particles.emit_dodge_dust()`)
2. **Ghost trail** — 2-3 semi-transparent copies of the player circle at previous positions (drawn during dodge frames, fading alpha)
3. **I-frame visual** — player circle tints blue/cyan during invulnerability
4. **Cooldown indicator** — subtle cooldown arc around player (optional, can be toggled)

These are all handled by the renderer checking `player_actions.is_dodging` and `player_actions.is_invulnerable`.

---

## 7. Enemy Tier Scaling & Attack Patterns

### 7.1 Two Attack Systems, Not One

Enemies currently have **two** attack mechanisms that must both work with the new state machine:

1. **Basic attacks** — `enemy.can_attack()` → `_enemy_attack_player()`. Timer-based, melee range (1.5 tiles), uses `damage_min`/`damage_max` from definition. These get wrapped by the AttackStateMachine.

2. **Special abilities** — `enemy.can_use_special_ability()` → `enemy.use_special_ability()`. Tag-based, with cooldowns, trigger conditions (health threshold, distance range, ally count), and the full effect executor pipeline. These are already more sophisticated and should route through the state machine for visual telegraphs, but their damage calculation stays unchanged.

The key insight: basic attacks become the enemy's "auto-attack" pattern with windups and hitboxes. Special abilities are interrupt-style attacks with their own telegraphs layered on top.

### 7.2 Enemy Attack Definitions — From JSON

Each enemy type gets a list of basic attack patterns in `Animation-Data.JSON/enemy-attacks.json`:

```json
{
  "wolf_grey": {
    "hurtbox_radius": 0.5,
    "attacks": [
      {
        "attack_id": "wolf_bite",
        "windup_ms": 400,
        "active_ms": 100,
        "recovery_ms": 200,
        "cooldown_ms": 1500,
        "hitbox": {
          "shape": "arc",
          "radius": 1.5,
          "arc_degrees": 60,
          "offset_forward": 0.6
        },
        "damage_multiplier": 1.0,
        "animation_id": "enemy_lunge",
        "telegraph_color": [255, 100, 100],
        "weight": 1.0
      }
    ]
  },
  "golem_stone": {
    "hurtbox_radius": 0.75,
    "attacks": [
      {
        "attack_id": "golem_slam",
        "windup_ms": 500,
        "active_ms": 150,
        "recovery_ms": 400,
        "cooldown_ms": 2000,
        "hitbox": {
          "shape": "circle",
          "radius": 2.0,
          "offset_forward": 0.0
        },
        "damage_multiplier": 1.5,
        "animation_id": "enemy_slam",
        "telegraph_color": [200, 150, 50],
        "screen_shake": true,
        "weight": 0.6
      },
      {
        "attack_id": "golem_swipe",
        "windup_ms": 300,
        "active_ms": 100,
        "recovery_ms": 200,
        "cooldown_ms": 1200,
        "hitbox": {
          "shape": "arc",
          "radius": 1.8,
          "arc_degrees": 120,
          "offset_forward": 0.4
        },
        "damage_multiplier": 0.8,
        "animation_id": "enemy_swipe",
        "telegraph_color": [200, 150, 50],
        "weight": 0.4
      }
    ]
  }
}
```

The `weight` field determines attack selection probability. The golem chooses slam 60% of the time and swipe 40%.

### 7.3 Visual Tier Scaling

Enemy render size scales with tier. Currently all enemies render at `TILE_SIZE // 2 * 2 = 32px` regardless of tier. The change:

```python
# In renderer.py, replacing the enemy size calculation:
TIER_SCALE = {1: 1.0, 2: 1.3, 3: 1.6, 4: 2.0}
base_size = Config.TILE_SIZE  # 32px
tier = enemy.definition.tier
scaled_size = int(base_size * TIER_SCALE.get(tier, 1.0))
# T1: 32px, T2: 42px, T3: 51px, T4: 64px

icon = image_cache.get_image(enemy.definition.icon_path, (scaled_size, scaled_size))
```

This has cascading effects on:
- **Health bar position**: Must move up proportionally (`ey - scaled_size//2 - 12`)
- **Tier text position**: Centered in the sprite, scales with sprite size
- **Hurtbox radius**: Already defined per-enemy in JSON, but should visually match

T4 enemies at 64px will feel like mini-bosses just from their screen presence. Combined with longer attack patterns and more hitbox coverage, they become genuinely intimidating.

### 7.4 Tier-Based Combat Philosophy

Each tier isn't just "more damage" — it's a different combat experience:

**T1 (wolves, slimes, beetles)**: One attack pattern, long telegraphs. The player learns the basics: read telegraph → dodge or position → punish during recovery. Mistakes are cheap — low damage, fast enemy recovery means quick retry.

**T2 (golems, dire wolves, crystal slimes)**: Two attack patterns, moderate telegraphs. The player must identify *which* attack to dodge for. A golem slam (circle AoE, 500ms windup) requires dodging away, while a golem swipe (120° arc, 300ms windup) requires dodging through. The choice matters.

**T3 (drakes, titans, void wraiths)**: Three+ patterns, short telegraphs, and **phase transitions**. At 50% HP, attack weights shift — the inferno drake starts favoring ranged fire breath over melee tail swipe, forcing the player to change strategy mid-fight.

**T4 (archons, primordials)**: Four+ patterns, mixed ranged/melee, **adaptive behavior**. T4 enemies track whether the player tends to dodge left or right and adjust their attack targeting. They use combos (slam → immediate swipe while player is recovering). They're designed to feel like boss fights.

### 7.5 Phase Transitions (T3+)

Enemies with `phases` in their attack definition switch attack weights at HP thresholds:

```json
{
  "inferno_drake": {
    "hurtbox_radius": 0.9,
    "phases": {
      "default": { "fire_breath": 0.3, "fireball_spit": 0.4, "tail_swipe": 0.3 },
      "below_50": { "fire_breath": 0.5, "fireball_spit": 0.3, "tail_swipe": 0.2 },
      "below_25": { "fire_breath": 0.2, "fireball_spit": 0.1, "tail_swipe": 0.1, "enrage_roar": 0.6 }
    },
    "attacks": [...]
  }
}
```

The combat_manager checks `enemy.current_health / enemy.max_health` and selects the appropriate phase weights. Phase transitions are visually marked — the enemy flashes, the screen shakes slightly, and the enemy pauses for ~200ms (a brief "phase change" animation).

### 7.6 Enemy Attack Selection in combat_manager.update()

Currently (line 498-501):
```python
elif enemy.can_attack():
    dist = enemy.distance_to(player_pos)
    if dist <= 1.5:
        self._enemy_attack_player(enemy, shield_blocking=shield_blocking)
```

With the new system:
```python
elif not enemy.attack_state_machine.is_attacking:
    dist = enemy.distance_to(player_pos)
    # Select attack based on weights and distance
    attack_def = self._select_enemy_attack(enemy, dist)
    if attack_def and dist <= attack_def.hitbox_params.get('radius', 1.5) + attack_def.hitbox_params.get('offset_forward', 0):
        damage_context = {
            'enemy': enemy,
            'base_damage': random.uniform(enemy.definition.damage_min, enemy.definition.damage_max),
        }
        enemy.attack_state_machine.start_attack(attack_def, damage_context)
```

The `_select_enemy_attack()` method:
```python
def _select_enemy_attack(self, enemy: Enemy, dist_to_player: float) -> Optional[AttackDefinition]:
    """Weighted random selection from available attacks, filtered by range."""
    available = []
    phase = self._get_enemy_phase(enemy)
    weights = enemy.attack_phases.get(phase, {})

    for attack_def in enemy.attack_definitions:
        # Check if this attack can reach the player
        max_reach = attack_def.hitbox_params.get('radius', 1.5) + attack_def.hitbox_params.get('offset_forward', 0)
        if attack_def.projectile_id:
            max_reach = 999  # Ranged attacks always "in range" for selection
        if dist_to_player <= max_reach * 1.2:  # 20% buffer
            weight = weights.get(attack_def.attack_id, 1.0)
            available.append((attack_def, weight))

    if not available:
        return None

    # Weighted random selection
    total = sum(w for _, w in available)
    roll = random.uniform(0, total)
    cumulative = 0
    for attack_def, weight in available:
        cumulative += weight
        if roll <= cumulative:
            return attack_def
    return available[-1][0]
```

### 7.7 Enemy Facing Angle Computation

The attack state machine needs `facing_angle` to position hitboxes. Currently enemies don't track this. The change in `enemy.update_ai()`:

```python
# At the start of update_ai, after checking is_alive:
# Compute facing angle toward player (or movement direction)
if self.ai_state in (AIState.CHASE, AIState.ATTACK):
    dx = player_position[0] - self.position[0]
    dy = player_position[1] - self.position[1]
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        self.facing_angle = math.degrees(math.atan2(dy, dx))
elif self.target_position:
    dx = self.target_position[0] - self.position[0]
    dy = self.target_position[1] - self.position[1]
    if abs(dx) > 0.01 or abs(dy) > 0.01:
        self.facing_angle = math.degrees(math.atan2(dy, dx))
```

---

## 8. Screen Effects & Visual Polish

### 8.1 Why This Matters

Screen effects are the difference between "I hit the enemy" and "I *felt* that hit." Without them, damage is just a number appearing. With them, the game world reacts to violence — the camera shakes, time stutters, sprites flash. These effects are cheap to implement and disproportionately improve perceived quality.

### 8.2 combat/screen_effects.py

```python
class ScreenEffects:
    """Global visual effects that modify the entire render output."""

    def __init__(self):
        # Screen shake
        self.shake_intensity: float = 0.0     # Current shake magnitude (pixels)
        self.shake_duration: float = 0.0      # Remaining shake time (ms)
        self.shake_decay: float = 0.0         # Intensity lost per ms
        self.shake_offset: Tuple[int, int] = (0, 0)

        # Hit pause (freeze frame)
        self.hit_pause_remaining: float = 0.0  # ms remaining of freeze

        # Time dilation
        self.time_scale: float = 1.0           # 1.0 = normal, 0.3 = slow-mo
        self.time_scale_duration: float = 0.0  # ms remaining

        # Entity flash tracking
        self.flash_entities: Dict[str, Tuple[Tuple[int,int,int], float]] = {}
        # entity_id → (color, remaining_ms)

    def screen_shake(self, intensity: float, duration_ms: float) -> None:
        """Trigger screen shake. Stacks with existing shake (takes max)."""
        self.shake_intensity = max(self.shake_intensity, intensity)
        self.shake_duration = max(self.shake_duration, duration_ms)
        self.shake_decay = self.shake_intensity / max(self.shake_duration, 1)

    def hit_pause(self, duration_ms: float) -> None:
        """Freeze the game world for duration. UI still updates."""
        self.hit_pause_remaining = max(self.hit_pause_remaining, duration_ms)

    def slow_motion(self, time_scale: float, duration_ms: float) -> None:
        """Temporary time dilation. Lower = slower."""
        self.time_scale = time_scale
        self.time_scale_duration = duration_ms

    def flash_entity(self, entity_id: str, color: Tuple[int,int,int],
                     duration_ms: float = 80.0) -> None:
        """Mark entity for white/red flash on next render."""
        self.flash_entities[entity_id] = (color, duration_ms)

    def update(self, dt_ms: float) -> None:
        # Hit pause — if active, skip all other updates
        if self.hit_pause_remaining > 0:
            self.hit_pause_remaining -= dt_ms
            return  # Don't decay other effects during pause

        # Screen shake
        if self.shake_duration > 0:
            self.shake_duration -= dt_ms
            self.shake_intensity -= self.shake_decay * dt_ms
            if self.shake_duration <= 0 or self.shake_intensity <= 0:
                self.shake_intensity = 0
                self.shake_duration = 0
                self.shake_offset = (0, 0)
            else:
                import random
                self.shake_offset = (
                    random.randint(-int(self.shake_intensity), int(self.shake_intensity)),
                    random.randint(-int(self.shake_intensity), int(self.shake_intensity))
                )

        # Time dilation
        if self.time_scale_duration > 0:
            self.time_scale_duration -= dt_ms
            if self.time_scale_duration <= 0:
                self.time_scale = 1.0

        # Entity flashes
        expired = []
        for eid, (color, remaining) in self.flash_entities.items():
            remaining -= dt_ms
            if remaining <= 0:
                expired.append(eid)
            else:
                self.flash_entities[eid] = (color, remaining)
        for eid in expired:
            del self.flash_entities[eid]

    @property
    def is_paused(self) -> bool:
        return self.hit_pause_remaining > 0

    def get_effective_dt(self, raw_dt_ms: float) -> float:
        """Apply time dilation to delta time."""
        if self.is_paused:
            return 0.0
        return raw_dt_ms * self.time_scale
```

### 8.3 When Effects Trigger

**Screen Shake**:
- Player lands a critical hit: `intensity=4, duration=100ms`
- Hammer slam hits: `intensity=6, duration=150ms`
- Boss AoE attack: `intensity=8, duration=200ms`
- Enemy killed: `intensity=2, duration=60ms`

**Hit Pause**:
- Critical hit: `40ms` — brief stutter makes crits feel devastating
- Killing blow: `60ms` — the world holds its breath
- Boss phase transition: `100ms` — dramatic punctuation

**Slow Motion**:
- Player reaches <10% HP: `time_scale=0.5, duration=500ms` — near-death tension
- Boss killed: `time_scale=0.3, duration=800ms` — cinematic kill
- (Optional, may feel gimmicky — implement but default to off)

**Entity Flash**:
- Any entity takes damage: white flash `80ms`
- Entity takes critical damage: red flash `120ms`
- Player takes damage: red flash `100ms`

### 8.4 Integration with Game Loop

The time dilation affects the `dt` passed to all game systems. In `game_engine.update()`:

```python
# After computing raw dt:
raw_dt_ms = (curr - self.last_tick)
dt_ms = self.screen_effects.get_effective_dt(raw_dt_ms)
dt = dt_ms / 1000.0

# If hit-paused, skip game updates but still render
if self.screen_effects.is_paused:
    self.screen_effects.update(raw_dt_ms)  # Decay the pause timer
    self.camera.follow(self.character.position)
    return  # Skip all game logic this frame

# All systems use dt_ms (dilated) instead of raw_dt_ms
self.player_actions.update(dt_ms)
self.player_attack_sm.update(dt_ms)
# ... etc
```

The renderer always runs — hit pause freezes logic but still draws (so the player sees the frozen impact frame). Screen shake is applied as an offset to all world-space drawing.

### 8.5 Attack Telegraphs — Enemy Windup Visuals

During enemy WINDUP phase, the attack zone is drawn as a semi-transparent overlay on the ground. This is the player's primary readability tool.

**Implementation in renderer**:
```python
# For each enemy in WINDUP phase:
if enemy.attack_state_machine.phase == AttackPhase.WINDUP:
    attack_def = enemy.attack_state_machine.current_attack
    progress = 1.0 - (enemy.attack_state_machine.phase_timer /
                       attack_def.windup_ms)  # 0→1 over windup

    hitbox_def = attack_def.hitbox_definition
    color = attack_def.telegraph_color  # From JSON
    alpha = int(40 + progress * 80)     # 40→120 alpha, increasingly visible

    if hitbox_def.shape == "circle":
        # Draw filling circle
        radius_px = int(hitbox_def.radius * Config.TILE_SIZE)
        telegraph_surf = pygame.Surface((radius_px*2, radius_px*2), pygame.SRCALPHA)
        pygame.draw.circle(telegraph_surf, (*color, alpha),
                          (radius_px, radius_px), int(radius_px * progress))
        # Outline at full radius
        pygame.draw.circle(telegraph_surf, (*color, alpha + 40),
                          (radius_px, radius_px), radius_px, 2)
        pos = hitbox_def.compute_world_position(enemy.position[0], enemy.position[1],
                                                 enemy.facing_angle)
        sx, sy = camera.world_to_screen(Position(pos[0], pos[1], 0))
        self.screen.blit(telegraph_surf, (sx - radius_px, sy - radius_px))

    elif hitbox_def.shape == "arc":
        # Draw filling arc/pie slice
        # Similar approach: pygame.draw.arc or polygon for pie
        ...
```

The telegraph starts faint and grows more visible/filled as the windup progresses. By the time it's fully opaque, the ACTIVE phase is about to begin — the player has ~1 frame to dodge.

### 8.6 Damage Numbers — Enhanced

The existing `DamageNumber` dataclass is simple: `damage, position, is_crit, lifetime, velocity_y`. We enhance it without changing the class signature:

```python
@dataclass
class DamageNumber:
    damage: int
    position: Position
    is_crit: bool
    lifetime: float = 1.2
    velocity_y: float = -2.0
    velocity_x: float = 0.0       # NEW: slight horizontal spread
    damage_type: str = "physical"  # NEW: for color coding
    scale: float = 1.0            # NEW: crits start at 1.5x

    def __post_init__(self):
        import random
        self.velocity_x = random.uniform(-0.3, 0.3)
        if self.is_crit:
            self.scale = 1.5
        # Color from damage type
        self.color = DAMAGE_COLORS.get(self.damage_type, (255, 255, 255))

    def update(self, dt: float) -> bool:
        self.lifetime -= dt
        self.position.y += self.velocity_y * dt
        self.position.x += self.velocity_x * dt
        self.velocity_y += 3.0 * dt  # Gravity — creates arc
        self.scale = max(0.8, self.scale - 0.3 * dt)  # Subtle shrink
        return self.lifetime > 0

DAMAGE_COLORS = {
    "physical": (255, 255, 255),
    "fire": (255, 150, 50),
    "ice": (100, 200, 255),
    "lightning": (255, 255, 100),
    "poison": (100, 255, 100),
    "arcane": (200, 100, 255),
    "shadow": (150, 100, 200),
    "holy": (255, 255, 200),
    "heal": (100, 255, 150),
}
```

The gravity on `velocity_y` creates an arc trajectory — numbers float up, then gently fall. Combined with the horizontal spread, multiple damage numbers from AoE attacks fan out attractively instead of stacking.

---

## 9. Renderer Integration

### 9.1 Minimal Changes to renderer.py

The renderer is 2,782 lines. We add to it; we don't restructure it. All new drawing happens in the existing `render_world()` method, inserted at the correct draw-order position.

The renderer receives references to the new systems via method parameters — it doesn't import them directly. This keeps the renderer loosely coupled.

### 9.2 Modified render_world() Signature

```python
def render_world(self, world, camera, character, damage_numbers, combat_manager=None,
                 animation_manager=None, hitbox_system=None, projectile_system=None,
                 screen_effects=None, player_actions=None, combat_particles=None):
```

New parameters are all optional with `None` defaults so existing call sites don't break during incremental rollout.

### 9.3 Draw Order (Updated)

```
1. Apply screen shake offset to all drawing ← NEW
2. Tiles (ground) — existing
3. Resources (trees, ore) — existing
4. Attack telegraphs (enemy WINDUP zones) ← NEW (behind entities)
5. Placed entities (turrets, chests) — existing
6. Enemies (with animation frame + tier scaling + flash) ← MODIFIED
7. Player (with animation frame + dodge ghost + flash) ← MODIFIED
8. Active hitboxes (melee slash arcs) ← NEW
9. Projectiles (with rotation + trail) ← NEW
10. Combat particles ← NEW
11. Damage numbers — existing (enhanced)
12. Attack effects (lines, blocked) — existing
13. Debug hitbox overlays (F1 mode) ← NEW
14. UI — existing
15. Remove screen shake offset ← NEW
```

### 9.4 Screen Shake Application

At the start of `render_world()`:
```python
# Apply screen shake offset
shake_offset = (0, 0)
if screen_effects:
    shake_offset = screen_effects.shake_offset

# Shift viewport for all world-space drawing
if shake_offset != (0, 0):
    self.screen.set_clip(pygame.Rect(0, 0, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT))
    # All subsequent world_to_screen calls get the offset
    camera_shake = Camera(camera.viewport_width, camera.viewport_height)
    camera_shake.position = camera.position.copy()
    camera_shake.position.x -= shake_offset[0] / Config.TILE_SIZE
    camera_shake.position.y -= shake_offset[1] / Config.TILE_SIZE
    draw_camera = camera_shake
else:
    draw_camera = camera
```

We create a temporary camera offset rather than shifting every blit call. All `world_to_screen` calls during this frame use `draw_camera`, which includes the shake displacement. The clip rect prevents shaken content from drawing outside the viewport.

### 9.5 Enemy Rendering Changes

Replace the current enemy drawing block (lines 1323-1370):

```python
# Render enemies
if combat_manager:
    for enemy in combat_manager.get_all_active_enemies():
        ex, ey = draw_camera.world_to_screen(Position(enemy.position[0], enemy.position[1], 0))

        if enemy.is_alive:
            # Tier-based size scaling
            TIER_SCALE = {1: 1.0, 2: 1.3, 3: 1.6, 4: 2.0}
            scale = TIER_SCALE.get(enemy.definition.tier, 1.0)
            base_size = Config.TILE_SIZE
            scaled_size = int(base_size * scale)

            # Check for animation frame override
            anim_frame = None
            if animation_manager:
                enemy_id = f"enemy_{id(enemy)}"
                anim_frame = animation_manager.get_current_frame(enemy_id)

            # Get sprite
            icon = image_cache.get_image(enemy.definition.icon_path,
                                          (scaled_size, scaled_size)) if enemy.definition.icon_path else None

            if icon:
                # Apply animation offset
                draw_x, draw_y = ex, ey
                if anim_frame:
                    draw_x += anim_frame.offset_x
                    draw_y += anim_frame.offset_y
                    # Apply animation scale
                    if anim_frame.scale != 1.0:
                        anim_size = int(scaled_size * anim_frame.scale)
                        icon = image_cache.get_image(enemy.definition.icon_path,
                                                      (anim_size, anim_size))

                # Apply hit flash
                if screen_effects and f"enemy_{id(enemy)}" in screen_effects.flash_entities:
                    flash_color, _ = screen_effects.flash_entities[f"enemy_{id(enemy)}"]
                    flash_surf = icon.copy()
                    flash_surf.fill(flash_color, special_flags=pygame.BLEND_RGB_ADD)
                    icon = flash_surf

                icon_rect = icon.get_rect(center=(draw_x, draw_y))
                self.screen.blit(icon, icon_rect)
            else:
                # Fallback circle (unchanged but scaled)
                tier_colors = {1: (200, 100, 100), 2: (255, 150, 0), 3: (200, 100, 255), 4: (255, 50, 50)}
                enemy_color = tier_colors.get(enemy.definition.tier, (200, 100, 100))
                pygame.draw.circle(self.screen, enemy_color, (ex, ey), scaled_size // 2)
                pygame.draw.circle(self.screen, (0, 0, 0), (ex, ey), scaled_size // 2, 2)

            # Health bar (positioned relative to scaled size)
            health_percent = enemy.current_health / enemy.max_health
            bar_w = max(Config.TILE_SIZE, scaled_size)
            bar_h = 4
            bar_y = ey - scaled_size // 2 - 12
            pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (ex - bar_w//2, bar_y, bar_w, bar_h))
            hp_w = int(bar_w * health_percent)
            pygame.draw.rect(self.screen, (255, 0, 0), (ex - bar_w//2, bar_y, hp_w, bar_h))
```

### 9.6 Player Rendering Changes

Currently a simple colored circle. We add dodge visuals and attack animation:

```python
# Render player
center_x, center_y = draw_camera.world_to_screen(character.position)
player_radius = Config.TILE_SIZE // 3

# Dodge ghost trail
if player_actions and player_actions.is_dodging:
    # Draw 2-3 ghost copies at previous positions
    for i, alpha_mult in enumerate([0.2, 0.4]):
        ghost_x = center_x - int(player_actions.dodge_direction[0] * (i+1) * 8)
        ghost_y = center_y - int(player_actions.dodge_direction[1] * (i+1) * 8)
        ghost_surf = pygame.Surface((player_radius*2+4, player_radius*2+4), pygame.SRCALPHA)
        pygame.draw.circle(ghost_surf, (*Config.COLOR_PLAYER, int(255*alpha_mult)),
                          (player_radius+2, player_radius+2), player_radius)
        self.screen.blit(ghost_surf, (ghost_x - player_radius-2, ghost_y - player_radius-2))

# Player circle with i-frame tint
player_color = Config.COLOR_PLAYER
if player_actions and player_actions.is_invulnerable:
    player_color = (100, 200, 255)  # Cyan tint during i-frames

# Flash on damage
if screen_effects and 'player' in screen_effects.flash_entities:
    flash_color, _ = screen_effects.flash_entities['player']
    player_color = flash_color

pygame.draw.circle(self.screen, player_color, (center_x, center_y), player_radius)
```

### 9.7 Slash Arc Rendering

After drawing entities, render active melee attack visuals:

```python
# Render slash arcs (player melee attacks)
if animation_manager:
    player_frame = animation_manager.get_current_frame('player_slash')
    if player_frame and player_frame.surface:
        # The slash surface is a pre-rendered arc, already rotated
        sx, sy = draw_camera.world_to_screen(character.position)
        slash_rect = player_frame.surface.get_rect(center=(sx, sy))
        self.screen.blit(player_frame.surface, slash_rect)
```

### 9.8 Projectile Rendering

```python
# Render projectiles
if projectile_system:
    for proj in projectile_system.get_active_projectiles():
        px, py = draw_camera.world_to_screen(Position(proj.x, proj.y, 0))

        # Simple procedural rendering (day-one, no art assets)
        size = 4
        color = PROJECTILE_COLORS.get(proj.definition.sprite_id, (255, 255, 255))

        # Rotated triangle for arrows, circle for magic
        if "arrow" in proj.definition.sprite_id:
            angle_rad = math.radians(proj.facing_angle)
            tip = (px + math.cos(angle_rad)*size*2, py + math.sin(angle_rad)*size*2)
            left = (px + math.cos(angle_rad + 2.5)*size, py + math.sin(angle_rad + 2.5)*size)
            right = (px + math.cos(angle_rad - 2.5)*size, py + math.sin(angle_rad - 2.5)*size)
            pygame.draw.polygon(self.screen, color, [tip, left, right])
        else:
            pygame.draw.circle(self.screen, color, (px, py), size)
            # Glow
            glow_surf = pygame.Surface((size*4, size*4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color, 60), (size*2, size*2), size*2)
            self.screen.blit(glow_surf, (px - size*2, py - size*2))
```

### 9.9 Debug Hitbox Rendering (F1 Mode)

When debug mode is active, draw all hitboxes and hurtboxes:

```python
if Config.DEBUG_MODE and hitbox_system:
    # Hurtboxes (green circles)
    for entity_id, hurtbox in hitbox_system.hurtboxes.items():
        hx, hy = draw_camera.world_to_screen(Position(hurtbox.world_x, hurtbox.world_y, 0))
        radius_px = int(hurtbox.radius * Config.TILE_SIZE)
        color = (0, 100, 255) if hurtbox.invulnerable else (0, 255, 0)
        pygame.draw.circle(self.screen, color, (hx, hy), radius_px, 2)

    # Active hitboxes (red shapes)
    for hitbox in hitbox_system.active_hitboxes:
        hx, hy = draw_camera.world_to_screen(Position(hitbox.world_x, hitbox.world_y, 0))

        if hitbox.definition.shape == "circle":
            radius_px = int(hitbox.definition.radius * Config.TILE_SIZE)
            pygame.draw.circle(self.screen, (255, 0, 0), (hx, hy), radius_px, 2)

        elif hitbox.definition.shape == "arc":
            radius_px = int(hitbox.definition.radius * Config.TILE_SIZE)
            start_angle = math.radians(hitbox.facing_angle - hitbox.definition.arc_degrees/2)
            end_angle = math.radians(hitbox.facing_angle + hitbox.definition.arc_degrees/2)
            rect = pygame.Rect(hx - radius_px, hy - radius_px, radius_px*2, radius_px*2)
            pygame.draw.arc(self.screen, (255, 0, 0), rect, -end_angle, -start_angle, 2)
            # Draw radial lines for arc edges
            for edge_angle in [start_angle, end_angle]:
                ex = hx + math.cos(edge_angle) * radius_px
                ey = hy - math.sin(edge_angle) * radius_px
                pygame.draw.line(self.screen, (255, 0, 0), (hx, hy), (int(ex), int(ey)), 1)

        elif hitbox.definition.shape == "rect":
            # Draw rotated rectangle
            w_px = int(hitbox.definition.width * Config.TILE_SIZE)
            h_px = int(hitbox.definition.height * Config.TILE_SIZE)
            angle_rad = math.radians(hitbox.facing_angle)
            corners = []
            for cx, cy in [(-w_px/2, -h_px/2), (w_px/2, -h_px/2),
                           (w_px/2, h_px/2), (-w_px/2, h_px/2)]:
                rx = cx * math.cos(angle_rad) - cy * math.sin(angle_rad) + hx
                ry = cx * math.sin(angle_rad) + cy * math.cos(angle_rad) + hy
                corners.append((int(rx), int(ry)))
            pygame.draw.polygon(self.screen, (255, 0, 0), corners, 2)

        elif hitbox.definition.shape == "line":
            length_px = int(hitbox.definition.length * Config.TILE_SIZE)
            angle_rad = math.radians(hitbox.facing_angle)
            end_x = hx + math.cos(angle_rad) * length_px
            end_y = hy + math.sin(angle_rad) * length_px
            pygame.draw.line(self.screen, (255, 0, 0), (hx, hy), (int(end_x), int(end_y)), 2)
```

This debug visualization is invaluable for tuning hitbox sizes and positions. When red shapes overlap green circles, a hit registers. When they don't, nothing happens. The visual makes it immediately obvious when hitboxes are too big, too small, or misaligned.

---

## 10. Game Engine Integration

### 10.1 Scope of Changes to game_engine.py

`game_engine.py` is the orchestrator. It initializes systems, handles input, calls update on everything, and triggers rendering. Our changes fall into 4 categories:

1. **__init__()**: Import and construct new systems (~20 lines added)
2. **handle_events()**: Add dodge input (Space bar), buffer attacks during animations (~15 lines)
3. **update()**: Add new system updates, route hit events to damage pipeline (~40 lines)
4. **render()**: Pass new systems to renderer (~5 lines of parameter additions)

Total: ~80 lines added to a 10,098-line file. Minimal footprint.

### 10.2 __init__() Additions

After `self.combat_manager` is created (currently around line 170):

```python
# === ACTION COMBAT SYSTEMS ===
from combat import USE_ACTION_COMBAT
if USE_ACTION_COMBAT:
    from combat.hitbox_system import HitboxSystem
    from combat.projectile_system import ProjectileSystem
    from combat.attack_state_machine import AttackStateMachine
    from combat.player_actions import PlayerActionSystem
    from combat.screen_effects import ScreenEffects
    from combat.combat_data_loader import CombatDataLoader
    from animation.animation_manager import AnimationManager
    from animation.combat_particles import CombatParticleSystem

    self.combat_data = CombatDataLoader(get_resource_path(""))
    self.combat_data.load_all()

    self.animation_manager = AnimationManager.get_instance()
    self.hitbox_system = HitboxSystem()
    self.projectile_system = ProjectileSystem(self.hitbox_system)
    self.player_actions = PlayerActionSystem(self.character)
    self.screen_effects = ScreenEffects()
    self.combat_particles = CombatParticleSystem()
    self.player_attack_sm = AttackStateMachine('player')

    # Register player hurtbox
    self.hitbox_system.register_hurtbox('player', radius=0.35)
else:
    self.animation_manager = None
    self.hitbox_system = None
    self.projectile_system = None
    self.player_actions = None
    self.screen_effects = None
    self.combat_particles = None
    self.player_attack_sm = None
    self.combat_data = None
```

The `else` branch ensures all attributes exist even when action combat is off, preventing AttributeError throughout the codebase.

### 10.3 handle_events() — Input Changes

**Dodge input** (in the KEYDOWN handler):
```python
elif event.key == pygame.K_SPACE:
    if USE_ACTION_COMBAT and self.player_actions:
        dir_x = dir_y = 0
        if pygame.K_w in self.keys_pressed: dir_y -= 1
        if pygame.K_s in self.keys_pressed: dir_y += 1
        if pygame.K_a in self.keys_pressed: dir_x -= 1
        if pygame.K_d in self.keys_pressed: dir_x += 1
        self.player_actions.try_dodge((dir_x, dir_y))
```

**Attack input buffering** (modifying the existing left-click attack block):

The existing code at lines 6771-6812 checks `1 in self.mouse_buttons_pressed`. We wrap this:

```python
if USE_ACTION_COMBAT and self.player_attack_sm:
    # Action combat: route through state machine
    if 1 in self.mouse_buttons_pressed:
        if self.player_attack_sm.is_attacking:
            # Buffer the attack for combo chaining
            self.player_actions.input_buffer.buffer("attack", {"hand": "mainHand"})
        elif self.character.can_attack('mainHand'):
            # Start new attack
            can_attack = True
            if hasattr(self.character, 'status_manager'):
                if self.character.status_manager.has_status('stun') or \
                   self.character.status_manager.has_status('freeze'):
                    can_attack = False
            if can_attack:
                mouse_pos = pygame.mouse.get_pos()
                if mouse_pos[0] < Config.VIEWPORT_WIDTH:
                    wx = (mouse_pos[0] - Config.VIEWPORT_WIDTH // 2) / Config.TILE_SIZE + self.camera.position.x
                    wy = (mouse_pos[1] - Config.VIEWPORT_HEIGHT // 2) / Config.TILE_SIZE + self.camera.position.y

                    # Compute facing angle toward mouse
                    aim_dx = wx - self.character.position.x
                    aim_dy = wy - self.character.position.y
                    self.character.facing_angle = math.degrees(math.atan2(aim_dy, aim_dx))

                    # Get weapon type and attack definition
                    weapon_type = self._get_weapon_type('mainHand')
                    attack_def = self.combat_data.get_weapon_attack(
                        weapon_type, self.player_attack_sm.combo_count)

                    effect_tags, effect_params = self._get_weapon_effect_data('mainHand')
                    damage_context = {
                        'hand': 'mainHand',
                        'effect_tags': effect_tags,
                        'effect_params': effect_params,
                    }
                    self.player_attack_sm.start_attack(attack_def, damage_context)

                    # Trigger animation
                    self.animation_manager.play('player_slash', attack_def.animation_id)

else:
    # Legacy instant combat (existing code unchanged)
    if 1 in self.mouse_buttons_pressed and self.character.can_attack('mainHand'):
        # ... existing lines 6771-6812 ...
```

### 10.4 update() — System Ticking

The new update block is inserted into `update()` after player movement and before `combat_manager.update()`:

```python
if USE_ACTION_COMBAT and self.hitbox_system:
    # Apply time dilation
    raw_dt_ms = dt * 1000
    effective_dt_ms = self.screen_effects.get_effective_dt(raw_dt_ms)

    # Skip game updates during hit pause
    if not self.screen_effects.is_paused:
        # Update player actions (dodge roll, cooldowns)
        self.player_actions.update(effective_dt_ms)

        # Apply dodge movement override
        if self.player_actions.is_dodging:
            dodge_vel = self.player_actions.get_dodge_velocity()
            self.character.move(dodge_vel[0], dodge_vel[1], self.world)

        # Set player hurtbox invulnerability from dodge
        player_hb = self.hitbox_system.hurtboxes.get('player')
        if player_hb:
            player_hb.invulnerable = self.player_actions.is_invulnerable

        # Update player attack state machine
        player_events = self.player_attack_sm.update(effective_dt_ms)

        # Process state machine events
        for event in player_events:
            if event.event_type == "phase_change":
                phase = event.data["phase"]
                if phase == "active":
                    # Spawn hitbox or projectile
                    attack_def = self.player_attack_sm.current_attack
                    pos = (self.character.position.x, self.character.position.y)
                    facing = self.character.facing_angle

                    if attack_def.projectile_id:
                        proj_def = self.combat_data.get_projectile(attack_def.projectile_id)
                        self.projectile_system.spawn(proj_def, pos, facing, 'player',
                                                      self.player_attack_sm.damage_context)
                    else:
                        hitbox_def = self.combat_data.get_hitbox_def(attack_def)
                        hitbox_pos = hitbox_def.compute_world_position(pos[0], pos[1], facing)
                        self.hitbox_system.spawn_hitbox(hitbox_def, hitbox_pos, facing,
                                                         'player', attack_def.active_ms,
                                                         self.player_attack_sm.damage_context)

                elif phase in ("cooldown", "idle"):
                    # Check input buffer for combo
                    buffered = self.player_actions.input_buffer.consume()
                    if buffered and buffered[0] == "attack":
                        weapon_type = self._get_weapon_type('mainHand')
                        next_def = self.combat_data.get_weapon_attack(
                            weapon_type, self.player_attack_sm.combo_count)
                        if next_def:
                            self.player_attack_sm.start_attack(next_def,
                                self.player_attack_sm.damage_context)

        # Update all hurtbox positions
        positions = {'player': (self.character.position.x, self.character.position.y)}
        for enemy in self.combat_manager.get_all_active_enemies():
            if enemy.is_alive:
                eid = f"enemy_{id(enemy)}"
                positions[eid] = (enemy.position[0], enemy.position[1])
        self.hitbox_system.update_hurtbox_positions(positions)

        # Check hitbox collisions
        hit_events = self.hitbox_system.update(effective_dt_ms)
        for hit in hit_events:
            self._process_combat_hit(hit)

        # Update projectiles
        proj_hits = self.projectile_system.update(effective_dt_ms)
        for hit in proj_hits:
            self._process_combat_hit(hit)

    # Always update screen effects (even during pause, to decay timers)
    self.screen_effects.update(raw_dt_ms)

    # Update animations
    self.animation_manager.update_all(effective_dt_ms if not self.screen_effects.is_paused else 0)

    # Update combat particles
    self.combat_particles.update(effective_dt_ms if not self.screen_effects.is_paused else 0)
```

### 10.5 _process_combat_hit() — The Router

```python
def _process_combat_hit(self, hit: HitEvent) -> None:
    """Route a hit event to the appropriate damage pipeline."""
    if hit.attacker_id == 'player':
        # Find the enemy
        for enemy in self.combat_manager.get_all_active_enemies():
            if f"enemy_{id(enemy)}" == hit.target_id and enemy.is_alive:
                # Prevent multi-hit
                if not self.player_attack_sm.record_hit(hit.target_id):
                    return

                ctx = hit.damage_context
                damage, is_crit, loot = self.combat_manager.player_attack_enemy_with_tags(
                    enemy, ctx['effect_tags'], ctx['effect_params'])

                # Visual feedback
                self.damage_numbers.append(DamageNumber(
                    int(damage),
                    Position(enemy.position[0], enemy.position[1], 0),
                    is_crit))

                self.screen_effects.flash_entity(hit.target_id, (255, 255, 255), 80)
                self.combat_particles.emit_hit_sparks(
                    enemy.position[0], enemy.position[1], "physical", damage)

                if is_crit:
                    self.screen_effects.hit_pause(40)
                    self.screen_effects.screen_shake(4, 100)

                if not enemy.is_alive:
                    self.add_notification(f"Defeated {enemy.definition.name}!", (255, 215, 0))
                    self.screen_effects.hit_pause(60)
                    self.screen_effects.screen_shake(3, 80)
                    if loot:
                        mat_db = MaterialDatabase.get_instance()
                        for material_id, qty in loot:
                            mat = mat_db.get_material(material_id)
                            item_name = mat.name if mat else material_id
                            self.add_notification(f"+{qty} {item_name}", (100, 255, 100))
                break
    else:
        # Enemy hit player
        for enemy in self.combat_manager.get_all_active_enemies():
            if f"enemy_{id(enemy)}" == hit.attacker_id:
                # Check dodge i-frames
                if self.player_actions.is_invulnerable:
                    return

                self.combat_manager._enemy_attack_player(
                    enemy, shield_blocking=self.character.is_blocking)

                self.screen_effects.flash_entity('player', (255, 100, 100), 100)
                self.screen_effects.screen_shake(3, 80)
                break
```

### 10.6 render() Changes

Minimal — just pass new systems to the renderer:

```python
# In render(), replacing the render_world call:
if USE_ACTION_COMBAT:
    self.renderer.render_world(
        self.world, self.camera, self.character, self.damage_numbers,
        self.combat_manager,
        animation_manager=self.animation_manager,
        hitbox_system=self.hitbox_system,
        projectile_system=self.projectile_system,
        screen_effects=self.screen_effects,
        player_actions=self.player_actions,
        combat_particles=self.combat_particles
    )
else:
    self.renderer.render_world(self.world, self.camera, self.character,
                                self.damage_numbers, self.combat_manager)
```

### 10.7 Enemy Hurtbox Registration

When enemies spawn, they need hurtbox registration. In `combat_manager.spawn_enemies_in_chunk()`:

```python
# After enemy is created:
if USE_ACTION_COMBAT and hasattr(self, '_hitbox_system') and self._hitbox_system:
    eid = f"enemy_{id(enemy)}"
    hurtbox_radius = self.combat_data.get_enemy_hurtbox_radius(enemy.definition.enemy_id)
    self._hitbox_system.register_hurtbox(eid, hurtbox_radius)
    # Create enemy's attack state machine
    enemy.attack_state_machine = AttackStateMachine(eid)
```

And when enemies die/despawn:
```python
if USE_ACTION_COMBAT and hasattr(self, '_hitbox_system') and self._hitbox_system:
    eid = f"enemy_{id(enemy)}"
    self._hitbox_system.unregister_hurtbox(eid)
```

The combat_manager needs a reference to the hitbox_system, set during initialization:
```python
self.combat_manager._hitbox_system = self.hitbox_system
```

---

## 11. JSON Data Files

### 11.1 Directory: Animation-Data.JSON/

This follows the project convention: data directory names use `PascalCase-Kebab.JSON/`. All values are tunable without code changes.

### 11.2 weapon-attacks.json

Complete weapon attack definitions including combo chains:

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Weapon attack timing, hitboxes, and combo chains"
  },
  "weapons": {
    "unarmed": {
      "attacks": [
        {
          "attack_id": "unarmed_punch_1",
          "windup_ms": 80,
          "active_ms": 50,
          "recovery_ms": 80,
          "cooldown_ms": 100,
          "hitbox": { "shape": "arc", "radius": 1.0, "arc_degrees": 60, "offset_forward": 0.5 },
          "damage_multiplier": 0.5,
          "animation_id": "swing_fast",
          "can_be_interrupted": true,
          "movement_multiplier": 0.8,
          "combo_next": "unarmed_punch_2",
          "combo_window_ms": 400,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "unarmed_punch_2",
          "windup_ms": 60,
          "active_ms": 50,
          "recovery_ms": 100,
          "cooldown_ms": 100,
          "hitbox": { "shape": "arc", "radius": 1.0, "arc_degrees": 60, "offset_forward": 0.5 },
          "damage_multiplier": 0.6,
          "animation_id": "swing_fast_reverse",
          "can_be_interrupted": true,
          "movement_multiplier": 0.7,
          "combo_next": "unarmed_kick",
          "combo_window_ms": 400,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "unarmed_kick",
          "windup_ms": 120,
          "active_ms": 60,
          "recovery_ms": 150,
          "cooldown_ms": 200,
          "hitbox": { "shape": "arc", "radius": 1.2, "arc_degrees": 90, "offset_forward": 0.6 },
          "damage_multiplier": 0.8,
          "animation_id": "swing_heavy",
          "can_be_interrupted": true,
          "movement_multiplier": 0.5,
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": ["knockback"],
          "screen_shake": false
        }
      ]
    },
    "dagger": {
      "attacks": [
        {
          "attack_id": "dagger_stab_1",
          "windup_ms": 80,
          "active_ms": 60,
          "recovery_ms": 80,
          "cooldown_ms": 80,
          "hitbox": { "shape": "line", "length": 1.2, "offset_forward": 0.3 },
          "damage_multiplier": 0.8,
          "animation_id": "thrust_fast",
          "can_be_interrupted": true,
          "movement_multiplier": 0.9,
          "combo_next": "dagger_stab_2",
          "combo_window_ms": 350,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "dagger_stab_2",
          "windup_ms": 60,
          "active_ms": 60,
          "recovery_ms": 80,
          "cooldown_ms": 80,
          "hitbox": { "shape": "line", "length": 1.2, "offset_forward": 0.3 },
          "damage_multiplier": 0.9,
          "animation_id": "thrust_fast_reverse",
          "can_be_interrupted": true,
          "movement_multiplier": 0.9,
          "combo_next": "dagger_flurry",
          "combo_window_ms": 350,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "dagger_flurry",
          "windup_ms": 100,
          "active_ms": 80,
          "recovery_ms": 120,
          "cooldown_ms": 150,
          "hitbox": { "shape": "arc", "radius": 1.0, "arc_degrees": 120, "offset_forward": 0.4 },
          "damage_multiplier": 1.2,
          "animation_id": "swing_fast_wide",
          "can_be_interrupted": false,
          "movement_multiplier": 0.6,
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": ["bleed"],
          "screen_shake": false
        }
      ]
    },
    "sword_1h": {
      "attacks": [
        {
          "attack_id": "sword_1h_swing_1",
          "windup_ms": 150,
          "active_ms": 100,
          "recovery_ms": 100,
          "cooldown_ms": 100,
          "hitbox": { "shape": "arc", "radius": 1.5, "arc_degrees": 90, "offset_forward": 0.8 },
          "damage_multiplier": 1.0,
          "animation_id": "swing_medium",
          "can_be_interrupted": true,
          "movement_multiplier": 0.7,
          "combo_next": "sword_1h_swing_2",
          "combo_window_ms": 600,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "sword_1h_swing_2",
          "windup_ms": 120,
          "active_ms": 100,
          "recovery_ms": 80,
          "cooldown_ms": 100,
          "hitbox": { "shape": "arc", "radius": 1.5, "arc_degrees": 90, "offset_forward": 0.8 },
          "damage_multiplier": 1.0,
          "animation_id": "swing_medium_reverse",
          "can_be_interrupted": true,
          "movement_multiplier": 0.7,
          "combo_next": "sword_1h_heavy",
          "combo_window_ms": 600,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "sword_1h_heavy",
          "windup_ms": 200,
          "active_ms": 120,
          "recovery_ms": 180,
          "cooldown_ms": 200,
          "hitbox": { "shape": "arc", "radius": 1.8, "arc_degrees": 120, "offset_forward": 0.7 },
          "damage_multiplier": 1.5,
          "animation_id": "swing_heavy_overhead",
          "can_be_interrupted": false,
          "movement_multiplier": 0.4,
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": [],
          "screen_shake": true
        }
      ]
    },
    "sword_2h": {
      "attacks": [
        {
          "attack_id": "sword_2h_swing_1",
          "windup_ms": 250,
          "active_ms": 120,
          "recovery_ms": 180,
          "cooldown_ms": 150,
          "hitbox": { "shape": "arc", "radius": 2.0, "arc_degrees": 120, "offset_forward": 0.9 },
          "damage_multiplier": 1.3,
          "animation_id": "swing_heavy",
          "can_be_interrupted": true,
          "movement_multiplier": 0.5,
          "combo_next": "sword_2h_cleave",
          "combo_window_ms": 700,
          "status_tags": [],
          "screen_shake": false
        },
        {
          "attack_id": "sword_2h_cleave",
          "windup_ms": 300,
          "active_ms": 150,
          "recovery_ms": 250,
          "cooldown_ms": 200,
          "hitbox": { "shape": "arc", "radius": 2.2, "arc_degrees": 180, "offset_forward": 0.8 },
          "damage_multiplier": 1.8,
          "animation_id": "swing_heavy_wide",
          "can_be_interrupted": false,
          "movement_multiplier": 0.3,
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": [],
          "screen_shake": true
        }
      ]
    },
    "hammer_2h": {
      "attacks": [
        {
          "attack_id": "hammer_overhead",
          "windup_ms": 300,
          "active_ms": 100,
          "recovery_ms": 200,
          "cooldown_ms": 200,
          "hitbox": { "shape": "circle", "radius": 1.8, "offset_forward": 0.6 },
          "damage_multiplier": 1.5,
          "animation_id": "slam_overhead",
          "can_be_interrupted": true,
          "movement_multiplier": 0.3,
          "combo_next": "hammer_slam",
          "combo_window_ms": 800,
          "status_tags": [],
          "screen_shake": true
        },
        {
          "attack_id": "hammer_slam",
          "windup_ms": 350,
          "active_ms": 120,
          "recovery_ms": 300,
          "cooldown_ms": 300,
          "hitbox": { "shape": "circle", "radius": 2.5, "offset_forward": 0.0 },
          "damage_multiplier": 2.0,
          "animation_id": "slam_ground",
          "can_be_interrupted": false,
          "movement_multiplier": 0.0,
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": ["stun"],
          "screen_shake": true
        }
      ]
    },
    "bow": {
      "attacks": [
        {
          "attack_id": "bow_shot",
          "windup_ms": 200,
          "active_ms": 50,
          "recovery_ms": 150,
          "cooldown_ms": 200,
          "hitbox": { "shape": "circle", "radius": 0.3 },
          "damage_multiplier": 1.0,
          "animation_id": "draw_release",
          "can_be_interrupted": true,
          "movement_multiplier": 0.5,
          "projectile_id": "arrow_basic",
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": [],
          "screen_shake": false
        }
      ]
    },
    "staff": {
      "attacks": [
        {
          "attack_id": "staff_cast",
          "windup_ms": 180,
          "active_ms": 80,
          "recovery_ms": 120,
          "cooldown_ms": 150,
          "hitbox": { "shape": "circle", "radius": 0.4 },
          "damage_multiplier": 1.0,
          "animation_id": "cast_release",
          "can_be_interrupted": true,
          "movement_multiplier": 0.6,
          "projectile_id": "magic_bolt",
          "combo_next": null,
          "combo_window_ms": 0,
          "status_tags": [],
          "screen_shake": false
        }
      ]
    }
  }
}
```

### 11.3 enemy-attacks.json

See Section 7.2 for format. Covers all 16 enemy types with tier-appropriate attack counts:
- T1 (wolf_grey, slime_green, beetle_brown): 1 attack each
- T2 (wolf_dire, golem_stone, slime_acid, beetle_armored): 2 attacks each
- T3 (wolf_elder, golem_crystal, slime_crystal, inferno_drake, beetle_titan): 2-3 attacks, phase transitions
- T4 (void_wraith, void_archon, storm_titan, entity_primordial): 3-4 attacks, phase transitions

### 11.4 projectile-definitions.json

```json
{
  "metadata": { "version": "1.0" },
  "projectiles": {
    "arrow_basic": {
      "speed": 12.0,
      "max_range": 15.0,
      "hitbox": { "shape": "circle", "radius": 0.2 },
      "sprite_id": "arrow",
      "trail_type": null,
      "homing": 0.0,
      "gravity": 0.0,
      "piercing": false
    },
    "magic_bolt": {
      "speed": 10.0,
      "max_range": 12.0,
      "hitbox": { "shape": "circle", "radius": 0.3 },
      "sprite_id": "magic_bolt",
      "trail_type": "arcane_trail",
      "homing": 0.0,
      "gravity": 0.0,
      "piercing": false
    },
    "enemy_fireball": {
      "speed": 8.0,
      "max_range": 10.0,
      "hitbox": { "shape": "circle", "radius": 0.4 },
      "sprite_id": "fireball",
      "trail_type": "fire_trail",
      "homing": 0.0,
      "gravity": 0.0,
      "piercing": false,
      "aoe_on_hit": { "shape": "circle", "radius": 2.0 },
      "aoe_duration_ms": 100
    },
    "enemy_acid_spit": {
      "speed": 6.0,
      "max_range": 8.0,
      "hitbox": { "shape": "circle", "radius": 0.5 },
      "sprite_id": "acid_blob",
      "trail_type": "acid_trail",
      "homing": 0.0,
      "gravity": 2.0,
      "piercing": false
    },
    "enemy_crystal_beam": {
      "speed": 15.0,
      "max_range": 15.0,
      "hitbox": { "shape": "line", "length": 1.0 },
      "sprite_id": "crystal_shard",
      "trail_type": "arcane_trail",
      "homing": 0.0,
      "gravity": 0.0,
      "piercing": true
    }
  }
}
```

### 11.5 combat/combat_data_loader.py

This module loads all three JSON files and provides lookup methods:

```python
class CombatDataLoader:
    def __init__(self, resource_path: str):
        self.resource_path = resource_path
        self.weapon_attacks: Dict[str, List[AttackDefinition]] = {}
        self.enemy_attacks: Dict[str, dict] = {}  # enemy_id → {attacks, hurtbox_radius, phases}
        self.projectiles: Dict[str, ProjectileDefinition] = {}

    def load_all(self) -> None:
        self._load_weapon_attacks()
        self._load_enemy_attacks()
        self._load_projectiles()

    def get_weapon_attack(self, weapon_type: str, combo_index: int) -> Optional[AttackDefinition]:
        attacks = self.weapon_attacks.get(weapon_type, [])
        if not attacks:
            attacks = self.weapon_attacks.get("unarmed", [])
        index = combo_index % len(attacks) if attacks else 0
        return attacks[index] if attacks else None

    def get_enemy_hurtbox_radius(self, enemy_id: str) -> float:
        data = self.enemy_attacks.get(enemy_id)
        if data:
            return data.get("hurtbox_radius", 0.5)
        return 0.5  # Default

    def get_projectile(self, projectile_id: str) -> Optional[ProjectileDefinition]:
        return self.projectiles.get(projectile_id)
```

---

## 12. Migration Strategy: Legacy Coexistence

### 12.1 The USE_ACTION_COMBAT Flag

```python
# combat/__init__.py
USE_ACTION_COMBAT = True  # Set to False to revert to instant click-to-attack
```

When `False`:
- All new systems are constructed but never updated
- Player attacks go through the existing `player_attack_enemy_with_tags()` directly
- Enemy attacks fire instantly via `_enemy_attack_player()`
- No dodge, no hitboxes, no projectile travel time
- The game plays exactly like it does today

This flag exists for two purposes:
1. **Incremental development**: Build systems one at a time, test in isolation
2. **Emergency rollback**: If action combat introduces a game-breaking bug, one line reverts everything

### 12.2 Phase-by-Phase Rollout

The systems can be enabled incrementally:

**Phase A — Animations only** (no gameplay change):
- Enable AnimationManager
- Add idle bob to enemies, hit flash on damage
- Enable screen shake on kills
- USE_ACTION_COMBAT = False (instant attacks still)
- Purpose: Validate animation infrastructure without changing combat feel

**Phase B — Player attack state machine**:
- USE_ACTION_COMBAT = True for player only
- Player attacks have windup/active/recovery
- Enemies still attack instantly
- Purpose: Tune player attack timings

**Phase C — Hitboxes for player**:
- Player attacks use hitbox collision instead of distance check
- Enemy attacks still instant
- Purpose: Validate hitbox geometry and collision math

**Phase D — Enemy attack state machine + hitboxes**:
- Both player and enemy attacks phased
- Enemy telegraphs visible
- Purpose: Test the full combat loop without dodge

**Phase E — Dodge + projectiles**:
- Full system online
- Purpose: Final tuning pass

### 12.3 Save System Compatibility

The new systems add no persistent state that needs saving. Attack state machines reset on load. Hitboxes are transient. The only potential issue is enemies that were mid-attack when saved — they'll reset to IDLE on load, which is the correct behavior.

No changes to `save_manager.py` required.

---

## 13. Testing Checkpoints

### 13.1 Unit Tests (can run without Pygame display)

**Hitbox collision math** — test each shape:
```python
def test_circle_circle_collision():
    # Overlapping circles → True
    # Non-overlapping → False
    # Edge case: exactly touching → True

def test_arc_circle_inside_arc():
    # Circle center within arc angle and radius → True

def test_arc_circle_outside_angle():
    # Circle center outside arc angle but within radius → False

def test_arc_circle_edge_overlap():
    # Circle center outside arc but circle edge overlaps arc edge → True

def test_rect_circle_rotated():
    # Rotated rectangle collision

def test_line_circle():
    # Point on line segment closest to circle center
```

**Attack state machine transitions**:
```python
def test_idle_to_windup():
    sm = AttackStateMachine("test")
    result = sm.start_attack(sword_def, {})
    assert result == True
    assert sm.phase == AttackPhase.WINDUP

def test_full_cycle():
    sm = AttackStateMachine("test")
    sm.start_attack(sword_def, {})
    events = sm.update(sword_def.windup_ms + 1)  # Past windup
    assert sm.phase == AttackPhase.ACTIVE
    events = sm.update(sword_def.active_ms + 1)
    assert sm.phase == AttackPhase.RECOVERY
    # ... through to IDLE

def test_multi_hit_prevention():
    sm = AttackStateMachine("test")
    sm.start_attack(sword_def, {})
    assert sm.record_hit("enemy_1") == True
    assert sm.record_hit("enemy_1") == False  # Can't hit same target twice

def test_combo_chain():
    sm = AttackStateMachine("test")
    sm.start_attack(swing_1_def, {})
    # Complete full cycle...
    # Start next within combo window
    sm.start_attack(swing_2_def, {})
    assert sm.combo_count == 1
```

**Projectile physics**:
```python
def test_projectile_straight_line():
    proj = Projectile(arrow_def, (0, 0), 0.0, "player", {})
    proj.update(1.0)  # 1 second
    assert abs(proj.x - arrow_def.speed) < 0.01

def test_projectile_max_range():
    proj = Projectile(arrow_def, (0, 0), 0.0, "player", {})
    for _ in range(100):
        proj.update(0.1)
    assert proj.alive == False

def test_projectile_gravity_arc():
    proj = Projectile(acid_def, (0, 0), 0.0, "player", {})
    proj.update(1.0)
    assert proj.vy > 0  # Gravity pulled it down
```

### 13.2 Visual Integration Tests (require Pygame)

These are manual playtests with debug mode (F1) enabled:

1. **Slash arc visible**: Attack → see red debug hitbox in correct position relative to player facing
2. **Enemy telegraph**: Approach enemy → see colored fill during windup → hitbox appears during active
3. **Dodge i-frames**: Dodge through enemy attack → blue hurtbox during i-frames → no damage taken
4. **Combo chain**: Attack 3 times quickly → see different slash animations → combo counter increments
5. **Projectile travel**: Use bow → see arrow travel with rotation → hits enemy at destination
6. **Screen shake**: Kill enemy with crit → feel the shake + pause
7. **Tier scaling**: Visit T1-T4 areas → enemies visually scale up → hurtboxes scale appropriately

### 13.3 Balance Verification

After all systems are online, verify the damage pipeline is unchanged:

```python
def test_damage_formula_preserved():
    """Same weapon, same enemy, same stats → same damage range"""
    # Set up identical combat scenario
    # Run with USE_ACTION_COMBAT = True and False
    # Verify damage output is within expected range
    # (Not identical due to state machine's damage_multiplier,
    #  but base pipeline values must match)
```

### 13.4 Performance Profiling

With F1 debug overlay, track:
- Frame time: Must stay under 16.67ms (60fps) with 50 entities
- Hitbox checks per frame: Should be <100 (3 active hitboxes × 30 hurtboxes)
- Particle count: Should stay under 400 budget
- Surface cache size: Monitor via AnimationManager stats

---

## Summary: Implementation Order

1. Create `animation/` and `combat/` packages with `__init__.py`
2. Implement `animation_data.py`, `sprite_animation.py`, `animation_manager.py`
3. Implement `procedural.py` — start with `create_hit_flash()` (simplest)
4. Implement `combat_event.py`, `attack_state_machine.py`
5. Implement `hitbox_system.py` with circle and arc collision
6. Write unit tests for collision math and state machine
7. Create `Animation-Data.JSON/weapon-attacks.json` with sword_1h
8. Implement `combat_data_loader.py`
9. Integrate into `game_engine.py` with USE_ACTION_COMBAT flag
10. Modify `renderer.py` — enemy tier scaling, hit flash, debug hitboxes
11. Implement `player_actions.py` — dodge roll and input buffer
12. Implement `projectile_system.py`
13. Implement `screen_effects.py`
14. Create `enemy-attacks.json` for all 16 enemies
15. Modify `enemy.py` — facing_angle, attack_state_machine, hurtbox_radius
16. Implement attack telegraphs in renderer
17. Implement `combat_particles.py`
18. Create `projectile-definitions.json`
19. Full integration testing and tuning pass

Each step produces a testable, functional intermediate state. No step depends on a future step. The game remains playable throughout.

---

**Last updated**: 2026-03-06
**For**: Direct coding reference — next task implements from this blueprint
**Total new files**: 10 Python modules + 3 JSON data files
**Total lines modified in existing files**: ~100 lines across game_engine.py, renderer.py, combat_manager.py, enemy.py
