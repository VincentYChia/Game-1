# Feature Trace 03 — Hostiles

**Wave:** 2 (parallel; calibrator = `01-quests.md`)
**Owned endpoints:** `wes_tool_hostiles`, `wes_hub_hostiles`
**Final output artifact:** `EnemyDefinition` JSON (one per LLM call from `wes_tool_hostiles`), persisted into `Definitions.JSON/hostiles-generated-*.JSON` and consumed at game start by `EnemyDatabase` and at chunk-spawn time by `CombatManager` / `ChunkTemplateDatabase.enemy_spawns`.
**Date:** 2026-05-26

> "The slop version is `level-3 wolf, HP 30, 1d8 damage`. The stagnant version is the same five enemies forever. The crazy version is a tropical-pelican-with-a-flamethrower in a snowy forest. The bar is above templated baseline."

A hostile is the thing the player swings at. It is also the thing that swings back. Everything in this trace is in service of: (a) the moment the player's HP bar moves because *something specific* hit them, (b) the moment they realize the thing they just killed belonged to *this* moor and *this* faction and *this* arc — not to the global wolf pool — and (c) the loot pouch they pry off the corpse fitting the world that produced it.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

Player crests a low ridge on the salt moors. Two riders on caked ponies emerge from a draw. They wear boiled-copper mail, swinging short weighted whips. They split — one harrier, one finisher. They charge in pairs, the harrier disengages when the player rotates to face it, the finisher commits. When the player kills the finisher, the harrier breaks contact and rides for the rise. They drop strips of moors_copper and a copperlash_gash skill-shard the player can attach to a future weapon.

That is the thing. Everything we generate — stats, AI behavior, drops, attacks, abilities, narrative, tags — exists so the player can name three properties of this enemy after one encounter:

- **Who** they are (Copperlash Riders, of the moors raider line).
- **Where** they belong (only the salt moors, only the copper road).
- **Why** they're here right now (the copper trade is breaking, and they're working the road harder than they used to).

The templated baseline gives the player "two humanoid enemies, tier 2." We have to clear that bar by enough that the player picks the name up off the corpse, not the loot.

### 1.2 Timing budget — when does the LLM fire?

Hostile generation is **not** a runtime call during combat. Combat tolerates zero LLM latency. The hostile JSON must already exist on disk before the chunk spawns, before the player walks into the chunk, before the encounter starts.

User direction (gold-standard quote from quests, applied to hostiles): *"running it live is impossible. So instead upon calls we make the [hostiles] and store them for the seamless experience."*

This dictates:

- `wes_tool_hostiles` fires during cascade time (post-WNS, before commit). The cascade can take 5-30 seconds — fine, no player is waiting.
- The committed JSON lives on disk in `Definitions.JSON/hostiles-generated-<timestamp>.JSON` and gets loaded by `EnemyDatabase` either on game restart or via a `reload()` method.
- **Today this is broken.** Per `DESIGNER_LEDGER.md` line 37: "Five content types can't hot-reload. Generated materials, hostiles, nodes, skills, and titles land on disk but the in-game database doesn't see them until restart." `EnemyDatabase` has no `reload()` method (confirmed by grep on `Combat/enemy.py`). This is the single largest infrastructure gap for hostile playtesting today — see §7.
- The chunk that spawns the enemy must reference the enemy by `enemyId` in its `enemySpawns` block, which means **the chunk's commit must postdate the hostile's commit OR the chunk and hostile must commit in the same plan**. The planner's DAG (see §4.6) handles the latter via `depends_on`.

The hostile lifecycle is: **generate at cascade → commit to disk → reload database → chunk dispatches at world-gen → CombatManager pulls from chunk's enemy spawn pool → encounter fires**. Latency is masked across the entire chain by the fact that the player isn't there yet.

### 1.3 Failure modes — what BAD looks like

**(a) Slop.** "A T2 humanoid bandit type. Health 200, damage 18-28. Drops 1-3 of some_ore. Knows leap_attack." The bandit has no name, no faction, no locale, no narrative. Two of them spawn next to a dragon and three slimes because the chunk pool is just a tier-tag-match. *(Defense: thread WNS narrative + locality + faction into the spec. The hub MUST stamp specific `prose_fragment` text. The tool MUST write a 2-3 sentence narrative that names the locale.)*

**(b) Stagnant predictability.** Every region has wolves, slimes, bandits, beetles. The player walks from the salt moors to the cursed marsh and the only thing that changes is the tint of the wolf sprite. *(Defense: biome-coherent species rotation, faction-aligned humanoid variants, abilities sourced from the 21-ability library biased by category × tier × narrative tone. Most importantly: the hub must see the recent_hostile_registry and avoid stacking same-category/same-tier enemies.)*

**(c) Craziness.** The tropical-pelican-with-a-flamethrower in a snowy forest. The LLM, ungrounded, invents a "Salt-Drowned Wyrm-Mantled Reaver-Pelican" in a region that has no wyrms, no pelicans, and is a moor. The tool also invents an ability `wing_burst` that doesn't exist, references a `salt_dragon_scale` material the registry doesn't carry, and emits tier=3 stats in a tier-2 plan step. *(Defense: ABILITY LIBRARY allow-list (21 entries — tool prompt enforces "do NOT invent abilities"); ecosystem coherence via biome tag in `hard_constraints`; orphan detector rejects unknown material drops; tier stat bands soft-enforced ±20%; tag allow-list with NEW: prefix surface for designer review.)*

**(d) Disconnected from the WNS narrative.** WNS NL4 just spent six fragments on "the salt moors restructuring around copper" and `<WES purpose="new-hostile">` fired. The tool emits a generic "T2 humanoid bandit" with no copper-flavor, no moors-flavor, no awareness that the narrative spent six fragments naming the copper trade. *(Defense: same as quests — the `BundleToolSlice.parent_summaries` leak at `context_bundle.py:342-370` strips the regional narrative before it reaches the hub, never mind the tool. Agent 1 flagged this as the single highest-leverage cross-tool bug. It hits hostiles equally hard — possibly worse, because hostiles are more deeply ecosystem-bound than quests.)*

**(e) Ecosystem-incoherent drops.** A wolf drops `salt_crystal`. A slime drops `moors_copper`. A dragon drops `wolf_pelt`. This breaks the player's mental model of the food chain. The combat loop loses meaning — kills stop teaching the player about the world. *(Defense: the hub's `cross_ref_hints.drop_material_ids` MUST be locality-relevant, drawn from materials co-emitted in the plan or already registered at the firing address. Generic materials like `wolf_pelt` are fine for `species:wolf` enemies; they break when applied to ooze/aberration/dragon.)*

