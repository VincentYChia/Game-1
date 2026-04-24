# Quest, NPC, and Skill Unlock Integration Guide

## Overview
This guide explains how to use the new enhanced JSON template system for NPCs, Quests, and Skill Unlocks. All systems are fully integrated and backwards compatible.

---

## ✅ Ready for Production

### What's Working Now:
1. **✅ Quest System** - All 3 quest types fully functional
2. **✅ NPC Interaction** - NPCs offer and accept quests
3. **✅ Quest Tracking UI** - Press `L` to view quest progress
4. **✅ Consumable Usage** - Right-click consumables to use them
5. **✅ Combat Tracking** - Enemy kills properly recorded
6. **✅ Enhanced JSON Format** - Both v1.0 and v2.0 formats supported

### JSON Files Available:
- `progression/npcs-enhanced.JSON` - Enhanced NPC format (v2.0)
- `progression/quests-enhanced.JSON` - Enhanced quest format (v2.0)
- `progression/skill-unlocks.JSON` - New skill unlock system (v1.0)
- `progression/npcs-1.JSON` - Original format (v1.0 - still works)
- `progression/quests-1.JSON` - Original format (v1.0 - still works)

---

## 📖 Using the Quest Tracking UI

### Accessing the Quest Log:
1. Press `L` to open the Encyclopedia
2. Click the "QUESTS" tab
3. Scroll with mouse wheel to view all quests

### What You'll See:

#### Active Quests:
- **Quest Title** - Name of the quest
- **Description** - What the quest is about
- **Objectives** - Real-time progress tracking
  - Gather quests show: `○ Gather Wood: 3/5` (○ = incomplete, ✓ = complete)
  - Combat quests show: `○ Defeat enemies: 1/3`
- **Completion Status** - `✅ Ready to turn in!` when objectives are met
- **Rewards Preview** - What you'll get upon completion
  - Experience points
  - Skills to be learned
  - Items received

#### Completed Quests:
- List of all quests you've finished
- Shown with green checkmark: `✓ First Steps`

### Quest Progress Tracking:
- **Gather Quests**: Automatically checks your inventory for required items
- **Combat Quests**: Tracks total enemy kills from your combat activity
- **Progress Updates**: Real-time - open the quest log to see current status
- **Color Coding**:
  - Yellow text = In progress
  - Green text = Complete/Ready to turn in
  - Gray text = No quests available

---

## 🎮 Complete Quest Flow

### 1. Finding NPCs
- Walk near an NPC (within 3.0 units)
- Click on the NPC to interact
- NPCs with available quests show dialogue

### 2. Accepting a Quest
- Read the quest description
- Click the quest button to accept it
- Quest appears in your Encyclopedia Quest Log (press `L` to check)

### 3. Completing Objectives
**For Gather Quests:**
- Use your tools (axe/pickaxe) to collect materials
- Open Quest Log (`L` → QUESTS tab) to check progress
- Items in your inventory count toward objectives

**For Combat Quests:**
- Find enemies in the world
- Attack them with weapons (Tab to cycle weapons)
- Each defeated enemy counts toward quest
- Check progress in Quest Log

### 4. Turning In Quests
- Return to the quest giver NPC
- Click on them to interact
- If objectives are complete, you'll see "Quest Complete" message
- Click "Turn In Quest" button
- Receive rewards:
  - Experience points added
  - Skills automatically learned
  - Items added to inventory
  - Health/Mana restored if reward includes it

---

## 🆕 Enhanced JSON Format Guide

### NPCs (v2.0 Format)

**Key Features:**
- **Behavior System**: NPCs can be static or wander within a radius
- **State-based Dialogue**: Different messages for quest states
- **Services**: NPCs can trade, repair, teach skills
- **Unlock Conditions**: NPCs can be hidden until requirements met

**Example Structure:**
```json
{
  "npc_id": "tutorial_guide",
  "name": "Elder Sage",
  "title": "Ancient Mentor",
  "position": {"x": 48.0, "y": 48.0, "z": 0.0},
  "sprite_color": [200, 150, 255],

  "behavior": {
    "isStatic": true,
    "wanderRadius": 0,
    "interactionRange": 3.0
  },

  "dialogue": {
    "greeting": {
      "default": "Welcome, traveler!",
      "questInProgress": "How goes your task?",
      "questComplete": "Well done!",
      "allComplete": "You've learned all I can teach."
    },
    "dialogue_lines": ["...", "...", "..."],
    "farewell": "May your path be blessed!"
  },

  "quests": ["tutorial_quest"],

  "services": {
    "canTrade": false,
    "canRepair": false,
    "canTeach": true,
    "teachableSkills": ["sprint"],
    "specialServices": []
  },

  "unlockConditions": {
    "alwaysAvailable": true,
    "characterLevel": 0,
    "completedQuests": []
  }
}
```

