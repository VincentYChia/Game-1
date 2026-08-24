# Feature Trace 06 — Skills

**Wave:** 2
**Owned endpoints:** `wes_tool_skills`, `wes_hub_skills`
**Final output artifact:** `SkillDefinition` JSON (one per LLM call from `wes_tool_skills`), committed to `ContentRegistry.reg_skills` and reloaded into `SkillDatabase`.
**Date:** 2026-05-26

> "These wolves have been bothering us. Help us." — slop quest, generic giver.
> A skill is the inverse failure mode: "Skill 47: deals 50 damage" is the slop. The bar is **a skill that BELONGS to its lineage** — to the master who teaches it, to the discipline it sharpens, to the moors-stone that shaped both.

This trace is anchored on a player who has just slotted a freshly-learned skill into their hotbar. Every decision below serves: the moment Captain Vell teaches the player Copperlash Gash, the moment the player presses 4 in the moors-stone fight, the moment the copperlash whips out and the rider on the next tile starts bleeding.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

There are TWO player-facing moments the skill pipeline serves, and they have different latency budgets:

**Moment A — Learning.** The player stands in front of an NPC who has the canTeach service and a teachable they meet requirements for. A dialogue beat: "I can show you what the salt taught me. Three winters' work in a single strike." The player accepts. A small flash. A new entry in their skill menu — name, icon, narrative line, mana/cooldown cost, the description that tells them WHAT IT DOES, the narrative that tells them WHY IT EXISTS. They drag it into hotbar slot 4.

**Moment B — Use.** Combat. Player presses 4. Mana drains. Cooldown starts. A whip-arc of motion fires from the player toward a target on the next tile. The target takes the base damage of the skill, scaled by STR and skill level, and starts a bleed DOT — because the skill's `combatTags` include `bleed` and the `combatParams.bleed_damage_per_second` is non-zero. Two seconds later the rider drops. The skill icon greys out on cooldown. The player feels: I JUST DID THAT, AND IT WAS MINE.

That is the entire experience the skill pipeline exists to serve. Everything we generate is in service of: (a) the moment the player learns it (cold-read of name + description + narrative + visible cost), (b) the moment they use it in combat or crafting (cold-execution of effect_executor through `combatTags` + `combatParams`), and (c) the moment they look at their skill list a session later and remember WHO TAUGHT THEM (the lineage hook).

### 1.2 Timing budget — the architectural constraint

Skills, unlike quests, have NO scroll-unfurl beat. Learning a skill is a dialogue exchange — the latency is masked by the NPC's "let me show you" line, which is ~1 second of speech-bubble or voiced dialogue. **The skill JSON MUST already exist by the time the player accepts the offer.** Live generation at learn-time is infeasible — 5-20s of dead air during dialogue would be jarring.

This dictates the architecture, identical in spirit to the quest pool:

- The `wes_tool_skills` LLM call MUST fire during WNS cascade time, not during teach-dialogue time. Generated `SkillDefinition` JSONs commit to `reg_skills` and write to `Skills/skills-generated-<timestamp>.JSON` (sibling-loaded by `SkillDatabase.reload()`).
- When an NPC with `services.canTeach: true` and `teachableSkills: [skill_id]` is co-emitted in the same WES plan, the skill MUST land before the NPC. The planner already enforces this via the DAG (`[skills] -> [npcs]` per the example in `prompt_fragments_wes_execution_planner.json`).
- The teach-time interaction is then deterministic: `SkillManager.can_learn_skill` checks requirements; if green, `SkillManager.learn_skill` runs through; `SKILL_LEARNED` is published to GameEventBus; `record_skill_learned` writes to StatStore; `progression_skills.py` evaluator interprets it as an L2 narrative row at the locality. **No LLM in this hot path.**
- Use-time is even more deterministic. The effect executor reads `combatTags` + `combatParams` and dispatches through the existing tag-driven system. Zero LLM. Sub-frame latency.

The ONE place the WES pipeline could leak into live time is at the moment the NPC OFFERS to teach. If we wanted the NPC to flavor the teach-offer dialogue contextually ("I'll teach you the copperlash gash if you walk with me to the moors-stone first"), that line is an NPC speechbank concern, not a skill-tool concern. The skill stays cold.

### 1.3 Failure modes — what BAD looks like