**(f) Combat-feel incoherent.** A dragon with 60 HP, a slime with 1.6 movement speed, a bandit with 800 HP. The stat bands exist in the tool prompt as soft guidelines — when the LLM ignores them, the encounter feels wrong even if the JSON validates. *(Defense: tier stat bands enforced ±20% in the schema validator; category implies movement archetype via `attack_profile_generator.py`; the hub must constrain tier in `hard_constraints` from the planner's `step.slots.tier`.)*

### 1.4 What "good" actually looks like

Player after one hour of moors play: *"The Copperlash Riders are pair-ambushers — one harries, one finishes. They only show up on the copper road in the salt moors and they drop moors_copper. I learned the copperlash_gash skill off them. They're working for someone — there's a captain who hates them now, I think because they killed his brother."*

Four properties:

- **Causally legible** — the player can name why this enemy exists in this place at this time.
- **Encounter-distinct** — the AI pattern + attack profile + ability has a *feel* the player can describe (pair-ambush, harasser/finisher).
- **Ecosystem-coherent** — drops fit, locale fits, faction fits.
- **Loot-meaningful** — the materials/skills they drop teach the player about the world, not just stat-pad their inventory.

---

## 2. Output artifact schema completeness audit

The static `EnemyDefinition` shape is fixed in `Combat/enemy.py:92-122` and load logic at `EnemyDatabase.load_from_file` (lines 192-300). Every field below must be filled by `wes_tool_hostiles` OR derived deterministically post-commit by `attack_profile_generator.py`.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `enemyId` | str (snake_case) | `wes_tool_hostiles` | Must encode locality + species/role. `copperlash_rider` beats `bandit_002`. Unique against registry. |
| `name` | str (Title Case) | `wes_tool_hostiles` | Evokes the locale's voice. "Copperlash Rider" beats "Bandit." |
| `tier` | int 1-4 | Hub `hard_constraints.tier` | Drives stat bands and visual_size. Must match planner step's `slots.tier`. |
| `category` | str (one of 9) | Hub `hard_constraints.category` | beast / ooze / insect / construct / undead / elemental / aberration / humanoid / dragon. Drives `attack_profile_generator` archetype and visual_size base. |
| `behavior` | str (one of 8 preferred) | Hub `hard_constraints.behavior` | passive_patrol / aggressive_pack / aggressive_swarm / aggressive_phase / boss_encounter / stationary / docile_wander / territorial. Drives attack tempo modifier. |
| `stats.health` | int | `wes_tool_hostiles` | Within ±20% of tier band. T2 = 120-250. |
| `stats.damage` | [int, int] | `wes_tool_hostiles` | Within tier band damage range. Two-int array MIN < MAX. |
| `stats.defense` | int | `wes_tool_hostiles` | Within tier band. Combat damage pipeline caps at 75% reduction. |
| `stats.speed` | float | `wes_tool_hostiles` | 0.5-1.6 typical. Category implies tempo (insect fast, construct slow). |
| `stats.aggroRange` | float | `wes_tool_hostiles` | 3-20 typical. Tier-correlated. |
| `stats.attackSpeed` | float | `wes_tool_hostiles` | 0.6-1.5 typical. |
| `drops[]` | List[Dict] | `wes_tool_hostiles` + Hub `cross_ref_hints.drop_material_ids` | 1-4 entries. Each material MUST cross-ref existing or co-emitted. `quantity` is two-int array (not qualitative — unlike nodes). |
| `drops[].materialId` | str | Cross-ref | Resolves to committed material or co-emitted in plan. Orphan detector blocks otherwise. |
| `drops[].quantity` | [int, int] | Tool | Tier-correlated. T1 = small, T4 = large. |
| `drops[].chance` | str | Tool | guaranteed / high / moderate / low. |
| `aiPattern.defaultState` | str | Tool | idle / wander / patrol / guard. Behavior-correlated. |
| `aiPattern.aggroOnDamage` | bool | Tool | Almost always true. Exception: bosses with phases. |
| `aiPattern.aggroOnProximity` | bool | Tool | Behavior-correlated. docile=false, aggressive=true. |
| `aiPattern.fleeAtHealth` | float 0-1 | Tool | 0 = never flee. Bosses always 0. Common enemies 0.1-0.3. |
| `aiPattern.callForHelpRadius` | float | Tool | 0 = solo. Pack enemies 8-20. Swarm enemies 5-12. |
| `aiPattern.packCoordination` | bool (optional) | Tool | True iff behavior is `aggressive_pack` or `boss_encounter` with adds. |
| `aiPattern.specialAbilities[]` | List[str] | Hub `flavor_hints.specialAbilities_hint` | MUST be from the 21-ability library. Tool refuses to invent new. |
| `skills[]` | List[str] (top-level) | Hub `cross_ref_hints.known_skills` | Optional. xref tracking. Empty acceptable. |
| `metadata.narrative` | str (2-3 sentences) | Tool | The LITERAL voice of who-they-are. "Moors raiders in boiled-copper mail, swinging short weighted whips from the backs of salt-caked ponies. They ride in pairs, one harrier and one finisher, and they break contact the moment numbers go against them." This field is the player's mental model anchor. |
| `metadata.tags[]` | List[str] (3-6) | Tool | From `TAG ALLOW-LIST` in tool prompt. NEW: prefix for designer review. Drive WMS retrieval + visual filters + chunk spawn pool. |
| `iconPath` | str (optional) | Loader auto-generates | `enemies/<enemy_id>.png` fallback if absent. |
| `attacks[]` (EnemyAttackDef) | List | NOT LLM-authored | Procedurally derived from category + tier + behavior + abilities by `attack_profile_generator.py`. Tool does NOT emit this. |
| `visual_size` | float (computed) | NOT LLM-authored | Computed from category × tier. 1.0-8.0. |
| `hurtbox_radius` | float (computed) | NOT LLM-authored | `visual_size × 0.4`. |

### 2.1 Schema completeness — what's MISSING

This is a `[WES-SCHEMA-GAP]` audit. The fields the design calls for that the v4 schema doesn't carry:

- `[WES-SCHEMA-GAP]` **`encounter_context` block.** The hostile JSON today has no structured "where does this enemy belong" field. Locality, biome, faction belonging, and ecological role (predator/prey/scavenger/sentient) all live implicitly in `metadata.tags` + `metadata.narrative`. This is good enough for combat but terrible for downstream queries: chunks can't filter "give me only enemies belonging to faction:moors_raiders," quests can't know "is this enemy part of an active arc?" Recommendation: add an `encounter_context: {biomes: [str], factions: [str], ecological_role: str, native_locality_ids: [str], wns_thread_id: str}` block. Backfill on existing sacred enemies as `biomes: ["forest", "wetland"], factions: [], ecological_role: "beast"`.
- `[WES-SCHEMA-GAP]` **`wns_thread_id`** — the narrative thread this enemy belongs to. Same continuity hook quests have. When the moors-copper thread closes, the runtime should know which generated enemies belong to that thread (for retirement, evolution, or archival flavor — see §9). Today: no link.
- `[WES-SCHEMA-GAP]` **`hunted_by_quest_ids[]`** — Agent 1's reciprocal cross-ref. When a quest's `objectives.objective_type=kill_target` references this enemy, the link should land on the enemy too so future WNS firings can read "this enemy is currently being hunted by an active quest, lean into the vendetta tone." Today: not stored on the enemy side.
- `[WES-SCHEMA-GAP]` **`emergent_proper_nouns[]`** — when the LLM coins a proper noun (e.g. "the Salt-Drowned" as a faction the enemy belongs to), that noun should be promoted to the registry so future generations can re-use it. Per WNS `emergent_entity` rule: 2 per fragment, 5 per run, designer review surface. Currently the noun lives inside the `narrative` string with no extraction layer.
- `[WES-SCHEMA-GAP]` **`engagement_pattern` summary.** What's the *feel* of fighting this enemy? "pair-ambush, harasser/finisher" or "stationary turret, slow heavy" or "swarm-overwhelm." Today this is implicit in (behavior + abilities + attacks). For tag-indexed retrieval ("give me a swarm-style T2 enemy"), an explicit `engagement_pattern: str` tag from a 6-10-entry allow-list would help. Probably worth deferring to a v2 schema bump.
- `[WES-SCHEMA-GAP]` **`drops_lore[]`** prose hints. The drops field is mechanical (`materialId`, `qty`, `chance`). The lore — "why this enemy yields this material" — lives only in `metadata.narrative`. A `drops[].lore_hint: str` field would let the renderer or quest dialogue say "the moors_copper strips were lashed to its bridle." Optional polish.
- `[FRAGMENT-GAP]` **The hub's `cross_ref_hints` does not currently carry the giving NPC's faction tag.** When the planner co-emits an NPC who *uses* these enemies as their faction's force (Captain Vell commands Copperlash Riders), there's no slot for "give this enemy faction:moors_raiders affinity." Add `cross_ref_hints.faction_affinity_tag: str`.
- `[FRAGMENT-GAP]` **The tool's prompt does not currently receive the giver NPC's narrative.** Same as quests' problem — when the spec is "hostile aligned with Captain Vell of the moors raiders," the tool needs the captain's voice/personality/grievance to flavor the enemy. Add `${giver_npc_voice_excerpt}` to the user_template when a faction NPC is co-emitted.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent procedural enemy generator (no LLM) emits given (tier, category, biome):

```json
{
  "enemyId": "bandit_004",
  "name": "Bandit",
  "tier": 2,
  "category": "humanoid",
  "behavior": "aggressive_swarm",
  "stats": {
    "health": 180,
    "damage": [22, 30],
    "defense": 14,
    "speed": 1.2,
    "aggroRange": 7,
    "attackSpeed": 1.1
  },
  "drops": [
    {"materialId": "iron_ore", "quantity": [1, 2], "chance": "moderate"},
    {"materialId": "cloth", "quantity": [1, 1], "chance": "low"}
  ],
  "aiPattern": {
    "defaultState": "patrol",
    "aggroOnDamage": true,
    "aggroOnProximity": true,
    "fleeAtHealth": 0.2,
    "callForHelpRadius": 8,
    "specialAbilities": []
  },
  "metadata": {
    "narrative": "A bandit. Aggressive and dangerous.",
    "tags": ["humanoid", "aggressive", "mid-game"]
  }
}
```

This is fine. This is also exactly what we lose to. The player can't name where this bandit lives, who they work for, what they want, or why they're here right now. Five sessions in, every region's bandits feel the same.

### 3.2 What the LLM has to add — field by field

1. **`enemyId`** — needs to encode locality + role. `copperlash_rider` beats `bandit_004`. Needs `directive_text` (intent) + `address_hint` (locale) + `recent_registry_entries` (for uniqueness check).
2. **`name`** — taste of the locale. "Copperlash Rider" beats "Bandit." Needs the chunk's biome flavor + the WNS thread's tone + (when present) faction affiliation prose.
3. **`category` selection** — should be coherent with WNS arc. A copper-trade arc breeds humanoid raiders, not aberrations. A cursed-marsh arc breeds undead and aberrations, not beasts. Today the hub picks; should be driven by WNS narrative_context.
4. **`behavior` selection** — coherent with role. Raiders pack-ambush. Beasts territorial-wander. Constructs stationary-guard. Should be informed by narrative tone — a `tone:ominous` thread breeds aggressive behavior, `tone:mundane` breeds passive/docile.
5. **`stats` weighting** — stay in tier band but bias by behavior. A pack-ambusher should lean lower-HP-higher-damage-faster-speed. A boss-encounter should lean high-HP-moderate-damage-low-flee. The tool's stat bands today are too coarse — see §4.4.
6. **`drops` cross-refs** — material IDs MUST be locality-relevant. A moors raider drops `moors_copper`, not `iron_ore`. A salt-drowned undead drops `essence_blood` + `salt_crystal`. Driven by `cross_ref_hints.drop_material_ids` from the hub, which should come from the plan's co-emitted materials OR the registry's locality-filtered material set.
7. **`aiPattern.specialAbilities`** — from the 21-ability library. Tool MUST refuse to invent. The library is currently locked — see §9 for proposed expansion path. Pack enemies suggest `howl_buff` + `leap_attack`. Boss enemies suggest `earthquake_stomp` or `ground_slam`. Aberrations suggest `phase_shift` or `reality_warp`. Driven by `flavor_hints.specialAbilities_hint`.
8. **`metadata.narrative`** — the load-bearing field. 2-3 sentences naming appearance, behavior, threat. This is where ALL the WNS-context-leakage shows up if §4.4 isn't fixed. Without the WNS parent narrative, the tool writes "a bandit who fights aggressively"; with it, the tool writes "moors raiders in boiled-copper mail, swinging short weighted whips from the backs of salt-caked ponies."
9. **`metadata.tags[]`** — from the allow-list. NEW: prefix for designer review. Tags drive WMS retrieval, chunk spawn pools, visual filters, and quest cross-refs. Tag diversity is itself a diversity dial — see §8.

The delta is: **locality-rooted naming, narrative-grounded behavior selection, ecosystem-coherent drops, and ability selection that respects the locked library while still flavoring per arc.** Three load-bearing properties.

---

## 4. Backward trace through the pipeline

### 4.1 Rung 0 — Encounter fires (player-facing)

Consumes: the `Enemy` runtime instance, spawned by `CombatManager._maybe_spawn_chunk_enemies` against `ChunkTemplate.enemy_spawns` weighted pool. The `EnemyDefinition` is pulled from `EnemyDatabase.enemies[enemy_id]`.
Emits: WMS `enemy_killed` event when the player kills it (via `StatTracker.record_enemy_killed`), `damage_taken` events when it hits the player, `enemy_ability_used` (not currently emitted — see §5).
Risk: if `EnemyDatabase` hasn't loaded the generated hostile (because `reload()` doesn't exist — see §1.2 and §7), the chunk's `enemySpawns` reference to `copperlash_rider` falls through and the chunk gets default-tier enemies instead. **This is the single biggest runtime gap for hostile playtest today.**

