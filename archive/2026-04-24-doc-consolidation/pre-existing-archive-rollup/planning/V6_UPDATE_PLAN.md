# V6 Update Plan - Section by Section

## Approach
- **Coded systems**: Replace conceptual with actual JSON schemas/code references
- **Partial implementations**: Augment concept with what's done, keep end goal
- **Not implemented**: Keep V5 aspirational content, mark as 🔮 PLANNED

---

## SECTION 1: Header & Latest Updates (Lines 1-86)
**Status:** ✅ Already updated in previous pass
**Action:** Minor refinements only

---

## SECTION 2: Part IV - Progression Systems (Lines 88-170)

### 2.1 Character Stats (Lines 117-170)
**V5:** Conceptual stat effects (STR +5% melee, etc.)
**Reality:** `stats-calculations.JSON` has complete hierarchical formula system
**Action:**
- Add actual formula from JSON: `FinalStat = globalBase × tierMultiplier × categoryMultiplier × typeMultiplier × subtypeMultiplier × itemMultiplier`
- Keep stat descriptions but add code references
- Add actual globalBases values (weaponDamage: 10, armorDefense: 10, etc.)

### 2.2 Level and Experience (Lines 174-234)
**V5:** EXP formula `200 * (1.75 ** (level - 1))`
**Reality:** Formula is implemented, combat-config.JSON has EXP rewards
**Action:**
- Verify formula matches code
- Add actual EXP rewards from combat-config.JSON (T1: 100, T2: 400, T3: 1600, T4: 6400)
- Add bossMultiplier: 10.0

### 2.3 Skill System (Lines 236-577)
**V5:** Conceptual effect types (empower, quicken, etc.)
**Reality:** `skills-translation-table.JSON` has complete formulas for all 10 effect types
**Action:**
- Replace conceptual magnitude descriptions with actual values:
  - Duration: instant=0s, brief=15s, moderate=30s, long=60s, extended=120s
  - Mana: low=30, moderate=60, high=100, extreme=150
  - Cooldown: short=120s, moderate=300s, long=600s, extreme=1200s
- Add actual effect calculation formulas with examples
- Add skill progression system (max level 10, EXP requirements)
- Add category translations (mining, forestry, combat, smithing, etc.)

### 2.4 Title System (Lines 580-620)
**V5:** Conceptual tiers (Novice, Apprentice, etc.)
**Reality:** `titles-1.JSON` exists but structure needs verification
**Action:**
- Verify title JSON structure
- Add actual title examples with bonuses
- Keep LLM generation as 🔮 PLANNED

### 2.5 Class System (Lines 623-810)
**Status:** ✅ Already updated with tag system
**Action:**
- Verify against `classes-1.JSON` (320 lines)
- Add full JSON structure example
- Ensure all 6 classes have complete data

---

## SECTION 3: Part V - Gameplay Systems (Lines 840-1100)

### 3.1 Combat System (Lines 842-982)
**Status:** ✅ Partially updated
**Reality:** `combat-config.JSON` + `combat_manager.py` (1,377 lines)
**Action:**
- Add spawn rates from combat-config.JSON (peaceful, normal, dangerous, rare)
- Add safe zone definition (center: 50,50, radius: 15)
- Add enemy respawn mechanics
- Add actual combat mechanics values

### 3.2 NPC Quest System (Lines 985-1050)
**V5:** 3 NPCs with quest chains
**Reality:** `npc_db.py` (146 lines), `quest_system.py`
**Action:**
- Verify actual NPC implementation
- Document what's working vs. planned

### 3.3 Inventory UI (Lines 1053-1100)
**V5:** Basic inventory description
**Reality:** Tooltip systems implemented
**Action:**
- Add tool slot tooltip details
- Add class selection tooltip details
- Add equipment slot descriptions

---

## SECTION 4: Part I - Architectural Foundation (Lines 1172-1509)

### 4.1 Design Principles (Lines 1172-1221)
**V5:** 10 core principles
**Reality:** Principles are followed in implementation
**Action:** Add implementation examples for each principle

