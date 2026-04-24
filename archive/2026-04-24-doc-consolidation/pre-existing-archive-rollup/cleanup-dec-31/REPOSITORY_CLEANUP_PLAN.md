# 🧹 Repository Cleanup & Reorganization Plan

**Created:** December 31, 2025
**Repository:** Game-1
**Current Size:** ~365MB (280MB is duplicate assets)
**Goal:** Reduce size by 75%, improve organization, establish clear structure

---

## Executive Summary

The repository is **functionally well-organized** with excellent modular architecture and comprehensive documentation, but suffers from:
- **280MB+ of duplicate icon assets** (78% of total asset size)
- Test files scattered at root level instead of dedicated directory
- Multiple archive directories with unclear purposes
- JSON file duplication across directories
- Documentation sprawl across multiple locations

**Expected Impact:**
- Free up **~280MB** of disk space (75% reduction)
- Reduce file count from **2,951** to **~670** files
- Improve developer onboarding and navigation
- Establish clear organizational standards

---

## 📊 Current State Analysis

### Repository Statistics
| Metric | Value |
|--------|-------|
| Total files (excluding .git) | 2,951 |
| Total size | ~365MB |
| Python files | 121 |
| JSON files | 52 |
| PNG assets | 2,570 |
| Markdown docs | 118 |
| Test files | 20 |

### Directory Sizes
| Directory | Size | Status |
|-----------|------|--------|
| `assets/` | 361MB | **280MB duplicates** |
| `archive/` (root) | 2.3MB | Needs consolidation |
| `Game-1-modular/archive/` | 605KB | Needs consolidation |
| Code directories | ~5MB | Well organized ✅ |

### Asset Duplication Breakdown
```
assets/
├── generated_icons-2/          37MB  ← DUPLICATE (appears in cycles 1-4)
├── generated_icons-3/          36MB  ← DUPLICATE (appears in cycles 1-4)
├── icons-generated-cycle-1/    42MB  ← OLD (contains duplicates)
├── icons-generated-cycle-2/    57MB  ← OLD (contains duplicates)
├── icons-generated-cycle-3/    74MB  ← OLD (contains duplicates)
├── icons-generated-cycle-4/    70MB  ← CURRENT (keep this one)
└── [other assets]              45MB  ← Keep (custom icons, organized items)
```

**Wasted space:** ~280MB from duplicate icon directories

---

## 🎯 Cleanup Protocol - 4 Priority Levels

## PRIORITY 1: CRITICAL - Free 280MB (Asset Deduplication)

### ❌ DELETE: Duplicate Icon Directories

**Actions:**
1. **Archive old icon generation cycles** (cycles 1-3 are superseded by cycle-4)
   ```bash
   # Create archive outside repository
   mkdir -p ../Game-1-archived-assets/icon-cycles-1-3/
   mv Game-1-modular/assets/icons-generated-cycle-1/ ../Game-1-archived-assets/icon-cycles-1-3/
   mv Game-1-modular/assets/icons-generated-cycle-2/ ../Game-1-archived-assets/icon-cycles-1-3/
   mv Game-1-modular/assets/icons-generated-cycle-3/ ../Game-1-archived-assets/icon-cycles-1-3/
   ```

2. **Remove root-level duplicate directories** (already in cycle-4)
   ```bash
   rm -rf Game-1-modular/assets/generated_icons-2/
   rm -rf Game-1-modular/assets/generated_icons-3/
   ```

3. **Update documentation** to reference only `icons-generated-cycle-4/`

**Space Saved:** ~280MB (75% of assets directory)
**Risk Level:** Low (old cycles are superseded, duplicates confirmed)
**Validation Required:**
- ✅ Verify `icons-generated-cycle-4/` contains all needed icons
- ✅ Check no code references deleted directories
- ✅ Test icon loading after deletion

---

## PRIORITY 2: HIGH - Improve Organization

### 🗂️ Task 2.1: Create Proper Test Directory Structure

**Current Problem:** 12 test files scattered at `/Game-1-modular/` root level

