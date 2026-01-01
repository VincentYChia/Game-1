# JSON Template Library - Game-1

Generated: 2026-01-01 19:53:07

## Overview

- **Total Categories**: 23
- **Total Unique Tags**: 458
- **Total Material IDs**: 125
- **Total Skill IDs**: 6

---

## Categories

### classes
**Description**: Starting class definitions
**Files**: classes-1.JSON
**Total Fields**: 42

**Key Fields**:
- `classId` (string): scholar, scavenger, artisan
- `description` (string): Masters of combat and physical might. Warriors excel at dealing and taking damage in melee combat., Swift explorers and natural harvesters. Rangers move quickly and gather resources efficiently., Lucky opportunists who find better loot and resources. Scavengers thrive on discovery.
- `name` (string): Adventurer, Scavenger, Warrior
- `narrative` (string): The wilderness is your home. Trees fall faster before you, and you move like the wind. Nature bends to those who respect it., You are not confined by tradition or specialty. Every path is open, every skill within reach. You are limitless., Knowledge is power, and you wield both. Potions brew faster in your hands, recipes reveal themselves, and magic bends to your will.
- `playstyle` (string): Research-focused, crafting-heavy, magic-oriented, Crafting-centric, quality-focused, efficient production, Direct combat, high survivability, straightforward gameplay
- `preferredArmorType` (string): light, robes, medium
- `preferredDamageTypes` (array): physical, poison, lightning
- `recommendedStats` (object): 
- `recommendedStats.avoid` (array): LCK, INT, None - true flexibility
- `recommendedStats.primary` (array): AGI, LCK, INT
- `recommendedStats.secondary` (array): AGI, VIT, STR
- `startingBonuses` (object): 
- `startingBonuses.allCrafting` (number): 0.05
- `startingBonuses.allCraftingTime` (number): 0.1
- `startingBonuses.allGathering` (number): 0.05
- `startingBonuses.baseHP` (integer): 0, 50, 30
- `startingBonuses.baseMana` (integer): 0, 50, 100
- `startingBonuses.carryCapacity` (integer): 0, 100
- `startingBonuses.critChance` (number): 0.0, 0.1

---

### crafting-stations
**Description**: Crafting station definitions
**Files**: crafting-stations-1.JSON
**Total Fields**: 27

**Key Fields**:
- `metadata` (object): 
- `metadata.description` (string): Crafting station definitions - placeable items that enable crafting
- `metadata.note` (string): Stations are just items with placeable flag, no special structure needed
- `metadata.version` (string): 1.0
- `stations` (array): 
- `stations[]` (object): 
- `stations[].category` (string): station
- `stations[].flags` (object): 
- `stations[].flags.placeable` (boolean): True
- `stations[].flags.repairable` (boolean): False
- `stations[].flags.stackable` (boolean): False
- `stations[].itemId` (string): forge_t3, refinery_t2, alchemy_table_t2
- `stations[].metadata` (object): 
- `stations[].metadata.narrative` (string): Basic stone furnace for refining raw ores into usable materials. Essential for any aspiring metalworker., Precision engineering station with specialized tools for complex device assembly., Simple stone forge with basic bellows. Hot enough for copper and iron work, but struggles with harder metals.
- `stations[].metadata.tags` (array): standard, refining, station
- `stations[].name` (string): Basic Engineering Bench, Advanced Engineering Bench, Reinforced Forge
- `stations[].range` (integer): 0
- `stations[].rarity` (string): common, uncommon, rare
- `stations[].requirements` (object): 

---

### hostiles
**Description**: Enemy and ability definitions
**Files**: hostiles-1.JSON, hostiles-testing-integration.JSON
**Total Fields**: 128

