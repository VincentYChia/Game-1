# Update System Documentation

**Complete automation for mass JSON content production**

---

## Overview

The Update-N system allows you to create unlimited game content through JSON files without modifying core game code. Everything is automated - from validation to deployment to in-game loading.

### Key Features

✅ **Zero Code Changes** - Add content via JSON only
✅ **Automatic Discovery** - Databases auto-load Update-N content
✅ **Conflict Detection** - Warns about duplicate IDs
✅ **Version Tracking** - Manifest tracks installed updates
✅ **One-Command Deployment** - Single script does everything
✅ **Scalable** - Update-1 through Update-999+

---

## Quick Start

### Deploy an Update
```bash
python tools/deploy_update.py Update-1 --force
```

### Launch Game
```bash
python main.py
```

That's it! Your content is in the game.

---

## System Architecture

### 1. Update Directory Structure

```
Game-1-modular/
├── Update-1/                          # First content pack
│   ├── items-testing-integration.JSON
│   ├── skills-testing-integration.JSON
│   ├── hostiles-testing-integration.JSON
│   ├── README.md
│   └── QUICKSTART.md
├── Update-2/                          # Future content
│   └── ...
├── updates_manifest.json              # Tracks installed updates
└── tools/
    ├── deploy_update.py               # ONE COMMAND deployment
    ├── update_manager.py              # Install/uninstall/validate
    ├── create_placeholder_icons_simple.py
    └── update_catalog.py
```

### 2. Database Auto-Discovery

**File**: `data/databases/update_loader.py`

On game launch, this module:
1. Reads `updates_manifest.json`
2. Scans all installed Update-N directories
3. Loads JSONs into appropriate databases
4. No code changes to core databases needed

**Integration Point**: `core/game_engine.py:122-124`
```python
# Load content from installed Update-N packages
from data.databases.update_loader import load_all_updates
load_all_updates(get_resource_path(""))
```

### 3. Manifest System

**File**: `updates_manifest.json`

```json
{
  "version": "1.0",
  "installed_updates": ["Update-1", "Update-2"],
  "schema_version": 1,
  "last_updated": "2025-12-25T22:08:14.928553"
}
```

Automatically managed - don't edit manually.

---

## Tools Reference

### deploy_update.py (Recommended)

**One-command deployment with full automation**

```bash
# Deploy Update-1 (all steps)
python tools/deploy_update.py Update-1 --force

# Skip icon generation
python tools/deploy_update.py Update-1 --skip-icons

# Skip catalog update
python tools/deploy_update.py Update-1 --skip-catalog
```

**What it does:**
1. Validates JSON files
2. Generates placeholder icons
3. Updates Vheer catalog
4. Installs update

### update_manager.py

**Lower-level control**

```bash
# List all updates
python tools/update_manager.py list

# Validate without installing
python tools/update_manager.py validate Update-1

# Install
python tools/update_manager.py install Update-1 [--force]

# Uninstall
python tools/update_manager.py uninstall Update-1
```

### create_placeholder_icons_simple.py

**Generate placeholder PNGs**

```bash
# All test content
python tools/create_placeholder_icons_simple.py --all-test-content

# Specific JSON
python tools/create_placeholder_icons_simple.py --json items.JSON/items-testing-integration.JSON
```

Creates 64x64 colored squares in `assets/generated_icons/`.

### update_catalog.py

**Add content to Vheer AI catalog**

```bash
# Update from Update-N
python tools/update_catalog.py --update Update-1

# Specific JSON
python tools/update_catalog.py --json items.JSON/items-testing-integration.JSON
```

Appends to `tools/ITEM_CATALOG_FOR_ICONS.md` for AI icon generation.

---

## Creating New Updates

### Step 1: Create Directory

```bash
mkdir Update-2
```

### Step 2: Add JSON Files

```
Update-2/
├── items-magic-weapons.JSON       # New magic weapons
├── skills-fire-magic.JSON         # Fire mage skills
└── hostiles-demons.JSON           # Demon enemies
```

### Step 3: Deploy

```bash
python tools/deploy_update.py Update-2 --force
```

### Step 4: Test

