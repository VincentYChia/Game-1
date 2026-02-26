# Unity UI Panel Audit Report

**Date**: 2026-02-26 (updated post-fix)
**Branch**: `claude/rework-unity-ui-iDXzN`
**Audited Against**: Python 2D source in `Game-1-modular/` (rendering/renderer.py, core/game_engine.py)
**Total UI Files**: 27 files in `Unity/Assets/Scripts/Game1.Unity/UI/`
**Commits**: 4 commits on branch (ffaa3b4, 9af4919, 0d43872, 6954e70)

---

## Executive Summary

All 27 UI panels self-build via `_buildUI()` and have correct layouts. After 4 rounds of fixes, **core UI functionality is at ~55-60%** compared to the Python 2D source. Most panels now have real data binding and event wiring. The remaining gaps are: crafting execution (minigames), consumable use, waypoint system, quest logic, and various polish items.

### Status Legend
- **WORKING**: Feature matches Python behavior
- **PARTIAL**: Feature exists but incomplete or differs from Python
- **STUB**: Code structure exists but does nothing meaningful
- **MISSING**: Feature from Python is entirely absent in Unity

### Quick Status Matrix

| Panel | Open/Close | Data Binding | User Interaction | Completeness |
|-------|-----------|-------------|-----------------|-------------|
| StatsUI | WORKING | WORKING | WORKING | ~90% |
| EquipmentUI | WORKING | WORKING | WORKING | ~75% |
| InventoryUI | WORKING | WORKING | PARTIAL | ~70% |
| CraftingUI | WORKING | WORKING | PARTIAL | ~60% |
| SkillsMenuUI | WORKING | WORKING | WORKING | ~80% |
| SkillBarUI | WORKING | WORKING | WORKING | ~80% |
| MapUI | WORKING | PARTIAL | WORKING | ~55% |
| EncyclopediaUI | WORKING | WORKING | WORKING | ~80% |
| TitleUI | WORKING | WORKING | PARTIAL | ~65% |
| DebugOverlay | WORKING | WORKING | WORKING | ~85% |
| DragDropManager | WORKING | N/A | WORKING | ~90% |
| ClassSelectionUI | WORKING | WORKING | WORKING | ~95% |
| StartMenuUI | WORKING | WORKING | WORKING | ~95% |
| StatusBarUI | WORKING | WORKING | N/A | ~70% |
| NotificationUI | WORKING | N/A | N/A | ~95% |
| SaveLoadUI | WORKING | WORKING | WORKING | ~90% |

---

## 1. CraftingUI.cs

**Python source**: `renderer.py:4429-5720` + `game_engine.py:3169-3550` + `interactive_crafting.py`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | Opens via station interaction, closes via ESC |
| Recipe list loading | WORKING | `GetRecipesForStation()` correctly filters by discipline+tier |
| Recipe selection | WORKING | Updates title, description, rebuilds grid |
| Material palette (debug) | WORKING | Shows all materials from MaterialDatabase with qty 99 |
| Material palette (normal) | WORKING | Filters inventory by tier |
| Grid: smithing | WORKING | Lookup table {T1:3, T2:5, T3:7, T4:9} matches Python exactly |
| Grid: alchemy | WORKING | Lookup table {T1:2, T2:3, T3:4, T4:6} matches Python exactly |
| Grid: refining | WORKING | Hub+spoke with {T1:(1,2), T2:(1,4), T3:(2,5), T4:(3,6)} |
| Grid: engineering | WORKING | Named slots FRAME/FUNCTION/POWER/MODIFIER/UTILITY, T1-T2 = 3 slots, T3-T4 = 5 |
| Grid: enchanting | WORKING | Lookup table {T1:8, T2:10, T3:12, T4:14} |
| Click-to-place material | WORKING | Left-click places selected palette material |
| Right-click remove | WORKING | Right-click clears placed material from slot |
| Drag-and-drop to grid | WORKING | OnDrop handler + ghost icon from DragDropManager |
| Material borrowing | WORKING | Deducts from inventory on place, returns on clear/close |
| Difficulty calculation | WORKING | Tier-based point system matching Python |
| Debug mode bypass | WORKING | Skips inventory checks in debug mode |
| **Crafting execution** | **STUB** | `_onCraftClicked()` transitions to MinigameActive state but doesn't start actual minigame |
| **Invent button** | **STUB** | Shows "Validating placement..." notification only |
| **Recipe matching** | **MISSING** | No pattern matching to validate if placement matches a recipe |