**Key Fields**:
- `abilityId` (string): life_drain, refraction_shield, reality_warp
- `ai` (object): 
- `ai.aggroRange` (number): 12.0, 14.0, 15.0
- `ai.attackCooldown` (number): 1.8, 2.0, 1.5
- `ai.behavior` (string): aggressive
- `ai.chaseRange` (number): 18.0, 20.0
- `aiPattern` (object): 
- `aiPattern.aggroOnDamage` (boolean): True
- `aiPattern.aggroOnProximity` (boolean): False, True
- `aiPattern.callForHelpRadius` (integer): 0, 8, 10
- `aiPattern.defaultState` (string): guard, wander, patrol
- `aiPattern.fleeAtHealth` (number, integer): 0.2, 0, 0.3
- `aiPattern.packCoordination` (boolean): True
- `aiPattern.specialAbilities` (array): life_drain, refraction_shield, reality_warp
- `behavior` (string): territorial, boss_encounter, aggressive_phase
- `category` (string): insect, elemental, undead
- `cooldown` (number): 35.0, 40.0, 12.0
- `drops` (array): 
- `drops[]` (object): 

---

### items-alchemy
**Description**: Potions, elixirs, and consumables
**Files**: items-alchemy-1.JSON
**Total Fields**: 23

**Key Fields**:
- `category` (string): consumable
- `duration` (integer): 0, 480, 300
- `effect` (string): Restores 100 HP instantly, +20% defense, +25% movement and attack speed
- `flags` (object): 
- `flags.consumable` (boolean): True
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): True
- `itemId` (string): health_potion, greater_health_potion, regeneration_tonic
- `metadata` (object): 
- `metadata.narrative` (string): Defense-boosting potion using iron scales and earth crystals. Skin hardens like metal, blows that should fell you merely bruise. Stand firm, unbreakable., Improved healing potion using water crystals to amplify restorative properties. The liquid shimmers with captured vitality. One swallow and you feel strength returning., Speed-enhancing draught using air crystals and spectral thread. Time seems to slow around you. Your movements blur, strikes land before enemies can react.
- `metadata.tags` (array): standard, regeneration, buff
- `name` (string): Health Potion, Swiftness Draught, Minor Health Potion
- `rarity` (string): common, uncommon, rare
- `requirements` (object): 
- `requirements.level` (integer): 1, 5, 7
- `requirements.stats` (object): 
- `stackSize` (integer): 10, 20, 5
- `statMultipliers` (object): 
- `statMultipliers.weight` (number): 0.2, 0.5, 0.3

---

### items-engineering
**Description**: Engineering devices and gadgets
**Files**: items-engineering-1.JSON
**Total Fields**: 128

**Key Fields**:
- `bombs` (array): 
- `bombs[]` (object): 
- `bombs[].category` (string): device
- `bombs[].effect` (string): Splits into 8 smaller explosions, total 120 damage over wide area, Explodes for 40 damage in 3 unit radius, Explodes for 75 fire damage + lingering flames
- `bombs[].effectParams` (object): 
- `bombs[].effectParams.baseDamage` (integer): 40, 75, 120
- `bombs[].effectParams.burn_damage_per_second` (number): 8.0
- `bombs[].effectParams.burn_duration` (number): 6.0
- `bombs[].effectParams.circle_radius` (number): 3.0, 4.0, 5.0
- `bombs[].effectTags` (array): fire, burn, physical
- `bombs[].flags` (object): 
- `bombs[].flags.placeable` (boolean): True
- `bombs[].flags.repairable` (boolean): False
- `bombs[].flags.stackable` (boolean): True
- `bombs[].itemId` (string): cluster_bomb, fire_bomb, simple_bomb
- `bombs[].metadata` (object): 
- `bombs[].metadata.narrative` (string): Cluster bomb that splits into multiple explosives. Maximum coverage. One becomes many, the sky rains destruction., Simple explosive using blast powder in iron casing. The universal problem solver. Pull pin, throw, run. In that order., Fire bomb with crystal-enhanced payload. Burns hot enough to melt stone. The explosion is just the beginning - the flames linger, hungry.
- `bombs[].metadata.tags` (array): elemental, area, explosive
- `bombs[].name` (string): Fire Bomb, Simple Bomb, Cluster Bomb

