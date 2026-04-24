# Tag-to-Effects System: Phase 1 Analysis

**Date:** 2025-12-15
**Status:** Discovery & Documentation
**Purpose:** Comprehensive analysis of all tags, effects, and abilities to design a universal tag-to-effects system

---

## Executive Summary

### Current State
- **190 unique tags** found across 44 JSON files (773 total occurrences)
- Tags are primarily **descriptive/categorical**, not functional
- **Only 3 tags** currently affect gameplay: `1H`, `2H`, `versatile`
- **Effect keywords** exist in text descriptions but are NOT formalized as tags
- **Special abilities** for hostiles exist separately from the tag system
- **122 tags are "uncategorized"** - need better classification

### Critical Discovery
**Many effects are described in text but NOT implemented as tags!**

Examples:
- "chain" - appears in 3+ effect descriptions, **NOT in any tags**
- "cone" - appears in effect descriptions, **NOT in tags**
- "burn", "bleed", "slow" - status effects in descriptions, **NOT in tags**
- "radius", "splash", "AOE" - geometry effects mentioned, incomplete in tags

---

## 1. Tag Inventory (190 Total Tags)

### 1.1 Currently Categorized Tags (68 tags)

#### AI Behavior (4 tags)
- `aggressive` (2 uses) - hostile behavior
- `defensive` (1 use) - defensive stance
- `passive` (2 uses) - non-aggressive behavior
- `support` (1 use) - support role

#### Attack Geometry (4 tags)
- `aoe` (3 uses) - area of effect (skills only)
- `area` (2 uses) - area attack (engineering items)
- `projectile` (2 uses) - projectile attack
- `ranged` (1 use) - ranged weapon

**MISSING:** `chain`, `cone`, `beam`, `splash`, `cleave`, `sweep`, `pierce` (mentioned in descriptions!)

#### Crafting Disciplines (5 tags)
- `alchemy` (6 uses)
- `enchanting` (4 uses)
- `engineering` (6 uses)
- `refining` (3 uses)
- `smithing` (8 uses)

#### Damage Types (2 tags)
- `crushing` (1 use)
- `precision` (2 uses)

**MISSING:** `slashing`, `piercing`, `blunt` (logical damage types)

#### Defensive Properties (4 tags)
- `armor` (19 uses)
- `defense` (8 uses)
- `defensive` (1 use)
- `shield` (1 use)

#### Device Types (4 tags)
- `bomb` (3 uses)
- `trap` (3 uses)
- `turret` (5 uses)
- `utility` (14 uses)

#### Elemental Types (4 tags)
- `fire` (9 uses)
- `frost` (5 uses)
- `lightning` (5 uses)
- `water` (1 use)

**MISSING:** `ice`, `earth`, `wind`, `nature`, `arcane`, `holy`, `shadow`, `void` (mentioned in lore)

#### Enemy Types (4 tags)
- `beetle` (3 uses)
- `construct` (2 uses)
- `entity` (1 use)
- `wolf` (3 uses)

#### Equipment Slots (2 tags)
- `accessory` (3 uses)
- `tool` (22 uses)

#### Gathering Activities (4 tags)
- `fishing` (1 use)
- `gathering` (11 uses)
- `harvesting` (1 use)
- `mining` (1 use)

#### Hand Type Tags (1 tag)
- `versatile` (1 use)

**MISSING:** `1H` and `2H` found in recipes but not in main tag inventory!

#### Item Categories (4 tags)
- `armor` (19 uses - duplicate with defensive)
- `potion` (11 uses)
- `tool` (22 uses - duplicate with equipment slot)
- `weapon` (29 uses)

#### Progression/Rarity (15 tags combined)
Rarity:
- `basic` (20 uses)
- `common` (3 uses)
- `uncommon` (5 uses)
- `rare` (10 uses)
- `epic` (8 uses)
- `legendary` (18 uses)
- `mythical` (5 uses)

Progression:
- `advanced` (11 uses)
- `starter` (27 uses)
- `master` (4 uses)
- `mastery` (2 uses)
- `end-game` (4 uses)
- `mid-game` (3 uses)
- `boss` (6 uses)

**ISSUE:** "master" vs "mastery" (92% similarity - potential typo)