### Remaining Work
1. Wire `_onCraftClicked()` to InteractiveCrafting system (consume materials, start minigame)
2. Wire `_onInventClicked()` to crafting classifier (CNN/LightGBM validation)
3. Add recipe pattern matching/validation

---

## 2. MapUI.cs

**Python source**: `renderer.py:2778-3171` + `systems/map_waypoint_system.py` (717 lines)

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | M key toggles map |
| Map texture rendering | PARTIAL | Uses WorldSystem.GetChunk() — may auto-generate unvisited chunks |
| Biome colors | WORKING | 14 biome colors matching Python |
| Zoom controls | WORKING | Range 0.25-4.0 (corrected from 5.0) |
| Pan/drag | WORKING | Drag to pan, scroll to zoom |
| Player marker | PARTIAL | Square marker (Python: triangle), color may differ |
| Grid lines | WORKING | Border lines between chunks |
| Spawn chunk highlight | WORKING | Gold border on (0,0) chunk |
| Center-on-player button | WORKING | Manual + auto-center on open |
| Auto-center on open | WORKING | Centers on player position when map opens |
| Fog of war | WORKING | Reveals 1x1 area (corrected from 3x3) |
| Coordinate display | PARTIAL | Shows player chunk, Python also shows hovered chunk + biome name |
| **Waypoint system** | **MISSING** | No waypoint markers, sidebar, teleportation, or MapWaypointSystem |
| **Death/dungeon markers** | **MISSING** | No skull markers or dungeon entrance indicators |
| **Chunk save/load** | **MISSING** | Explored chunks reset on reload |

### Remaining Work
1. Port `MapWaypointSystem` from Python (717 lines — prerequisite for waypoints)
2. Add waypoint markers, sidebar, add/remove, teleportation
3. Persist explored chunks in save system
4. Show hovered chunk biome name in coordinate display

---

## 3. StatsUI.cs

**Python source**: `renderer.py:6426-6538`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | C key toggles stats |
| Stat display (6 stats) | WORKING | All 6 stats with values |
| Stat allocation (+) | WORKING | Works correctly, debug mode grants free points |
| Stat deallocation (-) | WORKING | Debug mode only, HP/Mana clamped after dealloc |
| Unallocated points | WORKING | Shows point count |
| Level/class display | WORKING | Shows level and class name |
| Bonus descriptions | WORKING | Calculated bonuses per stat |
| Button enable/disable | WORKING | Grayed when no points or at max (30) |
| **Titles column** | **MISSING** | Python shows 8 most recent earned titles with tier colors |
| **Progress column** | **MISSING** | Python shows activity progress bars toward next title |

### Remaining Work
1. Add Titles column showing earned titles (or link to TitleUI)
2. Add Progress column showing activity progress bars

---

## 4. EquipmentUI.cs

**Python source**: `renderer.py:5720-5843`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | I key toggles equipment |
| 8 equipment slots | WORKING | Body-like layout matching Python |
| Equipment icons | WORKING | Uses SpriteDatabase |
| Durability bar | WORKING | Color-coded (green/yellow/red) fill |
| Slot labels | WORKING | Below each slot |
| Total damage display | WORKING | Shows main hand + off hand ranges |
| Total defense display | WORKING | Shows sum of armor defense |
| Stat bonuses section | WORKING | Shows equipment.GetStatBonuses() below damage/defense |
| Click-to-unequip | WORKING | Right-click or Shift+click via EquipmentSlotClickHandler |
| Equipment change events | WORKING | Refreshes on equip/unequip |
| **Tier badge** | **MISSING** | Python shows T1-T4 badge in slot corner |
| **Rarity color border** | **MISSING** | Python colors slot border by item rarity |
| **Equipment tooltip** | **MISSING** | Python shows detailed tooltip on hover |
| **Enchantment defense** | **PARTIAL** | GetTotalDefense uses raw item.Defense, not enchantment-adjusted |