### 4.2 Hardcode vs JSON Philosophy (Lines 1180-1205)
**V5:** Philosophy description
**Reality:** Fully implemented with 15+ JSON files
**Action:**
- List ALL actual JSON files with line counts
- Show file structure hierarchy

### 4.3 Element Template System (Lines 1224-1332)
**V5:** 7 elements with field templates
**Reality:** `tag-definitions.JSON` has damage_type category
**Action:**
- Cross-reference with actual tag system
- Show which elements are implemented in combat

### 4.4 Text-Based Value System (Lines 1336-1456)
**V5:** Conceptual 3-tier lookup
**Reality:** `value-translation-table-1.JSON` (237 lines) - FULLY IMPLEMENTED
**Action:** MAJOR UPDATE
- Replace conceptual description with actual JSON content
- Show all translation tables:
  - yieldTranslations (few, several, many, abundant, plentiful)
  - respawnTranslations (null, quick, normal, slow, very_slow)
  - chanceTranslations (guaranteed, high, moderate, low, rare, improbable)
  - densityTranslations
  - tierBiasTranslations
  - sizeMultipliers
  - toolEfficiency
  - resourceHealthByTier
  - toolDamageByTier

---

## SECTION 5: Part II - Game World & Content (Lines 1512-3331)

### 5.1 World Structure (Lines 1540-1593)
**V5:** 100×100 world, 36 chunks
**Reality:** `world_system.py`, `chunk.py`
**Action:** Verify dimensions match code

### 5.2 Chunk Templates (Lines 1594-1887)
**V5:** 9 chunk templates with detailed spawns
**Reality:** `Chunk-templates-1.JSON`
**Action:**
- Verify template implementation
- Cross-reference with value-translation-table densities