#### Skill Categories (14 tags)
- `basic` (20 uses)
- `combat` (7 uses)
- `crafting` (7 uses)
- `damage_boost` (1 use)
- `efficiency` (6 uses)
- `gathering` (11 uses)
- `ultimate` (3 uses)
- Plus discipline tags (alchemy, enchanting, engineering, etc.)

#### Speed Modifiers (1 tag)
- `fast` (1 use)

**MISSING:** `slow`, `quick`, `rapid` as tags (found in descriptions)

#### Status Effects (1 tag)
- `poison` (2 uses)

**CRITICAL GAP:** Many status effects in descriptions but NOT as tags!

#### Weapon Types (9 tags)
- `axe` (5 uses)
- `bow` (2 uses)
- `dagger` (2 uses)
- `mace` (1 use)
- `pickaxe` (4 uses)
- `spear` (1 use)
- `staff` (1 use)
- `sword` (2 uses)
- `wandering` (1 use - likely NPC tag, not weapon)

**MISSING:** `hammer`, `polearm`, `crossbow`, `wand`

---

### 1.2 Uncategorized Tags (122 tags)

**High Priority for Tag-to-Effects System:**

**Combat Effects (need functional implementation):**
- `bash` - knockback/stun effect
- `cleaving` - AOE melee
- `critical` - crit chance/damage
- `damage` (13 uses) - generic damage modifier
- `knockback` (2 uses) - displacement effect
- `lifesteal` (2 uses) - HP drain
- `thorns` (2 uses) - reflect damage
- `vampiric` (2 uses) - same as lifesteal?

**Status Effects (currently only descriptive):**
- `immobilize` (1 use) - movement disable
- `burst` - instant damage spike
- `over_time` - DoT effect

**Buff/Debuff:**
- `buff` (4 uses) - positive effect
- `bonus` - stat bonus
- `damage_reduction` - defensive buff
- `damage_boost` - offensive buff
- `speed_boost` - movement buff
- `attack_speed` - attack rate buff

**Utility/Special:**
- `bypass` - ignore restrictions
- `disable` - disable target
- `flight` - movement ability
- `phase` - phasing ability
- `reflect` - reflect damage/projectiles
- `regeneration` (4 uses) - HP over time
- `repair` (3 uses) - durability restoration
- `resistance` (3 uses) - damage resistance
- `soulbound` (2 uses) - death persistence
- `transcendence` - reality warping

**Crafting/Materials (low priority for effects):**
- `adamantine`, `bronze`, `copper`, `iron`, `mithril`, `orichalcum`, `steel`, `tin`, `etherion`
- `alloy`, `crystallization`, `essence`, `metal`, `metallic`, `minerals`
- `brewing`, `forging`, `smelting`, `sawing`, `transmutation`, `purification`

**Item Properties:**
- `cluster` - splits into multiple
- `composite` - combined materials
- `durable` - high durability
- `durability` (7 uses) - durability stat
- `explosive` - explosive damage
- `fine`, `flexible`, `heavy`, `light` - physical properties
- `fortune` (4 uses) - luck/loot modifier
- `luck` (4 uses) - same as fortune?
- `multi_purpose` - versatile use
- `quality` (15 uses) - crafting quality
- `rarity` (27 uses) - item rarity
- `silk-touch` (2 uses) - special harvesting
- `soulbound` - cannot drop
- `special` (4 uses) - unique properties
- `universal` (12 uses) - applies to all
- `weight` (2 uses) - encumbrance

**Progression/NPC:**
- `essential` - important NPC
- `repeatable` - repeatable quest
- `station` (30 uses) - crafting station
- `tier` - item tier
- `trader`, `trainer`, `tutorial`, `wandering` - NPC roles

**Material Types:**
- `wood` (8 uses) - wood material
- Various named materials (see above)

---

## 2. Effect Keywords Found in Descriptions (NOT as Tags!)

### 2.1 Attack Geometry Effects (in descriptions, not tags)

**From Engineering Items:**
- **`chain`** - "Fires lightning bolts, 70 damage + chain" (lightning_cannon)
- **`cone`** - "Sweeps cone of fire" (flamethrower_turret)
- **`radius`** - "Explodes for 40 damage in 3 unit radius" (simple_bomb)
- **`wide area`** - "120 damage over wide area" (cluster_bomb)
- **`splits`** - "Splits into 8 smaller explosions" (cluster_bomb)

