# Unity UI Panel Audit Report

**Date**: 2026-02-26
**Branch**: `claude/rework-unity-ui-iDXzN`
**Audited Against**: Python 2D source in `Game-1-modular/` (rendering/renderer.py, core/game_engine.py)
**Total UI Files**: 27 files in `Unity/Assets/Scripts/Game1.Unity/UI/`

---

## Executive Summary

All 27 UI panels compile and build their hierarchies correctly via `_buildUI()`. However, most panels are **structurally complete but functionally shallow** compared to the Python 2D source. The panels open/close, display headers, and have the right layout, but many lack the data binding, event wiring, and game logic that makes them functional.

### Status Legend
- **WORKING**: Feature matches Python behavior, no issues
- **PARTIAL**: Feature exists but is incomplete or differs from Python
- **STUB**: Code structure exists but does nothing meaningful
- **MISSING**: Feature from Python is entirely absent in Unity
- **BROKEN**: Code exists but won't work (compile error, wrong API, etc.)

---

## 1. CraftingUI.cs

**Python source**: `renderer.py:4429-5720` + `game_engine.py:3169-3550` + `interactive_crafting.py`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | Opens via station interaction, closes via ESC |
| Recipe list loading | WORKING | `GetRecipesForStation()` correctly filters by discipline+tier |
| Recipe list display | WORKING | Shows output name + material count |
| Recipe selection | WORKING | Updates title, description, rebuilds grid |
| Material palette (debug) | WORKING | Shows all materials from MaterialDatabase with qty 99 |
| Material palette (normal) | PARTIAL | Filters inventory by tier, but no material borrowing |
| Grid building (smithing) | PARTIAL | Correct sizing (3+tier*2), but Python uses tier→size lookup not formula |
| Grid building (alchemy) | **BROKEN** | Uses `3 + tier` slots. Python: {T1:2, T2:3, T3:4, T4:6} |
| Grid building (refining) | **BROKEN** | Missing multi-core for T3/T4. Python: surrounding={T1:2,T2:4,T3:5,T4:6} |
| Grid building (engineering) | **BROKEN** | Wrong slot names. Python: FRAME,FUNCTION,POWER,MODIFIER,UTILITY (not frame,core,mechanism,power,output). T1-T2 only show first 3 slots |
| Grid building (enchanting) | PARTIAL | Uses `4+tier` size. Python: {T1:8,T2:10,T3:12,T4:14} Cartesian shape |
| Click-to-place material | WORKING | Left-click places selected palette material |
| Right-click remove | WORKING | Right-click clears placed material from slot |
| Drag-and-drop to grid | PARTIAL | OnDrop handler works, but no visual ghost icon |
| Difficulty calculation | WORKING | Uses tier-based point system matching Python |
| **Crafting execution** | **MISSING** | `_onCraftClicked()` transitions to MinigameActive but doesn't start minigame |
| **Material borrowing** | **MISSING** | Python deducts materials on placement, returns on clear. Unity doesn't |
| **Invent button** | **STUB** | Shows "Validating placement..." but doesn't call classifier |
| Recipe matching/validation | **MISSING** | No pattern matching to detect if placement matches a recipe |

### Priority Fixes
1. Fix alchemy slot counts to {T1:2, T2:3, T3:4, T4:6}
2. Fix refining with multi-core and correct surrounding counts
3. Fix engineering slot names to FRAME/FUNCTION/POWER/MODIFIER/UTILITY
4. Fix enchanting grid sizes to {T1:8, T2:10, T3:12, T4:14}
5. Wire crafting execution to InteractiveCrafting system
6. Implement material borrowing (deduct on place, return on clear)

---

## 2. MapUI.cs

