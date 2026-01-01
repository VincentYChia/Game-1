# JSON Template Library - Game-1

Generated: 2026-01-01 19:58:33

## Overview

- **Total Categories**: 24
- **Total Unique Tags**: 498
- **Total Material IDs**: 90
- **Total Skill IDs**: 6
- **Total Recipe IDs**: 4

---

## Categories

### chunk-templates
**Description**: World generation templates
**Files**: Chunk-templates-1.JSON
**Total Fields**: 131
**Root Keys Found**: metadata, templates

**Key Fields**:
- `category` (string): peaceful, dangerous, rare
- `chunkType` (string): dangerous_forest, dangerous_quarry, dangerous_cave
- `enemySpawns` (object): 
- `enemySpawns.beetle_armored` (object): 
- `enemySpawns.beetle_armored.behavior` (string): aggressive_guard, aggressive_territory
- `enemySpawns.beetle_armored.density` (string): high, low, moderate
- `enemySpawns.beetle_brown` (object): 
- `enemySpawns.beetle_brown.behavior` (string): territorial, docile_wander
- `enemySpawns.beetle_brown.density` (string): very_low, moderate
- `enemySpawns.entity_primordial` (object): 
- `enemySpawns.entity_primordial.behavior` (string): boss_encounter
- `enemySpawns.entity_primordial.density` (string): very_low
- `enemySpawns.golem_crystal` (object): 
- `enemySpawns.golem_crystal.behavior` (string): aggressive_guard
- `enemySpawns.golem_crystal.density` (string): low
- `enemySpawns.golem_stone` (object): 
- `enemySpawns.golem_stone.behavior` (string): boss_encounter
- `enemySpawns.golem_stone.density` (string): low
- `enemySpawns.slime_acid` (object): 

---

### classes
**Description**: Starting class definitions
**Files**: classes-1.JSON
**Total Fields**: 65
**Root Keys Found**: classSwitching, classes, designNotes, metadata, statDescriptions

**Key Fields**:
- `classId` (string): warrior, adventurer, scavenger
- `classSwitching` (object): 
- `classSwitching.changedOnSwitch` (array): Starting skill (if applicable), Active class bonuses (old removed, new applied)
- `classSwitching.confirmationRequired` (boolean): True
- `classSwitching.cost` (integer): 1000
- `classSwitching.currency` (string): gold
- `classSwitching.description` (string): Players can switch classes at any time by paying a
- `classSwitching.restrictions` (object): 
- `classSwitching.restrictions.cooldown` (integer): 0
- `classSwitching.restrictions.minimumLevel` (integer): 1
- `classSwitching.restrictions.requiresNPC` (boolean): False
- `classSwitching.retainedOnSwitch` (array): All equipped gear, All inventory items, All skill levels and experience
- `description` (string): Intellectuals who master alchemy and magical arts., Balanced generalists who dabble in everything. Adv, Masters of combat and physical might. Warriors exc
- `designNotes` (object): 
- `designNotes.balance` (string): All numerical values are placeholders subject to b
- `designNotes.classDiversity` (string): Each class provides distinct starting advantages
- `designNotes.permanentProgression` (string): Most progression is retained across class switches
- `designNotes.switchingPhilosophy` (string): Simple cost-based system encourages experimentatio
- `name` (string): Artisan, Scholar, Ranger

---

### combat-config
**Description**: Combat configuration
**Files**: combat-config.JSON
**Total Fields**: 71
**Root Keys Found**: combatMechanics, damageFormulas, enemyRespawn, experienceRewards, metadata, safeZone, spawnRates

**Key Fields**:
- `combatMechanics` (object): 
- `combatMechanics.baseAttackCooldown` (number): 1.0
- `combatMechanics.combatTimeout` (number): 5.0
- `combatMechanics.comment` (string): Combat timeout = seconds of no damage before regen
- `combatMechanics.enemyCorpseLifetime` (integer): 60
- `combatMechanics.playerAttackRange` (number): 2.0
- `combatMechanics.toolAttackCooldown` (number): 0.5
- `damageFormulas` (object): 
- `damageFormulas.comment` (string): Formulas are for reference, implemented in code
- `damageFormulas.critMultiplier` (number): 2.0
- `damageFormulas.enemyDamage` (string): enemyBaseDamage * (1 - (DEF * 0.02 + armorBonus))
- `damageFormulas.playerDamage` (string): weaponDamage * (1 + STR * 0.05) * titleBonus * equ
- `enemyRespawn` (object): 
- `enemyRespawn.baseRespawnTime` (integer): 300
- `enemyRespawn.bossRespawnTime` (integer): 1800
- `enemyRespawn.comment` (string): Respawn times in seconds
- `enemyRespawn.tierMultipliers` (object): 
- `enemyRespawn.tierMultipliers.tier1` (number): 1.0
- `enemyRespawn.tierMultipliers.tier2` (number): 1.5
- `enemyRespawn.tierMultipliers.tier3` (number): 2.0

---

### crafting-stations
**Description**: Crafting station definitions
**Files**: crafting-stations-1.JSON
**Total Fields**: 21
**Root Keys Found**: metadata, stations

**Key Fields**:
- `category` (string): station
- `flags` (object): 
- `flags.placeable` (boolean): True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): False
- `itemId` (string): forge_t2, engineering_bench_t2, alchemy_table_t2
- `metadata` (object): 
- `metadata.narrative` (string): Legendary forge that bends reality itself. Can wor, Improved forge with reinforced stone and efficient, Precision engineering station with specialized too
- `metadata.tags` (array): starter, station, engineering
- `name` (string): Basic Alchemy Table, Reinforced Forge, Basic Engineering Bench
- `range` (integer): 0
- `rarity` (string): rare, epic, uncommon
- `requirements` (object): 
- `requirements.level` (integer): 1, 8, 10
- `stats` (object): 
- `stats.durability` (array): 9999
- `stats.weight` (number): 65.0, 35.0, 100.0
- `subtype` (string): engineering, smithing, refining
- `tier` (integer): 1, 2, 3

