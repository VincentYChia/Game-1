# JSON Template Library - LLM Fine-Tuning

Generated: 2026-01-02 01:26:25

## Purpose

These templates are organized by **content type** for training specialized LLMs.
Each category represents a distinct type of game content that could be handled
by a dedicated fine-tuned model.

## Categories Overview

| Category | Items | Description |
|----------|-------|-------------|
| abilities | 30 | Enemy abilities with tags and effect parameters |
| classes | 6 | Starting class definitions with bonuses and skills |
| consumables | 16 | Potions, elixirs, food, and other consumable items - alchemy output |
| devices | 5 | Engineering devices (turrets, traps, bombs) |
| devices_bombs | 4 | Explosive devices - engineering output |
| devices_traps | 4 | Trap devices - engineering output |
| devices_turrets | 8 | Automated turret defenses - engineering output |
| enemies | 19 | Enemy definitions with stats, behavior, and loot |
| equipment_accessories | 3 | Accessories (rings, amulets, belts) - smithing/enchanting output |
| equipment_armor | 6 | Armor pieces (helmets, chestplates, leggings, boots) - smithing output |
| equipment_shields | 1 | Shields and off-hand defensive items - smithing output |
| equipment_tools | 10 | Gathering tools (pickaxes, axes) - smithing output |
| equipment_weapons | 30 | Weapons (swords, axes, spears, bows, staffs) - smithing output |
| materials_raw | 65 | Raw crafting materials (ores, logs, crystals) - gathered resources |
| materials_refined | 16 | Refined crafting materials (ingots, planks, alloys) - refining output |
| npcs | 12 | NPC definitions with dialogue and quest associations |
| placements | 62 | Minigame placement patterns for crafting |
| placements_refining | 54 | Refining placement patterns (hub-and-spoke format) |
| recipes_alchemy | 24 | Alchemy recipes for potions and consumables |
| recipes_enchanting | 50 | Enchanting recipes for magical enhancements |
| recipes_engineering | 16 | Engineering recipes for devices and gadgets |
| recipes_generic | 103 | Generic recipes (test/placeholder without specific discipline) |
| recipes_refining | 5 | Refining recipes for processing raw materials |
| recipes_smithing | 41 | Smithing recipes for weapons, armor, and tools |
| resource_nodes | 28 | Gatherable resource node definitions |
| skill_unlocks | 14 | Skill unlock definitions - how players acquire skills |
| skills | 42 | Player skills with effects, costs, and evolution paths |
| stations | 23 | Placeable crafting stations and tools |
| titles | 10 | Achievement titles with prerequisites and bonuses |
| world_chunks | 9 | World chunk templates for procedural generation |

---

## Category Details

### abilities
**Description**: Enemy abilities with tags and effect parameters
**Total Items**: 30
**Source Files**: Definitions.JSON/hostiles-1.JSON, Update-1/hostiles-testing-integration.JSON

**Key Fields**:
- `abilityId` (string): leap_attack, charge_attack, refraction_shield
- `cooldown` (number): 35.0, 8.0, 40.0
- `effectParams` (object): 
- `effectParams.baseDamage` (integer): 65, 35, 100
- `effectParams.beam_range` (number): 12.0, 15.0
- `effectParams.beam_width` (number): 1.5, 2.0
- `effectParams.bleed_damage_per_second` (number): 5.0
- `effectParams.bleed_duration` (number): 6.0
- `effectParams.burn_damage_per_second` (number): 8.0, 10.0
- `effectParams.burn_duration` (number): 12.0, 15.0
- `effectParams.chain_count` (integer): 4
- `effectParams.chain_falloff` (number): 0.1
- `effectParams.chain_range` (number): 8.0, 6.0
- `effectParams.chargeSpeed` (number): 3.0
- `effectParams.circle_radius` (number): 3.0, 5.0, 6.0

---

### classes
**Description**: Starting class definitions with bonuses and skills
**Total Items**: 6
**Source Files**: progression/classes-1.JSON

