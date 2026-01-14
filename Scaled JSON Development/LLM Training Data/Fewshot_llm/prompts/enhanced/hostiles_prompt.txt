# Hostiles - Field Guidelines

Generate a JSON object following this structure with inline guidance:

```json
{
  "metadata": {
    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",
    "tags": ["Pick 2-5 from: "aggressive", "beetle", "boss", "common", "construct", "docile", "end-game", "entity", "epic", "golem", "mid-game", "mythical", "passive", "phase", "rare", "reality-bender", "slime", "starter", "territorial", "uncommon", ... (22 total)]
  },
  "behavior": "Pick one: ["aggressive_pack", "aggressive_phase", "aggressive_swarm", "boss_encounter", "docile_wander", "passive_patrol", "stationary", "territorial"]",
  "category": "Pick one: ["aberration", "beast", "construct", "insect", "ooze", "undead"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===
  // stats.aggroRange: T1: 3.0-5.0, T2: 6.0-8.0, T3: 10.0-12.0, T4: 12.0-20.0
  // stats.attackSpeed: T1: 0.8-1.0, T2: 0.8-1.2, T3: 0.6-1.5, T4: 0.7-1.3
  // stats.damage[0]: T1: 5.0-8.0, T2: 15.0-20.0, T3: 40.0-50.0, T4: 60.0-120.0
  // stats.damage[1]: T1: 8.0-12.0, T2: 22.0-30.0, T3: 60.0-80.0, T4: 90.0-180.0
  // stats.defense: T1: 2.0-12.0, T2: 8.0-25.0, T3: 25.0-40.0, T4: 15.0-60.0
  // stats.health: T1: 50.0-100.0, T2: 120.0-250.0, T3: 500.0-800.0, T4: 400.0-2000.0
  // stats.speed: T1: 0.5-1.2, T2: 0.7-1.4, T3: 0.5-1.6, T4: 0.6-1.5

  "stats": {
    "aggroRange": 0,  // T1: 3.0-5.0, T2: 6.0-8.0, T3: 10.0-12.0, T4: 12.0-20.0
    "attackSpeed": 0,  // T1: 0.8-1.0, T2: 0.8-1.2, T3: 0.6-1.5, T4: 0.7-1.3
    "damage[0]": 0,  // T1: 5.0-8.0, T2: 15.0-20.0, T3: 40.0-50.0, T4: 60.0-120.0
    "damage[1]": 0,  // T1: 8.0-12.0, T2: 22.0-30.0, T3: 60.0-80.0, T4: 90.0-180.0
    "defense": 0,  // T1: 2.0-12.0, T2: 8.0-25.0, T3: 25.0-40.0, T4: 15.0-60.0
    "health": 0,  // T1: 50.0-100.0, T2: 120.0-250.0, T3: 500.0-800.0, T4: 400.0-2000.0
    "speed": 0,  // T1: 0.5-1.2, T2: 0.7-1.4, T3: 0.5-1.6, T4: 0.6-1.5
  },

  "requirements": {
    "level": 1,  // Typically: T1: 1-5, T2: 6-15, T3: 16-25, T4: 26-30
    "stats": {}  // Optional stat requirements
  },

  "flags": {
    "stackable": false,
    "equippable": true,
    "repairable": true
  }
}
```

## Important Guidelines:

1. **IDs**: Use snake_case (e.g., `iron_sword`, `health_potion`)
2. **Names**: Use Title Case matching ID (e.g., `Iron Sword`, `Health Potion`)
3. **Tier Consistency**: Ensure all stats match the specified tier
4. **Tags**: Only use tags from the library above
5. **Narrative**: Keep it concise (2-3 sentences) and thematic
6. **Stats**: Stay within ±33% of tier ranges (validation will flag outliers)