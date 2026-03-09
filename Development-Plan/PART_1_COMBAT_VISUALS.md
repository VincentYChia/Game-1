# Part 1: Combat & Visual Overhaul

**Priority**: P1 — First
**Goal**: Transform click-to-attack into full action combat with projectile physics, dodgeable attacks, tier-scaled enemies, and polished visuals.

> **STATUS (2026-03-09)**: Phases 1.1–1.6 are **structurally complete** — all systems implemented and functional. Phase 1.7 (Integration & Polish) needs a **grand visual overhaul** — current procedural geometry visuals (arcs, polygons) need replacement with proper animated sprites and high-quality VFX. A new plan will be created for this overhaul.

---

## What Exists Today

### Combat (`Combat/combat_manager.py` — 1,655 lines)
- **Attack model**: Player clicks → `calculate_hit_damage()` → instant damage applied
- **Damage pipeline**: base × hand × STR × skill × class × crit - defense (preserved exactly)
- **Enemy targeting**: Click on enemy sprite → check distance → instant hit
- **No windup, no travel time, no dodge window**
- **Status effects**: DoT, CC, buffs all work but trigger instantly

### Enemy AI (`Combat/enemy.py` — 867 lines)
- **FSM states**: IDLE, PATROL, CHASE, ATTACK, RETREAT, STUNNED
- **Detection**: Circle-based aggro radius
- **Movement**: Direct pathfinding toward player
- **Attacks**: Timer-based (attack_cooldown), instant damage at range
- **All enemies same visual size** regardless of tier

### Rendering (`rendering/renderer.py` — 2,782 lines)
- **Static sprites**: Single image per entity, no frames
- **Enemy rendering**: `_draw_enemies()` — scales 1024x1024 sprites to fixed size (~48-64px)
- **Damage text**: Basic floating numbers, minimal animation
- **No particle system** for combat (exists for crafting minigames in `minigame_effects.py`)
- **Draw order**: tiles → resources → entities → projectiles → UI

### Assets
- 16 enemy sprites, all 1024x1024 JPEG (mislabeled .png)
- No sprite sheets, no animation frames
- No projectile sprites
- No attack effect sprites

---

## Phase 1.1: Animation Framework

**New files**: `animation/sprite_animation.py`, `animation/animation_manager.py`, `animation/animation_data.py`

### Core Classes

```python
@dataclass
class AnimationFrame:
    """Single frame of an animation"""
    surface: pygame.Surface        # Pre-rendered frame
    duration_ms: float             # How long this frame displays
    hitbox: Optional[HitboxData]   # Active hitbox during this frame (None = no hitbox)
    offset: Tuple[float, float]    # Sprite offset from entity center (for swing arcs)

@dataclass
class AnimationDefinition:
    """Complete animation sequence — loaded from JSON"""
    animation_id: str
    frames: List[AnimationFrame]
    loop: bool                     # True for idle/walk, False for attacks
    total_duration_ms: float       # Sum of all frame durations

class SpriteAnimation:
    """Plays an AnimationDefinition on an entity"""
    def __init__(self, definition: AnimationDefinition)
    def update(self, dt_ms: float) -> None
    def get_current_frame(self) -> AnimationFrame
    def is_finished(self) -> bool
    def reset(self) -> None
    @property
    def current_hitbox(self) -> Optional[HitboxData]

class AnimationManager:
    """Global registry — updates all active animations each frame"""
    _instance: ClassVar[Optional['AnimationManager']] = None

    def register(self, entity_id: str, animation: SpriteAnimation) -> None
    def update_all(self, dt_ms: float) -> None
    def get_current_frame(self, entity_id: str) -> Optional[AnimationFrame]
    def play(self, entity_id: str, anim_id: str, on_complete: Callable = None) -> None
```

### Animation Generation Strategy

Since we have single static sprites (not sprite sheets), animations are generated programmatically:

1. **Weapon swings**: Rotate weapon sprite through arc (e.g., -45° to +45° over 300ms)
2. **Enemy attacks**: Scale + color tint pulses (windup glow → strike flash)
3. **Movement**: Subtle bob/sway on idle, lean in direction of movement
4. **Hit reactions**: Brief white flash + knockback offset
5. **Death**: Fade out + optional collapse animation