**New Structure:**
```
Game-1-modular/
└── tests/
    ├── __init__.py
    ├── integration/
    │   ├── test_chain_harvest.py
    │   ├── test_class_tags.py
    │   ├── test_crafting_stats.py
    │   ├── test_durability.py
    │   ├── test_encyclopedia_integration.py
    │   ├── test_quest_integration.py
    │   ├── test_stat_modifiers.py
    │   └── test_weight_calculations.py
    ├── crafting/
    │   ├── test_alchemy_integration.py
    │   ├── test_enchanting_patterns.py
    │   ├── test_smithing_grid.py
    │   └── test_unified_crafting.py
    └── README.md  # How to run tests
```

**Actions:**
1. Create `tests/` directory structure
2. Move all `test_*.py` files from root to appropriate subdirectories
3. Create test runner documentation
4. Update any import paths in test files
5. Add pytest configuration if needed

**Benefits:**
- Clear separation of test code from production code
- Easy to run all tests: `pytest tests/`
- Professional project structure
- Better IDE support for testing

---

### 🗂️ Task 2.2: Remove JSON File Duplicates

**Current Problem:** `Update-1/` directory contains duplicates of files in main directories

**Duplicates Identified:**
| File in Update-1/ | Also exists in | Action |
|-------------------|----------------|--------|
| `items-testing-integration.JSON` | `items.JSON/` | ❌ Delete from Update-1 |
| `skills-testing-integration.JSON` | `Skills/` + `Definitions.JSON/` | ❌ Delete from Update-1 |
| `hostiles-testing-integration.JSON` | `Definitions.JSON/` | ❌ Delete from Update-1 |
| `recipes-smithing-testing.JSON` | `recipes.JSON/` | ✅ Keep if unique test data |

**Actions:**
1. Compare file contents to verify they're identical duplicates
2. If identical: delete from `Update-1/`, update references to point to canonical location
3. If different: rename to clarify purpose (e.g., `items-testing-UNIQUE.JSON`)
4. Document the purpose of `Update-1/` directory in its README

**Decision Point:**
- **Option A:** Delete `Update-1/` entirely if it's just an old test directory
- **Option B:** Keep it but remove duplicates and clarify its purpose
- **Recommendation:** Review with developer to understand intent before deletion

---

### 🗂️ Task 2.3: Rename Data Directories (Remove Misleading Extensions)

**Current Problem:** Directories have `.JSON` extension, making them look like files

**Renames:**
```bash
# Before                      # After
items.JSON/          →        items/
recipes.JSON/        →        recipes/
placements.JSON/     →        placements/
```

**Actions:**
1. Rename directories
2. Update all code references (grep for old names)
3. Update documentation
4. Commit with clear message about path changes

**Benefits:**
- Clearer that these are directories, not files
- Follows standard naming conventions
- Reduces confusion for new developers

---

## PRIORITY 3: MEDIUM - Consolidate & Standardize

### 📚 Task 3.1: Consolidate Archive Directories

**Current Problem:** Two separate archive directories with unclear purposes

**Current State:**
- `/archive/` (2.3MB) - Old `Game-1-singular/` codebase + analysis docs
- `/Game-1-modular/archive/` (605KB) - Old documentation (43 markdown files)

**Proposed Structure:**
```
archive/
├── README.md                          # Purpose and contents guide
├── codebase/
│   └── Game-1-singular/              # Original 10,327-line monolithic version
│       └── main.py
├── documentation/
│   ├── old-summaries/                # 17 old summary files
│   ├── batch-implementation/         # 4 batch implementation notes
│   └── tag-system-old/               # 25 old tag system docs
└── assets/
    └── icon-cycles-1-3/              # Archived icon generation cycles
```

**Actions:**
1. Create unified archive structure at root level
2. Move `/Game-1-modular/archive/` contents to `/archive/documentation/`
3. Keep root `/archive/` as single source of historical artifacts
4. Add comprehensive README explaining what's archived and why
5. Consider compressing archive to tarball: `archive.tar.gz`