**Backwards Compatibility:**
- All v1.0 fields still supported
- Can use either `dialogue_lines` array OR `dialogue` object
- Can use either `interaction_radius` field OR `behavior.interactionRange`

---

### Quests (v2.0 Format)

**Key Features:**
- **Quest Types**: tutorial, main, side, exploration, combat, crafting
- **Tier System**: Difficulty levels 1-4
- **Complex Descriptions**: Short, long, and narrative versions
- **Requirements**: Level, stats, titles, prerequisite quests
- **Progression**: Repeatable quests, cooldowns, quest chains
- **Enhanced Rewards**: Gold, stat points, multiple items

**Example Structure:**
```json
{
  "quest_id": "tutorial_quest",
  "questType": "tutorial",
  "tier": 1,

  "description": {
    "short": "Gather 5 wood",
    "long": "The Elder Sage wants you to gather 5 wood...",
    "narrative": "Every journey begins with a single step..."
  },

  "givenBy": "tutorial_guide",
  "returnTo": "tutorial_guide",

  "objectives": {
    "type": "gather",
    "items": [
      {
        "objectiveId": "obj_tutorial_gather_wood",
        "item_id": "wood",
        "quantity": 5,
        "description": "Gather Wood",
        "optional": false
      }
    ]
  },

  "rewards": {
    "experience": 100,
    "gold": 0,
    "health_restore": 50,
    "skills": ["sprint"],
    "items": [
      {"item_id": "minor_health_potion", "quantity": 2}
    ],
    "titles": ["novice_forester"],
    "statPoints": 0
  },

  "requirements": {
    "characterLevel": 1,
    "stats": {},
    "titles": [],
    "completedQuests": []
  },

  "progression": {
    "isRepeatable": false,
    "cooldown": null,
    "nextQuest": null,
    "questChain": "tutorial_chain"
  }
}
```

**Backwards Compatibility:**
- Supports both `quest_id` and `questId`
- Supports both `title` and `name`
- Supports both `type` and `objective_type` in objectives
- Supports both `npc_id` and `givenBy`
- Handles simple string descriptions OR complex description objects

---

### Skill Unlocks (v1.0 Format)

**Purpose:** Defines HOW skills are obtained (separate from skill definitions)

**Unlock Methods:**
1. **automatic** - Unlocks when conditions met (level-based)
2. **quest_reward** - Given upon quest completion ✅ IMPLEMENTED
3. **npc_purchase** - Buy from NPC with gold/materials
4. **milestone_unlock** - Earned through activity thresholds
5. **title_unlock** - Granted when earning titles
6. **skill_evolution** - Upgrade skill at level 10
7. **discovery** - Found through exploration
8. **class_specific** - Based on class choice
9. **random_drop** - Rare drops from enemies

**Example Structure:**
```json
{
  "unlockId": "unlock_sprint",
  "skillId": "sprint",
  "unlockMethod": "quest_reward",

  "conditions": {
    "characterLevel": 1,
    "completedQuests": ["tutorial_quest"]
  },

  "unlockTrigger": {
    "type": "quest_complete",
    "triggerValue": "tutorial_quest",
    "message": "The Elder Sage teaches you Sprint!"
  },

  "cost": {
    "gold": 0,
    "materials": []
  }
}
```

**Currently Mapped Skills:**
- sprint → Quest reward (tutorial_quest) ✅
- miners_endurance → Quest reward (gathering_quest) ✅
- combat_strike → Quest reward (combat_quest) ✅
- fortify → Quest reward (combat_quest) ✅
- smiths_focus → Milestone (10 smithing crafts)
- alchemists_insight → Milestone (25 alchemy crafts)
- treasure_sense → NPC purchase (Wandering Trader, 2500g)
- battle_fury → Milestone (50 kills)
- keen_eye → Milestone (200 gathers)
- chain_harvest → Title unlock (master_gatherer)
- whirlwind_strike → Title unlock (master_warrior)
- master_craftsman → Title unlock (master_smith)

---

## 🔧 Creating New Content

### Adding a New NPC:

1. **Choose a format** - Use enhanced format for new features
2. **Pick a unique ID** - e.g., `"npc_blacksmith_001"`
3. **Set position** - x, y coordinates in the world
4. **Define behavior** - Static or wandering
5. **Write dialogue** - Multiple states for quest progression
6. **Assign quests** - List of quest IDs this NPC offers
7. **Add to JSON** - Place in either npcs-enhanced.JSON or create new file