```python
class ProceduralAnimations:
    """Generate animation frames from single static sprites"""

    @staticmethod
    def create_swing_arc(weapon_sprite: Surface, arc_degrees: float,
                         duration_ms: float, num_frames: int) -> AnimationDefinition:
        """Rotate weapon through arc — used for melee attacks"""

    @staticmethod
    def create_windup_pulse(sprite: Surface, scale_range: Tuple[float, float],
                           tint_color: Color, duration_ms: float) -> AnimationDefinition:
        """Scale + tint for attack telegraph"""

    @staticmethod
    def create_hit_flash(sprite: Surface, flash_duration_ms: float) -> AnimationDefinition:
        """White flash on taking damage"""

    @staticmethod
    def create_idle_bob(sprite: Surface, amplitude: float,
                       period_ms: float) -> AnimationDefinition:
        """Gentle vertical bob for idle state"""
```

### JSON Schema: `Animation-Data.JSON/attack-animations.json`

```json
{
  "metadata": { "version": "1.0" },
  "weapon_animations": {
    "sword_1h": {
      "swing": {
        "arc_degrees": 90,
        "duration_ms": 350,
        "num_frames": 6,
        "phases": {
          "windup": { "duration_ms": 150, "scale": 0.9 },
          "active": { "duration_ms": 100, "hitbox_active": true },
          "recovery": { "duration_ms": 100 }
        }
      },
      "thrust": {
        "arc_degrees": 15,
        "duration_ms": 280,
        "num_frames": 5,
        "phases": {
          "windup": { "duration_ms": 100 },
          "active": { "duration_ms": 80, "hitbox_active": true },
          "recovery": { "duration_ms": 100 }
        }
      }
    },
    "hammer_2h": {
      "slam": {
        "arc_degrees": 120,
        "duration_ms": 600,
        "num_frames": 8,
        "phases": {
          "windup": { "duration_ms": 300, "scale": 1.1 },
          "active": { "duration_ms": 100, "hitbox_active": true, "screen_shake": true },
          "recovery": { "duration_ms": 200 }
        }
      }
    }
  }
}
```

---

## Phase 1.2: Attack State Machine

**New file**: `combat/attack_state_machine.py`

### The Core Change

Replace instant damage with phased attacks:

```
CURRENT:  Click → calculate_hit_damage() → apply damage → done
NEW:      Click → WINDUP (telegraph) → ACTIVE (hitbox live) → RECOVERY (vulnerable) → IDLE
```

### State Machine

```python
class AttackPhase(Enum):
    IDLE = "idle"
    WINDUP = "windup"       # Telegraph — animation plays, can be interrupted
    ACTIVE = "active"       # Hitbox is live — damage dealt on collision
    RECOVERY = "recovery"   # Animation finishing — attacker is vulnerable
    COOLDOWN = "cooldown"   # Can't attack again yet

@dataclass
class AttackDefinition:
    """Loaded from JSON — defines timing for one attack type"""
    attack_id: str
    windup_ms: float          # How long the telegraph lasts
    active_ms: float          # How long the hitbox is active
    recovery_ms: float        # Vulnerability window after
    cooldown_ms: float        # Time before next attack
    hitbox: HitboxDefinition  # Shape and size of damage zone
    damage_multiplier: float  # Multiplied with base damage pipeline
    animation_id: str         # Which animation to play
    can_be_interrupted: bool  # Can windup be cancelled by damage?
    projectile_id: Optional[str]  # If set, spawns projectile in ACTIVE phase

class AttackStateMachine:
    """Manages attack phases for one entity (player or enemy)"""

    def __init__(self, entity_id: str):
        self.phase: AttackPhase = AttackPhase.IDLE
        self.phase_timer: float = 0.0
        self.current_attack: Optional[AttackDefinition] = None
        self.hits_this_swing: Set[str] = set()  # Prevent multi-hit per swing

    def start_attack(self, attack_def: AttackDefinition) -> bool:
        """Begin attack if in IDLE. Returns False if can't attack."""

    def update(self, dt_ms: float) -> List[CombatEvent]:
        """Advance state machine. Returns events (phase transitions, hits)."""

    def interrupt(self) -> bool:
        """Cancel attack during WINDUP. Returns True if interrupted."""

    def is_vulnerable(self) -> bool:
        """True during RECOVERY — bonus damage window."""

    @property
    def is_attacking(self) -> bool:
        """True if not IDLE."""
```

