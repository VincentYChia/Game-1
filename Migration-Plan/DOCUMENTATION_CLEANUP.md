# Documentation State & Cleanup Guide

**Date**: 2026-02-21
**Purpose**: Definitive map of all documentation, what's current vs stale, and the recommended reading order for any developer or AI assistant.

---

## 1. Document Inventory (31 Migration-Plan docs + 12 .claude/Python docs)

### Migration-Plan/ — Authoritative Status

| # | Document | Lines | Status | Role |
|---|----------|-------|--------|------|
| 1 | **COMPLETION_STATUS.md** | 212 | **CURRENT — NEEDS UPDATE** | Central hub. Start here. File count and phase status claims need correction. |
| 2 | **MIGRATION_PLAN.md** | 1,229 | **CURRENT** | Master plan (what was designed). Historical reference for original architecture. |
| 3 | **IMPROVEMENTS.md** | 1,424 | **CURRENT** | Architecture improvements. Still authoritative for what SHOULD exist. Note: not all improvements were implemented (ItemFactory, ConsumableItem, PlaceableItem). |
| 4 | **CONVENTIONS.md** | 709 | **CURRENT** | Coding standards. Apply to all new code. |
| 5 | **PHASE_CONTRACTS.md** | 641 | **CURRENT — REFERENCE ONLY** | Phase I/O contracts. Useful for understanding dependencies. Many DELIVERS were not actually created. |
| 6 | **MIGRATION_META_PLAN.md** | 1,075 | **HISTORICAL** | Pre-implementation methodology. Useful for understanding approach but not actionable. |
| 7 | **ADAPTIVE_CHANGES.md** | 244 | **CURRENT** | All 25 deviations from plan. Essential reading for understanding why code differs from specs. |
| 8 | **POST_MIGRATION_PLAN.md** | 1,011 | **CURRENT** | Step-by-step guide to get from "C# files" to "playable prototype." Most actionable document for next steps. |
| 9 | **UNITY_MIGRATION_CHECKLIST.md** | 330 | **CURRENT — NEEDS CORRECTIONS** | Hub pointing to 7 domain audits. Gap counts are broadly correct but contain false positives identified by META_AUDIT. |
| 10 | **MIGRATION_COMPLETION_REPORT.md** | 215 | **HISTORICAL** | Written Feb 14 after Phase 7. Claims 147 files and 468+ tests — both inflated. Treat as session-end snapshot, not ground truth. |
| 11 | **HANDOFF_PROMPT.md** | 253 | **SUPERSEDED** | Written for Phase 6 handoff. Phase 6 is done. No longer needed. |
| 12 | **MIGRATION_AUDIT_2026-02-16.md** | ~800 | **SUPERSEDED** | First audit pass. Superseded by the 7 domain audits (Feb 19) + META_AUDIT_REPORT. |
| 13 | **PHASE_5_IMPLEMENTATION_SUMMARY.md** | ~100 | **CURRENT — MISPLACED** | Should be in phases/ directory with the other implementation summaries. |
| 14 | **AUDIT_IMPROVEMENT_PLAN.md** | NEW | **CURRENT** | This PR. Comprehensive gap remediation plan with corrections. |
| 15 | **DOCUMENTATION_CLEANUP.md** | NEW | **CURRENT** | This file. Documentation map and cleanup guide. |

### Migration-Plan/audits/ — Domain Audits