---

### hostiles
**Description**: Enemy and ability definitions
**Files**: hostiles-1.JSON, hostiles-testing-integration.JSON, hostiles-testing-integration.JSON
**Total Fields**: 138
**Root Keys Found**: abilities, enemies, metadata

**Key Fields**:
- `abilityId` (string): crystal_beam, wing_buffet, reality_warp
- `ai` (object): 
- `ai.aggroRange` (number): 12.0, 14.0, 15.0
- `ai.attackCooldown` (number): 1.8, 2.0, 1.5
- `ai.behavior` (string): aggressive
- `ai.chaseRange` (number): 18.0, 20.0
- `aiPattern` (object): 
- `aiPattern.aggroOnDamage` (boolean): True
- `aiPattern.aggroOnProximity` (boolean): False, True
- `aiPattern.callForHelpRadius` (integer, number): 0, 8, 10
- `aiPattern.defaultState` (string): guard, wander, patrol
- `aiPattern.fleeAtHealth` (integer, number): 0.2, 0, 0.3
- `aiPattern.packCoordination` (boolean): False, True
- `aiPattern.specialAbilities` (array): crystal_beam, wing_buffet, reality_warp
- `behavior` (string): territorial, aggressive_ranged, aggressive_melee
- `category` (string): beast, aberration, undead
- `cooldown` (number): 35.0, 40.0, 8.0
- `drops` (array): 
- `drops[]` (object): 

---

### items
**Description**: Processed materials (ingots, planks, alloys)
**Files**: items-refining-1.JSON, items-engineering-1.JSON, items-alchemy-1.JSON, items-materials-1.JSON, items-smithing-2.JSON, items-tools-1.JSON
**Total Fields**: 68
**Root Keys Found**: accessories, alloys, armor, basic_ingots, bombs, materials, metadata, potions_buff, potions_healing, potions_resistance, stations, tools, traps, turrets, utility_consumables, utility_devices, weapons, wood_planks

**Key Fields**:
- `attributes` (array): 
- `attributes[]` (object): 
- `attributes[].effect` (string): Adds lightning damage to attacks, Adds fire damage to attacks, Items crafted with this add fire damage
- `attributes[].element` (string): lightning, fire, frost
- `attributes[].type` (string): damage, elemental
- `attributes[].value` (integer): 10, 20, 5
- `category` (string): station, elemental, material
- `duration` (integer): 0, 480, 7200
- `effect` (string): Explodes for 75 fire damage + lingering flames, Triggers on contact, 25 damage + immobilize for 5 , +25% movement and attack speed
- `effectParams` (object): 
- `effectParams.baseDamage` (integer): 35, 37, 70
- `effectParams.beam_range` (number): 12.0
- `effectParams.beam_width` (number): 1.0
- `effectParams.bleed_damage_per_second` (number): 3.0
- `effectParams.bleed_duration` (number): 8.0
- `effectParams.burn_damage_per_second` (number): 8.0, 5.0
- `effectParams.burn_duration` (number): 3.0, 5.0, 6.0
- `effectParams.chain_count` (integer): 2
- `effectParams.chain_range` (number): 5.0

---

### items-testing
**Description**: Test items for tag validation
**Files**: items-testing-integration.JSON, items-testing-tags.JSON, items-testing-integration.JSON
**Total Fields**: 71
**Root Keys Found**: metadata, test_devices, test_edge_cases, test_weapons

**Key Fields**:
- `category` (string): device, equipment, weapon
- `description` (string): Whip that arcs lightning between foes, Blade that projects waves of flame, Cursed blade that feeds on lifeblood
- `effect` (string): Massive explosion with huge radius, Basic turret with no tag system support, Fires a burning laser beam
- `effectParams` (object): 
- `effectParams.baseDamage` (number): 35.0, 5.0, 70.0
- `effectParams.beam_length` (number): 15.0
- `effectParams.beam_width` (number): 1.0
- `effectParams.burn_damage_per_second` (number): 10.0, 5.0, 15.0
- `effectParams.burn_duration` (number): 10.0, 5.0, 6.0
- `effectParams.chain_count` (integer): 3, 4
- `effectParams.chain_damage_falloff` (number): 0.8, 0.9
- `effectParams.chrono_slow` (number): 0.5
- `effectParams.circle_radius` (number): 3.0, 20.0, 5.0
- `effectParams.cone_angle` (integer): 60, 45
- `effectParams.cone_length` (number): 8.0, 10.0
- `effectParams.freeze_duration` (number): 2.0, 3.0
- `effectParams.quantum_collapse_chance` (number): 0.1
- `effectParams.range` (number): 10.0, 15.0
- `effectParams.root_duration` (number): 3.0

---

### npcs
**Description**: NPC definitions
**Files**: npcs-enhanced.JSON, npcs-1.JSON
**Total Fields**: 37
**Root Keys Found**: metadata, npcs