### Integration with Existing Damage Pipeline

The damage pipeline (`calculate_hit_damage()`) is **preserved exactly**. The state machine only controls **when** damage is calculated, not **how**:

```python
# In refactored combat_manager.py
def process_attack_hit(self, attacker, target, attack_def):
    """Called when ACTIVE phase hitbox overlaps target hurtbox"""
    # Existing pipeline — UNCHANGED
    damage = self.calculate_hit_damage(attacker, target)
    # Apply attack-specific multiplier (new)
    damage *= attack_def.damage_multiplier
    # Rest of existing logic (enchantments, status effects, etc.)
    self.apply_damage(target, damage)
```

### Player Attack Flow (New)

```
1. Player presses attack key / clicks
2. AttackStateMachine.start_attack(weapon_attack_def)
3. WINDUP phase begins:
   - Weapon swing animation starts (backswing)
   - Player movement slowed (not stopped)
   - Visual telegraph (weapon trails, enemy outline for enemy attacks)
4. ACTIVE phase:
   - Hitbox spawned at weapon tip position
   - Each frame: check hitbox vs all enemy hurtboxes
   - On overlap: process_attack_hit() — damage pipeline fires ONCE per enemy per swing
5. RECOVERY phase:
   - Animation finishes (follow-through)
   - Player slightly slowed
   - Can be cancelled into dodge (input buffering)
6. COOLDOWN:
   - Short delay before next attack allowed
   - Player moves normally
```

### Enemy Attack Flow (New)

```
1. Enemy AI decides to attack (existing FSM ATTACK state)
2. AttackStateMachine.start_attack(enemy_attack_def)
3. WINDUP phase:
   - Visual telegraph: enemy glows/charges/raises weapon
   - CRITICAL: Long enough for player to react and dodge
   - T1: 400ms windup, T2: 350ms, T3: 250ms, T4: 200ms (faster = harder)
4. ACTIVE phase:
   - Hitbox or projectile spawned
   - Player can dodge through with i-frames
5. RECOVERY/COOLDOWN: Enemy is vulnerable, player can counter
```

### Attack Timing by Weapon Type (JSON-driven)

| Weapon | Windup | Active | Recovery | Total | Feel |
|--------|--------|--------|----------|-------|------|
| Dagger | 80ms | 60ms | 80ms | 220ms | Fast, precise |
| Sword 1H | 150ms | 100ms | 100ms | 350ms | Balanced |
| Sword 2H | 250ms | 120ms | 180ms | 550ms | Heavy, committal |
| Hammer | 300ms | 100ms | 200ms | 600ms | Slow, devastating |
| Bow | 200ms | 50ms | 150ms | 400ms | Ranged, projectile on active |
| Staff | 180ms | 80ms | 120ms | 380ms | Magic, projectile |

---

## Phase 1.3: Hitbox & Hurtbox System

**New file**: `combat/hitbox_system.py`

### Hitbox Types

