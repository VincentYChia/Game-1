# Feature Trace 07 — Titles

**Wave:** 2 (parallel with NPCs / Hostiles / Materials / Nodes / Skills / Chunks / WNS)
**Owned endpoints:** `wes_tool_titles`, `wes_hub_titles`
**Final output artifact:** `TitleDefinition` JSON entry inside `progression/titles-*.JSON` (one per LLM call from `wes_tool_titles`). Persistently consumed by `TitleDatabase`, evaluated against `Character` state by `TitleSystem.check_for_title`, and rendered as a "Title Earned" award when the player crosses the threshold.
**Date:** 2026-05-26

> "Titles look backward, not forward. They recognize what the player has done. The competition isn't 'no titles' — the competition is the slot-machine title that's the same for every player and the LLM title that invented a feud the player was never in."

Titles are fundamentally not like the other content tools. The hostile tool, the material tool, the chunk tool — those all paint things INTO the world for the player to encounter. The title tool paints things back AT the player, recognizing what they already did. That asymmetry rules everything below.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

The player has been hunting copperlash riders in the moors for the last hour and a half. Somewhere in the middle of the seventh kill, a brass-edged banner ribbon slides in from the top of the screen — a few words of bold serif text inside a thin frame, no animation gauche, just an arrival. *"Title earned: Apprentice Moors Reaver."* Below the title name, in lighter text, a bonus line: *"+25% melee damage. +5% critical chance."* The player can flick the banner open with a key — when they do, the narrative line unfolds underneath: *"You have cut down enough copperlash riders to know their rhythms in your sleep. The moors answer your arrival with a silence that carries down into the fog."* They close the banner and keep fighting. Two minutes later they remember it landed and they check the title in the menu. It's there, glowing, with a small icon, joined to their list.

That's the whole experience. Three beats — the arrival, the narrative reveal, the persistent badge in the menu. Plus a fourth quieter beat: in the next quest dialogue, the captain who recognizes them does so by their title; or the door at the moors gate that wouldn't open to a stranger now lets them through. Titles speak back to the world.

### 1.2 Timing budget — a different architectural constraint than quests

Quests have a 2-3 second scroll-unfurl as their latency mask. Titles have **no equivalent animation slot the way quests do**, because the title arrives as a reaction to the player crossing a threshold — there is no "the player just clicked the title-grant scroll" moment. The banner-ribbon entry is roughly 0.5 seconds; the cross-fade and bonus line is another 1 second. We cannot live-generate a title inside 1.5 seconds, much less a real-LLM round trip of 5-20s.

This means the title pool must be **pre-generated** before the player crosses the threshold. Pre-generation must fire at WNS cascade time, with the title sitting in `reg_titles` waiting for `TitleSystem.check_for_title` to find it, evaluate its requirements, and award it. The fact that titles already use threshold-driven `requirements.evaluate(character)` matches this perfectly — the runtime path is already there; the title just needs to exist before it's evaluated.

So the architecture is: pool-first, just like quests. But the firing trigger and the input shape are entirely different.

User direction analog: *"upon calls we make the [titles] and store them for the seamless experience."* The principle holds. The mechanics differ because the player's interaction with a title is "I crossed a threshold" not "I picked up a scroll."

### 1.3 Failure modes — what BAD looks like

**(a) Slop — generic templated title.** The player has killed 1000 wolves and the title is "Wolf Slayer (+10% damage vs canines)." Could have been spit out by a 1990s if/else table. The bonus is the only thing that distinguishes the title from a status effect; the name is bland; the description is empty; the narrative is "You have killed many wolves." This is the dominant failure mode — most fantasy RPG titles read this way. The LLM has rich biographical context available; the failure is the prompt not asking for biographical specificity. *(Defense: the locality / faction / domain personalization fields must be SLOTS in the tool input, fed from the player's actual recent activity context. If the player's last 50 wolf kills happened in Eastbend, the title should be "Wolf Slayer of Eastbend," not "Wolf Slayer." The data exists — see §5.)*

**(b) Stagnant predictability — only milestone titles.** The player gets a novice title at 50 kills, apprentice at 500, journeyman at 5000, expert at 20000, master at 100000. Every title in their list is a counter-driven, tier-laddered, predictable shape. No special-circumstance titles. No "you survived this thing" or "you did it without dying" titles. Three play sessions in, the player can name the next four titles they'll earn. *(Defense: the system already has four `acquisitionMethod` values — `guaranteed_milestone`, `event_based_rng`, `hidden_discovery`, `special_achievement`. The pool must be SEEDED with non-milestone titles too — titles whose triggers are circumstance, not count. The planner / hub must be tuned to fire titles for narrative-cue conditions, not only for "the player crossed N kills" thresholds.)*

**(c) Craziness — title invented from nothing.** The LLM grants "Defeater of the Lord of Sponges" to a player who has never seen a sponge. Or "Liberator of Aldenfen" when no such place exists. Or "First-Ascender of the Burning Stair" when no quest, no NPC, no chunk has ever mentioned a burning stair. Titles invent context the world doesn't have. This is the title-specific version of the craziness mode — and it's especially corrosive for titles because the player can't *do* anything with a title that references nothing real. *(Defense: cross-ref discipline at the hub layer. The hub must refuse to invent NPCs, locations, factions not in the registry or in the bundle's narrative. The `condition_anchor` field in hub flavor_hints names the real-world peg the title is tied to, sourced from WMS interpretation tags or committed registry entries.)*

**(d) Bonus mismatch — bonus that does nothing.** The LLM authors a title with `bonuses: {"crystalline_attunement": 0.30}` and the runtime has no consumer for `crystalline_attunement`. The title loads, the player sees +30% Crystalline Attunement in their menu, and it does literally nothing. *(Defense: the existing CONSUMER-VERIFIED bonus allow-list in the tool prompt — solid; but a `[FRAGMENT-GAP]` for how the planner picks bonus keys when none of the verified bonuses fit the title's flavor. The planner needs a "matching allowed bonus" hint built from the title's intended thematic frame, see §5.)*