### 5.3 Material System (Lines 2065-2698)
**V5:** 60 materials with narratives
**Reality:** `items-materials-1.JSON` - 57 materials
**Action:**
- Update count to 57 (note 3 T4 monster drops missing)
- Keep narratives (they're in the JSON)
- Add actual JSON structure example
- Verify tier/category distribution

### 5.4 Gathering System (Lines 2702-3201)
**V5:** Detailed gathering mechanics
**Reality:** `value-translation-table-1.JSON` has exact values
**Action:** MAJOR UPDATE
- Replace conceptual tool efficiency with actual:
  - sameTier: 1.0
  - oneTierHigher: 0.5
  - twoTiersHigher: 0.1
  - lowerTier: 1.5
- Add actual resource HP by tier (100/200/400/800)
- Add actual tool damage by tier (10/20/40/80)
- Add size multipliers from JSON

### 5.5 Resource Nodes (Lines 3271-3331)
**V5:** JSON example structure
**Reality:** `resource-node-1.JSON`
**Action:** Verify structure matches, update if different

---

## SECTION 6: Part III - Crafting Systems (Lines 3529-4639)

### 6.1 Crafting Overview (Lines 3531-3600)
**Status:** ✅ Partially updated
**Action:** Add actual recipe file references with sizes

### 6.2 Smithing (Lines 3690-3750)
**V5:** Conceptual mini-game
**Reality:** `smithing.py` (622 lines), `recipes-smithing-3.JSON` (30KB)
**Action:**
- Add actual recipe count
- Document mini-game mechanics from code
- Add recipe JSON structure example

### 6.3 Refining (Lines 3750-3890)
**V5:** Hub-spoke layout description
**Reality:** `refining.py` (669 lines), `recipes-refining-1.JSON` (24KB)
**Action:**
- Verify hub-spoke implementation
- Add actual mechanics from code

### 6.4 Alchemy (Lines 3890-4120)
**V5:** Detailed reaction chain description
**Reality:** `alchemy.py` (695 lines), `recipes-alchemy-1.JSON` (12KB)
**Action:**
- Verify gradient success implementation
- Document actual reaction mechanics

### 6.5 Engineering (Lines 4120-4450)
**V5:** Slot-type system, puzzle types
**Reality:** `engineering.py` (890 lines), `recipes-engineering-1.JSON` (11KB)
**Action:**
- Verify puzzle implementation
- Document device types actually working

### 6.6 Enchanting (Lines 4450-4500)
**V5:** Freeform pattern description
**Reality:** `enchanting.py` (1,265 lines), `recipes-enchanting-1.JSON` (22KB)
**Action:**
- Document actual pattern system
- List working enchantments from combat_manager.py

### 6.7 Cross-Crafting Systems (Lines 4500-4639)
**V5:** Station tiers, material consumption
**Reality:** `crafting-stations-1.JSON`
**Action:** Verify station implementation

---

## SECTION 7: New Sections to Add

### 7.1 Tag System (NEW)
**Source:** `tag-definitions.JSON`, `core/tag_*.py`
**Content:**
- All tag categories (equipment, geometry, damage_type, status_debuff, status_buff, special, trigger, context, class, playstyle, armor_type)
- Tag priorities and conflicts
- Synergy system
- Effect executor flow

### 7.2 Status Effects (Already added)
**Status:** ✅ Added in previous pass
**Action:** Verify against `status_effect.py` (827 lines)

### 7.3 Save System (Already added)
**Status:** ✅ Added in previous pass
**Action:** Verify completeness

### 7.4 Database Architecture (NEW)
**Source:** `data/databases/*.py` (~1,700 lines)
**Content:**
- Singleton pattern usage
- JSON loading flow
- Database classes and their roles

---

## Priority Order

1. **HIGH:** Section 4.4 (Text-Based Value System) - Replace conceptual with actual JSON
2. **HIGH:** Section 2.3 (Skill System) - Add translation table formulas
3. **HIGH:** Section 5.4 (Gathering System) - Add actual values
4. **MEDIUM:** Section 6.x (Crafting) - Verify implementations
5. **MEDIUM:** Section 7.1 (Tag System) - New comprehensive section
6. **LOW:** Remaining sections - Verify and cross-reference

---

## Estimated Changes

| Section | Lines to Update | Type |
|---------|-----------------|------|
| 4.4 Text-Based Values | ~120 lines | REPLACE |
| 2.3 Skill System | ~150 lines | AUGMENT |
| 5.4 Gathering | ~100 lines | REPLACE |
| 6.x Crafting (5 sections) | ~200 lines | AUGMENT |
| 7.1 Tag System | ~150 lines | NEW |
| Other sections | ~100 lines | VERIFY |

**Total estimated: ~820 lines of changes/additions**

---

## Hardcoded Items Tracking

Items that are currently hardcoded but should eventually migrate to JSON for full data-driven architecture.

### Intentionally Hardcoded (Keep as Code)
These are "invariant mechanics" - the HOW, not the WHAT:
- Element behavior boundaries (fire never slows, ice can slow AND damage)
- Lookup hierarchy logic (override → tier/category → fallback)
- Formula SHAPES (multiplication order, calculation structure)
- Mini-game core mechanics and scoring logic
- Position/distance calculations
- Grid rendering system
- Equipment slot architecture

### Hardcoded Placeholders (Should Become JSON)
These are values that should eventually move to JSON:

| Item | Current Location | Target JSON | Priority |
|------|------------------|-------------|----------|
| Character EXP curve formula | `character.py` | `progression-config.json` | LOW |
| Title progression thresholds | `title_system.py` | `titles-1.JSON` | LOW |
| Skill EXP per activation (100) | `skill_manager.py` | `skills-translation-table.JSON` | LOW |
| Stat bonus percentages (5% per point) | `character.py` | `stats-calculations.JSON` | MEDIUM |
| Mana regen formula | `character.py` | `stats-calculations.JSON` | LOW |
| Respec cooldown | `class_system.py` | `class-config.json` | LOW |
| Interaction radius (3 units) | Multiple files | `game-config.json` | LOW |
| Drop scatter radius (2-3 units) | `resource_system.py` | `game-config.json` | LOW |

### Not Yet Implemented (Planned Features)
- 🔮 LLM integration system
- 🔮 Block/Parry combat mechanics
- 🔮 Summon/minion mechanics
- ⏳ World generation (detailed templates pending)
- ⏳ NPC/Quest system (needs expansion)

### Notes
- The architecture IS fully tag/JSON-driven
- ~85-90% of content is JSON-driven
- Remaining hardcoded values are low priority (working fine as placeholders)
- Migration can happen incrementally during future development
