# System 6: Hostile-Chunk Assignment Plan
**Created**: 2026-01-10
**Purpose**: Fix enemySpawns data and design spawn rate implementation

---

## PART 1: AUDIT RESULTS - ALL HOSTILES

### Total Hostiles: 13 enemies across 4 tiers

**TIER 1 (Starter - Peaceful Chunks):**
1. `wolf_grey` - Grey Wolf (beast, passive_patrol)
2. `slime_green` - Green Slime (ooze, stationary)
3. `beetle_brown` - Brown Beetle (insect, docile_wander)

**TIER 2 (Mid-Game - Dangerous Chunks):**
4. `wolf_dire` - Dire Wolf (beast, aggressive_pack)
5. `slime_acid` - Acid Slime (ooze, aggressive_swarm)
6. `beetle_armored` - Armored Beetle (insect, territorial)

**TIER 3 (Advanced - Rare/Dangerous Chunks):**
7. `wolf_elder` - Elder Wolf (beast, boss_encounter)
8. `slime_crystal` - Crystal Slime (ooze, boss_encounter)
9. `golem_stone` - Stone Golem (construct, boss_encounter)

**TIER 4 (End-Game - Rare Chunks):**
10. `beetle_titan` - Titan Beetle (insect, boss_encounter)
11. `golem_crystal` - Crystal Golem (construct, boss_encounter)
12. `void_wraith` - Void Wraith (undead, aggressive_phase)
13. `entity_primordial` - Primordial Entity (aberration, boss_encounter)

---

## PART 2: PROPER CHUNK ASSIGNMENTS

### Chunk Types Available:
- **Peaceful**: peaceful_forest, peaceful_quarry, peaceful_cave
- **Dangerous**: dangerous_forest, dangerous_quarry, dangerous_cave
- **Rare**: rare_forest (Ancient Heartwood), rare_quarry (Primordial Vein), rare_cave (Paradox Hollow)

---

### PEACEFUL_FOREST Assignment
```json
{
  "chunkType": "peaceful_forest",
  "enemySpawns": {
    "wolf_grey": {
      "density": "very_low",
      "behavior": "passive_patrol"
    }
  }
}
```
**Rationale**: Grey wolves roam forests. Passive, low density for starter area.

---

### PEACEFUL_QUARRY Assignment
```json
{
  "chunkType": "peaceful_quarry",
  "enemySpawns": {
    "slime_green": {
      "density": "very_low",
      "behavior": "stationary"
    },
    "beetle_brown": {
      "density": "low",
      "behavior": "docile_wander"
    }
  }
}
```
**Rationale**: Slimes and beetles fit quarry/cave environments. Both docile for starter area.

---

### PEACEFUL_CAVE Assignment
```json
{
  "chunkType": "peaceful_cave",
  "enemySpawns": {
    "beetle_brown": {
      "density": "very_low",
      "behavior": "docile_wander"
    },
    "slime_green": {
      "density": "low",
      "behavior": "stationary"
    }
  }
}
```
**Rationale**: Cave insects and slimes. Swapped density from quarry for variety.

---

### DANGEROUS_FOREST Assignment
```json
{
  "chunkType": "dangerous_forest",
  "enemySpawns": {
    "wolf_grey": {
      "density": "high",
      "behavior": "aggressive_pack"
    },
    "wolf_dire": {
      "density": "moderate",
      "behavior": "aggressive_alpha"
    }
  }
}
```
**Rationale**:
- Grey wolves more numerous, behavior changes to aggressive
- Dire wolves spawn as pack leaders
- Forest-themed beast enemies only

---

### DANGEROUS_QUARRY Assignment
```json
{
  "chunkType": "dangerous_quarry",
  "enemySpawns": {
    "slime_green": {
      "density": "high",
      "behavior": "aggressive_swarm"
    },
    "slime_acid": {
      "density": "moderate",
      "behavior": "aggressive_swarm"
    },
    "beetle_brown": {
      "density": "moderate",
      "behavior": "territorial"
    },
    "beetle_armored": {
      "density": "low",
      "behavior": "aggressive_guard"
    }
  }
}
```
**Rationale**:
- Mix of T1 and T2 enemies
- Slime swarms dangerous in numbers
- Armored beetles rare but threatening