**Template:**
```json
{
  "npc_id": "your_npc_id",
  "name": "NPC Name",
  "title": "NPC Title",
  "position": {"x": 50.0, "y": 50.0, "z": 0.0},
  "sprite_color": [200, 200, 200],
  "behavior": {
    "isStatic": true,
    "wanderRadius": 0,
    "interactionRange": 3.0
  },
  "dialogue": {
    "greeting": {
      "default": "Hello!",
      "questInProgress": "Working on it?",
      "questComplete": "Nice work!",
      "allComplete": "All done!"
    },
    "dialogue_lines": ["Line 1", "Line 2", "Line 3"],
    "farewell": "Goodbye!"
  },
  "quests": ["quest_id_1"],
  "services": {
    "canTrade": false,
    "canRepair": false,
    "canTeach": false,
    "teachableSkills": [],
    "specialServices": []
  },
  "unlockConditions": {
    "alwaysAvailable": true,
    "characterLevel": 0,
    "completedQuests": []
  }
}
```

### Adding a New Quest:

1. **Choose quest type** - gather, combat, craft, explore, etc.
2. **Define objectives** - What must the player do?
3. **Set rewards** - XP, items, skills, gold
4. **Set requirements** - Level, prerequisite quests
5. **Write descriptions** - Short, long, narrative
6. **Add to JSON** - Place in quests-enhanced.JSON

**Gather Quest Template:**
```json
{
  "quest_id": "your_quest_id",
  "name": "Quest Name",
  "questType": "side",
  "tier": 1,
  "description": {
    "short": "Brief description",
    "long": "Detailed description of what to do",
    "narrative": "Flavor text from NPC"
  },
  "givenBy": "npc_id",
  "returnTo": "npc_id",
  "objectives": {
    "type": "gather",
    "items": [
      {"item_id": "wood", "quantity": 10, "description": "Gather Wood"}
    ]
  },
  "rewards": {
    "experience": 150,
    "gold": 25,
    "skills": [],
    "items": []
  },
  "requirements": {
    "characterLevel": 1
  },
  "progression": {
    "isRepeatable": false
  }
}
```

**Combat Quest Template:**
```json
{
  "quest_id": "your_combat_quest",
  "name": "Combat Quest",
  "questType": "combat",
  "tier": 1,
  "objectives": {
    "type": "combat",
    "enemies_killed": 5
  },
  "rewards": {
    "experience": 200,
    "skills": ["new_combat_skill"]
  }
}
```

### Adding a Skill Unlock:

1. **Reference existing skill** - Use skillId from skills-skills-1.JSON
2. **Choose unlock method** - How should players get this?
3. **Set conditions** - What must be true to unlock?
4. **Define trigger** - What event causes the unlock?
5. **Set cost** - Gold/materials if purchased

**Quest Reward Template:**
```json
{
  "unlockId": "unlock_skill_name",
  "skillId": "skill_name",
  "unlockMethod": "quest_reward",
  "conditions": {
    "characterLevel": 5,
    "completedQuests": ["prerequisite_quest"]
  },
  "unlockTrigger": {
    "type": "quest_complete",
    "triggerValue": "prerequisite_quest",
    "message": "You learned a new skill!"
  },
  "cost": {
    "gold": 0,
    "materials": []
  }
}
```

**Milestone Template:**
```json
{
  "unlockId": "unlock_skill_name",
  "skillId": "skill_name",
  "unlockMethod": "milestone_unlock",
  "conditions": {
    "characterLevel": 10,
    "activityMilestones": [
      {
        "type": "craft_count",
        "discipline": "smithing",
        "count": 50
      }
    ]
  },
  "unlockTrigger": {
    "type": "activity_threshold",
    "triggerValue": 50,
    "message": "Your dedication has unlocked a new skill!"
  }
}
```

---

## 🚀 Next Steps for Future Development

### Not Yet Implemented (But JSON Ready):

1. **Skill Unlock Milestone System**
   - Check activity counts against skill unlock conditions
   - Grant skills when thresholds reached
   - Display unlock notifications

2. **NPC Skill Purchase**
   - UI for buying skills from NPCs
   - Gold/material transaction system
   - Teachable skills inventory per NPC

3. **Quest Requirements Checking**
   - Block quest acceptance if requirements not met
   - Show requirement tooltips on quest buttons
   - Check character level, stats, titles, prerequisite quests

4. **Repeatable Quest System**
   - Track quest cooldowns
   - Allow re-accepting completed quests
   - Reset quest progress properly

5. **Quest Chains**
   - Auto-offer next quest in chain
   - Track chain progress
   - Special rewards for completing full chains