**Key Fields**:
- `classId` (string): scavenger, ranger, artisan
- `description` (string): Balanced generalists who dabble in every, Masters of combat and physical might. Wa, Master crafters who excel at all creatio
- `name` (string): Ranger, Adventurer, Artisan
- `narrative` (string): Your hands shape reality. What takes oth, Where others see rocks, you see treasure, Steel and strength. You are the immovabl
- `playstyle` (string): Fast-paced, mobility-focused, efficient , Crafting-centric, quality-focused, effic, Direct combat, high survivability, strai
- `preferredArmorType` (string): heavy, medium, light
- `preferredDamageTypes` (array): crushing, piercing, poison
- `recommendedStats` (object): 
- `recommendedStats.avoid` (array): STR, None - true flexibility, LCK
- `recommendedStats.primary` (array): Balanced - player choice, AGI, STR
- `recommendedStats.secondary` (array): STR, AGI, VIT
- `startingBonuses` (object): 
- `startingBonuses.allCrafting` (number): 0.05
- `startingBonuses.allCraftingTime` (number): 0.1
- `startingBonuses.allGathering` (number): 0.05

---

### consumables
**Description**: Potions, elixirs, food, and other consumable items - alchemy output
**Total Items**: 16
**Source Files**: items.JSON/items-alchemy-1.JSON

**Key Fields**:
- `category` (string): consumable
- `duration` (integer): 0, 480, 7200
- `effect` (string): Restores 100 HP instantly, +20% defense, Can dissolve most materials, use careful
- `flags` (object): 
- `flags.consumable` (boolean): False, True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): True
- `itemId` (string): strength_elixir, armor_polish, blast_powder
- `metadata` (object): 
- `metadata.narrative` (string): Creating universal solvent that can diss, Explosive powder from concentrated eleme, Fire resistance potion using water and f
- `metadata.tags` (array): resistance, agility, buff
- `name` (string): Weapon Oil, Health Potion, Greater Health Potion
- `rarity` (string): common, epic, uncommon
- `requirements` (object): 
- `requirements.level` (integer): 1, 5, 6

---

### devices
**Description**: Engineering devices (turrets, traps, bombs)
**Total Items**: 5
**Source Files**: items.JSON/items-engineering-1.JSON

**Key Fields**:
- `category` (string): device
- `effect` (string): Launches grappling hook up to 15 units, , Fires net that slows enemies by 80% for , Disables all mechanical devices in 8 uni
- `flags` (object): 
- `flags.placeable` (boolean): False, True
- `flags.repairable` (boolean): False, True
- `flags.stackable` (boolean): False, True
- `itemId` (string): jetpack, grappling_hook, net_launcher
- `metadata` (object): 
- `metadata.narrative` (string): Healing beacon that emanates restorative, Jetpack for brief flight. Fuel not inclu, Net launcher that ensnares enemies. Redu
- `metadata.tags` (array): crowd-control, device, mobility
- `name` (string): Jetpack, Net Launcher, Grappling Hook
- `rarity` (string): rare, epic, uncommon
- `requirements` (object): 
- `requirements.level` (integer): 8, 9, 13
- `requirements.stats` (object): 

---

### devices_bombs
**Description**: Explosive devices - engineering output
**Total Items**: 4
**Source Files**: items.JSON/items-engineering-1.JSON, items.JSON/items-testing-tags.JSON

**Key Fields**:
- `category` (string): device
- `effect` (string): Explodes for 75 fire damage + lingering , Explodes for 40 damage in 3 unit radius, Massive explosion with huge radius
- `effectParams` (object): 
- `effectParams.baseDamage` (integer, number): 40, 75, 120
- `effectParams.burn_damage_per_second` (number): 8.0, 15.0
- `effectParams.burn_duration` (number): 10.0, 6.0
- `effectParams.circle_radius` (number): 5.0, 3.0, 20.0
- `effectParams.shock_chance` (number): 0.5
- `effectParams.shock_damage` (number): 20.0
- `effectTags` (array): fire, burn, circle
- `flags` (object): 
- `flags.placeable` (boolean): True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): True
- `flags.tradeable` (boolean): True

---

### devices_traps
**Description**: Trap devices - engineering output
**Total Items**: 4
**Source Files**: items.JSON/items-engineering-1.JSON, items.JSON/items-testing-tags.JSON

**Key Fields**:
- `category` (string): device
- `effect` (string): Triggers on contact, 25 damage + immobil, Triggers on contact, 30 damage + bleed, Triggers on proximity, 50 damage + slow
- `effectParams` (object): 
- `effectParams.baseDamage` (integer, number): 25, 50, 20.0
- `effectParams.bleed_damage_per_second` (number): 3.0
- `effectParams.bleed_duration` (number): 8.0
- `effectParams.burn_damage_per_second` (number): 5.0
- `effectParams.burn_duration` (number): 5.0
- `effectParams.circle_radius` (number): 2.0, 3.0
- `effectParams.freeze_duration` (number): 2.0, 3.0
- `effectParams.root_duration` (number): 3.0, 5.0
- `effectParams.slow_duration` (number): 4.0
- `effectParams.slow_factor` (number): 0.5
- `effectParams.slow_percent` (number): 0.5
- `effectTags` (array): slow, crushing, piercing