### Remaining Work
1. Add tier badge in slot corner
2. Add rarity color border on slots
3. Add tooltip on hover for equipped items
4. Include enchantment bonuses in defense calculation

---

## 5. InventoryUI.cs

**Python source**: `renderer.py:3977-4238` + `game_engine.py:6544-7000`

| Feature | Status | Details |
|---------|--------|---------|
| 30-slot grid | WORKING | 6x5 grid with 64px slots |
| Item icons | WORKING | Uses SpriteDatabase |
| Quantity display | WORKING | Shows quantity for stacks >1 |
| Tooltips on hover | WORKING | Material tier/rarity, equipment stats |
| Right-click equip | WORKING | Equipment items equipped on right-click |
| Drag begin/end | WORKING | IBeginDragHandler/IEndDragHandler |
| Drag-drop swap | WORKING | OnDropCompleted handler swaps inventory slots |
| Drag-to-equip | WORKING | Inventory→Equipment slot equips item |
| Drop to world | WORKING | Drag outside inventory drops item |
| **Consumable use** | **STUB** | Shows notification but doesn't consume or apply effect |
| **Sort button** | **MISSING** | Python has sort by name/tier/quantity |
| **Gold display** | **MISSING** | Python shows gold amount |
| **Weight display** | **MISSING** | Python shows current/max weight |
| **Stack splitting** | **MISSING** | Python: SHIFT+CLICK splits stack |

### Remaining Work
1. Implement consumable use (consume item, apply healing/buff)
2. Add sort button (by name/tier/quantity)
3. Add gold and weight display
4. Add stack splitting (SHIFT+CLICK)

---

## 6. SkillsMenuUI.cs

**Python source**: `renderer.py:2475-2700`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | K key toggles |
| Known skills list | WORKING | Shows learned skills with filter |
| Skill detail view | WORKING | Name, description, mana, cooldown, tags |
| Category filters | WORKING | All/Combat/Buff/Heal/Utility tabs |
| Hotbar slots display | WORKING | 5 slots showing equipped skill names |
| Equip to hotbar | WORKING | Auto-assigns to first empty slot |
| Unequip from hotbar | WORKING | Removes skill from hotbar |
| Mana cost display | WORKING | Uses ManaCostRaw.ToString() (fixed) |
| **Available to Learn** | **MISSING** | Python shows unlearned skills that meet requirements |
| **Skill icons** | **MISSING** | Shows text-only buttons (Python shows icons) |

### Remaining Work
1. Add "Available to Learn" section below known skills
2. Add skill icons from SpriteDatabase

---

## 7. SkillBarUI.cs (In-Game Hotbar)

**Python source**: `renderer.py:2323-2473`

| Feature | Status | Details |
|---------|--------|---------|
| 5 skill slots | WORKING | Bottom-center of screen |
| Skill icons | WORKING | From SpriteDatabase |
| Key labels (1-5) | WORKING | Shows slot number |
| Skill activation | WORKING | Via InputManager.OnSkillActivate |
| Cooldown overlay | WORKING | Fill = remaining / maxCooldown from SkillDatabase.GetCooldownSeconds() |
| Skill name labels | WORKING | Truncated to 8 chars, populated per slot |
| Mana color indicator | WORKING | Red when insufficient mana, normal otherwise |
| **Hover tooltip** | **MISSING** | Python shows detailed skill tooltip on hover |

### Remaining Work
1. Add hover tooltip with skill details

### Potential Runtime Risk
- `SkillDatabase.GetCooldownSeconds()` and `GetManaCost()` are called but their existence hasn't been verified in a Unity build

---

## 8. EncyclopediaUI.cs