| # | Document | Status | Key Corrections Needed |
|---|----------|--------|----------------------|
| 16 | **AUDIT_1_INFRASTRUCTURE.md** | **CURRENT** | SentisBackendFactory is mock, not "complete" |
| 17 | **AUDIT_2_COMBAT_AND_MOVEMENT.md** | **CURRENT — NEEDS REWRITE §2-3** | 6 false positives from interface confusion. DamageNumberRenderer understated. |
| 18 | **AUDIT_3_CRAFTING_AND_MINIGAMES.md** | **CURRENT — MINOR FIX** | §14 invented recipe UI claim unverified |
| 19 | **AUDIT_4_UI_SYSTEMS.md** | **CURRENT — 5 FIXES** | E key, L/J key, K key, quantity splitting, start menu button count |
| 20 | **AUDIT_5_WORLD_AND_PROGRESSION.md** | **CURRENT — 3 FIXES** | §18 invented recipes exist, §24 SaveMigrator exists, §28 NPC overstated |
| 21 | **AUDIT_6_3D_REQUIREMENTS.md** | **CURRENT — LABEL FIX** | 4 files labeled "COMPLETE" should be "STRUCTURALLY COMPLETE — NOT WIRED" |
| 22 | **AUDIT_7_TESTING_STRATEGY.md** | **CURRENT — COUNT FIX** | 119 tests not ~180; 24 PlayMode not 95+ |
| 23 | **META_AUDIT_REPORT.md** | **CURRENT** | Source of truth for audit accuracy. No corrections needed. |

### Migration-Plan/phases/ — Phase Documents

| # | Document | Status | Notes |
|---|----------|--------|-------|
| 24 | PHASE_1_FOUNDATION.md | **HISTORICAL** | Original spec. Some deliverables not created (ItemFactory, ConsumableItem, PlaceableItem). |
| 25 | PHASE_2_DATA_LAYER.md | **HISTORICAL** | Original spec. 5 of 14 planned databases not created. |
| 26 | PHASE_3_ENTITY_LAYER.md | **HISTORICAL** | Original spec. 10 files created of 22 planned (consolidation). |
| 27 | PHASE_3_IMPLEMENTATION_SUMMARY.md | **CURRENT** | What was actually built. Documents consolidation decisions. |
| 28 | PHASE_4_GAME_SYSTEMS.md | **HISTORICAL** | Original spec. InteractiveCrafting and DungeonSystem not created. |
| 29 | PHASE_4_IMPLEMENTATION_SUMMARY.md | **CURRENT** | What was actually built. Documents deferred items. |
| 30 | PHASE_5_ML_CLASSIFIERS.md | **HISTORICAL** | Original spec. |
| 31 | PHASE_6_UNITY_INTEGRATION.md | **HISTORICAL** | Original spec. PlayerController, SaveLoadUI, TitleUI, SkillUnlockUI not created. |
| 32 | PHASE_6_IMPLEMENTATION_SUMMARY.md | **CURRENT** | What was actually built. |
| 33 | PHASE_7_POLISH_AND_LLM_STUB.md | **HISTORICAL** | Original spec. |
| 34 | PHASE_7_IMPLEMENTATION_SUMMARY.md | **CURRENT** | What was actually built. |

### Migration-Plan/reference/

| # | Document | Status |
|---|----------|--------|
| 35 | UNITY_PRIMER.md | **CURRENT** — Unity crash course, still useful |
| 36 | PYTHON_TO_CSHARP.md | **CURRENT** — Type mappings, still useful |

### .claude/ — Project-Level Context

| # | Document | Status | Needed Update |
|---|----------|--------|--------------|
| 37 | CLAUDE.md | **STALE** | Last meaningful update Feb 11. Needs Unity migration status, accurate file counts, updated reading order. |
| 38 | INDEX.md | **STALE** | Last updated Jan 27. Predates entire migration. Needs complete rewrite. |
| 39 | NAMING_CONVENTIONS.md | **CURRENT for Python** | Python naming conventions still valid for Python source. C# conventions in CONVENTIONS.md. |

---

## 2. Recommended Reading Orders

### For a developer picking up the project fresh