---

### items-equipment
**Description**: Weapons, armor, and shields
**Files**: items-smithing-2.JSON
**Total Fields**: 39

**Key Fields**:
- `attributes` (array): 
- `attributes[]` (object): 
- `attributes[].effect` (string): Elemental attacks deal bonus fire damage
- `attributes[].element` (string): fire
- `attributes[].type` (string): damage
- `attributes[].value` (integer): 15
- `category` (string): equipment
- `effectParams` (object): 
- `effectParams.baseDamage` (integer): 35, 40, 42
- `effectParams.burn_damage_per_second` (number): 5.0
- `effectParams.burn_duration` (number): 3.0
- `effectTags` (array): physical, slashing, piercing
- `flags` (object): 
- `flags.equippable` (boolean): True
- `flags.repairable` (boolean): True
- `flags.stackable` (boolean): False
- `itemId` (string): fire_crystal_staff, steel_battleaxe, composite_longbow
- `metadata` (object): 
- `metadata.narrative` (string): Simple copper-tipped spear with ash wood shaft. The extra reach keeps danger at arm's length. Perfect for those who prefer distance over direct confrontation., Mithril dagger that seems to shimmer out of existence. Wickedly sharp and impossibly light, it strikes faster than the eye can follow. The blade whispers through air and flesh alike., Balanced steel longsword that flows like water and strikes like thunder. The blade sings when it cuts through air, a testament to its quality.

---

### items-materials
**Description**: Raw materials and crafting ingredients
**Files**: items-materials-1.JSON
**Total Fields**: 9

**Key Fields**:
- `category` (string): monster_drop, metal, elemental
- `materialId` (string): tin_ore, phoenix_ash, diamond
- `metadata` (object): 
- `metadata.narrative` (string): The pinnacle of mortal metallurgy. Channels both physical force and magical energy with perfect efficiency., Refined ironwood planks, nearly as strong as actual metal., Pale crystal that drifts upward if not secured. Contains compressed winds.
- `metadata.tags` (array): standard, elemental, air
- `name` (string): Copper Ore, Orichalcum Ore, Adamantine Ingot
- `rarity` (string): rare, epic, common
- `tier` (integer): 1, 2, 3

---

### items-refining
**Description**: Processed materials (ingots, planks, alloys)
**Files**: items-refining-1.JSON
**Total Fields**: 27

**Key Fields**:
- `attributes` (array): 
- `attributes[]` (object): 
- `attributes[].effect` (string): Items crafted with this add lightning damage, Items crafted with this add frost damage, Items crafted with this add fire damage
- `attributes[].element` (string): fire, frost, lightning
- `attributes[].type` (string): elemental
- `attributes[].value` (integer): 10
- `category` (string): material
- `flags` (object): 
- `flags.consumable` (boolean): False
- `flags.repairable` (boolean): False
- `flags.stackable` (boolean): True
- `itemId` (string): frost_steel_ingot, adamantine_ingot, orichalcum_ingot
- `metadata` (object): 
- `metadata.narrative` (string): Dense steel ingot, dark grey with a bluish tint. Carbon-rich iron forged under intense heat. Holds an edge far better than common iron, the mark of quality craftsmanship., Bronze alloy forged from copper and tin. Stronger than either parent metal, the ancient alloy that built civilizations. The first lesson in combining materials., Sturdy iron ingot, grey and reliable. The workhorse of civilization - strong enough for weapons, durable enough for tools, abundant enough to be practical.
- `metadata.tags` (array): elemental, wood, lightning
- `name` (string): Adamantine Ingot, Ebony Plank, Fire Steel Ingot
- `rarity` (string): rare, epic, common
- `requirements` (object): 
- `requirements.level` (integer): 1, 3, 5

---

### items-tools
**Description**: Placeable crafting tools and stations
**Files**: items-tools-1.JSON
**Total Fields**: 33