### 4.2 Rung 1 — Chunk spawn dispatch (post-commit, world-gen)

`CombatManager` reads `ChunkTemplate.enemy_spawns` (a dict of `{enemy_id: EnemySpawnSpec}` with density + tier). Spawn weights derive from `DENSITY_WEIGHTS` (very_low=0.5, moderate=1.0, very_high=3.0).

Risk: the **chunk template must reference the enemy ID for the enemy to spawn**. If the planner emits a hostile step without a chunk step that references it, the enemy lives in `EnemyDatabase` but never appears in the world. The planner example in `prompt_fragments_wes_execution_planner.json:example` correctly co-emits chunk-with-enemy refs (`primary_enemy_ids: ["copperlash_rider"]`). This must hold in real plans.

`[FRAGMENT-GAP]` **Chunk-hostile co-emission discipline.** Today the planner CAN emit hostiles without an accompanying chunk (acceptable when the enemy is meant to populate an existing chunk type). But there's no postcondition check that "every committed hostile lands in at least one chunk template that references it within N firings." Without this, hostiles can land on disk and never spawn. Recommend: `ContentRegistry` audit pass on commit — warn if a hostile has no chunk reference. Designer task, not LLM task.

### 4.3 Rung 2 — `wes_tool_hostiles` (one ExecutorSpec → one hostile JSON)

Inputs (from `prompt_fragments_tool_hostiles.json` `user_template`):
- `spec_id`, `plan_step_id`, `item_intent` (the hub-authored prose: "moors raider riding salt-caked pony, weighted whip-line ambusher working the copper road in pairs"), `hard_constraints` (tier, category, behavior, biome, role), `flavor_hints` (name_hint, prose_fragment, thematic_anchors, specialAbilities_hint, drop_intent), `cross_ref_hints` (drop_material_ids, known_skills).

Output: one `EnemyDefinition` JSON.

What's MISSING:

- `[WES-SCHEMA-GAP]` **The bundle's narrative context never reaches the tool.** Same `BundleToolSlice.parent_summaries` leak (`living_world/infra/context_bundle.py:342-370`) that hits quests. The tool's `user_template` has NO `${narrative_context}` slot — the only narrative trace is `flavor_hints.prose_fragment` and `item_intent`, both of which are hub-condensed strings. The full WNS NL4 region narrative ("the salt moors are restructuring around copper trade and the raiders ride harder") never reaches the tool. **Result: hostiles disconnected from WNS narrative (failure mode 1.3.d).** Fix: add `${narrative_context}` and `${parent_narrative_excerpt}` slots; have hub thread them through `flavor_hints.narrative_excerpt`; OR pass the full BundleToolSlice with parent narrative preserved. **This is Agent 1's seed fix from quests — solve once, benefit eight features.**
- `[FRAGMENT-GAP]` **No faction-affinity slot.** When the spec is "this enemy belongs to faction:moors_raiders," the tool prompt has no variable for it. The narrative ends up flavor-coherent if the prose_fragment mentions raiders, but the ENEMY JSON has no faction tag. Faction belonging is currently only inferrable from the loose `metadata.tags` list. Add: `${faction_belonging}` slot + tool emits `metadata.tags` with `faction:moors_raiders`.
- `[FRAGMENT-GAP]` **No co-emitted-NPC voice slot.** When the planner co-emits Captain Vell who *commands* the copperlash riders, the tool has zero access to Vell's voice/personality. The result: the enemy narrative reads "a moors raider" but never references the captain's grievance or the chain of command. Add: `${commander_npc_voice_excerpt}` when faction has a leader NPC in the plan.
- `[FRAGMENT-GAP]` **No co-emitted-material flavor slot.** The hub passes `cross_ref_hints.drop_material_ids: ["moors_copper"]` but the tool has no access to the material's own `narrative` (rust-veined, acid-resistant). So the enemy narrative can't say "their whips wound with rust-vein cuts that resist healing." Add: `${drop_material_excerpts}` when materials are co-emitted.
- `[FRAGMENT-GAP]` **No ability-library description excerpts.** The tool prompt lists ability IDs by one-liner. When the LLM picks `leap_attack`, it doesn't see the full effect parameters (35 base damage, 6s bleed, 5 DPS). Result: the narrative might describe the ability inconsistently with the actual effect (e.g., narrating a "wild charge" when the ability is actually a pounce-and-bleed). Add: `${selected_abilities_descriptions}` block that expands the hub-suggested abilities.
- `[FRAGMENT-GAP]` **Recent-encounter signals not in input.** The hub gets `recent_registry_entries` for diversity. The tool doesn't see same-tier-same-region enemies for stat/role/drop differentiation. A T2 humanoid raider in the moors should not duplicate the stats and ability of a previously-committed T2 humanoid in the same region. Add: `${neighbor_enemies_summary}` (compact: id + role + abilities + drops for the nearest 3-5 same-tier same-biome enemies). 200-char budget.
- `[FRAGMENT-GAP]` **No ecosystem-role variable.** A region needs predators, prey, scavengers, sentients. Today the planner picks category without considering ecosystem balance. The tool gets `category` and `behavior` but no signal about whether this enemy is *filling a gap* (no scavengers in this region) or *adding to an over-served niche* (six predators already). Add: `${ecosystem_role_signal}` — derived deterministically from the registry's per-region census. Designer-tunable.

