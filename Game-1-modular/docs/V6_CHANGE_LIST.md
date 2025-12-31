# V6 Change List: Updates from V5

This document tracks all changes needed to transform V5 into V6.

## Legend
- ✅ IMPLEMENTED - Verified working in code
- ⏳ PARTIAL - Some aspects implemented
- 🔮 PLANNED - Design only, not coded
- ❌ REMOVED - No longer applicable
- 🔄 UPDATED - Values/mechanics changed from V5

---

## HEADER CHANGES

### Version Info (Lines 1-10)
- [ ] Update version to 6.0
- [ ] Update date to current
- [ ] Change status description to: "Living Document - Implementation Reality + Design Aspirations"
- [ ] Add note: "Implementation status markers (✅/⏳/🔮) indicate what's coded vs planned"

### Latest Updates Section (Lines 9-51)
- [ ] Update to reflect v5 → v6 changes
- [ ] Add new implemented features:
  - Tag-driven class system with skill affinity
  - Class selection tooltips
  - Tool slot tooltips with class bonuses
  - Enchantment combat integration
  - Full save/load system

---

## PART I: ARCHITECTURAL FOUNDATION

### Core Design Principles (Lines 1172-1221)
- [ ] Add status: ✅ IMPLEMENTED - Philosophy followed in codebase
- [ ] Note which principles are actively enforced vs aspirational

### Hardcode vs JSON Philosophy (Lines 1180-1205)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] List actual JSON files that exist:
  - classes-1.JSON ✅
  - skills-skills-1.JSON ✅
  - recipes-*.json ✅
  - items-*.JSON ✅
  - titles-1.JSON ✅
  - placements-*.JSON ✅

### Element Template System (Lines 1224-1332)
- [ ] Add status: ⏳ PARTIAL
- [ ] Note: Elements exist in combat (fire, ice, lightning, poison, etc.)
- [ ] Note: Template validation not enforced by LLM yet
- [ ] Verify element fields match combat_manager.py implementation

### Text-Based Value System (Lines 1336-1456)
- [ ] Add status: 🔮 PLANNED
- [ ] Note: Currently using hardcoded numeric values
- [ ] Note: Hierarchical lookup not implemented

### System Clarifications (Lines 1460-1509)
- [ ] Update Title System status: ✅ IMPLEMENTED (title_system.py)
- [ ] Update Skill System status: ✅ IMPLEMENTED (skill_manager.py)
- [ ] Update Progression System status: ⏳ PARTIAL
- [ ] Note skill evolution: 🔮 PLANNED (not implemented)

---

## PART II: GAME WORLD & CONTENT

### Vision and Philosophy (Lines 1512-1538)
- [ ] Keep as aspirational (no status marker needed - this is vision)

### World Structure (Lines 1540-1939)
- [ ] Add status: ⏳ PARTIAL
- [ ] Note: Basic world generation works
- [ ] Note: 9 chunk templates defined but simplified in implementation
- [ ] Verify chunk size matches world_system.py

### Chunk Content Specifications (Lines 1594-1887)
- [ ] Add status: 🔮 PLANNED (detailed specs)
- [ ] Note: Basic chunk types exist, detailed distributions not implemented
- [ ] Keep all detailed specs as design reference

### Material System - 60 Materials (Lines 2065-2698)
- [ ] Add status header: ⏳ PARTIAL
- [ ] Keep ALL material narratives (these are essential design content)
- [ ] Add implementation notes per category:
  - Metals: ⏳ PARTIAL (basic metals in items-materials-1.JSON)
  - Woods: ⏳ PARTIAL (basic woods exist)
  - Stones: ⏳ PARTIAL (basic stones exist)
  - Elementals: ✅ IMPLEMENTED (drop system works)
  - Monster Drops: ⏳ PARTIAL (wolf, slime, beetle drops work)
- [ ] Note T4 monster drops still PLACEHOLDER

### Gathering System (Lines 2702-3201)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Verify tool tier efficiency matches character.py
- [ ] Verify resource HP scaling matches natural_resource.py
- [ ] Update durability system to match actual implementation

### Resource Nodes (Lines 3271-3331)
- [ ] Add status: ⏳ PARTIAL
- [ ] Note: Basic node system works, JSON structure simplified

---

## PART III: CRAFTING SYSTEMS

### Crafting Overview (Lines 3334-3489)
- [ ] Add status: ✅ IMPLEMENTED (5 disciplines working)
- [ ] Update station tier info to match actual code
- [ ] Verify grid sizes

### Smithing (Lines 3492-3547)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: smithing.py (622 lines)
- [ ] Verify minigame mechanics match code

### Forging/Refining (Lines 3550-3687)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: refining.py (669 lines)
- [ ] Verify hub-spoke layout matches code

### Alchemy (Lines 3690-3918)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: alchemy.py (695 lines)
- [ ] Verify reaction chain mechanics

### Engineering (Lines 3921-4245)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: engineering.py (890 lines)
- [ ] Verify puzzle types match code

