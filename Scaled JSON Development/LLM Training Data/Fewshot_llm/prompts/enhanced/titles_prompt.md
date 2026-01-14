# Titles - Field Guidelines

Generate a JSON object following this structure with inline guidance:

```json
{
  "acquisitionMethod": "Pick one: ["event_based_rng", "guaranteed_milestone", "hidden_discovery", "special_achievement"]",
  "description": "Pick one: ["Combat flows through you like water. Blade and mind move as one.", "Fire-veined ores call to you. The heat of the deep welcomes your touch.", "First blood has been drawn. You've tasted battle and survived.", "Fortune herself smiles upon you. Or perhaps you've rigged the dice.", "Impurities flee before your knowledge. Material transformation is your domain.", "Legends speak of smiths who forged the impossible. You are one of them.", "The forest acknowledges your presence. Trees fall before you.", "The forge accepts you. Your hammer rings with purpose.", "Wyrms fear your name. The great beasts fall before you.", "Your first steps into the depths. Every mine begins with a single swing."]",
  "difficultyTier": "Pick one: ["apprentice", "expert", "journeyman", "master", "novice", "special"]",
  "name": "Pick one: ["Apprentice Flame Miner", "Dragon's Bane", "Expert Battle Sage", "Journeyman Refiner", "Lucky Bastard", "Master Eternal Smith", "Novice Lumberjack", "Novice Miner", "Novice Smith", "Novice Warrior"]",
  "narrative": "Pick one: ["Every great lumberjack started by felling their hundredth tree.", "Fifty foes have fallen. You're no longer prey.", "Heat, hammer, shape. The trinity of the smith begins with you.", "The dragon's roar becomes silence. You are the end of their age.", "The forge burns hotter with ores touched by flame. You seek them instinctively.", "The stone remembers your first strike. Keep swinging.", "When you strike the anvil, gods pause to listen. Your work transcends mortality.", "You don't believe in luck. You ARE luck.", "You don't fight. You dance. And everything around you dies beautifully.", "You see what others miss: the potential locked within raw matter."]",
  "titleId": "Pick one: ["apprentice_flame_miner", "expert_battle_sage", "hidden_dragons_bane", "hidden_lucky_bastard", "journeyman_refiner", "master_eternal_smith", "novice_lumberjack", "novice_miner", "novice_smith", "novice_warrior"]",
  "titleType": "Pick one: ["combat", "crafting", "gathering", "utility"]",
  "tier": 1,  // 1-4 (affects stat ranges below)
  "rarity": "Pick one: [common, uncommon, rare, epic, legendary, unique]",

  // === NUMERIC FIELDS (by tier) ===
  "generationChance": 0,  // T1: 0.0-1.0
  "isHidden": 0,  // T1: 0.0-1.0

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