**Benefits:**
- Single location for all archived materials
- Clear separation of active vs. historical
- Optional compression for further space savings

---

### 📚 Task 3.2: Centralize Documentation

**Current Problem:** 118 markdown files spread across multiple locations

**Documentation Sprawl:**
| Location | Files | Purpose |
|----------|-------|---------|
| `/Game-1-modular/docs/` | 24 | ✅ Active system documentation |
| `/Game-1-modular/` (root) | ~15 | Planning, tracking, guides |
| `/Game-1-modular/Crafting-subdisciplines/` | 2 | Design docs |
| `/Game-1-modular/archive/` | 43 | Old documentation |
| `/archive/` | ~15 | Analysis and summaries |
| `/claude-context/` | 7 | Claude AI integration docs |

**Proposed Structure:**
```
docs/
├── README.md                              # Documentation index
├── architecture/
│   ├── ARCHITECTURE.md
│   ├── MODULE_REFERENCE.md
│   ├── NAMING_CONVENTIONS.md
│   └── REFACTORING_SUMMARY.md
├── game-design/
│   ├── GAME_MECHANICS_V6.md
│   ├── FEATURES_CHECKLIST.md
│   ├── crafting/
│   │   ├── SIMPLIFIED_RARITY_SYSTEM.md
│   │   └── STAT_MODIFIER_DESIGN.md
│   └── systems/
│       ├── DURABILITY_WEIGHT_REPAIR_PLAN.md
│       └── SKILL-SYSTEM-HANDOFF.md
├── guides/
│   ├── DEVELOPMENT_GUIDE.md
│   ├── HOW_TO_RUN.md
│   └── testing/
│       └── [test documentation]
├── tracking/
│   ├── FEATURES_CHECKLIST.md
│   ├── KNOWN_LIMITATIONS.md
│   └── V6_UPDATE_PLAN.md
└── integrations/
    └── claude/                            # Claude AI context
        └── [7 context files]
```

**Actions:**
1. Create consolidated documentation structure in `/docs/`
2. Move active documentation to appropriate subdirectories
3. Archive old/outdated documentation
4. Create documentation index (README.md) with links
5. Update references in code and other docs

**Benefits:**
- Single source of truth for documentation
- Easy navigation by topic
- Clear distinction between design, implementation, and guides
- Better onboarding for new developers

---

### 📝 Task 3.3: Add Missing File Extensions

**Current Problem:** Some files lack extensions, making purpose unclear

**Files Needing Extensions:**
```
Definitions.JSON/JSON Templates                           → JSON-Templates.md
Definitions.JSON/Tentative 3 new templates JSONS         → Tentative-3-Templates.md
Crafting-subdisciplines/Crafting reference               → Crafting-reference.md
```

**Actions:**
1. Add appropriate extensions (.md, .txt, .json)
2. Update any references to these files
3. Verify git tracks the renames properly

**Benefits:**
- Clear file types
- Proper syntax highlighting in editors
- Better file searching and filtering

---

## PRIORITY 4: LOW - Polish & Cleanup

### 🧹 Task 4.1: Review Orphaned Files

**Files to Review:**
- `Crafting-subdisciplines/smithing-crafting.html` - Purpose unclear
- `Scaled JSON Development/` - Still needed?
- `.idea/` - IDE config (should be in .gitignore)

**Actions:**
1. Verify `smithing-crafting.html` is still used
   - If design mockup: move to `/docs/game-design/crafting/`
   - If tool output: move to `/tools/` or delete
   - If obsolete: delete

2. Evaluate `Scaled JSON Development/`
   - If superseded by `/tools/json_generators/`: archive or delete
   - If still used: move to `/tools/` and clarify purpose

3. Add `.idea/` to `.gitignore` if not already present
   - IDE configs are personal and shouldn't be in repo

---

### 📋 Task 4.2: Prune Outdated Planning Documents

**Review for Archival/Deletion:**
Root-level planning documents may be outdated:
- Various tracking markdown files
- Old planning documents superseded by current docs