---

### devices_turrets
**Description**: Automated turret defenses - engineering output
**Total Items**: 8
**Source Files**: items.JSON/items-engineering-1.JSON, items.JSON/items-testing-tags.JSON

**Key Fields**:
- `category` (string): device
- `effect` (string): Fires lightning bolts, 70 damage + chain, Sweeps cone of fire, 60 damage + lingeri, Fires concentrated light beam, 80 damage
- `effectParams` (object): 
- `effectParams.baseDamage` (integer, number): 35, 70.0, 80.0
- `effectParams.beam_length` (number): 15.0
- `effectParams.beam_range` (number): 12.0
- `effectParams.beam_width` (number): 1.0
- `effectParams.burn_damage_per_second` (number): 8.0, 10.0, 5.0
- `effectParams.burn_duration` (number): 5.0, 6.0
- `effectParams.chain_count` (integer): 2, 3
- `effectParams.chain_damage_falloff` (number): 0.9
- `effectParams.chain_range` (number): 5.0
- `effectParams.cone_angle` (integer, number): 60.0, 45
- `effectParams.cone_length` (number): 10.0
- `effectParams.cone_range` (number): 8.0

---

### enemies
**Description**: Enemy definitions with stats, behavior, and loot
**Total Items**: 19
**Source Files**: Definitions.JSON/hostiles-1.JSON, Definitions.JSON/hostiles-testing-integration.JSON, Update-1/hostiles-testing-integration.JSON

**Key Fields**:
- `ai` (object): 
- `ai.aggroRange` (number): 12.0, 14.0, 15.0
- `ai.attackCooldown` (number): 1.8, 2.0, 1.5
- `ai.behavior` (string): aggressive
- `ai.chaseRange` (number): 18.0, 20.0
- `aiPattern` (object): 
- `aiPattern.aggroOnDamage` (boolean): True
- `aiPattern.aggroOnProximity` (boolean): False, True
- `aiPattern.callForHelpRadius` (integer, number): 0.0, 8, 10.0
- `aiPattern.defaultState` (string): wander, patrol, guard
- `aiPattern.fleeAtHealth` (integer, number): 0.0, 0.3, 0.2
- `aiPattern.packCoordination` (boolean): False, True
- `aiPattern.specialAbilities` (array): leap_attack, charge_attack, refraction_shield
- `behavior` (string): aggressive_swarm, docile_wander, passive_patrol
- `category` (string): aberration, construct, ooze

---

### equipment_accessories
**Description**: Accessories (rings, amulets, belts) - smithing/enchanting output
**Total Items**: 3
**Source Files**: items.JSON/items-smithing-2.JSON

**Key Fields**:
- `attributes` (array): 
- `category` (string): equipment
- `flags` (object): 
- `flags.equippable` (boolean): True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): False
- `itemId` (string): iron_water_amulet, copper_fire_ring, steel_lightning_bracelet
- `metadata` (object): 
- `metadata.narrative` (string): Steel bracelet woven with lightning shar, Simple copper band holding a fire crysta, Iron amulet cradling water crystals. Fee
- `metadata.tags` (array): amulet, bracelet, accessory
- `name` (string): Copper Fire Ring, Steel Lightning Bracelet, Iron Water Amulet

---

### equipment_armor
**Description**: Armor pieces (helmets, chestplates, leggings, boots) - smithing output
**Total Items**: 6
**Source Files**: items.JSON/items-smithing-2.JSON

**Key Fields**:
- `category` (string): equipment
- `flags` (object): 
- `flags.equippable` (boolean): True
- `flags.repairable` (boolean): True
- `flags.stackable` (boolean): False
- `itemId` (string): steel_leggings, leather_tunic, iron_chestplate
- `metadata` (object): 
- `metadata.narrative` (string): Iron plates protecting vital organs with, Reinforced leather boots with iron caps., Steel helm with full face protection and
- `metadata.tags` (array): quality, head, hands
- `name` (string): Iron Chestplate, Leather Tunic, Iron-Studded Gauntlets
- `rarity` (string): common, uncommon
- `requirements` (object): 
- `requirements.level` (integer): 1, 2, 6
- `requirements.stats` (object): 
- `slot` (string): head, hands, feet

