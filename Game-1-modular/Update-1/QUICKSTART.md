# Update-1 Quickstart Guide

**One command to deploy everything:**

```bash
python tools/deploy_update.py Update-1 --force
```

That's it! The system will:
1. ✅ Validate JSON files
2. 🎨 Generate placeholder icons
3. 📚 Update Vheer catalog
4. 📦 Install Update-1

Then launch the game:
```bash
python main.py
```

---

## What You'll See

**During game launch:**
```
Loading content from installed Update-N packages...
📦 Loading 1 Update-N package(s): Update-1
🔄 Loading equipment from 1 update(s)...
   📦 Loading: Update-1/items-testing-integration.JSON
🔄 Loading skills from 1 update(s)...
   ⚡ Loading: Update-1/skills-testing-integration.JSON
✅ Update-N packages loaded successfully
```

**In-game:**
- 5 new weapons in inventory/equipment system
- 6 new skills in skill menu
- 3 new boss enemies spawning

---

## Uninstall

```bash
python tools/update_manager.py uninstall Update-1
```

Content won't load on next launch.

---

## Manual Control

### View what's installed:
```bash
python tools/update_manager.py list
```

### Install without validation (risky):
```bash
python tools/update_manager.py install Update-1 --force
```

### Just validate (no install):
```bash
python tools/update_manager.py validate Update-1
```

---

## For Developers

**Create Update-2:**
1. `mkdir Update-2`
2. Add JSONs to Update-2/
3. `python tools/deploy_update.py Update-2`

**Scales infinitely - no code changes needed!**