**Actions:**
1. Review each root-level .md file
2. Determine if still relevant or superseded
3. Archive outdated planning docs
4. Keep only active tracking documents at root (README, HOW_TO_RUN, etc.)
5. Move historical planning to `/archive/documentation/planning/`

---

### 🔍 Task 4.3: Update .gitignore

**Add Standard Ignores:**
```gitignore
# IDE
.idea/
.vscode/
*.swp
*.swo

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/

# OS
.DS_Store
Thumbs.db
*.tmp

# Game-specific
*.log
saves/*.sav
```

**Actions:**
1. Update `.gitignore` with comprehensive rules
2. Remove tracked files that should be ignored
3. Verify no sensitive data in repository

---

## 🎯 Implementation Phases

### Phase 1: Asset Cleanup (Immediate - High Impact)
**Duration:** 30 minutes
**Impact:** Free 280MB, 75% size reduction

1. ✅ Verify `icons-generated-cycle-4/` has all needed icons
2. ✅ Archive cycles 1-3 outside repository
3. ✅ Delete root-level duplicate directories
4. ✅ Test icon loading functionality
5. ✅ Commit changes

### Phase 2: Structure (1-2 hours)
**Impact:** Professional organization, better navigation

1. ✅ Create `tests/` directory structure
2. ✅ Move test files from root
3. ✅ Remove JSON file duplicates
4. ✅ Rename data directories (remove .JSON extensions)
5. ✅ Update code references
6. ✅ Commit changes

### Phase 3: Consolidation (2-3 hours)
**Impact:** Single source of truth for archives and docs

1. ✅ Consolidate archive directories
2. ✅ Centralize documentation
3. ✅ Add file extensions
4. ✅ Create documentation index
5. ✅ Commit changes

### Phase 4: Polish (1 hour)
**Impact:** Professional finish

1. ✅ Review and move orphaned files
2. ✅ Archive outdated planning docs
3. ✅ Update .gitignore
4. ✅ Final review and commit

**Total Time:** 4.5 - 6.5 hours
**Total Impact:** 280MB freed, ~2,280 files removed, clear organization

---

## ✅ Validation Checklist

After each phase, verify:

### Functionality Tests
- [ ] Game launches successfully: `python Game-1-modular/main.py`
- [ ] All icons load correctly
- [ ] No import errors or missing files
- [ ] Save/load functionality works
- [ ] All crafting disciplines load

### Code Quality Tests
- [ ] All Python files compile: `python -m py_compile Game-1-modular/**/*.py`
- [ ] No broken import references
- [ ] Tests still run: `pytest tests/`
- [ ] No dead symbolic links

### Repository Quality Tests
- [ ] No files >100MB (GitHub limit)
- [ ] .gitignore properly excludes build artifacts
- [ ] Documentation links are not broken
- [ ] README accurately describes structure

---

## 📐 Organizational Standards (Going Forward)

### Directory Structure Standards
```
Game-1-modular/
├── main.py                    # Entry point only
├── README.md                  # Overview and quick start
├── requirements.txt           # Dependencies
│
├── [source code modules]/     # All lowercase, no extensions
│   ├── core/
│   ├── entities/
│   ├── systems/
│   └── ...
│
├── [data directories]/        # All lowercase, no extensions
│   ├── items/
│   ├── recipes/
│   └── ...
│
├── tests/                     # All test files here
│   ├── unit/
│   └── integration/
│
├── tools/                     # Development utilities
│   └── json_generators/
│
├── docs/                      # All documentation here
│   ├── architecture/
│   ├── game-design/
│   └── guides/
│
└── assets/                    # Game assets
    ├── icons-generated-cycle-N/  # Keep only latest cycle
    ├── custom_icons/
    └── [organized by type]/
```

### File Naming Standards
- **Python files:** `lowercase_with_underscores.py`
- **JSON files:** `category-subcategory-version.JSON` (e.g., `items-smithing-2.JSON`)
- **Markdown docs:** `UPPERCASE_WITH_UNDERSCORES.md` (e.g., `GAME_MECHANICS_V6.md`)
- **Directories:** `lowercase-with-hyphens/` or `lowercase_with_underscores/`
- **All files have extensions** (no extension-less files)