```python
class HitboxShape(Enum):
    CIRCLE = "circle"         # Radius-based (melee swings, explosions)
    RECT = "rect"             # Rectangle (beam attacks, wide swings)
    ARC = "arc"               # Pie-slice (cone attacks, sweeping strikes)
    LINE = "line"             # Thin line (piercing attacks, laser beams)

@dataclass
class HitboxDefinition:
    """Shape and properties of a damage zone — loaded from JSON"""
    shape: HitboxShape
    # Shape parameters (only relevant ones used per shape)
    radius: float = 1.0           # CIRCLE, ARC
    width: float = 1.0            # RECT, LINE
    height: float = 1.0           # RECT
    arc_degrees: float = 90.0     # ARC
    length: float = 1.0           # LINE
    # Offset from entity center (in tiles)
    offset_x: float = 0.0
    offset_y: float = 0.0
    # Behavior
    follows_facing: bool = True   # Rotate with entity facing direction
    piercing: bool = False        # Hit multiple targets?

@dataclass
class ActiveHitbox:
    """A hitbox that exists in the world right now"""
    definition: HitboxDefinition
    world_x: float                # Center position in world coords
    world_y: float                # Center position in world coords
    facing_angle: float           # Rotation in degrees
    owner_id: str                 # Who created this hitbox
    remaining_ms: float           # Time until despawn
    hits: Set[str]                # Entities already hit (prevent double-hit)

class Hurtbox:
    """Damageable area of an entity — usually a circle matching sprite bounds"""
    def __init__(self, entity_id: str, radius: float):
        self.entity_id = entity_id
        self.radius = radius
        self.world_x: float = 0.0
        self.world_y: float = 0.0
        self.invulnerable: bool = False  # True during dodge i-frames

class HitboxSystem:
    """Manages all active hitboxes and checks collisions each frame"""
    _instance: ClassVar[Optional['HitboxSystem']] = None

    def __init__(self):
        self.active_hitboxes: List[ActiveHitbox] = []
        self.hurtboxes: Dict[str, Hurtbox] = {}  # entity_id → hurtbox

    def spawn_hitbox(self, hitbox_def: HitboxDefinition,
                     world_pos: Tuple[float, float],
                     facing: float, owner_id: str,
                     duration_ms: float) -> ActiveHitbox:
        """Create a new hitbox in the world"""

    def register_hurtbox(self, entity_id: str, radius: float) -> Hurtbox:
        """Register a damageable entity"""

    def update(self, dt_ms: float) -> List[HitEvent]:
        """Check all hitbox-vs-hurtbox collisions. Returns hit events."""

    def _check_collision(self, hitbox: ActiveHitbox, hurtbox: Hurtbox) -> bool:
        """Shape-specific collision detection"""
        # CIRCLE vs CIRCLE: distance < hitbox.radius + hurtbox.radius
        # RECT vs CIRCLE: axis-aligned rect intersection
        # ARC vs CIRCLE: distance check + angle within arc
        # LINE vs CIRCLE: closest point on line segment to circle center
```

### Visual Debug Mode

When F1 debug mode is active, render hitboxes:
- **Red** outlines for active attack hitboxes
- **Green** outlines for entity hurtboxes
- **Blue** outlines for dodge i-frame hurtboxes (invulnerable)

---

## Phase 1.4: Projectile System

**New file**: `combat/projectile_system.py`

### Projectile Entity

```python
@dataclass
class ProjectileDefinition:
    """Loaded from JSON — defines projectile behavior"""
    projectile_id: str
    speed: float                # Tiles per second
    max_range: float            # Tiles before despawn
    hitbox: HitboxDefinition    # Damage area (usually small circle or line)
    sprite_id: str              # Visual representation
    trail_effect: Optional[str] # Particle trail type
    homing: float = 0.0        # 0 = straight, 1 = perfect tracking
    gravity: float = 0.0       # Downward acceleration (for arcing projectiles)
    piercing: bool = False      # Pass through first target?
    aoe_on_hit: Optional[HitboxDefinition] = None  # Explode on contact?

class Projectile:
    """Live projectile in the world"""
    def __init__(self, definition: ProjectileDefinition,
                 start_pos: Tuple[float, float],
                 direction: Tuple[float, float],
                 owner_id: str,
                 damage_context: dict):
        self.pos_x, self.pos_y = start_pos
        self.vel_x = direction[0] * definition.speed
        self.vel_y = direction[1] * definition.speed
        self.distance_traveled: float = 0.0
        self.alive: bool = True

    def update(self, dt_seconds: float) -> None:
        """Move projectile, apply gravity/homing, check lifetime"""

class ProjectileSystem:
    """Manages all active projectiles"""
    _instance: ClassVar[Optional['ProjectileSystem']] = None

    def __init__(self, hitbox_system: HitboxSystem):
        self.projectiles: List[Projectile] = []
        self.hitbox_system = hitbox_system

    def spawn(self, proj_def: ProjectileDefinition,
              start: Tuple[float, float],
              target: Tuple[float, float],
              owner_id: str, damage_context: dict) -> Projectile:
        """Create projectile aimed at target position"""

    def update(self, dt_seconds: float) -> List[HitEvent]:
        """Move all projectiles, check collisions, despawn expired"""
```