```bash
python main.py
```

---

## JSON File Requirements

### Minimum Structure

All JSON files must have:

```json
{
  "metadata": {
    "version": "1.0",
    "description": "Description of content",
    "note": "Optional notes"
  },

  "items": [],      // Or skills, enemies, etc.
  "test_weapons": []  // Alternative key names supported
}
```

### Supported Content Types

| Type | Key Names | Example File |
|------|-----------|--------------|
| **Items (Equipment)** | `items`, `test_weapons`, `weapons`, `armor` | items-*.JSON |
| **Skills** | `skills` | skills-*.JSON |
| **Enemies** | `enemies` | hostiles-*.JSON, enemies-*.JSON |
| **Materials** | `materials` | materials-*.JSON |
| **Consumables** | `consumables` | consumables-*.JSON |
| **Devices** | `devices` | devices-*.JSON |

### ID Requirements

Every entity must have a unique ID:
- Items: `itemId`
- Skills: `skillId`
- Enemies: `enemyId`

IDs must be unique **across all files** (including core game files).

---

## Conflict Resolution

### Detection

The system automatically detects ID conflicts:

```bash
$ python tools/update_manager.py validate Update-1

⚠️  Conflicts detected:
   - Item ID conflict: copper_sword (exists in items-smithing-2.JSON)
   - Skill ID conflict: fireball (exists in skills-skills-1.JSON)
```

### Resolution Options

**Option 1: Rename conflicting IDs**
```json
{
  "itemId": "copper_sword_v2",  // Changed from copper_sword
  "name": "Copper Sword",
  ...
}
```

**Option 2: Force install (overwrites)**
```bash
python tools/update_manager.py install Update-1 --force
```

**Best Practice**: Use unique prefixes
```json
{
  "itemId": "update1_copper_sword",  // Prefixed with update name
  "skillId": "update1_fireball",
  "enemyId": "update1_demon_lord"
}
```

---

## Validation Rules

The system validates:

✅ **JSON Syntax** - Must be valid JSON
✅ **Metadata Section** - Must have metadata
✅ **Content Sections** - Must have at least one non-metadata section
✅ **File Structure** - Recognizes items/skills/enemies JSONs
✅ **ID Conflicts** - Checks against core game files

**Validation does NOT check:**
- Tag validity (checked at runtime)
- Parameter correctness (checked at runtime)
- Balance/gameplay (your responsibility)

---

## Troubleshooting

### "Update directory not found"

```
Error: Update directory not found: Update-1
```

**Fix**: Directory must be at project root
```bash
ls -la | grep Update
# Should show: drwxr-xr-x Update-1/
```

### "No .JSON files found"

```
Error: No .JSON files found in Update-1/
```

**Fix**: JSON files must have `.JSON` extension (uppercase)
```bash
# Wrong
items.json

# Correct
items.JSON
```

### "Validation failed: Invalid JSON"

```
Error: items-testing.JSON: Invalid JSON - Expecting ',' delimiter
```

**Fix**: Check JSON syntax with validator
```bash
python -m json.tool items-testing.JSON
```

### "Content not loading in game"

**Possible causes:**
1. Update not installed
   ```bash
   python tools/update_manager.py list
   # Check if update is marked as INSTALLED
   ```

2. Manifest corrupted
   ```bash
   cat updates_manifest.json
   # Should list your update in installed_updates
   ```

3. Game cached old data
   ```bash
   # Clear Python cache
   find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
   ```

### "Conflicts detected"

**If legitimate conflicts:**
- Rename IDs in your update
- Use unique prefixes

**If false positives (same file):**
- Use `--force` flag
- This happens when test files exist in both Update-N and core directories

---

## Advanced Usage

### Multiple Updates

Install multiple updates:
```bash
python tools/deploy_update.py Update-1 --force
python tools/deploy_update.py Update-2 --force
python tools/deploy_update.py Update-3 --force
```

All will load automatically on game launch.

### Selective Loading

Uninstall unwanted updates:
```bash
python tools/update_manager.py uninstall Update-2
```

Update-1 and Update-3 remain installed.

### Update Priority

