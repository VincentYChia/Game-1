# Documentation Archiving Recommendations

**Created**: January 27, 2026
**Purpose**: Evidence-based recommendations for which documents should be archived
**Philosophy**: Archive, don't delete - preserve history while reducing clutter

---

## Summary

Based on code-level audit of the repository, the following documents are recommended for archiving:

| Priority | File | Reason | Evidence |
|----------|------|--------|----------|
| HIGH | `/CRAFTING_LLM_INTEGRATION_PLAN.md` | Implementation complete | LLM system in production |
| HIGH | `/CRAFTING_FIX_PLAN.md` | Fixes implemented | Git commits confirm |
| MEDIUM | `/PROJECT_TIMELINE_ANALYSIS.md` | Historical reference | Covers Oct-Dec 2025 only |

---

## Detailed Recommendations

### 1. CRAFTING_LLM_INTEGRATION_PLAN.md

**Location**: `/home/user/Game-1/CRAFTING_LLM_INTEGRATION_PLAN.md`
**Size**: 35,701 bytes (997 lines)
**Created**: January 25, 2026

**Recommendation**: ARCHIVE

**Evidence**:
1. The plan describes integrating 5 classifiers (2 CNN + 3 LightGBM) - **DONE**
   - `systems/crafting_classifier.py` exists (1,256 lines)
   - All 5 classifiers are operational

2. LLM item generation via Claude API - **DONE**
   - `systems/llm_item_generator.py` exists (1,393 lines)
   - API integration working, debug logs in `llm_debug_logs/`

3. Save system extension for invented recipes - **DONE**
   - `character.invented_recipes` implemented
   - Persistence working across save/load

**Git Evidence**:
```
git log --oneline --since="Jan 25" -- "systems/llm_item_generator.py"
# Shows commits implementing this plan
```

**Archive Path**: `archive/cleanup-jan-2026/CRAFTING_LLM_INTEGRATION_PLAN.md`

---

### 2. CRAFTING_FIX_PLAN.md

**Location**: `/home/user/Game-1/CRAFTING_FIX_PLAN.md`
**Size**: 20,051 bytes (572 lines)
**Created**: ~January 2026

**Recommendation**: ARCHIVE

**Evidence**:
1. Issue 1 (Material Consumption) - **FIXED**
   - Commits show consumption logic resolved

2. Issue 2 (Minigame Difficulty) - **FIXED**
   - `difficulty_calculator.py` implemented (803 lines)
   - `reward_calculator.py` implemented (608 lines)
   - All discipline-specific calculations working

3. Speed Bonus mechanics - **IMPLEMENTED**
   - Each discipline has correct speed bonus application

4. Enchanting bug (UnboundLocalError) - **FIXED**
   - But note: `import random` still missing (separate issue)

**Git Evidence**:
```
git log --oneline | grep -i "crafting.*fix"
# Shows: "feat: Implement comprehensive crafting system fixes (Phase 1-2)"
```

**Archive Path**: `archive/cleanup-jan-2026/CRAFTING_FIX_PLAN.md`

---

### 3. PROJECT_TIMELINE_ANALYSIS.md

**Location**: `/home/user/Game-1/PROJECT_TIMELINE_ANALYSIS.md`
**Size**: 34,037 bytes (1,032 lines)
**Created**: ~December 2025

**Recommendation**: ARCHIVE (lower priority)

**Reason**: Historical analysis document covering October 19 - December 31, 2025. Useful for understanding project history but not for ongoing development.

**Content Summary**:
- Analyzes why project took 2.5 months
- Documents three development phases
- Explains the "Great Refactoring" of November 19
- Chronicles tag system implementation

**Value**: Historical reference only - no actionable items

**Archive Path**: `archive/cleanup-jan-2026/PROJECT_TIMELINE_ANALYSIS.md`

---

## Documents to KEEP (Not Archive)

The following documents should remain active:

### Primary References
| Document | Reason to Keep |
|----------|----------------|
| `.claude/CLAUDE.md` | Active developer guide (just updated) |
| `docs/GAME_MECHANICS_V6.md` | Master reference (needs minor updates) |
| `MASTER_ISSUE_TRACKER.md` | Active issue tracking |
| `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md` | Current status (just created) |