**Key Fields**:
- `metadata` (object): 
- `metadata.description` (string): Tool item definitions for gathering resources
- `metadata.note` (string): Tools can be used in combat with penalties to durability
- `metadata.version` (string): 1.0
- `tools` (array): 
- `tools[]` (object): 
- `tools[].category` (string): equipment
- `tools[].effectParams` (object): 
- `tools[].effectParams.baseDamage` (integer): 75, 10, 18
- `tools[].effectTags` (array): piercing, slashing, physical
- `tools[].flags` (object): 
- `tools[].flags.equippable` (boolean): True
- `tools[].flags.repairable` (boolean): True
- `tools[].flags.stackable` (boolean): False
- `tools[].itemId` (string): steel_axe, copper_axe, iron_pickaxe
- `tools[].metadata` (object): 
- `tools[].metadata.narrative` (string): Simple copper axe with oak handle. Every woodcutter's first companion on the journey to mastery., Sturdy iron axe that bites deep into wood. The standard tool for serious forestry work., Well-balanced steel axe with a razor edge. Fells even ancient trees with steady, powerful strikes.
- `tools[].metadata.tags` (array): standard, axe, quality
- `tools[].name` (string): Iron Axe, Copper Pickaxe, Copper Axe

---

### npcs
**Description**: NPC definitions
**Files**: npcs-1.JSON, npcs-enhanced.JSON
**Total Fields**: 43

**Key Fields**:
- `metadata` (object): 
- `metadata.description` (string): Enhanced NPC system - includes services, behavior, and unlock conditions
- `metadata.note` (string): Backwards compatible with v1.0 format
- `metadata.version` (string): 2.0
- `npcs` (array): 
- `npcs[]` (object): 
- `npcs[].behavior` (object): 
- `npcs[].behavior.interactionRange` (number): 3.0
- `npcs[].behavior.isStatic` (boolean): False, True
- `npcs[].behavior.wanderRadius` (number, integer): 0, 5.0
- `npcs[].dialogue` (object): 
- `npcs[].dialogue.dialogue_lines` (array): Defeat some enemies, and I'll reward your bravery., Welcome, traveler! I sense great potential within you., Ho there, warrior! Ready to test your mettle?
- `npcs[].dialogue.farewell` (string): Fight with honor!, May your path be blessed with fortune!, Safe travels, and may you find rare treasures!
- `npcs[].dialogue.greeting` (object): 
- `npcs[].dialogue.greeting.allComplete` (string): Your aid has been invaluable, friend., You are now a true warrior. Continue your training!, You've learned all I can teach. Go forth and explore!
- `npcs[].dialogue.greeting.default` (string): Ho there, warrior! Ready to test your mettle?, Greetings! I've traveled far and wide seeking rare materials., Welcome, traveler! I sense great potential within you.
- `npcs[].dialogue.greeting.questComplete` (string): Well done! Return to me when ready to claim your rewards., Impressive! You've earned my respect and rewards., Excellent! Those will serve my research perfectly.
- `npcs[].dialogue.greeting.questInProgress` (string): Go forth and prove yourself in battle!, Have you found those materials yet? I await eagerly!, How goes your task? The forest awaits your efforts.
- `npcs[].dialogue_lines` (array): Defeat some enemies, and I'll reward your bravery., Welcome, traveler! I sense great potential within you., Ho there, warrior! Ready to test your mettle?

---

### placements
**Description**: Minigame grid placement patterns
**Files**: placements-adornments-1.JSON, placements-alchemy-1.JSON, placements-engineering-1.JSON, placements-refining-1.JSON, placements-smithing-1.JSON
**Total Fields**: 528