### 4.4 Rung 3 — `wes_hub_hostiles` (one plan step → batch of ExecutorSpecs)

Inputs (`prompt_fragments_hub_hostiles.json` `user_template`):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "moors raider riding salt-caked pony, ambushes copper road in pairs, drops moors copper, knows copperlash gash" and decomposes it into 1+ ExecutorSpecs with `hard_constraints` / `flavor_hints` / `cross_ref_hints` per spec.

What's MISSING:

- `[WES-SCHEMA-GAP]` **`BundleToolSlice` parent narrative leak (same as 4.3).** Hub receives the slice that strips parent narrative. The hub's `directive_text` survives, but the NL3/NL4/NL5 cascading narratives are gone. The hub authoring `prose_fragment` for the tool has nothing but the directive to work with. This compounds at the tool layer: if hub already lost the context, the tool's filtered view through `flavor_hints` is fundamentally limited.
- `[FRAGMENT-GAP]` **`recent_registry_entries` shape isn't tier-stratified.** The hub gets a flat list of recent hostiles. For diversity, it needs to see "the last 5 T2 hostiles in this region" specifically, not "the last 20 hostiles globally." The slice should be tier × biome filtered. The signature accepts it as parameter (line 369 of `context_bundle.py`) but caller must populate from `ContentRegistry`. Verify wiring; if not present, add.
- `[FRAGMENT-GAP]` **No category-distribution awareness.** The hub should see "the moors already has 3 beasts and 1 humanoid; you're being asked to add another humanoid — consider differentiating sharply." Today: no such signal. Recommendation: extend `recent_registry_entries` with a `category_counts_in_biome: {beast: 3, humanoid: 1, ...}` block.
- `[FRAGMENT-GAP]` **No locked-ability hint expansion.** The hub's `flavor_hints.specialAbilities_hint` is a list of IDs. The hub prompt's domain guidance describes the 21-ability library by one-liner. If the hub wants to flavor "this enemy uses lifesteal abilities" it has no full effect-description corpus to reason against. Tool prompt has the same problem (4.3 above). The fix is the same: expand ability descriptions in both prompts. Or maintain a single `${ability_library_descriptions}` fragment included in both.

### 4.5 Rung 4 — `wes_execution_planner` (one bundle → one plan DAG)

Inputs (`prompt_fragments_wes_execution_planner.json`):
- `bundle_id`, `firing_tier`, `firing_address`, `bundle_directive`, `bundle_narrative_context`, `bundle_delta`, `thread_headlines`, `registry_counts`.

Scope rules (from prompt): hostiles allowed at Tier 1 (1 minor hostile), Tier 2 (1-2 of [material, node, hostile, skill]), Tier 3 (1-2 of [material, node, hostile, skill, title] + 1 NPC), Tier 4 (cross-tool sets including chunks).

What's MISSING:

- `[FRAGMENT-GAP]` **Geographic chain isn't surfaced to the planner.** The bridge (`wns_to_wes_bridge.py`) builds `scope_hint.geographic_chain` from region→province→nation, but the planner's `user_template` only sees `firing_address` and `firing_tier`. For hostile planning the geographic descriptor matters — "this enemy belongs to the salt moors" vs "this enemy belongs to the coast marches" tips behavior. Add: `${scope_hint}` slot with the geographic chain.
- `[FRAGMENT-GAP]` **`bundle_narrative_context` shape — is the relevant WNS layer's narrative actually populated?** Planner prompt does have this slot, but the bridge's contents need verification. If the bundle's narrative_context drops the WNS NL4 region narrative when firing tier is 4 (it shouldn't, but the slice leak suggests it might), then the planner picks scope/tools without the narrative grounding. Audit.
- Tier 1-2 scope rules forbid NPCs/quests/chunks. For hostiles, this means: a tier-1 firing can create ONE hostile but can't simultaneously create the chunk that hosts it or the NPC that hates it. **This is fine** — small-scope content additions stay scoped. But it means hostiles created at tier 1-2 are most at risk of becoming orphans (no chunk references them, no faction NPC commands them). Recommendation: a planner postcondition: "if you're creating a hostile at tier 1-2, you must justify which existing chunk hosts it." Lives in the planner prompt as a discipline rule.

### 4.6 Rung 5 — WNS NL3-NL7 weaver emits `<WES purpose="new-hostile">`

Per `narrative_fragments_nl4.json:_wes_tool` (lines 19), `new-hostile` is one of 7 purpose buckets at NL4 (region scope). Example body from the fragment: *"A tier-2 humanoid raider type for the moors - copperlash riders working in pairs, dropping moors_copper. Knows skills copperlash_gash and ambush_call."*

This is GOOD prose — names tier, category, biome, drops, skills. When the WNS produces this body, the planner has everything it needs.

What's MISSING:

- `[WNS-GAP]` **Firing guidance per layer is generic.** Hostiles can fire at NL3 (district scope, with `new-hostile` allowed), NL4 (region scope, common), NL5+ (broader). The firing fragments don't say WHEN specifically to fire `new-hostile`:
  - When a region's narrative shifts to martial / criminal / industrial domain and existing hostiles don't carry the shift (new threat type needed).
  - When a faction's territory expands and the faction's enemies don't yet exist in the new biome.
  - When the player's combat profile diversifies (the WMS `combat_style` evaluator shows they're farming the same 3 enemy types).
  - When a chunk is being created that has no existing hostiles for its biome.
  The current prose says "a tier-appropriate enemy archetype tied to the arc" — vague. *(Designer task: tune `_wes_tool` body for each layer with specific firing triggers per purpose-bucket.)*
- `[WNS-GAP]` **Directive_text shape isn't enforced.** Some weavers will emit "A new monster for the region." (slop). Others will emit the moors raider example (well-grounded). The fragment should TELL the weaver: name tier, category-hint, biome, ecological role, hostility level, expected drops, and (optional) faction belonging. *(Designer task: extend the `_wes_tool` example with multiple flavor variants.)*

### 4.7 Rung 6 — WNS reads WMS L2 interpretations

The `${wms_context}` budget (600 char) carries recent L2 interpretations including kill counts, area danger, population shifts, boss kills, combat damage regional. For hostile-relevant signals all the needed evaluators exist:

