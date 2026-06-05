# Feature Trace 02 — NPCs

**Wave:** 2 (parallel with Hostiles / Materials / Nodes / Skills / Titles / Chunks / WNS / Planner)
**Owned endpoints:** `wes_tool_npcs`, `wes_hub_npcs`, `npc_dialogue_speechbank`
**Final output artifacts:** (a) Static NPC v3 JSON committed to `progression/npcs-3.JSON`-shape registry (immutable past); (b) the dialogue lines the player literally reads when they walk up and press interact — greetings, idle barks, quest-offer line, quest-complete line, farewell line; (c) the dynamic context registry rows (npc_dynamic_state, npc_affinity, npc_dialogue_log) keyed by npc_id, which sit alongside the static and mutate at runtime.
**Date:** 2026-05-26

> "Voiced is the whole game. The slop NPC says 'Hello adventurer.' The stagnant NPC says it every time, forever. The crazy NPC says 'Greetings, son of the Convergence.' The benchmark is the NPC who remembers the moors and remembers what you just did there."

This trace is anchored on a player who has walked five steps into a village and pressed E on the figure standing by the well. The whole pipeline exists to make the line that pops up over that figure's head feel like it came from a person with a past, a place, a faction, and a current mood.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

The player approaches an NPC sprite. A name + title floats above their head (Captain Vell Sarn — Copperlash Captain). Player presses E. A dialogue panel opens with the NPC's portrait/sprite on the left and a greeting line on the right. The greeting is the FIRST thing the player reads in this conversation — it sets the entire impression. If the player keeps clicking through (with no quest in play), they get idle barks — short sentences in the NPC's voice that the player can read like the NPC is muttering to themselves or sharing local color. If the player has a quest from this NPC ready to turn in, the line shifts to quest_complete. If the NPC offers a quest, the player gets the quest_offer line as the lead-in before the scroll unfurls (see Quests trace §1).

That is the entire interaction surface NPCs own at the player layer. Everything else (faction affinity, gossip propagation, narrative threading) is INVISIBLE infrastructure — it manifests only through the lines and the consequences (quests gated, services unlocked, prices shifted).

There is also a secondary visible surface that's easy to overlook: **the NPC's presence in the world map**. Where they STAND, the position they spawn at, the chunk they belong to, the sprite color — these signal the NPC's belonging before the player has spoken a word. Cluster three militia-coded NPCs at a watchpost and the player learns the watchpost is militia territory without anyone saying it. This is silent worldbuilding the static JSON owns.

### 1.2 Timing budget — the dialogue is INSTANT, the speechbank is not

Unlike quests (scroll unfurl masks 2-3s of LLM), NPC dialogue at interact-time is **zero-latency**. The player presses E and the line appears. There is no animation slot to hide LLM latency. So the architecture is:

- **Speechbank is BIRTH-TIME pre-generated.** When `wes_tool_npcs` fires (during cascade), the speechbank dict (greeting[], farewell[], idle_barks[], quest_offer, quest_complete, phrase_bank) is fully populated on the static JSON. Interact-time is an inventory lookup — zero LLM latency.
- **LLM-powered dialogue (NPCAgentSystem.generate_dialogue) is OPT-IN and async.** The runtime has it but it's the secondary surface — used when the designer wants an open dialogue exchange ("Player types: 'What do you know about the moors?'"). The dialogue agent has its own latency budget (~1-3s typical with Sonnet) and the UI must mask it with a "..." typing indicator or buffer it asynchronously. **For v4 launch, the speechbank is the load-bearing path.** The agent is the luxury.
- **Speechbank refresh cadence is NOT interact-time.** When the WNS narrative moves on materially (new thread, faction conflict heats up, the captain's brother got mentioned again three sessions ago), a fresh `npc_dialogue_speechbank` firing regenerates greeting/idle_barks/phrase_bank with the new context. The refresh is on cascade, NOT on player interaction. The player gets the freshest speechbank that was last refreshed — which might be hours of play stale, but that's acceptable because speechbanks are written in immutable past-tense voice anyway. The captain's grievance from three winters ago doesn't change because the player wandered through last Tuesday.
- **Dynamic state updates are SYNCHRONOUS and CHEAP.** Affinity shifts, reputation tag additions, interaction_count increments — these run inline, no LLM, write to SQLite. The next interaction shows the updated state immediately.

This dictates two separate timing budgets:
- **Static-JSON pipeline** (`wes_tool_npcs` + `wes_hub_npcs`): runs on WNS cascade — same 5-20s budget as quests. Player never waits.
- **Speechbank pipeline** (`npc_dialogue_speechbank`): runs on WNS cascade OR on scheduled refresh — same budget. Player never waits.
- **Dynamic state writes**: synchronous, no LLM, microseconds.
- **Live LLM dialogue (luxury layer)**: 1-3s, masked by typing indicator. Out-of-scope for the immediate player-pressing-E moment.

### 1.3 Failure modes — what BAD looks like

Three flavors, plus an NPC-specific fourth:

**(a) Slop.** "Hello adventurer." "Welcome, traveler!" "Greetings." Generic placeholder text that could belong to any NPC in any game. The NPC has a name and a faction but the dialogue never references either. The personality.voice field exists but the speechbank ignores it. The phrase_bank is empty or contains generic words ("hello", "yes", "no"). *(Defense: phrase_bank pinning into every dialogue assembly. The home_chunk thematic anchors threaded through every speechbank line. The NPC's narrative voice surfaced as `voice_anchor` in flavor_hints. If a phrase_bank line doesn't sound like ONLY this NPC could have said it, it's slop.)*

**(b) Stagnant predictability.** Every NPC has exactly the same 5 greetings, 5 idle_barks, 1 quest_offer, 1 quest_complete that never change. After the player has talked to this NPC three times, they've seen everything the NPC will ever say. The world stops feeling like it's responding. *(Defense: (1) idle_barks should be 5-10 lines, cycled per the runtime's `_idle_index`. (2) Speechbank refresh cadence — when WNS thread state moves, the NPC's bank is regenerated with fresh content. (3) The LLM agent (NPCAgentSystem) handles the long-tail "what does Vell think of the copperlash retreat?" cases.)*

**(c) Craziness.** The LLM, given creative liberty, invents factions, places, events, relationships that don't exist. Captain Vell mentions his daughter (he has none), references the Convergence (doesn't exist), claims to be the son of the chieftain of the Salt-Drowned cult (no such cult is committed). Idle_barks reference materials, NPCs, and chunks that aren't in the registry. *(Defense: cross-ref discipline — home_chunk, teachableSkills, quests must exist or be co-emitted; thematic_anchors must be drawn from the home_chunk's narrative; the LLM is told phrase_bank lines must sound like this culture, not like fantasy-pastiche; orphan detector catches refs.)*

**(d) Voice incoherence across the speechbank.** This is NPC-specific. The narrative says Captain Vell is "clipped, salt-dry, names things by their parts." Then the greeting is in stiff military prose ("Halt! Identify yourself!"). The idle_barks veer into farmhand colloquialisms ("Reckon the weather'll turn soon."). The phrase_bank.oaths sound like a different person entirely. **The NPC has 5 voices stapled together** because each speechbank line was generated in isolation without the voice_anchor pinned. *(Defense: voice_anchor is THE load-bearing flavor hint for `wes_tool_npcs`; the phrase_bank pins itself into every line during speechbank generation; the dialogue agent uses both the narrative + the phrase_bank to keep voice coherent across LLM turns.)*

There is a fifth, quieter failure mode worth naming explicitly:

**(e) Disconnected from the WNS arc the NPC was BORN into.** An NPC was created because NL4 fired `<WES purpose="new-npc">` riding a thread about copper trade restructuring. The NPC's narrative should reference that thread. The narrative says: "A smith from a forest hamlet." The thread that spawned him is gone from his static. The world spent narrative weight earning this NPC's existence and the NPC is generic. This is the equivalent of Quest's failure mode (d) (disconnected from WNS) — and the cause is the same: `BundleToolSlice.parent_summaries` leak (see §4.4). One fix benefits both features.

### 1.4 What "good" actually looks like

The player walks up to Captain Vell. Sees the name "Captain Vell Sarn" and title "Copperlash Captain." Presses E.

> *"You're a long way from forge-light, stranger."*

The line knows where the player came from (the forge district to the south — implied by `forge-light`), references the moors locality without naming it directly, and uses a single contraction and pause-rhythm that fits the personality.voice. The player clicks through again.

> *"My brother knew this stone."*

Idle bark. References the narrative's "buried his brother on the moors-stone three winters ago" without restating it. The player feels the grief without being told.

> *"Three riders went out at dawn. Two came back."*

Local color. References the captain's faction (raiders) and reinforces the danger of the chunk.

The player asks for a quest. Vell says:

> *"There is a thing the line needs done. You'll do it."*

This is the speechbank quest_offer — terse, in voice, doesn't enumerate the quest yet (the scroll handles that). The player turns the quest in:

> *"It is done. The salt knows your name now."*

Speechbank quest_complete — same voice, lands the closure beat.