---

### equipment_shields
**Description**: Shields and off-hand defensive items - smithing output
**Total Items**: 1
**Source Files**: items.JSON/items-smithing-2.JSON

**Key Fields**:
- `category` (string): equipment
- `flags` (object): 
- `flags.equippable` (boolean): True
- `flags.repairable` (boolean): True
- `flags.stackable` (boolean): False
- `itemId` (string): iron_round_shield
- `metadata` (object): 
- `metadata.narrative` (string): Round iron shield with oak backing. Not 
- `metadata.tags` (array): bash, defensive, melee
- `name` (string): Iron Round Shield
- `range` (integer): 1
- `rarity` (string): common
- `requirements` (object): 
- `requirements.level` (integer): 3
- `requirements.stats` (object): 

---

### equipment_tools
**Description**: Gathering tools (pickaxes, axes) - smithing output
**Total Items**: 10
**Source Files**: items.JSON/items-smithing-2.JSON, items.JSON/items-tools-1.JSON

**Key Fields**:
- `category` (string): equipment
- `effectParams` (object): 
- `effectParams.baseDamage` (integer): 37, 10, 75
- `effectTags` (array): piercing, single, physical
- `flags` (object): 
- `flags.equippable` (boolean): True
- `flags.repairable` (boolean): True
- `flags.stackable` (boolean): False
- `itemId` (string): mithril_pickaxe, steel_sickle, steel_pickaxe
- `metadata` (object): 
- `metadata.narrative` (string): Flexible bamboo rod with silk line and b, Sturdy iron axe that bites deep into woo, Basic copper pickaxe with a wooden handl
- `metadata.tags` (array): herbs, quality, gathering
- `name` (string): Iron Axe, Steel Axe, Mithril Axe
- `range` (integer, number): 0.5, 1, 5
- `rarity` (string): common, uncommon, rare

---

### equipment_weapons
**Description**: Weapons (swords, axes, spears, bows, staffs) - smithing output
**Total Items**: 30
**Source Files**: Update-1/items-testing-integration.JSON, items.JSON/items-smithing-2.JSON, items.JSON/items-testing-integration.JSON, items.JSON/items-testing-tags.JSON

**Key Fields**:
- `attributes` (array): 
- `category` (string): weapon, equipment
- `description` (string): Whip that arcs lightning between foes, Hammer that freezes and repels nearby fo, Blade that projects waves of flame
- `effectParams` (object): 
- `effectParams.baseDamage` (integer, number): 35.0, 5.0, 40.0
- `effectParams.burn_damage_per_second` (number): 10.0, 5.0
- `effectParams.burn_duration` (number): 3.0, 5.0
- `effectParams.chain_count` (integer): 3, 4
- `effectParams.chain_damage_falloff` (number): 0.8
- `effectParams.chrono_slow` (number): 0.5
- `effectParams.circle_radius` (number): 5.0

---

### materials_raw
**Description**: Raw crafting materials (ores, logs, crystals) - gathered resources
**Total Items**: 65
**Source Files**: items.JSON/items-materials-1.JSON

**Key Fields**:
- `category` (string): monster_drop, stone, wood
- `materialId` (string): spectral_thread, golem_core, birch_log
- `metadata` (object): 
- `metadata.narrative` (string): Pitch-black stone that seems to pull lig, Gleaming golden metal with an otherworld, Refined pine planks, perfect for bows an
- `metadata.tags` (array): radiant, void, elemental
- `name` (string): Granite, Worldtree Plank, Iron Ingot
- `rarity` (string): common, rare, legendary
- `tier` (integer): 1, 2, 3

---

### materials_refined
**Description**: Refined crafting materials (ingots, planks, alloys) - refining output
**Total Items**: 16
**Source Files**: items.JSON/items-refining-1.JSON

**Key Fields**:
- `attributes` (array): 
- `category` (string): material
- `flags` (object): 
- `flags.consumable` (boolean): False
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): True
- `itemId` (string): steel_ingot, bronze_ingot, oak_plank
- `metadata` (object): 
- `metadata.narrative` (string): Sturdy iron ingot, grey and reliable. Th, Silvery tin ingot with a subtle sheen. R, Black adamantine ingot, heavy as sin and
- `metadata.tags` (array): ash, wood, copper
- `name` (string): Worldtree Plank, Iron Ingot, Ash Plank

