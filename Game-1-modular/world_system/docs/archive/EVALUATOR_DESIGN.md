# Evaluator Design — Layers 3 and 4

**Created**: 2026-03-24
**Scope**: What evaluators exist, what they see, what they produce, and how they overlap

---

## Design Philosophy

1. **More evaluators is better than fewer**. The cost of an evaluator that fires and finds nothing notable is near zero. The cost of missing an important pattern is high.

2. **Dual coverage is expected**. The same event (e.g., killing 50 wolves in Old Forest) may trigger both a Combat evaluator ("player is a proficient hunter") AND a Population evaluator ("wolf population declining in Old Forest"). These are different truths about the same fact.

3. **Context prevents misclassification**. A Crafting evaluator that only sees "smithing count = 95" can't tell if the player is a smithing specialist or just a well-rounded crafter. It needs to see ALL discipline counts to make that judgment. Evaluators should see enough to avoid false conclusions, even if they don't act on all of it.

4. **Triggers are opportunities, not mandates**. When a milestone threshold fires (1, 3, 5, 10, 25...), the evaluator examines the situation. It may produce nothing if the pattern isn't notable yet. It may update an existing interpretation. It may produce a new one.

5. **Each evaluator answers a question**, not tracks a stat. "Is the ecosystem under pressure?" not "count resource gathers."

---

## Layer 3 Evaluators

These consume Layer 2 events and Layer 1 stats to produce simple one-sentence interpretations.

### Population Dynamics

**Question**: What is happening to creature populations in this area?

**Triggers on**: ENEMY_KILLED milestone thresholds
**Also sees**: Kill distribution by species, by tier, by region. Layer 1 total kill stats.

**Outputs**:
- "Wolf population declining in Old Forest. 23 killed in recent days."
- "The goblin camps near Iron Hills have been cleared out. 47 eliminated."
- "A T3 dire bear was slain in the Eastern Caves — a rare kill."

**Nuance the old design lacked**: Different species matter differently. Killing 50 wolves is different from killing 5 T3 bears. The evaluator should weight by tier and rarity, not just count.

**Dual coverage**: A kill event also triggers Combat Proficiency. Population tracks the *ecological* impact; Combat tracks the *player's martial growth*.

### Ecosystem Pressure

**Question**: Are natural resources being sustainably harvested or depleted?