1. `.claude/CLAUDE.md` — Project overview (note: some details are stale, but overall picture is correct)
2. `Migration-Plan/COMPLETION_STATUS.md` — What the migration plan was, what was built
3. `Migration-Plan/AUDIT_IMPROVEMENT_PLAN.md` — What's actually missing and what to do about it
4. `Migration-Plan/UNITY_MIGRATION_CHECKLIST.md` — Hub pointing to domain-specific gaps
5. `Migration-Plan/POST_MIGRATION_PLAN.md` — How to get to a playable prototype
6. `Migration-Plan/CONVENTIONS.md` — Before writing any C# code
7. The specific `audits/AUDIT_*.md` for your domain

### For someone fixing a specific audit gap

1. `Migration-Plan/audits/META_AUDIT_REPORT.md` — Know what's wrong with the audits
2. `Migration-Plan/AUDIT_IMPROVEMENT_PLAN.md` §2 — Specific corrections
3. The relevant `audits/AUDIT_*.md` — Detailed gap
4. `Migration-Plan/ADAPTIVE_CHANGES.md` — Why code may differ from plan

### For understanding what the migration plan was

1. `Migration-Plan/MIGRATION_PLAN.md` — Master design
2. `Migration-Plan/IMPROVEMENTS.md` — Architecture changes
3. `Migration-Plan/PHASE_CONTRACTS.md` — Phase boundaries
4. Phase-specific spec documents in phases/

### For running the Unity project for the first time

1. `Migration-Plan/POST_MIGRATION_PLAN.md` §1 — User setup guide (45 min)
2. `Migration-Plan/POST_MIGRATION_PLAN.md` §2-8 — Code work

---

## 3. Documents to Archive/Mark

These documents should be clearly marked so future readers don't treat them as current:

### Mark as SUPERSEDED

Add a header banner to each:
```markdown
> **SUPERSEDED**: This document has been superseded by [replacement].
> Retained for historical reference only.
```

| Document | Superseded By |
|----------|--------------|
| HANDOFF_PROMPT.md | Phase 6 is complete. Reading order in COMPLETION_STATUS.md. |
| MIGRATION_AUDIT_2026-02-16.md | audits/AUDIT_1-7 + META_AUDIT_REPORT.md (Feb 19) |

### Mark as HISTORICAL (Original Specs)

Add a header banner:
```markdown
> **HISTORICAL**: This is the original specification. For what was actually
> built, see the corresponding IMPLEMENTATION_SUMMARY. For what's still
> missing, see AUDIT_IMPROVEMENT_PLAN.md.
```

Apply to: All 7 PHASE_*.md spec documents.

### File to Move

| File | Current Location | Move To |
|------|-----------------|---------|
| PHASE_5_IMPLEMENTATION_SUMMARY.md | Migration-Plan/ (root) | Migration-Plan/phases/ |

---

## 4. Key Numbers (Ground Truth)

These are the verified numbers. Use these, not the numbers in older documents.

| Metric | Verified Value | Source |
|--------|---------------|--------|
| Total C# files | 143 (137 source + 6 test) | Direct file enumeration, Feb 21 |
| Test registrations | 119 (95 EditMode + 24 PlayMode) | META_AUDIT_REPORT verification |
| Missing planned systems | 22+ files | AUDIT_IMPROVEMENT_PLAN §3 |
| Documentation files in Migration-Plan/ | 36 .md files | File listing |
| Audit false positives | 21 (8 critical/high) | META_AUDIT_REPORT |
| Audit false negatives | 9 | META_AUDIT_REPORT |
| Audit coverage gaps | 22 | META_AUDIT_REPORT |
| Adaptive changes logged | 25 (AC-001 through AC-025) | ADAPTIVE_CHANGES.md |
| Python source LOC | ~75,911 | CLAUDE.md |
| Phase spec documents | 7 | phases/ directory |
| Implementation summaries | 5 (Phases 3,4,5,6,7) | phases/ directory |
| Risk register items | 14 (0 resolved) | MIGRATION_PLAN §10 |

---

**Document Created**: 2026-02-21
**Purpose**: Single source of truth for documentation state
**Maintained By**: Update when documents are added, moved, or corrected