---

### DANGEROUS_CAVE Assignment
```json
{
  "chunkType": "dangerous_cave",
  "enemySpawns": {
    "beetle_brown": {
      "density": "high",
      "behavior": "territorial"
    },
    "beetle_armored": {
      "density": "moderate",
      "behavior": "aggressive_territory"
    },
    "slime_acid": {
      "density": "low",
      "behavior": "aggressive_swarm"
    },
    "golem_stone": {
      "density": "very_low",
      "behavior": "boss_encounter"
    }
  }
}
```
**Rationale**:
- Beetle-heavy cave environment
- Stone golem as rare mini-boss encounter
- Some acid slimes for variety

---

### RARE_FOREST (Ancient Heartwood) Assignment
```json
{
  "chunkType": "rare_forest",
  "enemySpawns": {
    "wolf_dire": {
      "density": "moderate",
      "behavior": "aggressive_hunter"
    },
    "wolf_elder": {
      "density": "low",
      "behavior": "boss_encounter"
    }
  }
}
```
**Rationale**:
- Ancient forest, ancient wolves
- Elder Wolf as legendary boss
- No T1 enemies in rare chunks

---

### RARE_QUARRY (Primordial Vein) Assignment
```json
{
  "chunkType": "rare_quarry",
  "enemySpawns": {
    "beetle_armored": {
      "density": "high",
      "behavior": "aggressive_guard"
    },
    "slime_acid": {
      "density": "moderate",
      "behavior": "aggressive_swarm"
    },
    "slime_crystal": {
      "density": "low",
      "behavior": "boss_encounter"
    },
    "golem_crystal": {
      "density": "very_low",
      "behavior": "aggressive_guard"
    }
  }
}
```
**Rationale**:
- Legendary ore deposits, guarded by constructs
- Crystal enemies (slime, golem) fit crystal quarry theme
- High-tier enemies only

---

### RARE_CAVE (Paradox Hollow) Assignment
```json
{
  "chunkType": "rare_cave",
  "enemySpawns": {
    "void_wraith": {
      "density": "moderate",
      "behavior": "aggressive_phase"
    },
    "golem_stone": {
      "density": "low",
      "behavior": "boss_encounter"
    },
    "beetle_titan": {
      "density": "very_low",
      "behavior": "boss_encounter"
    },
    "entity_primordial": {
      "density": "very_low",
      "behavior": "boss_encounter"
    }
  }
}
```
**Rationale**:
- Reality-warped depths, end-game content
- Void wraith phases through dimensions
- Primordial entity as ultimate boss
- Multiple boss encounters possible

---

## PART 3: SPAWN RATE SYSTEM DESIGN

### Current System (combat_manager.py)
```python
# Current spawning logic (simplified):
def spawn_enemies_in_chunk(chunk):
    if chunk.danger_level == "peaceful":
        spawn_count = random.randint(0, 2)
        tier_pool = [1]
    elif chunk.danger_level == "dangerous":
        spawn_count = random.randint(4, 8)
        tier_pool = [1, 2, 3]
    else:  # rare
        spawn_count = random.randint(1, 3)
        tier_pool = [1, 2, 3, 4]

    # Randomly pick from ALL enemies matching tier
    for _ in range(spawn_count):
        random_enemy = pick_random_enemy_from_tier(tier_pool)
        spawn(random_enemy)
```

**PROBLEM**: Completely ignores chunk theme (forest vs cave vs quarry) and enemySpawns field!

---

### NEW SYSTEM: Weighted Spawn Pool

**Design Philosophy:**
- **Base pool**: All enemies matching chunk tier (current behavior)
- **Priority pool**: Enemies listed in `enemySpawns` (NEW)
- **Weight system**: Priority enemies spawn 3-5x more often