Updates load in **alphabetical order**. For load order control:
```
Update-001-base-content/
Update-002-expansion-1/
Update-003-hotfix/
```

Later updates can override earlier ones (if IDs conflict).

---

## Integration with Tag System

Updates fully integrate with the tag system:

```json
{
  "itemId": "update1_plasma_rifle",
  "name": "Plasma Rifle",
  "type": "weapon",
  "slot": "mainHand",
  "effectTags": ["beam", "pierce", "lightning", "shock"],
  "effectParams": {
    "baseDamage": 120,
    "beam_range": 15.0,
    "pierce_count": 5,
    "shock_duration": 8.0,
    "damage_per_tick": 15.0
  }
}
```

**No code changes needed** - tag system processes automatically.

---

## Performance

### Loading Time

- **Per Update**: ~50-200ms depending on content count
- **5 Updates**: ~250ms-1s additional load time
- **Negligible** for reasonable update counts (<10)

### Memory

- Each JSON loaded into memory
- ~1-5 MB per update (typical)
- Minimal impact

### Runtime

- Zero performance impact
- Updates load once at game start
- After loading, identical to core content

---

## Best Practices

### 1. Organize by Feature

```
Update-1/  # Tag system test content
Update-2/  # Fire magic expansion
Update-3/  # Desert biome enemies
Update-4/  # Halloween event
```

### 2. Use Descriptive IDs

```json
// Bad
{"itemId": "sword1"}

// Good
{"itemId": "halloween_pumpkin_sword"}
```

### 3. Version Your Updates

```
Update-001-base/
Update-002-hotfix-balance/
Update-003-expansion-desert/
```

### 4. Test Before Deploying

```bash
# Validate first
python tools/update_manager.py validate Update-1

# Then deploy
python tools/deploy_update.py Update-1 --force
```

### 5. Document Your Updates

Create README.md in each Update-N directory:
```markdown
# Update-2: Fire Magic Expansion

## Contents
- 10 fire magic skills
- 3 fire-themed weapons
- 5 fire elemental enemies

## Testing Checklist
- [ ] All skills load
- [ ] Fire damage works
- [ ] Burn status applies
```

---

## Scaling to Production

### Content Pipeline

```
1. Designer creates JSON in Update-N/
2. Run: python tools/deploy_update.py Update-N
3. Test in-game
4. Iterate on JSON (no recompile needed)
5. When ready: git commit Update-N/
6. CI/CD deploys to production
```

### No Code Deployment

```bash
# Production server
git pull
python tools/update_manager.py install Update-42
# Content live immediately
```

### Hotfixes

```bash
# Create hotfix
mkdir Update-43-hotfix
# Add fixed JSON
python tools/deploy_update.py Update-43-hotfix
# Deployed in seconds
```

---

## Comparison: Before vs. After

### Before Update System

**To add 5 weapons:**
1. Edit `items.JSON/items-smithing-2.JSON`
2. Risk breaking existing content
3. Hard to track changes
4. Merge conflicts in git
5. Can't easily remove

**To deploy:**
1. Modify core files
2. Restart game
3. Hope nothing broke

### After Update System

**To add 5 weapons:**
1. Create `Update-N/weapons.JSON`
2. `python tools/deploy_update.py Update-N`
3. Done

**To deploy:**
1. Copy Update-N/ to server
2. One command
3. Live immediately

---

## Future Enhancements

**Planned:**
- [ ] Schema validation (JSON schemas for each type)
- [ ] Dependency system (Update-2 requires Update-1)
- [ ] Hot-reload (load updates without restart)
- [ ] Web UI for update management
- [ ] Automatic conflict resolution
- [ ] Update versioning (v1.0, v1.1, etc.)
- [ ] Rollback system
- [ ] Delta updates (only changed files)

**Community Contributions Welcome!**

---

## Summary

The Update-N system enables **mass JSON production at scale**:

✅ **Developers** - Add content without touching code
✅ **Designers** - Iterate on JSON directly
✅ **QA** - Test updates in isolation
✅ **Production** - Deploy content independently

**One command. Zero friction. Infinite scale.**

```bash
python tools/deploy_update.py Update-N --force
```
