# Intern Documentation Cleanup Plan

**Created**: January 27, 2026
**Purpose**: Step-by-step guide for comprehensive documentation review and cleanup
**Prerequisites**: Python familiarity, no Game-1 specific knowledge required

---

## Overview

This plan guides you through reviewing and updating the Game-1 documentation. The repository has 155 markdown files, with 87 already archived. Your goal is to ensure documentation accurately reflects the current codebase.

**Time Estimate**: 2-3 days for full review
**Priority Order**: Critical → High → Medium → Low

---

## Phase 1: Orientation (30 minutes)

### Step 1.1: Read Key Documents
Read these documents in order to understand the project:

1. **`.claude/CLAUDE.md`** - Developer guide (just updated, reflects current state)
2. **`docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`** - Comprehensive current status
3. **`MASTER_ISSUE_TRACKER.md`** - Known bugs and improvements

### Step 1.2: Understand the Codebase Structure
```
Game-1/
├── Game-1-modular/     # Main game code (136 Python files)
├── Scaled JSON Development/  # ML/LLM systems (39 Python files)
├── archive/            # Historical docs (87 files) - DO NOT MODIFY
└── .claude/            # AI assistant guides
```

### Step 1.3: Verify You Can Run the Game
```bash
cd Game-1-modular
python main.py
```
If this fails, note the error - it may indicate a documentation issue.

---

## Phase 2: Critical Bug Fix (10 minutes)

### Task 2.1: Fix Missing Import
**File**: `Game-1-modular/Crafting-subdisciplines/enchanting.py`
**Issue**: Missing `import random` - will cause crash on spinning wheel minigame

**Action**: Add `import random` at the top of the file (around line 32, with other imports)

### Task 2.2: Test the Fix
Run the game, enter a crafting station, select enchanting, verify it doesn't crash.

---

## Phase 3: Documentation Accuracy Review (4-6 hours)

### Step 3.1: Compare GAME_MECHANICS_V6.md Against Code

**File**: `Game-1-modular/docs/GAME_MECHANICS_V6.md` (5,089 lines)

This is the master reference but was last updated December 31, 2025. Check these sections:

| Section | Compare Against | What to Check |
|---------|-----------------|---------------|
| "LLM Integration" | `systems/llm_item_generator.py` | Is it documented? (Currently NOT in V6) |
| "Crafting System" | `Crafting-subdisciplines/*.py` | Do line counts match? |
| "Combat System" | `Combat/combat_manager.py` | Are all enchantments listed? |
| "Status Effects" | `entities/status_effect.py` | Are all 13 effects listed? |
| "Implementation Status" markers | Actual code | Are ✅/⏳/🔮 accurate? |

**Actions**:
1. For each section, verify claims against actual code
2. Note discrepancies in a separate file
3. Update incorrect information

### Step 3.2: Verify Feature Claims

For each feature marked "✅ IMPLEMENTED", verify it exists:

```python
# Example verification approach
# Open Python in Game-1-modular directory
import sys
sys.path.insert(0, '.')

# Test: Does LLM generator exist?
from systems.llm_item_generator import LLMItemGenerator
print("LLM generator exists:", LLMItemGenerator is not None)

# Test: Does crafting classifier exist?
from systems.crafting_classifier import CraftingClassifierManager
print("Classifier exists:", CraftingClassifierManager is not None)
```

### Step 3.3: Check Line Counts

The status report claims specific line counts. Verify key ones:

```bash
# Verify line counts
wc -l Game-1-modular/core/game_engine.py
# Should be ~7,817 lines

wc -l Game-1-modular/systems/llm_item_generator.py
# Should be ~1,393 lines

wc -l Game-1-modular/Combat/combat_manager.py
# Should be ~1,655 lines
```

---

## Phase 4: Document Staleness Check (2-3 hours)

### Step 4.1: Check Document Dates

For each document in `Game-1-modular/docs/`, check:
1. "Last Updated" date in the file
2. Compare against git history: `git log -1 --format="%ai" -- "path/to/file"`

### Step 4.2: Staleness Criteria

Mark documents as **STALE** if:
- Last updated > 2 weeks ago AND
- References features that have changed (check git commits)

Mark documents as **ARCHIVE CANDIDATE** if:
- Describes a completed one-time task (e.g., "MIGRATION_PLAN.md")
- Superseded by another document
- Historical reference only

### Step 4.3: Create Staleness Report

Create a file listing all stale documents with reasons:

```markdown
# Documentation Staleness Report
**Date**: [TODAY]

## Stale Documents (Need Update)
| File | Last Updated | Issue |
|------|--------------|-------|
| example.md | Dec 15, 2025 | Missing LLM section |

## Archive Candidates
| File | Reason |
|------|--------|
| CRAFTING_FIX_PLAN.md | Implementation complete |
```

