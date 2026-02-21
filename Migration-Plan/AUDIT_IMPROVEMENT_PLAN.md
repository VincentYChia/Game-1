# Audit Improvement Plan — Comprehensive Gap Remediation

**Date**: 2026-02-21
**Source**: META_AUDIT_REPORT.md + independent codebase verification
**Scope**: Every identified gap, false positive correction, missing system, and documentation inconsistency
**Goal**: Provide a single actionable reference for bringing the Unity migration to a playable state

---

## Table of Contents

1. [Actual Codebase State (Verified)](#1-actual-codebase-state-verified)
2. [Audit Corrections Required](#2-audit-corrections-required)
3. [Missing Systems — Complete Inventory](#3-missing-systems--complete-inventory)
4. [Architecture Gaps](#4-architecture-gaps)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Documentation Inconsistencies to Resolve](#6-documentation-inconsistencies-to-resolve)

---

## 1. Actual Codebase State (Verified)

Verified on 2026-02-21 by direct file enumeration.

### File Counts (Actual)

| Namespace | Script Files | Test Files | Total |
|-----------|-------------|------------|-------|
| Game1.Core | 4 | 0 | 4 |
| Game1.Data (Databases) | 10 | 0 | 10 |
| Game1.Data (Enums) | 6 | 0 | 6 |
| Game1.Data (Models) | 10 | 0 | 10 |
| Game1.Entities | 3 | 0 | 3 |
| Game1.Entities.Components | 7 | 0 | 7 |
| Game1.Systems (Classifiers) | 8 | 1 | 9 |
| Game1.Systems (Combat) | 6 | 0 | 6 |
| Game1.Systems (Crafting) | 8 | 0 | 8 |
| Game1.Systems (Effects) | 3 | 0 | 3 |
| Game1.Systems (Items) | 1 | 0 | 1 |
| Game1.Systems (LLM) | 6 | 3 | 9 |
| Game1.Systems (Progression) | 4 | 0 | 4 |
| Game1.Systems (Save) | 2 | 0 | 2 |
| Game1.Systems (Tags) | 4 | 0 | 4 |
| Game1.Systems (World) | 5 | 0 | 5 |
| Game1.Unity (Config) | 4 | 0 | 4 |
| Game1.Unity (Core) | 5 | 0 | 5 |
| Game1.Unity (ML) | 2 | 0 | 2 |
| Game1.Unity (UI) | 22 | 0 | 22 |
| Game1.Unity (Utilities) | 3 | 0 | 3 |
| Game1.Unity (World) | 13 | 0 | 13 |
| Tests (PlayMode) | 0 | 2 | 2 |
| **TOTAL** | **137** | **6** | **143** |

**Note**: Various documents claim 133, 139, 144, or 147 files. The actual count is **143** (137 source + 6 test). The discrepancy comes from documents written at different dates and counting conventions.

### What Actually Exists vs. What Documents Claim

| Claimed (by various docs) | Actually Exists? | Notes |
|---------------------------|-----------------|-------|
| 147 C# files | **143** | Off by 4; likely counts .py scripts or docs |
| ItemFactory.cs | **NO** | Planned in IMPROVEMENTS.md FIX-13, never created |
| InteractiveCrafting.cs | **NO** | Planned in PHASE_4, deferred to Phase 6, never created |
| FishingMinigame.cs | **NO** | Planned in MIGRATION_PLAN, never created |
| ConsumableItem.cs | **NO** | Planned in IGameItem hierarchy, never created |
| PlaceableItem.cs | **NO** | Planned in IGameItem hierarchy, never created |
| NPCDatabase.cs | **NO** | Planned in PHASE_CONTRACTS Phase 2, never created |
| TranslationDatabase.cs | **NO** | Planned in PHASE_CONTRACTS Phase 2, never created |
| SkillUnlockDatabase.cs | **NO** | SkillUnlockSystem.cs exists but is not a database singleton |
| DungeonSystem.cs | **NO** | Planned in PHASE_4, never created |
| PlayerController.cs | **NO** | Planned in PHASE_6, never created |
| SaveLoadUI.cs | **NO** | Planned in IMPROVEMENTS.md FIX-10, never created |
| SkillUnlockUI.cs | **NO** | Planned in PHASE_6, never created |
| TitleUI.cs | **NO** | Planned in PHASE_6, never created |
| ServiceLocator.cs | **NO** | Planned in MIGRATION_PLAN Appendix A, never created |
| CharacterBuilder.cs | **NO** | Planned in PHASE_3, never created |
| Tool.cs (entity) | **NO** | Planned in PHASE_3, tool data handled by EquipmentItem |
| DamageNumber.cs (entity) | **NO** | Planned in PHASE_3, deferred to Phase 6 renderer |
| ActivityTracker.cs | **NO** | Planned in PHASE_3, covered by StatTracker |
| CraftedStats.cs | **NO** | Planned in PHASE_3, handled inline in crafting |
| WeaponTagCalculator.cs | **NO** | Planned in PHASE_3, covered by DamageCalculator |
| MapWaypointConfig.cs | **NO** | Planned in PHASE_CONTRACTS, never created |
| UpdateLoader.cs | **NO** | Planned in PHASE_CONTRACTS, never created |

---

## 2. Audit Corrections Required

These corrections fix false claims in the 7 audit documents as identified by the META_AUDIT_REPORT.

### 2.1 AUDIT_2 — Combat & Movement (Most Corrections)

**Root cause**: Auditor confused `ICombatCharacter`/`ICombatEnemy` interface declarations in CombatManager.cs with actual methods on the `Character` class.

| Section | Current Claim | Correction |
|---------|--------------|------------|
| §2 Attack System | `Character.MainhandCooldown` exists | **Does not exist.** Interface contract only. Must be implemented on Character. |
| §2 Attack System | `Character.OffhandCooldown` exists | **Does not exist.** Interface contract only. Must be implemented on Character. |
| §2 Attack System | `Character.CanAttack()` exists | **Only on ICombatEnemy interface.** Character does not implement it. |
| §2 Attack System | `Character.ResetAttackCooldown()` exists | **Does not exist anywhere.** Must be written. |
| §3 Shield/Block | `Character.IsShieldActive()` exists | **Only on ICombatCharacter interface.** Not implemented. |
| §3 Shield/Block | `Character.GetShieldDamageReduction()` exists | **Only on ICombatCharacter interface.** Not implemented. |
| §3 Shield/Block | `Character.IsBlocking` property exists | **Does not exist on Character.** `TileType.IsBlocking` is unrelated. |
| §2 Equipment | `Equipment.GetWeaponRange()` exists | **Does not exist.** Must be written. |
| §1 Equipment | `Equipment.CalculateEncumbrance()` implied | **Does not exist.** Must be written. |
| §17 DamageNumber | DamageNumberRenderer at "30%" | Actually 80-90% complete (197 lines, full pool, animation, colors). Only missing: nothing calls `SpawnDamageNumber()` yet. |
| §16 AttackEffect | AttackEffectRenderer at "40%" | More complete than stated. |

**Action**: Rewrite AUDIT_2 §2-3 to distinguish interface declarations from Character implementation. Change percentages for DamageNumberRenderer and AttackEffectRenderer.

### 2.2 AUDIT_4 — UI Systems

| Section | Current Claim | Correction |
|---------|--------------|------------|
| Keyboard Bindings | Equipment "E" key → `OnToggleEquipment` COMPLETE | **WRONG.** `E` is bound to `Interact`. `OnToggleEquipment` has **no key binding.** |
| Keyboard Bindings | Encyclopedia opens via "L" key | **Actually bound to J key** (InputManager line 227). |
| Keyboard Bindings | "K key for Skills Menu" MISSING from InputManager | **WRONG.** `OnToggleSkills` event EXISTS and IS bound to K (line 229). The **UI panel** is what's missing. |
| DragDrop | "Item quantity splitting (partial drags)" | **No splitting logic exists.** `DraggedQuantity` is always full stack. |
| Start Menu | "Load World, Load Default" buttons fully implemented | **Only 2 buttons**: "Quick Start" and "New World". |

**Action**: Fix the 5 false claims listed above in AUDIT_4.

### 2.3 AUDIT_6 — 3D Requirements

| Section | Current Label | Correction |
|---------|--------------|------------|
| §1.3 | `ChunkMeshGenerator.GenerateWaterMesh()` exists | **Method is on TerrainMaterialManager**, not ChunkMeshGenerator. |
| §3.1 | CameraController "COMPLETE" (343 lines) | Should be "STRUCTURALLY COMPLETE — NOT WIRED" (lists "Changes Needed" including "Wire input handlers"). |
| §4.1 | DayNightOverlay "COMPLETE" (269 lines) | Should be "STRUCTURALLY COMPLETE — NOT WIRED" (lists "Changes Needed" including "Assign `_sunLight`"). |
| §5.2 | AttackEffectRenderer "COMPLETE" (172 lines) | Should be "STRUCTURALLY COMPLETE — NOT WIRED" (lists "Changes Needed" including "Wire combat system"). |

**Action**: Fix method attribution. Replace "COMPLETE" with "STRUCTURALLY COMPLETE — NOT WIRED" for all files that list required changes.

### 2.4 AUDIT_7 — Testing Strategy

| Section | Current Claim | Correction |
|---------|--------------|------------|
| Test counts | "~180 individual test cases already defined" | **Actual: 119** test registrations. Inflated ~50%. |
| Integration tests | "95+ integration tests" (PlayMode) | **Actual: 24** test methods (10 E2E + 14 LLM integration). |

**Action**: Correct to "119 test methods across 6 files: 95 EditMode + 24 PlayMode."

### 2.5 AUDIT_5 — World & Progression

| Section | Current Claim | Correction |
|---------|--------------|------------|
| §18 | Invented Recipe Persistence "UNKNOWN" | **EXISTS.** SaveManager.cs line 152 serializes `invented_recipes`. SaveMigrator handles migration. |
| §28 | NPC System "MISSING IN C# LOGIC (backend missing)" | **Partially exists.** QuestSystem.cs handles substantive NPC backend logic. Gap is real but overstated. |
| §24 | Save system — no mention of SaveMigrator | **SaveMigrator.cs exists** alongside SaveManager.cs (v1→v2→v3 migration). |

**Action**: Update AUDIT_5 §18 to "IMPLEMENTED in SaveManager/SaveMigrator". Downgrade §28 severity.

### 2.6 AUDIT_1 — Infrastructure

| Section | Current Claim | Correction |
|---------|--------------|------------|
| ML section | SentisBackendFactory "complete" | **Factory depends on mock.** SentisModelBackend returns 85% always. It's a placeholder, not a real implementation. |

**Action**: Mark SentisBackendFactory as "MOCK — returns placeholder results."

### 2.7 AUDIT_3 — Crafting & Minigames

| Section | Current Claim | Correction |
|---------|--------------|------------|
| §14 | Invented Recipe Persistence "FULLY IMPLEMENTED" incl. "Available in crafting UI" | Data layer exists; **CraftingUI wiring to display/re-craft invented recipes is NOT verified.** |

**Action**: Change to "Data persistence IMPLEMENTED. UI integration UNVERIFIED."

---

## 3. Missing Systems — Complete Inventory

Everything that was planned but does not exist in the codebase, organized by priority.

### 3.1 CRITICAL — Required for Game to Function

| # | System | Planned In | Python Source | Est. C# Lines | What It Does |
|---|--------|-----------|--------------|---------------|-------------|
| 1 | Unity project infrastructure | POST_MIGRATION_PLAN §1 | N/A | N/A | ProjectSettings, Packages, .asmdef, scenes, meta files |
| 2 | StreamingAssets/Content/ | POST_MIGRATION_PLAN §4 | N/A | N/A | Copy JSON data files for database loading |
| 3 | Assembly definitions (7) | POST_MIGRATION_PLAN §2 | N/A | ~200 JSON | Namespace isolation and compile-time dependency enforcement |
| 4 | Scene hierarchy | POST_MIGRATION_PLAN §5 | N/A | ~400 (editor script) | GameObject tree per Phase 6 spec |
| 5 | GameManager self-wiring | POST_MIGRATION_PLAN §5.3 | N/A | ~30 | FindFirstObjectByType fallbacks in Awake() |

### 3.2 HIGH — Core Planned Systems Never Created

| # | System | Planned In | Python Source | Est. C# Lines | What It Does |
|---|--------|-----------|--------------|---------------|-------------|
| 6 | **ItemFactory.cs** | IMPROVEMENTS.md FIX-13; PHASE_1 | N/A (new architecture) | ~150-200 | Centralized item creation. 6 scattered creation sites → 1 entry point. Cornerstone of IGameItem hierarchy. |
| 7 | **ConsumableItem.cs** | IMPROVEMENTS.md Part 4; PHASE_1 | N/A (new architecture) | ~80-120 | IGameItem implementation for potions, food, scrolls. Currently all items use dict-like approach. |
| 8 | **PlaceableItem.cs** | IMPROVEMENTS.md Part 4; PHASE_1 | N/A (new architecture) | ~60-80 | IGameItem implementation for crafting stations, turrets. |
| 9 | **InteractiveCrafting.cs** | PHASE_4 §2.4; MIGRATION_PLAN ln 453 | interactive_crafting.py (1,179 lines) | ~600-800 | Dispatches from CraftingUI → specific minigame. Handles material placement validation, station tier checks. Phase 4 summary says "deferred to Phase 6" but Phase 6 didn't create it either. |
| 10 | **FishingMinigame.cs** | MIGRATION_PLAN §2.1; PHASE_4 | fishing.py (872 lines) | ~400-500 | 6th crafting discipline. Casting, reeling, fish behavior AI. AUDIT_3 says "Out of scope?" but the migration plan does NOT exclude it. |
| 11 | **FishingMinigameUI.cs** | PHASE_6 | N/A | ~200-300 | Unity MonoBehaviour wrapper for fishing minigame. |
| 12 | **DungeonSystem.cs** | PHASE_4 §2.7; PHASE_CONTRACTS | dungeon_system.py (805 lines) | ~500-600 | Dungeon generation, wave spawning, boss fights, special rewards. Phase 4 summary says "partially implemented via WorldSystem chunk types" — but actual dungeon logic is missing. |
| 13 | **NPCDatabase.cs** | PHASE_CONTRACTS Phase 2 | npc_db.py (~200 lines) | ~150 | NPC definitions loaded from JSON. QuestSystem.cs partially covers NPC logic but not the data layer. |
| 14 | **SkillsMenuUI.cs** | PHASE_6 §1.5; AUDIT_4 | ~400 Python lines | ~250-350 | Skill browser, equip to hotbar, skill details, unlock requirements. |

### 3.3 MEDIUM — Planned But Not Created

| # | System | Planned In | Python Source | Est. C# Lines | What It Does |
|---|--------|-----------|--------------|---------------|-------------|
| 15 | TranslationDatabase.cs | PHASE_CONTRACTS Phase 2 | translation_db.py (~200 lines) | ~120 | Localization layer for game text |
| 16 | SkillUnlockDatabase.cs | PHASE_CONTRACTS Phase 2 | skill_unlock_db.py (~120 lines) | ~100 | Skill unlock condition definitions (separate from SkillUnlockSystem) |
| 17 | MapWaypointConfig.cs | PHASE_CONTRACTS Phase 2 | Part of map system (~100 lines) | ~80 | Map waypoint/POI definitions |
| 18 | PlayerController.cs | PHASE_6 CONTRACTS | N/A (new) | ~200 | Phase 6 MonoBehaviour for player movement, interaction raycasting |
| 19 | SaveLoadUI.cs | IMPROVEMENTS.md FIX-10 | Part of game_engine.py | ~200 | Save file selection, new game vs load, delete save |
| 20 | SkillUnlockUI.cs | PHASE_6 §1.5 | Part of game_engine.py | ~150 | Shows unlock requirements, cost, prerequisites |
| 21 | TitleUI.cs | PHASE_6 §1.5 | Part of game_engine.py | ~150 | Browse earned titles, equip active title |
| 22 | CharacterBuilder.cs | PHASE_3 | N/A (new) | ~100 | Factory for Character creation with default components |
| 23 | ServiceLocator.cs | MIGRATION_PLAN Appendix A | N/A (new) | ~80 | Service discovery alternative to singletons |
| 24 | UpdateLoader.cs | PHASE_CONTRACTS Phase 2 | update_loader.py (~150 lines) | ~100 | Dynamic content loading (may be dev-time only tool) |

### 3.4 LOW — Nice to Have / Deferred by Design

| # | System | Notes |
|---|--------|-------|
| 25 | Block/Parry mechanics | TODO in Python combat_manager.py. Not implemented in either codebase. |
| 26 | Summon mechanics | TODO in Python effect_executor.py. Not implemented in either codebase. |
| 27 | Advanced skill evolution | Design docs only. Never implemented in Python. |
| 28 | 10 planned specification documents | MIGRATION_PLAN §11.5 references them. Documentation debt. |

---

## 4. Architecture Gaps

These are cross-cutting concerns the meta-audit identified that no individual audit covers.

### 4.1 GameEvents Subscriber Verification

**Risk**: Silent failures if subscribers are missing.

GameEvents defines ~19 event types. No audit verified that all necessary subscribers are wired. Key subscribers to verify:

| Event | Expected Subscriber(s) | Verified? |
|-------|----------------------|-----------|
| OnEquipmentChanged | CharacterStats (stat recalc), SkillManager (dirty cache) | Unknown |
| OnEquipmentRemoved | CharacterStats (stat recalc) | Unknown |
| OnLevelUp | SkillManager (available skills recalc), TitleSystem (title check) | Unknown |
| OnTitleEarned | SkillManager (dirty cache) | Unknown |
| OnSkillLearned | SkillManager (dirty cache) | Unknown |
| OnItemInvented | RecipeDatabase (persist), NotificationSystem (display) | Unknown |
| OnNotificationShown | NotificationUI (render) | Documented but not wired |
| ~12 more events | Various systems | Unknown |

**Action needed**: Systematically audit every GameEvents event and verify all planned subscribers are connected.

### 4.2 Effect Dispatch Table Completeness

**Risk**: Missing effect handlers silently do nothing.

EffectExecutor uses a dispatch table (switch on tag name) per AC-010. Need to verify all Python effect types have handlers:

| Python Effect | C# Handler? | Status |
|--------------|-------------|--------|
| lifesteal | Yes (AC-010) | Verified |
| knockback | Yes (AC-010) | Verified |
| pull | Yes (AC-010) | Verified |
| execute | Yes (AC-010) | Verified |
| teleport | Yes (AC-010) | Verified |
| dash | Yes (AC-010) | Verified |
| phase | Yes (AC-010) | Verified |
| summon | No | Not implemented (by design) |
| reflect | In CombatManager (thorns) | Needs verification |
| chain_damage | In CombatManager | Needs verification |

### 4.3 UI/Data Separation (MACRO-3)

**Risk**: Item loss during save-while-dragging if not separated.

IMPROVEMENTS.md MACRO-3 specifies UI state must be separated from data models. This means:
- DragDropManager should track UI-only drag state
- Inventory data model should never be in an inconsistent state during drag
- Save system should save data model, not UI state

**Status**: Partially implemented (DragDropManager exists separately from Inventory), but no audit verified the save-during-drag scenario.

### 4.4 Stat Recalculation Caching (FIX-11)

**Risk**: Performance regression without dirty-flag caching.

CharacterStats is documented as having dirty-flag invalidation. Need to verify:
- Equipment changes trigger stat recalc
- Buff changes trigger stat recalc
- Level-up triggers stat recalc
- Cached values are actually used (not recomputed every frame)

### 4.5 Convention Compliance

**Risk**: Mismatched `[JsonProperty]` attributes silently drop data.

CONVENTIONS.md defines rules for file headers, namespaces, JSON attributes, error handling. No audit checked compliance across all 137 source files. Key risks:
- JSON property names must match Python field names exactly
- Namespace structure must match directory structure
- Singleton pattern must follow the established template

### 4.6 Risk Register Items (R1-R14)

MIGRATION_PLAN §10 defines 14 risks. None have status updates.

| Risk | Description | Status |
|------|------------|--------|
| R1 | float64→float32 precision divergence | **UNRESOLVED** — no comparison testing |
| R2 | Save format compatibility | Partially addressed by SaveMigrator |
| R3 | Sentis ONNX operator support | **UNRESOLVED** — Sentis not installed |
| R4-R14 | Various | **UNRESOLVED** — no status updates |

---

## 5. Implementation Roadmap

This is the recommended order for addressing all gaps, incorporating the meta-audit corrections and the POST_MIGRATION_PLAN structure.

### Stage 0: Documentation Cleanup (This PR)

No code changes. Fix documentation accuracy.

- [ ] Correct all false positives in AUDIT_2 (§2-3 rewrite)
- [ ] Correct false claims in AUDIT_4 (5 items)
- [ ] Replace "COMPLETE" with "STRUCTURALLY COMPLETE — NOT WIRED" in AUDIT_6 (4 files)
- [ ] Correct test counts in AUDIT_7
- [ ] Update AUDIT_5 §18, §24, §28
- [ ] Update COMPLETION_STATUS.md with accurate file count (143, not 147)
- [ ] Create documentation index showing what each doc is for and when to read it
- [ ] Archive or mark superseded documents

### Stage 1: Unity Project Bootstrap (Phase A from Checklist)

**Prerequisite for everything else. No game logic changes.**

1. User creates Unity project (manual, ~45 min)
2. Create 7 .asmdef files
3. Copy JSON to StreamingAssets/Content/
4. Mock out Sentis (replace SentisModelBackend/Factory with mock)
5. Fix compilation errors iteratively
6. Create scene hierarchy via editor script
7. Wire GameManager self-discovery (FindFirstObjectByType)
8. Verify: Unity compiles, Play mode starts without exceptions

### Stage 2: Core Missing Systems

**Create the systems that were planned but never written.**

Priority order (dependency-driven):

1. **ItemFactory.cs** — other systems need this for item creation
2. **ConsumableItem.cs + PlaceableItem.cs** — completes IGameItem hierarchy
3. **NPCDatabase.cs** — loads NPC definitions for QuestSystem
4. **InteractiveCrafting.cs** — connects CraftingUI to minigames
5. **FishingMinigame.cs + FishingMinigameUI.cs** — 6th discipline
6. **DungeonSystem.cs** — endgame content
7. **SkillsMenuUI.cs** — skill browsing/equipping
8. **PlayerController.cs** — movement and interaction in Unity
9. **SaveLoadUI.cs** — save file management
10. **TranslationDatabase, SkillUnlockDatabase, MapWaypointConfig** — supporting databases

### Stage 3: System Wiring (Phase B from Checklist)

**Connect existing C# systems to the game loop.**

1. Combat → GameManager (attack input, damage display, death/loot)
2. Enemy spawning (ChunkSystem → EnemySpawner → world)
3. Resource gathering (click → tool check → harvest → inventory)
4. Crafting stations (station interaction → CraftingUI → minigame)
5. Skills to hotbar (1-5 keys, mana/cooldown)
6. Day/night modifiers (night → enemy buffs)
7. Death/respawn (player death → death chest, enemy death → loot)
8. Save slot UI (multiple files, auto-save)
9. NotificationSystem → NotificationUI bridge
10. IItemGenerator → CraftingUI pipeline

### Stage 4: Architecture Verification

**Verify cross-cutting concerns.**

1. Audit all GameEvents subscribers
2. Verify effect dispatch table completeness
3. Test save-during-drag scenario (UI/data separation)
4. Verify stat recalculation caching
5. Check convention compliance across all files
6. Update risk register status (R1-R14)

### Stage 5: Testing (Phase E from Checklist, parallel)

**Can run alongside Stages 2-4.**

Priority order:
1. Database loading tests (validates JSON pipeline)
2. Damage formula tests (validates Pillar 1: exact fidelity)
3. Tag system tests (validates combat effects)
4. Crafting logic tests (all 6 disciplines)
5. Inventory/equipment tests
6. Save/load roundtrip tests
7. Remaining system tests

### Stage 6: 3D and Polish (Phases D+F from Checklist)

**After the game is playable in 2D.**

1. Replace Tilemap with height-mapped mesh terrain
2. Replace sprites with primitive 3D shapes
3. Switch to perspective camera
4. Add directional light sun cycle
5. Particle effects for combat/crafting
6. Audio system
7. ONNX model conversion and Sentis integration
8. Real LLM API integration

---

## 6. Documentation Inconsistencies to Resolve

These are contradictions and stale information across the documentation suite.

### 6.1 File Count Contradictions

| Document | Claims | Actual |
|----------|--------|--------|
| COMPLETION_STATUS.md | 147 C# files | 143 |
| MIGRATION_COMPLETION_REPORT.md | 147 C# files, ~34,712 LOC | 143 files |
| POST_MIGRATION_PLAN.md §0 | 133 source + 6 test = 139 | 137 source + 6 test = 143 |
| UNITY_MIGRATION_CHECKLIST.md | 133 source files (31,623 LOC) | 137 source files |
| ADAPTIVE_CHANGES.md | 147 total | 143 |

**Resolution**: Update all to 143 (137 source + 6 test). The 4-file difference from 139 likely reflects BillboardSprite.cs, ChunkMeshGenerator.cs, TerrainMaterialManager.cs, WaterSurfaceAnimator.cs added during the 3D audit phase.

### 6.2 Phase Completion Claims vs Reality

The COMPLETION_STATUS.md says "All 7 phases complete" and lists specific deliverables. But several planned deliverables were never created:
- Phase 1: ItemFactory, ConsumableItem, PlaceableItem — **not created**
- Phase 2: 5 of 14 planned databases — **not created**
- Phase 3: 4 of 11 planned components — **not created** (covered by other files)
- Phase 4: InteractiveCrafting, DungeonSystem — **not created**
- Phase 6: PlayerController, SaveLoadUI, SkillUnlockUI, TitleUI — **not created**

The phases are "complete" in the sense that the work done was committed, but the planned deliverables are not all present. This should be clearly documented.

### 6.3 Test Count Contradictions

| Document | Claims |
|----------|--------|
| MIGRATION_COMPLETION_REPORT.md | 468+ tests |
| AUDIT_7 | ~180 test cases |
| PHASE_7_IMPLEMENTATION_SUMMARY.md | 87+ tests |
| META_AUDIT_REPORT.md | 119 actual test registrations |

**Resolution**: The actual count is 119 test method registrations across 6 files (95 EditMode + 24 PlayMode). The "468+" in the completion report is aspirational, not actual.

### 6.4 Stale/Superseded Documents

| Document | Issue | Resolution |
|----------|-------|------------|
| HANDOFF_PROMPT.md | Written for Phase 6 handoff; Phase 6 is done | Mark as HISTORICAL |
| MIGRATION_AUDIT_2026-02-16.md | Superseded by 7 domain audits (Feb 19) + META_AUDIT_REPORT | Mark as SUPERSEDED BY audits/ |
| PHASE_5_IMPLEMENTATION_SUMMARY.md | In Migration-Plan/ root, not in phases/ like others | Move to phases/ for consistency |
| .claude/INDEX.md | Last updated Jan 27 — predates entire migration | Needs major update |
| .claude/CLAUDE.md | References Python architecture; partially updated for migration | Needs migration completion update |

### 6.5 Overlapping/Redundant Documents

Several documents cover similar ground and create confusion about which is authoritative:

| Topic | Documents | Recommendation |
|-------|-----------|---------------|
| "What's done" | COMPLETION_STATUS.md, MIGRATION_COMPLETION_REPORT.md, phase summaries | COMPLETION_STATUS.md is the hub. Report is historical. |
| "What's left" | UNITY_MIGRATION_CHECKLIST.md, POST_MIGRATION_PLAN.md, this document | CHECKLIST is the hub for gaps. POST_MIGRATION_PLAN is the how-to-run guide. This document is the accuracy corrections + plan. |
| "How to work on migration" | HANDOFF_PROMPT.md, COMPLETION_STATUS.md reading order | COMPLETION_STATUS.md reading order only. HANDOFF_PROMPT.md is historical. |
| "Audit findings" | MIGRATION_AUDIT_2026-02-16.md, 7 domain audits, META_AUDIT_REPORT.md | Domain audits + META_AUDIT are current. Feb-16 audit is superseded. |

---

## Summary

### Gap Totals

| Category | Count |
|----------|-------|
| False positives to correct in audits | 21 |
| False negatives to correct in audits | 9 |
| Coverage gaps (unaudited systems) | 22 |
| Missing planned C# files | 22+ |
| Architecture concerns unverified | 9 |
| Documentation contradictions | 15+ |
| Risk register items unresolved | 14 |
| **Estimated new C# files needed** | **~15-20** |
| **Estimated new C# LOC needed** | **~3,000-5,000** |

### Priority Summary

1. **Now**: Fix documentation accuracy (this PR)
2. **Next**: Unity project bootstrap (user + code work, ~10-17 hours per POST_MIGRATION_PLAN)
3. **Then**: Create missing core systems (ItemFactory, InteractiveCrafting, FishingMinigame, DungeonSystem)
4. **Then**: Wire all systems to game loop
5. **Parallel**: Write unit tests for all formulas
6. **Last**: 3D upgrade and polish

---

**Document Created**: 2026-02-21
**For**: Development team working on completing the Unity migration
**Supersedes**: None (new document)
**Related**: META_AUDIT_REPORT.md (input), UNITY_MIGRATION_CHECKLIST.md (gap hub), POST_MIGRATION_PLAN.md (bootstrap guide)