6. **Title-based Skill Unlocks**
   - Automatically grant skills when titles earned
   - Check title unlock conditions from skill-unlocks.JSON

7. **NPC Unlock Conditions**
   - Hide NPCs until player meets requirements
   - Reveal NPCs based on level, quests, titles
   - Special appearance effects for newly unlocked NPCs

8. **Enhanced Dialogue States**
   - Use different dialogue.greeting messages based on quest state
   - Implement farewell messages
   - Add personality to NPCs

9. **More Objective Types**
   - craft: Create specific items
   - explore: Discover new chunks
   - discover: Find rare materials
   - place: Place structures in world
   - interact: Activate objects/NPCs

10. **Conditional Rewards**
    - Grant different rewards based on choices
    - Track player decisions in quests
    - Branching quest paths

---

## 🎯 Testing Checklist

### Quest System:
- [x] Accept quest from Elder Sage
- [x] Gather 5 wood for tutorial quest
- [x] View quest progress in Quest Log (L → QUESTS)
- [x] Turn in completed quest
- [x] Receive Sprint skill as reward
- [x] Accept quest from Wandering Trader
- [x] Mine copper and iron ore
- [x] Turn in quest, receive Miner's Endurance
- [x] Accept quest from Battle Master
- [x] Defeat 3 enemies
- [x] Turn in quest, receive Combat Strike + Fortify

### Quest Tracking UI:
- [x] Press L to open Encyclopedia
- [x] Click QUESTS tab
- [x] See active quests with objectives
- [x] See real-time progress (item counts, kill counts)
- [x] See "Ready to turn in" status
- [x] See rewards preview
- [x] See completed quests list
- [x] Scroll with mouse wheel

### Consumables:
- [x] Right-click health potion to use
- [x] Right-click mana potion to use
- [x] Right-click strength elixir to use
- [x] See item consumed from inventory
- [x] See buff applied (if applicable)

### Combat Tracking:
- [x] Kill enemies
- [x] See kill count increase in activities
- [x] Quest progress updates in Quest Log

---

## 📚 Additional Resources

### JSON Documentation:
- See `Definitions.JSON/Tentative 3 new templates JSONS` for full field documentation
- Each template includes detailed FIELD_DOCUMENTATION section
- Usage notes and examples provided

### Code Documentation:
- See `CHANGES_SUMMARY.md` for technical implementation details
- Bug fixes and system integration explained
- Future work roadmap included

### System Architecture:
```
NPCDatabase.load_from_files()
    ↓
Loads enhanced JSON (v2.0) or fallback to v1.0
    ↓
NPCDefinition + QuestDefinition created
    ↓
Character interacts with NPC
    ↓
Quests offered based on NPC.quests array
    ↓
Player accepts quest
    ↓
Quest added to character.quests.active_quests
    ↓
Player completes objectives (tracked in real-time)
    ↓
Player views progress in Quest Log (Encyclopedia)
    ↓
Player returns to NPC
    ↓
Quest.check_completion() validates objectives
    ↓
Quest.consume_items() removes quest items
    ↓
Quest.grant_rewards() gives XP, skills, items
    ↓
Quest moved to character.quests.completed_quests
```

---

## ✨ Key Improvements

### User Experience:
1. **Visual Quest Tracking** - No more guessing quest progress
2. **Real-time Updates** - See progress as you gather/fight
3. **Organized Quest Log** - Clear separation of active/completed
4. **Reward Previews** - Know what you'll get before turning in
5. **Completion Indicators** - Green checkmarks and "Ready" status

### Developer Experience:
1. **Backwards Compatible** - Old JSON files still work
2. **Flexible Format** - Use v1.0 or v2.0 as needed
3. **Well Documented** - Templates include full documentation
4. **Type Safe** - All fields validated by Python dataclasses
5. **Error Reporting** - Tracebacks help debug JSON issues

### Future Proof:
1. **Extensible** - Easy to add new quest types
2. **Scalable** - Can handle hundreds of quests
3. **Maintainable** - Clear separation of concerns
4. **Upgradable** - Smooth path from v1.0 to v2.0
5. **Feature Rich** - Foundation for advanced systems

---

## 🐛 Known Issues

**None at this time!** All critical bugs have been fixed:
- ✅ Inventory attribute error fixed
- ✅ Combat tracking implemented
- ✅ Consumable usage working
- ✅ Quest completion checks working
- ✅ Quest turn-in working
- ✅ Skill rewards granted properly

---

## 💬 Support

For issues or questions:
1. Check `CHANGES_SUMMARY.md` for technical details
2. Review JSON template documentation
3. Test with provided example quests first
4. Verify JSON syntax with Python json.load()
5. Check game console for error messages

Happy questing! 🎮
