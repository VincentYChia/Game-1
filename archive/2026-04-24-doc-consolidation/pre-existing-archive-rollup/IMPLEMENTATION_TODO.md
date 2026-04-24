# Implementation TODO - November 16, 2025

## Completed ✅

1. **Fix Enchanting Selection Click Detection**
   - Issue: `enchantment_item_rects` was not initialized in __init__
   - Fix: Added `self.enchantment_item_rects = None` at line 4665
   - Status: FIXED ✓

2. **Recipe Scrolling (Already Working)**
   - Mouse wheel scrolling is already implemented (lines 4772-4780)
   - Shows 8 recipes at a time with scroll indicators
   - Works for all 5 crafting disciplines
   - Status: VERIFIED ✓

---

## In Progress ⏳

### 3. Skills Load from JSON (NEEDS IMPLEMENTATION)

**Current State:**
- SkillDatabase.load_from_file() is a stub (line 2127-2128)
- Only sets `self.loaded = True`, doesn't actually load JSON
- Skills JSON exists at `Skills/skills-skills-1.JSON` with 30 skills defined

**Required Changes:**
1. Create `SkillDefinition` dataclass with all fields from JSON
2. Implement proper JSON loading in `SkillDatabase.load_from_file()`
3. Update `PlayerSkill.get_definition()` to return actual SkillDefinition
4. Add skill lookup methods to SkillDatabase

**Implementation Notes:**
- JSON structure has: skillId, name, tier, rarity, categories, description, narrative, tags
- Effect structure: type, category, magnitude, target, duration
- Cost structure: mana (text), cooldown (text)
- Evolution structure: canEvolve, nextSkillId, requirement
- Requirements: characterLevel, stats, titles

**Files to Modify:**
- `main.py` lines 2090-2129 (Skill system classes)
- Use TitleDatabase.load_from_file() as a template (lines 745-798)

---

### 4. Titles Load from JSON (VERIFY CURRENT STATUS)

**Current State:**
- TitleDatabase.load_from_file() IS implemented (lines 745-798)
- Called in __init__ at line 4580: `TitleDatabase.get_instance().load_from_file("progression/titles-1.JSON")`
- Should be working!

**Action Needed:**
- Verify it's loading correctly
- Check if all title tiers (Novice through Master) are being loaded
- Test title acquisition in-game

**Status:** PROBABLY WORKING, needs verification

---

### 5. Expand Debug Mode for Skill/Title Testing