**(e) Title spam — too many low-tier titles.** Forty novice titles by hour 3. Each one is fine in isolation; collectively, they become wallpaper. The player stops looking at the banner ribbon because half a dozen pop per session. *(Defense: tier-distribution caps. Novice titles fire once per primary domain (mining, combat, smithing, etc.) — there shouldn't be three novice-tier "kill enough things" titles for slightly different enemy types. The planner needs awareness of `recent_registry_entries` AND of the player's already-earned title set so it doesn't keep emitting near-duplicate novices.)*

**(f) Disconnected from the world's recognition.** The player earns "Master Eternal Smith" but no NPC ever recognizes the title; doors don't open; faction standing doesn't shift; quest dialogue makes no acknowledgement. The title is a private museum exhibit. *(Defense: NOT a tool-generation problem; this is a downstream consumer problem in NPC dialogue / quest gating / faction reaction. Flagged as a `[WES-SCHEMA-GAP]` against NPC speechbank conditioning and quest `requirements.titles[]` use, not as a title-tool gap. The tool can supply great titles; the world must learn to react to them.)*

### 1.4 What "good" actually looks like

A good earned title, in the player's words after playing for an hour: *"I have 'Lighthouse Veteran of Brackhollow.' I got it because I survived three different lighthouse keepers' funerals during the haze plague and helped extinguish the last beacon — I remember which kills counted toward it, and the name reads like the chronicler picked it up from somebody on the docks."*

Four properties:
- **Earned, not granted** — the player can name what they DID that caused it.
- **Locality-specific** when the locality matters (Wolf Slayer **of Eastbend**), generic when the achievement transcends place (Master Eternal Smith).
- **Faction-resonant** when faction context dominated the earning (Knighted by the Verdant Guard) — and the title carries that faction's reciprocal recognition into future interactions.
- **Tier-proportional** — a master title doesn't feel like a novice title with bigger numbers; it feels like a genuine arrival. A novice title doesn't pretend to be epic.

---

## 2. Output artifact schema completeness audit

The `TitleDefinition` JSON shape is set by `data/models/titles.py:9-27` + the JSON conventions in `progression/titles-1.JSON`. The runtime parser is `data/databases/title_db.py:39-81`. Every field below must be filled by the tool unless flagged otherwise.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `titleId` | str (snake_case) | `wes_tool_titles` | Should encode tier + role + (optional) domain. `apprentice_moors_reaver` beats `title_0042`. Should be unique against `reg_titles`. |
| `name` | str (Title Case) | `wes_tool_titles` | Evokes domain AND optionally locality. "Apprentice Moors Reaver" beats "Reaver." For locality-specific titles, the locality suffix ("of Eastbend") is what makes it feel earned. |
| `titleType` | str (one of 4) | `wes_tool_titles` | combat / crafting / gathering / utility. Must align with the player activity that earned it. |
| `difficultyTier` | str (one of 6) | `wes_tool_titles` | novice / apprentice / journeyman / expert / master / special. Drives all the band defaults. |
| `description` | str (1 sentence) | `wes_tool_titles` | Evocative, NOT a stat enumeration. "Fire-veined ores call to you" beats "+25% mining damage, +15% fire ore chance." |
| `bonuses` | Dict[str, float] | `wes_tool_titles` | 1-4 keys from CONSUMER-VERIFIED allow-list. Primary at tier-primary value (e.g. apprentice=0.25); secondaries in tier-secondary range. **Bonus key choice must match titleType** — a combat title cannot give `miningSpeed`. |
| `prerequisites.conditions[]` | List[Dict] | `wes_tool_titles` | 1-3 conditions. At least one is the threshold-crossing trigger (`stat_tracker` path); higher tiers add `title` chain link + `level` floor. **stat_path must come from VERIFIED ALLOW-LIST**, see §5. |
| `acquisitionMethod` | str (one of 4) | `wes_tool_titles` | guaranteed_milestone / event_based_rng / hidden_discovery / special_achievement. Locked to tier (novice→guaranteed, master→special_achievement, etc). |
| `generationChance` | float 0-1 | `wes_tool_titles` | Locked to tier band (novice=1.0, apprentice=0.20, master=0.02). |
| `isHidden` | bool | `wes_tool_titles` | true only when `difficultyTier=special`. Surfaces in the title menu only after first earn. |
| `narrative` | str (2-3 sentences) | `wes_tool_titles` | The voiced chronicler line the player reads when they expand the banner. **This is the property that makes the title feel earned.** Must reference the activity context, ideally the locality / faction / specific deed. |
| `iconPath` | str | auto-generated by loader if absent | Loader fills `titles/{titleId}.png`. Designer-authored assets — placeholder OK. |
| **Legacy / deprecated fields** | | | |
| `activity_type` | str | derived by parser | Loader maps the first activity in legacy `activities` dict to one of [mining, forestry, smithing, ...]. New-format titles should use `prerequisites.conditions[]` instead — legacy filled for backward compat. |
| `acquisition_threshold` | int | derived by parser | Same — legacy mirror of first activity threshold. |
| `prerequisites` (legacy list) | List[str] | derived by parser | Mirror of `prerequisites.requiredTitles`. Legacy. |

### 2.1 Schema completeness — what's MISSING

Walking the schema against the player-experience anchor and the cross-feature needs, the following fields the design surfaces are **not in the current `TitleDefinition` schema** or in the tool prompt's authored shape:

- `[WES-SCHEMA-GAP]` **`flavor_locality`** — a field naming the locality (or district/region) the title is tied to. Currently the locality is implicit in the `name` ("Apprentice Moors Reaver" implies the moors), but it's not structured. Without a structured field, downstream consumers (NPC recognition: "ah, you're the Moors Reaver" — that NPC needs to know which NPCs in *which locality* should care) have no clean way to query. Recommendation: add `flavor_locality: Optional[str]` to `TitleDefinition`, filled by the tool from `cross_ref_hints.locality_anchor`. Backward compatible — old titles default to None.
- `[WES-SCHEMA-GAP]` **`flavor_faction`** — same problem for factions. A title knighted by the Verdant Guard should know it was *that* faction. Currently the tool can put faction prose in the narrative but no structured field captures it. Recommendation: `flavor_faction: Optional[str]`.
- `[WES-SCHEMA-GAP]` **`granted_by_quest_id`** — Agent 1's seed. When a title is awarded as a quest reward, the title should know which quest granted it so its narrative can reference the granting deed. Currently the only path is `prerequisites.conditions` of type `quest` (require quest X completed), which is a *requirement* not a *flavor source*. They overlap but aren't the same — a title can be quest-granted without quest-required-as-prereq if other paths also earn it. Recommendation: `granted_by_quest_id: Optional[str]`, filled by tool from `cross_ref_hints.granted_by_quest_id`.
- `[WES-SCHEMA-GAP]` **`signature_deeds[]`** — an array of 1-3 short string descriptors of what deeds led to this title's flavor (e.g. `["killed 100 copperlash riders in the moors", "survived three salt-tide raids", "burned the moors-stone in vengeance"]`). The narrative line is *prose* about these deeds; this is the *structured fact list*. Future modifier-AI and chronicler endpoints can consume these. Recommendation: `signature_deeds: List[str]` (1-3 entries), filled by tool from the WMS interpretation snapshot at firing time.
- `[WES-SCHEMA-GAP]` **`tags[]`** — every other content type has a `tags[]` field (locked allow-list, drives WMS retrieval and downstream classifiers). Titles don't. The hub prompt has nowhere to thread WMS-tag-indexed retrieval. Recommendation: `tags: List[str]` with allow-list `domain:*`, `tone:*`, `arc_tag:*`, `species:*`, `faction:*`, `tier:*` — the same families WMS uses.
- `[WES-SCHEMA-GAP]` **`earned_at_address`** — runtime field, written when `TitleSystem._award_title` actually awards the title. Captures the locality/district/region/province/nation where the player crossed the threshold. **Currently not captured at all** — the `TITLE_EARNED` event publishes `actor_id` and `title_id` but no address. The progression_identity evaluator (`world_memory/evaluators/progression_identity.py:91`) writes the title to WMS without an `affected_locality_ids` even though the event has the field — it falls back to `locality_id` from the event, which the publishing site doesn't set. Recommendation: title award path passes the player's current address into the published event; runtime title instance carries `earned_at_address`.
- `[FRAGMENT-GAP]` **player-fit signals into the tool input** — the tool has no slot for "the player's actual recent activity profile at the time the title would fire." Right now the hub authors a `condition_anchor` (a thematic frame) and a `stat_path_hint` (a suggested stat path); the tool doesn't get a snapshot of recent counters. Without the snapshot, the tool guesses at thresholds — see §5.1 for the proper extraction.
- `[FRAGMENT-GAP]` **the tool prompt has no slot for the narrative chunk of WNS that spawned this firing.** Same `BundleToolSlice.parent_summaries` leak Agent 1 flagged at `context_bundle.py:342-370`. Titles need this — the *voice* of the title's narrative line should taste like the chronicler that birthed it (a moors-region narrative has a different voice from a coastal-marches one). Fix shared with all 8 content tools.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent 1990s systematic title generator (no LLM) produces, given a player stat threshold and a tier table:

```json
{
  "titleId": "apprentice_warrior",
  "name": "Apprentice Warrior",
  "titleType": "combat",
  "difficultyTier": "apprentice",
  "description": "You have killed many enemies.",
  "bonuses": {
    "meleeDamage": 0.25,
    "criticalChance": 0.05
  },
  "prerequisites": {
    "conditions": [
      {"type": "stat_tracker", "stat_path": "combat_kills.total_kills", "min_value": 500},
      {"type": "title", "required_title": "novice_warrior"},
      {"type": "level", "min_level": 5}
    ]
  },
  "acquisitionMethod": "event_based_rng",
  "generationChance": 0.20,
  "isHidden": false,
  "narrative": "You have proven yourself in battle. You are no longer a novice."
}
```

This is fine. It is also a generic shape any switch table can spit out. The player sees the same thing every other player sees. It says nothing about THEM.

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM contributes that the slot machine cannot:

1. **`titleId`** — encode the place, the deed, OR the faction. `apprentice_moors_reaver` not `apprentice_warrior`. Needs `condition_anchor` from hub + `locality_anchor` cross-ref.
2. **`name`** — the locality suffix or the role qualifier. "Apprentice Moors Reaver" not "Apprentice Warrior." If the title is a universal milestone (Master Smith), drop the suffix. If it's locality-rooted (Wolf Slayer of Eastbend), keep it.
3. **`description`** — evocative, not enumerative. "The moors answer your arrival with a silence" beats "+25% melee damage." Needs `prose_fragment` from hub + WNS narrative excerpt + `signature_deeds[]`.
4. **`prerequisites.conditions[]`** — the slot machine picks one stat path and one threshold. The LLM should sometimes layer a *second* stat path (e.g. "kill 500 copperlash riders AND survive 5 salt-tide raids") — composite triggers feel less mechanical. Sometimes layer a quest completion: "kill 500 raiders AND completed `the_moors_vendetta` quest." This is what makes a title feel like a chapter of the player's story, not a counter cross.
5. **`bonuses` keys + values** — the slot machine picks the tier-primary. The LLM should choose secondary bonuses that fit the title's NARRATIVE — a Wolf Slayer title gets `criticalChance` because dispatching wolves with critical hits is the deed's flavor; a Master Smith gets `firstTryBonus` because mastery is single-strike fluency.
6. **`narrative`** — biographical. References the deeds (`signature_deeds[]`). Names the place where it was earned. Hints at what the world now sees in the player. "You have cut down enough copperlash riders to know their rhythms in your sleep. The moors answer your arrival with a silence that carries down into the fog." Slot machine: "You have killed many enemies."
7. **`tags[]`** — feeds WMS retrieval + faction reaction + NPC speechbank conditioning. The slot machine has no concept of WMS tags. The LLM must emit tags from the allow-list that future consumers will key off (e.g. `["domain:combat", "species:copperlash_rider", "tone:grim", "faction:moors_raiders"]`).

The delta is: **specificity of locality / deed / faction, narrative voice, and downstream consumer hooks.** Without those, the title is a stat patch. With them, the title is a chapter title in the player's biography.

---

## 4. Backward trace through the pipeline

This is the rung-by-rung walk from "banner ribbon slides in" backward to "WMS event row." Note: **for titles, the primary information source is the WMS substrate + StatStore, not the WNS narrative.** The WNS narrative is *flavor* — the *trigger* and the *biographical content* live in WMS. The trace order reflects this.

### 4.1 Rung 0 — Banner ribbon slides in (player-facing)

Consumes: `TitleDefinition` (from `TitleDatabase.titles`) + `Character` state at the moment the threshold is crossed.
Trigger: `TitleSystem.check_for_title(character, ...)` is called by the game loop / event hooks (combat kills, crafting completes, gather completes, level-ups). When `title.requirements.evaluate(character)` returns True and acquisition_method gates pass, `_award_title` fires.
Emits: banner UI; `earned_titles` list append; `stat_tracker.record_title_earned`; `TITLE_EARNED` event publish.

Risk: if no pre-generated title with these `prerequisites.conditions[]` exists for the activity the player just did, no banner fires. **The pool must always cover the major threshold paths** — every `stat_tracker.stat_path` the player can realistically cross should have at least one earnable title. This is the title-pool equivalent of "the giver NPC must always have a non-empty quest pool." See §7.

### 4.2 Rung 1 — `TitleSystem.check_for_title` (runtime evaluator, not LLM)

Inputs: `Character` (full state) + optional `activity_type`, `count` legacy params.
Logic: iterate every loaded title; skip already-earned; check `requirements.evaluate(character)`; gate by acquisition_method.

Solid. No LLM call here, no gap. The full power lives in the existing `UnlockRequirements.evaluate` over the `UnlockCondition` hierarchy (`data/models/unlock_conditions.py` lines 47-307).

The one optimization opportunity: `check_for_title` is **O(titles × conditions)** at every hook fire. Once the pool grows to several hundred titles, this becomes a hot path. Not a `[WMS-GAP]` — a *runtime engineering note*. Recommendation: bucket titles by primary stat_path so each hook only checks the titles whose conditions reference paths the hook just touched. Out of scope for this trace.

### 4.3 Rung 2 — `wes_tool_titles` (one ExecutorSpec → one title JSON)

Current inputs (from `prompt_fragments_tool_titles.json:_core.user_template`):
- `spec_id`, `plan_step_id`, `item_intent`, `hard_constraints` (titleType / difficultyTier / primary_bonus_key), `flavor_hints` (name_hint / prose_fragment / condition_anchor / stat_path_hint / required_title_hint), `cross_ref_hints` (required_title — for tier chain).

The tool prompt itself is **the strongest of the 8 WES tool prompts** — it has CONSUMER-VERIFIED bonus allow-lists, VERIFIED stat_tracker path allow-lists, tier value bands, and a worked example. This is good prior work and should be preserved.

What's MISSING:

- `[FRAGMENT-GAP]` **The biographical snapshot.** The tool sees `condition_anchor: "moors raiders"` but does not see the *factual record* of what the player did to earn the title. It has no `signature_deeds[]` to draw on. Without that, the `narrative` field is necessarily generic — the LLM is guessing at the player's history from a thematic anchor instead of writing from the actual chronicle. **Fix**: extend the tool user_template with `${biographical_snapshot}` — a structured 5-15-line summary of the player's recent activity tagged to the title's domain. Authored by the hub from WMS query (see Rung 3) + StatStore lookup. This is THE highest-leverage missing input for title quality.
- `[FRAGMENT-GAP]` **The locality/faction structured anchors.** `condition_anchor` is a single freeform string. For the schema fields we want (`flavor_locality`, `flavor_faction`, `granted_by_quest_id`), the tool needs explicit slots: `${locality_anchor}`, `${faction_anchor}`, `${quest_anchor}`. Currently the tool tries to pull all three out of a single `condition_anchor` string — fragile.
- `[FRAGMENT-GAP]` **The bonus allow-list hint.** The hub picks `primary_bonus_key` but the tool's bonus allow-list is *consumer-verified* (only those keys do anything live). When the hub's primary_bonus_key isn't in the allow-list, the tool currently has no fallback strategy other than "pick one yourself." The tool prompt should explicitly say: if `primary_bonus_key` is not in the allow-list, prefer the closest semantic match from the allow-list AND emit a tag indicating the original intent. This is a prompt-text fix, not a schema fix.
- `[FRAGMENT-GAP]` **WNS narrative excerpt.** Same `BundleToolSlice.parent_summaries` leak as every other tool. The tool prompt has no `${narrative_context}` slot — the moors-tone, the salt-tide imagery, the faction's specific vocabulary all live in the parent narratives and get dropped. Fix at the bundle slice layer benefits this tool too.
- `[FRAGMENT-GAP]` **Already-earned title set.** The hub gets `recent_registry_entries` (recent generations). The tool gets nothing about the player's *earned* titles. For chain-link cross-refs (`apprentice_moors_reaver` requires `novice_warrior` — does the player have it?) and for de-duplication (don't generate a near-identical apprentice title to one the player just got), the tool should see `${player_earned_titles}` — a short list of the player's currently-earned title_ids.