---

## Phase 5: Cross-Reference Check (1-2 hours)

### Step 5.1: Check Internal Links

Many documents reference other documents. Verify links work:

```bash
# Find all markdown links
grep -rh "\[.*\](.*\.md)" Game-1-modular/docs/ | sort | uniq

# Check each link target exists
```

### Step 5.2: Check Code References

Documents reference code locations (e.g., "line 349 of game_engine.py"). Verify:

```bash
# Example: Check if combat_manager.py:758 mentions enchantments
sed -n '755,760p' Game-1-modular/Combat/combat_manager.py
```

---

## Phase 6: Specific Document Reviews

### Step 6.1: MASTER_ISSUE_TRACKER.md

**Check each issue**:
1. Is it still valid?
2. Has it been fixed? (Check git log)
3. Are line number references accurate?

**Add new issues found during review**

### Step 6.2: Tag System Documentation

**Files**: `Game-1-modular/docs/tag-system/*.md`

Verify:
1. All listed tags exist in `Definitions.JSON/tag-definitions.JSON`
2. Tag examples work as described
3. No undocumented tags in JSON

### Step 6.3: Module Reference

**File**: `Game-1-modular/docs/MODULE_REFERENCE.md`

For each module listed:
1. Verify file exists at stated path
2. Check class/method names are accurate
3. Update any renamed/moved items

---

## Phase 7: Clean Up Actions (1-2 hours)

### Step 7.1: Remove Unused Imports

**Files to clean** (found during audit):

```bash
# In Crafting-subdisciplines/*.py, remove unused imports:
# - `from pathlib import Path` (in 6 files)
# - `import copy` (in engineering.py only)
```

### Step 7.2: Update Documentation Index

**File**: `Game-1-modular/DOCUMENTATION_INDEX.md`

Add missing documents:
- `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`
- Reference to `Scaled JSON Development/LLM Training Data/Fewshot_llm/README.md`

### Step 7.3: Archive Completed Planning Docs

Move these to `archive/cleanup-jan-2026/`:
1. `/CRAFTING_LLM_INTEGRATION_PLAN.md`
2. `/CRAFTING_FIX_PLAN.md`
3. `/PROJECT_TIMELINE_ANALYSIS.md`

**Use git mv to preserve history**:
```bash
git mv CRAFTING_LLM_INTEGRATION_PLAN.md archive/cleanup-jan-2026/
git mv CRAFTING_FIX_PLAN.md archive/cleanup-jan-2026/
git mv PROJECT_TIMELINE_ANALYSIS.md archive/cleanup-jan-2026/
```

---

## Phase 8: Final Verification (30 minutes)

### Step 8.1: Run Game Test
```bash
cd Game-1-modular
python main.py
```

Verify:
- Game launches without errors
- Can access crafting stations
- Enchanting spinning wheel works (after random import fix)

### Step 8.2: Run Tests
```bash
python -m pytest tests/ -v
```

Note any failures.

### Step 8.3: Commit Changes

```bash
git add -A
git commit -m "docs: Comprehensive documentation review and cleanup

- Fixed missing import random in enchanting.py
- Updated DOCUMENTATION_INDEX.md
- Removed unused imports from crafting files
- Archived completed planning documents
- Created staleness report

Reviewed by: [YOUR NAME]"
```

---

## Checklist Summary

Use this checklist to track progress:

- [ ] Phase 1: Orientation complete
- [ ] Phase 2: Critical bug fixed (random import)
- [ ] Phase 3: GAME_MECHANICS_V6.md reviewed
- [ ] Phase 4: Staleness report created
- [ ] Phase 5: Cross-references verified
- [ ] Phase 6.1: MASTER_ISSUE_TRACKER reviewed
- [ ] Phase 6.2: Tag system docs verified
- [ ] Phase 6.3: MODULE_REFERENCE verified
- [ ] Phase 7.1: Unused imports removed
- [ ] Phase 7.2: Documentation index updated
- [ ] Phase 7.3: Planning docs archived
- [ ] Phase 8: Final verification passed

---

## Questions to Ask If Stuck

1. **"Is this feature implemented?"** → Check if the Python file/class exists
2. **"Is this line number accurate?"** → Use `sed -n 'Xp' file` to check
3. **"Should this be archived?"** → If it's a completed plan, yes
4. **"Is this outdated?"** → Compare git commit date to content claims

---

## Contact

If you encounter issues or have questions:
1. Check `MASTER_ISSUE_TRACKER.md` first
2. Look for TODO comments in the relevant code
3. Ask the project maintainer

---

**Good luck! Your work helps keep this project maintainable.**