### Documentation Standards
- Active documentation in `/docs/`
- Historical documentation in `/archive/documentation/`
- Each directory has README.md explaining its purpose
- Outdated docs are archived, not left in place

### Asset Management Standards
- Keep only latest icon generation cycle
- Archive old cycles outside repository or delete
- No duplicate assets in repository
- Asset registry tracks all icons and their sources

---

## 🚨 Risks & Mitigations

### Risk 1: Deleting needed icon assets
**Mitigation:**
- Archive old cycles outside repo (don't delete permanently)
- Test icon loading after cleanup
- Keep 7-day backup before cleanup

### Risk 2: Breaking code references to moved files
**Mitigation:**
- Use grep to find all references before moving
- Update all code and documentation references
- Run full test suite after changes
- Commit each phase separately for easy rollback

### Risk 3: Losing important documentation
**Mitigation:**
- Review each doc before archiving
- Archive (don't delete) questionable docs
- Create index of all archived materials
- Keep archive accessible

### Risk 4: Git history issues
**Mitigation:**
- Use `git mv` for renames (preserves history)
- Commit each phase separately with clear messages
- Don't force-push or rebase after pushing
- Keep backup branch before major changes

---

## 📊 Success Metrics

### Quantitative Goals
- ✅ **Size reduction:** 365MB → ~85MB (77% reduction)
- ✅ **File reduction:** 2,951 → ~670 files (77% reduction)
- ✅ **Test organization:** 0 → 1 dedicated test directory with all 20 tests
- ✅ **Documentation consolidation:** 118 files in 6 locations → ~80 files in 1 location
- ✅ **Zero duplicates:** All duplicate assets and JSON files removed

### Qualitative Goals
- ✅ **Developer onboarding:** New developers can understand structure in <10 minutes
- ✅ **Navigation speed:** Find any file in <30 seconds
- ✅ **Clear purpose:** Every directory has clear, documented purpose
- ✅ **Professional appearance:** Repo looks production-ready
- ✅ **Maintainability:** Easy to keep organized going forward

---

## 📝 Notes

### What This Cleanup IS:
- ✅ Removing duplicate assets
- ✅ Organizing files into logical structure
- ✅ Consolidating scattered documentation
- ✅ Establishing organizational standards
- ✅ Reducing repository size significantly

### What This Cleanup IS NOT:
- ❌ Changing code functionality
- ❌ Modifying game mechanics
- ❌ Removing active features
- ❌ Refactoring code architecture (already excellent)
- ❌ Changing version control history

### Key Strengths to Preserve:
The repository already has **excellent** qualities:
- ✅ Clean modular code architecture
- ✅ Well-separated concerns (core, entities, systems, data)
- ✅ Component-based character system
- ✅ Comprehensive documentation
- ✅ Good development tooling
- ✅ Clear data organization

This cleanup **builds on these strengths** by removing cruft and improving navigation.

---

## 🎓 Lessons for Future Development

### Asset Management
1. **Archive old assets immediately** when new versions are created
2. **Never duplicate assets** in repository - use symlinks or references
3. **Document asset pipelines** clearly (icon-selector.py, generators, etc.)
4. **Automate cleanup** as part of asset generation workflow

### Documentation Management
1. **One canonical location** for all active documentation
2. **Archive immediately** when docs become outdated
3. **Create indexes** so people can find docs easily
4. **Review quarterly** and prune outdated materials

### Testing Organization
1. **Tests in dedicated directory** from day one
2. **Mirror source structure** in test structure
3. **Separate unit from integration** tests
4. **Automate test running** in CI/CD

### Repository Hygiene
1. **Regular cleanup sprints** (quarterly or after major features)
2. **Size monitoring** (alert if repo >500MB)
3. **Duplicate detection** (automated tools)
4. **Clear file naming standards** enforced in reviews

---

**Created by:** Repository Analysis Agent
**Next Review:** After Phase 4 completion
**Maintainer:** Development Team