---

### npcs
**Description**: NPC definitions with dialogue and quest associations
**Total Items**: 12
**Source Files**: progression/npcs-1.JSON, progression/npcs-enhanced.JSON, progression/quests-1.JSON, progression/quests-enhanced.JSON

**Key Fields**:
- `behavior` (object): 
- `behavior.interactionRange` (number): 3.0
- `behavior.isStatic` (boolean): False, True
- `behavior.wanderRadius` (integer, number): 0, 5.0
- `completion_dialogue` (array): Marvelous! These ores will be perfect fo, Impressive! You fight with the skill of , You have my deepest thanks, adventurer.
- `description` (object, string): The Elder Sage wants you to gather 5 oak, The Wandering Trader needs 3 copper ore , The Battle Master challenges you to defe
- `description.long` (string): The Battle Master challenges you to defe, The Elder Sage wants you to gather 5 oak, The Wandering Trader needs 3 copper ore 
- `description.narrative` (string): Every journey begins with a single step., A warrior is defined by their deeds. Sho, I study the properties of metals. Help m
- `description.short` (string): Defeat 3 enemies, Gather 5 oak logs for the Elder Sage, Collect 3 copper ore and 3 iron ore
- `dialogue` (object): 
- `dialogue.dialogue_lines` (array): Greetings! I've traveled far and wide., These lands are filled with resources to, Ho there, warrior! Ready to test your me
- `dialogue.farewell` (string): Safe travels, and may you find rare trea, Fight with honor!, May your path be blessed with fortune!
- `dialogue.greeting` (object): 
- `dialogue.greeting.allComplete` (string): You are now a true warrior. Continue you, You've learned all I can teach. Go forth, Your aid has been invaluable, friend.
- `dialogue.greeting.default` (string): Greetings! I've traveled far and wide se, Ho there, warrior! Ready to test your me, Welcome, traveler! I sense great potenti

---

### placements
**Description**: Minigame placement patterns for crafting
**Total Items**: 62
**Source Files**: placements.JSON/placements-adornments-1.JSON, placements.JSON/placements-smithing-1.JSON

**Key Fields**:
- `metadata` (object): 
- `metadata.gridSize` (string): 3x3, 7x7, 5x5
- `metadata.narrative` (string): Basic alchemy table with mortar, pestle,, Basic refinery for turning raw ores into, Basic workbench for assembling mechanica
- `placementMap` (object): 
- `placementMap.1,1` (string): steel_ingot, water_crystal, mithril_ingot
- `placementMap.1,2` (string): steel_ingot, spectral_thread, oak_plank
- `placementMap.1,3` (string): steel_ingot, water_crystal, mithril_ingot
- `placementMap.1,4` (string): steel_ingot, mithril_ingot, wolf_pelt
- `placementMap.1,5` (string): steel_ingot, dire_fang, mithril_ingot
- `placementMap.1,6` (string): mithril_ingot
- `placementMap.1,7` (string): fire_crystal
- `placementMap.2,1` (string): steel_ingot, obsidian, granite
- `placementMap.2,2` (string): phoenix_ash, steel_ingot, spectral_thread
- `placementMap.2,3` (string): phoenix_ash, steel_ingot, obsidian
- `placementMap.2,4` (string): phoenix_ash, steel_ingot, mithril_ingot

---

### placements_refining
**Description**: Refining placement patterns (hub-and-spoke format)
**Total Items**: 54
**Source Files**: placements.JSON/placements-refining-1.JSON

**Key Fields**:
- `coreInputs` (array): 
- `narrative` (string): Refining rare adamantine to epic. Nearly, Infusing copper with storm. Perfect cond, Refining tin ore. Essential for alloys -
- `outputId` (string): charcoal, quicklime, mithril_ingot
- `recipeId` (string): refining_rarity_adamantine_legendary, refining_limestone_to_quicklime, refining_orichalcum_ore_to_ingot
- `stationTier` (integer): 1, 2, 3
- `surroundingInputs` (array): 

---

### recipes_alchemy
**Description**: Alchemy recipes for potions and consumables
**Total Items**: 24
**Source Files**: recipes.JSON/recipes-alchemy-1.JSON, recipes.JSON/recipes-tag-tests.JSON