**Triggers on**: RESOURCE_GATHERED, NODE_DEPLETED milestone thresholds
**Also sees**: Biome resource state (from EcosystemAgent's depletion tracking), gather rate vs regeneration rate, resource tier.

**Outputs**:
- "Iron ore deposits are under heavy pressure in Iron Hills. 180 of 250 gathered."
- "Herb gathering in Peaceful Forest is light — ecosystem healthy."
- "Critical: Mithril ore nearly exhausted in the Eastern Caves. 95% depleted."

**Why this is separate from the old ResourcePressure evaluator**: The old one just counted gathers. This one correlates with actual depletion state, regeneration rates, and can distinguish sustainable harvesting from over-extraction.

### Combat Proficiency

**Question**: How capable and active is the player in combat?

**Triggers on**: ENEMY_KILLED, ATTACK_PERFORMED, DODGE_PERFORMED, PLAYER_DEATH, STATUS_APPLIED milestones
**Also sees**: Layer 1 stats — total damage dealt/taken by element, critical hit rate, longest killstreak, deaths, weapon types used, status effects applied/received, dungeon stats.

**Outputs**:
- "The adventurer has taken their first blood in Old Forest."
- "The adventurer has reached 100 kills. Proficient hunter."
- "The adventurer nearly died fighting a T3 cave troll — survived at 12% health."
- "Flawless victory against a T2 pack — no damage taken."
- "The adventurer is struggling in the Eastern Caves. 3 deaths, high damage taken."

**What this sees that AreaDanger didn't**: The old AreaDanger evaluator only counted damage taken and deaths. Combat Proficiency tracks the full picture — kills, near-death survival, flawless fights, weapon preferences, status effect usage. It can distinguish "area is dangerous" from "player is reckless" from "player is dominating."

**Dual coverage with Population**: A kill event fires both. Population says "wolves are dying." Combat says "player is becoming a skilled wolf hunter." Different audiences care about different truths.

**Low-health tracking**: A "near death" event is defined as: player at 15% HP or lower for 20+ continuous seconds, then above 15% for 20+ seconds (to filter out noise from rapid fluctuations). This is tracked by the game loop and published as a synthetic event.

### Crafting Mastery

**Question**: What is the player's crafting identity?

**Triggers on**: CRAFT_ATTEMPTED, ITEM_INVENTED, RECIPE_DISCOVERED milestones
**Also sees**: Layer 1 stats — per-discipline craft counts, per-discipline quality scores, tier distribution, success rates, perfect crafts, legendary crafts, best minigame scores.

**What it evaluates at each trigger**:
- Craft count by discipline (all 5)
- Craft count by tier (T1-T4) within each discipline
- Quality distribution (normal/fine/superior/masterwork/legendary) per discipline
- 95%+ minigame score count (total and per discipline)
- Success rate trends

**Outputs**:
- "The adventurer is specializing in smithing. 45 of 60 total crafts."
- "Dual specialty detected: smithing and enchanting both at 30+ crafts."
- "Legendary-quality alchemy output. 5 legendary potions crafted."
- "Well-rounded crafter: no single discipline above 40% of total."
- "First masterwork item crafted — a smithing achievement."
- "95%+ minigame performance in 12 of last 20 smithing attempts."

**Why context matters**: Without seeing ALL disciplines, the evaluator can't distinguish "smithing specialist" from "all-around crafter who happens to have done a lot of smithing." The ratio across disciplines is what determines specialization, not the absolute count.

### Player Milestones

**Question**: Has the player achieved something notable in their progression?

**Triggers on**: LEVEL_UP, TITLE_EARNED, CLASS_CHANGED, SKILL_LEARNED milestones
**Also sees**: Layer 1 progression stats, current level, titles earned by tier.

**Outputs**:
- "The adventurer has reached level 10. A significant milestone."
- "The adventurer has earned the title 'Wolf Hunter' — their first expert-tier title."
- "Class changed to Warrior. A defining choice."
- "5 skills learned in rapid succession — the adventurer is expanding their toolkit."

**Kept narrow by design**: This evaluator only covers progression events. Combat milestones (100 kills, first boss) are handled by Combat Proficiency. Crafting milestones (first legendary) are handled by Crafting Mastery. This avoids one evaluator trying to do everything.

### Exploration & Discovery

**Question**: How is the player engaging with the world geographically?

**Triggers on**: CHUNK_ENTERED, AREA_DISCOVERED milestones
**Also sees**: Layer 1 exploration stats — unique chunks visited, distance traveled by biome, furthest from spawn.

**Outputs**:
- "The adventurer has explored 25 unique areas. A well-traveled individual."
- "First visit to the Eastern Caves — new territory."
- "The adventurer has traveled extensively through mountain biomes."
- "Furthest expedition yet — 40 tiles from spawn."

### Social & Reputation

**Question**: How is the player interacting with NPCs and factions?

**Triggers on**: NPC_INTERACTION, QUEST_COMPLETED, QUEST_FAILED, faction milestone events
**Also sees**: Layer 1 social stats — NPCs met, dialogues completed, quests by type, faction reputation scores.

**Outputs**:
- "The adventurer has a strong relationship with the blacksmith. 7 conversations, friendly disposition."
- "Village Guard reputation: Recognized (0.28). The guards are warming up."
- "3 quests completed for the Crafters Guild. Building trust."
- "First quest failed — the herbalist's request went unfulfilled."

**NPC/Faction evaluations are functionally similar**: Both condense interaction history into narrative. They see NPC/faction metadata (personality, likes/dislikes, territory) and player behavior toward them. Higher layers will put even more emphasis on this — getting to know NPCs and factions is a progressive experience, like getting to know people.

### Economy & Items

**Question**: What is the player's economic behavior?

**Triggers on**: ITEM_ACQUIRED, ITEM_EQUIPPED, REPAIR_PERFORMED, ITEM_CONSUMED milestones
**Also sees**: Layer 1 economy stats, item collection counts, equipment swap history.

**Outputs**:
- "The adventurer has collected 15 unique items — a growing inventory."
- "Heavy potion usage in combat — 8 potions consumed in recent fights."
- "First T3 weapon equipped. A significant upgrade."
- "Frequent equipment swaps — the adventurer is experimenting with loadouts."

### Dungeon Progress

**Question**: How is the player performing in dungeon content?

**Triggers on**: Dungeon-related events (entered, completed, abandoned, wave, chest)
**Also sees**: Layer 1 dungeon stats — completions by rarity, fastest clears, deaths in dungeons.

**Outputs**:
- "First dungeon completed — a common-tier dungeon cleared."
- "3 rare dungeons completed. The adventurer is taking on serious challenges."
- "Dungeon abandoned after 2 deaths. The difficulty may be too high."
- "Fastest dungeon clear yet — 45 seconds. The adventurer is mastering this content."

---

## Layer 4 Evaluators (Connected Interpretations)

These consume Layer 3 interpretations and Layer 2 events to detect cross-domain and cross-region patterns. They have **different trigger thresholds** than Layer 3.

### Regional Activity Synthesizer

**Question**: What is the overall pattern of activity in this district/province?

**Consumes**: ALL Layer 3 categories for a geographic area
**Trigger**: 3+ Layer 3 interpretations in the same district within a time window

**Outputs**:
- "The player is systematically clearing Old Forest — population declining, resources harvested, multiple combat encounters."
- "Iron Hills is experiencing heavy extraction — both ore and wildlife depleted."
- "The Eastern Caves are contested territory — high danger, multiple deaths, but also significant kills."

**This is what the developer feedback described**: If three forests are decimated recently and are in the same region, Layer 4 notes "the player is decimating the northern forests." Layer 3 only saw each forest individually.

### Cross-Domain Pattern Detector

**Question**: Are there patterns that span multiple evaluator domains?

**Consumes**: Layer 3 interpretations from different categories that share geographic or temporal proximity
**Trigger**: 2+ different Layer 3 categories fire for the same area within a time window

**Outputs**:
- "The player is plundering Iron Hills — both wildlife (Population) and resources (Ecosystem) under heavy pressure."
- "Combat activity and crafting activity are correlated in the central district — the player fights, then forges."
- "Danger in the Eastern Caves is paired with exploration — the player keeps pushing deeper despite deaths."

### Player Identity Consolidator

**Question**: What kind of player is this, based on accumulated Layer 3 patterns?

**Consumes**: Layer 3 interpretations across all categories, weighted by frequency and severity
**Trigger**: Every 10 Layer 3 interpretations (regardless of category)

**Outputs**:
- "The adventurer is primarily a combatant — 60% of notable activity is combat-related."
- "Dual identity: skilled crafter (smithing+enchanting) and capable fighter."
- "Explorer-gatherer: high exploration activity, heavy resource collection, minimal combat."
- "The adventurer is a cautious player — avoids high-tier enemies, thorough resource collection."

### Faction Narrative Synthesizer

**Question**: What is the story of the player's relationship with each faction?

**Consumes**: Layer 3 Social & Reputation interpretations, faction milestone data, NPC interaction patterns
**Trigger**: Faction milestone crossed, OR 5+ social interpretations involving same faction

**Outputs**:
- "The Village Guard has gone from ignoring the adventurer to recognizing them as an ally. Recent bandit clearing cemented the relationship."
- "The Forest Wardens are growing hostile. Heavy deforestation and wildlife kills conflict with their values."
- "The Crafters Guild respects the adventurer's smithing skill but the relationship is still developing."

**Higher layers will see even more NPC/faction detail** — like getting to know people over time. Layer 4 begins that process by consolidating interactions into relationship narratives.

---

## Evaluator Visibility Rules

| Evaluator Layer | Sees Layer N-1 (full) | Sees Layer N-2 (limited) | Cannot See |
|:---:|:---:|:---:|:---:|
| Layer 3 | Layer 2 (events in lookback window) | Layer 1 (aggregate stats for context) | Layer 0 (bus events) |
| Layer 4 | Layer 3 (interpretations in scope) | Layer 2 (events for supporting detail) | Layer 1 |
| Layer 5 | Layer 4 (connected interpretations) | Layer 3 (significant+ interpretations) | Layers 1-2 |

---

## Dual Coverage Map

Shows which Layer 3 evaluators fire on the same event types:

| Event | Population | Ecosystem | Combat | Crafting | Milestones | Exploration | Social | Economy | Dungeon |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ENEMY_KILLED | X | | X | | | | | | |
| RESOURCE_GATHERED | | X | | | | | | | |
| CRAFT_ATTEMPTED | | | | X | | | | | |
| ITEM_INVENTED | | | | X | | | | | |
| DAMAGE_TAKEN | | | X | | | | | | |
| PLAYER_DEATH | | | X | | | | | | X |
| LEVEL_UP | | | | | X | | | | |
| TITLE_EARNED | | | | | X | | X | | |
| NPC_INTERACTION | | | | | | | X | | |
| QUEST_COMPLETED | | | | | | | X | | |
| CHUNK_ENTERED | | | | | | X | | | |
| ITEM_EQUIPPED | | | | | | | | X | |
| DODGE_PERFORMED | | | X | | | | | | |
| STATUS_APPLIED | | | X | | | | | | |
| Dungeon events | | | | | | | | | X |

The ENEMY_KILLED dual coverage (Population + Combat) is the clearest example: "wolves are dying" and "player is becoming a skilled hunter" are both true and both useful to different consumers.