**(a) Slop.** "Power Strike II: deals 75 damage. Cooldown 30s." The name is a number. The narrative is missing or generic ("Strike with power."). The combatTags are the bare minimum (`[physical, single_target]`). The cost is the default. There is nothing in this skill that says it BELONGS anywhere or to anyone. *(Defense: the hub MUST receive narrative_anchor and prose_fragment from the planner; the tool MUST be told to write `narrative` as 1-2 sentences in a voice rooted in that anchor, and to pick effect parameters that align with the anchor's flavor.)*

**(b) Stagnant predictability.** Every new combat skill is `devastate + damage + enemy + single_hit`. Every new crafting skill is `quicken + smithing + self`. After three sessions, the player has seen all the shapes of the wheel. New skills feel like reskins. *(Defense: tag-combination diversity dial — see §8. The hub must vary tier, effect.type, geometry combatTag, status combatTag, target shape across batches.)*

**(c) Craziness.** The LLM, given creative liberty, generates "Skill of Banana Telepathy" — tags `[fire, beam, freeze, lifesteal, pull, execute]` (six functional combat tags that conflict on dispatch). combatParams: `{baseDamage: 9999, cone_angle: 720}`. characterLevel: 1. The skill is unforgettable AND **immediately breaks combat balance** — a level-1 character one-shotting every enemy in line of sight. *(Defense: the tag allow-list is hard-locked to the existing `tag-definitions.JSON` library. The effect-type × category matrix is enforced by the tool prompt. The tier × stat × cost bands in the tool prompt clamp characterLevel/stat-reqs/cost to tier. The BalanceValidator [designed, not yet built] is the last line of defense — until then, the prompt's tier bands and the schema validator are it.)*

**(d) Mechanically illegible.** A subtle failure: the skill's `description` says "drains life from enemies" but `combatTags` is `[physical, single_target]` with no `lifesteal` tag. The player reads the description, uses the skill, sees no life drain, feels cheated. The text doesn't match the dispatch. *(Defense: the tool prompt must require `description` to be a literal English rendering of what `combatTags` + `combatParams` will do. If the tag is `lifesteal`, the description says "drains health." If `combatTags` includes `chain`, the description names how many targets it jumps.)*

**(e) Disconnected from teacher.** A skill generated under "Captain Vell teaches Copperlash Gash" emerges named "Power Slash" with no narrative reference to the moors, no copper, no whip. The teacher's narrative is in the bundle but never reaches the skill tool. This is the analog of quest failure (1.3.d), and it's the SAME leak — `BundleToolSlice.parent_summaries` strips narrative, and additionally the skill tool has no `teacher_npc_narrative` slot at all. *(Defense: close the slice leak [shared fix with quests] AND add a `cross_ref_hints.taught_by_npc_id` reverse hint + a `${teacher_voice_anchor}` template slot. See §4.4 and §6.2.)*

### 1.4 What "good" actually looks like

A good generated skill, in the player's words two sessions in: *"Copperlash Gash. Vell taught me that one. It bleeds them out — feels right for a salt-moors weapon."*

Four properties:
- **Mechanically legible** — what the description says it does is what `effect_executor` does when the tags fire.
- **Voiced** — the `narrative` line sounds like the discipline / NPC / locality it came from, not like a wiki entry.
- **Lineage-anchored** — there is some thread (the teacher's name, the material's faction, the chunk's biome) that makes the player remember WHERE this skill came from.
- **Tier-coherent** — characterLevel, stat reqs, mana, cooldown, damage all sit in the same tier band. Nothing wildly out of bounds.

---

## 2. Output artifact schema completeness audit

The `SkillDefinition` shape is locked in `data/models/skills.py:46-69` and consumed by `SkillDatabase._parse_skill` (`data/databases/skill_db.py:31-89`). Every field below must be filled by either the tool, the hub's hard_constraints/flavor_hints projection, or be deterministically defaulted.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `skillId` | str (snake_case) | `wes_tool_skills` | Should encode lineage + intent. `copperlash_gash` beats `combat_skill_47`. Unique against `reg_skills`. |
| `name` | str (Title Case) | `wes_tool_skills` | Evokes the lineage. "Copperlash Gash" beats "Power Strike". |
| `tier` | int 1-4 | `wes_tool_skills` (constrained by hub `hard_constraints.tier`) | Drives the stat/mana/cooldown/characterLevel band. Must align with the firing tier's scope rules. |
| `rarity` | str (6 values) | `wes_tool_skills` | common/uncommon/rare/epic/legendary/mythic. Diversity dial; affects RARITY_MULTIPLIERS in `skills-base-effects-1.JSON`. |
| `categories` | List[str] (1-3) | `wes_tool_skills` | From the 15-value categories allow-list (gathering, mining, combat, defense, smithing, etc.). Drives skill-menu filtering AND effect-category eligibility. Should overlap with the NPC teacher's `knowledge_domains` when teacher-coupled. |
| `description` | str (1-2 sentences) | `wes_tool_skills` | MECHANICAL prose. Literal English rendering of what the skill does in gameplay. Player reads this and predicts the dispatch. |
| `narrative` | str (1-2 sentences) | `wes_tool_skills` | FLAVOR prose. Lineage-voiced. The line that makes the skill feel earned. |
| `tags` | List[str] (2-5) | `wes_tool_skills` | From DESCRIPTIVE tag allow-list (in tool prompt). NOT combat-dispatch tags. Drives StatTracker / UI filtering / WMS retrieval. |
| `effect.type` | str (1 of 10) | `wes_tool_skills` (constrained by hub `hard_constraints.effect_type`) | empower/quicken/fortify/restore/regenerate/enrich/elevate/pierce/devastate/transcend. Locked allow-list. |
| `effect.category` | str (matrix-constrained) | `wes_tool_skills` | Must satisfy the TYPE × CATEGORY matrix in the tool prompt. E.g. `enrich` only valid with `mining` or `forestry`. |
| `effect.magnitude` | str (4 values) | `wes_tool_skills` | minor/moderate/major/extreme. Scales the magnitudeValues from `skills-base-effects-1.JSON`. |
| `effect.target` | str (4 values) | `wes_tool_skills` | self/enemy/resource_node/area. |
| `effect.duration` | str (5 values) | `wes_tool_skills` | instant/brief/moderate/long/extended. Maps to seconds via SkillDatabase.durations. |
| `effect.additionalEffects[]` | List[Dict] | `wes_tool_skills` | Optional secondary effects, same shape as primary. Empty `[]` is the common case; non-empty is the "compound skill" pattern (e.g. Battle Fury = empower+quicken). |
| `cost.mana` | int (or legacy str) | `wes_tool_skills` | Numeric points 20-150+. The tool prompt's tier band guides. Translation table backward-compat via `SkillDatabase.get_mana_cost`. |
| `cost.cooldown` | int seconds (or legacy str) | `wes_tool_skills` | 20-1200s. Tier band guides. |
| `requirements.characterLevel` | int 1-30 | `wes_tool_skills` | Must match tier band. Tier 1 → 1-5, Tier 4 → 26-30. |
| `requirements.stats` | Dict[STAT: int] | `wes_tool_skills` | Subset of STR/DEF/VIT/LCK/AGI/INT. Only stats the skill thematically needs (a fire skill needs INT; a melee skill needs STR). |
| `requirements.titles[]` | List[str] | `wes_tool_skills` | Title gates. Cross-ref TITLES (or co-emitted). Usually `[]`. |
| `iconPath` | str (auto-default) | Loader fallback in `skill_db.py:69-71` | Defaults to `skills/{skill_id}.png` if absent. Visual asset assumed missing-but-deterministic. |
| `combatTags[]` | List[str] | `wes_tool_skills` | **LOAD-BEARING.** Functional combat tags from `tag-definitions.JSON` allow-list (damage_type + geometry + status + special). Drives `effect_executor.execute_effect`. |
| `combatParams` | Dict | `wes_tool_skills` | Per-tag numeric parameters (`baseDamage`, `circle_radius`, `burn_duration`, etc.). MUST be paired with the corresponding combatTag. Defaults from `tag-definitions.JSON` apply if absent, but tool should set them explicitly. |
| `evolution.canEvolve` | bool | `wes_tool_skills` (or default false) | Whether this skill can mutate into a stronger variant. |
| `evolution.nextSkillId` | str or null | `wes_tool_skills` | Forward chain link. If non-null, must cross-ref another committed/co-emitted skill. |
| `evolution.requirement` | str | `wes_tool_skills` | Free-form prose describing the evolution gate ("kill 50 copperlash riders", "smith 100 weapons"). NOT machine-checked currently — descriptive only. |

### 2.1 Schema completeness — what's MISSING

This is a `[WES-SCHEMA-GAP]` audit. The current schema, while functional, has clear absences against the lineage / teacher-coupling design surface:

- `[WES-SCHEMA-GAP]` **`taught_by_npc_id` / `taught_by[]`** — the field that closes the lineage loop. NPC v3 has `services.teachableSkills: [skillId]` (forward: NPC → Skill). There is no reverse pointer (Skill → NPC). Agent 1 surfaced this need: skills should accept reverse cross-ref `taught_by_npc_id` to flavor the skill around the NPC who teaches it. Without it, the skill's `narrative` field has no deterministic way to pull the teacher's voice; the tool guesses from `flavor_hints.prose_fragment`. Recommend adding `taught_by: List[npc_id]` to the SkillDefinition schema (an array because multiple NPCs could teach the same skill across regions — a "lineage" rather than a single teacher).

- `[WES-SCHEMA-GAP]` **`prerequisite_skills[]`** — there is no formal "you must know X before you can learn Y" gate. `requirements.titles` and `requirements.stats` and `requirements.characterLevel` are the only learn gates. Yet `evolution.nextSkillId` implies a chain — but a chain is forward-emit only, not consumable by `can_learn_skill`. A real skill tree wants prerequisite gates. Workable workaround: title-as-prerequisite (e.g. "Apprentice Moors Reaver" gates Copperlash Gash II). Cleaner: add `requirements.prerequisiteSkills: [skillId]` with cross-ref discipline. *(This is a designer-call deferral — keep workable workaround for v4, add prerequisiteSkills if the skill tree expands.)*

- `[WES-SCHEMA-GAP]` **`unlockMethod` field** — `SkillUnlockDatabase` (separate system, `data/databases/skill_unlock_db.py`) tracks how skills are unlocked (level-up, NPC teach, quest reward, achievement). The `SkillDefinition` itself doesn't carry this info; the unlock side carries it. This is fine for now, BUT when WES generates a new skill, the unlock side ALSO needs a corresponding `SkillUnlock` entry — currently the WES pipeline only writes the skill, not the unlock record. **Skills emitted by `wes_tool_skills` are effectively only available via the auto level-up path (`get_available_skills` filter) — they cannot be taught by NPCs at runtime until a SkillUnlock entry is created.** This is a `[FRAGMENT-GAP]` at the orchestrator layer: the dispatcher should emit a default SkillUnlock alongside the skill when teach-coupling is established (`taught_by_npc_id` set → write `unlockMethod: NPCInteraction`).

- `[WES-SCHEMA-GAP]` **`source_origin`** — same as quests had at v3 launch. The loader (`SkillDatabase`) doesn't differentiate hand-authored vs. generated skills. For balance auditing and future modifier-AI scoping, generated skills need to be flagged. Loader-side fix, not LLM-emitted.

- `[FRAGMENT-GAP]` **`flavor_hints.teacher_voice_anchor`** — the hub prompt's `narrative_anchor` is a single string ("moors raiders"). It should also carry the teacher NPC's `narrative` excerpt and `personality.voice` excerpt when teacher-coupled, so the tool can write the skill's `narrative` field in a voice consistent with the eventual teacher's speechbank. Otherwise the player learns Copperlash Gash from Captain Vell who speaks in clipped salt-dry sentences, but the skill's flavor text reads like a generic fantasy tooltip.

- `[FRAGMENT-GAP]` **`flavor_hints.lineage_excerpt`** — a 1-2 sentence excerpt from the WNS firing layer's narrative that captures WHY this skill exists. "The moors raiders' copperlash whips draw cuts the salt wind salts further." That sentence wants to land in the tool's input so the `narrative` field can reference moors-stone or salt without inventing them.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent procedural skill generator (no LLM) produces, given a tier roll + an effect-type pick + a category pick:

```json
{
  "skillId": "combat_skill_47",
  "name": "Power Strike II",
  "tier": 2,
  "rarity": "uncommon",
  "categories": ["combat"],
  "description": "Strike with great power.",
  "narrative": "A powerful attack.",
  "tags": ["damage", "combat", "single_hit"],
  "effect": {
    "type": "devastate",
    "category": "damage",
    "magnitude": "moderate",
    "target": "enemy",
    "duration": "instant",
    "additionalEffects": []
  },
  "combatTags": ["physical", "single_target"],
  "combatParams": {
    "baseDamage": 60
  },
  "cost": {
    "mana": 60,
    "cooldown": 180
  },
  "requirements": {
    "characterLevel": 6,
    "stats": {"STR": 8},
    "titles": []
  }
}
```

This is fine. This is also the entire problem. The player learns this and forgets it inside two sessions. The wiki has nothing to say about it. The skill icon menu has another rectangle.

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM must contribute that the slot machine can't:

1. **`skillId`** — embed lineage + intent. `copperlash_gash` not `combat_skill_47`. Needs `narrative_anchor` (for lineage) + `item_intent` (for intent verb) + `recent_registry_entries` (to know what's been used).
2. **`name`** — needs to taste like the lineage's culture. "Copperlash Gash" not "Power Strike II." Needs the locality's material/biome flavor + the teacher's voice anchor.
3. **`description`** — must be the LITERAL English rendering of `combatTags` + `combatParams`. "A lash-strike with a copper-weighted whip that opens a bleeding wound (8 damage/sec for 6 seconds)." This is a CONTRACT between the tool's text output and the tool's dispatch output. The slot machine can't enforce this contract; the LLM can be prompted to.
4. **`narrative`** — flavor in the lineage's voice. "Moors raiders favor the copperlash — a short whip weighted with ore slugs that draws deep cuts the salt wind salts further." Needs the teacher NPC's `narrative` excerpt + the home_chunk's biome anchors + the WNS thread's tone.
5. **`combatTags`** — the slot machine picks defaults. The LLM picks the tag combination that MATCHES the narrative anchor. Copperlash = `[physical, single_target, bleed]` (not `[fire, beam]`). This requires the LLM to UNDERSTAND the tag library and pick coherently.
6. **`combatParams`** — the slot machine plugs in defaults. The LLM tunes them to tier AND to the narrative anchor's signature. A copperlash skill should have moderate baseDamage + non-trivial bleed_damage_per_second (because copperlash = "draws cuts"). A meteor strike has high baseDamage + large circle_radius + burn_duration (because meteor = "scorched earth").
7. **`effect.type` + `effect.category`** — the slot machine picks from the matrix randomly. The LLM picks the combination that MATCHES the intent. A bleed-causing whip is `devastate` (because devastate is in the damage category and is the destructive flavor); a smith's focus skill is `quicken` (because crafting-time extension is quicken-coded). Coherence with the matrix AND with intent.
8. **`evolution.requirement`** — slot machine is silent; LLM writes a prose requirement that connects to the lineage. "Slay 50 copperlash riders in the salt moors" beats "Use this skill 100 times."
9. **`requirements.stats`** — slot machine picks one stat per category. LLM picks the COMBINATION that fits the skill's flavor. Copperlash = STR + AGI (it's a whip — strength to draw, agility to flick). Field Medic = VIT + INT (vitality to anchor the heal, intelligence to know where).

The delta is: **lineage-rooted naming + mechanically legible description + tag/param coherence with the narrative anchor.** Everything in the skill pipeline architecture must serve these three properties.

---

## 4. Backward trace through the pipeline

This is the rung-by-rung walk from "player presses 4 in combat" backward to "WMS event row." Each rung names what it consumes, what it emits, and what could be missing.

### 4.1 Rung 0 — Player presses 4 (player-facing)

Consumes: `equipped_skills[3]` → skill_id → `SkillDatabase.skills[skill_id]` → `SkillDefinition.combatTags` + `.combatParams`. Plus runtime: PlayerSkill.level (for level-scaling bonus), character.mana (deducted), cooldown state.

Emits: `effect_executor.execute_effect(source=character, primary_target=..., tags=combatTags, params=combatParams, available_entities=...)` → damage/healing/status effects applied; `record_skill_used` to StatStore; `SKILL_LEARNED` already published earlier at learn-time.

Risk: if the skill was generated with combatTags that conflict (`fire` + `freeze` per `tag-definitions.JSON:153,162` conflicts_with), the dispatch silently no-ops on one of them. The tag registry's conflict checking is informational, not enforced at parse-time. **The tool must respect `conflicts_with` declarations in the tag library — this is a prompt-discipline issue, not a runtime guard.**

### 4.2 Rung 1 — Skill learned (player-facing, prior session)

Consumes: NPC dialogue → "teach me Copperlash Gash" branch → `SkillManager.learn_skill(skill_id, character)` → can_learn check (level + stats + titles) → `known_skills[skill_id] = PlayerSkill(...)` → `record_skill_learned(skill_id, source="npc_teach")` → `get_event_bus().publish("SKILL_LEARNED", {actor_id, skill_id})`.

Emits: the SKILL_LEARNED bus event is what the WMS `progression_skills.py` evaluator catches; it produces an L2 InterpretedEvent at the player's locality with `affects_tags=["type:player", "event:skill_learned", f"skill:{skill_name}"]`. This is the row that feeds NL2-NL4 narratives downstream — "the moors-stone has taught another." **Solid; this WMS plumbing already exists.**

Risk: only relevant for skills with a `SkillUnlock` entry (see §2.1 schema gap). Generated skills without an unlock entry can't be taught by NPCs at runtime. This is an orchestrator-layer fix, not a tool-prompt one.

### 4.3 Rung 2 — Pre-existence (the cold-storage that makes Rung 0/1 possible)

The `SkillDefinition` must already be in `SkillDatabase.skills` when the player learns it. This is achieved by:

1. WES pipeline fires during WNS cascade time.
2. `wes_tool_skills` emits the JSON.
3. `ContentRegistry.commit` writes to `reg_skills` table + flushes to `Skills/skills-generated-<timestamp>.JSON`.
4. `database_reloader._RELOAD_TARGETS["skills"]` calls `SkillDatabase.reload()` — **confirmed reload target exists in `content_registry/database_reloader.py:65-71`.**
5. From then on, `SkillManager.can_learn_skill(skill_id, ...)` resolves the skill.

Risk: `SkillDatabase.reload()` method itself — the reload target table calls `("reload", "_reload", "reload_all")` as method candidates. I did NOT see a `def reload` in `skill_db.py` in my read. If it's missing, the dispatcher logs a degrade and the database silently fails to pick up the new skill. **This is a per-link integration verification item (per memory `feedback_tool_integration_verification.md`):** skills' reload method may need to be added if not present. *(Skill ledger TODO: verify `SkillDatabase.reload()` exists, or write it as `SkillDatabase._reload(self): self.skills = {}; self.load_from_file(...) + load_from_file(generated_path) for each generated sibling`.)*

### 4.4 Rung 3 — `wes_tool_skills` (one ExecutorSpec → one skill JSON)

Inputs (from `prompt_fragments_tool_skills.json:11`):
- `spec_id`, `plan_step_id`, `item_intent`, `hard_constraints` (JSON: tier/effect_type/effect_category/magnitude/target/rarity), `flavor_hints` (JSON: name_hint, prose_fragment, narrative_anchor, tag_hints), `cross_ref_hints` (JSON: currently almost always `{}`).

Output: one `SkillDefinition`-shaped JSON.

What's MISSING:

- `[WES-SCHEMA-GAP]` **The bundle's narrative context at the skill tool layer.** SAME LEAK as quests (§4.4 in `01-quests.md`). `slice_bundle_for_tool` strips `parent_summaries` and `firing_layer_summary` and the wider WMS delta. By the time the spec reaches the tool, the only narrative trace is `flavor_hints.prose_fragment` — a single string the hub chose to keep. **The chunk of NL4 narrative that named the moors-stone and the copperlash never reaches the skill tool.** Fix is identical to the quest fix: extend the tool's user_template with `${narrative_context}` and `${parent_narrative}` slots; have the hub thread them through `flavor_hints.narrative_excerpt`.

- `[WES-SCHEMA-GAP]` **The teacher NPC's voice + narrative excerpt.** When the spec is being generated under "[skills] → [npcs]" dependency order — i.e. the planner says "skill s3 will be teachable by the NPC s6" — the teacher NPC has NOT YET been generated when the skills tool fires. So the teacher's narrative literally doesn't exist yet. **This inverts the quest/NPC pattern, where the NPC exists by the time the quest tool fires.** Two designer choices:
  1. **Flip the DAG**: emit NPCs before skills in any plan where they co-occur. The current planner example (`prompt_fragments_wes_execution_planner.json:15`) puts skills as `depends_on: []` and NPCs as `depends_on: ["s5", "s3"]` — skills first. Reasonable because the NPC's `teachableSkills` array needs the skill IDs to exist. **But this means the teacher's voice is unknown at skill-tool time.**
  2. **Carry the teacher's INTENT, not the teacher's full narrative**: the hub knows from the planner's `step.slots` (or the plan's wider context) which step number will be the teacher. The hub then provides a `flavor_hints.teacher_intent_anchor` — "this skill will be taught by a copperlash captain hardened by his brother's death on the moors-stone." That intent string is enough for the skill tool to write a lineage-rooted name and narrative, even though the FULL teacher narrative is still cooking.

  Recommend choice 2. It preserves DAG sanity and gives the skill tool enough voice anchor to write a lineage-coherent skill. Skill ledger TODO: add `flavor_hints.teacher_intent_anchor` to the hub→tool pipeline.

- `[FRAGMENT-GAP]` **`cross_ref_hints.taught_by_npc_id` (reverse cross-ref).** Per Agent 1's seed: skills should accept this as a reverse cross-ref. Currently the hub prompt says "cross_ref_hints: Almost always {}." (line 10 of `prompt_fragments_hub_skills.json`). Change the hub prompt to accept `taught_by_npc_id` when the planner co-emits an NPC. The tool then knows "this skill is going to be taught by NPC s6 once s6 generates" — even if it doesn't have s6's narrative yet, it has the NPC's intent string from the planner's step description. The hub propagates the intent string into `flavor_hints.teacher_intent_anchor`.

- `[FRAGMENT-GAP]` **`cross_ref_hints.rewarded_by_quest_id` (reverse cross-ref).** Per `01-quests.md` §6.2 / §6.4: when a quest grants a skill as reward (via `rewards_prose.skill_hint`), the quest reward materializer can either (a) reference an existing skill or (b) trigger skill co-emission in the same plan. The reverse linkage tells the skill tool "this skill is a reward for the salt-reach hunt quest" — flavor accordingly. Add to hub and tool prompts.

- `[FRAGMENT-GAP]` **`cross_ref_hints.signature_skill_of_hostile_id` (reverse cross-ref).** Hostiles can carry a `specialAbilities` list of skill IDs (or analogous — confirm in hostiles trace). The reverse pointer "this skill is the signature move of the copperlash_rider hostile" tells the skill tool that combatTags should match a humanoid raider archetype, baseDamage should be tier-appropriate for the hostile's tier, etc. This is the OTHER big lineage hook beyond NPCs.

- `[FRAGMENT-GAP]` **Tag library allow-list freshness.** Per `tag_system_functionality.md` memory: "tool prompts are 'growing prompts' with current library as allow-list." The current tool prompt embeds the descriptive tag allow-list and combat tag allow-list as STATIC text. If the designer adds a new combat tag (e.g. `corrode` for moors_copper), the tool prompt doesn't see it until manually updated. This is a Prompt Studio surface — the studio's "Coverage health" check should flag drift between the tool prompt's allow-list and `tag-definitions.JSON`.

- `[FRAGMENT-GAP]` **Description-vs-dispatch enforcement.** The tool prompt should require: "`description` MUST be a literal English rendering of what `combatTags` + `combatParams` will do at runtime. If `combatTags` includes `bleed`, the description mentions bleeding. If `combatTags` includes `chain`, the description names how many targets it jumps." Currently the prompt has rules 6 ("description: 1-2 sentences, mechanical. What does the skill DO?") and 9 (effect rules), but does NOT explicitly bind them. Add: "`description` and `combatTags`/`combatParams` are a CONTRACT — players read description, expect dispatch to match. Misalignment is a hard rejection."

### 4.5 Rung 4 — `wes_hub_skills` (one plan step → batch of ExecutorSpecs)

Inputs (from `prompt_fragments_hub_skills.json:11`):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "copper-weighted whip strike with bleed — signature of moors raiders" and emits 1 or more `<spec>` elements with fully-loaded constraints/hints/cross-refs.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same `parent_summaries` leak as the tool.** Fix at this layer propagates to the tool.

- `[FRAGMENT-GAP]` **Co-emission awareness.** When the plan contains `[skills, npcs]` with `npcs.depends_on=[skills.step_id]`, the hub should see "an NPC is about to consume this skill ID." That awareness is currently absent. The hub gets `recent_registry_entries` (for diversity against past skills) but no co-emission map of the current plan. Fix: when dispatcher constructs the hub call, attach `co_emission_context: {downstream_consumers: [npc_step_id], upstream_dependencies: []}` to the hub input.

- `[FRAGMENT-GAP]` **Effect-type × category matrix as a HARD invariant.** The hub prompt (line 10) says the matrix "is documented in the tool prompt" — the hub may suggest both; the tool validates. Fine. But the hub can ALSO check it before emitting the spec, sparing the tool an invalid input. Cheap win, but designer choice (overhead vs. defense-in-depth).

- `[FRAGMENT-GAP]` **`recent_registry_entries` shape.** Same diversity-of-shape concern as quests. The hub needs to see effect.type frequency, magnitude frequency, geometry combatTag frequency. Currently it's a flat list of recent skill metadata. Enriching it with frequency aggregates would let the hub explicitly diversify ("the last 5 skills in this region were all `devastate` damage — prefer non-damage next").

### 4.6 Rung 5 — `wes_execution_planner` (one bundle → one plan DAG)

The planner sees the full bundle and decides whether to emit a `skills` step. Skills are in scope at tier 2+ per the planner prompt (`Tier 2: Allowed: 1-2 of [material, node, hostile, skill]`).

What's MISSING:

- `[FRAGMENT-GAP]` **Skill-specific firing guidance.** The planner prompt's scope rules mention skills generically. There's no guidance on WHEN a skill should be emitted vs. when an existing skill should be referenced:
  - A skill should fire when: the WNS thread implies a *technique* the world is teaching (faction-specific moves, locality-specific crafts, evolutionary skill progressions).
  - A skill should NOT fire when: the WNS thread is purely narrative shift (faction conflict without new combat shape, economic restructuring without new gathering technique).
  - Designer tuning task: add a planner-prompt clause that gates skill emission against thread content, not just tier.

- `[FRAGMENT-GAP]` **Plan dependency clarity for skill-NPC-quest co-emission.** The planner's example (`prompt_fragments_wes_execution_planner.json:15`) shows the canonical pattern: skill (s3) → NPC (s6, depends on skill) → quest (s8, depends on NPC). But the planner prompt doesn't articulate that skills SHOULD be emitted first in any plan that has an NPC with `is_questgiver: true` and a quest reward of `skill_hint`. The pattern works in the example but isn't enforced by prose. Designer tuning task.

### 4.7 Rung 6 — WNS NL4-NL7 weaver emits `<WES purpose="new-skill">`

Confirmed: `narrative_fragments_nl4.json:19` lists `new-skill` in the purpose-bucket allow-list with the example body "A craft or technique the arc is teaching." NL3 has it as a "typical purpose" at district scope. NL5+ has it at higher scope.

What's MISSING:

- `[WNS-GAP]` **Skill-specific firing guidance in the `_wes_tool` fragment.** Same shape of gap as quests had. The current NL4 prose says "new-skill: A craft or technique the arc is teaching." Too vague. Should fire when:
  - A new faction's combat doctrine has emerged in the narrative ("the copperlash riders are a new signature presence").
  - A new craft discipline is taking root ("the moors-copper is being smithed in a new way").
  - An evolutionary thread is closing ("the apprentice smiths have surpassed their masters" → tier-3 evolution of an existing skill).
  - A character archetype has stabilized in the narrative such that they need a signature move (a captain needs an officer skill, a hermit needs a wisdom skill).
  Designer tuning task: tune the `_wes_tool` body for each NLn layer to give clearer firing guidance per purpose-bucket. Specifically for new-skill: when, what discipline, what lineage.

- `[WNS-GAP]` **The directive_text shape for new-skill.** The body of `<WES purpose="new-skill">body</WES>` is freeform. Per the NL4 example: "Knows skills copperlash_gash and ambush_call" — this is a hostile referencing skills, not a new-skill directive. A good new-skill directive: "A tier-2 melee whip-strike that opens bleeding wounds, signature of moors raiders, teachable by their captains." That's enough for the planner to emit `[skills]` with a slot that fits the tool prompt. The fragment should tell the weaver: name the discipline (combat / smithing / etc.), name the lineage (faction or NPC), name the mechanical signature (one or two words about effect — "bleed", "chain", "freeze"), name the tier band.

### 4.8 Rung 7 — WNS reads WMS L2 interpretations

`progression_skills.py` produces `skill_learned` and `skill_used` rows. These feed `${wms_context}` in the NL weavers. Solid — no fragment gap here. The signal "the player has learned X skills lately" is available; the signal "this skill is rising in regional use" is available via the `count_filtered` evaluator path.

The one creative-extraction worth surfacing: the WMS knows WHICH skills the player learned (each row has `affects_tags=["skill:{skill_name}"]`). The L3+ narratives can use this — "the player has been learning fire skills" leads to NL5 deciding the world's mystical-domain story bends fire-themed, which then biases future `<WES purpose="new-skill">` directives toward fire skills. Closed loop. Doesn't require WMS changes; just narrative tuning.

### 4.9 Rung 8 — WMS L2 evaluators

`progression_skills.py` is already implemented and reviewed (per `feature_designer_ledger_walkthrough_state.md` memory, §1 was locked which covered evaluator review). Solid.

Adjacent evaluators that feed skill quality:
- `combat_kills_regional_low_tier.py` / `_high_tier.py` — when the player kills hostiles using a skill, those rows tag both the kill AND the skill via `record_skill_used`. The skill's "this is what it kills" lineage exists in StatStore.
- `social_npc.py` — when the player interacts with a teacher NPC, the row carries the NPC's faction; combined with the skill_learned row, we get "the player learned X skill from a Y-faction NPC." This is the cross-entity composition rung that grounds future skill generation.

---

## 5. Per-field provenance table

For EVERY field that the LLM authors (so excluding `iconPath` which the loader defaults), where the upstream signal comes from. The 9-rung WMS column applies when a `[WMS-GAP]` might be tempting — walk it in writing.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `skillId` | Tool prompt + hub `flavor_hints.name_hint` + registry-uniqueness check | name_hint flows from hub which got it from planner's `step.intent` | Yes | — |
| `name` | Tool prompt + `flavor_hints.name_hint` | Hub crafts from `step.intent` + `narrative_anchor` | Yes | — |
| `tier` | Hub `hard_constraints.tier` | Planner picks from firing_tier scope rules + `directive_text` weight | Yes | — |
| `rarity` | Tool prompt + `hard_constraints.rarity` | Hub picks from 6 based on `step.intent` + tier weight | Yes | — |
| `categories` | Tool prompt | Tool picks 1-3 from allow-list, guided by `effect.category` + `narrative_anchor` | Yes | — |
| `description` | Tool prompt | Tool's own composition; MUST mirror combatTags/combatParams literally | Partial — prose-discipline rule not yet explicit | `[FRAGMENT-GAP]` — add the "description = literal English of dispatch" contract to tool prompt |
| `narrative` | Tool prompt | Tool's voice — BUT teacher's narrative is missing | Partial | `[WES-SCHEMA-GAP]` — see 4.4. Add `${teacher_intent_anchor}` to tool input. |
| `tags` | Tool prompt | Tool picks 2-5 from descriptive tag allow-list | Yes (locked) | — |
| `effect.type` | Hub `hard_constraints.effect_type` (optional) → Tool validates | Hub picks from 10 based on `step.intent`; tool may override if hub's pick violates matrix | Yes | — |
| `effect.category` | Hub `hard_constraints.effect_category` (optional) → Tool validates against matrix | Hub picks from matrix; tool enforces | Yes | — |
| `effect.magnitude` | Hub `hard_constraints.magnitude` (optional) | Hub picks from 4 based on tier + intent | Yes | — |
| `effect.target` | Hub `hard_constraints.target` (optional) | Hub picks from 4 based on `step.intent` | Yes | — |
| `effect.duration` | Tool prompt | Tool picks from 5 based on effect.type + magnitude | Yes | — |
| `effect.additionalEffects[]` | Tool prompt | Tool composes secondary effects; empty `[]` default | Yes | — |
| `cost.mana` | Tool prompt | Tier band guidance | Yes | — |
| `cost.cooldown` | Tool prompt | Tier band guidance + effect.duration weight | Yes | — |
| `requirements.characterLevel` | Tool prompt | Tier band guidance | Yes | — |
| `requirements.stats` | Tool prompt | Tool picks STR/DEF/VIT/LCK/AGI/INT subset matching `effect.category` + `narrative_anchor` | Yes | — |
| `requirements.titles[]` | Cross-ref hint when applicable | `cross_ref_hints.required_title_id` (when title-gated; future) | Yes (when threaded; currently almost always `[]`) | — |
| `combatTags[]` | Tool prompt | Tool picks from `tag-definitions.JSON` allow-list, matching `narrative_anchor` + effect.type | Yes | — |
| `combatParams` | Tool prompt | Tool tunes per combatTag default-params from tag library + tier scaling | Yes | — |
| `evolution.canEvolve` | Tool prompt | Defaults to `false`; true when tier 1-2 has a clear tier 2-3 successor in mind | Yes | — |
| `evolution.nextSkillId` | Cross-ref hint when chain-emitting | `cross_ref_hints.next_skill_id` from hub when chain emerged | Yes (when threaded; rare otherwise) | — |
| `evolution.requirement` | Tool prompt | Tool writes lineage-rooted prose requirement | Yes | — |

### 5.1 WMS-GAP walk — the one place I was tempted

The one piece of context I almost flagged `[WMS-GAP]` for: **player's recent skill-learning patterns + skill-use patterns**, for biasing new-skill generation toward what the player will actually equip.

The use case: at WNS firing time, the weaver wants to know "the player has been LEARNING but not USING fire skills lately — they hoard utility but fight melee." That signal would bias the WES toward emitting melee-utility hybrids, or toward emitting a skill that bridges the gap (a fire-touched melee strike).

I walked the 9 rungs:

1. **Direct query**: Is there a WMS event "player learning pattern shifted to melee"? No single event has this exact shape. **Fail.**
2. **Adjacent events**: Are there `skill_learned` events filtered by skill category? Yes — each row carries `affects_tags=["skill:{skill_name}"]` and the skill's categories. Querying `event_store.query(event_type="skill_learned", limit=20)` and joining with `SkillDatabase.skills[skill_id].categories` gives the categorical learning histogram. **Pass.**
3. **Negative patterns**: Has the player NOT used certain learned skills? Yes — compare `skills_learned` records vs. `skills.used` keys in StatStore. The delta is "hoarded skills." StatStore at lines 467-480 of `stat_tracker.py` records both. **Pass.**
4. **Aggregation**: `daily_ledger` may already track skill-category-usage diversity, or it can be added. Existing 33 L2 evaluators include `progression_skills.py` which already aggregates skill_used counts with severity bands. **Pass.**
5. **Trajectory**: `progression_skills.py` evaluates count over a time window with `lookback_time`. Adding a per-category breakdown is a same-file extension, not a new evaluator. **Pass with extension.**
6. **Cross-layer climb**: NL3+ narrative can already interpret "the player has been learning many fire skills" if the wms_context render includes it. The render is char-budgeted (600 chars by default); if it filters skill-learning rows, those are the rows that need to make the cut. **Pass with prompt tuning at the WNS render side.**
7. **Cross-entity composition**: "Skills learned from NPC X + NPC X's faction + the localities the player learned them in" = available by joining skill_learned rows with social_npc rows by approximate game-time. Not a direct query, but a composable one. **Pass with query layer.**
8. **Stat / ledger lookup**: StatStore is the gold mine. `progression.skills_learned.{skill_id}` counts; `skills.used.{skill_id}` counts; combined gives the hoard/use ratio per skill. Per-category aggregation by joining with `SkillDatabase`. **Pass — deterministic.**
9. **Trigger history**: Has the `<WES purpose="new-skill">` been firing on this player's locality recently? `ContentRegistry.reg_skills` has timestamps; `recent_registry_entries` already carries the most recent. **Pass.**

**Verdict**: NOT a WMS gap. Every signal is available through (2) skill_learned event rows + (8) StatStore + (3) cross-table composition. The gap is at the **WNS render layer** — the `${wms_context}` 600-char budget may be evicting skill-pattern rows in favor of combat/economy rows. Marker: `[FRAGMENT-GAP]` on the WNS context renderer's row-selection logic (favor skill-pattern rows when the firing tier is considering a `new-skill` purpose).

So **zero `[WMS-GAP]` markers in this trace.** The WMS substrate gives us everything; the gaps are at the WNS→WES boundary (bundle leak) + at the WNS render row-selection + at the prompt input layer (variables not threaded through). Same pattern as quests. Means the WMS sacred work is solid.

---

## 6. Cross-references with other features (personal shopper)

Sharing vs. flavor-divergent across the other 9 features.

### 6.1 Heavy shared infrastructure (use as-is)

- **WNS NL4-NL7 narrative weavers** — shared with EVERY content-generating feature. `new-skill` is already in the NL4 purpose-bucket allow-list.
- **WES Execution Planner** — shared. Scope-by-firing-tier rules govern skills (tier 2+).
- **WMS L2 evaluators + L2-L7 chronicle** — read-only shared. `progression_skills.py` already does the skill-side interpretation work.
- **Tag system + `tag-definitions.JSON`** — shared allow-list. **CRITICAL for skills:** `combatTags` and `combatParams` ARE the tag system. Skills are the most tag-load-bearing feature after hostiles. Adding a tag through any tool affects skills.
- **`BundleToolSlice`** — shared by all hubs. The `parent_summaries` leak (§4.4) affects skills equally. **Fix in one place benefits all 8.**
- **Orphan detector** — shared. Cross-ref enforcement for `evolution.nextSkillId`, `requirements.titles[]`, and (when we add it) `cross_ref_hints.taught_by_npc_id`.

### 6.2 Skill-specific shared with adjacent features

The skill tool is **deeply coupled to NPCs** and moderately coupled to **Quests**, **Hostiles**, and **Titles**. This is the most cross-coupled feature in the pipeline.

- **NPC teacher coupling** (THE BIG ONE).
  - **Forward** (NPC → Skill): NPC v3 has `services.teachableSkills: [skillId]`. When `canTeach: true`, the NPC offers a teach interaction at runtime. The NPC's `personality.reaction_modifiers.SKILL_LEARNED` triggers when the player learns ANY skill (optionally filtered by `skill_match`). This is the only formal cross-ref between the two.
  - **Reverse** (Skill → NPC): NONE in the current schema. **This is the schema gap from Agent 1.** Add `taught_by: [npc_id]` to SkillDefinition. The reverse pointer lets the skill's `narrative` be written in a voice that knows its teacher.
  - **Co-emission**: when a plan has `[skills, npcs]`, the planner emits skills first (DAG ordering); the NPC's `teachableSkills` references the skill IDs. The skill tool gets `flavor_hints.teacher_intent_anchor` (proposed addition) — a string describing the teacher NPC's intent / archetype / lineage, derived from the planner's step.intent for the NPC step. This is the deterministic spice the skill tool needs without waiting for the NPC's full narrative.
  - **At runtime**: the NPC teaches via dialogue → `SkillManager.learn_skill` → `SkillUnlockDatabase` needs an unlock record for the skill. **Currently the WES dispatcher does NOT emit a SkillUnlock record alongside the skill.** Generated skills are only learnable via auto level-up path until a SkillUnlock is hand-authored. Skill ledger TODO.
  - **Recommendation to NPCs agent**: when your tool emits an NPC with `canTeach: true` and `teachableSkills: [skill_id]`, the dispatcher should ALSO write a SkillUnlock record linking the skill back to the NPC. This is an orchestrator-side enhancement, not an NPC-tool-side one — but coordinate.

- **Quest reward coupling** (RECIPROCAL).
  - **Forward** (Quest → Skill): Quest v3 has `rewards_prose.skill_hint: skillId or null`. When set, the reward materializer grants the skill at turn-in (per `01-quests.md` rung 4.2 / table 5).
  - **Reverse** (Skill → Quest): NONE currently. Add `cross_ref_hints.rewarded_by_quest_id` per Agent 1 §6.4. The reverse pointer lets the skill's flavor reference the quest line ("an oath-mark earned from the salt-reach hunt"). Hub accepts and propagates to `flavor_hints.quest_anchor`.

- **Hostile coupling** (THE CONFUSING ONE).
  - **Forward** (Hostile → Skill): Hostiles can have `specialAbilities` referencing skill IDs. A hostile using a skill is the inverse of the player using a skill — same dispatch through effect_executor, but the hostile is the source. The planner example shows `copperlash_rider` "knowing" `copperlash_gash`.
  - **Reverse** (Skill → Hostile): NONE currently. Add `cross_ref_hints.signature_skill_of_hostile_id` to skill tool. When set, the skill is "the move the hostile is known for" — flavor accordingly (tier-match the hostile, combatTag-match the hostile's archetype).
  - **Co-emission**: same pattern as NPC. Skills emit first, hostile references them. The skill tool needs `flavor_hints.hostile_intent_anchor` — the hostile's intent string from the planner. *(Note: a skill can be BOTH a hostile's signature AND a teachable. Captain Vell teaches Copperlash Gash; copperlash_rider also uses it. The schema should support both — `taught_by: [npc_id]` AND `signature_skill_of: [hostile_id]` independently set.)*
  - **Recommendation to Hostiles agent**: same shape as NPCs. When your tool emits a hostile with `specialAbilities: [skill_id]`, ensure the dispatcher passes the reverse cross-ref to the skill tool.

- **Title coupling** (LIGHT).
  - **Forward** (Skill → Title): `requirements.titles[]` — skill cannot be learned until player has the title. The "skill-tree gate" path.
  - **Reverse** (Title → Skill): IF a title's effect grants a skill ("Master Smith I gives you Smith's Focus"), that's a `title.grants_skill_id` field on the title side. Most titles don't grant skills; the ones that do are the prestige-track ones.
  - **Co-emission**: rare. Most title↔skill linkage is hand-authored at the canonical level.

- **Material / Node coupling** (THEMATIC, NOT FORMAL).
  - Skills can REFERENCE materials in their narrative ("a lash-strike with a copper-weighted whip"), but there is NO formal `requires_material_id` cross-ref. The whip itself is an equipment item; the skill is the move. No coupling needed at the schema level — coupling lives at the narrative_anchor / prose_fragment layer.
  - However: gathering/crafting skills (like Bountiful Harvest, Miner's Fury) are thematically tied to specific material categories. Skill ledger TODO: consider whether `effect.category: mining` skills should optionally reference a `materialCategoryAffinity: [str]` field for finer-grained dispatch ("this skill boosts ONLY copper mining"). Designer call — current schema is intentionally coarse (effect.category is enough granularity).

- **Chunk coupling** (THEMATIC ONLY).
  - Skills have no formal chunk cross-ref. Chunks don't host skills directly. The thematic coupling is through the NPC teacher who lives in the chunk — Captain Vell lives in `dangerous_copper_moors`, teaches Copperlash Gash, the skill IS "of the moors" but through transit.

### 6.3 Where skills diverge (flavor not shareable)

- **The tag-driven dispatch system** — skills are the principal LLM-generated consumer of `tag-definitions.JSON`. Hostiles use tags too, but for AI behavior + on-hit auras; skills use them for player-action dispatch. The mechanical contract (description-must-match-dispatch) is unique to skills.
- **The matrix constraint** — effect.type × effect.category is a HARD invariant in the skill tool. No other feature has an equivalent matrix lock.
- **Mana / cooldown / characterLevel banding** — the tier band system is shared with other features but applies most tightly here because skill costs feed combat balance directly.
- **No lifecycle / archive** — skills are forever once learned. No quest-style archive. They can be UNLEARNED via class change or item respec, but not "archived with outcome." So the WMS-side narrative continuity model is simpler: skill_learned, skill_used over time. That's it.

### 6.4 Recommendations to other agents

- **NPCs agent**: When your tool emits a teacher (canTeach=true), ensure the dispatcher writes a SkillUnlock record so the skill is actually NPC-teachable at runtime. Also: your NPC's `personality.reaction_modifiers.SKILL_LEARNED` is a great hook — make sure it can carry `skill_match: [skillId]` so a teacher reacts uniquely when their OWN teachable is learned by the player (vs. ANY skill learned).
- **Hostiles agent**: Same shape — when your hostile has `specialAbilities: [skill_id]`, the reverse cross-ref `signature_skill_of_hostile_id` should reach the skill tool via hub `cross_ref_hints`.
- **Quests agent**: Already covered in `01-quests.md`. `rewards_prose.skill_hint` cross-ref is reciprocal — when set, the skill tool should know "this is a quest-reward skill."
- **Titles agent**: When your title has `grants_skill_id: [skill_id]`, ensure cross-ref discipline. And: think about whether your tool should accept `cross_ref_hints.granting_skill_id` for the reverse case ("this title is the prerequisite for learning Master's Edge").
- **Materials / Nodes / Chunks agents**: Light coupling. Skills don't formally cross-ref you. But narrative coherence matters — if your tool's locality is `salt_moors` and the skill being co-emitted is for `salt_moors`, the narrative_anchor strings should be consistent.
- **WNS / Planner+Supervisor agent**: **The single most impactful intervention** for skill quality (shared with quests) is closing the `BundleToolSlice` parent_summaries leak. Second-most: tune the `_wes_tool` body in narrative_fragments_nl3/nl4/nl5 to give the weaver clearer guidance on WHEN to fire `<WES purpose="new-skill">` and WHAT shape the directive should take ("name discipline, name lineage, name mechanical signature, name tier"). Third-most: enrich `${wms_context}` with skill-pattern rows when the firing tier is considering a `new-skill` purpose.

---

## 7. Storage / timing design

### 7.1 The pre-generated skill pool — the cold-storage architecture

Skills, like quests, are pre-generated and cold. The architecture:

- **Generation event**: WNS firing emits `<WES purpose="new-skill">` → planner → hub → tool → `SkillDefinition` JSON commits to `ContentRegistry.reg_skills` and writes to disk as `Skills/skills-generated-<timestamp>.JSON`.
- **Reload**: `database_reloader.reload_for_tools(["skills"])` is called as part of commit. `SkillDatabase.reload()` (CONFIRM this exists; see §4.3 risk) re-reads canonical + generated siblings.
- **Available for learning**: from this moment, `SkillManager.can_learn_skill(skill_id, character)` resolves the skill. If `requirements.characterLevel` etc. are met, the skill appears in `get_available_skills(character)`.
- **Unlocked via**: depends on `SkillUnlock` record (see §2.1 / §4.3 gap):
  - If no unlock record → only the auto-level-up path includes the skill. Players see it on level-up if they meet requirements.
  - If unlock record has `unlockMethod: NPCInteraction` → only the named NPC can teach it.
  - If unlock record has `unlockMethod: QuestCompletion` → only granted on quest turn-in.
  - If `unlockMethod: Achievement` → only granted on title earn (or other discrete trigger).

### 7.2 Pool sizing & refresh cadence

How many pre-generated skills should sit pre-existent per region/discipline? Designer-tunable, but recommended starting point:

- **Per discipline-region pairing**: 5-10 skills, distributed across tiers. A salt-moors region should have 5-10 skills spanning combat + crafting + utility.
- **Refresh trigger**: when WNS fires `<WES purpose="new-skill">` AND the locality matches. Otherwise refresh is cooldown-gated (suggest: every N game-days).
- **Stale skills**: unlike quests, skills don't expire from the pool. Once committed, they stay forever. A skill that's never learned by any player is dead-weight in the DB but not actively harmful. **No staleness model needed for v4.** *(Future: a player-pattern modifier could surface "the player has never used these 17 skills they learned" and the world stops generating that pattern. Out of scope.)*

### 7.3 Skill learn timing

The skill must exist BEFORE the player encounters the unlock condition. The pipeline:

1. WES generates skill → commits → reloads. **Cascade time** (no player visibility).
2. NPC with the teachable spawns at chunk-time. **Chunk-load time** (player wanders into chunk, NPC visible).
3. Player approaches NPC → dialogue → "teach me" interaction → `SkillManager.learn_skill`. **Runtime, masked by dialogue beat.**

The teach dialogue line itself is from the NPC's speechbank.quest_offer / canTeach_offer (or analogous; confirm NPC speechbank shape includes teach-offer line). **If it doesn't, that's an NPC v3 schema gap, not a skill gap.**

### 7.4 At-runtime cost adaptation? No.

Unlike quests where rewards adapt at turn-in (via `wes_quest_reward_adapt`), skills do NOT adapt at learn-time or use-time. The `cost.mana`, `cost.cooldown`, `combatParams.baseDamage` are fixed at generation time. PlayerSkill level scales them at use-time (linear +10% per level via `get_level_scaling_bonus`), but the static definition is immutable.

This is a designer call, not a gap. A skill that re-adapts at learn-time would be tempting ("scale damage to player's actual STR at learn-time") but breaks the social contract that other players who learn the same skill get the same definition. Keep skills cold; keep PlayerSkill level scaling the only dynamic.

### 7.5 The unlock-record gap (REPEAT for emphasis)

The biggest plumbing issue surfacing through this trace: **generated skills don't get SkillUnlock records.** Without them, NPCs can't teach them at runtime even when `teachableSkills` is set. The orchestrator-layer fix:

```
When dispatcher commits a skill with cross_ref_hints.taught_by_npc_id set:
  ALSO write a SkillUnlock record:
    unlockId: f"unlock_{skill_id}"
    skillId: skill_id
    unlockMethod: "NPCInteraction"
    conditions: [{type: "npc_taught", npcId: taught_by_npc_id}]
    cost: {} (or designer-tunable default)
```

This belongs in `content_registry.commit` or a new helper. Skill ledger TODO. Without it, the entire "Captain Vell teaches Copperlash Gash" loop is broken end-to-end.

---

## 8. Diversity / creativity design

User direction (from quote bank): *"the competition is quests that could be systematically generated, that is the benchmark we must be above; so what information is required for the [Skill] JSON to have that."*

Skills have one diversity superpower the other features don't have: **the tag-combination space is enormous and most of it is unexplored.**

### 8.1 The tag-combination space

The tag library carries:
- 12 damage types (physical/slashing/piercing/crushing/fire/frost/lightning/poison/holy/shadow/arcane/chaos/energy)
- 8 geometry tags (single_target/chain/cone/circle/beam/projectile/pierce/splash)
- 10 status_debuff tags (burn/freeze/chill/slow/stun/root/bleed/poison_status/shock/weaken)
- 8 status_buff tags (haste/quicken/empower/fortify/regeneration/shield/barrier/invisible)
- 13 special tags (lifesteal/vampiric/reflect/thorns/knockback/pull/teleport/summon/dash/charge/phase/execute/critical)

Crudest count: 12 × 8 × 10 × 13 = 12,480 quadruple combinations. Most are nonsensical (fire + freeze conflict; summon + pierce is meaningless). Realistically the "sensible" combination space is in the low thousands. **The existing skill library has 30 skills in `skills-skills-1.JSON` and 6 in `skills-testing-integration.JSON`.** We've explored 1% of the space.

Every new skill is an opportunity to land in an unexplored region of this space. The hub's diversity dial should EXPLICITLY check recent registry combatTag combinations and avoid recombinations.

### 8.2 Effect-type rotation

10 effect types in allow-list: `empower, quicken, fortify, restore, regenerate, enrich, elevate, pierce, devastate, transcend`. The hub MUST be discouraged from defaulting to `devastate` (damage-focused) for every combat skill. Implementation:
- `recent_registry_entries` should expose effect.type frequency. Hub prompt should say "if the last 5 skills in this region were all devastate, prefer fortify/restore/quicken next."
- Per-discipline bias: combat skills naturally bias toward `devastate`/`pierce`/`fortify`; crafting toward `quicken`/`empower`/`elevate`; gathering toward `enrich`/`elevate`/`transcend`. Within each natural cluster, rotate.

### 8.3 Tier × magnitude × target stretches

The current skill library is heavily biased to tier 1-2 with `target: self` (43 of 36 skills target self). Combat skills target `enemy`; AOE skills target `area`. The tag-test skills (Meteor Strike, Chain Lightning, Arctic Cone, Shadow Beam, Vampiric Aura, Gravity Well) demonstrate the AOE/area space.

Recommended distribution per emission batch:
- 50% `target: self` (buffs, gathering enhancements, crafting improvements)
- 30% `target: enemy` (single-target combat)
- 15% `target: area` (AOE combat)
- 5% `target: resource_node` (specialized gathering buffs)

Magnitude bias: `moderate` is the most common; encourage `minor` for utility / `major` for signature / `extreme` for tier-4 legendary picks.

### 8.4 CombatTag combination diversity

The most powerful diversity dial. The hub prompt should be augmented with:
- "When emitting a combat skill, vary the geometry combatTag across the batch (some single_target, some chain, some cone, some beam, some circle)."
- "When the narrative_anchor implies a damage type (`fire`, `frost`, `lightning`), the LLM picks that as the damage combatTag — but the geometry and status combatTags should still vary."
- "Status combatTag is the FLAVOR DIFFERENTIATOR. A `fire + single_target + burn` skill and a `fire + cone + weaken` skill feel completely different. Pair status combatTags with the lineage anchor — moors raiders bleed (`bleed`), salt-drowned freeze (`chill`), cliff-spirits stun (`stun`)."

### 8.5 Lineage-anchored creativity

This is where skills outpace stagnation. A skill named "Power Strike" with `[physical, single_target]` is a 1990s slot-machine skill. A skill named "Copperlash Gash" with `[physical, single_target, bleed]` AND a narrative line "Moors raiders favor the copperlash — a short whip weighted with ore slugs that draws deep cuts the salt wind salts further" is a skill that BELONGS somewhere.

Lineage anchors come from:
- The teacher NPC's faction + locality + narrative (via `flavor_hints.teacher_intent_anchor`).
- The host hostile's archetype + culture (via `flavor_hints.hostile_intent_anchor`).
- The quest's prose summary (via `flavor_hints.quest_anchor`).
- The chunk's biome + cultural anchors (via the WNS firing layer's narrative_context).

The hub prompt should be augmented to: "When you have ANY of these anchors, your `name_hint` and `prose_fragment` MUST reference the anchor by proper noun. 'Copperlash Gash' references the copperlash; 'Salt-Whisper' references salt. The skill's `narrative` field will inherit your prose_fragment."

### 8.6 Reward-style variance (analog of quest §8.7)

Skills don't have rewards. But they DO have effect.additionalEffects[] — the "compound skill" pattern. A skill with a single primary effect is one shape; a skill with a primary + 1 additional is another (Battle Fury = empower+quicken; Alchemist's Insight = quicken+empower; Refiner's Touch = quicken+elevate). Compound skills feel richer.

Recommended distribution:
- 70% single-effect (primary only, `additionalEffects: []`)
- 25% double-effect (primary + 1 additional)
- 5% triple-effect (rare; only for tier 3-4 legendary picks)

### 8.7 Emergent proper nouns

Per `quest_lifecycle_design.md` and the NL4 fragment: the `emergent_entity` tag allows the LLM to coin proper nouns. Caps: 2 per fragment, 5 per run. Skills inherit these — if NL4 invented "the Moors-Stone Tradition" as a thread headline, the skill can be named "Moors-Stone Stride" or have its narrative reference the Tradition. Designer-review surface.

### 8.8 Evolution chains as a creativity multiplier

`evolution.canEvolve` + `evolution.nextSkillId` is currently rare in the library. **Underutilized.** A 3-skill chain (Tier 1 → 2 → 3) is fundamentally richer than three flat-tier skills. Each evolution stage can:
- Add a new combatTag (Copperlash Gash → Copperlash Bloom adds `chain`; → Copperlash Reaper adds `execute`).
- Upgrade a combatParam (baseDamage 40 → 60 → 90; bleed_damage_per_second 3 → 6 → 10).
- Tighten lineage ("apprentice of Vell" → "veteran of the line" → "captain of the line").

The planner should emit evolution chains as a single plan step with count=3 (skill, skill, skill linked by evolution.nextSkillId). The hub then dispatches 3 specs with the chain linkage in `cross_ref_hints.next_skill_id`.

---

## 9. Speculative future endpoints

Things this trace surfaces as natural next-step LLM endpoints.

### 9.1 `wes_skill_evolution_chain_planner` — chain-aware multi-skill emission

The current `wes_hub_skills` emits one skill per spec. A 3-skill evolution chain requires 3 specs with cross-references — workable but coordination-heavy at the hub layer. A specialised planner step:

- **Trigger**: WNS NL4+ fires `<WES purpose="new-skill-evolution-chain">` (new bucket).
- **Inputs**: bundle + chain length target + the lineage/discipline anchor.
- **Outputs**: a 3-step plan with evolution_chain set, each step a skill spec.
- **Then**: fans out to existing `wes_hub_skills` + `wes_tool_skills`.

Endpoint count: +1 LLM task. Probably premature — start with the planner emitting `[skills, skills, skills]` with evolution.nextSkillId linkages and see if quality holds.

### 9.2 `wes_skill_balancer` — post-generation balance check

Skills are the feature where balance leakage is most player-visible (a too-strong skill breaks combat; a too-weak skill feels dead). BalanceValidator is designed-not-built (per CLAUDE.md). When it ships, it should:

- **Trigger**: after skill JSON is generated by `wes_tool_skills`, before commit.
- **Inputs**: the skill JSON + the tier's stat-range allow-list + the existing same-tier skill library.
- **Outputs**: pass/rerun/reject verdict + a 1-2 sentence rationale.
- **Where it lives**: the existing `wes_supervisor` already does shape validation; balance is the natural extension. Could be folded into supervisor (probably the right call) or split into a dedicated `wes_balance_supervisor`.

Endpoint count: +0 (fold into supervisor) or +1 (split).

### 9.3 `wes_skill_voice_re-narrator` — narrative refresh at teach-time

When the player approaches the teacher NPC, the skill's `narrative` was written with `flavor_hints.teacher_intent_anchor` (an INTENT string, not the full teacher narrative — see §4.4). At teach-time, the teacher's FULL narrative now exists. A small endpoint could re-render the skill's narrative with the full teacher context:

- **Trigger**: at teach-dialogue open, when the skill's recorded `taught_by_npc_id` exists.
- **Inputs**: the skill's static JSON + the teacher NPC's full narrative + voice anchor.
- **Outputs**: a re-rendered narrative line that incorporates the teacher's specific voice.
- **Latency budget**: 1-2 second dialogue masking. Acceptable.

Endpoint count: +1 LLM task. Probably premature — the intent_anchor approach in §4.4 should get us 80% of the way for v4. Add this if teaching beats feel voice-disconnected in playtest.

### 9.4 `wes_skill_modifier` — narrative-driven adaptation

Per the quest modifier (§9.1 of `01-quests.md`): if the WNS thread the skill belongs to evolves, the skill could shift. A salt-moors skill where the moors-stone has been DESTROYED in the narrative could have its `narrative` field updated to past-tense ("the technique passed down from the moors-stone, before its fall"). The mechanical fields stay locked; only the narrative shifts.

- **Trigger**: WNS thread movement past N stages since skill emission.
- **Inputs**: skill + current thread state.
- **Outputs**: a patch JSON — `{narrative?}`. Apply at next reload.
- **Latency budget**: cascade time. Not player-visible.

Endpoint count: +1 LLM task. Speculative — only worth it if narrative-shift over time is a player-visible feature (depends on how many sessions a player typically plays).

### 9.5 `wes_skill_player_signature` — player-driven skill emission

The most ambitious one. After enough play, the WMS knows the player's combat fingerprint (uses bleed skills + likes chain geometry + favors STR builds). The world could emit a skill TAILORED to the player's pattern at a tier the player is approaching. "The Salt-Drowned have noticed you. They have a name for what you do." — and a new skill named for the player's pattern lands.

- **Trigger**: WMS L4-L5 evaluator detects sustained player-pattern over N game-days (via StatStore + skill_used categorical aggregation).
- **Inputs**: player's StatStore signature + the existing skill library's coverage of similar patterns + the player's locality.
- **Outputs**: a SkillDefinition tuned to the player.
- **Where it goes**: into a SPECIAL `Skills/skills-player-signature-<timestamp>.JSON` — a different reload pool, not mixed with regular generated skills.

Endpoint count: +1 LLM task. Long-term post-release feature. Closes the "the world is reacting to YOU" loop in the most direct way possible.

### 9.6 Big-picture: the 2-endpoint skill pipeline could grow to 5-6

Current: `wes_tool_skills` + `wes_hub_skills` (2).
With speculatives: + `wes_skill_evolution_chain_planner` + `wes_skill_balancer` + `wes_skill_voice_re-narrator` + `wes_skill_modifier` + `wes_skill_player_signature` (potentially 7 total).

Most fold into existing tasks (balancer into supervisor; chain planner into the main planner). Pragmatic count: **3-4 endpoints** at maturity. The two shipped now are the load-bearing minimum.

---

## End

Four load-bearing fixes this trace surfaces, in priority order:

1. **Close the `BundleToolSlice` parent_summaries leak.** Single fix benefits skills, quests, and all 6 other content tools. The single largest source of "skill disconnected from lineage/teacher/anchor" failure.

2. **Add `taught_by_npc_id` reverse cross-ref + `teacher_intent_anchor` flavor_hint + SkillUnlock auto-emission.** The three together close the NPC teacher coupling end-to-end. Without them, generated skills are theoretically learnable by NPCs but practically aren't, AND their narrative doesn't know its teacher's voice. This is THE skill-feature integration item.

3. **Tune the WNS `_wes_tool` body for `new-skill` directives** across NL3/NL4/NL5. The current "A craft or technique the arc is teaching" is too vague. Give the weaver explicit firing guidance: name discipline, name lineage, name mechanical signature, name tier. Per memory `feedback_wns_prompts_must_be_tag_indexed.md` — should be tag-indexed micro-contexts, not monolithic.

4. **Enforce the description-vs-dispatch contract.** Add explicit prose-discipline rule to `wes_tool_skills` prompt: "description is the literal English rendering of combatTags + combatParams." Subtle but the failure mode (1.3.d) is hard to debug at playtest if it sneaks in.

Everything else in this trace — diversity dials, modifier-AI, evolution chains, player-signature skills — is downstream of those four.