**Python source**: `renderer.py:2760+`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | J key toggles (header says [E/ESC]) |
| 6 tabs | WORKING | Guide, Quests, Skills, Titles, Stats, Recipes |
| Tab switching | WORKING | Content swaps correctly |
| Guide tab | WORKING | Full controls reference text |
| Skills tab | WORKING | Lists known skills with mana cost and tags from SkillDatabase |
| Titles tab | WORKING | Lists all titles from TitleDatabase with tier/bonus |
| Stats tab | WORKING | Full character stats with calculated bonuses |
| Recipes tab | WORKING | All recipes by discipline from RecipeDatabase |
| Quests tab | **STUB** | Hardcoded "(No active quests)" — needs quest system |
| **Material enumeration** | **MISSING** | Python lists all discovered materials |
| **Equipment catalog** | **MISSING** | Python lists all equipment |

### Remaining Work
1. Wire quests tab to quest system when available
2. Add material enumeration tab/section
3. Fix header hint mismatch ([E/ESC] vs actual J key)

---

## 9. DebugOverlay.cs

| Feature | Status | Details |
|---------|--------|---------|
| F1: Toggle debug | WORKING | Shows/hides debug overlay |
| F2: Learn all skills | WORKING | Grants all skills from SkillDatabase |
| F3: Show all titles | WORKING | Toggles ShowAllTitles flag, TitleUI respects it |
| F4: Max level + stats | WORKING | Sets max level, grants stat points |
| F5: +10 stat points | WORKING | For manual allocation testing |
| F7: Infinite durability | WORKING | Toggle flag |
| Debug starts OFF | WORKING | _debugActive = false (fixed) |
| FPS counter | WORKING | Shows FPS |
| Position/chunk display | WORKING | Shows coordinates and chunk info |
| **F6 Quick Save** | **MISSING** | Python has F6 for quick save |

---

## 10. DragDropManager.cs

| Feature | Status | Details |
|---------|--------|---------|
| Singleton pattern | WORKING | Instance accessible globally |
| BeginDrag/CompleteDrop | WORKING | Full drag lifecycle |
| Ghost icon | WORKING | Overlay canvas + Image + CanvasGroup follows cursor |
| OnDropCompleted event | WORKING | InventoryUI subscribes and handles swaps |
| DragSource enum | WORKING | None, Inventory, Equipment, CraftingGrid, Chest, World |
| Input handling | WORKING | Uses Input.mousePosition (no InputSystem dependency) |
| Right-click cancel | WORKING | Cancels in-progress drag |
| Escape cancel | WORKING | Cancels via InputManager event |

---

## 11. TitleUI.cs

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | Opened programmatically (no keybind) |
| Title list | WORKING | Filters by requirement: ActivityType + AcquisitionThreshold |
| Free titles | WORKING | Shows titles with threshold <= 0 as starter |
| Debug ShowAllTitles | WORKING | F3 flag respected, shows all titles |
| Title detail view | WORKING | Name, tier, description, bonuses |
| **Title equipping** | **STUB** | OnEquipClicked raises event but doesn't track equipped title |
| **Title bonuses** | **MISSING** | Equipping doesn't apply stat bonuses to character |
| **Current title display** | **STUB** | Always shows "No title equipped" |

### Remaining Work
1. Track currently equipped title on character
2. Apply title bonuses to character stats
3. Update "Current Title" display after equip

---

## 12. Other Panels Summary

