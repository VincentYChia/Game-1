# Feature Trace 01 — Quests

**Wave:** 1 (Reference / Calibrator)
**Owned endpoints:** `wes_tool_quests`, `wes_hub_quests`, `wes_quest_reward_pregen`, `wes_quest_reward_adapt`
**Final output artifact:** `QuestDefinition` JSON (one per LLM call from `wes_tool_quests`), materialised at receive-time and again at turn-in via the two reward endpoints.
**Date:** 2026-05-26

> "The competition isn't no quests. The competition is quests that could be systematically generated. That's the benchmark we must be above."

This trace is anchored on a player who has just opened a scroll. Every decision below is in service of that scroll feeling like it came from a person who knows the moors, knows what just happened in the moors, and knows the player.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

A scroll appears in the player's hand — visually unfurling over 2-3 seconds, a roll of parchment in a wax-broken seal. Text reveals as the scroll opens, line by line: a title in a hand the player can read as the giver's, a short brief, a long brief in the giver's voice (the way Captain Vell talks about the moors-stone is not how Brother Galen talks about the cliffside chapel), then an "in return" line that hints — but does not enumerate — what the giver promises in exchange. The player accepts. The scroll rolls up. They walk into the world.

That is the entire experience the quest pipeline exists to serve. Everything we generate is in service of: (a) the moment the scroll opens, (b) the work the player does between then and turn-in, (c) the moment the giver speaks back at turn-in and the rewards land.

### 1.2 Timing budget — the architectural constraint

The scroll unfurl animation buys us 2-3 seconds of latency masking. Real-LLM (Claude Sonnet, occasionally Ollama) round-trip on the full WNS → WES → tool chain is 5-20 seconds for a multi-step plan. That gap is what kills the experience.

User direction (gold-standard quote): **"The quest generator is a tool from the WNS->WES pipeline, this means that running it live is impossible. So instead upon calls we make the quests and store them for the seamless experience."**

This dictates the entire architecture:

- The `wes_tool_quests` LLM call MUST fire during cascade time, not during scroll-open time.
- Generated quest JSONs sit in a **pre-generated quest pool** keyed by NPC giver, geographic scope, and player-fit signals. Scroll-open is an inventory lookup — zero LLM latency.
- The `wes_quest_reward_pregen` endpoint, which materialises prose into concrete numbers, can fire at scroll-open (within the 2-3s unfurl budget) OR at cascade time alongside the static JSON — designer choice. Default: at scroll-open, because rewards should reflect player level AT THAT MOMENT (a quest pre-generated three play-sessions ago should reward today's level).
- The `wes_quest_reward_adapt` endpoint fires at turn-in. Its latency budget is bigger — the player just turned in a quest, the "the giver opens his mouth" beat naturally takes 1-2 seconds anyway, and even a 4-5s pause feels like the giver weighing what to say. If adapt times out, the floor (`pre_generated_rewards`) lands silently.

### 1.3 Failure modes — what BAD looks like

Three flavors of bad, ranked from most-likely to most-corrosive:

**(a) Slop.** The quest reads like a fantasy-quest-shaped object with no specifics. "Defeat 5 enemies for the Battle Master." "Gather 10 herbs for the Wise Woman." The giver has no name that matters. The objective references nothing the player has actually been involved with. The reward feels generic. This is the failure mode of a tool that has rich inputs but lazy prompting. *(Defense: thread the WNS narrative through every field. If the quest can't reference the moors-stone or the recent copperlash ambush, it's because the WNS firing didn't carry those threads — fix the WNS, not the prompt's word count.)*

**(b) Stagnant predictability.** Every quest is the same shape: kill-N, gather-N, talk-to-N. Every giver gives the same kind of quest as their faction archetype. After three sessions, the player has seen all the colors of the wheel and feels like they're farming. *(Defense: objective-type rotation, faction-cross-pollination, urgency variance, expiration variety, chain depth variance. We do NOT solve this by adding more enemies — we solve it by varying the shape of the ask.)*

**(c) Craziness.** The opposite failure. The LLM, given creative liberty, generates a quest where Captain Vell of the moors raiders wants the player to escort his daughter (he has no daughter) to a chapel (no chapel exists nearby) to deliver a soul-bound relic (this is not how the game's economy or item taxonomy works) before the Convergence (we have no event called the Convergence). The quest is unforgettable and unplayable. *(Defense: cross-ref discipline, the allow-list-of-tags rule, the orphan detector, the BalanceValidator. The hub MUST refuse to invent NPCs/materials/locations not in the registry or co-emitted in this plan; the tool MUST emit tags from the existing tag library or prefix with NEW:.)*

There is also a fourth, quieter failure mode worth naming:

**(d) Disconnected from the WNS narrative.** A quest spawns at a locality where the WNS arc is "the salt moors are restructuring around copper trade" but the quest is a generic "kill 3 wolves for the innkeeper." The quest is fine in isolation. But the WNS just spent 30 events earning the right to a story about copper, and the world delivered wolves instead. The player never gets to feel that the world is responding to them. *(Defense: the bundle's `directive_text`, the firing tier, the thread headlines, and the cascading parent narrative MUST reach the quest tool. Right now `BundleToolSlice` strips parent_summaries — see §4.4. This is the biggest leak in the current pipeline.)*

### 1.4 What "good" actually looks like

A good generated quest, in the player's words after playing for an hour: *"I remember when Captain Vell asked me to hunt the copperlash riders — that quest existed because of what I'd been doing in the moors, and the reward made sense for what I went through."*

Three properties:
- **Causally legible** — the player can name why this quest exists (what they did, who they angered, what shifted).
- **Voiced** — the giver's offer sounds like the giver, not like a quest UI.
- **Proportional** — the reward fits the difficulty, the urgency, and the time the player invested.

---

## 2. Output artifact schema completeness audit

The static `QuestDefinition` JSON shape is locked in `data/models/quests.py` (lines 71-127). Every field below must be filled by either the tool, the reward pregen, the reward adapter, or canonical-quest hand-authoring. The "Author" column names which.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `quest_id` | str (snake_case) | `wes_tool_quests` | Should encode faction + locality + intent. `salt_reach_hunt` beats `quest_001`. Should be unique against the registry. |
| `name` | str (Title Case) | `wes_tool_quests` | Evokes giver and place. "The Salt Reach Hunt" beats "Hunt Quest." |
| `title` | str | `wes_tool_quests` | Legacy alias = `name`. Keep both filled. |
| `description` | str (legacy long-form) | `wes_tool_quests` | Mirror of `description_full.long` — runtime UI still reads this. |
| `npc_id` | str | `wes_tool_quests` | Legacy alias = `given_by`. Must be an existing NPC or co-emitted in same plan. |
| `objectives` | `QuestObjective` | `wes_tool_quests` | Type must match what the giver would ask FOR (an alchemist asks for herbs, not goblins). `items[]` must cross-ref real registry IDs. |
| `objectives.objective_type` | str | `wes_tool_quests` | One of 7. Diversity dial — see §8. |
| `objectives.items[]` | List[Dict] | `wes_tool_quests` | Shape varies by type — see schema. Cross-refs must resolve. |
| `objectives.enemies_killed` | int | `wes_tool_quests` | Combat-type only. Should be tier-appropriate and AGI-reachable in the urgency window (see expiration). |
| `rewards` | `QuestRewards` (zeroed defaults) | `wes_quest_reward_pregen` then `wes_quest_reward_adapt` | The pre-gen fills concrete numbers from prose at scroll-open; the adapter adjusts at turn-in within [0.5x, 1.5x] of pre-gen. |
| `rewards.experience` | int | pregen / adapt | Tier × player_level scaling (see pregen prompt). Adapter may scale ±50%. |
| `rewards.gold` | int | pregen / adapt | Tier × narrative weight. Zero acceptable when prose doesn't mention coin. |
| `rewards.health_restore` | int | pregen | Only when prose hints at it ("a flask of stillwater," "balm"). Often zero. |
| `rewards.mana_restore` | int | pregen | Same rule. Often zero. |
| `rewards.skills[]` | List[str] | pregen | Skill IDs that exist or were co-emitted. Empty unless `skill_hint` was set. |
| `rewards.items[]` | List[Dict] | pregen | Map `item_hints` prose strings to existing material IDs. Pregen should prefer dropping an item over inventing one. |
| `rewards.title` | str | pregen | Title ID that exists or was co-emitted. |
| `rewards.stat_points` | int | pregen | 0-3 for major quests; 0 default. |
| `rewards.status_effects[]` | List[Dict] | (NOT IMPLEMENTED) | Runtime stub — leave empty. |
| `rewards.buffs[]` | List[Dict] | (NOT IMPLEMENTED) | Runtime stub — leave empty. |
| `completion_dialogue[]` | List[str] | `wes_quest_reward_pregen` | 2-3 lines in giver's voice, spoken at turn-in. Must NOT enumerate rewards. |
| `name` (v3 additive) | str | `wes_tool_quests` | Same as `name` above — explicit duplicate in dataclass. |
| `quest_type` | str (one of 6) | `wes_tool_quests` | tutorial/side/main/chain/repeatable/hidden. Diversity dial. |
| `tier` | int 1-4 | `wes_tool_quests` | Drives reward sizing AND objective scaling. Must align with player level expectation. |
| `given_by` | str (npc_id) | `wes_tool_quests` | The NPC who offers. Cross-ref or co-emit. |
| `return_to` | str (npc_id) | `wes_tool_quests` | Usually = `given_by`; differs for courier quests. |
| `description_full` | Dict[short, long, narrative] | `wes_tool_quests` | Three voices: log-entry terse, quest-log full, NPC-spoken narrative. The narrative line is what the player hears the giver SAY. |
| `rewards_prose` | Dict | `wes_tool_quests` | Five fields: `summary`, `experience_hint`, `tier_hint`, `title_hint`, `skill_hint`, `item_hints[]`. This is the SLOT the pregen consumes. The summary line is the giver's "in return..." voice. |
| `requirements` | Dict | `wes_tool_quests` | Level/stats/titles/completedQuests/factionAffinity. Gates the quest. Must be plausible at the player's progression band. |
| `expiration` | Dict | `wes_tool_quests` | One of 5 types. Urgency dial — see §8. |
| `progression` | Dict | `wes_tool_quests` | isRepeatable/cooldown/nextQuest/questChain. Chain links must resolve or be co-emitted. |
| `wns_thread_id` | str | `wes_tool_quests` | The narrative thread this quest belongs to. Empty for orphan quests. **This is the cross-narrative continuity hook.** |
| `tags[]` | List[str] | `wes_tool_quests` | Must come from existing tag library or be flagged NEW:. Drive WMS retrieval, NOT combat. |
| `metadata.narrative` | str | `wes_tool_quests` | Design rationale — NOT player-facing. 1-2 sentences explaining why this quest exists. Fuel for archive + future WNS. |
| `metadata.tags[]` | List[str] | `wes_tool_quests` | 3-6 descriptive tags from allow-list. |
| `metadata.difficulty` | str | `wes_tool_quests` | trivial/easy/moderate/hard/brutal. Should align with tier AND with player-fit. |
| `metadata.estimatedTime` | str | `wes_tool_quests` | Free-form (e.g. "20 minutes"). Influences urgency adapter at turn-in. |
| `source_origin` | str | (set by loader, NOT LLM) | "canonical" for hand-authored; "generated" for everything from `wes_tool_quests`. Drives whether reward materialisation fires. |

### 2.1 Schema completeness — what's MISSING

This is a `[WES-SCHEMA-GAP]` audit. Reading the schema against the quest-lifecycle memory (`quest_lifecycle_design.md`), the following fields the design calls for are **not in the v3 schema**:

- `[WES-SCHEMA-GAP]` **time_started / received_at_game_time** — currently stored only on the runtime `Quest` instance (`quest_system.py:39`). Should be a top-level `QuestDefinition` field so the archive snapshot carries it. Workaround: archive layer reads from runtime instance.
- `[WES-SCHEMA-GAP]` **archived form fields** — `time_completed`, `duration`, `actual_result` (succeeded/failed/partial/abandoned), `actual_rewards_granted`, `participating_npcs`, `archived_narrative_tags`. The memory `quest_lifecycle_design.md` calls for these to be written at turn-in into an archive table. **Currently there is no archive table** — the archived shape is design-only. This is the largest single gap in the quest system. Without the archive, the "we need so much info so we can weave better stories with more continuity" rationale is unrealised — turned-in quests vanish into `completed_quests: List[str]` (just IDs).
- `[WES-SCHEMA-GAP]` **player-fit hints at quest generation** — the tool prompt currently has no input slot for "the player who will receive this." Pregen has `player_level` and `player_stats` but the *static template* doesn't carry e.g. preferred play style. This makes pre-generating a POOL of quests per player tricky — you can't pre-author against a player you haven't sampled yet. Workaround: pre-gen pools are NPC-scoped not player-scoped; player-fit only lands at materialisation.
- `[WES-SCHEMA-GAP]` **multi-stage objectives** — current schema has a single `objective_type` with a flat `items[]`. A real chain quest ("first gather X, THEN deliver to Y, THEN return to Z") has no representation. Each stage would be a separate quest in `progression.nextQuest`. Workable but clunky.
- `[FRAGMENT-GAP]` **modifier-AI hooks** — the design calls for a post-generation modifier that adjusts rewards/timelines/quantity goals based on WNS events since quest creation. The fields it would modify exist (`rewards`, `expiration`, `objectives.items[].quantity`) but no endpoint exists yet. See §9.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent 1990s systematic generator (no LLM) produces, given a giver NPC and an objective slot machine:

```json
{
  "quest_id": "quest_0042",
  "name": "Hunt the Wolves",
  "title": "Hunt the Wolves",
  "quest_type": "side",
  "tier": 2,
  "description_full": {
    "short": "Kill 5 wolves for the village.",
    "long": "The village is troubled by wolves. Defeat 5 of them.",
    "narrative": "These wolves have been bothering us. Help us."
  },
  "given_by": "village_elder_01",
  "npc_id": "village_elder_01",
  "return_to": "village_elder_01",
  "objectives": {
    "objective_type": "kill_target",
    "items": [{"target_id": "wolf_grey", "quantity": 5}],
    "enemies_killed": 0
  },
  "rewards": {
    "experience": 200, "gold": 50, "items": [{"item_id": "minor_health_potion", "quantity": 2}],
    "title": "", "stat_points": 0
  },
  "rewards_prose": {},
  "requirements": {"characterLevel": 5},
  "expiration": {"type": "none"},
  "progression": {"isRepeatable": false},
  "completion_dialogue": ["Thank you. Here is your reward."],
  "metadata": {"tags": ["combat", "side"], "difficulty": "moderate", "estimatedTime": "10 minutes"}
}
```

This is fine. This is also exactly what we lose to. The player has seen this quest a thousand times in a thousand games. It has no soul.

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM must contribute that the slot machine can't:

1. **`quest_id`** — embed faction + locality + intent. (`salt_reach_hunt` not `quest_0042`.) Needs `directive_text` (for intent) + `address_hint` (for locality) + `recent_registry_entries` (to know what's been used).
2. **`name`** — needs to taste like the giver's culture. "The Salt Reach Hunt" not "Hunt the Wolves." Needs the NPC's narrative + the chunk's biome flavor + the WNS thread's tone.
3. **`description_full.narrative`** — the giver's actual SPOKEN line. Cannot be written without the NPC's voice_anchor + their personality archetype + their recent grievance.
4. **`given_by`** — must be coherent with the objective. A blacksmith giving a gather-flowers quest is suspicious. Needs NPC's `knowledge_domains` and `role` to drive plausibility.
5. **`objectives` shape** — the slot machine picks one. The LLM should pick the shape that fits the giver and the WNS arc. (A captain wants kill_target on his enemies. A trader wants gather. A guard wants explore. A priest wants deliver. A scholar wants talk.)
6. **`rewards_prose.summary`** — "a captain's nod, a copperlash whip from his own hand, and silver enough for a tavern week" — this line carries the *feel* of the reward and feeds the pregen materializer. Without it, the materializer has nothing to work with.
7. **`expiration`** — the slot machine defaults to none. The LLM should set urgency based on narrative ("before the next moor-tide," "while the captain still lives"). Drives the adapter's urgency window.
8. **`requirements.factionAffinity`** — emergent gating. "You can't take this quest until you've at least nodded at the moors raiders." Slot machines don't gate this way.
9. **`wns_thread_id`** — narrative continuity. The slot machine has no concept of threads. This is the field that lets the player feel quests connect across hours of play.
10. **`metadata.narrative`** — design rationale. The slot machine doesn't write design notes. This field is the fuel for the future modifier-AI and the WNS continuity weaver. Without it the archived quest is just numbers.
11. **`completion_dialogue`** — the giver speaking AT turn-in, voiced. "It is done. The salt knows your name now." Slot machine: "Thank you. Here is your reward."

The delta is: **specificity of voice, causality with the world, and narrative-continuity hooks.** Everything in the quest pipeline architecture must serve these three properties.

---

## 4. Backward trace through the pipeline

This is the rung-by-rung walk from "scroll unfurls in player's hand" backward to "WMS event row." Each rung names what it consumes, what it emits, and what could be missing.

### 4.1 Rung 0 — Scroll unfurls (player-facing)

Consumes: `QuestDefinition` (from pool) + `rewards` (just-materialised by pregen) + `completion_dialogue` (just-materialised by pregen).
Emits: rendered scroll UI; the active `Quest` instance is added to `QuestManager.active_quests`.
Risk: if the pool is empty (no pre-generated quests for this giver), this fails open — falls back to canonical hand-authored quests on this giver, or no offer at all. **The pool must always be non-empty for giver-NPCs the player can encounter.** This is a *runtime architecture decision* — see §7.

### 4.2 Rung 1 — `wes_quest_reward_pregen` (at scroll-open, OR pre-warmed)

Inputs (from `quest_reward_adapter.py:_pregen_vars`, lines 344-360):
- `quest_id`, `quest_title`, `tier`, `rewards_prose` (object), `objectives` (summary), `player_level`, `player_stats` (the 6-stat block), `narrative` (the giver's spoken offer).

Output: `{rewards: QuestRewards, completion_dialogue: [str, str, str]}`.

What's MISSING from the input set that the prompt should arguably have:

- `[FRAGMENT-GAP]` **Player progression band beyond level** — `player_level` is one number. The pregen should probably see the player's recent activity profile (combat-heavy? crafting-heavy? exploration-heavy?) to weight item rewards toward what the player will USE. Pulled from `StatStore` via `StatTracker` — see WMS rung. *(This is a fragment-gap because the pregen prompt's `user_template` doesn't even have a slot for it.)*
- `[FRAGMENT-GAP]` **Giver's reward style** — the prompt prose says "the giver's known reward style" but no variable carries it. The giver's NPC narrative/personality/faction should tell us "this guy pays in silver and information, not artifacts." Pulled from the static NPC JSON (see NPC v3 schema). Add a `giver_reward_style` variable assembled from the NPC's personality archetype.
- `[FRAGMENT-GAP]` **Locality's economy** — a quest in a backwater pays less than one in the capital. Pulled from L4-L5 WMS interpretations on `domain:economy`. Add a `local_economic_band` variable.
- **Narrative tone** — already carries via the `narrative` field but it's the long-form `description_full.narrative`. Probably sufficient.

The output side is solid — the schema matches `QuestRewards` exactly and the loose-JSON parser handles malformed LLM output.

### 4.3 Rung 2 — `wes_quest_reward_adapt` (at turn-in)

Inputs (from `quest_reward_adapter.py:_adapt_vars`, lines 362-385):
- `quest_id`, `quest_title`, `pre_generated_rewards` (the floor), `rewards_prose` (original LLM hints), `time_taken_seconds`, `tier`, `narrative`, `expiration` (the structured block), `player_level`.

Output: `{rewards: QuestRewards}` — bounded to [0.5x, 1.5x] of pregen by hard rule in prompt; in practice the rule says clamp at 1.0x downward.

What's MISSING:

- `[FRAGMENT-GAP]` **Actual objective completion quality** — did the player complete the OPTIMAL way (e.g. avoid civilian casualties on a kill_target hunt)? Did they exceed quantity (kill 8 when 5 were asked)? The adapter has no signal for this beyond time elapsed. To get it: add objective-progress snapshot at completion (e.g. how many extra enemies of the target type the player killed; how cleanly they completed; whether they used the giver's preferred method).
- `[FRAGMENT-GAP]` **World state delta since quest receive** — has the WNS thread this quest is part of moved on? If the captain you were hunting raiders for has since DIED in the WNS narrative, the quest reward should arguably reflect "you avenged him posthumously." Pulled from `wns_thread_id` + WNS query for thread state. *(This straddles WNS-GAP — the WNS doesn't currently expose a read API the WES side can call. The bundle is one-shot, not a queryable store. For modifier-AI work this becomes a hard gap.)*
- `[FRAGMENT-GAP]` **Affinity shift since quest accept** — did the player's faction standing with the giver's faction change DURING the quest? FactionSystem tracks this (Phase 2+). Pulled from `FactionSystem.get_affinity(player_id, faction_tag)` deltas between accept and turn-in.

### 4.4 Rung 3 — `wes_tool_quests` (one ExecutorSpec → one quest JSON)

Inputs (from prompt user_template):
- `spec_id`, `plan_step_id`, `item_intent` (the hub-authored prose: "vendetta hunt issued by Captain Vell..."), `hard_constraints` (JSON: given_by/return_to/quest_type/tier/objective_type), `flavor_hints` (JSON: name_hint, prose_fragment, summary_hint, experience_hint, tier_hint, difficulty_hint), `cross_ref_hints` (JSON: given_by_npc_id, target_id, target_tool, recipient_npc_id, title_hint, skill_hint, previous_quest_id, next_quest_id, expiration_npc_id, expiration_chunk_id, wns_thread).

Implicit tag-indexed assembly: the tool prompt is `AssemblerStyle.WES` (templated monolith), NOT tag-indexed like WNS. This is by design per memory `feedback_wns_prompts_must_be_tag_indexed.md` — WES tools have unique input shapes per tool.

What's MISSING:

- `[WES-SCHEMA-GAP]` **The bundle's narrative context at the quest tool layer.** Critical leak. Read `slice_bundle_for_tool` (`context_bundle.py:342-370`): the hub gets `threads_in_focal_address` and `directive_text` but loses `parent_summaries`, `firing_layer_summary`, the WMS events delta, and the open threads at parent addresses. By the time the spec reaches the tool, the only narrative trace is the `flavor_hints.prose_fragment` string the hub chose to keep. **The full bundle narrative — the chunk of NL4 narrative that spawned this directive — never reaches the tool.** This is the single biggest source of "disconnected from WNS narrative" failure mode (1.3.d).
  - Fix: extend the tool's user_template with `${narrative_context}` and `${parent_narrative}` slots; have the hub thread them through `flavor_hints.narrative_excerpt` and `flavor_hints.parent_narrative_excerpt`; OR pass the full BundleToolSlice with parent narrative preserved.
- `[WES-SCHEMA-GAP]` **The giver NPC's full narrative.** When the spec names `given_by: "moors_copperlash_captain"`, the tool prompt has no access to that NPC's full static JSON. The tool can guess at voice from the `prose_fragment` but it doesn't see the personality archetype, the speechbank greeting pattern, the home_chunk biome flavor, the faction membership, the affinity_seeds. **The completion_dialogue and description_full.narrative fields are written into a voice the tool doesn't have data for.** Fix: enrich the spec with `${giver_npc_narrative}` and `${giver_voice_anchor}` slots assembled deterministically from the registry. (This is post-orphan-detector: by the time tool fires, the NPC is committed; we can fetch its narrative.)
- `[FRAGMENT-GAP]` **The pool of WMS interpretations near the firing address that AREN'T already in the bundle's narrative context.** The bundle's `NarrativeDelta.wms_events_since_last` carries WMS events between the prior firing and now, but earlier WMS history (the boss the player killed three sessions ago in this district) is dropped. For quest specificity ("hunt the copperlash riders who ambushed you on the moors-stone road last week") the tool wants to reach a few rungs back into WMS. *(Hub or planner should attach the most recent 10-30 WMS L2 interpretations at the firing address as `${recent_wms_summary}`.)*
- `[FRAGMENT-GAP]` **Player-fit signals.** None reach the tool. The static quest doesn't need to know who the player is (rewards do, see pregen). But objective sizing — "kill 3 vs kill 8" — could plausibly weight to player level. Currently it doesn't. Probably acceptable: the materializer scales rewards; objective count can stay tier-driven and the player should rise to the tier.

### 4.5 Rung 4 — `wes_hub_quests` (one plan step → batch of ExecutorSpecs)

Inputs (from prompt user_template):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "vendetta hunt for Captain Vell against his own riders" and emits 1 or more `<spec>` elements, each fully-loaded with the constraints/hints/cross-refs that the tool will use.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same parent_summaries leak as the tool.** The hub gets a `BundleToolSlice` (per `slice_bundle_for_tool`) which already strips parent narrative. Fix at this layer, propagates to the tool.
- `[FRAGMENT-GAP]` **Recent quest registry context.** `recent_registry_entries` is populated by caller-supplied list. The diversity guard depends on this — if the caller doesn't pass it, the hub will happily re-emit the same quest shape over and over. The `slice_bundle_for_tool` signature accepts it as parameter — needs explicit wiring at the orchestrator layer to actually populate from `ContentRegistry`. Verify wiring before relying on diversity.
- `[FRAGMENT-GAP]` **Cross-tool co-emission awareness.** When the plan has `[npcs, hostiles, quests]` and `quests` depends on both, the hub gets `step_slots` with the names but doesn't see the co-emitted hostile's tags / tier / locality. So the quest description can't easily reference "the copperlash riders' rust-cracked armor." Fix: when a quest step depends on another in the same plan, the dispatcher should attach the co-emitted artifacts' summaries to the hub's input.

### 4.6 Rung 5 — `wes_execution_planner` (one bundle → one plan DAG)

Inputs (from prompt user_template):
- `bundle_id`, `firing_tier`, `firing_address`, `bundle_directive` (the `<WES purpose="...">body</WES>` body), `bundle_narrative_context`, `bundle_delta`, `thread_headlines`, `registry_counts`.

The planner is the ONE place where the full bundle is in play. It MUST emit a plan that includes a `quests` step if the directive purpose is `new-quest` and the firing tier is ≥3.

What's MISSING:

- `[FRAGMENT-GAP]` **Bundle.directive.scope_hint contents** — the bridge (`wns_to_wes_bridge.py`) puts `geographic_chain`, `weaver_layer`, and `purpose` into scope_hint. The planner prompt has no `${scope_hint}` template variable — it only sees `firing_address` and `firing_tier`. The geographic chain (region → province → nation names + biomes) is dropped. For quest planning this matters less than for chunk planning, but if the planner is choosing between "issue a quest in salt_moors" and "issue a quest in coast_marches," the geo descriptor would tip the choice.
- The "scope by firing tier" prose in the prompt is locked: tier 1-2 = no quests, tier 3 = 1 NPC + quests OK, tier 4+ = full content sets. **This is the load-bearing prose the designer must tune.** A too-stingy ruleset means quests rarely generate; too-loose and tier-1 events spawn full faction arcs.

### 4.7 Rung 6 — WNS NL4-NL7 weaver emits `<WES purpose="new-quest">`

The `_wes_tool` fragment in each NLn narrative file tells the weaver when to fire `<WES>`. For quests, NL4 (region) is described as "common at this scope," NL3 (district) lists `new-quest` as a typical purpose, NL2 (locality) doesn't list it as common (which is right — locality-scope quests should be hand-authored or canonical).

What's MISSING:

- `[WNS-GAP]` **Quest-specific firing guidance.** The weaver's prompt lists `new-quest` as a bucket but doesn't elaborate on WHEN to fire it specifically. "New-quest" should fire when:
  - A WNS thread has gained momentum (stage rising_action or turning_point).
  - A player-action has angered a faction (affinity_shift went negative recently).
  - A new NPC was just created by `<WES purpose="new-npc">` and that NPC has unfulfilled grievance.
  - A previously-completed quest had a hanging hook (questChain has a nextQuest gap).
  The current prose says "a quest chain tied to the regional arc" — vague. *(Designer task: tune the `_wes_tool` body for each layer to give clearer firing guidance per purpose-bucket. Specifically for new-quest: when, who-from, what-flavor.)*
- `[WNS-GAP]` **The directive_text shape.** The body of `<WES purpose="new-quest">body</WES>` is freeform. Some weavers will write "Generate a quest." (slop). Others will write "Captain Vell, having buried his brother on the moors-stone, issues a vendetta hunt against his own copperlash riders who turned on him after the salt-tax was raised." The latter is exactly what we want — narrative-grounded, name-rooted, intent-rich. The fragment should tell the weaver: name the giver, name the target, name the grievance, name the world-state that caused this.

### 4.8 Rung 7 — WNS reads WMS L2 interpretations

The NL weavers consume `${wms_context}` — a 600-char rendered brief of recent WMS L2 interpretations whose `affected_locality_ids` intersect the firing address's locality set. This is the factual chronicler-voice input.

Solid — no fragment gap here. The WMS context builder already does the rung-2 work of (a) walking the geographic hierarchy to enumerate descendant localities, (b) querying interpretations, (c) char-budgeting the render. The 600-char cap is designer-tunable.

### 4.9 Rung 8 — WMS L2 evaluators interpret L1 events into narrative-ready rows

For quest-relevant signals: `social_quests.py` (quest accept/complete/fail), `social_npc.py` (NPC interactions), `faction_reputation.py`, `combat_kills_regional_*`, `gathering_regional.py`, etc. — these 33 evaluators turn raw events into category-tagged narrative rows that feed L3+ and feed `${wms_context}` in WNS.

Solid. The 33 evaluators are designer-reviewed and locked. Any quest-relevant WMS signal we want has a path here.

---

## 5. Per-field provenance table

For EVERY field that the LLM authors (so excluding `source_origin` which the loader sets), where the upstream signal comes from. The 9-rung WMS column applies when a `[WMS-GAP]` might be tempting — walk it in writing.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `quest_id` | Tool prompt + hub `flavor_hints.name_hint` + registry-uniqueness check | name_hint flows from hub which got it from planner's `step.intent` | Yes | — |
| `name` | Tool prompt + `flavor_hints.name_hint` | hub crafts from `step.intent` + `address_hint` | Yes | — |
| `title` | Tool prompt (alias of `name`) | — | Yes | — |
| `description` | Tool prompt (alias of `description_full.long`) | — | Yes | — |
| `description_full.short` | Tool prompt | `item_intent` + tool's own compression | Yes | — |
| `description_full.long` | Tool prompt | `item_intent` + `prose_fragment` + `thematic_anchors` | Yes | — |
| `description_full.narrative` | Tool prompt | Giver's voice — **but the tool only has `prose_fragment`, NOT the giver's full NPC narrative** | Partial | `[WES-SCHEMA-GAP]` — see 4.4. Add `${giver_voice_anchor}` and `${giver_personality_excerpt}` to tool input. |
| `given_by` / `npc_id` | Cross-ref hint from hub | `cross_ref_hints.given_by_npc_id` from planner's `step.slots.given_by` | Yes — but planner needs the NPC to exist or be co-emitted | — (hub_dependency_resolution.md covers the reactive case once implemented) |
| `return_to` | Cross-ref hint from hub | Defaults to given_by; differs for courier from `cross_ref_hints` | Yes | — |
| `quest_type` | Hub `hard_constraints.quest_type` | Hub chooses from 6 based on planner's `step.intent` + `step.slots.quest_type` | Yes | — |
| `tier` | Hub `hard_constraints.tier` | Planner picks from firing_tier scope rules + `directive_text` weight | Yes | — |
| `objectives.objective_type` | Hub `hard_constraints.objective_type` | Hub picks from 7 based on planner's `step.intent` + giver's role | Yes | — |
| `objectives.items[]` shape (gather) | `cross_ref_hints.target_id` (material) | Planner names the material from `step.slots` or relies on hub_dependency_resolver to fire materials tool | Partially — hub_dependency_resolver is **not implemented** yet | `[FRAGMENT-GAP]` — orchestrator-level wiring. Today, orphan-detector blocks; planner must pre-list materials in `step.depends_on`. |
| `objectives.items[]` shape (kill_target) | `cross_ref_hints.target_id` (hostile), `cross_ref_hints.target_tool=hostiles` | Same as gather | Same | Same |
| `objectives.items[].quantity` | Tool prompt | Tool's own tier-aware sizing | Yes | — |
| `objectives.enemies_killed` | Tool prompt | Tool's own tier-aware sizing for `combat` type | Yes | — |
| `rewards_prose.summary` | Tool prompt + `flavor_hints.summary_hint` | The hub-authored 1-sentence reward seed | Yes | — |
| `rewards_prose.experience_hint` | `flavor_hints.experience_hint` | Hub chooses from 5-value allow-list based on tier+narrative weight | Yes | — |
| `rewards_prose.tier_hint` | `flavor_hints.tier_hint` | Hub mirrors `hard_constraints.tier` ±1 | Yes | — |
| `rewards_prose.title_hint` | `cross_ref_hints.title_hint` | Planner co-emits a title step OR references existing title; cross-ref check at commit | Yes (but title must be co-emitted or exist) | — |
| `rewards_prose.skill_hint` | `cross_ref_hints.skill_hint` | Same as title | Yes | — |
| `rewards_prose.item_hints[]` | Tool prompt | Free narrative — tool invents flavor strings, NOT item_ids | Yes | — |
| `requirements.characterLevel` | Tool prompt | Tier + giver expectations | Yes | — |
| `requirements.stats` | Tool prompt | Often empty; tool fills from `objective_type` (combat → STR, gather → AGI, craft → INT) | Yes | — |
| `requirements.titles[]` | Tool prompt | Plausibility — quest's tier vs title-tier alignment | Yes | — |
| `requirements.completedQuests[]` | Cross-ref hint `previous_quest_id` from hub | Chain dependency | Yes | — |
| `requirements.factionAffinity` | Tool prompt | Inferred from giver's faction belonging + WNS thread tone | Yes | — |
| `expiration.type` | Tool prompt | Tool picks from 5 based on `directive_text` urgency + `metadata.estimatedTime` | Yes | — |
| `expiration.seconds` / `npc_id` / `chunk_id` | Cross-ref hint when applicable | `cross_ref_hints.expiration_npc_id` / `expiration_chunk_id` from hub | Yes | — |
| `progression.isRepeatable` | Tool prompt | `quest_type=repeatable` → true; else false | Yes | — |
| `progression.cooldown` | Tool prompt | Tier × narrative weight; tool's own pick | Yes | — |
| `progression.nextQuest` | `cross_ref_hints.next_quest_id` from hub | Chain dependency | Yes (when chained) | — |
| `progression.questChain` | Tool prompt | Tool picks a free-form chain identifier from `thematic_anchors` | Yes | — |
| `wns_thread_id` | `cross_ref_hints.wns_thread` from hub | Hub pulls from `narrative_context.open_threads[i].thread_id` (the bundle slice carries them) | **Partial — only threads in the focal address survive the slice; parent-address threads are dropped** | `[WES-SCHEMA-GAP]` — see 4.4 |
| `completion_dialogue` | `wes_quest_reward_pregen` | Pregen prompt builds from `narrative` (giver's offer voice) | Yes — but giver's broader voice is dim | `[FRAGMENT-GAP]` — pregen should also see giver's personality/speech archetype |
| `tags[]` | Tool prompt | Tool picks from allow-list in tool prompt | Yes (locked allow-list, see `tag_system_functionality.md`) | — |
| `metadata.narrative` | Tool prompt | Tool's own design-rationale summary, fed by `item_intent` + `prose_fragment` | Yes | — |
| `metadata.tags[]` | Tool prompt | Subset of `tags[]`, allow-list locked | Yes | — |
| `metadata.difficulty` | Tool prompt | `flavor_hints.difficulty_hint` from hub | Yes | — |
| `metadata.estimatedTime` | Tool prompt | Tool picks from `objective_type` × `quantity` × tier | Yes | — |
| `rewards.experience` (concrete) | `wes_quest_reward_pregen` | Tier × player_level × experience_hint mapping | Yes | — |
| `rewards.gold` (concrete) | `wes_quest_reward_pregen` | Tier × narrative weight + prose hints | Yes | — |
| `rewards.health_restore` (concrete) | `wes_quest_reward_pregen` | Prose hints | Yes | — |
| `rewards.mana_restore` (concrete) | `wes_quest_reward_pregen` | Prose hints | Yes | — |
| `rewards.skills[]` (concrete) | `wes_quest_reward_pregen` | `skill_hint` cross-ref | Yes | — |
| `rewards.items[]` (concrete) | `wes_quest_reward_pregen` | `item_hints` → material registry lookup; pregen prompt says skip if no fit | Yes | — |
| `rewards.title` (concrete) | `wes_quest_reward_pregen` | `title_hint` cross-ref | Yes | — |
| `rewards.stat_points` (concrete) | `wes_quest_reward_pregen` | Quest-type-driven (main story → 1-3, side → 0) | Yes | — |
| `rewards.*` (adapted) | `wes_quest_reward_adapt` | Pregen floor × time-taken/urgency adjustment | Yes — but adapter signals are thin (see 4.3) | `[FRAGMENT-GAP]` on objective-completion-quality and world-state-delta |

### 5.1 WMS-GAP walk — the one place I was tempted

The one piece of context I almost flagged `[WMS-GAP]` for: **player-grievance history with the giver's faction** at the locality scope.

The use case: pregen wants to know "has this player been ANTAGONISTIC to the moors raiders recently?" so that the rewards for Captain Vell's quest can flavor accordingly (give less to a hostile player; give more to a recently-converted ally).

I walked the 9 rungs:

1. **Direct query**: Is there a WMS event "player became hostile to moors raiders"? No single event has this exact shape. **Fail.**
2. **Adjacent events**: Same address + same entities — are there WMS L2 events tagged `species:copperlash_rider` + `event:enemy_killed` at locality:salt_moors? **Yes** — `combat_kills_regional_low_tier.py` and `combat_kills_regional_high_tier.py` evaluators produce exactly this. Querying `event_store.count_filtered(event_type='enemy_killed', address='locality:salt_moors')` returns it.
3. **Negative patterns**: Has the player NOT interacted with any moors_raiders NPCs lately? Absence-of-positive is a hostility signal. Pull from `entity_registry` and `social_npc.py` evaluator output.
4. **Aggregation**: `daily_ledger.unique_enemy_types_fought` already tracks species diversity per day. Combine with `social.quests.completed.kill_target` count: high kill / low ally-quest = hostile.
5. **Trajectory**: `social_quests.py` builds severity bands (minor/moderate/significant/major) by count + recency. Same evaluator can be queried for "how many anti-moors kills in last N game days."
6. **Cross-layer climb**: NL3 (district) and NL4 (region) narratives carry the *interpretation* of the player's hostility ("the moors-stone road grows quiet of riders"). The bundle already brings NL4 narrative if firing tier is 4.
7. **Cross-entity composition**: The combination "many copperlash kills + zero ally interactions + recent attempted-talk-to-moors-NPC failures" is what we want. All three rows exist in event_store; the combination is a query.
8. **Stat / ledger lookup**: `FactionSystem.get_affinity('player', 'guild:moors_raiders')` returns the current numeric standing — already deterministic, no LLM needed. Pregen can read this directly. **This is the cleanest single signal.**
9. **Trigger history**: Has the `<AffinityShift>` directive fired on `guild:moors_raiders` recently? `affinity_resolver.py` writes to a time-indexed ledger — query that for "deltas in last N game days."

**Verdict**: NOT a WMS gap. The signal is available through (8) faction affinity + (3-5) WMS aggregation. The actual gap is at the **pregen prompt input layer** — `_pregen_vars` doesn't carry any faction-affinity or player-action signals. Marker: `[FRAGMENT-GAP]` on the pregen prompt's input set, not `[WMS-GAP]`.

So **zero `[WMS-GAP]` markers in this trace.** WMS gives us everything; the gaps are at the WNS→WES boundary (bundle leak) and at the prompt input layer (variables not threaded through). Good news; means the upstream sacred work is solid.

---

## 6. Cross-references with other features (personal shopper)

Sharing vs. flavor-divergent across the other 9 features.

### 6.1 Heavy shared infrastructure (use as-is)

- **WNS NL4-NL7 narrative weavers** — shared with EVERY content-generating feature (NPCs, Hostiles, Materials, Nodes, Skills, Titles, Chunks). One narrative substrate; every feature reads `<WES purpose="...">` directives from it. *(Agent assignment: WNS / Planner+Supervisor.)*
- **WES Execution Planner** — shared with every feature. The scope-by-firing-tier rules govern all. *(Agent assignment: WNS / Planner+Supervisor.)*
- **WMS L2 evaluators + L2-L7 chronicle** — read-only shared substrate. Every feature's WES tool benefits from `${wms_context}` in its upstream WNS firings. *(Agent assignment: WNS / Planner+Supervisor.)*
- **Tag system + tag-registry.json** — shared allow-list. Every tool's `tags[]` field draws from it. Adding tags must be flagged NEW: in every tool. *(Cross-cutting; no single owner.)*
- **`BundleToolSlice`** — shared by all hubs. The `parent_summaries` leak (§4.4) affects every feature equally. **Fix in one place benefits all 8.**
- **Orphan detector** — shared. Cross-ref enforcement across all feature tools.

### 6.2 Quest-specific shared with adjacent features

- **NPC giver narrative + voice_anchor** — Quest tool desperately needs this (§4.4 schema gap). **NPC agent must publish an API that exposes giver narrative + voice_anchor at the WES dispatcher layer**, so when a quest spec references `given_by: moors_copperlash_captain`, the orchestrator can splice in the giver's static data. *(Agent assignment: NPCs.)*
- **Title cross-ref** — Quest's `rewards_prose.title_hint` and `requirements.titles[]` reference titles. Co-emission in the same plan is the norm. **The title tool must accept `cross_ref_hints.granted_by_quest_id`** as a hint to flavor the title's narrative around the quest that grants it. *(Agent assignment: Titles.)*
- **Skill cross-ref** — `rewards_prose.skill_hint` and (occasionally) `objectives.items[].skill_id` for craft objectives. Skills tool reciprocates with `cross_ref_hints.taught_by_npc_id`. *(Agent assignment: Skills.)*
- **Material cross-ref** — gather and deliver objectives both reference materials. Same pattern: material tool accepts `cross_ref_hints.gather_quest_id` to flavor the material's drop context. *(Agent assignment: Materials.)*
- **Hostile cross-ref** — kill_target objectives reference hostiles. Hostile tool reciprocates `cross_ref_hints.hunted_by_quest_id` to flavor the hostile's lore (e.g. "the copperlash riders are hunted by Captain Vell's vendetta"). *(Agent assignment: Hostiles.)*
- **Chunk cross-ref** — explore objectives reference chunks. Less reciprocity needed; chunks are spatial, not narrative-driven by quests. *(Agent assignment: Chunks.)*

### 6.3 Where quests diverge (flavor not shareable)

- **Reward materialisation flow** — `wes_quest_reward_pregen` + `wes_quest_reward_adapt` are UNIQUE to quests. No other feature has a "materialise prose into concrete at-receive-time + adapt at turn-in" pattern. NPCs don't have rewards. Materials don't have prose. The dual-stage flow is quest-architectural and shouldn't be force-shared.
- **Lifecycle / archive** — quests have an in-progress / archived distinction that other content types don't have. (Materials don't get archived when consumed; they just leave inventory. NPCs persist forever in the registry.) Quest archive is its own subsystem (currently unimplemented, see §9).
- **wns_thread_id linkage** — quests are the primary "narrative thread tracker." Other features (chunks, materials, hostiles) belong to threads transitively through the quests/NPCs they're attached to. The quest is the narrative anchor; other features anchor TO quests, not vice versa.

### 6.4 Recommendations to other agents

- **NPCs agent**: Publish a deterministic API to fetch a static NPC's narrative + voice_anchor + personality from a committed `npc_id`. The quest tool's `completion_dialogue` and `description_full.narrative` quality depends on this.
- **Titles agent**: Accept `cross_ref_hints.granted_by_quest_id` in your hub input; flavor title narratives around granting-quest theme.
- **Skills agent**: Accept `cross_ref_hints.taught_by_npc_id` and (for quest-rewarded skills) `cross_ref_hints.rewarded_by_quest_id`.
- **Materials / Hostiles / Chunks**: The reverse linkage (these features being referenced BY quests) is the dominant pattern; less work needed on your end other than ensuring your tool outputs reach `ContentRegistry` before the quest hub fires.
- **WNS / Planner+Supervisor agent**: **The single most impactful intervention you can make for quest quality is closing the `BundleToolSlice` parent_summaries leak.** Make sure the slice carries `parent_summaries` and `firing_layer_summary` through to the hub, then to the tool. Also: tune the `_wes_tool` body in `narrative_fragments_nl4.json` and `narrative_fragments_nl3.json` to give the weaver clearer guidance on WHEN to fire `<WES purpose="new-quest">` (see §4.7).

---

## 7. Storage / timing design

### 7.1 The pre-generated quest pool — the core architecture

The user's directive: *"upon calls we make the quests and store them for the seamless experience. This means that the user will have old and archived quests."*

Architecture:

- **Generation event**: WNS firing emits `<WES purpose="new-quest">` → planner → hub → tool → static `QuestDefinition` JSON commits to `ContentRegistry.reg_quests`. **No reward materialisation yet.**
- **Pool storage**: The committed quests live on disk as `progression/quests-generated-<timestamp>.JSON` (sacred-file untouched per CLAUDE.md guidance) and in `reg_quests` table. They are NOT yet offered to the player.
- **Offer event**: When the player interacts with a giver NPC, the runtime queries the pool for unoffered quests where `given_by == this_npc_id`. If found, presents the offer dialogue.
- **Reward materialisation**: At scroll-open, `wes_quest_reward_pregen` fires with the player's current level, stats, and (recommended additions) faction-affinity / activity-profile signals. The 2-3s scroll-unfurl animation masks the LLM latency.
- **Active state**: Quest enters `QuestManager.active_quests`. Pregen-materialised `rewards` and `completion_dialogue` cached on the runtime `Quest` instance.
- **Completion**: Player meets objectives → `Quest.complete_quest()` fires `wes_quest_reward_adapt` → adapted rewards land → `grant_rewards()` applies.
- **Archive**: At turn-in, a NEW archive record must be written (currently MISSING — see §2.1).

### 7.2 Pool sizing & refresh cadence

How many pre-generated quests should sit unoffered per giver NPC? Designer-tunable, but my recommendation:

- **Minimum 3 per active giver**, refreshed when count drops below 2.
- **Refresh trigger**: when WNS fires `<WES purpose="new-quest">` AND the giver named is the current giver, the new quest joins the pool. Otherwise, refresh is on cooldown (suggest: every N game-days, configurable).
- **Stale quests**: a pool quest unoffered for too long (suggest: 7 game-days) gets re-evaluated. If the WNS narrative has moved on (the captain's brother's death is no longer recent), the quest should either expire or feed into the modifier-AI for refresh.

### 7.3 Expiration types — when quests die unoffered

The existing `expiration.type` field covers:
- `none` — quest available forever
- `time_limit_seconds` — auto-fail after N seconds from accept
- `world_state` — narrative trigger (e.g. "before the moor-tide")
- `npc_death` — if giver dies, quest void
- `chunk_destroyed` — if location razed, quest void

For UNOFFERED pool quests (not yet accepted), an additional implicit expiration:
- `narrative_staleness` — if the WNS thread the quest belongs to has closed (`thread_stage:resolution` or `coda`), the quest expires from the pool unoffered. *(Add this as a runtime check, not a schema field; check at offer-time.)*

### 7.4 Adaptive context binding

A pre-generated quest sits in the pool with `wns_thread_id` set. If the thread evolves (the WNS arc moves from `rising_action` to `complication`), the quest's `description_full.narrative` and `rewards_prose.summary` may grow stale. The modifier-AI (see §9) handles this — at offer time, if the WNS thread has moved on materially, fire the modifier to refresh the prose AND the rewards_prose before pregen fires.

### 7.5 What the archive looks like

Per `quest_lifecycle_design.md`, at turn-in, write to a (currently nonexistent) archive table:

```
ArchivedQuest {
  quest_id, original_quest_def_json,
  time_started, time_completed, duration,
  actual_result (succeeded | failed | partial | abandoned),
  actual_rewards_granted (concrete QuestRewards),
  participating_npcs ([npc_id, ...]),
  participating_entities ([material/hostile/chunk ids touched]),
  archived_narrative_tags ([str], for WNS retrieval),
  wns_thread_id, archived_at_game_day
}
```

This is the **fuel for WNS continuity**. When a future WNS firing on this player happens, the chronicler can reach into ArchivedQuest history and say "the player avenged Captain Vell's brother three winters ago — Vell still remembers." Without the archive, the world's memory of completed quests is `completed_quests: List[str]` — IDs only, no story.

**Implementation hook**: archive table goes into `world_memory` as a sibling to `daily_ledger.py` (it's a chronicler-voice record, fits the WMS substrate). Read API exposed via `WorldQuery` so WNS weavers can pull archived-quest context.

---

## 8. Diversity & creativity design

User direction: *"the competition is quests that could be systematically generated, that is the benchmark we must be above; so what information is required for the quest JSON to have that."*

The diversity dials, ranked by impact:

### 8.1 Objective-type rotation

7 types in allow-list: `gather, combat, kill_target, craft, deliver, explore, talk`. The hub MUST be discouraged from defaulting to combat/gather. Implementation:
- `recent_registry_entries` should expose objective_type frequency. Hub prompt should be augmented to say "if the last 5 quests in this district were combat, prefer non-combat next."
- Per-NPC role bias: a scholar's quests skew talk/explore/craft; a captain's skew kill_target; a trader's skew gather/deliver. Driven by NPC's `knowledge_domains` and `role` — pull from NPC narrative.

### 8.2 Giver-cross-pollination

Don't generate every quest in a locality from the same NPC. Distribute across the locality's NPC population.
- Implementation: planner step (and hub) should see `recent_registry_entries.by_giver_npc_id` and avoid stacking.
- Cross-NPC chains: NPC-A gives a quest that completes by talking to NPC-B who then offers a follow-up. Chain depth 2-3 across givers. `progression.nextQuest` + `progression.questChain` already supports this; the planner needs to USE it.

### 8.3 Urgency variance

`expiration.type` skews to `none` by default in the prompt. Encourage variety:
- 60% `none`, 20% `time_limit_seconds`, 10% `world_state`, 5% `npc_death`, 5% `chunk_destroyed` is a starting distribution. Tunable in playtest.
- Time pressure is a strong diversity signal — a quest that must be done before the next in-game tide hits FEELS different from a quest you can do anytime.

### 8.4 Chain depth variance

Mix one-off quests, 2-quest chains, 3-quest chains, 5-quest arcs. Distribution suggestion: 70% one-off, 20% 2-3, 10% 4+. Driven by `quest_type=chain` and `progression.questChain`.

### 8.5 Mood/tone dials

`metadata.tags` includes `[vendetta, hunt, mystery, redemption, betrayal, political, religious, training, lore]`. Tag diversity is itself a diversity signal. The hub prompt should be augmented with "in addition to objective_type variety, vary the dominant metadata tag across the batch."

WNS-side: the firing layer's `tone:*` tag (`tone:hopeful`, `tone:ominous`, etc.) should propagate into the quest. A quest born from a `tone:ominous` thread should NOT feel `tone:triumphant`.

### 8.6 Player-action sensitivity

Two distinct sensitivity loops:

- **At generation time (cascade)**: WNS thread tags (`agency:player`, `agency:npc`, etc.) influence quest framing. A `agency:player`-tagged thread means the quest should reference what the player did.
- **At materialisation time (pregen)**: `player_level`, recommended additions of `player_activity_profile` and `player_faction_affinity_with_giver`. The rewards reflect not just what the quest is worth abstractly, but what's MEANINGFUL to this player. (A potion-rich player gets fewer potion rewards; a high-affinity ally gets bonus story-flavored items.)

### 8.7 Reward-style variance

The pregen prompt currently has experience/gold/items/title/stat_points as the slots it fills. Variety in WHICH slots fill matters: a quest that gives only experience feels different from one that gives a unique item; a quest that grants a stat_point is rare and special; a quest that grants ONLY a title (a coronation, an oath-mark) is unforgettable.

Suggested distribution:
- 60% experience + gold (sometimes + minor items)
- 20% experience + items (consumables or low-tier crafting materials)
- 10% experience + title
- 5% experience + skill
- 3% experience + stat_points
- 2% title-only or skill-only (no XP)

Achievable by tuning the pregen prompt's "CONSERVATIVE DEFAULT" rule and adding distribution guidance.

### 8.8 Emergent proper nouns

The `emergent_entity` tag in WNS narrative fragments allows the LLM to coin proper nouns (a place name, a person, an event). Caps: 2 per fragment, 5 per run. Quests inherit these: if NL4 invented "the Moors-Stone Massacre" as a thread headline, the quest can name it. This is where unrepeatability lives — every emergent proper noun is a one-off. Designer-review surface (per memory).

---

## 9. Speculative future endpoints

Things the user has flagged or that this trace surfaces as natural next-step LLM endpoints.

### 9.1 `wes_quest_modifier` — the post-creation modification AI

User direction: *"Future ideas could include quest expiration dates or a quest modification AI that takes generated quests and relevant WNS queries since its creation to modify quest rewards, timelines, or quantity goals."*

Design sketch:

- **Trigger**: at offer-time (player approaches giver), check if the pool quest's `wns_thread_id` has moved by N stages since quest generation. If yes, fire the modifier.
- **Inputs**: the original `QuestDefinition` JSON + the current WNS thread state (current `thread_stage`, current `tone`, current open threads at the giver's address) + WMS interpretations since quest generation.
- **Outputs**: a patch JSON — `{description_full?, rewards_prose?, expiration?, objectives.items[].quantity?}`. Apply patch to quest before scroll-open.
- **Latency budget**: same 2-3s scroll-unfurl mask. Should fire IN PARALLEL with `wes_quest_reward_pregen`.
- **Skip condition**: if WNS thread is `resolution` or `coda`, expire the quest unoffered instead of modifying.

Endpoint count: +1 LLM task. Prompt fragment file: `prompt_fragments_wes_quest_modifier.json`.

### 9.2 `wes_quest_expiration_handler` — narrative on quest void

When a quest's `expiration` triggers (giver dies, chunk destroyed, time limit hit) WHILE the quest is active, currently the runtime silently voids the quest. Should instead emit a 1-line "expired because..." narrative for the WNS to consume.

- **Trigger**: `expiration.type` condition met on an active quest.
- **Inputs**: quest JSON + the world-state delta that caused expiration.
- **Outputs**: a single narrative fragment + tags, written into the archive as `actual_result: "expired"` with cause prose.
- **Latency budget**: not player-facing immediate — fires async, written when the player next looks at quest log.

Endpoint count: +1 LLM task. *Could be folded into `wes_quest_modifier` as a flavor mode rather than a separate endpoint — designer call.*

### 9.3 `wes_quest_chain_planner` — for arc-scale quest chains

The current planner can emit chain quests as separate `quests` steps with `progression.nextQuest` cross-refs. But a 5-quest narrative arc is fundamentally PLANNED, not just listed. A specialised chain planner would:

- **Trigger**: WNS NL5+ fires `<WES purpose="new-quest-chain">` (new bucket).
- **Inputs**: bundle + chain length target.
- **Outputs**: a quest-chain plan with rising-falling-resolution structure across N steps, each step a quest spec.
- **Then**: each quest spec fans out to the existing `wes_hub_quests` + `wes_tool_quests` pipeline.

Endpoint count: +1 LLM task. Prompt fragment: `prompt_fragments_wes_quest_chain_planner.json`. Probably premature — start with `progression.nextQuest` linking and see if it suffices.

### 9.4 `wes_quest_archive_summarizer` — chronicler-voice archived-quest narration

When a quest archives, the WNS doesn't currently get a clean chronicler-voice line about it. A small endpoint that takes the `ArchivedQuest` record and emits a one-line chronicler summary ("In the third winter, the player avenged Captain Vell's brother on the moors-stone — three copperlash riders dead by their hand") would feed the WNS far better than raw JSON.

- **Trigger**: at archive write time.
- **Inputs**: the archive record (input + outcome).
- **Outputs**: 1-2 sentence chronicler narrative + tags.
- **Where it lives**: probably WMS-side (the archive is WMS substrate), not WES. Could be a new evaluator (extending `social_quests.py`) that produces an InterpretedEvent with chronicler narrative.

Endpoint count: +1 LLM task OR +1 evaluator. Probably the latter — WMS L2 evaluators are the natural home.

### 9.5 `wes_quest_giver_curator` — who-gives-what brokerage

Cross-feature concern: when WNS fires `<WES purpose="new-quest">` without a giver named, the system should auto-select a giver from the locality's NPCs whose role/personality/grievance best fits the quest's intent. Currently the planner picks (sometimes badly) or the directive_text names them. A curator endpoint would:

- **Trigger**: planner sees a `new-quest` purpose without a giver named.
- **Inputs**: directive_text + locality's NPC roster (id + role + faction + recent_dialogue_summary).
- **Outputs**: best-fit `given_by` npc_id + a 1-sentence rationale.

Endpoint count: +1 LLM task. Could be folded into the planner — designer call.

### 9.6 Big-picture: the 4-endpoint quest pipeline grows to potentially 7-8

Current: `wes_tool_quests` + `wes_hub_quests` + `wes_quest_reward_pregen` + `wes_quest_reward_adapt` (4).
With speculatives: + `wes_quest_modifier` + `wes_quest_expiration_handler` + `wes_quest_chain_planner` + `wes_quest_giver_curator` + `wes_quest_archive_summarizer` (potentially 9 total).

Some can fold into existing tasks (archive summarizer into a WMS evaluator; expiration handler into modifier; chain planner into planner). Pragmatic count: **5-6 endpoints** when the system reaches maturity. The four shipped now are the load-bearing minimum.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Close the `BundleToolSlice` parent_summaries leak.** The single largest source of "quest disconnected from WNS narrative" failure. Single fix benefits all 8 content tools.
2. **Build the archive table.** Without it, the lifecycle design's whole continuity-weaving rationale is unrealised. New WMS-side schema, `WorldQuery` API, optional evaluator/summarizer.
3. **Thread NPC giver narrative + voice_anchor through to the quest tool.** The completion_dialogue and description_full.narrative are written in a voice the tool doesn't have data for. Deterministic spice from the committed NPC registry.

Everything else in this trace — diversity dials, modifier-AI, pool architecture — is downstream of those three.