**Key Fields**:
- `behavior` (object): 
- `behavior.interactionRange` (number): 3.0
- `behavior.isStatic` (boolean): False, True
- `behavior.wanderRadius` (integer, number): 0, 5.0
- `dialogue` (object): 
- `dialogue.dialogue_lines` (array): Perhaps you could assist me?, Welcome, traveler! I sense great potential within , The wilds are dangerous, but I can help you prepar
- `dialogue.farewell` (string): May your path be blessed with fortune!, Safe travels, and may you find rare treasures!, Fight with honor!
- `dialogue.greeting` (object): 
- `dialogue.greeting.allComplete` (string): You are now a true warrior. Continue your training, You've learned all I can teach. Go forth and explo, Your aid has been invaluable, friend.
- `dialogue.greeting.default` (string): Greetings! I've traveled far and wide seeking rare, Ho there, warrior! Ready to test your mettle?, Welcome, traveler! I sense great potential within 
- `dialogue.greeting.questComplete` (string): Excellent! Those will serve my research perfectly., Impressive! You've earned my respect and rewards., Well done! Return to me when ready to claim your r
- `dialogue.greeting.questInProgress` (string): How goes your task? The forest awaits your efforts, Have you found those materials yet? I await eagerl, Go forth and prove yourself in battle!
- `dialogue_lines` (array): Perhaps you could assist me?, Welcome, traveler! I sense great potential within , The wilds are dangerous, but I can help you prepar
- `interaction_radius` (number): 3.0
- `metadata` (object): 
- `metadata.narrative` (string): The Elder Sage has guided countless travelers on t, A mysterious figure who wanders the lands collecti, A veteran warrior who trains adventurers in the ar
- `metadata.tags` (array): wandering, trader, starter
- `name` (string): Wandering Trader, Battle Master, Elder Sage
- `npc_id` (string): tutorial_guide, combat_trainer, mysterious_trader

---

### other-crafting-subdisciplines
**Description**: Other files from Crafting-subdisciplines
**Files**: rarity-modifiers.JSON
**Total Fields**: 180
**Root Keys Found**: armor, consumable, device, metadata, station, tool, weapon

**Key Fields**:
- `armor` (object): 
- `armor.common` (object): 
- `armor.common.description` (string): Basic armor with no bonuses
- `armor.common.modifiers` (object): 
- `armor.epic` (object): 
- `armor.epic.description` (string): Exceptional armor with knockback resistance and en
- `armor.epic.modifiers` (object): 
- `armor.epic.modifiers.damage_reduction` (number): 0.05
- `armor.epic.modifiers.defense` (number): 0.35
- `armor.epic.modifiers.durability` (number): 0.2
- `armor.epic.modifiers.resistance` (number): 0.1
- `armor.epic.special_effects` (object): 
- `armor.epic.special_effects.enhanced_durability` (boolean): True
- `armor.epic.special_effects.knockback_resistance` (boolean): True
- `armor.legendary` (object): 
- `armor.legendary.description` (string): Legendary armor with damage boost and thorns effec
- `armor.legendary.modifiers` (object): 
- `armor.legendary.modifiers.damage_reduction` (number): 0.1
- `armor.legendary.modifiers.defense` (number): 1.0
- `armor.legendary.modifiers.durability` (number): 0.3

---

### other-game-1-modular
**Description**: Other files from Game-1-modular
**Files**: updates_manifest.json
**Total Fields**: 0
**Root Keys Found**: installed_updates, last_updated, notes, schema_version, version

**Key Fields**:

---

### placements
**Description**: Minigame grid placement patterns
**Files**: placements-refining-1.JSON, placements-engineering-1.JSON, placements-smithing-1.JSON, placements-adornments-1.JSON, placements-alchemy-1.JSON
**Total Fields**: 528
**Root Keys Found**: metadata, placements

**Key Fields**:
- `coreInputs` (array): 
- `coreInputs[]` (object): 
- `coreInputs[].materialId` (string): orichalcum_ingot, steel_ore, limestone
- `coreInputs[].quantity` (integer): 1, 2, 3
- `coreInputs[].rarity` (string): rare, epic, uncommon
- `ingredients` (array): 
- `ingredients[]` (object): 
- `ingredients[].materialId` (string): beetle_carapace, wolf_pelt, limestone
- `ingredients[].quantity` (integer): 1, 2, 3
- `ingredients[].slot` (integer): 1, 2, 3
- `metadata` (object): 
- `metadata.gridSize` (string): 3x3, 5x5, 7x7
- `metadata.narrative` (string): Crafting a warhammer is about managing weight dist, Forging a steel battleaxe requires balance - too h, Simple spear with copper tip. Keep your enemies at
- `narrative` (string): Golem core provides titan strength. Storm heart ad, Infusing copper with storm. Perfect conductivity -, Teleporter folding space - etherion anchors realit
- `outputId` (string): armor_polish, fire_arrow_turret, titans_brew
- `placementMap` (object): 
- `placementMap.1,1` (string): beetle_carapace, mithril_ingot, wolf_pelt
- `placementMap.1,2` (string): ironwood_plank, beetle_carapace, oak_plank
- `placementMap.1,3` (string): ironwood_plank, beetle_carapace, mithril_ingot

---

### quests
**Description**: Quest definitions
**Files**: quests-enhanced.JSON, quests-1.JSON
**Total Fields**: 63
**Root Keys Found**: metadata, quests

**Key Fields**:
- `completion_dialogue` (array): Excellent work! You've proven yourself capable., Here, take these as payment., May your journey be prosperous!
- `description` (string, object): The Wandering Trader needs 3 copper ore and 3 iron, The Elder Sage wants you to gather 5 oak logs to p, The Battle Master challenges you to defeat 3 enemi
- `description.long` (string): The Wandering Trader needs 3 copper ore and 3 iron, The Elder Sage wants you to gather 5 oak logs to p, The Battle Master challenges you to defeat 3 enemi
- `description.narrative` (string): A warrior is defined by their deeds. Show me you c, I study the properties of metals. Help me gather s, Every journey begins with a single step. Show me y
- `description.short` (string): Collect 3 copper ore and 3 iron ore, Defeat 3 enemies, Gather 5 oak logs for the Elder Sage
- `givenBy` (string): tutorial_guide, combat_trainer, mysterious_trader
- `metadata` (object): 
- `metadata.difficulty` (string): medium, easy
- `metadata.estimatedTime` (string): 15 minutes, 10 minutes, 5 minutes
- `metadata.narrative` (string): The first quest given to all travelers. A simple t, The first true test of a warrior. Defeat enemies a, The Wandering Trader's research requires various m
- `metadata.tags` (array): warrior, starter, combat
- `name` (string): Material Research, Prove Your Worth, First Steps
- `npc_id` (string): tutorial_guide, combat_trainer, mysterious_trader
- `objectives` (object): 
- `objectives.enemies_killed` (integer): 3
- `objectives.items` (array): 
- `objectives.items[]` (object): 
- `objectives.items[].description` (string): Gather Oak Logs, Mine Copper Ore, Mine Iron Ore
- `objectives.items[].item_id` (string): oak_log, iron_ore, copper_ore