**Python source**: `renderer.py:2778-3171` + `systems/map_waypoint_system.py` (717 lines)

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | M key toggles map |
| Map texture rendering | PARTIAL | Uses WorldSystem.GetChunk() which auto-generates chunks, defeating fog-of-war |
| Biome colors | WORKING | 14 biome colors matching Python |
| Zoom controls | PARTIAL | Range 0.25-5.0 (Python: 0.25-4.0). Max should be 4.0 |
| Pan/drag | WORKING | Drag to pan, scroll to zoom |
| Player marker | PARTIAL | Wrong shape (square vs triangle) and color (red vs white) |
| Grid lines | WORKING | Border lines between chunks |
| Spawn chunk highlight | WORKING | Gold border on (0,0) chunk |
| Center-on-player button | WORKING | Manual center button works |
| Auto-center on open | **MISSING** | Python auto-centers when map opens |
| Coordinate display | PARTIAL | Shows player chunk, Python shows hovered chunk + biome name |
| Zoom level display | WORKING | Shows current zoom level |
| **Waypoint markers on map** | **MISSING** | No visual markers for waypoints rendered on map |
| **Waypoint sidebar list** | **STUB** | Empty scroll view, no waypoint entries |
| **Add/remove waypoints** | **MISSING** | No P key binding, no MapWaypointSystem ported |
| **Waypoint teleportation** | **MISSING** | No teleport logic |
| **Death chest markers** | **MISSING** | No skull markers on map |
| **Dungeon markers** | **MISSING** | No dungeon entrance indicators |
| Fog of war | PARTIAL | Reveals 3x3 area (Python: 1x1 only). Not persisted in saves |
| Chunk exploration save/load | **MISSING** | Explored chunks reset on reload |

### Priority Fixes
1. Port `MapWaypointSystem` from Python (prerequisite for waypoints)
2. Stop auto-generating chunks via GetChunk() -- use exploration data
3. Add waypoint markers on map
4. Populate waypoint sidebar
5. Fix zoom max to 4.0
6. Fix exploration radius to 1x1
7. Add save/load for exploration data

---

## 3. StatsUI.cs

**Python source**: `renderer.py:6426-6538`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | C key toggles stats |
| Stat display (6 stats) | WORKING | Shows all 6 stats with values |
| Stat allocation (+) | WORKING | Works correctly, debug mode grants free points |
| Stat deallocation (-) | WORKING | Works in debug mode only |
| Unallocated points display | WORKING | Shows point count |
| Level/class display | WORKING | Shows level and class name |
| Bonus descriptions | WORKING | Shows calculated bonuses per stat |
| F5 grants 10 points | WORKING | Debug key for testing |
| Button enable/disable | WORKING | Grayed out when no points or at max |
| **Titles column** | **MISSING** | Python shows 8 most recent earned titles with tier colors |
| **Progress column** | **MISSING** | Python shows activity progress bars toward next title |

| **_deallocateStat missing recalc** | **BUG** | Debug deallocation bypasses `_recalculateStats()`. After deallocating VIT, max HP won't decrease |

### Priority Fixes
1. Add Titles column showing earned titles (or link to TitleUI)
2. Add Progress column showing activity progress bars
3. Call recalculate after deallocation

---

## 4. EquipmentUI.cs

**Python source**: `renderer.py:5720-5843`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | I key toggles equipment |
| 8 equipment slots displayed | WORKING | Body-like layout matching Python |
| Equipment icons | WORKING | Uses SpriteDatabase for icons |
| Durability bar | WORKING | Color-coded (green/yellow/red) fill bar |
| Slot labels | WORKING | Below each slot |
| Total damage display | WORKING | Shows main hand + off hand damage ranges |
| Total defense display | WORKING | Shows sum of all armor defense |
| Equipment change events | WORKING | Refreshes on equip/unequip events |
| **Click-to-unequip** | **MISSING** | Python: SHIFT+CLICK to unequip. Unity: no click handler on slots |
| **Drag-drop from inventory** | PARTIAL | DragDropManager exists but no handler on equipment slots |
| **Tier badge** | **MISSING** | Python shows T1-T4 badge in corner of each slot |
| **Rarity color border** | **MISSING** | Python colors slot border by item rarity |
| **Stat bonuses section** | **MISSING** | Python shows equipment stat bonuses below damage/defense |
| **Equipment tooltip on hover** | **MISSING** | Python shows detailed tooltip when hovering equipment slots |