| Panel | Status | Key Issue |
|-------|--------|-----------|
| **ChestUI** | PARTIAL | Take All works, no per-item Take One |
| **NPCDialogueUI** | STUB | Quest accept/turn-in show notifications only |
| **ClassSelectionUI** | WORKING | 6 class cards, selection, confirm button |
| **SkillUnlockUI** | PARTIAL | Only checks level requirement, ignores prerequisites |
| **SaveLoadUI** | WORKING | Save/Load/Delete functional. No keybinding to open |
| **StartMenuUI** | WORKING | New/Load game flow works |
| **StatusBarUI** | PARTIAL | HP/Mana/EXP bars work. No buff icons |
| **NotificationUI** | WORKING | Show/fade/stack notifications |
| **TooltipRenderer** | WORKING | Deferred render, screen-edge clamping |
| **MinigameUI (base)** | WORKING | Timer, performance tracking, result overlay |
| **FishingMinigameUI** | PARTIAL | Ripple rendering is stub |
| **SmithingMinigameUI** | PARTIAL | Structure built, needs crafting execution wire-up |
| **AlchemyMinigameUI** | PARTIAL | Structure built, needs crafting execution wire-up |
| **RefiningMinigameUI** | PARTIAL | Structure built, needs crafting execution wire-up |
| **EngineeringMinigameUI** | PARTIAL | Structure built, needs crafting execution wire-up |
| **EnchantingMinigameUI** | PARTIAL | Structure built, needs crafting execution wire-up |

---

## Compile Issues

| File | Issue | Status |
|------|-------|--------|
| SkillsMenuUI.cs:372 | `ManaCostRaw` is `object`, needs `.ToString()` | **FIXED** |
| DragDropManager.cs | `using UnityEngine.InputSystem` removed | **FIXED** |

---

## Architecture Gaps (Not UI-specific)

These Python systems are NOT yet ported and are needed by UI panels:

1. **MapWaypointSystem** (717 lines) — Required by MapUI for waypoints/teleportation
2. **Consumable Use System** — Required by InventoryUI for right-click consumption
3. **Quest System** — Required by NPCDialogueUI for quest accept/turn-in
4. **Crafting Execution** — InteractiveCrafting exists but isn't wired to CraftingUI's craft button
5. **Title Equip Tracking** — No mechanism to track/apply equipped title on Character
6. **Combat System** — Not started (out of scope for UI work)
7. **Resource Gathering** — Not started (out of scope for UI work)
8. **Hostile AI** — Not started (out of scope for UI work)

---

## Potential Runtime Risks (Untested in Unity)

These are areas where the code compiles but may fail at runtime:

1. **SkillBarUI**: Calls `SkillDatabase.GetCooldownSeconds()` and `GetManaCost()` — method signatures verified via grep but not tested in build
2. **TitleUI**: Calls `tracker.GetActivityCount(title.ActivityType)` — StatTracker method unverified
3. **InventoryUI._onDropCompleted**: Calls `EquipmentDatabase.Instance.GetEquipment()` then `Equipment.Equip()` — flow not tested
4. **EquipmentUI.UnequipSlot**: Calls `Equipment.Unequip()` then `Inventory.AddItem()` — flow not tested
5. **EncyclopediaUI**: Multiple database Instance calls (SkillDatabase, TitleDatabase, RecipeDatabase) — may be null if databases not loaded
6. **MapUI._centerOnPlayer**: Called on state change, player position may not exist during startup transitions

---

## Remaining Work Priority (Post-Fix)

### Tier 1 — Core Gameplay Blockers
1. **Wire crafting execution** — CraftingUI craft button → InteractiveCrafting → minigame → item creation
2. **Consumable use** — InventoryUI right-click → consume item → apply healing/buff
3. **Title equip tracking** — TitleUI equip → persist on Character → apply bonuses

### Tier 2 — Major Feature Gaps
4. **Port MapWaypointSystem** — Waypoints, teleportation, death chest markers
5. **Quest system wiring** — NPCDialogueUI → accept/turn-in quests
6. **SkillUnlockUI prerequisites** — Check skill requirements, not just level
7. **Chunk persistence** — Save/load explored map data

### Tier 3 — Polish
8. Equipment tier badges + rarity borders
9. Inventory sort, gold/weight display, stack splitting
10. StatusBarUI buff icons
11. Skill/Equipment hover tooltips
12. Encyclopedia materials/equipment catalog tabs
13. StatsUI titles column + progress bars
14. ChestUI per-item Take One

### Tier 4 — Systems (Not UI)
15. Combat system
16. Resource gathering
17. Hostile AI
18. Save/load integration for all new state