**Key Fields**:
- `coreInputs` (array): 
- `coreInputs[]` (object): 
- `coreInputs[].materialId` (string): tin_ore, platinum_ore, platinum_ingot
- `coreInputs[].quantity` (integer): 1, 2, 3
- `coreInputs[].rarity` (string): rare, epic, common
- `ingredients` (array): 
- `ingredients[]` (object): 
- `ingredients[].materialId` (string): phoenix_ash, air_crystal, spectral_thread
- `ingredients[].quantity` (integer): 1, 2, 3
- `ingredients[].slot` (integer): 1, 2, 3
- `metadata` (object): 
- `metadata.gridSize` (string): 3x3, 5x5, 7x7
- `metadata.narrative` (string): Simple pine bow strung with treated sinew. Not powerful, but reliable., Master forge with crystal enhancement. Can reach extreme temperatures., Improved forge with better heat retention. Can work steel reliably.
- `narrative` (string): Golem core provides titan strength. Storm heart adds raw power. Phoenix ash ensures perpetual effect. Essence blood binds all. You feel unstoppable., Slime gel creates slick base. Spectral thread adds supernatural efficiency. Water crystal prevents evaporation. Productivity soars., Refining common steel to uncommon. Carbon bonds align perfectly.
- `outputId` (string): efficiency_oil, platinum_ingot, poison_trap
- `placementMap` (object): 
- `placementMap.1,1` (string): limestone, granite, steel_ingot
- `placementMap.1,2` (string): steel_ingot, spectral_thread, mithril_ingot
- `placementMap.1,3` (string): limestone, granite, steel_ingot

---

### quests
**Description**: Quest definitions
**Files**: quests-1.JSON, quests-enhanced.JSON
**Total Fields**: 69

**Key Fields**:
- `metadata` (object): 
- `metadata.description` (string): Enhanced quest system - includes requirements, progression, and detailed objectives
- `metadata.note` (string): Backwards compatible with v1.0 format
- `metadata.version` (string): 2.0
- `quests` (array): 
- `quests[]` (object): 
- `quests[].completion_dialogue` (array): Here, take these as payment., I'm honored to grant you these rewards., Take these rewards as a token of my gratitude.
- `quests[].description` (object, string): The Wandering Trader needs 3 copper ore and 3 iron ore for his studies., The Battle Master challenges you to defeat 3 enemies to prove your combat prowess., The Elder Sage wants you to gather 5 oak logs to prove your resourcefulness.
- `quests[].description.long` (string): The Battle Master challenges you to defeat 3 enemies to prove your combat prowess. Venture into the wilderness and return victorious., The Elder Sage wants you to gather 5 oak logs to prove your resourcefulness. Approach oak trees and use your axe to gather wood., The Wandering Trader needs 3 copper ore and 3 iron ore for his studies. Mine rocks to find these ores.
- `quests[].description.narrative` (string): I study the properties of metals. Help me gather samples and I'll reward you handsomely., A warrior is defined by their deeds. Show me you can stand against the dangers of this world., Every journey begins with a single step. Show me you can gather what nature provides.
- `quests[].description.short` (string): Gather 5 oak logs for the Elder Sage, Defeat 3 enemies, Collect 3 copper ore and 3 iron ore
- `quests[].givenBy` (string): mysterious_trader, combat_trainer, tutorial_guide
- `quests[].metadata` (object): 
- `quests[].metadata.difficulty` (string): medium, easy
- `quests[].metadata.estimatedTime` (string): 10 minutes, 5 minutes, 15 minutes
- `quests[].metadata.narrative` (string): The first true test of a warrior. Defeat enemies and prove your combat abilities., The first quest given to all travelers. A simple test of gathering skills., The Wandering Trader's research requires various metals. This quest can be repeated daily.
- `quests[].metadata.tags` (array): tutorial, repeatable, gathering
- `quests[].name` (string): Prove Your Worth, First Steps, Material Research
- `quests[].npc_id` (string): mysterious_trader, combat_trainer, tutorial_guide

---

### recipes-adornments
**Description**: Adornment and accessory recipes
**Files**: recipes-adornments-1.json
**Total Fields**: 32