**Key Fields**:
- `inputs` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): Powerful healing elixir using essence bl, Speed-enhancing draught using air crysta, Improved healing potion using water crys
- `metadata.tags` (array): resistance, gold, buff
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 35, 40, 75
- `miniGame.difficulty` (string): extreme, moderate, easy
- `miniGame.type` (string): alchemy
- `outputId` (string): tin_ingot, regeneration_tonic, test_gold_nugget
- `outputQty` (integer): 1, 2, 3
- `recipeId` (string): alchemy_frost_resistance_potion, alchemy_fire_resistance_potion, test_alchemy_conflicting_type
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): alchemy

---

### recipes_enchanting
**Description**: Enchanting recipes for magical enhancements
**Total Items**: 50
**Source Files**: recipes.JSON/recipes-adornments-1.json, recipes.JSON/recipes-enchanting-1.JSON

**Key Fields**:
- `applicableTo` (array): tool, armor, weapon
- `effect` (object): 
- `effect.chainCount` (integer): 2
- `effect.chainRange` (integer): 3
- `effect.conflictsWith` (array): protection_2, silk_touch, efficiency_2
- `effect.damagePerSecond` (integer): 8, 10
- `effect.damagePercent` (number): 0.5
- `effect.duration` (integer): 8, 4, 5
- `effect.element` (string): poison, lightning, fire
- `effect.maxStacks` (integer): 3, 5
- `effect.perMinute` (boolean): True
- `effect.slowPercent` (number): 0.3
- `effect.stackable` (boolean): False, True
- `effect.type` (string): reflect_damage, harvest_original_form, slow
- `effect.value` (integer, number): 0.1, 0.35, 0.6

---

### recipes_engineering
**Description**: Engineering recipes for devices and gadgets
**Total Items**: 16
**Source Files**: recipes.JSON/recipes-engineering-1.JSON

**Key Fields**:
- `inputs` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): Lightning cannon that channels storm ene, Net launcher that ensnares enemies. Redu, EMP device that disables electronic enem
- `metadata.tags` (array): crowd-control, cluster, turret
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 65, 35, 70
- `miniGame.difficulty` (string): extreme, moderate, easy
- `miniGame.type` (string): engineering
- `outputId` (string): jetpack, frost_mine, laser_turret
- `outputQty` (integer): 1, 2, 3
- `recipeId` (string): engineering_fire_arrow_turret, engineering_simple_bomb, engineering_jetpack
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): engineering

---

### recipes_generic
**Description**: Generic recipes (test/placeholder without specific discipline)
**Total Items**: 103
**Source Files**: Update-1/recipes-smithing-testing.JSON, placements.JSON/placements-alchemy-1.JSON, placements.JSON/placements-engineering-1.JSON, recipes.JSON/recipes-refining-1.JSON

**Key Fields**:
- `fuelRequired` (object, null): None
- `fuelRequired.materialId` (string): phoenix_ash
- `fuelRequired.quantity` (integer): 1
- `ingredients` (array): 
- `inputs` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): Refining legendary mithril into mythical, Working worldtree wood. It remembers bei, Processing pine into planks. Light, flex
- `metadata.tags` (array): crushing, frost, uncommon
- `narrative` (string): Air crystal creates speed foundation. Li, Jetpack for brief flight - mithril frame, Repair drone - mithril frame enables fli

---

### recipes_refining
**Description**: Refining recipes for processing raw materials
**Total Items**: 5
**Source Files**: recipes.JSON/recipes-tag-tests.JSON

**Key Fields**:
- `inputs` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): TEST: Refining with EMPTY tags array, TEST: Refining with MULTIPLE bonus proce, TEST: Refining with ONLY high-probabilit
- `metadata.tags` (array): basic, grinding, crushing
- `outputs` (array): 
- `recipeId` (string): test_refining_no_bonuses, test_refining_empty_tags, test_refining_all_bonuses
- `stationTier` (integer): 1
- `stationType` (string): refining

---

### recipes_smithing
**Description**: Smithing recipes for weapons, armor, and tools
**Total Items**: 41
**Source Files**: recipes.JSON/recipes-smithing-3.JSON, recipes.JSON/recipes-tag-tests.JSON