```python
# NEW spawning logic:
def spawn_enemies_in_chunk_NEW(chunk, chunk_template):
    # Get base spawn parameters
    danger_config = get_danger_config(chunk.category)
    spawn_count = random.randint(
        danger_config["min_enemies"],
        danger_config["max_enemies"]
    )

    # Build weighted spawn pool
    spawn_pool = []

    # 1. Add priority enemies from enemySpawns (HIGH WEIGHT)
    if "enemySpawns" in chunk_template:
        for enemy_id, spawn_info in chunk_template["enemySpawns"].items():
            weight = get_density_weight(spawn_info["density"])
            enemy_def = get_enemy_definition(enemy_id)

            spawn_pool.append({
                "enemy": enemy_def,
                "behavior": spawn_info["behavior"],
                "weight": weight,
                "priority": True
            })

    # 2. Add general pool enemies (LOW WEIGHT)
    # Only add if not already in priority pool
    tier_pool = get_tier_pool_for_danger(chunk.category)
    for tier in tier_pool:
        for enemy in get_enemies_by_tier(tier):
            # Skip if already in priority pool
            if any(e["enemy"].enemyId == enemy.enemyId for e in spawn_pool):
                continue

            # Add with low weight
            spawn_pool.append({
                "enemy": enemy,
                "behavior": enemy.behavior,  # Use default
                "weight": 1,  # Base weight
                "priority": False
            })

    # 3. Spawn enemies using weighted random selection
    for _ in range(spawn_count):
        selected = weighted_random_choice(spawn_pool)
        spawn_enemy(
            enemy_def=selected["enemy"],
            behavior=selected["behavior"],
            chunk=chunk
        )
```

---

### Density to Weight Mapping
```python
DENSITY_WEIGHTS = {
    "very_low": 2,      # 2x more likely than base
    "low": 3,           # 3x more likely
    "moderate": 5,      # 5x more likely
    "high": 8,          # 8x more likely
    "very_high": 12     # 12x more likely
}

def get_density_weight(density: str) -> int:
    return DENSITY_WEIGHTS.get(density, 1)
```

---

### Example Calculation

**Scenario**: Spawning in `dangerous_forest`

**Priority Pool** (from enemySpawns):
- `wolf_grey` (density: high, weight: 8)
- `wolf_dire` (density: moderate, weight: 5)

**General Pool** (tier 1-3, not in priority):
- `slime_green` (T1, weight: 1)
- `slime_acid` (T2, weight: 1)
- `beetle_brown` (T1, weight: 1)
- `beetle_armored` (T2, weight: 1)

**Total Weight**: 8 + 5 + 1 + 1 + 1 + 1 = 17

**Spawn Probabilities**:
- `wolf_grey`: 8/17 = **47%**
- `wolf_dire`: 5/17 = **29%**
- Other enemies: 4/17 = **24%** total (6% each)

**Result**: Wolves spawn 76% of the time, non-forest enemies 24%

---

### Behavior Override

**Key Feature**: enemySpawns can override default behavior!

```python
# Example: Grey wolf normally passive
wolf_grey_default.behavior = "passive_patrol"

# But in dangerous_forest:
enemySpawns: {
  "wolf_grey": {
    "density": "high",
    "behavior": "aggressive_pack"  # OVERRIDE
  }
}

# Result: Wolf spawns with aggressive_pack behavior
```

**Use Cases**:
- Peaceful chunks: Enemies spawn with docile behaviors
- Dangerous chunks: Same enemies spawn aggressive
- Rare chunks: Unique boss behaviors for normally common enemies

---

## PART 4: IMPLEMENTATION STEPS

### Step 1: Update Chunk Templates JSON
Replace current `Chunk-templates-1.JSON` with proper enemySpawns assignments (see Part 2).

