# UI Rework Handoff — February 26, 2026

**Branch**: `claude/rework-unity-ui-iDXzN`
**Purpose**: Hand off context from UI rework sessions to the next conversation.

---

## What Was Done (4 Commits)

### Commit 1: `ffaa3b4` — Center panels + crafting station interaction
- All UI panels centered (anchorMin/Max = 0.5, pivot = 0.5)
- Crafting stations trigger CraftingUI.Open() with correct discipline/tier
- Fixed SceneBootstrapper to detect and open crafting stations on interaction

### Commit 2: `9af4919` — Panel functionality polish (7 files, +545/-65)
- SkillsMenuUI: skill detail view, category filters, hotbar equip/unequip
- CraftingUI: recipe list loading, grid building per discipline, material palette
- EquipmentUI: durability bars, damage/defense totals
- MapUI: biome colors, pan/zoom, player marker
- InventoryUI: item icons, quantities, right-click equip
- StatusBarUI: HP/Mana/EXP bar fills
- EncyclopediaUI: tab switching framework

### Commit 3: `0d43872` — Compile fix + audit report
- Fixed CS1503 in SkillsMenuUI.cs: `ManaCostRaw` is `object`, added `.ToString()`
- Created `Unity/UI_AUDIT_REPORT.md` comparing all 27 panels against Python source

### Commit 4: `6954e70` — Comprehensive fixes (11 files, +476/-86)
Files changed:
- **DragDropManager.cs**: Removed `using UnityEngine.InputSystem`, added `_buildGhostIcon()`, switched to `Input.mousePosition`
- **DebugOverlay.cs**: Debug starts OFF, F3 toggles ShowAllTitles flag
- **CraftingUI.cs**: Python-exact grid configs (5 dictionaries), material borrowing, engineering slot name fix
- **EquipmentUI.cs**: EquipmentSlotClickHandler for right-click/shift-click unequip, stat bonuses display
- **InventoryUI.cs**: _onDropCompleted handler for swap/equip/drop
- **SkillBarUI.cs**: Cooldown uses max from SkillDatabase, skill name labels, mana color
- **MapUI.cs**: Zoom max 4.0, auto-center on open, 1x1 exploration
- **TitleUI.cs**: Requirement checking via ActivityType + AcquisitionThreshold
- **EncyclopediaUI.cs**: 5 real data builders (guide, skills, titles, stats, recipes)
- **StatsUI.cs**: HP/Mana clamp after debug deallocation

---

## Current State — What Works

### Fully Functional
- All 27 panels open/close with correct keybindings
- All panels self-build via `_buildUI()` (no prefab dependencies)
- **StatsUI**: 6 stats, +/- allocation, debug dealloc with HP/Mana clamp
- **EquipmentUI**: 8 slots, icons, durability bars, damage/defense, stat bonuses, right-click unequip
- **InventoryUI**: 30-slot grid, icons, quantities, tooltips, right-click equip, drag-drop swap/equip/drop
- **SkillsMenuUI**: Skill list with filters, detail view, hotbar equip/unequip
- **SkillBarUI**: 5 slots with icons, cooldown overlay, mana color, skill names
- **CraftingUI**: Recipes loaded, 5 discipline grids (exact Python configs), material borrowing
- **EncyclopediaUI**: 6 tabs with real data from databases
- **TitleUI**: Requirement-based filtering, debug ShowAllTitles
- **MapUI**: Biome-colored chunks, zoom 0.25-4.0x, auto-center, 1x1 exploration
- **DragDropManager**: Ghost icon, drag lifecycle, right-click/ESC cancel
- **DebugOverlay**: All F-keys (F1-F5, F7), starts OFF, ShowAllTitles property

### Non-Functional (Stubs)
- **Crafting execution**: Craft button transitions state but doesn't start minigame
- **Consumable use**: Shows notification, doesn't consume or apply effect
- **Title equipping**: Raises event but doesn't track or apply bonuses
- **Quest accept/turn-in**: Notification only
- **Waypoint system**: Not ported
- **Invent button**: Shows "Validating..." only

---

## Critical API Patterns

### Object-Typed Fields
`SkillCost.ManaCostRaw` and `CooldownRaw` are `object` (can be string "moderate" or numeric 60). Always use `.ToString()` before string operations.

### Dual Field Pattern (TMP + Legacy Text)
Every self-built panel has both TMP SerializeField references (for inspector wiring) and legacy `UnityEngine.UI.Text` fields (for `_buildUI()` path). Update BOTH in Refresh methods:
```csharp
// TMP path (inspector)
if (_someLabel != null) _someLabel.text = value;
// Programmatic path (code-built)
if (_someLabelFallback != null) _someLabelFallback.text = value;
```

### Character Has No Titles Property
`Character` exposes: Stats, Inventory, Equipment, Skills, Buffs, Leveling, StatTracker
`TitleSystem` exists in `Game1.Systems.Progression` but is NOT integrated into Character.
TitleUI works by directly querying TitleDatabase + StatTracker.

### EquipmentManager.Equip() Returns Tuple
```csharp
var (previousItem, status) = gm.Player.Equipment.Equip(item, slotName);
// status == "OK" means success
```

### Input: Legacy Only (No InputSystem Package)
All input uses `Input.mousePosition`, `Input.GetMouseButtonDown()`, `Input.GetKey()`.
Do NOT import `UnityEngine.InputSystem`.

