# Feature Trace 11 — Trigger Taxonomy (Meta-Trace, Wave 4)

> **2026-06-05 STALENESS NOTICE.** This trace's "two archetypes" framework (narrative-causal via NL cascade vs. behavior-causal via WMS threshold) was conceptually correct but predates the **Model C** implementation that wired them together at the bridge layer. Specifically: WMS Layer N firing now publishes `WMS_LAYER_{N}_SUMMARY_CREATED`; the `WMSToWNSBridge` subscribes and fires NL_N directly at the address (the "behavior-causal peak path" this trace anticipated). NL1 dialogue ALSO feeds the WMS weighted-bucket triggers point-equivalent to L2 events. Read `Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md` for the now-canonical wiring.

**Wave:** 4 (meta-trace; consumes 1-10)
**Owned endpoints:** NONE directly — this is a cross-cutting taxonomy. Affects: `wes_execution_planner`, `wes_supervisor`, `wns_layer{2..7}`, every `wes_hub_*`, every `wes_tool_*`, the `WMS→WNS bridge` (cascade trigger), `RequestLayer.build_specs`.
**Final output artifact:** **a framework, not a JSON.** The framework: two trigger archetypes (narrative-causal + behavior-causal) feeding the same 8 WES tools through the same WNS-WES pipeline, with explicit plumbing for the milestone path that the prior 10 traces under-covered.
**Date:** 2026-05-26

> "I will say the quality is incredibly high. However you may have tunnelled in solely on quests/npc interactions. Remember that there are other interactions as well. ... You have a ton of focus on the NPC interaction through the WNS, which is good. But don't forget about regular interactions through the WMS as well." — user, after reviewing Waves 1-3

> "The system should be unified remember. These are two seperate paths in a way, but also they inform each other and to the player should be seamless creation of high quality, well thought out patterns." — user, framing this trace's thesis

The 10 prior traces are right about what they cover. Agent 1 calibrated quality at quest-shape; Agents 2-8 inherited the quest's NPC-mediated framing; Agent 9 specced the WNS narrative substrate; Agent 10 wove orchestration around it. The trace pass was internally consistent because Agent 1 was the calibrator. **And because Agent 1 was the calibrator, every trace anchored on the same trigger archetype: a WNS thread, dense with NPCs and faction motion, fires a `<WES>` directive from inside narrative.** That is one of two archetypes. The other — a WMS milestone trips, the WNS interprets, the same `<WES>` directive fires from interpretation rather than from inside narrative — is structurally identical at the WES side and structurally different at the WNS side, and the prior traces did not name it.

This trace names it. Then it specifies the plumbing the behavior-causal path needs that the narrative-causal path didn't. Then it asks each of the 8 content tools "what does behavior-causal firing for YOU look like?" — because the answer differs per tool (skills lean heavily behavior-causal; NPCs lean heavily narrative-causal; chunks are mixed). Then it sweeps the prior 10 traces for over-specified prose fields (the user's second correction: skill evolution prose should be intentionally vague, not checklist-exact — that's almost certainly true of titles, hostile lore, chunk narrative, and several other prose fields too).

The unification thesis is the spine. **One world. Two pathways for content to ARISE. Identical pipeline downstream. The player must not perceive which path birthed what.**

---

## 1. The unification thesis

### 1.1 The user's framing, restated

There are two distinct *causes* for content to be generated in this game:

- **Narrative-causal.** A WNS thread reaches a state where new content WOULD MAKE THE STORY BETTER. NPCs are in motion; factions are colliding; the cult-sign matches the rust-mark; the chronicler at the regional capital is breaking a story. The WNS weaver emits `<WES purpose="new-X">` from inside its narrative, because the story is asking for new X.
- **Behavior-causal.** A WMS milestone trips — the player has used 1000 potions; the player has explored 10000 chunks and walked 100000 steps; the player has killed 500 hostiles of the same species; the player has crafted 100 items in one discipline. The WNS interprets the milestone — what is the player DOING? — and decides whether the world should respond with new content. If yes, the same `<WES purpose="new-X">` directive fires.

In the user's words: *"a player may gain a skill or title by an ordinary milestone in the WMS that is big enough for the WNS to call the WES to make a new skill."* The user wrote "WES flags the threshold" but the architecture is clear: thresholds live in `TriggerManager` which lives in `world_system/world_memory/`. **The WMS publishes the threshold event; the WNS interprets it; the WES generates.** WMS → WNS → WES, same direction as the narrative-causal path, but with the WMS layer doing more than passive event-catalog work — it's actively saying "this player just did something at scale."

### 1.2 Why unification matters (player anchor)

The player does not know what a WNS layer is. The player does not know the difference between a thread-stage-firing and a stream-count-threshold. The player sees: *the world responded to me.* The response can come because the chronicler at the regional capital noticed a faction's restructuring, OR because the player crossed 1000 potions used. Both responses arrive through the same channel — a new skill, a new title, a new NPC, a new chunk. **If the player can tell which response was narrative-driven and which was milestone-driven, the unification has failed.**

Per the user: *"to the player should be seamless creation of high quality, well thought out patterns."* The seamlessness IS the deliverable.

This is the trace's spine, and every section below answers a sub-question of it:

- Section 2: what ARE the two archetypes mechanically?
- Section 3: what WMS milestones can we trigger off TODAY (creative extraction; stringent on WMS gaps)?
- Section 4: per content tool, where should behavior-causal triggers fire that the prior traces missed?
- Section 5: what plumbing does the WMS→WNS bridge need so milestone events actually reach the WNS interpretive layer?
- Section 6: what does the planner / supervisor need to handle behavior-causal dispatch the same way it handles narrative-causal?
- Section 7: how do the two paths INFORM each other (the cross-archetype interaction surface)?
- Section 8: the prose-ambiguity sweep — the user's second correction applied across all 10 traces.
- Section 9: speculative trigger-system endpoints (no new content tools, per user constraint).

### 1.3 Mixed triggers are the norm, not the exception

The user's chunks pseudo-trace makes mixed-trigger the canonical case: NPC rumors of new spaces (narrative) + chunks_seen + steps_walked thresholds (behavior) → WNS consolidates BOTH signals → dispatches a chunk WES call with both contexts in the bundle → the chunk is alchemy-themed because the player has been alchemy-heavy (behavior) AND there are rumors of strange terrains (narrative) → the chunk THEN propagates to hostiles + materials (DAG cascade).

If we design as if narrative-causal is the dominant case and behavior-causal is the exception, we will under-build the plumbing for mixed triggers. The mixed case is what makes content feel like the world is RESPONDING, not just unfolding.

### 1.4 What the prior 10 traces got right that this trace builds on

- **Agent 1 (Quests)** correctly identified the `BundleToolSlice.parent_summaries` leak. Behavior-causal triggers need this MORE than narrative-causal triggers, because the behavior interpretation that the WNS makes IS the parent narrative for the WES dispatch. If parent_summaries doesn't reach the tool, the behavior-causal context is doubly lost.
- **Agent 6 (Skills)** §1.1 already named the behavior-causal pattern implicitly: "the player who uses potions frequently" pattern. But it treated this as ONE input among many for an NPC-teacher-mediated skill. The user's clarification: the milestone path is FIRST-CLASS, not subordinate to the NPC-teacher path.
- **Agent 7 (Titles)** is the trace that is MOST aligned with the behavior-causal archetype today. Titles are inherently milestone-coupled (`prerequisites.conditions[].type == "stat_tracker"`). But even Agent 7 framed firings primarily as narrative-driven ("the moors arc fires a new-title directive"). The threshold-driven path was implicit in the runtime evaluation, not the WES firing.
- **Agent 8 (Chunks)** §4.6 noted "the cult-sign the children draw matches the rust-mark on the moors-stone" as a narrative-causal trigger. The user's gold-standard chunks pseudo-trace mixes that with the chunks_seen + steps_walked milestone — a pure behavior-causal path that Agent 8 did not name.
- **Agent 9 (WNS)** specced the bundle contract. The behavior-causal path needs ADDITIONS to that contract (per §5 below) — a `behavior_signal` slot in the bundle, an `inferred_behavior_intent` field, and threshold metadata.
- **Agent 10 (Orchestration)** specced the planner/supervisor with `scope_by_firing_tier` rules. The behavior-causal path needs the planner to read a `trigger_archetype` discriminator (§6) so it can apply DIFFERENT acceptance criteria (a milestone-spawned skill should USE the milestone artifact; a narrative-spawned skill needs to USE the named lineage).

This trace does NOT redo the load-bearing fixes the prior 10 surfaced. The parent_summaries leak, the DAG ordering fix, the adjusted_instructions threading, the scope-by-firing-tier prose, the geographic_chain plumbing — those are correct and binding. This trace adds the SECOND axis the prior 10 didn't expand.

---

## 2. Trigger archetype taxonomy

### 2.1 Archetype A — Narrative-causal

**Definition.** A WNS thread has accumulated enough narrative weight that the weaver, mid-narration, decides "new X content would land here." The weaver emits `<WES purpose="new-X">body</WES>` inline. The body is a 1-2 sentence prose description of what X should be.

**Trigger source.** Inside the WNS weaver's prompt at firing time. The weaver fires because the WMS→WNS cascade-by-N rule fired (every 3 WMS L2 events at a locality, NL2 weaves; etc.). The CONTENT of the firing — the threads, the parent_summaries, the WMS context — accumulated enough to make the weaver emit the directive.

**WNS interpretation pattern.** The weaver READS the narrative state, decides the story wants X, embeds the directive. No separate interpretation pass — the interpretation IS the weaving.

**Bundle context shape.** The bundle carries the firing layer's narrative_context (what the weaver just wrote), the parent_summaries (what regional/national/world narratives say), the open_threads, and the directive_text (the 1-2 sentence body). The `trigger_archetype` field (proposed addition; see §6.2) is `"narrative"`. The `behavior_signal` field is empty.

**Dispatch decision criteria.** The planner reads the directive + parent narrative + open threads, decides scope, emits a plan. Supervisor verifies the staged content responds to the directive's proper nouns AND fits the firing tier's scope rules.

**Canonical example.** Agent 1's quest example. NL3 fires at coast-marches district; threads include "cult-sign matching rust-mark"; weaver writes "Captain Vell offers vendetta against his own copperlash riders" and embeds `<WES purpose="new-quest">vendetta hunt issued by Captain Vell...</WES>`. The planner builds a `[npcs, quests]` plan (or just `[quests]` if Captain Vell already exists). The quest is born from inside a narrative.

**Prior trace coverage.** ALL of Wave 1+2+3 deeply covered this. It is the default architecture in the v4 working doc.

### 2.2 Archetype B — Behavior-causal

**Definition.** A WMS milestone crosses a `THRESHOLD_SET` value (`trigger_manager.py:23` — `[1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]`). The `TriggerAction` it emits represents "this player has done X at this scale." A WNS-side interpreter reads the threshold + the StatStore + the daily ledger + the activity profile, decides whether the world should RESPOND, and if yes, fires a `<WES purpose="new-X">` directive of its own choosing.