- `combat_kills_regional_low_tier.py` and `combat_kills_regional_high_tier.py` — "Player has killed N <enemy> in <region>" — fuels the WNS "the moors are quiet of riders" or "the riders are thick" interpretations.
- `combat_boss_kills.py` — "Player has defeated <boss> in <region>" — fuels "vendetta" or "champion" themes for downstream hostile/quest generation.
- `combat_damage_regional.py` — "Player nearly died N times in <region>" — fuels "this region is dangerous" themes that can lead to "a new threat emerged" `<WES purpose="new-hostile">`.
- `combat_style.py` — global dodge/status/attack counts — informs the WNS "the player favors X playstyle" reads.
- `population.py` — "Player has killed N <enemy> in <region>" with different thresholds — fuels regional population shifts.
- `area_danger.py` — combined damage+death threat score per region — same as combat_damage_regional but with death weighting.

Solid coverage. The WMS chronicler-voice signals for hostile dynamics are present.

### 4.8 Rung 7 — WMS L1 events recorded

The L1 events that drive all of the above: `enemy_killed`, `damage_taken`, `player_death`, `attack_performed`, `dodge_performed`, `status_applied`. `StatTracker.record_enemy_killed` (line 307) records with dims: tier, species, rank (boss/dragon), weapon_element, location.

`[WMS-ENHANCEMENT]` **`enemy_ability_used` event.** Currently, when an enemy uses one of its 21-library abilities, no WMS event records it. The system can know "player killed wolves" but not "player has been hit by 6 howl_buff effects this region." For evaluators measuring "the player's tactical adaptation to ability sets" this is a future enrichment. NOT a blocker — solid playtest can launch without it.

`[WMS-ENHANCEMENT]` **`enemy_fled` event.** When `fleeAtHealth` triggers and an enemy escapes, no event records it. For WNS narratives like "the riders break contact more often now — they fear the road" this would be useful. NOT a blocker.

`[WMS-ENHANCEMENT]` **`enemy_first_encountered` event.** When the player encounters a generated enemy for the first time, an event would let the WNS write a "first sighting" thread headline. Not in scope for v4 launch.

---

## 5. Per-field provenance table

For EVERY field the LLM authors, where the upstream signal comes from. The 9-rung WMS column is walked only when a `[WMS-GAP]` is tempting (one case — see §5.1).

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `enemyId` | Tool + hub `flavor_hints.name_hint` + uniqueness check against `recent_registry_entries` | Hub crafts from `step.intent` + `address_hint` | Yes | — |
| `name` | Tool + `flavor_hints.name_hint` | Same as enemyId | Yes | — |
| `tier` | Hub `hard_constraints.tier` | Planner `step.slots.tier` | Yes | — |
| `category` | Hub `hard_constraints.category` | Planner `step.slots.category`; if absent hub picks from narrative tone + biome | Yes | — |
| `behavior` | Hub `hard_constraints.behavior` | Hub picks from 8 based on `step.intent` + `step.slots.role` | Yes | — |
| `stats.health/damage/defense/speed/aggroRange/attackSpeed` | Tool, within tier band | Tool's own stat sizing within `TIER STAT BANDS` table in prompt | Yes — but bands are coarse; biased only by tier | `[FRAGMENT-GAP]` — bands should also vary by category (insect leans low-HP-fast, construct leans high-HP-slow). Could be added to the prompt as a category × tier matrix. |
| `drops[].materialId` | Cross-ref hint | `cross_ref_hints.drop_material_ids` from hub; hub draws from planner `step.depends_on` materials + registry's biome-relevant materials | Partial — hub_dependency_resolution.md describes a "reactive trigger upstream tool when refs missing" pattern but it's not yet implemented. Today: planner must pre-list materials in `step.depends_on` OR orphan-detector blocks. | `[FRAGMENT-GAP]` — orchestrator-level wiring. Per memory `hub_dependency_resolution.md`, recursive dep resolution is future work. |
| `drops[].quantity` | Tool | Tier × narrative weight | Yes | — |
| `drops[].chance` | Tool | Tier × material rarity inference | Yes | — |
| `aiPattern.defaultState` | Tool | Tool's own pick from 4-entry allow-list, behavior-correlated | Yes | — |
| `aiPattern.aggroOnDamage` | Tool | Tool's own pick; default true | Yes | — |
| `aiPattern.aggroOnProximity` | Tool | Tool's own pick; behavior-correlated | Yes | — |
| `aiPattern.fleeAtHealth` | Tool | Tool's own pick; behavior-correlated (boss=0, common=0.1-0.3) | Yes | — |
| `aiPattern.callForHelpRadius` | Tool | Tool's own pick; behavior-correlated | Yes | — |
| `aiPattern.packCoordination` | Tool | Tool's own pick; true iff behavior=aggressive_pack or boss_encounter | Yes | — |
| `aiPattern.specialAbilities[]` | Hub `flavor_hints.specialAbilities_hint` (suggestion) + tool enforces from 21-library | Hub picks from library based on category + behavior + narrative tone | Yes — library is locked | — |
| `skills[]` (top-level) | Hub `cross_ref_hints.known_skills` | Planner co-emits skill steps when relevant | Yes | — |
| `metadata.narrative` | Tool | `item_intent` + `flavor_hints.prose_fragment` + (MISSING) `${narrative_context}` + `${commander_npc_voice}` | Partial — narrative_context is the leak | `[WES-SCHEMA-GAP]` — see §4.3 / §4.4. The single highest-leverage fix. |
| `metadata.tags[]` | Tool | Tool picks 3-6 from allow-list (40+ entries). NEW: prefix for designer review. | Yes — locked allow-list | — |
| `iconPath` | Loader auto-generates | Fallback `enemies/<id>.png` | Yes | — |
| `attacks[]` (EnemyAttackDef) | NOT LLM-authored — `attack_profile_generator.py` derives | Category × tier × behavior × abilities | Yes — procedural | — |
| `visual_size` | NOT LLM-authored — `enemy.py:visual_size` | Category × tier (table at lines 129-147 of enemy.py) | Yes — procedural | — |
| `hurtbox_radius` | NOT LLM-authored | `visual_size × 0.4` | Yes — procedural | — |

### 5.1 WMS-GAP walk — the one place I was tempted

The one piece of context I almost flagged `[WMS-GAP]` for: **regional ecosystem census** — "what's already in the moors? What predator/prey/scavenger niches are filled? What's missing?" so the planner can pick a category that fills a gap rather than over-serving a niche.

Walk the 9 rungs:

1. **Direct query**: Is there a WMS "ecosystem_census" event or evaluator? **No.** Fail.
2. **Adjacent events**: WMS records `enemy_killed` with species dim. `event_store.query(event_type='enemy_killed', locality_id='salt_moors', group_by='species')` returns species kill counts in the moors. **Yes** — this is the cleanest signal for "which enemies are actually being encountered in this region."
3. **Negative patterns**: Are there species the player has NEVER encountered in this region? `entity_registry` knows which enemy types exist; cross-reference against `event_store` enemy_killed query. The set of "enemies that exist in registry tagged biome:moors but have zero kills" is the under-served set. **Yes.**
4. **Aggregation**: `daily_ledger.unique_enemy_types_fought` aggregates species diversity per day. `combat_kills_regional_low_tier` and `_high_tier` produce per-region kill narratives per species. Combine: "the moors have 3 active species with kills, all beast category" = under-served humanoid/aberration/etc.
5. **Trajectory**: `population.py` evaluator builds severity bands on kill counts. Reading recent population shifts ("crystal_slime kills moderate in salt_moors") tells the planner the ecosystem is bending toward elemental — maybe the next addition should be a counter-niche.
6. **Cross-layer climb**: NL4 region narratives may interpret ecosystem shifts ("the moors are emptying of beasts; only the iron-bones remain"). If the bundle's `narrative_context` lands intact (post-leak-fix), this is readable.
7. **Cross-entity composition**: Combine `ContentRegistry` enemy roster (filtered by biome tag) + `event_store` kill counts (filtered by locality) = the registered-vs-active matrix. The gaps in this matrix = ecosystem niches.
8. **Stat / ledger lookup**: `StatStore` has `combat.kills.species.<species>.location.<location>` dims via `record_enemy_killed`'s `build_dimensional_keys`. Querying for per-region species counts is a direct lookup.
9. **Trigger history**: When `<WES purpose="new-hostile">` fires, the planner can read which categories have been added in the last N firings via `recent_registry_entries`. If recent_registry shows 4 beasts in a row in the moors, the planner picks humanoid.

