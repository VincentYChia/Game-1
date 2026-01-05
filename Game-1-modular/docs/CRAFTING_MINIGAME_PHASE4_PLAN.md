# Crafting Minigame Phase 4: Polish & Fun Factor

**Created**: January 5, 2026
**Purpose**: Comprehensive implementation plan for next developer
**Goal**: Complete, fun, visually polished minigames with proper difficulty/reward balance

---

## Table of Contents

1. [Current System Overview](#1-current-system-overview)
2. [Critical Issues to Address](#2-critical-issues-to-address)
3. [Engineering Minigame Overhaul](#3-engineering-minigame-overhaul)
4. [UI Visual Polish Specifications](#4-ui-visual-polish-specifications)
5. [Difficulty/Reward System Reference](#5-difficultyreward-system-reference)
6. [Implementation Checklist](#6-implementation-checklist)
7. [File Reference Guide](#7-file-reference-guide)

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

## 2. Critical Issues to Address

### 2.1 Engineering Minigame (CRITICAL)

**Problem**: Sliding tile puzzle is too hard and time-consuming.
- Rotation pipe puzzle (first puzzle) is fine
- Sliding tile puzzle takes too long to solve
- Players give up before completing

**Solution**: Replace sliding tile puzzle with a new, faster puzzle type (see Section 3)

### 2.2 UI Visual Polish (HIGH)

**Problem**: Most minigames have basic dark backgrounds without thematic aesthetics.

| Discipline | Current | Target |
|------------|---------|--------|
| Smithing | ✅ Forge aesthetic | Complete |
| Alchemy | ❌ Plain dark + green | Cauldron, bubbles, steam |
| Engineering | ❌ Plain dark + blue | Blueprint paper, gears |
| Refining | ❌ Plain with cylinders | Industrial, furnace glow |
| Enchanting | ⚠️ Wheel exists | Magical glow, runes |

### 2.3 Gameplay Feel (MEDIUM)

- Some minigames feel like chores, not games
- Need better visual feedback for actions
- Need clearer success/failure indicators
- Consider adding sound effect hooks (for future audio)

---

## 3. Engineering Minigame Overhaul

### Current Puzzles (Keep/Remove)

| Puzzle Type | Status | Reason |
|-------------|--------|--------|
| **RotationPipePuzzle** | ✅ KEEP | Fun, fast, intuitive |
| **SlidingTilePuzzle** | ❌ REMOVE | Too slow, frustrating |
| **TrafficJamPuzzle** | ⚠️ PLACEHOLDER | Not implemented |
| **PatternMatchingPuzzle** | ⚠️ PLACEHOLDER | Not implemented |

### NEW Puzzle: Wire Connection Puzzle

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

**Why This Works**:
- Faster than sliding puzzles (30-60 seconds vs 2-5 minutes)
- Intuitive drag-and-drop
- Visually satisfying
- Scales well with difficulty
- Fits "engineering/wiring" theme

### NEW Puzzle: Gear Alignment Puzzle

**Concept**: Rotate interlocking gears to align markers.

```
    ┌─────┐
    │  ↑  │  ← Marker must point UP
    │ ●●● │
    │●   ●│
    │ ●●● │
    └─────┘
      │
    ┌─────┐
    │  →  │  ← This gear affects the one above
    │ ●●● │
    │●   ●│
    │ ●●● │
    └─────┘
```

**Mechanics**:
1. Click gear to rotate it 90°
2. Interlocked gears rotate opposite direction
3. All markers must align (point up) to complete
4. Chain reactions make it puzzle-like

**Difficulty Scaling**:
- Common: 2 gears, simple chain
- Uncommon: 3 gears, branching
- Rare: 4 gears, complex chain
- Epic: 5 gears, multi-branch
- Legendary: 6+ gears, nested chains

### Implementation Priority

1. **Wire Connection Puzzle** (HIGH) - Replace sliding tile
2. **Gear Alignment Puzzle** (MEDIUM) - Add variety
3. Keep RotationPipePuzzle as base puzzle type

### Code Structure for New Puzzles

```python
class WireConnectionPuzzle:
    """Wire connection puzzle for engineering minigame."""

    def __init__(self, wire_count=3, grid_size=4):
        self.wire_count = wire_count
        self.grid_size = grid_size
        self.wires = []  # List of wire paths
        self.start_nodes = []  # Left side connection points
        self.end_nodes = []  # Right side connection points
        self.current_wire = None  # Wire being drawn
        self._generate_puzzle()

    def _generate_puzzle(self):
        """Generate solvable puzzle with randomized node positions."""
        pass

    def start_wire(self, node_index):
        """Begin drawing a wire from start node."""
        pass

    def extend_wire(self, grid_x, grid_y):
        """Extend current wire to grid position."""
        pass

    def complete_wire(self, end_node_index):
        """Complete wire connection to end node."""
        pass

    def check_solution(self):
        """Check if all wires are connected without crossing."""
        pass

    def get_state(self):
        """Get puzzle state for rendering."""
        return {
            "grid_size": self.grid_size,
            "wire_count": self.wire_count,
            "wires": self.wires,
            "start_nodes": self.start_nodes,
            "end_nodes": self.end_nodes,
            "current_wire": self.current_wire,
            "solved": self.check_solution()
        }
```

---

## 4. UI Visual Polish Specifications

### 4.1 Alchemy UI (Cauldron Theme)

**Color Palette**:
- Background: Deep purple-green gradient (#1a0a2e → #0a2e1a)
- Accent: Bubbling green (#00ff88), potion purple (#8800ff)
- Text: Pale green (#aaffcc)

**Visual Elements**:
```
┌─────────────────────────────────────────────────────┐
│  ░░░░░ ALCHEMY MINIGAME ░░░░░                       │
│  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~                        │
│                                                      │
│     ╭─────────╮        ┌─────────────────────┐      │
│    ╱  ○ ○ ○  ╲       │ Progress: ████░░░ 65%│      │
│   │  ○ BREW ○ │       └─────────────────────┘      │
│   │  ○ ○ ○ ○ │                                      │
│   │   (⌒⌒)   │  ← Bubbles animate upward           │
│   │  (~~~~)  │                                      │
│   ╰──────────╯                                      │
│      ════════   ← Fire glow animates                │
│     🔥🔥🔥🔥🔥                                        │
│                                                      │
│  [C] Chain Reaction    [S] Stabilize               │
└─────────────────────────────────────────────────────┘
```

**Animations**:
1. Bubbles rising from cauldron (random positions, sizes)
2. Fire flickering at base (color shift orange → yellow)
3. Steam wisps at top (fade in/out)
4. Potion color shifts based on reaction stage
5. "Sweet spot" glow effect when timing is perfect

**Implementation Notes**:
- Use `pygame.time.get_ticks()` for animation timing
- Particle system for bubbles: list of {x, y, size, speed, alpha}
- Color interpolation for reaction stages

### 4.2 Engineering UI (Blueprint Theme)

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

### 4.3 Refining UI (Industrial Theme)

**Color Palette**:
- Background: Dark metal (#2a2a2a) with rust accents (#8b4513)
- Accent: Molten orange (#ff6600), steel blue (#4682b4)
- Text: Industrial white (#e0e0e0)

**Visual Elements**:
- Furnace glow at bottom
- Lock cylinders with metallic sheen
- Sparks when cylinders align
- Heat distortion effect

### 4.4 Enchanting UI (Magical Theme)

**Color Palette**:
- Background: Deep purple-black gradient (#0a0015 → #150030)
- Accent: Magic blue (#00aaff), gold (#ffd700), purple (#9900ff)
- Text: Ethereal white (#ffffff with glow)

**Visual Elements**:
```
┌─────────────────────────────────────────────────────┐
│     ✨ ENCHANTING MINIGAME ✨                        │
│                                                      │
│            ╭───────────────╮                        │
│           ╱  ◐ ◑ ◒ ◓ ◔ ◕  ╲   ← Rune circle       │
│          │   ┌─────────┐   │      rotates          │
│          │   │  WHEEL  │   │                        │
│          │   │  SPINS  │   │                        │
│          │   │   HERE  │   │                        │
│          │   └─────────┘   │                        │
│           ╲  ◕ ◔ ◓ ◒ ◑ ◐  ╱                        │
│            ╰───────────────╯                        │
│                   ▼                                  │
│              [POINTER]                              │
│                                                      │
│  Currency: 💰 125    Spin: 2/3                      │
│  Bet: [====●========] 50                            │
│                                                      │
│  [SPIN WHEEL]                                       │
└─────────────────────────────────────────────────────┘
```

**Animations**:
1. Floating magic particles (random drift)
2. Rune circle rotation (slow, constant)
3. Wheel spin with deceleration easing
4. Glow pulse on win/loss
5. Currency counter animate on change

---

## 5. Difficulty/Reward System Reference

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

## 6. Implementation Checklist

### Phase 4A: Engineering Overhaul (Priority: CRITICAL)

- [ ] Create `WireConnectionPuzzle` class in `engineering.py`
  - [ ] `__init__` with wire_count, grid_size params
  - [ ] `_generate_puzzle()` - create solvable layout
  - [ ] `start_wire()`, `extend_wire()`, `complete_wire()`
  - [ ] `check_solution()` - verify no crossings
  - [ ] `get_state()` for rendering
- [ ] Update `_create_puzzle_for_tier()` to use WireConnectionPuzzle instead of SlidingTilePuzzle
- [ ] Add wire puzzle rendering in `game_engine.py:_render_engineering_minigame()`
- [ ] Add click detection for wire puzzle in `game_engine.py:handle_mouse_click()`
- [ ] Test all difficulty tiers

### Phase 4B: Alchemy UI Polish (Priority: HIGH)

- [ ] Create gradient background (purple-green)
- [ ] Add cauldron shape rendering
- [ ] Implement bubble particle system
- [ ] Add fire/flame animation at base
- [ ] Add steam wisps at top
- [ ] Color-code reaction stages
- [ ] Add "sweet spot" glow effect
- [ ] Test visual clarity at all stages

### Phase 4C: Engineering UI Polish (Priority: HIGH)

- [ ] Create blueprint grid background
- [ ] Add gear decorations (rotating)
- [ ] Implement schematic "drawing" animation on load
- [ ] Add spark effects on puzzle completion
- [ ] Style puzzle elements to look technical/mechanical
- [ ] Test visual clarity

### Phase 4D: Refining UI Polish (Priority: MEDIUM)

- [ ] Create industrial metal background
- [ ] Add furnace glow effect
- [ ] Style cylinders with metallic sheen
- [ ] Add spark/alignment effects
- [ ] Add heat distortion visual

### Phase 4E: Enchanting UI Polish (Priority: MEDIUM)

- [ ] Create magical gradient background
- [ ] Add floating particle effects
- [ ] Add rune circle around wheel
- [ ] Improve wheel visual design
- [ ] Add glow effects for outcomes
- [ ] Animate currency changes

### Phase 4F: Testing & Balance

- [ ] Run `testing_difficulty_distribution.py` to verify distribution
- [ ] Playtest each minigame at each difficulty tier
- [ ] Verify rewards feel appropriate for effort
- [ ] Check first-try bonus is working
- [ ] Verify no crashes or edge cases

---

## 7. File Reference Guide

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

**Immediate Priority**: Replace SlidingTilePuzzle with WireConnectionPuzzle in engineering minigame.

**Secondary Priority**: Visual polish for Alchemy and Engineering UIs.

**Design Philosophy**:
- Minigames should be **fun**, not chores
- 20-60 seconds per puzzle is ideal
- Visual feedback should be satisfying
- Difficulty should increase challenge, not tedium
- Rewards should feel earned

**Key Principle**: The harder the recipe, the more the minigame should challenge skill, not patience.

---

*Document prepared for handoff - January 5, 2026*