| **GetTotalDefense ignores enchantments** | **BUG** | Python uses `get_defense_with_enchantments()`. Unity uses raw `item.Defense` |
| **TMP stats fields never written** | **BUG** | `_totalDamageText`/`_totalDefenseText` (TMP path) are never updated in Refresh() |

### Priority Fixes
1. Add click-to-unequip handler (SHIFT+CLICK or right-click)
2. Fix GetTotalDefense to include enchantment bonuses
3. Add tier badge in slot corner
4. Add stat bonuses display below damage/defense
5. Add tooltip on hover for equipped items
6. Update TMP text fields in Refresh() alongside programmatic labels

---

## 5. InventoryUI.cs

**Python source**: `renderer.py:3977-4238` + `game_engine.py:6544-7000`

| Feature | Status | Details |
|---------|--------|---------|
| 30-slot grid | WORKING | 6x5 grid with 64px slots |
| Item icons | WORKING | Uses SpriteDatabase |
| Quantity display | WORKING | Shows quantity for stacks >1 |
| Tooltips on hover | WORKING | Shows material tier/rarity, equipment stats |
| Right-click equip | WORKING | Equipment items can be right-click equipped |
| Drag begin/end | WORKING | IBeginDragHandler/IEndDragHandler implemented |
| **Drag-drop swap/stack** | **BROKEN** | DragDropManager.OnDropCompleted has no subscribers that actually swap inventory slots |
| **Drop to world** | **MISSING** | Python: drag out of inventory = drop item. Unity: no handler |
| **Consumable use** | **STUB** | Shows "Used item_name" notification but doesn't consume item or apply effect |
| **Sort button** | **MISSING** | Python has sort by name/tier/quantity |
| **Gold display** | **MISSING** | Python shows gold amount |
| **Weight display** | **MISSING** | Python shows current/max weight |
| **Stack splitting** | **MISSING** | Python: SHIFT+CLICK splits stack |

### Priority Fixes
1. Wire DragDropManager.OnDropCompleted to actually perform inventory slot swaps
2. Implement consumable use (consume item, apply healing/buff)
3. Add drop-to-world functionality

---

## 6. SkillsMenuUI.cs

**Python source**: `renderer.py:2475-2700`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | K key toggles skills menu |
| Known skills list | WORKING | Shows learned skills with filter |
| Skill detail view | WORKING | Name, description, mana, cooldown, tags |
| Category filters | WORKING | All/Combat/Buff/Heal/Utility tabs |
| Hotbar slots display | WORKING | 5 slots showing equipped skill names |
| Equip to hotbar | WORKING | Auto-assigns to first empty slot |
| Unequip from hotbar | WORKING | Removes skill from hotbar |
| Scroll through skills | WORKING | ScrollRect with vertical list |
| Mana cost display | WORKING | Fixed: uses ManaCostRaw.ToString() |
| **Available to Learn section** | **MISSING** | Python shows skills that can be learned but haven't been |
| **Scroll indicator** | **MISSING** | Python shows "X-Y of Z" counter |
| **Skill icons** | **MISSING** | Python shows skill icons. Unity shows text-only buttons |
| **Click equip from list** | **MISSING** | Python: click learned skill to equip/unequip. Unity: must select then click button |

### Priority Fixes
1. Add "Available to Learn" section below known skills
2. Add click-to-equip directly from skill list entries

---

## 7. SkillBarUI.cs (In-Game Hotbar)

**Python source**: `renderer.py:2323-2473`