Three properties:
- **Voiced** — every line sounds like ONLY this NPC could have said it. The phrase_bank reads like a cultural fingerprint.
- **Anchored in place + past** — the moors, the salt, the brother, the line. None of these are restated; they're alluded to. The player accumulates a sense of who Vell is over six clicks instead of being told over one paragraph.
- **Causally legible** — Vell's hostility to hubtown isn't free-floating; the affinity_seeds say `guild:hubtown_militia: -85`. The player who has done hubtown quests recently gets cooler greetings.

---

## 2. Output artifact schema completeness audit

NPCs are TWO output artifacts: the static JSON (one-time, immutable, generated by `wes_tool_npcs`) and the speechbank refresh (regenerated periodically by `npc_dialogue_speechbank`). The dynamic registry rows are populated at NPC birth from `affinity_seeds` and then mutated by runtime (not LLM-authored at all — included here for completeness).

### 2.1 Static NPC v3 JSON (NPCDefinition — data/models/npcs.py)

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `npc_id` | str (snake_case) | `wes_tool_npcs` | Encodes locality + role + signature trait. `moors_copperlash_captain` beats `npc_007`. Must be unique against the registry. |
| `name` | str (Title Case) | `wes_tool_npcs` | Sounds like it belongs to the home_chunk's culture. "Captain Vell Sarn" not "Bob the Captain." |
| `title` | str | `wes_tool_npcs` | Evocative role descriptor. "Copperlash Captain" beats "Leader." May be empty for unornamented NPCs. |
| `narrative` | str (2-4 sentences) | `wes_tool_npcs` | **The load-bearing field.** Immutable past, anchored in home_chunk's culture. Must NEVER write present-tense intent. This is the source-of-truth for the NPC's voice across every downstream LLM use (speechbank refresh, dialogue agent, completion_dialogue in quests they give). |
| `personality.voice` | str (1-2 sentences) | `wes_tool_npcs` | Speech rhythm + register + signature mannerism. "Clipped, salt-dry, names things by their parts." Threaded into every speechbank generation as the voice_anchor. |
| `personality.knowledge_domains` | List[str] (2-5 from allow-list) | `wes_tool_npcs` | Drives gossip filter + dialogue topic plausibility. A smith doesn't gossip about runes. |
| `personality.reaction_modifiers` | Dict[EVENT_TYPE, {relationship_delta, emotion, optional match-filters}] | `wes_tool_npcs` | Drives NPCAgentSystem.on_world_event affinity updates. The bar: each modifier should make narrative sense for THIS NPC, not generic ("ENEMY_KILLED" with enemy_match=`copperlash_rider` is meaningful for Vell because his own line gets killed; the same modifier on a herbalist would be wrong). |
| `personality.gossip_interests` | List[str] (1-4 from allow-list) | `wes_tool_npcs` | Drives gossip propagation filter. Determines which WMS events become this NPC's `knowledge[]` rows. |
| `personality.base_emotional_state` | str (1 from allow-list) | `wes_tool_npcs` | Default emotion when no recent stimulus. Should match narrative (Vell = `wary`, a tutorial guide = `calm`). |
| `personality.dialogue_style.max_response_length` | int (80-300) | `wes_tool_npcs` | Length budget for LLM dialogue. Terse NPCs (Vell) get 120; verbose mentors get 250. |
| `personality.dialogue_style.formality` | str (1 from allow-list) | `wes_tool_npcs` | Register: informal / gentle / polite / formal / stern / archaic. Drives word choice in speechbank refresh. |
| `personality.dialogue_style.uses_jargon` | bool | `wes_tool_npcs` | Allows trade jargon (smithing terms, military cadence). Drives speechbank tone. |
| `locality.home_chunk` | str (chunkType) | `wes_tool_npcs` | **THE cultural anchor.** Must cross-ref a real chunk template or be co-emitted. Drives speechbank phrase_bank theme + narrative anchoring. |
| `faction.primary` | str (`namespace:name`) | `wes_tool_npcs` | One primary affiliation. Drives dialogue framing during faction conflicts. |
| `faction.belonging_tags[]` | List[{tag, significance, role, narrative_hooks}] | `wes_tool_npcs` | 1-4 affiliations. The combination is what makes the NPC's faction position TEXTURED rather than monolithic — Vell is a captain (role=captain in moors_raiders) AND a regional belonger (region:salt_moors) AND a family survivor (family:sarn_clan). Each significance + role + narrative_hooks adds a coordinate in faction-space. |
| `affinity_seeds{tag: int}` | Dict[str, int -100..100] | `wes_tool_npcs` | Starting opinions. **Reserved `_player` key sets the NPC's starting opinion of the player.** Must include primary faction (high positive) + at least one rival (negative) when narratively appropriate. Written into `npc_affinity` table at NPC birth. |
| `services.canTrade / canRepair / canTeach` | bool | `wes_tool_npcs` | Functional gate. Should align with role/personality (a captain teaches combat skills; a herbalist doesn't repair armor). |
| `services.teachableSkills[]` | List[skillId] | `wes_tool_npcs` | Cross-refs `skills-skills-1.JSON` or co-emitted skills. The skills should be plausible for the role. |
| `services.specialServices[]` | List[str] (free-form) | `wes_tool_npcs` | Common: identify_items, skill_training, enchanting, storage. |
| `unlockConditions.alwaysAvailable` | bool | `wes_tool_npcs` | Whether NPC is available from session start. Most generated NPCs default false. |
| `unlockConditions.characterLevel` | int (0-30) | `wes_tool_npcs` | Plausibility gate — a mid-game faction's NPCs shouldn't be talking to a level-1 player. |
| `unlockConditions.completedQuests[]` | List[questId] | `wes_tool_npcs` | Quest-chain gating. Cross-refs quests. |
| `speechbank.greeting[]` | List[str] (3-5 lines) | `wes_tool_npcs` (initial) / `npc_dialogue_speechbank` (refresh) | Cycled per conversation open. Must each sound like THIS NPC. First-impression weight is huge — the player reads one of these first. |
| `speechbank.farewell[]` | List[str] (2-3 lines) | same | Cycled on dialogue close. Should land the NPC's voice without overdoing it. |
| `speechbank.idle_barks[]` | List[str] (5-10 SHORT lines) | same | **The single biggest variety surface.** Ambient muttering, local color, the NPC's preoccupations. Must reference home_chunk culture + faction loyalties + occupational quirks. Each line is one sentence; the bank is the spine of "what is this NPC like to hang around." |
| `speechbank.quest_offer` | str (1 sentence) | same | The line right after the player accepts a quest. Per-NPC voice on quest-acceptance. The scroll handles the QUEST content; this line carries the GIVER. |
| `speechbank.quest_complete` | str (1 sentence) | same | The line at quest turn-in (when the quest's own completion_dialogue is empty — see Quests §2 priority chain). Per-NPC voice at quest closure. |
| `speechbank.phrase_bank` | Dict | same | **The cultural fingerprint, pinned into every LLM dialogue assembly.** `exclamations[]`, `oaths[]`, `endearments_friend[]`, `endearments_enemy[]`, `fillers[]`. Each sub-array 1-3 phrases. Vell says "By salt and copper!" — only Vell says it. The dialogue agent threads phrase_bank into every LLM call so voice stays coherent. |
| `quests[]` | List[questId] | `wes_tool_npcs` | Quests this NPC offers. Cross-refs quests; empty unless co-emitted. |
| `position{x,y,z}` | Position | `wes_tool_npcs` (initial) | Runtime spawn location. Should fit home_chunk. The planner/hub may override based on chunk geometry. |
| `sprite_color[r,g,b]` | List[int 0-255] | `wes_tool_npcs` | Marker color. Visual differentiation. |
| `interaction_radius` | float (2.0-5.0) | `wes_tool_npcs` | How close player must be. Standard 3.0; intimate NPCs can be 2.0, broadcast NPCs (criers) 5.0. |
| `tags[]` (top-level) | List[str] | `wes_tool_npcs` | WMS retrieval tags. Drive `social_npc.py` evaluator categorization. |
| `metadata.tags[]` | List[str] (3-6 from allow-list) | `wes_tool_npcs` | Descriptive tags — humanoid, trader, mentor, etc. NEW: prefix for new tags. |
| `dialogue_lines[]` (legacy) | List[str] | (NOT IMPLEMENTED for v3 — backward compat only) | Empty for v3 NPCs; only used as fallback when speechbank is absent on legacy NPCs. New NPCs leave empty. |

### 2.2 Dynamic context registry (populated at runtime, NOT LLM-authored)

These are NOT the LLM's responsibility for filling, BUT the static JSON must SEED them coherently. Included so the cross-feature opportunities are clear.

| Field | Type | Source | Notes |
|---|---|---|---|
| `npc_dynamic_state.current_emotion` | str | Initialized from `personality.base_emotional_state` | Mutates via NPCAgentSystem.on_world_event + dialogue. |
| `npc_dynamic_state.last_interaction_time` | float | runtime | — |
| `npc_dynamic_state.interaction_count` | int | runtime | — |
| `npc_dynamic_state.conversation_summary` | str (bounded) | runtime | Rolling 500-char snapshot. Read by dialogue agent for continuity. |
| `npc_dynamic_state.knowledge[]` | List[str] (bounded 30) | NPCAgentSystem.propagate_gossip | One-line WMS event summaries the NPC has heard. |
| `npc_dynamic_state.reputation_tags[]` | List[str] (bounded 10) | runtime | Tags the NPC associates with the player (heard player killed a copperlash → tag "moors-killer"). |
| `npc_dynamic_state.quest_state` | Dict[questId, str] | runtime | Per-quest tracking. |
| `npc_affinity[_player]` | int (-100..100) | Initialized from `affinity_seeds._player` | Mutates via reaction_modifiers + AffinityShift directives. |
| `npc_affinity[<faction_tag>]` | int (-100..100) | Initialized from `affinity_seeds[tag]` | Mutates via AffinityShift directives. |
| `npc_dialogue_log[]` | List[{turn, content, timestamp}] | runtime | Append-only log of dialogue exchanges. Bounded. |

### 2.3 Speechbank refresh artifact (`npc_dialogue_speechbank` output)

This endpoint OVERWRITES the static JSON's `speechbank` field (and only that field) at refresh time. The fixture shape (see §4.X for inputs) emits:

| Field | Type | Quality bar |
|---|---|---|
| `npc_id` | str | Must match an existing static NPC. |
| `speech_bank.greeting` | str (single, OR list[] — schema decision pending — see §2.4) | The new greeting after refresh. Voice MUST match narrative. |
| `speech_bank.quest_accept` | str | Maps to `speechbank.quest_offer` in static schema (naming drift between fixture and static — see §2.4 schema gap). |
| `speech_bank.quest_turnin` | str | Maps to `speechbank.quest_complete`. |
| `speech_bank.closing` | str | Maps to `speechbank.farewell`. |
| `mentions[]` | List[{entity, claim_type, significance}] | **Extraction surface.** Mention extractor reads this and feeds gossip propagation. The LLM names WMS-significant entities the NPC is now talking about. Per fixture description: "Mention extractor runs on this output." |

### 2.4 Schema completeness — what's MISSING

`[WES-SCHEMA-GAP]` markers:

- **`[WES-SCHEMA-GAP]` Speechbank refresh shape doesn't match static schema.** The `npc_dialogue_speechbank` fixture emits `speech_bank.greeting` (single string) and `speech_bank.quest_accept` / `quest_turnin` / `closing`. The static schema expects `speechbank.greeting` (LIST), `speechbank.quest_offer` (string), `speechbank.quest_complete` (string), `speechbank.farewell` (LIST), and additionally `speechbank.idle_barks` (LIST) which the fixture doesn't emit AT ALL. **The refresh endpoint can't produce a complete speechbank.** Fix: rewrite the speechbank fixture/prompt to match the static schema field-for-field, and add `idle_barks[]` to the output. Currently the refresh would either (a) destroy variety by replacing the list with a single line, or (b) be silently ignored at apply-time. Both are bad. This is the single most concrete schema bug in the NPC pipeline today.

- **`[WES-SCHEMA-GAP]` No prompt fragment file for `npc_dialogue_speechbank`.** Per registry.py:313, the fragment_path is `prompt_fragments.json` (placeholder — shared with WMS L2!) and the comment says "actual prompt is built inline in NPCMemoryManager." **There is no dedicated tag-indexed prompt fragment for the speechbank generator.** This is inconsistent with how every other LLM task in v4 is authored. Designer-tunable voice can't be tuned because the prompt is buried in code. Fix: extract to `prompt_fragments_npc_dialogue_speechbank.json` with tag-indexed fragments (see memory `feedback_wns_prompts_must_be_tag_indexed.md` for shape).

- **`[WES-SCHEMA-GAP]` No "publish API" exposing giver narrative + voice_anchor to Quests.** Per Agent 1 (Quests trace §4.4 + §6.4), the quest tool desperately needs `${giver_npc_narrative}` and `${giver_voice_anchor}` slots — the orchestrator should fetch these from the committed NPC registry post-orphan-check and splice them into the quest tool's input. This API does not exist. Fix: add `NPCDatabase.get_voice_excerpt(npc_id) -> {narrative, voice, primary_faction, phrase_bank_sample}` as a deterministic deep-link. **This is also load-bearing for completion_dialogue rendering at quest turn-in** — the giver's voice should be available everywhere a quest references that NPC.

- **`[WES-SCHEMA-GAP]` Speechbank cannot be tier-tagged or thread-tagged.** When the speechbank is refreshed, there is no metadata recording WHICH WNS thread state was the input. This makes "refresh on thread state change" detection impossible — the runtime can't tell whether a speechbank is stale. Fix: add `speechbank_meta: {generated_at, source_thread_ids[], source_layer, narrative_state_hash}` to the static schema. The runtime can then detect drift and trigger refresh.

- **`[WES-SCHEMA-GAP]` No NPC mortality / departure schema.** Per memory `quest_lifecycle_design.md`, quests have an archive at turn-in. NPCs do not have an equivalent: when an NPC dies (combat) or departs (narrative), there is no archived shape. This hits Quests too — `expiration.type: npc_death` voids the quest, but the NPC's "I existed and did these things" record vanishes. Fix: add an NPC archive table (sibling to the proposed quest archive) that holds the static NPC plus their final dynamic state, accessible by WNS for "remembered NPCs" continuity. Future LLM endpoint candidate: `npc_archive_summarizer` — chronicler-voice line about the departed NPC.

- **`[FRAGMENT-GAP]` Speechbank prompt doesn't have a slot for recent WNS narrative.** Per fixture: the canonical_user_prompt is "Current world state: Ashfall Moors restructuring; copper trade booming; bandit skirmishes increasing." This is a HAND-AUTHORED placeholder. The actual refresh path must pull this from the bundle, but the prompt has no `${narrative_context}` or `${recent_wms_summary}` template slots. Fix in §4.X.

- **`[FRAGMENT-GAP]` Static-JSON tool's reaction_modifiers shape allows orphan resource/enemy/quest refs that silently no-op.** Per tool prompt: "An NPC that references orphan resourceIds... silently no-ops at runtime." This is fine for graceful degrade BUT means a generated NPC could have reaction_modifiers that NEVER fire. Currently the orphan detector doesn't trace into the nested `resource_match` / `enemy_match` / `quest_match` arrays inside `reaction_modifiers`. Fix: extend orphan extractor to scan reaction_modifiers' nested arrays; flag refs to non-existent IDs.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a 1990s systematic generator with a name-table, role-table, faction-table, and a 50-line corpus produces for an NPC:

```json
{
  "npc_id": "npc_0017",
  "name": "Gareth Smith",
  "title": "Blacksmith",
  "narrative": "Gareth is the village blacksmith. He has been smithing for many years.",
  "personality": {
    "voice": "Friendly and helpful.",
    "knowledge_domains": ["smithing"],
    "reaction_modifiers": {},
    "gossip_interests": ["crafting"],
    "base_emotional_state": "neutral",
    "dialogue_style": {"max_response_length": 150, "formality": "polite", "uses_jargon": false}
  },
  "locality": {"home_chunk": "village"},
  "faction": {"primary": "guild:smiths", "belonging_tags": [{"tag": "guild:smiths", "significance": 0.8, "role": "smith", "narrative_hooks": null}]},
  "affinity_seeds": {"guild:smiths": 80, "_player": 0},
  "services": {"canTrade": true, "canRepair": true, "canTeach": false, "teachableSkills": [], "specialServices": ["repair"]},
  "unlockConditions": {"alwaysAvailable": true, "characterLevel": 0, "completedQuests": []},
  "speechbank": {
    "greeting": ["Hello, traveler.", "Welcome to my forge.", "How can I help you?"],
    "farewell": ["Goodbye.", "Safe travels."],
    "idle_barks": ["The forge is hot today.", "I make weapons and armor.", "Steel is hard to come by.", "Business is slow.", "I should sweep the floor."],
    "quest_offer": "I have a job for you.",
    "quest_complete": "Thank you. Here is your reward.",
    "phrase_bank": {"exclamations": ["Hah!"], "oaths": ["By the anvil."], "endearments_friend": ["friend"], "endearments_enemy": ["fool"], "fillers": ["hmm"]}
  },
  "quests": [],
  "position": {"x": 0.0, "y": 0.0, "z": 0.0},
  "sprite_color": [120, 80, 60],
  "interaction_radius": 3.0,
  "metadata": {"tags": ["smith", "trader", "humanoid"]}
}
```

This is fine. This is also exactly what we have to BEAT. The player has talked to this blacksmith in a hundred RPGs. He has no soul. The voice is interchangeable with the herbalist next door. The phrase_bank is single-phrase. The idle_barks are inventory descriptions. The narrative is two sentences of nothing.

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM contributes that the slot machine cannot:

1. **`npc_id`** — encodes home_chunk + role + signature. `tarmouth_ironrow_dwindling_smith` not `npc_0017`. Requires `address_hint` + signature trait from `prose_fragment`.
2. **`name`** — sounds like home_chunk's culture. `Gareth Smith` is fine but `Cassen Forgeknee` belongs to a culture where smiths get nicknamed by their work-injuries. Requires home_chunk's narrative + thematic_anchors.
3. **`narrative`** — 2-4 sentences of immutable past, anchored in concrete events. The bar is "this could not be another smith's narrative." Vell's narrative names the moors-stone burial. Gareth-Done-Right names the apprentice who ran to the copperdocks last winter and the day the old anvil cracked.
4. **`personality.voice`** — specific speech rhythm + a signature mannerism. "Friendly and helpful" is the slot machine; "Clipped, salt-dry, names things by their parts — the line, the stone, the brother who fell" is the bar.
5. **`personality.reaction_modifiers`** — every modifier must MAKE NARRATIVE SENSE for this NPC. Vell hates copperlash kills because they're his line; a tutorial mentor mourns enemy deaths because they're alive. The slot machine fills the field with generic deltas; the LLM picks events that REFLECT the narrative.
6. **`faction.belonging_tags[]`** — multiple coordinates with role + narrative_hooks. Vell's three tags (guild:moors_raiders captain + region:salt_moors regional + family:sarn_clan survivor) tell three different stories about him. Slot machines pick one tag.
7. **`affinity_seeds`** — narrative-driven enemies. Vell's `-85` toward hubtown isn't free-floating; it's the hubtown ambush that killed his brother. Slot machines pick uniform starts.
8. **`speechbank.greeting[]`** — every line a different angle on the NPC's voice. Vell's three greetings are clipped, terse, and each opens a different reading: assertive ("Speak quick"), wry ("You're a long way from forge-light"), commanding ("Stand where I can see you"). Slot machine: "Hello." three ways.
9. **`speechbank.idle_barks[]`** — 5-10 lines that build the NPC's world. Each references home_chunk culture, faction loyalty, or occupational lore. Vell's "Copper sings before it dulls" is a metaphor about decline. "My brother knew this stone" is a grief line. "Three riders went out at dawn. Two came back" is a stakes line. Slot machine: inventory descriptions.
10. **`speechbank.phrase_bank`** — the cultural fingerprint. Vell's `oaths: ["On the moors-stone, I swear it.", "By my brother's name."]` ARE the moors-stone + the brother. These two oaths anchor the NPC's voice in the LLM dialogue agent every single turn. Slot machine: "By the anvil."
11. **`speechbank.quest_offer / quest_complete`** — the giver's voice at the lifecycle hinge. Vell's "There is a thing the line needs done. You'll do it." is COMMANDING, doesn't enumerate the quest, ends with imperative. Slot machine: "I have a job for you."

The delta is: **specificity of voice grounded in narrative + cultural coherence threaded through phrase_bank + faction-position as texture not single-tag.**

---

## 4. Backward trace through the pipeline

### 4.1 Rung 0 — Player presses E (player-facing)

Consumes: the static NPC JSON's speechbank + name + title + sprite_color + position.
Emits: rendered dialogue panel with current line.
Risk: if the speechbank is empty/malformed, falls through to `dialogue_lines[]` legacy field, then to `"..."`. The fallthrough is deterministic safety (see `systems/npc_system.py:96-108`). The deterministic safety means a botched LLM generation does not break the game; the player just gets quiet NPCs.

### 4.2 Rung 1 — `npc_dialogue_speechbank` (cascade-time refresh, NOT live)

Inputs (per current fixture — placeholder shape, needs realignment):
- `npc_id` (which NPC's bank is being refreshed)
- Current world state prose (placeholder string — should be `${narrative_context}` from bundle)
- Local context (placeholder — should be locality-scoped WMS interpretations)

Output (per fixture):
- `{npc_id, speech_bank: {greeting, quest_accept, quest_turnin, closing}, mentions: [{entity, claim_type, significance}]}`

What's MISSING:

- `[WES-SCHEMA-GAP]` **Output shape mismatch with static schema.** See §2.4 — the fixture emits singleton strings for greeting/quest_accept/quest_turnin/closing, but the static schema expects lists for greeting/farewell/idle_barks. **The refresh endpoint is currently structurally incapable of producing the full speechbank.** Refactor target.

- `[FRAGMENT-GAP]` **The prompt doesn't carry the NPC's static narrative.** Critical. The refresh is generating dialogue WITHOUT seeing who the NPC is. The first thing the prompt should pin is the NPC's narrative + personality.voice + phrase_bank (existing). Without those, the LLM is writing in a void.

- `[FRAGMENT-GAP]` **No locality context.** The prompt should include the home_chunk's cultural narrative excerpt so refreshed lines stay anchored. (Vell talks salt and copper because his home_chunk is salt_moors.)

- `[FRAGMENT-GAP]` **No active NPC dynamic state context.** The refresh should know: has this NPC's affinity with the player shifted? Has the NPC's interaction_count gone above the threshold for familiarity? If yes, the greeting should shift register ("Stand where I can see you" → "You again — speak quick"). The current placeholder prompt doesn't have these slots.

- `[FRAGMENT-GAP]` **No WNS thread state at the NPC's locality.** This is the equivalent of Quest's BundleToolSlice leak: if the locality's NL2 narrative is "the salt moors are restructuring around copper trade," the NPC's refreshed idle_barks should reference that. Currently the prompt has hand-written world state placeholder; the real refresh needs `${focal_address_narrative}` + `${recent_locality_wms}`.

- `[FRAGMENT-GAP]` **No idle_barks slot in the output.** Mentioned in §2.4. The schema gap and the fragment gap are entwined — fix one, must fix the other.

The output side ALSO needs the `mentions[]` extractor to be wired. Per fixture description "Mention extractor runs on this output." This is the bridge that feeds the speechbank into WNS — when Vell starts saying "the copperdocks are taking my apprentices," that's a WMS event the chronicler should know about. **The mention extractor is the NPC pipeline's contribution back UP the stack.** It's how NPC dialogue becomes WMS-signal that future WNS firings can read. Without it, NPC dialogue is a dead-end.

### 4.3 Rung 2 — `wes_tool_npcs` (one ExecutorSpec → one NPC v3 JSON)

Inputs (per prompt_fragments_tool_npcs.json user_template):
- `spec_id`, `plan_step_id`, `item_intent` (hub-authored prose: "a captain of the Copperlash Rider line..."), `hard_constraints` (JSON: home_chunk REQUIRED + primary_faction + role + tier + is_questgiver), `flavor_hints` (JSON: name_hint, title_hint, prose_fragment, voice_anchor, thematic_anchors[]), `cross_ref_hints` (JSON: home_chunk + teachable_skill_ids + known_quest_ids + affinity_seed_factions).

What the tool does: takes the spec, emits a single NPC v3 JSON matching `data/models/npcs.py NPCDefinition`. Speechbank is generated at NPC birth in the same call — initial greeting/idle_barks/phrase_bank are author'd from voice_anchor + thematic_anchors.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same parent_summaries leak as Quests.** The tool's `BundleToolSlice` (via `slice_bundle_for_tool`) carries directive_text + address_hint + threads_in_focal_address + recent_registry_entries. **It DOES NOT carry parent_summaries or firing_layer_summary.** The narrative that SPAWNED this NPC (the NL4 fragment about copper trade restructuring) never reaches the tool. The NPC's static narrative gets written without the world-context that justified the NPC's existence. This is exactly the same fix as Quests — one patch in `slice_bundle_for_tool` benefits both features (and all 8 content tools).

- `[FRAGMENT-GAP]` **No home_chunk narrative excerpt.** The tool sees `hard_constraints.home_chunk: "dangerous_copper_moors"` — just the chunkType ID. To write a culturally-coherent voice + phrase_bank, the tool needs the chunk's narrative summary (its biome description, its cultural tokens, its tier). Fix: orchestrator should fetch chunk template's narrative + thematic_anchors and splice them as `${home_chunk_narrative}` + `${home_chunk_thematic_anchors}` into the user_template. (Post-orphan-detector: home_chunk is committed by the time tool fires.)

- `[FRAGMENT-GAP]` **No co-emitted faction sibling context.** If the same plan creates a Captain (Vell) and three Riders (his line), each is generated in isolation. The Riders should reference their captain narratively; the Captain should acknowledge his line. Currently each tool call is independent. Fix: when the same plan emits multiple NPCs with overlapping `primary_faction` or `belonging_tags`, splice the OTHER NPCs' name + role + narrative excerpts as `${faction_siblings_context}`.

- `[FRAGMENT-GAP]` **No referenced-quest context when NPC is a giver.** If `is_questgiver: true` and `known_quest_ids: [...]` are passed but the quests are co-emitted, the NPC doesn't see what the quests ARE narratively. Vell's narrative + idle_barks should be informed by the vendetta-hunt quest he gives. Fix: when quests are co-emitted, splice quest `item_intent` + `prose_fragment` as `${offered_quests_context}`.

- `[FRAGMENT-GAP]` **No player-progression hint.** Unlike Quests where pregen takes player_level, NPC creation is player-agnostic. **Probably correct** — the NPC's narrative is immutable and player-independent; the dynamic context registry is where player-specific state lives. Don't break this.

### 4.4 Rung 3 — `wes_hub_npcs` (one plan step → batch of NPC specs)

Inputs (per prompt_fragments_hub_npcs.json user_template):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: decomposes "a captain and three riders for the moors raiders" into 4 ExecutorSpecs, each fully-loaded with constraints/hints/cross-refs for the tool.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same parent_summaries leak.** Fix at hub propagates to tool.

- `[FRAGMENT-GAP]` **No locality NPC roster awareness.** When the hub is told "three riders," it should see the EXISTING NPCs in the focal address so it can position the riders' narratives against them (rivals, subordinates, kin). Currently the recent_registry_entries carries recent NPC entries but the hub prompt's diversity prose ("AVOID duplication: distinguish specs by faction, locality, role, voice register, or generation") doesn't say to ALIGN them either. The result: hub generates parallel narratives instead of interconnected ones. Fix: `${locality_npc_summary}` in user_template = brief role + faction + signature trait list for all NPCs in the focal address, with instruction "weave the new NPCs into this existing population."

- `[FRAGMENT-GAP]` **No faction-state context.** If the locality has a tense faction balance (`guild:moors_raiders` at -0.3 standing across the district), the hub should bias the generated NPCs toward acknowledging that tension — not by writing it explicitly but by setting affinity_seeds + reaction_modifiers that reflect it. Currently the hub has no such signal. Fix: `${faction_state_summary}` in user_template = brief tag → standing pairs for factions in scope. Reads from FactionSystem.

- `[FRAGMENT-GAP]` **Cross-tool co-emission awareness (same as Quests §4.5).** When the plan has `[chunks, npcs, quests]` with NPCs depending on chunks AND giving quests, the hub gets `step_slots` with the names but doesn't see the co-emitted chunk's narrative or the co-emitted quest's intent. Fix: dispatcher attaches co-emitted artifact summaries to hub input.

### 4.5 Rung 4 — `wes_execution_planner` (one bundle → one plan DAG)

Same role as in the Quest trace. For NPCs the load-bearing planner decisions are:

- **WHEN to fire an npcs step.** Per the planner's scope-by-firing-tier rules: tier 1-2 → no NPCs; tier 3 → 1 NPC allowed; tier 4+ → full population sets. This is the load-bearing prose the designer must tune. Too stingy and NPCs rarely generate (the world stays static); too loose and tier-1 events spawn full faction casts (the world gets crowded with low-relevance NPCs).
- **WHO to fire (giver vs. populator).** The planner should distinguish "this NPC is a quest giver" (needs `is_questgiver: true` + `known_quest_ids` co-emitted) from "this NPC populates the locality" (no quest hooks; pure flavor). Currently the planner's hub-step intent prose is freeform.
- **WHERE — home_chunk decision.** The planner picks home_chunk based on bundle's `delta.address` + cross-references with existing chunks. If the firing is at locality:salt_moors, the new NPC's home_chunk should be a chunkType within salt_moors. Co-emission of chunks if none exist.

What's MISSING:

- `[FRAGMENT-GAP]` **No npc-specific firing guidance.** The planner's prompt covers all 8 content tools generically. NPCs need their own guidance: "an npc step should specify the role + faction + is_questgiver intent up front; if the NPC is a giver, co-emit the quests they give; if the home_chunk doesn't exist, co-emit it; prefer to expand existing factions rather than inventing new ones." This is designer-tunable per-purpose prose.

### 4.6 Rung 5 — WNS emits `<WES purpose="new-npc">`

Per narrative_fragments_nl3.json _wes_tool, NL3 (district) lists `new-npc: a figure whose reach crosses locality lines`. NL2 (locality) is the more common NPC firing layer (a locality is where most NPCs live).

What's MISSING:

- `[WNS-GAP]` **NPC-specific firing guidance.** When should the weaver fire `new-npc`? Trigger conditions:
  - A WNS thread has gained a recurring named-character mention that doesn't resolve to an existing NPC (the weaver wrote "the smith at Ironrow" three fragments in a row and no NPC exists).
  - A faction's standing has shifted enough that the locality needs a NEW face representing the new balance (the moors raiders just lost a captain; the line needs new leadership).
  - A `<WES purpose="new-quest">` was just fired but no giver exists; the planner needs an NPC to attach the quest to (see Quest trace §9.5 — quest_giver_curator).
  - The locality population has gone quiet (no NPC-mention WMS events for N days); time for new arrivals/migrants.
  Currently the prose says "a figure whose reach crosses locality lines" — vague. Designer task: tune `_wes_tool` body per layer to give clearer firing guidance for new-npc specifically.

- `[WNS-GAP]` **Directive body shape.** The `<WES purpose="new-npc">body</WES>` body is freeform. Bad version: "Generate an NPC." Good version: "A blacksmith in Ironrow whose apprentices have been leaving for the copperdocks — bitter, faction-loyal, knows the district's hidden ore veins." The latter NAMES role + faction + locality + signature grievance + knowledge_domain. Fragment should instruct weaver: name the role, name the faction belonging, name the home_chunk, name a signature trait or grievance that anchors the narrative.

- `[FRAGMENT-GAP]` **AffinityShift integration.** Per memory `wns_affinity_modifier_tool.md`, WNS emits `<AffinityShift>` directives. When that directive applies to a specific NPC (`<Target>npc:gareth_smith</Target>`), the resolver currently writes to faction state. **It should ALSO mark the NPC's speechbank for refresh** because the NPC's standing has shifted. Without this link, an NPC who has just acquired hostile affinity toward the player keeps greeting them as "friend." The AffinityShift→speechbank-stale signal is missing.

### 4.7 Rung 6 — WNS reads WMS L2 interpretations (incl. `social_npc.py`)

The NL weavers consume `${wms_context}` — rendered WMS L2 interpretations at the firing address. For NPC-relevant signals:

- `social_npc.py` — NPC interactions, dialogue events, NPCs seen near player
- `faction_reputation.py` — faction standing deltas
- Combat kill evaluators — knowing which NPCs/factions have been antagonized
- `gathering_regional.py` — local resource pressure affecting NPC professions
- `social_quests.py` — quest activity at the locality

All solid — these are the existing 33 evaluators, designer-reviewed. NPC-relevant signal has a path through every one of them.

### 4.8 Rung 7 — `social_npc.py` L2 evaluator

This is the WMS-side evaluator that interprets raw NPC-interaction events into L2 narrative-ready rows. For the NPC pipeline this is the evaluator whose output most directly feeds back into NPC generation (when fragment retrieves "what's happening with NPCs in this locality," it reads social_npc's output).

Solid. No gaps here for NPC use cases.

---

## 5. Per-field provenance table

For every field the LLM authors in either `wes_tool_npcs` (static) or `npc_dialogue_speechbank` (refresh). Where the upstream signal comes from.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `npc_id` | Tool prompt + `flavor_hints.name_hint` + uniqueness check | Hub composes name_hint from `step.intent` + `address_hint`. Tool snake_cases it. | Yes | — |
| `name` | Tool prompt + `flavor_hints.name_hint` | Hub picks from `step.intent` + culture hints | Yes | — |
| `title` | Tool prompt + `flavor_hints.title_hint` | Hub picks from `step.intent` | Yes | — |
| `narrative` | Tool prompt | Hub's `prose_fragment` + `voice_anchor` + `thematic_anchors` + the home_chunk's narrative excerpt **(missing — see below)** | Partial | `[FRAGMENT-GAP]` — add `${home_chunk_narrative}` + `${parent_narrative}` slots (the latter blocked on BundleToolSlice fix) |
| `personality.voice` | Tool prompt + `flavor_hints.voice_anchor` | Hub provides voice_anchor | Yes | — |
| `personality.knowledge_domains[]` | Tool prompt | Inferred from role + faction + home_chunk + allow-list | Yes | — |
| `personality.reaction_modifiers` | Tool prompt | Inferred from narrative + faction (e.g., Vell hates copperlash kills) | Yes | — |
| `personality.gossip_interests[]` | Tool prompt | Inferred from role + knowledge_domains | Yes | — |
| `personality.base_emotional_state` | Tool prompt | Inferred from narrative tone + voice | Yes | — |
| `personality.dialogue_style.*` | Tool prompt | Inferred from voice + formality conventions | Yes | — |
| `locality.home_chunk` | Hub `hard_constraints.home_chunk` | Planner picks from bundle's `delta.address` + existing chunks; co-emits chunk if none exists | Yes | — |
| `faction.primary` | Hub `hard_constraints.primary_faction` | Planner picks from `step.slots.primary_faction` + locality's faction state | Yes | — |
| `faction.belonging_tags[]` | Tool prompt | Tool elaborates from primary + thematic_anchors + narrative; emergent (no registry validation) | Yes | — |
| `affinity_seeds{tag:int}` | Tool prompt | Tool picks from narrative + faction relationships; reserved `_player` from initial player-NPC stance hint | Partial — tool prompt mentions reserved `_player` and includes rival negative, but NO upstream signal for what the player's standing with this NPC should START AT | `[FRAGMENT-GAP]` — when WNS fires `new-npc` from a thread with strong `agency:player` tag, the directive_text should hint at the NPC's pre-existing opinion of the player ("a smith who has heard tell of a moor-killer wandering the road"). |
| `services.*` | Tool prompt | Inferred from role | Yes | — |
| `services.teachableSkills[]` | Tool prompt + `cross_ref_hints.teachable_skill_ids` | Planner co-emits skills or pulls from existing registry; orphan detector enforces | Yes (when wired) | — |
| `unlockConditions.*` | Tool prompt | Tool's own picks based on tier + narrative gating | Yes | — |
| `speechbank.greeting[]` (initial) | Tool prompt | Tool generates from voice_anchor + phrase_bank + narrative | Yes | — |
| `speechbank.greeting[]` (refresh) | `npc_dialogue_speechbank` | Refresh prompt — but the prompt is currently a placeholder; missing slots for static narrative, focal address WNS state, dynamic state. **Output is a single string, not a list.** | Partial | `[WES-SCHEMA-GAP]` + `[FRAGMENT-GAP]` — see §2.4 + §4.2 |
| `speechbank.farewell[]` (initial / refresh) | same | same | same | same |
| `speechbank.idle_barks[]` (initial) | Tool prompt | Tool generates 5-10 from voice + thematic_anchors + narrative + faction loyalties | Yes | — |
| `speechbank.idle_barks[]` (refresh) | `npc_dialogue_speechbank` | **Refresh fixture doesn't emit this field AT ALL.** | NO | `[WES-SCHEMA-GAP]` (severe — output schema mismatch) |
| `speechbank.quest_offer` | Tool prompt (initial) / refresh | Tool generates 1-sentence in voice; refresh regenerates with current state | Partial (initial yes; refresh has shape but no narrative context) | `[FRAGMENT-GAP]` — refresh needs same context fixes |
| `speechbank.quest_complete` | Tool prompt (initial) / refresh | same | same | same |
| `speechbank.phrase_bank` | Tool prompt | Tool generates from voice_anchor + thematic_anchors + home_chunk culture | Yes | — |
| `quests[]` | Hub `cross_ref_hints.known_quest_ids` | Planner co-emits quests if NPC is giver; orphan detector enforces | Yes (when wired) | — |
| `position{x,y,z}` | Tool prompt + chunk geometry | Tool picks plausible coords; chunk-spawning runtime may override | Yes | — |
| `sprite_color[r,g,b]` | Tool prompt | Tool picks from faction or role color conventions | Yes | — |
| `interaction_radius` | Tool prompt | Tool picks based on role broadcast vs intimate | Yes | — |
| `tags[]` (top-level) | Tool prompt | Tool picks from allow-list reflecting role + faction + locality | Yes | — |
| `metadata.tags[]` | Tool prompt | Subset of tags from descriptive allow-list | Yes | — |
| `mentions[]` (refresh output) | `npc_dialogue_speechbank` | LLM names WMS-significant entities in refreshed dialogue | Yes | — (but the mention extractor needs to be plumbed back to WMS — see §6.4) |

### 5.1 WMS-GAP walk — the places I was tempted

Two pieces of context where `[WMS-GAP]` was tempting. Walked the 9 rungs for both.

#### 5.1.1 "What does this NPC know about the player BEFORE first interaction?"

Use case: an NPC is being created in a locality the player has been operating in. The NPC's `affinity_seeds._player` should reflect what the locality's NPCs would have heard about the player ALREADY — gossip propagation in reverse. If the player has been killing copperlash riders, the moors raider NPCs being created now should start at hostile, not neutral.

The 9 rungs:
1. **Direct query** — is there a WMS event "player has reputation in salt_moors"? No single event of that exact shape. **Fail.**
2. **Adjacent events** — `social_npc.py` evaluator output for the focal address: how many NPC interactions has the player had here? `combat_kills_regional_*` for kills at the locality? `social_quests.py` for completed quests here? **All exist as L2 rows.** Querying `event_store.count_filtered(address='locality:salt_moors', event_types=['enemy_killed', 'npc_interaction', 'quest_completed'])` returns them.
3. **Negative patterns** — has the player avoided this locality? Absence-of-interaction is a signal too. `entity_registry` + activity tracker.
4. **Aggregation** — `daily_ledger` tracks NPC-interaction counts per day at locality scope. Combine over a window.
5. **Trajectory** — `social_npc.py` carries severity bands by recency. Same evaluator answers "how has player-NPC interaction at this locality trended recently."
6. **Cross-layer climb** — the NL3 district narrative carries the INTERPRETATION ("the moor folk no longer trust strangers"). This is the chronicler's voice already filtered. Available in the bundle's parent_summaries — IF the leak is fixed.
7. **Cross-entity composition** — combining "many kills at this locality" + "many faction-X-aligned-NPC kills" + "few faction-X-aligned-NPC dialogue interactions" = "the player is acting hostile toward faction X here." All three exist; the combination is a query.
8. **Stat / ledger lookup** — `FactionSystem.get_affinity('player', '<faction>')` returns the deterministic numeric standing. **This is the cleanest single signal.** Pull at NPC birth, seed affinity_seeds._player to a value derived from this.
9. **Trigger history** — has `<AffinityShift>` fired on the faction recently? `affinity_resolver` writes time-indexed.

**Verdict**: NOT a WMS gap. The signal is available through (8) faction affinity + (2-5) WMS aggregation. The gap is at the **fragment input layer** — the NPC tool prompt doesn't have a slot for "what's the player's standing with this NPC's primary_faction." Marker: `[FRAGMENT-GAP]` on the NPC tool prompt input set. Solution: orchestrator fetches `FactionSystem.get_affinity('player', primary_faction)` at tool-call time and splices as `${player_standing_with_primary_faction}` into user_template.

#### 5.1.2 "What's this NPC's place in the local social network?"

Use case: when generating a captain + 3 riders in the same plan, the captain's narrative should mention his line; the riders' narratives should hint at the captain. More broadly: an NPC being added to a locality with 5 existing NPCs should have plausible relational hooks (rival, kin, comrade) to one or two of them.

The 9 rungs:
1. **Direct query** — is there a WMS event "NPC X is rival of NPC Y"? No event of this shape exists in the WMS — relationships are SCHEMA in faction.belonging_tags + affinity_seeds, not events. **Fail.**
2. **Adjacent events** — events involving both NPCs (`social_npc.py` rows where both appear)? **Available.** If NPC X and NPC Y have appeared together in dialogue events the player witnessed, there's a row.
3. **Negative patterns** — NPCs in the same locality who have NEVER appeared together? That's a relational gap-signal. Comparing entity co-occurrences in `social_npc.py` rows.
4. **Aggregation** — counts of co-mentions per NPC pair in the same locality.
5. **Trajectory** — has co-mention frequency increased/decreased (NPCs growing closer or apart)?
6. **Cross-layer climb** — the NL2 narrative for the locality NAMES the social structure ("Vell commands the line; Edda is his second"). Available as `firing_layer_summary` if the leak is fixed.
7. **Cross-entity composition** — pairs of NPCs sharing faction belonging_tags = candidates for relational hooks. Querying `entity_registry` for NPCs in the locality and intersecting their `belonging_tags`.
8. **Stat / ledger lookup** — FactionSystem stores NPC affinity toward FACTIONS but not toward other NPCs directly. There's a gap here — we know Vell's standing with `guild:moors_raiders` (95) but not with the specific rider NPCs in that faction. **However**, this is reasonable: NPC-to-NPC relationships are EMERGENT from shared faction + locality + narrative co-mention; we don't need a per-pair affinity table.
9. **Trigger history** — `<AffinityShift>` directives targeting individual NPCs (per the AffinityShift spec) feed faction state per-NPC, not per-NPC-pair.

**Verdict**: NOT a WMS gap, but adjacent to one. The relational structure of a locality's NPCs is RECONSTRUCTABLE from (2) co-mention events + (7) shared faction tags + (6) the NL2 narrative summary. The actual gap is: **`wes_hub_npcs` doesn't get fed this reconstructed locality-NPC-roster context.** Marker: `[FRAGMENT-GAP]` on the hub input layer (covered in §4.4). Solution: orchestrator builds a `locality_npc_summary` from EntityRegistry + FactionSystem at hub-call time.

**Zero `[WMS-GAP]` markers in this trace.** WMS provides the substrate. The gaps are all at the WNS→WES boundary (BundleToolSlice leak) and at the prompt input layer (variables not threaded through). Same shape as Quests. Good news; the upstream sacred work is solid.

---

## 6. Cross-references with other features (personal shopper)

### 6.1 Heavy shared infrastructure (use as-is)

Same as Quests §6.1 — every content-generating feature shares:
- WNS NL2-NL7 narrative weavers
- WES Execution Planner
- WMS L2 evaluators + L2-L7 chronicle
- Tag system + tag-registry
- `BundleToolSlice` (and the parent_summaries leak)
- Orphan detector

### 6.2 NPC-specific shared with adjacent features

NPCs are the **HUB feature** — the most relationally connected of the 8 content tools. Almost every other content tool needs something from NPCs OR provides something to NPCs.

**To Quests (cf. Agent 1's request in 01-quests.md §6.4):**
- **Publish API: `NPCDatabase.get_voice_excerpt(npc_id) -> {narrative, voice, primary_faction, phrase_bank_sample, base_emotional_state}`.** Quests trace asked for this explicitly. Deterministic spice from the committed NPC registry. **The orchestrator should call this post-orphan-check for any quest spec that references a `given_by` NPC, and splice the result into the quest tool's user_template as `${giver_voice_anchor}` + `${giver_personality_excerpt}`.** This fixes Quest's failure mode where `description_full.narrative` and `completion_dialogue` are written in a voice the tool doesn't have data for. **Highest-leverage cross-feature API in this trace.**
- **Accept `cross_ref_hints.gives_quest_ids[]`** — when a quest is co-emitted with the giver NPC in the same plan, splice the quest intents into the NPC hub's input so the NPC's narrative + idle_barks can reference the quest themes.

**From Quests:**
- **`NPCDatabase.get_active_quests(npc_id)`** — Quest's runtime should be able to ask "what quests does this NPC currently offer?" so the NPC's interaction surface can route correctly (quest_offer vs idle_bark). Already implemented via `NPC.get_available_quests(quest_manager)` in npc_system.py.
- **Quest completion signals back to NPC affinity** — when a quest from a giver NPC is completed, the giver's affinity toward the player should shift. Currently the runtime's `Quest.complete_quest()` doesn't fire a faction-affinity event explicitly; the AffinityShift directive is more about WNS-level shifts than per-NPC-per-quest. **The quest's runtime should call `FactionSystem.adjust_npc_affinity_toward_player(giver_id, +affinity_delta)` on turn-in.** Quest tool can emit a hint (`metadata.affinity_reward_with_giver: int`) for the pregen to read.

**To Chunks:**
- **NPCs are the most chunk-bound content type.** `locality.home_chunk` is mandatory. NPCs reference chunk culture HEAVILY (phrase_bank thematic anchors come from chunk narrative). Chunk's tool should output a `narrative_anchors[]` field — short list of cultural tokens the chunk represents — for NPCs (and other content) to consume. (E.g., dangerous_copper_moors → `["salt", "copper", "moors-stone", "fog", "rust-veined cliffs"]`.) NPC hub then splices `${home_chunk_thematic_anchors}` into tool prompt.

**From Chunks:**
- Chunk's runtime should expose `ChunkDatabase.get_thematic_anchors(chunk_type)` for the NPC orchestrator. Same pattern as the NPC→Quest publish API.

**To Skills:**
- NPCs with `canTeach: true` reference skillIds in `teachableSkills[]`. Cross-ref discipline.

**From Skills:**
- When a skill is granted as a quest reward AND the quest is given by an NPC, the NPC should be that skill's narrative origin. Skill's narrative ("learned from Captain Vell on the moors-stone") should accept `cross_ref_hints.taught_by_npc_id`. The Quests trace (§6.4) already asks Skills for this; NPCs reinforce it.

**To/From Materials:**
- NPCs trade materials (`services.canTrade`). Material's spawned-in-context narrative could reference NPC traders ("sought by the wanderers' guild"). Less load-bearing than the other directions but cross-ref opportunity.

**To/From Hostiles:**
- NPCs HATE hostiles (`reaction_modifiers.ENEMY_KILLED` with enemy_match[]). This drives a lot of affinity shifts. Cross-ref discipline on enemy_match[]. Hostile's narrative could reference NPC factions ("the copperlash riders are hunted by the hubtown militia") — Hostile's tool accepts `cross_ref_hints.hunted_by_faction[]` or `hunted_by_npc[]`.

**To/From Titles:**
- Some titles are granted by NPCs (e.g., "Vell's Sworn-Friend"). Title's narrative accepts `cross_ref_hints.granted_by_npc_id`. Same pattern as Skills.

**To/From WNS:**
- **Mention extractor (speechbank → WMS).** When `npc_dialogue_speechbank` emits `mentions[]`, the WMS-side extractor writes those mentions as L1 events that feed L2 evaluators (`social_npc.py` etc.). This is the NPC pipeline's contribution back UP the stack — NPCs are not just consumers of world narrative, they are PRODUCERS. **Without the mention extractor, NPC dialogue is a dead-end — words land on the player and vanish.** Confirm this extractor is wired before launch.
- **AffinityShift on NPC target.** When WNS emits `<AffinityShift><Target>npc:X</Target>`, the resolver should ALSO mark X's speechbank for refresh. Without this link, an NPC whose standing has just shifted keeps using the old greetings.

**To Planner/Supervisor:**
- The planner needs to know "are there enough NPCs at this locality already" before deciding to fire `new-npc`. Expose `EntityRegistry.count_npcs_at_address(address)`.

### 6.3 Where NPCs diverge (flavor not shareable)

- **The dialogue agent layer (NPCAgentSystem.generate_dialogue).** Only NPCs have a "live LLM-powered open dialogue" surface. Quests don't. Materials don't. This is NPC-architectural and shouldn't be force-shared. The personality.voice + phrase_bank + dynamic state are NPC-only contexts.
- **The static/dynamic split.** NPCs have a unique dual-store pattern: static JSON (immutable) + dynamic SQLite (mutable). Other content types are mostly mutable-or-not (quests have the active/archive split which is RELATED but different). Don't force the same pattern on Materials or Hostiles.
- **Per-NPC reaction_modifiers.** Other content types react to events through tags, not per-instance modifiers. NPCs reacting individually is unique.
- **Phrase_bank as cultural fingerprint.** This is unique to NPCs because they're the ONLY content type that the player has open-ended verbal exchange with. Quest dialogue is one-shot; NPC dialogue is ongoing. Phrase_bank exists to keep voice coherent across many turns.

### 6.4 Recommendations to other agents

- **Quests agent**: Use `NPCDatabase.get_voice_excerpt(npc_id)` (proposed below) in your tool input for any spec where `given_by` is set. Stop writing completion_dialogue in a voice you don't have data for.
- **Chunks agent**: Expose `narrative_anchors[]` in your tool output. The NPC pipeline depends on it for cultural coherence.
- **Skills agent**: Accept `cross_ref_hints.taught_by_npc_id` and reflect the NPC's voice in the skill's narrative.
- **Titles agent**: Accept `cross_ref_hints.granted_by_npc_id`.
- **Hostiles agent**: Accept `cross_ref_hints.hunted_by_npc_id` or `hunted_by_faction[]`. The narrative loop between NPCs and their hostiles is one of the strongest worldbuilding levers.
- **WNS / Planner+Supervisor agent**: **The single most impactful intervention you can make for NPC quality is, same as Quests, closing the BundleToolSlice parent_summaries leak.** Additionally: tune the `_wes_tool` body in NL2 / NL3 fragment files to give clearer firing guidance for `new-npc` (see §4.6 trigger conditions). Also: wire the `<AffinityShift><Target>npc:X</Target>` resolver to mark NPC X's speechbank stale (so refresh fires on next cascade).
- **WES agent**: Build the speechbank refresh fragment (`prompt_fragments_npc_dialogue_speechbank.json`) with tag-indexed shape matching the WNS pattern. Make sure its output shape MATCHES the static schema (lists, not strings; include idle_barks).

---

## 7. Storage / timing design

### 7.1 Static JSON commit

`wes_tool_npcs` output commits to:
- `ContentRegistry.reg_npcs` — the in-runtime registry table
- `progression/npcs-generated-<timestamp>.JSON` — disk persistence (sacred-file untouched per CLAUDE.md philosophy)

Once committed, the static fields NEVER change. This is the load-bearing rule from memory `npc_schema_overhaul_v3.md`.

### 7.2 Dynamic context registry initialization at NPC birth

At commit time, the orchestrator runs an initialization pass:
- Iterate `affinity_seeds` → write rows to `npc_affinity[tag]` table (including reserved `_player`).
- Initialize `npc_dynamic_state` row: `current_emotion = personality.base_emotional_state`, `interaction_count = 0`, `last_interaction_time = -1`, `conversation_summary = ""`, `knowledge = []`, `reputation_tags = []`, `quest_state = {}`.
- This is deterministic, no LLM.

### 7.3 Speechbank refresh cadence

The most subtle timing question in the NPC pipeline. Three possible triggers:

- **WNS thread state change at the NPC's locality.** When the NL2 thread the NPC is participating in moves stage (rising_action → complication), the speechbank may be stale. The speechbank_meta.source_thread_ids[] field (proposed in §2.4) lets the runtime detect drift.
- **AffinityShift directive targeting the NPC.** When `<AffinityShift><Target>npc:X</Target>` fires, mark speechbank stale.
- **Time-based refresh cooldown.** Every N game days (configurable, designer-tunable; suggest 7 game days as a starting point), every NPC's speechbank is eligible for refresh if other conditions are met.

**Refresh execution**: Fires on WNS cascade (same budget as static generation). The refresh's BundleToolSlice carries the NPC's locality + current focal-address narrative + the NPC's dynamic state snapshot (knowledge[], reputation_tags[], current_emotion). The LLM outputs a full speechbank dict that REPLACES the existing speechbank wholesale (NOT a patch — easier semantics, single-shot).

**Stale-but-not-yet-refreshed handling**: while waiting for the next cascade, the NPC keeps using the existing speechbank. This is acceptable because:
- The static narrative voice doesn't change (immutable past).
- The idle_barks were written in past-tense, so they don't claim CURRENT facts.
- The dynamic state (affinity, emotion) still updates synchronously, so faction-conflict gating still works.

What's lost: the idle_barks won't NAME the new locality events until refresh. Trade-off acceptable.

### 7.4 NPC mortality / departure

Per §2.4, NPC mortality has no schema. When an NPC dies:
- Static JSON should be ARCHIVED (not deleted) so future WNS firings can reference "the late Captain Vell."
- Dynamic context rows should be flagged inactive but retained.
- Quests requiring this NPC void (already handled by `expiration.type: npc_death`).
- The locality's NPC count drops — planner sees the vacuum on next cascade and may spawn a successor.

Future LLM endpoint candidate: `npc_archive_summarizer` — chronicler-voice line about the departed NPC (see §9). Same shape as the proposed quest archive summarizer.

### 7.5 NPC mobility

The static schema has `position{x,y,z}` but most NPCs are static (per existing npcs-3.JSON examples). For wandering NPCs (the trader has `isStatic: false` in v2), the dynamic context registry should carry `current_position` separately from the static spawn position. Currently this is handled informally — designer task to formalize.

---

## 8. Diversity & creativity design

The diversity dials for NPCs, ranked by impact:

### 8.1 Voice variance across the locality

Each NPC's `personality.voice` should be DIFFERENT from every other NPC in the same locality. The hub prompt says "AVOID duplication" but in voice terms specifically. A locality with two stern-formal-military-voice NPCs has wasted a slot.
- Implementation: hub's `recent_registry_entries` should expose per-NPC voice + formality + base_emotional_state. Hub prompt instruction: "vary voice across the batch."

### 8.2 Faction position texture

A locality with three NPCs all at significance 0.9 with the same primary faction = monolithic. Vary along:
- Significance (deep-loyal vs loose-affiliate vs estranged)
- Role (captain vs rank-and-file vs outsider)
- Belonging_tags multiplicity (single-tag vs multi-tag)
- Affinity_seeds tone (faction-pure vs cross-faction)

A locality of moors raiders with one captain (sig 0.95 + role captain + family:sarn_clan), one veteran (sig 0.7 + role scout + veteran:nameless_war), and one defector (sig 0.3 + outcast:hubtown_militia + interest:rare_materials) has 3x the social texture of three identical-faction NPCs.

### 8.3 Idle_barks variety surface

Each idle_bark should illuminate a DIFFERENT facet of the NPC. The "5-10 lines" budget should be distributed:
- 1-2 about home_chunk culture/landscape
- 1-2 about faction loyalty/grievance
- 1-2 about occupation/role
- 1-2 about personal history / signature trait
- 1-2 about current locality conditions (these are the ones the refresh can update)

This distribution should be PROSE GUIDANCE in the tool prompt, not enforced.

### 8.4 Phrase_bank cultural variance

Different cultures → different phrase_bank lexicons. The moors phrase_bank says "salt and copper"; a forest village says "root and ring"; a desert outpost says "sand and shadow." Ensure home_chunk's thematic_anchors are DIFFERENT across chunks so phrase_banks aren't repetitive.

### 8.5 Affinity_seeds rival diversity

`tool prompt: "MUST include affinity values for at least one rival faction (negative) when narratively appropriate"` — but encourage VARIETY of rivals across the NPC population. A locality where every NPC hates `guild:hubtown_militia` is one-note. Mix rivals: one NPC hates hubtown, one hates a cult, one hates a rival craft guild.

### 8.6 Reaction_modifier creativity

The allow-list has 9 EVENT_TYPES. Encourage NPCs to react to UNUSUAL events. Most NPCs will react to ENEMY_KILLED and LEVEL_UP; have some react to ITEM_CRAFTED with specific discipline_match (an alchemist reacting to herbcraft), some to CHUNK_ENTERED (a recluse who only emerges when the player visits a specific chunk), some to RESOURCE_GATHERED with prefix wildcards (a smith caring about all `_ore` materials).

### 8.7 Emergent proper nouns

Same as Quests §8.8 — the `emergent_entity` tag in WNS narrative fragments allows the LLM to coin proper nouns. NPCs inherit these. Vell's narrative naming "the moors-stone" is an emergent proper noun. The first NPC who names a thing creates it.

### 8.8 Population balance

The planner's scope-by-firing-tier decides quantity. Designer-tunable trade-off:
- Too few NPCs per locality → world feels empty
- Too many → player can't remember who's who, dialogue surface gets diluted

Suggested baseline: 3-5 NPCs per active locality, 1-2 per outpost, scaling up by population center size.

### 8.9 Mood / tone from WNS thread

The firing layer's `tone:*` tag should propagate into the NPC. An NPC born from a `tone:tragic` thread should NOT have `base_emotional_state: cheerful`. The tone should bias toward `melancholy / wary / fervent`. Currently the hub doesn't pass tone explicitly — fix: hub propagates `${thread_tone}` into tool flavor_hints.

---

## 9. Speculative future endpoints

### 9.1 `wes_npc_modifier` — post-creation drift

Same pattern as Quest's modifier (Quests §9.1). When an NPC's narrative thread has moved significantly since the NPC was created, regenerate parts of the NPC's narrative (NOT the immutable past — that stays) but add a `narrative_addendum` field that the dialogue agent reads. Example: Vell was created in `thread:vendetta_against_hubtown`; six months of gameplay later the thread has resolved (vendetta succeeded). His narrative_addendum says "He has not ridden out in two seasons; the line is half its size."

This is a softer alternative to NPC mortality — NPCs change without dying.

### 9.2 `npc_archive_summarizer` — chronicler line on death

When an NPC dies or permanently departs, emit a one-line chronicler summary for WNS to consume. "Captain Vell Sarn died on the moors-stone in the seventh winter, taken by the hubtown line he had hunted for three winters." Feeds future WNS firings that want to reference the late NPC. Could be a WMS evaluator extension (`social_npc.py` extending to archived NPCs) rather than a standalone LLM endpoint.

### 9.3 `wes_npc_relational_planner` — for filling a locality's social network

When the planner is creating multiple NPCs for a locality in one plan, the current hub treats them as independent. A specialised relational planner would:
- Input: bundle + N NPC count + locality faction state
- Output: a relational graph (Vell → Edda is second-in-command; Edda → defector outsider; defector outsider → ex-hubtown comrade)
- Then: each NPC spec includes `cross_ref_hints.relational_role_with` referring to other NPCs in the same plan.

The current hub prompt's "AVOID duplication" guidance is too thin for this — a dedicated planner could do better. Probably premature; start by feeding hub the locality NPC roster (see §4.4 [FRAGMENT-GAP]) and see if it suffices.

### 9.4 `wes_npc_voice_curator` — voice coherence audit

A small LLM endpoint that reads a generated NPC's speechbank + narrative + personality.voice and answers: "Do these voices match?" Used as a quality gate during generation (supervisor extension). Designer-tunable acceptance threshold.

Probably folds into the supervisor (existing) rather than a standalone endpoint.

### 9.5 `wes_npc_dialogue_live` — fully open-ended player dialogue

Already exists as `NPCAgentSystem.generate_dialogue` but currently fragile (uses inline-built prompt, no dedicated fragment file, fixture is placeholder). Promoting this to a first-class fragment-tuned endpoint with proper context assembly (narrative + voice + phrase_bank + dynamic state + WNS focal narrative) would unlock the "I can ask any NPC anything" experience that the current implementation hints at but doesn't deliver well.

This is closer to "polish the existing endpoint" than a new endpoint, but it's significant enough that it should be a named work item.

### 9.6 `wes_npc_gossip_relay` — NPC-to-NPC narrative propagation

Currently `NPCAgentSystem.propagate_gossip` is deterministic — events spread by distance, NPCs absorb by interest. A speculative LLM layer would REINTERPRET the event per NPC personality: Vell hears "salt trade is booming in hubtown" and his knowledge[] entry becomes "the hubtown salt-thieves grow fat"; the herbalist hears the same event and her knowledge[] becomes "the salt-roads carry strange herbs now."

Probably out of scope for v4; flagged for future. Could be a WMS-side reinterpretation layer rather than WES.

### 9.7 Big-picture: the 3-endpoint NPC pipeline grows to potentially 5-7

Current: `wes_tool_npcs` + `wes_hub_npcs` + `npc_dialogue_speechbank` (3).
With speculatives: + `wes_npc_modifier` + `npc_archive_summarizer` + `wes_npc_relational_planner` + `wes_npc_voice_curator` + `wes_npc_dialogue_live` (potentially 8 total).

Some fold: voice_curator into supervisor; relational_planner into the existing planner; archive_summarizer into WMS evaluator. Pragmatic count at maturity: **4-5 endpoints**. The three shipped now are the load-bearing minimum (though `npc_dialogue_speechbank` needs the schema/prompt overhaul flagged in §2.4 + §4.2 to be usable).

---

## End

Four load-bearing fixes this trace surfaces, in priority order:

1. **Close the `BundleToolSlice` parent_summaries leak.** Same fix as Quests; benefits NPCs equally. Single patch unblocks every content tool's "born from a thread they don't see" failure mode.
2. **Rewrite `npc_dialogue_speechbank` prompt to match the static schema field-for-field.** Today the refresh endpoint emits a structurally incomplete speechbank (no idle_barks; greeting/quest_offer/quest_complete as singletons instead of lists). The endpoint is currently shipping but is silently degraded. Extract to a dedicated tag-indexed `prompt_fragments_npc_dialogue_speechbank.json`.
3. **Build the `NPCDatabase.get_voice_excerpt(npc_id)` publish API.** Quests need it; Skills need it; Titles need it; Hostiles will need it. Deterministic deep-link from any feature that references an npc_id. Splice into downstream tool inputs as `${giver_voice_anchor}` / `${taught_by_npc_excerpt}` / etc.
4. **Wire the speechbank mention extractor + AffinityShift→speechbank-stale link.** Without (a), NPC dialogue is a dead-end (words land and vanish). Without (b), NPCs whose standing has just shifted keep using old greetings until the next time-based refresh fires. Both are runtime-loop integration gaps; without them the WMS→WNS→NPC→WMS cycle is broken at the NPC→WMS arc.

Everything else in this trace — voice variance dials, refresh cadence, the dynamic registry, mortality archival, the speculative modifier endpoint — is downstream of those four.