**Trigger source.** Pre-existing `TriggerManager.on_event` in `world_system/world_memory/trigger_manager.py`. Today it returns `TriggerAction` objects which feed the WMS interpreter for L2 narrative-row creation. **What this trace proposes: the same TriggerAction stream also feeds a WNS-side "behavior interpreter" that decides whether the threshold warrants a WES dispatch.**

**WNS interpretation pattern.** The interpreter (call it the "behavior-causal pre-weaver" or, more precisely, an extension of `nl_weaver._build_user_prompt` for behavior-triggered firings) reads:
- The crossed threshold (`stream_count` or `regional_count`, plus the threshold value).
- The StatStore page for the relevant counter (`stat_tracker.py` 65 `record_*` methods).
- The daily ledger aggregations at the firing address (`daily_ledger.py`).
- The recent L2 evaluator outputs for the same player+address (33 evaluators in `world_memory/evaluators/`).
- The activity profile — what is the player DOING at this address (the user's example: "Looking at the ledger the WNS thinks that the player is using them in combat").

From these inputs, the interpreter generates the `directive_text` and the `inferred_behavior_intent` (a 1-2 sentence prose summary of what the player's pattern IS — "the player uses potions in combat; this looks like emergency healing"). Then the directive flows into the same WES pipeline.

**Bundle context shape.** The bundle carries:
- The same narrative_context the narrative-causal path carries (the firing layer's narrative is the WMS L2 interpretation of the threshold-causing event, NOT a weaver narrative).
- A NEW `behavior_signal` field: `{counter_path, threshold_crossed, stream_count, activity_profile, inferred_behavior_intent}`.
- `trigger_archetype` set to `"behavior"`.
- The directive_text generated by the behavior interpreter.

**Dispatch decision criteria.** The planner reads the directive + behavior_signal, decides scope. **Key difference from narrative-causal: scope discipline is tuned by the BEHAVIOR's nature, not by the firing tier alone.** A 1000-potion-usage milestone at locality scope warrants a locality-flavored skill (utility, not combat); the same milestone at province scope (rare) warrants a higher-tier skill referencing the player's overall identity. Supervisor checks: does the staged content USE the milestone artifact? If the trigger was "1000 potions," the resulting skill should clearly reference potions or healing.

**Canonical example.** The user's skill pseudo-trace: player uses 1000 potions; WMS publishes threshold event for `stream_key=(player, item_used, potion, locality)`; WNS behavior interpreter reads the ledger, sees combat usage pattern, dispatches `<WES purpose="new-skill">an instant-heal skill matching the player's pattern of emergency potion use in combat; tier 2-3; INT scaling</WES>`. WES generates "Field Medic's Reflex" — a skill that heals full-potion-value instantly. The world responded.

**Prior trace coverage.** UNDER-COVERED. Agent 7 (Titles) is closest because titles are mechanically milestone-coupled at runtime. But Agent 7 framed WES firings as primarily narrative-driven and the behavior-causal path as implicit in `prerequisites.conditions[].stat_path`. The user's clarification: behavior-causal is FIRST-CLASS in the WES firing decision itself, not just at runtime evaluation.

### 2.3 Archetype C — Mixed

**Definition.** BOTH narrative and behavior signals converge at WNS consolidation time, and the consolidation decides to dispatch. The bundle carries BOTH the narrative_context (parent_summaries, open_threads) AND the behavior_signal (the threshold + activity profile).

**Trigger source.** The user's chunks pseudo-trace is the canonical case: "If the WNS is tracking NPC conversations and there are rumors of new spaces/terrains [narrative-causal signal] AND then a threshold comes ... where the player has seen 10000 chunks and walked 100000 steps [behavior-causal signal] then the WNS can when consolidating also choose to trigger the WES."

**WNS interpretation pattern.** The consolidation happens at the WNS weaver, with BOTH signals present in its inputs. The weaver decides the directive body, blending: "A new biome type the regional rumors hint at, tilted toward the player's heavy alchemy activity — perhaps a fungal-bog terrain rich in alchemical reagents." The `<WES>` directive body explicitly references BOTH the narrative anchor AND the behavior anchor.

**Bundle context shape.** Both `narrative_context.parent_summaries` AND `behavior_signal` populated. `trigger_archetype` set to `"mixed"`. The supervisor reviews against BOTH criteria.

**Dispatch decision criteria.** The most permissive of the three. The planner may emit broader scope plans because the mixed signal is the strongest type of cause-for-content. Supervisor: staged content should respond to BOTH the narrative anchor (NPCs are rumoring this) AND the behavior anchor (the player has been doing X).

**Canonical example.** The user's chunks chain. The result: an alchemy-tilted new chunk template, which propagates to alchemy-themed hostiles (bog-fauna with alchemical drops) and alchemy-themed materials (fungal reagents) via the DAG cascade. **One trigger event birthed an entire ecosystem branch responsive to both the world's rumors and the player's identity.** This is the fully unified case.

**Prior trace coverage.** Agent 8 (Chunks) covered the narrative half of this example. The behavior half — chunks_seen + steps_walked + alchemy_activity_profile — was not in scope. This trace covers it.

### 2.4 The taxonomy summary table

| Property | Narrative-causal (A) | Behavior-causal (B) | Mixed (C) |
|---|---|---|---|
| Firing source | WNS weaver emits `<WES>` inline | WMS threshold → WNS behavior interpreter | WNS weaver consolidates both |
| `trigger_archetype` field | `"narrative"` | `"behavior"` | `"mixed"` |
| `behavior_signal` populated? | No (empty dict) | Yes (full) | Yes (full) |
| `narrative_context.parent_summaries`? | Yes (load-bearing) | Yes (smaller — interpretation context) | Yes (load-bearing) |
| Directive body author | WNS weaver, inline | WNS behavior interpreter (separate prompt or extended weaver) | WNS weaver, with behavior context in prompt |
| Planner scope rules | `scope_by_firing_tier` prose | NEW: `scope_by_behavior_threshold` prose (§6) | Hybrid; default to broader |
| Supervisor acceptance criteria | Directive proper-noun fidelity | NEW: Behavior-artifact fidelity (§6) | Both |
| Typical firing tier | NL2-NL7 (any) | NL2-NL5 (locality to province) | NL3-NL5 |
| Typical content tools triggered | All 8 | Skills, Titles, Quests heavily; Hostiles/Chunks/Materials mid-frequency; NPCs occasional | All 8 |
| Cadence | Cascade-by-N WMS events | Threshold-crossing in TriggerManager | Coincidence of both at same firing |
| Player-visible flavor | "the world is unfolding" | "the world recognizes ME" | "the world recognizes me AND is unfolding" |

---

## 3. WMS milestone surface inventory

This section walks the existing WMS for what behavior-causal triggers are REACHABLE TODAY without WMS changes. Per the methodology's stringency directive, the 9-rung creative-extraction checklist applies to every claim about what isn't available; bare `[WMS-GAP]` markers are rejected.

### 3.1 `TriggerManager` — the primary milestone surface

Confirmed at `world_system/world_memory/trigger_manager.py`. Two tracks:

- **Track 1 (stream).** Per `(actor_id, event_type, event_subtype, locality_id)`. Fires at each threshold crossing in `[1, 3, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 100000]`. Examples reachable:
  - `(player, item_used, potion, tarmouth)` crosses 1000 → "the player has used 1000 potions in Tarmouth."
  - `(player, skill_used, fireball, salt_moors_chunk_42)` crosses 500 → "the player has used Fireball 500 times in this specific chunk."
  - `(player, enemy_killed, copperlash_rider, dangerous_copper_moors)` crosses 100 → "the player has killed 100 copperlash riders in the moors."
  - `(player, resource_gathered, moors_copper, salt_moors)` crosses 250.
  - `(player, craft_attempted, alchemy, tarmouth)` crosses 50.

- **Track 2 (regional).** Per `(locality_id, event_category)` where `event_category ∈ {combat, gathering, crafting, economy, progression, exploration, social}`. Fires at the same thresholds. Examples:
  - `(salt_moors, combat)` crosses 1000 → "1000 combat events have happened in the salt moors."
  - `(tarmouth, gathering)` crosses 500.
  - `(silent_order_chapter_house, social)` crosses 100.

The `EVENT_CATEGORY_MAP` (`trigger_manager.py:30-72`) covers 35+ event_types. **Every player-action event already counted IS a milestone candidate.** No WMS changes needed to surface them.

**Today this stream feeds the WMS interpreter for L2 narrative-row creation.** The proposal: the same stream also feeds a NEW WNS-side subscriber (the behavior interpreter) which decides whether the threshold warrants a WES dispatch.

### 3.2 `StatStore` / `StatTracker` — the secondary milestone surface

Confirmed: 65+ `record_*` methods in `entities/components/stat_tracker.py`. Each method writes to StatStore. The methods cover:
- Combat (damage_dealt, damage_taken, enemy_killed, death, dodge, block, projectile_hit, ...).
- Gathering (resource_gathered, fish_caught, fishing_failed, gathering_damage, tool_swing/durability/broken/repaired, node_depleted).
- Crafting (crafting, invention, recipe_discovered, enchantment_applied).
- Economy (item_collected/used/dropped, gold_earned/spent, trade).
- Progression (level_up, exp_gained, title_earned, class_changed, skill_learned, skill_used).
- Exploration (movement, chunk_entered, landmark_discovered, dungeon_*).
- Social (npc_interaction, quest_accepted/completed/failed).
- Meta (activity_time, session_end, menu_time, idle_time, personal_best, first_discovery, save, game_load).

StatStore aggregations (count, sum, max, distribution-over-time, ratio) are queryable per stat. **Every aggregation IS a behavior signal.** Examples:
- `stat_store.get("combat.damage_dealt.by_type.fire.count")` → has the player been a fire-mage?
- `stat_store.get("gathering.tools.copper_pick.use_count") / stat_store.get("gathering.tools.iron_pick.use_count")` → tool preference ratio.
- `stat_store.get("progression.skills_learned.count") - stat_store.get("skills.used.unique_count")` → hoard-vs-use signal.

The 33 L2 evaluators in `world_memory/evaluators/` already do many such aggregations and emit L2 narrative rows. Those L2 rows are themselves milestone-derived behavior signals available to the WNS via `${wms_context}`.

### 3.3 Daily ledger — the temporal milestone surface

Confirmed: `world_memory/daily_ledger.py` aggregates per-day rows. Daily aggregations let the WNS see "the player used 200 potions THIS WEEK" rather than "the player used 1000 potions LIFETIME." For behavior-causal interpretation, trajectory matters as much as cumulative count.

### 3.4 What's NOT directly a milestone but is reachable via creative extraction

The 9-rung discipline applied to "what behavior signals are NOT obvious but reachable":

1. **Direct query.** Many candidates: StatStore counters by-source / by-target / by-locality.
2. **Adjacent events.** Skill_used events filtered by skill's category → "what kind of skills is the player using." Skill_learned events filtered by NPC teacher → "who has the player been learning from."
3. **Negative patterns.** Skills LEARNED but never USED (the hoard pattern). Hostiles repeatedly fled from (`damage_taken` followed by `movement` without `enemy_killed`). Localities entered but never engaged in.
4. **Aggregation.** Per-discipline ratio (combat/gathering/crafting time allocation). Per-faction reputation trajectory. Per-locality visit-rate decay.
5. **Trajectory.** Skill-use trends over recent game-days. Locality affinity rate-of-change.
6. **Cross-layer climb.** NL3+ narratives already say "the player has been here a lot this week" — interpretation captured in chronicle voice.
7. **Cross-entity composition.** Skill-used × class-affinity × locality = local playstyle fingerprint. Faction-affinity × NPC-interaction-count × dialogue-domain = relationship depth.
8. **Stat / ledger lookup.** Already covered.
9. **Trigger history.** `TriggerManager.get_state()` exposes counter history. The meta-signal "this player has crossed THIS counter 5 times in the last week."

**The behavior signal surface, walked carefully, is ENORMOUS.** Per the methodology stringency: there are zero `[WMS-GAP]` markers from the inventory above. The WMS substrate is sufficient. The gaps live at the boundary — at the WMS→WNS bridge (§5) where the milestone events need to actually reach the WNS interpretive layer.

### 3.5 The one tempting `[WMS-GAP]` walked through

**Temptation:** "Cross-session behavior signal — what the player has been doing across multiple play sessions."

Walking the 9 rungs:

1. **Direct query.** StatStore is persistent across saves; counts accumulate. The signal exists.
2. **Adjacent events.** Session-end events (`record_session_end`) bookend sessions; combined with action events, session-scoped slices are queryable.
3. **Negative patterns.** "Player has not done X this session vs. last session" is a trajectory delta.
4. **Aggregation.** `daily_ledger` aggregates per game-day; sessions span ≤ 1 game-day typically.
5. **Trajectory.** Already covered by daily aggregation.
6. **Cross-layer climb.** NL5+ narratives at province/nation scope cover multi-session timescales.
7. **Cross-entity composition.** Locality × session × activity = "where has the player been spending time across sessions."
8. **Stat / ledger lookup.** `record_save` and `record_game_load` events bracket sessions in stat_tracker.py:788,793.
9. **Trigger history.** Counter histories are persistent.

**Verdict.** NOT a WMS gap. Cross-session behavior is reachable. The gap is at the WNS bridge: the bundle should carry session-bracketed aggregates for behavior-causal firings. `[WNS-GAP]` — the bundle's behavior_signal should include a `session_delta` field. NOT a `[WMS-GAP]`.

**Zero `[WMS-GAP]` markers in this trace.** Consistent with Waves 1+2+3.

---

## 4. Per-content-tool behavior-causal audit

For EACH of the 8 content tools, what behavior-causal triggers SHOULD exist, what the existing trace covered, what it MISSED, what bundle context the behavior-causal path needs that narrative-causal didn't, and how the trigger feeds forward into the WES tool's prompt.

This is the personal-shopper sweep across the prior 10 — finding the gap each agent didn't see because Agent 1's calibration was narrative-causal.

### 4.1 Skills

**Behavior-causal triggers that SHOULD exist:**
- **Usage milestone.** `(player, skill_used, fireball, ANY)` at 1000 → world responds with a higher-tier fireball variant or a complementary skill. The user's potions example is the analog: 1000 potions → emergency-heal skill.
- **Cross-skill mastery pattern.** Player has used 10+ different fire skills 100+ times each → the world recognizes a "fire archetype" and emits a signature fire skill.
- **Discipline mastery.** Player has crafted 500+ alchemy items → an alchemy-utility skill emerges (instant-brew, multi-target potion application, etc.).
- **Death-by-source pattern.** Player has died to bleed 50 times → world responds with a bleed-resistance skill OR a counter-bleed skill (depending on personality/play history).
- **Tool preference.** Player uses copperpick 90% of the time → a copper-mining-specialty skill.
- **Cross-archetype combo.** Player uses melee AND fire skills frequently → a melee-fire hybrid skill.

**What Agent 6 (Skills) covered:**
- §1.1 named the behavior pattern indirectly: "the player has been LEARNING but not USING fire skills lately." Agent 6 surfaced this as a `[FRAGMENT-GAP]` on the WNS render layer.
- §5.1 walked the 9 rungs on player skill-learning patterns and arrived at "extend the WNS context renderer" — a FRAGMENT fix.
- §9.5 `wes_skill_player_signature` — speculatively named a player-pattern-driven skill emission as a future endpoint.

**What Agent 6 MISSED:**
- The behavior-causal trigger as a FIRST-CLASS firing mechanism in v4, not a speculative future endpoint. The user's potions example is canonical, not speculative.
- The skill tool's prompt input should include `behavior_signal` directly — not just rely on the WNS render layer surfacing the pattern indirectly through `${wms_context}`.
- The DAG implication: a behavior-causal skill firing does NOT require an NPC teacher. The skill can be self-learned (player levels up and discovers it; `unlockMethod: LevelUp` or a NEW unlockMethod `BehaviorEmergence`).
- The intent specificity: when the trigger is "1000 potions," the supervisor's directive-fidelity check should verify the generated skill REFERENCES potions or healing. Agent 6's supervisor framing (lineage-anchored) is correct for narrative-causal; behavior-causal has a different anchor (the milestone artifact).

**Bundle context needed:**
- `behavior_signal.counter_path = "items.consumed.potion.use_count"`.
- `behavior_signal.threshold_crossed = 1000`.
- `behavior_signal.activity_profile = "primarily combat use (78% of potion uses preceded combat events within 5s)"`.
- `behavior_signal.inferred_behavior_intent = "the player relies on potions for emergency healing in combat".`
- Plus the standard `narrative_context.parent_summaries` (smaller — the WMS L2 row interpreting the threshold).

**How it feeds the tool prompt:**
- Replace `flavor_hints.narrative_anchor` with `flavor_hints.behavior_anchor` when behavior-causal.
- Add explicit prompt rule: "If trigger_archetype is `behavior`, the skill MUST mechanically respond to the milestone artifact named in `behavior_signal.counter_path`. If counter is `items.consumed.potion`, the skill MUST relate to potions or healing."
- Skill `narrative` field should be intentionally vague about HOW the player earned this (per §8 prose-ambiguity sweep): "Born of habit. The hand reaches for the vial before the mind names the wound." NOT "Earned by using 1000 potions in combat."

**Highest-leverage finding for Skills:** the behavior-causal path is what gives the player the strongest "the world recognizes ME" feeling. It is the path where the unification thesis has the largest payoff. The skill tool's prompt MUST handle it as a first-class shape.

### 4.2 Titles

**Behavior-causal triggers that SHOULD exist:**
- This is the tool MOST behavior-aligned today. Titles' `prerequisites.conditions[].type == "stat_tracker"` IS a behavior-causal trigger at runtime.
- BUT the WES FIRING (when does a new title's JSON get authored?) was framed in Agent 7 as narrative-causal — a WNS thread says "the moors need a Reaver title."
- Triggers that should fire WES title creation:
  - Player crosses a milestone the existing title pool doesn't honor (1000 fish caught and no fishing-master title exists) → fire `<WES purpose="new-title">` to mint one.
  - Player has a SIGNATURE pattern (90% of kills are stealth backstabs) and no title exists for it → mint "Whisper-killer".
  - Cross-domain pattern (player completed 50 quests in coast-marches district) and no district-specific title exists.
  - Negative-pattern (player has avoided combat for 10 game-days and accumulated 100k gold) → mint "The Merchant" or analog non-combat title.

**What Agent 7 (Titles) covered:**
- §1.3.b correctly named "stagnant predictability — only milestone titles" as a failure mode. The defense was tier-distribution caps and seeding with non-milestone titles. **This is correct.**
- §1.3.e correctly named "title spam." The defense was awareness of recent_registry_entries.
- §2.1 added a `signature_deeds[]` schema field — the structured fact list of what the player did to earn this. **This IS the behavior-causal artifact.**
- §5.1 walked the 9 rungs and arrived at `StatTracker.activity_profile(locality_id)` as a deterministic accessor.

**What Agent 7 MISSED:**
- The WES firing trigger itself: titles should be SPAWNED behavior-causally, not just RECOGNIZED behavior-causally. Today Agent 7's framing has the title's existence narrative-driven and the title's earning behavior-driven. The user's framing: BOTH the existence and the earning can be behavior-driven.
- The "title pool refresh on milestone" trigger: when a player crosses a threshold and the existing pool has no matching title, the pool itself should expand. Today, the title pool is born at WNS firing time (narrative); the player crosses thresholds against an existing pool. The pool can stagnate.
- The `signature_deeds[]` field is the perfect carrier for the behavior_signal. The behavior-causal title firing should populate signature_deeds from the threshold events that triggered it.

**Bundle context needed:**
- Same `behavior_signal` shape as skills.
- PLUS: `behavior_signal.matching_titles_in_pool[] = []` (empty if no matches, signaling pool gap).

**How it feeds the tool prompt:**
- The title tool prompt should distinguish: "if `trigger_archetype` is `behavior`, this is a behavior-driven minting — the title MUST acknowledge the deed pattern in `signature_deeds`. If `narrative`, the title is a narrative reward and `signature_deeds` populates from the firing narrative."
- The narrative line should be vague (per §8): "You have done this enough that the world remembers." NOT "Earned by killing 500 wolves in the Northern Forest."

**Highest-leverage finding for Titles:** Agent 7 implicitly assumed the pool expands narrative-causally. **The pool MUST also expand behavior-causally.** Otherwise the milestone-runtime path that Agent 7 correctly described has nothing fresh to evaluate against.

### 4.3 Chunks (the mixed case)

**Behavior-causal triggers that SHOULD exist:**
- Exploration milestone: `(player, chunk_entered, ANY, ANY)` regional/global counts crossing thresholds.
- Movement milestone: `(player, movement, ANY, ANY)` crossing thresholds.
- Frontier-pressing pattern: trajectory of `chunk_entered` events shows the player consistently pushing into virgin territory.
- Avoidance pattern: localities entered but never engaged (no combat, no gathering, no NPC interaction) — the player is route-shopping but not investing. The world could respond by inserting a "destination" chunk in their path.
- Density preference: player visits high-resource-density chunks 80% of the time → emit a high-density variant biome.

**What Agent 8 (Chunks) covered:**
- The mixed-trigger case is the user's gold-standard pseudo-trace. Agent 8 covered the narrative half perfectly (§4.6 — NPC rumors of new terrains).
- §4.3 surfaced the player-progression-band gap: tool doesn't see what player level the average explorer is at. This is a behavior signal.

**What Agent 8 MISSED:**
- The behavior-causal path as a separate firing mechanism. The user's example: 10000 chunks seen + 100000 steps walked, IN COMBINATION WITH narrative rumors, fires a chunk directive. Agent 8 only covered the narrative half.
- The activity-profile influence: "If the player is heavily in alchemy for example then maybe it has a slight alchemy theme in the chunk." This is behavior-context flowing INTO the chunks tool prompt. Agent 8's bundle context spec did not include an activity_profile field.
- The DAG propagation: the user's example explicitly says "This then trickles down to hostiles and materials." Agent 8 covered the DAG generally (chunks → nodes/hostiles → materials) but didn't articulate that the BEHAVIOR FLAVOR (alchemy-theme) propagates DOWN through the DAG. Materials co-emitted with an alchemy-themed chunk should also be alchemy-themed.

**Bundle context needed:**
- `behavior_signal.activity_profile = {alchemy: 0.6, combat: 0.3, gathering: 0.1}`.
- `behavior_signal.exploration_signature = {avg_chunks_per_session: 23, frontier_pressure: 0.7, density_preference: "high"}`.
- The narrative half is unchanged from Agent 8.

**How it feeds the tool prompt:**
- Chunks tool prompt: "If `behavior_signal.activity_profile` shows discipline dominance, the chunk should LEAN INTO that discipline's resources/hostiles/theme. The lean is subtle — not an alchemy theme park, but alchemy-tinted ecology."
- The narrative description should be intentionally evocative, not checklist-exact: "The air carries the tang of something fermenting" beats "Contains 5 alchemy reagents."

**DAG propagation rule (new for chunks, mixed-trigger):**
When a chunks step is mixed-trigger with a behavior flavor, the planner attaches `flavor_hints.behavior_inheritance = "alchemy"` (or analogous) to downstream hostile + node + material specs in the same plan. The downstream tools READ this and bias their output toward the inherited flavor. **This is the unification thesis made concrete:** the behavior signal that birthed the chunk also shapes the chunk's entire DAG-spawned ecosystem.

**Highest-leverage finding for Chunks:** the chunks pseudo-trace is the user's most fully-articulated unified example. Implementing behavior-inheritance propagation across the DAG is the highest-leverage chunks-specific fix — it makes the player's identity flow through an entire generated biome's worth of content.

### 4.4 Hostiles

**Behavior-causal triggers that SHOULD exist:**
- Kill-count milestone per species at a locality: `(player, enemy_killed, copperlash_rider, dangerous_copper_moors)` crosses 100 → world responds with a tier-up variant (Copperlash Captain, Copperlash Veteran) or a sister-species at adjacent locality.
- Death-by-source pattern: player has died to bleed 50 times → world spawns a bleed-counter hostile (something that absorbs bleed damage and turns it into healing) as a teaching encounter.
- Biome dwell time: player has spent 100+ hours in salt_moors → the moors emit a new "endgame" tier-4 hostile for that biome (the captain's-mentor or the legendary-progenitor).
- Combat style adaptation: player uses ranged 90% → world responds with a fast-charging melee threat (anti-strategy hostile).
- Avoidance triggering: hostile X exists but player has consistently fled from it → DON'T re-emit similar hostiles (negative behavior signal).

**What Agent 3 (Hostiles) covered:**
- §1.3.b stagnant predictability + §8 diversity rotation across categories/tiers. **Correct.**
- §1.3.e ecosystem-incoherent drops + cross-ref discipline. **Correct.**
- Heavy NPC-mediated framing throughout (faction/locality narrative as primary anchor).

**What Agent 3 MISSED:**
- Kill-count milestone as a firing trigger. The defense Agent 3 named ("hub awareness of recent_registry_entries") is for the narrative-causal firing case. Behavior-causal firing has a different shape: the trigger IS "the player has killed N of these," and the response IS a tier-up or sister-species.
- Death-by-source as a teaching trigger. This is interesting because it inverts the "hostile responds to player" pattern: the hostile is generated to TEACH the player to handle a damage type they keep dying to.
- Combat-style adaptation: anti-strategy hostiles. This is the strongest "world recognizes the player" signal for combat. Agent 3 didn't name it.

**Bundle context needed:**
- `behavior_signal.kill_pattern = {species: copperlash_rider, count: 100, recency: high}`.
- `behavior_signal.death_pattern = {source: bleed, count: 50, recent: true}`.
- `behavior_signal.combat_style = {ranged_ratio: 0.9, dodge_count: 200, block_count: 5}`.

**How it feeds the tool prompt:**
- Hostiles tool prompt: "If `behavior_signal.kill_pattern.count` is over 100 for a species, the hostile generated should be a tier-up VARIANT of that species (Captain, Veteran, Elder) OR a sister-species in adjacent locality with shared lineage tags."
- "If `behavior_signal.death_pattern.source` is consistent, the hostile generated should be a TEACHING encounter — its kit teaches the player to handle that damage type. Drops should include a relevant counter-skill or counter-material."
- Hostile lore description should be intentionally vague about the player's involvement (per §8): "Survivors of the long campaign. They have learned what you fight like." NOT "Created because the player killed 100 copperlash riders."

**Highest-leverage finding for Hostiles:** behavior-causal hostile generation closes the combat-loop response. Today the loop is: player kills hostile → loot drops → player levels up. With behavior-causal, the loop becomes: player kills 100 hostiles → world responds with tier-up + new tactical challenge → player adapts. This is what makes the combat system feel ALIVE rather than a treadmill.

### 4.5 Materials

**Behavior-causal triggers that SHOULD exist:**
- Gather-count milestone per material at locality: `(player, resource_gathered, moors_copper, salt_moors)` crosses 1000 → world responds with a refined-tier variant (moors_copper_alloy) or a sister-material (moors_silver).
- Discipline-specific gather density: player gathers alchemy reagents 5x more than smithing materials → emit a new alchemy reagent at preferred localities.
- Crafting input shortage signal: player crafts X repeatedly, X requires material Y, Y is scarce → emit a Y-substitute or a Y-rich variant.
- Aesthetic preference: player crafts items with `copper` tag 80% of the time → emit a copper-variant of a non-copper material (silver→copper-tinged silver).

**What Agent 4 (Materials) covered:**
- Strong narrative-causal framing — materials born from WNS arcs about regional restructuring.
- Heavy ecosystem coherence emphasis (Agent 4 was rigorous on biome-coherence).

**What Agent 4 MISSED:**
- Gather-pattern milestones as a firing trigger. The "gathered 1000 moors_copper" signal isn't even in the bundle.
- Crafting-input shortage as a firing trigger. This is the player saying (via behavior) "give me more Y."
- The discipline-preference signal — same flavor as chunks (alchemy-tilted player → alchemy-tilted material).

**Bundle context needed:**
- `behavior_signal.gather_pattern = {material: moors_copper, count: 1000, locality: salt_moors}`.
- `behavior_signal.crafting_input_demand = {material_y: high_demand, recipe_z: heavy_use}`.
- Plus `activity_profile` (shared with chunks).

**How it feeds the tool prompt:**
- Materials tool prompt: "If `behavior_signal.gather_pattern.count` is over 1000 for a material at a locality, the new material generated should be a SISTER or REFINED-TIER variant in the same locality. Sister: shared biome, complementary use case. Refined-tier: higher tier of the original, same biome."
- Material description should be intentionally evocative: "Rarer than its cousin, found in the same veins by those who know where to look." NOT "Spawns 1 per 100 moors_copper gathers."

**Highest-leverage finding for Materials:** materials are the most subtle behavior-causal target because their "world responds to me" signal is the WEAKEST per-instance. The fix is treating materials as DAG-inherited from chunks (per §4.3) more than as standalone behavior-causal triggers. Materials behavior-causally fire RARELY; they more often inherit behavior-flavor from a parent chunk firing.

### 4.6 Nodes

**Behavior-causal triggers that SHOULD exist:**
- Same shape as materials but per-NODE rather than per-MATERIAL.
- Per-node depletion rate: player depletes copper_vein nodes 10x faster than iron_vein → emit a rare/legendary copper node in their preferred locality.
- Discovery pattern: player has discovered N unique node types → emit a "master gatherer" tier node with mixed yields.

**What Agent 5 (Nodes) covered:**
- Wired correctly to materials and chunks. Strong narrative-causal framing.

**What Agent 5 MISSED:**
- Per-node depletion as a behavior trigger.
- Same flavor-inheritance rule as materials (nodes are DAG-inherited from chunks; behavior flavor flows through).

**Bundle context needed:** same as materials, plus `behavior_signal.node_depletion_pattern`.

**Highest-leverage finding for Nodes:** same as materials — nodes are primarily DAG-inherited. Pure behavior-causal node firings are rare; the typical flavor flows through chunks.

### 4.7 NPCs

**Behavior-causal triggers that SHOULD exist:**
- This is the tool with the WEAKEST behavior-causal trigger surface. NPCs are inherently narrative-causal (NPCs come from "a person who matters" — that judgment is narrative).
- Possible behavior-causal triggers:
  - Player has NEVER spoken to an NPC in locality X (avoidance) → emit a "low-friction approach" NPC who can break the ice.
  - Player consistently rejects an NPC's quest type (combat) but accepts another (delivery) → emit an NPC who specializes in the accepted type at adjacent locality.
  - Player has 10+ NPC interactions at the same NPC over many sessions → emit a "kin" NPC (relative, mentor's mentor, etc.) connected to that NPC.
  - Faction-affinity trajectory: player is rising in faction X → emit a higher-rank faction X NPC who recognizes them.

**What Agent 2 (NPCs) covered:**
- Extremely thorough narrative-causal NPC trace. The v3 NPC schema split (static + dynamic context) is correct.
- §4 covered the WNS-driven NPC generation.

**What Agent 2 MISSED:**
- Behavior-driven NPC emission is shallow but real. Most NPC firings should be narrative-causal (that's correct); some should be behavior-causal (avoidance, kin, faction-rank-recognition).
- The dynamic_context registry Agent 2 specced is the natural carrier for behavior-causal NPC TUNING. An existing NPC's reactions can be tuned by the player's behavior history. This is a runtime adaptation, not a generation trigger.

**Bundle context needed:**
- `behavior_signal.npc_interaction_pattern = {avoidance_localities: [...], accepted_quest_types: [...], rejected_quest_types: [...]}`.
- `behavior_signal.faction_trajectory = {faction_id: rising/falling/stable}`.

**How it feeds the tool prompt:**
- NPC tool prompt: "If `behavior_signal.faction_trajectory` shows rising in faction X, this new NPC should be of faction X at a higher rank, with personality.reaction_modifiers reflecting recognition of player rank."
- NPC voice should be intentionally vague about how they know: "Word travels among us. We watch for our own." NOT "You have killed 50 enemies for our cause."

**Highest-leverage finding for NPCs:** NPCs are the tool where the unification thesis is HARDEST to implement, because the natural mode of NPC creation is narrative. The behavior-causal trigger for NPCs is mostly about TUNING (the dynamic_context carries behavior-state) rather than GENERATION. Accepting this is fine; the unification is on the tuning side, not the generation side.

### 4.8 Quests

**Behavior-causal triggers that SHOULD exist:**
- Quest accept-rate pattern: player has accepted 80% of delivery quests but only 20% of combat quests → emit a delivery quest variant when the locality's narrative warrants any quest.
- Cross-locality activity: player has been heavy in locality X for 10 sessions but never accepted a quest there → emit a "low-barrier introduction" quest from a non-questgiver NPC.
- Quest completion velocity: player completes quests in < 2 game-days each → tier up the difficulty of newly-generated quests at this address (the player is OUT-PACING the current quest pool).
- Failure pattern: player has failed 10 quests recently → emit a "comeback" quest with rewards scaling against recent failures (a redemption arc trigger).
- Inventory state: player has 1000+ gold and no major purchase pattern → emit a quest with a large material reward instead of a gold reward.

**What Agent 1 (Quests) covered:**
- The reference trace. Comprehensive narrative-causal framing.
- §8 covered diversity dials extensively.

**What Agent 1 MISSED:**
- Behavior-causal quest firing was outside scope because Agent 1 was the calibrator. The pseudo-trace established the narrative-causal framing; behavior-causal quests are the natural extension.
- Failure-pattern-as-trigger is genuinely novel. A redemption arc quest is exactly the kind of "world responds to me" content the user's framing wants.
- Quest reward adaptation (`wes_quest_reward_adapt`) is behavior-aware at materialization time. But the QUEST itself being behavior-spawned was not in Agent 1.

**Bundle context needed:**
- `behavior_signal.quest_accept_pattern = {accepted_types: [delivery: 0.8, combat: 0.2], rejected_types: [...]}`.
- `behavior_signal.quest_completion_velocity = {avg_days_per_quest: 1.5, recent_failures: 10}`.
- `behavior_signal.inventory_state = {gold: 1200, primary_holdings: [...]}` (light slice).

**How it feeds the tool prompt:**
- Quest tool prompt: "If `behavior_signal.quest_accept_pattern` shows clear type preference, this quest's `quest_type` SHOULD favor the preferred type. Quality bar: not slavish — vary 20% of the time so the player isn't pigeonholed."
- Quest description should be intentionally vague about the player's history (per §8): "Few among the unfamiliar would have answered. You are familiar." NOT "You have completed 50 delivery quests."

**Highest-leverage finding for Quests:** the behavior-causal failure-pattern trigger (the redemption arc) is the strongest "world recognizes me" quest pattern available. It's also the cleanest demonstration that the world's response can be SUPPORTIVE, not just iterative-difficulty. The pool refresh rule that Agent 1 specced should include a behavior-causal branch.

### 4.9 Synthesis table

| Tool | Behavior-causal weight | Primary behavior triggers | Prior trace coverage | Highest-leverage finding |
|---|---|---|---|---|
| Skills | **HIGH** | Usage milestone, discipline mastery, death-by-source | Spec'd as future endpoint | Behavior is FIRST-CLASS, not future |
| Titles | **HIGH** | Threshold no title honors, signature pattern | Runtime-coupled, not WES-firing-coupled | Pool must EXPAND behavior-causally |
| Chunks | **MIXED** (canonical) | Exploration milestone + activity profile | Narrative half done | DAG inheritance: behavior flavor propagates |
| Hostiles | **MID-HIGH** | Kill count, death-by-source, combat style | Narrative-only | Anti-strategy hostiles + tier-up variants |
| Materials | **LOW-MID** | Gather count, discipline demand | Narrative-only | Mostly DAG-inherited; rare standalone |
| Nodes | **LOW-MID** | Per-node depletion | Narrative-only | Mostly DAG-inherited; rare standalone |
| NPCs | **LOW** | Avoidance, faction trajectory | Narrative-only (correct) | Behavior tunes existing NPCs (dynamic_context) more than generates new ones |
| Quests | **MID-HIGH** | Accept pattern, failure pattern, velocity | Narrative-only | Redemption arc / accept-type bias |

The pattern: **content tools that respond to PLAYER IDENTITY (Skills, Titles, Hostiles, Quests) want behavior-causal triggers strongly. Content tools that build WORLD SUBSTRATE (Chunks, Materials, Nodes, NPCs) want behavior triggers in DAG inheritance more than in standalone firings.**

---

## 5. WMS → WNS milestone plumbing spec

Agent 9's contract identified the empty-NarrativeDelta gap at `wns_to_wes_bridge._build_narrative_delta` (`wns_to_wes_bridge.py:133-152`). The function constructs a NarrativeDelta with `npc_dialogue_since_last[]` and `wms_events_since_last[]` left empty. Verified against current code.

The behavior-causal path needs ADDITIONAL plumbing beyond Agent 9's spec.

### 5.1 The pipeline today (narrative-causal only)

```
WMS event published → TriggerManager.on_event → TriggerAction emitted
                                                       ↓
                          WMS interpreter consumes (creates L2 InterpretedEvent)
                                                       ↓
                                   L2 row stored in event_store
                                                       ↓
                       Cascade-by-N counter increments at this address
                                                       ↓
                          NL2 weaver fires (every 3 L2 events) → builds bundle → emits <WES>
```

**The TriggerAction is consumed by the WMS interpreter ONLY.** The WNS does not see the threshold-crossing event directly; it sees the L2 row the interpreter produced. By the time the WNS reads it, the threshold-ness has been flattened into chronicler prose.

### 5.2 The proposed addition (behavior-causal path)

```
WMS event published → TriggerManager.on_event → TriggerAction emitted
                                                       ↓
                  ┌────────────────────────────────────┼────────────────────────────────┐
                  ↓                                                                      ↓
   WMS interpreter consumes (existing)                          NEW: WNS BehaviorInterpreter consumes
        ↓                                                                  ↓
   L2 row stored                                          Decision: does this threshold warrant a WES dispatch?
        ↓                                                                  ↓
   Cascade-by-N → NL weaver                            If YES: synthesize <WES> directive WITHOUT going through NL weaver
                                                                          ↓
                                                       Bundle is assembled with trigger_archetype="behavior"
                                                                          ↓
                                                       WES Orchestrator runs the plan
```

**Two key properties:**
1. The TriggerAction stream is FORKED. Both subscribers consume the same events; they make different decisions.
2. The behavior-causal path can BYPASS the NL weaver because the behavior signal is the content of the directive. The "narrative" in the bundle for a behavior-causal firing is the WMS L2 interpretation row, NOT a fresh weaver output.

### 5.3 The WNS BehaviorInterpreter — proposed shape

A new module: `world_system/wns/behavior_interpreter.py`. Subscribes to `WMS_TRIGGER_FIRED` on the GameEventBus (a NEW bus event the trigger_manager publishes when it returns a TriggerAction).

```python
class BehaviorInterpreter:
    def __init__(self, stat_store, daily_ledger, event_store, geographic_registry):
        ...

    def on_trigger_fired(self, action: TriggerAction) -> None:
        # 1. Should this threshold trigger a WES dispatch?
        if not self._is_dispatch_worthy(action):
            return  # most thresholds are silent; only ~10-20% become dispatches

        # 2. Build the behavior signal
        signal = self._build_behavior_signal(action)
        #    .counter_path, .threshold_crossed, .activity_profile,
        #    .inferred_behavior_intent (1-2 sentences interpreting what the
        #     player is DOING — this is the "looking at the ledger the WNS
        #     thinks that the player is using them in combat" step)

        # 3. Synthesize the WES directive
        directive = self._compose_directive(signal)
        #    Selects purpose from {new-skill, new-title, new-hostile, new-quest, ...}
        #    based on counter_path category.
        #    Body is a 1-2 sentence prose framing of what content should fire.

        # 4. Build the bundle
        bundle = self._build_behavior_bundle(action, signal, directive)
        #    trigger_archetype="behavior"
        #    behavior_signal=signal
        #    narrative_context.firing_layer_summary = the WMS L2 row text
        #    (no weaver narrative because no weaver fired)

        # 5. Publish WNS_CALL_WES_REQUESTED with the bundle
        self._bus.publish("WNS_CALL_WES_REQUESTED", {"bundle": bundle.to_dict()})
```

### 5.4 `_is_dispatch_worthy` heuristics

Not every threshold warrants a WES dispatch. Most don't. The interpreter applies rules:

- **Suppress** if the counter is too low-significance: `(player, item_consumed, common_oak_log, ANY)` at 25 → not interesting.
- **Suppress** if the same counter fired a dispatch recently (e.g. last 100 game-minutes): cooldown.
- **Suppress** if the activity_profile shows the player is in transit, not engaged: high `record_movement` with low engagement events.
- **Suppress** if the threshold is a low rung (1, 3, 5) — these are too noisy.
- **Allow** for milestone rungs at 100+ for stream-counts and 250+ for regional-counts.
- **Allow** for ANY threshold if the counter is high-significance: `(player, enemy_killed, BOSS, ANY)` at 1, `(player, title_earned, ANY, ANY)` at 1 (meta-trigger: a title earn might trigger MORE content).
- **Allow** for negative-pattern triggers (StatStore aggregation showing the player has STOPPED doing X recently).

These rules are designer-tunable prose, similar to `scope_by_firing_tier` for the planner. Suggested home: `world_system/wns/behavior_dispatch_rules.json`.

### 5.5 Per-layer behavior-causal eligibility

The behavior interpreter's directives need a `firing_tier` like narrative-causal ones. How is firing_tier chosen for a behavior trigger?

| Behavior trigger scope | Firing tier (NL layer) |
|---|---|
| Stream-count threshold at a specific locality | NL2 (locality) |
| Regional-count threshold at a locality | NL2 (locality) |
| Cumulative threshold across multiple localities in a district | NL3 (district) |
| Cumulative across multiple districts in a region | NL4 (region) |
| Cumulative across multiple regions in a province | NL5 (province) |
| Provincial-or-higher counts | NL5-NL7 (rare; usually a meta-milestone like "player has played 1000 game-days") |

**The firing tier of a behavior-causal directive is the smallest scope that encompasses the events that triggered it.** A 100-rider-kill-in-the-moors milestone is locality-scope (NL2); a 1000-rider-kill-across-all-coast-marches milestone is district-scope (NL3); a "kill 1 of the only boss in the world" is world-scope (NL7).

What each layer is interpretable for behavior-causally:
- **NL2:** stream-counts at a locality; "the player has done X at this place." Most behavior-causal firings.
- **NL3:** cross-locality patterns; "the player is making a habit of X across the coast." Mid-frequency.
- **NL4:** regional-pattern milestones; "the player has invested heavily in this region." Less frequent.
- **NL5+:** civilizational-scale player milestones; "the player has played a long game; the world knows them." Rare.

### 5.6 The "journal-only vs. WES dispatch" decision

NOT every behavior-worthy threshold needs a WES dispatch. Some can be JOURNAL-ONLY — a chronicler-voice WMS L2 row plus a WNS narrative entry, but no content generation. The user's mention: "the WNS can when consolidating ALSO choose to trigger the WES." The "also" implies the consolidation may decide to ONLY narrate (no dispatch).

Decision rules:
- **Journal-only** if the milestone is interpreted as a quiet recognition: "the moors have learned your tread." Narrative row, no content.
- **Dispatch** if the milestone implies the world has CAPACITY to respond — a usable skill, a recognizable title, a new tier of foe.
- **Dispatch + Journal** for major milestones: both narrative and content respond.

This decision lives in the behavior interpreter, configurable via `behavior_dispatch_rules.json`.

### 5.7 Bundle schema extensions for behavior-causal

Per Agent 9's contract, `BundleToolSlice` extensions are already needed for parent_summaries, firing_layer_summary, geographic_chain, etc. For behavior-causal firings, ADD:

```python
@dataclass
class BehaviorSignal:
    counter_path: str             # "items.consumed.potion.use_count"
    threshold_crossed: int        # 1000
    stream_count: int             # current count (post-threshold)
    locality_id: str              # where this fired
    activity_profile: Dict[str, float]  # {combat: 0.78, gathering: 0.1, ...}
    inferred_behavior_intent: str  # "the player relies on potions for emergency healing in combat"
    matching_pool_entries: List[str]  # existing skills/titles/etc that may match — empty if pool gap
    session_delta: Dict[str, Any]  # cross-session trajectory (optional)

@dataclass
class WESContextBundle:
    # ... existing fields ...
    trigger_archetype: str = "narrative"     # "narrative" | "behavior" | "mixed"
    behavior_signal: Optional[BehaviorSignal] = None
```

**`[WES-SCHEMA-GAP]`** on the bundle: add `trigger_archetype` and `behavior_signal`. The slice carries them through to the hub and tool unchanged.

### 5.8 `[WMS-GAP]` walk — was there one?

**Temptation:** "The WNS BehaviorInterpreter needs to read `activity_profile(locality_id)` — a per-locality discipline-mix dict. This doesn't exist as a single StatStore accessor today."

Walking the 9 rungs:

1. **Direct query.** StatStore doesn't have an `activity_profile` method. **Fail at the convenience layer.**
2. **Adjacent events.** Per-event-type counts at a locality ARE in StatStore. Summing them by event_category (which already exists in `EVENT_CATEGORY_MAP`) gives the activity profile.
3. **Negative patterns.** Inverse (what's NOT happening at this locality) is constructible.
4. **Aggregation.** `daily_ledger.py` aggregates per-day, per-locality. Per-category roll-up is a sum.
5. **Trajectory.** Same shape, queryable over a time window.
6. **Cross-layer climb.** Not relevant for this signal.
7. **Cross-entity composition.** Not relevant.
8. **Stat / ledger lookup.** This IS the rung. The data exists in StatStore + daily_ledger; the convenience accessor doesn't.
9. **Trigger history.** TriggerManager state exposes per-counter history.

**Verdict.** NOT a WMS gap. The data is fully available; an accessor convenience method (StatStore.activity_profile(locality_id)) is missing. Marker: `[FRAGMENT-GAP]` — write the helper.

**Zero `[WMS-GAP]` markers raised in this trace.** Consistent with Waves 1-3.

### 5.9 Summary of plumbing changes

| Change | Scope | Marker |
|---|---|---|
| Publish `WMS_TRIGGER_FIRED` bus event from trigger_manager | TriggerManager extension | `[WNS-GAP]` (it's a WMS→WNS interface) |
| `BehaviorInterpreter` module in `world_system/wns/` | New module | New code |
| `behavior_dispatch_rules.json` config | New config | New file |
| `BehaviorSignal` dataclass + bundle extensions | dataclass + bundle | `[WES-SCHEMA-GAP]` |
| `StatStore.activity_profile(locality_id)` helper | StatStore extension | `[FRAGMENT-GAP]` |
| WMS L2 row text accessible for behavior-causal firings as `firing_layer_summary` | Existing infrastructure (WMS L2 rows are queryable) | No marker — already works |
| `slice_bundle_for_tool` propagates trigger_archetype + behavior_signal | Existing slice fix scope | `[WES-SCHEMA-GAP]` (subsumes Agent 9's slice fix) |

---

## 6. Planner / supervisor handling of behavior-causal dispatch

Agent 10's spec for the planner and supervisor was anchored on narrative-causal firings. The behavior-causal path needs supplementation.

### 6.1 Does the planner prompt need an explicit `trigger_archetype` discriminator? YES.

Per §5.7 the bundle carries `trigger_archetype` and `behavior_signal`. The planner must read both. The prompt needs:

- A discriminator clause: "if `trigger_archetype` is `behavior`, apply the behavior scope rules; if `narrative`, apply the standard tier scope rules; if `mixed`, apply BOTH and take the union of allowed purposes."
- A new `scope_by_behavior_threshold` prose section (companion to `scope_by_firing_tier`).

**`[FRAGMENT-GAP]`** on the planner prompt: add the discriminator and the scope-by-behavior-threshold prose. Below is a draft.

### 6.2 `scope_by_behavior_threshold` prose — draft

```
SCOPE BY BEHAVIOR THRESHOLD (when trigger_archetype = "behavior" or "mixed"):

The behavior_signal field tells you what the player has been doing at scale.
The scope of the plan is driven by the COUNTER PATH and the THRESHOLD CROSSED,
NOT primarily by the firing_tier.

Counter path categories and typical plans:

- items.consumed.* (potion / scroll / consumable usage at threshold):
    Allowed: 1 skill (utility/healing/effect mirror) OR 1 title. Forbidden: chunks,
    factions, NPCs.

- combat.kills.{species}.{locality} (kill-count per species at locality):
    Allowed at 100: 1 hostile (tier-up variant of {species}) at {locality}.
    Allowed at 500: 1 hostile (sister-species) at adjacent locality OR 1 title
    referencing the kill pattern. Forbidden: chunks (unless mixed with narrative
    rumor of new terrain).

- combat.deaths.by_source.{type} (death-by-damage-type):
    Allowed: 1 hostile that TEACHES handling of {type} (anti-pattern encounter)
    OR 1 skill that COUNTERS {type}. Forbidden: titles (titles for dying are
    cynical).

- gathering.resources.{material}.{locality} (gather-count per material):
    Allowed at 1000: 1 material (refined-tier of {material}) at {locality}.
    Allowed at 5000: 1 material (sister-material) at adjacent locality OR 1
    title for the gathering pattern.

- crafting.{discipline}.attempts (crafting count in a discipline):
    Allowed at 500: 1 skill (discipline utility) OR 1 title (master craftsman
    variant).

- exploration.chunks_entered.count (exploration milestone, GLOBAL):
    MIXED-TRIGGER ONLY: requires narrative_context to also imply new terrain.
    If mixed: 1 chunk (biome flavored by activity_profile dominance) + downstream
    DAG (nodes, hostiles, materials inheriting chunk's behavior flavor).
    If pure behavior: prefer journal-only narrative; chunks are too expensive
    to spawn from raw exploration count.

- progression.titles_earned (meta-trigger: player just earned a title):
    Allowed: 0-1 of {npc that recognizes the title, quest gated on the title}.
    Often journal-only.

CROSS-CUTTING BEHAVIOR-CAUSAL RULES:

- BEHAVIOR FIDELITY: every emitted step's intent MUST reference the
  behavior_signal.counter_path OR the inferred_behavior_intent. A behavior-causal
  plan that emits content unrelated to the milestone is wasted.

- POOL CHECK: read behavior_signal.matching_pool_entries. If non-empty, the pool
  already has content matching the player's pattern. Plan may emit a higher-tier
  variant; should NOT emit a near-duplicate of existing content.

- COOLDOWN AWARENESS: behavior triggers are higher-volume than narrative triggers.
  If recent_registry_entries shows behavior-causal content for the same counter
  at this address in the last few firings, ABANDON with reason "behavior cooldown
  active for this counter."

- VAGUE LINEAGE: behavior-causal content's narrative prose should NOT reference
  the specific milestone count. Pass flavor_hints.prose_ambiguity_directive = true
  so the tool writes "the world has noticed" rather than "after your 1000th
  potion."

- MIXED TRIGGER: when trigger_archetype is "mixed", the plan should leverage BOTH
  contexts. Chunk plans MUST attach flavor_hints.behavior_inheritance to
  downstream DAG steps. NPC plans MUST attach narrative voice anchors AND
  behavior recognition hints.
```

### 6.3 Does Agent 10's `scope_by_firing_tier` ("narrative authority") prose still hold? YES, with supplementation.

Agent 10's framing is correct for narrative-causal: tier-2 firings have locality-narrative authority and shouldn't author kingdom-scale content. **That principle holds.**

For behavior-causal, the principle is DIFFERENT: the firing tier is the SMALLEST scope that encompasses the events that triggered it (§5.5). A locality-scope behavior trigger has locality authority; a province-scope behavior trigger has province authority. Same tier discipline, different driver (the events' geographic extent, not the weaver's narrative voice).

The planner prompt needs BOTH: the existing `scope_by_firing_tier` for narrative, the new `scope_by_behavior_threshold` for behavior. Mixed cases apply both.

### 6.4 Does the supervisor evaluate behavior-causal content with different acceptance criteria? YES.

Agent 10 specced 6 supervisor checks. For behavior-causal, supplement:

**Existing checks (apply to all):**
1. Schema validity — same.
2. Directive fidelity — for behavior, fidelity is to the BEHAVIOR SIGNAL, not (only) to the directive prose.
3. Thematic coherence across artifacts — same.
4. Scope fidelity — apply behavior scope rules, not narrative tier scope rules.
5. Narrative voice — for behavior-causal, the voice should be VAGUE about the milestone (§8 ambiguity). Supervisor flags "skill narrative explicitly states the player used 1000 potions" as a fidelity FAIL.
6. Balance tells — same.

**New checks (behavior-causal only):**
7. **Behavior-artifact fidelity.** Does the staged content USE the milestone artifact? If the trigger was `items.consumed.potion.use_count`, the resulting skill MUST mention potions or healing in its combat tags / effect / description. A skill that emerges from a potion milestone and is a fire-attack skill is a FAIL.
8. **Pool-gap rationality.** If `behavior_signal.matching_pool_entries` was non-empty, did the plan generate content meaningfully DIFFERENT from existing pool entries? If a tier-1 potion-skill already exists and the plan generates another tier-1 potion-skill of the same shape, FAIL.
9. **Cooldown respect.** If the cooldown rule should have triggered abandonment but the planner ignored, FAIL.

**`[FRAGMENT-GAP]`** on the supervisor prompt: add checks 7-9 in a "BEHAVIOR-CAUSAL CHECKS (when trigger_archetype != 'narrative')" subsection.

### 6.5 How does the planner handle mixed triggers? The Chunks-pseudo-trace case.

When `trigger_archetype == "mixed"`:

- Planner reads BOTH `narrative_context.parent_summaries` AND `behavior_signal`.
- Plan scope is the BROADER of (narrative tier scope, behavior threshold scope).
- For chunks specifically: the plan should attach `flavor_hints.behavior_inheritance` to downstream DAG steps so the chunk's behavior-flavor propagates.
- Rationale text should explicitly acknowledge BOTH triggers: "Mixed trigger — NL4 rumors of new terrain + exploration milestone at 10000 chunks. Chunk theme tilted toward player's heavy alchemy activity. Downstream nodes + hostiles + materials inherit alchemy-flavor."

This is the unification thesis at the planner layer: one plan, both signals, one rationale.

### 6.6 RequestLayer interaction with behavior-causal triggers

The RequestLayer (Agent 10's third endpoint) handles orphan resolution. For behavior-causal content:

- Cascade-generated content (hostiles emerging because a chunk named them) should INHERIT the parent chunk's `behavior_inheritance` flavor_hint. **`[FRAGMENT-GAP]`** on RequestLayer.build_specs: when the requesting payload carries `behavior_inheritance`, propagate to the cascade spec's flavor_hints.
- The behavior_signal itself can OPTIONALLY be passed to cascade specs. For a hostile spawning from a behavior-driven chunk firing, the hostile MAY use the activity_profile context — but most often it just inherits the chunk's flavor without needing the raw behavior_signal.

This is a small addition to Agent 10's spec; the cascade pattern is unchanged in shape.

---

## 7. Cross-archetype interaction (the unification surface)

The two paths INFORM each other. This section specifies how.

### 7.1 Behavior-causal content feeding back into narrative

When a behavior-causal skill is generated and the player learns it, the NPC dialogue and WMS narrative should be ABLE to reference it. Concretely:

- The newly-generated skill commits to `reg_skills`. The skill has `tags` (per Agent 6's recommendation) that include behavior-causal markers (`origin:behavior_emergence`, `milestone_anchor:potion_use`).
- Future NL weaver firings at the player's locality have these skill rows available in `${wms_context}` (via `event_store` queries filtered by `affects_tags=["skill:{skill_name}"]`).
- NL2-NL4 weavers can WEAVE the player's new behavior-causal skill into local narrative. "The Tarmouth garrison has begun to ask how the wanderer brews their reflex-vials so quickly."
- NPCs can REACT via `personality.reaction_modifiers.SKILL_LEARNED` with `skill_match` (Agent 6 §6.4 already specced this). A behavior-causal skill triggers NPC reactions like a narrative one.

**Result.** The behavior-causal content is RE-NARRATED by the world. The player's identity becomes part of the world's story going forward. **This is what makes the world feel like it's paying attention.**

### 7.2 Narrative-causal context feeding behavior interpretation

When a narrative-causal firing wants to interpret the player, it reads the activity_profile and behavior history. Concretely:

- The behavior interpreter's `activity_profile` accessor is ALSO available to narrative-causal NL weavers (via the bundle's `behavior_signal` field — which can be populated in narrative bundles too, just at a smaller scope).
- A narrative-causal NL3 weaver at "the moors are restructuring" thread can READ the player's heavy alchemy activity and slant the narrative: "The moors-stone smelters have begun to notice the alchemist who walks among them."
- The NPC tool, when generating an NPC for a narrative-causal firing, can read activity_profile to tune the NPC's `personality.reaction_modifiers` — an alchemy-heavy player gets NPCs whose first reactions are alchemy-flavored.

**Result.** The narrative-causal generation is FLAVORED by the player's identity. Same world responds; same content tools; different shape per player.

**`[WES-SCHEMA-GAP]`** (small): bundle's `behavior_signal` should be populated even on narrative-causal firings, as a SMALL slice. The activity_profile at firing locality is cheap to compute and always useful. **Cross-archetype enrichment.**

### 7.3 The DAG-inheritance cascade — concrete spec

Per §4.3 the chunks pseudo-trace canonical case. Concrete plumbing:

1. Mixed-trigger NL4 firing emits `<WES purpose="new-chunk">a new chunk type, tilted toward the player's heavy alchemy activity, in line with the regional rumors of strange terrains</WES>`.
2. Bundle carries `trigger_archetype="mixed"`, `behavior_signal.activity_profile.alchemy=0.6`, `narrative_context.parent_summaries[region]="rumors of new terrains south of the moors"`.
3. Planner emits plan: `[materials, nodes, hostiles, chunks]` with DAG order (chunks last per Agent 8). Each step's `flavor_hints` carries `behavior_inheritance = "alchemy"` (NEW field).
4. Materials tool reads `flavor_hints.behavior_inheritance`. Generates `fungal_spore_essence` (an alchemy reagent) instead of generic `oak_log`.
5. Nodes tool reads same. Generates `spore_bog_node` referencing the new material.
6. Hostiles tool reads same. Generates `mire_alchemist` — a hostile that uses alchemy attacks, drops alchemical components.
7. Chunks tool reads same. Generates `fungal_bog_chunk` with the new node + the new hostile in `enemySpawns`.

**The cascade is unified.** One trigger event (mixed) birthed four content artifacts that all share alchemy-flavor. The alchemy flavor came from the PLAYER'S BEHAVIOR (their 60% alchemy time allocation). The terrain rumor came from the WNS narrative. The combination feels: "the world is responding to me AND telling a story."

**`[FRAGMENT-GAP]`** on every WES hub: read `step.flavor_hints.behavior_inheritance` and propagate as `${behavior_flavor}` template variable to the tool. Each tool's prompt has a clause: "If `${behavior_flavor}` is set, tilt this output toward that discipline/style. Subtlety preferred — not a theme park, but a flavor."

---

## 8. Prose-ambiguity sweep

The user's second correction: skill evolution prose should be intentionally vague ("master its usage in the native environment"), NOT checklist-exact ("kill 50 copperlash riders in the salt moors"). This applies broadly. Designer ambiguity in prose fields PRESERVES MYSTERY; checklist exactness destroys it.

This section sweeps the 10 prior traces for prose fields that were likely over-specified, distinguishes structural fields (where exactness matters) from prose fields (where ambiguity matters), and proposes ambiguity guidance per field.

### 8.1 The principle

A field is **structural** if downstream code reads it as data (xref IDs, numeric requirements, enum values, machine-checked conditions). Structural fields MUST be exact.

A field is **prose** if it is read by the PLAYER or by a HUMAN designer. Prose fields preserve mystery by being evocative-but-unspecific.

The failure mode the user named: a skill's `evolution.requirement` reading "kill 50 copperlash riders in the salt moors" is a checklist. The player sees it and treats the game as a checklist game. The mystery dies. The same field reading "master its usage in the native environment" is a hook. The player explores to find what "native environment" means. The mystery lives.

### 8.2 Sweep per trace

For each trace, identifying the prose fields that were likely overspecified, plus proposed ambiguity guidance for each.

#### 8.2.1 Trace 01 (Quests)

- **`completion_dialogue`** (the giver's line on turn-in): MOSTLY good in Agent 1 — the example "wandered the moors at the edge of the haze plague" is evocative. Risk: at scale, hubs may instruct tools to write completion lines that enumerate the deeds explicitly. **Guidance:** the line should reference the deed by FEEL, not by enumeration. "You walked through what most would not" beats "You killed 5 copperlash riders."
- **`description_full.objectives`**: STRUCTURAL — objectives are machine-checked. Keep exact.
- **`description_full.narrative`**: PROSE — Agent 1 covered this well. Vagueness already encouraged.
- **`expiration.body_text`**: PROSE — the explainer line for when a quest expires. Should be vague: "The trail has gone cold" not "10 game-days have passed since acceptance."

#### 8.2.2 Trace 02 (NPCs)

- **`personality.voice`**: PROSE — Agent 2's framing is good. Keep evocative.
- **`narrative.past`** (the immutable past prose): PROSE — should be specific to the NPC but not narratively-deterministic. "His brother died on the moors-stone" is good. "His brother died on day 47 of game-time year 1 due to incident X" is wrong.
- **`speechbank.quest_offer` (single lines)**: PROSE per line. Each should be evocative without scripting.

#### 8.2.3 Trace 03 (Hostiles)

- **`lore_description`** (the hostile's narrative description in encyclopedia / death-screen): PROSE. Agent 3's quality bar mentioned "the moors raider line" — vague-but-rooted. **Guidance:** "Hardened by the salt. They have learned what you fight like" beats "Has +20% defense vs ranged due to evolutionary adaptation after 1000 player ranged attacks."
- **`drops`** keys: STRUCTURAL — exact material IDs.
- **`drops_lore`** (if added per Agent 3): PROSE — "Carries copper from old veins" beats "Drops moors_copper at 80% chance."

#### 8.2.4 Trace 04 (Materials)

- **`description`** (in-game item description): PROSE. **Guidance:** "Rarer than its cousin, found by those who know where to look" beats "Drops at 1% rate in regions with player gather count > 1000."
- **`tier`, `category`**: STRUCTURAL.

#### 8.2.5 Trace 05 (Nodes)

- **`narrative`** (node's flavor description): PROSE. Same pattern as materials.

#### 8.2.6 Trace 06 (Skills) — **THE USER'S NAMED CASE**

- **`description`**: STRUCTURAL-ADJACENT. Agent 6 §1.3.d named the "description must match dispatch" contract — the description is a literal English rendering of the mechanical effect. **This is correct and SHOULD remain exact.** The player reads description and predicts dispatch.
- **`narrative`**: PROSE. Agent 6 §3.2.4 example "Moors raiders favor the copperlash — a short whip weighted with ore slugs" is lineage-anchored but not checklist. Good.
- **`evolution.requirement`**: THE NAMED FAILURE. Agent 6 §3.2.8 example: "Slay 50 copperlash riders in the salt moors." This is the checklist failure mode the user flagged.
  - **Per user direction:** "evolution should not be a prose that is so exact. Prose is fine, but shouldn't be a checklist type thing. Something more vague like 'master its usage in the native environment' or something intentially ambigous."
  - **Proposed guidance:** the tool prompt for `evolution.requirement` should require: "1-2 sentences, evocative, intentionally ambiguous. The PLAYER should not be able to derive a checklist from it. Reference what the skill THEMATICALLY needs — mastery, environment, opposition, repetition — without naming counts or specific entities. Acceptable: 'Master its usage in the native environment.' 'Survive what it cannot.' 'The skill seasons with use.' Unacceptable: 'Use 100 times.' 'Kill 50 of X.' 'Apply in chunk Y.'"
  - **Runtime impact:** today `evolution.requirement` is "NOT machine-checked currently — descriptive only" (Agent 6 §2 table). The ambiguity is RUNTIME-COMPATIBLE — the runtime doesn't read this string. The deterministic evolution gate (per the runtime evaluator) lives elsewhere if it exists at all. So designer-vague is purely a player-facing benefit; no runtime cost.

#### 8.2.7 Trace 07 (Titles)

- **`description`**: PROSE. **Guidance:** "Fire-veined ores call to you" beats "+25% mining damage." Agent 7 already correctly named this.
- **`narrative`** (the 2-3 sentence chronicler line): PROSE. Agent 7 §1.4 example "I have 'Lighthouse Veteran of Brackhollow.' I got it because I survived three different lighthouse keepers' funerals during the haze plague" is GOOD — vague-but-rooted.
- **`signature_deeds[]`** (Agent 7 proposed schema addition): MIXED. The structural side is "1-3 short string descriptors." The CONTENT of those strings should be EVOCATIVE-ROOTED, not checklist-exact. **Guidance:** "Carried the lighthouse-keeper's salt across three mournings" beats "Completed 3 funeral-quests in Brackhollow."
- **`prerequisites.conditions[]`**: STRUCTURAL — runtime-evaluated. Keep exact (`stat_path`, `min_value`, etc.).

#### 8.2.8 Trace 08 (Chunks)

- **`metadata.narrative`** (the chunk's 2-3 sentence flavor): PROSE. Agent 8 §3.2.5 example "windswept moors of rust-veined cliffs and boggy flats" is GOOD — sensory, specific, but not enumerative.
- **`generationRules.adjacencyPreference[]`**: STRUCTURAL (chunk-type IDs).
- **`metadata.tags[]`**: STRUCTURAL (allow-list values).

#### 8.2.9 Trace 09 (WNS)

- **`narrative`** field on every NarrativeRow: PROSE (the entire artifact). Per Agent 9 §1.4 and §8 voice rules — already prose-discipline-aware.
- **`headline`** (Agent 9 proposed schema addition): PROSE — 5-8 evocative words.
- **`payload.entity_refs[]` `.name` field**: STRUCTURAL (must match registry name for linking).

#### 8.2.10 Trace 10 (Orchestration)

- **`step.intent`** (planner output): PROSE-STRUCTURAL hybrid. The intent must be specific enough for the hub to derive constraints (structural), but evocative enough for downstream prose generation (prose). Agent 10 §2.1 table named the bar correctly. **Guidance:** the intent should reference proper nouns from the bundle but not enumerate counts/conditions. "Vendetta hunt issued by Captain Vell against his own copperlash riders" is right. "Vendetta hunt: kill 5 copperlash riders for Captain Vell, reward 100 gold + Apprentice Reaver title" is wrong (steps the hub's job, robs the tool's interpretive room).
- **`rationale`** (planner output, supervisor-read): PROSE for the supervisor. Should explain logic without checklist enumeration.
- **`adjusted_instructions`** (supervisor output, planner-read): PROSE-INSTRUCTIONAL. Should be specific enough to actually guide a fix. NOT meant for the player; can be more structural than other prose fields.

### 8.3 The most overspecified prose field across the 10 traces

**`evolution.requirement` in Trace 06 (Skills).** The user named this directly. The trace example "Slay 50 copperlash riders in the salt moors" is the cleanest single example of the failure mode across all 10 traces.

Runner-up: **`evolution.canEvolve` + `evolution.nextSkillId` chain mechanics**, which Agent 6 §8.8 specced as a planner-level emission of 3-skill chains with "evolution.requirement" prose between them. The temptation to over-specify the requirement at chain-step boundaries is high. The fix is the same: vague-but-rooted prose at each chain step.

### 8.4 The prose-ambiguity directive — proposed prompt clause

For every prose field across all 8 tools, add to the relevant prompt fragment:

```
PROSE AMBIGUITY DIRECTIVE:

Prose fields (description, narrative, lore_description, evolution.requirement,
narrative.past, completion_dialogue, headline, metadata.narrative, voice lines,
signature_deeds) MUST be evocative-but-vague. The PLAYER should not be able to
derive a checklist from them.

Acceptable patterns:
- "Master its usage in the native environment."
- "The hand knows before the mind names the wound."
- "Carries copper from old veins."
- "The moors have learned your tread."
- "She has seen wanderers come and go; she will see you go too."

Unacceptable patterns:
- "Use 100 times."
- "Kill 50 of [species] in [chunk_id]."
- "Defeat the boss [boss_name] to unlock."
- "Trigger when player.[stat] > [value]."
- "Achievable by completing quests [quest_id_1, quest_id_2, quest_id_3]."

The line between specific and checklist: SPECIFICITY ANCHORS THE FEEL; ENUMERATION
REVEALS THE MECHANIC. Anchor in feel; never reveal the mechanic.

When trigger_archetype is "behavior", this directive applies WITH EXTRA FORCE.
A behavior-causal artifact whose prose explicitly references the milestone
("You earned this by using 1000 potions") destroys the illusion that the world
is responding organically. The world has noticed; the world does not enumerate.
```

Designer-shared across all 8 tool prompts. Single fragment in `prompt_fragments.json` keyed `prose_ambiguity_directive`, included in every tool's system prompt.

---

## 9. Speculative future endpoints (trigger-system only)

Per user constraint: NO new content tools (recipes and equipment are handled by the player-driven crafting LLM `systems/llm_item_generator.py` + `systems/crafting_classifier.py`). This section lists trigger-system endpoints only.

### 9.1 `wns_behavior_interpreter` — the new module

Per §5.3. **NOT speculative — required for the behavior-causal path to exist at all.** Promoted to first-class.

### 9.2 `wns_behavior_pattern_evaluator` (deterministic, not LLM)

A pre-WNS pass that aggregates recent threshold events at an address into a small `inferred_behavior_intent` string. Today proposed as part of BehaviorInterpreter; could be a separate evaluator that runs more frequently than dispatch decisions. Allows `inferred_behavior_intent` to live in the bundle on EVERY firing, not just behavior-causal ones — supporting the §7.2 cross-archetype enrichment.

### 9.3 `wns_mixed_trigger_arbiter` (deterministic, with optional LLM tie-break)

When narrative and behavior signals BOTH want a firing at the same address in the same time window, decide whether to issue ONE mixed firing or TWO separate firings.

- **Trigger:** behavior interpreter wants to fire AND a WNS weaver is queued to fire at the same address within N seconds.
- **Inputs:** both candidate firings.
- **Outputs:** {issue_mixed | issue_both | suppress_behavior}.
- **Latency:** deterministic preferred; LLM-tie-break for edge cases.

Probably deterministic. Cheap.

### 9.4 `wns_player_presence_drift_detector` (deterministic)

The user's hint: "player-presence-as-content trigger (player avoids a region for N ticks → faction loses awareness → WNS narrative shifts)." This is BEHAVIOR-CAUSAL via NEGATIVE PATTERN — the player is NOT at locality X.

- **Trigger:** locality affinity counter has decayed past threshold (player hasn't visited in N game-days).
- **Output:** a behavior-causal narrative firing at that locality: "Tarmouth has not seen the wanderer in two seasons. The harbor master no longer asks where they went."
- **Behavior signal payload:** `counter_path="exploration.locality_visits.tarmouth"`, `threshold_crossed=N_days_absent`, `inferred_behavior_intent="the player has abandoned this locality"`.

This is a BEHAVIOR-CAUSAL FIRING WITHOUT A POSITIVE THRESHOLD — the trigger is the COUNTER NOT MOVING. The 9-rung rung 3 (negative patterns) is doing the work.

**Endpoint count:** part of the BehaviorInterpreter — same module, different rule set.

### 9.5 `wms_behavior_signal_summarizer` (LLM, deferred)

When the BehaviorInterpreter decides to fire a behavior-causal directive, the `inferred_behavior_intent` is currently proposed as deterministic (a function of counter_path category + activity_profile). A small LLM call could produce richer prose for the intent — useful when the behavior pattern is subtle.

- **Trigger:** behavior interpreter wants richer interpretation than deterministic rules give.
- **Inputs:** activity_profile + counter history + recent L2 rows at the address.
- **Outputs:** 1-2 sentences of inferred behavior intent.
- **Latency:** cascade time; fine.

**Endpoint count:** +1 LLM task. Probably premature; deterministic rules cover 80% of cases. Build only if `inferred_behavior_intent` is showing as the weak link in playtest.

### 9.6 `wms_cooldown_arbiter` (deterministic)

Behavior triggers are higher-volume than narrative. Without a cooldown, the world responds to every threshold and the player is buried in new content. The cooldown logic lives in BehaviorInterpreter; an explicit arbiter module makes it testable.

- **Trigger:** behavior interpreter's `_is_dispatch_worthy` calls it.
- **Inputs:** counter_path + recent dispatch history at this address.
- **Outputs:** `{allow | suppress}` + cooldown remaining.
- **Latency:** sub-millisecond.

Deterministic. Required, not speculative — promoted alongside BehaviorInterpreter.

### 9.7 Bigger-picture: the trigger-system endpoint count

Pragmatic v4:
- `BehaviorInterpreter` (deterministic module; required).
- `BehaviorDispatchRules.json` (config; required).
- `CooldownArbiter` (deterministic submodule; required).

Speculative (defer or skip):
- `wns_behavior_pattern_evaluator` (probably folds into BehaviorInterpreter).
- `wns_mixed_trigger_arbiter` (defer; deterministic when needed).
- `wns_player_presence_drift_detector` (part of BehaviorInterpreter rule set).
- `wms_behavior_signal_summarizer` (LLM; deferred).

**No NEW content tools.** Constraint honored.

---

## End

Five load-bearing fixes this trace surfaces, ordered by leverage:

1. **Introduce trigger archetype taxonomy (narrative / behavior / mixed) as a first-class field on the WESContextBundle.** Extend BundleToolSlice and every hub/tool prompt to read `trigger_archetype` and (when present) `behavior_signal`. This is the single architectural addition that lets the prior 10 traces' content tools handle behavior-causal firings without inventing per-tool plumbing.

2. **Build the BehaviorInterpreter module.** Subscribes to `WMS_TRIGGER_FIRED` (new bus event from TriggerManager). Implements `_is_dispatch_worthy` + cooldown + directive composition + bundle assembly. The behavior-causal path does not exist until this module exists. Per §5.3.

3. **Sweep the prose-ambiguity directive across all 10 traces' prompt fragments.** Per §8. The user-named failure (`evolution.requirement` checklist exactness) is the cleanest example, but the same principle applies to title narrative, hostile lore, chunk description, NPC voice, completion dialogues, and signature_deeds. Single shared fragment, included by every tool's system prompt. Behavior-causal artifacts apply the directive WITH EXTRA FORCE.

4. **Spec the DAG behavior-inheritance propagation rule.** Per §7.3. When a mixed-trigger chunk fires, its `flavor_hints.behavior_inheritance` propagates down through the cascade to nodes, hostiles, materials. This is the unification thesis at its most concrete: one trigger event birthed an ecosystem all aligned to the player's identity. Touches RequestLayer + every hub.

5. **Extend the planner prompt with `scope_by_behavior_threshold` prose + the trigger_archetype discriminator + the behavior-causal supervisor checks (7, 8, 9).** Per §6. This is the orchestration layer's response to the new firing path — the planner must know how to dispatch on it; the supervisor must know how to verify it.

The unification thesis holds because: (a) the WES tools downstream are unchanged in shape; (b) both archetypes flow through the same pipeline; (c) the player cannot tell which archetype birthed which content because the prose ambiguity directive blocks them from seeing the trigger; (d) cross-archetype enrichment (§7) means even narrative-causal firings are flavored by player behavior, and behavior-causal content is re-narrated by the world.

The world becomes a unified responder. The player's identity flows in; new content flows out; the world's voice acknowledges both. **Two pathways, one seamless world.**