| Feature | Status | Details |
|---------|--------|---------|
| 5 skill slots | WORKING | Bottom-center of screen |
| Skill icons | WORKING | From SpriteDatabase |
| Key labels (1-5) | WORKING | Shows slot number |
| Skill activation | WORKING | Via InputManager.OnSkillActivate |
| **Cooldown overlay** | **BROKEN** | Fill calculation divides by remaining time instead of max cooldown. Shows binary on/off, not gradual countdown |
| **Mana cost display** | **MISSING** | Python shows MP cost in each slot. Unity has `_noManaColor` but never uses it |
| **Skill name labels** | **MISSING** | Code-built path creates `_nameLabels` but never populates them |
| **Hover tooltip** | **MISSING** | Python shows detailed skill tooltip on hover |

### Priority Fixes
1. Fix cooldown fill calculation (divide by max cooldown, not remaining)
2. Add mana cost display per slot
3. Add mana-insufficient color indicator

---

## 8. EncyclopediaUI.cs

**Python source**: `renderer.py:2760+`

| Feature | Status | Details |
|---------|--------|---------|
| Panel open/close | WORKING | J key toggles (note: header says [E/ESC] but key is J) |
| 6 tabs | WORKING | Guide, Quests, Skills, Titles, Stats, Recipes |
| Tab switching | WORKING | Content swaps correctly |
| **Tab content** | **STUB** | Each tab shows 1-2 lines of placeholder text. Python renders full scrollable lists with icons and details |
| **Material enumeration** | **MISSING** | Python lists all discovered materials with tiers |
| **Equipment catalog** | **MISSING** | Python lists all equipment with stats |
| **Recipe browser** | **MISSING** | Python lists all known recipes with ingredients |
| **Skill browser** | **MISSING** | Python lists all skills with details |

### Priority Fixes
1. Populate each tab with actual data from databases
2. Fix keybinding mismatch (header says E, InputManager maps J)

---

## 9. DebugOverlay.cs

| Feature | Status | Details |
|---------|--------|---------|
| F1: Toggle debug | WORKING | Shows/hides debug overlay |
| F2: Learn all skills | WORKING | Grants all skills from SkillDatabase |
| F3: Grant all titles | **STUB** | Shows notification but doesn't actually grant titles |
| F4: Max level + stats | WORKING | Sets max level, grants stat points |
| F5: +10 stat points | WORKING | For manual allocation testing |
| F7: Infinite durability | WORKING | Toggle flag |
| FPS counter | WORKING | Shows FPS |
| Position/chunk display | WORKING | Shows coordinates and chunk info |
| **Debug starts ON** | **BUG** | `_debugActive = true` in Start() contradicts `_debugPanel.SetActive(false)` in _buildUI |
| **F6 Quick Save** | **MISSING** | Python has F6 for quick save |

---

## 10. DragDropManager.cs

| Feature | Status | Details |
|---------|--------|---------|
| Singleton pattern | WORKING | Instance accessible globally |
| BeginDrag/CompleteDrop API | WORKING | Events fire correctly |
| DragSource enum | WORKING | 6 sources: None, Inventory, Equipment, CraftingGrid, Chest, World |
| **Ghost icon** | **BROKEN** | No _buildUI creates ghost icon. Code-built path has no visual drag feedback |
| **OnDropCompleted subscribers** | **MISSING** | No code subscribes to handle actual slot swaps |
| **Input System dependency** | **RISK** | Unconditional `using UnityEngine.InputSystem` without #if guard |

---

## 11. Other Panels Summary

| Panel | Status | Key Issue |
|-------|--------|-----------|
| **ChestUI** | PARTIAL | Take All works, but no per-item Take One |
| **NPCDialogueUI** | STUB | Quest accept/turn-in show notifications only |
| **TitleUI** | BROKEN | Shows ALL titles as earned (no requirement check). "No title equipped" always |
| **ClassSelectionUI** | WORKING | 6 class cards, selection, confirm button |
| **SkillUnlockUI** | PARTIAL | Only checks level requirement, ignores prerequisites |
| **SaveLoadUI** | WORKING | Save/Load/Delete functional. No keybinding to open |
| **StartMenuUI** | WORKING | New/Load game flow works |
| **StatusBarUI** | PARTIAL | HP/Mana/EXP bars work. No buff icons |
| **NotificationUI** | WORKING | Show/fade/stack notifications |
| **TooltipRenderer** | WORKING | Deferred render, screen-edge clamping |
| **MinigameUI (base)** | WORKING | Timer, performance tracking, result overlay |
| **FishingMinigameUI** | PARTIAL | Ripple rendering is stub |

