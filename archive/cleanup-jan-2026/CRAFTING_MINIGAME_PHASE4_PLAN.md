# Crafting Minigame Phase 4: UI Polish & Visual Overhaul

**Created**: January 5, 2026
**Purpose**: Comprehensive implementation plan for next developer
**Goal**: Transform basic functional minigames into visually stunning, professionally polished experiences

---

## PRIMARY EMPHASIS: UI & Visual Polish

This phase focuses on **comprehensive UI upgrades** across all disciplines. The goal is to create
polished, thematic, visually satisfying minigame experiences that feel like complete, fun mini-games
rather than placeholder mechanics.

**Key Philosophy**: Every discipline should have a distinct, immersive visual identity with
animations, particle effects, and thematic elements that make crafting feel rewarding.

---

## Table of Contents

1. [Current System Overview](#1-current-system-overview)
2. [UI Visual Polish Specifications](#2-ui-visual-polish-specifications) ← PRIMARY FOCUS
3. [Animation & Particle Systems](#3-animation--particle-systems) ← PRIMARY FOCUS
4. [Visual Feedback Guidelines](#4-visual-feedback-guidelines) ← PRIMARY FOCUS
5. [Engineering Puzzle Replacement](#5-engineering-puzzle-replacement) ← Secondary
6. [Difficulty/Reward System Reference](#6-difficultyreward-system-reference)
7. [Implementation Checklist](#7-implementation-checklist)
8. [File Reference Guide](#8-file-reference-guide)

---

## 1. Current System Overview

### Architecture Summary

The crafting system uses a **centralized difficulty/reward calculator** with **discipline-specific minigames**:

```
Recipe Selection → Difficulty Calculator → Minigame Instance → Reward Calculator → Crafting Result
```

### Key Files

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| **Difficulty Calculator** | `core/difficulty_calculator.py` | ~600 | Calculates difficulty points, interpolates minigame parameters |
| **Reward Calculator** | `core/reward_calculator.py` | ~600 | Converts performance → quality tiers, stat bonuses |
| **Smithing Minigame** | `Crafting-subdisciplines/smithing.py` | ~500 | Hammer timing + temperature management |
| **Alchemy Minigame** | `Crafting-subdisciplines/alchemy.py` | ~700 | Reaction chain timing |
| **Refining Minigame** | `Crafting-subdisciplines/refining.py` | ~500 | Cylinder lock timing |
| **Engineering Minigame** | `Crafting-subdisciplines/engineering.py` | ~950 | Puzzle solving (NEEDS OVERHAUL) |
| **Enchanting Minigame** | `Crafting-subdisciplines/enchanting.py` | ~1300 | Spinning wheel gambling |
| **Minigame Rendering** | `core/game_engine.py` | 3211-3950 | All minigame render functions |

### Difficulty System (Linear Tier Points)

```python
# Material points: tier × quantity (LINEAR)
TIER_POINTS = {1: 1, 2: 2, 3: 3, 4: 4}

# Difficulty thresholds (updated Phase 3)
DIFFICULTY_THRESHOLDS = {
    'common': (0, 4),      # 19.5% of recipes
    'uncommon': (5, 10),   # 39% of recipes
    'rare': (11, 20),      # 28.7% of recipes
    'epic': (21, 40),      # 9.1% of recipes
    'legendary': (41, 150) # 3.7% of recipes
}
```

### Reward System

- **Performance Score**: 0.0 to 1.0 based on minigame execution
- **Quality Tiers**: Normal (0-25%), Fine (25-50%), Superior (50-75%), Masterwork (75-90%), Legendary (90-100%)
- **First-Try Bonus**: +10% performance boost on first attempt
- **Difficulty Scaling**: Higher difficulty unlocks higher max bonus (1.0x to 2.5x)

---

## 2. UI Visual Polish Specifications (PRIMARY FOCUS)

This section provides **comprehensive specifications** for transforming each minigame's visual presentation
from basic functional UI to polished, immersive experiences.

### UI Polish Status Overview

| Discipline | Current State | Target State | Priority |
|------------|---------------|--------------|----------|
| **Smithing** | ✅ Forge aesthetic exists | Minor refinements | LOW |
| **Alchemy** | ❌ Plain dark + green tint | Full cauldron scene with bubbles, steam, fire | **HIGH** |
| **Engineering** | ❌ Plain dark + blue | Blueprint paper, rotating gears, schematic feel | **HIGH** |
| **Refining** | ❌ Plain with basic cylinders | Industrial metal, furnace glow, sparks | **MEDIUM** |
| **Enchanting** | ⚠️ Wheel exists but basic | Magical atmosphere, runes, particle effects | **MEDIUM** |

### 2.1 Alchemy UI - Complete Cauldron Scene (HIGH PRIORITY)

**Theme**: Mystical witch's workshop with bubbling cauldron, magical fire, swirling steam

**Color Palette**:
```
Primary Background: Deep purple-green gradient
  - Top: #1a0a2e (deep purple)
  - Bottom: #0a2e1a (forest green)

Accent Colors:
  - Bubbles: #00ff88 (bright green), #88ffaa (pale green)
  - Fire: #ff6600 (orange) → #ffff00 (yellow) → #ff3300 (red-orange)
  - Steam: #aaccaa (pale green-grey), alpha 0.3-0.7
  - Potion liquid: Varies by stage (see below)
  - Text: #aaffcc (pale green)
  - UI elements: #8800ff (purple accent)
```

**Potion Color Stages** (based on reaction progress):
```python
POTION_COLORS = {
    'start': (100, 150, 200),      # Blue-grey (inactive)
    'heating': (150, 200, 100),    # Yellow-green (warming)
    'reacting': (50, 255, 100),    # Bright green (active)
    'critical': (255, 150, 50),    # Orange (near completion)
    'complete': (200, 100, 255),   # Purple (finished)
    'failed': (100, 50, 50),       # Dark red-brown (ruined)
}
```

**Visual Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ☆ ALCHEMY ☆                    ┌────────────────────────────┐ │
│   ~~~~~~~~~~~                    │ Reaction Chain: 3/5        │ │
│                                  │ ████████████░░░░░░░  65%   │ │
│        ∿∿∿∿∿∿∿                   └────────────────────────────┘ │
│       ∿ steam ∿                                                 │
│        ∿∿∿∿∿                     ┌────────────────────────────┐ │
│      ╭─────────╮                 │ TIMING WINDOW              │ │
│     ╱ ○  ○  ○  ╲                │ ▼▼▼▼▼▼▼▼▼▼                 │ │
│    │ ○ ▓▓▓▓▓ ○ │                │ ────●─────────             │ │
│    │ ○ ▓███▓ ○ │  ← Liquid      │ ▲▲▲▲▲▲▲▲▲▲                 │ │
│    │ ○ ▓▓▓▓▓ ○ │    color       │ [SPACEBAR] when in zone!   │ │
│    │   (⌒⌒)   │    varies      └────────────────────────────┘ │
│    │  (~~~~)  │                                                 │
│    ╰──────────╯                                                 │
│       ════════                                                  │
│     ▓▓▓▓▓▓▓▓▓▓   ← Fire glow (animated)                        │
│    ░░░░░░░░░░░░                                                 │
│                                                                  │
│   Temperature: ████████░░ 80°C   │   Stability: ●●●●○          │
│                                                                  │
│   [C] Chain Reaction    [S] Stabilize    [Q] Quit              │
└─────────────────────────────────────────────────────────────────┘
```

**Bubble Particle System**:
```python
class AlchemyBubble:
    """Single bubble particle for cauldron effect."""
    def __init__(self, cauldron_rect):
        self.x = cauldron_rect.centerx + random.randint(-30, 30)
        self.y = cauldron_rect.top + random.randint(20, 60)  # Start in liquid
        self.size = random.randint(3, 12)
        self.speed = random.uniform(0.5, 2.0)
        self.wobble = random.uniform(-0.3, 0.3)
        self.alpha = random.randint(150, 255)
        self.color = (0, 255, random.randint(100, 200))  # Green variations
        self.max_height = cauldron_rect.top - 20  # Pop above cauldron rim

    def update(self):
        self.y -= self.speed
        self.x += math.sin(pygame.time.get_ticks() * 0.01) * self.wobble
        self.alpha = max(0, self.alpha - 2)
        return self.y > self.max_height and self.alpha > 0

    def draw(self, surface):
        if self.alpha > 0:
            bubble_surf = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(bubble_surf, (*self.color, self.alpha),
                             (self.size, self.size), self.size)
            # Highlight for 3D effect
            pygame.draw.circle(bubble_surf, (255, 255, 255, self.alpha // 2),
                             (self.size - 2, self.size - 2), self.size // 3)
            surface.blit(bubble_surf, (self.x - self.size, self.y - self.size))
```

**Fire Animation System**:
```python
class CauldronFire:
    """Animated fire beneath cauldron."""
    def __init__(self, base_rect):
        self.base_rect = base_rect
        self.flames = []
        self._generate_flames()

    def _generate_flames(self):
        for i in range(8):  # 8 flame columns
            x = self.base_rect.left + (i * self.base_rect.width // 8) + 5
            self.flames.append({
                'x': x,
                'base_y': self.base_rect.top,
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(3, 6),
                'height': random.randint(20, 40)
            })

    def update(self):
        ticks = pygame.time.get_ticks()
        for flame in self.flames:
            # Flickering height
            flame['current_height'] = flame['height'] + \
                math.sin(ticks * 0.01 * flame['speed'] + flame['phase']) * 10

    def draw(self, surface):
        for flame in self.flames:
            height = int(flame['current_height'])
            # Draw flame gradient (yellow center, orange edges, red tips)
            for h in range(height, 0, -3):
                ratio = h / height
                r = int(255 * (1 - ratio * 0.3))
                g = int(255 * ratio * ratio)
                b = 0
                alpha = int(200 * ratio)
                flame_surf = pygame.Surface((12, 6), pygame.SRCALPHA)
                pygame.draw.ellipse(flame_surf, (r, g, b, alpha), (0, 0, 12, 6))
                surface.blit(flame_surf, (flame['x'] - 6, flame['base_y'] - h))
```

**Steam Wisp System**:
```python
class SteamWisp:
    """Rising steam particle above cauldron."""
    def __init__(self, source_x, source_y):
        self.x = source_x + random.randint(-20, 20)
        self.y = source_y
        self.alpha = random.randint(80, 150)
        self.size = random.randint(15, 30)
        self.drift = random.uniform(-0.5, 0.5)
        self.rise_speed = random.uniform(0.3, 0.8)

    def update(self):
        self.y -= self.rise_speed
        self.x += self.drift
        self.size += 0.1
        self.alpha -= 1
        return self.alpha > 0

    def draw(self, surface):
        steam_surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        color = (170, 200, 170, int(self.alpha))
        pygame.draw.circle(steam_surf, color, (int(self.size), int(self.size)), int(self.size))
        surface.blit(steam_surf, (int(self.x - self.size), int(self.y - self.size)))
```

**Sweet Spot Glow Effect**:
When player timing is in the "sweet spot", add pulsing glow around timing indicator:
```python
def draw_sweet_spot_glow(surface, center_pos, is_active):
    if is_active:
        ticks = pygame.time.get_ticks()
        pulse = (math.sin(ticks * 0.01) + 1) / 2  # 0.0 to 1.0
        glow_radius = 20 + int(pulse * 10)
        glow_alpha = int(100 + pulse * 100)
        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 255, 100, glow_alpha),
                          (glow_radius, glow_radius), glow_radius)
        surface.blit(glow_surf, (center_pos[0] - glow_radius, center_pos[1] - glow_radius))
```

---

### 2.2 Engineering UI - Blueprint Schematic Theme (HIGH PRIORITY)

**Color Palette**:
- Background: Blueprint blue (#1a3a5c) with grid lines (#2a5a8c)
- Accent: Copper/brass (#cd7f32), steel (#708090)
- Text: White chalk (#f0f0f0)

**Visual Elements**:
```
┌─────────────────────────────────────────────────────┐
│  ┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐                   │
│  ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤  ENGINEERING      │
│  ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤  Puzzle 1/2       │
│  ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤                   │
│  └──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘                   │
│                                                      │
│   ⚙️ ══════════════════════════ ⚙️                  │
│                                                      │
│  ┌─────────────────────────────────────────┐        │
│  │  [PUZZLE AREA - Wire/Gear/Pipe]         │        │
│  │                                          │        │
│  │                                          │        │
│  └─────────────────────────────────────────┘        │
│                                                      │
│  Hints: ●●●○  │  Solved: 0/2                        │
│                                                      │
│  [Click to interact with puzzle]                    │
└─────────────────────────────────────────────────────┘
```

**Animations**:
1. Rotating gear decorations in corners
2. Grid line shimmer effect
3. "Schematic" drawing effect when puzzle loads
4. Success: gears spin, sparks fly

**Blueprint Grid Background Implementation**:
```python
def draw_blueprint_background(surface, rect):
    """Draw blueprint-style background with grid."""
    # Base color
    surface.fill((26, 58, 92))  # #1a3a5c

    # Major grid lines (every 50 pixels)
    grid_color = (42, 90, 140, 100)  # #2a5a8c with alpha
    for x in range(rect.left, rect.right, 50):
        pygame.draw.line(surface, grid_color, (x, rect.top), (x, rect.bottom))
    for y in range(rect.top, rect.bottom, 50):
        pygame.draw.line(surface, grid_color, (rect.left, y), (rect.right, y))

    # Minor grid lines (every 10 pixels, lighter)
    minor_color = (42, 90, 140, 40)
    for x in range(rect.left, rect.right, 10):
        if x % 50 != 0:
            pygame.draw.line(surface, minor_color, (x, rect.top), (x, rect.bottom))
    for y in range(rect.top, rect.bottom, 10):
        if y % 50 != 0:
            pygame.draw.line(surface, minor_color, (rect.left, y), (rect.right, y))
```

**Rotating Gear Decoration**:
```python
class DecorativeGear:
    """Rotating gear for corner decoration."""
    def __init__(self, center, radius, teeth=8):
        self.center = center
        self.radius = radius
        self.teeth = teeth
        self.angle = 0
        self.rotation_speed = 0.5  # degrees per frame

    def update(self):
        self.angle = (self.angle + self.rotation_speed) % 360

    def draw(self, surface):
        # Outer circle
        copper = (205, 127, 50)  # #cd7f32
        pygame.draw.circle(surface, copper, self.center, self.radius, 3)

        # Inner circle
        pygame.draw.circle(surface, copper, self.center, self.radius // 2, 2)

        # Teeth
        for i in range(self.teeth):
            tooth_angle = math.radians(self.angle + i * (360 / self.teeth))
            inner_x = self.center[0] + math.cos(tooth_angle) * self.radius
            inner_y = self.center[1] + math.sin(tooth_angle) * self.radius
            outer_x = self.center[0] + math.cos(tooth_angle) * (self.radius + 8)
            outer_y = self.center[1] + math.sin(tooth_angle) * (self.radius + 8)
            pygame.draw.line(surface, copper, (inner_x, inner_y), (outer_x, outer_y), 3)

        # Center hole
        pygame.draw.circle(surface, (40, 40, 50), self.center, 5)
```

**Schematic Drawing Animation**:
When a new puzzle loads, draw elements progressively as if being sketched:
```python
class SchematicDrawEffect:
    """Progressive drawing effect for puzzle elements."""
    def __init__(self, elements, draw_time_ms=500):
        self.elements = elements  # List of drawable elements
        self.draw_time = draw_time_ms
        self.start_time = None
        self.complete = False

    def start(self):
        self.start_time = pygame.time.get_ticks()
        self.complete = False

    def draw(self, surface):
        if self.start_time is None:
            return

        elapsed = pygame.time.get_ticks() - self.start_time
        progress = min(1.0, elapsed / self.draw_time)

        # Draw only portion of elements based on progress
        elements_to_draw = int(len(self.elements) * progress)
        for element in self.elements[:elements_to_draw]:
            element.draw(surface)

        if progress >= 1.0:
            self.complete = True
```

---

### 2.3 Refining UI - Industrial Foundry Theme (MEDIUM PRIORITY)

**Theme**: Heavy industrial foundry with molten metal, mechanical lock mechanisms, heat and sparks

**Color Palette**:
```
Primary Background: Dark brushed metal
  - Base: #2a2a2a (dark grey)
  - Highlights: #3a3a3a (lighter grey for depth)

Accent Colors:
  - Rust accents: #8b4513 (saddle brown), #a0522d (sienna)
  - Molten metal: #ff6600 (orange) → #ffcc00 (gold) → #ffffff (white-hot)
  - Steel blue: #4682b4 (for cooled metal)
  - Sparks: #ffff00 (yellow), #ff8800 (orange)
  - Text: #e0e0e0 (industrial white)
```

**Visual Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  ═══════════════════════════════════════════════════════════   │
│                                                                  │
│   ⚙ REFINING ⚙                                                  │
│   ════════════                                                   │
│                                                                  │
│     ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐                  │
│     │ ░░░░ │   │ ████ │   │ ▒▒▒▒ │   │ ░░░░ │  ← Lock cylinders│
│     │ ░░░░ │   │ ████ │   │ ▒▒▒▒ │   │ ░░░░ │    (metallic)    │
│     │ ░░░░ │   │ ████ │   │ ▒▒▒▒ │   │ ░░░░ │                  │
│     └──────┘   └──────┘   └──────┘   └──────┘                  │
│        ▲          ▲          ▲          ▲                       │
│        │          │          │          │                       │
│     [Click or use arrow keys to rotate]                         │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  │
│   │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  FURNACE GLOW  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  │
│   │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│   Aligned: 2/4   │   Quality: ████████░░ 80%                   │
│                                                                  │
│   [SPACE] Lock cylinder    [Q] Quit                             │
└─────────────────────────────────────────────────────────────────┘
```

**Metallic Cylinder Rendering**:
```python
def draw_metallic_cylinder(surface, rect, rotation, is_aligned):
    """Draw a lock cylinder with metallic appearance."""
    # Base cylinder (dark metal)
    pygame.draw.rect(surface, (60, 60, 70), rect, border_radius=5)

    # Metallic gradient effect (lighter at top)
    gradient_rect = pygame.Rect(rect.left + 2, rect.top + 2, rect.width - 4, rect.height // 3)
    pygame.draw.rect(surface, (90, 90, 100), gradient_rect, border_radius=3)

    # Rotation marker
    marker_color = (100, 255, 100) if is_aligned else (200, 200, 200)
    marker_rect = pygame.Rect(rect.centerx - 3, rect.top + 5, 6, 15)
    # Rotate marker based on cylinder rotation
    # ... rotation logic ...

    # Highlight when aligned
    if is_aligned:
        glow_surf = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (100, 255, 100, 80), glow_surf.get_rect(), border_radius=8)
        surface.blit(glow_surf, (rect.left - 5, rect.top - 5))

    # Border
    border_color = (100, 255, 100) if is_aligned else (100, 100, 110)
    pygame.draw.rect(surface, border_color, rect, 2, border_radius=5)
```

**Furnace Glow Effect**:
```python
class FurnaceGlow:
    """Animated furnace glow at bottom of screen."""
    def __init__(self, rect):
        self.rect = rect
        self.intensity = 0.5

    def update(self):
        ticks = pygame.time.get_ticks()
        # Pulsing glow
        self.intensity = 0.5 + math.sin(ticks * 0.003) * 0.2

    def draw(self, surface):
        # Multiple layers for depth
        for i in range(5):
            alpha = int((self.intensity * 150) * (1 - i * 0.15))
            height = self.rect.height + i * 20
            color = (255, int(100 + i * 20), 0, alpha)
            glow_surf = pygame.Surface((self.rect.width, height), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, color, glow_surf.get_rect())
            surface.blit(glow_surf, (self.rect.left, self.rect.bottom - height))
```

**Spark Particle Effect**:
```python
class RefiningSparkParticle:
    """Spark particle for alignment success."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-5, -2)
        self.gravity = 0.15
        self.life = 1.0
        self.color = random.choice([(255, 255, 0), (255, 200, 0), (255, 150, 0)])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.life -= 0.03
        return self.life > 0

    def draw(self, surface):
        alpha = int(self.life * 255)
        size = max(1, int(self.life * 4))
        spark_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(spark_surf, (*self.color, alpha), (size, size), size)
        surface.blit(spark_surf, (int(self.x - size), int(self.y - size)))
```

---

### 2.4 Enchanting UI - Mystical Arcane Theme (MEDIUM PRIORITY)

**Theme**: Mystical ritual space with floating runes, magical particles, arcane wheel of fortune

**Color Palette**:
```
Primary Background: Deep cosmic purple-black gradient
  - Top: #0a0015 (near black with purple tint)
  - Bottom: #150030 (deep purple)

Accent Colors:
  - Magic blue: #00aaff (primary magic glow)
  - Arcane gold: #ffd700 (success, currency)
  - Mystic purple: #9900ff (secondary glow)
  - Win green: #00ff88
  - Loss red: #ff4444
  - Text: #ffffff (ethereal white with glow)
```

**Visual Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│   ·  *  ·     ·  ✦  ·     ·  *  ·    ← Floating particles      │
│      ·    ✦       ·    *      ·                                 │
│                                                                  │
│              ✨ ENCHANTING ✨                                    │
│              ~~~~~~~~~~~~~~~~                                    │
│                                                                  │
│              ◐ ◑ ◒ ◓ ◔ ◕ ◐ ◑      ← Rotating rune circle       │
│            ╭───────────────────╮                                │
│           ╱  ┌───────────────┐  ╲                               │
│          │   │    GREEN      │   │                              │
│          │   │     ████      │   │   ← Wheel slices             │
│          │   │   RED  GREY   │   │      (20 segments)           │
│          │   │    ████████   │   │                              │
│          │   └───────────────┘   │                              │
│           ╲                     ╱                               │
│            ╰───────────────────╯                                │
│                     ▼                                           │
│                 [POINTER]                                       │
│                                                                  │
│   ╔═══════════════════════════════════════════════════════════╗│
│   ║  💰 Currency: 125         Spin: 2/3                       ║│
│   ║                                                            ║│
│   ║  Bet: [░░░░░░░●░░░░░░░░░] 50                              ║│
│   ║                                                            ║│
│   ║              [✦ SPIN WHEEL ✦]                             ║│
│   ╚═══════════════════════════════════════════════════════════╝│
│                                                                  │
│   ·    *    ·    ✦    ·    *    ·                               │
└─────────────────────────────────────────────────────────────────┘
```

**Magic Particle System**:
```python
class MagicParticle:
    """Floating magical particle."""
    def __init__(self, bounds):
        self.bounds = bounds
        self.x = random.randint(bounds.left, bounds.right)
        self.y = random.randint(bounds.top, bounds.bottom)
        self.size = random.uniform(1, 3)
        self.alpha = random.randint(50, 200)
        self.drift_x = random.uniform(-0.2, 0.2)
        self.drift_y = random.uniform(-0.3, 0.1)
        self.pulse_phase = random.uniform(0, math.pi * 2)
        self.color = random.choice([
            (0, 170, 255),   # Blue
            (255, 215, 0),   # Gold
            (153, 0, 255),   # Purple
        ])

    def update(self):
        self.x += self.drift_x
        self.y += self.drift_y
        self.pulse_phase += 0.05

        # Wrap around bounds
        if self.x < self.bounds.left:
            self.x = self.bounds.right
        elif self.x > self.bounds.right:
            self.x = self.bounds.left
        if self.y < self.bounds.top:
            self.y = self.bounds.bottom
        elif self.y > self.bounds.bottom:
            self.y = self.bounds.top

    def draw(self, surface):
        pulse = (math.sin(self.pulse_phase) + 1) / 2
        current_alpha = int(self.alpha * (0.5 + pulse * 0.5))
        current_size = self.size * (0.8 + pulse * 0.4)

        particle_surf = pygame.Surface((int(current_size * 4), int(current_size * 4)), pygame.SRCALPHA)
        pygame.draw.circle(particle_surf, (*self.color, current_alpha),
                          (int(current_size * 2), int(current_size * 2)), int(current_size))
        surface.blit(particle_surf, (int(self.x - current_size * 2), int(self.y - current_size * 2)))
```

**Rotating Rune Circle**:
```python
class RuneCircle:
    """Rotating circle of runes around the wheel."""
    RUNES = ['◐', '◑', '◒', '◓', '◔', '◕', '☽', '☾', '✦', '✧']

    def __init__(self, center, radius):
        self.center = center
        self.radius = radius
        self.angle = 0
        self.rotation_speed = 0.2
        self.rune_count = 12
        self.font = pygame.font.Font(None, 24)

    def update(self):
        self.angle = (self.angle + self.rotation_speed) % 360

    def draw(self, surface):
        for i in range(self.rune_count):
            rune_angle = math.radians(self.angle + i * (360 / self.rune_count))
            x = self.center[0] + math.cos(rune_angle) * self.radius
            y = self.center[1] + math.sin(rune_angle) * self.radius

            rune = self.RUNES[i % len(self.RUNES)]
            # Glow effect
            glow_color = (0, 170, 255, 100)
            rune_surf = self.font.render(rune, True, (0, 170, 255))
            surface.blit(rune_surf, (x - rune_surf.get_width() // 2, y - rune_surf.get_height() // 2))
```

**Wheel Spin Animation with Easing**:
```python
class WheelSpinAnimation:
    """Smooth wheel spin with deceleration easing."""
    def __init__(self, start_angle, target_slice, spin_duration_ms=3000):
        self.start_angle = start_angle
        self.target_angle = target_slice * (360 / 20) + random.uniform(0, 360 / 20)  # 20 slices
        # Add extra rotations for dramatic effect
        self.target_angle += 360 * random.randint(3, 5)
        self.duration = spin_duration_ms
        self.start_time = None
        self.current_angle = start_angle
        self.complete = False

    def start(self):
        self.start_time = pygame.time.get_ticks()

    def update(self):
        if self.start_time is None:
            return

        elapsed = pygame.time.get_ticks() - self.start_time
        progress = min(1.0, elapsed / self.duration)

        # Ease-out cubic for smooth deceleration
        eased_progress = 1 - (1 - progress) ** 3

        self.current_angle = self.start_angle + (self.target_angle - self.start_angle) * eased_progress

        if progress >= 1.0:
            self.complete = True

    def get_angle(self):
        return self.current_angle % 360
```

**Currency Change Animation**:
```python
class CurrencyAnimation:
    """Animated currency counter."""
    def __init__(self):
        self.displayed_value = 100
        self.target_value = 100
        self.animation_speed = 2

    def set_target(self, value):
        self.target_value = value

    def update(self):
        if self.displayed_value < self.target_value:
            self.displayed_value = min(self.displayed_value + self.animation_speed, self.target_value)
        elif self.displayed_value > self.target_value:
            self.displayed_value = max(self.displayed_value - self.animation_speed, self.target_value)

    def draw(self, surface, pos, font):
        # Color based on change direction
        if self.displayed_value > 100:
            color = (0, 255, 136)  # Green for profit
        elif self.displayed_value < 100:
            color = (255, 68, 68)  # Red for loss
        else:
            color = (255, 255, 255)  # White for neutral

        text = font.render(f"💰 {int(self.displayed_value)}", True, color)
        surface.blit(text, pos)
```

---

## 3. Animation & Particle Systems (PRIMARY FOCUS)

This section covers the **reusable animation infrastructure** that should be implemented
to support all minigame visual effects.

### 3.1 Base Particle System

```python
class ParticleSystem:
    """
    Reusable particle system for all minigames.

    Usage:
        particles = ParticleSystem(max_particles=100)
        particles.add(SparkParticle(x, y))
        # In update loop:
        particles.update()
        particles.draw(surface)
    """
    def __init__(self, max_particles=100):
        self.particles = []
        self.max_particles = max_particles

    def add(self, particle):
        if len(self.particles) < self.max_particles:
            self.particles.append(particle)

    def update(self):
        self.particles = [p for p in self.particles if p.update()]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)

    def clear(self):
        self.particles.clear()
```

### 3.2 Animation Timing Utilities

```python
class AnimationTimer:
    """
    Utility for frame-independent animation timing.

    Usage:
        timer = AnimationTimer()
        # In update loop:
        delta = timer.tick()
        position += velocity * delta
    """
    def __init__(self):
        self.last_time = pygame.time.get_ticks()

    def tick(self):
        """Returns delta time in seconds since last tick."""
        current = pygame.time.get_ticks()
        delta = (current - self.last_time) / 1000.0
        self.last_time = current
        return delta


def ease_out_cubic(t):
    """Ease-out cubic: decelerating to zero velocity."""
    return 1 - (1 - t) ** 3


def ease_in_out_sine(t):
    """Ease-in-out sine: smooth acceleration/deceleration."""
    return -(math.cos(math.pi * t) - 1) / 2


def lerp_color(color1, color2, t):
    """Linear interpolation between two RGB colors."""
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t),
    )
```

### 3.3 Glow Effect Utility

```python
def draw_glow(surface, center, radius, color, intensity=1.0):
    """
    Draw a soft glow effect at the specified position.

    Args:
        surface: Pygame surface to draw on
        center: (x, y) center position
        radius: Glow radius in pixels
        color: RGB tuple
        intensity: 0.0 to 1.0 brightness multiplier
    """
    glow_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)

    for r in range(radius, 0, -2):
        alpha = int((r / radius) * 100 * intensity)
        pygame.draw.circle(glow_surf, (*color, alpha), (radius, radius), r)

    surface.blit(glow_surf, (center[0] - radius, center[1] - radius),
                 special_flags=pygame.BLEND_RGBA_ADD)
```

---

## 4. Visual Feedback Guidelines (PRIMARY FOCUS)

### 4.1 Action Feedback Principles

Every player action should have **immediate, clear visual feedback**:

| Action Type | Feedback | Duration |
|-------------|----------|----------|
| Button press | Color flash + scale pulse | 100-200ms |
| Successful action | Green glow + particle burst | 300-500ms |
| Failed action | Red flash + screen shake | 200-300ms |
| Critical success | Gold glow + particle explosion | 500-800ms |
| Progress milestone | Progress bar pulse + chime indication | 300ms |

### 4.2 Screen Shake Effect

```python
class ScreenShake:
    """Screen shake effect for impact feedback."""
    def __init__(self):
        self.intensity = 0
        self.duration = 0
        self.start_time = 0

    def trigger(self, intensity=5, duration_ms=200):
        self.intensity = intensity
        self.duration = duration_ms
        self.start_time = pygame.time.get_ticks()

    def get_offset(self):
        if self.duration <= 0:
            return (0, 0)

        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed >= self.duration:
            self.duration = 0
            return (0, 0)

        # Decay over time
        remaining = 1 - (elapsed / self.duration)
        current_intensity = self.intensity * remaining

        return (
            random.randint(-int(current_intensity), int(current_intensity)),
            random.randint(-int(current_intensity), int(current_intensity))
        )
```

### 4.3 Button Press Animation

```python
class AnimatedButton:
    """Button with press animation."""
    def __init__(self, rect, text, base_color, hover_color, press_color):
        self.rect = rect
        self.text = text
        self.base_color = base_color
        self.hover_color = hover_color
        self.press_color = press_color
        self.current_color = base_color
        self.scale = 1.0
        self.pressed = False
        self.hovered = False

    def update(self, mouse_pos, mouse_pressed):
        self.hovered = self.rect.collidepoint(mouse_pos)

        if self.pressed and not mouse_pressed:
            self.pressed = False
            self.scale = 1.0
        elif self.hovered and mouse_pressed and not self.pressed:
            self.pressed = True
            self.scale = 0.95

        # Smooth color transition
        target = self.press_color if self.pressed else (
            self.hover_color if self.hovered else self.base_color
        )
        self.current_color = lerp_color(self.current_color, target, 0.2)

    def draw(self, surface, font):
        # Scale effect
        scaled_rect = self.rect.copy()
        if self.scale != 1.0:
            dw = int(self.rect.width * (1 - self.scale) / 2)
            dh = int(self.rect.height * (1 - self.scale) / 2)
            scaled_rect.inflate_ip(-dw * 2, -dh * 2)

        pygame.draw.rect(surface, self.current_color, scaled_rect, border_radius=5)
        pygame.draw.rect(surface, (255, 255, 255), scaled_rect, 2, border_radius=5)

        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=scaled_rect.center)
        surface.blit(text_surf, text_rect)
```

### 4.4 Progress Bar with Animation

```python
class AnimatedProgressBar:
    """Progress bar with smooth fill animation and milestone pulses."""
    def __init__(self, rect, color, bg_color=(50, 50, 50)):
        self.rect = rect
        self.color = color
        self.bg_color = bg_color
        self.displayed_progress = 0.0
        self.target_progress = 0.0
        self.milestone_pulse = 0.0

    def set_progress(self, value):
        old_milestone = int(self.target_progress * 4)  # 25% milestones
        new_milestone = int(value * 4)
        if new_milestone > old_milestone:
            self.milestone_pulse = 1.0
        self.target_progress = value

    def update(self):
        # Smooth progress animation
        self.displayed_progress += (self.target_progress - self.displayed_progress) * 0.1

        # Decay milestone pulse
        if self.milestone_pulse > 0:
            self.milestone_pulse -= 0.05

    def draw(self, surface):
        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=3)

        # Progress fill
        fill_width = int(self.rect.width * self.displayed_progress)
        if fill_width > 0:
            fill_rect = pygame.Rect(self.rect.left, self.rect.top, fill_width, self.rect.height)

            # Pulse effect on milestone
            color = self.color
            if self.milestone_pulse > 0:
                color = lerp_color(self.color, (255, 255, 255), self.milestone_pulse)

            pygame.draw.rect(surface, color, fill_rect, border_radius=3)

        # Border
        pygame.draw.rect(surface, (100, 100, 100), self.rect, 1, border_radius=3)
```

---

## 5. Engineering Puzzle Replacement (Secondary Priority)

**Note**: This is secondary to UI polish. The existing rotation pipe puzzle works fine.
Only replace the sliding tile puzzle when all UI polish is complete.

### Current Puzzles (Keep/Remove)

| Puzzle Type | Status | Reason |
|-------------|--------|--------|
| **RotationPipePuzzle** | ✅ KEEP | Fun, fast, intuitive |
| **SlidingTilePuzzle** | ❌ REMOVE | Too slow, frustrating |
| **TrafficJamPuzzle** | ⚠️ PLACEHOLDER | Not implemented |
| **PatternMatchingPuzzle** | ⚠️ PLACEHOLDER | Not implemented |

### Proposed Replacement: Wire Connection Puzzle

**Concept**: Connect colored wires from left side to right side without crossing.

```
LEFT SIDE          GRID           RIGHT SIDE
  [RED] ●  ─────────────────────  ● [RED]
 [BLUE] ●  ─────────────────────  ● [BLUE]
[GREEN] ●  ─────────────────────  ● [GREEN]
```

**Mechanics**:
1. Click start node, drag to end node
2. Wires can only go horizontal/vertical (no diagonal)
3. Wires cannot cross each other
4. All wires must connect to complete puzzle

**Difficulty Scaling**:
- Common: 3 wires, 4x4 grid
- Uncommon: 4 wires, 5x5 grid
- Rare: 5 wires, 6x6 grid
- Epic: 6 wires, 7x7 grid
- Legendary: 7 wires, 8x8 grid

**Implementation**: Only after UI polish phases are complete.

---

## 6. Difficulty/Reward System Reference

### How Difficulty Flows Through the System

```
1. Recipe selected
   │
   ▼
2. calculate_X_difficulty(recipe) called
   │  - Reads recipe['inputs']
   │  - Calculates material points (tier × qty)
   │  - Applies diversity multiplier
   │  - Applies discipline-specific modifiers
   │
   ▼
3. Returns params dict:
   {
     'difficulty_points': float,
     'difficulty_tier': str,  # 'common' to 'legendary'
     # Plus discipline-specific params...
   }
   │
   ▼
4. Minigame uses params to set:
   - Time limits
   - Target sizes
   - Puzzle complexity
   - etc.
   │
   ▼
5. Player completes minigame
   │
   ▼
6. calculate_X_rewards(difficulty_points, performance) called
   │  - performance is Dict with discipline-specific metrics
   │
   ▼
7. Returns rewards dict:
   {
     'quality_tier': str,
     'bonus_pct': int,
     'stat_multiplier': float,
     'first_try_bonus_applied': bool,
     # Plus discipline-specific rewards...
   }
```

### Performance Calculation by Discipline

**Smithing**:
```python
performance = {
    'avg_hammer_score': 0-100,  # Average accuracy of hits
    'temp_in_ideal': bool,      # Was temperature maintained?
    'attempt': int              # 1 = first try bonus eligible
}
```

**Alchemy**:
```python
performance = {
    'chains_completed': int,    # Reactions successfully chained
    'total_chains': int,        # Total reactions needed
    'avg_timing_score': 0-100,  # Timing precision
    'explosions': int,          # Number of failed reactions
    'attempt': int
}
```

**Engineering**:
```python
performance = {
    'puzzles_solved': int,
    'total_puzzles': int,
    'hints_used': int,
    'time_remaining': float,    # 0.0-1.0 fraction
    'attempt': int
}
```

**Enchanting**:
```python
performance = {
    'final_currency': int,      # Out of starting 100
    'spins_completed': int,
    'green_hits': int,
    'red_hits': int
}
```

### Tier-Scaled Failure Penalties

When player fails/abandons minigame:
```python
FAILURE_PENALTIES = {
    'common': 0.30,      # 30% materials lost
    'uncommon': 0.45,    # 45% materials lost
    'rare': 0.60,        # 60% materials lost
    'epic': 0.75,        # 75% materials lost
    'legendary': 0.90    # 90% materials lost
}
```

---

## 7. Implementation Checklist

**IMPORTANT**: UI polish is the PRIMARY focus. Complete all UI work before touching engineering puzzles.

### Phase 4A: Animation Infrastructure (Priority: CRITICAL - Do First)

- [ ] Create `core/minigame_effects.py` module with reusable components:
  - [ ] `ParticleSystem` base class
  - [ ] `AnimationTimer` utility
  - [ ] `ScreenShake` effect
  - [ ] `AnimatedButton` component
  - [ ] `AnimatedProgressBar` component
  - [ ] `draw_glow()` utility function
  - [ ] Easing functions (`ease_out_cubic`, `ease_in_out_sine`, `lerp_color`)
- [ ] Test all components work with existing minigames

### Phase 4B: Alchemy UI Polish (Priority: CRITICAL)

- [ ] Create gradient background (purple-green)
- [ ] Implement cauldron shape with proper perspective
- [ ] Create `AlchemyBubble` particle class
- [ ] Implement bubble particle system (spawn, update, draw loop)
- [ ] Create `CauldronFire` animated fire effect
- [ ] Create `SteamWisp` particle class
- [ ] Implement steam particle system
- [ ] Add potion color stages (POTION_COLORS dict)
- [ ] Add "sweet spot" glow effect for timing
- [ ] Update `game_engine.py:_render_alchemy_minigame()` with new visuals
- [ ] Test visual clarity at all reaction stages
- [ ] Verify particle performance (target: 60fps with 100+ particles)

### Phase 4C: Engineering UI Polish (Priority: HIGH)

- [ ] Implement `draw_blueprint_background()` with grid
- [ ] Create `DecorativeGear` class for corner decorations
- [ ] Add 4 gear instances to corners of minigame area
- [ ] Implement `SchematicDrawEffect` for puzzle loading
- [ ] Add spark particle burst on puzzle completion
- [ ] Style pipe/rotation elements with copper/brass colors
- [ ] Update `game_engine.py:_render_engineering_minigame()` with new visuals
- [ ] Test visual clarity with all puzzle types

### Phase 4D: Refining UI Polish (Priority: HIGH)

- [ ] Create brushed metal background texture
- [ ] Implement `draw_metallic_cylinder()` with gradient effect
- [ ] Create `FurnaceGlow` animated effect
- [ ] Add furnace glow to bottom of screen
- [ ] Create `RefiningSparkParticle` class
- [ ] Add spark burst on cylinder alignment
- [ ] Add green glow highlight for aligned cylinders
- [ ] Update `game_engine.py:_render_refining_minigame()` with new visuals
- [ ] Test visual clarity at all cylinder states

### Phase 4E: Enchanting UI Polish (Priority: MEDIUM)

- [ ] Create cosmic purple gradient background
- [ ] Create `MagicParticle` class for ambient effect
- [ ] Implement magic particle system (30-50 particles)
- [ ] Create `RuneCircle` rotating decoration
- [ ] Implement `WheelSpinAnimation` with easing
- [ ] Create `CurrencyAnimation` for smooth counter
- [ ] Add glow effects for win (green) and loss (red)
- [ ] Update `game_engine.py:_render_enchanting_minigame()` with new visuals
- [ ] Test visual clarity during wheel spin

### Phase 4F: Visual Feedback Polish (Priority: MEDIUM)

- [ ] Add screen shake on failed actions (all minigames)
- [ ] Add button press animations to all minigame buttons
- [ ] Add progress bar pulse effects on milestones
- [ ] Add success particle bursts on completion
- [ ] Add failure visual feedback (red flash)
- [ ] Test feedback timing feels responsive

### Phase 4G: Testing & Integration

- [ ] Playtest each minigame at each difficulty tier
- [ ] Verify 60fps performance with all effects enabled
- [ ] Test on lower-end hardware if possible
- [ ] Verify rewards still feel appropriate
- [ ] Run `testing_difficulty_distribution.py` to verify balance unchanged
- [ ] Check no visual regressions in smithing (already polished)

### Phase 4H: Engineering Puzzle Replacement (Priority: LOW - Only After All Above)

**Note**: Only start this after ALL UI polish is complete and tested.

- [ ] Create `WireConnectionPuzzle` class in `engineering.py`
  - [ ] `__init__` with wire_count, grid_size params
  - [ ] `_generate_puzzle()` - create solvable layout
  - [ ] `start_wire()`, `extend_wire()`, `complete_wire()`
  - [ ] `check_solution()` - verify no crossings
  - [ ] `get_state()` for rendering
- [ ] Add wire puzzle rendering with blueprint theme
- [ ] Add click/drag detection for wire drawing
- [ ] Update `_create_puzzle_for_tier()` to use WireConnectionPuzzle
- [ ] Test all difficulty tiers
- [ ] Verify puzzle is faster than sliding tile (~30-60 sec target)

---

## 8. File Reference Guide

### Adding a New Puzzle Type

1. **Create puzzle class** in `Crafting-subdisciplines/engineering.py`:
```python
class NewPuzzle:
    def __init__(self, difficulty_param):
        pass
    def check_solution(self) -> bool:
        pass
    def get_state(self) -> dict:
        pass
```

2. **Register in `_create_puzzle_for_tier()`**:
```python
def _create_puzzle_for_tier(self, index):
    tier = self.difficulty_tier
    if tier == 'common':
        return NewPuzzle(easy_params)
    # etc.
```

3. **Add rendering** in `core/game_engine.py`:
```python
def _render_engineering_minigame(self):
    # ...
    if 'new_puzzle_field' in puzzle:
        self._render_new_puzzle(surf, puzzle, wx, wy)
```

4. **Add click handling**:
```python
def handle_mouse_click(self, pos):
    if self.minigame_type == 'engineering':
        # Handle new puzzle clicks
```

### Modifying Difficulty Parameters

Edit `core/difficulty_calculator.py`:

```python
# Find the PARAMS dict for your discipline
ENGINEERING_PARAMS = {
    'puzzle_count': (1, 2),  # (easy_value, hard_value)
    'grid_size': (3, 4),
    # Add new params here
}

# Params are interpolated based on difficulty_points
# Low points → first value, high points → second value
```

### Modifying Rewards

Edit `core/reward_calculator.py`:

```python
def calculate_engineering_rewards(difficulty_points, performance):
    # Modify performance calculation
    # Modify reward outputs
    return {
        'quality_tier': str,
        'bonus_pct': int,
        # Add new reward fields
    }
```

### Testing Difficulty Distribution

```bash
cd /path/to/Game-1
python Game-1-modular/core/testing_difficulty_distribution.py
```

This outputs distribution analysis for all disciplines.

---

## Summary

### Priority Order (Follow This Sequence)

1. **CRITICAL - Animation Infrastructure**: Build reusable particle/animation system first
2. **CRITICAL - Alchemy UI**: Full cauldron scene with bubbles, fire, steam
3. **HIGH - Engineering UI**: Blueprint theme with rotating gears
4. **HIGH - Refining UI**: Industrial foundry with furnace glow
5. **MEDIUM - Enchanting UI**: Mystical theme with magic particles
6. **MEDIUM - Visual Feedback**: Screen shake, button animations, progress pulses
7. **LOW - Engineering Puzzles**: Replace sliding tile (only after all UI complete)

### Design Philosophy

- **Visual polish is the goal** - Transform basic UIs into immersive, thematic experiences
- Minigames should be **fun**, not chores
- Every action needs **immediate visual feedback**
- Particle effects and animations should feel **alive and satisfying**
- 60fps performance is mandatory, even with effects
- Difficulty should increase challenge, not tedium
- Rewards should feel earned

### Key Files to Modify

| Priority | File | Changes |
|----------|------|---------|
| 1 | `core/minigame_effects.py` | NEW FILE - reusable animation/particle classes |
| 2 | `core/game_engine.py` | Update render functions: `_render_alchemy_minigame()`, `_render_engineering_minigame()`, `_render_refining_minigame()`, `_render_enchanting_minigame()` |
| 3 | `Crafting-subdisciplines/*.py` | Add effect state management to minigame classes |

### What "Done" Looks Like

- [ ] Each minigame has a distinct, immersive visual theme
- [ ] Particle effects (bubbles, sparks, magic) run at 60fps
- [ ] All buttons and progress bars animate smoothly
- [ ] Success/failure has clear, satisfying feedback
- [ ] The crafting experience feels **polished and professional**

---

*Document prepared for handoff - January 5, 2026*
*Updated with UI-first priority emphasis*