**Key Fields**:
- `applicableTo` (array): accessory, armor, tool
- `effect` (object): 
- `effect.chainCount` (integer): 2
- `effect.chainRange` (integer): 3
- `effect.conflictsWith` (array): sharpness_1, efficiency_1, protection_2
- `effect.damagePerSecond` (integer): 8, 10
- `effect.damagePercent` (number): 0.5
- `effect.duration` (integer): 8, 4, 5
- `effect.element` (string): fire, poison, lightning
- `effect.maxStacks` (integer): 3, 5
- `effect.perMinute` (boolean): True
- `effect.slowPercent` (number): 0.3
- `effect.stackable` (boolean): False, True
- `effect.type` (string): health_regeneration, movement_speed_multiplier, lifesteal
- `effect.value` (number, integer): 0.1, 0.35, 0.6
- `enchantmentId` (string): efficiency_1, protection_3, sharpness_2
- `enchantmentName` (string): Soulbound, Frost Touch, Lifesteal
- `inputs` (array): 
- `inputs[]` (object): 

---

### recipes-alchemy
**Description**: Alchemy recipes for potions
**Files**: recipes-alchemy-1.JSON
**Total Fields**: 17

**Key Fields**:
- `inputs` (array): 
- `inputs[]` (object): 
- `inputs[].materialId` (string): phoenix_ash, air_crystal, spectral_thread
- `inputs[].quantity` (integer): 1, 2, 3
- `metadata` (object): 
- `metadata.narrative` (string): Speed-enhancing draught using air crystals and spectral thread. Time seems to slow., Polish that makes armor gleam and deflect attacks. Sheen turns blades., Transmuting basic copper into tin. Foundation of alchemical wealth.
- `metadata.tags` (array): standard, elemental, purification
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 35, 40, 75
- `miniGame.difficulty` (string): moderate, extreme, hard
- `miniGame.type` (string): alchemy
- `outputId` (string): health_potion, universal_solvent, frost_resistance_potion
- `outputQty` (integer): 1, 2, 3
- `recipeId` (string): alchemy_elemental_harmony, alchemy_transmute_copper_tin, alchemy_titans_brew
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): alchemy

---

### recipes-enchanting
**Description**: Enchanting recipes
**Files**: recipes-enchanting-1.JSON
**Total Fields**: 32

**Key Fields**:
- `applicableTo` (array): accessory, armor, tool
- `effect` (object): 
- `effect.chainCount` (integer): 2
- `effect.chainRange` (integer): 3
- `effect.conflictsWith` (array): sharpness_1, efficiency_1, protection_2
- `effect.damagePerSecond` (integer): 8, 10
- `effect.damagePercent` (number): 0.5
- `effect.duration` (integer): 8, 4, 5
- `effect.element` (string): fire, poison, lightning
- `effect.maxStacks` (integer): 3, 5
- `effect.perMinute` (boolean): True
- `effect.slowPercent` (number): 0.3
- `effect.stackable` (boolean): False, True
- `effect.type` (string): health_regeneration, movement_speed_multiplier, lifesteal
- `effect.value` (number, integer): 0.1, 0.35, 0.6
- `enchantmentId` (string): efficiency_1, protection_3, sharpness_2
- `enchantmentName` (string): Soulbound, Frost Touch, Lifesteal
- `inputs` (array): 
- `inputs[]` (object): 

---

### recipes-engineering
**Description**: Engineering recipes for devices
**Files**: recipes-engineering-1.JSON
**Total Fields**: 17

**Key Fields**:
- `inputs` (array): 
- `inputs[]` (object): 
- `inputs[].materialId` (string): phoenix_ash, air_crystal, spectral_thread
- `inputs[].quantity` (integer): 2, 3, 4
- `metadata` (object): 
- `metadata.narrative` (string): Fire bomb with crystal-enhanced payload. Burns hot enough to melt stone., Lightning cannon that channels storm energy. Extremely effective, extremely dangerous., Laser turret using focused light crystals. Precise and devastating.
- `metadata.tags` (array): elemental, explosive, lightning
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 65, 35, 70
- `miniGame.difficulty` (string): moderate, extreme, hard
- `miniGame.type` (string): engineering
- `outputId` (string): frost_mine, bear_trap, emp_device
- `outputQty` (integer): 1, 2, 3
- `recipeId` (string): engineering_net_launcher, engineering_bear_trap, engineering_healing_beacon
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): engineering