---

## Compile Errors Found

| File | Line | Issue | Status |
|------|------|-------|--------|
| SkillsMenuUI.cs | 372 | `ManaCostRaw` is `object`, not `string` | **FIXED** (added `.ToString()`) |
| DragDropManager.cs | 16 | `using UnityEngine.InputSystem` without #if guard | **RISK** (may fail without Input System package) |

---

## Architecture Gaps (Not UI-specific)

These Python systems have NOT been ported to Unity and are required by multiple UI panels:

1. **MapWaypointSystem** (717 lines) - Required by MapUI for waypoints, exploration tracking, teleportation
2. **Consumable Use System** - Required by InventoryUI for right-click item consumption
3. **Quest System** - Required by NPCDialogueUI for quest accept/turn-in
4. **Inventory Drag Logic** - Required by InventoryUI + EquipmentUI for slot swaps and transfers
5. **Material Borrowing** - Required by CraftingUI for temporary material removal during placement

---

## What You Should Expect (Current State)

### Works Now
- All panels **open and close** with correct keybindings
- All panels **display headers, layout, and structure** correctly
- **Stats allocation** works with +/- buttons (debug mode grants free points, F5 gives 10)
- **Equipment** shows equipped items with icons, durability bars, and real damage/defense stats
- **Inventory** shows items with icons and quantities, tooltips work
- **Crafting** loads and displays recipes, palette shows materials (debug=all, normal=inventory)
- **Crafting grid** can be populated via click-to-place
- **Skills menu** shows learned skills, can equip/unequip to hotbar
- **Map** shows explored chunks with biome colors, zoom/pan works

### Does Not Work Yet
- **Cannot actually craft items** (craft button doesn't start minigame with materials)
- **Cannot drag-drop items between inventory slots** (no swap handler)
- **Cannot unequip items** from equipment panel (no click handler)
- **Cannot use consumable items** (stub notification only)
- **Cannot add/manage waypoints** on map
- **Cannot teleport** to waypoints
- **Cannot learn new skills** from skills menu
- **Encyclopedia tabs are empty** (placeholder text only)
- **Titles panel shows all titles as earned** (broken requirement check)
- **Quest accept/turn-in don't work** (stub)
- **Drag-and-drop has no visual feedback** (no ghost icon)
- **Cooldown display on skill hotbar is broken** (wrong math)

---

## Recommended Fix Priority

### Tier 1 - Compile/Runtime Blockers
1. Fix DragDropManager Input System dependency (add #if guard)
2. Fix DebugOverlay starting with debug ON

### Tier 2 - Core Gameplay (players can't progress without these)
3. Wire crafting execution to InteractiveCrafting system
4. Wire inventory drag-drop to perform actual slot swaps
5. Fix SkillBarUI cooldown calculation
6. Implement consumable use (healing potions, etc.)
7. Add click-to-unequip on equipment slots

### Tier 3 - Major Feature Gaps
8. Fix crafting grid layouts (alchemy, refining, engineering, enchanting)
9. Implement material borrowing in crafting
10. Port MapWaypointSystem for waypoints
11. Populate encyclopedia tabs with real data
12. Fix TitleUI requirement checks
13. Add "Available to Learn" skills section

### Tier 4 - Polish
14. Add inventory sort, gold/weight display
15. Add stat bonuses display in equipment panel
16. Fix encyclopedia keybinding mismatch (J vs E)
17. Add buff icons to status bar
18. Add proper ghost icon for drag-drop
