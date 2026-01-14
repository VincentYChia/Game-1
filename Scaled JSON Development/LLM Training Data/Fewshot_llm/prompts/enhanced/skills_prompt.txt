# Skills - Field Guidelines

Generate a JSON object following this structure with inline guidance:

```json
{
  "metadata": {
    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",
    "tags": ["Pick 2-5 from: "abundance", "alchemy", "aoe", "attack_speed", "basic", "berserker", "bonus", "burst", "bypass", "combat", "crafting", "critical", "damage", "damage_boost", "damage_reduction", "defense", "destruction", "durability", "efficiency", "enchanting", ... (52 total)]
  },
  "rarity": "Pick one: ["common", "epic", "legendary", "mythic", "rare", "uncommon"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===

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