**Verdict**: NOT a WMS gap. The signal is available through (2) + (3) + (7) + (8) — registry-filtered census + WMS-derived activity census. The actual gap is at the **planner/hub prompt input layer** — neither prompt has a slot for `${biome_category_census}` or `${biome_ecological_gaps}`. Marker: `[FRAGMENT-GAP]` on the planner + hub prompt inputs, not `[WMS-GAP]`. Fix: assemble `category_counts_in_biome` deterministically in code from registry + event_store and thread it through.

**Zero `[WMS-GAP]` markers in this trace.** WMS substrate is complete for hostile-relevant signals. Gaps are at the WNS→WES boundary (bundle leak), at the prompt input layer (variables not threaded), and at the WES schema layer (missing fields like `encounter_context` and `wns_thread_id`).

---

## 6. Cross-references with other features (personal shopper)

### 6.1 Heavy shared infrastructure (use as-is)

- **WNS NL3-NL5 narrative weavers** — shared with every content tool. Hostile uses the `_wes_tool` `new-hostile` purpose at NL3/NL4/NL5.
- **WES Execution Planner** — shared. Scope rules govern hostile creation at tier 1-7.
- **WMS L2 combat evaluators** — shared substrate. Hostile-relevant chains: `enemy_killed` → `combat_kills_regional_low_tier` / `_high_tier` → `combat_boss_kills` → `population` → fed into `${wms_context}` for downstream WNS firings.
- **Tag system + tag-definitions.JSON** — shared allow-list. Hostile tags drive WMS retrieval, chunk spawn pools, visual filters.
- **`BundleToolSlice`** — shared by all hubs. The `parent_summaries` leak (Agent 1's seed) affects hostiles equally. **Single fix benefits all 8 content tools.**
- **Orphan detector** — shared. Cross-ref enforcement (drop material IDs, known skill IDs).
- **`attack_profile_generator.py`** — hostile-specific but reads `EnemyDefinition` fields. Deterministic post-LLM. Tool author doesn't need to know about it. Stays unchanged.

### 6.2 Hostile-specific shared with adjacent features

- **Material drops cross-ref** — Hostile's `drops[].materialId` references materials. Co-emission in the same plan is the norm. **The material tool should accept `cross_ref_hints.dropped_by_hostile_id`** as a hint to flavor the material's drop-source narrative ("the moors raiders strip these copper-strands from their bridles"). *(Agent assignment: Materials.)*
- **Skill cross-ref** — `skills[]` and `aiPattern.specialAbilities[]` references. Skills tool reciprocates with `cross_ref_hints.used_by_hostile_id` for flavor (a skill known by enemies has a different lore weight than a player-only skill). *(Agent assignment: Skills.)*
- **NPC cross-ref** — When a faction NPC commands these enemies (Captain Vell commands Copperlash Riders), the enemy should reference the NPC and the NPC should reference enemies-under-command. **The NPC tool's `dynamic_context` should carry a `commanded_hostiles: [enemy_id]` slot**, and the hostile tool's MISSING `encounter_context.factions` field should carry the corresponding faction tag. *(Agent assignment: NPCs.)*
- **Quest cross-ref (Agent 1's seed)** — When a quest's `objectives.objective_type=kill_target` references this enemy, the hostile tool should accept `cross_ref_hints.hunted_by_quest_id` to flavor the narrative ("hunted to extinction by Captain Vell's vendetta"). The MISSING `hunted_by_quest_ids[]` field on the hostile JSON is the reciprocal storage. *(Agent assignment: Quests — already noted.)*
- **Chunk cross-ref** — Hostile's role in chunk's `enemySpawns` is the load-bearing spawn integration. **The chunks tool's `enemySpawns` block must reference committed or co-emitted enemy IDs.** Today this is enforced through xref_rules (`REL_SPAWNS`). The reciprocal — hostile knows which chunks host it — should land in the MISSING `encounter_context.native_chunk_types[]` field. *(Agent assignment: Chunks.)*
- **Node cross-ref** — Indirect. A hostile drops materials; nodes also yield those materials. No direct hostile↔node link needed today, but in the future (a "hostile contests this node" mechanic), the hostile JSON might carry `contested_nodes: [node_id]`. Not in scope.

### 6.3 Where hostiles diverge (flavor not shareable)

- **Combat-feel parameters** — `aiPattern`, attack profile derivation, hitbox/hurtbox sizing — are hostile-specific. No other content type has analogous combat-runtime fields.
- **21-ability library lock-in** — Hostiles draw from a fixed library (no LLM-authored new abilities). This is a hostile-specific discipline; quests/NPCs/materials don't have an equivalent "must pick from N existing things" constraint at the same level (skills can be LLM-authored, materials can be LLM-authored).
- **Visual size / hurtbox derivation** — computed post-LLM from category × tier. Other content types don't have analogous procedural derivation.
- **Spawn-pool integration** — hostiles live in chunks' `enemySpawns` block. This is hostile-unique cross-ref shape.

### 6.4 Recommendations to other agents

- **Materials agent**: Accept `cross_ref_hints.dropped_by_hostile_ids: [enemy_id]` to flavor material's drop-source lore. Honor `biomes` cross-ref so material narratives can reference the locale.
- **NPCs agent**: Add `dynamic_context.commanded_hostiles: [enemy_id]` for faction-leader NPCs. Publish a deterministic API to fetch the NPC's voice/personality/grievance so the hostile tool can splice it (see §4.3 `[FRAGMENT-GAP]`).
- **Skills agent**: Accept `cross_ref_hints.used_by_hostile_ids: [enemy_id]` to mark skills enemies "know" (useful for skill narratives — a skill that the enemy faction teaches reads differently than a player-only skill). If skills agent ever extends the 21-ability library, **the new abilities must flow into the hostile tool prompt as additions to the ABILITY LIBRARY block.**
- **Chunks agent**: Ensure `enemySpawns` references existing or co-emitted enemy IDs. Reciprocate by populating `encounter_context.native_chunk_types[]` on the committed hostile (deterministic post-commit step).
- **Quests agent**: Already covered by Agent 1. Accept `cross_ref_hints.hunted_by_quest_id` is the right pattern — reciprocate by writing the link onto the hostile's `hunted_by_quest_ids[]` post-commit.
- **WNS / Planner+Supervisor agent**: **Two highest-impact interventions for hostile quality:** (1) close the `BundleToolSlice` parent_summaries leak (Agent 1's universal fix). (2) Tune `_wes_tool` body for `new-hostile` purpose with specific firing triggers (martial-domain shifts, faction expansion, player combat-monotony, chunk biome additions). See §4.6.
- **Titles agent**: Accept `cross_ref_hints.granted_by_hunting_hostile_id` for combat-titles. Title narratives around hostile-hunting threads benefit from the reciprocal link.

---

## 7. Storage / timing design

### 7.1 The hostile commit lifecycle

The hostile lifecycle differs from quests structurally — there is no "scroll opens" moment because the hostile is **runtime-spawned by chunks**, not offered to the player as a discrete choice. The lifecycle is:

- **Generation event**: WNS firing emits `<WES purpose="new-hostile">` → planner → hub → tool → static `EnemyDefinition` JSON commits to `ContentRegistry.reg_hostiles` AND to `Definitions.JSON/hostiles-generated-<timestamp>.JSON`. No reward materialisation step (hostiles have no rewards). No pre-gen pool — the hostile IS the artifact.
- **Reload event**: `EnemyDatabase` reloads to pick up new hostile. **This is currently broken** — `EnemyDatabase.reload()` does not exist. Per `DESIGNER_LEDGER.md` line 37, this blocks designer playtest. **The single largest infrastructure gap for hostile feature today.**
- **Chunk integration**: The chunk template (either co-emitted in the same plan OR existing) references the new enemy ID in `enemySpawns`. `ChunkTemplateDatabase.reload()` exists (per CLAUDE.md v8.1 note on chunks runtime integration); EnemyDatabase doesn't.
- **Spawn event**: `CombatManager._maybe_spawn_chunk_enemies` reads the chunk's `enemy_spawns` weighted pool, picks against `DENSITY_WEIGHTS`, spawns `Enemy` runtime instances.
- **Encounter**: Player kills, dies, dodges. WMS L1 events fire. Evaluators consume.
- **Death/return**: Enemy corpse despawns. No archive needed (unlike quests). The hostile DEFINITION persists; runtime instances are ephemeral.

### 7.2 Pool sizing — there is none

Unlike quests, hostiles don't have a "pool of pre-generated unoffered items" model. The hostile JSON is the artifact. Pool semantics are at the chunk level — a chunk's `enemySpawns` dict IS the pool, weighted by density.

The question is not "how many hostiles per giver" but "how many distinct hostile types per region / per biome / per tier band." Designer-tunable guidelines:

- **Per region**: 8-15 hostile types is a healthy distribution. Below 5 = ecosystem feels thin; above 20 = player can't form mental models.
- **Per tier band per region**: 2-4 hostiles per tier. T1 are common encounters; T4 are rare boss-tier encounters.
- **Per category per region**: at least 2 categories represented (beasts + humanoids, or beasts + aberrations). Single-category regions feel monotonous.

These guidelines live in WNS firing discipline (§4.6) — the weaver should fire `<WES purpose="new-hostile">` when the registry shows under-served niches.

### 7.3 Retirement and evolution (future-mode)

Per memory `chunk_evolution_future_idea.md`: chunks may eventually evolve down a branch with small chance, post-release. Hostiles could follow analogously — a "wolf_grey" might evolve into "wolf_grey_scarred" after enough player encounters. **Not implementing pre-release. Leave schema room** in `encounter_context` for `evolution_branch: [enemy_id]` future field.

WNS thread retirement: when a `wns_thread_id`-tagged hostile's thread reaches `coda` or `resolution`, the hostile should NOT spawn in chunks anymore (the moors raiders disband after their captain's vendetta resolves). Implementation: `EnemyDatabase` filters out hostiles whose `wns_thread_id` is in a closed state at spawn time. Today: not implemented — hostile spawning has no thread-state awareness. Recommendation: defer to post-launch — most players won't reach narrative resolutions in v4 playtest.

### 7.4 The reload gap — what to do about it

Today: generated hostiles land on disk but don't appear in-game until restart. Three approaches:

1. **Minimum-viable fix**: add `EnemyDatabase.reload()` that re-runs `load_from_file()` on the merged sacred + generated paths, regenerates attack profiles, refreshes `enemies_by_tier`. Match the `ChunkTemplateDatabase` pattern. Designer task, not LLM task. ~30 minutes work.
2. **Better fix**: same as 1, but also fire a `HostileDatabaseReloaded` event on the bus so `CombatManager` can refresh any cached spawn pools.
3. **Speculative**: when a new hostile commits, if any existing chunk template's `enemySpawns` *could* host it (biome match), auto-add the enemy to the chunk's spawn pool. Today the planner is supposed to co-emit chunk+hostile, but for opportunistic cases this would be nice. Designer call. Defer.

**Recommendation**: ship #1 for v4 playtest. #2 if time. #3 post-launch.

### 7.5 Persistence layout

```
Definitions.JSON/
├── hostiles-1.JSON                       # Sacred (untouched)
├── hostiles-generated-2026-05-26.JSON    # Generated by wes_tool_hostiles
├── hostiles-generated-2026-05-27.JSON    # Next session's batch
└── ...
```

The loader (`EnemyDatabase.load_from_file`) currently takes a single filepath. Needs extension to merge sacred + generated files, with generated overriding sacred on `enemyId` collision (last-writer-wins, same pattern as `ChunkTemplateDatabase`). Designer task.

---

## 8. Diversity & creativity design

User direction (re-channeled for hostiles): *"the competition is enemies that could be systematically generated... craziness is not the solution either... I want players to experience adventure not stagnant predictability."*

### 8.1 Category rotation

9 categories: beast, ooze, insect, construct, undead, elemental, aberration, humanoid, dragon. Most regions should host 2-3 categories. The hub should be discouraged from same-category stacking.

- Implementation: `recent_registry_entries` exposes per-region category counts. Hub prompt: "if last 3 hostiles in this region were all beast, prefer non-beast."
- WNS-side: narrative tone biases category. `tone:ominous` favors undead/aberration. `tone:mundane` favors beast/humanoid. `tone:tragic` favors humanoid (the fallen). `tone:hopeful` rarely favors hostile creation at all.

### 8.2 Behavior diversity

8 behaviors: passive_patrol, aggressive_pack, aggressive_swarm, aggressive_phase, boss_encounter, stationary, docile_wander, territorial. The hub should vary behavior across consecutive hostiles in a region.

- Suggested distribution per region: 40% aggressive (pack/swarm), 30% passive/territorial, 15% docile/stationary, 10% boss_encounter, 5% phase. Tunable.
- Behavior + category coupling: `aggressive_pack` is natural for beasts/humanoids, awkward for oozes/constructs. `stationary` is natural for constructs/ooze (a sentry-turret feel) but odd for beasts. The hub should respect natural couplings.

### 8.3 Ability-set diversity

The 21-ability library is locked. Diversity comes from VARIED PICKS per hostile. The hub's `flavor_hints.specialAbilities_hint` should rotate:

- Common T1-T2 enemies: 0-1 abilities. Most have none — basic attacks only.
- Uncommon T2-T3: 1 ability.
- Boss T3-T4: 2-4 abilities, including self-buff (`shell_shield`, `rampage`, `stone_armor`), control (`earthquake_stomp`, `void_rift`), and signature damage (`life_drain`, `crystal_beam`).
- Ability tone-coupling: `shadow` tags suggest `void_rift` / `life_drain` / `phase_shift`. `arcane` suggests `elemental_burst` / `crystal_beam` / `temporal_distortion`. `physical` suggests `leap_attack` / `earthquake_stomp` / `ground_slam`.

### 8.4 Drop-set diversity

Drops should mix:

- 1 guaranteed common material (the "trophy" drop — `wolf_pelt`, `slime_gel`, `moors_copper`).
- 1-2 moderate-chance T1-T2 materials (broader utility).
- 0-1 low-chance T3-T4 material (rare reward, the "essence" — `essence_blood`, `crystal_quartz`, `shadow_core`).
- Boss-tier may add 2-3 guaranteed materials and a low-chance T4.

The hub's `cross_ref_hints.drop_material_ids` should source materials from:
1. Co-emitted materials in the same plan (the moors-copper case).
2. Existing materials tagged with the biome (the "local economy" set).
3. Existing rare materials (the "essence" set, biome-agnostic for T3+ drops).

### 8.5 Stat-band variance within tier

Tier stat bands are ±20% by prompt. Within-tier variance via behavior coupling:

- Pack ambushers: lower HP, higher damage, faster speed, lower defense.
- Tank guards: higher HP, lower damage, slower speed, higher defense.
- Glass cannons (rare T2+): low HP, very high damage, fast.
- Bosses: max HP, moderate damage variance, low speed, high defense, fleeAtHealth=0.

Today the tool's stat sizing is intuitive but not formally constrained. A `${stat_archetype}` hint (e.g. "tank" / "glass_cannon" / "ambusher") in the hub's `flavor_hints` would tighten this.

### 8.6 Locality-specific naming pressure

The single biggest diversity dial is **locality-rooted naming**. Repeatedly emitting "Bandit," "Brigand," "Raider" across regions is the stagnation failure mode. The hub's `flavor_hints.name_hint` should:

- Compose locale + role + signature. "Copperlash Rider" = locale (copper-rich, lash-using) + role (rider).
- Avoid generic English. "Salt-Drowned" beats "Drowned One." "Fogbound Terrorbeak" beats "Marsh Bird."
- Inherit emergent_entity coinages from WNS (per memory: 2 per fragment, 5 per run, designer review). When WNS named "the Moors-Stone Massacre" as a thread headline, related hostiles can riff: "Moors-Stone Survivor," "Massacre-Survivor Rider."

### 8.7 Encounter-pattern diversity

The combination (behavior + abilities + attack profile) defines combat feel. Designer-tunable patterns:

- **Pair-ambusher**: `aggressive_pack` + `leap_attack` + medium speed. Two-spawn weighted pool. (Copperlash Rider archetype.)
- **Swarm-overwhelm**: `aggressive_swarm` + no abilities + high spawn count. (Acid slime archetype.)
- **Skirmisher**: `aggressive_pack` + `phase_shift` or `teleport` + fast. (Wraith archetype.)
- **Turret**: `stationary` + `crystal_beam` or `chaos_burst` + low spawn count. (Crystal slime mid-arena archetype.)
- **Boss-multistage**: `boss_encounter` + 3-4 abilities + `shell_shield` self-buff. (Elder wolf archetype.)
- **Docile-defender**: `docile_wander` + `earthquake_stomp` at low HP + high defense. (Beetle archetype.)

These patterns can be surfaced as `flavor_hints.engagement_pattern` allow-list. Defer to v2 schema unless designer feedback says it's needed early.

### 8.8 Emergent proper-noun discipline

Per WNS rule, the LLM may coin 2 proper nouns per fragment, 5 per run. For hostiles:
- "the Salt-Drowned" — a faction name implied by enemy naming pattern.
- "the Moors-Stone Massacre" — a referenceable event in the enemy's narrative.
- "the Copperlash Line" — a specific raider sub-group.

These should land in the `metadata.narrative` field but ALSO be extracted to a registry (the MISSING `emergent_proper_nouns[]` field — see §2.1). Designer reviews; promoted nouns become re-usable across future generations.

---

## 9. Speculative future endpoints

### 9.1 `wes_tool_hostile_ability` — author new abilities (CAREFULLY)

The 21-ability library is locked by design. But the library is finite, and designer playtest will surface gaps. A specialised endpoint for ability creation:

- **Trigger**: planner emits `<WES purpose="new-ability">` (new bucket) when hostile tool's `flavor_hints.specialAbilities_hint` can't be satisfied by the existing library and the planner can justify the need.
- **Inputs**: directive + the new hostile's `category`, `tier`, narrative tone, requested-effect type.
- **Outputs**: one ability JSON matching the `abilities[]` shape in `hostiles-1.JSON` (abilityId, name, tags, effectParams, cooldown, triggerConditions). Tags MUST come from `tag-definitions.JSON` allow-list — same discipline as combat tags.
- **Constraint**: tags only, no new tag invention. Effect params within combat-config band.
- **Risk**: ability proliferation breaks the locked library promise. Mitigation: cap at 1 new ability per plan, designer-review surface (added abilities live in `Definitions.JSON/hostiles-generated-<timestamp>.JSON#abilities` and designer reviews before merging into sacred).

Endpoint count: +1 LLM task. Probably NEEDED post-v4 launch when the library starts feeling limiting.

### 9.2 `wes_hostile_modifier` — adapt hostile to evolving WNS thread

User direction from quests (translated for hostiles): a hostile generated three sessions ago may be stale if the WNS thread has moved on. A modifier endpoint:

- **Trigger**: at chunk spawn time, if the hostile's `wns_thread_id` has moved by N stages since generation, fire the modifier.
- **Inputs**: original `EnemyDefinition` + current WNS thread state + WMS events since generation.
- **Outputs**: patch JSON — `{metadata.narrative?, drops?, aiPattern.specialAbilities?, stats?}`.
- **Latency budget**: chunk generation has no UI mask. Should be background-async; if not ready by player-arrival, spawn the original definition.

Endpoint count: +1 LLM task. Lower priority than `wes_hostile_ability`.

### 9.3 `wes_hostile_encounter_director` — adapt encounter difficulty at spawn time

Hostile DEFINITIONS are static, but encounter DIFFICULTY varies with party comp, player level, recent player profile. A real-time director:

- **Trigger**: at chunk spawn, if player's combat profile (skill, recent deaths, level) diverges from hostile's tier expectation by N bands.
- **Inputs**: hostile definition + player profile + recent combat ledger.
- **Outputs**: a spawn modifier — `{health_scale: float, count_scale: int, ability_pool_filter: [str]}`.

This is the closest hostile equivalent to quests' `wes_quest_reward_adapt`. **Probably NOT LLM-driven** — encounter scaling should be deterministic from player stats × tier mapping. Mention here so the designer doesn't try to LLM-up something better-solved with math.

Endpoint count: 0 LLM tasks. Pure code. Mention deferred to `Development-Plan/SHARED_INFRASTRUCTURE.md` as a TODO.

### 9.4 `wes_hostile_evolution` — chunk-evolution-style enemy evolution

Per memory `chunk_evolution_future_idea.md`: post-release, chunk templates may form trees and existing instances roll small chance to evolve down branches. Hostiles could follow:

- **Trigger**: when an enemy's `wns_thread_id` reaches `turning_point` or when player kill-count of this enemy crosses threshold.
- **Inputs**: original enemy + thread state + kill stats.
- **Outputs**: a child `EnemyDefinition` (e.g. `wolf_grey_scarred`) with adjusted stats/abilities/narrative.
- **Schema room**: leave `encounter_context.evolution_branch: [enemy_id]` field for this future.

Endpoint count: +1 LLM task. Post-release. Schema-prep only for v4.

### 9.5 `wes_hostile_curator` — biome-coherence audit on commit

When a new hostile commits, an audit pass checks:
- Does at least one existing chunk's `enemySpawns` reference this hostile?
- Are the hostile's drops materials actually findable in the same biome (cross-check with `ChunkTemplate.resource_density`)?
- Is the hostile's tier consistent with the biome's average tier?
- Does the hostile reference a faction NPC that exists?

This is a deterministic audit — code, not LLM. Mentioned for completeness.

Endpoint count: 0 LLM tasks. Pure code. Bundled into `ContentRegistry.commit` post-commit hooks.

### 9.6 `wes_hostile_dialogue` — taunts, death rattles, ability calls

Some hostiles (humanoids, sentient undead, dragons) have voice. The current schema has no dialogue field. A future endpoint:

- **Trigger**: when hostile is committed and category in {humanoid, undead, aberration, dragon}.
- **Inputs**: hostile definition + faction NPC voice (if linked) + ability set.
- **Outputs**: a `speechbank: {aggro_call: [str, ...], ability_call: {ability_id: [str, ...]}, death_rattle: [str, ...], flee_taunt: [str, ...]}` block.
- **Runtime**: combat manager reads `speechbank` at the relevant moments.

Endpoint count: +1 LLM task. Parallels NPC speechbank pattern. Mid-priority — adds voice to humanoid combat which is the most "named" hostile tier.

### 9.7 Big-picture: 2-endpoint hostile pipeline grows to potentially 4-5

Current: `wes_tool_hostiles` + `wes_hub_hostiles` (2).
With speculatives: + `wes_tool_hostile_ability` + `wes_hostile_modifier` + `wes_hostile_dialogue` (5 total — encounter_director and curator are code, not LLM).

Pragmatic v4 launch: ship the 2 endpoints, close the bundle leak, add `EnemyDatabase.reload()`, add the missing schema fields (`encounter_context`, `wns_thread_id`, `hunted_by_quest_ids`). That's the production-ready hostile system. The speculatives are post-launch enrichments.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Add `EnemyDatabase.reload()` and merged sacred+generated loading.** Without this, generated hostiles never reach the player. The hostile feature has no playtest path. ~30 minutes of work; matches existing `ChunkTemplateDatabase` pattern. Highest priority by margin.
2. **Close the `BundleToolSlice` parent_summaries leak.** Hostile narrative quality collapses without WNS parent context (failure mode 1.3.d). Same fix as quests, NPCs, and all other tools — solve once, benefit eight features.
3. **Extend hostile JSON schema with `encounter_context` block.** Without locality / faction / wns_thread_id / hunted_by_quest_ids storage, downstream queries (chunks filtering by faction, quests linking to hostiles, WNS retirement of closed-thread hostiles) all degrade. Schema bump now is cheaper than retrofitting after content lands.

Everything else in this trace — diversity dials, ecosystem census, modifier endpoints, dialogue, evolution — is downstream of those three. The hostile system has a strong WMS substrate (zero `[WMS-GAP]`), a workable WES pipeline, a solid existing schema, and clean cross-feature shape with the other seven content tools. The work left is plumbing and discipline, not new substrate.