---

### recipes-refining
**Description**: Refining recipes for material processing
**Files**: recipes-refining-1.JSON
**Total Fields**: 20

**Key Fields**:
- `fuelRequired` (object, null): None
- `fuelRequired.materialId` (string): phoenix_ash
- `fuelRequired.quantity` (integer): 1
- `inputs` (array): 
- `inputs[]` (object): 
- `inputs[].materialId` (string): tin_ore, adamantine_ingot, ash_log
- `inputs[].quantity` (integer): 1, 2, 3
- `inputs[].rarity` (string): rare, epic, common
- `metadata` (object): 
- `metadata.narrative` (string): Refining common copper into uncommon quality. Careful heat and patience., Infusing copper with storm essence. Perfect magical conductivity., Refining rare bronze into epic quality. Surpassing even the legendary smiths of old.
- `metadata.tags` (array): elemental, wood, mythical
- `outputs` (array): 
- `outputs[]` (object): 
- `outputs[].materialId` (string): frost_steel_ingot, ironwood_plank, etherion_ingot
- `outputs[].quantity` (integer): 1, 2, 3
- `outputs[].rarity` (string): mythical, rare, epic
- `recipeId` (string): refining_rarity_copper_rare, refining_rarity_etherion_mythical, refining_rarity_copper_epic
- `stationRequired` (string): refinery
- `stationTierRequired` (integer): 1, 2, 3

---

### recipes-smithing
**Description**: Smithing recipes for weapons and armor
**Files**: recipes-smithing-3.JSON
**Total Fields**: 18

**Key Fields**:
- `gridSize` (string): 3x3, 5x5, 7x7
- `inputs` (array): 
- `inputs[]` (object): 
- `inputs[].materialId` (string): phoenix_ash, air_crystal, ash_log
- `inputs[].quantity` (integer): 1, 2, 3
- `metadata` (object): 
- `metadata.narrative` (string): Simple pine bow strung with treated sinew. Not powerful, but reliable., Master forge with crystal enhancement. Can reach extreme temperatures., Improved forge with better heat retention. Can work steel reliably.
- `metadata.tags` (array): standard, elemental, lightning
- `miniGame` (object): 
- `miniGame.baseTime` (integer): 65, 35, 70
- `miniGame.difficulty` (string): moderate, extreme, hard
- `miniGame.type` (string): smithing
- `outputId` (string): leather_tunic, copper_axe, iron_pickaxe
- `outputQty` (integer): 1
- `recipeId` (string): smithing_forge_t3, smithing_leather_tunic, smithing_iron_water_amulet
- `stationTier` (integer): 1, 2, 3
- `stationType` (string): smithing

---

### resource-nodes
**Description**: Gatherable resource node definitions
**Files**: resource-node-1.JSON
**Total Fields**: 16

**Key Fields**:
- `baseHealth` (integer): 200, 800, 100
- `category` (string): tree, ore, stone
- `drops` (array): 
- `drops[]` (object): 
- `drops[].chance` (string): moderate, rare, improbable
- `drops[].materialId` (string): tin_ore, phoenix_ash, diamond
- `drops[].quantity` (string): few, several, many
- `metadata` (object): 
- `metadata.narrative` (string): Dense volcanic rock with distinctive dark banding. Exceptional compression strength., Pale-barked tree with wood that absorbs shock beautifully. Weapon smiths prize these for handle material., Volcanic glass born in eruption's heart. Razor-sharp edges, incredibly brittle.
- `metadata.tags` (array): standard, wood, temporal
- `name` (string): Obsidian Flow, Oak Tree, Genesis Structure
- `requiredTool` (string): pickaxe, axe
- `resourceId` (string): limestone_outcrop, basalt_column, eternity_monolith
- `respawnTime` (null, string): None, very_slow, normal
- `tier` (integer): 1, 2, 3