---

### recipes
**Description**: Refining recipes
**Files**: recipes-refining-1.JSON, recipes-smithing-testing.JSON, recipes-alchemy-1.JSON, recipes-enchanting-1.JSON, recipes-engineering-1.JSON, recipes-smithing-3.JSON, recipes-adornments-1.json
**Total Fields**: 46
**Root Keys Found**: metadata, recipes

**Key Fields**:
- `applicableTo` (array): accessory, tool, weapon
- `effect` (object): 
- `effect.chainCount` (integer): 2
- `effect.chainRange` (integer): 3
- `effect.conflictsWith` (array): sharpness_2, protection_1, unbreaking_1
- `effect.damagePerSecond` (integer): 8, 10
- `effect.damagePercent` (number): 0.5
- `effect.duration` (integer): 8, 4, 5
- `effect.element` (string): ice, fire, poison
- `effect.maxStacks` (integer): 3, 5
- `effect.perMinute` (boolean): True
- `effect.slowPercent` (number): 0.3
- `effect.stackable` (boolean): False, True
- `effect.type` (string): damage_reduction, harvest_original_form, bonus_yield_chance
- `effect.value` (integer, number): 0.1, 0.35, 0.6
- `enchantmentId` (string): lifesteal, fire_aspect, soulbound
- `enchantmentName` (string): Knockback, Soulbound, Lightning Strike
- `fuelRequired` (null, object): None
- `fuelRequired.materialId` (string): phoenix_ash

---

### recipes-testing
**Description**: Test recipes
**Files**: recipes-tag-tests.JSON
**Total Fields**: 18
**Root Keys Found**: metadata, recipes

**Key Fields**:
- `inputs` (array): 
- `inputs[]` (object): 
- `inputs[].materialId` (string): iron_ore, iron_ingot, slime_gel
- `inputs[].quantity` (integer): 1, 2, 3
- `metadata` (object): 
- `metadata.narrative` (string): TEST: Alchemy with EMPTY tags array, TEST: Refining with MULTIPLE bonus process tags (c, TEST: Refining with alloying tag for maximum rarit
- `metadata.tags` (array): smelting, sword, melee
- `outputId` (string): test_healing_potion, test_ultimate_sword, test_multi_effect_potion
- `outputQty` (integer): 1, 3
- `outputs` (array): 
- `outputs[]` (object): 
- `outputs[].materialId` (string): iron_ingot
- `outputs[].quantity` (integer): 1
- `outputs[].rarity` (string): common
- `recipeId` (string): test_smithing_conflicting_hands, test_refining_all_bonuses, test_alchemy_explicit_potion
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): smithing, alchemy, refining

---

### resource-nodes
**Description**: Gatherable resource node definitions
**Files**: resource-node-1.JSON
**Total Fields**: 16
**Root Keys Found**: metadata, nodes

**Key Fields**:
- `baseHealth` (integer): 200, 800, 100
- `category` (string): tree, stone, ore
- `drops` (array): 
- `drops[]` (object): 
- `drops[].chance` (string): rare, low, improbable
- `drops[].materialId` (string): obsidian, steel_ore, limestone
- `drops[].quantity` (string): abundant, several, many
- `metadata` (object): 
- `metadata.narrative` (string): Pitch-black stone that pulls light into itself. Ra, Legendary tree connected to the World Tree's root , Legendary silver-white deposits that seem to drink
- `metadata.tags` (array): metallic, impossible, advanced
- `name` (string): Birch Tree, Quartz Cluster, Orichalcum Trove
- `requiredTool` (string): axe, pickaxe
- `resourceId` (string): adamantine_lode, eternity_monolith, ebony_tree
- `respawnTime` (string, null): None, normal, very_slow
- `tier` (integer): 1, 2, 3

---

### skill-unlocks
**Description**: Skill unlock requirements
**Files**: skill-unlocks.JSON
**Total Fields**: 61
**Root Keys Found**: FIELD_DOCUMENTATION, USAGE_NOTES, metadata, skillUnlocks

**Key Fields**:
- `FIELD_DOCUMENTATION` (object): 
- `FIELD_DOCUMENTATION.conditions` (object): 
- `FIELD_DOCUMENTATION.conditions.activityMilestones` (string): Array of activity requirements
- `FIELD_DOCUMENTATION.conditions.characterLevel` (string): Minimum level required
- `FIELD_DOCUMENTATION.conditions.completedQuests` (string): Array of questIds required
- `FIELD_DOCUMENTATION.conditions.stats` (string): Object like {strength: 5, luck: 10}
- `FIELD_DOCUMENTATION.conditions.titles` (string): Array of titleIds required
- `FIELD_DOCUMENTATION.cost` (object): 
- `FIELD_DOCUMENTATION.cost.gold` (string): Gold required to unlock
- `FIELD_DOCUMENTATION.cost.materials` (string): Array of {materialId, quantity}
- `FIELD_DOCUMENTATION.cost.note` (string): Cost is paid AFTER conditions met
- `FIELD_DOCUMENTATION.cost.skillPoints` (string): Special skill points if system uses them
- `FIELD_DOCUMENTATION.skillId` (object): 
- `FIELD_DOCUMENTATION.skillId.description` (string): References skillId from Skills/skills-skills-1.JSO
- `FIELD_DOCUMENTATION.skillId.note` (string): This is the skill being unlocked
- `FIELD_DOCUMENTATION.skillId.required` (boolean): True
- `FIELD_DOCUMENTATION.unlockId` (object): 
- `FIELD_DOCUMENTATION.unlockId.description` (string): Unique identifier for this unlock definition
- `FIELD_DOCUMENTATION.unlockId.format` (string): unlock_{skill_name}