### Projectile Definitions (JSON)

```json
{
  "projectiles": {
    "arrow_basic": {
      "speed": 12.0,
      "max_range": 15.0,
      "hitbox": { "shape": "circle", "radius": 0.3 },
      "sprite_id": "arrow",
      "trail_effect": null,
      "piercing": false
    },
    "fireball": {
      "speed": 8.0,
      "max_range": 10.0,
      "hitbox": { "shape": "circle", "radius": 0.4 },
      "sprite_id": "fireball",
      "trail_effect": "fire_trail",
      "aoe_on_hit": { "shape": "circle", "radius": 2.0 },
      "piercing": false
    },
    "enemy_spit": {
      "speed": 6.0,
      "max_range": 8.0,
      "hitbox": { "shape": "circle", "radius": 0.5 },
      "sprite_id": "acid_blob",
      "trail_effect": "acid_drip",
      "gravity": 2.0
    }
  }
}
```

### Key Design: Dodgeable Projectiles

Projectiles have **real travel time**. A fireball at 8 tiles/sec aimed at a player 5 tiles away takes **625ms** to arrive. At player speed 0.15 tiles/frame (9 tiles/sec at 60fps), the player can sidestep in time **if they react during the enemy's windup**.

This is where the combat loop emerges:
```
Enemy WINDUP (visual telegraph) → Player reads attack type →
  Player dodges / moves → Projectile misses
  Player doesn't react → Projectile hits → Damage pipeline
```

---

## Phase 1.5: Player Actions

### Dodge Roll

```python
class PlayerActionSystem:
    """Manages player movement actions beyond basic walking"""

    def __init__(self, character):
        self.dodge_cooldown: float = 0.0
        self.dodge_duration_ms: float = 250.0     # Roll duration
        self.dodge_speed_mult: float = 3.0        # Speed multiplier during roll
        self.dodge_cooldown_ms: float = 800.0     # Time between dodges
        self.iframe_duration_ms: float = 200.0    # Invulnerability window
        self.is_dodging: bool = False
        self.iframe_timer: float = 0.0

    def dodge(self, direction: Tuple[float, float]) -> bool:
        """Initiate dodge roll in direction. Returns False if on cooldown."""

    def update(self, dt_ms: float) -> None:
        """Update dodge state, i-frame timer, cooldowns"""
```

### Input Buffering

```python
class InputBuffer:
    """Queues inputs during attack animations for responsive chaining"""
    BUFFER_WINDOW_MS = 200  # Accept inputs this far before current action ends

    def __init__(self):
        self.buffered_action: Optional[str] = None
        self.buffer_timer: float = 0.0

    def buffer(self, action: str) -> None:
        """Queue an action to execute when current one ends"""

    def consume(self) -> Optional[str]:
        """Get and clear buffered action if still valid"""
```

### Attack Combos (Simple)

Consecutive attacks within a window chain into different animations:
- **Hit 1**: Normal swing (sword arc left-to-right)
- **Hit 2**: Return swing (right-to-left, slightly faster)
- **Hit 3**: Heavy finisher (overhead, slower, more damage, bigger hitbox)

Combo resets if player doesn't attack within 600ms of recovery end.

---

## Phase 1.6: Enemy Tier Scaling & Attack Patterns

### Visual Scaling