**Current Debug Features (F1 toggles):**
- Infinite resources (nodes don't deplete)
- Debug info overlays
- Located at line 4750: `Config.DEBUG_INFINITE_RESOURCES = not Config.DEBUG_INFINITE_RESOURCES`

**Needed Additions:**

#### A. Skill Testing Mode
```python
# Add to debug mode toggle (around line 4750)
if event.key == pygame.K_F2:  # F2 for skills
    # Learn all skills from JSON
    skill_db = SkillDatabase.get_instance()
    for skill_id in skill_db.skills.keys():
        self.character.skills.learn_skill(skill_id)
    # Equip first 6 skills to hotbar
    for i, skill_id in enumerate(list(skill_db.skills.keys())[:6]):
        self.character.skills.equip_skill(skill_id, i)
    self.add_notification("Debug: All skills learned!", (255, 215, 0))
```

#### B. Title Testing Mode
```python
# Add to debug mode (around line 4752)
if event.key == pygame.K_F3:  # F3 for titles
    # Grant all titles from JSON
    title_db = TitleDatabase.get_instance()
    for title in title_db.titles.values():
        if title not in self.character.titles.earned_titles:
            self.character.titles.earned_titles.append(title)
    self.add_notification(f"Debug: Granted {len(title_db.titles)} titles!", (255, 215, 0))
```

#### C. Max Stats/Level
```python
# Add to debug mode (around line 4754)
if event.key == pygame.K_F4:  # F4 for max level/stats
    self.character.leveling.level = 30
    self.character.leveling.unallocated_stat_points = 30
    self.character.stats.strength = 30
    self.character.stats.defense = 30
    self.character.stats.vitality = 30
    self.character.stats.luck = 30
    self.character.stats.agility = 30
    self.character.stats.intelligence = 30
    self.character.recalculate_stats()
    self.add_notification("Debug: Max level & stats!", (255, 215, 0))
```

**Files to Modify:**
- `main.py` around lines 4750-4766 (existing debug toggle section)

---

### 6. Health Regeneration (5 HP/sec after 5s no combat)

**Specification:**
- After 5 seconds of no damage taken OR dealt
- Regenerate 5 HP per second
- Stops when damage taken/dealt resumes

**Implementation:**

#### A. Add tracking to Character class
```python
# Add to Character.__init__ (around line 2343)
self.time_since_last_damage_taken = 0.0
self.time_since_last_damage_dealt = 0.0
self.health_regen_threshold = 5.0  # 5 seconds
self.health_regen_rate = 5.0  # 5 HP per second
```

#### B. Update timing when damage occurs
```python
# In harvest_resource() when harvesting (line ~2471)
self.time_since_last_damage_dealt = 0.0

# In combat_manager when player takes damage (combat_manager.py)
# (Need to add callback to Character to reset time_since_last_damage_taken)
```

#### C. Add regeneration logic
```python
# Add new method to Character class
def update_health_regen(self, dt: float):
    """Update health regeneration"""
    self.time_since_last_damage_taken += dt
    self.time_since_last_damage_dealt += dt

    # Check if we should regenerate
    if (self.time_since_last_damage_taken >= self.health_regen_threshold and
        self.time_since_last_damage_dealt >= self.health_regen_threshold):
        if self.health < self.max_health:
            regen_amount = self.health_regen_rate * dt
            self.health = min(self.max_health, self.health + regen_amount)

# Call from GameEngine.update() (around line 6068)
self.character.update_health_regen(dt)
```

**Files to Modify:**
- `main.py` Character class (around line 2343, 2471, add new method)
- `main.py` GameEngine.update() (around line 6068)
- `Combat/combat_manager.py` when player takes damage

---

## Summary of Files to Modify

| File | Lines | Change |
|------|-------|--------|
| main.py | 2090-2129 | Implement SkillDefinition & SkillDatabase.load_from_file() |
| main.py | 2343 | Add health regen tracking fields to Character.__init__ |
| main.py | 2471 | Reset damage dealt timer in harvest_resource() |
| main.py | ~2540 | Add Character.update_health_regen(dt) method |
| main.py | 4750-4766 | Add F2/F3/F4 debug modes for skills/titles/stats |
| main.py | 6068 | Call character.update_health_regen(dt) in GameEngine.update() |
| Combat/combat_manager.py | ~400 | Reset damage taken timer when player takes damage |

---

## Testing Checklist

- [ ] Enchanting: Click items to select them
- [ ] Recipe scrolling: Mouse wheel scrolls recipe list
- [ ] Skills: F2 grants all skills from JSON
- [ ] Titles: F3 grants all titles from JSON
- [ ] Stats: F4 maxes out level and stats
- [ ] Health regen: Wait 5s without combat, health regenerates at 5 HP/s
- [ ] Health regen stops: Take/deal damage, regen stops

---

## Priority Order

1. **HIGH**: Implement SkillDatabase.load_from_file() - User wants skills from JSON
2. **HIGH**: Add debug modes (F2/F3/F4) - User specifically requested for testing
3. **MEDIUM**: Health regeneration - Quality of life feature
4. **VERIFY**: Enchanting fix - Already done, needs testing
5. **VERIFY**: Recipe scrolling - Already working, needs testing
6. **VERIFY**: Title loading - Should already work, needs verification

---

**Next Session:** Focus on implementing the Skill system properly and adding the debug modes.
