# Tag System Documentation Index

**Quick Start:** Read TAG-REFERENCE.md (tabular format, ~15 min)

---

## Documentation Structure

### 📖 Quick Reference (START HERE)
**TAG-REFERENCE.md** - Condensed tables, fast lookup
- Equipment tags (1H, 2H, versatile)
- Geometry tags with parameters (chain, cone, circle, beam)
- Damage types (physical, fire, frost, etc.)
- Status effects (burn, freeze, slow, etc.)
- Special mechanics (lifesteal, knockback, etc.)
- Common combinations
- Migration quick guide
- **~4000 words, tabular format**

### 📚 Detailed References
**TAG-DEFINITIONS-PHASE2.md** - Complete specifications (~18K words)
- Every tag defined in detail
- Implementation pseudocode
- Context-aware behavior
- Visual indicators
- **Use when:** Need implementation details

**TAG-COMBINATIONS-EXAMPLES.md** - Real-world examples (~8K words)
- 50+ combination examples
- Before/after conversions
- Edge cases
- **Use when:** Converting existing items

**MIGRATION-GUIDE.md** - Step-by-step migration (~6K words)
- Conversion process
- Validation scripts
- Testing strategy
- **Use when:** Actually migrating JSONs

### 📊 Data Files
**tag-inventory.json** - Machine-readable tag data
- All 190 current tags
- Usage locations
- Categories
- **Use with:** tag_collector.py

**tag-inventory.txt** - Human-readable inventory
- Full tag list with occurrences
- Categorization
- Potential typos
- **Use for:** Review and auditing

### 🔧 Tools
**tools/tag_collector.py** - Tag inventory tool
- Scans all JSONs
- Extracts tags
- Detects typos
- Generates reports

---

## Reading Paths

### For Developers (Implementing System)
1. **TAG-REFERENCE.md** - Understand tag vocabulary
2. **TAG-DEFINITIONS-PHASE2.md** - Implementation details
3. **PHASE2-SUMMARY.md** - Architecture overview
4. Start coding Phase 3

### For Content Creators (Converting JSONs)
1. **TAG-REFERENCE.md** - Quick tag lookup
2. **MIGRATION-GUIDE.md** - Conversion steps
3. **TAG-COMBINATIONS-EXAMPLES.md** - Real examples
4. Use validate_tags.py

### For Quick Lookup
1. **TAG-REFERENCE.md** - Tables section
2. Done!

---

## Phase Overview

### ✅ Phase 1: Analysis (COMPLETE)
- TAG-ANALYSIS-PHASE1.md
- tag-inventory.txt/json
- tag_collector.py

**Discovered:** 190 tags, only 3 functional, massive gaps

### ✅ Phase 2: Design (COMPLETE)
- TAG-REFERENCE.md ⭐ Quick lookup
- TAG-DEFINITIONS-PHASE2.md (detailed)
- TAG-COMBINATIONS-EXAMPLES.md (examples)
- MIGRATION-GUIDE.md (how-to)
- PHASE2-SUMMARY.md (overview)

**Defined:** 80+ functional tags, parameters, combinations

### 🔄 Phase 3: Implementation (NEXT)
- Core systems (registry, parser, geometry, status)
- Integration (turrets, combat, skills)
- Testing

---

## Tag Categories Quick Reference

| Category | Tags | File Section |
|----------|------|--------------|
| Equipment | 3 tags | TAG-REFERENCE.md#equipment-tags |
| Geometry | 9 tags | TAG-REFERENCE.md#geometry-tags |
| Damage Types | 15 tags | TAG-REFERENCE.md#damage-types |
| Status Effects | 22 tags | TAG-REFERENCE.md#status-effects |
| Special Mechanics | 15 tags | TAG-REFERENCE.md#special-mechanics |
| Context/Triggers | 17 tags | TAG-REFERENCE.md#context--triggers |

**Total Functional Tags:** 80+

---

## Common Questions

**Q: What does the "chain" tag do?**
A: TAG-REFERENCE.md#geometry-tags → chain row

**Q: How do I convert "Fires lightning bolts, 70 damage + chain"?**
A: TAG-REFERENCE.md#migration-quick-guide

**Q: What if tags conflict (chain + cone)?**
A: TAG-REFERENCE.md#conflict-resolution

**Q: What are default parameters?**
A: TAG-REFERENCE.md#default-parameters

**Q: How does context-aware work?**
A: TAG-REFERENCE.md#context-aware-behavior-examples

**Q: Need implementation details?**
A: TAG-DEFINITIONS-PHASE2.md

---

## Current Status

**Phase:** 2 Complete, 3 Next
**Functional Tags Defined:** 80+
**Documentation:** ~35K words (condensed to TAG-REFERENCE for quick access)
**Tools:** tag_collector.py
**Ready For:** Implementation

---

## File Sizes (Reference)

```
TAG-REFERENCE.md           ~4K words   ← START HERE
TAG-DEFINITIONS-PHASE2.md  ~18K words  ← Details
TAG-COMBINATIONS.md        ~8K words   ← Examples
MIGRATION-GUIDE.md         ~6K words   ← Migration
PHASE2-SUMMARY.md          ~2K words   ← Overview
INDEX.md                   This file   ← Navigation
```

---

**Last Updated:** 2025-12-15
**Version:** 1.0