---

### skills
**Description**: Player skill definitions
**Files**: skills-skills-1.JSON
**Total Fields**: 39

**Key Fields**:
- `categories` (array): forestry, refining, gathering
- `cost` (object): 
- `cost.cooldown` (string): moderate, short, long
- `cost.mana` (string): moderate, extreme, low
- `description` (string): Move significantly faster for a brief period., Dramatically boost crafted item quality and gain massive rarity upgrade chance., Instantly restore a moderate amount of health.
- `effect` (object): 
- `effect.additionalEffects` (array): 
- `effect.additionalEffects[]` (object): 
- `effect.additionalEffects[].category` (string): refining, mining, damage
- `effect.additionalEffects[].duration` (string): moderate, long, extended
- `effect.additionalEffects[].magnitude` (string): major, moderate, extreme
- `effect.additionalEffects[].target` (string): area, self, enemy
- `effect.additionalEffects[].type` (string): quicken, pierce, elevate
- `effect.category` (string): forestry, refining, mining
- `effect.duration` (string): instant, moderate, brief
- `effect.magnitude` (string): major, extreme, moderate
- `effect.target` (string): resource_node, area, self
- `effect.type` (string): transcend, quicken, fortify
- `evolution` (object): 

---

### tag-definitions
**Description**: Master tag system definitions
**Files**: tag-definitions.JSON
**Total Fields**: 536

**Key Fields**:
- `categories` (object): 
- `categories.armor_type` (array): medium, robes, heavy
- `categories.class` (array): scholar, scavenger, artisan
- `categories.context` (array): ally, friendly, device
- `categories.damage_type` (array): physical, poison, lightning
- `categories.equipment` (array): 2H, versatile, 1H
- `categories.geometry` (array): projectile, beam, cone
- `categories.playstyle` (array): ranged, caster, tanky
- `categories.special` (array): lifesteal, knockback, vampiric
- `categories.status_buff` (array): invisible, regeneration, quicken
- `categories.status_debuff` (array): freeze, poison_status, slow
- `categories.trigger` (array): on_damage, on_hit, instant
- `conflict_resolution` (object): 
- `conflict_resolution.geometry_priority` (array): beam, cone, circle
- `conflict_resolution.mutually_exclusive` (object): 
- `conflict_resolution.mutually_exclusive.1H` (array): versatile, 2H
- `conflict_resolution.mutually_exclusive.2H` (array): versatile, 1H
- `conflict_resolution.mutually_exclusive.burn` (array): freeze
- `conflict_resolution.mutually_exclusive.freeze` (array): burn

---

### titles
**Description**: Achievement title definitions
**Files**: titles-1.JSON
**Total Fields**: 56

**Key Fields**:
- `acquisitionMethod` (string): event_based_rng, hidden_discovery, special_achievement
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
**Description**: Qualitative to numeric value mappings
**Files**: value-translation-table-1.JSON
**Total Fields**: 175

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

---

## All Tags

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
- `Shadow damage`
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
- `bronze`
- `buff`
- `burn`
- `burning`
- `burst`
- `bypass`
- `carapace`
- `caster`
- `chain`
- `chaos`
- `charge`
- `chest`
- `chill`
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
- `copper`
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
- `forge`
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
- `golem`
- `hands`
- `harvesting`
- `haste`
- `head`
- `heal_over_time`
- `healing`
- `heavy`
- `hemorrhage`
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
- `mobile`
- `mobility`
- `monster`
- `movement`
- `multi_purpose`
- `multiplicative`
- `mythical`
- `nature`
- `necrotic`
- `none`
- `oak`
- `ore`
- `orichalcum`
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
- `quantum`
- `quicken`
- `radial`
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
- `reflect_damage`
- `regen`
- `regeneration`
- `repair`
- `repeatable`
- `resistance`
- `ring`
- `root`
- `rooted`
- `rush`
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
- `worldtree`
- `wraith`
- `yield`