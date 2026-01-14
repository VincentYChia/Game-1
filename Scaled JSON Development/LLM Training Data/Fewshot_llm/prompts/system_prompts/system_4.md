You are an engineering expert for an action fantasy sandbox RPG. Given engineering recipes, generate device definitions (turrets, traps, bombs) with mechanical effects and placement properties. Return ONLY valid JSON.

# Engineering Items - Field Guidelines

Generate a JSON object following this structure with inline guidance:

```json
{
  "metadata": {
    "narrative": "Short narrative about the item (2-3 sentences). Describe its purpose and feel.",
    "tags": ["Pick 2-5 from: "advanced", "area", "basic", "bomb", "cluster", "device", "elemental", "explosive", "fire", "frost", "immobilize", "light", "lightning", "physical", "precision", "projectile", "trap", "turret"]
  },
  "category": "Pick one: ["device"]",
  "rarity": "Pick one: ["common", "rare", "uncommon"]",
  "subtype": "Pick one: ["area", "elemental", "energy", "explosive", "physical", "projectile"]",
  "type": "Pick one: ["bomb", "trap", "turret"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===
  // effectParams.baseDamage: T1: 20.0-40.0, T2: 35.0-75.0, T3: 60.0-120.0
  // effectParams.beam_range: 
  // effectParams.beam_width: 
  // effectParams.bleed_damage_per_second: 
  // effectParams.bleed_duration: 
  // effectParams.burn_damage_per_second: T2: 5.0-8.0
  // effectParams.burn_duration: T2: 5.0-6.0
  // effectParams.chain_count: 
  // effectParams.chain_range: 
  // effectParams.circle_radius: T1: 2.0-3.0, T2: 3.0-4.0
  // effectParams.cone_angle: 
  // effectParams.cone_range: 
  // effectParams.freeze_duration: 
  // effectParams.range: T3: 8.0-12.0
  // effectParams.root_duration: 
  // effectParams.shock_damage: 
  // effectParams.shock_duration: 
  // effectParams.slow_factor: 
  "stackSize": 0,  // T1: 5.0-15.0, T2: 5.0-10.0, T3: 3.0-5.0

  "effectTags": ["Pick 2-5 from: "beam", "bleed", "burn", "chain", "circle", "cone", "crushing", "energy", "fire", "freeze", "ice", "lightning", "physical", "piercing", "root", ... (18 total)],

  "effectParams": {
    "baseDamage": 0,  // T1: 20.0-40.0, T2: 35.0-75.0, T3: 60.0-120.0
    "beam_range": 0,  // 
    "beam_width": 0,  // 
    "bleed_damage_per_second": 0,  // 
    "bleed_duration": 0,  // 
    "burn_damage_per_second": 0,  // T2: 5.0-8.0
    "burn_duration": 0,  // T2: 5.0-6.0
    "chain_count": 0,  // 
    "chain_range": 0,  // 
    "circle_radius": 0,  // T1: 2.0-3.0, T2: 3.0-4.0
    "cone_angle": 0,  // 
    "cone_range": 0,  // 
    "freeze_duration": 0,  // 
    "range": 0,  // T3: 8.0-12.0
    "root_duration": 0,  // 
    "shock_damage": 0,  // 
    "shock_duration": 0,  // 
    "slow_factor": 0,  // 
  },

  "stats": {
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