### Enchanting (Lines 4249-4296)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: enchanting.py (1,265 lines)
- [ ] Verify pattern system matches code
- [ ] ADD: List of working enchantments from combat_manager.py:
  - Sharpness, Protection, Efficiency, Fortune, Unbreaking
  - Fire Aspect, Poison, Swiftness, Thorns, Lifesteal
  - Knockback, Frost Touch, Chain Damage

### Cross-Crafting Systems (Lines 4299-4434)
- [ ] Add status: ⏳ PARTIAL
- [ ] Verify station upgrade system status

---

## PART IV: PROGRESSION & SYSTEMS (Lines 55-398 in V5)

### Character Stats (Lines 76-138)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Verify stat effects match character.py:recalculate_stats()
- [ ] Add code references

### Level and Experience (Lines 140-234)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Verify EXP formula: `200 * (1.75 ** (level - 1))`
- [ ] Verify EXP sources match code

### Skill System (Lines 236-388)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: skill_manager.py (709 lines)
- [ ] ADD: Skill affinity system (NEW in V6):
  ```
  When using skills, matching tags between class and skill grant bonuses:
  - 1 tag match: +5% effectiveness
  - 2 tags: +10%
  - 3 tags: +15%
  - 4+ tags: +20% (capped)
  ```
- [ ] Note: Skill evolution 🔮 PLANNED

### Title System (Lines 390-577)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: title_system.py, title_db.py
- [ ] Note: LLM generation 🔮 PLANNED

### Class System (Lines 580-693)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: class_system.py, classes-1.JSON
- [ ] ADD: Tag-driven system (NEW in V6):
  - Each class has tags array
  - Tags drive skill affinity bonuses
  - Tags drive tool efficiency bonuses
- [ ] ADD: Class tooltips showing tag effects
- [ ] Verify class bonuses match JSON

### Equipment Progression (Lines 696-718)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: equipment_manager.py

---

## PART V: GAMEPLAY SYSTEMS (Lines 721-968)

### Combat System (Lines 724-787)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] Reference: combat_manager.py (1,377 lines)
- [ ] ADD: Full damage calculation pipeline
- [ ] ADD: Weapon tag effects (precision, crushing, armor_breaker)
- [ ] ADD: Dual wielding system
- [ ] ADD: Enchantment integration
- [ ] Note: Block/Parry 🔮 PLANNED (not implemented)
- [ ] Note: Summon 🔮 PLANNED (not implemented)

### NPC Quest System (Lines 790-842)
- [ ] Add status: ⏳ PARTIAL
- [ ] Reference: npc_system.py, quest_system.py
- [ ] Note: Basic quests work, full system needs expansion

### Inventory UI (Lines 845-896)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] ADD: Tool slot tooltips (NEW in V6)
- [ ] ADD: Class selection tooltips (NEW in V6)

### Technical Architecture (Lines 899-968)
- [ ] Add status: ✅ IMPLEMENTED
- [ ] ADD: Save/Load system details
- [ ] Reference: save_manager.py

---

## PART VI: DEVELOPMENT REFERENCE (Lines 970-1100)

### JSON Schemas (Lines 975-1100)
- [ ] Add status: ⏳ PARTIAL
- [ ] Verify schemas match actual JSON files
- [ ] Note which schemas are fully implemented

---

## NEW SECTIONS TO ADD

### Status Effects System (NOT IN V5)
- [ ] ADD entire section from status_effect.py (827 lines)
- [ ] Document: DoT effects (Burn, Bleed, Poison, Shock)
- [ ] Document: CC effects (Freeze, Slow, Stun, Root)
- [ ] Document: Buffs (Regeneration, Shield, Haste, Empower)
- [ ] Document: Debuffs (Weaken, Vulnerable)

### Tag System (NOT IN V5)
- [ ] ADD section documenting effect_executor.py tag system
- [ ] Document tag categories: geometry, damage, status, context, trigger

### Save System (NOT IN V5)
- [ ] ADD section documenting save_manager.py
- [ ] List all saved data categories

### Unimplemented Features (NEW)
- [ ] ADD section listing features that are 🔮 PLANNED:
  - Block/Parry mechanics
  - Summon mechanics
  - LLM content generation
  - Skill evolution
  - Text-based value lookup

---

## CHANGES SUMMARY

### By Status:
- **✅ IMPLEMENTED**: ~60% of V5 content
- **⏳ PARTIAL**: ~25% of V5 content
- **🔮 PLANNED**: ~15% of V5 content

### New V6 Content:
1. Skill affinity system documentation
2. Tag-driven class system
3. Tool efficiency bonuses by class
4. Class/tool tooltips
5. Status effects system
6. Tag system for combat
7. Save system details
8. Enchantment combat integration
9. Implementation status markers throughout

### Preserved from V5:
- ALL 60 material narratives
- Element template system
- Text-based value system design
- Chunk template specifications
- Crafting minigame designs
- Vision and philosophy sections