**Currently Existing (partial):**
- `aoe` - in skills, but not items
- `area` - in some items
- `projectile` - basic projectile

**MISSING FROM TAGS:**
- `chain` - arc between targets
- `cone` - cone-shaped attack
- `beam` - continuous line attack
- `splash` - impact AOE
- `pierce` - penetrate through targets

### 2.2 Status Effects (in descriptions, not tags)

**From Engineering Items:**
- **`burn`** / **`burning`** / **`lingering burn`** - "35 damage + burn" (fire_arrow_turret)
- **`slow`** - "50 damage + slow" (frost_mine), "slows enemies by 80%" (net_launcher)
- **`bleed`** - "30 damage + bleed" (spike_trap)
- **`immobilize`** - "25 damage + immobilize for 5 seconds" (bear_trap)

**From Hostile Special Abilities:**
- `acid_damage_over_time` - DoT effect
- None of these are formalized as tags!

**Currently Existing:**
- `poison` (2 uses as tag) - but not implemented

**MISSING FROM TAGS:**
- `burn` / `burning` - fire DoT
- `freeze` / `frozen` - ice CC
- `slow` / `slowed` - movement reduction
- `stun` / `stunned` - action disable
- `bleed` / `bleeding` - physical DoT
- `shock` / `electrified` - lightning effect
- `weaken` / `weakened` - stat reduction
- `root` / `rooted` - movement disable

### 2.3 Healing/Support Effects

- `heal` / `heals` - "Heals 10 HP/sec" (healing_beacon)
- `regenerate` / `regeneration` - over-time healing
- `restore` - instant restoration

Current: `healing` (11 uses) - but as tag, not implemented effect

---

## 3. Hostile Special Abilities (NOT in Tag System!)

### 3.1 Current Implementation
Hostiles have `"specialAbilities"` arrays separate from tags.

**All Special Abilities Found:**

**Wolf Abilities:**
- `howl_buff` - pack buff
- `leap_attack` - gap closer

**Slime Abilities:**
- `acid_damage_over_time` - DoT
- `split_on_damage` - spawns smaller slimes
- `elemental_burst` - AOE damage

**Beetle Abilities:**
- `charge_attack` - rush attack
- `earthquake_stomp` - AOE knockdown
- `shell_shield` - damage reduction
- `rampage` - enraged state

**Golem Abilities:**
- `ground_slam` - AOE attack
- `stone_armor` - defense buff
- `crystal_beam` - beam attack
- `refraction_shield` - projectile reflection
- `summon_shards` - summon minions

**Wraith Abilities:**
- `phase_shift` - intangibility
- `life_drain` - HP steal
- `teleport` - instant movement

**Primordial Entity Abilities:**
- `reality_warp` - reality manipulation
- `void_rift` - portal/AOE
- `temporal_distortion` - time manipulation
- `chaos_burst` - random AOE

### 3.2 The Problem
These abilities are **hardcoded separately** from the tag system. A universal tag-to-effects system should handle ALL of these!

---

## 4. Gaps & Inconsistencies

### 4.1 Potential Typos (85%+ similarity)
- `master` vs `mastery` (92.31%)
- `flight` vs `light` (90.91%) - probably not a typo, but similar
- `defense` vs `defensive` (87.50%) - semantic overlap
- `common` vs `uncommon` (85.71%) - related but distinct

### 4.2 Missing Hand Type Tags
- `1H` - found ONLY in recipes (1 occurrence)
- `2H` - found ONLY in recipes (1 occurrence)
- `versatile` - found in tags (1 occurrence)

**Issue:** Hand type tags should be consistent across items AND recipes!

### 4.3 Tag Duplication/Overlap
- `armor` appears in both "defensive" and "item_category" (19 uses)
- `tool` appears in both "equipment_slot" and "item_category" (22 uses)
- `luck` (4 uses) vs `fortune` (4 uses) - same concept?
- `lifesteal` vs `vampiric` - same effect?
- `master` vs `mastery` - related progression
- Various discipline tags (`smithing`, `alchemy`) overlap with skill categories

### 4.4 Missing Logical Tags

**Damage Types:**
- `slashing` - sword/axe damage
- `piercing` - spear/arrow damage
- `blunt` - mace/hammer damage
- Current: Only `crushing` and `precision`