### 4.4 Rung 3 — `wes_hub_titles` (one plan step → batch of ExecutorSpecs)

Current inputs (from `prompt_fragments_hub_titles.json:_core.user_template`):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "title rewarding sustained anti-copperlash play, granted at threshold" and emits 1+ `<spec>` elements with hard_constraints + flavor_hints + cross_ref_hints loaded.

What's MISSING:

- `[FRAGMENT-GAP]` **The hub has no WMS query interface.** The single biggest title-specific gap. For a title to be biographically accurate, the hub MUST know what the player has actually been doing. The hub currently authors `condition_anchor: "moors raiders"` from the planner's `step_intent`, but it has no way to ask the WMS: "what species has this player been killing in this region for the last N game-days, and what stat counter best captures that?" The answer is sitting one rung away in StatStore and in the recent L2 interpretations — but the hub can't reach. **Fix**: extend the hub with a deterministic `${biographical_snapshot}` field assembled BEFORE the hub LLM call by code in `wes_orchestrator.py` or `plan_dispatcher.py`, which:
  1. Queries `StatStore` for the top N highest-rate stat paths the player has touched in the last 7-14 game days.
  2. For each top path, looks up the related WMS L2 interpretations in the firing address's locality set.
  3. Renders a 5-15-line digest of the player's biographical activity, tagged to the title's domain hint.
  This digest is then passed through to the tool layer via `flavor_hints.biographical_snapshot`.
- `[FRAGMENT-GAP]` **Same parent_summaries leak.** Hub gets a `BundleToolSlice` (`context_bundle.py:342-370`) that has stripped parent_summaries. For titles, the parent summary contains the *world's recognition of this player* at the relevant scope. Fix shared with all 8 hubs.
- `[FRAGMENT-GAP]` **Already-earned titles in `recent_registry_entries`.** The hub's `recent_registry_entries` is whatever the caller passes. For titles, the relevant "recent" is **the player's own earned title list**, not just recent generations. Two separate slices: `recent_registry_entries` (avoid duplicate generations) AND `${player_earned_titles}` (avoid generating titles the player already has near-duplicates of, plan chain links correctly).
- `[FRAGMENT-GAP]` **Cross-tool co-emission awareness.** When the plan emits `[hostiles, titles]` with the title depending on the hostile (the title rewards killing N of the new hostile), the hub gets `step_slots` naming the hostile but doesn't see the hostile's tier/tags/locality. So the title's `condition_anchor` and stat_path can't easily reference the hostile's species. Same fix shared with quests: dispatcher attaches co-emitted artifact summaries to the hub input.