---

### skills
**Description**: Skill base effect definitions
**Files**: skills-base-effects-1.JSON, skills-skills-1.JSON
**Total Fields**: 157
**Root Keys Found**: BASE_EFFECT_TYPES, RARITY_MULTIPLIERS, metadata, skills

**Key Fields**:
- `BASE_EFFECT_TYPES` (object): 
- `BASE_EFFECT_TYPES.devastate` (object): 
- `BASE_EFFECT_TYPES.devastate.baseValue` (string): 5 tile radius
- `BASE_EFFECT_TYPES.devastate.description` (string): Creates area of effect. Damage, gathering, or effe
- `BASE_EFFECT_TYPES.devastate.magnitudeValues` (object): 
- `BASE_EFFECT_TYPES.devastate.magnitudeValues.extreme` (integer): 10
- `BASE_EFFECT_TYPES.devastate.magnitudeValues.major` (integer): 7
- `BASE_EFFECT_TYPES.devastate.magnitudeValues.minor` (integer): 3
- `BASE_EFFECT_TYPES.devastate.magnitudeValues.moderate` (integer): 5
- `BASE_EFFECT_TYPES.devastate.tags` (array): radius, combat, aoe
- `BASE_EFFECT_TYPES.devastate.typicalTier` (string): 3, 4
- `BASE_EFFECT_TYPES.devastate.useCases` (array): damage all enemies nearby, gather from 3x3 area, attack hits 5-tile radius
- `BASE_EFFECT_TYPES.elevate` (object): 
- `BASE_EFFECT_TYPES.elevate.baseValue` (string): +10% rarity upgrade chance
- `BASE_EFFECT_TYPES.elevate.description` (string): Increases rarity upgrade chance on crafts or mater
- `BASE_EFFECT_TYPES.elevate.magnitudeValues` (object): 
- `BASE_EFFECT_TYPES.elevate.magnitudeValues.extreme` (number): 0.6
- `BASE_EFFECT_TYPES.elevate.magnitudeValues.major` (number): 0.4
- `BASE_EFFECT_TYPES.elevate.magnitudeValues.minor` (number): 0.15

---

### skills-testing
**Description**: Test skills
**Files**: skills-testing-integration.JSON, skills-testing-integration.JSON
**Total Fields**: 49
**Root Keys Found**: metadata, skills

**Key Fields**:
- `categories` (array): ice, shadow, combat
- `combatParams` (object): 
- `combatParams.baseDamage` (integer): 100, 40, 45
- `combatParams.beam_range` (number): 15.0
- `combatParams.beam_width` (number): 2.0
- `combatParams.burn_damage_per_second` (number): 10.0
- `combatParams.burn_duration` (number): 12.0
- `combatParams.chain_count` (integer): 5
- `combatParams.chain_range` (number): 7.0
- `combatParams.circle_radius` (number): 8.0, 6.0, 7.0
- `combatParams.cone_angle` (number): 90.0
- `combatParams.cone_range` (number): 10.0
- `combatParams.freeze_duration` (number): 4.0
- `combatParams.knockback_distance` (number): 5.0
- `combatParams.lifesteal_percent` (number): 0.6
- `combatParams.origin` (string): source, target
- `combatParams.pierce_count` (integer): 10
- `combatParams.pull_distance` (number): 5.0
- `combatParams.shock_damage_per_tick` (number): 4.0

---

### skills-translation
**Description**: Skill translation tables
**Files**: skills-translation-table.JSON
**Total Fields**: 170
**Root Keys Found**: categoryTranslations, cooldownTranslations, durationTranslations, effectCalculations, manaCostTranslations, metadata, skillProgressionSystem, targetTranslations

**Key Fields**:
- `categoryTranslations` (object): 
- `categoryTranslations.alchemy` (object): 
- `categoryTranslations.alchemy.applicableTo` (array): potion_quality, mini_game_time, effect_strength
- `categoryTranslations.alchemy.compatibleEffects` (array): quicken, empower, pierce
- `categoryTranslations.alchemy.description` (string): Applies to alchemy mini-game
- `categoryTranslations.combat` (object): 
- `categoryTranslations.combat.applicableTo` (array): weapon_damage, critical_chance, attack_speed
- `categoryTranslations.combat.compatibleEffects` (array): regenerate, quicken, devastate
- `categoryTranslations.combat.description` (string): Applies to combat actions
- `categoryTranslations.damage` (object): 
- `categoryTranslations.damage.applicableTo` (array): elemental_damage, critical_damage, physical_damage
- `categoryTranslations.damage.compatibleEffects` (array): empower, pierce, devastate
- `categoryTranslations.damage.description` (string): Applies to all damage types
- `categoryTranslations.defense` (object): 
- `categoryTranslations.defense.applicableTo` (array): damage_reduction, armor_effectiveness
- `categoryTranslations.defense.compatibleEffects` (array): regenerate, fortify, restore
- `categoryTranslations.defense.description` (string): Applies to defensive stats
- `categoryTranslations.durability` (object): 
- `categoryTranslations.durability.applicableTo` (array): durability_consumption, repair_rate
- `categoryTranslations.durability.compatibleEffects` (array): regenerate, fortify, restore

---

### stats-calculations
**Description**: Stat calculation formulas
**Files**: stats-calculations.JSON
**Total Fields**: 277
**Root Keys Found**: attackSpeedSystem, balancingGuidelines, consumableSystem, damageSystem, defenseSystem, deviceSystem, durabilitySystem, exampleFullCalculations, gatheringSystem, globalBases, metadata, rangeSystem, raritySystem, tierMultipliers, weightSystem

