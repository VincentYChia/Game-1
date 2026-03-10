# Visual Overhaul Plan: Procedural Attack Animations

## Current State

The animation system infrastructure is complete (Phases 1.1-1.6):
- `animation/` module: AnimationManager, SpriteAnimation, ProceduralAnimations, WeaponVisualStyle
- `combat_particles.py`: World-space particle system (sparks, trails, dust)
- `weapon_visuals.py`: Tag-driven style resolution per weapon type/element/tier
- Renderer has ~500 lines of attack visual code drawing geometric shapes (arcs, polygons, lines)

**Problem**: Current visuals use raw `pygame.draw.arc/polygon/line` — they look like programmer art geometry, not polished fantasy combat effects.

## Design Goals (from user)
1. **Procedural generation** — no hand-drawn art needed
2. **Smooth, sleek, polished fantasy** aesthetic for top-down view
3. **Subtle but consistent distinction** between weapon types (axe thicker than sword, sword different from punch)
4. **Enemy attacks mirror player system** with similar distinctions
5. **Priority order**: Player attacks > Enemy attacks > Projectile polish > Movement
6. Sprite sheets welcome if provided, but system must look great without them

## Implementation Plan

### Step 1: Procedural Swing Effect Generator (`animation/swing_renderer.py`)

Replace geometric arc drawing with pre-rendered, multi-layered attack effect surfaces.

**Core idea**: Instead of drawing raw `pygame.draw.arc()` at render time, pre-generate smooth attack animation frames at startup using layered compositing:

- **Layer 1 — Motion Trail**: Gradient-filled crescent shape (not wireframe arc) that sweeps through the weapon's arc. Uses anti-aliased polygon fills with alpha gradients for smooth falloff.
- **Layer 2 — Blade Edge**: Bright leading edge line with Gaussian-approximated glow (3-pass draw at decreasing alpha and increasing width). White-hot center, element-colored outer glow.
- **Layer 3 — Afterimage Echoes**: 2-3 fading copies of the blade edge at prior positions, creating motion blur feel.
- **Layer 4 — Spark Particles**: Small bright dots scattered along the sweep path, denser near the blade tip.

**Weapon Distinction** (reads from existing `WeaponVisualStyle`):
| Weapon Type | Arc Width | Trail Thickness | Trail Shape | Blade Edge | Feel |
|-------------|-----------|-----------------|-------------|------------|------|
| Sword 1H | 65° | Medium | Thin crescent | Thin, bright | Quick slash |
| Sword 2H | 100° | Wide | Wide crescent | Thick, heavy | Power sweep |
| Dagger | 30° | Narrow | Minimal trail | Sharp, fast | Flick |
| Axe | 80° | Very wide | Chunky wedge | Thick, rough | Heavy chop |
| Hammer | 90° | Extra wide | Blunt arc | Blunt, impact-heavy | Crushing |
| Spear | 12° | Thin line | Elongated thrust | Point-focused | Stab |
| Unarmed | 55° | Diffuse | Circular burst | No blade, wider impact | Punch |

**Implementation approach**:
- New class `SwingEffectRenderer` in `animation/swing_renderer.py`
- Method `generate_swing_frames(weapon_style, num_frames=8) -> List[pygame.Surface]`
- Each frame is a pre-rendered SRCALPHA surface with all layers composited
- Renderer calls this at attack start, caches result, then blits frame-by-frame
- Cache key = `(weapon_type, element, tier)` — typically <30 unique combinations

### Step 2: Upgrade Player Attack Rendering in `renderer.py`

Replace the inline geometric drawing in the hitbox rendering section (~lines 2060-2190) with calls to `SwingEffectRenderer`:

- On hitbox creation: generate or fetch cached swing frames for the weapon style
- Each frame: blit the pre-rendered surface rotated to the attack facing angle
- Progress through frames based on hitbox lifetime ratio
- Keep the existing `WeaponVisualStyle` resolution — it already provides all the parameters

**Key changes**:
- Replace the "arc" shape section (~lines 2080-2188) with frame-based rendering
- Replace the "line" (thrust) section (~lines 2190-2216) with thrust-specific frames
- Replace the "circle" section (~lines 2060-2078) with radial burst frames
- Keep "rect" section mostly as-is (beam attacks)

### Step 3: Mirror System for Enemy Attacks

The enemy attack rendering (~lines 1368-1480) already reads `attack_anim_tags`, `attack_anim_angle`, etc. Upgrade it to use the same `SwingEffectRenderer`:

- Resolve enemy weapon type from attack data (already available via `_attack_weapon_type`)
- Generate swing frames with enemy-specific color tinting (red-shifted for hostile)
- Same frame-based blitting, just with enemy position/facing
- Enemy attacks get slightly different color treatment: more saturated, warning-red undertones

### Step 4: Projectile Visual Polish

Current projectile rendering (~lines 2244+) draws basic shapes. Upgrade:
- Add glow halos around projectile bodies (multi-pass circle at decreasing alpha)
- Add proper motion-blur trail (elongated in travel direction)
- Element-colored core + white highlight center
- Trail particles already exist in `combat_particles.py` — increase density and quality

### Step 5: Attack Effect System Polish (`_render_attack_effects`)

The `AttackEffectType.SLASH_ARC` and `THRUST` renderers (~lines 7535-7730) need the same treatment:
- Replace raw polygon/arc drawing with the pre-rendered frame system
- These fire as secondary "echo" effects after hitbox damage — should look like the afterglow of the swing

## Files Modified
- `animation/swing_renderer.py` — **NEW**: Pre-rendered procedural swing frame generator
- `rendering/renderer.py` — Replace inline geometric drawing with frame-based rendering
- `animation/weapon_visuals.py` — Minor additions for thrust/punch profile resolution
- `animation/combat_particles.py` — Enhanced particle quality (glow, size variation)

## Files NOT Modified
- No content JSON files
- No game logic files (combat_manager.py, etc.)
- No formula changes
- No asset/icon PNGs

## Technical Notes
- All frames pre-rendered at generation time — zero per-frame transform cost
- Cache invalidation: clear on weapon change (rare)
- Memory: ~8 frames × ~128x128 px × 4 bytes × 30 weapon combos ≈ 15MB (negligible)
- Fallback: if `SwingEffectRenderer` unavailable, existing geometric drawing remains