### Tag System
| Document | Reason to Keep |
|----------|----------------|
| `docs/tag-system/TAG-GUIDE.md` | Active reference |
| `docs/tag-system/TAG-DEFINITIONS-PHASE2.md` | Tag specifications |
| `docs/tag-system/TAG-COMBINATIONS-EXAMPLES.md` | Examples still valid |

### Development Guides
| Document | Reason to Keep |
|----------|----------------|
| `docs/ARCHITECTURE.md` | System architecture |
| `docs/DEVELOPMENT_GUIDE.md` | Development workflow |
| `docs/MODULE_REFERENCE.md` | Module documentation |
| `docs/DEVELOPER_GUIDE_JSON_INTEGRATION.md` | JSON integration |

### LLM System (NEW)
| Document | Reason to Keep |
|----------|----------------|
| `Fewshot_llm/README.md` | LLM system overview |
| `Fewshot_llm/MANUAL_TUNING_GUIDE.md` | Prompt editing |
| `Fewshot_llm/PROJECT_STRUCTURE.md` | System architecture |

---

## Documents Needing Updates (Not Archive)

These documents are outdated but should be UPDATED, not archived:

### GAME_MECHANICS_V6.md

**Issue**: Missing LLM integration section
**Action**: Add section covering:
- LLM item generation system
- Crafting classifiers
- Invented recipes persistence

### DOCUMENTATION_INDEX.md

**Issue**: Doesn't list new documents
**Action**: Add entries for:
- `docs/REPOSITORY_STATUS_REPORT_2026-01-27.md`
- `docs/INTERN_DOCUMENTATION_CLEANUP_PLAN.md`
- `docs/ARCHIVING_RECOMMENDATIONS.md`

### MASTER_ISSUE_TRACKER.md

**Issue**: Missing critical bug
**Action**: Add entry for:
- Missing `import random` in `enchanting.py`

---

## Already Archived (87 files)

The following are already in `archive/`:

| Subdirectory | Files | Content |
|--------------|-------|---------|
| `batch-notes/` | 4 | Implementation notes (Batch 1-4) |
| `tag-system-old/` | 27 | Historical tag system docs |
| `claude-context-nov-17/` | 7 | November 2025 context |
| `cleanup-dec-31/` | 5 | December 2025 cleanup |
| `cleanup-jan-2026/` | 8 | January 2026 cleanup |
| `planning/` | 5 | Historical planning docs |
| `old-summaries/` | 11 | Completion reports |
| Other | 20 | Various historical docs |

**Do not modify these** - they preserve project history.

---

## Archiving Procedure

### Step 1: Create Archive Commit
```bash
# Ensure clean working directory
git status

# Move files
git mv /home/user/Game-1/CRAFTING_LLM_INTEGRATION_PLAN.md /home/user/Game-1/archive/cleanup-jan-2026/
git mv /home/user/Game-1/CRAFTING_FIX_PLAN.md /home/user/Game-1/archive/cleanup-jan-2026/
git mv /home/user/Game-1/PROJECT_TIMELINE_ANALYSIS.md /home/user/Game-1/archive/cleanup-jan-2026/
```

### Step 2: Update Any References
Search for references to archived files and update them:
```bash
grep -r "CRAFTING_LLM_INTEGRATION_PLAN" --include="*.md"
grep -r "CRAFTING_FIX_PLAN" --include="*.md"
grep -r "PROJECT_TIMELINE_ANALYSIS" --include="*.md"
```

### Step 3: Commit
```bash
git commit -m "docs: Archive completed planning documents

Moved to archive/cleanup-jan-2026/:
- CRAFTING_LLM_INTEGRATION_PLAN.md (implementation complete)
- CRAFTING_FIX_PLAN.md (fixes implemented)
- PROJECT_TIMELINE_ANALYSIS.md (historical reference)

See docs/ARCHIVING_RECOMMENDATIONS.md for justification."
```

---

## Future Archiving Criteria

When evaluating documents for archiving in the future, use these criteria:

### Archive If:
- [x] Describes a one-time implementation task that is complete
- [x] Superseded by a newer version (e.g., V5 → V6)
- [x] Historical analysis with no ongoing relevance
- [x] Bug report for a fixed bug (older than 2 weeks)
- [x] Planning document for completed work

### Keep If:
- [ ] Active reference documentation
- [ ] Contains information not documented elsewhere
- [ ] Still has actionable items
- [ ] Describes current system behavior
- [ ] Frequently referenced by other documents

---

**End of Recommendations**