**Key Fields**:
- `gridSize` (string): 3x3, 7x7, 5x5
- `inputs` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): Basic alchemy table with mortar, pestle,, Basic refinery for turning raw ores into, Basic workbench for assembling mechanica
- `metadata.tags` (array): bow, weapon, 2H
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 65, 35, 70
- `miniGame.difficulty` (string): extreme, moderate, easy
- `miniGame.type` (string): smithing
- `outputId` (string): steel_leggings, steel_pickaxe, refinery_t1
- `outputQty` (integer): 1
- `recipeId` (string): smithing_refinery_t1, smithing_iron_axe, smithing_iron_shortsword
- `stationTier` (integer): 1, 2, 3

---

### resource_nodes
**Description**: Gatherable resource node definitions
**Total Items**: 28
**Source Files**: Definitions.JSON/resource-node-1.JSON

**Key Fields**:
- `baseHealth` (integer): 200, 800, 100
- `category` (string): stone, tree, ore
- `drops` (array): 
- `metadata` (object): 
- `metadata.narrative` (string): Speckled igneous rock with visible cryst, Impossibly perfect geometric form that c, Dark, impossibly hard ore found only in 
- `metadata.tags` (array): radiant, void, flexible
- `name` (string): Ironwood Tree, Worldtree Sapling, Diamond Geode
- `requiredTool` (string): pickaxe, axe
- `resourceId` (string): genesis_structure, voidstone_shard, tin_seam
- `respawnTime` (string, null): None, very_slow, slow
- `tier` (integer): 1, 2, 3

---

### skill_unlocks
**Description**: Skill unlock definitions - how players acquire skills
**Total Items**: 14
**Source Files**: progression/skill-unlocks.JSON

**Key Fields**:
- `conditions` (object): 
- `conditions.activityMilestones` (string, array): 
- `conditions.characterLevel` (integer, string): 1, 3, 5
- `conditions.completedQuests` (string, array): gathering_quest, combat_quest, tutorial_quest
- `conditions.stats` (object, string): Object like {strength: 5, luck: 10}
- `conditions.stats.intelligence` (integer): 8
- `conditions.stats.luck` (integer): 10, 12
- `conditions.stats.strength` (integer): 15
- `conditions.titles` (string, array): master_warrior, master_gatherer, master_smith
- `cost` (object): 
- `cost.gold` (integer, string): 0, 2500, Gold required to unlock
- `cost.materials` (string, array): 

---

### skills
**Description**: Player skills with effects, costs, and evolution paths
**Total Items**: 42
**Source Files**: Skills/skills-skills-1.JSON, Skills/skills-testing-integration.JSON, Update-1/skills-testing-integration.JSON

**Key Fields**:
- `categories` (array): gathering, defense, refining
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

---

### stations
**Description**: Placeable crafting stations and tools
**Total Items**: 23
**Source Files**: Definitions.JSON/crafting-stations-1.JSON, items.JSON/items-smithing-2.JSON

**Key Fields**:
- `category` (string): station
- `flags` (object): 
- `flags.placeable` (boolean): True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): False
- `itemId` (string): forge_t2, forge_t4, alchemy_table_t1
- `metadata` (object): 
- `metadata.narrative` (string): Arcane enchanting table surrounded by fl, Simple alchemy table with mortar, pestle, Master forge with obsidian construction 
- `metadata.tags` (array): engineering, forge, alchemy
- `name` (string): Advanced Alchemy Table, Basic Forge, Advanced Refinery
- `range` (integer): 0
- `rarity` (string): common, epic, uncommon
- `requirements` (object): 
- `requirements.level` (integer): 1, 8, 10
- `requirements.stats` (object): 

---

### titles
**Description**: Achievement titles with prerequisites and bonuses
**Total Items**: 10
**Source Files**: progression/titles-1.JSON

**Key Fields**:
- `acquisitionMethod` (string): special_achievement, hidden_discovery, guaranteed_milestone
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

---

### world_chunks
**Description**: World chunk templates for procedural generation
**Total Items**: 9
**Source Files**: Definitions.JSON/Chunk-templates-1.JSON

**Key Fields**:
- `category` (string): peaceful, rare, dangerous
- `chunkType` (string): peaceful_forest, rare_forest, rare_quarry
- `enemySpawns` (object): 
- `enemySpawns.beetle_armored` (object): 
- `enemySpawns.beetle_armored.behavior` (string): aggressive_territory, aggressive_guard
- `enemySpawns.beetle_armored.density` (string): high, moderate, low
- `enemySpawns.beetle_brown` (object): 
- `enemySpawns.beetle_brown.behavior` (string): territorial, docile_wander
- `enemySpawns.beetle_brown.density` (string): moderate, very_low
- `enemySpawns.entity_primordial` (object): 
- `enemySpawns.entity_primordial.behavior` (string): boss_encounter
- `enemySpawns.entity_primordial.density` (string): very_low
- `enemySpawns.golem_crystal` (object): 
- `enemySpawns.golem_crystal.behavior` (string): aggressive_guard
- `enemySpawns.golem_crystal.density` (string): low