```python
# In enemy.py — tier-based size multipliers
TIER_SCALE = {
    1: 1.0,    # Base size (48px rendered)
    2: 1.3,    # 30% larger
    3: 1.6,    # 60% larger
    4: 2.0,    # Double size — boss-like presence
}

# Hurtbox radius derived from ACTUAL sprite content, not full image
# Since sprites are 1024x1024 with backgrounds, need alpha/edge detection
def calculate_sprite_radius(sprite_surface: pygame.Surface) -> float:
    """Find radius of non-background content in sprite"""
    # Sample pixels from center outward to find content edge
    # Use color variance from corners (assumed background) to detect content
    # Return radius in tiles based on rendered size
```

### Enemy Attack Patterns (JSON-driven)

```json
{
  "enemy_attacks": {
    "wolf_grey": {
      "tier": 1,
      "attacks": [
        {
          "attack_id": "bite",
          "windup_ms": 400,
          "active_ms": 100,
          "recovery_ms": 200,
          "cooldown_ms": 1500,
          "hitbox": { "shape": "arc", "radius": 1.5, "arc_degrees": 60 },
          "damage_multiplier": 1.0,
          "weight": 1.0
        }
      ]
    },
    "golem_stone": {
      "tier": 2,
      "attacks": [
        {
          "attack_id": "slam",
          "windup_ms": 500,
          "active_ms": 150,
          "recovery_ms": 400,
          "cooldown_ms": 2000,
          "hitbox": { "shape": "circle", "radius": 2.0 },
          "damage_multiplier": 1.5,
          "screen_shake": true,
          "weight": 0.6
        },
        {
          "attack_id": "swipe",
          "windup_ms": 300,
          "active_ms": 100,
          "recovery_ms": 200,
          "cooldown_ms": 1200,
          "hitbox": { "shape": "arc", "radius": 1.8, "arc_degrees": 120 },
          "damage_multiplier": 0.8,
          "weight": 0.4
        }
      ]
    },
    "inferno_drake": {
      "tier": 3,
      "attacks": [
        {
          "attack_id": "fire_breath",
          "windup_ms": 600,
          "active_ms": 400,
          "recovery_ms": 300,
          "cooldown_ms": 3000,
          "hitbox": { "shape": "arc", "radius": 4.0, "arc_degrees": 45 },
          "damage_multiplier": 2.0,
          "status_effect": "burn",
          "weight": 0.3
        },
        {
          "attack_id": "fireball_spit",
          "windup_ms": 500,
          "active_ms": 50,
          "recovery_ms": 400,
          "cooldown_ms": 2500,
          "projectile_id": "enemy_fireball",
          "damage_multiplier": 1.5,
          "weight": 0.4
        },
        {
          "attack_id": "tail_swipe",
          "windup_ms": 250,
          "active_ms": 100,
          "recovery_ms": 300,
          "cooldown_ms": 1500,
          "hitbox": { "shape": "arc", "radius": 2.5, "arc_degrees": 180 },
          "damage_multiplier": 1.0,
          "knockback": 2.0,
          "weight": 0.3
        }
      ]
    }
  }
}
```

### T3-T4 Boss Behavior Enhancement

Higher tier enemies don't just hit harder — they have richer attack selection:

- **T1**: 1 attack type, long windups, predictable
- **T2**: 2 attack types, moderate windups, occasional combos
- **T3**: 3+ attack types, short windups, phase-based behavior (changes at 50% HP)
- **T4**: 4+ attack types, mixed ranged/melee, multi-phase, adaptive (tracks player dodge patterns)

---

## Phase 1.7: Visual Polish & Integration

### Damage Numbers (Floating Combat Text)

```python
class DamageNumber:
    """Floating damage text with physics"""
    def __init__(self, value: int, pos: Tuple[float, float],
                 is_crit: bool = False, damage_type: str = "physical"):
        self.value = value
        self.x, self.y = pos
        self.vel_y = -2.0          # Float upward
        self.vel_x = random.uniform(-0.5, 0.5)  # Slight horizontal spread
        self.alpha = 255
        self.scale = 2.0 if is_crit else 1.0  # Crits are bigger
        self.color = DAMAGE_COLORS.get(damage_type, (255, 255, 255))
        self.lifetime = 1200       # ms
        self.age = 0

    def update(self, dt_ms: float):
        self.age += dt_ms
        self.y += self.vel_y * (dt_ms / 16.67)  # Normalize to 60fps
        self.x += self.vel_x * (dt_ms / 16.67)
        self.vel_y += 0.05  # Gravity — arc effect
        self.alpha = max(0, 255 * (1 - self.age / self.lifetime))
        self.scale *= 0.998  # Subtle shrink
```