**Attack Geometry:**
- `chain` - lightning, curse spreading
- `cone` - flamethrower, breath
- `beam` - laser, ray
- `splash` - impact AOE
- `pierce` - penetrate armor/targets

**Status Effects:**
- `burn`, `freeze`, `stun`, `slow`, `bleed`, `root`, `weaken`, `fear`
- Current: Only `poison`

**Elemental:**
- `ice`, `earth`, `wind`, `nature`, `arcane`, `holy`, `shadow`, `void`
- Current: Only `fire`, `frost`, `lightning`, `water`

---

## 5. Tag Usage Patterns

### 5.1 Where Tags Appear

**Most Common Files:**
1. **recipes.JSON/** - 340+ tag occurrences
2. **items.JSON/** - 150+ tag occurrences
3. **Skills/** - 130+ tag occurrences
4. **Definitions.JSON/hostiles-1.JSON** - 40+ tag occurrences
5. **progression/** - 30+ tag occurrences

### 5.2 Tag Density by Category

**High-frequency tags (20+ uses):**
- `station` (30 uses) - crafting stations
- `weapon` (29 uses) - weapon category
- `rarity` (27 uses) - item rarity
- `starter` (27 uses) - starter content
- `upgrade` (23 uses) - upgrade recipes
- `tool` (22 uses) - tools
- `basic` (20 uses) - basic tier
- `armor` (19 uses) - armor category
- `legendary` (18 uses) - legendary tier

**Low-frequency tags (1-2 uses):**
- 80+ tags have only 1-2 occurrences
- Many are material names or one-off descriptors
- Some are critical mechanics (`1H`, `2H`, `versatile`) despite low count!

---

## 6. Recommended Tag Vocabulary (Unified System)

### 6.1 Core Functional Tags (Must Implement Effects)

#### **Equipment/Weapon Properties**
- `1H` - can equip in either hand
- `2H` - requires both hands
- `versatile` - can use offhand optionally
- `dual_wield` - requires two weapons
- `thrown` - throwable weapon

#### **Attack Geometry (Target Selection)**
- `single_target` - hits one target
- `chain` - arcs to nearby targets (n targets, m range)
- `cone` - cone-shaped AOE (angle, range)
- `circle` / `radius` / `aoe` - circular AOE (radius)
- `beam` / `line` - line attack (range, width)
- `pierce` - penetrates through targets
- `splash` - impact AOE around hit point
- `cleave` - frontal arc melee AOE
- `sweep` - 360° melee AOE
- `projectile` - ranged projectile
- `hitscan` - instant ranged

#### **Damage Types**
- `physical` - physical damage
- `slashing` - swords, axes
- `piercing` - spears, arrows
- `crushing` / `blunt` - maces, hammers
- `elemental` - elemental damage
- `fire` - fire damage
- `frost` / `ice` - cold damage
- `lightning` / `electric` - electric damage
- `poison` - poison damage
- `arcane` / `magic` - magic damage
- `holy` / `light` - holy damage
- `shadow` / `dark` - shadow damage
- `chaos` / `void` - chaos damage

#### **Status Effects (Debuffs)**
- `burn` - fire DoT (damage/sec, duration)
- `freeze` - full immobilization (duration)
- `chill` / `slow` - movement speed reduction (%, duration)
- `stun` - action disable (duration)
- `root` - movement disable (duration)
- `bleed` - physical DoT (damage/sec, duration)
- `poison_status` - poison DoT (damage/sec, duration)
- `shock` - periodic damage + interrupt
- `weaken` - stat reduction (%, duration)
- `vulnerable` - increased damage taken (%, duration)
- `silence` - disable skills (duration)
- `blind` - accuracy reduction (%, duration)
- `fear` - forced movement away (duration)
- `taunt` - forced targeting (duration)

#### **Status Effects (Buffs)**
- `haste` / `quicken` - attack speed increase
- `empower` - damage increase
- `fortify` - defense increase
- `regeneration` / `regen` - HP over time
- `shield` / `barrier` - absorb damage
- `invisible` / `stealth` - avoid detection
- `invulnerable` - immune to damage (short duration)
- `enrage` / `berserker` - damage up, defense down

#### **Special Mechanics**
- `lifesteal` / `vampiric` - HP drain from damage (%)
- `reflect` / `thorns` - reflect damage (% or flat)
- `knockback` - displacement (distance)
- `pull` - pull targets towards source
- `summon` - spawn entities
- `teleport` - instant movement
- `dash` / `blink` - short-distance movement
- `charge` - movement + attack
- `leap` - vertical + horizontal movement
- `phase` - temporary intangibility
- `block` - negate next attack
- `parry` - counter-attack on block
- `execute` - bonus damage below HP threshold
- `critical` - crit chance/damage modifier

#### **Trigger Conditions**
- `on_hit` - triggers when hitting
- `on_kill` - triggers on enemy death
- `on_damage` - triggers when taking damage
- `on_block` - triggers when blocking
- `on_dodge` - triggers when dodging
- `on_crit` - triggers on critical hit
- `on_low_hp` - triggers below HP threshold
- `passive` - always active
- `active` - requires activation
- `toggle` - on/off state
- `channeled` - continuous cast
- `instant` - no cast time
- `cooldown` - time between uses

#### **Targeting/Context**
- `self` - affects caster
- `ally` / `friendly` - affects allies
- `enemy` / `hostile` - affects enemies
- `all` - affects all entities
- `player` - affects players only
- `turret` / `device` - affects devices
- `construct` - affects constructs
- `undead` - affects undead
- `mechanical` - affects mechanical enemies

---

### 6.2 Descriptive Tags (Non-Functional)

**These tags are for filtering/categorization, not effects:**

- Rarity: `common`, `uncommon`, `rare`, `epic`, `legendary`, `mythical`
- Tier: `starter`, `basic`, `advanced`, `master`, `end-game`
- Disciplines: `smithing`, `alchemy`, `engineering`, `enchanting`, `refining`
- Categories: `weapon`, `armor`, `potion`, `tool`, `device`, `station`
- Materials: `iron`, `steel`, `mithril`, `wood`, `copper`, etc.
- Slots: `helmet`, `chest`, `legs`, `feet`, `hands`, `accessory`
- Enemy types: `wolf`, `slime`, `beetle`, `golem`, `wraith`, `construct`

**Keep these, but they should NOT generate effects automatically.**

---

## 7. Next Steps

### Phase 2: Tag Definitions
Create plain-text definitions for each functional tag including:
- **Tag name** and aliases
- **Category** (geometry, status, damage type, etc.)
- **Parameters** (magnitude, duration, range, count, etc.)
- **Context-aware behavior** (what happens when used on enemies vs allies vs objects)
- **Combination rules** (how it interacts with other tags)
- **Visual indicators** (VFX, UI hints)

### Phase 3: Effect Composition System
Design how multiple tags combine:
- `fire` + `chain` = chaining fire damage
- `cone` + `freeze` = freeze enemies in cone
- `projectile` + `pierce` = penetrating projectile
- `lifesteal` + `aoe` = heal from all targets hit

### Phase 4: Implementation Architecture
- Effect registry (tag → effect function mapping)
- Context detection (enemy/ally/object/terrain)
- Target finder (geometry-based target selection)
- Effect application pipeline
- Debug/logging framework

### Phase 5: Migration
- Replace hardcoded skill effects with tags
- Convert hostile special abilities to tags
- Update all item/turret effect descriptions to use tags
- Validation and testing

---

## 8. Open Questions for User

1. **Tag Naming Conventions:**
   - Should we use `burn` or `burning`? `freeze` or `frozen`?
   - Prefer underscores (`damage_over_time`) or single words (`burn`)?

2. **Tag Combinations:**
   - Should `fire` + `chain` automatically make targets take ongoing fire damage?
   - Or should it require both `fire` and `burn` tags?

3. **Magnitude/Parameters:**
   - Should tags encode magnitude? (`burn_minor`, `burn_major`)
   - Or should tags be pure flags with magnitude in separate field?

4. **Backwards Compatibility:**
   - Should we preserve existing tags during migration?
   - Or consolidate duplicates (e.g., `luck` and `fortune` → just `luck`)?

5. **Default Behaviors:**
   - What happens if a tag has no context match?
   - E.g., `chain` on an NPC dialogue - silent fail or error log?

---

**End of Phase 1 Analysis**

**Next Document:** `TAG-DEFINITIONS-PHASE2.md` - Detailed tag definitions with context-aware behavior