### Step 2: Modify `combat_manager.py`
Add weighted spawn pool logic:
```python
# Location: combat_manager.py, _spawn_enemies_in_chunk()

def _spawn_enemies_in_chunk(self, chunk, chunk_template):
    """
    Spawn enemies in chunk using weighted pool.
    Priority given to enemies listed in chunk_template.enemySpawns.
    """
    # ... implementation from Part 3
```

### Step 3: Add Configuration
```python
# combat_config.JSON additions:
{
  "spawnWeights": {
    "very_low": 2,
    "low": 3,
    "moderate": 5,
    "high": 8,
    "very_high": 12
  },
  "enableEnemySpawnsField": true,  # Feature flag
  "fallbackToGeneralPool": true    # Allow non-listed enemies
}
```

### Step 4: Testing
1. **Test peaceful chunks**: Only T1 enemies, low density
2. **Test dangerous chunks**: Mix of priority (wolves/beetles) and general pool
3. **Test rare chunks**: High-tier bosses spawn appropriately
4. **Test behavior overrides**: Same enemy, different behavior per chunk
5. **Test weights**: Priority enemies spawn significantly more often

---

## PART 5: LLM TRAINING DATA EXTRACTION

Once enemySpawns is properly populated, extraction becomes:

```python
def extract_hostile_chunk_assignments(chunk_templates):
    """Build reverse mapping: hostile → chunks"""
    hostile_to_chunks = {}

    for template in chunk_templates["templates"]:
        for enemy_id, spawn_info in template.get("enemySpawns", {}).items():
            if enemy_id not in hostile_to_chunks:
                hostile_to_chunks[enemy_id] = []

            hostile_to_chunks[enemy_id].append({
                "chunkType": template["chunkType"],
                "category": template["category"],
                "theme": template["theme"],
                "density": spawn_info["density"],
                "behavior": spawn_info["behavior"]
            })

    return hostile_to_chunks
```

**Training Data Example**:
```json
INPUT = {
  "primaryChunk": "dangerous_forest",
  "chunkCategory": "dangerous",
  "chunkTheme": "forest",
  "spawnDensity": "high",
  "spawnBehavior": "aggressive_pack",
  "allChunks": ["peaceful_forest", "dangerous_forest"],
  "tier": 1,
  "category": "beast",
  "tags": ["wolf", "common", "aggressive"]
}

OUTPUT = {
  // Complete wolf_grey hostile JSON
}
```

**LLM Learns**:
- Forest chunks → wolf/beast enemies
- Cave/quarry chunks → beetle/slime enemies
- Dangerous chunks → aggressive behaviors
- Rare chunks → boss encounters, high-tier enemies

---

## PART 6: FUTURE EXTENSIBILITY

### Adding New Chunk Types
```json
{
  "chunkType": "volcanic_depths",
  "category": "rare",
  "theme": "volcanic",
  "enemySpawns": {
    "fire_elemental": {  // NEW ENEMY
      "density": "moderate",
      "behavior": "aggressive_burn"
    }
  }
}
```

**LLM generates `fire_elemental`** based on:
- Chunk theme (volcanic)
- Expected tier (rare → T3-T4)
- Spawn density (moderate)
- Behavior (aggressive_burn)

### Dynamic Difficulty Scaling
```python
# Future enhancement: Scale density based on player level
def adjust_spawn_density_for_player_level(base_density, player_level):
    if player_level > 20:
        return scale_density_up(base_density)
    return base_density
```

---

## SUMMARY

**Problems Solved**:
✅ Incomplete enemySpawns data → **All 13 hostiles properly assigned**
✅ Unused enemySpawns field → **Designed weighted spawn system**
✅ No chunk theming → **Forest gets wolves, caves get beetles/slimes**
✅ No LLM training data → **Clean chunk → hostile mappings**

**Next Steps**:
1. Update `Chunk-templates-1.JSON` with proper assignments
2. Implement weighted spawn pool in `combat_manager.py`
3. Test spawn rates and behaviors
4. Extract training data for LLM
5. Train LLM to generate hostiles for new chunk types

---

**End of Plan**