### 4.5 Rung 4 — `wes_execution_planner` (one bundle → one plan DAG)

Same inputs as for quests (Agent 1 §4.6). The planner sees the full bundle. It MUST emit a `titles` step when:
- A region-or-larger thread has matured and a player-facing milestone exists at this scope.
- A quest step (in the same plan) reserves a `title_hint` reward, so the title must be co-emitted to satisfy the orphan detector.
- Player threshold crossings are imminent (this is the trickier case — see Rung 6).

The planner prompt example (`prompt_fragments_wes_execution_planner.json:_output.example`, step s7) shows a titles step depending on a hostile step. This is correct. The titles tier discipline is correct: "Tier 3 (district): ... 1-2 of [..., title]. Tier 4 (region): cross-tool sets including titles."

What's MISSING:

- `[FRAGMENT-GAP]` **Title-specific firing guidance.** The planner prompt is largely generic. The `new-title` purpose bucket is not currently called out separately. Per memory `feedback_wns_prompts_must_be_tag_indexed.md`, the WNS-side `_wes_tool` body should list `new-title` as a purpose at the relevant scopes (NL3 district, NL4 region) and tell the weaver WHEN to fire it. Currently NL3's `_wes_tool` lists new-chunk/new-faction/new-skill/new-npc/new-quest but no new-title; NL4 likewise omits it. **Fix at WNS layer, not planner layer.** Recommend: add `new-title` to the NL3 and NL4 `_wes_tool` purpose buckets with guidance: "fire when a player threshold or arc completion implies recognition the registry can't yet grant." See §4.7.
- `[FRAGMENT-GAP]` **Player threshold awareness at the planner.** The planner has no signal that the player is *about to* cross a milestone. It only knows what tier of bundle fired. If the player is at 487 copperlash kills with 500 being the apprentice threshold, the planner doesn't know that. For *just-in-time* title generation (vs. eager full-pool), this matters. Probably acceptable to skip — the eager-pool strategy means we generate ahead and any threshold-bound title sits waiting. But if pool size becomes a problem, planner threshold awareness becomes a future endpoint (see §9).

### 4.6 Rung 5 — WNS NL3 / NL4 weavers emit `<WES purpose="new-title">`

The `_wes_tool` fragments in `narrative_fragments_nl3.json:27` and `narrative_fragments_nl4.json:19` define when `<WES>` fires from each layer. As noted in 4.5, **neither layer currently lists `new-title` as a purpose bucket.**

What's MISSING:

- `[WNS-GAP]` **`new-title` is not an enumerated purpose at any WNS layer.** The system can technically emit `<WES purpose="new-title">` because the planner allows the `titles` tool, but the weaver fragment never tells the weaver to do so. So in practice titles get emitted only when the planner happens to add them as cross-refs from quests (e.g. "this quest hints at a title reward"). **Untapped firing path.** Fix: add `new-title` to NL3 and NL4 `_wes_tool` purpose lists with guidance like:

  ```
  - new-title: when a regional arc converges on a player-facing milestone — the kind of deed
    that the chronicle wants to label. Fire when one of:
      • a thread has just crossed turning_point on an agency:player arc
      • a faction's standing toward the player has shifted enough to warrant naming
      • a unique encounter (boss kill, plague survival, first-ascend) has occurred
        and no title exists to recognize it
    Body should name the deed-class (combat / crafting / survival / discovery / political),
    the affected locality or faction, and the rough difficulty tier.
  ```
- `[WNS-GAP]` **The directive_text body shape.** Same shape issue as quests — without guidance, the weaver writes "Generate a title." (slop). Or writes a directive that doesn't carry the deed-class, locality, faction, OR difficulty tier — so the planner has nothing to weight scope by. Fragment-author responsibility: the `_wes_tool` body for `new-title` should call out these four pegs as required content.
- `[WNS-GAP]` **NL5+ (province / nation / world) `_wes_tool` should also expose new-title for cross-scale titles.** A "Hero of the Northern Realm" title is province-scale. A "World-Breaker" title is world-scale. These extreme-tier titles need a path from NL5-NL7 firings. Currently NL5+ scope rules are unstudied; flagged as part of WNS-layer authorship.

### 4.7 Rung 6 — WNS reads WMS L2 interpretations

The NL weavers consume `${wms_context}` — a rendered brief of recent WMS L2 interpretations whose `affected_locality_ids` intersect the firing address's locality set.

For titles specifically: the relevant WMS interpretation **categories** are `player_milestone` (from `player_milestones.py`), `progression_identity` (from `progression_identity.py`), `combat_kills_*` (regional kill-count rollups), `gathering_global` / `gathering_regional` (gather rollups), `crafting_*` (per-discipline crafting evaluators), `social_quests` (quest completion rollups), `exploration_*` (discovery rollups), and `faction_reputation` (player standing shifts).

These are exactly the interpretation categories that should carry the title's biographical signal. The good news: **all the relevant evaluators already exist and are running.** The signal is on disk.

What's MISSING:

- `[FRAGMENT-GAP]` (NOT WMS-GAP) **The `${wms_context}` budget at WNS firings.** It's char-budgeted (600 chars per Agent 1's note). For title-firing layers (NL3, NL4), the WMS context needs to prioritize *player_milestone* + *progression_identity* + the dominant activity category. Currently the budget allocation is uniform across categories. Fix: WMS context builder takes a hint from the firing weaver's expected `<WES>` directives (or just always weights player_milestone / progression_identity slightly heavier at the title-firing layers).
- `[FRAGMENT-GAP]` **Faction reputation context.** The `faction_reputation` evaluator exists; its interpretations land in WMS. For title generation, faction-driven titles (e.g. "Knighted by the Verdant Guard") require the faction's affinity shift events to surface in `${wms_context}`. Currently faction interpretation visibility at WNS layers is uniform; faction-titles want it weighted up.

### 4.8 Rung 7 — WMS L2 evaluators consume L1 events

The relevant evaluators for title biographical content:

- `player_milestones.py` — already produces "Player has killed N enemies of type X in region Y" lines with severity bands. Direct title-fuel.
- `progression_identity.py` — handles `title_earned` and `class_changed` events. Writes back-into-WMS the title-earned chronicle line. Reflexive.
- `combat_kills_regional_low_tier.py` / `combat_kills_regional_high_tier.py` — region-scale species kill rollups with thresholds. Already used by quest tool's species-anchor; equally good for title's species-anchor.
- `gathering_global.py` / `gathering_regional.py` — region/global gather counts. Drive gathering-tier titles.
- `crafting_*.py` (8 evaluators across disciplines) — discipline-specific craft milestones. Drive crafting-tier titles.
- `exploration_territory.py` / `exploration_dungeons.py` — discovery and dungeon-completion rollups. Drive utility/exploration titles.
- `faction_reputation.py` — faction standing shifts. Drive faction-themed titles.

All present. All running. All correctly tagged. **No `[WMS-GAP]` at this layer.**

---

## 5. Per-field provenance table

