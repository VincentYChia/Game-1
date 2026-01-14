You are a world designer for an action fantasy sandbox RPG. Given chunk generation data, generate resource node definitions with yields, tiers, and spawn conditions. Return ONLY valid JSON.

# Node Types - Field Guidelines

Generate a JSON object following this structure with inline guidance:

```json
{
  "metadata": {
    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",
    "tags": ["Pick 2-5 from: "advanced", "ancient", "common", "crystal", "durable", "fine", "flexible", "impossible", "layered", "legendary", "living", "magical", "memory", "metal", "metallic", "mythical", "ore", "precious", "quality", "quantum", ... (31 total)]
  },
  "category": "Pick one: ["ore", "stone", "tree"]",
  "requiredTool": "Pick one: ["axe", "pickaxe"]",
  "respawnTime": "Pick one: ["normal", "slow", "very_slow"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===
  "baseHealth": 0,  // T1: 100.0-100.0, T2: 200.0-200.0, T3: 400.0-400.0, T4: 800.0-800.0

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