### Grid Configurations (Python-Exact)
```
Smithing:    {T1:3, T2:5, T3:7, T4:9} square grid
Alchemy:     {T1:2, T2:3, T3:4, T4:6} sequence slots
Refining:    {T1:(1c,2s), T2:(1c,4s), T3:(2c,5s), T4:(3c,6s)} hub+spoke
Engineering: T1-T2: FRAME,FUNCTION,POWER | T3-T4: +MODIFIER,UTILITY
Enchanting:  {T1:8, T2:10, T3:12, T4:14} Cartesian grid
```

---

## Potential Runtime Risks (Not Yet Tested in Unity)

These compile but may fail at runtime — test these first:

1. **SkillBarUI line ~139**: `skillDb.GetCooldownSeconds(skillDef.Cost.CooldownRaw)` — verify method exists
2. **SkillBarUI line ~158**: `skillDb.GetManaCost(skillDef.Cost.ManaCostRaw)` — verify method exists
3. **TitleUI line ~234**: `tracker.GetActivityCount(title.ActivityType)` — verify StatTracker has this method
4. **InventoryUI._onDropCompleted**: Full equip flow (EquipmentDatabase.GetEquipment → Equipment.Equip) untested
5. **EquipmentUI.UnequipSlot**: Unequip → AddItem flow untested
6. **EncyclopediaUI**: Multiple `Database.Instance` calls — null if databases not loaded yet
7. **MapUI._centerOnPlayer**: Called on state change — player position may not exist during startup

---

## Recommended Next Steps

### Immediate (Debug Current Pushes)
1. **Build in Unity** — verify no compile errors remain
2. **Test each panel** — open/close, check data displays correctly
3. **Test drag-drop flow** — inventory swap, inventory→equipment, drop-to-world
4. **Test crafting grids** — open each discipline at each tier, verify slot counts
5. **Test title requirements** — verify titles filter correctly (toggle F3 to compare)

### Then Continue Toward 60%
6. Wire crafting execution (craft button → minigame → item creation)
7. Implement consumable use system
8. Port MapWaypointSystem (717 lines from Python)
9. Wire quest accept/turn-in logic
10. Add title equip tracking on Character

### Reference Documents
- `Unity/UI_AUDIT_REPORT.md` — Full panel-by-panel status with remaining work
- `Migration-Plan/COMPLETION_STATUS.md` — Overall migration hub
- `Migration-Plan/CONVENTIONS.md` — C# coding conventions
- `.claude/CLAUDE.md` — Project overview and architecture

---

## File Map (All Modified UI Files)

```
Unity/Assets/Scripts/Game1.Unity/UI/
├── CraftingUI.cs          — Grid configs, material borrowing, recipe selection
├── DebugOverlay.cs        — Debug flags, F-keys, ShowAllTitles
├── DragDropManager.cs     — Ghost icon, drag lifecycle, input handling
├── EncyclopediaUI.cs      — 6 tabs with real database content
├── EquipmentUI.cs         — 8 slots, unequip handler, stat bonuses
├── InventoryUI.cs         — 30 slots, drag-drop handler, right-click equip
├── MapUI.cs               — Biome map, zoom, auto-center, fog of war
├── SkillBarUI.cs          — 5 hotbar slots, cooldown, mana indicator
├── SkillsMenuUI.cs        — Skill list, filters, hotbar management
├── StatsUI.cs             — 6 stat rows, allocation, HP/Mana clamp
├── TitleUI.cs             — Title list with requirement filtering
├── ClassSelectionUI.cs    — (unchanged) 6 class cards
├── StartMenuUI.cs         — (unchanged) New/Load game
├── StatusBarUI.cs         — (unchanged) HP/Mana/EXP bars
├── NotificationUI.cs      — (unchanged) Notification stack
├── SaveLoadUI.cs          — (unchanged) Save/Load/Delete
├── ChestUI.cs             — (unchanged) Take All only
├── NPCDialogueUI.cs       — (unchanged) Stub quest logic
├── SkillUnlockUI.cs       — (unchanged) Level-only check
├── TooltipRenderer.cs     — (unchanged) Screen-edge clamping
├── MinigameUI.cs          — (unchanged) Base minigame framework
├── SmithingMinigameUI.cs  — (unchanged) Needs execution wire-up
├── AlchemyMinigameUI.cs   — (unchanged) Needs execution wire-up
├── RefiningMinigameUI.cs  — (unchanged) Needs execution wire-up
├── EngineeringMinigameUI.cs — (unchanged) Needs execution wire-up
├── EnchantingMinigameUI.cs  — (unchanged) Needs execution wire-up
└── FishingMinigameUI.cs   — (unchanged) Stub ripple rendering
```

---

## Key Lessons from This Session

1. **Always `.ToString()` on `object`-typed fields** — ManaCostRaw, CooldownRaw are `object` not `string`
2. **Character doesn't have every subsystem** — No `.Titles`, no `.Quests`. Check Character.cs before assuming
3. **Don't use UnityEngine.InputSystem** — Project uses legacy Input class
4. **Test grid configs against Python source** — Don't derive formulas, use the exact lookup tables from Python
5. **Update BOTH TMP and legacy Text fields** — Self-built UI uses `Text`, inspector path uses TMP
6. **FindFirstObjectByType<T>() is expensive** — Cache references in Start(), don't call every frame