**Key Fields**:
- `attackSpeedSystem` (object): 
- `attackSpeedSystem.exampleCalculation` (object): 
- `attackSpeedSystem.exampleCalculation.calculation` (string): 1.0 (base) × 1.4 (dagger type) × 1.0 (dagger subty
- `attackSpeedSystem.exampleCalculation.item` (string): Copper Dagger (T1, itemMultiplier 1.3)
- `attackSpeedSystem.formula` (string): globalBases.attackSpeed × typeMultiplier × subtype
- `attackSpeedSystem.handednessModifiers` (object): 
- `attackSpeedSystem.handednessModifiers.1H` (string): No modifier (baseline)
- `attackSpeedSystem.handednessModifiers.2H` (string): 15% slower (0.85x)
- `attackSpeedSystem.handednessModifiers.note` (string): Applied by game logic based on weapon tags, not in
- `attackSpeedSystem.handednessModifiers.versatile_1H` (string): Base speed
- `attackSpeedSystem.handednessModifiers.versatile_2H` (string): Slightly slower (0.9x) but more damage
- `attackSpeedSystem.note` (string): Attack speed in attacks per second. Higher = faste
- `attackSpeedSystem.subtypeMultipliers` (object): 
- `attackSpeedSystem.subtypeMultipliers.battle_staff` (number): 0.9
- `attackSpeedSystem.subtypeMultipliers.battleaxe` (number): 0.9
- `attackSpeedSystem.subtypeMultipliers.buckler` (number): 1.2
- `attackSpeedSystem.subtypeMultipliers.crossbow` (number): 0.6
- `attackSpeedSystem.subtypeMultipliers.dagger` (number): 1.0
- `attackSpeedSystem.subtypeMultipliers.dual_dagger` (number): 1.2
- `attackSpeedSystem.subtypeMultipliers.greataxe` (number): 0.7

---

### tag-definitions
**Description**: Master tag system definitions
**Files**: tag-definitions.JSON
**Total Fields**: 519
**Root Keys Found**: categories, conflict_resolution, context_inference, metadata, tag_definitions

**Key Fields**:
- `conflict_resolution` (object): 
- `conflict_resolution.geometry_priority` (array): beam, chain, circle
- `conflict_resolution.mutually_exclusive` (object): 
- `conflict_resolution.mutually_exclusive.1H` (array): versatile, 2H
- `conflict_resolution.mutually_exclusive.2H` (array): 1H, versatile
- `conflict_resolution.mutually_exclusive.burn` (array): freeze
- `conflict_resolution.mutually_exclusive.freeze` (array): burn
- `conflict_resolution.mutually_exclusive.versatile` (array): 1H, 2H
- `context_inference` (object): 
- `context_inference.buff` (string): ally
- `context_inference.damage` (string): enemy
- `context_inference.debuff` (string): enemy
- `context_inference.healing` (string): ally
- `tag_definitions` (object): 
- `tag_definitions.1H` (object): 
- `tag_definitions.1H.category` (string): equipment
- `tag_definitions.1H.conflicts_with` (array): versatile, 2H
- `tag_definitions.1H.description` (string): Can be equipped in mainHand OR offHand
- `tag_definitions.1H.priority` (integer): 0
- `tag_definitions.2H` (object): 

---

### templates-crafting
**Description**: Crafting templates
**Files**: templates-crafting-1.JSON
**Total Fields**: 250
**Root Keys Found**: IMPLEMENTATION_SUMMARY, disciplines, metadata

**Key Fields**:
- `IMPLEMENTATION_SUMMARY` (object): 
- `IMPLEMENTATION_SUMMARY.common_mistakes_to_avoid` (array): Using engineering-specific material names instead , Forgetting to use empty array [] instead of null f, Exceeding tier slot/grid limits
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference` (object): 
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.alchemy` (object): 
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.alchemy.data_structure` (string): ingredients array with slot numbers
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.alchemy.key_rule` (string): Order is critical, no volatility field
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.alchemy.system` (string): Sequential slots (3-9 slots)
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.engineering` (object): 
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.engineering.data_structure` (string): slots array with type designation
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.engineering.key_rule` (string): FUNCTION slot determines device type, use simple m
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.engineering.system` (string): Slot-type canvas (3-7 slots)
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.refining` (object): 
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.refining.data_structure` (string): coreInputs array + surroundingInputs array
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.refining.key_rule` (string): Multi-core must have equal quantities, no output d
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.refining.system` (string): Hub-and-spoke (core + surrounding)
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.smithing` (object): 
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.smithing.data_structure` (string): placementMap object with 'row,col' keys
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.smithing.key_rule` (string): Diagonal placement preferred, rows start at 1
- `IMPLEMENTATION_SUMMARY.discipline_quick_reference.smithing.system` (string): Grid-based (3x3 to 9x9)
- `IMPLEMENTATION_SUMMARY.file_organization_options` (object): 

---

### titles
**Description**: Achievement title definitions
**Files**: titles-1.JSON
**Total Fields**: 81
**Root Keys Found**: difficultyTiers, metadata, titleCategories, titles

**Key Fields**:
- `acquisitionMethod` (string): guaranteed_milestone, event_based_rng, hidden_discovery
- `bonuses` (object): 
- `bonuses.alloyQuality` (number): 0.25
- `bonuses.attackSpeed` (number): 0.0
- `bonuses.combatSkillExp` (number): 0.25
- `bonuses.counterChance` (number): 0.15
- `bonuses.criticalChance` (number): 0.0, 0.1, 0.2
- `bonuses.dragonDamage` (number): 0.5
- `bonuses.durabilityBonus` (number): 0.25
- `bonuses.elementalAfinity` (string): fire
- `bonuses.fireOreChance` (number): 0.15
- `bonuses.fireResistance` (number): 0.3
- `bonuses.firstTryBonus` (number): 0.0, 0.1
- `bonuses.forestryDamage` (number): 0.1
- `bonuses.forestrySpeed` (number): 0.0
- `bonuses.legendaryChance` (number): 0.05
- `bonuses.legendaryDropRate` (number): 0.1
- `bonuses.luckStat` (number): 0.25
- `bonuses.materialYield` (number): 0.1

---

### value-translations
**Description**: Qualitative to numeric mappings
**Files**: value-translation-table-1.JSON
**Total Fields**: 170
**Root Keys Found**: chanceTranslations, densityTranslations, metadata, resourceHealthByTier, respawnTranslations, sizeMultipliers, tierBiasTranslations, toolDamageByTier, toolEfficiency, yieldTranslations

**Key Fields**:
- `chanceTranslations` (object): 
- `chanceTranslations.guaranteed` (object): 
- `chanceTranslations.guaranteed.description` (string): Always drops
- `chanceTranslations.guaranteed.percentage` (integer): 100
- `chanceTranslations.guaranteed.probability` (number): 1.0
- `chanceTranslations.high` (object): 
- `chanceTranslations.high.description` (string): Very likely to drop
- `chanceTranslations.high.percentage` (integer): 75
- `chanceTranslations.high.probability` (number): 0.75
- `chanceTranslations.improbable` (object): 
- `chanceTranslations.improbable.description` (string): Very rare drop
- `chanceTranslations.improbable.percentage` (integer): 3
- `chanceTranslations.improbable.probability` (number): 0.03
- `chanceTranslations.low` (object): 
- `chanceTranslations.low.description` (string): Unlikely but possible
- `chanceTranslations.low.percentage` (integer): 25
- `chanceTranslations.low.probability` (number): 0.25
- `chanceTranslations.moderate` (object): 
- `chanceTranslations.moderate.description` (string): 50/50 chance
- `chanceTranslations.moderate.percentage` (integer): 50

---

## All Tags (Sorted)

- `1H`
- `2H`
- `Absorbs damage`
- `Absorbs damage (alias for shield)`
- `Affects all entities`
- `Affects allies`
- `Affects allies (alias for ally)`
- `Affects construct enemies`
- `Affects enemies`
- `Affects enemies (alias for enemy)`
- `Affects mechanical enemies`
- `Affects only caster`
- `Affects players only`
- `Affects turrets/devices`
- `Affects turrets/devices (alias for turret)`
- `Affects undead enemies`
- `Always active`
- `Arcane magic damage, bypasses armor`
- `Arcs to additional nearby targets`
- `BURN`
- `Base physical damage`
- `Bonus damage below HP threshold`
- `Can be equipped in mainHand OR offHand`
- `Cannot act or move`
- `Cannot move, can still act`
- `Chaotic damage, random type each hit`
- `Close-range combat focus`
- `Cloth armor - lowest defense, magic bonuses`
- `Complete immobilization`
- `Critical hit chance and damage`
- `Fire damage over time`
- `Fire elemental damage`
- `Frontline fighter class - high HP, melee damage`
- `Frost elemental damage`
- `Heal percentage of damage dealt`
- `Heal percentage of damage dealt (alias for lifesteal)`
- `Healing over time`
- `Heavy armor - high defense, low mobility`
- `High survivability focus`
- `Hits all targets in frontal cone`
- `Hits all targets in radius`
- `Hits all targets in straight line`
- `Hits only primary target`
- `Holy damage, bonus vs undead`
- `Impact creates AOE`
- `Increased damage`
- `Increased defense`
- `Increased speed`
- `Increased speed (alias for haste)`
- `Instant movement`
- `Item creation focus`
- `Jack of all trades class - balanced versatility`
- `Light armor - low defense, high mobility`
- `Lightning elemental damage`
- `Long-range combat focus`
- `Loot hunter class - luck, rare drops, gathering`
- `Magical researcher class - mana, alchemy, arcane`
- `Magical/arcane combat focus`
- `Master crafter class - crafting speed and quality`
- `Medium armor - balanced stats`
- `Mobile gatherer class - speed, ranged, nature`
- `Movement speed reduction`
- `Movement speed reduction (alias for chill)`
- `No cast time`
- `No specialization, versatile`
- `Optional offHand, different stats when 2H`
- `Penetrates through targets`
- `Periodic damage and interrupt`
- `Physical`
- `Physical cutting damage`
- `Physical damage over time`
- `Physical impact damage, bonus vs armor`
- `Physical piercing damage, ignores some armor`
- `Physical projectile that travels`
- `Poison damage`
- `Poison damage over time`
- `Pull target toward source`
- `Push target away`
- `Rapid movement`
- `Rapid movement (alias for dash)`
- `Requires both hands, blocks offHand`
- `Requires manual activation`
- `Resource collection focus`
- `Return damage to attacker`
- `Return damage to attacker (alias for reflect)`
- `SLASHING`
- `Shadow damage`
- `Single`
- `Spawn entities`
- `Speed and evasion focus`
- `Spell-casting focus`
- `Stat reduction`
- `Temporary intangibility`
- `Triggers on critical hit`
- `Triggers when attack hits`
- `Triggers when kills target`
- `Triggers when nearby`
- `Triggers when taking damage`
- `Triggers when touched`
- `Undetectable by enemies`
- `abundance`
- `accessory`
- `adamantine`
- `adaptive`
- `additive`
- `advanced`
- `adventurer`
- `aggressive`
- `agile`
- `agility`
- `air`
- `alchemy`
- `all`
- `alloy`
- `alloying`
- `ally`
- `amulet`
- `ancient`
- `aoe`
- `arcane`
- `area`
- `armor`
- `armor_breaker`
- `armor_buff`
- `armor_type`
- `artisan`
- `ash`
- `attack_speed`
- `attract`
- `axe`
- `balanced`
- `barrier`
- `bash`
- `basic`
- `beam`
- `beetle`
- `berserker`
- `bleed`
- `bleeding`
- `blink`
- `blood`
- `blunt`
- `bomb`
- `bonus`
- `boss`
- `bow`
- `bracelet`
- `brewing`
- `bronze`
- `buff`
- `burn`
- `burning`
- `burst`
- `bypass`
- `carapace`
- `caster`
- `cave`
- `chain`
- `chance`
- `chaos`
- `charge`
- `chest`
- `chill`
- `chrono`
- `circle`
- `class`
- `cleaving`
- `cluster`
- `cold`
- `combat`
- `common`
- `composite`
- `cone`
- `confuse`
- `construct`
- `consumable`
- `context`
- `control`
- `copper`
- `cost`
- `crafting`
- `create`
- `crit`
- `critical`
- `crowd-control`
- `crushing`
- `crystal`
- `crystallization`
- `dagger`
- `damage`
- `damage_boost`
- `damage_buff`
- `damage_reduction`
- `damage_shield`
- `damage_type`
- `dangerous`
- `dark`
- `dash`
- `dazed`
- `debuff`
- `defense`
- `defense_buff`
- `defensive`
- `destruction`
- `device`
- `diminishing`
- `disable`
- `displace`
- `docile`
- `drain`
- `draw_in`
- `drops`
- `durability`
- `durable`
- `earth`
- `ebony`
- `efficiency`
- `electric`
- `elemental`
- `empower`
- `enchanting`
- `end-game`
- `enemy`
- `energy`
- `enfeeble`
- `engineering`
- `enhancement`
- `enrage`
- `entity`
- `epic`
- `equipment`
- `essence`
- `essential`
- `ethereal`
- `etherion`
- `exotic`
- `explorer`
- `explosive`
- `fang`
- `fast`
- `feet`
- `fine`
- `finisher`
- `fire`
- `fishing`
- `flexible`
- `flight`
- `forest`
- `forge`
- `forging`
- `fortify`
- `fortune`
- `freeze`
- `friendly`
- `frontline`
- `frost`
- `frozen`
- `gathering`
- `gel`
- `generalist`
- `geometry`
- `gold`
- `golem`
- `grinding`
- `hands`
- `harmony`
- `harvesting`
- `haste`
- `head`
- `heal_over_time`
- `healing`
- `health`
- `heavy`
- `hemorrhage`
- `herbs`
- `hidden`
- `hostile`
- `hot`
- `ice`
- `ignite`
- `immobilize`
- `immobilized`
- `impossible`
- `instant`
- `intangible`
- `invisible`
- `iron`
- `ironwood`
- `knockback`
- `layered`
- `leather`
- `legendary`
- `legendary-ore`
- `legendary-wood`
- `legs`
- `life_drain`
- `lifesteal`
- `light`
- `lightning`
- `line`
- `linear`
- `living`
- `luck`
- `mace`
- `magic`
- `magical`
- `mana`
- `master`
- `mastery`
- `material`
- `mechanical`
- `melee`
- `memory`
- `metal`
- `metallic`
- `mid-game`
- `minerals`
- `mining`
- `mithril`
- `mixed`
- `mixed-quality`
- `mobile`
- `mobility`
- `monster`
- `movement`
- `multi_purpose`
- `multiplicative`
- `multiplier`
- `mythical`
- `mythical-materials`
- `nature`
- `necrotic`
- `none`
- `oak`
- `ore`
- `ore-quality`
- `orichalcum`
- `output`
- `over_time`
- `passive`
- `phase`
- `phase_shift`
- `physical`
- `pickaxe`
- `pierce`
- `piercing`
- `plank`
- `player`
- `playstyle`
- `poison`
- `poison_status`
- `poisoned`
- `potion`
- `power`
- `precious`
- `precision`
- `projectile`
- `protection`
- `pull`
- `purification`
- `purifying`
- `push`
- `quality`
- `quantity`
- `quantum`
- `quarry`
- `quicken`
- `radial`
- `radiant`
- `radius`
- `random`
- `ranged`
- `ranger`
- `rare`
- `rarity`
- `reach`
- `reality-bender`
- `recovery`
- `reduction`
- `refined`
- `refinery`
- `refining`
- `reflect`
- `reflect_damage`
- `regen`
- `regeneration`
- `repair`
- `repeatable`
- `resistance`
- `restriction`
- `ring`
- `rng`
- `root`
- `rooted`
- `rush`
- `safe`
- `sawing`
- `scales`
- `scavenger`
- `scholar`
- `self`
- `shadow`
- `sharp`
- `shield`
- `shock`
- `silence`
- `silk-touch`
- `single`
- `single_hit`
- `single_target`
- `slashing`
- `slime`
- `slow`
- `slowed`
- `smelting`
- `smithing`
- `snare`
- `solvent`
- `soulbound`
- `spawn`
- `spear`
- `special`
- `spectral`
- `speed`
- `speed_boost`
- `staff`
- `standard`
- `starter`
- `station`
- `status_buff`
- `status_debuff`
- `stealth`
- `steel`
- `stone`
- `stone-rich`
- `strength`
- `strengthen`
- `strong`
- `stun`
- `stunned`
- `summon`
- `summon_id`
- `support`
- `survival`
- `sustain`
- `sustained`
- `swiftness`
- `sword`
- `tanky`
- `target`
- `targeted`
- `tech`
- `teleport`
- `temporal`
- `territorial`
- `thorns`
- `tier`
- `time`
- `tin`
- `tool`
- `toxic`
- `trader`
- `trainer`
- `transcendence`
- `transmutation`
- `trap`
- `treasure`
- `tree`
- `trigger`
- `turret`
- `tutorial`
- `ultimate`
- `uncommon`
- `undead`
- `universal`
- `unlock`
- `upgrade`
- `utility`
- `vampiric`
- `versatile`
- `void`
- `volcanic`
- `vulnerable`
- `wandering`
- `warp`
- `warrior`
- `water`
- `weaken`
- `weakened`
- `weapon`
- `weight`
- `wolf`
- `wood`
- `wood-quality`
- `wood-rich`
- `worldtree`
- `wraith`
- `yield`