---

## All Tags

Total unique tags: 315

- `1H`
- `2H`
- `BURN`
- `Physical`
- `SLASHING`
- `Single`
- `abundance`
- `accessory`
- `adamantine`
- `adaptive`
- `advanced`
- `adventurer`
- `aggressive`
- `agile`
- `agility`
- `air`
- `alchemy`
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
- `artisan`
- `ash`
- `attack_speed`
- `axe`
- `balanced`
- `bash`
- `basic`
- `beam`
- `beetle`
- `berserker`
- `bleed`
- `blood`
- `bomb`
- `bonus`
- `boss`
- `bow`
- `bracelet`
- `brewing`
- `bronze`
- `buff`
- `burn`
- `burst`
- `bypass`
- `carapace`
- `caster`
- `cave`
- `chain`
- `chaos`
- `chest`
- `chrono`
- `circle`
- `cleaving`
- `cluster`
- `combat`
- `common`
- `composite`
- `cone`
- `confuse`
- `construct`
- `consumable`
- `control`
- `copper`
- `crafting`
- `critical`
- `crowd-control`
- `crushing`
- `crystal`
- `crystallization`
- `dagger`
- `damage`
- `damage_boost`
- `damage_reduction`
- `dangerous`
- `dark`
- `debuff`
- `defense`
- `defensive`
- `destruction`
- `device`
- `disable`
- `docile`
- `durability`
- `durable`
- `earth`
- `ebony`
- `efficiency`
- `elemental`
- `empower`
- `enchanting`
- `end-game`
- `energy`
- `engineering`
- `enhancement`
- `enrage`
- `entity`
- `epic`
- `essence`
- `essential`
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
- `frontline`
- `frost`
- `gathering`
- `gel`
- `generalist`
- `gold`
- `golem`
- `grinding`
- `hands`
- `harmony`
- `harvesting`
- `haste`
- `head`
- `healing`
- `heavy`
- `herbs`
- `ice`
- `immobilize`
- `impossible`
- `instant`
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
- `lifesteal`
- `light`
- `lightning`
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
- `mythical`
- `mythical-materials`
- `nature`
- `oak`
- `ore`
- `ore-quality`
- `orichalcum`
- `over_time`
- `passive`
- `phase`
- `physical`
- `pickaxe`
- `pierce`
- `piercing`
- `plank`
- `player`
- `poison`
- `poison_status`
- `potion`
- `power`
- `precious`
- `precision`
- `projectile`
- `protection`
- `pull`
- `purification`
- `purifying`
- `quality`
- `quantum`
- `quarry`
- `radiant`
- `random`
- `ranged`
- `ranger`
- `rare`
- `rarity`
- `reach`
- `reality-bender`
- `recovery`
- `refined`
- `refinery`
- `refining`
- `reflect`
- `regeneration`
- `repair`
- `repeatable`
- `resistance`
- `ring`
- `root`
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
- `smelting`
- `smithing`
- `solvent`
- `soulbound`
- `spear`
- `special`
- `spectral`
- `speed`
- `speed_boost`
- `staff`
- `standard`
- `starter`
- `station`
- `steel`
- `stone`
- `stone-rich`
- `strength`
- `strong`
- `stun`
- `summon`
- `support`
- `survival`
- `sustain`
- `sword`
- `tanky`
- `tech`
- `teleport`
- `temporal`
- `territorial`
- `thorns`
- `tier`
- `time`
- `tin`
- `tool`
- `trader`
- `trainer`
- `transcendence`
- `transmutation`
- `trap`
- `treasure`
- `tree`
- `turret`
- `tutorial`
- `ultimate`
- `uncommon`
- `universal`
- `upgrade`
- `utility`
- `vampiric`
- `versatile`
- `void`
- `volcanic`
- `vulnerable`
- `wandering`
- `warrior`
- `water`
- `weaken`
- `weapon`
- `weight`
- `wolf`
- `wood`
- `wood-quality`
- `wood-rich`
- `worldtree`
- `wraith`
- `yield`