### Screen Effects

```python
class ScreenEffects:
    """Global visual effects manager"""

    def screen_shake(self, intensity: float, duration_ms: float):
        """Shake camera — big hits, explosions, boss slams"""

    def hit_flash(self, entity_id: str, color: Tuple[int,int,int], duration_ms: float):
        """Flash entity sprite white/red on hit"""

    def hit_pause(self, duration_ms: float):
        """Freeze game for N ms on big hit — 'hit stop' feel"""
        # Typically 30-60ms, makes hits feel impactful

    def slow_motion(self, time_scale: float, duration_ms: float):
        """Temporary time dilation — critical kills, near-death moments"""
```

### Rendering Changes to `renderer.py`

The renderer needs these additions (additive, not replacing existing code):

1. **Animation-aware entity drawing**: Check AnimationManager for current frame before drawing
2. **Hitbox debug rendering**: Draw hitbox/hurtbox outlines in debug mode
3. **Projectile rendering**: Draw projectile sprites with rotation + trails
4. **Damage number rendering**: Draw floating combat text above entities
5. **Screen shake offset**: Apply shake offset to all world-space drawing
6. **Attack telegraph rendering**: Draw AOE indicators during enemy WINDUP phase

### Attack Telegraph Visuals

During enemy WINDUP, render the attack zone as a semi-transparent overlay:
- **Circle attacks**: Red circle fills over windup duration (danger zone)
- **Arc attacks**: Red arc/cone fills toward entity
- **Line attacks**: Red line extends toward target
- **Projectile attacks**: Red line from enemy to aimed position (trajectory preview)

This is the **primary readability tool** — players learn to read these and react.

---

## Integration Order

```
Week 1-2:  Phase 1.1 (Animation Framework)
           - SpriteAnimation, AnimationManager, ProceduralAnimations
           - Test with player idle bob and weapon swing

Week 3-4:  Phase 1.2 + 1.3 (Attack States + Hitboxes)
           - AttackStateMachine with WINDUP/ACTIVE/RECOVERY
           - HitboxSystem with circle and arc shapes
           - Wire into existing combat_manager.py
           - Player attacks now have timing

Week 5-6:  Phase 1.4 (Projectiles)
           - ProjectileSystem with basic arrow and fireball
           - Enemy ranged attacks spawn projectiles
           - Projectile collision with hurtboxes

Week 7-8:  Phase 1.5 + 1.6 (Player Actions + Enemy Scaling)
           - Dodge roll with i-frames
           - Input buffering and basic combos
           - Enemy tier scaling (visual + hitbox)
           - JSON-driven enemy attack patterns

Week 9-10: Phase 1.7 (Polish)
           - Damage numbers with physics
           - Screen shake, hit flash, hit pause
           - Attack telegraphs for enemies
           - Debug hitbox visualization

Week 11:   Tuning & Balance
           - Playtest timing values
           - Adjust windup/recovery per weapon
           - Tune dodge i-frames and cooldowns
           - Ensure damage pipeline still balanced
```

---

## Critical Constraints

1. **Damage pipeline is SACRED**: The existing formula (base × hand × STR × skill × class × crit - defense) is NOT changed. The state machine controls WHEN it fires, not HOW.

2. **Existing combat must keep working during development**: Each phase adds on top. The old click-to-attack can coexist during transition via a `USE_ACTION_COMBAT = True` flag.

3. **60 FPS budget**: Hitbox checks must be O(n²) worst case (active_hitboxes × hurtboxes). With <50 entities on screen, this is fine. Profile if >100 entities.

4. **JSON-driven**: All timing, hitbox sizes, attack patterns, and projectile properties in JSON. Tuning without code changes.

5. **Tag system integration**: Attack definitions reference existing tags (fire, ice, knockback, etc.) for status effects. The tag system drives what happens on hit.
