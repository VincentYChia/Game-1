"""
Automatically extracted few-shot examples from training data.
"""

EXTRACTED_EXAMPLES = {
    "1": [
        {
            "input": """{
  "recipeId": "smithing_iron_shortsword",
  "stationTier": 1,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "iron_ingot",
      "quantity": 2
    },
    {
      "materialId": "oak_plank",
      "quantity": 1
    }
  ],
  "narrative": "The foundational smithing technique - blade, tang, handle. Simple in concept, demanding in execution. Every smith remembers their first sword."
}""",
            "output": """{
  "metadata": {
    "narrative": "A simple iron blade with a wooden handle. Every warrior's first step on the path to mastery. The weight feels right in your hand - not perfect, but yours.",
    "tags": [
      "melee",
      "sword",
      "versatile",
      "starter"
    ]
  },
  "itemId": "iron_shortsword",
  "name": "Iron Shortsword",
  "category": "equipment",
  "type": "weapon",
  "subtype": "shortsword",
  "tier": 1,
  "rarity": "common",
  "range": 1,
  "slot": "mainHand",
  "effectTags": [
    "physical",
    "slashing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 30
  },
  "statMultipliers": {
    "damage": 1.0,
    "attackSpeed": 1.0,
    "durability": 1.0,
    "weight": 1.0
  },
  "requirements": {
    "level": 1,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_pickaxe",
  "stationTier": 1,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "copper_ingot",
      "quantity": 3
    },
    {
      "materialId": "oak_log",
      "quantity": 2
    }
  ],
  "narrative": "Your first pickaxe. The gateway to greater resources and deeper discoveries."
}""",
            "output": """{
  "metadata": {
    "narrative": "Basic copper pickaxe with a wooden handle. Your first step into the mining profession - crude but functional.",
    "tags": [
      "tool",
      "pickaxe",
      "starter"
    ]
  },
  "itemId": "copper_pickaxe",
  "name": "Copper Pickaxe",
  "category": "equipment",
  "type": "tool",
  "subtype": "pickaxe",
  "tier": 1,
  "rarity": "common",
  "range": 1,
  "effectTags": [
    "physical",
    "piercing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 10
  },
  "stats": {
    "damage": [
      8,
      12
    ],
    "mining": 10,
    "durability": [
      500,
      500
    ],
    "weight": 4.0
  },
  "requirements": {
    "level": 1
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_steel_longsword",
  "stationTier": 2,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "dire_fang",
      "quantity": 2
    },
    {
      "materialId": "maple_plank",
      "quantity": 1
    },
    {
      "materialId": "steel_ingot",
      "quantity": 4
    }
  ],
  "narrative": "Balanced steel longsword. The blade flows like water, strikes like thunder."
}""",
            "output": """{
  "metadata": {
    "narrative": "Balanced steel longsword that flows like water and strikes like thunder. The blade sings when it cuts through air, a testament to its quality.",
    "tags": [
      "melee",
      "sword",
      "versatile",
      "quality"
    ]
  },
  "itemId": "steel_longsword",
  "name": "Steel Longsword",
  "category": "equipment",
  "type": "weapon",
  "subtype": "longsword",
  "tier": 2,
  "rarity": "uncommon",
  "range": 1,
  "slot": "mainHand",
  "effectTags": [
    "physical",
    "slashing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 40
  },
  "statMultipliers": {
    "damage": 1.1,
    "attackSpeed": 1.0,
    "durability": 1.1,
    "weight": 1.0
  },
  "requirements": {
    "level": 8,
    "stats": {
      "STR": 10
    }
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_iron_chestplate",
  "stationTier": 2,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "beetle_carapace",
      "quantity": 6
    },
    {
      "materialId": "iron_ingot",
      "quantity": 7
    },
    {
      "materialId": "wolf_pelt",
      "quantity": 5
    }
  ],
  "narrative": "Iron plates protect vital organs. Heavy but reliable."
}""",
            "output": """{
  "metadata": {
    "narrative": "Iron plates protecting vital organs with beetle carapace reinforcement. Heavy but reliable. When arrows fly and blades swing, you'll appreciate every ounce of protection.",
    "tags": [
      "armor",
      "chest",
      "heavy",
      "standard"
    ]
  },
  "itemId": "iron_chestplate",
  "name": "Iron Chestplate",
  "category": "equipment",
  "type": "armor",
  "subtype": "chestplate",
  "tier": 2,
  "rarity": "common",
  "slot": "chest",
  "statMultipliers": {
    "defense": 1.0,
    "durability": 1.0,
    "weight": 1.0
  },
  "requirements": {
    "level": 6,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_mithril_dagger",
  "stationTier": 3,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "ebony_plank",
      "quantity": 4
    },
    {
      "materialId": "essence_blood",
      "quantity": 1
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 3
    }
  ],
  "narrative": "Mithril dagger that seems to shimmer out of existence. Wickedly sharp, impossibly light."
}""",
            "output": """{
  "metadata": {
    "narrative": "Mithril dagger that seems to shimmer out of existence. Wickedly sharp and impossibly light, it strikes faster than the eye can follow. The blade whispers through air and flesh alike.",
    "tags": [
      "melee",
      "dagger",
      "1H",
      "fast",
      "precision",
      "legendary"
    ]
  },
  "itemId": "mithril_dagger",
  "name": "Mithril Dagger",
  "category": "equipment",
  "type": "weapon",
  "subtype": "dagger",
  "tier": 3,
  "rarity": "rare",
  "range": 0.5,
  "slot": "mainHand",
  "effectTags": [
    "physical",
    "piercing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 42
  },
  "statMultipliers": {
    "damage": 1.1,
    "attackSpeed": 1.2,
    "durability": 1.5,
    "weight": 0.5
  },
  "requirements": {
    "level": 16,
    "stats": {
      "AGI": 20
    }
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_mithril_pickaxe",
  "stationTier": 3,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "ebony_plank",
      "quantity": 5
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 9
    }
  ],
  "narrative": "Legendary mithril pickaxe that sings through stone. Impossibly light yet incredibly effective."
}""",
            "output": """{
  "metadata": {
    "narrative": "Legendary mithril pickaxe that sings through stone. Impossibly light yet incredibly effective.",
    "tags": [
      "tool",
      "pickaxe",
      "legendary"
    ]
  },
  "itemId": "mithril_pickaxe",
  "name": "Mithril Pickaxe",
  "category": "equipment",
  "type": "tool",
  "subtype": "pickaxe",
  "tier": 4,
  "rarity": "rare",
  "range": 1,
  "effectTags": [
    "physical",
    "piercing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 75
  },
  "stats": {
    "damage": [
      60,
      90
    ],
    "mining": 80,
    "durability": [
      4000,
      4000
    ],
    "weight": 3.0
  },
  "requirements": {
    "level": 20
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_axe",
  "stationTier": 1,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "copper_ingot",
      "quantity": 3
    },
    {
      "materialId": "pine_log",
      "quantity": 2
    }
  ],
  "narrative": "Basic axe for woodcutting. Simple but essential for any aspiring adventurer."
}""",
            "output": """{
  "metadata": {
    "narrative": "Simple copper axe with oak handle. Every woodcutter's first companion on the journey to mastery.",
    "tags": [
      "tool",
      "axe",
      "starter"
    ]
  },
  "itemId": "copper_axe",
  "name": "Copper Axe",
  "category": "equipment",
  "type": "tool",
  "subtype": "axe",
  "tier": 1,
  "rarity": "common",
  "range": 1,
  "effectTags": [
    "physical",
    "slashing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 10
  },
  "stats": {
    "damage": [
      8,
      12
    ],
    "forestry": 10,
    "durability": [
      500,
      500
    ],
    "weight": 3.5
  },
  "requirements": {
    "level": 1
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_spear",
  "stationTier": 1,
  "stationType": "smithing",
  "inputs": [
    {
      "materialId": "ash_log",
      "quantity": 2
    },
    {
      "materialId": "copper_ingot",
      "quantity": 1
    }
  ],
  "narrative": "Simple spear with copper tip. Keep your enemies at a distance."
}""",
            "output": """{
  "metadata": {
    "narrative": "Simple copper-tipped spear with ash wood shaft. The extra reach keeps danger at arm's length. Perfect for those who prefer distance over direct confrontation.",
    "tags": [
      "melee",
      "spear",
      "versatile",
      "reach"
    ]
  },
  "itemId": "copper_spear",
  "name": "Copper Spear",
  "category": "equipment",
  "type": "weapon",
  "subtype": "spear",
  "tier": 1,
  "rarity": "common",
  "range": 2,
  "slot": "mainHand",
  "effectTags": [
    "physical",
    "piercing",
    "single"
  ],
  "effectParams": {
    "baseDamage": 25
  },
  "statMultipliers": {
    "damage": 1.0,
    "attackSpeed": 1.0,
    "durability": 1.0,
    "weight": 0.9
  },
  "requirements": {
    "level": 1,
    "stats": {}
  },
  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}"""
        }
    ],
    "1x2": [
        {
            "input": """{
  "recipeId": "smithing_iron_shortsword",
  "itemId": "iron_shortsword",
  "tier": 1,
  "gridSize": "3x3",
  "inputs": [
    {
      "materialId": "iron_ingot",
      "quantity": 2
    },
    {
      "materialId": "oak_plank",
      "quantity": 1
    }
  ],
  "itemMetadata": {
    "narrative": "A simple iron blade with a wooden handle. Every warrior's first step on the path to mastery. The weight feels right in your hand - not perfect, but yours.",
    "tags": [
      "melee",
      "sword",
      "versatile",
      "starter"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_iron_shortsword",
  "placementMap": {
    "3,1": "oak_plank",
    "2,2": "iron_ingot",
    "1,3": "iron_ingot"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "The foundational smithing technique - blade, tang, handle. Simple in concept, demanding in execution. Every smith remembers their first sword."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_pickaxe",
  "itemId": "copper_pickaxe",
  "tier": 1,
  "gridSize": "3x3",
  "inputs": [
    {
      "materialId": "copper_ingot",
      "quantity": 3
    },
    {
      "materialId": "oak_log",
      "quantity": 2
    }
  ],
  "itemMetadata": {
    "narrative": "Basic copper pickaxe with a wooden handle. Your first step into the mining profession - crude but functional.",
    "tags": [
      "tool",
      "pickaxe",
      "starter"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_copper_pickaxe",
  "placementMap": {
    "3,1": "oak_log",
    "2,2": "oak_log",
    "1,2": "copper_ingot",
    "1,3": "copper_ingot",
    "2,3": "copper_ingot"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "Your first pickaxe. The gateway to greater resources and deeper discoveries."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_steel_longsword",
  "itemId": "steel_longsword",
  "tier": 2,
  "gridSize": "5x5",
  "inputs": [
    {
      "materialId": "dire_fang",
      "quantity": 2
    },
    {
      "materialId": "maple_plank",
      "quantity": 1
    },
    {
      "materialId": "steel_ingot",
      "quantity": 4
    }
  ],
  "itemMetadata": {
    "narrative": "Balanced steel longsword that flows like water and strikes like thunder. The blade sings when it cuts through air, a testament to its quality.",
    "tags": [
      "melee",
      "sword",
      "versatile",
      "quality"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_steel_longsword",
  "placementMap": {
    "4,2": "steel_ingot",
    "3,3": "steel_ingot",
    "2,4": "steel_ingot",
    "1,5": "steel_ingot",
    "5,1": "maple_plank",
    "4,1": "dire_fang",
    "5,2": "dire_fang"
  },
  "metadata": {
    "gridSize": "5x5",
    "narrative": "Balanced steel longsword. The blade flows like water, strikes like thunder."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_iron_chestplate",
  "itemId": "iron_chestplate",
  "tier": 2,
  "gridSize": "3x3",
  "inputs": [
    {
      "materialId": "beetle_carapace",
      "quantity": 6
    },
    {
      "materialId": "iron_ingot",
      "quantity": 7
    },
    {
      "materialId": "wolf_pelt",
      "quantity": 5
    }
  ],
  "itemMetadata": {
    "narrative": "Iron plates protecting vital organs with beetle carapace reinforcement. Heavy but reliable. When arrows fly and blades swing, you'll appreciate every ounce of protection.",
    "tags": [
      "armor",
      "chest",
      "heavy",
      "standard"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_iron_chestplate",
  "placementMap": {
    "2,2": "beetle_carapace",
    "3,2": "iron_ingot",
    "2,4": "beetle_carapace",
    "3,4": "iron_ingot",
    "1,2": "wolf_pelt",
    "1,4": "wolf_pelt",
    "3,3": "iron_ingot",
    "2,3": "iron_ingot",
    "4,2": "iron_ingot",
    "4,4": "iron_ingot",
    "4,3": "iron_ingot",
    "5,2": "wolf_pelt",
    "5,4": "wolf_pelt",
    "5,3": "wolf_pelt",
    "3,5": "beetle_carapace",
    "4,5": "beetle_carapace",
    "3,1": "beetle_carapace",
    "4,1": "beetle_carapace"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "Iron plates protect vital organs. Heavy but reliable."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_mithril_dagger",
  "itemId": "mithril_dagger",
  "tier": 3,
  "gridSize": "5x5",
  "inputs": [
    {
      "materialId": "ebony_plank",
      "quantity": 4
    },
    {
      "materialId": "essence_blood",
      "quantity": 1
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 3
    }
  ],
  "itemMetadata": {
    "narrative": "Mithril dagger that seems to shimmer out of existence. Wickedly sharp and impossibly light, it strikes faster than the eye can follow. The blade whispers through air and flesh alike.",
    "tags": [
      "melee",
      "dagger",
      "1H",
      "fast",
      "precision",
      "legendary"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_mithril_dagger",
  "placementMap": {
    "5,3": "ebony_plank",
    "4,4": "mithril_ingot",
    "3,5": "mithril_ingot",
    "4,2": "ebony_plank",
    "6,4": "ebony_plank",
    "6,2": "ebony_plank",
    "7,1": "essence_blood",
    "2,6": "mithril_ingot"
  },
  "metadata": {
    "gridSize": "5x5",
    "narrative": "Mithril dagger that seems to shimmer out of existence. Wickedly sharp, impossibly light."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_mithril_pickaxe",
  "itemId": "mithril_pickaxe",
  "tier": 3,
  "gridSize": "7x7",
  "inputs": [
    {
      "materialId": "ebony_plank",
      "quantity": 5
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 9
    }
  ],
  "itemMetadata": {
    "narrative": "Legendary mithril pickaxe that sings through stone. Impossibly light yet incredibly effective.",
    "tags": [
      "tool",
      "pickaxe",
      "legendary"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_mithril_pickaxe",
  "placementMap": {
    "7,1": "ebony_plank",
    "6,2": "ebony_plank",
    "5,3": "ebony_plank",
    "4,4": "ebony_plank",
    "4,7": "mithril_ingot",
    "3,5": "ebony_plank",
    "2,6": "mithril_ingot",
    "3,7": "mithril_ingot",
    "1,4": "mithril_ingot",
    "1,5": "mithril_ingot",
    "1,6": "mithril_ingot",
    "2,7": "mithril_ingot",
    "2,5": "mithril_ingot",
    "3,6": "mithril_ingot"
  },
  "metadata": {
    "gridSize": "7x7",
    "narrative": "Legendary mithril pickaxe that sings through stone. Impossibly light yet incredibly effective."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_axe",
  "itemId": "copper_axe",
  "tier": 1,
  "gridSize": "3x3",
  "inputs": [
    {
      "materialId": "copper_ingot",
      "quantity": 3
    },
    {
      "materialId": "pine_log",
      "quantity": 2
    }
  ],
  "itemMetadata": {
    "narrative": "Simple copper axe with oak handle. Every woodcutter's first companion on the journey to mastery.",
    "tags": [
      "tool",
      "axe",
      "starter"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_copper_axe",
  "placementMap": {
    "3,2": "pine_log",
    "2,2": "pine_log",
    "1,2": "copper_ingot",
    "1,3": "copper_ingot",
    "2,3": "copper_ingot"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "Basic axe for woodcutting. Simple but essential for any aspiring adventurer."
  }
}"""
        },
        {
            "input": """{
  "recipeId": "smithing_copper_spear",
  "itemId": "copper_spear",
  "tier": 1,
  "gridSize": "3x3",
  "inputs": [
    {
      "materialId": "ash_log",
      "quantity": 2
    },
    {
      "materialId": "copper_ingot",
      "quantity": 1
    }
  ],
  "itemMetadata": {
    "narrative": "Simple copper-tipped spear with ash wood shaft. The extra reach keeps danger at arm's length. Perfect for those who prefer distance over direct confrontation.",
    "tags": [
      "melee",
      "spear",
      "versatile",
      "reach"
    ]
  }
}""",
            "output": """{
  "recipeId": "smithing_copper_spear",
  "placementMap": {
    "1,3": "copper_ingot",
    "2,2": "ash_log",
    "3,1": "ash_log"
  },
  "metadata": {
    "gridSize": "3x3",
    "narrative": "Simple spear with copper tip. Keep your enemies at a distance."
  }
}"""
        }
    ],
    "2": [
        {
            "input": """{
  "recipeId": "refining_copper_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "copper_ore",
      "quantity": 1
    }
  ],
  "narrative": "Smelting raw copper into usable ingots. The foundation of metallurgy."
}""",
            "output": """{
  "metadata": {
    "narrative": "Refined copper shaped into usable ingots. Malleable, forgiving for beginner crafters, accepts enchantments readily.",
    "tags": [
      "refined",
      "metal",
      "starter"
    ]
  },
  "materialId": "copper_ingot",
  "name": "Copper Ingot",
  "tier": 1,
  "rarity": "common",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_iron_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "iron_ore",
      "quantity": 1
    }
  ],
  "narrative": "Smelting iron ore into reliable metal. Backbone of civilization. Crushing the ore first increases yield."
}""",
            "output": """{
  "metadata": {
    "narrative": "Moderately conductive, somewhat malleable when heated. The workhorse of civilization - reliable, abundant, essential for weapons, tools, and armor.",
    "tags": [
      "refined",
      "metal",
      "standard"
    ]
  },
  "materialId": "iron_ingot",
  "name": "Iron Ingot",
  "tier": 1,
  "rarity": "common",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_tin_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "tin_ore",
      "quantity": 1
    }
  ],
  "narrative": "Refining tin ore into silvery metal. Essential for alloys."
}""",
            "output": """{
  "metadata": {
    "narrative": "Refined tin with excellent magical conductivity. Used in alloys and enchanted items.",
    "tags": [
      "refined",
      "metal",
      "magical"
    ]
  },
  "materialId": "tin_ingot",
  "name": "Tin Ingot",
  "tier": 1,
  "rarity": "uncommon",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_steel_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "steel_ore",
      "quantity": 1
    }
  ],
  "narrative": "Forging steel from carbon-rich ore. Requires intense heat."
}""",
            "output": """{
  "metadata": {
    "narrative": "Superior to iron in every way. Holds a keen edge, resists corrosion, and strikes with authority.",
    "tags": [
      "refined",
      "metal",
      "advanced"
    ]
  },
  "materialId": "steel_ingot",
  "name": "Steel Ingot",
  "tier": 2,
  "rarity": "uncommon",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_mithril_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "mithril_ore",
      "quantity": 1
    }
  ],
  "narrative": "Refining legendary mithril. The metal seems to purify itself, occasionally yielding higher quality ingots."
}""",
            "output": """{
  "metadata": {
    "narrative": "Refined mithril that whispers of ancient secrets. Perfect for weapons that need both power and grace.",
    "tags": [
      "refined",
      "metal",
      "legendary"
    ]
  },
  "materialId": "mithril_ingot",
  "name": "Mithril Ingot",
  "tier": 2,
  "rarity": "rare",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_adamantine_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "adamantine_ore",
      "quantity": 1
    }
  ],
  "narrative": "Smelting adamantine requires extreme heat and purification techniques. Sometimes yields exceptionally pure ingots."
}""",
            "output": """{
  "metadata": {
    "narrative": "Nearly indestructible metal that can withstand forces that would shatter lesser materials. Each ingot represents months of careful refinement.",
    "tags": [
      "refined",
      "metal",
      "rare"
    ]
  },
  "materialId": "adamantine_ingot",
  "name": "Adamantine Ingot",
  "tier": 3,
  "rarity": "rare",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_orichalcum_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "orichalcum_ore",
      "quantity": 1
    }
  ],
  "narrative": "Refining the ancient metal. Channels both physical and magical forces."
}""",
            "output": """{
  "metadata": {
    "narrative": "The pinnacle of mortal metallurgy. Channels both physical force and magical energy with perfect efficiency.",
    "tags": [
      "refined",
      "metal",
      "ancient"
    ]
  },
  "materialId": "orichalcum_ingot",
  "name": "Orichalcum Ingot",
  "tier": 3,
  "rarity": "epic",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "recipeId": "refining_etherion_ore_to_ingot",
  "stationTier": 1,
  "stationType": "refining",
  "inputs": [
    {
      "materialId": "etherion_ore",
      "quantity": 1
    }
  ],
  "narrative": "Refining metal that exists in multiple states. Reality bends during the process."
}""",
            "output": """{
  "metadata": {
    "narrative": "Reality-bending metal that has transcended conventional physics. Durability frozen in time, effects can occur before cause.",
    "tags": [
      "refined",
      "metal",
      "mythical",
      "temporal"
    ]
  },
  "materialId": "etherion_ingot",
  "name": "Etherion Ingot",
  "tier": 4,
  "rarity": "legendary",
  "category": "metal"
}"""
        }
    ],
    "2x2": [
        {
            "input": """{
  "recipeId": "refining_copper_ore_to_ingot",
  "materialId": "copper_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Refined copper shaped into usable ingots. Malleable, forgiving for beginner crafters, accepts enchantments readily.",
    "tags": [
      "refined",
      "metal",
      "starter"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_copper_ore_to_ingot",
  "outputId": "copper_ingot",
  "stationTier": 1,
  "coreInputs": [
    {
      "materialId": "copper_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Smelting raw copper. Foundation of metallurgy - heat purifies ore, impurities burn away."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_iron_ore_to_ingot",
  "materialId": "iron_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Moderately conductive, somewhat malleable when heated. The workhorse of civilization - reliable, abundant, essential for weapons, tools, and armor.",
    "tags": [
      "refined",
      "metal",
      "standard"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_iron_ore_to_ingot",
  "outputId": "iron_ingot",
  "stationTier": 1,
  "coreInputs": [
    {
      "materialId": "iron_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Smelting iron ore. Backbone of civilization - each cylinder reveals metal within stone."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_tin_ore_to_ingot",
  "materialId": "tin_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Refined tin with excellent magical conductivity. Used in alloys and enchanted items.",
    "tags": [
      "refined",
      "metal",
      "magical"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_tin_ore_to_ingot",
  "outputId": "tin_ingot",
  "stationTier": 1,
  "coreInputs": [
    {
      "materialId": "tin_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Refining tin ore. Essential for alloys - cylinders click with different tone than iron."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_steel_ore_to_ingot",
  "materialId": "steel_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Superior to iron in every way. Holds a keen edge, resists corrosion, and strikes with authority.",
    "tags": [
      "refined",
      "metal",
      "advanced"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_steel_ore_to_ingot",
  "outputId": "steel_ingot",
  "stationTier": 2,
  "coreInputs": [
    {
      "materialId": "steel_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Forging steel from carbon-rich ore. Requires intense heat - cylinders resist then yield."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_mithril_ore_to_ingot",
  "materialId": "mithril_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Refined mithril that whispers of ancient secrets. Perfect for weapons that need both power and grace.",
    "tags": [
      "refined",
      "metal",
      "legendary"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_mithril_ore_to_ingot",
  "outputId": "mithril_ingot",
  "stationTier": 2,
  "coreInputs": [
    {
      "materialId": "mithril_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Refining legendary mithril. Metal purifies itself - cylinders align eagerly."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_adamantine_ore_to_ingot",
  "materialId": "adamantine_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Nearly indestructible metal that can withstand forces that would shatter lesser materials. Each ingot represents months of careful refinement.",
    "tags": [
      "refined",
      "metal",
      "rare"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_adamantine_ore_to_ingot",
  "outputId": "adamantine_ingot",
  "stationTier": 3,
  "coreInputs": [
    {
      "materialId": "adamantine_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Smelting adamantine. Extreme heat required - cylinders groan under strain."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_orichalcum_ore_to_ingot",
  "materialId": "orichalcum_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "The pinnacle of mortal metallurgy. Channels both physical force and magical energy with perfect efficiency.",
    "tags": [
      "refined",
      "metal",
      "ancient"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_orichalcum_ore_to_ingot",
  "outputId": "orichalcum_ingot",
  "stationTier": 3,
  "coreInputs": [
    {
      "materialId": "orichalcum_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Refining ancient metal. Channels physical and magical forces - harmonic resonance."
}"""
        },
        {
            "input": """{
  "recipeId": "refining_etherion_ore_to_ingot",
  "materialId": "etherion_ingot",
  "tier": 1,
  "coreInput": {},
  "surroundingInputs": [],
  "materialMetadata": {
    "narrative": "Reality-bending metal that has transcended conventional physics. Durability frozen in time, effects can occur before cause.",
    "tags": [
      "refined",
      "metal",
      "mythical",
      "temporal"
    ]
  }
}""",
            "output": """{
  "recipeId": "refining_etherion_ore_to_ingot",
  "outputId": "etherion_ingot",
  "stationTier": 4,
  "coreInputs": [
    {
      "materialId": "etherion_ore",
      "quantity": 1
    }
  ],
  "surroundingInputs": [],
  "narrative": "Refining multidimensional metal. Reality bends - impossible configurations work."
}"""
        }
    ],
    "3": [
        {
            "input": """{
  "recipeId": "alchemy_minor_health_potion",
  "stationTier": 1,
  "stationType": "alchemy",
  "inputs": [
    {
      "materialId": "slime_gel",
      "quantity": 2
    },
    {
      "materialId": "wolf_pelt",
      "quantity": 1
    }
  ],
  "narrative": "Basic healing potion from natural herbs and slime gel. Every alchemist's first creation."
}""",
            "output": """{
  "metadata": {
    "narrative": "Basic healing potion from natural herbs and slime gel. Every alchemist's first creation. Tastes terrible, works wonderfully. Wounds close and pain fades within moments.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "starter"
    ]
  },
  "itemId": "minor_health_potion",
  "name": "Minor Health Potion",
  "category": "consumable",
  "type": "potion",
  "subtype": "healing",
  "tier": 1,
  "rarity": "common",
  "effect": "Restores 50 HP instantly",
  "duration": 0,
  "stackSize": 20,
  "statMultipliers": {
    "weight": 0.2
  },
  "requirements": {
    "level": 1,
    "stats": {}
  },
  "flags": {
    "stackable": true,
    "consumable": true,
    "repairable": false
  }
}"""
        },
        {
            "input": """{
  "recipeId": "alchemy_health_potion",
  "stationTier": 2,
  "stationType": "alchemy",
  "inputs": [
    {
      "materialId": "living_ichor",
      "quantity": 2
    },
    {
      "materialId": "water_crystal",
      "quantity": 2
    },
    {
      "materialId": "slime_gel",
      "quantity": 1
    }
  ],
  "narrative": "Improved healing potion using water crystals to amplify restorative properties."
}""",
            "output": """{
  "metadata": {
    "narrative": "Improved healing potion using water crystals to amplify restorative properties. The liquid shimmers with captured vitality. One swallow and you feel strength returning.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "standard"
    ]
  },
  "itemId": "health_potion",
  "name": "Health Potion",
  "category": "consumable",
  "type": "potion",
  "subtype": "healing",
  "tier": 2,
  "rarity": "common",
  "effect": "Restores 100 HP instantly",
  "duration": 0,
  "stackSize": 20,
  "statMultipliers": {
    "weight": 0.2
  },
  "requirements": {
    "level": 5,
    "stats": {}
  },
  "flags": {
    "stackable": true,
    "consumable": true,
    "repairable": false
  }
}"""
        },
        {
            "input": """{
  "recipeId": "alchemy_greater_health_potion",
  "stationTier": 3,
  "stationType": "alchemy",
  "inputs": [
    {
      "materialId": "essence_blood",
      "quantity": 3
    },
    {
      "materialId": "light_gem",
      "quantity": 2
    },
    {
      "materialId": "living_ichor",
      "quantity": 2
    }
  ],
  "narrative": "Powerful healing elixir using essence blood and light gems. Closes wounds rapidly."
}""",
            "output": """{
  "metadata": {
    "narrative": "Powerful healing elixir using essence blood and light gems. Closes wounds rapidly, mends broken bones, restores vitality. The taste of life itself.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "quality"
    ]
  },
  "itemId": "greater_health_potion",
  "name": "Greater Health Potion",
  "category": "consumable",
  "type": "potion",
  "subtype": "healing",
  "tier": 3,
  "rarity": "uncommon",
  "effect": "Restores 200 HP instantly",
  "duration": 0,
  "stackSize": 20,
  "statMultipliers": {
    "weight": 0.2
  },
  "requirements": {
    "level": 12,
    "stats": {}
  },
  "flags": {
    "stackable": true,
    "consumable": true,
    "repairable": false
  }
}"""
        }
    ],
    "3x2": [
        {
            "input": """{
  "recipeId": "alchemy_minor_health_potion",
  "itemId": "minor_health_potion",
  "tier": 1,
  "inputs": [
    {
      "materialId": "slime_gel",
      "quantity": 2
    },
    {
      "materialId": "wolf_pelt",
      "quantity": 1
    }
  ],
  "itemMetadata": {
    "narrative": "Basic healing potion from natural herbs and slime gel. Every alchemist's first creation. Tastes terrible, works wonderfully. Wounds close and pain fades within moments.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "starter"
    ]
  }
}""",
            "output": """{
  "recipeId": "alchemy_minor_health_potion",
  "outputId": "minor_health_potion",
  "stationTier": 1,
  "ingredients": [
    {
      "slot": 1,
      "materialId": "slime_gel",
      "quantity": 2
    },
    {
      "slot": 2,
      "materialId": "wolf_pelt",
      "quantity": 1
    }
  ],
  "narrative": "Slime gel dissolves first, creating restorative base. Wolf pelt binds mixture second. Watch for gentle green glow - too quick and they won't merge."
}"""
        },
        {
            "input": """{
  "recipeId": "alchemy_health_potion",
  "itemId": "health_potion",
  "tier": 2,
  "inputs": [
    {
      "materialId": "living_ichor",
      "quantity": 2
    },
    {
      "materialId": "water_crystal",
      "quantity": 2
    },
    {
      "materialId": "slime_gel",
      "quantity": 1
    }
  ],
  "itemMetadata": {
    "narrative": "Improved healing potion using water crystals to amplify restorative properties. The liquid shimmers with captured vitality. One swallow and you feel strength returning.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "standard"
    ]
  }
}""",
            "output": """{
  "recipeId": "alchemy_health_potion",
  "outputId": "health_potion",
  "stationTier": 2,
  "ingredients": [
    {
      "slot": 1,
      "materialId": "living_ichor",
      "quantity": 2
    },
    {
      "slot": 2,
      "materialId": "water_crystal",
      "quantity": 2
    },
    {
      "slot": 3,
      "materialId": "slime_gel",
      "quantity": 1
    }
  ],
  "narrative": "Living ichor provides life force base. Water crystals amplify properties. Slime gel completes stabilization. Each stage must settle before next."
}"""
        },
        {
            "input": """{
  "recipeId": "alchemy_greater_health_potion",
  "itemId": "greater_health_potion",
  "tier": 3,
  "inputs": [
    {
      "materialId": "essence_blood",
      "quantity": 3
    },
    {
      "materialId": "light_gem",
      "quantity": 2
    },
    {
      "materialId": "living_ichor",
      "quantity": 2
    }
  ],
  "itemMetadata": {
    "narrative": "Powerful healing elixir using essence blood and light gems. Closes wounds rapidly, mends broken bones, restores vitality. The taste of life itself.",
    "tags": [
      "potion",
      "healing",
      "consumable",
      "quality"
    ]
  }
}""",
            "output": """{
  "recipeId": "alchemy_greater_health_potion",
  "outputId": "greater_health_potion",
  "stationTier": 3,
  "ingredients": [
    {
      "slot": 1,
      "materialId": "essence_blood",
      "quantity": 3
    },
    {
      "slot": 2,
      "materialId": "light_gem",
      "quantity": 2
    },
    {
      "slot": 3,
      "materialId": "living_ichor",
      "quantity": 2
    }
  ],
  "narrative": "Essence blood provides foundation. Light gem illuminates and purifies. Living ichor amplifies. Miss a peak, lose potency - catch them all, wounds close rapidly."
}"""
        }
    ],
    "4": [
    ],
    "4x2": [
    ],
    "5": [
        {
            "input": """{
  "recipeId": "enchanting_sharpness_basic",
  "enchantmentId": "sharpness_1",
  "stationTier": 1,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "fire_crystal",
      "quantity": 4
    },
    {
      "materialId": "granite",
      "quantity": 2
    },
    {
      "materialId": "iron_ingot",
      "quantity": 3
    },
    {
      "materialId": "tin_ore",
      "quantity": 2
    }
  ],
  "narrative": "Basic sharpening enchantment using fire crystals. The edge never dulls."
}""",
            "output": """{
  "enchantmentId": "sharpness_1",
  "name": "",
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.1,
    "stackable": false,
    "conflictsWith": [
      "sharpness_2",
      "sharpness_3"
    ]
  },
  "metadata": {
    "narrative": "Basic sharpening enchantment using fire crystals. The edge never dulls.",
    "tags": [
      "weapon",
      "damage",
      "basic"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_durability_basic",
  "enchantmentId": "unbreaking_1",
  "stationTier": 1,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "beetle_carapace",
      "quantity": 4
    },
    {
      "materialId": "earth_crystal",
      "quantity": 4
    }
  ],
  "narrative": "Basic durability enchantment. Items last longer before needing repair."
}""",
            "output": """{
  "enchantmentId": "unbreaking_1",
  "name": "",
  "applicableTo": [
    "weapon",
    "tool",
    "armor"
  ],
  "effect": {
    "type": "durability_multiplier",
    "value": 0.3,
    "stackable": false,
    "conflictsWith": [
      "unbreaking_2"
    ]
  },
  "metadata": {
    "narrative": "Basic durability enchantment. Items last longer before needing repair.",
    "tags": [
      "universal",
      "durability",
      "basic"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_sharpness_advanced",
  "enchantmentId": "sharpness_2",
  "stationTier": 2,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "dire_fang",
      "quantity": 3
    },
    {
      "materialId": "frost_essence",
      "quantity": 2
    },
    {
      "materialId": "lightning_shard",
      "quantity": 3
    },
    {
      "materialId": "marble",
      "quantity": 4
    }
  ],
  "narrative": "Improved sharpening using lightning shards. The blade crackles with energy."
}""",
            "output": """{
  "enchantmentId": "sharpness_2",
  "name": "",
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.2,
    "stackable": false,
    "conflictsWith": [
      "sharpness_1",
      "sharpness_3"
    ]
  },
  "metadata": {
    "narrative": "Improved sharpening using lightning shards. The blade crackles with energy.",
    "tags": [
      "weapon",
      "damage",
      "advanced"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_fire_aspect",
  "enchantmentId": "fire_aspect",
  "stationTier": 2,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "fire_crystal",
      "quantity": 6
    },
    {
      "materialId": "light_gem",
      "quantity": 1
    },
    {
      "materialId": "maple_plank",
      "quantity": 6
    },
    {
      "materialId": "steel_ingot",
      "quantity": 3
    }
  ],
  "narrative": "Fire enchantment for weapons. Strikes leave burning wounds."
}""",
            "output": """{
  "enchantmentId": "fire_aspect",
  "name": "",
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_over_time",
    "element": "fire",
    "damagePerSecond": 10,
    "duration": 5,
    "stackable": true,
    "conflictsWith": []
  },
  "metadata": {
    "narrative": "Fire enchantment for weapons. Strikes leave burning wounds.",
    "tags": [
      "weapon",
      "elemental",
      "fire"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_sharpness_master",
  "enchantmentId": "sharpness_3",
  "stationTier": 3,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 3
    },
    {
      "materialId": "diamond",
      "quantity": 5
    },
    {
      "materialId": "essence_blood",
      "quantity": 2
    },
    {
      "materialId": "marble",
      "quantity": 1
    },
    {
      "materialId": "phoenix_ash",
      "quantity": 3
    }
  ],
  "narrative": "Master sharpening using phoenix ash. The edge exists between states of matter."
}""",
            "output": """{
  "enchantmentId": "sharpness_3",
  "name": "",
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.35,
    "stackable": false,
    "conflictsWith": [
      "sharpness_1",
      "sharpness_2"
    ]
  },
  "metadata": {
    "narrative": "Master sharpening using phoenix ash. The edge exists between states of matter.",
    "tags": [
      "weapon",
      "damage",
      "legendary"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_durability_advanced",
  "enchantmentId": "unbreaking_2",
  "stationTier": 3,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 4
    },
    {
      "materialId": "diamond",
      "quantity": 4
    },
    {
      "materialId": "golem_core",
      "quantity": 1
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 8
    },
    {
      "materialId": "spectral_thread",
      "quantity": 8
    }
  ],
  "narrative": "Advanced durability enchantment using diamond. Nearly indestructible."
}""",
            "output": """{
  "enchantmentId": "unbreaking_2",
  "name": "",
  "applicableTo": [
    "weapon",
    "tool",
    "armor"
  ],
  "effect": {
    "type": "durability_multiplier",
    "value": 0.6,
    "stackable": false,
    "conflictsWith": [
      "unbreaking_1"
    ]
  },
  "metadata": {
    "narrative": "Advanced durability enchantment using diamond. Nearly indestructible.",
    "tags": [
      "universal",
      "durability",
      "advanced"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_fortune_advanced",
  "enchantmentId": "fortune_2",
  "stationTier": 4,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "chaos_matrix",
      "quantity": 3
    },
    {
      "materialId": "diamond",
      "quantity": 9
    },
    {
      "materialId": "genesis_lattice",
      "quantity": 4
    },
    {
      "materialId": "light_gem",
      "quantity": 4
    },
    {
      "materialId": "living_ichor",
      "quantity": 6
    },
    {
      "materialId": "obsidian",
      "quantity": 6
    }
  ],
  "narrative": "Master fortune using chaos essence. Reality bends toward abundance."
}""",
            "output": """{
  "enchantmentId": "fortune_2",
  "name": "",
  "applicableTo": [
    "tool"
  ],
  "effect": {
    "type": "bonus_yield_chance",
    "value": 0.6,
    "stackable": false,
    "conflictsWith": [
      "fortune_1",
      "silk_touch"
    ]
  },
  "metadata": {
    "narrative": "Master fortune using chaos essence. Reality bends toward abundance.",
    "tags": [
      "tool",
      "fortune",
      "master"
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_soulbound",
  "enchantmentId": "soulbound",
  "stationTier": 4,
  "stationType": "enchanting",
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 4
    },
    {
      "materialId": "chaos_matrix",
      "quantity": 4
    },
    {
      "materialId": "eternity_stone",
      "quantity": 4
    },
    {
      "materialId": "obsidian",
      "quantity": 4
    },
    {
      "materialId": "primordial_crystal",
      "quantity": 3
    },
    {
      "materialId": "voidstone",
      "quantity": 5
    },
    {
      "materialId": "worldtree_plank",
      "quantity": 5
    }
  ],
  "narrative": "Soul bound enchantment. Item returns to you upon death."
}""",
            "output": """{
  "enchantmentId": "soulbound",
  "name": "",
  "applicableTo": [
    "weapon",
    "tool",
    "armor",
    "accessory"
  ],
  "effect": {
    "type": "soulbound",
    "value": 1.0,
    "stackable": false,
    "conflictsWith": []
  },
  "metadata": {
    "narrative": "Soul bound enchantment. Item returns to you upon death.",
    "tags": [
      "universal",
      "soulbound",
      "special"
    ]
  }
}"""
        }
    ],
    "5x2": [
        {
            "input": """{
  "recipeId": "enchanting_sharpness_basic",
  "enchantmentId": "sharpness_1",
  "tier": 1,
  "inputs": [
    {
      "materialId": "fire_crystal",
      "quantity": 4
    },
    {
      "materialId": "granite",
      "quantity": 2
    },
    {
      "materialId": "iron_ingot",
      "quantity": 3
    },
    {
      "materialId": "tin_ore",
      "quantity": 2
    }
  ],
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.1,
    "stackable": false,
    "conflictsWith": [
      "sharpness_2",
      "sharpness_3"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_sharpness_basic",
  "placementMap": {
    "gridType": "square_8x8",
    "vertices": {
      "0,1": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "-1,2": {
        "materialId": "iron_ingot",
        "isKey": false
      },
      "0,4": {
        "materialId": "iron_ingot",
        "isKey": false
      },
      "1,2": {
        "materialId": "iron_ingot",
        "isKey": false
      },
      "2,0": {
        "materialId": "tin_ore",
        "isKey": false
      },
      "-2,0": {
        "materialId": "tin_ore",
        "isKey": false
      },
      "1,0": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "0,-2": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "-1,0": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "-1,-4": {
        "materialId": "granite",
        "isKey": false
      },
      "1,-4": {
        "materialId": "granite",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "square_small",
        "vertices": [
          "0,1",
          "-1,2",
          "0,4",
          "1,2"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "2,0",
          "1,2",
          "0,1"
        ],
        "rotation": 225
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-2,0",
          "0,1",
          "-1,2"
        ],
        "rotation": 135
      },
      {
        "type": "square_small",
        "vertices": [
          "0,1",
          "1,0",
          "0,-2",
          "-1,0"
        ],
        "rotation": 315
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-2",
          "-1,-4",
          "1,-4"
        ],
        "rotation": 0
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_durability_basic",
  "enchantmentId": "unbreaking_1",
  "tier": 1,
  "inputs": [
    {
      "materialId": "beetle_carapace",
      "quantity": 4
    },
    {
      "materialId": "earth_crystal",
      "quantity": 4
    }
  ],
  "applicableTo": [
    "weapon",
    "tool",
    "armor"
  ],
  "effect": {
    "type": "durability_multiplier",
    "value": 0.3,
    "stackable": false,
    "conflictsWith": [
      "unbreaking_2"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_durability_basic",
  "placementMap": {
    "gridType": "square_8x8",
    "vertices": {
      "1,1": {
        "materialId": "earth_crystal",
        "isKey": false
      },
      "1,-1": {
        "materialId": "earth_crystal",
        "isKey": false
      },
      "-1,-1": {
        "materialId": "earth_crystal",
        "isKey": false
      },
      "-1,1": {
        "materialId": "earth_crystal",
        "isKey": false
      },
      "0,3": {
        "materialId": "beetle_carapace",
        "isKey": false
      },
      "0,-3": {
        "materialId": "beetle_carapace",
        "isKey": false
      },
      "3,0": {
        "materialId": "beetle_carapace",
        "isKey": false
      },
      "-3,0": {
        "materialId": "beetle_carapace",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "square_small",
        "vertices": [
          "1,1",
          "1,-1",
          "-1,-1",
          "-1,1"
        ],
        "rotation": 270
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,3",
          "-1,1",
          "1,1"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-3",
          "1,-1",
          "-1,-1"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "3,0",
          "1,1",
          "1,-1"
        ],
        "rotation": 270
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-3,0",
          "-1,-1",
          "-1,1"
        ],
        "rotation": 90
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_sharpness_advanced",
  "enchantmentId": "sharpness_2",
  "tier": 2,
  "inputs": [
    {
      "materialId": "dire_fang",
      "quantity": 3
    },
    {
      "materialId": "frost_essence",
      "quantity": 2
    },
    {
      "materialId": "lightning_shard",
      "quantity": 3
    },
    {
      "materialId": "marble",
      "quantity": 4
    }
  ],
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.2,
    "stackable": false,
    "conflictsWith": [
      "sharpness_1",
      "sharpness_3"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_sharpness_advanced",
  "placementMap": {
    "gridType": "square_10x10",
    "vertices": {
      "0,5": {
        "materialId": "dire_fang",
        "isKey": false
      },
      "-1,2": {
        "materialId": "lightning_shard",
        "isKey": false
      },
      "1,2": {
        "materialId": "lightning_shard",
        "isKey": false
      },
      "0,0": {
        "materialId": "lightning_shard",
        "isKey": false
      },
      "1,1": {
        "materialId": "frost_essence",
        "isKey": false
      },
      "-1,1": {
        "materialId": "frost_essence",
        "isKey": false
      },
      "2,0": {
        "materialId": "dire_fang",
        "isKey": false
      },
      "1,-2": {
        "materialId": "marble",
        "isKey": false
      },
      "-1,-2": {
        "materialId": "marble",
        "isKey": false
      },
      "-2,0": {
        "materialId": "dire_fang",
        "isKey": false
      },
      "-1,-4": {
        "materialId": "marble",
        "isKey": false
      },
      "1,-4": {
        "materialId": "marble",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "0,5",
          "-1,2",
          "1,2"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-1,2",
          "0,0",
          "1,1"
        ],
        "rotation": 45
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "1,2",
          "-1,1",
          "0,0"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "1,1",
          "2,0",
          "1,-2",
          "0,0"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "-1,1",
          "0,0",
          "-1,-2",
          "-2,0"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "-1,-4",
          "-1,-2",
          "1,-2",
          "1,-4"
        ],
        "rotation": 90
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_fire_aspect",
  "enchantmentId": "fire_aspect",
  "tier": 2,
  "inputs": [
    {
      "materialId": "fire_crystal",
      "quantity": 6
    },
    {
      "materialId": "light_gem",
      "quantity": 1
    },
    {
      "materialId": "maple_plank",
      "quantity": 6
    },
    {
      "materialId": "steel_ingot",
      "quantity": 3
    }
  ],
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_over_time",
    "element": "fire",
    "damagePerSecond": 10,
    "duration": 5,
    "stackable": true,
    "conflictsWith": []
  }
}""",
            "output": """{
  "recipeId": "enchanting_fire_aspect",
  "placementMap": {
    "gridType": "square_10x10",
    "vertices": {
      "-3,-3": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "-1,-3": {
        "materialId": "steel_ingot",
        "isKey": false
      },
      "-1,-5": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "-3,-5": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "1,-3": {
        "materialId": "steel_ingot",
        "isKey": false
      },
      "3,-3": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "3,-5": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "1,-5": {
        "materialId": "maple_plank",
        "isKey": false
      },
      "0,-4": {
        "materialId": "steel_ingot",
        "isKey": false
      },
      "0,-1": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "-2,0": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "2,0": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "0,2": {
        "materialId": "light_gem",
        "isKey": false
      },
      "1,1": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "-1,1": {
        "materialId": "fire_crystal",
        "isKey": false
      },
      "0,0": {
        "materialId": "fire_crystal",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "square_small",
        "vertices": [
          "-3,-3",
          "-1,-3",
          "-1,-5",
          "-3,-5"
        ],
        "rotation": 0
      },
      {
        "type": "square_small",
        "vertices": [
          "1,-3",
          "3,-3",
          "3,-5",
          "1,-5"
        ],
        "rotation": 0
      },
      {
        "type": "square_small",
        "vertices": [
          "0,-4",
          "-1,-3",
          "0,-1",
          "1,-3"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "-2,0",
          "-3,-3",
          "-1,-3"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "2,0",
          "1,-3",
          "3,-3"
        ],
        "rotation": 0
      },
      {
        "type": "square_small",
        "vertices": [
          "0,2",
          "1,1",
          "0,-1",
          "-1,1"
        ],
        "rotation": 315
      },
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "-1,-3",
          "0,0",
          "-2,0"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "1,-3",
          "2,0",
          "0,0"
        ],
        "rotation": 180
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_sharpness_master",
  "enchantmentId": "sharpness_3",
  "tier": 3,
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 3
    },
    {
      "materialId": "diamond",
      "quantity": 5
    },
    {
      "materialId": "essence_blood",
      "quantity": 2
    },
    {
      "materialId": "marble",
      "quantity": 1
    },
    {
      "materialId": "phoenix_ash",
      "quantity": 3
    }
  ],
  "applicableTo": [
    "weapon"
  ],
  "effect": {
    "type": "damage_multiplier",
    "value": 0.35,
    "stackable": false,
    "conflictsWith": [
      "sharpness_1",
      "sharpness_2"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_sharpness_master",
  "placementMap": {
    "gridType": "square_12x12",
    "vertices": {
      "0,6": {
        "materialId": "diamond",
        "isKey": false
      },
      "-1,3": {
        "materialId": "diamond",
        "isKey": false
      },
      "1,3": {
        "materialId": "diamond",
        "isKey": false
      },
      "2,1": {
        "materialId": "essence_blood",
        "isKey": false
      },
      "0,2": {
        "materialId": "phoenix_ash",
        "isKey": false
      },
      "-2,1": {
        "materialId": "essence_blood",
        "isKey": false
      },
      "0,-2": {
        "materialId": "marble",
        "isKey": false
      },
      "1,-3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "0,-5": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "-1,-3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "1,-1": {
        "materialId": "phoenix_ash",
        "isKey": false
      },
      "3,-2": {
        "materialId": "diamond",
        "isKey": false
      },
      "-3,-2": {
        "materialId": "diamond",
        "isKey": false
      },
      "-1,-1": {
        "materialId": "phoenix_ash",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "triangle_isosceles_small",
        "vertices": [
          "0,6",
          "-1,3",
          "1,3"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "2,1",
          "1,3",
          "0,2"
        ],
        "rotation": 225
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-2,1",
          "0,2",
          "-1,3"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_equilateral_large",
        "vertices": [
          "0,-2",
          "2,1",
          "-2,1"
        ],
        "rotation": 180
      },
      {
        "type": "square_small",
        "vertices": [
          "0,-2",
          "1,-3",
          "0,-5",
          "-1,-3"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "0,-2",
          "1,-1",
          "3,-2",
          "1,-3"
        ],
        "rotation": 45
      },
      {
        "type": "square_small",
        "vertices": [
          "0,-2",
          "-1,-3",
          "-3,-2",
          "-1,-1"
        ],
        "rotation": 225
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_durability_advanced",
  "enchantmentId": "unbreaking_2",
  "tier": 3,
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 4
    },
    {
      "materialId": "diamond",
      "quantity": 4
    },
    {
      "materialId": "golem_core",
      "quantity": 1
    },
    {
      "materialId": "mithril_ingot",
      "quantity": 8
    },
    {
      "materialId": "spectral_thread",
      "quantity": 8
    }
  ],
  "applicableTo": [
    "weapon",
    "tool",
    "armor"
  ],
  "effect": {
    "type": "durability_multiplier",
    "value": 0.6,
    "stackable": false,
    "conflictsWith": [
      "unbreaking_1"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_durability_advanced",
  "placementMap": {
    "gridType": "square_12x12",
    "vertices": {
      "0,0": {
        "materialId": "golem_core",
        "isKey": false
      },
      "3,3": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "6,0": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "3,-3": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "-3,3": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "0,6": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "-6,0": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "-3,-3": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "0,-6": {
        "materialId": "spectral_thread",
        "isKey": false
      },
      "0,3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "1,5": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "-1,5": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "0,-3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "1,-1": {
        "materialId": "diamond",
        "isKey": false
      },
      "-1,-1": {
        "materialId": "diamond",
        "isKey": false
      },
      "-3,0": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "-5,1": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "-5,-1": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "3,0": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "1,1": {
        "materialId": "diamond",
        "isKey": false
      },
      "-1,-5": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "1,-5": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "-1,1": {
        "materialId": "diamond",
        "isKey": false
      },
      "5,-1": {
        "materialId": "mithril_ingot",
        "isKey": false
      },
      "5,1": {
        "materialId": "mithril_ingot",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "square_large",
        "vertices": [
          "0,0",
          "3,3",
          "6,0",
          "3,-3"
        ],
        "rotation": 45
      },
      {
        "type": "square_large",
        "vertices": [
          "-3,3",
          "0,6",
          "3,3",
          "0,0"
        ],
        "rotation": 45
      },
      {
        "type": "square_large",
        "vertices": [
          "-6,0",
          "-3,3",
          "0,0",
          "-3,-3"
        ],
        "rotation": 45
      },
      {
        "type": "square_large",
        "vertices": [
          "-3,-3",
          "0,0",
          "3,-3",
          "0,-6"
        ],
        "rotation": 45
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,3",
          "1,5",
          "-1,5"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-3",
          "1,-1",
          "-1,-1"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-3,0",
          "-5,1",
          "-5,-1"
        ],
        "rotation": 270
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "3,0",
          "1,1",
          "1,-1"
        ],
        "rotation": 270
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-3",
          "-1,-5",
          "1,-5"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,3",
          "-1,1",
          "1,1"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-3,0",
          "-1,-1",
          "-1,1"
        ],
        "rotation": 90
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "3,0",
          "5,-1",
          "5,1"
        ],
        "rotation": 90
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_fortune_advanced",
  "enchantmentId": "fortune_2",
  "tier": 4,
  "inputs": [
    {
      "materialId": "chaos_matrix",
      "quantity": 3
    },
    {
      "materialId": "diamond",
      "quantity": 9
    },
    {
      "materialId": "genesis_lattice",
      "quantity": 4
    },
    {
      "materialId": "light_gem",
      "quantity": 4
    },
    {
      "materialId": "living_ichor",
      "quantity": 6
    },
    {
      "materialId": "obsidian",
      "quantity": 6
    }
  ],
  "applicableTo": [
    "tool"
  ],
  "effect": {
    "type": "bonus_yield_chance",
    "value": 0.6,
    "stackable": false,
    "conflictsWith": [
      "fortune_1",
      "silk_touch"
    ]
  }
}""",
            "output": """{
  "recipeId": "enchanting_fortune_advanced",
  "placementMap": {
    "gridType": "square_14x14",
    "vertices": {
      "3,-4": {
        "materialId": "diamond",
        "isKey": false
      },
      "0,-7": {
        "materialId": "diamond",
        "isKey": false
      },
      "-3,-4": {
        "materialId": "diamond",
        "isKey": false
      },
      "0,-1": {
        "materialId": "diamond",
        "isKey": false
      },
      "-3,4": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "3,4": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "-4,5": {
        "materialId": "light_gem",
        "isKey": false
      },
      "-3,7": {
        "materialId": "light_gem",
        "isKey": false
      },
      "-2,5": {
        "materialId": "obsidian",
        "isKey": false
      },
      "2,5": {
        "materialId": "obsidian",
        "isKey": false
      },
      "3,7": {
        "materialId": "light_gem",
        "isKey": false
      },
      "4,5": {
        "materialId": "light_gem",
        "isKey": false
      },
      "5,4": {
        "materialId": "diamond",
        "isKey": false
      },
      "4,2": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "-4,2": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "-5,4": {
        "materialId": "diamond",
        "isKey": false
      },
      "-5,3": {
        "materialId": null,
        "isKey": false
      },
      "-5,0": {
        "materialId": null,
        "isKey": false
      },
      "-6,2": {
        "materialId": "obsidian",
        "isKey": false
      },
      "5,3": {
        "materialId": null,
        "isKey": false
      },
      "6,2": {
        "materialId": "obsidian",
        "isKey": false
      },
      "5,0": {
        "materialId": null,
        "isKey": false
      },
      "6,-1": {
        "materialId": "diamond",
        "isKey": false
      },
      "5,-3": {
        "materialId": null,
        "isKey": false
      },
      "4,-1": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "6,-4": {
        "materialId": "obsidian",
        "isKey": false
      },
      "5,-5": {
        "materialId": null,
        "isKey": false
      },
      "-6,-4": {
        "materialId": "obsidian",
        "isKey": false
      },
      "-5,-3": {
        "materialId": null,
        "isKey": false
      },
      "-5,-5": {
        "materialId": null,
        "isKey": false
      },
      "-4,-1": {
        "materialId": "living_ichor",
        "isKey": false
      },
      "-6,-1": {
        "materialId": "diamond",
        "isKey": false
      },
      "0,2": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "1,1": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "-1,1": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "-1,3": {
        "materialId": null,
        "isKey": false
      },
      "0,5": {
        "materialId": "diamond",
        "isKey": false
      },
      "1,3": {
        "materialId": null,
        "isKey": false
      },
      "-1,-3": {
        "materialId": "genesis_lattice",
        "isKey": false
      },
      "1,-3": {
        "materialId": "genesis_lattice",
        "isKey": false
      },
      "1,-5": {
        "materialId": "genesis_lattice",
        "isKey": false
      },
      "-1,-5": {
        "materialId": "genesis_lattice",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "square_large",
        "vertices": [
          "3,-4",
          "0,-7",
          "-3,-4",
          "0,-1"
        ],
        "rotation": 225
      },
      {
        "type": "square_small",
        "vertices": [
          "-3,4",
          "-4,5",
          "-3,7",
          "-2,5"
        ],
        "rotation": 135
      },
      {
        "type": "square_small",
        "vertices": [
          "3,4",
          "2,5",
          "3,7",
          "4,5"
        ],
        "rotation": 135
      },
      {
        "type": "square_small",
        "vertices": [
          "4,5",
          "5,4",
          "4,2",
          "3,4"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "-4,5",
          "-3,4",
          "-4,2",
          "-5,4"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "-5,3",
          "-4,2",
          "-5,0",
          "-6,2"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "5,3",
          "6,2",
          "5,0",
          "4,2"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "5,0",
          "6,-1",
          "5,-3",
          "4,-1"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "6,-4",
          "5,-5",
          "3,-4",
          "5,-3"
        ],
        "rotation": 225
      },
      {
        "type": "square_small",
        "vertices": [
          "-6,-4",
          "-5,-3",
          "-3,-4",
          "-5,-5"
        ],
        "rotation": 45
      },
      {
        "type": "square_small",
        "vertices": [
          "-5,0",
          "-4,-1",
          "-5,-3",
          "-6,-1"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "0,2",
          "1,1",
          "0,-1",
          "-1,1"
        ],
        "rotation": 315
      },
      {
        "type": "square_small",
        "vertices": [
          "0,2",
          "-1,3",
          "0,5",
          "1,3"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-1,3",
          "-2,5",
          "-3,4"
        ],
        "rotation": 225
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "1,3",
          "3,4",
          "2,5"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-1",
          "-1,-3",
          "1,-3"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "0,-7",
          "1,-5",
          "-1,-5"
        ],
        "rotation": 180
      },
      {
        "type": "square_small",
        "vertices": [
          "1,-5",
          "-1,-5",
          "-1,-3",
          "1,-3"
        ],
        "rotation": 180
      }
    ]
  }
}"""
        },
        {
            "input": """{
  "recipeId": "enchanting_soulbound",
  "enchantmentId": "soulbound",
  "tier": 4,
  "inputs": [
    {
      "materialId": "adamantine_ingot",
      "quantity": 4
    },
    {
      "materialId": "chaos_matrix",
      "quantity": 4
    },
    {
      "materialId": "eternity_stone",
      "quantity": 4
    },
    {
      "materialId": "obsidian",
      "quantity": 4
    },
    {
      "materialId": "primordial_crystal",
      "quantity": 3
    },
    {
      "materialId": "voidstone",
      "quantity": 5
    },
    {
      "materialId": "worldtree_plank",
      "quantity": 5
    }
  ],
  "applicableTo": [
    "weapon",
    "tool",
    "armor",
    "accessory"
  ],
  "effect": {
    "type": "soulbound",
    "value": 1.0,
    "stackable": false,
    "conflictsWith": []
  }
}""",
            "output": """{
  "recipeId": "enchanting_soulbound",
  "placementMap": {
    "gridType": "square_14x14",
    "vertices": {
      "0,-2": {
        "materialId": "worldtree_plank",
        "isKey": false
      },
      "-1,-7": {
        "materialId": "worldtree_plank",
        "isKey": false
      },
      "1,-7": {
        "materialId": "worldtree_plank",
        "isKey": false
      },
      "3,-6": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "4,-5": {
        "materialId": "obsidian",
        "isKey": false
      },
      "5,-3": {
        "materialId": "obsidian",
        "isKey": false
      },
      "5,-1": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "-5,-1": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "-5,-3": {
        "materialId": "obsidian",
        "isKey": false
      },
      "-4,-5": {
        "materialId": "obsidian",
        "isKey": false
      },
      "-3,-6": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "-3,1": {
        "materialId": "worldtree_plank",
        "isKey": false
      },
      "0,4": {
        "materialId": "primordial_crystal",
        "isKey": false
      },
      "3,1": {
        "materialId": "worldtree_plank",
        "isKey": false
      },
      "-5,1": {
        "materialId": "voidstone",
        "isKey": false
      },
      "-3,-1": {
        "materialId": "primordial_crystal",
        "isKey": false
      },
      "3,-1": {
        "materialId": "primordial_crystal",
        "isKey": false
      },
      "5,1": {
        "materialId": "voidstone",
        "isKey": false
      },
      "-4,3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "-6,3": {
        "materialId": "voidstone",
        "isKey": false
      },
      "6,3": {
        "materialId": "voidstone",
        "isKey": false
      },
      "4,3": {
        "materialId": "adamantine_ingot",
        "isKey": false
      },
      "0,6": {
        "materialId": "voidstone",
        "isKey": false
      },
      "-1,7": {
        "materialId": "eternity_stone",
        "isKey": false
      },
      "1,7": {
        "materialId": "eternity_stone",
        "isKey": false
      },
      "7,5": {
        "materialId": "chaos_matrix",
        "isKey": false
      },
      "5,5": {
        "materialId": "eternity_stone",
        "isKey": false
      },
      "-5,5": {
        "materialId": "eternity_stone",
        "isKey": false
      },
      "-7,5": {
        "materialId": "chaos_matrix",
        "isKey": false
      }
    },
    "shapes": [
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "0,-2",
          "-1,-7",
          "1,-7"
        ],
        "rotation": 0
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "0,-2",
          "3,-6",
          "4,-5"
        ],
        "rotation": 45
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "0,-2",
          "5,-3",
          "5,-1"
        ],
        "rotation": 90
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "0,-2",
          "-5,-1",
          "-5,-3"
        ],
        "rotation": 270
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "0,-2",
          "-4,-5",
          "-3,-6"
        ],
        "rotation": 315
      },
      {
        "type": "square_large",
        "vertices": [
          "-3,1",
          "0,4",
          "3,1",
          "0,-2"
        ],
        "rotation": 45
      },
      {
        "type": "square_small",
        "vertices": [
          "-5,-1",
          "-5,1",
          "-3,1",
          "-3,-1"
        ],
        "rotation": 90
      },
      {
        "type": "square_small",
        "vertices": [
          "3,-1",
          "3,1",
          "5,1",
          "5,-1"
        ],
        "rotation": 90
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-5,1",
          "-4,3",
          "-6,3"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "5,1",
          "6,3",
          "4,3"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "-4,3",
          "0,6",
          "-1,7"
        ],
        "rotation": 135
      },
      {
        "type": "triangle_isosceles_large",
        "vertices": [
          "4,3",
          "1,7",
          "0,6"
        ],
        "rotation": 225
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "6,3",
          "7,5",
          "5,5"
        ],
        "rotation": 180
      },
      {
        "type": "triangle_equilateral_small",
        "vertices": [
          "-6,3",
          "-5,5",
          "-7,5"
        ],
        "rotation": 180
      }
    ]
  }
}"""
        }
    ],
    "6": [
        {
            "input": """{
  "chunkType": "peaceful_forest",
  "chunkCategory": "peaceful",
  "chunkTheme": "forest",
  "enemySpawns": {
    "wolf_grey": {
      "density": "very_low",
      "tier": 1
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Common grey wolf that roams grasslands and forests. More curious than aggressive, but will defend territory if threatened.",
    "tags": [
      "wolf",
      "common",
      "passive",
      "starter"
    ]
  },
  "enemyId": "wolf_grey",
  "name": "Grey Wolf",
  "tier": 1,
  "category": "beast",
  "behavior": "passive_patrol",
  "stats": {
    "health": 80,
    "damage": [
      8,
      12
    ],
    "defense": 5,
    "speed": 1.2,
    "aggroRange": 5,
    "attackSpeed": 1.0
  },
  "drops": [
    {
      "materialId": "wolf_pelt",
      "quantity": [
        2,
        4
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "dire_fang",
      "quantity": [
        1,
        1
      ],
      "chance": "low"
    }
  ],
  "aiPattern": {
    "defaultState": "wander",
    "aggroOnDamage": true,
    "aggroOnProximity": false,
    "fleeAtHealth": 0.2,
    "callForHelpRadius": 8
  }
}"""
        },
        {
            "input": """{
  "chunkType": "peaceful_quarry",
  "chunkCategory": "peaceful",
  "chunkTheme": "quarry",
  "enemySpawns": {
    "slime_green": {
      "density": "very_low",
      "tier": 1
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Small green slime that oozes slowly across terrain. Mostly harmless unless you step on it.",
    "tags": [
      "slime",
      "common",
      "passive",
      "starter"
    ]
  },
  "enemyId": "slime_green",
  "name": "Green Slime",
  "tier": 1,
  "category": "ooze",
  "behavior": "stationary",
  "stats": {
    "health": 50,
    "damage": [
      5,
      8
    ],
    "defense": 2,
    "speed": 0.5,
    "aggroRange": 3,
    "attackSpeed": 0.8
  },
  "drops": [
    {
      "materialId": "slime_gel",
      "quantity": [
        3,
        6
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "water_crystal",
      "quantity": [
        1,
        1
      ],
      "chance": "rare"
    }
  ],
  "aiPattern": {
    "defaultState": "idle",
    "aggroOnDamage": true,
    "aggroOnProximity": false,
    "fleeAtHealth": 0,
    "callForHelpRadius": 0
  }
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_forest",
  "chunkCategory": "dangerous",
  "chunkTheme": "forest",
  "enemySpawns": {
    "wolf_dire": {
      "density": "moderate",
      "tier": 2
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Larger, more aggressive wolf. Alpha predator that hunts in coordinated packs.",
    "tags": [
      "wolf",
      "uncommon",
      "aggressive",
      "mid-game"
    ]
  },
  "enemyId": "wolf_dire",
  "name": "Dire Wolf",
  "tier": 2,
  "category": "beast",
  "behavior": "aggressive_pack",
  "stats": {
    "health": 200,
    "damage": [
      18,
      28
    ],
    "defense": 12,
    "speed": 1.4,
    "aggroRange": 8,
    "attackSpeed": 1.2
  },
  "drops": [
    {
      "materialId": "wolf_pelt",
      "quantity": [
        3,
        6
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "dire_fang",
      "quantity": [
        2,
        4
      ],
      "chance": "high"
    },
    {
      "materialId": "living_ichor",
      "quantity": [
        1,
        2
      ],
      "chance": "moderate"
    }
  ],
  "aiPattern": {
    "defaultState": "patrol",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 12,
    "packCoordination": true
  }
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_quarry",
  "chunkCategory": "dangerous",
  "chunkTheme": "quarry",
  "enemySpawns": {
    "slime_acid": {
      "density": "moderate",
      "tier": 2
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Corrosive slime that dissolves anything it touches. Highly aggressive and surprisingly fast.",
    "tags": [
      "slime",
      "uncommon",
      "aggressive",
      "mid-game"
    ]
  },
  "enemyId": "slime_acid",
  "name": "Acid Slime",
  "tier": 2,
  "category": "ooze",
  "behavior": "aggressive_swarm",
  "stats": {
    "health": 120,
    "damage": [
      15,
      22
    ],
    "defense": 8,
    "speed": 0.9,
    "aggroRange": 6,
    "attackSpeed": 1.0
  },
  "drops": [
    {
      "materialId": "slime_gel",
      "quantity": [
        5,
        10
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "living_ichor",
      "quantity": [
        2,
        3
      ],
      "chance": "high"
    },
    {
      "materialId": "shadow_core",
      "quantity": [
        1,
        1
      ],
      "chance": "low"
    }
  ],
  "aiPattern": {
    "defaultState": "patrol",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 10,
    "specialAbilities": [
      "acid_damage_over_time"
    ]
  }
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_cave",
  "chunkCategory": "dangerous",
  "chunkTheme": "cave",
  "enemySpawns": {
    "golem_stone": {
      "density": "very_low",
      "tier": 3
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Animated stone construct that guards ancient places. Slow but nearly indestructible.",
    "tags": [
      "golem",
      "rare",
      "boss",
      "construct"
    ]
  },
  "enemyId": "golem_stone",
  "name": "Stone Golem",
  "tier": 3,
  "category": "construct",
  "behavior": "boss_encounter",
  "stats": {
    "health": 800,
    "damage": [
      50,
      80
    ],
    "defense": 40,
    "speed": 0.5,
    "aggroRange": 10,
    "attackSpeed": 0.6
  },
  "drops": [
    {
      "materialId": "golem_core",
      "quantity": [
        2,
        4
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "granite",
      "quantity": [
        10,
        15
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "earth_crystal",
      "quantity": [
        5,
        8
      ],
      "chance": "high"
    },
    {
      "materialId": "diamond",
      "quantity": [
        1,
        2
      ],
      "chance": "moderate"
    }
  ],
  "aiPattern": {
    "defaultState": "guard",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 0,
    "specialAbilities": [
      "ground_slam",
      "stone_armor"
    ]
  }
}"""
        },
        {
            "input": """{
  "chunkType": "rare_forest",
  "chunkCategory": "rare",
  "chunkTheme": "forest",
  "enemySpawns": {
    "wolf_elder": {
      "density": "low",
      "tier": 3
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Ancient wolf wreathed in shadow. Pack leader that has survived countless battles.",
    "tags": [
      "wolf",
      "rare",
      "boss",
      "end-game"
    ]
  },
  "enemyId": "wolf_elder",
  "name": "Elder Wolf",
  "tier": 3,
  "category": "beast",
  "behavior": "boss_encounter",
  "stats": {
    "health": 600,
    "damage": [
      45,
      70
    ],
    "defense": 25,
    "speed": 1.6,
    "aggroRange": 12,
    "attackSpeed": 1.5
  },
  "drops": [
    {
      "materialId": "wolf_pelt",
      "quantity": [
        8,
        12
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "dire_fang",
      "quantity": [
        6,
        10
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "essence_blood",
      "quantity": [
        3,
        5
      ],
      "chance": "high"
    },
    {
      "materialId": "spectral_thread",
      "quantity": [
        2,
        3
      ],
      "chance": "moderate"
    }
  ],
  "aiPattern": {
    "defaultState": "patrol",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 20,
    "packCoordination": true,
    "specialAbilities": [
      "howl_buff",
      "leap_attack"
    ]
  }
}"""
        },
        {
            "input": """{
  "chunkType": "rare_quarry",
  "chunkCategory": "rare",
  "chunkTheme": "quarry",
  "enemySpawns": {
    "golem_crystal": {
      "density": "very_low",
      "tier": 4
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Crystalline golem pulsing with magical energy. Rare guardian of legendary deposits.",
    "tags": [
      "golem",
      "epic",
      "boss",
      "construct"
    ]
  },
  "enemyId": "golem_crystal",
  "name": "Crystal Golem",
  "tier": 4,
  "category": "construct",
  "behavior": "boss_encounter",
  "stats": {
    "health": 1000,
    "damage": [
      80,
      120
    ],
    "defense": 45,
    "speed": 0.7,
    "aggroRange": 12,
    "attackSpeed": 0.8
  },
  "drops": [
    {
      "materialId": "golem_core",
      "quantity": [
        3,
        5
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "crystal_quartz",
      "quantity": [
        10,
        15
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "diamond",
      "quantity": [
        3,
        5
      ],
      "chance": "high"
    },
    {
      "materialId": "primordial_crystal",
      "quantity": [
        1,
        2
      ],
      "chance": "low"
    }
  ],
  "aiPattern": {
    "defaultState": "guard",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 0,
    "specialAbilities": [
      "crystal_beam",
      "refraction_shield",
      "summon_shards"
    ]
  }
}"""
        },
        {
            "input": """{
  "chunkType": "rare_cave",
  "chunkCategory": "rare",
  "chunkTheme": "cave",
  "enemySpawns": {
    "void_wraith": {
      "density": "moderate",
      "tier": 4
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Spectral entity that phases between dimensions. Attacks pass through it unpredictably.",
    "tags": [
      "wraith",
      "rare",
      "phase",
      "end-game"
    ]
  },
  "enemyId": "void_wraith",
  "name": "Void Wraith",
  "tier": 4,
  "category": "undead",
  "behavior": "aggressive_phase",
  "stats": {
    "health": 400,
    "damage": [
      60,
      90
    ],
    "defense": 15,
    "speed": 1.5,
    "aggroRange": 15,
    "attackSpeed": 1.3
  },
  "drops": [
    {
      "materialId": "spectral_thread",
      "quantity": [
        5,
        10
      ],
      "chance": "guaranteed"
    },
    {
      "materialId": "void_essence",
      "quantity": [
        3,
        5
      ],
      "chance": "high"
    },
    {
      "materialId": "shadow_core",
      "quantity": [
        4,
        6
      ],
      "chance": "high"
    },
    {
      "materialId": "essence_blood",
      "quantity": [
        3,
        4
      ],
      "chance": "moderate"
    }
  ],
  "aiPattern": {
    "defaultState": "patrol",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0,
    "callForHelpRadius": 0,
    "specialAbilities": [
      "phase_shift",
      "life_drain",
      "teleport"
    ]
  }
}"""
        }
    ],
    "7": [
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Copper Vein",
  "sourceTier": 1,
  "materialTier": 1,
  "materialCategory": "metal",
  "allSources": [
    "copper_vein"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "A soft, reddish metal found in shallow veins near the surface. Easy to work with basic tools but lacks the durability needed for serious combat. The foundation of all smithing - every blacksmith's first lesson.",
    "tags": [
      "basic",
      "metal",
      "starter"
    ]
  },
  "materialId": "copper_ore",
  "name": "Copper Ore",
  "tier": 1,
  "rarity": "common",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Iron Deposit",
  "sourceTier": 1,
  "materialTier": 1,
  "materialCategory": "metal",
  "allSources": [
    "iron_deposit"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Sturdy grey metal from common deposits throughout the land. The workhorse of civilization - reliable, abundant, and strong enough for most purposes.",
    "tags": [
      "basic",
      "metal",
      "standard"
    ]
  },
  "materialId": "iron_ore",
  "name": "Iron Ore",
  "tier": 1,
  "rarity": "common",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Steel Node",
  "sourceTier": 2,
  "materialTier": 2,
  "materialCategory": "metal",
  "allSources": [
    "steel_node"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Harder and more durable than pure iron. The secret of its strength lies in its carbon-rich structure. A true warrior's metal.",
    "tags": [
      "basic",
      "metal",
      "advanced"
    ]
  },
  "materialId": "steel_ore",
  "name": "Steel Ore",
  "tier": 2,
  "rarity": "uncommon",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Mithril Cache",
  "sourceTier": 2,
  "materialTier": 2,
  "materialCategory": "metal",
  "allSources": [
    "mithril_cache"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Legendary silver-white metal that seems to drink in moonlight and starshine. Impossibly light yet incredibly strong.",
    "tags": [
      "basic",
      "metal",
      "legendary"
    ]
  },
  "materialId": "mithril_ore",
  "name": "Mithril Ore",
  "tier": 2,
  "rarity": "rare",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Adamantine Lode",
  "sourceTier": 3,
  "materialTier": 3,
  "materialCategory": "metal",
  "allSources": [
    "adamantine_lode"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Dark, impossibly hard metal that absorbs light. Found only in the deepest caverns where the world's bones are exposed.",
    "tags": [
      "basic",
      "metal",
      "rare"
    ]
  },
  "materialId": "adamantine_ore",
  "name": "Adamantine Ore",
  "tier": 3,
  "rarity": "rare",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "hostile",
  "sourceName": "Titan Beetle",
  "sourceTier": 4,
  "materialTier": 3,
  "materialCategory": "metal",
  "allSources": [
    "beetle_titan"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Nearly indestructible metal that can withstand forces that would shatter lesser materials. Each ingot represents months of careful refinement.",
    "tags": [
      "refined",
      "metal",
      "rare"
    ]
  },
  "materialId": "adamantine_ingot",
  "name": "Adamantine Ingot",
  "tier": 3,
  "rarity": "rare",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "node",
  "sourceName": "Etherion Nexus",
  "sourceTier": 4,
  "materialTier": 4,
  "materialCategory": "metal",
  "allSources": [
    "etherion_nexus"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Metal that simultaneously exists in multiple states. Scholars argue whether it's matter or energy, present or future. It is all of these and none.",
    "tags": [
      "basic",
      "metal",
      "mythical",
      "temporal"
    ]
  },
  "materialId": "etherion_ore",
  "name": "Etherion Ore",
  "tier": 4,
  "rarity": "legendary",
  "category": "metal"
}"""
        },
        {
            "input": """{
  "sourceType": "hostile",
  "sourceName": "Primordial Entity",
  "sourceTier": 4,
  "materialTier": 4,
  "materialCategory": "metal",
  "allSources": [
    "entity_primordial"
  ]
}""",
            "output": """{
  "metadata": {
    "narrative": "Reality-bending metal that has transcended conventional physics. Durability frozen in time, effects can occur before cause.",
    "tags": [
      "refined",
      "metal",
      "mythical",
      "temporal"
    ]
  },
  "materialId": "etherion_ingot",
  "name": "Etherion Ingot",
  "tier": 4,
  "rarity": "legendary",
  "category": "metal"
}"""
        }
    ],
    "8": [
        {
            "input": """{
  "chunkType": "peaceful_forest",
  "chunkCategory": "peaceful",
  "chunkTheme": "forest",
  "resourceDensity": {
    "oak_tree": {
      "density": "very_high",
      "tierBias": "low"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Ancient oak standing patient as centuries pass. The trees here grow thick and safe, perfect for beginners learning the woodcutter's craft.",
    "tags": [
      "tree",
      "wood",
      "starter"
    ]
  },
  "resourceId": "oak_tree",
  "name": "Oak Tree",
  "category": "tree",
  "tier": 1,
  "requiredTool": "axe",
  "baseHealth": 100,
  "drops": [
    {
      "materialId": "oak_log",
      "quantity": "many",
      "chance": "guaranteed"
    }
  ],
  "respawnTime": "normal"
}"""
        },
        {
            "input": """{
  "chunkType": "peaceful_forest",
  "chunkCategory": "peaceful",
  "chunkTheme": "forest",
  "resourceDensity": {
    "pine_tree": {
      "density": "very_high",
      "tierBias": "low"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Tall conifer reaching toward the sky. Flexible wood perfect for bows and lightweight construction.",
    "tags": [
      "tree",
      "wood",
      "flexible"
    ]
  },
  "resourceId": "pine_tree",
  "name": "Pine Tree",
  "category": "tree",
  "tier": 1,
  "requiredTool": "axe",
  "baseHealth": 100,
  "drops": [
    {
      "materialId": "pine_log",
      "quantity": "many",
      "chance": "guaranteed"
    }
  ],
  "respawnTime": "normal"
}"""
        },
        {
            "input": """{
  "chunkType": "peaceful_forest",
  "chunkCategory": "peaceful",
  "chunkTheme": "forest",
  "resourceDensity": {
    "birch_tree": {
      "density": "moderate",
      "tierBias": "mid"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Elegant tree with papery white bark. Fine grain makes it ideal for detailed carving work.",
    "tags": [
      "tree",
      "wood",
      "fine"
    ]
  },
  "resourceId": "birch_tree",
  "name": "Birch Tree",
  "category": "tree",
  "tier": 2,
  "requiredTool": "axe",
  "baseHealth": 200,
  "drops": [
    {
      "materialId": "birch_log",
      "quantity": "several",
      "chance": "guaranteed"
    }
  ],
  "respawnTime": "slow"
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_forest",
  "chunkCategory": "dangerous",
  "chunkTheme": "forest",
  "resourceDensity": {
    "birch_tree": {
      "density": "high",
      "tierBias": "mid"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Elegant tree with papery white bark. Fine grain makes it ideal for detailed carving work.",
    "tags": [
      "tree",
      "wood",
      "fine"
    ]
  },
  "resourceId": "birch_tree",
  "name": "Birch Tree",
  "category": "tree",
  "tier": 2,
  "requiredTool": "axe",
  "baseHealth": 200,
  "drops": [
    {
      "materialId": "birch_log",
      "quantity": "several",
      "chance": "guaranteed"
    }
  ],
  "respawnTime": "slow"
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_forest",
  "chunkCategory": "dangerous",
  "chunkTheme": "forest",
  "resourceDensity": {
    "ironwood_tree": {
      "density": "low",
      "tierBias": "high"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Rare tree whose wood rivals soft metals in hardness. Almost metallic ring when struck.",
    "tags": [
      "tree",
      "wood",
      "rare",
      "metallic"
    ]
  },
  "resourceId": "ironwood_tree",
  "name": "Ironwood Tree",
  "category": "tree",
  "tier": 3,
  "requiredTool": "axe",
  "baseHealth": 400,
  "drops": [
    {
      "materialId": "ironwood_log",
      "quantity": "few",
      "chance": "high"
    }
  ],
  "respawnTime": "very_slow"
}"""
        },
        {
            "input": """{
  "chunkType": "dangerous_cave",
  "chunkCategory": "dangerous",
  "chunkTheme": "cave",
  "resourceDensity": {
    "voidstone_shard": {
      "density": "low",
      "tierBias": "high"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Pitch-black stone that pulls light into itself. Radiates subtle wrongness.",
    "tags": [
      "stone",
      "void",
      "rare"
    ]
  },
  "resourceId": "voidstone_shard",
  "name": "Voidstone Shard",
  "category": "stone",
  "tier": 3,
  "requiredTool": "pickaxe",
  "baseHealth": 400,
  "drops": [
    {
      "materialId": "voidstone",
      "quantity": "few",
      "chance": "moderate"
    },
    {
      "materialId": "void_essence",
      "quantity": "few",
      "chance": "low"
    }
  ],
  "respawnTime": null
}"""
        },
        {
            "input": """{
  "chunkType": "rare_forest",
  "chunkCategory": "rare",
  "chunkTheme": "forest",
  "resourceDensity": {
    "worldtree_sapling": {
      "density": "very_low",
      "tierBias": "legendary"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Legendary tree connected to the World Tree's root network. The wood hums with accumulated magical essence.",
    "tags": [
      "tree",
      "wood",
      "legendary",
      "living"
    ]
  },
  "resourceId": "worldtree_sapling",
  "name": "Worldtree Sapling",
  "category": "tree",
  "tier": 4,
  "requiredTool": "axe",
  "baseHealth": 800,
  "drops": [
    {
      "materialId": "worldtree_log",
      "quantity": "few",
      "chance": "low"
    }
  ],
  "respawnTime": null
}"""
        },
        {
            "input": """{
  "chunkType": "rare_quarry",
  "chunkCategory": "rare",
  "chunkTheme": "quarry",
  "resourceDensity": {
    "primordial_formation": {
      "density": "very_low",
      "tierBias": "legendary"
    }
  }
}""",
            "output": """{
  "metadata": {
    "narrative": "Crystal suspended in perpetual crystallization. Neither solid nor energy, exists in quantum superposition.",
    "tags": [
      "stone",
      "mythical",
      "quantum"
    ]
  },
  "resourceId": "primordial_formation",
  "name": "Primordial Formation",
  "category": "stone",
  "tier": 4,
  "requiredTool": "pickaxe",
  "baseHealth": 800,
  "drops": [
    {
      "materialId": "primordial_crystal",
      "quantity": "few",
      "chance": "improbable"
    }
  ],
  "respawnTime": null
}"""
        }
    ],
    "10": [
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "damage_boost",
    "gathering",
    "basic"
  ]
}""",
            "output": """{
  "skillId": "miners_fury",
  "name": "Miner's Fury",
  "tier": 1,
  "rarity": "common",
  "categories": [
    "gathering",
    "mining"
  ],
  "description": "Channel raw strength into your pickaxe, doubling mining damage for a sustained period.",
  "narrative": "The mountain yields to those who show it proper respect. Or, failing that, overwhelming force.",
  "tags": [
    "damage_boost",
    "gathering",
    "basic"
  ],
  "effect": {
    "type": "empower",
    "category": "mining",
    "magnitude": "major",
    "target": "self",
    "duration": "moderate",
    "additionalEffects": []
  },
  "cost": {
    "mana": "moderate",
    "cooldown": "moderate"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "titans_excavation",
    "requirement": "Reach level 10 and mine 1000 ore nodes"
  },
  "requirements": {
    "characterLevel": 1,
    "stats": {},
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "speed_boost",
    "gathering",
    "basic"
  ]
}""",
            "output": """{
  "skillId": "lumberjacks_rhythm",
  "name": "Lumberjack's Rhythm",
  "tier": 1,
  "rarity": "common",
  "categories": [
    "gathering",
    "forestry"
  ],
  "description": "Fall into a steady rhythm, chopping wood much faster than normal.",
  "narrative": "Listen to the forest. Find the heartbeat. Match your swing to the ancient pulse.",
  "tags": [
    "speed_boost",
    "gathering",
    "basic"
  ],
  "effect": {
    "type": "quicken",
    "category": "forestry",
    "magnitude": "moderate",
    "target": "self",
    "duration": "moderate",
    "additionalEffects": []
  },
  "cost": {
    "mana": "moderate",
    "cooldown": "moderate"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "natures_tempo",
    "requirement": "Reach level 10 and harvest 500 trees"
  },
  "requirements": {
    "characterLevel": 1,
    "stats": {},
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "critical",
    "precision",
    "multi_purpose"
  ]
}""",
            "output": """{
  "skillId": "keen_eye",
  "name": "Keen Eye",
  "tier": 2,
  "rarity": "rare",
  "categories": [
    "gathering",
    "combat"
  ],
  "description": "Significantly increase critical hit chance for all actions.",
  "narrative": "See the weaknesses others miss. Strike where it matters most.",
  "tags": [
    "critical",
    "precision",
    "multi_purpose"
  ],
  "effect": {
    "type": "pierce",
    "category": "damage",
    "magnitude": "major",
    "target": "self",
    "duration": "moderate",
    "additionalEffects": []
  },
  "cost": {
    "mana": "high",
    "cooldown": "moderate"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "eagle_vision",
    "requirement": "Reach level 10 and land 500 critical hits"
  },
  "requirements": {
    "characterLevel": 8,
    "stats": {
      "LCK": 10,
      "AGI": 10
    },
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "crafting",
    "alchemy",
    "quality"
  ]
}""",
            "output": """{
  "skillId": "alchemists_insight",
  "name": "Alchemist's Insight",
  "tier": 2,
  "rarity": "uncommon",
  "categories": [
    "crafting",
    "alchemy"
  ],
  "description": "Gain extra time for your alchemy mini-game and increase potion quality.",
  "narrative": "The brew reveals its secrets to those patient enough to watch. And lucky enough to not explode.",
  "tags": [
    "crafting",
    "alchemy",
    "quality"
  ],
  "effect": {
    "type": "quicken",
    "category": "alchemy",
    "magnitude": "moderate",
    "target": "self",
    "duration": "instant",
    "additionalEffects": [
      {
        "type": "empower",
        "category": "alchemy",
        "magnitude": "minor",
        "target": "self",
        "duration": "instant"
      }
    ]
  },
  "cost": {
    "mana": "moderate",
    "cooldown": "moderate"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "master_alchemist",
    "requirement": "Reach level 10 and brew 150 potions"
  },
  "requirements": {
    "characterLevel": 6,
    "stats": {
      "INT": 8
    },
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "aoe",
    "gathering",
    "efficiency"
  ]
}""",
            "output": """{
  "skillId": "chain_harvest",
  "name": "Chain Harvest",
  "tier": 3,
  "rarity": "epic",
  "categories": [
    "gathering"
  ],
  "description": "Gather from multiple resource nodes in a small area simultaneously.",
  "narrative": "Why harvest one at a time when you can harvest all of them?",
  "tags": [
    "aoe",
    "gathering",
    "efficiency"
  ],
  "effect": {
    "type": "devastate",
    "category": "mining",
    "magnitude": "major",
    "target": "area",
    "duration": "instant",
    "additionalEffects": []
  },
  "cost": {
    "mana": "extreme",
    "cooldown": "long"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": null,
    "requirement": "Reach level 10 - LLM generates evolution"
  },
  "requirements": {
    "characterLevel": 15,
    "stats": {
      "STR": 20
    },
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "aoe",
    "combat",
    "damage"
  ]
}""",
            "output": """{
  "skillId": "whirlwind_strike",
  "name": "Whirlwind Strike",
  "tier": 3,
  "rarity": "epic",
  "categories": [
    "combat"
  ],
  "description": "Attack all enemies in a wide radius around you.",
  "narrative": "Spin. Strike. Repeat. Simple tactics are often the deadliest.",
  "tags": [
    "aoe",
    "combat",
    "damage"
  ],
  "effect": {
    "type": "devastate",
    "category": "damage",
    "magnitude": "moderate",
    "target": "area",
    "duration": "instant",
    "additionalEffects": []
  },
  "cost": {
    "mana": "extreme",
    "cooldown": "long"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": null,
    "requirement": "Reach level 10 - LLM generates evolution"
  },
  "requirements": {
    "characterLevel": 16,
    "stats": {
      "STR": 20,
      "AGI": 15
    },
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "defense",
    "damage_reduction",
    "combat"
  ]
}""",
            "output": """{
  "skillId": "battle_stance",
  "name": "Battle Stance",
  "tier": 1,
  "rarity": "uncommon",
  "categories": [
    "combat",
    "defense"
  ],
  "description": "Brace yourself against incoming attacks, reducing damage taken significantly.",
  "narrative": "Plant your feet. Lower your center. Become the immovable object.",
  "tags": [
    "defense",
    "damage_reduction",
    "combat"
  ],
  "effect": {
    "type": "fortify",
    "category": "defense",
    "magnitude": "major",
    "target": "self",
    "duration": "long",
    "additionalEffects": []
  },
  "cost": {
    "mana": "moderate",
    "cooldown": "long"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "iron_fortress",
    "requirement": "Reach level 10 and block 5000 damage"
  },
  "requirements": {
    "characterLevel": 3,
    "stats": {
      "DEF": 5
    },
    "titles": []
  }
}"""
        },
        {
            "input": """{
  "requiredLevel": 1,
  "requiredSkills": [],
  "discipline": "",
  "tags": [
    "damage",
    "single_hit",
    "combat"
  ]
}""",
            "output": """{
  "skillId": "combat_strike",
  "name": "Power Strike",
  "tier": 1,
  "rarity": "common",
  "categories": [
    "combat"
  ],
  "description": "Your next attack hits with devastating force, dealing massive damage.",
  "narrative": "Sometimes subtlety fails. Sometimes you just need to hit something really, really hard.",
  "tags": [
    "damage",
    "single_hit",
    "combat"
  ],
  "effect": {
    "type": "empower",
    "category": "damage",
    "magnitude": "extreme",
    "target": "enemy",
    "duration": "instant",
    "additionalEffects": []
  },
  "cost": {
    "mana": "high",
    "cooldown": "short"
  },
  "evolution": {
    "canEvolve": true,
    "nextSkillId": "decimating_blow",
    "requirement": "Reach level 10 and deal 10000 damage"
  },
  "requirements": {
    "characterLevel": 1,
    "stats": {},
    "titles": []
  }
}"""
        }
    ],
    "11": [
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "novice_miner",
  "name": "Novice Miner",
  "titleType": "gathering",
  "difficultyTier": "novice",
  "description": "Your first steps into the depths. Every mine begins with a single swing.",
  "bonuses": {
    "miningDamage": 0.1,
    "miningSpeed": 0.0,
    "rareOreChance": 0.0
  },
  "prerequisites": {
    "activities": {
      "oresMined": 100
    },
    "requiredTitles": [],
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone",
  "isHidden": false,
  "narrative": "The stone remembers your first strike. Keep swinging."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "novice_lumberjack",
  "name": "Novice Lumberjack",
  "titleType": "gathering",
  "difficultyTier": "novice",
  "description": "The forest acknowledges your presence. Trees fall before you.",
  "bonuses": {
    "forestryDamage": 0.1,
    "forestrySpeed": 0.0,
    "rareWoodChance": 0.0
  },
  "prerequisites": {
    "activities": {
      "treesChopped": 100
    },
    "requiredTitles": [],
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone",
  "isHidden": false,
  "narrative": "Every great lumberjack started by felling their hundredth tree."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "novice_smith",
  "name": "Novice Smith",
  "titleType": "crafting",
  "difficultyTier": "novice",
  "description": "The forge accepts you. Your hammer rings with purpose.",
  "bonuses": {
    "smithingTime": 0.1,
    "smithingQuality": 0.0,
    "firstTryBonus": 0.0
  },
  "prerequisites": {
    "activities": {
      "itemsSmithed": 50
    },
    "requiredTitles": [],
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone",
  "isHidden": false,
  "narrative": "Heat, hammer, shape. The trinity of the smith begins with you."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "novice_warrior",
  "name": "Novice Warrior",
  "titleType": "combat",
  "difficultyTier": "novice",
  "description": "First blood has been drawn. You've tasted battle and survived.",
  "bonuses": {
    "meleeDamage": 0.1,
    "criticalChance": 0.0,
    "attackSpeed": 0.0
  },
  "prerequisites": {
    "activities": {
      "enemiesDefeated": 50
    },
    "requiredTitles": [],
    "characterLevel": 0
  },
  "acquisitionMethod": "guaranteed_milestone",
  "isHidden": false,
  "narrative": "Fifty foes have fallen. You're no longer prey."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "apprentice_flame_miner",
  "name": "Apprentice Flame Miner",
  "titleType": "gathering",
  "difficultyTier": "apprentice",
  "description": "Fire-veined ores call to you. The heat of the deep welcomes your touch.",
  "bonuses": {
    "miningDamage": 0.25,
    "fireOreChance": 0.15,
    "elementalAfinity": "fire"
  },
  "prerequisites": {
    "activities": {
      "oresMined": 1000,
      "fireOresMined": 200
    },
    "requiredTitles": [
      "novice_miner"
    ],
    "characterLevel": 5
  },
  "acquisitionMethod": "event_based_rng",
  "generationChance": 0.2,
  "isHidden": false,
  "narrative": "The forge burns hotter with ores touched by flame. You seek them instinctively."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "journeyman_refiner",
  "name": "Journeyman Refiner",
  "titleType": "crafting",
  "difficultyTier": "journeyman",
  "description": "Impurities flee before your knowledge. Material transformation is your domain.",
  "bonuses": {
    "refiningPrecision": 0.5,
    "alloyQuality": 0.25,
    "materialYield": 0.1
  },
  "prerequisites": {
    "activities": {
      "materialsRefined": 500,
      "alloysCreated": 50
    },
    "requiredTitles": [
      "novice_refiner"
    ],
    "characterLevel": 10
  },
  "acquisitionMethod": "event_based_rng",
  "generationChance": 0.1,
  "isHidden": false,
  "narrative": "You see what others miss: the potential locked within raw matter."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "expert_battle_sage",
  "name": "Expert Battle Sage",
  "titleType": "combat",
  "difficultyTier": "expert",
  "description": "Combat flows through you like water. Blade and mind move as one.",
  "bonuses": {
    "meleeDamage": 1.0,
    "criticalChance": 0.2,
    "combatSkillExp": 0.25,
    "counterChance": 0.15
  },
  "prerequisites": {
    "activities": {
      "enemiesDefeated": 1000,
      "criticalHits": 500,
      "perfectDodges": 100
    },
    "requiredTitles": [
      "journeyman_warrior"
    ],
    "characterLevel": 20
  },
  "acquisitionMethod": "event_based_rng",
  "generationChance": 0.05,
  "isHidden": false,
  "narrative": "You don't fight. You dance. And everything around you dies beautifully."
}"""
        },
        {
            "input": """{
  "category": "",
  "tier": 1,
  "requirements": {},
  "tags": []
}""",
            "output": """{
  "titleId": "master_eternal_smith",
  "name": "Master Eternal Smith",
  "titleType": "crafting",
  "difficultyTier": "master",
  "description": "Legends speak of smiths who forged the impossible. You are one of them.",
  "bonuses": {
    "smithingTime": 2.0,
    "smithingQuality": 0.5,
    "firstTryBonus": 0.1,
    "durabilityBonus": 0.25,
    "legendaryChance": 0.05
  },
  "prerequisites": {
    "activities": {
      "itemsSmithed": 5000,
      "legendaryItemsCreated": 10,
      "perfectCrafts": 500
    },
    "requiredTitles": [
      "expert_master_smith"
    ],
    "characterLevel": 40
  },
  "acquisitionMethod": "special_achievement",
  "generationChance": 0.02,
  "isHidden": false,
  "narrative": "When you strike the anvil, gods pause to listen. Your work transcends mortality."
}"""
        }
    ],
}