For EVERY field that the LLM authors (so excluding loader-derived legacy fields), where the upstream signal comes from. The 9-rung WMS column applies when a `[WMS-GAP]` might be tempting.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `titleId` | Tool prompt + hub `flavor_hints.name_hint` + registry-uniqueness | name_hint flows from hub which got it from planner's `step.intent` + `step.slots` | Yes | — |
| `name` | Tool prompt + `flavor_hints.name_hint` | hub crafts from `step.intent` + `address_hint` + `condition_anchor` | Yes | — |
| `titleType` | Hub `hard_constraints.titleType` | Hub picks from 4 based on `step.intent` activity domain | Yes | — |
| `difficultyTier` | Hub `hard_constraints.difficultyTier` | Hub picks from 6 based on planner's `step.slots.tier` + thematic peg | Yes | — |
| `description` | Tool prompt | `item_intent` + `prose_fragment` — but stretched thin without biographical snapshot | Partial | `[FRAGMENT-GAP]` — tool input lacks `${biographical_snapshot}` to ground the description in actual player deeds |
| `bonuses` (keys + values) | Tool prompt | Hub `hard_constraints.primary_bonus_key` + tool's tier value bands + consumer-verified allow-list | Yes | — |
| `prerequisites.conditions[]` (stat_tracker type) | Tool prompt + `flavor_hints.stat_path_hint` | Hub picks from VERIFIED ALLOW-LIST based on `step.intent` | Yes | — |
| `prerequisites.conditions[]` (title type) | Tool prompt + `cross_ref_hints.required_title` | Hub picks based on chain link; planner emits previous-tier title via co-emission | Yes (but co-emission must commit before this title's check) | — |
| `prerequisites.conditions[]` (level type) | Tool prompt | Tier × suggested floor (apprentice=5, journeyman=10, expert=20, master=40) | Yes | — |
| `prerequisites.conditions[]` (quest type) | Tool prompt + `cross_ref_hints.required_quest` | When title is quest-gated, planner/hub provides quest_id (Agent 1 cross-ref) | Partial | `[WES-SCHEMA-GAP]` — current hub flavor_hints have no quest cross-ref slot for titles; Agent 1's `granted_by_quest_id` seed is the reciprocal side |
| `prerequisites.conditions[]` (skill type) | Tool prompt + `cross_ref_hints.required_skill` | When title requires skill, planner/hub provides skill_id | Partial | `[WES-SCHEMA-GAP]` — hub flavor_hints have no skill cross-ref slot for titles |
| `prerequisites.conditions[]` (faction type) | NOT CURRENTLY SUPPORTED | No `FactionCondition` in `unlock_conditions.py` | No | `[WES-SCHEMA-GAP]` — faction-affinity-gated titles (e.g. "you must be Verdant-aligned at +0.5") have no condition type. Worth adding `FactionAffinityCondition` to `unlock_conditions.py`. |
| `acquisitionMethod` | Tool prompt | Locked to tier by tool prompt | Yes | — |
| `generationChance` | Tool prompt | Locked to tier by tool prompt | Yes | — |
| `isHidden` | Tool prompt | true only when difficultyTier=special | Yes | — |
| `narrative` | Tool prompt | `item_intent` + `prose_fragment` + (would-be) `biographical_snapshot` + (would-be) `narrative_context` | Partial | `[FRAGMENT-GAP]` — without biographical_snapshot and parent_summaries narrative excerpt, narrative voice is generic. Both leaks fixed at hub/bundle layer benefit this. |
| `tags[]` (proposed addition) | Tool prompt | Tool picks from allow-list seeded by `tags` library | Schema gap (see §2.1) | `[WES-SCHEMA-GAP]` — `tags[]` not currently in TitleDefinition |
| `flavor_locality` (proposed) | Cross-ref hint from hub | `cross_ref_hints.locality_anchor` from planner's `address_hint` | Schema gap | `[WES-SCHEMA-GAP]` |
| `flavor_faction` (proposed) | Cross-ref hint from hub | `cross_ref_hints.faction_anchor` from WNS narrative thread tags | Schema gap | `[WES-SCHEMA-GAP]` |
| `granted_by_quest_id` (proposed; Agent 1's seed) | Cross-ref hint from hub | `cross_ref_hints.granted_by_quest_id` from co-emitted quest step | Schema gap | `[WES-SCHEMA-GAP]` |
| `signature_deeds[]` (proposed) | Tool prompt | Pulled from `${biographical_snapshot}` — 1-3 short deed summaries | Schema gap + fragment gap | `[WES-SCHEMA-GAP]` + `[FRAGMENT-GAP]` |
| `earned_at_address` (runtime field) | Award path | `TitleSystem._award_title` reads player's current address | Not currently captured | `[WES-SCHEMA-GAP]` — schema slot + award-path wiring + WMS event payload addition |

### 5.1 WMS-GAP walk — the biographical snapshot

The single piece of context I was tempted to call `[WMS-GAP]` on: **a structured biographical snapshot of the player at the moment of title firing, ready-to-render for the tool.**

The use case: when the title tool fires for an `apprentice_moors_reaver` candidate, the tool needs to know — in structured form — that the player has killed 487 copperlash riders, mostly in the salt_moors locality, with 23 critical hits, over 8 game-days, alongside surviving 3 salt-tide raids and completing 1 vendetta quest from Captain Vell. This is *what makes the narrative* "you have cut down enough copperlash riders to know their rhythms in your sleep" instead of "you have killed many enemies."

Per the user's directive: walk all 9 rungs before declaring `[WMS-GAP]`.

1. **Direct query** — Is there a single WMS row containing "player's biographical activity summary tagged for title generation"? No — the chronicle is per-event, per-interpretation. Multiple rows must compose.
2. **Adjacent events** — `event_store.query(event_type="enemy_killed", event_subtype="killed_copperlash_rider", since_game_time=...)` returns the raw kills. Plus `event_store.query(event_type="enemy_killed", actor_id="player", locality_id="salt_moors", ...)`. Plus `interpretation_store.query(category="combat_kills_regional_high_tier", affected_locality_ids contains "salt_moors", ...)`. All present, all queryable. The biographical snapshot is the *composition* of these three queries. **The data exists in WMS — what's missing is the rendering code.**
3. **Negative patterns** — The player has NOT been killing wolves (so the title shouldn't be "Wolf Slayer"). Absence of competing categories is a useful disambiguator. Computable from the same stat queries.
4. **Aggregation** — `daily_ledger.unique_enemy_types_fought` rolls per-day enemy diversity. `combat_kills_regional_high_tier` aggregates kills per region per species per time window with severity bands. The aggregation evaluators exist and run.
5. **Trajectory** — Are copperlash kills rising or stable? `combat_kills_regional_*.py` evaluators have lookback windows (150s by default — designer-tunable). Rate-of-change queryable.
6. **Cross-layer climb** — NL3 narratives often interpret these stats into chronicler-voice prose ("the moors-stone road grows quiet of riders"). The interpretation is one layer up from the raw counts. Both useful — counts for the threshold-trigger, NL3 interpretation for the narrative voice.
7. **Cross-entity composition** — "many copperlash kills + quest completion of `the_moors_vendetta` + standing shift toward Captain Vell" is the composite signal that distinguishes `apprentice_moors_reaver` from a generic `apprentice_warrior`. All three rows exist; the join is a query.
8. **Stat / ledger lookup** — `StatStore.get_value("combat.kills.species.copperlash_rider.location.salt_moors")` returns the count. **Cleanest single signal.** Plus the dimensional breakdowns the `record_*` methods write automatically (`stat_tracker.py:267-340`).
9. **Trigger history** — Has the threshold-crossing trigger fired before for this player on this stat path? The 'already-earned' check in `check_for_title` covers it.

**Verdict**: NOT a WMS gap. The signal is composable from existing rows. The gap is at the **hub-orchestration layer** — the hub doesn't currently CALL the queries to compose the snapshot. Marker: `[FRAGMENT-GAP]` on the hub's input assembly path (a code-side, pre-LLM-call task), not `[WMS-GAP]`.

The actual code path needed:

```python
# Sketch — in plan_dispatcher.py or wes_orchestrator.py before hub call:
def compose_biographical_snapshot(
    bundle: WESContextBundle,
    plan_step: PlanStep,
    stat_store: StatStore,
    interpretation_store: EventStore,
    title_type_hint: str,  # combat / crafting / gathering / utility
) -> str:
    """Render a 5-15-line digest of the player's biography tagged to a title type."""
    locality_set = bundle.delta.locality_ids
    top_paths = stat_store.top_paths_by_recent_growth(
        n=8, locality_filter=locality_set, category_filter=title_type_hint,
        since=bundle.delta.since_game_time,
    )
    top_interpretations = interpretation_store.query(
        category_in=["combat_kills_regional_*", "player_milestone", "progression_identity"],
        affected_locality_ids=locality_set,
        actor_id="player",
        limit=10,
    )
    lines = []
    for path, current, delta in top_paths:
        lines.append(f"- {path}: {current:.0f} ({'+' if delta>0 else ''}{delta:.0f} in window)")
    lines.append("")
    lines.append("Recent chronicler interpretations:")
    for interp in top_interpretations[:5]:
        lines.append(f"- {interp.narrative} (severity:{interp.severity})")
    return "\n".join(lines)
```

This is a code-side deterministic preprocessing step — same pattern as Agent 1's recommended `BundleToolSlice.narrative_excerpt` enrichment, applied to titles.

So **zero `[WMS-GAP]` markers in this trace.** Same conclusion as Agent 1: WMS is sufficient; gaps are at the WNS→WES bundle slice (the leak) and at the hub-input assembly layer (deterministic preprocessing not wired through). For titles specifically, the **biographical snapshot synthesizer** is the new code surface that has to exist for titles to be biographically grounded.

---

## 6. Cross-references with other features (personal shopper)

Titles are PRIMARILY downstream consumers — they're earned in response to player activity that other systems generate. Cross-refs go in both directions.

### 6.1 Heavy shared infrastructure

- **WNS NL3 / NL4 weavers** — shared with every content-generating feature. Need the `new-title` purpose bucket added (see §4.6). *(Agent assignment: WNS.)*
- **WES Execution Planner** — shared. Scope-by-firing-tier rules already correctly include titles at T3+. *(Agent assignment: WNS / Planner+Supervisor.)*
- **WMS L2 evaluators** — shared substrate. `player_milestones`, `progression_identity`, `combat_kills_*`, `gathering_*`, `crafting_*`, `social_quests`, `exploration_*`, `faction_reputation` all feed titles directly. **No new evaluator needed for titles** — the shipped 33 are sufficient.
- **`BundleToolSlice`** — shared by all hubs. Parent_summaries leak (`context_bundle.py:342-370`) affects titles the same as everyone else. Single fix benefits all 8 tools.
- **Orphan detector** — shared cross-ref enforcement.
- **CONSUMER-VERIFIED bonus allow-list** — UNIQUE to titles. No other tool has a consumer-verified field allow-list of this kind. The pattern is good and should be considered for other tools (e.g. material `tags` allow-list, skill `effectType` allow-list).
- **VERIFIED stat_tracker path allow-list** — UNIQUE to titles for now. The pattern is reusable — quests' `requirements.completedQuests`-style cross-refs could use it; skills' learning conditions could use it.

### 6.2 Title-specific cross-refs with adjacent features

- **Quests ↔ Titles** — bidirectional. Agent 1's seed: `cross_ref_hints.granted_by_quest_id` is the title's *flavor cue* about which quest granted it. Reciprocal from Agent 1: `rewards_prose.title_hint` + `cross_ref_hints.title_hint` is the quest's *reward-side reference* to the title. Co-emission is the norm. *(Agent assignment: Titles ↔ Quests. Both agents must agree on the cross_ref hint name.)*
- **NPCs ↔ Titles** — bidirectional but mostly *downstream consumption*. NPCs read player's earned titles for dialogue conditioning (the speechbank). The title's `flavor_faction` and `granted_by_quest_id` flow INTO NPC dialogue context — so the NPC who knighted the player can recognize them by their title. **NPC speechbank conditioning on player titles is a NEW capability** — currently NPCs greet → idle barks → quest offer / complete; titles are not a conditioning variable. Recommendation to NPC agent: add `earned_titles` to dialogue context and let speechbank entries gate on title presence. *(Agent assignment: NPCs.)*
- **Hostiles ↔ Titles** — bidirectional. Hostile kills are the most common title threshold trigger (combat titles). The hostile's species/tier/locality should be queryable for the title's `condition_anchor`. Hostile agent should expose a reverse-lookup: "what hostile species in this region have I been emitting in the bundle's narrative window?" The hub composes the answer from `recent_registry_entries` already. *(Agent assignment: Hostiles. No new schema needed on hostile side; the reverse-lookup is at the hub layer.)*
- **Materials ↔ Titles** — same pattern. Material-gather counts drive gathering titles. The material's tier/element/locality should be queryable for `condition_anchor`. No schema work on materials side; titles hub composes. *(Agent assignment: Materials.)*
- **Skills ↔ Titles** — bidirectional. Some titles require specific skills (`prerequisites.conditions[]` of type `skill`). Some skills are *taught* by earning a title — recursive cross-ref. The title's `cross_ref_hints.required_skill_id` and the skill's `cross_ref_hints.granted_by_title_id` are reciprocal. *(Agent assignment: Skills.)*
- **Chunks ↔ Titles** — weak. Chunks are spatial; titles are biographical. The intersection is locality-rooted titles ("Wolf Slayer of Eastbend") where the chunk's geographic peg helps anchor the title's `flavor_locality`. The chunk agent doesn't need title-specific schema; the title hub reads chunk addresses from the bundle. *(Agent assignment: Chunks. Low-priority.)*
- **Factions ↔ Titles** — Phase 2+ Faction System exists. Titles' `flavor_faction` ties into faction recognition. `FactionAffinityCondition` (proposed addition to `unlock_conditions.py`) lets titles gate on faction standing. The faction system already publishes affinity events to WMS; the `faction_reputation` evaluator interprets them. Title hub composes from the same source. *(No dedicated faction agent in this wave; flagged as cross-cutting consolidation work.)*

### 6.3 Where titles diverge (flavor not shareable)

- **The CONSUMER-VERIFIED bonus allow-list** — title-specific. The bonus keys that actually do something live are the keys with consumers in `equipment_manager`, `combat_manager`, `crafting_manager`, etc. This list cannot be auto-derived; designer maintains it. Pattern is good.
- **The VERIFIED stat_tracker path allow-list** — title-specific. Other tools don't gate their condition fields on a path allow-list at this granularity. Pattern could be reused for `requirements.completedQuests` etc., but the title use case is the canonical one.
- **Reverse-flow generation timing** — titles fire from biographical thresholds, not from forward-looking narrative beats. Other tools (npcs, hostiles, chunks, materials) create things; titles recognize things. The reverse direction means the firing logic differs (see §7).
- **No reward-materialisation flow** — unlike quests, titles don't have an at-receive-time materialisation step. The `bonuses` block is concrete-on-author. No analog to `wes_quest_reward_pregen`/`adapt`.
- **Acquisition-method gating** — titles have an RNG/event/discovery layer (4 acquisition methods) that no other content type has. A title is *earnable*, not *grantable* — the requirements can be met but the title still may not award (event_based_rng with 0.20 chance). This is unique.

### 6.4 Recommendations to other agents

- **Quests agent (Agent 1)**: Already aligned on `granted_by_quest_id` ↔ `title_hint` reciprocal. Confirm naming convention.
- **NPCs agent**: Add `earned_titles` to NPC dialogue context. Let speechbank entries condition on `if 'apprentice_moors_reaver' in earned_titles` style gates. This is what makes the world recognize the player.
- **Hostiles agent**: Ensure hostile JSON output includes `flavor_locality` and primary `species` tag — they feed title generation cross-refs.
- **Materials agent**: Same pattern — `flavor_locality` and primary `element`/`category` tag.
- **Skills agent**: Reciprocal `granted_by_title_id` cross-ref slot when relevant.
- **WNS / Planner+Supervisor agent**: **The single most impactful intervention you can make for title quality is adding `new-title` to NL3 + NL4 + NL5+ `_wes_tool` purpose buckets with proper firing guidance.** Plus close the `BundleToolSlice` parent_summaries leak (shared with quests). Plus add the biographical-snapshot composer as a code-side preprocessor in `wes_orchestrator.py` or `plan_dispatcher.py` before hub-titles is called.

---

## 7. Storage / timing design

### 7.1 The pre-generated title pool — the core architecture

Titles, like quests, must be pre-generated. The fast banner-ribbon UX has no latency slack.

Architecture:

- **Generation event**: WNS NL3 or NL4 firing emits `<WES purpose="new-title">` → planner → hub → tool → static `TitleDefinition` JSON commits to `reg_titles`. The new title joins `TitleDatabase.titles` in-memory (or *would*, if title hot-reload were implemented — see §7.4).
- **Pool storage**: The committed titles live on disk at `progression/titles-generated-<timestamp>.JSON` (sacred-file convention: hand-authored `titles-1.JSON` is untouched; generated titles sit in a sibling file).
- **Earning event**: At every player action hook (kill, craft, gather, level up, quest complete, etc.), `TitleSystem.check_for_title(character)` iterates loaded titles. When a title's `requirements.evaluate(character)` returns True AND the acquisition_method gating passes, `_award_title` fires — banner ribbon UI + `TITLE_EARNED` event.
- **No reward materialisation phase**. Bonuses are baked in at author time. (The only deferred materialization analogous to quest pregen would be locality-suffixed *names* — but locality is captured at author time too, via cross_ref_hints.)

### 7.2 Pool sizing & refresh cadence

How many pre-generated unearned titles should sit in `reg_titles` at any time? Designer-tunable, but my recommendation:

- **Hand-authored novice titles cover the 4 primary domains** (combat, crafting, gathering, utility). These are baked into `titles-1.JSON` — the existing 5 novice titles are the foundation.
- **Pool target: at minimum 1 generated title per `(titleType, difficultyTier)` pair that's reachable by the player's current progression band.** A level-15 player should have, in the pool, at least 1 unearned apprentice and 1 unearned journeyman title in each of the 4 titleTypes they're actively engaging with. So minimum ~8 unearned titles in the relevant tier band.
- **Refresh trigger**: when the player crosses a tier band threshold (apprentice→journeyman, etc.) OR when the WNS fires a `new-title` purpose, OR when the pool drops below the minimum coverage. The first two are event-driven; the third is a periodic check (suggest every game-day, configurable).
- **Stale titles**: a generated title that's been in the pool for a long game-time without earning could be re-evaluated. If the WNS narrative has moved on (the title's `flavor_faction` is no longer narratively active), the title should remain in the pool — the player might still cross the threshold and earn it — but its `narrative` text may want a refresh. **No mandatory deletion** — unlike quests, an unearned title stays earnable.

### 7.3 Firing cadence — threshold-crossings are the natural trigger

Unlike quests (whose firing follows narrative beats), titles have **two distinct firing modes** in the eager-pool architecture:

**(a) Eager pool-generation firing.** At WNS cascade time, `new-title` directives fire whenever the chronicler's narrative implies player-recognition the registry can't yet grant. Generation happens *before* the player crosses the threshold.

**(b) Just-in-time pool-refresh firing.** When the player crosses an existing title's threshold AND the pool of next-tier titles is empty, the runtime can synthesise a `<WES purpose="new-title">` directive directly (skipping the WNS layer) and pump it through the WES side. **This is a runtime-orphan-fix-style direct firing**, structurally similar to the Request Layer's deterministic specs (`world_system/wes/request_layer.py`). Not currently implemented; speculative endpoint (§9).

**(c) Designer-cue firing** for hidden / special titles. A `hidden_discovery` title fires when a specific WMS event sequence is recognized (e.g. "dragons_killed >= 1 AND fire_weapon equipped at the time"). These trigger conditions are *designer-authored*, not WNS-derived. The current shipped pattern: a `prerequisites.conditions[]` with `comment` notes and the LLM author makes a custom condition. Acceptable for now.

The dominant mode is (a). Mode (b) is the safety net.

### 7.4 The hot-reload gap (Half-built per DESIGNER_LEDGER.md)

Per `DESIGNER_LEDGER.md` §"Half-built": **titles are one of the 5 content types that can't hot-reload.** A generated title lands on disk in `reg_titles` and `progression/titles-generated-*.JSON` but `TitleDatabase` (singleton) does not see it until restart. The reload-method pattern exists in `ChunkTemplateDatabase` and `NPCDatabase` — needs to be repeated for `TitleDatabase`.

**Specifically missing**: a `TitleDatabase.reload_from_disk()` (or similar) method that re-reads `progression/titles-*.JSON` files, parses them, and updates `self.titles` in-place. Called by the WES commit path after generation.

Without this fix, the eager-pool architecture is functional but the player must restart to see new titles. Not a `[WES-SCHEMA-GAP]` — this is a *runtime engineering task*, flagged in the half-built section. **Developer ticket**, not a design trace gap.

### 7.5 What the archive looks like

Quests have an archive (Agent 1 §7.5) for chronicler-voice continuity. Do titles? Two observations:

- Titles don't get *consumed* — once earned, they persist in `earned_titles` forever. There's nothing to archive; the title IS its own persistent record.
- However: **the title-earn EVENT** (when, where, after what deeds) is currently underrecorded. `TITLE_EARNED` event payload is `{actor_id, title_id, tier}` — no address, no causal event_id chain, no biographical snapshot snapshot. For future chronicler-voice "the player avenged Captain Vell's brother *three winters ago, the same winter they became the Moors Reaver*" continuity, the title-earn moment should write a richer record.

Recommendation: extend the `TITLE_EARNED` event payload with `{earned_at_address, signature_event_ids[], snapshot_summary}` and have the `progression_identity.py` evaluator's `_eval_title` write these into the interpretation row. This makes the title's earning-moment a query-able chronicle entry. Future chronicler endpoints can reach for "the day they became X."

Marker: `[WMS-ENHANCEMENT]` (deferred) — the existing setup loads enough; this is an enrichment for richer future continuity weaving. **NOT a `[WMS-GAP]`** — the substrate is sufficient.

---

## 8. Diversity & creativity design

User direction: *"the competition is [content] that could be systematically generated, that is the benchmark we must be above; so what information is required for the [title] JSON to have that. I want players to experience adventure not stagnant predictability, however craziness is not the solution either."*

For titles the diversity dials, ranked by impact:

### 8.1 Locality / faction / quest personalization

The dominant diversity dial. A title that says "Wolf Slayer of Eastbend" instead of "Wolf Slayer" is functionally identical at the stat layer and biographically *transformative* at the UX layer. The information that makes this dial work:

- `cross_ref_hints.locality_anchor` (the WNS-firing address's locality name → slugified into the title name suffix when appropriate).
- `cross_ref_hints.faction_anchor` (when the title was earned through faction-aligned activity; the faction name flavors the title).
- `cross_ref_hints.granted_by_quest_id` (when the title was a quest reward; the quest's flavor flows into the title's narrative).

**Default behavior**: locality suffix when activity is concentrated in one address (>70% of relevant kills/crafts/etc. happened there); generic title (no suffix) when activity is geographically diffuse. Threshold designer-tunable.

### 8.2 Tier-distribution discipline (avoid title spam)

The system has 6 tiers. The natural decay curve (novice=1.0 generationChance, master=0.02) means later tiers self-limit. The risk is *novice spam*: every primary activity hits its novice threshold and emits a banner. 

Recommendation:
- Cap novice titles to *one per titleType per primary domain*. The player gets `novice_warrior` OR `novice_archer` OR `novice_brawler` based on their *style* in the early combat hours, not all three.
- **The hub must see `${player_earned_titles}`** (currently a fragment gap, see §4.4) to make this discrimination — otherwise it can't tell that the player already has a novice combat title.

### 8.3 Acquisition-method variance

The 4 acquisition methods (guaranteed_milestone / event_based_rng / hidden_discovery / special_achievement) are themselves a diversity signal. Distribution suggestion:

- **Novice tier**: 100% guaranteed_milestone. These are unmissable.
- **Apprentice tier**: 100% event_based_rng (chance=0.20). Sometimes the threshold-cross awards, sometimes not. Mild RNG keeps players engaged.
- **Journeyman tier**: 100% event_based_rng (chance=0.10). More rare, more felt.
- **Expert tier**: 100% event_based_rng (chance=0.05). Genuinely uncommon.
- **Master tier**: 100% special_achievement (chance=0.02). Earned-through-deed titles, not just thresholds.
- **Special tier**: 100% hidden_discovery (chance=1.0). Trigger-condition-based; surprise reveals.

This is roughly what the existing tier table in `titles-1.JSON` §"difficultyTiers" prescribes; tool prompt already encodes it. Diversity is in maintaining this distribution under generation pressure — the planner/hub must not collapse to "everything's an apprentice event_based_rng" because that's the easiest tier to author.

### 8.4 Bonus-shape variance

Within the consumer-verified allow-list, 5 categories: combat / crafting / gathering / fishing / utility. Each has 4-8 verified bonus keys. Within a tier, the LLM should pick *combinations* that taste different:

- A combat apprentice title with `{meleeDamage, criticalChance}` reads as "blade fighter."
- A combat apprentice title with `{meleeDamage, durabilityBonus}` reads as "durability-first warrior."
- A combat apprentice title with `{meleeDamage, dragonDamage}` reads as "specialized hunter."

Same numeric apprentice tier; very different identity. The tool's tier value bands give the *magnitudes*; the *secondary bonus selection* is where the LLM expresses player identity. The hub should hint at secondaries via flavor_hints (a new field: `secondary_bonus_hints: List[str]`) — currently the tool picks freely, which is fine but unmoored. Designer-tunable.

### 8.5 Narrative voice variance

The narrative line is the title's voice surface. It should taste like:
- The locality where it was earned (a moors title sounds different from a coastal title sounds different from a deep-forest title).
- The faction associated (if any) — a Verdant-Guard title sounds different from a Pilgrim-Order title.
- The chronicler's tone tag at the firing layer (`tone:grim` → grim title narrative; `tone:triumphant` → triumphant; `tone:melancholy` → melancholy).

The information is all available IF the bundle's parent_summaries leak is fixed. The tone tag is in the firing-layer thread. The locality name is in the address. The faction is in the WNS thread tags. The tool's narrative line should integrate all three.

### 8.6 Specialization vs. generalization

A diversity-of-shape dial:

- **Specialized titles** — "Killed 500 copperlash riders specifically." Activity-domain narrow. Many of these.
- **Compound titles** — "Killed 500 enemies of any kind AND survived without dying for 1000 game-seconds." Composite triggers. Some of these.
- **Generalized titles** — "Reached level 15 in any class." Activity-domain wide. Few of these.

Distribution suggestion across the pool: 65% specialized, 25% compound, 10% generalized. Compound titles are particularly diverse because the composite conditions vary endlessly. The current tool prompt allows 1-3 conditions; the diversity is in *which* conditions chain together.

### 8.7 Player-action sensitivity

Titles are *the most player-sensitive feature in the game* — every title is, by definition, about what the player did. The two distinct sensitivity loops:

- **At pool-generation time (cascade)**: the WNS thread tags (`agency:player`, `agency:npc`, etc.) influence whether a title should be generated for this scope at all. Titles fire from `agency:player` threads in particular.
- **At pool-curation time**: the hub's `${player_earned_titles}` + `${biographical_snapshot}` (both currently `[FRAGMENT-GAP]`s) drive which titles to add to the pool next. Fill the gaps in the player's title-tree, not the dense areas.

The biographical snapshot composer (§5.1) is the single piece of new code that unlocks both diversity dials.

---

## 9. Speculative future endpoints

Things the user has flagged elsewhere, or that this trace surfaces as natural next-step LLM endpoints.

### 9.1 `wes_title_pool_refresh` — just-in-time pool topping

When the player crosses a tier threshold and the next-tier pool is empty for the relevant titleType, fire a direct `wes_hub_titles` request without going through WNS. Structurally similar to the Request Layer's deterministic spec construction.

- **Trigger**: `TitleSystem.check_for_title` returns no candidate, AND `reg_titles.count(filter={titleType, next_tier, unearned})` < 1.
- **Inputs**: player's current biographical snapshot + earned titles + recent activity address.
- **Outputs**: a generated apprentice/journeyman/etc title joining the pool.
- **Latency**: not player-facing immediate. The just-crossed title (the one that fired this) is what banner-ribbons; the new pool title is preparation for next time. So latency budget is generous (1-2 minutes is fine).

Endpoint count: not a new LLM task — reuses `wes_hub_titles` + `wes_tool_titles`. New code path: a direct dispatcher entry that builds a synthetic plan-step for the titles tool. Prompt fragment file: none new.

### 9.2 `wes_title_narrative_refresh` — keep title flavor current

When a generated title has been in the pool for a long game-time without being earned AND the WNS thread it's flavored after has moved on materially (the faction has dispersed, the locality's situation has changed), refresh the title's `narrative` text. The bonuses, prerequisites, and tier stay frozen — only the voice gets a new pass.

- **Trigger**: on offer-time check OR periodic sweep — title's flavor staleness exceeds threshold.
- **Inputs**: original `TitleDefinition` + current WNS thread state at the title's `flavor_locality`.
- **Outputs**: a patched narrative string. Apply to the title's record.

Endpoint count: could fold into a generalized `wes_content_narrative_refresh` shared with quests and other narrative-bearing artifacts. Designer call. Probably premature.

### 9.3 `wes_title_chronicler_summarizer` — chronicler-voice title earn record

Agent 1 §9.4 surfaced this for quests. Same applies for titles. At award time, instead of `TITLE_EARNED` writing just `{actor_id, title_id, tier}`, the chronicler emits a 1-line "the day they became X" record into the WMS interpretation store, with signature_event_ids cross-linked.

- **Where it lives**: extend `progression_identity.py` evaluator's `_eval_title` — already runs on `title_earned` events. Currently writes a generic template `"Player has earned the title {title}."` Extend to richer template using the title's `narrative` field + cross-linked signature events.
- **Output**: enriched `InterpretedEvent` with multi-sentence chronicler narrative + cross-ref event_ids.

Endpoint count: NOT a new LLM task — just enrichment of the existing evaluator. Could optionally fire an LLM-side polish pass at low priority; probably the deterministic enrichment suffices.

### 9.4 `wes_title_curator` — pool diversity sweep

Periodically reviews the title pool for diversity health: tier distribution skew, titleType concentration, redundant near-duplicates. Emits removal/refresh recommendations.

- **Trigger**: weekly game-time periodic sweep.
- **Inputs**: full `reg_titles` snapshot + player's `earned_titles`.
- **Outputs**: `{titles_to_archive: [...], refresh_candidates: [...]}`.

Endpoint count: +1 LLM task. Could fold into the supervisor with a "title diversity health check" subroutine — designer call.

### 9.5 `wes_faction_recognition_title` — knighting / coronation titles

A distinct category of titles emerge from faction milestones, not player threshold-crossings. When a faction's affinity toward the player crosses a meaningful threshold (e.g. `faction:verdant_guard` standing reaches +0.7), a recognition title should fire: "Knighted by the Verdant Guard."

This requires:
- A `FactionAffinityCondition` in `unlock_conditions.py` (flagged in §5 as `[WES-SCHEMA-GAP]`).
- An event hook in `FactionSystem` that triggers a `<WES purpose="new-title">` directive when the threshold crosses.
- Optionally: faction-side configuration of which standing tiers grant titles ("knight" at 0.7, "champion" at 0.85, "legend" at 0.95).

Endpoint count: not a new LLM task — reuses `wes_hub_titles` + `wes_tool_titles`. New runtime hook in faction system. Schema additions per §2.1.

### 9.6 `wes_title_modifier` — post-creation flavor evolution

Analogous to Agent 1's `wes_quest_modifier`. When a title's `flavor_locality` undergoes major events that change the locality's character, the title's name and narrative can drift to reflect the player's evolving relationship with the place. "Wolf Slayer of Eastbend" → "Wolf Slayer of Burned Eastbend" after the village burns.

- **Trigger**: WMS interpretation at the title's `flavor_locality` matches certain category patterns (destruction, transformation, regime change).
- **Inputs**: current title + the transforming WMS event(s).
- **Outputs**: patched name and narrative.

Endpoint count: +1 LLM task OR fold into the shared `wes_content_narrative_refresh` from §9.2. Probably premature for the v4 ship.

### 9.7 Big-picture: the 2-endpoint title pipeline grows to potentially 4-5

Current: `wes_tool_titles` + `wes_hub_titles` (2).
With speculatives: + `wes_title_pool_refresh` (no LLM, just code) + `wes_title_narrative_refresh` (folds into shared) + `wes_title_chronicler_summarizer` (folds into evaluator) + `wes_title_curator` (folds into supervisor) + `wes_faction_recognition_title` (no LLM, just runtime hook) + `wes_title_modifier` (folds into shared modifier).

**Pragmatic count: 2 LLM endpoints at maturity** — the existing two are the load-bearing minimum, and all the speculatives fold into shared infrastructure or non-LLM runtime hooks. This is a smaller endpoint footprint than quests (5-6) because titles' "modifier" and "archive" needs naturally fold into either deterministic code or shared multi-feature endpoints.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Compose the biographical snapshot pre-hub.** A deterministic code path in `wes_orchestrator.py` or `plan_dispatcher.py` that synthesises a 5-15-line digest of the player's recent activity from StatStore + WMS interpretations, scoped to the title's domain hint, before `wes_hub_titles` runs. **Without this, the title narrative is generic regardless of how good the prompt is** — the LLM cannot write "you have cut down enough copperlash riders to know their rhythms in your sleep" without seeing the kill count. Highest leverage for title quality. Shared substrate with cross-tool needs (Agent 1's quest-narrative slot benefits too).

2. **Add `new-title` to NL3 + NL4 + NL5 `_wes_tool` purpose buckets in `narrative_fragments_nl{3,4,5}.json` with firing guidance.** Without this, titles only emit as cross-refs from quests — the WNS-driven title-firing path doesn't exist. Designer-task at the WNS-fragment layer.

3. **Close the `BundleToolSlice` parent_summaries leak (`context_bundle.py:342-370`).** Shared with all 8 content tools. For titles specifically, this is what carries the *tone* and *world-recognition voice* through to the narrative line.

Speculative but very-tractable runtime fixes:
- Title hot-reload (`TitleDatabase.reload_from_disk()`) — flagged in DESIGNER_LEDGER as half-built.
- `FactionAffinityCondition` in `unlock_conditions.py` to unlock faction-recognition titles.
- Schema additions: `flavor_locality`, `flavor_faction`, `granted_by_quest_id`, `signature_deeds[]`, `tags[]`, `earned_at_address` on `TitleDefinition`. All backward-compatible (Optional / default).

Everything else in this trace — diversity dials, modifier-AI, pool-refresh — is downstream of those three.
